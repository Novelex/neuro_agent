"""CalendarEvent database repository."""

from datetime import datetime, date, time
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.calendar_event import CalendarEvent


class CalendarRepository:
    def upsert_events(self, db: Session, user_id: str, events_data: List[dict]) -> Tuple[int, int, List[CalendarEvent]]:
        """
        Upsert a list of calendar events.
        
        Rules:
        - If external_event_id exists, upsert by user_id + provider + external_event_id.
        - If external_event_id is null, always create a new event. Do not try to upsert null external IDs.
        """
        imported_count = 0
        updated_count = 0
        saved_events = []

        for data in events_data:
            ext_id = data.get("external_event_id")
            provider = data.get("provider", "manual")
            
            existing = None
            if ext_id is not None:
                existing = db.query(CalendarEvent).filter(
                    and_(
                        CalendarEvent.user_id == user_id,
                        CalendarEvent.provider == provider,
                        CalendarEvent.external_event_id == ext_id
                    )
                ).first()

            if existing:
                # Update existing event
                for key, val in data.items():
                    setattr(existing, key, val)
                existing.updated_at = datetime.now(existing.updated_at.tzinfo or None)
                updated_count += 1
                saved_events.append(existing)
            else:
                # Create a new event
                new_event = CalendarEvent(user_id=user_id, **data)
                db.add(new_event)
                imported_count += 1
                saved_events.append(new_event)

        db.commit()
        for ev in saved_events:
            db.refresh(ev)

        return imported_count, updated_count, saved_events

    def list_events(self, db: Session, user_id: str, start_time: datetime, end_time: datetime) -> List[CalendarEvent]:
        """List all events overlapping with start_time and end_time, ordered by start_time."""
        return db.query(CalendarEvent).filter(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.start_time <= end_time,
                CalendarEvent.end_time >= start_time
            )
        ).order_by(CalendarEvent.start_time.asc()).all()

    def get_event_by_id(self, db: Session, user_id: str, event_id: str) -> Optional[CalendarEvent]:
        """Fetch a specific event by ID, scoped to user."""
        return db.query(CalendarEvent).filter(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.id == event_id
            )
        ).first()

    def delete_event(self, db: Session, user_id: str, event_id: str) -> bool:
        """Delete an event by ID, scoped to user."""
        event = self.get_event_by_id(db, user_id, event_id)
        if event:
            db.delete(event)
            db.commit()
            return True
        return False

    def delete_events_for_range(self, db: Session, user_id: str, start_time: datetime, end_time: datetime) -> int:
        """Delete all events for a user within/overlapping a range."""
        events = self.list_events(db, user_id, start_time, end_time)
        count = len(events)
        for ev in events:
            db.delete(ev)
        db.commit()
        return count

    def list_events_for_day(self, db: Session, user_id: str, check_date: date) -> List[CalendarEvent]:
        """List all events overlapping the specified date (from 00:00:00 to 23:59:59)."""
        day_start = datetime.combine(check_date, time.min)
        day_end = datetime.combine(check_date, time.max)
        # Standard filter: event starts before the end of the day, and ends after the start of the day
        return db.query(CalendarEvent).filter(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.start_time <= day_end,
                CalendarEvent.end_time >= day_start
            )
        ).order_by(CalendarEvent.start_time.asc()).all()

    def count_events_for_day(self, db: Session, user_id: str, check_date: date) -> int:
        """Count all events overlapping the specified date."""
        day_start = datetime.combine(check_date, time.min)
        day_end = datetime.combine(check_date, time.max)
        return db.query(CalendarEvent).filter(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.start_time <= day_end,
                CalendarEvent.end_time >= day_start
            )
        ).count()

    def list_back_to_back_events(self, db: Session, user_id: str, check_date: date) -> List[CalendarEvent]:
        """List events on the specified date marked as back-to-back."""
        day_start = datetime.combine(check_date, time.min)
        day_end = datetime.combine(check_date, time.max)
        return db.query(CalendarEvent).filter(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.is_back_to_back == True,
                CalendarEvent.start_time <= day_end,
                CalendarEvent.end_time >= day_start
            )
        ).order_by(CalendarEvent.start_time.asc()).all()


calendar_repository = CalendarRepository()
