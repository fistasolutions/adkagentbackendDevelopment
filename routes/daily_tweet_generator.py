from typing import Dict, List, Optional, Any
from agents import Agent, Runner, function_tool
from pydantic import BaseModel, validator
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pydantic_settings import BaseSettings
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import random
import logging
from fastapi import APIRouter, HTTPException, Depends, Response
from db.db import get_connection
import json
from agent.risk_assessment_agent import RiskAssessmentAgent, RiskAssessmentRequest
from collections import Counter

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


router = APIRouter()


class TweetOutput(BaseModel):
    tweet: str
    hashtags: List[str]
    risk_score: float
    reach_estimate: int
    engagement_potential: float
    scheduled_time: str


class TweetsOutput(BaseModel):
    tweets: List[TweetOutput]
    total_risk_score: float
    average_reach_estimate: float
    overall_engagement_potential: float

    @validator('tweets')
    def validate_tweets_count(cls, v, values, **kwargs):
        # Remove the validation that limits tweets to 5
        return v


class AnalysisOutput(BaseModel):
    insights: List[str]
    recommendations: List[str]
    patterns: Dict[str, Any]
    metrics: Dict[str, float]


class SentimentAnalysisOutput(BaseModel):
    sentiment_score: float
    confidence: float


class ContentSafetyOutput(BaseModel):
    is_safe: bool
    risk_level: str


class CharacterConsistencyOutput(BaseModel):
    consistency_score: float
    areas_of_improvement: List[str]
    strengths: List[str]


class SpeechPatternsOutput(BaseModel):
    speech_style: str
    common_phrases: List[str]
    tone_markers: List[str]

    model_config = {"json_schema_extra": {"additionalProperties": False}}


class TweetRequest(BaseModel):
    user_id: str
    account_id: str


class TweetUpdateRequest(BaseModel):
    tweet_id: str
    content: Optional[str] = None
    scheduled_time: Optional[str] = None


class TweetImageUpdateRequest(BaseModel):
    tweet_id: str
    image_urls: List[str]


class DeleteTweetRequest(BaseModel):
    tweet_id: str


class DeleteTweetImageRequest(BaseModel):
    tweet_id: str
    image_urls: List[str]


async def get_events(
    user_id: str, 
    account_id: str, 
    limit: int = 10
) -> List[dict]:
    """Get upcoming events for a user and account."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT event_title, event_details, event_datetime
                FROM events 
                WHERE user_id = %s 
                AND account_id = %s 
                AND event_datetime > NOW()
                AND status = 'active'
                ORDER BY event_datetime ASC 
                LIMIT %s
                """,
                (user_id, account_id, limit),
            )
            events = [
                {
                    "title": row[0],
                    "details": row[1],
                    "datetime": row[2].strftime("%Y-%m-%dT%H:%M:%SZ")
                }
                for row in cursor.fetchall()
            ]
            return events
    finally:
        conn.close()

async def get_post_requests(
    user_id: str, 
    account_id: str, 
    limit: int = 10
) -> List[dict]:
    """Get post requests for a user and account."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT request_id, chat_list, main_point, created_at
                FROM posts_requests 
                WHERE user_id = %s 
                AND account_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
                """,
                (user_id, account_id, limit),
            )
            post_requests = [
                {
                    "request_id": row[0],
                    "chat_list": row[1],
                    "main_point": row[2],
                    "created_at": row[3].strftime("%Y-%m-%dT%H:%M:%SZ")
                }
                for row in cursor.fetchall()
            ]
            return post_requests
    finally:
        conn.close()

