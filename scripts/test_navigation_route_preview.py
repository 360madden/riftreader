from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any

from scripts import navigation_route_preview as preview
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
        "max_consumer_state_age_seconds": 60.0,
        "alignment_threshold_degrees": 7.5,
        "require_fresh_pose": False,
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


def _waypoints() -> list[dict[str, Any]]:
    return [
        {"id": "a", "label": "A", "x": 10.0, "y": 0.0, "z": 0.0, "arrivalRadius": 1.0},
        {"id": "b", "label": "B", "x": 10.0, "y": 0.0, "z": 10.0, "arrivalRadius": 2.0},
    ]


def _consumer_state(
    *,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    yaw_degrees: float = 0.0,
    generated_at: str | None = None,
    input_sent: bool = False,
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-consumer-state",
        "generatedAtUtc": generated_at or preview.utc_iso(),
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
                "coordinate": {"x": x, "y": y, "z": z},
                "sourceOffset": "0x320",
            },
            "orientation": {
                "state": "promoted",
                "chain": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
                "yawDegrees": yaw_degrees,
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
            "generatedAtUtc": preview.utc_iso(),
            "inputJson": "waypoints.json",
            "defaultArrivalRadius": 2.0,
            "requestedWaypointIds": None,
        },
        "waypoints": _waypoints(),
    }


def _readiness(normalized: Path) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-waypoint-readiness",
        "generatedAtUtc": preview.utc_iso(),
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
            "summaryJson": "sequence.json",
            "summaryMarkdown": "sequence.md",
        },
        "contract": {
            "status": "passed",
            "consumable": True,
            "summaryJson": "contract.json",
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
    readiness_path = _write_json(tmp_path / "readiness.json", _readiness(normalized_path))
    return consumer_path, readiness_path


class NavigationRoutePreviewTests(unittest.TestCase):
    def test_route_preview_builds_current_pose_first_leg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            consumer_path, readiness_path = _fixture_files(tmp_path)

            report = preview.build_report(_args(tmp_path, consumer_path, readiness_path))

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["route"]["waypointCount"], 2)
        self.assertEqual(report["route"]["legCount"], 2)
        self.assertFalse(report["route"]["routeComplete"])
        self.assertEqual(report["route"]["nextWaypointId"], "a")
        self.assertAlmostEqual(report["route"]["activeLeg"]["planarDistance"], 10.0)
        self.assertAlmostEqual(report["route"]["activeLeg"]["bearingDegrees"], 0.0)
        self.assertAlmostEqual(report["route"]["activeLeg"]["initialYawDeltaDegrees"], 0.0)
        self.assertEqual(report["route"]["activeLeg"]["suggestedInitialTurnDirection"], "aligned")
        self.assertTrue(report["capabilities"]["canRenderRoutePreview"])
        self.assertTrue(report["capabilities"]["canQueueGatedLiveRunRequest"])
        self.assertFalse(report["capabilities"]["canExecuteLiveNavigation"])
        self.assertFalse(report["safety"]["targetMemoryBytesRead"])

    def test_route_preview_skips_arrived_waypoint_for_active_leg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            consumer_path, readiness_path = _fixture_files(tmp_path, consumer=_consumer_state(x=10.0, z=0.0))

            report = preview.build_report(_args(tmp_path, consumer_path, readiness_path))

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["route"]["nextWaypointId"], "b")
        self.assertEqual(report["route"]["legCount"], 1)
        self.assertAlmostEqual(report["route"]["activeLeg"]["bearingDegrees"], 90.0)
        self.assertAlmostEqual(report["route"]["activeLeg"]["initialYawDeltaDegrees"], 90.0)
        self.assertEqual(report["route"]["activeLeg"]["suggestedInitialTurnDirection"], "right")

    def test_stale_pose_warns_and_disables_live_queue_without_blocking_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            old_consumer = _consumer_state(generated_at="2020-01-01T00:00:00+00:00")
            consumer_path, readiness_path = _fixture_files(tmp_path, consumer=old_consumer)

            report = preview.build_report(_args(tmp_path, consumer_path, readiness_path))

        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["capabilities"]["canRenderRoutePreview"])
        self.assertFalse(report["capabilities"]["canQueueGatedLiveRunRequest"])
        self.assertTrue(any(item.startswith("consumer-state-stale:") for item in report["warnings"]))

    def test_route_preview_report_schema_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            consumer_path, readiness_path = _fixture_files(tmp_path)

            report = preview.build_report(_args(tmp_path, consumer_path, readiness_path))
            schema = schema_validator.load_json_object(schema_validator.schema_path(REPO_ROOT, "navigation-route-preview"))
            validation = schema_validator.validate_payload(report, schema)

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["errors"], [])


if __name__ == "__main__":
    unittest.main()
