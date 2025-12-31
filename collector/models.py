from datetime import datetime, timezone
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Run(BaseModel):
    id: int
    analysis_id: int
    owner_id: int
    status: str = "PENDING"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    jobs: List[Job] = []
