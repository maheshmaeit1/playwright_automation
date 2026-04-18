# Playwright Automation Framework

## Supported automation layers

- UI automation through Playwright page objects
- API automation through reusable API clients
- Visual automation through screenshot assertions
- BDD coverage through Playwright BDD feature generation

## Project structure

- `pages/` page object classes
- `api/clients/` reusable API clients
- `fixtures/` shared Playwright fixtures
- `tests/ui/` UI functional specs
- `tests/api/` API specs
- `tests/visual_tests/` visual regression specs
- `features/` BDD feature files and step definitions

## Install dependencies and browsers

```bash
npm install
npm run pw:install
```

## Execution commands

```bash
npm run test:ui
npm run test:api
npm run test:visual
npm run test:bdd
npm run test:headed
npm run typecheck
```

## Run specific tests

### Run by file

```bash
npx playwright test tests/ui/search.spec.ts --project=ui
npx playwright test tests/api/payment.api.spec.ts --project=api
npx playwright test tests/visual_tests/search.visual.spec.ts --project=visual
```

### Run by file and line number

```bash
npx playwright test tests/ui/search.spec.ts:4 --project=ui
npx playwright test tests/api/payment.api.spec.ts:9 --project=api
```

### Run by test name

```bash
npx playwright test --grep "TC_001"
npx playwright test --project=api --grep "GET-05"
npx playwright test --project=visual --grep "VS_001"
```

### Run by project only

```bash
npx playwright test --project=ui
npx playwright test --project=api
npx playwright test --project=visual
npm run test:bdd
```

### Run BDD scenarios by feature file

Generate BDD specs first, then run the generated feature spec by file:

```bash
npm run bdd:generate
npx playwright test .features-gen/features/search.feature.spec.js --project=bdd
```

### Run by tag

For Playwright tests, use built-in tags in the test title or test details and filter with `--grep`.

Example:

```ts
test('TC_001 @smoke @ui exact product name search returns only Wireless Headphones', async ({ homePage }) => {
	// test body
});
```

Run tagged Playwright tests:

```bash
npx playwright test --grep "@smoke"
npx playwright test --project=ui --grep "@ui"
npx playwright test --project=api --grep "@contract"
```

For BDD scenarios, add tags above the feature or scenario in the `.feature` file:

```gherkin
@smoke @search
Scenario: Exact product name search returns only Wireless Headphones
```

Then regenerate and run with grep:

```bash
npm run bdd:generate
npx playwright test --project=bdd --grep "@smoke"
```

### Run headed or debug mode for a specific test

```bash
npx playwright test tests/ui/search.spec.ts --project=ui --headed
npx playwright test --project=visual --grep "VS_001" --debug
```

### Useful combinations

```bash
npx playwright test tests/ui/search.spec.ts --project=ui --grep "@smoke"
npx playwright test tests/api/payment.api.spec.ts:46 --project=api
npx playwright test --project=bdd --grep "Wireless Headphones"
```

## Visual regression workflow

```bash
npm run test:visual:update
npm run test:visual
npx playwright show-report
```

For detailed visual testing guidance, see [VISUAL_TESTING_GUIDE.md](VISUAL_TESTING_GUIDE.md).