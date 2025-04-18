from typing import Optional, List, Dict, Any
from agents import Agent, Runner
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi import HTTPException

load_dotenv()

class CharacterSettings(BaseModel):
    characterSettings: str
    
class Tweet(BaseModel):
    tweet1: str
    tweet2: str

class TweetAgentSettings(BaseModel):
    id: Optional[str] = None
    characterSettings: Optional[CharacterSettings] = None

class ADKAgent:
    def __init__(self, settings: Optional[TweetAgentSettings] = None):
        """
        Initialize the ADK Agent for tweet generation.
        
        Args:
            settings (Optional[TweetAgentSettings]): Settings for tweet generation
        """
        if settings:
            self.settings = settings
            self.agent = Agent(
                name="ADK Agent",
                instructions=self._generate_instructions(settings),
                output_type=Tweet
            )
        else:
            self.settings = None
            self.agent = Agent(
                name="ADK Agent",
                instructions="You are a tweet generation assistant. Help users create engaging tweets.",
                output_type=Tweet
            )
    
    def _generate_instructions(self, settings: TweetAgentSettings) -> str:
        """Generate agent instructions from settings"""
        character_context = ""
        if settings.characterSettings:
            character = settings.characterSettings
            character_context = f"""
            Character Context:
            {character.characterSettings}
            """
        
        return f"""You are a tweet generation assistant.
        
        {character_context}
        
        Generate two tweets that match the character context above.
        Keep tweets under 280 characters.
        Return the tweets in a structured format with tweet1 and tweet2 fields."""
    
    async def get_response(self, message: str) -> Tweet:
        """
        Get a response from the agent using the SDK's Runner.
        
        Args:
            message (str): The user's message/query
            tools (Optional[List[Dict[str, Any]]]): List of tools to make available to the agent
            
        Returns:
            Tweet: The agent's response containing two tweets
        """
        try:
            result = await Runner.run(
                self.agent,
                message,
                # tools=tools
            )
            return result.final_output
        except Exception as e:
            raise Exception(f"Error generating response: {str(e)}")
    
    def add_handoff(self, other_agent: 'ADKAgent') -> None:
        """Add a handoff to another agent"""
        self.agent.handoffs.append(other_agent.agent)

class ChatSettings(BaseModel):
    id: Optional[str] = None
    instructions: str

class ChatAgent:
    def __init__(self, settings: ChatSettings):
        """
        Initialize the Twitter Agent that answers based only on the Twitter AI Agent system design document.
        
        Args:
            settings (ChatSettings): Settings for chat behavior
        """
        settings.instructions = (
                "You are a Twitter Automation Agent designed to assist users in understanding and using the "
            "This includes:\n"
            "- AI-powered tweet generation based on personas and trends\n"
            "- Risk scoring and content safety detection\n"
            "- Scheduling posts for future publication\n"
            "- Publishing to Twitter/X via API\n"
            "- Tracking and analyzing engagement metrics\n"
            "- Improving content strategy using AI suggestions\n\n"
            "Your role is to act as a knowledge interface to the Twitter Agent system. Do NOT use outside knowledge.\n"
            "✅ Be clear, concise, and technical when needed. Only refer to functionality, architecture, and processes described in the document."
        )
        
        self.settings = settings
        self.agent = Agent(
            name="Twitter AI Agent",
            instructions=settings.instructions,
            output_type=str
        )

    async def get_response(self, instructions: str) -> str:
        """
        Get a response from the agent using the SDK's Runner.

        Args:
            instructions (str): The user's message/query

        Returns:
            str: The agent's response
        """
        try:
            result = await Runner.run(
                self.agent,
                instructions
            )
            return result.final_output
        except Exception as e:
            raise Exception(f"Error generating response: {str(e)}")
