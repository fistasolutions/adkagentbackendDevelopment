from fastapi import APIRouter, HTTPException
import httpx
import time
import datetime
import json
from db.db import get_connection

router = APIRouter()

TWITTER_API_URL = "https://api.twitter.com/2/users"
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAN6v0gEAAAAA6rLvWK1fnVsfhSAwubYqulpJtVQ%3Dc0ujCdjOBasf6Zc9ewpKAgckArQHs5XdBGf5A1y7skpC2ZGqaH"
# BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAADSe0gEAAAAAHLK1v%2FQ2JFmRJsK9DqIcLLiv8rU%3DcgtltjsRjTMXSnJZEAMqjDQ0Xf0AmArVbzRRLMKShg6rOVxgZp"
# BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAABef0gEAAAAAG1WN1tJMGkifs2nrsGJTi%2BsdOM4%3Dg23lsIJHohFesKuImCMfklZBLBZk7k39jBcv84gWqcWTaP6rJc"
# BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAD6J0gEAAAAAHyOeocAJ1cffIarF6rj%2BlRuwZ24%3D8X15xgFCHEM4fpkcDkCoTwiHPr25EvXRTPw6h527b8GBQELbjN"
# BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAGtdxwEAAAAA91i%2BgzwkPpLhHOGhf40KVfbNxfY%3DuMbVHT42TpDFhwFqI9TooY1at2mJ86xmOhtcDiIntdEk45rLY5"
HEADERS = {"Authorization": f"Bearer {BEARER_TOKEN}"}
# Very basic cache dictionary
tweet_cache = {}
CACHE_TTL = 60 * 5  # Cache for 5 minutes

@router.get("/tweets/{user_id}")
async def get_user_id(username: str) -> str:
    async with httpx.AsyncClient() as client:
        url = f"https://api.twitter.com/2/users/by/username/{username}"
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200:
            raise Exception(f"Twitter API Error: {resp.text}")
        return resp.json()["data"]["id"]


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
        print(replies)
        return replies
    
@router.get("/analyze-user/")
async def analyze_user(username: str, userId: int):
    try:
        # First check if we have recent data
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
                print(last_update)
                current_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                time_diff = current_time - last_update
                if time_diff.total_seconds() < 7200:  # 2 hours in seconds
                    print("Using cached data")
                    return json.loads(data_json)

        # If no recent data, proceed with Twitter API
        user_id = await get_user_id(username)
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(days=7)
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        all_tweets = []
        next_token = None

        async with httpx.AsyncClient() as client:
            while True:
                url = f"https://api.twitter.com/2/users/{user_id}/tweets"
                params = {
                    "max_results": 100,  # Maximum allowed by Twitter API
                    "tweet.fields": "created_at,public_metrics,conversation_id,attachments,entities",
                    "expansions": "attachments.media_keys",
                    "media.fields": "url,preview_image_url,type,height,width",
                    "start_time": start_time_str,
                    "end_time": end_time_str
                }
                
                if next_token:
                    params["pagination_token"] = next_token

                resp = await client.get(url, headers=HEADERS, params=params)

                if resp.status_code != 200:
                    return {"error": resp.text}

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
                    break

            result = {
                "username": username,
                "total_tweets_analyzed": len(all_tweets),
                "tweets": all_tweets
            }

            # Save the new data to database
            from routes.twitter_data import save_twitter_data
            await save_twitter_data(result, userId,username)
            print("running twitter api")
            return result

    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

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