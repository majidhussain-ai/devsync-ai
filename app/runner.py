"""
DevSync AI - Scraper Runner
Orchestrates the data extraction pipeline across multiple sources (YouTube, OpenAI, Anthropic)
and handles bulk database ingestion.
"""
import logging
from typing import List, Dict, Any

from app.config import YOUTUBE_CHANNELS
from app.scrapers.youtube import YouTubeScraper
from app.scrapers.openai import OpenAIScraper
from app.scrapers.anthropic import AnthropicScraper
from app.database.repository import Repository

logger = logging.getLogger(__name__)


def run_scrapers(hours: int = 24) -> Dict[str, Any]:
    """
    Executes all scrapers to fetch the latest AI news and saves them to the database.
    
    Args:
        hours (int): The time window to look back for new content. Default is 24 hours.
        
    Returns:
        Dict[str, Any]: A dictionary containing lists of scraped Pydantic objects.
    """
    youtube_scraper = YouTubeScraper()
    openai_scraper = OpenAIScraper()
    anthropic_scraper = AnthropicScraper()
    repo = None

    try:
        repo = Repository()

        youtube_videos = []
        video_dicts = []

        # 1. YouTube Scraping - Propagates failure instead of swallowing it
        try:
            for channel_id in YOUTUBE_CHANNELS:
                videos = youtube_scraper.get_latest_videos(channel_id, hours=hours)[:1]
                youtube_videos.extend(videos)
                
                for v in videos:
                    v_dict = v.model_dump()
                    v_dict["channel_id"] = channel_id
                    video_dicts.append(v_dict)
        except Exception:
            logger.exception("YouTube Scraping failed")
            raise

        # 2. OpenAI Scraping - Propagates failure instead of swallowing it
        try:
            openai_articles = openai_scraper.get_articles(hours=hours)[:2]
        except Exception:
            logger.exception("OpenAI Scraping failed")
            raise

        # 3. Anthropic Scraping - Propagates failure instead of swallowing it
        try:
            anthropic_articles = anthropic_scraper.get_articles(hours=hours)[:1]
        except Exception:
            logger.exception("Anthropic Scraping failed")
            raise

        # 4. Database Bulk Ingestion
        if video_dicts:
            repo.bulk_create_youtube_videos(video_dicts)

        if openai_articles:
            repo.bulk_create_openai_articles([a.model_dump() for a in openai_articles])

        if anthropic_articles:
            repo.bulk_create_anthropic_articles([a.model_dump() for a in anthropic_articles])

        return {
            "youtube": youtube_videos,
            "openai": openai_articles,
            "anthropic": anthropic_articles,
        }
    finally:
        if repo is not None:
            repo.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger.info("Starting DevSync AI Scraper Pipeline...")
    
    results = run_scrapers(hours=24)
    
    logger.info(f"Pipeline Completed. YouTube: {len(results['youtube'])} | "
                f"OpenAI: {len(results['openai'])} | "
                f"Anthropic: {len(results['anthropic'])}")