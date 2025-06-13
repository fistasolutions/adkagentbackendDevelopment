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
        request (EventTweetGenerationRequest): The request containing the number of drafts needed, prompt, optional date, and optional event_id
        
    Returns:
        EventTweetResponse: The generated draft tweets
    """
    try:
        # If event_id is provided, fetch event data
        event_data = None
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
        agent = EventTweetAgent()
        
        # Create base request
        tweet_request = EventTweetRequest(
            num_drafts=request.num_drafts,
            prompt=request.prompt,
            date=request.date,
            character_settings=character_settings[0] if character_settings else None
        )
        
        response = await agent.get_response(tweet_request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@router.post("/insert-event", response_model=dict)
async def insert_event(request: EventInsertRequest):
    """
    Insert a new event into the events table.
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
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close() 
