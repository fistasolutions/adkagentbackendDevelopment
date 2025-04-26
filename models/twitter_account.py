from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    user_id: str
    username: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    account_id: Optional[str] = None

class UserResponse(BaseModel):
    user_id: str
    username: str
    account_id: str
    created_at: datetime
    updated_at: datetime
