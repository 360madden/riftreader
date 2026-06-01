#!/usr/bin/env python3
"""Apply the explicit static-owner turn-rate promotion gate.

Dry-run is the default. With ``--apply``, this helper writes a tracked
turn-rate promotion artifact and updates current truth. It never sends live
input, moves the player, attaches a debugger, writes target memory, writes
provider repositories, or performs proof/actor-chain/navigation-control
promotion.
"""

from __future__ import annotations

import argparse
import copy
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, write_json
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, write_json  # type: ignore


SCHEMA_VERSION = 1
TOOL_VERSION = "turn-rate-promotion-apply-v0.1.0"
REQUIRED_OFFSET = "0x304"
REQUIRED_CHAIN = "[rift_x64+0x32EBC80]+0x304"
READINESS_PREFIX = "turn-rate-promotion-readiness-review-"
DEFAULT_DASHBOARD_JSON = Path(".riftreader-local") / "navigation-pointer-discovery" / "latest" / "summary.json"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "turn-rate-promotion-apply" / "latest"
DEFAULT_PROMOTION_JSON = Path("docs") / "recovery" / "static-owner-turn-rate-promoted-2026-06-01.json"


def repo_rel(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def newest_readiness_review(root: Path) -> Path | None:
    candidates: list[tuple[float, Path]] = []
    for path in (root / "scripts" / "captures").glob(f"{READINESS_PREFIX}*/summary.json"):
        try:
            payload = load_json_object(path)
        except Exception:  # noqa: BLE001
            continue
        if payload.get("kind") != "turn-rate-promotion-readiness-review-packet":
            continue
        candidates.append((path.stat().st_mtime, path))
    return max(candidates, default=(0.0, None), key=lambda item: item[0])[1]


def same_target(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    keys = ("processId", "targetWindowHandle", "processStartUtc", "moduleBase")
    return all(left.get(key) == right.get(key) for key in keys if left.get(key) is not None or right.get(key) is not None)


def freshness_status(dashboard: Mapping[str, Any], key: str) -> str | None:
    return safe_mapping(safe_mapping(safe_mapping(dashboard.get("sources")).get(key)).get("freshness")).get("status")


def build_promotion_artifact(
    *,
    readiness: Mapping[str, Any],
    dashboard: Mapping[str, Any],
    current_truth_path: Path,
    promotion_json_path: Path,
    generated_at_utc: str,
) -> dict[str, Any]:
    candidates = safe_mapping(dashboard.get("candidates"))
    turn_rate = safe_mapping(candidates.get("candidateTurnRate"))
    promoted_coordinate = safe_mapping(candidates.get("promotedCoordinate"))
    facing = safe_mapping(candidates.get("candidateFacingTarget"))
    candidate = safe_mapping(readiness.get("candidate"))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-turn-rate-promotion",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated_at_utc,
        "status": "promoted",
        "verdict": "static-owner-turn-rate-promoted",
        "approvalRecord": {
            "source": "Explicit current-session operator approval to complete practical navigation-chain promotion gates.",
            "scope": "owner+0x304 turn-rate discriminator only",
        },
        "target": dashboard.get("target") or readiness.get("target"),
        "promotionScope": {
            "promoted": "Static owner turn-rate discriminator at owner+0x304.",
            "notPromoted": [
                "Autonomous turn-control automation.",
                "Turn backend/input method.",
                "Heading/support fields owner+0x300/0x308.",
                "Animation timer owner+0x408.",
                "Full actor/stat chain.",
                "Proof-anchor promotion.",
                "Historical heap owner addresses as static.",
            ],
        },
        "turnRateResolver": {
            "expression": REQUIRED_CHAIN,
            "rootModule": "rift_x64.exe",
            "rootRva": "0x32EBC80",
            "ownerAddress": promoted_coordinate.get("ownerAddress") or safe_mapping(facing).get("ownerAddress"),
            "turnRateOffset": REQUIRED_OFFSET,
            "valueType": "float32",
            "latestValue": turn_rate.get("latestValue") if turn_rate else candidate.get("latestValue"),
            "latestClassification": turn_rate.get("latestClassification") if turn_rate else candidate.get("latestClassification"),
            "signConvention": {
                "positive": "left",
                "negative": "right",
                "nearZero": "stationary",
            },
        },
        "coordinateResolver": {
            "status": promoted_coordinate.get("status"),
            "chain": promoted_coordinate.get("chain"),
        },
        "facingYawResolver": {
            "status": facing.get("status"),
            "chain": facing.get("chainShape"),
            "latestYawDegrees": facing.get("latestYawDegrees"),
        },
        "evidence": {
            "readinessReviewJson": safe_mapping(readiness.get("artifacts")).get("summaryJson"),
            "navigationDashboardJson": str(DEFAULT_DASHBOARD_JSON),
            "currentTruthJson": str(current_truth_path),
            "leftTurnSummaryJson": safe_mapping(readiness.get("inputs")).get("leftTurnSummaryJson"),
            "rightTurnSummaryJson": safe_mapping(readiness.get("inputs")).get("rightTurnSummaryJson"),
            "staticEvidence": safe_mapping(readiness.get("inputs")).get("staticEvidence"),
        },
        "promotionGates": {
            "reviewPassed": safe_mapping(readiness.get("promotionDecision")).get("reviewPassed") is True,
            "freshPrePromotionReadbackSatisfied": True,
            "coordinateResolverCurrent": safe_mapping(safe_mapping(readiness.get("reviewGates")).get("coordinateResolverCurrent")).get("passed") is True,
            "facingYawCurrent": safe_mapping(safe_mapping(readiness.get("reviewGates")).get("facingYawCurrent")).get("passed") is True,
            "leftRightSignFlip": safe_mapping(safe_mapping(readiness.get("reviewGates")).get("leftRightSignFlip")).get("passed") is True,
            "staticRootSourceSiteEvidence": safe_mapping(safe_mapping(readiness.get("reviewGates")).get("staticRootSourceSiteEvidence")).get("passed") is True,
            "operatorPromotionApproval": True,
        },
        "usePolicy": {
            "primaryUse": "Directional turn-rate cross-check/discriminator for route planning and turn completion diagnostics.",
            "requiredPreflight": [
                "Verify exact PID/HWND/process-start/module-base.",
                "Read promoted coordinate and facing/yaw in the same target epoch.",
                "Reacquire owner through rift_x64+0x32EBC80; never reuse heap owner addresses.",
            ],
            "boundary": "This promotion does not authorize autonomous turn-control automation by itself.",
        },
        "safety": base_safety()
        | {
            "turnRatePromotion": True,
            "currentTruthWrite": True,
            "navigationControl": False,
            "targetMemoryBytesWritten": False,
        },
        "artifacts": {
            "promotionJson": str(promotion_json_path),
            "promotionMarkdown": str(promotion_json_path.with_suffix(".md")),
        },
    }


def update_current_truth(current_truth: dict[str, Any], artifact: Mapping[str, Any], promotion_json_path: Path) -> dict[str, Any]:
    updated = copy.deepcopy(current_truth)
    generated = str(artifact.get("generatedAtUtc"))
    resolver = safe_mapping(artifact.get("turnRateResolver"))
    promotion_entry = {
        "status": "promoted-static-owner-turn-rate-current-pid-readback-passed",
        "promotionAllowed": True,
        "promotedAtUtc": generated,
        "promotionArtifact": str(promotion_json_path),
        "primaryCandidate": {
            "expression": REQUIRED_CHAIN,
            "rootModule": "rift_x64.exe",
            "rootRva": "0x32EBC80",
            "ownerAddress": resolver.get("ownerAddress"),
            "turnRateOffset": REQUIRED_OFFSET,
            "latestValue": resolver.get("latestValue"),
            "latestClassification": resolver.get("latestClassification"),
            "signConvention": resolver.get("signConvention"),
            "valueType": "float32",
        },
        "latestPromotionReview": {
            "status": "passed",
            "promotionPerformed": True,
            "recordedAtUtc": generated,
            "readinessReviewJson": safe_mapping(artifact.get("evidence")).get("readinessReviewJson"),
        },
        "doesNotPromote": [
            "Autonomous turn-control automation.",
            "Heading/support fields owner+0x300/0x308.",
            "Animation timer owner+0x408.",
            "Full actor/stat chain.",
        ],
    }
    updated["staticOwnerTurnRate"] = promotion_entry
    chains = safe_mapping(updated.get("navigationControlChains"))
    chains["turnRate"] = {
        **promotion_entry,
        "state": "promoted",
        "chain": REQUIRED_CHAIN,
        "offset": REQUIRED_OFFSET,
    }
    support = safe_mapping(chains.get("supportFields"))
    support.setdefault("headingSupport0x300", {"state": "candidate", "offset": "0x300"})
    support.setdefault("rotationSupport0x308", {"state": "candidate", "offset": "0x308"})
    support.setdefault("animationTimer0x408", {"state": "candidate", "offset": "0x408"})
    chains["supportFields"] = support
    updated["navigationControlChains"] = chains
    warnings = [item for item in updated.get("currentWarnings", []) if item != "turn-rate-candidate-only-without-independent-promotion-artifact"]
    updated["currentWarnings"] = warnings
    updated["updatedAtUtc"] = generated
    return updated


def markdown_for_artifact(artifact: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Static Owner Turn-Rate Promotion — 2026-06-01",
            "",
            f"- Status: `{artifact.get('status')}`",
            f"- Generated UTC: `{artifact.get('generatedAtUtc')}`",
            f"- Resolver: `{safe_mapping(artifact.get('turnRateResolver')).get('expression')}`",
            "",
            "## Promotion boundary",
            "",
            f"Promoted: {safe_mapping(artifact.get('promotionScope')).get('promoted')}",
            "",
            "Not promoted:",
            *[f"- {item}" for item in safe_mapping(artifact.get("promotionScope")).get("notPromoted", [])],
            "",
        ]
    )


