import argparse
import json
import struct
import tempfile
import unittest
from pathlib import Path

from scripts.static_owner_facing_discovery import (
    build_yaw_transition_analysis,
    build_progress_analysis,
    compare_snapshots,
    load_waypoint_destination,
    nav_state_from_owner_window,
    navigation_target_from_state,
    normalize_degrees,
    resolve_navigation_target_request,
    run_plan,
    run_progress,
    validate_state_args,
)


def snapshot(label, yaw, scalar, coord_x=0.0):
    return {
        "status": "passed",
        "label": label,
        "owner": {"ownerAddress": "0x1000"},
        "coordinate": {"x": coord_x, "y": 0.0, "z": 0.0},
        "floatSamples": [
            {"offset": "0x10", "address": "0x1010", "value": scalar},
            {"offset": "0x320", "address": "0x1320", "value": coord_x},
        ],
        "vectorSamples": [
            {"offset": "0xD4", "address": "0x10D4", "length": 1.0, "yawDegrees": yaw, "pitchDegrees": 0.0},
        ],
        "relativeTargetSamples": [
            {
                "offset": "0x30C",
                "address": "0x130C",
                "targetCoordinate": {"x": coord_x + 10.0, "y": 0.0, "z": 0.0},
                "direction": {"x": 10.0, "y": 0.0, "z": 0.0},
                "planarDistance": 10.0,
                "yawDegrees": yaw,
                "pitchDegrees": 0.0,
            },
        ],
    }


