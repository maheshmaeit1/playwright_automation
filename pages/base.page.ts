import { expect, type Locator, type Page } from '@playwright/test';

/**
 * Shared page object utilities for all app pages.
 */
export class BasePage {
  /**
   * @param page Playwright Page instance for browser interactions.
   */
  constructor(protected readonly page: Page) {}

  /**
   * Navigates to the provided route using configured Playwright baseURL.
   * @param path Relative route path (defaults to root '/').
   */
  public async navigate(path = '/'): Promise<void> {
    await this.page.goto(path);
  }

  /**
   * Waits until the given locator is visible before continuing.
   */
  protected async waitForVisible(locator: Locator): Promise<void> {
    await expect(locator).toBeVisible();
  }

  /**
   * Provides a small synchronization point for stable visual assertions.
   */
  public async waitForPageReady(): Promise<void> {
    await this.page.waitForLoadState('domcontentloaded');
  }
}
