import argparse
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.static_owner_nav_route_step import base_safety
from scripts.static_owner_turn_forward_experiment import (
    summarize_forward_result,
    validate_args,
    validate_saved_summary,
    validate_turn_forward_experiment_contract,
)


def _testdata_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "navigation" / "testdata" / name


def route_step_fixture() -> dict:
    return json.loads(_testdata_path("static-owner-nav-route-step-summary-progress.json").read_text(encoding="utf-8"))


def plan_fixture(name: str = "static-owner-turn-aware-route-plan-summary-turn-needed.json") -> dict:
    return json.loads(_testdata_path(name).read_text(encoding="utf-8"))


class StaticOwnerTurnForwardExperimentTests(unittest.TestCase):
    def test_forward_result_passes_progress_step(self):
        result = summarize_forward_result(route_step_fixture())

        self.assertEqual("passed", result["status"])
        self.assertEqual("turn-forward-live-progress-validated", result["verdict"])
        self.assertEqual("progress", result["routeStatus"])

    def test_forward_result_blocks_unaligned_step(self):
        step = route_step_fixture()
        step["status"] = "blocked"
        step["verdict"] = "route-step-initial-decision-blocked"
        step["blockers"] = ["initial-bearing-not-aligned:left"]

        result = summarize_forward_result(step)

        self.assertEqual("blocked", result["status"])
        self.assertEqual("forward-route-step-blocked", result["verdict"])
        self.assertIn("initial-bearing-not-aligned:left", result["blockers"])

    def test_validate_args_blocks_total_input_duration(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=None,
            destination_z=2.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            arrival_radius=2.0,
            alignment_threshold_degrees=7.5,
            turn_hold_milliseconds=500,
            forward_hold_milliseconds=500,
            max_initial_turn_degrees=90.0,
            max_cumulative_turn_degrees=90.0,
            max_observed_turn_degrees=90.0,
            max_total_input_milliseconds=600,
            max_route_steps=1,
            samples=3,
            interval_seconds=0.1,
            turn_settle_seconds=0.75,
            forward_settle_seconds=0.75,
            command_timeout_seconds=120.0,
            minimum_yaw_delta_degrees=1.0,
            max_turn_planar_drift=1.0,
        )

        self.assertIn("planned-input-duration-exceeds-max-total-input-milliseconds", validate_args(args))

    def test_validate_args_blocks_multi_step_experiment(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=None,
            destination_z=2.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            arrival_radius=2.0,
            alignment_threshold_degrees=7.5,
            turn_hold_milliseconds=175,
            forward_hold_milliseconds=250,
            max_initial_turn_degrees=90.0,
            max_cumulative_turn_degrees=90.0,
            max_observed_turn_degrees=90.0,
            max_total_input_milliseconds=600,
            max_route_steps=2,
            samples=3,
            interval_seconds=0.1,
            turn_settle_seconds=0.75,
            forward_settle_seconds=0.75,
            command_timeout_seconds=120.0,
            minimum_yaw_delta_degrees=1.0,
            max_turn_planar_drift=1.0,
        )

        self.assertIn("turn-forward-experiment-supports-exactly-one-route-step", validate_args(args))

    def test_live_experiment_contract_passes_fixture_shape(self):
        safety = base_safety()
        safety["movementSent"] = True
        safety["inputSent"] = True
        safety["navigationControl"] = True
        summary = {
            "kind": "static-owner-turn-forward-experiment",
            "status": "passed",
            "verdict": "turn-forward-live-progress-validated",
            "operator": {
                "dryRun": False,
                "movementApproved": True,
                "turnApproved": True,
                "allowCandidateTurnControl": True,
            },
            "turnAwarePlanSummary": plan_fixture("static-owner-turn-aware-route-plan-summary-aligned.json"),
            "forwardResult": {
                "status": "passed",
                "verdict": "turn-forward-live-progress-validated",
                "routeStatus": "progress",
                "totalProgressDistance": 1.0,
            },
            "safety": safety,
        }

        contract = validate_turn_forward_experiment_contract(summary)

        self.assertEqual("passed", contract["status"])
        self.assertEqual([], contract["blockers"])
        self.assertTrue(contract["inputSent"])
        self.assertTrue(contract["navigationControl"])

    def test_dry_run_experiment_contract_passes_without_input(self):
        safety = base_safety()
        summary = {
            "kind": "static-owner-turn-forward-experiment",
            "status": "passed",
            "verdict": "turn-forward-experiment-dry-run-plan-built",
            "operator": {
                "dryRun": True,
                "movementApproved": False,
                "turnApproved": False,
                "allowCandidateTurnControl": False,
            },
            "turnAwarePlanSummary": plan_fixture("static-owner-turn-aware-route-plan-summary-turn-needed.json"),
            "forwardResult": {},
            "safety": safety,
        }

        contract = validate_turn_forward_experiment_contract(summary)

        self.assertEqual("passed", contract["status"])
        self.assertEqual([], contract["blockers"])
        self.assertFalse(contract["inputSent"])
        self.assertFalse(contract["navigationControl"])

    def test_validate_saved_experiment_fixture_passes(self):
        safety = base_safety()
        safety["movementSent"] = True
        safety["inputSent"] = True
        safety["navigationControl"] = True
        fixture_summary = {
            "schemaVersion": 1,
            "kind": "static-owner-turn-forward-experiment",
            "generatedAtUtc": "2026-05-28T18:10:00+00:00",
            "status": "passed",
            "verdict": "turn-forward-live-progress-validated",
            "repoRoot": "C:\\RIFT MODDING\\RiftReader",
            "operator": {
                "dryRun": False,
                "movementApproved": True,
                "turnApproved": True,
                "allowCandidateTurnControl": True,
            },
            "turnAwarePlanSummary": plan_fixture("static-owner-turn-aware-route-plan-summary-aligned.json"),
            "forwardStepSummary": route_step_fixture(),
            "forwardResult": summarize_forward_result(route_step_fixture()),
            "blockers": [],
            "warnings": ["candidate-facing-yaw-not-promoted"],
            "errors": [],
            "safety": safety,
            "artifacts": {"runDirectory": "fixture", "summaryJson": "fixture", "summaryMarkdown": "fixture"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "experiment.json"
            fixture.write_text(json.dumps(fixture_summary, indent=2), encoding="utf-8")
            args = argparse.Namespace(
                repo_root=None,
                output_root=tmp,
                validate_experiment_summary_json=str(fixture),
            )

            summary = validate_saved_summary(args)

        self.assertEqual("passed", summary["status"])
        self.assertEqual("passed", summary["contract"]["status"])

    def test_checked_in_live_progress_fixture_passes_contract(self):
        summary = json.loads(_testdata_path("static-owner-turn-forward-experiment-summary-progress.json").read_text(encoding="utf-8"))

        contract = validate_turn_forward_experiment_contract(summary)

        self.assertEqual("passed", contract["status"])
        self.assertEqual([], contract["blockers"])
        self.assertEqual("turn-forward-live-progress-validated", contract["verdict"])
        self.assertTrue(contract["movementSent"])
        self.assertTrue(contract["inputSent"])
        self.assertTrue(contract["navigationControl"])


if __name__ == "__main__":
    unittest.main()
