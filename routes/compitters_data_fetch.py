from fastapi import APIRouter, HTTPException, Depends
from db.db import get_connection
import random
import logging
from routes.twitter import get_twitter_credentials, get_user_id
from requests_oauthlib import OAuth1Session
import datetime
from routes.twitter_data import save_twitter_data
import json

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def save_competitor_data(content: dict, user_id: int, account_id: int, competitor_username: str, account_type: str):
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            content_json = json.dumps(content)
            cursor.execute(
                """
                INSERT INTO compititers_data (created_at, content, user_id, account_id, compititers_username, account_type)
                VALUES (NOW(), %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (content_json, user_id, account_id, competitor_username, account_type)
            )
            new_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Saved competitor data for {competitor_username} with id {new_id}")
            return new_id
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error saving competitor data for {competitor_username}: {e}")
        raise
    finally:
        if conn:
            conn.close()

async def check_data_exists_today(user_id: int, account_id: int, competitor_username: str, account_type: str) -> bool:
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id FROM compititers_data
                WHERE user_id = %s
                AND account_id = %s
                AND compititers_username = %s
                AND account_type = %s
                AND DATE(created_at) = CURRENT_DATE
                """,
                (user_id, account_id, competitor_username, account_type)
            )
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking existing data for {competitor_username}: {e}")
        return False
    finally:
        if conn:
            conn.close()

async def fetch_and_store_tweets(username: str, user_id: int, account_id: int, account_type: str):
    logger.info(f"Starting analysis for competitor user: {username}")
    try:
        creds = get_twitter_credentials(account_id)
        
        twitter_user_id = await get_user_id(username, creds)
        logger.info(f"Retrieved Twitter user ID: {twitter_user_id} for competitor {username}")
        
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(days=7)
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        all_tweets = []
        next_token = None
        
        oauth = OAuth1Session(
            creds["api_key"],
            client_secret=creds["api_secret"],
            resource_owner_key=creds["access_token"],
            resource_owner_secret=creds["access_token_secret"]
        )
        
        while True:
            url = f"https://api.twitter.com/2/users/{twitter_user_id}/tweets"
            params = {
                "max_results": 100,
                "tweet.fields": "created_at,public_metrics,conversation_id,attachments,entities",
                "expansions": "attachments.media_keys",
                "media.fields": "url,preview_image_url,type,height,width",
                "start_time": start_time_str,
                "end_time": end_time_str,
                "exclude": "replies"
            }
            if next_token:
                params["pagination_token"] = next_token

            response = oauth.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Twitter API error for {username}: {response.text}")
                # We can decide to stop or continue for other accounts.
                # For now, we log and stop for this user.
                raise Exception(f"Twitter API Error for {username}: {response.text}")
            
            data = response.json()
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
        
        await save_competitor_data(result, user_id, account_id, username, account_type)
        logger.info(f"Successfully fetched and stored {len(all_tweets)} tweets for competitor {username}")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch and store tweets for {username}: {str(e)}")
        # We might want to handle this more gracefully, e.g. by not re-raising
        # to allow the main process to continue with other accounts.
        # For now, re-raising to be aware of errors.
        raise


@router.get("/competitors-data-fetch")
async def competitors_data_fetch():
    conn = None
    fetched_data = []
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT user_id, account_id, role_models, industry_standard, competition 
                   FROM persona_safety"""
            )
            persona_records = cursor.fetchall()

        for record in persona_records:
            user_id, account_id, role_models, industry_standard, competition = record
            
            all_accounts_with_type = []
            if role_models:
                for acc_name in role_models.values():
                    if acc_name:
                         all_accounts_with_type.append((acc_name, "role_models"))
            if industry_standard:
                for acc_name in industry_standard.values():
                    if acc_name:
                        all_accounts_with_type.append((acc_name, "industry_standard"))
            if competition:
                for acc_name in competition.values():
                    if acc_name:
                        all_accounts_with_type.append((acc_name, "competition"))

            if not all_accounts_with_type:
                logger.info(f"No competitor accounts found for user_id: {user_id}, account_id: {account_id}. Skipping.")
                continue

            random.shuffle(all_accounts_with_type)

            for competitor_username, account_type in all_accounts_with_type:
                data_exists = await check_data_exists_today(user_id, account_id, competitor_username, account_type)
                if data_exists:
                    logger.info(f"Data for '{competitor_username}' ({account_type}) already fetched today for user_id: {user_id}, account_id: {account_id}. Trying next competitor.")
                    continue

                logger.info(f"Selected account '{competitor_username}' ({account_type}) for user_id: {user_id}, account_id: {account_id} for fetching.")
                try:
                    data = await fetch_and_store_tweets(competitor_username, user_id, account_id, account_type)
                    fetched_data.append(data)
                    break 
                except Exception as e:
                    logger.error(f"Could not fetch data for account '{competitor_username}' (user_id: {user_id}, account_id: {account_id}): {e}")
                    break

        return {"status": "success", "fetched_data_count": len(fetched_data), "data": fetched_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()
