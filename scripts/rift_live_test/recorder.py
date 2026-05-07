from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reports import write_json


def coordinate_recording_enabled(profile: dict[str, Any]) -> bool:
    recording = profile.get("recording")
    return isinstance(recording, dict) and bool(recording.get("coordSamples"))


def record_pulse_coordinates(
    *,
    run_dir: Path,
    profile_name: str,
    profile: dict[str, Any],
    process_id: int,
    target_window_handle: str,
    pulse_index: int,
    stage: str,
    dry_run: dict[str, Any] | None,
    live_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not coordinate_recording_enabled(profile):
        return None

    recorder_dir = run_dir / "recorder"
    recorder_dir.mkdir(parents=True, exist_ok=True)
    samples_file = recorder_dir / "coord-samples.ndjson"
    pulse_summary_file = recorder_dir / f"coord-pulse-{pulse_index:03d}-summary.json"
    samples_file.touch(exist_ok=True)

    samples = _samples_for_pulse(
        profile_name=profile_name,
        process_id=process_id,
        target_window_handle=target_window_handle,
        pulse_index=pulse_index,
        stage=stage,
        dry_run=dry_run,
        live_result=live_result,
    )
    if samples:
        with samples_file.open("a", encoding="utf-8") as handle:
            for sample in samples:
                handle.write(json.dumps(sample, sort_keys=True) + "\n")

    first = samples[0]["coordinate"] if samples else None
    last = samples[-1]["coordinate"] if samples else None
    summary = {
        "schemaVersion": 1,
        "mode": "rift-live-test-coordinate-recording",
        "profileName": profile_name,
        "pulseIndex": pulse_index,
        "stage": stage,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sampleCount": len(samples),
        "samplesFile": str(samples_file),
        "pulseSummaryFile": str(pulse_summary_file),
        "processId": process_id,
        "targetWindowHandle": target_window_handle,
        "noCheatEngine": True,
        "savedVariablesUsedAsLiveTruth": False,
        "phases": _phase_counts(samples),
        "firstCoordinate": first,
        "lastCoordinate": last,
        "recordedCoordinateDelta": _delta(first, last),
        "wrapperCoordinateDelta": _wrapper_delta(live_result),
        "sourceSummaryFiles": sorted(
            {
                str(path)
                for path in (
                    _get(dry_run, "SummaryFile"),
                    _get(live_result, "SummaryFile"),
                    _get(_get(live_result, "Preflight"), "SummaryFile"),
                    _get(_get(live_result, "PostReadback"), "SummaryFile"),
                )
                if path
            }
        ),
    }
    write_json(pulse_summary_file, summary)
    return summary


def _samples_for_pulse(
    *,
    profile_name: str,
    process_id: int,
    target_window_handle: str,
    pulse_index: int,
    stage: str,
    dry_run: dict[str, Any] | None,
    live_result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    sources = [
        ("dry-run-preflight", _get(dry_run, "Preflight"), _get(dry_run, "SummaryFile")),
        ("live-preflight", _get(live_result, "Preflight"), _get(live_result, "SummaryFile")),
        (
            "live-post-readback",
            _get(live_result, "PostReadback"),
            _get(live_result, "SummaryFile"),
        ),
    ]
    for phase, payload, wrapper_summary_file in sources:
        samples.extend(
            _samples_from_readback(
                phase=phase,
                payload=payload,
                profile_name=profile_name,
                process_id=process_id,
                target_window_handle=target_window_handle,
                pulse_index=pulse_index,
                stage=stage,
                wrapper_summary_file=wrapper_summary_file,
            )
        )
    return samples


def _samples_from_readback(
    *,
    phase: str,
    payload: Any,
    profile_name: str,
    process_id: int,
    target_window_handle: str,
    pulse_index: int,
    stage: str,
    wrapper_summary_file: Any,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    raw_samples = _get(_get(payload, "AnchorReadback"), "DecodedSamples")
    samples: list[dict[str, Any]] = []
    if isinstance(raw_samples, list):
        for index, raw in enumerate(raw_samples):
            coordinate = _coordinate(raw)
            if coordinate:
                samples.append(
                    _sample(
                        phase=phase,
                        profile_name=profile_name,
                        process_id=process_id,
                        target_window_handle=target_window_handle,
                        pulse_index=pulse_index,
                        stage=stage,
                        source_sample_index=_get(raw, "SampleIndex", index),
                        coordinate=coordinate,
                        readback_summary_file=_get(payload, "SummaryFile"),
                        wrapper_summary_file=wrapper_summary_file,
                    )
                )

    if samples:
        return samples

    coordinate = _coordinate(_get(payload, "CurrentCoordinate"))
    if not coordinate:
        return []
    return [
        _sample(
            phase=phase,
            profile_name=profile_name,
            process_id=process_id,
            target_window_handle=target_window_handle,
            pulse_index=pulse_index,
            stage=stage,
            source_sample_index=0,
            coordinate=coordinate,
            readback_summary_file=_get(payload, "SummaryFile"),
            wrapper_summary_file=wrapper_summary_file,
        )
    ]


def _sample(
    *,
    phase: str,
    profile_name: str,
    process_id: int,
    target_window_handle: str,
    pulse_index: int,
    stage: str,
    source_sample_index: Any,
    coordinate: dict[str, Any],
    readback_summary_file: Any,
    wrapper_summary_file: Any,
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "mode": "rift-live-test-coordinate-sample",
        "profileName": profile_name,
        "pulseIndex": pulse_index,
        "stage": stage,
        "phase": phase,
        "sourceSampleIndex": source_sample_index,
        "recordedAtUtc": coordinate.get("recordedAtUtc"),
        "coordinate": coordinate,
        "processId": process_id,
        "targetWindowHandle": target_window_handle,
        "readbackSummaryFile": str(readback_summary_file) if readback_summary_file else None,
        "wrapperSummaryFile": str(wrapper_summary_file) if wrapper_summary_file else None,
        "source": "proof-anchor-current-readback",
        "noCheatEngine": True,
        "savedVariablesUsedAsLiveTruth": False,
    }


def _coordinate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    x = _coerce_float(_get(value, "X"))
    y = _coerce_float(_get(value, "Y"))
    z = _coerce_float(_get(value, "Z"))
    if x is None or y is None or z is None:
        return None
    return {
        "x": x,
        "y": y,
        "z": z,
        "recordedAtUtc": _get(value, "RecordedAtUtc"),
    }


def _delta(first: dict[str, Any] | None, last: dict[str, Any] | None) -> dict[str, Any] | None:
    if not first or not last:
        return None
    try:
        delta_x = float(last["x"]) - float(first["x"])
        delta_y = float(last["y"]) - float(first["y"])
        delta_z = float(last["z"]) - float(first["z"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "deltaX": delta_x,
        "deltaY": delta_y,
        "deltaZ": delta_z,
        "planarDistance": math.sqrt((delta_x * delta_x) + (delta_z * delta_z)),
        "spatialDistance": math.sqrt(
            (delta_x * delta_x) + (delta_y * delta_y) + (delta_z * delta_z)
        ),
    }


def _wrapper_delta(live_result: dict[str, Any] | None) -> dict[str, Any] | None:
    value = _get(live_result, "CoordinateDelta")
    if not isinstance(value, dict):
        return None
    return {
        "deltaX": _get(value, "DeltaX"),
        "deltaY": _get(value, "DeltaY"),
        "deltaZ": _get(value, "DeltaZ"),
        "planarDistance": _get(value, "PlanarDistance"),
        "spatialDistance": _get(value, "SpatialDistance"),
    }


def _phase_counts(samples: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in samples:
        phase = str(sample.get("phase"))
        counts[phase] = counts.get(phase, 0) + 1
    return counts


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get(payload: Any, name: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(name, default)
    return default
