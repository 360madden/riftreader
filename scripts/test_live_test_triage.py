#!/usr/bin/env python3

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import live_test_triage  # noqa: E402


class LiveTestTriageTests(unittest.TestCase):
    def test_classifies_no_live_target_first(self) -> None:
        packet = {
            "blockers": ["coordinate-status:live-target-not-running:rift_x64"],
            "errors": [],
            "currentProof": {"summary": {"status": "blocked-target-drift"}},
            "currentTruth": {"summary": {"movementGate": {"allowed": False, "status": "blocked"}}},
            "coordinateRecoveryStatus": {"liveTarget": {"verdict": "no-live-process", "livePids": []}},
        }

        result = live_test_triage.classify_packet(packet)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["failedStage"], "live-target")
        self.assertEqual(result["blockerCategory"], "no-live-process")

    def test_artifact_pid_stale_guidance_uses_current_live_pid(self) -> None:
        packet = {
            "blockers": ["coordinate-status:artifact-target-pid-not-running:artifact=27552;live=22304"],
            "errors": [],
            "currentProof": {"summary": {"status": "blocked-target-drift"}},
            "currentTruth": {"summary": {"movementGate": {"allowed": False, "status": "blocked"}}},
            "coordinateRecoveryStatus": {
                "liveTarget": {
                    "verdict": "artifact-pid-stale",
                    "livePids": [22304],
                    "artifactPid": 27552,
                    "artifactHwnd": "0x3411E2",
                }
            },
        }

        result = live_test_triage.classify_packet(packet)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["failedStage"], "live-target")
        self.assertEqual(result["blockerCategory"], "artifact-pid-stale")
        self.assertIn("rift_x64 process is visible with PID(s) [22304]", result["nextRecommendedAction"])
        self.assertIn("historical PID 27552 / HWND 0x3411E2", result["nextRecommendedAction"])
        self.assertIn("do not reuse stale proof", result["nextRecommendedAction"])
        self.assertNotIn("Load RIFT into the character/world", result["nextRecommendedAction"])

    def test_classifies_target_drift_when_live_target_not_blocking(self) -> None:
        packet = {
            "blockers": ["current-proof-status:blocked-target-drift"],
            "errors": [],
            "currentProof": {"summary": {"status": "blocked-target-drift"}},
            "currentTruth": {"summary": {"movementGate": {"allowed": False, "status": "blocked"}}},
            "coordinateRecoveryStatus": {"liveTarget": {"verdict": "artifact-pid-running", "livePids": [1234]}},
        }

        result = live_test_triage.classify_packet(packet)

        self.assertEqual(result["failedStage"], "proof-target-drift")
        self.assertEqual(result["blockerCategory"], "blocked-target-drift")

    def test_classifies_movement_gate_when_proof_not_blocked(self) -> None:
        packet = {
            "blockers": ["movement-not-allowed:blocked"],
            "errors": [],
            "currentProof": {"summary": {"status": "current-target-proofonly-passed"}},
            "currentTruth": {
                "summary": {
                    "movementGate": {
                        "allowed": False,
                        "status": "blocked-no-live-target-reacquisition-required",
                        "reason": "blocked",
                    }
                }
            },
            "coordinateRecoveryStatus": {"liveTarget": {"verdict": "artifact-pid-running", "livePids": [1234]}},
        }

        result = live_test_triage.classify_packet(packet)

        self.assertEqual(result["failedStage"], "movement-gate")
        self.assertEqual(result["blockerCategory"], "blocked-no-live-target-reacquisition-required")

    def test_classifies_blocked_recovery_stage(self) -> None:
        packet = {
            "blockers": [],
            "errors": [],
            "currentProof": {"summary": {"status": "current-target-proofonly-passed"}},
            "currentTruth": {"summary": {"movementGate": {"allowed": True, "status": "passed"}}},
            "coordinateRecoveryStatus": {
                "liveTarget": {"verdict": "artifact-pid-running", "livePids": [1234]},
                "recoveryProfile": {
                    "stageTimings": [
                        {"label": "reference-chromalink-fast-path", "phase": "reference", "status": "blocked"}
                    ]
                },
            },
        }

        result = live_test_triage.classify_packet(packet)

        self.assertEqual(result["failedStage"], "reference")
        self.assertEqual(result["blockerCategory"], "blocked")

    def test_write_outputs_uses_ignored_live_triage_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            triage = {
                "status": "blocked",
                "failedStage": "live-target",
                "blockerCategory": "no-live-process",
                "reason": "no live process",
                "blockers": ["live-target-not-running:rift_x64"],
                "warnings": [],
                "errors": [],
                "evidence": {},
                "nextRecommendedAction": "load game",
                "statusPacket": None,
                "artifacts": {},
                "safety": {"movementSent": False, "gitMutation": False},
            }

            artifacts = live_test_triage.write_outputs(root, triage)

            self.assertTrue(artifacts["summaryJson"].startswith(".riftreader-local\\live-test-triage\\"))
            self.assertTrue((root / artifacts["summaryJson"]).is_file())
            self.assertTrue((root / artifacts["summaryMarkdown"]).is_file())


if __name__ == "__main__":
    unittest.main()
