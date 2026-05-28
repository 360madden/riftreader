import argparse
import copy
import json
import unittest
from pathlib import Path

from scripts.static_owner_nav_route_run import summarize_route_run_steps, validate_args


def route_step_fixture() -> dict:
    fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-step-summary-progress.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


class StaticOwnerNavRouteRunTests(unittest.TestCase):
    def test_progress_blocks_when_max_steps_reached_before_arrival(self):
        step = route_step_fixture()

        result = summarize_route_run_steps([step], max_steps=1)

        self.assertEqual("blocked", result["status"])
        self.assertEqual("route-run-max-steps-reached-before-arrival", result["verdict"])
        self.assertIn("max-steps-reached-before-arrival", result["blockers"])
        self.assertFalse(result["arrived"])

    def test_arrived_step_passes(self):
        step = route_step_fixture()
        step["routeResult"]["routeStatus"] = "arrived"
        step["routeResult"]["stopReason"] = "within-arrival-radius"
        step["routeResult"]["finalPlanarDistance"] = 0.75

        result = summarize_route_run_steps([step], max_steps=3)

        self.assertEqual("passed", result["status"])
        self.assertEqual("route-run-arrived", result["verdict"])
        self.assertTrue(result["arrived"])
        self.assertEqual(1, result["arrivalStep"])

    def test_wrong_way_step_blocks(self):
        step = route_step_fixture()
        step["routeResult"]["routeStatus"] = "wrong-way"

        result = summarize_route_run_steps([step], max_steps=3)

        self.assertEqual("blocked", result["status"])
        self.assertEqual("route-run-blocked", result["verdict"])
        self.assertIn("step-1-contract-blocked", result["blockers"])
        self.assertIn("route-result-route-status-must-be-progress-or-arrived", result["blockers"])

    def test_dry_run_plan_passes_without_input(self):
        step = copy.deepcopy(route_step_fixture())
        step["verdict"] = "route-step-dry-run-plan-built"
        step["routeResult"] = {}
        step["safety"]["movementSent"] = False
        step["safety"]["inputSent"] = False

        result = summarize_route_run_steps([step], max_steps=3, dry_run=True)

        self.assertEqual("passed", result["status"])
        self.assertEqual("route-run-dry-run-plan-built", result["verdict"])
        self.assertFalse(result["movementSent"])
        self.assertFalse(result["inputSent"])

    def test_validate_args_requires_positive_max_steps(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=None,
            destination_z=2.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            arrival_radius=2.0,
            alignment_threshold_degrees=7.5,
            samples=3,
            interval_seconds=0.1,
            hold_milliseconds=250,
            settle_seconds=0.75,
            command_timeout_seconds=120.0,
            step_timeout_seconds=240.0,
            max_steps=0,
        )

        self.assertIn("max-steps-must-be-positive", validate_args(args))


if __name__ == "__main__":
    unittest.main()
