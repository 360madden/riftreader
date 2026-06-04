#!/usr/bin/env python3
# Version: riftreader-test-mcp-client-config-v0.1.0
# Total-Character-Count: 0000002554
# Purpose: Unit tests for the RiftReader MCP client config and stdio smoke helper.

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

from tools.riftreader_mcp.client_config import EXPECTED_TOOLS, mcp_config, smoke_test  # noqa: E402


def make_temp_repo() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="riftreader-mcp-client-test-"))
    subprocess.run(["git", "init"], cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp, check=True)
    (tmp / "scripts").mkdir()
    (tmp / "tools" / "riftreader_mcp").mkdir(parents=True)
    (tmp / "scripts" / "riftreader-mcp-server.cmd").write_text("@echo off\n", encoding="utf-8")
    server_src = ROOT / "tools" / "riftreader_mcp" / "server.py"
    init_src = ROOT / "tools" / "riftreader_mcp" / "__init__.py"
    (tmp / "tools" / "riftreader_mcp" / "server.py").write_text(server_src.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp / "tools" / "riftreader_mcp" / "__init__.py").write_text(init_src.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return tmp


class RiftReaderMcpClientConfigTests(unittest.TestCase):
    def test_config_contains_expected_server(self) -> None:
        repo = Path(r"C:\RIFT MODDING\RiftReader")
        config = mcp_config(repo, server_name="riftreader")
        server = config["mcpServers"]["riftreader"]
        self.assertIn("riftreader-mcp-server.cmd", server["command"])
        self.assertEqual(server["args"], ["--repo", str(repo)])

    def test_smoke_test_lists_expected_tools(self) -> None:
        repo = make_temp_repo()
        result = smoke_test(repo, timeout_seconds=15)
        self.assertEqual(result["status"], "passed")
        self.assertTrue(EXPECTED_TOOLS.issubset(set(result["toolsListToolNames"])))


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
