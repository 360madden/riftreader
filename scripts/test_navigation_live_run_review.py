from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any

from scripts import navigation_live_run_request as request
from scripts import navigation_live_run_review as review
from scripts import navigation_schema_validate as schema_validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _package_payload(*, input_sent: bool = False, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-downstream-package",
        "generatedAtUtc": generated_at or review.utc_iso(),
        "status": "passed",
        "verdict": "package-ready-live-run-request-gated",
        "input": {
            "currentTruthJson": "current-truth.json",
            "consumerStateOutputDir": "consumer-state",
            "waypointReadinessJson": "readiness.json",
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
            "nextWaypointId": "waypoint-001",
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
        "schemaValidations": [
            {
                "label": "schema-consumer-state",
                "status": "passed",
                "inputJson": "state.json",
                "inputKind": "riftreader-navigation-consumer-state",
                "schemaKey": "navigation-consumer-state",
                "validationStatus": "passed",
                "validationErrorCount": 0,
                "summaryJson": "schema-state.json",
                "summaryMarkdown": "schema-state.md",
                "exitCode": 0,
                "blockers": [],
                "warnings": [],
                "errors": [],
            }
        ],
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
            "inputSent": input_sent,
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


def _request_args(tmp_path: Path, package_path: Path) -> Namespace:
    return Namespace(
        repo_root=str(REPO_ROOT),
        output_root=str(tmp_path / "request-out"),
        downstream_package_json=str(package_path),
        request_id="request-001",
        requested_by="unit-test",
        requested_mode="continuous-route-run",
        json=True,
    )


def _review_args(tmp_path: Path, request_path: Path, **overrides: Any) -> Namespace:
    data: dict[str, Any] = {
        "repo_root": str(REPO_ROOT),
        "output_root": str(tmp_path / "review-out"),
        "live_run_request_json": str(request_path),
        "review_id": "review-001",
        "max_request_age_seconds": 3600.0,
        "max_source_package_age_seconds": 3600.0,
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


def _write_request(tmp_path: Path, package_payload: dict[str, Any]) -> tuple[Path, Path]:
    package_path = _write_json(tmp_path / "package.json", package_payload)
    request_report = request.build_report(_request_args(tmp_path, package_path))
    request_path = _write_json(tmp_path / "request.json", request_report)
    return request_path, package_path


class NavigationLiveRunReviewTests(unittest.TestCase):
    def test_review_accepts_fresh_request_without_authorizing_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request_path, _package_path = _write_request(tmp_path, _package_payload())

            report = review.build_report(_review_args(tmp_path, request_path))

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["verdict"], "navigation-live-run-review-ready-for-separate-live-approval")
        self.assertTrue(report["review"]["readyForSeparateLiveApproval"])
        self.assertFalse(report["review"]["executionReviewApproved"])
        self.assertFalse(report["review"]["executionAuthorized"])
        self.assertFalse(report["review"]["executionAttempted"])
        self.assertFalse(report["review"]["routeRunnerInvoked"])
        self.assertFalse(report["safety"]["inputSent"])
        self.assertFalse(report["safety"]["targetMemoryBytesRead"])
        self.assertIn("source-package-used-read-only-target-memory-refresh", report["warnings"])

    def test_review_blocks_stale_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request_path, _package_path = _write_request(tmp_path, _package_payload())
            payload = json.loads(request_path.read_text(encoding="utf-8"))
            payload["generatedAtUtc"] = "2000-01-01T00:00:00+00:00"
            _write_json(request_path, payload)

            report = review.build_report(_review_args(tmp_path, request_path))

        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(item.startswith("request-stale:") for item in report["blockers"]))
        self.assertFalse(report["review"]["readyForSeparateLiveApproval"])
        self.assertFalse(report["review"]["executionAuthorized"])

    def test_review_blocks_unsafe_source_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request_path, _package_path = _write_request(tmp_path, _package_payload(input_sent=True))

            report = review.build_report(_review_args(tmp_path, request_path))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("request-not-accepted-for-review", report["blockers"])
        self.assertIn("source-package-safety-inputSent-must-be-false", report["blockers"])
        self.assertFalse(report["review"]["readyForSeparateLiveApproval"])

    def test_review_report_schema_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            request_path, _package_path = _write_request(tmp_path, _package_payload())

            report = review.build_report(_review_args(tmp_path, request_path))
            schema = schema_validator.load_json_object(schema_validator.schema_path(REPO_ROOT, "navigation-live-run-review"))
            validation = schema_validator.validate_payload(report, schema)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["errors"], [])


if __name__ == "__main__":
    unittest.main()
