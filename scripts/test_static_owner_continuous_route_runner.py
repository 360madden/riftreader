from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest import mock

from scripts.static_owner_continuous_route_runner import (
    DEFAULT_ALIGNMENT_THRESHOLD_DEGREES,
    DEFAULT_ARRIVAL_RADIUS,
    DEFAULT_MAX_FORWARD_HOLD_MS,
    DEFAULT_MIN_FORWARD_HOLD_MS,
    FORWARD_ACCEL_DISTANCE_M,
    FORWARD_ACCEL_TIME_MS,
    FORWARD_SPEED_M_PER_S,
    build_markdown,
    build_sequence_markdown,
    compact,
    compact_plan,
    compact_sequence_summary,
    compute_forward_hold_ms,
    compute_turn_hold_ms,
    clear_ui_focus_command,
    load_waypoint_sequence,
    make_waypoint_args,
    run,
    run_sequence,
    safe_mapping,
    validate_args,
)
from scripts import workflow_common as workflow_common_module

# Turn calibration constants (local copies; originals moved to local scope in compute_turn_hold_ms)
_DEFAULT_MIN_TURN_HOLD_MS = 150
_DEFAULT_MAX_TURN_HOLD_MS = 1200
_TURN_RATE_DEGREES_PER_MS = 0.177


