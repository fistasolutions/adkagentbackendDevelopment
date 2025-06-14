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
    risk_score: float

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

class DeletePostRepliesRequest(BaseModel):
    reply_ids: List[str]

def get_post_analysis_agent_instructions(
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

    return f"""You are an expert Post analyzer and comment generator. Your role is to:

    1. Deep Post Analysis:
       - Analyze post sentiment and tone
       - Identify post type (question, feedback, concern, suggestion)
       - Extract key points and underlying intent
       - Evaluate engagement potential
       - Assess response priority
       - Calculate risk score (10 to 50) based on content sensitivity and potential impact
    
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
                "tweet_id": "string",
                "tweet_text": "string",
                "username": "string",
                "schedule_time": "string",
                "comments": "string",
                "risk_score": float,
                "should_respond": boolean,
                "suggested_response": "string",
                "commentor_username": "string"
            }}
        ]
    }}"""

def get_post_response_agent_instructions() -> str:
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
    instructions=get_post_analysis_agent_instructions(),
    output_type=AnalysisOutput
)

comment_response_agent = Agent(
    name="Comment Response Agent",
    instructions=get_post_response_agent_instructions(),
    output_type=ResponseOutput
)

async def update_competitor_tweet_status(comment_id: str, user_id: str, account_id: str):
    """Update competitor tweet content to mark that a response has been created."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # First get the current content using tweet_id
            cursor.execute(
                """
                SELECT id, content FROM compititers_data 
                WHERE content::jsonb->'tweets'->0->>'tweet_id' = %s 
                AND user_id = %s 
                AND account_id = %s
                """,
                (comment_id, user_id, account_id)
            )
            result = cursor.fetchone()
            if result:
                competitor_id, content = result
                if isinstance(content, str):
                    content = json.loads(content)
                
                # Update the tweet status in content
                if "tweets" in content and content["tweets"]:
                    content["tweets"][0]["has_response"] = True
                    content["tweets"][0]["response_created_at"] = datetime.utcnow().isoformat()
                
                # Update the content using the correct competitor_id
                cursor.execute(
                    """
                    UPDATE compititers_data 
                    SET content = %s
                    WHERE id = %s
                    """,
                    (json.dumps(content), competitor_id)
                )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update competitor tweet status: {str(e)}"
        )
    finally:
        conn.close()

async def save_comments_to_db(comments: List[CommentAnalysis], user_id: str, account_id: str):
    """Save generated comments to the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            for comment in comments:
                # First get the original tweet text
                cursor.execute(
                    """
                    SELECT content::jsonb->'tweets'->0->>'text' as tweet_text
                    FROM compititers_data 
                    WHERE content::jsonb->'tweets'->0->>'tweet_id' = %s 
                    AND user_id = %s 
                    AND account_id = %s
                    """,
                    (comment.comment_id, user_id, account_id)
                )
                tweet_result = cursor.fetchone()
                tweet_text = tweet_result[0] if tweet_result else ""

                # Save the comment with tweet text
                cursor.execute(
                    """
                    INSERT INTO post_reply (
                        original_post_url,
                        user_id,
                        account_id,
                        competitor_username,
                        generated_comment,
                        tweet_id,
                        post_status,
                        schedule_time,
                        risk_score,
                        tweet_text,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """,
                    (
                        f"https://twitter.com/{comment.commentor_username}/status/{comment.comment_id}",
                        user_id,
                        account_id,
                        comment.commentor_username,
                        comment.suggested_response,
                        comment.comment_id,
                        "unposted",
                        comment.scheduled_time,
                        comment.risk_score,
                        tweet_text,
                    )
                )
                
                # Then update the competitor tweet status
                await update_competitor_tweet_status(comment.comment_id, user_id, account_id)
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save comments to database: {str(e)}"
        )
    finally:
        conn.close()

