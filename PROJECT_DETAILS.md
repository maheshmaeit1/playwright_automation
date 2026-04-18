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
  - retries: `0`
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

---

## AI Test Healer Agent

### Location
```
healer/
└── healer_agent.py       # Python agent (entry point)
└── requirements.txt      # Python dependency: anthropic>=0.40.0
Jenkinsfile               # Jenkins CI/CD pipeline (project root)
```

### What it does
A Python agent that plugs into the Jenkins pipeline. When Playwright tests fail it:
1. Parses the Playwright JSON failure report (`test-results/results.json`)
2. Reads the failing test file and any imported page objects
3. Calls Claude AI (Anthropic SDK) with the error, stack trace, and source code
4. Receives a root-cause diagnosis + corrected file content
5. Backs up the original file and writes the fix in place
6. Jenkins then re-runs the suite to verify the fix and commits it

### Key classes
| Class | File | Responsibility |
|---|---|---|
| `PlaywrightReportParser` | `healer_agent.py` | Walks Playwright JSON report tree → `TestFailure` list |
| `PlaywrightTestHealer` | `healer_agent.py` | Orchestrates read → prompt → call Claude → patch |
| `TestFailure` | `healer_agent.py` | Dataclass: suite, title, file, error, stack trace |
| `HealingResult` | `healer_agent.py` | Dataclass: outcome, root cause, confidence, fix description |
| `HealingReport` | `healer_agent.py` | Dataclass serialised to `healing_report.json` |

### Claude prompt strategy
- **System prompt**: roles the model as a Playwright/TypeScript expert with strict rules (never remove assertions, prefer semantic locators, fix test code only)
- **User prompt**: injects test title, error message, stack trace, full test file source, and any imported page object sources
- **Response contract**: Claude must return a single JSON object with `root_cause`, `fix_description`, `fixed_code`, `confidence` (`high|medium|low`), and `requires_app_change`
- Fixes with `confidence=low` or `requires_app_change=true` are skipped — the healer logs them as unhealed

### Reporter change
`playwright.config.ts` was updated to emit a JSON report when `CI=true`:
```ts
reporter: [
  ['list'],
  ['html', { open: 'never' }],
  ...(process.env.CI ? [['json', { outputFile: 'test-results/results.json' }]] : [])
]
```

### Healer CLI
```bash
export ANTHROPIC_API_KEY=sk-ant-...

python3 healer/healer_agent.py \
  --report    test-results/results.json \
  --workspace . \
  --output    test-results/healing_report.json \
  [--dry-run] \
  [--model    claude-sonnet-4-6]
```

Exit codes: `0` = all healed, `1` = some unhealed, `2` = startup error.

### Jenkins pipeline stages
| Stage | Trigger condition |
|---|---|
| Checkout | always |
| Setup (Node + Python) | always |
| Test | always |
| Heal | test exit code ≠ 0 AND `SKIP_HEALING=false` |
| Re-run after healing | heal exit code = 0 AND `DRY_RUN=false` |
| Commit fixes | re-run exit code = 0 AND `DRY_RUN=false` |

Required Jenkins credential: **Secret Text** with ID `anthropic-api-key`.

### Dependency
```
anthropic>=0.40.0   # Anthropic Python SDK (healer/requirements.txt)
```
