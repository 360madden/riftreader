from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .navigation_consumer_demo import (
        DEFAULT_CONSUMER_STATE_JSON,
        latest_waypoint_readiness,
        load_optional_json,
        parse_utc,
        path_from_mapping,
        schema_check,
        source_safety_blockers,
    )
    from .workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from navigation_consumer_demo import (  # type: ignore
        DEFAULT_CONSUMER_STATE_JSON,
        latest_waypoint_readiness,
        load_optional_json,
        parse_utc,
        path_from_mapping,
        schema_check,
        source_safety_blockers,
    )
    from workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-route-preview"
DEFAULT_ALIGNMENT_THRESHOLD_DEGREES = 7.5


def resolve_path(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def finite_float(value: Any, label: str, blockers: list[str]) -> float | None:
    if isinstance(value, bool) or value is None:
        blockers.append(f"{label}-must-be-finite-number")
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        blockers.append(f"{label}-must-be-finite-number")
        return None
    if not math.isfinite(number):
        blockers.append(f"{label}-must-be-finite-number")
        return None
    return number


def normalize_degrees(delta: float) -> float:
    normalized = math.fmod(float(delta) + 180.0, 360.0)
    if normalized < 0:
        normalized += 360.0
    return normalized - 180.0


def coord_from_mapping(value: Mapping[str, Any], label: str, blockers: list[str]) -> dict[str, float] | None:
    x = finite_float(value.get("x"), f"{label}-x", blockers)
    y = finite_float(value.get("y"), f"{label}-y", blockers)
    z = finite_float(value.get("z"), f"{label}-z", blockers)
    if x is None or y is None or z is None:
        return None
    return {"x": x, "y": y, "z": z}


def consumer_pose_summary(
    payload: Mapping[str, Any],
    *,
    now: datetime,
    override_max_age: float | None,
    blockers: list[str],
) -> dict[str, Any]:
    generated_at = parse_utc(payload.get("generatedAtUtc"))
    contract = safe_mapping(payload.get("consumerContract"))
    raw_max_age = contract.get("maxConsumerAgeSeconds")
    max_age = override_max_age if override_max_age is not None else float(raw_max_age) if isinstance(raw_max_age, (int, float)) else 5.0
    age_seconds = (now - generated_at).total_seconds() if generated_at else None
    navigation = safe_mapping(payload.get("navigation"))
    position = safe_mapping(navigation.get("position"))
    orientation = safe_mapping(navigation.get("orientation"))
    coordinate = coord_from_mapping(safe_mapping(position.get("coordinate")), "consumer-position", blockers)
    yaw_degrees = finite_float(orientation.get("yawDegrees"), "consumer-yawDegrees", blockers)
    pitch_degrees = orientation.get("pitchDegrees")
    pitch = None if pitch_degrees is None else finite_float(pitch_degrees, "consumer-pitchDegrees", blockers)
    return {
        "status": payload.get("status"),
        "verdict": payload.get("verdict"),
        "generatedAtUtc": payload.get("generatedAtUtc"),
        "ageSeconds": age_seconds,
        "maxAgeSeconds": max_age,
        "fresh": age_seconds is not None and age_seconds <= max_age,
        "target": payload.get("target"),
        "position": coordinate,
        "yawDegrees": yaw_degrees,
        "pitchDegrees": pitch,
    }


def waypoint_from_mapping(raw: Mapping[str, Any], index: int, blockers: list[str]) -> dict[str, Any] | None:
    coordinate = coord_from_mapping(raw, f"waypoint-{index}", blockers)
    radius = finite_float(raw.get("arrivalRadius"), f"waypoint-{index}-arrivalRadius", blockers)
    if radius is not None and radius < 0:
        blockers.append(f"waypoint-{index}-arrivalRadius-must-be-nonnegative")
    if coordinate is None or radius is None or radius < 0:
        return None
    return {
        "id": str(raw.get("id") or f"waypoint-{index:03d}"),
        "label": str(raw.get("label") or raw.get("id") or f"waypoint-{index:03d}"),
        **coordinate,
        "arrivalRadius": radius,
    }


def normalized_waypoints(payload: Mapping[str, Any], blockers: list[str]) -> list[dict[str, Any]]:
    raw_waypoints = payload.get("waypoints")
    if not isinstance(raw_waypoints, list):
        blockers.append("normalized-waypoints-must-be-array")
        return []
    waypoints: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_waypoints, start=1):
        if not isinstance(raw, Mapping):
            blockers.append(f"waypoint-{index}-must-be-object")
            continue
        waypoint = waypoint_from_mapping(raw, index, blockers)
        if waypoint:
            waypoints.append(waypoint)
    if not waypoints:
        blockers.append("normalized-waypoints-empty")
    return waypoints


