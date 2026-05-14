from __future__ import annotations

import sys
import unittest
from pathlib import Path

snapshot = None
if sys.platform == "win32":
    import capture_current_pid_coordinate_family_snapshot as snapshot


@unittest.skipIf(snapshot is None, "capture_current_pid_coordinate_family_snapshot requires Windows")
class CaptureCurrentPidCoordinateFamilySnapshotTests(unittest.TestCase):
    def test_reference_drift_marks_large_movement_as_drifted(self) -> None:
        start = {"label": "start", "sourceFile": "start.json", "x": 100.0, "y": 50.0, "z": 25.0}
        end = {"label": "end", "sourceFile": "end.json", "x": 101.5, "y": 50.1, "z": 25.0}

        result = snapshot.summarize_reference_drift(start, end, tolerance=0.25)

        self.assertEqual(result["status"], "drifted")
        self.assertFalse(result["withinTolerance"])
        self.assertAlmostEqual(result["maxAbsDelta"], 1.5)
        self.assertEqual(result["delta"]["x"], 1.5)

    def test_reference_drift_accepts_stable_pose(self) -> None:
        start = {"label": "start", "sourceFile": "start.json", "x": 100.0, "y": 50.0, "z": 25.0}
        end = {"label": "end", "sourceFile": "end.json", "x": 100.05, "y": 49.9, "z": 25.1}

        result = snapshot.summarize_reference_drift(start, end, tolerance=0.25)

        self.assertEqual(result["status"], "stable")
        self.assertTrue(result["withinTolerance"])
        self.assertLessEqual(result["maxAbsDelta"], 0.25)

    def test_normalize_captured_reference_supports_rift_api_coordinate_shape(self) -> None:
        parsed = {
            "GeneratedAtUtc": "2026-05-14T02:30:00Z",
            "Coordinate": {
                "X": 7402.0,
                "Y": 871.77,
                "Z": 3029.42,
                "CapturedAtUtc": "2026-05-14T02:29:59Z",
            },
        }

        result = snapshot.normalize_captured_reference("fresh", Path("coord.json"), parsed)

        self.assertEqual(result["label"], "fresh")
        self.assertEqual(result["sourceFile"], "coord.json")
        self.assertEqual((result["x"], result["y"], result["z"]), (7402.0, 871.77, 3029.42))
        self.assertEqual(result["generatedAtUtc"], "2026-05-14T02:29:59Z")


if __name__ == "__main__":
    unittest.main()
