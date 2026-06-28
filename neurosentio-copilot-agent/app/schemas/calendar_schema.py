"""Calendar Pydantic schemas."""

from datetime import datetime, date
from typing import Optional, List, Any
from pydantic import BaseModel, Field, model_validator, ConfigDict


class CalendarEventCreate(BaseModel):
    external_event_id: Optional[str] = None
    provider: str = "manual"
    calendar_id: Optional[str] = None
    title: str = Field(..., min_length=1)
    start_time: datetime
    end_time: datetime
    timezone: Optional[str] = None
    location: Optional[str] = None
    attendee_count: int = Field(default=0, ge=0)
    is_busy: bool = True
    raw_metadata: Optional[dict] = None

    @model_validator(mode="after")
    def validate_times(self) -> "CalendarEventCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CalendarEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    provider: str
    external_event_id: Optional[str] = None
    calendar_id: Optional[str] = None
    title: str
    start_time: datetime
    end_time: datetime
    timezone: Optional[str] = None
    location: Optional[str] = None
    attendee_count: int
    meeting_type: str
    load_score: int
    energy_cost: str
    sensory_cost: str
    is_back_to_back: bool
    is_busy: bool
    raw_metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class CalendarImportRequest(BaseModel):
    events: List[CalendarEventCreate]


class CalendarImportResponse(BaseModel):
    imported_count: int
    updated_count: int
    events: List[CalendarEvent]


class FreeBlock(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_minutes: int


class CalendarDaySummary(BaseModel):
    date: date
    event_count: int
    high_load_event_count: int
    back_to_back_count: int
    total_busy_minutes: int
    total_meeting_minutes: int
    free_blocks: List[FreeBlock]
    recommendation: str
