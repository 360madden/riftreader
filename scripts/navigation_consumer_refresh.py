from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .workflow_common import base_safety, repo_root, run_child, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import base_safety, repo_root, run_child, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-consumer-refresh"
DEFAULT_CONSUMER_STATE_OUTPUT_DIR = Path(".riftreader-local") / "navigation-consumer-state" / "latest"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 90.0


def _resolve_path(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def _consumer_state_command(args: argparse.Namespace, root: Path, output_dir: Path) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "navigation_consumer_state.py"),
        "--repo-root",
        str(root),
        "--current-truth-json",
        str(_resolve_path(root, args.current_truth_json)),
        "--max-consumer-age-seconds",
        str(float(args.max_consumer_state_age_seconds)),
        "--write",
        "--output-dir",
        str(output_dir),
        "--json",
    ]
    if args.pid is not None:
        command.extend(["--pid", str(int(args.pid))])
    if args.hwnd:
        command.extend(["--hwnd", str(args.hwnd)])
    if args.module_base:
        command.extend(["--module-base", str(args.module_base)])
    if args.process_name:
        command.extend(["--process-name", str(args.process_name)])
    return command


def _consumer_demo_command(
    args: argparse.Namespace,
    root: Path,
    *,
    output_root: Path,
    consumer_state_json: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "navigation_consumer_demo.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--consumer-state-json",
        str(consumer_state_json),
        "--max-consumer-state-age-seconds",
        str(float(args.max_consumer_state_age_seconds)),
        "--json",
    ]
    if args.waypoint_readiness_json:
        command.extend(["--waypoint-readiness-json", str(_resolve_path(root, args.waypoint_readiness_json))])
    if args.normalized_waypoints_json:
        command.extend(["--normalized-waypoints-json", str(_resolve_path(root, args.normalized_waypoints_json))])
    if args.sequence_summary_json:
        command.extend(["--sequence-summary-json", str(_resolve_path(root, args.sequence_summary_json))])
    if args.contract_report_json:
        command.extend(["--contract-report-json", str(_resolve_path(root, args.contract_report_json))])
    if args.require_fresh_pose:
        command.append("--require-fresh-pose")
    return command