def _make_args(**overrides: Any) -> Any:
    """Build a Namespace-like object with defaults for required route-runner args."""
    import argparse

    defaults: dict[str, Any] = {
        "repo_root": None,
        "output_root": None,
        "current_truth_json": "docs/recovery/current-truth.json",
        "destination_x": 7295.0,
        "destination_y": None,
        "destination_z": 2945.0,
        "destination_label": "ne-35m",
        "destination_waypoint_json": None,
        "destination_waypoint_id": None,
        "waypoint_sequence_json": None,
        "waypoint_sequence_ids": None,
        "arrival_radius": DEFAULT_ARRIVAL_RADIUS,
        "alignment_threshold_degrees": DEFAULT_ALIGNMENT_THRESHOLD_DEGREES,
        "minimum_progress_distance": 0.35,
        "wrong_way_tolerance": 1.0,
        "forward_key": "w",
        "turn_backend": "key",
        "input_mode": "ScanCode",
        "mouse_pixels_per_pulse": 40,
        "mouse_steps": 8,
        "mouse_hold_ms": 250,
        "clear_ui_focus_before_input": False,
        "clear_ui_focus_key": "escape",
        "clear_ui_focus_hold_milliseconds": 50,
        "title_contains": "RIFT",
        "focus_delay_milliseconds": 250,
        "turn_settle_seconds": 1.0,
        "forward_settle_seconds": 0.75,
        "max_iterations": 20,
        "max_total_seconds": 300.0,
        "command_timeout_seconds": 120.0,
        "turn_approved": True,
        "movement_approved": True,
        "allow_candidate_turn_control": True,
        "dry_run": False,
        "json": False,
        "skip_readback_freshness_gate": False,
        "nav_state": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class ComputeTurnHoldMsTests(unittest.TestCase):
    """Test the calibrated turn-hold computation."""

    def test_zero_degrees_returns_minimum_hold(self) -> None:
        self.assertEqual(compute_turn_hold_ms(0.0), _DEFAULT_MIN_TURN_HOLD_MS)

    def test_small_turn_clamps_to_minimum(self) -> None:
        # 0.5 degrees: 0.5 / 0.177 = 2.8ms → clamped to min (150ms)
        hold = compute_turn_hold_ms(0.5)
        self.assertEqual(hold, _DEFAULT_MIN_TURN_HOLD_MS)

    def test_typical_40_degree_turn(self) -> None:
        # 40 / 0.177 ≈ 226ms
        hold = compute_turn_hold_ms(40.0)
        self.assertAlmostEqual(hold, 226, delta=1)

    def test_90_degree_turn(self) -> None:
        # 90 / 0.177 ≈ 508ms
        hold = compute_turn_hold_ms(90.0)
        self.assertAlmostEqual(hold, 508, delta=1)

    def test_max_180_degree_turn_clamps_to_max(self) -> None:
        # 180 / 0.177 ≈ 1017ms → should be within max (1200ms)
        hold = compute_turn_hold_ms(180.0)
        self.assertLessEqual(hold, _DEFAULT_MAX_TURN_HOLD_MS)
        self.assertGreater(hold, _DEFAULT_MIN_TURN_HOLD_MS)

    def test_negative_degrees_uses_absolute(self) -> None:
        hold_pos = compute_turn_hold_ms(45.0)
        hold_neg = compute_turn_hold_ms(-45.0)
        self.assertEqual(hold_pos, hold_neg)

    def test_over_max_clamps_to_max(self) -> None:
        # 250 degrees → clamped to 180 internally → 180 / 0.177 ≈ 1017ms
        hold = compute_turn_hold_ms(250.0)
        self.assertLessEqual(hold, _DEFAULT_MAX_TURN_HOLD_MS)


class ComputeForwardHoldMsTests(unittest.TestCase):
    """Test the calibrated forward-hold computation."""

    def test_zero_distance_returns_minimum(self) -> None:
        self.assertEqual(compute_forward_hold_ms(0.0), DEFAULT_MIN_FORWARD_HOLD_MS)

    def test_negative_distance_returns_minimum(self) -> None:
        self.assertEqual(compute_forward_hold_ms(-1.0), DEFAULT_MIN_FORWARD_HOLD_MS)

    def test_acceleration_phase_short_distance(self) -> None:
        # 0.5m — less than accel distance, returns min hold
        hold = compute_forward_hold_ms(0.5)
        self.assertEqual(hold, DEFAULT_MIN_FORWARD_HOLD_MS)

    def test_typical_30m_distance(self) -> None:
        # cruising: 30 - 1 = 29m @ 6.1 m/s = 4.75s → + 200ms accel = 4951ms
        hold = compute_forward_hold_ms(30.0)
        self.assertAlmostEqual(hold, 4952, delta=5)

    def test_10m_distance(self) -> None:
        # cruising: 10 - 1 = 9m @ 6.1 m/s = 1.475s → + 200ms = 1675ms
        hold = compute_forward_hold_ms(10.0)
        self.assertAlmostEqual(hold, 1675, delta=5)

    def test_clamps_to_max(self) -> None:
        # 100m → way over max
        hold = compute_forward_hold_ms(100.0)
        self.assertEqual(hold, DEFAULT_MAX_FORWARD_HOLD_MS)

    def test_exactly_at_minimum(self) -> None:
        hold = compute_forward_hold_ms(0.05)
        self.assertEqual(hold, DEFAULT_MIN_FORWARD_HOLD_MS)


class CompactPlanTests(unittest.TestCase):
    """Test compact_plan extracts fields correctly."""

    def test_extracts_all_fields(self) -> None:
        plan = {
            "plan": {
                "firstAction": "turn-left",
                "turnMagnitudeClass": "large",
                "navigationTarget": {
                    "suggestedTurnDirection": "left",
                    "signedBearingDeltaDegrees": -45.0,
                    "absoluteBearingDeltaDegrees": 45.0,
                    "planarDistance": 37.5,
                    "withinArrivalRadius": False,
                    "withinAlignmentThreshold": False,
                },
                "executionBlocked": False,
                "executionBlockers": [],
                "engineTurnRateClassification": "left",
            },
        }
        result = compact_plan(plan)
        self.assertEqual(result["firstAction"], "turn-left")
        self.assertEqual(result["suggestedTurnDirection"], "left")
        self.assertEqual(result["signedBearingDeltaDegrees"], -45.0)
        self.assertEqual(result["absoluteBearingDeltaDegrees"], 45.0)
        self.assertEqual(result["planarDistance"], 37.5)
        self.assertFalse(result["withinArrivalRadius"])
        self.assertFalse(result["withinAlignmentThreshold"])
        self.assertFalse(result["executionBlocked"])
        self.assertEqual(result["engineTurnRateClassification"], "left")

    def test_aligned_plan(self) -> None:
        plan = {
            "plan": {
                "firstAction": "forward",
                "turnMagnitudeClass": "aligned",
                "navigationTarget": {
                    "suggestedTurnDirection": "aligned",
                    "signedBearingDeltaDegrees": 1.0,
                    "absoluteBearingDeltaDegrees": 1.0,
                    "planarDistance": 10.0,
                    "withinArrivalRadius": False,
                    "withinAlignmentThreshold": True,
                },
                "executionBlocked": False,
                "executionBlockers": [],
                "engineTurnRateClassification": "stationary",
            },
        }
        result = compact_plan(plan)
        self.assertEqual(result["suggestedTurnDirection"], "aligned")
        self.assertEqual(result["planarDistance"], 10.0)
        self.assertTrue(result["withinAlignmentThreshold"])

    def test_arrived_plan(self) -> None:
        plan = {
            "plan": {
                "firstAction": "stop",
                "navigationTarget": {
                    "withinArrivalRadius": True,
                    "planarDistance": 1.5,
                },
                "executionBlocked": False,
                "executionBlockers": [],
            },
        }
        result = compact_plan(plan)
        self.assertTrue(result["withinArrivalRadius"])
        self.assertEqual(result["planarDistance"], 1.5)

    def test_empty_navigation_target(self) -> None:
        plan = {"plan": {"navigationTarget": {}}}
        result = compact_plan(plan)
        self.assertIsNone(result["firstAction"])
        self.assertIsNone(result["planarDistance"])


class ValidateArgsTests(unittest.TestCase):
    """Test argument validation."""

    def test_passes_valid_direct_coordinates(self) -> None:
        args = _make_args(
            destination_x=7295.0,
            destination_z=2945.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
        )
        self.assertEqual(validate_args(args), [])

    def test_blocks_missing_destination(self) -> None:
        args = _make_args(
            destination_x=None,
            destination_z=None,
        )
        errors = validate_args(args)
        self.assertIn("destination-x-and-z-required", errors)

    def test_blocks_mutually_exclusive_destinations(self) -> None:
        args = _make_args(
            destination_x=7295.0,
            destination_z=2945.0,
            destination_waypoint_json="waypoints.json",
            destination_waypoint_id="wp1",
        )
        errors = validate_args(args)
        self.assertIn("destination-waypoint-and-direct-coordinates-mutually-exclusive", errors)

    def test_blocks_negative_arrival_radius(self) -> None:
        args = _make_args(arrival_radius=-1.0)
        errors = validate_args(args)
        self.assertIn("arrival-radius-must-be-nonnegative", errors)

    def test_blocks_negative_alignment_threshold(self) -> None:
        args = _make_args(alignment_threshold_degrees=-1.0)
        errors = validate_args(args)
        self.assertIn("alignment-threshold-degrees-must-be-nonnegative", errors)

    def test_blocks_zero_max_iterations(self) -> None:
        args = _make_args(max_iterations=0)
        errors = validate_args(args)
        self.assertIn("max-iterations-must-be-positive", errors)

    def test_blocks_short_total_seconds(self) -> None:
        args = _make_args(max_total_seconds=5.0)
        errors = validate_args(args)
        self.assertIn("max-total-seconds-must-be-at-least-10", errors)

    def test_blocks_negative_progress_distance(self) -> None:
        args = _make_args(minimum_progress_distance=-0.1)
        errors = validate_args(args)
        self.assertIn("minimum-progress-distance-must-be-nonnegative", errors)

    def test_blocks_negative_wrong_way_tolerance(self) -> None:
        args = _make_args(wrong_way_tolerance=-1.0)
        errors = validate_args(args)
        self.assertIn("wrong-way-tolerance-must-be-nonnegative", errors)

    def test_blocks_negative_settle_seconds(self) -> None:
        args = _make_args(turn_settle_seconds=-1.0)
        errors = validate_args(args)
        self.assertIn("settle-seconds-must-be-nonnegative", errors)

    def test_blocks_zero_command_timeout(self) -> None:
        args = _make_args(command_timeout_seconds=0.0)
        errors = validate_args(args)
        self.assertIn("command-timeout-seconds-must-be-positive", errors)

    def test_blocks_bad_clear_ui_focus_options(self) -> None:
        args = _make_args(
            clear_ui_focus_before_input=True,
            clear_ui_focus_key="",
            clear_ui_focus_hold_milliseconds=0,
        )

        errors = validate_args(args)

        self.assertIn("clear-ui-focus-key-required", errors)
        self.assertIn("clear-ui-focus-hold-milliseconds-must-be-positive", errors)

    def test_clear_ui_focus_command_uses_exact_target_escape(self) -> None:
        args = _make_args(clear_ui_focus_before_input=True)
        cmd = clear_ui_focus_command(
            args,
            Path("C:/RIFT MODDING/RiftReader"),
            {
                "target": {
                    "processName": "rift_x64",
                    "processId": 25668,
                    "targetWindowHandle": "0x320CB0",
                }
            },
        )

        self.assertEqual("escape", cmd[cmd.index("--key") + 1])
        self.assertEqual("50", cmd[cmd.index("--hold-ms") + 1])
        self.assertEqual("25668", cmd[cmd.index("--pid") + 1])
        self.assertEqual("0x320CB0", cmd[cmd.index("--hwnd") + 1])

    def test_waypoint_requires_json_and_id(self) -> None:
        args = _make_args(
            destination_x=None,
            destination_z=None,
            destination_waypoint_json="waypoints.json",
            destination_waypoint_id=None,
        )
        errors = validate_args(args)
        self.assertIn("destination-waypoint-id-required", errors)

        args2 = _make_args(
            destination_x=None,
            destination_z=None,
            destination_waypoint_json=None,
            destination_waypoint_id="wp1",
        )
        errors2 = validate_args(args2)
        self.assertIn("destination-waypoint-json-required", errors2)


class BuildMarkdownTests(unittest.TestCase):
    """Test the markdown summary builder."""

    def test_produces_valid_markdown(self) -> None:
        summary = {
            "generatedAtUtc": "2026-05-29T12:00:00Z",
            "status": "passed",
            "verdict": "route-loop-arrived",
            "total": {
                "iterationCount": 3,
                "totalDurationSeconds": 45.0,
                "initialPlanarDistance": 37.5,
                "finalPlanarDistance": 1.2,
                "totalProgressDistance": 36.3,
                "turnsExecuted": 2,
                "forwardSteps": 3,
            },
            "iterations": [
                {
                    "iteration": 1,
                    "planarDistance": 37.5,
                    "plan": {"firstAction": "turn-left"},
                    "turnDirection": "left",
                    "computedTurnHoldMs": 226,
                    "turnResult": {"status": "passed"},
                    "forwardResult": {"status": "not-needed"},
                },
                {
                    "iteration": 2,
                    "planarDistance": 20.0,
                    "plan": {"firstAction": "forward"},
                    "turnResult": {"status": "not-needed"},
                    "forwardResult": {"status": "passed", "routeStatus": "progress"},
                },
                {
                    "iteration": 3,
                    "planarDistance": 1.2,
                    "plan": {"firstAction": "forward"},
                    "turnResult": {"status": "not-needed"},
                    "forwardResult": {"status": "passed", "routeStatus": "arrived"},
                },
            ],
            "blockers": [],
            "warnings": [],
            "errors": [],
            "safety": {
                "movementSent": True,
                "inputSent": True,
                "navigationControl": True,
                "facingPromotion": False,
            },
        }
        md = build_markdown(summary)
        self.assertIn("Static owner continuous route run", md)
        self.assertIn("Status: `passed`", md)
        self.assertIn("route-loop-arrived", md)
        self.assertIn("Iterations: `3`", md)
        self.assertIn("Total progress: `36.3`", md)
        self.assertIn("Turns executed: `2`", md)
        self.assertIn("Forward steps: `3`", md)
        # Each iteration should be listed
        self.assertIn("### Iteration 1", md)
        self.assertIn("### Iteration 2", md)
        self.assertIn("### Iteration 3", md)

    def test_blockers_and_warnings_appear(self) -> None:
        summary = {
            "generatedAtUtc": "2026-05-29T12:00:00Z",
            "status": "blocked",
            "verdict": "route-loop-blocked",
            "total": {
                "iterationCount": 1,
                "totalDurationSeconds": 10.0,
                "initialPlanarDistance": 37.5,
                "finalPlanarDistance": 37.5,
                "totalProgressDistance": 0.0,
                "turnsExecuted": 1,
                "forwardSteps": 0,
            },
            "iterations": [],
            "blockers": ["max-total-seconds-reached:300", "forward-no-progress-3-consecutive-stuck"],
            "warnings": ["dry-run-only-no-input-sent"],
            "errors": [],
            "safety": {
                "movementSent": False,
                "inputSent": True,
                "navigationControl": False,
                "facingPromotion": False,
            },
        }
        md = build_markdown(summary)
        self.assertIn("## Blockers", md)
        self.assertIn("max-total-seconds-reached:300", md)
        self.assertIn("forward-no-progress-3-consecutive-stuck", md)
        self.assertIn("## Warnings", md)
        self.assertIn("dry-run-only-no-input-sent", md)

    def test_errors_section_shows_when_present(self) -> None:
        summary = {
            "generatedAtUtc": "2026-05-29T12:00:00Z",
            "status": "failed",
            "verdict": "route-loop-error",
            "total": {"iterationCount": 0},
            "iterations": [],
            "blockers": [],
            "warnings": [],
            "errors": ["ValueError:something-went-wrong"],
            "safety": {},
        }
        md = build_markdown(summary)
        self.assertIn("## Errors", md)
        self.assertIn("ValueError:something-went-wrong", md)


class CompactTests(unittest.TestCase):
    """Test the final summary compaction."""

    def test_compact_preserves_all_keys(self) -> None:
        summary = {
            "status": "passed",
            "verdict": "route-loop-arrived",
            "total": {
                "iterationCount": 2,
                "totalDurationSeconds": 30.0,
                "initialPlanarDistance": 37.5,
                "finalPlanarDistance": 1.0,
                "totalProgressDistance": 36.5,
                "turnsExecuted": 1,
                "forwardSteps": 2,
            },
            "artifacts": {
                "summaryJson": "captures/route/summary.json",
                "summaryMarkdown": "captures/route/summary.md",
            },
            "safety": {
                "movementSent": True,
                "inputSent": True,
                "navigationControl": True,
                "facingPromotion": False,
            },
            "blockers": [],
            "warnings": [],
            "errors": [],
        }
        result = compact(summary)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verdict"], "route-loop-arrived")
        self.assertEqual(result["iterationCount"], 2)
        self.assertEqual(result["totalProgressDistance"], 36.5)
        self.assertEqual(result["turnsExecuted"], 1)
        self.assertEqual(result["forwardSteps"], 2)
        self.assertTrue(result["movementSent"])

    def test_compact_with_blocked_verdict(self) -> None:
        summary = {
            "status": "blocked",
            "verdict": "forward-no-progress-3-consecutive-stuck",
            "total": {
                "iterationCount": 4,
                "totalDurationSeconds": 65.0,
                "initialPlanarDistance": 37.5,
                "finalPlanarDistance": 37.5,
                "totalProgressDistance": 0.0,
                "turnsExecuted": 1,
                "forwardSteps": 3,
            },
            "artifacts": {},
            "safety": {"movementSent": True, "inputSent": True},
            "blockers": ["forward-no-progress-3-consecutive-stuck"],
            "warnings": [],
            "errors": [],
        }
        result = compact(summary)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["forwardSteps"], 3)
        self.assertIn("forward-no-progress-3-consecutive-stuck", result["blockers"])
        self.assertEqual(result["totalProgressDistance"], 0.0)


