from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from db.db import get_connection

router = APIRouter()

class TimeUpdateRequest(BaseModel):
    user_id: str
    account_id: str
    type: bool

@router.post("/update-comments-reply-time")
async def update_comments_reply_time(request: TimeUpdateRequest):
    """Update times in comments_reply table based on type."""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            if request.type:
                # Set recommended_time into schedule_time, skip if schedule_time exists
                cursor.execute("""
                    UPDATE comments_reply 
                    SET schedule_time = recommended_time
                    WHERE user_id = %s AND account_username = %s
                    AND schedule_time IS NULL
                    RETURNING id, schedule_time, recommended_time
                """, (request.user_id, request.account_id))
            else:
                # Move schedule_time to recommended_time and set schedule_time to NULL
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
    """Update times in posts table based on type."""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            if request.type:
                # Set recommended_time into schedule_time, skip if schedule_time exists
                cursor.execute("""
                    UPDATE posts 
                    SET scheduled_time = recommended_time
                    WHERE user_id = %s AND account_id = %s
                    AND scheduled_time IS NULL
                    RETURNING id, scheduled_time, recommended_time
                """, (request.user_id, request.account_id))
            else:
                # Move schedule_time to recommended_time and set schedule_time to NULL
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
    """Update times in post_reply table based on type."""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            if request.type:
                # Set recommended_time into schedule_time, skip if schedule_time exists
                cursor.execute("""
                    UPDATE post_reply 
                    SET schedule_time = recommended_time
                    WHERE user_id = %s AND account_id = %s
                    AND schedule_time IS NULL
                    RETURNING id, schedule_time, recommended_time
                """, (request.user_id, request.account_id))
            else:
                # Move schedule_time to recommended_time and set schedule_time to NULL
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
                        "schedule_time": record[1],
                        "recommended_time": record[2]
                    } for record in updated_records
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
