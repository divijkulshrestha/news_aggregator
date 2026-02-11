"""Lightweight pandas-based ingestion and processing helpers for news RSS feeds.

Only metadata is extracted (title, link, published_date, summary, source_url).
"""
from typing import List
import json
import os
from pathlib import Path
from datetime import datetime

import requests
import feedparser
from bs4 import BeautifulSoup
import pandas as pd
from dateutil import parser as date_parser
import html


DEFAULT_FEEDS_FILE = Path(__file__).resolve().parent / "feeds.json"


def load_feed_urls(feeds_file: str | Path = None) -> List[str]:
    path = Path(feeds_file) if feeds_file else DEFAULT_FEEDS_FILE
    if not path.exists():
        raise FileNotFoundError(f"Feeds file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("urls", [])


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


def fetch_feed_entries(url: str, timeout: int = 15) -> List[dict]:
    headers = {
        "User-Agent": "news-etl-bot/1.0 (+https://example.com)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

    feed = feedparser.parse(resp.content)
    entries = []
    for e in feed.entries:
        title = getattr(e, "title", "")
        link = getattr(e, "link", "")
        published = getattr(e, "published", None) or getattr(e, "updated", None)
        summary = getattr(e, "summary", None) or getattr(e, "description", None) or ""

        entries.append({
            "source_url": url,
            "title": _clean_html(title),
            "link": link.strip(),
            "published_raw": published,
            "summary": _clean_html(summary),
        })
    return entries


def fetch_all_articles(feeds_file: str | Path = None) -> pd.DataFrame:
    urls = load_feed_urls(feeds_file)
    all_entries: List[dict] = []
    for u in urls:
        print(f"Fetching: {u}")
        all_entries.extend(fetch_feed_entries(u))
    if not all_entries:
        return pd.DataFrame(columns=["source_url", "title", "link", "published_raw", "summary"])  # empty
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
    out_base = Path(output_base)
    out_base.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = out_base / f"news_articles_{run_ts}"
    out_dir.mkdir(parents=True, exist_ok=False)

    out_file = out_dir / "part-00000.csv"
    # Select the columns we want to persist
    cols = [
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
    print(f"Wrote {len(df_to_write)} rows to {out_file}")
    return out_dir


if __name__ == "__main__":
    print("This module provides helper functions. Use etl_news.py to run the pipeline.")