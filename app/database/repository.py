from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import YouTubeVideo, OpenAIArticle, AnthropicArticle, Digest, Recipient
from .connection import get_session


class Repository:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    def get_all_recipients(self) -> List[Recipient]:
        return list(self.session.scalars(select(Recipient)).all())

    def add_recipient(self, name: str, email: str, interests: str = "AI") -> Optional[Recipient]:
        existing = self.session.scalar(select(Recipient).where(Recipient.email == email))
        if existing:
            return None
        db_recipient = Recipient(name=name, email=email, interests=interests)
        self.session.add(db_recipient)
        self.session.commit()
        self.session.refresh(db_recipient)
        return db_recipient

    def delete_recipient(self, email: str) -> bool:
        recipient = self.session.scalar(select(Recipient).where(Recipient.email == email))
        if recipient:
            self.session.delete(recipient)
            self.session.commit()
            return True
        return False

    # Single creates
    def create_youtube_video(self, **kwargs) -> Optional[YouTubeVideo]:
        existing = self.session.scalar(select(YouTubeVideo).where(YouTubeVideo.video_id == kwargs.get("video_id")))
        if existing:
            return None
        video = YouTubeVideo(**kwargs)
        self.session.add(video)
        self.session.commit()
        return video

    def create_openai_article(self, **kwargs) -> Optional[OpenAIArticle]:
        existing = self.session.scalar(select(OpenAIArticle).where(OpenAIArticle.guid == kwargs.get("guid")))
        if existing:
            return None
        article = OpenAIArticle(**kwargs)
        self.session.add(article)
        self.session.commit()
        return article

    def create_anthropic_article(self, **kwargs) -> Optional[AnthropicArticle]:
        existing = self.session.scalar(select(AnthropicArticle).where(AnthropicArticle.guid == kwargs.get("guid")))
        if existing:
            return None
        article = AnthropicArticle(**kwargs)
        self.session.add(article)
        self.session.commit()
        return article

    # Optimized Bulk Creates (Fixes N+1 Problem)
    def bulk_create_youtube_videos(self, videos: List[Dict[str, Any]]) -> int:
        if not videos:
            return 0
        incoming_ids = [v["video_id"] for v in videos]
        existing_ids = set(self.session.scalars(
            select(YouTubeVideo.video_id).where(YouTubeVideo.video_id.in_(incoming_ids))
        ).all())

        new_records = [YouTubeVideo(**v) for v in videos if v["video_id"] not in existing_ids]
        if new_records:
            self.session.add_all(new_records)
            self.session.commit()
        return len(new_records)

    def bulk_create_openai_articles(self, articles: List[Dict[str, Any]]) -> int:
        if not articles:
            return 0
        incoming_guids = [a["guid"] for a in articles]
        existing_guids = set(self.session.scalars(
            select(OpenAIArticle.guid).where(OpenAIArticle.guid.in_(incoming_guids))
        ).all())

        new_records = [OpenAIArticle(**a) for a in articles if a["guid"] not in existing_guids]
        if new_records:
            self.session.add_all(new_records)
            self.session.commit()
        return len(new_records)

    def bulk_create_anthropic_articles(self, articles: List[Dict[str, Any]]) -> int:
        if not articles:
            return 0
        incoming_guids = [a["guid"] for a in articles]
        existing_guids = set(self.session.scalars(
            select(AnthropicArticle.guid).where(AnthropicArticle.guid.in_(incoming_guids))
        ).all())

        new_records = [AnthropicArticle(**a) for a in articles if a["guid"] not in existing_guids]
        if new_records:
            self.session.add_all(new_records)
            self.session.commit()
        return len(new_records)

    def get_anthropic_articles_without_markdown(self, limit: Optional[int] = None) -> List[AnthropicArticle]:
        stmt = select(AnthropicArticle).where(AnthropicArticle.markdown.is_(None))
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def update_anthropic_article_markdown(self, guid: str, markdown: str) -> bool:
        article = self.session.scalar(select(AnthropicArticle).where(AnthropicArticle.guid == guid))
        if article:
            article.markdown = markdown
            self.session.commit()
            return True
        return False

    def get_openai_articles_without_markdown(self, limit: Optional[int] = None) -> List[OpenAIArticle]:
        stmt = select(OpenAIArticle).where(OpenAIArticle.markdown.is_(None))
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def update_openai_article_markdown(self, guid: str, markdown: str) -> bool:
        article = self.session.scalar(select(OpenAIArticle).where(OpenAIArticle.guid == guid))
        if article:
            article.markdown = markdown
            self.session.commit()
            return True
        return False

    def get_youtube_videos_without_transcript(self, limit: Optional[int] = None) -> List[YouTubeVideo]:
        stmt = select(YouTubeVideo).where(YouTubeVideo.transcript.is_(None))
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def update_youtube_video_transcript(self, video_id: str, transcript: str) -> bool:
        video = self.session.scalar(select(YouTubeVideo).where(YouTubeVideo.video_id == video_id))
        if video:
            video.transcript = transcript
            self.session.commit()
            return True
        return False

    # UPDATED: get_articles_without_digest
    def get_articles_without_digest(self, limit: Optional[int] = None, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        articles = []
        digests = self.session.scalars(select(Digest)).all()
        seen_ids = {f"{d.article_type}:{d.article_id}" for d in digests}

        # Query builder for YouTube
        stmt_yt = select(YouTubeVideo).where(
            YouTubeVideo.transcript.isnot(None),
            YouTubeVideo.transcript != "__UNAVAILABLE__"
        )
        if since:
            stmt_yt = stmt_yt.where(YouTubeVideo.published_at >= since)
        youtube_videos = self.session.scalars(stmt_yt).all()
        
        for video in youtube_videos:
            if f"youtube:{video.video_id}" not in seen_ids:
                articles.append({
                    "type": "youtube",
                    "id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "content": video.transcript or video.description or "",
                    "published_at": video.published_at,
                    "image_url": None
                })

        # Query builder for OpenAI
        stmt_openai = select(OpenAIArticle)
        if since:
            stmt_openai = stmt_openai.where(OpenAIArticle.published_at >= since)
        openai_articles = self.session.scalars(stmt_openai).all()
        
        for article in openai_articles:
            if f"openai:{article.guid}" not in seen_ids:
                articles.append({
                    "type": "openai",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.description or "",
                    "published_at": article.published_at,
                    "image_url": getattr(article, "image_url", None)
                })

        # Query builder for Anthropic
        stmt_anth = select(AnthropicArticle).where(AnthropicArticle.markdown.isnot(None))
        if since:
            stmt_anth = stmt_anth.where(AnthropicArticle.published_at >= since)
        anthropic_articles = self.session.scalars(stmt_anth).all()
        
        for article in anthropic_articles:
            if f"anthropic:{article.guid}" not in seen_ids:
                articles.append({
                    "type": "anthropic",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.markdown or article.description or "",
                    "published_at": article.published_at,
                    "image_url": getattr(article, "image_url", None)
                })

        # UPDATED: Sorting articles by published_at date before applying limit
        articles.sort(key=lambda x: x["published_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        if limit:
            articles = articles[:limit]
        return articles

    def create_digest(self, article_type: str, article_id: str, url: str, title: str, summary: str,
                    published_at: Optional[datetime] = None, image_url: Optional[str] = None) -> Optional[Digest]:
        digest_id = f"{article_type}:{article_id}"
        existing = self.session.scalar(select(Digest).where(Digest.id == digest_id))
        if existing:
            return None

        created_at = published_at if published_at else datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        digest = Digest(
            id=digest_id,
            article_type=article_type,
            article_id=article_id,
            url=url,
            title=title,
            summary=summary,
            created_at=created_at,
            image_url=image_url
        )
        self.session.add(digest)
        self.session.commit()
        return digest

    # UPDATED: get_recent_digests
    def get_recent_digests(self, hours: int = 24, limit: int = 20) -> List[Dict[str, Any]]:
        # Calculate cutoff time based on hours provided
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Apply the cutoff time directly in the database query
        digests = self.session.scalars(
            select(Digest)
            .where(Digest.created_at >= cutoff_time)
            .order_by(Digest.created_at.desc())
            .limit(limit)
        ).all()
        
        return [
            {
                "id": d.id,
                "article_type": d.article_type,
                "article_id": d.article_id,
                "url": d.url,
                "title": d.title,
                "summary": d.summary,
                "created_at": d.created_at,
                "image_url": getattr(d, "image_url", None)
            }
            for d in digests
        ]