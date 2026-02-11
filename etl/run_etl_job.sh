# Simple run script for the pandas ETL
set -euo pipefail

PYTHON=${PYTHON:-python}
${PYTHON} etl/etl_news.py --feeds etl/feeds.json --output data

# --- Keep the container alive ---
#!/bin/bash

# --- Start Jupyter Notebook in the background ---
echo "Starting Jupyter Notebook in background..."
/usr/local/bin/start-notebook.sh --ip=0.0.0.0 --port=8888 --no-browser --allow-root &

# --- Run PySpark ETL Job ---
echo "Running PySpark ETL job..."
mkdir -p /app/container_logs

echo "Waiting for database (db:5432) to be available..."
/usr/local/bin/wait-for-it.sh db:5432 --timeout=60 --strict -- \
  spark-submit \
  --jars /usr/local/spark/jars/postgresql-42.7.7.jar \
  --conf spark.driver.extraClassPath=/usr/local/spark/jars/postgresql-42.7.7.jar \
  --conf spark.executor.extraClassPath=/usr/local/spark/jars/postgresql-42.7.7.jar \
  /app/ingest_and_process.py > "/app/container_logs/etl_run_$(date +%Y%m%d_%H%M%S).log" 2>&1

echo "PySpark ETL job finished. Jupyter is still running."

# --- Keep the container alive ---
tail -f /dev/null