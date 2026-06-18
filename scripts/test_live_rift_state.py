#!/usr/bin/env python3
# Purpose: Regression tests for safe read-only live RIFT MCP state helpers.
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import live_rift_state  # noqa: E402


NOW = datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc)


def write_fixture_repo(
    root: Path,
    *,
    last_updated: str = "2026-06-18T12:30:00Z",
    target_pid: int | str = 130540,
) -> None:
    (root / ".git").mkdir()
    (root / "agents.md").write_text("# agents\n", encoding="utf-8")
    recovery = root / "docs" / "recovery"
    recovery.mkdir(parents=True)
    proof = {
        "schemaVersion": 1,
        "status": "current-target-proofonly-passed",
        "lastUpdatedUtc": last_updated,
        "target": {"processName": "rift_x64", "processId": target_pid, "targetWindowHandle": "0x9310EA"},
        "currentTruthClassification": {
            "classification": "current-live-target-proof-anchor",
            "savedVariablesUsedAsLiveTruth": False,
            "noCheatEngine": True,
        },
        "latestValidation": {
            "status": "valid",
            "movementSent": False,
            "currentCoordinate": {"x": 1.0, "y": 2.0, "z": 3.0, "recordedAtUtc": last_updated},
            "proofAnchorCandidateId": "api-family-hit-000001",
            "proofAnchorCandidateAddressHex": "0x1F342E20800",
            "readbackSummaryFile": "scripts/captures/readback-summary.json",
            "proofAnchorFile": "scripts/captures/telemetry-proof-coord-anchor.json",
            "generatedAtUtc": last_updated,
        },
        "latestProofOnly": {
            "status": "passed-proof-only",
            "generatedAtUtc": last_updated,
            "movementSent": False,
            "movementAttempted": False,
            "currentCoordinate": {"x": 1.0, "y": 2.0, "z": 3.0, "recordedAtUtc": last_updated},
            "coordinateDelta": None,
            "runSummaryFile": "scripts/captures/proofonly/run-summary.json",
            "readbackSummaryFile": "scripts/captures/readback-summary.json",
        },
    }
    (recovery / "current-proof-anchor-readback.json").write_text(json.dumps(proof), encoding="utf-8")
    profile = {
        "schemaVersion": 1,
        "kind": "riftreader-coordinate-recovery-profile",
        "target": {"pid": target_pid, "hwnd": "0x9310EA", "processName": "rift_x64"},
    }
    (recovery / "coordinate-recovery-profile.json").write_text(json.dumps(profile), encoding="utf-8")


def discovery_payload(*, pid: int = 130540, hwnd: str = "0x9310EA", module_base: str | None = "0x7FF6EE5D0000") -> dict:
    return {
        "mode": "rift-window-target-discovery",
        "status": "passed",
        "ok": True,
        "processName": "rift_x64",
        "count": 1,
        "windows": [
            {
                "ProcessId": pid,
                "ProcessName": "rift_x64",
                "WindowHandleHex": hwnd,
                "Title": "RIFT",
                "Foreground": False,
                "Left": 1,
                "Top": 3,
                "Right": 656,
                "Bottom": 401,
                "Width": 655,
                "Height": 398,
                "StartTime": "2026-06-17T21:57:01.8571209-04:00",
                "ModuleBaseAddressHex": module_base,
                "ModulePath": "C:\\Program Files (x86)\\Glyph\\Games\\RIFT\\Live\\rift_x64.exe",
                "Responding": True,
            }
        ],
        "blockers": [],
        "warnings": [],
    }


class LiveRiftStateTests(unittest.TestCase):
    def test_identity_gate_passes_with_fresh_exact_pid_hwnd_and_module_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = live_rift_state.build_live_target_identity_gate(
                root,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["exactTargetFacts"]["processId"], 130540)
        self.assertEqual(payload["exactTargetFacts"]["targetWindowHandle"], "0x9310EA")
        self.assertEqual(payload["exactTargetFacts"]["moduleBase"], "0x7FF6EE5D0000")
        self.assertFalse(payload["safety"]["inputSent"])
        self.assertFalse(payload["safety"]["movementSent"])
        self.assertFalse(payload["safety"]["savedVariablesUsedAsLiveTruth"])
        self.assertTrue(payload["safety"]["noCheatEngine"])
        self.assertFalse(payload["safety"]["x64dbgAttach"])

    def test_identity_gate_normalizes_string_pid_from_proof_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root, target_pid="130540")
            payload = live_rift_state.build_live_target_identity_gate(
                root,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["requestedTarget"]["processId"], 130540)
        self.assertEqual(payload["exactTargetFacts"]["processId"], 130540)

    def test_identity_gate_blocks_stale_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root, last_updated="2026-06-16T12:30:00Z")
            payload = live_rift_state.build_live_target_identity_gate(
                root,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("proof-anchor-stale:174600s>86400s", payload["blockers"])
        self.assertIsNone(payload["exactTargetFacts"])

    def test_identity_gate_blocks_mismatched_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = live_rift_state.build_live_target_identity_gate(
                root,
                discovery_payload=discovery_payload(hwnd="0xBAD"),
                now=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("exact-target-window-match-count-not-one:0", payload["blockers"])

    def test_readonly_state_withholds_coordinate_until_identity_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = live_rift_state.build_live_readonly_state(
                root,
                discovery_payload=discovery_payload(module_base=None),
                now=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["liveState"], {"withheldUntilIdentityGatePasses": True})
        self.assertIn("exact-target-module-base-missing", payload["blockers"])

    def test_no_input_proof_summary_is_available_only_after_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = live_rift_state.build_live_no_input_proof_status(
                root,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["proofSummary"]["latestProofOnly"]["status"], "passed-proof-only")
        self.assertFalse(payload["proofSummary"]["latestProofOnly"]["movementSent"])
        self.assertFalse(payload["safety"]["proofOnlyExecuted"])
        self.assertFalse(payload["safety"]["inputSent"])
        self.assertFalse(payload["safety"]["movementSent"])


if __name__ == "__main__":
    unittest.main()
