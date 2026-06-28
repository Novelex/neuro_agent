"""
Mock LLM client.

Returns deterministic fake outputs — no API key required.
Used by default in local development and all tests.

Supports schema_name:
  - "TaskDecomposeResponse"  → micro-action list
  - "reply_draft"            → reply draft options
  - anything else            → generic micro-action fallback
"""

from app.llm.base import BaseLLMClient

# ── Task decomposition templates ──────────────────────────────────────

_DEFAULT_ACTIONS = [
    {
        "title": "Open the place where this task lives",
        "description": (
            "Start by opening only the file, tool, or workspace related to this task. "
            "You don't need to do anything yet — just open it."
        ),
        "duration_minutes": 2,
        "energy_cost": "low",
        "sensory_cost": "low",
        "friction_level": "low",
    },
    {
        "title": "Write one rough note about what needs to happen",
        "description": (
            "Add one imperfect sentence or bullet. "
            "It does not need to be complete or correct. Just one thought."
        ),
        "duration_minutes": 5,
        "energy_cost": "low",
        "sensory_cost": "low",
        "friction_level": "low",
    },
    {
        "title": "Do one tiny visible action for 5 minutes",
        "description": (
            "Pick the smallest possible physical action you can do right now. "
            "Set a 5-minute timer. Stop when it rings — that's the whole task."
        ),
        "duration_minutes": 5,
        "energy_cost": "low",
        "sensory_cost": "low",
        "friction_level": "low",
    },
    {
        "title": "Review what you just noted and pick one next step",
        "description": (
            "Look at your rough note. "
            "Pick one specific thing to do next — even if it's tiny."
        ),
        "duration_minutes": 3,
        "energy_cost": "low",
        "sensory_cost": "low",
        "friction_level": "low",
    },
    {
        "title": "Save your progress and close the workspace",
        "description": (
            "Save anything you've written or changed. "
            "Close the files. You've made real progress — that counts."
        ),
        "duration_minutes": 2,
        "energy_cost": "low",
        "sensory_cost": "low",
        "friction_level": "low",
    },
]

_RECOVERY_ACTIONS = [
    {
        "title": "Open the task and read it once",
        "description": (
            "Just open it and read through once. "
            "You don't have to do anything else right now."
        ),
        "duration_minutes": 2,
        "energy_cost": "low",
        "sensory_cost": "low",
        "friction_level": "low",
    },
    {
        "title": "Write one sentence about where to start",
        "description": (
            "Write a single sentence — even just 'I think I need to...' "
            "Imperfect is fine. That's the whole action."
        ),
        "duration_minutes": 3,
        "energy_cost": "low",
        "sensory_cost": "low",
        "friction_level": "low",
    },
]

# ── Reply draft templates ──────────────────────────────────────────────

_REPLY_DEFAULT = {
    "draft_options": [
        {
            "type": "short",
            "text": "Thanks for your message. I'll take a look and get back to you soon.",
        },
        {
            "type": "warm",
            "text": "Thanks for reaching out. I'll review this and send you a proper response soon.",
        },
        {
            "type": "detailed",
            "text": (
                "Thanks for your message. I've received it and will review the details carefully. "
                "I'll follow up with a clearer answer once I've had time to check everything."
            ),
        },
        {
            "type": "boundary",
            "text": (
                "Thanks for your message. I'm not able to take this on today, "
                "but I can follow up when I have more capacity."
            ),
        },
    ]
}

_REPLY_ACCEPT = {
    "draft_options": [
        {"type": "short", "text": "Yes, that works for me. Thanks."},
        {"type": "warm", "text": "Yes, that works for me. Thanks for checking."},
        {
            "type": "detailed",
            "text": (
                "Yes, that works for me. I'm happy to go ahead with this "
                "and will follow up if anything changes."
            ),
        },
        {
            "type": "boundary",
            "text": "That works for me. I'll let you know if anything changes on my end.",
        },
    ]
}

