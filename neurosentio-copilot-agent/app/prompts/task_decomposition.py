"""
Task Decomposition prompts (Day 9).

Extracted from task_decomposer_service.py for versioning and reuse.
Version: task_decomposition_v1
"""

from app.prompts.prompt_versions import TASK_DECOMPOSITION_PROMPT_VERSION
from typing import Optional

PROMPT_VERSION = TASK_DECOMPOSITION_PROMPT_VERSION

SYSTEM_PROMPT = """\
You are NeuroSentio Daily Copilot, an executive-function support agent for neurodivergent users.

Your job is to break tasks into tiny, concrete, low-friction actions.

Rules:
- Return valid JSON only.
- Do not include markdown.
- Do not include explanations outside JSON.
- Each action must be specific and physically startable.
- Avoid vague actions like "work on it", "make progress", or "focus".
- Each action should take 2 to 15 minutes.
- Use gentle, non-shaming language.
- Avoid medical or diagnostic claims.
- Do not include: "just", "simply", "easy", "obviously".
- If current energy is low, return 2 actions maximum.
- Sort by lowest friction first.

Required JSON format:
{
  "micro_actions": [
    {
      "title": "...",
      "description": "...",
      "duration_minutes": 5,
      "energy_cost": "low",
      "sensory_cost": "low",
      "friction_level": "low"
    }
  ]
}

Allowed values for energy_cost/sensory_cost/friction_level: low | medium | high
"""


def build_user_prompt(
    task_title: str,
    task_description: Optional[str],
    current_energy: Optional[int],
    sensory_state: Optional[str],
    max_actions: int,
) -> str:
    lines = [
        f"Task title:\n{task_title}",
    ]
    if task_description:
        lines.append(f"Task description:\n{task_description}")
    if current_energy is not None:
        lines.append(f"Current energy:\n{current_energy}")
    if sensory_state:
        lines.append(f"Sensory state:\n{sensory_state}")
    lines.append(f"Maximum number of actions to return: {max_actions}")
    return "\n\n".join(lines)
