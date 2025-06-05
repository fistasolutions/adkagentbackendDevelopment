import json
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from db.db import get_connection
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from agents import Agent, Runner
import calendar

router = APIRouter()

class PostingRequest(BaseModel):
    account_id: int
    user_id: int
    request: str  # User's main point or request
    chat_list: Optional[List[str]] = None  # Conversation history

class PostingRequestResponse(BaseModel):
    request_id: int
    created_at: datetime
    account_id: int
    user_id: int
    chat_list: List[str]
    main_point: str

# Define a new agent for temporary posting requests
posting_request_agent = Agent(
    name="Temporary Posting Request Agent",
    instructions="""
    You are a social media assistant specializing in handling temporary, one-time requests for post direction. 
    Your job is to understand the user's special instructions (such as themes, events, or temporary preferences) and respond in a natural, conversational way, confirming the request and asking any clarifying questions if needed. 
    Do not make permanent changes—these are for one-time or short-term use only. 
    Always be polite, clear, and helpful, and keep the conversation focused on the user's temporary needs for post generation.
    You talk is about the user's temporary requests related to the post content.
    You have to ask ask what type of post you want to create and if user mention it then you have to ask when did these post i have to add it then you have to ask for the end date of the post.

    If user mention the end date then you have to ask for the end date of the post.
    and canclode the converstasion
    Example:
    System:
    Do you have any temporary requests related to the post content?

User:
Since Valentine's Day is coming soon, please add more Valentine's-related content.

System:
Understood. Until when should we keep adding Valentine's posts?

User:
By 14th

System:
Understood. If you could save it, we will keep this setting until the 14th.


    
    """,
    output_type=str
)

