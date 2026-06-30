from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .navigation_route_preview import normalize_degrees
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from navigation_route_preview import normalize_degrees  # type: ignore
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-offline-simulation"
DEFAULT_STEP_DISTANCE = 2.0
DEFAULT_TURN_STEP_DEGREES = 30.0
DEFAULT_MAX_STEPS = 20
DEFAULT_ALIGNMENT_THRESHOLD_DEGREES = 7.5
DEFAULT_ARRIVAL_RADIUS = 1.0
DEFAULT_MINIMUM_PROGRESS_DISTANCE = 0.05
DEFAULT_WRONG_WAY_TOLERANCE_DISTANCE = 0.25


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


def validate_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    direct_requested = args.destination_x is not None or args.destination_y is not None or args.destination_z is not None
    if direct_requested and args.waypoints_json:
        errors.append("destination-and-waypoints-json-mutually-exclusive")
    if direct_requested and (args.destination_x is None or args.destination_z is None):
        errors.append("destination-x-and-z-required")
    if not direct_requested and not args.waypoints_json:
        errors.append("destination-or-waypoints-json-required")
    if args.step_distance < 0:
        errors.append("step-distance-must-be-nonnegative")
    if args.turn_step_degrees <= 0 or args.turn_step_degrees > 180:
        errors.append("turn-step-degrees-must-be-between-zero-and-180")
    if args.max_steps <= 0:
        errors.append("max-steps-must-be-positive")
    if args.arrival_radius < 0:
        errors.append("arrival-radius-must-be-nonnegative")
    if args.alignment_threshold_degrees < 0 or args.alignment_threshold_degrees > 180:
        errors.append("alignment-threshold-degrees-must-be-between-zero-and-180")
    if args.minimum_progress_distance < 0:
        errors.append("minimum-progress-distance-must-be-nonnegative")
    if args.wrong_way_tolerance_distance < 0:
        errors.append("wrong-way-tolerance-distance-must-be-nonnegative")
    if args.stuck_after_step is not None and args.stuck_after_step <= 0:
        errors.append("stuck-after-step-must-be-positive")
    return sorted(set(errors))


def pose_from_args(args: argparse.Namespace) -> dict[str, float]:
    return {
        "x": float(args.start_x),
        "y": float(args.start_y),
        "z": float(args.start_z),
        "yawDegrees": normalize_degrees(float(args.start_yaw_degrees)),
    }


def waypoints_from_args(args: argparse.Namespace, root: Path, blockers: list[str]) -> list[dict[str, Any]]:
    if args.waypoints_json:
        path = Path(args.waypoints_json)
        if not path.is_absolute():
            path = root / path
        try:
            payload = load_json_object(path)
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"waypoints-json-load-failed:{type(exc).__name__}:{exc}")
            return []
        raw_waypoints = payload.get("waypoints")
        if not isinstance(raw_waypoints, list):
            blockers.append("waypoints-json-waypoints-must-be-array")
            return []
        waypoints: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_waypoints, start=1):
            if not isinstance(raw, Mapping):
                blockers.append(f"waypoint-{index}-must-be-object")
                continue
            waypoint = waypoint_from_mapping(raw, index, blockers, default_radius=float(args.arrival_radius))
            if waypoint:
                waypoints.append(waypoint)
        if not waypoints:
            blockers.append("waypoints-empty")
        return waypoints

    direct = {
        "id": str(args.destination_id or "destination-001"),
        "label": str(args.destination_label or args.destination_id or "Destination"),
        "x": args.destination_x,
        "y": args.destination_y if args.destination_y is not None else args.start_y,
        "z": args.destination_z,
        "arrivalRadius": args.arrival_radius,
    }
    waypoint = waypoint_from_mapping(direct, 1, blockers, default_radius=float(args.arrival_radius))
    return [waypoint] if waypoint else []


