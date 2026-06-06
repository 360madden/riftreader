#!/usr/bin/env python3
# Version: riftreader-mcp-local-server-control-v0.1.2
# Purpose: Safe local lifecycle control for the ChatGPT Web/Desktop HTTP MCP server.

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from tools.riftreader_mcp.auth import token_fingerprint
from tools.riftreader_mcp.config import PROTOCOL_VERSION, default_repo_root, ensure_local_config, load_config, runtime_root
from tools.riftreader_mcp.logging_util import utc_iso, utc_stamp

VERSION = "riftreader-mcp-local-server-control-v0.1.2"
END_MARKER = "END_RIFTREADER_MCP_LOCAL_SERVER_CONTROL"
SERVER_MODULE = "tools.riftreader_mcp.http_server"


def powershell_json(script: str, *, timeout_seconds: int = 20) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exitCode": None,
            "stdout": str(exc.stdout or "")[:4000],
            "stderr": str(exc.stderr or "")[:4000],
            "timedOut": True,
            "timeoutSeconds": timeout_seconds,
            "payload": None,
        }
    stdout = proc.stdout.strip()
    payload: Any = None
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"rawStdout": stdout}
    return {
        "ok": proc.returncode == 0,
        "exitCode": proc.returncode,
        "stdout": stdout[:4000],
        "stderr": proc.stderr.strip()[:4000],
        "timedOut": False,
        "payload": payload,
    }


def find_listener(host: str, port: int) -> dict[str, Any]:
    host_json = json.dumps(host)
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$conn = Get-NetTCPConnection -LocalAddress {host_json} -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $conn) {{
  [ordered]@{{ exists = $false }} | ConvertTo-Json -Compress
}} else {{
  [ordered]@{{
    exists = $true
    localAddress = [string]$conn.LocalAddress
    localPort = [int]$conn.LocalPort
    owningProcess = [int]$conn.OwningProcess
    state = [string]$conn.State
  }} | ConvertTo-Json -Compress
}}
"""
    result = powershell_json(script)
    payload = result.get("payload")
    if not isinstance(payload, dict):
        return {"exists": False, "query": result, "queryFailed": True}
    payload["query"] = {"ok": result["ok"], "exitCode": result["exitCode"], "stderr": result["stderr"], "timedOut": result.get("timedOut", False)}
    return payload


def process_info(pid: int | None) -> dict[str, Any]:
    if not pid:
        return {"exists": False}
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$proc = Get-CimInstance Win32_Process -Filter "ProcessId={int(pid)}"
if ($null -eq $proc) {{
  [ordered]@{{ exists = $false; pid = {int(pid)} }} | ConvertTo-Json -Compress
}} else {{
  [ordered]@{{
    exists = $true
    pid = [int]$proc.ProcessId
    name = [string]$proc.Name
    executablePath = [string]$proc.ExecutablePath
    commandLine = [string]$proc.CommandLine
  }} | ConvertTo-Json -Compress
}}
"""
    result = powershell_json(script)
    payload = result.get("payload")
    if not isinstance(payload, dict):
        return {"exists": False, "pid": pid, "query": result, "queryFailed": True}
    payload["query"] = {"ok": result["ok"], "exitCode": result["exitCode"], "stderr": result["stderr"], "timedOut": result.get("timedOut", False)}
    return payload


def normalize_for_match(value: str) -> str:
    return value.replace("\\", "/").replace('"', "").lower()


def is_server_process(process: dict[str, Any], repo: Path) -> bool:
    command_line = str(process.get("commandLine") or "")
    normalized_command = normalize_for_match(command_line)
    normalized_repo = normalize_for_match(str(repo.resolve()))
    return SERVER_MODULE in normalized_command and normalized_repo in normalized_command


def health_check(host: str, port: int, token: str | None) -> dict[str, Any]:
    if not token:
        return {"ok": False, "status": "auth_token_missing"}
    url = f"http://{host}:{port}/health"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("MCP-Protocol-Version", PROTOCOL_VERSION)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:  # noqa: S310 - operator-requested localhost health check.
            payload = json.loads(response.read().decode("utf-8-sig"))
            return {"ok": int(response.status) == 200, "statusCode": int(response.status), "payload": payload}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "statusCode": int(exc.code), "error": exc.reason}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def control_status(repo: Path) -> dict[str, Any]:
    config = load_config(repo=repo)
    listener = find_listener(config.host, config.port)
    listener_query_failed = bool(listener.get("queryFailed") or listener.get("query", {}).get("timedOut"))
    if listener_query_failed:
        process = {"exists": False, "querySkipped": True}
        matches = False
        health = {"ok": False, "status": "not_checked_listener_query_failed"}
        status = "blocked_listener_query_failed"
    else:
        process = process_info(listener.get("owningProcess") if listener.get("exists") else None)
        process_query_failed = bool(process.get("queryFailed") or process.get("query", {}).get("timedOut"))
        matches = bool(listener.get("exists") and process.get("exists") and is_server_process(process, repo))
        health = health_check(config.host, config.port, config.token) if matches else {"ok": False, "status": "not_checked"}
        status = (
            "running"
            if matches and health.get("ok")
            else "blocked_process_query_failed"
            if process_query_failed
            else "foreign_listener"
            if listener.get("exists") and not matches
            else "not_running"
        )
    return {
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "action": "status",
        "status": status,
        "repo": str(repo),
        "host": config.host,
        "port": config.port,
        "localMcpUrl": f"http://{config.host}:{config.port}/mcp",
        "listener": listener,
        "process": process,
        "processMatchesExpectedServer": matches,
        "health": health,
        "tokenConfigured": bool(config.token),
        "tokenFingerprint": token_fingerprint(config.token),
        "tokenPrinted": False,
    }


