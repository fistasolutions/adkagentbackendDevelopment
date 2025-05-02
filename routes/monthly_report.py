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

@router.post("/monthly-report")
async def generate_monthly_report(request: MonthlyReportRequest):
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
                    (request.user_id, request.account_username, week_start, week_end)
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
            followers_count = get_twitter_followers(request.account_username, bearer_token)

            # 1. Check if a row exists for this user/account/month
            cursor.execute(
                '''
                SELECT id FROM account_analytics
                WHERE user_id = %s AND account_username = %s
                AND date_trunc('month', created_at) = date_trunc('month', %s)
                ''',
                (request.user_id, request.account_username, current_time)
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
                        request.user_id,
                        request.account_username,
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
                user_id=request.user_id,
                account_username=request.account_username
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