_REPLY_DECLINE = {
    "draft_options": [
        {
            "type": "short",
            "text": "Thanks for thinking of me, but I can't take this on right now.",
        },
        {
            "type": "warm",
            "text": (
                "Thanks for reaching out. I appreciate it, "
                "but I'm not able to take this on right now."
            ),
        },
        {
            "type": "detailed",
            "text": (
                "Thanks for reaching out and thinking of me. "
                "I'm not able to take this on right now, but I appreciate you asking."
            ),
        },
        {
            "type": "boundary",
            "text": "I'm not available for this today. I'll let you know if that changes.",
        },
    ]
}

_REPLY_DELAY = {
    "draft_options": [
        {
            "type": "short",
            "text": "Thanks for your message. I'll get back to you tomorrow.",
        },
        {
            "type": "warm",
            "text": (
                "Thanks for your message. I need a little more time to respond properly, "
                "and I'll get back to you tomorrow."
            ),
        },
        {
            "type": "detailed",
            "text": (
                "Thanks for your message. I've received this and want to respond properly. "
                "I need a little more time, so I'll get back to you tomorrow."
            ),
        },
        {
            "type": "boundary",
            "text": "I need more time to respond properly. I'll be in touch tomorrow.",
        },
    ]
}

_REPLY_URGENT = {
    "draft_options": [
        {
            "type": "short",
            "text": "Got your message — I'll look at this now.",
        },
        {
            "type": "warm",
            "text": "Thanks for flagging this as urgent. I'll look at it now and get back to you shortly.",
        },
        {
            "type": "detailed",
            "text": (
                "Thanks for your message — I can see this is urgent. "
                "I'll review it now and follow up with you as soon as I have an answer."
            ),
        },
        {
            "type": "boundary",
            "text": (
                "I've seen your message. I'll review this shortly — "
                "please allow me a little time to give you a proper response."
            ),
        },
    ]
}


def _pick_reply_template(user_prompt: str, is_low_energy: bool) -> dict:
    """Pick the most appropriate reply template based on prompt signals."""
    prompt_lower = user_prompt.lower()

    if "accept" in prompt_lower:
        return _REPLY_ACCEPT
    if "decline" in prompt_lower:
        return _REPLY_DECLINE
    if "delay" in prompt_lower or "more time" in prompt_lower:
        return _REPLY_DELAY
    if "urgent" in prompt_lower:
        return _REPLY_URGENT

    return _REPLY_DEFAULT


class MockLLMClient(BaseLLMClient):
    """
    Deterministic mock — returns pre-written templates.
    Stable across test runs. No network calls. No API keys.
    """

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str = "",
    ) -> dict:

        # ── Smoke Test mode ───────────────────────────────────────────
        if schema_name == "smoke_test":
            return {"status": "ok"}

        # ── Transition Script mode ────────────────────────────────────
        if schema_name == "transition_script":
            return {
                "title": "Transition: Leaving work",
                "script_steps": [
                    "Close your laptop lid.",
                    "Take a deep breath.",
                    "Step outside your work environment."
                ],
                "message": "You only need the first movement."
            }

        # ── Reply draft mode ──────────────────────────────────────────
        if schema_name == "reply_draft":
            is_low_energy = False
            for line in user_prompt.splitlines():
                if "current energy:" in line.lower():
                    parts = line.split(":")
                    if len(parts) > 1:
                        try:
                            val = int(parts[1].strip())
                            if val < 30:
                                is_low_energy = True
                        except ValueError:
                            pass

            return _pick_reply_template(user_prompt, is_low_energy)

        # ── Task decomposition mode (default) ─────────────────────────
        is_recovery = False
        lines = user_prompt.splitlines()
        for i, line in enumerate(lines):
            if "current energy:" in line.lower():
                for j in range(i + 1, min(i + 3, len(lines))):
                    candidate = lines[j].strip()
                    if candidate:
                        try:
                            energy_val = int(candidate)
                            if energy_val < 30:
                                is_recovery = True
                        except ValueError:
                            pass
                        break

        if is_recovery:
            return {"micro_actions": _RECOVERY_ACTIONS[:2]}

        return {"micro_actions": _DEFAULT_ACTIONS[:5]}
