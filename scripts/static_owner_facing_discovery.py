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
NEAR_ZERO_PROGRESS = 0.001  # 1 mm — treat progress at or below this as effectively zero
CATALOG_SUPPORT_OFFSETS = (0x438, 0x43C, 0x440)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def finite_float(value: float) -> bool:
    return math.isfinite(value) and abs(value) < 1_000_000


DEFAULT_TURN_RATE_THRESHOLD = 0.35


def classify_turn_direction_from_rate(
    rate: float | None,
    threshold: float = DEFAULT_TURN_RATE_THRESHOLD,
) -> dict[str, Any]:
    """Classify candidate turn direction from the 0x304 sign.

    Positive values (> +threshold) have correlated with left turns in historical
    captures; negative values (< -threshold) have correlated with right turns.
    Within +/-threshold is a low-magnitude candidate state.

    This is a single 4-byte float read and must stay candidate/support unless
    the dedicated turn-rate promotion gate proves live non-zero delta,
    settle-to-baseline behavior, restart survival, and current-PID freshness.
    Use promoted atan2(yaw) from 0x30C-0x314 and 0x320-0x328 as the hard source.

    Historical evidence: 4-pose triangulation (baseline / turn-right-2 /
    turn-left-3 / turn-left-symmetric):
      - baseline (stationary): 0.247  → within threshold → stationary
      - turn-right-2 (D 500ms):  −1.18 → below −threshold  → right
      - turn-left-3 (A 800ms):   +2.77 → above +threshold  → left
      - turn-left-sym (A 1000ms):+0.61 → above +threshold  → left (settling)

    Current-PID note (2026-06-01): a live stimulus review observed 0x304 can
    remain non-zero at rest and produce turnRateDelta=0.0 during a turn key
    capture, so sign alone is insufficient proof.
    """
    if rate is None or not math.isfinite(rate):
        return {"direction": "unknown", "rate": rate, "turning": False}
    if rate > float(threshold):
        return {"direction": "left", "rate": rate, "turning": True}
    if rate < -float(threshold):
        return {"direction": "right", "rate": rate, "turning": True}
    return {"direction": "stationary", "rate": rate, "turning": False}


def unpack_float(data: bytes, offset: int) -> float | None:
    try:
        value = struct.unpack_from("<f", data, offset)[0]
    except struct.error:
        return None
    return float(value) if finite_float(float(value)) else None


def unpack_i32(data: bytes, offset: int) -> int | None:
    try:
        return int(struct.unpack_from("<i", data, offset)[0])
    except struct.error:
        return None


def unpack_u32(data: bytes, offset: int) -> int | None:
    try:
        return int(struct.unpack_from("<I", data, offset)[0])
    except struct.error:
        return None


def catalog_support_field(data: bytes, *, owner_address: int, offset: int) -> dict[str, Any]:
    raw = data[offset : offset + 4]
    u32 = unpack_u32(data, offset)
    return {
        "state": "candidate",
        "semanticStatus": "unclassified",
        "offset": int_hex(offset),
        "address": int_hex(owner_address + offset),
        "float": unpack_float(data, offset),
        "i32": unpack_i32(data, offset),
        "u32": u32,
        "rawHex": int_hex(u32) if u32 is not None else None,
        "rawBytesLittleEndian": raw.hex(" ") if len(raw) == 4 else None,
    }


def catalog_support_fields(data: bytes, *, owner_address: int) -> dict[str, dict[str, Any]]:
    return {
        f"owner+{int_hex(offset)}": catalog_support_field(data, owner_address=owner_address, offset=offset)
        for offset in CATALOG_SUPPORT_OFFSETS
    }


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
    heading_support = unpack_float(data, 0x300)
    turn_rate = unpack_float(data, 0x304)
    rotation_support = unpack_float(data, 0x308)
    animation_timer = unpack_float(data, 0x408)
    support_fields = catalog_support_fields(data, owner_address=owner_address)
    turn_discriminator = classify_turn_direction_from_rate(turn_rate)
    return {
        "ownerAddress": int_hex(owner_address),
        "coordinate": position,
        "facingTargetCoordinate": facing_target,
        "facingVector": {"x": dx, "y": dy, "z": dz},
        "yawDegrees": yaw,
        "pitchDegrees": pitch,
        "planarLookaheadDistance": planar,
        "lookaheadDistance3d": distance,
        "headingSupport0x300": heading_support,
        "turnRate0x304": turn_rate,
        "turnRateClassification": turn_discriminator["direction"],
        "turnRateDiscriminator": turn_discriminator,
        "rotationSupport0x308": rotation_support,
        "animationTimer0x408": animation_timer,
        "catalogSupportFields": support_fields,
        "positionOffset": "0x320",
        "facingTargetOffset": "0x30C",
        "headingSupportOffset": "0x300",
        "turnRateOffset": "0x304",
        "rotationSupportOffset": "0x308",
        "animationTimerOffset": "0x408",
    }


