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
        self.assertIn("Browser & Computer Use", html)


if __name__ == "__main__":
    unittest.main()
