#!/usr/bin/env python3
"""
Playwright Test Healer Agent
Usage:
    python healer_agent.py --report test-results/results.json --workspace .
    python healer_agent.py --report results.json --workspace . --dry-run
"""

import json
import os
import re
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

from models import TestFailure, HealingResult, HealingReport
from copilot_client import resolve_cli_command, call_copilot, call_agent
from prompts import build_prompt, build_agent_prompt
from reporter import write_summary, PlaywrightReportParser
from test_runner import run_test, get_failures_from_run

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
# Healer
# ──────────────────────────────────────────────

class PlaywrightTestHealer:
    def __init__(self, workspace: str, dry_run: bool = False, model: str = "github-copilot",
                 max_tokens: int = 8096, cli_command: str = "copilot") -> None:
        self.workspace = Path(workspace).resolve()
        self.dry_run = dry_run
        self.model = model
        self.max_tokens = max_tokens
        self.cli_command = cli_command
        self._results: list[HealingResult] = []

    # ── file helpers ──────────────────────────

    def _read(self, path: str) -> str:
        """Try a few candidate locations and return the file content."""
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
        """Find and read any page-object files imported by the test."""
        objects: dict[str, str] = {}
        for imp in re.findall(r"from\s+['\"](\.[^'\"]+)['\"]", test_src):
            for ext in (".ts", ".js", ".tsx", ".jsx"):
                candidate = self.workspace / f"{imp}{ext}"
                if candidate.exists():
                    objects[imp] = candidate.read_text(encoding="utf-8")
                    break
        return objects

    def _apply_fix(self, failure: TestFailure, fixed_code: str) -> bool:
        """Write the fixed code to disk (with a timestamped backup)."""
        if not fixed_code.strip():
            return False

        target = None
        for candidate in (
            self.workspace / failure.file_path,
            (self.workspace / "tests" / failure.file_path).resolve(),
            Path(failure.file_path),
        ):
            if candidate.exists():
                target = candidate
                break

        if target is None:
            logger.warning("Cannot locate file to patch: %s", failure.file_path)
            return False

        if self.dry_run:
            logger.info("[DRY-RUN] Would patch: %s", target)
            return True

        backup = target.with_suffix(f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}{target.suffix}")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        target.write_text(fixed_code, encoding="utf-8")
        logger.info("Patched: %s  (backup: %s)", target, backup.name)
        return True

    # ── public API ────────────────────────────

    def heal_via_agent(self, failure: TestFailure) -> HealingResult:
        """Invoke the playwright-test-healer Copilot agent directly.

        The agent uses MCP tools (test_run, test_debug, browser_snapshot, edit, search)
        to autonomously run → debug → edit → verify the test.  It handles the full
        heal-run-retry cycle internally, so no JSON parsing or manual _apply_fix needed.
        """
        logger.info("--- [Agent] Healing: %s", failure.test_title)

        if self.dry_run:
            logger.info("[DRY-RUN] Would invoke playwright-test-healer agent for: %s", failure.file_path)
            result = HealingResult(test_title=failure.test_title, file_path=failure.file_path,
                                   success=True, root_cause="[DRY-RUN]", fix_description="[DRY-RUN]")
            self._results.append(result)
            return result

        prompt = build_agent_prompt(failure)

        try:
            output = call_agent("playwright-test-healer", prompt, self.cli_command, str(self.workspace))
        except Exception as exc:
            logger.error("Agent invocation error: %s", exc)
            result = HealingResult(test_title=failure.test_title, file_path=failure.file_path,
                                   success=False, root_cause=f"Agent error: {exc}", fix_description="")
            self._results.append(result)
            return result

        logger.info("Agent output (first 500 chars):\n%s", output[:500])

        # The agent edits files directly — infer success from its output text
        out_lower = output.lower()
        success = (
            "passed" in out_lower
            or "fixed" in out_lower
            or "test.fixme" in out_lower
            or "fixme" in out_lower
            or "resolved" in out_lower
            or "successfully" in out_lower
        )

        result = HealingResult(
            test_title=failure.test_title,
            file_path=failure.file_path,
            success=success,
            root_cause="Diagnosed and fixed by playwright-test-healer agent",
            fix_description=output[:1000],
            confidence="high" if success else "low",
        )
        self._results.append(result)
        return result

    def heal(self, failure: TestFailure) -> HealingResult:
        logger.info("--- Healing: %s", failure.test_title)

        test_src = self._read(failure.file_path)
        if not test_src:
            result = HealingResult(test_title=failure.test_title, file_path=failure.file_path,
                                   success=False, root_cause="Could not read test file", fix_description="")
            self._results.append(result)
            return result

        prompt = build_prompt(failure, test_src, self._page_objects(test_src), self.model)

        try:
            analysis = call_copilot(prompt, self.model, self.max_tokens, self.cli_command, str(self.workspace))
        except Exception as exc:
            logger.error("Copilot CLI error: %s", exc)
            result = HealingResult(test_title=failure.test_title, file_path=failure.file_path,
                                   success=False, root_cause=f"Copilot CLI error: {exc}", fix_description="")
            self._results.append(result)
            return result

        root_cause   = analysis.get("root_cause", "")
        fix_desc     = analysis.get("fix_description", "")
        confidence   = analysis.get("confidence", "low")
        requires_app = analysis.get("requires_app_change", False)
        fixed_code   = analysis.get("fixed_code", "")

        logger.info("Root cause : %s", root_cause)
        logger.info("Confidence : %s", confidence)
        if requires_app:
            logger.warning("Requires app-level change — skipping auto-fix")

        success = False
        if confidence != "low" and not requires_app:
            success = self._apply_fix(failure, fixed_code)

        result = HealingResult(test_title=failure.test_title, file_path=failure.file_path,
                               success=success, root_cause=root_cause, fix_description=fix_desc,
                               confidence=confidence, requires_app_change=requires_app)
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

    def heal_with_retry(self, report_path: str, max_retries: int = 2) -> list[HealingResult]:
        """
        Full heal-run-retry loop:
        1. Heal all failures from the initial report.
        2. Run each fixed test file with the Playwright MCP (npx playwright test).
        3. If the test still fails, heal again using the new error — up to max_retries times.
        """
        failures = PlaywrightReportParser().parse(report_path)
        if not failures:
            logger.info("No failures found in report — nothing to heal.")
            return []

        logger.info("Found %d failure(s). Starting heal-run-retry loop (max %d retries).",
                    len(failures), max_retries)

        for failure in failures:
            attempt = 0
            current_failure = failure

            while attempt <= max_retries:
                logger.info("=== Attempt %d/%d for: %s ===",
                            attempt + 1, max_retries + 1, current_failure.test_title)

                # Step 1 — Heal
                result = self.heal(current_failure)

                if not result.success:
                    logger.warning("Heal did not apply a fix — stopping retries for this test.")
                    break

                if self.dry_run:
                    logger.info("[DRY-RUN] Skipping test execution.")
                    break

                # Step 2 — Run the test via Playwright MCP
                passed, run_report = run_test(current_failure.file_path, str(self.workspace))

                if passed:
                    logger.info("Test PASSED after heal — done: %s", current_failure.test_title)
                    # Mark the last result as verified-passing
                    result.fix_description += " [verified passing]"
                    break

                attempt += 1
                if attempt > max_retries:
                    logger.warning("Test still failing after %d retries: %s",
                                   max_retries, current_failure.test_title)
                    break

                # Step 3 — Build an updated failure from the new run output
                new_failures = get_failures_from_run(run_report)
                if new_failures:
                    f = new_failures[0]
                    current_failure = TestFailure(
                        suite_title=f["suite_title"],
                        test_title=f["test_title"],
                        file_path=f["file_path"],
                        error_message=f["error_message"],
                        stack_trace=f["stack_trace"],
                        retry_count=attempt,
                    )
                else:
                    logger.warning("Could not read retry report — stopping retries.")
                    break

        return self._results

    def write_summary(self, output_path: str = "healing_report.json") -> HealingReport:
        return write_summary(self._results, str(self.workspace), self.dry_run, output_path)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Playwright Test Healer — AI-powered test failure fixer")
    p.add_argument("--report",          required=True,  help="Path to Playwright JSON report")
    p.add_argument("--workspace",       default=".",    help="Project root directory")
    p.add_argument("--output",          default="healing_report.json", help="Where to write the healing report")
    p.add_argument("--model",           default="github-copilot",      help="Copilot model hint")
    p.add_argument("--copilot-command", default=os.environ.get("COPILOT_CLI_COMMAND", "copilot"),
                   help="Copilot CLI command to use")
    p.add_argument("--dry-run",         action="store_true", help="Analyse only; do not write fixes")
    p.add_argument("--retry",           type=int, default=0, metavar="N",
                   help="After healing, run the test and re-heal up to N times if still failing (default: 0)")
    p.add_argument("--no-agent",        action="store_true",
                   help="Disable direct playwright-test-healer agent mode and use legacy JSON prompt mode. "
                        "By default, the healer now invokes the agent directly on every run.")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    try:
        resolve_cli_command(args.copilot_command)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        sys.exit(2)

    healer = PlaywrightTestHealer(
        workspace=args.workspace,
        dry_run=args.dry_run,
        model=args.model,
        cli_command=args.copilot_command,
    )

    use_agent = not args.no_agent

    if use_agent:
        if args.retry > 0:
            logger.info("--retry=%d ignored in agent mode; the agent handles its own iteration.", args.retry)
        failures = PlaywrightReportParser().parse(args.report)
        if not failures:
            logger.info("No failures found in report — nothing to heal.")
        else:
            logger.info("Found %d failure(s). Invoking playwright-test-healer agent.", len(failures))
            for f in failures:
                healer.heal_via_agent(f)
    elif args.retry > 0:
        healer.heal_with_retry(args.report, max_retries=args.retry)
    else:
        healer.heal_report(args.report)

    report = healer.write_summary(args.output)

    sys.exit(0 if report.failed_to_heal == 0 else 1)


if __name__ == "__main__":
    main()
