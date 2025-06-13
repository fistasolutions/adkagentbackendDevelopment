from typing import Optional, List
from agents import Agent, Runner
from pydantic import BaseModel
from fastapi import HTTPException

class DraftTweetRequest(BaseModel):
    previous_tweet: str
    num_drafts: int
    prompt: Optional[str] = None
    character_settings: Optional[str] = None

class DraftTweetResponse(BaseModel):
    draft_tweets: List[str]

class DraftTweetAgent:
    def __init__(self):
        """
        Initialize the Draft Tweet Agent for generating draft tweets based on previous tweets.
        """
        self.agent = Agent(
            name="Draft Tweet Generator",
            instructions=self._get_instructions(),
            output_type=DraftTweetResponse
        )
    
    def _get_instructions(self, character_settings: Optional[str] = None) -> str:
        """Generate agent instructions"""
        base_instructions = """You are a tweet generation assistant. Your task is to generate tweets based on a previous tweet.
        
        Rules:
        1. Analyze the previous tweet's style, tone, and content
        2. Generate draft tweets that maintain consistency with the previous tweet
        3. Each draft tweet should be under 280 characters
        4. Return the draft tweets in a structured format with a list of draft_tweets
        5. If the user mentions a specific language, translate the tweets to that language
        6. If no language is specified, keep the tweets in the same language as the previous tweet
        7. If a prompt is provided, use it to guide the generation of tweets
        
        The response must be in the following format:
        {
            "draft_tweets": [
                "First draft tweet",
                "Second draft tweet",
                ...
            ]
        }"""

        if character_settings:
            base_instructions += f"""

        Additionally, you must follow these character-specific guidelines:
        {character_settings}
        
        Character Voice Requirements:
        1. MUST use the exact speech patterns from character settings
        2. MUST maintain the character's unique personality
        3. MUST incorporate character's special abilities and interests
        4. MUST use the specified language and tone
        5. MUST ensure content aligns with character's background
        6. MUST maintain consistency with the character's established tone and approach
        
        Content Structure:
        1. Follow the character's typical posting patterns
        2. Include appropriate hashtags (2-3 per tweet)
        3. Maintain optimal length (240-280 characters)
        4. Include relevant emojis and media references
        5. Ensure content aligns with character's background
        6. Address any provided prompts while maintaining character voice
        """
        
        return base_instructions
    
    async def get_response(self, request: DraftTweetRequest) -> DraftTweetResponse:
        """
        Get draft tweets based on the previous tweet.
        
        Args:
            request (DraftTweetRequest): The request containing the previous tweet, number of drafts needed, optional prompt, and optional character settings
            
        Returns:
            DraftTweetResponse: The agent's response containing the draft tweets
        """
        try:
            # Update agent instructions with character settings if provided
            if request.character_settings:
                self.agent.instructions = self._get_instructions(request.character_settings)
            
            # Create the prompt for the agent
            prompt = f"""Previous tweet: {request.previous_tweet}
            Number of draft tweets needed: {request.num_drafts}"""
            
            if request.prompt:
                prompt += f"\nAdditional instructions: {request.prompt}"
            
            prompt += f"\n\nPlease generate {request.num_drafts} draft tweets that follow the style and tone of the previous tweet."
            
            result = await Runner.run(
                self.agent,
                prompt
            )
            return result.final_output
        except Exception as e:
            raise Exception(f"Error generating draft tweets: {str(e)}")
    
    def add_handoff(self, other_agent: 'DraftTweetAgent') -> None:
        """Add a handoff to another agent"""
        self.agent.handoffs.append(other_agent.agent) 