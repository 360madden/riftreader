#!/usr/bin/env python3
"""Shared safe workflow utilities for RiftReader local helpers.

This module intentionally contains only deterministic, offline-safe primitives:
time formatting, repo-relative path rendering, duplicate filtering, standard
safety flags, and repo-root discovery. It must not send live input, attach
debuggers, mutate Git state, or write provider repositories.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, TypeVar


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
