#!/usr/bin/env python3

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_server_status  # noqa: E402


def listener(command_line: str, *, pid: int = 1234) -> dict[str, object]:
    return {
        "ok": True,
        "exists": True,
        "host": "127.0.0.1",
        "port": 8770,
        "listeners": [
            {
                "localAddress": "127.0.0.1",
                "localPort": 8770,
                "state": "Listen",
                "owningProcess": pid,
                "processExists": True,
                "processName": "python.exe",
                "executablePath": r"C:\Python\python.exe",
                "commandLine": command_line,
            }
        ],
    }


class McpServerStatusTests(unittest.TestCase):
    def test_current_full_profile_server_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query=listener(
                    r'python "tools\riftreader_workflow\riftreader_chatgpt_mcp.py" --serve '
                    r"--tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http "
                    r"--allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com"
                ),
            )

        self.assertTrue(payload["ok"])
        self.assertEqual("running-current", payload["status"])
        self.assertEqual("full", payload["selectedListener"]["classification"]["toolProfile"])
        self.assertEqual([], payload["blockers"])

    def test_missing_listener_blocks_with_clear_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query={"ok": True, "exists": False, "listeners": []},
            )

        self.assertFalse(payload["ok"])
        self.assertEqual("not-running", payload["status"])
        self.assertIn("local-backend-not-running:127.0.0.1:8770", payload["blockers"])
        self.assertEqual("saved-chatgpt-connector-config-does-not-start-local-backend", payload["operatorRule"])

    def test_foreign_listener_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query=listener(r"C:\OtherApp\python.exe unrelated_server.py --port 8770"),
            )

        self.assertFalse(payload["ok"])
        self.assertEqual("foreign-listener", payload["status"])
        self.assertIn("local-backend-port-foreign-listener:8770", payload["blockers"])

    def test_legacy_listener_does_not_satisfy_current_chatgpt_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query=listener(r"python -m tools.riftreader_mcp.http_server --repo . --json"),
            )

        self.assertFalse(payload["ok"])
        self.assertEqual("running-legacy", payload["status"])
        self.assertIn("current-chatgpt-mcp-server-not-running:legacy-server-listening", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
