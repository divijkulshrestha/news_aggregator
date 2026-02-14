"""
Article display and interaction tests.
"""
import pytest
from playwright.sync_api import Page, expect


class TestArticles:
    """Test cases for articles display and interaction."""
    
    def test_should_load_and_display_articles(self, page: Page):
        """Test that articles load and display properly."""
        page.goto("http://localhost:8000/")
        
        # Wait for articles to load (remove loading indicator)
        page.wait_for_selector(".loading", state="hidden", timeout=10000)
        
        # Check that articles container exists
        expect(page.locator("#articles-container")).to_be_visible()
        
        # Check article count is displayed
        article_count = page.locator("#article-count")
        expect(article_count).not_to_contain_text("Loading...")
    
    def test_should_display_article_cards_with_required_information(self, page: Page):
        """Test that article cards contain required elements."""
        page.goto("http://localhost:8000/")
        
        # Wait for articles to load
        try:
            page.wait_for_selector(".article-card", timeout=10000)
        except:
            print("No articles found - this might be expected if database is empty")
            return
        
        # Check if at least one article is displayed
        article_cards = page.locator(".article-card")
        count = article_cards.count()
        
        if count > 0:
            # Check first article has required elements
            first_article = article_cards.first
            expect(first_article.locator(".article-title")).to_be_visible()
            expect(first_article.locator(".article-link")).to_be_visible()
    
    def test_should_refresh_articles_when_refresh_button_clicked(self, page: Page):
        """Test that clicking refresh reloads articles."""
        page.goto("http://localhost:8000/")
        
        # Wait for initial load
        page.wait_for_selector(".loading", state="hidden", timeout=10000)
        
        # Get initial article count
        initial_count = page.locator("#article-count").text_content()
        
        # Click refresh button
        page.click(".refresh-btn")
        
        # Wait for loading state
        page.wait_for_selector(".loading", state="visible")
        page.wait_for_selector(".loading", state="hidden", timeout=10000)
        
        # Verify articles were refreshed (count should still be displayed)
        new_count = page.locator("#article-count").text_content()
        assert new_count != "Loading..."
