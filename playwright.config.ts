import { defineConfig, devices } from '@playwright/test';
import { defineBddConfig } from 'playwright-bdd';

const bddTestDir = defineBddConfig({
  features: 'features/**/*.feature',
  steps: ['features/steps/**/*.ts'],
  outputDir: '.features-gen'
});

export default defineConfig({
  testDir: './tests',
  testIgnore: ['**/*-snapshots/**'],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 30_000,
  outputDir: 'test-results/artifacts',
  expect: {
    timeout: 10_000,
    toHaveScreenshot: {
      animations: 'disabled',
      caret: 'hide'
    }
  },
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'test-results/results.json' }]
  ],
  use: {
    headless: true,
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
    baseURL: process.env.BASE_URL || 'http://localhost:5173'
  },
  projects: [
    {
      name: 'ui',
      testDir: './tests/ui',
      testMatch: '**/*.spec.ts',
      use: {
        ...devices['Desktop Chrome']
      }
    },
    {
      name: 'bdd',
      testDir: bddTestDir,
      testMatch: '**/*.spec.js',
      use: {
        ...devices['Desktop Chrome']
      }
    },
    {
      name: 'visual',
      testDir: './tests/visual_tests',
      testMatch: '**/*.spec.ts',
      use: {
        ...devices['Desktop Chrome']
      }
    },
    {
      name: 'api',
      testDir: './tests/api',
      testMatch: '**/*.spec.ts',
      use: {
        baseURL: process.env.API_BASE_URL || 'http://localhost:3000'
      }
    }
  ]
});
