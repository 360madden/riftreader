#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import turn_rate_promotion_readiness_review as review  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seed_inputs(root: Path, *, right_sign: bool = True) -> dict[str, Path]:
    nav = root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.json"
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
    for path, direction, ok in ((left, "left", True), (right, "right", right_sign)):
        write_json(
            path,
            {
                "kind": "static-owner-turn-stimulus-capture",
                "status": "passed",
                "analysis": {
                    "status": "passed",
                    "direction": direction,
                    "absoluteYawDeltaDegrees": 12.0,
                    "signedYawDeltaDegrees": -12.0 if direction == "left" else 12.0,
                    "turnRateSignMatchedDirection": ok,
                    "turnRateDelta": 1.0 if direction == "left" else -1.0,
                },
                "safety": {"movementSent": True, "inputSent": True, "targetMemoryBytesWritten": False},
                "artifacts": {"summaryJson": str(path)},
            },
        )
    static_doc.parent.mkdir(parents=True, exist_ok=True)
    static_doc.write_text("root 0x32EBC80 turn-rate 0x304 source site", encoding="utf-8")
    return {"nav": nav, "left": left, "right": right, "static": static_doc}


def make_args(paths: dict[str, Path]) -> object:
    return type(
        "Args",
        (),
        {
            "navigation_summary_json": paths["nav"],
            "left_turn_summary_json": paths["left"],
            "right_turn_summary_json": paths["right"],
            "static_source_site_md": paths["static"],
            "static_pointer_evidence_md": None,
        },
    )()


class TurnRatePromotionReadinessReviewTests(unittest.TestCase):
    def test_review_passes_without_allowing_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paths = seed_inputs(root)
            summary, exit_code = review.build_review_packet(make_args(paths), root, root / "out")

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", summary["status"])
        self.assertTrue(summary["promotionDecision"]["reviewPassed"])
        self.assertFalse(summary["promotionDecision"]["promotionAllowed"])
        self.assertFalse(summary["promotionDecision"]["promotionPerformed"])
        self.assertTrue(summary["reviewGates"]["leftRightSignFlip"]["passed"])
        self.assertFalse(summary["safety"]["inputSent"])

    def test_review_blocks_without_right_sign_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paths = seed_inputs(root, right_sign=False)
            summary, exit_code = review.build_review_packet(make_args(paths), root, root / "out")

        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", summary["status"])
        self.assertIn("right-turn-rate-sign-proof-missing", summary["blockers"])

    def test_main_self_test_json_passes(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = review.main(["--self-test", "--json"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("passed", payload["status"])
        self.assertTrue(payload["checks"]["reviewPassed"])


if __name__ == "__main__":
    unittest.main()
