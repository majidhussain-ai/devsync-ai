from typing import Optional

from app.scrapers.openai import OpenAIScraper
from app.database.repository import Repository


def process_openai_markdown(limit: Optional[int] = None) -> dict:
    scraper = OpenAIScraper()
    repo = None
    try:
        repo = Repository()
        
        # Repository function for OpenAI (matching your Anthropic pattern)
        articles = repo.get_openai_articles_without_markdown(limit=limit)
        processed = 0
        failed = 0
        
        for article in articles:
            markdown = scraper.url_to_markdown(article.url)
            try:
                if markdown:
                    # Repository function to update OpenAI markdown
                    repo.update_openai_article_markdown(article.guid, markdown)
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                print(f"Error processing article {article.guid}: {e}")
                continue
        
        return {
            "total": len(articles),
            "processed": processed,
            "failed": failed
        }
    finally:
        if repo is not None:
            repo.session.close()


if __name__ == "__main__":
    result = process_openai_markdown()
    print(f"Total OpenAI articles: {result['total']}")
    print(f"Processed: {result['processed']}")
    print(f"Failed: {result['failed']}")