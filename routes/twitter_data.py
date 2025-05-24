from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.db import get_connection
from models.twitter_data import TwitterData
from datetime import datetime, timedelta
import json
from typing import List

router = APIRouter()



class TweetFetchRequest(BaseModel):
    user_id: int
    account_id: int


@router.post("/twitter-data/")
async def save_twitter_data(data: dict, user_id: int,username:str):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get current timestamp
            current_time = datetime.utcnow()
            
            # Calculate start of current week (Monday)
            start_of_week = current_time - timedelta(days=current_time.weekday())
            
            # Check and delete existing data from current week
            cursor.execute(
                """
                DELETE FROM post_data 
                WHERE user_id = %s AND username = %s
                AND update_at >= %s
                """,
                (user_id, username, start_of_week)
            )
            
            # Convert data to JSON string with proper formatting
            data_json = json.dumps(data, ensure_ascii=False, indent=2)
            
            # Insert new data into database
            cursor.execute(
                """
                INSERT INTO post_data (created_at, update_at, data_json, user_id,username)
                VALUES (%s, %s, %s, %s,%s)
                RETURNING post_data_id
                """,
                (current_time, current_time, data_json, user_id,username)
            )
            
            post_data_id = cursor.fetchone()[0]
            conn.commit()
            
            return {
                "post_data_id": post_data_id,
                "message": "Twitter data saved successfully"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()



@router.get("/twitter-data/{user_id}")
async def get_twitter_data(user_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT post_data_id, created_at, update_at, data_json, user_id
                FROM post_data
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            results = cursor.fetchall()
            if not results:
                return []
            return [
                {
                    "post_data_id": row[0],
                    "created_at": row[1],
                    "update_at": row[2],
                    "data_json": json.loads(row[3]),
                    "user_id": row[4]
                }
                for row in results
            ]
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close() 
        
@router.get("/generated-tweets/{user_id}/{account_id}")
async def get_generated_tweets(user_id: int, account_id: int    ):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, created_at, content, user_id, account_id, status,posted_id,scheduled_time,"Image_url"
                FROM posts
                WHERE user_id = %s AND account_id = %s
                ORDER BY created_at DESC
                """,
                (user_id, account_id)
            )
            results = cursor.fetchall()
            if not results:
                return []
            return [
                {
                    "post_id": row[0],
                    "created_at": row[1],
                    "content": row[2],
                    "user_id": row[3],
                    "account_id": row[4],
                    "status": row[5],
                    "posted_id": row[6],
                    "scheduled_time": row[7],
                    "Image_url": row[8]
                }
                for row in results
            ]
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close() 
        
        
class PostDeleteRequest(BaseModel):
    post_ids: List[int]

@router.delete("/delete-posts")
async def delete_posts(request: PostDeleteRequest):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Convert list of IDs to a tuple for SQL IN clause
            post_ids = tuple(request.post_ids)
            
            # Delete posts with the given IDs
            cursor.execute(
                """
                DELETE FROM posts 
                WHERE id IN %s
                RETURNING id
                """,
                (post_ids,)
            )
            
            deleted_ids = cursor.fetchall()
            conn.commit()
            
            if not deleted_ids:
                raise HTTPException(status_code=404, detail="No posts found with the provided IDs")
            
            return {
                "message": "Posts deleted successfully",
                "deleted_post_ids": [row[0] for row in deleted_ids]
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close() 
        
        
