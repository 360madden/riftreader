"""Shared workflow utilities for the static-owner navigation pipeline.

Provides canonical implementations of common helpers used across multiple
navigation scripts: subprocess orchestration, JSON I/O, safety defaults,
timestamps, and type-safe mapping wrappers.

All navigation-pipeline scripts should import from here rather than
re-defining these helpers.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


def utc_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def utc_stamp() -> str:
    """Return a compact UTC timestamp suitable for directory/file names."""
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root() -> Path:
    """Resolve the repository root from the current file's location."""
    return Path(__file__).resolve().parents[1]


def safe_mapping(value: Any) -> dict[str, Any]:
    """Safely cast a value to ``dict[str, Any]``, returning ``{}`` if not a Mapping."""
    return dict(value) if isinstance(value, Mapping) else {}


def preview(text: str, *, limit: int = 2000) -> str:
    """Truncate *text* to *limit* chars, appending ``...<truncated>`` if exceeded."""
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def load_json_object(path: str | Path) -> dict[str, Any]:
    """Read and parse a JSON file, raising if the root value is not an object."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON file is not an object: {path}")
    return data


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    """Write a JSON object to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def base_safety() -> dict[str, Any]:
    """Return a default safety-gate dictionary with all flags in a safe initial state."""
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "debuggerAttached": False,
        "providerWrites": False,
        "gitMutation": False,
        "proofPromotion": False,
        "actorChainPromotion": False,
        "facingPromotion": False,
        "navigationControl": False,
        "savedVariablesUsedAsLiveTruth": False,
        "navStateCandidateOnly": True,
        "actionableForNavigation": False,
    }


def run_child(
    *,
    label: str,
    command: Sequence[str],
    cwd: Path,
    child_dir: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run a subprocess, capture output, and return a structured envelope.

    The envelope includes stdout/stderr previews, parsed JSON (if applicable),
    timing metadata, and a persistent command-record JSON file.
    """
    child_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = child_dir / f"{label}.stdout.txt"
    stderr_path = child_dir / f"{label}.stderr.txt"
    command_path = child_dir / f"{label}.command.json"
    started = time.perf_counter()
    started_utc = utc_iso()
    parsed: Any = None
    parse_error: str | None = None
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
        if stdout.strip():
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError as exc:
                parse_error = f"JSONDecodeError:{exc}"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        exit_code = 124
        parse_error = f"TimeoutExpired:{exc}"

    duration = time.perf_counter() - started
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    envelope: dict[str, Any] = {
        "label": label,
        "command": list(command),
        "cwd": str(cwd),
        "startedAtUtc": started_utc,
        "endedAtUtc": utc_iso(),
        "durationSeconds": duration,
        "exitCode": exit_code,
        "ok": exit_code == 0,
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
        "stdoutPreview": preview(stdout),
        "stderrPreview": preview(stderr),
        "json": parsed,
        "jsonParseError": parse_error,
    }
    write_json(command_path, {key: value for key, value in envelope.items() if key != "json"})
    envelope["commandPath"] = str(command_path)
    return envelope


def full_summary_from_compact(compact: Mapping[str, Any]) -> dict[str, Any]:
    """Load the full summary JSON referenced by a child command's compact envelope."""
    path = compact.get("summaryJson")
    if not path:
        raise ValueError("child-compact-summary-json-missing")
    return load_json_object(str(path))
