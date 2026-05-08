from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rift_live_test.turn_keys import (
    TurnKeyProfileConfig,
    TurnKeyProfiler,
    classify_turn_attempt,
    format_turn_key_markdown,
    normalize_degrees,
    planar_coord_delta,
)


class TurnKeyProfileTests(unittest.TestCase):
    def test_normalize_degrees_returns_short_signed_delta(self) -> None:
        self.assertAlmostEqual(normalize_degrees(358.0), -2.0)
        self.assertAlmostEqual(normalize_degrees(-358.0), 2.0)
        self.assertAlmostEqual(normalize_degrees(181.0), -179.0)

    def test_planar_coord_delta_uses_xz_plane(self) -> None:
        delta = planar_coord_delta(
            {"x": 10.0, "y": 5.0, "z": 20.0},
            {"x": 13.0, "y": 9.0, "z": 24.0},
        )
        self.assertAlmostEqual(delta["planarDistance"], 5.0)
        self.assertAlmostEqual(delta["linearDistance"], (3.0**2 + 4.0**2 + 4.0**2) ** 0.5)

    def test_classify_turn_candidate_requires_yaw_without_coord_movement(self) -> None:
        self.assertEqual(
            classify_turn_attempt(
                input_exit_code=0,
                yaw_delta_degrees=5.0,
                coord_delta={"planarDistance": 0.0},
                min_yaw_delta_degrees=1.0,
                max_coord_delta=0.25,
            ),
            "turn-candidate",
        )
        self.assertEqual(
            classify_turn_attempt(
                input_exit_code=0,
                yaw_delta_degrees=5.0,
                coord_delta={"planarDistance": 1.0},
                min_yaw_delta_degrees=1.0,
                max_coord_delta=0.25,
            ),
            "movement-detected",
        )

    def test_promoted_candidates_require_two_consistent_turn_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TurnKeyProfileConfig(
                repo_root=Path(temp_dir),
                process_id=123,
                target_window_handle="0x123",
                keys=("d",),
                input_modes=("post-message",),
                shells=("pwsh",),
                repeats=2,
            )
            profiler = TurnKeyProfiler(config)
            profiler.attempts = [
                {
                    "attemptId": "001",
                    "key": "d",
                    "inputMode": "post-message",
                    "shell": "pwsh",
                    "classification": "turn-candidate",
                    "yawDeltaDegrees": 3.0,
                    "coordDelta": {"planarDistance": 0.0},
                },
                {
                    "attemptId": "002",
                    "key": "d",
                    "inputMode": "post-message",
                    "shell": "pwsh",
                    "classification": "turn-candidate",
                    "yawDeltaDegrees": 4.0,
                    "coordDelta": {"planarDistance": 0.0},
                },
            ]

            promoted = profiler.promoted_candidates()
            self.assertEqual(len(promoted), 1)
            self.assertEqual(promoted[0]["key"], "d")
            self.assertEqual(promoted[0]["consistentSign"], 1)

    def test_markdown_records_safety_flags(self) -> None:
        text = format_turn_key_markdown(
            {
                "status": "plan-only",
                "ok": True,
                "generatedAtUtc": "2026-05-08T00:00:00Z",
                "runDirectory": "C:/tmp/run",
                "processName": "rift_x64",
                "processId": 123,
                "targetWindowHandle": "0x123",
                "live": False,
                "inputSent": False,
                "movementDetected": False,
                "noCheatEngine": True,
                "savedVariablesUsedAsLiveTruth": False,
                "attempts": [],
                "promotedCandidates": [],
                "issues": [],
            }
        )
        self.assertIn("No Cheat Engine: `true`", text)
        self.assertIn("SavedVariables live truth: `false`", text)


if __name__ == "__main__":
    unittest.main()

