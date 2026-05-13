from __future__ import annotations

import unittest

from rift_live_test.x64dbg_target_recovery import summarize_threads


class X64DbgTargetRecoveryTests(unittest.TestCase):
    def test_summarize_threads_counts_recovery_evidence(self) -> None:
        summary = summarize_threads(
            [
                {
                    "opened": True,
                    "contextCaptured": True,
                    "debugRegistersNonZero": True,
                    "clearDebugRegistersAttempted": True,
                    "clearDebugRegistersSucceeded": True,
                    "previousSuspendCount": 1,
                    "forceResumeExistingSuspensionAttempted": True,
                    "forceResumeExistingSuspensionCalls": 1,
                    "errors": [],
                },
                {
                    "opened": True,
                    "contextCaptured": True,
                    "debugRegistersNonZero": False,
                    "clearDebugRegistersAttempted": False,
                    "clearDebugRegistersSucceeded": False,
                    "previousSuspendCount": 0,
                    "forceResumeExistingSuspensionAttempted": False,
                    "forceResumeExistingSuspensionCalls": 0,
                    "errors": ["sample"],
                },
            ]
        )

        self.assertEqual(summary["threadCount"], 2)
        self.assertEqual(summary["openedCount"], 2)
        self.assertEqual(summary["contextCapturedCount"], 2)
        self.assertEqual(summary["nonZeroDebugRegisterCount"], 1)
        self.assertEqual(summary["clearDebugRegistersAttemptedCount"], 1)
        self.assertEqual(summary["clearDebugRegistersSucceededCount"], 1)
        self.assertEqual(summary["previouslySuspendedCount"], 1)
        self.assertEqual(summary["forceResumeExistingSuspensionAttemptedCount"], 1)
        self.assertEqual(summary["forceResumeExistingSuspensionCallCount"], 1)
        self.assertEqual(summary["errorCount"], 1)


if __name__ == "__main__":
    unittest.main()
