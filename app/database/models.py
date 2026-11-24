from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def utc_now() -> datetime:
    """Returns a timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class YouTubeVideo(Base):
    __tablename__ = "youtube_videos"
    
    video_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    channel_id: Mapped[str] = mapped_column(String)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[Optional[str]] = mapped_column(Text)
    transcript: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class OpenAIArticle(Base):
    __tablename__ = "openai_articles"
    
    guid: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[Optional[str]] = mapped_column(String)
    markdown: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class AnthropicArticle(Base):
    __tablename__ = "anthropic_articles"
    
    guid: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[Optional[str]] = mapped_column(String)
    markdown: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Digest(Base):
    __tablename__ = "digests"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    article_type: Mapped[str] = mapped_column(String)
    article_id: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Recipient(Base):
    __tablename__ = "recipients"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    interests: Mapped[Optional[str]] = mapped_column(String, default="AI")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)