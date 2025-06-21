from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from requests_oauthlib import OAuth1Session
from db.db import get_connection
import logging
import json
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class FollowerResponse(BaseModel):
    username: str
    follower_count: int
    following_count: int
    tweet_count: int
    account_created_at: Optional[str] = None
    description: Optional[str] = None
    profile_image_url: Optional[str] = None
    verified: Optional[bool] = None

class AccountAnalyticsResponse(BaseModel):
    username: str
    follower_count: int
    following_count: int
    tweet_count: int
    account_created_at: Optional[str] = None
    description: Optional[str] = None
    profile_image_url: Optional[str] = None
    verified: Optional[bool] = None
    engagement_rate: Optional[float] = None
    total_impressions: Optional[int] = None
    total_likes: Optional[int] = None
    total_replies: Optional[int] = None
    total_retweets: Optional[int] = None

class MonthlyAnalytics(BaseModel):
    total_impressions: int
    total_likes: int
    total_replies: int
    total_tweets: int

class CombinedAnalyticsResponse(BaseModel):
    total_impressions: int
    total_likes: int
    total_replies: int
    engagement_rate: str
    followers: Optional[int]
    followers_change: Optional[int]

def get_twitter_credentials(account_id: int):
    """Get Twitter credentials for a specific account"""
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

async def get_user_id(username: str, creds: dict) -> str:
    """Get Twitter user ID from username"""
    url = f"https://api.twitter.com/2/users/by/username/{username}"
    
    oauth = OAuth1Session(
        creds["api_key"],
        client_secret=creds["api_secret"],
        resource_owner_key=creds["access_token"],
        resource_owner_secret=creds["access_token_secret"]
    )
    
    resp = oauth.get(url)
    
    if resp.status_code != 200:
        raise Exception(f"Failed to get user ID for {username}: {resp.text}")
    
    data = resp.json()
    if "data" not in data:
        raise Exception(f"User {username} not found")
    
    return data["data"]["id"]

def get_all_twitter_accounts():
    """Get all Twitter accounts from the database"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT account_id, username, bearer_token, twitter_access_token, twitter_api_key, twitter_api_secret, twitter_access_token_secret
                FROM twitter_account
                """
            )
            results = cursor.fetchall()
            accounts = []
            for result in results:
                accounts.append({
                    "account_id": result[0],
                    "username": result[1],
                    "bearer_token": result[2],
                    "access_token": result[3],
                    "api_key": result[4],
                    "api_secret": result[5],
                    "access_token_secret": result[6]
                })
            return accounts
    finally:
        conn.close()

