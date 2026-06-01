#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import owner_0x304_semantics_review as review  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seed_artifacts(root: Path, *, include_owner304: bool = True) -> tuple[Path, Path, Path]:
    multipose = root / "scripts" / "captures" / "static-owner-camera-yaw-multipose-report-20260601-000000-000000" / "summary.json"
    right_offsets = [{"offset": "0x300", "delta": 1.0}]
    left_offsets = [{"offset": "0x300", "delta": 1.0}]
    if include_owner304:
        right_offsets.append({"offset": "0x304", "delta": -math.radians(25.0), "absDelta": math.radians(25.0)})
        left_offsets.append({"offset": "0x304", "delta": math.radians(25.0), "absDelta": math.radians(25.0)})
    write_json(
        multipose,
        {
            "kind": "static-owner-camera-yaw-multipose-report",
            "status": "passed",
            "verdict": "route-actionable-candidate-present-needs-proof",
            "generatedAtUtc": "2026-06-01T00:00:00Z",
            "sourceSafety": {"inputSent": True, "movementSent": True, "targetMemoryBytesRead": True},
            "poses": [
                {
                    "summaryJson": "right.json",
                    "stimulus": {"direction": "right"},
                    "classification": "visual-and-static-yaw-changed",
                    "staticYawChanged": True,
                    "signedYawDeltaDegrees": 25.0,
                    "changedFocusOffsets": right_offsets,
                },
                {
                    "summaryJson": "left.json",
                    "stimulus": {"direction": "left"},
                    "classification": "visual-and-static-yaw-changed",
                    "staticYawChanged": True,
                    "signedYawDeltaDegrees": -25.0,
                    "changedFocusOffsets": left_offsets,
                },
            ],
        },
    )
    turn_review = root / "scripts" / "captures" / "turn-rate-promotion-readiness-review-20260601-000100-000000" / "summary.json"
    write_json(
        turn_review,
        {
            "kind": "turn-rate-promotion-readiness-review-packet",
            "status": "blocked",
            "verdict": "candidate-turn-rate-review-not-ready",
            "generatedAtUtc": "2026-06-01T00:01:00Z",
            "promotionDecision": {"reviewPassed": False, "promotionAllowed": False, "promotionPerformed": False},
            "blockers": ["left-turn-rate-delta-proof-too-small:0.0"],
            "artifacts": {"summaryJson": str(turn_review)},
        },
    )
    nav_state = root / "scripts" / "captures" / "static-owner-nav-state-20260601-000200-000000" / "summary.json"
    write_json(
        nav_state,
        {
            "kind": "static-owner-nav-state-readback",
            "status": "passed",
            "generatedAtUtc": "2026-06-01T00:02:00Z",
            "latestState": {
                "turnRate0x304": 0.7,
                "turnRateClassification": "left",
                "turnRateDiscriminator": {"direction": "left", "turning": True, "rate": 0.7},
            },
            "analysis": {"maxPlanarDelta": 0.0, "yawRangeDegrees": 0.0, "maxAbsYawDeltaDegrees": 0.0},
            "artifacts": {"summaryJson": str(nav_state)},
        },
    )
    return multipose, turn_review, nav_state


class Owner304SemanticsReviewTests(unittest.TestCase):
    def test_current_evidence_classifies_0x304_as_yaw_adjacent_not_turn_rate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            multipose, turn_review, nav_state = seed_artifacts(root)
            args = review.build_parser().parse_args(
                [
                    "--repo-root",
                    str(root),
                    "--camera-yaw-multipose-summary-json",
                    str(multipose),
                    "--turn-rate-review-summary-json",
                    str(turn_review),
                    "--nav-state-summary-json",
                    str(nav_state),
                ]
            )

            summary = review.build_summary(args)

        self.assertEqual("passed", summary["status"])
        self.assertEqual("owner-0x304-yaw-adjacent-scalar-not-active-turn-rate", summary["verdict"])
        analysis = summary["analysis"]
        self.assertEqual("yaw-adjacent-opposes-promoted-yaw-radians", analysis["classification"])
        self.assertEqual("yaw-adjacent-scalar-candidate", analysis["owner304Role"])
        self.assertFalse(analysis["promotionAllowed"])
        self.assertFalse(analysis["activeTurnRatePromotionAllowed"])
        self.assertTrue(analysis["turnRateReadinessContrast"]["deltaProofBlocked"])
        self.assertFalse(analysis["stationaryNavStateReview"]["legacyTurnClassifierReliable"])
        self.assertIn("legacy-0x304-sign-classifier-reports-turning-while-stationary", summary["warnings"])
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["safety"]["targetMemoryBytesRead"])

    def test_missing_owner304_pose_delta_blocks_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            multipose, turn_review, nav_state = seed_artifacts(root, include_owner304=False)
            args = review.build_parser().parse_args(
                [
                    "--repo-root",
                    str(root),
                    "--camera-yaw-multipose-summary-json",
                    str(multipose),
                    "--turn-rate-review-summary-json",
                    str(turn_review),
                    "--nav-state-summary-json",
                    str(nav_state),
                ]
            )

            summary = review.build_summary(args)

        self.assertEqual("blocked", summary["status"])
        self.assertIn("owner-0x304-pose-delta-evidence-missing", summary["blockers"])
        self.assertFalse(summary["safety"]["inputSent"])


if __name__ == "__main__":
    unittest.main()
