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

    mode = "recovery" if risk_score >= HIGH_RISK_THRESHOLD else "normal"

    return {
        "risk_score": risk_score,
        "mode": mode,
        "reasons": reasons,
    }
