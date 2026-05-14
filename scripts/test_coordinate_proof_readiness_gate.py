from __future__ import annotations

import unittest

from rift_live_test.coordinate_proof_readiness_gate import readiness_decision, target_mismatches


class CoordinateProofReadinessGateTests(unittest.TestCase):
    def test_blocks_when_reference_is_not_fresh_even_if_milestone_ready(self) -> None:
        decision = readiness_decision(
            {"usable": False, "blockers": ["blocked-fresh-reference-unavailable"]},
            {"readOnlyProofAllowed": True, "selectedCandidatePresent": True, "blockers": []},
        )

        self.assertEqual(decision["status"], "blocked")
        self.assertFalse(decision["readOnlyProofAllowed"])
        self.assertIn("reference:blocked-fresh-reference-unavailable", decision["blockers"])

    def test_passes_only_when_reference_and_milestone_are_ready(self) -> None:
        decision = readiness_decision(
            {"usable": True, "blockers": []},
            {"readOnlyProofAllowed": True, "selectedCandidatePresent": True, "blockers": []},
        )

        self.assertEqual(decision["status"], "passed")
        self.assertEqual(decision["verdict"], "ready-for-read-only-proof")
        self.assertTrue(decision["readOnlyProofAllowed"])
        self.assertFalse(decision["movementAllowed"])

    def test_target_mismatches_accepts_hwnd_decimal_and_exe_suffix(self) -> None:
        self.assertEqual(
            target_mismatches(
                {"processName": "rift_x64", "pid": 2928, "hwnd": "0xC0994"},
                {"processName": "rift_x64.exe", "processId": 2928, "targetWindowHandle": "788884"},
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
