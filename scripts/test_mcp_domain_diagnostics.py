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
    def test_legacy_caddyfile_routes_domain_mcp_to_local_backend(self) -> None:
        text = diag.caddyfile_text("mcp.360madden.com")

        self.assertIn("Legacy/deprecated", text)
        self.assertIn("Cloudflare named Tunnel", text)
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

    def test_windows_port_owner_filters_exact_listening_port(self) -> None:
        netstat_stdout = "\n".join(
            [
                "  TCP    0.0.0.0:443          0.0.0.0:0              LISTENING       123",
                "  TCP    127.0.0.1:4430       127.0.0.1:49350        FIN_WAIT_2      456",
                "  TCP    127.0.0.1:8770       127.0.0.1:3684         ESTABLISHED     789",
            ]
        )

        def fake_run(args: list[str], stdout_limit: int | None = 4000) -> dict[str, object]:
            if args[:2] == ["netstat", "-ano"]:
                return {"args": args, "exitCode": 0, "ok": True, "stdout": netstat_stdout, "stderr": ""}
            if args[:1] == ["tasklist"]:
                return {"args": args, "exitCode": 0, "ok": True, "stdout": '"caddy.exe","123","Services","0","1,234 K"\n', "stderr": ""}
            return {"args": args, "exitCode": 1, "ok": False, "stdout": "", "stderr": ""}

        with mock.patch.object(diag, "_run", side_effect=fake_run):
            payload = diag.check_windows_port_owner(443)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["listeners"], [{"protocol": "TCP", "local": "0.0.0.0:443", "foreign": "0.0.0.0:0", "state": "LISTENING", "pid": "123"}])
        self.assertEqual(payload["processes"], [{"pid": "123", "imageName": "caddy.exe"}])

    def test_collect_diagnostics_marks_cloudflare_tunnel_active_and_caddy_deprecated(self) -> None:
        fake_owner_443 = {
            "status": "blocked",
            "ok": False,
            "port": 443,
            "listeners": [{"protocol": "TCP", "local": "0.0.0.0:443", "foreign": "0.0.0.0:0", "state": "LISTENING", "pid": "123"}],
            "processes": [{"pid": "123", "imageName": "not-caddy.exe"}],
            "blockers": ["tcp-443-owner-not-caddy"],
        }
        with (
            mock.patch.object(diag, "check_dns", return_value={"status": "passed", "ok": True, "host": "mcp.360madden.com", "addresses": ["203.0.113.1"]}),
            mock.patch.object(diag, "_socket_connect", side_effect=[
                {"ok": True, "host": "127.0.0.1", "port": 8770},
                {"ok": True, "host": "mcp.360madden.com", "port": 443},
            ]),
            mock.patch.object(
                diag,
                "check_windows_port_owner",
                side_effect=[
                    {"status": "passed", "ok": True, "port": 8770, "listeners": [], "processes": [], "blockers": []},
                    fake_owner_443,
                ],
            ),
            mock.patch.object(
                diag,
                "smoke_public_initialize",
                return_value={"status": "passed", "ok": True, "blockers": [], "serverInfo": {"name": "riftreader_chatgpt_mcp"}},
            ),
        ):
            payload = diag.collect_domain_diagnostics(REPO_ROOT, public_host="mcp.360madden.com")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["activeRoute"]["key"], "cloudflare-named-tunnel")
        self.assertEqual(payload["activeRoute"]["expectedTunnelName"], "riftreader-mcp-360madden")
        self.assertEqual(payload["activeRoute"]["expectedPublishedApplicationService"], "http://127.0.0.1:8770")
        self.assertTrue(payload["caddy"]["deprecated"])
        self.assertFalse(payload["caddy"]["activeRouteUsesCaddy"])
        self.assertIsNone(payload["caddy"]["generatedCaddyfile"])
        self.assertIsNone(payload["artifacts"]["generatedCaddyfile"])
        self.assertTrue(payload["safety"]["caddyRouterDeprecated"])
        self.assertNotIn("tcp-443-owner-not-caddy", payload["blockers"])
        self.assertTrue(any("legacy-tcp-443-owner-not-caddy" in item for item in payload["warnings"]))

    def test_collect_diagnostics_writes_legacy_caddyfile_only_when_requested(self) -> None:
        with (
            mock.patch.object(
                diag,
                "check_dns",
                return_value={"status": "passed", "ok": True, "host": "mcp.360madden.com", "addresses": ["203.0.113.1"]},
            ),
            mock.patch.object(
                diag,
                "_socket_connect",
                side_effect=[
                    {"ok": True, "host": "127.0.0.1", "port": 8770},
                    {"ok": True, "host": "mcp.360madden.com", "port": 443},
                ],
            ),
            mock.patch.object(
                diag,
                "check_windows_port_owner",
                side_effect=[
                    {"status": "passed", "ok": True, "port": 8770, "listeners": [], "processes": [], "blockers": []},
                    {"status": "passed", "ok": True, "port": 443, "listeners": [], "processes": [], "blockers": []},
                ],
            ),
            mock.patch.object(
                diag,
                "smoke_public_initialize",
                return_value={"status": "passed", "ok": True, "blockers": [], "serverInfo": {"name": "riftreader_chatgpt_mcp"}},
            ),
        ):
            payload = diag.collect_domain_diagnostics(REPO_ROOT, public_host="mcp.360madden.com", write_caddyfile=True)

        caddyfile = payload["artifacts"]["generatedCaddyfile"]
        self.assertIsNotNone(caddyfile)
        self.assertTrue((REPO_ROOT / caddyfile).is_file())
        self.assertTrue(payload["caddy"]["writeCaddyfileRequested"])


if __name__ == "__main__":
    unittest.main()
