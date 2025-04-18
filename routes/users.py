from fastapi import APIRouter, HTTPException, Depends,Response
from db.db import get_connection
from models import UserCreate, UserResponse
from typing import List
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

# @router.post("/users/", response_model=UserResponse)
# async def create_user(user: UserCreate):
#     try:
#         conn = get_connection()
#         with conn.cursor() as cursor:
#             # Check if email already exists
#             cursor.execute("SELECT user_id FROM users WHERE email = %s", (user.email,))
#             if cursor.fetchone():
#                 raise HTTPException(status_code=400, detail="Email already registered")
            
#             # Generate enterprise_id if not provided
#             if not user.enterprise_id:
#                 user.enterprise_id = str(random.randint(100000, 999999))
            
#             # Hash the password
#             hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
            
#             cursor.execute(
#                 "INSERT INTO users (fullname, email, password, enterprise_id) VALUES (%s, %s, %s, %s) RETURNING user_id",
#                 (user.fullname, user.email, hashed_password.decode('utf-8'), user.enterprise_id)
#             )
#             user_id = cursor.fetchone()[0]
#             conn.commit()
            
#             return {
#                 "user_id": user_id,
#                 "fullname": user.fullname,
#                 "email": user.email,
#                 "enterprise_id": user.enterprise_id
#             }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         conn.close()


@router.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, response: Response):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Check if email exists
            cursor.execute("SELECT user_id FROM users WHERE email = %s", (user.email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
            
            # Generate enterprise ID if not provided
            if not user.enterprise_id:
                user.enterprise_id = str(random.randint(100000, 999999))

            # Hash password
            hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

            # Insert user
            cursor.execute(
                "INSERT INTO users (fullname, email, password, enterprise_id) VALUES (%s, %s, %s, %s) RETURNING user_id",
                (user.fullname, user.email, hashed_password.decode('utf-8'), user.enterprise_id)
            )
            user_id = cursor.fetchone()[0]
            conn.commit()

            # ✅ Create JWT token
            token = create_access_token({"sub": user.email})

            # ✅ Set secure cookie
            if user.rememberMe:
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
                "user_id": user_id,
                "fullname": user.fullname,
                "email": user.email,
                "enterprise_id": user.enterprise_id
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/users/", response_model=List[UserResponse])
async def get_all_users():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, fullname, email, enterprise_id FROM users")
            users = cursor.fetchall()
            return [{"user_id": user[0], "fullname": user[1], "email": user[2], "enterprise_id": user[3]} for user in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, fullname, email, enterprise_id FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return {"user_id": user[0], "fullname": user[1], "email": user[2], "enterprise_id": user[3]}
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
    print(login_request)
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Check if user exists with given email and enterprise_id
            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (login_request.email,)
            )
            user = cursor.fetchone()
            print(user)
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