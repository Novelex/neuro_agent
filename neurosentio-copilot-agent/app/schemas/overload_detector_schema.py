from pydantic import BaseModel

class OverloadDetectorResponse(BaseModel):
    overload_detected: bool
    message: str
    current_mode: str