class StaticOwnerFacingDiscoveryTests(unittest.TestCase):
    def test_nav_state_from_owner_window_computes_yaw_from_relative_target(self):
        data = bytearray(0x700)
        struct.pack_into("<fff", data, 0x320, 10.0, 2.0, 20.0)
        struct.pack_into("<fff", data, 0x30C, 20.0, 2.0, 20.0)

        state = nav_state_from_owner_window(bytes(data), owner_address=0x1000)

        self.assertEqual(state["positionOffset"], "0x320")
        self.assertEqual(state["facingTargetOffset"], "0x30C")
        self.assertAlmostEqual(state["coordinate"]["x"], 10.0)
        self.assertAlmostEqual(state["facingTargetCoordinate"]["x"], 20.0)
        self.assertAlmostEqual(state["facingVector"]["x"], 10.0)
        self.assertAlmostEqual(state["facingVector"]["z"], 0.0)
        self.assertAlmostEqual(state["yawDegrees"], 0.0)
        self.assertAlmostEqual(state["planarLookaheadDistance"], 10.0)

    def test_nav_state_from_owner_window_computes_z_axis_yaw(self):
        data = bytearray(0x700)
        struct.pack_into("<fff", data, 0x320, 10.0, 2.0, 20.0)
        struct.pack_into("<fff", data, 0x30C, 10.0, 2.0, 30.0)

        state = nav_state_from_owner_window(bytes(data), owner_address=0x1000)

        self.assertAlmostEqual(state["facingVector"]["x"], 0.0)
        self.assertAlmostEqual(state["facingVector"]["z"], 10.0)
        self.assertAlmostEqual(state["yawDegrees"], 90.0)
        self.assertAlmostEqual(state["planarLookaheadDistance"], 10.0)

    def test_normalize_degrees_short_delta(self):
        self.assertAlmostEqual(normalize_degrees(358.0), -2.0)
        self.assertAlmostEqual(normalize_degrees(-358.0), 2.0)

    def test_yaw_transition_analysis_uses_short_signed_delta_across_wrap(self):
        analysis = build_yaw_transition_analysis(
            [
                {"status": "passed", "sampleIndex": 0, "elapsedSeconds": 0.0, "yawDegrees": 179.0},
                {"status": "passed", "sampleIndex": 1, "elapsedSeconds": 0.5, "yawDegrees": -179.0},
            ]
        )

        self.assertEqual(len(analysis["yawTransitions"]), 1)
        transition = analysis["yawTransitions"][0]
        self.assertAlmostEqual(transition["signedYawDeltaDegrees"], 2.0)
        self.assertAlmostEqual(transition["absoluteYawDeltaDegrees"], 2.0)
        self.assertAlmostEqual(transition["yawSpeedDegreesPerSecond"], 4.0)
        self.assertAlmostEqual(analysis["maxAbsYawDeltaDegrees"], 2.0)
        self.assertAlmostEqual(analysis["maxAbsYawSpeedDegreesPerSecond"], 4.0)

    def test_navigation_target_from_state_builds_candidate_turn_analysis(self):
        state = {
            "coordinate": {"x": 0.0, "y": 5.0, "z": 0.0},
            "yawDegrees": 90.0,
        }

        target = navigation_target_from_state(
            state,
            destination_x=10.0,
            destination_y=None,
            destination_z=0.0,
            destination_label="east",
            arrival_radius=1.5,
            alignment_threshold_degrees=7.5,
        )

        self.assertEqual(target["status"], "turn-candidate")
        self.assertEqual(target["sourceKind"], "static-owner-relative-target-candidate-facing")
        self.assertTrue(target["candidateOnly"])
        self.assertFalse(target["actionableForMovement"])
        self.assertAlmostEqual(target["destination"]["y"], 5.0)
        self.assertAlmostEqual(target["planarDistance"], 10.0)
        self.assertAlmostEqual(target["destinationBearingDegrees"], 0.0)
        self.assertAlmostEqual(target["signedBearingDeltaDegrees"], -90.0)
        self.assertEqual(target["suggestedTurnDirection"], "left")
        self.assertFalse(target["withinArrivalRadius"])
        self.assertFalse(target["withinAlignmentThreshold"])

    def test_validate_state_args_requires_destination_x_and_z_together(self):
        args = argparse.Namespace(
            pid=1,
            hwnd="0x1",
            module_base="0x1000",
            owner_window_bytes=0x700,
            samples=1,
            interval_seconds=0.0,
            max_planar_jump_per_sample=25.0,
            max_sample_gap_seconds=2.0,
            max_stationary_planar_drift=0.5,
            min_target_distance=0.5,
            max_target_distance=100.0,
            destination_x=10.0,
            destination_y=None,
            destination_z=None,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            arrival_radius=2.0,
            alignment_threshold_degrees=7.5,
        )

        self.assertIn("destination-x-and-z-required-together", validate_state_args(args))

    def test_validate_state_args_rejects_mixed_direct_and_waypoint_destination(self):
        args = argparse.Namespace(
            pid=1,
            hwnd="0x1",
            module_base="0x1000",
            owner_window_bytes=0x700,
            samples=1,
            interval_seconds=0.0,
            max_planar_jump_per_sample=25.0,
            max_sample_gap_seconds=2.0,
            max_stationary_planar_drift=0.5,
            min_target_distance=0.5,
            max_target_distance=100.0,
            destination_x=10.0,
            destination_y=None,
            destination_z=20.0,
            destination_waypoint_json="scripts/navigation/waypoints.json",
            destination_waypoint_id="destination",
            arrival_radius=None,
            alignment_threshold_degrees=7.5,
        )

        self.assertIn("destination-waypoint-and-direct-coordinates-mutually-exclusive", validate_state_args(args))

    def test_load_waypoint_destination_extracts_target_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            waypoint_file = root / "waypoints.json"
            waypoint_file.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "waypoints": [
                            {"id": "start", "x": 1.0, "y": 2.0, "z": 3.0},
                            {"id": "dest", "label": "Destination", "x": 10.0, "y": 20.0, "z": 30.0, "arrivalRadius": 4.5},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            waypoint = load_waypoint_destination(root, "waypoints.json", "dest")

            self.assertEqual(str(waypoint_file), waypoint["sourceFile"])
            self.assertEqual("dest", waypoint["waypointId"])
            self.assertEqual("Destination", waypoint["label"])
            self.assertAlmostEqual(10.0, waypoint["x"])
            self.assertAlmostEqual(20.0, waypoint["y"])
            self.assertAlmostEqual(30.0, waypoint["z"])
            self.assertAlmostEqual(4.5, waypoint["arrivalRadius"])

    def test_resolve_navigation_target_request_uses_waypoint_arrival_radius(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            waypoint_file = root / "waypoints.json"
            waypoint_file.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "waypoints": [
                            {"id": "dest", "label": "Destination", "x": 10.0, "y": 20.0, "z": 30.0, "arrivalRadius": 4.5},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                destination_waypoint_json="waypoints.json",
                destination_waypoint_id="dest",
                destination_label=None,
                destination_x=None,
                destination_y=None,
                destination_z=None,
                arrival_radius=None,
                alignment_threshold_degrees=6.0,
            )

            request = resolve_navigation_target_request(args, root)

            self.assertIsNotNone(request)
            self.assertEqual("waypoint-json", request["sourceKind"])
            self.assertEqual("dest", request["waypointId"])
            self.assertEqual("Destination", request["destinationLabel"])
            self.assertAlmostEqual(4.5, request["arrivalRadius"])
            self.assertAlmostEqual(6.0, request["alignmentThresholdDegrees"])

    def test_run_plan_builds_dry_run_target_from_saved_state_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_summary = root / "state-summary.json"
            state_summary.write_text(
                json.dumps(
                    {
                        "kind": "static-owner-nav-state-readback",
                        "status": "passed",
                        "verdict": "position-and-facing-nav-state-readback-passed",
                        "generatedAtUtc": "2026-05-28T00:00:00+00:00",
                        "latestState": {
                            "coordinate": {"x": 0.0, "y": 5.0, "z": 0.0},
                            "yawDegrees": 90.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                repo_root=str(root),
                output_root=str(root / "captures"),
                state_summary_json=str(state_summary),
                destination_x=10.0,
                destination_y=None,
                destination_z=0.0,
                destination_label="east",
                destination_waypoint_json=None,
                destination_waypoint_id=None,
                arrival_radius=2.0,
                alignment_threshold_degrees=7.5,
            )

            plan = run_plan(args)

            self.assertEqual("passed", plan["status"])
            self.assertEqual("static-owner-nav-target-dry-run-plan-built", plan["verdict"])
            self.assertTrue(plan["safety"]["dryRunOnly"])
            self.assertFalse(plan["safety"]["movementSent"])
            self.assertFalse(plan["navigationTarget"]["actionableForMovement"])
            self.assertAlmostEqual(-90.0, plan["navigationTarget"]["signedBearingDeltaDegrees"])
            self.assertEqual("left", plan["navigationTarget"]["suggestedTurnDirection"])

    def test_run_plan_reuses_saved_navigation_target_request_when_no_new_target_is_supplied(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_summary = root / "state-summary.json"
            state_summary.write_text(
                json.dumps(
                    {
                        "kind": "static-owner-nav-state-readback",
                        "status": "passed",
                        "latestState": {
                            "coordinate": {"x": 0.0, "y": 0.0, "z": 0.0},
                            "yawDegrees": 0.0,
                        },
                        "navigationTargetRequest": {
                            "sourceKind": "direct-coordinates",
                            "destinationLabel": "north",
                            "destinationX": 0.0,
                            "destinationY": None,
                            "destinationZ": 10.0,
                            "arrivalRadius": 2.0,
                            "alignmentThresholdDegrees": 7.5,
                        },
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                repo_root=str(root),
                output_root=str(root / "captures"),
                state_summary_json=str(state_summary),
                destination_x=None,
                destination_y=None,
                destination_z=None,
                destination_label=None,
                destination_waypoint_json=None,
                destination_waypoint_id=None,
                arrival_radius=None,
                alignment_threshold_degrees=7.5,
            )

            plan = run_plan(args)

            self.assertEqual("passed", plan["status"])
            self.assertEqual("north", plan["navigationTarget"]["destination"]["label"])
            self.assertAlmostEqual(90.0, plan["navigationTarget"]["destinationBearingDegrees"])
            self.assertEqual("right", plan["navigationTarget"]["suggestedTurnDirection"])

    def test_progress_analysis_classifies_arrival_progress_wrong_way_and_overshoot(self):
        arrived = build_progress_analysis(
            [
                {"sampleIndex": 0, "planarDistance": 10.0, "withinArrivalRadius": False},
                {"sampleIndex": 1, "planarDistance": 1.0, "withinArrivalRadius": True},
            ],
            minimum_progress_distance=0.35,
            wrong_way_tolerance_distance=0.75,
            arrival_radius=2.0,
        )
        self.assertEqual("arrived", arrived["status"])
        self.assertEqual("within-arrival-radius", arrived["stopReason"])

        progress = build_progress_analysis(
            [
                {"sampleIndex": 0, "planarDistance": 10.0, "withinArrivalRadius": False},
                {"sampleIndex": 1, "planarDistance": 9.0, "withinArrivalRadius": False},
            ],
            minimum_progress_distance=0.35,
            wrong_way_tolerance_distance=0.75,
            arrival_radius=2.0,
        )
        self.assertEqual("progress", progress["status"])

        wrong_way = build_progress_analysis(
            [
                {"sampleIndex": 0, "planarDistance": 10.0, "withinArrivalRadius": False},
                {"sampleIndex": 1, "planarDistance": 11.0, "withinArrivalRadius": False},
            ],
            minimum_progress_distance=0.35,
            wrong_way_tolerance_distance=0.75,
            arrival_radius=2.0,
        )
        self.assertEqual("wrong-way", wrong_way["status"])

        overshot = build_progress_analysis(
            [
                {"sampleIndex": 0, "planarDistance": 10.0, "withinArrivalRadius": False},
                {"sampleIndex": 1, "planarDistance": 1.0, "withinArrivalRadius": True},
                {"sampleIndex": 2, "planarDistance": 4.0, "withinArrivalRadius": False},
            ],
            minimum_progress_distance=0.35,
            wrong_way_tolerance_distance=0.75,
            arrival_radius=2.0,
        )
        self.assertEqual("overshot", overshot["status"])
        self.assertFalse(overshot["actionableForMovement"])

    def test_run_progress_builds_dry_run_progress_from_saved_plan_summaries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "plan-1.json"
            second = root / "plan-2.json"
            for path, distance in ((first, 10.0), (second, 9.0)):
                path.write_text(
                    json.dumps(
                        {
                            "kind": "static-owner-nav-target-dry-run-plan",
                            "status": "passed",
                            "verdict": "static-owner-nav-target-dry-run-plan-built",
                            "generatedAtUtc": "2026-05-28T00:00:00+00:00",
                            "navigationTarget": {
                                "planarDistance": distance,
                                "arrivalRadius": 2.0,
                                "withinArrivalRadius": False,
                                "suggestedTurnDirection": "aligned",
                                "destination": {"label": "dest", "x": 10.0, "y": 0.0, "z": 0.0},
                            },
                        }
                    ),
                    encoding="utf-8",
                )
            args = argparse.Namespace(
                repo_root=str(root),
                output_root=str(root / "captures"),
                plan_summary_json=[str(first), str(second)],
                minimum_progress_distance=0.35,
                wrong_way_tolerance_distance=0.75,
                arrival_radius=None,
            )

            progress = run_progress(args)

            self.assertEqual("passed", progress["status"])
            self.assertEqual("static-owner-nav-progress-dry-run-built", progress["verdict"])
            self.assertTrue(progress["safety"]["dryRunOnly"])
            self.assertFalse(progress["safety"]["movementSent"])
            self.assertEqual("progress", progress["analysis"]["status"])
            self.assertAlmostEqual(1.0, progress["analysis"]["totalProgressDistance"])

    def test_compare_scores_vector_and_scalar_candidates(self):
        result = compare_snapshots(
            [snapshot("baseline", 10.0, 1.0), snapshot("after-right", 25.0, 1.5), snapshot("after-left", 5.0, 1.1)],
            min_scalar_delta=0.001,
            min_yaw_delta_degrees=1.0,
            max_coordinate_planar_drift=0.5,
        )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["vectorCandidateCount"], 1)
        self.assertEqual(result["vectorCandidates"][0]["offset"], "0xD4")
        self.assertEqual(result["relativeTargetCandidateCount"], 1)
        self.assertEqual(result["relativeTargetCandidates"][0]["offset"], "0x30C")
        self.assertEqual(result["scalarCandidateCount"], 1)
        self.assertEqual(result["scalarCandidates"][0]["offset"], "0x10")

    def test_compare_warns_on_coordinate_drift(self):
        result = compare_snapshots(
            [snapshot("baseline", 10.0, 1.0, 0.0), snapshot("after-right", 20.0, 1.2, 2.0)],
            min_scalar_delta=0.001,
            min_yaw_delta_degrees=1.0,
            max_coordinate_planar_drift=0.5,
        )

        self.assertTrue(any(item.startswith("coordinate-drift-during-facing-capture") for item in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
