#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import facing_target_three_pose_gate as gate  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_route_step(root: Path, index: int, *, progress: float = 1.0, label: str = "current-facing-target-0x30C") -> Path:
    route_summary_path = root / "scripts" / "captures" / f"route-{index}" / "summary.json"
    write_json(
        route_summary_path,
        {
            "kind": "static-owner-nav-route",
            "status": "passed",
            "navigationTargetRequest": {
                "destinationLabel": label,
                "destinationX": 10.0 + index,
                "destinationY": 2.0,
                "destinationZ": 20.0 + index,
                "arrivalRadius": 2.5,
            },
            "safety": {"targetMemoryBytesRead": True},
        },
    )
    step_summary_path = root / "scripts" / "captures" / f"step-{index}" / "summary.json"
    write_json(
        step_summary_path,
        {
            "kind": "static-owner-nav-route-step",
            "status": "passed",
            "verdict": "route-step-live-movement-progress-validated",
            "generatedAtUtc": "2026-06-01T00:00:00Z",
            "initialDecision": {
                "suggestedTurnDirection": "aligned",
                "absoluteBearingDeltaDegrees": 0.0,
                "navStateAvailable": True,
                "navStateYawDegrees": 49.0,
                "navStateFacingTargetCoordinate": {"x": 10.0 + index, "y": 2.0, "z": 20.0 + index},
            },
            "routeResult": {
                "routeStatus": "progress",
                "totalProgressDistance": progress,
                "initialPlanarDistance": 10.0,
                "finalPlanarDistance": 10.0 - progress,
            },
            "safety": {
                "movementSent": True,
                "inputSent": True,
                "noCheatEngine": True,
                "proofPromotion": False,
                "facingPromotion": False,
                "providerWrites": False,
            },
            "artifacts": {"routeSummaryJson": str(route_summary_path)},
        },
    )
    return step_summary_path


class FacingTargetThreePoseGateTests(unittest.TestCase):
    def test_gate_passes_for_three_route_progress_poses_without_promoting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paths = [write_route_step(root, index) for index in range(3)]
            args = type(
                "Args",
                (),
                {
                    "route_step_summary_json": [str(path) for path in paths],
                    "minimum_progress_distance": 0.5,
                    "minimum_pose_count": 3,
                },
            )()

            summary, exit_code = gate.build_three_pose_gate(args, root, root / "scripts" / "captures" / "gate")

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", summary["status"])
        self.assertEqual("formal-three-pose-route-progress-gate-passed", summary["verdict"])
        self.assertEqual(3, summary["passedPoseCount"])
        self.assertTrue(summary["analysis"]["formalThreePoseGatePassed"])
        self.assertFalse(summary["analysis"]["promotionAllowed"])
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertTrue(summary["sourceSafety"]["inputSent"])
        self.assertTrue(summary["sourceSafety"]["movementSent"])

    def test_gate_blocks_when_pose_progress_is_too_small(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            paths = [write_route_step(root, 0, progress=0.1), write_route_step(root, 1), write_route_step(root, 2)]
            args = type(
                "Args",
                (),
                {
                    "route_step_summary_json": [str(path) for path in paths],
                    "minimum_progress_distance": 0.5,
                    "minimum_pose_count": 3,
                },
            )()

            summary, exit_code = gate.build_three_pose_gate(args, root, root / "scripts" / "captures" / "gate")

        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", summary["status"])
        self.assertTrue(any("route-progress-below-minimum" in item for item in summary["blockers"]))
        self.assertFalse(summary["analysis"]["formalThreePoseGatePassed"])

    def test_main_self_test_json_passes(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = gate.main(["--self-test", "--json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("passed", payload["status"])
        self.assertFalse(payload["checks"]["promotionAllowed"])
        self.assertFalse(payload["checks"]["helperInputSent"])


if __name__ == "__main__":
    unittest.main()
