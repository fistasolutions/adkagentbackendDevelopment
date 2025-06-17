from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict
import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from agent.risk_assessment_agent import RiskAssessmentAgent, RiskAssessmentRequest
from db.db import get_connection
import json
from datetime import datetime, timedelta
from datetime import datetime, timedelta
from agent.reply_generation_agent import generate_reply, ReplyGenerationRequest
from requests_oauthlib import OAuth1Session
from agent.draft_post_comment_agent import DraftPostCommentAgent, DraftPostCommentRequest, DraftPostCommentResponse



class DraftPostCommentRequestPost(BaseModel):
    previous_comment: str
    num_drafts: int
    prompt: Optional[str] = None
    character_settings: Optional[str] = None
    user_id: int
    account_id: str


load_dotenv()

# Twitter API credentials
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

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
class TweetImageUpdateRequest(BaseModel):
    tweet_id: str
    image_urls: List[str]
    
class HashtagsResponse(BaseModel):
    results: List[HashtagResponse]

class HashtagRequest(BaseModel):
    hashtags: List[str]  # List of hashtags
class DeleteTweetImageRequest(BaseModel):
    tweet_id: str
    image_urls: List[str]
    
class TweetUpdateRequest(BaseModel):
    tweet_id: str
    content: Optional[str] = None
    scheduled_time: Optional[str] = None   
    
    
 
def get_next_scheduled_times(posting_days: dict, posting_time: dict, posting_frequency: int, pre_create: int) -> List[str]:
    """
    Generate a list of scheduled times for posts based on the given parameters.
    
    Args:
        posting_days: Dict mapping days to boolean values (e.g., {"月": True, "火": False, ...})
        posting_time: Dict mapping hours to boolean values (e.g., {"0": True, "1": False, ...})
        posting_frequency: Number of posts per day
        pre_create: Number of days in advance to schedule posts
    
    Returns:
        List of ISO format datetime strings for scheduled posts
    """
    # Map Japanese day names to weekday numbers (0 = Monday, 6 = Sunday)
    day_mapping = {
        "月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6
    }
    
    # Get current time in UTC
    current_time = datetime.utcnow()
    
    # Get enabled days (days marked as True)
    enabled_days = [day for day, enabled in posting_days.items() if enabled]
    if not enabled_days:
        raise ValueError("No posting days are enabled")
    
    # Get enabled hours (hours marked as True)
    enabled_hours = [int(hour) for hour, enabled in posting_time.items() if enabled]
    if not enabled_hours:
        raise ValueError("No posting hours are enabled")
    
    # Sort enabled hours
    enabled_hours.sort()
    
    # Calculate total number of posts needed
    total_posts = posting_frequency * pre_create
    scheduled_times = []
    current_date = current_time.date()
    
    while len(scheduled_times) < total_posts:
        # Check if current day is enabled
        current_day_jp = ["月", "火", "水", "木", "金", "土", "日"][current_date.weekday()]
        
        if current_day_jp in enabled_days:
            # For each enabled hour on this day
            for hour in enabled_hours:
                # Create datetime for this hour
                post_time = datetime.combine(current_date, datetime.min.time().replace(hour=hour))
                
                # Only add if it's in the future
                if post_time > current_time:
                    scheduled_times.append(post_time.isoformat() + "Z")
                    
                    # If we have enough posts for today, break
                    if len([t for t in scheduled_times if t.startswith(current_date.isoformat())]) >= posting_frequency:
                        break
        
        # Move to next day
        current_date += timedelta(days=1)
    
    # Sort and return the scheduled times
    return sorted(scheduled_times)[:total_posts]
   
    
