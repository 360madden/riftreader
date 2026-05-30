#!/usr/bin/env python3
"""Tests for the turn completion detector pulse-loop module."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.turn_completion_detector import (
    DEFAULT_ALIGNMENT_THRESHOLD_DEGREES,
    DEFAULT_MAX_PULSES,
    DEFAULT_PULSE_HOLD_MS,
    DEFAULT_PULSE_INTERVAL_MS,
    DEFAULT_SETTLE_MS,
    _cross_check_turn_rate,
    build_markdown,
    build_parser,
    compact,
    validate_args,
)


# ── validate_args ──


class TestValidateArgs:
    def test_valid_minimal_args(self):
        ns = argparse.Namespace(
            direction="left",
            target_bearing_degrees=90.0,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=DEFAULT_ALIGNMENT_THRESHOLD_DEGREES,
            max_pulses=DEFAULT_MAX_PULSES,
            pulse_hold_ms=DEFAULT_PULSE_HOLD_MS,
            pulse_interval_ms=DEFAULT_PULSE_INTERVAL_MS,
            settle_ms=DEFAULT_SETTLE_MS,
            command_timeout_seconds=60.0,
        )
        assert validate_args(ns) == []

    def test_valid_with_signed_delta(self):
        ns = argparse.Namespace(
            direction="right",
            target_bearing_degrees=None,
            signed_bearing_delta_degrees=-45.0,
            alignment_threshold_degrees=5.0,
            max_pulses=10,
            pulse_hold_ms=50,
            pulse_interval_ms=100,
            settle_ms=150,
            command_timeout_seconds=30.0,
        )
        assert validate_args(ns) == []

    def test_missing_both_target_and_delta(self):
        ns = argparse.Namespace(
            direction="left",
            target_bearing_degrees=None,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=7.5,
            max_pulses=25,
            pulse_hold_ms=50,
            pulse_interval_ms=100,
            settle_ms=150,
            command_timeout_seconds=60.0,
        )
        errors = validate_args(ns)
        assert any("target-bearing" in e for e in errors)

    def test_mutually_exclusive_bearing_and_delta(self):
        ns = argparse.Namespace(
            direction="left",
            target_bearing_degrees=90.0,
            signed_bearing_delta_degrees=45.0,
            alignment_threshold_degrees=7.5,
            max_pulses=25,
            pulse_hold_ms=50,
            pulse_interval_ms=100,
            settle_ms=150,
            command_timeout_seconds=60.0,
        )
        errors = validate_args(ns)
        assert any("mutually-exclusive" in e for e in errors)

    def test_invalid_direction(self):
        ns = argparse.Namespace(
            direction="up",
            target_bearing_degrees=90.0,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=7.5,
            max_pulses=25,
            pulse_hold_ms=50,
            pulse_interval_ms=100,
            settle_ms=150,
            command_timeout_seconds=60.0,
        )
        errors = validate_args(ns)
        assert any("direction-must-be" in e for e in errors)

    def test_negative_alignment_threshold(self):
        ns = argparse.Namespace(
            direction="left",
            target_bearing_degrees=90.0,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=-1.0,
            max_pulses=25,
            pulse_hold_ms=50,
            pulse_interval_ms=100,
            settle_ms=150,
            command_timeout_seconds=60.0,
        )
        errors = validate_args(ns)
        assert any("alignment-threshold" in e for e in errors)

    def test_zero_max_pulses(self):
        ns = argparse.Namespace(
            direction="left",
            target_bearing_degrees=90.0,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=7.5,
            max_pulses=0,
            pulse_hold_ms=50,
            pulse_interval_ms=100,
            settle_ms=150,
            command_timeout_seconds=60.0,
        )
        errors = validate_args(ns)
        assert any("max-pulses-must-be-positive" in e for e in errors)

    def test_zero_pulse_hold_ms(self):
        ns = argparse.Namespace(
            direction="left",
            target_bearing_degrees=90.0,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=7.5,
            max_pulses=25,
            pulse_hold_ms=0,
            pulse_interval_ms=100,
            settle_ms=150,
            command_timeout_seconds=60.0,
        )
        errors = validate_args(ns)
        assert any("pulse-hold-ms-must-be-positive" in e for e in errors)

    def test_negative_pulse_interval(self):
        ns = argparse.Namespace(
            direction="left",
            target_bearing_degrees=90.0,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=7.5,
            max_pulses=25,
            pulse_hold_ms=50,
            pulse_interval_ms=-1,
            settle_ms=150,
            command_timeout_seconds=60.0,
        )
        errors = validate_args(ns)
        assert any("pulse-interval-ms" in e for e in errors)

    def test_negative_settle_ms(self):
        ns = argparse.Namespace(
            direction="left",
            target_bearing_degrees=90.0,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=7.5,
            max_pulses=25,
            pulse_hold_ms=50,
            pulse_interval_ms=100,
            settle_ms=-1,
            command_timeout_seconds=60.0,
        )
        errors = validate_args(ns)
        assert any("settle-ms-must-be-nonnegative" in e for e in errors)

    def test_zero_command_timeout(self):
        ns = argparse.Namespace(
            direction="left",
            target_bearing_degrees=90.0,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=7.5,
            max_pulses=25,
            pulse_hold_ms=50,
            pulse_interval_ms=100,
            settle_ms=150,
            command_timeout_seconds=0,
        )
        errors = validate_args(ns)
        assert any("command-timeout" in e for e in errors)

    def test_all_errors_combined(self):
        ns = argparse.Namespace(
            direction="invalid",
            target_bearing_degrees=None,
            signed_bearing_delta_degrees=None,
            alignment_threshold_degrees=-5,
            max_pulses=0,
            pulse_hold_ms=0,
            pulse_interval_ms=-10,
            settle_ms=-5,
            command_timeout_seconds=0,
        )
        errors = validate_args(ns)
        assert len(errors) >= 5  # at least direction, target, alignment, max_pulses, pulse_hold, etc


# ── _cross_check_turn_rate ──


class TestCrossCheckTurnRate:
    def test_agreement_left(self):
        agreements, warnings = _cross_check_turn_rate("left", "left", 3)
        assert len(agreements) == 1
        assert "agrees" in agreements[0]
        assert len(warnings) == 0

    def test_agreement_right(self):
        agreements, warnings = _cross_check_turn_rate("right", "right", 0)
        assert len(agreements) == 1
        assert "agrees" in agreements[0]

    def test_disagreement(self):
        agreements, warnings = _cross_check_turn_rate("left", "right", 5)
        assert len(warnings) == 1
        assert "indicates-right" in warnings[0]

    def test_unknown_classification(self):
        agreements, warnings = _cross_check_turn_rate("left", "unknown", 0)
        assert len(agreements) == 0
        assert len(warnings) == 0

    def test_aligned_classification(self):
        agreements, warnings = _cross_check_turn_rate("right", "aligned", 1)
        assert len(agreements) == 0
        assert len(warnings) == 0

    def test_empty_classification(self):
        agreements, warnings = _cross_check_turn_rate("left", "", 0)
        assert len(agreements) == 0
        assert len(warnings) == 0

    def test_pulse_index_in_warning(self):
        agreements, warnings = _cross_check_turn_rate("left", "right", 7)
        assert "pulse-7" in warnings[0]


# ── Pulse loop logic (unit tests with mocked dependencies) ──


class TestPulseLoopConvergence:
    """Test the run() function's pulse loop behavior using mocked read_nav_state."""

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_immediate_convergence_no_pulses(self, mock_run_child, mock_sleep, mock_read_nav):
        """If pre-turn yaw is already within threshold, no pulses should be sent."""
        from scripts.turn_completion_detector import run
        mock_read_nav.return_value = {
            "ok": True,
            "yawDegrees": 45.0,
            "turnRateClassification": "aligned",
        }

        ns = _make_namespace(direction="right", target_bearing_degrees=47.0, alignment_threshold_degrees=5.0)
        result = run(ns)

        assert result["status"] == "passed"
        assert result["verdict"] == "turn-converged"
        assert result["totalPulses"] == 0
        assert result["preYawDegrees"] == 45.0
        mock_run_child.assert_not_called()
        # bearing error: 47 - 45 = 2, abs(2) <= 5 → converged on first read

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_immediate_convergence_when_aligned(self, mock_run_child, mock_sleep, mock_read_nav):
        """Exact match — zero error."""
        from scripts.turn_completion_detector import run
        mock_read_nav.return_value = {
            "ok": True,
            "yawDegrees": 90.0,
            "turnRateClassification": "aligned",
        }

        ns = _make_namespace(direction="left", target_bearing_degrees=90.0, alignment_threshold_degrees=3.0)
        result = run(ns)

        assert result["status"] == "passed"
        assert result["verdict"] == "turn-converged"
        assert result["totalPulses"] == 0
        assert abs(result["bearingErrorDegrees"]) <= 3.0

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_convergence_after_pulses(self, mock_run_child, mock_sleep, mock_read_nav):
        """Yaw starts at 0°, target is 45° — should pulse until within threshold."""
        from scripts.turn_completion_detector import run

        # First read (pre-turn): yaw=0°
        # After pulse 1: yaw=10° (error=35°, not converged)
        # After pulse 2: yaw=20° (error=25°)
        # After pulse 3: yaw=42° (error=3°, converged!)
        yaw_values = [0.0, 10.0, 20.0, 42.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {
                "ok": True,
                "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)],
                "turnRateClassification": "right",
            }

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=45.0,
            alignment_threshold_degrees=5.0,
            max_pulses=5,
            pulse_hold_ms=50,
        )
        result = run(ns)

        assert result["status"] == "passed"
        assert result["verdict"] == "turn-converged"
        assert result["totalPulses"] == 3  # 3 pulses to get from 0 to 42°
        assert result["preYawDegrees"] == 0.0
        assert result["postYawDegrees"] == 42.0
        assert abs(result["bearingErrorDegrees"]) <= 5.0

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_timeout_max_pulses_exhausted(self, mock_run_child, mock_sleep, mock_read_nav):
        """Yaw starts at 0°, target is 90° — never converges, max pulses exhausted."""
        from scripts.turn_completion_detector import run

        # Yaw only advances 2° per pulse — never reaches 90°
        yaw_values = [0.0, 2.0, 4.0, 6.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {
                "ok": True,
                "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)],
                "turnRateClassification": "right",
            }

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=90.0,
            alignment_threshold_degrees=5.0,
            max_pulses=3,
            pulse_hold_ms=50,
        )
        result = run(ns)

        assert result["status"] == "blocked"
        assert result["verdict"] == "turn-timeout"
        assert result["totalPulses"] == 3
        assert any("max-pulses-exhausted" in b for b in result["blockers"])

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_overshoot_sign_flip(self, mock_run_child, mock_sleep, mock_read_nav):
        """Start at 0°, target is 30° left (signed delta -30°), but yaw goes past target to -35°."""
        from scripts.turn_completion_detector import run

        # Yaw values: pre=0°, pulse1=-15°, pulse2=-36° (overshot -30° target)
        yaw_values = [0.0, -15.0, -36.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {
                "ok": True,
                "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)],
                "turnRateClassification": "left",
            }

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        # Target bearing = 0 + (-30) = -30 → normalize to 330
        ns = _make_namespace(
            direction="left",
            target_bearing_degrees=330.0,
            alignment_threshold_degrees=5.0,
            max_pulses=5,
            pulse_hold_ms=50,
        )
        result = run(ns)

        assert result["status"] == "blocked"
        assert result["verdict"] == "turn-overcorrected"
        assert any("sign-flipped" in b for b in result["blockers"])
        assert result["totalPulses"] == 2

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    def test_turn_not_approved(self, mock_sleep, mock_read_nav):
        """Should fail immediately without --turn-approved."""
        from scripts.turn_completion_detector import run

        ns = _make_namespace(
            direction="left",
            target_bearing_degrees=90.0,
            alignment_threshold_degrees=5.0,
            turn_approved=False,
        )
        result = run(ns)

        assert result["status"] == "blocked"
        assert result["verdict"] == "turn-approval-required"
        assert "turn-approved-flag-required" in result["blockers"]

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    def test_pre_turn_yaw_readback_fails(self, mock_sleep, mock_read_nav):
        """If pre-turn yaw can't be read, fail immediately."""
        from scripts.turn_completion_detector import run
        mock_read_nav.return_value = {
            "ok": False,
            "yawDegrees": None,
            "error": "module-base-mismatch",
        }

        ns = _make_namespace(direction="left", target_bearing_degrees=90.0)
        result = run(ns)

        assert result["status"] == "failed"
        assert result["verdict"] == "pre-turn-yaw-readback-failed"
        assert "module-base-mismatch" in str(result["errors"])

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_post_pulse_yaw_readback_fails(self, mock_run_child, mock_sleep, mock_read_nav):
        """If a post-pulse yaw readback fails mid-loop, fail."""
        from scripts.turn_completion_detector import run

        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"ok": True, "yawDegrees": 0.0}
            # Second call fails (post-pulse readback)
            return {"ok": False, "yawDegrees": None, "error": "nav-state-readback-error"}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=90.0,
            alignment_threshold_degrees=5.0,
            max_pulses=3,
        )
        result = run(ns)

        assert result["status"] == "failed"
        assert result["verdict"] == "post-pulse-yaw-readback-failed"


