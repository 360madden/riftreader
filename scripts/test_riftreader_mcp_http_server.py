#!/usr/bin/env python3
# Version: riftreader-test-mcp-http-server-v0.1.0
# Purpose: Unit tests for the ChatGPT Web/Desktop HTTP MCP adapter identity and origin gate.

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_mcp.config import ADAPTER_KIND, ADAPTER_PURPOSE, McpHttpConfig  # noqa: E402
from tools.riftreader_mcp.http_server import RiftReaderHttpServer  # noqa: E402
from tools.riftreader_mcp.readonly_tools import RiftReaderReadOnlyTools  # noqa: E402


def make_config(repo: Path) -> McpHttpConfig:
    return McpHttpConfig(repo_root=repo, token="unit-test-token")


class RiftReaderHttpMcpServerTests(unittest.TestCase):
    def test_health_identifies_chatgpt_http_adapter_not_codex_stdio(self) -> None:
        with tempfile.TemporaryDirectory(prefix="riftreader-http-mcp-test-") as temp:
            tools = RiftReaderReadOnlyTools(make_config(Path(temp)))

            health = tools.health({})

        self.assertTrue(health["ok"])
        self.assertEqual(health["adapterKind"], ADAPTER_KIND)
        self.assertEqual(health["adapterPurpose"], ADAPTER_PURPOSE)
        self.assertFalse(health["codexStdioAdapter"])

    def test_initialize_identifies_chatgpt_http_adapter_not_codex_stdio(self) -> None:
        with tempfile.TemporaryDirectory(prefix="riftreader-http-mcp-test-") as temp:
            server = RiftReaderHttpServer(("127.0.0.1", 0), make_config(Path(temp)))
            try:
                response = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            finally:
                server.server_close()

        result = response["result"]
        self.assertEqual(result["serverInfo"]["adapterKind"], ADAPTER_KIND)
        self.assertEqual(result["serverInfo"]["adapterPurpose"], ADAPTER_PURPOSE)
        self.assertIn("ChatGPT Web/Desktop HTTP adapter", result["instructions"])
        self.assertIn("Codex/stdio", result["instructions"])

    def test_origin_allowlist_accepts_chatgpt_and_loopback_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="riftreader-http-mcp-test-") as temp:
            server = RiftReaderHttpServer(("127.0.0.1", 0), make_config(Path(temp)))
            try:
                self.assertTrue(server.origin_allowed(None))
                self.assertTrue(server.origin_allowed("https://chatgpt.com"))
                self.assertTrue(server.origin_allowed("https://chat.openai.com/"))
                self.assertTrue(server.origin_allowed("http://127.0.0.1:3000"))
                self.assertTrue(server.origin_allowed("http://localhost:3000"))
                self.assertFalse(server.origin_allowed("https://evil.example"))
                self.assertFalse(server.origin_allowed("https://chatgpt.com.evil.example"))
            finally:
                server.server_close()


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
