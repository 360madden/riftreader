from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any

from scripts import navigation_consumer_demo as demo
from scripts import navigation_schema_validate as schema_validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _args(tmp_path: Path, consumer: Path, readiness: Path, **overrides: Any) -> Namespace:
    data: dict[str, Any] = {
        "repo_root": str(REPO_ROOT),
        "output_root": str(tmp_path / "out"),
        "consumer_state_json": str(consumer),
        "waypoint_readiness_json": str(readiness),
        "normalized_waypoints_json": None,
        "sequence_summary_json": None,
        "contract_report_json": None,
        "max_consumer_state_age_seconds": 60.0,
        "require_fresh_pose": False,
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


def _waypoints() -> list[dict[str, Any]]:
    return [
        {"id": "a", "label": "A", "x": 1.0, "y": 2.0, "z": 3.0, "arrivalRadius": 2.0},
        {"id": "b", "label": "B", "x": 4.0, "y": 2.0, "z": 6.0, "arrivalRadius": 2.0},
    ]


def _consumer_state(generated_at: str | None = None, *, input_sent: bool = False) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-consumer-state",
        "generatedAtUtc": generated_at or demo.utc_iso(),
        "status": "passed",
        "verdict": "consumer-navigation-state-ready",
        "target": {"processName": "rift_x64", "processId": 1234, "targetWindowHandle": "0x123"},
        "consumerContract": {
            "version": "navigation-consumer-state/v1",
            "readOnly": True,
            "maxConsumerAgeSeconds": 60.0,
            "requiredConsumerChecks": ["reject-status-other-than-passed"],
        },
        "navigation": {
            "position": {
                "state": "promoted",
                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                "sourceOffset": "0x320",
            },
            "orientation": {
                "state": "promoted",
                "chain": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
                "yawDegrees": 45.0,
                "pitchDegrees": 0.0,
                "sourceOffset": "0x30C",
            },
            "diagnostics": {},
            "routeControl": {"authorized": False, "movementPermission": False, "turnPermission": False},
        },
        "safety": {
            "movementSent": False,
            "inputSent": input_sent,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "x64dbgAttach": False,
        },
        "blockers": [],
        "warnings": [],
        "errors": [],
    }


def _normalized_waypoints() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "provenance": {
            "kind": "riftreader-normalized-navigation-waypoints",
            "generatedAtUtc": demo.utc_iso(),
            "inputJson": "waypoints.json",
            "defaultArrivalRadius": 2.0,
            "requestedWaypointIds": None,
        },
        "waypoints": _waypoints(),
    }


def _sequence_summary() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "static-owner-continuous-route-sequence",
        "generatedAtUtc": demo.utc_iso(),
        "status": "passed",
        "verdict": "sequence-dry-run-plan-built",
        "operator": {
            "dryRun": True,
            "movementApproved": False,
            "turnApproved": False,
            "allowCandidateTurnControl": False,
        },
        "waypointSequence": _waypoints(),
        "legs": [
            {
                "status": "passed",
                "verdict": "dry-run-plan-built",
                "safety": {"movementSent": False, "inputSent": False, "navigationControl": False},
            }
        ],
        "total": {"totalLegs": 2, "legsPlanned": 1, "legsArrived": 0, "legsFailed": 0},
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "navigationControl": False,
            "providerWrites": False,
            "x64dbgAttach": False,
        },
        "artifacts": {"summaryJson": "sequence.json", "summaryMarkdown": "sequence.md"},
        "blockers": [],
        "warnings": [],
        "errors": [],
    }


def _contract_report(sequence_path: Path) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "static-owner-continuous-route-sequence-contract-report",
        "generatedAtUtc": demo.utc_iso(),
        "status": "passed",
        "sourceSummaryJson": str(sequence_path),
        "source": {
            "kind": "static-owner-continuous-route-sequence",
            "status": "passed",
            "verdict": "sequence-dry-run-plan-built",
            "totalLegs": 2,
            "legsPlanned": 1,
            "legsArrived": 0,
            "legsFailed": 0,
        },
        "contract": {
            "status": "passed",
            "consumable": True,
            "acceptedSequenceVerdicts": ["sequence-dry-run-plan-built"],
            "acceptedLegVerdicts": ["dry-run-plan-built"],
            "totalLegs": 2,
            "legsPlanned": 1,
            "legsArrived": 0,
            "legsFailed": 0,
            "recordedLegs": 1,
            "firstUnreachedLegIndex": 1,
            "blockers": [],
            "warnings": [],
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "x64dbgAttach": False,
        },
        "artifacts": {"summaryJson": "contract.json", "summaryMarkdown": "contract.md"},
        "blockers": [],
        "warnings": [],
        "errors": [],
    }


