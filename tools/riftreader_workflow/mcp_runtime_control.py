#!/usr/bin/env python3
"""Guarded runtime-control helpers for the RiftReader ChatGPT MCP lane.

These helpers intentionally operate on the narrow, fixed local MCP adapter only.
They do not accept arbitrary commands, shell snippets, paths, tunnel tokens, or
live RIFT actions.  The mutating restart flow is split into read-only preflight
and token-gated scheduling so a ChatGPT MCP call can return before the server is
stopped.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from .common import safety_flags, utc_iso
    from .mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import safety_flags, utc_iso
    from riftreader_workflow.mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES


SCHEMA_VERSION = 1
VERSION = "riftreader-mcp-runtime-control-v0.1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8770
DEFAULT_PUBLIC_MCP_URL = "https://mcp.360madden.com/mcp"
ROOT_LAUNCHER = "START_RIFTREADER_CHATGPT_MCP.cmd"
RESTART_ARTIFACT_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "runtime-control"
TOKEN_PREFIX = "MCPRESTART"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def approval_token_for_facts(approval_facts: dict[str, Any]) -> str:
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-runtime-restart-approval-token",
        "facts": approval_facts,
    }
    digest = sha256_text(_canonical_json(payload))
    return f"{TOKEN_PREFIX}-{digest[:16]}"


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _runtime_status(repo_root: Path, *, check_runtime_surface: bool = False, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict[str, Any]:
    try:
        from . import mcp_server_status
    except ImportError:  # pragma: no cover - direct script execution.
        from riftreader_workflow import mcp_server_status

    return mcp_server_status.build_status_payload(
        repo_root,
        host=host,
        port=port,
        check_runtime_surface=check_runtime_surface,
    )


def _proof_status(repo_root: Path) -> dict[str, Any]:
    try:
        from . import mcp_proof_replay
    except ImportError:  # pragma: no cover - direct script execution.
        from riftreader_workflow import mcp_proof_replay

    return mcp_proof_replay.replay_actual_client_proof(repo_root)


def _normalize_tool_names(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    names = [str(item) for item in value if isinstance(item, str)]
    return names if len(names) == len(value) else None


def _surface_comparison(expected: list[str], observed: list[str] | None) -> dict[str, Any]:
    if observed is None:
        return {
            "status": "not-checked",
            "ok": None,
            "reason": "observed-tool-names-unavailable",
            "expectedCount": len(expected),
            "observedCount": None,
            "missing": [],
            "extra": [],
            "orderMatches": None,
        }
    missing = [name for name in expected if name not in observed]
    extra = [name for name in observed if name not in expected]
    order_matches = observed == expected
    ok = not missing and not extra and order_matches
    return {
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "expectedCount": len(expected),
        "observedCount": len(observed),
        "missing": missing,
        "extra": extra,
        "orderMatches": order_matches,
    }


def build_tool_surface_diff(
    repo_root: Path,
    *,
    manifest_tool_names: list[str] | tuple[str, ...] | None = None,
    active_profile: str | None = None,
    runtime_status_payload: dict[str, Any] | None = None,
    proof_status_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare source manifest, loaded adapter, runtime status, and proof artifact."""

    expected = list(EXPECTED_CHATGPT_MCP_TOOL_NAMES)
    manifest = [str(item) for item in (manifest_tool_names or expected)]
    runtime = runtime_status_payload or _runtime_status(repo_root, check_runtime_surface=False)
    proof = proof_status_payload or _proof_status(repo_root)

    runtime_surface = runtime.get("runtimeSurface") if isinstance(runtime.get("runtimeSurface"), dict) else {}
    runtime_names = _normalize_tool_names(runtime_surface.get("observedToolNames"))
    runtime_comparison_mode = "runtime-surface-observed-tool-list"
    runtime_source_freshness = runtime.get("runtimeSourceFreshness") if isinstance(runtime.get("runtimeSourceFreshness"), dict) else {}
    if runtime_names is None and runtime.get("ok") is True and runtime_source_freshness.get("ok") is True:
        runtime_names = list(manifest)
        runtime_comparison_mode = "loaded-manifest-plus-running-current-source-freshness"
    proof_summary = proof.get("proofSummary") if isinstance(proof.get("proofSummary"), dict) else {}
    proof_names = _normalize_tool_names(proof_summary.get("toolNames"))
    if proof_names is None:
        proof_names = _normalize_tool_names(proof_summary.get("toolOutputSchemaToolNames"))

    source_vs_manifest = _surface_comparison(expected, manifest)
    source_vs_runtime = _surface_comparison(expected, runtime_names)
    source_vs_proof = _surface_comparison(expected, proof_names)

    blockers: list[str] = []
    warnings: list[str] = []
    if not source_vs_manifest.get("ok"):
        blockers.append("source-manifest-tool-surface-mismatch")
    runtime_ok = runtime.get("ok")
    if runtime_ok is False:
        blockers.extend(str(item) for item in runtime.get("blockers") or [])
    if runtime_source_freshness.get("ok") is False:
        blockers.append("runtime-source-freshness-blocked")
    if source_vs_runtime.get("status") == "blocked":
        blockers.append("runtime-observed-tool-surface-mismatch")
    elif source_vs_runtime.get("status") == "not-checked":
        warnings.append("runtime-observed-tool-surface-not-checked-from-mcp-tool")
    if proof.get("ok") is False:
        blockers.extend(str(item) for item in proof.get("blockers") or [])
    if source_vs_proof.get("status") == "blocked":
        blockers.append("actual-client-proof-tool-surface-mismatch")
    elif source_vs_proof.get("status") == "not-checked":
        warnings.append("actual-client-proof-tool-names-not-available")

    deduped_blockers = list(dict.fromkeys(blockers))
    deduped_warnings = list(dict.fromkeys(warnings + [str(item) for item in proof.get("warnings") or []]))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-tool-surface-diff",
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not deduped_blockers else "blocked",
        "ok": not deduped_blockers,
        "activeProfile": active_profile,
        "expected": {
            "source": "tools/riftreader_workflow/mcp_tool_surface.py",
            "toolCount": len(expected),
            "toolNames": expected,
        },
        "sourceVsManifest": source_vs_manifest,
        "sourceVsRuntime": {**source_vs_runtime, "comparisonMode": runtime_comparison_mode},
        "sourceVsActualClientProof": source_vs_proof,
        "runtime": {
            "status": runtime.get("status"),
            "ok": runtime.get("ok"),
            "selectedListener": runtime.get("selectedListener"),
            "runtimeSourceFreshness": runtime_source_freshness,
            "runtimeSurface": runtime_surface,
        },
        "actualClientProof": {
            "status": proof.get("status"),
            "ok": proof.get("ok"),
            "proofPath": proof.get("proofPath"),
            "proofFreshness": proof.get("proofFreshness"),
            "proofSummary": proof_summary,
        },
        "blockers": deduped_blockers,
        "warnings": deduped_warnings,
        "safety": {
            **safety_flags(),
            "readOnlyDiff": True,
            "runtimeSurfaceHttpProbeSkipped": True,
            "serverStarted": False,
            "serverStopped": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
            "providerWrites": False,
            "inputSent": False,
            "movementSent": False,
            "x64dbgAttach": False,
            "noCheatEngine": True,
        },
    }


