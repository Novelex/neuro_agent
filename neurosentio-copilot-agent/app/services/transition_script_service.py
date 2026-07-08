"""
Transition Script Service.

Generates neurodivergent-friendly transition scripts.
Currently uses rule-based fallback logic without DB ORM dependencies.
"""

import logging
import uuid
import time
from typing import Optional, List
from psycopg2.extensions import connection as Connection

from app.core import supabase_queries as sq
from app.schemas.transition_script_schema import (
    TransitionScriptGenerateRequest,
    TransitionScriptGenerateResponse,
    TransitionScriptLLMOutput,
)
from app.llm.client_factory import get_llm_client
from app.services.llm_rate_limit_service import check_rate_limit, log_rate_limit_skip
from app.prompts import transition_scripts as ts_prompts

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Template library — rule-based fallback
# ──────────────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, dict] = {
    "leaving_house": {
        "title": "Leaving the house",
        "steps_normal": [
            "Check: keys.",
            "Check: phone.",
            "Check: wallet.",
            "Check: water bottle.",
            "One last look at the room. You're ready.",
        ],
        "steps_recovery": [
            "Check: keys, phone, wallet.",
            "You can go. You have what you need.",
        ],
        "message": "You only need the first movement.",
    },
    "starting_work": {
        "title": "Starting work",
        "steps_normal": [
            "Put your phone face down or in another room.",
            "Open only the document or tool for this task.",
            "Set a 10-minute timer.",
            "Write one rough sentence or make one small action.",
            "When the timer rings, you can stop or keep going.",
        ],
        "steps_recovery": [
            "Open only what you need.",
            "Set a 5-minute timer.",
            "Write one rough sentence. It does not need to be good.",
        ],
        "message": "You only need the first movement. The rest follows.",
    },
    "making_call": {
        "title": "Making a call",
        "steps_normal": [
            "Write the person's name or number.",
            "Write one thing you need to say or ask.",
            "Your first sentence: 'Hi, I'm calling about [topic].'",
            "Dial. You can pause before speaking.",
            "It's okay to say: 'Give me a moment, I'm just looking at my notes.'",
        ],
        "steps_recovery": [
            "Write the one thing you need to say.",
            "Start with: 'Hi, I'll be brief.'",
            "Dial. You can pause.",
        ],
        "message": "The call only needs a first sentence.",
    },
    "ending_day": {
        "title": "Ending the day",
        "steps_normal": [
            "Write: 'Tomorrow I start with...' — one sentence.",
            "Close any open tabs or documents.",
            "Stand up. The day is done.",
        ],
        "steps_recovery": [
            "Close all tabs.",
            "Stand up. Work is over.",
        ],
        "message": "It is okay to stop now.",
    },
    "switching_context": {
        "title": "Switching tasks",
        "steps_normal": [
            "Write down where you left off on the old task.",
            "Close its window.",
            "Take one deep breath.",
            "Write one sentence about what the new task needs first.",
            "Open the new tool.",
        ],
        "steps_recovery": [
            "Write 'Start here next:' and one sentence.",
            "Close current work. Open only the next thing.",
        ],
        "message": "Pick one small step.",
    },
    "recovery_break": {
        "title": "Recovery break",
        "steps_normal": [
            "Step away from the screen.",
            "Drink a glass of water.",
            "Sit somewhere quieter if possible.",
            "No productivity requirement right now.",
            "Return when you feel ready — even 5 minutes helps.",
        ],
        "steps_recovery": [
            "Step away from the screen.",
            "Drink water.",
            "Rest. No tasks right now.",
        ],
        "message": "Today may need a lighter version. Rest is productive.",
    },
    "custom": {
        "title": "Transition",
        "steps_normal": [
            "Take a breath.",
            "Write one sentence about what comes next.",
            "Do the first physical step.",
        ],
        "steps_recovery": [
            "Take a breath.",
            "Do one small thing.",
        ],
        "message": "You only need the first movement.",
    },
}


def _get_template_steps(
    transition_type: str,
    is_recovery: bool,
    next_task_title: Optional[str],
    max_steps: int,
) -> List[str]:
    tmpl = _TEMPLATES.get(transition_type, _TEMPLATES["custom"])
    key = "steps_recovery" if is_recovery else "steps_normal"
    steps = list(tmpl[key])

    if next_task_title:
        steps = [s.replace("[topic]", next_task_title) for s in steps]

    return steps[:max_steps]


async def generate_transition_script(
    db: Connection,
    user_id: str,
    request: TransitionScriptGenerateRequest,
) -> TransitionScriptGenerateResponse:
    
    is_recovery = request.current_energy is not None and request.current_energy < 30
    max_steps = min(request.max_steps, 3) if is_recovery else request.max_steps
    tmpl = _TEMPLATES.get(request.transition_type, _TEMPLATES["custom"])

    user_prompt = ts_prompts.build_user_prompt(
        transition_type=request.transition_type,
        next_task_title=request.next_task_title,
        current_energy=request.current_energy,
        context_note=request.context_note,
        sensory_state=request.sensory_state,
        max_steps=max_steps,
    )

    llm_client = None
    source = "llm"
    steps = []

    try:
        llm_client = get_llm_client()
        rate_result = check_rate_limit(db, user_id)
        if not rate_result["allowed"]:
            logger.warning("Rate limit exceeded for user %s: %s", user_id, rate_result["reason"])
            log_rate_limit_skip(db, user_id, "transition_script")
            raise Exception("Rate limit exceeded")
            
        raw = await llm_client.generate_json(
            system_prompt=ts_prompts.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema_name="transition_script",
        )
        
        llm_output = TransitionScriptLLMOutput(**raw)
        steps = llm_output.script_steps[:max_steps]
        
    except Exception as e:
        logger.warning(f"LLM failed for transition script — using fallback. Reason: {e}")
        source = "fallback"
        steps = _get_template_steps(
            transition_type=request.transition_type,
            is_recovery=is_recovery,
            next_task_title=request.next_task_title,
            max_steps=max_steps,
        )

    title = tmpl["title"] if request.transition_type != "custom" or not request.next_task_title else request.next_task_title
    message = tmpl["message"]

    sq.save_transition_script(
        conn=db,
        user_id=user_id,
        transition_type=request.transition_type,
        title=title,
        steps=steps,
        source=source
    )
    
    script_id = str(uuid.uuid4())

    return TransitionScriptGenerateResponse(
        id=script_id,
        transition_type=request.transition_type,
        title=title,
        script_steps=steps,
        source=source,
        message=message,
    )