def get_tweet_agent_instructions(
    character_settings: str = None,
    competitor_data: List[str] = None,
    previous_tweets: List[str] = None,
    post_settings_data: dict = None,
    events: List[dict] = None,
    post_requests: List[dict] = None,
) -> str:
    base_instructions = f"""You are a professional tweet generation expert specializing in creating natural, human-like content. Your role is to generate tweets that perfectly match the provided character settings while learning from successful role models.

    **CHARACTER ANALYSIS AND ADAPTATION:**
    {character_settings}
    
    Analyze the character settings to understand:
    1. Speech patterns and unique phrases
    2. Personality traits and tone
    3. Background story and context
    4. Special abilities and interests
    5. Language preferences and style
    
    **ROLE MODEL ANALYSIS:**
    {competitor_data}
    
    Study the role models to understand:
    1. Content themes and topics
    2. Engagement patterns
    3. Posting style and format
    4. Hashtag usage
    5. Media integration
    6. Language patterns and tone
    
    **UPCOMING EVENTS:**
    {events if events else "No upcoming events"}
    
    **POST REQUESTS:**
    {post_requests if post_requests else "No post requests"}
    
    **POSTING SCHEDULE:**
    {post_settings_data}
    
    **PREVIOUS CONTENT (AVOID DUPLICATION):**
    {previous_tweets}
    
    GENERATION RULES:
    1. Character Voice:
       - MUST use the exact speech patterns from character settings
       - MUST maintain the character's unique personality
       - MUST incorporate character's special abilities and interests
       - MUST use the specified language and tone
    
    2. Content Structure:
       - Follow successful patterns from role models
       - Include appropriate hashtags (2-3 per tweet)
       - Maintain optimal length (240-280 characters)
       - Include relevant emojis and media references
       - Ensure content aligns with character's background
       - Incorporate upcoming events when relevant
       - Address post requests while maintaining character voice
    
    3. Engagement Optimization:
       - Study role models' successful content patterns
       - Incorporate trending topics when relevant
       - Use engaging call-to-actions
       - Maintain consistent posting schedule
       - Create anticipation for upcoming events
       - Consider post request topics and themes
    
    4. Risk Assessment:
       - Evaluate content for potential risks
       - Ensure alignment with character's values
       - Avoid controversial topics
       - Maintain brand safety
    
    5. Scheduling:
       - Follow posting schedule strictly
       - Distribute content across specified times
       - Ensure all times are in the future
       - Consider time zones and audience
       - Plan content around event dates
       - Prioritize time-sensitive post requests
    
    Return the tweets in the following JSON format:
    {{
        "tweets": [
            {{
                "tweet": "tweet text here",
                "hashtags": ["hashtag1", "hashtag2"],
                "risk_score": 15.5,
                "reach_estimate": 5000,
                "engagement_potential": 0.12,
                "scheduled_time": "2024-03-21T10:00:00Z"
            }},
            ... (4 more tweets)
        ],
        "total_risk_score": 77.5,
        "average_reach_estimate": 5000,
        "overall_engagement_potential": 0.12
    }}
    """
    
    return base_instructions


tweet_agent = Agent(
    name="Tweet Agent",
    instructions=get_tweet_agent_instructions(),
    output_type=TweetsOutput,
    # context_manager=True,
    # memory=,
)



trend_strategy_agent = Agent(
    name="Trend Strategy Agent",
    instructions="""You are a social media trend and strategy expert. Your role is to:
    1. Analyze current trends and patterns
    2. Identify relevant hashtags and topics
    3. Provide strategic advice to the Tweet Agent for engagement
    4. Consider cultural and business context""",
    handoffs=["Tweet Agent"],
)

risk_analyzer_agent = Agent(
    name="Risk Analyzer Agent",
    instructions="""You are a risk analysis expert. Your role is to:
    1. Analyze content for potential risks
    2. Score risks on a scale of 0-100
    3. Identify specific risk factors
    4. Provide risk mitigation suggestions to the Tweet Agent""",
    handoffs=["Tweet Agent"],
)

impact_analyzer_agent = Agent(
    name="Impact Analyzer Agent",
    instructions="""You are an impact analysis expert. Your role is to:
    1. Analyze post performance metrics
    2. Compare against historical averages
    3. Identify engagement patterns
    4. Generate improvement recommendations for the Tweet Agent""",
    handoffs=["Tweet Agent"],
)

