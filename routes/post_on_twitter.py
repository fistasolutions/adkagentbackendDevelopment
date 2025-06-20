from fastapi import APIRouter, HTTPException
from db.db import get_connection
from pydantic import BaseModel
import requests
from requests_oauthlib import OAuth1
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta, timezone
import json
load_dotenv()
router = APIRouter()
class PostTweetsRequest(BaseModel):
    user_id: int
    account_id: int
class ScheduledTweetRequest(BaseModel):
    user_id: int
    account_id: int
RATE_LIMIT_WINDOW = 15 * 60  
MAX_TWEETS_PER_WINDOW = 50  
RETRY_DELAY = 60  
MAX_RETRIES = 3
SCHEDULE_CHECK_INTERVAL = 30  

def validate_image_url(image_url: str) -> bool:
    """Validate if the image URL is accessible and returns an image"""
    try:
        response = requests.head(image_url, timeout=10)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            return content_type.startswith('image/')
        return False
    except Exception as e:
        print(f"[CRON][DEBUG] Image URL validation failed for {image_url}: {str(e)}")
        return False

def upload_media_to_twitter(image_url: str, auth: OAuth1) -> str:
    """Upload a single image to Twitter and return the media_id"""
    try:
        # Validate the image URL first
        if not validate_image_url(image_url):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid or inaccessible image URL: {image_url}"
            )
        
        # Download the image from the URL
        print(f"[CRON][DEBUG] Downloading image from: {image_url}")
        image_response = requests.get(image_url, timeout=30)
        image_response.raise_for_status()
        
        # Upload to Twitter
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"
        
        # Twitter API v1.1 media upload
        files = {'media': ('image.jpg', image_response.content, 'image/jpeg')}
        
        response = requests.post(upload_url, auth=auth, files=files, timeout=30)
        
        if response.status_code == 200:
            media_data = response.json()
            media_id = media_data['media_id_string']
            print(f"[CRON][DEBUG] Media uploaded successfully. Media ID: {media_id}")
            return media_id
        else:
            print(f"[CRON][ERROR] Media upload failed: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to upload media: {response.text}"
            )
    except Exception as e:
        print(f"[CRON][ERROR] Error uploading media: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading media: {str(e)}"
        )

def post_single_tweet(text: str, auth: OAuth1, image_urls: list = None) -> dict:
    """Post a tweet with optional images"""
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": text}
    
    # If images are provided, upload them and add media_ids to payload
    if image_urls and len(image_urls) > 0:
        try:
            # Filter out empty URLs and limit to Twitter's maximum of 4 images
            valid_image_urls = [url.strip() for url in image_urls if url and url.strip()]
            if len(valid_image_urls) > 4:
                print(f"[CRON][WARNING] Too many images ({len(valid_image_urls)}), limiting to 4")
                valid_image_urls = valid_image_urls[:4]
            
            if valid_image_urls:
                media_ids = []
                failed_images = []
                
                for i, image_url in enumerate(valid_image_urls):
                    try:
                        print(f"[CRON][DEBUG] Processing image {i+1}/{len(valid_image_urls)}: {image_url}")
                        media_id = upload_media_to_twitter(image_url, auth)
                        media_ids.append(media_id)
                        time.sleep(1)  # Small delay between uploads
                    except Exception as e:
                        print(f"[CRON][ERROR] Failed to upload image {i+1}: {str(e)}")
                        failed_images.append(f"Image {i+1}: {str(e)}")
                        continue
                
                if media_ids:
                    payload["media"] = {"media_ids": media_ids}
                    print(f"[CRON][DEBUG] Added {len(media_ids)} media IDs to tweet payload")
                    if failed_images:
                        print(f"[CRON][WARNING] Some images failed to upload: {failed_images}")
                else:
                    print(f"[CRON][WARNING] All images failed to upload, posting text-only tweet")
            else:
                print(f"[CRON][DEBUG] No valid image URLs found, posting text-only tweet")
                
        except Exception as e:
            print(f"[CRON][ERROR] Failed to upload images, posting text-only tweet: {str(e)}")
            # Continue with text-only tweet if image upload fails

    try:
        response = requests.post(url, auth=auth, json=payload, timeout=30)
        
        if response.status_code == 201:
            response_json = response.json()
            print(f"[CRON][DEBUG] Success response JSON: {response_json}")
            return response_json
        elif response.status_code == 429:  
            print(f"[CRON][ERROR] Rate limit exceeded: {response.text}")
            raise HTTPException(
                status_code=429,
                detail="Twitter rate limit exceeded. Please try again later."
            )
        else:
            print(f"[CRON][ERROR] Twitter API error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to post tweet: {response.text}"
            )
    except requests.exceptions.Timeout:
        print(f"[CRON][ERROR] Request timeout after 30 seconds")
        raise HTTPException(
            status_code=408,
            detail="Request timeout - Twitter API took too long to respond"
        )
    except requests.exceptions.ConnectionError as e:
        print(f"[CRON][ERROR] Connection error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Connection error: {str(e)}"
        )
    except Exception as e:
        print(f"[CRON][ERROR] Unexpected error in post_single_tweet: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error posting tweet: {str(e)}"
        )