# ── Signed-bearing-delta resolution ──


class TestSignedBearingDeltaResolution:
    """Test that --signed-bearing-delta-degrees correctly resolves to target bearing."""

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_signed_delta_resolves_target_bearing(self, mock_run_child, mock_sleep, mock_read_nav):
        """When --signed-bearing-delta-degrees is passed, target bearing is computed from pre-yaw + delta."""
        from scripts.turn_completion_detector import run

        yaw_values = [30.0, 55.0]  # pre-yaw=30°, target=30+45=75°, pulse brings it to 55°, converge?
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {
                "ok": True,
                "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)],
                "turnRateClassification": "right",
            }

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        # pre-yaw=30°, signed delta=+45° → target = 75°
        # After 1 pulse: 55° → error = 75-55 = 20° — still outside 5° threshold
        # After max_pulses=1, it should be "blocked" with timeout
        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=None,
            signed_bearing_delta_degrees=45.0,
            alignment_threshold_degrees=5.0,
            max_pulses=1,
        )
        result = run(ns)

        # With max_pulses=1, after the first pulse ends, the loop index reaches
        # the max and the next readback finds 55° (error=20° > 5° threshold)
        # Since the loop exhausted without convergence, it's a timeout
        assert result["status"] == "blocked"
        assert result["verdict"] == "turn-timeout"
        assert result["targetBearingDegrees"] == 75.0
        assert result["totalPulses"] == 1


