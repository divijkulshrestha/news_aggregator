import { test, expect } from '@playwright/test';

test.describe('Homepage', () => {
  test('should load and display the news aggregator', async ({ page }) => {
    await page.goto('/');
    
    // Check page title
    await expect(page).toHaveTitle(/Personal News Aggregator/);
    
    // Check header is visible
    await expect(page.locator('h1')).toContainText('Personal News Feed');
    await expect(page.locator('.subtitle')).toContainText('Curated news from your favorite sources');
  });

  test('should display category filters', async ({ page }) => {
    await page.goto('/');
    
    // Check all category buttons are present
    const categories = ['All', 'Top Stories', 'World', 'Technology', 'India', 'Cricket'];
    
    for (const category of categories) {
      await expect(page.locator('.filter-btn', { hasText: category })).toBeVisible();
    }
    
    // Check that "All" is active by default
    await expect(page.locator('.filter-btn.active[data-category="all"]')).toBeVisible();
  });

  test('should display time filters', async ({ page }) => {
    await page.goto('/');
    
    // Check time filter buttons
    const timeFilters = ['Last Hour', 'Last Day', 'Last Week'];
    
    for (const filter of timeFilters) {
      await expect(page.locator('.time-btn', { hasText: filter })).toBeVisible();
    }
    
    // Check that "Last Day" is active by default
    await expect(page.locator('.time-btn.active[data-time="1d"]')).toBeVisible();
  });

  test('should have refresh button', async ({ page }) => {
    await page.goto('/');
    
    const refreshBtn = page.locator('.refresh-btn');
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toContainText('Refresh');
  });
});