def build_markdown(summary: Mapping[str, Any]) -> str:
    consumer_state = safe_mapping(summary.get("consumerState"))
    demo = safe_mapping(summary.get("consumerDemo"))
    capabilities = safe_mapping(demo.get("capabilities"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Navigation consumer refresh",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Refreshed artifacts",
        "",
        f"- Consumer state: `{consumer_state.get('summaryJson')}`",
        f"- Consumer demo: `{demo.get('summaryJson')}`",
        f"- Refresh summary: `{artifacts.get('summaryJson')}`",
        "",
        "## Capability decision",
        "",
        f"- Can render route: `{capabilities.get('canRenderRoute')}`",
        f"- Can use dry-run contract: `{capabilities.get('canUseDryRunContract')}`",
        f"- Can queue gated live-run request: `{capabilities.get('canQueueGatedLiveRunRequest')}`",
        f"- Can execute live navigation: `{capabilities.get('canExecuteLiveNavigation')}`",
        f"- Recommended mode: `{capabilities.get('recommendedMode')}`",
        f"- Next action: `{capabilities.get('nextRecommendedAction')}`",
        "",
        "## Safety",
        "",
        "- Refresh may read live target memory through the consumer-state helper.",
        "- It sends no input or movement and never authorizes route execution.",
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
    demo = safe_mapping(summary.get("consumerDemo"))
    capabilities = safe_mapping(demo.get("capabilities"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "consumerStateSummaryJson": safe_mapping(summary.get("consumerState")).get("summaryJson"),
        "consumerDemoSummaryJson": demo.get("summaryJson"),
        "recommendedMode": capabilities.get("recommendedMode"),
        "nextRecommendedAction": capabilities.get("nextRecommendedAction"),
        "canRenderRoute": capabilities.get("canRenderRoute"),
        "canUseDryRunContract": capabilities.get("canUseDryRunContract"),
        "canQueueGatedLiveRunRequest": capabilities.get("canQueueGatedLiveRunRequest"),
        "canExecuteLiveNavigation": capabilities.get("canExecuteLiveNavigation"),
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
    run_dir = output_root / f"navigation-consumer-refresh-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    consumer_output_dir = _resolve_path(root, args.consumer_state_output_dir) or root / DEFAULT_CONSUMER_STATE_OUTPUT_DIR
    consumer_summary_path = consumer_output_dir / "summary.json"
    demo_output_root = run_dir / "consumer-demo"

    safety = base_safety()
    safety.update(
        {
            "readOnlyConsumerRefresh": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "routeControlAuthorized": False,
            "consumerRefreshOnly": True,
        }
    )
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "verdict": "navigation-consumer-refresh-pending",
        "repoRoot": str(root),
        "input": {
            "currentTruthJson": str(_resolve_path(root, args.current_truth_json)),
            "consumerStateOutputDir": str(consumer_output_dir),
            "waypointReadinessJson": str(_resolve_path(root, args.waypoint_readiness_json))
            if args.waypoint_readiness_json
            else None,
            "requireFreshPose": bool(args.require_fresh_pose),
            "maxConsumerStateAgeSeconds": float(args.max_consumer_state_age_seconds),
        },
        "consumerState": {
            "status": None,
            "summaryJson": str(consumer_summary_path),
            "exitCode": None,
        },
        "consumerDemo": {
            "status": None,
            "summaryJson": None,
            "capabilities": {},
            "exitCode": None,
        },
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
        consumer_child = run_child(
            label="consumer-state-refresh",
            command=_consumer_state_command(args, root, consumer_output_dir),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(consumer_child)
        consumer_json = consumer_child.get("json") if isinstance(consumer_child.get("json"), Mapping) else {}
        consumer_artifacts = safe_mapping(consumer_json.get("artifacts"))
        consumer_summary_json = consumer_artifacts.get("summaryJson") or str(consumer_summary_path)
        summary["consumerState"] = {
            "status": consumer_json.get("status"),
            "verdict": consumer_json.get("verdict"),
            "summaryJson": consumer_summary_json,
            "summaryMarkdown": consumer_artifacts.get("summaryMarkdown"),
            "exitCode": consumer_child.get("exitCode"),
        }
        safety["targetMemoryBytesRead"] = bool(safe_mapping(consumer_json.get("safety")).get("targetMemoryBytesRead"))
        if consumer_child.get("exitCode") == 1:
            summary["errors"].append("consumer-state-refresh-failed")
            summary["status"] = "failed"
            summary["verdict"] = "navigation-consumer-refresh-failed"
            return summary
        if consumer_child.get("exitCode") != 0 or consumer_json.get("status") != "passed":
            summary["blockers"].append(f"consumer-state-refresh-not-passed:{consumer_json.get('status')}")
            summary["status"] = "blocked"
            summary["verdict"] = "navigation-consumer-refresh-blocked"
            return summary

        demo_child = run_child(
            label="consumer-demo-refresh",
            command=_consumer_demo_command(
                args,
                root,
                output_root=demo_output_root,
                consumer_state_json=Path(str(consumer_summary_json)),
            ),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(demo_child)
        demo_json = demo_child.get("json") if isinstance(demo_child.get("json"), Mapping) else {}
        summary["consumerDemo"] = {
            "status": demo_json.get("status"),
            "verdict": demo_json.get("verdict"),
            "summaryJson": demo_json.get("summaryJson"),
            "summaryMarkdown": demo_json.get("summaryMarkdown"),
            "exitCode": demo_child.get("exitCode"),
            "capabilities": {
                "recommendedMode": demo_json.get("recommendedMode"),
                "nextRecommendedAction": demo_json.get("nextRecommendedAction"),
                "canRenderRoute": demo_json.get("canRenderRoute"),
                "canUseDryRunContract": demo_json.get("canUseDryRunContract"),
                "canQueueGatedLiveRunRequest": demo_json.get("canQueueGatedLiveRunRequest"),
                "canExecuteLiveNavigation": demo_json.get("canExecuteLiveNavigation"),
            },
        }
        summary["warnings"].extend(str(item) for item in demo_json.get("warnings", []) if item)
        summary["blockers"].extend(str(item) for item in demo_json.get("blockers", []) if item)
        summary["errors"].extend(str(item) for item in demo_json.get("errors", []) if item)
        if demo_child.get("exitCode") == 1 or demo_json.get("status") == "failed":
            summary["status"] = "failed"
            summary["verdict"] = "navigation-consumer-refresh-failed"
        elif summary["blockers"] or demo_json.get("status") == "blocked":
            summary["status"] = "blocked"
            summary["verdict"] = "navigation-consumer-refresh-blocked"
        else:
            summary["status"] = "passed"
            summary["verdict"] = str(demo_json.get("recommendedMode") or "navigation-consumer-refresh-passed")
    except Exception as exc:  # noqa: BLE001 - durable helper error capture.
        summary["status"] = "failed"
        summary["verdict"] = "navigation-consumer-refresh-failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")

    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh consumer pose and rerun downstream navigation consumer demo")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--consumer-state-output-dir", default=str(DEFAULT_CONSUMER_STATE_OUTPUT_DIR))
    parser.add_argument("--waypoint-readiness-json", help="Saved waypoint readiness summary; demo defaults to newest when omitted")
    parser.add_argument("--normalized-waypoints-json")
    parser.add_argument("--sequence-summary-json")
    parser.add_argument("--contract-report-json")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--module-base")
    parser.add_argument("--max-consumer-state-age-seconds", type=float, default=5.0)
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
