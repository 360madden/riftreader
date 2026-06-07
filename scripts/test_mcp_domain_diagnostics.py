#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_domain_diagnostics as diag  # noqa: E402


class FakeHeaders:
    def __init__(self, content_type: str = "application/json") -> None:
        self.content_type = content_type

    def get(self, name: str, default: str = "") -> str:
        return self.content_type if name.lower() == "content-type" else default


class FakeResponse:
    def __init__(self, status: int, payload: dict[str, object], content_type: str = "application/json") -> None:
        self.status = status
        self.headers = FakeHeaders(content_type)
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, _limit: int = -1) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class McpDomainDiagnosticsTests(unittest.TestCase):
    def test_caddyfile_routes_domain_mcp_to_local_backend(self) -> None:
        text = diag.caddyfile_text("mcp.360madden.com")

        self.assertIn("mcp.360madden.com", text)
        self.assertIn("@mcp path /mcp", text)
        self.assertIn("reverse_proxy @mcp http://127.0.0.1:8770", text)

    def test_public_smoke_fails_http_502(self) -> None:
        error = HTTPError("https://mcp.360madden.com/mcp", 502, "Bad Gateway", FakeHeaders("text/html"), None)
        error.fp = type("FakeFp", (), {"read": lambda self, _limit=-1: b"<html>bad gateway</html>"})()
        with mock.patch.object(diag, "urlopen", side_effect=error):
            payload = diag.smoke_public_initialize("https://mcp.360madden.com/mcp")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["httpStatus"], 502)
        self.assertIn("public-mcp-http-status:502", payload["blockers"])
        self.assertEqual(payload["request"]["protocolVersion"], "2025-06-18")
        self.assertEqual(payload["request"]["headerMcpProtocolVersion"], "2025-06-18")

    def test_public_smoke_requires_riftreader_server_info(self) -> None:
        response = FakeResponse(
            200,
            {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "wrong"}, "protocolVersion": "2025-06-18"}},
        )
        with mock.patch.object(diag, "urlopen", return_value=response):
            payload = diag.smoke_public_initialize("https://mcp.360madden.com/mcp")

        self.assertFalse(payload["ok"])
        self.assertIn("server-info-name-mismatch:'wrong'", payload["blockers"])

    def test_public_smoke_accepts_valid_initialize(self) -> None:
        response = FakeResponse(
            200,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"serverInfo": {"name": "riftreader_chatgpt_mcp"}, "protocolVersion": "2025-06-18"},
            },
        )
        with mock.patch.object(diag, "urlopen", return_value=response):
            payload = diag.smoke_public_initialize("https://mcp.360madden.com/mcp")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["blockers"], [])


if __name__ == "__main__":
    unittest.main()
