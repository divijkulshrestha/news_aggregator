# Quick Start Guide

Get up and running with the Personal News Aggregator in minutes!

## Quick Setup (Docker Compose)

The fastest way to get started:

```powershell
# 1. Start PostgreSQL and run initial ETL
docker-compose up --build

# 2. In a new terminal, start the API server
docker-compose up api

# 3. Open your browser
http://localhost:8000
```

That's it! The app is running with sample articles.

## Local Development Setup

### Step 1: Install Dependencies

```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### Step 2: Start PostgreSQL

```powershell
# Using Docker
docker-compose up -d db

# Or install PostgreSQL locally and create database
```

### Step 3: Set Environment Variables

```powershell
# Copy example env file
Copy-Item .env.example .env

# Edit .env if using custom database credentials
notepad .env
```

### Step 4: Initialize Database

```powershell
# Create tables
python backend/database.py
```

### Step 5: Run ETL to Fetch Articles

```powershell
# Fetch articles from RSS feeds
python etl/etl_news.py --feeds etl/feeds.json --postgres
```

You should see output like:
```
Fetching [top_stories]: http://feeds.reuters.com/reuters/topNews
Fetching [world]: https://www.theguardian.com/world/rss
...
✅ Inserted 45 new articles
```

### Step 6: Start the API Server

```powershell
# Start FastAPI server
uvicorn backend.app:app --reload
```

### Step 7: Open Your Browser

Navigate to: **http://localhost:8000**

You should see your personal news feed! 🎉

## Testing the API

### View API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Test API Endpoints

```powershell
# Get all articles
curl http://localhost:8000/api/articles

# Get technology articles from last hour
curl "http://localhost:8000/api/articles?category=technology&time_range=1h"

# Get statistics
curl http://localhost:8000/api/stats

# Get categories
curl http://localhost:8000/api/categories
```

## Customizing Your News Sources

Edit [../etl/feeds.json](../etl/feeds.json) to add or remove RSS feeds:

```json
{
  "feeds": [
    {
      "category": "your_category",
      "urls": [
        "https://example.com/rss"
      ]
    }
  ]
}
```

Then re-run the ETL:

```powershell
python etl/etl_news.py --feeds etl/feeds.json --postgres
```

## Scheduling Automatic Updates

### Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily (or your preference)
4. Action: Start a program
5. Program: `C:\path\to\venv\Scripts\python.exe`
6. Arguments: `C:\path\to\news_etl\scripts\run_etl.py`

### Using Python Schedule Library

Create `scheduler.py`:

```python
import schedule
import time
from scripts.run_etl import run_etl

# Run every hour
schedule.every().hour.do(run_etl)

while True:
    schedule.run_pending()
    time.sleep(60)
```

Run it:
```powershell
python scheduler.py
```

## Next Steps

### For Local Development:
1. ✅ Add your favorite RSS feeds to [../etl/feeds.json](../etl/feeds.json)
2. ✅ Customize the frontend styling in [../frontend/styles.css](../frontend/styles.css)
3. ✅ Set up automatic ETL scheduling
4. ✅ Add more categories and filters

### For AWS Deployment:
1. ✅ Read [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md)
2. ✅ Set up RDS PostgreSQL
3. ✅ Deploy to ECS Fargate
4. ✅ Configure EventBridge for scheduling

## Troubleshooting

### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:**
- Make sure PostgreSQL is running: `docker-compose ps`
- Check DATABASE_URL in .env file
- Verify PostgreSQL port 5432 is not in use

### No Articles Showing

**Solution:**
- Run ETL first: `python etl/etl_news.py --postgres`
- Check CloudWatch logs (if on AWS)
- Verify RSS feeds are accessible

### Import Errors

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:**
- Activate virtual environment: `.\venv\Scripts\activate`
- Install dependencies: `pip install -r requirements.txt`

### Port 8000 Already in Use

**Solution:**
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID)
taskkill /PID <PID> /F

# Or use different port
uvicorn backend.app:app --port 8001
```

## Useful Commands

```powershell
# Run ETL
python etl/etl_news.py --postgres

# Start API server
uvicorn backend.app:app --reload

# Run tests
pytest etl/tests/

# View database articles (using psql)
psql -h localhost -U news_user -d news_db -c "SELECT category, title FROM articles LIMIT 10;"

# Check Docker logs
docker-compose logs -f

# Stop all Docker containers
docker-compose down

# Rebuild Docker images
docker-compose build --no-cache
```

## Getting Help

- Check [../README.md](../README.md) for full documentation
- See [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) for AWS deployment
- API documentation: http://localhost:8000/docs

Happy news reading! 📰
