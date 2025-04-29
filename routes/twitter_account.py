from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException,Response
from db.db import get_connection
from pydantic import BaseModel

router = APIRouter()

class AccountCreate(BaseModel):
    username: str | None = None
    user_id: int | None = None

class AccountUpdate(BaseModel):
    username: str | None = None
    user_id: str | None = None

class AccountResponse(BaseModel):
    username: str
    user_id: str
    account_id: str
    created_at: datetime
    updated_at: datetime


@router.post("/twitter/accounts", response_model=AccountResponse)
async def create_account(account: AccountCreate, response: Response):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:


            # Insert user
            cursor.execute(
                "INSERT INTO twitter_account (username, user_id, created_at, updated_at) VALUES (%s, %s, %s, %s) RETURNING user_id, username, account_id, created_at, updated_at",
                (account.username, account.user_id, datetime.utcnow(), datetime.utcnow())
            )
            row = cursor.fetchone()
            conn.commit()

            return {
                "user_id": str(row[0]),
                "username": row[1],
                "account_id": str(row[2]),
                "created_at": row[3],
                "updated_at": row[4]
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
@router.get("/twitter/accounts/{user_id}", response_model=List[AccountResponse])
async def get_accounts(user_id: int, response: Response):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM twitter_account WHERE user_id = %s", (user_id,))
            rows = cursor.fetchall()
            print(rows)
            if not rows:
                raise HTTPException(status_code=404, detail="Account not found")
            
            accounts = []
            for row in rows:
                account = AccountResponse(
                    account_id=str(row[0]),
                    created_at=row[1],
                    updated_at=row[2],
                    username=row[3],
                    user_id=str(row[4])
                )
                accounts.append(account)
            
            return accounts

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    
@router.put("/twitter/accounts/{account_id}", response_model=AccountResponse)
async def update_account(account_id: str, account: AccountUpdate, response: Response):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Build update query dynamically based on provided fields
            update_fields = []
            values = []
            if account.username is not None:
                update_fields.append("username = %s")
                values.append(account.username)
            if account.user_id is not None:
                update_fields.append("user_id = %s")
                values.append(account.user_id)
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            update_fields.append("updated_at = %s")
            values.append(datetime.utcnow())
            values.append(account_id)
            query = f"UPDATE twitter_account SET {', '.join(update_fields)} WHERE account_id = %s RETURNING user_id, username, account_id, created_at, updated_at"
            cursor.execute(query, values)
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Account not found")
            conn.commit()
            return {
                "user_id": str(row[0]),
                "username": row[1],
                "account_id": str(row[2]),
                "created_at": row[3],
                "updated_at": row[4]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.delete("/twitter/accounts/{account_id}")
async def delete_account(account_id: str, response: Response):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM twitter_account WHERE account_id = %s RETURNING account_id", (account_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Account not found")
            conn.commit()
            return {"message": "Account deleted successfully", "account_id": account_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


