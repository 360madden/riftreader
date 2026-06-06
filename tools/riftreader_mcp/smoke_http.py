#!/usr/bin/env python3
# Version: riftreader-mcp-http-smoke-v0.1.1
# Purpose: Local and optional public smoke tests for the RiftReader HTTP MCP adapter.

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from tools.riftreader_mcp.config import TOKEN_ENV_VAR, default_repo_root, load_config, runtime_root
from tools.riftreader_mcp.logging_util import utc_iso, utc_stamp
from tools.riftreader_mcp.readonly_tools import RiftReaderReadOnlyTools
from tools.riftreader_mcp.config import McpHttpConfig


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(url: str, *, token: str, payload: dict[str, Any] | None = None, timeout: float = 5.0) -> tuple[int, dict[str, Any]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="GET" if data is None else "POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", "RiftReader-MCP-Smoke/0.1")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - operator-requested local/public smoke.
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return int(exc.code), parsed


def request_raw(url: str, *, token: str, payload: dict[str, Any] | None = None, method: str | None = None, timeout: float = 5.0) -> tuple[int, bytes, dict[str, str]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method or ("GET" if data is None else "POST"))
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", "RiftReader-MCP-Smoke/0.1")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - operator-requested local/public smoke.
            return int(response.status), response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(), dict(exc.headers.items())


def direct_missing_handoff_check() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="riftreader-mcp-missing-handoff-") as raw:
        repo = Path(raw)
        (repo / ".git").mkdir()
        config = McpHttpConfig(repo_root=repo, token="not-used")
        payload = RiftReaderReadOnlyTools(config).get_latest_handoff({})
        return {"status": payload.get("status"), "ok": payload.get("ok") is True}


