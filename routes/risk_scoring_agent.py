from typing import Dict, List, Any
from agents import Agent, Runner
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi import  HTTPException, Depends
from fastapi import APIRouter, HTTPException, Depends,Response
from db.db import get_connection
import json
import re
load_dotenv()


router = APIRouter()
class TweetOutput(BaseModel):
    tweet: str
    hashtags: List[str]
    impact_score: float
    reach_estimate: int
    engagement_potential: float

class RiskScoringRequest(BaseModel):
    text: str
    comments: str

class RiskScoringResponse(BaseModel):
    risk_score: int
    risk_factors: List[str]
    explanation: str

class TweetRiskRequest(BaseModel):
    user_id: str
    username: str

class TweetRiskItem(BaseModel):
    tweet_id: str
    text: str
    risk_score: int
    risk_factors: List[str]
    explanation: str

class CommentRiskItem(BaseModel):
    comment_id: str
    username: str
    text: str
    risk_score: int
    risk_factors: List[str]
    explanation: str

class TweetWithCommentsRiskItem(BaseModel):
    tweet_id: str
    tweet_text: str
    tweet_risk_score: int
    tweet_risk_factors: List[str]
    tweet_explanation: str
    comments: List[CommentRiskItem]

class TweetRiskResponse(BaseModel):
    username: str
    account_id: str
    total_analyzed: int
    tweets: List[TweetWithCommentsRiskItem]
    average_risk_score: float

def get_tweet_agent_instructions(character_settings: str = None) -> str:
    base_instructions = """You are a professional tweet generation expert specializing in creating natural, human-like content with an educated perspective. Your role is to:
    1. Generate EXACTLY FIVE unique, natural-sounding tweets that read as if written by an educated professional
    2. Each tweet must follow these guidelines:
       - Write in a natural, conversational tone while maintaining professionalism
       - Include personal insights and observations that feel authentic
       - Use appropriate contractions and natural language patterns
       - Include only verified facts and truthful information
       - Avoid emotionally charged or provocative content
       - Never spread misinformation or unverified claims
       - Include relevant hashtags (2-3 per tweet)
       - Maintain optimal length (240-280 characters)
       - Use clear, professional call-to-actions
       - Base content on verifiable data and statistics
    3. Content must be:
       - Natural and conversational while remaining professional
       - Factually accurate and verifiable
       - Professional and business-appropriate
       - Focused on industry insights and developments
       - Based on objective analysis rather than emotional appeal
       - Respectful and inclusive
       - Include personal perspective where appropriate
    4. Writing style should:
       - Sound like an educated professional sharing insights
       - Use natural language patterns and occasional contractions
       - Include personal observations and experiences
       - Maintain a balance between professional and approachable
       - Show personality while staying within professional boundaries
       - Show personality while staying within professional boundaries
    5. Return the tweets in the following JSON format:
       {
         "tweets": [
           {
             "tweet": "tweet text here",
             "hashtags": ["hashtag1", "hashtag2"],
             "impact_score": 85.5,
             "reach_estimate": 5000,
             "engagement_potential": 0.12
           },
           ... (4 more tweets)
         ],
         "total_impact_score": 427.5,
         "average_reach_estimate": 5000,
         "overall_engagement_potential": 0.12
       }
       """
    
    if character_settings:
        return f"""{base_instructions}

    Additionally, you must follow these character-specific guidelines:
    {character_settings}
    
    - Show personality while staying within professional boundaries
    5. Return the tweets in the following JSON format:
     

    Your tweets should reflect this character's personality, tone, and style while maintaining professional standards."""
    
    return base_instructions

