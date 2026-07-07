"""
Task Decomposer Service.

Core capability of Day 3-4:
Given a task, break it into tiny, neurodivergent-friendly micro-actions
using the LLM client (defaults to mock for local/test use).

Responsibilities:
- Validate task ownership (user_id scoped — 404 if not found)
- Skip regeneration if micro-actions exist and force_regenerate=False
- Delete open micro-actions on force_regenerate=True
- Build structured LLM prompts
- Call LLM client and validate response with Pydantic
- Fall back to rule-based decomposition if LLM fails
- Persist micro-actions and return TaskDecomposeResponse
"""

import logging
import time
from typing import Optional, List, Dict, Any

from psycopg2.extensions import connection as Connection

from app.core import supabase_queries as sq
from app.llm.base import BaseLLMClient, LLMError
from app.llm.client_factory import get_llm_client
from app.schemas.micro_action_schema import (
    MicroAction as MicroActionSchema,
    MicroActionCreate,
    TaskDecomposeRequest,
    TaskDecomposeResponse,
    MakeSmallerRequest,
    MakeSmallerResponse,
)
from app.prompts.prompt_versions import TASK_DECOMPOSITION_PROMPT_VERSION
from app.utils.llm_costs import estimate_llm_cost
from app.services.llm_rate_limit_service import check_rate_limit, log_rate_limit_skip

logger = logging.getLogger(__name__)
PROMPT_VERSION = TASK_DECOMPOSITION_PROMPT_VERSION

# ──────────────────────────────────────────────────────────────────────
# LLM Prompts
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are NeuroSentio Daily Copilot, supporting neurodivergent users.
Break tasks into tiny, concrete, low-friction actions (2-15 mins).

Rules:
- Output raw JSON only. No markdown formatting or explanation.
- Each action must be specific and physically startable.
- Avoid vague terms ("focus", "progress").
- Use gentle, non-shaming, non-medical language.
- Never use: "just", "simply", "easy", "obviously".
- If current energy is low, return max 2 actions.
- Sort by lowest friction first.

