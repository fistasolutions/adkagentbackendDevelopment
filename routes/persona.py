from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import os
from openai import OpenAI
import pinecone
from pinecone import Pinecone

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("adkagent")  # use your index name


class PersonaInput(BaseModel):
    id: str  # unique ID for persona
    characterSettings: str


def generate_embedding(persona: PersonaInput):
    # Combine tone, keywords, and sentiment into one string
    text = f"Tone: {persona.characterSettings}."
    
    # Call OpenAI to get the embedding with reduced dimensions
    response = client.embeddings.create(
        input=[text],
        model="text-embedding-3-small",
        dimensions=1024  # Specify 1024 dimensions to match Pinecone index
    )
    return response.data[0].embedding


@router.post("/persona/embed")
async def embed_persona(persona: PersonaInput):
    print(persona)
    if not persona.characterSettings:
        raise HTTPException(status_code=400, detail="All fields must be provided.")

    embedding = generate_embedding(persona)

    # Upsert into Pinecone
    index.upsert(vectors=[(persona.id, embedding, {"characterSettings": persona.characterSettings})])

    return {"status": "success", "id": persona.id}


@router.get("/persona/{persona_id}")
async def get_persona(persona_id: str):
    try:
        # Fetch the vector from Pinecone
        result = index.fetch(ids=[persona_id])
        
        if not result.vectors:
            raise HTTPException(status_code=404, detail="Persona not found")
            
        vector = result.vectors[persona_id]
        return {
            "id": persona_id,
            "characterSettings": vector.metadata["characterSettings"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
