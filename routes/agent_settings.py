from fastapi import APIRouter, HTTPException, Depends
from db.db import get_connection
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

class AgentSettingCreate(BaseModel):
    user_id: int
    character_settings: str
    username: str

class AgentSettingUpdate(BaseModel):
    character_settings: str
    username: str

class AgentSettingResponse(BaseModel):
    id: int
    user_id: int
    character_settings: str
    created_at: datetime

@router.post("/agent-settings/", response_model=AgentSettingResponse)
async def create_agent_setting(agent_setting: AgentSettingCreate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if user exists
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (agent_setting.user_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
            
            # Get account_id from username
            cursor.execute("SELECT account_id FROM twitter_account WHERE username = %s", (agent_setting.username,))
            account_result = cursor.fetchone()
            if not account_result:
                raise HTTPException(status_code=404, detail="Twitter account not found")
            account_id = account_result[0]
            
            # Check if persona already exists for this user_id and account_id
            cursor.execute(
                "SELECT id FROM personas WHERE user_id = %s AND account_id = %s",
                (agent_setting.user_id, account_id)
            )
            existing_persona = cursor.fetchone()
            
            if existing_persona:
                # Update existing persona
                cursor.execute(
                    "UPDATE personas SET character_settings = %s WHERE id = %s RETURNING id, user_id, character_settings, account_id, created_at",
                    (agent_setting.character_settings, existing_persona[0])
                )
            else:
                # Insert new persona
                cursor.execute(
                    "INSERT INTO personas (user_id, character_settings, account_id, created_at) VALUES (%s, %s, %s, NOW()) RETURNING id, user_id, character_settings, account_id, created_at",
                    (agent_setting.user_id, agent_setting.character_settings, account_id)
                )
            
            setting = cursor.fetchone()
            conn.commit()
            
            return {
                "id": setting[0],
                "user_id": setting[1],
                "character_settings": setting[2],
                "account_id": setting[3],
                "created_at": setting[4]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/agent-settings/", response_model=List[AgentSettingResponse])
async def get_all_agent_settings():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, user_id, character_settings, account_id, created_at FROM personas")
            settings = cursor.fetchall()
            return [
                {
                    "id": setting[0], 
                    "user_id": setting[1], 
                    "character_settings": setting[2],
                    "account_id": setting[3],
                    "created_at": setting[4]
                } 
                for setting in settings
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/agent-settings/{setting_id}", response_model=AgentSettingResponse)
async def get_agent_setting(setting_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, user_id, character_settings, account_id, created_at FROM personas WHERE id = %s", (setting_id,))
            setting = cursor.fetchone()
            if not setting:
                raise HTTPException(status_code=404, detail="Agent setting not found")
            return {
                "id": setting[0],
                "user_id": setting[1],
                "character_settings": setting[2],
                "account_id": setting[3],
                "created_at": setting[4]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/agent-settings/user/{user_id}", response_model=List[AgentSettingResponse])
async def get_user_agent_settings(user_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, user_id, character_settings, account_id, created_at FROM personas WHERE user_id = %s", (user_id,))
            settings = cursor.fetchall()
            if not settings:
                return []
            return [
                {
                    "id": setting[0], 
                    "user_id": setting[1], 
                    "character_settings": setting[2],
                    "account_id": setting[3],
                    "created_at": setting[4]
                } 
                for setting in settings
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.put("/agent-settings/{setting_id}", response_model=AgentSettingResponse)
async def update_agent_setting(setting_id: int, agent_setting: AgentSettingUpdate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if setting exists
            cursor.execute("SELECT id FROM personas WHERE id = %s", (setting_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Agent setting not found")
            
            # Update setting
            cursor.execute(
                "UPDATE personas SET character_settings = %s, account_id = %s WHERE id = %s RETURNING id, user_id, character_settings, account_id, created_at",
                (agent_setting.character_settings, agent_setting.account_id, setting_id)
            )
            updated_setting = cursor.fetchone()
            conn.commit()
            
            return {
                "id": updated_setting[0],
                "user_id": updated_setting[1],
                "character_settings": updated_setting[2],
                "account_id": updated_setting[3],
                "created_at": updated_setting[4]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.delete("/agent-settings/{setting_id}", response_model=dict)
async def delete_agent_setting(setting_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if setting exists
            cursor.execute("SELECT id FROM personas WHERE id = %s", (setting_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Agent setting not found")
            
            # Delete setting
            cursor.execute("DELETE FROM personas WHERE id = %s", (setting_id,))
            conn.commit()
            
            return {"message": "Agent setting deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
