from typing import List, Optional
from pydantic import BaseModel

class StuckTask(BaseModel):
    task_id: str
    title: str
    days_stuck: int
    reason: str

class TaskPatternAnalysis(BaseModel):
    stuck_tasks: List[StuckTask]
    identified_patterns: List[str]
    suggested_actions: List[str]

class TaskAggregatorResponse(BaseModel):
    analysis: TaskPatternAnalysis
    total_open_tasks: int
    total_stuck_tasks: int