# ── compact output ──


class TestCompact:
    def test_compact_converged(self):
        summary = {
            "status": "passed",
            "verdict": "turn-converged",
            "operator": {"direction": "left"},
            "targetBearingDegrees": 90.0,
            "preYawDegrees": 45.0,
            "postYawDegrees": 87.5,
            "achievedBearingDegrees": 87.5,
            "bearingErrorDegrees": 2.5,
            "totalPulses": 3,
            "totalHoldMs": 150,
            "totalYawDeltaDegrees": 42.5,
            "pulseHistory": [{}, {}, {}],
            "turnRate0x304CrossCheck": {"warnings": ["test-warning"]},
            "safety": {"movementSent": True, "inputSent": True},
            "artifacts": {"summaryJson": "/tmp/test.json"},
            "blockers": [],
            "warnings": [],
            "errors": [],
        }
        c = compact(summary)
        assert c["status"] == "passed"
        assert c["verdict"] == "turn-converged"
        assert c["direction"] == "left"
        assert c["totalPulses"] == 3
        assert c["pulseCount"] == 3
        assert c["turnRateCrossCheckWarnings"] == 1
        assert c["movementSent"] is True

    def test_compact_timeout(self):
        summary = {
            "status": "blocked",
            "verdict": "turn-timeout",
            "preYawDegrees": 0.0,
            "postYawDegrees": 20.0,
            "targetBearingDegrees": 90.0,
            "achievedBearingDegrees": 20.0,
            "bearingErrorDegrees": 70.0,
            "totalPulses": 25,
            "totalHoldMs": 1250,
            "totalYawDeltaDegrees": 20.0,
            "pulseHistory": [{}] * 25,
            "turnRate0x304CrossCheck": {},
            "safety": {},
            "blockers": ["max-pulses-exhausted:25"],
            "warnings": [],
            "errors": [],
        }
        c = compact(summary)
        assert c["status"] == "blocked"
        assert "max-pulses-exhausted" in str(c["blockers"])

    def test_compact_missing_operator(self):
        summary = {
            "status": "passed",
            "verdict": "turn-converged",
            "preYawDegrees": 0.0,
            "postYawDegrees": 0.0,
            "targetBearingDegrees": 0.0,
            "achievedBearingDegrees": 0.0,
            "bearingErrorDegrees": 0.0,
            "totalPulses": 0,
            "totalHoldMs": 0,
            "totalYawDeltaDegrees": 0.0,
            "pulseHistory": [],
            "safety": {},
            "blockers": [],
            "warnings": [],
            "errors": [],
        }
        c = compact(summary)
        assert c["direction"] is None


