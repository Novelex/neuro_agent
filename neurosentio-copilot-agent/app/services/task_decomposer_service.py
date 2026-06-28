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

Product principle:
All generated language must be gentle, specific, non-shaming, and low-friction.
"""

import asyncio
import logging
import time
from typing import Optional, List

from sqlalchemy.orm import Session

from app.repositories.task_repository import task_repository
from app.repositories.micro_action_repository import micro_action_repository
from app.repositories.llm_usage_repository import llm_usage_repository
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
from app.models.micro_action import MicroAction as MicroActionModel
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
    task,
    current_energy: Optional[int],
    sensory_state: Optional[str],
    max_actions: int,
) -> str:
    energy_str = str(current_energy) if current_energy is not None else "unknown"
    sensory_str = sensory_state or "unknown"
    due_date_str = str(task.due_date) if task.due_date else "not set"
    description_str = task.description or "no description provided"

    return (
        f"Task title:\n{task.title}\n\n"
        f"Task description:\n{description_str}\n\n"
        f"Priority:\n{task.priority}\n\n"
        f"Due date:\n{due_date_str}\n\n"
        f"Current energy:\n{energy_str}\n\n"
        f"Sensory state:\n{sensory_str}\n\n"
        f"Maximum number of actions:\n{max_actions}\n\n"
        "Break this task into tiny next actions.\n\n"
        "The first action must be extremely easy to start."
    )


# ──────────────────────────────────────────────────────────────────────
# Fallback — rule-based decomposition (no LLM required)
# ──────────────────────────────────────────────────────────────────────

def _fallback_decompose(
    task_title: str,
    current_energy: Optional[int],
    max_actions: int,
) -> tuple[List[MicroActionCreate], str]:
    """
    Returns (list of MicroActionCreate, mode).
    Used when the LLM is unavailable or returns invalid output.
    """
    is_recovery = current_energy is not None and current_energy < 30

    if is_recovery:
        actions = [
            MicroActionCreate(
                title=f"Open the place where '{task_title}' lives",
                description=(
                    "Just open the file, app, or page related to this task. "
                    "You don't need to do anything else yet."
                ),
                duration_minutes=2,
                energy_cost="low",
                sensory_cost="low",
                friction_level="low",
                sort_order=0,
            ),
            MicroActionCreate(
                title="Write one sentence about where to start",
                description=(
                    "Write a single rough sentence — even just 'I think I need to…' "
                    "It doesn't have to be complete."
                ),
                duration_minutes=3,
                energy_cost="low",
                sensory_cost="low",
                friction_level="low",
                sort_order=1,
            ),
        ]
        return actions[:min(max_actions, 2)], "recovery"

    actions = [
        MicroActionCreate(
            title=f"Open the place where '{task_title}' lives",
            description=(
                "Start by opening only the file, tool, or workspace related to this task. "
                "You don't need to do anything yet — just open it."
            ),
            duration_minutes=2,
            energy_cost="low",
            sensory_cost="low",
            friction_level="low",
            sort_order=0,
        ),
        MicroActionCreate(
            title="Write one rough note about what needs to happen",
            description=(
                "Add one imperfect sentence or bullet. "
                "It does not need to be complete or correct. Just one thought."
            ),
            duration_minutes=5,
            energy_cost="low",
            sensory_cost="low",
            friction_level="low",
            sort_order=1,
        ),
        MicroActionCreate(
            title="Do one tiny visible action for 5 minutes",
            description=(
                "Pick the smallest possible physical action right now. "
                "Set a 5-minute timer. Stop when it rings — that's the whole task."
            ),
            duration_minutes=5,
            energy_cost="low",
            sensory_cost="low",
            friction_level="low",
            sort_order=2,
        ),
    ]
    return actions[:max_actions], "normal"


# ──────────────────────────────────────────────────────────────────────
# LLM output → MicroActionCreate list
# ──────────────────────────────────────────────────────────────────────

_VALID_COSTS = {"low", "medium", "high"}


def _parse_llm_output(raw: dict, max_actions: int) -> List[MicroActionCreate]:
    """
    Validates the LLM output dict and converts it to MicroActionCreate objects.
    Raises ValueError if the shape is invalid or fields are out of range.
    """
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

        if energy_cost not in _VALID_COSTS:
            energy_cost = "low"
        if sensory_cost not in _VALID_COSTS:
            sensory_cost = "low"
        if friction_level not in _VALID_COSTS:
            friction_level = "low"

        duration = item.get("duration_minutes")
        if duration is not None:
            try:
                duration = int(duration)
                if duration < 1 or duration > 120:
                    duration = 5  # clamp to safe default
            except (TypeError, ValueError):
                duration = 5

        result.append(
            MicroActionCreate(
                title=title,
                description=item.get("description"),
                duration_minutes=duration,
                energy_cost=energy_cost,
                sensory_cost=sensory_cost,
                friction_level=friction_level,
                sort_order=idx,
            )
        )

    return result


# ──────────────────────────────────────────────────────────────────────
# Public service functions
# ──────────────────────────────────────────────────────────────────────

async def decompose_task(
    db: Session,
    user_id: str,
    task_id: str,
    request: TaskDecomposeRequest,
    llm_client: Optional[BaseLLMClient] = None,
) -> TaskDecomposeResponse:
    """
    Main entry point.

    1. Fetch task — 404 if not owned by user.
    2. If micro-actions exist and force_regenerate=False → return existing.
    3. If force_regenerate=True → delete open micro-actions.
    4. Call LLM → validate → save.
    5. On failure → fallback rule-based decomposition.
    """
    # ── 1. Validate task ownership ────────────────────────────────────
    task = task_repository.get_by_id(db, task_id, user_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found for user {user_id}")

    # ── 2. Check for existing micro-actions ───────────────────────────
    existing = micro_action_repository.get_by_task(db, user_id, task_id)
    if existing and not request.force_regenerate:
        return TaskDecomposeResponse(
            task_id=task_id,
            mode=_infer_mode(request.current_energy),
            source="existing",
            message="Let's make this easier to start. Your micro-actions are ready.",
            micro_actions=[MicroActionSchema.model_validate(m) for m in existing],
        )

    # ── 3. Delete open micro-actions on force_regenerate ─────────────
    if request.force_regenerate:
        micro_action_repository.delete_open_for_task(db, user_id, task_id)

    # ── 4. Build prompts ──────────────────────────────────────────────
    if llm_client is None:
        llm_client = get_llm_client()

    user_prompt = _build_user_prompt(
        task=task,
        current_energy=request.current_energy,
        sensory_state=request.sensory_state,
        max_actions=request.max_actions,
    )

    # ── 5. Call LLM (with fallback on any error) ──────────────────────
    source = "llm"
    actions: List[MicroActionCreate] = []
    mode = _infer_mode(request.current_energy)
    llm_status = "success"
    error_type = None
    latency_ms = None

    # ── Rate limit check ──────────────────────────────────────────────
    client_class = llm_client.__class__.__name__
    provider = "mock" if client_class == "MockLLMClient" else client_class.lower().replace("client", "")
    from app.core.llm_config import get_llm_settings
    settings = get_llm_settings()
    model = settings.llm_model or None

    rate_result = check_rate_limit(db, user_id)
    if not rate_result["allowed"]:
        logger.warning("Rate limit exceeded for user %s: %s", user_id, rate_result["reason"])
        log_rate_limit_skip(
            db=db, user_id=user_id, feature="task_decomposition",
            provider=provider, reason=rate_result["reason"],
            prompt_version=PROMPT_VERSION,
        )
        actions, mode = _fallback_decompose(task.title, request.current_energy, request.max_actions)
        source = "fallback"
        llm_status = "skipped_rate_limit"
    else:
        t0 = time.monotonic()
        try:
            raw = await llm_client.generate_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema_name="TaskDecomposeResponse",
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            actions = _parse_llm_output(raw, request.max_actions)
            source = "mock" if client_class == "MockLLMClient" else "llm"
            llm_status = "success"

        except (LLMError, ValueError, Exception) as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            logger.warning("LLM call failed — using fallback decomposition. Reason: %s", exc)
            actions, mode = _fallback_decompose(task.title, request.current_energy, request.max_actions)
            source = "fallback"
            llm_status = "fallback"
            error_type = type(exc).__name__

        # Log usage metadata (no prompt text stored)
        cost = estimate_llm_cost(provider, model, None, None)
        llm_usage_repository.create_log(
            db=db,
            user_id=user_id,
            feature="task_decomposition",
            provider=provider,
            model=model,
            prompt_version=PROMPT_VERSION,
            status=llm_status,
            error_type=error_type,
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
            request_metadata={"schema_name": "TaskDecomposeResponse", "prompt_version": PROMPT_VERSION},
        )

    # ── 6. Persist ────────────────────────────────────────────────────
    saved = micro_action_repository.create_many(db, user_id, task_id, actions)

    # ── 7. Build message ──────────────────────────────────────────────
    message = _build_message(mode, len(saved))

    return TaskDecomposeResponse(
        task_id=task_id,
        mode=mode,
        source=source,
        message=message,
        micro_actions=[MicroActionSchema.model_validate(m) for m in saved],
    )


async def make_micro_action_smaller(
    db: Session,
    user_id: str,
    micro_action_id: str,
    request: MakeSmallerRequest,
    llm_client: Optional[BaseLLMClient] = None,
) -> MakeSmallerResponse:
    """
    Splits one micro-action into 1–3 smaller child actions.

    Behavior change (Day 5):
    - The original is marked 'deferred' so dashboard stops surfacing it.
    - Each child stores parent_micro_action_id = original.id.
    - Children are inserted after the original in sort_order.
    """
    original = micro_action_repository.get_by_id(db, user_id, micro_action_id)
    if original is None:
        raise ValueError(f"MicroAction {micro_action_id} not found for user {user_id}")

    task_id = original.task_id
    max_sort = micro_action_repository.get_max_sort_order(db, user_id, task_id)
    is_recovery = request.current_energy is not None and request.current_energy < 30

    if is_recovery:
        smaller = [
            MicroActionCreate(
                title=f"Re-read: {original.title}",
                description="Just re-read the action. You don't have to do it yet.",
                duration_minutes=1,
                energy_cost="low",
                sensory_cost="low",
                friction_level="low",
                sort_order=max_sort + 1,
                parent_micro_action_id=original.id,
            ),
        ]
    else:
        smaller = [
            MicroActionCreate(
                title=f"Prepare for: {original.title}",
                description=(
                    "Open the tools or files you'll need. "
                    "You don't need to start the actual work yet."
                ),
                duration_minutes=2,
                energy_cost="low",
                sensory_cost="low",
                friction_level="low",
                sort_order=max_sort + 1,
                parent_micro_action_id=original.id,
            ),
            MicroActionCreate(
                title=f"Start the first movement: {original.title}",
                description=(
                    "Do just the first physical movement — "
                    "open, type one line, or click one thing. Then pause if needed."
                ),
                duration_minutes=3,
                energy_cost="low",
                sensory_cost="low",
                friction_level="low",
                sort_order=max_sort + 2,
                parent_micro_action_id=original.id,
            ),
            MicroActionCreate(
                title=f"Note what you did for: {original.title}",
                description="Write one sentence about what you just did. That's it.",
                duration_minutes=2,
                energy_cost="low",
                sensory_cost="low",
                friction_level="low",
                sort_order=max_sort + 3,
                parent_micro_action_id=original.id,
            ),
        ]

    # ── Defer the original so dashboard moves to child actions ────────
    micro_action_repository.set_status_direct(db, user_id, original.id, "deferred")

    # Refresh so the returned schema reflects the new status
    db.refresh(original)

    saved = micro_action_repository.create_many(db, user_id, task_id, smaller)

    return MakeSmallerResponse(
        original_micro_action=MicroActionSchema.model_validate(original),
        smaller_actions=[MicroActionSchema.model_validate(m) for m in saved],
    )


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

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
