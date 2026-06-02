from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any

from scripts import navigation_live_run_command_plan as command_plan
from scripts import navigation_live_run_request as request
from scripts import navigation_live_run_review as review
from scripts import navigation_schema_validate as schema_validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _normalized_waypoints() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "provenance": {
            "kind": "riftreader-normalized-navigation-waypoints",
            "generatedAtUtc": command_plan.utc_iso(),
            "inputJson": "waypoints.json",
            "defaultArrivalRadius": 2.0,
            "requestedWaypointIds": None,
        },
        "waypoints": [
            {"id": "alpha", "label": "Alpha", "x": 1.0, "y": 2.0, "z": 3.0, "arrivalRadius": 2.0},
            {"id": "bravo", "label": "Bravo", "x": 4.0, "y": 2.0, "z": 6.0, "arrivalRadius": 2.0},
        ],
    }


def _waypoint_readiness(normalized_path: Path) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-waypoint-readiness",
        "generatedAtUtc": command_plan.utc_iso(),
        "status": "passed",
        "verdict": "waypoint-readiness-consumable",
        "input": {
            "waypointSequenceJson": "waypoints.json",
            "waypointSequenceIds": None,
            "skipDryRun": False,
            "currentTruthJson": "docs/recovery/current-truth.json",
        },
        "lint": {
            "status": "passed",
            "inputJson": "waypoints.json",
            "originalWaypointCount": 2,
            "selectedWaypointCount": 2,
            "defaultArrivalRadius": 2.0,
            "requestedWaypointIds": None,
            "normalizedWaypoints": _normalized_waypoints()["waypoints"],
            "blockers": [],
            "warnings": [],
        },
        "dryRun": {
            "status": "passed",
            "verdict": "sequence-dry-run-plan-built",
            "summaryJson": "sequence-summary.json",
            "summaryMarkdown": "sequence-summary.md",
        },
        "contract": {
            "status": "passed",
            "consumable": True,
            "summaryJson": "contract-summary.json",
            "summaryMarkdown": "contract-summary.md",
            "blockers": [],
            "warnings": [],
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "x64dbgAttach": False,
        },
        "artifacts": {
            "summaryJson": "readiness.json",
            "summaryMarkdown": "readiness.md",
            "normalizedWaypointJson": str(normalized_path),
        },
        "blockers": [],
        "warnings": [],
        "errors": [],
    }


def _package_payload(readiness_path: Path, *, next_waypoint_id: str = "alpha") -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-downstream-package",
        "generatedAtUtc": command_plan.utc_iso(),
        "status": "passed",
        "verdict": "package-ready-live-run-request-gated",
        "input": {
            "currentTruthJson": "current-truth.json",
            "consumerStateOutputDir": "consumer-state",
            "waypointReadinessJson": str(readiness_path),
            "normalizedWaypointsJson": None,
            "maxConsumerStateAgeSeconds": 30.0,
            "alignmentThresholdDegrees": 7.5,
            "requireFreshPose": False,
        },
        "consumerRefresh": {
            "status": "passed",
            "verdict": "ready",
            "summaryJson": "refresh.json",
            "summaryMarkdown": "refresh.md",
            "consumerStateSummaryJson": "state.json",
            "consumerDemoSummaryJson": "demo.json",
            "canRenderRoute": True,
            "canUseDryRunContract": True,
            "canQueueGatedLiveRunRequest": True,
            "canExecuteLiveNavigation": False,
            "exitCode": 0,
        },
        "routePreview": {
            "status": "passed",
            "verdict": "ready",
            "summaryJson": "preview.json",
            "summaryMarkdown": "preview.md",
            "waypointCount": 2,
            "legCount": 1,
            "routeComplete": False,
            "nextWaypointId": next_waypoint_id,
            "activeLegPlanarDistance": 10.0,
            "activeLegBearingDegrees": 20.0,
            "activeLegInitialYawDeltaDegrees": 3.0,
            "activeLegSuggestedInitialTurnDirection": "aligned",
            "canRenderRoutePreview": True,
            "canUseRoutePreview": True,
            "canQueueGatedLiveRunRequest": True,
            "canExecuteLiveNavigation": False,
            "exitCode": 0,
        },
        "schemaValidations": [],
        "capabilities": {
            "canRenderRoute": True,
            "canUseDryRunContract": True,
            "canRenderRoutePreview": True,
            "canUseRoutePreview": True,
            "canQueueGatedLiveRunRequest": True,
            "canExecuteLiveNavigation": False,
            "liveExecutionRequiresExplicitApproval": True,
            "recommendedMode": "package-ready-live-run-request-gated",
            "nextRecommendedAction": "Queue gated request.",
        },
        "childCommands": [],
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": True,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "x64dbgAttach": False,
            "downstreamPackageOnly": True,
            "routeControlAuthorized": False,
        },
        "artifacts": {"summaryJson": "package.json", "summaryMarkdown": "package.md"},
        "blockers": [],
        "warnings": [],
        "errors": [],
    }


