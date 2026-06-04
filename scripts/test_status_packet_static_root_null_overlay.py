# Version: riftreader-test-status-static-root-null-overlay-v0.1.0
# Total-Character-Count: 0000003665
# Purpose: Unit tests for status_packet static-root-null workflow classification overlay.
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow import status_packet  # noqa: E402


class StatusStaticRootNullOverlayTests(unittest.TestCase):
    def test_proof_target_matches_live_target(self) -> None:
        proof = {"status": "current-target-proofonly-passed", "target": {"processId": 77152}}
        live = {"livePids": [77152], "artifactPidStale": True}
        self.assertTrue(status_packet.proof_target_matches_live_target(proof, live))

    def test_static_root_null_classifies_static_chain_repair(self) -> None:
        proof = {
            "status": "current-target-proofonly-passed",
            "target": {"processId": 77152, "targetWindowHandle": "0x17A0DB2"},
        }
        live = {
            "artifactPidStale": True,
            "artifactPid": 12664,
            "artifactHwnd": "0x205146C",
            "livePids": [77152],
        }
        static_owner = {
            "coordinateChain": {
                "status": "blocked",
                "verdict": "root-pointer-null",
                "blockers": ["root-pointer-null"],
            }
        }
        classification = status_packet.classify_workflow_state(
            current_proof_summary=proof,
            live_target=live,
            static_owner_readback=static_owner,
            navigation_pointer_discovery={},
            current_truth_refresh_plan={},
        )
        self.assertEqual(classification["classification"], "static-chain-repair-needed")
        self.assertEqual(classification["blocker"], "static-chain-repair-needed:root-pointer-null")
        self.assertTrue(classification["proofAnchorCurrent"])
        self.assertTrue(classification["staticOwnerRootNull"])
        self.assertIn("Repair the static pointer chain", classification["nextRecommendedAction"])

    def test_stale_reason_can_label_current_truth_artifact(self) -> None:
        live = {"livePids": [77152], "artifactPid": 12664, "artifactHwnd": "0x205146C"}
        reason = status_packet.stale_live_target_reason(
            live,
            artifact_label="current-truth/status coordinate artifact",
        )
        self.assertIn("current-truth/status coordinate artifact", reason)
        self.assertNotIn("current proof artifact points", reason)

    def test_compact_summary_exposes_workflow_classification(self) -> None:
        packet = {
            "generatedAtUtc": "2026-06-04T00:00:00Z",
            "status": "blocked",
            "repoRoot": str(ROOT),
            "git": {"status": {}, "head": {}},
            "currentProof": {"summary": {}},
            "currentTruth": {"summary": {}},
            "workflowClassification": {
                "classification": "static-chain-repair-needed",
                "blocker": "static-chain-repair-needed:root-pointer-null",
            },
            "latestHandoff": {},
            "liveTarget": {},
            "opencode": {},
            "launcher": {},
            "characterLoginSupervisor": {},
            "staticOwnerReadback": {},
            "navigationPointerDiscovery": {},
            "currentTruthRefreshPlan": {},
            "currentTruthRefreshApply": {},
            "facingPromotionReadinessReview": {},
            "blockers": [],
            "warnings": [],
            "errors": [],
            "safety": {},
        }
        compact = status_packet.compact_summary(packet)
        self.assertEqual(
            compact["workflowClassification"]["classification"],
            "static-chain-repair-needed",
        )


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