def build_leg(
    *,
    leg_index: int,
    from_kind: str,
    from_id: str,
    from_label: str,
    start: Mapping[str, float],
    waypoint: Mapping[str, Any],
    current_yaw_degrees: float | None,
    alignment_threshold_degrees: float,
) -> dict[str, Any]:
    dx = float(waypoint["x"]) - float(start["x"])
    dy = float(waypoint["y"]) - float(start["y"])
    dz = float(waypoint["z"]) - float(start["z"])
    planar = math.hypot(dx, dz)
    distance_3d = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
    bearing = normalize_degrees(math.degrees(math.atan2(dz, dx)))
    radius = float(waypoint["arrivalRadius"])
    within_arrival = planar <= radius
    signed_delta = None if current_yaw_degrees is None else normalize_degrees(bearing - float(current_yaw_degrees))
    abs_delta = None if signed_delta is None else abs(signed_delta)
    within_alignment = None if abs_delta is None else abs_delta <= alignment_threshold_degrees
    if within_arrival:
        turn = "arrived"
    elif within_alignment is True:
        turn = "aligned"
    elif signed_delta is None:
        turn = None
    elif signed_delta > 0:
        turn = "right"
    else:
        turn = "left"
    return {
        "legIndex": leg_index,
        "from": {
            "kind": from_kind,
            "id": from_id,
            "label": from_label,
            "coordinate": dict(start),
        },
        "to": {
            "kind": "waypoint",
            "id": waypoint["id"],
            "label": waypoint["label"],
            "coordinate": {"x": waypoint["x"], "y": waypoint["y"], "z": waypoint["z"]},
        },
        "delta": {"x": dx, "y": dy, "z": dz},
        "planarDistance": planar,
        "distance3d": distance_3d,
        "heightDelta": dy,
        "arrivalRadius": radius,
        "withinArrivalRadius": within_arrival,
        "distanceToArrivalBoundary": max(0.0, planar - radius),
        "bearingDegrees": bearing,
        "initialYawDeltaDegrees": signed_delta,
        "absoluteInitialYawDeltaDegrees": abs_delta,
        "alignmentThresholdDegrees": alignment_threshold_degrees,
        "withinAlignmentThreshold": within_alignment,
        "suggestedInitialTurnDirection": turn,
    }


def build_route_preview(
    *,
    pose: Mapping[str, Any],
    waypoints: Sequence[Mapping[str, Any]],
    alignment_threshold_degrees: float,
) -> dict[str, Any]:
    position = safe_mapping(pose.get("position"))
    yaw = pose.get("yawDegrees")
    first_unreached_index: int | None = None
    for index, waypoint in enumerate(waypoints):
        dx = float(waypoint["x"]) - float(position["x"])
        dz = float(waypoint["z"]) - float(position["z"])
        if math.hypot(dx, dz) > float(waypoint["arrivalRadius"]):
            first_unreached_index = index
            break

    if first_unreached_index is None:
        return {
            "waypointCount": len(waypoints),
            "legCount": 0,
            "routeComplete": True,
            "firstUnreachedWaypointIndex": None,
            "nextWaypointId": None,
            "activeLeg": None,
            "legs": [],
            "totalPlanarDistance": 0.0,
            "totalDistance3d": 0.0,
            "routePolyline": [dict(position)],
        }

    remaining = list(waypoints[first_unreached_index:])
    legs: list[dict[str, Any]] = []
    start = {"x": float(position["x"]), "y": float(position["y"]), "z": float(position["z"])}
    from_kind = "current-pose"
    from_id = "current-pose"
    from_label = "Current pose"
    for leg_index, waypoint in enumerate(remaining, start=1):
        leg = build_leg(
            leg_index=leg_index,
            from_kind=from_kind,
            from_id=from_id,
            from_label=from_label,
            start=start,
            waypoint=waypoint,
            current_yaw_degrees=float(yaw) if leg_index == 1 and isinstance(yaw, (int, float)) else None,
            alignment_threshold_degrees=alignment_threshold_degrees,
        )
        legs.append(leg)
        start = {"x": float(waypoint["x"]), "y": float(waypoint["y"]), "z": float(waypoint["z"])}
        from_kind = "waypoint"
        from_id = str(waypoint["id"])
        from_label = str(waypoint["label"])

    route_polyline = [
        {"x": float(position["x"]), "y": float(position["y"]), "z": float(position["z"])},
        *[
            {"x": float(item["x"]), "y": float(item["y"]), "z": float(item["z"])}
            for item in remaining
        ],
    ]
    return {
        "waypointCount": len(waypoints),
        "legCount": len(legs),
        "routeComplete": False,
        "firstUnreachedWaypointIndex": first_unreached_index,
        "nextWaypointId": remaining[0]["id"],
        "activeLeg": legs[0],
        "legs": legs,
        "totalPlanarDistance": sum(float(item["planarDistance"]) for item in legs),
        "totalDistance3d": sum(float(item["distance3d"]) for item in legs),
        "routePolyline": route_polyline,
    }


