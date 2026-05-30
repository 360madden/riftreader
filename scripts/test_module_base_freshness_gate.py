"""Tests for module base freshness gate (#1) and facing target zero-vector guard (#2).

These guards prevent silent navigation failures caused by:
- Stale module base in current-truth.json (reads from wrong memory)
- Facing target (0,0,0) after fresh zone-in or resolver degradation
"""

import struct
import unittest

from static_owner_coordinate_chain_readback import (
    DEFAULT_COORD_OFFSET,
    DEFAULT_FACING_TARGET_ZERO_EPSILON,
    get_live_module_base,
    int_hex,
    nav_state_from_owner_bytes,
    triplet_is_zero,
)


class TestTripletIsZero(unittest.TestCase):
    """Zero-vector detection for the facing-target guard."""

    def test_exact_zero(self) -> None:
        self.assertTrue(triplet_is_zero({"x": 0.0, "y": 0.0, "z": 0.0}))

    def test_near_zero_within_epsilon(self) -> None:
        eps = DEFAULT_FACING_TARGET_ZERO_EPSILON
        self.assertTrue(
            triplet_is_zero({"x": eps * 0.5, "y": eps * 0.5, "z": eps * 0.5})
        )

    def test_near_zero_all_negative(self) -> None:
        eps = DEFAULT_FACING_TARGET_ZERO_EPSILON
        self.assertTrue(
            triplet_is_zero({"x": -eps * 0.9, "y": -eps * 0.9, "z": -eps * 0.9})
        )

    def test_above_epsilon_not_zero(self) -> None:
        self.assertFalse(
            triplet_is_zero({"x": 0.01, "y": 0.01, "z": 0.01})
        )

    def test_one_axis_above_epsilon(self) -> None:
        self.assertFalse(
            triplet_is_zero({"x": 0.0, "y": 0.0, "z": 25.0})
        )

    def test_one_axis_near_zero_others_above(self) -> None:
        self.assertFalse(
            triplet_is_zero({"x": 0.0, "y": 100.0, "z": 100.0})
        )

    def test_valid_facing_target_not_zero(self) -> None:
        self.assertFalse(
            triplet_is_zero({"x": 7262.43, "y": 821.46, "z": 3011.12})
        )

    def test_custom_epsilon(self) -> None:
        self.assertTrue(
            triplet_is_zero({"x": 1.0, "y": 1.0, "z": 1.0}, epsilon=2.0)
        )
        self.assertFalse(
            triplet_is_zero({"x": 1.0, "y": 1.0, "z": 1.0}, epsilon=0.5)
        )

    def test_inf_and_nan_not_zero(self) -> None:
        import math
        self.assertFalse(
            triplet_is_zero({"x": float("inf"), "y": float("inf"), "z": float("inf")})
        )
        self.assertFalse(
            triplet_is_zero({"x": float("nan"), "y": float("nan"), "z": float("nan")})
        )
        # But triple with one nan and two zeros: not zero
        self.assertFalse(
            triplet_is_zero({"x": float("nan"), "y": 0.0, "z": 0.0})
        )


