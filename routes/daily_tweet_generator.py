from typing import Dict, List, Optional, Any
from agents import Agent, Runner, function_tool
from pydantic import BaseModel
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

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


router = APIRouter()


class TweetOutput(BaseModel):
    tweet: str
    hashtags: List[str]
    impact_score: float
    reach_estimate: int
    engagement_potential: float
    scheduled_time: str


class TweetsOutput(BaseModel):
    tweets: List[TweetOutput]
    total_impact_score: float
    average_reach_estimate: float
    overall_engagement_potential: float


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
    image_url: str
class DeleteTweetRequest(BaseModel):
    tweet_id: str


def get_tweet_agent_instructions(
    character_settings: str = None,
    competitor_data: List[str] = None,
    previous_tweets: List[str] = None,
    post_settings_data: dict = None,
) -> str:
    base_instructions = f"""You are a professional tweet generation expert specializing in creating natural, human-like content with an educated perspective. Your role is to:
    1. Generate EXACTLY FIVE unique, natural-sounding tweets that read as if written by an educated professional
    **
    if user give any its language in the character settings, you have to write in that language. if not, write in japanese.
    these are the previous tweets:
    {previous_tweets}
    these are the competitor data:
    {competitor_data}
    
    **These are the Post Schedule Settings:
    {post_settings_data}
    
    IMPORTANT SCHEDULING RULES:
    1. You MUST schedule tweets ONLY on the days specified in posting_day
    2. You MUST schedule tweets ONLY within the time ranges specified in posting_time
    3. The posting_frequency indicates how many posts should be made per day
    4. All scheduled times must be in the future relative to the current time ({datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")})
    5. Distribute the tweets across the specified posting days and times
    
    you have to avoid repeating the same content as the previous tweets.
    Analyze the previous tweets and the competitor data and generate tweets that are unique and engaging.
    **
    2. Each tweet must follow these guidelines:
       - Write in a natural, conversational tone while maintaining professionalism
       - Include personal insights and observations that feel authentic
       - Use appropriate contractions and natural language patterns
       - Include only verified facts and truthful information
       - Avoid emotionally charged or provocative content
       - Never spread misinformation or unverified claims
       - Include relevant hashtags (2-3 per tweet)
       - Maintain optimal length (240-280 characters)
       - Use clear, professional call-to-actions
       - Base content on verifiable data and statistics
    3. Content must be:
       - Natural and conversational while remaining professional
       - Factually accurate and verifiable
       - Professional and business-appropriate
       - Focused on industry insights and developments
       - Based on objective analysis rather than emotional appeal
       - Respectful and inclusive
       - Include personal perspective where appropriate
    4. Writing style should:
       - Sound like an educated professional sharing insights
       - Use natural language patterns and occasional contractions
       - Include personal observations and experiences
       - Maintain a balance between professional and approachable
    5. For each tweet, suggest an optimal posting time based on:
       - Content type (e.g., industry news, educational content, engagement posts)
       - Target audience's timezone and activity patterns
       - Day of the week (weekdays vs weekends)
       - Current trends and peak engagement times
       
       - IMPORTANT: Schedule times must be in the future relative to the current time ({datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")})
       - IMPORTANT: Schedule times according to the post settings data. The day of week mention in the post settings data is the day of the week when the tweet will be posted.
    6. Return the tweets in the following JSON format:
       {{
         "tweets": [
           {{
             "tweet": "tweet text here",
             "hashtags": ["hashtag1", "hashtag2"],
             "impact_score": 85.5,
             "reach_estimate": 5000,
             "engagement_potential": 0.12,
             "scheduled_time": "2024-03-21T10:00:00Z"  // Must be a future date/time
           }},
           ... (4 more tweets)
         ],
         "total_impact_score": 427.5,
         "average_reach_estimate": 5000,
         "overall_engagement_potential": 0.12
       }}
       """

    full_instructions = base_instructions

    if character_settings:
        full_instructions += f"""

    Additionally, you must follow these character-specific guidelines:
    {character_settings}
    - Show personality while staying within professional boundaries
    - Consider the character's typical posting patterns when suggesting scheduled times
    - Ensure all scheduled times are in the future relative to the current time ({datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")})

    Your tweets should reflect this character's personality, tone, and style while maintaining professional standards."""

    return full_instructions


