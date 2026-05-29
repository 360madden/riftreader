from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parent_slot_neighborhood_summary import safe_mapping
from .reports import write_json, write_text_atomic

SCHEMA_VERSION = 1

# ── Per-blocker diagnostic guidance ────────────────────────────────────────
# Each entry maps a blocker prefix (matched via str.startswith) to a
# human-readable diagnostic: what the blocker means and what to do about it.
BLOCKER_DIAGNOSTICS: dict[str, dict[str, str]] = {
    "current-proof-anchor-not-passed": {
        "meaning": "The current ProofOnly anchor is not passing for the active target PID/HWND.",
        "action": "Re-run proof-anchor validation against the exact live PID/HWND. If the target has restarted, reacquire a fresh proof anchor before attempting promotion.",
    },
    "actor-candidate-readback-not-passed": {
        "meaning": "The actor-chain candidate readback did not return a passing best candidate.",
        "action": "Rerun candidate readback against the current live process. Check that the candidate address is readable and the offset-corrected delta is within tolerance.",
    },
    "static-resolver-candidate-not-promoted": {
        "meaning": "A static resolver candidate exists but has not been through the full promotion gate suite (displacement validation, reboot survival, API-now cross-check).",
        "action": "Complete the promotion gate suite: displacement validation, reboot/relogin survival test, and API-now vs static-chain-now cross-check before promotion review.",
    },
    "no-static-resolver-promoted": {
        "meaning": "No static resolver chain has been promoted. The actor chain remains candidate-only.",
        "action": "Continue no-debug root discovery to find a viable static resolver candidate. Once found, run the full promotion gate suite before promotion review.",
    },
    "no-debug-root-lanes-exhausted": {
        "meaning": "All no-debugger root discovery lanes have been exhausted without finding viable module/RVA hits.",
        "action": "Broaden pointer-scan targets or request explicit approval for a single bounded debugger access-provenance step to unblock discovery.",
    },
    "blocked-no-debugger-access-provenance": {
        "meaning": "The current-truth static chain status reports a debugger-access-provenance blocker. The chain cannot be promoted without debugger-backed evidence.",
        "action": "Either resolve the debugger-access-provenance gap with a bounded x64dbg/CE session (requires explicit approval), or pursue alternative no-debug evidence lanes.",
    },
    "artifact-missing": {
        "meaning": "One or more required artifact files are missing from the expected paths.",
        "action": "Check the artifact paths listed in the blockers. Regenerate missing artifacts from the current live session or restore them from backups.",
    },
}


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


