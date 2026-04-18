import { expect, type Locator, type Page } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Page object for EcoShop home/search interactions.
 */
export class HomePage extends BasePage {
  private readonly searchInput: Locator;
  private readonly productCountLabel: Locator;
  private readonly productCards: Locator;
  private readonly addToCartButtons: Locator;

  /**
   * @param page Playwright Page instance for the current browser context.
   */
  constructor(page: Page) {
    super(page);
    this.searchInput = page.getByRole('textbox', { name: 'Search products...' });
    this.productCountLabel = page.locator('text=/^Showing\\s+\\d+\\s+product\\(s\\)$/');
    this.productCards = page.locator('[data-testid="product-card"], .product-card');
    this.addToCartButtons = page.getByRole('button', { name: 'Add to Cart' });
  }

  /**
   * Opens the application home page.
   */
  public async open(): Promise<void> {
    await this.navigate('/');
    await this.waitForPageReady();
    await this.waitForVisible(this.searchInput);
  }

  /**
   * Searches for a product from the home page search textbox.
   * @param productName Product text to type in the search input.
   */
  public async searchForProduct(productName: string): Promise<void> {
    await this.waitForVisible(this.searchInput);
    await this.searchInput.fill(productName);
  }

  /**
   * Logs the locator object used for the search input for debugging.
   */
  public logSearchInputLocator(): void {
    console.log('Search Input Attributes:', this.searchInput);
  }

  /**
   * Verifies that the filtered product result count displays the expected item count.
   */
  public async expectProductCount(expectedCount: number): Promise<void> {
    await expect(this.productCountLabel).toContainText(`Showing ${expectedCount} product(s)`);
  }

  /**
   * Verifies that the requested product title is visible.
   */
  public async expectProductHeadingVisible(productName: string): Promise<void> {
    await expect(this.page.getByRole('heading', { name: productName })).toBeVisible();
  }

  /**
   * Backward-compatible wrapper for existing exact-match tests.
   */
  public async expectWirelessHeadphonesVisible(): Promise<void> {
    await this.expectProductHeadingVisible('Wireless Headphones');
  }

  /**
   * Verifies the count of rendered product cards when stable test ids exist.
   */
  public async expectRenderedProductCards(expectedCount: number): Promise<void> {
    if (await this.productCards.count()) {
      await expect(this.productCards).toHaveCount(expectedCount);
    }
  }

  /**
   * Verifies only one Add to Cart button is present after filtering.
   */
  public async expectSingleAddToCartButton(): Promise<void> {
    await expect(this.addToCartButtons).toHaveCount(1);
  }

  /**
   * Verifies the visible page state for visual regression checks.
   */
  public async expectInitialVisualState(): Promise<void> {
    await this.waitForVisible(this.searchInput);
    await expect(this.productCountLabel).toBeVisible();
  }
}
