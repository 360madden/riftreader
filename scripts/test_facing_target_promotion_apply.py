#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import facing_target_promotion_apply as helper  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seed_fixture(root: Path, *, stale_api: bool = False) -> tuple[Path, Path, Path]:
    target = {
        "processName": "rift_x64",
        "processId": 41808,
        "targetWindowHandle": "0x2B0A26",
        "processStartUtc": "2026-06-01T01:50:50Z",
        "moduleBase": "0x7FF6EE5D0000",
    }
    truth_path = root / "docs" / "recovery" / "current-truth.json"
    dashboard_path = root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.json"
    readiness_path = (
        root
        / "scripts"
        / "captures"
        / "facing-target-promotion-readiness-review-20260601-165301-000000"
        / "summary.json"
    )
    write_json(
        truth_path,
        {
            "kind": "riftreader-current-truth",
            "updatedAtUtc": "2026-06-01T16:50:00Z",
            "target": target,
            "currentWarnings": ["facing-promotion-is-candidate-only-without-independent-truth-surface-reference"],
            "staticOwnerFacing": {
                "status": "candidate-only",
                "promotionAllowed": False,
                "primaryCandidate": {
                    "expression": helper.REQUIRED_CHAIN,
                    "yawFormula": "atan2(Z_at_0x314 - playerZ_at_0x328, X_at_0x30C - playerX_at_0x320)",
                },
            },
        },
    )
    write_json(
        dashboard_path,
        {
            "kind": "riftreader-navigation-pointer-discovery-status",
            "status": "passed",
            "target": target,
            "sources": {
                "coordinateReadback": {"freshness": {"status": "fresh"}},
                "navState": {"freshness": {"status": "fresh"}},
                "apiReference": {"freshness": {"status": "stale" if stale_api else "fresh"}},
                "facingPromotionReadinessReview": {"freshness": {"status": "fresh"}},
            },
            "candidates": {
                "promotedCoordinate": {
                    "promotionAllowed": True,
                    "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed",
                    "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                    "ownerAddress": "0x1000",
                    "coordinateAddress": "0x1320",
                    "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "apiNowStatus": "passed-current-pid-41808-api-now-vs-chain-now",
                    "apiNowComparison": {
                        "apiReferenceJson": "api.json",
                        "maxAbsDelta": 0.004,
                        "withinTolerance": True,
                    },
                },
                "candidateFacingTarget": {
                    "ownerAddress": "0x1000",
                    "address": "0x130C",
                    "latestYawDegrees": 80.5,
                    "latestPitchDegrees": 4.9,
                    "planarLookaheadDistance": 9.96,
                    "evidence": {"navStateJson": "nav.json", "facingComparisonJson": "facing.json"},
                },
            },
            "proofGates": {
                "facingThreePoseGate": {"formalThreePoseGatePassed": True, "evidence": {"summaryJson": "three.json"}},
                "facingRestartSurvival": {"restartRelogSurvived": True, "evidence": {"summaryJson": "restart.json"}},
                "turnForwardExperiment": {"status": "passed", "evidence": {"summaryJson": "turn.json"}},
                "ghidraStaticEvidence": {"status": "passed", "summaryJson": "ghidra.json"},
            },
        },
    )
    write_json(
        readiness_path,
        {
            "kind": "facing-target-promotion-readiness-review-packet",
            "status": "passed",
            "generatedAtUtc": "2026-06-01T16:53:01Z",
            "target": target,
            "candidate": {
                "chainExpression": helper.REQUIRED_CHAIN,
                "offset": helper.REQUIRED_OFFSET,
                "apiNowStatus": "passed-current-pid-41808-api-now-vs-chain-now",
            },
            "promotionDecision": {"reviewPassed": True, "promotionPerformed": False},
            "blockers": [],
            "errors": [],
        },
    )
    return truth_path, dashboard_path, readiness_path


class FacingTargetPromotionApplyTests(unittest.TestCase):
    def test_apply_writes_promotion_artifact_and_updates_current_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            truth_path, dashboard_path, readiness_path = seed_fixture(root)
            promotion_path = root / "docs" / "recovery" / "static-owner-facing-yaw-promoted-2026-06-01.json"
            args = type(
                "Args",
                (),
                {
                    "apply": True,
                    "readiness_json": readiness_path,
                    "dashboard_json": dashboard_path,
                    "current_truth_json": truth_path,
                    "output_dir": root / ".riftreader-local" / "apply",
                    "promotion_json": promotion_path,
                },
            )()

            summary, exit_code = helper.build_summary(args, root)
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            artifact = json.loads(promotion_path.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual("facing-target-promotion-applied", summary["verdict"])
        self.assertEqual("promoted", artifact["status"])
        self.assertTrue(artifact["safety"]["facingPromotion"])
        self.assertTrue(truth["staticOwnerFacing"]["promotionAllowed"])
        self.assertEqual(str(promotion_path), truth["staticOwnerFacing"]["promotionArtifact"])
        self.assertTrue(truth["staticOwnerFacing"]["latestCurrentReacquisition"]["promotionPerformed"])
        self.assertNotIn(
            "facing-promotion-is-candidate-only-without-independent-truth-surface-reference",
            truth["currentWarnings"],
        )

    def test_apply_blocks_on_stale_api_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            truth_path, dashboard_path, readiness_path = seed_fixture(root, stale_api=True)
            args = type(
                "Args",
                (),
                {
                    "apply": True,
                    "readiness_json": readiness_path,
                    "dashboard_json": dashboard_path,
                    "current_truth_json": truth_path,
                    "output_dir": root / ".riftreader-local" / "apply",
                    "promotion_json": root / "docs" / "recovery" / "promotion.json",
                },
            )()

            summary, exit_code = helper.build_summary(args, root)

        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", summary["status"])
        self.assertIn("dashboard-source-not-fresh:apiReference:stale", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
