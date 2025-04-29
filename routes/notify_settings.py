from fastapi import APIRouter, HTTPException, Depends
from db.db import get_connection
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

class NotifySettingCreate(BaseModel):
    posting_day: str
    posting_time: str
    sentence_length: int
    notify_type: str
    template_use: bool
    target_hashtag: Optional[str] = None
    persona_id: int
    account_id: int

class NotifySettingUpdate(BaseModel):
    posting_day: Optional[str] = None
    posting_time: Optional[str] = None
    sentence_length: Optional[int] = None
    notify_type: Optional[str] = None
    template_use: Optional[bool] = None
    target_hashtag: Optional[str] = None
    account_id: Optional[int] = None

class NotifySettingResponse(BaseModel):
    notify_id: int
    posting_day: str
    posting_time: str
    sentence_length: int
    notify_type: str
    template_use: bool
    target_hashtag: Optional[str]
    persona_id: int
    account_id: int
    created_at: datetime

@router.post("/notify-settings", response_model=NotifySettingResponse)
async def create_notify_setting(notify_setting: NotifySettingCreate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if persona exists
            cursor.execute("SELECT id FROM personas WHERE id = %s", (notify_setting.persona_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Persona not found")
            
            # Check if account exists
            cursor.execute("SELECT account_id FROM twitter_account WHERE account_id = %s", (notify_setting.account_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Account not found")
            
            # Insert new notification setting
            cursor.execute(
                """INSERT INTO notify_settings 
                (posting_day, posting_time, sentence_length, notify_type, template_use, 
                target_hashtag, persona_id, account_id, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW()) 
                RETURNING notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, persona_id, account_id, created_at""",
                (
                    notify_setting.posting_day,
                    notify_setting.posting_time,
                    notify_setting.sentence_length,
                    notify_setting.notify_type,
                    notify_setting.template_use,
                    notify_setting.target_hashtag,
                    notify_setting.persona_id,
                    notify_setting.account_id
                )
            )
            
            setting = cursor.fetchone()
            conn.commit()
            
            return {
                "notify_id": setting[0],
                "posting_day": setting[1],
                "posting_time": setting[2],
                "sentence_length": setting[3],
                "notify_type": setting[4],
                "template_use": setting[5],
                "target_hashtag": setting[6],
                "persona_id": setting[7],
                "account_id": setting[8],
                "created_at": setting[9]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/notify-settings/", response_model=List[NotifySettingResponse])
async def get_all_notify_settings():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, persona_id, account_id, created_at 
                FROM notify_settings"""
            )
            settings = cursor.fetchall()
            return [
                {
                    "notify_id": setting[0],
                    "posting_day": setting[1],
                    "posting_time": setting[2],
                    "sentence_length": setting[3],
                    "notify_type": setting[4],
                    "template_use": setting[5],
                    "target_hashtag": setting[6],
                    "persona_id": setting[7],
                    "account_id": setting[8],
                    "created_at": setting[9]
                }
                for setting in settings
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/notify-settings/{notify_id}", response_model=NotifySettingResponse)
async def get_notify_setting(notify_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, persona_id, account_id, created_at 
                FROM notify_settings WHERE notify_id = %s""",
                (notify_id,)
            )
            setting = cursor.fetchone()
            if not setting:
                raise HTTPException(status_code=404, detail="Notification setting not found")
            return {
                "notify_id": setting[0],
                "posting_day": setting[1],
                "posting_time": setting[2],
                "sentence_length": setting[3],
                "notify_type": setting[4],
                "template_use": setting[5],
                "target_hashtag": setting[6],
                "persona_id": setting[7],
                "account_id": setting[8],
                "created_at": setting[9]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/notify-settings/persona/{persona_id}", response_model=List[NotifySettingResponse])
async def get_persona_notify_settings(persona_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, persona_id, account_id, created_at 
                FROM notify_settings WHERE persona_id = %s""",
                (persona_id,)
            )
            settings = cursor.fetchall()
            if not settings:
                return []
            return [
                {
                    "notify_id": setting[0],
                    "posting_day": setting[1],
                    "posting_time": setting[2],
                    "sentence_length": setting[3],
                    "notify_type": setting[4],
                    "template_use": setting[5],
                    "target_hashtag": setting[6],
                    "persona_id": setting[7],
                    "account_id": setting[8],
                    "created_at": setting[9]
                }
                for setting in settings
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.put("/notify-settings/{notify_id}", response_model=NotifySettingResponse)
async def update_notify_setting(notify_id: int, notify_setting: NotifySettingUpdate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if setting exists
            cursor.execute("SELECT notify_id FROM notify_settings WHERE notify_id = %s", (notify_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Notification setting not found")
            
            # Build update query dynamically based on provided fields
            update_fields = []
            update_values = []
            
            if notify_setting.posting_day is not None:
                update_fields.append("posting_day = %s")
                update_values.append(notify_setting.posting_day)
            
            if notify_setting.posting_time is not None:
                update_fields.append("posting_time = %s")
                update_values.append(notify_setting.posting_time)
            
            if notify_setting.sentence_length is not None:
                update_fields.append("sentence_length = %s")
                update_values.append(notify_setting.sentence_length)
            
            if notify_setting.notify_type is not None:
                update_fields.append("notify_type = %s")
                update_values.append(notify_setting.notify_type)
            
            if notify_setting.template_use is not None:
                update_fields.append("template_use = %s")
                update_values.append(notify_setting.template_use)
            
            if notify_setting.target_hashtag is not None:
                update_fields.append("target_hashtag = %s")
                update_values.append(notify_setting.target_hashtag)
            
            if notify_setting.account_id is not None:
                update_fields.append("account_id = %s")
                update_values.append(notify_setting.account_id)
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            # Add notify_id to the values list
            update_values.append(notify_id)
            
            # Execute update
            cursor.execute(
                f"""UPDATE notify_settings 
                SET {', '.join(update_fields)}
                WHERE notify_id = %s
                RETURNING notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, persona_id, account_id, created_at""",
                tuple(update_values)
            )
            
            updated_setting = cursor.fetchone()
            conn.commit()
            
            return {
                "notify_id": updated_setting[0],
                "posting_day": updated_setting[1],
                "posting_time": updated_setting[2],
                "sentence_length": updated_setting[3],
                "notify_type": updated_setting[4],
                "template_use": updated_setting[5],
                "target_hashtag": updated_setting[6],
                "persona_id": updated_setting[7],
                "account_id": updated_setting[8],
                "created_at": updated_setting[9]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.delete("/notify-settings/{notify_id}", response_model=dict)
async def delete_notify_setting(notify_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if setting exists
            cursor.execute("SELECT notify_id FROM notify_settings WHERE notify_id = %s", (notify_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Notification setting not found")
            
            # Delete setting
            cursor.execute("DELETE FROM notify_settings WHERE notify_id = %s", (notify_id,))
            conn.commit()
            
            return {"message": "Notification setting deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
