from fastapi import FastAPI
from db.db import get_connection
from routes.users import router as user_router
from routes.twitter import router as twitter_router
import os
from routes.persona import router as persona_router
from routes.agent_routes import router as agent_router
from routes.adk_agent_routes import router as adk_agent_router
from routes.forgotPassword import router as forgot_password_router
from routes.twitter_account import router as twitter_account_router
from routes.agent_settings import router as agent_settings_router
from routes.notify_settings import router as notify_settings_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from pydantic import BaseModel
import logging
from typing import List
import asyncio
from routes.daily_tweet_generator import generate_tweet
import json
from datetime import datetime

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

@app.post("/api/generate-pre-tweets")
async def generate_tweets(request: TweetGenerationRequest):
    try:
        
        
        
        result = await generate_tweet(
            request.learning_data
        )
        
        # Save the generated tweets to database
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Get current timestamp
                current_time = datetime.utcnow()
                
                # Save each tweet as a separate row
                saved_posts = []
                for tweet in result:
                    # Convert single tweet to JSON
                    data_json = json.dumps({"tweet": tweet}, ensure_ascii=False, indent=2)
                    
                    # Insert tweet into database
                    cursor.execute(
                        """
                        INSERT INTO posts (created_at, content, user_id, account_id)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, created_at, content, user_id, account_id
                        """,
                        (current_time, data_json, request.user_id, request.account_id)
                    )
                    # Get the full post data
                    post_data = cursor.fetchone()
                    saved_posts.append({
                        "id": post_data[0],
                        "created_at": post_data[1],
                        "content": json.loads(post_data[2]),
                        "user_id": post_data[3],
                        "account_id": post_data[4]
                    })
                
                conn.commit()
                
                return {
                    "status": "success", 
                    "data": result,
                    "message": f"{len(saved_posts)} tweets saved successfully",
                    "saved_posts": saved_posts
                }
        finally:
            conn.close()
            
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    
  
    
    

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
    
    
    
    

@app.get("/api/fetch-tweets")
async def fetch_tweets(request: TweetFetchRequest):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, created_at, content, user_id, account_id
                FROM posts
                WHERE user_id = %s AND account_id = %s
                ORDER BY created_at DESC
                """,
                (request.user_id, request.account_id)
            )
            posts = cursor.fetchall()
            
            # Format the response with labeled fields
            formatted_posts = []
            for post in posts:
                formatted_posts.append({
                    "post_id": post[0],
                    "created_at": post[1],
                    "tweet_content": json.loads(post[2]),
                    "user_id": post[3],
                    "account_id": post[4]
                })
            
            return formatted_posts
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()
    
    
    
    