def navigation_control_chain_labels(root: Path, truth_path_text: str | None) -> dict[str, Any]:
    """Return promoted/candidate labels for nav-state fields from tracked truth.

    The state readback itself is read-only and should not infer promotion from
    raw offsets. This helper lets the summary label fields using the tracked
    current-truth contract when available, while failing closed to candidate
    labels on malformed/missing truth.
    """

    labels: dict[str, Any] = {
        "position": {"state": "promoted", "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328"},
        "facingYaw": {"state": "candidate", "chain": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314"},
        "turnRate": {"state": "candidate", "offset": "0x304"},
        "headingSupport": {"state": "candidate", "offset": "0x300"},
        "rotationSupport": {"state": "candidate", "offset": "0x308"},
        "animationTimer": {"state": "candidate", "offset": "0x408"},
        "catalogSupport": {
            f"owner+{int_hex(offset)}": {"state": "candidate", "offset": int_hex(offset), "semanticStatus": "unclassified"}
            for offset in CATALOG_SUPPORT_OFFSETS
        },
    }
    if not truth_path_text:
        labels["warning"] = "current-truth-path-missing"
        return labels
    try:
        truth_path = Path(truth_path_text)
        if not truth_path.is_absolute():
            truth_path = root / truth_path
        truth = load_json_object(truth_path)
    except Exception as exc:  # noqa: BLE001 - labels must not fail readback.
        labels["warning"] = f"current-truth-label-load-failed:{type(exc).__name__}"
        return labels

    facing = safe_mapping(truth.get("staticOwnerFacing"))
    facing_primary = safe_mapping(facing.get("primaryCandidate"))
    if facing.get("promotionAllowed") is True and facing.get("promotionArtifact"):
        labels["facingYaw"] = {
            "state": "promoted",
            "chain": facing_primary.get("expression") or "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
            "promotionArtifact": facing.get("promotionArtifact"),
        }

    control = safe_mapping(truth.get("navigationControlChains"))
    turn_rate = safe_mapping(control.get("turnRate"))
    if turn_rate.get("promotionAllowed") is True and turn_rate.get("promotionArtifact"):
        labels["turnRate"] = {
            "state": "promoted",
            "offset": turn_rate.get("offset") or "0x304",
            "promotionArtifact": turn_rate.get("promotionArtifact"),
        }
    return labels


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


def load_waypoint_destination(root: Path, waypoint_json: str, waypoint_id: str) -> dict[str, Any]:
    path = Path(waypoint_json)
    if not path.is_absolute():
        path = root / path
    data = load_json_object(path)
    waypoints = data.get("waypoints")
    if not isinstance(waypoints, list):
        raise ValueError("waypoint-json-missing-waypoints-array")
    for item in waypoints:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("id")) != waypoint_id:
            continue
        missing = [axis for axis in ("x", "y", "z") if item.get(axis) is None]
        if missing:
            raise ValueError(f"waypoint-missing-coordinate:{','.join(missing)}")
        return {
            "sourceFile": str(path),
            "waypointId": waypoint_id,
            "label": item.get("label") or waypoint_id,
            "x": float(item["x"]),
            "y": float(item["y"]),
            "z": float(item["z"]),
            "arrivalRadius": None if item.get("arrivalRadius") is None else float(item["arrivalRadius"]),
        }
    raise ValueError(f"waypoint-id-not-found:{waypoint_id}")


def resolve_navigation_target_request(args: argparse.Namespace, root: Path) -> dict[str, Any] | None:
    if args.destination_waypoint_json:
        waypoint = load_waypoint_destination(root, args.destination_waypoint_json, str(args.destination_waypoint_id))
        return {
            "sourceKind": "waypoint-json",
            "sourceFile": waypoint["sourceFile"],
            "waypointId": waypoint["waypointId"],
            "destinationLabel": args.destination_label or waypoint["label"],
            "destinationX": waypoint["x"],
            "destinationY": waypoint["y"],
            "destinationZ": waypoint["z"],
            "arrivalRadius": float(args.arrival_radius if args.arrival_radius is not None else waypoint["arrivalRadius"] if waypoint["arrivalRadius"] is not None else 2.0),
            "alignmentThresholdDegrees": float(args.alignment_threshold_degrees),
        }
    if args.destination_x is not None and args.destination_z is not None:
        return {
            "sourceKind": "direct-coordinates",
            "sourceFile": None,
            "waypointId": None,
            "destinationLabel": args.destination_label,
            "destinationX": float(args.destination_x),
            "destinationY": None if args.destination_y is None else float(args.destination_y),
            "destinationZ": float(args.destination_z),
            "arrivalRadius": float(args.arrival_radius if args.arrival_radius is not None else 2.0),
            "alignmentThresholdDegrees": float(args.alignment_threshold_degrees),
        }
    return None


def validate_navigation_target_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    direct_destination_requested = args.destination_x is not None or args.destination_y is not None or args.destination_z is not None
    waypoint_destination_requested = args.destination_waypoint_json is not None or args.destination_waypoint_id is not None
    if direct_destination_requested and waypoint_destination_requested:
        errors.append("destination-waypoint-and-direct-coordinates-mutually-exclusive")
    if direct_destination_requested and (args.destination_x is None or args.destination_z is None):
        errors.append("destination-x-and-z-required-together")
    if waypoint_destination_requested and not args.destination_waypoint_json:
        errors.append("destination-waypoint-json-required")
    if waypoint_destination_requested and not args.destination_waypoint_id:
        errors.append("destination-waypoint-id-required")
    if args.arrival_radius is not None and args.arrival_radius < 0:
        errors.append("arrival-radius-must-be-nonnegative")
    if args.alignment_threshold_degrees < 0:
        errors.append("alignment-threshold-degrees-must-be-nonnegative")
    return errors


def resolve_plan_navigation_target_request(args: argparse.Namespace, root: Path, source_summary: Mapping[str, Any]) -> dict[str, Any]:
    request = resolve_navigation_target_request(args, root)
    if request is not None:
        return request
    saved_request = safe_mapping(source_summary.get("navigationTargetRequest"))
    required_keys = {"destinationX", "destinationZ", "arrivalRadius", "alignmentThresholdDegrees"}
    if required_keys.issubset(saved_request.keys()):
        return dict(saved_request)
    raise ValueError("navigation-target-required")


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
    errors.extend(validate_navigation_target_args(args))
    return errors


def validate_plan_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if not args.state_summary_json:
        errors.append("state-summary-json-required")
    errors.extend(validate_navigation_target_args(args))
    return errors


def validate_progress_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if not args.plan_summary_json:
        errors.append("plan-summary-json-required")
    elif len(args.plan_summary_json) < 2:
        errors.append("at-least-two-plan-summaries-required")
    if args.minimum_progress_distance < 0:
        errors.append("minimum-progress-distance-must-be-nonnegative")
    if args.wrong_way_tolerance_distance < 0:
        errors.append("wrong-way-tolerance-distance-must-be-nonnegative")
    if args.arrival_radius is not None and args.arrival_radius < 0:
        errors.append("arrival-radius-must-be-nonnegative")
    return errors


def validate_route_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if not args.state_summary_json:
        errors.append("state-summary-json-required")
    elif len(args.state_summary_json) < 2:
        errors.append("at-least-two-state-summaries-required")
    if args.minimum_progress_distance < 0:
        errors.append("minimum-progress-distance-must-be-nonnegative")
    if args.wrong_way_tolerance_distance < 0:
        errors.append("wrong-way-tolerance-distance-must-be-nonnegative")
    errors.extend(validate_navigation_target_args(args))
    return errors