def start_server(repo: Path, *, port: int, token: str) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env[TOKEN_ENV_VAR] = token
    return subprocess.Popen(
        [sys.executable, "-m", "tools.riftreader_mcp.http_server", "--repo", str(repo), "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(repo),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_local_smoke(repo: Path) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    port = find_free_port()
    proc = start_server(repo, port=port, token=token)
    base = f"http://127.0.0.1:{port}"
    checks: list[dict[str, Any]] = []
    try:
        deadline = time.time() + 15
        health: tuple[int, dict[str, Any]] | None = None
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                health = request_json(f"{base}/health", token=token)
                if health[0] == 200:
                    break
            except OSError:
                time.sleep(0.25)
        checks.append({"name": "server_starts_and_health_works", "passed": bool(health and health[0] == 200), "statusCode": health[0] if health else None})

        tools_list = request_json(base + "/mcp", token=token, payload={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = [item.get("name") for item in tools_list[1].get("result", {}).get("tools", [])]
        checks.append({"name": "tools_list_has_readonly_allowlist", "passed": set(names) == {"health", "get_repo_status", "get_latest_handoff"}, "tools": names})
        tool_defs = tools_list[1].get("result", {}).get("tools", [])
        checks.append(
            {
                "name": "tools_list_has_chatgpt_guidance_and_output_schemas",
                "passed": all(
                    isinstance(item, dict)
                    and isinstance(item.get("description"), str)
                    and "Use this when" in item["description"]
                    and isinstance(item.get("inputSchema"), dict)
                    and isinstance(item.get("outputSchema"), dict)
                    for item in tool_defs
                ),
            }
        )

        repo_status = request_json(
            base + "/mcp",
            token=token,
            payload={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_repo_status", "arguments": {}}},
        )
        checks.append({"name": "get_repo_status_works", "passed": repo_status[0] == 200 and "result" in repo_status[1]})
        repo_status_result = repo_status[1].get("result", {})
        checks.append(
            {
                "name": "tool_result_has_structured_content",
                "passed": isinstance(repo_status_result.get("structuredContent"), dict)
                and repo_status_result["structuredContent"].get("ok") is True
                and isinstance(repo_status_result.get("content"), list),
            }
        )

        handoff = request_json(
            base + "/mcp",
            token=token,
            payload={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_latest_handoff", "arguments": {"maxChars": 4000}}},
        )
        checks.append({"name": "get_latest_handoff_present_or_clean", "passed": handoff[0] == 200 and "result" in handoff[1]})

        missing = direct_missing_handoff_check()
        checks.append({"name": "get_latest_handoff_missing_case", "passed": missing.get("ok") and missing.get("status") == "missing", "directToolStatus": missing})

        wrong_auth = request_json(f"{base}/health", token="wrong-token")
        checks.append({"name": "wrong_auth_fails_closed", "passed": wrong_auth[0] == 401 and wrong_auth[1].get("status") == "auth_invalid", "statusCode": wrong_auth[0]})

        notification = request_raw(base + "/mcp", token=token, payload={"jsonrpc": "2.0", "method": "notifications/initialized"})
        checks.append(
            {
                "name": "notification_returns_accepted_empty_body",
                "passed": notification[0] == 202 and notification[1] == b"",
                "statusCode": notification[0],
                "bodyBytes": len(notification[1]),
            }
        )

        get_mcp = request_raw(base + "/mcp", token=token)
        checks.append({"name": "get_mcp_without_sse_is_405", "passed": get_mcp[0] == 405, "statusCode": get_mcp[0]})

        serialized = json.dumps({"checks": checks, "health": health[1] if health else None, "toolsList": tools_list[1]})
        checks.append({"name": "no_secret_in_smoke_output", "passed": token not in serialized})
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    return {
        "baseUrl": base,
        "status": "passed" if all(item.get("passed") for item in checks) else "failed",
        "checks": checks,
    }


def run_public_check(public_url: str, token: str) -> dict[str, Any]:
    base = public_url.rstrip("/")
    checks: list[dict[str, Any]] = []
    try:
        health = request_json(base + "/health", token=token, timeout=10)
        checks.append({"name": "public_health", "passed": health[0] == 200, "statusCode": health[0], "status": health[1].get("status")})
        tools = request_json(base + "/mcp", token=token, payload={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, timeout=10)
        tool_defs = tools[1].get("result", {}).get("tools", [])
        tool_names = [item.get("name") for item in tool_defs if isinstance(item, dict)]
        checks.append(
            {
                "name": "public_tools_list",
                "passed": tools[0] == 200 and set(tool_names) == {"health", "get_repo_status", "get_latest_handoff"},
                "statusCode": tools[0],
                "tools": tool_names,
            }
        )
        checks.append(
            {
                "name": "public_tools_have_chatgpt_guidance_and_output_schemas",
                "passed": all(
                    isinstance(item, dict)
                    and isinstance(item.get("description"), str)
                    and "Use this when" in item["description"]
                    and isinstance(item.get("outputSchema"), dict)
                    for item in tool_defs
                ),
            }
        )
        repo_status = request_json(
            base + "/mcp",
            token=token,
            payload={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_repo_status", "arguments": {}}},
            timeout=10,
        )
        repo_result = repo_status[1].get("result", {})
        checks.append(
            {
                "name": "public_tool_result_has_structured_content",
                "passed": repo_status[0] == 200 and isinstance(repo_result.get("structuredContent"), dict) and repo_result["structuredContent"].get("ok") is True,
                "statusCode": repo_status[0],
            }
        )
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "public_route_reachable", "passed": False, "error": f"{type(exc).__name__}: {exc}"})
    return {"publicUrl": public_url, "status": "passed" if all(item.get("passed") for item in checks) else "failed", "checks": checks}


def write_summary(repo: Path, payload: dict[str, Any]) -> Path:
    out_dir = runtime_root(repo) / "smoke" / utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "summary.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out_dir / "summary.md").write_text(
        "# RiftReader MCP HTTP Smoke\n\n"
        f"- Status: `{payload['status']}`\n"
        f"- Generated: `{payload['generatedAtUtc']}`\n"
        f"- Checks: `{sum(1 for c in payload['local']['checks'] if c.get('passed'))}/{len(payload['local']['checks'])}` local passed\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test the read-only RiftReader HTTP MCP adapter.")
    parser.add_argument("--repo", default=str(default_repo_root()))
    parser.add_argument("--public-url", help="Optional public tunnel URL, for example https://mcp.360madden.com")
    parser.add_argument("--public-token", help="Token for public check. Prefer RIFTREADER_MCP_TOKEN or local config instead of this argument.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    local = run_local_smoke(repo)
    public = None
    public_token = args.public_token or os.environ.get(TOKEN_ENV_VAR)
    if args.public_url and not public_token:
        try:
            public_token = load_config(repo=repo).token
        except Exception:
            public_token = None
    if args.public_url:
        if public_token:
            public = run_public_check(args.public_url, public_token)
        else:
            public = {"publicUrl": args.public_url, "status": "blocked", "checks": [{"name": "public_token_configured", "passed": False, "status": "auth_missing"}]}
    payload = {
        "version": "riftreader-mcp-http-smoke-v0.1.1",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if local["status"] == "passed" and (public is None or public["status"] == "passed") else "failed",
        "local": local,
        "public": public,
    }
    path = write_summary(repo, payload)
    payload["summaryJson"] = str(path)
    print(json.dumps(payload, indent=2))
    print("PASS" if payload["status"] == "passed" else "FAIL")
    print("END_RIFTREADER_MCP_HTTP_SMOKE")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
