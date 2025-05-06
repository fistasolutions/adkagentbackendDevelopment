from fastapi import APIRouter, HTTPException, Depends,Response, Query
from db.db import get_connection
from models import UserCreate, UserResponse
from typing import List, Optional
from pydantic import BaseModel
import bcrypt
import random
from utils.jwt import create_access_token
router = APIRouter()

class UserUpdate(BaseModel):
    fullname: str | None = None
    email: str | None = None
    password: str | None = None

class LoginRequest(BaseModel):
    rememberMe: bool
    enterprise_id: str
    email: str
    password: str

class LoginResponse(BaseModel):
    user_id: int
    fullname: str
    email: str
    enterprise_id: str
    message: str
    role: str

class TwitterAccount(BaseModel):
    account_id: int
    username: str

class UserWithTwitter(UserResponse):
    twitter_accounts: List[TwitterAccount] = []

class PaginatedUserResponse(BaseModel):
    users: List[UserWithTwitter]
    total: int
    page: int
    page_size: int
    total_pages: int

class UserRoleResponse(BaseModel):
    role: str

@router.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, response: Response):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Check if email exists
            cursor.execute("SELECT user_id FROM users WHERE email = %s", (user.email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
            
            if not user.enterprise_id:
                user.enterprise_id = str(random.randint(100000, 999999))

            hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

            cursor.execute(
                "INSERT INTO users (fullname, email, password, enterprise_id) VALUES (%s, %s, %s, %s) RETURNING user_id",
                (user.fullname, user.email, hashed_password.decode('utf-8'), user.enterprise_id)
            )
            user_id = cursor.fetchone()[0]
            conn.commit()



            return {
                "user_id": user_id,
                "fullname": user.fullname,
                "email": user.email,
                "enterprise_id": user.enterprise_id
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/users", response_model=PaginatedUserResponse)
async def get_all_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page")
):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get total count of users
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Calculate offset
            offset = (page - 1) * page_size
            
            # Get paginated users
            cursor.execute(
                "SELECT user_id, fullname, email, enterprise_id FROM users ORDER BY user_id LIMIT %s OFFSET %s",
                (page_size, offset)
            )
            users = cursor.fetchall()
            
            # Calculate total pages
            total_pages = (total_users + page_size - 1) // page_size
            
            return {
                "users": [{"user_id": user[0], "fullname": user[1], "email": user[2], "enterprise_id": user[3]} for user in users],
                "total": total_users,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/users/paginated", response_model=PaginatedUserResponse)
async def get_paginated_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page")
):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get total count of users
            cursor.execute("SELECT COUNT(DISTINCT u.user_id) FROM users u")
            total_users = cursor.fetchone()[0]
            
            # Calculate offset
            offset = (page - 1) * page_size
            
            # Get paginated users with their Twitter accounts
            cursor.execute("""
                WITH paginated_users AS (
                    SELECT DISTINCT u.user_id
                    FROM users u
                    ORDER BY u.user_id
                    LIMIT %s OFFSET %s
                )
                SELECT 
                    u.user_id, 
                    u.fullname, 
                    u.email, 
                    u.enterprise_id,
                    u.role,
                    t.account_id,
                    t.username
                FROM paginated_users pu
                JOIN users u ON pu.user_id = u.user_id
                LEFT JOIN twitter_account t ON u.user_id = t.user_id
                ORDER BY u.user_id, t.account_id
            """, (page_size, offset))
            
            users_data = cursor.fetchall()
            
            # Calculate total pages
            total_pages = (total_users + page_size - 1) // page_size
            
            # Transform the results
            formatted_users = {}
            for row in users_data:
                user_id = row[0]
                if user_id not in formatted_users:
                    formatted_users[user_id] = {
                        "user_id": row[0],
                        "fullname": row[1],
                        "email": row[2],
                        "enterprise_id": row[3],
                        "role": row[4],
                        "twitter_accounts": []
                    }
                
                # Add Twitter account if it exists
                if row[5]:  # account_id exists
                    formatted_users[user_id]["twitter_accounts"].append({
                        "account_id": row[5],
                        "username": row[6]
                    })
            
            return {
                "users": list(formatted_users.values()),
                "total": total_users,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, fullname, email, enterprise_id, role FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return {"user_id": user[0], "fullname": user[1], "email": user[2], "enterprise_id": user[3], "role": user[4]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_update: UserUpdate):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if user exists
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
            
            # Hash the password
            hashed_password = bcrypt.hashpw(user_update.password.encode('utf-8'), bcrypt.gensalt())
            
            # Build update query dynamically based on provided fields
            update_fields = []
            values = []
            if user_update.fullname is not None:
                update_fields.append("fullname = %s")
                values.append(user_update.fullname)
            if user_update.email is not None:
                update_fields.append("email = %s")
                values.append(user_update.email)
            if user_update.password is not None:
                update_fields.append("password = %s")
                values.append(hashed_password.decode('utf-8'))
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            # Add user_id to values
            values.append(user_id)
            
            # Execute update
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = %s RETURNING user_id, fullname, email"
            cursor.execute(query, values)
            updated_user = cursor.fetchone()
            conn.commit()
            
            return {
                "user_id": updated_user[0],
                "fullname": updated_user[1],
                "email": updated_user[2]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/login", response_model=LoginResponse)
async def login(login_request: LoginRequest, response: Response):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if user exists with given email and enterprise_id
            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (login_request.email,)
            )
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            
            # Verify password using bcrypt
            stored_password = user[3].encode('utf-8')  # password is at index 3
            provided_password = login_request.password.encode('utf-8')
            
            if not bcrypt.checkpw(provided_password, stored_password):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            # Create JWT token
            token = create_access_token({"sub": user[2]})  # email is at index 2

           # ✅ Set secure cookie
            if login_request.rememberMe:
                response.set_cookie(
                    key="token",
                    value=token,
                    httponly=True,
                    samesite="Lax",
                    secure=False , 
                domain="https://adkaiagentfrontend.vercel.app",
                    max_age=60 * 60 * 24 * 7  # 1 week
                )
            else:
                response.set_cookie(
                    key="token",
                    value=token,
                    httponly=True,
                    samesite="Lax",
                )
            
            return {
                "user_id": user[0],
                "fullname": user[1],
                "email": user[2],
                "enterprise_id": user[5],  # enterprise_id is at index 5
                "role": user[8],
                "message": "Login successful"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close() 

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("token")
    return {"message": "Logged out"}

@router.get("/users/search", response_model=PaginatedUserResponse)
async def search_users(
    query: str = Query(..., description="Search query for email or fullname"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page")
):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get total count of matching users
            cursor.execute(
                """
                SELECT COUNT(DISTINCT u.user_id) 
                FROM users u 
                WHERE u.email ILIKE %s OR u.fullname ILIKE %s
                """,
                (f'%{query}%', f'%{query}%')
            )
            total_users = cursor.fetchone()[0]
            
            # Calculate offset
            offset = (page - 1) * page_size
            
            # Get paginated users with their Twitter accounts
            cursor.execute(
                """
                WITH paginated_users AS (
                    SELECT DISTINCT u.user_id
                    FROM users u
                    WHERE u.email ILIKE %s OR u.fullname ILIKE %s
                    ORDER BY u.user_id
                    LIMIT %s OFFSET %s
                )
                SELECT 
                    u.user_id, 
                    u.fullname, 
                    u.email, 
                    u.enterprise_id,
                    u.role,
                    t.account_id,
                    t.username
                FROM paginated_users pu
                JOIN users u ON pu.user_id = u.user_id
                LEFT JOIN twitter_account t ON u.user_id = t.user_id
                ORDER BY u.user_id, t.account_id
                """,
                (f'%{query}%', f'%{query}%', page_size, offset)
            )
            
            users_data = cursor.fetchall()
            
            # Calculate total pages
            total_pages = (total_users + page_size - 1) // page_size
            
            # Transform the results
            formatted_users = {}
            for row in users_data:
                user_id = row[0]
                if user_id not in formatted_users:
                    formatted_users[user_id] = {
                        "user_id": row[0],
                        "fullname": row[1],
                        "email": row[2],
                        "enterprise_id": row[3],
                        "role": row[4],
                        "twitter_accounts": []
                    }
                
                # Add Twitter account if it exists
                if row[5]:  # account_id exists
                    formatted_users[user_id]["twitter_accounts"].append({
                        "account_id": row[5],
                        "username": row[6]
                    })
            
            return {
                "users": list(formatted_users.values()),
                "total": total_users,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/users/search/all", response_model=List[UserWithTwitter])
async def search_all_users(query: str = Query(..., description="Search query for email or fullname")):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get all matching users with their Twitter accounts
            cursor.execute(
                """
                SELECT 
                    u.user_id, 
                    u.fullname, 
                    u.email, 
                    u.enterprise_id,
                    u.role,
                    t.account_id,
                    t.username
                FROM users u
                LEFT JOIN twitter_account t ON u.user_id = t.user_id
                WHERE u.email ILIKE %s OR u.fullname ILIKE %s
                ORDER BY u.user_id, t.account_id
                """,
                (f'%{query}%', f'%{query}%')
            )
            
            users_data = cursor.fetchall()
            
            # Transform the results
            formatted_users = {}
            for row in users_data:
                user_id = row[0]
                if user_id not in formatted_users:
                    formatted_users[user_id] = {
                        "user_id": row[0],
                        "fullname": row[1],
                        "email": row[2],
                        "enterprise_id": row[3],
                        "role": row[4],
                        "twitter_accounts": []
                    }
                
                # Add Twitter account if it exists
                if row[5]:  # account_id exists
                    formatted_users[user_id]["twitter_accounts"].append({
                        "account_id": row[5],
                        "username": row[6]
                    })
            
            return list(formatted_users.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/users/{user_id}/role", response_model=UserRoleResponse)
async def get_user_role(user_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            return {"role": result[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()