from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any

from scripts import navigation_schema_validate as validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def _args(input_path: Path, output_root: Path, **overrides: Any) -> Namespace:
    data: dict[str, Any] = {
        "repo_root": str(REPO_ROOT),
        "output_root": str(output_root),
        "input": str(input_path),
        "schema_key": None,
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


def _load_schema(key: str) -> dict[str, Any]:
    return validator.load_json_object(validator.schema_path(REPO_ROOT, key))


def _valid_waypoint_readiness() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-waypoint-readiness",
        "generatedAtUtc": "2026-06-02T00:00:00Z",
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
            "originalWaypointCount": 1,
            "selectedWaypointCount": 1,
            "defaultArrivalRadius": 2.0,
            "requestedWaypointIds": None,
            "normalizedWaypoints": [
                {
                    "id": "a",
                    "label": "A",
                    "x": 1.0,
                    "y": 2.0,
                    "z": 3.0,
                    "arrivalRadius": 2.0,
                }
            ],
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
            "summaryJson": "summary.json",
            "summaryMarkdown": "summary.md",
            "normalizedWaypointJson": "normalized-waypoints.json",
        },
        "blockers": [],
        "warnings": [],
        "errors": [],
    }


def _valid_normalized_waypoints() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "provenance": {
            "kind": "riftreader-normalized-navigation-waypoints",
            "generatedAtUtc": "2026-06-02T00:00:00Z",
            "inputJson": "waypoints.json",
            "defaultArrivalRadius": 2.0,
            "requestedWaypointIds": None,
        },
        "waypoints": [
            {
                "id": "a",
                "label": "A",
                "x": 1.0,
                "y": 2.0,
                "z": 3.0,
                "arrivalRadius": 2.0,
            }
        ],
    }


class NavigationSchemaValidateTests(unittest.TestCase):
    def test_infers_and_validates_waypoint_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload_path = tmp_path / "readiness.json"
            payload_path.write_text(json.dumps(_valid_waypoint_readiness()), encoding="utf-8")

            report = validator.build_report(_args(payload_path, tmp_path / "out"))

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["schemaKey"], "navigation-waypoint-readiness")
        self.assertEqual(report["inputKind"], "riftreader-navigation-waypoint-readiness")
        self.assertEqual(report["validation"]["errorCount"], 0)
        self.assertFalse(report["safety"]["inputSent"])
        self.assertTrue(report["safety"]["readOnlySavedJson"])

    def test_normalized_waypoints_infers_from_provenance_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload_path = tmp_path / "normalized-waypoints.json"
            payload_path.write_text(json.dumps(_valid_normalized_waypoints()), encoding="utf-8")

            report = validator.build_report(_args(payload_path, tmp_path / "out"))

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["schemaKey"], "normalized-waypoints")
        self.assertEqual(report["inputKind"], "riftreader-normalized-navigation-waypoints")

    def test_missing_required_field_blocks(self) -> None:
        payload = _valid_waypoint_readiness()
        payload.pop("safety")

        result = validator.validate_payload(payload, _load_schema("navigation-waypoint-readiness"))

        self.assertEqual(result["status"], "blocked")
        self.assertIn("$.safety:required-missing", result["errors"])

    def test_const_mismatch_blocks_unsafe_saved_payload(self) -> None:
        payload = _valid_waypoint_readiness()
        payload["safety"]["inputSent"] = True

        result = validator.validate_payload(payload, _load_schema("navigation-waypoint-readiness"))

        self.assertEqual(result["status"], "blocked")
        self.assertIn("$.safety.inputSent:const-mismatch:expected=False:actual=True", result["errors"])

    def test_non_finite_numbers_are_not_valid_numbers(self) -> None:
        payload = _valid_waypoint_readiness()
        payload["lint"]["normalizedWaypoints"][0]["x"] = float("nan")

        result = validator.validate_payload(payload, _load_schema("navigation-waypoint-readiness"))

        self.assertEqual(result["status"], "blocked")
        self.assertIn("$.lint.normalizedWaypoints[0].x:type-mismatch:expected=number:actual=number", result["errors"])

    def test_unknown_kind_blocks_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload_path = tmp_path / "unknown.json"
            payload_path.write_text(json.dumps({"kind": "unknown"}), encoding="utf-8")

            report = validator.build_report(_args(payload_path, tmp_path / "out"))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("schema-key-not-provided-and-kind-not-recognized", report["blockers"])


if __name__ == "__main__":
    unittest.main()
