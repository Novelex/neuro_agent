"""
Morning Plan prompts.

Used by morning_plan_service to generate a concrete, step-by-step day plan
from the user's tasks fetched from Supabase.

Version: morning_plan_v1
"""

from typing import List, Dict, Any

from app.prompts.prompt_versions import MORNING_PLAN_PROMPT_VERSION

PROMPT_VERSION = MORNING_PLAN_PROMPT_VERSION

SYSTEM_PROMPT = """\
You are a daily planning assistant.
Given a list of tasks for today, generate a concrete, step-by-step plan to complete them.

Rules:
- Output raw JSON only. No markdown, no explanation.
- For each task, generate 1-3 specific, actionable steps to complete it.
- Each step must describe a real physical action — not a vague goal.
- Include a realistic "duration_minutes" for each step (5 to 60 minutes).
- Include the exact "task_id" and "task_title" from the input for each step.
- Write a short "summary" (1-2 sentences) describing what the user will accomplish today.
- Write a short "message" (1 sentence, max 20 words) to help the user get started.
- Do NOT invent tasks not in the input list.

Format:
{
  "summary": "...",
  "message": "...",
  "steps": [
    {
      "task_id": "exact task ID from input",
      "task_title": "exact task title from input",
      "title": "Short step title",
      "description": "What exactly to do in this step",
      "duration_minutes": 20
    }
  ]
}
"""


def build_user_prompt(open_tasks: List[Dict[str, Any]]) -> str:
    """
    Build the prompt sent to the LLM.
    Includes all tasks fetched from Supabase (planner_tasks).
    """
    if not open_tasks:
        return (
            "No tasks are scheduled for today.\n"
            "Generate a short summary saying there is nothing to do "
            "and return an empty steps list."
        )

    tasks_str = "\n".join(
        f"- ID: {t['id']} | Title: {t.get('title', 'Untitled')}"
        + (f" | Notes: {t.get('subtitle')}" if t.get("subtitle") else "")
        for t in open_tasks
    )

    return (
        f"Tasks for today:\n{tasks_str}\n\n"
        "Generate a step-by-step plan to complete all of these tasks today."
    )
