from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from typing import Any
from unittest import mock

from scripts import navigation_waypoint_readiness as readiness


def _args(tmp_path: Path, waypoint_file: Path, **overrides: Any) -> Namespace:
    data: dict[str, Any] = {
        "repo_root": str(tmp_path),
        "output_root": str(tmp_path / "out"),
        "waypoint_sequence_json": str(waypoint_file),
        "waypoint_sequence_ids": None,
        "current_truth_json": str(tmp_path / "docs" / "recovery" / "current-truth.json"),
        "default_arrival_radius": 2.0,
        "command_timeout_seconds": 30.0,
        "skip_dry_run": True,
        "json": True,
    }
    data.update(overrides)
    return Namespace(**data)


def _write_waypoints(path: Path, waypoints: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schemaVersion": 1, "waypoints": waypoints}), encoding="utf-8")


class NavigationWaypointReadinessTests(unittest.TestCase):
    def test_lint_normalizes_radius_alias_and_generated_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            waypoint_file = tmp_path / "waypoints.json"
            _write_waypoints(
                waypoint_file,
                [
                    {"label": "Start", "x": 1.0, "y": 2.0, "z": 3.0, "radius": 1.25},
                ],
            )

            result = readiness.run(_args(tmp_path, waypoint_file))

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["verdict"], "waypoint-readiness-lint-passed")
            normalized_path = Path(result["artifacts"]["normalizedWaypointJson"])
            normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
            self.assertEqual(normalized["waypoints"][0]["id"], "waypoint-001")
            self.assertEqual(normalized["waypoints"][0]["arrivalRadius"], 1.25)
            self.assertIn("waypoint-1-legacy-radius-normalized-to-arrivalRadius", result["warnings"])

    def test_duplicate_id_blocks_before_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            waypoint_file = tmp_path / "waypoints.json"
            _write_waypoints(
                waypoint_file,
                [
                    {"id": "dup", "x": 1.0, "y": 2.0, "z": 3.0},
                    {"id": "dup", "x": 4.0, "y": 5.0, "z": 6.0},
                ],
            )

            result = readiness.run(_args(tmp_path, waypoint_file, skip_dry_run=False))

            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["verdict"], "waypoint-readiness-lint-blocked")
            self.assertIn("waypoint-id-duplicate:dup", result["blockers"])
            self.assertEqual(result["childCommands"], [])

    def test_filters_requested_ids_into_normalized_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            waypoint_file = tmp_path / "waypoints.json"
            _write_waypoints(
                waypoint_file,
                [
                    {"id": "a", "x": 1.0, "y": 2.0, "z": 3.0},
                    {"id": "b", "x": 4.0, "y": 5.0, "z": 6.0},
                ],
            )

            result = readiness.run(_args(tmp_path, waypoint_file, waypoint_sequence_ids="b,a"))

            self.assertEqual(result["status"], "passed")
            normalized = json.loads(Path(result["artifacts"]["normalizedWaypointJson"]).read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in normalized["waypoints"]], ["b", "a"])

    def test_dry_run_and_contract_children_make_consumable_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            waypoint_file = tmp_path / "waypoints.json"
            _write_waypoints(
                waypoint_file,
                [
                    {"id": "a", "x": 1.0, "y": 2.0, "z": 3.0},
                    {"id": "b", "x": 4.0, "y": 5.0, "z": 6.0},
                ],
            )

            def fake_run_child(*, label: str, command: list[str], cwd: Path,
                               child_dir: Path, timeout_seconds: float) -> dict[str, Any]:
                if label == "sequence-dry-run":
                    return {
                        "label": label,
                        "ok": True,
                        "exitCode": 0,
                        "json": {
                            "status": "passed",
                            "verdict": "sequence-dry-run-plan-built",
                            "summaryJson": str(tmp_path / "sequence-summary.json"),
                            "summaryMarkdown": str(tmp_path / "sequence-summary.md"),
                        },
                    }
                if label == "sequence-contract":
                    return {
                        "label": label,
                        "ok": True,
                        "exitCode": 0,
                        "json": {
                            "status": "passed",
                            "consumable": True,
                            "summaryJson": str(tmp_path / "contract-summary.json"),
                            "summaryMarkdown": str(tmp_path / "contract-summary.md"),
                            "blockers": [],
                            "warnings": [],
                        },
                    }
                raise AssertionError(label)

            with mock.patch.object(readiness, "run_child", side_effect=fake_run_child):
                result = readiness.run(_args(tmp_path, waypoint_file, skip_dry_run=False))

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["verdict"], "waypoint-readiness-consumable")
            self.assertEqual(result["dryRun"]["verdict"], "sequence-dry-run-plan-built")
            self.assertTrue(result["contract"]["consumable"])
            self.assertFalse(result["safety"]["inputSent"])
            self.assertFalse(result["safety"]["movementSent"])
            self.assertTrue(result["safety"]["targetMemoryBytesRead"])


if __name__ == "__main__":
    unittest.main()
