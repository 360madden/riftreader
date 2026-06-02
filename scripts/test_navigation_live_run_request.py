from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any

from scripts import navigation_live_run_request as request
from scripts import navigation_schema_validate as schema_validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _args(tmp_path: Path, package_path: Path, **overrides: Any) -> Namespace:
    data: dict[str, Any] = {
        "repo_root": str(REPO_ROOT),
        "output_root": str(tmp_path / "out"),
        "downstream_package_json": str(package_path),
        "request_id": "test-request-001",
        "requested_by": "unit-test",
        "requested_mode": "continuous-route-run",
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


def _package_payload(*, status: str = "passed", can_queue: bool = True, input_sent: bool = False) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-downstream-package",
        "generatedAtUtc": request.utc_iso(),
        "status": status,
        "verdict": "package-ready-live-run-request-gated" if status == "passed" else "blocked",
        "consumerRefresh": {
            "summaryJson": "refresh.json",
            "consumerDemoSummaryJson": "demo.json",
            "consumerStateSummaryJson": "state.json",
        },
        "routePreview": {
            "summaryJson": "preview.json",
            "canExecuteLiveNavigation": False,
        },
        "schemaValidations": [],
        "capabilities": {
            "canRenderRoute": True,
            "canUseDryRunContract": True,
            "canRenderRoutePreview": True,
            "canUseRoutePreview": True,
            "canQueueGatedLiveRunRequest": can_queue,
            "canExecuteLiveNavigation": False,
            "liveExecutionRequiresExplicitApproval": True,
            "recommendedMode": "package-ready-live-run-request-gated",
            "nextRecommendedAction": "Queue gated request.",
        },
        "safety": {
            "movementSent": False,
            "inputSent": input_sent,
            "targetMemoryBytesRead": True,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "x64dbgAttach": False,
            "navigationControl": False,
        },
        "artifacts": {"summaryJson": "package.json", "summaryMarkdown": "package.md"},
        "blockers": [],
        "warnings": [],
        "errors": [],
    }


class NavigationLiveRunRequestTests(unittest.TestCase):
    def test_request_accepts_passed_queue_ready_package_without_authorizing_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            package_path = _write_json(tmp_path / "package.json", _package_payload())

            report = request.build_report(_args(tmp_path, package_path))

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["verdict"], "navigation-live-run-request-queued-for-gated-review")
        self.assertEqual(report["request"]["requestId"], "test-request-001")
        self.assertTrue(report["request"]["executionGate"]["requestAcceptedForReview"])
        self.assertFalse(report["request"]["executionGate"]["executionAuthorized"])
        self.assertFalse(report["request"]["executionGate"]["executionAttempted"])
        self.assertFalse(report["request"]["executionGate"]["routeRunnerInvoked"])
        self.assertFalse(report["request"]["capabilitySnapshot"]["canExecuteLiveNavigation"])
        self.assertFalse(report["safety"]["inputSent"])
        self.assertFalse(report["safety"]["targetMemoryBytesRead"])
        self.assertIn("source-package-used-read-only-target-memory-refresh", report["warnings"])

    def test_request_blocks_when_package_cannot_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            package_path = _write_json(tmp_path / "package.json", _package_payload(can_queue=False))

            report = request.build_report(_args(tmp_path, package_path))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("source-package-cannot-queue-gated-live-run-request", report["blockers"])
        self.assertFalse(report["request"]["executionGate"]["requestAcceptedForReview"])
        self.assertFalse(report["request"]["executionGate"]["executionAuthorized"])

    def test_request_blocks_on_unsafe_source_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            package_path = _write_json(tmp_path / "package.json", _package_payload(input_sent=True))

            report = request.build_report(_args(tmp_path, package_path))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("source-package-safety-inputSent-must-be-false", report["blockers"])
        self.assertFalse(report["request"]["executionGate"]["requestAcceptedForReview"])
        self.assertFalse(report["request"]["executionGate"]["executionAuthorized"])

    def test_request_report_schema_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            package_path = _write_json(tmp_path / "package.json", _package_payload())

            report = request.build_report(_args(tmp_path, package_path))
            schema = schema_validator.load_json_object(schema_validator.schema_path(REPO_ROOT, "navigation-live-run-request"))
            validation = schema_validator.validate_payload(report, schema)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["errors"], [])


if __name__ == "__main__":
    unittest.main()
