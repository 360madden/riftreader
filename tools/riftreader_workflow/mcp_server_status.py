#!/usr/bin/env python3
"""Read-only current-lane MCP backend process classifier.

This helper exists because "port 8770 is busy" and "the ChatGPT connector is
configured" are not enough proof that the current RiftReader ChatGPT MCP server
is actually running.  It classifies the loopback listener by process command
line and fails closed for missing, foreign, or legacy listeners.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, safety_flags, utc_iso
    from .mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
    from .riftreader_chatgpt_mcp import DEFAULT_HOST, DEFAULT_PORT, ensure_mcp_sdk_available, run_transport_client_once
except ImportError:  # pragma: no cover - direct script execution fallback.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, utc_iso
    from riftreader_workflow.mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
    from riftreader_workflow.riftreader_chatgpt_mcp import DEFAULT_HOST, DEFAULT_PORT, ensure_mcp_sdk_available, run_transport_client_once


SCHEMA_VERSION = 1
VERSION = "riftreader-mcp-server-status-v0.1.0"
CURRENT_SERVER_MARKER = "riftreader_chatgpt_mcp.py"
LEGACY_MODULE_MARKER = "tools.riftreader_mcp.http_server"
LEGACY_FILE_MARKER = "riftreader_mcp/http_server.py"
RUNTIME_SURFACE_TIMEOUT_SECONDS = 8.0


def normalize_command_line(value: str) -> str:
    return value.replace("\\", "/").replace('"', "").lower()


def _argument_after(command_line: str, flag: str) -> str | None:
    pattern = re.compile(rf"(?:^|\s){re.escape(flag)}(?:=|\s+)([^\s]+)", re.IGNORECASE)
    match = pattern.search(command_line)
    return match.group(1).strip('"') if match else None


def classify_command_line(command_line: str) -> dict[str, Any]:
    normalized = normalize_command_line(command_line)
    is_current = CURRENT_SERVER_MARKER in normalized and "--serve" in normalized
    is_legacy = LEGACY_MODULE_MARKER in normalized or LEGACY_FILE_MARKER in normalized
    profile = _argument_after(command_line, "--tool-profile")
    transport = _argument_after(command_line, "--transport")
    allowed_host = _argument_after(command_line, "--allowed-host")
    allowed_origin = _argument_after(command_line, "--allowed-origin")
    if is_current:
        lane = "current-chatgpt-mcp"
    elif is_legacy:
        lane = "legacy-tokenized-http-mcp"
    else:
        lane = "foreign-or-unknown"
    return {
        "lane": lane,
        "isCurrentChatGptMcpServer": is_current,
        "isLegacyHttpMcpServer": is_legacy,
        "toolProfile": profile,
        "transport": transport,
        "allowedHost": allowed_host,
        "allowedOrigin": allowed_origin,
        "fullProfileReady": bool(is_current and profile == "full"),
    }


def query_windows_listeners(host: str, port: int, *, timeout_seconds: int = 10) -> dict[str, Any]:
    host_json = json.dumps(host)
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$items = @()
$connections = @(Get-NetTCPConnection -LocalAddress {host_json} -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue)
foreach ($conn in $connections) {{
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
  $items += [ordered]@{{
    localAddress = [string]$conn.LocalAddress
    localPort = [int]$conn.LocalPort
    state = [string]$conn.State
    owningProcess = [int]$conn.OwningProcess
    processExists = ($null -ne $proc)
    processName = if ($null -eq $proc) {{ $null }} else {{ [string]$proc.Name }}
    executablePath = if ($null -eq $proc) {{ $null }} else {{ [string]$proc.ExecutablePath }}
    commandLine = if ($null -eq $proc) {{ $null }} else {{ [string]$proc.CommandLine }}
  }}
}}
[ordered]@{{
  ok = $true
  exists = ($items.Count -gt 0)
  host = {host_json}
  port = {int(port)}
  listeners = $items
}} | ConvertTo-Json -Depth 6 -Compress
"""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exists": False,
            "host": host,
            "port": port,
            "listeners": [],
            "queryTimedOut": True,
            "error": f"TimeoutExpired:{exc}",
        }
    if completed.returncode != 0:
        return {
            "ok": False,
            "exists": False,
            "host": host,
            "port": port,
            "listeners": [],
            "exitCode": completed.returncode,
            "stderr": completed.stderr[-1000:],
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "exists": False,
            "host": host,
            "port": port,
            "listeners": [],
            "error": f"JSONDecodeError:{exc}",
            "stdout": completed.stdout[-1000:],
        }
    return payload if isinstance(payload, dict) else {"ok": False, "exists": False, "listeners": []}


