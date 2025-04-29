from fastapi import FastAPI
from db.db import get_connection
from routes.users import router as user_router
from routes.twitter import router as twitter_router
import os
from routes.persona import router as persona_router
from routes.agent_routes import router as agent_router
from routes.adk_agent_routes import router as adk_agent_router
from routes.forgotPassword import router as forgot_password_router
from routes.twitter_account import router as twitter_account_router
from routes.agent_settings import router as agent_settings_router
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
origins = [
    "http://localhost:3000",
    "https://adkaiagentfrontend.vercel.app"
]
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],     # Or ["GET", "POST"]
    allow_headers=["*"],
)
# Include the user routes
app.include_router(user_router, prefix="/api")
app.include_router(twitter_router, prefix="/api")
app.include_router(persona_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(adk_agent_router, prefix="/api")
app.include_router(forgot_password_router, prefix="/api")
app.include_router(twitter_account_router, prefix="/api")
app.include_router(agent_settings_router, prefix="/api")


@app.get("/")
async def root():
    try:
        conn = get_connection()
        # Test the connection
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        return {"status": "success", "message": "Database connection is working"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    
    
    
