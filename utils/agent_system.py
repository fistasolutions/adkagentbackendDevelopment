from typing import Dict, Optional
import openai
from fastapi import  HTTPException
from pinecone import Pinecone
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class CharacterSettings(BaseModel):
    id: str
    name: str
    personality: str
    background: str
    goals: str
    constraints: str
    examples: str

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("adkagent")

class AgentSystem:
    def get_character(self, character_id: str):  # Add self here
        try:
            result = index.fetch(ids=[character_id])
            if not result.vectors:
                raise HTTPException(status_code=404, detail="Character not found")
            vector = result.vectors[character_id]
            return {
                "id": character_id,
                "characterSettings": vector.metadata["characterSettings"],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    def generate_response(self, character_id: str, user_input: str) -> str:
        """Generate a response using the character's settings"""
        characterSettings = self.get_character(character_id)
        if not characterSettings:
            return "Character not found"
        
        system_message = f"""
        {characterSettings}.
        
        Stay in character and respond to the user's input."""
        
        # Generate response using OpenAI
        response = client.chat.completions.create(
            model="adkagent",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input}
            ]
        )
        
        return response.choices[0].message.content 