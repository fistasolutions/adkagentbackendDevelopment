# import asyncio
# from openai import OpenAI
# from agents import Agent, Runner, set_default_openai_key
# import os
# from dotenv import load_dotenv
# import logging

# # Set up logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler('tweet_generator.log', encoding='utf-8')
#     ]
# )
# logger = logging.getLogger(__name__)

# # Load environment variables
# load_dotenv()

# # Initialize OpenAI API key
# openai_api_key = os.getenv("OPENAI_API_KEY")
# set_default_openai_key(openai_api_key)

# # Initialize tweet generator agent
# tweet_generator_agent = Agent(
#     name="Tweet Generator",
#     instructions="You are an expert at creating engaging and relevant tweets. Your are a japanese twitter user and your tweets should be in japanese."
# )

# async def generate_tweet(learning_data: str) -> list[str]:
#     """Generate tweets based on learning data and return them in reverse order."""
#     tweets_result = await Runner.run(tweet_generator_agent, f"Generate 5 tweets based on: {learning_data}")
#     tweets = [tweet for tweet in tweets_result.final_output.split("\n") if tweet.strip() and not tweet.startswith("もちろん！")]
#     formatted_tweets = [f"tweet {i+1}: {tweet}" for i, tweet in enumerate(reversed(tweets))]
#     logger.info(f"Generated {len(tweets)} formatted tweets")
#     return formatted_tweets

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
from fastapi import APIRouter, HTTPException, Depends,Response
from db.db import get_connection
load_dotenv()


router = APIRouter()
class TweetOutput(BaseModel):
    tweet: str
    hashtags: List[str]
    impact_score: float
    reach_estimate: int
    engagement_potential: float

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

TEST_TWEETS = [
    TweetOutput(
        tweet="Exciting news in AI! New breakthroughs in natural language processing are revolutionizing how we interact with technology. #AI #Innovation",
        hashtags=["AI", "Innovation"],
        impact_score=85.5,
        reach_estimate=5000,
        engagement_potential=0.12
    ),
    TweetOutput(
        tweet="How is your company adapting to digital transformation? Share your experiences below! #DigitalTransformation #Business",
        hashtags=["DigitalTransformation", "Business"],
        impact_score=78.2,
        reach_estimate=4500,
        engagement_potential=0.15
    )
]

TEST_ANALYSIS = AnalysisOutput(
    insights=[
        "High engagement during morning hours",
        "Educational content performs best",
        "Industry news drives most shares"
    ],
    recommendations=[
        "Increase morning post frequency",
        "Focus on educational content",
        "Include more industry insights"
    ],
    patterns={
        "best_performing_times": ["09:00", "15:00"],
        "content_types": {
            "educational": 40,
            "news": 30,
            "engagement": 30
        }
    },
    metrics={
        "average_engagement": 4.5,
        "reach_growth": 12.3,
        "conversion_rate": 2.1
    }
)

# Function tool output models
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

    model_config = {
        "json_schema_extra": {
            "additionalProperties": False
        }
    }

class TweetRequest(BaseModel):
    user_id: str
    account_id: str

# Test data for role model analysis
ROLE_MODEL_TEST_DATA = {
    "communication_style": "Professional and engaging",
    "tone": "Balanced mix of informative and conversational",
    "engagement_patterns": {
        "posting_frequency": "3-5 times per day",
        "best_performing_times": ["09:00", "12:00", "15:00", "18:00"],
        "average_engagement_rate": 4.5
    },
    "content_structure": {
        "hook_style": "Question-based or surprising fact",
        "body_length": "280 characters",
        "hashtag_usage": "2-3 relevant hashtags"
    }
}

# Test data for industry standards
INDUSTRY_STANDARD_TEST_DATA = {
    "trends": [
        "AI-powered automation",
        "Sustainable business practices",
        "Remote work optimization",
        "Digital transformation"
    ],
    "content_patterns": {
        "educational_posts": 40,
        "industry_news": 30,
        "thought_leadership": 20,
        "engagement_posts": 10
    },
    "best_practices": [
        "Use data-driven insights",
        "Maintain consistent branding",
        "Engage with audience regularly",
        "Share industry expertise"
    ]
}

# Test data for competitor analysis
COMPETITOR_TEST_DATA = {
    "content_effectiveness": {
        "average_engagement_rate": 3.8,
        "best_performing_content": "Industry insights",
        "worst_performing_content": "Promotional posts"
    },
    "engagement_patterns": {
        "peak_engagement_times": ["10:00", "14:00", "16:00"],
        "average_response_time": "2 hours",
        "engagement_types": {
            "likes": 45,
            "retweets": 30,
            "replies": 25
        }
    },
    "posting_schedule": {
        "frequency": "4 times per day",
        "days": ["Monday", "Wednesday", "Friday"],
        "times": ["09:00", "12:00", "15:00", "18:00"]
    }
}

