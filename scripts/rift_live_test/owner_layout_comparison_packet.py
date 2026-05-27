from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parent_slot_neighborhood_summary import safe_list, safe_mapping
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_CURRENT_PROOF_POINTER = Path("docs/recovery/current-proof-anchor-readback.json")
DEFAULT_CURRENT_TRUTH = Path("docs/recovery/current-truth.json")
DEFAULT_OUTPUT_ROOT = Path("scripts/captures")
HISTORICAL_OWNER_TEMPLATE = {
    "ownerBase": "0x20005B304E0",
    "coordField": "0x20005B30800",
    "coordOffsets": ["0x320", "0x324", "0x328"],
    "epoch": "PID 63412 historical",
    "classification": "historical-owner-shape-template",
    "promotionEligible": False,
}
HISTORICAL_COMPARISON_CANDIDATES = [
    {
        "address": "0x1FF94EC0000",
        "classification": "historical-moving-slot-family",
        "use": "displacement-tracking shape comparison only",
        "promotionEligible": False,
    },
    {
        "address": "0x1FF08502BC8",
        "classification": "historical-actor-like-or-scene-object-candidate",
        "use": "actor-like shape comparison only",
        "promotionEligible": False,
    },
]


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


def load_json_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        return rows
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
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


def resolve_repo_path(repo_root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / path


def find_latest_summary(repo_root: Path, pattern: str, predicate: Callable[[Mapping[str, Any]], bool]) -> Path | None:
    candidates = sorted((repo_root / "scripts" / "captures").glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            doc = load_json_object(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if predicate(doc):
            return path
    return None


def current_candidate_from_pointer(pointer: Mapping[str, Any], repo_root: Path) -> dict[str, Any]:
    candidate_source = safe_mapping(pointer.get("riftscanCandidateSource"))
    candidate_file = resolve_repo_path(repo_root, candidate_source.get("matchFile"))
    candidate_id = candidate_source.get("candidateId")
    candidate_address = norm_hex(candidate_source.get("sourceAbsoluteAddressHex"))
    candidate_row: dict[str, Any] | None = None
    if candidate_file and candidate_file.exists():
        for row in load_json_records(candidate_file):
            row_id = row.get("candidate_id") or row.get("candidateId")
            row_address = norm_hex(row.get("absolute_address_hex") or row.get("absoluteAddressHex"))
            if (candidate_id and row_id == candidate_id) or (candidate_address and row_address == candidate_address):
                candidate_row = row
                break
    return {
        "candidateId": candidate_id,
        "addressHex": candidate_address,
        "candidateFile": str(candidate_file) if candidate_file else None,
        "candidateFileExists": bool(candidate_file and candidate_file.exists()),
        "candidateRowFound": candidate_row is not None,
        "sourceBaseAddressHex": norm_hex(candidate_source.get("sourceBaseAddressHex") or candidate_source.get("sourceBaseAddress")),
        "sourceOffsetHex": norm_hex(candidate_source.get("sourceOffsetHex") or candidate_source.get("sourceOffset")),
        "axisOrder": candidate_source.get("axisOrder") or (candidate_row or {}).get("axis_order"),
        "supportCount": candidate_source.get("supportCount") or (candidate_row or {}).get("support_count"),
        "bestMaxAbsDistance": candidate_source.get("bestMaxAbsDistance") or (candidate_row or {}).get("best_max_abs_distance"),
        "sourceKind": candidate_source.get("sourceKind"),
        "classification": "current-proof-anchor",
        "promotionEligible": False,
    }


def summarize_family_analysis(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    doc = load_json_object(path)
    anchor = safe_mapping(doc.get("anchor"))
    runs = safe_list(doc.get("runs"))
    return {
        "path": str(path),
        "status": doc.get("status"),
        "anchor": {
            "addressHex": anchor.get("addressHex"),
            "candidateId": anchor.get("candidateId"),
            "family16MiBBaseHex": anchor.get("family16MiBBaseHex"),
            "megaPage1MiBBaseHex": anchor.get("megaPage1MiBBaseHex"),
            "page4KiBBaseHex": anchor.get("page4KiBBaseHex"),
        },
        "runCount": len(runs),
        "safety": doc.get("safety"),
    }


def summarize_family_inspector(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    doc = load_json_object(path)
    hits = safe_list(doc.get("hits"))
    return {
        "path": str(path),
        "status": doc.get("status"),
        "scanWindow": doc.get("scanWindow"),
        "hitCount": doc.get("hitCount"),
        "knownCandidateCount": doc.get("knownCandidateCount"),
        "hits": [
            {
                "address": hit.get("address"),
                "offsetFromWindowBase": hit.get("offsetFromWindowBase"),
                "knownCandidate": hit.get("knownCandidate"),
                "offsetCorrectedMaxAbsDelta": hit.get("offsetCorrectedMaxAbsDelta"),
            }
            for hit in hits
            if isinstance(hit, Mapping)
        ],
        "safety": doc.get("safety"),
    }


def summarize_pointer_family(path: Path | None, candidate_address: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    doc = load_json_object(path)
    ranked = safe_list(doc.get("rankedTargets"))
    target_rows = []
    ref_storage = None
    module_hits = 0
    rift_module_hits = 0
    for row in ranked:
        if not isinstance(row, Mapping):
            continue
        module_hits += int(row.get("moduleHitCount") or 0)
        rift_module_hits += int(row.get("riftModuleHitCount") or 0)
        hits = safe_list(row.get("hits"))
        target_rows.append(
            {
                "target": row.get("target"),
                "hitCount": row.get("hitCount"),
                "moduleHitCount": row.get("moduleHitCount"),
                "riftModuleHitCount": row.get("riftModuleHitCount"),
                "hits": [{"address": hit.get("address"), "module": hit.get("module")} for hit in hits if isinstance(hit, Mapping)],
            }
        )
        if norm_hex(row.get("target")) == candidate_address and hits:
            first_hit = safe_mapping(hits[0])
            ref_storage = {
                "address": first_hit.get("address"),
                "regionBase": first_hit.get("regionBase"),
                "module": first_hit.get("module"),
                "pointsTo": candidate_address,
            }
    return {
        "path": str(path),
        "status": doc.get("status"),
        "counts": doc.get("counts"),
        "moduleHitCount": module_hits,
        "riftModuleHitCount": rift_module_hits,
        "refStorage": ref_storage,
        "rankedTargets": target_rows,
        "safety": doc.get("safety"),
    }


def summarize_ref_storage(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    doc = load_json_object(path)
    analysis = safe_mapping(doc.get("analysis"))
    owner = safe_mapping(doc.get("owner"))
    exact_counts = safe_mapping(analysis.get("exactTargetCounts"))
    return {
        "path": str(path),
        "status": doc.get("status"),
        "ownerAddress": owner.get("address"),
        "exactTargetCounts": dict(exact_counts),
        "modulePointerCount": analysis.get("modulePointerCount"),
        "ownerWindowModulePointerCount": analysis.get("ownerWindowModulePointerCount"),
        "regionMatchCount": analysis.get("regionMatchCount"),
        "classification": "heap-local-ref-storage",
        "promotionEligible": False,
        "safety": doc.get("safety"),
    }


def summarize_owner_batch(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    doc = load_json_object(path)
    counts = safe_mapping(doc.get("counts"))
    ranked_rows = safe_list(doc.get("rankedRows"))
    module_hints = safe_list(doc.get("moduleRvaHints"))
    return {
        "path": str(path),
        "status": doc.get("status"),
        "counts": dict(counts),
        "topRows": [
            {
                "owner": row.get("owner"),
                "score": row.get("score"),
                "scoreReasons": row.get("scoreReasons"),
                "exactTargetCounts": row.get("exactTargetCounts"),
                "regionMatchCount": row.get("regionMatchCount"),
                "modulePointerCount": row.get("modulePointerCount"),
                "ownerWindowModulePointerCount": row.get("ownerWindowModulePointerCount"),
                "summaryJson": row.get("summaryJson"),
            }
            for row in ranked_rows[:5]
            if isinstance(row, Mapping)
        ],
        "moduleRvaHints": [
            {
                "rva": hint.get("rva"),
                "ownerWindowHitCount": hint.get("ownerWindowHitCount"),
                "ownerCount": hint.get("ownerCount"),
                "owners": hint.get("owners"),
                "examples": hint.get("examples"),
                "candidateOnly": hint.get("candidateOnly", True),
                "promotionEligible": hint.get("promotionEligible", False),
            }
            for hint in module_hints
            if isinstance(hint, Mapping)
        ],
        "safety": doc.get("safety"),
    }


def build_classification(
    *,
    candidate: Mapping[str, Any],
    pointer_family: Mapping[str, Any] | None,
    ref_storage: Mapping[str, Any] | None,
    owner_batch: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    pointer_module_hits = int(safe_mapping(pointer_family).get("moduleHitCount") or 0)
    pointer_rift_hits = int(safe_mapping(pointer_family).get("riftModuleHitCount") or 0)
    ref_module_count = int(safe_mapping(ref_storage).get("ownerWindowModulePointerCount") or 0)
    batch_counts = safe_mapping(safe_mapping(owner_batch).get("counts"))
    batch_module_hint_count = int(batch_counts.get("moduleRvaHintCount") or 0)
    static_root_status = "candidate-hints-present-not-root" if batch_module_hint_count else "absent"
    static_root_evidence = [
        f"pointerFamily.moduleHitCount={pointer_module_hits}",
        f"pointerFamily.riftModuleHitCount={pointer_rift_hits}",
        f"refStorage.ownerWindowModulePointerCount={ref_module_count}",
    ]
    if batch_module_hint_count:
        static_root_evidence.append(f"ownerBatch.moduleRvaHintCount={batch_module_hint_count}")
        static_root_evidence.append("module RVA hints are owner-window hints only; no resolver or restart-stable root is proven")
    return [
        {
            "class": "proof-api-buffer",
            "status": "supported",
            "evidence": [
                f"current proof pointer candidate {candidate.get('candidateId')} at {candidate.get('addressHex')}",
                f"sourceKind={candidate.get('sourceKind')}",
            ],
            "promotionEligible": False,
        },
        {
            "class": "heap-local-ref-storage",
            "status": "supported" if ref_storage else "not-observed",
            "evidence": [
                f"{safe_mapping(ref_storage).get('ownerAddress')} -> {candidate.get('addressHex')}",
                f"regionMatchCount={safe_mapping(ref_storage).get('regionMatchCount')}",
            ]
            if ref_storage
            else [],
            "promotionEligible": False,
        },
        {
            "class": "copy-or-mirror-family",
            "status": "possible",
            "evidence": ["current anchor behaves as proof/API-family coordinate evidence; no owner/root relation proven"],
            "promotionEligible": False,
        },
        {
            "class": "actor-like-offset-candidate",
            "status": "not-proven-current",
            "evidence": ["no current owner base + coordinate offset relation like owner+0x320 is present in reviewed artifacts"],
            "promotionEligible": False,
        },
        {
            "class": "owner-layout-candidate",
            "status": "historical-template-only",
            "evidence": [
                "historical PID 63412 owner 0x20005B304E0 with coordinate offsets +0x320/+0x324/+0x328",
                "no current-PID owner-layout match found in reviewed artifacts",
            ],
            "promotionEligible": False,
        },
        {
            "class": "module-rva-static-owner-root",
            "status": static_root_status,
            "evidence": static_root_evidence,
            "promotionEligible": False,
        },
    ]


def relationship_offsets(candidate: Mapping[str, Any], pointer_family: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    candidate_address = parse_int(candidate.get("addressHex"))
    source_base = parse_int(candidate.get("sourceBaseAddressHex"))
    rows: list[dict[str, Any]] = []
    if candidate_address is not None and source_base is not None:
        rows.append(
            {
                "relationship": "current-proof-source-base-to-coordinate",
                "from": hex_int(source_base),
                "to": hex_int(candidate_address),
                "offset": hex_int(candidate_address - source_base),
                "templateMatch": "proof-anchor-local-offset-not-owner-shape",
                "promotionEligible": False,
            }
        )
    ref_storage = safe_mapping(safe_mapping(pointer_family).get("refStorage"))
    ref_address = parse_int(ref_storage.get("address"))
    if candidate_address is not None and ref_address is not None:
        rows.append(
            {
                "relationship": "current-ref-storage-to-coordinate-target",
                "from": hex_int(ref_address),
                "to": hex_int(candidate_address),
                "offset": hex_int(candidate_address - ref_address),
                "templateMatch": "pointer-edge-not-owner-coordinate-field",
                "promotionEligible": False,
            }
        )
    rows.append(
        {
            "relationship": "historical-owner-template-to-coordinate-field",
            "from": HISTORICAL_OWNER_TEMPLATE["ownerBase"],
            "to": HISTORICAL_OWNER_TEMPLATE["coordField"],
            "offset": "0x320",
            "templateMatch": "historical-template-only",
            "promotionEligible": False,
        }
    )
    return rows


def safety_ledger() -> dict[str, bool]:
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "debuggerAttached": False,
        "debugActiveProcessStopCalled": False,
        "targetMemoryBytesReadByThisPacket": False,
        "targetMemoryBytesWritten": False,
        "providerWrites": False,
        "gitMutation": False,
        "proofPromotion": False,
        "actorChainPromotion": False,
    }


def build_summary(
    *,
    repo_root: Path,
    current_truth_path: Path,
    current_proof_pointer_path: Path,
    family_analysis_path: Path | None = None,
    family_inspector_path: Path | None = None,
    pointer_family_path: Path | None = None,
    ref_storage_path: Path | None = None,
    owner_batch_path: Path | None = None,
) -> dict[str, Any]:
    current_truth = load_json_object(current_truth_path)
    pointer = load_json_object(current_proof_pointer_path)
    candidate = current_candidate_from_pointer(pointer, repo_root)
    candidate_address = str(candidate.get("addressHex") or "")

    if family_analysis_path is None:
        family_analysis_path = find_latest_summary(
            repo_root,
            "current-pid-family-neighborhood-analysis-*/summary.json",
            lambda doc: norm_hex(safe_mapping(doc.get("anchor")).get("addressHex")) == candidate_address,
        )
    if family_inspector_path is None:
        family_inspector_path = find_latest_summary(
            repo_root,
            "current-pid-family-neighborhood-inspector-*/summary.json",
            lambda doc: any(norm_hex(safe_mapping(hit).get("address")) == candidate_address for hit in safe_list(doc.get("hits"))),
        )
    if pointer_family_path is None:
        pointer_family_path = find_latest_summary(
            repo_root,
            "pointer-family-scan-*/summary.json",
            lambda doc: any(norm_hex(safe_mapping(row).get("target")) == candidate_address for row in safe_list(doc.get("rankedTargets"))),
        )
    if ref_storage_path is None:
        ref_storage_path = find_latest_summary(
            repo_root,
            "pointer-owner-neighborhood-inspector-*/summary.json",
            lambda doc: candidate_address in {norm_hex(key) for key in safe_mapping(safe_mapping(doc.get("analysis")).get("exactTargetCounts")).keys()},
        )
    if owner_batch_path is None:
        owner_batch_path = find_latest_summary(
            repo_root,
            "pointer-owner-batch-currentpid-*/summary.json",
            lambda doc: any(
                norm_hex(safe_mapping(row).get("sourceTarget")) == candidate_address
                for row in safe_list(doc.get("rankedRows"))
            ),
        )

    family_analysis = summarize_family_analysis(family_analysis_path)
    family_inspector = summarize_family_inspector(family_inspector_path)
    pointer_family = summarize_pointer_family(pointer_family_path, candidate_address)
    ref_storage = summarize_ref_storage(ref_storage_path)
    owner_batch = summarize_owner_batch(owner_batch_path)
    classifications = build_classification(
        candidate=candidate,
        pointer_family=pointer_family,
        ref_storage=ref_storage,
        owner_batch=owner_batch,
    )
    offsets = relationship_offsets(candidate, pointer_family)

    blockers = [
        "actor-static-chain-not-promoted",
        "no-static-resolver-promoted",
        "not-restart-validated-for-static-actor-chain",
        "blocked-no-debugger-access-provenance",
        "x64dbg-attach-blocked-existing-debug-object",
        "debugactiveprocessstop-access-denied-winerr-5",
        "module-rva-static-owner-root-absent-in-reviewed-artifacts",
        "module-rva-hints-are-not-static-resolver",
        "current-owner-plus-0x320-shape-not-found",
    ]
    target = safe_mapping(current_truth.get("target"))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "owner-layout-comparison-packet",
        "generatedAtUtc": utc_iso(),
        "status": "blocked",
        "verdict": "candidate-only-no-current-owner-layout-root",
        "repoRoot": str(repo_root),
        "target": {
            "processName": target.get("processName") or safe_mapping(pointer.get("target")).get("processName"),
            "processId": target.get("processId") or safe_mapping(pointer.get("target")).get("processId"),
            "targetWindowHandle": target.get("targetWindowHandle") or safe_mapping(pointer.get("target")).get("targetWindowHandle"),
            "processStartUtc": target.get("processStartUtc"),
            "moduleBase": target.get("moduleBase"),
        },
        "inputs": {
            "currentTruthJson": str(current_truth_path.resolve()),
            "currentProofPointerJson": str(current_proof_pointer_path.resolve()),
            "familyAnalysisSummaryJson": str(family_analysis_path.resolve()) if family_analysis_path else None,
            "familyInspectorSummaryJson": str(family_inspector_path.resolve()) if family_inspector_path else None,
            "pointerFamilySummaryJson": str(pointer_family_path.resolve()) if pointer_family_path else None,
            "refStorageSummaryJson": str(ref_storage_path.resolve()) if ref_storage_path else None,
            "ownerBatchSummaryJson": str(owner_batch_path.resolve()) if owner_batch_path else None,
        },
        "currentProofAnchor": candidate,
        "currentEvidence": {
            "familyAnalysis": family_analysis,
            "familyInspector": family_inspector,
            "pointerFamily": pointer_family,
            "refStorage": ref_storage,
            "ownerBatch": owner_batch,
        },
        "relationshipOffsets": offsets,
        "historicalTemplates": {
            "ownerShape": HISTORICAL_OWNER_TEMPLATE,
            "comparisonCandidates": HISTORICAL_COMPARISON_CANDIDATES,
        },
        "classificationMatrix": classifications,
        "negativeEvidence": [
            "Reviewed current pointer-family evidence has zero module and zero rift_x64 hits.",
            "The exact ref-storage hit is heap-local and is not a static root.",
            "Current proof source +0x40 and ref-storage pointer distance +0x9A50 do not establish the historical owner+0x320 coordinate-field shape.",
            "Owner-window module RVA hints from targeted expansion remain candidate-only and do not form a resolver.",
            "Current proof anchor is proof/API-family evidence and must not be treated as player actor ownership.",
            "Historical PID 63412 and PID 28248 absolute addresses are stale templates or audit history only.",
            "Broad heap-only pointer scans should not be repeated unchanged.",
        ],
        "blockers": blockers,
        "warnings": [
            "This packet reads existing artifacts only and does not perform discovery scans.",
            "All absolute addresses in this packet are current-epoch evidence or historical templates, not restart-stable truth.",
            "Promotion requires module/RVA/static-owner provenance plus API-now vs chain-now and restart validation.",
        ],
        "safety": safety_ledger(),
        "next": {
            "singleBestStep": (
                "If continuing no-debug, run a targeted current-PID owner/ref-storage structure expansion around "
                "0x23863A1D400 and the 0x23863A26E50 candidate region, explicitly searching for an owner+0x320-like "
                "coordinate-bearing shape or module/RVA/static-owner hints; stop if evidence remains heap-only."
            ),
            "requiresApprovalBefore": [
                "live input or movement",
                "x64dbg/debugger attach or DebugActiveProcessStop",
                "Cheat Engine",
                "provider repo writes",
                "proof or actor-chain promotion",
                "git stage/commit/push/revert/cleanup",
            ],
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    target = safe_mapping(summary.get("target"))
    anchor = safe_mapping(summary.get("currentProofAnchor"))
    evidence = safe_mapping(summary.get("currentEvidence"))
    pointer_family = safe_mapping(evidence.get("pointerFamily"))
    ref_storage = safe_mapping(evidence.get("refStorage"))
    owner_batch = safe_mapping(evidence.get("ownerBatch"))
    owner_batch_counts = safe_mapping(owner_batch.get("counts"))
    lines = [
        "# Owner-layout comparison packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Target: `{target.get('processName')}` PID `{target.get('processId')}` HWND `{target.get('targetWindowHandle')}`",
        f"- Proof anchor: `{anchor.get('candidateId')}` at `{anchor.get('addressHex')}`",
        "",
        "## Current evidence",
        "",
        "| Evidence | Result | Promotion eligible |",
        "|---|---|---:|",
        (
            f"| Proof anchor | `{anchor.get('classification')}`; file exists "
            f"`{str(anchor.get('candidateFileExists')).lower()}` | `false` |"
        ),
        (
            f"| Pointer family | module hits `{pointer_family.get('moduleHitCount')}`, "
            f"rift hits `{pointer_family.get('riftModuleHitCount')}` | `false` |"
        ),
        (
            f"| Ref storage | owner `{ref_storage.get('ownerAddress')}`, "
            f"region matches `{ref_storage.get('regionMatchCount')}`, "
            f"owner-window module pointers `{ref_storage.get('ownerWindowModulePointerCount')}` | `false` |"
        ),
        (
            f"| Targeted owner batch | inspected owners `{owner_batch_counts.get('inspectedOwnerCount')}`, "
            f"module RVA hints `{owner_batch_counts.get('moduleRvaHintCount')}` | `false` |"
        ),
        "",
        "## Relationship offsets",
        "",
        "| Relationship | From | To | Offset | Template match | Promotion eligible |",
        "|---|---|---|---:|---|---:|",
    ]
    for row in safe_list(summary.get("relationshipOffsets")):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"| `{row.get('relationship')}` | `{row.get('from')}` | `{row.get('to')}` | "
            f"`{row.get('offset')}` | `{row.get('templateMatch')}` | "
            f"`{str(row.get('promotionEligible')).lower()}` |"
        )
    lines.extend(
        [
            "",
        "## Classification matrix",
        "",
        "| Class | Status | Evidence | Promotion eligible |",
        "|---|---|---|---:|",
        ]
    )
    for row in safe_list(summary.get("classificationMatrix")):
        if not isinstance(row, Mapping):
            continue
        evidence_text = "; ".join(str(item) for item in safe_list(row.get("evidence")))
        lines.append(
            f"| `{row.get('class')}` | `{row.get('status')}` | {evidence_text} | "
            f"`{str(row.get('promotionEligible')).lower()}` |"
        )
    lines.extend(
        [
            "",
            "## Blockers",
            "",
        ]
    )
    for blocker in safe_list(summary.get("blockers")):
        lines.append(f"- `{blocker}`")
    lines.extend(
        [
            "",
            "## Next single best step",
            "",
            str(safe_mapping(summary.get("next")).get("singleBestStep")),
            "",
            "Do not promote, move, attach a debugger, use CE, or write provider repos from this packet.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-debug/read-only owner-layout comparison packet from existing artifacts."
    )
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--current-truth-json", default=str(DEFAULT_CURRENT_TRUTH))
    parser.add_argument("--current-proof-pointer-json", default=str(DEFAULT_CURRENT_PROOF_POINTER))
    parser.add_argument("--family-analysis-summary-json", default=None)
    parser.add_argument("--family-inspector-summary-json", default=None)
    parser.add_argument("--pointer-family-summary-json", default=None)
    parser.add_argument("--ref-storage-summary-json", default=None)
    parser.add_argument("--owner-batch-summary-json", default=None)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_module()
    current_truth_path = resolve_repo_path(repo_root, args.current_truth_json)
    current_pointer_path = resolve_repo_path(repo_root, args.current_proof_pointer_json)
    if current_truth_path is None or current_pointer_path is None:
        raise ValueError("current truth and current proof pointer paths are required")
    summary = build_summary(
        repo_root=repo_root,
        current_truth_path=current_truth_path,
        current_proof_pointer_path=current_pointer_path,
        family_analysis_path=resolve_repo_path(repo_root, args.family_analysis_summary_json),
        family_inspector_path=resolve_repo_path(repo_root, args.family_inspector_summary_json),
        pointer_family_path=resolve_repo_path(repo_root, args.pointer_family_summary_json),
        ref_storage_path=resolve_repo_path(repo_root, args.ref_storage_summary_json),
        owner_batch_path=resolve_repo_path(repo_root, args.owner_batch_summary_json),
    )
    output_root = resolve_repo_path(repo_root, args.output_root)
    if output_root is None:
        raise ValueError("output root is required")
    output_dir = output_root / f"owner-layout-comparison-packet-{utc_stamp()}"
    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary.md"
    summary.setdefault("artifacts", {})
    summary["artifacts"] = {
        "outputDir": str(output_dir.resolve()),
        "summaryJson": str(summary_json.resolve()),
        "summaryMarkdown": str(summary_md.resolve()),
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, render_markdown(summary))
    if args.json:
        print(json.dumps(summary))
    else:
        print(f"wrote {summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
