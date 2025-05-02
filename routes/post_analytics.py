from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
import os
from typing import List, Dict, Any
from pydantic import BaseModel
from db.db import get_connection
from agents import Agent, Runner
import json

router = APIRouter()

class AnalysisOutput(BaseModel):
    insights: List[str]
    improvements: List[str]
    impact_analysis: str
    
class PostAnalyticsRequest(BaseModel):
    account_id: int
    user_id: int

class PostAnalyticsResponse(BaseModel):
    insights: List[str]
    improvements: List[str]
    impact_analysis: str

class ActivityLog(BaseModel):
    activity_id: int
    user_id: int
    account_id: int
    text: str
    type: str
    created_at: datetime

class ActivityLogResponse(BaseModel):
    logs: List[ActivityLog]

async def save_activity_log(conn, user_id: int, account_id: int, text: str, activity_type: str):
    """
    Save an activity log entry
    """
    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO activity_logs (user_id, account_id, text, type, created_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING activity_id
        """
        cursor.execute(query, (user_id, account_id, text, activity_type, datetime.now()))
        activity_id = cursor.fetchone()[0]
        conn.commit()
        return activity_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        if 'cursor' in locals():
            cursor.close()

# Define the analytics agent
analytics_agent = Agent(
    name="Post Analytics Agent",
    instructions="""
    You are a strategic social media analyst. Your task is to analyze social media posts and provide:
    1. 5 key insights about the impact on the industry strategy
    2. 7 specific improvement suggestions
    3. A brief analysis of the overall impact
    
    IMPORTANT: Your response must be a valid JSON object with the following exact structure:
    {
        "insights": ["insight1", "insight2", "insight3", "insight4", "insight5"],
        "improvements": ["improvement1", "improvement2", "improvement3", "improvement4", "improvement5", "improvement6", "improvement7"],
        "impact_analysis": "brief analysis of overall impact"
    }
    
    Do not include any additional text or formatting outside of this JSON structure.
    """,
    output_type=AnalysisOutput
)

async def analyze_posts_with_agent(posts: List[Dict]) -> PostAnalyticsResponse:
    """
    Analyze posts using OpenAI Agents SDK to generate strategic insights and improvements
    """
    try:
        # Prepare the posts text for analysis
        posts_text = "\n".join([f"Post {i+1}: {post.get('content', '')}" for i, post in enumerate(posts)])
        
        # Run the agent to analyze the posts
        result = await Runner.run(
            analytics_agent,
            f"Analyze these social media posts and provide strategic insights in JSON format:\n\n{posts_text}"
        )
        
        # Convert the AnalysisOutput to PostAnalyticsResponse
        analysis_output = result.final_output
        
        return PostAnalyticsResponse(
            insights=analysis_output.insights,
            improvements=analysis_output.improvements,
            impact_analysis=analysis_output.impact_analysis
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing posts: {str(e)}")

async def check_today_analysis_exists(conn, user_id: int, account_id: int) -> bool:
    """
    Check if analysis logs already exist for today
    """
    try:
        cursor = conn.cursor()
        today = datetime.now().date()
        
        query = """
        SELECT COUNT(*) 
        FROM activity_logs 
        WHERE user_id = %s 
        AND account_id = %s 
        AND type = 'impact_analysis'
        AND DATE(created_at) = %s
        """
        
        cursor.execute(query, (user_id, account_id, today))
        count = cursor.fetchone()[0]
        return count > 0
    finally:
        if 'cursor' in locals():
            cursor.close()

@router.get("/post-analytics/today", response_model=PostAnalyticsResponse)
async def get_today_post_analytics(request: PostAnalyticsRequest):
    """
    Get strategic analysis of today's posts using OpenAI Agents SDK and save results to activity logs
    """
    try:
        # Get database connection
        conn = get_connection()
        
        # Check if analysis already exists for today
        if await check_today_analysis_exists(conn, request.user_id, request.account_id):
            # If analysis exists, fetch the latest insights
            cursor = conn.cursor()
            query = """
            SELECT text, type
            FROM activity_logs
            WHERE user_id = %s 
            AND account_id = %s 
            AND DATE(created_at) = %s
            ORDER BY created_at DESC
            """
            
            today = datetime.now().date()
            cursor.execute(query, (request.user_id, request.account_id, today))
            logs = cursor.fetchall()
            
            # Group logs by type
            insights = []
            improvements = []
            impact_analysis = ""
            
            for log in logs:
                if log[1] == "insight":
                    insights.append(log[0])
                elif log[1] == "improvement":
                    improvements.append(log[0])
                elif log[1] == "impact_analysis":
                    impact_analysis = log[0]
            
            return PostAnalyticsResponse(
                insights=insights[:5],  # Ensure we only return 5 insights
                improvements=improvements[:7],  # Ensure we only return 7 improvements
                impact_analysis=impact_analysis
            )
        
        # If no analysis exists, proceed with new analysis
        cursor = conn.cursor()
        
        # Get today's date
        today = datetime.now().date()
        
        # Query to get today's posts
        query = """
        SELECT content, created_at
        FROM posts 
        WHERE DATE(created_at) = %s AND account_id = %s AND user_id = %s
        """
        
        cursor.execute(query, (today, request.account_id, request.user_id))
        posts = cursor.fetchall()
        
        if not posts:
            raise HTTPException(status_code=404, detail="No posts found for today")
        
        # Convert posts to list of dictionaries
        posts_list = [
            {
                "content": post[0],
                "created_at": post[1]
            }
            for post in posts
        ]
        
        # Analyze posts using the agent
        analysis = await analyze_posts_with_agent(posts_list)
        
        # Save insights to activity logs
        for insight in analysis.insights:
            await save_activity_log(conn, request.user_id, request.account_id, insight, "insight")
            
        # Save improvements to activity logs
        for improvement in analysis.improvements:
            await save_activity_log(conn, request.user_id, request.account_id, improvement, "improvement")
            
        # Save impact analysis to activity logs
        await save_activity_log(conn, request.user_id, request.account_id, analysis.impact_analysis, "impact_analysis")
        
        return analysis
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@router.get("/activity-logs/user/{user_id}/account/{account_id}", response_model=ActivityLogResponse)
async def get_activity_logs(user_id: int, account_id: int):
    """
    Get all activity logs for a user and account, ordered by creation time (latest first)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT activity_id, user_id, account_id, text, type, created_at
        FROM activity_logs
        WHERE user_id = %s AND account_id = %s
        ORDER BY created_at DESC
        """
        
        cursor.execute(query, (user_id, account_id))
        logs = cursor.fetchall()
        
        # Convert to ActivityLog objects
        activity_logs = [
            ActivityLog(
                activity_id=log[0],
                user_id=log[1],
                account_id=log[2],
                text=log[3],
                type=log[4],
                created_at=log[5]
            )
            for log in logs
        ]
        
        return ActivityLogResponse(logs=activity_logs)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 