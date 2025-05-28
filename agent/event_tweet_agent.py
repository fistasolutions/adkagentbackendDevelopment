from typing import Optional, List
from agents import Agent, Runner
from pydantic import BaseModel
from fastapi import HTTPException
from datetime import datetime

class EventTweetRequest(BaseModel):
    num_drafts: int
    prompt: str
    date: Optional[str] = None

class EventTweetResponse(BaseModel):
    draft_tweets: List[str]

class EventTweetAgent:
    def __init__(self):
        """
        Initialize the Event Tweet Agent for generating tweets based on events and prompts.
        """
        self.agent = Agent(
            name="Event Tweet Generator",
            instructions=self._get_instructions(),
            output_type=EventTweetResponse
        )
    
    def _get_instructions(self) -> str:
        """Generate agent instructions"""
        return """You are a tweet generation assistant specialized in creating event-based tweets, with a focus on Japanese events and culture.
        
        Rules:
        1. Generate engaging and relevant tweets based on the provided prompt
        2. Each tweet should be under 280 characters
        3. If an event is provided, incorporate it naturally into the tweets
        4. Use appropriate hashtags related to the event or topic
        5. Maintain a professional yet engaging tone
        6. If the user mentions a specific language, translate the tweets to that language
        7. If no language is specified, keep the tweets in English
        8. When checking for events on a specific date, ONLY consider:
           - Official Japanese national holidays (as defined by Japanese law)
           - Major Japanese cultural events and festivals
           - Seasonal events in Japan (like cherry blossom season, etc.)
           - Major technology events in Japan
           - DO NOT include events from other countries unless they are widely recognized in Japan
           - DO NOT make up or assume events - only include events you are certain about
           - If unsure about an event, do not include it
        
        The response must be in the following format:
        {
            "draft_tweets": [
                "First draft tweet",
                "Second draft tweet",
                ...
            ]
        }"""
    
    def _get_event_info(self, date_str: Optional[str]) -> str:
        """Get information about events on the specified date"""
        if not date_str:
            return ""
            
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return f"Date to check for events: {date_str}"
        except ValueError:
            return ""
    
    async def get_response(self, request: EventTweetRequest) -> EventTweetResponse:
        """
        Get draft tweets based on events and prompt.
        
        Args:
            request (EventTweetRequest): The request containing the number of drafts needed, prompt, and optional date
            
        Returns:
            EventTweetResponse: The agent's response containing the draft tweets
        """
        try:
            # Get event information if date is provided
            event_info = self._get_event_info(request.date)
            
            # Create the prompt for the agent
            prompt = f"""Number of draft tweets needed: {request.num_drafts}
            User's prompt: {request.prompt}"""
            
            if event_info:
                prompt += f"\n{event_info}"
                prompt += "\nPlease check if there are any significant events on this date. IMPORTANT: Only include events that are officially recognized in Japan or are major cultural events in Japan. Do not include events from other countries unless they are widely recognized in Japan. If you are unsure about an event, do not include it."
            
            prompt += f"\n\nPlease generate {request.num_drafts} engaging tweets based on the above information. If you identified any events for the date, incorporate them naturally into the tweets. If no specific events are found for the date, focus on the user's prompt without mentioning any events."
            
            result = await Runner.run(
                self.agent,
                prompt
            )
            return result.final_output
        except Exception as e:
            raise Exception(f"Error generating draft tweets: {str(e)}")
    
    def add_handoff(self, other_agent: 'EventTweetAgent') -> None:
        """Add a handoff to another agent"""
        self.agent.handoffs.append(other_agent.agent) 