# Core agents with handoffs defined inside their bodies
def get_tweet_agent_instructions(character_settings: str = None) -> str:
    base_instructions = """You are a professional tweet generation expert specializing in creating natural, human-like content with an educated perspective. Your role is to:
    1. Generate EXACTLY FIVE unique, natural-sounding tweets that read as if written by an educated professional
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
       - Show personality while staying within professional boundaries
       - Show personality while staying within professional boundaries
    5. Return the tweets in the following JSON format:
       {
         "tweets": [
           {
             "tweet": "tweet text here",
             "hashtags": ["hashtag1", "hashtag2"],
             "impact_score": 85.5,
             "reach_estimate": 5000,
             "engagement_potential": 0.12
           },
           ... (4 more tweets)
         ],
         "total_impact_score": 427.5,
         "average_reach_estimate": 5000,
         "overall_engagement_potential": 0.12
       }
       """
    
    if character_settings:
        return f"""{base_instructions}

    Additionally, you must follow these character-specific guidelines:
    {character_settings}
    
    - Show personality while staying within professional boundaries
    5. Return the tweets in the following JSON format:
     

    Your tweets should reflect this character's personality, tone, and style while maintaining professional standards."""
    
    return base_instructions

tweet_agent = Agent(
    name="Tweet Agent",
    instructions=get_tweet_agent_instructions(),
    output_type=TweetsOutput,
    handoffs=[
        "Role Model Analysis Agent",
        "Industry Standard Analysis Agent",
        "Competitor Analysis Agent",
        "Trend Strategy Agent",
        "Risk Analyzer Agent",
        "Impact Analyzer Agent",
        "Persona Agent"
    ]
)

role_model_agent = Agent(
    name="Role Model Analysis Agent",
    instructions=f"""You are an expert in analyzing and learning from successful social media accounts. Your role is to:
    1. Analyze role model accounts using test data: {ROLE_MODEL_TEST_DATA}
    2. Extract best practices and patterns (e.g., communication style, tone, engagement tactics)
    3. Identify transferable strategies
    4. Provide specific recommendations to the Tweet Agent for implementation""",
    output_type=AnalysisOutput,
    handoffs=["Tweet Agent"]
)

industry_standard_agent = Agent(
    name="Industry Standard Analysis Agent",
    instructions=f"""You are an expert in industry trends and standards analysis. Your role is to:
    1. Monitor and analyze industry standards using test data: {INDUSTRY_STANDARD_TEST_DATA}
    2. Track trends and emerging topics
    3. Identify content patterns and themes
    4. Provide insights to the Tweet Agent for timely and relevant content""",
    output_type=AnalysisOutput,
    handoffs=["Tweet Agent"]
)

competitor_analysis_agent = Agent(
    name="Competitor Analysis Agent",
    instructions=f"""You are an expert in competitor analysis and strategy. Your role is to:
    1. Analyze competitor accounts using test data: {COMPETITOR_TEST_DATA}
    2. Track and compare performance metrics
    3. Identify successful patterns and strategies (e.g., content types, engagement tactics)
    4. Provide actionable recommendations to the Tweet Agent""",
    output_type=AnalysisOutput,
    handoffs=["Tweet Agent"]
)

trend_strategy_agent = Agent(
    name="Trend Strategy Agent",
    instructions="""You are a social media trend and strategy expert. Your role is to:
    1. Analyze current trends and patterns
    2. Identify relevant hashtags and topics
    3. Provide strategic advice to the Tweet Agent for engagement
    4. Consider cultural and business context""",
    handoffs=["Tweet Agent"]
)

risk_analyzer_agent = Agent(
    name="Risk Analyzer Agent",
    instructions="""You are a risk analysis expert. Your role is to:
    1. Analyze content for potential risks
    2. Score risks on a scale of 0-100
    3. Identify specific risk factors
    4. Provide risk mitigation suggestions to the Tweet Agent""",
    handoffs=["Tweet Agent"]
)

impact_analyzer_agent = Agent(
    name="Impact Analyzer Agent",
    instructions="""You are an impact analysis expert. Your role is to:
    1. Analyze post performance metrics
    2. Compare against historical averages
    3. Identify engagement patterns
    4. Generate improvement recommendations for the Tweet Agent""",
    handoffs=["Tweet Agent"]
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

    handoffs=["Tweet Agent"]
)

