"""Energy Pattern Analyzer Service."""

from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.repositories.energy_repository import energy_repository


def get_energy_patterns(db: Session, user_id: str, days: int = 14) -> dict:
    """
    Fetch recent energy logs, aggregate battery levels by hour, and compute patterns.
    """
    logs = energy_repository.list_recent(db, user_id, days)
    total_logs = len(logs)

    # Determine confidence tier
    if total_logs < 5:
        confidence_tier = "low"
    elif total_logs <= 15:
        confidence_tier = "medium"
    else:
        confidence_tier = "high"

    # Group by hour
    hour_sums: Dict[int, float] = {}
    hour_counts: Dict[int, int] = {}

    for log in logs:
        # We use the hour of the logged_at datetime
        h = log.logged_at.hour
        hour_sums[h] = hour_sums.get(h, 0.0) + log.battery_level
        hour_counts[h] = hour_counts.get(h, 0) + 1

    # Calculate hourly averages
    hourly_averages: Dict[str, float] = {}
    high_energy_hours: List[int] = []
    low_energy_hours: List[int] = []

    # Keep a dict of int hours to averages for window calculation
    int_hourly_averages: Dict[int, float] = {}

    for h in range(24):
        if h in hour_counts:
            avg = round(hour_sums[h] / hour_counts[h], 1)
            hourly_averages[str(h)] = avg
            int_hourly_averages[h] = avg
            if avg >= 65:
                high_energy_hours.append(h)
            if avg <= 35:
                low_energy_hours.append(h)
        else:
            int_hourly_averages[h] = 50.0  # Neutral baseline for window calculations

    # Calculate best_focus_window (best consecutive 3-hour window)
    best_focus_window: Optional[str] = None
    if total_logs > 0:
        best_avg = -1.0
        best_start = 9  # default starting hour
        
        # Scan starting hours from 0 to 23
        for h in range(24):
            # Check a 3-hour block starting at h
            avg_window = (
                int_hourly_averages[h] + 
                int_hourly_averages[(h + 1) % 24] + 
                int_hourly_averages[(h + 2) % 24]
            ) / 3.0
            
            if avg_window > best_avg:
                best_avg = avg_window
                best_start = h

        best_focus_window = f"{best_start:02d}:00 - {(best_start + 3) % 24:02d}:00"

    return {
        "high_energy_hours": sorted(high_energy_hours),
        "low_energy_hours": sorted(low_energy_hours),
        "best_focus_window": best_focus_window,
        "confidence_tier": confidence_tier,
        "hourly_averages": hourly_averages,
    }
