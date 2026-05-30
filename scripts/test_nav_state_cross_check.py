"""Tests for _build_nav_state_cross_check in static_owner_turn_aware_route_plan.py."""
from __future__ import annotations

import unittest
from typing import Any

from scripts.static_owner_turn_aware_route_plan import _build_nav_state_cross_check


def _make_latest_state(
    yaw: float = 0.0,
    turn_rate_class: str = "stable",
    turn_rate_discriminator: float = 0.0,
) -> dict[str, Any]:
    return {
        "yawDegrees": yaw,
        "turnRateClassification": turn_rate_class,
        "turnRateDiscriminator": turn_rate_discriminator,
    }


def _make_nav_state_readback(
    ok: bool = True,
    yaw: float = 0.0,
    turn_rate_0x304: float = 0.0,
    turn_rate_class: str = "stable",
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "yawDegrees": yaw,
        "turnRate0x304": turn_rate_0x304,
        "turnRateClassification": turn_rate_class,
        "error": error,
    }


class TestBuildNavStateCrossCheck(unittest.TestCase):
    """Tests for _build_nav_state_cross_check."""

    # ------------------------------------------------------------------
    # Unavailable / not-requested
    # ------------------------------------------------------------------

    def test_unavailable_when_nav_state_none(self) -> None:
        """Returns unavailable when nav_state_readback is None."""
        result = _build_nav_state_cross_check(
            _make_latest_state(),
            None,
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["actionableForNavigation"])

    def test_unavailable_when_nav_state_not_ok(self) -> None:
        """Returns unavailable when nav_state_readback ok=False."""
        result = _build_nav_state_cross_check(
            _make_latest_state(),
            _make_nav_state_readback(ok=False, error="readback-failed"),
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "readback-failed")
        self.assertFalse(result["actionableForNavigation"])

    # ------------------------------------------------------------------
    # Agreement cases
    # ------------------------------------------------------------------

    def test_agreement_when_all_match(self) -> None:
        """Status is agreement when yaw and turn rate match."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=45.0, turn_rate_class="stable", turn_rate_discriminator=0.001),
            _make_nav_state_readback(yaw=45.0, turn_rate_0x304=0.001, turn_rate_class="stable"),
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["status"], "agreement")
        self.assertIn("turn-rate-classification-agrees:stable", result["agreements"])
        self.assertIn("turn-rate-discriminator-agrees", result["agreements"][1])
        self.assertIn("yaw-agrees", result["agreements"][2])
        self.assertEqual(result["warnings"], [])

    def test_agreement_yaw_small_delta(self) -> None:
        """Yaw delta < 1.0 degrees is agreement."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=45.0, turn_rate_class="stable", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=45.5, turn_rate_0x304=0.0, turn_rate_class="stable"),
        )
        self.assertEqual(result["status"], "agreement")
        self.assertTrue(any("yaw-agrees" in a for a in result["agreements"]))

    def test_agreement_yaw_boundary(self) -> None:
        """Yaw delta exactly 0.99 is still agreement."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="stable", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=0.99, turn_rate_0x304=0.0, turn_rate_class="stable"),
        )
        self.assertEqual(result["status"], "agreement")

    def test_agreement_turn_discriminator_small_delta(self) -> None:
        """Turn discriminator delta < 0.01 is agreement."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="stable", turn_rate_discriminator=0.005),
            _make_nav_state_readback(yaw=0.0, turn_rate_0x304=0.008, turn_rate_class="stable"),
        )
        self.assertEqual(result["status"], "agreement")
        self.assertTrue(any("turn-rate-discriminator-agrees" in a for a in result["agreements"]))

    # ------------------------------------------------------------------
    # Warning cases (close but not exact match)
    # ------------------------------------------------------------------

    def test_yaw_close(self) -> None:
        """Yaw delta 1.0-5.0 degrees is a close warning."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="stable", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=3.0, turn_rate_0x304=0.0, turn_rate_class="stable"),
        )
        self.assertEqual(result["status"], "dissonance")
        self.assertTrue(any("yaw-close" in w for w in result["warnings"]))

    def test_turn_discriminator_close(self) -> None:
        """Turn discriminator delta 0.01-0.5 is a close warning."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="stable", turn_rate_discriminator=0.1),
            _make_nav_state_readback(yaw=0.0, turn_rate_0x304=0.4, turn_rate_class="stable"),
        )
        self.assertEqual(result["status"], "dissonance")
        self.assertTrue(any("turn-rate-discriminator-close" in w for w in result["warnings"]))

    # ------------------------------------------------------------------
    # Dissonance cases
    # ------------------------------------------------------------------

    def test_dissonance_yaw_diverges(self) -> None:
        """Yaw delta > 5.0 degrees is a divergence warning."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="stable", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=10.0, turn_rate_0x304=0.0, turn_rate_class="stable"),
        )
        self.assertEqual(result["status"], "dissonance")
        self.assertTrue(any("yaw-diverges" in w for w in result["warnings"]))

    def test_dissonance_turn_discriminator_diverges(self) -> None:
        """Turn discriminator delta > 0.5 is a divergence warning."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="stable", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=0.0, turn_rate_0x304=2.0, turn_rate_class="stable"),
        )
        self.assertEqual(result["status"], "dissonance")
        self.assertTrue(any("turn-rate-discriminator-diverges" in w for w in result["warnings"]))

    def test_dissonance_turn_class_disagrees(self) -> None:
        """Turn rate classification mismatch produces dissonance."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="left", turn_rate_discriminator=1.5),
            _make_nav_state_readback(yaw=0.0, turn_rate_0x304=1.5, turn_rate_class="right"),
        )
        self.assertEqual(result["status"], "dissonance")
        self.assertTrue(any("turn-rate-classification-disagrees" in w for w in result["warnings"]))

    # ------------------------------------------------------------------
    # Active turn scenarios
    # ------------------------------------------------------------------

    def test_agreement_active_turn(self) -> None:
        """Agreement during active left turn with consistent yaw delta and tight discriminator match."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=-30.0, turn_rate_class="left", turn_rate_discriminator=1.80),
            _make_nav_state_readback(yaw=-29.5, turn_rate_0x304=1.805, turn_rate_class="left"),
        )
        self.assertEqual(result["status"], "agreement")
        self.assertIn("turn-rate-classification-agrees:left", result["agreements"])

    def test_dissonance_active_turn_class_mismatch(self) -> None:
        """Mismatch when one source says left and the other says right."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=45.0, turn_rate_class="left", turn_rate_discriminator=2.0),
            _make_nav_state_readback(yaw=45.0, turn_rate_0x304=-2.0, turn_rate_class="right"),
        )
        self.assertEqual(result["status"], "dissonance")

    # ------------------------------------------------------------------
    # Unknown classifications
    # ------------------------------------------------------------------

    def test_unknown_turn_class_skips_comparison(self) -> None:
        """When either classification is unknown, skip class comparison."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="unknown", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=0.0, turn_rate_0x304=0.0, turn_rate_class="stable"),
        )
        self.assertEqual(result["status"], "agreement")
        self.assertFalse(any("classification" in a for a in result["agreements"]))
        self.assertFalse(any("classification" in w for w in result["warnings"]))

    def test_ptr_unknown_class_skips_comparison(self) -> None:
        """When pointer-chain classification is unknown, skip class comparison."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="stable", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=0.0, turn_rate_0x304=0.0, turn_rate_class="unknown"),
        )
        self.assertEqual(result["status"], "agreement")

    # ------------------------------------------------------------------
    # Safety markers
    # ------------------------------------------------------------------

    def test_safety_markers_present(self) -> None:
        """candidateOnly and actionableForNavigation markers are always present."""
        result = _build_nav_state_cross_check(
            _make_latest_state(),
            _make_nav_state_readback(),
        )
        self.assertTrue(result["candidateOnly"])
        self.assertFalse(result["actionableForNavigation"])

    def test_safety_markers_present_on_unavailable(self) -> None:
        """Safety markers present even when unavailable."""
        result = _build_nav_state_cross_check(_make_latest_state(), None)
        self.assertTrue(result["candidateOnly"])
        self.assertFalse(result["actionableForNavigation"])

    # ------------------------------------------------------------------
    # Output structure
    # ------------------------------------------------------------------

    def test_output_has_pointer_chain_fields(self) -> None:
        """Pointer-chain source fields are present in output."""
        result = _build_nav_state_cross_check(
            _make_latest_state(),
            _make_nav_state_readback(yaw=42.0, turn_rate_0x304=1.25, turn_rate_class="left"),
        )
        pc = result["pointerChain"]
        self.assertEqual(pc["yawDegrees"], 42.0)
        self.assertEqual(pc["turnRate0x304"], 1.25)
        self.assertEqual(pc["turnRateClassification"], "left")

    def test_output_has_facing_discovery_fields(self) -> None:
        """Facing-discovery source fields are present in output."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=42.0, turn_rate_class="left", turn_rate_discriminator=1.25),
            _make_nav_state_readback(yaw=42.0, turn_rate_0x304=1.25, turn_rate_class="left"),
        )
        fd = result["facingDiscovery"]
        self.assertEqual(fd["yawDegrees"], 42.0)
        self.assertEqual(fd["turnRateDiscriminator"], 1.25)
        self.assertEqual(fd["turnRateClassification"], "left")

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_yaw_none_in_pointer_chain(self) -> None:
        """When pointer-chain yaw is None, yaw comparison is skipped."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=45.0, turn_rate_class="stable", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=None, turn_rate_0x304=0.0, turn_rate_class="stable"),
        )
        # Should still be available, but no yaw agreement/disagreement
        self.assertTrue(result["available"])
        self.assertFalse(any("yaw" in a for a in result.get("agreements", [])))

    def test_turn_rate_none_in_pointer_chain(self) -> None:
        """When pointer-chain turn rate is None, discriminator comparison skipped."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="stable", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=0.0, turn_rate_0x304=None, turn_rate_class="stable"),
        )
        self.assertTrue(result["available"])
        self.assertFalse(any("discriminator" in a for a in result.get("agreements", [])))

    def test_yaw_none_in_facing_discovery(self) -> None:
        """When facing-discovery yaw is None, yaw comparison is skipped."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=None, turn_rate_class="stable", turn_rate_discriminator=0.0),
            _make_nav_state_readback(yaw=45.0, turn_rate_0x304=0.0, turn_rate_class="stable"),
        )
        self.assertTrue(result["available"])

    def test_multiple_warnings(self) -> None:
        """Multiple disagreements produce multiple warnings."""
        result = _build_nav_state_cross_check(
            _make_latest_state(yaw=0.0, turn_rate_class="left", turn_rate_discriminator=2.0),
            _make_nav_state_readback(yaw=10.0, turn_rate_0x304=-1.0, turn_rate_class="right"),
        )
        self.assertEqual(result["status"], "dissonance")
        self.assertGreaterEqual(len(result["warnings"]), 3)


if __name__ == "__main__":
    unittest.main()
