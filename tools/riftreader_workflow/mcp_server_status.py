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
from datetime import datetime, timedelta, timezone
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
RUNTIME_SURFACE_TIMEOUT_SECONDS = 15.0
RUNTIME_SOURCE_FRESHNESS_TOLERANCE_SECONDS = 1.0
RUNTIME_SOURCE_PATHS = (
    Path("tools/riftreader_workflow/riftreader_chatgpt_mcp.py"),
    Path("tools/riftreader_workflow/mcp_server_status.py"),
    Path("tools/riftreader_workflow/mcp_tool_surface.py"),
    Path("tools/riftreader_workflow/mcp_runtime_control.py"),
    Path("tools/riftreader_workflow/chatgpt_trial_recorder.py"),
    Path("tools/riftreader_workflow/mcp_final_readiness.py"),
    Path("tools/riftreader_workflow/mcp_phase2_status.py"),
    Path("tools/riftreader_workflow/mcp_phase1_completion.py"),
    Path("tools/riftreader_workflow/mcp_proof_replay.py"),
    Path("tools/riftreader_workflow/mcp_workflow_state.py"),
    Path("tools/riftreader_workflow/commit_reviewed_slice.py"),
    Path("tools/riftreader_workflow/push_current_branch.py"),
    Path("tools/riftreader_workflow/mcp_ci_status.py"),
    Path("tools/riftreader_workflow/bounded_repo_commands.py"),
    Path("tools/riftreader_workflow/local_artifact_bridge.py"),
    Path("tools/riftreader_workflow/package_draft_review.py"),
    Path("tools/riftreader_workflow/tracked_repo_context.py"),
)


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


