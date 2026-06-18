#!/usr/bin/env python3
# Purpose: Regression tests for Stage 42 plan-only live-control MCP helper.
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

from riftreader_workflow import live_control_plan  # noqa: E402


NOW = datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc)


def write_fixture_repo(root: Path) -> None:
    (root / ".git").mkdir()
    recovery = root / "docs" / "recovery"
    recovery.mkdir(parents=True)
    proof = {
        "schemaVersion": 1,
        "status": "current-target-proofonly-passed",
        "lastUpdatedUtc": "2026-06-18T12:30:00Z",
        "target": {"processName": "rift_x64", "processId": 130540, "targetWindowHandle": "0x9310EA"},
        "currentTruthClassification": {
            "classification": "current-live-target-proof-anchor",
            "savedVariablesUsedAsLiveTruth": False,
            "noCheatEngine": True,
        },
        "latestValidation": {
            "status": "valid",
            "movementSent": False,
            "currentCoordinate": {"x": 1.0, "y": 2.0, "z": 3.0, "recordedAtUtc": "2026-06-18T12:30:00Z"},
            "generatedAtUtc": "2026-06-18T12:30:00Z",
        },
        "latestProofOnly": {
            "status": "passed-proof-only",
            "generatedAtUtc": "2026-06-18T12:30:00Z",
            "movementSent": False,
            "movementAttempted": False,
            "currentCoordinate": {"x": 1.0, "y": 2.0, "z": 3.0, "recordedAtUtc": "2026-06-18T12:30:00Z"},
        },
    }
    (recovery / "current-proof-anchor-readback.json").write_text(json.dumps(proof), encoding="utf-8")
    profile = {
        "schemaVersion": 1,
        "kind": "riftreader-coordinate-recovery-profile",
        "target": {"pid": 130540, "hwnd": "0x9310EA", "processName": "rift_x64"},
    }
    (recovery / "coordinate-recovery-profile.json").write_text(json.dumps(profile), encoding="utf-8")


def discovery_payload() -> dict[str, object]:
    return {
        "mode": "rift-window-target-discovery",
        "status": "passed",
        "ok": True,
        "processName": "rift_x64",
        "count": 1,
        "windows": [
            {
                "ProcessId": 130540,
                "ProcessName": "rift_x64",
                "WindowHandleHex": "0x9310EA",
                "Title": "RIFT",
                "Foreground": True,
                "StartTime": "2026-06-17T21:57:01.8571209-04:00",
                "ModuleBaseAddressHex": "0x7FF6EE5D0000",
                "ModulePath": "C:\\Program Files (x86)\\Glyph\\Games\\RIFT\\Live\\rift_x64.exe",
                "Responding": True,
            }
        ],
        "blockers": [],
        "warnings": [],
    }


class LiveControlPlanTests(unittest.TestCase):
    def test_movement_key_plan_writes_ignored_artifact_without_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = live_control_plan.build_live_control_plan(
                root,
                key_chord="W",
                hold_milliseconds=250,
                target_identity={"processId": 130540, "targetWindowHandle": "0x9310EA"},
                verification_requirements={"postAction": ["get_live_no_input_proof_status"]},
                discovery_payload=discovery_payload(),
                now=NOW,
            )

            plan_path = root / payload["artifact"]["planPath"]
            markdown_path = root / payload["artifact"]["planMarkdownPath"]
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["status"], "planned")
            self.assertEqual(payload["riskClass"], "movement-risk")
            self.assertTrue(payload["movementRisk"])
            self.assertEqual(payload["requestedAction"]["primitiveTool"], "hold_key:W")
            self.assertTrue(str(payload["artifact"]["planPath"]).startswith(".riftreader-local"))
            self.assertTrue(plan_path.is_file())
            self.assertTrue(markdown_path.is_file())
            artifact_payload = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact_payload["planHash"], payload["planHash"])
            self.assertIn(payload["planHash"][:16], payload["approvalPacket"]["humanPrompt"])
            self.assertFalse(payload["safety"]["inputSent"])
            self.assertFalse(payload["safety"]["movementSent"])
            self.assertFalse(payload["safety"]["reusableApprovalTokenCreated"])
            self.assertTrue(payload["safety"]["noCheatEngine"])
            self.assertFalse(payload["safety"]["x64dbgAttach"])
            self.assertFalse(payload["safety"]["savedVariablesUsedAsLiveTruth"])

    def test_inventory_action_is_ui_risk_not_movement(self) -> None:
        classification = live_control_plan.classify_action(
            action_kind=None,
            semantic_action="open-inventory",
            key_chord=None,
        )

        self.assertTrue(classification["ok"], classification)
        self.assertEqual(classification["actionKind"], "ui-action")
        self.assertEqual(classification["riskClass"], "semantic-ui-action-risk")
        self.assertFalse(classification["movementRisk"])
        self.assertEqual(classification["primitiveTool"], "send_key:I")
        self.assertTrue(classification["blockedByDefault"])

    def test_target_identity_mismatch_blocks_plan_but_still_sends_no_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = live_control_plan.build_live_control_plan(
                root,
                semantic_action="hotbar-1",
                target_identity={"processId": 999999, "targetWindowHandle": "0xBAD"},
                discovery_payload=discovery_payload(),
                now=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("target-identity-mismatch:processId", payload["blockers"])
        self.assertIn("target-identity-mismatch:targetWindowHandle", payload["blockers"])
        self.assertFalse(payload["movementRisk"])
        self.assertFalse(payload["safety"]["inputSent"])
        self.assertFalse(payload["safety"]["movementSent"])

    def test_dry_run_false_is_blocked_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = live_control_plan.build_live_control_plan(
                root,
                key_chord="Space",
                dry_run=False,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("live-plan-dry-run-required", payload["blockers"])
        self.assertTrue(payload["movementRisk"])
        self.assertFalse(payload["safety"]["inputSent"])
        self.assertFalse(payload["safety"]["movementSent"])


if __name__ == "__main__":
    unittest.main()
