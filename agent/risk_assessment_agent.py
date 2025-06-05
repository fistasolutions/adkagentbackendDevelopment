from typing import List, Optional
from pydantic import BaseModel
from agents import Agent, Runner

class RiskCategory(BaseModel):
    category: str
    risk_level: int  # 1-100
    reason: str

class RiskAssessmentResponse(BaseModel):
    overall_risk_score: int  # 1-100
    risk_categories: List[RiskCategory]
    risk_assignment: str

class RiskAssessmentRequest(BaseModel):
    content: str

class RiskAssessmentAgent:
    def __init__(self):
        """
        Initialize the Risk Assessment Agent for analyzing content and assigning risk scores.
        """
        self.agent = Agent(
            name="Risk Assessment Agent",
            instructions=self._get_instructions(),
            output_type=RiskAssessmentResponse
        )
    
    def _get_instructions(self) -> str:
        """Generate agent instructions"""
        return """You are a content risk assessment expert. Your task is to analyze content and assign risk scores based on predefined categories.

        Risk Categories and Scoring Guidelines:
        1. Political Content (1-100)
           - Strong criticism/support of politicians/parties
           - Biased opinions about policies
           - Discriminatory remarks about countries/ethnic groups
           - Content on sensitive historical issues

        2. Religious Content (1-100)
           - Denial/criticism of specific religions
           - Disrespectful expressions toward religious symbols
           - Statements inciting religious conflict

        3. Gender and Sexual Orientation (1-100)
           - Sexist language
           - Derogatory remarks toward LGBTQ+ identities
           - Extreme views on feminism/gender equality

        4. Race and Ethnicity (1-100)
           - Discriminatory expressions
           - Insensitive comments about racial issues
           - Xenophobic rhetoric

        5. Disasters and Incidents (1-100)
           - Mocking victims
           - Spreading conspiracy theories
           - Inappropriate criticism of emergency responses

        6. Privacy and Personal Information (1-100)
           - Leaking personal information
           - Posting private content without consent
           - Personal attacks/defamation

        7. Animal Welfare and Environment (1-100)
           - Content condoning animal abuse
           - Extreme environmental stances
           - Support of environmental destruction

        8. Medical and Health (1-100)
           - Medical misinformation
           - Unscientific health practices
           - Discriminatory comments about illnesses

        9. Labor and Economic Issues (1-100)
           - Justifying workplace harassment
           - Discriminatory language about industries
           - Insensitive remarks about poverty

        10. Copyright and IP (1-100)
            - Unauthorized use of copyrighted materials
            - Plagiarism
            - IP infringement

        Scoring Guidelines:
        - 1-20: Minimal risk, content is generally acceptable
        - 21-40: Low risk, minor concerns
        - 41-60: Moderate risk, requires review
        - 61-80: High risk, likely problematic
        - 81-100: Critical risk, content should be rejected

Generate and display an explanatory message about why the Agent classified it as high risk and suggestions for improvement.
Content matching the following category(ies) was detected in the text:
Political Content / Religious Content / Gender and Sexual Orientation / Race and Ethnicity / Disasters, Incidents, and Accidents / Privacy and Personal Information / Animal Welfare and Environmental Issues / Medical and Health Topics / Labor and Economic Issues / Copyright and Intellectual Property
       and also how to improve it in message
       
        You must return a JSON object with this exact structure:
        {
            "overall_risk_score": int,  # 1-100
            "risk_categories": [
                {
                    "category": "string",
                    "risk_level": int,  # 1-100
                    "reason": "string"
                }
            ],
            "risk_assignment": "message"  
        }"""
    
    async def get_response(self, request: RiskAssessmentRequest) -> RiskAssessmentResponse:
        """
        Analyze content and assign risk scores.
        
        Args:
            request (RiskAssessmentRequest): The request containing the content to analyze
            
        Returns:
            RiskAssessmentResponse: The risk assessment results
        """
        try:
            prompt = f"""Content to analyze: {request.content}
            
            Please analyze this content and provide a comprehensive risk assessment based on the predefined categories."""
            
            result = await Runner.run(
                self.agent,
                prompt
            )
            return result.final_output
        except Exception as e:
            raise Exception(f"Error performing risk assessment: {str(e)}")
    
    def add_handoff(self, other_agent: 'RiskAssessmentAgent') -> None:
        """Add a handoff to another agent"""
        self.agent.handoffs.append(other_agent.agent) 