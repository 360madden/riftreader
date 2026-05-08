from __future__ import annotations

import json
import unittest
from pathlib import Path


class CurrentProofPointerTests(unittest.TestCase):
    def test_current_proof_pointer_preserves_riftscan_candidate_source(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        pointer_file = repo_root / "docs" / "recovery" / "current-proof-anchor-readback.json"
        pointer = json.loads(pointer_file.read_text(encoding="utf-8-sig"))

        self.assertEqual(pointer.get("mode"), "current-proof-anchor-readback-pointer")
        self.assertIsInstance(pointer.get("target"), dict)
        self.assertGreater(int(pointer["target"].get("processId") or 0), 0)

        source = pointer.get("riftscanCandidateSource")
        self.assertIsInstance(source, dict)
        self.assertTrue(source.get("matchFile"))
        self.assertTrue(source.get("candidateId"))
        self.assertTrue(source.get("sourceAbsoluteAddressHex"))

        latest_proof = pointer.get("latestProofOnly")
        self.assertIsInstance(latest_proof, dict)
        self.assertEqual(latest_proof.get("status"), "passed-proof-only")
        self.assertTrue(latest_proof.get("runSummaryFile"))
        self.assertTrue(latest_proof.get("readbackSummaryFile"))


if __name__ == "__main__":
    unittest.main()
