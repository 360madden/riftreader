from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .navigation_schema_validate import infer_schema_key, schema_path, validate_payload
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from navigation_schema_validate import infer_schema_key, schema_path, validate_payload  # type: ignore
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-consumer-demo"
DEFAULT_CONSUMER_STATE_JSON = Path(".riftreader-local") / "navigation-consumer-state" / "latest" / "summary.json"


def resolve_path(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def latest_waypoint_readiness(root: Path) -> Path | None:
    capture_root = root / "scripts" / "captures"
    candidates = sorted(
        capture_root.glob("navigation-waypoint-readiness-*/summary.json"),
        key=lambda item: item.stat().st_mtime_ns if item.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def path_from_mapping(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    return resolve_path(root, value)


def load_optional_json(path: Path | None, label: str, errors: list[str]) -> dict[str, Any] | None:
    if path is None:
        errors.append(f"{label}-path-missing")
        return None
    try:
        return load_json_object(path)
    except Exception as exc:  # noqa: BLE001 - report loader failures in summary.
        errors.append(f"{label}-load-failed:{type(exc).__name__}:{exc}")
        return None


def schema_check(root: Path, label: str, path: Path | None, payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "label": label,
            "path": str(path) if path else None,
            "schemaKey": None,
            "status": "blocked",
            "errorCount": 1,
            "errors": [f"{label}-payload-missing"],
        }
    key = infer_schema_key(payload)
    if not key:
        return {
            "label": label,
            "path": str(path) if path else None,
            "schemaKey": None,
            "status": "blocked",
            "errorCount": 1,
            "errors": [f"{label}-schema-key-not-recognized"],
        }
    schema = load_json_object(schema_path(root, key))
    validation = validate_payload(payload, schema)
    return {
        "label": label,
        "path": str(path) if path else None,
        "schemaKey": key,
        "status": validation["status"],
        "errorCount": validation["errorCount"],
        "errors": validation["errors"],
    }


def source_safety_blockers(name: str, payload: Mapping[str, Any]) -> list[str]:
    safety = safe_mapping(payload.get("safety"))
    blockers: list[str] = []
    for key in ("movementSent", "inputSent", "navigationControl", "targetMemoryBytesWritten", "providerWrites", "x64dbgAttach"):
        if safety.get(key) is True:
            blockers.append(f"{name}-source-safety-{key}-must-be-false")
    return blockers


def consumer_state_summary(payload: Mapping[str, Any], *, now: datetime, override_max_age: float | None) -> dict[str, Any]:
    generated_at = parse_utc(payload.get("generatedAtUtc"))
    contract = safe_mapping(payload.get("consumerContract"))
    max_age = override_max_age
    if max_age is None:
        raw_max_age = contract.get("maxConsumerAgeSeconds")
        max_age = float(raw_max_age) if isinstance(raw_max_age, (int, float)) else 5.0
    age_seconds = (now - generated_at).total_seconds() if generated_at else None
    navigation = safe_mapping(payload.get("navigation"))
    position = safe_mapping(navigation.get("position"))
    orientation = safe_mapping(navigation.get("orientation"))
    return {
        "status": payload.get("status"),
        "verdict": payload.get("verdict"),
        "generatedAtUtc": payload.get("generatedAtUtc"),
        "ageSeconds": age_seconds,
        "maxAgeSeconds": max_age,
        "fresh": age_seconds is not None and age_seconds <= max_age,
        "target": payload.get("target"),
        "position": position.get("coordinate"),
        "yawDegrees": orientation.get("yawDegrees"),
        "pitchDegrees": orientation.get("pitchDegrees"),
    }


def summarize_waypoints(payload: Mapping[str, Any]) -> dict[str, Any]:
    waypoints = payload.get("waypoints") if isinstance(payload.get("waypoints"), list) else []
    first = safe_mapping(waypoints[0]) if waypoints else {}
    last = safe_mapping(waypoints[-1]) if waypoints else {}
    return {
        "count": len(waypoints),
        "firstId": first.get("id"),
        "lastId": last.get("id"),
        "waypoints": waypoints,
    }


def all_schema_checks_pass(schema_checks: Sequence[Mapping[str, Any]]) -> bool:
    return all(item.get("status") == "passed" for item in schema_checks)


def build_capabilities(
    *,
    schema_ok: bool,
    consumer_state: Mapping[str, Any],
    waypoints: Mapping[str, Any],
    readiness: Mapping[str, Any],
    contract: Mapping[str, Any],
    require_fresh_pose: bool,
) -> dict[str, Any]:
    readiness_contract = safe_mapping(readiness.get("contract"))
    waypoint_count = int(waypoints.get("count") or 0)
    consumer_state_passed = consumer_state.get("status") == "passed"
    pose_fresh = consumer_state.get("fresh") is True
    contract_consumable = contract.get("status") == "passed" and safe_mapping(contract.get("contract")).get("consumable") is True
    readiness_consumable = readiness.get("status") == "passed" and readiness_contract.get("consumable") is True
    can_render = schema_ok and waypoint_count > 0
    can_use_dry_run = can_render and readiness_consumable and contract_consumable
    can_queue = can_use_dry_run and consumer_state_passed and pose_fresh
    if require_fresh_pose and not pose_fresh:
        can_queue = False
    if not schema_ok:
        mode = "blocked-schema-invalid"
        action = "Fix or regenerate invalid saved navigation artifacts before consumption."
    elif not can_render:
        mode = "blocked-no-route-to-render"
        action = "Provide normalized waypoints from waypoint readiness."
    elif not can_use_dry_run:
        mode = "render-only-contract-blocked"
        action = "Regenerate waypoint readiness and sequence contract report."
    elif not pose_fresh:
        mode = "render-and-dry-run-ready-refresh-pose-before-live-queue"
        action = "Render the route and dry-run output, then refresh consumer-state pose before requesting a gated live run."
    else:
        mode = "render-and-dry-run-ready-live-run-request-gated"
        action = "External consumer may render and queue a gated live-run request; execution still needs explicit live movement approval."
    return {
        "canRenderRoute": can_render,
        "canUseDryRunContract": can_use_dry_run,
        "canQueueGatedLiveRunRequest": can_queue,
        "canExecuteLiveNavigation": False,
        "liveExecutionRequiresExplicitApproval": True,
        "recommendedMode": mode,
        "nextRecommendedAction": action,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"navigation-consumer-demo-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    generated_at = utc_iso()
    errors: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    consumer_state_path = resolve_path(root, args.consumer_state_json or DEFAULT_CONSUMER_STATE_JSON)
    waypoint_readiness_path = resolve_path(root, args.waypoint_readiness_json) if args.waypoint_readiness_json else latest_waypoint_readiness(root)

    consumer_payload = load_optional_json(consumer_state_path, "consumer-state", errors)
    readiness_payload = load_optional_json(waypoint_readiness_path, "waypoint-readiness", errors)
    readiness_artifacts = safe_mapping(safe_mapping(readiness_payload).get("artifacts"))
    readiness_dry_run = safe_mapping(safe_mapping(readiness_payload).get("dryRun"))
    readiness_contract = safe_mapping(safe_mapping(readiness_payload).get("contract"))

    normalized_path = (
        resolve_path(root, args.normalized_waypoints_json)
        if args.normalized_waypoints_json
        else path_from_mapping(root, readiness_artifacts.get("normalizedWaypointJson"))
    )
    sequence_path = (
        resolve_path(root, args.sequence_summary_json)
        if args.sequence_summary_json
        else path_from_mapping(root, readiness_dry_run.get("summaryJson"))
    )
    contract_path = (
        resolve_path(root, args.contract_report_json)
        if args.contract_report_json
        else path_from_mapping(root, readiness_contract.get("summaryJson"))
    )

    normalized_payload = load_optional_json(normalized_path, "normalized-waypoints", errors)
    sequence_payload = load_optional_json(sequence_path, "sequence-summary", errors)
    contract_payload = load_optional_json(contract_path, "contract-report", errors)

    schema_checks = [
        schema_check(root, "consumer-state", consumer_state_path, consumer_payload),
        schema_check(root, "waypoint-readiness", waypoint_readiness_path, readiness_payload),
        schema_check(root, "normalized-waypoints", normalized_path, normalized_payload),
        schema_check(root, "sequence-summary", sequence_path, sequence_payload),
        schema_check(root, "contract-report", contract_path, contract_payload),
    ]
    for check in schema_checks:
        if check.get("status") != "passed":
            blockers.append(f"schema-check-blocked:{check.get('label')}")

    for label, payload in (
        ("consumer-state", consumer_payload),
        ("waypoint-readiness", readiness_payload),
        ("sequence-summary", sequence_payload),
        ("contract-report", contract_payload),
    ):
        if payload is not None:
            blockers.extend(source_safety_blockers(label, payload))

    consumer_summary = consumer_state_summary(
        consumer_payload or {},
        now=now,
        override_max_age=float(args.max_consumer_state_age_seconds)
        if args.max_consumer_state_age_seconds is not None
        else None,
    )
    if consumer_payload and consumer_payload.get("status") != "passed":
        blockers.append(f"consumer-state-status-not-passed:{consumer_payload.get('status')}")
    if not consumer_summary.get("fresh"):
        stale_text = (
            f"consumer-state-stale:ageSeconds={consumer_summary.get('ageSeconds')};"
            f"maxAgeSeconds={consumer_summary.get('maxAgeSeconds')}"
        )
        if args.require_fresh_pose:
            blockers.append(stale_text)
        else:
            warnings.append(stale_text)

    waypoints_summary = summarize_waypoints(normalized_payload or {})
    if int(waypoints_summary.get("count") or 0) <= 0:
        blockers.append("normalized-waypoints-empty")

    contract_summary = {
        "status": safe_mapping(contract_payload).get("status"),
        "consumable": safe_mapping(safe_mapping(contract_payload).get("contract")).get("consumable"),
        "summaryJson": str(contract_path) if contract_path else None,
    }
    sequence_summary = {
        "status": safe_mapping(sequence_payload).get("status"),
        "verdict": safe_mapping(sequence_payload).get("verdict"),
        "summaryJson": str(sequence_path) if sequence_path else None,
    }
    capabilities = build_capabilities(
        schema_ok=all_schema_checks_pass(schema_checks),
        consumer_state=consumer_summary,
        waypoints=waypoints_summary,
        readiness=readiness_payload or {},
        contract=contract_payload or {},
        require_fresh_pose=bool(args.require_fresh_pose),
    )

    safety = base_safety()
    safety.update(
        {
            "readOnlySavedJson": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "consumerDemoOnly": True,
            "routeControlAuthorized": False,
        }
    )
    status = "failed" if errors else "blocked" if blockers else "passed"
    if status == "passed":
        verdict = str(capabilities["recommendedMode"])
    elif status == "blocked":
        verdict = "navigation-consumer-demo-blocked"
    else:
        verdict = "navigation-consumer-demo-failed"

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": generated_at,
        "status": status,
        "verdict": verdict,
        "repoRoot": str(root),
        "input": {
            "consumerStateJson": str(consumer_state_path) if consumer_state_path else None,
            "waypointReadinessJson": str(waypoint_readiness_path) if waypoint_readiness_path else None,
            "normalizedWaypointsJson": str(normalized_path) if normalized_path else None,
            "sequenceSummaryJson": str(sequence_path) if sequence_path else None,
            "contractReportJson": str(contract_path) if contract_path else None,
            "requireFreshPose": bool(args.require_fresh_pose),
            "maxConsumerStateAgeSeconds": args.max_consumer_state_age_seconds,
        },
        "schemaChecks": schema_checks,
        "consumerState": consumer_summary,
        "waypoints": waypoints_summary,
        "dryRun": sequence_summary,
        "contract": contract_summary,
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
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    caps = safe_mapping(summary.get("capabilities"))
    consumer_state = safe_mapping(summary.get("consumerState"))
    waypoints = safe_mapping(summary.get("waypoints"))
    lines = [
        "# Navigation consumer demo",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Capability decision",
        "",
        f"- Can render route: `{caps.get('canRenderRoute')}`",
        f"- Can use dry-run contract: `{caps.get('canUseDryRunContract')}`",
        f"- Can queue gated live-run request: `{caps.get('canQueueGatedLiveRunRequest')}`",
        f"- Can execute live navigation: `{caps.get('canExecuteLiveNavigation')}`",
        f"- Recommended mode: `{caps.get('recommendedMode')}`",
        f"- Next action: `{caps.get('nextRecommendedAction')}`",
        "",
        "## Inputs",
        "",
        f"- Consumer state age seconds: `{consumer_state.get('ageSeconds')}`",
        f"- Consumer state fresh: `{consumer_state.get('fresh')}`",
        f"- Waypoints: `{waypoints.get('count')}`",
        "",
        "## Schema checks",
        "",
    ]
    for check in summary.get("schemaChecks", []):
        if isinstance(check, Mapping):
            lines.append(
                f"- `{check.get('label')}`: `{check.get('status')}` "
                f"schema=`{check.get('schemaKey')}` errors=`{check.get('errorCount')}`"
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
    artifacts = safe_mapping(summary.get("artifacts"))
    caps = safe_mapping(summary.get("capabilities"))
    consumer_state = safe_mapping(summary.get("consumerState"))
    waypoints = safe_mapping(summary.get("waypoints"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "recommendedMode": caps.get("recommendedMode"),
        "nextRecommendedAction": caps.get("nextRecommendedAction"),
        "canRenderRoute": caps.get("canRenderRoute"),
        "canUseDryRunContract": caps.get("canUseDryRunContract"),
        "canQueueGatedLiveRunRequest": caps.get("canQueueGatedLiveRunRequest"),
        "canExecuteLiveNavigation": caps.get("canExecuteLiveNavigation"),
        "consumerStateFresh": consumer_state.get("fresh"),
        "consumerStateAgeSeconds": consumer_state.get("ageSeconds"),
        "waypointCount": waypoints.get("count"),
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
    parser = argparse.ArgumentParser(description="Build a saved-artifact downstream navigation consumer demo report")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--consumer-state-json", default=str(DEFAULT_CONSUMER_STATE_JSON))
    parser.add_argument("--waypoint-readiness-json", help="Saved waypoint readiness summary; defaults to newest capture")
    parser.add_argument("--normalized-waypoints-json", help="Optional override; otherwise derived from readiness artifacts")
    parser.add_argument("--sequence-summary-json", help="Optional override; otherwise derived from readiness dryRun.summaryJson")
    parser.add_argument("--contract-report-json", help="Optional override; otherwise derived from readiness contract.summaryJson")
    parser.add_argument("--max-consumer-state-age-seconds", type=float)
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
