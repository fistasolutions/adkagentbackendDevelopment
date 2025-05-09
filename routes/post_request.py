import json
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from db.db import get_connection
from datetime import datetime
from typing import List, Optional
from agents import Agent, Runner
from fastapi import status

router = APIRouter()

class PostingRequest(BaseModel):
    account_id: int
    user_id: int
    request: str  # User's main point or request
    chat_list: Optional[List[str]] = None  # Conversation history

class PostingRequestResponse(BaseModel):
    request_id: int
    created_at: datetime
    account_id: int
    user_id: int
    chat_list: List[str]
    main_point: str

# Define a new agent for temporary posting requests
posting_request_agent = Agent(
    name="Temporary Posting Request Agent",
    instructions="""
    You are a social media assistant specializing in handling temporary, one-time requests for post direction. 
    Your job is to understand the user's special instructions (such as themes, events, or temporary preferences) and respond in a natural, conversational way, confirming the request and asking any clarifying questions if needed. 
    Do not make permanent changes—these are for one-time or short-term use only. 
    Always be polite, clear, and helpful, and keep the conversation focused on the user's temporary needs for post generation.
    
    """,
    output_type=str
)

@router.post("/temporary-posting-request", response_model=PostingRequestResponse)
async def temporary_posting_request(request: PostingRequest):
    """
    Handle a temporary posting request, chat with the Temporary Posting Request Agent, and store the request in posts_requests table.
    """
    chat_history = request.chat_list or []
    chat_history.append(request.request)
    main_point = request.request
    try:
        agent_input = f"User request: {main_point}\nConversation: {chat_history}"
        agent_result = await Runner.run(posting_request_agent, input=agent_input)
        # Optionally, you can use agent_result.final_output for further logic
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO posts_requests (created_at, account_id, user_id, chat_list, main_point)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING request_id, created_at
                """,
                (datetime.utcnow(), request.account_id, request.user_id, str(chat_history), main_point)
            )
            row = cursor.fetchone()
            conn.commit()
            return PostingRequestResponse(
                request_id=row[0],
                created_at=row[1],
                account_id=request.account_id,
                user_id=request.user_id,
                chat_list=chat_history,
                main_point=main_point
            )
    except Exception as db_error:
        raise HTTPException(status_code=500, detail=f"DB error: {str(db_error)}")
    finally:
        conn.close()

class PostingChatRequest(BaseModel):
    account_id: int
    user_id: int
    chat_list: List[str]  # Full conversation history, latest user message last

class PostingChatResponse(BaseModel):
    agent_reply: str
    chat_list: List[str]

@router.post("/temporary-posting-chat", response_model=PostingChatResponse)
async def temporary_posting_chat(request: PostingChatRequest):
    """
    Live chat with the Temporary Posting Request Agent. Returns the agent's reply, does not save to DB.
    """
    chat_history = request.chat_list
    try:
        agent_input = f"Conversation: {chat_history}"
        agent_result = await Runner.run(posting_request_agent, input=agent_input)
        agent_reply = agent_result.final_output if hasattr(agent_result, 'final_output') else str(agent_result)
        chat_history.append(agent_reply)
        return PostingChatResponse(agent_reply=agent_reply, chat_list=chat_history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

class PostingKeepRequest(BaseModel):
    account_id: int
    user_id: int
    chat_list: List[str]
    main_point: str

@router.post("/temporary-posting-request/keep", response_model=PostingRequestResponse)
async def temporary_posting_keep(request: PostingKeepRequest):
    """
    Save the chat history and main point to posts_requests table when the user clicks 'keep'.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO posts_requests (created_at, account_id, user_id, chat_list, main_point)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING request_id, created_at
                """,
                (datetime.utcnow(), request.account_id, request.user_id, json.dumps(request.chat_list), request.main_point)
            )
            row = cursor.fetchone()
            conn.commit()
            return PostingRequestResponse(
                request_id=row[0],
                created_at=row[1],
                account_id=request.account_id,
                user_id=request.user_id,
                chat_list=request.chat_list,
                main_point=request.main_point
            )
    except Exception as db_error:
        raise HTTPException(status_code=500, detail=f"DB error: {str(db_error)}")
    finally:
        conn.close()

@router.get("/temporary-posting-requests", response_model=List[PostingRequestResponse])
async def get_temporary_posting_requests(account_id: int = Query(...), user_id: int = Query(...)):
    """
    Fetch all posts_requests data for a given account_id and user_id.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT request_id, created_at, account_id, user_id, chat_list, main_point
                FROM posts_requests
                WHERE account_id = %s AND user_id = %s
                ORDER BY created_at DESC
                """,
                (account_id, user_id)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                # Parse chat_list from JSON string to Python list
                chat_list = row[4]
                if isinstance(chat_list, str):
                    try:
                        chat_list = json.loads(chat_list)
                    except Exception:
                        chat_list = []
                results.append(PostingRequestResponse(
                    request_id=row[0],
                    created_at=row[1],
                    account_id=row[2],
                    user_id=row[3],
                    chat_list=chat_list,
                    main_point=row[5]
                ))
            return results
    except Exception as db_error:
        raise HTTPException(status_code=500, detail=f"DB error: {str(db_error)}")
    finally:
        conn.close()

class PostingDeleteRequest(BaseModel):
    request_id: int

@router.delete("/temporary-posting-request/{request_id}")
async def delete_temporary_posting_request(request_id: int):
    """
    Delete a posts_requests entry by request_id.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM posts_requests WHERE request_id = %s RETURNING request_id
                """,
                (request_id,)
            )
            deleted = cursor.fetchone()
            conn.commit()
            if not deleted:
                raise HTTPException(status_code=404, detail="Request not found")
            return {"message": "Request deleted successfully", "request_id": deleted[0]}
    except Exception as db_error:
        raise HTTPException(status_code=500, detail=f"DB error: {str(db_error)}")
    finally:
        conn.close()