def waypoint_from_mapping(
    raw: Mapping[str, Any],
    index: int,
    blockers: list[str],
    *,
    default_radius: float,
) -> dict[str, Any] | None:
    x = finite_float(raw.get("x"), f"waypoint-{index}-x", blockers)
    y = finite_float(raw.get("y", 0.0), f"waypoint-{index}-y", blockers)
    z = finite_float(raw.get("z"), f"waypoint-{index}-z", blockers)
    radius_raw = raw.get("arrivalRadius", raw.get("radius", default_radius))
    radius = finite_float(radius_raw, f"waypoint-{index}-arrivalRadius", blockers)
    if radius is not None and radius < 0:
        blockers.append(f"waypoint-{index}-arrivalRadius-must-be-nonnegative")
    if x is None or y is None or z is None or radius is None or radius < 0:
        return None
    return {
        "id": str(raw.get("id") or f"waypoint-{index:03d}"),
        "label": str(raw.get("label") or raw.get("id") or f"waypoint-{index:03d}"),
        "x": x,
        "y": y,
        "z": z,
        "arrivalRadius": radius,
    }


def planar_distance(pose: Mapping[str, float], waypoint: Mapping[str, Any]) -> float:
    return math.hypot(float(waypoint["x"]) - float(pose["x"]), float(waypoint["z"]) - float(pose["z"]))


def bearing_to_waypoint(pose: Mapping[str, float], waypoint: Mapping[str, Any]) -> float:
    dx = float(waypoint["x"]) - float(pose["x"])
    dz = float(waypoint["z"]) - float(pose["z"])
    return normalize_degrees(math.degrees(math.atan2(dz, dx)))


def active_waypoint_index(pose: Mapping[str, float], waypoints: Sequence[Mapping[str, Any]]) -> int | None:
    for index, waypoint in enumerate(waypoints):
        if planar_distance(pose, waypoint) > float(waypoint["arrivalRadius"]):
            return index
    return None


def turn_direction(delta_degrees: float) -> str:
    if delta_degrees > 0:
        return "right"
    if delta_degrees < 0:
        return "left"
    return "aligned"


def advance_yaw(current_yaw: float, delta_degrees: float, turn_step_degrees: float) -> float:
    if abs(delta_degrees) <= turn_step_degrees:
        return normalize_degrees(current_yaw + delta_degrees)
    return normalize_degrees(current_yaw + (turn_step_degrees if delta_degrees > 0 else -turn_step_degrees))


def forward_pose(pose: Mapping[str, float], distance: float) -> dict[str, float]:
    yaw_radians = math.radians(float(pose["yawDegrees"]))
    return {
        "x": float(pose["x"]) + math.cos(yaw_radians) * distance,
        "y": float(pose["y"]),
        "z": float(pose["z"]) + math.sin(yaw_radians) * distance,
        "yawDegrees": float(pose["yawDegrees"]),
    }


