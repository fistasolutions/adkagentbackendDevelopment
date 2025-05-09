from fastapi import APIRouter, HTTPException, Depends
from db.db import get_connection
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

router = APIRouter()

class NotifySettingCreate(BaseModel):
    posting_day: Dict[str, Any]
    posting_time: Dict[str, Any]
    sentence_length: int
    notify_type: str
    template_use: bool
    target_hashtag: Optional[str] = None
    user_id: int
    account_id: int
    created_at: datetime
    posting_frequency: str
    pre_create: str
    post_mode: bool
    template: str

class NotifySettingUpdate(BaseModel):
    posting_day: Optional[Dict[str, Any]] = None
    posting_time: Optional[Dict[str, Any]] = None
    sentence_length: Optional[int] = None
    notify_type: Optional[str] = None
    template_use: Optional[bool] = None
    target_hashtag: Optional[str] = None
    account_id: Optional[int] = None

class PostModeUpdate(BaseModel):
    post_mode: bool

class NotifySettingResponse(BaseModel):
    notify_id: int
    posting_day: Dict[str, Any]
    posting_time: Dict[str, Any]
    sentence_length: int
    notify_type: str
    template_use: bool
    target_hashtag: Optional[str]
    user_id: int
    account_id: int
    created_at: datetime
    posting_frequency: str
    pre_create: str
    post_mode: bool
    template: str

