#!/usr/bin/env python3
"""Build a report-only static-owner turn-rate promotion-readiness packet.

This helper consumes existing navigation/readback/static evidence and writes a
durable JSON/Markdown packet. It does not send live input, read target memory,
restart RIFT, attach debuggers, write providers, update current truth, mutate
Git, or promote turn-rate truth.
"""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, write_json
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, write_json  # type: ignore


SCHEMA_VERSION = 1
REQUIRED_OFFSET = "0x304"
REQUIRED_CHAIN = "[rift_x64+0x32EBC80]+0x304"
DEFAULT_NAVIGATION_SUMMARY = Path(".riftreader-local") / "navigation-pointer-discovery" / "latest" / "summary.json"
DEFAULT_OUTPUT_ROOT = Path("scripts") / "captures"
READINESS_PREFIX = "turn-rate-promotion-readiness-review-"
DEFAULT_MIN_TURN_RATE_DELTA_ABS = 0.35


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def repo_rel(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def resolve_under_repo(root: Path, value: str | Path | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_optional_input(root: Path, path: Path | None, *, label: str, blockers: list[str], errors: list[str]) -> dict[str, Any] | None:
    if path is None:
        blockers.append(f"{label}-summary-json-required")
        return None
    if not path.is_file():
        blockers.append(f"{label}-summary-json-not-found:{repo_rel(root, path)}")
        return None
    try:
        return load_json_object(path)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{label}-summary-json-malformed:{repo_rel(root, path)}:{type(exc).__name__}:{exc}")
        return None


def source_safety_summary(sources: list[Mapping[str, Any]]) -> dict[str, Any]:
    summary = base_safety()
    summary["turnRatePromotion"] = False
    summary["currentTruthWrite"] = False
    for source in sources:
        for safety in (safe_mapping(source.get("safety")), safe_mapping(source.get("sourceSafety"))):
            for key in set(summary) | set(safety):
                summary[key] = bool(summary.get(key)) or bool(safety.get(key))
    return summary


def validate_navigation(nav: Mapping[str, Any] | None, blockers: list[str]) -> dict[str, Any]:
    if not nav:
        return {}
    if nav.get("kind") != "riftreader-navigation-pointer-discovery-status":
        blockers.append(f"navigation-summary-kind-unexpected:{nav.get('kind')}")
    if nav.get("status") != "passed":
        blockers.append(f"navigation-summary-status-not-passed:{nav.get('status')}")
    candidates = safe_mapping(nav.get("candidates"))
    turn = safe_mapping(candidates.get("candidateTurnRate"))
    promoted = safe_mapping(candidates.get("promotedCoordinate"))
    facing = safe_mapping(candidates.get("candidateFacingTarget"))
    if (turn.get("offset") or REQUIRED_OFFSET) != REQUIRED_OFFSET:
        blockers.append(f"turn-rate-offset-mismatch:{turn.get('offset')}")
    if turn.get("promotionAllowed"):
        blockers.append("turn-rate-promotion-unexpectedly-allowed")
    if not math.isfinite(float(turn.get("latestValue", 0.0))):
        blockers.append("turn-rate-latest-value-not-finite")
    if not promoted.get("promotionAllowed"):
        blockers.append("promoted-coordinate-not-allowed-in-navigation-summary")
    if not facing.get("promotionAllowed"):
        blockers.append("promoted-facing-yaw-required-for-turn-rate-review")
    return {
        "status": turn.get("status"),
        "candidateOnly": bool(turn.get("candidateOnly", True)),
        "promotionAllowed": bool(turn.get("promotionAllowed")),
        "chainExpression": turn.get("chainShape") or REQUIRED_CHAIN,
        "offset": turn.get("offset") or REQUIRED_OFFSET,
        "latestValue": turn.get("latestValue"),
        "latestClassification": turn.get("latestClassification"),
        "coordinateResolverStatus": promoted.get("status"),
        "facingYawStatus": facing.get("status"),
        "target": nav.get("target"),
        "evidence": turn.get("evidence") or {},
    }


def validate_turn_summary(summary: Mapping[str, Any] | None, *, expected_direction: str, blockers: list[str]) -> dict[str, Any]:
    if not summary:
        return {"passed": False, "direction": expected_direction}
    if summary.get("kind") != "static-owner-turn-stimulus-capture":
        blockers.append(f"{expected_direction}-turn-kind-unexpected:{summary.get('kind')}")
    if summary.get("status") != "passed":
        blockers.append(f"{expected_direction}-turn-status-not-passed:{summary.get('status')}")
    analysis = safe_mapping(summary.get("analysis"))
    if analysis.get("direction") != expected_direction:
        blockers.append(f"{expected_direction}-turn-direction-mismatch:{analysis.get('direction')}")
    if analysis.get("status") != "passed":
        blockers.append(f"{expected_direction}-turn-analysis-not-passed:{analysis.get('status')}")
    if analysis.get("absoluteYawDeltaDegrees") is None:
        blockers.append(f"{expected_direction}-turn-yaw-delta-missing")
    if analysis.get("turnRateSignMatchedDirection") is not True:
        blockers.append(f"{expected_direction}-turn-rate-sign-proof-missing")
    turn_rate_delta = None
    try:
        turn_rate_delta = float(analysis.get("turnRateDelta"))
    except (TypeError, ValueError):
        blockers.append(f"{expected_direction}-turn-rate-delta-proof-missing")
    if turn_rate_delta is not None and (not math.isfinite(turn_rate_delta) or abs(turn_rate_delta) < DEFAULT_MIN_TURN_RATE_DELTA_ABS):
        blockers.append(f"{expected_direction}-turn-rate-delta-proof-too-small:{turn_rate_delta}")
    return {
        "passed": summary.get("status") == "passed"
        and analysis.get("turnRateSignMatchedDirection") is True
        and turn_rate_delta is not None
        and math.isfinite(turn_rate_delta)
        and abs(turn_rate_delta) >= DEFAULT_MIN_TURN_RATE_DELTA_ABS,
        "direction": expected_direction,
        "summaryJson": safe_mapping(summary.get("artifacts")).get("summaryJson"),
        "signedYawDeltaDegrees": analysis.get("signedYawDeltaDegrees"),
        "turnRateDelta": analysis.get("turnRateDelta"),
        "minimumTurnRateDeltaAbs": DEFAULT_MIN_TURN_RATE_DELTA_ABS,
        "turnRateSignMatchedDirection": analysis.get("turnRateSignMatchedDirection"),
    }


def validate_static_evidence(paths: list[Path], blockers: list[str]) -> dict[str, Any]:
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths if path and path.is_file())
    contains_root = "0x32EBC80" in text or "32EBC80" in text
    contains_turn = "0x304" in text
    if not contains_root:
        blockers.append("static-evidence-missing-root-0x32EBC80")
    if not contains_turn:
        blockers.append("static-evidence-missing-turn-rate-0x304")
    return {
        "passed": contains_root and contains_turn,
        "containsRootRva": contains_root,
        "containsTurnRateOffset": contains_turn,
        "promotionAllowed": False,
    }


def build_review_packet(args: argparse.Namespace, root: Path, run_dir: Path) -> tuple[dict[str, Any], int]:
    blockers: list[str] = []
    warnings: list[str] = ["report-only-no-live-input-sent", "turn-rate-candidate-only-no-promotion"]
    errors: list[str] = []

    nav_path = resolve_under_repo(root, args.navigation_summary_json or DEFAULT_NAVIGATION_SUMMARY)
    left_path = resolve_under_repo(root, args.left_turn_summary_json)
    right_path = resolve_under_repo(root, args.right_turn_summary_json)
    static_paths = [
        path
        for path in [
            resolve_under_repo(root, args.static_source_site_md),
            resolve_under_repo(root, args.static_pointer_evidence_md),
        ]
        if path is not None
    ]

    nav = load_optional_input(root, nav_path, label="navigation", blockers=blockers, errors=errors)
    left = load_optional_input(root, left_path, label="left-turn", blockers=blockers, errors=errors)
    right = load_optional_input(root, right_path, label="right-turn", blockers=blockers, errors=errors)

    candidate = validate_navigation(nav, blockers)
    left_gate = validate_turn_summary(left, expected_direction="left", blockers=blockers)
    right_gate = validate_turn_summary(right, expected_direction="right", blockers=blockers)
    static_gate = validate_static_evidence(static_paths, blockers) if static_paths else {"passed": False}
    if not static_paths:
        blockers.append("static-evidence-path-required")

    source_safety = source_safety_summary([item for item in [nav, left, right] if item])
    for forbidden in ("targetMemoryBytesWritten", "proofPromotion", "actorChainPromotion", "facingPromotion", "providerWrites"):
        if source_safety.get(forbidden):
            blockers.append(f"source-safety-forbidden-{forbidden}")

    review_passed = not blockers and not errors
    status = "failed" if errors else ("passed" if review_passed else "blocked")
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "turn-rate-promotion-readiness-review-packet",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": "candidate-turn-rate-review-ready-for-explicit-promotion-gate" if review_passed else "candidate-turn-rate-review-not-ready",
        "repoRoot": str(root),
        "inputs": {
            "navigationSummaryJson": repo_rel(root, nav_path),
            "leftTurnSummaryJson": repo_rel(root, left_path),
            "rightTurnSummaryJson": repo_rel(root, right_path),
            "staticEvidence": [repo_rel(root, path) for path in static_paths],
        },
        "target": candidate.get("target") or {},
        "candidate": candidate,
        "reviewGates": {
            "coordinateResolverCurrent": {"passed": bool(candidate.get("coordinateResolverStatus"))},
            "facingYawCurrent": {"passed": str(candidate.get("facingYawStatus") or "").startswith("promoted-")},
            "candidateTurnRateReadback": {"passed": bool(candidate) and candidate.get("offset") == REQUIRED_OFFSET},
            "leftTurnSign": left_gate,
            "rightTurnSign": right_gate,
            "leftRightSignFlip": {"passed": bool(left_gate.get("passed") and right_gate.get("passed"))},
            "staticRootSourceSiteEvidence": static_gate,
        },
        "promotionDecision": {
            "reviewPassed": review_passed,
            "candidateOnly": True,
            "promotionAllowed": False,
            "promotionPerformed": False,
            "explicitPromotionGateRequired": True,
            "freshPrePromotionReadbackRequired": True,
            "recommendedPromotionState": "review-passed-awaiting-explicit-promotion-gate-and-fresh-readback"
            if review_passed
            else "blocked-keep-turn-rate-candidate-only",
        },
        "sourceSafety": source_safety,
        "safety": base_safety() | {"turnRatePromotion": False, "currentTruthWrite": False},
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
        "next": {
            "recommendedAction": "Resolve blockers and keep owner+0x304 candidate-only until both left/right turn-rate sign proofs and static evidence pass.",
            "recommendedActions": [
                "Run explicit left and right turn-stimulus captures that record turn-rate sign during/around the turn.",
                "Refresh exact-target coordinate/nav/API readbacks immediately before any apply gate.",
                "Run the separate turn-rate promotion apply helper only after this review passes.",
            ],
        },
    }
    return summary, 0 if status == "passed" else 2 if status == "blocked" else 1


