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

async def get_last_week_posts_and_comments(user_id: str, account_username: str) -> List[Dict[str, Any]]:
    """Get posts and their comments from the last week."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Get posts from current week
            cursor.execute(
                """
                SELECT c.id, c.content, c.created_at
                FROM comments c
                WHERE c.user_id = %s 
                AND c.account_username = %s
                AND c.created_at >= DATE_TRUNC('week', CURRENT_TIMESTAMP)
                ORDER BY c.created_at DESC
                """,
                (user_id, account_username)
            )
            rows = cursor.fetchall()
            
            # Organize posts and comments
            processed_comments = []
            for row in rows:
                try:
                    content_data = json.loads(row[1])
                    for tweet_data in content_data:
                        # Process each comment in the replies
                        if "replies" in tweet_data:
                            for reply in tweet_data["replies"]:
                                # Skip if reply already has a status
                                if "status" in reply and reply["status"] == "responded":
                                    continue
                                    
                                processed_comment = {
                                    "tweet_id": tweet_data["tweet_id"],
                                    "tweet_text": tweet_data["tweet_text"],
                                    "comment": reply["text"],
                                    "username": reply["username"],
                                    "comment_id": row[0],
                                    "reply_index": tweet_data["replies"].index(reply)
                                }
                                processed_comments.append(processed_comment)
                except json.JSONDecodeError:
                    print(f"Error parsing JSON for row {row[0]}")
                    continue
            
            return processed_comments
    finally:
        conn.close()


@router.post("/test-analyze-and-respond-comments")
async def test_analyze_and_respond_to_comments(user_id:str,account_username:str):
    """Test endpoint with dummy data to analyze comments and generate responses."""
    try:
        # Get unresponded comments
        posts_with_comments = await get_last_week_posts_and_comments(user_id,account_username)
        if not posts_with_comments:
            return {"message": "No new comments requiring responses found"}
            
        analysis_input = str(posts_with_comments)
        
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT posting_day, posting_time, posting_frequency,posting_time
                FROM persona_notify 
                WHERE notify_type = 'commentReply'
                AND user_id = %s 
                """,
                (user_id,),
            )
            post_settings = cursor.fetchone()
            
            if not post_settings:
                raise HTTPException(
                    status_code=400,
                    detail="Post settings data not found. Please set up your post settings before generating tweets.",
                )
            
            # Parse the post settings
            posting_day = post_settings[0]  # This is a JSON object
            posting_time = post_settings[1]  # This is a JSON object
            posting_frequency = post_settings[2]
            posting_time = post_settings[3]
            
            # Format post settings data for the agent
            post_settings_data = {
                "posting_day": posting_day,
                "posting_time": posting_time,
                "posting_frequency": posting_frequency,
                "posting_time": posting_time
            }
            comment_analysis_agent.instructions = get_comment_analysis_agent_instructions(post_settings_data)

        # Analyze comments using the analysis agent
        analysis_result = await Runner.run(
            comment_analysis_agent,
            input=analysis_input
        )
        
        # Handle the analysis output
        analysis_output = analysis_result.final_output
        if isinstance(analysis_output, str):
            analysis_output = json.loads(analysis_output)
        
        # Convert to AnalysisOutput model
        if not isinstance(analysis_output, AnalysisOutput):
            analysis_output = AnalysisOutput(**analysis_output)
        
        # Filter comments that need responses
        comments_to_respond = [
            comment for comment in analysis_output.comments
            if comment.should_respond
        ]
        
        if not comments_to_respond:
            return {"message": "No comments requiring responses found"}
        
        # Generate responses for each comment
        responses = []
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                for comment in comments_to_respond:
                    # Generate response using response agent
                    response_input = f"""Post Content: {comment.comment_text}
                    Comment: {comment.comment_text}
                    Comment Type: {comment.comment_type}
                    Key Points: {', '.join(comment.key_points)}
                    Tone: {comment.tone}
                    Context: {comment.reason}
                    Username: {comment.commentor_username}"""
                    
                    response_result = await Runner.run(
                        comment_response_agent,
                        input=response_input
                    )
                    
                    # Handle the response output
                    response_output = response_result.final_output
                    if isinstance(response_output, str):
                        response_output = json.loads(response_output)
                    
                    # Convert to ResponseOutput model
                    if not isinstance(response_output, ResponseOutput):
                        response_output = ResponseOutput(**response_output)
                
                    # Generate X.com URL for the tweet
                    tweet_url = f"https://x.com/i/web/status/{comment.post_id}"
                    
                    # First, get the current content
                    cursor.execute(
                        "SELECT content FROM comments WHERE id = %s",
                        (comment.comment_id,)
                    )
                    current_content = cursor.fetchone()[0]
                    content_data = json.loads(current_content)
                    
                    # Update the status in the replies array
                    for tweet in content_data:
                        if tweet["tweet_id"] == comment.post_id:
                            for reply in tweet["replies"]:
                                if reply["username"] == comment.commentor_username and reply["text"] == comment.comment_text:
                                    reply["status"] = "responded"
                                    reply["response"] = response_output.response_text
                                    reply["scheduled_time"] = comment.scheduled_time
                                    break
                    
                    # Update the content in the database
                    cursor.execute(
                        """
                        UPDATE comments 
                        SET content = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        RETURNING id
                        """,
                        (json.dumps(content_data), comment.comment_id)
                    )
                    
                    # Save response to database
                    cursor.execute(
                        """
                        INSERT INTO comments_reply 
                        (reply_text, risk_score, user_id, account_username, schedule_time, commentor_username, tweet_id, original_comment, tweet_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            response_output.response_text,
                            20,
                            user_id,
                            account_username,
                            datetime.utcnow() if comment.scheduled_time == "Immediate" else comment.scheduled_time,
                            comment.commentor_username,
                            comment.post_id,
                            comment.comment_text,
                            tweet_url
                        )
                    )
                    reply_id = cursor.fetchone()[0]
                    
                    responses.append({
                        "reply_id": reply_id,
                        "comment_id": comment.comment_id,
                        "post_id": comment.post_id,
                        "response_text": response_output.response_text,
                        "scheduled_time": comment.scheduled_time,
                        "priority": comment.response_priority,
                        "engagement_score": response_output.engagement_score,
                        "tone_match_score": response_output.tone_match_score,
                        "context_relevance_score": response_output.context_relevance_score,
                        "response_type": response_output.response_type,
                        "comment_type": comment.comment_type,
                        "key_points": comment.key_points,
                        "tone": comment.tone,
                        "risk_score": 20,
                        "commentor_username": comment.commentor_username
                    })
                
                conn.commit()
        finally:
            conn.close()

        return {
            "message": "Test completed successfully",
            "analysis_result": analysis_output.dict(),
            "generated_responses": responses
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