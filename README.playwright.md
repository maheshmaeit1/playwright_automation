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

---

## AI Test Healer

The healer is a Python agent (`healer/healer_agent.py`) that reads a Playwright JSON failure report, sends each failing test to the GitHub Copilot CLI for diagnosis, and automatically patches the test file with the fix.

### How it works

```
Run tests → JSON report → Healer Agent → GitHub Copilot CLI → Patched test file → Re-run
```

1. Playwright runs and writes `test-results/results.json`
2. The healer reads every failed test from that report
3. For each failure it sends the test file + error + page objects to the GitHub Copilot CLI
4. Copilot returns a root cause analysis and corrected file content
5. The healer writes the fix and (in CI) re-runs the suite to verify

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or later |
| GitHub Copilot CLI | installed and signed in |
| Optional env var `COPILOT_CLI_COMMAND` | override the CLI command if needed |

Install the Python dependency:

```bash
pip install -r healer/requirements.txt
```

### Run the healer locally

**Step 1 — run tests and capture the JSON report**

```bash
# Set CI=true so playwright.config.ts enables the JSON reporter
CI=true npx playwright test --reporter=json --output=test-results/results.json
```

Alternatively, pass the reporter flag directly:

```bash
npx playwright test --reporter=json > test-results/results.json
```

**Step 2 — verify the Copilot CLI is available**

```bash
copilot --version
```

If you need a custom command, set:

```bash
export COPILOT_CLI_COMMAND="copilot"
```

**Step 3 — run the healer**

```bash
python3 healer/healer_agent.py \
  --report    test-results/results.json \
  --workspace . \
  --output    test-results/healing_report.json
```

**Step 4 — review the output**

The healer prints a summary table to stdout:

```
══════════════════════════════════════════════════════════════
  HEALER SUMMARY
══════════════════════════════════════════════════════════════
  Total failures : 3
  Healed         : 2
  Could not heal : 1
══════════════════════════════════════════════════════════════

  [✓ HEALED  ] Basic search functionality - find specific product
    File       : tests/ui/search-functionality.spec.ts
    Root cause : Locator changed from role=heading to role=link
    Fix        : Updated getByRole call to match current DOM

  [✗ UNHEALED] Visual snapshot mismatch
    File       : tests/visual_tests/home.visual.spec.ts
    Root cause : Screenshot baseline is outdated — requires manual update
```

A machine-readable `healing_report.json` is also written.

**Step 5 — re-run to verify**

```bash
npx playwright test
```

### Healer CLI options

| Flag | Default | Description |
|---|---|---|
| `--report` | *(required)* | Path to Playwright JSON report |
| `--workspace` | `.` | Project root directory |
| `--output` | `healing_report.json` | Where to write the healing summary |
| `--model` | `github-copilot` | Optional model hint for the prompt |
| `--copilot-command` | `copilot` | Override the Copilot CLI command |
| `--dry-run` | off | Analyse failures but do not write any file changes |

### Dry-run mode

Use `--dry-run` to see what the healer would do without touching any files:

```bash
python3 healer/healer_agent.py \
  --report test-results/results.json \
  --workspace . \
  --dry-run
```

---

## Jenkins Pipeline

The `Jenkinsfile` at the project root defines a full CI pipeline that runs tests and automatically invokes the healer on failures.

### Pipeline stages

| Stage | What it does |
|---|---|
| **Checkout** | Clones the repository |
| **Setup** | Installs Node deps, Playwright browsers, and verifies the Copilot CLI is available |
| **Test** | Runs the full Playwright suite and writes `test-results/results.json` |
| **Heal** | Invokes `healer_agent.py` when there are failures |
| **Re-run** | Re-runs the suite after healing to verify the fixes work |
| **Commit fixes** | Commits and pushes the patched test files back to the branch |

### Jenkins setup — step by step

**Step 1 — ensure the Jenkins agent has the Copilot CLI installed and signed in**

1. Install the GitHub Copilot CLI on the Jenkins worker
2. Sign in once on that agent so non-interactive prompts are allowed
3. Verify it with `copilot --version`

**Step 2 — create a Pipeline job**

1. New Item → **Pipeline**
2. Under **Pipeline**, choose `Pipeline script from SCM`
3. SCM: `Git`, enter your repository URL
4. Branch: `*/main` (or your target branch)
5. Script Path: `Jenkinsfile`
6. Save

**Step 3 — configure the agent**

The `Jenkinsfile` uses `agent any`. Ensure the Jenkins node where the job runs has:
- Node.js 18 or later (with `npm`)
- Python 3.10 or later (with `pip3`)
- Chromium dependencies (`npx playwright install --with-deps chromium` handles this)

**Step 4 — trigger a build**

Click **Build with Parameters**. Available parameters:

| Parameter | Default | Description |
|---|---|---|
| `DRY_RUN` | false | Analyse failures, do not write fixes |
| `SKIP_HEALING` | false | Skip Heal + Re-run stages entirely |
| `TEST_GREP` | *(empty)* | Filter tests by title, e.g. `search` |

**Step 5 — review results**

- **Playwright Report (initial run)** — HTML report published before healing
- **Playwright Report (after healing)** — HTML report published after re-run
- **healing_report.json** — archived artifact with per-test healing details
- **Build description** — Jenkins build page shows `Failures: N | Healed: M | Unhealed: K`

### Pipeline behaviour at a glance

```
All tests pass
  └─ Pipeline succeeds. Heal / Re-run / Commit stages are skipped.

Some tests fail, healer fixes all of them
  └─ Re-run passes → healed files are committed → pipeline succeeds.

Some tests fail, healer fixes some but not all
  └─ Re-run still has failures → pipeline fails with a clear message.
      Manual intervention required for the unhealed tests.

SKIP_HEALING=true
  └─ Pipeline fails immediately when tests fail (no healing attempted).

DRY_RUN=true
  └─ Healer analyses and logs but writes nothing → Re-run / Commit are skipped.
```

### Exit codes

The healer script uses standard exit codes so Jenkins can react:

| Exit code | Meaning |
|---|---|
| `0` | All failures were healed |
| `1` | One or more failures could not be healed |
| `2` | Startup error (missing API key, bad arguments) |