from pydantic import BaseModel, EmailStr
from typing import Optional

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
    role: Optional[str] = None

    class Config:
        from_attributes = True 