#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import turn_rate_promotion_apply as helper  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seed_fixture(root: Path, *, stale_api: bool = False) -> tuple[Path, Path, Path]:
    target = {
        "processId": 1,
        "targetWindowHandle": "0x1",
        "processStartUtc": "2026-06-01T00:00:00Z",
        "moduleBase": "0x1000",
    }
    truth = root / "docs" / "recovery" / "current-truth.json"
    dashboard = root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.json"
    readiness = root / "scripts" / "captures" / "turn-rate-promotion-readiness-review-fixture" / "summary.json"
    write_json(truth, {"kind": "riftreader-current-truth", "target": target, "currentWarnings": ["turn-rate-candidate-only-without-independent-promotion-artifact"]})
    write_json(
        dashboard,
        {
            "kind": "riftreader-navigation-pointer-discovery-status",
            "status": "passed",
            "target": target,
            "sources": {
                "coordinateReadback": {"freshness": {"status": "fresh"}},
                "navState": {"freshness": {"status": "fresh"}},
                "apiReference": {"freshness": {"status": "stale" if stale_api else "fresh"}},
            },
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
            "candidate": {"offset": "0x304", "latestValue": 0.0, "latestClassification": "stationary"},
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
    return truth, dashboard, readiness


class TurnRatePromotionApplyTests(unittest.TestCase):
    def test_apply_writes_promotion_artifact_and_updates_current_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            truth, dashboard, readiness = seed_fixture(root)
            promotion = root / "docs" / "recovery" / "static-owner-turn-rate-promoted-2026-06-01.json"
            args = type(
                "Args",
                (),
                {
                    "apply": True,
                    "readiness_json": readiness,
                    "dashboard_json": dashboard,
                    "current_truth_json": truth,
                    "output_dir": root / ".local" / "apply",
                    "promotion_json": promotion,
                },
            )()
            summary, exit_code = helper.build_summary(args, root)
            promoted_truth = json.loads(truth.read_text(encoding="utf-8"))
            artifact = json.loads(promotion.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual("turn-rate-promotion-applied", summary["verdict"])
        self.assertEqual("promoted", artifact["status"])
        self.assertTrue(promoted_truth["staticOwnerTurnRate"]["promotionAllowed"])
        self.assertTrue(promoted_truth["navigationControlChains"]["turnRate"]["promotionAllowed"])
        self.assertFalse(artifact["safety"]["navigationControl"])

    def test_apply_blocks_on_stale_api_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            truth, dashboard, readiness = seed_fixture(root, stale_api=True)
            args = type(
                "Args",
                (),
                {
                    "apply": True,
                    "readiness_json": readiness,
                    "dashboard_json": dashboard,
                    "current_truth_json": truth,
                    "output_dir": root / ".local" / "apply",
                    "promotion_json": root / "docs" / "recovery" / "promotion.json",
                },
            )()
            summary, exit_code = helper.build_summary(args, root)

        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", summary["status"])
        self.assertIn("dashboard-source-not-fresh:apiReference:stale", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
