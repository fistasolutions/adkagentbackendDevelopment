from typing import List
from fastapi import APIRouter, HTTPException
import httpx
import time
import datetime
import json
import logging
import asyncio

from pydantic import BaseModel
from db.db import get_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()



class UsersRequest(BaseModel):
    accounts: dict[str, str]  # Changed from List[str] to dict[str, str]

class CompetitorMetrics(BaseModel):
    id: int
    competitor_name: str
    impressions: int
    likes: int
    retweets: int
    replies: int
    engagement_rate: float
    collected_at: datetime.datetime

class MonthlyCompetitorMetrics(BaseModel):
    month: str
    competitor_name: str
    total_impressions: int
    total_likes: int
    total_retweets: int
    total_replies: int
    average_engagement_rate: float
    data_points: int

TWITTER_API_URL = "https://api.twitter.com/2/users"
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAN6v0gEAAAAATJ%2FK69fGoI5s3aLKkMKMX0R8g1M%3De9zLuhs1lfYtVTUSXJbnN2qqfINn0hWo50OXtf3BHHTmuY8abF"
HEADERS = {"Authorization": f"Bearer {BEARER_TOKEN}"}
# Very basic cache dictionary
tweet_cache = {}
CACHE_TTL = 60 * 5  # Cache for 5 minutes

TIMEOUT = httpx.Timeout(30.0, connect=10.0)  # 30 seconds total, 10 seconds for connection
CLIENT_KWARGS = {
    "timeout": TIMEOUT,
    "follow_redirects": True,
    "verify": True
}

async def get_user_id(username: str) -> str:
    async with httpx.AsyncClient(**CLIENT_KWARGS) as client:
        url = f"https://api.twitter.com/2/users/by/username/{username}"
        try:
            logger.info(f"Attempting to get user ID for username: {username}")
            resp = await client.get(url, headers=HEADERS)
            print(resp.json())
            if resp.status_code != 200:
                logger.error(f"Twitter API Error: {resp.text}")
                raise Exception(f"Twitter API Error: {resp.text}")
            return resp.json()["data"]["id"]
        except httpx.TimeoutException:
            logger.error("Timeout while getting user ID")
            raise
        except Exception as e:
            logger.error(f"Error getting user ID: {str(e)}")
            raise

async def get_tweet_replies(tweet_id: str, author_username: str):
    search_url = "https://api.twitter.com/2/tweets/search/recent"
    # Restore the original query with both conversation_id and to:username
    query = f"conversation_id:{tweet_id} to:{author_username}"

    async with httpx.AsyncClient() as client:
        params = {
            "query": query,
            "tweet.fields": "created_at,author_id,conversation_id,in_reply_to_user_id",
            "expansions": "author_id,in_reply_to_user_id",
            "user.fields": "username,name,profile_image_url",
            "max_results": 100  # Increased from 20 to get more replies
        }

        resp = await client.get(search_url, headers=HEADERS, params=params)

        if resp.status_code != 200:
            return []

        data = resp.json()
        tweets = data.get("data", [])
        users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}

        replies = []
        for tweet in tweets:
            # Skip if it's not actually a reply to the original tweet
            if tweet.get("in_reply_to_user_id") != author_username:
                continue
                
            user = users.get(tweet["author_id"], {})
            print(user)
            replies.append({
                "reply_text": tweet["text"],
                "reply_time": tweet["created_at"],
                "replied_by": {
                    "username": user.get("username"),
                    "name": user.get("name"),
                    "profile_image": user.get("profile_image_url")
                }
            })
        return replies
    
