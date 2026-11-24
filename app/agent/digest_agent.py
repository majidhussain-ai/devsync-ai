import logging
import os
import json
from typing import Optional, List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from groq import Groq
from app.env import load_env

load_env()

logger = logging.getLogger(__name__)

# Single Digest Schema
class DigestOutput(BaseModel):
    title: str
    summary: str

# Ranked Article Detail Schema for Chunking
class RankedArticleDetail(BaseModel):
    digest_id: str
    rank: int = Field(ge=1, le=10, description="Score from 1 to 10")
    relevance_score: float
    title: str
    summary: str
    url: str
    article_type: str
    reasoning: Optional[str] = None

# List wrapper for Chunking Response
class RankedDigestList(BaseModel):
    articles: List[RankedArticleDetail]

PROMPT = """You are an expert AI news analyst specializing in summarizing technical articles, research papers, and video content about artificial intelligence.

Your role is to create concise, informative digests that help readers quickly understand the key points and significance of AI-related content.

Guidelines:
- Create a compelling title (5-10 words) that captures the essence of the content
- Write a 2-3 sentence summary that highlights the main points and why they matter
- Focus on actionable insights and implications
- Use clear, accessible language while maintaining technical accuracy
- Avoid marketing fluff - focus on substance

IMPORTANT: Output STRICTLY in valid JSON matching this schema: {"title": "string", "summary": "string"}"""

RANKING_PROMPT = """You are a Principal AI Engineer evaluating recent tech news.
Your task is to rank the provided AI articles based on their technical importance, industry impact, and relevance to developers.

Assign a 'rank' (1 = highest priority/impact, 10 = lowest) and a 'relevance_score' (out of 10.0) to each article.

IMPORTANT: You MUST return a STRICT JSON object with a single key "articles" containing a list of the ranked items.
"""


class DigestAgent:
    def __init__(self) -> None:
        # Initialize Clients
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.gemini_client = genai.Client(api_key=gemini_key) if gemini_key else genai.Client()
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # MULTI-MODEL ROUTING QUEUES (Fastest/Best -> Fallbacks)
        self.gemini_routing = [
            "gemini-3.8-flash",   # Primary: Best quality, but might hit 503
            "gemini-3.5-flash",   # Fallback 1: Very capable
            "gemini-2.5-flash"    # Fallback 2: Older but highly available
        ]
        
        self.groq_routing = [
            "qwen/qwen3.8-27b",   # Primary Groq: Fast, good at JSON
            "openai/gpt-oss-120b",# Fallback 1: Heavy reasoning
            "openai/gpt-oss-20b"  # Fallback 2: Lightweight safety net
        ]
        
        self.system_prompt = PROMPT

    def generate_digest(self, title: str, content: str, article_type: str) -> Optional[DigestOutput]:
        user_prompt = f"Create a digest for this {article_type}:\nTitle: {title}\nContent: {content[:8000]}"
        
        try:
            return self._call_gemini(user_prompt)
        except Exception as e_gemini:
            msg = str(e_gemini).lower()
            if "429" in msg or "rate limit" in msg or "quota" in msg:
                logger.warning(f"Gemini Rate Limited (429). Switching to Groq Fallback... Error: {type(e_gemini).__name__}")
            else:
                logger.warning(f"Gemini failed ({type(e_gemini).__name__}). Switching to Groq Fallback... Error: {e_gemini}")
            
            try:
                return self._call_groq(user_prompt)
            except Exception as e_groq:
                logger.error(f"Both LLMs failed. Gemini: {type(e_gemini).__name__} | Groq: {e_groq}")
                return None

    def _call_gemini(self, user_prompt: str) -> DigestOutput:
        last_error = None
        
        # Loop through the list of Gemini models defined in __init__
        for model_name in self.gemini_routing:
            try:
                resp = self.gemini_client.models.generate_content(
                    model=model_name, # Pass single string, not list
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.7,
                        response_mime_type="application/json",
                        response_schema=DigestOutput,
                    )
                )

                if resp.text and resp.text.strip() != "":
                    return DigestOutput.model_validate_json(resp.text)
                    
            except Exception as e:
                logger.warning(f"Gemini {model_name} failed: {type(e).__name__}. Routing to next...")
                last_error = e
                continue
                
        raise ValueError(f"All Gemini models exhausted. Last error: {last_error}")

    def _call_groq(self, user_prompt: str) -> DigestOutput:
        last_error = None
        
        for model_name in self.groq_routing:
            try:
                resp = self.groq_client.chat.completions.create(
                    model=model_name, # Pylance fix: single string from list
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4096, 
                    response_format={"type": "json_object"}
                )
                
                content = resp.choices[0].message.content
                if content and content.strip() != "":
                    content = content.replace("```json", "").replace("```", "").strip()
                    return DigestOutput.model_validate_json(content)
                    
            except Exception as e:
                logger.warning(f"Groq {model_name} failed: {type(e).__name__}. Routing to next...")
                last_error = e
                continue
                
        raise ValueError(f"All Groq models exhausted. Last error: {last_error}")

    def rank_digests(self, digests: List[dict]) -> List[RankedArticleDetail]:
        if not digests:
            return []
            
        logger.info(f"Ranking {len(digests)} digests using Chunking Strategy...")
        
        chunk_size = 2 
        all_ranked_articles = []
        
        for i in range(0, len(digests), chunk_size):
            chunk = digests[i:i + chunk_size]
            
            prompt_content = "Rank the following articles:\n\n"
            for digest in chunk:
                prompt_content += f"ID: {digest['id']}\nTitle: {digest['title']}\nSummary: {digest['summary']}\nType: {digest['article_type']}\n\n"
            
            chunk_success = False
            # Loop through Groq models for this specific chunk
            for model_name in self.groq_routing:
                try:
                    resp = self.groq_client.chat.completions.create(
                        model=model_name, # Passed single string model
                        messages=[
                            {"role": "system", "content": RANKING_PROMPT},
                            {"role": "user", "content": prompt_content}
                        ],
                        temperature=0.3,
                        max_tokens=2048, 
                        response_format={"type": "json_object"} 
                    )
                    
                    content = resp.choices[0].message.content
                    if not content or content.strip() == "":
                        raise ValueError(f"Empty response from {model_name}")
                        
                    content = content.replace("```json", "").replace("```", "").strip()
                    parsed_chunk = RankedDigestList.model_validate_json(content)
                    
                    for ranked_item in parsed_chunk.articles:
                        original = next((d for d in chunk if d['id'] == ranked_item.digest_id), None)
                        if original:
                            ranked_item.url = original.get('url', '')
                            # Add missing mapping fields from previous optimization step
                            ranked_item.title = original.get('title', '')
                            ranked_item.summary = original.get('summary', '')
                            ranked_item.article_type = original.get('article_type', '')
                            
                    all_ranked_articles.extend(parsed_chunk.articles)
                    chunk_success = True
                    break # Success! Break out of the fallback loop and move to next chunk
                    
                except Exception as e:
                    logger.warning(f"Groq {model_name} chunk ranking failed. Trying next model...")
                    continue
            
            if not chunk_success:
                logger.error(f"Failed to rank chunk starting at index {i} across ALL models.")
                # Continue to next chunk even if this one totally failed (graceful degradation)
                
        sorted_articles = sorted(all_ranked_articles, key=lambda x: x.relevance_score, reverse=True)
        
        for index, item in enumerate(sorted_articles):
            item.rank = index + 1
            
        return sorted_articles