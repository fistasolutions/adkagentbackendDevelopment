from typing import Dict, List, Optional, Any
from agents import Agent, Runner
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from requests_oauthlib import OAuth1Session
from db.db import get_connection
import logging
import json
import random
import httpx
import time

from agent.draft_comment_reply_agent import (
    DraftCommentReplyAgent,
    DraftCommentReplyRequest,
    DraftCommentReplyResponse,
)
from agent.risk_assessment_agent import RiskAssessmentAgent, RiskAssessmentRequest

router = APIRouter()

load_dotenv()

router = APIRouter()
class TweetRequest(BaseModel):
    user_id: str
    account_id: str


class DraftCommentReplyRequestPost(BaseModel):
    previous_comment: str
    num_drafts: int
    prompt: Optional[str] = None
    character_settings: Optional[str] = None
    account_id: str
    user_id: int

class TweetUpdateRequest(BaseModel):
    tweet_id: str
    content: Optional[str] = None
    scheduled_time: Optional[str] = None


class TweetImageUpdateRequest(BaseModel):
    tweet_id: str
    image_urls: List[str]


class DeleteTweetRequest(BaseModel):
    tweet_id: str


class DeleteTweetImageRequest(BaseModel):
    tweet_id: str
    image_urls: List[str]
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
    

class TwitterComment(BaseModel):
    id: str
    text: str
    author_id: str
    created_at: str
    username: str

class PostWithComments(BaseModel):
    id: int
    content: str
    user_id: int
    account_id: int
    status: str
    posted_id: Optional[str]
    posted_time: Optional[datetime]
    created_at: datetime
    comments: List[TwitterComment]

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
        - Today is {datetime.utcnow().strftime("%Y-%m-%d")}
        
        When scheduling responses, strictly adhere to these posting schedule constraints.
        The scheduled_time field should be one of the times returned by get_next_scheduled_times().
        """

    return f"""You are an expert comment analyzer and response generator. Your role is to:

    1. Deep Comment Analysis:
       - Analyze comment sentiment and tone
       - Identify comment type (question, feedback, concern, suggestion, greeting)
       - Extract key points and underlying intent
       - Evaluate engagement potential
       - Assess response priority
    
    2. Response Decision Making:
       - Always respond to greetings and casual interactions to maintain engagement
       - Determine if response is warranted (default to True for greetings)
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



def get_next_scheduled_times(posting_days: dict, posting_time: dict, posting_frequency: int, pre_create: int) -> List[str]:
    """
    Generate a list of scheduled times for posts based on the given parameters.
    
    Args:
        posting_days: Dict mapping days to boolean values (e.g., {"月": True, "火": False, ...})
        posting_time: Dict mapping hours to boolean values (e.g., {"0": True, "1": False, ...})
        posting_frequency: Number of posts per day
        pre_create: Number of days in advance to schedule posts
    
    Returns:
        List of ISO format datetime strings for scheduled posts
    """
    # Map Japanese day names to weekday numbers (0 = Monday, 6 = Sunday)
    day_mapping = {
        "月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6
    }
    
    # Get current time in UTC
    current_time = datetime.utcnow()
    
    # Get enabled days (days marked as True)
    enabled_days = [day for day, enabled in posting_days.items() if enabled]
    if not enabled_days:
        raise ValueError("No posting days are enabled")
    print("enabled_days",enabled_days)
    # Get enabled hours (hours marked as True)
    enabled_hours = [int(hour) for hour, enabled in posting_time.items() if enabled]
    if not enabled_hours:
        raise ValueError("No posting hours are enabled")
    
    # Sort enabled hours
    enabled_hours.sort()
    
    # Calculate total number of posts needed
    total_posts = posting_frequency * pre_create
    print("total_posts",total_posts)
    scheduled_times = []
    current_date = current_time.date()
    
    while len(scheduled_times) < total_posts:
        # Check if current day is enabled
        current_day_jp = ["月", "火", "水", "木", "金", "土", "日"][current_date.weekday()]
        
        if current_day_jp in enabled_days:
            # For each enabled hour on this day
            for hour in enabled_hours:
                # Create datetime for this hour
                post_time = datetime.combine(current_date, datetime.min.time().replace(hour=hour))
                
                # Only add if it's in the future
                if post_time > current_time:
                    scheduled_times.append(post_time.isoformat() + "Z")
                    
                    # If we have enough posts for today, break
                    if len([t for t in scheduled_times if t.startswith(current_date.isoformat())]) >= posting_frequency:
                        break
        
        # Move to next day
        current_date += timedelta(days=1)
    
    # Sort and return the scheduled times
    return sorted(scheduled_times)[:total_posts]

