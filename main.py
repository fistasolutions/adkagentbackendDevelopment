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
from agent.event_tweet_agent import EventTweetAgent, EventTweetRequest, EventTweetResponse
from agent.event_based_tweet_agent import EventBasedTweetAgent, EventBasedTweetRequest, EventBasedTweetResponse
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

class EventTweetGenerationRequest(BaseModel):
    num_drafts: int
    prompt: str
    date: Optional[str] = None

class PostInsertRequest(BaseModel):
    content: str
    user_id: Optional[int] = None
    account_id: Optional[int] = None
    mode: Optional[str] = None
    status: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    posted_time: Optional[datetime] = None
    posted_id: Optional[str] = None
    media_id: Optional[str] = None
    image_url: Optional[str] = None
    risk_score: Optional[float] = None
    manual_time: Optional[datetime] = None

class EventInsertRequest(BaseModel):
    event_title: str
    event_details: Optional[str] = None
    event_datetime: datetime
    user_id: Optional[int] = None
    account_id: int
    status: Optional[str] = "active"

class EventAndPostResponse(BaseModel):
    event: dict
    post: dict

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
    
@app.post("/api/generate-event-tweets", response_model=EventTweetResponse)
async def generate_event_tweets(request: EventTweetGenerationRequest):
    """
    Generate draft tweets based on events and prompt.
    
    Args:
        request (EventTweetGenerationRequest): The request containing the number of drafts needed, prompt, and optional date
        
    Returns:
        EventTweetResponse: The generated draft tweets
    """
    try:
        agent = EventTweetAgent()
        response = await agent.get_response(EventTweetRequest(
            num_drafts=request.num_drafts,
            prompt=request.prompt,
            date=request.date
        ))
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/insert-post")
async def insert_post(request: PostInsertRequest):
    """
    Insert a new post into the posts table using raw SQL query.
    All fields are optional except content.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Build the dynamic SQL query based on provided fields
            fields = ["content"]
            values = [request.content]
            placeholders = ["%s"]
            
            if request.user_id is not None:
                fields.append("user_id")
                values.append(request.user_id)
                placeholders.append("%s")
            
            if request.account_id is not None:
                fields.append("account_id")
                values.append(request.account_id)
                placeholders.append("%s")
            
            if request.mode is not None:
                fields.append("mode")
                values.append(request.mode)
                placeholders.append("%s")
            
            if request.status is not None:
                fields.append("status")
                values.append(request.status)
                placeholders.append("%s")
            
            if request.scheduled_time is not None:
                fields.append("scheduled_time")
                values.append(request.scheduled_time)
                placeholders.append("%s")
            
            if request.posted_time is not None:
                fields.append("posted_time")
                values.append(request.posted_time)
                placeholders.append("%s")
            
            if request.posted_id is not None:
                fields.append("posted_id")
                values.append(request.posted_id)
                placeholders.append("%s")
            
            if request.media_id is not None:
                fields.append("media_id")
                values.append(request.media_id)
                placeholders.append("%s")
            
            if request.image_url is not None:
                fields.append("Image_url")
                values.append(request.image_url)
                placeholders.append("%s")
            
            if request.risk_score is not None:
                fields.append("risk_score")
                values.append(request.risk_score)
                placeholders.append("%s")
            
            if request.manual_time is not None:
                fields.append("manual_time")
                values.append(request.manual_time)
                placeholders.append("%s")
            
            # Construct and execute the SQL query
            query = f"""
                INSERT INTO posts ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING id, content, user_id, account_id, mode, status, 
                         scheduled_time, posted_time, created_at, posted_id, 
                         media_id, "Image_url", risk_score, manual_time
            """
            
            cursor.execute(query, tuple(values))
            result = cursor.fetchone()
            conn.commit()
            
            return {
                "id": result[0],
                "content": result[1],
                "user_id": result[2],
                "account_id": result[3],
                "mode": result[4],
                "status": result[5],
                "scheduled_time": result[6],
                "posted_time": result[7],
                "created_at": result[8],
                "posted_id": result[9],
                "media_id": result[10],
                "image_url": result[11],
                "risk_score": result[12],
                "manual_time": result[13]
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()
    
@app.post("/api/insert-event", response_model=EventAndPostResponse)
async def insert_event(request: EventInsertRequest):
    """
    Insert a new event into the events table and generate a tweet for it.
    All fields are optional except event_title, event_datetime, and account_id.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # First, insert the event
            fields = ["event_title", "event_datetime", "account_id"]
            values = [request.event_title, request.event_datetime, request.account_id]
            placeholders = ["%s", "%s", "%s"]
            
            if request.event_details is not None:
                fields.append("event_details")
                values.append(request.event_details)
                placeholders.append("%s")
            
            if request.user_id is not None:
                fields.append("user_id")
                values.append(request.user_id)
                placeholders.append("%s")
            
            if request.status is not None:
                fields.append("status")
                values.append(request.status)
                placeholders.append("%s")
            
            # Insert event
            event_query = f"""
                INSERT INTO events ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING id, event_title, event_details, event_datetime, 
                         created_at, user_id, account_id, status
            """
            
            cursor.execute(event_query, tuple(values))
            event_result = cursor.fetchone()
            event_id = event_result[0]
            
            # Generate tweet using the agent
            agent = EventBasedTweetAgent()
            tweet_response = await agent.get_response(EventBasedTweetRequest(
                event_title=request.event_title,
                event_details=request.event_details or ""
            ))
            
            # Insert the generated tweet
            post_query = """
                INSERT INTO posts (content, user_id, account_id, status, created_at, scheduled_time)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                RETURNING *
            """
            
            cursor.execute(post_query, (
                tweet_response.tweet_content,
                request.user_id,
                request.account_id,
                "unposted",
                request.event_datetime
            ))
            post_result = cursor.fetchone()
            
            # Get column names for the posts table
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'posts' 
                ORDER BY ordinal_position
            """)
            post_columns = [col[0] for col in cursor.fetchall()]
            
            # Convert post_result tuple to dictionary
            post_dict = dict(zip(post_columns, post_result))
            
            conn.commit()
            
            return {
                "event": {
                    "id": event_result[0],
                    "event_title": event_result[1],
                    "event_details": event_result[2],
                    "event_datetime": event_result[3],
                    "created_at": event_result[4],
                    "user_id": event_result[5],
                    "account_id": event_result[6],
                    "status": event_result[7]
                },
                "post": post_dict
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()
    
    
    
    

    
    
    
