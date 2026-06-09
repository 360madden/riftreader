#!/usr/bin/env python3
# Version: riftreader-git-state-reader-v0.1.0
# Total-Character-Count: 0000005662
# Purpose: Read fixed Git status/log state for RiftReader MCP Phase 1A without staging, committing, pushing, or running arbitrary shell.
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
from typing import Any

VERSION = "riftreader-git-state-reader-v0.1.0"
KIND = "riftreader-git-state-reader"
END_MARKER = "END_OF_SCRIPT_MARKER"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safety() -> dict[str, Any]:
    return {
        "gitMutation": False,
        "gitAddDot": False,
        "stagedFiles": False,
        "committed": False,
        "pushed": False,
        "providerWrites": False,
        "inputSent": False,
        "movementSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "readOnlyGit": True,
        "arbitraryShell": False,
    }


def run_git(repo_root: pathlib.Path, args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    allowed = {
        ("status", "--short", "--branch"),
        ("rev-parse", "--abbrev-ref", "HEAD"),
        ("rev-parse", "HEAD"),
        ("rev-list", "--left-right", "--count", "@{upstream}...HEAD"),
    }
    if tuple(args) not in allowed and not (len(args) >= 3 and args[:2] == ["log", "-n"]):
        raise ValueError(f"disallowed-git-args:{args!r}")
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        shell=False,
    )


def parse_status_short_branch(text: str) -> dict[str, Any]:
    branch = None
    paths: list[dict[str, str]] = []
    ahead = None
    behind = None
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line:
            continue
        if line.startswith("## "):
            branch = line[3:]
            if "[ahead " in branch:
                try:
                    ahead = int(branch.split("[ahead ", 1)[1].split("]", 1)[0].split(",", 1)[0])
                except ValueError:
                    ahead = None
            if "behind " in branch:
                try:
                    behind = int(branch.split("behind ", 1)[1].split("]", 1)[0].split(",", 1)[0])
                except ValueError:
                    behind = None
            continue
        if len(line) >= 4:
            paths.append({"xy": line[:2], "path": line[3:]})
    return {"branchLine": branch, "ahead": ahead, "behind": behind, "isClean": not paths, "paths": paths}


def parse_log_records(text: str) -> list[dict[str, str]]:
    commits: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f", 3)
        if len(parts) != 4:
            continue
        sha, short_sha, author_date, subject = parts
        commits.append({
            "sha": sha,
            "shortSha": short_sha,
            "authorDateIso": author_date,
            "subject": subject,
        })
    return commits


def get_dirty_paths(repo_root: pathlib.Path, timeout: float) -> dict[str, Any]:
    proc = run_git(repo_root, ["status", "--short", "--branch"], timeout)
    parsed = parse_status_short_branch(proc.stdout)
    ok = proc.returncode == 0
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-dirty-paths",
        "version": VERSION,
        "generatedAtUtc": utc_now(),
        "status": "clean" if ok and parsed["isClean"] else "dirty" if ok else "blocked",
        "ok": ok,
        "branchLine": parsed["branchLine"],
        "ahead": parsed["ahead"],
        "behind": parsed["behind"],
        "isClean": parsed["isClean"],
        "paths": parsed["paths"],
        "exitCode": proc.returncode,
        "stderrPreview": proc.stderr[-2000:],
        "safety": safety(),
        "endMarker": END_MARKER,
    }


def get_recent_commits(repo_root: pathlib.Path, limit: int, timeout: float) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 50))
    fmt = "%H%x1f%h%x1f%aI%x1f%s"
    proc = run_git(repo_root, ["log", "-n", str(safe_limit), f"--pretty=format:{fmt}"], timeout)
    commits = parse_log_records(proc.stdout)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-recent-commits",
        "version": VERSION,
        "generatedAtUtc": utc_now(),
        "status": "passed" if proc.returncode == 0 else "blocked",
        "ok": proc.returncode == 0,
        "limit": safe_limit,
        "commits": commits,
        "exitCode": proc.returncode,
        "stderrPreview": proc.stderr[-2000:],
        "safety": safety(),
        "endMarker": END_MARKER,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read fixed Git state for RiftReader MCP Phase 1A.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", choices=["dirty-paths", "recent-commits"], required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = pathlib.Path(args.repo_root).resolve()
    if args.mode == "dirty-paths":
        result = get_dirty_paths(repo_root, args.timeout_seconds)
    else:
        result = get_recent_commits(repo_root, args.limit, args.timeout_seconds)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{result['status']} ok={result['ok']}")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
# END_OF_SCRIPT_MARKER
