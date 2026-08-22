"""
Filter functionality tests.
"""
import pytest
from playwright.sync_api import Page, expect
import time


class TestFiltering:
    """Test cases for article filtering."""

    def test_should_filter_articles_by_category(self, page: Page):
        """Test category filtering."""
        page.goto("http://localhost:8000/")

        # Wait for articles to load
        page.wait_for_selector(".loading", state="hidden", timeout=10000)

        # Click on Technology category
        tech_button = page.locator('.category-btn[data-category="technology"]')
        tech_button.click()

        # Check that Technology button is now active
        expect(tech_button).to_have_class("category-btn active")

        # Check that the previously-active category is no longer active
        expect(page.locator('.category-btn[data-category="top_stories"]')).not_to_have_class("category-btn active")

        # Wait for filtered results
        time.sleep(1)

    def test_should_switch_between_different_categories(self, page: Page):
        """Test switching between multiple categories."""
        page.goto("http://localhost:8000/")

        page.wait_for_selector(".loading", state="hidden", timeout=10000)

        categories = ["technology", "world", "cricket", "top_stories"]

        for category in categories:
            button = page.locator(f'.category-btn[data-category="{category}"]')
            button.click()
            expect(button).to_have_class("category-btn active")
            time.sleep(0.5)

    def test_should_filter_articles_by_time_range(self, page: Page):
        """Test time range filtering."""
        page.goto("http://localhost:8000/")

        page.wait_for_selector(".loading", state="hidden", timeout=10000)

        # Click on Last Hour
        last_hour_btn = page.locator('.time-btn[data-time="1h"]')
        last_hour_btn.click()

        # Check that Last Hour is now active
        expect(last_hour_btn).to_have_class("filter-btn time-btn active")

        # Click on Last Week
        last_week_btn = page.locator('.time-btn[data-time="7d"]')
        last_week_btn.click()

        # Check that Last Week is now active
        expect(last_week_btn).to_have_class("filter-btn time-btn active")
        expect(last_hour_btn).not_to_have_class("filter-btn time-btn active")

    def test_should_combine_category_and_time_filters(self, page: Page):
        """Test combining category and time filters."""
        page.goto("http://localhost:8000/")

        page.wait_for_selector(".loading", state="hidden", timeout=10000)

        # Select Technology category
        page.click('.category-btn[data-category="technology"]')
        time.sleep(0.5)

        # Select Last Hour time range
        page.click('.time-btn[data-time="1h"]')
        time.sleep(0.5)

        # Both should be active
        expect(page.locator('.category-btn[data-category="technology"]')).to_have_class("category-btn active")
        expect(page.locator('.time-btn[data-time="1h"]')).to_have_class("filter-btn time-btn active")