def get_risk_scoring_agent_instructions() -> str:
    return """You are a risk analysis expert who evaluates social media content for potential risks.
    
    Your task is to:
    1. Analyze the provided text (tweet or post) and any associated comments
    2. Evaluate the content for potential risks including:
       - Legal issues (defamation, copyright, etc.)
       - Regulatory compliance concerns
       - Reputational risks
       - Community guideline violations
       - Potential for misinterpretation
       - Controversial or sensitive topics
       - Offensive language or themes
    3. Assign a risk score from 1 to 100 where:
       - 1-20: Minimal risk
       - 21-40: Low risk
       - 41-60: Moderate risk
       - 61-80: High risk
       - 81-100: Extreme risk
    4. Provide specific risk factors identified in the content
    5. Include a brief explanation for the risk assessment
    
    Return your analysis in the following JSON format:
    {
      "risk_score": 45,
      "risk_factors": ["potentially controversial topic", "ambiguous wording"],
      "explanation": "The content discusses a politically divisive topic and contains phrasing that could be misinterpreted."
    }
    """

tweet_agent = Agent(
    name="Tweet Agent",
    instructions=get_tweet_agent_instructions(),
    handoffs=[
        "Role Model Analysis Agent",
        "Industry Standard Analysis Agent",
        "Competitor Analysis Agent",
        "Trend Strategy Agent",
        "Risk Analyzer Agent",
        "Impact Analyzer Agent",
        "Persona Agent"
    ]
)

risk_scoring_agent = Agent(
    name="Risk Scoring Agent",
    instructions=get_risk_scoring_agent_instructions(),
)

@router.post("/generate-tweets", response_model=List[Dict[str, str]])
async def generate_tweets(request: Any):
    """Generate five high-quality tweets using the Tweet Agent."""
    print("Generating tweets...")
        
@router.post("/risk-scoring", response_model=RiskScoringResponse)
async def analyze_risk(request: RiskScoringRequest):
    """Analyze text and comments for risk factors and return a risk score between 1-100."""
    try:
        runner = Runner()
        input_text = request.text
        if request.comments:
            input_text += "\n\nComments:\n" + request.comments
        result = await runner.run(risk_scoring_agent, input_text)
        if hasattr(result, "final_output") and result.final_output:
            result_text = result.final_output
        else:
            result_text = str(result)
        import json
        import re
        
        json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', result_text)
        if not json_match:
            json_match = re.search(r'{[\s\S]*?"risk_score"[\s\S]*?}', result_text)
            
        if json_match:
            try:
                response_dict = json.loads(json_match.group(1) if '```json' in result_text else json_match.group(0))
            except json.JSONDecodeError:
                json_str = json_match.group(1) if '```json' in result_text else json_match.group(0)
                json_str = re.sub(r'[\n\r\t]', '', json_str)
                try:
                    response_dict = json.loads(json_str)
                except:
                    response_dict = {
                        "risk_score": 50, 
                        "risk_factors": ["Error parsing JSON response"],
                        "explanation": f"Failed to parse the agent's JSON response"
                    }
        else:
            response_dict = {
                "risk_score": 50,
                "risk_factors": ["Unable to extract JSON from response"],
                "explanation": "Agent response did not contain properly formatted JSON"
            }
        
        risk_score = response_dict.get("risk_score", 50)
        if not isinstance(risk_score, int):
            try:
                risk_score = int(float(risk_score))
            except:
                risk_score = 50
                
        risk_factors = response_dict.get("risk_factors", ["No specific risk factors identified"])
        if not isinstance(risk_factors, list):
            risk_factors = [str(risk_factors)]
            
        explanation = response_dict.get("explanation", "No detailed explanation provided")
        if not isinstance(explanation, str):
            explanation = str(explanation)
        
        # Return the formatted response
        return RiskScoringResponse(
            risk_score=risk_score,
            risk_factors=risk_factors,
            explanation=explanation
        )
    except Exception as e:
        import traceback
        print(f"Error in risk scoring: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing risk analysis: {str(e)}")

