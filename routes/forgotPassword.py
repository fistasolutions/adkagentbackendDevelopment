from fastapi import APIRouter, HTTPException
import secrets
import requests
from typing import Optional
from pydantic import BaseModel
from db.db import get_connection
from datetime import datetime, timedelta, timezone
import bcrypt

router = APIRouter()

class ForgotPasswordRequest(BaseModel):
    email: str

class VerifyCodeRequest(BaseModel):
    email: str
    verification_code: str

class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str

def generate_verification_code():
    """Generate a random 6-character verification code"""
    return secrets.token_hex(3).upper()

async def send_verification_email(user_email: str, verification_code: str):
    """Send verification email to user"""
    email_payload = {
        'email': user_email,
        'subject': 'ADK  - Verification Code',
        'code': verification_code
    }
    
    try:
        response = requests.post(
            'https://lms.unialsolutions.com/sendEmailGentlebridge',
            json=email_payload,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        
        if response.headers.get('content-type', '').startswith('application/json'):
            return response.json()
        return response.text
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@router.post("/send_verification_code")
async def forgot_password(request: ForgotPasswordRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (request.email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="User not found")
            
        # Generate verification code
        verification_code = generate_verification_code()
        
        # Update user's verification code
        cursor.execute(
            "INSERT INTO verification_codes (email, verification_code) VALUES (%s, %s)",
            (request.email, verification_code)
        )
        conn.commit()
        
        # Send verification email
        await send_verification_email(request.email, verification_code)
        
        cursor.close()
        conn.close()
        
        return {
            "message": "Verification code sent successfully",
            "status": "success"
        }
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-code")
async def verify_code(request: VerifyCodeRequest):
    try:
        print(request.email , request.verification_code)
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get the verification code for the email
        cursor.execute(
            "SELECT verification_code, created_at FROM verification_codes WHERE email = %s ORDER BY created_at DESC LIMIT 1",
            (request.email,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="No verification code found for this email")
            
        stored_code, created_at = result
        
        # Make both datetimes timezone-aware
        current_time = datetime.now(timezone.utc)
        created_at = created_at.replace(tzinfo=timezone.utc)
        
        # Check if code is expired (15 minutes)
        if current_time - created_at > timedelta(minutes=15):
            cursor.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Verification code has expired")
            
        # Verify the code
        if stored_code != request.verification_code:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid verification code")
            
        # Code is valid, we can delete it
        cursor.execute(
            "DELETE FROM verification_codes WHERE email = %s",
            (request.email,)
        )
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {
            "message": "Code verified successfully",
            "status": "success"
        }
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (request.email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="User not found")
            
        # Hash the new password using bcrypt
        hashed_password = bcrypt.hashpw(request.new_password.encode('utf-8'), bcrypt.gensalt())
        
        # Update user's password
        cursor.execute(
            "UPDATE users SET password = %s WHERE email = %s",
            (hashed_password.decode('utf-8'), request.email)
        )
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {
            "message": "Password reset successfully",
            "status": "success"
        }
        
    except Exception as e:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=str(e))




