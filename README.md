# News ETL Project (pandas)

Purpose: Ingest news metadata from multiple RSS feeds, normalize and deduplicate entries, and write timestamped CSV output directories under `data/`.

What this rewrite provides:
- A lightweight pandas-based ETL (`etl/etl_news.py`) that fetches feed metadata (title, link, published date, summary).
- Helpers for fetching and cleaning in `etl/ingest_and_process.py`.
- Simple CLI and run script at `etl/run_etl_job.sh` for local or container runs.

Notes & Requirements:
- Python 3.8+ and a virtual environment.
- Dependencies: see `etl/requirements.txt` (includes `pandas`, `feedparser`, `requests`, `beautifulsoup4`, `python-dateutil`).
- This implementation persists metadata only (no full article scraping).

Quick start (local):
```bash
python -m venv .venv
.venv/bin/activate       # or `.venv\Scripts\activate` on Windows
pip install -r etl/requirements.txt
python etl/etl_news.py --feeds etl/feeds.json --output data
```

Output: A new directory such as `data/news_articles_YYYYMMDD_HHMMSS/` containing `part-00000.csv` and `_SUCCESS`.

Docker notes:
- The repo previously used a PySpark image. For the lightweight pandas ETL you can build a simple image using a Python base image and installing `etl/requirements.txt`.
- If you want, I can add a `Dockerfile` optimized for this pandas ETL and a `docker-compose` service that runs it on startup.