persona_agent = Agent(
    name="Persona Agent",
    instructions="""You are an expert character and persona development specialist. Your role is to create and analyze detailed character personas with the following structure:

    1. Basic Information Analysis:
    - Create and validate character names that fit their background
    - Determine appropriate age and occupation
    - Define core personality traits that drive behavior
    
    2. Background Development:
    - Craft compelling and consistent background stories
    - Define meaningful goals and aspirations
    - Ensure background aligns with character's current state
    
    3. Characteristics Definition:
    - Develop unique speech patterns and verbal traits
    - Define detailed preferences and hobbies
    - Identify and justify character dislikes
    
    4. Character Settings:
    - Create coherent worldview based on background
    - Define and maintain consistent relationships
    - Ensure all elements support character development
    
    For each analysis:
    - Maintain internal consistency across all aspects
    - Provide specific examples and justifications
    - Consider cultural and contextual implications
    - Generate practical content recommendations
    - Define clear tone and style guidelines""",
    handoffs=["Tweet Agent"],
)

learning_agent = Agent(
    name="Learning Agent",
    instructions="""You are a data analysis expert. Your role is to:
    1. Analyze learning data and generate insights
    2. Identify patterns and trends in the data
    3. Provide actionable recommendations based on the analysis
    4. Maintain context of previous learning for continuous improvement""",
    handoffs=[],  # No handoffs for learning agent
)

triage_agent = Agent(
    name="Triage Agent",
    instructions="""You are responsible for routing tasks to the appropriate specialist agent.
    Based on the input, determine whether it should be handled by:
    1. Learning Agent - for data analysis and insights
    2. Persona Agent - for persona analysis and management
    3. Tweet Agent - for content generation
    Provide clear reasoning for your routing decision.""",
    handoffs=[],  # No handoffs for triage agent
)

comment_analyzer_agent = Agent(
    name="Comment Analyzer Agent",
    instructions="""You are an expert in analyzing comments on social media posts. Your role is to:
    1. Analyze comments on each of the five tweets generated by the Tweet Agent
    2. Determine the sentiment, backlash, or impact of the comments
    3. Provide a one-line summary (max 100 characters) for each tweet's comment analysis
    4. Use sentiment analysis to gauge overall reception""",
    output_type=List[Dict[str, str]],
    handoffs=[],  # No handoffs for comment analyzer agent
)






async def get_previous_tweets(
    user_id: str, account_id: str, limit: int = 100
) -> List[str]:
    """Get previously generated tweets for a user to avoid duplicates."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT content 
                FROM posts 
                WHERE user_id = %s 
                AND account_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
                """,
                (user_id, account_id, limit),
            )
            previous_tweets = [row[0] for row in cursor.fetchall()]
            return previous_tweets
    finally:
        conn.close()

async def get_compititers_tweets(
    user_id: str, account_id: str, limit: int = 100
) -> List[str]:
    """Get previously generated tweets for a user to avoid duplicates."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT compititers_username, content
                    FROM compititers_data 
                    WHERE user_id = %s 
                    AND account_id = %s
                """,
                (user_id, account_id, limit),
            )
            previous_tweets = [row[0] for row in cursor.fetchall()]
            return previous_tweets
    finally:
        conn.close()

