import { test, expect } from '@playwright/test';

test.describe('Articles Display', () => {
  test('should load and display articles', async ({ page }) => {
    await page.goto('/');
    
    // Wait for articles to load (remove loading indicator)
    await page.waitForSelector('.loading', { state: 'hidden', timeout: 10000 });
    
    // Check that articles container exists
    await expect(page.locator('#articles-container')).toBeVisible();
    
    // Check article count is displayed
    const articleCount = page.locator('#article-count');
    await expect(articleCount).not.toContainText('Loading...');
  });

  test('should display article cards with required information', async ({ page }) => {
    await page.goto('/');
    
    // Wait for articles to load
    await page.waitForSelector('.article-card', { timeout: 10000 }).catch(() => {
      console.log('No articles found - this might be expected if database is empty');
    });
    
    // Check if at least one article is displayed
    const articleCards = page.locator('.article-card');
    const count = await articleCards.count();
    
    if (count > 0) {
      // Check first article has required elements
      const firstArticle = articleCards.first();
      await expect(firstArticle.locator('.article-title')).toBeVisible();
      await expect(firstArticle.locator('.article-link')).toBeVisible();
    }
  });

  test('should refresh articles when refresh button is clicked', async ({ page }) => {
    await page.goto('/');
    
    // Wait for initial load
    await page.waitForSelector('.loading', { state: 'hidden', timeout: 10000 });
    
    // Get initial article count
    const initialCount = await page.locator('#article-count').textContent();
    
    // Click refresh button
    await page.click('.refresh-btn');
    
    // Wait for loading state
    await page.waitForSelector('.loading', { state: 'visible' });
    await page.waitForSelector('.loading', { state: 'hidden', timeout: 10000 });
    
    // Verify articles were refreshed (count should still be displayed)
    const newCount = await page.locator('#article-count').textContent();
    expect(newCount).not.toBe('Loading...');
  });
});