def build_capabilities(*, schema_ok: bool, pose_fresh: bool, route: Mapping[str, Any]) -> dict[str, Any]:
    route_complete = route.get("routeComplete") is True
    can_render = schema_ok and int(route.get("waypointCount") or 0) > 0
    can_preview = can_render and route.get("legCount") is not None
    can_queue = can_preview and pose_fresh and not route_complete
    if not schema_ok:
        mode = "blocked-schema-invalid"
        action = "Fix or regenerate invalid saved navigation artifacts before route preview consumption."
    elif not can_render:
        mode = "blocked-no-route-to-preview"
        action = "Provide normalized waypoints before building a route preview."
    elif route_complete:
        mode = "route-preview-complete-already-at-waypoints"
        action = "Render route completion; no live navigation request is needed for this waypoint set."
    elif not pose_fresh:
        mode = "route-preview-ready-refresh-pose-before-live-queue"
        action = "Render the preview, then refresh consumer-state pose before requesting gated live navigation."
    else:
        mode = "route-preview-ready-live-run-request-gated"
        action = "External consumer may render preview and queue a gated live-run request; execution still needs explicit live movement approval."
    return {
        "canRenderRoutePreview": can_render,
        "canUseRoutePreview": can_preview,
        "canQueueGatedLiveRunRequest": can_queue,
        "canExecuteLiveNavigation": False,
        "liveExecutionRequiresExplicitApproval": True,
        "recommendedMode": mode,
        "nextRecommendedAction": action,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"navigation-route-preview-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    errors: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    consumer_state_path = resolve_path(root, args.consumer_state_json or DEFAULT_CONSUMER_STATE_JSON)
    readiness_path = resolve_path(root, args.waypoint_readiness_json) if args.waypoint_readiness_json else latest_waypoint_readiness(root)
    readiness_payload = load_optional_json(readiness_path, "waypoint-readiness", errors) if readiness_path else None
    readiness_artifacts = safe_mapping(safe_mapping(readiness_payload).get("artifacts"))
    normalized_path = (
        resolve_path(root, args.normalized_waypoints_json)
        if args.normalized_waypoints_json
        else path_from_mapping(root, readiness_artifacts.get("normalizedWaypointJson"))
    )
    consumer_payload = load_optional_json(consumer_state_path, "consumer-state", errors)
    normalized_payload = load_optional_json(normalized_path, "normalized-waypoints", errors)

    schema_checks = [
        schema_check(root, "consumer-state", consumer_state_path, consumer_payload),
        schema_check(root, "normalized-waypoints", normalized_path, normalized_payload),
    ]
    if readiness_payload is not None:
        schema_checks.append(schema_check(root, "waypoint-readiness", readiness_path, readiness_payload))
    for check in schema_checks:
        if check.get("status") != "passed":
            blockers.append(f"schema-check-blocked:{check.get('label')}")

    for label, payload in (("consumer-state", consumer_payload), ("waypoint-readiness", readiness_payload)):
        if payload is not None:
            blockers.extend(source_safety_blockers(label, payload))

    if consumer_payload and consumer_payload.get("status") != "passed":
        blockers.append(f"consumer-state-status-not-passed:{consumer_payload.get('status')}")
    if readiness_payload and readiness_payload.get("status") != "passed":
        blockers.append(f"waypoint-readiness-status-not-passed:{readiness_payload.get('status')}")

    pose = consumer_pose_summary(
        consumer_payload or {},
        now=now,
        override_max_age=float(args.max_consumer_state_age_seconds)
        if args.max_consumer_state_age_seconds is not None
        else None,
        blockers=blockers,
    )
    if not pose.get("fresh"):
        stale = f"consumer-state-stale:ageSeconds={pose.get('ageSeconds')};maxAgeSeconds={pose.get('maxAgeSeconds')}"
        if args.require_fresh_pose:
            blockers.append(stale)
        else:
            warnings.append(stale)

    waypoints = normalized_waypoints(normalized_payload or {}, blockers)
    route = (
        build_route_preview(
            pose=pose,
            waypoints=waypoints,
            alignment_threshold_degrees=float(args.alignment_threshold_degrees),
        )
        if pose.get("position") and pose.get("yawDegrees") is not None and waypoints
        else {
            "waypointCount": len(waypoints),
            "legCount": 0,
            "routeComplete": False,
            "firstUnreachedWaypointIndex": None,
            "nextWaypointId": None,
            "activeLeg": None,
            "legs": [],
            "totalPlanarDistance": 0.0,
            "totalDistance3d": 0.0,
            "routePolyline": [],
        }
    )
    schema_ok = all(item.get("status") == "passed" for item in schema_checks)
    capabilities = build_capabilities(schema_ok=schema_ok, pose_fresh=pose.get("fresh") is True, route=route)

    safety = base_safety()
    safety.update(
        {
            "readOnlySavedJson": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "routePreviewOnly": True,
            "routeControlAuthorized": False,
        }
    )
    status = "failed" if errors else "blocked" if blockers else "passed"
    if status == "passed":
        verdict = str(capabilities["recommendedMode"])
    elif status == "blocked":
        verdict = "navigation-route-preview-blocked"
    else:
        verdict = "navigation-route-preview-failed"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(root),
        "input": {
            "consumerStateJson": str(consumer_state_path) if consumer_state_path else None,
            "waypointReadinessJson": str(readiness_path) if readiness_path else None,
            "normalizedWaypointsJson": str(normalized_path) if normalized_path else None,
            "requireFreshPose": bool(args.require_fresh_pose),
            "maxConsumerStateAgeSeconds": args.max_consumer_state_age_seconds,
            "alignmentThresholdDegrees": float(args.alignment_threshold_degrees),
        },
        "schemaChecks": schema_checks,
        "consumerPose": pose,
        "route": route,
        "capabilities": capabilities,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    route = safe_mapping(summary.get("route"))
    active_leg = safe_mapping(route.get("activeLeg"))
    caps = safe_mapping(summary.get("capabilities"))
    lines = [
        "# Navigation route preview",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Preview",
        "",
        f"- Waypoints: `{route.get('waypointCount')}`",
        f"- Remaining legs: `{route.get('legCount')}`",
        f"- Route complete: `{route.get('routeComplete')}`",
        f"- Next waypoint: `{route.get('nextWaypointId')}`",
        f"- Total planar distance: `{route.get('totalPlanarDistance')}`",
        "",
        "## Active leg",
        "",
        f"- Bearing degrees: `{active_leg.get('bearingDegrees')}`",
        f"- Initial yaw delta degrees: `{active_leg.get('initialYawDeltaDegrees')}`",
        f"- Suggested initial turn: `{active_leg.get('suggestedInitialTurnDirection')}`",
        f"- Arrival radius: `{active_leg.get('arrivalRadius')}`",
        "",
        "## Capabilities",
        "",
        f"- Can render route preview: `{caps.get('canRenderRoutePreview')}`",
        f"- Can queue gated live-run request: `{caps.get('canQueueGatedLiveRunRequest')}`",
        f"- Can execute live navigation: `{caps.get('canExecuteLiveNavigation')}`",
        f"- Next action: `{caps.get('nextRecommendedAction')}`",
        "",
        "Saved-artifact-only; no input, no movement, and no route execution.",
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
    return "\n".join(lines) + "\n"


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    route = safe_mapping(summary.get("route"))
    active_leg = safe_mapping(route.get("activeLeg"))
    caps = safe_mapping(summary.get("capabilities"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "recommendedMode": caps.get("recommendedMode"),
        "nextRecommendedAction": caps.get("nextRecommendedAction"),
        "waypointCount": route.get("waypointCount"),
        "legCount": route.get("legCount"),
        "routeComplete": route.get("routeComplete"),
        "nextWaypointId": route.get("nextWaypointId"),
        "activeLegPlanarDistance": active_leg.get("planarDistance"),
        "activeLegBearingDegrees": active_leg.get("bearingDegrees"),
        "activeLegInitialYawDeltaDegrees": active_leg.get("initialYawDeltaDegrees"),
        "activeLegSuggestedInitialTurnDirection": active_leg.get("suggestedInitialTurnDirection"),
        "canRenderRoutePreview": caps.get("canRenderRoutePreview"),
        "canQueueGatedLiveRunRequest": caps.get("canQueueGatedLiveRunRequest"),
        "canExecuteLiveNavigation": caps.get("canExecuteLiveNavigation"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "targetMemoryBytesRead": safety.get("targetMemoryBytesRead"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a saved-artifact route preview for downstream navigation consumers")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--consumer-state-json", default=str(DEFAULT_CONSUMER_STATE_JSON))
    parser.add_argument("--waypoint-readiness-json", help="Saved waypoint readiness summary; defaults to newest capture")
    parser.add_argument("--normalized-waypoints-json", help="Optional override; otherwise derived from readiness artifacts")
    parser.add_argument("--max-consumer-state-age-seconds", type=float)
    parser.add_argument("--alignment-threshold-degrees", type=float, default=DEFAULT_ALIGNMENT_THRESHOLD_DEGREES)
    parser.add_argument("--require-fresh-pose", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    summary = build_report(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
