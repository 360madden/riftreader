#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_dashboard as dashboard  # noqa: E402


class McpDashboardTests(unittest.TestCase):
    def test_redact_repo_root_recursively(self) -> None:
        root = Path(r"C:\RIFT MODDING\RiftReader")
        payload = {
            "path": r"C:\RIFT MODDING\RiftReader\docs\HANDOFF.md",
            "nested": [r"C:/RIFT MODDING/RiftReader/.riftreader-local/proof.json"],
        }

        redacted = dashboard.redact_repo_root(payload, root)
        text = json.dumps(redacted)

        self.assertNotIn(str(root), text)
        self.assertNotIn(str(root).replace("\\", "/"), text)
        self.assertIn(".\\\\docs\\\\HANDOFF.md", text)

    def test_self_test_blocks_absolute_root_and_secret_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            leaked = {
                "safety": {"localhostOnly": True},
                "path": str(root),
                "token": "sk-proj-leaky-test-token-1234567890",
            }
            with mock.patch.object(dashboard, "collect_status", return_value=leaked):
                payload = dashboard.self_test(root, "mcp.360madden.com")

        self.assertFalse(payload["ok"])
        self.assertIn("absolute-repo-root-exposed", payload["blockers"])
        self.assertIn("secret-like-token-exposed", payload["blockers"])

    def test_handler_serves_html_with_status_only_safety_copy(self) -> None:
        html = dashboard.render_html().decode("utf-8")

        self.assertIn("Local status dashboard only", html)
        self.assertIn("No start/stop", html)
        self.assertIn("/status.json", html)
        self.assertIn("Readiness Summary", html)
        self.assertIn("Browser & Computer Use", html)
        self.assertIn("Desktop Queue Contract", html)
        self.assertIn("Desktop Queue Draft Viewer", html)
        self.assertIn("Desktop Readiness Commands", html)
        self.assertIn("Status JSON", html)
        self.assertIn("legacy Caddy/router is deprecated", html)
        self.assertIn("Full ${esc(s.toolSurface.fullFinalProofToolCount)}-tool final proof", html)
        self.assertNotIn("Full 12-tool final proof", html)

    def test_render_html_embeds_initial_status_for_fetch_blocked_browsers(self) -> None:
        html = dashboard.render_html(
            {"kind": "test-status", "unsafe": "</script><script>bad()</script>"}
        ).decode("utf-8")

        self.assertIn('id="initial-status"', html)
        self.assertIn('"kind": "test-status"', html)
        self.assertIn("renderStatus(latestStatus, \"embedded\")", html)
        self.assertIn("<\\/script>", html)
        self.assertNotIn("</script><script>bad()", html)

    def test_collect_status_marks_local_443_owner_as_diagnostic_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                mock.patch.object(dashboard, "_socket_connect", return_value={"ok": True}),
                mock.patch.object(dashboard, "check_dns", return_value={"ok": True, "status": "passed"}),
                mock.patch.object(dashboard, "check_windows_port_owner", return_value={"ok": True, "processes": []}),
                mock.patch.object(
                    dashboard,
                    "build_mcp_server_status_payload",
                    return_value={"ok": True, "status": "running-current", "blockers": []},
                ),
                mock.patch.object(
                    dashboard,
                    "smoke_public_initialize",
                    return_value={"ok": True, "status": "passed", "blockers": []},
                ),
                mock.patch.object(dashboard, "command_json", return_value={"ok": True, "status": "passed"}),
                mock.patch.object(
                    dashboard,
                    "desktop_control_readiness_payload",
                    return_value={
                        "ok": True,
                        "status": "passed",
                        "repairGuide": {
                            "recordBlockedCommand": [
                                "scripts\\riftreader-desktop-control-readiness.cmd",
                                "--record-observation",
                                "--browser-dashboard-smoke-ok",
                                "--computer-use-stage",
                                "setup",
                                "--computer-use-error",
                                "Computer Use native pipe path is unavailable",
                                "--json",
                            ],
                            "recordSuccessCommand": [
                                "scripts\\riftreader-desktop-control-readiness.cmd",
                                "--record-observation",
                                "--browser-dashboard-smoke-ok",
                                "--computer-use-native-pipe-ok",
                                "--computer-use-list-apps-ok",
                                "--computer-use-stage",
                                "passed",
                                "--json",
                            ],
                        },
                    },
                ),
                mock.patch.object(
                    dashboard,
                    "desktop_control_queue_contract_payload",
                    return_value={
                        "ok": True,
                        "status": "passed",
                        "summary": "plan only",
                        "execution": {"enabled": False, "status": "disabled"},
                        "queueItemSchema": {"forbiddenActionFamilies": ["desktop-click"]},
                        "queueDraftViewer": {
                            "ok": True,
                            "status": "ready",
                            "count": 0,
                            "latestDraft": None,
                            "safety": {
                                "viewerOnly": True,
                                "draftWriteEndpoint": False,
                                "executionEndpoint": False,
                            },
                        },
                        "chatGptWindowDiscovery": {
                            "ok": True,
                            "status": "ready",
                            "actionKey": "chatgpt-window-discovery-no-input",
                        },
                        "requiredGatesBeforeAnyFutureExecutor": ["desktopControlReadiness.ok=true"],
                        "safety": {"contractOnly": True, "executionEndpoint": False},
                    },
                ),
            ):
                status = dashboard.collect_status(root, "mcp.360madden.com", include_public_smoke=True)

        self.assertEqual(status["activeRoute"]["key"], "cloudflare-named-tunnel")
        self.assertTrue(status["activeRoute"]["legacyCaddyRouterDeprecated"])
        self.assertTrue(status["activeRoute"]["tcp443OwnerDiagnosticOnly"])
        self.assertTrue(status["domain"]["tcp443OwnerDiagnosticOnly"])
        self.assertIn("readinessBadges", status)
        self.assertIn("local-mcp-server", [badge["key"] for badge in status["readinessBadges"]])
        self.assertIn("computer-use", [badge["key"] for badge in status["readinessBadges"]])
        self.assertEqual("running-current", status["backend"]["serverDependency"]["status"])
        self.assertEqual(status["desktopControlQueue"]["execution"]["status"], "disabled")
        self.assertFalse(status["desktopControlQueue"]["execution"]["enabled"])
        self.assertEqual(status["desktopControlQueue"]["queueDraftViewer"]["status"], "ready")
        self.assertFalse(status["desktopControlQueue"]["queueDraftViewer"]["safety"]["draftWriteEndpoint"])
        self.assertEqual(
            status["desktopControlQueue"]["chatGptWindowDiscovery"]["actionKey"],
            "chatgpt-window-discovery-no-input",
        )
        self.assertIn("desktopControlReadiness.ok=true", status["desktopControlQueue"]["requiredGatesBeforeAnyFutureExecutor"])
        self.assertIn("--computer-use-native-pipe-ok", status["desktopControlCommands"]["recordSuccessCommandText"])
        self.assertIn('"Computer Use native pipe path is unavailable"', status["desktopControlCommands"]["recordBlockedCommandText"])
        self.assertTrue(status["desktopControlCommands"]["safety"]["copyOnly"])
        self.assertFalse(status["desktopControlCommands"]["safety"]["executionEndpoint"])

    def test_self_test_blocks_desktop_queue_execution_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unsafe_status = {
                "safety": {"localhostOnly": True},
                "desktopControlQueue": {
                    "execution": {
                        "enabled": True,
                        "executorImplemented": True,
                        "mcpToolExposed": True,
                    },
                    "safety": {
                        "executionEndpoint": True,
                        "queueWriteEndpoint": True,
                    },
                    "queueDraftViewer": {
                        "safety": {
                            "viewerOnly": False,
                            "draftWriteEndpoint": True,
                            "executionEndpoint": True,
                        },
                    },
                },
                "desktopControlCommands": {
                    "safety": {
                        "copyOnly": False,
                        "executionEndpoint": True,
                    },
                },
            }
            with mock.patch.object(dashboard, "collect_status", return_value=unsafe_status):
                payload = dashboard.self_test(root, "mcp.360madden.com")

        self.assertFalse(payload["ok"])
        self.assertIn("desktop-control-queue-execution-enabled", payload["blockers"])
        self.assertIn("desktop-control-queue-executor-implemented", payload["blockers"])
        self.assertIn("desktop-control-queue-mcp-tool-exposed", payload["blockers"])
        self.assertIn("desktop-control-queue-execution-endpoint", payload["blockers"])
        self.assertIn("desktop-control-queue-write-endpoint", payload["blockers"])
        self.assertIn("desktop-control-draft-viewer-not-viewer-only", payload["blockers"])
        self.assertIn("desktop-control-draft-viewer-write-endpoint", payload["blockers"])
        self.assertIn("desktop-control-draft-viewer-execution-endpoint", payload["blockers"])
        self.assertIn("desktop-control-commands-not-copy-only", payload["blockers"])
        self.assertIn("desktop-control-commands-execution-endpoint", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
