import { test, expect } from '@playwright/test';

test.describe('API Endpoints', () => {
  test('should fetch articles from API', async ({ request }) => {
    const response = await request.get('/api/articles');
    
    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
  });

  test('should filter articles by category via API', async ({ request }) => {
    const response = await request.get('/api/articles?category=technology');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    
    // All returned articles should be in technology category
    data.forEach((article: any) => {
      expect(article.category).toBe('technology');
    });
  });

  test('should filter articles by time range via API', async ({ request }) => {
    const response = await request.get('/api/articles?hours=1');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    
    // Check that articles are recent
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    data.forEach((article: any) => {
      const publishedDate = new Date(article.published_date);
      expect(publishedDate.getTime()).toBeGreaterThanOrEqual(oneHourAgo.getTime());
    });
  });

  test('should return stats from API', async ({ request }) => {
    const response = await request.get('/api/stats');
    
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    
    expect(data).toHaveProperty('total_articles');
    expect(data).toHaveProperty('by_category');
    expect(typeof data.total_articles).toBe('number');
  });
});
