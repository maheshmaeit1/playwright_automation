#!/usr/bin/env python3
"""
Playwright Test Healer Agent
AI-powered agent that analyzes Playwright test failures and automatically fixes them.
Designed to be invoked from Jenkins CI/CD pipelines.

Usage:
    python healer_agent.py --report test-results/results.json --workspace .
    python healer_agent.py --report results.json --workspace . --dry-run
"""

import json
import os
import re
import sys
import shlex
import shutil
import argparse
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("healer.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────

@dataclass
class TestFailure:
    suite_title: str
    test_title: str
    file_path: str
    error_message: str
    stack_trace: str
    retry_count: int = 0


@dataclass
class HealingResult:
    test_title: str
    file_path: str
    success: bool
    root_cause: str
    fix_description: str
    confidence: str = "unknown"
    requires_app_change: bool = False


@dataclass
class HealingReport:
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    workspace: str = ""
    dry_run: bool = False
    total_failures: int = 0
    healed: int = 0
    failed_to_heal: int = 0
    results: list = field(default_factory=list)


# ──────────────────────────────────────────────
# Report parser
# ──────────────────────────────────────────────

class PlaywrightReportParser:
    """Parses Playwright JSON reporter output into TestFailure objects."""

    def parse(self, report_path: str) -> list[TestFailure]:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)

        failures: list[TestFailure] = []
        for suite in report.get("suites", []):
            self._walk_suite(suite, failures, parent_title="")
        return failures

    def _walk_suite(self, suite: dict, failures: list, parent_title: str) -> None:
        suite_title = f"{parent_title} > {suite.get('title', '')}".strip(" >")

        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                if test.get("status") not in ("failed", "timedOut", "unexpected"):
                    continue
                for result in test.get("results", []):
                    if result.get("status") not in ("failed", "timedOut"):
                        continue
                    errors = result.get("errors", [{}])
                    err = errors[0] if errors else {}
                    failures.append(
                        TestFailure(
                            suite_title=suite_title,
                            test_title=spec.get("title", "unknown"),
                            file_path=spec.get("file", suite.get("file", "")),
                            error_message=err.get("message", ""),
                            stack_trace=err.get("stack", ""),
                            retry_count=result.get("retry", 0),
                        )
                    )

        for child in suite.get("suites", []):
            self._walk_suite(child, failures, suite_title)


# ──────────────────────────────────────────────
# Healer core
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert Playwright / TypeScript test automation engineer.
Your job is to diagnose failing tests and produce minimal, targeted fixes.

Rules:
- Fix only test code — never the application under test.
- Preserve all assertions; do not remove or weaken them.
- Prefer Playwright semantic locators: getByRole, getByLabel, getByTestId, getByPlaceholder.
- Add explicit waits (waitFor, expect(...).toBeVisible) only when timing is the root cause.
- Return a single valid JSON object — no markdown fences, no extra text.
"""

FIX_PROMPT_TEMPLATE = """\
A Playwright test is failing. Diagnose the root cause and provide the corrected file.

## Failure details
Test:  {test_title}
Suite: {suite_title}
File:  {file_path}

### Error message
{error_message}

### Stack trace
{stack_trace}

## Current test file
```typescript
{test_content}
```
{page_objects_section}
## Required JSON response (no markdown, no extra text)
{{
  "root_cause": "<one-sentence explanation>",
  "fix_description": "<what you changed and why>",
  "fixed_code": "<complete corrected file content>",
  "confidence": "high|medium|low",
  "requires_app_change": false
}}

