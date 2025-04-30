from fastapi import APIRouter, HTTPException, Depends, Response
from db.db import get_connection
from models import UserCreate, UserResponse
from typing import List
from pydantic import BaseModel
import bcrypt
import random
from utils.jwt import create_access_token
import requests
from requests_oauthlib import OAuth1
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

class UserUpdate(BaseModel):
    fullname: str | None = None
    email: str | None = None
    password: str | None = None

class LoginRequest(BaseModel):
    rememberMe: bool
    enterprise_id: str
    email: str
    password: str

class LoginResponse(BaseModel):
    user_id: int
    fullname: str
    email: str
    enterprise_id: str
    message: str

class TweetRequest(BaseModel):
    text: str
    post_id: str

# Twitter API credentials
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

@router.post("/post_tweet")
async def post_tweet(tweet: TweetRequest):
    try:
        # OAuth 1.0a authentication
        auth = OAuth1(
            TWITTER_API_KEY,
            TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_TOKEN_SECRET
        )

        # Twitter API endpoint
        url = "https://api.twitter.com/2/tweets"
        
        # Request payload
        payload = {
            "text": tweet.text
        }

        # Make the request
        response = requests.post(
            url,
            auth=auth,
            json=payload
        )

        # Check if the request was successful
        if response.status_code == 201:
            # Update post status in database
            tweet_id = response.json()["data"]["id"]
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE posts 
                        SET status = 'posted', 
                            posted_time = NOW(),
                            posted_id = %s
                        WHERE id = %s
                        RETURNING id, status, posted_time, posted_id
                        """,
                        (tweet_id, tweet.post_id)
                    )
                    updated_post = cursor.fetchone()
                    conn.commit()
                    
                    return {
                        "status": "success", 
                        "tweet": response.json(),
                        "post": {
                            "id": updated_post[0],
                            "status": updated_post[1],
                            "posted_time": updated_post[2],
                            "posted_id": updated_post[3]
                        }
                    }
            except Exception as db_error:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update post status: {str(db_error)}"
                )
            finally:
                conn.close()
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to post tweet: {response.text}"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error posting tweet: {str(e)}"
        )


    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, fullname, email, enterprise_id FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return {"user_id": user[0], "fullname": user[1], "email": user[2], "enterprise_id": user[3]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if user exists
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
            
            # Hash the password
            hashed_password = bcrypt.hashpw(user_update.password.encode('utf-8'), bcrypt.gensalt())
            
            # Build update query dynamically based on provided fields
            update_fields = []
            values = []
            if user_update.fullname is not None:
                update_fields.append("fullname = %s")
                values.append(user_update.fullname)
            if user_update.email is not None:
                update_fields.append("email = %s")
                values.append(user_update.email)
            if user_update.password is not None:
                update_fields.append("password = %s")
                values.append(hashed_password.decode('utf-8'))
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            # Add user_id to values
            values.append(user_id)
            
            # Execute update
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = %s RETURNING user_id, fullname, email"
            cursor.execute(query, values)
            updated_user = cursor.fetchone()
            conn.commit()
            
            return {
                "user_id": updated_user[0],
                "fullname": updated_user[1],
                "email": updated_user[2]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()