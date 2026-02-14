"""FastAPI backend for news aggregation platform."""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import get_db, Article, init_db

app = FastAPI(
    title="Personal News Aggregator",
    description="A minimal news platform aggregating curated RSS feeds",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API responses
class ArticleResponse(BaseModel):
    id: int
    category: str
    title: str
    link: str
    summary: Optional[str]
    published_date: Optional[datetime]
    source_url: str
    ingestion_timestamp: datetime

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total_articles: int
    categories: dict
    latest_ingestion: Optional[datetime]


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """Serve the frontend."""
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Personal News Aggregator API", "docs": "/docs"}


@app.get("/api/articles", response_model=List[ArticleResponse])
async def get_articles(
    category: Optional[str] = Query(None, description="Filter by category"),
    time_range: str = Query("1d", description="Time range: 1h, 1d, or 7d"),
    limit: int = Query(100, le=500, description="Maximum number of articles"),
    db: Session = Depends(get_db)
):
    """Get articles with optional filtering by category and time range."""
    from sqlalchemy import or_, and_
    
    # Calculate time filter
    now = datetime.utcnow()
    time_filters = {
        "1h": now - timedelta(hours=1),
        "1d": now - timedelta(days=1),
        "7d": now - timedelta(days=7),
    }
    
    min_date = time_filters.get(time_range, time_filters["1d"])
    
    # Build query - filter by published_date if available, otherwise use ingestion_timestamp
    query = db.query(Article).filter(
        or_(
            and_(Article.published_date.isnot(None), Article.published_date >= min_date),
            and_(Article.published_date.is_(None), Article.ingestion_timestamp >= min_date)
        )
    )
    
    if category:
        query = query.filter(Article.category == category)
    
    # Order by published date (or ingestion timestamp if published_date is null)
    articles = query.order_by(
        desc(Article.published_date),
        desc(Article.ingestion_timestamp)
    ).limit(limit).all()
    
    return articles


@app.get("/api/categories")
async def get_categories(db: Session = Depends(get_db)):
    """Get all available categories with article counts."""
    from sqlalchemy import func
    
    categories = db.query(
        Article.category,
        func.count(Article.id).label("count")
    ).group_by(Article.category).all()
    
    return [{"category": cat, "count": count} for cat, count in categories]


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """Get overall statistics."""
    from sqlalchemy import func
    
    total = db.query(func.count(Article.id)).scalar()
    
    categories = db.query(
        Article.category,
        func.count(Article.id).label("count")
    ).group_by(Article.category).all()
    
    latest = db.query(func.max(Article.ingestion_timestamp)).scalar()
    
    return {
        "total_articles": total,
        "categories": {cat: count for cat, count in categories},
        "latest_ingestion": latest
    }


@app.delete("/api/cleanup")
async def cleanup_old_articles(db: Session = Depends(get_db)):
    """Remove articles older than 7 days."""
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    deleted = db.query(Article).filter(
        Article.ingestion_timestamp < cutoff_date
    ).delete()
    db.commit()
    return {"message": f"Deleted {deleted} old articles"}


# Mount static files for frontend
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