def get_twitter_credentials(account_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT bearer_token, twitter_access_token, twitter_api_key, twitter_api_secret, twitter_access_token_secret
                FROM twitter_account  
                WHERE account_id = %s
                """,
                (account_id,)
            )
            result = cursor.fetchone()
            if not result:
                raise Exception(f"No Twitter credentials found for account_id {account_id}")
            return {
                "bearer_token": result[0],
                "access_token": result[1],
                "api_key": result[2],
                "api_secret": result[3],
                "access_token_secret": result[4]
            }
    finally:
        conn.close()

def process_tweets(tweets_to_process):
    posted_count = 0
    failed_tweets = []
    print(f"[CRON][DEBUG] process_tweets called with: {tweets_to_process}")
    for row in tweets_to_process:
        tweet_id = row[0]
        content = row[1]
        
        # Determine column layout based on row length
        # Regular posts: id, content, user_id, account_id, Image_url (5 columns)
        # Scheduled posts: id, content, user_id, account_id, scheduled_time, Image_url (6 columns)
        
        if len(row) == 5:
            # Regular posts format
            account_id = row[3]
            image_urls_raw = row[4]  # Image_url column
        elif len(row) == 6:
            # Scheduled posts format
            account_id = row[3]
            image_urls_raw = row[5]  # Image_url column
        else:
            # Fallback - try to get account_id from row (if available)
            try:
                account_id = row[3]
            except IndexError:
                account_id = None
            image_urls_raw = None
        
        # Try to get image_urls from row (if available)
        image_urls = None
        try:
            if image_urls_raw:
                # Parse the JSON array of image URLs
                if isinstance(image_urls_raw, str):
                    image_urls = json.loads(image_urls_raw)
                elif isinstance(image_urls_raw, list):
                    image_urls = image_urls_raw
                print(f"[CRON][DEBUG] Found image URLs: {image_urls}")
                print(f"[CRON][DEBUG] Number of images to process: {len(image_urls) if image_urls else 0}")
            else:
                print(f"[CRON][DEBUG] No image URLs found in database")
        except (IndexError, json.JSONDecodeError, TypeError) as e:
            print(f"[CRON][DEBUG] No image URLs found or invalid format: {e}")
            image_urls = None
        
        retry_count = 0
        if account_id is None:
            failed_tweets.append({
                "tweet_id": tweet_id,
                "error": "account_id missing in tweet row"
            })
            continue
        # Fetch credentials for this account
        print(f"[CRON][DEBUG] Fetching credentials for account_id: {account_id}")
        creds = get_twitter_credentials(account_id)
        print("creds", creds)
        print(f"[CRON][DEBUG] Creating OAuth1 auth object")
        auth = OAuth1(
            creds["api_key"],
            creds["api_secret"],
            creds["access_token"],
            creds["access_token_secret"]
        )
        print(f"[CRON][DEBUG] OAuth1 auth object created successfully")
        while retry_count < MAX_RETRIES:
            try:
                print(f"[CRON][DEBUG] Attempting to post tweet (attempt {retry_count + 1}/{MAX_RETRIES})")
                print(f"[CRON][DEBUG] Tweet content: {content}")
                print(f"[CRON][DEBUG] Image URLs: {image_urls}")
                tweet_response = post_single_tweet(content, auth, image_urls)
                print(f"[CRON][DEBUG] Tweet posted successfully! Response: {tweet_response}")
                tweet_id_twitter = tweet_response["data"]["id"]
                print(f"[CRON][DEBUG] Twitter tweet ID: {tweet_id_twitter}")
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
                        print(f"[CRON][DEBUG] Database updated successfully for tweet_id: {tweet_id}")
                finally:
                    conn.close()
                posted_count += 1
                time.sleep(2)  
                break
            except HTTPException as e:
                print(f"[CRON][ERROR] HTTPException occurred: {e.status_code} - {e.detail}")
                if e.status_code == 429:  
                    if retry_count < MAX_RETRIES - 1:
                        print(f"[CRON][DEBUG] Rate limited, waiting {RETRY_DELAY} seconds before retry")
                        time.sleep(RETRY_DELAY)
                        retry_count += 1
                        continue
                failed_tweets.append({
                    "tweet_id": tweet_id,
                    "error": str(e.detail)
                })
                break
            except Exception as e:
                print(f"[CRON][ERROR] Unexpected exception occurred: {str(e)}")
                print(f"[CRON][ERROR] Exception type: {type(e).__name__}")
                import traceback
                print(f"[CRON][ERROR] Full traceback: {traceback.format_exc()}")
                failed_tweets.append({
                    "tweet_id": tweet_id,
                    "error": str(e)
                })
                break
    print(f"[CRON][DEBUG] process_tweets completed. Posted: {posted_count}, Failed: {len(failed_tweets)}")
    return posted_count, failed_tweets

def is_auto_post_enabled(user_id, account_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT post_mode FROM persona_notify
                WHERE user_id = %s AND account_id = %s AND notify_type = 'post'
                """,
                (user_id, account_id)
            )
            result = cursor.fetchone()
            return result and result[0]  # True/False or None
    finally:
        conn.close()

@router.post("/post_tweets")
async def post_tweets(request: PostTweetsRequest):
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, content, user_id, account_id, "Image_url"
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

@router.post("/process_due_scheduled_tweets")
def process_due_scheduled_tweets():
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                now = datetime.now(timezone.utc)
                cursor.execute(
                    """
                    SELECT p.id, p.content, p.user_id, p.account_id, p.scheduled_time,p."Image_url"
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
                tweets_to_post = []
                for row in scheduled_tweets:
                    # Just append the entire row - process_tweets will handle the unpacking
                    tweets_to_post.append(row)
                if tweets_to_post:
                    posted_count, failed_tweets = process_tweets(tweets_to_post)
                    print(f"[CRON] Posted {posted_count} scheduled tweets. {len(failed_tweets)} failed.")
                    if failed_tweets:
                        print(f"[CRON][ERROR] Failed tweets details:")
                        for failed_tweet in failed_tweets:
                            print(f"[CRON][ERROR] Tweet ID {failed_tweet['tweet_id']}: {failed_tweet['error']}")
                else:
                    print("[CRON] No scheduled tweets to process (auto post disabled for all).")
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

