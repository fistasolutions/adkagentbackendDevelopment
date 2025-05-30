from typing import Dict, List, Optional, Any
from agents import Agent, Runner
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from db.db import get_connection
import logging

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

def get_comment_analysis_agent_instructions() -> str:
    return """You are an expert comment analyzer and response generator. Your role is to:

    1. Deep Comment Analysis:
       - Analyze comment sentiment and tone
       - Identify comment type (question, feedback, concern, suggestion)
       - Extract key points and underlying intent
       - Evaluate engagement potential
       - Assess response priority
    
    2. Response Decision Making:
       - Determine if response is warranted
       - Identify optimal response timing
       - Evaluate potential impact
       - Assess risk factors
       - Plan engagement strategy
    
    3. Response Planning:
       - Generate appropriate response suggestions
       - Consider post context and tone
       - Plan engagement approach
       - Assess response priority
       - Determine optimal timing
    
    4. Quality Assurance:
       - Ensure response relevance
       - Maintain brand voice
       - Consider community guidelines
       - Assess potential impact
       - Evaluate engagement potential
    
    You must return a JSON object with this exact structure:
    {
        "comments": [
            {
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
            }
        ]
    }"""

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

def get_post_analysis_agent_instructions() -> str:
    return """You are an expert post analyzer and comment strategist. Your role is to:

    1. Deep Content Analysis:
       - Analyze post content, tone, and context
       - Identify key themes and topics
       - Evaluate engagement potential
       - Assess risk factors and potential backlash
       - Determine optimal engagement times
    
    2. Comment Strategy Development:
       - Identify valuable engagement opportunities
       - Determine best commenting approaches
       - Assess potential impact
       - Evaluate risk levels
       - Plan optimal timing
    
    3. Contextual Understanding:
       - Consider post context and audience
       - Analyze current trends and timing
       - Evaluate brand voice alignment
       - Assess community engagement patterns
       - Identify potential conversation starters
    
    4. Risk Assessment:
       - Evaluate potential controversy
       - Assess brand alignment
       - Consider audience sensitivity
       - Identify safe engagement boundaries
       - Plan risk mitigation strategies
    
    You must return a JSON object with this exact structure:
    {
        "posts": [
            {
                "post_id": "string",
                "content": "string",
                "sentiment_score": float,
                "engagement_potential": float,
                "best_time_to_comment": "string",
                "suggested_comments": ["string"],
                "risk_score": float,
                "topics": ["string"],
                "tone": "string",
                "key_points": ["string"],
                "engagement_strategy": "string"
            }
        ]
    }"""

def get_comment_generation_agent_instructions() -> str:
    return """You are an expert at generating high-quality, professional comments for social media posts. Your role is to:

    1. Comment Quality Standards:
       - Generate comments that are professional and on-brand
       - Ensure contextual relevance and value
       - Create engaging and meaningful interactions
       - Maintain risk-free and backlash-proof content
       - Match the post's tone and style
    
    2. Contextual Understanding:
       - Consider original post context deeply
       - Align with brand voice and guidelines
       - Stay current with trends
       - Follow community standards
       - Understand audience expectations
    
    3. Content Guidelines:
       - Avoid controversial topics
       - Steer clear of generic responses
       - Prevent overly promotional content
       - Eliminate negative or divisive language
       - Ensure platform-appropriate content
    
    4. Engagement Optimization:
       - Add value to conversations
       - Maintain professional writing standards
       - Match post tone perfectly
       - Ensure platform appropriateness
       - Encourage meaningful interaction
    
    You must return a JSON object with this exact structure:
    {
        "comment_text": "string",
        "scheduled_time": "string",
        "engagement_score": float,
        "tone_match_score": float,
        "context_relevance_score": float
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

post_analysis_agent = Agent(
    name="Post Analysis Agent",
    instructions=get_post_analysis_agent_instructions(),
    output_type=PostAnalysisOutput
)

comment_generation_agent = Agent(
    name="Comment Generation Agent",
    instructions=get_comment_generation_agent_instructions(),
    output_type=CommentGenerationOutput
)

async def get_last_week_posts_and_comments(user_id: str, account_id: str) -> List[Dict[str, Any]]:
    """Get posts and their comments from the last week."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Get posts from last week
            one_week_ago = datetime.utcnow() - timedelta(days=7)
            cursor.execute(
                """
                SELECT p.id, p.content, p.created_at, c.id as comment_id, c.content as comment_content, c.created_at as comment_created_at
                FROM posts p
                LEFT JOIN comments c ON p.id = c.post_id
                WHERE p.user_id = %s 
                AND p.account_id = %s
                AND p.created_at > %s
                ORDER BY p.created_at DESC, c.created_at ASC
                """,
                (user_id, account_id, one_week_ago)
            )
            rows = cursor.fetchall()
            
            # Organize posts and comments
            posts = {}
            for row in rows:
                post_id = row[0]
                if post_id not in posts:
                    posts[post_id] = {
                        "id": post_id,
                        "content": row[1],
                        "created_at": row[2],
                        "comments": []
                    }
                if row[3]:  # If there's a comment
                    posts[post_id]["comments"].append({
                        "id": row[3],
                        "content": row[4],
                        "created_at": row[5]
                    })
            
            return list(posts.values())
    finally:
        conn.close()



