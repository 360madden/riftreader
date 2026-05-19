#!/usr/bin/env python3
"""Shared safe workflow utilities for RiftReader local helpers.

This module intentionally contains only deterministic, offline-safe primitives:
time formatting, repo-relative path rendering, duplicate filtering, standard
safety flags, and repo-root discovery. It must not send live input, attach
debuggers, mutate Git state, or write provider repositories.
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TypeVar


T = TypeVar("T")


def utc_iso() -> str:
    """Return the current UTC time in compact ISO-8601 form."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    """Return a filesystem-safe UTC timestamp."""

    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")


def find_repo_root(start: Path) -> Path:
    """Find the RiftReader repo root by walking upward from *start*."""

    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "agents.md").is_file():
            return candidate
    raise RuntimeError(f"Could not find RiftReader repo root from {start}")


def repo_rel(repo_root: Path, path: Path | None) -> str | None:
    """Render *path* relative to *repo_root* when possible, using Windows separators."""

    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("/", "\\")
    except ValueError:
        return str(path)


def unique(values: Iterable[T]) -> list[T]:
    """Return values in first-seen order with duplicates removed."""

    seen: set[T] = set()
    result: list[T] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def preview_text(text: str | None, *, max_lines: int = 80, max_chars: int = 8000) -> str:
    """Return a bounded preview suitable for command envelopes."""

    if not text:
        return ""
    lines = text.splitlines()
    preview = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        preview += f"\n... truncated {len(lines) - max_lines} line(s)"
    if len(preview) > max_chars:
        preview = preview[:max_chars] + f"\n... truncated to {max_chars} char(s)"
    return preview


def run_command_envelope(
    label: str,
    args: list[str],
    cwd: Path,
    *,
    timeout_seconds: float = 30.0,
    expected_exit_codes: set[int] | None = None,
    capture_full_output: bool = False,
) -> dict[str, Any]:
    """Run a local command and return a bounded diagnostic envelope.

    This helper does not add any mutation authority. Callers must still choose
    safe command arguments and expected exit codes.
    """

    expected = expected_exit_codes if expected_exit_codes is not None else {0}
    started = utc_iso()
    start_monotonic = time.monotonic()
    envelope: dict[str, Any] = {
        "label": label,
        "args": args,
        "cwd": str(cwd),
        "startedAtUtc": started,
        "timeoutSeconds": timeout_seconds,
        "exitCode": None,
        "ok": False,
        "timedOut": False,
        "stdoutPreview": "",
        "stderrPreview": "",
    }
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        envelope["exitCode"] = completed.returncode
        envelope["ok"] = completed.returncode in expected
        envelope["stdoutPreview"] = preview_text(completed.stdout)
        envelope["stderrPreview"] = preview_text(completed.stderr)
        if capture_full_output:
            envelope["stdout"] = completed.stdout
            envelope["stderr"] = completed.stderr
    except subprocess.TimeoutExpired as exc:
        envelope["timedOut"] = True
        envelope["error"] = f"TimeoutExpired:{exc}"
        envelope["stdoutPreview"] = preview_text(exc.stdout if isinstance(exc.stdout, str) else "")
        envelope["stderrPreview"] = preview_text(exc.stderr if isinstance(exc.stderr, str) else "")
    except FileNotFoundError as exc:
        envelope["error"] = f"FileNotFoundError:{exc}"
    except Exception as exc:  # noqa: BLE001 - command envelope must capture unexpected local failures.
        envelope["error"] = f"{type(exc).__name__}:{exc}"
    finally:
        envelope["endedAtUtc"] = utc_iso()
        envelope["durationSeconds"] = round(time.monotonic() - start_monotonic, 3)
    return envelope


def safety_flags() -> dict[str, bool]:
    """Return the shared fail-closed workflow safety state."""

    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "providerWrites": False,
        "gitMutation": False,
        "applyFlagSent": False,
        "savedVariablesUsedAsLiveTruth": False,
    }


def timestamped_output_dir(base: Path, *, create: bool = True) -> Path:
    """Return a unique timestamped child directory under *base*."""

    stamp = utc_stamp()
    output_dir = base / stamp
    suffix = 2
    while output_dir.exists():
        output_dir = base / f"{stamp}-{suffix}"
        suffix += 1
    if create:
        output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir
