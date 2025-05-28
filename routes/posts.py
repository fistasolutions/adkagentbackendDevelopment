from fastapi import APIRouter, HTTPException
from models.tweet_models import DraftTweetGenerationRequest, PostInsertRequest
from agent.draft_tweet_agent import DraftTweetAgent, DraftTweetRequest, DraftTweetResponse
from db.db import get_connection

router = APIRouter()

@router.post("/generate-draft-tweets", response_model=DraftTweetResponse)
async def generate_draft_tweets(request: DraftTweetGenerationRequest):
    """
    Generate draft tweets based on a previous tweet.
    
    Args:
        request (DraftTweetGenerationRequest): The request containing the previous tweet, number of drafts needed, and optional prompt
        
    Returns:
        DraftTweetResponse: The generated draft tweets
    """
    try:
        agent = DraftTweetAgent()
        response = await agent.get_response(DraftTweetRequest(
            previous_tweet=request.previous_tweet,
            num_drafts=request.num_drafts,
            prompt=request.prompt
        ))
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
       
@router.post("/insert-post")
async def insert_post(request: PostInsertRequest):
    """
    Insert a new post into the posts table using raw SQL query.
    All fields are optional except content.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Build the dynamic SQL query based on provided fields
            fields = ["content"]
            values = [request.content]
            placeholders = ["%s"]
            
            if request.user_id is not None:
                fields.append("user_id")
                values.append(request.user_id)
                placeholders.append("%s")
            
            if request.account_id is not None:
                fields.append("account_id")
                values.append(request.account_id)
                placeholders.append("%s")
            
            if request.mode is not None:
                fields.append("mode")
                values.append(request.mode)
                placeholders.append("%s")
            
            if request.status is not None:
                fields.append("status")
                values.append(request.status)
                placeholders.append("%s")
            
            if request.scheduled_time is not None:
                fields.append("scheduled_time")
                values.append(request.scheduled_time)
                placeholders.append("%s")
            
            if request.posted_time is not None:
                fields.append("posted_time")
                values.append(request.posted_time)
                placeholders.append("%s")
            
            if request.posted_id is not None:
                fields.append("posted_id")
                values.append(request.posted_id)
                placeholders.append("%s")
            
            if request.media_id is not None:
                fields.append("media_id")
                values.append(request.media_id)
                placeholders.append("%s")
            
            if request.image_url is not None:
                fields.append("Image_url")
                values.append(request.image_url)
                placeholders.append("%s")
            
            if request.risk_score is not None:
                fields.append("risk_score")
                values.append(request.risk_score)
                placeholders.append("%s")
            
            if request.manual_time is not None:
                fields.append("manual_time")
                values.append(request.manual_time)
                placeholders.append("%s")
            
            # Construct and execute the SQL query
            query = f"""
                INSERT INTO posts ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING id, content, user_id, account_id, mode, status, 
                         scheduled_time, posted_time, created_at, posted_id, 
                         media_id, "Image_url", risk_score, manual_time
            """
            
            cursor.execute(query, tuple(values))
            result = cursor.fetchone()
            conn.commit()
            
            return {
                "id": result[0],
                "content": result[1],
                "user_id": result[2],
                "account_id": result[3],
                "mode": result[4],
                "status": result[5],
                "scheduled_time": result[6],
                "posted_time": result[7],
                "created_at": result[8],
                "posted_id": result[9],
                "media_id": result[10],
                "image_url": result[11],
                "risk_score": result[12],
                "manual_time": result[13]
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close() 