def simulate_route(
    *,
    start_pose: Mapping[str, float],
    waypoints: Sequence[Mapping[str, Any]],
    max_steps: int = DEFAULT_MAX_STEPS,
    step_distance: float = DEFAULT_STEP_DISTANCE,
    turn_step_degrees: float = DEFAULT_TURN_STEP_DEGREES,
    alignment_threshold_degrees: float = DEFAULT_ALIGNMENT_THRESHOLD_DEGREES,
    minimum_progress_distance: float = DEFAULT_MINIMUM_PROGRESS_DISTANCE,
    wrong_way_tolerance_distance: float = DEFAULT_WRONG_WAY_TOLERANCE_DISTANCE,
    stuck_after_step: int | None = None,
) -> dict[str, Any]:
    pose = dict(start_pose)
    steps: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    arrived_waypoint_ids: list[str] = []
    last_route_status = "not-started"

    for step_number in range(1, max_steps + 1):
        active_index = active_waypoint_index(pose, waypoints)
        if active_index is None:
            last_route_status = "arrived"
            return {
                "status": "passed",
                "verdict": "offline-simulation-route-complete",
                "stepsRun": len(steps),
                "arrived": True,
                "lastRouteStatus": last_route_status,
                "arrivedWaypointIds": arrived_waypoint_ids,
                "finalPose": pose,
                "steps": steps,
                "blockers": [],
                "warnings": warnings,
                "errors": [],
            }

        waypoint = waypoints[active_index]
        initial_distance = planar_distance(pose, waypoint)
        bearing = bearing_to_waypoint(pose, waypoint)
        yaw_delta = normalize_degrees(bearing - float(pose["yawDegrees"]))
        abs_delta = abs(yaw_delta)
        within_alignment = abs_delta <= alignment_threshold_degrees
        action = "forward" if within_alignment else f"turn-{turn_direction(yaw_delta)}"
        before_pose = dict(pose)

        if action.startswith("turn-"):
            pose["yawDegrees"] = advance_yaw(float(pose["yawDegrees"]), yaw_delta, turn_step_degrees)
            final_distance = planar_distance(pose, waypoint)
            progress = initial_distance - final_distance
            route_status = "turning"
            stop_reason = "bearing-not-aligned"
        else:
            intended_distance = min(float(step_distance), max(0.0, initial_distance - float(waypoint["arrivalRadius"])))
            if stuck_after_step is not None and step_number >= stuck_after_step:
                next_pose = dict(pose)
            else:
                next_pose = forward_pose(pose, intended_distance)
            final_distance = planar_distance(next_pose, waypoint)
            progress = initial_distance - final_distance
            pose = next_pose
            if final_distance <= float(waypoint["arrivalRadius"]):
                route_status = "arrived"
                stop_reason = "within-arrival-radius"
                if str(waypoint["id"]) not in arrived_waypoint_ids:
                    arrived_waypoint_ids.append(str(waypoint["id"]))
            elif progress < -float(wrong_way_tolerance_distance):
                route_status = "wrong-way"
                stop_reason = "distance-increased-beyond-tolerance"
                blockers.append(f"step-{step_number}-wrong-way")
            elif progress < float(minimum_progress_distance):
                route_status = "no-progress"
                stop_reason = "minimum-progress-not-met"
                blockers.append(f"step-{step_number}-no-progress")
            else:
                route_status = "progress"
                stop_reason = "distance-decreased"

        last_route_status = route_status
        steps.append(
            {
                "stepNumber": step_number,
                "activeWaypointIndex": active_index,
                "activeWaypointId": waypoint["id"],
                "activeWaypointLabel": waypoint["label"],
                "action": action,
                "routeStatus": route_status,
                "stopReason": stop_reason,
                "initialPose": before_pose,
                "finalPose": dict(pose),
                "initialPlanarDistance": initial_distance,
                "finalPlanarDistance": final_distance,
                "progressDistance": progress,
                "bearingDegrees": bearing,
                "initialYawDeltaDegrees": yaw_delta,
                "absoluteInitialYawDeltaDegrees": abs_delta,
                "alignmentThresholdDegrees": alignment_threshold_degrees,
                "arrivalRadius": float(waypoint["arrivalRadius"]),
            }
        )

        if route_status in {"wrong-way", "no-progress"}:
            return {
                "status": "blocked",
                "verdict": "offline-simulation-route-blocked",
                "stepsRun": len(steps),
                "arrived": False,
                "lastRouteStatus": last_route_status,
                "arrivedWaypointIds": arrived_waypoint_ids,
                "finalPose": pose,
                "steps": steps,
                "blockers": sorted(set(blockers)),
                "warnings": warnings,
                "errors": [],
            }

    active_index = active_waypoint_index(pose, waypoints)
    if active_index is None:
        return {
            "status": "passed",
            "verdict": "offline-simulation-route-complete",
            "stepsRun": len(steps),
            "arrived": True,
            "lastRouteStatus": "arrived",
            "arrivedWaypointIds": arrived_waypoint_ids,
            "finalPose": pose,
            "steps": steps,
            "blockers": [],
            "warnings": warnings,
            "errors": [],
        }
    blockers.append("max-steps-reached-before-route-complete")
    return {
        "status": "blocked",
        "verdict": "offline-simulation-max-steps-reached",
        "stepsRun": len(steps),
        "arrived": False,
        "lastRouteStatus": last_route_status,
        "arrivedWaypointIds": arrived_waypoint_ids,
        "finalPose": pose,
        "steps": steps,
        "blockers": sorted(set(blockers)),
        "warnings": warnings,
        "errors": [],
    }