@router.get("/account/followers")
async def get_all_accounts_followers():
    """
    Get follower data for all Twitter accounts in the database.
    Processes each account one by one and returns aggregated results.
    """
    try:
        # Get all accounts from database
        accounts = get_all_twitter_accounts()
        
        if not accounts:
            return {"message": "No Twitter accounts found in database", "accounts": []}
        
        results = []
        
        for account in accounts:
            try:
                username = account["username"]

                # Check if data has been fetched today
                conn_check = get_connection()
                try:
                    with conn_check.cursor() as cursor:
                        cursor.execute(
                            "SELECT 1 FROM followers WHERE account_id = %s AND DATE(created_at) = CURRENT_DATE",
                            (account['account_id'],)
                        )
                        already_fetched = cursor.fetchone()
                finally:
                    conn_check.close()
                
                if already_fetched:
                    logger.info(f"Data for {username} already fetched today. Skipping.")
                    results.append({
                        "account_id": account['account_id'],
                        "username": username,
                        "status": "skipped",
                        "message": "Data already fetched today."
                    })
                    continue

                creds = {
                    "bearer_token": account["bearer_token"],
                    "access_token": account["access_token"],
                    "api_key": account["api_key"],
                    "api_secret": account["api_secret"],
                    "access_token_secret": account["access_token_secret"]
                }
                
                # Get user ID
                user_id = await get_user_id(username, creds)
                
                # Get user details with metrics
                url = f"https://api.twitter.com/2/users/{user_id}"
                params = {
                    "user.fields": "public_metrics,created_at,description,profile_image_url,verified"
                }
                
                oauth = OAuth1Session(
                    creds["api_key"],
                    client_secret=creds["api_secret"],
                    resource_owner_key=creds["access_token"],
                    resource_owner_secret=creds["access_token_secret"]
                )
                
                resp = oauth.get(url, params=params)
                
                if resp.status_code == 200:
                    data = resp.json()
                    user_data = data.get("data", {})
                    metrics = user_data.get("public_metrics", {})
                    
                    account_data = {
                        "account_id": account["account_id"],
                        "username": username,
                        "follower_count": metrics.get("followers_count", 0),
                        "following_count": metrics.get("following_count", 0),
                        "tweet_count": metrics.get("tweet_count", 0),
                        "account_created_at": user_data.get("created_at"),
                        "description": user_data.get("description"),
                        "profile_image_url": user_data.get("profile_image_url"),
                        "verified": user_data.get("verified", False),
                        "status": "success"
                    }

                    # Save to DB
                    db_conn = get_connection()
                    try:
                        with db_conn.cursor() as cursor:
                            # 1. Save to followers table
                            follower_count = account_data["follower_count"]
                            cursor.execute(
                                """
                                INSERT INTO followers (account_id, followers, created_at)
                                VALUES (%s, %s, NOW())
                                """,
                                (account["account_id"], follower_count)
                            )

                            # 2. Update profile_image_url in twitter_account
                            profile_image_url = user_data.get("profile_image_url")
                            if profile_image_url:
                                cursor.execute(
                                    """
                                    UPDATE twitter_account SET profile_image_url = %s WHERE account_id = %s
                                    """,
                                    (profile_image_url, account["account_id"])
                                )
                            
                            db_conn.commit()
                            logger.info(f"Successfully updated database for account {username}")
                            account_data["db_status"] = "success"
                    except Exception as db_e:
                        logger.error(f"Database error for {username}: {db_e}")
                        account_data["db_status"] = "error"
                        account_data["db_error"] = str(db_e)
                    finally:
                        db_conn.close()

                else:
                    account_data = {
                        "account_id": account["account_id"],
                        "username": username,
                        "status": "error",
                        "error": f"Twitter API Error: {resp.status_code}"
                    }
                
                results.append(account_data)
                logger.info(f"Processed account {username}: {account_data.get('follower_count', 'N/A')} followers")
                
            except Exception as e:
                logger.error(f"Error processing account {account.get('username', 'unknown')}: {str(e)}")
                results.append({
                    "account_id": account.get("account_id"),
                    "username": account.get("username", "unknown"),
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "total_accounts": len(accounts),
            "successful_accounts": len([r for r in results if r.get("status") == "success"]),
            "failed_accounts": len([r for r in results if r.get("status") == "error"]),
            "accounts": results
        }
        
    except Exception as e:
        logger.error(f"Error fetching all accounts followers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/monthly-analytics", response_model=MonthlyAnalytics)
async def get_monthly_analytics(
    user_id: int,
    username: str,
    year: int,
    month: int = Query(..., ge=1, le=12)
):
    """
    Get monthly analytics for a specific Twitter account.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Fetch data from post_data table for the specific month
            cursor.execute(
                """
                SELECT data_json, created_at
                FROM post_data
                WHERE user_id = %s
                  AND username = %s
                  AND EXTRACT(YEAR FROM created_at) = %s
                  AND EXTRACT(MONTH FROM created_at) = %s
                ORDER BY created_at ASC
                """,
                (user_id, username, year, month)
            )
            rows = cursor.fetchall()

            if not rows:
                analytics = MonthlyAnalytics(total_impressions=0, total_likes=0, total_replies=0, total_tweets=0)
                _save_monthly_analytics_to_db(user_id, username, year, month, analytics)
                return analytics

            total_likes = 0
            total_replies = 0
            total_impressions = 0
            unique_tweets = set()

            for row in rows:
                data_json, created_at = row
                if data_json:  # Check if data_json is not null
                    try:
                        data = json.loads(data_json) if isinstance(data_json, str) else data_json
                        if data and 'tweets' in data and isinstance(data['tweets'], list):
                            for tweet in data['tweets']:
                                # Count unique tweets
                                if 'tweet_id' in tweet:
                                    unique_tweets.add(tweet['tweet_id'])
                                
                                # Sum up metrics
                                total_likes += tweet.get('like_count', 0)
                                total_replies += tweet.get('reply_count', 0)
                                total_impressions += tweet.get('impression_count', 0)
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        logger.warning(f"Error processing data for {username} at {created_at}: {str(e)}")
                        continue

            if not unique_tweets:
                raise HTTPException(status_code=404, detail={
                    "total_impressions": 0,
                    "total_likes": 0,
                    "total_replies": 0,
                    "total_tweets": 0
                })
            
            analytics = MonthlyAnalytics(
                total_impressions=total_impressions,
                total_likes=total_likes,
                total_replies=total_replies,
                total_tweets=len(unique_tweets)
            )
            
            _save_monthly_analytics_to_db(user_id, username, year, month, analytics)
            return analytics

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetch  ing monthly analytics for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        if conn:
            conn.close()

def _save_monthly_analytics_to_db(user_id: int, username: str, year: int, month: int, analytics: MonthlyAnalytics):
    """
    Save or update monthly analytics data to the account_analytics table.
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Calculate engagement rate
            if analytics.total_impressions > 0:
                engagement_rate = ((analytics.total_likes + analytics.total_replies) / analytics.total_impressions) * 100
            else:
                engagement_rate = 0.0

            # Check if a record already exists for this user and month
            cursor.execute(
                """
                SELECT id FROM account_analytics
                WHERE user_id = %s
                  AND EXTRACT(YEAR FROM created_at) = %s
                  AND EXTRACT(MONTH FROM created_at) = %s
                """,
                (user_id, year, month)
            )
            existing_record = cursor.fetchone()

            if existing_record:
                # Update existing record
                record_id = existing_record[0]
                cursor.execute(
                    """
                    UPDATE account_analytics
                    SET
                        likes = %s,
                        reply = %s,
                        impressions = %s,
                        "engagementRate" = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        str(analytics.total_likes),
                        str(analytics.total_replies),
                        str(analytics.total_impressions),
                        f"{engagement_rate:.2f}%",
                        record_id
                    )
                )
                logger.info(f"Updated monthly analytics for {username} for {year}-{month:02d}.")
            else:
                # Insert new record
                record_date = datetime.datetime(year, month, 1)
                cursor.execute(
                    """
                    INSERT INTO account_analytics (user_id, account_username, likes, reply, impressions, "engagementRate", created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        user_id,
                        username,
                        str(analytics.total_likes),
                        str(analytics.total_replies),
                        str(analytics.total_impressions),
                        f"{engagement_rate:.2f}%",
                        record_date
                    )
                )
                logger.info(f"Inserted new monthly analytics for {username} for {year}-{month:02d}.")

            conn.commit()

    except Exception as e:
        logger.error(f"Error saving monthly analytics for {username} to DB: {str(e)}")
        # We don't re-raise here to not fail the API call if DB save fails.
    finally:
        if conn:
            conn.close()

@router.get("/account/combined-analytics", response_model=CombinedAnalyticsResponse)
async def get_combined_analytics(
    user_id: int,
    account_id: int,
    year: int,
    username: str,
    month: int = Query(..., ge=1, le=12)
):
    """
    Get combined analytics data from account_analytics and followers tables.
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 1. Fetch from account_analytics
            cursor.execute(
                """
                SELECT likes, reply, impressions, "engagementRate"
                FROM account_analytics
                WHERE user_id = %s
                  AND account_username = %s
                  AND EXTRACT(YEAR FROM created_at) = %s
                  AND EXTRACT(MONTH FROM created_at) = %s
                """,
                (user_id, username, year, month)
            )
            analytics_record = cursor.fetchone()

            if analytics_record:
                total_likes = int(analytics_record[0])
                total_replies = int(analytics_record[1])
                total_impressions = int(analytics_record[2])
                engagement_rate = analytics_record[3]
            else:
                total_likes = 0
                total_replies = 0
                total_impressions = 0
                engagement_rate = "0.00%"

            # 2. Fetch from followers for the current month
            cursor.execute(
                """
                SELECT followers
                FROM followers
                WHERE account_id = %s
                  AND EXTRACT(YEAR FROM created_at) = %s
                  AND EXTRACT(MONTH FROM created_at) = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (account_id, year, month)
            )
            current_followers_record = cursor.fetchone()
            current_followers = current_followers_record[0] if current_followers_record else None

            # 3. Fetch from followers for the previous month
            prev_month_date = (datetime.date(year, month, 1) - datetime.timedelta(days=1))
            prev_year = prev_month_date.year
            prev_month = prev_month_date.month
            print(current_followers)
            cursor.execute(
                """
                SELECT followers
                FROM followers
                WHERE account_id = %s
                  AND EXTRACT(YEAR FROM created_at) = %s
                  AND EXTRACT(MONTH FROM created_at) = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (account_id, prev_year, prev_month)
            )
            prev_followers_record = cursor.fetchone()
            prev_followers = prev_followers_record[0] if prev_followers_record else None

            # 4. Calculate follower change
            followers_change = None
            if current_followers is not None and prev_followers is not None:
                followers_change = current_followers - prev_followers

            return CombinedAnalyticsResponse(
                total_impressions=total_impressions,
                total_likes=total_likes,
                total_replies=total_replies,
                engagement_rate=engagement_rate,
                followers=current_followers,
                followers_change=followers_change
            )

    except Exception as e:
        logger.error(f"Error fetching combined analytics for user_id {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        if conn:
            conn.close()




