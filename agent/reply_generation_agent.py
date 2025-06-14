import json
from agents import Agent, Runner
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ReplyOutput(BaseModel):
    tweet_id: str
    tweet_text: str
    post_username: str
    reply_text: str
    risk_score: float
    schedule_time: str

class ReplyGenerationRequest(BaseModel):
    tweet_id: str
    tweet_text: str
    post_username: str
    character_settings: str
    posting_frequency: int
    pre_create: int
    template_use: bool
    template_text: Optional[str] = None
    posting_day: dict
    posting_time: dict

def get_reply_agent_instructions(
    character_settings: str,
    posting_frequency: int,
    pre_create: int,
    template_use: bool,
    posting_day: dict,
    posting_time: dict,
    template_text: Optional[str] = None
) -> str:
    # Parse templates if available
    templates = []
    if template_use and template_text:
        try:
            templates = json.loads(template_text)
            if not isinstance(templates, list):
                templates = [templates]
        except json.JSONDecodeError:
            print("Error parsing template_text JSON")
            templates = []

    base_instructions = f"""You are a professional social media engagement expert specializing in creating natural, human-like replies that match the character's personality and tone.

    **CHARACTER ANALYSIS AND ADAPTATION:**
    {character_settings}
    
    **POSTING SETTINGS:**
    -Remember you have to reply to the tweets of the day you have to post the reply and the time you have to post the reply and post always in future.
    -You did not have to reply every tweet, you have to reply only 70% of the tweets.
    - Posting Frequency: {posting_frequency} posts per day
    - Pre-create: {pre_create} posts advance days. For Example if post frequency is 10 and pre_create is 2 you have to make 20 posts in advance
    - Template Use: {template_use}
    {f'- Available Templates: {json.dumps(templates, indent=2)}' if templates else ''}
    - Posting Day: {posting_day} the day you have to post the reply
    - Posting Time: {posting_time} the time you have to post the reply
    -Today is {datetime.utcnow().strftime("%Y-%m-%d")} the current date

    **SCHEDULING RULES:**
    1. Schedule Time Rules:
       - MUST schedule replies for future dates only
       - Use posting_day dictionary to determine valid days (True values)
       - Use posting_time dictionary to determine valid hours (True values)
       - Calculate next available posting slot based on current date/time
       - Ensure schedule_time is in ISO format (YYYY-MM-DDTHH:MM:SSZ)
       - Distribute replies across available posting slots
       - Consider posting_frequency and pre_create settings for distribution

    2. Example Schedule Calculation:
       - If today is Monday and posting_day has True for Wednesday and Friday
       - And posting_time has True for hours 10, 14, and 18
       - Schedule first reply for next Wednesday at 10:00
       - Schedule second reply for next Wednesday at 14:00
       - Continue this pattern for all replies

    Analyze the character settings to understand:
    1. Speech patterns and unique phrases
    2. Personality traits and tone
    3. Background story and context
    4. Special abilities and interests
    5. Language preferences and style
    
    GENERATION RULES:
    1. Template Usage:
       {f'- MUST use one of the provided templates that best matches the tweet context' if template_use and templates else '- Generate custom replies based on character settings'}
       {f'- Do not create new replies, only adapt the chosen template to the specific tweet context' if template_use and templates else ''}
       {f'- If no template matches the tweet context, use the most generic template' if template_use and templates else ''}
    
    2. Character Voice:
       - MUST use the exact speech patterns from character settings
       - MUST maintain the character's unique personality
       - MUST incorporate character's special abilities and interests
       - MUST use the specified language and tone
    
    3. Content Structure:
       - Keep replies concise and engaging
       - Use appropriate emojis and media references
       - Ensure content aligns with character's background
       - Maintain natural conversation flow
       {f'- Replace template placeholders with relevant content from the tweet' if template_use and templates else ''}
    
    4. Engagement Optimization:
       - Create engaging responses
       - Use appropriate call-to-actions
       - Maintain consistent tone
       - Consider the original post's context
       - Space out replies based on posting frequency ({posting_frequency} posts per day)
       - Ensure total replies match posting_frequency * pre_create ({posting_frequency * pre_create} total replies)
    
    5. Risk Assessment:
       - Evaluate content for potential risks
       - Ensure alignment with character's values
       - Avoid controversial topics
       - Maintain brand safety
    
    Return the reply in the following JSON format:
    {{
        "tweet_id": "original tweet id",
        "tweet_text": "original tweet text",
        "post_username": "username of the original post",
        "reply_text": "generated reply text",
        "risk_score": 15.5,
        "schedule_time": "2024-03-21T10:00:00Z"  # MUST be a future date/time based on posting_day and posting_time settings
    }}
    """
    
    return base_instructions

reply_agent = Agent(
    name="Reply Generation Agent",
    instructions=get_reply_agent_instructions("", 1, 1, False, {}, {}),
    output_type=ReplyOutput
)

async def generate_reply(request: ReplyGenerationRequest) -> ReplyOutput:
    """Generate a reply for a tweet using the Reply Generation Agent."""
    reply_agent.instructions = get_reply_agent_instructions(
        request.character_settings,
        request.posting_frequency,
        request.pre_create,
        request.template_use,
        request.posting_day,
        request.posting_time,
        request.template_text
    )
    
    run_result = await Runner.run(
        reply_agent, 
        input=f"Generate a reply for this tweet:\nTweet ID: {request.tweet_id}\nTweet Text: {request.tweet_text}\nPost Username: {request.post_username}"
    )
    
    return run_result.final_output 