def build_markdown(summary: Mapping[str, Any]) -> str:
    decision = safe_mapping(summary.get("promotionDecision"))
    lines = [
        "# Turn-rate promotion-readiness review packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Promotion allowed: `{decision.get('promotionAllowed')}`",
        f"- Promotion performed: `{decision.get('promotionPerformed')}`",
        "",
        "## Gates",
        "",
    ]
    for name, gate in safe_mapping(summary.get("reviewGates")).items():
        lines.append(f"- `{name}`: `{safe_mapping(gate).get('passed')}`")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- `{item}`" for item in safe_list(summary.get("blockers")) or ["none"])
    lines.extend(["", "## Next", ""])
    for item in safe_list(safe_mapping(summary.get("next")).get("recommendedActions")):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(summary: dict[str, Any]) -> None:
    artifacts = safe_mapping(summary.get("artifacts"))
    summary_json = Path(str(artifacts["summaryJson"]))
    summary_md = Path(str(artifacts["summaryMarkdown"]))
    write_json(summary_json, summary)
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text(build_markdown(summary), encoding="utf-8")


def run_self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_name:
        root = Path(temp_name)
        nav = root / DEFAULT_NAVIGATION_SUMMARY
        left = root / "scripts" / "captures" / "left" / "summary.json"
        right = root / "scripts" / "captures" / "right" / "summary.json"
        static_doc = root / "docs" / "static.md"
        target = {"processId": 1, "targetWindowHandle": "0x1", "processStartUtc": "2026-06-01T00:00:00Z"}
        write_json(
            nav,
            {
                "kind": "riftreader-navigation-pointer-discovery-status",
                "status": "passed",
                "target": target,
                "candidates": {
                    "promotedCoordinate": {"promotionAllowed": True, "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed"},
                    "candidateFacingTarget": {"promotionAllowed": True, "status": "promoted-static-owner-facing-yaw-current-pid-readback-passed"},
                    "candidateTurnRate": {"status": "candidate-only", "candidateOnly": True, "promotionAllowed": False, "offset": "0x304", "latestValue": 0.0, "latestClassification": "stationary"},
                },
            },
        )
        for path, direction, delta in ((left, "left", -10.0), (right, "right", 10.0)):
            write_json(
                path,
                {
                    "kind": "static-owner-turn-stimulus-capture",
                    "status": "passed",
                    "analysis": {
                        "status": "passed",
                        "direction": direction,
                        "absoluteYawDeltaDegrees": abs(delta),
                        "signedYawDeltaDegrees": delta,
                        "turnRateSignMatchedDirection": True,
                        "turnRateDelta": 1.0 if direction == "left" else -1.0,
                    },
                    "safety": {"movementSent": True, "inputSent": True, "targetMemoryBytesWritten": False},
                    "artifacts": {"summaryJson": str(path)},
                },
            )
        static_doc.parent.mkdir(parents=True, exist_ok=True)
        static_doc.write_text("root 0x32EBC80 turn rate 0x304 source site", encoding="utf-8")
        args = argparse.Namespace(
            navigation_summary_json=nav,
            left_turn_summary_json=left,
            right_turn_summary_json=right,
            static_source_site_md=static_doc,
            static_pointer_evidence_md=None,
        )
        summary, exit_code = build_review_packet(args, root, root / "scripts" / "captures" / f"{READINESS_PREFIX}selftest")
    return {
        "kind": "turn-rate-promotion-readiness-review-self-test",
        "status": "passed" if exit_code == 0 and summary["promotionDecision"]["reviewPassed"] else "failed",
        "checks": {
            "reviewPassed": summary["promotionDecision"]["reviewPassed"],
            "promotionAllowed": summary["promotionDecision"]["promotionAllowed"],
            "helperInputSent": summary["safety"]["inputSent"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--navigation-summary-json", default=str(DEFAULT_NAVIGATION_SUMMARY))
    parser.add_argument("--left-turn-summary-json")
    parser.add_argument("--right-turn-summary-json")
    parser.add_argument("--static-source-site-md")
    parser.add_argument("--static-pointer-evidence-md")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        result = run_self_test()
        print(json.dumps(result) if args.json else json.dumps(result, indent=2))
        return 0 if result.get("status") == "passed" else 1

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    run_dir = (root / args.output_root) / f"{READINESS_PREFIX}{datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')}"
    summary, exit_code = build_review_packet(args, root, run_dir)
    write_outputs(summary)
    compact = {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "summaryJson": safe_mapping(summary.get("artifacts")).get("summaryJson"),
        "summaryMarkdown": safe_mapping(summary.get("artifacts")).get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }
    print(json.dumps(compact) if args.json else json.dumps(compact, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
