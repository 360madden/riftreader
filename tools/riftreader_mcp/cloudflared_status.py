#!/usr/bin/env python3
# Version: riftreader-mcp-cloudflared-status-v0.1.0
# Purpose: Secret-safe Windows cloudflared service/process status for the 360madden MCP lane.

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.riftreader_mcp.config import default_repo_root, runtime_root
from tools.riftreader_mcp.logging_util import utc_iso


VERSION = "riftreader-mcp-cloudflared-status-v0.1.0"
SERVICE_NAME = "Cloudflared"
PROCESS_IMAGE = "cloudflared.exe"
STATE_RE = re.compile(r"^\s*STATE\s*:\s*\d+\s+([A-Z_]+)", re.IGNORECASE | re.MULTILINE)
PID_RE = re.compile(r"^\s*PID\s*:\s*(\d+)", re.IGNORECASE | re.MULTILINE)
START_TYPE_LABELS = {
    0: "Boot",
    1: "System",
    2: "Automatic",
    3: "Manual",
    4: "Disabled",
}


def _run(args: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def _query_service() -> dict[str, Any]:
    result = _run(["sc.exe", "queryex", SERVICE_NAME])
    stdout = result.stdout if result else ""
    stderr = result.stderr if result else ""
    exit_code = result.returncode if result else None
    state_match = STATE_RE.search(stdout)
    pid_match = PID_RE.search(stdout)
    state = state_match.group(1).upper() if state_match else None
    pid = int(pid_match.group(1)) if pid_match and pid_match.group(1).isdigit() else None
    exists = bool(exit_code == 0 or state or pid)
    if not exists and ("FAILED 1060" in stdout or "FAILED 1060" in stderr):
        exists = False
    return {
        "name": SERVICE_NAME,
        "exists": exists,
        "state": state,
        "running": state == "RUNNING",
        "pid": pid if state == "RUNNING" else None,
        "queryExitCode": exit_code,
    }


def _query_start_type() -> dict[str, Any]:
    # Read only non-secret registry values. Do not read ImagePath because service
    # commands can contain a Cloudflare tunnel token.
    try:
        import winreg  # type: ignore[import-not-found]
    except Exception:
        return {"startType": None, "startTypeValue": None, "delayedAutoStart": None}

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SYSTEM\CurrentControlSet\Services\{SERVICE_NAME}") as key:
            start_value = int(winreg.QueryValueEx(key, "Start")[0])
            try:
                delayed = bool(int(winreg.QueryValueEx(key, "DelayedAutostart")[0]))
            except OSError:
                delayed = False
    except OSError:
        return {"startType": None, "startTypeValue": None, "delayedAutoStart": None}

    label = START_TYPE_LABELS.get(start_value, f"Unknown({start_value})")
    if start_value == 2 and delayed:
        label = "Automatic (Delayed)"
    return {"startType": label, "startTypeValue": start_value, "delayedAutoStart": delayed}


def _query_process_pids() -> list[int]:
    result = _run(["tasklist", "/FI", f"IMAGENAME eq {PROCESS_IMAGE}", "/FO", "CSV", "/NH"])
    if not result or result.returncode != 0:
        return []

    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("INFO:"):
            continue
        try:
            row = next(csv.reader([line]))
        except Exception:
            continue
        if len(row) < 2:
            continue
        if row[0].strip('"').lower() != PROCESS_IMAGE.lower():
            continue
        pid_text = row[1].strip().strip('"')
        if pid_text.isdigit():
            pids.append(int(pid_text))
    return sorted(set(pids))


def _latest_file(root: Path, pattern: str) -> Path | None:
    if not root.is_dir():
        return None
    files = list(root.rglob(pattern))
    return max(files, key=lambda item: item.stat().st_mtime) if files else None


def _read_json_or_none(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _verdict(service: dict[str, Any], process_pids: list[int], non_service_pids: list[int]) -> str:
    if service.get("running") and not non_service_pids:
        return "service_only"
    if service.get("running") and non_service_pids:
        return "duplicate_processes"
    if process_pids:
        return "detached_only"
    if service.get("exists"):
        return "service_configured_not_running"
    return "not_running"


def build_cloudflared_status(repo: str | Path | None = None) -> dict[str, Any]:
    repo_path = Path(repo).resolve() if repo else None
    service = _query_service()
    service.update(_query_start_type())

    process_pids = _query_process_pids()
    service_pid = service.get("pid") if isinstance(service.get("pid"), int) else None
    non_service_pids = [pid for pid in process_pids if pid != service_pid]
    status = _verdict(service, process_pids, non_service_pids)

    latest_dedupe = None
    latest_dedupe_payload = None
    if repo_path:
        latest_dedupe = _latest_file(runtime_root(repo_path) / "cloudflared", "dedupe-*.json")
        latest_dedupe_payload = _read_json_or_none(latest_dedupe)

    warnings: list[str] = []
    if status == "duplicate_processes":
        warnings.append("More than one cloudflared process is connected locally; stop the non-service duplicate before treating the setup as clean.")
    elif status == "detached_only":
        warnings.append("cloudflared is running only as a detached process; use a Windows service for durable restart behavior.")
    elif status == "service_configured_not_running":
        warnings.append("Cloudflared service exists but is not running.")
    elif status == "not_running":
        warnings.append("No local cloudflared service/process was detected.")

    return {
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "service": service,
        "processes": {
            "imageName": PROCESS_IMAGE,
            "pids": process_pids,
            "count": len(process_pids),
            "nonServicePids": non_service_pids,
        },
        "latestDedupeSummary": str(latest_dedupe) if latest_dedupe else None,
        "latestDedupeStatus": latest_dedupe_payload.get("status") if latest_dedupe_payload else None,
        "warnings": warnings,
        "tokenPrinted": False,
        "tokenMaterialRead": False,
        "serviceCommandLineRead": False,
        "processCommandLineRead": False,
    }


def _timestamp_for_path() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def write_status(repo: Path, payload: dict[str, Any]) -> Path:
    out_dir = runtime_root(repo) / "cloudflared"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"service-status-{_timestamp_for_path()}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print secret-safe cloudflared service/process status.")
    parser.add_argument("--repo", default=str(default_repo_root()))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    payload = build_cloudflared_status(repo)
    if args.write:
        payload["summaryJson"] = str(write_status(repo, payload))
    print(json.dumps(payload, indent=2))
    print("END_RIFTREADER_MCP_CLOUDFLARED_STATUS")
    return 0 if payload.get("status") in {"service_only", "duplicate_processes", "detached_only"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
