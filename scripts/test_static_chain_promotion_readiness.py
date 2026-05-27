from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rift_live_test.static_chain_promotion_readiness import build_markdown, build_summary_from_documents


NOW = datetime(2026, 5, 27, 20, 0, 0, tzinfo=UTC)


def base_truth(*, promotion_allowed: bool = False, latest_refresh_status: str | None = None) -> dict:
    latest_refresh = {}
    if latest_refresh_status:
        latest_refresh = {
            "status": latest_refresh_status,
            "rrapicoordBlockers": ["rrapicoord-no-usable-marker"] if latest_refresh_status == "blocked" else [],
            "chromalinkBlockers": ["world-state-player-position-stale"] if latest_refresh_status == "blocked" else [],
            "doesNotPromote": True,
        }
    return {
        "target": {
            "processName": "rift_x64",
            "processId": 34176,
            "targetWindowHandle": "0x3D1544",
            "processStartUtc": "2026-05-27T18:06:53Z",
            "moduleBase": "0x7FF77AF40000",
            "live": True,
            "inWorld": True,
        },
        "staticChainStatus": {
            "status": "promotion-review-ready-not-promoted",
            "promotionAllowed": promotion_allowed,
            "primaryCandidate": {
                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                "rootModule": "rift_x64.exe",
                "rootRva": "0x32EBC80",
                "rootAddress": "0x7FF77E22BC80",
                "ownerAddress": "0x278C3830010",
                "coordinateAddress": "0x278C3830330",
                "restartRelogSurvived": True,
            },
            "latestApiNowValidation": {"status": "passed"},
            "latestFreshApiSourceRefreshAttempt": latest_refresh,
        },
    }


def promotion_review(*, captured_at: datetime | None = None) -> dict:
    captured = captured_at or (NOW - timedelta(seconds=10))
    captured_text = captured.isoformat().replace("+00:00", "Z")
    return {
        "status": "ready-for-explicit-promotion-approval-not-promoted",
        "verdict": "promotion-evidence-ready-but-not-applied",
        "candidate": {
            "expression": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
            "rootRva": "0x32EBC80",
        },
        "target": {
            "processName": "rift_x64",
            "processId": 34176,
            "targetWindowHandle": "0x3D1544",
            "processStartUtc": "2026-05-27T18:06:53Z",
            "moduleBase": "0x7FF77AF40000",
        },
        "finalFreshSample": {
            "apiNow": {
                "status": "captured",
                "capturedAtUtc": captured_text,
                "coordinate": {"x": 7259.9497, "y": 821.44, "z": 2990.3799},
                "movementSent": False,
                "savedVariablesUse": "none",
                "noCheatEngine": True,
            },
            "chainNow": {
                "status": "passed",
                "capturedAtUtc": captured_text,
                "coordinate": {"x": 7259.94970703125, "y": 821.4375610351562, "z": 2990.375732421875},
                "movementSent": False,
                "noCheatEngine": True,
            },
            "comparison": {
                "maxAbsDelta": 0.004167578124906868,
                "tolerance": 0.25,
                "withinTolerance": True,
            },
        },
        "promotionPlan": {"approved": False, "applied": False},
    }


class StaticChainPromotionReadinessTests(unittest.TestCase):
    def test_ready_fresh_review_still_requires_explicit_approval(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(),
            promotion_review=promotion_review(),
            proof={"target": {"processId": 12148, "targetWindowHandle": "0x640C0C"}, "status": "current-target-proofonly-passed"},
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["verdict"], "ready-for-explicit-promotion-approval")
        self.assertIn("explicit-promotion-approval-required", summary["blockers"])
        self.assertFalse(summary["promotionGates"]["staleProofPointerUsed"])
        self.assertIn("stale-proof-pointer-ignored", summary["warnings"])

    def test_promoted_fresh_review_passes_without_using_stale_proof_pointer(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(promotion_allowed=True),
            promotion_review=promotion_review(),
            proof={"target": {"processId": 12148, "targetWindowHandle": "0x640C0C"}, "status": "current-target-proofonly-passed"},
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["verdict"], "static-chain-promotion-gates-passed")
        self.assertTrue(summary["promotionGates"]["promotionAllowed"])
        self.assertFalse(summary["promotionGates"]["staleProofPointerUsed"])

    def test_latest_blocked_fresh_api_attempt_blocks_historical_review_reuse(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(latest_refresh_status="blocked"),
            promotion_review=promotion_review(),
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["verdict"], "blocked-fresh-api-reference-unavailable")
        self.assertIn("latest-fresh-api-source-refresh-blocked", summary["blockers"])
        self.assertIn("rrapicoord:rrapicoord-no-usable-marker", summary["blockers"])
        self.assertFalse(summary["promotionGates"]["freshApiNowVsChainNowCurrent"])

    def test_stale_final_sample_blocks_promotion_readiness(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(),
            promotion_review=promotion_review(captured_at=NOW - timedelta(seconds=900)),
            max_sample_age_seconds=300,
            now=NOW,
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["verdict"], "blocked-fresh-api-sample-stale")
        self.assertTrue(any(blocker.startswith("api-now-sample-too-old") for blocker in summary["blockers"]))
        self.assertTrue(any(blocker.startswith("chain-now-sample-too-old") for blocker in summary["blockers"]))

    def test_markdown_contains_chain_and_safety_boundary(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth=base_truth(latest_refresh_status="blocked"),
            promotion_review=promotion_review(),
            max_sample_age_seconds=300,
            now=NOW,
        )
        markdown = build_markdown(summary)

        self.assertIn("[rift_x64+0x32EBC80]+0x320/+0x324/+0x328", markdown)
        self.assertIn("does not send input", markdown)
        self.assertIn("latest-fresh-api-source-refresh-blocked", markdown)


if __name__ == "__main__":
    unittest.main()