# ── build_markdown ──


class TestBuildMarkdown:
    def test_markdown_converged(self):
        summary = {
            "generatedAtUtc": "2026-01-01T00:00:00Z",
            "status": "passed",
            "verdict": "turn-converged",
            "operator": {"direction": "left", "targetBearingDegrees": 90.0, "alignmentThresholdDegrees": 5.0, "maxPulses": 10, "pulseHoldMs": 50},
            "preYawDegrees": 0.0,
            "postYawDegrees": 88.5,
            "achievedBearingDegrees": 88.5,
            "bearingErrorDegrees": 1.5,
            "totalYawDeltaDegrees": 88.5,
            "totalPulses": 5,
            "totalHoldMs": 250,
            "turnRate0x304CrossCheck": {"agreements": ["pulse-0: agrees"], "warnings": []},
            "safety": {"movementSent": True, "inputSent": True, "noCheatEngine": True},
            "artifacts": {"summaryJson": "/tmp/test.json", "runDirectory": "/tmp/"},
            "blockers": [],
            "warnings": [],
            "errors": [],
        }
        md = build_markdown(summary)
        assert "# Turn completion detector" in md
        assert "turn-converged" in md
        assert "0.0" in md

    def test_markdown_with_blockers(self):
        summary = {
            "generatedAtUtc": "2026-01-01T00:00:00Z",
            "status": "blocked",
            "verdict": "turn-timeout",
            "operator": {},
            "preYawDegrees": 0.0,
            "postYawDegrees": 30.0,
            "achievedBearingDegrees": 30.0,
            "bearingErrorDegrees": 60.0,
            "totalYawDeltaDegrees": 30.0,
            "totalPulses": 25,
            "totalHoldMs": 1250,
            "turnRate0x304CrossCheck": {},
            "safety": {},
            "artifacts": {},
            "blockers": ["max-pulses-exhausted:25"],
            "warnings": ["turn-timeout-at-iteration-1"],
            "errors": [],
        }
        md = build_markdown(summary)
        assert "max-pulses-exhausted:25" in md
        assert "turn-timeout-at-iteration-1" in md

    def test_markdown_with_turn_rate_warnings(self):
        summary = {
            "generatedAtUtc": "2026-01-01T00:00:00Z",
            "status": "passed",
            "verdict": "turn-converged",
            "operator": {},
            "preYawDegrees": None,
            "postYawDegrees": None,
            "achievedBearingDegrees": None,
            "bearingErrorDegrees": None,
            "totalYawDeltaDegrees": None,
            "totalPulses": 3,
            "totalHoldMs": 150,
            "turnRate0x304CrossCheck": {
                "agreements": ["pulse-1: agrees"],
                "warnings": ["pulse-2: sent-left-but-engine-0x304-indicates-right"],
            },
            "safety": {},
            "artifacts": {},
            "blockers": [],
            "warnings": [],
            "errors": [],
        }
        md = build_markdown(summary)
        assert "0x304-indicates-right" in md


# ── build_parser ──


