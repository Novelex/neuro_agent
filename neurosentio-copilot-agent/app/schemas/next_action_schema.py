from pydantic import BaseModel
from typing import Optional

class MicroActionResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    duration_minutes: int
    energy_cost: str
    status: str
    sort_order: int
    task_id: Optional[str]

class NextActionResponse(BaseModel):
    has_action: bool
    action: Optional[MicroActionResponse]
    message: str