def fetch_tweets_for_hashtag(hashtag: str, max_results: int = 10) -> List[dict]:
    """Fetch tweets for a single hashtag using X API."""
    try:
        print("max_results", max_results)
        headers = {
            'Authorization': f'Bearer {X_BEARER_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        url = "https://api.twitter.com/2/tweets/search/recent"
        params = {
            'query': f"#{hashtag}",
            'max_results': max_results,
            'tweet.fields': 'created_at,public_metrics',
            'user.fields': 'name,username,profile_image_url',
            'expansions': 'author_id'
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching tweets for #{hashtag}: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        tweet_list = []
        
        if 'data' in data and 'includes' in data and 'users' in data['includes']:
            users = {user['id']: user for user in data['includes']['users']}
            
            for tweet in data['data']:
                try:
                    user = users.get(tweet['author_id'])
                    if not user:
                        continue
                        
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
                except Exception as e:
                    print(f"Error processing tweet for #{hashtag}: {str(e)}")
                    continue
        
        return tweet_list
    except Exception as e:
        print(f"Unexpected error in fetch_tweets_for_hashtag for #{hashtag}: {str(e)}")
        return []

def parse_frequency_string(freq_str: str) -> int:
    """Parse frequency string like '10day' or '1日' to get the numeric value."""
    if not freq_str:
        return 1
    
    # Remove any non-numeric characters from the start
    numeric_part = ''
    for char in freq_str:
        if char.isdigit():
            numeric_part += char
        else:
            break
    
    return int(numeric_part) if numeric_part else 1

@router.get("/cron/fetch-hashtag-tweets")
async def cron_fetch_hashtag_tweets():
    """Cron job endpoint to fetch tweets for all accounts with postReply notifications."""
    conn = None
    try:
        conn = get_connection()
        results = []
        
        with conn.cursor() as cursor:
            try:
                # Get all twitter accounts with their user_ids
                cursor.execute("""
                    SELECT ta.account_id, ta.user_id 
                    FROM twitter_account ta
                    INNER JOIN persona_notify pn ON ta.account_id = pn.account_id 
                    WHERE pn.notify_type = 'postReply'
                """)
                accounts = cursor.fetchall()
            except Exception as e:
                print(f"Error fetching accounts: {str(e)}")
                return {'results': [], 'message': 'Error fetching accounts'}
            
            for account_id, user_id in accounts:
                try:
                    # First check if we already have data for today
                    cursor.execute("""
                        SELECT COUNT(*) FROM post_for_reply
                        WHERE account_id = %s 
                        AND DATE(created_at) = %s
                    """, (account_id, datetime.utcnow().date()))
                    
                    if cursor.fetchone()[0] > 0:
                        print(f"Skipping account {account_id} - already has data for today")
                        continue

                    # Get character settings for this account
                    cursor.execute("""
                        SELECT character_settings 
                        FROM personas 
                        WHERE user_id = %s 
                        AND account_id = %s
                    """, (user_id, account_id))
                    character_settings = cursor.fetchone()
                    
                    if not character_settings:
                        print(f"No character settings found for account {account_id}")
                        continue

                    # Get target hashtags for this account
                    cursor.execute("""
                        SELECT target_hashtag, posting_frequency, pre_create,template_use,template_text,posting_day,posting_time,post_mode
                        FROM persona_notify 
                        WHERE account_id = %s 
                        AND user_id = %s 
                        AND notify_type = 'postReply'
                    """, (account_id, user_id))
                    
                    hashtag_result = cursor.fetchone()
                    if not hashtag_result or not hashtag_result[0]:
                        print(f"No hashtags found for account {account_id}")
                        continue
                    
                    try:
                        hashtags = json.loads(hashtag_result[0])
                        posting_frequency = parse_frequency_string(hashtag_result[1])
                        pre_create = parse_frequency_string(hashtag_result[2])
                        template_use = hashtag_result[3]
                        template_text = hashtag_result[4]
                        # Handle posting_day - check if it's already a dict
                        posting_day = hashtag_result[5]
                        if isinstance(posting_day, str):
                            posting_day = json.loads(posting_day)
                        # Handle posting_time - check if it's already a dict
                        posting_time = hashtag_result[6]
                        if isinstance(posting_time, str):
                            posting_time = json.loads(posting_time)
                        post_mode = hashtag_result[7]
                        if not hashtags:
                            print(f"Empty hashtags list for account {account_id}")
                            continue
                            
                        # Calculate total tweets needed and distribute across hashtags
                        total_tweets_needed = posting_frequency * pre_create
                        
                        # Get scheduled times for all tweets
                        scheduled_times = get_next_scheduled_times(
                            posting_day,
                            posting_time,
                            posting_frequency,
                            pre_create
                        )
                        print("scheduled_times",scheduled_times)
                        # Ensure we fetch at least 10 tweets per hashtag (Twitter API requirement)
                        min_tweets_per_hashtag = 10
                        tweets_per_hashtag = max(min_tweets_per_hashtag, total_tweets_needed // len(hashtags))
                        remaining_tweets = total_tweets_needed % len(hashtags)
                        
                        all_tweets = []
                        for i, hashtag in enumerate(hashtags):
                            try:
                                hashtag_value = hashtag.lstrip('#')
                                
                                # Calculate tweets needed for this hashtag
                                # Distribute remaining tweets to first few hashtags
                                current_hashtag_tweets = tweets_per_hashtag + (1 if i < remaining_tweets else 0)
                                
                                # Ensure we fetch at least 10 tweets (Twitter API requirement)
                                fetch_count = max(min_tweets_per_hashtag, current_hashtag_tweets)
                                
                                print(f"Fetching {fetch_count} tweets for #{hashtag_value}")
                                tweet_list = fetch_tweets_for_hashtag(hashtag_value, max_results=fetch_count)
                                
                                if tweet_list:
                                    # If we fetched more tweets than needed, randomly select the required number
                                    if len(tweet_list) > current_hashtag_tweets:
                                        import random
                                        tweet_list = random.sample(tweet_list, current_hashtag_tweets)
                                    all_tweets.extend(tweet_list)
                                
                            except Exception as e:
                                print(f"Error processing hashtag {hashtag}: {str(e)}")
                                continue
                        
                        if not all_tweets:
                            print(f"No tweets found for any hashtags")
                            continue 

                        # Ensure we have the exact number of tweets needed
                        if len(all_tweets) > total_tweets_needed:
                            import random
                            all_tweets = random.sample(all_tweets, total_tweets_needed)

                        try:
                            cursor.execute("""
                                INSERT INTO post_data (created_at, update_at, data_json, user_id)
                                VALUES (%s, %s, %s, %s)
                            """, (
                                datetime.utcnow(),
                                datetime.utcnow(),
                                json.dumps({
                                    'hashtags': [h.lstrip('#') for h in hashtags],
                                    'tweet_count': len(all_tweets),
                                    'tweets': all_tweets,
                                    'account_id': account_id
                                }),
                                user_id
                            ))

                            for tweet_index, tweet in enumerate(all_tweets):
                                try:
                                    # Generate reply using the reply generation agent
                                    reply_request = ReplyGenerationRequest(
                                        tweet_id=tweet['id'],
                                        tweet_text=tweet['text'],
                                        post_username=tweet['user']['screen_name'],
                                        character_settings=character_settings[0],
                                        posting_frequency=posting_frequency,
                                        pre_create=pre_create,
                                        template_use=template_use,
                                        template_text=template_text,
                                        posting_day=posting_day,
                                        posting_time=posting_time
                                    )
                                    
                                    reply = await generate_reply(reply_request)
                                    
                                    # Get scheduled time for this tweet
                                    scheduled_time = scheduled_times[i] if i < len(scheduled_times) else None
                                    
                                    cursor.execute("""
                                        INSERT INTO post_for_reply (
                                            created_at, 
                                            tweet_id, 
                                            text, 
                                            post_username, 
                                            account_id, 
                                            user_id,
                                            reply_text,
                                            risk_score,
                                            schedule_time,
                                            author_profile,
                                            recommended_time
                                        )
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        datetime.utcnow(),
                                        tweet['id'],
                                        tweet['text'],
                                        tweet['user']['screen_name'],
                                        account_id,
                                        user_id,
                                        reply.reply_text,
                                        reply.risk_score,
                                        scheduled_times[tweet_index] if str(post_mode).upper() == "TRUE" else None,
                                        tweet['user']['profile_image_url']
                                    ))
                                except Exception as e:
                                    print(f"Error processing tweet {tweet['id']}: {str(e)}")
                                    continue

                            results.append({
                                'account_id': account_id,
                                'user_id': user_id,
                                'hashtags': [h.lstrip('#') for h in hashtags],
                                'tweet_count': len(all_tweets)
                            })
                        except Exception as e:
                            print(f"Error saving data for hashtags: {str(e)}")
                            continue

                    except json.JSONDecodeError as e:
                        print(f"Error parsing hashtags for account {account_id}: {str(e)}")
                        continue
                    except Exception as e:
                        print(f"Error processing account {account_id}: {str(e)}")
                        continue
                        
                except Exception as e:
                    print(f"Error processing account {account_id}: {str(e)}")
                    continue
                
        if conn:
            conn.commit()
        return {'results': results, 'message': 'Successfully processed accounts'}
        
    except Exception as e:
        print(f"Unexpected error in cron_fetch_hashtag_tweets: {str(e)}")
        return {'results': [], 'message': f'Error: {str(e)}'}
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                print(f"Error closing connection: {str(e)}")

@router.get("/cron/post-scheduled-replies")
async def post_scheduled_replies():
    """Cron job endpoint to post scheduled replies to Twitter."""
    conn = None
    try:
        conn = get_connection()
        results = []
        
        with conn.cursor() as cursor:
            # Get all unposted replies where schedule time has passed
            cursor.execute("""
                SELECT pr.id, pr.tweet_id, pr.reply_text, pr.account_id
                FROM post_for_reply pr
                WHERE pr.post_status = 'unposted'
                AND pr.schedule_time <= %s
            """, (datetime.utcnow(),))
            
            scheduled_replies = cursor.fetchall()
            
            for reply_id, tweet_id, reply_text, account_id in scheduled_replies:
                try:
                    # Create OAuth 1.0a session
                    oauth = OAuth1Session(
                        TWITTER_API_KEY,
                        client_secret=TWITTER_API_SECRET,
                        resource_owner_key=TWITTER_ACCESS_TOKEN,
                        resource_owner_secret=TWITTER_ACCESS_TOKEN_SECRET
                    )
                    
                    # Prepare the request
                    url = "https://api.twitter.com/2/tweets"
                    data = {
                        "text": reply_text,
                        "reply": {
                            "in_reply_to_tweet_id": tweet_id
                        }
                    }
                    
                    # Post the reply
                    reply_response = oauth.post(
                        url,
                        json=data
                    )
                    
                    if reply_response.status_code == 201:
                        response_data = reply_response.json()
                        posted_id = response_data.get('data', {}).get('id')
                        
                        # Update the database to mark as posted
                        cursor.execute("""
                            UPDATE post_for_reply
                            SET post_status = 'posted',
                                posted_id = %s
                            WHERE id = %s
                        """, (posted_id, reply_id))
                        
                        results.append({
                            'reply_id': reply_id,
                            'tweet_id': tweet_id,
                            'status': 'success'
                        })
                    else:
                        print(f"Error posting reply for tweet {tweet_id}: {reply_response.status_code}")
                        results.append({
                            'reply_id': reply_id,
                            'tweet_id': tweet_id,
                            'status': 'error',
                            'error': reply_response.text
                        })
                        
                except Exception as e:
                    print(f"Error processing reply {reply_id}: {str(e)}")
                    results.append({
                        'reply_id': reply_id,
                        'tweet_id': tweet_id,
                        'status': 'error',
                        'error': str(e)
                    })
                    continue
        
        if conn:
            conn.commit()
        return {'results': results, 'message': 'Successfully processed scheduled replies'}
        
    except Exception as e:
        print(f"Unexpected error in post_scheduled_replies: {str(e)}")
        return {'results': [], 'message': f'Error: {str(e)}'}
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                print(f"Error closing connection: {str(e)}")


@router.put("/update-post-comment-image")
async def update_tweet_image(request:TweetImageUpdateRequest):
    """Append new image URLs to a tweet, avoiding duplicates."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # First check if the tweet exists and get current images
                cursor.execute(
                    """
                    SELECT id, image_urls
                    FROM post_for_reply 
                    WHERE id = %s
                    """,
                    (request.tweet_id,),
                )
                tweet = cursor.fetchone()

                if not tweet:
                    raise HTTPException(status_code=404, detail="Tweet not found")

                current_images = tweet[1]
                if current_images:
                    try:
                        if isinstance(current_images, str):
                            current_images = json.loads(current_images)
                    except Exception:
                        current_images = []
                else:
                    current_images = []

                # Append new images, avoiding duplicates
                updated_images = list(dict.fromkeys(current_images + request.image_urls))

                # Update the image URLs (as JSONB)
                cursor.execute(
                    """
                    UPDATE post_for_reply 
                    SET image_urls = %s
                    WHERE id = %s
                    RETURNING id, image_urls
                    """,
                    (json.dumps(updated_images), request.tweet_id),
                )
                updated_tweet = cursor.fetchone()

                conn.commit()

                return {
                    "message": "Tweet images updated successfully",
                    "tweet": {
                        "id": updated_tweet[0],
                        "image_urls": updated_tweet[1],
                    },
                }

        except HTTPException as he:
            raise he
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update tweet images: {str(db_error)}"
            )
        finally:
            conn.close()

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating tweet images: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update tweet images: {str(e)}")
    
    
    
@router.delete("/delete-post-comment-image")
async def delete_post_comment_image(request: DeleteTweetImageRequest):
    """Delete specific image URLs from a tweet's Image_url field."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # First check if the tweet exists and get current images
                cursor.execute(
                    """
                    SELECT id, image_urls
                    FROM post_for_reply 
                    WHERE id = %s
                    """,
                    (request.tweet_id,),
                )
                tweet = cursor.fetchone()

                if not tweet:
                    raise HTTPException(status_code=404, detail="Tweet not found")

                current_images = tweet[1]
                if current_images:
                    try:
                        if isinstance(current_images, str):
                            current_images = json.loads(current_images)
                    except Exception:
                        current_images = []
                else:
                    current_images = []

                # Remove the specified image URLs
                updated_images = [url for url in current_images if url not in request.image_urls]

                # Update the image URLs (as JSONB)
                cursor.execute(
                    """
                    UPDATE post_for_reply 
                    SET image_urls = %s
                    WHERE id = %s
                    RETURNING id, image_urls
                    """,
                    (json.dumps(updated_images), request.tweet_id),
                )
                updated_tweet = cursor.fetchone()

                conn.commit()

                return {
                    "message": "Tweet images deleted successfully",
                    "tweet": {
                        "id": updated_tweet[0],
                        "image_urls": updated_tweet[1],
                    },
                }

        except HTTPException as he:
            raise he
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to delete tweet images: {str(db_error)}"
            )
        finally:
            conn.close()

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error deleting tweet images: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete tweet images: {str(e)}")



@router.put("/update-post-comment")
async def update_post_comment(request: TweetUpdateRequest):
    """Update the content or scheduled time of a tweet."""
    try:
        if not request.content and not request.scheduled_time:
            raise HTTPException(
                status_code=400,
                detail="At least one of content or scheduled_time must be provided",
            )

        # Perform risk assessment if content is being updated
        risk_assessment = None
        if request.content:
            risk_agent = RiskAssessmentAgent()
            risk_assessment = await risk_agent.get_response(RiskAssessmentRequest(content=request.content))
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM post_for_reply 
                    WHERE id = %s
                    """,
                    (request.tweet_id,),
                )
                tweet = cursor.fetchone()

                if not tweet:
                    raise HTTPException(status_code=404, detail="Tweet not found")

                # Prepare the update query based on provided fields
                update_fields = []
                update_values = []

                if request.content:
                    update_fields.append("reply_text = %s")
                    update_values.append(request.content)
                    if risk_assessment:
                        update_fields.append("risk_score = %s")
                        update_values.append(risk_assessment.overall_risk_score)
                    if risk_assessment:
                        update_fields.append("risk_assesments = %s")
                        risk_assessment_json = json.dumps({
                            "risk_categories": [category.dict() for category in risk_assessment.risk_categories],
                            "risk_assignment": risk_assessment.risk_assignment
                        })
                        update_values.append(risk_assessment_json)

                if request.scheduled_time:
                    try:
                        update_fields.append("schedule_time = %s")
                        update_values.append(request.scheduled_time)
                    except ValueError:
                        raise HTTPException(
                            status_code=400,
                            detail="Invalid scheduled_time format. Use ISO format: YYYY-MM-DDTHH:MM:SSZ",
                        )

                # Add tweet_id to the values list
                update_values.append(request.tweet_id)

                # Construct and execute the update query
                update_query = f"""
                    UPDATE post_for_reply 
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                    RETURNING id, reply_text, schedule_time, risk_score
                """

                cursor.execute(update_query, update_values)
                updated_tweet = cursor.fetchone()

                conn.commit()

                response = {
                    "message": "Tweet updated successfully",
                    "tweet": {
                        "id": updated_tweet[0],
                        "content": updated_tweet[1],
                        "schedule_time": updated_tweet[2],
                        "risk_score": updated_tweet[3]
                    }
                }

                return response

        except HTTPException as he:
            raise he
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update tweet: {str(db_error)}"
            )
        finally:
            conn.close()

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating tweet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update tweet: {str(e)}")
    
    
@router.post("/generate-post-comment", response_model=DraftPostCommentResponse)
async def generate_post_comment(request: DraftPostCommentRequestPost):
    """
    Generate draft comments based on previous comments and prompt.
    
    Args:
        request (DraftPostCommentRequest): The request containing the number of drafts needed, prompt, user_id, account_id, and optional character settings
        
    Returns:
        DraftPostCommentResponse: The generated draft tweets
    """
    try:
        # If event_id is provided, fetch event data
        post_comment_data = None
        character_settings = None
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Fetch character settings
                cursor.execute("""
                    SELECT character_settings 
                    FROM personas 
                    WHERE user_id = %s 
                    AND account_id = %s
                """, (request.user_id, request.account_id))
                character_settings = cursor.fetchone()
                
                if not character_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="Character settings not found. Please set up your character settings before generating tweets."
                    )
                
        finally:
            conn.close()

        # Initialize agent with event data if available
        agent = DraftPostCommentAgent()
        
        # Create base request for the agent
        agent_request = DraftPostCommentRequest(
            num_drafts=request.num_drafts,
            prompt=request.prompt,
            previous_comment=request.previous_comment,
            character_settings=character_settings[0] if character_settings else None
        )
        
        response = await agent.get_response(agent_request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
    
    

class DraftPostCommentResponse(BaseModel):
    draft_tweets: List[str]
 
    
    