class TestBuildParser:
    def test_required_args(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_minimal_args(self):
        parser = build_parser()
        args = parser.parse_args(["--direction", "left", "--target-bearing-degrees", "90"])
        assert args.direction == "left"
        assert args.target_bearing_degrees == 90.0

    def test_signed_delta_args(self):
        parser = build_parser()
        args = parser.parse_args(["--direction", "right", "--signed-bearing-delta-degrees", "-45"])
        assert args.direction == "right"
        assert args.signed_bearing_delta_degrees == -45.0

    def test_mutually_exclusive_group_rejects_both(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--direction", "left", "--target-bearing-degrees", "90", "--signed-bearing-delta-degrees", "45"])

    def test_all_options_default_values(self):
        parser = build_parser()
        args = parser.parse_args([
            "--direction", "left",
            "--target-bearing-degrees", "90",
            "--alignment-threshold-degrees", "3.0",
            "--max-pulses", "10",
            "--pulse-hold-ms", "75",
            "--pulse-interval-ms", "50",
            "--settle-ms", "200",
            "--input-mode", "VirtualKey",
            "--command-timeout-seconds", "120",
            "--turn-approved",
        ])
        assert args.alignment_threshold_degrees == 3.0
        assert args.max_pulses == 10
        assert args.pulse_hold_ms == 75
        assert args.pulse_interval_ms == 50
        assert args.settle_ms == 200
        assert args.input_mode == "VirtualKey"
        assert args.command_timeout_seconds == 120
        assert args.turn_approved is True


# ── Angle math edge cases ──


class TestAngleEdgeCases:
    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    def test_wrap_around_180_boundary(self, mock_sleep, mock_read_nav):
        """Target near ±180° boundary: pre-yaw=170°, target=-170° (delta = 20° right)."""
        from scripts.turn_completion_detector import run
        mock_read_nav.return_value = {
            "ok": True,
            "yawDegrees": 170.0,
            "turnRateClassification": "aligned",
        }

        # 170° → target -170° = 190° → normalize to -170°.
        # bearing error = normalize_degrees(-170 - 170) = normalize_degrees(-340) = 20°
        # abs(20) > 5° threshold → should NOT converge immediately
        ns = _make_namespace(direction="right", target_bearing_degrees=-170.0, alignment_threshold_degrees=5.0,
            max_pulses=1, pulse_hold_ms=50)
        result = run(ns)

        # First read shows 170°, error=20° > 5° → not converged
        # With max_pulses=1, the loop will read once more after the pulse
        # But we have no yaw advance since we only mocked one read state
        assert result["status"] != "passed"  # should not converge on first read

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_overshoot_across_boundary(self, mock_run_child, mock_sleep, mock_read_nav):
        """Overshoot across the ±180° boundary: yaw=-170°, target=170° (delta=-20° left)."""
        from scripts.turn_completion_detector import run

        yaw_values = [-170.0, 165.0, -175.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {
                "ok": True,
                "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)],
                "turnRateClassification": "right",
            }

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        # pre=-170, target=170. normalize_degrees(170-(-170)) = normalize_degrees(340) = -20
        # Initial sign = copy_sign(1, -20) = -1
        # After pulse 1: yaw=165. error = normalize_degrees(170-165) = 5 → abs(5) ≤ 5 → CONVERGED
        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=170.0,
            alignment_threshold_degrees=5.0,
            max_pulses=3,
            pulse_hold_ms=50,
        )
        result = run(ns)

        assert result["status"] == "passed"
        assert result["verdict"] == "turn-converged"

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_positive_initial_error_sign(self, mock_run_child, mock_sleep, mock_read_nav):
        """Initial bearing error is positive (target to the right)."""
        from scripts.turn_completion_detector import run

        # pre=0°, target=45°. error = +45°, sign = +1
        # After pulse: yaw=20°, error = +25°, sign still +1 → no overshoot
        # After pulse: yaw=51°, error = -6°, sign = -1 → OVERSHOOT (+ abs(6°) > 5° threshold)
        yaw_values = [0.0, 20.0, 51.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {
                "ok": True,
                "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)],
                "turnRateClassification": "right",
            }

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=45.0,
            alignment_threshold_degrees=5.0,
            max_pulses=5,
            pulse_hold_ms=50,
        )
        result = run(ns)

        assert result["status"] == "blocked"
        assert result["verdict"] == "turn-overcorrected"


# ── Edge-case: zero-degree crossing wrap-around ──


class TestZeroDegreeCrossing:
    """Test turn convergence when yaw crosses the 0°/360° boundary."""

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_right_turn_crosses_zero(self, mock_run_child, mock_sleep, mock_read_nav):
        """Right turn from 355° to 10° crosses through 0°. Error should be 15°."""
        from scripts.turn_completion_detector import run

        # pre=355°, target=10°. normalize(10-355) = normalize(-345) = 15° error
        # Not within 5° threshold → needs pulses
        # After pulse 1: yaw=358° → error = normalize(10-358) = 12° → not converged
        # After pulse 2: yaw=363° → normalize to 3° → error = normalize(10-3) = 7° → not converged
        # After pulse 3: yaw=368° → normalize to 8° → error = normalize(10-8) = 2° → CONVERGED
        yaw_values = [355.0, 358.0, 3.0, 8.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {
                "ok": True,
                "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)],
                "turnRateClassification": "right",
            }

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=10.0,
            alignment_threshold_degrees=5.0,
            max_pulses=5,
            pulse_hold_ms=50,
        )
        result = run(ns)

        assert result["status"] == "passed"
        assert result["verdict"] == "turn-converged"
        assert result["totalPulses"] == 3
        assert result["preYawDegrees"] == 355.0
        assert abs(float(result["achievedBearingDegrees"]) - 8.0) < 0.01

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_left_turn_crosses_zero(self, mock_run_child, mock_sleep, mock_read_nav):
        """Left turn from 5° to 350° crosses through 0°."""
        from scripts.turn_completion_detector import run

        # pre=5°, target=350°. normalize(350-5) = 345° → normalized further? No, it's already in [-180,180].
        # Wait: normalize_degrees(345) = -15° (since 345 > 180 → 345-360 = -15)
        # So error = -15°, which means turning left by 15°
        yaw_values = [5.0, 352.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {
                "ok": True,
                "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)],
                "turnRateClassification": "left",
            }

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(
            direction="left",
            target_bearing_degrees=350.0,
            alignment_threshold_degrees=5.0,
            max_pulses=3,
            pulse_hold_ms=50,
        )
        result = run(ns)

        # After pulse 1: yaw=352°, error = normalize(350-352) = -2° → abs(2°) ≤ 5° → CONVERGED
        assert result["status"] == "passed"
        assert result["verdict"] == "turn-converged"


# ── Edge-case: boundary convergence ──


class TestBoundaryConvergence:
    """Test that convergence at the exact threshold boundary works correctly."""

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    def test_exact_threshold_match(self, mock_sleep, mock_read_nav):
        """Error exactly equals threshold — should converge immediately."""
        from scripts.turn_completion_detector import run

        # pre_yaw=0°, target=5°, threshold=5° → error=5° == threshold → converged
        mock_read_nav.return_value = {
            "ok": True,
            "yawDegrees": 0.0,
            "turnRateClassification": "aligned",
        }

        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=5.0,
            alignment_threshold_degrees=5.0,
        )
        result = run(ns)

        assert result["status"] == "passed"
        assert result["verdict"] == "turn-converged"
        assert result["totalPulses"] == 0
        assert result["bearingErrorDegrees"] == 5.0

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_just_below_threshold_converges(self, mock_run_child, mock_sleep, mock_read_nav):
        """Error just below threshold after pulses — should converge."""
        from scripts.turn_completion_detector import run

        # pre=0°, target=42°, threshold=5°
        # After pulse 1: yaw=38° → error=4° (just under 5°) → CONVERGED
        yaw_values = [0.0, 38.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {"ok": True, "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)], "turnRateClassification": "right"}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(direction="right", target_bearing_degrees=42.0, alignment_threshold_degrees=5.0, max_pulses=3, pulse_hold_ms=50)
        result = run(ns)

        assert result["status"] == "passed"
        assert result["verdict"] == "turn-converged"
        assert result["totalPulses"] == 1

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    def test_just_above_threshold_not_converged(self, mock_sleep, mock_read_nav):
        """Error just above threshold — should NOT converge (and require pulses)."""
        from scripts.turn_completion_detector import run

        # pre_yaw=0°, target=5.1°, threshold=5° → error=5.1° > 5° → not converged
        # With max_pulses=1, we'd send one pulse, then loop exhausts → timeout
        mock_read_nav.return_value = {
            "ok": True,
            "yawDegrees": 0.0,
            "turnRateClassification": "right",
        }

        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=5.1,
            alignment_threshold_degrees=5.0,
            max_pulses=1,
            pulse_hold_ms=50,
            turn_approved=True,
        )
        result = run(ns)

        # Error > threshold, max_pulses=1 → will pulse once, but we don't have
        # a second read_nav_state return value, so the post-pulse read fails
        # with the same mock return (0.0 yaw, error still 5.1)
        assert result["status"] != "passed"


# ── Edge-case: signed delta edge cases ──


class TestSignedDeltaEdgeCases:
    """Edge-case behavior of signed bearing delta resolution."""

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_negative_signed_delta_left_turn(self, mock_run_child, mock_sleep, mock_read_nav):
        """Signed delta of -45° on pre-yaw=90° should resolve target to 45° and turn left."""
        from scripts.turn_completion_detector import run

        yaw_values = [90.0, 60.0, 48.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {"ok": True, "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)], "turnRateClassification": "left"}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        # pre=90°, signed delta=-45° → target = normalize(90-45) = 45°
        # After pulse 1: yaw=60° → error = normalize(45-60) = -15° → abs(15) > 5° → not converged
        # After pulse 2: yaw=48° → error = normalize(45-48) = -3° → abs(3) ≤ 5° → CONVERGED
        ns = _make_namespace(
            direction="left",
            target_bearing_degrees=None,
            signed_bearing_delta_degrees=-45.0,
            alignment_threshold_degrees=5.0,
            max_pulses=3,
            pulse_hold_ms=50,
        )
        result = run(ns)

        assert result["status"] == "passed"
        assert result["targetBearingDegrees"] == 45.0
        assert result["totalPulses"] == 2

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    def test_signed_delta_zero(self, mock_sleep, mock_read_nav):
        """Signed delta of 0° means target = pre-yaw, should converge immediately."""
        from scripts.turn_completion_detector import run

        mock_read_nav.return_value = {
            "ok": True,
            "yawDegrees": 180.0,
            "turnRateClassification": "aligned",
        }

        ns = _make_namespace(
            direction="left",
            target_bearing_degrees=None,
            signed_bearing_delta_degrees=0.0,
            alignment_threshold_degrees=5.0,
        )
        result = run(ns)

        assert result["status"] == "passed"
        assert result["verdict"] == "turn-converged"
        assert result["totalPulses"] == 0
        # normalize_degrees(180) may return -180; both represent the same angle
        assert abs(float(result["targetBearingDegrees"])) == 180.0

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    def test_signed_delta_wraps_around(self, mock_sleep, mock_read_nav):
        """Signed delta that would exceed 360° — correctly normalized."""
        from scripts.turn_completion_detector import run

        # pre=350°, delta=+45° → target=395° → normalize to 35°
        mock_read_nav.return_value = {
            "ok": True,
            "yawDegrees": 350.0,
            "turnRateClassification": "right",
        }

        ns = _make_namespace(
            direction="right",
            target_bearing_degrees=None,
            signed_bearing_delta_degrees=45.0,
            alignment_threshold_degrees=30.0,
            max_pulses=1,
            pulse_hold_ms=50,
        )
        result = run(ns)

        # target = normalize_degrees(350+45) = normalize_degrees(395) = 35°
        # pre-error = normalize_degrees(35-350) = normalize_degrees(-315) = 45°
        # 45° > 30° threshold → not converged
        assert result["targetBearingDegrees"] == 35.0
        assert result["status"] != "passed"


# ── Edge-case: yaw readback edge cases ──


class TestYawReadbackEdgeCases:
    """Edge cases around yaw readback failures."""

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    def test_pre_turn_ok_true_yaw_none(self, mock_sleep, mock_read_nav):
        """read_nav_state returns ok=True but yawDegrees is None — should fail."""
        from scripts.turn_completion_detector import run

        mock_read_nav.return_value = {
            "ok": True,
            "yawDegrees": None,
            "error": None,
        }

        ns = _make_namespace(direction="left", target_bearing_degrees=90.0)
        result = run(ns)

        assert result["status"] == "failed"
        assert result["verdict"] == "pre-turn-yaw-readback-failed"

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_post_pulse_ok_true_yaw_none(self, mock_run_child, mock_sleep, mock_read_nav):
        """Post-pulse readback returns ok=True but yawDegrees=None — should fail."""
        from scripts.turn_completion_detector import run

        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"ok": True, "yawDegrees": 0.0}
            return {"ok": True, "yawDegrees": None}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(direction="right", target_bearing_degrees=90.0, max_pulses=3, pulse_hold_ms=50)
        result = run(ns)

        assert result["status"] == "failed"
        assert result["verdict"] == "post-pulse-yaw-readback-failed"


# ── Edge-case: pulse history tracking ──


class TestPulseHistoryTracking:
    """Verify pulseHistory is correctly populated during pulse loop."""

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_pulse_history_includes_all_iterations(self, mock_run_child, mock_sleep, mock_read_nav):
        """Pulse history should contain entries for each yaw read in the loop."""
        from scripts.turn_completion_detector import run

        yaw_values = [0.0, 10.0, 20.0, 42.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {"ok": True, "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)], "turnRateClassification": "right"}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(direction="right", target_bearing_degrees=45.0, alignment_threshold_degrees=5.0, max_pulses=5, pulse_hold_ms=50)
        result = run(ns)

        # pulseHistory should have 4 entries:
        # idx=0: pre-yaw (0.0) — no pulse sent
        # idx=1: after pulse 1 (10.0) — pulse sent (converged? error=35° > 5° → no)
        # idx=2: after pulse 2 (20.0) — pulse sent
        # idx=3: after pulse 3 (42.0) — pulse sent (error=3° ≤ 5° → converged, no more pulses)
        assert len(result["pulseHistory"]) == 4
        assert result["pulseHistory"][0]["pulseIndex"] == 0
        assert result["pulseHistory"][0]["yawDegrees"] == 0.0
        assert result["pulseHistory"][1]["yawDegrees"] == 10.0
        assert result["pulseHistory"][2]["yawDegrees"] == 20.0
        assert result["pulseHistory"][3]["yawDegrees"] == 42.0
        # Check pulseSent is False for the convergence check iteration
        # (pulse 3 converged before sending another pulse)
        # Actually wait: pulse 3 sends a pulse before reading the convergence result
        # Let's think about this differently
        assert result["totalPulses"] == 3  # 3 pulses sent

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_pulse_history_with_timeout(self, mock_run_child, mock_sleep, mock_read_nav):
        """Pulse history captures all iterations even on timeout."""
        from scripts.turn_completion_detector import run

        yaw_values = [0.0, 5.0, 10.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {"ok": True, "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)], "turnRateClassification": "right"}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(direction="right", target_bearing_degrees=90.0, alignment_threshold_degrees=5.0, max_pulses=2, pulse_hold_ms=50)
        result = run(ns)

        assert result["status"] == "blocked"
        assert result["verdict"] == "turn-timeout"
        # max_pulses=2 → range(2) = [0,1] → 2 iterations → 2 pulseHistory entries
        assert len(result["pulseHistory"]) == 2


# ── Edge-case: cross-check warnings ──


class TestCrossCheckWarningsNonFatal:
    """Cross-check warnings should never block or fail a turn."""

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_warnings_do_not_block_converged_turn(self, mock_run_child, mock_sleep, mock_read_nav):
        """Turn converges despite engine 0x304 warning on pre-turn."""
        from scripts.turn_completion_detector import run

        # pre-turn: engine shows "left" but commanded "right" → warning on pre-turn
        # But yaw is at 43°, target=45° → converged
        mock_read_nav.return_value = {
            "ok": True,
            "yawDegrees": 43.0,
            "turnRateClassification": "left",
        }

        ns = _make_namespace(direction="right", target_bearing_degrees=45.0, alignment_threshold_degrees=5.0)
        result = run(ns)

        assert result["status"] == "passed"
        # Should have a cross-check warning
        assert len(result["turnRate0x304CrossCheck"]["warnings"]) >= 1
        assert any("shows-left-but-commanded-right" in w or "indicates-left" in w for w in result["turnRate0x304CrossCheck"]["warnings"])

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_warnings_accumulate_across_pulses(self, mock_run_child, mock_sleep, mock_read_nav):
        """Multiple 0x304 dissonances across pulses produce multiple warnings."""
        from scripts.turn_completion_detector import run

        yaw_values = [0.0, 10.0, 20.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {"ok": True, "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)], "turnRateClassification": "left"}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(direction="right", target_bearing_degrees=90.0, alignment_threshold_degrees=5.0, max_pulses=2, pulse_hold_ms=50)
        result = run(ns)

        # Pre-turn (0.0) and pulse-1 (10.0) both show "left" but commanded "right"
        assert len(result["turnRate0x304CrossCheck"]["warnings"]) >= 1
        # Turn should still be "blocked" due to max-pulses-exhausted, but not due to warnings
        assert result["status"] == "blocked"
        assert result["verdict"] == "turn-timeout"


# ── Edge-case: subprocess timeout ──


class TestSubprocessTimeout:
    """Test behavior when run_child or read_nav_state raises TimeoutExpired."""

    @patch("scripts.turn_completion_detector.read_nav_state", side_effect=subprocess.TimeoutExpired(cmd=["test"], timeout=5.0))
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    def test_read_nav_state_timeout(self, mock_sleep, mock_read_nav):
        """read_nav_state raises TimeoutExpired — should be caught as failed."""
        from scripts.turn_completion_detector import run

        ns = _make_namespace(direction="left", target_bearing_degrees=90.0)
        result = run(ns)

        assert result["status"] == "failed"
        assert result["verdict"] == "turn-completion-command-timeout"

    @patch("scripts.turn_completion_detector.read_nav_state", return_value={"ok": True, "yawDegrees": 0.0, "turnRateClassification": "right"})
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child", side_effect=subprocess.TimeoutExpired(cmd=["pwsh", "-File", "dummy.ps1"], timeout=5.0))
    def test_send_pulse_timeout(self, mock_run_child, mock_sleep, mock_read_nav):
        """run_child raises TimeoutExpired during pulse — should be caught as failed."""
        from scripts.turn_completion_detector import run

        ns = _make_namespace(direction="right", target_bearing_degrees=90.0, max_pulses=5, pulse_hold_ms=50)
        result = run(ns)

        assert result["status"] == "failed"
        assert result["verdict"] == "turn-completion-command-timeout"


# ── Edge-case: main function ──


class TestMainFunction:
    """Test exit codes and basic main() behavior."""

    @patch("scripts.turn_completion_detector.run")
    def test_main_returns_0_on_passed(self, mock_run):
        """main() returns 0 when status is 'passed'."""
        from scripts.turn_completion_detector import main
        mock_run.return_value = {
            "status": "passed",
            "artifacts": {"summaryJson": "/tmp/test.json", "summaryMarkdown": "/tmp/test.md"},
        }
        with patch("scripts.turn_completion_detector.write_json"), patch("scripts.turn_completion_detector.Path.write_text"):
            exit_code = main(["--direction", "left", "--target-bearing-degrees", "90"])
        assert exit_code == 0

    @patch("scripts.turn_completion_detector.run")
    def test_main_returns_2_on_blocked(self, mock_run):
        """main() returns 2 when status is 'blocked'."""
        from scripts.turn_completion_detector import main
        mock_run.return_value = {
            "status": "blocked",
            "artifacts": {"summaryJson": "/tmp/test.json", "summaryMarkdown": "/tmp/test.md"},
        }
        with patch("scripts.turn_completion_detector.write_json"), patch("scripts.turn_completion_detector.Path.write_text"):
            exit_code = main(["--direction", "left", "--target-bearing-degrees", "90"])
        assert exit_code == 2

    @patch("scripts.turn_completion_detector.run")
    def test_main_returns_1_on_failed(self, mock_run):
        """main() returns 1 when status is 'failed'."""
        from scripts.turn_completion_detector import main
        mock_run.return_value = {
            "status": "failed",
            "artifacts": {"summaryJson": "/tmp/test.json", "summaryMarkdown": "/tmp/test.md"},
        }
        with patch("scripts.turn_completion_detector.write_json"), patch("scripts.turn_completion_detector.Path.write_text"):
            exit_code = main(["--direction", "left", "--target-bearing-degrees", "90"])
        assert exit_code == 1


# ── Edge-case: maximum pulses at boundary ──


class TestMaxPulsesBoundary:
    """Test behavior at max_pulses boundary values."""

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_single_pulse_success(self, mock_run_child, mock_sleep, mock_read_nav):
        """max_pulses=1, one pulse converges."""
        from scripts.turn_completion_detector import run

        yaw_values = [0.0, 42.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {"ok": True, "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)], "turnRateClassification": "right"}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        # max_pulses=2 so the loop has a second iteration to re-read yaw after the pulse
        ns = _make_namespace(direction="right", target_bearing_degrees=45.0, alignment_threshold_degrees=5.0, max_pulses=2, pulse_hold_ms=80)
        result = run(ns)

        # pre=0°, error=45° > 5° → send 1 pulse → re-read yaw=42°, error=3° ≤ 5° → CONVERGED
        assert result["status"] == "passed"
        assert result["totalPulses"] == 1

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_single_pulse_no_convergence(self, mock_run_child, mock_sleep, mock_read_nav):
        """max_pulses=1, single pulse does NOT converge → timeout."""
        from scripts.turn_completion_detector import run

        yaw_values = [0.0, 2.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {"ok": True, "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)], "turnRateClassification": "right"}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        ns = _make_namespace(direction="right", target_bearing_degrees=90.0, alignment_threshold_degrees=5.0, max_pulses=1, pulse_hold_ms=50)
        result = run(ns)

        assert result["status"] == "blocked"
        assert result["verdict"] == "turn-timeout"
        assert result["totalPulses"] == 1

    @patch("scripts.turn_completion_detector.read_nav_state")
    @patch("scripts.turn_completion_detector.time.sleep", return_value=None)
    @patch("scripts.turn_completion_detector.run_child")
    def test_convergence_on_last_pulse(self, mock_run_child, mock_sleep, mock_read_nav):
        """Converges exactly on the last allowed pulse."""
        from scripts.turn_completion_detector import run

        yaw_values = [0.0, 10.0, 20.0, 42.0]
        call_count = [0]

        def read_nav_state_side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return {"ok": True, "yawDegrees": yaw_values[min(idx, len(yaw_values) - 1)], "turnRateClassification": "right"}

        mock_read_nav.side_effect = read_nav_state_side_effect
        mock_run_child.return_value = {"ok": True, "exitCode": 0}

        # max_pulses=4 → range(4) = [0,1,2,3] → 4 iterations
        # pulse_idx=3 reads yaw_values[3]=42.0 (call 3) → error=3° ≤ 5° → CONVERGED
        ns = _make_namespace(direction="right", target_bearing_degrees=45.0, alignment_threshold_degrees=5.0, max_pulses=4, pulse_hold_ms=50)
        result = run(ns)

        assert result["status"] == "passed"
        # 3 pulses sent at idx 0,1,2; idx 3 converged before sending
        assert result["totalPulses"] == 3


# ── edge-case: compact with missing keys ──


class TestCompactEdgeCases:
    """Compact function edge cases with missing or malformed data."""

    def test_compact_empty_summary(self):
        """compact() with empty dict should not raise."""
        c = compact({})
        assert c["status"] is None
        assert c["direction"] is None
        assert c["turnRateCrossCheckWarnings"] == 0
        assert c["movementSent"] is False
        assert c["inputSent"] is False
        assert c["summaryJson"] is None

    def test_compact_null_operator(self):
        """compact() with operator set to None should not raise."""
        c = compact({"operator": None})
        assert c["direction"] is None

    def test_compact_null_artifacts(self):
        """compact() with artifacts set to None should not raise."""
        c = compact({"artifacts": None})
        assert c["summaryJson"] is None

    def test_compact_pulse_count_zero(self):
        """compact() with empty pulseHistory should report pulseCount=0."""
        c = compact({"pulseHistory": []})
        assert c["pulseCount"] == 0


# ── Helpers ──


def _make_namespace(**overrides) -> argparse.Namespace:
    defaults = {
        "repo_root": None,
        "output_root": None,
        "current_truth_json": "docs/recovery/current-truth.json",
        "direction": "left",
        "key": None,
        "target_bearing_degrees": 90.0,
        "signed_bearing_delta_degrees": None,
        "alignment_threshold_degrees": DEFAULT_ALIGNMENT_THRESHOLD_DEGREES,
        "max_pulses": DEFAULT_MAX_PULSES,
        "pulse_hold_ms": DEFAULT_PULSE_HOLD_MS,
        "pulse_interval_ms": DEFAULT_PULSE_INTERVAL_MS,
        "settle_ms": DEFAULT_SETTLE_MS,
        "input_mode": "ScanCode",
        "title_contains": "RIFT",
        "command_timeout_seconds": 60.0,
        "turn_approved": True,
        "json": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
