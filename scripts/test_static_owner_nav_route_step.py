from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from scripts.static_owner_nav_route_step import (
    build_markdown,
    classify_initial_step,
    classify_route_result,
    compact,
    clear_ui_focus_command,
    destination_args,
    repo_root,
    route_command,
    send_key_command,
    state_command,
    validate_args,
    validate_route_command,
    validate_route_step_summary_contract,
)
from scripts.workflow_common import full_summary_from_compact


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

    # ------------------------------------------------------------------ #
    # Expanded classify_initial_step coverage
    # ------------------------------------------------------------------ #

    def test_initial_step_blocks_missing_navigation_target(self):
        decision = classify_initial_step({})
        self.assertEqual("blocked", decision["status"])
        self.assertEqual("pre-state-navigation-target-missing", decision["reason"])
        self.assertFalse(decision["movementRequired"])

    def test_initial_step_blocks_unknown_suggested_turn(self):
        decision = classify_initial_step(
            {
                "navigationTarget": {
                    "withinArrivalRadius": False,
                    "suggestedTurnDirection": "",
                }
            }
        )
        self.assertEqual("blocked", decision["status"])
        self.assertEqual("initial-bearing-not-aligned:unknown", decision["reason"])

    # ------------------------------------------------------------------ #
    # Expanded classify_route_result coverage
    # ------------------------------------------------------------------ #

    def test_route_result_blocks_no_progress(self):
        result = classify_route_result(
            {"analysis": {"status": "no-progress"}},
            {"status": "passed", "contract": {"movementPermission": False}},
        )
        self.assertEqual("blocked", result["status"])
        self.assertIn("route-step-no-progress:minimum-progress-not-met", result["blockers"])

    def test_route_result_blocks_overshot(self):
        result = classify_route_result(
            {"analysis": {"status": "overshot"}},
            {"status": "passed"},
        )
        self.assertEqual("blocked", result["status"])
        self.assertIn("route-step-overshot", result["blockers"])

    def test_route_result_blocks_unrecognized_status(self):
        result = classify_route_result(
            {"analysis": {"status": "zigzag"}},
            {"status": "passed"},
        )
        self.assertEqual("blocked", result["status"])
        self.assertIn("route-step-status-unrecognized:zigzag", result["blockers"])

    def test_route_result_blocks_contract_validation_failure(self):
        result = classify_route_result(
            {"analysis": {"status": "progress"}},
            {"status": "blocked", "contract": {}},
        )
        self.assertEqual("blocked", result["status"])
        self.assertIn("route-contract-validation-not-passed", result["blockers"])

    def test_route_result_arrived_passes_without_progress_distance(self):
        result = classify_route_result(
            {"analysis": {"status": "arrived", "stopReason": "within-arrival-radius"}},
            {"status": "passed", "contract": {"movementPermission": False}},
        )
        self.assertEqual("passed", result["status"])
        self.assertEqual("arrived", result["routeStatus"])
        self.assertEqual([], result["blockers"])

    # ------------------------------------------------------------------ #
    # destination_args tests
    # ------------------------------------------------------------------ #

    def test_destination_args_direct_coordinates(self):
        args = argparse.Namespace(
            destination_x=100.0,
            destination_y=None,
            destination_z=200.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            destination_label=None,
            arrival_radius=None,
            alignment_threshold_degrees=7.5,
        )
        parts = destination_args(args)
        self.assertIn("--destination-x", parts)
        self.assertIn("100.0", parts)
        self.assertIn("--destination-z", parts)
        self.assertIn("200.0", parts)
        self.assertIn("--alignment-threshold-degrees", parts)
        self.assertIn("7.5", parts)
        self.assertNotIn("--destination-waypoint-json", parts)

    def test_destination_args_with_destination_y(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=2.0,
            destination_z=3.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            destination_label=None,
            arrival_radius=None,
            alignment_threshold_degrees=5.0,
        )
        parts = destination_args(args)
        self.assertIn("--destination-y", parts)
        self.assertIn("2.0", parts)

    def test_destination_args_with_label_and_arrival_radius(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=None,
            destination_z=2.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            destination_label="town",
            arrival_radius=5.0,
            alignment_threshold_degrees=7.5,
        )
        parts = destination_args(args)
        self.assertIn("--destination-label", parts)
        self.assertIn("town", parts)
        self.assertIn("--arrival-radius", parts)
        self.assertIn("5.0", parts)

    def test_destination_args_waypoint_mode(self):
        args = argparse.Namespace(
            destination_x=None,
            destination_y=None,
            destination_z=None,
            destination_waypoint_json="waypoints.json",
            destination_waypoint_id="dest1",
            destination_label=None,
            arrival_radius=None,
            alignment_threshold_degrees=7.5,
        )
        parts = destination_args(args)
        self.assertIn("--destination-waypoint-json", parts)
        self.assertIn("waypoints.json", parts)
        self.assertIn("--destination-waypoint-id", parts)
        self.assertIn("dest1", parts)
        self.assertNotIn("--destination-x", parts)

    def test_destination_args_waypoint_mode_without_id(self):
        args = argparse.Namespace(
            destination_x=None,
            destination_y=None,
            destination_z=None,
            destination_waypoint_json="wp.json",
            destination_waypoint_id=None,
            destination_label=None,
            arrival_radius=None,
            alignment_threshold_degrees=10.0,
        )
        parts = destination_args(args)
        self.assertIn("--destination-waypoint-json", parts)
        self.assertNotIn("--destination-waypoint-id", parts)
        self.assertIn("--alignment-threshold-degrees", parts)
        self.assertIn("10.0", parts)

    # ------------------------------------------------------------------ #
    # compact tests
    # ------------------------------------------------------------------ #

    def test_compact_full_summary(self):
        summary = {
            "status": "passed",
            "verdict": "route-step-live-movement-progress-validated",
            "initialDecision": {"status": "passed"},
            "routeResult": {"status": "passed", "routeStatus": "progress"},
            "safety": {"movementSent": True, "inputSent": True},
            "artifacts": {
                "summaryJson": "out/summary.json",
                "summaryMarkdown": "out/summary.md",
                "preStateSummaryJson": "out/pre.json",
                "postStateSummaryJson": "out/post.json",
                "routeSummaryJson": "out/route.json",
                "routeContractSummaryJson": "out/contract.json",
            },
            "blockers": [],
            "warnings": ["dry-run-only"],
            "errors": [],
        }
        c = compact(summary)
        self.assertEqual("passed", c["status"])
        self.assertEqual("progress", c["routeResult"]["routeStatus"])
        self.assertTrue(c["movementSent"])
        self.assertTrue(c["inputSent"])
        self.assertIn("dry-run-only", c["warnings"])

    def test_compact_minimal_summary(self):
        c = compact({})
        self.assertIsNone(c["status"])
        self.assertIsNone(c["initialDecision"])
        self.assertIsNone(c["movementSent"])
        self.assertEqual([], c["blockers"])

    # ------------------------------------------------------------------ #
    # full_summary_from_compact tests
    # ------------------------------------------------------------------ #

    def test_full_summary_from_compact_reads_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "summary.json"
            fixture.write_text(json.dumps({"status": "passed", "foo": "bar"}), encoding="utf-8")
            result = full_summary_from_compact({"summaryJson": str(fixture)})
        self.assertEqual("passed", result["status"])
        self.assertEqual("bar", result["foo"])

    def test_full_summary_from_compact_raises_on_missing_key(self):
        with self.assertRaises(ValueError):
            full_summary_from_compact({})

    def test_full_summary_from_compact_raises_on_non_dict_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "summary.json"
            fixture.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            with self.assertRaises(ValueError):
                full_summary_from_compact({"summaryJson": str(fixture)})

    # ------------------------------------------------------------------ #
    # state_command tests
    # ------------------------------------------------------------------ #

    def test_state_command_basic_structure(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=None,
            destination_z=2.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            destination_label=None,
            arrival_radius=None,
            alignment_threshold_degrees=7.5,
            current_truth_json="docs/recovery/current-truth.json",
            samples=3,
            interval_seconds=0.1,
            output_root=None,
        )
        root = repo_root()
        cmd = state_command(args, root)
        self.assertIn("static_owner_facing_discovery.py", " ".join(cmd))
        self.assertIn("state", cmd)
        self.assertIn("--expect-stationary", cmd)
        self.assertIn("--json", cmd)
        self.assertIn("docs/recovery/current-truth.json", cmd)

    def test_state_command_with_output_root(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=None,
            destination_z=2.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            destination_label=None,
            arrival_radius=None,
            alignment_threshold_degrees=7.5,
            current_truth_json="current-truth.json",
            samples=5,
            interval_seconds=0.2,
            output_root="/tmp/out",
        )
        cmd = state_command(args, Path("/repo"))
        self.assertIn("--output-root", cmd)
        self.assertIn("/tmp/out", cmd)
        self.assertIn("--samples", cmd)
        self.assertIn("5", cmd)

    # ------------------------------------------------------------------ #
    # route_command tests
    # ------------------------------------------------------------------ #

    def test_route_command_basic_structure(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=None,
            destination_z=2.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            destination_label=None,
            arrival_radius=None,
            alignment_threshold_degrees=7.5,
            minimum_progress_distance=0.05,
            wrong_way_tolerance_distance=0.75,
            output_root=None,
        )
        cmd = route_command(args, repo_root(), "pre.json", "post.json")
        self.assertIn("route", cmd)
        self.assertIn("--state-summary-json", cmd)
        self.assertIn("pre.json", cmd)
        self.assertIn("post.json", cmd)
        self.assertIn("--minimum-progress-distance", cmd)
        self.assertIn("0.05", cmd)
        self.assertIn("--wrong-way-tolerance-distance", cmd)
        self.assertIn("0.75", cmd)

    def test_route_command_produces_post_state_path_last(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=None,
            destination_z=2.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            destination_label=None,
            arrival_radius=None,
            alignment_threshold_degrees=7.5,
            minimum_progress_distance=0.05,
            wrong_way_tolerance_distance=0.75,
            output_root=None,
        )
        cmd = route_command(args, repo_root(), "pre.json", "post.json")
        idx_pre = cmd.index("pre.json")
        idx_post = cmd.index("post.json")
        self.assertLess(idx_pre, idx_post, "pre_state_path should appear before post_state_path")

    # ------------------------------------------------------------------ #
    # validate_route_command tests
    # ------------------------------------------------------------------ #

    def test_validate_route_command_basic_structure(self):
        args = argparse.Namespace(output_root=None)
        cmd = validate_route_command(args, repo_root(), "route-summary.json")
        self.assertIn("validate-route", cmd)
        self.assertIn("--route-summary-json", cmd)
        self.assertIn("route-summary.json", cmd)
        self.assertIn("--json", cmd)

    def test_validate_route_command_with_output_root(self):
        args = argparse.Namespace(output_root="/tmp/validate")
        cmd = validate_route_command(args, repo_root(), "route-summary.json")
        self.assertIn("--output-root", cmd)
        self.assertIn("/tmp/validate", cmd)

    # ------------------------------------------------------------------ #
    # send_key_command tests
    # ------------------------------------------------------------------ #

    def test_send_key_command_basic_structure(self):
        args = argparse.Namespace(
            key="w",
            hold_milliseconds=250,
            title_contains="RIFT",
            input_mode="ScanCode",
            focus_delay_milliseconds=250,
        )
        pre_state = {
            "target": {
                "processName": "rift_x64",
                "processId": 1234,
                "targetWindowHandle": "0xABC",
            }
        }
        cmd = send_key_command(args, repo_root(), pre_state)
        self.assertIn("send-rift-key-csharp.ps1", " ".join(cmd))
        self.assertIn("--key", cmd)
        self.assertIn("w", cmd)
        self.assertIn("--pid", cmd)
        self.assertIn("1234", cmd)
        self.assertIn("--hwnd", cmd)
        self.assertIn("0xABC", cmd)

    def test_send_key_command_falls_back_to_rift_x64(self):
        args = argparse.Namespace(
            key="a",
            hold_milliseconds=500,
            title_contains="RIFT",
            input_mode="VirtualKey",
            focus_delay_milliseconds=100,
        )
        cmd = send_key_command(args, repo_root(), {})
        self.assertIn("rift_x64", " ".join(cmd))
        self.assertIn("VirtualKey", cmd)

    def test_clear_ui_focus_command_uses_exact_target_escape(self):
        args = argparse.Namespace(
            clear_ui_focus_key="escape",
            clear_ui_focus_hold_milliseconds=50,
            title_contains="RIFT",
            input_mode="ScanCode",
            focus_delay_milliseconds=250,
        )
        pre_state = {
            "target": {
                "processName": "rift_x64",
                "processId": 1234,
                "targetWindowHandle": "0xABC",
            }
        }

        cmd = clear_ui_focus_command(args, repo_root(), pre_state)

        self.assertIn("send-rift-key-csharp.ps1", " ".join(cmd))
        self.assertEqual("escape", cmd[cmd.index("--key") + 1])
        self.assertEqual("50", cmd[cmd.index("--hold-ms") + 1])
        self.assertEqual("1234", cmd[cmd.index("--pid") + 1])
        self.assertEqual("0xABC", cmd[cmd.index("--hwnd") + 1])

    def test_validate_args_rejects_bad_clear_ui_focus_options(self):
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
            clear_ui_focus_before_input=True,
            clear_ui_focus_key="",
            clear_ui_focus_hold_milliseconds=0,
        )

        errors = validate_args(args)

        self.assertIn("clear-ui-focus-key-required", errors)
        self.assertIn("clear-ui-focus-hold-milliseconds-must-be-positive", errors)

    # ------------------------------------------------------------------ #
    # build_markdown tests
    # ------------------------------------------------------------------ #

    def test_build_markdown_full_summary(self):
        md = build_markdown(
            {
                "generatedAtUtc": "2026-05-29T12:00:00+00:00",
                "status": "passed",
                "verdict": "route-step-live-movement-progress-validated",
                "initialDecision": {
                    "status": "passed",
                    "reason": "initial-bearing-aligned-forward-step-eligible",
                    "controlIntent": "forward",
                    "movementRequired": True,
                },
                "routeResult": {
                    "routeStatus": "progress",
                    "stopReason": "distance-decreased",
                    "totalProgressDistance": 1.5,
                    "controllerRecommendedAction": "continue-aligned-candidate",
                },
                "safety": {
                    "movementSent": True,
                    "inputSent": True,
                    "noCheatEngine": True,
                    "x64dbgAttach": False,
                    "providerWrites": False,
                    "proofPromotion": False,
                },
                "artifacts": {
                    "summaryJson": "out/summary.json",
                    "runDirectory": "out/run",
                },
                "blockers": [],
                "warnings": [],
                "errors": [],
            }
        )
        self.assertIn("Static owner navigation route step", md)
        self.assertIn("passed", md)
        self.assertIn("Initial decision", md)
        self.assertIn("Route result", md)
        self.assertIn("Safety", md)
        self.assertIn("Artifacts", md)

    def test_build_markdown_with_blockers_warnings_errors(self):
        md = build_markdown(
            {
                "generatedAtUtc": "now",
                "status": "blocked",
                "verdict": "route-step-initial-decision-blocked",
                "initialDecision": {"status": "blocked"},
                "routeResult": {},
                "safety": {},
                "artifacts": {},
                "blockers": ["initial-bearing-not-aligned:left"],
                "warnings": ["candidate-only-yaw"],
                "errors": ["something-went-wrong"],
            }
        )
        self.assertIn("Blockers", md)
        self.assertIn("initial-bearing-not-aligned:left", md)
        self.assertIn("Warnings", md)
        self.assertIn("candidate-only-yaw", md)
        self.assertIn("Errors", md)
        self.assertIn("something-went-wrong", md)
        # Section order: blockers first, then warnings, then errors
        idx_blockers = md.index("Blockers")
        idx_warnings = md.index("Warnings")
        idx_errors = md.index("Errors")
        self.assertLess(idx_blockers, idx_warnings)
        self.assertLess(idx_warnings, idx_errors)

    def test_build_markdown_minimal(self):
        md = build_markdown({"generatedAtUtc": "now", "status": "unknown"})
        self.assertIn("now", md)
        self.assertIn("unknown", md)
        # No Blockers/Warnings/Errors sections when lists are absent
        self.assertNotIn("Blockers", md)
        self.assertNotIn("Warnings", md)
        self.assertNotIn("Errors", md)
