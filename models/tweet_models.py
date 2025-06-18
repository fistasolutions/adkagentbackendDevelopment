from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
import re

class DraftTweetGenerationRequest(BaseModel):
    previous_tweet: str
    num_drafts: int
    prompt: Optional[str] = None
    user_id: int
    account_id: int

class EventTweetGenerationRequest(BaseModel):
    num_drafts: int
    prompt: str
    date: Optional[str] = None
    user_id: str
    account_id: str

class PostInsertRequest(BaseModel):
    content: str
    user_id: Optional[int] = None
    account_id: Optional[int] = None
    mode: Optional[str] = None
    status: Optional[str] = None
    scheduled_time: Optional[datetime] = Field(None, description="ISO format datetime string with timezone")
    posted_time: Optional[datetime] = Field(None, description="ISO format datetime string with timezone")
    posted_id: Optional[str] = None
    media_id: Optional[str] = None
    image_url: Optional[str] = None
    risk_score: Optional[float] = None
    manual_time: Optional[datetime] = Field(None, description="ISO format datetime string with timezone")
    recommended_time: Optional[datetime] = Field(None, description="ISO format datetime string with timezone")

    @validator('scheduled_time', 'posted_time', 'manual_time', 'recommended_time', pre=True)
    def parse_datetime(cls, value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        # Handle format like "2025-06-25 11:16:00+00"
        if isinstance(value, str):
            # Convert space to T and add :00 to timezone if needed
            value = re.sub(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})(\+\d{2})', r'\1T\2\3:00', value)
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValueError(f"Invalid datetime format: {value}")
        return value

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "content": "Example tweet content",
                "scheduled_time": "2025-06-25T11:16:00+00:00",
                "recommended_time": "2025-06-25T11:16:00+00:00"
            }
        }

class EventInsertRequest(BaseModel):
    event_title: str
    event_details: Optional[str] = None
    event_datetime: datetime
    user_id: Optional[int] = None
    account_id: int
    status: Optional[str] = "active"

class EventAndPostResponse(BaseModel):
    event: dict
    post: dict 