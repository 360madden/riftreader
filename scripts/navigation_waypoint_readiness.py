from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .workflow_common import (
        base_safety,
        load_json_object,
        repo_root,
        run_child,
        safe_mapping,
        utc_iso,
        utc_stamp,
        write_json,
    )
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import (  # type: ignore
        base_safety,
        load_json_object,
        repo_root,
        run_child,
        safe_mapping,
        utc_iso,
        utc_stamp,
        write_json,
    )


SCHEMA_VERSION = 1
KIND = "riftreader-navigation-waypoint-readiness"
DEFAULT_ARRIVAL_RADIUS = 2.0
DEFAULT_COMMAND_TIMEOUT_SECONDS = 120.0


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _parse_float(value: Any, field: str, blockers: list[str]) -> float | None:
    if isinstance(value, bool) or value is None:
        blockers.append(f"{field}-must-be-finite-number")
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        blockers.append(f"{field}-must-be-finite-number")
        return None
    if not math.isfinite(number):
        blockers.append(f"{field}-must-be-finite-number")
        return None
    return number


def _requested_ids(sequence_ids: str | None, blockers: list[str]) -> list[str] | None:
    if sequence_ids is None:
        return None
    ids = [item.strip() for item in sequence_ids.split(",") if item.strip()]
    if not ids:
        blockers.append("waypoint-sequence-ids-empty")
    if len(ids) != len(set(ids)):
        blockers.append("waypoint-sequence-ids-contains-duplicates")
    return ids


def lint_and_normalize_waypoints(
    data: Mapping[str, Any],
    *,
    input_path: Path,
    default_arrival_radius: float,
    sequence_ids: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    requested = _requested_ids(sequence_ids, blockers)
    raw_waypoints = data.get("waypoints")
    if not isinstance(raw_waypoints, list):
        blockers.append("waypoints-must-be-array")
        raw_waypoints = []
    if not raw_waypoints:
        blockers.append("waypoints-must-not-be-empty")

    normalized_all: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    for index, raw in enumerate(raw_waypoints, start=1):
        if not isinstance(raw, Mapping):
            blockers.append(f"waypoint-{index}-must-be-object")
            continue

        raw_id = str(raw.get("id") or "").strip()
        waypoint_id = raw_id or f"waypoint-{index:03d}"
        if not raw_id:
            warnings.append(f"waypoint-{index}-id-generated:{waypoint_id}")
        if waypoint_id in seen_ids:
            blockers.append(f"waypoint-id-duplicate:{waypoint_id}")
        seen_ids[waypoint_id] = index

        label = str(raw.get("label") or waypoint_id)
        item_blockers: list[str] = []
        x = _parse_float(raw.get("x"), f"waypoint-{index}-x", item_blockers)
        y = _parse_float(raw.get("y"), f"waypoint-{index}-y", item_blockers)
        z = _parse_float(raw.get("z"), f"waypoint-{index}-z", item_blockers)
        blockers.extend(item_blockers)

        arrival_value = raw.get("arrivalRadius")
        if arrival_value is None and raw.get("radius") is not None:
            arrival_value = raw.get("radius")
            warnings.append(f"waypoint-{index}-legacy-radius-normalized-to-arrivalRadius")
        elif arrival_value is not None and raw.get("radius") is not None:
            warnings.append(f"waypoint-{index}-legacy-radius-ignored-because-arrivalRadius-present")
        elif arrival_value is None:
            arrival_value = default_arrival_radius
            warnings.append(f"waypoint-{index}-arrivalRadius-defaulted:{default_arrival_radius}")

        radius = _parse_float(arrival_value, f"waypoint-{index}-arrivalRadius", blockers)
        if radius is not None and radius < 0:
            blockers.append(f"waypoint-{index}-arrivalRadius-must-be-nonnegative")

        if x is None or y is None or z is None or radius is None:
            continue

        normalized_all.append(
            {
                "id": waypoint_id,
                "label": label,
                "x": x,
                "y": y,
                "z": z,
                "arrivalRadius": radius,
            }
        )

    selected = normalized_all
    if requested is not None:
        by_id = {item["id"]: item for item in normalized_all}
        missing = [item for item in requested if item not in by_id]
        if missing:
            blockers.append(f"waypoint-ids-not-found:{','.join(missing)}")
        selected = [by_id[item] for item in requested if item in by_id]
        if not selected:
            blockers.append("selected-waypoints-empty")

    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    return {
        "status": "passed" if not blockers else "blocked",
        "inputJson": str(input_path),
        "originalWaypointCount": len(raw_waypoints),
        "selectedWaypointCount": len(selected),
        "defaultArrivalRadius": default_arrival_radius,
        "requestedWaypointIds": requested,
        "normalizedWaypoints": selected,
        "blockers": blockers,
        "warnings": warnings,
    }


def normalized_waypoint_payload(lint: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "provenance": {
            "kind": "riftreader-normalized-navigation-waypoints",
            "generatedAtUtc": utc_iso(),
            "inputJson": lint.get("inputJson"),
            "defaultArrivalRadius": lint.get("defaultArrivalRadius"),
            "requestedWaypointIds": lint.get("requestedWaypointIds"),
        },
        "waypoints": lint.get("normalizedWaypoints", []),
    }


def _sequence_dry_run_command(args: argparse.Namespace, root: Path, normalized_path: Path, output_root: Path) -> list[str]:
    current_truth = _resolve_path(root, str(args.current_truth_json))
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_continuous_route_runner.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--current-truth-json",
        str(current_truth),
        "--waypoint-sequence-json",
        str(normalized_path),
        "--dry-run",
        "--command-timeout-seconds",
        str(float(args.command_timeout_seconds)),
        "--json",
    ]


