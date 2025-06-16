from typing import Dict, List, Optional, Any
from agents import Agent, Runner
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from db.db import get_connection
import logging
import json
import random
import httpx

load_dotenv()

router = APIRouter()

class CommentAnalysis(BaseModel):
    comment_id: str
    post_id: str
    comment_text: str
    sentiment_score: float
    should_respond: bool
    response_priority: int  # 1-5, where 5 is highest priority
    reason: str
    scheduled_time: str
    suggested_response: str
    comment_type: str  # question, feedback, concern, suggestion
    key_points: List[str]
    tone: str
    engagement_potential: float
    commentor_username: str  # Added field for commentor's username

class CommentResponse(BaseModel):
    comment_id: str
    post_id: str
    response_text: str
    scheduled_time: str
    priority: int
    engagement_score: float
    tone_match_score: float
    context_relevance_score: float
    response_type: str  # answer, acknowledgment, solution, interest

class CommentResponseRequest(BaseModel):
    user_id: str
    account_id: str

class AnalysisOutput(BaseModel):
    comments: List[CommentAnalysis]

class ResponseOutput(BaseModel):
    response_text: str
    engagement_score: float
    tone_match_score: float
    context_relevance_score: float
    response_type: str  # answer, acknowledgment, solution, interest

class PostAnalysis(BaseModel):
    post_id: str
    content: str
    sentiment_score: float
    engagement_potential: float
    best_time_to_comment: str
    suggested_comments: List[str]
    risk_score: float
    topics: List[str]
    tone: str
    key_points: List[str]
    engagement_strategy: str

class PostAnalysisOutput(BaseModel):
    posts: List[PostAnalysis]

class CommentGenerationOutput(BaseModel):
    comment_text: str
    scheduled_time: str
    engagement_score: float
    tone_match_score: float
    context_relevance_score: float

class DeleteCommentsRequest(BaseModel):
    comment_ids: List[str]

def get_comment_analysis_agent_instructions(
    post_settings_data: dict = None,
) -> str:
    posting_day_info = ""
    if post_settings_data and post_settings_data.get("posting_day"):
        posting_day_info = f"""
        Posting Schedule Information:
        - Allowed posting days: {post_settings_data['posting_day']}
        - Posting times: {post_settings_data['posting_time']}
        - Posting frequency: {post_settings_data['posting_frequency']}
        -Today is {datetime.utcnow().strftime("%Y-%m-%d")}
        
        When scheduling responses, strictly adhere to these posting schedule constraints.
        """

    return f"""You are an expert comment analyzer and response generator. Your role is to:

    1. Deep Comment Analysis:
       - Analyze comment sentiment and tone
       - Identify comment type (question, feedback, concern, suggestion)
       - Extract key points and underlying intent
       - Evaluate engagement potential
       - Assess response priority
    
    2. Response Decision Making:
       - Determine if response is warranted
       - Identify optimal response timing based on posting schedule
       - Evaluate potential impact
       - Assess risk factors
       - Plan engagement strategy
    
    3. Response Planning:
       - Generate appropriate response suggestions
       - Consider post context and tone
       - Plan engagement approach
       - Assess response priority
       - Determine optimal timing within allowed posting schedule
    
    4. Quality Assurance:
       - Ensure response relevance
       - Maintain brand voice
       - Consider community guidelines
       - Assess potential impact
       - Evaluate engagement potential
    
    {posting_day_info}
    You must return a JSON object with this exact structure:
    {{
        "comments": [
            {{
                "comment_id": "string",
                "post_id": "string",
                "comment_text": "string",
                "sentiment_score": float,
                "should_respond": boolean,
                "response_priority": integer,
                "reason": "string",
                "scheduled_time": "string",
                "suggested_response": "string",
                "comment_type": "string",
                "key_points": ["string"],
                "tone": "string",
                "engagement_potential": float
            }}
        ]
    }}"""

