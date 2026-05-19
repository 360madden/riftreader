#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_mission_control as mission  # noqa: E402


def make_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "riftreader-operator-lite.cmd").write_text(
        '@echo off\necho {"ok":true,"status":"passed"}\nexit /b 0\n',
        encoding="utf-8",
    )
    (scripts / "riftreader-chatgpt-mcp.cmd").write_text(
        '@echo off\necho {"ok":true,"status":"passed"}\nexit /b 0\n',
        encoding="utf-8",
    )


class McpMissionControlTests(unittest.TestCase):
    def test_dashboard_lists_commands_without_starting_public_tunnel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = mission.mission_control(root)

        self.assertEqual(payload["kind"], "riftreader-mcp-mission-control")
        self.assertIn("readiness", payload["pasteSafeCommands"])
        self.assertIn("proposalSmoke", payload["pasteSafeCommands"])
        self.assertIn("trialSession", payload["pasteSafeCommands"])
        self.assertIn("phase2Status", payload["pasteSafeCommands"])
        self.assertIn("phase2CompactStatus", payload["pasteSafeCommands"])
        self.assertIn("artifactBrowser", payload["pasteSafeCommands"])
        self.assertIn("safeCommitPlan", payload["pasteSafeCommands"])
        self.assertIn("ciStatus", payload)
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertFalse(payload["safety"]["gitMutation"])

    def test_trial_command_displays_bounded_public_trial_command_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = mission.trial_command_payload(root)

        self.assertEqual(payload["kind"], "riftreader-mcp-mission-control-trial-command")
        self.assertIn("--chatgpt-trial-session", payload["command"])
        self.assertIn("--chatgpt-session-seconds", payload["command"])
        self.assertTrue(payload["safety"]["commandDisplayedOnly"])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])

    def test_run_readiness_executes_local_only_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = mission.run_local_action(root, "mcpTrialReadiness", "run-readiness")

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertIn("riftreader-operator-lite.cmd", payload["command"][0])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertFalse(payload["safety"]["gitMutation"])

    def test_cli_trial_command_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = mission.main(["--repo-root", str(root), "--trial-command", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-mcp-mission-control-trial-command")

    def test_markdown_summary_and_checklist_are_generated_from_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            payload = mission.mission_control(root)

            summary = mission.render_summary_markdown(payload)
            checklist = mission.render_proof_checklist(payload)

        self.assertIn("RiftReader MCP Mission Control Summary", summary)
        self.assertIn("Current-head CI", summary)
        self.assertIn("Latest artifacts", summary)
        self.assertIn("RiftReader MCP Proof Checklist", checklist)
        self.assertIn("scripts\\riftreader-chatgpt-trial-recorder.cmd --record --input proof.json --json", checklist)


if __name__ == "__main__":
    unittest.main()
