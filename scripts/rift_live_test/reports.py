from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
