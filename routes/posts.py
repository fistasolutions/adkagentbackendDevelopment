import json
from fastapi import APIRouter, HTTPException
from models.tweet_models import DraftTweetGenerationRequest, PostInsertRequest
from agent.draft_tweet_agent import (
    DraftTweetAgent,
    DraftTweetRequest,
    DraftTweetResponse,
)
from agent.risk_assessment_agent import RiskAssessmentAgent, RiskAssessmentRequest
from agent.scheduling_agent import SchedulingAgent, ScheduleRequest
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
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT character_settings 
                FROM personas 
                WHERE user_id = %s 
                AND account_id = %s
                """,
                (request.user_id, request.account_id),
            )
            character_settings = cursor.fetchone()
        print(character_settings)
        agent = DraftTweetAgent()
        response = await agent.get_response(
            DraftTweetRequest(
                previous_tweet=request.previous_tweet,
                num_drafts=request.num_drafts,
                prompt=request.prompt,
                character_settings=(
                    character_settings[0] if character_settings else None
                ),
            )
        )
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
        # Perform risk assessment but don't block content
        risk_agent = RiskAssessmentAgent()
        risk_assessment = await risk_agent.get_response(
            RiskAssessmentRequest(content=request.content)
        )

        print(risk_assessment)
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                    SELECT posting_day, posting_time, posting_frequency,posting_time,pre_create,post_mode
                    FROM persona_notify 

                    WHERE user_id = %s 
                    AND account_id = %s
                    AND notify_type = 'post'
                    """,
                (request.user_id, request.account_id),
            )
            post_settings = cursor.fetchone()

        scheduling_agent = SchedulingAgent()
        scheduling_response = await scheduling_agent.get_response(
            ScheduleRequest(
                user_id=request.user_id,
                account_id=request.account_id,
                post_settings=post_settings,
                content=request.content,
            )
        )

        print("scheduling_responsrisk_assessment", risk_assessment)
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

            if request.status is not None:
                fields.append("status")
                values.append(request.status)
                placeholders.append("%s")

            if request.scheduled_time is not None:
                fields.append("scheduled_time")
                values.append(request.scheduled_time)
                placeholders.append("%s")
            if request.mode is None:
                fields.append("recommended_time")
                values.append(scheduling_response.scheduling_date)
                placeholders.append("%s")
            else:
                if request.recommended_time is not None:
                    fields.append("recommended_time")
                    values.append(request.recommended_time)
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

            # Add risk score from assessment
            fields.append("risk_score")
            values.append(risk_assessment.overall_risk_score)
            placeholders.append("%s")
            fields.append("risk_assesments")
            risk_assessment_json = json.dumps(
                {
                    "risk_categories": [
                        category.dict() for category in risk_assessment.risk_categories
                    ],
                    "risk_assignment": risk_assessment.risk_assignment,
                }
            )
            values.append(risk_assessment_json)
            placeholders.append("%s")

            if request.manual_time is not None:
                fields.append("manual_time")
                values.append(request.manual_time)
                placeholders.append("%s")

            # Construct and execute the SQL query
            query = f"""
                INSERT INTO posts ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING id, content, user_id, account_id, status, 
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
                "status": result[4],
                "scheduled_time": result[5],
                "posted_time": result[6],
                "created_at": result[7],
                "posted_id": result[8],
                "media_id": result[9],
                "image_url": result[10],
                "risk_score": result[11],
                "manual_time": result[12],
                "risk_assessment": risk_assessment.dict(),
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if "conn" in locals():
            conn.close()
