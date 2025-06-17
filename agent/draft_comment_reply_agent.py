from typing import Optional, List
from agents import Agent, Runner
from pydantic import BaseModel
from fastapi import HTTPException

class DraftCommentReplyRequest(BaseModel):
    previous_comment: str
    num_drafts: int
    prompt: Optional[str] = None
    character_settings: Optional[str] = None
    

class DraftCommentReplyResponse(BaseModel):
    draft_tweets: List[str]

class DraftCommentReplyAgent:
    def __init__(self):
        """
        Initialize the Draft Comment Reply Agent for generating draft comments based on previous comments.
        """
        self.agent = Agent(
            name="Draft Comment Reply Generator",
            instructions=self._get_instructions(),
            output_type=DraftCommentReplyResponse
        )
    
    def _get_instructions(self, character_settings: Optional[str] = None) -> str:
        """Generate agent instructions"""
        base_instructions = """You are a comment reply generation assistant. Your task is to generate comments based on a previous comment.
        
        Rules:
        1. Analyze the previous comment's style, tone, and content
        2. Generate draft comments that maintain consistency with the previous comment
        3. Each draft comment should be under 280 characters
        4. Return the draft comments in a structured format with a list of draft_comments
        5. If the user mentions a specific language, translate the tweets to that language
        6. If no language is specified, keep the tweets in the same language as the previous tweet
        7. If a prompt is provided, use it to guide the generation of tweets
        
        The response must be in the following format:
        {
            "draft_tweets": [
                "First draft comment",
                "Second draft comment",
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
    
    async def get_response(self, request: DraftCommentReplyRequest) -> DraftCommentReplyResponse:
        """
        Get draft comments based on the previous comment.
        
        Args:
            request (DraftCommentReplyRequest): The request containing the previous comment, number of drafts needed, optional prompt, and optional character settings
            
        Returns:
            DraftCommentReplyResponse: The agent's response containing the draft comments
        """
        try:
            # Update agent instructions with character settings if provided
            if request.character_settings:
                self.agent.instructions = self._get_instructions(request.character_settings)
            
            # Create the prompt for the agent
            prompt = f"""Previous comment: {request.previous_comment}
            Number of draft comments needed: {request.num_drafts}"""
            
            if request.prompt:
                prompt += f"\nAdditional instructions: {request.prompt}"
            
            prompt += f"\n\nPlease generate {request.num_drafts} draft comments that follow the style and tone of the previous comment."
            
            result = await Runner.run(
                self.agent,
                prompt
            )
            return result.final_output
        except Exception as e:
            raise Exception(f"Error generating draft comments: {str(e)}")
    
    def add_handoff(self, other_agent: 'DraftCommentReplyAgent') -> None:
        """Add a handoff to another agent"""
        self.agent.handoffs.append(other_agent.agent) 