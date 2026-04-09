from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import List

class IncidentEvent(BaseModel):
    regional_time: datetime
    industry: str
    region: str
    hosts_count: int = Field(ge=0)
    threat_code: int = Field(ge=1)
    success: int = Field(ge=0, le=1)

    @validator('regional_time')
    def validate_regional_time(cls, v):
        if v > datetime.utcnow():
            raise ValueError('regional_time cannot be in the future')
        return v

class IncidentBatch(BaseModel):
    events: List[IncidentEvent]
