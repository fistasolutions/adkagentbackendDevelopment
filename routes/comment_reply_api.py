from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from db.db import get_connection
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
from requests_oauthlib import OAuth1Session
import time

load_dotenv()

router = APIRouter()

def get_twitter_credentials_for_account(account_id):
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

def get_twitter_auth(credentials):
    return OAuth1Session(
        credentials["api_key"],
        client_secret=credentials["api_secret"],
        resource_owner_key=credentials["access_token"],
        resource_owner_secret=credentials["access_token_secret"]
    )

class CommentResponse(BaseModel):
    id: str
    text: str
    author_id: str
    created_at: str
    username: str

class PostWithComments(BaseModel):
    id: int
    content: str
    user_id: int
    account_id: int
    status: str
    posted_id: Optional[str]
    posted_time: Optional[datetime]
    created_at: datetime
    comments: List[CommentResponse]

@router.get("/posts-with-comments", response_model=List[PostWithComments])
async def get_posts_with_comments(
    limit: int = Query(20, ge=1, le=50)
):
    """
    Fetch posts with their comments from Twitter API.
    Only returns posts with status "posted" in round-robin order.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get posts with status 'posted' in round-robin order
            cursor.execute(
                """
                SELECT id, content, user_id, account_id, status, posted_id, 
                       posted_time, created_at
                FROM posts 
                WHERE status = 'posted'
                ORDER BY COALESCE(comments_fetched_at, created_at) ASC
                LIMIT %s
                """,
                (limit,)
            )
            posts = cursor.fetchall()
            
            result = []
            
            for post in posts:
                posted_id = post[5]  # post[5] is posted_id
                account_id = post[3]  # post[3] is account_id
                if not posted_id:
                    continue

                # Fetch credentials for this account
                try:
                    credentials = get_twitter_credentials_for_account(account_id)
                except Exception as e:
                    print(f"No Twitter credentials found for account_id {account_id}: {str(e)}")
                    continue

                oauth = get_twitter_auth(credentials)

                # Add delay between requests to avoid rate limiting
                time.sleep(1)  # 1 second delay between requests

                # Fetch comments from Twitter API
                url = f"https://api.twitter.com/2/tweets/search/recent"
                params = {
                    "query": f"in_reply_to_tweet_id:{posted_id}",
                    "tweet.fields": "author_id,created_at,in_reply_to_user_id",
                    "expansions": "author_id",
                    "user.fields": "username",
                    "max_results": 100
                }
                
                try:
                    response = oauth.get(url, params=params)
                    print(f"Twitter API response for tweet {posted_id}: Status {response.status_code}")
                    if response.status_code == 429:  # Rate limit exceeded
                        print(f"Rate limit hit for tweet {posted_id}, waiting 15 seconds...")
                        time.sleep(15)  # Wait 15 seconds before retrying
                        response = oauth.get(url, params=params)
                    
                    if response.status_code != 200:
                        print(f"Twitter API error for tweet {posted_id}: {response.text}")
                        continue

                    twitter_data = response.json()
                    print(f"Twitter API data for tweet {posted_id}: {twitter_data}")
                    
                    # Create a map of author_id -> username
                    author_map = {
                        user["id"]: user["username"] 
                        for user in twitter_data.get("includes", {}).get("users", [])
                    }
                    
                    # Convert Twitter comments to CommentResponse objects
                    comment_list = []
                    for tweet in twitter_data.get("data", []):
                        author_id = tweet["author_id"]
                        comment_list.append(CommentResponse(
                            id=tweet["id"],
                            text=tweet["text"],
                            author_id=author_id,
                            created_at=tweet["created_at"],
                            username=author_map.get(author_id, "unknown_user")
                        ))
                    
                    # Create PostWithComments object
                    post_with_comments = PostWithComments(
                        id=post[0],
                        content=post[1],
                        user_id=post[2],
                        account_id=post[3],
                        status=post[4],
                        posted_id=post[5],
                        posted_time=post[6],
                        created_at=post[7],
                        comments=comment_list
                    )
                    result.append(post_with_comments)
                except Exception as e:
                    print(f"Error processing tweet {posted_id}: {str(e)}")
                    continue
            
            return result
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()
