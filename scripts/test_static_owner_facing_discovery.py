import argparse
import json
import struct
import tempfile
import unittest
from pathlib import Path

import math

from scripts.static_owner_facing_discovery import (
    DEFAULT_TURN_RATE_THRESHOLD,
    build_yaw_transition_analysis,
    build_progress_analysis,
    classify_turn_direction_from_rate,
    compare_snapshots,
    finite_float,
    load_waypoint_destination,
    nav_state_from_owner_window,
    navigation_target_from_state,
    normalize_degrees,
    resolve_navigation_target_request,
    run_plan,
    run_progress,
    run_route,
    run_validate_route,
    unpack_float,
    validate_route_summary_contract,
    validate_state_args,
    validate_route_args,
    vector_from_data,
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

    def test_run_route_builds_dry_run_route_from_saved_state_summaries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "state-1.json"
            second = root / "state-2.json"
            for path, x in ((first, 0.0), (second, 1.0)):
                path.write_text(
                    json.dumps(
                        {
                            "kind": "static-owner-nav-state-readback",
                            "status": "passed",
                            "verdict": "position-and-facing-nav-state-readback-passed",
                            "generatedAtUtc": "2026-05-28T00:00:00+00:00",
                            "latestState": {
                                "coordinate": {"x": x, "y": 0.0, "z": 0.0},
                                "yawDegrees": 0.0,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
            args = argparse.Namespace(
                repo_root=str(root),
                output_root=str(root / "captures"),
                state_summary_json=[str(first), str(second)],
                destination_x=10.0,
                destination_y=None,
                destination_z=0.0,
                destination_label="east",
                destination_waypoint_json=None,
                destination_waypoint_id=None,
                arrival_radius=2.0,
                alignment_threshold_degrees=7.5,
                minimum_progress_distance=0.35,
                wrong_way_tolerance_distance=0.75,
            )

            route = run_route(args)

            self.assertEqual("passed", route["status"])
            self.assertEqual("static-owner-nav-route-dry-run-built", route["verdict"])
            self.assertTrue(route["safety"]["dryRunOnly"])
            self.assertFalse(route["safety"]["movementSent"])
            self.assertEqual("progress", route["analysis"]["status"])
            self.assertAlmostEqual(1.0, route["analysis"]["totalProgressDistance"])
            self.assertEqual(2, len(route["routePlanTargets"]))
            self.assertFalse(route["routePlanTargets"][0]["navigationTarget"]["actionableForMovement"])
            self.assertEqual("continue-aligned-candidate", route["controllerRecommendation"]["recommendedAction"])
            self.assertFalse(route["controllerRecommendation"]["movementPermission"])
            self.assertFalse(route["controllerRecommendation"]["actionableForMovement"])

    def test_run_route_controller_recommendation_stops_on_wrong_way(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "state-1.json"
            second = root / "state-2.json"
            for path, x in ((first, 0.0), (second, -1.0)):
                path.write_text(
                    json.dumps(
                        {
                            "kind": "static-owner-nav-state-readback",
                            "status": "passed",
                            "latestState": {
                                "coordinate": {"x": x, "y": 0.0, "z": 0.0},
                                "yawDegrees": 180.0,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
            args = argparse.Namespace(
                repo_root=str(root),
                output_root=str(root / "captures"),
                state_summary_json=[str(first), str(second)],
                destination_x=10.0,
                destination_y=None,
                destination_z=0.0,
                destination_label="east",
                destination_waypoint_json=None,
                destination_waypoint_id=None,
                arrival_radius=2.0,
                alignment_threshold_degrees=7.5,
                minimum_progress_distance=0.35,
                wrong_way_tolerance_distance=0.75,
            )

            route = run_route(args)

            self.assertEqual("passed", route["status"])
            self.assertEqual("wrong-way", route["analysis"]["status"])
            self.assertEqual("stop-wrong-way", route["controllerRecommendation"]["recommendedAction"])
            self.assertEqual("stop", route["controllerRecommendation"]["controlIntent"])
            self.assertTrue(route["controllerRecommendation"]["candidateOnly"])
            self.assertFalse(route["controllerRecommendation"]["movementPermission"])

    def test_route_arg_validation_requires_two_state_summaries(self):
        args = argparse.Namespace(
            state_summary_json=["only-one.json"],
            destination_x=10.0,
            destination_y=None,
            destination_z=0.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            arrival_radius=2.0,
            alignment_threshold_degrees=7.5,
            minimum_progress_distance=0.35,
            wrong_way_tolerance_distance=0.75,
        )

        errors = validate_route_args(args)

        self.assertIn("at-least-two-state-summaries-required", errors)

    def test_route_contract_validation_passes_safe_route_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "state-1.json"
            second = root / "state-2.json"
            for path, x in ((first, 0.0), (second, 1.0)):
                path.write_text(
                    json.dumps(
                        {
                            "kind": "static-owner-nav-state-readback",
                            "status": "passed",
                            "latestState": {
                                "coordinate": {"x": x, "y": 0.0, "z": 0.0},
                                "yawDegrees": 0.0,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
            route_args = argparse.Namespace(
                repo_root=str(root),
                output_root=str(root / "captures"),
                state_summary_json=[str(first), str(second)],
                destination_x=10.0,
                destination_y=None,
                destination_z=0.0,
                destination_label="east",
                destination_waypoint_json=None,
                destination_waypoint_id=None,
                arrival_radius=2.0,
                alignment_threshold_degrees=7.5,
                minimum_progress_distance=0.35,
                wrong_way_tolerance_distance=0.75,
            )
            route = run_route(route_args)
            route_summary = root / "route-summary.json"
            route_summary.write_text(json.dumps(route), encoding="utf-8")
            validate_args = argparse.Namespace(
                repo_root=str(root),
                output_root=str(root / "captures"),
                route_summary_json=str(route_summary),
            )

            validation = run_validate_route(validate_args)

            self.assertEqual("passed", validation["status"])
            self.assertEqual("static-owner-nav-route-contract-passed", validation["verdict"])
            self.assertEqual([], validation["blockers"])
            self.assertFalse(validation["contract"]["movementPermission"])
            self.assertEqual(2, validation["contract"]["checkedRouteTargetCount"])

    def test_route_contract_validation_blocks_movement_permission(self):
        route = {
            "kind": "static-owner-nav-route-dry-run",
            "status": "passed",
            "routePlanTargets": [
                {
                    "navigationTarget": {
                        "candidateOnly": True,
                        "actionableForMovement": False,
                        "planarDistance": 10.0,
                    }
                },
                {
                    "navigationTarget": {
                        "candidateOnly": True,
                        "actionableForMovement": False,
                        "planarDistance": 9.0,
                    }
                },
            ],
            "analysis": {
                "status": "progress",
                "sampleCount": 2,
                "candidateOnly": True,
                "actionableForMovement": False,
            },
            "controllerRecommendation": {
                "recommendedAction": "continue-aligned-candidate",
                "controlIntent": "continue",
                "candidateOnly": True,
                "dryRunOnly": True,
                "actionableForMovement": False,
                "movementPermission": True,
                "navigationControl": False,
                "requiresFreshPreflightBeforeLiveUse": True,
            },
            "safety": {
                "movementSent": False,
                "inputSent": False,
                "reloaduiSent": False,
                "screenshotKeySent": False,
                "x64dbgAttach": False,
                "providerWrites": False,
                "navigationControl": False,
                "noCheatEngine": True,
                "dryRunOnly": True,
                "facingPromotion": False,
            },
        }

        contract = validate_route_summary_contract(route)

        self.assertEqual("blocked", contract["status"])
        self.assertIn("controller-movement-permission-must-be-false", contract["blockers"])

    def test_checked_in_route_contract_fixture_passes(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-summary-safe.json"
        route = json.loads(fixture.read_text(encoding="utf-8"))

        contract = validate_route_summary_contract(route)

        self.assertEqual("passed", contract["status"])
        self.assertEqual([], contract["blockers"])
        self.assertEqual("continue-aligned-candidate", contract["controllerRecommendedAction"])
        self.assertFalse(contract["movementPermission"])
        self.assertEqual(2, contract["checkedRouteTargetCount"])

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


class FiniteFloatTests(unittest.TestCase):
    """Test the finite_float filter."""

    def test_finite_numbers_return_true(self) -> None:
        self.assertTrue(finite_float(0.0))
        self.assertTrue(finite_float(1.0))
        self.assertTrue(finite_float(-1.0))
        self.assertTrue(finite_float(3.14159))
        self.assertTrue(finite_float(999_999.999))

    def test_infinity_returns_false(self) -> None:
        self.assertFalse(finite_float(float("inf")))
        self.assertFalse(finite_float(float("-inf")))

    def test_nan_returns_false(self) -> None:
        self.assertFalse(finite_float(float("nan")))

    def test_huge_values_outside_bound_return_false(self) -> None:
        self.assertFalse(finite_float(1_000_001.0))
        self.assertFalse(finite_float(-1_000_001.0))

    def test_boundary_just_under_1m(self) -> None:
        self.assertTrue(finite_float(999_999.999))
        self.assertTrue(finite_float(-999_999.999))

    def test_exactly_1m_returns_false(self) -> None:
        self.assertFalse(finite_float(1_000_000.0))
        self.assertFalse(finite_float(-1_000_000.0))


class ClassifyTurnDirectionFromRateTests(unittest.TestCase):
    """Test the turn-direction classifier with 0x304 turn-rate float."""

    def test_none_rate_returns_unknown(self) -> None:
        result = classify_turn_direction_from_rate(None)
        self.assertEqual(result["direction"], "unknown")
        self.assertIsNone(result["rate"])
        self.assertFalse(result["turning"])

    def test_infinity_returns_unknown(self) -> None:
        result = classify_turn_direction_from_rate(float("inf"))
        self.assertEqual(result["direction"], "unknown")
        self.assertFalse(result["turning"])

    def test_nan_returns_unknown(self) -> None:
        result = classify_turn_direction_from_rate(float("nan"))
        self.assertEqual(result["direction"], "unknown")
        self.assertFalse(result["turning"])

    def test_negative_infinity_returns_unknown(self) -> None:
        result = classify_turn_direction_from_rate(float("-inf"))
        self.assertEqual(result["direction"], "unknown")
        self.assertFalse(result["turning"])

    # --- Stationary (within ±threshold) ---

    def test_zero_rate_is_stationary(self) -> None:
        result = classify_turn_direction_from_rate(0.0)
        self.assertEqual(result["direction"], "stationary")
        self.assertEqual(result["rate"], 0.0)
        self.assertFalse(result["turning"])

    def test_small_positive_within_threshold_is_stationary(self) -> None:
        result = classify_turn_direction_from_rate(0.2)
        self.assertEqual(result["direction"], "stationary")
        self.assertFalse(result["turning"])

    def test_small_negative_within_threshold_is_stationary(self) -> None:
        result = classify_turn_direction_from_rate(-0.2)
        self.assertEqual(result["direction"], "stationary")
        self.assertFalse(result["turning"])

    def test_exactly_at_positive_threshold_is_stationary(self) -> None:
        # threshold is 0.35, rate > threshold → left (strictly greater)
        result = classify_turn_direction_from_rate(0.35)
        self.assertEqual(result["direction"], "stationary")
        self.assertFalse(result["turning"])

    def test_exactly_at_negative_threshold_is_stationary(self) -> None:
        result = classify_turn_direction_from_rate(-0.35)
        self.assertEqual(result["direction"], "stationary")
        self.assertFalse(result["turning"])

    def test_just_above_positive_threshold_is_left(self) -> None:
        result = classify_turn_direction_from_rate(0.351)
        self.assertEqual(result["direction"], "left")
        self.assertTrue(result["turning"])

    def test_just_below_negative_threshold_is_right(self) -> None:
        result = classify_turn_direction_from_rate(-0.351)
        self.assertEqual(result["direction"], "right")
        self.assertTrue(result["turning"])

    # --- Left turns ---

    def test_large_positive_rate_is_left(self) -> None:
        result = classify_turn_direction_from_rate(5.0)
        self.assertEqual(result["direction"], "left")
        self.assertTrue(result["turning"])

    def test_very_large_positive_rate_is_left(self) -> None:
        result = classify_turn_direction_from_rate(100.0)
        self.assertEqual(result["direction"], "left")
        self.assertTrue(result["turning"])

    def test_huge_positive_rate_is_left(self) -> None:
        result = classify_turn_direction_from_rate(999_999.0)
        self.assertEqual(result["direction"], "left")
        self.assertTrue(result["turning"])
        self.assertEqual(result["rate"], 999_999.0)

    # --- Right turns ---

    def test_large_negative_rate_is_right(self) -> None:
        result = classify_turn_direction_from_rate(-5.0)
        self.assertEqual(result["direction"], "right")
        self.assertTrue(result["turning"])

    def test_very_large_negative_rate_is_right(self) -> None:
        result = classify_turn_direction_from_rate(-100.0)
        self.assertEqual(result["direction"], "right")
        self.assertTrue(result["turning"])

    def test_huge_negative_rate_is_right(self) -> None:
        result = classify_turn_direction_from_rate(-999_999.0)
        self.assertEqual(result["direction"], "right")
        self.assertTrue(result["turning"])
        self.assertEqual(result["rate"], -999_999.0)

    # --- Four-pose triangulation regression (from production evidence) ---

    def test_baseline_stationary_0_247(self) -> None:
        """Baseline (no input): 0.247 → within default 0.35 threshold → stationary."""
        result = classify_turn_direction_from_rate(0.247)
        self.assertEqual(result["direction"], "stationary")
        self.assertFalse(result["turning"])

    def test_turn_right_2_minus_1_18(self) -> None:
        """Turn-right-2 (D key 500ms): -1.18 → below -0.35 → right."""
        result = classify_turn_direction_from_rate(-1.18)
        self.assertEqual(result["direction"], "right")
        self.assertTrue(result["turning"])

    def test_turn_left_3_plus_2_77(self) -> None:
        """Turn-left-3 (A key 800ms): +2.77 → above +0.35 → left."""
        result = classify_turn_direction_from_rate(2.77)
        self.assertEqual(result["direction"], "left")
        self.assertTrue(result["turning"])

    def test_turn_left_symmetric_plus_0_61(self) -> None:
        """Turn-left-symmetric (A key 1000ms, settling): +0.61 → above +0.35 → left."""
        result = classify_turn_direction_from_rate(0.61)
        self.assertEqual(result["direction"], "left")
        self.assertTrue(result["turning"])

    # --- Rate preserved in output ---

    def test_rate_preserved_in_output(self) -> None:
        result = classify_turn_direction_from_rate(-1.18)
        self.assertAlmostEqual(result["rate"], -1.18)

        result = classify_turn_direction_from_rate(2.77)
        self.assertAlmostEqual(result["rate"], 2.77)

    # --- Custom threshold ---

    def test_custom_threshold_stationary(self) -> None:
        """With a larger threshold, a modest rate can be stationary."""
        result = classify_turn_direction_from_rate(2.0, threshold=3.0)
        self.assertEqual(result["direction"], "stationary")
        self.assertFalse(result["turning"])

    def test_custom_threshold_above(self) -> None:
        result = classify_turn_direction_from_rate(1.5, threshold=1.0)
        self.assertEqual(result["direction"], "left")
        self.assertTrue(result["turning"])

    def test_custom_threshold_below(self) -> None:
        result = classify_turn_direction_from_rate(-1.5, threshold=1.0)
        self.assertEqual(result["direction"], "right")
        self.assertTrue(result["turning"])

    def test_zero_threshold_all_nonzero_is_turning(self) -> None:
        """With threshold=0, any non-zero rate is turning."""
        result = classify_turn_direction_from_rate(0.01, threshold=0.0)
        self.assertEqual(result["direction"], "left")
        self.assertTrue(result["turning"])

        result = classify_turn_direction_from_rate(-0.01, threshold=0.0)
        self.assertEqual(result["direction"], "right")
        self.assertTrue(result["turning"])

    # --- Default threshold constant ---

    def test_default_threshold_is_0_35(self) -> None:
        self.assertAlmostEqual(DEFAULT_TURN_RATE_THRESHOLD, 0.35)


class UnpackFloatTests(unittest.TestCase):
    """Test the memory-data unpacker."""

    def test_unpack_valid_float(self) -> None:
        data = struct.pack("<f", 3.14159)
        result = unpack_float(data, 0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 3.14159, places=5)

    def test_unpack_negative_float(self) -> None:
        data = struct.pack("<f", -42.5)
        result = unpack_float(data, 0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, -42.5)

    def test_unpack_at_offset(self) -> None:
        data = struct.pack("<ff", 1.0, 2.0)
        result = unpack_float(data, 4)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 2.0)

    def test_unpack_past_end_returns_none(self) -> None:
        data = b"\x00" * 2
        result = unpack_float(data, 0)
        self.assertIsNone(result)

    def test_unpack_nan_returns_none(self) -> None:
        data = struct.pack("<f", float("nan"))
        result = unpack_float(data, 0)
        self.assertIsNone(result)

    def test_unpack_inf_returns_none(self) -> None:
        data = struct.pack("<f", float("inf"))
        result = unpack_float(data, 0)
        self.assertIsNone(result)


class VectorFromDataTests(unittest.TestCase):
    """Test the vector/unpacker."""

    def test_valid_unit_vector(self) -> None:
        data = struct.pack("<fff", 1.0, 0.0, 0.0)
        result = vector_from_data(data, 0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["x"], 1.0)
        self.assertAlmostEqual(result["y"], 0.0)
        self.assertAlmostEqual(result["z"], 0.0)
        self.assertAlmostEqual(result["length"], 1.0)
        self.assertAlmostEqual(result["yawDegrees"], 0.0)
        self.assertAlmostEqual(result["pitchDegrees"], 0.0)

    def test_z_axis_vector(self) -> None:
        data = struct.pack("<fff", 0.0, 0.0, 1.0)
        result = vector_from_data(data, 0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["length"], 1.0)
        self.assertAlmostEqual(result["yawDegrees"], 90.0)

    def test_diagonal_vector(self) -> None:
        data = struct.pack("<fff", 1.0, 0.0, 1.0)
        result = vector_from_data(data, 0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["x"], 1.0)
        self.assertAlmostEqual(result["z"], 1.0)
        self.assertAlmostEqual(result["length"], math.sqrt(2))
        self.assertAlmostEqual(result["yawDegrees"], 45.0)

    def test_vector_with_pitch(self) -> None:
        data = struct.pack("<fff", 1.0, 1.0, 0.0)
        result = vector_from_data(data, 0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["length"], math.sqrt(2))
        self.assertAlmostEqual(result["pitchDegrees"], 45.0, places=5)
        self.assertAlmostEqual(result["yawDegrees"], 0.0)

    def test_zero_vector_returns_none(self) -> None:
        data = struct.pack("<fff", 0.0, 0.0, 0.0)
        result = vector_from_data(data, 0)
        self.assertIsNone(result)

    def test_nan_in_vector_returns_none(self) -> None:
        data = struct.pack("<fff", float("nan"), 0.0, 1.0)
        result = vector_from_data(data, 0)
        self.assertIsNone(result)

    def test_inf_in_vector_returns_none(self) -> None:
        data = struct.pack("<fff", float("inf"), 0.0, 1.0)
        result = vector_from_data(data, 0)
        self.assertIsNone(result)

    def test_negative_coordinates_vector(self) -> None:
        """All-negative vector should still have positive length."""
        data = struct.pack("<fff", -1.0, 0.0, 0.0)
        result = vector_from_data(data, 0)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["length"], 1.0)
        self.assertAlmostEqual(result["yawDegrees"], 180.0)

    def test_offset_into_buffer(self) -> None:
        data = struct.pack("<ffffff", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        result = vector_from_data(data, 12)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["x"], 1.0)
        self.assertAlmostEqual(result["length"], 1.0)

    def test_truncated_buffer_returns_none(self) -> None:
        data = b"\x00" * 8
        result = vector_from_data(data, 0)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
