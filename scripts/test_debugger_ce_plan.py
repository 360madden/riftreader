#!/usr/bin/env python3
# Purpose: Regression tests for Stage 45 debugger/CE plan-only MCP helper.
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

from riftreader_workflow import debugger_ce_plan  # noqa: E402


NOW = datetime(2026, 6, 18, 14, 0, tzinfo=timezone.utc)


def write_fixture_repo(root: Path) -> None:
    (root / ".git").mkdir()
    recovery = root / "docs" / "recovery"
    recovery.mkdir(parents=True)
    proof = {
        "schemaVersion": 1,
        "status": "current-target-proofonly-passed",
        "lastUpdatedUtc": "2026-06-18T13:30:00Z",
        "target": {"processName": "rift_x64", "processId": 130540, "targetWindowHandle": "0x9310EA"},
        "currentTruthClassification": {
            "classification": "current-live-target-proof-anchor",
            "savedVariablesUsedAsLiveTruth": False,
            "noCheatEngine": True,
        },
        "latestValidation": {
            "status": "valid",
            "movementSent": False,
            "currentCoordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
            "generatedAtUtc": "2026-06-18T13:30:00Z",
        },
        "latestProofOnly": {
            "status": "passed-proof-only",
            "generatedAtUtc": "2026-06-18T13:30:00Z",
            "movementSent": False,
            "movementAttempted": False,
            "currentCoordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
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


class DebuggerCePlanTests(unittest.TestCase):
    def test_static_review_plan_writes_ignored_artifact_without_attach_or_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = debugger_ce_plan.build_debugger_ce_plan(
                root,
                action_kind="static-review",
                question="Review prior static offset notes for a yaw candidate.",
                static_evidence={"doc": "tracked-notes"},
                now=NOW,
            )

            plan_path = root / payload["artifact"]["planPath"]
            markdown_path = root / payload["artifact"]["planMarkdownPath"]
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["status"], "planned")
            self.assertEqual(payload["riskClass"], "static-review")
            self.assertFalse(payload["movementRisk"])
            self.assertTrue(str(payload["artifact"]["planPath"]).startswith(".riftreader-local"))
            self.assertTrue(plan_path.is_file())
            self.assertTrue(markdown_path.is_file())
            artifact_payload = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact_payload["planHash"], payload["planHash"])
            self.assertFalse(payload["safety"]["inputSent"])
            self.assertFalse(payload["safety"]["movementSent"])
            self.assertTrue(payload["safety"]["noCheatEngine"])
            self.assertFalse(payload["safety"]["x64dbgAttach"])
            self.assertFalse(payload["safety"]["debuggerAttached"])
            self.assertFalse(payload["safety"]["breakpointsSet"])
            self.assertFalse(payload["safety"]["watchpointsSet"])
            self.assertFalse(payload["safety"]["targetMemoryBytesWritten"])

    def test_x64dbg_watchpoint_plan_requires_approval_but_still_does_not_attach(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = debugger_ce_plan.build_debugger_ce_plan(
                root,
                action_kind="watchpoint",
                target_tool="x64dbg",
                requested_action="Plan a watchpoint on a candidate read-only coordinate address.",
                question="Would a watchpoint help classify this candidate?",
                target_identity={"processId": 130540, "targetWindowHandle": "0x9310EA"},
                candidate_evidence={"candidateAddress": "0x12345678"},
                max_duration_seconds=60,
                stop_condition="detach immediately after one read trap or 60 seconds",
                crash_risk_acknowledged=True,
                static_first_reviewed=True,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["riskClass"], "debugger-attach-plan")
            self.assertTrue(payload["classification"]["requiresApproval"])
            self.assertTrue(payload["classification"]["blockedByDefault"])
            self.assertFalse(payload["executionReadiness"]["canExecuteFromThisTool"])
            self.assertIn("DEBUGGER_STAGE45_PLAN_ONLY_NO_EXECUTION_TOOL", payload["executionReadiness"]["executionBlockers"])
            self.assertIn(payload["planHash"][:16], payload["approvalPacket"]["humanPrompt"])
            self.assertFalse(payload["safety"]["debuggerAttached"])
            self.assertFalse(payload["safety"]["targetMemoryBytesRead"])
            self.assertFalse(payload["safety"]["targetMemoryBytesWritten"])

    def test_attach_plan_blocks_without_static_first_crash_ack_stop_and_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = debugger_ce_plan.build_debugger_ce_plan(
                root,
                action_kind="debugger-attach",
                target_tool="x64dbg",
                requested_action="Attach debugger now.",
                discovery_payload={"ok": False, "blockers": ["no-live-target"], "windows": []},
                now=NOW,
            )

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["status"], "blocked")
            self.assertIn("DEBUGGER_STATIC_FIRST_REQUIRED", payload["blockers"])
            self.assertIn("DEBUGGER_CRASH_RISK_NOT_ACKNOWLEDGED", payload["blockers"])
            self.assertIn("DEBUGGER_STOP_CONDITION_MISSING", payload["blockers"])
            self.assertIn("DEBUGGER_TARGET_NOT_BOUND", payload["blockers"])
            self.assertFalse(payload["safety"]["debuggerAttached"])
            self.assertFalse(payload["safety"]["inputSent"])

    def test_cheat_engine_scan_classifies_as_ce_plan_not_movement(self) -> None:
        classification = debugger_ce_plan.classify_debugger_ce_action(
            action_kind="scan",
            target_tool="Cheat Engine",
            requested_action="plan an unknown-value scan",
        )

        self.assertTrue(classification["ok"], classification)
        self.assertEqual(classification["riskClass"], "ce-attach-plan")
        self.assertFalse(classification["movementRisk"])
        self.assertTrue(classification["requiresApproval"])
        self.assertTrue(classification["blockedByDefault"])
        self.assertFalse(classification["safety"]["inputSent"])
        self.assertTrue(classification["safety"]["noCheatEngine"])

    def test_dry_run_false_is_blocked_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = debugger_ce_plan.build_debugger_ce_plan(
                root,
                action_kind="candidate-triage",
                question="Review candidate evidence only.",
                dry_run=False,
                now=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("DEBUGGER_PLAN_DRY_RUN_REQUIRED", payload["blockers"])
        self.assertFalse(payload["safety"]["x64dbgAttach"])
        self.assertTrue(payload["safety"]["noCheatEngine"])

    def test_target_identity_mismatch_blocks_plan_but_still_does_not_attach(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            payload = debugger_ce_plan.build_debugger_ce_plan(
                root,
                action_kind="watchpoint",
                target_tool="x64dbg",
                requested_action="Plan watchpoint only.",
                target_identity={"processId": 999999, "targetWindowHandle": "0xBAD"},
                max_duration_seconds=60,
                stop_condition="detach after one trap",
                crash_risk_acknowledged=True,
                static_first_reviewed=True,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("DEBUGGER_TARGET_MISMATCH:processId", payload["blockers"])
        self.assertIn("DEBUGGER_TARGET_MISMATCH:targetWindowHandle", payload["blockers"])
        self.assertFalse(payload["safety"]["debuggerAttached"])
        self.assertFalse(payload["safety"]["cheatEngineConnected"])

    def test_promotion_request_blocks_candidate_only_lane(self) -> None:
        classification = debugger_ce_plan.classify_debugger_ce_action(
            action_kind="promote-current-truth",
            target_tool="static",
            requested_action="promote candidate",
        )

        self.assertFalse(classification["ok"])
        self.assertEqual(classification["riskClass"], "blocked")
        self.assertIn("DEBUGGER_PROMOTION_FORBIDDEN", classification["blockers"])
        self.assertFalse(classification["safety"]["truthPromotionPerformed"])


if __name__ == "__main__":
    unittest.main()
