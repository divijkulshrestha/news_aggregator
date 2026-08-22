#!/usr/bin/env python3
"""Scheduled ETL job runner for news aggregation.

This script runs the ETL process and can be triggered by:
- AWS EventBridge (CloudWatch Events)
- ECS Scheduled Tasks
- Cron job
- Manual execution
"""
import logging
import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.logging_config import setup_logging
from etl.ingest_and_process import fetch_all_articles, clean_dataframe, save_to_postgres
from datetime import datetime, timedelta

setup_logging()
logger = logging.getLogger(__name__)


def wait_for_db(max_retries=30, delay=2):
    """Wait for database to be ready."""
    from backend.database import engine
    from sqlalchemy import text
    
    for i in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
        except Exception:
            if i < max_retries - 1:
                logger.info("Waiting for database... (%d/%d)", i + 1, max_retries)
                time.sleep(delay)
            else:
                logger.exception("Could not connect to database after %d attempts", max_retries)
                return False
    return False


def cleanup_old_articles():
    """Remove articles older than 7 days, keeping any that are bookmarked."""
    try:
        from backend.database import Article, Bookmark, SessionLocal

        db = SessionLocal()
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        bookmarked_ids = db.query(Bookmark.article_id)
        deleted = db.query(Article).filter(
            Article.ingestion_timestamp < cutoff_date,
            Article.id.notin_(bookmarked_ids)
        ).delete(synchronize_session=False)
        db.commit()
        db.close()

        logger.info("Cleaned up %d old articles", deleted)
        return deleted
    except Exception:
        logger.exception("Error during cleanup")
        return 0


def compute_stats():
    """Roll up today's per-category ingestion counts for the admin stats dashboard."""
    try:
        from backend.database import SessionLocal
        from backend.stats import compute_daily_stats

        db = SessionLocal()
        try:
            compute_daily_stats(db)
        finally:
            db.close()
    except Exception:
        logger.exception("Error computing daily stats")


def run_etl():
    """Run the complete ETL process."""
    logger.info("Starting ETL job at %s", datetime.utcnow().isoformat())

    # Wait for database to be ready
    if not wait_for_db():
        logger.error("ETL job failed: Database not available")
        return 1

    # Initialize database tables if they don't exist
    try:
        from backend.database import init_db
        logger.info("Initializing database tables...")
        init_db()
    except Exception:
        logger.exception("Database initialization warning")

    try:
        # Fetch articles - prefers the DB-backed feeds table, falling back to feeds.json if empty
        logger.info("Fetching articles from feeds...")
        df = fetch_all_articles()

        if df.empty:
            logger.warning("No articles fetched. Exiting.")
            return 0

        # Clean data
        logger.info("Cleaning %d articles...", len(df))
        df_clean = clean_dataframe(df)

        # Save to database
        logger.info("Saving to database...")
        count = save_to_postgres(df_clean)

        # Cleanup old articles
        cleanup_old_articles()

        # Roll up today's per-category counts for the admin stats dashboard
        compute_stats()

        logger.info("ETL job complete. Processed %d articles, inserted %d new ones.", len(df_clean), count)
        return 0

    except Exception:
        logger.exception("ETL job failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_etl())
