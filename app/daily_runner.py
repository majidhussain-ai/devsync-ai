"""
DevSync AI - Daily Orchestrator
Executes the end-to-end data pipeline asynchronously.
"""
import asyncio
import logging
from datetime import datetime

from app.env import load_env
load_env()

# Imports for pipeline steps
from app.runner import run_scrapers
from app.services.process_anthropic import process_anthropic_markdown
from app.services.process_openai import process_openai_markdown # FIXED: Imported missing OpenAI processing
from app.services.process_youtube import process_youtube_transcripts
from app.services.process_digest import process_digests
from app.services.process_email import send_digest_email

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


async def run_daily_pipeline(hours: int = 24, top_n: int = 10) -> dict:
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("DevSync-AI | Autonomous Personalized Intelligence Pipeline")
    logger.info("=" * 60)
    results = {
        "start_time": start_time.isoformat(),
        "scraping": {},
        "processing": {},
        "digests": {},
        "email": {},
        "success": False
    }
    
    logger.info("\n[1/5] Scraping articles from sources...")
    try:
        # Running synchronous scraper in a separate thread to avoid blocking the event loop
        scraping_results = await asyncio.to_thread(run_scrapers, hours)
        results["scraping"] = {
            "youtube": len(scraping_results.get("youtube", [])),
            "openai": len(scraping_results.get("openai", [])),
            "anthropic": len(scraping_results.get("anthropic", []))
        }
        logger.info(f"✓ Scraped {results['scraping']['youtube']} YouTube videos, "
                    f"{results['scraping']['openai']} OpenAI articles, "
                    f"{results['scraping']['anthropic']} Anthropic articles")
    except Exception as e:
        logger.error(f"✗ Scraping step failed: {type(e).__name__} - {e}")
        results["scraping_error"] = str(e)

    # FIXED: Pipeline Execution Guard 
    # Stops the pipeline immediately if scraping failed or returned 0 items, preventing old backlog processing
    if "scraping_error" in results or not any(results.get("scraping", {}).values()):
        logger.warning("Scraping failed or found no fresh articles; stopping pipeline.")
        results["duration_seconds"] = (datetime.now() - start_time).total_seconds()
        # Mark as successful if it just cleanly found no articles (avoids cron job failures)
        if "scraping_error" not in results:
            results["success"] = True 
        return results

    logger.info("\n[2/5] Processing Anthropic & OpenAI markdown...")
    try:
        anthropic_result = await asyncio.to_thread(process_anthropic_markdown)
        results["processing"]["anthropic"] = anthropic_result
        logger.info(f"✓ Processed {anthropic_result['processed']} Anthropic articles ({anthropic_result['failed']} failed)")
    except Exception as e:
        logger.error(f"✗ Anthropic processing failed: {type(e).__name__} - {e}")
        results["processing"]["anthropic_error"] = str(e)
        
    try:
        # FIXED: Missing execution call added for OpenAI Markdown
        openai_result = await asyncio.to_thread(process_openai_markdown)
        results["processing"]["openai"] = openai_result
        # Safely using .get() to prevent dict key errors just in case
        logger.info(f"✓ Processed {openai_result.get('processed', 0)} OpenAI articles ({openai_result.get('failed', 0)} failed)")
    except Exception as e:
        logger.error(f"✗ OpenAI processing failed: {type(e).__name__} - {e}")
        results["processing"]["openai_error"] = str(e)

    logger.info("\n[3/5] Processing YouTube transcripts...")
    try:
        youtube_result = await asyncio.to_thread(process_youtube_transcripts)
        results["processing"]["youtube"] = youtube_result
        logger.info(f"✓ Processed {youtube_result['processed']} transcripts ({youtube_result['unavailable']} unavailable)")
    except Exception as e:
        logger.error(f"✗ YouTube transcript processing failed: {type(e).__name__} - {e}")
        results["processing"]["youtube_error"] = str(e)

    logger.info("\n[4/5] Creating digests for articles (Async Concurrency)...")
    try:
        # This will be our natively async bottleneck solver
        digest_result = await process_digests(limit=2) 
        results["digests"] = digest_result
        logger.info(f"✓ Created {digest_result['processed']} digests ({digest_result['failed']} failed)")
    except Exception as e:
        logger.error(f"✗ Digest processing failed: {type(e).__name__} - {e}")
        results["digests_error"] = str(e)

    logger.info("\n[5/5] Generating and sending email digest...")
    try:
        email_result = await asyncio.to_thread(send_digest_email, hours, top_n)
        results["email"] = email_result
        if email_result.get("success"):
            logger.info(f"✓ Email sent successfully with {email_result['articles_count']} articles")
            results["success"] = True
        else:
            logger.error(f"✗ Failed to send email: {email_result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"✗ Email step failed: {type(e).__name__} - {e}")
        results["email"] = {"success": False, "error": str(e)}
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    results["duration_seconds"] = duration
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Pipeline Summary | Duration: {duration:.1f}s | Success: {results['success']}")
    logger.info("=" * 60)
    
    return results


if __name__ == "__main__":
    # Modern Asyncio Entry Point
    result = asyncio.run(run_daily_pipeline(hours=70, top_n=4))
    raise SystemExit(0 if result.get("success") else 1)