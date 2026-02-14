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
        expect(page).to_have_title("Personal News Aggregator")
        
        # Check header is visible
        expect(page.locator("h1")).to_contain_text("Personal News Feed")
        expect(page.locator(".subtitle")).to_contain_text("Curated news from your favorite sources")
    
    def test_should_display_category_filters(self, page: Page):
        """Test that all category filter buttons are present."""
        page.goto("http://localhost:8000/")
        
        # Check all category buttons are present
        categories = ["All", "Top Stories", "World", "Technology", "India", "Cricket"]
        
        for category in categories:
            expect(page.locator(".filter-btn", has_text=category)).to_be_visible()
        
        # Check that "All" is active by default
        expect(page.locator('.filter-btn.active[data-category="all"]')).to_be_visible()
    
    def test_should_display_time_filters(self, page: Page):
        """Test that time filter buttons are present."""
        page.goto("http://localhost:8000/")
        
        # Check time filter buttons
        time_filters = ["Last Hour", "Last Day", "Last Week"]
        
        for time_filter in time_filters:
            expect(page.locator(".time-btn", has_text=time_filter)).to_be_visible()
        
        # Check that "Last Day" is active by default
        expect(page.locator('.time-btn.active[data-time="1d"]')).to_be_visible()
    
    def test_should_have_refresh_button(self, page: Page):
        """Test that refresh button is visible."""
        page.goto("http://localhost:8000/")
        
        refresh_btn = page.locator(".refresh-btn")
        expect(refresh_btn).to_be_visible()
        expect(refresh_btn).to_contain_text("Refresh")