def _run_text_command(args: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        errors="replace",
        timeout=timeout_seconds,
    )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_wmic_list_output(stdout: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        current[key] = value.strip()
        if key == "ProcessId":
            records.append(current)
            current = {}
    if current:
        records.append(current)
    return records


def _process_record_from_wmic(record: dict[str, str]) -> dict[str, Any] | None:
    pid = _int_or_none(record.get("ProcessId"))
    if pid is None:
        return None
    return {
        "processId": pid,
        "parentProcessId": _int_or_none(record.get("ParentProcessId")),
        "processExists": True,
        "processName": record.get("Name") or None,
        "executablePath": record.get("ExecutablePath") or None,
        "creationDate": record.get("CreationDate") or None,
        "commandLine": record.get("CommandLine") or None,
    }


def _query_process_by_pid(pid: int, *, timeout_seconds: int) -> dict[str, Any]:
    completed = _run_text_command(
        [
            "wmic",
            "process",
            "where",
            f"processid={int(pid)}",
            "get",
            "ProcessId,ParentProcessId,Name,ExecutablePath,CreationDate,CommandLine",
            "/format:list",
        ],
        timeout_seconds=timeout_seconds,
    )
    if completed.returncode != 0:
        return {
            "processId": int(pid),
            "processExists": False,
            "processQueryExitCode": completed.returncode,
            "processQueryStderr": completed.stderr[-1000:],
        }
    for record in _parse_wmic_list_output(completed.stdout):
        payload = _process_record_from_wmic(record)
        if payload is not None:
            return payload
    return {"processId": int(pid), "processExists": False}


def _query_all_processes(*, timeout_seconds: int) -> dict[str, Any]:
    completed = _run_text_command(
        [
            "wmic",
            "process",
            "get",
            "ProcessId,ParentProcessId,Name,ExecutablePath,CreationDate,CommandLine",
            "/format:list",
        ],
        timeout_seconds=timeout_seconds,
    )
    if completed.returncode != 0:
        return {
            "ok": False,
            "status": "query-failed",
            "count": 0,
            "processes": [],
            "exitCode": completed.returncode,
            "stderr": completed.stderr[-1000:],
            "warnings": [],
        }
    processes = [
        process
        for record in _parse_wmic_list_output(completed.stdout)
        if (process := _process_record_from_wmic(record)) is not None
    ]
    return {"ok": True, "count": len(processes), "processes": processes}


def _split_netstat_address(value: str) -> tuple[str, int] | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith("[") and "]:" in text:
        address, port_text = text.rsplit("]:", 1)
        address = address[1:]
    elif ":" in text:
        address, port_text = text.rsplit(":", 1)
    else:
        return None
    port = _int_or_none(port_text)
    if port is None:
        return None
    return address, port


def _host_matches(observed: str, expected: str) -> bool:
    normalized_observed = observed.strip("[]").lower()
    normalized_expected = expected.strip("[]").lower()
    return normalized_observed in {normalized_expected, "0.0.0.0", "::"}


def query_windows_listeners(host: str, port: int, *, timeout_seconds: int = 10) -> dict[str, Any]:
    """Return loopback listeners using Python plus Windows CLI tools, not PowerShell."""

    try:
        completed = _run_text_command(["netstat", "-ano", "-p", "tcp"], timeout_seconds=timeout_seconds)
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

    listeners: list[dict[str, Any]] = []
    pids_seen: set[int] = set()
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local = _split_netstat_address(parts[1])
        if local is None:
            continue
        local_address, local_port = local
        state = parts[3].upper()
        pid = _int_or_none(parts[4])
        if local_port != int(port) or state != "LISTENING" or pid is None:
            continue
        if not _host_matches(local_address, host):
            continue
        if pid in pids_seen:
            continue
        pids_seen.add(pid)
        process = _query_process_by_pid(pid, timeout_seconds=timeout_seconds)
        listeners.append(
            {
                "localAddress": local_address,
                "localPort": int(local_port),
                "state": "Listen",
                "owningProcess": int(pid),
                "processExists": bool(process.get("processExists")),
                "processName": process.get("processName"),
                "executablePath": process.get("executablePath"),
                "creationDate": process.get("creationDate"),
                "commandLine": process.get("commandLine"),
            }
        )
    return {
        "ok": True,
        "exists": bool(listeners),
        "host": host,
        "port": int(port),
        "listeners": listeners,
    }


def query_stdio_counterparts(repo_root: Path, *, timeout_seconds: int = 10) -> dict[str, Any]:
    """Find local stdio adapter processes that can keep old MCP tool surfaces alive.

    The Cloudflare ChatGPT route uses the loopback streamable-HTTP server.  Codex
    and local MCP clients may also have stdio instances of the same adapter
    running.  Those processes are not proof that the public route is current, but
    if they started before the latest adapter source change they can mislead an
    operator because actual callable tools in the current client can still show an
    older surface.
    """

    repo_root_text = str(repo_root.resolve()).replace("\\", "/")
    try:
        payload = _query_all_processes(timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "status": "query-failed",
            "count": 0,
            "processes": [],
            "queryTimedOut": True,
            "error": f"TimeoutExpired:{exc}",
            "warnings": [],
        }
    if not payload.get("ok", True):
        return payload

    processes: list[dict[str, Any]] = []
    for process in payload.get("processes", []):
        if not isinstance(process, dict):
            continue
        command_line = str(process.get("commandLine") or "")
        normalized = command_line.replace("\\", "/")
        if (
            "riftreader_chatgpt_mcp.py" in normalized
            and "--serve" in normalized
            and re.search(r"--transport(?:=|\s+)stdio", normalized)
            and (repo_root_text in normalized or "tools/riftreader_workflow/riftreader_chatgpt_mcp.py" in normalized)
        ):
            processes.append(process)
    return summarize_stdio_counterparts(repo_root, {"ok": True, "count": len(processes), "processes": processes})


def summarize_stdio_counterparts(repo_root: Path, query: dict[str, Any]) -> dict[str, Any]:
    processes = query.get("processes") if isinstance(query.get("processes"), list) else []
    summarized: list[dict[str, Any]] = []
    warnings: list[str] = []
    stale_pids: list[int] = []
    for item in processes:
        if not isinstance(item, dict):
            continue
        classification = classify_command_line(str(item.get("commandLine") or ""))
        freshness = check_runtime_source_freshness(repo_root, item)
        pid = item.get("processId")
        if freshness.get("ok") is False and isinstance(pid, int):
            stale_pids.append(pid)
            warnings.append(f"codex-stdio-counterpart-stale:{pid}")
        summarized.append({**item, "classification": classification, "runtimeSourceFreshness": freshness})

    if not query.get("ok", True):
        status = "query-failed"
        ok = False
    elif not summarized:
        status = "not-running"
        ok = True
    elif stale_pids:
        status = "stale-running"
        ok = False
    else:
        status = "running-current"
        ok = True

    if summarized:
        warnings.append("codex-stdio-counterparts-are-not-cloudflare-http-runtime-proof")

    return {
        "status": status,
        "ok": ok,
        "count": len(summarized),
        "processes": summarized,
        "staleProcessIds": stale_pids,
        "warnings": list(dict.fromkeys(warnings)),
        "why": (
            "These stdio MCP adapter processes are optional local/Codex counterparts. "
            "They do not prove the Cloudflare HTTP route, but stale instances can keep "
            "an actual callable client surface on an older tool count until the client/app restarts."
        ),
    }


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


def parse_windows_creation_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    dmtf_match = re.match(r"^(\d{14})\.(\d{1,6})([+-]\d{3})$", text)
    if dmtf_match:
        timestamp, microseconds_text, offset_text = dmtf_match.groups()
        try:
            parsed = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        except ValueError:
            return None
        microseconds = int(microseconds_text.ljust(6, "0")[:6])
        offset_minutes = int(offset_text)
        parsed = parsed.replace(
            microsecond=microseconds,
            tzinfo=timezone(timedelta(minutes=offset_minutes)),
        )
        return parsed.astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def latest_runtime_source_mtime(repo_root: Path) -> dict[str, Any]:
    latest_path: Path | None = None
    latest_mtime = 0.0
    inspected: list[str] = []
    for relative in RUNTIME_SOURCE_PATHS:
        path = repo_root / relative
        if not path.is_file():
            continue
        inspected.append(str(relative))
        mtime = path.stat().st_mtime
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = relative
    if latest_path is None:
        return {
            "status": "not-checked",
            "ok": None,
            "reason": "runtime-source-files-not-found",
            "inspectedPaths": inspected,
        }
    latest_dt = datetime.fromtimestamp(latest_mtime, tz=timezone.utc)
    return {
        "status": "passed",
        "ok": True,
        "latestSourcePath": str(latest_path),
        "latestSourceMtimeUtc": latest_dt.isoformat().replace("+00:00", "Z"),
        "latestSourceMtimeEpoch": latest_mtime,
        "inspectedPaths": inspected,
    }


def check_runtime_source_freshness(repo_root: Path, listener: dict[str, Any]) -> dict[str, Any]:
    source = latest_runtime_source_mtime(repo_root)
    if not source.get("ok"):
        return source
    started_at = parse_windows_creation_date(listener.get("creationDate"))
    if started_at is None:
        return {
            "status": "not-checked",
            "ok": None,
            "reason": "process-creation-date-unavailable",
            "latestSourcePath": source.get("latestSourcePath"),
            "latestSourceMtimeUtc": source.get("latestSourceMtimeUtc"),
        }
    latest_mtime = float(source.get("latestSourceMtimeEpoch") or 0.0)
    process_started_epoch = started_at.timestamp()
    stale_by = latest_mtime - process_started_epoch
    blockers: list[str] = []
    if stale_by > RUNTIME_SOURCE_FRESHNESS_TOLERANCE_SECONDS:
        blockers.append(
            "runtime-process-started-before-current-source:"
            f"{source.get('latestSourcePath')}:{round(stale_by, 3)}s"
        )
    return {
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "processStartedAtUtc": started_at.isoformat().replace("+00:00", "Z"),
        "latestSourcePath": source.get("latestSourcePath"),
        "latestSourceMtimeUtc": source.get("latestSourceMtimeUtc"),
        "staleBySeconds": round(stale_by, 3),
        "blockers": blockers,
    }


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
    runtime_source_freshness_probe: dict[str, Any] | None = None,
    stdio_counterpart_query: dict[str, Any] | None = None,
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
        runtime_source_freshness = (
            runtime_source_freshness_probe
            if runtime_source_freshness_probe is not None
            else check_runtime_source_freshness(repo_root, current)
        )
        if runtime_source_freshness.get("ok") is False:
            status = "running-stale-runtime"
            blockers.append("current-chatgpt-mcp-server-started-before-current-source")
            for blocker in runtime_source_freshness.get("blockers", []):
                blockers.append(str(blocker))
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
    else:
        runtime_source_freshness = {
            "status": "not-checked",
            "ok": None,
            "reason": "no-current-full-profile-listener",
        }
    if stdio_counterpart_query is not None:
        stdio_counterparts = summarize_stdio_counterparts(repo_root, stdio_counterpart_query)
    elif listener_query is not None:
        stdio_counterparts = {
            "status": "not-checked",
            "ok": None,
            "count": None,
            "processes": [],
            "warnings": [],
            "reason": "injected-listener-query-test-mode",
        }
    else:
        stdio_counterparts = query_stdio_counterparts(repo_root)
    if stdio_counterparts.get("status") == "stale-running":
        warnings.extend(str(item) for item in stdio_counterparts.get("warnings") or [])
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
            "key": "runtime-source-freshness",
            "status": runtime_source_freshness.get("status"),
            "ok": runtime_source_freshness.get("ok"),
            "why": "The MCP adapter process must have started after current adapter source files were last modified.",
        },
        {
            "key": "codex-stdio-counterparts",
            "status": "warning" if stdio_counterparts.get("status") == "stale-running" else stdio_counterparts.get("status"),
            "ok": stdio_counterparts.get("ok"),
            "why": (
                "Codex/local stdio MCP counterparts are not the Cloudflare HTTP runtime, but stale stdio "
                "instances can explain why actual callable tools still show an old tool surface."
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
        "runtimeSourceFreshness": runtime_source_freshness,
        "stdioCounterparts": stdio_counterparts,
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
