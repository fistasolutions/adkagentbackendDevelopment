import asyncio
from openai import OpenAI
from agents import Agent, Runner, set_default_openai_key
import os
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tweet_generator.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")
set_default_openai_key(openai_api_key)

# Initialize tweet generator agent
tweet_generator_agent = Agent(
    name="Tweet Generator",
    instructions="You are an expert at creating engaging and relevant tweets. Your are a japanese twitter user and your tweets should be in japanese."
)

async def generate_tweet(learning_data: str) -> list[str]:
    """Generate tweets based on learning data and return them in reverse order."""
    logger.info("Starting tweet generation...")
    
    # Generate tweets
    tweets_result = await Runner.run(tweet_generator_agent, f"Generate 5 tweets based on: {learning_data}")
    
    # Split tweets, remove empty lines and the final message
    tweets = [tweet for tweet in tweets_result.final_output.split("\n") if tweet.strip() and not tweet.startswith("もちろん！")]
    
    # Format tweets with proper numbering
    formatted_tweets = [f"tweet {i+1}: {tweet}" for i, tweet in enumerate(reversed(tweets))]
    
    logger.info(f"Generated {len(tweets)} formatted tweets")
    return formatted_tweets
