"""
Pytest configuration and fixtures for Playwright tests.
"""
import pytest
from playwright.sync_api import Page
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

BASE_URL = "http://localhost:8000"
