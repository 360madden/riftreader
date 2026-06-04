#!/usr/bin/env python3
# Version: riftreader-test-mcp-tool-caller-v0.1.2
# Total-Character-Count: 0000002450
# Purpose: Unit tests for the RiftReader MCP tool caller.

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

from tools.riftreader_mcp.call_tool import call_tool, parse_arguments_json  # noqa: E402


def make_temp_repo() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="riftreader-mcp-call-test-"))
    subprocess.run(["git", "init"], cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp, check=True)
    (tmp / "tools" / "riftreader_mcp").mkdir(parents=True)
    for name in ("server.py", "__init__.py"):
        src = ROOT / "tools" / "riftreader_mcp" / name
        (tmp / "tools" / "riftreader_mcp" / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return tmp


class RiftReaderMcpToolCallerTests(unittest.TestCase):
    def test_parse_arguments_json_defaults_empty(self) -> None:
        self.assertEqual(parse_arguments_json(None, None), {})

    def test_parse_arguments_json_object(self) -> None:
        self.assertEqual(parse_arguments_json('{"timeoutSeconds": 30}', None), {"timeoutSeconds": 30})

    def test_call_get_git_state(self) -> None:
        repo = make_temp_repo()
        result = call_tool(repo, tool="riftreader.get_git_state", arguments={}, timeout_seconds=15)
        self.assertEqual(result["status"], "passed")
        self.assertIn("riftreader.get_git_state", result["availableTools"])
        self.assertIn("Initial", result["textContent"])

    def test_unavailable_tool_fails(self) -> None:
        repo = make_temp_repo()
        with self.assertRaises(Exception):
            call_tool(repo, tool="riftreader.shell", arguments={}, timeout_seconds=15)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
