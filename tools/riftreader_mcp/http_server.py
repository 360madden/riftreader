#!/usr/bin/env python3
# Version: riftreader-mcp-http-server-v0.1.2
# Purpose: Read-only local HTTP MCP server for Cloudflare-tunneled ChatGPT access.

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from tools.riftreader_mcp.auth import authorize, token_fingerprint
from tools.riftreader_mcp.config import PROTOCOL_VERSION, VERSION, McpHttpConfig, ensure_local_config, load_config
from tools.riftreader_mcp.logging_util import write_log
from tools.riftreader_mcp.readonly_tools import ReadOnlyToolError, RiftReaderReadOnlyTools


SUPPORTED_PROTOCOL_VERSIONS = {PROTOCOL_VERSION, "2025-03-26"}
MCP_PROTOCOL_HEADER = "MCP-Protocol-Version"


def json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def mcp_text_result(payload: Any, *, is_error: bool = False) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}], "isError": bool(is_error)}
    if isinstance(payload, dict):
        result["structuredContent"] = payload
    return result


class RiftReaderHttpMcpHandler(BaseHTTPRequestHandler):
    server: "RiftReaderHttpServer"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        write_log(self.server.config, "http_message", {"client": self.client_address[0], "message": format % args})

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._send_common_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_empty(self, status: int, *, allow: str | None = None) -> None:
        self.send_response(status)
        if allow:
            self.send_header("Allow", allow)
        self._send_common_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_common_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(MCP_PROTOCOL_HEADER, PROTOCOL_VERSION)
        self.send_header("Vary", "Origin")
        origin = self.headers.get("Origin")
        if origin and self.server.origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin.strip().rstrip("/"))

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if self.server.origin_allowed(origin):
            return True
        write_log(self.server.config, "origin_rejected", {"path": self.path, "origin": origin, "client": self.client_address[0]})
        self._send_json(
            HTTPStatus.FORBIDDEN,
            {"ok": False, "status": "origin_rejected", "message": "Origin is not allowed for this local MCP server."},
        )
        return False

    def _protocol_version_ok(self) -> bool:
        raw_version = self.headers.get(MCP_PROTOCOL_HEADER)
        if not raw_version:
            return True
        version = raw_version.strip()
        if version in SUPPORTED_PROTOCOL_VERSIONS:
            return True
        write_log(self.server.config, "protocol_version_rejected", {"path": self.path, "protocolVersion": version, "client": self.client_address[0]})
        self._send_json(HTTPStatus.BAD_REQUEST, self.server.error_response(None, -32000, f"Unsupported {MCP_PROTOCOL_HEADER}: {version}"))
        return False

    def _transport_ok(self) -> bool:
        return self._origin_ok() and self._protocol_version_ok()

    def _authorized(self) -> bool:
        result = authorize(self.server.config, self.headers)
        if result.ok:
            return True
        write_log(self.server.config, "auth_failed", {"path": self.path, "status": result.status, "client": self.client_address[0]})
        self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "status": result.status, "message": result.message})
        return False

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self._origin_ok():
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_common_headers()
        self.send_header("Access-Control-Allow-Headers", f"Authorization, X-RiftReader-MCP-Token, Content-Type, Accept, {MCP_PROTOCOL_HEADER}")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._transport_ok():
            return
        if self.path.rstrip("/") == "/mcp":
            self._send_empty(HTTPStatus.METHOD_NOT_ALLOWED, allow="POST, OPTIONS")
            return
        if self.path.rstrip("/") not in {"/health", "/healthz"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "status": "not_found", "message": "Use /health or POST /mcp."})
            return
        if not self._authorized():
            return
        payload = self.server.tools.health({})
        write_log(self.server.config, "health", {"status": "ok", "client": self.client_address[0]})
        self._send_json(HTTPStatus.OK, payload)

    def do_POST(self) -> None:  # noqa: N802
        if not self._transport_ok():
            return
        if self.path.rstrip("/") != "/mcp":
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "status": "not_found", "message": "Use POST /mcp."})
            return
        if not self._authorized():
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            request = json.loads(body.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("JSON-RPC request must be an object.")
            response = self.server.handle_jsonrpc(request)
            if response is None:
                self._send_empty(HTTPStatus.ACCEPTED)
            else:
                self._send_json(HTTPStatus.OK, response)
        except json.JSONDecodeError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, self.server.error_response(None, -32700, f"Parse error: {exc}"))
        except Exception as exc:  # noqa: BLE001
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, self.server.error_response(None, -32000, f"{type(exc).__name__}: {exc}"))


class RiftReaderHttpServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], config: McpHttpConfig) -> None:
        super().__init__(server_address, RiftReaderHttpMcpHandler)
        self.config = config
        self.tools = RiftReaderReadOnlyTools(config)

    def origin_allowed(self, origin: str | None) -> bool:
        if not origin or not self.config.validate_origin:
            return True
        normalized = origin.strip().rstrip("/")
        if normalized in self.config.allowed_origins:
            return True
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").lower()
        return parsed.scheme in {"http", "https"} and host in {"127.0.0.1", "localhost", "::1"}

    @staticmethod
    def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def handle_jsonrpc(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") if isinstance(request.get("params"), dict) else {}
        if request.get("jsonrpc") != "2.0":
            return self.error_response(request_id, -32600, "Invalid JSON-RPC version")
        if request_id is None and isinstance(method, str) and method.startswith("notifications/"):
            return None
        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "riftreader-mcp-http", "title": "RiftReader Local Repo MCP", "version": VERSION},
                        "instructions": (
                            "Use only the advertised read-only RiftReader tools. This server cannot write files, run shell "
                            "commands, stage/commit/push Git changes, or interact with RIFT/game/debugger state."
                        ),
                    },
                }
            if method == "ping":
                return {"jsonrpc": "2.0", "id": request_id, "result": {}}
            if method == "tools/list":
                return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": self.tools.definitions()}}
            if method == "tools/call":
                name = str(params.get("name") or "")
                arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
                return {"jsonrpc": "2.0", "id": request_id, "result": mcp_text_result(self.tools.call(name, arguments))}
            return self.error_response(request_id, -32601, f"Method not found: {method}")
        except ReadOnlyToolError as exc:
            return self.error_response(request_id, -32602, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self.error_response(request_id, -32000, f"{type(exc).__name__}: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the read-only RiftReader HTTP MCP server.")
    parser.add_argument("--repo", default=None)
    parser.add_argument("--config")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--init-local-config", action="store_true", help="Create .riftreader-local/mcp/config.json with a generated token, then exit.")
    parser.add_argument("--force-init-local-config", action="store_true", help="Replace the local config token. Use only if rotating auth.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.init_local_config or args.force_init_local_config:
        result = ensure_local_config(args.repo, force=args.force_init_local_config)
        print(json.dumps(result, indent=2))
        return 0

    config = load_config(repo=args.repo, config_path=args.config, host=args.host, port=args.port)
    if config.require_auth and not config.token:
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": "auth_token_not_configured",
                    "message": "Token auth is required. Run scripts\\start_mcp_local.cmd once to create local config, or set RIFTREADER_MCP_TOKEN.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    server = RiftReaderHttpServer((config.host, config.port), config)
    startup = {
        "ok": True,
        "status": "listening",
        "version": VERSION,
        "url": f"http://{config.host}:{config.port}",
        "mcpUrl": f"http://{config.host}:{config.port}/mcp",
        "healthUrl": f"http://{config.host}:{config.port}/health",
        "repoRoot": str(config.repo_root) if config.expose_repo_root else None,
        "authRequired": config.require_auth,
        "tokenConfigured": bool(config.token),
        "tokenFingerprint": token_fingerprint(config.token),
        "enabledTools": list(config.enabled_tools),
        "originValidationEnabled": config.validate_origin,
        "allowedOrigins": list(config.allowed_origins),
        "logs": str(config.log_root),
    }
    write_log(config, "startup", startup)
    print(json.dumps(startup, indent=2))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
