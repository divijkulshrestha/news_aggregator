# news-etl-mvp/etl/ingest_and_process.py

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit, udf, to_timestamp
from pyspark.sql.types import StructType, StructField, StringType, TimestampType
import feedparser
import requests
from bs4 import BeautifulSoup
import json
import os
import datetime

# --- Configuration ---
FEEDS_FILE = "/app/feeds.json"
OUTPUT_DIR = "/app/data" # Directory within the Docker container
OUTPUT_FILENAME_PREFIX = "news_articles"

# --- Spark Session Initialization (Local Mode) ---
spark = SparkSession.builder \
    .appName("NewsETL_MVP") \
    .master("local[*]") \
    .config("spark.driver.memory", "4g") \
    .config("spark.executor.memory", "4g") \
    .getOrCreate()

print("Spark Session initialized in local mode.")

# Before parsing
spark.conf.set("spark.sql.legacy.timeParserPolicy", "LEGACY")

# --- Helper Function to Fetch and Parse a Single RSS Feed ---
def fetch_and_parse_feed(url):
    """Fetches and parses a single RSS feed, returning a list of article dictionaries."""
    articles = []
    try:
        print(f"Fetching feed: {url}")
        response = requests.get(url, timeout=15) # Increased timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        feed = feedparser.parse(response.content)

        for entry in feed.entries:
            title = getattr(entry, 'title', 'No Title').replace('\n', ' ').strip()
            link = getattr(entry, 'link', 'No Link').replace('\n', ' ').strip()
            published = getattr(entry, 'published', None)
            summary = getattr(entry, 'summary', getattr(entry, 'description', 'No Summary')).replace('\n', ' ').strip()
            
            print(published, title, link)

            full_content = None
            if link and link != "No Link":
                try:
                    # Attempt to fetch full article content (basic scraping)
                    article_response = requests.get(link, timeout=10)
                    article_response.raise_for_status()
                    soup = BeautifulSoup(article_response.text, 'html.parser')
                    # This is a very basic attempt. Real web scraping needs more specific selectors.
                    # Try to find common article content containers
                    article_body = soup.find('article') or soup.find('div', class_='article-body') or soup.find('main')
                    if article_body:
                        paragraphs = article_body.find_all('p')
                        full_content = ' '.join([p.get_text().strip() for p in paragraphs if p.get_text().strip() != ''])
                    else:
                        full_content = ' '.join([p.get_text().strip() for p in soup.find_all('p') if p.get_text().strip() != ''])

                    if not full_content: # Fallback if no specific content found
                        full_content = summary # Use summary if full content extraction fails

                except requests.exceptions.RequestException as req_err:
                    print(f"  Warning: HTTP error fetching full content for {link}: {req_err}")
                    full_content = summary # Use summary as fallback
                except Exception as e:
                    print(f"  Warning: Error parsing full content for {link}: {e}")
                    full_content = summary # Use summary as fallback

            articles.append({
                "source_url": url,
                "title": title,
                "link": link,
                "published_date": published,
                "summary": summary,
                "full_content": full_content
            })
        print(f"Fetched {len(articles)} articles from {url}")
        return articles
    except requests.exceptions.RequestException as req_err:
        print(f"Error fetching feed {url}: {req_err}")
    except Exception as e:
        print(f"Error parsing feed {url}: {e}")
    return []

# --- Main ETL Logic ---
if __name__ == "__main__":
    # 1. Load RSS Feeds from JSON
    try:
        with open(FEEDS_FILE, "r") as f:
            feed_urls = json.load(f)["urls"]
        print(f"Loaded {len(feed_urls)} RSS feed URLs.")
    except FileNotFoundError:
        print(f"Error: {FEEDS_FILE} not found. Please create it.")
        spark.stop()
        exit()
    except Exception as e:
        print(f"Error loading {FEEDS_FILE}: {e}")
        spark.stop()
        exit()

    all_articles_data = []
    for url in feed_urls:
        all_articles_data.extend(fetch_and_parse_feed(url))

    if not all_articles_data:
        print("No articles fetched. Exiting.")
        spark.stop()
        exit()

    # Define schema for better data quality and performance
    schema = StructType([
        StructField("source_url", StringType(), True),
        StructField("title", StringType(), True),
        StructField("link", StringType(), True),
        StructField("published_date", StringType(), True), # Raw string from feedparser
        StructField("summary", StringType(), True),
        StructField("full_content", StringType(), True)
    ])

    # Create Spark DataFrame from collected data
    raw_df = spark.createDataFrame(all_articles_data, schema=schema)
    print(f"Initial DataFrame created with {raw_df.count()} rows.")
    raw_df.printSchema()

    # 2. Transformation (Basic Cleaning & Duplication Handling)
    processed_df = raw_df \
        .withColumn("ingestion_timestamp", current_timestamp()) \
        .withColumn("published_date", to_timestamp(raw_df["published_date"], "EEE, dd MMM yyyy HH:mm:ss")) # Attempt to parse common RSS date format

    # Handle common HTML entities in text (basic)
    from pyspark.sql.functions import lit, regexp_replace
    def clean_text_for_csv(text_col):
        # Remove common HTML tags (not exhaustive)
        text_col = regexp_replace(text_col, "<[^>]*>", "")
        # Replace common HTML entities (add more as needed)
        text_col = regexp_replace(text_col, "&amp;", "&")
        text_col = regexp_replace(text_col, "&lt;", "<")
        text_col = regexp_replace(text_col, "&gt;", ">")
        text_col = regexp_replace(text_col, "&quot;", "\"")
        text_col = regexp_replace(text_col, "&#39;", "'")
        return text_col

    processed_df = processed_df.withColumn("title", clean_text_for_csv(processed_df["title"]))
    processed_df = processed_df.withColumn("summary", clean_text_for_csv(processed_df["summary"]))
    processed_df = processed_df.withColumn("full_content", clean_text_for_csv(processed_df["full_content"]))

    # Deduplicate based on link (assuming link is unique for an article)
    deduplicated_df = processed_df.dropDuplicates(["link"])
    print(f"DataFrame after deduplication: {deduplicated_df.count()} rows.")

    # 3. Loading to CSV
    # Ensure the output directory exists on the host (Docker will mount it)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_path = os.path.join(OUTPUT_DIR, f"{OUTPUT_FILENAME_PREFIX}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    print(f"Saving processed data to CSV at: {output_path}")

# Write as a single CSV file for simplicity in MVP, good for smaller datasets
    deduplicated_df.coalesce(1).write \
        .option("header", True) \
        .option("escape", "\"") \
        .option("quoteMode", "ALL") \
        .csv(output_path, mode="overwrite")

    print("CSV file(s) saved successfully.")
    spark.stop()
    print("Spark Session stopped.")