from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.riftscan_validation import (
    build_latest_pointer,
    build_validation_steps,
    dry_run_summary,
    markdown_for_summary,
    validate_milestone_stdout,
    validate_riftscan_status,
    write_latest_pointer,
    write_markdown_summary,
    write_summary,
)


class RiftScanValidationTests(unittest.TestCase):
    def test_default_steps_are_argument_lists_and_preserve_readonly_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            steps = build_validation_steps(
                repo_root=root,
                riftscan_root=riftscan,
                process_id=33912,
                target_window_handle="0xE0DB2",
                process_name="rift_x64",
                include_pwsh=False,
                quick=True,
            )

            self.assertGreater(len(steps), 5)
            for step in steps:
                self.assertIsInstance(step.command, list)
                self.assertTrue(step.command)
                self.assertNotIn("&", step.command)
                self.assertNotIn("|", step.command)

            milestone = next(step for step in steps if step.kind == "milestone-json")
            self.assertIn("--riftscan-root", milestone.command)
            self.assertIn(str(riftscan), milestone.command)
            self.assertIn("--pid", milestone.command)
            self.assertIn("33912", milestone.command)
            self.assertIn("--hwnd", milestone.command)
            self.assertIn("0xE0DB2", milestone.command)
            self.assertIn("--compact-json", milestone.command)
            self.assertNotIn("--write-summary", milestone.command)
            self.assertNotIn("--write-markdown", milestone.command)

            riftscan_status = steps[-1]
            self.assertEqual(riftscan_status.kind, "riftscan-status-clean")
            self.assertEqual(riftscan_status.command[:3], ["git", "-C", str(riftscan)])

    def test_validate_milestone_stdout_accepts_ready_or_safe_blocked_no_movement(self) -> None:
        payload = {
            "status": "ready-for-read-only-proof",
            "strategy": {
                "decision": "proceed-read-only-proof-first",
                "movementAllowedByReview": False,
                "readOnlyProofAllowedByReview": True,
            },
            "riftScanBoundary": {
                "writeAllowed": False,
                "noCheatEngine": True,
            },
        }

        ok, detail = validate_milestone_stdout(json.dumps(payload))
        self.assertTrue(ok, detail)
        self.assertEqual(detail, "ready-for-read-only-proof")

        payload["status"] = "blocked"
        payload["strategy"] = {
            "decision": "block",
            "movementAllowedByReview": False,
            "readOnlyProofAllowedByReview": False,
        }
        ok, detail = validate_milestone_stdout(json.dumps(payload))
        self.assertTrue(ok, detail)
        self.assertEqual(detail, "safe-blocked")

        payload["strategy"]["movementAllowedByReview"] = True
        ok, detail = validate_milestone_stdout(json.dumps(payload))
        self.assertFalse(ok)
        self.assertIn("allowed movement", detail)

    def test_validate_riftscan_status_requires_clean_provider_tree(self) -> None:
        ok, detail = validate_riftscan_status("## main...origin/main\n")
        self.assertTrue(ok, detail)

        ok, detail = validate_riftscan_status("## main...origin/main\n M reports/generated/file.json\n")
        self.assertFalse(ok)
        self.assertIn("not clean", detail)

    def test_dry_run_summary_records_no_live_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            steps = build_validation_steps(
                repo_root=root,
                riftscan_root=riftscan,
                process_id=33912,
                target_window_handle="0xE0DB2",
                include_pwsh=False,
                quick=True,
            )
            summary = dry_run_summary(steps)

            self.assertEqual(summary["status"], "dry-run")
            self.assertTrue(summary["noCheatEngine"])
            self.assertFalse(summary["movementSent"])
            self.assertFalse(summary["writesToRiftScan"])
            self.assertEqual(summary["stepCount"], len(steps))

    def test_summary_writers_refuse_riftscan_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            riftscan = Path(temp) / "Riftscan"
            summary = {
                "status": "passed",
                "generatedAtUtc": "2026-05-08T11:30:00Z",
                "requestedTarget": {
                    "processName": "rift_x64",
                    "processId": 33912,
                    "targetWindowHandle": "0xE0DB2",
                },
                "noCheatEngine": True,
                "movementSent": False,
                "writesToRiftScan": False,
                "stepCount": 1,
                "failedStepCount": 0,
                "steps": [
                    {
                        "name": "fixture",
                        "status": "passed",
                        "detail": "ok",
                    }
                ],
            }
            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                write_summary(summary, riftscan / "reports" / "generated" / "bad.json", riftscan_root=riftscan)
            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                write_markdown_summary(
                    summary,
                    riftscan / "reports" / "generated" / "bad.md",
                    riftscan_root=riftscan,
                )
            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                write_latest_pointer(
                    summary,
                    riftscan / "reports" / "generated" / "latest.json",
                    riftscan_root=riftscan,
                )

    def test_markdown_summary_contains_status_and_boundaries(self) -> None:
        summary = {
            "status": "passed",
            "generatedAtUtc": "2026-05-08T11:30:00Z",
            "requestedTarget": {
                "processName": "rift_x64",
                "processId": 33912,
                "targetWindowHandle": "0xE0DB2",
            },
            "noCheatEngine": True,
            "movementSent": False,
            "writesToRiftScan": False,
            "stepCount": 1,
            "failedStepCount": 0,
            "steps": [
                {
                    "name": "riftscan provider git status clean",
                    "status": "passed",
                    "detail": "## main...origin/main",
                }
            ],
        }

        markdown = markdown_for_summary(summary)

        self.assertIn("| Status | `passed` |", markdown)
        self.assertIn("| No Cheat Engine | `True` |", markdown)
        self.assertIn("| Movement sent | `False` |", markdown)
        self.assertIn("| Writes to RiftScan | `False` |", markdown)
        self.assertIn("riftscan provider git status clean", markdown)

    def test_latest_pointer_keeps_resume_fields_and_failed_step_summary(self) -> None:
        summary = {
            "status": "failed",
            "generatedAtUtc": "2026-05-08T11:30:00Z",
            "summaryFile": "C:/RiftReader/scripts/captures/riftscan-validation.json",
            "markdownFile": "C:/RiftReader/scripts/captures/riftscan-validation.md",
            "repoRoot": "C:/RiftReader",
            "riftScanRoot": "C:/Riftscan",
            "requestedTarget": {
                "processName": "rift_x64",
                "processId": 33912,
                "targetWindowHandle": "0xE0DB2",
            },
            "noCheatEngine": True,
            "movementSent": False,
            "writesToRiftScan": False,
            "stepCount": 3,
            "failedStepCount": 1,
            "steps": [
                {
                    "name": "riftscan milestone smoke",
                    "kind": "milestone-json",
                    "status": "passed",
                    "detail": "ready-for-read-only-proof",
                    "exitCode": 0,
                },
                {
                    "name": "fixture failed",
                    "kind": "exit-code",
                    "status": "failed",
                    "detail": "exit 1",
                    "exitCode": 1,
                },
                {
                    "name": "riftscan provider git status clean",
                    "kind": "riftscan-status-clean",
                    "status": "passed",
                    "detail": "## main...origin/main",
                    "exitCode": 0,
                },
            ],
        }

        pointer = build_latest_pointer(summary)

        self.assertEqual(pointer["status"], "failed")
        self.assertEqual(pointer["summaryFile"], summary["summaryFile"])
        self.assertEqual(pointer["markdownFile"], summary["markdownFile"])
        self.assertEqual(pointer["milestoneStatus"], "ready-for-read-only-proof")
        self.assertEqual(pointer["riftScanProviderStatus"], "## main...origin/main")
        self.assertEqual(pointer["failedSteps"], [{"name": "fixture failed", "detail": "exit 1", "exitCode": 1}])


if __name__ == "__main__":
    unittest.main()
