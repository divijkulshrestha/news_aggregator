"""Daily rollup aggregation, computed once per ETL run as a batch step downstream of ingestion."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.database import Article, DailyStats

logger = logging.getLogger(__name__)


def compute_daily_stats(db: Session, day: datetime = None) -> Dict[str, int]:
    """Recompute and upsert today's per-category article counts.

    Counts articles by ingestion_timestamp falling on `day` (UTC calendar day, default: today).
    Upserted (not additive) so re-running the ETL multiple times on the same day recomputes
    rather than double-counts.

    Returns:
        Dict of category -> articles_ingested for the day just computed.
    """
    target_day = (day or datetime.now(timezone.utc)).replace(tzinfo=None)
    day_start = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    counts = (
        db.query(Article.category, func.count(Article.id))
        .filter(Article.ingestion_timestamp >= day_start, Article.ingestion_timestamp < day_end)
        .group_by(Article.category)
        .all()
    )
    counts_by_category = {category: count for category, count in counts}

    if not counts_by_category:
        logger.info("No articles ingested on %s, nothing to roll up", day_start.date())
        return {}

    rows = [
        {"date": day_start, "category": category, "articles_ingested": count}
        for category, count in counts_by_category.items()
    ]

    stmt = insert(DailyStats).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["date", "category"],
        set_={"articles_ingested": stmt.excluded.articles_ingested},
    )
    db.execute(stmt)
    db.commit()

    logger.info("Rolled up daily stats for %s: %s", day_start.date(), counts_by_category)
    return counts_by_category
