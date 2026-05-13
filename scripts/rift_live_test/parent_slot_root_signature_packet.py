from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parent_slot_neighborhood_summary import safe_list, safe_mapping
from .reports import write_json, write_text_atomic


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


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value), 0)
    except ValueError:
        return None


def hex_int(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{value:X}"


def norm_hex(value: Any) -> str | None:
    parsed = parse_int(value)
    if parsed is not None:
        return hex_int(parsed)
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() if text else None


def offset_address(base: Any, offset: Any) -> str | None:
    base_int = parse_int(base)
    offset_int = parse_int(offset)
    if base_int is None or offset_int is None:
        return None
    return hex_int(base_int + offset_int)


def sorted_offsets(values: Sequence[Any]) -> list[str]:
    unique: dict[str, int | None] = {}
    for value in values:
        text = str(value)
        if text not in unique:
            unique[text] = parse_int(value)
    return sorted(unique, key=lambda item: (unique[item] is None, unique[item] if unique[item] is not None else 0, item))


def find_slot_by_owner_slot(summary: Mapping[str, Any], owner_slot: str | None) -> Mapping[str, Any] | None:
    if not owner_slot:
        top_slot = safe_mapping(summary.get("topSlot"))
        return top_slot or None
    normalized = norm_hex(owner_slot)
    for slot in safe_list(summary.get("slots")):
        if isinstance(slot, Mapping) and norm_hex(slot.get("ownerSlot")) == normalized:
            return slot
    return None


def find_neighborhood_slot(summary: Mapping[str, Any], owner_slot: str | None) -> Mapping[str, Any] | None:
    normalized = norm_hex(owner_slot)
    for slot in safe_list(summary.get("slots")):
        if isinstance(slot, Mapping) and norm_hex(slot.get("ownerSlot")) == normalized:
            return slot
    return None


def find_owner(summary: Mapping[str, Any], owner_base: str | None) -> Mapping[str, Any] | None:
    normalized = norm_hex(owner_base)
    if normalized:
        for owner in safe_list(summary.get("owners")):
            if isinstance(owner, Mapping) and norm_hex(owner.get("ownerBase")) == normalized:
                return owner
    top_owner = safe_mapping(summary.get("topOwner"))
    return top_owner or None


def exact_owner_base(slot: Mapping[str, Any]) -> str | None:
    exact_owner = safe_mapping(slot.get("exactOwner"))
    address = norm_hex(exact_owner.get("address"))
    if address:
        return address
    for target in safe_list(slot.get("exactTargets")):
        if isinstance(target, Mapping):
            address = norm_hex(target.get("address"))
            if address:
                return address
    return None


def module_pointers_from_slot(slot: Mapping[str, Any]) -> list[dict[str, Any]]:
    pointers: list[dict[str, Any]] = []
    for pointer in safe_list(slot.get("ownerWindowModulePointers")):
        if isinstance(pointer, Mapping):
            pointers.append(
                {
                    "offsetFromOwnerSlot": str(pointer.get("offsetFromOwner")),
                    "storageAddress": offset_address(slot.get("ownerSlot"), pointer.get("offsetFromOwner")),
                    "rva": norm_hex(pointer.get("rva")) or pointer.get("rva"),
                }
            )
    if pointers:
        return pointers

    for entry in safe_list(slot.get("ownerWindowInteresting")):
        if not isinstance(entry, Mapping):
            continue
        module_pointer = safe_mapping(safe_mapping(entry.get("classification")).get("modulePointer"))
        rva = norm_hex(module_pointer.get("rva"))
        if not rva:
            continue
        pointers.append(
            {
                "offsetFromOwnerSlot": str(entry.get("offsetFromOwner")),
                "storageAddress": offset_address(slot.get("ownerSlot"), entry.get("offsetFromOwner")),
                "rva": rva,
            }
        )
    return pointers


def owner_module_fields(owner: Mapping[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for field in safe_list(owner.get("modulePointerFields")):
        if isinstance(field, Mapping):
            fields.append(
                {
                    "offsetFromOwner": str(field.get("offset")),
                    "storageAddress": field.get("storage"),
                    "absoluteValue": field.get("value"),
                    "rva": norm_hex(field.get("rva")) or field.get("rva"),
                }
            )
    return fields


def selected_rva_locations(
    *,
    selected_rva: str,
    slot_module_pointers: Sequence[Mapping[str, Any]],
    fields: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    selected = norm_hex(selected_rva) or selected_rva
    return {
        "selectedRva": selected,
        "parentSlotOffsets": [
            {
                "offsetFromOwnerSlot": pointer.get("offsetFromOwnerSlot"),
                "storageAddress": pointer.get("storageAddress"),
            }
            for pointer in slot_module_pointers
            if norm_hex(pointer.get("rva")) == selected
        ],
        "ownerOffsets": [
            {
                "offsetFromOwner": field.get("offsetFromOwner"),
                "storageAddress": field.get("storageAddress"),
            }
            for field in fields
            if norm_hex(field.get("rva")) == selected
        ],
    }


def build_known_chain(
    *,
    owner_slot: str | None,
    owner_base: str | None,
    coord_pointer_storage: str | None,
    coord_pointer: str | None,
    slot_module_pointers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    if slot_module_pointers:
        first_pointer = slot_module_pointers[0]
        chain.append(
            {
                "order": 1,
                "kind": "module-hint-near-parent-slot",
                "address": first_pointer.get("storageAddress"),
                "relation": f"{first_pointer.get('offsetFromOwnerSlot')} from parent slot",
                "value": first_pointer.get("rva"),
                "meaning": "current best static-owner clue, not a root by itself",
            }
        )
    chain.append(
        {
            "order": 2,
            "kind": "parent-slot",
            "address": owner_slot,
            "relation": "stores owner pointer",
            "value": owner_base,
        }
    )
    chain.append(
        {
            "order": 3,
            "kind": "owner",
            "address": owner_base,
            "relation": "+0x10 coord pointer storage",
            "value": coord_pointer_storage,
        }
    )
    chain.append(
        {
            "order": 4,
            "kind": "coord-pointer",
            "address": coord_pointer_storage,
            "relation": "points to current coord-candidate region",
            "value": coord_pointer,
        }
    )
    return chain


def build_search_predicates(
    *,
    owner_slot: str | None,
    owner_base: str | None,
    coord_pointer_storage: str | None,
    coord_pointer: str | None,
    selected_rva: str,
    slot_module_pointers: Sequence[Mapping[str, Any]],
    fields: Sequence[Mapping[str, Any]],
    parent_ref_parent_hit_count: Any,
) -> list[dict[str, Any]]:
    predicates: list[dict[str, Any]] = [
        {
            "id": "parent-slot-points-to-owner",
            "address": owner_slot,
            "expectedValue": owner_base,
            "priority": "must-match",
            "why": "This slot is the current root-search gap: it points to the best player-owner candidate.",
        },
        {
            "id": "owner-coord-pointer-at-plus-0x10",
            "address": coord_pointer_storage,
            "expectedValue": coord_pointer,
            "priority": "must-match",
            "why": "The owner relation to the stable coord-candidate pointer is the key bridge to coordinate data.",
        },
    ]
    selected = norm_hex(selected_rva) or selected_rva
    for pointer in slot_module_pointers:
        if norm_hex(pointer.get("rva")) == selected:
            predicates.append(
                {
                    "id": "parent-slot-selected-rva-module-hint",
                    "address": pointer.get("storageAddress"),
                    "offsetFromOwnerSlot": pointer.get("offsetFromOwnerSlot"),
                    "expectedRva": selected,
                    "priority": "high",
                    "why": "The selected module RVA appears immediately before the parent slot and is the strongest static-owner clue.",
                }
            )
    for field in fields:
        predicates.append(
            {
                "id": f"owner-module-field-{field.get('offsetFromOwner')}",
                "address": field.get("storageAddress"),
                "offsetFromOwner": field.get("offsetFromOwner"),
                "expectedRva": field.get("rva"),
                "priority": "high" if field.get("rva") == selected else "medium",
                "why": "Owner module-field layout should remain stable across sibling instances and restart validation.",
            }
        )
    predicates.append(
        {
            "id": "negative-parent-of-parent-evidence",
            "observedParentHitCount": parent_ref_parent_hit_count,
            "priority": "context",
            "why": "Current artifact evidence did not find a parent of the parent slot; search must widen to container/family ownership rather than reuse stale absolute pointers.",
        }
    )
    return predicates


def build_recommended_actions() -> list[dict[str, str]]:
    return [
        {
            "action": "Search family/container refs above the parent slot, not just adjacent offsets.",
            "why": "The known chain stops at `0x268D7539700`; the missing piece is an owner/container above that slot.",
        },
        {
            "action": "Batch-scan sibling parent slots with the same predicate packet.",
            "why": "Sibling confirmation separates reusable structure from player-only coincidence.",
        },
        {
            "action": "Use the selected module hint `0x263E950` as a search seed only.",
            "why": "It is the strongest static-owner clue but not static-chain proof by itself.",
        },
        {
            "action": "Convert any root hit into a resolver candidate before promotion.",
            "why": "A real static chain needs module/RVA provenance and repeatable resolution.",
        },
        {
            "action": "Require API-now vs chain-now agreement across poses.",
            "why": "Current evidence is candidate-only and must not bypass freshness gates.",
        },
    ]


def build_summary(
    *,
    parent_slot_container_rank_path: Path,
    parent_slot_summary_path: Path,
    owner_structural_signature_path: Path,
    owner_slot: str | None = None,
    selected_rva: str = "0x263E950",
) -> dict[str, Any]:
    container_rank = load_json_object(parent_slot_container_rank_path)
    parent_slot_summary = load_json_object(parent_slot_summary_path)
    owner_signature = load_json_object(owner_structural_signature_path)

    blockers: list[str] = []
    warnings: list[str] = [
        "Offline root-search signature packet only; it does not read live target memory or prove a static chain.",
        "Candidate-only evidence; movement/navigation remains blocked until fresh API-now versus memory-now proof passes.",
    ]

    top_slot = find_slot_by_owner_slot(container_rank, owner_slot)
    if not top_slot:
        blockers.append("no-parent-slot-container-rank-row-found")
        top_slot = {}
    owner_slot_hex = norm_hex(top_slot.get("ownerSlot"))
    owner_base_hex = exact_owner_base(top_slot)
    owner = find_owner(owner_signature, owner_base_hex)
    if not owner:
        blockers.append("no-owner-structural-signature-row-found")
        owner = {}
    if not owner_base_hex:
        owner_base_hex = norm_hex(owner.get("ownerBase"))
    neighborhood_slot = find_neighborhood_slot(parent_slot_summary, owner_slot_hex)
    if not neighborhood_slot:
        warnings.append("No matching parent-slot neighborhood summary row found; using container-rank row only.")
        neighborhood_slot = {}

    owner_base_from_signature = norm_hex(owner.get("ownerBase"))
    if owner_base_hex and owner_base_from_signature and owner_base_hex != owner_base_from_signature:
        warnings.append(f"Owner mismatch between rank and signature: rank={owner_base_hex};signature={owner_base_from_signature}.")

    parent_ref = safe_mapping(owner.get("parentRef"))
    parent_ref_address = norm_hex(parent_ref.get("address"))
    if owner_slot_hex and parent_ref_address and owner_slot_hex != parent_ref_address:
        warnings.append(f"Parent-slot mismatch between rank and owner signature: rank={owner_slot_hex};signature={parent_ref_address}.")

    selected = norm_hex(selected_rva) or selected_rva
    slot_module_pointers = module_pointers_from_slot(top_slot)
    fields = owner_module_fields(owner)
    coord_pointer_storage = norm_hex(owner.get("coordPointerStorage")) or norm_hex(top_slot.get("ownerCoordPointerStorage"))
    coord_pointer = norm_hex(owner.get("coordPointer")) or norm_hex(top_slot.get("ownerCoordPointer"))
    near_internal = sorted_offsets(safe_list(top_slot.get("nearOwnerInternalPointerOffsets")))
    internal_offsets = sorted_offsets(safe_list(top_slot.get("internalPointerOffsets")))
    selected_locations = selected_rva_locations(
        selected_rva=selected,
        slot_module_pointers=slot_module_pointers,
        fields=fields,
    )
    root_gap = owner_slot_hex or parent_ref_address
    known_chain = build_known_chain(
        owner_slot=root_gap,
        owner_base=owner_base_hex,
        coord_pointer_storage=coord_pointer_storage,
        coord_pointer=coord_pointer,
        slot_module_pointers=slot_module_pointers,
    )
    predicates = build_search_predicates(
        owner_slot=root_gap,
        owner_base=owner_base_hex,
        coord_pointer_storage=coord_pointer_storage,
        coord_pointer=coord_pointer,
        selected_rva=selected,
        slot_module_pointers=slot_module_pointers,
        fields=fields,
        parent_ref_parent_hit_count=parent_ref.get("parentHitCount", top_slot.get("parentRefParentHitCount")),
    )

    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "parent-slot-root-signature-packet",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "inputs": {
            "parentSlotContainerRankJson": str(parent_slot_container_rank_path.resolve()),
            "parentSlotSummaryJson": str(parent_slot_summary_path.resolve()),
            "ownerStructuralSignatureJson": str(owner_structural_signature_path.resolve()),
            "requestedOwnerSlot": norm_hex(owner_slot) if owner_slot else None,
            "selectedRva": selected,
        },
        "counts": {
            "containerRankSlotCount": safe_mapping(container_rank.get("counts")).get("slotCount"),
            "parentSlotSummaryCount": safe_mapping(parent_slot_summary.get("counts")).get("slotSummaryCount"),
            "ownerSignatureOwnerCount": safe_mapping(owner_signature.get("counts")).get("ownerCount"),
            "searchPredicateCount": len(predicates),
            "knownChainNodeCount": len(known_chain),
        },
        "rootSearch": {
            "rootGapAbove": root_gap,
            "unresolvedObjective": "Find a restart-stable module/static or container owner that resolves this parent slot.",
            "knownChain": known_chain,
            "selectedRvaLocations": selected_locations,
            "candidateOnly": True,
            "movementProofEligible": False,
        },
        "signature": {
            "parentSlot": root_gap,
            "ownerBase": owner_base_hex,
            "ownerScore": owner.get("score") or top_slot.get("ownerSignatureScore"),
            "ownerScoreReasons": owner.get("scoreReasons"),
            "coordPointerStorage": coord_pointer_storage,
            "coordPointer": coord_pointer,
            "coordPointerVec3": owner.get("coordPointerVec3"),
            "coordPointerIsCandidate": owner.get("coordPointerIsCandidate", top_slot.get("ownerCoordPointerIsCandidate")),
            "parentSlotModuleHints": slot_module_pointers,
            "ownerModuleFields": fields,
            "nearOwnerInternalPointerOffsets": near_internal,
            "internalPointerOffsets": internal_offsets,
            "parentSlotRankScore": top_slot.get("score"),
            "parentSlotRankReasons": top_slot.get("scoreReasons"),
            "parentSlotClassification": top_slot.get("slotClassification") or top_slot.get("classification"),
            "parentSlotNeighborhoodClassification": neighborhood_slot.get("classification"),
            "regionMatchCount": top_slot.get("regionMatchCount") or neighborhood_slot.get("regionMatchCount"),
            "modulePointerCount": top_slot.get("modulePointerCount") or neighborhood_slot.get("modulePointerCount"),
            "parentRefParentHitCount": parent_ref.get("parentHitCount", top_slot.get("parentRefParentHitCount")),
        },
        "searchPredicates": predicates,
        "negativeEvidence": {
            "parentRefParentHitCount": parent_ref.get("parentHitCount", top_slot.get("parentRefParentHitCount")),
            "parentHits": parent_ref.get("parentHits", []),
            "meaning": "No parent-of-parent hit was present in the current offline evidence; this is why the next search widens to container/family ownership.",
        },
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
            "recommendedAction": "Use this packet as the root-search predicate set for broad family/container scans above the parent slot; do not promote until restart and API-now-vs-chain-now proof pass.",
            "recommendedActions": build_recommended_actions(),
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    counts = safe_mapping(summary.get("counts"))
    root_search = safe_mapping(summary.get("rootSearch"))
    signature = safe_mapping(summary.get("signature"))
    lines = [
        "# Parent-slot root signature packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Root gap above: `{root_search.get('rootGapAbove')}`",
        f"- Search predicates: `{counts.get('searchPredicateCount')}`",
        f"- Candidate only: `{str(safe_mapping(summary.get('safety')).get('candidateOnly')).lower()}`",
        f"- Movement proof eligible: `{str(safe_mapping(summary.get('safety')).get('movementProofEligible')).lower()}`",
        "",
        "## Known candidate chain",
        "",
        "| # | Kind | Address | Relation | Value |",
        "|---:|---|---|---|---|",
    ]
    for node in safe_list(root_search.get("knownChain")):
        if isinstance(node, Mapping):
            lines.append(
                f"| `{node.get('order')}` | `{node.get('kind')}` | `{node.get('address')}` | "
                f"{node.get('relation')} | `{node.get('value')}` |"
            )
    lines.extend(
        [
            "",
            "## Signature",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Parent slot | `{signature.get('parentSlot')}` |",
            f"| Owner base | `{signature.get('ownerBase')}` |",
            f"| Owner score | `{signature.get('ownerScore')}` |",
            f"| Coord pointer storage | `{signature.get('coordPointerStorage')}` |",
            f"| Coord pointer | `{signature.get('coordPointer')}` |",
            f"| Coord pointer vec3 | `{signature.get('coordPointerVec3')}` |",
            f"| Parent-slot rank score | `{signature.get('parentSlotRankScore')}` |",
            f"| Parent-of-parent hit count | `{signature.get('parentRefParentHitCount')}` |",
            "",
            "## Module hints",
            "",
            "| Scope | Offset | Storage | RVA |",
            "|---|---:|---|---|",
        ]
    )
    for hint in safe_list(signature.get("parentSlotModuleHints")):
        if isinstance(hint, Mapping):
            lines.append(
                f"| Parent slot | `{hint.get('offsetFromOwnerSlot')}` | `{hint.get('storageAddress')}` | `{hint.get('rva')}` |"
            )
    for field in safe_list(signature.get("ownerModuleFields")):
        if isinstance(field, Mapping):
            lines.append(
                f"| Owner | `{field.get('offsetFromOwner')}` | `{field.get('storageAddress')}` | `{field.get('rva')}` |"
            )
    lines.extend(
        [
            "",
            "## Search predicates",
            "",
            "| ID | Priority | Address | Expected | Why |",
            "|---|---|---|---|---|",
        ]
    )
    for predicate in safe_list(summary.get("searchPredicates")):
        if not isinstance(predicate, Mapping):
            continue
        expected = predicate.get("expectedValue") or predicate.get("expectedRva") or predicate.get("observedParentHitCount")
        lines.append(
            f"| `{predicate.get('id')}` | `{predicate.get('priority')}` | `{predicate.get('address')}` | "
            f"`{expected}` | {predicate.get('why')} |"
        )
    near_internal = ", ".join(f"`{offset}`" for offset in safe_list(signature.get("nearOwnerInternalPointerOffsets")))
    lines.extend(["", "## Near-owner internal pointer offsets", "", near_internal or "_None_"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in safe_list(summary.get("warnings")))
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    recommended = safe_list(safe_mapping(summary.get("next")).get("recommendedActions"))
    if recommended:
        lines.extend(["", "## Recommended next actions", "", "| # | Action | Why |", "|---:|---|---|"])
        for index, item in enumerate(recommended, start=1):
            if isinstance(item, Mapping):
                lines.append(f"| {index} | {item.get('action')} | {item.get('why')} |")
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a root-search signature packet from parent-slot and owner structural evidence.")
    parser.add_argument("--parent-slot-container-rank-json", type=Path, required=True)
    parser.add_argument("--parent-slot-summary-json", type=Path, required=True)
    parser.add_argument("--owner-structural-signature-json", type=Path, required=True)
    parser.add_argument("--owner-slot")
    parser.add_argument("--selected-rva", default="0x263E950")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"parent-slot-root-signature-packet-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary = build_summary(
        parent_slot_container_rank_path=args.parent_slot_container_rank_json,
        parent_slot_summary_path=args.parent_slot_summary_json,
        owner_structural_signature_path=args.owner_structural_signature_json,
        owner_slot=args.owner_slot,
        selected_rva=args.selected_rva,
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
        print(json.dumps(summary, indent=2))
    else:
        print(f"status={summary.get('status')} summary={summary_json}")
    return 0 if summary.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