def _redact_repo_root(value: Any, repo_root: Path) -> Any:
    root = str(repo_root.resolve())
    root_posix = root.replace("\\", "/")
    if isinstance(value, str):
        return value.replace(root, ".").replace(root_posix, ".")
    if isinstance(value, list):
        return [_redact_repo_root(item, repo_root) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_repo_root(item, repo_root) for key, item in value.items()}
    return value


def _compact_exception(exc: BaseException) -> str:
    text = f"{type(exc).__name__}:{exc}"
    return text if len(text) <= 800 else text[:797] + "..."


def probe_runtime_surface(
    repo_root: Path,
    host: str,
    port: int,
    *,
    timeout_seconds: float = RUNTIME_SURFACE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Probe the live MCP runtime, not just the process command line.

    A stale long-running Python process can still have the right
    ``riftreader_chatgpt_mcp.py --serve`` command line while exposing an older
    loaded tool surface.  This read-only probe lists tools and calls ``health``
    over the live streamable-HTTP backend so status fails closed before proof.
    """

    url = f"http://{host}:{int(port)}/mcp"
    progress: dict[str, Any] = {}
    try:
        sdk_path_additions = ensure_mcp_sdk_available(repo_root)
        client = asyncio.run(
            asyncio.wait_for(
                run_transport_client_once(
                    url,
                    package_proposal=None,
                    client_read_timeout_seconds=max(1.0, timeout_seconds),
                    progress=progress,
                ),
                timeout=timeout_seconds,
            )
        )
    except Exception as exc:  # noqa: BLE001 - status must report, not crash.
        return {
            "status": "failed",
            "ok": False,
            "url": url,
            "error": _compact_exception(exc),
            "clientProgress": progress,
            "blockers": ["runtime-surface-probe-failed"],
        }

    expected_names = list(EXPECTED_CHATGPT_MCP_TOOL_NAMES)
    observed_names = [str(name) for name in client.get("toolNames") or []]
    health = client.get("healthStructuredContent") if isinstance(client.get("healthStructuredContent"), dict) else {}
    health_tool_names = [
        str(tool.get("name"))
        for tool in health.get("tools", [])
        if isinstance(tool, dict) and isinstance(tool.get("name"), str)
    ]
    blockers: list[str] = []
    if client.get("toolCount") != EXPECTED_CHATGPT_MCP_TOOL_COUNT:
        blockers.append(f"runtime-tool-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:{client.get('toolCount')!r}")
    if observed_names != expected_names:
        blockers.append("runtime-tool-names-not-expected")
    if health.get("toolCount") != EXPECTED_CHATGPT_MCP_TOOL_COUNT:
        blockers.append(f"runtime-health-tool-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:{health.get('toolCount')!r}")
    if health_tool_names and health_tool_names != expected_names:
        blockers.append("runtime-health-tool-names-not-expected")
    if client.get("healthIsError"):
        blockers.append("runtime-health-call-is-error")

    return {
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "url": url,
        "expectedToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "observedToolCount": client.get("toolCount"),
        "expectedToolNames": expected_names,
        "observedToolNames": observed_names,
        "healthToolCount": health.get("toolCount"),
        "healthToolNames": health_tool_names,
        "healthVersion": health.get("version"),
        "sdkPathAdditions": sdk_path_additions,
        "clientStepTimings": client.get("clientStepTimings", []),
        "blockers": blockers,
    }


def build_status_payload(
    repo_root: Path,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    listener_query: dict[str, Any] | None = None,
    runtime_surface_probe: dict[str, Any] | None = None,
    check_runtime_surface: bool = True,
) -> dict[str, Any]:
    query = listener_query if listener_query is not None else query_windows_listeners(host, port)
    listeners = query.get("listeners") if isinstance(query.get("listeners"), list) else []
    classified_listeners: list[dict[str, Any]] = []
    for listener in listeners:
        if not isinstance(listener, dict):
            continue
        classification = classify_command_line(str(listener.get("commandLine") or ""))
        classified_listeners.append({**listener, "classification": classification})

    current = next(
        (item for item in classified_listeners if item["classification"]["isCurrentChatGptMcpServer"]),
        None,
    )
    legacy = next((item for item in classified_listeners if item["classification"]["isLegacyHttpMcpServer"]), None)
    blockers: list[str] = []
    warnings: list[str] = []
    if not query.get("ok", True):
        status = "blocked-query-failed"
        blockers.append("local-mcp-server-listener-query-failed")
    elif current is not None:
        profile = current["classification"].get("toolProfile")
        status = "running-current"
        if profile != "full":
            warnings.append(f"current-mcp-server-not-full-profile:{profile or 'unknown'}")
    elif legacy is not None:
        status = "running-legacy"
        blockers.append("current-chatgpt-mcp-server-not-running:legacy-server-listening")
    elif classified_listeners:
        status = "foreign-listener"
        blockers.append(f"local-backend-port-foreign-listener:{port}")
    else:
        status = "not-running"
        blockers.append(f"local-backend-not-running:{host}:{port}")

    selected = current or legacy or (classified_listeners[0] if classified_listeners else None)
    selected_classification = selected.get("classification") if isinstance(selected, dict) else {}
    runtime_surface: dict[str, Any] = {
        "status": "not-checked",
        "ok": None,
        "reason": "no-current-full-profile-listener",
    }
    if current is not None and selected_classification.get("toolProfile") == "full":
        if not check_runtime_surface:
            runtime_surface = {
                "status": "skipped",
                "ok": None,
                "reason": "runtime-surface-check-disabled",
            }
        else:
            runtime_surface = (
                runtime_surface_probe
                if runtime_surface_probe is not None
                else probe_runtime_surface(repo_root, host, port)
            )
            if not runtime_surface.get("ok"):
                status = "running-stale-runtime"
                blockers.append("current-chatgpt-mcp-server-runtime-surface-not-current")
                for blocker in runtime_surface.get("blockers", []):
                    blockers.append(str(blocker))
    connector_note = "saved-chatgpt-connector-config-does-not-start-local-backend"
    sequence = [
        {
            "key": "saved-connector-is-not-runtime",
            "status": "info",
            "ok": True,
            "why": connector_note,
        },
        {
            "key": "loopback-listener",
            "status": "passed" if classified_listeners else "blocked",
            "ok": bool(classified_listeners),
            "why": f"{host}:{port} must have a listening process before ChatGPT can reach the backend.",
        },
        {
            "key": "listener-identity",
            "status": "passed" if current is not None else "blocked",
            "ok": current is not None,
            "why": "The listener command line must be the current riftreader_chatgpt_mcp.py --serve adapter, not a legacy or foreign process.",
        },
        {
            "key": "tool-profile",
            "status": "passed"
            if selected_classification.get("toolProfile") == "full"
            else "warning"
            if current is not None
            else "blocked",
            "ok": selected_classification.get("toolProfile") == "full",
            "why": f"Final {EXPECTED_CHATGPT_MCP_TOOL_COUNT}-tool proof requires --tool-profile full; read-only profile is only for Phase 0 domain checks.",
        },
        {
            "key": "runtime-loaded-tool-surface",
            "status": runtime_surface.get("status"),
            "ok": runtime_surface.get("ok"),
            "why": (
                "The live MCP list_tools and health response must match the current expected "
                f"{EXPECTED_CHATGPT_MCP_TOOL_COUNT}-tool surface; a saved connector or matching process command line is not enough."
            ),
        },
        {
            "key": "public-route-forwarding",
            "status": "not-checked",
            "ok": None,
            "why": "After local backend passes, verify Cloudflare named Tunnel/public route separately.",
        },
        {
            "key": "actual-client-proof",
            "status": "not-checked",
            "ok": None,
            "why": "After route passes, verify from actual ChatGPT/MCP connector health and proof replay.",
        },
    ]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-server-status",
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": current is not None and not blockers,
        "host": host,
        "port": port,
        "localMcpUrl": f"http://{host}:{port}/mcp",
        "selectedListener": selected,
        "listeners": classified_listeners,
        "runtimeSurface": runtime_surface,
        "blockers": blockers,
        "warnings": warnings,
        "dependencySequence": sequence,
        "operatorRule": connector_note,
        "safety": {
            **safety_flags(),
            "readOnlyStatus": True,
            "runtimeSurfaceChecked": bool(check_runtime_surface and current is not None),
            "serverStarted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
        },
    }
    return _redact_repo_root(payload, repo_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify the current RiftReader ChatGPT MCP backend listener.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--skip-runtime-surface-check",
        action="store_true",
        help="Only classify the listener process; intended for narrow diagnostics/tests, not proof readiness.",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    payload = build_status_payload(
        repo_root,
        host=args.host,
        port=args.port,
        check_runtime_surface=not args.skip_runtime_surface_check,
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
