from __future__ import annotations

import json
import unittest
from pathlib import Path


class CurrentProofPointerTests(unittest.TestCase):
    def test_current_proof_pointer_is_either_current_proof_or_explicit_blocker(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        pointer_file = repo_root / "docs" / "recovery" / "current-proof-anchor-readback.json"
        pointer = json.loads(pointer_file.read_text(encoding="utf-8-sig"))

        self.assertEqual(pointer.get("mode"), "current-proof-anchor-readback-pointer")
        self.assertIsInstance(pointer.get("target"), dict)
        self.assertGreater(int(pointer["target"].get("processId") or 0), 0)

        if pointer.get("status") == "blocked-target-drift":
            classification = pointer.get("currentTruthClassification")
            self.assertIsInstance(classification, dict)
            self.assertEqual(classification.get("classification"), "stale-target-drift-blocker")
            self.assertFalse(classification.get("movementAllowed"))
            self.assertEqual(pointer.get("latestValidation", {}).get("status"), "blocked-target-drift")
            self.assertFalse(pointer.get("latestValidation", {}).get("movementAllowed"))
            stale = pointer.get("staleProofPointer")
            self.assertIsInstance(stale, dict)
            self.assertIn("do-not-use-as-current-proof", stale.get("reusePolicy", ""))
            return

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

        latest_runtime_pointer = repo_root / "scripts" / "captures" / "latest-live-test-run.json"
        if not latest_runtime_pointer.exists():
            return

        runtime_pointer = json.loads(latest_runtime_pointer.read_text(encoding="utf-8-sig"))
        run_summary_file = runtime_pointer.get("runSummaryFile")
        if not run_summary_file or not Path(run_summary_file).exists():
            return

        run_summary = json.loads(Path(run_summary_file).read_text(encoding="utf-8-sig"))
        runtime_pid = int(run_summary.get("processId") or 0)
        runtime_hwnd = str(run_summary.get("targetWindowHandle") or "").lower()
        pointer_pid = int(pointer["target"].get("processId") or 0)
        pointer_hwnd = str(pointer["target"].get("targetWindowHandle") or "").lower()

        self.assertEqual(pointer_pid, runtime_pid)
        self.assertEqual(pointer_hwnd, runtime_hwnd)


if __name__ == "__main__":
    unittest.main()
