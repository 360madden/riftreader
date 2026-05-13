from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parent_slot_neighborhood_summary import safe_list, safe_mapping
from .parent_slot_root_signature_packet import norm_hex, parse_int
from .pointer_family_scan import int_hex, run_reader_json, validate_target
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_READER_DLL = Path(r"reader\RiftReader.Reader\bin\Debug\net10.0-windows\RiftReader.Reader.dll")
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"


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


def bytes_from_hex(text: Any) -> bytes:
    if not isinstance(text, str):
        return b""
    compact = text.replace(" ", "").replace("\n", "").replace("\r", "")
    if len(compact) % 2:
        compact = compact[:-1]
    try:
        return bytes.fromhex(compact)
    except ValueError:
        return b""


def qword_at(hit: Mapping[str, Any], address: int) -> int | None:
    context = safe_mapping(hit.get("Context"))
    window_start = parse_int(context.get("WindowStart"))
    if window_start is None:
        return None
    data = bytes_from_hex(context.get("BytesHex"))
    offset = address - window_start
    if offset < 0 or offset + 8 > len(data):
        return None
    return int.from_bytes(data[offset : offset + 8], "little", signed=False)


def qword_hex_at(hit: Mapping[str, Any], address: int) -> str | None:
    return int_hex(qword_at(hit, address))


def rva_absolute(root_packet: Mapping[str, Any], selected_rva: int, module_base: int) -> int:
    for field in safe_list(safe_mapping(root_packet.get("signature")).get("ownerModuleFields")):
        if not isinstance(field, Mapping):
            continue
        if parse_int(field.get("rva")) == selected_rva:
            absolute = parse_int(field.get("absoluteValue"))
            if absolute is not None and absolute - module_base == selected_rva:
                return absolute
    return module_base + selected_rva


def owner_field_offsets(root_packet: Mapping[str, Any]) -> dict[int, int]:
    offsets: dict[int, int] = {}
    for field in safe_list(safe_mapping(root_packet.get("signature")).get("ownerModuleFields")):
        if not isinstance(field, Mapping):
            continue
        offset = parse_int(field.get("offsetFromOwner"))
        rva = parse_int(field.get("rva"))
        if offset is not None and rva is not None:
            offsets[offset] = rva
    return offsets


def selected_owner_offsets(root_packet: Mapping[str, Any], selected_rva: int) -> list[int]:
    offsets = [
        offset
        for offset, rva in owner_field_offsets(root_packet).items()
        if rva == selected_rva
    ]
    return offsets or [0xE0]


def heap_like(value: int | None, module_base: int) -> bool:
    if value is None:
        return False
    return 0x10000000000 <= value < module_base


def signed_hex(value: int | None) -> str | None:
    if value is None:
        return None
    if value < 0:
        return f"-0x{-value:X}"
    return f"0x{value:X}"


def field_mismatch_warnings(candidate: Mapping[str, Any] | None) -> list[str]:
    if not candidate:
        return []
    warnings: list[str] = []
    for field in safe_list(candidate.get("fieldMatches")):
        if not isinstance(field, Mapping) or field.get("matched"):
            continue
        warnings.append(
            "top-owner-field-mismatch:"
            f"offset={field.get('offsetFromOwner')};"
            f"expectedRva={field.get('expectedRva')};"
            f"actualRva={field.get('actualRva')};"
            f"ownerBase={candidate.get('ownerBase')}"
        )
    return warnings


def analyze_owner_field_candidate(
    *,
    hit: Mapping[str, Any],
    selected_owner_offset: int,
    owner_field_rvas: Mapping[int, int],
    module_base: int,
    expected_owner: int | None,
    expected_coord_pointer: int | None,
) -> dict[str, Any]:
    hit_address = parse_int(hit.get("Address"))
    if hit_address is None:
        return {}
    owner_base = hit_address - selected_owner_offset
    field_matches: list[dict[str, Any]] = []
    for offset, expected_rva in sorted(owner_field_rvas.items()):
        storage = owner_base + offset
        actual = qword_at(hit, storage)
        actual_rva = actual - module_base if actual is not None and actual >= module_base else None
        matched = actual_rva == expected_rva
        field_matches.append(
            {
                "offsetFromOwner": int_hex(offset),
                "storageAddress": int_hex(storage),
                "expectedRva": int_hex(expected_rva),
                "actualValue": int_hex(actual),
                "actualRva": int_hex(actual_rva),
                "matched": matched,
            }
        )
    coord_pointer = qword_at(hit, owner_base + 0x10)
    score = sum(25 for field in field_matches if field.get("matched"))
    reasons: list[str] = []
    matched_count = sum(1 for field in field_matches if field.get("matched"))
    if field_matches:
        reasons.append(f"matched-owner-module-fields={matched_count}/{len(field_matches)}")
    if field_matches and all(field.get("matched") for field in field_matches):
        score += 80
        reasons.append("complete-owner-module-field-signature")
    if expected_owner is not None and owner_base == expected_owner:
        score += 80
        reasons.append("matches-known-owner")
    if expected_coord_pointer is not None and coord_pointer == expected_coord_pointer:
        score += 60
        reasons.append("matches-known-coord-pointer")
    elif heap_like(coord_pointer, module_base):
        score += 10
        reasons.append("coord-pointer-slot-heap-like")
    return {
        "hitAddress": int_hex(hit_address),
        "selectedOwnerOffset": signed_hex(selected_owner_offset),
        "ownerBase": int_hex(owner_base),
        "coordPointerStorage": int_hex(owner_base + 0x10),
        "coordPointer": int_hex(coord_pointer),
        "fieldMatches": field_matches,
        "score": score,
        "scoreReasons": reasons,
        "candidateOnly": True,
        "promotionEligible": False,
    }