def build_restart_preflight(
    repo_root: Path,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    runtime_status_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a read-only exact-PID restart preflight and approval token."""

    runtime = runtime_status_payload or _runtime_status(repo_root, check_runtime_surface=False, host=host, port=port)
    selected = runtime.get("selectedListener") if isinstance(runtime.get("selectedListener"), dict) else None
    classification = selected.get("classification") if isinstance(selected, dict) and isinstance(selected.get("classification"), dict) else {}
    launcher = repo_root / ROOT_LAUNCHER
    blockers: list[str] = []
    warnings: list[str] = []

    pid = selected.get("owningProcess") if isinstance(selected, dict) else None
    command_line = str(selected.get("commandLine") or "") if isinstance(selected, dict) else ""
    creation_date = selected.get("creationDate") if isinstance(selected, dict) else None
    if not selected or not classification.get("isCurrentChatGptMcpServer"):
        blockers.append("current-chatgpt-mcp-server-not-selected")
    if classification.get("toolProfile") != "full":
        blockers.append(f"current-chatgpt-mcp-server-not-full-profile:{classification.get('toolProfile') or 'unknown'}")
    if not isinstance(pid, int) or pid <= 0:
        blockers.append("current-chatgpt-mcp-server-pid-unavailable")
    if not isinstance(creation_date, str) or not creation_date.strip():
        blockers.append("current-chatgpt-mcp-server-start-time-unavailable")
    if not command_line:
        blockers.append("current-chatgpt-mcp-server-command-line-unavailable")
    if not launcher.is_file():
        blockers.append(f"root-launcher-missing:{ROOT_LAUNCHER}")
    if runtime.get("status") == "not-running":
        blockers.append(f"local-backend-not-running:{host}:{port}")
    elif runtime.get("status") not in {"running-current", "running-stale-runtime"}:
        warnings.append(f"runtime-status-not-clean:{runtime.get('status')}")

    source_freshness = runtime.get("runtimeSourceFreshness") if isinstance(runtime.get("runtimeSourceFreshness"), dict) else {}
    approval_facts = {
        "host": host,
        "port": int(port),
        "localMcpUrl": f"http://{host}:{int(port)}/mcp",
        "targetPid": pid,
        "processCreationDate": creation_date,
        "commandLineSha256": sha256_text(command_line) if command_line else None,
        "toolProfile": classification.get("toolProfile"),
        "transport": classification.get("transport"),
        "allowedHost": classification.get("allowedHost"),
        "allowedOrigin": classification.get("allowedOrigin"),
        "expectedToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "latestSourcePath": source_freshness.get("latestSourcePath"),
        "latestSourceMtimeUtc": source_freshness.get("latestSourceMtimeUtc"),
        "launcher": ROOT_LAUNCHER,
    }
    ready = not blockers
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-runtime-restart-preflight",
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "ready" if ready else "blocked",
        "ok": ready,
        "host": host,
        "port": int(port),
        "runtimeStatus": runtime,
        "approvalFacts": approval_facts,
        "expectedApprovalToken": approval_token_for_facts(approval_facts) if ready else None,
        "blockers": list(dict.fromkeys(blockers + [str(item) for item in runtime.get("blockers") or [] if "started-before-current-source" not in str(item)])) if not selected else list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings + [str(item) for item in runtime.get("warnings") or []])),
        "nextAction": (
            "If the facts match the target process, pass targetPid, processCreationDate, commandLineSha256, and expectedApprovalToken to restart_mcp_runtime."
            if ready
            else "Resolve blockers before scheduling a restart; do not kill an unclassified or foreign listener."
        ),
        "safety": {
            **safety_flags(),
            "readOnlyPreflight": True,
            "serverStarted": False,
            "serverStopped": False,
            "exactPidRequiredForRestart": True,
            "arbitraryCommandAccepted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
            "providerWrites": False,
            "inputSent": False,
            "movementSent": False,
            "x64dbgAttach": False,
            "noCheatEngine": True,
        },
    }


def _restart_summary_path(repo_root: Path) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    root = repo_root / RESTART_ARTIFACT_ROOT / "restarts"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{stamp}-restart-scheduled.json"


def _powershell_restart_script(
    *,
    repo_root: Path,
    target_pid: int,
    expected_command_line_sha256: str,
    summary_path: Path,
    delay_seconds: int,
) -> str:
    repo_json = json.dumps(str(repo_root))
    summary_json = json.dumps(str(summary_path))
    launcher_json = json.dumps(str(repo_root / ROOT_LAUNCHER))
    expected_hash_json = json.dumps(expected_command_line_sha256.lower())
    return f"""
$ErrorActionPreference = 'Stop'
$RepoRoot = {repo_json}
$SummaryPath = {summary_json}
$Launcher = {launcher_json}
$ExpectedHash = {expected_hash_json}
$TargetPid = {int(target_pid)}
$DelaySeconds = {int(delay_seconds)}
function Write-Summary($Status, $Ok, $Extra) {{
  $payload = [ordered]@{{
    schemaVersion = {SCHEMA_VERSION}
    kind = 'riftreader-chatgpt-mcp-runtime-restart-summary'
    version = '{VERSION}'
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    status = $Status
    ok = $Ok
    targetPid = $TargetPid
    summaryPath = $SummaryPath
  }}
  foreach ($key in $Extra.Keys) {{ $payload[$key] = $Extra[$key] }}
  New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($SummaryPath)) | Out-Null
  $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
}}
try {{
  Start-Sleep -Seconds $DelaySeconds
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$TargetPid" -ErrorAction SilentlyContinue
  if ($null -eq $proc) {{
    Write-Summary 'blocked-target-process-missing' $false @{{ blockers = @('target-process-missing-before-stop') }}
    exit 2
  }}
  $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$proc.CommandLine)
  $sha256 = [System.Security.Cryptography.SHA256]::Create()
  try {{
    $hashBytes = $sha256.ComputeHash($bytes)
  }} finally {{
    $sha256.Dispose()
  }}
  $hash = [System.BitConverter]::ToString($hashBytes).Replace('-', '').ToLowerInvariant()
  if ($hash -ne $ExpectedHash) {{
    Write-Summary 'blocked-target-command-line-drift' $false @{{ blockers = @('target-command-line-sha256-drift'); observedCommandLineSha256 = $hash }}
    exit 2
  }}
  Stop-Process -Id $TargetPid -Force -ErrorAction Stop
  Start-Sleep -Milliseconds 750
  $env:RIFTREADER_MCP_NO_PAUSE = '1'
  $started = Start-Process -FilePath $Launcher -ArgumentList 'serve' -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
  Write-Summary 'restart-launched' $true @{{ stoppedPid = $TargetPid; launcher = '{ROOT_LAUNCHER}'; startedWrapperPid = [int]$started.Id; blockers = @(); warnings = @('verify-runtime-status-after-reconnect') }}
  exit 0
}} catch {{
  Write-Summary 'failed' $false @{{ blockers = @('restart-helper-exception:' + $_.Exception.GetType().Name); error = [string]$_.Exception.Message }}
  exit 1
}}
"""


def schedule_runtime_restart(
    repo_root: Path,
    *,
    target_pid: int,
    process_creation_date: str,
    command_line_sha256: str,
    approval_token: str | None,
    timeout_seconds: float = 30.0,
    delay_seconds: int = 2,
    preflight_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preflight = preflight_payload or build_restart_preflight(repo_root)
    approval_facts = preflight.get("approvalFacts") if isinstance(preflight.get("approvalFacts"), dict) else {}
    blockers: list[str] = []
    warnings: list[str] = [str(item) for item in preflight.get("warnings") or []]
    if not preflight.get("ok"):
        blockers.extend(str(item) for item in preflight.get("blockers") or [])
    expected_token = preflight.get("expectedApprovalToken")
    if not isinstance(approval_token, str) or not approval_token.strip():
        blockers.append("approval-token-required:restart_mcp_runtime")
    elif approval_token.strip() != expected_token:
        blockers.append("approval-token-mismatch:restart_mcp_runtime")
    if approval_facts.get("targetPid") != target_pid:
        blockers.append("target-pid-mismatch")
    if str(approval_facts.get("processCreationDate") or "") != process_creation_date:
        blockers.append("process-creation-date-mismatch")
    if str(approval_facts.get("commandLineSha256") or "").lower() != command_line_sha256.lower():
        blockers.append("command-line-sha256-mismatch")
    if timeout_seconds < 5 or timeout_seconds > 120:
        blockers.append("timeout-seconds-out-of-range:5..120")
    if blockers:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-runtime-restart",
            "version": VERSION,
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "restartScheduled": False,
            "targetPid": target_pid,
            "preflight": preflight,
            "blockers": list(dict.fromkeys(blockers)),
            "warnings": warnings,
            "safety": {
                **safety_flags(),
                "serverStopScheduled": False,
                "serverStartScheduled": False,
                "exactPidRequiredForRestart": True,
                "approvalTokenRequired": True,
                "arbitraryCommandAccepted": False,
                "gitMutation": False,
                "providerWrites": False,
                "inputSent": False,
                "movementSent": False,
                "x64dbgAttach": False,
                "noCheatEngine": True,
            },
        }

    summary_path = _restart_summary_path(repo_root)
    script = _powershell_restart_script(
        repo_root=repo_root,
        target_pid=target_pid,
        expected_command_line_sha256=command_line_sha256,
        summary_path=summary_path,
        delay_seconds=max(1, int(delay_seconds)),
    )
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(  # noqa: S603 - fixed PowerShell helper with exact PID/hash verification.
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=str(repo_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-runtime-restart",
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "scheduled",
        "ok": True,
        "restartScheduled": True,
        "helperPid": proc.pid,
        "targetPid": target_pid,
        "summaryJson": _relative(repo_root, summary_path),
        "preflight": preflight,
        "blockers": [],
        "warnings": list(dict.fromkeys(warnings + ["mcp-runtime-restart-scheduled-connection-will-drop", "call-get_mcp_runtime_status-after-reconnect"])),
        "safety": {
            **safety_flags(),
            "serverStopScheduled": True,
            "serverStartScheduled": True,
            "exactPidRequiredForRestart": True,
            "approvalTokenRequired": True,
            "arbitraryCommandAccepted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
            "providerWrites": False,
            "inputSent": False,
            "movementSent": False,
            "x64dbgAttach": False,
            "noCheatEngine": True,
        },
    }


def _cloudflared_status(repo_root: Path) -> dict[str, Any]:
    repo_text = str(repo_root.resolve())
    if repo_text not in sys.path:
        sys.path.insert(0, repo_text)
    try:
        from tools.riftreader_mcp import cloudflared_status
    except ImportError:  # pragma: no cover - alternate import path in tests.
        import importlib

        cloudflared_status = importlib.import_module("tools.riftreader_mcp.cloudflared_status")
    return cloudflared_status.build_cloudflared_status(repo_root)


def _public_route_probe(public_mcp_url: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    parsed = urlsplit(public_mcp_url)
    if parsed.scheme != "https" or not parsed.netloc or not parsed.path.endswith("/mcp"):
        return {
            "status": "blocked",
            "ok": False,
            "url": public_mcp_url,
            "blockers": ["public-mcp-url-must-be-https-and-end-with-/mcp"],
        }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "riftreader-mcp-tunnel-status", "version": VERSION},
        },
    }
    req = urllib.request.Request(public_mcp_url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("Origin", "https://chatgpt.com")
    req.add_header("User-Agent", "RiftReader-MCP-Tunnel-Status/0.1")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310 - fixed operator-owned public MCP URL probe.
            raw = response.read(4096).decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {"rawPreview": raw[:1000]}
            result = body.get("result") if isinstance(body, dict) and isinstance(body.get("result"), dict) else {}
            server_info = result.get("serverInfo") if isinstance(result.get("serverInfo"), dict) else {}
            ok = int(response.status) == 200 and bool(server_info.get("name"))
            return {
                "status": "passed" if ok else "blocked",
                "ok": ok,
                "url": public_mcp_url,
                "statusCode": int(response.status),
                "reason": "public-mcp-initialize-succeeded" if ok else "public-mcp-initialize-malformed",
                "serverInfo": server_info,
                "protocolVersion": result.get("protocolVersion"),
                "blockers": [] if ok else ["public-mcp-initialize-malformed"],
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": "blocked",
            "ok": False,
            "url": public_mcp_url,
            "statusCode": int(exc.code),
            "reason": "public-mcp-initialize-http-error",
            "blockers": [f"public-route-http-error:{int(exc.code)}"],
        }
    except Exception as exc:  # noqa: BLE001 - status helper must report, not crash.
        return {
            "status": "blocked",
            "ok": False,
            "url": public_mcp_url,
            "error": f"{type(exc).__name__}: {exc}",
            "blockers": ["public-route-probe-failed"],
        }


def build_tunnel_status(repo_root: Path, *, public_mcp_url: str = DEFAULT_PUBLIC_MCP_URL, timeout_seconds: float = 5.0) -> dict[str, Any]:
    cloudflared = _cloudflared_status(repo_root)
    runtime = _runtime_status(repo_root, check_runtime_surface=False)
    route = _public_route_probe(public_mcp_url, timeout_seconds=timeout_seconds)
    cloudflared_running = cloudflared.get("status") in {"service_only", "duplicate_processes", "detached_only"}
    blockers: list[str] = []
    warnings: list[str] = []
    if not cloudflared_running:
        blockers.append(f"cloudflared-not-running:{cloudflared.get('status')}")
    if runtime.get("ok") is False:
        blockers.extend(str(item) for item in runtime.get("blockers") or [])
    if route.get("ok") is False:
        blockers.extend(str(item) for item in route.get("blockers") or [])
    warnings.extend(str(item) for item in cloudflared.get("warnings") or [])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-tunnel-status",
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "publicMcpUrl": public_mcp_url,
        "connectionMode": "cloudflare-named-tunnel",
        "cloudflared": cloudflared,
        "localRuntime": {
            "status": runtime.get("status"),
            "ok": runtime.get("ok"),
            "selectedListener": runtime.get("selectedListener"),
            "runtimeSourceFreshness": runtime.get("runtimeSourceFreshness"),
        },
        "publicRouteProbe": route,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "safety": {
            **safety_flags(),
            "readOnlyTunnelStatus": True,
            "publicHttpsProbeSent": True,
            "publicTunnelStarted": False,
            "cloudflareMutationEndpoint": False,
            "chatGptRegistrationPerformed": False,
            "serverStarted": False,
            "serverStopped": False,
            "gitMutation": False,
            "providerWrites": False,
            "inputSent": False,
            "movementSent": False,
            "x64dbgAttach": False,
            "noCheatEngine": True,
        },
    }


def build_connector_setup_packet(repo_root: Path, *, public_mcp_url: str = DEFAULT_PUBLIC_MCP_URL) -> dict[str, Any]:
    runtime = _runtime_status(repo_root, check_runtime_surface=False)
    expected = list(EXPECTED_CHATGPT_MCP_TOOL_NAMES)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-connector-setup-packet",
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "ok": True,
        "appNameSuggestion": "rift-mcp",
        "serverUrl": public_mcp_url,
        "authMode": "No Authentication",
        "connectionMode": "cloudflare-named-tunnel",
        "expectedToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "expectedToolNames": expected,
        "localRuntimeStatus": {
            "status": runtime.get("status"),
            "ok": runtime.get("ok"),
            "blockers": runtime.get("blockers") or [],
        },
        "setupSteps": [
            "Start or verify the local MCP runtime before using the saved ChatGPT app connector; the saved connector does not start the server.",
            "In ChatGPT Web/Desktop Developer Mode, configure the app Server URL as https://mcp.360madden.com/mcp with No Authentication.",
            "After code or tool metadata changes, restart the local MCP runtime, then refresh/reconnect the ChatGPT app so it rescans tools.",
            "First call get_mcp_runtime_status, then get_tool_surface_diff, then get_tunnel_status before recording proof.",
            "Record fresh actual-client proof with submit_actual_client_observation only after ChatGPT visibly exposes the expected tool count.",
        ],
        "firstToolCalls": [
            "health",
            "get_mcp_runtime_status",
            "get_tool_surface_diff",
            "get_tunnel_status",
            "get_actual_client_proof_status",
        ],
        "proofChecklist": {
            "mustObserveToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "mustObserveToolNamesExactly": expected,
            "mustObserveOutputSchemasForAllTools": True,
            "mustUseActualChatGptWebOrDesktopClient": True,
            "staleProofIsBlocked": True,
        },
        "blockers": [],
        "warnings": [
            "operator-owned-startup-required-saved-connector-does-not-run-local-server",
            "refresh-chatgpt-app-after-mcp-tool-metadata-changes",
        ],
        "safety": {
            **safety_flags(),
            "readOnlySetupPacket": True,
            "serverStarted": False,
            "serverStopped": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "secretMaterialIncluded": False,
            "gitMutation": False,
            "providerWrites": False,
            "inputSent": False,
            "movementSent": False,
            "x64dbgAttach": False,
            "noCheatEngine": True,
        },
    }


# END_OF_SCRIPT_MARKER