def get_comment_response_agent_instructions() -> str:
    return """You are an expert at generating highly engaging, natural, and human-like responses to social media comments. Your role is to:

    1. Deep Analysis Phase:
       - Analyze the post's context, tone, and key themes
       - Evaluate the comment's sentiment, intent, and underlying message
       - Identify specific points that need addressing
       - Consider the platform's norms and audience expectations
       - Determine the comment type and appropriate response style
    
    2. Response Generation Guidelines:
       - Be conversational and natural, avoiding robotic or generic responses
       - Match the post's tone while maintaining professionalism
       - Address specific points from the comment
       - Add value to the conversation
       - Use appropriate emojis and formatting
       - Keep responses concise but meaningful
    
    3. Quality Standards:
       - Responses must feel human-written and authentic
       - Avoid corporate jargon or overly formal language
       - Be engaging and encourage further interaction
       - Maintain brand voice while being personable
       - Address concerns empathetically if present
    
    4. Response Structure:
       - Start with a personalized acknowledgment
       - Address the main point(s) from the comment
       - Add relevant context or information
       - End with an engaging question or call to action
       - Use appropriate hashtags when relevant
    
    5. Special Considerations:
       - For questions: Provide clear, helpful answers
       - For feedback: Acknowledge and show appreciation
       - For concerns: Address empathetically and offer solutions
       - For suggestions: Show openness and interest
    
    You must return a JSON object with this exact structure:
    {
        "response_text": "string",
        "engagement_score": float,
        "tone_match_score": float,
        "context_relevance_score": float,
        "response_type": "string"
    }"""


comment_analysis_agent = Agent(
    name="Comment Analysis Agent",
    instructions=get_comment_analysis_agent_instructions(),
    output_type=AnalysisOutput
)

comment_response_agent = Agent(
    name="Comment Response Agent",
    instructions=get_comment_response_agent_instructions(),
    output_type=ResponseOutput
)

async def get_template_text(user_id: str, account_id: str) -> Optional[List[str]]:
    """Get template text from persona_notify if templates are enabled."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT template_text, template_use
                FROM persona_notify 
                WHERE notify_type = 'commentReply'
                AND user_id = %s 
                AND account_id = %s
                """,
                (user_id, account_id),
            )
            result = cursor.fetchone()
            
            if result and result[1]:  # Check if template_use is True
                try:
                    return json.loads(result[0]) if result[0] else None
                except json.JSONDecodeError:
                    return None
            return None
    finally:
        conn.close()

