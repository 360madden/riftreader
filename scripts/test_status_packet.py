#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import status_packet  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


class StatusPacketProofFreshnessTests(unittest.TestCase):
    def test_latest_current_truth_refresh_plan_reads_dry_run_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_json(
                root / ".riftreader-local" / "current-truth-refresh-plan" / "latest" / "summary.json",
                {
                    "schemaVersion": 1,
                    "kind": "riftreader-current-truth-refresh-plan",
                    "generatedAtUtc": "2026-05-31T15:38:15Z",
                    "status": "passed",
                    "verdict": "dry-run-current-truth-refresh-plan-ready",
                    "updateCount": 9,
                    "blockers": [],
                    "warnings": ["current-truth-staticOwnerFacing-already-promoted-dashboard-candidate-only-plan-does-not-change-it"],
                    "errors": [],
                    "artifacts": {
                        "summaryJson": ".riftreader-local/current-truth-refresh-plan/latest/summary.json",
                        "summaryMarkdown": ".riftreader-local/current-truth-refresh-plan/latest/summary.md",
                        "proposedCurrentTruthJson": ".riftreader-local/current-truth-refresh-plan/latest/proposed-current-truth.json",
                        "proposedCurrentTruthDiff": ".riftreader-local/current-truth-refresh-plan/latest/proposed-current-truth.diff",
                    },
                    "next": {
                        "recommendedAction": "Review ignored artifacts.",
                        "requiresExplicitApprovalForApply": True,
                    },
                    "safety": {
                        "dryRunOnly": True,
                        "trackedTruthWritten": False,
                        "movementSent": False,
                        "inputSent": False,
                        "targetMemoryBytesRead": False,
                        "targetMemoryBytesWritten": False,
                        "proofPromotion": False,
                        "actorChainPromotion": False,
                        "facingPromotion": False,
                        "gitMutation": False,
                    },
                },
            )

            summary = status_packet.latest_current_truth_refresh_plan(root)

        self.assertEqual("passed", summary["status"])
        self.assertEqual(9, summary["updateCount"])
        self.assertTrue(summary["requiresExplicitApprovalForApply"])
        self.assertIn("proposed-current-truth.diff", summary["proposedCurrentTruthDiff"])
        self.assertFalse(summary["safety"]["trackedTruthWritten"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["proofPromotion"])

    def test_current_truth_refresh_plan_parse_error_stays_inside_compact_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(
                root / ".riftreader-local" / "current-truth-refresh-plan" / "latest" / "summary.json",
                "{bad",
            )

            packet = status_packet.build_status_packet(
                root,
                run_coordinate_status=False,
                check_opencode=False,
                collect_git_state=False,
            )
            compact = status_packet.compact_summary(packet)

        plan = compact["currentTruthRefreshPlan"]
        self.assertEqual("passed", packet["status"])
        self.assertEqual("parse-error", plan["status"])
        self.assertIn("current-truth-refresh-plan-summary-unusable", plan["blockers"])
        self.assertFalse(plan["safety"]["trackedTruthWritten"])
        self.assertFalse(plan["safety"]["proofPromotion"])

    def test_latest_current_truth_refresh_apply_reads_apply_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_json(
                root / ".riftreader-local" / "current-truth-refresh-apply" / "latest" / "summary.json",
                {
                    "schemaVersion": 1,
                    "kind": "riftreader-current-truth-refresh-apply",
                    "generatedAtUtc": "2026-06-01T06:01:06Z",
                    "status": "passed",
                    "verdict": "current-truth-refresh-applied",
                    "applyRequested": True,
                    "target": {"processId": 41808, "targetWindowHandle": "0x2B0A26"},
                    "plan": {"status": "passed", "updateCount": 34},
                    "hashes": {"trackedAfterSha256": "abc"},
                    "artifacts": {
                        "summaryJson": ".riftreader-local/current-truth-refresh-apply/latest/summary.json",
                        "summaryMarkdown": ".riftreader-local/current-truth-refresh-apply/latest/summary.md",
                        "backupCurrentTruthJson": ".riftreader-local/current-truth-refresh-apply/latest/current-truth-before-apply.json",
                    },
                    "blockers": [],
                    "warnings": ["no-facing-promotion-performed-by-apply-helper"],
                    "errors": [],
                    "safety": {
                        "dryRunOnly": False,
                        "applyFlagSent": True,
                        "trackedTruthWritten": True,
                        "movementSent": False,
                        "inputSent": False,
                        "targetMemoryBytesRead": False,
                        "targetMemoryBytesWritten": False,
                        "proofPromotion": False,
                        "actorChainPromotion": False,
                        "facingPromotion": False,
                        "gitMutation": False,
                    },
                    "next": {"recommendedAction": "Refresh status."},
                },
            )

            summary = status_packet.latest_current_truth_refresh_apply(root)

        self.assertEqual("passed", summary["status"])
        self.assertTrue(summary["applyRequested"])
        self.assertEqual(34, summary["plan"]["updateCount"])
        self.assertTrue(summary["safety"]["trackedTruthWritten"])
        self.assertFalse(summary["safety"]["proofPromotion"])
        self.assertIn("current-truth-before-apply.json", summary["backupCurrentTruthJson"])

    def test_latest_facing_promotion_readiness_review_reads_report_only_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_json(
                root
                / "scripts"
                / "captures"
                / "facing-target-promotion-readiness-review-20260601-063700-000000"
                / "summary.json",
                {
                    "schemaVersion": 1,
                    "kind": "facing-target-promotion-readiness-review-packet",
                    "generatedAtUtc": "2026-06-01T06:37:00Z",
                    "status": "passed",
                    "verdict": "candidate-facing-review-ready-for-explicit-promotion-gate",
                    "target": {"processId": 41808, "targetWindowHandle": "0x2B0A26"},
                    "candidate": {"offset": "0x30C", "candidateOnly": True},
                    "promotionDecision": {
                        "reviewPassed": True,
                        "promotionAllowed": False,
                        "promotionPerformed": False,
                        "explicitPromotionGateRequired": True,
                        "freshPrePromotionReadbackRequired": True,
                    },
                    "reviewGates": {"restartRelogSurvival": {"passed": True}},
                    "artifacts": {
                        "summaryJson": "scripts/captures/facing-target-promotion-readiness-review-20260601-063700-000000/summary.json",
                        "summaryMarkdown": "scripts/captures/facing-target-promotion-readiness-review-20260601-063700-000000/summary.md",
                    },
                    "blockers": [],
                    "warnings": ["candidate-facing-target-only-no-promotion"],
                    "errors": [],
                    "safety": {
                        "movementSent": False,
                        "inputSent": False,
                        "targetMemoryBytesRead": False,
                        "targetMemoryBytesWritten": False,
                        "proofPromotion": False,
                        "actorChainPromotion": False,
                        "facingPromotion": False,
                        "currentTruthWrite": False,
                        "gitMutation": False,
                    },
                    "sourceSafety": {"movementSent": True, "inputSent": True, "targetMemoryBytesRead": True},
                    "next": {"recommendedAction": "Refresh exact-target readbacks."},
                },
            )

            summary = status_packet.latest_facing_promotion_readiness_review(root)

        self.assertEqual("passed", summary["status"])
        self.assertEqual(41808, summary["target"]["processId"])
        self.assertTrue(summary["promotionDecision"]["reviewPassed"])
        self.assertFalse(summary["promotionDecision"]["promotionAllowed"])
        self.assertFalse(summary["promotionDecision"]["promotionPerformed"])
        self.assertTrue(summary["promotionDecision"]["freshPrePromotionReadbackRequired"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertTrue(summary["sourceSafety"]["movementSent"])
        self.assertEqual("Refresh exact-target readbacks.", summary["nextRecommendedAction"])

    def test_latest_navigation_pointer_discovery_reads_dashboard_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_json(
                root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.json",
                {
                    "schemaVersion": 1,
                    "kind": "riftreader-navigation-pointer-discovery-status",
                    "generatedAtUtc": "2026-05-31T15:00:00Z",
                    "status": "passed",
                    "verdict": "navigation-pointer-discovery-indexed",
                    "target": {
                        "processName": "rift_x64",
                        "processId": 25668,
                        "targetWindowHandle": "0x320CB0",
                        "processStartUtc": "2026-05-30T02:46:41Z",
                    },
                    "freshness": {
                        "status": "stale",
                        "staleSources": ["currentTruth"],
                        "unknownSources": [],
                    },
                    "candidates": {
                        "promotedCoordinate": {
                            "status": "promoted-static-coordinate-resolver",
                            "promotionAllowed": True,
                            "candidateOnly": False,
                            "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                            "rootRva": "0x32EBC80",
                            "coordinateOffset": "0x320",
                            "latestReadbackStatus": "passed",
                            "latestReadbackAtUtc": "2026-05-31T14:59:00Z",
                        },
                        "candidateFacingTarget": {
                            "status": "candidate-only",
                            "candidateOnly": True,
                            "promotionAllowed": False,
                            "chainShape": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
                            "offset": "0x30C",
                            "comparisonMaxAbsYawDeltaDegrees": 14.25,
                        },
                        "candidateTurnRate": {
                            "status": "candidate-only",
                            "candidateOnly": True,
                            "promotionAllowed": False,
                            "offset": "0x304",
                            "comparisonMaxAbsDelta": 0.5,
                        },
                        "coordinateDeltaCandidate": {
                            "status": "confirms-promoted-coordinate-offset",
                            "candidateOnly": False,
                            "ownerOffset": "0x320",
                            "trackingErrorMaxAbs": 0.01,
                            "matchesPromotedCoordinateAddress": True,
                        },
                    },
                    "proofGates": {
                        "facingThreePoseGate": {
                            "status": "passed",
                            "verdict": "formal-three-pose-route-progress-gate-passed",
                            "candidateOnly": True,
                            "promotionAllowed": False,
                            "formalThreePoseGatePassed": True,
                            "poseCount": 3,
                            "passedPoseCount": 3,
                            "minimumProgressDistance": 1.25,
                        },
                        "facingRestartSurvival": {
                            "status": "passed",
                            "verdict": "candidate-facing-target-restart-relog-survival-passed",
                            "candidateOnly": True,
                            "promotionAllowed": False,
                            "restartRelogSurvived": True,
                            "offsetsStable": True,
                            "processStartChanged": True,
                            "facingTargetOffset": "0x30C",
                        },
                        "turnForwardExperiment": {
                            "status": "passed",
                            "verdict": "turn-forward-live-progress-validated",
                            "candidateOnly": True,
                            "promotionAllowed": False,
                            "routeStatus": "progress",
                            "totalProgressDistance": 1.5,
                            "movementApproved": True,
                            "turnApproved": True,
                            "sourceMovementSent": True,
                            "sourceInputSent": True,
                        },
                        "ghidraStaticEvidence": {
                            "status": "passed",
                            "kind": "riftreader-ghidra-static-evidence-run",
                            "generatedAtUtc": "2026-05-31T14:59:30Z",
                            "summaryJson": "scripts\\captures\\ghidra-static-analysis-x\\summary.json",
                            "summaryMarkdown": "scripts\\captures\\ghidra-static-analysis-x\\summary.md",
                            "evidenceJson": "scripts\\captures\\ghidra-static-analysis-x\\pointer-evidence.json",
                            "rootAddress": "1432ebc80",
                            "rootReferenceCountCaptured": 200,
                            "instructionsScanned": 8057130,
                            "analysisTimedOutProjectSaved": True,
                            "offlineOnly": True,
                            "warnings": ["ghidra-analysis-timeout-project-saved"],
                        },
                    },
                    "promotionReadiness": {
                        "coordinateResolver": "promoted",
                        "facingTarget": "candidate-only-gates-packaged-requires-review",
                        "facingThreePoseGate": "passed",
                        "restartRelogSurvival": "passed",
                        "turnForwardLiveProgress": "passed",
                        "proofPromotionPerformed": False,
                    },
                    "next": {
                        "recommendedAction": "Run restart/relog survival plus static-root proof.",
                        "recommendedActions": ["Run restart/relog survival plus static-root proof."],
                    },
                    "blockers": [],
                    "warnings": ["current-truth-stale"],
                    "errors": [],
                    "safety": {
                        "readOnlyArtifactIndex": True,
                        "movementSent": False,
                        "inputSent": False,
                        "targetMemoryBytesRead": False,
                        "targetMemoryBytesWritten": False,
                        "proofPromotion": False,
                        "actorChainPromotion": False,
                        "facingPromotion": False,
                        "gitMutation": False,
                    },
                },
            )
            write_text(root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.md", "# Summary\n")

            summary = status_packet.latest_navigation_pointer_discovery(root)

        self.assertEqual("passed", summary["status"])
        self.assertEqual("stale", summary["freshnessStatus"])
        self.assertEqual(["currentTruth"], summary["staleSources"])
        self.assertEqual(25668, summary["target"]["processId"])
        self.assertEqual("0x30C", summary["candidateFacingTarget"]["offset"])
        self.assertEqual(14.25, summary["candidateFacingTarget"]["comparisonMaxAbsYawDeltaDegrees"])
        self.assertEqual("0x304", summary["candidateTurnRate"]["offset"])
        self.assertEqual(0.01, summary["coordinateDeltaCandidate"]["trackingErrorMaxAbs"])
        self.assertTrue(summary["proofGates"]["facingThreePoseGate"]["formalThreePoseGatePassed"])
        self.assertTrue(summary["proofGates"]["facingRestartSurvival"]["restartRelogSurvived"])
        self.assertEqual(1.5, summary["proofGates"]["turnForwardExperiment"]["totalProgressDistance"])
        ghidra_static = summary["proofGates"]["ghidraStaticEvidence"]
        self.assertEqual("passed", ghidra_static["status"])
        self.assertEqual("1432ebc80", ghidra_static["rootAddress"])
        self.assertEqual(200, ghidra_static["rootReferenceCountCaptured"])
        self.assertTrue(ghidra_static["offlineOnly"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["safety"]["proofPromotion"])

    def test_latest_navigation_pointer_discovery_missing_is_nonblocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = status_packet.latest_navigation_pointer_discovery(Path(temp_dir))

        self.assertEqual("missing", summary["status"])
        self.assertEqual([], summary["blockers"])
        self.assertEqual([], summary["warnings"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["gitMutation"])

    def test_navigation_pointer_discovery_parse_error_stays_inside_compact_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(
                root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.json",
                "{not-json",
            )

            packet = status_packet.build_status_packet(
                root,
                run_coordinate_status=False,
                check_opencode=False,
                collect_git_state=False,
            )
            compact = status_packet.compact_summary(packet)

        navigation = compact["navigationPointerDiscovery"]
        self.assertEqual("passed", packet["status"])
        self.assertEqual([], packet["errors"])
        self.assertEqual("parse-error", navigation["status"])
        self.assertIn("navigation-pointer-discovery-summary-unusable", navigation["blockers"])
        self.assertTrue(navigation["warnings"][0].startswith("navigation-pointer-discovery-summary-parse-error:"))
        self.assertFalse(navigation["safety"]["movementSent"])
        self.assertFalse(navigation["safety"]["inputSent"])
        self.assertFalse(navigation["safety"]["proofPromotion"])

    def test_compact_markdown_includes_navigation_pointer_discovery_section(self) -> None:
        packet = {
            "schemaVersion": 1,
            "kind": "riftreader-local-workflow-status-packet",
            "generatedAtUtc": "2026-05-31T15:00:00Z",
            "status": "passed",
            "repoRoot": str(REPO_ROOT),
            "blockers": [],
            "warnings": [],
            "errors": [],
            "git": {},
            "liveTarget": {},
            "launcher": {},
            "characterLoginSupervisor": {},
            "currentProof": {"summary": {}},
            "currentTruth": {"summary": {}},
            "latestHandoff": {},
            "opencode": {"retired": True, "checked": False},
            "navigationPointerDiscovery": {
                "status": "passed",
                "freshnessStatus": "fresh",
                "staleSources": [],
                "summaryJson": ".riftreader-local/navigation-pointer-discovery/latest/summary.json",
                "promotedCoordinate": {"status": "promoted", "chain": "[rift_x64+0x32EBC80]+0x320"},
                "candidateFacingTarget": {
                    "status": "candidate-only",
                    "offset": "0x30C",
                    "comparisonMaxAbsYawDeltaDegrees": 12.0,
                },
                "candidateTurnRate": {"status": "candidate-only", "offset": "0x304"},
                "promotionReadiness": {
                    "facingThreePoseGate": "passed",
                    "restartRelogSurvival": "passed",
                    "turnForwardLiveProgress": "passed",
                },
                "nextRecommendedAction": "Run facing proof.",
            },
            "currentTruthRefreshPlan": {
                "status": "passed",
                "summaryJson": ".riftreader-local/current-truth-refresh-plan/latest/summary.json",
                "proposedCurrentTruthDiff": ".riftreader-local/current-truth-refresh-plan/latest/proposed-current-truth.diff",
                "updateCount": 9,
                "requiresExplicitApprovalForApply": True,
                "nextRecommendedAction": "Review ignored artifacts.",
            },
            "currentTruthRefreshApply": {
                "status": "passed",
                "verdict": "current-truth-refresh-applied",
                "summaryJson": ".riftreader-local/current-truth-refresh-apply/latest/summary.json",
                "backupCurrentTruthJson": ".riftreader-local/current-truth-refresh-apply/latest/current-truth-before-apply.json",
                "applyRequested": True,
                "safety": {"trackedTruthWritten": True, "proofPromotion": False},
                "nextRecommendedAction": "Refresh status.",
            },
            "facingPromotionReadinessReview": {
                "status": "passed",
                "verdict": "candidate-facing-review-ready-for-explicit-promotion-gate",
                "summaryJson": "scripts/captures/facing-target-promotion-readiness-review-x/summary.json",
                "promotionDecision": {
                    "reviewPassed": True,
                    "promotionAllowed": False,
                    "promotionPerformed": False,
                    "freshPrePromotionReadbackRequired": True,
                },
                "nextRecommendedAction": "Refresh exact-target readbacks.",
            },
            "safety": {"movementSent": False, "gitMutation": False},
            "nextRecommendedAction": "none",
            "artifacts": {},
        }

        markdown = status_packet.render_compact_markdown(packet)

        self.assertIn("## Navigation pointer discovery", markdown)
        self.assertIn("## Current truth refresh plan", markdown)
        self.assertIn("## Current truth refresh apply", markdown)
        self.assertIn("0x30C", markdown)
        self.assertIn("three-pose", markdown)
        self.assertIn("Run facing proof.", markdown)
        self.assertIn("proposed-current-truth.diff", markdown)
        self.assertIn("current-truth-refresh-applied", markdown)
        self.assertIn("## Facing promotion-readiness review", markdown)
        self.assertIn("candidate-facing-review-ready-for-explicit-promotion-gate", markdown)
        self.assertIn("Refresh exact-target readbacks.", markdown)

    def test_latest_static_owner_readback_reports_capture_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_json(
                root
                / "scripts"
                / "captures"
                / "static-owner-coordinate-chain-readback-20260528-120000-000000"
                / "summary.json",
                {
                    "status": "passed",
                    "verdict": "promoted-static-coordinate-resolver-readback-passed",
                    "classification": "static-coordinate-resolver-current-position-source",
                    "generatedAtUtc": "2026-05-28T12:00:00Z",
                    "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "sampleCount": 3,
                    "maxPlanarDelta": 0.0,
                    "blockers": [],
                    "warnings": ["readback-only-not-facing-or-actor-stat-promotion"],
                },
            )
            write_json(
                root / "scripts" / "captures" / "static-owner-nav-state-20260528-120001-000000" / "summary.json",
                {
                    "status": "passed",
                    "verdict": "position-and-facing-nav-state-readback-passed",
                    "classification": "candidate-facing-state-source-not-promoted",
                    "generatedAtUtc": "2026-05-28T12:00:01Z",
                    "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "yawDegrees": 80.5,
                    "pitchDegrees": 2.0,
                    "sampleCount": 3,
                    "yawRangeDegrees": 0.0,
                    "maxAbsYawDeltaDegrees": 0.0,
                    "blockers": [],
                    "warnings": ["facing-candidate-readback-only-not-promoted"],
                },
            )
            errors: list[str] = []
            warnings: list[str] = []

            summary = status_packet.latest_static_owner_readback(
                root,
                errors,
                warnings,
                now=datetime(2026, 5, 28, 12, 1, tzinfo=timezone.utc),
            )

        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual("passed", summary["coordinateChain"]["status"])
        self.assertEqual("fresh", summary["coordinateChain"]["freshness"]["status"])
        self.assertEqual(60, summary["coordinateChain"]["freshness"]["ageSeconds"])
        self.assertEqual(1.0, summary["coordinateChain"]["coordinate"]["x"])
        self.assertEqual("passed", summary["navState"]["status"])
        self.assertEqual(80.5, summary["navState"]["yawDegrees"])

    def test_current_proof_summary_reports_proof_freshness(self) -> None:
        now = datetime(2026, 5, 27, 7, 2, tzinfo=timezone.utc)
        proof = {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-27T07:00:00Z",
            "latestValidation": {
                "status": "valid",
                "movementAllowed": True,
                "generatedAtUtc": "2026-05-27T07:01:30Z",
            },
            "latestProofOnly": {
                "status": "passed-proof-only",
                "generatedAtUtc": "2026-05-27T07:01:20Z",
            },
        }

        summary = status_packet.summarize_current_proof(proof, now=now)

        self.assertEqual(summary["proofFreshness"]["status"], "fresh")
        self.assertEqual(summary["proofFreshness"]["ageSeconds"], 30)
        self.assertEqual(summary["proofFreshness"]["observedSource"], "latestValidation.generatedAtUtc")

    def test_build_status_packet_blocks_stale_proof_anchor_movement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "docs" / "handoffs" / "2026-05-27-handoff.md", "# Handoff\n\n## TL;DR\n\nproof stale")
            write_text(root / "docs" / "recovery" / "current-truth.md", "# Truth\n\n## Verdict\n\nMovement was allowed.")
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "status": "current-target-proofonly-passed",
                    "updatedAtUtc": "2026-05-27T07:00:00Z",
                    "target": {"processName": "rift_x64", "processId": 12148, "targetWindowHandle": "0x640C0C"},
                    "movementGate": {
                        "allowed": True,
                        "status": "allowed-current-target-proofonly-passed-route-smoke-passed",
                        "reason": "historically allowed",
                    },
                    "currentBlockers": [],
                    "nextRecommendedAction": "historical next action",
                },
            )
            write_json(
                root / "docs" / "recovery" / "current-proof-anchor-readback.json",
                {
                    "status": "current-target-proofonly-passed",
                    "lastUpdatedUtc": "2026-05-27T07:00:00Z",
                    "target": {"processName": "rift_x64", "processId": 12148, "targetWindowHandle": "0x640C0C"},
                    "latestValidation": {
                        "status": "valid",
                        "movementAllowed": True,
                        "movementSent": False,
                        "generatedAtUtc": "2026-05-27T07:00:00Z",
                    },
                    "latestProofOnly": {
                        "status": "passed-proof-only",
                        "movementSent": False,
                        "movementAttempted": False,
                        "generatedAtUtc": "2026-05-27T07:00:00Z",
                    },
                },
            )

            packet = status_packet.build_status_packet(
                root,
                run_coordinate_status=False,
                check_opencode=False,
                collect_git_state=False,
                now=datetime(2026, 5, 27, 7, 2, tzinfo=timezone.utc),
            )

        movement_gate = packet["currentTruth"]["summary"]["movementGate"]
        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(movement_gate["allowed"])
        self.assertEqual(movement_gate["status"], "blocked-proof-anchor-age-out-of-range")
        self.assertEqual(movement_gate["proofFreshness"]["ageSeconds"], 120)
        self.assertIn("proof-anchor-stale-for-movement:ageSeconds=120;maxAgeSeconds=60", packet["blockers"])
        self.assertIn("movement-not-allowed:blocked-proof-anchor-age-out-of-range", packet["blockers"])
        self.assertIn("same-target ProofOnly/proof-anchor refresh", packet["nextRecommendedAction"])

    def test_build_status_packet_prefers_promoted_facing_navigation_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "docs" / "recovery" / "current-truth.md", "# Truth\n")
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "status": "current-static-resolver",
                    "updatedAtUtc": "2026-06-01T17:07:09Z",
                    "target": {"processName": "rift_x64", "processId": 41808, "targetWindowHandle": "0x2B0A26"},
                    "movementGate": {"allowed": True, "status": "allowed"},
                    "currentBlockers": [],
                    "nextRecommendedAction": "historical next action",
                },
            )
            write_json(
                root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.json",
                {
                    "schemaVersion": 1,
                    "kind": "riftreader-navigation-pointer-discovery-status",
                    "generatedAtUtc": "2026-06-01T17:07:24Z",
                    "status": "passed",
                    "verdict": "navigation-pointer-discovery-indexed",
                    "freshness": {"status": "fresh", "staleSources": [], "unknownSources": []},
                    "candidates": {
                        "promotedCoordinate": {"status": "promoted", "promotionAllowed": True},
                        "candidateFacingTarget": {
                            "status": "promoted-static-owner-facing-yaw-current-pid-readback-passed",
                            "candidateOnly": False,
                            "promotionAllowed": True,
                            "offset": "0x30C",
                        },
                    },
                    "promotionReadiness": {
                        "facingTarget": "promoted-static-owner-facing-yaw-current-pid-readback-passed",
                        "facingPromotionPerformed": True,
                        "promotionReviewRequired": False,
                    },
                    "next": {
                        "recommendedAction": "Use promoted facing/yaw after exact-target preflight.",
                        "recommendedActions": ["Use promoted facing/yaw after exact-target preflight."],
                    },
                    "blockers": [],
                    "warnings": [],
                    "errors": [],
                    "safety": {
                        "readOnlyArtifactIndex": True,
                        "movementSent": False,
                        "inputSent": False,
                        "proofPromotion": False,
                        "actorChainPromotion": False,
                        "facingPromotion": False,
                        "gitMutation": False,
                    },
                },
            )
            write_json(
                root
                / "scripts"
                / "captures"
                / "facing-target-promotion-readiness-review-20260601-170000-000000"
                / "summary.json",
                {
                    "schemaVersion": 1,
                    "kind": "facing-target-promotion-readiness-review-packet",
                    "generatedAtUtc": "2026-06-01T17:00:00Z",
                    "status": "passed",
                    "target": {"processId": 41808, "targetWindowHandle": "0x2B0A26"},
                    "candidate": {"offset": "0x30C", "candidateOnly": True},
                    "promotionDecision": {"reviewPassed": True, "promotionAllowed": False, "promotionPerformed": False},
                    "blockers": [],
                    "warnings": [],
                    "errors": [],
                    "safety": {"movementSent": False, "inputSent": False, "proofPromotion": False, "facingPromotion": False},
                    "sourceSafety": {"movementSent": True, "inputSent": True},
                    "next": {"recommendedAction": "Refresh exact-target readbacks."},
                },
            )

            packet = status_packet.build_status_packet(
                root,
                run_coordinate_status=False,
                check_opencode=False,
                collect_git_state=False,
                now=datetime(2026, 6, 1, 17, 8, tzinfo=timezone.utc),
            )

        self.assertEqual("passed", packet["status"])
        self.assertEqual("Use promoted facing/yaw after exact-target preflight.", packet["nextRecommendedAction"])

    def test_compact_summary_reports_static_owner_navigation_bridge_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "scripts" / "riftreader-actor-chain-no-debug-status.cmd", "@echo off\n")
            write_text(root / "scripts" / "static-owner-coordinate-chain-readback.cmd", "@echo off\n")
            write_text(root / "scripts" / "static-owner-nav-now.cmd", "@echo off\n")
            write_text(root / "scripts" / "static-owner-turn-aware-route-plan.cmd", "@echo off\n")
            write_text(root / "scripts" / "static-owner-nav-report-route-run.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-navigation-pointer-discovery.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-current-truth-refresh-plan.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-current-truth-refresh-apply.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-facing-target-three-pose-gate.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-facing-target-restart-survival-packet.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-facing-target-promotion-readiness-review.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-facing-target-promotion-apply.cmd", "@echo off\n")
            packet = {
                "schemaVersion": 1,
                "kind": "riftreader-local-workflow-status-packet",
                "generatedAtUtc": "2026-05-28T00:00:00Z",
                "status": "passed",
                "repoRoot": str(root),
                "blockers": [],
                "warnings": [],
                "errors": [],
                "git": {},
                "liveTarget": {},
                "launcher": {},
                "currentProof": {"summary": {}},
                "currentTruth": {"summary": {}},
                "latestHandoff": {},
                "coordinateRecoveryStatus": {},
                "opencode": {"retired": True, "checked": False},
                "safety": {"movementSent": False, "gitMutation": False},
                "nextRecommendedAction": "none",
                "artifacts": {},
            }

            compact = status_packet.compact_summary(packet)

        commands = {item["key"]: item for item in compact["bridgeCommands"]}
        self.assertTrue(commands["actor-chain-no-debug-status"]["exists"])
        self.assertIn("no promotion", commands["actor-chain-no-debug-status"]["safety"])
        self.assertTrue(commands["static-owner-coordinate-chain-readback"]["exists"])
        self.assertIn("live target memory readback only", commands["static-owner-coordinate-chain-readback"]["safety"])
        self.assertTrue(commands["static-owner-nav-now"]["exists"])
        self.assertIn("facing/yaw readback only", commands["static-owner-nav-now"]["safety"])
        self.assertTrue(commands["static-owner-turn-aware-plan"]["exists"])
        self.assertIn("dry-run route/turn planning only", commands["static-owner-turn-aware-plan"]["safety"])
        self.assertTrue(commands["static-owner-route-run-report"]["exists"])
        self.assertIn("saved route-run report only", commands["static-owner-route-run-report"]["safety"])
        self.assertTrue(commands["navigation-pointer-discovery"]["exists"])
        self.assertIn("read-only artifact index", commands["navigation-pointer-discovery"]["safety"])
        self.assertTrue(commands["current-truth-refresh-plan"]["exists"])
        self.assertIn("ignored dry-run plan only", commands["current-truth-refresh-plan"]["safety"])
        self.assertTrue(commands["current-truth-refresh-apply"]["exists"])
        self.assertIn("dry-run validation by default", commands["current-truth-refresh-apply"]["safety"])
        self.assertTrue(commands["facing-target-three-pose-gate"]["exists"])
        self.assertIn("report-only package", commands["facing-target-three-pose-gate"]["safety"])
        self.assertTrue(commands["facing-target-restart-survival-packet"]["exists"])
        self.assertIn("report-only pre/post", commands["facing-target-restart-survival-packet"]["safety"])
        self.assertTrue(commands["facing-target-promotion-readiness-review"]["exists"])
        self.assertIn("report-only review", commands["facing-target-promotion-readiness-review"]["safety"])
        self.assertTrue(commands["facing-target-promotion-apply"]["exists"])
        self.assertIn("--apply writes tracked facing/yaw promotion", commands["facing-target-promotion-apply"]["safety"])


if __name__ == "__main__":
    unittest.main()
