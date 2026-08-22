"""FastAPI backend for news aggregation platform."""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import get_db, Article, Bookmark, Feed, FeedRun, DailyStats, ReadHistory, init_db
from backend.logging_config import setup_logging
from url_safety import validate_feed_url, UnsafeFeedUrlError

setup_logging()

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
    is_bookmarked: bool = False
    visited_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total_articles: int
    categories: dict
    latest_ingestion: Optional[datetime]


class FeedCreate(BaseModel):
    category: str
    url: str


class FeedUpdate(BaseModel):
    category: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None


class FeedResponse(BaseModel):
    id: int
    category: str
    url: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class StatsOverviewResponse(BaseModel):
    total_articles: int
    articles_today: int
    category_counts_7d: Dict[str, int]
    category_counts_30d: Dict[str, int]
    last_successful_run: Optional[datetime]


class FeedHealthResponse(BaseModel):
    id: int
    category: str
    url: str
    enabled: bool
    last_run_at: Optional[datetime]
    last_run_success: Optional[bool]
    consecutive_failures: int
    success_rate: Optional[float]


class StatsTrendsResponse(BaseModel):
    dates: List[str]
    series: Dict[str, List[int]]


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize database on startup."""
    init_db()


@app.get("/", response_model=None)
async def root() -> Union[FileResponse, Dict[str, str]]:
    """Serve the frontend."""
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Personal News Aggregator API", "docs": "/docs"}


@app.get("/admin.html", response_model=None)
async def admin_page() -> FileResponse:
    """Serve the admin panel (feed management + health/stats)."""
    admin_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "admin.html")
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    raise HTTPException(status_code=404, detail="Not found")


def _time_range_cutoff(time_range: str) -> datetime:
    """Resolve a time_range query param ('1h', '1d', '7d') to a UTC cutoff datetime."""
    now = datetime.utcnow()
    time_filters = {
        "1h": now - timedelta(hours=1),
        "1d": now - timedelta(days=1),
        "7d": now - timedelta(days=7),
    }
    return time_filters.get(time_range, time_filters["1d"])


@app.get("/api/articles", response_model=List[ArticleResponse])
async def get_articles(
    category: Optional[str] = Query(None, description="Filter by category"),
    time_range: str = Query("1d", description="Time range: 1h, 1d, or 7d"),
    limit: int = Query(100, le=500, description="Maximum number of articles"),
    db: Session = Depends(get_db)
) -> List[ArticleResponse]:
    """Get articles with optional filtering by category and time range."""
    min_date = _time_range_cutoff(time_range)

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

    bookmarked_ids = {b.article_id for b in db.query(Bookmark.article_id).all()}
    results = []
    for article in articles:
        response = ArticleResponse.model_validate(article)
        response.is_bookmarked = article.id in bookmarked_ids
        results.append(response)

    return results


@app.get("/api/categories")
async def get_categories(
    time_range: Optional[str] = Query(None, description="Time range: 1h, 1d, or 7d (omit for all-time)"),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get all available categories with article counts, optionally scoped to a time range."""
    query = db.query(Article.category, func.count(Article.id).label("count"))

    if time_range:
        min_date = _time_range_cutoff(time_range)
        query = query.filter(
            or_(
                and_(Article.published_date.isnot(None), Article.published_date >= min_date),
                and_(Article.published_date.is_(None), Article.ingestion_timestamp >= min_date)
            )
        )

    categories = query.group_by(Article.category).all()

    return [{"category": cat, "count": count} for cat, count in categories]


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    """Get overall statistics."""
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


# --- Bookmarks ---

@app.get("/api/bookmarks", response_model=List[ArticleResponse])
async def get_bookmarks(db: Session = Depends(get_db)) -> List[ArticleResponse]:
    """Get all bookmarked articles."""
    articles = (
        db.query(Article)
        .join(Bookmark, Bookmark.article_id == Article.id)
        .order_by(desc(Bookmark.created_at))
        .all()
    )
    results = []
    for article in articles:
        response = ArticleResponse.model_validate(article)
        response.is_bookmarked = True
        results.append(response)
    return results


