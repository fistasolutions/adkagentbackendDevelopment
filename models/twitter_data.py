from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TwitterData(BaseModel):
    post_data_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    data_json: str
    user_id: int

    class Config:
        from_attributes = True 