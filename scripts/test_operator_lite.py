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
        "riftreader-package-intake-selftest.cmd",
        "riftreader-local-artifact-bridge.cmd",
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
        self.assertEqual(
            keys,
            {
                "workflow-status",
                "compact-sitrep",
                "live-triage",
                "package-selftest",
                "bridge-selftest",
                "bridge-preflight",
                "bridge-index",
                "git-status",
            },
        )
        compact = next(item for item in plan["commands"] if item["key"] == "compact-sitrep")
        self.assertEqual(compact["expectedExitCodes"], [0, 2])
        self.assertIn("--compact", compact["args"])
        package_selftest = next(item for item in plan["commands"] if item["key"] == "package-selftest")
        self.assertIn("riftreader-package-intake-selftest.cmd", package_selftest["args"][0])
        bridge_selftest = next(item for item in plan["commands"] if item["key"] == "bridge-selftest")
        self.assertIn("riftreader-local-artifact-bridge.cmd", bridge_selftest["args"][0])
        self.assertIn("--self-test", bridge_selftest["args"])
        bridge_preflight = next(item for item in plan["commands"] if item["key"] == "bridge-preflight")
        self.assertIn("--preflight", bridge_preflight["args"])
        self.assertEqual(bridge_preflight["expectedExitCodes"], [0, 2])
        bridge_index = next(item for item in plan["commands"] if item["key"] == "bridge-index")
        self.assertIn("--index", bridge_index["args"])
        self.assertIn("bridge-serve-or-tunnel", plan["disabledLiveActions"])
        self.assertFalse(plan["safety"]["movementSent"])
        self.assertFalse(plan["safety"]["gitMutation"])

    def test_denies_live_or_git_mutating_fragments(self) -> None:
        self.assertIn("send-rift-key", operator_lite.validate_safe_args(["scripts/send-rift-key.ps1"]))
        self.assertIn("git push", operator_lite.validate_safe_args(["git", "push", "origin", "main"]))
        self.assertIn("proofonly", operator_lite.validate_safe_args(["run-ProofOnly.ps1"]))
        self.assertIn("--serve", operator_lite.validate_safe_args(["scripts/riftreader-local-artifact-bridge.cmd", "--serve"]))
        self.assertIn("cloudflared", operator_lite.validate_safe_args(["cloudflared", "tunnel", "--url", "http://127.0.0.1:8765"]))

    def test_package_intake_dry_run_args_are_ask_gated_but_not_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            args = operator_lite.package_intake_dry_run_args(root, Path("C:/tmp/package.zip"))

        self.assertIn("--compact-json", args)
        self.assertEqual(operator_lite.validate_safe_args(args), [])

    def test_latest_report_returns_newest_local_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            older = root / ".riftreader-local" / "opencode-status" / "old" / "report.md"
            newer = root / ".riftreader-local" / "package-intake-selftest" / "new" / "summary.json"
            older.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            older.write_text("old", encoding="utf-8")
            newer.write_text("{}", encoding="utf-8")
            os.utime(older, (1_700_000_000, 1_700_000_000))
            os.utime(newer, (1_800_000_000, 1_800_000_000))

            report = operator_lite.latest_report(root)

        self.assertEqual(report, newer)

    def test_bridge_status_summary_is_read_only_and_local(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = root / "artifacts" / "chatgpt-payloads" / "payload-one"
            payload.mkdir(parents=True)
            (payload / "manifest.json").write_text("{}", encoding="utf-8")
            (payload / "chunk-index.json").write_text("{}", encoding="utf-8")

            summary = operator_lite.bridge_status_summary(root)

        self.assertEqual(summary["mode"], "read_only_manual_start")
        self.assertFalse(summary["serveManagedByOperatorLite"])
        self.assertFalse(summary["tunnelManagedByOperatorLite"])
        self.assertEqual(summary["payloadCount"], 1)
        self.assertEqual(summary["latestPayloadId"], "payload-one")
        self.assertTrue(summary["safety"]["noHttpWrites"])
        self.assertTrue(summary["safety"]["manualTunnelOnly"])

    def test_redacted_bridge_instructions_do_not_include_real_token(self) -> None:
        instructions = operator_lite.redacted_bridge_instructions(REPO_ROOT)

        self.assertIn("<token>/health", instructions)
        self.assertIn("cloudflared tunnel --url http://127.0.0.1:8765", instructions)
        self.assertNotIn("token=", instructions.lower())
        self.assertNotIn("sk-", instructions.lower())

    def test_redacted_bridge_start_command_keeps_manual_serve_explicit(self) -> None:
        command = operator_lite.redacted_bridge_start_command(REPO_ROOT)

        self.assertIn("--serve", command)
        self.assertIn("--token auto", command)
        self.assertIn("127.0.0.1", command)
        self.assertIn("Start any tunnel manually", command)
        self.assertNotIn("cloudflared", command.lower())
        self.assertNotIn("sk-", command.lower())

    def test_redacted_bridge_chatgpt_prompt_points_to_safe_aliases(self) -> None:
        prompt = operator_lite.redacted_bridge_chatgpt_prompt(REPO_ROOT)

        self.assertIn("<token>/", prompt)
        self.assertIn("<token>/payloads/latest/readme.md", prompt)
        self.assertIn("<token>/payloads/latest/chunks.json", prompt)
        self.assertIn("GET/HEAD only", prompt)
        self.assertIn("registered chunk IDs", prompt)
        self.assertNotIn("token=", prompt.lower())
        self.assertNotIn("sk-", prompt.lower())

    def test_gui_theme_summary_has_distinct_action_groups(self) -> None:
        summary = operator_lite.gui_theme_summary()

        self.assertIn("Workflow Status & Triage", summary["sections"])
        self.assertIn("Local Artifact Bridge", summary["sections"])
        self.assertIn("bridge", summary["buttonVariants"])
        self.assertIn("warning", summary["buttonVariants"])
        self.assertIn("manual bridge start command copy", summary["visualRules"])
        self.assertIn("redacted ChatGPT bridge prompt copy", summary["visualRules"])
        self.assertIn("muted locked-control badges", summary["visualRules"])
        self.assertTrue(summary["palette"]["primary"].startswith("#"))
        self.assertNotEqual(summary["palette"]["primary"], summary["palette"]["bridge"])

    def test_command_plan_json_serializable(self) -> None:
        plan = operator_lite.command_plan(REPO_ROOT)
        encoded = json.dumps(plan)

        self.assertIn("riftreader-operator-lite-command-plan", encoded)


if __name__ == "__main__":
    unittest.main()