def _contract_command(args: argparse.Namespace, root: Path, sequence_summary_json: str, output_root: Path) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "navigation_sequence_summary_contract.py"),
        sequence_summary_json,
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--json",
    ]


def build_markdown(summary: Mapping[str, Any]) -> str:
    lint = safe_mapping(summary.get("lint"))
    dry_run = safe_mapping(summary.get("dryRun"))
    contract = safe_mapping(summary.get("contract"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Navigation waypoint readiness",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Lint",
        "",
        f"Input: `{lint.get('inputJson')}`",
        f"Original waypoints: `{lint.get('originalWaypointCount')}`",
        f"Selected waypoints: `{lint.get('selectedWaypointCount')}`",
        f"Normalized waypoints: `{artifacts.get('normalizedWaypointJson')}`",
        "",
        "## Dry-run / contract",
        "",
        f"Dry-run status: `{dry_run.get('status')}`",
        f"Dry-run summary: `{dry_run.get('summaryJson')}`",
        f"Contract status: `{contract.get('status')}`",
        f"Contract consumable: `{contract.get('consumable')}`",
        f"Contract summary: `{contract.get('summaryJson')}`",
        "",
    ]
    if summary.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
        lines.append("")
    if summary.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
        lines.append("")
    if summary.get("errors"):
        lines.extend(["## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
        lines.append("")
    return "\n".join(lines) + "\n"


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    lint = safe_mapping(summary.get("lint"))
    dry_run = safe_mapping(summary.get("dryRun"))
    contract = safe_mapping(summary.get("contract"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "selectedWaypointCount": lint.get("selectedWaypointCount"),
        "normalizedWaypointJson": artifacts.get("normalizedWaypointJson"),
        "dryRunStatus": dry_run.get("status"),
        "dryRunVerdict": dry_run.get("verdict"),
        "dryRunSummaryJson": dry_run.get("summaryJson"),
        "contractStatus": contract.get("status"),
        "contractConsumable": contract.get("consumable"),
        "contractSummaryJson": contract.get("summaryJson"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"navigation-waypoint-readiness-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    input_path = _resolve_path(root, str(args.waypoint_sequence_json))
    normalized_path = run_dir / "normalized-waypoints.json"
    safety = base_safety()
    safety["targetMemoryBytesRead"] = False
    safety["targetMemoryBytesWritten"] = False
    safety["readOnlyWaypointReadiness"] = True

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "verdict": None,
        "repoRoot": str(root),
        "input": {
            "waypointSequenceJson": str(input_path),
            "waypointSequenceIds": args.waypoint_sequence_ids,
            "skipDryRun": bool(args.skip_dry_run),
            "currentTruthJson": str(_resolve_path(root, str(args.current_truth_json))),
        },
        "lint": {},
        "dryRun": {},
        "contract": {},
        "childCommands": [],
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
            "normalizedWaypointJson": str(normalized_path),
        },
    }

    try:
        data = load_json_object(input_path)
        lint = lint_and_normalize_waypoints(
            data,
            input_path=input_path,
            default_arrival_radius=float(args.default_arrival_radius),
            sequence_ids=args.waypoint_sequence_ids,
        )
        summary["lint"] = lint
        summary["warnings"].extend(lint.get("warnings", []))
        summary["blockers"].extend(lint.get("blockers", []))
        if lint.get("normalizedWaypoints"):
            write_json(normalized_path, normalized_waypoint_payload(lint))
        if lint.get("status") != "passed":
            summary["status"] = "blocked"
            summary["verdict"] = "waypoint-readiness-lint-blocked"
            return summary

        write_json(normalized_path, normalized_waypoint_payload(lint))
        if args.skip_dry_run:
            summary["status"] = "passed"
            summary["verdict"] = "waypoint-readiness-lint-passed"
            return summary

        safety["targetMemoryBytesRead"] = True
        sequence_child = run_child(
            label="sequence-dry-run",
            command=_sequence_dry_run_command(args, root, normalized_path, run_dir / "sequence-dry-run"),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(sequence_child)
        sequence_json = sequence_child.get("json") if isinstance(sequence_child.get("json"), Mapping) else {}
        sequence_status = str(sequence_json.get("status") or "")
        summary["dryRun"] = {
            "status": sequence_status or None,
            "verdict": sequence_json.get("verdict"),
            "summaryJson": sequence_json.get("summaryJson"),
            "summaryMarkdown": sequence_json.get("summaryMarkdown"),
        }
        if not sequence_child.get("ok") or sequence_status != "passed":
            if sequence_status == "blocked":
                summary["status"] = "blocked"
                summary["verdict"] = "waypoint-readiness-dry-run-blocked"
                summary["blockers"].append("sequence-dry-run-blocked")
            else:
                summary["status"] = "failed"
                summary["verdict"] = "waypoint-readiness-dry-run-failed"
                summary["errors"].append(f"sequence-dry-run-status:{sequence_status or sequence_child.get('exitCode')}")
            return summary
        sequence_summary_json = sequence_json.get("summaryJson")
        if not sequence_summary_json:
            summary["status"] = "failed"
            summary["verdict"] = "waypoint-readiness-dry-run-summary-missing"
            summary["errors"].append("sequence-dry-run-summary-json-missing")
            return summary

        contract_child = run_child(
            label="sequence-contract",
            command=_contract_command(args, root, str(sequence_summary_json), run_dir / "sequence-contract"),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(contract_child)
        contract_json = contract_child.get("json") if isinstance(contract_child.get("json"), Mapping) else {}
        summary["contract"] = {
            "status": contract_json.get("status"),
            "consumable": contract_json.get("consumable"),
            "summaryJson": contract_json.get("summaryJson"),
            "summaryMarkdown": contract_json.get("summaryMarkdown"),
            "blockers": contract_json.get("blockers", []),
            "warnings": contract_json.get("warnings", []),
        }
        summary["warnings"].extend(contract_json.get("warnings", []) if isinstance(contract_json.get("warnings"), list) else [])
        summary["blockers"].extend(contract_json.get("blockers", []) if isinstance(contract_json.get("blockers"), list) else [])
        if contract_json.get("status") == "passed" and contract_json.get("consumable") is True:
            summary["status"] = "passed"
            summary["verdict"] = "waypoint-readiness-consumable"
        elif contract_json.get("status") == "blocked":
            summary["status"] = "blocked"
            summary["verdict"] = "waypoint-readiness-contract-blocked"
        else:
            summary["status"] = "failed"
            summary["verdict"] = "waypoint-readiness-contract-failed"
            if not summary["errors"]:
                summary["errors"].append(f"sequence-contract-status:{contract_json.get('status') or contract_child.get('exitCode')}")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "waypoint-readiness-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    finally:
        summary["blockers"] = sorted(set(summary["blockers"]))
        summary["warnings"] = sorted(set(summary["warnings"]))
        summary["errors"] = sorted(set(summary["errors"]))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lint waypoint files and optionally run a safe dry-run readiness gate")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--waypoint-sequence-json", required=True)
    parser.add_argument("--waypoint-sequence-ids")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--default-arrival-radius", type=float, default=DEFAULT_ARRIVAL_RADIUS)
    parser.add_argument("--command-timeout-seconds", type=float, default=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    parser.add_argument("--skip-dry-run", action="store_true", help="Lint/normalize only; do not read live target state")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    summary = run(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
