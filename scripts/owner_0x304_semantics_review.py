#!/usr/bin/env python3
"""Review current owner+0x304 semantics from existing navigation evidence.

This helper is report-only.  It consumes existing camera/yaw multi-pose,
turn-rate readiness, and no-input nav-state artifacts to decide whether
``owner+0x304`` currently behaves like an active turn-rate discriminator or a
yaw-adjacent scalar.  It never sends input, reads target memory, writes current
truth, or promotes the field.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
TOOL_VERSION = "owner-0x304-semantics-review-v0.1.0"
DEFAULT_OUTPUT_ROOT = Path("scripts") / "captures"
DEFAULT_MAX_RADIANS_ERROR = 0.05
DEFAULT_MIN_YAW_DELTA_DEGREES = 2.0
DEFAULT_MIN_OWNER304_DELTA_ABS = 0.05
DEFAULT_MIN_POSE_COUNT = 2


def safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def repo_rel(root: Path, path: Path | str | None) -> str | None:
    if path is None:
        return None
    candidate = Path(str(path))
    try:
        return str(candidate.resolve().relative_to(root.resolve()))
    except Exception:  # noqa: BLE001 - display fallback only.
        return str(candidate)


def resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def newest_summary(root: Path, *, prefix: str, expected_kind: str) -> Path | None:
    capture_root = root / "scripts" / "captures"
    if not capture_root.is_dir():
        return None
    candidates: list[tuple[str, int, Path]] = []
    for path in capture_root.glob(f"{prefix}*/summary.json"):
        if not path.is_file():
            continue
        try:
            data = load_json_object(path)
        except Exception:  # noqa: BLE001 - ignore malformed historical artifacts.
            continue
        if data.get("kind") != expected_kind:
            continue
        generated = str(data.get("generatedAtUtc") or "")
        candidates.append((generated, path.stat().st_mtime_ns, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def offset_row(pose: Mapping[str, Any], offset: str = "0x304") -> dict[str, Any] | None:
    for row in safe_list(pose.get("changedFocusOffsets")):
        item = safe_mapping(row)
        if str(item.get("offset") or "").lower() == offset.lower():
            return item
    return None


def pose_semantics_rows(
    multipose: Mapping[str, Any],
    *,
    max_radians_error: float,
    min_yaw_delta_degrees: float,
    min_owner304_delta_abs: float,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    poses = safe_list(multipose.get("poses"))
    for index, raw_pose in enumerate(poses):
        pose = safe_mapping(raw_pose)
        stimulus = safe_mapping(pose.get("stimulus"))
        yaw_delta_degrees = finite_float(pose.get("signedYawDeltaDegrees"))
        row = offset_row(pose)
        owner_delta = finite_float(safe_mapping(row).get("delta") if row else None)
        if row is None:
            warnings.append(f"pose-{index}-owner-0x304-delta-missing")
            continue
        if yaw_delta_degrees is None or owner_delta is None:
            warnings.append(f"pose-{index}-yaw-or-owner-0x304-delta-not-finite")
            continue
        yaw_delta_radians = math.radians(yaw_delta_degrees)
        same_error = abs(owner_delta - yaw_delta_radians)
        opposite_error = abs(owner_delta + yaw_delta_radians)
        relation = "opposes-yaw-radians" if opposite_error < same_error else "matches-yaw-radians"
        row_summary = {
            "poseIndex": index,
            "direction": stimulus.get("direction"),
            "summaryJson": pose.get("summaryJson"),
            "classification": pose.get("classification"),
            "staticYawChanged": pose.get("staticYawChanged"),
            "signedYawDeltaDegrees": yaw_delta_degrees,
            "yawDeltaRadians": yaw_delta_radians,
            "owner304Delta": owner_delta,
            "owner304AbsDelta": abs(owner_delta),
            "sameRadianError": same_error,
            "oppositeRadianError": opposite_error,
            "bestRadianRelation": relation,
            "withinRadianTolerance": min(same_error, opposite_error) <= max_radians_error,
            "yawDeltaAboveMinimum": abs(yaw_delta_degrees) >= min_yaw_delta_degrees,
            "owner304DeltaAboveMinimum": abs(owner_delta) >= min_owner304_delta_abs,
        }
        rows.append(row_summary)
    if not rows:
        blockers.append("owner-0x304-pose-delta-evidence-missing")
    return rows, sorted(set(blockers)), sorted(set(warnings))


def turn_review_delta_blocked(review: Mapping[str, Any] | None) -> dict[str, Any]:
    if not review:
        return {
            "status": "missing",
            "deltaProofBlocked": None,
            "reviewPassed": None,
            "blockers": [],
            "summaryJson": None,
        }
    blockers = [str(item) for item in safe_list(review.get("blockers"))]
    delta_blocked = any(
        "turn-rate-delta-proof-too-small" in item or "turn-rate-delta-proof-missing" in item or "analysis-turn-rate-delta-proof-required" in item
        for item in blockers
    )
    decision = safe_mapping(review.get("promotionDecision"))
    artifacts = safe_mapping(review.get("artifacts"))
    return {
        "status": review.get("status"),
        "verdict": review.get("verdict"),
        "deltaProofBlocked": delta_blocked,
        "reviewPassed": bool(decision.get("reviewPassed")),
        "promotionAllowed": bool(decision.get("promotionAllowed")),
        "promotionPerformed": bool(decision.get("promotionPerformed")),
        "blockers": blockers,
        "summaryJson": artifacts.get("summaryJson"),
    }


def stationary_nav_state_review(nav_state: Mapping[str, Any] | None) -> dict[str, Any]:
    if not nav_state:
        return {"status": "missing", "stationary": None, "legacyTurnClassifierReliable": None}
    analysis = safe_mapping(nav_state.get("analysis"))
    latest = safe_mapping(nav_state.get("latestState"))
    discriminator = safe_mapping(latest.get("turnRateDiscriminator"))
    max_planar = finite_float(analysis.get("maxPlanarDelta"))
    yaw_range = finite_float(analysis.get("yawRangeDegrees"))
    max_yaw = finite_float(analysis.get("maxAbsYawDeltaDegrees"))
    stationary = (
        nav_state.get("status") == "passed"
        and (max_planar is None or max_planar <= 0.001)
        and (yaw_range is None or yaw_range <= 0.001)
        and (max_yaw is None or max_yaw <= 0.001)
    )
    legacy_turning = discriminator.get("turning") is True
    return {
        "status": nav_state.get("status"),
        "summaryJson": safe_mapping(nav_state.get("artifacts")).get("summaryJson"),
        "stationary": stationary,
        "maxPlanarDelta": max_planar,
        "yawRangeDegrees": yaw_range,
        "maxAbsYawDeltaDegrees": max_yaw,
        "owner304Value": latest.get("turnRate0x304"),
        "legacyTurnRateClassification": latest.get("turnRateClassification"),
        "legacyTurnRateDiscriminator": discriminator,
        "legacyTurnClassifierReliable": False if stationary and legacy_turning else None,
        "legacyClassifierWarning": "legacy-0x304-sign-classifier-reports-turning-while-stationary"
        if stationary and legacy_turning
        else None,
    }


def build_analysis(
    *,
    multipose: Mapping[str, Any],
    turn_review: Mapping[str, Any] | None,
    nav_state: Mapping[str, Any] | None,
    max_radians_error: float,
    min_yaw_delta_degrees: float,
    min_owner304_delta_abs: float,
    min_pose_count: int,
) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    rows, row_blockers, row_warnings = pose_semantics_rows(
        multipose,
        max_radians_error=max_radians_error,
        min_yaw_delta_degrees=min_yaw_delta_degrees,
        min_owner304_delta_abs=min_owner304_delta_abs,
    )
    blockers.extend(row_blockers)
    warnings.extend(row_warnings)
    directions = sorted({str(row.get("direction")) for row in rows if row.get("direction")})
    if len(rows) < min_pose_count:
        blockers.append(f"owner-0x304-minimum-pose-count-not-met:{len(rows)}<{min_pose_count}")
    if not {"left", "right"}.issubset(set(directions)):
        blockers.append("owner-0x304-left-right-pose-pair-required")
    weak_rows = [
        row
        for row in rows
        if not bool(row.get("withinRadianTolerance"))
        or not bool(row.get("yawDeltaAboveMinimum"))
        or not bool(row.get("owner304DeltaAboveMinimum"))
    ]
    if weak_rows:
        blockers.append("owner-0x304-yaw-radian-correlation-not-proven")
    max_same_error = max((float(row["sameRadianError"]) for row in rows), default=None)
    max_opposite_error = max((float(row["oppositeRadianError"]) for row in rows), default=None)
    relation = "unclassified"
    if rows and max_opposite_error is not None and max_opposite_error <= max_radians_error and (
        max_same_error is None or max_opposite_error < max_same_error
    ):
        relation = "yaw-adjacent-opposes-promoted-yaw-radians"
    elif rows and max_same_error is not None and max_same_error <= max_radians_error:
        relation = "yaw-adjacent-matches-promoted-yaw-radians"
    elif rows:
        relation = "changed-but-not-radian-yaw"
    turn_delta_review = turn_review_delta_blocked(turn_review)
    if turn_delta_review.get("deltaProofBlocked") is True:
        warnings.append("active-turn-rate-delta-proof-blocked-owner-0x304-not-promotable-as-turn-rate")
    elif turn_delta_review.get("status") == "missing":
        warnings.append("turn-rate-promotion-review-missing")
    stationary_review = stationary_nav_state_review(nav_state)
    if stationary_review.get("legacyClassifierWarning"):
        warnings.append(str(stationary_review["legacyClassifierWarning"]))

    yaw_adjacent = relation in {
        "yaw-adjacent-opposes-promoted-yaw-radians",
        "yaw-adjacent-matches-promoted-yaw-radians",
    }
    if yaw_adjacent and turn_delta_review.get("deltaProofBlocked") is True:
        semantic_verdict = "owner-0x304-yaw-adjacent-scalar-not-active-turn-rate"
    elif yaw_adjacent:
        semantic_verdict = "owner-0x304-yaw-adjacent-scalar-needs-active-turn-rate-contrast"
    else:
        semantic_verdict = "owner-0x304-semantics-not-proven"
    return (
        {
            "status": "blocked" if blockers else "passed",
            "classification": relation,
            "semanticVerdict": semantic_verdict,
            "candidateOnly": True,
            "promotionAllowed": False,
            "owner304Role": "yaw-adjacent-scalar-candidate" if yaw_adjacent else "unproven-candidate",
            "activeTurnRatePromotionAllowed": False,
            "maxRadiansErrorTolerance": max_radians_error,
            "maxSameRadianError": max_same_error,
            "maxOppositeRadianError": max_opposite_error,
            "directions": directions,
            "poseCount": len(rows),
            "poses": rows,
            "turnRateReadinessContrast": turn_delta_review,
            "stationaryNavStateReview": stationary_review,
            "recommendedAction": (
                "Keep owner+0x304 candidate-only and do not promote it as turn-rate; use promoted facing/yaw for route decisions."
                if semantic_verdict == "owner-0x304-yaw-adjacent-scalar-not-active-turn-rate"
                else "Collect a fresh left/right camera-yaw and turn-key contrast pack before changing owner+0x304 semantics."
            ),
        },
        sorted(set(blockers)),
        sorted(set(warnings)),
    )


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root) if args.output_root else DEFAULT_OUTPUT_ROOT
    output_root = output_root if output_root.is_absolute() else root / output_root
    run_prefix = "owner-0x304-semantics-self-test" if args.self_test else "owner-0x304-semantics-review"
    run_dir = output_root / f"{run_prefix}-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=False)

    if args.self_test:
        return build_self_test_summary(run_dir)

    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    multipose_path = resolve_path(root, args.camera_yaw_multipose_summary_json) or newest_summary(
        root,
        prefix="static-owner-camera-yaw-multipose-report-",
        expected_kind="static-owner-camera-yaw-multipose-report",
    )
    turn_review_path = resolve_path(root, args.turn_rate_review_summary_json) or newest_summary(
        root,
        prefix="turn-rate-promotion-readiness-review-",
        expected_kind="turn-rate-promotion-readiness-review-packet",
    )
    nav_state_path = resolve_path(root, args.nav_state_summary_json) or newest_summary(
        root,
        prefix="static-owner-nav-state-",
        expected_kind="static-owner-nav-state-readback",
    )

    multipose: dict[str, Any] | None = None
    turn_review: dict[str, Any] | None = None
    nav_state: dict[str, Any] | None = None
    try:
        if not multipose_path:
            blockers.append("camera-yaw-multipose-summary-required")
        else:
            multipose = load_json_object(multipose_path)
            if multipose.get("kind") != "static-owner-camera-yaw-multipose-report":
                blockers.append(f"camera-yaw-multipose-kind-mismatch:{multipose.get('kind')}")
        if turn_review_path:
            turn_review = load_json_object(turn_review_path)
        else:
            warnings.append("turn-rate-review-summary-missing")
        if nav_state_path:
            nav_state = load_json_object(nav_state_path)
        else:
            warnings.append("nav-state-summary-missing")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{type(exc).__name__}:{exc}")

    analysis: dict[str, Any] = {}
    if multipose and not errors:
        analysis, analysis_blockers, analysis_warnings = build_analysis(
            multipose=multipose,
            turn_review=turn_review,
            nav_state=nav_state,
            max_radians_error=float(args.max_radians_error),
            min_yaw_delta_degrees=float(args.min_yaw_delta_degrees),
            min_owner304_delta_abs=float(args.min_owner304_delta_abs),
            min_pose_count=int(args.min_pose_count),
        )
        blockers.extend(analysis_blockers)
        warnings.extend(analysis_warnings)

    status = "failed" if errors else ("blocked" if blockers else "passed")
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "owner-0x304-semantics-review",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": analysis.get("semanticVerdict") if status == "passed" else "owner-0x304-semantics-review-blocked" if status == "blocked" else "owner-0x304-semantics-review-failed",
        "repoRoot": str(root),
        "sourceArtifacts": {
            "cameraYawMultiposeSummaryJson": repo_rel(root, multipose_path),
            "turnRateReviewSummaryJson": repo_rel(root, turn_review_path),
            "navStateSummaryJson": repo_rel(root, nav_state_path),
        },
        "analysis": analysis,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": errors,
        "safety": base_safety()
        | {
            "reportOnly": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "turnRatePromotion": False,
            "currentTruthWrite": False,
        },
        "sourceSafety": {
            "cameraYawInputSent": bool(safe_mapping(safe_mapping(multipose or {}).get("sourceSafety")).get("inputSent")),
            "cameraYawMovementSent": bool(safe_mapping(safe_mapping(multipose or {}).get("sourceSafety")).get("movementSent")),
            "cameraYawTargetMemoryBytesRead": bool(
                safe_mapping(safe_mapping(multipose or {}).get("sourceSafety")).get("targetMemoryBytesRead")
            ),
        },
        "next": {"recommendedAction": analysis.get("recommendedAction")},
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }
    return summary


def build_self_test_summary(run_dir: Path) -> dict[str, Any]:
    multipose = {
        "kind": "static-owner-camera-yaw-multipose-report",
        "poses": [
            {
                "stimulus": {"direction": "right"},
                "classification": "visual-and-static-yaw-changed",
                "staticYawChanged": True,
                "signedYawDeltaDegrees": 30.0,
                "changedFocusOffsets": [{"offset": "0x304", "delta": -math.radians(30.0), "absDelta": math.radians(30.0)}],
            },
            {
                "stimulus": {"direction": "left"},
                "classification": "visual-and-static-yaw-changed",
                "staticYawChanged": True,
                "signedYawDeltaDegrees": -30.0,
                "changedFocusOffsets": [{"offset": "0x304", "delta": math.radians(30.0), "absDelta": math.radians(30.0)}],
            },
        ],
    }
    turn_review = {
        "kind": "turn-rate-promotion-readiness-review-packet",
        "status": "blocked",
        "blockers": ["left-turn-rate-delta-proof-too-small:0.0"],
        "promotionDecision": {"reviewPassed": False, "promotionAllowed": False, "promotionPerformed": False},
    }
    nav_state = {
        "kind": "static-owner-nav-state-readback",
        "status": "passed",
        "latestState": {
            "turnRate0x304": 0.5,
            "turnRateClassification": "left",
            "turnRateDiscriminator": {"direction": "left", "turning": True, "rate": 0.5},
        },
        "analysis": {"maxPlanarDelta": 0.0, "yawRangeDegrees": 0.0, "maxAbsYawDeltaDegrees": 0.0},
    }
    analysis, blockers, warnings = build_analysis(
        multipose=multipose,
        turn_review=turn_review,
        nav_state=nav_state,
        max_radians_error=DEFAULT_MAX_RADIANS_ERROR,
        min_yaw_delta_degrees=DEFAULT_MIN_YAW_DELTA_DEGREES,
        min_owner304_delta_abs=DEFAULT_MIN_OWNER304_DELTA_ABS,
        min_pose_count=DEFAULT_MIN_POSE_COUNT,
    )
    checks = [
        {"name": "analysis-passed", "passed": analysis.get("status") == "passed"},
        {
            "name": "yaw-adjacent-opposite-radians",
            "passed": analysis.get("classification") == "yaw-adjacent-opposes-promoted-yaw-radians",
        },
        {
            "name": "not-turn-rate-verdict",
            "passed": analysis.get("semanticVerdict") == "owner-0x304-yaw-adjacent-scalar-not-active-turn-rate",
        },
    ]
    passed = all(bool(item["passed"]) for item in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "owner-0x304-semantics-review-self-test",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "passed" if passed else "failed",
        "verdict": "self-test-passed" if passed else "self-test-failed",
        "checks": checks,
        "analysis": analysis,
        "blockers": blockers,
        "warnings": warnings,
        "errors": [] if passed else ["self-test-check-failed"],
        "safety": base_safety() | {"reportOnly": True, "targetMemoryBytesRead": False, "targetMemoryBytesWritten": False},
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    analysis = safe_mapping(summary.get("analysis"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Owner +0x304 semantics review",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        "",
        "## Analysis",
        "",
        f"- Classification: `{analysis.get('classification')}`",
        f"- Owner role: `{analysis.get('owner304Role')}`",
        f"- Max opposite-radian error: `{analysis.get('maxOppositeRadianError')}`",
        f"- Max same-radian error: `{analysis.get('maxSameRadianError')}`",
        f"- Pose count: `{analysis.get('poseCount')}`",
        f"- Directions: `{analysis.get('directions')}`",
        f"- Promotion allowed: `{analysis.get('promotionAllowed')}`",
        "",
        "## Pose relation rows",
        "",
        "| Direction | Yaw delta deg | Yaw delta rad | 0x304 delta | Relation | Opposite error |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for row in safe_list(analysis.get("poses")):
        item = safe_mapping(row)
        lines.append(
            f"| `{item.get('direction')}` | `{item.get('signedYawDeltaDegrees')}` | `{item.get('yawDeltaRadians')}` | "
            f"`{item.get('owner304Delta')}` | `{item.get('bestRadianRelation')}` | `{item.get('oppositeRadianError')}` |"
        )
    lines.extend(["", "## Source artifacts", ""])
    for key, value in safe_mapping(summary.get("sourceArtifacts")).items():
        lines.append(f"- `{key}`: `{value}`")
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in safe_list(summary.get("warnings")))
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in safe_list(summary.get("errors")))
    lines.extend(["", "## Safety", ""])
    lines.append("Report-only; no live input, target memory read/write, current-truth write, or promotion.")
    lines.extend(["", "## Artifacts", ""])
    lines.append(f"- Summary JSON: `{artifacts.get('summaryJson')}`")
    lines.append(f"- Summary Markdown: `{artifacts.get('summaryMarkdown')}`")
    return "\n".join(lines) + "\n"


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    analysis = safe_mapping(summary.get("analysis"))
    artifacts = safe_mapping(summary.get("artifacts"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "classification": analysis.get("classification"),
        "owner304Role": analysis.get("owner304Role"),
        "maxOppositeRadianError": analysis.get("maxOppositeRadianError"),
        "maxSameRadianError": analysis.get("maxSameRadianError"),
        "poseCount": analysis.get("poseCount"),
        "promotionAllowed": analysis.get("promotionAllowed"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
        "safety": summary.get("safety", {}),
    }


def persist(summary: dict[str, Any]) -> None:
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review owner+0x304 semantic evidence without promotion.")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--camera-yaw-multipose-summary-json")
    parser.add_argument("--turn-rate-review-summary-json")
    parser.add_argument("--nav-state-summary-json")
    parser.add_argument("--max-radians-error", type=float, default=DEFAULT_MAX_RADIANS_ERROR)
    parser.add_argument("--min-yaw-delta-degrees", type=float, default=DEFAULT_MIN_YAW_DELTA_DEGREES)
    parser.add_argument("--min-owner304-delta-abs", type=float, default=DEFAULT_MIN_OWNER304_DELTA_ABS)
    parser.add_argument("--min-pose-count", type=int, default=DEFAULT_MIN_POSE_COUNT)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_summary(args)
    persist(summary)
    print(json.dumps(compact(summary), ensure_ascii=False) if args.json else json.dumps(compact(summary), indent=2, ensure_ascii=False))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