def parse_pre_create_days(pre_create_str: str) -> int:
    """
    Parse the pre_create string from Japanese format (e.g., "7日") to an integer.
    
    Args:
        pre_create_str: String in format like "7日"
    
    Returns:
        Integer number of days
    """
    try:
        # Remove the "日" character and convert to integer
        return int(pre_create_str.replace("日", ""))
    except (ValueError, AttributeError):
        # If parsing fails, return a default value of 7
        return 7

def parse_posting_frequency(frequency_str: str) -> int:
    """
    Parse the posting frequency string (e.g., "1day") to an integer.
    
    Args:
        frequency_str: String in format like "1day"
    
    Returns:
        Integer number of posts per day
    """
    try:
        # Remove the "day" suffix and convert to integer
        return int(frequency_str.replace("day", ""))
    except (ValueError, AttributeError):
        # If parsing fails, return a default value of 1
        return 1


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



async def get_posts_with_comments(
    limit: int = Query(20, ge=1, le=50)
):
    """
    Fetch posts with their comments from Twitter API.
    Only returns posts with status "posted" in round-robin order.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get posts with status 'posted' in round-robin order
            cursor.execute(
                """
                SELECT id, content, user_id, account_id, status, posted_id, 
                       posted_time, created_at
                FROM posts 
                WHERE status = 'posted'
                AND (
                    comments_fetched_at IS NULL 
                    OR DATE(comments_fetched_at) < CURRENT_DATE
                )
                ORDER BY COALESCE(comments_fetched_at, created_at) ASC
                LIMIT %s
                """,
                (limit,)
            )
            posts = cursor.fetchall()
            
            result = []
            for post in posts:
                posted_id = post[5]  # post[5] is posted_id
                account_id = post[3]  # post[3] is account_id
                if not posted_id:
                    continue

                # Fetch credentials for this account
                def get_twitter_credentials_for_account(account_id):
                    conn_inner = get_connection()
                    try:
                        with conn_inner.cursor() as cursor_inner:
                            cursor_inner.execute(
                                """
                                SELECT bearer_token, twitter_access_token, twitter_api_key, twitter_api_secret, twitter_access_token_secret
                                FROM twitter_account  
                                WHERE account_id = %s
                                """,
                                (account_id,)
                            )
                            result_inner = cursor_inner.fetchone()
                            if not result_inner:
                                raise Exception(f"No Twitter credentials found for account_id {account_id}")
                            return {
                                "bearer_token": result_inner[0],
                                "access_token": result_inner[1],
                                "api_key": result_inner[2],
                                "api_secret": result_inner[3],
                                "access_token_secret": result_inner[4]
                            }
                    finally:
                        conn_inner.close()

                def get_twitter_auth(credentials):
                    return OAuth1Session(
                        credentials["api_key"],
                        client_secret=credentials["api_secret"],
                        resource_owner_key=credentials["access_token"],
                        resource_owner_secret=credentials["access_token_secret"]
                    )

                try:
                    credentials = get_twitter_credentials_for_account(account_id)
                except Exception as e:
                    print(f"No Twitter credentials found for account_id {account_id}: {str(e)}")
                    continue

                oauth = get_twitter_auth(credentials)
                print("oauth", oauth)

                # Update comments_fetched_at immediately after fetching post
                with conn.cursor() as update_cursor:
                    update_cursor.execute(
                        """
                        UPDATE posts 
                        SET comments_fetched_at = %s
                        WHERE id = %s
                        """,
                        (datetime.utcnow(), post[0])
                    )
                    conn.commit()

                # Add delay between requests to avoid rate limiting
                time.sleep(1)  # 1 second delay between requests

                # Fetch comments from Twitter API
                url = f"https://api.twitter.com/2/tweets/search/recent"
                params = {
                    "query": f"in_reply_to_tweet_id:{posted_id}",
                    "tweet.fields": "author_id,created_at,in_reply_to_user_id",
                    "expansions": "author_id",
                    "user.fields": "username",
                    "max_results": 100
                }
                
                try:
                    response = oauth.get(url, params=params)
                    print(f"Twitter API response for tweet {posted_id}: Status {response.status_code}")
                    
                    # Check rate limit headers
                    remaining_requests = int(response.headers.get('x-rate-limit-remaining', 0))
                    reset_time = int(response.headers.get('x-rate-limit-reset', 0))
                    
                    if remaining_requests <= 1:  # If we're about to hit the rate limit
                        wait_time = reset_time - int(time.time())
                        if wait_time > 0:
                            print(f"Rate limit almost reached. Waiting {wait_time} seconds...")
                            time.sleep(wait_time)
                    
                    if response.status_code == 429:  # Rate limit exceeded
                        wait_time = reset_time - int(time.time())
                        if wait_time > 0:
                            print(f"Rate limit hit for tweet {posted_id}, waiting {wait_time} seconds...")
                            time.sleep(wait_time)
                            response = oauth.get(url, params=params)
                    
                    if response.status_code != 200:
                        print(f"Twitter API error for tweet {posted_id}: {response.text}")
                        continue

                    twitter_data = response.json()
                    print(f"Twitter API data for tweet {posted_id}: {twitter_data}")
                    
                    # Create a map of author_id -> username
                    author_map = {
                        user["id"]: user["username"] 
                        for user in twitter_data.get("includes", {}).get("users", [])
                    }
                    
                    # Convert Twitter comments to CommentResponse objects
                    comment_list = []
                    for tweet in twitter_data.get("data", []):
                        author_id = tweet["author_id"]
                        comment_list.append(TwitterComment(
                            id=tweet["id"],
                            text=tweet["text"],
                            author_id=author_id,
                            created_at=tweet["created_at"],
                            username=author_map.get(author_id, "unknown_user")
                        ))
                    
                    # Create PostWithComments object
                    post_with_comments = PostWithComments(
                        id=post[0],
                        content=post[1],
                        user_id=post[2],
                        account_id=post[3],
                        status=post[4],
                        posted_id=post[5],
                        posted_time=post[6],
                        created_at=post[7],
                        comments=comment_list
                    )
                    result.append(post_with_comments)
                except Exception as e:
                    print(f"Error processing tweet {posted_id}: {str(e)}")
                    continue
            
            return result
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.post("/test-analyze-and-respond-comments")
async def test_analyze_and_respond_to_comments():
    """Test endpoint with dummy data to analyze comments and generate responses, optimized for Twitter API rate limits."""
    try:
        # Get up to 20 posts with comments using the local function
        posts_with_comments = await get_posts_with_comments(limit=20)

        if not posts_with_comments:
            return {"message": "No posts with comments found"}

        all_responses = []
        processed_post_ids = []
        for post in posts_with_comments:
            # Skip if post has no comments
            if not post.comments:
                continue
                
            user_id = post.user_id
            account_id = post.account_id
            post_id = post.id
            processed_post_ids.append(post_id)
            
            # Get post settings for the agent
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT posting_day, posting_time, posting_frequency, posting_time, pre_create
                    FROM persona_notify 
                    WHERE notify_type = 'commentReply'
                    AND user_id = %s 
                    AND account_id = %s
                    """,
                    (user_id, account_id),
                )
                post_settings = cursor.fetchone()
                if not post_settings:
                    continue  
                posting_day = post_settings[0]
                posting_time = post_settings[1]
                posting_frequency = parse_posting_frequency(post_settings[2])
                posting_time = post_settings[3]
                pre_create = parse_pre_create_days(post_settings[4])
                
                # Get scheduled times for responses
                scheduled_times = get_next_scheduled_times(
                    posting_day,
                    posting_time,
                    posting_frequency,
                    pre_create
                )
                
                post_settings_data = {
                    "posting_day": posting_day,
                    "posting_time": posting_time,
                    "posting_frequency": posting_frequency,
                    "posting_time": posting_time,
                    "scheduled_times": scheduled_times
                }
                comment_analysis_agent.instructions = get_comment_analysis_agent_instructions(post_settings_data)

            # Prepare comments for analysis
            comments_for_analysis = []
            conn_check = get_connection()
            try:
                with conn_check.cursor() as cursor_check:
                    for comment in post.comments:
                        # Check if this comment has already been responded to
                        print("comment",comment)
                        cursor_check.execute(
                            """
                            SELECT 1 FROM comments_reply WHERE comment_id = %s
                            """,
                            (comment.id,)
                        )
                        if cursor_check.fetchone():
                            continue  # Already responded, skip
                        comments_for_analysis.append({
                            "tweet_id": post.posted_id,
                            "tweet_text": post.content,
                            "comment": comment.text,
                            "username": comment.username,
                            "comment_id": comment.id
                        })
            finally:
                conn_check.close()

            if not comments_for_analysis:
                continue

            # Analyze comments using the analysis agent
            analysis_input = str(comments_for_analysis)
            print(f"Analyzing comments: {analysis_input}")
            analysis_result = await Runner.run(
                comment_analysis_agent,
                input=analysis_input
            )
            analysis_output = analysis_result.final_output
            if isinstance(analysis_output, str):
                analysis_output = json.loads(analysis_output)
            if not isinstance(analysis_output, AnalysisOutput):
                analysis_output = AnalysisOutput(**analysis_output)
            print(f"Analysis output: {analysis_output}")
            
            comments_to_respond = [
                comment for comment in analysis_output.comments
                if comment.should_respond
            ]
            print(f"Comments to respond: {len(comments_to_respond)}")
            
            if not comments_to_respond:
                print("No comments to respond to, skipping...")
                continue

            templates = await get_template_text(user_id, account_id)
            print(f"Got templates: {templates is not None}")
            responses = []
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    for i, comment in enumerate(comments_to_respond):
                        print(f"Processing comment: {comment.comment_text}")
                        response_text = None
                        if templates and templates:  # Check if templates exist and are not empty
                            template = random.choice(templates)
                            if template and template.strip():  # Check if template is not empty
                                response_text = template
                                print(f"Using template response: {response_text}")
                        
                        # If no template or template is empty, use suggested response
                        if not response_text:
                            response_text = comment.suggested_response
                            print(f"Using suggested response: {response_text}")

                        tweet_url = f"https://x.com/i/web/status/{post.posted_id}"
                        
                        # Get scheduled time from the list of available times
                        scheduled_time = scheduled_times[i % len(scheduled_times)] if scheduled_times else datetime.utcnow()
                        
                        # Save response to comments_reply table
                        try:
                            print(f"Attempting to save response to database: {response_text}")
                            cursor.execute(
                                """
                                INSERT INTO comments_reply 
                                (reply_text, risk_score, user_id, account_username, schedule_time, commentor_username, tweet_id, original_comment, tweet_url, comment_id)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                                """,
                                (
                                    response_text,
                                    20,
                                    user_id,
                                    account_id,
                                    scheduled_time,
                                    comment.commentor_username,
                                    post.posted_id,
                                    comment.comment_text,
                                    tweet_url,
                                    comment.comment_id
                                )
                            )
                            reply_id = cursor.fetchone()[0]
                            print(f"Successfully saved response with ID: {reply_id}")
                            conn.commit()
                        except Exception as e:
                            print(f"Error saving response to database: {str(e)}")
                            conn.rollback()
                            continue

                        responses.append({
                            "reply_id": reply_id,
                            "comment_id": comment.comment_id,
                            "post_id": post.posted_id,
                            "response_text": response_text,
                            "scheduled_time": scheduled_time,
                            "priority": comment.response_priority,
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
                    c.created_at,
                    c.image_urls,
                    c.risk_assesments
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
                    "created_at": row[10],
                    "image_urls": row[11],
                    "risk_assesments": row[12] if row[12] else None
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
        
        
@router.put("/update-comment")
async def update_tweet(request: TweetUpdateRequest):
    """Update the content or scheduled time of a tweet."""
    try:
        if not request.content and not request.scheduled_time:
            raise HTTPException(
                status_code=400,
                detail="At least one of content or scheduled_time must be provided",
            )

        # Perform risk assessment if content is being updated
        risk_assessment = None
        if request.content:
            risk_agent = RiskAssessmentAgent()
            risk_assessment = await risk_agent.get_response(RiskAssessmentRequest(content=request.content))
            print(risk_assessment)
        
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # First check if the tweet exists
                cursor.execute(
                    """
                    SELECT id
                    FROM  comments_reply
                    WHERE id = %s
                    """,
                    (request.tweet_id,),
                )
                tweet = cursor.fetchone()

                if not tweet:
                    raise HTTPException(status_code=404, detail="Tweet not found")

                # Prepare the update query based on provided fields
                update_fields = []
                update_values = []

                if request.content:
                    update_fields.append("reply_text = %s")
                    update_values.append(request.content)
                    # Add risk score if content is being updated
                    if risk_assessment:
                        update_fields.append("risk_score = %s")
                        update_values.append(risk_assessment.overall_risk_score)
                        # Convert risk assessment to JSON string
                        risk_assessment_json = json.dumps({
                            "risk_categories": [category.dict() for category in risk_assessment.risk_categories],
                            "risk_assignment": risk_assessment.risk_assignment
                        })
                        update_fields.append("risk_assesments = %s")
                        update_values.append(risk_assessment_json)

                if request.scheduled_time:
                    try:
                        update_fields.append("schedule_time = %s")
                        update_values.append(request.scheduled_time)
                    except ValueError:
                        raise HTTPException(
                            status_code=400,
                            detail="Invalid scheduled_time format. Use ISO format: YYYY-MM-DDTHH:MM:SSZ",
                        )

                # Add tweet_id to the values list
                update_values.append(request.tweet_id)

                # Construct and execute the update query
                update_query = f"""
                    UPDATE comments_reply 
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                    RETURNING id, reply_text, schedule_time, risk_score, risk_assesments
                """

                cursor.execute(update_query, update_values)
                updated_tweet = cursor.fetchone()

                conn.commit()

                risk_assesments_value = updated_tweet[4]
                if isinstance(risk_assesments_value, str):
                    try:
                        risk_assesments_value = json.loads(risk_assesments_value)
                    except Exception:
                        pass
                response = {
                    "message": "Tweet updated successfully",
                    "tweet": {
                        "id": updated_tweet[0],
                        "reply_text": updated_tweet[1],
                        "scheduled_time": updated_tweet[2],
                        "risk_score": updated_tweet[3],
                        "risk_assesments": risk_assesments_value
                    }
                }

                return response

        except HTTPException as he:
            raise he
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update tweet: {str(db_error)}"
            )
        finally:
            conn.close()

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating tweet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update tweet: {str(e)}")


@router.put("/update-comment-image")
async def update_tweet_image(request: TweetImageUpdateRequest):
    """Append new image URLs to a tweet, avoiding duplicates."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # First check if the tweet exists and get current images
                cursor.execute(
                    """
                    SELECT id, image_urls
                    FROM comments_reply 
                    WHERE id = %s
                    """,
                    (request.tweet_id,),
                )
                tweet = cursor.fetchone()

                if not tweet:
                    raise HTTPException(status_code=404, detail="Tweet not found")

                current_images = tweet[1]
                if current_images:
                    try:
                        if isinstance(current_images, str):
                            current_images = json.loads(current_images)
                    except Exception:
                        current_images = []
                else:
                    current_images = []

                # Append new images, avoiding duplicates
                updated_images = list(dict.fromkeys(current_images + request.image_urls))

                # Update the image URLs (as JSONB)
                cursor.execute(
                    """
                    UPDATE comments_reply 
                    SET image_urls = %s
                    WHERE id = %s
                    RETURNING id, image_urls
                    """,
                    (json.dumps(updated_images), request.tweet_id),
                )
                updated_tweet = cursor.fetchone()

                conn.commit()

                return {
                    "message": "Tweet images updated successfully",
                    "tweet": {
                        "id": updated_tweet[0],
                        "image_urls": updated_tweet[1],
                    },
                }

        except HTTPException as he:
            raise he
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update tweet images: {str(db_error)}"
            )
        finally:
            conn.close()

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating tweet images: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update tweet images: {str(e)}")
    
    

@router.delete("/delete-comment-image")
async def delete_tweet_image(request: DeleteTweetImageRequest):
    """Delete specific image URLs from a tweet's Image_url field."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # First check if the tweet exists and get current images
                cursor.execute(
                    """
                    SELECT id, image_urls
                    FROM comments_reply 
                    WHERE id = %s
                    """,
                    (request.tweet_id,),
                )
                tweet = cursor.fetchone()

                if not tweet:
                    raise HTTPException(status_code=404, detail="Tweet not found")

                current_images = tweet[1]
                if current_images:
                    try:
                        if isinstance(current_images, str):
                            current_images = json.loads(current_images)
                    except Exception:
                        current_images = []
                else:
                    current_images = []

                # Remove the specified image URLs
                updated_images = [url for url in current_images if url not in request.image_urls]

                # Update the image URLs (as JSONB)
                cursor.execute(
                    """
                    UPDATE comments_reply 
                    SET image_urls = %s
                    WHERE id = %s
                    RETURNING id, image_urls
                    """,
                    (json.dumps(updated_images), request.tweet_id),
                )
                updated_tweet = cursor.fetchone()

                conn.commit()

                return {
                    "message": "Tweet images deleted successfully",
                    "tweet": {
                        "id": updated_tweet[0],
                        "image_urls": updated_tweet[1],
                    },
                }

        except HTTPException as he:
            raise he
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to delete tweet images: {str(db_error)}"
            )
        finally:
            conn.close()

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error deleting tweet images: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete tweet images: {str(e)}")




