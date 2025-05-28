from typing import List
from agents import Agent, Runner
from pydantic import BaseModel

class EventBasedTweetRequest(BaseModel):
    event_title: str
    event_details: str

class EventBasedTweetResponse(BaseModel):
    tweet_content: str

class EventBasedTweetAgent:
    def __init__(self):
        """
        Initialize the Event Based Tweet Agent for generating tweets based on event information.
        """
        self.agent = Agent(
            name="Event Based Tweet Generator",
            instructions=self._get_instructions(),
            output_type=EventBasedTweetResponse
        )
    
    def _get_instructions(self) -> str:
        """Generate agent instructions"""
        return """You are a tweet generation assistant specialized in creating engaging tweets based on event information.
        
        Rules:
        1. Generate an engaging and relevant tweet based on the provided event title and details
        2. The tweet should be under 280 characters
        3. Maintain a professional yet engaging tone
        4. Include relevant hashtags related to the event
        5. Focus on creating excitement and interest in the event
        6. Keep the language clear and concise
        7. If the event details are in Japanese, respond in Japanese
        8. If the event details are in English, respond in English
        
        The response must be in the following format:
        {
            "tweet_content": "Your generated tweet here"
        }"""
    
    async def get_response(self, request: EventBasedTweetRequest) -> EventBasedTweetResponse:
        """
        Get a tweet based on event information.
        
        Args:
            request (EventBasedTweetRequest): The request containing event title and details
            
        Returns:
            EventBasedTweetResponse: The agent's response containing the generated tweet
        """
        try:
            # Create the prompt for the agent
            prompt = f"""Event Title: {request.event_title}
            Event Details: {request.event_details}
            
            Please generate an engaging tweet based on this event information."""
            
            result = await Runner.run(
                self.agent,
                prompt
            )
            return result.final_output
        except Exception as e:
            raise Exception(f"Error generating tweet: {str(e)}")
    
    def add_handoff(self, other_agent: 'EventBasedTweetAgent') -> None:
        """Add a handoff to another agent"""
        self.agent.handoffs.append(other_agent.agent) 