Format:
{
  "micro_actions": [
    {
      "title": "Short title",
      "description": "Short explanation",
      "duration_minutes": 5,
      "energy_cost": "low",
      "sensory_cost": "low",
      "friction_level": "low"
    }
  ]
}
Allowed costs/friction: low | medium | high
"""


def _build_user_prompt(
    task: Dict[str, Any],
    current_energy: Optional[int],
    sensory_state: Optional[str],
    max_actions: int,
) -> str:
    energy_str = str(current_energy) if current_energy is not None else "unknown"
    sensory_str = sensory_state or "unknown"
    due_date_str = str(task.get("date")) if task.get("date") else "not set"
    description_str = task.get("subtitle") or "no description provided"

    return (
        f"Task title:\n{task['title']}\n\n"
        f"Task description:\n{description_str}\n\n"
        f"Due date:\n{due_date_str}\n\n"
        f"Current energy:\n{energy_str}\n\n"
        f"Sensory state:\n{sensory_str}\n\n"
        f"Maximum number of actions:\n{max_actions}\n\n"
        "Break this task into tiny next actions.\n\n"
        "The first action must be extremely easy to start."
    )


def _fallback_decompose(
    task_title: str,
    current_energy: Optional[int],
    max_actions: int,
) -> tuple[List[Dict[str, Any]], str]:
    is_recovery = current_energy is not None and current_energy < 30

    if is_recovery:
        actions = [
            {
                "title": f"Open the place where '{task_title}' lives",
                "description": "Just open the file, app, or page related to this task. You don't need to do anything else yet.",
                "duration_minutes": 2,
                "energy_cost": "low",
                "sensory_cost": "low",
                "friction_level": "low",
                "sort_order": 0,
            },
            {
                "title": "Write one sentence about where to start",
                "description": "Write a single rough sentence — even just 'I think I need to…' It doesn't have to be complete.",
                "duration_minutes": 3,
                "energy_cost": "low",
                "sensory_cost": "low",
                "friction_level": "low",
                "sort_order": 1,
            },
        ]
        return actions[:min(max_actions, 2)], "recovery"

    actions = [
        {
            "title": f"Open the place where '{task_title}' lives",
            "description": "Start by opening only the file, tool, or workspace related to this task. You don't need to do anything yet — just open it.",
            "duration_minutes": 2,
            "energy_cost": "low",
            "sensory_cost": "low",
            "friction_level": "low",
            "sort_order": 0,
        },
        {
            "title": "Write down the very first physical movement",
            "description": "What is the very first physical movement needed? (e.g. click 'New File', type 'Hello'). Write it down.",
            "duration_minutes": 2,
            "energy_cost": "low",
            "sensory_cost": "low",
            "friction_level": "low",
            "sort_order": 1,
        },
        {
            "title": "Do one tiny visible action for 5 minutes",
            "description": "Pick the smallest possible physical action right now. Set a 5-minute timer. Stop when it rings — that's the whole task.",
            "duration_minutes": 5,
            "energy_cost": "low",
            "sensory_cost": "low",
            "friction_level": "low",
            "sort_order": 2,
        },
    ]
    return actions[:max_actions], "normal"


_VALID_COSTS = {"low", "medium", "high"}

def _parse_llm_output(raw: dict, max_actions: int) -> List[Dict[str, Any]]:
    if "micro_actions" not in raw or not isinstance(raw["micro_actions"], list):
        raise ValueError("LLM output missing 'micro_actions' list")

    items = raw["micro_actions"][:max_actions]
    result = []

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"micro_actions[{idx}] is not a dict")

        title = item.get("title", "").strip()
        if not title:
            raise ValueError(f"micro_actions[{idx}] missing 'title'")

        energy_cost = item.get("energy_cost", "low")
        sensory_cost = item.get("sensory_cost", "low")
        friction_level = item.get("friction_level", "low")

        if energy_cost not in _VALID_COSTS: energy_cost = "low"
        if sensory_cost not in _VALID_COSTS: sensory_cost = "low"
        if friction_level not in _VALID_COSTS: friction_level = "low"

        duration = item.get("duration_minutes")
        if duration is not None:
            try:
                duration = int(duration)
                if duration < 1 or duration > 120: duration = 5
            except (TypeError, ValueError):
                duration = 5

        result.append({
            "title": title,
            "description": item.get("description"),
            "duration_minutes": duration,
            "energy_cost": energy_cost,
            "sensory_cost": sensory_cost,
            "friction_level": friction_level,
            "sort_order": idx,
        })

    return result

async def decompose_task(
    db: Connection,
    user_id: str,
    task_id: str,
    request: TaskDecomposeRequest,
    llm_client: Optional[BaseLLMClient] = None,
) -> TaskDecomposeResponse:
    # ── 1. Validate task ownership ────────────────────────────────────
    task = sq.get_task(db, user_id, task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found for user {user_id}")

    # ── 2. Check for existing micro-actions ───────────────────────────
    existing = sq.get_micro_actions_for_task(db, user_id, task_id)
    if existing and not request.force_regenerate:
        return TaskDecomposeResponse(
            task_id=task_id,
            mode=_infer_mode(request.current_energy),
            source="existing",
            message="Let's make this easier to start. Your micro-actions are ready.",
            micro_actions=[MicroActionSchema(**m) for m in existing],
        )

    # ── 3. Delete open micro-actions on force_regenerate ─────────────
    if request.force_regenerate:
        sq.delete_open_micro_actions_for_task(db, user_id, task_id)

    # ── 4. Build prompts ──────────────────────────────────────────────
    source = "llm"
    actions: List[Dict[str, Any]] = []
    mode = _infer_mode(request.current_energy)
    llm_status = "success"
    error_type = None
    latency_ms = None
    provider = "unknown"
    model = ""
    
    from app.core.llm_config import get_llm_settings
    settings = get_llm_settings()
    model = settings.llm_model or ""

    user_prompt = _build_user_prompt(
        task=task,
        current_energy=request.current_energy,
        sensory_state=request.sensory_state,
        max_actions=request.max_actions,
    )

    t0 = time.monotonic()
    try:
        if llm_client is None:
            llm_client = get_llm_client()
            
        client_class = llm_client.__class__.__name__
        provider = client_class.lower().replace("client", "")

        rate_result = check_rate_limit(db, user_id)
        if not rate_result["allowed"]:
            logger.warning("Rate limit exceeded for user %s: %s", user_id, rate_result["reason"])
            sq.log_llm_usage(
                db=db, user_id=user_id, feature="task_decomposition",
                provider=provider, model=model or "", status="rate_limited",
            )
            actions, mode = _fallback_decompose(task["title"], request.current_energy, request.max_actions)
            source = "fallback"
            llm_status = "skipped_rate_limit"
        else:
            raw = await llm_client.generate_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema_name="TaskDecomposeResponse",
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            actions = _parse_llm_output(raw, request.max_actions)
            source = "llm"
            llm_status = "success"

    except (LLMError, ValueError) as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("LLM setup or call failed — using fallback decomposition. Reason: %s", exc)
        actions, mode = _fallback_decompose(task["title"], request.current_energy, request.max_actions)
        source = "fallback"
        llm_status = "fallback"
        error_type = type(exc).__name__

    cost = estimate_llm_cost(provider, model, None, None)
    sq.log_llm_usage(
        db=db, user_id=user_id, feature="task_decomposition",
        provider=provider, model=model or "", status=llm_status,
        latency_ms=latency_ms, cost=cost
    )

    # ── 6. Persist ────────────────────────────────────────────────────
    sq.save_micro_actions(db, user_id, task_id, None, actions)
    # Re-fetch to get IDs
    saved = sq.get_micro_actions_for_task(db, user_id, task_id)
    
    # We only want the recently added ones if force_regenerate didn't delete the done ones
    # But since force_regenerate deletes 'open' ones, 'saved' contains all of them.
    # We just return them all.

    message = _build_message(mode, len(actions))

    return TaskDecomposeResponse(
        task_id=task_id,
        mode=mode,
        source=source,
        message=message,
        micro_actions=[MicroActionSchema(**m) for m in saved],
    )


async def make_micro_action_smaller(
    db: Connection,
    user_id: str,
    micro_action_id: str,
    request: MakeSmallerRequest,
    llm_client: Optional[BaseLLMClient] = None,
) -> MakeSmallerResponse:
    original = sq.get_micro_action_by_id(db, user_id, micro_action_id)
    if original is None:
        raise ValueError(f"MicroAction {micro_action_id} not found for user {user_id}")

    task_id = original["task_id"]
    max_sort = sq.get_max_sort_order(db, user_id, task_id)
    is_recovery = request.current_energy is not None and request.current_energy < 30

    if is_recovery:
        smaller = [
            {
                "title": f"Re-read: {original['title']}",
                "description": "Just re-read the action. You don't have to do it yet.",
                "duration_minutes": 1,
                "energy_cost": "low",
                "sensory_cost": "low",
                "friction_level": "low",
                "sort_order": max_sort + 1,
                "parent_id": original["id"],
            },
        ]
    else:
        smaller = [
            {
                "title": f"Prepare for: {original['title']}",
                "description": "Open the tools or files you'll need. You don't need to start the actual work yet.",
                "duration_minutes": 2,
                "energy_cost": "low",
                "sensory_cost": "low",
                "friction_level": "low",
                "sort_order": max_sort + 1,
                "parent_id": original["id"],
            },
            {
                "title": f"Start the first movement: {original['title']}",
                "description": "Do just the first physical movement — open, type one line, or click one thing. Then pause if needed.",
                "duration_minutes": 3,
                "energy_cost": "low",
                "sensory_cost": "low",
                "friction_level": "low",
                "sort_order": max_sort + 2,
                "parent_id": original["id"],
            },
            {
                "title": f"Note what you did for: {original['title']}",
                "description": "Write one sentence about what you just did. That's it.",
                "duration_minutes": 2,
                "energy_cost": "low",
                "sensory_cost": "low",
                "friction_level": "low",
                "sort_order": max_sort + 3,
                "parent_id": original["id"],
            },
        ]

    sq.set_micro_action_status(db, user_id, original["id"], "deferred")
    original["status"] = "deferred"
    
    sq.save_micro_actions(db, user_id, task_id, None, smaller)
    all_mas = sq.get_micro_actions_for_task(db, user_id, task_id)
    saved_smaller = [m for m in all_mas if str(m["parent_id"]) == str(original["id"])]

    return MakeSmallerResponse(
        original_micro_action=MicroActionSchema(**original),
        smaller_actions=[MicroActionSchema(**m) for m in saved_smaller],
    )


def _infer_mode(current_energy: Optional[int]) -> str:
    if current_energy is not None and current_energy < 30:
        return "recovery"
    return "normal"


def _build_message(mode: str, count: int) -> str:
    if mode == "recovery":
        return (
            "Today may need a lighter version. "
            "Let's start with one small step."
        )
    return (
        f"Let's make this easier to start. "
        f"Here are {count} tiny actions — pick the first one."
    )