@router.post("/generate-draft-comments", response_model=DraftCommentReplyResponse)
async def generate_draft_comments(request: DraftCommentReplyRequestPost):
    """
    Generate draft comments based on a previous comment.

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
        agent = DraftCommentReplyAgent()
        response = await agent.get_response(
            DraftCommentReplyRequest(
                previous_comment=request.previous_comment,
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

@router.post("/regenerate-comments")
async def regenerate_comments(request: CommentResponseRequest):
    """Regenerate all unposted comment replies for a user and account."""
    print("Regenerating comment replies...")
    try:
        # First check for character settings and get competitor data
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Check for character settings
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
                
                if not character_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="Character settings not found. Please set up your character settings before generating comment replies.",
                    )

                cursor.execute(
                    """
                    SELECT posting_day, posting_time, posting_frequency, posting_time, pre_create
                    FROM persona_notify 
                    WHERE user_id = %s 
                    AND account_id = %s
                    AND notify_type = 'commentReply'
                    """,
                    (request.user_id, request.account_id),
                )
                post_settings = cursor.fetchone()
                
                if not post_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="Post settings data not found. Please set up your post settings before generating comment replies.",
                    )
                
                # Parse the post settings
                posting_day = post_settings[0]  # This is a JSON object
                posting_time = post_settings[1]  # This is a JSON object
                posting_frequency = parse_posting_frequency(post_settings[2])  # Parse frequency string
                posting_time = post_settings[3]
                pre_create = parse_pre_create_days(post_settings[4])  # Parse Japanese format

                # Get scheduled times based on settings
                scheduled_times = get_next_scheduled_times(
                    posting_day,
                    posting_time,
                    posting_frequency,
                    pre_create
                )
                
                # Format post settings data for the agent
                post_settings_data = {
                    "posting_day": posting_day,
                    "posting_time": posting_time,
                    "posting_frequency": posting_frequency,
                    "posting_time": posting_time,
                    "pre_create": pre_create,
                    "scheduled_times": scheduled_times
                }

                # Get all unposted comments that need replies
                cursor.execute(
                    """
                    SELECT c.id, c.original_comment, c.tweet_id, c.commentor_username, c.tweet_url
                    FROM comments_reply c
                    WHERE c.user_id = %s 
                    AND c.account_username = %s 
                    AND c.post_status = 'unposted'
                    """,
                    (request.user_id, request.account_id),
                )
                unposted_comments = cursor.fetchall()

                # Delete all unposted comment replies
                cursor.execute(
                    """
                    DELETE FROM comments_reply 
                    WHERE user_id = %s 
                    AND account_username = %s 
                    AND post_status = 'unposted'
                    """,
                    (request.user_id, request.account_id),
                )
                conn.commit()
                
        finally:
            conn.close()

        # Get templates for comment replies
        templates = await get_template_text(request.user_id, request.account_id)
        
        # Process each comment and generate new replies
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                current_time = datetime.utcnow()
                saved_replies = []
                
                for i, comment in enumerate(unposted_comments):
                    # Get scheduled time from the list of available times
                    scheduled_time = scheduled_times[i % len(scheduled_times)] if scheduled_times else datetime.utcnow()
                    
                    # Generate response using template or suggested response
                    response_text = None
                    
                    # First try to use templates if available
                    if templates and templates:
                        template = random.choice(templates)
                        if template and template.strip():
                            response_text = template
                            print(f"Using template response: {response_text}")
                    
                    # Only use AI generation if no templates are available
                    if not response_text:
                        print("No templates available, using AI generation")
                        # Use the comment analysis agent to generate a response
                        analysis_input = str([{
                            "tweet_id": comment[2],
                            "tweet_text": "",  # We don't have the original tweet text
                            "comment": comment[1],
                            "username": comment[3],
                            "comment_id": comment[0]
                        }])
                        
                        analysis_result = await Runner.run(
                            comment_analysis_agent,
                            input=analysis_input
                        )
                        analysis_output = analysis_result.final_output
                        if isinstance(analysis_output, str):
                            analysis_output = json.loads(analysis_output)
                        if not isinstance(analysis_output, AnalysisOutput):
                            analysis_output = AnalysisOutput(**analysis_output)
                        
                        if analysis_output.comments and analysis_output.comments[0].suggested_response:
                            response_text = analysis_output.comments[0].suggested_response
                            print(f"Using AI generated response: {response_text}")
                        else:
                            print("No response could be generated, skipping comment")
                            continue  # Skip if no response could be generated

                    # Save the new reply
                    cursor.execute(
                        """
                        INSERT INTO comments_reply 
                        (reply_text, risk_score, user_id, account_username, schedule_time, 
                         commentor_username, tweet_id, original_comment, tweet_url, comment_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, reply_text, schedule_time, risk_score
                        """,
                        (
                            response_text,
                            20,  # Default risk score
                            request.user_id,
                            request.account_id,
                            scheduled_time,
                            comment[3],  # commentor_username
                            comment[2],  # tweet_id
                            comment[1],  # original_comment
                            comment[4],  # tweet_url
                            comment[0]   # comment_id
                        )
                    )
                    reply_data = cursor.fetchone()
                    saved_replies.append({
                        "id": reply_data[0],
                        "reply_text": reply_data[1],
                        "scheduled_time": reply_data[2],
                        "risk_score": reply_data[3]
                    })
                
                conn.commit()
                
                return {
                    "message": f"Successfully regenerated {len(saved_replies)} comment replies",
                    "replies": saved_replies
                }
                
        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save comment replies to database: {str(db_error)}",
            )
        finally:
            conn.close()
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error regenerating comment replies: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to regenerate comment replies: {str(e)}"
        )

