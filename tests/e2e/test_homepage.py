"""
Homepage UI tests for the news aggregator.
"""
import pytest
from playwright.sync_api import Page, expect


class TestHomepage:
    """Test cases for the homepage."""

    def test_should_load_and_display_news_aggregator(self, page: Page):
        """Test that the page loads with correct title and header."""
        page.goto("http://localhost:8000/")

        # Check page title
        expect(page).to_have_title("Divij's Digest")

        # Check sidebar header is visible
        expect(page.locator(".sidebar-header h1")).to_contain_text("Divij's Digest")

    def test_should_display_category_filters(self, page: Page):
        """Test that all category filter buttons are present in the sidebar."""
        page.goto("http://localhost:8000/")

        categories = [
            "Top Stories", "India", "World", "Business and Finance",
            "Science and History", "Technology", "Company Blogs", "Cricket",
        ]

        for category in categories:
            expect(page.locator(".category-btn", has_text=category)).to_be_visible()

        # "Top Stories" is active by default
        expect(page.locator('.category-btn.active[data-category="top_stories"]')).to_be_visible()

    def test_should_display_time_filters(self, page: Page):
        """Test that time filter buttons are present."""
        page.goto("http://localhost:8000/")

        time_filters = ["Last Hour", "Last Day", "Last Week"]

        for time_filter in time_filters:
            expect(page.locator(".time-btn", has_text=time_filter)).to_be_visible()

        # "Last Day" is active by default
        expect(page.locator('.time-btn.active[data-time="1d"]')).to_be_visible()

    def test_should_have_refresh_button(self, page: Page):
        """Test that refresh button is visible."""
        page.goto("http://localhost:8000/")

        refresh_btn = page.locator(".refresh-btn")
        expect(refresh_btn).to_be_visible()
        expect(refresh_btn).to_contain_text("Refresh")
