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
        characterSettings = await get_characterSettings(request.persona_id)
        
        agent_id = str(uuid.uuid4())
        settings = TweetAgentSettings(
            id=agent_id,
            characterSettings=characterSettings
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

@router.get("/tweet-agents/{agent_id}")
async def get_tweet_agent(agent_id: str):
    """Get tweet agent details"""
    try:
        if agent_id not in agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Generate a new tweet to demonstrate the agent's current state
        current_tweet = await agents[agent_id].get_response(
            message="Generate a tweet that shows your current personality and style",
        )
        
        return {
            "agent_id": agent_id,
            "tweet": current_tweet,
            "character_settings": agents[agent_id].settings.characterSettings
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/tweet-agents/{agent_id}/generate")
async def generate_tweet(agent_id: str, request: ChatRequest):
    """Generate a tweet using the agent"""
    try:
        if agent_id not in agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        response = await agents[agent_id].get_response(
            message=request.message,
            tools=request.tools
        )
        return {"tweet": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tweet-agents/{from_agent_id}/handoff/{to_agent_id}")
async def setup_handoff(from_agent_id: str, to_agent_id: str):
    """Set up a handoff between two tweet agents"""
    try:
        if from_agent_id not in agents:
            raise HTTPException(status_code=404, detail="From agent not found")
            
        if to_agent_id not in agents:
            raise HTTPException(status_code=404, detail="To agent not found")
            
        agents[from_agent_id].add_handoff(agents[to_agent_id])
        return {"message": f"Handoff set up from {from_agent_id} to {to_agent_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/{agent_id}")
async def chat_with_agent(agent_id: str, request: ChatRequest):
    """Simple chat endpoint to interact with an agent"""
    try:
        if agent_id not in agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        response = await agents[agent_id].get_response(
            message=request.message,
            tools=request.tools
        )
        return {"response": response}
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

@router.post("/chat-agents/{agent_id}/chat")
async def chat_with_agent(agent_id: str, request: ChatRequest):
    """Chat with a chat agent"""
    try:
        if agent_id not in chat_agents:
            raise HTTPException(status_code=404, detail="Chat agent not found")
        
        response = await chat_agents[agent_id].get_response(
            message=request.message
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