class SafetyGateTests(unittest.TestCase):
    """Test that the run() function enforces all safety gates."""

    def test_blocks_without_turn_approval(self) -> None:
        args = _make_args(turn_approved=False)
        with tempfile.TemporaryDirectory() as tmp:
            args.repo_root = tmp
            args.output_root = Path(tmp) / "out"
            result = run(args)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["verdict"], "turn-approval-required")
            self.assertIn("turn-approved-flag-required", result["blockers"])

    def test_blocks_without_movement_approval(self) -> None:
        args = _make_args(movement_approved=False)
        with tempfile.TemporaryDirectory() as tmp:
            args.repo_root = tmp
            args.output_root = Path(tmp) / "out"
            result = run(args)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["verdict"], "movement-approval-required")
            self.assertIn("movement-approved-flag-required", result["blockers"])

    def test_blocks_without_candidate_turn_control(self) -> None:
        args = _make_args(allow_candidate_turn_control=False)
        with tempfile.TemporaryDirectory() as tmp:
            args.repo_root = tmp
            args.output_root = Path(tmp) / "out"
            result = run(args)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["verdict"], "candidate-turn-control-approval-required")
            self.assertIn("allow-candidate-turn-control-flag-required", result["blockers"])

    def test_invalid_args_produces_error_status(self) -> None:
        args = _make_args(destination_x=None, destination_z=None, max_iterations=0)
        with tempfile.TemporaryDirectory() as tmp:
            args.repo_root = tmp
            args.output_root = Path(tmp) / "out"
            result = run(args)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["verdict"], "invalid-arguments")
            self.assertIn("destination-x-and-z-required", result["errors"])
            self.assertIn("max-iterations-must-be-positive", result["errors"])


class DryRunTests(unittest.TestCase):
    """Test that dry-run mode works correctly."""

    def test_dry_run_plans_without_input(self) -> None:
        """Dry run should never send input, regardless of whether RIFT is running."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args = _make_args(
                dry_run=True,
                skip_readback_freshness_gate=True,
                repo_root=str(tmp_path),
                output_root=str(tmp_path / "out"),
                current_truth_json=str(tmp_path / "docs" / "recovery" / "current-truth.json"),
            )
            # Create a dummy truth file to prevent file-not-found errors
            truth_dir = tmp_path / "docs" / "recovery"
            truth_dir.mkdir(parents=True, exist_ok=True)
            (truth_dir / "current-truth.json").write_text(
                json.dumps({"target": {"processName": "rift_x64"}}), encoding="utf-8",
            )

            result = run(args)
            # Verify the dry-run contract: no input was sent regardless of RIFT availability
            safety = result.get("safety", {})
            self.assertFalse(safety.get("inputSent", False))
            self.assertFalse(safety.get("movementSent", False))


class RoutePersistenceTests(unittest.TestCase):
    """Test that the route runner persists summaries and markdown correctly."""

    def test_summary_json_and_md_are_written_to_output_dir(self) -> None:
        """When run() returns a result, artifacts should be writable to the run directory."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args = _make_args(
                turn_approved=False,  # Will block on safety gate before writing
                repo_root=str(tmp_path),
                output_root=str(tmp_path / "out"),
            )
            result = run(args)
            # The output dir for artifacts is created inside run()
            # With turn_approved=False, it should block early but still create the dir
        # The function should return a valid result dict regardless of blocking
        self.assertEqual(result["kind"], "static-owner-continuous-route")
        self.assertIn("artifacts", result)
        self.assertIn("summaryJson", result["artifacts"])

    def test_run_on_missing_truth_file_still_returns_structured_output(self) -> None:
        """Even without a truth file, the run() function should return structured JSON."""
        import scripts.static_owner_continuous_route_runner as route_runner

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Mock run_child to return a failed envelope (no JSON, no process)
        with mock.patch.object(route_runner, "run_child") as mock_run:
            # The readback freshness gate runs first; mock it to pass so we
            # reach the initial-state call that this test targets.
            def _mock_run_side_effect(*, label: str, command: Sequence[str], cwd: Path,
                                        child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
                if label == "00-readback-freshness":
                    return {
                        "label": label,
                        "ok": True,
                        "exitCode": 0,
                        "json": {
                            "summaryJson": str(tmp_path / "mocked-readback-summary.json"),
                            "status": "passed",
                        },
                        "commandPath": str(tmp_path / "cmd.json"),
                        "stdoutPath": str(tmp_path / "stdout.txt"),
                        "stderrPath": str(tmp_path / "stderr.txt"),
                        "stdoutPreview": "",
                        "stderrPreview": "",
                        "durationSeconds": 0.05,
                    }
                return {
                    "label": label,
                    "ok": False,
                    "exitCode": 1,
                    "json": None,
                    "commandPath": str(tmp_path / "cmd.json"),
                    "stdoutPath": str(tmp_path / "stdout.txt"),
                    "stderrPath": str(tmp_path / "stderr.txt"),
                    "stdoutPreview": "",
                    "stderrPreview": "",
                    "durationSeconds": 0.05,
                }

            mock_run.side_effect = _mock_run_side_effect
            args = _make_args(
                repo_root=str(tmp_path),
                output_root=str(tmp_path / "out"),
                current_truth_json=str(tmp_path / "nonexistent.json"),
            )
            result = route_runner.run(args)

            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["verdict"], "initial-state-readback-failed")
            self.assertIn("kind", result)
            self.assertEqual(result["kind"], "static-owner-continuous-route")


class UtilityFunctionTests(unittest.TestCase):
    """Test standalone utility helpers used by the route runner."""

    def test_safe_mapping_with_none(self) -> None:
        self.assertEqual(safe_mapping(None), {})

    def test_safe_mapping_with_dict(self) -> None:
        self.assertEqual(safe_mapping({"a": 1}), {"a": 1})

    def test_safe_mapping_with_empty_dict(self) -> None:
        self.assertEqual(safe_mapping({}), {})

    def test_compute_turn_hold_ms_consistency(self) -> None:
        """Verify turn hold roughly matches the calibrated rate."""
        # For a 60-degree turn: 60 / 0.177 ≈ 339ms
        hold = compute_turn_hold_ms(60.0)
        expected_approx = 60.0 / _TURN_RATE_DEGREES_PER_MS
        self.assertAlmostEqual(hold, expected_approx, delta=2)

    def test_compute_forward_hold_ms_speed_match(self) -> None:
        """Verify forward hold formula matches cruising speed."""
        # For 30m: accel 200ms + (30-1)/6.1*1000 ≈ 200 + 4754 = 4954ms
        hold = compute_forward_hold_ms(30.0)
        cruising_distance = 30.0 - FORWARD_ACCEL_DISTANCE_M
        cruising_ms = (cruising_distance / FORWARD_SPEED_M_PER_S) * 1000
        expected = FORWARD_ACCEL_TIME_MS + int(cruising_ms)
        self.assertAlmostEqual(hold, expected, delta=5)

    def test_planar_distance_calibration_curve(self) -> None:
        """Verify the calibration curve is monotonic and sensible."""
        # More distance = more hold time (monotonic)
        holds = [compute_forward_hold_ms(d) for d in [1, 5, 10, 20, 30, 50]]
        for i in range(1, len(holds)):
            self.assertGreaterEqual(holds[i], holds[i - 1])

    def test_turn_hold_monotonic(self) -> None:
        """More degrees = more turn hold time (monotonic)."""
        holds = [compute_turn_hold_ms(d) for d in [0, 10, 30, 45, 90, 135, 180]]
        for i in range(1, len(holds)):
            self.assertGreaterEqual(holds[i], holds[i - 1])