async def get_last_week_posts(user_id: str, account_id: str) -> List[Dict[str, Any]]:
    """Get posts and their comments from the last week."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Get posts from current week
            cursor.execute(
                """
                SELECT c.id, c.content, c.created_at
                FROM compititers_data c
                WHERE c.user_id = %s 
                AND c.account_id = %s
                AND c.created_at >= DATE_TRUNC('week', CURRENT_TIMESTAMP)
                ORDER BY c.created_at DESC
                """,
                (user_id, account_id)
            )
            rows = cursor.fetchall()
            print(rows)
            
            # Organize posts and comments
            processed_comments = []
            for row in rows:
                try:
                    content_data = row[1]  # This is already a dictionary
                    if isinstance(content_data, str):
                        content_data = json.loads(content_data)
                        
                    if "tweets" in content_data and content_data["tweets"]:
                        tweet = content_data["tweets"][0]  # Get first tweet
                        # Skip if tweet already has a response
                        if tweet.get("has_response", False):
                            continue
                            
                        processed_comment = {
                            "tweet_text": tweet.get("text", ""),
                            "created_at": tweet.get("created_at", ""),
                            "username": content_data.get("username", ""),
                            "tweet_id": tweet.get("tweet_id", "")
                        }
                        processed_comments.append(processed_comment)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error processing row {row[0]}: {str(e)}")
                    continue
            
            return processed_comments
    finally:
        conn.close()

@router.post("/generate-comments_for_post")
async def generate_comments_for_post(user_id:str, account_id:str):
    """Get posts and generate comments for them."""
    try:
        # Get posts from last week
        posts = await get_last_week_posts(user_id, account_id)
        if not posts:
            return {"message": "No posts found from last week"}
        print(posts)
        
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT posting_day, posting_time, posting_frequency,posting_time
                FROM persona_notify 
                WHERE notify_type = 'postReply'
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
            comment_analysis_agent.instructions = get_post_analysis_agent_instructions(post_settings_data)

        # Analyze comments using the analysis agent
        post_string = str(posts)
        analysis_result = await Runner.run(
            comment_analysis_agent,
            input=post_string
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
        
        print(comments_to_respond)
        if not comments_to_respond:
            return {"message": "No comments requiring responses found"}
        
        # Save comments to database
        await save_comments_to_db(comments_to_respond, user_id, account_id)
        
        return {
            "message": "Posts retrieved and comments saved successfully",
            "posts": comments_to_respond
        }
            
    except Exception as e:
        print(f"Error in generate comments endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process posts: {str(e)}"
        )



@router.get("/post_comments")
async def get_comments(
    user_id: str,
    account_id: str,
    post_status: Optional[str] = None,
    page: int = 1,
    limit: int = 50
):
    """
    Get comments for a user with filtering and pagination.
    
    Parameters:
    - user_id: The user's ID
    - account_id: The account username
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
                    tweet_id,
                    text,
                    post_username,
                    account_id,
                    reply_text,
                    risk_score,
                    schedule_time,
                    recommended_time,
                    post_status,
                    user_id,
                    id
                FROM post_for_reply
                WHERE account_id = %s
                AND user_id = %s
            """
            params = [account_id, user_id]
            
            # Add status filter if provided and not "all"
            if post_status and post_status.lower() != "all":
                query += " AND post_status = %s"
                params.append(post_status)
            
            # Add pagination
            query += " ORDER BY schedule_time DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            # Execute the query
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Get total count for pagination
            count_query = """
                SELECT COUNT(*)
                FROM post_for_reply
                WHERE account_id = %s
                AND user_id = %s
            """
            count_params = [account_id, user_id]
            
            if post_status and post_status.lower() != "all":
                count_query += " AND post_status = %s"
                count_params.append(post_status)
            
            cursor.execute(count_query, count_params)
            total_count = cursor.fetchone()[0]
            
            # Process the results
            comments = []
            for row in rows:
                comment = {
                    "tweet_id": row[0],
                    "text": row[1],
                    "post_username": row[2],
                    "account_id": row[3],
                    "reply_text": row[4],
                    "risk_score": row[5],
                    "schedule_time": row[6].isoformat() if row[6] else None,
                    "recommended_time": row[7].isoformat() if row[7] else None,
                    "post_status": row[8],
                    "user_id": row[9],
                    "id": row[10]
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

@router.delete("/post_replies")
async def delete_post_replies(request: DeletePostRepliesRequest):
    """
    Delete multiple post replies.
    
    Parameters:
    - reply_ids: List of reply IDs to delete
    """
    if not request.reply_ids:
        raise HTTPException(
            status_code=400,
            detail="No reply IDs provided"
        )
    
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Convert string IDs to integers
            reply_ids = [int(id) for id in request.reply_ids]
            
            # Delete the post replies
            cursor.execute(
                """
                DELETE FROM post_reply 
                WHERE id = ANY(%s)
                RETURNING id
                """,
                (reply_ids,)
            )
            
            deleted_ids = cursor.fetchall()
            conn.commit()
            
            if not deleted_ids:
                raise HTTPException(
                    status_code=404,
                    detail="No post replies found to delete"
                )
            
            return {
                "message": "Post replies deleted successfully",
                "deleted_ids": [row[0] for row in deleted_ids]
            }
            
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid reply ID format. All IDs must be valid numbers."
        )
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete post replies: {str(e)}"
        )
    finally:
        conn.close()
        
        
        
