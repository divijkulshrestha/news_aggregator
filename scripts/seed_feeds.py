#!/usr/bin/env python3
"""One-time migration: load etl/feeds.json into the feeds database table."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.ingest_and_process import load_categorized_feeds
from backend.database import Feed, SessionLocal, init_db


def seed_feeds():
    init_db()
    feeds = load_categorized_feeds()

    db = SessionLocal()
    inserted = 0
    try:
        for feed in feeds:
            category = feed.get("category", "general")
            for url in feed.get("urls", []):
                existing = db.query(Feed).filter(Feed.url == url).first()
                if not existing:
                    db.add(Feed(category=category, url=url, enabled=True))
                    inserted += 1
        db.commit()
        print(f"Seeded {inserted} feeds into the database.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_feeds()
