"""Calendar Event Analysis Service."""

from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Tuple

from app.schemas.calendar_schema import FreeBlock, CalendarDaySummary


def detect_meeting_type(event: Any) -> str:
    """
    Detect the meeting type based on title, attendee count, and is_busy.
    
    Allowed meeting_types:
    - solo_block
    - one_to_one
    - group_meeting
    - presentation
    - interview
    - travel
    - personal
    - recovery
    - unknown
    """
    title = (getattr(event, "title", "") or "").lower()
    attendee_count = getattr(event, "attendee_count", 0) or 0
    is_busy = getattr(event, "is_busy", True)

    if "interview" in title:
        return "interview"
    if any(kw in title for kw in ["presentation", "pitch", "demo", "review"]):
        return "presentation"
    if any(kw in title for kw in ["travel", "commute", "drive"]):
        return "travel"
    if any(kw in title for kw in ["break", "rest", "recovery"]):
        return "recovery"
    
    if attendee_count == 0 and is_busy:
        return "solo_block"
    if attendee_count == 1:
        return "one_to_one"
    if attendee_count >= 2:
        return "group_meeting"
        
    return "unknown"


def calculate_load_score(event: Any) -> int:
    """
    Calculate the calendar load score from 0 to 100.
    
    Base scores:
    - recovery: 0
    - solo_block: 10
    - personal: 15
    - one_to_one: 30
    - travel: 40
    - group_meeting: 50
    - presentation: 75
    - interview: 80
    - unknown: 20

    Modifiers:
    - duration > 60 minutes: +10
    - attendee_count >= 5: +10
    - attendee_count >= 10: +20
    - title contains "urgent" or "deadline": +10

    Cap score at 100.
    """
    meeting_type = getattr(event, "meeting_type", "unknown") or "unknown"
    title = (getattr(event, "title", "") or "").lower()
    attendee_count = getattr(event, "attendee_count", 0) or 0

    base_scores = {
        "recovery": 0,
        "solo_block": 10,
        "personal": 15,
        "one_to_one": 30,
        "travel": 40,
        "group_meeting": 50,
        "presentation": 75,
        "interview": 80,
        "unknown": 20,
    }

    score = base_scores.get(meeting_type, 20)

    # Modifiers
    start_time = getattr(event, "start_time")
    end_time = getattr(event, "end_time")
    if start_time and end_time:
        duration = (end_time - start_time).total_seconds() / 60
        if duration > 60:
            score += 10

    if attendee_count >= 10:
        score += 20
    elif attendee_count >= 5:
        score += 10

    if "urgent" in title or "deadline" in title:
        score += 10

    return min(100, max(0, score))


def map_costs(load_score: int) -> Tuple[str, str]:
    """
    Map load score to energy_cost and sensory_cost.
    - 0–25: energy low, sensory low
    - 26–60: energy medium, sensory medium
    - 61–100: energy high, sensory high
    """
    if load_score <= 25:
        return "low", "low"
    elif load_score <= 60:
        return "medium", "medium"
    else:
        return "high", "high"


def mark_back_to_back(events: List[Any]) -> List[Any]:
    """
    Sort events by start_time.
    If gap between previous end_time and current start_time is <= 10 minutes:
      - mark current as back-to-back
      - mark previous as back-to-back
    """
    if not events:
        return events

    # Sort by start_time
    sorted_events = sorted(events, key=lambda e: e.start_time)
    
    # Initialize all is_back_to_back to False
    for ev in sorted_events:
        ev.is_back_to_back = False

    for i in range(len(sorted_events) - 1):
        curr_ev = sorted_events[i]
        next_ev = sorted_events[i + 1]
        
        # Check gap
        gap = (next_ev.start_time - curr_ev.end_time).total_seconds() / 60
        # If there's an overlap or gap is <= 10 mins
        if gap <= 10:
            curr_ev.is_back_to_back = True
            next_ev.is_back_to_back = True

    return sorted_events


