"""Lightweight pandas-based ingestion and processing helpers for news RSS feeds.

Only metadata is extracted (title, link, published_date, summary, source_url, category).
"""
from typing import List, Dict
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

import requests
import feedparser
from bs4 import BeautifulSoup
import pandas as pd
from dateutil import parser as date_parser
from sqlalchemy.dialects.postgresql import insert
import html

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from url_safety import validate_feed_url, UnsafeFeedUrlError

logger = logging.getLogger(__name__)

DEFAULT_FEEDS_FILE = Path(__file__).resolve().parent / "feeds.json"


def load_feeds_from_db() -> List[Dict[str, any]]:
    """Load enabled feeds from the database, grouped by category.

    Returns:
        List of dicts with 'category' and 'urls' keys, where each entry in 'urls'
        is a dict {'url': str, 'feed_id': int}, or [] if the table is empty /
        unavailable (caller should fall back to feeds.json).
    """
    try:
        from backend.database import Feed, SessionLocal
    except ImportError:
        return []

    db = SessionLocal()
    try:
        feeds = db.query(Feed).filter(Feed.enabled.is_(True)).order_by(Feed.category).all()
        grouped: Dict[str, List[dict]] = {}
        for feed in feeds:
            grouped.setdefault(feed.category, []).append({"url": feed.url, "feed_id": feed.id})
        return [{"category": cat, "urls": urls} for cat, urls in grouped.items()]
    except Exception:
        return []
    finally:
        db.close()