def analyze_parent_slot_candidate(
    *,
    hit: Mapping[str, Any],
    selected_parent_slot_offset: int,
    module_base: int,
    expected_parent_slot: int | None,
    expected_owner: int | None,
) -> dict[str, Any]:
    hit_address = parse_int(hit.get("Address"))
    if hit_address is None:
        return {}
    parent_slot = hit_address - selected_parent_slot_offset
    owner_pointer = qword_at(hit, parent_slot)
    score = 0
    reasons: list[str] = []
    if expected_parent_slot is not None and parent_slot == expected_parent_slot:
        score += 80
        reasons.append("matches-known-parent-slot")
    if expected_owner is not None and owner_pointer == expected_owner:
        score += 80
        reasons.append("matches-known-owner")
    elif heap_like(owner_pointer, module_base):
        score += 15
        reasons.append("owner-pointer-heap-like")
    return {
        "hitAddress": int_hex(hit_address),
        "selectedParentSlotOffset": signed_hex(selected_parent_slot_offset),
        "parentSlot": int_hex(parent_slot),
        "ownerPointer": int_hex(owner_pointer),
        "score": score,
        "scoreReasons": reasons,
        "candidateOnly": True,
        "promotionEligible": False,
    }


def rank_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted((dict(candidate) for candidate in candidates), key=lambda row: (-int(row.get("score") or 0), str(row.get("hitAddress"))))


