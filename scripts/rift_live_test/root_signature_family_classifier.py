from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parent_slot_neighborhood_summary import safe_list, safe_mapping
from .parent_slot_root_signature_packet import norm_hex, parse_int
from .reports import write_json, write_text_atomic
from .root_signature_module_hint_sweep import (
    field_mismatch_warnings,
    heap_like,
    summarize_hits,
)


SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def resolve_path(value: Any, *, base: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = base / path
    return path


def field_offsets(candidate: Mapping[str, Any], *, matched: bool) -> list[str]:
    offsets: list[str] = []
    for field in safe_list(candidate.get("fieldMatches")):
        if isinstance(field, Mapping) and bool(field.get("matched")) is matched:
            offset = str(field.get("offsetFromOwner"))
            if offset not in offsets:
                offsets.append(offset)
    return offsets


def pointer_class(value: Any, *, known: int | None, module_base: int | None) -> str:
    parsed = parse_int(value)
    if parsed is None:
        return "missing"
    if parsed == 0:
        return "zero"
    if known is not None and parsed == known:
        return "known"
    if module_base is not None and parsed >= module_base:
        return "module-or-static"
    if module_base is not None and heap_like(parsed, module_base):
        return "heap-like"
    return "other"


def region_hex(value: Any, *, size: int = 0x10000) -> str | None:
    parsed = parse_int(value)
    if parsed is None:
        return None
    return f"0x{parsed - (parsed % size):X}"


def candidate_score(candidate: Mapping[str, Any]) -> int:
    score = parse_int(candidate.get("score"))
    return int(score or 0)


def owner_family_key(candidate: Mapping[str, Any], *, known_coord_pointer: int | None, module_base: int | None) -> str:
    matched = ",".join(field_offsets(candidate, matched=True)) or "none"
    coord_class = pointer_class(candidate.get("coordPointer"), known=known_coord_pointer, module_base=module_base)
    return f"matched={matched}|coord={coord_class}"


def parent_family_key(candidate: Mapping[str, Any], *, known_owner: int | None, module_base: int | None) -> str:
    owner_class = pointer_class(candidate.get("ownerPointer"), known=known_owner, module_base=module_base)
    return f"offset={candidate.get('selectedParentSlotOffset')}|ownerPointer={owner_class}"


def build_families(
    candidates: Sequence[Mapping[str, Any]],
    *,
    key_fn: Callable[[Mapping[str, Any]], str],
    sample_limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[key_fn(candidate)].append(candidate)

    rows: list[dict[str, Any]] = []
    for key, group in grouped.items():
        ranked = sorted(group, key=lambda item: (-candidate_score(item), str(item.get("hitAddress"))))
        top = dict(ranked[0]) if ranked else {}
        top_score = candidate_score(top)
        rows.append(
            {
                "familyKey": key,
                "count": len(group),
                "topScore": top_score,
                "familyScore": top_score + min(len(group), 100),
                "topCandidate": top,
                "hitRegions": sorted(
                    {
                        region
                        for region in (region_hex(candidate.get("hitAddress")) for candidate in group)
                        if region is not None
                    }
                )[:sample_limit],
                "examples": [dict(candidate) for candidate in ranked[:sample_limit]],
                "candidateOnly": True,
                "promotionEligible": False,
            }
        )
    return sorted(rows, key=lambda row: (-int(row.get("familyScore") or 0), -int(row.get("topScore") or 0), str(row.get("familyKey"))))


def parent_region_clusters(candidates: Sequence[Mapping[str, Any]], *, sample_limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        region = region_hex(candidate.get("ownerPointer")) or "missing"
        grouped[region].append(candidate)
    rows: list[dict[str, Any]] = []
    for region, group in grouped.items():
        ranked = sorted(group, key=lambda item: (-candidate_score(item), str(item.get("parentSlot"))))
        top = dict(ranked[0]) if ranked else {}
        rows.append(
            {
                "ownerPointerRegion": region,
                "count": len(group),
                "topScore": candidate_score(top),
                "topCandidate": top,
                "examples": [dict(candidate) for candidate in ranked[:sample_limit]],
            }
        )
    return sorted(rows, key=lambda row: (-int(row.get("count") or 0), -int(row.get("topScore") or 0), str(row.get("ownerPointerRegion"))))


def strong_parent_leads(candidates: Sequence[Mapping[str, Any]], *, known_parent_slot: int | None, limit: int) -> list[dict[str, Any]]:
    leads: list[Mapping[str, Any]] = []
    for candidate in candidates:
        parent_slot = parse_int(candidate.get("parentSlot"))
        if known_parent_slot is not None and parent_slot == known_parent_slot:
            continue
        if candidate_score(candidate) <= 0:
            continue
        leads.append(candidate)
    ranked = sorted(leads, key=lambda item: (-candidate_score(item), str(item.get("parentSlot"))))
    return [dict(item) for item in ranked[:limit]]


def build_summary(
    *,
    module_hint_sweep_path: Path,
    root_signature_path: Path | None = None,
    sample_limit: int = 8,
    lead_limit: int = 24,
) -> dict[str, Any]:
    repo_root = repo_root_from_module()
    sweep = load_json_object(module_hint_sweep_path)
    artifacts = safe_mapping(sweep.get("artifacts"))
    raw_scan_path = resolve_path(artifacts.get("rawScanJson"), base=repo_root)
    if raw_scan_path is None:
        raw_scan_path = resolve_path(artifacts.get("rawScanJson"), base=module_hint_sweep_path.parent)
    root_path = root_signature_path or resolve_path(safe_mapping(sweep.get("inputs")).get("rootSignatureJson"), base=repo_root)

    blockers: list[str] = []
    warnings: list[str] = []
    if raw_scan_path is None or not raw_scan_path.is_file():
        blockers.append(f"raw-scan-json-missing:{raw_scan_path}")
    if root_path is None or not root_path.is_file():
        blockers.append(f"root-signature-json-missing:{root_path}")

    root_packet: dict[str, Any] = {}
    raw_scan: dict[str, Any] = {}
    if not blockers:
        root_packet = load_json_object(root_path)  # type: ignore[arg-type]
        raw_scan = load_json_object(raw_scan_path)  # type: ignore[arg-type]

    target = safe_mapping(sweep.get("target"))
    process_details = safe_mapping(target.get("processDetails"))
    module_base = parse_int(process_details.get("moduleBaseAddressHex") or safe_mapping(sweep.get("inputs")).get("moduleBase"))
    selected_rva = parse_int(safe_mapping(sweep.get("inputs")).get("selectedRva"))
    if module_base is None and not blockers:
        blockers.append("module-base-missing")
    if selected_rva is None and not blockers:
        blockers.append("selected-rva-missing")

    signature = safe_mapping(root_packet.get("signature"))
    known_coord_pointer = parse_int(signature.get("coordPointer"))
    known_owner = parse_int(signature.get("ownerBase"))
    known_parent_slot = parse_int(signature.get("parentSlot") or safe_mapping(root_packet.get("rootSearch")).get("rootGapAbove"))

    if blockers:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "root-signature-family-classifier",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "blockers": blockers,
            "warnings": warnings,
            "inputs": {
                "moduleHintSweepJson": str(module_hint_sweep_path.resolve()),
                "rootSignatureJson": str(root_path.resolve()) if root_path else None,
                "rawScanJson": str(raw_scan_path.resolve()) if raw_scan_path else None,
            },
            "safety": safety_contract(),
        }

    analyzed = summarize_hits(
        root_packet=root_packet,
        scan=raw_scan,
        module_base=module_base or 0,
        selected_rva=selected_rva or 0,
    )
    owner_candidates = [candidate for candidate in safe_list(analyzed.get("ownerFieldCandidates")) if isinstance(candidate, Mapping)]
    parent_candidates = [candidate for candidate in safe_list(analyzed.get("parentSlotCandidates")) if isinstance(candidate, Mapping)]
    owner_families = build_families(
        owner_candidates,
        key_fn=lambda candidate: owner_family_key(candidate, known_coord_pointer=known_coord_pointer, module_base=module_base),
        sample_limit=sample_limit,
    )
    parent_families = build_families(
        parent_candidates,
        key_fn=lambda candidate: parent_family_key(candidate, known_owner=known_owner, module_base=module_base),
        sample_limit=sample_limit,
    )
    parent_clusters = parent_region_clusters(parent_candidates, sample_limit=sample_limit)
    top_owner = analyzed.get("topOwnerFieldCandidate")
    warnings.extend(field_mismatch_warnings(top_owner if isinstance(top_owner, Mapping) else None))
    if warnings:
        warnings = list(dict.fromkeys(warnings))

    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "root-signature-family-classifier",
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "blockers": [],
        "warnings": warnings,
        "inputs": {
            "moduleHintSweepJson": str(module_hint_sweep_path.resolve()),
            "rootSignatureJson": str(root_path.resolve()) if root_path else None,
            "rawScanJson": str(raw_scan_path.resolve()) if raw_scan_path else None,
            "moduleBase": f"0x{module_base:X}" if module_base is not None else None,
            "selectedRva": f"0x{selected_rva:X}" if selected_rva is not None else None,
            "sampleLimit": sample_limit,
            "leadLimit": lead_limit,
        },
        "counts": {
            "modulePointerHitCount": int(raw_scan.get("HitCount") or len(safe_list(raw_scan.get("Hits")))),
            "ownerFieldCandidateCount": len(owner_candidates),
            "parentSlotCandidateCount": len(parent_candidates),
            "ownerFamilyCount": len(owner_families),
            "parentSlotFamilyCount": len(parent_families),
            "parentOwnerPointerRegionClusterCount": len(parent_clusters),
            "nonPlayerParentLeadCount": len(strong_parent_leads(parent_candidates, known_parent_slot=known_parent_slot, limit=10_000)),
        },
        "knownChain": {
            "parentSlot": norm_hex(known_parent_slot),
            "ownerBase": norm_hex(known_owner),
            "coordPointer": norm_hex(known_coord_pointer),
            "topOwnerFieldCandidate": top_owner,
            "topParentSlotCandidate": analyzed.get("topParentSlotCandidate"),
        },
        "ownerFamilies": owner_families,
        "parentSlotFamilies": parent_families,
        "parentOwnerPointerRegionClusters": parent_clusters[:lead_limit],
        "nonPlayerParentSlotLeads": strong_parent_leads(parent_candidates, known_parent_slot=known_parent_slot, limit=lead_limit),
        "safety": safety_contract(),
        "next": {
            "recommendedAction": "Use the non-player parent-slot leads and owner-pointer region clusters as broad family/container search seeds; keep all outputs candidate-only until restart and fresh API proof pass.",
        },
    }


def safety_contract() -> dict[str, Any]:
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgLaunched": False,
        "debuggerAttached": False,
        "breakpointsSet": False,
        "targetMemoryBytesRead": False,
        "targetMemoryBytesWritten": False,
        "offlineArtifactOnly": True,
        "providerWrites": False,
        "githubConnectorWrites": False,
        "candidateOnly": True,
        "movementProofEligible": False,
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    counts = safe_mapping(summary.get("counts"))
    known = safe_mapping(summary.get("knownChain"))
    lines = [
        "# Root-signature family classifier",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Module-pointer hits: `{counts.get('modulePointerHitCount')}`",
        f"- Owner families: `{counts.get('ownerFamilyCount')}`",
        f"- Parent-slot families: `{counts.get('parentSlotFamilyCount')}`",
        f"- Non-player parent leads: `{counts.get('nonPlayerParentLeadCount')}`",
        f"- Known parent slot: `{known.get('parentSlot')}`",
        f"- Known owner: `{known.get('ownerBase')}`",
        f"- Known coord pointer: `{known.get('coordPointer')}`",
        "",
        "## Owner-field families",
        "",
        "| Rank | Family score | Count | Top score | Key | Top owner | Top coord pointer |",
        "|---:|---:|---:|---:|---|---|---|",
    ]
    for index, family in enumerate(safe_list(summary.get("ownerFamilies"))[:12], start=1):
        if not isinstance(family, Mapping):
            continue
        top = safe_mapping(family.get("topCandidate"))
        lines.append(
            f"| {index} | `{family.get('familyScore')}` | `{family.get('count')}` | `{family.get('topScore')}` | "
            f"`{family.get('familyKey')}` | `{top.get('ownerBase')}` | `{top.get('coordPointer')}` |"
        )
    lines.extend(
        [
            "",
            "## Parent-slot families",
            "",
            "| Rank | Family score | Count | Top score | Key | Top parent slot | Top owner pointer |",
            "|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for index, family in enumerate(safe_list(summary.get("parentSlotFamilies"))[:12], start=1):
        if not isinstance(family, Mapping):
            continue
        top = safe_mapping(family.get("topCandidate"))
        lines.append(
            f"| {index} | `{family.get('familyScore')}` | `{family.get('count')}` | `{family.get('topScore')}` | "
            f"`{family.get('familyKey')}` | `{top.get('parentSlot')}` | `{top.get('ownerPointer')}` |"
        )
    lines.extend(
        [
            "",
            "## Non-player parent-slot leads",
            "",
            "| Rank | Score | Parent slot | Owner pointer | Hit | Reasons |",
            "|---:|---:|---|---|---|---|",
        ]
    )
    for index, lead in enumerate(safe_list(summary.get("nonPlayerParentSlotLeads"))[:16], start=1):
        if not isinstance(lead, Mapping):
            continue
        reasons = ", ".join(str(reason) for reason in safe_list(lead.get("scoreReasons")))
        lines.append(
            f"| {index} | `{lead.get('score')}` | `{lead.get('parentSlot')}` | `{lead.get('ownerPointer')}` | "
            f"`{lead.get('hitAddress')}` | {reasons} |"
        )
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in safe_list(summary.get("warnings")))
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "Offline artifact classification only. No live memory read, movement, input, x64dbg, Cheat Engine, provider writes, or proof promotion.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify root-signature module-hint sweep hits into structural families.")
    parser.add_argument("--module-hint-sweep-json", type=Path, required=True)
    parser.add_argument("--root-signature-json", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--sample-limit", type=int, default=8)
    parser.add_argument("--lead-limit", type=int, default=24)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"root-signature-family-classifier-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary = build_summary(
        module_hint_sweep_path=args.module_hint_sweep_json,
        root_signature_path=args.root_signature_json,
        sample_limit=args.sample_limit,
        lead_limit=args.lead_limit,
    )
    summary["repoRoot"] = str(repo_root)
    summary["artifacts"] = {
        "runDirectory": str(run_dir),
        "summaryJson": str(summary_json),
        "summaryMarkdown": str(summary_md),
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, render_markdown(summary))
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary.get("status"),
                    "summaryJson": str(summary_json),
                    "summaryMarkdown": str(summary_md),
                    "counts": summary.get("counts"),
                    "topOwnerFamily": (safe_list(summary.get("ownerFamilies")) or [None])[0],
                    "topParentSlotFamily": (safe_list(summary.get("parentSlotFamilies")) or [None])[0],
                    "nonPlayerParentSlotLeads": safe_list(summary.get("nonPlayerParentSlotLeads"))[:5],
                    "blockers": summary.get("blockers"),
                    "warnings": summary.get("warnings"),
                },
                separators=(",", ":"),
            )
        )
    return 2 if summary.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
