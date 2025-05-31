from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from agent.adkagent import ADKAgent, TweetAgentSettings, CharacterSettings
from db.db import get_connection
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from agents import Agent

router = APIRouter()

# Pydantic Models
class CommentAnalysis(BaseModel):
    comment_id: str
    post_id: str
    comment_text: str
    author: str
    sentiment: str
    engagement_potential: float
    requires_response: bool
    response_priority: str
    response_type: str
    context: str
    key_points: List[str]
    tone: str
    engagement_strategy: str
    quality_metrics: dict

class CommentResponse(BaseModel):
    comment_id: str
    post_id: str
    response_text: str
    response_type: str
    tone: str
    engagement_score: float
    tone_match_score: float
    context_relevance_score: float
    quality_metrics: dict

class CommentResponseRequest(BaseModel):
    user_id: str
    account_id: str

# Database Functions
def get_last_week_posts_and_comments(user_id: str, account_id: str):
    """Fetch posts and comments from the last week"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get posts from the last week
            query = """
                SELECT p.*, c.* 
                FROM posts p
                LEFT JOIN comments c ON p.post_id = c.post_id
                WHERE p.user_id = %s 
                AND p.account_id = %s
                AND p.created_at >= NOW() - INTERVAL '7 days'
                ORDER BY p.created_at DESC, c.created_at DESC
            """
            
            cursor.execute(query, (user_id, account_id))
            result = cursor.fetchall()
            
            # Organize posts and comments
            posts = {}
            for row in result:
                if row['post_id'] not in posts:
                    posts[row['post_id']] = {
                        "post_id": row['post_id'],
                        "content": row['content'],
                        "created_at": row['created_at'],
                        "comments": []
                    }
                if row['comment_id']:  # If there are comments
                    posts[row['post_id']]["comments"].append({
                        "comment_id": row['comment_id'],
                        "text": row['text'],
                        "author": row['author'],
                        "created_at": row['created_at']
                    })
            
            return list(posts.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

# Test Data
TEST_POSTS = [
    {
        "post_id": "post1",
        "content": "Just launched our new AI-powered analytics dashboard! Check it out and let us know what you think. #AI #Analytics #Innovation",
        "created_at": "2024-03-15T10:00:00Z",
        "comments": [
            {
                "comment_id": "comment1",
                "text": "This looks amazing! How does it compare to other solutions in the market?",
                "author": "tech_enthusiast",
                "created_at": "2024-03-15T10:05:00Z"
            },
            {
                "comment_id": "comment2",
                "text": "The interface seems a bit cluttered. Any plans to simplify it?",
                "author": "user123",
                "created_at": "2024-03-15T10:10:00Z"
            }
        ]
    },
    {
        "post_id": "post2",
        "content": "We're hiring! Looking for talented developers to join our team. Remote positions available. #Hiring #TechJobs #RemoteWork",
        "created_at": "2024-03-14T15:00:00Z",
        "comments": [
            {
                "comment_id": "comment3",
                "text": "What's the tech stack you're using?",
                "author": "dev_candidate",
                "created_at": "2024-03-14T15:30:00Z"
            }
        ]
    }
]

# Comment Analysis Agent
comment_analysis_settings = TweetAgentSettings(
    characterSettings=CharacterSettings(
        characterSettings="""You are an expert at analyzing social media comments to determine which ones deserve responses and how to respond to them effectively.

Your task is to analyze each comment and determine:
1. Whether it requires a response
2. The priority level of the response
3. The type of response needed
4. The context and key points to address
5. The appropriate tone and engagement strategy

Follow these steps for each comment:

1. Initial Analysis:
   - Evaluate the comment's sentiment and intent
   - Identify key topics and questions
   - Assess the commenter's engagement level
   - Determine if the comment requires a response

2. Response Planning:
   - If response is needed, determine the priority level
   - Identify the type of response needed (clarification, appreciation, etc.)
   - Extract key points that need to be addressed
   - Determine the appropriate tone and engagement strategy

3. Quality Assessment:
   - Evaluate the comment's engagement potential
   - Assess the impact of responding
   - Consider the relationship with the commenter

Output Format:
{
    "comment_id": "string",
    "post_id": "string",
    "comment_text": "string",
    "author": "string",
    "sentiment": "string",
    "engagement_potential": float,
    "requires_response": boolean,
    "response_priority": "string",
    "response_type": "string",
    "context": "string",
    "key_points": ["string"],
    "tone": "string",
    "engagement_strategy": "string",
    "quality_metrics": {
        "sentiment_score": float,
        "engagement_potential": float,
        "response_urgency": float,
        "relationship_value": float
    }
}

