# Project Details

## Overview
This repository is a Playwright + TypeScript UI automation project for a demo e-commerce application (EcoShop).
Current automation scope validates product search behavior.

## Tech Stack
- Playwright Test: `@playwright/test` `^1.58.2`
- TypeScript: `^6.0.2`
- Node type definitions: `@types/node` `^25.5.0`
- Allure package present: `3.3.1`

## Playwright Configuration
- Config file: `playwright.config.ts`
- Test directory: `./tests`
- Base URL: `http://localhost:5173` (override with `BASE_URL` env var)
- Browser projects:
  - `chromium` (Desktop Chrome)
  - `firefox` (Desktop Firefox)
- Reporter: `html`
- Trace: `on-first-retry`
- CI behavior:
  - retries: `2`
  - workers: `1`

## Current Framework Structure (POM)
- `pages/base.page.ts`
  - `BasePage`
  - Common utility: `navigate(path = '/')`
- `pages/home.page.ts`
  - `HomePage extends BasePage`
  - Encapsulates search input actions and assertions for home/search flow
- `tests/example.spec.ts`
  - Uses `HomePage`
  - Test case: `TC_001 - exact product name search returns only Wireless Headphones`

## Current Test Flow (TC_001)
1. Navigate to home page (`/`)
2. Log search input locator information
3. Search for product: `Wireless Headphones`
4. Validate `Showing 1 product(s)` is visible
5. Validate product heading `Wireless Headphones` is visible
6. Validate Add to Cart button count is `1`

## NPM Scripts
- Install browser binaries:
  - `npm run pw:install`
- Run all tests:
  - `npm test`
- Run in headed mode:
  - `npm run test:headed`
- Run Playwright UI mode:
  - `npm run test:ui`
- Open codegen:
  - `npm run codegen https://example.com`

## Useful Direct Command
- Run current spec in headed mode:
  - `npx playwright test tests/example.spec.ts --headed`

## Locator Guidance Used
Preferred locator priority for stability and readability:
1. `getByRole`
2. `getByLabel`
3. `getByTestId`
4. `getByPlaceholder` (used when no label/test id is available)

Current search input locator in POM:
- `page.getByRole('textbox', { name: 'Search products...' })`

## Next Migration Targets
When adding more tests, keep this pattern:
1. Add page/component classes under `pages/`
2. Keep assertions in page methods only when they represent page state contracts
3. Keep test data explicit in spec files unless reused, then move to constants/fixtures
4. Reuse `BasePage` for shared navigation/waits
