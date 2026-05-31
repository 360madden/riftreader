#!/usr/bin/env python3
"""Tests for the timestamped validation ledger helper."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.riftreader_workflow import validation_ledger


REPO_ROOT = Path(__file__).resolve().parents[1]


class ValidationLedgerTests(unittest.TestCase):
    def run_ledger(self, *args: str) -> dict:
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        parser = validation_ledger.build_parser()
        namespace = parser.parse_args(["--repo-root", str(REPO_ROOT), "--output-root", tmp_dir.name, *args])
        summary = validation_ledger.run_validation(namespace)
        summary["_testOutputRoot"] = tmp_dir.name
        self.assertTrue(Path(summary["artifacts"]["summaryJson"]).is_file())
        self.assertTrue(Path(summary["artifacts"]["summaryMarkdown"]).is_file())
        return summary

    def command_json(self, **overrides) -> str:
        payload = {
            "label": "test-command",
            "phase": "unit-test",
            "args": [sys.executable, "-c", "print('hello-ledger')"],
            "timeoutSeconds": 10,
            "budgetSeconds": 60,
        }
        payload.update(overrides)
        return json.dumps(payload)

    def test_success_summary_schema_and_logs(self):
        summary = self.run_ledger("--tier", "custom", "--command-json", self.command_json())

        self.assertEqual(summary["schemaVersion"], 1)
        self.assertEqual(summary["kind"], validation_ledger.KIND)
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["tier"], "custom")
        self.assertIn("startedAtUtc", summary)
        self.assertIn("endedAtUtc", summary)
        self.assertGreaterEqual(summary["durationSeconds"], 0)
        self.assertIn("branch", summary["git"])
        self.assertFalse(summary["safety"]["gitMutation"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["inputSent"])

        command = summary["commands"][0]
        self.assertEqual(command["label"], "test-command")
        self.assertTrue(command["ok"])
        self.assertEqual(command["exitCode"], 0)
        self.assertGreaterEqual(command["durationSeconds"], 0)
        self.assertTrue(Path(command["stdoutPath"]).is_file())
        self.assertTrue(Path(command["stderrPath"]).is_file())
        self.assertIn("hello-ledger", command["stdoutPreview"])

    def test_nonzero_command_fails(self):
        summary = self.run_ledger(
            "--tier",
            "custom",
            "--command-json",
            self.command_json(args=[sys.executable, "-c", "import sys; sys.exit(7)"]),
        )

        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["commands"][0]["exitCode"], 7)
        self.assertFalse(summary["commands"][0]["ok"])
        self.assertTrue(summary["errors"])

    def test_timeout_records_timed_out_and_failed(self):
        summary = self.run_ledger(
            "--tier",
            "custom",
            "--heartbeat-seconds",
            "0.05",
            "--command-json",
            self.command_json(
                args=[sys.executable, "-c", "import time; time.sleep(1)"],
                timeoutSeconds=0.1,
            ),
        )

        self.assertEqual(summary["status"], "failed")
        self.assertTrue(summary["commands"][0]["timedOut"])
        self.assertFalse(summary["commands"][0]["ok"])

    def test_slow_success_warns_without_failure(self):
        summary = self.run_ledger(
            "--tier",
            "custom",
            "--command-json",
            self.command_json(
                args=[sys.executable, "-c", "import time; time.sleep(0.08); print('slow-ok')"],
                budgetSeconds=0.001,
            ),
        )

        self.assertEqual(summary["status"], "passed")
        self.assertTrue(summary["slowCommands"])
        self.assertTrue(any("slow-command" in warning for warning in summary["warnings"]))

    def test_enforced_budget_fails_slow_success(self):
        summary = self.run_ledger(
            "--tier",
            "custom",
            "--enforce-budget",
            "--command-json",
            self.command_json(
                args=[sys.executable, "-c", "import time; time.sleep(0.08); print('slow-fail')"],
                budgetSeconds=0.001,
            ),
        )

        self.assertEqual(summary["status"], "failed")
        self.assertTrue(summary["commands"][0]["budgetExceeded"])

    def test_markdown_contains_required_sections(self):
        summary = self.run_ledger("--tier", "custom", "--command-json", self.command_json())
        markdown = Path(summary["artifacts"]["summaryMarkdown"]).read_text(encoding="utf-8")

        self.assertIn("# RiftReader validation ledger", markdown)
        self.assertIn("## Timing summary", markdown)
        self.assertIn("## Slow commands", markdown)
        self.assertIn("## Failures", markdown)
        self.assertIn("## Artifacts", markdown)
        self.assertIn("## Next action", markdown)

    def test_missing_ci_prerequisite_blocks(self):
        summary = self.run_ledger(
            "--tier",
            "ci-parity",
            "--gh-executable",
            "definitely-missing-gh-for-validation-ledger-test",
            "--ci-timeout-seconds",
            "1",
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertTrue(summary["blockers"])
        self.assertTrue(summary["commands"][0]["blocked"])

    def test_command_string_is_supported_for_targeted(self):
        summary = self.run_ledger(
            "--tier",
            "targeted",
            "--command",
            f'"{sys.executable}" -c "print(123)"',
        )

        self.assertEqual(summary["status"], "passed")
        self.assertIn("123", summary["commands"][0]["stdoutPreview"])

    def test_self_test_report_passes(self):
        report = validation_ledger.run_self_test()

        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["safety"]["gitMutation"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
