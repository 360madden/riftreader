#!/usr/bin/env python3
"""Read and compare promoted-owner memory snapshots for yaw/facing discovery.

This helper is intentionally read-only. It uses the promoted static coordinate
resolver only to reacquire the current owner object, then snapshots aligned
floats and unit-vector-like triples from that owner window. Live input, if any,
must be performed by an external exact-target controller between snapshot runs.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from static_owner_coordinate_chain_readback import (
    base_safety,
    build_poll_analysis,
    get_process_creation_time_utc,
    int_hex,
    load_current_truth_defaults,
    open_process_for_read,
    process_start_check,
    qword,
    read_memory,
    repo_root as default_repo_root,
    safe_mapping,
    triplet,
    utc_stamp,
)
from rift_live_test.current_pid_family_neighborhood_inspector import close_handle, verify_hwnd_owner

SCHEMA_VERSION = 1
DEFAULT_OWNER_WINDOW_BYTES = 0x700
DEFAULT_VECTOR_MIN_LENGTH = 0.75
DEFAULT_VECTOR_MAX_LENGTH = 1.25
DEFAULT_MIN_TARGET_DISTANCE = 0.5
DEFAULT_MAX_TARGET_DISTANCE = 100.0
DEFAULT_MIN_SCALAR_DELTA = 0.001
DEFAULT_MIN_YAW_DELTA_DEGREES = 1.0
COORD_OFFSETS = {0x320, 0x324, 0x328}


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def finite_float(value: float) -> bool:
    return math.isfinite(value) and abs(value) < 1_000_000


def unpack_float(data: bytes, offset: int) -> float | None:
    try:
        value = struct.unpack_from("<f", data, offset)[0]
    except struct.error:
        return None
    return float(value) if finite_float(float(value)) else None


def vector_from_data(data: bytes, offset: int) -> dict[str, float] | None:
    try:
        x, y, z = struct.unpack_from("<fff", data, offset)
    except struct.error:
        return None
    x = float(x)
    y = float(y)
    z = float(z)
    if not all(finite_float(value) for value in (x, y, z)):
        return None
    length = math.sqrt((x * x) + (y * y) + (z * z))
    if length <= 0:
        return None
    yaw = math.degrees(math.atan2(z, x))
    pitch = math.degrees(math.atan2(y, math.sqrt((x * x) + (z * z))))
    return {"x": x, "y": y, "z": z, "length": length, "yawDegrees": yaw, "pitchDegrees": pitch}


def normalize_degrees(delta: float) -> float:
    normalized = math.fmod(float(delta) + 180.0, 360.0)
    if normalized < 0:
        normalized += 360.0
    return normalized - 180.0


def extract_float_samples(data: bytes, *, owner_address: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(0, len(data) - 3, 4):
        value = unpack_float(data, offset)
        if value is None:
            continue
        rows.append({"offset": int_hex(offset), "address": int_hex(owner_address + offset), "value": value})
    return rows


def extract_vector_samples(
    data: bytes,
    *,
    owner_address: int,
    min_length: float,
    max_length: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(0, len(data) - 11, 4):
        vector = vector_from_data(data, offset)
        if vector is None:
            continue
        if min_length <= vector["length"] <= max_length:
            rows.append({"offset": int_hex(offset), "address": int_hex(owner_address + offset), **vector})
    return rows


def extract_relative_target_samples(
    data: bytes,
    *,
    owner_address: int,
    coordinate: Mapping[str, Any],
    min_distance: float,
    max_distance: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cx = float(coordinate["x"])
    cy = float(coordinate["y"])
    cz = float(coordinate["z"])
    for offset in range(0, len(data) - 11, 4):
        target = vector_from_data(data, offset)
        if target is None:
            continue
        dx = target["x"] - cx
        dy = target["y"] - cy
        dz = target["z"] - cz
        planar = math.hypot(dx, dz)
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if not (min_distance <= planar <= max_distance):
            continue
        yaw = math.degrees(math.atan2(dz, dx))
        pitch = math.degrees(math.atan2(dy, planar)) if planar else 0.0
        rows.append(
            {
                "offset": int_hex(offset),
                "address": int_hex(owner_address + offset),
                "targetCoordinate": {"x": target["x"], "y": target["y"], "z": target["z"]},
                "direction": {"x": dx, "y": dy, "z": dz},
                "planarDistance": planar,
                "distance3d": distance,
                "yawDegrees": yaw,
                "pitchDegrees": pitch,
            }
        )
    return rows


def nav_state_from_owner_window(data: bytes, *, owner_address: int) -> dict[str, Any]:
    position = triplet(data, 0x320)
    facing_target = triplet(data, 0x30C)
    dx = facing_target["x"] - position["x"]
    dy = facing_target["y"] - position["y"]
    dz = facing_target["z"] - position["z"]
    planar = math.hypot(dx, dz)
    distance = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
    yaw = math.degrees(math.atan2(dz, dx))
    pitch = math.degrees(math.atan2(dy, planar)) if planar else 0.0
    return {
        "ownerAddress": int_hex(owner_address),
        "coordinate": position,
        "facingTargetCoordinate": facing_target,
        "facingVector": {"x": dx, "y": dy, "z": dz},
        "yawDegrees": yaw,
        "pitchDegrees": pitch,
        "planarLookaheadDistance": planar,
        "lookaheadDistance3d": distance,
        "positionOffset": "0x320",
        "facingTargetOffset": "0x30C",
    }


def build_yaw_transition_analysis(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    passed_samples = [sample for sample in samples if sample.get("status") == "passed" and sample.get("yawDegrees") is not None]
    transitions: list[dict[str, Any]] = []
    max_abs_yaw_delta = 0.0
    max_abs_yaw_speed: float | None = None
    for index in range(1, len(passed_samples)):
        previous = passed_samples[index - 1]
        current = passed_samples[index]
        elapsed_delta = None
        if previous.get("elapsedSeconds") is not None and current.get("elapsedSeconds") is not None:
            elapsed_delta = float(current["elapsedSeconds"]) - float(previous["elapsedSeconds"])
        signed_delta = normalize_degrees(float(current["yawDegrees"]) - float(previous["yawDegrees"]))
        absolute_delta = abs(signed_delta)
        yaw_speed = absolute_delta / elapsed_delta if elapsed_delta and elapsed_delta > 0 else None
        max_abs_yaw_delta = max(max_abs_yaw_delta, absolute_delta)
        if yaw_speed is not None:
            max_abs_yaw_speed = yaw_speed if max_abs_yaw_speed is None else max(max_abs_yaw_speed, yaw_speed)
        transitions.append(
            {
                "fromSample": previous.get("sampleIndex"),
                "toSample": current.get("sampleIndex"),
                "elapsedSeconds": elapsed_delta,
                "signedYawDeltaDegrees": signed_delta,
                "absoluteYawDeltaDegrees": absolute_delta,
                "yawSpeedDegreesPerSecond": yaw_speed,
            }
        )
    return {
        "yawTransitions": transitions,
        "maxAbsYawDeltaDegrees": max_abs_yaw_delta,
        "maxAbsYawSpeedDegreesPerSecond": max_abs_yaw_speed,
    }


def navigation_target_from_state(
    state: Mapping[str, Any],
    *,
    destination_x: float,
    destination_y: float | None,
    destination_z: float,
    destination_label: str | None,
    arrival_radius: float,
    alignment_threshold_degrees: float,
) -> dict[str, Any]:
    coordinate = safe_mapping(state.get("coordinate"))
    current_x = float(coordinate["x"])
    current_y = float(coordinate["y"])
    current_z = float(coordinate["z"])
    dest_y = current_y if destination_y is None else float(destination_y)
    delta_x = float(destination_x) - current_x
    delta_y = dest_y - current_y
    delta_z = float(destination_z) - current_z
    planar_distance = math.hypot(delta_x, delta_z)
    distance_3d = math.sqrt((delta_x * delta_x) + (delta_y * delta_y) + (delta_z * delta_z))
    destination_bearing = normalize_degrees(math.degrees(math.atan2(delta_z, delta_x)))
    current_yaw = float(state["yawDegrees"])
    signed_delta = normalize_degrees(destination_bearing - current_yaw)
    absolute_delta = abs(signed_delta)
    within_arrival = planar_distance <= arrival_radius
    within_alignment = absolute_delta <= alignment_threshold_degrees
    if within_alignment:
        turn_direction = "aligned"
    elif signed_delta > 0:
        turn_direction = "right"
    else:
        turn_direction = "left"
    return {
        "status": "arrived" if within_arrival else "aligned-candidate" if within_alignment else "turn-candidate",
        "sourceKind": "static-owner-relative-target-candidate-facing",
        "candidateOnly": True,
        "actionableForMovement": False,
        "reason": "static-owner-facing-target-is-candidate-only-not-promoted",
        "destination": {
            "label": destination_label,
            "x": float(destination_x),
            "y": dest_y,
            "z": float(destination_z),
        },
        "delta": {"x": delta_x, "y": delta_y, "z": delta_z},
        "planarDistance": planar_distance,
        "distance3d": distance_3d,
        "heightDelta": delta_y,
        "arrivalRadius": float(arrival_radius),
        "withinArrivalRadius": within_arrival,
        "destinationBearingDegrees": destination_bearing,
        "currentYawDegrees": current_yaw,
        "signedBearingDeltaDegrees": signed_delta,
        "absoluteBearingDeltaDegrees": absolute_delta,
        "alignmentThresholdDegrees": float(alignment_threshold_degrees),
        "withinAlignmentThreshold": within_alignment,
        "suggestedTurnDirection": turn_direction,
    }


def apply_current_truth(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    defaults = load_current_truth_defaults(root, args.current_truth_json)
    if args.pid is None and defaults.get("pid") is not None:
        args.pid = int(defaults["pid"])
    if not args.hwnd and defaults.get("hwnd"):
        args.hwnd = str(defaults["hwnd"])
    if not args.module_base and defaults.get("moduleBase"):
        args.module_base = str(defaults["moduleBase"])
    if not args.expected_process_start_utc and defaults.get("processStartUtc"):
        args.expected_process_start_utc = str(defaults["processStartUtc"])
    if not args.root_rva and defaults.get("rootRva"):
        args.root_rva = str(defaults["rootRva"])
    return defaults


def validate_snapshot_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if args.pid is None:
        errors.append("pid-required")
    if not args.hwnd:
        errors.append("hwnd-required")
    if not args.module_base:
        errors.append("module-base-required")
    if args.owner_window_bytes < 0x330:
        errors.append("owner-window-bytes-too-small")
    return errors


def validate_state_args(args: argparse.Namespace) -> list[str]:
    errors = validate_snapshot_args(args)
    if args.samples < 1:
        errors.append("samples-must-be-positive")
    if args.interval_seconds < 0:
        errors.append("interval-seconds-must-be-nonnegative")
    if args.max_planar_jump_per_sample < 0:
        errors.append("max-planar-jump-per-sample-must-be-nonnegative")
    if args.max_sample_gap_seconds <= 0:
        errors.append("max-sample-gap-seconds-must-be-positive")
    if args.max_stationary_planar_drift < 0:
        errors.append("max-stationary-planar-drift-must-be-nonnegative")
    if args.min_target_distance < 0:
        errors.append("min-target-distance-must-be-nonnegative")
    if args.max_target_distance < args.min_target_distance:
        errors.append("max-target-distance-must-be-greater-than-or-equal-to-min-target-distance")
    destination_requested = args.destination_x is not None or args.destination_y is not None or args.destination_z is not None
    if destination_requested and (args.destination_x is None or args.destination_z is None):
        errors.append("destination-x-and-z-required-together")
    if args.arrival_radius < 0:
        errors.append("arrival-radius-must-be-nonnegative")
    if args.alignment_threshold_degrees < 0:
        errors.append("alignment-threshold-degrees-must-be-nonnegative")
    return errors


def run_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    defaults = apply_current_truth(args, root)
    errors = validate_snapshot_args(args)
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-facing-snapshot-{args.label}-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-facing-snapshot",
        "generatedAtUtc": utc_iso(),
        "label": args.label,
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "target": {
            "processName": args.process_name,
            "processId": args.pid,
            "targetWindowHandle": args.hwnd,
            "expectedProcessStartUtc": args.expected_process_start_utc,
            "moduleBase": args.module_base,
            "currentTruthPath": defaults.get("path"),
        },
        "resolver": {
            "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
            "rootRva": args.root_rva or defaults.get("rootRva"),
            "coordOffset": "0x320",
            "currentTruthStaticResolverStatus": defaults.get("staticResolverStatus"),
            "currentTruthPromotionAllowed": defaults.get("promotionAllowed"),
        },
        "owner": {},
        "coordinate": {},
        "floatSamples": [],
        "vectorSamples": [],
        "relativeTargetSamples": [],
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": base_safety(),
        "artifacts": {"runDirectory": str(run_dir), "summaryJson": str(run_dir / "summary.json"), "summaryMarkdown": str(run_dir / "summary.md")},
    }
    summary["safety"]["facingPromotion"] = False
    if errors:
        return summary

    module_base = int(str(args.module_base), 0)
    root_rva = int(str(args.root_rva or defaults.get("rootRva") or "0x32EBC80"), 0)
    root_address = module_base + root_rva
    hwnd_check = verify_hwnd_owner(str(args.hwnd), int(args.pid))
    summary["target"]["hwndCheck"] = hwnd_check
    if not hwnd_check.get("ownerMatchesExpectedPid"):
        summary["status"] = "blocked"
        summary["verdict"] = "target-hwnd-pid-mismatch"
        summary["blockers"].append("target-hwnd-pid-mismatch")
        return summary

    handle = open_process_for_read(int(args.pid))
    try:
        actual_start = get_process_creation_time_utc(handle)
        start_check = process_start_check(actual_start, args.expected_process_start_utc, tolerance_seconds=args.process_start_tolerance_seconds)
        summary["target"]["actualProcessStartUtc"] = actual_start
        summary["target"]["processStartCheck"] = start_check
        if start_check.get("matchesExpected") is False:
            summary["status"] = "blocked"
            summary["verdict"] = "target-process-start-mismatch"
            summary["blockers"].append("target-process-start-mismatch")
            return summary
        owner_address = qword(read_memory(handle, root_address, 8))
        data = read_memory(handle, owner_address, int(args.owner_window_bytes))
        coordinate = triplet(data, 0x320)
        owner_vtable = qword(data, 0)
        summary["owner"] = {
            "rootAddress": int_hex(root_address),
            "ownerAddress": int_hex(owner_address),
            "ownerVtable": int_hex(owner_vtable),
            "ownerVtableRva": int_hex(owner_vtable - module_base) if module_base <= owner_vtable < module_base + 0x4000000 else None,
            "windowBytes": int(args.owner_window_bytes),
        }
        summary["coordinate"] = coordinate
        summary["floatSamples"] = extract_float_samples(data, owner_address=owner_address)
        summary["vectorSamples"] = extract_vector_samples(
            data,
            owner_address=owner_address,
            min_length=float(args.vector_min_length),
            max_length=float(args.vector_max_length),
        )
        summary["relativeTargetSamples"] = extract_relative_target_samples(
            data,
            owner_address=owner_address,
            coordinate=coordinate,
            min_distance=float(args.min_target_distance),
            max_distance=float(args.max_target_distance),
        )
        summary["status"] = "passed"
        summary["verdict"] = "static-owner-facing-snapshot-captured"
        summary["warnings"].append("snapshot-only-not-yaw-promotion")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "snapshot-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    finally:
        close_handle(handle)
    return summary


def run_state(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    defaults = apply_current_truth(args, root)
    errors = validate_state_args(args)
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-nav-state-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-nav-state-readback",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "target": {
            "processName": args.process_name,
            "processId": args.pid,
            "targetWindowHandle": args.hwnd,
            "expectedProcessStartUtc": args.expected_process_start_utc,
            "moduleBase": args.module_base,
            "currentTruthPath": defaults.get("path"),
        },
        "resolver": {
            "positionChain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
            "facingTargetChain": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
            "yawFormula": "atan2((owner+0x314)-(owner+0x328), (owner+0x30C)-(owner+0x320))",
            "currentTruthStaticResolverStatus": defaults.get("staticResolverStatus"),
            "currentTruthPromotionAllowed": defaults.get("promotionAllowed"),
        },
        "polling": {
            "requestedSampleCount": int(args.samples),
            "intervalSeconds": float(args.interval_seconds),
            "exactHwndPidCheckPerSample": True,
            "maxPlanarJumpPerSample": float(args.max_planar_jump_per_sample),
            "maxSampleGapSeconds": float(args.max_sample_gap_seconds),
            "minLookaheadDistance": float(args.min_target_distance),
            "maxLookaheadDistance": float(args.max_target_distance),
        },
        "samples": [],
        "latestState": {},
        "navigationTarget": {},
        "analysis": {},
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": base_safety() | {"facingPromotion": False, "navigationControl": False},
        "artifacts": {"runDirectory": str(run_dir), "summaryJson": str(run_dir / "summary.json"), "summaryMarkdown": str(run_dir / "summary.md")},
    }
    if errors:
        return summary

    module_base = int(str(args.module_base), 0)
    root_rva = int(str(args.root_rva or defaults.get("rootRva") or "0x32EBC80"), 0)
    root_address = module_base + root_rva
    hwnd_check = verify_hwnd_owner(str(args.hwnd), int(args.pid))
    summary["target"]["hwndCheck"] = hwnd_check
    if not hwnd_check.get("ownerMatchesExpectedPid"):
        summary["status"] = "blocked"
        summary["verdict"] = "target-hwnd-pid-mismatch"
        summary["blockers"].append("target-hwnd-pid-mismatch")
        return summary

    handle = open_process_for_read(int(args.pid))
    start = time.perf_counter()
    try:
        actual_start = get_process_creation_time_utc(handle)
        start_check = process_start_check(actual_start, args.expected_process_start_utc, tolerance_seconds=args.process_start_tolerance_seconds)
        summary["target"]["actualProcessStartUtc"] = actual_start
        summary["target"]["processStartCheck"] = start_check
        if start_check.get("matchesExpected") is False:
            summary["status"] = "blocked"
            summary["verdict"] = "target-process-start-mismatch"
            summary["blockers"].append("target-process-start-mismatch")
            return summary
        for index in range(int(args.samples)):
            sample_check = verify_hwnd_owner(str(args.hwnd), int(args.pid))
            sample: dict[str, Any] = {
                "sampleIndex": index,
                "sampledAtUtc": utc_iso(),
                "elapsedSeconds": time.perf_counter() - start,
                "hwndCheck": sample_check,
            }
            if not sample_check.get("ownerMatchesExpectedPid"):
                sample["status"] = "blocked"
                sample["blocker"] = "target-hwnd-pid-mismatch-during-poll"
                summary["samples"].append(sample)
                summary["blockers"].append("target-hwnd-pid-mismatch-during-poll")
                break
            owner_address = qword(read_memory(handle, root_address, 8))
            data = read_memory(handle, owner_address, int(args.owner_window_bytes))
            state = nav_state_from_owner_window(data, owner_address=owner_address)
            sample.update({"status": "passed", **state})
            if not (float(args.min_target_distance) <= float(state["planarLookaheadDistance"]) <= float(args.max_target_distance)):
                sample["lookaheadDistanceOutOfRange"] = True
                summary["blockers"].append("facing-lookahead-distance-out-of-range")
            summary["latestState"] = state
            summary["samples"].append(sample)
            if index < int(args.samples) - 1 and args.interval_seconds > 0:
                time.sleep(float(args.interval_seconds))
        summary["analysis"] = build_poll_analysis(
            summary["samples"],
            max_planar_jump_per_sample=float(args.max_planar_jump_per_sample),
            max_sample_gap_seconds=float(args.max_sample_gap_seconds),
            expect_stationary=bool(args.expect_stationary),
            max_stationary_planar_drift=float(args.max_stationary_planar_drift),
        )
        yaw_values = [float(sample["yawDegrees"]) for sample in summary["samples"] if sample.get("status") == "passed" and sample.get("yawDegrees") is not None]
        if yaw_values:
            summary["analysis"]["yawMinDegrees"] = min(yaw_values)
            summary["analysis"]["yawMaxDegrees"] = max(yaw_values)
            summary["analysis"]["yawRangeDegrees"] = max(yaw_values) - min(yaw_values)
        summary["analysis"].update(build_yaw_transition_analysis(summary["samples"]))
        if args.destination_x is not None and args.destination_z is not None and summary.get("latestState"):
            summary["navigationTarget"] = navigation_target_from_state(
                summary["latestState"],
                destination_x=float(args.destination_x),
                destination_y=None if args.destination_y is None else float(args.destination_y),
                destination_z=float(args.destination_z),
                destination_label=args.destination_label,
                arrival_radius=float(args.arrival_radius),
                alignment_threshold_degrees=float(args.alignment_threshold_degrees),
            )
        summary["blockers"].extend(summary["analysis"].get("blockers", []))
        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "nav-state-readback-blocked"
        else:
            summary["status"] = "passed"
            summary["verdict"] = "position-and-facing-nav-state-readback-passed"
            summary["classification"] = "candidate-facing-state-source-not-promoted"
            summary["warnings"].append("facing-candidate-readback-only-not-promoted")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "nav-state-readback-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    finally:
        close_handle(handle)
    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    return summary


def rows_by_offset(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("offset")): row for row in rows if row.get("offset")}


def coordinate_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, float]:
    dx = float(right.get("x", 0.0)) - float(left.get("x", 0.0))
    dy = float(right.get("y", 0.0)) - float(left.get("y", 0.0))
    dz = float(right.get("z", 0.0)) - float(left.get("z", 0.0))
    return {"x": dx, "y": dy, "z": dz, "planarXz": math.hypot(dx, dz), "distance3d": math.sqrt(dx * dx + dy * dy + dz * dz)}


def compare_snapshots(
    snapshots: Sequence[Mapping[str, Any]],
    *,
    min_scalar_delta: float,
    min_yaw_delta_degrees: float,
    max_coordinate_planar_drift: float,
) -> dict[str, Any]:
    labels = [str(snapshot.get("label") or f"snapshot-{index}") for index, snapshot in enumerate(snapshots)]
    blockers: list[str] = []
    warnings: list[str] = []
    if len(snapshots) < 2:
        blockers.append("at-least-two-snapshots-required")
        return {
            "status": "blocked",
            "labels": labels,
            "blockers": blockers,
            "warnings": warnings,
            "scalarCandidates": [],
            "vectorCandidates": [],
            "relativeTargetCandidates": [],
        }
    if any(snapshot.get("status") != "passed" for snapshot in snapshots):
        blockers.append("all-snapshots-must-pass")
    owner_addresses = {safe_mapping(snapshot.get("owner")).get("ownerAddress") for snapshot in snapshots}
    if len(owner_addresses) > 1:
        blockers.append("owner-address-changed-between-snapshots")

    baseline = snapshots[0]
    coord_deltas = [coordinate_delta(safe_mapping(baseline.get("coordinate")), safe_mapping(snapshot.get("coordinate"))) for snapshot in snapshots[1:]]
    max_coord_planar = max((delta["planarXz"] for delta in coord_deltas), default=0.0)
    if max_coord_planar > max_coordinate_planar_drift:
        warnings.append(f"coordinate-drift-during-facing-capture:{max_coord_planar:.6f}>{max_coordinate_planar_drift:.6f}")

    float_maps = [rows_by_offset(snapshot.get("floatSamples", [])) for snapshot in snapshots]
    common_float_offsets = set(float_maps[0])
    for mapping in float_maps[1:]:
        common_float_offsets &= set(mapping)
    scalar_candidates: list[dict[str, Any]] = []
    for offset in sorted(common_float_offsets, key=lambda item: int(item, 0)):
        parsed_offset = int(offset, 0)
        if parsed_offset in COORD_OFFSETS:
            continue
        values = [float(mapping[offset].get("value")) for mapping in float_maps]
        deltas = [values[index] - values[0] for index in range(1, len(values))]
        max_abs_delta = max((abs(delta) for delta in deltas), default=0.0)
        if max_abs_delta < min_scalar_delta:
            continue
        scalar_candidates.append(
            {
                "offset": offset,
                "address": float_maps[0][offset].get("address"),
                "valuesByLabel": dict(zip(labels, values, strict=False)),
                "deltasFromBaseline": dict(zip(labels[1:], deltas, strict=False)),
                "maxAbsDelta": max_abs_delta,
                "score": max_abs_delta,
            }
        )
    scalar_candidates.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)

    vector_maps = [rows_by_offset(snapshot.get("vectorSamples", [])) for snapshot in snapshots]
    common_vector_offsets = set(vector_maps[0])
    for mapping in vector_maps[1:]:
        common_vector_offsets &= set(mapping)
    vector_candidates: list[dict[str, Any]] = []
    for offset in sorted(common_vector_offsets, key=lambda item: int(item, 0)):
        yaws = [float(mapping[offset].get("yawDegrees")) for mapping in vector_maps]
        yaw_deltas = [normalize_degrees(yaws[index] - yaws[0]) for index in range(1, len(yaws))]
        max_abs_yaw_delta = max((abs(delta) for delta in yaw_deltas), default=0.0)
        if max_abs_yaw_delta < min_yaw_delta_degrees:
            continue
        lengths = [float(mapping[offset].get("length")) for mapping in vector_maps]
        vector_candidates.append(
            {
                "offset": offset,
                "address": vector_maps[0][offset].get("address"),
                "yawDegreesByLabel": dict(zip(labels, yaws, strict=False)),
                "yawDeltasFromBaseline": dict(zip(labels[1:], yaw_deltas, strict=False)),
                "lengthsByLabel": dict(zip(labels, lengths, strict=False)),
                "maxAbsYawDeltaDegrees": max_abs_yaw_delta,
                "score": max_abs_yaw_delta,
            }
        )
    vector_candidates.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)

    target_maps = [rows_by_offset(snapshot.get("relativeTargetSamples", [])) for snapshot in snapshots]
    common_target_offsets = set(target_maps[0])
    for mapping in target_maps[1:]:
        common_target_offsets &= set(mapping)
    relative_target_candidates: list[dict[str, Any]] = []
    for offset in sorted(common_target_offsets, key=lambda item: int(item, 0)):
        yaws = [float(mapping[offset].get("yawDegrees")) for mapping in target_maps]
        yaw_deltas = [normalize_degrees(yaws[index] - yaws[0]) for index in range(1, len(yaws))]
        max_abs_yaw_delta = max((abs(delta) for delta in yaw_deltas), default=0.0)
        if max_abs_yaw_delta < min_yaw_delta_degrees:
            continue
        distances = [float(mapping[offset].get("planarDistance")) for mapping in target_maps]
        relative_target_candidates.append(
            {
                "offset": offset,
                "address": target_maps[0][offset].get("address"),
                "targetCoordinatesByLabel": {
                    label: target_maps[index][offset].get("targetCoordinate") for index, label in enumerate(labels)
                },
                "directionByLabel": {label: target_maps[index][offset].get("direction") for index, label in enumerate(labels)},
                "yawDegreesByLabel": dict(zip(labels, yaws, strict=False)),
                "yawDeltasFromBaseline": dict(zip(labels[1:], yaw_deltas, strict=False)),
                "planarDistancesByLabel": dict(zip(labels, distances, strict=False)),
                "maxAbsYawDeltaDegrees": max_abs_yaw_delta,
                "score": max_abs_yaw_delta,
            }
        )
    relative_target_candidates.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)

    status = "blocked" if blockers else "passed" if relative_target_candidates or vector_candidates or scalar_candidates else "no-candidates"
    return {
        "status": status,
        "labels": labels,
        "ownerAddresses": sorted(str(item) for item in owner_addresses),
        "coordinateDeltasFromBaseline": coord_deltas,
        "maxCoordinatePlanarDrift": max_coord_planar,
        "scalarCandidateCount": len(scalar_candidates),
        "vectorCandidateCount": len(vector_candidates),
        "relativeTargetCandidateCount": len(relative_target_candidates),
        "scalarCandidates": scalar_candidates[:50],
        "vectorCandidates": vector_candidates[:50],
        "relativeTargetCandidates": relative_target_candidates[:50],
        "blockers": blockers,
        "warnings": warnings,
    }


def run_compare(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-facing-comparison-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshots = [load_json_object(Path(path)) for path in args.snapshot_json]
    comparison = compare_snapshots(
        snapshots,
        min_scalar_delta=float(args.min_scalar_delta),
        min_yaw_delta_degrees=float(args.min_yaw_delta_degrees),
        max_coordinate_planar_drift=float(args.max_coordinate_planar_drift),
    )
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-facing-comparison",
        "generatedAtUtc": utc_iso(),
        "status": comparison.get("status"),
        "verdict": "static-owner-facing-candidates-scored",
        "snapshotJson": [str(Path(path).resolve()) for path in args.snapshot_json],
        "comparison": comparison,
        "safety": base_safety() | {"facingPromotion": False, "movementSent": False, "inputSent": False},
        "artifacts": {"runDirectory": str(run_dir), "summaryJson": str(run_dir / "summary.json"), "summaryMarkdown": str(run_dir / "summary.md")},
    }
    return summary


def markdown(summary: Mapping[str, Any]) -> str:
    if summary.get("kind") == "static-owner-nav-state-readback":
        latest = safe_mapping(summary.get("latestState"))
        analysis = safe_mapping(summary.get("analysis"))
        navigation_target = safe_mapping(summary.get("navigationTarget"))
        lines = [
            "# Static owner navigation state readback",
            "",
            f"Status: `{summary.get('status')}`",
            f"Verdict: `{summary.get('verdict')}`",
            f"Coordinate: `{latest.get('coordinate')}`",
            f"Facing target: `{latest.get('facingTargetCoordinate')}`",
            f"Yaw degrees: `{latest.get('yawDegrees')}`",
            f"Pitch degrees: `{latest.get('pitchDegrees')}`",
            f"Lookahead distance: `{latest.get('planarLookaheadDistance')}`",
            f"Samples: `{analysis.get('sampleCount')}`",
            f"Max coordinate delta: `{analysis.get('maxPlanarDelta')}`",
            f"Yaw range: `{analysis.get('yawRangeDegrees')}`",
            f"Max signed yaw delta: `{analysis.get('maxAbsYawDeltaDegrees')}`",
            f"Max yaw speed/s: `{analysis.get('maxAbsYawSpeedDegreesPerSecond')}`",
            "",
            "Candidate readback only; no facing promotion and no navigation control.",
        ]
        if navigation_target:
            lines.extend(
                [
                    "",
                    "## Navigation target analysis",
                    "",
                    f"Destination: `{navigation_target.get('destination')}`",
                    f"Planar distance: `{navigation_target.get('planarDistance')}`",
                    f"Destination bearing: `{navigation_target.get('destinationBearingDegrees')}`",
                    f"Signed bearing delta: `{navigation_target.get('signedBearingDeltaDegrees')}`",
                    f"Suggested turn: `{navigation_target.get('suggestedTurnDirection')}`",
                    f"Candidate only: `{navigation_target.get('candidateOnly')}`",
                ]
            )
        if summary.get("blockers"):
            lines.extend(["", "## Blockers", ""])
            lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
        if summary.get("warnings"):
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
        return "\n".join(lines) + "\n"
    if summary.get("kind") == "static-owner-facing-snapshot":
        owner = safe_mapping(summary.get("owner"))
        return "\n".join(
            [
                "# Static owner facing snapshot",
                "",
                f"Status: `{summary.get('status')}`",
                f"Label: `{summary.get('label')}`",
                f"Owner: `{owner.get('ownerAddress')}`",
                f"Coordinate: `{summary.get('coordinate')}`",
                f"Float samples: `{len(summary.get('floatSamples', []))}`",
        f"Vector-like samples: `{len(summary.get('vectorSamples', []))}`",
        f"Relative target samples: `{len(summary.get('relativeTargetSamples', []))}`",
                "",
                "Snapshot only; no facing promotion.",
            ]
        ) + "\n"
    comparison = safe_mapping(summary.get("comparison"))
    vectors = comparison.get("vectorCandidates", []) if isinstance(comparison.get("vectorCandidates"), list) else []
    relative_targets = comparison.get("relativeTargetCandidates", []) if isinstance(comparison.get("relativeTargetCandidates"), list) else []
    scalars = comparison.get("scalarCandidates", []) if isinstance(comparison.get("scalarCandidates"), list) else []
    lines = [
        "# Static owner facing comparison",
        "",
        f"Status: `{summary.get('status')}`",
        f"Relative target candidates: `{comparison.get('relativeTargetCandidateCount')}`",
        f"Vector candidates: `{comparison.get('vectorCandidateCount')}`",
        f"Scalar candidates: `{comparison.get('scalarCandidateCount')}`",
        f"Max coordinate planar drift: `{comparison.get('maxCoordinatePlanarDrift')}`",
        "",
        "## Top relative target candidates",
        "",
        "| Offset | Address | Max yaw delta | Yaws | Planar distances |",
        "|---|---|---:|---|---|",
    ]
    for row in relative_targets[:10]:
        lines.append(
            f"| `{row.get('offset')}` | `{row.get('address')}` | `{row.get('maxAbsYawDeltaDegrees')}` | "
            f"`{row.get('yawDegreesByLabel')}` | `{row.get('planarDistancesByLabel')}` |"
        )
    lines.extend(
        [
            "",
        "## Top vector candidates",
        "",
        "| Offset | Address | Max yaw delta | Yaws |",
        "|---|---|---:|---|",
        ]
    )
    for row in vectors[:10]:
        lines.append(f"| `{row.get('offset')}` | `{row.get('address')}` | `{row.get('maxAbsYawDeltaDegrees')}` | `{row.get('yawDegreesByLabel')}` |")
    lines.extend(["", "## Top scalar candidates", "", "| Offset | Address | Max delta | Values |", "|---|---|---:|---|"])
    for row in scalars[:10]:
        lines.append(f"| `{row.get('offset')}` | `{row.get('address')}` | `{row.get('maxAbsDelta')}` | `{row.get('valuesByLabel')}` |")
    if comparison.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in comparison.get("blockers", []))
    if comparison.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in comparison.get("warnings", []))
    lines.extend(["", "Candidate discovery only; no yaw/facing promotion."])
    return "\n".join(lines) + "\n"


def write_outputs(summary: dict[str, Any]) -> None:
    artifacts = safe_mapping(summary.get("artifacts"))
    Path(str(artifacts["summaryJson"])).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    Path(str(artifacts["summaryMarkdown"])).write_text(markdown(summary), encoding="utf-8")


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    if summary.get("kind") == "static-owner-nav-state-readback":
        latest = safe_mapping(summary.get("latestState"))
        analysis = safe_mapping(summary.get("analysis"))
        return {
            "status": summary.get("status"),
            "verdict": summary.get("verdict"),
            "classification": summary.get("classification"),
            "coordinate": latest.get("coordinate"),
            "yawDegrees": latest.get("yawDegrees"),
            "pitchDegrees": latest.get("pitchDegrees"),
            "planarLookaheadDistance": latest.get("planarLookaheadDistance"),
            "sampleCount": analysis.get("sampleCount"),
            "maxPlanarDelta": analysis.get("maxPlanarDelta"),
            "yawRangeDegrees": analysis.get("yawRangeDegrees"),
            "maxAbsYawDeltaDegrees": analysis.get("maxAbsYawDeltaDegrees"),
            "maxAbsYawSpeedDegreesPerSecond": analysis.get("maxAbsYawSpeedDegreesPerSecond"),
            "navigationTarget": summary.get("navigationTarget") or None,
            "summaryJson": artifacts.get("summaryJson"),
            "summaryMarkdown": artifacts.get("summaryMarkdown"),
            "blockers": summary.get("blockers", []),
            "warnings": summary.get("warnings", []),
            "errors": summary.get("errors", []),
        }
    if summary.get("kind") == "static-owner-facing-snapshot":
        return {
            "status": summary.get("status"),
            "label": summary.get("label"),
            "ownerAddress": safe_mapping(summary.get("owner")).get("ownerAddress"),
            "coordinate": summary.get("coordinate"),
            "floatSampleCount": len(summary.get("floatSamples", [])),
            "vectorSampleCount": len(summary.get("vectorSamples", [])),
            "relativeTargetSampleCount": len(summary.get("relativeTargetSamples", [])),
            "summaryJson": artifacts.get("summaryJson"),
            "blockers": summary.get("blockers", []),
            "warnings": summary.get("warnings", []),
            "errors": summary.get("errors", []),
        }
    comparison = safe_mapping(summary.get("comparison"))
    vectors = comparison.get("vectorCandidates", []) if isinstance(comparison.get("vectorCandidates"), list) else []
    relative_targets = comparison.get("relativeTargetCandidates", []) if isinstance(comparison.get("relativeTargetCandidates"), list) else []
    scalars = comparison.get("scalarCandidates", []) if isinstance(comparison.get("scalarCandidates"), list) else []
    return {
        "status": summary.get("status"),
        "relativeTargetCandidateCount": comparison.get("relativeTargetCandidateCount"),
        "vectorCandidateCount": comparison.get("vectorCandidateCount"),
        "scalarCandidateCount": comparison.get("scalarCandidateCount"),
        "topRelativeTargetCandidate": relative_targets[0] if relative_targets else None,
        "topVectorCandidate": vectors[0] if vectors else None,
        "topScalarCandidate": scalars[0] if scalars else None,
        "maxCoordinatePlanarDrift": comparison.get("maxCoordinatePlanarDrift"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": comparison.get("blockers", []),
        "warnings": comparison.get("warnings", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promoted owner facing/yaw snapshot and comparison helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snap = subparsers.add_parser("snapshot")
    snap.add_argument("--repo-root")
    snap.add_argument("--output-root")
    snap.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    snap.add_argument("--label", default="snapshot")
    snap.add_argument("--process-name", default="rift_x64")
    snap.add_argument("--pid", type=int)
    snap.add_argument("--hwnd")
    snap.add_argument("--module-base")
    snap.add_argument("--expected-process-start-utc")
    snap.add_argument("--process-start-tolerance-seconds", type=float, default=2.0)
    snap.add_argument("--root-rva")
    snap.add_argument("--owner-window-bytes", type=lambda value: int(value, 0), default=DEFAULT_OWNER_WINDOW_BYTES)
    snap.add_argument("--vector-min-length", type=float, default=DEFAULT_VECTOR_MIN_LENGTH)
    snap.add_argument("--vector-max-length", type=float, default=DEFAULT_VECTOR_MAX_LENGTH)
    snap.add_argument("--min-target-distance", type=float, default=DEFAULT_MIN_TARGET_DISTANCE)
    snap.add_argument("--max-target-distance", type=float, default=DEFAULT_MAX_TARGET_DISTANCE)
    snap.add_argument("--json", action="store_true")

    comp = subparsers.add_parser("compare")
    comp.add_argument("--repo-root")
    comp.add_argument("--output-root")
    comp.add_argument("--snapshot-json", nargs="+", required=True)
    comp.add_argument("--min-scalar-delta", type=float, default=DEFAULT_MIN_SCALAR_DELTA)
    comp.add_argument("--min-yaw-delta-degrees", type=float, default=DEFAULT_MIN_YAW_DELTA_DEGREES)
    comp.add_argument("--max-coordinate-planar-drift", type=float, default=0.5)
    comp.add_argument("--json", action="store_true")

    state = subparsers.add_parser("state")
    state.add_argument("--repo-root")
    state.add_argument("--output-root")
    state.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    state.add_argument("--process-name", default="rift_x64")
    state.add_argument("--pid", type=int)
    state.add_argument("--hwnd")
    state.add_argument("--module-base")
    state.add_argument("--expected-process-start-utc")
    state.add_argument("--process-start-tolerance-seconds", type=float, default=2.0)
    state.add_argument("--root-rva")
    state.add_argument("--owner-window-bytes", type=lambda value: int(value, 0), default=DEFAULT_OWNER_WINDOW_BYTES)
    state.add_argument("--samples", type=int, default=5)
    state.add_argument("--interval-seconds", type=float, default=0.1)
    state.add_argument("--max-planar-jump-per-sample", type=float, default=25.0)
    state.add_argument("--max-sample-gap-seconds", type=float, default=2.0)
    state.add_argument("--expect-stationary", action="store_true")
    state.add_argument("--max-stationary-planar-drift", type=float, default=0.5)
    state.add_argument("--min-target-distance", type=float, default=DEFAULT_MIN_TARGET_DISTANCE)
    state.add_argument("--max-target-distance", type=float, default=DEFAULT_MAX_TARGET_DISTANCE)
    state.add_argument("--destination-x", type=float)
    state.add_argument("--destination-y", type=float)
    state.add_argument("--destination-z", type=float)
    state.add_argument("--destination-label")
    state.add_argument("--arrival-radius", type=float, default=2.0)
    state.add_argument("--alignment-threshold-degrees", type=float, default=7.5)
    state.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "snapshot":
        summary = run_snapshot(args)
    elif args.command == "compare":
        summary = run_compare(args)
    elif args.command == "state":
        summary = run_state(args)
    else:
        raise ValueError(f"unsupported command: {args.command}")
    write_outputs(summary)
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") in {"passed", "no-candidates"} else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
