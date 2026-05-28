import argparse
import json
import unittest
from pathlib import Path

from scripts.static_owner_nav_route_step import classify_initial_step, classify_route_result, validate_args, validate_route_step_summary_contract


class StaticOwnerNavRouteStepTests(unittest.TestCase):
    def test_initial_step_allows_aligned_forward(self):
        decision = classify_initial_step(
            {
                "navigationTarget": {
                    "withinArrivalRadius": False,
                    "suggestedTurnDirection": "aligned",
                    "signedBearingDeltaDegrees": 1.0,
                    "absoluteBearingDeltaDegrees": 1.0,
                    "planarDistance": 10.0,
                }
            }
        )

        self.assertEqual("passed", decision["status"])
        self.assertTrue(decision["movementRequired"])
        self.assertEqual("forward", decision["controlIntent"])

    def test_initial_step_blocks_candidate_turn(self):
        decision = classify_initial_step(
            {
                "navigationTarget": {
                    "withinArrivalRadius": False,
                    "suggestedTurnDirection": "left",
                    "signedBearingDeltaDegrees": -45.0,
                    "absoluteBearingDeltaDegrees": 45.0,
                    "planarDistance": 10.0,
                }
            }
        )

        self.assertEqual("blocked", decision["status"])
        self.assertFalse(decision["movementRequired"])
        self.assertEqual("initial-bearing-not-aligned:left", decision["reason"])

    def test_initial_step_stops_when_already_arrived(self):
        decision = classify_initial_step(
            {
                "navigationTarget": {
                    "withinArrivalRadius": True,
                    "suggestedTurnDirection": "aligned",
                    "planarDistance": 1.0,
                }
            }
        )

        self.assertEqual("passed", decision["status"])
        self.assertFalse(decision["movementRequired"])
        self.assertEqual("stop", decision["controlIntent"])

    def test_route_result_passes_progress_with_contract(self):
        result = classify_route_result(
            {
                "analysis": {
                    "status": "progress",
                    "stopReason": "distance-decreased",
                    "totalProgressDistance": 1.0,
                    "initialPlanarDistance": 10.0,
                    "finalPlanarDistance": 9.0,
                },
                "controllerRecommendation": {
                    "recommendedAction": "continue-aligned-candidate",
                    "controlIntent": "continue",
                },
            },
            {
                "status": "passed",
                "contract": {
                    "movementPermission": False,
                },
            },
        )

        self.assertEqual("passed", result["status"])
        self.assertEqual([], result["blockers"])
        self.assertEqual("progress", result["routeStatus"])

    def test_route_result_blocks_wrong_way_even_with_contract(self):
        result = classify_route_result(
            {
                "analysis": {
                    "status": "wrong-way",
                    "stopReason": "distance-increased-beyond-tolerance",
                },
                "controllerRecommendation": {
                    "recommendedAction": "stop-wrong-way",
                    "controlIntent": "stop",
                },
            },
            {"status": "passed", "contract": {"movementPermission": False}},
        )

        self.assertEqual("blocked", result["status"])
        self.assertIn("route-step-wrong-way", result["blockers"])

    def test_validate_args_requires_destination(self):
        args = argparse.Namespace(
            destination_x=None,
            destination_y=None,
            destination_z=None,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            arrival_radius=2.0,
            alignment_threshold_degrees=7.5,
            samples=3,
            interval_seconds=0.1,
            hold_milliseconds=250,
            settle_seconds=0.75,
            command_timeout_seconds=120.0,
        )

        self.assertIn("destination-x-and-z-required", validate_args(args))

    def test_checked_in_route_step_fixture_passes_contract(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-step-summary-progress.json"
        summary = json.loads(fixture.read_text(encoding="utf-8"))

        contract = validate_route_step_summary_contract(summary)

        self.assertEqual("passed", contract["status"])
        self.assertEqual([], contract["blockers"])
        self.assertEqual("progress", contract["routeStatus"])
        self.assertTrue(contract["movementSent"])
        self.assertTrue(contract["inputSent"])

    def test_route_step_contract_blocks_wrong_way(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-step-summary-progress.json"
        summary = json.loads(fixture.read_text(encoding="utf-8"))
        summary["routeResult"]["routeStatus"] = "wrong-way"

        contract = validate_route_step_summary_contract(summary)

        self.assertEqual("blocked", contract["status"])
        self.assertIn("route-result-route-status-must-be-progress-or-arrived", contract["blockers"])


if __name__ == "__main__":
    unittest.main()
