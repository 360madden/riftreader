#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_control_center as control_center  # noqa: E402


def minimal_dashboard_status() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-mcp-dashboard-status",
        "generatedAtUtc": "2026-06-17T00:00:00Z",
        "status": "passed",
        "ok": True,
        "backend": {
            "host": "127.0.0.1",
            "port": 8770,
            "connect": {"ok": True},
            "owner": {"processes": []},
        },
        "domain": {
            "publicHost": "mcp.360madden.com",
            "publicMcpUrl": "https://mcp.360madden.com/mcp",
            "dns": {"ok": True, "status": "passed"},
            "publicSmoke": {"ok": True, "status": "passed"},
        },
        "readinessBadges": [
            {"key": "repo-final-gate", "label": "Repo final gate", "status": "passed", "ok": True, "blockers": []}
        ],
        "missionControl": {"status": "passed", "ok": True},
        "proof": {"latestTemplatePath": ".riftreader-local/template/proof-input.json"},
    }


class McpControlCenterTests(unittest.TestCase):
    def test_action_registry_has_no_forbidden_command_fragments(self) -> None:
        blockers = control_center.registry_static_checks()

        self.assertEqual([], blockers)

    def test_unknown_action_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = control_center.run_action(Path(temp_dir), "definitely-not-an-action")

        self.assertFalse(result["ok"])
        self.assertIn("unknown-action:definitely-not-an-action", result["blockers"])

    def test_start_and_stop_actions_require_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for action in ("start_full_server", "start_readonly_server", "stop_managed_server"):
                result = control_center.run_action(root, action, confirmed=False)
                self.assertFalse(result["ok"], action)
                self.assertIn("confirmation-required", result["blockers"], action)

    def test_command_action_redacts_root_and_secret_like_output(self) -> None:
        spec = control_center.ACTION_SPECS["final_gate"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            completed = subprocess.CompletedProcess(
                args=list(spec.command),
                returncode=0,
                stdout=json.dumps({"path": str(root / "secret.txt"), "token": "sk-proj-testtoken1234567890"}),
                stderr="",
            )
            with mock.patch.object(control_center.subprocess, "run", return_value=completed):
                result = control_center.run_command_action(root, spec)

        text = json.dumps(result)
        self.assertTrue(result["ok"])
        self.assertNotIn(str(root), text)
        self.assertNotIn("sk-proj-testtoken1234567890", text)
        self.assertIn("<redacted-secret>", text)

    def test_collect_status_exposes_bounded_gui_safety_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with mock.patch.object(control_center, "collect_dashboard_status", return_value=minimal_dashboard_status()):
                status = control_center.collect_status(root, "mcp.360madden.com", include_public_smoke=False)

        self.assertEqual("riftreader-mcp-control-center-status", status["kind"])
        self.assertTrue(status["safety"]["localhostOnly"])
        self.assertFalse(status["safety"]["arbitraryShellEndpoint"])
        self.assertFalse(status["safety"]["gitMutationEndpoint"])
        self.assertFalse(status["safety"]["cloudflareMutationEndpoint"])
        self.assertFalse(status["safety"]["riftInputEndpoint"])
        self.assertEqual("https://mcp.360madden.com/mcp", status["chatGpt"]["serverUrl"])
        self.assertEqual(20, status["toolSurface"]["expectedToolCount"])

    def test_static_gui_includes_polished_navigation_surfaces(self) -> None:
        index = (control_center.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        styles = (control_center.STATIC_ROOT / "styles.css").read_text(encoding="utf-8")
        app = (control_center.STATIC_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("role=\"tablist\"", index)
        self.assertIn("Overview", index)
        self.assertIn("Server", index)
        self.assertIn("Route & ChatGPT", index)
        self.assertIn("Proof", index)
        self.assertIn("Logs & JSON", index)
        self.assertIn("font-family", styles)
        self.assertIn("grid-template-columns", styles)
        self.assertIn("X-RiftReader-Control-Center", app)
        self.assertIn("window.confirm", app)


if __name__ == "__main__":
    unittest.main()
