from __future__ import annotations

import argparse
import unittest

from scripts.static_owner_mouse_turn_probe import (
    analyze_attempt,
    build_parser,
    direction_to_dx,
    expected_delta_sign,
    hwnd_to_hex,
    parse_hwnd,
    split_delta,
    target_from_summary,
    validate_args,
)


def state(yaw: float, x: float = 10.0, z: float = 20.0) -> dict:
    return {
        "status": "passed",
        "latestState": {
            "yawDegrees": yaw,
            "coordinate": {
                "x": x,
                "y": 5.0,
                "z": z,
            },
        },
    }


def args(**overrides) -> argparse.Namespace:
    defaults = {
        "directions": ["left", "right"],
        "pixels": [80, 160],
        "steps": 8,
        "hold_milliseconds": 250,
        "focus_delay_milliseconds": 250,
        "post_input_wait_milliseconds": 500,
        "samples": 3,
        "interval_seconds": 0.1,
        "minimum_yaw_delta_degrees": 1.0,
        "max_planar_drift": 2.0,
        "command_timeout_seconds": 120.0,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class StaticOwnerMouseTurnProbeTests(unittest.TestCase):
    def test_parse_hwnd_accepts_hex_decimal_and_int(self) -> None:
        self.assertEqual(0x320CB0, parse_hwnd("0x320CB0"))
        self.assertEqual(3280048, parse_hwnd("3280048"))
        self.assertEqual(3280048, parse_hwnd(3280048))
        self.assertEqual("0x320CB0", hwnd_to_hex("0x320CB0"))

    def test_parse_hwnd_rejects_empty_or_zero(self) -> None:
        with self.assertRaises(ValueError):
            parse_hwnd("")
        with self.assertRaises(ValueError):
            parse_hwnd("0")

    def test_direction_mapping_matches_yaw_sign_convention(self) -> None:
        self.assertEqual(-1, expected_delta_sign("left"))
        self.assertEqual(1, expected_delta_sign("right"))
        self.assertEqual(-80, direction_to_dx("left", 80))
        self.assertEqual(80, direction_to_dx("right", 80))

    def test_split_delta_preserves_sum_and_sign(self) -> None:
        left = split_delta(-80, 8)
        right = split_delta(81, 8)

        self.assertEqual(-80, sum(left))
        self.assertTrue(all(item <= 0 for item in left))
        self.assertEqual(81, sum(right))
        self.assertTrue(all(item >= 0 for item in right))

    def test_target_from_summary_normalizes_exact_target(self) -> None:
        target = target_from_summary(
            {
                "target": {
                    "processName": "rift_x64",
                    "processId": 25668,
                    "targetWindowHandle": "0x320CB0",
                }
            }
        )

        self.assertEqual("rift_x64", target["processName"])
        self.assertEqual(25668, target["processId"])
        self.assertEqual("0x320CB0", target["targetWindowHandle"])

    def test_analyze_attempt_passes_any_large_yaw_delta(self) -> None:
        analysis = analyze_attempt(
            direction="left",
            pixels=80,
            pre_summary=state(90.0),
            post_summary=state(84.0),
            minimum_yaw_delta_degrees=1.0,
            max_planar_drift=2.0,
        )

        self.assertEqual("passed", analysis["status"])
        self.assertLess(analysis["signedYawDeltaDegrees"], 0)
        self.assertTrue(analysis["candidateOnly"])

    def test_analyze_attempt_warns_for_inverted_mouse_mapping(self) -> None:
        analysis = analyze_attempt(
            direction="left",
            pixels=80,
            pre_summary=state(90.0),
            post_summary=state(96.0),
            minimum_yaw_delta_degrees=1.0,
            max_planar_drift=2.0,
        )

        self.assertEqual("passed", analysis["status"])
        self.assertIn("yaw-delta-opposite-expected-direction", analysis["warnings"])

    def test_analyze_attempt_blocks_zero_yaw_delta(self) -> None:
        analysis = analyze_attempt(
            direction="right",
            pixels=80,
            pre_summary=state(47.0),
            post_summary=state(47.0),
            minimum_yaw_delta_degrees=1.0,
            max_planar_drift=2.0,
        )

        self.assertEqual("blocked", analysis["status"])
        self.assertIn("yaw-delta-below-threshold", analysis["blockers"])

    def test_analyze_attempt_warns_on_planar_drift(self) -> None:
        analysis = analyze_attempt(
            direction="right",
            pixels=160,
            pre_summary=state(10.0, 0.0, 0.0),
            post_summary=state(15.0, 5.0, 0.0),
            minimum_yaw_delta_degrees=1.0,
            max_planar_drift=2.0,
        )

        self.assertEqual("passed", analysis["status"])
        self.assertIn("planar-drift-exceeded", analysis["warnings"])

    def test_validate_args_rejects_bad_values(self) -> None:
        errors = validate_args(args(directions=["up"], pixels=[0], steps=0))

        self.assertIn("unsupported-directions:up", errors)
        self.assertIn("pixels-must-be-positive", errors)
        self.assertIn("steps-must-be-positive", errors)

    def test_parser_accepts_probe_options(self) -> None:
        parsed = build_parser().parse_args(
            [
                "--directions",
                "left",
                "--pixels",
                "80",
                "160",
                "--mouse-approved",
                "--allow-nonforeground",
                "--no-stop-on-first-success",
            ]
        )

        self.assertEqual(["left"], parsed.directions)
        self.assertEqual([80, 160], parsed.pixels)
        self.assertTrue(parsed.mouse_approved)
        self.assertFalse(parsed.require_foreground)
        self.assertFalse(parsed.stop_on_first_success)


if __name__ == "__main__":
    unittest.main()