def validate_simulation_contract(summary: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if summary.get("kind") != KIND:
        blockers.append("simulation-kind-must-be-riftreader-navigation-offline-simulation")
    if summary.get("schemaVersion") != SCHEMA_VERSION:
        blockers.append("simulation-schema-version-must-be-1")
    if summary.get("status") not in {"passed", "blocked", "failed"}:
        blockers.append("simulation-status-invalid")
    safety = safe_mapping(summary.get("safety"))
    required_false = [
        "movementSent",
        "inputSent",
        "targetMemoryBytesRead",
        "targetMemoryBytesWritten",
        "providerWrites",
        "x64dbgAttach",
        "debuggerAttached",
        "gitMutation",
        "proofPromotion",
        "actorChainPromotion",
        "facingPromotion",
        "savedVariablesUsedAsLiveTruth",
    ]
    for key in required_false:
        if safety.get(key) is not False:
            blockers.append(f"safety-{key}-must-be-false")
    if safety.get("offlineSimulationOnly") is not True:
        blockers.append("safety-offline-simulation-only-must-be-true")
    if safety.get("routeControlAuthorized") is not False:
        blockers.append("safety-route-control-authorized-must-be-false")
    if not isinstance(summary.get("simulation"), Mapping):
        blockers.append("simulation-object-required")
    else:
        simulation = safe_mapping(summary.get("simulation"))
        steps = simulation.get("steps")
        if not isinstance(steps, list):
            blockers.append("simulation-steps-must-be-array")
        elif simulation.get("stepsRun") != len(steps):
            blockers.append("simulation-steps-run-must-match-step-count")
        if simulation.get("arrived") is True and simulation.get("lastRouteStatus") != "arrived":
            blockers.append("arrived-simulation-last-route-status-must-be-arrived")
    return {
        "status": "blocked" if blockers else "passed",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"navigation-offline-simulation-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    blockers: list[str] = validate_args(args)
    waypoints = waypoints_from_args(args, root, blockers) if not blockers else []
    start_pose = pose_from_args(args)
    safety = base_safety()
    safety.update(
        {
            "offlineSimulationOnly": True,
            "readOnlySavedJson": bool(args.waypoints_json),
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "routeControlAuthorized": False,
            "liveExecutionRequiresExplicitApproval": True,
        }
    )
    if blockers:
        simulation = {
            "status": "failed",
            "verdict": "offline-simulation-invalid-input",
            "stepsRun": 0,
            "arrived": False,
            "lastRouteStatus": "not-started",
            "arrivedWaypointIds": [],
            "finalPose": start_pose,
            "steps": [],
            "blockers": blockers,
            "warnings": [],
            "errors": [],
        }
    else:
        simulation = simulate_route(
            start_pose=start_pose,
            waypoints=waypoints,
            max_steps=int(args.max_steps),
            step_distance=float(args.step_distance),
            turn_step_degrees=float(args.turn_step_degrees),
            alignment_threshold_degrees=float(args.alignment_threshold_degrees),
            minimum_progress_distance=float(args.minimum_progress_distance),
            wrong_way_tolerance_distance=float(args.wrong_way_tolerance_distance),
            stuck_after_step=args.stuck_after_step,
        )
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": simulation["status"],
        "verdict": simulation["verdict"],
        "repoRoot": str(root),
        "input": {
            "startPose": start_pose,
            "waypointsJson": str(args.waypoints_json) if args.waypoints_json else None,
            "destination": None
            if args.waypoints_json
            else {
                "id": args.destination_id or "destination-001",
                "label": args.destination_label or args.destination_id or "Destination",
                "x": args.destination_x,
                "y": args.destination_y if args.destination_y is not None else args.start_y,
                "z": args.destination_z,
                "arrivalRadius": args.arrival_radius,
            },
            "stepDistance": args.step_distance,
            "turnStepDegrees": args.turn_step_degrees,
            "maxSteps": args.max_steps,
            "alignmentThresholdDegrees": args.alignment_threshold_degrees,
            "minimumProgressDistance": args.minimum_progress_distance,
            "wrongWayToleranceDistance": args.wrong_way_tolerance_distance,
            "stuckAfterStep": args.stuck_after_step,
        },
        "waypoints": waypoints,
        "simulation": simulation,
        "contract": {},
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
        "blockers": simulation.get("blockers", []),
        "warnings": simulation.get("warnings", []),
        "errors": simulation.get("errors", []),
    }
    contract = validate_simulation_contract(summary)
    summary["contract"] = contract
    if contract["status"] != "passed":
        summary["status"] = "blocked" if summary["status"] != "failed" else "failed"
        summary["blockers"] = sorted(set(summary["blockers"] + contract["blockers"]))
        summary["warnings"] = sorted(set(summary["warnings"] + contract["warnings"]))
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    simulation = safe_mapping(summary.get("simulation"))
    final_pose = safe_mapping(simulation.get("finalPose"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Navigation offline simulation",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Result",
        "",
        f"- Steps run: `{simulation.get('stepsRun')}`",
        f"- Arrived: `{simulation.get('arrived')}`",
        f"- Last route status: `{simulation.get('lastRouteStatus')}`",
        f"- Final pose: `x={final_pose.get('x')}, y={final_pose.get('y')}, z={final_pose.get('z')}, yaw={final_pose.get('yawDegrees')}`",
        "",
        "## Step trace",
        "",
        "| # | Action | Route status | Waypoint | Initial distance | Final distance | Progress | Yaw delta |",
        "|---:|---|---|---|---:|---:|---:|---:|",
    ]
    for step in simulation.get("steps", []):
        row = safe_mapping(step)
        lines.append(
            "| {step} | `{action}` | `{route_status}` | `{waypoint}` | {initial:.3f} | {final:.3f} | {progress:.3f} | {yaw:.3f} |".format(
                step=row.get("stepNumber"),
                action=row.get("action"),
                route_status=row.get("routeStatus"),
                waypoint=row.get("activeWaypointId"),
                initial=float(row.get("initialPlanarDistance") or 0.0),
                final=float(row.get("finalPlanarDistance") or 0.0),
                progress=float(row.get("progressDistance") or 0.0),
                yaw=float(row.get("initialYawDeltaDegrees") or 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "Offline simulation only. No target memory read, input, movement, debugger/CE, provider write, proof promotion, or route authorization.",
            "",
            "## Artifacts",
            "",
            f"- Summary JSON: `{artifacts.get('summaryJson')}`",
            f"- Run directory: `{artifacts.get('runDirectory')}`",
        ]
    )
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
    simulation = safe_mapping(summary.get("simulation"))
    artifacts = safe_mapping(summary.get("artifacts"))
    safety = safe_mapping(summary.get("safety"))
    final_pose = safe_mapping(simulation.get("finalPose"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "stepsRun": simulation.get("stepsRun"),
        "arrived": simulation.get("arrived"),
        "lastRouteStatus": simulation.get("lastRouteStatus"),
        "arrivedWaypointIds": simulation.get("arrivedWaypointIds"),
        "finalPose": final_pose,
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "targetMemoryBytesRead": safety.get("targetMemoryBytesRead"),
        "offlineSimulationOnly": safety.get("offlineSimulationOnly"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an offline navigation simulation with synthetic pose/waypoints")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--start-x", type=float, required=True)
    parser.add_argument("--start-y", type=float, default=0.0)
    parser.add_argument("--start-z", type=float, required=True)
    parser.add_argument("--start-yaw-degrees", type=float, required=True)
    parser.add_argument("--waypoints-json")
    parser.add_argument("--destination-id")
    parser.add_argument("--destination-label")
    parser.add_argument("--destination-x", type=float)
    parser.add_argument("--destination-y", type=float)
    parser.add_argument("--destination-z", type=float)
    parser.add_argument("--arrival-radius", type=float, default=DEFAULT_ARRIVAL_RADIUS)
    parser.add_argument("--step-distance", type=float, default=DEFAULT_STEP_DISTANCE)
    parser.add_argument("--turn-step-degrees", type=float, default=DEFAULT_TURN_STEP_DEGREES)
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--alignment-threshold-degrees", type=float, default=DEFAULT_ALIGNMENT_THRESHOLD_DEGREES)
    parser.add_argument("--minimum-progress-distance", type=float, default=DEFAULT_MINIMUM_PROGRESS_DISTANCE)
    parser.add_argument("--wrong-way-tolerance-distance", type=float, default=DEFAULT_WRONG_WAY_TOLERANCE_DISTANCE)
    parser.add_argument("--stuck-after-step", type=int)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    summary = build_summary(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    compact_summary = compact(summary)
    print(json.dumps(compact_summary) if args.json else json.dumps(compact_summary, indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
