"""Database connection and models for news aggregation platform."""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# Database URL from environment variable. Only local dev may fall back to the default
# credentials below; any other ENVIRONMENT must set DATABASE_URL explicitly or fail fast,
# rather than silently connecting with well-known default credentials.
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    if ENVIRONMENT == "local":
        DATABASE_URL = "postgresql://news_user:news_password@localhost:5432/news_db"
    else:
        raise RuntimeError(
            f"DATABASE_URL must be set when ENVIRONMENT={ENVIRONMENT!r}; "
            "refusing to fall back to default local credentials."
        )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Article(Base):
    """Article model for storing news articles."""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), index=True, nullable=False)
    source_url = Column(String(500), nullable=False)
    title = Column(String(500), nullable=False)
    link = Column(String(1000), unique=True, nullable=False, index=True)
    published_date = Column(DateTime, index=True)
    summary = Column(Text)
    ingestion_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<Article(id={self.id}, category={self.category}, title={self.title[:50]})>"


class Bookmark(Base):
    """Bookmark model for saving favorite articles."""
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    article = relationship("Article")

    def __repr__(self):
        return f"<Bookmark(article_id={self.article_id})>"


class ReadHistory(Base):
    """Tracks articles the user has clicked through to read."""
    __tablename__ = "read_history"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    visited_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    article = relationship("Article")

    def __repr__(self):
        return f"<ReadHistory(article_id={self.article_id}, visited_at={self.visited_at})>"


class Feed(Base):
    """RSS feed source, replacing the static feeds.json file."""
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)
    url = Column(String(1000), unique=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Feed(category={self.category}, url={self.url})>"


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


if __name__ == "__main__":
    init_db()
