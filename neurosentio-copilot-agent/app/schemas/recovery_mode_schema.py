from pydantic import BaseModel
from typing import List

class RecoveryModeResponse(BaseModel):
    success: bool
    message: str
    snoozed_count: int
    recovery_tasks_added: List[str]
