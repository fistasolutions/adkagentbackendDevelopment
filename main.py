from fastapi import FastAPI
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
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from pydantic import BaseModel
import logging
from typing import List, Optional
import asyncio
from agent.draft_tweet_agent import DraftTweetAgent, DraftTweetRequest, DraftTweetResponse
import json
from datetime import datetime, timedelta

app = FastAPI()
origins = [
    "http://localhost:3000",
    "https://adkaiagentfrontend.vercel.app"
]
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],     # Or ["GET", "POST"]
    allow_headers=["*"],
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

class DraftTweetGenerationRequest(BaseModel):
    previous_tweet: str
    num_drafts: int
    prompt: Optional[str] = None

@app.get("/")
async def root():
    try:
        conn = get_connection()
        # Test the connection
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        return {"status": "success", "message": "Database connection is working"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
@app.post("/api/generate-draft-tweets", response_model=DraftTweetResponse)
async def generate_draft_tweets(request: DraftTweetGenerationRequest):
    """
    Generate draft tweets based on a previous tweet.
    
    Args:
        request (DraftTweetGenerationRequest): The request containing the previous tweet, number of drafts needed, and optional prompt
        
    Returns:
        DraftTweetResponse: The generated draft tweets
    """
    try:
        agent = DraftTweetAgent()
        response = await agent.get_response(DraftTweetRequest(
            previous_tweet=request.previous_tweet,
            num_drafts=request.num_drafts,
            prompt=request.prompt
        ))
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
    
    

    
    
    
