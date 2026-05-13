from __future__ import annotations

import argparse
import csv
import io
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


def norm_hex(value: Any) -> str | None:
    parsed = parse_int(value)
    if parsed is not None:
        return f"0x{parsed:X}"
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() if text else None


def owner_rows_by_base(owner_signature_summary: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows: dict[str, Mapping[str, Any]] = {}
    for owner in safe_list(owner_signature_summary.get("owners")):
        if isinstance(owner, Mapping):
            owner_base = norm_hex(owner.get("ownerBase"))
            if owner_base:
                rows[owner_base] = owner
    return rows


def choose_exact_owner(slot: Mapping[str, Any], player_label_fragment: str) -> Mapping[str, Any] | None:
    targets = [target for target in safe_list(slot.get("exactTargets")) if isinstance(target, Mapping)]
    for target in targets:
        if player_label_fragment.lower() in str(target.get("label")).lower():
            return target
    return targets[0] if targets else None


def owner_window_entries(slot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [entry for entry in safe_list(slot.get("ownerWindowInteresting")) if isinstance(entry, Mapping)]


def module_rvas_from_entries(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    rvas: list[str] = []
    for entry in entries:
        module_pointer = safe_mapping(safe_mapping(entry.get("classification")).get("modulePointer"))
        rva = norm_hex(module_pointer.get("rva"))
        if rva and rva not in rvas:
            rvas.append(rva)
    return rvas


def module_pointer_entries(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pointers: list[dict[str, Any]] = []
    for entry in entries:
        module_pointer = safe_mapping(safe_mapping(entry.get("classification")).get("modulePointer"))
        rva = norm_hex(module_pointer.get("rva"))
        if rva:
            pointers.append({"offsetFromOwner": str(entry.get("offsetFromOwner")), "rva": rva})
    return pointers


def internal_pointer_offsets(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    offsets: list[str] = []
    for entry in entries:
        classification = safe_mapping(entry.get("classification"))
        if not classification.get("inTargetWindow"):
            continue
        offset = entry.get("offsetFromOwner")
        if offset is not None and str(offset) not in offsets:
            offsets.append(str(offset))
    return offsets


def near_offsets(offsets: Sequence[str], *, max_abs: int = 0x80) -> list[str]:
    near: list[str] = []
    for offset in offsets:
        parsed = parse_int(offset)
        if parsed is not None and abs(parsed) <= max_abs:
            near.append(offset)
    return near


def score_slot(
    *,
    slot: Mapping[str, Any],
    owner: Mapping[str, Any] | None,
    exact_owner: Mapping[str, Any] | None,
    module_rvas: Sequence[str],
    internal_offsets: Sequence[str],
    near_internal_offsets: Sequence[str],
    selected_rva: str,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    owner_score = owner.get("score") if owner else None
    if isinstance(owner_score, int):
        owner_score_component = min(owner_score, 300) // 3
        score += owner_score_component
        reasons.append(f"owner-score-component={owner_score_component}")
    if exact_owner:
        score += 25
        reasons.append("exact-owner-slot")
    if owner and not owner.get("missingRvas"):
        score += 45
        reasons.append("owner-complete-module-signature")
    if owner and owner.get("coordPointerIsCandidate"):
        score += 35
        reasons.append("owner-stable-coord-candidate")
    if slot.get("ownerWindowModulePointerCount"):
        score += 25
        reasons.append("slot-has-module-hint")
    if selected_rva in module_rvas:
        score += 25
        reasons.append("slot-has-selected-rva")
    if len(near_internal_offsets) >= 4:
        score += 20
        reasons.append("near-internal-pointer-cluster")
    elif near_internal_offsets:
        score += 5 * len(near_internal_offsets)
        reasons.append(f"near-internal-pointers={len(near_internal_offsets)}")
    if len(internal_offsets) >= 8:
        score += 10
        reasons.append("rich-internal-pointer-layout")
    region_match_count = parse_int(slot.get("regionMatchCount"))
    if region_match_count is not None and region_match_count >= 100:
        score += 10
        reasons.append("dense-region-matches")
    if not owner:
        score -= 10
        reasons.append("missing-owner-signature-row")
    return score, reasons


def summarize_slot(
    *,
    slot: Mapping[str, Any],
    owner_by_base: Mapping[str, Mapping[str, Any]],
    selected_rva: str,
    player_label_fragment: str,
) -> dict[str, Any]:
    exact_owner = choose_exact_owner(slot, player_label_fragment)
    owner = owner_by_base.get(norm_hex(exact_owner.get("address")) or "") if exact_owner else None
    entries = owner_window_entries(slot)
    module_rvas = module_rvas_from_entries(entries)
    module_pointers = module_pointer_entries(entries)
    internal_offsets = internal_pointer_offsets(entries)
    near_internal = near_offsets(internal_offsets)
    module_offsets = [str(pointer.get("offsetFromOwner")) for pointer in module_pointers]
    near_module_offsets = near_offsets(module_offsets)
    score, reasons = score_slot(
        slot=slot,
        owner=owner,
        exact_owner=exact_owner,
        module_rvas=module_rvas,
        internal_offsets=internal_offsets,
        near_internal_offsets=near_internal,
        selected_rva=selected_rva,
    )
    parent_ref = safe_mapping(owner.get("parentRef")) if owner else {}
    return {
        "ownerSlot": slot.get("ownerSlot"),
        "exactOwner": dict(exact_owner) if exact_owner else None,
        "score": score,
        "scoreReasons": reasons,
        "slotClassification": slot.get("classification"),
        "ownerSignatureScore": owner.get("score") if owner else None,
        "ownerMissingRvas": owner.get("missingRvas") if owner else None,
        "ownerCoordPointer": owner.get("coordPointer") if owner else None,
        "ownerCoordPointerIsCandidate": owner.get("coordPointerIsCandidate") if owner else None,
        "ownerCoordPointerStorage": owner.get("coordPointerStorage") if owner else None,
        "parentRefParentHitCount": parent_ref.get("parentHitCount"),
        "ownerWindowModuleRvas": module_rvas,
        "ownerWindowModulePointers": module_pointers,
        "ownerWindowModuleOffsets": module_offsets,
        "nearOwnerModuleOffsets": near_module_offsets,
        "internalPointerOffsets": internal_offsets,
        "nearOwnerInternalPointerOffsets": near_internal,
        "ownerWindowInterestingCount": slot.get("ownerWindowInterestingCount"),
        "regionMatchCount": slot.get("regionMatchCount"),
        "modulePointerCount": slot.get("modulePointerCount"),
        "sourceSummaryJson": slot.get("summaryJson"),
        "recommendedSearch": {
            "kind": "parent-slot-container-root",
            "rootGapAbove": slot.get("ownerSlot"),
            "reason": "Parent slot points to the best structural owner but has no parent-of-parent hit in current evidence.",
        },
    }


def build_summary(
    *,
    parent_slot_path: Path,
    owner_signature_path: Path,
    selected_rva: str,
    player_label_fragment: str,
) -> dict[str, Any]:
    parent_slot_summary = load_json_object(parent_slot_path)
    owner_signature_summary = load_json_object(owner_signature_path)
    owner_by_base = owner_rows_by_base(owner_signature_summary)
    rows: list[dict[str, Any]] = []
    for slot in safe_list(parent_slot_summary.get("slots")):
        if isinstance(slot, Mapping):
            rows.append(
                summarize_slot(
                    slot=slot,
                    owner_by_base=owner_by_base,
                    selected_rva=selected_rva,
                    player_label_fragment=player_label_fragment,
                )
            )
    rows.sort(key=lambda row: (-int(row.get("score") or 0), str(row.get("ownerSlot"))))
    blockers = [] if rows else ["no-parent-slots-found"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "parent-slot-container-rank",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "blocked",
        "blockers": blockers,
        "warnings": [
            "Offline parent-slot/container ranking only; this does not read live target memory or prove a static root.",
            "Top slot is a root-search seed, not movement truth.",
        ],
        "inputs": {
            "parentSlotSummaryJson": str(parent_slot_path.resolve()),
            "ownerStructuralSignatureJson": str(owner_signature_path.resolve()),
            "selectedRva": selected_rva,
            "playerLabelFragment": player_label_fragment,
        },
        "counts": {
            "slotCount": len(rows),
            "moduleHintSlotCount": sum(1 for row in rows if row.get("ownerWindowModuleRvas")),
            "selectedRvaSlotCount": sum(1 for row in rows if selected_rva in safe_list(row.get("ownerWindowModuleRvas"))),
            "stableCoordOwnerSlotCount": sum(1 for row in rows if row.get("ownerCoordPointerIsCandidate")),
        },
        "topSlot": rows[0] if rows else None,
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
            "recommendedAction": "Use the top parent slot as the root-search seed and search for container/list structures above it.",
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    counts = safe_mapping(summary.get("counts"))
    lines = [
        "# Parent-slot container rank",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Slots: `{counts.get('slotCount')}`",
        f"- Selected-RVA slots: `{counts.get('selectedRvaSlotCount')}`",
        f"- Stable coord-owner slots: `{counts.get('stableCoordOwnerSlotCount')}`",
        "",
        "| Rank | Score | Parent slot | Owner | Selected RVA offsets | Near internal offsets | Coord candidate | Reasons |",
        "|---:|---:|---|---|---|---|---:|---|",
    ]
    for index, row in enumerate(safe_list(summary.get("slots")), start=1):
        if not isinstance(row, Mapping):
            continue
        exact_owner = safe_mapping(row.get("exactOwner"))
        reasons = ", ".join(str(reason) for reason in safe_list(row.get("scoreReasons")))
        module_pointers = [
            pointer for pointer in safe_list(row.get("ownerWindowModulePointers")) if isinstance(pointer, Mapping)
        ]
        selected_offsets = ", ".join(
            str(pointer.get("offsetFromOwner"))
            for pointer in module_pointers
            if pointer.get("rva") == safe_mapping(summary.get("inputs")).get("selectedRva")
        )
        if not selected_offsets:
            selected_offsets = ", ".join(str(offset) for offset in safe_list(row.get("ownerWindowModuleOffsets")))
        near_internal = ", ".join(str(offset) for offset in safe_list(row.get("nearOwnerInternalPointerOffsets")))
        lines.append(
            f"| {index} | `{row.get('score')}` | `{row.get('ownerSlot')}` | `{exact_owner.get('address')}` | "
            f"`{selected_offsets}` | `{near_internal}` | `{str(row.get('ownerCoordPointerIsCandidate')).lower()}` | {reasons} |"
        )
    top = safe_mapping(summary.get("topSlot"))
    if top:
        lines.extend(
            [
                "",
                "## Top slot search seed",
                "",
                f"- Parent slot: `{top.get('ownerSlot')}`",
                f"- Owner: `{safe_mapping(top.get('exactOwner')).get('address')}`",
                f"- Coord pointer storage: `{top.get('ownerCoordPointerStorage')}`",
                f"- Coord pointer: `{top.get('ownerCoordPointer')}`",
                f"- Source summary: `{top.get('sourceSummaryJson')}`",
                "",
                "## Top slot near-owner internal pointer offsets",
                "",
                ", ".join(f"`{offset}`" for offset in safe_list(top.get("nearOwnerInternalPointerOffsets"))) or "_None_",
            ]
        )
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in safe_list(summary.get("warnings")))
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    return "\n".join(lines).rstrip() + "\n"


def render_csv(summary: Mapping[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "rank",
            "score",
            "ownerSlot",
            "owner",
            "ownerSignatureScore",
            "coordPointer",
            "coordPointerIsCandidate",
            "moduleRvas",
            "modulePointers",
            "nearOwnerInternalOffsets",
            "scoreReasons",
        ],
    )
    writer.writeheader()
    for index, row in enumerate(safe_list(summary.get("slots")), start=1):
        if not isinstance(row, Mapping):
            continue
        writer.writerow(
            {
                "rank": index,
                "score": row.get("score"),
                "ownerSlot": row.get("ownerSlot"),
                "owner": safe_mapping(row.get("exactOwner")).get("address"),
                "ownerSignatureScore": row.get("ownerSignatureScore"),
                "coordPointer": row.get("ownerCoordPointer"),
                "coordPointerIsCandidate": row.get("ownerCoordPointerIsCandidate"),
                "moduleRvas": " ".join(str(rva) for rva in safe_list(row.get("ownerWindowModuleRvas"))),
                "modulePointers": " ".join(
                    f"{safe_mapping(pointer).get('rva')}@{safe_mapping(pointer).get('offsetFromOwner')}"
                    for pointer in safe_list(row.get("ownerWindowModulePointers"))
                ),
                "nearOwnerInternalOffsets": " ".join(
                    str(offset) for offset in safe_list(row.get("nearOwnerInternalPointerOffsets"))
                ),
                "scoreReasons": " | ".join(str(reason) for reason in safe_list(row.get("scoreReasons"))),
            }
        )
    return output.getvalue()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank parent-slot/container root candidates from offline parent-slot and owner-signature evidence.")
    parser.add_argument("--parent-slot-summary-json", type=Path, required=True)
    parser.add_argument("--owner-structural-signature-json", type=Path, required=True)
    parser.add_argument("--selected-rva", default="0x263E950")
    parser.add_argument("--player-label-fragment", default="player")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"parent-slot-container-rank-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary_csv = run_dir / "summary.csv"
    summary = build_summary(
        parent_slot_path=args.parent_slot_summary_json,
        owner_signature_path=args.owner_structural_signature_json,
        selected_rva=norm_hex(args.selected_rva) or args.selected_rva,
        player_label_fragment=args.player_label_fragment,
    )
    summary["repoRoot"] = str(repo_root)
    summary["artifacts"] = {
        "runDirectory": str(run_dir),
        "summaryJson": str(summary_json),
        "summaryMarkdown": str(summary_md),
        "summaryCsv": str(summary_csv),
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, render_markdown(summary))
    write_text_atomic(summary_csv, render_csv(summary))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"status={summary.get('status')} summary={summary_json}")
    return 0 if summary.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
