from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from scripts.static_owner_turn_input_probe import (
    analyze_attempt,
    build_parser,
    csharp_sendinput_command,
    infer_direction,
    input_command,
    legacy_post_key_command,
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


def target() -> dict:
    return {
        "processName": "rift_x64",
        "processId": 25668,
        "targetWindowHandle": "0x320CB0",
    }


def args(**overrides) -> argparse.Namespace:
    defaults = {
        "current_truth_json": "docs/recovery/current-truth.json",
        "process_name": "rift_x64",
        "keys": ["left", "right"],
        "backends": ["csharp-scancode"],
        "hold_milliseconds": 250,
        "post_input_wait_milliseconds": 350,
        "samples": 3,
        "interval_seconds": 0.1,
        "minimum_yaw_delta_degrees": 1.0,
        "max_planar_drift": 1.5,
        "title_contains": "RIFT",
        "focus_delay_milliseconds": 250,
        "command_timeout_seconds": 120.0,
        "dry_run": False,
        "probe_approved": True,
        "stop_on_first_success": True,
        "json": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class StaticOwnerTurnInputProbeTests(unittest.TestCase):
    def test_infer_direction_for_common_turn_keys(self) -> None:
        self.assertEqual("left", infer_direction("left"))
        self.assertEqual("left", infer_direction("a"))
        self.assertEqual("left", infer_direction("q"))
        self.assertEqual("right", infer_direction("right"))
        self.assertEqual("right", infer_direction("d"))
        self.assertEqual("right", infer_direction("e"))
        self.assertIsNone(infer_direction("w"))

    def test_csharp_command_exact_targets_pid_hwnd(self) -> None:
        command = csharp_sendinput_command(
            args=args(),
            root=Path("C:/RIFT MODDING/RiftReader"),
            target=target(),
            key="left",
            input_mode="ScanCode",
        )

        self.assertEqual("rift_x64", command[command.index("--process-name") + 1])
        self.assertEqual("25668", command[command.index("--pid") + 1])
        self.assertEqual("0x320CB0", command[command.index("--hwnd") + 1])
        self.assertEqual("ScanCode", command[command.index("--input-mode") + 1])

    def test_legacy_window_message_command_uses_exact_target(self) -> None:
        command = legacy_post_key_command(
            args=args(),
            root=Path("C:/RIFT MODDING/RiftReader"),
            target=target(),
            key="a",
            require_foreground=False,
        )

        self.assertIn("-UseWindowMessage", command)
        self.assertIn("-TargetProcessId", command)
        self.assertEqual("25668", command[command.index("-TargetProcessId") + 1])
        self.assertEqual("0x320CB0", command[command.index("-TargetWindowHandle") + 1])

    def test_input_command_rejects_unknown_backend(self) -> None:
        with self.assertRaises(ValueError):
            input_command(
                args=args(),
                root=Path("."),
                target=target(),
                key="left",
                backend="unknown",
            )

    def test_analyze_left_turn_passes_negative_yaw_delta(self) -> None:
        analysis = analyze_attempt(
            key="left",
            backend="csharp-scancode",
            pre_summary=state(90.0),
            post_summary=state(84.0),
            minimum_yaw_delta_degrees=1.0,
            max_planar_drift=1.5,
        )

        self.assertEqual("passed", analysis["status"])
        self.assertLess(analysis["signedYawDeltaDegrees"], 0)
        self.assertTrue(analysis["candidateOnly"])

    def test_analyze_blocks_zero_yaw_delta(self) -> None:
        analysis = analyze_attempt(
            key="a",
            backend="legacy-window-message",
            pre_summary=state(47.0),
            post_summary=state(47.0),
            minimum_yaw_delta_degrees=1.0,
            max_planar_drift=1.5,
        )

        self.assertEqual("blocked", analysis["status"])
        self.assertIn("yaw-delta-below-threshold", analysis["blockers"])

    def test_analyze_warns_on_planar_drift_but_keeps_yaw_signal(self) -> None:
        analysis = analyze_attempt(
            key="right",
            backend="csharp-scancode",
            pre_summary=state(10.0, 0.0, 0.0),
            post_summary=state(15.0, 5.0, 0.0),
            minimum_yaw_delta_degrees=1.0,
            max_planar_drift=1.5,
        )

        self.assertEqual("passed", analysis["status"])
        self.assertIn("planar-drift-exceeded", analysis["warnings"])

    def test_validate_args_rejects_bad_backend(self) -> None:
        errors = validate_args(args(backends=["not-real"]))
        self.assertIn("unsupported-backends:not-real", errors)

    def test_parser_accepts_probe_options(self) -> None:
        parsed = build_parser().parse_args([
            "--keys", "a", "d",
            "--backends", "csharp-scancode", "legacy-window-message",
            "--probe-approved",
            "--no-stop-on-first-success",
        ])

        self.assertEqual(["a", "d"], parsed.keys)
        self.assertEqual(["csharp-scancode", "legacy-window-message"], parsed.backends)
        self.assertTrue(parsed.probe_approved)
        self.assertFalse(parsed.stop_on_first_success)


if __name__ == "__main__":
    unittest.main()
