from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .navigation_consumer_refresh import DEFAULT_COMMAND_TIMEOUT_SECONDS, DEFAULT_CONSUMER_STATE_OUTPUT_DIR
    from .workflow_common import base_safety, repo_root, run_child, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from navigation_consumer_refresh import DEFAULT_COMMAND_TIMEOUT_SECONDS, DEFAULT_CONSUMER_STATE_OUTPUT_DIR  # type: ignore
    from workflow_common import base_safety, repo_root, run_child, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-downstream-package"
DEFAULT_MAX_CONSUMER_STATE_AGE_SECONDS = 30.0


def _resolve_path(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def _optional_arg(command: list[str], flag: str, value: str | Path | None, root: Path) -> None:
    resolved = _resolve_path(root, value)
    if resolved is not None:
        command.extend([flag, str(resolved)])


def _consumer_refresh_command(args: argparse.Namespace, root: Path, output_root: Path) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "navigation_consumer_refresh.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--current-truth-json",
        str(_resolve_path(root, args.current_truth_json)),
        "--consumer-state-output-dir",
        str(_resolve_path(root, args.consumer_state_output_dir)),
        "--max-consumer-state-age-seconds",
        str(float(args.max_consumer_state_age_seconds)),
        "--command-timeout-seconds",
        str(float(args.command_timeout_seconds)),
        "--json",
    ]
    _optional_arg(command, "--waypoint-readiness-json", args.waypoint_readiness_json, root)
    _optional_arg(command, "--normalized-waypoints-json", args.normalized_waypoints_json, root)
    _optional_arg(command, "--sequence-summary-json", args.sequence_summary_json, root)
    _optional_arg(command, "--contract-report-json", args.contract_report_json, root)
    if args.pid is not None:
        command.extend(["--pid", str(int(args.pid))])
    if args.hwnd:
        command.extend(["--hwnd", str(args.hwnd)])
    if args.module_base:
        command.extend(["--module-base", str(args.module_base)])
    if args.process_name:
        command.extend(["--process-name", str(args.process_name)])
    if args.require_fresh_pose:
        command.append("--require-fresh-pose")
    return command


def _route_preview_command(
    args: argparse.Namespace,
    root: Path,
    output_root: Path,
    *,
    consumer_state_json: str,
) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "navigation_route_preview.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--consumer-state-json",
        consumer_state_json,
        "--max-consumer-state-age-seconds",
        str(float(args.max_consumer_state_age_seconds)),
        "--alignment-threshold-degrees",
        str(float(args.alignment_threshold_degrees)),
        "--json",
    ]
    _optional_arg(command, "--waypoint-readiness-json", args.waypoint_readiness_json, root)
    _optional_arg(command, "--normalized-waypoints-json", args.normalized_waypoints_json, root)
    if args.require_fresh_pose:
        command.append("--require-fresh-pose")
    return command


def _schema_validate_command(root: Path, output_root: Path, input_json: str) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "navigation_schema_validate.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--input",
        input_json,
        "--json",
    ]


def _child_json(child: Mapping[str, Any]) -> dict[str, Any]:
    return safe_mapping(child.get("json"))


def _status_from_child(child: Mapping[str, Any]) -> str | None:
    return _child_json(child).get("status")


def _validation_summary(child: Mapping[str, Any]) -> dict[str, Any]:
    payload = _child_json(child)
    return {
        "label": child.get("label"),
        "status": payload.get("status"),
        "inputJson": payload.get("inputJson"),
        "inputKind": payload.get("inputKind"),
        "schemaKey": payload.get("schemaKey"),
        "validationStatus": payload.get("validationStatus"),
        "validationErrorCount": payload.get("validationErrorCount"),
        "summaryJson": payload.get("summaryJson"),
        "summaryMarkdown": payload.get("summaryMarkdown"),
        "exitCode": child.get("exitCode"),
        "blockers": payload.get("blockers", []),
        "warnings": payload.get("warnings", []),
        "errors": payload.get("errors", []),
    }


