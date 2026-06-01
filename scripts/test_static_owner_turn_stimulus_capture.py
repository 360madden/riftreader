import argparse
import json
import tempfile
import unittest
from pathlib import Path

from scripts.static_owner_turn_stimulus_capture import (
    classify_turn_analysis,
    validate_args,
    validate_saved_summary,
    validate_turn_capture_summary_contract,
)


def state(yaw: float, x: float = 10.0, z: float = 20.0, turn_rate: float | None = None) -> dict:
    latest = {
        "yawDegrees": yaw,
        "coordinate": {
            "x": x,
            "y": 5.0,
            "z": z,
        },
    }
    if turn_rate is not None:
        latest["turnRate0x304"] = turn_rate
    return {
        "status": "passed",
        "latestState": latest,
    }


class StaticOwnerTurnStimulusCaptureTests(unittest.TestCase):
    def test_classify_left_turn_passes_negative_yaw_delta(self):
        analysis = classify_turn_analysis(
            state(90.0, turn_rate=0.0),
            state(84.0, turn_rate=0.0),
            mid_summary=state(88.0, turn_rate=1.25),
            stimulus_running_before_mid_readback=True,
            stimulus_running_after_mid_readback=True,
            direction="left",
            key="left",
            minimum_yaw_delta_degrees=2.0,
            minimum_turn_rate_abs=0.01,
            max_planar_drift=1.0,
        )

        self.assertEqual("passed", analysis["status"])
        self.assertLess(analysis["signedYawDeltaDegrees"], 0)
        self.assertTrue(analysis["candidateOnly"])
        self.assertFalse(analysis["actionableForNavigation"])

    def test_classify_blocks_small_yaw_delta(self):
        analysis = classify_turn_analysis(
            state(90.0),
            state(89.5),
            direction="left",
            key="left",
            minimum_yaw_delta_degrees=2.0,
            max_planar_drift=1.0,
        )

        self.assertEqual("blocked", analysis["status"])
        self.assertIn("yaw-delta-below-threshold", analysis["blockers"])

    def test_classify_blocks_opposite_direction(self):
        analysis = classify_turn_analysis(
            state(90.0),
            state(96.0),
            direction="left",
            key="left",
            minimum_yaw_delta_degrees=2.0,
            max_planar_drift=1.0,
        )

        self.assertEqual("blocked", analysis["status"])
        self.assertIn("yaw-delta-opposite-expected-direction", analysis["blockers"])

    def test_classify_blocks_planar_drift(self):
        analysis = classify_turn_analysis(
            state(90.0, 10.0, 20.0),
            state(84.0, 12.0, 20.0),
            direction="left",
            key="left",
            minimum_yaw_delta_degrees=2.0,
            max_planar_drift=1.0,
        )

        self.assertEqual("blocked", analysis["status"])
        self.assertIn("planar-drift-exceeded", analysis["blockers"])

    def test_classify_left_turn_records_positive_mid_turn_rate_sign(self):
        analysis = classify_turn_analysis(
            state(90.0, turn_rate=0.0),
            state(84.0, turn_rate=0.0),
            mid_summary=state(88.0, turn_rate=1.25),
            stimulus_running_before_mid_readback=True,
            stimulus_running_after_mid_readback=True,
            direction="left",
            key="left",
            minimum_yaw_delta_degrees=2.0,
            minimum_turn_rate_abs=0.01,
            max_planar_drift=1.0,
        )

        self.assertEqual("passed", analysis["status"])
        self.assertEqual("left", analysis["turnRateObservedDirection"])
        self.assertTrue(analysis["turnRateSignMatchedDirection"])
        self.assertEqual(1.25, analysis["turnRateDelta"])

    def test_classify_right_turn_blocks_positive_mid_turn_rate_sign(self):
        analysis = classify_turn_analysis(
            state(84.0, turn_rate=0.0),
            state(90.0, turn_rate=0.0),
            mid_summary=state(88.0, turn_rate=1.25),
            stimulus_running_before_mid_readback=True,
            stimulus_running_after_mid_readback=True,
            direction="right",
            key="right",
            minimum_yaw_delta_degrees=2.0,
            minimum_turn_rate_abs=0.01,
            max_planar_drift=1.0,
        )

        self.assertEqual("blocked", analysis["status"])
        self.assertIn("turn-rate-sign-opposite-expected-direction", analysis["blockers"])

    def test_classify_left_turn_accepts_yaw_wrap_when_turn_rate_sign_matches(self):
        analysis = classify_turn_analysis(
            state(37.0, turn_rate=0.0),
            state(-169.0, turn_rate=0.0),
            mid_summary=state(37.0, turn_rate=0.95),
            stimulus_running_before_mid_readback=True,
            stimulus_running_after_mid_readback=True,
            direction="left",
            key="left",
            minimum_yaw_delta_degrees=2.0,
            minimum_turn_rate_abs=0.01,
            max_planar_drift=1.0,
        )

        self.assertEqual("passed", analysis["status"])
        self.assertNotIn("yaw-delta-opposite-expected-direction", analysis["blockers"])
        self.assertIn("yaw-delta-normalized-opposite-turn-rate-sign-likely-wrap", analysis["warnings"])

    def test_validate_args_requires_positive_hold(self):
        args = argparse.Namespace(
            direction="left",
            samples=3,
            interval_seconds=0.1,
            hold_milliseconds=0,
            settle_seconds=0.75,
            minimum_yaw_delta_degrees=2.0,
            minimum_turn_rate_abs=0.01,
            max_planar_drift=1.0,
            command_timeout_seconds=120.0,
            mid_turn_sample_delay_seconds=0.15,
            mid_turn_samples=1,
            mid_turn_interval_seconds=0.0,
        )

        self.assertIn("hold-milliseconds-must-be-positive", validate_args(args))

    def test_turn_capture_contract_passes_safe_fixture_shape(self):
        summary = {
            "kind": "static-owner-turn-stimulus-capture",
            "status": "passed",
            "verdict": "turn-yaw-delta-validated",
            "analysis": {
                "status": "passed",
                "candidateOnly": True,
                "actionableForNavigation": False,
                "movementPermission": False,
                "facingPromotion": False,
                "absoluteYawDeltaDegrees": 6.0,
                "signedYawDeltaDegrees": -6.0,
                "midTurnRate0x304": 1.25,
                "turnRateDelta": 1.25,
                "turnRateSignMatchedDirection": True,
                "coordinateDelta": {"planar": 0.0},
                "direction": "left",
                "key": "left",
            },
            "safety": {
                "movementSent": True,
                "inputSent": True,
                "reloaduiSent": False,
                "screenshotKeySent": False,
                "noCheatEngine": True,
                "x64dbgAttach": False,
                "debuggerAttached": False,
                "providerWrites": False,
                "gitMutation": False,
                "proofPromotion": False,
                "actorChainPromotion": False,
                "facingPromotion": False,
                "navigationControl": False,
                "savedVariablesUsedAsLiveTruth": False,
            },
            "artifacts": {
                "preStateSummaryJson": "pre.json",
                "midTurnStateSummaryJson": "mid.json",
                "postStateSummaryJson": "post.json",
            },
            "childCommands": [
                {"label": "01-pre-state"},
                {"label": "02-turn-stimulus"},
                {"label": "03-mid-turn-state"},
                {"label": "04-post-state"},
            ],
        }

        contract = validate_turn_capture_summary_contract(summary)

        self.assertEqual("passed", contract["status"])
        self.assertEqual([], contract["blockers"])
        self.assertEqual(-6.0, contract["signedYawDeltaDegrees"])
        self.assertTrue(contract["turnRateSignMatchedDirection"])

    def test_checked_in_left_turn_fixture_passes_contract(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-turn-stimulus-summary-left.json"
        summary = json.loads(fixture.read_text(encoding="utf-8"))

        contract = validate_turn_capture_summary_contract(summary)

        self.assertEqual("passed", contract["status"])
        self.assertEqual([], contract["blockers"])
        self.assertEqual("left", contract["direction"])
        self.assertLess(contract["signedYawDeltaDegrees"], 0)
        self.assertEqual(0.0, contract["planarDrift"])

    def test_checked_in_right_turn_fixture_passes_contract(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-turn-stimulus-summary-right.json"
        summary = json.loads(fixture.read_text(encoding="utf-8"))

        contract = validate_turn_capture_summary_contract(summary)

        self.assertEqual("passed", contract["status"])
        self.assertEqual([], contract["blockers"])
        self.assertEqual("right", contract["direction"])
        self.assertGreater(contract["signedYawDeltaDegrees"], 0)
        self.assertEqual(0.0, contract["planarDrift"])

    def test_validate_saved_turn_fixture_passes(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-turn-stimulus-summary-left.json"
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                repo_root=None,
                output_root=tmp,
                validate_turn_summary_json=str(fixture),
            )

            summary = validate_saved_summary(args)

        self.assertEqual("passed", summary["status"])
        self.assertEqual("passed", summary["contract"]["status"])
        self.assertEqual([], summary["blockers"])


if __name__ == "__main__":
    unittest.main()
