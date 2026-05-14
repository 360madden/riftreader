#!/usr/bin/env python3
"""Create an offline duplicate-coordinate-copy disambiguation packet.

This helper is intentionally read-only. It consumes already captured
RiftReader artifacts and summarizes which current-reference-matching heap
copies have the best family/pointer context for the next proof step.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rift_live_test.reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return document


def parse_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    return int(text, 0)


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{value:X}"


def normalize_hex(value: str | int | None) -> str | None:
    parsed = parse_int(value)
    return int_hex(parsed)


def finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def get_path(document: dict[str, Any], dotted_path: str) -> Any:
    current: Any = document
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def resolve_artifact_path(repo_root: Path, path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    if path.is_absolute():
        return path
    return repo_root / path


def pointer_index(pointer_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in pointer_summary.get("rankedTargets") or []:
        key = normalize_hex(item.get("target"))
        if key:
            indexed[key] = item
    return indexed


def copy_role(current_truth: dict[str, Any], address_hex: str) -> str:
    best = current_truth.get("bestCurrentCandidate") or {}
    if normalize_hex(best.get("addressHex")) == address_hex:
        return "current-truth-best"
    return "duplicate-current-reference-copy"


def build_candidate_rows(
    *,
    current_truth: dict[str, Any],
    passive_readback: dict[str, Any],
    pointer_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    pointer_by_target = pointer_index(pointer_summary)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    matches = [
        item
        for item in passive_readback.get("BestReferenceMatches") or []
        if item.get("ReferenceMatchesReadback") is True and normalize_hex(item.get("CandidateAddressHex"))
    ]
    for match in matches:
        address = parse_int(match.get("CandidateAddressHex"))
        if address is None:
            continue
        address_hex = int_hex(address)
        if address_hex in seen:
            continue
        seen.add(address_hex)
        segment_base_hex = int_hex(address & ~0xFFFF)
        family_base_hex = int_hex(address & ~0xFFFFF)
        exact_pointer = pointer_by_target.get(address_hex or "")
        segment_pointer = pointer_by_target.get(segment_base_hex or "")
        family_pointer = pointer_by_target.get(family_base_hex or "")
        exact_hits = int((exact_pointer or {}).get("hitCount") or 0)
        segment_hits = int((segment_pointer or {}).get("hitCount") or 0)
        family_hits = int((family_pointer or {}).get("hitCount") or 0)
        exact_module_hits = int((exact_pointer or {}).get("moduleHitCount") or 0)
        segment_module_hits = int((segment_pointer or {}).get("moduleHitCount") or 0)
        family_module_hits = int((family_pointer or {}).get("moduleHitCount") or 0)
        exact_rift_hits = int((exact_pointer or {}).get("riftModuleHitCount") or 0)
        segment_rift_hits = int((segment_pointer or {}).get("riftModuleHitCount") or 0)
        family_rift_hits = int((family_pointer or {}).get("riftModuleHitCount") or 0)
        source_preview = bool(match.get("SourcePreviewMatchesReadback"))
        stable = bool(match.get("StableAcrossReadbackSamples"))
        reference_delta = finite_float(match.get("ReferenceMaxAbsDelta"))
        score = (
            (10000 if source_preview else 0)
            + (1000 if stable else 0)
            + (segment_hits * 10)
            + (family_hits * 4)
            + exact_hits
            + ((exact_module_hits + segment_module_hits + family_module_hits) * 500)
            + ((exact_rift_hits + segment_rift_hits + family_rift_hits) * 1000)
            - (reference_delta or 0.0)
        )
        rows.append(
            {
                "candidateId": match.get("CandidateId"),
                "addressHex": address_hex,
                "role": copy_role(current_truth, address_hex or ""),
                "segmentBaseHex": segment_base_hex,
                "familyBaseHex": family_base_hex,
                "referenceMaxAbsDelta": reference_delta,
                "sourcePreviewMatchesReadback": source_preview,
                "stableAcrossReadbackSamples": stable,
                "exactPointerHitCount": exact_hits,
                "segmentBasePointerHitCount": segment_hits,
                "familyBasePointerHitCount": family_hits,
                "modulePointerHitCount": exact_module_hits + segment_module_hits + family_module_hits,
                "riftModulePointerHitCount": exact_rift_hits + segment_rift_hits + family_rift_hits,
                "exactPointerSummary": (exact_pointer or {}).get("artifactPath"),
                "segmentPointerSummary": (segment_pointer or {}).get("artifactPath"),
                "familyPointerSummary": (family_pointer or {}).get("artifactPath"),
                "candidateOnly": True,
                "promotionEligible": False,
                "score": round(score, 6),
                "nextValidationStep": "Capture displaced-pose delta proof or approved access evidence before promotion.",
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            float(item["score"]),
            int(item["segmentBasePointerHitCount"]),
            int(item["familyBasePointerHitCount"]),
            str(item["addressHex"]),
        ),
        reverse=True,
    )


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Coordinate duplicate disambiguation packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Movement allowed: `{str(summary.get('movementAllowed')).lower()}`",
        f"- Promotion eligible: `{str(summary.get('promotionEligible')).lower()}`",
        "",
        "## Ranked duplicate coordinate copies",
        "",
        "| Rank | Address | Role | Ref max abs delta | Exact ptr hits | Segment-base ptr hits | Family-base ptr hits | Module ptr hits |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(summary.get("rankedCopies") or [], start=1):
        lines.append(
            f"| {index} | `{row.get('addressHex')}` | `{row.get('role')}` | "
            f"`{row.get('referenceMaxAbsDelta')}` | `{row.get('exactPointerHitCount')}` | "
            f"`{row.get('segmentBasePointerHitCount')}` | `{row.get('familyBasePointerHitCount')}` | "
            f"`{row.get('modulePointerHitCount')}` |"
        )
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            summary.get("verdict") or "",
            "",
            "## Required before movement",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in summary.get("requiredBeforeMovement") or [])
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{item}`" for item in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{item}`" for item in summary["warnings"])
    return "\n".join(lines).rstrip() + "\n"


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    current_truth_path = args.current_truth.resolve()
    current_truth = load_json(current_truth_path)
    passive_readback_path = args.passive_readback
    if passive_readback_path is None:
        passive_readback_path = resolve_artifact_path(
            repo_root,
            get_path(current_truth, "latestCoordinateReacquisition.latestPassiveStabilityReadback"),
        )
    pointer_summary_path = args.pointer_summary
    if passive_readback_path is None:
        raise ValueError("passive readback path was not supplied and current truth has no latest passive readback")
    if pointer_summary_path is None:
        raise ValueError("pointer summary path is required")
    passive_readback_path = passive_readback_path.resolve()
    pointer_summary_path = pointer_summary_path.resolve()
    passive_readback = load_json(passive_readback_path)
    pointer_summary = load_json(pointer_summary_path)
    run_dir = args.output_root or repo_root / "scripts" / "captures" / f"coordinate-duplicate-disambiguation-{utc_stamp()}"
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    rows = build_candidate_rows(
        current_truth=current_truth,
        passive_readback=passive_readback,
        pointer_summary=pointer_summary,
    )
    blockers: list[str] = []
    warnings: list[str] = []
    if not rows:
        blockers.append("no-current-reference-matching-duplicate-copies")
    if not any(int(row.get("modulePointerHitCount") or 0) > 0 for row in rows):
        warnings.append("no-module-or-static-pointer-hits-found")
    if len(rows) > 1:
        blockers.append("duplicate-current-reference-matching-heap-copies-not-disambiguated")
    packet: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "coordinate-duplicate-disambiguation-packet",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "candidate_only_ranked",
        "repoRoot": str(repo_root),
        "inputs": {
            "currentTruth": str(current_truth_path),
            "passiveReadback": str(passive_readback_path),
            "pointerSummary": str(pointer_summary_path),
        },
        "counts": {
            "referenceMatchCopyCount": len(rows),
            "pointerScannedTargetCount": get_path(pointer_summary, "counts.scannedTargetCount"),
        },
        "rankedCopies": rows,
        "bestCandidate": rows[0] if rows else None,
        "verdict": (
            "Candidate-only: ranked current-reference-matching heap copies by pointer/family context. "
            "This packet does not prove a movement source or static chain."
        ),
        "requiredBeforeMovement": [
            "displaced-pose API-vs-memory delta agreement",
            "static/root provenance or approved access evidence",
            "restart validation",
            "same-target ProofOnly pass",
        ],
        "movementAllowed": False,
        "promotionEligible": False,
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "processMemoryReadStarted": False,
            "offlineAnalysisOnly": True,
        },
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "next": {
            "recommendedAction": (
                "Use the ranked copies as priors for a displaced-pose family snapshot sequence or approved bounded access capture."
            ),
        },
    }
    write_json(summary_json, packet)
    write_text_atomic(summary_md, render_markdown(packet))
    return packet


def build_parser() -> argparse.ArgumentParser:
    repo_root = repo_root_from_script()
    parser = argparse.ArgumentParser(description="Build an offline duplicate coordinate-copy disambiguation packet.")
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--current-truth", type=Path, default=repo_root / "docs" / "recovery" / "current-truth.json")
    parser.add_argument("--passive-readback", type=Path, default=None)
    parser.add_argument("--pointer-summary", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    packet = build_packet(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": packet["status"],
                    "summaryJson": packet["artifacts"]["summaryJson"],
                    "summaryMarkdown": packet["artifacts"]["summaryMarkdown"],
                    "referenceMatchCopyCount": packet["counts"]["referenceMatchCopyCount"],
                    "bestCandidate": packet["bestCandidate"],
                    "blockers": packet["blockers"],
                    "warnings": packet["warnings"],
                },
                separators=(",", ":"),
            )
        )
    return 2 if packet["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
