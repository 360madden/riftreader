#!/usr/bin/env python3
# Version: riftreader-test-mcp-local-server-control-v0.1.0
# Purpose: Unit tests for safe local HTTP MCP server lifecycle matching.

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_mcp.local_server_control import is_server_process, normalize_for_match  # noqa: E402


class RiftReaderMcpLocalServerControlTests(unittest.TestCase):
    def test_normalize_for_match_handles_quotes_case_and_slashes(self) -> None:
        self.assertEqual(normalize_for_match('"C:\\RIFT MODDING\\RiftReader"'), "c:/rift modding/riftreader")

    def test_is_server_process_accepts_repo_local_http_mcp_server(self) -> None:
        repo = Path("C:/RIFT MODDING/RiftReader")
        process = {
            "commandLine": (
                '"C:\\Python\\python.exe" -m tools.riftreader_mcp.http_server '
                '--repo "C:\\RIFT MODDING\\RiftReader" --json'
            )
        }

        self.assertTrue(is_server_process(process, repo))

    def test_is_server_process_rejects_codex_stdio_counterpart(self) -> None:
        repo = Path("C:/RIFT MODDING/RiftReader")
        process = {
            "commandLine": (
                '"C:\\Python\\python.exe" -m tools.riftreader_mcp.server '
                '--repo "C:\\RIFT MODDING\\RiftReader"'
            )
        }

        self.assertFalse(is_server_process(process, repo))

    def test_is_server_process_rejects_wrong_repo(self) -> None:
        repo = Path("C:/RIFT MODDING/RiftReader")
        process = {
            "commandLine": (
                '"C:\\Python\\python.exe" -m tools.riftreader_mcp.http_server '
                '--repo "C:\\Other\\Repo" --json'
            )
        }

        self.assertFalse(is_server_process(process, repo))


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
