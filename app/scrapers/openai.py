import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import feedparser
import trafilatura
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class OpenAIArticle(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    title: str = Field(..., min_length=1)
    description: str = Field(default="")
    url: str = Field(..., min_length=1)
    guid: str = Field(..., min_length=1)
    published_at: datetime
    category: Optional[str] = None
    image_url: Optional[str] = None


class OpenAIScraper:
    def __init__(self) -> None:
        self.rss_url: str = "https://openai.com/news/rss.xml"

    def get_articles(self, hours: int = 24) -> List[OpenAIArticle]:
        feed = feedparser.parse(self.rss_url)
        
        # FIXED: Surface RSS parse failures instead of silent swallowing
        if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
            exc = feed.bozo_exception
            raise RuntimeError(f"RSS fetch/parse failed for {self.rss_url}: {exc}") from exc

        if not getattr(feed, "entries", None):
            return []

        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        articles: List[OpenAIArticle] = []
        seen_guids: set[str] = set()

        for entry in feed.entries:
            published_parsed = getattr(entry, "published_parsed", None)
            if not published_parsed:
                continue

            published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)
            if published_time >= cutoff_time:
                guid = entry.get("id") or entry.get("link") or ""
                if not guid or guid in seen_guids:
                    continue
                seen_guids.add(guid)

                image_url = self._extract_image_url(entry)
                tags = entry.get("tags")
                category = tags[0].get("term") if tags and isinstance(tags, list) else None

                articles.append(
                    OpenAIArticle(
                        title=entry.get("title", "Untitled"),
                        description=entry.get("description", ""),
                        url=entry.get("link", ""),
                        guid=guid,
                        published_at=published_time,
                        category=category,
                        image_url=image_url,
                    )
                )

        return articles

    @staticmethod
    def _extract_image_url(entry: dict) -> Optional[str]:
        # FIXED: Replaced dot notation with safe dictionary .get() access
        media_thumbnail = entry.get("media_thumbnail")
        if media_thumbnail and isinstance(media_thumbnail, list):
            return media_thumbnail[0].get("url")
            
        media_content = entry.get("media_content")
        if media_content and isinstance(media_content, list):
            return media_content[0].get("url")
            
        for link in entry.get("links", []):
            if "image" in link.get("type", ""):
                return link.get("href")
        return None

    def url_to_markdown(self, url: str) -> Optional[str]:
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return None
            return trafilatura.extract(
                downloaded,
                output_format="markdown",
                include_links=True,
                include_images=False,
            )
        except Exception:
            # FIXED: Log unexpected exceptions with traceback instead of silent return
            logger.exception("Failed to convert URL to markdown: %s", url)
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    scraper = OpenAIScraper()
    articles = scraper.get_articles(hours=100)
    print(f"Fetched {len(articles)} OpenAI articles.")
    if articles:
        print("Sample:", articles[0].model_dump())