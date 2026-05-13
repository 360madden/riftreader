from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def positive_exact_targets(counts: Mapping[str, Any], targets: Sequence[Any]) -> list[dict[str, Any]]:
    by_address: dict[str, Any] = {}
    for target in targets:
        if not isinstance(target, Mapping):
            continue
        address = str(target.get("address"))
        by_address[address] = target
    rows: list[dict[str, Any]] = []
    for address, count in counts.items():
        try:
            parsed_count = int(count)
        except (TypeError, ValueError):
            parsed_count = 0
        if parsed_count <= 0:
            continue
        target = safe_mapping(by_address.get(str(address)))
        rows.append({"address": str(address), "label": target.get("label"), "count": parsed_count})
    return rows


def module_rvas(entries: Sequence[Any]) -> list[str]:
    rvas: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        classification = safe_mapping(entry.get("classification"))
        module_pointer = safe_mapping(classification.get("modulePointer"))
        rva = module_pointer.get("rva")
        if rva and str(rva) not in rvas:
            rvas.append(str(rva))
    return rvas


def summarize_slot(path: Path, doc: Mapping[str, Any]) -> dict[str, Any]:
    analysis = safe_mapping(doc.get("analysis"))
    exact_targets = positive_exact_targets(
        safe_mapping(analysis.get("exactTargetCounts")),
        safe_list(doc.get("targets")),
    )
    owner_window = safe_list(analysis.get("ownerWindow"))
    owner_window_interesting = [
        entry
        for entry in owner_window
        if isinstance(entry, Mapping) and safe_mapping(entry.get("classification")).get("interesting")
    ]
    owner_window_module_entries = safe_list(analysis.get("ownerWindowModulePointers"))
    row = {
        "summaryJson": str(path.resolve()),
        "status": doc.get("status"),
        "ownerSlot": safe_mapping(doc.get("owner")).get("address"),
        "ownerRegionBase": safe_mapping(doc.get("ownerRegion")).get("baseAddress"),
        "targetWindowBase": safe_mapping(doc.get("targetWindow")).get("baseAddress"),
        "regionMatchCount": analysis.get("regionMatchCount"),
        "modulePointerCount": analysis.get("modulePointerCount"),
        "ownerWindowModulePointerCount": analysis.get("ownerWindowModulePointerCount"),
        "ownerWindowModuleRvas": module_rvas(owner_window_module_entries),
        "exactTargets": exact_targets,
        "ownerWindowInterestingCount": len(owner_window_interesting),
        "ownerWindowInteresting": owner_window_interesting[:32],
    }
    if exact_targets and row["ownerWindowModulePointerCount"]:
        row["classification"] = "owner-slot-with-module-hint"
    elif exact_targets:
        row["classification"] = "owner-slot-heap-only"
    else:
        row["classification"] = "no-exact-owner-slot"
    return row


def build_summary(paths: Sequence[Path]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        try:
            rows.append(summarize_slot(path, load_json_object(path)))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}:{type(exc).__name__}:{exc}")
    rows.sort(
        key=lambda row: (
            0 if row.get("classification") == "owner-slot-with-module-hint" else 1,
            0 if row.get("classification") == "owner-slot-heap-only" else 1,
            str(row.get("ownerSlot")),
        )
    )
    module_hint_count = sum(1 for row in rows if row.get("ownerWindowModulePointerCount"))
    exact_owner_count = sum(1 for row in rows if row.get("exactTargets"))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "parent-slot-neighborhood-summary",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "passed",
        "blockers": [],
        "warnings": [
            "Offline artifact comparison only; this does not promote coordinate truth or navigation movement.",
            "Module pointers near owner slots are source-chain clues, not static root proof by themselves.",
        ],
        "errors": errors,
        "counts": {
            "slotSummaryCount": len(rows),
            "exactOwnerSlotCount": exact_owner_count,
            "moduleHintSlotCount": module_hint_count,
        },
        "slots": rows,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "githubConnectorWrites": False,
            "candidateOnly": True,
            "movementProofEligible": False,
        },
        "next": {
            "recommendedAction": "Use module-hint owner slots as source-chain leads only; require proof/static validation before promotion.",
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Parent slot neighborhood summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Slot summaries: `{safe_mapping(summary.get('counts')).get('slotSummaryCount')}`",
        f"- Exact owner slots: `{safe_mapping(summary.get('counts')).get('exactOwnerSlotCount')}`",
        f"- Module-hint slots: `{safe_mapping(summary.get('counts')).get('moduleHintSlotCount')}`",
        "",
        "| Owner slot | Classification | Exact target | Region matches | Owner-window module RVAs |",
        "|---|---|---|---:|---|",
    ]
    for slot in safe_list(summary.get("slots")):
        if not isinstance(slot, Mapping):
            continue
        exact = ", ".join(
            f"{target.get('address')}:{target.get('label')}"
            for target in safe_list(slot.get("exactTargets"))
            if isinstance(target, Mapping)
        )
        rvas = ", ".join(str(rva) for rva in safe_list(slot.get("ownerWindowModuleRvas")))
        lines.append(
            f"| `{slot.get('ownerSlot')}` | `{slot.get('classification')}` | `{exact}` | "
            f"`{slot.get('regionMatchCount')}` | `{rvas}` |"
        )
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in summary.get("warnings", []))
    if summary.get("errors"):
        lines.extend(["", "## Errors"])
        lines.extend(f"- `{error}`" for error in summary.get("errors", []))
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize pointer-owner neighborhood artifacts for parent-slot source-chain clues.")
    parser.add_argument("--slot-summary-json", action="append", type=Path, default=[], required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"parent-slot-neighborhood-summary-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary = build_summary(args.slot_summary_json)
    summary["repoRoot"] = str(repo_root)
    summary["artifacts"] = {"runDirectory": str(run_dir), "summaryJson": str(summary_json), "summaryMarkdown": str(summary_md)}
    write_json(summary_json, summary)
    write_text_atomic(summary_md, render_markdown(summary))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"status={summary.get('status')} summary={summary_json}")
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
