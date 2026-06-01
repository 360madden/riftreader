#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
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

from riftreader_workflow import navigation_pointer_discovery as discovery  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seed_navigation_artifacts(root: Path) -> None:
    write_json(
        root / "docs" / "recovery" / "current-truth.json",
        {
            "updatedAtUtc": "2026-05-31T14:23:12Z",
            "target": {
                "processName": "rift_x64",
                "processId": 25668,
                "targetWindowHandle": "0x320CB0",
                "processStartUtc": "2026-05-30T02:46:41Z",
                "moduleBase": "0x7FF6EE5D0000",
                "status": "current",
            },
            "staticChainStatus": {
                "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed",
                "promotionAllowed": True,
                "primaryCandidate": {
                    "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                    "rootModule": "rift_x64.exe",
                    "rootRva": "0x32EBC80",
                    "ownerAddress": "0x1000",
                    "coordinateAddress": "0x1320",
                    "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "latestCurrentReadbackAtUtc": "2026-05-31T14:23:12Z",
                },
                "latestApiNowValidation": {
                    "currentApiNowStatus": "passed-current-pid-25668-api-now-vs-chain-now",
                    "currentPidValidation": {"status": "passed-current-pid-25668-api-now-vs-chain-now"},
                },
            },
        },
    )
    write_json(
        root / "scripts" / "captures" / "static-owner-coordinate-chain-readback-20260531-142312-924000" / "summary.json",
        {
            "mode": "static-owner-coordinate-chain-readback",
            "status": "passed",
            "verdict": "promoted-static-coordinate-resolver-readback-passed",
            "generatedAtUtc": "2026-05-31T14:23:12Z",
            "reads": {"ownerAddress": "0x1000", "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0}},
            "analysis": {"maxPlanarDelta": 0.0},
            "target": {
                "processName": "rift_x64",
                "processId": 25668,
                "targetWindowHandle": "0x320CB0",
                "expectedProcessStartUtc": "2026-05-30T02:46:41Z",
                "moduleBase": "0x7FF6EE5D0000",
            },
            "safety": {"targetMemoryBytesRead": True},
        },
    )
    write_json(
        root / "scripts" / "captures" / "static-owner-nav-state-20260531-142313-000000" / "summary.json",
        {
            "kind": "static-owner-nav-state-readback",
            "status": "passed",
            "verdict": "position-and-facing-nav-state-readback-passed",
            "generatedAtUtc": "2026-05-31T14:23:13Z",
            "target": {
                "processName": "rift_x64",
                "processId": 25668,
                "targetWindowHandle": "0x320CB0",
                "expectedProcessStartUtc": "2026-05-30T02:46:41Z",
                "moduleBase": "0x7FF6EE5D0000",
            },
            "latestState": {
                "ownerAddress": "0x1000",
                "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                "facingTargetCoordinate": {"x": 10.0, "y": 2.0, "z": 6.0},
                "yawDegrees": 22.5,
                "pitchDegrees": -4.0,
                "planarLookaheadDistance": 9.9,
                "headingSupport0x300": 12.5,
                "turnRate0x304": 1.25,
                "turnRateClassification": "left",
                "rotationSupport0x308": 0.5,
                "animationTimer0x408": 0.125,
                "facingTargetOffset": "0x30C",
                "turnRateOffset": "0x304",
            },
            "safety": {"targetMemoryBytesRead": True},
        },
    )
    write_json(
        root / "scripts" / "captures" / "static-owner-facing-comparison-20260531-141949-380215" / "summary.json",
        {
            "kind": "static-owner-facing-comparison",
            "status": "passed",
            "verdict": "static-owner-facing-candidates-scored",
            "generatedAtUtc": "2026-05-31T14:19:49Z",
            "comparison": {
                "ownerAddresses": ["0x1000"],
                "maxCoordinatePlanarDrift": 0.0,
                "relativeTargetCandidates": [
                    {
                        "offset": "0x30C",
                        "address": "0x130C",
                        "yawDeltasFromBaseline": {"right": 49.4, "left": -62.1},
                        "maxAbsYawDeltaDegrees": 62.1,
                    }
                ],
                "scalarCandidates": [
                    {
                        "offset": "0x304",
                        "address": "0x1304",
                        "deltasFromBaseline": {"right": -0.8, "left": 1.0},
                        "maxAbsDelta": 1.0,
                    }
                ],
            },
        },
    )
    write_json(
        root / "scripts" / "captures" / "pointer-owner-neighborhood-inspector-20260531-142006-017134" / "summary.json",
        {
            "kind": "pointer-owner-neighborhood-inspector",
            "status": "passed",
            "generatedAtUtc": "2026-05-31T14:20:06Z",
            "analysis": {"exactTargetCounts": {"0x130C": 0}, "regionMatchCount": 2, "modulePointerCount": 0},
        },
    )
    family_dir = root / "scripts" / "captures" / "family-snapshot-sequence-currentpid-25668-20260531-142159-332736"
    candidate_path = family_dir / "delta-analysis" / "candidate-vec3.json"
    write_json(
        family_dir / "summary.json",
        {
            "mode": "current-pid-family-snapshot-sequence",
            "status": "passed",
            "generatedAtUtc": "2026-05-31T14:21:59Z",
            "artifacts": {"candidateVec3Json": str(candidate_path)},
            "safety": {"movementSent": True, "inputSent": True},
            "analysis": {
                "analysis": {
                    "candidateCount": 2,
                    "familyCount": 1,
                    "bestCandidate": {
                        "candidateId": "snapshot-delta-1320-xyz",
                        "addressHex": "0x1320",
                        "segmentOffsetHex": "0x320",
                        "axisOrder": "xyz",
                        "apiDelta": {"planar": 2.0},
                        "memoryDelta": {"planar": 2.01},
                        "trackingError": {"maxAbs": 0.006},
                        "baselineMaxAbsDelta": 0.003,
                        "displacedMaxAbsDelta": 0.004,
                    },
                }
            },
        },
    )
    write_json(candidate_path, {"candidateCount": 1, "candidates": []})
    write_json(
        root
        / "scripts"
        / "captures"
        / "static-owner-camera-yaw-classification-20260531-174422-894291"
        / "summary.json",
        {
            "kind": "static-owner-camera-yaw-classification",
            "status": "passed",
            "verdict": "visual-changed-static-yaw-unchanged",
            "generatedAtUtc": "2026-05-31T14:22:30Z",
            "stimulus": {"type": "mouse-look", "direction": "right", "pixels": 120, "approved": True},
            "visualEvidence": {
                "baseline": {"output": "baseline.png"},
                "post": {"output": "post.png"},
                "rawDiff": {"status": "changed", "changedPercent": 74.0},
            },
            "snapshotEvidence": {
                "comparisonJson": "comparison.json",
                "pointerNeighborhoodJson": "pointer.json",
            },
            "analysis": {
                "classification": "visual-changed-static-yaw-unchanged",
                "visualChanged": True,
                "staticYawChanged": False,
                "actionableForRouteControl": False,
                "signedYawDeltaDegrees": 0.0,
                "absoluteYawDeltaDegrees": 0.0,
                "changedFocusOffsets": [
                    {"offset": "0x300", "delta": 58.1875, "absDelta": 58.1875},
                    {"offset": "0x304", "delta": -0.605, "absDelta": 0.605},
                ],
            },
            "safety": {"movementSent": True, "inputSent": True, "targetMemoryBytesRead": True},
        },
    )


def seed_camera_yaw_multipose_report(root: Path) -> None:
    write_json(
        root
        / "scripts"
        / "captures"
        / "static-owner-camera-yaw-multipose-report-20260531-174600-000000"
        / "summary.json",
        {
            "kind": "static-owner-camera-yaw-multipose-report",
            "status": "passed",
            "verdict": "route-actionable-candidate-present-needs-proof",
            "generatedAtUtc": "2026-05-31T14:23:30Z",
            "sourceCount": 2,
            "poses": [
                {
                    "summaryJson": "right-summary.json",
                    "stimulus": {"type": "mouse-look", "direction": "right", "pixels": 120, "approved": True},
                    "classification": "visual-and-static-yaw-changed",
                    "staticYawChanged": True,
                    "signedYawDeltaDegrees": 8.4,
                    "actionableForRouteControl": True,
                },
                {
                    "summaryJson": "left-summary.json",
                    "stimulus": {"type": "mouse-look", "direction": "left", "pixels": 120, "approved": True},
                    "classification": "visual-and-static-yaw-changed",
                    "staticYawChanged": True,
                    "signedYawDeltaDegrees": -8.4,
                    "actionableForRouteControl": True,
                },
            ],
            "offsetAggregate": {
                "0x300": {"sampleCount": 2, "directions": ["left", "right"], "maxAbsDelta": 8.4},
                "0x304": {"sampleCount": 2, "directions": ["left", "right"], "maxAbsDelta": 0.01},
            },
            "analysis": {
                "classificationCounts": {"visual-and-static-yaw-changed": 2},
                "routeActionablePoseCount": 2,
                "visualChangedStaticYawUnchangedCount": 0,
                "changedOffsetCount": 2,
                "candidateOnly": True,
                "promotionAllowed": False,
                "actionableForRouteControl": True,
            },
            "sourceSafety": {
                "inputSent": True,
                "movementSent": False,
                "targetMemoryBytesRead": True,
                "targetMemoryBytesWritten": False,
            },
            "safety": {
                "inputSent": False,
                "movementSent": False,
                "targetMemoryBytesRead": False,
                "targetMemoryBytesWritten": False,
                "proofPromotion": False,
            },
        },
    )


def seed_facing_proof_gate_artifacts(root: Path) -> None:
    write_json(
        root
        / "scripts"
        / "captures"
        / "facing-target-three-pose-gate-20260531-142500-000000"
        / "summary.json",
        {
            "kind": "facing-target-three-pose-gate",
            "status": "passed",
            "verdict": "formal-three-pose-route-progress-gate-passed",
            "generatedAtUtc": "2026-05-31T14:23:45Z",
            "poseCount": 3,
            "passedPoseCount": 3,
            "analysis": {
                "candidateOnly": True,
                "promotionAllowed": False,
                "formalThreePoseGatePassed": True,
                "aggregateProgressDistance": 4.5,
                "minimumProgressDistance": 1.25,
                "maximumProgressDistance": 1.75,
                "candidateFacingTargetOffset": "0x30C",
                "supportOnlyTurnRateOffset": "0x304",
            },
            "sourceSafety": {"movementSent": True, "inputSent": True},
            "safety": {"movementSent": False, "inputSent": False, "proofPromotion": False, "facingPromotion": False},
            "blockers": [],
            "warnings": ["candidate-facing-target-only-no-promotion"],
        },
    )
    write_json(
        root
        / "scripts"
        / "captures"
        / "facing-target-restart-survival-packet-20260531-142600-000000"
        / "summary.json",
        {
            "kind": "facing-target-restart-survival-packet",
            "status": "passed",
            "verdict": "candidate-facing-target-restart-relog-survival-passed",
            "generatedAtUtc": "2026-05-31T14:23:50Z",
            "preRestart": {"summaryJson": "pre.json"},
            "postRestart": {"summaryJson": "post.json"},
            "analysis": {
                "candidateOnly": True,
                "promotionAllowed": False,
                "restartRelogSurvived": True,
                "offsetsStable": True,
                "processStartChanged": True,
                "processIdChanged": True,
                "windowHandleChanged": True,
                "ownerAddressChanged": True,
                "facingTargetOffset": "0x30C",
                "positionOffset": "0x320",
                "supportOnlyTurnRateOffset": "0x304",
            },
            "sourceSafety": {"targetMemoryBytesRead": True, "movementSent": False, "inputSent": False},
            "safety": {"movementSent": False, "inputSent": False, "proofPromotion": False, "facingPromotion": False},
            "blockers": [],
            "warnings": ["candidate-facing-target-only-no-promotion"],
        },
    )
    write_json(
        root
        / "scripts"
        / "captures"
        / "static-owner-turn-forward-experiment-20260531-142700-000000"
        / "summary.json",
        {
            "kind": "static-owner-turn-forward-experiment",
            "status": "passed",
            "verdict": "turn-forward-live-progress-validated",
            "generatedAtUtc": "2026-05-31T14:23:55Z",
            "operator": {"movementApproved": True, "turnApproved": True, "allowCandidateTurnControl": True},
            "forwardResult": {
                "routeStatus": "progress",
                "totalProgressDistance": 1.5,
                "initialPlanarDistance": 10.0,
                "finalPlanarDistance": 8.5,
            },
            "contract": {"status": "passed"},
            "artifacts": {"forwardStepSummaryJson": "step.json", "turnAwarePlanSummaryJson": "plan.json"},
            "safety": {
                "movementSent": True,
                "inputSent": True,
                "navigationControl": True,
                "proofPromotion": False,
                "facingPromotion": False,
            },
            "blockers": [],
            "warnings": [],
        },
    )


def seed_facing_promotion_readiness_review(root: Path) -> None:
    write_json(
        root
        / "scripts"
        / "captures"
        / "facing-target-promotion-readiness-review-20260531-142800-000000"
        / "summary.json",
        {
            "kind": "facing-target-promotion-readiness-review-packet",
            "status": "passed",
            "verdict": "candidate-facing-review-ready-for-explicit-promotion-gate",
            "generatedAtUtc": "2026-05-31T14:23:58Z",
            "target": {
                "processName": "rift_x64",
                "processId": 25668,
                "targetWindowHandle": "0x320CB0",
                "processStartUtc": "2026-05-30T02:46:41Z",
                "moduleBase": "0x7FF6EE5D0000",
            },
            "candidate": {
                "status": "candidate-only",
                "chainExpression": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
                "offset": "0x30C",
                "promotionAllowed": False,
                "candidateOnly": True,
            },
            "promotionDecision": {
                "reviewPassed": True,
                "promotionAllowed": False,
                "promotionPerformed": False,
                "explicitPromotionGateRequired": True,
                "freshPrePromotionReadbackRequired": True,
                "recommendedPromotionState": "review-passed-awaiting-explicit-promotion-gate-and-fresh-readback",
            },
            "next": {
                "recommendedAction": "Refresh exact-target static/nav/API readbacks, then run a separate explicit promotion gate only if approved."
            },
            "artifacts": {
                "summaryJson": "scripts\\captures\\facing-target-promotion-readiness-review-20260531-142800-000000\\summary.json",
                "summaryMarkdown": "scripts\\captures\\facing-target-promotion-readiness-review-20260531-142800-000000\\summary.md",
            },
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
            "blockers": [],
            "warnings": ["candidate-facing-target-only-no-promotion"],
        },
    )


def seed_turn_rate_promotion_readiness_review(root: Path) -> None:
    write_json(
        root
        / "scripts"
        / "captures"
        / "turn-rate-promotion-readiness-review-20260531-142900-000000"
        / "summary.json",
        {
            "kind": "turn-rate-promotion-readiness-review-packet",
            "status": "passed",
            "verdict": "candidate-turn-rate-review-ready-for-explicit-promotion-gate",
            "generatedAtUtc": "2026-05-31T14:23:59Z",
            "target": {
                "processName": "rift_x64",
                "processId": 25668,
                "targetWindowHandle": "0x320CB0",
                "processStartUtc": "2026-05-30T02:46:41Z",
                "moduleBase": "0x7FF6EE5D0000",
            },
            "candidate": {
                "status": "candidate-only",
                "chainExpression": "[rift_x64+0x32EBC80]+0x304",
                "offset": "0x304",
                "promotionAllowed": False,
                "candidateOnly": True,
            },
            "promotionDecision": {
                "reviewPassed": True,
                "promotionAllowed": False,
                "promotionPerformed": False,
                "explicitPromotionGateRequired": True,
                "freshPrePromotionReadbackRequired": True,
                "recommendedPromotionState": "review-passed-awaiting-explicit-promotion-gate-and-fresh-readback",
            },
            "next": {"recommendedAction": "Refresh exact-target static/nav/API readbacks before turn-rate apply."},
            "artifacts": {
                "summaryJson": "scripts\\captures\\turn-rate-promotion-readiness-review-20260531-142900-000000\\summary.json",
                "summaryMarkdown": "scripts\\captures\\turn-rate-promotion-readiness-review-20260531-142900-000000\\summary.md",
            },
            "safety": {
                "movementSent": False,
                "inputSent": False,
                "targetMemoryBytesRead": False,
                "targetMemoryBytesWritten": False,
                "proofPromotion": False,
                "actorChainPromotion": False,
                "turnRatePromotion": False,
                "currentTruthWrite": False,
                "gitMutation": False,
            },
            "sourceSafety": {"movementSent": True, "inputSent": True, "targetMemoryBytesRead": True},
            "blockers": [],
            "warnings": ["turn-rate-candidate-only-no-promotion"],
        },
    )


def seed_ghidra_static_evidence(root: Path) -> None:
    write_json(
        root / "scripts" / "captures" / "ghidra-static-analysis-20260531-142900-000000" / "summary.json",
        {
            "kind": "riftreader-ghidra-static-evidence-run",
            "status": "passed",
            "generatedAtUtc": "2026-05-31T14:23:59Z",
            "summaryJson": "scripts\\captures\\ghidra-static-analysis-20260531-142900-000000\\summary.json",
            "summaryMarkdown": "scripts\\captures\\ghidra-static-analysis-20260531-142900-000000\\summary.md",
            "evidenceJson": "scripts\\captures\\ghidra-static-analysis-20260531-142900-000000\\pointer-evidence.json",
            "evidenceSummary": {
                "programName": "rift_x64.exe",
                "imageBase": "140000000",
                "rootAddress": "1432ebc80",
                "rootReferenceCountCaptured": 200,
                "rootReferenceTypes": {"READ": 101, "WRITE": 99},
                "instructionsScanned": 8057130,
                "offsets": {
                    "0x30C": {
                        "hitCount": 80,
                        "writeLikeCount": 26,
                        "firstHits": [
                            {
                                "address": "14003fa41",
                                "instruction": "MOV dword ptr [RDI + 0x30c],R13D",
                                "accessGuess": "write-or-destination",
                            }
                        ],
                    },
                    "0x320": {
                        "hitCount": 80,
                        "writeLikeCount": 22,
                        "firstHits": [
                            {
                                "address": "14003fa67",
                                "instruction": "MOV dword ptr [RDI + 0x320],R13D",
                                "accessGuess": "write-or-destination",
                            }
                        ],
                    },
                },
            },
            "warnings": ["ghidra-analysis-timeout-project-saved"],
            "blockers": [],
            "safety": {
                "offlineOnly": True,
                "movementSent": False,
                "inputSent": False,
                "targetMemoryBytesRead": False,
                "targetMemoryBytesWritten": False,
                "proofPromotion": False,
                "providerWrites": False,
            },
        },
    )


class NavigationPointerDiscoveryTests(unittest.TestCase):
    def test_build_summary_indexes_promoted_and_candidate_navigation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["kind"], "riftreader-navigation-pointer-discovery-status")
        candidates = summary["candidates"]
        self.assertFalse(candidates["promotedCoordinate"]["candidateOnly"])
        self.assertEqual(candidates["promotedCoordinate"]["coordinateOffset"], "0x320")
        self.assertEqual(candidates["promotedCoordinate"]["coordinate"], {"x": 1.0, "y": 2.0, "z": 3.0})
        self.assertTrue(candidates["candidateFacingTarget"]["candidateOnly"])
        self.assertEqual(candidates["candidateFacingTarget"]["offset"], "0x30C")
        self.assertEqual(candidates["candidateFacingTarget"]["comparisonMaxAbsYawDeltaDegrees"], 62.1)
        self.assertTrue(candidates["candidateTurnRate"]["candidateOnly"])
        self.assertEqual(candidates["candidateTurnRate"]["chainShape"], "[rift_x64+0x32EBC80]+0x304")
        self.assertEqual(candidates["candidateTurnRate"]["latestClassification"], "left")
        self.assertEqual(summary["navigationControlChains"]["turnRate"]["state"], "candidate")
        self.assertEqual(summary["navigationControlChains"]["supportFields"]["headingSupport0x300"]["latestValue"], 12.5)
        self.assertEqual(summary["candidateLedger"]["velocitySpeed"]["state"], "candidate")
        self.assertEqual(summary["candidateLedger"]["actorState"]["status"], "not-discovered")
        self.assertEqual(candidates["coordinateDeltaCandidate"]["status"], "confirms-promoted-coordinate-offset")
        self.assertEqual(candidates["coordinateDeltaCandidate"]["trackingErrorMaxAbs"], 0.006)
        self.assertEqual(candidates["cameraYawClassification"]["classification"], "visual-changed-static-yaw-unchanged")
        self.assertFalse(candidates["cameraYawClassification"]["actionableForRouteControl"])
        self.assertEqual(candidates["cameraYawClassification"]["changedFocusOffsetCount"], 2)
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["safety"]["gitMutation"])
        self.assertFalse(summary["safety"]["proofPromotion"])
        self.assertTrue(summary["sourceSafety"]["familySnapshotMovementSent"])
        self.assertTrue(summary["sourceSafety"]["cameraYawClassificationInputSent"])
        self.assertEqual(summary["freshness"]["status"], "fresh")
        self.assertEqual(summary["sources"]["coordinateReadback"]["freshness"]["status"], "fresh")
        self.assertEqual(summary["target"]["identitySource"], "latest-coordinate-and-nav-state-readbacks")

    def test_multipose_camera_yaw_report_is_preferred_for_route_next_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            seed_camera_yaw_multipose_report(root)

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        camera_yaw = summary["candidates"]["cameraYawClassification"]
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(camera_yaw["proofPackKind"], "multipose-camera-yaw-report")
        self.assertEqual(camera_yaw["routeActionablePoseCount"], 2)
        self.assertTrue(camera_yaw["candidateOnly"])
        self.assertFalse(camera_yaw["promotionAllowed"])
        self.assertEqual(summary["sources"]["cameraYawMultipose"]["status"], "passed")
        self.assertTrue(summary["sourceSafety"]["cameraYawClassificationInputSent"])
        self.assertTrue(any("three-pose gate" in item for item in summary["next"]["recommendedActions"]))
        self.assertFalse(any("Rerun a small camera/yaw proof pack" in item for item in summary["next"]["recommendedActions"]))

    def test_facing_gate_artifacts_are_indexed_and_shift_next_action_to_review_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            seed_camera_yaw_multipose_report(root)
            seed_facing_proof_gate_artifacts(root)

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        gates = summary["proofGates"]
        readiness = summary["promotionReadiness"]
        self.assertEqual(summary["status"], "passed")
        self.assertTrue(gates["facingThreePoseGate"]["formalThreePoseGatePassed"])
        self.assertTrue(gates["facingRestartSurvival"]["restartRelogSurvived"])
        self.assertEqual(1.5, gates["turnForwardExperiment"]["totalProgressDistance"])
        self.assertEqual("candidate-only-gates-packaged-requires-review", readiness["facingTarget"])
        self.assertEqual("passed", readiness["facingThreePoseGate"])
        self.assertEqual("passed", readiness["restartRelogSurvival"])
        self.assertEqual("passed", readiness["turnForwardLiveProgress"])
        self.assertIn("promotion-readiness review packet", summary["next"]["recommendedAction"])
        self.assertFalse(summary["safety"]["proofPromotion"])
        self.assertFalse(summary["safety"]["facingPromotion"])

    def test_turn_rate_review_packet_is_indexed_without_promoting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            seed_turn_rate_promotion_readiness_review(root)

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        review = summary["proofGates"]["turnRatePromotionReadinessReview"]
        self.assertEqual(summary["status"], "passed")
        self.assertTrue(review["reviewPassed"])
        self.assertFalse(review["promotionAllowed"])
        self.assertFalse(review["promotionPerformed"])
        self.assertEqual("passed", summary["promotionReadiness"]["turnRatePromotionReview"])
        self.assertEqual(
            "review-passed-awaiting-explicit-promotion-gate-and-fresh-readback",
            summary["promotionReadiness"]["turnRate"],
        )
        self.assertEqual("passed", summary["sources"]["turnRatePromotionReadinessReview"]["status"])
        self.assertEqual("candidate", summary["navigationControlChains"]["turnRate"]["state"])
        self.assertFalse(summary["safety"]["proofPromotion"])

    def test_facing_review_packet_shifts_next_action_to_explicit_gate_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            seed_camera_yaw_multipose_report(root)
            seed_facing_proof_gate_artifacts(root)
            seed_facing_promotion_readiness_review(root)

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        gates = summary["proofGates"]
        readiness = summary["promotionReadiness"]
        review = gates["facingPromotionReadinessReview"]
        self.assertEqual(summary["status"], "passed")
        self.assertTrue(review["reviewPassed"])
        self.assertFalse(review["promotionAllowed"])
        self.assertFalse(review["promotionPerformed"])
        self.assertEqual("passed", readiness["promotionReview"])
        self.assertEqual(
            "review-passed-awaiting-explicit-promotion-gate-and-fresh-readback",
            readiness["facingTarget"],
        )
        self.assertEqual(summary["sources"]["facingPromotionReadinessReview"]["status"], "passed")
        self.assertIn("explicit facing-promotion gate", summary["next"]["recommendedAction"])
        self.assertFalse(any("promotion-readiness review packet" in item for item in summary["next"]["recommendedActions"]))
        self.assertFalse(summary["safety"]["proofPromotion"])
        self.assertFalse(summary["safety"]["facingPromotion"])

    def test_promoted_facing_truth_is_projected_into_navigation_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            seed_camera_yaw_multipose_report(root)
            seed_facing_proof_gate_artifacts(root)
            seed_facing_promotion_readiness_review(root)
            promotion_path = root / "docs" / "recovery" / "static-owner-facing-yaw-promoted-2026-06-01.json"
            write_json(promotion_path, {"kind": "static-owner-facing-yaw-promotion", "status": "promoted"})
            comparison_path = (
                root
                / "scripts"
                / "captures"
                / "static-owner-facing-comparison-20260531-141949-380215"
                / "summary.json"
            )
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
            comparison["comparison"]["relativeTargetCandidates"][0]["address"] = "0x9999"
            comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
            truth_path = root / "docs" / "recovery" / "current-truth.json"
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            truth["staticOwnerFacing"] = {
                "status": "promoted-static-owner-facing-yaw-current-pid-readback-passed",
                "promotionAllowed": True,
                "promotedAtUtc": "2026-06-01T16:55:00Z",
                "latestPromotionAtUtc": "2026-06-01T16:55:00Z",
                "promotionArtifact": str(promotion_path),
                "latestPromotionReview": {
                    "status": "passed",
                    "promotionPerformed": True,
                    "readinessReviewJson": "review.json",
                },
                "primaryCandidate": {
                    "expression": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
                },
            }
            truth_path.write_text(json.dumps(truth), encoding="utf-8")

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        facing = summary["candidates"]["candidateFacingTarget"]
        self.assertEqual(summary["status"], "passed")
        self.assertEqual("promoted-static-owner-facing-yaw-current-pid-readback-passed", facing["status"])
        self.assertFalse(facing["candidateOnly"])
        self.assertTrue(facing["promotionAllowed"])
        self.assertEqual("0x130C", facing["address"])
        self.assertEqual("0x30C", facing["offsetFromOwner"])
        self.assertEqual(str(promotion_path), facing["promotionArtifact"])
        self.assertEqual(
            "promoted-static-owner-facing-yaw-current-pid-readback-passed",
            summary["promotionReadiness"]["facingTarget"],
        )
        self.assertFalse(summary["promotionReadiness"]["promotionReviewRequired"])
        self.assertTrue(summary["promotionReadiness"]["facingPromotionPerformed"])

    def test_ghidra_static_evidence_is_indexed_as_offline_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            seed_ghidra_static_evidence(root)

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        static_evidence = summary["proofGates"]["ghidraStaticEvidence"]
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["sources"]["ghidraStaticEvidence"]["status"], "passed")
        self.assertEqual("passed", summary["promotionReadiness"]["staticEvidence"])
        self.assertEqual("1432ebc80", static_evidence["rootAddress"])
        self.assertEqual(200, static_evidence["rootReferenceCountCaptured"])
        self.assertEqual(26, static_evidence["offsets"]["0x30C"]["writeLikeCount"])
        self.assertTrue(static_evidence["offlineOnly"])
        self.assertTrue(static_evidence["analysisTimedOutProjectSaved"])
        self.assertFalse(summary["safety"]["proofPromotion"])

    def test_promoted_coordinate_uses_latest_readback_coordinate_over_tracked_truth_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            truth_path = root / "docs" / "recovery" / "current-truth.json"
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            truth["staticChainStatus"]["primaryCandidate"]["coordinate"] = {"x": -1.0, "y": -2.0, "z": -3.0}
            truth_path.write_text(json.dumps(truth), encoding="utf-8")

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        self.assertEqual(summary["status"], "passed")
        promoted = summary["candidates"]["promotedCoordinate"]
        self.assertEqual(promoted["ownerAddress"], "0x1000")
        self.assertEqual(promoted["coordinateAddress"], "0x1320")
        self.assertEqual(promoted["coordinate"], {"x": 1.0, "y": 2.0, "z": 3.0})

    def test_target_identity_prefers_latest_readback_when_current_truth_pid_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            truth_path = root / "docs" / "recovery" / "current-truth.json"
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            truth["target"]["processId"] = 11111
            truth["target"]["targetWindowHandle"] = "0xBAD"
            truth_path.write_text(json.dumps(truth), encoding="utf-8")

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(25668, summary["target"]["processId"])
        self.assertEqual("0x320CB0", summary["target"]["targetWindowHandle"])
        self.assertEqual("latest-coordinate-and-nav-state-readbacks", summary["target"]["identitySource"])

    def test_freshness_classifies_stale_current_readbacks_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 16, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["freshness"]["status"], "stale")
        self.assertIn("coordinateReadback", summary["freshness"]["staleSources"])
        self.assertIn("navState", summary["freshness"]["staleSources"])
        self.assertNotIn("facingComparison", summary["freshness"]["staleSources"])

    def test_nested_facing_comparison_from_camera_yaw_run_can_refresh_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            nested_path = (
                root
                / "scripts"
                / "captures"
                / "static-owner-camera-yaw-classification-20260531-143000-000000"
                / "static-owner-facing-comparison-20260531-143001-000000"
                / "summary.json"
            )
            write_json(
                nested_path,
                {
                    "kind": "static-owner-facing-comparison",
                    "status": "passed",
                    "verdict": "static-owner-facing-candidates-scored",
                    "generatedAtUtc": "2026-05-31T14:30:01Z",
                    "comparison": {
                        "ownerAddresses": ["0x1000"],
                        "maxCoordinatePlanarDrift": 0.0,
                        "relativeTargetCandidates": [
                            {
                                "offset": "0x30C",
                                "address": "0x130C",
                                "yawDeltasFromBaseline": {"return": 33.8},
                                "maxAbsYawDeltaDegrees": 33.8,
                            }
                        ],
                        "scalarCandidates": [
                            {
                                "offset": "0x304",
                                "address": "0x1304",
                                "deltasFromBaseline": {"return": -0.59},
                                "maxAbsDelta": 0.59,
                            }
                        ],
                    },
                },
            )

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 31, tzinfo=timezone.utc),
            )

        facing = summary["candidates"]["candidateFacingTarget"]
        self.assertEqual("passed", summary["status"])
        self.assertNotIn("facingComparison", summary["freshness"]["staleSources"])
        self.assertIn("static-owner-camera-yaw-classification-20260531-143000-000000", summary["sources"]["facingComparison"]["path"])
        self.assertEqual(33.8, facing["comparisonMaxAbsYawDeltaDegrees"])

    def test_next_action_prioritizes_truth_refresh_when_only_current_truth_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            truth_path = root / "docs" / "recovery" / "current-truth.json"
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            truth["updatedAtUtc"] = "2026-05-31T13:00:00Z"
            truth_path.write_text(json.dumps(truth), encoding="utf-8")

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["freshness"]["staleSources"], ["currentTruth"])
        self.assertIn("current-truth refresh slice", summary["next"]["recommendedAction"])
        self.assertTrue(any("static-root proof" in item for item in summary["next"]["recommendedActions"]))
        self.assertTrue(any("camera-yaw classification" in item for item in summary["next"]["recommendedActions"]))

    def test_missing_artifacts_blocks_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)

            summary = discovery.build_navigation_pointer_discovery(root)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("navigation-pointer-evidence-missing", summary["blockers"])
        self.assertFalse(summary["safety"]["targetMemoryBytesRead"])

    def test_malformed_current_truth_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "docs" / "recovery").mkdir(parents=True)
            (root / "docs" / "recovery" / "current-truth.json").write_text("{bad", encoding="utf-8")

            summary = discovery.build_navigation_pointer_discovery(root)

        self.assertEqual(summary["status"], "failed")
        self.assertIn("current-truth-unreadable", summary["blockers"])
        self.assertTrue(any(item.startswith("current-truth-malformed") for item in summary["errors"]))

    def test_write_outputs_creates_json_and_markdown_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

            artifacts = discovery.write_outputs(root, summary, Path(".riftreader-local") / "navigation-pointer-discovery" / "latest")

            summary_json = root / artifacts["summaryJson"]
            summary_md = root / artifacts["summaryMarkdown"]
            loaded = json.loads(summary_json.read_text(encoding="utf-8"))
            markdown = summary_md.read_text(encoding="utf-8")

        self.assertEqual(loaded["status"], "passed")
        self.assertIn("Navigation Pointer Discovery Status", markdown)
        self.assertIn("Candidate summary", markdown)
        self.assertIn("Camera/yaw classification", markdown)
        self.assertIn("Freshness", markdown)
        self.assertIn("Recommended action list", markdown)
        self.assertIn("Next action", markdown)

    def test_main_self_test_json_passes(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = discovery.main(["--self-test", "--json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "passed")
        self.assertFalse(payload["safety"]["proofPromotion"])


if __name__ == "__main__":
    unittest.main()
