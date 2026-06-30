from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any

from scripts import navigation_schema_validate as schema_validator
from scripts.navigation_offline_simulator import (
    build_markdown,
    build_summary,
    simulate_route,
    validate_args,
    validate_simulation_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _args(tmp_path: Path, **overrides: Any) -> Namespace:
    data: dict[str, Any] = {
        "repo_root": str(REPO_ROOT),
        "output_root": str(tmp_path / "out"),
        "start_x": 0.0,
        "start_y": 0.0,
        "start_z": 0.0,
        "start_yaw_degrees": 0.0,
        "waypoints_json": None,
        "destination_id": "dest",
        "destination_label": "Destination",
        "destination_x": 5.0,
        "destination_y": None,
        "destination_z": 0.0,
        "arrival_radius": 1.0,
        "step_distance": 2.0,
        "turn_step_degrees": 30.0,
        "max_steps": 10,
        "alignment_threshold_degrees": 7.5,
        "minimum_progress_distance": 0.05,
        "wrong_way_tolerance_distance": 0.25,
        "stuck_after_step": None,
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


class NavigationOfflineSimulatorTests(unittest.TestCase):
    def test_aligned_direct_destination_arrives(self) -> None:
        result = simulate_route(
            start_pose={"x": 0.0, "y": 0.0, "z": 0.0, "yawDegrees": 0.0},
            waypoints=[{"id": "a", "label": "A", "x": 5.0, "y": 0.0, "z": 0.0, "arrivalRadius": 1.0}],
            step_distance=2.0,
            max_steps=5,
        )

        self.assertEqual("passed", result["status"])
        self.assertEqual("offline-simulation-route-complete", result["verdict"])
        self.assertTrue(result["arrived"])
        self.assertEqual(["a"], result["arrivedWaypointIds"])
        self.assertTrue(any(step["action"] == "forward" for step in result["steps"]))

    def test_turn_then_forward_to_destination(self) -> None:
        result = simulate_route(
            start_pose={"x": 0.0, "y": 0.0, "z": 0.0, "yawDegrees": 0.0},
            waypoints=[{"id": "north", "label": "North", "x": 0.0, "y": 0.0, "z": 4.0, "arrivalRadius": 1.0}],
            step_distance=2.0,
            turn_step_degrees=45.0,
            max_steps=10,
        )

        self.assertEqual("passed", result["status"])
        self.assertEqual(["turn-right", "turn-right"], [step["action"] for step in result["steps"][:2]])
        self.assertEqual("forward", result["steps"][2]["action"])
        self.assertTrue(result["arrived"])

    def test_start_inside_waypoint_records_arrived_id(self) -> None:
        result = simulate_route(
            start_pose={"x": 0.0, "y": 0.0, "z": 0.0, "yawDegrees": 0.0},
            waypoints=[{"id": "start", "label": "Start", "x": 0.0, "y": 0.0, "z": 0.0, "arrivalRadius": 1.0}],
            max_steps=5,
        )

        self.assertEqual("passed", result["status"])
        self.assertTrue(result["arrived"])
        self.assertEqual(0, result["stepsRun"])
        self.assertEqual(["start"], result["arrivedWaypointIds"])

    def test_completed_waypoint_stays_completed_after_leaving_radius(self) -> None:
        result = simulate_route(
            start_pose={"x": 0.0, "y": 0.0, "z": 0.0, "yawDegrees": 0.0},
            waypoints=[
                {"id": "first", "label": "First", "x": 2.0, "y": 0.0, "z": 0.0, "arrivalRadius": 1.0},
                {"id": "second", "label": "Second", "x": 8.0, "y": 0.0, "z": 0.0, "arrivalRadius": 1.0},
            ],
            step_distance=2.0,
            max_steps=5,
        )

        self.assertEqual("passed", result["status"])
        self.assertTrue(result["arrived"])
        self.assertEqual(["first", "second"], result["arrivedWaypointIds"])
        self.assertEqual(["first", "second"], sorted({step["activeWaypointId"] for step in result["steps"]}))

    def test_no_progress_blocks(self) -> None:
        result = simulate_route(
            start_pose={"x": 0.0, "y": 0.0, "z": 0.0, "yawDegrees": 0.0},
            waypoints=[{"id": "a", "label": "A", "x": 5.0, "y": 0.0, "z": 0.0, "arrivalRadius": 1.0}],
            step_distance=2.0,
            stuck_after_step=1,
            max_steps=5,
        )

        self.assertEqual("blocked", result["status"])
        self.assertEqual("offline-simulation-route-blocked", result["verdict"])
        self.assertIn("step-1-no-progress", result["blockers"])
        self.assertEqual("no-progress", result["lastRouteStatus"])

    def test_wrong_way_blocks_when_threshold_allows_bad_alignment(self) -> None:
        result = simulate_route(
            start_pose={"x": 0.0, "y": 0.0, "z": 0.0, "yawDegrees": 180.0},
            waypoints=[{"id": "a", "label": "A", "x": 5.0, "y": 0.0, "z": 0.0, "arrivalRadius": 1.0}],
            alignment_threshold_degrees=180.0,
            step_distance=1.0,
            max_steps=2,
        )

        self.assertEqual("blocked", result["status"])
        self.assertEqual("wrong-way", result["lastRouteStatus"])
        self.assertIn("step-1-wrong-way", result["blockers"])

    def test_validate_args_requires_destination_or_waypoints(self) -> None:
        args = _args(Path("."), destination_x=None, destination_z=None, waypoints_json=None)

        errors = validate_args(args)

        self.assertIn("destination-or-waypoints-json-required", errors)

    def test_build_summary_with_waypoints_json_is_offline_and_schema_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            waypoint_path = tmp_path / "waypoints.json"
            waypoint_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "waypoints": [
                            {"id": "a", "label": "A", "x": 4.0, "y": 0.0, "z": 0.0, "arrivalRadius": 1.0}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            summary = build_summary(_args(tmp_path, destination_x=None, destination_z=None, waypoints_json=str(waypoint_path)))

        self.assertEqual("passed", summary["status"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["safety"]["targetMemoryBytesRead"])
        self.assertTrue(summary["safety"]["offlineSimulationOnly"])
        contract = validate_simulation_contract(summary)
        self.assertEqual("passed", contract["status"])
        schema = schema_validator.load_json_object(schema_validator.schema_path(REPO_ROOT, "navigation-offline-simulation"))
        validation = schema_validator.validate_payload(summary, schema)
        self.assertEqual("passed", validation["status"])
        self.assertEqual([], validation["errors"])

    def test_markdown_mentions_offline_safety(self) -> None:
        summary = {
            "generatedAtUtc": "2026-06-29T00:00:00+00:00",
            "status": "passed",
            "verdict": "offline-simulation-route-complete",
            "simulation": {
                "stepsRun": 1,
                "arrived": True,
                "lastRouteStatus": "arrived",
                "finalPose": {"x": 1.0, "y": 0.0, "z": 0.0, "yawDegrees": 0.0},
                "steps": [
                    {
                        "stepNumber": 1,
                        "action": "forward",
                        "routeStatus": "arrived",
                        "activeWaypointId": "a",
                        "initialPlanarDistance": 2.0,
                        "finalPlanarDistance": 1.0,
                        "progressDistance": 1.0,
                        "initialYawDeltaDegrees": 0.0,
                    }
                ],
            },
            "artifacts": {"summaryJson": "summary.json", "runDirectory": "run"},
            "blockers": [],
            "warnings": [],
            "errors": [],
        }

        markdown = build_markdown(summary)

        self.assertIn("Navigation offline simulation", markdown)
        self.assertIn("No target memory read", markdown)


if __name__ == "__main__":
    unittest.main()
