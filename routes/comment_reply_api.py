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

# Twitter API credentials
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

def get_twitter_auth():
    return OAuth1Session(
        TWITTER_API_KEY,
        client_secret=TWITTER_API_SECRET,
        resource_owner_key=TWITTER_ACCESS_TOKEN,
        resource_owner_secret=TWITTER_ACCESS_TOKEN_SECRET
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
            oauth = get_twitter_auth()
            
            for post in posts:
                posted_id = post[5]  # post[5] is posted_id
                if not posted_id:
                    continue

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
