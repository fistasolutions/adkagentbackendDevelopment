from fastapi import APIRouter, HTTPException
from db.db import get_connection
from pydantic import BaseModel
import requests
from requests_oauthlib import OAuth1
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta, timezone
load_dotenv()
router = APIRouter()
class PostTweetsRequest(BaseModel):
    user_id: int
    account_id: int
class ScheduledTweetRequest(BaseModel):
    user_id: int
    account_id: int
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
RATE_LIMIT_WINDOW = 15 * 60  
MAX_TWEETS_PER_WINDOW = 50  
RETRY_DELAY = 60  
MAX_RETRIES = 3
SCHEDULE_CHECK_INTERVAL = 5  
def get_twitter_auth():
    return OAuth1(
        TWITTER_API_KEY,
        TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN,
        TWITTER_ACCESS_TOKEN_SECRET
    )
def post_single_tweet(text: str, auth: OAuth1) -> dict:
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": text}
    
    response = requests.post(url, auth=auth, json=payload)
    
    if response.status_code == 201:
        return response.json()
    elif response.status_code == 429:  
        raise HTTPException(
            status_code=429,
            detail="Twitter rate limit exceeded. Please try again later."
        )
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to post tweet: {response.text}"
        )
def process_tweets(tweets_to_process):
    auth = get_twitter_auth()
    posted_count = 0
    failed_tweets = []
    print(f"[CRON][DEBUG] process_tweets called with: {tweets_to_process}")
    for row in tweets_to_process:
        tweet_id = row[0]
        content = row[1]
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                tweet_response = post_single_tweet(content, auth)
                tweet_id_twitter = tweet_response["data"]["id"]
                conn = get_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE posts 
                            SET status = 'posted', 
                                posted_time = NOW(),
                                posted_id = %s
                            WHERE id = %s
                            """,
                            (tweet_id_twitter, tweet_id)
                        )
                        conn.commit()
                finally:
                    conn.close()
                posted_count += 1
                time.sleep(2)  
                break
            except HTTPException as e:
                if e.status_code == 429:  
                    if retry_count < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        retry_count += 1
                        continue
                failed_tweets.append({
                    "tweet_id": tweet_id,
                    "error": str(e.detail)
                })
                break
            except Exception as e:
                failed_tweets.append({
                    "tweet_id": tweet_id,
                    "error": str(e)
                })
                break
    return posted_count, failed_tweets
@router.post("/post_tweets")
async def post_tweets(request: PostTweetsRequest):
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, content 
                    FROM posts 
                    WHERE user_id = %s 
                    AND account_id = %s 
                    AND status = 'unposted'
                    AND (scheduled_time IS NULL OR scheduled_time <= NOW())
                    ORDER BY COALESCE(scheduled_time, created_at) ASC
                    """,
                    (request.user_id, request.account_id)
                )
                unposted_tweets = cursor.fetchall()
                if not unposted_tweets:
                    return {
                        "status": "success",
                        "message": "No unposted tweets found",
                        "posted_count": 0
                    }
                posted_count, failed_tweets = process_tweets(unposted_tweets)
                return {
                    "status": "success",
                    "posted_count": posted_count,
                    "failed_tweets": failed_tweets,
                    "message": f"Successfully posted {posted_count} tweets. {len(failed_tweets)} tweets failed."
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
            detail=f"Error processing tweets: {str(e)}"
        )

@router.get("/cron/process-scheduled-tweets")
def process_due_scheduled_tweets():
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                now = datetime.now(timezone.utc)
                cursor.execute(
                    """
                    SELECT p.id, p.content, p.user_id, p.account_id, p.scheduled_time
                    FROM posts p
                    WHERE p.status = 'unposted'
                    AND p.scheduled_time IS NOT NULL
                    AND p.scheduled_time <= %s
                    AND p.scheduled_time >= %s
                    ORDER BY p.scheduled_time ASC
                    """,
                    (now, now - timedelta(minutes=SCHEDULE_CHECK_INTERVAL))
                )
                scheduled_tweets = cursor.fetchall()
                if scheduled_tweets:
                    posted_count, failed_tweets = process_tweets(scheduled_tweets)
                    print(f"[CRON] Posted {posted_count} scheduled tweets. {len(failed_tweets)} failed.")
                else:
                    print("[CRON] No scheduled tweets to process.")
                    cursor.execute(
                        """
                        SELECT p.id, p.content, p.scheduled_time, p.status
                        FROM posts p
                        WHERE p.status = 'unposted' AND p.scheduled_time IS NOT NULL
                        ORDER BY p.scheduled_time ASC
                        """
                    )
                    all_unposted = cursor.fetchall()
                    if not all_unposted:
                        print("[CRON][DEBUG] There are no unposted scheduled tweets in the database.")
                    else:
                        for row in all_unposted:
                            print(f"[CRON][DEBUG] Row length: {len(row)}, Row: {row}")
                            post_id = row[0]
                            content = row[1]
                            scheduled_time = row[2]
                            status = row[3]
                            if scheduled_time > now:
                                time_left = scheduled_time - now
                                print(f"[CRON][DEBUG] Post ID {post_id} is scheduled in {time_left}. Content: {content}")
                            else:
                                print(f"[CRON][DEBUG] Post ID {post_id} is not being picked up for unknown reason. Scheduled time: {scheduled_time}, Now: {now}")
        finally:
            conn.close()
    except Exception as e:
        print(f"[CRON] Error processing scheduled tweets: {str(e)}")

