#!/usr/bin/env python3
# Version: riftreader-maintenance-blocked-handoff-helper-v0.1.0
# Total-Character-Count: 33103
# Purpose: Create a RiftReader maintenance-blocked handoff/status package, optionally update Drive status, and optionally commit/push only generated handoff files.

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REPO_ROOT = Path(r"C:\RIFT MODDING\RiftReader")
DEFAULT_DRIVE_ROOT = Path(r"G:\My Drive\RiftReader")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, indent=2))


def run_command(args: list[str], cwd: Path, timeout_seconds: int = 60) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "args": args,
            "cwd": str(cwd),
            "exitCode": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "timedOut": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "cwd": str(cwd),
            "exitCode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timedOut": True,
            "timeoutSeconds": timeout_seconds,
        }


def require_success(result: dict[str, Any], label: str) -> None:
    if result.get("exitCode") != 0 or result.get("timedOut"):
        raise RuntimeError(
            f"{label} failed exit={result.get('exitCode')} timedOut={result.get('timedOut')} "
            f"stderr={str(result.get('stderr') or '')[:1000]}"
        )


def git(repo_root: Path, *args: str, timeout_seconds: int = 60) -> dict[str, Any]:
    return run_command(["git", *args], cwd=repo_root, timeout_seconds=timeout_seconds)


def git_lines(repo_root: Path, *args: str, timeout_seconds: int = 60) -> list[str]:
    result = git(repo_root, *args, timeout_seconds=timeout_seconds)
    require_success(result, "git " + " ".join(args))
    return str(result.get("stdout") or "").splitlines()


def status_lines(repo_root: Path) -> list[str]:
    return git_lines(repo_root, "status", "--short")


def tracked_or_staged_status_lines(lines: list[str]) -> list[str]:
    risky: list[str] = []
    for line in lines:
        if not line:
            continue
        if line.startswith("?? "):
            continue
        risky.append(line)
    return risky


def resolve_repo_root(candidate: str | None) -> Path:
    if candidate:
        root = Path(candidate).resolve()
    else:
        cwd = Path.cwd().resolve()
        root = cwd if (cwd / ".git").exists() else DEFAULT_REPO_ROOT.resolve()
    if not root.exists():
        raise FileNotFoundError(f"repo root not found: {root}")
    if not (root / ".git").exists():
        raise RuntimeError(f"not a git repository: {root}")
    return root


def resolve_powershell() -> str | None:
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    return None


