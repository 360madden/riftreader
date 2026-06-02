from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any
from unittest import mock

from scripts import navigation_downstream_package as package
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
        "max_consumer_state_age_seconds": 30.0,
        "alignment_threshold_degrees": 7.5,
        "command_timeout_seconds": 30.0,
        "require_fresh_pose": False,
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


def _refresh_child(tmp_path: Path, *, status: str = "passed", exit_code: int = 0) -> dict[str, Any]:
    return {
        "label": "consumer-refresh",
        "ok": exit_code == 0,
        "exitCode": exit_code,
        "json": {
            "status": status,
            "verdict": "render-and-dry-run-ready-live-run-request-gated"
            if status == "passed"
            else "navigation-consumer-refresh-blocked",
            "summaryJson": str(tmp_path / "refresh" / "summary.json"),
            "summaryMarkdown": str(tmp_path / "refresh" / "summary.md"),
            "consumerStateSummaryJson": str(tmp_path / "consumer-state" / "summary.json"),
            "consumerDemoSummaryJson": str(tmp_path / "consumer-demo" / "summary.json"),
            "canRenderRoute": status == "passed",
            "canUseDryRunContract": status == "passed",
            "canQueueGatedLiveRunRequest": status == "passed",
            "canExecuteLiveNavigation": False,
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": status == "passed",
            "blockers": [] if status == "passed" else ["refresh-blocked"],
            "warnings": [],
            "errors": [],
        },
    }


def _route_child(tmp_path: Path, *, status: str = "passed", exit_code: int = 0) -> dict[str, Any]:
    return {
        "label": "route-preview",
        "ok": exit_code == 0,
        "exitCode": exit_code,
        "json": {
            "status": status,
            "verdict": "route-preview-ready-live-run-request-gated"
            if status == "passed"
            else "navigation-route-preview-blocked",
            "summaryJson": str(tmp_path / "route-preview" / "summary.json"),
            "summaryMarkdown": str(tmp_path / "route-preview" / "summary.md"),
            "waypointCount": 2,
            "legCount": 2,
            "routeComplete": False,
            "nextWaypointId": "a",
            "activeLegPlanarDistance": 10.0,
            "activeLegBearingDegrees": 0.0,
            "activeLegInitialYawDeltaDegrees": 0.0,
            "activeLegSuggestedInitialTurnDirection": "aligned",
            "canRenderRoutePreview": status == "passed",
            "canUseRoutePreview": status == "passed",
            "canQueueGatedLiveRunRequest": status == "passed",
            "canExecuteLiveNavigation": False,
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "blockers": [] if status == "passed" else ["route-blocked"],
            "warnings": [],
            "errors": [],
        },
    }


def _schema_child(label: str, input_json: str, *, status: str = "passed", exit_code: int = 0) -> dict[str, Any]:
    return {
        "label": label,
        "ok": exit_code == 0,
        "exitCode": exit_code,
        "json": {
            "status": status,
            "kind": "riftreader-navigation-schema-validation",
            "inputJson": input_json,
            "inputKind": "test-kind",
            "schemaKey": label.replace("schema-", ""),
            "schemaJson": "schema.json",
            "validationStatus": "passed" if status == "passed" else "blocked",
            "validationErrorCount": 0 if status == "passed" else 1,
            "summaryJson": f"{label}-summary.json",
            "summaryMarkdown": f"{label}-summary.md",
            "blockers": [] if status == "passed" else ["schema-blocked"],
            "warnings": [],
            "errors": [],
        },
    }


class NavigationDownstreamPackageTests(unittest.TestCase):
    def test_package_runs_refresh_preview_and_schema_validations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def fake_run_child(**kwargs: Any) -> dict[str, Any]:
                label = kwargs["label"]
                if label == "consumer-refresh":
                    return _refresh_child(tmp_path)
                if label == "route-preview":
                    return _route_child(tmp_path)
                if label.startswith("schema-"):
                    input_json = kwargs["command"][kwargs["command"].index("--input") + 1]
                    return _schema_child(label, input_json)
                raise AssertionError(label)

            with mock.patch.object(package, "run_child", side_effect=fake_run_child):
                report = package.build_report(_args(tmp_path))

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["verdict"], "package-ready-live-run-request-gated")
        self.assertTrue(report["capabilities"]["canRenderRoute"])
        self.assertTrue(report["capabilities"]["canRenderRoutePreview"])
        self.assertTrue(report["capabilities"]["canQueueGatedLiveRunRequest"])
        self.assertFalse(report["capabilities"]["canExecuteLiveNavigation"])
        self.assertTrue(report["safety"]["targetMemoryBytesRead"])
        self.assertFalse(report["safety"]["inputSent"])
        self.assertEqual(
            [item["label"] for item in report["childCommands"]],
            [
                "consumer-refresh",
                "route-preview",
                "schema-consumer-state",
                "schema-consumer-demo",
                "schema-consumer-refresh",
                "schema-route-preview",
            ],
        )

    def test_refresh_block_stops_before_route_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with mock.patch.object(package, "run_child", return_value=_refresh_child(tmp_path, status="blocked", exit_code=2)):
                report = package.build_report(_args(tmp_path))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("consumer-refresh-not-passed:blocked", report["blockers"])
        self.assertEqual(len(report["childCommands"]), 1)
        self.assertFalse(report["capabilities"]["canExecuteLiveNavigation"])

    def test_schema_validation_block_blocks_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def fake_run_child(**kwargs: Any) -> dict[str, Any]:
                label = kwargs["label"]
                if label == "consumer-refresh":
                    return _refresh_child(tmp_path)
                if label == "route-preview":
                    return _route_child(tmp_path)
                input_json = kwargs["command"][kwargs["command"].index("--input") + 1]
                if label == "schema-route-preview":
                    return _schema_child(label, input_json, status="blocked", exit_code=2)
                return _schema_child(label, input_json)

            with mock.patch.object(package, "run_child", side_effect=fake_run_child):
                report = package.build_report(_args(tmp_path))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("schema-route-preview-not-passed:blocked", report["blockers"])
        self.assertFalse(report["capabilities"]["canQueueGatedLiveRunRequest"])

    def test_package_report_schema_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def fake_run_child(**kwargs: Any) -> dict[str, Any]:
                label = kwargs["label"]
                if label == "consumer-refresh":
                    return _refresh_child(tmp_path)
                if label == "route-preview":
                    return _route_child(tmp_path)
                input_json = kwargs["command"][kwargs["command"].index("--input") + 1]
                return _schema_child(label, input_json)

            with mock.patch.object(package, "run_child", side_effect=fake_run_child):
                report = package.build_report(_args(tmp_path))
            schema = schema_validator.load_json_object(schema_validator.schema_path(REPO_ROOT, "navigation-downstream-package"))
            validation = schema_validator.validate_payload(report, schema)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["errors"], [])


if __name__ == "__main__":
    unittest.main()