def validate_route_contract_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if not args.route_summary_json:
        errors.append("route-summary-json-required")
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
            "turnRateChain": "[rift_x64+0x32EBC80]+0x304",
            "yawFormula": "atan2((owner+0x314)-(owner+0x328), (owner+0x30C)-(owner+0x320))",
            "currentTruthStaticResolverStatus": defaults.get("staticResolverStatus"),
            "currentTruthPromotionAllowed": defaults.get("promotionAllowed"),
        },
        "chainStates": navigation_control_chain_labels(root, defaults.get("path")),
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
        "navigationTargetRequest": {},
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
    try:
        navigation_target_request = resolve_navigation_target_request(args, root)
        if navigation_target_request is not None:
            summary["navigationTargetRequest"] = navigation_target_request
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "navigation-target-request-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
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
        if summary.get("navigationTargetRequest") and summary.get("latestState"):
            target_request = safe_mapping(summary.get("navigationTargetRequest"))
            summary["navigationTarget"] = navigation_target_from_state(
                summary["latestState"],
                destination_x=float(target_request["destinationX"]),
                destination_y=None if target_request.get("destinationY") is None else float(target_request["destinationY"]),
                destination_z=float(target_request["destinationZ"]),
                destination_label=target_request.get("destinationLabel"),
                arrival_radius=float(target_request["arrivalRadius"]),
                alignment_threshold_degrees=float(target_request["alignmentThresholdDegrees"]),
            )
        summary["blockers"].extend(summary["analysis"].get("blockers", []))
        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "nav-state-readback-blocked"
        else:
            summary["status"] = "passed"
            summary["verdict"] = "position-and-facing-nav-state-readback-passed"
            chain_states = safe_mapping(summary.get("chainStates"))
            facing_state = safe_mapping(chain_states.get("facingYaw")).get("state")
            turn_rate_state = safe_mapping(chain_states.get("turnRate")).get("state")
            if facing_state == "promoted":
                summary["classification"] = "promoted-position-facing-yaw-readback-with-candidate-control-fields"
                if turn_rate_state != "promoted":
                    summary["warnings"].append("turn-rate-control-field-candidate-only-not-promoted")
                    discriminator = safe_mapping(safe_mapping(summary.get("latestState")).get("turnRateDiscriminator"))
                    if args.expect_stationary and discriminator.get("turning") is True:
                        summary["warnings"].append("legacy-0x304-sign-classifier-reports-turning-while-stationary")
            else:
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


def run_plan(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    errors = validate_plan_args(args)
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-nav-target-plan-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-nav-target-dry-run-plan",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "sourceStateSummary": {"path": str(Path(args.state_summary_json).resolve()) if args.state_summary_json else None},
        "navigationTargetRequest": {},
        "navigationTarget": {},
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": base_safety() | {"facingPromotion": False, "navigationControl": False, "dryRunOnly": True},
        "artifacts": {"runDirectory": str(run_dir), "summaryJson": str(run_dir / "summary.json"), "summaryMarkdown": str(run_dir / "summary.md")},
    }
    if errors:
        return summary
    try:
        source_path = Path(args.state_summary_json)
        if not source_path.is_absolute():
            source_path = root / source_path
        source_summary = load_json_object(source_path)
        latest_state = safe_mapping(source_summary.get("latestState"))
        if not latest_state or not latest_state.get("coordinate") or latest_state.get("yawDegrees") is None:
            raise ValueError("state-summary-missing-latest-state-coordinate-or-yaw")
        target_request = resolve_plan_navigation_target_request(args, root, source_summary)
        summary["sourceStateSummary"].update(
            {
                "path": str(source_path),
                "kind": source_summary.get("kind"),
                "status": source_summary.get("status"),
                "verdict": source_summary.get("verdict"),
                "generatedAtUtc": source_summary.get("generatedAtUtc"),
            }
        )
        summary["navigationTargetRequest"] = target_request
        summary["navigationTarget"] = navigation_target_from_state(
            latest_state,
            destination_x=float(target_request["destinationX"]),
            destination_y=None if target_request.get("destinationY") is None else float(target_request["destinationY"]),
            destination_z=float(target_request["destinationZ"]),
            destination_label=target_request.get("destinationLabel"),
            arrival_radius=float(target_request["arrivalRadius"]),
            alignment_threshold_degrees=float(target_request["alignmentThresholdDegrees"]),
        )
        summary["status"] = "passed"
        summary["verdict"] = "static-owner-nav-target-dry-run-plan-built"
        summary["warnings"].extend(
            [
                "dry-run-only-no-live-read-or-input",
                "facing-candidate-readback-only-not-promoted",
            ]
        )
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "static-owner-nav-target-dry-run-plan-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["warnings"] = sorted(set(summary["warnings"]))
    return summary


