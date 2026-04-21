import { test, expect } from '@playwright/test';

test.describe('Search Functionality', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to the application before each test
    await page.goto('http://localhost:5173/');
  });

  test('Basic search functionality - find specific product', async ({ page }) => {
    const searchInput = page.getByRole('textbox', { name: 'Search products...' });
    
    // Click on the search input field to test basic search interaction
    await searchInput.click();
    
    // Test search functionality by typing a product name
    await searchInput.fill('headphones');
    
    // Verify search results
    await expect(page.getByText('Showing 1 product(s)')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Wireless Headphones' })).toBeVisible();
    await expect(page.getByText('High-quality wireless headphones with noise cancellation')).toBeVisible();
    
    // Verify clear button appears
    await expect(page.getByRole('button', { name: '✕' })).toBeVisible();
  });

  test('Partial matching search - find multiple products', async ({ page }) => {
    const searchInput = page.getByRole('textbox', { name: 'Search products...' });
    
    // Test partial matching by searching for 'usb'
    await searchInput.click();
    await searchInput.fill('usb');
    
    // Verify multiple matching products are found
    await expect(page.getByText('Showing 2 product(s)')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'USB-C Cable' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'USB Hub' })).toBeVisible();
  });

  test('Case insensitive search functionality', async ({ page }) => {
    const searchInput = page.getByRole('textbox', { name: 'Search products...' });
    
    // Test case sensitivity by typing 'MOUSE' in uppercase
    await searchInput.click();
    await searchInput.fill('MOUSE');
    
    // Verify case insensitive search works
    await expect(page.getByText('Showing 1 product(s)')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Mouse Pad' })).toBeVisible();
  });

  test('No results scenario - handle invalid search terms', async ({ page }) => {
    const searchInput = page.getByRole('textbox', { name: 'Search products...' });
    
    // Test no results by typing a non-existent product term
    await searchInput.click();
    await searchInput.fill('xyz123');
    
    // Verify no results message is displayed
    await expect(page.getByText('Showing 0 product(s)')).toBeVisible();
    await expect(page.getByText('No products found. Try a different search!')).toBeVisible();
  });

  test('Clear search functionality - reset to all products', async ({ page }) => {
    const searchInput = page.getByRole('textbox', { name: 'Search products...' });
    const clearButton = page.getByRole('button', { name: '✕' });
    
    // Perform a search first
    await searchInput.click();
    await searchInput.fill('headphones');
    await expect(page.getByText('Showing 1 product(s)')).toBeVisible();
    
    // Test clearing the search to see if all products are shown again
    await clearButton.click();
    
    // Verify all products are restored
    await expect(page.getByText('Showing 8 product(s)')).toBeVisible();
    await expect(searchInput).toHaveValue('');
    
    // Verify multiple products are visible again
    await expect(page.getByRole('heading', { name: 'Wireless Headphones' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Laptop Stand' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'USB-C Cable' })).toBeVisible();
  });

  test('Search by category name should return no results', async ({ page }) => {
    const searchInput = page.getByRole('textbox', { name: 'Search products...' });
    
    // Test search by category name 'electronics' - should not match category field
    await searchInput.click();
    await searchInput.fill('electronics');
    
    // Verify category search doesn't match products
    await expect(page.getByText('Showing 0 product(s)')).toBeVisible();
    await expect(page.getByText('No products found. Try a different search!')).toBeVisible();
  });

  test('Search input validation - empty search shows all products', async ({ page }) => {
    // Verify initial state shows all products
    await expect(page.getByText('Showing 8 product(s)')).toBeVisible();
    
    // Click on search input and verify it becomes active
    const searchInput = page.getByRole('textbox', { name: 'Search products...' });
    await searchInput.click();
    await expect(searchInput).toBeFocused();
  });

  test('Search results display - verify product information', async ({ page }) => {
    const searchInput = page.getByRole('textbox', { name: 'Search products...' });
    
    // Search for a specific product
    await searchInput.fill('Portable Charger');
    
    // Verify complete product information is displayed correctly
    await expect(page.getByText('Showing 1 product(s)')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Portable Charger 123' })).toBeVisible();
    await expect(page.getByText('20000mAh portable power bank with fast charging')).toBeVisible();
    await expect(page.getByText('$49.99')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add to Cart' })).toBeVisible();
  });
});