def get_next_scheduled_times(posting_days: dict, posting_time: dict, posting_frequency: int, pre_create: int) -> List[str]:
    """
    Generate a list of scheduled times for posts based on the new scheduling logic.
    
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
    current_date = current_time.date()
    
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
    
    # Get the next posting days
    next_posting_dates = []
    current_weekday = current_date.weekday()
    
    # Start from the next day
    check_date = current_date + timedelta(days=1)
    
    while len(next_posting_dates) < pre_create:
        # Check if current day is enabled
        current_day_jp = ["月", "火", "水", "木", "金", "土", "日"][check_date.weekday()]
        
        if current_day_jp in enabled_days:
            next_posting_dates.append(check_date)
        
        check_date += timedelta(days=1)
    
    # Generate scheduled times for each posting date
    scheduled_times = []
    for posting_date in next_posting_dates:
        for hour in enabled_hours:
            # Create datetime for this hour
            post_time = datetime.combine(posting_date, datetime.min.time().replace(hour=hour))
            
            # Only add if it's in the future
            if post_time > current_time:
                scheduled_times.append(post_time.isoformat() + "Z")
                
                # If we have enough posts for today, break
                if len([t for t in scheduled_times if t.startswith(posting_date.isoformat())]) >= posting_frequency:
                    break
    
    # Sort and return the scheduled times
    return sorted(scheduled_times)[:total_posts]

def parse_pre_create_days(pre_create_str: str) -> int:
    """
    Parse the pre_create string from Japanese format (e.g., "7日") to an integer.
    
    Args:
        pre_create_str: String in format like "7日"
    
    Returns:
        Integer number of days
    """
    try:
        # Remove the "日" character and convert to integer
        return int(pre_create_str.replace("日", ""))
    except (ValueError, AttributeError):
        # If parsing fails, return a default value of 7
        return 7

def parse_posting_frequency(frequency_str: str) -> int:
    """
    Parse the posting frequency string (e.g., "1day") to an integer.
    
    Args:
        frequency_str: String in format like "1day"
    
    Returns:
        Integer number of posts per day
    """
    try:
        # Remove the "day" suffix and convert to integer
        return int(frequency_str.replace("day", ""))
    except (ValueError, AttributeError):
        # If parsing fails, return a default value of 1
        return 1

def clean_tweet_content(content: str) -> str:
    """
    Clean tweet content by removing null characters and other problematic characters.
    
    Args:
        content: The original tweet content
    
    Returns:
        Cleaned tweet content
    """
    if not content:
        return ""
    # Remove null characters and other control characters
    return ''.join(char for char in content if ord(char) >= 32 or char in '\n\r\t')

def get_next_scheduled_times_rolling(
    posting_days, posting_time, posting_frequency, pre_create, existing_scheduled_times
):
    """
    Generate a rolling window of scheduled times, always keeping pre_create enabled days (each with posting_frequency posts) in the future.
    """
    enabled_days = [day for day, enabled in posting_days.items() if enabled]
    enabled_hours = sorted([int(hour) for hour, enabled in posting_time.items() if enabled])
    current_time = datetime.utcnow()
    current_date = current_time.date()
    days_needed = pre_create

    # Parse existing_scheduled_times into a dict: {date: count}
    existing_dates = [datetime.fromisoformat(t.replace('Z', '')) for t in existing_scheduled_times]
    # Only consider posts scheduled strictly after now
    future_dates = [dt.date() for dt in existing_dates if dt > current_time]
    date_counts = Counter(future_dates)

    # Find the next N enabled days that need more posts
    scheduled_times = []
    check_date = current_date + timedelta(days=1)
    filled_days = 0
    while filled_days < days_needed:
        day_jp = ["月", "火", "水", "木", "金", "土", "日"][check_date.weekday()]
        if day_jp in enabled_days:
            count = date_counts.get(check_date, 0)
            for i in range(count, posting_frequency):
                hour = enabled_hours[i % len(enabled_hours)]
                post_time = datetime.combine(check_date, datetime.min.time().replace(hour=hour))
                if post_time > current_time:
                    scheduled_times.append(post_time.isoformat() + "Z")
            filled_days += 1
        check_date += timedelta(days=1)
    return scheduled_times

@router.post("/generate-daily-tweets", response_model=TweetsOutput)
async def generate_tweets(request: TweetRequest):
    """Generate tweets using the Tweet Agent."""
    print("Generating tweets...")
    try:
        # First check for character settings and get competitor data
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Check for character settings
                cursor.execute(
                    """
                    SELECT character_settings 
                    FROM personas 
                    WHERE user_id = %s 
                    AND account_id = %s
                    """,
                    (request.user_id, request.account_id),
                )
                character_settings = cursor.fetchone()
                
                if not character_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="Character settings not found. Please set up your character settings before generating tweets.",
                    )

                cursor.execute(
                    """
                    SELECT compititers_username, content
                    FROM compititers_data 
                    WHERE user_id = %s 
                    AND account_id = %s
                    """,
                    (request.user_id, request.account_id),
                )
                competitor_rows = cursor.fetchall()
                competitor_data = [
                    f"Username: {row[0]}, Content: {row[1]}"
                    for row in competitor_rows
                    if row[0] and row[1]
                ]
                
                cursor.execute(
                    """
                    SELECT posting_day, posting_time, posting_frequency,posting_time,pre_create,post_mode
                    FROM persona_notify 
                    WHERE user_id = %s 
                    AND account_id = %s
                    AND notify_type = 'post'
                    """,
                    (request.user_id, request.account_id),
                )
                post_settings = cursor.fetchone()
                
                if not post_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="Post settings data not found. Please set up your post settings before generating tweets.",
                    )
                
                # Parse the post settings
                posting_day = post_settings[0]  # This is a JSON object
                posting_time = post_settings[1]  # This is a JSON object
                posting_frequency = parse_posting_frequency(post_settings[2])  # Parse frequency string
                posting_time = post_settings[3]
                pre_created_tweets = parse_pre_create_days(post_settings[4])  # Parse Japanese format
                post_mode = post_settings[5]

                # Fetch all future scheduled posts for this user/account
                current_time = datetime.utcnow()
                
                # Use different time field based on post_mode
                if str(post_mode).upper() == "TRUE":
                    # When post_mode is True, check scheduled_time
                    cursor.execute(
                        """
                        SELECT scheduled_time, recommended_time
                        FROM posts 
                        WHERE user_id = %s 
                        AND status = 'unposted'
                        AND account_id = %s 
                        AND scheduled_time > %s
                        """,
                        (request.user_id, request.account_id, current_time),
                    )
                    existing_scheduled_times = [row[0].strftime("%Y-%m-%dT%H:%M:%SZ") for row in cursor.fetchall() if row[0]]
                else:
                    # When post_mode is False, check recommended_time
                    cursor.execute(
                        """
                        SELECT scheduled_time, recommended_time
                        FROM posts 
                        WHERE user_id = %s 
                        AND status = 'unposted'
                        AND account_id = %s 
                        AND recommended_time > %s
                        """,
                        (request.user_id, request.account_id, current_time),
                    )
                    existing_scheduled_times = [row[1].strftime("%Y-%m-%dT%H:%M:%SZ") for row in cursor.fetchall() if row[1]]
                
                print("post_mode", post_mode)

                # Use rolling scheduling logic
                scheduled_times = get_next_scheduled_times_rolling(
                    posting_day,
                    posting_time,
                    posting_frequency,
                    pre_created_tweets,
                    existing_scheduled_times
                )

                # Format post settings data for the agent
                post_settings_data = {
                    "posting_day": posting_day,
                    "posting_time": posting_time,
                    "posting_frequency": posting_frequency,
                    "posting_time": posting_time,
                    "pre_created_tweets": pre_created_tweets,
                    "scheduled_times": scheduled_times
                }

                posts_to_generate = len(scheduled_times)
                if posts_to_generate <= 0:
                    raise HTTPException(
                        status_code=200,
                        detail="No new posts needed. Future posts are already scheduled.",
                    )
        finally:
            conn.close()

        previous_tweets = await get_previous_tweets(request.user_id, request.account_id)
        events = await get_events(request.user_id, request.account_id)
        post_requests = await get_post_requests(request.user_id, request.account_id)
        
        # Update the agent's instructions to specify the exact number of tweets needed
        tweet_agent.instructions = get_tweet_agent_instructions(
            character_settings[0], 
            competitor_data, 
            previous_tweets, 
            post_settings_data,
            events,
            post_requests
        )
        
        # Generate tweets with explicit count
        run_result = await Runner.run(
            tweet_agent, 
            input=f"Create exactly {posts_to_generate} tweets. Each tweet must be unique and follow the character settings."
        )
        result = run_result.final_output
        
        if not isinstance(result, TweetsOutput):
            print(f"Unexpected response type: {type(result)}")
            print(f"Response content: {result}")
            raise HTTPException(
                status_code=500, detail="Unexpected response format from Tweet Agent"
            )
        
        # Verify the number of tweets generated
        if len(result.tweets) != posts_to_generate:
            raise HTTPException(
                status_code=500,
                detail=f"Expected {posts_to_generate} tweets but got {len(result.tweets)}"
            )
        
        # Save tweets to database
        print(result.tweets)
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                current_time = datetime.utcnow()
                
                # Save each tweet as a separate row
                saved_posts = []
                print("post_mode", post_mode)
                for i, tweet in enumerate(result.tweets):
                    scheduled_time = scheduled_times[i] if i < len(scheduled_times) else None
                    # Clean the tweet content before saving
                    cleaned_content = clean_tweet_content(tweet.tweet)
                    cursor.execute(
                        """
                        INSERT INTO posts (content, created_at, user_id, account_id, status, scheduled_time,risk_score,recommended_time)
                        VALUES (%s, %s, %s, %s, %s, %s,%s,%s)
                        RETURNING id, content, created_at, status, scheduled_time,risk_score,recommended_time
                        """,
                        (
                            cleaned_content,
                            current_time,
                            request.user_id,
                            request.account_id,
                            "unposted",
                            scheduled_time if str(post_mode).upper() == "TRUE" else None,
                            tweet.risk_score,
                            None if str(post_mode).upper() == "TRUE" else scheduled_time,
                        ),
                    )
                    post_data = cursor.fetchone()
                    saved_posts.append(
                        {
                        "id": post_data[0],
                        "content": post_data[1],
                        "created_at": post_data[2],
                            "status": post_data[3],
                            "scheduled_time": post_data[4],
                            "risk_score": post_data[5],
                        }
                    )
                
                conn.commit()
                
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save tweets to database: {str(db_error)}",
            )
        finally:
            conn.close()
        
        print("Tweets generated and saved successfully")
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error generating tweets: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate tweets: {str(e)}"
        )


@router.post("/analyze-comments", response_model=List[Dict[str, str]])
async def analyze_comments(tweet_ids: List[str]):
    """Analyze comments for the specified tweets using the Comment Analyzer Agent."""
    print(f"Analyzing comments for tweets: {tweet_ids}")
    if len(tweet_ids) != 5:
        print("Exactly five tweet IDs must be provided")
        raise HTTPException(
            status_code=400, detail="Exactly five tweet IDs must be provided"
        )
    try:
        result = Runner.run(comment_analyzer_agent, input={"tweet_ids": tweet_ids})
        if len(result) != 5:
            print("Comment Analyzer Agent did not return analysis for five tweets")
            raise HTTPException(
                status_code=500, detail="Expected analysis for five tweets"
            )
        print("Comments analyzed successfully")
        return result
    except Exception as e:
        print(f"Error analyzing comments: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze comments: {str(e)}"
        )


@router.put("/update-tweet")
async def update_tweet(request: TweetUpdateRequest):
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
            print(risk_assessment)
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # First check if the tweet exists
                cursor.execute(
                    """
                    SELECT id
                    FROM posts 
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
                    update_fields.append("content = %s")
                    update_values.append(request.content)
                    # Add risk score if content is being updated
                    if risk_assessment:
                        update_fields.append("risk_score = %s")
                        update_values.append(risk_assessment.overall_risk_score)
                        # Convert risk assessment to JSON string
                        risk_assessment_json = json.dumps({
                            "risk_categories": [category.dict() for category in risk_assessment.risk_categories],
                            "risk_assignment": risk_assessment.risk_assignment
                        })
                        update_fields.append("risk_assesments = %s")
                        update_values.append(risk_assessment_json)

                if request.scheduled_time:
                    try:
                    
                        update_fields.append("scheduled_time = %s")
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
                    UPDATE posts 
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                    RETURNING id, content, scheduled_time, risk_score, risk_assesments
                """

                cursor.execute(update_query, update_values)
                updated_tweet = cursor.fetchone()

                conn.commit()

                risk_assesments_value = updated_tweet[4]
                if isinstance(risk_assesments_value, str):
                    try:
                        risk_assesments_value = json.loads(risk_assesments_value)
                    except Exception:
                        pass
                response = {
                    "message": "Tweet updated successfully",
                    "tweet": {
                        "id": updated_tweet[0],
                        "content": updated_tweet[1],
                        "scheduled_time": updated_tweet[2],
                        "risk_score": updated_tweet[3],
                        "risk_assesments": risk_assesments_value
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


@router.put("/update-tweet-image")
async def update_tweet_image(request: TweetImageUpdateRequest):
    """Append new image URLs to a tweet, avoiding duplicates."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # First check if the tweet exists and get current images
                cursor.execute(
                    """
                    SELECT id, "Image_url"
                    FROM posts 
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
                    UPDATE posts 
                    SET "Image_url" = %s
                    WHERE id = %s
                    RETURNING id, "Image_url"
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
    
    
@router.delete("/delete-tweet")
async def delete_tweet(request: DeleteTweetRequest):
    """Delete a tweet by its ID."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # First check if the tweet exists
                cursor.execute(
                    """
                    SELECT id
                    FROM posts 
                    WHERE id = %s
                    """,
                    (request.tweet_id,),
                )
                tweet = cursor.fetchone()

                if not tweet:
                    raise HTTPException(status_code=404, detail="Tweet not found")

                # Delete the tweet
                cursor.execute(
                    """
                    DELETE FROM posts 
                    WHERE id = %s
                    RETURNING id
                    """,
                    (request.tweet_id,),
                )
                deleted_tweet = cursor.fetchone()

                conn.commit()

                return {
                    "message": "Tweet deleted successfully",
                    "tweet_id": deleted_tweet[0]
                }

        except HTTPException as he:
            raise he
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to delete tweet: {str(db_error)}"
            )
        finally:
            conn.close()

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error deleting tweet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete tweet: {str(e)}")


