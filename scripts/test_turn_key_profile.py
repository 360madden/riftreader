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
    summarize_input_delivery,
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

    def test_input_delivery_detects_sendinput_fallback(self) -> None:
        delivery = summarize_input_delivery(
            requested_input_mode="foreground-sendinput",
            stdout=(
                "WARNING: Foreground SendInput path failed; attempting AutoHotkey fallback. "
                "SendInput sent 0 of 1 keyboard inputs for virtual key 68.\n"
                "[RiftKey] AutoHotkey fallback SUCCESS\n"
                "[RiftKey] SUCCESS\n"
            ),
        )
        self.assertTrue(delivery["sendInputFailed"])
        self.assertTrue(delivery["autoHotkeyFallbackUsed"])
        self.assertEqual(delivery["effectiveMode"], "autohotkey-fallback")

    def test_proof_refresh_retry_returns_first_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TurnKeyProfileConfig(
                repo_root=Path(temp_dir),
                process_id=123,
                target_window_handle="0x123",
                proof_refresh_retries=2,
            )

            class StubProfiler(TurnKeyProfiler):
                def __init__(self, stub_config: TurnKeyProfileConfig) -> None:
                    super().__init__(stub_config)
                    self.calls: list[tuple[str, str]] = []

                def _run_proof_refresh(self, *, label: str, output_subdir: str) -> dict:
                    self.calls.append((label, output_subdir))
                    ok = len(self.calls) == 2
                    return {
                        "ok": ok,
                        "summary": {
                            "status": "passed-proof-only" if ok else "blocked-proof-refresh",
                            "runDirectory": f"C:/tmp/proof-{len(self.calls)}",
                        },
                    }

            profiler = StubProfiler(config)
            result = profiler._run_proof_refresh_with_retries(
                label="proof-refresh-before",
                output_subdir="proof-refreshes/attempt",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["attemptCount"], 2)
            self.assertEqual(result["maxAttemptCount"], 3)
            self.assertEqual(
                [attempt["ok"] for attempt in result["attemptResults"]],
                [False, True],
            )
            self.assertEqual(
                profiler.calls,
                [
                    ("proof-refresh-before-try1", "proof-refreshes/attempt/try1"),
                    ("proof-refresh-before-try2", "proof-refreshes/attempt/try2"),
                ],
            )

    def test_validate_rejects_negative_proof_refresh_retries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TurnKeyProfileConfig(
                repo_root=Path(temp_dir),
                process_id=123,
                target_window_handle="0x123",
                proof_refresh_retries=-1,
            )
            with self.assertRaisesRegex(ValueError, "proof_refresh_retries"):
                TurnKeyProfiler(config)._validate_config()

    def test_live_post_message_requires_explicit_incident_review_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TurnKeyProfileConfig(
                repo_root=Path(temp_dir),
                process_id=123,
                target_window_handle="0x123",
                live=True,
                input_modes=("post-message",),
            )
            with self.assertRaisesRegex(ValueError, "post-message live input is blocked"):
                TurnKeyProfiler(config)._validate_config()

            allowed = TurnKeyProfileConfig(
                repo_root=Path(temp_dir),
                process_id=123,
                target_window_handle="0x123",
                live=True,
                input_modes=("post-message",),
                allow_post_message_input=True,
            )
            TurnKeyProfiler(allowed)._validate_config()

    def test_markdown_records_input_delivery(self) -> None:
        text = format_turn_key_markdown(
            {
                "status": "completed-no-promoted-turn-candidate",
                "ok": False,
                "generatedAtUtc": "2026-05-08T00:00:00Z",
                "runDirectory": "C:/tmp/run",
                "processName": "rift_x64",
                "processId": 123,
                "targetWindowHandle": "0x123",
                "live": True,
                "inputSent": True,
                "movementDetected": False,
                "noCheatEngine": True,
                "savedVariablesUsedAsLiveTruth": False,
                "attempts": [
                    {
                        "attemptId": "001",
                        "key": "d",
                        "inputMode": "foreground-sendinput",
                        "shell": "pwsh",
                        "classification": "no-turn",
                        "yawDeltaDegrees": 0.0,
                        "coordDelta": {"planarDistance": 0.0},
                        "inputCommand": {
                            "exitCode": 0,
                            "inputDelivery": {"effectiveMode": "autohotkey-fallback"},
                        },
                    }
                ],
                "promotedCandidates": [],
                "issues": [],
            }
        )
        self.assertIn("| Attempt | Key | Mode | Delivery | Shell |", text)
        self.assertIn("`autohotkey-fallback`", text)


if __name__ == "__main__":
    unittest.main()