@app.post("/api/bookmarks/{article_id}", status_code=201)
async def add_bookmark(article_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Bookmark an article."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    existing = db.query(Bookmark).filter(Bookmark.article_id == article_id).first()
    if existing:
        return {"message": "Already bookmarked"}

    db.add(Bookmark(article_id=article_id))
    db.commit()
    return {"message": "Bookmarked"}


@app.delete("/api/bookmarks/{article_id}")
async def remove_bookmark(article_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Remove a bookmark."""
    deleted = db.query(Bookmark).filter(Bookmark.article_id == article_id).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return {"message": "Bookmark removed"}


# --- Read History ---

@app.get("/api/history", response_model=List[ArticleResponse])
async def get_history(
    limit: int = Query(100, le=500, description="Maximum number of articles"),
    db: Session = Depends(get_db)
) -> List[ArticleResponse]:
    """Get articles the user has clicked through to read, most recent first."""
    rows = (
        db.query(Article, ReadHistory.visited_at)
        .join(ReadHistory, ReadHistory.article_id == Article.id)
        .order_by(desc(ReadHistory.visited_at))
        .limit(limit)
        .all()
    )

    bookmarked_ids = {b.article_id for b in db.query(Bookmark.article_id).all()}
    results = []
    for article, visited_at in rows:
        response = ArticleResponse.model_validate(article)
        response.is_bookmarked = article.id in bookmarked_ids
        response.visited_at = visited_at
        results.append(response)
    return results


@app.post("/api/history/{article_id}", status_code=201)
async def log_history(article_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Record that the user clicked through to read an article."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    existing = db.query(ReadHistory).filter(ReadHistory.article_id == article_id).first()
    if existing:
        existing.visited_at = datetime.utcnow()
    else:
        db.add(ReadHistory(article_id=article_id))
    db.commit()
    return {"message": "Logged"}


@app.delete("/api/history")
async def clear_history(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Clear all read history."""
    deleted = db.query(ReadHistory).delete()
    db.commit()
    return {"message": f"Cleared {deleted} history entries"}


# --- RSS Feed Management ---

@app.get("/api/feeds", response_model=List[FeedResponse])
async def list_feeds(db: Session = Depends(get_db)) -> List[Feed]:
    """List all configured RSS feeds."""
    return db.query(Feed).order_by(Feed.category, Feed.url).all()


@app.post("/api/feeds", response_model=FeedResponse, status_code=201)
async def create_feed(feed: FeedCreate, db: Session = Depends(get_db)) -> Feed:
    """Add a new RSS feed."""
    try:
        validate_feed_url(feed.url)
    except UnsafeFeedUrlError as e:
        raise HTTPException(status_code=422, detail=str(e))

    existing = db.query(Feed).filter(Feed.url == feed.url).first()
    if existing:
        raise HTTPException(status_code=409, detail="Feed URL already exists")

    new_feed = Feed(category=feed.category, url=feed.url, enabled=True)
    db.add(new_feed)
    db.commit()
    db.refresh(new_feed)
    return new_feed


@app.patch("/api/feeds/{feed_id}", response_model=FeedResponse)
async def update_feed(feed_id: int, updates: FeedUpdate, db: Session = Depends(get_db)) -> Feed:
    """Update a feed's category, URL, or enabled status."""
    feed = db.query(Feed).filter(Feed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    if updates.category is not None:
        feed.category = updates.category
    if updates.url is not None:
        try:
            validate_feed_url(updates.url)
        except UnsafeFeedUrlError as e:
            raise HTTPException(status_code=422, detail=str(e))
        feed.url = updates.url
    if updates.enabled is not None:
        feed.enabled = updates.enabled

    db.commit()
    db.refresh(feed)
    return feed


@app.delete("/api/feeds/{feed_id}")
async def delete_feed(feed_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Delete an RSS feed."""
    deleted = db.query(Feed).filter(Feed.id == feed_id).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Feed not found")
    return {"message": "Feed deleted"}


# --- Admin: Health & Stats ---

@app.get("/api/admin/stats/overview", response_model=StatsOverviewResponse)
async def get_stats_overview(db: Session = Depends(get_db)) -> StatsOverviewResponse:
    """Rollup stats for the admin dashboard: totals, today's count, and category trends."""
    total_articles = db.query(func.count(Article.id)).scalar()

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    articles_today = db.query(func.count(Article.id)).filter(
        Article.ingestion_timestamp >= today
    ).scalar()

    def category_counts_since(days: int) -> Dict[str, int]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.query(DailyStats.category, func.sum(DailyStats.articles_ingested))
            .filter(DailyStats.date >= cutoff)
            .group_by(DailyStats.category)
            .all()
        )
        return {category: int(total) for category, total in rows}

    last_run = db.query(func.max(FeedRun.run_at)).filter(FeedRun.success.is_(True)).scalar()

    return StatsOverviewResponse(
        total_articles=total_articles,
        articles_today=articles_today,
        category_counts_7d=category_counts_since(7),
        category_counts_30d=category_counts_since(30),
        last_successful_run=last_run,
    )


@app.get("/api/admin/stats/trends", response_model=StatsTrendsResponse)
async def get_stats_trends(
    days: int = Query(30, ge=1, le=90, description="Number of days of history to return"),
    db: Session = Depends(get_db)
) -> StatsTrendsResponse:
    """Daily per-category article counts for the last N days, for the admin trends chart."""
    start_date = (datetime.utcnow() - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    rows = (
        db.query(DailyStats.date, DailyStats.category, DailyStats.articles_ingested)
        .filter(DailyStats.date >= start_date)
        .order_by(DailyStats.date)
        .all()
    )

    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    categories = sorted({category for _, category, _ in rows})
    series = {category: [0] * days for category in categories}

    for date, category, count in rows:
        day_index = (date - start_date).days
        if 0 <= day_index < days:
            series[category][day_index] = count

    return StatsTrendsResponse(dates=dates, series=series)


@app.get("/api/admin/feeds/health", response_model=List[FeedHealthResponse])
async def get_feeds_health(db: Session = Depends(get_db)) -> List[FeedHealthResponse]:
    """Per-feed health: last run status, consecutive failures, and rolling success rate."""
    feeds = db.query(Feed).order_by(Feed.category, Feed.url).all()

    results = []
    for feed in feeds:
        recent_runs = (
            db.query(FeedRun)
            .filter(FeedRun.feed_id == feed.id)
            .order_by(desc(FeedRun.run_at))
            .limit(20)
            .all()
        )

        consecutive_failures = 0
        for run in recent_runs:
            if run.success:
                break
            consecutive_failures += 1

        success_rate = (
            sum(1 for r in recent_runs if r.success) / len(recent_runs)
            if recent_runs else None
        )

        results.append(FeedHealthResponse(
            id=feed.id,
            category=feed.category,
            url=feed.url,
            enabled=feed.enabled,
            last_run_at=recent_runs[0].run_at if recent_runs else None,
            last_run_success=recent_runs[0].success if recent_runs else None,
            consecutive_failures=consecutive_failures,
            success_rate=success_rate,
        ))

    return results


# Mount static files for frontend
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