Guidelines:
- Be thorough in your analysis
- Consider both the comment content and context
- Prioritize comments that add value to the conversation
- Identify opportunities for meaningful engagement
- Avoid responding to spam or inappropriate comments
- Consider the brand voice and values
- Evaluate the potential impact of responding"""
    )
)

comment_analysis_agent = Agent(
    name="Comment Analysis Agent",
    instructions=comment_analysis_settings.characterSettings.characterSettings,
    output_type=CommentAnalysis
)

# Comment Response Agent
comment_response_settings = TweetAgentSettings(
    characterSettings=CharacterSettings(
        characterSettings="""You are an expert at crafting engaging, authentic, and valuable responses to social media comments.

Your task is to generate high-quality responses that:
1. Address the commenter's specific points
2. Maintain the appropriate tone and style
3. Add value to the conversation
4. Encourage further engagement
5. Align with the brand voice

Follow these steps for each response:

1. Response Planning:
   - Review the comment analysis
   - Identify key points to address
   - Determine the appropriate tone
   - Plan the response structure

2. Response Generation:
   - Craft a clear and concise response
   - Address all key points
   - Use appropriate language and tone
   - Include relevant information
   - Encourage further engagement

3. Quality Check:
   - Ensure the response is relevant
   - Verify tone consistency
   - Check for clarity and conciseness
   - Assess engagement potential
   - Evaluate overall quality

Output Format:
{
    "comment_id": "string",
    "post_id": "string",
    "response_text": "string",
    "response_type": "string",
    "tone": "string",
    "engagement_score": float,
    "tone_match_score": float,
    "context_relevance_score": float,
    "quality_metrics": {
        "clarity_score": float,
        "engagement_potential": float,
        "tone_consistency": float,
        "value_added": float
    }
}

Guidelines:
- Keep responses concise and focused
- Maintain a professional yet friendly tone
- Address all key points from the comment
- Add value to the conversation
- Encourage further engagement
- Avoid generic or automated-sounding responses
- Consider the brand voice and values
- Ensure responses are timely and relevant"""
    )
)

comment_response_agent = Agent(
    name="Comment Response Agent",
    instructions=comment_response_settings.characterSettings.characterSettings,
    output_type=CommentResponse
)

@router.post("/analyze-and-respond-comments")
async def analyze_and_respond_comments(
    request: CommentResponseRequest,
    db: Session = Depends(get_connection)
):
    """Analyze comments and generate responses"""
    try:
        # Get posts and comments from the last week
        posts = get_last_week_posts_and_comments(request.user_id, request.account_id)
        
        all_responses = []
        
        # Process each post and its comments
        for post in posts:
            for comment in post.get("comments", []):
                # Analyze the comment
                analysis_result = await comment_analysis_agent.run(
                    comment_id=comment["comment_id"],
                    post_id=post["post_id"],
                    comment_text=comment["text"],
                    author=comment["author"],
                    post_content=post["content"]
                )
                
                # If the comment requires a response, generate one
                if analysis_result.requires_response:
                    response_result = await comment_response_agent.run(
                        comment_id=comment["comment_id"],
                        post_id=post["post_id"],
                        comment_text=comment["text"],
                        author=comment["author"],
                        analysis=analysis_result.dict()
                    )
                    
                    all_responses.append(response_result)
        
        return {
            "status": "success",
            "message": f"Generated {len(all_responses)} responses",
            "responses": all_responses
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-analyze-and-respond-comments")
async def test_analyze_and_respond_comments():
    """Test endpoint for comment analysis and response generation using dummy data"""
    try:
        all_responses = []
        
        # Process each test post and its comments
        for post in TEST_POSTS:
            for comment in post.get("comments", []):
                # Analyze the comment
                analysis_result = await comment_analysis_agent.run(
                    comment_id=comment["comment_id"],
                    post_id=post["post_id"],
                    comment_text=comment["text"],
                    author=comment["author"],
                    post_content=post["content"]
                )
                
                # If the comment requires a response, generate one
                if analysis_result.requires_response:
                    response_result = await comment_response_agent.run(
                        comment_id=comment["comment_id"],
                        post_id=post["post_id"],
                        comment_text=comment["text"],
                        author=comment["author"],
                        analysis=analysis_result.dict()
                    )
                    
                    all_responses.append({
                        "analysis": analysis_result.dict(),
                        "response": response_result.dict()
                    })
        
        return {
            "status": "success",
            "message": f"Generated {len(all_responses)} responses",
            "results": all_responses
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process test data: {str(e)}") 