def stop_server(repo: Path, *, dry_run: bool = False) -> dict[str, Any]:
    before = control_status(repo)
    if before["status"] == "not_running":
        return {**before, "action": "stop", "status": "already_stopped", "dryRun": dry_run}
    if before["status"] != "running":
        return {
            **before,
            "action": "stop",
            "status": "blocked_foreign_listener",
            "dryRun": dry_run,
            "blockers": ["listener-process-does-not-match-riftreader-http-mcp-server"],
        }
    pid = int(before["process"]["pid"])
    if dry_run:
        return {**before, "action": "stop", "status": "dry_run_would_stop", "dryRun": True, "targetPid": pid}
    script = f"Stop-Process -Id {pid} -Force; Start-Sleep -Milliseconds 500; [ordered]@{{ stoppedPid = {pid} }} | ConvertTo-Json -Compress"
    stop_result = powershell_json(script)
    time.sleep(0.5)
    after = control_status(repo)
    return {
        **after,
        "action": "stop",
        "status": "stopped" if after["status"] == "not_running" else "failed_stop_still_listening",
        "dryRun": False,
        "targetPid": pid,
        "stopResult": stop_result,
    }


def server_log_paths(repo: Path) -> tuple[Path, Path]:
    out_dir = runtime_root(repo) / "server"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    return out_dir / f"http-server-control-{stamp}.out.log", out_dir / f"http-server-control-{stamp}.err.log"


def start_server(repo: Path, *, dry_run: bool = False) -> dict[str, Any]:
    before = control_status(repo)
    if before["status"] == "running":
        return {**before, "action": "start", "status": "already_running", "dryRun": dry_run}
    if before["status"] == "foreign_listener":
        return {
            **before,
            "action": "start",
            "status": "blocked_foreign_listener",
            "dryRun": dry_run,
            "blockers": ["listener-process-does-not-match-riftreader-http-mcp-server"],
        }
    config_setup = None
    if not dry_run:
        config_setup = ensure_local_config(repo)
        before = control_status(repo)
    stdout_path, stderr_path = server_log_paths(repo)
    command = [sys.executable, "-m", SERVER_MODULE, "--repo", str(repo), "--json"]
    if dry_run:
        return {
            **before,
            "action": "start",
            "status": "dry_run_would_start",
            "dryRun": True,
            "command": command,
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "wouldEnsureLocalConfig": True,
        }
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(  # noqa: S603 - fixed Python module invocation for repo-local server.
            command,
            cwd=str(repo),
            stdout=stdout,
            stderr=stderr,
            creationflags=creation_flags,
        )
    time.sleep(2.0)
    after = control_status(repo)
    return {
        **after,
        "action": "start",
        "status": "started" if after["status"] == "running" else "failed_start_not_listening",
        "dryRun": False,
        "startedPid": proc.pid,
        "command": command,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "configSetup": config_setup,
    }


def restart_server(repo: Path, *, dry_run: bool = False) -> dict[str, Any]:
    stop = stop_server(repo, dry_run=dry_run)
    if stop["status"] not in {"stopped", "already_stopped", "dry_run_would_stop"}:
        return {**stop, "action": "restart", "restartStatus": "blocked_before_start"}
    start = start_server(repo, dry_run=dry_run)
    return {
        **start,
        "action": "restart",
        "restartStatus": "restarted" if start["status"] in {"started", "already_running", "dry_run_would_start"} else "failed",
        "stopPhase": {k: stop.get(k) for k in ("status", "targetPid", "dryRun", "blockers")},
    }


def write_summary(repo: Path, payload: dict[str, Any]) -> Path:
    out_dir = runtime_root(repo) / "server"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"local-server-control-{utc_stamp()}.json"
    payload["summaryJson"] = str(path)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely control the local RiftReader ChatGPT HTTP MCP server.")
    parser.add_argument("action", choices=("status", "start", "stop", "restart"))
    parser.add_argument("--repo", default=str(default_repo_root()))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if args.action == "status":
        payload = control_status(repo)
    elif args.action == "start":
        payload = start_server(repo, dry_run=args.dry_run)
    elif args.action == "stop":
        payload = stop_server(repo, dry_run=args.dry_run)
    else:
        payload = restart_server(repo, dry_run=args.dry_run)

    summary = write_summary(repo, payload)
    payload["summaryJson"] = str(summary)
    print(json.dumps(payload, indent=2))
    if payload["status"].startswith("blocked") or payload["status"].startswith("failed"):
        print(f"BLOCKED: local MCP server control action did not complete: {payload['status']}")
        print(END_MARKER)
        return 2
    print("PASS: local MCP server control action complete")
    print(END_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