@router.post("/temporary-posting-request", response_model=PostingRequestResponse)
async def temporary_posting_request(request: PostingRequest):
    """
    Handle a temporary posting request, chat with the Temporary Posting Request Agent, and store the request in posts_requests table.
    """
    chat_history = request.chat_list or []
    chat_history.append(request.request)
    main_point = request.request
    try:
        agent_input = f"User request: {main_point}\nConversation: {chat_history}"
        agent_result = await Runner.run(posting_request_agent, input=agent_input)
        # Optionally, you can use agent_result.final_output for further logic
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO posts_requests (created_at, account_id, user_id, chat_list, main_point)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING request_id, created_at
                """,
                (datetime.utcnow(), request.account_id, request.user_id, str(chat_history), main_point)
            )
            row = cursor.fetchone()
            conn.commit()
            return PostingRequestResponse(
                request_id=row[0],
                created_at=row[1],
                account_id=request.account_id,
                user_id=request.user_id,
                chat_list=chat_history,
                main_point=main_point
            )
    except Exception as db_error:
        raise HTTPException(status_code=500, detail=f"DB error: {str(db_error)}")
    finally:
        conn.close()

class PostingChatRequest(BaseModel):
    account_id: int
    user_id: int
    chat_list: List[str]  # Full conversation history, latest user message last

class PostingChatResponse(BaseModel):
    agent_reply: str
    chat_list: List[str]

@router.post("/temporary-posting-chat", response_model=PostingChatResponse)
async def temporary_posting_chat(request: PostingChatRequest):
    """
    Live chat with the Temporary Posting Request Agent. Returns the agent's reply, does not save to DB.
    """
    chat_history = request.chat_list
    try:
        agent_input = f"""You're an expert generating next reply/response of the conversation,reply must be according to previous chat.
        Generate the an reply text nothing else, no other text be part of of response.
        As chat is about generating textual tweets only, so don't mention about image, video or any graphic content. 
        Only give reply text according the concept of textual tweets only.
        Conversation: {chat_history}"""
        agent_result = await Runner.run(posting_request_agent, input=agent_input)
        agent_reply = agent_result.final_output if hasattr(agent_result, 'final_output') else str(agent_result)
        chat_history.append(agent_reply)
        return PostingChatResponse(agent_reply=agent_reply, chat_list=chat_history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

class PostingKeepRequest(BaseModel):
    account_id: int
    user_id: int
    chat_list: List[str]
    main_point: str

# Create a specialized agent for conversation summarization
summary_agent = Agent(
    name="Conversation Summary Agent",
    instructions="""
    You are an expert at summarizing conversations concisely.
    Your task is to analyze the conversation history and create a brief summary in 20 words or less.
    Focus on the main topic, key points, and any specific requests or preferences mentioned.
    Return only the summary text, nothing else.
    """,
    output_type=str
)

@router.post("/temporary-posting-request/keep", response_model=PostingRequestResponse)
async def temporary_posting_keep(request: PostingKeepRequest):
    """
    Generate a summary of the conversation, then save the chat history and summary to posts_requests table.
    """
    try:
        # Generate summary using the summary agent
        agent_input = f"Conversation history: {request.chat_list}"
        summary_result = await Runner.run(summary_agent, input=agent_input)
        summary = summary_result.final_output if hasattr(summary_result, 'final_output') else str(summary_result)
        
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO posts_requests (created_at, account_id, user_id, chat_list, main_point)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING request_id, created_at
                """,
                (datetime.utcnow(), request.account_id, request.user_id, json.dumps(request.chat_list), summary)
            )
            row = cursor.fetchone()
            conn.commit()
            return PostingRequestResponse(
                request_id=row[0],
                created_at=row[1],
                account_id=request.account_id,
                user_id=request.user_id,
                chat_list=request.chat_list,
                main_point=summary
            )
    except Exception as db_error:
        raise HTTPException(status_code=500, detail=f"DB error: {str(db_error)}")
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/temporary-posting-requests", response_model=List[PostingRequestResponse])
async def get_temporary_posting_requests(account_id: int = Query(...), user_id: int = Query(...)):
    """
    Fetch all posts_requests data for a given account_id and user_id.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT request_id, created_at, account_id, user_id, chat_list, main_point
                FROM posts_requests
                WHERE account_id = %s AND user_id = %s
                ORDER BY created_at DESC
                """,
                (account_id, user_id)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                # Parse chat_list from JSON string to Python list
                chat_list = row[4]
                if isinstance(chat_list, str):
                    try:
                        chat_list = json.loads(chat_list)
                    except Exception:
                        chat_list = []
                results.append(PostingRequestResponse(
                    request_id=row[0],
                    created_at=row[1],
                    account_id=row[2],
                    user_id=row[3],
                    chat_list=chat_list,
                    main_point=row[5]
                ))
            return results
    except Exception as db_error:
        raise HTTPException(status_code=500, detail=f"DB error: {str(db_error)}")
    finally:
        conn.close()

class PostingDeleteRequest(BaseModel):
    request_id: int

@router.delete("/temporary-posting-request/{request_id}")
async def delete_temporary_posting_request(request_id: int):
    """
    Delete a posts_requests entry by request_id.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM posts_requests WHERE request_id = %s RETURNING request_id
                """,
                (request_id,)
            )
            deleted = cursor.fetchone()
            conn.commit()
            if not deleted:
                raise HTTPException(status_code=404, detail="Request not found")
            return {"message": "Request deleted successfully", "request_id": deleted[0]}
    except Exception as db_error:
        raise HTTPException(status_code=500, detail=f"DB error: {str(db_error)}")
    finally:
        conn.close()

class TweetGenerationRequest(BaseModel):
    account_id: int
    user_id: int
    chat_list: List[str]

def get_next_occurrence_of_date(target_month: int, target_day: int) -> datetime:
    """Get the next occurrence of a specific date (month and day)"""
    today = datetime.utcnow()
    target_year = today.year
    
    # If the date has already passed this year, target next year
    if (today.month > target_month) or (today.month == target_month and today.day > target_day):
        target_year += 1
    
    return datetime(target_year, target_month, target_day)

