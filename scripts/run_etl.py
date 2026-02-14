#!/usr/bin/env python3
"""Scheduled ETL job runner for news aggregation.

This script runs the ETL process and can be triggered by:
- AWS EventBridge (CloudWatch Events)
- ECS Scheduled Tasks
- Cron job
- Manual execution
"""
import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.ingest_and_process import fetch_all_articles, clean_dataframe, save_to_postgres
from datetime import datetime, timedelta


def wait_for_db(max_retries=30, delay=2):
    """Wait for database to be ready."""
    from backend.database import engine
    from sqlalchemy import text
    
    for i in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
            return True
        except Exception as e:
            if i < max_retries - 1:
                print(f"⏳ Waiting for database... ({i+1}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"❌ Could not connect to database after {max_retries} attempts")
                return False
    return False


def cleanup_old_articles():
    """Remove articles older than 7 days."""
    try:
        from backend.database import Article, SessionLocal
        
        db = SessionLocal()
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        deleted = db.query(Article).filter(
            Article.ingestion_timestamp < cutoff_date
        ).delete()
        db.commit()
        db.close()
        
        print(f"🗑️  Cleaned up {deleted} old articles")
        return deleted
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return 0


def run_etl():
    """Run the complete ETL process."""
    print(f"🚀 Starting ETL job at {datetime.utcnow().isoformat()}")
    
    # Wait for database to be ready
    if not wait_for_db():
        print("❌ ETL job failed: Database not available")
        return 1
    
    # Initialize database tables if they don't exist
    try:
        from backend.database import init_db
        print("🔧 Initializing database tables...")
        init_db()
    except Exception as e:
        print(f"⚠️  Database initialization warning: {e}")
    
    try:
        # Fetch articles
        feeds_path = Path(__file__).resolve().parent.parent / "etl" / "feeds.json"
        print(f"📡 Fetching articles from feeds...")
        df = fetch_all_articles(feeds_path)
        
        if df.empty:
            print("⚠️  No articles fetched. Exiting.")
            return 0
        
        # Clean data
        print(f"🧹 Cleaning {len(df)} articles...")
        df_clean = clean_dataframe(df)
        
        # Save to database
        print(f"💾 Saving to database...")
        count = save_to_postgres(df_clean)
        
        # Cleanup old articles
        cleanup_old_articles()
        
        print(f"✅ ETL job complete. Processed {len(df_clean)} articles, inserted {count} new ones.")
        return 0
        
    except Exception as e:
        print(f"❌ ETL job failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_etl())
