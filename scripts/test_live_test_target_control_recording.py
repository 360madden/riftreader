# Version: riftreader-test-target-control-summary-v0.3.0
# Total-Character-Count: 2483
# Purpose: Offline tests for live-test target-control summary helpers. No live game access.

from __future__ import annotations

import unittest

from rift_live_test.target_control_summary import compact_target_control_summary, target_control_state_detail


class TargetControlSummaryTests(unittest.TestCase):
    def test_compact_summary_preserves_policy_fields(self) -> None:
        compact = compact_target_control_summary(
            {
                "status": "passed-target-control",
                "classification": "exact-hwnd-foreground",
                "ok": True,
                "readyForReadOnlyProof": True,
                "readyForVisualGate": True,
                "readyForLiveInput": True,
                "summaryPath": "C:/RIFT MODDING/RiftReader/scripts/captures/tc/target-control-status.json",
                "blockers": [],
                "warnings": ["demo-warning"],
                "capabilities": {"readOnlyProof": True},
                "attempts": [{"large": "omitted"}],
            }
        )

        self.assertEqual(compact["status"], "passed-target-control")
        self.assertEqual(compact["classification"], "exact-hwnd-foreground")
        self.assertTrue(compact["readyForLiveInput"])
        self.assertNotIn("attempts", compact)
        self.assertEqual(compact["warnings"], ["demo-warning"])

    def test_missing_summary_fails_closed(self) -> None:
        compact = compact_target_control_summary(None)

        self.assertEqual(compact["status"], "target-control-missing")
        self.assertFalse(compact["readyForReadOnlyProof"])
        self.assertIn("target_control_summary_missing", compact["blockers"])

    def test_state_detail_is_human_readable(self) -> None:
        text = target_control_state_detail(
            {
                "status": "blocked-target-control",
                "classification": "different-process-foreground",
                "readyForReadOnlyProof": False,
                "readyForVisualGate": False,
                "readyForLiveInput": False,
                "blockers": ["different-process-foreground"],
            }
        )

        self.assertIn("classification=different-process-foreground", text)
        self.assertIn("readyForLiveInput=False", text)
        self.assertIn("blockers=different-process-foreground", text)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
