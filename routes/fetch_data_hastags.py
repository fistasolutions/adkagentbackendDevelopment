from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from db.db import get_connection
import json
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize router
router = APIRouter()

# X API credentials
X_BEARER_TOKEN = os.getenv('BEARER_TOKEN')  # Make sure this is set in your .env file

# Add CORS middleware
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class TweetResponse(BaseModel):
    id: str
    text: str
    created_at: str
    user: dict
    retweet_count: int
    favorite_count: int

class HashtagResponse(BaseModel):
    hashtag: str
    tweet_count: int
    tweets: List[TweetResponse]

class HashtagsResponse(BaseModel):
    results: List[HashtagResponse]

class HashtagRequest(BaseModel):
    hashtags: List[str]  # List of hashtags

def fetch_tweets_for_hashtag(hashtag: str) -> List[dict]:
    """Fetch tweets for a single hashtag using X API."""
    headers = {
        'Authorization': f'Bearer {X_BEARER_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        'query': f"#{hashtag}",
        'max_results': 10,
        'tweet.fields': 'created_at,public_metrics',
        'user.fields': 'name,username,profile_image_url',
        'expansions': 'author_id'
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    
    data = response.json()
    tweet_list = []
    
    if 'data' in data:
        users = {user['id']: user for user in data['includes']['users']}
        
        for tweet in data['data']:
            user = users[tweet['author_id']]
            tweet_data = {
                'id': str(tweet['id']),
                'text': tweet['text'],
                'created_at': tweet['created_at'],
                'user': {
                    'name': user['name'],
                    'screen_name': user['username'],
                    'profile_image_url': user['profile_image_url']
                },
                'retweet_count': tweet['public_metrics']['retweet_count'],
                'favorite_count': tweet['public_metrics']['like_count']
            }
            tweet_list.append(tweet_data)
    
    return tweet_list

@router.post("/fetch-tweets", response_model=HashtagsResponse)
async def get_tweets_by_hashtags(request: HashtagRequest):
    try:
        results = []
        
        for hashtag in request.hashtags:
            hashtag_value = hashtag.lstrip('#')
            tweet_list = fetch_tweets_for_hashtag(hashtag_value)
            
            results.append({
                'hashtag': f"#{hashtag_value}",
                'tweet_count': len(tweet_list),
                'tweets': tweet_list
            })
        
        return {'results': results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cron/fetch-hashtag-tweets")
async def cron_fetch_hashtag_tweets():
    """Cron job endpoint to fetch tweets for all accounts with postReply notifications."""
    try:
        conn = get_connection()
        results = []
        
        with conn.cursor() as cursor:
            # Get all twitter accounts with their user_ids
            cursor.execute("""
                SELECT ta.account_id, ta.user_id 
                FROM twitter_account ta
                INNER JOIN persona_notify pn ON ta.account_id = pn.account_id 
                WHERE pn.notify_type = 'postReply'
            """)
            accounts = cursor.fetchall()
            
            for account_id, user_id in accounts:
                # Get target hashtags for this account
                cursor.execute("""
                    SELECT target_hashtag 
                    FROM persona_notify 
                    WHERE account_id = %s 
                    AND user_id = %s 
                    AND notify_type = 'postReply'
                """, (account_id, user_id))
                
                hashtag_result = cursor.fetchone()
                if not hashtag_result or not hashtag_result[0]:
                    continue  # Skip if no hashtags
                
                try:
                    hashtags = json.loads(hashtag_result[0])
                    if not hashtags:  # Skip if hashtags list is empty
                        continue
                        
                    for hashtag in hashtags:
                        hashtag_value = hashtag.lstrip('#')
                        # Get today's tweet_ids for this account
                        cursor.execute("""
                            SELECT tweet_id FROM post_for_reply
                            WHERE account_id = %s AND DATE(created_at) = %s
                        """, (account_id, datetime.utcnow().date()))
                        todays_tweet_ids = set(row[0] for row in cursor.fetchall())
                        # Fetch tweets from Twitter API
                        tweet_list = fetch_tweets_for_hashtag(hashtag_value)
                        # Filter out tweets that already exist today
                        new_tweets = [tweet for tweet in tweet_list if tweet['id'] not in todays_tweet_ids]
                        if not new_tweets:
                            continue  # Skip if all tweets already exist
                        # Store the results in the database
                        cursor.execute("""
                            INSERT INTO post_data (created_at, update_at, data_json, user_id)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            datetime.utcnow(),
                            datetime.utcnow(),
                            json.dumps({
                                'hashtag': f"#{hashtag_value}",
                                'tweet_count': len(new_tweets),
                                'tweets': new_tweets,
                                'account_id': account_id
                            }),
                            user_id
                        ))
                        for tweet in new_tweets:
                            cursor.execute("""
                                INSERT INTO post_for_reply (created_at, tweet_id, text, post_username, account_id, user_id)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                datetime.utcnow(),
                                tweet['id'],
                                tweet['text'],
                                tweet['user']['screen_name'],
                                account_id,
                                user_id
                            ))
                        results.append({
                            'account_id': account_id,
                            'user_id': user_id,
                            'hashtag': f"#{hashtag_value}",
                            'tweet_count': len(new_tweets)
                        })
                        
                except json.JSONDecodeError:
                    continue  # Skip if JSON parsing fails
                
        conn.commit()
        return {'results': results, 'message': 'Successfully fetched tweets for all accounts'}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
