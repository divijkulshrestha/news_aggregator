"""Shared logging setup for the app, ETL pipeline, and scripts."""
import logging
import os


def setup_logging() -> None:
    """Configure root logging once, using LOG_LEVEL from the environment (default INFO).

    Uses basicConfig so output goes to stdout/stderr, which is what
    container log drivers (e.g. ECS/CloudWatch) collect by default.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
