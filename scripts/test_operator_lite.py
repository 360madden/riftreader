#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import operator_lite  # noqa: E402


def make_repo(root: Path) -> None:
    (root / ".git").mkdir()
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    for name in [
        "riftreader-workflow-status.cmd",
        "riftreader-live-triage.cmd",
        "riftreader-package-intake.cmd",
    ]:
        (scripts / name).write_text("@echo off\n", encoding="utf-8")


class OperatorLiteTests(unittest.TestCase):
    def test_command_plan_contains_only_safe_default_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            plan = operator_lite.command_plan(root)

        self.assertEqual(plan["status"], "passed")
        keys = {item["key"] for item in plan["commands"]}
        self.assertEqual(keys, {"workflow-status", "live-triage", "git-status"})
        self.assertFalse(plan["safety"]["movementSent"])
        self.assertFalse(plan["safety"]["gitMutation"])

    def test_denies_live_or_git_mutating_fragments(self) -> None:
        self.assertIn("send-rift-key", operator_lite.validate_safe_args(["scripts/send-rift-key.ps1"]))
        self.assertIn("git push", operator_lite.validate_safe_args(["git", "push", "origin", "main"]))
        self.assertIn("proofonly", operator_lite.validate_safe_args(["run-ProofOnly.ps1"]))

    def test_package_intake_dry_run_args_are_ask_gated_but_not_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            args = operator_lite.package_intake_dry_run_args(root, Path("C:/tmp/package.zip"))

        self.assertIn("--json", args)
        self.assertEqual(operator_lite.validate_safe_args(args), [])

    def test_latest_report_returns_newest_local_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            older = root / ".riftreader-local" / "opencode-status" / "old" / "report.md"
            newer = root / ".riftreader-local" / "live-test-triage" / "new" / "summary.json"
            older.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            older.write_text("old", encoding="utf-8")
            newer.write_text("{}", encoding="utf-8")
            os.utime(older, (1_700_000_000, 1_700_000_000))
            os.utime(newer, (1_800_000_000, 1_800_000_000))

            report = operator_lite.latest_report(root)

        self.assertEqual(report, newer)

    def test_command_plan_json_serializable(self) -> None:
        plan = operator_lite.command_plan(REPO_ROOT)
        encoded = json.dumps(plan)

        self.assertIn("riftreader-operator-lite-command-plan", encoded)


if __name__ == "__main__":
    unittest.main()
