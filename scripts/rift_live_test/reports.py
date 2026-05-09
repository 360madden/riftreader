from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        for attempt in range(5):
            try:
                os.replace(temp_path, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_json(path: Path, data: Any) -> None:
    write_text_atomic(path, json.dumps(data, indent=2) + "\n")


def write_markdown_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Live test summary: {summary.get('profileName')}",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- OK: `{str(summary.get('ok')).lower()}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Run directory: `{summary.get('runDirectory')}`",
        f"- Live flag: `{str(summary.get('live')).lower()}`",
        f"- Movement sent: `{str(summary.get('movementSent')).lower()}`",
    ]
    if summary.get("currentCoordinate"):
        coord = summary["currentCoordinate"]
        lines.append(
            "- Current coordinate: "
            f"`X={coord.get('x')}`, `Y={coord.get('y')}`, `Z={coord.get('z')}` "
            f"at `{coord.get('recordedAtUtc')}`"
        )
    if summary.get("coordinateDelta"):
        delta = summary["coordinateDelta"]
        lines.append(
            "- Coordinate delta: "
            f"planar `{delta.get('planarDistance')}`, "
            f"dX `{delta.get('deltaX')}`, dY `{delta.get('deltaY')}`, "
            f"dZ `{delta.get('deltaZ')}`"
        )
    if summary.get("seriesPulses"):
        lines.extend(
            [
                f"- Series pulses: `{summary.get('completedPulseCount')}` / "
                f"`{summary.get('requestedPulseCount')}` completed",
            ]
        )
        if summary.get("seriesCoordinateDelta"):
            series_delta = summary["seriesCoordinateDelta"]
            lines.append(
                "- Series delta: "
                f"planar `{series_delta.get('planarDistance')}`, "
                f"dX `{series_delta.get('deltaX')}`, "
                f"dY `{series_delta.get('deltaY')}`, "
                f"dZ `{series_delta.get('deltaZ')}`"
            )
    if summary.get("runHealth"):
        health = summary["runHealth"]
        lines.extend(
            [
                "",
                "## Run health",
                "",
                "| Field | Value |",
                "|---|---|",
                f"| State | `{health.get('state')}` |",
                f"| Issue count | `{health.get('issueCount')}` |",
                f"| Primary issue | `{health.get('primaryIssue')}` |",
                f"| Movement sent | `{str(health.get('movementSent')).lower()}` |",
                f"| Movement attempted | `{str(health.get('movementAttempted')).lower()}` |",
                f"| Final summary written | `{str(health.get('finalSummaryWritten')).lower()}` |",
                f"| No Cheat Engine | `{str(health.get('noCheatEngine')).lower()}` |",
                "| SavedVariables live truth | "
                f"`{str(health.get('savedVariablesUsedAsLiveTruth')).lower()}` |",
            ]
        )
    if summary.get("currentProofPointerUpdate"):
        update = summary["currentProofPointerUpdate"]
        archive = update.get("archivedSupersededPointer") if isinstance(update, dict) else None
        archive_path = archive.get("path") if isinstance(archive, dict) else None
        lines.extend(
            [
                "",
                "## Current proof pointer update",
                "",
                "| Field | Value |",
                "|---|---|",
                f"| Updated | `{str(update.get('updated')).lower()}` |",
                f"| Pointer | `{update.get('path')}` |",
                f"| Archived superseded pointer | `{archive_path}` |",
            ]
        )
    if summary.get("issues"):
        lines.extend(["", "## Issues"])
        for issue in summary["issues"]:
            lines.append(f"- `{issue}`")
    if summary.get("seriesPulses"):
        lines.extend(
            [
                "",
                "## Series pulses",
                "",
                "| Pulse | Status | Stage | Sent | Planar delta | Summary |",
                "|---:|---|---|---|---:|---|",
            ]
        )
        for pulse in summary.get("seriesPulses", []):
            delta = pulse.get("coordinateDelta") or {}
            summary_file = pulse.get("liveSummaryFile") or pulse.get("dryRunSummaryFile") or ""
            lines.append(
                f"| `{pulse.get('pulseIndex')}` | `{pulse.get('status')}` | "
                f"`{pulse.get('stage')}` | `{str(pulse.get('movementSent')).lower()}` | "
                f"`{delta.get('planarDistance')}` | `{summary_file}` |"
            )
    if summary.get("coordinateRecordings"):
        lines.extend(
            [
                "",
                "## Coordinate recordings",
                "",
                "| Pulse | Samples | Phases | File |",
                "|---:|---:|---|---|",
            ]
        )
        for recording in summary.get("coordinateRecordings", []):
            phases = recording.get("phases") or {}
            phase_text = ", ".join(f"{name}={count}" for name, count in sorted(phases.items()))
            lines.append(
                f"| `{recording.get('pulseIndex')}` | `{recording.get('sampleCount')}` | "
                f"`{phase_text}` | `{recording.get('pulseSummaryFile')}` |"
            )
    lines.extend(["", "## State history", "", "| State | Status | Detail |", "|---|---|---|"])
    for state in summary.get("states", []):
        detail = state.get("detail") or state.get("summaryFile") or ""
        lines.append(f"| `{state.get('state')}` | `{state.get('status')}` | `{detail}` |")
    write_text_atomic(path, "\n".join(lines).rstrip() + "\n")
