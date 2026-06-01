#!/usr/bin/env python3
"""Package route-forward passes into a formal candidate-facing three-pose gate.

This helper is report-only: it consumes existing `static-owner-nav-route-step`
summary JSON files and writes a durable JSON/Markdown packet.  It does not send
input, read target memory, attach debuggers, promote truth, or mutate Git state.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
DEFAULT_MINIMUM_PROGRESS_DISTANCE = 0.5
DEFAULT_MINIMUM_POSE_COUNT = 3
PASS_ROUTE_STATUSES = {"progress", "arrived"}
PASS_ROUTE_STEP_VERDICTS = {
    "route-step-live-movement-progress-validated",
    "route-step-live-arrived",
}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_under_repo(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def repo_rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def route_summary_for_pose(root: Path, step_summary: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
    artifacts = safe_mapping(step_summary.get("artifacts"))
    route_summary_json = artifacts.get("routeSummaryJson")
    if not route_summary_json:
        return {}, "route-summary-json-missing"
    path = resolve_under_repo(root, str(route_summary_json))
    if not path.is_file():
        return {}, f"route-summary-json-not-found:{path}"
    try:
        return load_json_object(path), None
    except Exception as exc:  # noqa: BLE001 - packet must capture malformed source artifacts.
        return {}, f"route-summary-json-malformed:{path}:{type(exc).__name__}:{exc}"


def summarize_pose(root: Path, path: Path, data: Mapping[str, Any], *, minimum_progress_distance: float) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    kind = data.get("kind")
    status = data.get("status")
    verdict = data.get("verdict")
    if kind != "static-owner-nav-route-step":
        blockers.append(f"route-step-kind-mismatch:{kind}")
    if status != "passed":
        blockers.append(f"route-step-status-not-passed:{status}")
    if verdict not in PASS_ROUTE_STEP_VERDICTS:
        blockers.append(f"route-step-verdict-not-three-pose-eligible:{verdict}")

    route_result = safe_mapping(data.get("routeResult"))
    route_status = route_result.get("routeStatus")
    if route_status not in PASS_ROUTE_STATUSES:
        blockers.append(f"route-status-not-progress-or-arrived:{route_status}")

    initial_distance = numeric(route_result.get("initialPlanarDistance"))
    final_distance = numeric(route_result.get("finalPlanarDistance"))
    progress_distance = numeric(route_result.get("totalProgressDistance"))
    if progress_distance is None:
        blockers.append("route-progress-distance-missing")
    elif route_status != "arrived" and progress_distance < minimum_progress_distance:
        blockers.append(f"route-progress-below-minimum:{progress_distance}<{minimum_progress_distance}")
    if initial_distance is None or final_distance is None:
        blockers.append("route-initial-or-final-distance-missing")
    elif final_distance >= initial_distance and route_status != "arrived":
        blockers.append(f"route-distance-did-not-decrease:{final_distance}>={initial_distance}")

    initial_decision = safe_mapping(data.get("initialDecision"))
    if initial_decision.get("suggestedTurnDirection") != "aligned":
        blockers.append(f"initial-bearing-not-aligned:{initial_decision.get('suggestedTurnDirection')}")
    if initial_decision.get("navStateAvailable") is not True:
        blockers.append("initial-nav-state-not-available")
    facing_target_coordinate = safe_mapping(initial_decision.get("navStateFacingTargetCoordinate"))
    if not facing_target_coordinate:
        blockers.append("initial-facing-target-coordinate-missing")

    route_summary, route_summary_error = route_summary_for_pose(root, data)
    if route_summary_error:
        blockers.append(route_summary_error)
    navigation_request = safe_mapping(route_summary.get("navigationTargetRequest"))
    destination_label = navigation_request.get("destinationLabel")
    if not str(destination_label or "").startswith("current-facing-target-0x30C"):
        blockers.append(f"destination-label-not-current-facing-target-0x30C:{destination_label}")
    route_safety = safe_mapping(route_summary.get("safety"))
    if route_safety and route_safety.get("targetMemoryBytesRead") is not True:
        warnings.append("route-summary-target-memory-read-flag-not-true")

    safety = safe_mapping(data.get("safety"))
    if safety.get("movementSent") is not True:
        blockers.append("source-route-step-movement-not-sent")
    if safety.get("inputSent") is not True:
        blockers.append("source-route-step-input-not-sent")
    for forbidden_flag in ("proofPromotion", "actorChainPromotion", "facingPromotion", "providerWrites"):
        if safety.get(forbidden_flag):
            blockers.append(f"source-route-step-forbidden-flag:{forbidden_flag}")

    artifacts = safe_mapping(data.get("artifacts"))
    return {
        "summaryJson": repo_rel(root, path),
        "status": status,
        "kind": kind,
        "verdict": verdict,
        "generatedAtUtc": data.get("generatedAtUtc"),
        "routeStatus": route_status,
        "progressDistance": progress_distance,
        "initialPlanarDistance": initial_distance,
        "finalPlanarDistance": final_distance,
        "initialDecision": {
            "suggestedTurnDirection": initial_decision.get("suggestedTurnDirection"),
            "absoluteBearingDeltaDegrees": initial_decision.get("absoluteBearingDeltaDegrees"),
            "navStateYawDegrees": initial_decision.get("navStateYawDegrees"),
            "navStateFacingTargetCoordinate": facing_target_coordinate,
        },
        "destination": {
            "label": destination_label,
            "x": navigation_request.get("destinationX"),
            "y": navigation_request.get("destinationY"),
            "z": navigation_request.get("destinationZ"),
            "arrivalRadius": navigation_request.get("arrivalRadius"),
        },
        "artifacts": {
            "preStateSummaryJson": artifacts.get("preStateSummaryJson"),
            "postStateSummaryJson": artifacts.get("postStateSummaryJson"),
            "routeSummaryJson": artifacts.get("routeSummaryJson"),
            "routeContractSummaryJson": artifacts.get("routeContractSummaryJson"),
        },
        "sourceSafety": {
            "movementSent": bool(safety.get("movementSent")),
            "inputSent": bool(safety.get("inputSent")),
            "targetMemoryBytesRead": bool(route_safety.get("targetMemoryBytesRead")),
            "targetMemoryBytesWritten": bool(safety.get("targetMemoryBytesWritten")),
            "proofPromotion": bool(safety.get("proofPromotion")),
            "facingPromotion": bool(safety.get("facingPromotion")),
        },
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "eligible": not blockers,
    }


def build_three_pose_gate(args: argparse.Namespace, root: Path, run_dir: Path) -> tuple[dict[str, Any], int]:
    requested_paths = [resolve_under_repo(root, Path(str(item))) for item in args.route_step_summary_json or []]
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "facing-target-three-pose-gate",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "verdict": "three-pose-gate-not-built",
        "repoRoot": str(root),
        "runDirectory": str(run_dir),
        "sourceCount": len(requested_paths),
        "poseCount": 0,
        "passedPoseCount": 0,
        "minimums": {
            "minimumPoseCount": args.minimum_pose_count,
            "minimumProgressDistance": args.minimum_progress_distance,
        },
        "poses": [],
        "analysis": {
            "candidateOnly": True,
            "promotionAllowed": False,
            "formalThreePoseGatePassed": False,
            "restartRelogSurvived": False,
        },
        "promotionReadinessInputs": {
            "threePoseRouteStepSummaries": [],
            "threePoseGateSummaryJson": str(run_dir / "summary.json"),
            "restartRelogSurvivalPacket": None,
            "staticRootSourceSiteProof": None,
            "promotionReviewRequired": True,
        },
        "blockers": [],
        "warnings": ["report-only-no-live-input-sent", "candidate-facing-target-only-no-promotion"],
        "errors": [],
        "safety": {
            **base_safety(),
            "reportOnly": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        },
        "sourceSafety": {
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        },
        "artifacts": {
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
        "next": {
            "recommendedAction": "Build restart/relog survival and static-root source-site proof packets before any facing promotion review.",
            "recommendedActions": [
                "Build restart/relog survival packet from pre/post-restart nav-state summaries.",
                "Attach static-root/source-site proof for owner+0x30C/+0x310/+0x314 and promoted +0x320/+0x324/+0x328.",
                "Run a separate proof/promotion review; this packet never promotes candidate facing truth.",
            ],
        },
    }

    if not requested_paths:
        summary["status"] = "blocked"
        summary["verdict"] = "route-step-summary-json-required"
        summary["blockers"].append("route-step-summary-json-required")
        return summary, 2

    try:
        for path in requested_paths:
            if not path.is_file():
                summary["blockers"].append(f"route-step-summary-not-found:{path}")
                continue
            try:
                data = load_json_object(path)
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append(f"route-step-summary-malformed:{path}:{type(exc).__name__}:{exc}")
                continue
            pose = summarize_pose(root, path, data, minimum_progress_distance=args.minimum_progress_distance)
            summary["poses"].append(pose)
            summary["promotionReadinessInputs"]["threePoseRouteStepSummaries"].append(repo_rel(root, path))
            source_safety = safe_mapping(pose.get("sourceSafety"))
            for key in summary["sourceSafety"]:
                summary["sourceSafety"][key] = bool(summary["sourceSafety"][key]) or bool(source_safety.get(key))

        summary["poseCount"] = len(summary["poses"])
        eligible_poses = [pose for pose in summary["poses"] if pose.get("eligible")]
        summary["passedPoseCount"] = len(eligible_poses)
        for index, pose in enumerate(summary["poses"], start=1):
            for blocker in safe_list(pose.get("blockers")):
                summary["blockers"].append(f"pose-{index}:{blocker}")
            for warning in safe_list(pose.get("warnings")):
                summary["warnings"].append(f"pose-{index}:{warning}")

        progress_distances = [numeric(pose.get("progressDistance")) for pose in eligible_poses]
        progress_distances = [item for item in progress_distances if item is not None]
        destination_labels = sorted({str(safe_mapping(pose.get("destination")).get("label")) for pose in eligible_poses})
        route_statuses = sorted({str(pose.get("routeStatus")) for pose in eligible_poses})
        labels_are_facing_target = bool(destination_labels) and all(
            str(label).startswith("current-facing-target-0x30C") for label in destination_labels
        )
        summary["analysis"].update(
            {
                "routeStatuses": route_statuses,
                "destinationLabels": destination_labels,
                "aggregateProgressDistance": sum(progress_distances),
                "minimumProgressDistance": min(progress_distances) if progress_distances else None,
                "maximumProgressDistance": max(progress_distances) if progress_distances else None,
                "candidateFacingTargetOffset": "0x30C" if labels_are_facing_target else None,
                "supportOnlyTurnRateOffset": "0x304",
            }
        )
        if summary["passedPoseCount"] < args.minimum_pose_count:
            summary["blockers"].append(f"eligible-pose-count-below-minimum:{summary['passedPoseCount']}<{args.minimum_pose_count}")

        if summary["errors"]:
            summary["status"] = "failed"
            summary["verdict"] = "three-pose-gate-error"
            exit_code = 1
        elif summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "three-pose-gate-blocked"
            exit_code = 2
        else:
            summary["status"] = "passed"
            summary["verdict"] = "formal-three-pose-route-progress-gate-passed"
            summary["analysis"]["formalThreePoseGatePassed"] = True
            exit_code = 0

        summary["blockers"] = sorted(set(str(item) for item in summary["blockers"]))
        summary["warnings"] = sorted(set(str(item) for item in summary["warnings"]))
        summary["errors"] = sorted(set(str(item) for item in summary["errors"]))
        return summary, exit_code
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "three-pose-gate-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        return summary, 1


def build_markdown(summary: Mapping[str, Any]) -> str:
    analysis = safe_mapping(summary.get("analysis"))
    lines = [
        "# Facing-target three-pose route-progress gate",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Run directory: `{summary.get('runDirectory')}`",
        f"- Pose count: `{summary.get('poseCount')}`",
        f"- Passed pose count: `{summary.get('passedPoseCount')}`",
        f"- Formal three-pose gate passed: `{analysis.get('formalThreePoseGatePassed')}`",
        f"- Promotion allowed: `{analysis.get('promotionAllowed')}`",
        "",
        "## Poses",
        "",
        "| # | Route status | Progress | Initial distance | Final distance | Destination label | Eligible |",
        "|---:|---|---:|---:|---:|---|---:|",
    ]
    for index, pose_value in enumerate(safe_list(summary.get("poses")), start=1):
        pose = safe_mapping(pose_value)
        destination = safe_mapping(pose.get("destination"))
        lines.append(
            f"| {index} | `{pose.get('routeStatus')}` | `{pose.get('progressDistance')}` | "
            f"`{pose.get('initialPlanarDistance')}` | `{pose.get('finalPlanarDistance')}` | "
            f"`{destination.get('label')}` | `{pose.get('eligible')}` |"
        )
    if not safe_list(summary.get("poses")):
        lines.append("| none |  |  |  |  |  |  |")
    lines.extend(["", "## Analysis", ""])
    for key, value in analysis.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Promotion readiness inputs", ""])
    for key, value in safe_mapping(summary.get("promotionReadinessInputs")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Blockers", ""])
    for item in safe_list(summary.get("blockers")) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Warnings", ""])
    for item in safe_list(summary.get("warnings")) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Errors", ""])
    for item in safe_list(summary.get("errors")) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Safety", "", "| Flag | Value |", "|---|---:|"])
    for key, value in safe_mapping(summary.get("safety")).items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Next", ""])
    for item in safe_list(safe_mapping(summary.get("next")).get("recommendedActions")):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(summary: dict[str, Any]) -> None:
    artifacts = safe_mapping(summary.get("artifacts"))
    summary_json = Path(str(artifacts.get("summaryJson")))
    summary_md = Path(str(artifacts.get("summaryMarkdown")))
    write_json(summary_json, summary)
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text(build_markdown(summary), encoding="utf-8")


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    analysis = safe_mapping(summary.get("analysis"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "poseCount": summary.get("poseCount"),
        "passedPoseCount": summary.get("passedPoseCount"),
        "formalThreePoseGatePassed": analysis.get("formalThreePoseGatePassed"),
        "promotionAllowed": analysis.get("promotionAllowed"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
        "safety": summary.get("safety", {}),
        "sourceSafety": summary.get("sourceSafety", {}),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=Path("scripts") / "captures")
    parser.add_argument("--route-step-summary-json", nargs="+", help="Existing static-owner-nav-route-step summary JSON files.")
    parser.add_argument("--minimum-progress-distance", type=float, default=DEFAULT_MINIMUM_PROGRESS_DISTANCE)
    parser.add_argument("--minimum-pose-count", type=int, default=DEFAULT_MINIMUM_POSE_COUNT)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def self_test_payload() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_name:
        root = Path(temp_name)
        route_summary_paths: list[str] = []
        for index in range(3):
            route_dir = root / "scripts" / "captures" / f"route-{index}"
            step_dir = root / "scripts" / "captures" / f"step-{index}"
            route_summary = {
                "kind": "static-owner-nav-route",
                "status": "passed",
                "navigationTargetRequest": {
                    "destinationLabel": "current-facing-target-0x30C",
                    "destinationX": 10 + index,
                    "destinationY": 2,
                    "destinationZ": 20 + index,
                    "arrivalRadius": 2.5,
                },
                "safety": {"targetMemoryBytesRead": True},
            }
            route_summary_path = route_dir / "summary.json"
            write_json(route_summary_path, route_summary)
            step_summary = {
                "kind": "static-owner-nav-route-step",
                "status": "passed",
                "verdict": "route-step-live-movement-progress-validated",
                "generatedAtUtc": "2026-06-01T00:00:00Z",
                "initialDecision": {
                    "suggestedTurnDirection": "aligned",
                    "absoluteBearingDeltaDegrees": 0.0,
                    "navStateAvailable": True,
                    "navStateYawDegrees": 49.0,
                    "navStateFacingTargetCoordinate": {"x": 10 + index, "y": 2, "z": 20 + index},
                },
                "routeResult": {
                    "routeStatus": "progress",
                    "totalProgressDistance": 1.0,
                    "initialPlanarDistance": 10.0,
                    "finalPlanarDistance": 9.0,
                },
                "safety": {"movementSent": True, "inputSent": True, "noCheatEngine": True},
                "artifacts": {"routeSummaryJson": str(route_summary_path)},
            }
            step_summary_path = step_dir / "summary.json"
            write_json(step_summary_path, step_summary)
            route_summary_paths.append(str(step_summary_path))

        args = argparse.Namespace(
            route_step_summary_json=route_summary_paths,
            minimum_progress_distance=0.5,
            minimum_pose_count=3,
        )
        summary, _ = build_three_pose_gate(args, root, root / "scripts" / "captures" / "facing-target-three-pose-gate-self-test")
    return {
        "status": "passed" if summary.get("status") == "passed" else "failed",
        "checks": {
            "gatePassed": summary.get("status") == "passed",
            "poseCount": summary.get("poseCount"),
            "promotionAllowed": safe_mapping(summary.get("analysis")).get("promotionAllowed"),
            "helperInputSent": safe_mapping(summary.get("safety")).get("inputSent"),
        },
        "safety": summary.get("safety", {}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        payload = self_test_payload()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"self-test:{payload['status']}")
        return 0 if payload.get("status") == "passed" else 1

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = resolve_under_repo(root, Path(args.output_root))
    run_dir = output_root / f"facing-target-three-pose-gate-{utc_stamp()}"
    summary, exit_code = build_three_pose_gate(args, root, run_dir)
    write_outputs(summary)
    if args.json:
        print(json.dumps(compact(summary), indent=2))
    else:
        print(f"{summary['status']}: {safe_mapping(summary.get('artifacts')).get('summaryMarkdown')}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
