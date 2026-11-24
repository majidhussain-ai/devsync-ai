from datetime import datetime, timedelta, timezone
from typing import List, Optional
import os
import logging
import feedparser
from pydantic import BaseModel, ConfigDict, Field
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api.proxies import WebshareProxyConfig

logger = logging.getLogger(__name__)


class Transcript(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    text: str = Field(..., min_length=1)


class ChannelVideo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    title: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    video_id: str = Field(..., min_length=1)
    published_at: datetime
    description: str = Field(default="")
    transcript: Optional[str] = None


class YouTubeScraper:
    def __init__(self) -> None:
        proxy_config = None
        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")

        if proxy_username and proxy_password:
            proxy_config = WebshareProxyConfig(
                proxy_username=proxy_username, proxy_password=proxy_password
            )

        self.transcript_api = YouTubeTranscriptApi(proxy_config=proxy_config)

    def _get_rss_url(self, channel_id: str) -> str:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    def _extract_video_id(self, video_url: str) -> str:
        if "youtube.com/watch?v=" in video_url:
            return video_url.split("v=")[1].split("&")[0]
        if "youtube.com/shorts/" in video_url:
            return video_url.split("shorts/")[1].split("?")[0]
        if "youtu.be/" in video_url:
            return video_url.split("youtu.be/")[1].split("?")[0]
        return video_url

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        try:
            transcript = self.transcript_api.fetch(video_id)
            text = " ".join([snippet.text for snippet in transcript.snippets])
            return Transcript(text=text.strip())
        except (TranscriptsDisabled, NoTranscriptFound):
            # Expected API limitations where transcripts are genuinely missing/disabled
            return None
        except Exception:
            # FIXED: Log unexpected transient transcript errors with traceback instead of permanently trapping as None
            logger.exception("Unexpected error fetching transcript for video_id: %s", video_id)
            raise

    def get_latest_videos(self, channel_id: str, hours: int = 24) -> List[ChannelVideo]:
        rss_url = self._get_rss_url(channel_id)
        feed = feedparser.parse(rss_url)
        
        # FIXED: Surface RSS parse failures instead of silent swallowing
        if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
            exc = feed.bozo_exception
            raise RuntimeError(f"RSS fetch/parse failed for {rss_url}: {exc}") from exc

        if not getattr(feed, "entries", None):
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        videos: List[ChannelVideo] = []
        seen_ids: set[str] = set()

        for entry in feed.entries:
            link = entry.get("link", "")
            if not link or "/shorts/" in link:
                continue

            published_parsed = getattr(entry, "published_parsed", None)
            if not published_parsed:
                continue

            published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)
            if published_time >= cutoff_time:
                video_id = entry.get("yt_videoid") or self._extract_video_id(link)
                if not video_id or video_id in seen_ids:
                    continue
                seen_ids.add(video_id)

                videos.append(
                    ChannelVideo(
                        title=entry.get("title", "Untitled Video"),
                        url=link,
                        video_id=video_id,
                        published_at=published_time,
                        description=entry.get("summary", ""),
                    )
                )

        return videos

    def scrape_channel(self, channel_id: str, hours: int = 150) -> List[ChannelVideo]:
        videos = self.get_latest_videos(channel_id, hours)
        result: List[ChannelVideo] = []
        for video in videos:
            transcript = self.get_transcript(video.video_id)
            result.append(
                video.model_copy(
                    update={"transcript": transcript.text if transcript else None}
                )
            )
        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    scraper = YouTubeScraper()
    test_videos = scraper.get_latest_videos("UCn8ujwUInbJkBhffxqAPBVQ", hours=200)
    print(f"Fetched {len(test_videos)} videos.")
    if test_videos:
        print("Sample video:", test_videos[0].model_dump())