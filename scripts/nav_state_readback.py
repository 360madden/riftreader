#!/usr/bin/env python3
"""Shared pointer-chain nav-state readback helper.

Single source of truth for spawning the promoted static resolver subprocess
with --nav-state. All navigation/decision tools import from here instead of
having their own duplicate subprocess logic.

Usage:
    from scripts.nav_state_readback import read_nav_state
    result = read_nav_state(
        root=Path("."),
        use_current_truth=True,
        current_truth_json="docs/recovery/current-truth.json",
    )
    if result["ok"]:
        print(f"Yaw: {result['yawDegrees']}, Turn: {result['turnRateClassification']}")

Returns a dict with:
    ok: bool                  — True when subprocess succeeded AND nav-state parsed
    exitCode: int             — subprocess exit code
    status: str               — readback status (passed/blocked/unavailable/parse-error/timeout)
    verdict: str | None       — readback verdict
    commanderAddress: str     — owner object address (hex)
    yawDegrees: float | None
    pitchDegrees: float | None
    turnRate0x304: float | None
    turnRateClassification: str
    facingTargetCoordinate: dict | None
    playerCoordinate: dict | None
    planarLookaheadDistance: float | None
    error: str | None         — error string (None when ok)
    stdoutPreview: str
    stderrPreview: str
    rawJson: dict | None      — full parsed JSON from subprocess

Safety: this is a READ-ONLY subprocess. No game input, no debugger attach,
no mutation.
"""  # noqa: D205
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


def safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def preview(text: str, *, limit: int = 2000) -> str:
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def read_nav_state(
    *,
    root: Path,
    pid: int | None = None,
    hwnd: str | None = None,
    module_base: str | None = None,
    process_name: str = "rift_x64",
    current_truth_json: str = "docs/recovery/current-truth.json",
    use_current_truth: bool = False,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Run the promoted static resolver with --nav-state as a read-only subprocess.

    Supports two target modes:
    1. Explicit: --pid, --hwnd, --module-base (for live window enumeration)
    2. Current-truth: --use-current-truth, --current-truth-json (auto-populate from truth JSON)

    Returns a comprehensive dict with all nav-state fields. Callers should
    check result["ok"] before consuming fields.
    """
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_coordinate_chain_readback.py"),
        "--repo-root", str(root),
        "--nav-state",
        "--json",
    ]
    if use_current_truth:
        command += [
            "--current-truth-json", str(current_truth_json),
            "--use-current-truth",
        ]
    else:
        if pid is not None:
            command += ["--pid", str(pid)]
        if hwnd is not None:
            command += ["--hwnd", str(hwnd)]
        if module_base is not None:
            command += ["--module-base", str(module_base)]
    if process_name:
        command += ["--process-name", str(process_name)]

    try:
        result = subprocess.run(
            command,
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        parsed: Any = None
        parse_error: str | None = None
        if result.stdout.strip():
            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                parse_error = f"JSONDecodeError:{exc}"

        if parse_error:
            return {
                "ok": False,
                "exitCode": result.returncode,
                "status": "parse-error",
                "verdict": None,
                "commanderAddress": None,
                "yawDegrees": None,
                "pitchDegrees": None,
                "turnRate0x304": None,
                "turnRateClassification": "unknown",
                "facingTargetCoordinate": None,
                "playerCoordinate": None,
                "planarLookaheadDistance": None,
                "error": parse_error,
                "stdoutPreview": preview(result.stdout),
                "stderrPreview": preview(result.stderr),
                "rawJson": None,
            }

        if not isinstance(parsed, dict):
            return {
                "ok": False,
                "exitCode": result.returncode,
                "status": "parse-error",
                "verdict": None,
                "commanderAddress": None,
                "yawDegrees": None,
                "pitchDegrees": None,
                "turnRate0x304": None,
                "turnRateClassification": "unknown",
                "facingTargetCoordinate": None,
                "playerCoordinate": None,
                "planarLookaheadDistance": None,
                "error": "readback-output-is-not-a-json-object",
                "stdoutPreview": preview(result.stdout),
                "stderrPreview": preview(result.stderr),
                "rawJson": None,
            }

        nav_state = safe_mapping(parsed.get("navState"))
        reads = safe_mapping(parsed.get("reads"))

        return {
            "ok": parsed.get("status") not in ("unavailable", "readback-failed", "parse-error", "blocked"),
            "exitCode": result.returncode,
            "status": parsed.get("status"),
            "verdict": parsed.get("verdict"),
            "commanderAddress": reads.get("ownerAddress"),
            "rawJson": parsed,
            "yawDegrees": nav_state.get("yawDegrees"),
            "pitchDegrees": nav_state.get("pitchDegrees"),
            "turnRate0x304": nav_state.get("turnRate0x304"),
            "turnRateClassification": str(nav_state.get("turnRateClassification") or "unknown"),
            "facingTargetCoordinate": nav_state.get("facingTargetCoordinate"),
            "playerCoordinate": nav_state.get("coordinate"),
            "planarLookaheadDistance": nav_state.get("planarLookaheadDistance"),
            "error": None,
            "stdoutPreview": preview(result.stdout),
            "stderrPreview": preview(result.stderr),
        }

    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exitCode": 124,
            "status": "timeout",
            "verdict": None,
            "commanderAddress": None,
            "yawDegrees": None,
            "pitchDegrees": None,
            "turnRate0x304": None,
            "turnRateClassification": "unknown",
            "facingTargetCoordinate": None,
            "playerCoordinate": None,
            "planarLookaheadDistance": None,
            "error": f"TimeoutExpired:{exc}",
            "stdoutPreview": "",
            "stderrPreview": preview(exc.stderr if isinstance(exc.stderr, str) else ""),
            "rawJson": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "exitCode": -1,
            "status": "error",
            "verdict": None,
            "commanderAddress": None,
            "yawDegrees": None,
            "pitchDegrees": None,
            "turnRate0x304": None,
            "turnRateClassification": "unknown",
            "facingTargetCoordinate": None,
            "playerCoordinate": None,
            "planarLookaheadDistance": None,
            "error": f"{type(exc).__name__}:{exc}",
            "stdoutPreview": "",
            "stderrPreview": "",
            "rawJson": None,
        }
