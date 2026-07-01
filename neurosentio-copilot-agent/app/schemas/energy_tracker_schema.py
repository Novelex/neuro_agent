from pydantic import BaseModel
from typing import List

class EnergyTrendResponse(BaseModel):
    current_level: int
    trend: str
    suggestions: List[str]
