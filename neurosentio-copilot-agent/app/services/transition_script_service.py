"""
Transition Script Service (Day 6).

Generates neurodivergent-friendly transition scripts using
mock LLM (default) with fallback to rule-based templates.

All generated language must be gentle, direct, and low-friction.
"""

import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app.repositories.transition_script_repository import transition_script_repository
from app.schemas.transition_script_schema import (
    TransitionScript as TransitionScriptSchema,
    TransitionScriptCreate,
    TransitionScriptGenerateRequest,
    TransitionScriptGenerateResponse,
)

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
            "Note one thing you completed today, however small.",
            "Shut the computer or put work items away.",
            "You are done for today.",
        ],
        "steps_recovery": [
            "Write tomorrow's first step in one sentence.",
            "Close everything. You are done.",
        ],
        "message": "Today is complete. Tomorrow has one starting point.",
    },
    "context_switch": {
        "title": "Switching context",
        "steps_normal": [
            "Write: 'I was here. Next step is...' on a note.",
            "Save and close current work.",
            "Take a 2-minute pause before opening the next task.",
            "Open only the next task — nothing else.",
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

    # Inject task title into starting_work / making_call where relevant
    if next_task_title:
        steps = [s.replace("[topic]", next_task_title) for s in steps]

    return steps[:max_steps]


# ──────────────────────────────────────────────────────────────────────
# Public service function
# ──────────────────────────────────────────────────────────────────────

def generate_transition_script(
    db: Session,
    user_id: str,
    request: TransitionScriptGenerateRequest,
) -> TransitionScriptGenerateResponse:
    """
    Generates a transition script and persists it.

    Currently rule-based (mock).
    LLM integration is a Day 7 upgrade.
    """
    is_recovery = (
        request.current_energy is not None and request.current_energy < 30
    )
    max_steps = min(request.max_steps, 3) if is_recovery else request.max_steps

    steps = _get_template_steps(
        transition_type=request.transition_type,
        is_recovery=is_recovery,
        next_task_title=request.next_task_title,
        max_steps=max_steps,
    )

    tmpl = _TEMPLATES.get(request.transition_type, _TEMPLATES["custom"])
    title = tmpl["title"]
    message = tmpl["message"]

    # Build context note
    context_parts = []
    if request.next_task_title:
        context_parts.append(f"Task: {request.next_task_title}")
    if request.context_note:
        context_parts.append(request.context_note)
    context = " | ".join(context_parts) if context_parts else None

    # Persist
    row = transition_script_repository.create(
        db,
        user_id,
        TransitionScriptCreate(
            transition_type=request.transition_type,
            title=title,
            script_steps=steps,
            context=context,
            tone="gentle",
            source="mock",
        ),
    )

    return TransitionScriptGenerateResponse(
        id=row.id,
        transition_type=row.transition_type,
        title=row.title,
        script_steps=row.script_steps,
        source=row.source,
        message=message,
    )