def load_categorized_feeds(feeds_file: str | Path = None) -> List[Dict[str, any]]:
    """Load categorized feeds, preferring the database over the JSON file.

    Returns:
        List of dicts with 'category' and 'urls' keys.
    """
    if feeds_file is None:
        db_feeds = load_feeds_from_db()
        if db_feeds:
            return db_feeds

    path = Path(feeds_file) if feeds_file else DEFAULT_FEEDS_FILE
    if not path.exists():
        raise FileNotFoundError(f"Feeds file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support both old and new format
    if "feeds" in data:
        return data["feeds"]
    elif "urls" in data:
        # Legacy format - convert to new format
        return [{"category": "general", "urls": data["urls"]}]
    else:
        return []


def load_feed_urls(feeds_file: str | Path = None) -> List[str]:
    """Legacy function - loads all URLs without categories."""
    feeds = load_categorized_feeds(feeds_file)
    all_urls = []
    for feed in feeds:
        for entry in feed.get("urls", []):
            all_urls.append(entry["url"] if isinstance(entry, dict) else entry)
    return all_urls


def record_feed_run(feed_id: int, success: bool, articles_fetched: int = 0, error_message: str = None) -> None:
    """Record the outcome of a single feed fetch attempt for health monitoring.

    No-ops (with a debug log) if the DB is unavailable or feed_id is None
    (e.g. feeds loaded from feeds.json have no DB-backed Feed row to attribute the run to).
    """
    if feed_id is None:
        return

    try:
        from backend.database import FeedRun, SessionLocal
    except ImportError:
        return

    db = SessionLocal()
    try:
        db.add(FeedRun(
            feed_id=feed_id,
            success=success,
            articles_fetched=articles_fetched,
            error_message=(error_message[:2000] if error_message else None),
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Error recording feed run for feed_id=%s", feed_id)
    finally:
        db.close()


def _clean_html(text: str) -> str:
    if not text:
        return ""
    # Remove HTML tags
    try:
        soup = BeautifulSoup(text, "html.parser")
        cleaned = soup.get_text(separator=" ")
    except Exception:
        cleaned = text
    # Unescape HTML entities and normalize whitespace
    cleaned = html.unescape(cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned


def fetch_feed_entries(url: str, category: str = "general", timeout: int = 15, feed_id: int = None) -> List[dict]:
    """Fetch entries from an RSS feed.

    Args:
        url: RSS feed URL
        category: Category tag for the articles
        timeout: Request timeout in seconds
        feed_id: DB id of the Feed row this URL came from, for health tracking (None if not DB-backed)
    """
    try:
        validate_feed_url(url)
    except UnsafeFeedUrlError as e:
        logger.warning("Refusing to fetch %s: %s", url, e)
        record_feed_run(feed_id, success=False, error_message=str(e))
        return []

    headers = {
        "User-Agent": "news-etl-bot/1.0 (+https://example.com)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.is_redirect:
            redirect_url = urljoin(url, resp.headers.get("Location", ""))
            validate_feed_url(redirect_url)
            resp = requests.get(redirect_url, headers=headers, timeout=timeout, allow_redirects=False)
        resp.raise_for_status()
    except UnsafeFeedUrlError as e:
        logger.warning("Refusing to follow redirect for %s: %s", url, e)
        record_feed_run(feed_id, success=False, error_message=str(e))
        return []
    except Exception as e:
        logger.exception("Error fetching %s", url)
        record_feed_run(feed_id, success=False, error_message=str(e))
        return []

    feed = feedparser.parse(resp.content)
    entries = []
    for e in feed.entries:
        title = getattr(e, "title", "")
        link = getattr(e, "link", "")
        published = getattr(e, "published", None) or getattr(e, "updated", None)
        summary = getattr(e, "summary", None) or getattr(e, "description", None) or ""

        entries.append({
            "category": category,
            "source_url": url,
            "title": _clean_html(title),
            "link": link.strip(),
            "published_raw": published,
            "summary": _clean_html(summary),
        })

    record_feed_run(feed_id, success=True, articles_fetched=len(entries))
    return entries


def fetch_all_articles(feeds_file: str | Path = None) -> pd.DataFrame:
    """Fetch all articles from categorized feeds.
    
    Returns:
        DataFrame with columns: category, source_url, title, link, published_raw, summary
    """
    feeds = load_categorized_feeds(feeds_file)
    all_entries: List[dict] = []
    
    for feed in feeds:
        category = feed.get("category", "general")
        urls = feed.get("urls", [])

        for entry in urls:
            if isinstance(entry, dict):
                url, feed_id = entry["url"], entry.get("feed_id")
            else:
                url, feed_id = entry, None
            logger.info("Fetching [%s]: %s", category, url)
            all_entries.extend(fetch_feed_entries(url, category, feed_id=feed_id))
    
    if not all_entries:
        return pd.DataFrame(columns=["category", "source_url", "title", "link", "published_raw", "summary"])
    
    df = pd.DataFrame(all_entries)
    return df


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    # Parse published dates using dateutil; invalid -> NaT
    def _parse_date(val):
        try:
            return date_parser.parse(val) if val else pd.NaT
        except Exception:
            return pd.NaT

    df = df.copy()
    df["published_date"] = df["published_raw"].apply(_parse_date)
    df["ingestion_timestamp"] = pd.Timestamp.now(tz=None)

    # Basic normalization
    df["title"] = df["title"].astype(str).str.strip()
    df["summary"] = df["summary"].astype(str).str.strip()

    # Drop rows without link or title
    df = df[df["link"].astype(bool)]
    df = df[df["title"].astype(bool)]

    # Deduplicate by link
    df = df.drop_duplicates(subset=["link"]).reset_index(drop=True)
    return df


def save_to_csv(df: pd.DataFrame, output_base: str | Path = "data") -> Path:
    """Save articles to CSV (backward compatibility)."""
    out_base = Path(output_base)
    out_base.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = out_base / f"news_articles_{run_ts}"
    out_dir.mkdir(parents=True, exist_ok=False)

    out_file = out_dir / "part-00000.csv"
    # Select the columns we want to persist
    cols = [
        "category",
        "source_url",
        "title",
        "link",
        "published_date",
        "summary",
        "ingestion_timestamp",
    ]
    df_to_write = df.copy()
    # Ensure published_date is ISO-formatted strings (empty if NaT)
    df_to_write["published_date"] = df_to_write["published_date"].apply(lambda x: x.isoformat() if pd.notna(x) else "")
    df_to_write.to_csv(out_file, columns=cols, index=False, encoding="utf-8")

    # Touch _SUCCESS
    (out_dir / "_SUCCESS").write_text("")
    logger.info("Wrote %d rows to %s", len(df_to_write), out_file)
    return out_dir


def save_to_postgres(df: pd.DataFrame, db_url: str = None) -> int:
    """Save articles to PostgreSQL database.
    
    Args:
        df: Cleaned DataFrame with articles
        db_url: PostgreSQL connection URL
    
    Returns:
        Number of new articles inserted
    """
    try:
        from backend.database import Article, SessionLocal
    except ImportError:
        logger.error("Cannot import database modules. Make sure backend/database.py exists.")
        return 0

    if df.empty:
        logger.info("No articles to save")
        return 0
    
    # Prepare data for insertion
    articles_data = []
    for _, row in df.iterrows():
        article_dict = {
            "category": row.get("category", "general"),
            "source_url": row["source_url"],
            "title": row["title"],
            "link": row["link"],
            "published_date": row["published_date"] if pd.notna(row["published_date"]) else None,
            "summary": row.get("summary", ""),
            "ingestion_timestamp": row.get("ingestion_timestamp", datetime.utcnow()),
        }
        articles_data.append(article_dict)
    
    # Bulk upsert: skip rows whose link already exists (unique constraint on Article.link)
    db = SessionLocal()

    try:
        stmt = insert(Article).values(articles_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["link"]).returning(Article.id)
        inserted_ids = db.execute(stmt).scalars().all()
        db.commit()

        inserted_count = len(inserted_ids)
        logger.info(
            "Inserted %d new articles (skipped %d duplicates)",
            inserted_count, len(articles_data) - inserted_count
        )
        return inserted_count

    except Exception:
        db.rollback()
        logger.exception("Error saving to database")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    print("This module provides helper functions. Use etl_news.py to run the pipeline.")