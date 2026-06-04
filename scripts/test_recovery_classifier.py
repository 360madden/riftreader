#!/usr/bin/env python3
# Version: riftreader-test-recovery-classifier-v0.1.0
# Total-Character-Count: 0000002407
# Purpose: Unit tests for the RiftReader recovery classifier.

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow.recovery_classifier import build_self_test, classify, evidence_from_status  # noqa: E402


class RecoveryClassifierTests(unittest.TestCase):
    def test_static_chain_repair_classification(self) -> None:
        status = {
            "workflowClassification": {
                "classification": "static-chain-repair-needed",
                "blocker": "static-chain-repair-needed:root-pointer-null",
                "proofAnchorCurrent": True,
                "staticOwnerRootNull": True,
            }
        }
        decision = classify(status, compact_status_path=None)
        self.assertEqual(decision.name, "static-chain-repair-needed")
        self.assertIn("do not rerun proof-anchor recovery", " ".join(decision.do_not_do).lower())

    def test_proof_reacquire_classification(self) -> None:
        status = {
            "workflowClassification": {
                "proofAnchorCurrent": False,
                "staticOwnerRootNull": True,
            },
            "blockers": ["proof-anchor-stale"],
        }
        self.assertEqual(classify(status, compact_status_path=None).name, "proof-reacquire-needed")

    def test_status_refresh_needed(self) -> None:
        self.assertEqual(classify({}, compact_status_path=None).name, "status-refresh-needed")

    def test_evidence_extracts_nested_fields(self) -> None:
        status = {
            "workflowClassification": {"proofAnchorCurrent": True},
            "currentProof": {"targetPid": 123},
            "staticOwnerReadback": {"coordinateChain": {"verdict": "blocked"}},
        }
        evidence = evidence_from_status(status)
        self.assertTrue(evidence["proofAnchorCurrent"])
        self.assertEqual(evidence["currentProof"]["targetPid"], 123)
        self.assertEqual(evidence["staticOwnerCoordinateChain"]["verdict"], "blocked")

    def test_self_test_passes(self) -> None:
        self.assertEqual(build_self_test()["status"], "passed")


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
