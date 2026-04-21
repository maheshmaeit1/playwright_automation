# Healer Agent Quick Start

## What Changed?
The healer agent now fixes **simple locator issues instantly** without waiting 180 seconds for Copilot.

## Quick Usage

### Run the healer
```bash
cd playwright_automation
python healer/healer_agent.py --report test-results/results.json --workspace .
```

### Expected Output
```
2026-04-21 19:38:11 [INFO] Found 1 failure(s) to process.
2026-04-21 19:38:11 [INFO] --- Healing: Search results display - verify product information
2026-04-21 19:38:11 [INFO]   Attempting local analysis for common patterns...
2026-04-21 19:38:11 [INFO]   Local analyzer: Detected element not found - element(s) not found
2026-04-21 19:38:11 [INFO]   Local analyzer: Suggesting locator change from getByRole to getByText
2026-04-21 19:38:11 [INFO] Root cause : Locator element(s) not found - element may not be a heading
2026-04-21 19:38:11 [INFO] Confidence : medium
2026-04-21 19:38:11 [INFO] Patched: tests/ui/search-functionality.spec.ts

============================================================
  HEALER SUMMARY
============================================================
  Total failures : 1
  Healed         : 1
  Could not heal : 0
  Dry-run mode   : False
============================================================

  [✓ HEALED  ] Search results display - verify product information
    File       : tests/ui/search-functionality.spec.ts
    Root cause : Locator element(s) not found - element may not be a heading
    Fix        : Changed getByRole('heading', { name: 'Portable Charger 123' }) to getByText('Portable Charger 123') for more flexible matching

============================================================
```

## Specific Fix Example

### Problem
Test was looking for: `getByRole('heading', { name: 'Portable Charger 123' })`
But it wasn't found on the page.

### Auto-Fixed To
Test now looks for: `getByText('Portable Charger 123')`

This is more flexible because:
- ✅ Doesn't assume the element is a heading
- ✅ Works with any element containing that text
- ✅ Less brittle to UI structure changes

## Advanced Options

### Change Copilot timeout (if Copilot is slow)
```bash
# 2 minute timeout (for slow networks)
python healer/healer_agent.py \
  --report test-results/results.json \
  --workspace . \
  --copilot-timeout 120
```

### Test without applying fixes
```bash
python healer/healer_agent.py \
  --report test-results/results.json \
  --workspace . \
  --dry-run
```

### Save to custom report location
```bash
python healer/healer_agent.py \
  --report test-results/results.json \
  --workspace . \
  --output custom_healing_report.json
```

## Key Improvements

| Feature | Before | After |
|---------|--------|-------|
| Simple locator fix | 180s timeout ❌ | <100ms ✓ |
| Timeout handling | None | Graceful fallback ✓ |
| Local fixes | None | Yes ✓ |
| Copilot timeout | 180s | 60s (configurable) |

## Backup Files
When a fix is applied, the original test file is backed up:
```
tests/ui/search-functionality.spec.ts
tests/ui/search-functionality.spec.ts.bak_20260421_193811.ts  ← Backup
```

## Reports
- **JSON Report**: `test-results/healing_report.json` (detailed results)
- **HTML Report**: `test-results/healing_report.html` (visual summary)

## Tips
1. Always run `--dry-run` first if unsure
2. Check the generated HTML report for visual summary
3. Review backups if needed - files are preserved
4. Increase `--copilot-timeout` if network is unreliable
