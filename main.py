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
from routes.post_on_twitter import router as post_on_twitter_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from pydantic import BaseModel
import logging
from typing import List
import asyncio
# from routes.daily_tweet_generator import generate_tweet
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

# @app.post("/api/generate-pre-tweets")
# async def generate_tweets(request: TweetGenerationRequest):
#     try:
#         # Check for recent tweets
#         conn = get_connection()
#         try:
#             with conn.cursor() as cursor:
#                 # Get current timestamp and 20 minutes ago
#                 current_time = datetime.utcnow()
#                 twenty_minutes_ago = current_time - timedelta(minutes=20)
                
#                 # Check for recent tweets
#                 cursor.execute(
#                     """
#                     SELECT COUNT(*) 
#                     FROM posts 
#                     WHERE user_id = %s 
#                     AND account_id = %s 
#                     AND created_at > %s
#                     """,
#                     (request.user_id, request.account_id, twenty_minutes_ago)
#                 )
#                 recent_tweets_count = cursor.fetchone()[0]
                
#                 if recent_tweets_count > 0:
#                     return {
#                         "status": "error",
#                         "message": "Cannot generate tweets. A tweet was created within the last 20 minutes for this account."
#                     }
#         finally:
#             conn.close()
        
#         result = await generate_tweet(
#             request.learning_data
#         )
        
#         # Save the generated tweets to database
#         conn = get_connection()
#         try:
#             with conn.cursor() as cursor:
#                 current_time = datetime.utcnow()
                
#                 # Save each tweet as a separate row
#                 saved_posts = []
#                 for tweet in result:
#                     # Remove the "tweet X: 1." prefix if it exists
#                     clean_tweet = tweet
#                     if ": " in tweet:
#                         clean_tweet = tweet.split(": ", 1)[1]
                    
#                     # Insert tweet into database
#                     cursor.execute(
#                         """
#                         INSERT INTO posts (created_at, content, user_id, account_id)
#                         VALUES (%s, %s, %s, %s)
#                         RETURNING id, created_at, content, user_id, account_id
#                         """,
#                         (current_time, clean_tweet, request.user_id, request.account_id)
#                     )
#                     # Get the full post data
#                     post_data = cursor.fetchone()
#                     saved_posts.append({
#                         "id": post_data[0],
#                         "created_at": post_data[1],
#                         "content": post_data[2],
#                         "user_id": post_data[3],
#                         "account_id": post_data[4]
#                     })
                
#                 conn.commit()
                
#                 return {
#                     "status": "success", 
#                     "data": result,
#                     "message": f"{len(saved_posts)} tweets saved successfully",
#                     "saved_posts": saved_posts
#                 }
#         finally:
#             conn.close()
            
#     except Exception as e:
#         return {"status": "error", "message": str(e)}
  
    
  
    
    

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
    
    
    
    

    
    
    
