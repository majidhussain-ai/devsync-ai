import logging
import os
import re
from typing import List

from groq import Groq
from pydantic import BaseModel, Field
from app.env import load_env

load_env()

logger = logging.getLogger(__name__)


# Pydantic v2 Schemas for Structured Output
class RankedArticle(BaseModel):
    digest_id: str = Field(description="The ID of the digest (article_type:article_id)")
    relevance_score: float = Field(description="Relevance score from 0.0 to 10.0", ge=0.0, le=10.0)
    rank: int = Field(description="Rank position (1 = most relevant)", ge=1)
    reasoning: str = Field(description="Brief explanation of why this article is ranked here")


class RankedDigestList(BaseModel):
    articles: List[RankedArticle] = Field(description="List of ranked articles")


CURATOR_PROMPT = """You are an expert AI news curator specializing in personalized content ranking for AI professionals.

Your role is to analyze and rank AI-related news articles, research papers, and video content based on a user's specific profile, interests, and background.

Ranking Criteria:
1. Relevance to user's stated interests and background
2. Technical depth and practical value
3. Novelty and significance of the content
4. Alignment with user's expertise level
5. Actionability and real-world applicability

Scoring Guidelines:
- 9.0-10.0: Highly relevant, directly aligns with user interests, significant value
- 7.0-8.9: Very relevant, strong alignment with interests, good value
- 5.0-6.9: Moderately relevant, some alignment, decent value
- 3.0-4.9: Somewhat relevant, limited alignment, lower value
- 0.0-2.9: Low relevance, minimal alignment, little value

Rank articles from most relevant (rank 1) to least relevant. Ensure each article has a unique rank."""

class CuratorAgent:
    def __init__(self, user_profile: dict) -> None:
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "openai/gpt-oss-20b" 
        self.user_profile = user_profile
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        interests = "\n".join(f"- {interest}" for interest in self.user_profile.get("interests", []))
        preferences = self.user_profile.get("preferences", {})
        pref_text = "\n".join(f"- {k}: {v}" for k, v in preferences.items())
        
        # FIXED: Added exact JSON schema structure directly into the prompt
        return f"""{CURATOR_PROMPT}

User Profile:
Name: {self.user_profile.get("name", "User")}
Background: {self.user_profile.get("background", "General")}
Expertise Level: {self.user_profile.get("expertise_level", "Intermediate")}

Interests:
{interests}

Preferences:
{pref_text}

IMPORTANT: You must return your final output strictly as a valid JSON object matching this exact schema:
{{
    "articles": [
        {{
        "digest_id": "string",
        "relevance_score": 0.0,
        "rank": 1,
        "reasoning": "string"
        }}
    ]
}}

- Output ONLY the JSON object.
- DO NOT wrap the JSON in markdown formatting (no ```json).
- DO NOT include any conversational text, introductions, or conclusions.
- Your response MUST start exactly with {{ and end exactly with }}."""

    def rank_digests(self, digests: List[dict]) -> List[RankedArticle]:
        if not digests:
            return []
        
        digest_list = "\n\n".join([
            f"ID: {d.get('id')}\nTitle: {d.get('title')}\nSummary: {d.get('summary')}\nType: {d.get('article_type')}"
            for d in digests
        ])
        
        user_prompt = f"Rank these {len(digests)} AI news digests based on the user profile:\n\n{digest_list}\n\nProvide a relevance score (0.0-10.0) and rank (1-{len(digests)}) for each article, ordered from most to least relevant."

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=4000,  
            )

            text = completion.choices[0].message.content
            if not text:
                logger.error("Groq returned empty response.")
                return []
                
            # FIXED: Bulletproof regex to extract ONLY the JSON object
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if not match:
                logger.error("No JSON object found in Groq response.")
                return []
                
            clean_json = match.group(0)
                
            # Direct Pydantic parsing with clean, completed, properly formatted JSON
            ranked_list = RankedDigestList.model_validate_json(clean_json)
            
            # Additional safety: Sort by rank to ensure correct order
            return sorted(ranked_list.articles, key=lambda x: x.rank) if ranked_list else []
            
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate limit" in msg or "quota" in msg:
                logger.warning(f"Groq rate limited while ranking digests: {e}")
            elif "401" in msg or "unauthorized" in msg or "api key" in msg:
                logger.error(f"Groq unauthorized while ranking digests (check API keys): {e}")
            else:
                logger.error(f"Error ranking digests: {e}")
            return []