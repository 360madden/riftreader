#!/usr/bin/env python3
"""Build a report-only candidate-facing promotion-readiness review packet.

This helper consumes existing navigation/gate/static evidence and writes a
durable JSON/Markdown review packet.  It does not send live input, read target
memory, restart RIFT, attach debuggers, write providers, update current truth,
mutate Git, or promote candidate facing truth.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
REQUIRED_FACING_OFFSET = "0x30C"
REQUIRED_FACING_CHAIN = "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314"
DEFAULT_NAVIGATION_SUMMARY = Path(".riftreader-local") / "navigation-pointer-discovery" / "latest" / "summary.json"
DEFAULT_STATIC_SOURCE_SITE_MD = Path("docs") / "recovery" / "ghidra-facing-coordinate-source-site-review-2026-06-01.md"
DEFAULT_STATIC_POINTER_EVIDENCE_MD = Path("docs") / "recovery" / "ghidra-static-pointer-evidence-2026-06-01.md"
DEFAULT_OUTPUT_ROOT = Path("scripts") / "captures"
CAPTURE_ROOT = Path("scripts") / "captures"


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_under_repo(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def repo_rel(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


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


def latest_summary_by_prefix(root: Path, prefix: str, expected_kind: str) -> Path | None:
    capture_root = root / CAPTURE_ROOT
    if not capture_root.is_dir():
        return None
    candidates: list[tuple[datetime, Path]] = []
    for path in capture_root.glob(f"{prefix}-*/summary.json"):
        if not path.is_file():
            continue
        try:
            payload = load_json_object(path)
        except Exception:
            continue
        if payload.get("kind") != expected_kind:
            continue
        generated = parse_iso(payload.get("generatedAtUtc")) or datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        candidates.append((generated, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1].stat().st_mtime_ns))[1]


def load_input(root: Path, path: Path | None, *, label: str, expected_kind: str | None, blockers: list[str], errors: list[str]) -> dict[str, Any] | None:
    if path is None:
        blockers.append(f"{label}-summary-json-not-found")
        return None
    if not path.is_file():
        blockers.append(f"{label}-summary-json-not-found:{path}")
        return None
    try:
        payload = load_json_object(path)
    except Exception as exc:  # noqa: BLE001 - packet must capture malformed evidence.
        errors.append(f"{label}-summary-json-malformed:{repo_rel(root, path)}:{type(exc).__name__}:{exc}")
        return None
    if expected_kind and payload.get("kind") != expected_kind:
        blockers.append(f"{label}-kind-mismatch:{payload.get('kind')}")
    return payload


def source_safety_summary(sources: list[Mapping[str, Any]]) -> dict[str, Any]:
    summary = {
        "movementSent": False,
        "inputSent": False,
        "targetMemoryBytesRead": False,
        "targetMemoryBytesWritten": False,
        "proofPromotion": False,
        "actorChainPromotion": False,
        "facingPromotion": False,
        "providerWrites": False,
        "navigationControl": False,
    }
    for source in sources:
        safety = safe_mapping(source.get("safety"))
        source_safety = safe_mapping(source.get("sourceSafety"))
        for key in summary:
            summary[key] = bool(summary[key]) or bool(safety.get(key)) or bool(source_safety.get(key))
    return summary


def validate_navigation(nav: Mapping[str, Any] | None, blockers: list[str]) -> dict[str, Any]:
    if not nav:
        return {}
    if nav.get("status") != "passed":
        blockers.append(f"navigation-summary-status-not-passed:{nav.get('status')}")
    candidates = safe_mapping(nav.get("candidates"))
    facing = safe_mapping(candidates.get("candidateFacingTarget"))
    promoted = safe_mapping(candidates.get("promotedCoordinate"))
    proof_gates = safe_mapping(nav.get("proofGates"))
    if facing.get("status") != "candidate-only":
        blockers.append(f"candidate-facing-status-not-candidate-only:{facing.get('status')}")
    if facing.get("offset") != REQUIRED_FACING_OFFSET:
        blockers.append(f"candidate-facing-offset-mismatch:{facing.get('offset')}")
    if facing.get("promotionAllowed"):
        blockers.append("candidate-facing-promotion-unexpectedly-allowed")
    if not promoted.get("promotionAllowed"):
        blockers.append("promoted-coordinate-not-allowed-in-navigation-summary")
    return {
        "status": facing.get("status"),
        "chainExpression": facing.get("chainShape") or REQUIRED_FACING_CHAIN,
        "offset": facing.get("offset"),
        "latestYawDegrees": facing.get("latestYawDegrees"),
        "planarLookaheadDistance": facing.get("planarLookaheadDistance"),
        "promotionAllowed": bool(facing.get("promotionAllowed")),
        "candidateOnly": bool(facing.get("candidateOnly", True)),
        "coordinateResolverStatus": promoted.get("status"),
        "coordinateResolverChain": promoted.get("chain"),
        "apiNowStatus": promoted.get("apiNowStatus"),
        "proofGateStatuses": {
            "facingThreePoseGate": safe_mapping(proof_gates.get("facingThreePoseGate")).get("status"),
            "facingRestartSurvival": safe_mapping(proof_gates.get("facingRestartSurvival")).get("status"),
            "turnForwardExperiment": safe_mapping(proof_gates.get("turnForwardExperiment")).get("status"),
        },
    }


def validate_three_pose(gate: Mapping[str, Any] | None, blockers: list[str]) -> dict[str, Any]:
    if not gate:
        return {}
    analysis = safe_mapping(gate.get("analysis"))
    if gate.get("status") != "passed":
        blockers.append(f"three-pose-gate-status-not-passed:{gate.get('status')}")
    if analysis.get("formalThreePoseGatePassed") is not True:
        blockers.append("formal-three-pose-gate-not-passed")
    if analysis.get("promotionAllowed"):
        blockers.append("three-pose-gate-unexpectedly-allows-promotion")
    return {
        "status": gate.get("status"),
        "verdict": gate.get("verdict"),
        "formalThreePoseGatePassed": bool(analysis.get("formalThreePoseGatePassed")),
        "poseCount": gate.get("poseCount"),
        "passedPoseCount": gate.get("passedPoseCount"),
        "aggregateProgressDistance": analysis.get("aggregateProgressDistance"),
        "minimumProgressDistance": analysis.get("minimumProgressDistance"),
        "promotionAllowed": bool(analysis.get("promotionAllowed")),
        "sourceMovementSent": bool(safe_mapping(gate.get("sourceSafety")).get("movementSent")),
        "sourceInputSent": bool(safe_mapping(gate.get("sourceSafety")).get("inputSent")),
    }


def validate_restart_survival(packet: Mapping[str, Any] | None, blockers: list[str]) -> dict[str, Any]:
    if not packet:
        return {}
    analysis = safe_mapping(packet.get("analysis"))
    if packet.get("status") != "passed":
        blockers.append(f"restart-survival-status-not-passed:{packet.get('status')}")
    if analysis.get("restartRelogSurvived") is not True:
        blockers.append("restart-relog-survival-not-passed")
    if analysis.get("promotionAllowed"):
        blockers.append("restart-survival-unexpectedly-allows-promotion")
    return {
        "status": packet.get("status"),
        "verdict": packet.get("verdict"),
        "restartRelogSurvived": bool(analysis.get("restartRelogSurvived")),
        "offsetsStable": bool(analysis.get("offsetsStable")),
        "processStartChanged": bool(analysis.get("processStartChanged")),
        "ownerAddressChanged": bool(analysis.get("ownerAddressChanged")),
        "facingTargetOffset": analysis.get("facingTargetOffset"),
        "promotionAllowed": bool(analysis.get("promotionAllowed")),
        "sourceTargetMemoryBytesRead": bool(safe_mapping(packet.get("sourceSafety")).get("targetMemoryBytesRead")),
    }


def validate_turn_forward(experiment: Mapping[str, Any] | None, blockers: list[str]) -> dict[str, Any]:
    if not experiment:
        return {}
    forward = safe_mapping(experiment.get("forwardResult"))
    operator = safe_mapping(experiment.get("operator"))
    if experiment.get("status") != "passed":
        blockers.append(f"turn-forward-status-not-passed:{experiment.get('status')}")
    if experiment.get("verdict") != "turn-forward-live-progress-validated":
        blockers.append(f"turn-forward-verdict-unexpected:{experiment.get('verdict')}")
    if forward.get("routeStatus") not in {"progress", "arrived"}:
        blockers.append(f"turn-forward-route-status-unexpected:{forward.get('routeStatus')}")
    return {
        "status": experiment.get("status"),
        "verdict": experiment.get("verdict"),
        "routeStatus": forward.get("routeStatus"),
        "totalProgressDistance": forward.get("totalProgressDistance"),
        "movementApproved": bool(operator.get("movementApproved")),
        "turnApproved": bool(operator.get("turnApproved")),
        "sourceMovementSent": bool(safe_mapping(experiment.get("safety")).get("movementSent")),
        "sourceInputSent": bool(safe_mapping(experiment.get("safety")).get("inputSent")),
        "promotionAllowed": False,
    }


def validate_static_evidence(root: Path, paths: list[Path], blockers: list[str], warnings: list[str]) -> dict[str, Any]:
    required_tokens = ["0x32EBC80", "0x30C", "0x310", "0x314", "0x320", "0x324", "0x328"]
    docs: list[dict[str, Any]] = []
    combined = ""
    for path in paths:
        if not path.is_file():
            blockers.append(f"static-evidence-doc-not-found:{path}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        combined += "\n" + text
        docs.append(
            {
                "path": repo_rel(root, path),
                "containsRootRva": "0x32EBC80" in text,
                "containsCandidateFacingOffsets": all(token in text for token in ["0x30C", "0x310", "0x314"]),
                "containsPromotedCoordinateOffsets": all(token in text for token in ["0x320", "0x324", "0x328"]),
                "promotionPerformedFalse": "Promotion performed | `false`" in text or "promotion" in text.lower(),
            }
        )
    for token in required_tokens:
        if token not in combined:
            blockers.append(f"static-evidence-token-missing:{token}")
    if "supporting evidence only" not in combined.lower():
        warnings.append("static-evidence-does-not-state-supporting-only-boundary")
    return {
        "status": "present" if docs and not any(item.startswith("static-evidence-token-missing") for item in blockers) else "blocked",
        "docs": docs,
        "requiredTokens": required_tokens,
        "promotionAllowed": False,
    }


def build_review_packet(args: argparse.Namespace, root: Path, run_dir: Path) -> tuple[dict[str, Any], int]:
    blockers: list[str] = []
    warnings: list[str] = ["report-only-no-live-input-sent", "candidate-facing-target-only-no-promotion"]
    errors: list[str] = []
    nav_path = resolve_under_repo(root, args.navigation_summary_json)
    three_pose_path = resolve_under_repo(root, args.three_pose_gate_summary_json) or latest_summary_by_prefix(
        root, "facing-target-three-pose-gate", "facing-target-three-pose-gate"
    )
    restart_path = resolve_under_repo(root, args.restart_survival_summary_json) or latest_summary_by_prefix(
        root, "facing-target-restart-survival-packet", "facing-target-restart-survival-packet"
    )
    turn_forward_path = resolve_under_repo(root, args.turn_forward_summary_json) or latest_summary_by_prefix(
        root, "static-owner-turn-forward-experiment", "static-owner-turn-forward-experiment"
    )
    static_paths = [
        item
        for item in [
            resolve_under_repo(root, args.static_source_site_md),
            resolve_under_repo(root, args.static_pointer_evidence_md),
        ]
        if item is not None
    ]

    nav = load_input(
        root,
        nav_path,
        label="navigation",
        expected_kind="riftreader-navigation-pointer-discovery-status",
        blockers=blockers,
        errors=errors,
    )
    three_pose = load_input(
        root,
        three_pose_path,
        label="three-pose-gate",
        expected_kind="facing-target-three-pose-gate",
        blockers=blockers,
        errors=errors,
    )
    restart = load_input(
        root,
        restart_path,
        label="restart-survival",
        expected_kind="facing-target-restart-survival-packet",
        blockers=blockers,
        errors=errors,
    )
    turn_forward = load_input(
        root,
        turn_forward_path,
        label="turn-forward",
        expected_kind="static-owner-turn-forward-experiment",
        blockers=blockers,
        errors=errors,
    )

    candidate = validate_navigation(nav, blockers)
    three_pose_review = validate_three_pose(three_pose, blockers)
    restart_review = validate_restart_survival(restart, blockers)
    turn_forward_review = validate_turn_forward(turn_forward, blockers)
    static_review = validate_static_evidence(root, static_paths, blockers, warnings)
    source_safety = source_safety_summary([item for item in [nav, three_pose, restart, turn_forward] if item])
    for forbidden in ("targetMemoryBytesWritten", "proofPromotion", "actorChainPromotion", "facingPromotion", "providerWrites"):
        if source_safety.get(forbidden):
            blockers.append(f"source-forbidden-safety-flag:{forbidden}")

    exit_code = 1 if errors else 2 if blockers else 0
    review_passed = exit_code == 0
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "facing-target-promotion-readiness-review-packet",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if review_passed else "failed" if errors else "blocked",
        "verdict": (
            "candidate-facing-review-ready-for-explicit-promotion-gate"
            if review_passed
            else "candidate-facing-review-not-ready"
        ),
        "repoRoot": str(root),
        "runDirectory": str(run_dir),
        "inputs": {
            "navigationSummaryJson": repo_rel(root, nav_path),
            "threePoseGateSummaryJson": repo_rel(root, three_pose_path),
            "restartSurvivalSummaryJson": repo_rel(root, restart_path),
            "turnForwardSummaryJson": repo_rel(root, turn_forward_path),
            "staticEvidenceDocs": [repo_rel(root, path) for path in static_paths],
        },
        "target": safe_mapping(nav.get("target")) if nav else {},
        "candidate": candidate,
        "reviewGates": {
            "coordinateResolverCurrent": {
                "status": candidate.get("coordinateResolverStatus"),
                "chain": candidate.get("coordinateResolverChain"),
                "apiNowStatus": candidate.get("apiNowStatus"),
                "passed": bool(candidate.get("coordinateResolverStatus")) and str(candidate.get("apiNowStatus") or "").startswith("passed-"),
            },
            "candidateFacingReadback": {
                "status": candidate.get("status"),
                "chainExpression": candidate.get("chainExpression"),
                "offset": candidate.get("offset"),
                "candidateOnly": candidate.get("candidateOnly"),
                "passed": candidate.get("status") == "candidate-only" and candidate.get("offset") == REQUIRED_FACING_OFFSET,
            },
            "threePoseRouteProgress": {**three_pose_review, "passed": bool(three_pose_review.get("formalThreePoseGatePassed"))},
            "restartRelogSurvival": {**restart_review, "passed": bool(restart_review.get("restartRelogSurvived"))},
            "turnForwardProgress": {**turn_forward_review, "passed": turn_forward_review.get("routeStatus") in {"progress", "arrived"}},
            "staticRootSourceSiteEvidence": {**static_review, "passed": static_review.get("status") == "present"},
        },
        "promotionDecision": {
            "candidateOnly": True,
            "reviewPassed": review_passed,
            "promotionAllowed": False,
            "promotionPerformed": False,
            "explicitPromotionGateRequired": True,
            "freshPrePromotionReadbackRequired": True,
            "currentTruthWritePerformed": False,
            "recommendedPromotionState": (
                "review-passed-awaiting-explicit-promotion-gate-and-fresh-readback"
                if review_passed
                else "blocked-review-inputs-incomplete-or-failed"
            ),
        },
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": errors,
        "safety": {
            **base_safety(),
            "reportOnly": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "currentTruthWrite": False,
        },
        "sourceSafety": source_safety,
        "artifacts": {
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
        "next": {
            "recommendedAction": (
                "Refresh exact-target static/nav/API readbacks, then run a separate explicit promotion gate only if approved."
                if review_passed
                else "Resolve review blockers, regenerate supporting packets, and keep candidate-facing truth unpromoted."
            ),
            "recommendedActions": [
                "Refresh exact-target static-owner coordinate/nav-state readbacks before any promotion gate.",
                "Capture fresh API-now versus chain-now agreement for the current PID/HWND.",
                "Run a separate explicit promotion gate only after reviewing this packet; this helper never promotes.",
            ],
        },
    }
    return summary, exit_code


def build_markdown(summary: Mapping[str, Any]) -> str:
    decision = safe_mapping(summary.get("promotionDecision"))
    lines = [
        "# Candidate-facing promotion-readiness review packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Promotion allowed: `{decision.get('promotionAllowed')}`",
        f"- Promotion performed: `{decision.get('promotionPerformed')}`",
        f"- Explicit promotion gate required: `{decision.get('explicitPromotionGateRequired')}`",
        "",
        "## Review gates",
        "",
        "| Gate | Passed | Status | Detail |",
        "|---|---:|---|---|",
    ]
    for name, gate in safe_mapping(summary.get("reviewGates")).items():
        gate_map = safe_mapping(gate)
        detail = gate_map.get("verdict") or gate_map.get("chain") or gate_map.get("chainExpression") or gate_map.get("offset")
        lines.append(f"| `{name}` | `{gate_map.get('passed')}` | `{gate_map.get('status')}` | `{detail}` |")
    lines.extend(["", "## Inputs", ""])
    for key, value in safe_mapping(summary.get("inputs")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Blockers", ""])
    for item in safe_list(summary.get("blockers")) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Warnings", ""])
    for item in safe_list(summary.get("warnings")) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Safety", "", "| Flag | Value |", "|---|---:|"])
    for key, value in safe_mapping(summary.get("safety")).items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Source safety", "", "| Flag | Value |", "|---|---:|"])
    for key, value in safe_mapping(summary.get("sourceSafety")).items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Next", ""])
    for item in safe_list(safe_mapping(summary.get("next")).get("recommendedActions")):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(summary: dict[str, Any]) -> None:
    artifacts = safe_mapping(summary.get("artifacts"))
    summary_json = Path(str(artifacts.get("summaryJson")))
    summary_md = Path(str(artifacts.get("summaryMarkdown")))
    write_json(summary_json, summary)
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text(build_markdown(summary), encoding="utf-8")


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    decision = safe_mapping(summary.get("promotionDecision"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "reviewPassed": decision.get("reviewPassed"),
        "promotionAllowed": decision.get("promotionAllowed"),
        "promotionPerformed": decision.get("promotionPerformed"),
        "explicitPromotionGateRequired": decision.get("explicitPromotionGateRequired"),
        "freshPrePromotionReadbackRequired": decision.get("freshPrePromotionReadbackRequired"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
        "safety": summary.get("safety", {}),
        "sourceSafety": summary.get("sourceSafety", {}),
        "next": summary.get("next", {}),
    }


def self_test_payload() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_name:
        root = Path(temp_name)
        nav_path = root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.json"
        three_path = root / "scripts" / "captures" / "facing-target-three-pose-gate-test" / "summary.json"
        restart_path = root / "scripts" / "captures" / "facing-target-restart-survival-packet-test" / "summary.json"
        turn_path = root / "scripts" / "captures" / "static-owner-turn-forward-experiment-test" / "summary.json"
        source_doc = root / "docs" / "recovery" / "source.md"
        pointer_doc = root / "docs" / "recovery" / "pointer.md"
        write_json(
            nav_path,
            {
                "kind": "riftreader-navigation-pointer-discovery-status",
                "status": "passed",
                "target": {"processId": 1, "targetWindowHandle": "0x1"},
                "candidates": {
                    "promotedCoordinate": {
                        "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed",
                        "promotionAllowed": True,
                        "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                        "apiNowStatus": "passed-current-pid-1-api-now-vs-chain-now",
                    },
                    "candidateFacingTarget": {
                        "status": "candidate-only",
                        "candidateOnly": True,
                        "promotionAllowed": False,
                        "chainShape": REQUIRED_FACING_CHAIN,
                        "offset": REQUIRED_FACING_OFFSET,
                    },
                },
                "proofGates": {},
            },
        )
        write_json(
            three_path,
            {
                "kind": "facing-target-three-pose-gate",
                "status": "passed",
                "verdict": "formal-three-pose-route-progress-gate-passed",
                "poseCount": 3,
                "passedPoseCount": 3,
                "analysis": {"formalThreePoseGatePassed": True, "promotionAllowed": False},
                "sourceSafety": {"movementSent": True, "inputSent": True},
                "safety": {"movementSent": False, "inputSent": False},
            },
        )
        write_json(
            restart_path,
            {
                "kind": "facing-target-restart-survival-packet",
                "status": "passed",
                "verdict": "candidate-facing-target-restart-relog-survival-passed",
                "analysis": {
                    "restartRelogSurvived": True,
                    "offsetsStable": True,
                    "processStartChanged": True,
                    "ownerAddressChanged": True,
                    "facingTargetOffset": REQUIRED_FACING_OFFSET,
                    "promotionAllowed": False,
                },
                "sourceSafety": {"targetMemoryBytesRead": True},
                "safety": {"movementSent": False, "inputSent": False},
            },
        )
        write_json(
            turn_path,
            {
                "kind": "static-owner-turn-forward-experiment",
                "status": "passed",
                "verdict": "turn-forward-live-progress-validated",
                "operator": {"movementApproved": True, "turnApproved": True},
                "forwardResult": {"routeStatus": "progress", "totalProgressDistance": 1.5},
                "safety": {"movementSent": True, "inputSent": True},
            },
        )
        source_text = "supporting evidence only 0x32EBC80 0x30C 0x310 0x314 0x320 0x324 0x328 Promotion performed | `false`"
        source_doc.parent.mkdir(parents=True, exist_ok=True)
        source_doc.write_text(source_text, encoding="utf-8")
        pointer_doc.write_text(source_text, encoding="utf-8")
        args = argparse.Namespace(
            navigation_summary_json=str(nav_path),
            three_pose_gate_summary_json=str(three_path),
            restart_survival_summary_json=str(restart_path),
            turn_forward_summary_json=str(turn_path),
            static_source_site_md=str(source_doc),
            static_pointer_evidence_md=str(pointer_doc),
        )
        summary, _ = build_review_packet(args, root, root / "scripts" / "captures" / "review")
    return {
        "status": "passed" if summary.get("status") == "passed" else "failed",
        "checks": {
            "reviewPassed": safe_mapping(summary.get("promotionDecision")).get("reviewPassed"),
            "promotionAllowed": safe_mapping(summary.get("promotionDecision")).get("promotionAllowed"),
            "promotionPerformed": safe_mapping(summary.get("promotionDecision")).get("promotionPerformed"),
            "helperInputSent": safe_mapping(summary.get("safety")).get("inputSent"),
        },
        "safety": summary.get("safety", {}),
        "sourceSafety": summary.get("sourceSafety", {}),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--navigation-summary-json", default=DEFAULT_NAVIGATION_SUMMARY)
    parser.add_argument("--three-pose-gate-summary-json", default=None)
    parser.add_argument("--restart-survival-summary-json", default=None)
    parser.add_argument("--turn-forward-summary-json", default=None)
    parser.add_argument("--static-source-site-md", default=DEFAULT_STATIC_SOURCE_SITE_MD)
    parser.add_argument("--static-pointer-evidence-md", default=DEFAULT_STATIC_POINTER_EVIDENCE_MD)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        payload = self_test_payload()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"self-test:{payload['status']}")
        return 0 if payload.get("status") == "passed" else 1
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = resolve_under_repo(root, Path(args.output_root))
    assert output_root is not None
    run_dir = output_root / f"facing-target-promotion-readiness-review-{utc_stamp()}"
    summary, exit_code = build_review_packet(args, root, run_dir)
    write_outputs(summary)
    if args.json:
        print(json.dumps(compact(summary), indent=2))
    else:
        print(f"{summary['status']}: {safe_mapping(summary.get('artifacts')).get('summaryMarkdown')}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