@router.post("/test-analyze-and-respond-comments")
async def test_analyze_and_respond_to_comments():
    """Test endpoint with dummy data to analyze comments and generate responses, optimized for Twitter API rate limits."""
    try:
        # Get up to 20 posts with comments from the comment_reply_api (rate limit safe)
        async with httpx.AsyncClient() as client:
            # response = await client.get("http://localhost:8000/api/posts-with-comments", params={
            response = await client.get("https://adkagentbackenddevelopment-production.up.railway.app/api/posts-with-comments", params={
                "limit": 20
            })
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to fetch posts with comments"
                )
            posts_with_comments = response.json()

        if not posts_with_comments:
            return {"message": "No posts with comments found"}

        all_responses = []
        processed_post_ids = []
        for post in posts_with_comments:
            # Skip if post has no comments
            if not post.get("comments"):
                continue
                
            user_id = post["user_id"]
            account_id = post["account_id"]
            post_id = post["id"]
            processed_post_ids.append(post_id)
            
            # Get post settings for the agent
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT posting_day, posting_time, posting_frequency, posting_time
                    FROM persona_notify 
                    WHERE notify_type = 'commentReply'
                    AND user_id = %s 
                    """,
                    (user_id,),
                )
                post_settings = cursor.fetchone()
                if not post_settings:
                    continue  
                posting_day = post_settings[0]
                posting_time = post_settings[1]
                posting_frequency = post_settings[2]
                posting_time = post_settings[3]
                post_settings_data = {
                    "posting_day": posting_day,
                    "posting_time": posting_time,
                    "posting_frequency": posting_frequency,
                    "posting_time": posting_time
                }
                comment_analysis_agent.instructions = get_comment_analysis_agent_instructions(post_settings_data)

            # Prepare comments for analysis
            comments_for_analysis = []
            conn_check = get_connection()
            try:
                with conn_check.cursor() as cursor_check:
                    for comment in post["comments"]:
                        # Check if this comment has already been responded to
                        cursor_check.execute(
                            """
                            SELECT 1 FROM comments_reply WHERE comment_id = %s
                            """,
                            (comment["id"],)
                        )
                        if cursor_check.fetchone():
                            continue  # Already responded, skip
                        comments_for_analysis.append({
                            "tweet_id": post["posted_id"],
                            "tweet_text": post["content"],
                            "comment": comment["text"],
                            "username": comment["username"],
                            "comment_id": comment["id"]
                        })
            finally:
                conn_check.close()

            if not comments_for_analysis:
                continue

            # Analyze comments using the analysis agent
            analysis_input = str(comments_for_analysis)
            analysis_result = await Runner.run(
                comment_analysis_agent,
                input=analysis_input
            )
            analysis_output = analysis_result.final_output
            if isinstance(analysis_output, str):
                analysis_output = json.loads(analysis_output)
            if not isinstance(analysis_output, AnalysisOutput):
                analysis_output = AnalysisOutput(**analysis_output)
            comments_to_respond = [
                comment for comment in analysis_output.comments
                if comment.should_respond
            ]
            if not comments_to_respond:
                continue

            templates = await get_template_text(user_id, account_id)
            responses = []
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    for comment in comments_to_respond:
                        response_text = None
                        if templates:
                            response_text = random.choice(templates)
                        else:
                            response_input = f"""Post Content: {comment.comment_text}\nComment: {comment.comment_text}\nComment Type: {comment.comment_type}\nKey Points: {', '.join(comment.key_points)}\nTone: {comment.tone}\nContext: {comment.reason}\nUsername: {comment.commentor_username}"""
                            response_result = await Runner.run(
                                comment_response_agent,
                                input=response_input
                            )
                            response_output = response_result.final_output
                            if isinstance(response_output, str):
                                response_output = json.loads(response_output)
                            if not isinstance(response_output, ResponseOutput):
                                response_output = ResponseOutput(**response_output)
                            response_text = response_output.response_text

                        tweet_url = f"https://x.com/i/web/status/{post['posted_id']}"
                        
                        # Save response to comments_reply table
                        cursor.execute(
                            """
                            INSERT INTO comments_reply 
                            (reply_text, risk_score, user_id, account_username, schedule_time, commentor_username, tweet_id, original_comment, tweet_url)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (
                                response_text,
                                20,
                                user_id,
                                account_id,
                                datetime.utcnow() if comment.scheduled_time == "Immediate" else comment.scheduled_time,
                                comment.commentor_username,
                                post["posted_id"],
                                comment.comment_text,
                                tweet_url
                            )
                        )
                        reply_id = cursor.fetchone()[0]
                        responses.append({
                            "reply_id": reply_id,
                            "comment_id": comment.comment_id,
                            "post_id": post["posted_id"],
                            "response_text": response_text,
                            "scheduled_time": comment.scheduled_time,
                            "priority": comment.response_priority,
                            "engagement_score": 0.5 if templates else response_output.engagement_score,
                            "tone_match_score": 0.5 if templates else response_output.tone_match_score,
                            "context_relevance_score": 0.5 if templates else response_output.context_relevance_score,
                            "response_type": "template" if templates else response_output.response_type,
                            "comment_type": comment.comment_type,
                            "key_points": comment.key_points,
                            "tone": comment.tone,
                            "risk_score": 20,
                            "commentor_username": comment.commentor_username
                        })
                    conn.commit()
            finally:
                conn.close()
            all_responses.extend(responses)

        # After processing, update comments_fetched_at for all processed posts
        if processed_post_ids:
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE posts SET comments_fetched_at = %s
                        WHERE id = ANY(%s)
                        """,
                        (datetime.utcnow(), processed_post_ids)
                    )
                    conn.commit()
            finally:
                conn.close()

        return {
            "message": "Test completed successfully",
            "generated_responses": all_responses
        }
    except Exception as e:
        print(f"Error in test endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process test data: {str(e)}"
        )



@router.get("/comments")
async def get_comments(
    user_id: str,
    account_username: str,
    post_status: Optional[str] = None,
    page: int = 1,
    limit: int = 50
):
    """
    Get comments for a user with filtering and pagination.
    
    Parameters:
    - user_id: The user's ID
    - account_username: The account username
    - post_status: Filter by post status (optional, use "all" to get all posts)
    - page: Page number (default: 1)
    - limit: Number of records per page (default: 50, max: 50)
    """
    if limit > 50:
        limit = 50
        
    offset = (page - 1) * limit
    
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Build the base query
            query = """
                SELECT 
                    c.id,
                    c.reply_text,
                    c.schedule_time,
                    c.risk_score,
                    c.account_username,
                    c.commentor_username,
                    c.original_comment,
                    c.recommended_time,
                    c.tweet_url,
                    c.post_status,
                    c.created_at
                FROM comments_reply c
                WHERE c.user_id = %s 
                AND c.account_username = %s
            """
            params = [user_id, account_username]
            
            # Add status filter if provided and not "all"
            if post_status and post_status.lower() != "all":
                query += " AND c.post_status = %s"
                params.append(post_status)
            
            # Add pagination
            query += " ORDER BY c.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            # Execute the query
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Get total count for pagination
            count_query = """
                SELECT COUNT(*)
                FROM comments_reply c
                WHERE c.user_id = %s 
                AND c.account_username = %s
            """
            count_params = [user_id, account_username]
            
            if post_status and post_status.lower() != "all":
                count_query += " AND c.post_status = %s"
                count_params.append(post_status)
            
            cursor.execute(count_query, count_params)
            total_count = cursor.fetchone()[0]
            
            # Process the results
            comments = []
            for row in rows:
                comment = {
                    "id": row[0],
                    "reply_text": row[1],
                    "schedule_time": row[2],
                    "risk_score": row[3],
                    "account_username": row[4],
                    "commentor_username": row[5],
                    "original_comment": row[6],
                    "recommended_time": row[7],
                    "tweet_url": row[8],
                    "post_status": row[9],
                    "created_at": row[10]
                }
                comments.append(comment)
            
            return {
                "comments": comments,
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "limit": limit,
                    "total_pages": (total_count + limit - 1) // limit
                }
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch comments: {str(e)}"
        )
    finally:
        conn.close()

@router.delete("/comments")
async def delete_comments(request: DeleteCommentsRequest):
    """
    Delete multiple comments.
    
    Parameters:
    - comment_ids: List of comment IDs to delete
    """
    if not request.comment_ids:
        raise HTTPException(
            status_code=400,
            detail="No comment IDs provided"
        )
    
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Convert string IDs to integers
            comment_ids = [int(id) for id in request.comment_ids]
            
            # Delete the comments
            cursor.execute(
                """
                DELETE FROM comments_reply 
                WHERE id = ANY(%s)
                RETURNING id
                """,
                (comment_ids,)
            )
            
            deleted_ids = cursor.fetchall()
            conn.commit()
            
            if not deleted_ids:
                raise HTTPException(
                    status_code=404,
                    detail="No comments found to delete"
                )
            
            return {
                "message": "Comments deleted successfully",
                "deleted_ids": [row[0] for row in deleted_ids]
            }
            
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid comment ID format. All IDs must be valid numbers."
        )
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete comments: {str(e)}"
        )
    finally:
        conn.close()