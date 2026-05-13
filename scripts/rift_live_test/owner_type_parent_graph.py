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


def parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip(), 0)
        except ValueError:
            return None
    return None


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):X}"


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def pointer_targets_by_address(pointer_summary: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for item in safe_list(pointer_summary.get("rankedTargets")):
        if not isinstance(item, Mapping):
            continue
        target = parse_int(item.get("target"))
        if target is None:
            continue
        result[target] = item
    return result


def hit_addresses(scan_item: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for hit in safe_list(scan_item.get("hits")):
        if not isinstance(hit, Mapping):
            continue
        address = parse_int(hit.get("address") or hit.get("Address") or hit.get("AddressHex"))
        if address is None:
            continue
        result.append(
            {
                "address": int_hex(address),
                "addressInt": address,
                "regionBase": hit.get("regionBase") or hit.get("RegionBaseHex"),
                "module": hit.get("module"),
                "asciiPreview": hit.get("asciiPreview"),
            }
        )
    return result


def classify_owner(row: Mapping[str, Any]) -> str:
    if row.get("coordPointerIsCandidate") and row.get("parentRefCount") == 1 and row.get("parentRefParentHitCount") == 0:
        return "candidate-owner-heap-terminal"
    if row.get("coordPointerIsCandidate"):
        return "candidate-owner-parent-search-needed"
    if row.get("coordPointerVec3"):
        return "coord-like-sibling"
    return "type-instance-noncoord-or-zero"


def build_graph(owner_summary: Mapping[str, Any], pointer_summary: Mapping[str, Any]) -> dict[str, Any]:
    by_target = pointer_targets_by_address(pointer_summary)
    owner_rows: list[dict[str, Any]] = []
    for instance in safe_list(owner_summary.get("instances")):
        if not isinstance(instance, Mapping):
            continue
        owner_base = parse_int(instance.get("ownerBase"))
        if owner_base is None:
            continue
        scan_item = by_target.get(owner_base, {})
        refs = hit_addresses(scan_item)
        ref_parent_hit_count = 0
        ref_rows: list[dict[str, Any]] = []
        for ref in refs:
            ref_addr = parse_int(ref.get("address"))
            parent_scan = by_target.get(ref_addr or -1, {})
            parent_hits = hit_addresses(parent_scan)
            ref_parent_hit_count += len(parent_hits)
            ref_rows.append({**ref, "parentHitCount": len(parent_hits), "parentHits": parent_hits[:8]})
        candidate = instance.get("coordPointerCandidate") if isinstance(instance.get("coordPointerCandidate"), Mapping) else None
        row = {
            "ownerBase": instance.get("ownerBase"),
            "coordPointer": instance.get("coordPointer"),
            "coordPointerStorage": instance.get("coordPointerStorage"),
            "coordPointerIsCandidate": bool(instance.get("coordPointerIsCandidate")),
            "coordPointerCandidateLabel": candidate.get("label") if candidate else None,
            "coordPointerVec3": instance.get("coordPointerVec3") if isinstance(instance.get("coordPointerVec3"), Mapping) else None,
            "parentRefCount": len(refs),
            "parentRefs": ref_rows,
            "parentRefParentHitCount": ref_parent_hit_count,
            "pointerScanHitCount": scan_item.get("hitCount"),
            "pointerScanArtifact": scan_item.get("artifactPath"),
        }
        row["classification"] = classify_owner(row)
        owner_rows.append(row)
    owner_rows.sort(
        key=lambda row: (
            0 if row.get("coordPointerIsCandidate") else 1,
            int(row.get("parentRefCount") or 0),
            str(row.get("ownerBase")),
        )
    )
    candidate_owners = [row for row in owner_rows if row.get("coordPointerIsCandidate")]
    terminal_candidates = [row for row in candidate_owners if row.get("classification") == "candidate-owner-heap-terminal"]
    return {
        "ownerCount": len(owner_rows),
        "candidateOwnerCount": len(candidate_owners),
        "terminalCandidateOwnerCount": len(terminal_candidates),
        "coordLikeSiblingCount": sum(1 for row in owner_rows if row.get("coordPointerVec3")),
        "owners": owner_rows,
    }


def build_summary(owner_summary_json: Path, pointer_summary_json: Path) -> dict[str, Any]:
    owner_summary = load_json_object(owner_summary_json)
    pointer_summary = load_json_object(pointer_summary_json)
    graph = build_graph(owner_summary, pointer_summary)
    warnings = [
        "Offline artifact comparison only; this does not promote coordinate truth or navigation movement.",
        "Heap-terminal candidate owners still require a static/root parent or restart validation before use.",
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "owner-type-parent-graph",
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "blockers": [],
        "warnings": warnings,
        "errors": [],
        "inputs": {
            "ownerSummaryJson": str(owner_summary_json.resolve()),
            "pointerSummaryJson": str(pointer_summary_json.resolve()),
        },
        "counts": {
            "ownerCount": graph["ownerCount"],
            "candidateOwnerCount": graph["candidateOwnerCount"],
            "terminalCandidateOwnerCount": graph["terminalCandidateOwnerCount"],
            "coordLikeSiblingCount": graph["coordLikeSiblingCount"],
        },
        "owners": graph["owners"],
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
            "recommendedAction": "Search for a durable/static parent above heap-terminal candidate owners; do not navigate until ProofOnly passes.",
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Owner type parent graph",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Owners: `{summary.get('counts', {}).get('ownerCount')}`",
        f"- Candidate owners: `{summary.get('counts', {}).get('candidateOwnerCount')}`",
        f"- Heap-terminal candidate owners: `{summary.get('counts', {}).get('terminalCandidateOwnerCount')}`",
        "",
        "| Owner base | Coord pointer | Classification | Parent refs | Parent-parent hits | Candidate |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in safe_list(summary.get("owners")):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"| `{row.get('ownerBase')}` | `{row.get('coordPointer')}` | `{row.get('classification')}` | "
            f"`{row.get('parentRefCount')}` | `{row.get('parentRefParentHitCount')}` | "
            f"`{row.get('coordPointerCandidateLabel')}` |"
        )
    lines.extend(["", "## Parent refs", ""])
    for row in safe_list(summary.get("owners")):
        if not isinstance(row, Mapping):
            continue
        refs = safe_list(row.get("parentRefs"))
        if not refs:
            continue
        lines.append(f"### `{row.get('ownerBase')}`")
        for ref in refs:
            if isinstance(ref, Mapping):
                lines.append(f"- `{ref.get('address')}` parent hits: `{ref.get('parentHitCount')}`")
        lines.append("")
    if summary.get("warnings"):
        lines.extend(["## Warnings"])
        lines.extend(f"- {warning}" for warning in summary.get("warnings", []))
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize owner/type instance parent refs from offline/read-only artifacts.")
    parser.add_argument("--owner-summary-json", type=Path, required=True)
    parser.add_argument("--pointer-summary-json", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"owner-type-parent-graph-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    try:
        summary = build_summary(args.owner_summary_json, args.pointer_summary_json)
        status_code = 0
    except Exception as exc:  # noqa: BLE001 - CLI must preserve diagnosis.
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "owner-type-parent-graph",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "blockers": [],
            "warnings": [],
            "errors": [f"{type(exc).__name__}:{exc}"],
            "safety": {
                "movementSent": False,
                "inputSent": False,
                "noCheatEngine": True,
                "x64dbgLaunched": False,
                "targetMemoryBytesRead": False,
                "targetMemoryBytesWritten": False,
                "providerWrites": False,
                "githubConnectorWrites": False,
            },
        }
        status_code = 1
    summary["repoRoot"] = str(repo_root)
    summary["artifacts"] = {"runDirectory": str(run_dir), "summaryJson": str(summary_json), "summaryMarkdown": str(summary_md)}
    write_json(summary_json, summary)
    write_text_atomic(summary_md, render_markdown(summary))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"status={summary.get('status')} summary={summary_json}")
    return status_code


if __name__ == "__main__":
    raise SystemExit(main())
