"""Database connection and models for news aggregation platform."""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://news_user:news_password@localhost:5432/news_db"
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
    print("✅ Database tables created successfully")


if __name__ == "__main__":
    init_db()
