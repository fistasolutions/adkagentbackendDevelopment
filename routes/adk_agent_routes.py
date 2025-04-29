from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from agent.adkagent import ADKAgent, TweetAgentSettings, CharacterSettings, ChatAgent, ChatSettings
import uuid
import os
from openai import OpenAI
import pinecone
from pinecone import Pinecone

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("adkagent")  # use your index name
# Store agents in memory (you might want to use a database in production)
agents = {}

# Store chat agents in memory
chat_agents = {}

class CreateTweetAgentRequest(BaseModel):
    persona_id: str

class UpdateTweetAgentRequest(BaseModel):
    persona_id: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    tools: Optional[List[Dict[str, Any]]] = None

class CreateChatAgentRequest(BaseModel):
    instructions: str

class GenerateTweetsRequest(BaseModel):
    topic: Optional[str] = None

async def get_characterSettings(persona_id: str) -> CharacterSettings:
    """Fetch character settings from Pinecone"""
    try:
        result = index.fetch(ids=[persona_id])
        if not result.vectors:
            raise HTTPException(status_code=404, detail="Persona not found")
        
        vector = result.vectors[persona_id]
        metadata = vector.metadata
        
        # Convert the metadata to match our CharacterSettings model
        characterSettings = CharacterSettings(
            characterSettings=metadata.get("characterSettings", "")
        )
        
        return characterSettings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tweet-agents")
async def create_tweet_agent(request: CreateTweetAgentRequest):
    """Create a new tweet generation agent"""
    try:
        # Fetch character settings from Pinecone
        # characterSettings = await get_characterSettings(request.persona_id)
        
        agent_id = str(uuid.uuid4())
        settings = TweetAgentSettings(
            id=agent_id,
            characterSettings="You are a social media expert who creates engaging and relevant tweets."
        )
        
        agent = ADKAgent(settings=settings)
        agents[agent_id] = agent
        
        initial_tweet = await agent.get_response(
            message="Generate a tweet that introduces yourself and your role",
        )
        
        return {
            "tweet": initial_tweet,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat-agents")
async def create_chat_agent(request: CreateChatAgentRequest):
    """Create a new chat agent"""
    try:
        agent_id = str(uuid.uuid4())
        settings = ChatSettings(
            id=agent_id,
            instructions=request.instructions
        )
        
        agent = ChatAgent(settings=settings)
        chat_agents[agent_id] = agent
        result = await agent.get_response(request.instructions)
        print(result)
        return {
            "agent_id": agent_id,
            "output": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-tweets")
async def generate_tweets(request: GenerateTweetsRequest):
    """Generate 5 tweets using an existing agent with persona-specific settings"""
    try:
        
        
        
        agent_id = str(uuid.uuid4())
        characterSettings = CharacterSettings(
            characterSettings="You are a social media expert who creates engaging and relevant tweets."
        )
        
        settings = TweetAgentSettings(
            id=agent_id,
            characterSettings=characterSettings
        )
        
        agent = ADKAgent(settings=settings)
        tweets = []
        
        # Generate 5 tweets
        for i in range(5):
            prompt = "Generate a tweet"
            if request.topic:
                prompt += f" about {request.topic}"
            
            tweet = await agent.get_response(message=prompt)
            tweets.append(tweet)
        
        return {
            "tweets": tweets
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