def detect_special_date(text: str) -> Optional[Tuple[datetime, str]]:
    """Detect if the text mentions a special date and return the date and occasion"""
    text = text.lower()
    
    # Dictionary of special dates (month, day, occasion)
    special_dates = {
        # Western Holidays
        "valentine": (2, 14, "Valentine's Day"),
        "christmas": (12, 25, "Christmas"),
        "new year": (1, 1, "New Year's Day"),
        "halloween": (10, 31, "Halloween"),
        "thanksgiving": (11, 24, "Thanksgiving"),
        "independence day": (7, 4, "Independence Day"),
        "mother's day": (5, 12, "Mother's Day"),
        "father's day": (6, 16, "Father's Day"),
        "easter": (3, 31, "Easter"),
        "black friday": (11, 29, "Black Friday"),
        "cyber monday": (12, 2, "Cyber Monday"),
        
        # Asian Holidays
        "chinese new year": (2, 10, "Chinese New Year"),  # 2024 date
        "lunar new year": (2, 10, "Lunar New Year"),
        "diwali": (11, 12, "Diwali"),  # 2024 date
        "holi": (3, 25, "Holi"),  # 2024 date
        "ramadan": (3, 10, "Ramadan"),  # 2024 start date
        "eid al-fitr": (4, 10, "Eid al-Fitr"),  # 2024 date
        "eid al-adha": (6, 17, "Eid al-Adha"),  # 2024 date
        
        # Japanese Holidays
        "golden week": (4, 29, "Golden Week"),
        "obon": (8, 13, "Obon Festival"),
        "tanabata": (7, 7, "Tanabata Festival"),
        "children's day": (5, 5, "Children's Day"),
        "coming of age day": (1, 8, "Coming of Age Day"),
        
        # Korean Holidays
        "chuseok": (9, 17, "Chuseok"),  # 2024 date
        "seollal": (2, 10, "Seollal"),  # 2024 date
        
        # Indian Holidays
        "rakhi": (8, 19, "Raksha Bandhan"),  # 2024 date
        "ganesh chaturthi": (9, 7, "Ganesh Chaturthi"),  # 2024 date
        "dussehra": (10, 12, "Dussehra"),  # 2024 date
        
        # Middle Eastern Holidays
        "mawlid": (9, 16, "Mawlid al-Nabi"),  # 2024 date
        "ashura": (7, 17, "Ashura"),  # 2024 date
        
        # European Holidays
        "carnival": (2, 13, "Carnival"),  # 2024 date
        "oktoberfest": (9, 21, "Oktoberfest"),  # 2024 date
        "bastille day": (7, 14, "Bastille Day"),
        
        # Latin American Holidays
        "day of the dead": (11, 2, "Day of the Dead"),
        "carnival of rio": (2, 13, "Carnival of Rio"),  # 2024 date
        
        # African Holidays
        "kwanzaa": (12, 26, "Kwanzaa"),
        "africa day": (5, 25, "Africa Day"),
        
        # Business/Professional Events
        "world cup": (6, 14, "World Cup"),  # 2024 date
        "olympics": (7, 26, "Olympics"),  # 2024 date
        "super bowl": (2, 11, "Super Bowl"),  # 2024 date
        "comic con": (7, 25, "Comic Con"),  # 2024 date
        "ces": (1, 9, "CES"),  # 2024 date
        "e3": (6, 11, "E3"),  # 2024 date
        
        # Tech Industry Events
        "apple event": (9, 10, "Apple Event"),  # Typical September event
        "google io": (5, 14, "Google I/O"),  # 2024 date
        "microsoft build": (5, 21, "Microsoft Build"),  # 2024 date
        
        # Seasonal Events
        "summer solstice": (6, 21, "Summer Solstice"),
        "winter solstice": (12, 21, "Winter Solstice"),
        "spring equinox": (3, 20, "Spring Equinox"),
        "autumn equinox": (9, 22, "Autumn Equinox"),
        
        # Awareness Days
        "world health day": (4, 7, "World Health Day"),
        "earth day": (4, 22, "Earth Day"),
        "world environment day": (6, 5, "World Environment Day"),
        "international women's day": (3, 8, "International Women's Day"),
        "pride month": (6, 1, "Pride Month"),
        "black history month": (2, 1, "Black History Month"),
        "asian heritage month": (5, 1, "Asian Heritage Month"),
        "hispanic heritage month": (9, 15, "Hispanic Heritage Month")
    }
    
    for keyword, (month, day, occasion) in special_dates.items():
        if keyword in text:
            return get_next_occurrence_of_date(month, day), occasion
    
    return None

