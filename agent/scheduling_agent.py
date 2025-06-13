from typing import List, Optional, Dict, Any, Union, Tuple
from pydantic import BaseModel, Field, validator
from agents import Agent, Runner
from datetime import datetime, timedelta
import json

class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    is_available: bool
    reason: Optional[str] = None

class ScheduleResponse(BaseModel):
    scheduling_date: datetime

class ScheduleRequest(BaseModel):
    user_id: int
    account_id: int
    post_settings: Dict[str, Any] = Field(default_factory=dict)
    content: str
    risk_score: float = Field(default=0.0)

    @validator('post_settings', pre=True)
    def convert_tuple_to_dict(cls, v):
        if isinstance(v, tuple):
            # Get the first three values from the tuple, using None as default for missing values
            values = list(v) + [None] * (3 - len(v))  # Ensure we have at least 3 values
            posting_day, posting_time, posting_frequency = values[:3]  # Take only first 3 values
            
            # Create dictionary with only non-None values
            result = {}
            if posting_day is not None:
                result['posting_day'] = posting_day
            if posting_time is not None:
                result['posting_time'] = posting_time
            if posting_frequency is not None:
                result['posting_frequency'] = posting_frequency
                
            return result
        return v

    class Config:
        extra = "allow"  # Allow extra fields in the input

class SchedulingAgent:
    def __init__(self):
        """
        Initialize the Scheduling Agent for managing tweet schedules.
        """
        self.agent = Agent(
            name="Scheduling Agent",
            instructions=self._get_instructions(),
            output_type=ScheduleResponse
        )
    
    def _get_instructions(self) -> str:
        """Generate agent instructions"""
        return """You are a scheduling optimization expert for social media posts. Your task is to analyze time slots and create optimal schedules based on given constraints and preferences.

        Scheduling Guidelines:
        1. Posting Time MUST be in the future
        2. Post Settings Requirements:
           - You MUST only schedule posts on days specified in post_settings.posting_day
           - You MUST only schedule posts at times specified in post_settings.posting_time
           - If no posting_day is specified, you can use any day
           - If no posting_time is specified, you can use any time
           - Always ensure the scheduled time is in the future
        3. Consider posting frequency when scheduling multiple posts

        You must return a JSON object with this exact structure:
        {
            "scheduling_date": "datetime"
        }

        Example:
        If post_settings.posting_day = {"monday": true, "wednesday": true}
        and post_settings.posting_time = {"09:00": true, "15:00": true}
        Then you should only schedule posts on Mondays and Wednesdays at either 9 AM or 3 PM UTC."""
    
    async def get_response(self, request: ScheduleRequest) -> ScheduleResponse:
        """
        Analyze time slots and create optimal schedules for tweets.
        
        Args:
            request (ScheduleRequest): The request containing scheduling parameters
            
        Returns:
            ScheduleResponse: The scheduling results
        """
        try:
            # Parse post settings
            posting_day = request.post_settings.get('posting_day', {})
            posting_time = request.post_settings.get('posting_time', {})
            posting_frequency = request.post_settings.get('posting_frequency', 1)
            
            prompt = f"""Scheduling request:
            Current Time: {datetime.utcnow().isoformat()}
            Post Settings:
            - Posting Days: {json.dumps(posting_day)}
            - Posting Times: {json.dumps(posting_time)}
            - Posting Frequency: {posting_frequency}
            
            Content Details:
            - Risk Score: {request.risk_score}
            - Content Length: {len(request.content)}
            
            Please analyze these parameters and provide an optimal schedule."""
            
            result = await Runner.run(
                self.agent,
                prompt
            )
            return result.final_output
        except Exception as e:
            raise Exception(f"Error performing scheduling: {str(e)}")
    
    def add_handoff(self, other_agent: 'SchedulingAgent') -> None:
        """Add a handoff to another agent"""
        self.agent.handoffs.append(other_agent.agent) 