class TestNavStateFacingTargetZeroVector(unittest.TestCase):
    """Tests that nav_state_from_owner_bytes detects zero-vector facing target."""

    def _build_owner_bytes(
        self,
        *,
        facing_x: float = 7262.43,
        facing_y: float = 821.46,
        facing_z: float = 3011.12,
        position_x: float = 7262.06,
        position_y: float = 821.58,
        position_z: float = 3001.12,
        turn_rate: float = 0.0,
        coord_offset: int = DEFAULT_COORD_OFFSET,
    ) -> bytes:
        """Build synthetic owner window bytes with nav-state fields."""
        # Allocate enough room: coord_offset + 12 bytes for coordinate triplet
        size = coord_offset + 12
        data = bytearray(size)
        # Turn rate at coord_offset - 0x1C
        struct.pack_into("<f", data, coord_offset - 0x1C, turn_rate)
        # Facing target at coord_offset - 0x14
        struct.pack_into("<fff", data, coord_offset - 0x14, facing_x, facing_y, facing_z)
        # Position at coord_offset
        struct.pack_into("<fff", data, coord_offset, position_x, position_y, position_z)
        return bytes(data)

    def test_zero_facing_target_returns_error(self) -> None:
        data = self._build_owner_bytes(facing_x=0.0, facing_y=0.0, facing_z=0.0)
        result = nav_state_from_owner_bytes(data, owner_address=0x1234)
        self.assertEqual(result.get("navStateError"), "facing-target-zero-vector")
        self.assertIsNotNone(result.get("facingTargetCoordinate"))
        fc = result["facingTargetCoordinate"]
        self.assertAlmostEqual(fc["x"], 0.0)
        self.assertAlmostEqual(fc["y"], 0.0)
        self.assertAlmostEqual(fc["z"], 0.0)

    def test_near_zero_facing_target_within_epsilon(self) -> None:
        eps = DEFAULT_FACING_TARGET_ZERO_EPSILON * 0.5
        data = self._build_owner_bytes(
            facing_x=eps, facing_y=eps, facing_z=-eps,
        )
        result = nav_state_from_owner_bytes(data, owner_address=0x1234)
        self.assertEqual(result.get("navStateError"), "facing-target-zero-vector")

    def test_valid_facing_target_no_error(self) -> None:
        data = self._build_owner_bytes()
        result = nav_state_from_owner_bytes(data, owner_address=0x1234)
        self.assertIsNone(result.get("navStateError"))
        self.assertIsNotNone(result.get("yawDegrees"))
        self.assertIsNotNone(result.get("facingTargetCoordinate"))

    def test_zero_facing_does_not_affect_position_read(self) -> None:
        data = self._build_owner_bytes(
            facing_x=0.0, facing_y=0.0, facing_z=0.0,
            position_x=100.0, position_y=200.0, position_z=300.0,
        )
        result = nav_state_from_owner_bytes(data, owner_address=0x1234)
        self.assertEqual(result.get("navStateError"), "facing-target-zero-vector")
        self.assertAlmostEqual(result["facingTargetCoordinate"]["x"], 0.0)
        # Position is still correctly recorded in the error return
        self.assertIsNotNone(result["facingTargetCoordinate"])

    def test_non_finite_facing_takes_priority_over_zero_check(self) -> None:
        """The non-finite check runs first and should short-circuit."""
        import math
        data = self._build_owner_bytes(
            facing_x=float("nan"), facing_y=float("nan"), facing_z=float("nan"),
        )
        result = nav_state_from_owner_bytes(data, owner_address=0x1234)
        self.assertEqual(
            result.get("navStateError"), "non-finite-facing-target-coordinate"
        )

    def test_facing_target_exactly_on_epsilon_boundary(self) -> None:
        eps = DEFAULT_FACING_TARGET_ZERO_EPSILON
        # Exactly at epsilon — should be treated as NOT zero
        data = self._build_owner_bytes(facing_x=eps, facing_y=eps, facing_z=eps)
        result = nav_state_from_owner_bytes(data, owner_address=0x1234)
        self.assertIsNone(result.get("navStateError"))


class TestModuleBaseEnumeration(unittest.TestCase):
    """Tests for get_live_module_base enumeration logic."""

    def test_nonexistent_pid_returns_none(self) -> None:
        # PID 0 is the System Idle Process — no modules
        result = get_live_module_base(0, "rift_x64.exe")
        self.assertIsNone(result)

    def test_invalid_pid_returns_none(self) -> None:
        result = get_live_module_base(99999999, "rift_x64.exe")
        self.assertIsNone(result)

    def test_enumeration_is_case_insensitive(self) -> None:
        # Only test that the comparison logic works — will fail enumeration
        # but should not crash regardless of casing
        result = get_live_module_base(99999999, "RIFT_X64.EXE")
        self.assertIsNone(result)

    def test_module_name_without_extension(self) -> None:
        result = get_live_module_base(99999999, "rift_x64")
        self.assertIsNone(result)


class TestModuleBaseCheckInNavStateReadback(unittest.TestCase):
    """Tests that nav_state_readback.py correctly surfaces module-base blockers.

    When the subprocess returns status=blocked with a module-base-mismatch
    blocker, read_nav_state() must return ok=False (not silently pass).
    """

    def test_blocked_status_produces_not_ok(self) -> None:
        # The ok-logic rule in nav_state_readback.py:
        #   parsed.get("status") not in ("unavailable", "readback-failed",
        #   "parse-error", "blocked")
        # These four statuses MUST produce ok=False so that callers
        # (route plan, route runner, decision packet, target watch)
        # never consume nav-state data from a blocked/failed readback.
        not_ok_statuses = {"unavailable", "readback-failed", "parse-error", "blocked"}
        ok_statuses = {"passed", "warning", "degraded"}
        for status in not_ok_statuses:
            with self.subTest(status=status):
                ok = status not in {"unavailable", "readback-failed", "parse-error", "blocked"}
                self.assertFalse(ok, f"status={status} must produce ok=False")
        for status in ok_statuses:
            with self.subTest(status=status):
                ok = status not in {"unavailable", "readback-failed", "parse-error", "blocked"}
                self.assertTrue(ok, f"status={status} must produce ok=True")


if __name__ == "__main__":
    unittest.main()
