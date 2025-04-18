from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    fullname: str
    email: EmailStr
    password: str
    enterprise_id: Optional[str] = None
    rememberMe: Optional[bool] = False

class UserResponse(BaseModel):
    user_id: int
    fullname: str
    email: EmailStr
    enterprise_id: Optional[str] = None

    class Config:
        from_attributes = True

class Tweet(BaseModel):
    tweet_id: str
    text: str
    author_id: str
    created_at: datetime
    retweet_count: int
    like_count: int
    reply_count: int
    quote_count: int
    lang: Optional[str] = None
    source: Optional[str] = None
    media_urls: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    mentions: Optional[List[str]] = None

class TweetResponse(BaseModel):
    tweets: List[Tweet]
    next_token: Optional[str] = None

    class Config:
        from_attributes = True 