def collect_rift_process_snapshot(repo_root: Path, process_name: str) -> dict[str, Any]:
    ps = resolve_powershell()
    if not ps:
        return {
            "status": "unavailable",
            "reason": "powershell_not_found",
            "processName": process_name,
            "items": [],
        }

    script = f"""
$ErrorActionPreference = 'Stop'
$ProcessName = '{process_name.replace("'", "''")}'
$items = @(Get-Process -Name $ProcessName -ErrorAction SilentlyContinue | ForEach-Object {{
    [ordered]@{{
        processName = [string]$_.ProcessName
        processId = [int]$_.Id
        mainWindowTitle = [string]$_.MainWindowTitle
        mainWindowHandle = ('0x{{0:X}}' -f [int64]$_.MainWindowHandle)
        path = try {{ [string]$_.Path }} catch {{ $null }}
        startTimeUtc = try {{ $_.StartTime.ToUniversalTime().ToString('o') }} catch {{ $null }}
    }}
}})
[ordered]@{{
    status = 'captured'
    processName = $ProcessName
    count = [int]$items.Count
    items = $items
}} | ConvertTo-Json -Depth 8
"""
    result = run_command(
        [ps, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=repo_root,
        timeout_seconds=30,
    )
    if result.get("exitCode") != 0:
        return {
            "status": "failed",
            "processName": process_name,
            "error": result.get("stderr") or result.get("stdout"),
            "items": [],
        }
    try:
        return json.loads(str(result.get("stdout") or "{}"))
    except json.JSONDecodeError as exc:
        return {
            "status": "failed",
            "processName": process_name,
            "error": f"json_decode_error:{exc}",
            "stdoutPreview": str(result.get("stdout") or "")[:2000],
            "items": [],
        }


def find_latest_stage1_summary(repo_root: Path) -> dict[str, Any] | None:
    captures = repo_root / "scripts" / "captures"
    if not captures.exists():
        return None
    candidates: list[Path] = []
    for pattern, summary_name in (
        ("postupdate-proof-reacquire-stage1-*", "stage1-wrapper-summary.json"),
        ("postupdate-proof-reacquire-stage1-python-*", "stage1-python-summary.json"),
    ):
        for directory in captures.glob(pattern):
            candidate = directory / summary_name
            if candidate.is_file():
                candidates.append(candidate)
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        parsed = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        parsed = {"status": "unreadable", "error": f"{type(exc).__name__}: {exc}"}
    return {
        "path": str(latest),
        "modifiedUtc": datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "summary": parsed,
    }


def current_handoff_markdown(doc: dict[str, Any]) -> str:
    repo = doc.get("repo", {})
    process = doc.get("riftProcessSnapshot", {})
    latest_stage1 = doc.get("latestStage1Summary") or {}
    return "\n".join(
        [
            "# RiftReader Current Handoff",
            "",
            f"- Status: `{doc.get('status')}`",
            f"- Generated UTC: `{doc.get('generatedUtc')}`",
            f"- Current lane: `{doc.get('currentLane')}`",
            f"- Branch: `{repo.get('branch')}`",
            f"- HEAD: `{repo.get('head')}`",
            f"- Dirty files before handoff: `{len(repo.get('statusBefore') or [])}`",
            f"- RIFT process snapshot status: `{process.get('status')}`",
            f"- RIFT process count: `{process.get('count', len(process.get('items') or []))}`",
            f"- Latest Stage 1 summary: `{latest_stage1.get('path')}`",
            "",
            "## Current blocker",
            "",
            str(doc.get("currentBlocker") or ""),
            "",
            "## Exact next action",
            "",
            str(doc.get("exactNextAction") or ""),
            "",
            "## Do not do",
            "",
            *[f"- {item}" for item in doc.get("doNotDo") or []],
            "",
            "## Verified helper state",
            "",
            *[f"- `{item}`" for item in doc.get("verifiedHelpers") or []],
            "",
            "## Drive artifacts",
            "",
            *[f"- `{item}`" for item in doc.get("driveArtifactPaths") or []],
            "",
            "# END_OF_DOCUMENT_MARKER",
            "",
        ]
    )


def run_summary_markdown(doc: dict[str, Any]) -> str:
    repo = doc.get("repo", {})
    return "\n".join(
        [
            "# RiftReader Maintenance-Blocked Handoff",
            "",
            f"- Status: `{doc.get('status')}`",
            f"- Generated UTC: `{doc.get('generatedUtc')}`",
            f"- Repo root: `{doc.get('repoRoot')}`",
            f"- Branch: `{repo.get('branch')}`",
            f"- HEAD: `{repo.get('head')}`",
            f"- Current lane: `{doc.get('currentLane')}`",
            "",
            "## Reason",
            "",
            str(doc.get("currentBlocker") or ""),
            "",
            "## Next action",
            "",
            str(doc.get("exactNextAction") or ""),
            "",
            "## Generated artifacts",
            "",
            *[f"- `{path}`" for path in doc.get("generatedArtifacts") or []],
            "",
            "# END_OF_DOCUMENT_MARKER",
            "",
        ]
    )


def build_handoff_doc(repo_root: Path, drive_root: Path, process_name: str) -> dict[str, Any]:
    branch = (git(repo_root, "branch", "--show-current").get("stdout") or "").strip()
    head = (git(repo_root, "rev-parse", "HEAD").get("stdout") or "").strip()
    status_before = status_lines(repo_root)
    process_snapshot = collect_rift_process_snapshot(repo_root, process_name)
    latest_stage1 = find_latest_stage1_summary(repo_root)

    return {
        "schemaVersion": 1,
        "mode": "riftreader-maintenance-blocked-handoff",
        "status": "maintenance-blocked",
        "generatedUtc": utc_iso(),
        "repoRoot": str(repo_root),
        "currentLane": "post-update proof-anchor reacquisition paused because RIFT is down for maintenance",
        "currentBlocker": "RIFT is unavailable/down for maintenance. Live target resolution, visual gate, coordinate-family scan, proof promotion, ProofOnly, yaw, route smoke, and movement workflows are blocked until the game is back and Atank is confirmed in-world.",
        "exactNextAction": "After maintenance ends: pull latest main if needed, log into Atank in-world, then run cmd\\riftreader-postupdate-proof-reacquire-stage1.cmd --visual-full. Only run --allow-movement-stimulus after visual gate and coordinate truth are healthy.",
        "repo": {
            "branch": branch,
            "head": head,
            "statusBefore": status_before,
            "trackedOrStagedBefore": tracked_or_staged_status_lines(status_before),
        },
        "riftProcessSnapshot": process_snapshot,
        "latestStage1Summary": latest_stage1,
        "verifiedHelpers": [
            "cmd/riftreader-postupdate-proof-reacquire-stage1.cmd",
            "scripts/riftreader_postupdate_proof_reacquire_stage1.py",
            "scripts/test_riftreader_postupdate_proof_reacquire_stage1.py",
            "docs/development/postupdate-proof-reacquire-stage1.md",
        ],
        "driveArtifactPaths": [
            str(drive_root / "status" / "RIFTREADER_CURRENT_STATUS.md"),
            str(drive_root / "status" / "RIFTREADER_CURRENT_STATUS.json"),
        ],
        "doNotDo": [
            "Do not run live recovery while RIFT is down for maintenance.",
            "Do not run Stage 1, ProofOnly, promotion, yaw, route smoke, auto-turn, or navigation until Atank is in-world.",
            "Do not update docs/recovery/current-truth.md or docs/recovery/current-proof-anchor-readback.json before same-target ProofOnly passes.",
            "Do not use old PID/HWND proof pointers as current truth.",
            "Do not commit unrelated local changes.",
        ],
        "generatedArtifacts": [],
    }


def create_handoff(repo_root: Path, drive_root: Path, process_name: str, write_drive: bool) -> dict[str, Any]:
    stamp = utc_stamp()
    out_dir = repo_root / "handoffs" / "current" / "maintenance-blocked" / stamp
    handoff_json = out_dir / "RIFTREADER_MAINTENANCE_BLOCKED_HANDOFF.json"
    handoff_md = out_dir / "RIFTREADER_MAINTENANCE_BLOCKED_HANDOFF.md"
    current_json = repo_root / "handoffs" / "current" / "RIFTREADER_CURRENT_HANDOFF.json"
    current_md = repo_root / "handoffs" / "current" / "RIFTREADER_CURRENT_HANDOFF.md"

    doc = build_handoff_doc(repo_root, drive_root, process_name)
    doc["generatedArtifacts"] = [
        str(handoff_json),
        str(handoff_md),
        str(current_json),
        str(current_md),
    ]

    write_json(handoff_json, doc)
    write_text(handoff_md, run_summary_markdown(doc))
    write_json(current_json, doc)
    write_text(current_md, current_handoff_markdown(doc))

    drive_written: list[str] = []
    if write_drive and drive_root.exists():
        status_md = drive_root / "status" / "RIFTREADER_CURRENT_STATUS.md"
        status_json = drive_root / "status" / "RIFTREADER_CURRENT_STATUS.json"
        write_text(status_md, current_handoff_markdown(doc))
        write_json(status_json, doc)
        drive_written = [str(status_md), str(status_json)]

    return {
        "doc": doc,
        "repoFiles": [str(handoff_json.relative_to(repo_root)), str(handoff_md.relative_to(repo_root)), str(current_json.relative_to(repo_root)), str(current_md.relative_to(repo_root))],
        "driveFiles": drive_written,
        "outDir": str(out_dir),
    }


def commit_generated(repo_root: Path, repo_files: list[str], message: str, push: bool) -> dict[str, Any]:
    before_lines = status_lines(repo_root)
    unexpected_tracked = [
        line for line in tracked_or_staged_status_lines(before_lines)
        if not any(line.endswith(path.replace("/", os.sep)) or line.endswith(path) for path in repo_files)
    ]
    if unexpected_tracked:
        raise RuntimeError("Refusing commit because unrelated tracked/staged changes exist: " + json.dumps(unexpected_tracked))

    add_result = git(repo_root, "add", "--", *repo_files)
    require_success(add_result, "git add explicit generated files")
    diff_check = git(repo_root, "diff", "--check", "--cached")
    require_success(diff_check, "git diff --check --cached")
    cached_files = git_lines(repo_root, "diff", "--cached", "--name-only")
    if sorted(cached_files) != sorted(repo_files):
        raise RuntimeError(f"Staged file allowlist mismatch. staged={cached_files} expected={repo_files}")

    if not cached_files:
        return {
            "commitCreated": False,
            "reason": "no_changes_to_commit",
            "staged": [],
        }

    commit_result = git(repo_root, "commit", "-m", message, timeout_seconds=120)
    require_success(commit_result, "git commit")
    head = (git(repo_root, "rev-parse", "HEAD").get("stdout") or "").strip()

    result: dict[str, Any] = {
        "commitCreated": True,
        "staged": cached_files,
        "commitStdout": commit_result.get("stdout"),
        "commitStderr": commit_result.get("stderr"),
        "head": head,
    }

    if push:
        branch = (git(repo_root, "branch", "--show-current").get("stdout") or "").strip() or "main"
        push_result = git(repo_root, "push", "origin", branch, timeout_seconds=180)
        result["pushExitCode"] = push_result.get("exitCode")
        result["pushStdout"] = push_result.get("stdout")
        result["pushStderr"] = push_result.get("stderr")
        require_success(push_result, "git push")
        remote = git(repo_root, "ls-remote", "origin", f"refs/heads/{branch}")
        require_success(remote, "git ls-remote")
        remote_sha = (remote.get("stdout") or "").split()[0] if (remote.get("stdout") or "").split() else ""
        result["remoteSha"] = remote_sha
        result["remoteVerified"] = remote_sha == head
        if remote_sha != head:
            raise RuntimeError(f"Remote SHA verification failed. local={head} remote={remote_sha}")

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create RiftReader maintenance-blocked handoff/status artifacts.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--drive-root", default=str(DEFAULT_DRIVE_ROOT))
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--no-drive", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = resolve_repo_root(args.repo_root)
    drive_root = Path(args.drive_root)
    status_before = status_lines(repo_root)
    preexisting_tracked = tracked_or_staged_status_lines(status_before)
    if preexisting_tracked:
        raise RuntimeError("Refusing to generate handoff because tracked/staged local changes already exist: " + json.dumps(preexisting_tracked))

    handoff = create_handoff(
        repo_root=repo_root,
        drive_root=drive_root,
        process_name=args.process_name,
        write_drive=not args.no_drive,
    )

    commit_result = None
    if args.commit:
        commit_result = commit_generated(
            repo_root=repo_root,
            repo_files=handoff["repoFiles"],
            message="Record RiftReader maintenance blocked handoff",
            push=bool(args.push),
        )

    result = {
        "status": "created",
        "repoRoot": str(repo_root),
        "outDir": handoff["outDir"],
        "repoFiles": handoff["repoFiles"],
        "driveFiles": handoff["driveFiles"],
        "commit": commit_result,
        "afterStatusShort": status_lines(repo_root),
        "next": handoff["doc"]["exactNextAction"],
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=== RIFTREADER MAINTENANCE HANDOFF ===")
        print(f"Status   : {result['status']}")
        print(f"OutDir   : {result['outDir']}")
        print(f"RepoFiles: {len(result['repoFiles'])}")
        print(f"Drive    : {len(result['driveFiles'])} files")
        if commit_result:
            print(f"Commit   : {commit_result.get('head')}")
            print(f"RemoteOK : {commit_result.get('remoteVerified')}")
        print(f"Next     : {result['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