def get_optimal_posting_time() -> datetime:
    """Get the optimal posting time (between 9 AM and 5 PM)"""
    now = datetime.utcnow()
    optimal_time = now.replace(hour=12, minute=0, second=0, microsecond=0)  # Default to noon
    
    # If current time is past 5 PM, schedule for next day
    if now.hour >= 17:
        optimal_time += timedelta(days=1)
    
    return optimal_time

# Create a specialized agent for date detection
date_detection_agent = Agent(
    name="Date Detection Agent",
    instructions="""
    You are an expert at analyzing conversations to identify special dates, holidays, and events.
    Your task is to analyze the conversation and identify any special dates or events being discussed.
    Consider:
    1. Explicit mentions of dates or events
    2. Contextual clues about upcoming events
    3. Cultural and international holidays
    4. Business events and seasons
    5. Awareness days and months
    
    Return your response in this format:
    {
        "detected_date": true/false,
        "date_type": "holiday/event/season/awareness",
        "name": "name of the date/event",
        "month": month number (1-12),
        "day": day number (1-31),
        "confidence": "high/medium/low",
        "context": "brief explanation of why you detected this date"
    }
    If no date is detected, return:
    {
        "detected_date": false,
        "context": "brief explanation of why no date was detected"
    }
    """,
    output_type=dict
)

@router.post("/generate-and-post-tweet", response_model=PostingRequestResponse)
async def generate_and_post_tweet(request: TweetGenerationRequest):
    """
    Generate and schedule a tweet based on the chat history with the AI agent.
    """
    try:
        # First, get the character settings for the account
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT character_settings 
                FROM personas 
                WHERE account_id = %s
                """,
                (request.account_id,)
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail="Character settings not found for this account. Please set up character settings first."
                )
            character_settings = result[0]

        # Analyze chat history for date detection
        date_detection_input = f"Conversation history: {request.chat_list}"
        date_detection_result = await Runner.run(date_detection_agent, input=date_detection_input)
        date_info = date_detection_result.final_output if hasattr(date_detection_result, 'final_output') else date_detection_result

        # Create a specialized agent for tweet generation
        tweet_agent = Agent(
            name="Tweet Generation Agent",
            instructions=f"""
            You are a social media expert specializing in creating engaging tweets.
            Your task is to analyze the conversation history and create a compelling tweet.
            The tweet should be:
            1. Engaging and conversational
            2. Under 280 characters
            3. Include relevant hashtags if appropriate
            4. Maintain the brand voice from these character settings: {character_settings}
            5. If a special date or event was detected ({date_info.get('name', 'none')}), incorporate it naturally
            
            Format your response as a single tweet text.
            """,
            output_type=str
        )

        # Generate the tweet using the agent
        agent_input = f"Conversation history: {request.chat_list}"
        agent_result = await Runner.run(tweet_agent, input=agent_input)
        tweet_content = agent_result.final_output if hasattr(agent_result, 'final_output') else str(agent_result)

        # Determine the best posting time based on detected date
        if date_info.get('detected_date', False) and date_info.get('confidence', 'low') in ['high', 'medium']:
            scheduled_time = get_next_occurrence_of_date(date_info['month'], date_info['day'])
            # Add hashtag if not already present
            if not f"#{date_info['name'].replace(' ', '')}" in tweet_content.lower():
                tweet_content = f"{tweet_content} #Happy{date_info['name'].replace(' ', '')}"
        else:
            scheduled_time = get_optimal_posting_time()

        # Save the tweet to the database with scheduled time
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO posts (content, created_at, user_id, account_id, status, scheduled_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (tweet_content, datetime.utcnow(), request.user_id, request.account_id, "unposted", scheduled_time)
            )
            row = cursor.fetchone()
            conn.commit()

            return PostingRequestResponse(
                request_id=row[0],
                created_at=row[1],
                account_id=request.account_id,
                user_id=request.user_id,
                chat_list=request.chat_list
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating and scheduling tweet: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()


