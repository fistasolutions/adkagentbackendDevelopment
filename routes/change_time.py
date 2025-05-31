from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from db.db import get_connection

router = APIRouter()

class TimeUpdateRequest(BaseModel):
    user_id: str
    account_id: str

@router.post("/update-comments-reply-time")
async def update_comments_reply_time(request: TimeUpdateRequest):
    """Update scheduled_time to recommended_time in comments_reply table."""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Update the scheduled_time to recommended_time
            cursor.execute("""
                UPDATE comments_reply 
                SET recommended_time = DATE(schedule_time),
                    schedule_time = NULL
                WHERE user_id = %s AND account_username = %s
                RETURNING id, schedule_time, recommended_time
            """, (request.user_id, request.account_id))
            
            updated_records = cursor.fetchall()
            conn.commit()
            
            return {
                "message": "Successfully updated comments_reply times",
                "updated_records": [
                    {
                        "id": record[0],
                        "schedule_time": record[1],
                        "recommended_time": record[2]
                    } for record in updated_records
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/update-posts-time")
async def update_posts_time(request: TimeUpdateRequest):
    """Update scheduled_time to recommended_time in posts table."""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Update the scheduled_time to recommended_time
            cursor.execute("""
                UPDATE posts 
                SET recommended_time = DATE(scheduled_time),
                    scheduled_time = NULL
                WHERE user_id = %s AND account_id = %s
                RETURNING id, scheduled_time, recommended_time
            """, (request.user_id, request.account_id))
            
            updated_records = cursor.fetchall()
            conn.commit()
            
            return {
                "message": "Successfully updated posts times",
                "updated_records": [
                    {
                        "id": record[0],
                        "scheduled_time": record[1],
                        "recommended_time": record[2]
                    } for record in updated_records
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/update-post-reply-time")
async def update_post_reply_time(request: TimeUpdateRequest):
    """Update scheduled_time to recommended_time in post_reply table."""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Update the scheduled_time to recommended_time
            cursor.execute("""
                UPDATE post_reply 
                SET recommended_time = DATE(schedule_time),
                    schedule_time = NULL
                WHERE user_id = %s AND account_id = %s
                RETURNING id, schedule_time, recommended_time
            """, (request.user_id, request.account_id))
            
            updated_records = cursor.fetchall()
            conn.commit()
            
            return {
                "message": "Successfully updated post_reply times",
                "updated_records": [
                    {
                        "id": record[0],
                        "recommended_time": record[2]
                    } for record in updated_records
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
