from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
SOURCE_KIND = "static-owner-continuous-route-sequence"
REPORT_KIND = "static-owner-continuous-route-sequence-contract-report"
ACCEPTED_SEQUENCE_VERDICTS = {"sequence-dry-run-plan-built", "sequence-all-waypoints-reached"}
ACCEPTED_LEG_VERDICTS = {"dry-run-plan-built", "already-arrived"}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _sequence_legs(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [safe_mapping(item) for item in summary.get("legs", []) if isinstance(item, Mapping)]


def validate_sequence_summary_contract(summary: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    if summary.get("kind") != SOURCE_KIND:
        blockers.append("sequence-kind-must-be-static-owner-continuous-route-sequence")
    if summary.get("status") != "passed":
        blockers.append("sequence-status-must-be-passed")
    verdict = str(summary.get("verdict") or "")
    if verdict not in ACCEPTED_SEQUENCE_VERDICTS:
        blockers.append("sequence-verdict-must-be-dry-run-plan-or-all-waypoints-reached")
    if summary.get("blockers"):
        blockers.append("sequence-blockers-must-be-empty")
    if summary.get("errors"):
        blockers.append("sequence-errors-must-be-empty")

    operator = safe_mapping(summary.get("operator"))
    if operator.get("dryRun") is not True:
        blockers.append("sequence-operator-dryRun-must-be-true")
    safety = safe_mapping(summary.get("safety"))
    if safety.get("movementSent") is True:
        blockers.append("sequence-safety-movementSent-must-be-false")
    if safety.get("inputSent") is True:
        blockers.append("sequence-safety-inputSent-must-be-false")
    if safety.get("navigationControl") is True:
        blockers.append("sequence-safety-navigationControl-must-be-false")
    if safety.get("x64dbgAttach") is True or safety.get("debuggerAttached") is True:
        blockers.append("sequence-safety-debugger-must-be-false")
    if safety.get("providerWrites") is True:
        blockers.append("sequence-safety-providerWrites-must-be-false")
    if safety.get("targetMemoryBytesWritten") is True:
        blockers.append("sequence-safety-targetMemoryBytesWritten-must-be-false")

    total = safe_mapping(summary.get("total"))
    total_legs = _as_int(total.get("totalLegs"))
    legs_planned = _as_int(total.get("legsPlanned"))
    legs_arrived = _as_int(total.get("legsArrived"))
    legs_failed = _as_int(total.get("legsFailed"))
    if total_legs <= 0:
        blockers.append("sequence-totalLegs-must-be-positive")
    if legs_failed != 0:
        blockers.append("sequence-legsFailed-must-be-zero")

    legs = _sequence_legs(summary)
    if not legs:
        blockers.append("sequence-legs-must-not-be-empty")

    dry_run_plan_indices: list[int] = []
    for index, leg in enumerate(legs, start=1):
        leg_status = str(leg.get("status") or "")
        leg_verdict = str(leg.get("verdict") or "")
        if leg_status != "passed":
            blockers.append(f"leg-{index}-status-must-be-passed")
        if leg_verdict not in ACCEPTED_LEG_VERDICTS:
            blockers.append(f"leg-{index}-verdict-must-be-dry-run-plan-or-already-arrived")
        if leg_verdict == "dry-run-plan-built":
            dry_run_plan_indices.append(index)
        leg_safety = safe_mapping(leg.get("safety"))
        if leg_safety.get("movementSent") is True:
            blockers.append(f"leg-{index}-movementSent-must-be-false")
        if leg_safety.get("inputSent") is True:
            blockers.append(f"leg-{index}-inputSent-must-be-false")
        if leg_safety.get("navigationControl") is True:
            blockers.append(f"leg-{index}-navigationControl-must-be-false")

    if verdict == "sequence-dry-run-plan-built":
        if legs_planned <= 0:
            blockers.append("sequence-dry-run-legsPlanned-must-be-positive")
        if not dry_run_plan_indices:
            blockers.append("sequence-dry-run-must-include-one-dry-run-plan-leg")
        if len(dry_run_plan_indices) > 1:
            blockers.append("sequence-dry-run-must-stop-after-first-unreached-leg")
        if dry_run_plan_indices and dry_run_plan_indices[-1] != len(legs):
            blockers.append("sequence-dry-run-plan-leg-must-be-final-recorded-leg")
        if legs_arrived >= total_legs:
            blockers.append("sequence-dry-run-legsArrived-must-be-less-than-totalLegs")
    elif verdict == "sequence-all-waypoints-reached":
        if legs_arrived != total_legs:
            blockers.append("sequence-all-reached-legsArrived-must-equal-totalLegs")
        if dry_run_plan_indices:
            blockers.append("sequence-all-reached-must-not-include-dry-run-plan-leg")

    if len(legs) > total_legs > 0:
        blockers.append("sequence-recorded-legs-must-not-exceed-totalLegs")
    if legs_planned > 1:
        warnings.append("sequence-dry-run-planned-more-than-one-leg")

    first_unreached_leg_index = dry_run_plan_indices[0] if dry_run_plan_indices else None
    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    return {
        "status": "passed" if not blockers else "blocked",
        "consumable": not blockers,
        "acceptedSequenceVerdicts": sorted(ACCEPTED_SEQUENCE_VERDICTS),
        "acceptedLegVerdicts": sorted(ACCEPTED_LEG_VERDICTS),
        "totalLegs": total_legs,
        "legsPlanned": legs_planned,
        "legsArrived": legs_arrived,
        "legsFailed": legs_failed,
        "recordedLegs": len(legs),
        "firstUnreachedLegIndex": first_unreached_leg_index,
        "blockers": blockers,
        "warnings": warnings,
    }


def build_report(source_path: Path, output_root: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    output_root = (output_root or root / "scripts" / "captures").resolve()
    run_dir = output_root / f"static-owner-continuous-route-sequence-contract-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    safety = base_safety()
    safety["targetMemoryBytesRead"] = False
    safety["targetMemoryBytesWritten"] = False
    safety["readOnlySavedSummary"] = True
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": REPORT_KIND,
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "repoRoot": str(root),
        "sourceSummaryJson": str(source_path.resolve()),
        "source": {},
        "contract": {},
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
        source = load_json_object(source_path)
        contract = validate_sequence_summary_contract(source)
        total = safe_mapping(source.get("total"))
        summary["source"] = {
            "kind": source.get("kind"),
            "status": source.get("status"),
            "verdict": source.get("verdict"),
            "totalLegs": total.get("totalLegs"),
            "legsPlanned": total.get("legsPlanned", 0),
            "legsArrived": total.get("legsArrived"),
            "legsFailed": total.get("legsFailed"),
        }
        summary["contract"] = contract
        summary["blockers"].extend(contract["blockers"])
        summary["warnings"].extend(contract["warnings"])
        summary["status"] = "passed" if contract["status"] == "passed" else "blocked"
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    source = safe_mapping(summary.get("source"))
    contract = safe_mapping(summary.get("contract"))
    lines = [
        "# Static owner continuous route sequence contract report",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Source summary: `{summary.get('sourceSummaryJson')}`",
        "",
        "## Source",
        "",
        f"Kind: `{source.get('kind')}`",
        f"Verdict: `{source.get('verdict')}`",
        f"Total legs: `{source.get('totalLegs')}`",
        f"Planned: `{source.get('legsPlanned')}`",
        f"Arrived: `{source.get('legsArrived')}`",
        f"Failed: `{source.get('legsFailed')}`",
        "",
        "## Contract",
        "",
        f"Consumable: `{contract.get('consumable')}`",
        f"First unreached leg index: `{contract.get('firstUnreachedLegIndex')}`",
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
    contract = safe_mapping(summary.get("contract"))
    source = safe_mapping(summary.get("source"))
    return {
        "status": summary.get("status"),
        "kind": summary.get("kind"),
        "sourceSummaryJson": summary.get("sourceSummaryJson"),
        "sourceVerdict": source.get("verdict"),
        "consumable": contract.get("consumable"),
        "totalLegs": contract.get("totalLegs"),
        "legsPlanned": contract.get("legsPlanned"),
        "legsArrived": contract.get("legsArrived"),
        "firstUnreachedLegIndex": contract.get("firstUnreachedLegIndex"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate/report a saved continuous route sequence dry-run summary")
    parser.add_argument("summary_json", help="Saved static-owner-continuous-route-sequence summary.json")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else None
    summary = build_report(Path(args.summary_json), output_root=output_root, root=root)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