@router.post("/notify-settings", response_model=NotifySettingResponse)
async def create_notify_setting(notify_setting: NotifySettingCreate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if persona exists
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (notify_setting.user_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
            
            # Check if account exists
            cursor.execute("SELECT account_id FROM twitter_account WHERE account_id = %s", (notify_setting.account_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Account not found")

            # Check if record with same user_id, account_id and notify_type exists
            cursor.execute(
                """SELECT notify_id FROM persona_notify 
                WHERE user_id = %s AND account_id = %s AND notify_type = %s""",
                (notify_setting.user_id, notify_setting.account_id, notify_setting.notify_type)
            )
            existing_record = cursor.fetchone()
            
            # If record exists, delete it
            if existing_record:
                cursor.execute(
                    "DELETE FROM persona_notify WHERE notify_id = %s",
                    (existing_record[0],)
                )
            
            # Insert new notification setting
            cursor.execute(
                """INSERT INTO persona_notify 
                (posting_day, posting_time, sentence_length, notify_type, template_use, 
                target_hashtag, user_id, account_id, created_at,posting_frequency,pre_create,post_mode,template_text) 
                VALUES (%s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, NOW(),%s,%s,%s,%s) 
                RETURNING notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, user_id, account_id, created_at,posting_frequency,pre_create,post_mode,template_text""",
                (
                    json.dumps(notify_setting.posting_day),
                    json.dumps(notify_setting.posting_time),
                    notify_setting.sentence_length,
                    notify_setting.notify_type,
                    notify_setting.template_use,
                    notify_setting.target_hashtag,
                    notify_setting.user_id,
                    notify_setting.account_id,
                    notify_setting.posting_frequency,
                    notify_setting.pre_create,
                    notify_setting.post_mode,
                    notify_setting.template
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
                "user_id": setting[7],
                "account_id": setting[8],
                "created_at": setting[9],
                "posting_frequency": setting[10],
                "pre_create": setting[11],
                "post_mode": setting[12],
                "template": setting[13]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/notify-settings/", response_model=List[NotifySettingResponse])
async def get_all_persona_notify():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, user_id, account_id, created_at,posting_frequency,pre_create,post_mode,template_text
                FROM persona_notify"""
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
                    "user_id": setting[7],
                    "account_id": setting[8],
                    "created_at": setting[9],
                    "posting_frequency": setting[10],
                    "pre_create": setting[11],
                    "post_mode": setting[12],
                    "template": setting[13]
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
                notify_type, template_use, target_hashtag, user_id, account_id, created_at,posting_frequency,pre_create,post_mode,template_text
                FROM persona_notify WHERE notify_id = %s""",
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
                "user_id": setting[7],
                "account_id": setting[8],
                "created_at": setting[9],
                "posting_frequency": setting[10],
                "pre_create": setting[11],
                "post_mode": setting[12],
                "template": setting[13]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/notify-settings/persona/{user_id}/{username}", response_model=List[NotifySettingResponse])
async def get_persona_notify_settings(user_id: int, username: str):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if twitter account exists
            cursor.execute("SELECT account_id FROM twitter_account WHERE username = %s AND user_id = %s", (username, user_id))
            account_result = cursor.fetchone()
            if not account_result:
                raise HTTPException(status_code=404, detail="Twitter account not found")
            account_id = account_result[0]
            
            # Get notification settings
            cursor.execute(
                """SELECT notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, user_id, account_id, created_at,posting_frequency,pre_create,post_mode,template_text
                FROM persona_notify WHERE user_id = %s AND account_id = %s""",
                (user_id, account_id)
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
                    "user_id": setting[7],
                    "account_id": setting[8],
                    "created_at": setting[9],
                    "posting_frequency": setting[10],
                    "pre_create": setting[11],
                    "post_mode": setting[12],
                    "template": setting[13]
                }
                for setting in settings
            ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving notification settings: {str(e)}")
    finally:
        conn.close()

@router.put("/notify-settings/{notify_id}", response_model=NotifySettingResponse)
async def update_notify_setting(notify_id: int, notify_setting: NotifySettingUpdate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if setting exists
            cursor.execute("SELECT notify_id FROM persona_notify WHERE notify_id = %s", (notify_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Notification setting not found")
            
            # Build update query dynamically based on provided fields
            update_fields = []
            update_values = []
            
            if notify_setting.posting_day is not None:
                update_fields.append("posting_day = %s::jsonb")
                update_values.append(json.dumps(notify_setting.posting_day))
            
            if notify_setting.posting_time is not None:
                update_fields.append("posting_time = %s::jsonb")
                update_values.append(json.dumps(notify_setting.posting_time))
            
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
                f"""UPDATE persona_notify 
                SET {', '.join(update_fields)}
                WHERE notify_id = %s
                RETURNING notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, user_id, account_id, created_at,posting_frequency,pre_create,post_mode,template_text""",
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
                "user_id": updated_setting[7],
                "account_id": updated_setting[8],
                "created_at": updated_setting[9],
                "posting_frequency": updated_setting[10],
                "pre_create": updated_setting[11],
                "post_mode": updated_setting[12],
                "template": updated_setting[13]
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
            cursor.execute("SELECT notify_id FROM persona_notify WHERE notify_id = %s", (notify_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Notification setting not found")
            
            # Delete setting
            cursor.execute("DELETE FROM persona_notify WHERE notify_id = %s", (notify_id,))
            conn.commit()
            
            return {"message": "Notification setting deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.put("/notify-settings/user/{user_id}/post-mode/{account_id}", response_model=List[NotifySettingResponse])
async def update_user_post_mode(user_id: int, account_id: int, post_mode_update: PostModeUpdate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if user exists
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
            
            # Update post_mode for all notification settings of the user
            cursor.execute(
                """UPDATE persona_notify 
                SET post_mode = %s
                WHERE user_id = %s
                AND account_id = %s
                AND notify_type = 'post'
                RETURNING notify_id, posting_day, posting_time, sentence_length, 
                notify_type, template_use, target_hashtag, user_id, account_id, created_at,
                posting_frequency, pre_create, post_mode, template_text""",
                (post_mode_update.post_mode, user_id, account_id)
            )
            
            updated_settings = cursor.fetchall()
            conn.commit()
            
            if not updated_settings:
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
                    "user_id": setting[7],
                    "account_id": setting[8],
                    "created_at": setting[9],
                    "posting_frequency": setting[10],
                    "pre_create": setting[11],
                    "post_mode": setting[12],
                    "template": setting[13]
                }
                for setting in updated_settings
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()



