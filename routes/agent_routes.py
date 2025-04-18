import os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.agent_system import AgentSystem, CharacterSettings
from agents.agent import Agent
from agents import Runner

router = APIRouter()
agent_system = AgentSystem()

class CharacterCreate(BaseModel):
    name: str
    personality: str
    background: str
    goals: str
    constraints: str
    examples: str

class ChatRequest(BaseModel):
    character_id: str
    message: str

class ChatWithAgentRequest(BaseModel):
    message: str



load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

@router.post("/characters")
async def create_character(character: CharacterCreate):
    """Create a new character and store it in Pinecone"""
    try:
        import uuid
        character_id = str(uuid.uuid4())
        
        # Create character settings
        character_settings = CharacterSettings(
            id=character_id,
            **character.dict()
        )
        
        # Save to Pinecone
        agent_system.save_character(character_settings)
        
        return {"character_id": character_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/characters/{character_id}")
async def get_character(character_id: str):
    """Retrieve character settings by ID"""
    character = agent_system.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character

@router.post("/chat")
async def chat(request: ChatRequest):
    """Generate a response from the character"""
    try:
        response = agent_system.generate_response(
            character_id=request.character_id,
            user_input=request.message
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat-with-agent")
async def chat_with_agent(request: ChatWithAgentRequest):
    """Chat with the agent with optional instructions"""
    try:
        agent = Agent(  
            name="Assistant",
            instructions="You are a helpful assistant",
            model="gpt-4"
        )
        
        response = await Runner.run(agent, request.message)
        
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
    