class MockedIntegrationTests(unittest.TestCase):
    """Full run() pipeline with mocked subprocess calls."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.tmp_path = Path(self.temp_dir.name)

        # Create a minimal truth file so path resolution doesn't fail
        truth_dir = self.tmp_path / "docs" / "recovery"
        truth_dir.mkdir(parents=True, exist_ok=True)
        (truth_dir / "current-truth.json").write_text(
            json.dumps({"target": {"processName": "rift_x64"}}), encoding="utf-8",
        )

    def _make_envelope(self, label: str, json_data: dict[str, Any] | None) -> dict[str, Any]:
        """Create a run_child envelope with a deterministic summaryJson path."""
        summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
        return {
            "label": label,
            "ok": json_data is not None,
            "exitCode": 0 if json_data is not None else 1,
            "json": {"summaryJson": summary_path} if json_data else None,
            "commandPath": str(self.tmp_path / f"{label}.command.json"),
            "stdoutPath": str(self.tmp_path / f"{label}.stdout.txt"),
            "stderrPath": str(self.tmp_path / f"{label}.stderr.txt"),
            "stdoutPreview": "",
            "stderrPreview": "",
            "durationSeconds": 0.05,
        }

    def _mock_run_child_fn(self) -> Any:
        """Return a side_effect function that uses label to determine the envelope."""
        full_summaries: dict[str, dict[str, Any]] = {}

        def add_state(label: str, coord: dict[str, float], yaw: float, turn_class: str) -> None:
            summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
            full_summaries[summary_path] = {
                "status": "passed",
                "latestState": {
                    "coordinate": coord,
                    "yawDegrees": yaw,
                    "turnRateClassification": turn_class,
                },
            }

        def add_plan(label: str, first_action: str, turn_magnitude: str, turn_dir: str | None,
                     signed_delta: float, abs_delta: float, plan_dist: float,
                     within_radius: bool, within_align: bool, exec_blocked: bool,
                     engine_class: str, blockers: list[str] | None = None) -> None:
            summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
            nav_target: dict[str, Any] = {
                "suggestedTurnDirection": turn_dir,
                "signedBearingDeltaDegrees": signed_delta,
                "absoluteBearingDeltaDegrees": abs_delta,
                "planarDistance": plan_dist,
                "withinArrivalRadius": within_radius,
                "withinAlignmentThreshold": within_align,
            }
            full_summaries[summary_path] = {
                "status": "passed",
                "plan": {
                    "firstAction": first_action,
                    "turnMagnitudeClass": turn_magnitude,
                    "navigationTarget": nav_target,
                    "executionBlocked": exec_blocked,
                    "executionBlockers": blockers or [],
                    "engineTurnRateClassification": engine_class,
                },
            }

        def add_turn(label: str, post_yaw: float, abs_delta: float) -> None:
            summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
            full_summaries[summary_path] = {
                "status": "passed",
                "turnSamples": [{"postYawDegrees": post_yaw, "absoluteYawDeltaDegrees": abs_delta}],
            }

        def add_forward(label: str, route_status: str, progress: float,
                        initial_dist: float, final_dist: float,
                        no_progress_sub: str | None = None) -> None:
            summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
            full_summaries[summary_path] = {
                "status": "passed" if route_status in ("progress", "arrived") else "blocked",
                "routeResult": {
                    "routeStatus": route_status,
                    "totalProgressDistance": progress,
                    "initialPlanarDistance": initial_dist,
                    "finalPlanarDistance": final_dist,
                    "noProgressSubClassification": no_progress_sub if route_status == "no-progress" else None,
                },
            }

        def get_summary(path: str) -> dict[str, Any]:
            if path in full_summaries:
                return full_summaries[path]
            raise ValueError(f"Unexpected mocked summary path: {path}")

        def mock_run(*, label: str, command: Sequence[str], cwd: Path,
                     child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
            return self._make_envelope(
                label,
                {"summaryJson": str(self.tmp_path / f"mocked-{label}-summary.json")},
            )

        return add_state, add_plan, add_turn, add_forward, get_summary, mock_run

    # --- Tests ---

    def test_two_iteration_arrival(self) -> None:
        """Full happy path: state → plan → turn → replan → forward → arrived."""
        import scripts.static_owner_continuous_route_runner as route_runner

        add_state, add_plan, add_turn, add_forward, get_summary, mock_run = self._mock_run_child_fn()

        # Register all expected summaries
        add_state("00-initial-state", {"x": 7261.83, "y": 821.45, "z": 2998.98}, 80.82, "stationary")
        add_plan("00-initial-plan", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_plan("plan-001", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_turn("turn-001-left", -36.35, 42.35)
        add_plan("replan-001", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-001", "arrived", 33.0, 4.5, 0.5)

        args = _make_args(
            skip_readback_freshness_gate=True,
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verdict"], "route-loop-arrived")
        self.assertEqual(result["total"]["iterationCount"], 1)
        self.assertEqual(result["total"]["turnsExecuted"], 1)
        self.assertEqual(result["total"]["forwardSteps"], 1)
        self.assertGreater(result["total"]["totalProgressDistance"], 0)
        self.assertTrue(result["safety"]["inputSent"])
        self.assertTrue(result["safety"]["movementSent"])
        self.assertTrue(result["safety"]["navigationControl"])
        self.assertEqual(result["iterations"][0]["turnDirection"], "left")

    def test_three_consecutive_forward_no_progress_blocks(self) -> None:
        """3 consecutive forward failures should trigger no-progress guard."""
        import scripts.static_owner_continuous_route_runner as route_runner

        add_state, add_plan, add_turn, add_forward, get_summary, mock_run = self._mock_run_child_fn()

        # Initial state and plan — need a turn first, then aligned
        add_state("00-initial-state", {"x": 7261.83, "y": 821.45, "z": 2998.98}, 80.82, "stationary")
        add_plan("00-initial-plan", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_plan("plan-001", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_turn("turn-001-left", -36.35, 42.35)
        add_plan("replan-001", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        # 3 forward attempts — all fail (no progress, not arrived)
        # Each iteration re-plans before forward, so register plan-002/003 too
        add_plan("plan-002", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-001", "blocked", 0.0, 4.5, 4.5)
        add_plan("plan-003", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-002", "blocked", 0.0, 4.5, 4.5)
        add_forward("forward-003", "blocked", 0.0, 4.5, 4.5)

        args = _make_args(
            max_iterations=5,
            skip_readback_freshness_gate=True,
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("forward-no-progress-3-consecutive-stuck", result["blockers"])
        # 3 iterations ran, but all forwards failed — total_forwards stays 0
        self.assertEqual(result["total"]["iterationCount"], 3)
        self.assertEqual(result["total"]["forwardSteps"], 0)
        self.assertEqual(result["total"]["totalProgressDistance"], 0.0)

    def test_already_arrived_returns_immediately(self) -> None:
        """If initial plan shows withinArrivalRadius, skip loop."""
        import scripts.static_owner_continuous_route_runner as route_runner

        add_state, add_plan, add_turn, add_forward, get_summary, mock_run = self._mock_run_child_fn()

        add_state("00-initial-state", {"x": 7285.0, "y": 821.0, "z": 2980.0}, 45.0, "stationary")
        add_plan("00-initial-plan", "stop", "aligned", "aligned",
                 0.5, 0.5, 1.5, True, True, False, "stationary")

        args = _make_args(
            skip_readback_freshness_gate=True,
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verdict"], "already-arrived")
        self.assertIn("destination-already-within-arrival-radius", result["warnings"])
        self.assertEqual(result["total"]["iterationCount"], 0)
        # No input was sent since we never entered the loop
        self.assertFalse(result["safety"]["inputSent"])

    def test_execution_blocked_breaks_loop(self) -> None:
        """If plan shows executionBlocked, break out of loop."""
        import scripts.static_owner_continuous_route_runner as route_runner

        add_state, add_plan, add_turn, add_forward, get_summary, mock_run = self._mock_run_child_fn()

        add_state("00-initial-state", {"x": 7261.83, "y": 821.45, "z": 2998.98}, 80.82, "stationary")
        add_plan("00-initial-plan", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        # Plan iteration 1 is execution blocked
        add_plan("plan-001", "blocked", "blocked", None,
                 0.0, 0.0, 37.49, False, False, True, "unknown",
                 blockers=["turn-direction-mismatch-atan2-wants-left-but-engine-0x304-is-turning-right"])

        args = _make_args(
            max_iterations=5,
            skip_readback_freshness_gate=True,
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["verdict"], "route-loop-plan-execution-blocked")
        self.assertIn(
            "turn-direction-mismatch-atan2-wants-left-but-engine-0x304-is-turning-right",
            result["blockers"],
        )

    def test_turn_json_missing_does_not_block_loop(self) -> None:
        """If turn returns no JSON, the loop should continue with a warning."""
        import scripts.static_owner_continuous_route_runner as route_runner

        # We'll mock run_child directly: return a valid envelope for most calls,
        # but a failed one for the turn call
        def mock_break(*, label: str, command: Sequence[str], cwd: Path,
                       child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
            # Return failed envelope for turn-001, valid for everything else
            if label == "turn-001-left":
                return self._make_envelope(label, None)
            return self._make_envelope(
                label,
                {"summaryJson": str(self.tmp_path / f"mocked-{label}-summary.json")},
            )

        add_state, add_plan, add_turn, add_forward, get_summary, _ = self._mock_run_child_fn()

        add_state("00-initial-state", {"x": 7261.83, "y": 821.45, "z": 2998.98}, 80.82, "stationary")
        add_plan("00-initial-plan", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_plan("plan-001", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_plan("replan-001", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-001", "arrived", 33.0, 4.5, 0.5)

        args = _make_args(
            skip_readback_freshness_gate=True,
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_break):
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verdict"], "route-loop-arrived")
        self.assertTrue(any("turn-json-missing" in (w or "") for w in result.get("warnings", [])))

    def test_forward_json_missing_does_not_block_loop(self) -> None:
        """If forward returns no JSON, the loop should continue with a warning."""
        import scripts.static_owner_continuous_route_runner as route_runner

        def mock_break(*, label: str, command: Sequence[str], cwd: Path,
                       child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
            if label == "forward-001":
                return self._make_envelope(label, None)
            return self._make_envelope(
                label,
                {"summaryJson": str(self.tmp_path / f"mocked-{label}-summary.json")},
            )

        add_state, add_plan, add_turn, add_forward, get_summary, _ = self._mock_run_child_fn()

        add_state("00-initial-state", {"x": 7261.83, "y": 821.45, "z": 2998.98}, 80.82, "stationary")
        add_plan("00-initial-plan", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_plan("plan-001", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_turn("turn-001-left", -36.35, 42.35)
        add_plan("replan-001", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")

        args = _make_args(
            max_iterations=5,
            skip_readback_freshness_gate=True,
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_break):
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertIn(result["status"], ("blocked", "failed"))
        self.assertTrue(any("forward-json-missing" in (w or "") for w in result.get("warnings", [])))


class LoadWaypointSequenceTests(unittest.TestCase):
    """Test loading waypoints from JSON for multi-waypoint sequencing."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.waypoints_file = self.root / "waypoints.json"
        self.waypoints_file.write_text(json.dumps({
            "schemaVersion": 1,
            "waypoints": [
                {"id": "wp1", "label": "Waypoint 1", "x": 100.0, "y": 50.0, "z": 200.0, "arrivalRadius": 2.5},
                {"id": "wp2", "label": "Waypoint 2", "x": 300.0, "y": 60.0, "z": 400.0},
                {"id": "wp3", "label": "Waypoint 3", "x": 500.0, "y": 70.0, "z": 600.0, "arrivalRadius": 1.0},
            ],
        }), encoding="utf-8")

    def test_loads_all_waypoints_when_no_ids_specified(self) -> None:
        result = load_waypoint_sequence(self.root, str(self.waypoints_file))
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["id"], "wp1")
        self.assertEqual(result[0]["x"], 100.0)
        self.assertEqual(result[0]["y"], 50.0)
        self.assertEqual(result[0]["z"], 200.0)
        self.assertEqual(result[0]["arrivalRadius"], 2.5)
        self.assertEqual(result[1]["id"], "wp2")
        self.assertIsNone(result[1]["arrivalRadius"])

    def test_filters_by_specific_ids(self) -> None:
        result = load_waypoint_sequence(self.root, str(self.waypoints_file), "wp1,wp3")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "wp1")
        self.assertEqual(result[1]["id"], "wp3")

    def test_filters_preserves_requested_order(self) -> None:
        result = load_waypoint_sequence(self.root, str(self.waypoints_file), "wp3,wp1")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "wp3")
        self.assertEqual(result[1]["id"], "wp1")

    def test_single_id_filter(self) -> None:
        result = load_waypoint_sequence(self.root, str(self.waypoints_file), "wp2")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "wp2")
        self.assertEqual(result[0]["label"], "Waypoint 2")

    def test_raises_on_missing_id(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            load_waypoint_sequence(self.root, str(self.waypoints_file), "wp1,wp999")
        self.assertIn("waypoint-ids-not-found", str(ctx.exception))
        self.assertIn("wp999", str(ctx.exception))

    def test_raises_on_empty_ids_string(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            load_waypoint_sequence(self.root, str(self.waypoints_file), "")
        self.assertIn("waypoint-sequence-ids-empty", str(ctx.exception))

    def test_raises_on_missing_coordinate(self) -> None:
        bad_file = self.root / "bad.json"
        bad_file.write_text(json.dumps({
            "waypoints": [
                {"id": "wp1", "x": 100.0, "z": 200.0},  # missing y
            ],
        }), encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            load_waypoint_sequence(self.root, str(bad_file))
        self.assertIn("waypoint-missing-coordinate:y", str(ctx.exception))

    def test_raises_on_empty_waypoints_array(self) -> None:
        empty_file = self.root / "empty.json"
        empty_file.write_text(json.dumps({"waypoints": []}), encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            load_waypoint_sequence(self.root, str(empty_file))
        self.assertIn("waypoint-sequence-empty", str(ctx.exception))

    def test_uses_id_as_label_when_label_missing(self) -> None:
        no_label_file = self.root / "no_label.json"
        no_label_file.write_text(json.dumps({
            "waypoints": [{"id": "start", "x": 0.0, "y": 0.0, "z": 0.0}],
        }), encoding="utf-8")
        result = load_waypoint_sequence(self.root, str(no_label_file))
        self.assertEqual(result[0]["label"], "start")

    def test_loads_from_relative_path(self) -> None:
        result = load_waypoint_sequence(self.root, "waypoints.json")
        self.assertEqual(len(result), 3)


class MakeWaypointArgsTests(unittest.TestCase):
    """Test creation of per-leg args from waypoint data."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_root = Path(self.temp_dir.name) / "captures"

    def test_sets_coordinates_and_label(self) -> None:
        args = _make_args()
        waypoint = {"id": "wp1", "label": "Start", "x": 100.0, "y": 50.0, "z": 200.0, "arrivalRadius": None}
        leg_args = make_waypoint_args(args, waypoint, 1, self.output_root)
        self.assertEqual(leg_args.destination_x, 100.0)
        self.assertEqual(leg_args.destination_y, 50.0)
        self.assertEqual(leg_args.destination_z, 200.0)
        self.assertEqual(leg_args.destination_label, "Start")
        self.assertIsNone(leg_args.destination_waypoint_json)
        self.assertIsNone(leg_args.destination_waypoint_id)

    def test_overrides_arrival_radius(self) -> None:
        args = _make_args()
        waypoint = {"id": "wp1", "label": "Target", "x": 100.0, "y": 0.0, "z": 200.0, "arrivalRadius": 1.5}
        leg_args = make_waypoint_args(args, waypoint, 1, self.output_root)
        self.assertEqual(leg_args.arrival_radius, 1.5)

    def test_preserves_default_arrival_radius(self) -> None:
        args = _make_args()
        waypoint = {"id": "wp1", "label": "Target", "x": 100.0, "y": 0.0, "z": 200.0, "arrivalRadius": None}
        leg_args = make_waypoint_args(args, waypoint, 1, self.output_root)
        self.assertEqual(leg_args.arrival_radius, DEFAULT_ARRIVAL_RADIUS)

    def test_sets_per_leg_output_root(self) -> None:
        args = _make_args()
        waypoint = {"id": "wp1", "label": "A", "x": 0.0, "y": 0.0, "z": 0.0, "arrivalRadius": None}
        leg_args = make_waypoint_args(args, waypoint, 2, self.output_root)
        expected_output = str(self.output_root / "leg-02")
        self.assertEqual(leg_args.output_root, expected_output)

    def test_preserves_other_args_unchanged(self) -> None:
        args = _make_args(max_iterations=5)
        waypoint = {"id": "wp1", "label": "A", "x": 0.0, "y": 0.0, "z": 0.0, "arrivalRadius": None}
        leg_args = make_waypoint_args(args, waypoint, 1, self.output_root)
        self.assertEqual(leg_args.max_iterations, 5)
        self.assertEqual(leg_args.turn_approved, True)
        self.assertEqual(leg_args.movement_approved, True)


class CompactSequenceSummaryTests(unittest.TestCase):
    """Test sequence summary compaction."""

    def test_compact_preserves_all_sequence_keys(self) -> None:
        summary = {
            "status": "passed",
            "verdict": "sequence-all-waypoints-reached",
            "kind": "static-owner-continuous-route-sequence",
            "total": {
                "totalLegs": 3,
                "legsArrived": 3,
                "legsFailed": 0,
                "totalDurationSeconds": 120.0,
                "totalTurnsExecuted": 4,
                "totalForwardSteps": 6,
                "totalProgressDistance": 150.0,
            },
            "safety": {
                "movementSent": True,
                "inputSent": True,
                "navigationControl": True,
            },
            "destinationRequest": {
                "waypointSequenceJson": "waypoints.json",
                "waypointSequenceIds": "wp1,wp2,wp3",
            },
            "artifacts": {
                "summaryJson": "captures/sequence/summary.json",
                "summaryMarkdown": "captures/sequence/summary.md",
            },
            "blockers": [],
            "warnings": [],
            "errors": [],
        }
        result = compact_sequence_summary(summary)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verdict"], "sequence-all-waypoints-reached")
        self.assertEqual(result["totalLegs"], 3)
        self.assertEqual(result["legsArrived"], 3)
        self.assertEqual(result["totalTurnsExecuted"], 4)
        self.assertEqual(result["totalForwardSteps"], 6)
        self.assertEqual(result["totalProgressDistance"], 150.0)
        self.assertTrue(result["movementSent"])

    def test_compact_with_blocked_sequence(self) -> None:
        summary = {
            "status": "blocked",
            "verdict": "sequence-blocked",
            "kind": "static-owner-continuous-route-sequence",
            "total": {
                "totalLegs": 3,
                "legsArrived": 1,
                "legsFailed": 1,
                "totalDurationSeconds": 45.0,
                "totalTurnsExecuted": 2,
                "totalForwardSteps": 3,
                "totalProgressDistance": 50.0,
            },
            "safety": {"movementSent": True, "inputSent": True, "navigationControl": False},
            "destinationRequest": {},
            "artifacts": {},
            "blockers": ["leg-2-forward-no-progress-3-consecutive-stuck"],
            "warnings": ["leg-2-dry-run-only-no-input-sent"],
            "errors": [],
        }
        result = compact_sequence_summary(summary)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["legsArrived"], 1)
        self.assertEqual(result["legsFailed"], 1)
        self.assertIn("leg-2-forward-no-progress-3-consecutive-stuck", result["blockers"])


class BuildSequenceMarkdownTests(unittest.TestCase):
    """Test sequence markdown builder."""

    def test_full_sequence_markdown(self) -> None:
        summary = {
            "generatedAtUtc": "2026-05-29T12:00:00Z",
            "status": "passed",
            "verdict": "sequence-all-waypoints-reached",
            "waypointSequence": [
                {"id": "wp1", "label": "Waypoint 1"},
                {"id": "wp2", "label": "Waypoint 2"},
            ],
            "total": {
                "totalLegs": 2,
                "legsArrived": 2,
                "legsFailed": 0,
                "totalDurationSeconds": 65.0,
                "totalTurnsExecuted": 3,
                "totalForwardSteps": 5,
                "totalProgressDistance": 100.0,
            },
            "safety": {
                "movementSent": True,
                "inputSent": True,
                "navigationControl": True,
            },
            "legs": [
                {
                    "status": "passed",
                    "verdict": "route-loop-arrived",
                    "total": {"iterationCount": 2, "turnsExecuted": 1, "forwardSteps": 2},
                },
                {
                    "status": "passed",
                    "verdict": "route-loop-arrived",
                    "total": {"iterationCount": 3, "turnsExecuted": 2, "forwardSteps": 3},
                },
            ],
            "blockers": [],
            "warnings": [],
            "errors": [],
        }
        md = build_sequence_markdown(summary)
        self.assertIn("Static owner continuous route sequence", md)
        self.assertIn("Status: `passed`", md)
        self.assertIn("Total legs: `2`", md)
        self.assertIn("Arrived: `2`", md)
        self.assertIn("Failed: `0`", md)
        self.assertIn("Total progress: `100.0`", md)
        self.assertIn("### Leg 1: Waypoint 1", md)
        self.assertIn("### Leg 2: Waypoint 2", md)
        self.assertIn("Iterations: `2`", md)

    def test_sequence_markdown_with_blockers(self) -> None:
        summary = {
            "generatedAtUtc": "2026-05-29T12:00:00Z",
            "status": "blocked",
            "verdict": "sequence-blocked",
            "waypointSequence": [{"id": "wp1", "label": "Failed Waypoint"}],
            "total": {
                "totalLegs": 1,
                "legsArrived": 0,
                "legsFailed": 1,
                "totalDurationSeconds": 10.0,
                "totalTurnsExecuted": 1,
                "totalForwardSteps": 0,
                "totalProgressDistance": 0.0,
            },
            "safety": {"movementSent": True, "inputSent": True, "navigationControl": False},
            "legs": [{
                "status": "blocked",
                "verdict": "route-loop-blocked",
                "total": {"iterationCount": 1, "turnsExecuted": 1, "forwardSteps": 0},
            }],
            "blockers": ["leg-1-forward-no-progress-3-consecutive-stuck"],
            "warnings": [],
            "errors": [],
        }
        md = build_sequence_markdown(summary)
        self.assertIn("## Blockers", md)
        self.assertIn("leg-1-forward-no-progress-3-consecutive-stuck", md)

    def test_sequence_markdown_with_errors(self) -> None:
        summary = {
            "generatedAtUtc": "2026-05-29T12:00:00Z",
            "status": "failed",
            "verdict": "sequence-error",
            "waypointSequence": [],
            "total": {"totalLegs": 0, "legsArrived": 0, "legsFailed": 0},
            "safety": {},
            "legs": [],
            "blockers": [],
            "warnings": [],
            "errors": ["ValueError:waypoint-sequence-empty"],
        }
        md = build_sequence_markdown(summary)
        self.assertIn("## Errors", md)
        self.assertIn("ValueError:waypoint-sequence-empty", md)


class ReadbackFreshnessGateTests(unittest.TestCase):
    """Test the pre-movement static resolver readback freshness gate."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.tmp_path = Path(self.temp_dir.name)
        truth_dir = self.tmp_path / "docs" / "recovery"
        truth_dir.mkdir(parents=True, exist_ok=True)
        (truth_dir / "current-truth.json").write_text(
            json.dumps({"target": {"processName": "rift_x64"}}), encoding="utf-8",
        )

    def test_readback_freshness_gate_blocks_when_no_json_returned(self) -> None:
        """Gate should block (failed) when readback returns no parseable JSON."""
        import scripts.static_owner_continuous_route_runner as route_runner

        def mock_run(*, label: str, command: Sequence[str], cwd: Path,
                     child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
            if label == "00-readback-freshness":
                return {
                    "label": label,
                    "ok": False,
                    "exitCode": 1,
                    "json": None,
                    "commandPath": str(self.tmp_path / "cmd.json"),
                    "stdoutPath": str(self.tmp_path / "stdout.txt"),
                    "stderrPath": str(self.tmp_path / "stderr.txt"),
                    "stdoutPreview": "",
                    "stderrPreview": "",
                    "durationSeconds": 0.05,
                }
            return {
                "label": label,
                "ok": True,
                "exitCode": 0,
                "json": {"summaryJson": str(self.tmp_path / f"mocked-{label}-summary.json")},
                "commandPath": str(self.tmp_path / f"{label}.command.json"),
                "stdoutPath": str(self.tmp_path / f"{label}.stdout.txt"),
                "stderrPath": str(self.tmp_path / f"{label}.stderr.txt"),
                "stdoutPreview": "",
                "stderrPreview": "",
                "durationSeconds": 0.05,
            }

        args = _make_args(
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run):
            result = route_runner.run(args)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["verdict"], "static-resolver-readback-freshness-failed")
        self.assertIn("static-resolver-readback-freshness-gate-no-json", result["blockers"])

    def test_readback_freshness_gate_blocks_when_status_is_blocked(self) -> None:
        """Gate should block when readback returns status=blocked."""
        import scripts.static_owner_continuous_route_runner as route_runner

        def mock_run(*, label: str, command: Sequence[str], cwd: Path,
                     child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
            if label == "00-readback-freshness":
                return {
                    "label": label,
                    "ok": True,
                    "exitCode": 2,
                    "json": {
                        "summaryJson": str(self.tmp_path / "mocked-readback-summary.json"),
                        "status": "blocked",
                    },
                    "commandPath": str(self.tmp_path / "cmd.json"),
                    "stdoutPath": str(self.tmp_path / "stdout.txt"),
                    "stderrPath": str(self.tmp_path / "stderr.txt"),
                    "stdoutPreview": "",
                    "stderrPreview": "",
                    "durationSeconds": 0.05,
                }
            return {
                "label": label,
                "ok": True,
                "exitCode": 0,
                "json": {"summaryJson": str(self.tmp_path / f"mocked-{label}-summary.json")},
                "commandPath": str(self.tmp_path / f"{label}.command.json"),
                "stdoutPath": str(self.tmp_path / f"{label}.stdout.txt"),
                "stderrPath": str(self.tmp_path / f"{label}.stderr.txt"),
                "stdoutPreview": "",
                "stderrPreview": "",
                "durationSeconds": 0.05,
            }

        args = _make_args(
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run):
            result = route_runner.run(args)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["verdict"], "static-resolver-readback-freshness-blocked")
        self.assertIn("static-resolver-readback-freshness-gate:blocked", result["blockers"])

    def test_readback_freshness_gate_blocks_when_status_is_failed(self) -> None:
        """Gate should block when readback returns status=failed."""
        import scripts.static_owner_continuous_route_runner as route_runner

        def mock_run(*, label: str, command: Sequence[str], cwd: Path,
                     child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
            if label == "00-readback-freshness":
                return {
                    "label": label,
                    "ok": True,
                    "exitCode": 1,
                    "json": {
                        "summaryJson": str(self.tmp_path / "mocked-readback-summary.json"),
                        "status": "failed",
                    },
                    "commandPath": str(self.tmp_path / "cmd.json"),
                    "stdoutPath": str(self.tmp_path / "stdout.txt"),
                    "stderrPath": str(self.tmp_path / "stderr.txt"),
                    "stdoutPreview": "",
                    "stderrPreview": "",
                    "durationSeconds": 0.05,
                }
            return {
                "label": label,
                "ok": True,
                "exitCode": 0,
                "json": {"summaryJson": str(self.tmp_path / f"mocked-{label}-summary.json")},
                "commandPath": str(self.tmp_path / f"{label}.command.json"),
                "stdoutPath": str(self.tmp_path / f"{label}.stdout.txt"),
                "stderrPath": str(self.tmp_path / f"{label}.stderr.txt"),
                "stdoutPreview": "",
                "stderrPreview": "",
                "durationSeconds": 0.05,
            }

        args = _make_args(
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run):
            result = route_runner.run(args)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["verdict"], "static-resolver-readback-freshness-failed")
        self.assertIn("static-resolver-readback-freshness-gate:failed", result["blockers"])

    def test_readback_freshness_gate_passes_when_status_is_passed(self) -> None:
        """Gate should allow route loop when readback returns status=passed."""
        import scripts.static_owner_continuous_route_runner as route_runner

        # We need the full mock setup to test past the gate.
        # Mock run_child to return readback-passed, then initial state + plan showing arrival.
        def mock_run_passed(*, label: str, command: Sequence[str], cwd: Path,
                            child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
            envelope: dict[str, Any] = {
                "label": label,
                "ok": True,
                "exitCode": 0,
                "json": {"summaryJson": str(self.tmp_path / f"mocked-{label}-summary.json")},
                "commandPath": str(self.tmp_path / f"{label}.command.json"),
                "stdoutPath": str(self.tmp_path / f"{label}.stdout.txt"),
                "stderrPath": str(self.tmp_path / f"{label}.stderr.txt"),
                "stdoutPreview": "",
                "stderrPreview": "",
                "durationSeconds": 0.05,
            }
            if label == "00-readback-freshness":
                envelope["json"] = {
                    "summaryJson": str(self.tmp_path / "mocked-readback-summary.json"),
                    "status": "passed",
                }
            return envelope

        # Register summaries for downstream calls (initial state, initial plan)
        full_summaries: dict[str, dict[str, Any]] = {}
        summary_path_state = str(self.tmp_path / "mocked-00-initial-state-summary.json")
        full_summaries[summary_path_state] = {
            "status": "passed",
            "latestState": {
                "coordinate": {"x": 7285.0, "y": 821.0, "z": 2980.0},
                "yawDegrees": 45.0,
                "turnRateClassification": "stationary",
            },
        }
        summary_path_plan = str(self.tmp_path / "mocked-00-initial-plan-summary.json")
        full_summaries[summary_path_plan] = {
            "status": "passed",
            "plan": {
                "firstAction": "stop",
                "navigationTarget": {
                    "suggestedTurnDirection": "aligned",
                    "signedBearingDeltaDegrees": 0.5,
                    "absoluteBearingDeltaDegrees": 0.5,
                    "planarDistance": 1.5,
                    "withinArrivalRadius": True,
                    "withinAlignmentThreshold": True,
                },
                "executionBlocked": False,
                "executionBlockers": [],
            },
        }

        def get_summary(path: str) -> dict[str, Any]:
            if path in full_summaries:
                return full_summaries[path]
            raise ValueError(f"Unexpected mocked summary path: {path}")

        args = _make_args(
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run_passed):
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verdict"], "already-arrived")
        # Verify the readback command was recorded in childCommands
        child_labels = [
            item["label"]
            for item in result.get("childCommands", [])
            if isinstance(item, dict)
        ]
        self.assertIn("00-readback-freshness", child_labels)


class TerrainNoProgressSubClassificationTests(unittest.TestCase):
    """Test that terrain sub-classification from child forward results is surfaced."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.tmp_path = Path(self.temp_dir.name)
        truth_dir = self.tmp_path / "docs" / "recovery"
        truth_dir.mkdir(parents=True, exist_ok=True)
        (truth_dir / "current-truth.json").write_text(
            json.dumps({"target": {"processName": "rift_x64"}}), encoding="utf-8",
        )

    def _mock_run_child_fn(self) -> Any:
        """Return a side_effect function with terrain-aware forward support."""
        full_summaries: dict[str, dict[str, Any]] = {}

        def add_state(label: str, coord: dict[str, float], yaw: float, turn_class: str) -> None:
            summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
            full_summaries[summary_path] = {
                "status": "passed",
                "latestState": {
                    "coordinate": coord,
                    "yawDegrees": yaw,
                    "turnRateClassification": turn_class,
                },
            }

        def add_plan(label: str, first_action: str, turn_magnitude: str, turn_dir: str | None,
                     signed_delta: float, abs_delta: float, plan_dist: float,
                     within_radius: bool, within_align: bool, exec_blocked: bool,
                     engine_class: str, blockers: list[str] | None = None) -> None:
            summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
            nav_target: dict[str, Any] = {
                "suggestedTurnDirection": turn_dir,
                "signedBearingDeltaDegrees": signed_delta,
                "absoluteBearingDeltaDegrees": abs_delta,
                "planarDistance": plan_dist,
                "withinArrivalRadius": within_radius,
                "withinAlignmentThreshold": within_align,
            }
            full_summaries[summary_path] = {
                "status": "passed",
                "plan": {
                    "firstAction": first_action,
                    "turnMagnitudeClass": turn_magnitude,
                    "navigationTarget": nav_target,
                    "executionBlocked": exec_blocked,
                    "executionBlockers": blockers or [],
                    "engineTurnRateClassification": engine_class,
                },
            }

        def add_turn(label: str, post_yaw: float, abs_delta: float) -> None:
            summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
            full_summaries[summary_path] = {
                "status": "passed",
                "turnSamples": [{"postYawDegrees": post_yaw, "absoluteYawDeltaDegrees": abs_delta}],
            }

        def add_forward(label: str, route_status: str, progress: float,
                        initial_dist: float, final_dist: float,
                        no_progress_sub: str | None = None) -> None:
            summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
            full_summaries[summary_path] = {
                "status": "passed" if route_status in ("progress", "arrived") else "blocked",
                "routeResult": {
                    "routeStatus": route_status,
                    "totalProgressDistance": progress,
                    "initialPlanarDistance": initial_dist,
                    "finalPlanarDistance": final_dist,
                    "noProgressSubClassification": no_progress_sub if route_status == "no-progress" else None,
                },
            }

        def get_summary(path: str) -> dict[str, Any]:
            if path in full_summaries:
                return full_summaries[path]
            raise ValueError(f"Unexpected mocked summary path: {path}")

        def mock_run(*, label: str, command: Sequence[str], cwd: Path,
                     child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
            return {
                "label": label,
                "ok": True,
                "exitCode": 0,
                "json": {"summaryJson": str(self.tmp_path / f"mocked-{label}-summary.json")},
                "commandPath": str(self.tmp_path / f"{label}.command.json"),
                "stdoutPath": str(self.tmp_path / f"{label}.stdout.txt"),
                "stderrPath": str(self.tmp_path / f"{label}.stderr.txt"),
                "stdoutPreview": "",
                "stderrPreview": "",
                "durationSeconds": 0.05,
            }

        return add_state, add_plan, add_turn, add_forward, get_summary, mock_run

    def test_forward_result_includes_no_progress_sub_classification(self) -> None:
        """When forward returns no-progress with sub-classification, it appears in iteration record."""
        import scripts.static_owner_continuous_route_runner as route_runner

        add_state, add_plan, add_turn, add_forward, get_summary, mock_run = self._mock_run_child_fn()

        add_state("00-initial-state", {"x": 7261.83, "y": 821.45, "z": 2998.98}, 80.82, "stationary")
        add_plan("00-initial-plan", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_plan("plan-001", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_turn("turn-001-left", -36.35, 42.35)
        add_plan("replan-001", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-001", "no-progress", 0.0, 4.5, 4.5,
                    no_progress_sub="blocked-stationary-no-movement")
        # Need plan-002 for iteration 2
        add_plan("plan-002", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-002", "no-progress", 0.0, 4.5, 4.5,
                    no_progress_sub="blocked-stationary-no-movement")
        # Also need plan-003 for iteration 3
        add_plan("plan-003", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-003", "no-progress", 0.0, 4.5, 4.5,
                    no_progress_sub="blocked-stationary-no-movement")

        args = _make_args(
            max_iterations=5,
            skip_readback_freshness_gate=True,
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertEqual(result["status"], "blocked")
        # Verify the sub-classification appears in the iteration record
        self.assertEqual(len(result["iterations"]), 3)
        for it in result["iterations"]:
            forward = it.get("forwardResult", {})
            self.assertEqual(forward.get("noProgressSubClassification"), "blocked-stationary-no-movement")

    def test_blocked_stationary_triggers_terrain_specific_blocker(self) -> None:
        """3 consecutive blocked-stationary forwards → terrain-specific blocker."""
        import scripts.static_owner_continuous_route_runner as route_runner

        add_state, add_plan, add_turn, add_forward, get_summary, mock_run = self._mock_run_child_fn()

        add_state("00-initial-state", {"x": 7261.83, "y": 821.45, "z": 2998.98}, 80.82, "stationary")
        add_plan("00-initial-plan", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_plan("plan-001", "turn-left", "large", "left",
                 -40.58, 40.58, 37.49, False, False, False, "left")
        add_turn("turn-001-left", -36.35, 42.35)
        add_plan("replan-001", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_plan("plan-002", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-001", "no-progress", 0.0, 4.5, 4.5,
                    no_progress_sub="blocked-stationary-no-movement")
        add_plan("plan-003", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-002", "no-progress", 0.0, 4.5, 4.5,
                    no_progress_sub="blocked-stationary-no-movement")
        add_forward("forward-003", "no-progress", 0.0, 4.5, 4.5,
                    no_progress_sub="blocked-stationary-no-movement")

        args = _make_args(
            max_iterations=5,
            skip_readback_freshness_gate=True,
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("forward-no-progress-3-consecutive-blocked-stationary-terrain", result["blockers"])
        self.assertNotIn("forward-no-progress-3-consecutive-stuck", result["blockers"])
        self.assertEqual(result["terrain"]["primarySubClassification"], "blocked-stationary-no-movement")
        self.assertEqual(result["terrain"]["terrainSubClassifications"], {"blocked-stationary-no-movement": 3})
        self.assertEqual(result["recoveryPlan"]["status"], "recommended")
        self.assertTrue(result["recoveryPlan"]["advisoryOnly"])
        self.assertFalse(result["recoveryPlan"]["movementPermission"])
        self.assertEqual(
            result["recoveryPlan"]["recommendedAction"],
            "plan-lateral-strafe-recovery-before-forward-rerun",
        )

    def test_drifted_back_triggers_recovery_plan(self) -> None:
        """3 consecutive drift-back no-progress steps → drift-specific blocker and recovery plan."""
        import scripts.static_owner_continuous_route_runner as route_runner

        add_state, add_plan, add_turn, add_forward, get_summary, mock_run = self._mock_run_child_fn()

        add_state("00-initial-state", {"x": 7261.83, "y": 821.45, "z": 2998.98}, 80.82, "stationary")
        add_plan("00-initial-plan", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_plan("plan-001", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-001", "no-progress", 0.0, 4.5, 4.5,
                    no_progress_sub="drifted-back-after-initial-progress")
        add_plan("plan-002", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-002", "no-progress", 0.0, 4.5, 4.5,
                    no_progress_sub="drifted-back-after-initial-progress")
        add_plan("plan-003", "forward", "aligned", "aligned",
                 1.77, 1.77, 4.5, False, True, False, "stationary")
        add_forward("forward-003", "no-progress", 0.0, 4.5, 4.5,
                    no_progress_sub="drifted-back-after-initial-progress")

        args = _make_args(
            max_iterations=5,
            skip_readback_freshness_gate=True,
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(workflow_common_module, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("forward-no-progress-3-consecutive-drifted-back-terrain", result["blockers"])
        self.assertEqual(result["terrain"]["primarySubClassification"], "drifted-back-after-initial-progress")
        self.assertEqual(result["terrain"]["terrainSubClassifications"], {"drifted-back-after-initial-progress": 3})
        self.assertEqual(
            result["recoveryPlan"]["recommendedAction"],
            "plan-opposite-strafe-recovery-before-forward-rerun",
        )
        self.assertIn("try-opposite-lateral-strafe-if-still-stationary", result["recoveryPlan"]["candidateSequence"])

    def test_markdown_shows_no_progress_sub_classification(self) -> None:
        """Markdown output includes sub-classification when present in forward result."""
        summary = {
            "generatedAtUtc": "2026-05-29T12:00:00Z",
            "status": "blocked",
            "verdict": "route-loop-blocked",
            "total": {
                "iterationCount": 2,
                "totalDurationSeconds": 15.0,
                "initialPlanarDistance": 37.5,
                "finalPlanarDistance": 37.5,
                "totalProgressDistance": 0.0,
                "turnsExecuted": 1,
                "forwardSteps": 0,
            },
            "iterations": [
                {
                    "iteration": 1,
                    "planarDistance": 37.5,
                    "plan": {"firstAction": "turn-left"},
                    "turnDirection": "left",
                    "computedTurnHoldMs": 226,
                    "turnResult": {"status": "passed"},
                    "forwardResult": {"status": "not-needed"},
                },
                {
                    "iteration": 2,
                    "planarDistance": 37.5,
                    "plan": {"firstAction": "forward"},
                    "turnResult": {"status": "not-needed"},
                    "forwardResult": {
                        "status": "blocked",
                        "routeStatus": "no-progress",
                        "noProgressSubClassification": "blocked-stationary-no-movement",
                    },
                },
            ],
            "terrain": {
                "noProgressStepCount": 1,
                "terrainSubClassifications": {"blocked-stationary-no-movement": 1},
                "primarySubClassification": "blocked-stationary-no-movement",
                "terrainBlockerPresent": True,
            },
            "recoveryPlan": {
                "status": "recommended",
                "advisoryOnly": True,
                "movementPermission": False,
                "recommendedAction": "plan-lateral-strafe-recovery-before-forward-rerun",
                "why": "Terrain collision",
                "candidateSequence": ["fresh-static-owner-nav-state-readback"],
            },
            "blockers": ["forward-no-progress-3-consecutive-blocked-stationary-terrain"],
            "warnings": [],
            "errors": [],
            "safety": {
                "movementSent": True,
                "inputSent": True,
                "navigationControl": False,
                "facingPromotion": False,
            },
        }
        md = build_markdown(summary)
        self.assertIn("No-progress reason: `blocked-stationary-no-movement`", md)
        self.assertIn("## Terrain / drift classification", md)
        self.assertIn("Recommended action: `plan-lateral-strafe-recovery-before-forward-rerun`", md)


class WaypointSequenceIntegrationTests(unittest.TestCase):
    """Test run_sequence() with mocked run() calls."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

        # Create a waypoints file
        self.waypoints_file = self.root / "waypoints.json"
        self.waypoints_file.write_text(json.dumps({
            "waypoints": [
                {"id": "wp1", "label": "First", "x": 100.0, "y": 50.0, "z": 200.0, "arrivalRadius": 2.0},
                {"id": "wp2", "label": "Second", "x": 300.0, "y": 60.0, "z": 400.0},
            ],
        }), encoding="utf-8")

    def test_two_waypoint_sequence_both_arrived(self) -> None:
        """Both waypoints reached — status is passed."""
        import scripts.static_owner_continuous_route_runner as route_runner

        # Mock run() to return passed for both legs
        def mock_run_pass(args: Any) -> dict[str, Any]:
            return {
                "status": "passed",
                "verdict": "route-loop-arrived",
                "total": {
                    "iterationCount": 2,
                    "turnsExecuted": 1,
                    "forwardSteps": 2,
                    "totalProgressDistance": 35.0,
                },
                "safety": {
                    "movementSent": True,
                    "inputSent": True,
                    "navigationControl": True,
                },
                "blockers": [],
                "warnings": [],
                "errors": [],
            }

        args = _make_args(
            waypoint_sequence_json=str(self.waypoints_file),
            waypoint_sequence_ids="wp1,wp2",
            repo_root=str(self.root),
            output_root=str(self.root / "out"),
        )

        with mock.patch.object(route_runner, "run", side_effect=mock_run_pass):
            result = route_runner.run_sequence(args)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verdict"], "sequence-all-waypoints-reached")
        self.assertEqual(result["total"]["totalLegs"], 2)
        self.assertEqual(result["total"]["legsArrived"], 2)
        self.assertEqual(result["total"]["legsFailed"], 0)
        self.assertEqual(result["total"]["totalTurnsExecuted"], 2)  # 1 per leg
        self.assertEqual(result["total"]["totalForwardSteps"], 4)  # 2 per leg
        self.assertEqual(result["total"]["totalProgressDistance"], 70.0)  # 35 per leg
        self.assertEqual(len(result["legs"]), 2)
        self.assertEqual(len(result["waypointSequence"]), 2)

    def test_first_leg_fails_sequence_stops(self) -> None:
        """If first waypoint fails, sequence stops and does not attempt second."""
        import scripts.static_owner_continuous_route_runner as route_runner

        call_count: list[int] = [0]

        def mock_run_fail_first(args: Any) -> dict[str, Any]:
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "status": "blocked",
                    "verdict": "route-loop-blocked",
                    "total": {"iterationCount": 1, "turnsExecuted": 1, "forwardSteps": 0, "totalProgressDistance": 0.0},
                    "safety": {"movementSent": True, "inputSent": True, "navigationControl": False},
                    "blockers": ["forward-no-progress-3-consecutive-stuck"],
                    "warnings": [],
                    "errors": [],
                }
            return {
                "status": "passed",
                "verdict": "route-loop-arrived",
                "total": {"iterationCount": 2, "turnsExecuted": 1, "forwardSteps": 2, "totalProgressDistance": 30.0},
                "safety": {"movementSent": True, "inputSent": True, "navigationControl": True},
                "blockers": [],
                "warnings": [],
                "errors": [],
            }

        args = _make_args(
            waypoint_sequence_json=str(self.waypoints_file),
            waypoint_sequence_ids="wp1,wp2",
            repo_root=str(self.root),
            output_root=str(self.root / "out"),
        )

        with mock.patch.object(route_runner, "run", side_effect=mock_run_fail_first):
            result = route_runner.run_sequence(args)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["verdict"], "sequence-blocked")
        self.assertEqual(result["total"]["legsArrived"], 0)
        self.assertEqual(result["total"]["legsFailed"], 1)
        self.assertIn("leg-1-forward-no-progress-3-consecutive-stuck", result["blockers"])
        # run() should only have been called once (second leg never attempted)
        self.assertEqual(call_count[0], 1)

    def test_single_waypoint_sequence(self) -> None:
        """Single waypoint should work as a degenerate case."""
        import scripts.static_owner_continuous_route_runner as route_runner

        def mock_run_single(args: Any) -> dict[str, Any]:
            return {
                "status": "passed",
                "verdict": "route-loop-arrived",
                "total": {"iterationCount": 1, "turnsExecuted": 0, "forwardSteps": 1, "totalProgressDistance": 5.0},
                "safety": {"movementSent": True, "inputSent": True, "navigationControl": True},
                "blockers": [],
                "warnings": [],
                "errors": [],
            }

        single_file = self.root / "single.json"
        single_file.write_text(json.dumps({
            "waypoints": [{"id": "only", "label": "Only WP", "x": 10.0, "y": 0.0, "z": 20.0}],
        }), encoding="utf-8")

        args = _make_args(
            waypoint_sequence_json=str(single_file),
            waypoint_sequence_ids=None,
            repo_root=str(self.root),
            output_root=str(self.root / "out"),
        )

        with mock.patch.object(route_runner, "run", side_effect=mock_run_single):
            result = route_runner.run_sequence(args)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verdict"], "sequence-all-waypoints-reached")
        self.assertEqual(result["total"]["totalLegs"], 1)
        self.assertEqual(result["total"]["legsArrived"], 1)
        self.assertEqual(len(result["legs"]), 1)

    def test_load_error_propagates_to_summary(self) -> None:
        """If waypoint file is malformed, sequence returns failed."""
        import scripts.static_owner_continuous_route_runner as route_runner

        args = _make_args(
            waypoint_sequence_json=str(self.root / "nonexistent.json"),
            repo_root=str(self.root),
            output_root=str(self.root / "out"),
        )

        result = route_runner.run_sequence(args)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["verdict"], "sequence-error")
        self.assertTrue(any("FileNotFoundError" in (e or "") for e in result.get("errors", [])))
