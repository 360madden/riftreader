from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any
from unittest import mock

from scripts import navigation_consumer_refresh as refresh
from scripts import navigation_schema_validate as schema_validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def _args(tmp_path: Path, **overrides: Any) -> Namespace:
    data: dict[str, Any] = {
        "repo_root": str(REPO_ROOT),
        "output_root": str(tmp_path / "out"),
        "current_truth_json": "docs/recovery/current-truth.json",
        "consumer_state_output_dir": str(tmp_path / "consumer-state"),
        "waypoint_readiness_json": str(tmp_path / "readiness.json"),
        "normalized_waypoints_json": None,
        "sequence_summary_json": None,
        "contract_report_json": None,
        "process_name": "rift_x64",
        "pid": None,
        "hwnd": None,
        "module_base": None,
        "max_consumer_state_age_seconds": 5.0,
        "command_timeout_seconds": 30.0,
        "require_fresh_pose": False,
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


def _consumer_child(tmp_path: Path, *, status: str = "passed", exit_code: int = 0) -> dict[str, Any]:
    return {
        "label": "consumer-state-refresh",
        "ok": exit_code == 0,
        "exitCode": exit_code,
        "json": {
            "status": status,
            "verdict": "consumer-navigation-state-ready" if status == "passed" else "consumer-navigation-state-not-ready",
            "artifacts": {
                "summaryJson": str(tmp_path / "consumer-state" / "summary.json"),
                "summaryMarkdown": str(tmp_path / "consumer-state" / "summary.md"),
            },
            "safety": {
                "movementSent": False,
                "inputSent": False,
                "targetMemoryBytesRead": status == "passed",
                "targetMemoryBytesWritten": False,
            },
        },
    }


def _demo_child(tmp_path: Path, *, status: str = "passed", exit_code: int = 0) -> dict[str, Any]:
    blockers = [] if status == "passed" else ["demo-blocked"]
    return {
        "label": "consumer-demo-refresh",
        "ok": exit_code == 0,
        "exitCode": exit_code,
        "json": {
            "status": status,
            "verdict": "render-and-dry-run-ready-live-run-request-gated"
            if status == "passed"
            else "navigation-consumer-demo-blocked",
            "summaryJson": str(tmp_path / "demo" / "summary.json"),
            "summaryMarkdown": str(tmp_path / "demo" / "summary.md"),
            "recommendedMode": "render-and-dry-run-ready-live-run-request-gated",
            "nextRecommendedAction": "Queue a gated live-run request; execution still requires approval.",
            "canRenderRoute": True,
            "canUseDryRunContract": True,
            "canQueueGatedLiveRunRequest": status == "passed",
            "canExecuteLiveNavigation": False,
            "blockers": blockers,
            "warnings": [],
            "errors": [],
        },
    }


class NavigationConsumerRefreshTests(unittest.TestCase):
    def test_refresh_runs_consumer_state_then_demo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def fake_run_child(**kwargs: Any) -> dict[str, Any]:
                if kwargs["label"] == "consumer-state-refresh":
                    return _consumer_child(tmp_path)
                if kwargs["label"] == "consumer-demo-refresh":
                    return _demo_child(tmp_path)
                raise AssertionError(kwargs["label"])

            with mock.patch.object(refresh, "run_child", side_effect=fake_run_child):
                report = refresh.build_report(_args(tmp_path))

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["consumerState"]["status"], "passed")
        self.assertEqual(report["consumerDemo"]["status"], "passed")
        self.assertTrue(report["consumerDemo"]["capabilities"]["canQueueGatedLiveRunRequest"])
        self.assertFalse(report["consumerDemo"]["capabilities"]["canExecuteLiveNavigation"])
        self.assertTrue(report["safety"]["targetMemoryBytesRead"])
        self.assertFalse(report["safety"]["inputSent"])
        self.assertEqual([item["label"] for item in report["childCommands"]], ["consumer-state-refresh", "consumer-demo-refresh"])

    def test_consumer_state_block_stops_before_demo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            with mock.patch.object(refresh, "run_child", return_value=_consumer_child(tmp_path, status="blocked", exit_code=2)):
                report = refresh.build_report(_args(tmp_path))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("consumer-state-refresh-not-passed:blocked", report["blockers"])
        self.assertEqual(len(report["childCommands"]), 1)

    def test_demo_block_propagates_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def fake_run_child(**kwargs: Any) -> dict[str, Any]:
                if kwargs["label"] == "consumer-state-refresh":
                    return _consumer_child(tmp_path)
                if kwargs["label"] == "consumer-demo-refresh":
                    return _demo_child(tmp_path, status="blocked", exit_code=2)
                raise AssertionError(kwargs["label"])

            with mock.patch.object(refresh, "run_child", side_effect=fake_run_child):
                report = refresh.build_report(_args(tmp_path))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("demo-blocked", report["blockers"])
        self.assertFalse(report["consumerDemo"]["capabilities"]["canExecuteLiveNavigation"])

    def test_refresh_report_schema_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def fake_run_child(**kwargs: Any) -> dict[str, Any]:
                if kwargs["label"] == "consumer-state-refresh":
                    return _consumer_child(tmp_path)
                if kwargs["label"] == "consumer-demo-refresh":
                    return _demo_child(tmp_path)
                raise AssertionError(kwargs["label"])

            with mock.patch.object(refresh, "run_child", side_effect=fake_run_child):
                report = refresh.build_report(_args(tmp_path))
            schema = schema_validator.load_json_object(
                schema_validator.schema_path(REPO_ROOT, "navigation-consumer-refresh")
            )

            validation = schema_validator.validate_payload(report, schema)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["errors"], [])


if __name__ == "__main__":
    unittest.main()
