from __future__ import annotations

import unittest
from pathlib import Path

from rift_live_test.priority_scan_exhaustion_report import (
    aggregate_scan_totals,
    infer_verdict,
    same_target_identity,
    summarize_pointer_scan,
)


class PriorityScanExhaustionReportTests(unittest.TestCase):
    def test_summarize_pointer_scan_totals_ranked_targets(self) -> None:
        summary = summarize_pointer_scan(
            Path("scan.json"),
            {
                "status": "passed",
                "target": {"pid": 2928, "hwndHex": "0xC0994", "processName": "rift_x64"},
                "counts": {"scannedTargetCount": 2, "queuedTargetCount": 2},
                "rankedTargets": [
                    {"target": "0x1", "targetLabel": "a", "hitCount": 2, "moduleHitCount": 0, "riftModuleHitCount": 0},
                    {"target": "0x2", "targetLabel": "b", "hitCount": 1, "moduleHitCount": 1, "riftModuleHitCount": 1},
                ],
            },
            repo_root=Path("."),
        )

        self.assertEqual(summary["totalHits"], 3)
        self.assertEqual(summary["moduleHitCount"], 1)
        self.assertEqual(summary["riftModuleHitCount"], 1)
        self.assertEqual(summary["targetsWithHits"], 2)

    def test_target_identity_mismatch_reports_only_drift(self) -> None:
        mismatches = same_target_identity(
            {"processName": "rift_x64", "pid": 1, "hwnd": "0x10", "startTimeUtc": "a", "moduleBaseAddressHex": "0x1000"},
            {"processName": "rift_x64.exe", "pid": 1, "hwnd": "16", "startTimeUtc": "b", "moduleBaseAddressHex": "4096"},
        )

        self.assertEqual(mismatches, ["startTimeUtc:a!=b"])

    def test_infer_verdict_exhausted_no_static_root(self) -> None:
        verdict = infer_verdict(
            [
                {"priorityParentLeadCount": 15, "exportedPriorityParentLeadCount": 8},
                {"priorityParentLeadCount": 15, "exportedPriorityParentLeadCount": 7},
            ],
            [{"moduleHitCount": 0, "riftModuleHitCount": 0}],
        )

        self.assertEqual(verdict, "priority-lane-exhausted-no-static-root")

    def test_aggregate_scan_totals(self) -> None:
        totals = aggregate_scan_totals(
            [
                {"scannedTargetCount": 2, "queuedTargetCount": 3, "targetsWithHits": 1, "totalHits": 4, "moduleHitCount": 0, "riftModuleHitCount": 0},
                {"scannedTargetCount": 5, "queuedTargetCount": 5, "targetsWithHits": 2, "totalHits": 6, "moduleHitCount": 1, "riftModuleHitCount": 1},
            ]
        )

        self.assertEqual(totals["scannedTargetCount"], 7)
        self.assertEqual(totals["queuedTargetCount"], 8)
        self.assertEqual(totals["moduleHitCount"], 1)


if __name__ == "__main__":
    unittest.main()