@router.post("/account-risk-analysis", response_model=TweetRiskResponse)
async def analyze_account_tweets(request: TweetRiskRequest):
    """Analyze risk score for all tweets from a specific account."""
    try:
        # Connect to database and get tweets for the account
        conn = get_connection()
        cursor = conn.cursor()
        
        # Fetch tweets data for the account
        cursor.execute(
            """
            SELECT data_json 
            FROM post_data 
            WHERE user_id = %s AND username = %s 
            ORDER BY created_at DESC 
            LIMIT 1
            """,
            (request.user_id, request.username)
        )
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"No tweets found for account {request.user_id}")
        
        tweets_data = json.loads(result[0])
        
        # Initialize response data
        runner = Runner()
        analyzed_tweets = []
        total_risk_score = 0
        
        # Process only up to 10 tweets for performance reasons
        max_tweets = min(10, len(tweets_data.get("tweets", [])))
        
        for i, tweet in enumerate(tweets_data.get("tweets", [])[:max_tweets]):
            # Skip empty tweets
            if not tweet.get("text"):
                continue
                
            # Analyze the tweet text
            input_text = tweet.get("text", "")
            
            # Get the risk score for this tweet
            result = await runner.run(risk_scoring_agent, input_text)
            
            # Extract the response
            if hasattr(result, "final_output") and result.final_output:
                result_text = result.final_output
            else:
                result_text = str(result)
            
            # Parse the JSON response
            json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', result_text)
            if not json_match:
                json_match = re.search(r'{[\s\S]*?"risk_score"[\s\S]*?}', result_text)
                
            if json_match:
                try:
                    response_dict = json.loads(json_match.group(1) if '```json' in result_text else json_match.group(0))
                except json.JSONDecodeError:
                    json_str = json_match.group(1) if '```json' in result_text else json_match.group(0)
                    json_str = re.sub(r'[\n\r\t]', '', json_str)
                    try:
                        response_dict = json.loads(json_str)
                    except:
                        response_dict = {
                            "risk_score": 30, 
                            "risk_factors": ["Error analyzing tweet"],
                            "explanation": "Could not properly analyze this tweet content"
                        }
            else:
                response_dict = {
                    "risk_score": 30,
                    "risk_factors": ["Analysis failed"],
                    "explanation": "Failed to analyze this tweet content"
                }
            
            # Extract and format the risk data
            risk_score = response_dict.get("risk_score", 30)
            if not isinstance(risk_score, int):
                try:
                    risk_score = int(float(risk_score))
                except:
                    risk_score = 30
                    
            risk_factors = response_dict.get("risk_factors", ["No specific risk factors identified"])
            if not isinstance(risk_factors, list):
                risk_factors = [str(risk_factors)]
                
            explanation = response_dict.get("explanation", "No detailed explanation provided")
            if not isinstance(explanation, str):
                explanation = str(explanation)
            
            # Add to the results
            analyzed_tweets.append(TweetRiskItem(
                tweet_id=tweet.get("tweet_id", "unknown"),
                text=tweet.get("text", ""),
                risk_score=risk_score,
                risk_factors=risk_factors,
                explanation=explanation
            ))
            
            total_risk_score += risk_score
            
            # Update risk score in the original tweets data
            for t in tweets_data["tweets"]:
                if t.get("tweet_id") == tweet.get("tweet_id"):
                    t["risk_score"] = risk_score
        
        # Calculate average risk score
        average_risk = total_risk_score / len(analyzed_tweets) if analyzed_tweets else 0
        tweets_data["average_risk_score"] = round(average_risk, 2)
        
        # Update the database with the new data that includes risk scores
        cursor.execute(
            """
            UPDATE post_data 
            SET data_json = %s 
            WHERE user_id = %s AND username = %s
            """,
            (json.dumps(tweets_data), request.user_id, request.username)
        )
        conn.commit()
        
        return TweetRiskResponse(
            username=request.username,
            account_id=request.user_id,
            total_analyzed=len(analyzed_tweets),
            tweets=analyzed_tweets,
            average_risk_score=round(average_risk, 2)
        )
    
    except Exception as e:
        import traceback
        print(f"Error analyzing account tweets: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error analyzing account tweets: {str(e)}")

