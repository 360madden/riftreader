from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return document


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def normalize_hwnd(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        return f"0x{int(str(value), 0):X}"
    except ValueError:
        return str(value)


def path_text(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def hex_or_none(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return f"0x{value:X}"
    text = str(value)
    try:
        return f"0x{int(text, 0):X}"
    except ValueError:
        return text


def summarize_classifier(path: Path, document: Mapping[str, Any], repo_root: Path) -> dict[str, Any]:
    counts = safe_dict(document.get("counts"))
    inputs = safe_dict(document.get("inputs"))
    return {
        "path": path_text(path, repo_root),
        "status": document.get("status"),
        "generatedAtUtc": document.get("generatedAtUtc"),
        "priorityOffset": inputs.get("priorityOffset"),
        "leadLimit": inputs.get("leadLimit"),
        "priorityParentLeadCount": counts.get("priorityParentLeadCount"),
        "exportedPriorityParentLeadCount": counts.get("exportedPriorityParentLeadCount"),
        "modulePointerHitCount": counts.get("modulePointerHitCount"),
        "ownerFamilyCount": counts.get("ownerFamilyCount"),
        "parentSlotFamilyCount": counts.get("parentSlotFamilyCount"),
        "contextKindCounts": document.get("contextKindCounts"),
        "priorityParentLeadTargetsJson": document.get("priorityParentLeadTargetsJson"),
        "warnings": safe_list(document.get("warnings")),
        "blockers": safe_list(document.get("blockers")),
    }


def target_identity_from_scan(document: Mapping[str, Any]) -> dict[str, Any]:
    target = safe_dict(document.get("target"))
    return {
        "processName": first_present(target.get("processName"), target.get("process")),
        "pid": first_present(target.get("pid"), target.get("processId")),
        "hwnd": normalize_hwnd(first_present(target.get("hwndHex"), target.get("hwnd"), target.get("targetWindowHandle"))),
        "startTimeUtc": target.get("startTimeUtc"),
        "moduleBaseAddressHex": hex_or_none(first_present(target.get("moduleBaseAddressHex"), target.get("moduleBaseAddress"))),
    }


def summarize_pointer_scan(path: Path, document: Mapping[str, Any], repo_root: Path) -> dict[str, Any]:
    counts = safe_dict(document.get("counts"))
    ranked_targets = safe_list(document.get("rankedTargets"))
    total_hits = sum(int(target.get("hitCount") or 0) for target in ranked_targets if isinstance(target, dict))
    module_hits = sum(int(target.get("moduleHitCount") or 0) for target in ranked_targets if isinstance(target, dict))
    rift_module_hits = sum(int(target.get("riftModuleHitCount") or 0) for target in ranked_targets if isinstance(target, dict))
    targets_with_hits = sum(1 for target in ranked_targets if isinstance(target, dict) and int(target.get("hitCount") or 0) > 0)
    top_target = ranked_targets[0] if ranked_targets and isinstance(ranked_targets[0], dict) else None
    return {
        "path": path_text(path, repo_root),
        "status": document.get("status"),
        "generatedAtUtc": document.get("generatedAtUtc"),
        "target": target_identity_from_scan(document),
        "seedCount": counts.get("seedCount"),
        "scannedTargetCount": counts.get("scannedTargetCount"),
        "queuedTargetCount": counts.get("queuedTargetCount"),
        "rankedTargetCount": len(ranked_targets),
        "targetsWithHits": targets_with_hits,
        "totalHits": total_hits,
        "moduleHitCount": module_hits,
        "riftModuleHitCount": rift_module_hits,
        "topTarget": {
            "target": top_target.get("target"),
            "label": top_target.get("targetLabel"),
            "hitCount": top_target.get("hitCount"),
            "moduleHitCount": top_target.get("moduleHitCount"),
            "riftModuleHitCount": top_target.get("riftModuleHitCount"),
        }
        if top_target
        else None,
        "warnings": safe_list(document.get("warnings")),
        "blockers": safe_list(document.get("blockers")),
    }


def same_target_identity(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> list[str]:
    mismatches: list[str] = []
    expected_pid = expected.get("pid")
    if expected_pid is not None and observed.get("pid") is not None and int(expected_pid) != int(observed["pid"]):
        mismatches.append(f"pid:{expected_pid}!={observed['pid']}")
    expected_hwnd = normalize_hwnd(expected.get("hwnd"))
    observed_hwnd = normalize_hwnd(observed.get("hwnd"))
    if expected_hwnd and observed_hwnd and expected_hwnd != observed_hwnd:
        mismatches.append(f"hwnd:{expected_hwnd}!={observed_hwnd}")
    expected_process = str(expected.get("processName") or "").lower().removesuffix(".exe")
    observed_process = str(observed.get("processName") or "").lower().removesuffix(".exe")
    if expected_process and observed_process and expected_process != observed_process:
        mismatches.append(f"processName:{expected_process}!={observed_process}")
    expected_start = expected.get("startTimeUtc")
    if expected_start and observed.get("startTimeUtc") and str(expected_start) != str(observed["startTimeUtc"]):
        mismatches.append(f"startTimeUtc:{expected_start}!={observed['startTimeUtc']}")
    expected_module = hex_or_none(expected.get("moduleBaseAddressHex"))
    observed_module = hex_or_none(observed.get("moduleBaseAddressHex"))
    if expected_module and observed_module and expected_module != observed_module:
        mismatches.append(f"moduleBase:{expected_module}!={observed_module}")
    return mismatches


def aggregate_scan_totals(scans: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    scan_list = list(scans)
    return {
        "scanCount": len(scan_list),
        "scannedTargetCount": sum(int(scan.get("scannedTargetCount") or 0) for scan in scan_list),
        "queuedTargetCount": sum(int(scan.get("queuedTargetCount") or 0) for scan in scan_list),
        "targetsWithHits": sum(int(scan.get("targetsWithHits") or 0) for scan in scan_list),
        "totalHits": sum(int(scan.get("totalHits") or 0) for scan in scan_list),
        "moduleHitCount": sum(int(scan.get("moduleHitCount") or 0) for scan in scan_list),
        "riftModuleHitCount": sum(int(scan.get("riftModuleHitCount") or 0) for scan in scan_list),
    }


def infer_verdict(classifiers: Sequence[Mapping[str, Any]], scans: Sequence[Mapping[str, Any]]) -> str:
    if not classifiers:
        return "blocked-no-classifier"
    if not scans:
        return "blocked-no-pointer-scans"
    latest_classifier = classifiers[-1]
    priority_total = latest_classifier.get("priorityParentLeadCount")
    exported_total = sum(int(classifier.get("exportedPriorityParentLeadCount") or 0) for classifier in classifiers)
    totals = aggregate_scan_totals(scans)
    if int(totals["riftModuleHitCount"]) > 0 or int(totals["moduleHitCount"]) > 0:
        return "candidate-static-root-hits-present"
    if priority_total is not None and exported_total >= int(priority_total):
        return "priority-lane-exhausted-no-static-root"
    return "priority-lane-partial-no-static-root"


def markdown_summary(summary: Mapping[str, Any]) -> str:
    totals = safe_dict(summary.get("totals"))
    lines = [
        "# Priority scan exhaustion report",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Candidate-only: `{str(safe_dict(summary.get('safety')).get('candidateOnly')).lower()}`",
        f"- Movement sent: `{str(safe_dict(summary.get('safety')).get('movementSent')).lower()}`",
        (
            "- Process memory read by this helper: "
            f"`{str(safe_dict(summary.get('safety')).get('processMemoryReadByThisHelper')).lower()}`"
        ),
        (
            "- Summarized pointer scans were read-only memory scans: "
            f"`{str(safe_dict(summary.get('safety')).get('summarizedPointerScansReadOnlyProcessMemory')).lower()}`"
        ),
        "",
        "## Totals",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Classifier artifacts | `{totals.get('classifierCount')}` |",
        f"| Pointer scan artifacts | `{totals.get('scanCount')}` |",
        f"| Exported priority leads | `{totals.get('exportedPriorityParentLeadCount')}` |",
        f"| Latest priority parent leads | `{totals.get('latestPriorityParentLeadCount')}` |",
        f"| Scanned targets | `{totals.get('scannedTargetCount')}` |",
        f"| Targets with heap hits | `{totals.get('targetsWithHits')}` |",
        f"| Total heap hits | `{totals.get('totalHits')}` |",
        f"| Module hits | `{totals.get('moduleHitCount')}` |",
        f"| RIFT module hits | `{totals.get('riftModuleHitCount')}` |",
        "",
        "## Classifier windows",
        "",
        "| Path | Offset | Exported | Priority total |",
        "|---|---:|---:|---:|",
    ]
    for classifier in safe_list(summary.get("classifiers")):
        lines.append(
            f"| `{classifier.get('path')}` | `{classifier.get('priorityOffset')}` | "
            f"`{classifier.get('exportedPriorityParentLeadCount')}` | "
            f"`{classifier.get('priorityParentLeadCount')}` |"
        )
    lines.extend(["", "## Pointer scans", "", "| Path | Scanned | Targets with hits | Hits | Module hits | RIFT module hits | Top target |", "|---|---:|---:|---:|---:|---:|---|"])
    for scan in safe_list(summary.get("pointerScans")):
        top = safe_dict(scan.get("topTarget"))
        lines.append(
            f"| `{scan.get('path')}` | `{scan.get('scannedTargetCount')}` | "
            f"`{scan.get('targetsWithHits')}` | `{scan.get('totalHits')}` | "
            f"`{scan.get('moduleHitCount')}` | `{scan.get('riftModuleHitCount')}` | "
            f"`{top.get('target')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in safe_list(summary.get("warnings")))
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"priority-scan-exhaustion-report-{utc_stamp()}"
    output_root = output_root.resolve()
    blockers: list[str] = []
    warnings: list[str] = []

    classifiers: list[dict[str, Any]] = []
    for path in args.classifier_json:
        try:
            classifiers.append(summarize_classifier(path, load_json_object(path), repo_root))
        except Exception as exc:
            blockers.append(f"classifier-read-failed:{path}:{type(exc).__name__}:{exc}")

    pointer_scans: list[dict[str, Any]] = []
    expected_target = {
        "processName": args.process_name,
        "pid": args.target_pid,
        "hwnd": args.target_hwnd,
        "startTimeUtc": args.expected_start_time_utc,
        "moduleBaseAddressHex": args.expected_module_base,
    }
    for path in args.pointer_scan_json:
        try:
            scan = summarize_pointer_scan(path, load_json_object(path), repo_root)
        except Exception as exc:
            blockers.append(f"pointer-scan-read-failed:{path}:{type(exc).__name__}:{exc}")
            continue
        mismatches = same_target_identity(expected_target, safe_dict(scan.get("target")))
        if mismatches:
            blockers.append(f"pointer-scan-target-mismatch:{path}:{';'.join(mismatches)}")
        pointer_scans.append(scan)

    if not classifiers:
        blockers.append("no-classifier-json")
    if not pointer_scans:
        blockers.append("no-pointer-scan-json")

    scan_totals = aggregate_scan_totals(pointer_scans)
    latest_priority_total = classifiers[-1].get("priorityParentLeadCount") if classifiers else None
    exported_total = sum(int(classifier.get("exportedPriorityParentLeadCount") or 0) for classifier in classifiers)
    totals = {
        "classifierCount": len(classifiers),
        "scanCount": len(pointer_scans),
        "latestPriorityParentLeadCount": latest_priority_total,
        "exportedPriorityParentLeadCount": exported_total,
        **scan_totals,
    }
    if latest_priority_total is not None and exported_total < int(latest_priority_total):
        warnings.append(f"priority-export-coverage-partial:{exported_total}<{latest_priority_total}")

    status = "passed" if not blockers else "blocked"
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "priority-scan-exhaustion-report",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": infer_verdict(classifiers, pointer_scans) if status == "passed" else "blocked",
        "target": expected_target,
        "totals": totals,
        "classifiers": classifiers,
        "pointerScans": pointer_scans,
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "x64dbgAttached": False,
            "cheatEngineUsed": False,
            "processMemoryReadByThisHelper": False,
            "summarizedPointerScansReadOnlyProcessMemory": bool(pointer_scans),
            "targetMemoryWritten": False,
            "candidateOnly": True,
            "promotionEligible": False,
        },
        "next": {
            "recommendedAction": "Restore a fresh API/reference surface before proof promotion; otherwise widen lower-priority families in bounded explicit batches.",
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(summary_json, summary)
    write_text_atomic(summary_md, markdown_summary(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate priority classifier windows and pointer scans into an exhaustion report.")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--classifier-json", type=Path, action="append", required=True)
    parser.add_argument("--pointer-scan-json", type=Path, action="append", required=True)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--target-hwnd", required=True)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--expected-start-time-utc")
    parser.add_argument("--expected-module-base")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_summary(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "verdict": summary["verdict"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "totals": summary["totals"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"verdict={summary['verdict']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        if summary["blockers"]:
            print("blockers:")
            for blocker in summary["blockers"]:
                print(f"  - {blocker}")
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
