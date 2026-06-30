#!/usr/bin/env python3
"""Build a safe post-patch resolver profile packet for RiftReader.

Phase 1/2 only:
- fingerprint the local RIFT build when files are available;
- freeze/flag stale tracked truth when the build or root evidence is unverified;
- surface candidate-only resolver leads from tracked truth and recovery docs;
- write a movement-proof plan template, but do not send input or promote truth.

This helper intentionally performs no live process reads, no movement, no
debugger attach, no provider writes, and no Git mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, repo_rel, safety_flags, timestamped_output_dir, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel, safety_flags, timestamped_output_dir, utc_iso


DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "postpatch-profile"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_RECOVERY_PLAN_MD = Path("docs") / "recovery" / "post-update-pointer-chain-recovery-plan-2026-06-02.md"
DEFAULT_MANIFEST_PATH = Path(r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\manifest64.txt")
DEFAULT_BINARY_PATH = Path(r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe")

ROOT_NULL_RE = re.compile(r"\[rift_x64\+0x(?P<rva>[0-9A-Fa-f]+)\]\s*==\s*0x0")
CHAIN_RE = re.compile(r"`(?P<chain>[^`]*rift_x64\+0x[0-9A-Fa-f]+[^`]*)`")
ROOT_RVA_RE = re.compile(r"rift_x64\+0x(?P<rva>[0-9A-Fa-f]+)")
STABLE_VERSION_RE = re.compile(r"STABLE-[0-9A-Za-z._-]+")


def read_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:  # noqa: BLE001
        return None, f"read-failed:{type(exc).__name__}:{exc}"
    try:
        value = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        return None, f"json-parse-failed:{type(exc).__name__}:{exc}"
    if not isinstance(value, dict):
        return None, "not-json-object"
    return value, None


def read_text_file(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:  # noqa: BLE001
        return None, f"read-failed:{type(exc).__name__}:{exc}"


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest().upper()
    except Exception:  # noqa: BLE001 - fingerprint failure is reported by caller metadata.
        return None


def file_fingerprint(path: Path, *, text_preview: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "sha256": None,
        "sizeBytes": None,
        "lastWriteTimeUtc": None,
    }
    if not path.is_file():
        return result

    try:
        stat = path.stat()
        result["sizeBytes"] = stat.st_size
        result["lastWriteTimeUtc"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
    except Exception as exc:  # noqa: BLE001
        result["statError"] = f"{type(exc).__name__}:{exc}"

    result["sha256"] = sha256_file(path)

    if text_preview:
        text, error = read_text_file(path)
        if text is None:
            result["textReadError"] = error
        else:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            result["firstNonEmptyLines"] = lines[:12]
            versions = STABLE_VERSION_RE.findall(text)
            result["stableManifestVersions"] = sorted(set(versions))
            result["primaryStableManifestVersion"] = versions[0] if versions else None

    return result


def build_fingerprint(manifest_path: Path, binary_path: Path) -> dict[str, Any]:
    manifest = file_fingerprint(manifest_path, text_preview=True)
    binary = file_fingerprint(binary_path, text_preview=False)
    if manifest["exists"] and binary["exists"]:
        status = "local-build-fingerprinted"
    elif manifest["exists"] or binary["exists"]:
        status = "partial-local-build-fingerprint"
    else:
        status = "local-build-files-not-found"
    return {
        "status": status,
        "generatedAtUtc": utc_iso(),
        "manifest": manifest,
        "binary": binary,
    }


def extract_root_null_evidence(recovery_text: str | None) -> list[dict[str, Any]]:
    if not recovery_text:
        return []
    evidence: list[dict[str, Any]] = []
    for match in ROOT_NULL_RE.finditer(recovery_text):
        rva = "0x" + match.group("rva").upper()
        evidence.append(
            {
                "rootRva": rva,
                "expression": match.group(0),
                "classification": "root-pointer-null",
            }
        )
    return evidence


def classify_chain(chain: str) -> dict[str, Any]:
    root_match = ROOT_RVA_RE.search(chain)
    root_rva = "0x" + root_match.group("rva").upper() if root_match else None
    normalized = chain.strip()
    lower = normalized.lower()
    coordinate_like = (
        "+0x320" in lower and "+0x324" in lower and "+0x328" in lower
    ) or (
        "+0x28" in lower and "+0x2c" in lower and "+0x30" in lower
    )
    orientation_like = any(token in lower for token in ["0x335f508", "orientation", "matrix", "+0x30c"])
    if coordinate_like:
        role = "coordinate"
    elif orientation_like:
        role = "orientation-or-facing"
    else:
        role = "unknown"
    return {
        "chain": normalized,
        "rootRva": root_rva,
        "role": role,
        "candidateOnly": True,
        "promotionAllowed": False,
    }


def extract_recovery_candidates(recovery_text: str | None, source_path: Path, repo_root: Path) -> list[dict[str, Any]]:
    if not recovery_text:
        return []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in CHAIN_RE.finditer(recovery_text):
        chain = match.group("chain").strip()
        if chain in seen:
            continue
        seen.add(chain)
        if "== 0x0" in chain or "root-pointer-null" in chain:
            continue
        if "rift_x64+" not in chain:
            continue
        candidate = classify_chain(chain)
        candidate["source"] = repo_rel(repo_root, source_path)
        candidate["sourceKind"] = "recovery-doc"
        if candidate["role"] == "coordinate" or candidate.get("rootRva"):
            candidates.append(candidate)
    return candidates


def current_truth_candidate(current_truth: dict[str, Any] | None) -> dict[str, Any] | None:
    if not current_truth:
        return None

    best = current_truth.get("bestCurrentCandidate")
    if isinstance(best, dict):
        return {
            "sourceKind": "tracked-current-truth",
            "candidateId": best.get("candidateId"),
            "classification": best.get("classification"),
            "chain": best.get("chain"),
            "rootRva": best.get("rootRva"),
            "role": "coordinate",
            "candidateOnly": False,
            "promotionAllowed": bool(best.get("promotionEligible") or best.get("promotionAllowed")),
            "status": best.get("status"),
            "latestCurrentReadbackAtUtc": best.get("latestCurrentReadbackAtUtc"),
            "restartRelogSurvived": best.get("reacquiredAfterReboot"),
        }

    static_status = current_truth.get("staticChainStatus")
    primary = static_status.get("primaryCandidate") if isinstance(static_status, dict) else None
    if isinstance(primary, dict):
        return {
            "sourceKind": "tracked-current-truth",
            "chain": primary.get("chain"),
            "rootRva": primary.get("rootRva"),
            "role": "coordinate",
            "candidateOnly": False,
            "promotionAllowed": bool(static_status.get("promotionAllowed")),
            "status": static_status.get("status"),
            "restartRelogSurvived": primary.get("restartRelogSurvived"),
        }
    return None


def summarize_current_truth(current_truth: dict[str, Any] | None, read_error: str | None) -> dict[str, Any]:
    if current_truth is None:
        return {
            "status": "missing" if read_error == "missing" else "unusable",
            "readError": read_error,
            "updatedAtUtc": None,
            "target": {},
            "bestCurrentCandidate": None,
            "movementGate": {},
        }

    target = current_truth.get("target") if isinstance(current_truth.get("target"), dict) else {}
    movement_gate = current_truth.get("movementGate") if isinstance(current_truth.get("movementGate"), dict) else {}
    return {
        "status": current_truth.get("status"),
        "updatedAtUtc": current_truth.get("updatedAtUtc"),
        "target": {
            "processName": target.get("processName"),
            "processId": target.get("processId"),
            "targetWindowHandle": target.get("targetWindowHandle"),
            "processStartUtc": target.get("processStartUtc"),
            "moduleBase": target.get("moduleBase"),
            "moduleFileName": target.get("moduleFileName"),
            "lastVerifiedUtc": target.get("lastVerifiedUtc"),
        },
        "bestCurrentCandidate": current_truth_candidate(current_truth),
        "movementGate": {
            "allowed": movement_gate.get("allowed"),
            "status": movement_gate.get("status"),
            "reason": movement_gate.get("reason"),
        },
    }


def stale_truth_report(
    current_truth: dict[str, Any] | None,
    current_truth_error: str | None,
    build: dict[str, Any],
    root_null_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    truth_summary = summarize_current_truth(current_truth, current_truth_error)
    tracked_candidate = truth_summary.get("bestCurrentCandidate") or {}
    tracked_root = tracked_candidate.get("rootRva")

    if truth_summary["status"] in {"missing", "unusable"}:
        blockers.append(f"tracked-current-truth-{truth_summary['status']}")
    if build["status"] != "local-build-fingerprinted":
        warnings.append(f"build-fingerprint-{build['status']}")
    if tracked_root:
        for evidence in root_null_evidence:
            if str(evidence.get("rootRva")).lower() == str(tracked_root).lower():
                blockers.append(f"tracked-root-has-postupdate-null-evidence:{tracked_root}")
    if tracked_candidate and tracked_candidate.get("candidateOnly") is False:
        warnings.append("tracked-current-truth-is-promoted-snapshot-reverify-before-consumers")
    if truth_summary.get("movementGate", {}).get("allowed") is True:
        warnings.append("movement-gate-was-allowed-in-tracked-truth-but-postpatch-profile-does-not-enable-consumers")

    if blockers:
        status = "blocked-safe"
    elif warnings:
        status = "review-required"
    else:
        status = "no-stale-truth-evidence-detected"

    return {
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "currentTruth": truth_summary,
        "rootNullEvidence": root_null_evidence,
        "consumerPolicy": {
            "navigationConsumersBlocked": True,
            "reason": "Phase 1/2 post-patch profile packets never enable route/navigation consumers; proof/promotion is a later explicit gate.",
        },
    }


def choose_best_candidate(
    tracked: dict[str, Any] | None,
    recovery_candidates: list[dict[str, Any]],
    root_null_evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    null_roots = {str(item.get("rootRva")).lower() for item in root_null_evidence}
    coordinate_candidates = [c for c in recovery_candidates if c.get("role") == "coordinate"]
    non_null_coordinates = [
        c for c in coordinate_candidates if str(c.get("rootRva")).lower() not in null_roots
    ]
    if non_null_coordinates:
        # Prefer a container-like candidate from the post-update recovery document over stale tracked truth.
        for candidate in non_null_coordinates:
            if "32dd7e8" in str(candidate.get("chain", "")).lower():
                return candidate
        return non_null_coordinates[0]
    if tracked and str(tracked.get("rootRva")).lower() not in null_roots:
        return tracked
    if coordinate_candidates:
        return coordinate_candidates[0]
    return tracked


def candidate_resolver_profile(
    repo_root: Path,
    current_truth: dict[str, Any] | None,
    recovery_text: str | None,
    recovery_path: Path,
    root_null_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    tracked = current_truth_candidate(current_truth)
    recovery_candidates = extract_recovery_candidates(recovery_text, recovery_path, repo_root)
    best = choose_best_candidate(tracked, recovery_candidates, root_null_evidence)

    candidates: list[dict[str, Any]] = []
    if tracked:
        candidates.append(tracked)
    candidates.extend(recovery_candidates)

    # De-duplicate by chain while preserving tracked-first ordering.
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        chain = str(candidate.get("chain"))
        if chain in seen:
            continue
        seen.add(chain)
        deduped.append(candidate)

    return {
        "status": "candidate-profile-ready" if best else "no-candidate-found",
        "bestCandidate": best,
        "candidates": deduped,
        "promotion": {
            "allowed": False,
            "performed": False,
            "reason": "Phase 1/2 profile generation is candidate-only and cannot promote current truth.",
        },
        "requiredProofGaps": {
            "apiNowVsChainNow": "required-fresh",
            "controlledDisplacement": "required-explicit-movement-approval",
            "restartRelogSurvival": "required-before-promotion",
            "proofOnly": "required-before-current-truth-apply",
        },
    }


def movement_proof_plan_template(best_candidate: dict[str, Any] | None, current_truth_summary: dict[str, Any]) -> dict[str, Any]:
    target = current_truth_summary.get("target") if isinstance(current_truth_summary.get("target"), dict) else {}
    return {
        "status": "template-ready" if best_candidate else "blocked-no-candidate",
        "approval": {
            "explicitMovementApprovalRequired": True,
            "approvalTokenSuggested": "RIFTREADER-CONTROLLED-DISCOVERY-MOVEMENT-APPROVED",
            "consumerMovementEnabled": False,
            "currentTruthPromotionEnabled": False,
        },
        "targetBinding": {
            "required": True,
            "expectedProcessName": target.get("processName") or "rift_x64",
            "expectedPid": target.get("processId"),
            "expectedHwnd": target.get("targetWindowHandle"),
            "expectedProcessStartUtc": target.get("processStartUtc"),
            "expectedModuleBase": target.get("moduleBase"),
        },
        "candidateUnderTest": best_candidate,
        "stimulusSequence": [
            {
                "name": "baseline",
                "input": "none",
                "capture": ["addon/api coordinate", "candidate chain readback", "target identity"],
            },
            {
                "name": "forward-pulse",
                "input": "bounded forward movement pulse only after explicit approval",
                "capture": ["addon/api coordinate", "candidate chain readback", "delta chain-minus-api"],
            },
            {
                "name": "settle-pause",
                "input": "none",
                "capture": ["stationary drift", "candidate chain stability"],
            },
            {
                "name": "turn-or-second-vector",
                "input": "bounded second-vector stimulus only after explicit approval",
                "capture": ["addon/api coordinate", "candidate chain readback", "copy-buffer rejection"],
            },
            {
                "name": "final-readback",
                "input": "none",
                "capture": ["target identity", "api-vs-chain final delta", "proof gaps"],
            },
        ],
        "passCriteria": {
            "exactTargetStable": True,
            "apiVsChainMaxAbsDeltaWithinTolerance": True,
            "twoDisplacedApiPosesMinimum": True,
            "candidateTracksSamePlayerAcrossPoses": True,
            "noConsumerAutomationDuringProof": True,
            "noCurrentTruthWriteDuringProof": True,
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    stale = summary["staleTruthReport"]
    candidate_profile = summary["candidateResolverProfile"]
    best = candidate_profile.get("bestCandidate") or {}
    build = summary["buildFingerprint"]
    lines = [
        "# RiftReader Post-Patch Resolver Profile",
        "",
        f"- Generated UTC: `{summary['generatedAtUtc']}`",
        f"- Status: `{summary['status']}`",
        f"- Verdict: `{summary['verdict']}`",
        "",
        "## Build fingerprint",
        "",
        f"- Status: `{build['status']}`",
        f"- Manifest: `{build['manifest']['path']}` exists=`{build['manifest']['exists']}`",
        f"- Binary: `{build['binary']['path']}` exists=`{build['binary']['exists']}`",
        "",
        "## Stale truth freeze",
        "",
        f"- Status: `{stale['status']}`",
        f"- Blockers: `{', '.join(stale['blockers']) if stale['blockers'] else 'none'}`",
        f"- Warnings: `{', '.join(stale['warnings']) if stale['warnings'] else 'none'}`",
        "- Navigation/consumer movement remains blocked in this Phase 1/2 packet.",
        "",
        "## Best candidate",
        "",
    ]
    if best:
        lines.extend(
            [
                f"- Chain: `{best.get('chain')}`",
                f"- Root RVA: `{best.get('rootRva')}`",
                f"- Role: `{best.get('role')}`",
                f"- Candidate-only: `{best.get('candidateOnly')}`",
                f"- Promotion allowed: `{best.get('promotionAllowed')}`",
            ]
        )
    else:
        lines.append("- No candidate found.")
    lines.extend(
        [
            "",
            "## Movement proof plan",
            "",
            "- Controlled discovery movement is treated as required proof stimulus, not consumer automation.",
            "- Explicit movement approval is required before any movement pulse.",
            "- This packet never promotes current truth and never enables route/navigation consumers.",
            "",
            "## Safety",
            "",
            "```json",
            json.dumps(summary["safety"], indent=2, sort_keys=True),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def write_artifacts(repo_root: Path, summary: dict[str, Any], output_base: Path) -> dict[str, str]:
    run_dir = timestamped_output_dir(repo_root / output_base)
    artifacts = {
        "summaryJson": run_dir / "summary.json",
        "summaryMarkdown": run_dir / "summary.md",
        "buildFingerprintJson": run_dir / "build-fingerprint.json",
        "staleTruthReportJson": run_dir / "stale-truth-report.json",
        "candidateResolverProfileJson": run_dir / "candidate-resolver-profile.json",
        "movementProofPlanTemplateJson": run_dir / "movement-proof-plan-template.json",
    }
    artifacts["summaryJson"].write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    artifacts["summaryMarkdown"].write_text(render_markdown(summary), encoding="utf-8")
    artifacts["buildFingerprintJson"].write_text(
        json.dumps(summary["buildFingerprint"], indent=2, sort_keys=True), encoding="utf-8"
    )
    artifacts["staleTruthReportJson"].write_text(
        json.dumps(summary["staleTruthReport"], indent=2, sort_keys=True), encoding="utf-8"
    )
    artifacts["candidateResolverProfileJson"].write_text(
        json.dumps(summary["candidateResolverProfile"], indent=2, sort_keys=True), encoding="utf-8"
    )
    artifacts["movementProofPlanTemplateJson"].write_text(
        json.dumps(summary["movementProofPlanTemplate"], indent=2, sort_keys=True), encoding="utf-8"
    )
    latest = repo_root / output_base / "latest-run.txt"
    latest.write_text(repo_rel(repo_root, run_dir) or str(run_dir), encoding="utf-8")
    return {key: repo_rel(repo_root, value) or str(value) for key, value in artifacts.items()}


def build_postpatch_profile(
    repo_root: Path,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    binary_path: Path = DEFAULT_BINARY_PATH,
    current_truth_path: Path | None = None,
    recovery_plan_path: Path | None = None,
) -> dict[str, Any]:
    current_truth_path = current_truth_path or repo_root / DEFAULT_CURRENT_TRUTH_JSON
    recovery_plan_path = recovery_plan_path or repo_root / DEFAULT_RECOVERY_PLAN_MD

    current_truth, current_truth_error = read_json_file(current_truth_path)
    recovery_text, recovery_error = read_text_file(recovery_plan_path)

    build = build_fingerprint(manifest_path, binary_path)
    root_null = extract_root_null_evidence(recovery_text)
    stale = stale_truth_report(current_truth, current_truth_error, build, root_null)
    candidate_profile = candidate_resolver_profile(
        repo_root,
        current_truth,
        recovery_text,
        recovery_plan_path,
        root_null,
    )
    movement_plan = movement_proof_plan_template(
        candidate_profile.get("bestCandidate"),
        stale.get("currentTruth", {}),
    )

    blockers = list(stale.get("blockers") or [])
    warnings = list(stale.get("warnings") or [])
    if recovery_error and recovery_error != "missing":
        warnings.append(f"recovery-plan-read-warning:{recovery_error}")
    if candidate_profile["status"] == "no-candidate-found":
        blockers.append("no-coordinate-resolver-candidate-found")

    if blockers:
        status = "blocked-safe"
        verdict = "postpatch-profile-blocked-safe"
    else:
        status = "passed"
        verdict = "postpatch-phase1-phase2-profile-ready"

    return {
        "schemaVersion": 1,
        "kind": "riftreader-postpatch-resolver-profile",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "phaseScope": {
            "phase1BuildFingerprintAndStaleTruthFreeze": True,
            "phase2CandidateReacquireProfile": True,
            "movementProofPlanTemplateOnly": True,
            "promotion": False,
        },
        "repoRoot": str(repo_root),
        "inputs": {
            "manifestPath": str(manifest_path),
            "binaryPath": str(binary_path),
            "currentTruthJson": repo_rel(repo_root, current_truth_path),
            "recoveryPlanMarkdown": repo_rel(repo_root, recovery_plan_path),
            "currentTruthReadError": current_truth_error,
            "recoveryPlanReadError": recovery_error,
        },
        "buildFingerprint": build,
        "staleTruthReport": stale,
        "candidateResolverProfile": candidate_profile,
        "movementProofPlanTemplate": movement_plan,
        "blockers": blockers,
        "warnings": warnings,
        "errors": [],
        "safety": {
            **safety_flags(),
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "currentTruthWrite": False,
            "proofPromotion": False,
            "consumerMovementEnabled": False,
            "movementProofPlanOnly": True,
            "writeScopeIgnoredLocalArtifactsOnly": False,
        },
        "next": {
            "safeNextAction": "Review candidate-resolver-profile.json and stale-truth-report.json; do not enable consumers.",
            "gatedNextAction": "Run controlled displacement proof only after explicit movement approval and exact-target preflight.",
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a safe Phase 1/2 post-patch resolver profile packet.")
    parser.add_argument("--json", action="store_true", help="Print summary JSON.")
    parser.add_argument("--write", action="store_true", help="Write ignored .riftreader-local artifacts.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--binary-path", type=Path, default=DEFAULT_BINARY_PATH)
    parser.add_argument("--current-truth-json", type=Path)
    parser.add_argument("--recovery-plan-md", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = find_repo_root(Path(__file__))

    summary = build_postpatch_profile(
        repo_root,
        manifest_path=args.manifest_path,
        binary_path=args.binary_path,
        current_truth_path=args.current_truth_json,
        recovery_plan_path=args.recovery_plan_md,
    )

    if args.write:
        artifacts = write_artifacts(repo_root, summary, args.output_dir)
        summary["artifacts"] = artifacts
        summary["safety"]["writeScopeIgnoredLocalArtifactsOnly"] = True

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render_markdown(summary), end="")

    return 0 if summary["status"] in {"passed", "blocked-safe"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
