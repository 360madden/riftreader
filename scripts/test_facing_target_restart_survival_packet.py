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

import facing_target_restart_survival_packet as packet  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_nav_state(root: Path, label: str, *, pid: int, process_start: str, owner_address: str = "0x1000") -> Path:
    path = root / "scripts" / "captures" / f"nav-{label}" / "summary.json"
    write_json(
        path,
        {
            "kind": "static-owner-nav-state-readback",
            "status": "passed",
            "verdict": "position-and-facing-nav-state-readback-passed",
            "generatedAtUtc": process_start,
            "target": {
                "processName": "rift_x64",
                "processId": pid,
                "targetWindowHandle": f"0x{pid:X}",
                "actualProcessStartUtc": process_start,
                "expectedProcessStartUtc": process_start,
                "moduleBase": "0x7FF600000000",
            },
            "latestState": {
                "ownerAddress": owner_address,
                "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                "facingTargetCoordinate": {"x": 10.0, "y": 2.0, "z": 20.0},
                "positionOffset": "0x320",
                "facingTargetOffset": "0x30C",
                "turnRateOffset": "0x304",
            },
            "safety": {
                "targetMemoryBytesRead": True,
                "targetMemoryBytesWritten": False,
                "movementSent": False,
                "inputSent": False,
                "proofPromotion": False,
                "facingPromotion": False,
            },
        },
    )
    return path


class FacingTargetRestartSurvivalPacketTests(unittest.TestCase):
    def test_packet_passes_for_distinct_process_epochs_and_stable_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            pre = write_nav_state(root, "pre", pid=100, process_start="2026-06-01T00:00:00Z", owner_address="0x1000")
            post = write_nav_state(root, "post", pid=200, process_start="2026-06-01T00:10:00Z", owner_address="0x2000")
            args = type(
                "Args",
                (),
                {"pre_restart_nav_summary_json": str(pre), "post_restart_nav_summary_json": str(post)},
            )()

            summary, exit_code = packet.build_restart_survival_packet(args, root, root / "scripts" / "captures" / "packet")

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", summary["status"])
        self.assertTrue(summary["analysis"]["restartRelogSurvived"])
        self.assertTrue(summary["analysis"]["processStartChanged"])
        self.assertTrue(summary["analysis"]["offsetsStable"])
        self.assertFalse(summary["analysis"]["promotionAllowed"])
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertTrue(summary["sourceSafety"]["targetMemoryBytesRead"])

    def test_packet_blocks_when_process_epoch_did_not_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            pre = write_nav_state(root, "pre", pid=100, process_start="2026-06-01T00:00:00Z")
            post = write_nav_state(root, "post", pid=100, process_start="2026-06-01T00:00:00Z")
            args = type(
                "Args",
                (),
                {"pre_restart_nav_summary_json": str(pre), "post_restart_nav_summary_json": str(post)},
            )()

            summary, exit_code = packet.build_restart_survival_packet(args, root, root / "scripts" / "captures" / "packet")

        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", summary["status"])
        self.assertIn("process-start-not-changed-or-missing", summary["blockers"])
        self.assertFalse(summary["analysis"]["restartRelogSurvived"])

    def test_main_self_test_json_passes(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = packet.main(["--self-test", "--json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("passed", payload["status"])
        self.assertTrue(payload["checks"]["restartRelogSurvived"])
        self.assertFalse(payload["checks"]["promotionAllowed"])
        self.assertFalse(payload["checks"]["helperInputSent"])


if __name__ == "__main__":
    unittest.main()
