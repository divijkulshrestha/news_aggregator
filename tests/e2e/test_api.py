"""
API endpoint tests using Playwright's request context.
"""
import pytest
from playwright.sync_api import APIRequestContext, expect
from datetime import datetime, timedelta


class TestAPI:
    """Test cases for API endpoints."""
    
    @pytest.fixture(scope="function")
    def api_context(self, playwright):
        """Create an API request context."""
        request_context = playwright.request.new_context(
            base_url="http://localhost:8000"
        )
        yield request_context
        request_context.dispose()
    
    def test_should_fetch_articles_from_api(self, api_context: APIRequestContext):
        """Test fetching articles from API."""
        response = api_context.get("/api/articles")
        
        assert response.ok
        assert response.status == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_should_filter_articles_by_category_via_api(self, api_context: APIRequestContext):
        """Test category filtering via API."""
        response = api_context.get("/api/articles?category=technology")
        
        assert response.ok
        data = response.json()
        assert isinstance(data, list)
        
        # All returned articles should be in technology category
        for article in data:
            assert article["category"] == "technology"
    
    def test_should_filter_articles_by_time_range_via_api(self, api_context: APIRequestContext):
        """Test time range filtering via API."""
        response = api_context.get("/api/articles?hours=1")
        
        assert response.ok
        data = response.json()
        assert isinstance(data, list)
        
        # Check that articles are recent
        one_hour_ago = datetime.now() - timedelta(hours=1)
        for article in data:
            published_date = datetime.fromisoformat(article["published_date"].replace("Z", "+00:00"))
            assert published_date >= one_hour_ago
    
    def test_should_return_stats_from_api(self, api_context: APIRequestContext):
        """Test stats endpoint."""
        response = api_context.get("/api/stats")
        
        assert response.ok
        data = response.json()
        
        assert "total_articles" in data
        assert "by_category" in data
        assert isinstance(data["total_articles"], int)
