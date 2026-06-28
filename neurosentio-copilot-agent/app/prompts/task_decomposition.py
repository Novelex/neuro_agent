"""
Task Decomposition prompts (Day 9).

Extracted from task_decomposer_service.py for versioning and reuse.
Version: task_decomposition_v1
"""

from app.prompts.prompt_versions import TASK_DECOMPOSITION_PROMPT_VERSION
from typing import Optional

PROMPT_VERSION = TASK_DECOMPOSITION_PROMPT_VERSION

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
