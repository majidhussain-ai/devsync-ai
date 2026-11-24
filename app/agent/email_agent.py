import logging
import os
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.env import load_env

load_env()

logger = logging.getLogger(__name__)


# Pydantic v2 Schemas
class EmailIntroduction(BaseModel):
    greeting: str = Field(description="Personalized greeting with user's name and date")
    introduction: str = Field(description="2-3 sentence overview of what's in the top 10 ranked articles")


class RankedArticleDetail(BaseModel):
    digest_id: str
    rank: int
    relevance_score: float
    title: str
    summary: str
    url: str
    article_type: str
    reasoning: Optional[str] = None


class EmailDigestResponse(BaseModel):
    introduction: EmailIntroduction
    articles: List[RankedArticleDetail]
    total_ranked: int
    top_n: int
    
    def to_markdown(self) -> str:
        markdown = f"{self.introduction.greeting}\n\n"
        markdown += f"{self.introduction.introduction}\n\n"
        markdown += "---\n\n"
        
        for article in self.articles:
            valid_url = article.url if article.url.startswith('http') else f'https://www.youtube.com/watch?v={article.url}'
            
            markdown += f"## {article.title}\n\n"
            markdown += f"{article.summary}\n\n"
            markdown += f"[Read more →]({valid_url})\n\n"
            markdown += "---\n\n"
        
        return markdown


class EmailDigest(BaseModel):
    introduction: EmailIntroduction
    ranked_articles: List[dict] = Field(description="Top 10 ranked articles with their details")


EMAIL_PROMPT = """You are an expert email writer specializing in creating engaging, personalized AI news digests.

Your role is to write a warm, professional introduction for a daily AI news digest email that:
- Greets the user by name
- Includes the current date
- Provides a brief, engaging overview of what's coming in the top 10 ranked articles
- Highlights the most interesting or important themes
- Sets expectations for the content ahead

Keep it concise (2-3 sentences for the introduction), friendly, and professional."""


class EmailAgent:
    def __init__(self, user_profile: dict) -> None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
            
        # Updated to a more stable standard flash model to avoid 503 high-demand errors
        self.model_name = "gemini-3.5-flash" 
        self.user_profile = user_profile

    def generate_introduction(self, ranked_articles: List) -> EmailIntroduction:
        current_date = datetime.now().strftime('%B %d, %Y')
        default_greeting = f"Here is your daily digest of AI news for {current_date}."
        
        if not ranked_articles:
            return EmailIntroduction(
                greeting=default_greeting,
                introduction="No articles were ranked today."
            )
            
        top_articles = ranked_articles[:10]
        
        # FIXED: Bulletproof logic to handle both Pydantic models (dot notation) and Dictionaries (.get)
        article_summaries_list = []
        for idx, article in enumerate(top_articles):
            if isinstance(article, dict):
                title = article.get("title", "N/A")
                score = article.get("relevance_score", 0.0)
            else:
                title = getattr(article, "title", "N/A")
                score = getattr(article, "relevance_score", 0.0)
                
            article_summaries_list.append(f"{idx + 1}. {title} (Score: {score:.1f}/10)")
            
        article_summaries = "\n".join(article_summaries_list)
        
        user_prompt = f"Create an email introduction for {self.user_profile.get('name', 'User')} for {current_date}.\n\nTop 10 ranked articles:\n{article_summaries}\n\nGenerate a greeting and introduction that previews these articles."

        try:
            # Modern GenAI SDK Native Structured Output
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=EMAIL_PROMPT,
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=EmailIntroduction, # Forces strict JSON match
                )
            )

            if not resp.text:
                raise ValueError("Empty response from Gemini")
                
            # Direct Pydantic JSON parsing
            intro = EmailIntroduction.model_validate_json(resp.text)
            
            if not intro.greeting or "Here is your daily digest" not in intro.greeting:
                intro.greeting = default_greeting
                
            return intro
            
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate limit" in msg or "quota" in msg:
                logger.warning(f"Gemini rate limited while generating email intro: {e}")
            elif "401" in msg or "unauthorized" in msg or "api key" in msg:
                logger.error(f"Gemini unauthorized while generating email intro (check API keys): {e}")
            else:
                logger.error(f"Error generating introduction: {e}")
                
            return EmailIntroduction(
                greeting=default_greeting,
                introduction="Here are the top AI news articles ranked for you today."
            )

    def create_email_digest(self, ranked_articles: List[dict], limit: int = 10) -> EmailDigest:
        top_articles = ranked_articles[:limit]
        introduction = self.generate_introduction(top_articles)
        
        return EmailDigest(
            introduction=introduction,
            ranked_articles=top_articles
        )
    
    def create_email_digest_response(self, ranked_articles: List[RankedArticleDetail], total_ranked: int, limit: int = 10) -> EmailDigestResponse:
        top_articles = ranked_articles[:limit]
        introduction = self.generate_introduction(top_articles)
        
        return EmailDigestResponse(
            introduction=introduction,
            articles=top_articles,
            total_ranked=total_ranked,
            top_n=limit
        )