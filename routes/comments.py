from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List
from db.db import get_connection
from datetime import datetime
import json

router = APIRouter()

class ReplyResponse(BaseModel):
    tweet_id: str
    tweet_text: str
    replies: List[dict]
    risk_score: int
    risk_factors: List[str]
    explanation: str

@router.get("/replies/{account_username}")
async def get_replies(
    account_username: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    """
    Get replies for a specific account username and date.
    The date should be in YYYY-MM-DD format.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Parse the date to ensure it's valid
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Please use YYYY-MM-DD"
                )
            
            # Query to get comments for the specific date and account
            query = """
                SELECT content
                FROM comments
                WHERE account_username = %s
                AND DATE(created_at) = %s
            """
            
            cursor.execute(query, (account_username, target_date))
            result = cursor.fetchone()
            
            if not result:
                return {
                    "account_username": account_username,
                    "date": date,
                    "replies": []
                }
            
            # Parse the JSON content
            try:
                content_data = json.loads(result[0])
                return {
                    "account_username": account_username,
                    "date": date,
                    "replies": content_data
                }
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=500,
                    detail="Error parsing comment content"
                )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close() 