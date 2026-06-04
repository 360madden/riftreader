#!/usr/bin/env python3
# Version: riftreader-test-mcp-server-v0.1.0
# Total-Character-Count: 0000003866
# Purpose: Unit tests for the RiftReader MCP server protocol surface and strict tool behavior.

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_mcp.server import RiftReaderMcpServer, porcelain_paths  # noqa: E402


def make_temp_repo() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="riftreader-mcp-test-"))
    subprocess.run(["git", "init"], cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp, check=True)
    (tmp / "scripts").mkdir()
    (tmp / "handoffs" / "current").mkdir(parents=True)
    (tmp / "tools" / "riftreader_mcp").mkdir(parents=True)
    (tmp / "handoffs" / "current" / "RIFTREADER_CURRENT_HANDOFF.md").write_text("# Test handoff\n", encoding="utf-8")
    (tmp / "handoffs" / "current" / "RIFTREADER_CURRENT_HANDOFF.json").write_text(
        json.dumps({"kind": "test-handoff"}),
        encoding="utf-8",
    )
    (tmp / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return tmp


class RiftReaderMcpServerTests(unittest.TestCase):
    def test_initialize_and_list_tools(self) -> None:
        repo = make_temp_repo()
        server = RiftReaderMcpServer(repo)
        response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["result"]["capabilities"]["tools"]["listChanged"], False)

        tools = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = {tool["name"] for tool in tools["result"]["tools"]}
        self.assertIn("riftreader.get_git_state", names)
        self.assertIn("riftreader.get_current_handoff", names)
        self.assertIn("riftreader.run_static_chain_diagnostics", names)

    def test_get_current_handoff_tool(self) -> None:
        repo = make_temp_repo()
        server = RiftReaderMcpServer(repo)
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "riftreader.get_current_handoff", "arguments": {"maxChars": 10000}},
            }
        )
        result = response["result"]
        self.assertFalse(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("Test handoff", text)
        self.assertIn("test-handoff", text)

    def test_unknown_tool_errors(self) -> None:
        repo = make_temp_repo()
        server = RiftReaderMcpServer(repo)
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "riftreader.shell", "arguments": {}},
            }
        )
        self.assertIn("error", response)
        self.assertIn("Unknown tool", response["error"]["message"])

    def test_porcelain_paths(self) -> None:
        output = "## main...origin/main\n M tools/riftreader_workflow/status_packet.py\n?? docs/workflow/example.md\n"
        self.assertEqual(
            porcelain_paths(output),
            ["docs/workflow/example.md", "tools/riftreader_workflow/status_packet.py"],
        )


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
