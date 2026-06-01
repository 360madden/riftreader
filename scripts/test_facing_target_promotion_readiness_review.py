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

import facing_target_promotion_readiness_review as review  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_inputs(root: Path, *, restart_survived: bool = True) -> dict[str, Path]:
    nav = root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.json"
    three = root / "scripts" / "captures" / "facing-target-three-pose-gate-fixture" / "summary.json"
    restart = root / "scripts" / "captures" / "facing-target-restart-survival-packet-fixture" / "summary.json"
    turn = root / "scripts" / "captures" / "static-owner-turn-forward-experiment-fixture" / "summary.json"
    source = root / "docs" / "recovery" / "source-site.md"
    pointer = root / "docs" / "recovery" / "pointer.md"
    write_json(
        nav,
        {
            "kind": "riftreader-navigation-pointer-discovery-status",
            "status": "passed",
            "target": {"processId": 41808, "targetWindowHandle": "0x2B0A26"},
            "candidates": {
                "promotedCoordinate": {
                    "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed",
                    "promotionAllowed": True,
                    "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                    "apiNowStatus": "passed-current-pid-41808-api-now-vs-chain-now",
                },
                "candidateFacingTarget": {
                    "status": "candidate-only",
                    "candidateOnly": True,
                    "promotionAllowed": False,
                    "chainShape": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
                    "offset": "0x30C",
                    "latestYawDegrees": 75.1,
                },
            },
            "proofGates": {},
        },
    )
    write_json(
        three,
        {
            "kind": "facing-target-three-pose-gate",
            "status": "passed",
            "verdict": "formal-three-pose-route-progress-gate-passed",
            "poseCount": 3,
            "passedPoseCount": 3,
            "analysis": {
                "formalThreePoseGatePassed": True,
                "aggregateProgressDistance": 4.7,
                "minimumProgressDistance": 1.5,
                "promotionAllowed": False,
            },
            "sourceSafety": {"movementSent": True, "inputSent": True},
            "safety": {"movementSent": False, "inputSent": False},
        },
    )
    write_json(
        restart,
        {
            "kind": "facing-target-restart-survival-packet",
            "status": "passed" if restart_survived else "blocked",
            "verdict": "candidate-facing-target-restart-relog-survival-passed",
            "analysis": {
                "restartRelogSurvived": restart_survived,
                "offsetsStable": True,
                "processStartChanged": restart_survived,
                "ownerAddressChanged": True,
                "facingTargetOffset": "0x30C",
                "promotionAllowed": False,
            },
            "sourceSafety": {"targetMemoryBytesRead": True},
            "safety": {"movementSent": False, "inputSent": False},
        },
    )
    write_json(
        turn,
        {
            "kind": "static-owner-turn-forward-experiment",
            "status": "passed",
            "verdict": "turn-forward-live-progress-validated",
            "operator": {"movementApproved": True, "turnApproved": True},
            "forwardResult": {"routeStatus": "progress", "totalProgressDistance": 1.5},
            "safety": {"movementSent": True, "inputSent": True},
        },
    )
    doc_text = (
        "supporting evidence only 0x32EBC80 0x30C 0x310 0x314 "
        "0x320 0x324 0x328 Promotion performed | `false`"
    )
    write_text(source, doc_text)
    write_text(pointer, doc_text)
    return {
        "nav": nav,
        "three": three,
        "restart": restart,
        "turn": turn,
        "source": source,
        "pointer": pointer,
    }


def make_args(paths: dict[str, Path]) -> object:
    return type(
        "Args",
        (),
        {
            "navigation_summary_json": str(paths["nav"]),
            "three_pose_gate_summary_json": str(paths["three"]),
            "restart_survival_summary_json": str(paths["restart"]),
            "turn_forward_summary_json": str(paths["turn"]),
            "static_source_site_md": str(paths["source"]),
            "static_pointer_evidence_md": str(paths["pointer"]),
        },
    )()


class FacingTargetPromotionReadinessReviewTests(unittest.TestCase):
    def test_review_passes_without_allowing_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paths = write_inputs(root)

            summary, exit_code = review.build_review_packet(make_args(paths), root, root / "scripts" / "captures" / "review")

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", summary["status"])
        self.assertTrue(summary["promotionDecision"]["reviewPassed"])
        self.assertFalse(summary["promotionDecision"]["promotionAllowed"])
        self.assertFalse(summary["promotionDecision"]["promotionPerformed"])
        self.assertTrue(summary["promotionDecision"]["explicitPromotionGateRequired"])
        self.assertTrue(summary["reviewGates"]["restartRelogSurvival"]["passed"])
        self.assertTrue(summary["sourceSafety"]["movementSent"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["inputSent"])

    def test_review_blocks_when_restart_survival_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paths = write_inputs(root, restart_survived=False)

            summary, exit_code = review.build_review_packet(make_args(paths), root, root / "scripts" / "captures" / "review")

        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", summary["status"])
        self.assertFalse(summary["promotionDecision"]["reviewPassed"])
        self.assertIn("restart-relog-survival-not-passed", summary["blockers"])
        self.assertFalse(summary["promotionDecision"]["promotionAllowed"])

    def test_main_self_test_json_passes(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = review.main(["--self-test", "--json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("passed", payload["status"])
        self.assertTrue(payload["checks"]["reviewPassed"])
        self.assertFalse(payload["checks"]["promotionAllowed"])
        self.assertFalse(payload["checks"]["helperInputSent"])


if __name__ == "__main__":
    unittest.main()