@router.post("/account-risk-analysis-comments", response_model=TweetRiskResponse)
async def analyze_account_tweets_with_comments(request: TweetRiskRequest):
    """Analyze risk score for tweets and their comments."""
    try:
        # Connect to database
        conn = get_connection()
        cursor = conn.cursor()
        
        # Fetch comments data
        cursor.execute(
            """
            SELECT content 
            FROM comments 
            WHERE user_id = %s AND account_username = %s 
            ORDER BY created_at DESC 
            LIMIT 1
            """,
            (request.user_id, request.username)
        )
        result = cursor.fetchone()
        
        # Handle missing data more gracefully
        if not result:
            print(f"No comments found for account {request.user_id}")
            return TweetRiskResponse(
                username=request.username,
                account_id=request.user_id,
                total_analyzed=0,
                tweets=[],
                average_risk_score=0.0
            )
        
        # Parse comments data - handle potential JSON errors
        try:
            comments_data = json.loads(result[0])
        except json.JSONDecodeError:
            print(f"Invalid JSON data for account {request.user_id}")
            return TweetRiskResponse(
                username=request.username,
                account_id=request.user_id,
                total_analyzed=0,
                tweets=[],
                average_risk_score=0.0
            )
        
        # Check if we have valid data structure
        if not comments_data or not isinstance(comments_data, list):
            print(f"Invalid comments data format for account {request.user_id}")
            return TweetRiskResponse(
                username=request.username,
                account_id=request.user_id,
                total_analyzed=0,
                tweets=[],
                average_risk_score=0.0
            )
        
        # Initialize response data
        runner = Runner()
        analyzed_tweets = []
        total_risk_score = 0
        total_items_analyzed = 0
        
        # Process tweets with comments
        for tweet_with_comments in comments_data:
            tweet_id = tweet_with_comments.get("tweet_id", "unknown")
            tweet_text = tweet_with_comments.get("tweet_text", "")
            replies = tweet_with_comments.get("replies", [])
            
            if not tweet_text:
                continue
                
            # Analyze tweet text
            try:
                tweet_result = await runner.run(risk_scoring_agent, tweet_text)
                tweet_analysis = await parse_risk_analysis(tweet_result)
            except Exception as e:
                print(f"Error analyzing tweet {tweet_id}: {str(e)}")
                tweet_analysis = {
                    "risk_score": 30,
                    "risk_factors": ["Analysis error"],
                    "explanation": f"Error during analysis: {str(e)[:100]}"
                }
            
            # Analyze each comment
            analyzed_comments = []
            for reply in replies:
                comment_text = reply.get("text", "")
                if not comment_text:
                    continue
                    
                try:
                    comment_result = await runner.run(risk_scoring_agent, comment_text)
                    comment_analysis = await parse_risk_analysis(comment_result)
                except Exception as e:
                    print(f"Error analyzing comment in tweet {tweet_id}: {str(e)}")
                    comment_analysis = {
                        "risk_score": 30,
                        "risk_factors": ["Analysis error"],
                        "explanation": f"Error during analysis: {str(e)[:100]}"
                    }
                
                analyzed_comments.append(CommentRiskItem(
                    comment_id=reply.get("id", "unknown"),
                    username=reply.get("username", "unknown"),
                    text=comment_text,
                    risk_score=comment_analysis["risk_score"],
                    risk_factors=comment_analysis["risk_factors"],
                    explanation=comment_analysis["explanation"]
                ))
                
                total_risk_score += comment_analysis["risk_score"]
                total_items_analyzed += 1
            
            # Add tweet risk score to total
            total_risk_score += tweet_analysis["risk_score"]
            total_items_analyzed += 1
            
            # Add to the results
            analyzed_tweets.append(TweetWithCommentsRiskItem(
                tweet_id=tweet_id,
                tweet_text=tweet_text,
                tweet_risk_score=tweet_analysis["risk_score"],
                tweet_risk_factors=tweet_analysis["risk_factors"],
                tweet_explanation=tweet_analysis["explanation"],
                comments=analyzed_comments
            ))
            
            # Update risk scores in the original data
            tweet_with_comments["risk_score"] = tweet_analysis["risk_score"]
            tweet_with_comments["risk_factors"] = tweet_analysis["risk_factors"]
            tweet_with_comments["explanation"] = tweet_analysis["explanation"]
            
            # Create a map of comment IDs to their analysis for easier lookup
            comment_analysis_map = {
                analyzed_comment.comment_id: {
                    "risk_score": analyzed_comment.risk_score,
                    "risk_factors": analyzed_comment.risk_factors,
                    "explanation": analyzed_comment.explanation
                }
                for analyzed_comment in analyzed_comments
            }
            
            # Update each reply with its risk analysis
            for reply in replies:
                comment_id = reply.get("id", "unknown")
                if comment_id in comment_analysis_map:
                    analysis = comment_analysis_map[comment_id]
                    reply.update({
                        "risk_score": analysis["risk_score"],
                        "risk_factors": analysis["risk_factors"],
                        "explanation": analysis["explanation"]
                    })
                else:
                    # If no analysis was performed, add default values
                    reply.update({
                        "risk_score": 30,
                        "risk_factors": ["No analysis performed"],
                        "explanation": "This comment was not analyzed"
                    })
        
        # Calculate average risk score
        average_risk = total_risk_score / total_items_analyzed if total_items_analyzed > 0 else 0
        
        # Update the database with the new data including risk scores
        try:
            # First, check if the record exists
            cursor.execute(
                """
                SELECT content 
                FROM comments 
                WHERE user_id = %s AND account_username = %s
                """,
                (request.user_id, request.username)
            )
            existing_record = cursor.fetchone()
            
            if existing_record:
                # Update existing record
                cursor.execute(
                    """
                    UPDATE comments 
                    SET content = %s
                    WHERE user_id = %s AND account_username = %s
                    """,
                    (json.dumps(comments_data), request.user_id, request.username)
                )
            
            conn.commit()
            print(f"Successfully updated risk scores in database for user {request.user_id}")
            print(f"Updated data structure: {json.dumps(comments_data, indent=2)}")
        except Exception as e:
            print(f"Error updating database: {str(e)}")
            # Continue without failing if DB update fails
        
        return TweetRiskResponse(
            username=request.username,
            account_id=request.user_id,
            total_analyzed=total_items_analyzed,
            tweets=analyzed_tweets,
            average_risk_score=round(average_risk, 2)
        )
    
    except Exception as e:
        import traceback
        print(f"Error analyzing tweets with comments: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error analyzing tweets with comments: {str(e)}")

