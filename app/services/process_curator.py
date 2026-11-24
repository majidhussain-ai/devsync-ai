"""
DevSync AI - Curation Service
Utility script to fetch recent digests and rank them against a specific user profile
using the AI CuratorAgent.
"""
import logging
from typing import Dict, Any

from app.env import load_env
load_env()

from app.agent.curator_agent import CuratorAgent
from app.profiles.user_profile import USER_PROFILE
from app.database.repository import Repository

logger = logging.getLogger(__name__)


def curate_digests(hours: int = 24) -> Dict[str, Any]:
    """
    Fetches recent digests and ranks them according to the user profile.
    """
    curator = CuratorAgent(USER_PROFILE)
    repo = None
    
    try:
        repo = Repository()
        
        digests = repo.get_recent_digests(hours=hours)
        total = len(digests)
        
        if total == 0:
            logger.warning(f"No digests found from the last {hours} hours.")
            return {"total": 0, "ranked": 0, "articles": []}
        
        logger.info(f"Curating {total} digests from the last {hours} hours...")
        logger.info(f"User profile: {USER_PROFILE.get('name', 'User')} - {USER_PROFILE.get('background', 'Unknown')}")
        
        # Single bulk call to the LLM agent for ranking
        ranked_articles = curator.rank_digests(digests)
        
        if not ranked_articles:
            logger.error("Failed to rank digests (Agent returned None or empty list).")
            return {"total": total, "ranked": 0, "articles": []}
        
        logger.info(f"Successfully ranked {len(ranked_articles)} articles.")
        logger.info("\n=== Top 10 Ranked Articles ===")
        
        for article in ranked_articles[:10]:
            digest = next((d for d in digests if d["id"] == getattr(article, "digest_id", None)), None)
            if digest:
                rank = getattr(article, "rank", "N/A")
                score = getattr(article, "relevance_score", 0.0)
                reasoning = getattr(article, "reasoning", "No reasoning provided.")
                
                logger.info(f"\nRank {rank} | Score: {score:.1f}/10.0")
                logger.info(f"Title: {digest.get('title', 'Unknown')}")
                logger.info(f"Type: {digest.get('article_type', 'Unknown')}")
                logger.info(f"Reasoning: {reasoning}")
        
        return {
            "total": total,
            "ranked": len(ranked_articles),
            "articles": [
                {
                    "digest_id": getattr(a, "digest_id", None),
                    "rank": getattr(a, "rank", None),
                    "relevance_score": getattr(a, "relevance_score", None),
                    "reasoning": getattr(a, "reasoning", None)
                }
                for a in ranked_articles
            ]
        }
        
    except Exception as e:
        logger.error(f"Curation process failed: {type(e).__name__} - {e}")
        return {"total": 0, "ranked": 0, "articles": [], "error": str(e)}
        
    finally:
        if repo is not None:
            repo.session.close()


if __name__ == "__main__":
    # Setup CLI logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    result = curate_digests(hours=24)
    
    print("\n=== Curation Results ===")
    print(f"Total digests: {result.get('total', 0)}")
    print(f"Ranked: {result.get('ranked', 0)}")