@router.post("/test-analyze-and-respond-comments")
async def test_analyze_and_respond_to_comments():
    """Test endpoint with dummy data to analyze comments and generate responses."""
    try:
        # Dummy data for testing
        dummy_posts_with_comments = [
            {
                "id": "post1",
                "content": "We're thrilled to announce our new AI-powered analytics platform! Transform your data into actionable insights. #AI #Analytics #Innovation",
                "created_at": "2024-03-20T10:00:00Z",
                "comments": [
                    {
                        "id": "comment1",
                        "content": "This looks amazing! Can't wait to try it out. How does it compare to other solutions?",
                        "created_at": "2024-03-20T10:05:00Z"
                    },
                    {
                        "id": "comment2",
                        "content": "What's the pricing structure? And do you offer a free trial?",
                        "created_at": "2024-03-20T10:10:00Z"
                    }
                ]
            },
            {
                "id": "post2",
                "content": "Join us for our upcoming webinar on 'The Future of Digital Marketing' next Thursday at 2 PM EST. Register now! #DigitalMarketing #Webinar",
                "created_at": "2024-03-19T15:00:00Z",
                "comments": [
                    {
                        "id": "comment3",
                        "content": "Will there be a recording available for those who can't attend live?",
                        "created_at": "2024-03-19T15:30:00Z"
                    }
                ]
            }
        ]
        
        # Prepare input for analysis agent
        analysis_input = str(dummy_posts_with_comments)
        
        # Analyze comments using the analysis agent
        analysis_result = await Runner.run(
            comment_analysis_agent,
            input=analysis_input
        )
        
        # Handle the analysis output
        analysis_output = analysis_result.final_output
        if isinstance(analysis_output, str):
            import json
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
        for comment in comments_to_respond:
            # Generate response using response agent
            response_input = f"""Post Content: {comment.comment_text}
            Comment: {comment.comment_text}
            Comment Type: {comment.comment_type}
            Key Points: {', '.join(comment.key_points)}
            Tone: {comment.tone}
            Context: {comment.reason}"""
            
            response_result = await Runner.run(
                comment_response_agent,
                input=response_input
            )
            
            # Handle the response output
            response_output = response_result.final_output
            if isinstance(response_output, str):
                import json
                response_output = json.loads(response_output)
            
            # Convert to ResponseOutput model
            if not isinstance(response_output, ResponseOutput):
                response_output = ResponseOutput(**response_output)
            
            responses.append({
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
                "tone": comment.tone
            })
        
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

@router.post("/test-analyze-and-comment-posts")
async def test_analyze_and_comment_posts():
    """Test endpoint with dummy data to analyze posts and generate comments."""
    try:
        # Dummy data for testing
        dummy_posts = [
            {
                "id": "post1",
                "content": "We're thrilled to announce our new AI-powered analytics platform! Transform your data into actionable insights. #AI #Analytics #Innovation",
                "created_at": "2024-03-20T10:00:00Z"
            },
            {
                "id": "post2",
                "content": "Join us for our upcoming webinar on 'The Future of Digital Marketing' next Thursday at 2 PM EST. Register now! #DigitalMarketing #Webinar",
                "created_at": "2024-03-19T15:00:00Z"
            },
            {
                "id": "post3",
                "content": "Our team just completed a major milestone in our sustainability initiative. Proud of our progress towards a greener future! #Sustainability #GreenTech",
                "created_at": "2024-03-18T09:00:00Z"
            }
        ]
        
        # Analyze posts using the analysis agent
        analysis_result = await Runner.run(
            post_analysis_agent,
            input=str(dummy_posts)
        )
        
        # Handle the analysis output
        analysis_output = analysis_result.final_output
        if isinstance(analysis_output, str):
            import json
            analysis_output = json.loads(analysis_output)
        
        # Convert to PostAnalysisOutput model
        if not isinstance(analysis_output, PostAnalysisOutput):
            analysis_output = PostAnalysisOutput(**analysis_output)
        
        # Generate comments for each post
        generated_comments = []
        for post in analysis_output.posts:
            # Generate comment using comment generation agent
            comment_input = f"""Post Content: {post.content}
            Topics: {', '.join(post.topics)}
            Best Time: {post.best_time_to_comment}
            Risk Score: {post.risk_score}
            Tone: {post.tone}
            Key Points: {', '.join(post.key_points)}
            Engagement Strategy: {post.engagement_strategy}
            Suggested Comments: {', '.join(post.suggested_comments)}"""
            
            comment_result = await Runner.run(
                comment_generation_agent,
                input=comment_input
            )
            
            # Handle the comment output
            comment_output = comment_result.final_output
            if isinstance(comment_output, str):
                import json
                comment_output = json.loads(comment_output)
            
            # Convert to CommentGenerationOutput model
            if not isinstance(comment_output, CommentGenerationOutput):
                comment_output = CommentGenerationOutput(**comment_output)
            
            generated_comments.append({
                "post_id": post.post_id,
                "post_content": post.content,
                "generated_comment": comment_output.comment_text,
                "scheduled_time": comment_output.scheduled_time,
                "engagement_score": comment_output.engagement_score,
                "tone_match_score": comment_output.tone_match_score,
                "context_relevance_score": comment_output.context_relevance_score,
                "risk_score": post.risk_score,
                "topics": post.topics,
                "tone": post.tone,
                "key_points": post.key_points
            })
        
        return {
            "message": "Test completed successfully",
            "analysis_result": analysis_output.dict(),
            "generated_comments": generated_comments
        }
            
    except Exception as e:
        print(f"Error in test endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process test data: {str(e)}"
        ) 