from fastapi import FastAPI, HTTPException
from db.db import get_connection
from routes.users import router as user_router
from routes.twitter import router as twitter_router
import os
from routes.persona import router as persona_router
from routes.twitter_data import router as twitter_data_router
from routes.agent_routes import router as agent_router
from routes.adk_agent_routes import router as adk_agent_router
from routes.forgotPassword import router as forgot_password_router
from routes.twitter_account import router as twitter_account_router
from routes.agent_settings import router as agent_settings_router
from routes.notify_settings import router as notify_settings_router
from routes.daily_tweet_generator import router as daily_tweet_generator_router
from routes.post_on_twitter import router as post_on_twitter_router, process_due_scheduled_tweets
from routes.compitterAccounts import router as compitter_accounts_router
from routes.risk_scoring_agent import router as risk_scoring_agent_router
from routes.monthly_report import router as monthly_report_router
from routes.post_analytics import router as post_analytics_router
from routes.post_request import router as post_request_router
from routes.posts import router as posts_router
from routes.events import router as events_router
from routes.comments import router as comments_router
from routes.comment_response_agent import router as comment_response_router
from routes.comment_workflow import router as comment_workflow_router
from routes.change_time import router as change_time_router
from routes.post_reply import router as post_reply_router
from routes.fetch_data_hastags import router as hashtag_router
from routes.comment_reply_api import router as comment_reply_api_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body, Query
from pydantic import BaseModel
import logging
from typing import List, Optional
import asyncio
import json
from datetime import datetime, timedelta
from routes import daily_tweet_generator, persona, comment_response_agent, comment_workflow
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()
origins = [
    "http://localhost:3000",
    "https://adkaiagentfrontend.vercel.app",
    "https://adkagentbackenddevelopment-production.up.railway.app",
    "http://localhost:8000"
]
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Use the defined origins list
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include the user routes
app.include_router(user_router, prefix="/api")
app.include_router(twitter_router, prefix="/api")
app.include_router(persona_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(adk_agent_router, prefix="/api")
app.include_router(forgot_password_router, prefix="/api")
app.include_router(twitter_account_router, prefix="/api")
app.include_router(agent_settings_router, prefix="/api")
app.include_router(notify_settings_router, prefix="/api")
app.include_router(twitter_data_router, prefix="/api")
app.include_router(post_on_twitter_router, prefix="/api")
app.include_router(daily_tweet_generator_router, prefix="/api")
app.include_router(compitter_accounts_router, prefix="/api")
app.include_router(risk_scoring_agent_router, prefix="/api")    
app.include_router(monthly_report_router, prefix="/api")
app.include_router(post_analytics_router, prefix="/api")
app.include_router(post_request_router, prefix="/api")
app.include_router(posts_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(comments_router, prefix="/api")
app.include_router(comment_response_router, prefix="/api")
app.include_router(daily_tweet_generator.router, prefix="/api")
app.include_router(persona.router, prefix="/api")
app.include_router(comment_response_agent.router, prefix="/api")
app.include_router(comment_workflow.router, prefix="/api")
app.include_router(change_time_router, prefix="/api")
app.include_router(post_reply_router, prefix="/api")
app.include_router(hashtag_router, prefix="/api")
app.include_router(comment_reply_api_router, prefix="/api")


class TweetGenerationRequest(BaseModel):
    learning_data: str
    account_id: int
    user_id: int

class SaveTweetsRequest(BaseModel):
    tweets: List[str]
    user_id: int
    username: str

class TweetFetchRequest(BaseModel):
    user_id: int
    account_id: int

class ReplyResponse(BaseModel):
    tweet_id: str
    tweet_text: str
    replies: List[dict]
    risk_score: int
    risk_factors: List[str]
    explanation: str

@app.get("/")
async def root():
    return {"message": "Welcome to ADK Agent Backend API"}

@app.get("/api/replies/{account_username}")
async def get_replies(
    account_username: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    """
    Get replies for a specific account username and date.
    The date should be in YYYY-MM-DD format.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Parse the date to ensure it's valid
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Please use YYYY-MM-DD"
                )
            
            # Query to get comments for the specific date and account
            query = """
                SELECT content
                FROM comments
                WHERE account_username = %s
                AND DATE(created_at) = %s
            """
            
            cursor.execute(query, (account_username, target_date))
            result = cursor.fetchone()
            
            if not result:
                return {
                    "account_username": account_username,
                    "date": date,
                    "replies": []
                }
            
            # Parse the JSON content
            try:
                content_data = json.loads(result[0])
                return {
                    "account_username": account_username,
                    "date": date,
                    "replies": content_data
                }
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=500,
                    detail="Error parsing comment content"
                )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()
    
    
    
    

    
    
    
