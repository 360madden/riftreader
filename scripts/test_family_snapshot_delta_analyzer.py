#!/usr/bin/env python3

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

import family_snapshot_delta_analyzer as analyzer


def default_args() -> argparse.Namespace:
    return argparse.Namespace(
        axis_orders="xyz",
        candidate_scan_stride=1,
        max_tracking_error=0.75,
        min_api_planar_delta=0.05,
        window_x=2048.0,
        window_y=512.0,
        window_z=2048.0,
        max_abs_coordinate=100000.0,
        max_candidate_starts_per_segment=250000,
        max_candidates=1000,
        passive_stable_tolerance=0.01,
        passive_reference_tolerance=0.25,
        top=100,
    )


class FamilySnapshotDeltaAnalyzerTests(unittest.TestCase):
    def test_selftest_manifest_finds_unaligned_stride_family(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = analyzer.build_self_test_manifest(root)
            summary, *_ = analyzer.analyze_manifest(manifest, root / "analysis", default_args())

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["analysis"]["candidateCount"], 2)
            best = summary["analysis"]["bestCandidate"]
            self.assertEqual(best["residueMod4"], 3)
            self.assertEqual(best["trackingError"]["maxAbs"], 0.0)
            self.assertEqual(best["passiveNoiseByteOverlap"], 0)
            self.assertEqual(best["candidate_id"], best["candidateId"])
            self.assertEqual(best["base_address_hex"], best["segmentBaseHex"])
            self.assertEqual(best["offset_hex"], best["segmentOffsetHex"])
            self.assertEqual(best["axis_order"], "xyz")
            self.assertEqual(best["truth_readiness"], "candidate_only_not_movement_proof")
            self.assertEqual(summary["analysis"]["topFamily"]["commonAddressDeltaHex"], "0x100")

    def test_missing_displaced_pose_blocks_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = analyzer.build_self_test_manifest(root, include_displaced=False)
            summary, *_ = analyzer.analyze_manifest(manifest, root / "analysis", default_args())

            self.assertEqual(summary["status"], "blocked")
            self.assertIn("blocked-no-displaced-pose", summary["blockers"])
            self.assertEqual(summary["analysis"]["passiveStabilityCandidateCount"], 2)
            best = summary["analysis"]["bestCandidate"]
            self.assertEqual(best["candidateKind"], "passive-stability-near-reference")
            self.assertEqual(best["passiveMaxValueDrift"], 0.0)
            self.assertFalse(best["promotionEligible"])
            self.assertEqual(best["candidate_id"], best["candidateId"])
            self.assertEqual(best["base_address_hex"], best["segmentBaseHex"])
            self.assertEqual(best["offset_hex"], best["segmentOffsetHex"])
            self.assertEqual(best["axis_order"], "xyz")
            self.assertEqual(best["truth_readiness"], "candidate_only_not_movement_proof")


if __name__ == "__main__":
    unittest.main()
