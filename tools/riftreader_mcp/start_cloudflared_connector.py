#!/usr/bin/env python3
# Version: riftreader-mcp-start-cloudflared-connector-v0.1.0
# Purpose: Start the Cloudflare Tunnel connector from the dashboard-copied token command without printing the token.

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.riftreader_mcp.config import default_repo_root, runtime_root


TOKEN_PATTERN = re.compile(r"cloudflared(?:\.exe)?\s+service\s+install\s+(.+)$", re.IGNORECASE | re.DOTALL)


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_clipboard() -> str:
    try:
        import tkinter  # noqa: PLC0415

        root = tkinter.Tk()
        root.withdraw()
        try:
            return str(root.clipboard_get())
        finally:
            root.destroy()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to read clipboard: {type(exc).__name__}: {exc}") from exc


def clear_clipboard() -> None:
    try:
        import tkinter  # noqa: PLC0415

        root = tkinter.Tk()
        root.withdraw()
        try:
            root.clipboard_clear()
            root.update()
        finally:
            root.destroy()
    except Exception:
        pass


def parse_token(raw: str) -> str:
    command = raw.replace("\r", " ").replace("\n", " ").strip()
    command = re.sub(r"^\s*\$\s*", "", command)
    match = TOKEN_PATTERN.search(command)
    if not match:
        raise ValueError("Clipboard does not contain the expected cloudflared service install command.")
    token = match.group(1).strip().strip('"')
    if len(token) < 40:
        raise ValueError("Parsed connector token is unexpectedly short.")
    return token


def start_connector(repo: Path, *, clear_clip: bool) -> dict[str, Any]:
    raw = read_clipboard()
    token = parse_token(raw)
    if clear_clip:
        clear_clipboard()

    exe = shutil.which("cloudflared.exe") or shutil.which("cloudflared")
    if not exe:
        raise FileNotFoundError("cloudflared.exe was not found on PATH.")

    out_dir = runtime_root(repo) / "cloudflared"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    stdout_log = out_dir / f"detached-{stamp}.log"
    stderr_log = out_dir / f"detached-{stamp}.err.log"
    summary = out_dir / f"detached-{stamp}.json"

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    stdout_handle = stdout_log.open("ab")
    stderr_handle = stderr_log.open("ab")
    try:
        proc = subprocess.Popen(
            [exe, "tunnel", "--no-autoupdate", "run", "--token", token],
            cwd=str(repo),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            close_fds=True,
            creationflags=creationflags,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()

    payload = {
        "version": "riftreader-mcp-start-cloudflared-connector-v0.1.0",
        "generatedAtUtc": utc_iso(),
        "status": "started",
        "pid": proc.pid,
        "cloudflaredExe": exe,
        "stdoutLog": str(stdout_log),
        "stderrLog": str(stderr_log),
        "summaryJson": str(summary),
        "tokenPrinted": False,
        "clipboardCleared": clear_clip,
    }
    summary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start cloudflared connector from dashboard-copied command.")
    parser.add_argument("--repo", default=str(default_repo_root()))
    parser.add_argument("--from-clipboard", action="store_true", required=True)
    parser.add_argument("--clear-clipboard", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = start_connector(Path(args.repo).resolve(), clear_clip=args.clear_clipboard)
        print(json.dumps(payload, indent=2))
        print("PASS")
        print("END_RIFTREADER_CLOUDFLARED_CONNECTOR_START")
        return 0
    except Exception as exc:  # noqa: BLE001
        payload = {
            "version": "riftreader-mcp-start-cloudflared-connector-v0.1.0",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "tokenPrinted": False,
        }
        print(json.dumps(payload, indent=2))
        print("FAIL")
        print("END_RIFTREADER_CLOUDFLARED_CONNECTOR_START")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
