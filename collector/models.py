from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class Job(BaseModel):
    id: int
    run_id: int
    input_channel: str
    youtube_channel_id: Optional[str] = None
    status: str = "PENDING"
    attempts: int = 0
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Run(BaseModel):
    id: int
    analysis_id: int
    owner_id: int
    status: str = "PENDING"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    jobs: List[Job] = []