def _request_args(tmp_path: Path, package_path: Path, *, mode: str) -> Namespace:
    return Namespace(
        repo_root=str(REPO_ROOT),
        output_root=str(tmp_path / "request-out"),
        downstream_package_json=str(package_path),
        request_id="request-001",
        requested_by="unit-test",
        requested_mode=mode,
        json=True,
    )


def _review_args(tmp_path: Path, request_path: Path) -> Namespace:
    return Namespace(
        repo_root=str(REPO_ROOT),
        output_root=str(tmp_path / "review-out"),
        live_run_request_json=str(request_path),
        review_id="review-001",
        max_request_age_seconds=3600.0,
        max_source_package_age_seconds=3600.0,
        json=True,
    )


def _plan_args(tmp_path: Path, review_path: Path, **overrides: Any) -> Namespace:
    data: dict[str, Any] = {
        "repo_root": str(REPO_ROOT),
        "output_root": str(tmp_path / "plan-out"),
        "live_run_review_json": str(review_path),
        "plan_id": "plan-001",
        "max_review_age_seconds": 3600.0,
        "turn_backend": "mouse-look",
        "mouse_pixels_per_pulse": 40,
        "game_maintenance": False,
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


def _write_review_chain(tmp_path: Path, *, mode: str = "continuous-route-run") -> Path:
    normalized_path = _write_json(tmp_path / "normalized-waypoints.json", _normalized_waypoints())
    readiness_path = _write_json(tmp_path / "readiness.json", _waypoint_readiness(normalized_path))
    package_path = _write_json(tmp_path / "package.json", _package_payload(readiness_path))
    request_report = request.build_report(_request_args(tmp_path, package_path, mode=mode))
    request_path = _write_json(tmp_path / "request.json", request_report)
    review_report = review.build_report(_review_args(tmp_path, request_path))
    return _write_json(tmp_path / "review.json", review_report)


class NavigationLiveRunCommandPlanTests(unittest.TestCase):
    def test_continuous_command_plan_builds_templates_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            review_path = _write_review_chain(tmp_path)

            report = command_plan.build_report(_plan_args(tmp_path, review_path, game_maintenance=True))

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["verdict"], "navigation-live-run-command-plan-ready-non-executable")
        self.assertEqual(report["commandPlan"]["requestedMode"], "continuous-route-run")
        self.assertIn("scripts/static_owner_continuous_route_runner.py", report["commandPlan"]["executionCommandTemplate"])
        self.assertIn("--movement-approved", report["commandPlan"]["executionCommandTemplate"])
        self.assertTrue(report["executionGate"]["commandPlanOnly"])
        self.assertFalse(report["executionGate"]["executionAuthorized"])
        self.assertFalse(report["executionGate"]["routeRunnerInvoked"])
        self.assertFalse(report["safety"]["targetMemoryBytesRead"])
        self.assertIn("game-maintenance-world-entry-unavailable-live-execution-not-possible", report["warnings"])

    def test_single_step_command_plan_uses_next_waypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            review_path = _write_review_chain(tmp_path, mode="single-route-step")

            report = command_plan.build_report(_plan_args(tmp_path, review_path))

        self.assertEqual(report["status"], "passed")
        self.assertIn("scripts/static_owner_nav_route_step.py", report["commandPlan"]["executionCommandTemplate"])
        self.assertIn("--destination-waypoint-id", report["commandPlan"]["executionCommandTemplate"])
        self.assertIn("alpha", report["commandPlan"]["executionCommandTemplate"])
        self.assertFalse(report["executionGate"]["executionAuthorized"])

    def test_command_plan_blocks_when_review_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            review_path = _write_review_chain(tmp_path)
            payload = json.loads(review_path.read_text(encoding="utf-8"))
            payload["review"]["readyForSeparateLiveApproval"] = False
            _write_json(review_path, payload)

            report = command_plan.build_report(_plan_args(tmp_path, review_path))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("review-not-ready-for-separate-live-approval", report["blockers"])
        self.assertFalse(report["executionGate"]["executionAuthorized"])

    def test_command_plan_schema_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            review_path = _write_review_chain(tmp_path)

            report = command_plan.build_report(_plan_args(tmp_path, review_path))
            schema = schema_validator.load_json_object(
                schema_validator.schema_path(REPO_ROOT, "navigation-live-run-command-plan")
            )
            validation = schema_validator.validate_payload(report, schema)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["errors"], [])


if __name__ == "__main__":
    unittest.main()
