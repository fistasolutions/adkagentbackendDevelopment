from fastapi import APIRouter, HTTPException
from models.tweet_models import EventTweetGenerationRequest, EventInsertRequest, EventAndPostResponse
from agent.event_tweet_agent import EventTweetAgent, EventTweetRequest, EventTweetResponse
from agent.event_based_tweet_agent import EventBasedTweetAgent, EventBasedTweetRequest
from db.db import get_connection

router = APIRouter()

@router.post("/generate-event-tweets", response_model=EventTweetResponse)
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
 
@router.post("/insert-event", response_model=EventAndPostResponse)
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