"""Simple pandas-based ETL runner for news feed metadata.

Usage: 
    python etl/etl_news.py --feeds etl/feeds.json --output data  # Save to CSV
    python etl/etl_news.py --feeds etl/feeds.json --postgres     # Save to PostgreSQL
"""
from pathlib import Path
import argparse
import logging
import sys
import os

from ingest_and_process import fetch_all_articles, clean_dataframe, save_to_csv, save_to_postgres

logger = logging.getLogger(__name__)


def main(feeds: str | None, output: str | None, use_postgres: bool = False) -> int:
    try:
        df = fetch_all_articles(feeds)
    except FileNotFoundError as e:
        logger.error(e)
        return 2
    if df.empty:
        logger.info("No articles fetched. Exiting.")
        return 0

    df_clean = clean_dataframe(df)

    if use_postgres:
        # Save to PostgreSQL database
        count = save_to_postgres(df_clean)
        logger.info("ETL complete. Inserted %d new articles into database.", count)
    else:
        # Save to CSV (legacy mode)
        out_dir = save_to_csv(df_clean, output or "data")
        logger.info("ETL complete. Output directory: %s", out_dir)

    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run news metadata ETL (pandas)")
    parser.add_argument("--feeds", help="Path to feeds.json", default="etl/feeds.json")
    parser.add_argument("--output", help="Base output directory (for CSV mode)", default="data")
    parser.add_argument("--postgres", action="store_true", help="Save to PostgreSQL instead of CSV")
    args = parser.parse_args()
    raise SystemExit(main(args.feeds, args.output, args.postgres))