tweet_agent = Agent(
    name="Tweet Agent",
    instructions=get_tweet_agent_instructions(),
    output_type=TweetsOutput,
    
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


@router.post("/generate-daily-tweets", response_model=TweetsOutput)
async def generate_tweets(request: TweetRequest):
    """Generate five high-quality tweets using the Tweet Agent."""
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
                
                #
                if not competitor_data:
                    raise HTTPException(
                        status_code=400,
                        detail="Competitor data not found. Please set up your competitor data before generating tweets.",
                    )
                
                cursor.execute(
                    """
                    SELECT posting_day, posting_time, posting_frequency,posting_time
                    FROM persona_notify 
                    WHERE user_id = %s 
                    AND account_id = %s
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
                posting_frequency = post_settings[2]
                posting_time = post_settings[3]
                
                # Format post settings data for the agent
                post_settings_data = {
                    "posting_day": posting_day,
                    "posting_time": posting_time,
                    "posting_frequency": posting_frequency,
                    "posting_time": posting_time
                }
                
                current_time = datetime.utcnow()
                thirty_minutes_ago = current_time - timedelta(minutes=30)

                cursor.execute(
                    """
                    SELECT COUNT(*) 
                    FROM posts 
                    WHERE user_id = %s 
                    AND account_id = %s 
                    AND created_at > %s
                    """,
                    (request.user_id, request.account_id, thirty_minutes_ago),
                )
                recent_tweets_count = cursor.fetchone()[0]

                if recent_tweets_count > 0:
                    raise HTTPException(
                        status_code=429,  # Too Many Requests
                        detail="You have already generated tweets in the last 30 minutes. Please wait before generating new tweets.",
                    )
        finally:
            conn.close()

        previous_tweets = await get_previous_tweets(request.user_id, request.account_id)

        tweet_agent.instructions = get_tweet_agent_instructions(
            character_settings[0], competitor_data, previous_tweets, post_settings_data
        )

        run_result = await Runner.run(tweet_agent, input="generate 5 tweets")
        result = run_result.final_output

        if not isinstance(result, TweetsOutput):
            print(f"Unexpected response type: {type(result)}")
            print(f"Response content: {result}")
            raise HTTPException(
                status_code=500, detail="Unexpected response format from Tweet Agent"
            )
        if len(result.tweets) != 5:
            raise HTTPException(status_code=500, detail="Expected exactly five tweets")

        # Save tweets to database
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                current_time = datetime.utcnow()

                # Save each tweet as a separate row
                saved_posts = []
                for tweet in result.tweets:
                    cursor.execute(
                        """
                        INSERT INTO posts (content, created_at, user_id, account_id, status, scheduled_time)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id, content, created_at, status, scheduled_time
                        """,
                        (
                            tweet.tweet,
                            current_time,
                            request.user_id,
                            request.account_id,
                            "unposted",
                            tweet.scheduled_time,
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
@router.post("/generate-bulk-tweets", response_model=TweetsOutput)
async def generate_tweets(request: TweetRequest):
    """Generate five high-quality tweets using the Tweet Agent."""
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
                
                #
                if not competitor_data:
                    raise HTTPException(
                        status_code=400,
                        detail="Competitor data not found. Please set up your competitor data before generating tweets.",
                    )
                
                cursor.execute(
                    """
                    SELECT posting_day, posting_time, posting_frequency,posting_time
                    FROM persona_notify 
                    WHERE user_id = %s 
                    AND account_id = %s
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
                posting_frequency = post_settings[2]
                posting_time = post_settings[3]
                
                # Format post settings data for the agent
                post_settings_data = {
                    "posting_day": posting_day,
                    "posting_time": posting_time,
                    "posting_frequency": posting_frequency,
                    "posting_time": posting_time
                }
                
        finally:
            conn.close()

        previous_tweets = await get_previous_tweets(request.user_id, request.account_id)

        tweet_agent.instructions = get_tweet_agent_instructions(
            character_settings[0], competitor_data, previous_tweets, post_settings_data
        )

        run_result = await Runner.run(tweet_agent, input="generate 5 tweets")
        result = run_result.final_output

        if not isinstance(result, TweetsOutput):
            print(f"Unexpected response type: {type(result)}")
            print(f"Response content: {result}")
            raise HTTPException(
                status_code=500, detail="Unexpected response format from Tweet Agent"
            )
        if len(result.tweets) != 5:
            raise HTTPException(status_code=500, detail="Expected exactly five tweets")

        # Save tweets to database
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                current_time = datetime.utcnow()

                # Save each tweet as a separate row
                saved_posts = []
                for tweet in result.tweets:
                    cursor.execute(
                        """
                        INSERT INTO posts (content, created_at, user_id, account_id, status, scheduled_time)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id, content, created_at, status, scheduled_time
                        """,
                        (
                            tweet.tweet,
                            current_time,
                            request.user_id,
                            request.account_id,
                            "unposted",
                            tweet.scheduled_time,
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

                if request.scheduled_time:
                    try:
                        # Validate the scheduled time format
                        datetime.strptime(request.scheduled_time, "%Y-%m-%dT%H:%M:%SZ")
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
                    RETURNING id, content, scheduled_time
                """

                cursor.execute(update_query, update_values)
                updated_tweet = cursor.fetchone()

                conn.commit()

                return {
                    "message": "Tweet updated successfully",
                    "tweet": {
                        "id": updated_tweet[0],
                        "content": updated_tweet[1],
                        "scheduled_time": updated_tweet[2],
                    },
                }

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
    """Update the image URL of a tweet."""
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

                # Update the image URL
                cursor.execute(
                    """
                    UPDATE posts 
                    SET "Image_url" = %s
                    WHERE id = %s
                    RETURNING id, "Image_url"
                    """,
                    (request.image_url, request.tweet_id),
                )
                updated_tweet = cursor.fetchone()

                conn.commit()

                return {
                    "message": "Tweet image updated successfully",
                    "tweet": {
                        "id": updated_tweet[0],
                        "image_url": updated_tweet[1],
                    },
                }

        except HTTPException as he:
            raise he
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update tweet image: {str(db_error)}"
            )
        finally:
            conn.close()

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating tweet image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update tweet image: {str(e)}")
    
    
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