@router.delete("/delete-tweet-image")
async def delete_tweet_image(request: DeleteTweetImageRequest):
    """Delete specific image URLs from a tweet's Image_url field."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # First check if the tweet exists and get current images
                cursor.execute(
                    """
                    SELECT id, "Image_url"
                    FROM posts 
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
                    UPDATE posts 
                    SET "Image_url" = %s
                    WHERE id = %s
                    RETURNING id, "Image_url"
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


@router.post("/regenerate-unposted-tweets", response_model=TweetsOutput)
async def regenerate_unposted_tweets(request: TweetRequest):
    """Regenerate all unposted tweets for a user and account."""
    print("Regenerating unposted tweets...")
    try:
        # First check for character settings and get competitor data
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Check for character settings
                cursor.execute(
                    """
                    SELECT character_settings 
                    FROM personas 
                    WHERE user_id = %s 
                    AND account_id = %s
                    """,
                    (request.user_id, request.account_id),
                )
                character_settings = cursor.fetchone()
                
                if not character_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="Character settings not found. Please set up your character settings before generating tweets.",
                    )

                cursor.execute(
                    """
                    SELECT compititers_username, content
                    FROM compititers_data 
                    WHERE user_id = %s 
                    AND account_id = %s
                    """,
                    (request.user_id, request.account_id),
                )
                competitor_rows = cursor.fetchall()
                competitor_data = [
                    f"Username: {row[0]}, Content: {row[1]}"
                    for row in competitor_rows
                    if row[0] and row[1]
                ]
                
                if not competitor_data:
                    raise HTTPException(
                        status_code=400,
                        detail="Competitor data not found. Please set up your competitor data before generating tweets.",
                    )
                
                cursor.execute(
                    """
                    SELECT posting_day, posting_time, posting_frequency,posting_time,pre_create,post_mode
                    FROM persona_notify 
                    WHERE user_id = %s 
                    AND account_id = %s
                    AND notify_type = 'post'
                    """,
                    (request.user_id, request.account_id),
                )
                post_settings = cursor.fetchone()
                
                if not post_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="Post settings data not found. Please set up your post settings before generating tweets.",
                    )
                
                # Parse the post settings
                posting_day = post_settings[0]  # This is a JSON object
                posting_time = post_settings[1]  # This is a JSON object
                posting_frequency = parse_posting_frequency(post_settings[2])  # Parse frequency string
                posting_time = post_settings[3]
                pre_created_tweets = parse_pre_create_days(post_settings[4])  # Parse Japanese format
                post_mode = post_settings[5]
                
                print("posting_day",posting_day)
                print("posting_time",posting_time)
                print("posting_frequency",posting_frequency)
                print("pre_created_tweets",pre_created_tweets)
                print("post_mode",post_mode)

                # Get scheduled times based on settings
                scheduled_times = get_next_scheduled_times(
                    posting_day,
                    posting_time,
                    posting_frequency,
                    pre_created_tweets
                )
                
                # Format post settings data for the agent
                post_settings_data = {
                    "posting_day": posting_day,
                    "posting_time": posting_time,
                    "posting_frequency": posting_frequency,
                    "posting_time": posting_time,
                    "pre_created_tweets": pre_created_tweets,
                    "scheduled_times": scheduled_times
                }


                cursor.execute(
                    """
                    DELETE FROM posts 
                    WHERE user_id = %s 
                    AND account_id = %s 
                    AND status = 'unposted'
                    """,
                    (request.user_id, request.account_id),
                )
                conn.commit()
                
        finally:
            conn.close()

        previous_tweets = await get_previous_tweets(request.user_id, request.account_id)
        events = await get_events(request.user_id, request.account_id)
        post_requests = await get_post_requests(request.user_id, request.account_id)

        tweet_agent.instructions = get_tweet_agent_instructions(
            character_settings[0], 
            competitor_data, 
            previous_tweets, 
            post_settings_data,
            events,
            post_requests
        )
        
        total_tweets_needed = posting_frequency * pre_created_tweets
        run_result = await Runner.run(tweet_agent, input=f"generate {total_tweets_needed} tweets")
        result = run_result.final_output
        
        if not isinstance(result, TweetsOutput):
            raise HTTPException(
                status_code=500, detail="Unexpected response format from Tweet Agent"   
            )
        if len(result.tweets) != total_tweets_needed:
            raise HTTPException(
                status_code=500, 
                detail=f"Expected {total_tweets_needed} tweets but got {len(result.tweets)}"
            )
        
        # Save tweets to database
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                current_time = datetime.utcnow()
                
                # Save each tweet as a separate row
                saved_posts = []
                for i, tweet in enumerate(result.tweets):
                    scheduled_time = scheduled_times[i] if i < len(scheduled_times) else None
                    cursor.execute(
                        """
                        INSERT INTO posts (content, created_at, user_id, account_id, status, scheduled_time,risk_score,recommended_time)
                        VALUES (%s, %s, %s, %s, %s, %s,%s,%s)
                        RETURNING id, content, created_at, status, scheduled_time,risk_score,recommended_time
                        """,
                        (
                            tweet.tweet,
                            current_time,
                            request.user_id,
                            request.account_id,
                            "unposted",
                            scheduled_time if str(post_mode).upper() == "TRUE" else None,
                            tweet.risk_score,
                            None if str(post_mode).upper() == "TRUE" else scheduled_time,
                        ),
                    )
                    post_data = cursor.fetchone()
                    saved_posts.append(
                        {
                        "id": post_data[0],
                        "content": post_data[1],
                        "created_at": post_data[2],
                            "status": post_data[3],
                            "scheduled_time": post_data[4],
                            "risk_score": post_data[5],
                        }
                    )
                
                conn.commit()
                
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save tweets to database: {str(db_error)}",
            )
        finally:
            conn.close()
        
        print(f"Successfully regenerated {total_tweets_needed} tweets")
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error regenerating tweets: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to regenerate tweets: {str(e)}"
        )





