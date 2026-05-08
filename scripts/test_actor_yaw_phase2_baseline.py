from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rift_live_test.actor_yaw_phase2_baseline import build_phase2_baseline


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class ActorYawPhase2BaselineTests(unittest.TestCase):
    def build_repo(self, root: Path) -> None:
        capture_file = root / "scripts" / "captures" / "yaw-smoke" / "capture-actor-orientation.json"
        proof_summary = root / "scripts" / "captures" / "proof" / "run-summary.json"

        write_json(
            root / "docs" / "recovery" / "current-actor-yaw-disambiguation.json",
            {
                "processName": "rift_x64",
                "processId": 33912,
                "targetWindowHandle": "0xE0DB2",
                "singleSurvivor": {
                    "file": str(root / "validation.json"),
                    "candidateKey": "0x202CA5D23E0|0xD4",
                    "sourceAddress": "0x202CA5D23E0",
                    "basisForwardOffset": "0xD4",
                    "yawDeltaDegrees": -17.2,
                    "reverseYawDeltaDegrees": -32.4,
                    "truthLike": True,
                    "candidateResponsive": True,
                    "reversibleCandidateCount": 1,
                    "reversibleCycleCount": 1,
                    "playerCoordDeltaMagnitude": 0.0,
                },
                "promotedLead": {
                    "sourceAddress": "0x202CA5D23E0",
                    "basisForwardOffset": "0xD4",
                    "candidateKey": "0x202CA5D23E0|0xD4",
                },
            },
        )
        write_json(
            root / "scripts" / "actor-facing-behavior-backed-lead.json",
            {
                "SourceAddress": "0x202CA5D23E0",
                "BasisForwardOffset": "0xD4",
                "CanonicalYawFormula": "atan2(forwardZ, forwardX)",
                "CanonicalPitchFormula": "atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))",
                "CandidateDiagnostics": {
                    "CandidateKey": "0x202CA5D23E0|0xD4",
                    "ProcessId": 33912,
                    "TargetWindowHandle": "0xE0DB2",
                    "ValidationArtifact": str(root / "validation.json"),
                },
            },
        )
        write_json(
            root / "scripts" / "captures" / "latest-actor-yaw-readback-smoke.json",
            {
                "summaryFile": str(root / "scripts" / "captures" / "yaw-smoke" / "run-summary.json"),
                "target": {
                    "processName": "rift_x64",
                    "processId": 33912,
                    "targetWindowHandle": "0xE0DB2",
                },
                "readPlayerOrientation": {
                    "status": "passed",
                    "selectedSourceAddress": "0x202CA5D23E0",
                    "basisForwardOffset": "0xD4",
                    "preferredYawDegrees": 22.0,
                    "preferredPitchDegrees": -21.0,
                },
                "captureActorOrientation": {
                    "status": "passed",
                    "file": str(capture_file),
                    "selectedSourceAddress": "0x202CA5D23E0",
                    "basisForwardOffset": "0xD4",
                    "preferredYawDegrees": 10.5,
                    "preferredPitchDegrees": -20.2,
                },
                "safety": {
                    "movementSent": False,
                    "noCheatEngine": True,
                    "writesToRiftScan": False,
                    "savedVariablesUsedAsLiveTruth": False,
                },
            },
        )
        write_json(
            capture_file,
            {
                "ReaderOrientation": {
                    "PreferredBasis": {
                        "Name": "Basis@0xD4",
                        "Forward": {"X": 0.9, "Y": -0.3, "Z": 0.1},
                        "Up": {"X": 0.1, "Y": 0.8, "Z": 0.6},
                        "Right": {"X": -0.3, "Y": -0.5, "Z": 0.7},
                        "Determinant": 0.99,
                        "IsOrthonormal": True,
                    },
                    "PreferredEstimate": {
                        "YawDegrees": 10.5,
                        "PitchDegrees": -20.2,
                        "Magnitude": 0.99,
                    },
                }
            },
        )
        write_json(
            root / "scripts" / "captures" / "latest-live-test-run.json",
            {
                "runSummaryFile": str(proof_summary),
                "runDirectory": str(proof_summary.parent),
            },
        )
        write_json(
            proof_summary,
            {
                "status": "passed-proof-only",
                "summaryFile": str(root / "proof-readback.json"),
                "currentCoordinate": {
                    "x": 7446.0,
                    "y": 887.2,
                    "z": 3027.5,
                    "recordedAtUtc": "2026-05-08T19:43:47Z",
                },
                "movementSent": False,
                "movementAttempted": False,
                "noCheatEngine": True,
                "savedVariablesUsedAsLiveTruth": False,
            },
        )

    def test_builds_safe_phase2_pre_restart_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.build_repo(root)
            with (
                patch(
                    "rift_live_test.actor_yaw_phase2_baseline.powershell_process_info",
                    return_value={
                        "processName": "rift_x64",
                        "processId": 33912,
                        "targetWindowHandle": "0xE0DB2",
                        "mainWindowTitle": "RIFT",
                        "responding": True,
                        "processStartTimeUtc": "2026-05-08T02:38:08Z",
                    },
                ),
                patch(
                    "rift_live_test.actor_yaw_phase2_baseline.verify_target",
                    return_value={"status": "valid", "valid": True, "issues": []},
                ),
            ):
                packet = build_phase2_baseline(repo_root=root, process_id=33912, target_window_handle="0xE0DB2")

        self.assertEqual(packet["status"], "phase2-pre-restart-baseline-ready")
        self.assertEqual(packet["actorFacing"]["sourceAddress"], "0x202CA5D23E0")
        self.assertEqual(packet["actorFacing"]["basisSignature"]["status"], "captured")
        self.assertEqual(packet["coordinate"]["latestProofOnlyStatus"], "passed-proof-only")
        self.assertFalse(packet["movementGate"]["activeMovementAllowed"])
        self.assertFalse(packet["safety"]["movementAllowed"])
        self.assertFalse(packet["safety"]["writesToRiftScan"])
        self.assertTrue(packet["safety"]["noCheatEngine"])
        self.assertGreaterEqual(len(packet["phase2"]["fallbackOrder"]), 5)

    def test_fails_closed_when_exact_target_verification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.build_repo(root)
            with (
                patch(
                    "rift_live_test.actor_yaw_phase2_baseline.powershell_process_info",
                    return_value={
                        "processName": "rift_x64",
                        "processId": 33912,
                        "targetWindowHandle": "0xE0DB2",
                        "mainWindowTitle": "RIFT",
                        "responding": True,
                        "processStartTimeUtc": "2026-05-08T02:38:08Z",
                    },
                ),
                patch(
                    "rift_live_test.actor_yaw_phase2_baseline.verify_target",
                    return_value={"status": "pid-hwnd-mismatch", "valid": False, "issues": ["window_pid_mismatch"]},
                ),
            ):
                with self.assertRaisesRegex(ValueError, "Exact target verification failed"):
                    build_phase2_baseline(repo_root=root, process_id=33912, target_window_handle="0xE0DB2")


if __name__ == "__main__":
    unittest.main()
