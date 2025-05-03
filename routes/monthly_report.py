from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
import json
from db.db import get_connection
from typing import List, Optional
from pydantic import BaseModel
import requests
import os
from dateutil.relativedelta import relativedelta

router = APIRouter()

class MonthlyReportRequest(BaseModel):
    user_id: int
    account_username: str

class EngagementData(BaseModel):
    id: Optional[int] = None
    likes: int
    reply: int
    impressions: int
    engagementRate: float
    user_id: int
    account_username: str

def get_twitter_followers(username, bearer_token):
    url = f"https://api.twitter.com/2/users/by/username/{username}?user.fields=public_metrics"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data["data"]["public_metrics"]["followers_count"]

@router.post("/monthly-report/{user_id}/{account_username}")
async def generate_monthly_report(user_id: int, account_username: str):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            current_time = datetime.utcnow()
            # 1. Get the first and last day of the current month
            first_day = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day = (first_day + relativedelta(months=1)) - timedelta(seconds=1)

            # 2. For each week in the month, get the latest post_data
            week_starts = []
            week_start = first_day
            while week_start < last_day:
                week_starts.append(week_start)
                week_start += timedelta(days=7)

            weekly_post_data = []
            for week_start in week_starts:
                week_end = week_start + timedelta(days=7)
                cursor.execute(
                    '''
                    SELECT data_json, update_at FROM post_data
                    WHERE user_id = %s AND username = %s
                    AND update_at >= %s AND update_at < %s
                    ORDER BY update_at DESC LIMIT 1
                    ''',
                    (user_id, account_username, week_start, week_end)
                )
                result = cursor.fetchone()
                if result:
                    weekly_post_data.append(result[0])  # data_json

            total_likes = 0
            total_replies = 0
            total_impressions = 0
            for data_json in weekly_post_data:
                posts_data = json.loads(data_json)
                for post in posts_data.get("tweets", []):
                    total_likes += post.get("like_count", 0)
                    total_replies += post.get("reply_count", 0)
                    total_impressions += post.get("impression_count", 0)

            engagementRate = ((total_likes + total_replies) / total_impressions * 100) if total_impressions > 0 else 0

            bearer_token = os.getenv("BEARER_TOKEN")  
            followers_count = get_twitter_followers(account_username, bearer_token)

            # 1. Check if a row exists for this user/account/month
            cursor.execute(
                '''
                SELECT id FROM account_analytics
                WHERE user_id = %s AND account_username = %s
                AND date_trunc('month', created_at) = date_trunc('month', %s)
                ''',
                (user_id, account_username, current_time)
            )
            existing = cursor.fetchone()

            if existing:
                # 2. Update the existing row
                cursor.execute(
                    '''
                    UPDATE account_analytics
                    SET likes = %s, reply = %s, impressions = %s, "engagementRate" = %s, followers = %s, updated_at = %s
                    WHERE id = %s
                    ''',
                    (
                        str(total_likes),
                        str(total_replies),
                        str(total_impressions),
                        str(engagementRate),
                        str(followers_count),
                        current_time,
                        existing[0]
                    )
                )
                analytics_id = existing[0]
            else:
                # 3. Insert a new row
                cursor.execute(
                    '''
                    INSERT INTO account_analytics 
                    (likes, reply, impressions, "engagementRate", followers, user_id, account_username, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    ''',
                    (
                        str(total_likes),
                        str(total_replies),
                        str(total_impressions),
                        str(engagementRate),
                        str(followers_count),
                        user_id,
                        account_username,
                        current_time,
                        current_time
                    )
                )
                analytics_id = cursor.fetchone()[0]

            conn.commit()

            engagement_data = EngagementData(
                id=analytics_id,
                likes=total_likes,
                reply=total_replies,
                impressions=total_impressions,
                engagementRate=engagementRate,
                user_id=user_id,
                account_username=account_username
            )

            return {
                "status": "success",
                "message": "Monthly report generated successfully",
                "data": engagement_data
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/monthly-report/{user_id}/{account_username}")
async def get_monthly_report(user_id: int, account_username: str):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get all reports for the given user and account
            cursor.execute(
                '''
                SELECT id, likes, reply, impressions, "engagementRate", followers, created_at
                FROM account_analytics
                WHERE user_id = %s AND account_username = %s
                ORDER BY created_at DESC
                ''',
                (user_id, account_username)
            )
            results = cursor.fetchall()

            if not results:
                raise HTTPException(
                    status_code=404,
                    detail="No reports found for the specified user and account"
                )

            # Convert results to list of dictionaries
            reports = []
            for result in results:
                report_data = {
                    "id": result[0],
                    "likes": int(result[1]),
                    "reply": int(result[2]),
                    "impressions": int(result[3]),
                    "engagementRate": float(result[4]),
                    "followers": int(result[5]),
                    "created_at": result[6],
                    "user_id": user_id,
                    "account_username": account_username
                }
                reports.append(report_data)

            return {
                "status": "success",
                "data": reports
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