def extract_free_blocks(
    events: List[Any],
    day_start: datetime,
    day_end: datetime,
    minimum_minutes: int = 15
) -> List[FreeBlock]:
    """
    Identify free time slots in standard day range.
    Only considers busy events.
    Merges overlapping busy events first, then finds gaps.
    """
    # 1. Filter only busy events
    busy_events = [e for e in events if getattr(e, "is_busy", True)]
    if not busy_events:
        duration = int((day_end - day_start).total_seconds() / 60)
        if duration >= minimum_minutes:
            return [FreeBlock(start_time=day_start, end_time=day_end, duration_minutes=duration)]
        return []

    # 2. Extract busy intervals and clamp to day start/end
    intervals: List[Tuple[datetime, datetime]] = []
    for ev in busy_events:
        # Clamp event times to the day boundaries
        s = max(ev.start_time, day_start)
        e = min(ev.end_time, day_end)
        if s < e:
            intervals.append((s, e))

    if not intervals:
        duration = int((day_end - day_start).total_seconds() / 60)
        if duration >= minimum_minutes:
            return [FreeBlock(start_time=day_start, end_time=day_end, duration_minutes=duration)]
        return []

    # 3. Merge overlapping intervals
    intervals.sort(key=lambda x: x[0])
    merged: List[Tuple[datetime, datetime]] = [intervals[0]]
    for current in intervals[1:]:
        prev_start, prev_end = merged[-1]
        curr_start, curr_end = current
        if curr_start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, curr_end))
        else:
            merged.append(current)

    # 4. Find gaps
    free_blocks: List[FreeBlock] = []
    
    # Gap before the first busy block
    first_start, _ = merged[0]
    if first_start > day_start:
        dur = int((first_start - day_start).total_seconds() / 60)
        if dur >= minimum_minutes:
            free_blocks.append(FreeBlock(start_time=day_start, end_time=first_start, duration_minutes=dur))

    # Gaps between busy blocks
    for i in range(len(merged) - 1):
        _, curr_end = merged[i]
        next_start, _ = merged[i + 1]
        if next_start > curr_end:
            dur = int((next_start - curr_end).total_seconds() / 60)
            if dur >= minimum_minutes:
                free_blocks.append(FreeBlock(start_time=curr_end, end_time=next_start, duration_minutes=dur))

    # Gap after the last busy block
    _, last_end = merged[-1]
    if last_end < day_end:
        dur = int((day_end - last_end).total_seconds() / 60)
        if dur >= minimum_minutes:
            free_blocks.append(FreeBlock(start_time=last_end, end_time=day_end, duration_minutes=dur))

    return free_blocks


def build_day_summary(events: List[Any], check_date: date) -> CalendarDaySummary:
    """
    Build CalendarDaySummary for a given date.
    Defines working day window as 09:00 to 17:00 for standard free block extraction.
    """
    day_start = datetime.combine(check_date, time(9, 0))
    day_end = datetime.combine(check_date, time(17, 0))

    event_count = len(events)
    high_load_event_count = sum(1 for e in events if getattr(e, "load_score", 0) >= 60)
    back_to_back_count = sum(1 for e in events if getattr(e, "is_back_to_back", False))

    total_busy_minutes = 0
    total_meeting_minutes = 0

    # Calculate meeting minutes
    for ev in events:
        start_time = getattr(ev, "start_time")
        end_time = getattr(ev, "end_time")
        if start_time and end_time:
            dur = (end_time - start_time).total_seconds() / 60
            if getattr(ev, "meeting_type", "unknown") not in ["solo_block", "recovery"]:
                total_meeting_minutes += dur

    # Calculate actual busy minutes using merged intervals clamped to working day
    busy_events = [e for e in events if getattr(e, "is_busy", True)]
    intervals = []
    for ev in busy_events:
        intervals.append((ev.start_time, ev.end_time))
    
    if intervals:
        intervals.sort(key=lambda x: x[0])
        merged = [intervals[0]]
        for current in intervals[1:]:
            prev_start, prev_end = merged[-1]
            curr_start, curr_end = current
            if curr_start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, curr_end))
            else:
                merged.append(current)
        total_busy_minutes = int(sum((e - s).total_seconds() / 60 for s, e in merged))

    # Free blocks
    free_blocks = extract_free_blocks(events, day_start, day_end)

    # Recommendation heuristic
    if back_to_back_count > 0:
        recommendation = "There are back-to-back events today. Add recovery space where possible."
    elif high_load_event_count > 0 or total_meeting_minutes > 120:
        recommendation = "Your calendar has several meetings. Keep the plan lighter."
    else:
        recommendation = "Your calendar looks light today. A normal plan should be okay."

    return CalendarDaySummary(
        date=check_date,
        event_count=event_count,
        high_load_event_count=high_load_event_count,
        back_to_back_count=back_to_back_count,
        total_busy_minutes=total_busy_minutes,
        total_meeting_minutes=int(total_meeting_minutes),
        free_blocks=free_blocks,
        recommendation=recommendation,
    )
