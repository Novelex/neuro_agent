"""
Rule-based planning service.

Selects tasks and generates a gentle, neurodivergent-friendly plan summary.
No LLM — all rule-based logic for Day 1/2.
"""

from typing import List, Optional
from datetime import date

from app.models.task import Task as TaskModel
from app.models.energy_log import EnergyLog as EnergyLogModel
from app.schemas.copilot_schema import NextAction, Recovery

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _sort_tasks(tasks: List[TaskModel]) -> List[TaskModel]:
    """
    Sort tasks by:
    1. Priority (high → medium → low)
    2. Due date (earliest first, None last)
    3. Created at (oldest first)
    """
    def sort_key(t: TaskModel):
        priority_rank = PRIORITY_ORDER.get(t.priority, 99)
        due = t.due_date or date(9999, 12, 31)
        return (priority_rank, due, t.created_at)

    return sorted(tasks, key=sort_key)


def select_tasks(
    open_tasks: List[TaskModel],
    mode: str,
    max_tasks: int = 3,
) -> List[TaskModel]:
    """
    Return top tasks based on mode.
    - recovery → max 1 task
    - normal   → max 3 tasks (or override)
    """
    limit = 1 if mode == "recovery" else max_tasks
    sorted_tasks = _sort_tasks(open_tasks)
    return sorted_tasks[:limit]


def build_suggested_next_action(
    selected_tasks: List[TaskModel],
    mode: str,
) -> NextAction:
    if not selected_tasks:
        return NextAction(
            type="no_tasks",
            message="No open tasks right now. Take a breath — you're caught up! 🌿",
        )

    top_task = selected_tasks[0]

    if mode == "recovery":
        return NextAction(
            type="recovery_task",
            message=f"Let's make this easier to start. One small step: '{top_task.title}'.",
            task_id=top_task.id,
            task_title=top_task.title,
        )

    return NextAction(
        type="suggested_task",
        message=f"Pick one small step: start with '{top_task.title}'.",
        task_id=top_task.id,
        task_title=top_task.title,
    )


def build_recovery_recommendation(
    mode: str,
    latest_energy: Optional[EnergyLogModel],
    reasons: List[str],
) -> Optional[Recovery]:
    if mode != "recovery":
        return None

    suggestions = [
        "Reduce today's plan to one task.",
        "Take a sensory break before starting.",
        "Drink some water and step away from screens for 5 minutes.",
    ]

    if latest_energy and latest_energy.sensory_state in ("overstimulated", "shutdown"):
        suggestions.insert(0, "Your sensory state suggests you need a quieter environment first.")

    return Recovery(
        message="Today may need a lighter plan. That's okay — your plan can be reduced.",
        suggestions=suggestions,
    )


def build_plan_summary(
    mode: str,
    open_tasks_count: int,
    selected_tasks: List[TaskModel],
    latest_energy: Optional[EnergyLogModel],
    reasons: List[str],
) -> str:
    if latest_energy is None:
        return (
            "We don't have an energy reading yet. "
            "Log how you're feeling to get a more personalised plan."
        )

    battery = latest_energy.battery_level

    if mode == "recovery":
        return (
            f"Your energy is at {battery}/100 and your load looks heavy. "
            "Today's plan has been reduced to one task. "
            "Your plan can be reduced — that's not failure, it's smart pacing."
        )

    if open_tasks_count > 5 and battery < 50:
        return (
            f"You have {open_tasks_count} open tasks and {battery}/100 energy. "
            "Let's make this easier to start — here are your top picks for today."
        )

    return (
        f"You're at {battery}/100 energy. "
        f"Here are your top {len(selected_tasks)} task(s) to focus on today. "
        "Pick one small step and go from there."
    )