def _readiness(normalized: Path, sequence: Path, contract: Path) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-waypoint-readiness",
        "generatedAtUtc": demo.utc_iso(),
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
            "normalizedWaypoints": _waypoints(),
            "blockers": [],
            "warnings": [],
        },
        "dryRun": {
            "status": "passed",
            "verdict": "sequence-dry-run-plan-built",
            "summaryJson": str(sequence),
            "summaryMarkdown": "sequence.md",
        },
        "contract": {
            "status": "passed",
            "consumable": True,
            "summaryJson": str(contract),
            "summaryMarkdown": "contract.md",
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
            "normalizedWaypointJson": str(normalized),
        },
        "blockers": [],
        "warnings": [],
        "errors": [],
    }


def _fixture_files(tmp_path: Path, *, consumer: dict[str, Any] | None = None) -> tuple[Path, Path]:
    consumer_path = _write_json(tmp_path / "consumer.json", consumer or _consumer_state())
    normalized_path = _write_json(tmp_path / "normalized.json", _normalized_waypoints())
    sequence_path = _write_json(tmp_path / "sequence.json", _sequence_summary())
    contract_path = _write_json(tmp_path / "contract.json", _contract_report(sequence_path))
    readiness_path = _write_json(tmp_path / "readiness.json", _readiness(normalized_path, sequence_path, contract_path))
    return consumer_path, readiness_path


class NavigationConsumerDemoTests(unittest.TestCase):
    def test_saved_artifacts_make_render_and_dry_run_ready_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            consumer_path, readiness_path = _fixture_files(tmp_path)

            report = demo.build_report(_args(tmp_path, consumer_path, readiness_path))

        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["capabilities"]["canRenderRoute"])
        self.assertTrue(report["capabilities"]["canUseDryRunContract"])
        self.assertTrue(report["capabilities"]["canQueueGatedLiveRunRequest"])
        self.assertFalse(report["capabilities"]["canExecuteLiveNavigation"])
        self.assertFalse(report["safety"]["inputSent"])
        self.assertFalse(report["safety"]["targetMemoryBytesRead"])

    def test_stale_pose_warns_and_disables_live_queue_without_blocking_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            old_consumer = _consumer_state(generated_at="2020-01-01T00:00:00+00:00")
            consumer_path, readiness_path = _fixture_files(tmp_path, consumer=old_consumer)

            report = demo.build_report(_args(tmp_path, consumer_path, readiness_path))

        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["capabilities"]["canRenderRoute"])
        self.assertFalse(report["capabilities"]["canQueueGatedLiveRunRequest"])
        self.assertTrue(any(item.startswith("consumer-state-stale:") for item in report["warnings"]))

    def test_require_fresh_pose_blocks_on_stale_consumer_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            old_consumer = _consumer_state(generated_at="2020-01-01T00:00:00+00:00")
            consumer_path, readiness_path = _fixture_files(tmp_path, consumer=old_consumer)

            report = demo.build_report(_args(tmp_path, consumer_path, readiness_path, require_fresh_pose=True))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("navigation-consumer-demo-blocked", report["verdict"])
        self.assertTrue(any(item.startswith("consumer-state-stale:") for item in report["blockers"]))

    def test_unsafe_source_artifact_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            consumer_path, readiness_path = _fixture_files(tmp_path, consumer=_consumer_state(input_sent=True))

            report = demo.build_report(_args(tmp_path, consumer_path, readiness_path))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("consumer-state-source-safety-inputSent-must-be-false", report["blockers"])

    def test_report_schema_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            consumer_path, readiness_path = _fixture_files(tmp_path)
            report = demo.build_report(_args(tmp_path, consumer_path, readiness_path))
            schema = schema_validator.load_json_object(
                schema_validator.schema_path(REPO_ROOT, "navigation-consumer-demo")
            )

            validation = schema_validator.validate_payload(report, schema)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["errors"], [])


if __name__ == "__main__":
    unittest.main()
