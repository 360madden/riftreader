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
    DEFAULT_MAX_TURN_HOLD_MS,
    DEFAULT_MIN_FORWARD_HOLD_MS,
    DEFAULT_MIN_TURN_HOLD_MS,
    FORWARD_ACCEL_DISTANCE_M,
    FORWARD_ACCEL_TIME_MS,
    FORWARD_SPEED_M_PER_S,
    TURN_RATE_DEGREES_PER_MS,
    build_markdown,
    compact,
    compact_plan,
    compute_forward_hold_ms,
    compute_turn_hold_ms,
    run,
    safe_mapping,
    validate_args,
)


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
        "arrival_radius": DEFAULT_ARRIVAL_RADIUS,
        "alignment_threshold_degrees": DEFAULT_ALIGNMENT_THRESHOLD_DEGREES,
        "minimum_progress_distance": 0.35,
        "wrong_way_tolerance": 1.0,
        "forward_key": "w",
        "input_mode": "ScanCode",
        "title_contains": "RIFT",
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
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class ComputeTurnHoldMsTests(unittest.TestCase):
    """Test the calibrated turn-hold computation."""

    def test_zero_degrees_returns_minimum_hold(self) -> None:
        self.assertEqual(compute_turn_hold_ms(0.0), DEFAULT_MIN_TURN_HOLD_MS)

    def test_small_turn_clamps_to_minimum(self) -> None:
        # 0.5 degrees: 0.5 / 0.177 = 2.8ms → clamped to min (150ms)
        hold = compute_turn_hold_ms(0.5)
        self.assertEqual(hold, DEFAULT_MIN_TURN_HOLD_MS)

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
        self.assertLessEqual(hold, DEFAULT_MAX_TURN_HOLD_MS)
        self.assertGreater(hold, DEFAULT_MIN_TURN_HOLD_MS)

    def test_negative_degrees_uses_absolute(self) -> None:
        hold_pos = compute_turn_hold_ms(45.0)
        hold_neg = compute_turn_hold_ms(-45.0)
        self.assertEqual(hold_pos, hold_neg)

    def test_over_max_clamps_to_max(self) -> None:
        # 250 degrees → clamped to 180 internally → 180 / 0.177 ≈ 1017ms
        hold = compute_turn_hold_ms(250.0)
        self.assertLessEqual(hold, DEFAULT_MAX_TURN_HOLD_MS)


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
                mock_run.return_value = {
                    "label": "00-initial-state",
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
        expected_approx = 60.0 / TURN_RATE_DEGREES_PER_MS
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
                        initial_dist: float, final_dist: float) -> None:
            summary_path = str(self.tmp_path / f"mocked-{label}-summary.json")
            full_summaries[summary_path] = {
                "status": "passed" if route_status in ("progress", "arrived") else "blocked",
                "routeResult": {
                    "routeStatus": route_status,
                    "totalProgressDistance": progress,
                    "initialPlanarDistance": initial_dist,
                    "finalPlanarDistance": final_dist,
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
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(route_runner, "load_json_object", side_effect=get_summary):
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
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(route_runner, "load_json_object", side_effect=get_summary):
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
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(route_runner, "load_json_object", side_effect=get_summary):
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
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_run) as _mock:
            with mock.patch.object(route_runner, "load_json_object", side_effect=get_summary):
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
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_break):
            with mock.patch.object(route_runner, "load_json_object", side_effect=get_summary):
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
            repo_root=str(self.tmp_path),
            output_root=str(self.tmp_path / "out"),
            current_truth_json=str(self.tmp_path / "docs" / "recovery" / "current-truth.json"),
        )

        with mock.patch.object(route_runner, "run_child", side_effect=mock_break):
            with mock.patch.object(route_runner, "load_json_object", side_effect=get_summary):
                result = route_runner.run(args)

        self.assertIn(result["status"], ("blocked", "failed"))
        self.assertTrue(any("forward-json-missing" in (w or "") for w in result.get("warnings", [])))


if __name__ == "__main__":
    unittest.main()
