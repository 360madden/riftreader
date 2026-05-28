import argparse
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.static_owner_nav_route_run import (
    build_report_markdown,
    compact_report,
    report_saved_summary,
    summarize_turn_forward_evidence,
    summarize_turn_evidence,
    summarize_route_run_steps,
    validate_args,
    validate_route_run_summary_contract,
    validate_saved_summary,
)


def route_step_fixture() -> dict:
    fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-step-summary-progress.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


def route_run_fixture() -> dict:
    fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-run-summary-arrived.json"
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
            max_arrival_radius=10.0,
        )

        self.assertIn("max-steps-must-be-positive", validate_args(args))

    def test_validate_args_blocks_overlarge_arrival_radius(self):
        args = argparse.Namespace(
            destination_x=1.0,
            destination_y=None,
            destination_z=2.0,
            destination_waypoint_json=None,
            destination_waypoint_id=None,
            arrival_radius=25.0,
            alignment_threshold_degrees=7.5,
            samples=3,
            interval_seconds=0.1,
            hold_milliseconds=250,
            settle_seconds=0.75,
            command_timeout_seconds=120.0,
            step_timeout_seconds=240.0,
            max_steps=1,
            max_arrival_radius=10.0,
        )

        self.assertIn("arrival-radius-exceeds-max-arrival-radius", validate_args(args))

    def test_checked_in_route_run_fixture_passes_contract(self):
        summary = route_run_fixture()

        contract = validate_route_run_summary_contract(summary)

        self.assertEqual("passed", contract["status"])
        self.assertEqual([], contract["blockers"])
        self.assertEqual(2, contract["stepsRun"])
        self.assertTrue(contract["arrived"])
        self.assertTrue(contract["movementSent"])
        self.assertTrue(contract["inputSent"])
        self.assertTrue(contract["navigationControl"])

    def test_route_run_contract_blocks_unarrived_final_step(self):
        summary = route_run_fixture()
        summary["aggregate"]["lastRouteStatus"] = "progress"
        summary["aggregate"]["arrived"] = False
        summary["steps"][-1]["routeStatus"] = "progress"

        contract = validate_route_run_summary_contract(summary)

        self.assertEqual("blocked", contract["status"])
        self.assertIn("aggregate-arrived-must-be-true", contract["blockers"])
        self.assertIn("last-step-route-status-must-be-arrived", contract["blockers"])

    def test_validate_saved_summary_passes_fixture(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-run-summary-arrived.json"
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                repo_root=None,
                output_root=tmp,
                validate_route_run_summary_json=str(fixture),
            )

            summary = validate_saved_summary(args)

        self.assertEqual("passed", summary["status"])
        self.assertEqual("passed", summary["contract"]["status"])
        self.assertEqual([], summary["blockers"])

    def test_report_saved_summary_passes_fixture(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-run-summary-arrived.json"
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                repo_root=None,
                output_root=tmp,
                report_route_run_summary_json=str(fixture),
                turn_summary_json=None,
            )

            summary = report_saved_summary(args)

        self.assertEqual("passed", summary["status"])
        self.assertEqual("route-run-arrived", summary["source"]["verdict"])
        self.assertEqual(2, summary["source"]["aggregate"]["stepsRun"])
        self.assertEqual("passed", summary["contract"]["status"])

    def test_turn_evidence_can_be_added_to_route_run_report(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-run-summary-arrived.json"
        left = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-turn-stimulus-summary-left.json"
        right = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-turn-stimulus-summary-right.json"
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                repo_root=None,
                output_root=tmp,
                report_route_run_summary_json=str(fixture),
                turn_summary_json=[str(left), str(right)],
            )

            summary = report_saved_summary(args)

        self.assertEqual("passed", summary["status"])
        self.assertEqual(2, len(summary["turnEvidence"]))
        self.assertEqual(["left", "right"], [item["direction"] for item in summary["turnEvidence"]])
        self.assertEqual(["passed", "passed"], [item["contractStatus"] for item in summary["turnEvidence"]])

    def test_turn_forward_evidence_can_be_added_to_route_run_report(self):
        fixture = Path(__file__).resolve().parent / "navigation" / "testdata" / "static-owner-nav-route-run-summary-arrived.json"
        turn_forward = (
            Path(__file__).resolve().parent
            / "navigation"
            / "testdata"
            / "static-owner-turn-forward-experiment-summary-progress.json"
        )
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                repo_root=None,
                output_root=tmp,
                report_route_run_summary_json=str(fixture),
                turn_summary_json=None,
                turn_forward_summary_json=[str(turn_forward)],
            )

            summary = report_saved_summary(args)

        self.assertEqual("passed", summary["status"])
        self.assertEqual(1, len(summary["turnForwardEvidence"]))
        self.assertEqual("passed", summary["turnForwardEvidence"][0]["contractStatus"])
        self.assertEqual("turn-forward-live-progress-validated", summary["turnForwardEvidence"][0]["verdict"])
        self.assertEqual("progress", summary["turnForwardEvidence"][0]["routeStatus"])
        compact = compact_report(summary)
        self.assertEqual(1, compact["turnForwardEvidenceCount"])
        self.assertEqual(["passed"], compact["turnForwardEvidenceStatuses"])
        markdown = build_report_markdown(summary)
        self.assertIn("## Turn-forward evidence", markdown)
        self.assertIn("turn-forward-live-progress-validated", markdown)

    def test_summarize_turn_evidence_blocks_invalid_path(self):
        evidence, blockers, warnings = summarize_turn_evidence(["missing-turn-summary.json"])

        self.assertEqual([], evidence)
        self.assertIn("turn-evidence-1-load-or-contract-failed", blockers)
        self.assertTrue(warnings)

    def test_summarize_turn_forward_evidence_blocks_invalid_path(self):
        evidence, blockers, warnings = summarize_turn_forward_evidence(["missing-turn-forward-summary.json"])

        self.assertEqual([], evidence)
        self.assertIn("turn-forward-evidence-1-load-or-contract-failed", blockers)
        self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main()
