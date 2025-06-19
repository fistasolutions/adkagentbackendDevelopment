from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.db import get_connection
import requests
from requests_oauthlib import OAuth1
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timezone
from routes.post_on_twitter import get_twitter_credentials

load_dotenv()
router = APIRouter()

class PostReplyRequest(BaseModel):
    user_id: str
    account_id: str

def get_twitter_auth(credentials):
    return OAuth1(
        credentials["api_key"],
        credentials["api_secret"],
        credentials["access_token"],
        credentials["access_token_secret"]
    )

def post_tweet_reply(tweet_id: str, reply_text: str, auth: OAuth1) -> dict:
    url = f"https://api.twitter.com/2/tweets"
    payload = {
        "text": reply_text,
        "reply": {
            "in_reply_to_tweet_id": tweet_id
        }
    }
    
    response = requests.post(url, auth=auth, json=payload)
    
    if response.status_code == 201:
        return response.json()
    elif response.status_code == 429:  # Rate limit exceeded
        raise HTTPException(
            status_code=429,
            detail="Twitter rate limit exceeded. Please try again later."
        )
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to post reply: {response.text}"
        )

@router.post("/post-comment-replies")
async def post_replies():
    """
    Post replies to tweets from the comments_reply table.
    This endpoint will process all unposted replies for the given user and account.
    """
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Get all unposted replies (include account_id in select)
                cursor.execute(
                    """
                    SELECT id, comment_id, reply_text, account_username 
                    FROM comments_reply 
                    WHERE post_status = 'unposted'
                    AND (schedule_time <= NOW())
                    ORDER BY COALESCE(schedule_time, created_at) ASC
                    """
                )
                unposted_replies = cursor.fetchall()
                print("unposted_replies", unposted_replies)
                if not unposted_replies:
                    return {
                        "status": "success",
                        "message": "No unposted replies found",
                        "posted_count": 0
                    }
                posted_count = 0
                failed_replies = []
                for reply in unposted_replies:
                    reply_id, tweet_id, reply_text, account_id = reply
                    try:
                        # Fetch credentials for this account
                        credentials = get_twitter_credentials(account_id)
                        auth = get_twitter_auth(credentials)
                        # Post the reply
                        response = post_tweet_reply(tweet_id, reply_text, auth)
                        reply_tweet_id = response["data"]["id"]
                        # Update the status in database
                        cursor.execute(
                            """
                            UPDATE comments_reply 
                            SET post_status = 'posted',
                                posted_id = %s
                            WHERE id = %s
                            """,
                            (reply_tweet_id, reply_id)
                        )
                        posted_count += 1
                        # Add delay to respect rate limits
                        time.sleep(2)
                    except Exception as e:
                        failed_replies.append({
                            "reply_id": reply_id,
                            "error": str(e)
                        })
                conn.commit()
                return {
                    "status": "success",
                    "posted_count": posted_count,
                    "failed_replies": failed_replies,
                    "message": f"Successfully posted {posted_count} replies. {len(failed_replies)} replies failed."
                }
        except Exception as db_error:
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(db_error)}"
            )
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing replies: {str(e)}"
        ) 