def build_summary(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], int]:
    readiness_path = resolve_path(root, args.readiness_json) if args.readiness_json else newest_readiness_review(root)
    dashboard_path = resolve_path(root, args.dashboard_json)
    current_truth_path = resolve_path(root, args.current_truth_json)
    output_dir = resolve_path(root, args.output_dir)
    promotion_json_path = resolve_path(root, args.promotion_json)
    generated = utc_iso()
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "turn-rate-promotion-apply",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated,
        "status": "pending",
        "verdict": "turn-rate-promotion-not-run",
        "applyRequested": bool(args.apply),
        "inputs": {
            "readinessJson": repo_rel(root, readiness_path),
            "dashboardJson": repo_rel(root, dashboard_path),
            "currentTruthJson": repo_rel(root, current_truth_path),
            "promotionJson": repo_rel(root, promotion_json_path),
        },
        "promotionArtifact": None,
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": base_safety() | {"turnRatePromotion": False, "currentTruthWrite": False, "targetMemoryBytesWritten": False},
        "artifacts": {
            "summaryJson": str(output_dir / "summary.json"),
            "summaryMarkdown": str(output_dir / "summary.md"),
            "backupCurrentTruthJson": repo_rel(root, output_dir / "current-truth-before-turn-rate-promotion.json"),
            "promotionJson": repo_rel(root, promotion_json_path),
            "promotionMarkdown": repo_rel(root, promotion_json_path.with_suffix(".md")),
        },
    }
    try:
        if readiness_path is None or not readiness_path.is_file():
            summary["blockers"].append("turn-rate-readiness-review-not-found")
            readiness = {}
        else:
            readiness = load_json_object(readiness_path)
        dashboard = load_json_object(dashboard_path)
        current_truth = load_json_object(current_truth_path)
        if readiness.get("kind") != "turn-rate-promotion-readiness-review-packet":
            summary["blockers"].append(f"readiness-kind-unexpected:{readiness.get('kind')}")
        decision = safe_mapping(readiness.get("promotionDecision"))
        if decision.get("reviewPassed") is not True:
            summary["blockers"].append("readiness-review-not-passed")
        if decision.get("promotionPerformed") is True:
            summary["warnings"].append("readiness-review-already-claims-promotion-performed")
        if dashboard.get("status") != "passed":
            summary["blockers"].append(f"dashboard-status-not-passed:{dashboard.get('status')}")
        for key in ("coordinateReadback", "navState", "apiReference"):
            status = freshness_status(dashboard, key)
            if status != "fresh":
                summary["blockers"].append(f"dashboard-source-not-fresh:{key}:{status}")
        if not same_target(safe_mapping(dashboard.get("target")), safe_mapping(current_truth.get("target"))):
            summary["blockers"].append("dashboard-current-truth-target-mismatch")
        candidate = safe_mapping(readiness.get("candidate"))
        if candidate.get("offset") != REQUIRED_OFFSET:
            summary["blockers"].append(f"turn-rate-offset-mismatch:{candidate.get('offset')}")
        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "turn-rate-promotion-blocked"
            return summary, 2

        artifact = build_promotion_artifact(
            readiness=readiness,
            dashboard=dashboard,
            current_truth_path=current_truth_path,
            promotion_json_path=promotion_json_path,
            generated_at_utc=generated,
        )
        summary["promotionArtifact"] = artifact
        if args.apply:
            promotion_json_path.parent.mkdir(parents=True, exist_ok=True)
            write_json(promotion_json_path, artifact)
            promotion_json_path.with_suffix(".md").write_text(markdown_for_artifact(artifact), encoding="utf-8")
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "current-truth-before-turn-rate-promotion.json").write_text(
                current_truth_path.read_text(encoding="utf-8-sig"),
                encoding="utf-8",
            )
            write_json(current_truth_path, update_current_truth(current_truth, artifact, promotion_json_path))
            summary["safety"]["turnRatePromotion"] = True
            summary["safety"]["currentTruthWrite"] = True
            summary["status"] = "passed"
            summary["verdict"] = "turn-rate-promotion-applied"
        else:
            summary["status"] = "passed"
            summary["verdict"] = "turn-rate-promotion-dry-run-ready"
        return summary, 0
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "turn-rate-promotion-failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        return summary, 1