def summarize_hits(
    *,
    root_packet: Mapping[str, Any],
    scan: Mapping[str, Any],
    module_base: int,
    selected_rva: int,
) -> dict[str, Any]:
    signature = safe_mapping(root_packet.get("signature"))
    root_search = safe_mapping(root_packet.get("rootSearch"))
    expected_parent_slot = parse_int(signature.get("parentSlot") or root_search.get("rootGapAbove"))
    expected_owner = parse_int(signature.get("ownerBase"))
    expected_coord_pointer = parse_int(signature.get("coordPointer"))
    owner_offsets = selected_owner_offsets(root_packet, selected_rva)
    parent_offsets: list[int] = []
    for hint in safe_list(signature.get("parentSlotModuleHints")):
        if isinstance(hint, Mapping) and parse_int(hint.get("rva")) == selected_rva:
            offset = parse_int(hint.get("offsetFromOwnerSlot"))
            if offset is not None and offset not in parent_offsets:
                parent_offsets.append(offset)
    parent_offsets = parent_offsets or [-0x40]
    field_rvas = owner_field_offsets(root_packet)

    owner_candidates: list[dict[str, Any]] = []
    parent_candidates: list[dict[str, Any]] = []
    for hit in safe_list(scan.get("Hits")):
        if not isinstance(hit, Mapping):
            continue
        for selected_owner_offset in owner_offsets:
            candidate = analyze_owner_field_candidate(
                hit=hit,
                selected_owner_offset=selected_owner_offset,
                owner_field_rvas=field_rvas,
                module_base=module_base,
                expected_owner=expected_owner,
                expected_coord_pointer=expected_coord_pointer,
            )
            if candidate:
                owner_candidates.append(candidate)
        for selected_parent_offset in parent_offsets:
            candidate = analyze_parent_slot_candidate(
                hit=hit,
                selected_parent_slot_offset=selected_parent_offset,
                module_base=module_base,
                expected_parent_slot=expected_parent_slot,
                expected_owner=expected_owner,
            )
            if candidate:
                parent_candidates.append(candidate)

    ranked_owner = rank_candidates(owner_candidates)
    ranked_parent = rank_candidates(parent_candidates)
    return {
        "ownerFieldCandidates": ranked_owner,
        "parentSlotCandidates": ranked_parent,
        "topOwnerFieldCandidate": ranked_owner[0] if ranked_owner else None,
        "topParentSlotCandidate": ranked_parent[0] if ranked_parent else None,
        "counts": {
            "hitCount": int(scan.get("HitCount") or len(safe_list(scan.get("Hits")))),
            "ownerFieldCandidateCount": len(ranked_owner),
            "parentSlotCandidateCount": len(ranked_parent),
            "nonZeroOwnerFieldCandidateCount": sum(1 for row in ranked_owner if int(row.get("score") or 0) > 0),
            "nonZeroParentSlotCandidateCount": sum(1 for row in ranked_parent if int(row.get("score") or 0) > 0),
        },
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    counts = safe_mapping(summary.get("counts"))
    lines = [
        "# Root-signature module-hint sweep",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Target PID: `{safe_mapping(summary.get('target')).get('pid')}`",
        f"- Target HWND: `{safe_mapping(summary.get('target')).get('hwndHex')}`",
        f"- Selected RVA: `{safe_mapping(summary.get('inputs')).get('selectedRva')}`",
        f"- Selected absolute: `{safe_mapping(summary.get('inputs')).get('selectedAbsolute')}`",
        f"- Module-pointer hits: `{counts.get('modulePointerHitCount')}`",
        f"- Non-zero owner-field candidates: `{counts.get('nonZeroOwnerFieldCandidateCount')}`",
        f"- Non-zero parent-slot candidates: `{counts.get('nonZeroParentSlotCandidateCount')}`",
        "",
        "## Top owner-field candidates",
        "",
        "| Rank | Score | Hit | Owner base | Coord pointer | Reasons |",
        "|---:|---:|---|---|---|---|",
    ]
    for index, candidate in enumerate(safe_list(summary.get("ownerFieldCandidates"))[:10], start=1):
        if isinstance(candidate, Mapping):
            reasons = ", ".join(str(reason) for reason in safe_list(candidate.get("scoreReasons")))
            lines.append(
                f"| {index} | `{candidate.get('score')}` | `{candidate.get('hitAddress')}` | "
                f"`{candidate.get('ownerBase')}` | `{candidate.get('coordPointer')}` | {reasons} |"
            )
    lines.extend(
        [
            "",
            "## Top parent-slot candidates",
            "",
            "| Rank | Score | Hit | Parent slot | Owner pointer | Reasons |",
            "|---:|---:|---|---|---|---|",
        ]
    )
    for index, candidate in enumerate(safe_list(summary.get("parentSlotCandidates"))[:10], start=1):
        if isinstance(candidate, Mapping):
            reasons = ", ".join(str(reason) for reason in safe_list(candidate.get("scoreReasons")))
            lines.append(
                f"| {index} | `{candidate.get('score')}` | `{candidate.get('hitAddress')}` | "
                f"`{candidate.get('parentSlot')}` | `{candidate.get('ownerPointer')}` | {reasons} |"
            )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in safe_list(summary.get("warnings")))
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "Read-only process-memory scan through RiftReader.Reader. No movement, input, x64dbg, Cheat Engine, breakpoints, provider writes, or proof promotion.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run_sweep(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = args.output_root.resolve() if args.output_root else repo_root / "scripts" / "captures" / f"root-signature-module-hint-sweep-{utc_stamp()}"
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    raw_scan_json = raw_dir / "selected-module-pointer-scan.json"

    reader_dll = args.reader_dll
    if not reader_dll.is_absolute():
        reader_dll = repo_root / reader_dll

    blockers: list[str] = []
    warnings: list[str] = []
    if not reader_dll.is_file():
        blockers.append(f"reader-dll-missing:{reader_dll}")
    target, target_blockers, target_warnings = validate_target(args)
    blockers.extend(target_blockers)
    warnings.extend(target_warnings)
    root_packet = load_json_object(args.root_signature_json)
    selected_rva = parse_int(args.selected_rva or safe_mapping(root_packet.get("inputs")).get("selectedRva"))
    if selected_rva is None:
        blockers.append("selected-rva-missing")
        selected_rva = 0
    process_details = safe_mapping(target).get("processDetails") if target else {}
    module_base = parse_int(safe_mapping(process_details).get("moduleBaseAddressHex") or args.expected_module_base)
    if module_base is None:
        blockers.append("module-base-missing")
        module_base = 0
    selected_absolute = rva_absolute(root_packet, selected_rva, module_base) if selected_rva and module_base else 0

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "root-signature-module-hint-sweep",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "started",
        "repoRoot": str(repo_root),
        "target": target,
        "inputs": {
            "rootSignatureJson": str(args.root_signature_json.resolve()),
            "readerDll": str(reader_dll),
            "selectedRva": int_hex(selected_rva),
            "selectedAbsolute": int_hex(selected_absolute),
            "contextBytes": args.context_bytes,
            "maxHits": args.max_hits,
        },
        "counts": {
            "modulePointerHitCount": 0,
            "ownerFieldCandidateCount": 0,
            "parentSlotCandidateCount": 0,
            "nonZeroOwnerFieldCandidateCount": 0,
            "nonZeroParentSlotCandidateCount": 0,
        },
        "ownerFieldCandidates": [],
        "parentSlotCandidates": [],
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": {
            "runDirectory": str(run_dir),
            "rawDirectory": str(raw_dir),
            "rawScanJson": str(raw_scan_json),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "breakpointsSet": False,
            "readOnlyProcessMemoryScan": True,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "githubConnectorWrites": False,
            "candidateOnly": True,
            "movementProofEligible": False,
        },
    }
    if blockers:
        write_json(summary_json, summary)
        write_text_atomic(summary_md, build_markdown(summary))
        return summary

    started = time.monotonic()
    scan = run_reader_json(
        reader_dll,
        [
            "--pid",
            str(args.target_pid),
            "--scan-pointer",
            int_hex(selected_absolute) or str(selected_absolute),
            "--pointer-width",
            "8",
            "--scan-context",
            str(args.context_bytes),
            "--max-hits",
            str(args.max_hits),
            "--json",
        ],
        timeout_seconds=args.timeout_seconds,
    )
    scan["scanElapsedSeconds"] = round(time.monotonic() - started, 3)
    write_json(raw_scan_json, scan)
    analyzed = summarize_hits(
        root_packet=root_packet,
        scan=scan,
        module_base=module_base,
        selected_rva=selected_rva,
    )
    summary["status"] = "passed"
    mismatch_warnings = field_mismatch_warnings(analyzed["topOwnerFieldCandidate"])
    if mismatch_warnings:
        warnings.extend(mismatch_warnings)
    summary["counts"] = {
        "modulePointerHitCount": analyzed["counts"]["hitCount"],
        "ownerFieldCandidateCount": analyzed["counts"]["ownerFieldCandidateCount"],
        "parentSlotCandidateCount": analyzed["counts"]["parentSlotCandidateCount"],
        "nonZeroOwnerFieldCandidateCount": analyzed["counts"]["nonZeroOwnerFieldCandidateCount"],
        "nonZeroParentSlotCandidateCount": analyzed["counts"]["nonZeroParentSlotCandidateCount"],
        "topOwnerFieldMismatchCount": len(mismatch_warnings),
    }
    summary["ownerFieldCandidates"] = analyzed["ownerFieldCandidates"][: args.report_limit]
    summary["parentSlotCandidates"] = analyzed["parentSlotCandidates"][: args.report_limit]
    summary["topOwnerFieldCandidate"] = analyzed["topOwnerFieldCandidate"]
    summary["topParentSlotCandidate"] = analyzed["topParentSlotCandidate"]
    summary["warnings"] = warnings
    summary["next"] = {
        "recommendedAction": "Use non-zero module-hint candidates as broad family/container follow-up seeds only; continue to require restart validation and fresh API-now proof before promotion.",
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sweep current process memory for root-signature module-hint occurrences.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--reader-dll", type=Path, default=DEFAULT_READER_DLL)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--target-hwnd", required=True)
    parser.add_argument("--expected-start-time-utc", default=None)
    parser.add_argument("--start-time-tolerance-seconds", type=float, default=1.0)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--root-signature-json", type=Path, required=True)
    parser.add_argument("--selected-rva")
    parser.add_argument("--context-bytes", type=int, default=288)
    parser.add_argument("--max-hits", type=int, default=2048)
    parser.add_argument("--report-limit", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_sweep(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary.get("status"),
                    "summaryJson": safe_mapping(summary.get("artifacts")).get("summaryJson"),
                    "summaryMarkdown": safe_mapping(summary.get("artifacts")).get("summaryMarkdown"),
                    "rawScanJson": safe_mapping(summary.get("artifacts")).get("rawScanJson"),
                    "counts": summary.get("counts"),
                    "topOwnerFieldCandidate": summary.get("topOwnerFieldCandidate"),
                    "topParentSlotCandidate": summary.get("topParentSlotCandidate"),
                    "blockers": summary.get("blockers"),
                    "warnings": summary.get("warnings"),
                },
                separators=(",", ":"),
            )
        )
    return 2 if summary.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
