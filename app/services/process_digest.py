import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from app.agent.digest_agent import DigestAgent
from app.database.repository import Repository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


async def _generate_single_digest(
    article: Dict[str, Any], 
    agent: DigestAgent, 
    sem: asyncio.Semaphore
) -> dict:
    """Helper async function to process a single article with API limits."""
    article_type = article["type"]
    article_id = article["id"]
    article_title = article["title"][:60] + "..." if len(article["title"]) > 60 else article["title"]
    
    async with sem:
        logger.info(f"Processing {article_type}: {article_title}")
        max_retries = 3
        
        for attempt in range(1, max_retries + 1):
            try:
                # asyncio.to_thread runs the synchronous LLM call without blocking the event loop
                digest_result = await asyncio.to_thread(
                    agent.generate_digest,
                    title=article["title"],
                    content=article["content"],
                    article_type=article_type
                )
                
                if digest_result:
                    return {"success": True, "article": article, "result": digest_result}
                    
            except Exception as e:
                error_message = str(e)
                if "429" in error_message and attempt < max_retries:
                    logger.warning(f"Rate limited (429) for {article_id}. Retry {attempt}/{max_retries} in 60s...")
                    await asyncio.sleep(60)  # Non-blocking sleep
                    continue
                
                concise_error = f"{type(e).__name__}: {error_message}"[:200]
                logger.error(f"✗ Failed {article_id} after {attempt} attempts: {concise_error}")
                return {"success": False, "article": article, "error": concise_error}
                
        return {"success": False, "article": article, "error": "Digest generation failed after retries"}


async def process_digests(hours: int = 24, limit: Optional[int] = None) -> dict:
    agent = DigestAgent()
    repo = None
    try:
        # Initialize Repo locally
        repo = await asyncio.to_thread(Repository)
        
        # FIXED: Calculate time cutoff and pass 'since' to repository to prevent database backlogs
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        articles = await asyncio.to_thread(repo.get_articles_without_digest, limit=limit, since=since)
        total = len(articles)
        processed = 0
        failed = 0
        failed_items = {}
        
        if total == 0:
            logger.info("No new articles to process for digests.")
            return {"total": 0, "processed": 0, "failed": 0, "failed_items": {}}

        logger.info(f"Starting async digest processing for {total} articles")
        
        # Concurrency controller: Max 5 LLM API requests at exactly the same time
        sem = asyncio.Semaphore(5)
        
        # 1. Dispatch all API calls concurrently
        tasks = [
            _generate_single_digest(article, agent, sem)
            for article in articles
        ]
        
        # Wait for all LLM calls to complete
        results = await asyncio.gather(*tasks)
        
        # 2. Database Insertion (Sequential to prevent SQLAlchemy Session crashes)
        for res in results:
            article = res["article"]
            article_id = article["id"]
            
            if not res["success"]:
                failed += 1
                failed_items[article_id] = res["error"]
                continue
                
            digest_result = res["result"]
            
            # DB insertions take mere milliseconds
            created = await asyncio.to_thread(
                repo.create_digest,
                article_type=article["type"],
                article_id=article_id,
                url=article["url"],
                title=digest_result.title,
                summary=digest_result.summary,
                published_at=article.get("published_at"),
                image_url=article.get("image_url")  # Kept your critical fix for thumbnails
            )
            
            if created:
                processed += 1
                logger.info(f"✓ Created digest for {article_id}")
            else:
                failed += 1
                failed_items[article_id] = "Persistence failed/Duplicate"
                logger.warning(f"✗ Persistence failed for {article_id}")

        return {"total": total, "processed": processed, "failed": failed, "failed_items": failed_items}
    finally:
        if repo is not None:
            await asyncio.to_thread(repo.session.close)