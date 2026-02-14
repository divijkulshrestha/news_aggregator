import { test, expect } from '@playwright/test';

test.describe('Article Filtering', () => {
  test('should filter articles by category', async ({ page }) => {
    await page.goto('/');
    
    // Wait for articles to load
    await page.waitForSelector('.loading', { state: 'hidden', timeout: 10000 });
    
    // Click on Technology category
    const techButton = page.locator('.filter-btn[data-category="technology"]');
    await techButton.click();
    
    // Check that Technology button is now active
    await expect(techButton).toHaveClass(/active/);
    
    // Check that All button is no longer active
    await expect(page.locator('.filter-btn[data-category="all"]')).not.toHaveClass(/active/);
    
    // Wait for filtered results
    await page.waitForTimeout(1000);
  });

  test('should switch between different categories', async ({ page }) => {
    await page.goto('/');
    
    await page.waitForSelector('.loading', { state: 'hidden', timeout: 10000 });
    
    const categories = ['technology', 'world', 'cricket', 'all'];
    
    for (const category of categories) {
      const button = page.locator(`.filter-btn[data-category="${category}"]`);
      await button.click();
      await expect(button).toHaveClass(/active/);
      await page.waitForTimeout(500);
    }
  });

  test('should filter articles by time range', async ({ page }) => {
    await page.goto('/');
    
    await page.waitForSelector('.loading', { state: 'hidden', timeout: 10000 });
    
    // Click on Last Hour
    const lastHourBtn = page.locator('.time-btn[data-time="1h"]');
    await lastHourBtn.click();
    
    // Check that Last Hour is now active
    await expect(lastHourBtn).toHaveClass(/active/);
    
    // Click on Last Week
    const lastWeekBtn = page.locator('.time-btn[data-time="7d"]');
    await lastWeekBtn.click();
    
    // Check that Last Week is now active
    await expect(lastWeekBtn).toHaveClass(/active/);
    await expect(lastHourBtn).not.toHaveClass(/active/);
  });

  test('should combine category and time filters', async ({ page }) => {
    await page.goto('/');
    
    await page.waitForSelector('.loading', { state: 'hidden', timeout: 10000 });
    
    // Select Technology category
    await page.click('.filter-btn[data-category="technology"]');
    await page.waitForTimeout(500);
    
    // Select Last Hour time range
    await page.click('.time-btn[data-time="1h"]');
    await page.waitForTimeout(500);
    
    // Both should be active
    await expect(page.locator('.filter-btn[data-category="technology"]')).toHaveClass(/active/);
    await expect(page.locator('.time-btn[data-time="1h"]')).toHaveClass(/active/);
  });
});
