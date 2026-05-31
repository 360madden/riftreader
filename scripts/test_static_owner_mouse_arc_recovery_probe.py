from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from scripts.static_owner_mouse_arc_recovery_probe import (
    analyze_attempt,
    bearing_to_destination,
    build_parser,
    clear_ui_focus_command,
    destination_progress,
    direction_for_signed_delta,
    forward_command,
    target_bearing_for_offset,
    turn_completion_command,
    validate_args,
)


def args(**overrides) -> argparse.Namespace:
    defaults = {
        "repo_root": None,
        "output_root": None,
        "current_truth_json": "docs/recovery/current-truth.json",
        "process_name": "rift_x64",
        "destination_x": None,
        "destination_z": None,
        "arc_offsets_degrees": [45.0, -45.0],
        "samples": 3,
        "interval_seconds": 0.1,
        "alignment_threshold_degrees": 7.5,
        "max_turn_pulses": 5,
        "turn_settle_milliseconds": 350,
        "turn_pulse_interval_milliseconds": 100,
        "mouse_pixels_per_pulse": 40,
        "mouse_steps": 8,
        "mouse_hold_milliseconds": 250,
        "forward_key": "w",
        "forward_hold_milliseconds": 450,
        "post_forward_wait_milliseconds": 750,
        "input_mode": "ScanCode",
        "focus_delay_milliseconds": 250,
        "title_contains": "RIFT",
        "clear_ui_focus_before_input": False,
        "clear_ui_focus_key": "escape",
        "clear_ui_focus_hold_milliseconds": 50,
        "minimum_movement_distance": 0.35,
        "max_total_displacement": 10.0,
        "command_timeout_seconds": 90.0,
        "dry_run": False,
        "arc_approved": True,
        "movement_approved": True,
        "skip_readback_freshness_gate": False,
        "stop_on_first_success": True,
        "json": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def target() -> dict:
    return {
        "processName": "rift_x64",
        "processId": 25668,
        "targetWindowHandle": "0x320CB0",
    }


def state(yaw: float, x: float, z: float) -> dict:
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


class StaticOwnerMouseArcRecoveryProbeTests(unittest.TestCase):
    def test_target_bearing_for_offset_normalizes(self) -> None:
        self.assertAlmostEqual(85.0, target_bearing_for_offset(40.0, 45.0))
        self.assertAlmostEqual(-175.0, target_bearing_for_offset(170.0, 15.0))

    def test_direction_for_signed_delta(self) -> None:
        self.assertEqual("right", direction_for_signed_delta(1.0))
        self.assertEqual("left", direction_for_signed_delta(-1.0))
        self.assertEqual("left", direction_for_signed_delta(0.0))

    def test_destination_progress_reports_toward_destination(self) -> None:
        progress = destination_progress(
            {"x": 0.0, "z": 0.0},
            {"x": 2.0, "z": 0.0},
            {"x": 5.0, "z": 0.0},
        )

        self.assertEqual(5.0, progress["initialPlanarDistance"])
        self.assertEqual(3.0, progress["finalPlanarDistance"])
        self.assertEqual(2.0, progress["distanceDelta"])
        self.assertTrue(progress["movedTowardDestination"])

    def test_bearing_to_destination_uses_x_z_axes(self) -> None:
        self.assertAlmostEqual(0.0, bearing_to_destination({"x": 0.0, "z": 0.0}, {"x": 10.0, "z": 0.0}))
        self.assertAlmostEqual(90.0, bearing_to_destination({"x": 0.0, "z": 0.0}, {"x": 0.0, "z": 10.0}))

    def test_analyze_attempt_passes_for_planar_movement(self) -> None:
        analysis = analyze_attempt(
            arc_offset_degrees=45.0,
            target_bearing_degrees=90.0,
            pre_summary=state(45.0, 0.0, 0.0),
            post_summary=state(90.0, 0.0, 1.0),
            minimum_movement_distance=0.35,
            destination={"x": 0.0, "z": 5.0},
        )

        self.assertEqual("passed", analysis["status"])
        self.assertAlmostEqual(1.0, analysis["movementDelta"]["planar"])
        self.assertGreater(analysis["destinationProgress"]["distanceDelta"], 0)

    def test_analyze_attempt_blocks_stationary(self) -> None:
        analysis = analyze_attempt(
            arc_offset_degrees=45.0,
            target_bearing_degrees=90.0,
            pre_summary=state(45.0, 0.0, 0.0),
            post_summary=state(90.0, 0.0, 0.0),
            minimum_movement_distance=0.35,
            destination=None,
        )

        self.assertEqual("blocked", analysis["status"])
        self.assertIn("movement-below-threshold", analysis["blockers"])

    def test_forward_command_exact_targets_pid_hwnd(self) -> None:
        command = forward_command(args=args(), root=Path("C:/RIFT MODDING/RiftReader"), target=target())

        self.assertEqual("25668", command[command.index("--pid") + 1])
        self.assertEqual("0x320CB0", command[command.index("--hwnd") + 1])
        self.assertEqual("w", command[command.index("--key") + 1])

    def test_clear_ui_focus_command_exact_targets_pid_hwnd(self) -> None:
        command = clear_ui_focus_command(
            args(clear_ui_focus_before_input=True),
            Path("C:/RIFT MODDING/RiftReader"),
            {"target": target()},
        )

        self.assertEqual("25668", command[command.index("--pid") + 1])
        self.assertEqual("0x320CB0", command[command.index("--hwnd") + 1])
        self.assertEqual("escape", command[command.index("--key") + 1])
        self.assertEqual("50", command[command.index("--hold-ms") + 1])

    def test_turn_completion_command_uses_mouse_backend_and_exact_target(self) -> None:
        command = turn_completion_command(
            args=args(),
            root=Path("C:/RIFT MODDING/RiftReader"),
            output_root=Path("C:/tmp/out"),
            target=target(),
            direction="right",
            signed_delta_degrees=45.0,
        )

        self.assertEqual("mouse-look", command[command.index("--turn-backend") + 1])
        self.assertEqual("25668", command[command.index("--pid") + 1])
        self.assertEqual("0x320CB0", command[command.index("--hwnd") + 1])

    def test_validate_args_rejects_bad_values(self) -> None:
        errors = validate_args(
            args(
                arc_offsets_degrees=[],
                mouse_pixels_per_pulse=0,
                mouse_steps=0,
                forward_hold_milliseconds=0,
                clear_ui_focus_before_input=True,
                clear_ui_focus_key="",
                clear_ui_focus_hold_milliseconds=0,
                destination_x=1.0,
                destination_z=None,
            )
        )

        self.assertIn("arc-offsets-degrees-required", errors)
        self.assertIn("mouse-pixels-per-pulse-must-be-positive", errors)
        self.assertIn("mouse-steps-must-be-positive", errors)
        self.assertIn("forward-hold-milliseconds-must-be-positive", errors)
        self.assertIn("clear-ui-focus-key-required", errors)
        self.assertIn("clear-ui-focus-hold-milliseconds-must-be-positive", errors)
        self.assertIn("destination-x-and-z-required-together", errors)

    def test_parser_accepts_live_gate_options(self) -> None:
        parsed = build_parser().parse_args(
            [
                "--arc-offsets-degrees",
                "45",
                "-45",
                "--destination-x",
                "1",
                "--destination-z",
                "2",
                "--arc-approved",
                "--movement-approved",
                "--skip-readback-freshness-gate",
                "--clear-ui-focus-before-input",
                "--no-stop-on-first-success",
            ]
        )

        self.assertEqual([45.0, -45.0], parsed.arc_offsets_degrees)
        self.assertEqual(1.0, parsed.destination_x)
        self.assertEqual(2.0, parsed.destination_z)
        self.assertTrue(parsed.arc_approved)
        self.assertTrue(parsed.movement_approved)
        self.assertTrue(parsed.clear_ui_focus_before_input)
        self.assertTrue(parsed.skip_readback_freshness_gate)
        self.assertFalse(parsed.stop_on_first_success)


if __name__ == "__main__":
    unittest.main()