@router.get("/analyze-user/")
async def analyze_user(username: str, userId: int):
    logger.info(f"Starting analysis for user: {username} with ID: {userId}")
    conn = None
    try:
        # First check if we have recent data
        logger.info("Checking for cached data in database")
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT data_json, update_at 
                FROM post_data 
                WHERE user_id = %s AND username = %s
                ORDER BY update_at DESC 
                LIMIT 1
                """,
                (userId,username)
            )
            result = cursor.fetchone()
            if result:
                data_json, last_update = result
                logger.info(f"Found cached data from {last_update}")
                current_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                time_diff = current_time - last_update
                if time_diff.total_seconds() < 7200:  # 2 hours in seconds
                    logger.info("Using cached data as it's less than 2 hours old")
                    return json.loads(data_json)

        # If no recent data, try Twitter API
        logger.info("No recent cached data found, attempting Twitter API")
        try:
            user_id = await get_user_id(username)
            logger.info(f"Retrieved Twitter user ID: {user_id}")
            
            end_time = datetime.datetime.utcnow()
            start_time = end_time - datetime.timedelta(days=7)
            start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.info(f"Fetching tweets between {start_time_str} and {end_time_str}")

            all_tweets = []
            next_token = None

            async with httpx.AsyncClient() as client:
                while True:
                    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
                    params = {
                        "max_results": 100,
                        "tweet.fields": "created_at,public_metrics,conversation_id,attachments,entities",
                        "expansions": "attachments.media_keys",
                        "media.fields": "url,preview_image_url,type,height,width",
                        "start_time": start_time_str,
                        "end_time": end_time_str
                    }
                    
                    if next_token:
                        params["pagination_token"] = next_token

                    resp = await client.get(url, headers=HEADERS, params=params)
                    logger.info(f"Twitter API response status: {resp.status_code}")

                    if resp.status_code != 200:
                        logger.error(f"Twitter API error: {resp.text}")
                        # If Twitter API fails, return latest database data
                        if result:
                            logger.info("Returning latest database data due to Twitter API error")
                            return json.loads(data_json)
                        raise Exception(f"Twitter API Error: {resp.text}")

                    data = resp.json()
                    tweets = data.get("data", [])
                    logger.info(f"Retrieved {len(tweets)} tweets")
                    media = {m["media_key"]: m for m in data.get("includes", {}).get("media", [])}

                    for tweet in tweets:
                        metrics = tweet.get("public_metrics", {})
                        
                        tweet_media = []
                        if "attachments" in tweet and "media_keys" in tweet["attachments"]:
                            for media_key in tweet["attachments"]["media_keys"]:
                                if media_key in media:
                                    media_item = media[media_key]
                                    tweet_media.append({
                                        "type": media_item["type"],
                                        "url": media_item.get("url"),
                                        "preview_url": media_item.get("preview_image_url"),
                                        "dimensions": {
                                            "height": media_item.get("height"),
                                            "width": media_item.get("width")
                                        }
                                    })

                        all_tweets.append({
                            "tweet_id": tweet["id"],
                            "text": tweet["text"],
                            "created_at": tweet["created_at"],
                            "like_count": metrics.get("like_count"),
                            "retweet_count": metrics.get("retweet_count"),
                            "reply_count": metrics.get("reply_count"),
                            "quote_count": metrics.get("quote_count"),
                            "impression_count": metrics.get("impression_count"),
                            "media": tweet_media
                        })

                    next_token = data.get("meta", {}).get("next_token")
                    if not next_token:
                        logger.info("No more tweets to fetch")
                        break

                result = {
                    "username": username,
                    "total_tweets_analyzed": len(all_tweets),
                    "tweets": all_tweets
                }

                logger.info(f"Successfully analyzed {len(all_tweets)} tweets for user {username}")
                
                logger.info("Saving data to database")
                from routes.twitter_data import save_twitter_data
                await save_twitter_data(result, userId, username)
                logger.info("Data saved successfully")
                return result

        except Exception as e:
            logger.error(f"Twitter API error: {str(e)}")
            # If Twitter API fails, return latest database data
            if result:
                logger.info("Returning latest database data due to Twitter API error")
                return json.loads(data_json)
            raise Exception(f"Twitter API Error: {str(e)}")

    except Exception as e:
        logger.error(f"Error in analyze_user: {str(e)}", exc_info=True)
        # If we have any database data, return it
        if result:
            logger.info("Returning latest database data due to error")
            return json.loads(data_json)
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")
            
            
@router.get("/analyze-user-replies")
async def analyze_user_replies(username: str, user_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # First check if we have recent data in comments table (within 2 hours)
            cursor.execute(
                """
                SELECT content, created_at 
                FROM comments 
                WHERE user_id = %s AND account_username = %s
                AND created_at > NOW() - INTERVAL '2 hours'
                ORDER BY created_at DESC 
                LIMIT 1
                """,
                (user_id, username)
            )
            result = cursor.fetchone()
            
            # If we have recent comments data, return it
            if result:
                content_json, created_at = result
                logger.info(f"Found cached comments data from {created_at}")
                return json.loads(content_json)
            # If no recent data, proceed with API call
            logger.info("No recent comments data found, fetching from Twitter API")
            # Get the latest data from post_data table
            cursor.execute(
                """
                SELECT data_json 
                FROM post_data 
                WHERE user_id = %s AND username = %s
                ORDER BY update_at DESC 
                LIMIT 1
                """,
                (user_id, username)
            )
            result = cursor.fetchone()
            
            if not result:
                return []
                
            data_json = json.loads(result[0])
            tweets = data_json.get("tweets", [])
            
            # Create a map of tweet_id -> tweet text
            tweet_map = {tweet["tweet_id"]: tweet["text"] for tweet in tweets}
            
            # For each tweet ID, get replies from Twitter API
            all_replies = []
            for tweet_id, tweet_text in tweet_map.items():
                url = f"https://api.twitter.com/2/tweets/search/recent?query=conversation_id:{tweet_id}&tweet.fields=author_id,in_reply_to_user_id,conversation_id,created_at&expansions=author_id&user.fields=username"
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=HEADERS)
                    response.raise_for_status()
                    twitter_data = response.json()
                    
                    # Create a map of author_id -> username
                    author_map = {user["id"]: user["username"] for user in twitter_data.get("includes", {}).get("users", [])}
                    
                    # Extract replies
                    replies = []
                    for tweet in twitter_data.get("data", []):
                        author_id = tweet["author_id"]
                        commenter_name = author_map.get(author_id, "unknown_user")
                        # Include the tweet creation time from Twitter API
                        replies.append({
                            "username": commenter_name,
                            "text": tweet["text"],
                            "created_at": tweet.get("created_at")
                        })
                    
                    if replies:  # Only add if there are replies
                        all_replies.append({
                            "tweet_id": tweet_id,
                            "tweet_text": tweet_text,
                            "replies": replies
                        })
            
            # Save all replies to comments table
            if all_replies:
                # Convert to JSON string
                replies_json = json.dumps(all_replies)
                
                # Save to comments table
                cursor.execute(
                    """
                    INSERT INTO comments 
                    (content, user_id, account_username)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (replies_json, user_id, username)
                )
                conn.commit()
            
            return all_replies
            
    except Exception as e:
        logger.error(f"Error in analyze_user_replies: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

@router.get("/followers/{username}")
async def get_user_followers(username: str):
    try:
        # First get the user ID
        user_id = await get_user_id(username)
        
        # Now get the followers
        url = f"{TWITTER_API_URL}/{user_id}/followers"
        params = {
            "max_results": 100,
            "user.fields": "username,name,profile_image_url"
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=HEADERS, params=params)
            
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Twitter API Error: {resp.text}")
                
            data = resp.json()
            followers = data.get("data", [])
            
            return {
                "username": username,
                "total_followers": len(followers),
                "followers": followers
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trends/japan")
async def get_japan_trends():
    """Get trending topics in Japan"""
    try:
        url = "https://api.twitter.com/1.1/trends/place.json"
        params = {
            "id": 23424856  # WOEID for Japan
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=HEADERS, params=params)
            
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Twitter API Error: {resp.text}")
                
            data = resp.json()
            if not data or not isinstance(data, list) or len(data) == 0:
                return {"trends": []}
                
            trends = data[0].get("trends", [])
            
            return {
                "location": "Japan",
                "as_of": data[0].get("as_of"),
                "created_at": data[0].get("created_at"),
                "trends": trends
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def make_twitter_request(client, url, headers, params, max_retries=5):
    """
    Make a request to Twitter API with retry logic and exponential backoff
    """
    for attempt in range(max_retries):
        try:
            resp = await client.get(url, headers=headers, params=params)
            
            if resp.status_code == 429:  # Rate limit exceeded
                if attempt < max_retries - 1:
                    # Calculate backoff time (exponential backoff)
                    backoff_time = (2 ** attempt) * 5  # 5, 10, 20, 40, 80 seconds
                    logger.warning(f"Rate limit exceeded. Retrying in {backoff_time} seconds...")
                    await asyncio.sleep(backoff_time)
                    continue
                else:
                    raise Exception("Max retries reached for rate limit")
                    
            if resp.status_code != 200:
                raise Exception(f"Twitter API Error: {resp.text}")
                
            return resp
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Request failed, retrying... Error: {str(e)}")
            await asyncio.sleep(5)  # Basic retry delay

class MultipleAccountsRequest(BaseModel):
    usernames: List[str]
    user_id: int
    account_id: int

async def wait_for_rate_limit_reset(reset_time: int):
    """Wait until the rate limit reset time"""
    current_time = int(time.time())
    wait_time = max(0, reset_time - current_time)
    if wait_time > 0:
        logger.info(f"Rate limit reached. Waiting {wait_time} seconds until reset...")
        await asyncio.sleep(wait_time)

@router.post("/analyze-multiple-accounts")
async def analyze_multiple_accounts(request: MultipleAccountsRequest):
    """
    Fetch Twitter data for multiple accounts over the last 7 days.
    Returns data for each account including tweets, metrics, and engagement.
    Saves data to compititers_data table for each account.
    Skips API call if data exists from last 2 hours.
    """
    try:
        results = {}
        conn = get_connection()
        pending_accounts = request.usernames.copy()
        
        while pending_accounts:
            for username in pending_accounts[:]:  # Create a copy to iterate
                try:
                    # First check if we have recent data (less than 2 hours old)
                    with conn.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT content, created_at 
                            FROM compititers_data 
                            WHERE user_id = %s 
                            AND account_id = %s 
                            AND compititers_username = %s
                            AND created_at > NOW() - INTERVAL '2 hours'
                            ORDER BY created_at DESC 
                            LIMIT 1
                            """,
                            (request.user_id, request.account_id, username)
                        )
                        existing_data = cursor.fetchone()
                        
                        if existing_data:
                            # If we have recent data, use it instead of calling Twitter API
                            if isinstance(existing_data[0], str):
                                content = json.loads(existing_data[0])
                            else:
                                content = existing_data[0]
                            results[username] = {
                                "status": "success",
                                "username": username,
                                "total_tweets": content["total_tweets"],
                                "total_likes": content["total_likes"],
                                "total_retweets": content["total_retweets"],
                                "total_replies": content["total_replies"],
                                "total_impressions": content["total_impressions"],
                                "engagement_rate": content["engagement_rate"],
                                "saved_data_id": existing_data[1],
                                "data_status": "cached",
                                "cached_at": existing_data[1].isoformat()
                            }
                            pending_accounts.remove(username)
                            continue
                    
                    # If no recent data, proceed with Twitter API call
                    user_id = None
                    for attempt in range(5):  # Try up to 5 times
                        try:
                            user_id = await get_user_id(username)
                            break
                        except Exception as e:
                            if "Too Many Requests" in str(e):
                                # Get reset time from response headers
                                reset_time = int(e.response.headers.get('x-rate-limit-reset', 0))
                                if reset_time > 0:
                                    await wait_for_rate_limit_reset(reset_time)
                                    continue
                            if attempt < 4:
                                backoff_time = (2 ** attempt) * 5
                                logger.warning(f"Error getting user ID for {username}. Retrying in {backoff_time} seconds...")
                                await asyncio.sleep(backoff_time)
                                continue
                            raise
                    
                    if not user_id:
                        raise Exception("Failed to get user ID after retries")
                    
                    # Set time range for last 7 days
                    end_time = datetime.datetime.now(datetime.timezone.utc)
                    start_time = end_time - datetime.timedelta(days=2)
                    start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    
                    all_tweets = []
                    next_token = None
                    
                    async with httpx.AsyncClient() as client:
                        while True:
                            try:
                                url = f"https://api.twitter.com/2/users/{user_id}/tweets"
                                params = {
                                    "max_results": 100,
                                    "tweet.fields": "created_at,public_metrics,conversation_id,attachments,entities",
                                    "expansions": "attachments.media_keys",
                                    "media.fields": "url,preview_image_url,type,height,width",
                                    "start_time": start_time_str,
                                    "end_time": end_time_str
                                }
                                
                                if next_token:
                                    params["pagination_token"] = next_token
                                
                                resp = await client.get(url, headers=HEADERS, params=params)
                                
                                if resp.status_code == 429:  # Rate limit exceeded
                                    reset_time = int(resp.headers.get('x-rate-limit-reset', 0))
                                    if reset_time > 0:
                                        await wait_for_rate_limit_reset(reset_time)
                                        continue
                                    else:
                                        raise Exception("Rate limit exceeded but no reset time provided")
                                
                                if resp.status_code != 200:
                                    raise Exception(f"Twitter API Error: {resp.text}")
                                
                                data = resp.json()
                                tweets = data.get("data", [])
                                media = {m["media_key"]: m for m in data.get("includes", {}).get("media", [])}
                                
                                for tweet in tweets:
                                    metrics = tweet.get("public_metrics", {})
                                    
                                    tweet_media = []
                                    if "attachments" in tweet and "media_keys" in tweet["attachments"]:
                                        for media_key in tweet["attachments"]["media_keys"]:
                                            if media_key in media:
                                                media_item = media[media_key]
                                                tweet_media.append({
                                                    "type": media_item["type"],
                                                    "url": media_item.get("url"),
                                                    "preview_url": media_item.get("preview_image_url"),
                                                    "dimensions": {
                                                        "height": media_item.get("height"),
                                                        "width": media_item.get("width")
                                                    }
                                                })
                                                
                                    tweet_data = {
                                        "tweet_id": tweet["id"],
                                        "text": tweet["text"],
                                        "created_at": tweet["created_at"],
                                        "like_count": metrics.get("like_count", 0),
                                        "retweet_count": metrics.get("retweet_count", 0),
                                        "reply_count": metrics.get("reply_count", 0),
                                        "quote_count": metrics.get("quote_count", 0),
                                        "impression_count": metrics.get("impression_count", 0),
                                        "media": tweet_media
                                    }
                                    
                                    all_tweets.append(tweet_data)
                                
                                next_token = data.get("meta", {}).get("next_token")
                                if not next_token:
                                    break
                                    
                            except Exception as e:
                                if "Too Many Requests" in str(e):
                                    reset_time = int(e.response.headers.get('x-rate-limit-reset', 0))
                                    if reset_time > 0:
                                        await wait_for_rate_limit_reset(reset_time)
                                        continue
                                raise
                    
                    # Calculate aggregated metrics
                    total_tweets = len(all_tweets)
                    total_likes = sum(tweet["like_count"] for tweet in all_tweets)
                    total_retweets = sum(tweet["retweet_count"] for tweet in all_tweets)
                    total_replies = sum(tweet["reply_count"] for tweet in all_tweets)
                    total_impressions = sum(tweet["impression_count"] for tweet in all_tweets)
                    engagement_rate = (total_likes + total_retweets + total_replies) / total_impressions if total_impressions > 0 else 0
                    
                    # Prepare data for saving
                    account_data = {
                        "username": username,
                        "total_tweets": total_tweets,
                        "total_likes": total_likes,
                        "total_retweets": total_retweets,
                        "total_replies": total_replies,
                        "total_impressions": total_impressions,
                        "engagement_rate": engagement_rate,
                        "tweets": all_tweets,
                        "data_status": "complete"
                    }
                    
                    # Save to compititers_data table with retry
                    for attempt in range(5):
                        try:
                            with conn.cursor() as cursor:
                                cursor.execute(
                                    """
                                    INSERT INTO compititers_data 
                                    (content, user_id, account_id, created_at,compititers_username)
                                    VALUES (%s, %s, %s, %s,%s)
                                    RETURNING id
                                    """,
                                    (
                                        json.dumps(account_data),
                                        request.user_id,
                                        request.account_id,
                                        datetime.datetime.now(datetime.timezone.utc),
                                        username
                                    )
                                )
                                data_id = cursor.fetchone()[0]
                                conn.commit()
                                break
                        except Exception as e:
                            if attempt < 4:
                                backoff_time = (2 ** attempt) * 5
                                logger.warning(f"Database error saving data for {username}, retrying in {backoff_time} seconds... Error: {str(e)}")
                                await asyncio.sleep(backoff_time)
                                continue
                            raise
                    
                    results[username] = {
                        "username": username,
                        "total_tweets": total_tweets,
                        "total_likes": total_likes,
                        "total_retweets": total_retweets,
                        "total_replies": total_replies,
                        "total_impressions": total_impressions,
                        "engagement_rate": engagement_rate,
                        "tweets": all_tweets,
                        "saved_data_id": data_id,
                        "data_status": "complete"
                    }
                    
                    # Remove successfully processed account from pending list
                    pending_accounts.remove(username)
                    
                except Exception as e:
                    logger.error(f"Error processing account {username}: {str(e)}")
                    if "Too Many Requests" in str(e):
                        # Keep the account in pending_accounts for retry
                        continue
                    results[username] = {"error": str(e)}
                    pending_accounts.remove(username)
                
        return {
            "status": "success",
            "results": results,
            "summary": {
                "total_accounts": len(request.usernames),
                "successful_analyses": len([r for r in results.values() if "error" not in r]),
                "failed_analyses": len([r for r in results.values() if "error" in r])
            }
        }
        
    except Exception as e:
        logger.error(f"Error in analyze_multiple_accounts: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

@router.get("/competitor-metrics/monthly/{user_id}/{account_id}")
async def get_monthly_competitor_metrics(user_id: int, account_id: int):
    """
    Fetch monthly aggregated competitor metrics for a specific user and account.
    Returns data grouped by month and competitor, ensuring no duplicate data is used within 48 hours.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # First, let's check if we have any data at all for this user and account
            cursor.execute("""
                SELECT COUNT(*) 
                FROM competitor_metrics 
                WHERE user_id = %s AND account_id = %s
            """, (user_id, account_id))
            total_records = cursor.fetchone()[0]
            logger.info(f"Total records found for user_id {user_id} and account_id {account_id}: {total_records}")

            if total_records == 0:
                return {"message": "No competitor metrics found for the specified user and account"}

            # Get the date range of our data
            cursor.execute("""
                SELECT MIN(collected_at), MAX(collected_at)
                FROM competitor_metrics
                WHERE user_id = %s AND account_id = %s
            """, (user_id, account_id))
            min_date, max_date = cursor.fetchone()
            logger.info(f"Data date range: from {min_date} to {max_date}")

            # Now get the monthly metrics
            cursor.execute("""
                WITH latest_data AS (
                    SELECT 
                        competitor_name,
                        MAX(collected_at) as last_collected
                    FROM competitor_metrics
                    WHERE user_id = %s 
                    AND account_id = %s
                    GROUP BY competitor_name
                )
                SELECT 
                    DATE_TRUNC('month', cm.collected_at) as month,
                    cm.competitor_name,
                    SUM(cm.impressions) as total_impressions,
                    SUM(cm.likes) as total_likes,
                    SUM(cm.retweets) as total_retweets,
                    SUM(cm.replies) as total_replies,
                    AVG(cm.engagement_rate) as average_engagement_rate,
                    COUNT(*) as data_points
                FROM competitor_metrics cm
                LEFT JOIN latest_data ld ON cm.competitor_name = ld.competitor_name
                WHERE cm.user_id = %s 
                AND cm.account_id = %s
                AND (
                    -- Include the record if it's the only one for this competitor
                    NOT EXISTS (
                        SELECT 1 
                        FROM competitor_metrics cm2 
                        WHERE cm2.competitor_name = cm.competitor_name 
                        AND cm2.user_id = cm.user_id 
                        AND cm2.account_id = cm.account_id
                        AND cm2.collected_at > cm.collected_at
                    )
                    -- OR if it's older than 48 hours from the latest record
                    OR (ld.last_collected IS NOT NULL AND cm.collected_at <= ld.last_collected - INTERVAL '48 hours')
                )
                GROUP BY DATE_TRUNC('month', cm.collected_at), cm.competitor_name
                ORDER BY month DESC, cm.competitor_name
            """, (user_id, account_id, user_id, account_id))
            
            results = cursor.fetchall()
            
            if not results:
                return {
                    "message": "No competitor metrics found for the specified period",
                    "debug_info": {
                        "total_records": total_records,
                        "date_range": {
                            "min": min_date.isoformat() if min_date else None,
                            "max": max_date.isoformat() if max_date else None
                        }
                    }
                }
            
            # Convert results to list of MonthlyCompetitorMetrics
            monthly_metrics = []
            for row in results:
                monthly_metrics.append(MonthlyCompetitorMetrics(
                    month=row[0].strftime("%Y-%m"),
                    competitor_name=row[1],
                    total_impressions=row[2],
                    total_likes=row[3],
                    total_retweets=row[4],
                    total_replies=row[5],
                    average_engagement_rate=float(row[6]),
                    data_points=row[7]
                ))
            
            return {
                "user_id": user_id,
                "account_id": account_id,
                "metrics": monthly_metrics,
                "debug_info": {
                    "total_records": total_records,
                    "date_range": {
                        "min": min_date.isoformat() if min_date else None,
                        "max": max_date.isoformat() if max_date else None
                    }
                }
            }
            
    except Exception as e:
        logger.error(f"Error fetching monthly competitor metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

@router.get("/tweet/{tweet_id}")
async def get_tweet_details(tweet_id: str):
    """
    Get only likes and comments count for a specific tweet
    """
    try:
        # Get tweet details
        url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        params = {
            "tweet.fields": "public_metrics"
        }

        async with httpx.AsyncClient() as client:
            # Get tweet details
            resp = await client.get(url, headers=HEADERS, params=params)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Twitter API Error: {resp.text}")

            data = resp.json()
            tweet_data = data.get("data", {})
            metrics = tweet_data.get("public_metrics", {})

            return {
                "likes": metrics.get("like_count", 0),
                "comments": metrics.get("reply_count", 0)
            }

    except Exception as e:
        logger.error(f"Error in get_tweet_details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retweets/{username}")
async def get_user_retweets(username: str):
    """
    Fetch only retweets made by a specific Twitter account.
    Returns information about which tweets were retweeted by the account.
    """
    try:
        # First get the user ID
        user_id = await get_user_id(username)
        
        # Set time range for last 7 days
        end_time = datetime.datetime.now(datetime.timezone.utc)
        start_time = end_time - datetime.timedelta(days=7)
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        url = f"https://api.twitter.com/2/users/{user_id}/tweets"
        params = {
            "max_results": 100,
            "tweet.fields": "created_at,referenced_tweets,public_metrics",
            "expansions": "referenced_tweets.id,referenced_tweets.id.author_id",
            "user.fields": "username,name,profile_image_url",
            "start_time": start_time_str,
            "end_time": end_time_str,
            "exclude": "replies"  # Only exclude replies, as retweets are handled by the referenced_tweets filter
        }
        
        all_retweets = []
        next_token = None
        
        async with httpx.AsyncClient() as client:
            while True:
                if next_token:
                    params["pagination_token"] = next_token
                
                resp = await client.get(url, headers=HEADERS, params=params)
                
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=f"Twitter API Error: {resp.text}")
                
                data = resp.json()
                tweets = data.get("data", [])
                
                # Create maps for referenced tweets and users
                referenced_tweets = {tweet["id"]: tweet for tweet in data.get("includes", {}).get("tweets", [])}
                users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}
                
                for tweet in tweets:
                    # Only process retweets
                    if "referenced_tweets" in tweet:
                        for ref in tweet["referenced_tweets"]:
                            if ref["type"] == "retweeted":
                                original_tweet = referenced_tweets.get(ref["id"])
                                if original_tweet:
                                    original_author = users.get(original_tweet["author_id"])
                                    retweet_data = {
                                        "retweet_id": tweet["id"],
                                        "retweeted_at": tweet["created_at"],
                                        "original_tweet": {
                                            "id": original_tweet["id"],
                                            "text": original_tweet["text"],
                                            "created_at": original_tweet["created_at"],
                                            "metrics": original_tweet.get("public_metrics", {}),
                                            "author": {
                                                "username": original_author.get("username"),
                                                "name": original_author.get("name"),
                                                "profile_image_url": original_author.get("profile_image_url")
                                            } if original_author else None
                                        }
                                    }
                                    all_retweets.append(retweet_data)
                
                next_token = data.get("meta", {}).get("next_token")
                if not next_token:
                    break
        
        return {
            "username": username,
            "total_retweets": len(all_retweets),
            "retweets": all_retweets
        }
        
    except Exception as e:
        logger.error(f"Error in get_user_retweets: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