def build_capabilities(
    *,
    consumer_refresh: Mapping[str, Any],
    route_preview: Mapping[str, Any],
    schema_ok: bool,
) -> dict[str, Any]:
    can_render_route = consumer_refresh.get("canRenderRoute") is True
    can_use_dry_run = consumer_refresh.get("canUseDryRunContract") is True
    can_render_preview = route_preview.get("canRenderRoutePreview") is True
    can_use_preview = route_preview.get("canUseRoutePreview") is True
    can_queue = (
        schema_ok
        and consumer_refresh.get("canQueueGatedLiveRunRequest") is True
        and route_preview.get("canQueueGatedLiveRunRequest") is True
    )
    if not schema_ok:
        mode = "blocked-schema-invalid"
        action = "Regenerate package artifacts until every saved JSON schema validation passes."
    elif not can_render_route or not can_render_preview:
        mode = "blocked-render-artifacts-missing"
        action = "Regenerate waypoint readiness, consumer refresh, and route preview before downstream consumption."
    elif not can_use_dry_run or not can_use_preview:
        mode = "render-ready-dry-run-or-preview-blocked"
        action = "Use render-only data and regenerate the blocked contract or preview before queueing live navigation."
    elif not can_queue:
        mode = "package-ready-refresh-pose-before-live-queue"
        action = "Render package data, then refresh the package again before queueing a gated live-run request."
    else:
        mode = "package-ready-live-run-request-gated"
        action = "External consumer may render, use preview/dry-run data, and queue a gated live-run request; execution still needs explicit live movement approval."
    return {
        "canRenderRoute": can_render_route,
        "canUseDryRunContract": can_use_dry_run,
        "canRenderRoutePreview": can_render_preview,
        "canUseRoutePreview": can_use_preview,
        "canQueueGatedLiveRunRequest": can_queue,
        "canExecuteLiveNavigation": False,
        "liveExecutionRequiresExplicitApproval": True,
        "recommendedMode": mode,
        "nextRecommendedAction": action,
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    caps = safe_mapping(summary.get("capabilities"))
    refresh = safe_mapping(summary.get("consumerRefresh"))
    route = safe_mapping(summary.get("routePreview"))
    lines = [
        "# Navigation downstream package",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Bundle",
        "",
        f"- Consumer refresh: `{refresh.get('summaryJson')}`",
        f"- Consumer demo: `{refresh.get('consumerDemoSummaryJson')}`",
        f"- Consumer state: `{refresh.get('consumerStateSummaryJson')}`",
        f"- Route preview: `{route.get('summaryJson')}`",
        "",
        "## Capability decision",
        "",
        f"- Can render route: `{caps.get('canRenderRoute')}`",
        f"- Can use dry-run contract: `{caps.get('canUseDryRunContract')}`",
        f"- Can render route preview: `{caps.get('canRenderRoutePreview')}`",
        f"- Can queue gated live-run request: `{caps.get('canQueueGatedLiveRunRequest')}`",
        f"- Can execute live navigation: `{caps.get('canExecuteLiveNavigation')}`",
        f"- Recommended mode: `{caps.get('recommendedMode')}`",
        f"- Next action: `{caps.get('nextRecommendedAction')}`",
        "",
        "## Schema validations",
        "",
    ]
    for item in summary.get("schemaValidations", []):
        if isinstance(item, Mapping):
            lines.append(
                f"- `{item.get('label')}`: `{item.get('status')}` "
                f"schema=`{item.get('schemaKey')}` errors=`{item.get('validationErrorCount')}`"
            )
    lines.extend(["", "No input, movement, route execution, debugger/CE, provider write, or promotion is authorized."])
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
    caps = safe_mapping(summary.get("capabilities"))
    refresh = safe_mapping(summary.get("consumerRefresh"))
    route = safe_mapping(summary.get("routePreview"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "recommendedMode": caps.get("recommendedMode"),
        "nextRecommendedAction": caps.get("nextRecommendedAction"),
        "consumerRefreshSummaryJson": refresh.get("summaryJson"),
        "consumerDemoSummaryJson": refresh.get("consumerDemoSummaryJson"),
        "consumerStateSummaryJson": refresh.get("consumerStateSummaryJson"),
        "routePreviewSummaryJson": route.get("summaryJson"),
        "canRenderRoute": caps.get("canRenderRoute"),
        "canUseDryRunContract": caps.get("canUseDryRunContract"),
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


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"navigation-downstream-package-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    safety = base_safety()
    safety.update(
        {
            "downstreamPackageOnly": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "routeControlAuthorized": False,
        }
    )
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "verdict": "navigation-downstream-package-pending",
        "repoRoot": str(root),
        "input": {
            "currentTruthJson": str(_resolve_path(root, args.current_truth_json)),
            "consumerStateOutputDir": str(_resolve_path(root, args.consumer_state_output_dir)),
            "waypointReadinessJson": str(_resolve_path(root, args.waypoint_readiness_json))
            if args.waypoint_readiness_json
            else None,
            "normalizedWaypointsJson": str(_resolve_path(root, args.normalized_waypoints_json))
            if args.normalized_waypoints_json
            else None,
            "maxConsumerStateAgeSeconds": float(args.max_consumer_state_age_seconds),
            "alignmentThresholdDegrees": float(args.alignment_threshold_degrees),
            "requireFreshPose": bool(args.require_fresh_pose),
        },
        "consumerRefresh": {},
        "routePreview": {},
        "schemaValidations": [],
        "capabilities": build_capabilities(consumer_refresh={}, route_preview={}, schema_ok=False),
        "childCommands": [],
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }

    try:
        refresh_child = run_child(
            label="consumer-refresh",
            command=_consumer_refresh_command(args, root, run_dir / "consumer-refresh"),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(refresh_child)
        refresh_json = _child_json(refresh_child)
        summary["consumerRefresh"] = {
            "status": refresh_json.get("status"),
            "verdict": refresh_json.get("verdict"),
            "summaryJson": refresh_json.get("summaryJson"),
            "summaryMarkdown": refresh_json.get("summaryMarkdown"),
            "consumerStateSummaryJson": refresh_json.get("consumerStateSummaryJson"),
            "consumerDemoSummaryJson": refresh_json.get("consumerDemoSummaryJson"),
            "canRenderRoute": refresh_json.get("canRenderRoute"),
            "canUseDryRunContract": refresh_json.get("canUseDryRunContract"),
            "canQueueGatedLiveRunRequest": refresh_json.get("canQueueGatedLiveRunRequest"),
            "canExecuteLiveNavigation": refresh_json.get("canExecuteLiveNavigation"),
            "exitCode": refresh_child.get("exitCode"),
        }
        safety["targetMemoryBytesRead"] = bool(refresh_json.get("targetMemoryBytesRead"))
        summary["warnings"].extend(str(item) for item in refresh_json.get("warnings", []) if item)
        summary["blockers"].extend(str(item) for item in refresh_json.get("blockers", []) if item)
        summary["errors"].extend(str(item) for item in refresh_json.get("errors", []) if item)
        if refresh_child.get("exitCode") == 1 or refresh_json.get("status") == "failed":
            summary["errors"].append("consumer-refresh-failed")
            summary["status"] = "failed"
            summary["verdict"] = "navigation-downstream-package-failed"
            return summary
        if refresh_child.get("exitCode") != 0 or refresh_json.get("status") != "passed":
            summary["blockers"].append(f"consumer-refresh-not-passed:{refresh_json.get('status')}")
            summary["status"] = "blocked"
            summary["verdict"] = "navigation-downstream-package-blocked"
            return summary

        consumer_state_summary = str(refresh_json.get("consumerStateSummaryJson") or "")
        if not consumer_state_summary:
            summary["errors"].append("consumer-state-summary-json-missing")
            summary["status"] = "failed"
            summary["verdict"] = "navigation-downstream-package-failed"
            return summary

        route_child = run_child(
            label="route-preview",
            command=_route_preview_command(
                args,
                root,
                run_dir / "route-preview",
                consumer_state_json=consumer_state_summary,
            ),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(route_child)
        route_json = _child_json(route_child)
        summary["routePreview"] = {
            "status": route_json.get("status"),
            "verdict": route_json.get("verdict"),
            "summaryJson": route_json.get("summaryJson"),
            "summaryMarkdown": route_json.get("summaryMarkdown"),
            "waypointCount": route_json.get("waypointCount"),
            "legCount": route_json.get("legCount"),
            "routeComplete": route_json.get("routeComplete"),
            "nextWaypointId": route_json.get("nextWaypointId"),
            "activeLegPlanarDistance": route_json.get("activeLegPlanarDistance"),
            "activeLegBearingDegrees": route_json.get("activeLegBearingDegrees"),
            "activeLegInitialYawDeltaDegrees": route_json.get("activeLegInitialYawDeltaDegrees"),
            "activeLegSuggestedInitialTurnDirection": route_json.get("activeLegSuggestedInitialTurnDirection"),
            "canRenderRoutePreview": route_json.get("canRenderRoutePreview"),
            "canUseRoutePreview": route_json.get("canUseRoutePreview"),
            "canQueueGatedLiveRunRequest": route_json.get("canQueueGatedLiveRunRequest"),
            "canExecuteLiveNavigation": route_json.get("canExecuteLiveNavigation"),
            "exitCode": route_child.get("exitCode"),
        }
        summary["warnings"].extend(str(item) for item in route_json.get("warnings", []) if item)
        summary["blockers"].extend(str(item) for item in route_json.get("blockers", []) if item)
        summary["errors"].extend(str(item) for item in route_json.get("errors", []) if item)

        schema_inputs = [
            ("schema-consumer-state", refresh_json.get("consumerStateSummaryJson")),
            ("schema-consumer-demo", refresh_json.get("consumerDemoSummaryJson")),
            ("schema-consumer-refresh", refresh_json.get("summaryJson")),
            ("schema-route-preview", route_json.get("summaryJson")),
        ]
        for label, input_json in schema_inputs:
            if not input_json:
                summary["errors"].append(f"{label}-input-json-missing")
                continue
            schema_child = run_child(
                label=label,
                command=_schema_validate_command(root, run_dir / "schema-validation", str(input_json)),
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=float(args.command_timeout_seconds),
            )
            summary["childCommands"].append(schema_child)
            validation = _validation_summary(schema_child)
            summary["schemaValidations"].append(validation)
            summary["warnings"].extend(str(item) for item in validation.get("warnings", []) if item)
            summary["errors"].extend(str(item) for item in validation.get("errors", []) if item)
            if schema_child.get("exitCode") == 1 or validation.get("status") == "failed":
                summary["errors"].append(f"{label}-failed")
            elif schema_child.get("exitCode") != 0 or validation.get("validationStatus") != "passed":
                summary["blockers"].append(f"{label}-not-passed:{validation.get('validationStatus')}")
                summary["blockers"].extend(str(item) for item in validation.get("blockers", []) if item)

        schema_ok = all(item.get("validationStatus") == "passed" for item in summary["schemaValidations"]) and len(summary["schemaValidations"]) == 4
        summary["capabilities"] = build_capabilities(
            consumer_refresh=safe_mapping(summary.get("consumerRefresh")),
            route_preview=safe_mapping(summary.get("routePreview")),
            schema_ok=schema_ok,
        )
        if route_child.get("exitCode") == 1 or route_json.get("status") == "failed":
            summary["errors"].append("route-preview-failed")
        elif route_child.get("exitCode") != 0 or route_json.get("status") != "passed":
            summary["blockers"].append(f"route-preview-not-passed:{route_json.get('status')}")

        if summary["errors"]:
            summary["status"] = "failed"
            summary["verdict"] = "navigation-downstream-package-failed"
        elif summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "navigation-downstream-package-blocked"
        else:
            summary["status"] = "passed"
            summary["verdict"] = str(safe_mapping(summary.get("capabilities")).get("recommendedMode"))
    except Exception as exc:  # noqa: BLE001 - durable workflow helper error capture.
        summary["status"] = "failed"
        summary["verdict"] = "navigation-downstream-package-failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")

    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a one-command downstream navigation package")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--consumer-state-output-dir", default=str(DEFAULT_CONSUMER_STATE_OUTPUT_DIR))
    parser.add_argument("--waypoint-readiness-json", help="Saved waypoint readiness summary; defaults are delegated to child helpers")
    parser.add_argument("--normalized-waypoints-json")
    parser.add_argument("--sequence-summary-json")
    parser.add_argument("--contract-report-json")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--module-base")
    parser.add_argument("--max-consumer-state-age-seconds", type=float, default=DEFAULT_MAX_CONSUMER_STATE_AGE_SECONDS)
    parser.add_argument("--alignment-threshold-degrees", type=float, default=7.5)
    parser.add_argument("--command-timeout-seconds", type=float, default=DEFAULT_COMMAND_TIMEOUT_SECONDS)
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
