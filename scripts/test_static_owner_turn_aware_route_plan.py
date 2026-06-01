import argparse
import json
import tempfile
import unittest
from pathlib import Path

from scripts.static_owner_turn_aware_route_plan import (
    build_turn_aware_plan,
    turn_magnitude_class,
    validate_args,
    validate_saved_summary,
    validate_turn_aware_plan_contract,
)


def state(
    yaw: float,
    x: float = 0.0,
    z: float = 0.0,
    *,
    turn_rate_classification: str | None = None,
    turn_rate_state: str = "candidate",
) -> dict:
    result = {
        "coordinate": {"x": x, "y": 0.0, "z": z},
        "yawDegrees": yaw,
    }
    if turn_rate_classification is not None:
        result["turnRateClassification"] = turn_rate_classification
        result["chainStates"] = {"turnRate": {"state": turn_rate_state}}
    return result


def target(x: float, z: float, *, label: str = "test", alignment: float = 7.5) -> dict:
    return {
        "sourceKind": "direct-coordinates",
        "sourceFile": None,
        "waypointId": None,
        "destinationLabel": label,
        "destinationX": x,
        "destinationY": None,
        "destinationZ": z,
        "arrivalRadius": 2.0,
        "alignmentThresholdDegrees": alignment,
    }


class StaticOwnerTurnAwareRoutePlanTests(unittest.TestCase):
    def test_aligned_plan_recommends_forward_without_turn_gate(self):
        plan = build_turn_aware_plan(state(0.0), target(10.0, 0.0))

        self.assertEqual("forward", plan["firstAction"])
        self.assertEqual("aligned", plan["turnMagnitudeClass"])
        self.assertFalse(plan["executionBlocked"])
        self.assertEqual("not-required", plan["turnControlGate"]["status"])

    def test_small_angle_still_recommends_forward(self):
        plan = build_turn_aware_plan(state(0.0), target(10.0, 0.75, label="small"))

        self.assertEqual("forward", plan["firstAction"])
        self.assertEqual("small-angle", plan["turnMagnitudeClass"])
        self.assertFalse(plan["executionBlocked"])

    def test_turn_needed_blocks_without_candidate_turn_control(self):
        plan = build_turn_aware_plan(state(0.0), target(0.0, 10.0, label="turn"))

        self.assertEqual("turn-right", plan["firstAction"])
        self.assertEqual("turn-needed", plan["turnMagnitudeClass"])
        self.assertTrue(plan["executionBlocked"])
        self.assertIn("candidate-turn-control-not-enabled", plan["executionBlockers"])

    def test_turn_needed_can_be_unblocked_by_explicit_candidate_turn_gate(self):
        plan = build_turn_aware_plan(
            state(0.0),
            target(0.0, 10.0, label="turn"),
            allow_candidate_turn_control=True,
        )

        self.assertEqual("turn-right", plan["firstAction"])
        self.assertFalse(plan["executionBlocked"])
        self.assertEqual("passed", plan["turnControlGate"]["status"])

    def test_candidate_turn_rate_mismatch_is_warning_not_hard_block(self):
        plan = build_turn_aware_plan(
            state(0.0, turn_rate_classification="left", turn_rate_state="candidate"),
            target(0.0, 10.0, label="turn"),
            allow_candidate_turn_control=True,
        )

        self.assertEqual("turn-right", plan["firstAction"])
        self.assertFalse(plan["executionBlocked"])
        self.assertIn("candidate-turn-direction-mismatch", " ".join(plan["turnControlGate"]["warnings"]))

    def test_promoted_turn_rate_mismatch_blocks(self):
        plan = build_turn_aware_plan(
            state(0.0, turn_rate_classification="left", turn_rate_state="promoted"),
            target(0.0, 10.0, label="turn"),
            allow_candidate_turn_control=True,
        )

        self.assertEqual("turn-right", plan["firstAction"])
        self.assertTrue(plan["executionBlocked"])
        self.assertIn(
            "turn-direction-mismatch-atan2-wants-right-but-engine-0x304-is-turning-left",
            plan["executionBlockers"],
        )

    def test_multi_step_turn_control_stays_blocked_even_with_candidate_turn_gate(self):
        plan = build_turn_aware_plan(
            state(0.0),
            target(0.0, 10.0, label="multi-step-turn"),
            allow_candidate_turn_control=True,
            max_route_steps=2,
        )

        self.assertEqual("turn-right", plan["firstAction"])
        self.assertTrue(plan["executionBlocked"])
        self.assertIn("multi-step-turn-aware-routing-not-enabled", plan["executionBlockers"])
        self.assertEqual("blocked", plan["turnControlGate"]["status"])

    def test_opposite_facing_is_classified_and_bounded(self):
        plan = build_turn_aware_plan(state(0.0), target(-10.0, 0.0, label="opposite"))

        self.assertEqual("turn-left", plan["firstAction"])
        self.assertEqual("opposite-facing", plan["turnMagnitudeClass"])
        self.assertIn("initial-turn-exceeds-max-initial-turn-degrees", plan["executionBlockers"])

    def test_turn_magnitude_class_arrived(self):
        self.assertEqual(
            "arrived",
            turn_magnitude_class({"withinArrivalRadius": True, "absoluteBearingDeltaDegrees": 0.0}),
        )

    def test_validate_args_requires_destination(self):
        args = argparse.Namespace(
            destination_x=None,
            destination_y=None,
            destination_z=None,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            state_summary_json=None,
            arrival_radius=2.0,
            alignment_threshold_degrees=7.5,
            opposite_threshold_degrees=150.0,
            max_initial_turn_degrees=90.0,
            max_cumulative_turn_degrees=90.0,
            max_total_input_milliseconds=700,
            max_route_steps=1,
            samples=3,
            interval_seconds=0.1,
            command_timeout_seconds=120.0,
        )

        self.assertIn("destination-x-and-z-required", validate_args(args))

    def test_checked_in_plan_fixtures_pass_contract(self):
        testdata = Path(__file__).resolve().parent / "navigation" / "testdata"
        expected = {
            "static-owner-turn-aware-route-plan-summary-aligned.json": ("forward", "aligned"),
            "static-owner-turn-aware-route-plan-summary-small-angle.json": ("forward", "small-angle"),
            "static-owner-turn-aware-route-plan-summary-turn-needed.json": ("turn-right", "turn-needed"),
            "static-owner-turn-aware-route-plan-summary-opposite-facing.json": ("turn-left", "opposite-facing"),
        }
        for filename, (first_action, magnitude) in expected.items():
            with self.subTest(filename=filename):
                summary = json.loads((testdata / filename).read_text(encoding="utf-8"))
                contract = validate_turn_aware_plan_contract(summary)
                self.assertEqual("passed", contract["status"])
                self.assertEqual([], contract["blockers"])
                self.assertEqual(first_action, contract["firstAction"])
                self.assertEqual(magnitude, contract["turnMagnitudeClass"])

    def test_validate_saved_plan_fixture_passes(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-turn-aware-route-plan-summary-turn-needed.json"
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                repo_root=None,
                output_root=tmp,
                validate_plan_summary_json=str(fixture),
            )

            summary = validate_saved_summary(args)

        self.assertEqual("passed", summary["status"])
        self.assertEqual("passed", summary["contract"]["status"])


if __name__ == "__main__":
    unittest.main()
