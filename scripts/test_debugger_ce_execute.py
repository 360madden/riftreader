#!/usr/bin/env python3
"""Tests for Stage 46 fail-closed debugger/CE execution-boundary helper."""
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

from riftreader_workflow import debugger_ce_execute, debugger_ce_plan  # noqa: E402


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


class DebuggerCeExecuteTests(unittest.TestCase):
    def _debugger_plan(self, root: Path) -> dict[str, object]:
        return debugger_ce_plan.build_debugger_ce_plan(
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

    def test_static_review_boundary_writes_artifact_without_attach_or_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            plan = debugger_ce_plan.build_debugger_ce_plan(
                root,
                action_kind="static-review",
                question="Review prior static offset notes for a yaw candidate.",
                static_evidence={"doc": "tracked-notes"},
                now=NOW,
            )
            payload = debugger_ce_execute.build_debugger_ce_execution_boundary(
                root,
                plan_id=plan["planId"],
                dry_run=True,
                now=NOW,
            )

            run_path = root / payload["artifact"]["runPath"]
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["status"], "ready-for-approval")
            self.assertEqual(payload["stage"], 46)
            self.assertEqual(payload["planId"], plan["planId"])
            self.assertEqual(payload["riskClass"], "static-review")
            self.assertTrue(str(payload["artifact"]["runPath"]).startswith(".riftreader-local"))
            self.assertTrue(run_path.is_file())
            self.assertFalse(payload["safety"]["debuggerLaunchAttempted"])
            self.assertFalse(payload["safety"]["cheatEngineLaunchAttempted"])
            self.assertFalse(payload["safety"]["debuggerAttached"])
            self.assertFalse(payload["safety"]["breakpointsSet"])
            self.assertFalse(payload["safety"]["watchpointsSet"])
            self.assertFalse(payload["safety"]["targetMemoryBytesRead"])
            self.assertFalse(payload["safety"]["targetMemoryBytesWritten"])
            self.assertFalse(payload["safety"]["inputSent"])
            self.assertFalse(payload["safety"]["movementSent"])
            self.assertTrue(payload["safety"]["noCheatEngine"])
            self.assertFalse(payload["safety"]["x64dbgAttach"])

    def test_attach_boundary_missing_approval_blocks_before_attach(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            plan = self._debugger_plan(root)
            payload = debugger_ce_execute.build_debugger_ce_execution_boundary(
                root,
                plan_id=plan["planId"],
                target_identity={"processId": 130540, "targetWindowHandle": "0x9310EA"},
                dry_run=False,
                allow_debugger_risk=True,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["status"], "blocked-before-attach")
            self.assertIn("DEBUGGER_APPROVAL_MISSING", payload["blockers"])
            self.assertIn("DEBUGGER_BACKEND_UNAVAILABLE", payload["blockers"])
            self.assertIn("DEBUGGER_STAGE46_ATTACH_BACKEND_DISABLED", payload["blockers"])
            self.assertFalse(payload["executionReadiness"]["canExecuteFromThisToolNow"])
            self.assertTrue(payload["executionReadiness"]["blockedBeforeAttach"])
            self.assertFalse(payload["safety"]["debuggerAttached"])
            self.assertFalse(payload["safety"]["targetMemoryScanned"])

    def test_matching_approval_still_blocks_when_backend_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            plan = self._debugger_plan(root)
            dry_run = debugger_ce_execute.build_debugger_ce_execution_boundary(
                root,
                plan_id=plan["planId"],
                target_identity={"processId": 130540, "targetWindowHandle": "0x9310EA"},
                dry_run=True,
                allow_debugger_risk=True,
                discovery_payload=discovery_payload(),
                now=NOW,
            )
            payload = debugger_ce_execute.build_debugger_ce_execution_boundary(
                root,
                plan_id=plan["planId"],
                approval_phrase=dry_run["approval"]["expectedApprovalPhrase"],
                target_identity={"processId": 130540, "targetWindowHandle": "0x9310EA"},
                dry_run=False,
                allow_debugger_risk=True,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["approval"]["status"], "matched")
            self.assertTrue(payload["approval"]["suppliedApprovalMatched"])
            self.assertIn("DEBUGGER_BACKEND_UNAVAILABLE", payload["blockers"])
            self.assertIn("DEBUGGER_STAGE46_ATTACH_BACKEND_DISABLED", payload["blockers"])
            self.assertFalse(payload["safety"]["debuggerBackendCalled"])
            self.assertFalse(payload["safety"]["debuggerAttached"])
            self.assertFalse(payload["safety"]["cheatEngineConnected"])

    def test_attach_boundary_blocks_without_debugger_risk_allowance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_fixture_repo(root)
            plan = self._debugger_plan(root)
            payload = debugger_ce_execute.build_debugger_ce_execution_boundary(
                root,
                plan_id=plan["planId"],
                target_identity={"processId": 130540, "targetWindowHandle": "0x9310EA"},
                dry_run=True,
                allow_debugger_risk=False,
                discovery_payload=discovery_payload(),
                now=NOW,
            )

            self.assertFalse(payload["ok"])
            self.assertIn("DEBUGGER_RISK_NOT_ALLOWED_FOR_EXECUTION_BOUNDARY", payload["blockers"])
            self.assertFalse(payload["safety"]["debuggerAttached"])
            self.assertFalse(payload["safety"]["x64dbgAttach"])


if __name__ == "__main__":
    unittest.main()