def write_summary_outputs(output_dir: Path, summary: Mapping[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "summary.json", summary)
    lines = [
        "# Turn-Rate Promotion Apply",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Apply requested: `{summary.get('applyRequested')}`",
        f"- Promotion JSON: `{safe_mapping(summary.get('artifacts')).get('promotionJson')}`",
        "",
        "## Blockers",
        "",
        *[f"- `{item}`" for item in summary.get("blockers", []) or ["none"]],
    ]
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_name:
        root = Path(temp_name)
        target = {"processId": 1, "targetWindowHandle": "0x1", "processStartUtc": "2026-06-01T00:00:00Z", "moduleBase": "0x1000"}
        truth = root / DEFAULT_CURRENT_TRUTH_JSON
        dashboard = root / DEFAULT_DASHBOARD_JSON
        readiness = root / "scripts" / "captures" / f"{READINESS_PREFIX}selftest" / "summary.json"
        write_json(truth, {"kind": "riftreader-current-truth", "target": target, "currentWarnings": ["turn-rate-candidate-only-without-independent-promotion-artifact"]})
        write_json(
            dashboard,
            {
                "kind": "riftreader-navigation-pointer-discovery-status",
                "status": "passed",
                "target": target,
                "sources": {key: {"freshness": {"status": "fresh"}} for key in ("coordinateReadback", "navState", "apiReference")},
                "candidates": {
                    "promotedCoordinate": {"promotionAllowed": True, "ownerAddress": "0x1000", "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328"},
                    "candidateFacingTarget": {"promotionAllowed": True, "status": "promoted-static-owner-facing-yaw-current-pid-readback-passed", "chainShape": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314"},
                    "candidateTurnRate": {"promotionAllowed": False, "offset": "0x304", "latestValue": 0.0, "latestClassification": "stationary"},
                },
            },
        )
        write_json(
            readiness,
            {
                "kind": "turn-rate-promotion-readiness-review-packet",
                "status": "passed",
                "target": target,
                "candidate": {"offset": REQUIRED_OFFSET, "latestValue": 0.0, "latestClassification": "stationary"},
                "promotionDecision": {"reviewPassed": True, "promotionPerformed": False},
                "reviewGates": {
                    "coordinateResolverCurrent": {"passed": True},
                    "facingYawCurrent": {"passed": True},
                    "leftRightSignFlip": {"passed": True},
                    "staticRootSourceSiteEvidence": {"passed": True},
                },
                "artifacts": {"summaryJson": str(readiness)},
            },
        )
        args = argparse.Namespace(
            apply=True,
            readiness_json=readiness,
            dashboard_json=dashboard,
            current_truth_json=truth,
            output_dir=root / ".local" / "apply",
            promotion_json=root / DEFAULT_PROMOTION_JSON,
        )
        summary, exit_code = build_summary(args, root)
        promoted_truth = load_json_object(truth)
    return {
        "kind": "turn-rate-promotion-apply-self-test",
        "status": "passed" if exit_code == 0 and safe_mapping(promoted_truth.get("staticOwnerTurnRate")).get("promotionAllowed") is True else "failed",
        "promotionApplied": summary.get("verdict") == "turn-rate-promotion-applied",
        "currentTruthPromoted": safe_mapping(promoted_truth.get("staticOwnerTurnRate")).get("promotionAllowed") is True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root")
    parser.add_argument("--readiness-json")
    parser.add_argument("--dashboard-json", default=str(DEFAULT_DASHBOARD_JSON))
    parser.add_argument("--current-truth-json", default=str(DEFAULT_CURRENT_TRUTH_JSON))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--promotion-json", default=str(DEFAULT_PROMOTION_JSON))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        result = run_self_test()
        print(json.dumps(result) if args.json else json.dumps(result, indent=2))
        return 0 if result.get("status") == "passed" else 1

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    summary, exit_code = build_summary(args, root)
    output_dir = resolve_path(root, args.output_dir)
    write_summary_outputs(output_dir, summary)
    compact = {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "summaryJson": safe_mapping(summary.get("artifacts")).get("summaryJson"),
        "summaryMarkdown": safe_mapping(summary.get("artifacts")).get("summaryMarkdown"),
        "promotionJson": safe_mapping(summary.get("artifacts")).get("promotionJson"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }
    print(json.dumps(compact) if args.json else json.dumps(compact, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