learning_agent = Agent(
    name="Learning Agent",
    instructions="""You are a data analysis expert. Your role is to:
    1. Analyze learning data and generate insights
    2. Identify patterns and trends in the data
    3. Provide actionable recommendations based on the analysis
    4. Maintain context of previous learning for continuous improvement""",
    handoffs=[]  # No handoffs for learning agent
)

triage_agent = Agent(
    name="Triage Agent",
    instructions="""You are responsible for routing tasks to the appropriate specialist agent.
    Based on the input, determine whether it should be handled by:
    1. Learning Agent - for data analysis and insights
    2. Persona Agent - for persona analysis and management
    3. Tweet Agent - for content generation
    Provide clear reasoning for your routing decision.""",
    handoffs=[]  # No handoffs for triage agent
)

comment_analyzer_agent = Agent(
    name="Comment Analyzer Agent",
    instructions="""You are an expert in analyzing comments on social media posts. Your role is to:
    1. Analyze comments on each of the five tweets generated by the Tweet Agent
    2. Determine the sentiment, backlash, or impact of the comments
    3. Provide a one-line summary (max 100 characters) for each tweet's comment analysis
    4. Use sentiment analysis to gauge overall reception""",
    output_type=List[Dict[str, str]],
    handoffs=[]  # No handoffs for comment analyzer agent
)

@router.post("/generate-daily-tweets", response_model=TweetsOutput)
async def generate_tweets(request: TweetRequest):
    """Generate five high-quality tweets using the Tweet Agent."""
    print("Generating tweets...")
    try:
        # First check for character settings
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
                    (request.user_id, request.account_id)
                )
                character_settings = cursor.fetchone()
                
                if not character_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="Character settings not found. Please set up your character settings before generating tweets."
                    )
                
                # Then check for recent tweets
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
                    (request.user_id, request.account_id, thirty_minutes_ago)
                )
                recent_tweets_count = cursor.fetchone()[0]
                
                if recent_tweets_count > 0:
                    raise HTTPException(
                        status_code=429,  # Too Many Requests
                        detail="You have already generated tweets in the last 30 minutes. Please wait before generating new tweets."
                    )
        finally:
            conn.close()

        # If character settings exist and no recent tweets, proceed with generation
        # Update agent with character-specific instructions
        tweet_agent.instructions = get_tweet_agent_instructions(character_settings[0])
        
        run_result = await Runner.run(tweet_agent, input="generate 5 tweets")
        result = run_result.final_output
        
        if not isinstance(result, TweetsOutput):
            print(f"Unexpected response type: {type(result)}")
            print(f"Response content: {result}")
            raise HTTPException(status_code=500, detail="Unexpected response format from Tweet Agent")
        if len(result.tweets) != 5:
            print(f"Generated {len(result.tweets)} tweets instead of 5")
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
                        INSERT INTO posts (content, created_at, user_id, account_id, status)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id, content, created_at, status
                        """,
                        (tweet.tweet, current_time, request.user_id, request.account_id, 'unposted')
                    )
                    post_data = cursor.fetchone()
                    saved_posts.append({
                        "id": post_data[0],
                        "content": post_data[1],
                        "created_at": post_data[2],
                        "status": post_data[3]
                    })
                
                conn.commit()
                print(f"Successfully saved {len(saved_posts)} tweets to database")
                
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(status_code=500, detail=f"Failed to save tweets to database: {str(db_error)}")
        finally:
            conn.close()
        
        print("Tweets generated and saved successfully")
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error generating tweets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate tweets: {str(e)}")

@router.post("/analyze-comments", response_model=List[Dict[str, str]])
async def analyze_comments(tweet_ids: List[str]):
    """Analyze comments for the specified tweets using the Comment Analyzer Agent."""
    print(f"Analyzing comments for tweets: {tweet_ids}")
    if len(tweet_ids) != 5:
        print("Exactly five tweet IDs must be provided")
        raise HTTPException(status_code=400, detail="Exactly five tweet IDs must be provided")
    try:
        result = Runner.run(comment_analyzer_agent, input={"tweet_ids": tweet_ids})
        if len(result) != 5:
            print("Comment Analyzer Agent did not return analysis for five tweets")
            raise HTTPException(status_code=500, detail="Expected analysis for five tweets")
        print("Comments analyzed successfully")
        return result
    except Exception as e:
        print(f"Error analyzing comments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze comments: {str(e)}")
