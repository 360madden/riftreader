import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts import static_owner_coordinate_chain_readback as readback


class StaticOwnerCoordinateChainReadbackTests(unittest.TestCase):
    def test_poll_analysis_reports_speed_and_passes_stable_stationary_baseline(self) -> None:
        samples = [
            {"sampleIndex": 0, "elapsedSeconds": 0.0, "ownerAddress": "0x1000", "coordinate": {"x": 10.0, "y": 2.0, "z": 20.0}},
            {"sampleIndex": 1, "elapsedSeconds": 0.2, "ownerAddress": "0x1000", "coordinate": {"x": 10.01, "y": 2.0, "z": 20.01}},
        ]

        analysis = readback.build_poll_analysis(
            samples,
            max_planar_jump_per_sample=25.0,
            max_sample_gap_seconds=2.0,
            expect_stationary=True,
            max_stationary_planar_drift=0.5,
        )

        self.assertEqual(analysis["sampleCount"], 2)
        self.assertEqual(analysis["ownerChangedCount"], 0)
        self.assertAlmostEqual(analysis["maxPlanarDelta"], 0.0141421356, places=6)
        self.assertEqual(analysis["blockers"], [])

    def test_poll_analysis_blocks_owner_change_jump_and_stale_gap(self) -> None:
        samples = [
            {"sampleIndex": 0, "elapsedSeconds": 0.0, "ownerAddress": "0x1000", "coordinate": {"x": 0.0, "y": 0.0, "z": 0.0}},
            {"sampleIndex": 1, "elapsedSeconds": 5.0, "ownerAddress": "0x2000", "coordinate": {"x": 100.0, "y": 0.0, "z": 0.0}},
        ]

        analysis = readback.build_poll_analysis(
            samples,
            max_planar_jump_per_sample=25.0,
            max_sample_gap_seconds=2.0,
            expect_stationary=True,
            max_stationary_planar_drift=0.5,
        )

        self.assertIn("owner-address-changed-during-poll:1", analysis["blockers"])
        self.assertIn("coordinate-jump-threshold-exceeded:1", analysis["blockers"])
        self.assertIn("sample-gap-threshold-exceeded:1", analysis["blockers"])
        self.assertTrue(any(item.startswith("stationary-baseline-drift-too-large") for item in analysis["blockers"]))

    def test_use_current_truth_defaults_extracts_promoted_resolver_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            truth_path = root / "current-truth.json"
            truth_path.write_text(
                """
                {
                  "target": {
                    "processName": "rift_x64.exe",
                    "processId": 34176,
                    "targetWindowHandle": "0x3D1544",
                    "processStartUtc": "2026-05-27T18:06:53Z",
                    "moduleBase": "0x7FF77AF40000"
                  },
                  "staticChainStatus": {
                    "status": "promoted-static-player-coordinate-resolver",
                    "promotionAllowed": true,
                    "primaryCandidate": {
                      "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                      "rootRva": "0x32EBC80"
                    }
                  }
                }
                """,
                encoding="utf-8",
            )

            defaults = readback.load_current_truth_defaults(root, str(truth_path))

        self.assertEqual(defaults["pid"], 34176)
        self.assertEqual(defaults["hwnd"], "0x3D1544")
        self.assertEqual(defaults["moduleBase"], "0x7FF77AF40000")
        self.assertEqual(defaults["rootRva"], "0x32EBC80")
        self.assertTrue(defaults["promotionAllowed"])

    def test_validate_args_requires_target_when_current_truth_not_used(self) -> None:
        args = Namespace(
            pid=None,
            hwnd=None,
            module_base=None,
            samples=1,
            interval_seconds=0.2,
            max_planar_jump_per_sample=25.0,
            max_sample_gap_seconds=2.0,
            max_stationary_planar_drift=0.5,
            process_start_tolerance_seconds=2.0,
        )

        errors = readback.validate_args(args)

        self.assertIn("pid-required", errors)
        self.assertIn("hwnd-required", errors)
        self.assertIn("module-base-required", errors)

    def test_process_start_check_allows_precision_differences_but_blocks_drift(self) -> None:
        passed = readback.process_start_check(
            "2026-05-27T18:06:53.070146+00:00",
            "2026-05-27T18:06:53.0701460Z",
            tolerance_seconds=2.0,
        )
        failed = readback.process_start_check(
            "2026-05-27T18:06:53.070146+00:00",
            "2026-05-27T18:07:10Z",
            tolerance_seconds=2.0,
        )

        self.assertTrue(passed["matchesExpected"])
        self.assertFalse(failed["matchesExpected"])
        self.assertEqual(failed["status"], "mismatch")


if __name__ == "__main__":
    unittest.main()
