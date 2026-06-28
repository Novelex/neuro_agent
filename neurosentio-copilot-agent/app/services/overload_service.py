"""
Overload risk calculator.

Produces a numeric risk score and a mode (normal | recovery)
based on energy state, open task count, and sensory state.
No LLM — pure rule-based logic.
"""

from typing import Optional
from app.models.energy_log import EnergyLog as EnergyLogModel


HIGH_RISK_THRESHOLD = 60


def calculate_overload_risk(
    latest_energy: Optional[EnergyLogModel],
    open_tasks_count: int,
    high_priority_count: int,
    event_count: Optional[int] = None,
    back_to_back_count: Optional[int] = None,
    high_load_event_exists: Optional[bool] = None,
    total_meeting_minutes: Optional[int] = None,
) -> dict:
    """
    Returns:
        {
            "risk_score": int,
            "mode": "normal" | "recovery",
            "reasons": [str, ...],
        }
    """
    risk_score = 0
    reasons: list[str] = []

    # ── Energy score ──────────────────────────────────────────────────
    if latest_energy is None:
        # Unknown energy — treat conservatively but not recovery
        reasons.append("No energy log found — we can't measure your load right now.")
    else:
        battery = latest_energy.battery_level
        if battery < 30:
            risk_score += 50
            reasons.append(f"Energy is very low ({battery}/100).")
        elif battery < 50:
            risk_score += 25
            reasons.append(f"Energy is moderate ({battery}/100).")

        # ── Sensory score ─────────────────────────────────────────────
        sensory = latest_energy.sensory_state
        if sensory == "overstimulated":
            risk_score += 25
            reasons.append("Sensory state is overstimulated.")
        elif sensory == "shutdown":
            risk_score += 50
            reasons.append("Sensory state is shutdown — this needs a lighter plan.")

    # ── Task load score ───────────────────────────────────────────────
    if open_tasks_count > 5:
        risk_score += 15
        reasons.append(f"You have {open_tasks_count} open tasks — that's a full plate.")
    if high_priority_count > 2:
        risk_score += 15
        reasons.append(f"{high_priority_count} high-priority tasks are waiting.")

    # ── Calendar-aware scoring ────────────────────────────────────────
    # Only apply if at least one calendar parameter is provided (is not None)
    has_calendar = any(x is not None for x in [event_count, back_to_back_count, high_load_event_exists, total_meeting_minutes])
    
    if has_calendar:
        if event_count is not None and event_count >= 4:
            risk_score += 20
            reasons.append(f"You have {event_count} events scheduled today.")
        if back_to_back_count is not None and back_to_back_count >= 2:
            risk_score += 25
            reasons.append(f"You have {back_to_back_count} back-to-back events scheduled.")
        if high_load_event_exists is True:
            risk_score += 20
            reasons.append("High-load events exist today.")
        if total_meeting_minutes is not None and total_meeting_minutes > 240:
            risk_score += 20
            reasons.append(f"Over 4 hours of meetings scheduled ({total_meeting_minutes} minutes).")

    mode = "recovery" if risk_score >= HIGH_RISK_THRESHOLD else "normal"

    return {
        "risk_score": risk_score,
        "mode": mode,
        "reasons": reasons,
    }

