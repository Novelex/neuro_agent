"""
Mock LLM client.

Returns deterministic fake decompositions — no API key required.
Used by default in local development and all tests.

The output is intentionally varied slightly by task title so different tasks
produce different but stable results.
"""

from app.llm.base import BaseLLMClient

# Neurodivergent-friendly micro-action templates
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


class MockLLMClient(BaseLLMClient):
    """
    Deterministic mock — returns pre-written micro-action templates.
    Stable across test runs. No network calls. No API keys.
    """

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str = "",
    ) -> dict:
        # Detect recovery signal from the user prompt
        is_recovery = False
        lines = user_prompt.splitlines()
        for i, line in enumerate(lines):
            if "current energy:" in line.lower():
                # The energy value is on the next non-empty line
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