def resolve_path(repo_root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def load_optional(repo_root: Path, value: str | Path | None) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if value is None:
        return None, None, None
    path = resolve_path(repo_root, str(value))
    if path is None:
        return None, None, None
    if not path.exists():
        return None, str(path), "missing"
    return load_json_object(path), str(path), None


def artifact_value(truth: Mapping[str, Any], key: str) -> str | None:
    artifacts = safe_mapping(truth.get("canonicalArtifacts"))
    value = artifacts.get(key)
    return str(value) if value else None


def first_nonempty(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def summarize_pointer_scan(path: str, document: Mapping[str, Any]) -> dict[str, Any]:
    counts = safe_mapping(document.get("counts"))
    ranked = document.get("rankedTargets") if isinstance(document.get("rankedTargets"), list) else []
    targets_with_hits = 0
    total_hits = 0
    module_hits = 0
    rift_hits = 0
    for item in ranked:
        row = safe_mapping(item)
        hit_count = int(row.get("hitCount") or 0)
        targets_with_hits += 1 if hit_count else 0
        total_hits += hit_count
        module_hits += int(row.get("moduleHitCount") or 0)
        rift_hits += int(row.get("riftModuleHitCount") or 0)
    return {
        "path": path,
        "status": document.get("status"),
        "scannedTargetCount": int(counts.get("scannedTargetCount") or 0),
        "queuedTargetCount": int(counts.get("queuedTargetCount") or 0),
        "targetsWithHits": targets_with_hits,
        "totalHits": total_hits,
        "moduleHitCount": module_hits,
        "riftModuleHitCount": rift_hits,
        "candidateOnly": True,
        "promotionEligible": False,
    }


def summarize_exhaustion(path: str, document: Mapping[str, Any]) -> dict[str, Any]:
    totals = safe_mapping(document.get("totals"))
    return {
        "path": path,
        "status": document.get("status"),
        "verdict": document.get("verdict"),
        "scannedTargetCount": int(totals.get("scannedTargetCount") or 0),
        "moduleHitCount": int(totals.get("moduleHitCount") or 0),
        "riftModuleHitCount": int(totals.get("riftModuleHitCount") or 0),
    }


def summarize_static_resolver(truth: Mapping[str, Any]) -> dict[str, Any]:
    static_status = safe_mapping(truth.get("staticChainStatus"))
    primary = safe_mapping(static_status.get("primaryCandidate"))
    latest_api = safe_mapping(static_status.get("latestApiNowValidation"))
    latest_api_refresh = safe_mapping(static_status.get("latestFreshApiSourceRefreshAttempt"))
    latest_extended = safe_mapping(static_status.get("latestExtendedStaticRootDiscovery"))
    chain = primary.get("chain")
    root_rva = primary.get("rootRva")
    owner_address = primary.get("ownerAddress")
    coordinate_address = primary.get("coordinateAddress")
    complete = bool(chain and root_rva and owner_address and coordinate_address)
    promoted = bool(complete and static_status.get("promotionAllowed"))
    return {
        "status": static_status.get("status"),
        "complete": complete,
        "promoted": promoted,
        "promotionAllowed": bool(static_status.get("promotionAllowed")),
        "chain": chain,
        "rootModule": primary.get("rootModule"),
        "rootRva": root_rva,
        "rootAddress": primary.get("rootAddress"),
        "ownerAddress": owner_address,
        "coordinateAddress": coordinate_address,
        "restartValidated": bool(primary.get("restartRelogSurvived")),
        "latestApiNowValidationStatus": latest_api.get("status"),
        "latestFreshApiSourceRefreshStatus": latest_api_refresh.get("status"),
        "latestExtendedRootDiscoveryStatus": latest_extended.get("status"),
        "candidateOnly": not promoted,
        "promotionEligible": False,
    }


def display_artifact_path(path: str) -> str:
    artifact_path = Path(path)
    if artifact_path.name.lower() == "summary.json" and artifact_path.parent.name:
        return f"{artifact_path.parent.name}/{artifact_path.name}"
    return artifact_path.name or path


def build_self_test() -> dict[str, Any]:
    repo_root = Path(".")
    truth = {
        "target": {"processName": "rift_x64", "processId": 1, "targetWindowHandle": "0x10"},
        "canonicalArtifacts": {},
        "staticChainStatus": {"blockers": ["blocked-no-debugger-access-provenance"]},
    }
    proof = {"status": "current-target-proofonly-passed", "riftscanCandidateSource": {"sourceAbsoluteAddressHex": "0x1000"}}
    readback = {
        "status": "passed",
        "bestReadback": {
            "candidateId": "c1",
            "addressHex": "0x2000",
            "classification": "offset-corrected-current-coordinate-candidate",
            "offsetCorrectedMaxAbsDelta": 0.01,
            "truthReadiness": "candidate_only_not_movement_proof",
        },
    }
    scan = {"status": "passed", "counts": {"scannedTargetCount": 1}, "rankedTargets": [{"hitCount": 1, "moduleHitCount": 0, "riftModuleHitCount": 0}]}
    summary = build_summary_from_documents(
        repo_root=repo_root,
        truth=truth,
        proof=proof,
        candidate_readback=readback,
        root_sweep={},
        root_family={},
        pointer_scans=[("scan.json", scan)],
        exhaustion_reports=[],
        missing_artifacts=[],
    )
    return {"status": "passed" if summary["verdict"] == "candidate-only-no-debug-root-blocked" else "failed", "summary": summary}


def _build_blocker_diagnostics(blockers: list[str]) -> list[dict[str, str]]:
    """Build per-blocker diagnostic guidance for each active blocker."""
    diagnostics: list[dict[str, str]] = []
    seen_prefixes: set[str] = set()
    for blocker in blockers:
        matched = False
        for prefix, diag in BLOCKER_DIAGNOSTICS.items():
            if blocker.startswith(prefix):
                if prefix not in seen_prefixes:
                    diagnostics.append({
                        "blocker": blocker,
                        "meaning": diag["meaning"],
                        "action": diag["action"],
                    })
                    seen_prefixes.add(prefix)
                matched = True
                break
        if not matched:
            diagnostics.append({
                "blocker": blocker,
                "meaning": "Unrecognized blocker. Review the blocker string for context.",
                "action": "Inspect related artifacts and gates to determine the root cause.",
            })
    return diagnostics


def build_summary_from_documents(
    *,
    repo_root: Path,
    truth: Mapping[str, Any],
    proof: Mapping[str, Any] | None,
    candidate_readback: Mapping[str, Any] | None,
    root_sweep: Mapping[str, Any] | None,
    root_family: Mapping[str, Any] | None,
    pointer_scans: list[tuple[str, Mapping[str, Any]]],
    exhaustion_reports: list[tuple[str, Mapping[str, Any]]],
    missing_artifacts: list[str],
) -> dict[str, Any]:
    proof_doc = safe_mapping(proof)
    readback_doc = safe_mapping(candidate_readback)
    best_readback = safe_mapping(readback_doc.get("bestReadback"))
    root_top = safe_mapping(safe_mapping(root_sweep).get("topOwnerFieldCandidate"))
    family_counts = safe_mapping(safe_mapping(root_family).get("counts"))
    scan_summaries = [summarize_pointer_scan(path, doc) for path, doc in pointer_scans]
    exhaustion_summaries = [summarize_exhaustion(path, doc) for path, doc in exhaustion_reports]
    total_module_hits = sum(item["moduleHitCount"] for item in scan_summaries)
    total_rift_hits = sum(item["riftModuleHitCount"] for item in scan_summaries)
    current_proof = proof_doc.get("status") == "current-target-proofonly-passed"
    candidate_passed = readback_doc.get("status") == "passed" and bool(best_readback)
    static_resolver = summarize_static_resolver(truth)
    static_resolver_found = bool(static_resolver.get("complete"))
    static_resolver_promoted = bool(static_resolver.get("promoted"))
    no_debug_roots_exhausted = bool(scan_summaries) and total_module_hits == 0 and total_rift_hits == 0 and not static_resolver_found
    promotion_allowed = bool(current_proof and candidate_passed and static_resolver_promoted)
    blockers: list[str] = []
    if missing_artifacts:
        blockers.extend(f"artifact-missing:{path}" for path in missing_artifacts)
    if not current_proof:
        blockers.append("current-proof-anchor-not-passed")
    if not candidate_passed and not static_resolver_found:
        blockers.append("actor-candidate-readback-not-passed")
    if static_resolver_found and not static_resolver_promoted:
        blockers.append("static-resolver-candidate-not-promoted")
    if not static_resolver_found:
        blockers.append("no-static-resolver-promoted")
    if no_debug_roots_exhausted:
        blockers.append("no-debug-root-lanes-exhausted")
    if "blocked-no-debugger-access-provenance" in list(safe_mapping(truth.get("staticChainStatus")).get("blockers") or []):
        blockers.append("blocked-no-debugger-access-provenance")
    if promotion_allowed:
        verdict = "promoted-static-chain-ready"
    elif static_resolver_found:
        verdict = "static-resolver-candidate-found-not-promoted"
    else:
        verdict = "candidate-only-no-debug-root-blocked"
    deduped_blockers = sorted(set(blockers))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "actor-chain-no-debug-status",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not missing_artifacts else "blocked",
        "verdict": verdict,
        "repoRoot": str(repo_root),
        "target": safe_mapping(truth.get("target")),
        "proof": {
            "status": proof_doc.get("status"),
            "candidateAddressHex": safe_mapping(proof_doc.get("riftscanCandidateSource")).get("sourceAbsoluteAddressHex"),
            "currentCoordinate": safe_mapping(proof_doc.get("latestValidation")).get("currentCoordinate"),
        },
        "actorCandidate": {
            "candidateId": best_readback.get("candidateId"),
            "addressHex": best_readback.get("addressHex"),
            "classification": best_readback.get("classification"),
            "offsetCorrectedMaxAbsDelta": best_readback.get("offsetCorrectedMaxAbsDelta"),
            "truthReadiness": best_readback.get("truthReadiness"),
            "candidateOnly": True,
            "promotionEligible": False,
        },
        "ownerEvidence": {
            "topOwnerScore": root_top.get("score"),
            "ownerBase": root_top.get("ownerBase"),
            "coordPointerStorage": root_top.get("coordPointerStorage"),
            "ownerFamilyCount": family_counts.get("ownerFamilyCount"),
            "priorityParentLeadCount": family_counts.get("priorityParentLeadCount"),
        },
        "staticResolver": static_resolver,
        "noDebugRootSearch": {
            "pointerScans": scan_summaries,
            "exhaustionReports": exhaustion_summaries,
            "totalModuleHitCount": total_module_hits,
            "totalRiftModuleHitCount": total_rift_hits,
            "noDebugRootLanesExhausted": no_debug_roots_exhausted,
        },
        "promotionGates": {
            "currentProofAnchorPassed": current_proof,
            "actorCandidateReadbackPassed": candidate_passed,
            "staticResolverCandidateFound": static_resolver_found,
            "accessProvenancePresent": False,
            "staticResolverPromoted": static_resolver_promoted,
            "restartValidated": bool(static_resolver.get("restartValidated")),
            "promotionAllowed": promotion_allowed,
        },
        "blockers": deduped_blockers,
        "blockerDiagnostics": _build_blocker_diagnostics(deduped_blockers),
        "warnings": [],
        "safety": {
            "offlineArtifactOnly": True,
            "movementSent": False,
            "inputSent": False,
            "targetMemoryRead": False,
            "targetMemoryWritten": False,
            "x64dbgAttached": False,
            "breakpointsSet": False,
            "noCheatEngine": True,
            "providerWrites": False,
            "gitMutation": False,
        },
        "next": {
            "recommendedAction": (
                "Static resolver candidate exists; restore a fresh API/reference source and rerun API-now vs static-chain-now before promotion review."
                if static_resolver_found and not static_resolver_promoted
                else "Keep the actor chain candidate-only; broaden only with new static evidence, or request explicit approval for one bounded debugger access-provenance step."
            )
        },
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    truth_path = resolve_path(repo_root, str(args.truth_json))
    if truth_path is None or not truth_path.exists():
        raise FileNotFoundError(f"truth JSON not found: {args.truth_json}")
    truth = load_json_object(truth_path)
    proof_path = first_nonempty(args.proof_json, artifact_value(truth, "currentProofPointer"))
    candidate_path = first_nonempty(args.candidate_readback_json, artifact_value(truth, "currentActorCandidateReadback"))
    root_sweep_path = first_nonempty(args.root_sweep_json, artifact_value(truth, "currentActorRootSignatureSweep"))
    root_family_path = first_nonempty(args.root_family_json, artifact_value(truth, "currentActorRootFamilyClassifier"))
    inferred_pointer_paths = [
        artifact_value(truth, "currentPriorityPointerFamilyScan"),
        artifact_value(truth, "currentNonPriorityParentPointerFamilyScan"),
        artifact_value(truth, "currentOwnerCoordStoragePointerFamilyScan"),
    ]
    inferred_exhaustion_paths = [
        artifact_value(truth, "currentPriorityScanExhaustionReport"),
        artifact_value(truth, "currentNonPriorityParentScanExhaustionReport"),
    ]
    missing: list[str] = []
    proof, _, missing_proof = load_optional(repo_root, proof_path)
    candidate, _, missing_candidate = load_optional(repo_root, candidate_path)
    root_sweep, _, missing_root_sweep = load_optional(repo_root, root_sweep_path)
    root_family, _, missing_root_family = load_optional(repo_root, root_family_path)
    for item in (missing_proof, missing_candidate, missing_root_sweep, missing_root_family):
        if item:
            # Paths are reported below from their source strings.
            pass
    for source, missing_flag in ((proof_path, missing_proof), (candidate_path, missing_candidate), (root_sweep_path, missing_root_sweep), (root_family_path, missing_root_family)):
        if missing_flag and source:
            missing.append(str(resolve_path(repo_root, source)))
    pointer_scans: list[tuple[str, Mapping[str, Any]]] = []
    for raw_path in [*inferred_pointer_paths, *args.pointer_scan_json]:
        doc, resolved, missing_flag = load_optional(repo_root, raw_path)
        if missing_flag and resolved:
            missing.append(resolved)
        if doc is not None and resolved is not None:
            pointer_scans.append((resolved, doc))
    exhaustion_reports: list[tuple[str, Mapping[str, Any]]] = []
    for raw_path in [*inferred_exhaustion_paths, *args.exhaustion_json]:
        doc, resolved, missing_flag = load_optional(repo_root, raw_path)
        if missing_flag and resolved:
            missing.append(resolved)
        if doc is not None and resolved is not None:
            exhaustion_reports.append((resolved, doc))
    summary = build_summary_from_documents(
        repo_root=repo_root,
        truth=truth,
        proof=proof,
        candidate_readback=candidate,
        root_sweep=root_sweep,
        root_family=root_family,
        pointer_scans=pointer_scans,
        exhaustion_reports=exhaustion_reports,
        missing_artifacts=missing,
    )
    summary["inputs"] = {
        "truthJson": str(truth_path),
        "proofJson": str(resolve_path(repo_root, proof_path)) if proof_path else None,
        "candidateReadbackJson": str(resolve_path(repo_root, candidate_path)) if candidate_path else None,
        "rootSweepJson": str(resolve_path(repo_root, root_sweep_path)) if root_sweep_path else None,
        "rootFamilyJson": str(resolve_path(repo_root, root_family_path)) if root_family_path else None,
    }
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    candidate = safe_mapping(summary.get("actorCandidate"))
    gates = safe_mapping(summary.get("promotionGates"))
    static_resolver = safe_mapping(summary.get("staticResolver"))
    root = safe_mapping(summary.get("noDebugRootSearch"))
    lines = [
        "# Actor-chain no-debug status",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Candidate: `{candidate.get('candidateId')}` / `{candidate.get('addressHex')}`",
        f"- Candidate classification: `{candidate.get('classification')}`",
        f"- Offset-corrected max abs delta: `{candidate.get('offsetCorrectedMaxAbsDelta')}`",
        f"- Static resolver: `{static_resolver.get('chain')}`",
        f"- Static resolver status: `{static_resolver.get('status')}`",
        "",
        "## Promotion gates",
        "",
        "| Gate | Value |",
        "|---|---:|",
    ]
    for key in ("currentProofAnchorPassed", "actorCandidateReadbackPassed", "staticResolverCandidateFound", "accessProvenancePresent", "staticResolverPromoted", "restartValidated", "promotionAllowed"):
        lines.append(f"| `{key}` | `{str(gates.get(key)).lower()}` |")
    lines.extend([
        "",
        "## No-debug root search",
        "",
        f"- Total module hits: `{root.get('totalModuleHitCount')}`",
        f"- Total rift_x64 hits: `{root.get('totalRiftModuleHitCount')}`",
        f"- Exhausted: `{str(root.get('noDebugRootLanesExhausted')).lower()}`",
        "",
        "| Scan | Targets | Hits | Module hits | rift_x64 hits |",
        "|---|---:|---:|---:|---:|",
    ])
    for scan in root.get("pointerScans") or []:
        row = safe_mapping(scan)
        lines.append(f"| `{display_artifact_path(str(row.get('path') or ''))}` | `{row.get('scannedTargetCount')}` | `{row.get('totalHits')}` | `{row.get('moduleHitCount')}` | `{row.get('riftModuleHitCount')}` |")
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        for blocker in summary.get("blockers") or []:
            lines.append(f"- `{blocker}`")
    blocker_diags = [safe_mapping(item) for item in summary.get("blockerDiagnostics", []) if isinstance(item, Mapping)]
    if blocker_diags:
        lines.extend(["", "## Blocker diagnostics", ""])
        for diag in blocker_diags:
            lines.append(f"### `{diag.get('blocker')}`")
            lines.append(f"- **What this means:** {diag.get('meaning')}")
            lines.append(f"- **What to do:** {diag.get('action')}")
            lines.append("")
    next_section = safe_mapping(summary.get("next"))
    if next_section.get("recommendedAction"):
        lines.extend([
            "",
            "## Recommended next action",
            "",
            str(next_section.get("recommendedAction")),
        ])
    lines.extend([
        "",
        "## Safety",
        "",
        "Offline artifact aggregation only. This helper sends no input, reads no live process memory, attaches no debugger, sets no breakpoints, writes no target memory, and does not promote coordinate truth.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--truth-json", type=Path, default=Path("docs/recovery/current-truth.json"))
    parser.add_argument("--proof-json")
    parser.add_argument("--candidate-readback-json")
    parser.add_argument("--root-sweep-json")
    parser.add_argument("--root-family-json")
    parser.add_argument("--pointer-scan-json", action="append", default=[])
    parser.add_argument("--exhaustion-json", action="append", default=[])
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        result = build_self_test()
        print(json.dumps(result if args.json else result["summary"], indent=2))
        return 0 if result["status"] == "passed" else 1

    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"actor-chain-no-debug-status-{utc_stamp()}"
    output_root.mkdir(parents=True, exist_ok=True)
    summary = build_summary(args)
    artifacts = {
        "runDirectory": str(output_root),
        "summaryJson": str(output_root / "summary.json"),
        "summaryMarkdown": str(output_root / "summary.md"),
    }
    summary["artifacts"] = artifacts
    write_json(output_root / "summary.json", summary)
    write_text_atomic(output_root / "summary.md", build_markdown(summary))
    result = {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "promotionAllowed": safe_mapping(summary.get("promotionGates")).get("promotionAllowed"),
        "summaryJson": artifacts["summaryJson"],
        "summaryMarkdown": artifacts["summaryMarkdown"],
        "blockers": summary.get("blockers"),
    }
    print(json.dumps(result if args.json else summary, indent=2))
    return 0 if summary.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
