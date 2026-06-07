#!/usr/bin/env python3
"""Domain/proxy diagnostics for the RiftReader ChatGPT Web/Desktop MCP route.

This helper is intentionally status-only. It does not start Caddy, edit router
state, register ChatGPT, mutate Git, send RIFT input, or expose a control
endpoint. Generated Caddyfile plans and diagnostic summaries are written only
under ``.riftreader-local``.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from .common import find_repo_root, repo_rel as rel, safety_flags, timestamped_output_dir, utc_iso
    from .riftreader_chatgpt_mcp import DEFAULT_HOST, DEFAULT_PORT, SERVER_NAME
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.riftreader_chatgpt_mcp import DEFAULT_HOST, DEFAULT_PORT, SERVER_NAME


SCHEMA_VERSION = 1
MCP_PROTOCOL_VERSION = "2025-06-18"
DEFAULT_PUBLIC_HOST = "mcp.360madden.com"
DEFAULT_PUBLIC_PATH = "/mcp"
DEFAULT_OUTPUT_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "domain-diagnostics"
FAIL_HTTP_STATUSES = {403, 404, 421, 502}


def public_mcp_url(public_host: str, public_path: str = DEFAULT_PUBLIC_PATH) -> str:
    return f"https://{public_host}{public_path if public_path.startswith('/') else '/' + public_path}"


def caddyfile_text(public_host: str, backend_host: str = DEFAULT_HOST, backend_port: int = DEFAULT_PORT) -> str:
    return (
        f"{public_host} {{\n"
        "    encode zstd gzip\n"
        "    @mcp path /mcp\n"
        f"    reverse_proxy @mcp http://{backend_host}:{backend_port}\n"
        "}\n"
    )


def _socket_connect(host: str, port: int, timeout_seconds: float) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return {"ok": True, "host": host, "port": port, "durationSeconds": round(time.monotonic() - started, 3)}
    except OSError as exc:
        return {
            "ok": False,
            "host": host,
            "port": port,
            "durationSeconds": round(time.monotonic() - started, 3),
            "error": f"{type(exc).__name__}:{exc}",
        }


def check_dns(public_host: str) -> dict[str, Any]:
    try:
        infos = socket.getaddrinfo(public_host, 443, type=socket.SOCK_STREAM)
        addresses = sorted({info[4][0] for info in infos})
        return {"status": "passed", "ok": True, "host": public_host, "addresses": addresses}
    except OSError as exc:
        return {"status": "failed", "ok": False, "host": public_host, "addresses": [], "error": f"{type(exc).__name__}:{exc}"}


def _run(args: list[str], timeout_seconds: float = 5.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "args": args,
            "exitCode": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-4000:],
        }
    except Exception as exc:  # noqa: BLE001 - diagnostics must capture platform gaps.
        return {"args": args, "exitCode": None, "ok": False, "error": f"{type(exc).__name__}:{exc}"}


def check_windows_port_owner(port: int) -> dict[str, Any]:
    netstat = _run(["netstat", "-ano", "-p", "tcp"])
    rows: list[dict[str, Any]] = []
    pids: set[str] = set()
    if netstat.get("ok"):
        marker = f":{port}"
        for line in str(netstat.get("stdout") or "").splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].upper() == "TCP" and marker in parts[1]:
                row = {"protocol": parts[0], "local": parts[1], "foreign": parts[2], "state": parts[3], "pid": parts[4]}
                rows.append(row)
                pids.add(parts[4])
    processes: list[dict[str, str]] = []
    for pid in sorted(pids):
        task = _run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"])
        name = ""
        if task.get("ok"):
            line = str(task.get("stdout") or "").strip().splitlines()
            if line and line[0].startswith('"'):
                name = line[0].split('","', 1)[0].strip('"')
        processes.append({"pid": pid, "imageName": name})
    caddy_like = [proc for proc in processes if "caddy" in proc.get("imageName", "").lower()]
    status = "passed" if rows and (port != 443 or caddy_like) else ("blocked" if rows else "blocked")
    blockers: list[str] = []
    if not rows:
        blockers.append(f"tcp-{port}-listener-missing")
    if port == 443 and rows and not caddy_like:
        blockers.append("tcp-443-owner-not-caddy")
    return {
        "status": status if not blockers else "blocked",
        "ok": not blockers,
        "port": port,
        "listeners": rows,
        "processes": processes,
        "blockers": blockers,
        "commands": {"netstat": {key: netstat.get(key) for key in ("args", "exitCode", "ok", "error") if key in netstat}},
    }


def parse_mcp_initialize_response(text: str, content_type: str) -> dict[str, Any]:
    candidates: list[str] = []
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)
    if "text/event-stream" in content_type.lower() or "\ndata:" in text:
        for line in text.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    candidates.append(data)
    parse_errors: list[str] = []
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            parse_errors.append(f"JSONDecodeError:{exc}")
            continue
        if isinstance(payload, dict):
            return {"ok": True, "payload": payload}
    return {"ok": False, "payload": None, "parseErrors": parse_errors[-3:], "bodyPreview": stripped[:500]}


def validate_initialize_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["initialize-response-not-json-object"]
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    server_info = result.get("serverInfo") if isinstance(result.get("serverInfo"), dict) else {}
    blockers: list[str] = []
    if server_info.get("name") != SERVER_NAME:
        blockers.append(f"server-info-name-mismatch:{server_info.get('name')!r}")
    protocol = result.get("protocolVersion")
    if protocol not in (MCP_PROTOCOL_VERSION, None):
        blockers.append(f"protocol-version-mismatch:{protocol!r}")
    return blockers


def smoke_public_initialize(url: str, timeout_seconds: float = 15.0) -> dict[str, Any]:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "riftreader-domain-diagnostics", "version": "1.0.0"},
            },
        }
    ).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Origin": "https://chatgpt.com",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        },
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout_seconds, context=ssl.create_default_context()) as response:
            status_code = int(response.status)
            content_type = response.headers.get("Content-Type", "")
            text = response.read(512 * 1024).decode("utf-8", errors="replace")
    except HTTPError as exc:
        text = exc.read(64 * 1024).decode("utf-8", errors="replace")
        return {
            "status": "failed",
            "ok": False,
            "url": url,
            "httpStatus": exc.code,
            "contentType": exc.headers.get("Content-Type", ""),
            "durationSeconds": round(time.monotonic() - started, 3),
            "blockers": [f"public-mcp-http-status:{exc.code}"],
            "bodyPreview": text[:500],
            "request": {"protocolVersion": MCP_PROTOCOL_VERSION, "headerMcpProtocolVersion": MCP_PROTOCOL_VERSION},
        }
    except URLError as exc:
        return {
            "status": "failed",
            "ok": False,
            "url": url,
            "httpStatus": None,
            "durationSeconds": round(time.monotonic() - started, 3),
            "blockers": [f"public-mcp-url-error:{type(exc.reason).__name__ if hasattr(exc, 'reason') else type(exc).__name__}"],
            "error": str(exc),
            "request": {"protocolVersion": MCP_PROTOCOL_VERSION, "headerMcpProtocolVersion": MCP_PROTOCOL_VERSION},
        }
    parsed = parse_mcp_initialize_response(text, content_type)
    blockers: list[str] = []
    if status_code < 200 or status_code >= 300 or status_code in FAIL_HTTP_STATUSES:
        blockers.append(f"public-mcp-http-status:{status_code}")
    if not parsed.get("ok"):
        blockers.append("public-mcp-initialize-non-json")
    blockers.extend(validate_initialize_payload(parsed.get("payload")))
    return {
        "status": "passed" if not blockers else "failed",
        "ok": not blockers,
        "url": url,
        "httpStatus": status_code,
        "contentType": content_type,
        "durationSeconds": round(time.monotonic() - started, 3),
        "serverInfo": ((parsed.get("payload") or {}).get("result") or {}).get("serverInfo")
        if isinstance(parsed.get("payload"), dict)
        else None,
        "blockers": blockers,
        "bodyPreview": text[:500] if blockers else "",
        "request": {"protocolVersion": MCP_PROTOCOL_VERSION, "headerMcpProtocolVersion": MCP_PROTOCOL_VERSION},
    }


def collect_domain_diagnostics(
    repo_root: Path,
    *,
    public_host: str = DEFAULT_PUBLIC_HOST,
    backend_host: str = DEFAULT_HOST,
    backend_port: int = DEFAULT_PORT,
    timeout_seconds: float = 15.0,
    write_caddyfile: bool = False,
    run_public_smoke: bool = True,
) -> dict[str, Any]:
    output_dir = timestamped_output_dir(repo_root / DEFAULT_OUTPUT_ROOT)
    caddyfile = output_dir / "Caddyfile"
    caddyfile.write_text(caddyfile_text(public_host, backend_host, backend_port), encoding="utf-8")
    url = public_mcp_url(public_host)
    dns = check_dns(public_host)
    backend_connect = _socket_connect(backend_host, backend_port, min(timeout_seconds, 5.0))
    tcp443_connect = _socket_connect(public_host, 443, min(timeout_seconds, 5.0))
    backend_owner = check_windows_port_owner(backend_port)
    tcp443_owner = check_windows_port_owner(443)
    public_smoke = smoke_public_initialize(url, timeout_seconds=timeout_seconds) if run_public_smoke else {
        "status": "skipped",
        "ok": None,
        "blockers": [],
        "warnings": ["public smoke skipped by operator flag"],
    }
    blockers: list[str] = []
    warnings: list[str] = []
    if not dns.get("ok"):
        blockers.append("dns-resolution-failed")
    if not backend_connect.get("ok"):
        blockers.append("backend-127001-8770-not-reachable")
    if not tcp443_connect.get("ok"):
        blockers.append("public-tcp-443-not-reachable")
    if tcp443_owner.get("listeners") and not tcp443_owner.get("ok"):
        blockers.extend(tcp443_owner.get("blockers") or [])
    elif not tcp443_owner.get("listeners"):
        warnings.append("tcp-443-owner-not-local-or-not-visible; this is normal when 443 terminates off-host")
    if run_public_smoke and not public_smoke.get("ok"):
        blockers.extend(public_smoke.get("blockers") or ["public-mcp-smoke-failed"])
    status = "passed" if not blockers else "blocked"
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-domain-diagnostics",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": not blockers,
        "publicMcpUrl": url,
        "publicHost": public_host,
        "backend": {"host": backend_host, "port": backend_port, "connect": backend_connect, "owner": backend_owner},
        "dns": dns,
        "tcp443": {"connect": tcp443_connect, "owner": tcp443_owner},
        "caddy": {
            "expectedProcessName": "caddy.exe",
            "generatedCaddyfile": rel(repo_root, caddyfile),
            "installedCaddyfile": rel(repo_root, repo_root / "Caddyfile") if (repo_root / "Caddyfile").exists() else None,
            "writeCaddyfileRequested": write_caddyfile,
        },
        "publicSmoke": public_smoke,
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": {
            "summaryJson": rel(repo_root, output_dir / "summary.json"),
            "summaryMarkdown": rel(repo_root, output_dir / "summary.md"),
            "generatedCaddyfile": rel(repo_root, caddyfile),
        },
        "safety": {
            **safety_flags(),
            "statusOnly": True,
            "serverStarted": False,
            "caddyStarted": False,
            "routerConfigured": False,
            "chatGptRegistrationPerformed": False,
            "publicSmokeOnly": run_public_smoke,
            "writesUnderRiftreaderLocalOnly": True,
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# RiftReader MCP Domain Diagnostics",
        "",
        f"- Generated UTC: `{payload.get('generatedAtUtc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Public MCP URL: `{payload.get('publicMcpUrl')}`",
        f"- Backend: `{payload.get('backend', {}).get('host')}:{payload.get('backend', {}).get('port')}`",
        f"- DNS: `{payload.get('dns', {}).get('status')}`",
        f"- Public smoke: `{payload.get('publicSmoke', {}).get('status')}`",
        "",
        "## Blockers",
        "",
    ]
    for blocker in payload.get("blockers") or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Warnings", ""])
    for warning in payload.get("warnings") or ["none"]:
        lines.append(f"- `{warning}`")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Status-only RiftReader ChatGPT MCP domain/proxy diagnostics.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--public-mcp-host", default=DEFAULT_PUBLIC_HOST)
    parser.add_argument("--backend-host", default=DEFAULT_HOST)
    parser.add_argument("--backend-port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--skip-public-smoke", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    payload = collect_domain_diagnostics(
        repo_root,
        public_host=args.public_mcp_host,
        backend_host=args.backend_host,
        backend_port=args.backend_port,
        timeout_seconds=args.timeout_seconds,
        run_public_smoke=not args.skip_public_smoke,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
