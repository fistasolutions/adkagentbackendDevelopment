from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DraftTweetGenerationRequest(BaseModel):
    previous_tweet: str
    num_drafts: int
    prompt: Optional[str] = None

class EventTweetGenerationRequest(BaseModel):
    num_drafts: int
    prompt: str
    date: Optional[str] = None

class PostInsertRequest(BaseModel):
    content: str
    user_id: Optional[int] = None
    account_id: Optional[int] = None
    mode: Optional[str] = None
    status: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    posted_time: Optional[datetime] = None
    posted_id: Optional[str] = None
    media_id: Optional[str] = None
    image_url: Optional[str] = None
    risk_score: Optional[float] = None
    manual_time: Optional[datetime] = None

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