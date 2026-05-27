from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_MAX_SAMPLE_AGE_SECONDS = 300.0
DEFAULT_TOLERANCE = 0.25


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def safe_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def resolve_path(repo_root: Path, value: Any) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    return path if path.is_absolute() else repo_root / path


def normalize_hwnd(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return f"0x{int(str(value), 0):X}"
    except (TypeError, ValueError):
        return str(value)


def normalize_process_name(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).lower().removesuffix(".exe")


def same_text(left: Any, right: Any) -> bool:
    if left in (None, "") or right in (None, ""):
        return True
    return str(left).lower() == str(right).lower()


def truncate_fractional_seconds(text: str) -> str:
    return re.sub(r"\.(\d{6})\d+([+-]\d\d:\d\d|Z)?$", r".\1\2", text)


def parse_iso(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = truncate_fractional_seconds(str(value).strip())
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def age_seconds(value: Any, *, now: datetime) -> float | None:
    parsed = parse_iso(value)
    if parsed is None:
        return None
    return (now - parsed).total_seconds()


def first_nonempty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def numeric_coordinate(value: Mapping[str, Any]) -> dict[str, float] | None:
    try:
        return {axis: float(value[axis]) for axis in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError):
        return None


def coordinate_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, float] | None:
    left_coord = numeric_coordinate(left)
    right_coord = numeric_coordinate(right)
    if left_coord is None or right_coord is None:
        return None
    return {axis: left_coord[axis] - right_coord[axis] for axis in ("x", "y", "z")}


def target_mismatches(current: Mapping[str, Any], review: Mapping[str, Any]) -> list[str]:
    mismatches: list[str] = []
    current_pid = first_nonempty(current.get("processId"), current.get("pid"))
    review_pid = first_nonempty(review.get("processId"), review.get("pid"))
    if current_pid is not None and review_pid is not None and int(current_pid) != int(review_pid):
        mismatches.append(f"processId:{current_pid}!={review_pid}")
    current_hwnd = normalize_hwnd(first_nonempty(current.get("targetWindowHandle"), current.get("hwnd")))
    review_hwnd = normalize_hwnd(first_nonempty(review.get("targetWindowHandle"), review.get("hwnd")))
    if current_hwnd and review_hwnd and current_hwnd != review_hwnd:
        mismatches.append(f"targetWindowHandle:{current_hwnd}!={review_hwnd}")
    current_process = normalize_process_name(current.get("processName"))
    review_process = normalize_process_name(review.get("processName"))
    if current_process and review_process and current_process != review_process:
        mismatches.append(f"processName:{current_process}!={review_process}")
    for field in ("processStartUtc", "moduleBase"):
        if not same_text(current.get(field), review.get(field)):
            mismatches.append(f"{field}:{current.get(field)}!={review.get(field)}")
    return mismatches


def summarize_static_resolver(truth: Mapping[str, Any]) -> dict[str, Any]:
    static_status = safe_mapping(truth.get("staticChainStatus"))
    best = safe_mapping(truth.get("bestCurrentCandidate"))
    primary = safe_mapping(static_status.get("primaryCandidate"))
    chain = first_nonempty(primary.get("chain"), best.get("chain"))
    root_rva = first_nonempty(primary.get("rootRva"), best.get("rootRva"))
    root_address = first_nonempty(primary.get("rootAddress"), best.get("rootAddress"))
    owner_address = first_nonempty(primary.get("ownerAddress"), best.get("currentOwnerAddress"))
    coordinate_address = first_nonempty(primary.get("coordinateAddress"), best.get("currentCoordinateAddress"))
    complete = bool(chain and root_rva and root_address and owner_address and coordinate_address)
    return {
        "status": static_status.get("status"),
        "complete": complete,
        "promotionAllowed": bool(static_status.get("promotionAllowed")),
        "chain": chain,
        "rootModule": first_nonempty(primary.get("rootModule"), best.get("rootModule")),
        "rootRva": root_rva,
        "rootAddress": root_address,
        "ownerAddress": owner_address,
        "coordinateAddress": coordinate_address,
        "restartRelogSurvived": bool(primary.get("restartRelogSurvived") or best.get("reacquiredAfterReboot")),
        "latestApiNowValidationStatus": safe_mapping(static_status.get("latestApiNowValidation")).get("status"),
        "latestFreshApiSourceRefreshAttempt": safe_mapping(static_status.get("latestFreshApiSourceRefreshAttempt")),
        "doesNotPromote": True,
    }


def summarize_latest_refresh_attempt(static_resolver: Mapping[str, Any]) -> dict[str, Any]:
    attempt = safe_mapping(static_resolver.get("latestFreshApiSourceRefreshAttempt"))
    return {
        "status": attempt.get("status"),
        "rrapicoordBlockers": safe_list(attempt.get("rrapicoordBlockers")),
        "chromalinkBlockers": safe_list(attempt.get("chromalinkBlockers")),
        "rrapicoordDiagnostics": attempt.get("rrapicoordDiagnostics"),
        "chromalinkWorldStateReference": attempt.get("chromalinkWorldStateReference"),
        "doesNotPromote": bool(attempt.get("doesNotPromote")),
    }


def summarize_final_sample(
    promotion_review: Mapping[str, Any],
    *,
    now: datetime,
    max_sample_age_seconds: float,
    default_tolerance: float,
) -> dict[str, Any]:
    final_sample = safe_mapping(promotion_review.get("finalFreshSample"))
    api_now = safe_mapping(final_sample.get("apiNow"))
    chain_now = safe_mapping(final_sample.get("chainNow"))
    comparison = safe_mapping(final_sample.get("comparison"))
    api_age = age_seconds(api_now.get("capturedAtUtc"), now=now)
    chain_age = age_seconds(chain_now.get("capturedAtUtc"), now=now)
    api_coord = numeric_coordinate(safe_mapping(api_now.get("coordinate")))
    chain_coord = numeric_coordinate(safe_mapping(chain_now.get("coordinate")))
    computed_delta = coordinate_delta(safe_mapping(chain_now.get("coordinate")), safe_mapping(api_now.get("coordinate")))
    computed_abs = {axis: abs(value) for axis, value in computed_delta.items()} if computed_delta else None
    computed_max = max(computed_abs.values()) if computed_abs else None
    reported_max = comparison.get("maxAbsDelta")
    try:
        max_abs_delta = float(reported_max) if reported_max is not None else computed_max
    except (TypeError, ValueError):
        max_abs_delta = computed_max
    try:
        tolerance = float(comparison.get("tolerance", default_tolerance))
    except (TypeError, ValueError):
        tolerance = default_tolerance
    blockers: list[str] = []
    warnings: list[str] = []
    if api_age is None:
        blockers.append("api-now-sample-missing-captured-at")
    elif api_age < -5:
        blockers.append(f"api-now-sample-clock-skew:{api_age:.3f}")
    elif api_age > max_sample_age_seconds:
        blockers.append(f"api-now-sample-too-old:{api_age:.3f}>{max_sample_age_seconds:.3f}")
    if chain_age is None:
        blockers.append("chain-now-sample-missing-captured-at")
    elif chain_age < -5:
        blockers.append(f"chain-now-sample-clock-skew:{chain_age:.3f}")
    elif chain_age > max_sample_age_seconds:
        blockers.append(f"chain-now-sample-too-old:{chain_age:.3f}>{max_sample_age_seconds:.3f}")
    if api_coord is None:
        blockers.append("api-now-coordinate-missing")
    if chain_coord is None:
        blockers.append("chain-now-coordinate-missing")
    if api_now.get("movementSent") is not False:
        blockers.append("api-now-movement-sent-not-false")
    if chain_now.get("movementSent") is not False:
        blockers.append("chain-now-movement-sent-not-false")
    if api_now.get("noCheatEngine") is not True:
        blockers.append("api-now-no-cheat-engine-not-true")
    if chain_now.get("noCheatEngine") is not True:
        blockers.append("chain-now-no-cheat-engine-not-true")
    if str(api_now.get("savedVariablesUse") or "none").lower() != "none":
        blockers.append(f"api-now-savedvariables-use:{api_now.get('savedVariablesUse')}")
    if max_abs_delta is None:
        blockers.append("api-chain-max-delta-missing")
    elif max_abs_delta > tolerance:
        blockers.append(f"api-chain-max-delta-too-large:{max_abs_delta:.6f}>{tolerance:.6f}")
    if comparison.get("withinTolerance") is False:
        blockers.append("api-chain-comparison-reported-out-of-tolerance")
    if reported_max is not None and computed_max is not None and abs(float(reported_max) - computed_max) > 0.0001:
        warnings.append("api-chain-reported-delta-differs-from-recomputed-delta")
    return {
        "apiNow": {
            "status": api_now.get("status"),
            "source": api_now.get("source"),
            "capturedAtUtc": api_now.get("capturedAtUtc"),
            "ageSeconds": api_age,
            "coordinate": api_coord,
            "referenceFile": api_now.get("referenceFile"),
            "scanFile": api_now.get("scanFile"),
        },
        "chainNow": {
            "status": chain_now.get("status"),
            "capturedAtUtc": chain_now.get("capturedAtUtc"),
            "ageSeconds": chain_age,
            "coordinate": chain_coord,
            "summaryJson": chain_now.get("summaryJson"),
        },
        "comparison": {
            "deltasChainMinusApi": computed_delta or safe_mapping(comparison.get("deltasChainMinusApi")),
            "absDeltas": computed_abs or safe_mapping(comparison.get("absDeltas")),
            "maxAbsDelta": max_abs_delta,
            "tolerance": tolerance,
            "withinTolerance": bool(max_abs_delta is not None and max_abs_delta <= tolerance and comparison.get("withinTolerance") is not False),
        },
        "maxSampleAgeSeconds": max_sample_age_seconds,
        "blockers": blockers,
        "warnings": warnings,
    }


def summarize_stale_proof_pointer(
    *,
    repo_root: Path,
    truth: Mapping[str, Any],
    proof: Mapping[str, Any] | None,
    proof_path: Path | None,
) -> dict[str, Any]:
    proof_doc = safe_mapping(proof)
    proof_target = safe_mapping(proof_doc.get("target"))
    mismatches = target_mismatches(safe_mapping(truth.get("target")), proof_target)
    return {
        "path": str(proof_path) if proof_path else None,
        "status": proof_doc.get("status"),
        "usedForReadiness": False,
        "target": proof_target,
        "targetMismatches": mismatches,
        "warning": "stale-proof-pointer-ignored" if mismatches else None,
        "policy": "The old proof pointer is historical only; static-chain promotion readiness uses current static resolver plus fresh API-now vs chain-now evidence.",
    }


def classify_verdict(blockers: Sequence[str], *, approval_required: bool) -> str:
    if any(blocker.startswith("target-mismatch:") for blocker in blockers):
        return "blocked-target-mismatch"
    if "static-resolver-incomplete" in blockers:
        return "blocked-static-resolver-incomplete"
    if "latest-fresh-api-source-refresh-blocked" in blockers:
        return "blocked-fresh-api-reference-unavailable"
    if any("too-old" in blocker or "clock-skew" in blocker for blocker in blockers):
        return "blocked-fresh-api-sample-stale"
    if any(blocker.startswith("api-chain-") for blocker in blockers):
        return "blocked-api-chain-comparison"
    if approval_required and blockers == ["explicit-promotion-approval-required"]:
        return "ready-for-explicit-promotion-approval"
    if not blockers:
        return "static-chain-promotion-gates-passed"
    return "blocked-static-chain-promotion-readiness"


def build_summary_from_documents(
    *,
    repo_root: Path,
    truth: Mapping[str, Any],
    promotion_review: Mapping[str, Any] | None,
    promotion_review_path: Path | None = None,
    proof: Mapping[str, Any] | None = None,
    proof_path: Path | None = None,
    max_sample_age_seconds: float = DEFAULT_MAX_SAMPLE_AGE_SECONDS,
    tolerance: float = DEFAULT_TOLERANCE,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    static_resolver = summarize_static_resolver(truth)
    latest_refresh = summarize_latest_refresh_attempt(static_resolver)
    target = safe_mapping(truth.get("target"))
    review = safe_mapping(promotion_review)
    final_sample = summarize_final_sample(review, now=now, max_sample_age_seconds=max_sample_age_seconds, default_tolerance=tolerance)
    review_target = safe_mapping(review.get("target"))
    blockers: list[str] = []
    warnings: list[str] = []
    if not static_resolver.get("complete"):
        blockers.append("static-resolver-incomplete")
    if not static_resolver.get("restartRelogSurvived"):
        blockers.append("static-resolver-restart-relog-not-validated")
    if not promotion_review:
        blockers.append("promotion-review-missing")
    mismatches = target_mismatches(target, review_target)
    blockers.extend(f"target-mismatch:{item}" for item in mismatches)
    if static_resolver.get("chain") and review.get("candidate"):
        candidate = safe_mapping(review.get("candidate"))
        if not same_text(static_resolver.get("chain"), candidate.get("expression")):
            blockers.append("candidate-chain-mismatch")
        if not same_text(static_resolver.get("rootRva"), candidate.get("rootRva")):
            blockers.append("candidate-root-rva-mismatch")
    if latest_refresh.get("status") == "blocked":
        blockers.append("latest-fresh-api-source-refresh-blocked")
        blockers.extend(f"rrapicoord:{item}" for item in safe_list(latest_refresh.get("rrapicoordBlockers")))
        blockers.extend(f"chromalink:{item}" for item in safe_list(latest_refresh.get("chromalinkBlockers")))
    blockers.extend(final_sample["blockers"])
    warnings.extend(final_sample["warnings"])
    stale_proof = summarize_stale_proof_pointer(repo_root=repo_root, truth=truth, proof=proof, proof_path=proof_path)
    if stale_proof.get("warning"):
        warnings.append(str(stale_proof["warning"]))
    approval_required = not bool(static_resolver.get("promotionAllowed")) and not [item for item in blockers if item != "explicit-promotion-approval-required"]
    if approval_required:
        blockers.append("explicit-promotion-approval-required")
    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    verdict = classify_verdict(blockers, approval_required=approval_required)
    blocking_without_approval = [item for item in blockers if item != "explicit-promotion-approval-required"]
    status = "passed" if not blockers else "blocked"
    if verdict == "ready-for-explicit-promotion-approval":
        status = "blocked"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-chain-promotion-readiness",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(repo_root),
        "target": target,
        "staticResolver": static_resolver,
        "promotionReview": {
            "path": str(promotion_review_path) if promotion_review_path else None,
            "status": review.get("status"),
            "verdict": review.get("verdict"),
            "promotionPlanApproved": safe_mapping(review.get("promotionPlan")).get("approved"),
            "promotionPlanApplied": safe_mapping(review.get("promotionPlan")).get("applied"),
        },
        "freshnessGate": {
            "latestFreshApiSourceRefreshAttempt": latest_refresh,
            "finalFreshSample": final_sample,
            "currentEnoughForPromotionReview": not blocking_without_approval,
            "maxSampleAgeSeconds": max_sample_age_seconds,
        },
        "staleProofPointer": stale_proof,
        "promotionGates": {
            "staticResolverComplete": bool(static_resolver.get("complete")),
            "restartRelogSurvived": bool(static_resolver.get("restartRelogSurvived")),
            "freshApiNowVsChainNowCurrent": not bool(final_sample["blockers"]) and latest_refresh.get("status") != "blocked",
            "staleProofPointerUsed": False,
            "promotionAllowed": bool(static_resolver.get("promotionAllowed")),
            "explicitApprovalRequired": "explicit-promotion-approval-required" in blockers,
            "doesNotPromote": True,
        },
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "offlineArtifactOnly": True,
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "targetMemoryReadByThisHelper": False,
            "targetMemoryWritten": False,
            "x64dbgAttached": False,
            "breakpointsSet": False,
            "cheatEngineUsed": False,
            "noCheatEngine": True,
            "providerWrites": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "gitMutation": False,
        },
        "next": {
            "recommendedAction": (
                "Ask for explicit promotion approval, then apply the resolver promotion gate."
                if verdict == "ready-for-explicit-promotion-approval"
                else "Restore a fresh RRAPICOORD or ChromaLink reference, rerun API-now vs static-chain-now, and re-run this readiness gate before any promotion."
                if status == "blocked"
                else "Static-chain promotion gates are passed; keep movement gated until the promoted resolver is written and validated."
            )
        },
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    resolver = safe_mapping(summary.get("staticResolver"))
    gates = safe_mapping(summary.get("promotionGates"))
    freshness = safe_mapping(summary.get("freshnessGate"))
    final_sample = safe_mapping(freshness.get("finalFreshSample"))
    comparison = safe_mapping(final_sample.get("comparison"))
    stale_proof = safe_mapping(summary.get("staleProofPointer"))
    lines = [
        "# Static chain promotion readiness",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Chain: `{resolver.get('chain')}`",
        f"- Static root: `{resolver.get('rootModule')}+{resolver.get('rootRva')}`",
        f"- Owner: `{resolver.get('ownerAddress')}`",
        f"- Coordinate field: `{resolver.get('coordinateAddress')}`",
        "",
        "## Promotion gates",
        "",
        "| Gate | Value |",
        "|---|---:|",
    ]
    for key in (
        "staticResolverComplete",
        "restartRelogSurvived",
        "freshApiNowVsChainNowCurrent",
        "staleProofPointerUsed",
        "promotionAllowed",
        "explicitApprovalRequired",
        "doesNotPromote",
    ):
        lines.append(f"| `{key}` | `{str(gates.get(key)).lower()}` |")
    lines.extend(
        [
            "",
            "## Fresh API-now vs chain-now sample",
            "",
            f"- API age seconds: `{safe_mapping(final_sample.get('apiNow')).get('ageSeconds')}`",
            f"- Chain age seconds: `{safe_mapping(final_sample.get('chainNow')).get('ageSeconds')}`",
            f"- Max abs delta: `{comparison.get('maxAbsDelta')}`",
            f"- Tolerance: `{comparison.get('tolerance')}`",
            f"- Within tolerance: `{str(comparison.get('withinTolerance')).lower()}`",
            "",
            "## Stale proof pointer policy",
            "",
            f"- Used for readiness: `{str(stale_proof.get('usedForReadiness')).lower()}`",
            f"- Target mismatches: `{stale_proof.get('targetMismatches')}`",
        ]
    )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in safe_list(summary.get("warnings")))
    next_section = safe_mapping(summary.get("next"))
    if next_section.get("recommendedAction"):
        lines.extend(["", "## Recommended next action", "", str(next_section.get("recommendedAction"))])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This readiness helper is offline artifact analysis only. It does not send input, read target memory, attach a debugger, use Cheat Engine, write provider repos, or promote the chain.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def default_promotion_review_path(repo_root: Path, truth: Mapping[str, Any]) -> Path | None:
    static_status = safe_mapping(truth.get("staticChainStatus"))
    best = safe_mapping(truth.get("bestCurrentCandidate"))
    canonical = safe_mapping(truth.get("canonicalArtifacts"))
    return resolve_path(
        repo_root,
        first_nonempty(
            safe_mapping(static_status.get("promotionReview")).get("reviewJson"),
            best.get("promotionReviewArtifact"),
            canonical.get("staticOwnerChainPromotionReviewReportJson"),
        ),
    )


