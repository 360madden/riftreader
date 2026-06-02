from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .navigation_live_run_review import age_report, schema_validation
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from navigation_live_run_review import age_report, schema_validation  # type: ignore
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-live-run-command-plan"
COMMAND_PLAN_CONTRACT_VERSION = "navigation-live-run-command-plan/v1"
DEFAULT_MAX_REVIEW_AGE_SECONDS = 3600.0


def resolve_path(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def latest_live_run_review(root: Path) -> Path | None:
    capture_root = root / "scripts" / "captures"
    candidates = sorted(
        capture_root.glob("navigation-live-run-review-*/summary.json"),
        key=lambda item: item.stat().st_mtime_ns if item.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def source_package_path(root: Path, review_payload: Mapping[str, Any]) -> Path | None:
    path = safe_mapping(review_payload.get("review")).get("sourcePackageSummaryJson")
    return resolve_path(root, path) if path else None


def waypoint_readiness_path(root: Path, package_payload: Mapping[str, Any]) -> Path | None:
    input_payload = safe_mapping(package_payload.get("input"))
    path = input_payload.get("waypointReadinessJson")
    return resolve_path(root, path) if path else None


def normalized_waypoints_path(root: Path, package_payload: Mapping[str, Any], readiness_payload: Mapping[str, Any]) -> Path | None:
    input_payload = safe_mapping(package_payload.get("input"))
    explicit = input_payload.get("normalizedWaypointsJson")
    if explicit:
        return resolve_path(root, explicit)
    artifact = safe_mapping(readiness_payload.get("artifacts")).get("normalizedWaypointJson")
    return resolve_path(root, artifact) if artifact else None


def review_blockers(payload: Mapping[str, Any]) -> list[str]:
    review = safe_mapping(payload.get("review"))
    blockers: list[str] = []
    if payload.get("kind") != "riftreader-navigation-live-run-review":
        blockers.append(f"review-kind-not-supported:{payload.get('kind')}")
    if payload.get("status") != "passed":
        blockers.append(f"review-status-not-passed:{payload.get('status')}")
    if review.get("readyForSeparateLiveApproval") is not True:
        blockers.append("review-not-ready-for-separate-live-approval")
    if review.get("executionReviewApproved") is not False:
        blockers.append("review-execution-review-approved-must-be-false")
    if review.get("executionAuthorized") is not False:
        blockers.append("review-execution-authorized-must-be-false")
    if review.get("executionAttempted") is not False:
        blockers.append("review-execution-attempted-must-be-false")
    if review.get("routeRunnerInvoked") is not False:
        blockers.append("review-route-runner-invoked-must-be-false")
    return blockers


def source_package_blockers(payload: Mapping[str, Any]) -> list[str]:
    caps = safe_mapping(payload.get("capabilities"))
    blockers: list[str] = []
    if payload.get("kind") != "riftreader-navigation-downstream-package":
        blockers.append(f"source-package-kind-not-supported:{payload.get('kind')}")
    if payload.get("status") != "passed":
        blockers.append(f"source-package-status-not-passed:{payload.get('status')}")
    if caps.get("canQueueGatedLiveRunRequest") is not True:
        blockers.append("source-package-cannot-queue-gated-live-run-request")
    if caps.get("canExecuteLiveNavigation") is not False:
        blockers.append("source-package-live-execution-must-remain-false")
    return blockers


def load_optional_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return load_json_object(path)


def requested_mode(review_payload: Mapping[str, Any]) -> str:
    review = safe_mapping(review_payload.get("review"))
    request_path = review.get("requestSummaryJson")
    if request_path:
        try:
            request_payload = load_json_object(str(request_path))
            mode = safe_mapping(request_payload.get("request")).get("requestedMode")
            if isinstance(mode, str):
                return mode
        except Exception:
            return "unknown"
    return "unknown"


def command_templates(
    args: argparse.Namespace,
    *,
    root: Path,
    mode: str,
    normalized_waypoints: Path | None,
    next_waypoint_id: Any,
) -> dict[str, Any]:
    dry_run: list[str] | None = None
    execution: list[str] | None = None
    if mode == "continuous-route-run":
        if normalized_waypoints:
            dry_run = [
                "python",
                "scripts/static_owner_continuous_route_runner.py",
                "--waypoint-sequence-json",
                str(normalized_waypoints),
                "--dry-run",
                "--nav-state",
                "--json",
            ]
            execution = [
                "python",
                "scripts/static_owner_continuous_route_runner.py",
                "--waypoint-sequence-json",
                str(normalized_waypoints),
                "--turn-backend",
                str(args.turn_backend),
                "--mouse-pixels-per-pulse",
                str(int(args.mouse_pixels_per_pulse)),
                "--turn-approved",
                "--movement-approved",
                "--allow-candidate-turn-control",
                "--nav-state",
                "--json",
            ]
    elif mode == "single-route-step":
        if normalized_waypoints and isinstance(next_waypoint_id, str) and next_waypoint_id:
            dry_run = [
                "python",
                "scripts/static_owner_nav_route_step.py",
                "--destination-waypoint-json",
                str(normalized_waypoints),
                "--destination-waypoint-id",
                next_waypoint_id,
                "--dry-run",
                "--nav-state",
                "--json",
            ]
            execution = [
                "python",
                "scripts/static_owner_nav_route_step.py",
                "--destination-waypoint-json",
                str(normalized_waypoints),
                "--destination-waypoint-id",
                next_waypoint_id,
                "--movement-approved",
                "--nav-state",
                "--json",
            ]
    return {
        "mode": mode,
        "repoRoot": str(root),
        "normalizedWaypointsJson": str(normalized_waypoints) if normalized_waypoints else None,
        "nextWaypointId": next_waypoint_id if isinstance(next_waypoint_id, str) else None,
        "dryRunCommandTemplate": dry_run,
        "executionCommandTemplate": execution,
        "templateOnly": True,
        "approvalFlagsIncludedInTemplate": bool(execution),
        "approvalFlagsRequired": [
            "--movement-approved",
            "--turn-approved",
            "--allow-candidate-turn-control",
        ]
        if mode == "continuous-route-run"
        else ["--movement-approved"]
        if mode == "single-route-step"
        else [],
        "preflightRequirements": [
            "separate-explicit-live-movement-approval",
            "fresh-exact-target-static-chain-readback",
            "fresh-target-identity-check",
            "live-input-surface-audit-pass",
            "route-runner-gates-pass",
            "game-world-entry-available",
        ],
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    plan = safe_mapping(summary.get("commandPlan"))
    gate = safe_mapping(summary.get("executionGate"))
    lines = [
        "# Navigation live-run command plan",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        f"Plan ID: `{plan.get('planId')}`",
        f"Requested mode: `{plan.get('requestedMode')}`",
        "",
        "## Execution gate",
        "",
        f"- Command plan only: `{gate.get('commandPlanOnly')}`",
        f"- Execution authorized: `{gate.get('executionAuthorized')}`",
        f"- Execution attempted: `{gate.get('executionAttempted')}`",
        f"- Route runner invoked: `{gate.get('routeRunnerInvoked')}`",
        f"- Movement approved: `{gate.get('movementApproved')}`",
        "",
        "## Command templates",
        "",
        "Dry-run template:",
        "```json",
        json.dumps(plan.get("dryRunCommandTemplate"), indent=2),
        "```",
        "",
        "Execution template:",
        "```json",
        json.dumps(plan.get("executionCommandTemplate"), indent=2),
        "```",
        "",
        "Templates are not executed by this helper.",
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
    plan = safe_mapping(summary.get("commandPlan"))
    gate = safe_mapping(summary.get("executionGate"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "planId": plan.get("planId"),
        "requestedMode": plan.get("requestedMode"),
        "dryRunCommandTemplate": plan.get("dryRunCommandTemplate"),
        "executionCommandTemplate": plan.get("executionCommandTemplate"),
        "commandPlanOnly": gate.get("commandPlanOnly"),
        "executionAuthorized": gate.get("executionAuthorized"),
        "executionAttempted": gate.get("executionAttempted"),
        "routeRunnerInvoked": gate.get("routeRunnerInvoked"),
        "movementApproved": gate.get("movementApproved"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "targetMemoryBytesRead": safety.get("targetMemoryBytesRead"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"navigation-live-run-command-plan-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    review_path = resolve_path(root, args.live_run_review_json) if args.live_run_review_json else latest_live_run_review(root)

    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    schema_validations: list[dict[str, Any]] = []
    review_payload: dict[str, Any] = {}
    package_payload: dict[str, Any] = {}
    readiness_payload: dict[str, Any] = {}
    package_path: Path | None = None
    readiness_path: Path | None = None
    normalized_path: Path | None = None

    if review_path is None:
        errors.append("live-run-review-json-not-found")
    else:
        try:
            review_payload = load_json_object(review_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"live-run-review-load-failed:{type(exc).__name__}:{exc}")

    if review_payload:
        review_validation = schema_validation(
            root,
            label="live-run-review",
            schema_file="navigation-live-run-review.schema.json",
            payload=review_payload,
            input_json=review_path,
        )
        schema_validations.append(review_validation)
        if review_validation["status"] != "passed":
            blockers.append(f"live-run-review-schema-not-passed:{review_validation['status']}")
            blockers.extend(str(item) for item in review_validation.get("blockers", []))
        blockers.extend(review_blockers(review_payload))
        freshness = age_report(review_payload.get("generatedAtUtc"), max_age_seconds=float(args.max_review_age_seconds))
        if freshness["status"] == "unknown":
            blockers.append("review-generatedAtUtc-unparseable")
        elif not freshness["fresh"]:
            blockers.append(
                f"review-stale:ageSeconds={freshness['ageSeconds']:.3f};"
                f"maxAgeSeconds={freshness['maxAgeSeconds']}"
            )
        package_path = source_package_path(root, review_payload)
        if package_path is None:
            blockers.append("source-package-summary-json-missing")
        else:
            try:
                package_payload = load_json_object(package_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"source-package-load-failed:{type(exc).__name__}:{exc}")

    if package_payload:
        package_validation = schema_validation(
            root,
            label="source-package",
            schema_file="navigation-downstream-package.schema.json",
            payload=package_payload,
            input_json=package_path,
        )
        schema_validations.append(package_validation)
        if package_validation["status"] != "passed":
            blockers.append(f"source-package-schema-not-passed:{package_validation['status']}")
            blockers.extend(str(item) for item in package_validation.get("blockers", []))
        blockers.extend(source_package_blockers(package_payload))
        readiness_path = waypoint_readiness_path(root, package_payload)
        if readiness_path is None:
            blockers.append("waypoint-readiness-json-missing")
        else:
            try:
                readiness_payload = load_json_object(readiness_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"waypoint-readiness-load-failed:{type(exc).__name__}:{exc}")

    if readiness_payload:
        readiness_validation = schema_validation(
            root,
            label="waypoint-readiness",
            schema_file="navigation-waypoint-readiness.schema.json",
            payload=readiness_payload,
            input_json=readiness_path,
        )
        schema_validations.append(readiness_validation)
        if readiness_validation["status"] != "passed":
            blockers.append(f"waypoint-readiness-schema-not-passed:{readiness_validation['status']}")
            blockers.extend(str(item) for item in readiness_validation.get("blockers", []))
        normalized_path = normalized_waypoints_path(root, package_payload, readiness_payload)
        if normalized_path is None:
            blockers.append("normalized-waypoints-json-missing")
        elif not normalized_path.exists():
            blockers.append(f"normalized-waypoints-json-not-found:{normalized_path}")

    mode = requested_mode(review_payload)
    route_preview = safe_mapping(package_payload.get("routePreview"))
    next_waypoint_id = route_preview.get("nextWaypointId")
    plan_core = command_templates(
        args,
        root=root,
        mode=mode,
        normalized_waypoints=normalized_path,
        next_waypoint_id=next_waypoint_id,
    )
    if mode not in {"continuous-route-run", "single-route-step", "preview-only"}:
        blockers.append(f"requested-mode-not-supported:{mode}")
    if mode != "preview-only" and plan_core.get("executionCommandTemplate") is None:
        blockers.append("execution-command-template-not-buildable")

    if errors:
        status = "failed"
        verdict = "navigation-live-run-command-plan-failed"
    elif blockers:
        status = "blocked"
        verdict = "navigation-live-run-command-plan-blocked"
    else:
        status = "passed"
        verdict = "navigation-live-run-command-plan-ready-non-executable"

    command_plan = {
        "planId": str(args.plan_id or f"live-run-command-plan-{utc_stamp()}"),
        "reviewSummaryJson": str(review_path) if review_path else None,
        "sourcePackageSummaryJson": str(package_path) if package_path else None,
        "waypointReadinessSummaryJson": str(readiness_path) if readiness_path else None,
        "requestedMode": mode,
        **plan_core,
    }
    execution_gate = {
        "commandPlanOnly": True,
        "executionAuthorized": False,
        "executionAttempted": False,
        "routeRunnerInvoked": False,
        "movementApproved": False,
        "turnApproved": False,
        "candidateTurnControlAllowed": False,
        "requiresExplicitLiveMovementApproval": True,
        "gameWorldEntryAvailable": False if args.game_maintenance else None,
        "blockersBeforeExecution": [
            "game-maintenance-world-entry-unavailable"
        ]
        if args.game_maintenance
        else [],
    }
    if args.game_maintenance:
        warnings.append("game-maintenance-world-entry-unavailable-live-execution-not-possible")

    safety = base_safety()
    safety.update(
        {
            "readOnlySavedJson": True,
            "liveRunCommandPlanOnly": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "routeControlAuthorized": False,
            "routeRunnerInvoked": False,
        }
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "contractVersion": COMMAND_PLAN_CONTRACT_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(root),
        "input": {
            "liveRunReviewJson": str(review_path) if review_path else None,
            "maxReviewAgeSeconds": float(args.max_review_age_seconds),
            "planId": args.plan_id,
            "turnBackend": str(args.turn_backend),
            "mousePixelsPerPulse": int(args.mouse_pixels_per_pulse),
            "gameMaintenance": bool(args.game_maintenance),
        },
        "commandPlan": command_plan,
        "executionGate": execution_gate,
        "schemaValidations": schema_validations,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a non-executing command plan from a reviewed navigation live-run request")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--live-run-review-json", help="Saved live-run review summary; defaults to newest")
    parser.add_argument("--plan-id")
    parser.add_argument("--max-review-age-seconds", type=float, default=DEFAULT_MAX_REVIEW_AGE_SECONDS)
    parser.add_argument("--turn-backend", choices=("key", "mouse-look"), default="mouse-look")
    parser.add_argument("--mouse-pixels-per-pulse", type=int, default=40)
    parser.add_argument("--game-maintenance", action="store_true", help="Annotate that world entry is currently unavailable")
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