async def parse_risk_analysis(result) -> Dict:
    """Helper function to parse risk analysis results."""
    if hasattr(result, "final_output") and result.final_output:
        result_text = result.final_output
    else:
        result_text = str(result)
    
    # Parse the JSON response
    json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', result_text)
    if not json_match:
        json_match = re.search(r'{[\s\S]*?"risk_score"[\s\S]*?}', result_text)
        
    if json_match:
        try:
            response_dict = json.loads(json_match.group(1) if '```json' in result_text else json_match.group(0))
        except json.JSONDecodeError:
            json_str = json_match.group(1) if '```json' in result_text else json_match.group(0)
            json_str = re.sub(r'[\n\r\t]', '', json_str)
            try:
                response_dict = json.loads(json_str)
            except:
                response_dict = {
                    "risk_score": 30, 
                    "risk_factors": ["Error analyzing content"],
                    "explanation": "Could not properly analyze this content"
                }
    else:
        response_dict = {
            "risk_score": 30,
            "risk_factors": ["Analysis failed"],
            "explanation": "Failed to analyze this content"
        }
    
    # Extract and format the risk data
    risk_score = response_dict.get("risk_score", 30)
    if not isinstance(risk_score, int):
        try:
            risk_score = int(float(risk_score))
        except:
            risk_score = 30
            
    risk_factors = response_dict.get("risk_factors", ["No specific risk factors identified"])
    if not isinstance(risk_factors, list):
        risk_factors = [str(risk_factors)]
        
    explanation = response_dict.get("explanation", "No detailed explanation provided")
    if not isinstance(explanation, str):
        explanation = str(explanation)
    
    return {
        "risk_score": risk_score,
        "risk_factors": risk_factors,
        "explanation": explanation
    }
