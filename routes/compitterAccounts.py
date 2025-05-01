from fastapi import APIRouter, HTTPException, Depends
from db.db import get_connection
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

router = APIRouter()

class PersonaSafetyCreate(BaseModel):
    role_models: Optional[Dict[str, Any]] = None
    industry_standard: Optional[Dict[str, Any]] = None
    competition: Optional[Dict[str, Any]] = None
    user_id: int
    account_id: int

class PersonaSafetyUpdate(BaseModel):
    role_models: Optional[Dict[str, Any]] = None
    industry_standard: Optional[Dict[str, Any]] = None
    competition: Optional[Dict[str, Any]] = None
    account_id: Optional[int] = None

class PersonaSafetyResponse(BaseModel):
    id: int
    role_models: Optional[Dict[str, Any]] = None
    industry_standard: Optional[Dict[str, Any]] = None
    competition: Optional[Dict[str, Any]] = None
    user_id: int
    account_id: int
    created_at: datetime

@router.post("/persona-safety", response_model=PersonaSafetyResponse)
async def create_persona_safety(persona_safety: PersonaSafetyCreate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if user exists
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (persona_safety.user_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
            
            # Check if account exists
            cursor.execute("SELECT account_id FROM twitter_account WHERE account_id = %s", (persona_safety.account_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Account not found")

            # Check if record with same user_id and account_id exists
            cursor.execute(
                """SELECT id FROM persona_safety 
                WHERE user_id = %s AND account_id = %s""",
                (persona_safety.user_id, persona_safety.account_id)
            )
            existing_record = cursor.fetchone()  
            
            if existing_record:
                update_fields = []
                update_values = []
                
                if persona_safety.role_models is not None:
                    update_fields.append("role_models = %s::jsonb")
                    update_values.append(json.dumps(persona_safety.role_models))
                
                if persona_safety.industry_standard is not None:
                    update_fields.append("industry_standard = %s::jsonb")
                    update_values.append(json.dumps(persona_safety.industry_standard))
                
                if persona_safety.competition is not None:
                    update_fields.append("competition = %s::jsonb")
                    update_values.append(json.dumps(persona_safety.competition))
                
                if update_fields:
                    update_values.append(existing_record[0])
                    cursor.execute(
                        f"""UPDATE persona_safety 
                        SET {', '.join(update_fields)}
                        WHERE id = %s
                        RETURNING id, role_models, industry_standard, competition, 
                        user_id, account_id, created_at""",
                        tuple(update_values)
                    )
                    safety = cursor.fetchone()
                else:
                    # If no fields to update, just fetch the existing record
                    cursor.execute(
                        """SELECT id, role_models, industry_standard, competition, 
                        user_id, account_id, created_at 
                        FROM persona_safety WHERE id = %s""",
                        (existing_record[0],)
                    )
                    safety = cursor.fetchone()
            else:
                # Insert new safety setting with only provided fields
                fields = ["user_id", "account_id", "created_at"]
                values = [persona_safety.user_id, persona_safety.account_id]
                placeholders = ["%s", "%s", "NOW()"]
                
                if persona_safety.role_models is not None:
                    fields.append("role_models")
                    values.append(json.dumps(persona_safety.role_models))
                    placeholders.append("%s::jsonb")
                
                if persona_safety.industry_standard is not None:
                    fields.append("industry_standard")
                    values.append(json.dumps(persona_safety.industry_standard))
                    placeholders.append("%s::jsonb")
                
                if persona_safety.competition is not None:
                    fields.append("competition")
                    values.append(json.dumps(persona_safety.competition))
                    placeholders.append("%s::jsonb")
                
                cursor.execute(
                    f"""INSERT INTO persona_safety 
                    ({', '.join(fields)}) 
                    VALUES ({', '.join(placeholders)}) 
                    RETURNING id, role_models, industry_standard, competition, 
                    user_id, account_id, created_at""",
                    tuple(values)
                )
                safety = cursor.fetchone()
            
            conn.commit()
            
            return {
                "id": safety[0],
                "role_models": safety[1],
                "industry_standard": safety[2],
                "competition": safety[3],
                "user_id": safety[4],
                "account_id": safety[5],
                "created_at": safety[6]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/persona-safety/", response_model=List[PersonaSafetyResponse])
async def get_all_persona_safety():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, role_models, industry_standard, competition, 
                user_id, account_id, created_at 
                FROM persona_safety"""
            )
            safety_records = cursor.fetchall()
            return [
                {
                    "id": record[0],
                    "role_models": record[1],
                    "industry_standard": record[2],
                    "competition": record[3],
                    "user_id": record[4],
                    "account_id": record[5],
                    "created_at": record[6]
                }
                for record in safety_records
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/persona-safety/{id}", response_model=PersonaSafetyResponse)
async def get_persona_safety(id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, role_models, industry_standard, competition, 
                user_id, account_id, created_at 
                FROM persona_safety WHERE id = %s""",
                (id,)
            )
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Safety record not found")
            return {
                "id": record[0],
                "role_models": record[1],
                "industry_standard": record[2],
                "competition": record[3],
                "user_id": record[4],
                "account_id": record[5],
                "created_at": record[6]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/persona-safety/user/{user_id}/account/{account_id}", response_model=PersonaSafetyResponse)
async def get_user_account_safety(user_id: int, account_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, role_models, industry_standard, competition, 
                user_id, account_id, created_at 
                FROM persona_safety WHERE user_id = %s AND account_id = %s""",
                (user_id, account_id)
            )
            record = cursor.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Safety record not found")
            return {
                "id": record[0],
                "role_models": record[1],
                "industry_standard": record[2],
                "competition": record[3],
                "user_id": record[4],
                "account_id": record[5],
                "created_at": record[6]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.put("/persona-safety/{id}", response_model=PersonaSafetyResponse)
async def update_persona_safety(id: int, persona_safety: PersonaSafetyUpdate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if safety record exists
            cursor.execute("SELECT id FROM persona_safety WHERE id = %s", (id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Safety record not found")
            
            # Build update query dynamically based on provided fields
            update_fields = []
            update_values = []
            
            if persona_safety.role_models is not None:
                update_fields.append("role_models = %s::jsonb")
                update_values.append(json.dumps(persona_safety.role_models))
            
            if persona_safety.industry_standard is not None:
                update_fields.append("industry_standard = %s::jsonb")
                update_values.append(json.dumps(persona_safety.industry_standard))
            
            if persona_safety.competition is not None:
                update_fields.append("competition = %s::jsonb")
                update_values.append(json.dumps(persona_safety.competition))
            
            if persona_safety.account_id is not None:
                update_fields.append("account_id = %s")
                update_values.append(persona_safety.account_id)
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            # Add id to the values list
            update_values.append(id)
            
            # Execute update
            cursor.execute(
                f"""UPDATE persona_safety 
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING id, role_models, industry_standard, competition, 
                user_id, account_id, created_at""",
                tuple(update_values)
            )
            
            updated_record = cursor.fetchone()
            conn.commit()
            
            return {
                "id": updated_record[0],
                "role_models": updated_record[1],
                "industry_standard": updated_record[2],
                "competition": updated_record[3],
                "user_id": updated_record[4],
                "account_id": updated_record[5],
                "created_at": updated_record[6]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.delete("/persona-safety/{id}", response_model=dict)
async def delete_persona_safety(id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if safety record exists
            cursor.execute("SELECT id FROM persona_safety WHERE id = %s", (id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Safety record not found")
            
            # Delete record
            cursor.execute("DELETE FROM persona_safety WHERE id = %s", (id,))
            conn.commit()
            
            return {"message": "Safety record deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