If you cannot determine a reliable fix, set confidence to "low" and leave fixed_code empty.
"""


class PlaywrightTestHealer:
    def __init__(
        self,
        workspace: str,
        dry_run: bool = False,
        model: str = "github-copilot",
        max_tokens: int = 8096,
        cli_command: str = "copilot",
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.dry_run = dry_run
        self.model = model
        self.max_tokens = max_tokens
        self.cli_command = cli_command
        self._results: list[HealingResult] = []

    # ── file helpers ──────────────────────────

    def _read(self, path: str) -> str:
        for candidate in (
            self.workspace / path,
            (self.workspace / "tests" / path).resolve(),
            Path(path),
        ):
            try:
                if candidate.exists():
                    return candidate.read_text(encoding="utf-8")
            except Exception:
                pass
        return ""

    def _page_objects(self, test_src: str) -> dict[str, str]:
        objects: dict[str, str] = {}
        for imp in re.findall(r"from\s+['\"](\.[^'\"]+)['\"]", test_src):
            for ext in (".ts", ".js", ".tsx", ".jsx"):
                candidate = self.workspace / f"{imp}{ext}"
                if candidate.exists():
                    objects[imp] = candidate.read_text(encoding="utf-8")
                    break
        return objects

    # ── prompt builder ────────────────────────

    def _build_prompt(self, failure: TestFailure, test_src: str) -> str:
        page_objects = self._page_objects(test_src)
        po_section = ""
        for path, content in page_objects.items():
            po_section += f"\n## Page object: {path}\n```typescript\n{content}\n```\n"

        return FIX_PROMPT_TEMPLATE.format(
            test_title=failure.test_title,
            suite_title=failure.suite_title,
            file_path=failure.file_path,
            error_message=failure.error_message or "(none)",
            stack_trace=failure.stack_trace or "(none)",
            test_content=test_src,
            page_objects_section=po_section,
        )

    # ── Copilot CLI call ──────────────────────

    def _call_copilot(self, prompt: str) -> dict:
        full_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Model hint: {self.model}. "
            f"Return only the requested JSON object.\n\n"
            f"{prompt}"
        )

        cmd = shlex.split(self.cli_command, posix=os.name != "nt")
        executable = cmd[0] if cmd else "copilot"
        if shutil.which(executable) is None:
            raise FileNotFoundError(
                f"Copilot CLI was not found on PATH: {executable}. "
                "Install/sign in to GitHub Copilot CLI or set COPILOT_CLI_COMMAND."
            )

        response = subprocess.run(
            [
                *cmd,
                f"--prompt={full_prompt}",
                "--silent",
                "--output-format",
                "text",
            ],
            cwd=str(self.workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )

        if response.returncode != 0:
            stderr = (response.stderr or response.stdout or "").strip()
            raise RuntimeError(
                f"Copilot CLI failed with exit code {response.returncode}: {stderr}"
            )

        raw = (response.stdout or "").strip()
        if not raw:
            raise RuntimeError("Copilot CLI returned an empty response.")

        # Strip accidental markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON object from text
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            raise

    # ── fix application ───────────────────────

    def _apply_fix(self, failure: TestFailure, fixed_code: str) -> bool:
        if not fixed_code.strip():
            return False

        for candidate in (
            self.workspace / failure.file_path,
            (self.workspace / "tests" / failure.file_path).resolve(),
            Path(failure.file_path),
        ):
            if candidate.exists():
                target = candidate
                break
        else:
            logger.warning("Cannot locate file to patch: %s", failure.file_path)
            return False

        if self.dry_run:
            logger.info("[DRY-RUN] Would patch: %s", target)
            return True

        backup = target.with_suffix(
            f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}{target.suffix}"
        )
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")

        target.write_text(fixed_code, encoding="utf-8")
        logger.info("Patched: %s  (backup: %s)", target, backup.name)
        return True

    # ── public API ────────────────────────────

    def heal(self, failure: TestFailure) -> HealingResult:
        logger.info("--- Healing: %s", failure.test_title)
        test_src = self._read(failure.file_path)
        if not test_src:
            result = HealingResult(
                test_title=failure.test_title,
                file_path=failure.file_path,
                success=False,
                root_cause="Could not read test file",
                fix_description="",
            )
            self._results.append(result)
            return result

        prompt = self._build_prompt(failure, test_src)

        try:
            analysis = self._call_copilot(prompt)
        except Exception as exc:
            logger.error("Copilot CLI error: %s", exc)
            result = HealingResult(
                test_title=failure.test_title,
                file_path=failure.file_path,
                success=False,
                root_cause=f"Copilot CLI error: {exc}",
                fix_description="",
            )
            self._results.append(result)
            return result

        root_cause = analysis.get("root_cause", "")
        fix_desc = analysis.get("fix_description", "")
        confidence = analysis.get("confidence", "low")
        requires_app = analysis.get("requires_app_change", False)
        fixed_code = analysis.get("fixed_code", "")

        logger.info("Root cause : %s", root_cause)
        logger.info("Confidence : %s", confidence)
        if requires_app:
            logger.warning("Requires app-level change — skipping auto-fix")

        success = False
        if confidence != "low" and not requires_app:
            success = self._apply_fix(failure, fixed_code)

        result = HealingResult(
            test_title=failure.test_title,
            file_path=failure.file_path,
            success=success,
            root_cause=root_cause,
            fix_description=fix_desc,
            confidence=confidence,
            requires_app_change=requires_app,
        )
        self._results.append(result)
        return result

    def heal_report(self, report_path: str) -> list[HealingResult]:
        failures = PlaywrightReportParser().parse(report_path)
        if not failures:
            logger.info("No failures found in report — nothing to heal.")
            return []

        logger.info("Found %d failure(s) to process.", len(failures))
        for f in failures:
            self.heal(f)
        return self._results

    def write_summary(self, output_path: str = "healing_report.json") -> HealingReport:
        report = HealingReport(
            workspace=str(self.workspace),
            dry_run=self.dry_run,
            total_failures=len(self._results),
            healed=sum(1 for r in self._results if r.success),
            failed_to_heal=sum(1 for r in self._results if not r.success),
            results=[
                {
                    "test_title": r.test_title,
                    "file_path": r.file_path,
                    "healed": r.success,
                    "confidence": r.confidence,
                    "root_cause": r.root_cause,
                    "fix_description": r.fix_description,
                    "requires_app_change": r.requires_app_change,
                }
                for r in self._results
            ],
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.__dict__, f, indent=2)

        # ── console summary ──
        sep = "=" * 62
        print(f"\n{sep}")
        print("  HEALER SUMMARY")
        print(sep)
        print(f"  Total failures : {report.total_failures}")
        print(f"  Healed         : {report.healed}")
        print(f"  Could not heal : {report.failed_to_heal}")
        print(f"  Dry-run mode   : {report.dry_run}")
        print(sep)
        for r in self._results:
            tag = "✓ HEALED  " if r.success else "✗ UNHEALED"
            print(f"\n  [{tag}] {r.test_title}")
            print(f"    File       : {r.file_path}")
            print(f"    Root cause : {r.root_cause}")
            if r.fix_description:
                print(f"    Fix        : {r.fix_description}")
        print(f"\n{sep}\n")

        self._write_html_summary(report, output_path)
        return report

    def _write_html_summary(self, report: HealingReport, json_path: str) -> None:
        html_path = Path(json_path).with_suffix(".html")
        rows = ""
        for r in report.results:
            status_color = "#2ecc71" if r["healed"] else "#e74c3c"
            status_text = "HEALED" if r["healed"] else "UNHEALED"
            rows += f"""
            <tr>
                <td style="color:{status_color};font-weight:bold">{status_text}</td>
                <td>{r["test_title"]}</td>
                <td><code>{r["file_path"]}</code></td>
                <td>{r["root_cause"]}</td>
                <td>{r.get("fix_description","")}</td>
                <td>{r.get("confidence","")}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Healing Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; background: #f9f9f9; }}
    h1 {{ color: #333; }}
    .summary {{ display:flex; gap:32px; margin-bottom:24px; }}
    .card {{ background:#fff; border-radius:8px; padding:16px 24px; box-shadow:0 1px 4px rgba(0,0,0,.1); text-align:center; }}
    .card .num {{ font-size:2em; font-weight:bold; }}
    .total {{ color:#3498db; }} .healed {{ color:#2ecc71; }} .unhealed {{ color:#e74c3c; }}
    table {{ border-collapse:collapse; width:100%; background:#fff; box-shadow:0 1px 4px rgba(0,0,0,.1); border-radius:8px; overflow:hidden; }}
    th {{ background:#3498db; color:#fff; padding:10px 14px; text-align:left; }}
    td {{ padding:10px 14px; border-bottom:1px solid #eee; vertical-align:top; }}
    tr:last-child td {{ border-bottom:none; }}
    code {{ background:#eee; padding:2px 4px; border-radius:3px; font-size:.9em; }}
  </style>
</head>
<body>
  <h1>AI Healer Report</h1>
  <p>Generated: {report.timestamp} | Dry-run: {report.dry_run}</p>
  <div class="summary">
    <div class="card"><div class="num total">{report.total_failures}</div>Total Failures</div>
    <div class="card"><div class="num healed">{report.healed}</div>Healed</div>
    <div class="card"><div class="num unhealed">{report.failed_to_heal}</div>Unhealed</div>
  </div>
  <table>
    <tr><th>Status</th><th>Test</th><th>File</th><th>Root Cause</th><th>Fix Applied</th><th>Confidence</th></tr>
    {rows}
  </table>
</body>
</html>"""
        html_path.write_text(html, encoding="utf-8")
        logger.info("HTML report written to %s", html_path)


# ──────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Playwright Test Healer — AI-powered test failure fixer"
    )
    p.add_argument("--report", required=True, help="Path to Playwright JSON report")
    p.add_argument("--workspace", default=".", help="Project root directory")
    p.add_argument("--output", default="healing_report.json", help="Where to write the healing report")
    p.add_argument("--model", default="github-copilot", help="Optional Copilot model hint")
    p.add_argument(
        "--copilot-command",
        default=os.environ.get("COPILOT_CLI_COMMAND", "copilot"),
        help="Copilot CLI command to use",
    )
    p.add_argument("--dry-run", action="store_true", help="Analyse only; do not write fixes")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    cmd = shlex.split(args.copilot_command, posix=os.name != "nt")
    executable = cmd[0] if cmd else "copilot"
    if shutil.which(executable) is None:
        logger.error(
            "Copilot CLI is not available on PATH. Install/sign in to GitHub Copilot CLI or set COPILOT_CLI_COMMAND."
        )
        sys.exit(2)

    healer = PlaywrightTestHealer(
        workspace=args.workspace,
        dry_run=args.dry_run,
        model=args.model,
        cli_command=args.copilot_command,
    )

    healer.heal_report(args.report)
    report = healer.write_summary(args.output)

    # Non-zero exit when there are unhealed failures so Jenkins can react
    sys.exit(0 if report.failed_to_heal == 0 else 1)


if __name__ == "__main__":
    main()
