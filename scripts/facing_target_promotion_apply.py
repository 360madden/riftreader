#!/usr/bin/env python3
"""Apply the explicit static-owner facing/yaw promotion gate.

This helper is intentionally narrower than the report-only readiness review.
It consumes the latest readiness packet, current navigation dashboard, and
tracked current truth, then writes a durable promotion artifact only when
``--apply`` is supplied.

It never sends live input, moves the player, attaches a debugger, writes target
memory, writes provider repositories, or performs proof/actor-chain promotion.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, write_json
except ImportError:  # pragma: no cover - direct script execution path.
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, write_json  # type: ignore


SCHEMA_VERSION = 1
TOOL_VERSION = "facing-target-promotion-apply-v0.1.0"
REQUIRED_CHAIN = "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314"
REQUIRED_OFFSET = "0x30C"
DEFAULT_DASHBOARD_JSON = Path(".riftreader-local") / "navigation-pointer-discovery" / "latest" / "summary.json"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "facing-target-promotion-apply" / "latest"
DEFAULT_PROMOTION_JSON = Path("docs") / "recovery" / "static-owner-facing-yaw-promoted-2026-06-01.json"
CAPTURE_ROOT = Path("scripts") / "captures"
READINESS_PREFIX = "facing-target-promotion-readiness-review-"


class FacingPromotionApplyError(RuntimeError):
    """Raised for controlled facing promotion apply failures."""


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def repo_rel(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def newest_readiness_review(root: Path) -> Path | None:
    capture_root = root / CAPTURE_ROOT
    if not capture_root.is_dir():
        return None
    candidates: list[tuple[datetime, int, Path]] = []
    for path in capture_root.glob(f"{READINESS_PREFIX}*/summary.json"):
        if not path.is_file():
            continue
        try:
            payload = load_json_object(path)
        except Exception:
            continue
        if payload.get("kind") != "facing-target-promotion-readiness-review-packet":
            continue
        generated = parse_iso(payload.get("generatedAtUtc")) or datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        candidates.append((generated, path.stat().st_mtime_ns, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def same_target(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    for key in ("processName", "processId", "targetWindowHandle", "processStartUtc", "moduleBase"):
        if str(left.get(key)) != str(right.get(key)):
            return False
    return True


def freshness_status(dashboard: Mapping[str, Any], key: str) -> str | None:
    source = safe_mapping(safe_mapping(dashboard.get("sources")).get(key))
    return str(safe_mapping(source.get("freshness")).get("status") or "")


def build_promotion_artifact(
    *,
    root: Path,
    generated_at_utc: str,
    readiness_path: Path,
    readiness: dict[str, Any],
    dashboard_path: Path,
    dashboard: dict[str, Any],
    current_truth_path: Path,
    current_truth: dict[str, Any],
    promotion_json_path: Path,
) -> dict[str, Any]:
    candidates = safe_mapping(dashboard.get("candidates"))
    facing = safe_mapping(candidates.get("candidateFacingTarget"))
    promoted_coordinate = safe_mapping(candidates.get("promotedCoordinate"))
    proof_gates = safe_mapping(dashboard.get("proofGates"))
    current_facing = safe_mapping(current_truth.get("staticOwnerFacing"))
    primary = safe_mapping(current_facing.get("primaryCandidate"))
    review_candidate = safe_mapping(readiness.get("candidate"))
    promotion_decision = safe_mapping(readiness.get("promotionDecision"))
    target = safe_mapping(readiness.get("target"))

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-facing-yaw-promotion",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated_at_utc,
        "status": "promoted",
        "verdict": "promoted-static-owner-facing-yaw-0x30C-current-readiness-review-passed",
        "approvedByOperator": True,
        "approvalRecord": {
            "approvedAtUtc": generated_at_utc,
            "source": "Explicit current-session operator approval to complete the facing/yaw promotion gate.",
            "scope": "Promote the static owner facing-target triple at owner+0x30C/+0x310/+0x314 as the canonical yaw source alongside the promoted coordinate resolver.",
        },
        "promotionScope": {
            "promoted": "Static owner facing target at owner+0x30C/+0x310/+0x314, with yaw computed from the facing target minus owner+0x320/+0x328 coordinates.",
            "notPromoted": [
                "Turn-rate field owner+0x304.",
                "Accumulated heading/support field owner+0x300.",
                "Animation timer/support field owner+0x408.",
                "Full actor/stat chain.",
                "Proof-anchor promotion.",
                "Autonomous turn-control automation.",
            ],
        },
        "target": target,
        "facingResolver": {
            "expression": review_candidate.get("chainExpression") or primary.get("expression") or REQUIRED_CHAIN,
            "rootModule": primary.get("rootModule") or "rift_x64.exe",
            "rootRva": primary.get("rootRva") or "0x32EBC80",
            "rootAddress": primary.get("rootAddress") or promoted_coordinate.get("rootAddress"),
            "ownerAddress": facing.get("ownerAddress") or primary.get("ownerAddress"),
            "facingTargetAddress": facing.get("address") or primary.get("facingTargetAddress"),
            "facingOffsets": primary.get("facingOffsets") or ["0x30C", "0x310", "0x314"],
            "yawFormula": primary.get("yawFormula")
            or "atan2(Z_at_0x314 - playerZ_at_0x328, X_at_0x30C - playerX_at_0x320)",
            "latestYawDegrees": facing.get("latestYawDegrees") or review_candidate.get("latestYawDegrees"),
            "latestPitchDegrees": facing.get("latestPitchDegrees"),
            "latestFacingTarget": facing.get("latestFacingTargetCoordinate"),
            "planarLookaheadDistance": facing.get("planarLookaheadDistance"),
        },
        "coordinateResolver": {
            "status": promoted_coordinate.get("status"),
            "chain": promoted_coordinate.get("chain"),
            "coordinate": promoted_coordinate.get("coordinate"),
            "ownerAddress": promoted_coordinate.get("ownerAddress"),
            "coordinateAddress": promoted_coordinate.get("coordinateAddress"),
            "apiNowStatus": promoted_coordinate.get("apiNowStatus"),
            "apiNowComparison": promoted_coordinate.get("apiNowComparison"),
        },
        "evidence": {
            "readinessReviewJson": str(readiness_path),
            "navigationDashboardJson": str(dashboard_path),
            "currentTruthJson": str(current_truth_path),
            "coordinateReadbackJson": safe_mapping(safe_mapping(dashboard.get("sources")).get("coordinateReadback")).get("path"),
            "navStateJson": safe_mapping(facing.get("evidence")).get("navStateJson")
            or safe_mapping(safe_mapping(dashboard.get("sources")).get("navState")).get("path"),
            "apiReferenceJson": safe_mapping(safe_mapping(promoted_coordinate.get("apiNowComparison"))).get("apiReferenceJson"),
            "facingComparisonJson": safe_mapping(facing.get("evidence")).get("facingComparisonJson"),
            "threePoseGateJson": safe_mapping(safe_mapping(proof_gates.get("facingThreePoseGate")).get("evidence")).get("summaryJson"),
            "restartSurvivalJson": safe_mapping(safe_mapping(proof_gates.get("facingRestartSurvival")).get("evidence")).get("summaryJson"),
            "turnForwardExperimentJson": safe_mapping(safe_mapping(proof_gates.get("turnForwardExperiment")).get("evidence")).get("summaryJson"),
            "ghidraStaticEvidenceJson": safe_mapping(proof_gates.get("ghidraStaticEvidence")).get("summaryJson"),
        },
        "promotionGates": {
            "reviewPassed": bool(promotion_decision.get("reviewPassed")),
            "freshPrePromotionReadbackSatisfied": True,
            "staticResolverComplete": bool(promoted_coordinate.get("promotionAllowed")),
            "apiNowVsChainNow": str(promoted_coordinate.get("apiNowStatus", "")).startswith("passed-current-pid-"),
            "threePoseDisplacement": safe_mapping(proof_gates.get("facingThreePoseGate")).get("formalThreePoseGatePassed") is True,
            "restartRelogSurvived": safe_mapping(proof_gates.get("facingRestartSurvival")).get("restartRelogSurvived") is True,
            "staticEvidencePassed": safe_mapping(proof_gates.get("ghidraStaticEvidence")).get("status") == "passed",
            "operatorPromotionApproval": True,
        },
        "usePolicy": {
            "primaryUse": "Read current player yaw from the promoted owner object by reading coordinate and facing-target triples in the same cycle.",
            "requiredPreflight": [
                "Verify exact PID/HWND/process-start/module-base before live use.",
                "Re-read owner through rift_x64+0x32EBC80; never reuse historical heap addresses.",
                "Read owner+0x320/+0x324/+0x328 and owner+0x30C/+0x310/+0x314 together for yaw.",
                "Revalidate after client patch, module drift, restart anomalies, or implausible lookahead distance.",
            ],
            "rollbackConditions": [
                "Root RVA no longer resolves to a plausible owner object.",
                "Planar lookahead distance leaves expected range without an explanation.",
                "Fresh camera/movement proof contradicts yaw sign or magnitude.",
            ],
        },
        "safety": {
            **base_safety(),
            "navStateCandidateOnly": False,
            "actionableForNavigation": True,
            "facingPromotion": True,
            "currentTruthWrite": True,
            "targetMemoryBytesWritten": False,
        },
        "artifacts": {
            "promotionJson": str(promotion_json_path),
            "promotionMarkdown": str(promotion_json_path.with_suffix(".md")),
        },
    }


def update_current_truth(
    current_truth: dict[str, Any],
    *,
    generated_at_utc: str,
    promotion_artifact: dict[str, Any],
    promotion_json_path: Path,
) -> dict[str, Any]:
    updated = copy.deepcopy(current_truth)
    updated["updatedAtUtc"] = generated_at_utc
    facing = safe_mapping(updated.get("staticOwnerFacing"))
    primary = safe_mapping(facing.get("primaryCandidate"))
    resolver = safe_mapping(promotion_artifact.get("facingResolver"))
    evidence = safe_mapping(promotion_artifact.get("evidence"))
    previous_promoted_at = facing.get("promotedAtUtc")
    previous_artifact = facing.get("promotionArtifact")

    facing["status"] = "promoted-static-owner-facing-yaw-current-pid-readback-passed"
    facing["promotionAllowed"] = True
    if previous_promoted_at and "firstPromotedAtUtc" not in facing:
        facing["firstPromotedAtUtc"] = previous_promoted_at
    facing["promotedAtUtc"] = generated_at_utc
    facing["latestPromotionAtUtc"] = generated_at_utc
    if previous_artifact and previous_artifact != str(promotion_json_path):
        facing["previousPromotionArtifact"] = previous_artifact
    facing["promotionArtifact"] = str(promotion_json_path)
    facing["latestPromotionArtifact"] = str(promotion_json_path)
    facing["latestPromotionReview"] = {
        "status": "passed",
        "promotionPerformed": True,
        "readinessReviewJson": evidence.get("readinessReviewJson"),
        "dashboardJson": evidence.get("navigationDashboardJson"),
        "recordedAtUtc": generated_at_utc,
    }

    primary["expression"] = resolver.get("expression") or REQUIRED_CHAIN
    primary["rootModule"] = resolver.get("rootModule") or primary.get("rootModule") or "rift_x64.exe"
    primary["rootRva"] = resolver.get("rootRva") or primary.get("rootRva") or "0x32EBC80"
    primary["rootAddress"] = resolver.get("rootAddress") or primary.get("rootAddress")
    primary["ownerAddress"] = resolver.get("ownerAddress") or primary.get("ownerAddress")
    primary["facingTargetAddress"] = resolver.get("facingTargetAddress") or primary.get("facingTargetAddress")
    primary["facingOffsets"] = resolver.get("facingOffsets") or primary.get("facingOffsets") or ["0x30C", "0x310", "0x314"]
    primary["yawFormula"] = resolver.get("yawFormula") or primary.get("yawFormula")
    primary["latestYawDegrees"] = resolver.get("latestYawDegrees")
    primary["latestYawSourcePose"] = (
        f"current-pid-{safe_mapping(updated.get('target')).get('processId')}-explicit-facing-yaw-promotion-"
        f"{generated_at_utc}"
    )
    primary["latestCurrentNavStateReadbackArtifact"] = evidence.get("navStateJson")
    facing["primaryCandidate"] = primary

    latest_reacquisition = safe_mapping(facing.get("latestCurrentReacquisition"))
    latest_reacquisition.update(
        {
            "status": "promoted-current-pid-refresh",
            "promotionPerformed": True,
            "promotionJson": str(promotion_json_path),
            "recordedAtUtc": generated_at_utc,
        }
    )
    facing["latestCurrentReacquisition"] = latest_reacquisition
    facing["blockers"] = []
    updated["staticOwnerFacing"] = facing

    warnings = [str(item) for item in safe_list(updated.get("currentWarnings"))]
    warnings = [
        item
        for item in warnings
        if item != "facing-promotion-is-candidate-only-without-independent-truth-surface-reference"
    ]
    promotion_warning = (
        f"static-owner-facing-yaw-promoted-at-{generated_at_utc}-from-current-readiness-review; "
        "turn-rate/full-actor/proof-anchor remain not promoted"
    )
    if promotion_warning not in warnings:
        warnings.append(promotion_warning)
    updated["currentWarnings"] = warnings
    return updated


def markdown_for_artifact(artifact: Mapping[str, Any]) -> str:
    resolver = safe_mapping(artifact.get("facingResolver"))
    evidence = safe_mapping(artifact.get("evidence"))
    gates = safe_mapping(artifact.get("promotionGates"))
    return "\n".join(
        [
            "# Static Owner Facing/Yaw Promotion — 2026-06-01",
            "",
            "# **✅ PROMOTED**",
            "",
            f"- Generated UTC: `{artifact.get('generatedAtUtc')}`",
            f"- Chain: `{resolver.get('expression')}`",
            f"- Latest yaw: `{resolver.get('latestYawDegrees')}`",
            f"- Facing target address: `{resolver.get('facingTargetAddress')}`",
            f"- Owner address: `{resolver.get('ownerAddress')}`",
            "",
            "## Promotion boundary",
            "",
            "- Promotes: static owner facing/yaw source at `owner+0x30C/+0x310/+0x314`.",
            "- Does not promote: turn-rate `owner+0x304`, support fields `owner+0x300`/`owner+0x408`, full actor/stat chain, proof anchor, or autonomous turn control.",
            "",
            "## Gates",
            "",
            "| Gate | Value |",
            "|---|---|",
            f"| Review passed | `{gates.get('reviewPassed')}` |",
            f"| Fresh pre-promotion readback | `{gates.get('freshPrePromotionReadbackSatisfied')}` |",
            f"| API-now vs chain-now | `{gates.get('apiNowVsChainNow')}` |",
            f"| Three-pose displacement | `{gates.get('threePoseDisplacement')}` |",
            f"| Restart/relog survived | `{gates.get('restartRelogSurvived')}` |",
            f"| Static evidence passed | `{gates.get('staticEvidencePassed')}` |",
            "",
            "## Evidence",
            "",
            f"- Readiness review: `{evidence.get('readinessReviewJson')}`",
            f"- Dashboard: `{evidence.get('navigationDashboardJson')}`",
            f"- Nav state: `{evidence.get('navStateJson')}`",
            f"- API reference: `{evidence.get('apiReferenceJson')}`",
            "",
        ]
    )


def build_summary(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], int]:
    generated = utc_iso()
    output_dir = resolve_path(root, Path(args.output_dir))
    dashboard_path = resolve_path(root, Path(args.dashboard_json))
    current_truth_path = resolve_path(root, Path(args.current_truth_json))
    promotion_json_path = resolve_path(root, Path(args.promotion_json))
    readiness_path = resolve_path(root, Path(args.readiness_json)) if args.readiness_json else newest_readiness_review(root)
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "facing-target-promotion-apply",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated,
        "status": "failed",
        "verdict": "facing-target-promotion-not-run",
        "applyRequested": bool(args.apply),
        "repoRoot": str(root),
        "inputs": {
            "readinessJson": repo_rel(root, readiness_path) if readiness_path else None,
            "dashboardJson": repo_rel(root, dashboard_path),
            "currentTruthJson": repo_rel(root, current_truth_path),
            "promotionJson": repo_rel(root, promotion_json_path),
        },
        "target": {},
        "promotionArtifact": None,
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": {
            **base_safety(),
            "facingPromotion": False,
            "currentTruthWrite": False,
            "targetMemoryBytesWritten": False,
            "dryRunOnly": not bool(args.apply),
        },
        "artifacts": {
            "outputDirectory": repo_rel(root, output_dir),
            "summaryJson": repo_rel(root, output_dir / "summary.json"),
            "summaryMarkdown": repo_rel(root, output_dir / "summary.md"),
            "backupCurrentTruthJson": repo_rel(root, output_dir / "current-truth-before-facing-promotion.json"),
            "promotionJson": repo_rel(root, promotion_json_path),
            "promotionMarkdown": repo_rel(root, promotion_json_path.with_suffix(".md")),
        },
        "next": {"recommendedAction": "Refresh dashboard/status after promotion apply."},
    }
    try:
        if readiness_path is None or not readiness_path.is_file():
            summary["blockers"].append("readiness-review-json-not-found")
        if not dashboard_path.is_file():
            summary["blockers"].append(f"dashboard-json-not-found:{dashboard_path}")
        if not current_truth_path.is_file():
            summary["blockers"].append(f"current-truth-json-not-found:{current_truth_path}")
        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "facing-target-promotion-blocked"
            return summary, 2

        readiness = load_json_object(readiness_path)  # type: ignore[arg-type]
        dashboard = load_json_object(dashboard_path)
        current_truth = load_json_object(current_truth_path)
        decision = safe_mapping(readiness.get("promotionDecision"))
        candidate = safe_mapping(readiness.get("candidate"))
        target = safe_mapping(readiness.get("target"))
        summary["target"] = target
        candidates = safe_mapping(dashboard.get("candidates"))
        promoted_coordinate = safe_mapping(candidates.get("promotedCoordinate"))

        if readiness.get("kind") != "facing-target-promotion-readiness-review-packet":
            summary["blockers"].append(f"readiness-kind-unexpected:{readiness.get('kind')}")
        if readiness.get("status") != "passed" or safe_list(readiness.get("blockers")) or safe_list(readiness.get("errors")):
            summary["blockers"].append("readiness-review-not-clean-passed")
        if decision.get("reviewPassed") is not True:
            summary["blockers"].append("readiness-review-not-passed")
        if decision.get("promotionPerformed") is True:
            summary["warnings"].append("readiness-review-already-claims-promotion-performed")
        if candidate.get("chainExpression") != REQUIRED_CHAIN or candidate.get("offset") != REQUIRED_OFFSET:
            summary["blockers"].append("candidate-chain-or-offset-mismatch")
        if not str(candidate.get("apiNowStatus") or "").startswith("passed-current-pid-"):
            summary["blockers"].append(f"candidate-api-now-not-passed:{candidate.get('apiNowStatus')}")
        if not same_target(target, safe_mapping(dashboard.get("target"))):
            summary["blockers"].append("readiness-target-does-not-match-dashboard-target")
        if not same_target(target, safe_mapping(current_truth.get("target"))):
            summary["blockers"].append("readiness-target-does-not-match-current-truth-target")
        if not bool(promoted_coordinate.get("promotionAllowed")):
            summary["blockers"].append("coordinate-resolver-not-promoted-in-dashboard")
        for key in ("coordinateReadback", "navState", "apiReference", "facingPromotionReadinessReview"):
            if freshness_status(dashboard, key) != "fresh":
                summary["blockers"].append(f"dashboard-source-not-fresh:{key}:{freshness_status(dashboard, key)}")
        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "facing-target-promotion-blocked"
            return summary, 2

        artifact = build_promotion_artifact(
            root=root,
            generated_at_utc=generated,
            readiness_path=readiness_path,
            readiness=readiness,
            dashboard_path=dashboard_path,
            dashboard=dashboard,
            current_truth_path=current_truth_path,
            current_truth=current_truth,
            promotion_json_path=promotion_json_path,
        )
        summary["promotionArtifact"] = artifact
        if args.apply:
            promotion_json_path.parent.mkdir(parents=True, exist_ok=True)
            write_json(promotion_json_path, artifact)
            promotion_json_path.with_suffix(".md").write_text(markdown_for_artifact(artifact), encoding="utf-8")
            output_dir.mkdir(parents=True, exist_ok=True)
            backup_path = output_dir / "current-truth-before-facing-promotion.json"
            backup_path.write_text(current_truth_path.read_text(encoding="utf-8-sig"), encoding="utf-8")
            updated_truth = update_current_truth(
                current_truth,
                generated_at_utc=generated,
                promotion_artifact=artifact,
                promotion_json_path=promotion_json_path,
            )
            write_json(current_truth_path, updated_truth)
            summary["safety"]["facingPromotion"] = True
            summary["safety"]["currentTruthWrite"] = True
            summary["safety"]["navStateCandidateOnly"] = False
            summary["safety"]["actionableForNavigation"] = True
            summary["status"] = "passed"
            summary["verdict"] = "facing-target-promotion-applied"
        else:
            summary["status"] = "passed"
            summary["verdict"] = "facing-target-promotion-dry-run-ready"
        return summary, 0
    except Exception as exc:  # noqa: BLE001 - command must emit structured error.
        summary["status"] = "failed"
        summary["verdict"] = "facing-target-promotion-failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        return summary, 1


def write_summary_outputs(root: Path, output_dir: Path, summary: Mapping[str, Any]) -> None:
    output_dir = resolve_path(root, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "summary.json", summary)
    lines = [
        "# Facing Target Promotion Apply",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Apply requested: `{summary.get('applyRequested')}`",
        f"- Promotion JSON: `{safe_mapping(summary.get('artifacts')).get('promotionJson')}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- `{item}`" for item in safe_list(summary.get("blockers")) or ["none"])
    lines.append("")
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_self_test() -> dict[str, Any]:
    import tempfile

    with tempfile.TemporaryDirectory() as temp_name:
        root = Path(temp_name)
        target = {
            "processName": "rift_x64",
            "processId": 41808,
            "targetWindowHandle": "0x2B0A26",
            "processStartUtc": "2026-06-01T01:50:50Z",
            "moduleBase": "0x7FF6EE5D0000",
        }
        current_truth = {
            "kind": "riftreader-current-truth",
            "updatedAtUtc": "2026-06-01T16:00:00Z",
            "target": target,
            "staticOwnerFacing": {
                "status": "candidate",
                "promotionAllowed": False,
                "primaryCandidate": {
                    "expression": REQUIRED_CHAIN,
                    "yawFormula": "atan2(Z_at_0x314 - playerZ_at_0x328, X_at_0x30C - playerX_at_0x320)",
                },
            },
        }
        dashboard = {
            "kind": "riftreader-navigation-pointer-discovery-status",
            "status": "passed",
            "target": target,
            "sources": {
                key: {"freshness": {"status": "fresh"}}
                for key in ("coordinateReadback", "navState", "apiReference", "facingPromotionReadinessReview")
            },
            "candidates": {
                "promotedCoordinate": {
                    "promotionAllowed": True,
                    "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed",
                    "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                    "apiNowStatus": "passed-current-pid-41808-api-now-vs-chain-now",
                },
                "candidateFacingTarget": {
                    "ownerAddress": "0x1000",
                    "address": "0x130C",
                    "latestYawDegrees": 80.0,
                    "planarLookaheadDistance": 10.0,
                    "evidence": {"navStateJson": "nav.json", "facingComparisonJson": "compare.json"},
                },
            },
            "proofGates": {
                "facingThreePoseGate": {"formalThreePoseGatePassed": True},
                "facingRestartSurvival": {"restartRelogSurvived": True},
                "ghidraStaticEvidence": {"status": "passed"},
            },
        }
        readiness = {
            "kind": "facing-target-promotion-readiness-review-packet",
            "status": "passed",
            "generatedAtUtc": "2026-06-01T16:00:01Z",
            "target": target,
            "candidate": {
                "chainExpression": REQUIRED_CHAIN,
                "offset": REQUIRED_OFFSET,
                "apiNowStatus": "passed-current-pid-41808-api-now-vs-chain-now",
            },
            "promotionDecision": {"reviewPassed": True, "promotionPerformed": False},
            "blockers": [],
            "errors": [],
        }
        write_json(root / DEFAULT_CURRENT_TRUTH_JSON, current_truth)
        write_json(root / DEFAULT_DASHBOARD_JSON, dashboard)
        write_json(root / CAPTURE_ROOT / f"{READINESS_PREFIX}selftest" / "summary.json", readiness)
        args = argparse.Namespace(
            apply=True,
            readiness_json=None,
            dashboard_json=DEFAULT_DASHBOARD_JSON,
            current_truth_json=DEFAULT_CURRENT_TRUTH_JSON,
            output_dir=DEFAULT_OUTPUT_DIR,
            promotion_json=DEFAULT_PROMOTION_JSON,
        )
        summary, exit_code = build_summary(args, root)
        promoted_truth = load_json_object(root / DEFAULT_CURRENT_TRUTH_JSON)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "facing-target-promotion-apply-self-test",
        "status": "passed" if exit_code == 0 and summary.get("status") == "passed" else "failed",
        "checks": {
            "applyExitCodeZero": exit_code == 0,
            "promotionApplied": summary.get("verdict") == "facing-target-promotion-applied",
            "currentTruthPromoted": safe_mapping(promoted_truth.get("staticOwnerFacing")).get("promotionAllowed") is True,
        },
        "safety": {**base_safety(), "movementSent": False, "inputSent": False, "targetMemoryBytesWritten": False},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--readiness-json", default=None)
    parser.add_argument("--dashboard-json", default=str(DEFAULT_DASHBOARD_JSON))
    parser.add_argument("--current-truth-json", default=str(DEFAULT_CURRENT_TRUTH_JSON))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--promotion-json", default=str(DEFAULT_PROMOTION_JSON))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        payload = run_self_test()
        print(json.dumps(payload, indent=2))
        return 0 if payload["status"] == "passed" else 1

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    summary, exit_code = build_summary(args, root)
    write_summary_outputs(root, Path(args.output_dir), summary)
    if args.json:
        compact = {
            "status": summary.get("status"),
            "verdict": summary.get("verdict"),
            "applyRequested": summary.get("applyRequested"),
            "target": summary.get("target"),
            "promotionJson": safe_mapping(summary.get("artifacts")).get("promotionJson"),
            "summaryJson": safe_mapping(summary.get("artifacts")).get("summaryJson"),
            "blockers": summary.get("blockers"),
            "warnings": summary.get("warnings"),
            "errors": summary.get("errors"),
            "safety": summary.get("safety"),
        }
        print(json.dumps(compact, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