def default_proof_path(repo_root: Path, truth: Mapping[str, Any]) -> Path | None:
    return resolve_path(repo_root, safe_mapping(truth.get("canonicalArtifacts")).get("currentProofPointer"))


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    truth_path = resolve_path(repo_root, args.truth_json)
    if truth_path is None or not truth_path.exists():
        raise FileNotFoundError(f"current truth JSON not found: {args.truth_json}")
    truth = load_json_object(truth_path)
    review_path = resolve_path(repo_root, args.promotion_review_json) if args.promotion_review_json else default_promotion_review_path(repo_root, truth)
    promotion_review = load_json_object(review_path) if review_path and review_path.exists() else None
    proof_path = resolve_path(repo_root, args.proof_json) if args.proof_json else default_proof_path(repo_root, truth)
    proof = load_json_object(proof_path) if proof_path and proof_path.exists() else None
    output_root = (args.output_root or repo_root / "scripts" / "captures" / f"static-chain-promotion-readiness-{utc_stamp()}").resolve()
    summary = build_summary_from_documents(
        repo_root=repo_root,
        truth=truth,
        promotion_review=promotion_review,
        promotion_review_path=review_path,
        proof=proof,
        proof_path=proof_path,
        max_sample_age_seconds=args.max_sample_age_seconds,
        tolerance=args.tolerance,
    )
    artifacts = {
        "runDirectory": str(output_root),
        "summaryJson": str(output_root / "summary.json"),
        "summaryMarkdown": str(output_root / "summary.md"),
    }
    summary["artifacts"] = artifacts
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / "summary.json", summary)
    write_text_atomic(output_root / "summary.md", build_markdown(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail-closed readiness gate for the reboot-surviving static player-coordinate chain.")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--promotion-review-json")
    parser.add_argument("--proof-json")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--max-sample-age-seconds", type=float, default=DEFAULT_MAX_SAMPLE_AGE_SECONDS)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_summary(args)
    compact = {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "promotionAllowed": safe_mapping(summary.get("promotionGates")).get("promotionAllowed"),
        "summaryJson": safe_mapping(summary.get("artifacts")).get("summaryJson"),
        "summaryMarkdown": safe_mapping(summary.get("artifacts")).get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
    }
    print(json.dumps(compact if args.json else summary, indent=None if args.json else 2, separators=(",", ":") if args.json else None))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