def load_plan_targets(root: Path, paths: Sequence[str]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for index, raw_path in enumerate(paths):
        path = Path(raw_path)
        if not path.is_absolute():
            path = root / path
        summary = load_json_object(path)
        target = safe_mapping(summary.get("navigationTarget"))
        if not target:
            raise ValueError(f"plan-summary-missing-navigation-target:{path}")
        if target.get("planarDistance") is None:
            raise ValueError(f"plan-summary-missing-planar-distance:{path}")
        targets.append(
            {
                "sampleIndex": index,
                "sourceFile": str(path),
                "status": summary.get("status"),
                "verdict": summary.get("verdict"),
                "generatedAtUtc": summary.get("generatedAtUtc"),
                "planarDistance": float(target["planarDistance"]),
                "arrivalRadius": None if target.get("arrivalRadius") is None else float(target["arrivalRadius"]),
                "withinArrivalRadius": bool(target.get("withinArrivalRadius")),
                "suggestedTurnDirection": target.get("suggestedTurnDirection"),
                "signedBearingDeltaDegrees": target.get("signedBearingDeltaDegrees"),
                "absoluteBearingDeltaDegrees": target.get("absoluteBearingDeltaDegrees"),
                "destination": target.get("destination"),
            }
        )
    return targets


def build_progress_analysis(
    plan_targets: Sequence[Mapping[str, Any]],
    *,
    minimum_progress_distance: float,
    wrong_way_tolerance_distance: float,
    arrival_radius: float | None,
) -> dict[str, Any]:
    if len(plan_targets) < 2:
        raise ValueError("at-least-two-plan-targets-required")
    distances = [float(target["planarDistance"]) for target in plan_targets]
    initial_distance = distances[0]
    final_distance = distances[-1]
    best_distance = min(distances)
    best_index = distances.index(best_distance)
    effective_arrival_radius = arrival_radius
    if effective_arrival_radius is None:
        for target in reversed(plan_targets):
            if target.get("arrivalRadius") is not None:
                effective_arrival_radius = float(target["arrivalRadius"])
                break
            destination = safe_mapping(target.get("destination"))
            if destination.get("arrivalRadius") is not None:
                effective_arrival_radius = float(destination["arrivalRadius"])
                break
    if effective_arrival_radius is None:
        effective_arrival_radius = 0.0

    total_progress = initial_distance - final_distance
    best_progress = initial_distance - best_distance
    moved_wrong_way = final_distance > initial_distance + wrong_way_tolerance_distance
    arrived_now = final_distance <= effective_arrival_radius
    arrived_at_any_sample = any(bool(target.get("withinArrivalRadius")) or float(target["planarDistance"]) <= effective_arrival_radius for target in plan_targets)
    overshot = (
        not arrived_now
        and arrived_at_any_sample
        and final_distance > effective_arrival_radius + wrong_way_tolerance_distance
    ) or (
        not arrived_now
        and best_index < len(distances) - 1
        and best_progress >= minimum_progress_distance
        and final_distance > best_distance + wrong_way_tolerance_distance
    )

    if arrived_now:
        status = "arrived"
        stop_reason = "within-arrival-radius"
    elif overshot:
        status = "overshot"
        stop_reason = "moved-away-after-closest-approach"
    elif moved_wrong_way:
        status = "wrong-way"
        stop_reason = "distance-increased-beyond-tolerance"
    elif total_progress >= minimum_progress_distance:
        status = "progress"
        stop_reason = "distance-decreased"
    else:
        status = "no-progress"
        stop_reason = "minimum-progress-not-met"
        # Sub-classify no-progress for terrain/obstacle diagnostics.
        # Truly zero movement = blocked by terrain/obstacle.
        # Tiny movement below threshold = insufficient progress (stalled).
        # Progress-then-regress = drifted back after initial gain.
        #
        # NOTE: drifted-back-after-initial-progress is only reachable with
        # unusually wide wrong_way_tolerance (>= best_distance - start_distance)
        # because the overshot gate normally fires first. This branch exists for
        # explicit diagnostic configurations where tolerance is intentionally wide.
        #
        # NOTE: When total_progress <= NEAR_ZERO_PROGRESS but best_progress is
        # between NEAR_ZERO_PROGRESS and minimum_progress_distance, no specific
        # branch matches — it falls through to the generic "minimum-progress-not-met"
        # default, which is acceptable for this rare edge case.
        if total_progress <= NEAR_ZERO_PROGRESS and best_progress <= NEAR_ZERO_PROGRESS:
            stop_reason = "blocked-stationary-no-movement"
        elif best_progress >= minimum_progress_distance and total_progress <= NEAR_ZERO_PROGRESS:
            stop_reason = "drifted-back-after-initial-progress"
        elif 0.0 < total_progress < minimum_progress_distance:
            stop_reason = "insufficient-progress-below-threshold"

    transitions: list[dict[str, Any]] = []
    for index in range(1, len(plan_targets)):
        previous = plan_targets[index - 1]
        current = plan_targets[index]
        previous_distance = float(previous["planarDistance"])
        current_distance = float(current["planarDistance"])
        transitions.append(
            {
                "fromSample": previous.get("sampleIndex"),
                "toSample": current.get("sampleIndex"),
                "previousPlanarDistance": previous_distance,
                "currentPlanarDistance": current_distance,
                "progressDistance": previous_distance - current_distance,
                "distanceIncreased": current_distance > previous_distance,
            }
        )
    return {
        "status": status,
        "stopReason": stop_reason,
        "sampleCount": len(plan_targets),
        "initialPlanarDistance": initial_distance,
        "finalPlanarDistance": final_distance,
        "bestPlanarDistance": best_distance,
        "bestSampleIndex": plan_targets[best_index].get("sampleIndex"),
        "totalProgressDistance": total_progress,
        "bestProgressDistance": best_progress,
        "minimumProgressDistance": float(minimum_progress_distance),
        "wrongWayToleranceDistance": float(wrong_way_tolerance_distance),
        "arrivalRadius": float(effective_arrival_radius),
        "arrivedAtAnySample": arrived_at_any_sample,
        "candidateOnly": True,
        "actionableForMovement": False,
        "noProgressSubClassification": stop_reason if status == "no-progress" and stop_reason != "minimum-progress-not-met" else None,
        "transitions": transitions,
    }


def run_progress(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    errors = validate_progress_args(args)
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-nav-progress-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-nav-progress-dry-run",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "planTargets": [],
        "analysis": {},
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": base_safety() | {"facingPromotion": False, "navigationControl": False, "dryRunOnly": True},
        "artifacts": {"runDirectory": str(run_dir), "summaryJson": str(run_dir / "summary.json"), "summaryMarkdown": str(run_dir / "summary.md")},
    }
    if errors:
        return summary
    try:
        plan_targets = load_plan_targets(root, args.plan_summary_json)
        summary["planTargets"] = plan_targets
        summary["analysis"] = build_progress_analysis(
            plan_targets,
            minimum_progress_distance=float(args.minimum_progress_distance),
            wrong_way_tolerance_distance=float(args.wrong_way_tolerance_distance),
            arrival_radius=None if args.arrival_radius is None else float(args.arrival_radius),
        )
        summary["status"] = "passed"
        summary["verdict"] = "static-owner-nav-progress-dry-run-built"
        summary["warnings"].extend(
            [
                "dry-run-only-no-live-read-or-input",
                "progress-analysis-is-not-movement-permission",
            ]
        )
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "static-owner-nav-progress-dry-run-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["warnings"] = sorted(set(summary["warnings"]))
    return summary


def build_route_plan_targets(
    root: Path,
    state_summary_paths: Sequence[str],
    target_request: Mapping[str, Any],
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for index, raw_path in enumerate(state_summary_paths):
        path = Path(raw_path)
        if not path.is_absolute():
            path = root / path
        source_summary = load_json_object(path)
        latest_state = safe_mapping(source_summary.get("latestState"))
        if not latest_state or not latest_state.get("coordinate") or latest_state.get("yawDegrees") is None:
            raise ValueError(f"state-summary-missing-latest-state-coordinate-or-yaw:{path}")
        navigation_target = navigation_target_from_state(
            latest_state,
            destination_x=float(target_request["destinationX"]),
            destination_y=None if target_request.get("destinationY") is None else float(target_request["destinationY"]),
            destination_z=float(target_request["destinationZ"]),
            destination_label=target_request.get("destinationLabel"),
            arrival_radius=float(target_request["arrivalRadius"]),
            alignment_threshold_degrees=float(target_request["alignmentThresholdDegrees"]),
        )
        targets.append(
            {
                "sampleIndex": index,
                "sourceFile": str(path),
                "kind": source_summary.get("kind"),
                "status": source_summary.get("status"),
                "verdict": source_summary.get("verdict"),
                "generatedAtUtc": source_summary.get("generatedAtUtc"),
                "coordinate": latest_state.get("coordinate"),
                "yawDegrees": latest_state.get("yawDegrees"),
                "navigationTarget": navigation_target,
                "planarDistance": float(navigation_target["planarDistance"]),
                "arrivalRadius": float(navigation_target["arrivalRadius"]),
                "withinArrivalRadius": bool(navigation_target["withinArrivalRadius"]),
                "suggestedTurnDirection": navigation_target.get("suggestedTurnDirection"),
                "signedBearingDeltaDegrees": navigation_target.get("signedBearingDeltaDegrees"),
                "absoluteBearingDeltaDegrees": navigation_target.get("absoluteBearingDeltaDegrees"),
                "destination": navigation_target.get("destination"),
            }
        )
    return targets


def build_route_controller_recommendation(
    route_targets: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> dict[str, Any]:
    if not route_targets:
        raise ValueError("route-targets-required")
    latest_target = safe_mapping(route_targets[-1])
    navigation_target = safe_mapping(latest_target.get("navigationTarget"))
    if not navigation_target:
        navigation_target = latest_target
    progress_status = str(analysis.get("status") or "unknown")
    suggested_turn = navigation_target.get("suggestedTurnDirection")
    if progress_status == "arrived":
        recommended_action = "stop-arrived"
        control_intent = "stop"
        reason = "within-arrival-radius"
    elif progress_status == "overshot":
        recommended_action = "stop-overshot"
        control_intent = "stop"
        reason = "moved-away-after-closest-approach"
    elif progress_status == "wrong-way":
        recommended_action = "stop-wrong-way"
        control_intent = "stop"
        reason = "distance-increased-beyond-tolerance"
    elif progress_status == "no-progress":
        recommended_action = "sample-more-or-reassess"
        control_intent = "wait"
        reason = "minimum-progress-not-met"
    elif suggested_turn == "left":
        recommended_action = "turn-left-candidate"
        control_intent = "turn-left"
        reason = "candidate-bearing-left-of-current-yaw"
    elif suggested_turn == "right":
        recommended_action = "turn-right-candidate"
        control_intent = "turn-right"
        reason = "candidate-bearing-right-of-current-yaw"
    else:
        recommended_action = "continue-aligned-candidate"
        control_intent = "continue"
        reason = "candidate-bearing-within-alignment-threshold"
    return {
        "status": "candidate-controller-recommendation",
        "recommendedAction": recommended_action,
        "controlIntent": control_intent,
        "reason": reason,
        "progressStatus": progress_status,
        "stopReason": analysis.get("stopReason"),
        "sourceSampleIndex": latest_target.get("sampleIndex"),
        "sourceFile": latest_target.get("sourceFile"),
        "latestPlanarDistance": navigation_target.get("planarDistance"),
        "arrivalRadius": navigation_target.get("arrivalRadius"),
        "suggestedTurnDirection": suggested_turn,
        "signedBearingDeltaDegrees": navigation_target.get("signedBearingDeltaDegrees"),
        "absoluteBearingDeltaDegrees": navigation_target.get("absoluteBearingDeltaDegrees"),
        "withinArrivalRadius": navigation_target.get("withinArrivalRadius"),
        "withinAlignmentThreshold": navigation_target.get("withinAlignmentThreshold"),
        "candidateOnly": True,
        "dryRunOnly": True,
        "actionableForMovement": False,
        "movementPermission": False,
        "navigationControl": False,
        "requiresFreshPreflightBeforeLiveUse": True,
    }


def run_route(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    errors = validate_route_args(args)
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-nav-route-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-nav-route-dry-run",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "sourceStateSummaries": [str(Path(path).resolve()) for path in (args.state_summary_json or [])],
        "navigationTargetRequest": {},
        "routePlanTargets": [],
        "analysis": {},
        "controllerRecommendation": {},
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": base_safety() | {"facingPromotion": False, "navigationControl": False, "dryRunOnly": True},
        "artifacts": {"runDirectory": str(run_dir), "summaryJson": str(run_dir / "summary.json"), "summaryMarkdown": str(run_dir / "summary.md")},
    }
    if errors:
        return summary
    try:
        first_path = Path(args.state_summary_json[0])
        if not first_path.is_absolute():
            first_path = root / first_path
        first_summary = load_json_object(first_path)
        target_request = resolve_plan_navigation_target_request(args, root, first_summary)
        route_targets = build_route_plan_targets(root, args.state_summary_json, target_request)
        summary["navigationTargetRequest"] = target_request
        summary["routePlanTargets"] = route_targets
        summary["analysis"] = build_progress_analysis(
            route_targets,
            minimum_progress_distance=float(args.minimum_progress_distance),
            wrong_way_tolerance_distance=float(args.wrong_way_tolerance_distance),
            arrival_radius=None if args.arrival_radius is None else float(args.arrival_radius),
        )
        summary["controllerRecommendation"] = build_route_controller_recommendation(
            route_targets,
            safe_mapping(summary.get("analysis")),
        )
        summary["status"] = "passed"
        summary["verdict"] = "static-owner-nav-route-dry-run-built"
        summary["warnings"].extend(
            [
                "dry-run-only-no-live-read-or-input",
                "route-analysis-is-not-movement-permission",
                "controller-recommendation-is-candidate-only-not-movement-permission",
                "facing-candidate-readback-only-not-promoted",
            ]
        )
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "static-owner-nav-route-dry-run-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["warnings"] = sorted(set(summary["warnings"]))
    return summary


def validate_route_summary_contract(route_summary: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if route_summary.get("kind") != "static-owner-nav-route-dry-run":
        blockers.append("route-summary-kind-must-be-static-owner-nav-route-dry-run")
    if route_summary.get("status") != "passed":
        blockers.append("route-summary-status-must-be-passed")

    route_targets = route_summary.get("routePlanTargets")
    if not isinstance(route_targets, list) or len(route_targets) < 2:
        blockers.append("route-plan-targets-must-have-at-least-two-samples")
        route_targets = []
    analysis = safe_mapping(route_summary.get("analysis"))
    controller = safe_mapping(route_summary.get("controllerRecommendation"))
    safety = safe_mapping(route_summary.get("safety"))
    if not analysis:
        blockers.append("analysis-required")
    elif analysis.get("actionableForMovement") is not False:
        blockers.append("analysis-actionable-for-movement-must-be-false")
    if analysis.get("candidateOnly") is not True:
        blockers.append("analysis-candidate-only-must-be-true")
    if not controller:
        blockers.append("controller-recommendation-required")
    controller_required_false = {
        "movementPermission": "controller-movement-permission-must-be-false",
        "actionableForMovement": "controller-actionable-for-movement-must-be-false",
        "navigationControl": "controller-navigation-control-must-be-false",
    }
    controller_required_true = {
        "candidateOnly": "controller-candidate-only-must-be-true",
        "dryRunOnly": "controller-dry-run-only-must-be-true",
        "requiresFreshPreflightBeforeLiveUse": "controller-requires-fresh-preflight-before-live-use-must-be-true",
    }
    for key, blocker in controller_required_false.items():
        if controller.get(key) is not False:
            blockers.append(blocker)
    for key, blocker in controller_required_true.items():
        if controller.get(key) is not True:
            blockers.append(blocker)

    safety_required_false = {
        "movementSent": "safety-movement-sent-must-be-false",
        "inputSent": "safety-input-sent-must-be-false",
        "reloaduiSent": "safety-reloadui-sent-must-be-false",
        "screenshotKeySent": "safety-screenshot-key-sent-must-be-false",
        "x64dbgAttach": "safety-x64dbg-attach-must-be-false",
        "providerWrites": "safety-provider-writes-must-be-false",
        "navigationControl": "safety-navigation-control-must-be-false",
    }
    for key, blocker in safety_required_false.items():
        if safety.get(key) is not False:
            blockers.append(blocker)
    if safety.get("noCheatEngine") is not True:
        blockers.append("safety-no-cheat-engine-must-be-true")
    if safety.get("dryRunOnly") is not True:
        blockers.append("safety-dry-run-only-must-be-true")
    if safety.get("facingPromotion") is not False:
        blockers.append("safety-facing-promotion-must-be-false")

    for index, target in enumerate(route_targets):
        target_mapping = safe_mapping(target)
        navigation_target = safe_mapping(target_mapping.get("navigationTarget"))
        if not navigation_target:
            blockers.append(f"route-target-{index}-navigation-target-required")
            continue
        if navigation_target.get("candidateOnly") is not True:
            blockers.append(f"route-target-{index}-candidate-only-must-be-true")
        if navigation_target.get("actionableForMovement") is not False:
            blockers.append(f"route-target-{index}-actionable-for-movement-must-be-false")
        if navigation_target.get("planarDistance") is None:
            blockers.append(f"route-target-{index}-planar-distance-required")
    recommended_action = controller.get("recommendedAction")
    allowed_actions = {
        "stop-arrived",
        "stop-overshot",
        "stop-wrong-way",
        "sample-more-or-reassess",
        "turn-left-candidate",
        "turn-right-candidate",
        "continue-aligned-candidate",
    }
    if recommended_action and recommended_action not in allowed_actions:
        warnings.append(f"controller-recommended-action-unrecognized:{recommended_action}")
    return {
        "status": "blocked" if blockers else "passed",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "routeStatus": analysis.get("status"),
        "stopReason": analysis.get("stopReason"),
        "sampleCount": analysis.get("sampleCount"),
        "checkedRouteTargetCount": len(route_targets),
        "controllerRecommendedAction": recommended_action,
        "controllerControlIntent": controller.get("controlIntent"),
        "movementPermission": controller.get("movementPermission"),
        "dryRunOnly": controller.get("dryRunOnly"),
        "candidateOnly": controller.get("candidateOnly"),
        "actionableForMovement": controller.get("actionableForMovement"),
    }


def run_validate_route(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    errors = validate_route_contract_args(args)
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-nav-route-contract-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    route_summary_path = Path(args.route_summary_json).resolve() if args.route_summary_json else None
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-nav-route-contract-validation",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "sourceRouteSummary": {"path": str(route_summary_path) if route_summary_path else None},
        "contract": {},
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": base_safety() | {"facingPromotion": False, "navigationControl": False, "dryRunOnly": True},
        "artifacts": {"runDirectory": str(run_dir), "summaryJson": str(run_dir / "summary.json"), "summaryMarkdown": str(run_dir / "summary.md")},
    }
    if errors:
        return summary
    try:
        source_path = Path(args.route_summary_json)
        if not source_path.is_absolute():
            source_path = root / source_path
        route_summary = load_json_object(source_path)
        summary["sourceRouteSummary"].update(
            {
                "path": str(source_path),
                "kind": route_summary.get("kind"),
                "status": route_summary.get("status"),
                "verdict": route_summary.get("verdict"),
                "generatedAtUtc": route_summary.get("generatedAtUtc"),
            }
        )
        contract = validate_route_summary_contract(route_summary)
        summary["contract"] = contract
        summary["blockers"] = list(contract.get("blockers", []))
        summary["warnings"].extend(contract.get("warnings", []))
        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "static-owner-nav-route-contract-blocked"
        else:
            summary["status"] = "passed"
            summary["verdict"] = "static-owner-nav-route-contract-passed"
            summary["warnings"].append("route-contract-validation-is-not-movement-permission")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "static-owner-nav-route-contract-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
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
    if summary.get("kind") == "static-owner-nav-route-contract-validation":
        contract = safe_mapping(summary.get("contract"))
        lines = [
            "# Static owner navigation route contract validation",
            "",
            f"Status: `{summary.get('status')}`",
            f"Verdict: `{summary.get('verdict')}`",
            f"Route status: `{contract.get('routeStatus')}`",
            f"Controller recommendation: `{contract.get('controllerRecommendedAction')}`",
            f"Movement permission: `{contract.get('movementPermission')}`",
            f"Checked route targets: `{contract.get('checkedRouteTargetCount')}`",
            "",
            "Contract validation only; no live read, no movement, and no movement permission.",
        ]
        if summary.get("blockers"):
            lines.extend(["", "## Blockers", ""])
            lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
        if summary.get("errors"):
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- `{item}`" for item in summary.get("errors", []))
        if summary.get("warnings"):
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
        return "\n".join(lines) + "\n"
    if summary.get("kind") == "static-owner-nav-route-dry-run":
        analysis = safe_mapping(summary.get("analysis"))
        controller = safe_mapping(summary.get("controllerRecommendation"))
        lines = [
            "# Static owner navigation route dry-run",
            "",
            f"Status: `{summary.get('status')}`",
            f"Verdict: `{summary.get('verdict')}`",
            f"Route status: `{analysis.get('status')}`",
            f"Stop reason: `{analysis.get('stopReason')}`",
            f"State summaries: `{len(summary.get('sourceStateSummaries', []))}`",
            f"Initial distance: `{analysis.get('initialPlanarDistance')}`",
            f"Final distance: `{analysis.get('finalPlanarDistance')}`",
            f"Best distance: `{analysis.get('bestPlanarDistance')}`",
            f"Total progress: `{analysis.get('totalProgressDistance')}`",
            f"Controller recommendation: `{controller.get('recommendedAction')}`",
            f"Controller movement permission: `{controller.get('movementPermission')}`",
            "",
            "Dry-run only; no live read, no movement, and no movement permission.",
        ]
        if summary.get("errors"):
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- `{item}`" for item in summary.get("errors", []))
        if summary.get("warnings"):
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
        return "\n".join(lines) + "\n"
    if summary.get("kind") == "static-owner-nav-progress-dry-run":
        analysis = safe_mapping(summary.get("analysis"))
        lines = [
            "# Static owner navigation progress dry-run",
            "",
            f"Status: `{summary.get('status')}`",
            f"Verdict: `{summary.get('verdict')}`",
            f"Progress status: `{analysis.get('status')}`",
            f"Stop reason: `{analysis.get('stopReason')}`",
            f"Initial distance: `{analysis.get('initialPlanarDistance')}`",
            f"Final distance: `{analysis.get('finalPlanarDistance')}`",
            f"Best distance: `{analysis.get('bestPlanarDistance')}`",
            f"Total progress: `{analysis.get('totalProgressDistance')}`",
            "",
            "Dry-run only; no live read, no movement, and no movement permission.",
        ]
        if summary.get("errors"):
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- `{item}`" for item in summary.get("errors", []))
        if summary.get("warnings"):
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
        return "\n".join(lines) + "\n"
    if summary.get("kind") == "static-owner-nav-target-dry-run-plan":
        source = safe_mapping(summary.get("sourceStateSummary"))
        target_request = safe_mapping(summary.get("navigationTargetRequest"))
        navigation_target = safe_mapping(summary.get("navigationTarget"))
        lines = [
            "# Static owner navigation target dry-run plan",
            "",
            f"Status: `{summary.get('status')}`",
            f"Verdict: `{summary.get('verdict')}`",
            f"Source state: `{source}`",
            "",
            "## Navigation target analysis",
            "",
            f"Request: `{target_request}`",
            f"Destination: `{navigation_target.get('destination')}`",
            f"Planar distance: `{navigation_target.get('planarDistance')}`",
            f"Destination bearing: `{navigation_target.get('destinationBearingDegrees')}`",
            f"Signed bearing delta: `{navigation_target.get('signedBearingDeltaDegrees')}`",
            f"Suggested turn: `{navigation_target.get('suggestedTurnDirection')}`",
            f"Candidate only: `{navigation_target.get('candidateOnly')}`",
            "",
            "Dry-run only; no live read, no movement, and no facing promotion.",
        ]
        if summary.get("errors"):
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- `{item}`" for item in summary.get("errors", []))
        if summary.get("warnings"):
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
        return "\n".join(lines) + "\n"
    if summary.get("kind") == "static-owner-nav-state-readback":
        latest = safe_mapping(summary.get("latestState"))
        analysis = safe_mapping(summary.get("analysis"))
        target_request = safe_mapping(summary.get("navigationTargetRequest"))
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
                    f"Request: `{target_request}`",
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
    if summary.get("kind") == "static-owner-nav-route-contract-validation":
        contract = safe_mapping(summary.get("contract"))
        return {
            "status": summary.get("status"),
            "verdict": summary.get("verdict"),
            "routeStatus": contract.get("routeStatus"),
            "controllerRecommendedAction": contract.get("controllerRecommendedAction"),
            "movementPermission": contract.get("movementPermission"),
            "dryRunOnly": contract.get("dryRunOnly"),
            "candidateOnly": contract.get("candidateOnly"),
            "actionableForMovement": contract.get("actionableForMovement"),
            "checkedRouteTargetCount": contract.get("checkedRouteTargetCount"),
            "summaryJson": artifacts.get("summaryJson"),
            "summaryMarkdown": artifacts.get("summaryMarkdown"),
            "blockers": summary.get("blockers", []),
            "warnings": summary.get("warnings", []),
            "errors": summary.get("errors", []),
        }
    if summary.get("kind") == "static-owner-nav-route-dry-run":
        return {
            "status": summary.get("status"),
            "verdict": summary.get("verdict"),
            "routeStatus": safe_mapping(summary.get("analysis")).get("status"),
            "stopReason": safe_mapping(summary.get("analysis")).get("stopReason"),
            "sampleCount": safe_mapping(summary.get("analysis")).get("sampleCount"),
            "initialPlanarDistance": safe_mapping(summary.get("analysis")).get("initialPlanarDistance"),
            "finalPlanarDistance": safe_mapping(summary.get("analysis")).get("finalPlanarDistance"),
            "totalProgressDistance": safe_mapping(summary.get("analysis")).get("totalProgressDistance"),
            "navigationTargetRequest": summary.get("navigationTargetRequest") or None,
            "controllerRecommendation": summary.get("controllerRecommendation") or None,
            "summaryJson": artifacts.get("summaryJson"),
            "summaryMarkdown": artifacts.get("summaryMarkdown"),
            "blockers": summary.get("blockers", []),
            "warnings": summary.get("warnings", []),
            "errors": summary.get("errors", []),
        }
    if summary.get("kind") == "static-owner-nav-progress-dry-run":
        return {
            "status": summary.get("status"),
            "verdict": summary.get("verdict"),
            "progressStatus": safe_mapping(summary.get("analysis")).get("status"),
            "stopReason": safe_mapping(summary.get("analysis")).get("stopReason"),
            "sampleCount": safe_mapping(summary.get("analysis")).get("sampleCount"),
            "initialPlanarDistance": safe_mapping(summary.get("analysis")).get("initialPlanarDistance"),
            "finalPlanarDistance": safe_mapping(summary.get("analysis")).get("finalPlanarDistance"),
            "totalProgressDistance": safe_mapping(summary.get("analysis")).get("totalProgressDistance"),
            "summaryJson": artifacts.get("summaryJson"),
            "summaryMarkdown": artifacts.get("summaryMarkdown"),
            "blockers": summary.get("blockers", []),
            "warnings": summary.get("warnings", []),
            "errors": summary.get("errors", []),
        }
    if summary.get("kind") == "static-owner-nav-target-dry-run-plan":
        return {
            "status": summary.get("status"),
            "verdict": summary.get("verdict"),
            "sourceStateSummary": summary.get("sourceStateSummary"),
            "navigationTargetRequest": summary.get("navigationTargetRequest") or None,
            "navigationTarget": summary.get("navigationTarget") or None,
            "summaryJson": artifacts.get("summaryJson"),
            "summaryMarkdown": artifacts.get("summaryMarkdown"),
            "blockers": summary.get("blockers", []),
            "warnings": summary.get("warnings", []),
            "errors": summary.get("errors", []),
        }
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
            "navigationTargetRequest": summary.get("navigationTargetRequest") or None,
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

    plan = subparsers.add_parser("plan")
    plan.add_argument("--repo-root")
    plan.add_argument("--output-root")
    plan.add_argument("--state-summary-json", required=True)
    plan.add_argument("--destination-x", type=float)
    plan.add_argument("--destination-y", type=float)
    plan.add_argument("--destination-z", type=float)
    plan.add_argument("--destination-label")
    plan.add_argument("--destination-waypoint-json")
    plan.add_argument("--destination-waypoint-id")
    plan.add_argument("--arrival-radius", type=float)
    plan.add_argument("--alignment-threshold-degrees", type=float, default=7.5)
    plan.add_argument("--json", action="store_true")

    progress = subparsers.add_parser("progress")
    progress.add_argument("--repo-root")
    progress.add_argument("--output-root")
    progress.add_argument("--plan-summary-json", nargs="+", required=True)
    progress.add_argument("--minimum-progress-distance", type=float, default=0.35)
    progress.add_argument("--wrong-way-tolerance-distance", type=float, default=0.75)
    progress.add_argument("--arrival-radius", type=float)
    progress.add_argument("--json", action="store_true")

    route = subparsers.add_parser("route")
    route.add_argument("--repo-root")
    route.add_argument("--output-root")
    route.add_argument("--state-summary-json", nargs="+", required=True)
    route.add_argument("--destination-x", type=float)
    route.add_argument("--destination-y", type=float)
    route.add_argument("--destination-z", type=float)
    route.add_argument("--destination-label")
    route.add_argument("--destination-waypoint-json")
    route.add_argument("--destination-waypoint-id")
    route.add_argument("--arrival-radius", type=float)
    route.add_argument("--alignment-threshold-degrees", type=float, default=7.5)
    route.add_argument("--minimum-progress-distance", type=float, default=0.35)
    route.add_argument("--wrong-way-tolerance-distance", type=float, default=0.75)
    route.add_argument("--json", action="store_true")

    validate_route = subparsers.add_parser("validate-route")
    validate_route.add_argument("--repo-root")
    validate_route.add_argument("--output-root")
    validate_route.add_argument("--route-summary-json", required=True)
    validate_route.add_argument("--json", action="store_true")

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
    state.add_argument("--destination-waypoint-json")
    state.add_argument("--destination-waypoint-id")
    state.add_argument("--arrival-radius", type=float)
    state.add_argument("--alignment-threshold-degrees", type=float, default=7.5)
    state.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "snapshot":
        summary = run_snapshot(args)
    elif args.command == "compare":
        summary = run_compare(args)
    elif args.command == "plan":
        summary = run_plan(args)
    elif args.command == "progress":
        summary = run_progress(args)
    elif args.command == "route":
        summary = run_route(args)
    elif args.command == "validate-route":
        summary = run_validate_route(args)
    elif args.command == "state":
        summary = run_state(args)
    else:
        raise ValueError(f"unsupported command: {args.command}")
    write_outputs(summary)
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") in {"passed", "no-candidates"} else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
