"""Tests for nav_state_freshness_watchdog.py."""
from __future__ import annotations

import json
import unittest
from typing import Any

from scripts.nav_state_freshness_watchdog import (
    classify_correlation,
    compact,
    compute_deltas,
    build_parser,
    safe_mapping,
)


class TestClassifyCorrelation(unittest.TestCase):
    """Tests for the correlation classifier."""

    def test_no_data_when_turn_rate_none(self) -> None:
        """Returns no-data when turn rates are None."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": None,
            "turnRate0x304After": None,
            "turnRate0x304Delta": None,
            "yawDeltaDegrees": None,
        }
        result = classify_correlation(deltas, "stable", "stable")
        self.assertEqual(result["status"], "no-data")
        self.assertEqual(result["reason"], "turn-rate-values-none")
        self.assertFalse(result["correlationEstablished"])

    def test_no_data_when_turn_before_none(self) -> None:
        """Returns no-data when turnRate0x304Before is None."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": None,
            "turnRate0x304After": 0.5,
            "turnRate0x304Delta": None,
        }
        result = classify_correlation(deltas, "stable", "stable")
        self.assertEqual(result["status"], "no-data")

    def test_no_data_when_turn_after_none(self) -> None:
        """Returns no-data when turnRate0x304After is None."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 0.5,
            "turnRate0x304After": None,
            "turnRate0x304Delta": None,
        }
        result = classify_correlation(deltas, "stable", "stable")
        self.assertEqual(result["status"], "no-data")

    def test_stationary_freshness_confirmed(self) -> None:
        """Returns passed when turn rate is stable and facing didn't move."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 0.001,
            "turnRate0x304After": 0.002,
            "turnRate0x304Delta": 0.001,
            "yawDeltaDegrees": 0.0,
            "facingTargetDx": 0.0,
            "facingTargetDz": 0.0,
        }
        result = classify_correlation(deltas, "stable", "stable")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["reason"], "stationary-freshness-confirmed")
        self.assertTrue(result["correlationEstablished"])
        self.assertTrue(result["turnRateStable"])
        self.assertFalse(result["facingTargetMoved"])

    def test_stationary_freshness_with_small_delta(self) -> None:
        """Turn delta < 0.01 is considered stable."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 0.0,
            "turnRate0x304After": 0.009,
            "turnRate0x304Delta": 0.009,
            "yawDeltaDegrees": 0.0,
            "facingTargetDx": 0.0,
            "facingTargetDz": 0.0,
        }
        result = classify_correlation(deltas, "stable", "stable")
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["turnRateStable"])

    def test_active_turn_freshness_confirmed(self) -> None:
        """Returns passed when turn rate is active and facing moved."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 1.5,
            "turnRate0x304After": 2.1,
            "turnRate0x304Delta": 0.6,
            "yawDeltaDegrees": 3.0,
            "facingTargetDx": 1.0,
            "facingTargetDz": 2.0,
        }
        result = classify_correlation(deltas, "left", "left")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["reason"], "active-turn-freshness-confirmed")
        self.assertTrue(result["correlationEstablished"])
        self.assertTrue(result["facingTargetMoved"])

    def test_active_turn_with_class_shift(self) -> None:
        """Active turn with class string shift includes note in detail."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": -1.5,
            "turnRate0x304After": 2.1,
            "turnRate0x304Delta": 3.6,
            "yawDeltaDegrees": 5.0,
            "facingTargetDx": 1.0,
            "facingTargetDz": 2.0,
        }
        result = classify_correlation(deltas, "right", "left")
        self.assertEqual(result["status"], "passed")
        self.assertIn("right→left", result["detail"])

    def test_dissonance_facing_moved_turn_stable(self) -> None:
        """Dissonance when facing moves but turn rate is stable."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 0.001,
            "turnRate0x304After": 0.002,
            "turnRate0x304Delta": 0.001,
            "yawDeltaDegrees": 5.0,
            "facingTargetDx": 3.0,
            "facingTargetDz": 4.0,
        }
        result = classify_correlation(deltas, "stable", "stable")
        self.assertEqual(result["status"], "dissonance")
        self.assertEqual(result["reason"], "facing-moved-while-turn-rate-stable")
        self.assertFalse(result["correlationEstablished"])

    def test_dissonance_turn_active_facing_stable(self) -> None:
        """Dissonance when turn rate changes but facing doesn't move."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 0.5,
            "turnRate0x304After": 1.5,
            "turnRate0x304Delta": 1.0,
            "yawDeltaDegrees": 0.0,
            "facingTargetDx": 0.0,
            "facingTargetDz": 0.0,
        }
        result = classify_correlation(deltas, "left", "left")
        self.assertEqual(result["status"], "dissonance")
        self.assertEqual(result["reason"], "turn-rate-active-while-facing-stable")
        self.assertFalse(result["correlationEstablished"])

    def test_facing_move_distance_computed(self) -> None:
        """Facing target move distance is computed correctly."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 0.003,
            "turnRate0x304After": 0.005,
            "turnRate0x304Delta": 0.002,
            "yawDeltaDegrees": 7.0,
            "facingTargetDx": 3.0,
            "facingTargetDz": 4.0,
        }
        result = classify_correlation(deltas, "stable", "stable")
        self.assertEqual(result["status"], "dissonance")
        self.assertAlmostEqual(result["facingTargetMoveDistance"], 5.0, places=3)

    def test_yaw_delta_preserved(self) -> None:
        """Yaw delta is preserved in the correlation output."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 0.0,
            "turnRate0x304After": 0.0,
            "turnRate0x304Delta": 0.0,
            "yawDeltaDegrees": -12.5,
            "facingTargetDx": 0.0,
            "facingTargetDz": 0.0,
        }
        result = classify_correlation(deltas, "stable", "stable")
        self.assertEqual(result["yawDeltaDegrees"], -12.5)


class TestComputeDeltas(unittest.TestCase):
    """Tests for delta computation between two readback payloads."""

    def _make_readback(
        self,
        yaw: float | None,
        turn: float | None,
        facing_x: float | None,
        facing_z: float | None,
        coord_x: float | None = 100.0,
        coord_z: float | None = 200.0,
    ) -> dict[str, Any]:
        """Build a mock _read_one_nav_state result."""
        nav_state: dict[str, Any] = {}
        if yaw is not None:
            nav_state["yawDegrees"] = yaw
        if turn is not None:
            nav_state["turnRate0x304"] = turn
        if facing_x is not None and facing_z is not None:
            nav_state["facingTargetCoordinate"] = {"x": facing_x, "z": facing_z}
        if coord_x is not None and coord_z is not None:
            nav_state["coordinate"] = {"x": coord_x, "z": coord_z}
        return {"ok": True, "navState": nav_state}

    def test_all_fields_present(self) -> None:
        """All deltas computed when all fields are present."""
        before = self._make_readback(yaw=10.0, turn=0.5, facing_x=100.0, facing_z=200.0)
        after = self._make_readback(yaw=15.0, turn=1.2, facing_x=103.0, facing_z=204.0)
        deltas = compute_deltas(before, after)
        self.assertAlmostEqual(deltas["yawDeltaDegrees"], 5.0)
        self.assertAlmostEqual(deltas["turnRate0x304Delta"], 0.7)
        self.assertAlmostEqual(deltas["facingTargetDx"], 3.0)
        self.assertAlmostEqual(deltas["facingTargetDz"], 4.0)

    def test_yaw_none_on_missing(self) -> None:
        """Yaw delta is None when yaw is missing."""
        before = self._make_readback(yaw=None, turn=0.5, facing_x=100.0, facing_z=200.0)
        after = self._make_readback(yaw=15.0, turn=1.2, facing_x=103.0, facing_z=204.0)
        deltas = compute_deltas(before, after)
        self.assertIsNone(deltas["yawDeltaDegrees"])

    def test_turn_delta_none_on_missing(self) -> None:
        """Turn delta is None when turn rate is missing."""
        before = self._make_readback(yaw=10.0, turn=0.5, facing_x=100.0, facing_z=200.0)
        after = self._make_readback(yaw=15.0, turn=None, facing_x=103.0, facing_z=204.0)
        deltas = compute_deltas(before, after)
        self.assertIsNone(deltas["turnRate0x304Delta"])

    def test_facing_deltas_none_on_missing(self) -> None:
        """Facing deltas are None when facing coordinates are missing."""
        before = self._make_readback(yaw=10.0, turn=0.5, facing_x=None, facing_z=None)
        after = self._make_readback(yaw=15.0, turn=1.2, facing_x=103.0, facing_z=204.0)
        deltas = compute_deltas(before, after)
        self.assertIsNone(deltas["facingTargetDx"])
        self.assertIsNone(deltas["facingTargetDz"])

    def test_coordinate_deltas_computed(self) -> None:
        """Coordinate deltas are computed correctly."""
        before = self._make_readback(yaw=10.0, turn=0.5, facing_x=100.0, facing_z=200.0, coord_x=500.0, coord_z=600.0)
        after = self._make_readback(yaw=15.0, turn=1.2, facing_x=103.0, facing_z=204.0, coord_x=510.0, coord_z=605.0)
        deltas = compute_deltas(before, after)
        self.assertAlmostEqual(deltas["coordinateDx"], 10.0)
        self.assertAlmostEqual(deltas["coordinateDz"], 5.0)

    def test_empty_nav_state(self) -> None:
        """Empty nav states produce all-None deltas."""
        before: dict[str, Any] = {"ok": True, "navState": {}}
        after: dict[str, Any] = {"ok": True, "navState": {}}
        deltas = compute_deltas(before, after)
        self.assertIsNone(deltas["yawDeltaDegrees"])
        self.assertIsNone(deltas["turnRate0x304Delta"])
        self.assertIsNone(deltas["facingTargetDx"])
        self.assertIsNone(deltas["coordinateDx"])

    def test_turn_before_after_preserved(self) -> None:
        """Raw turn rate values are preserved in deltas."""
        before = self._make_readback(yaw=10.0, turn=-2.5, facing_x=100.0, facing_z=200.0)
        after = self._make_readback(yaw=15.0, turn=1.5, facing_x=103.0, facing_z=204.0)
        deltas = compute_deltas(before, after)
        self.assertAlmostEqual(deltas["turnRate0x304Before"], -2.5)
        self.assertAlmostEqual(deltas["turnRate0x304After"], 1.5)


class TestCompact(unittest.TestCase):
    """Tests for the compact output formatter."""

    def test_compact_passed(self) -> None:
        """Compact output for a passed correlation."""
        summary: dict[str, Any] = {
            "status": "passed",
            "verdict": "nav-state-freshness-confirmed",
            "correlation": {
                "status": "passed",
                "correlationEstablished": True,
                "turnRateStable": True,
                "facingTargetMoved": False,
            },
            "deltas": {
                "yawDeltaDegrees": 0.0,
                "turnRate0x304Delta": 0.0,
                "facingTargetDx": 0.0,
                "facingTargetDz": 0.0,
            },
            "blockers": [],
            "warnings": [],
            "errors": [],
        }
        result = compact(summary)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["correlationStatus"], "passed")
        self.assertTrue(result["correlationEstablished"])
        self.assertEqual(result["yawDeltaDegrees"], 0.0)

    def test_compact_blocked(self) -> None:
        """Compact output for a blocked correlation."""
        summary: dict[str, Any] = {
            "status": "blocked",
            "verdict": "nav-state-insufficient-data",
            "correlation": {
                "status": "no-data",
                "correlationEstablished": False,
                "turnRateStable": False,
                "facingTargetMoved": False,
            },
            "deltas": {},
            "blockers": ["insufficient-nav-state-data"],
            "warnings": [],
            "errors": [],
        }
        result = compact(summary)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("insufficient-nav-state-data", result["blockers"])

    def test_compact_with_none_deltas(self) -> None:
        """Compact handles None delta values."""
        summary: dict[str, Any] = {
            "status": "blocked",
            "verdict": "nav-state-freshness-dissonance-detected",
            "correlation": {
                "status": "dissonance",
                "correlationEstablished": False,
                "turnRateStable": True,
                "facingTargetMoved": True,
            },
            "deltas": {
                "yawDeltaDegrees": None,
                "turnRate0x304Delta": None,
                "facingTargetDx": None,
                "facingTargetDz": None,
            },
            "blockers": ["correlation:facing-moved-while-turn-rate-stable"],
            "warnings": [],
            "errors": [],
        }
        result = compact(summary)
        self.assertIsNone(result["yawDeltaDegrees"])
        self.assertIsNone(result["turnRate0x304Delta"])


class TestSafeMapping(unittest.TestCase):
    """Tests for the safe_mapping helper."""

    def test_returns_dict(self) -> None:
        """Returns the dict when given a dict."""
        self.assertEqual(safe_mapping({"a": 1}), {"a": 1})

    def test_returns_empty_on_none(self) -> None:
        """Returns empty dict when given None."""
        self.assertEqual(safe_mapping(None), {})

    def test_returns_empty_on_string(self) -> None:
        """Returns empty dict when given a string."""
        self.assertEqual(safe_mapping("hello"), {})

    def test_returns_empty_on_list(self) -> None:
        """Returns empty dict when given a list."""
        self.assertEqual(safe_mapping([1, 2, 3]), {})

    def test_returns_empty_on_int(self) -> None:
        """Returns empty dict when given an int."""
        self.assertEqual(safe_mapping(42), {})


class TestBuildParser(unittest.TestCase):
    """Tests for CLI argument parsing."""

    def test_defaults(self) -> None:
        """Parser returns expected defaults."""
        parser = build_parser()
        args = parser.parse_args([])
        self.assertEqual(args.interval_seconds, 0.5)
        self.assertEqual(args.timeout_seconds, 30.0)
        self.assertEqual(args.process_name, "rift_x64")
        self.assertEqual(args.current_truth_json, "docs/recovery/current-truth.json")
        self.assertFalse(args.json)
        self.assertFalse(args.use_current_truth)

    def test_custom_interval(self) -> None:
        """Custom interval is parsed correctly."""
        parser = build_parser()
        args = parser.parse_args(["--interval-seconds", "0.25"])
        self.assertEqual(args.interval_seconds, 0.25)

    def test_pid_parsed(self) -> None:
        """PID is parsed as int."""
        parser = build_parser()
        args = parser.parse_args(["--pid", "25668"])
        self.assertEqual(args.pid, 25668)

    def test_use_current_truth_flag(self) -> None:
        """--use-current-truth flag is recognized."""
        parser = build_parser()
        args = parser.parse_args(["--use-current-truth"])
        self.assertTrue(args.use_current_truth)

    def test_json_flag(self) -> None:
        """--json flag is recognized."""
        parser = build_parser()
        args = parser.parse_args(["--json"])
        self.assertTrue(args.json)

    def test_all_flags_combined(self) -> None:
        """All flags combined parse correctly."""
        parser = build_parser()
        args = parser.parse_args([
            "--pid", "25668",
            "--hwnd", "0x320CB0",
            "--module-base", "0x7FF6EE5D0000",
            "--use-current-truth",
            "--interval-seconds", "1.0",
            "--json",
        ])
        self.assertEqual(args.pid, 25668)
        self.assertEqual(args.hwnd, "0x320CB0")
        self.assertTrue(args.use_current_truth)
        self.assertEqual(args.interval_seconds, 1.0)
        self.assertTrue(args.json)


class TestEdgeCases(unittest.TestCase):
    """Edge case tests for the watchdog."""

    def test_classify_correlation_facing_none_movement(self) -> None:
        """When facing dx/dz are None, facing_moved is False."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 0.003,
            "turnRate0x304After": 0.005,
            "turnRate0x304Delta": 0.002,
            "yawDeltaDegrees": 0.0,
            "facingTargetDx": None,
            "facingTargetDz": None,
        }
        result = classify_correlation(deltas, "stable", "stable")
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["facingTargetMoved"])

    def test_classify_correlation_zero_turn_delta_stable(self) -> None:
        """Zero turn delta is considered stable."""
        deltas: dict[str, Any] = {
            "turnRate0x304Before": 0.0,
            "turnRate0x304After": 0.0,
            "turnRate0x304Delta": 0.0,
            "yawDeltaDegrees": 0.0,
            "facingTargetDx": 0.0,
            "facingTargetDz": 0.0,
        }
        result = classify_correlation(deltas, "none", "none")
        self.assertTrue(result["turnRateStable"])

    def test_compute_deltas_with_mixed_types(self) -> None:
        """Deltas handle int/float mix correctly."""
        before: dict[str, Any] = {"ok": True, "navState": {"yawDegrees": 10, "turnRate0x304": 1}}
        after: dict[str, Any] = {"ok": True, "navState": {"yawDegrees": 15.5, "turnRate0x304": 1.8}}
        deltas = compute_deltas(before, after)
        self.assertAlmostEqual(deltas["yawDeltaDegrees"], 5.5)
        self.assertAlmostEqual(deltas["turnRate0x304Delta"], 0.8)


if __name__ == "__main__":
    unittest.main()
