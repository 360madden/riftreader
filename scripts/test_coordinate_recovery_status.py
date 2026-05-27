#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import coordinate_recovery_status as status_tool


class CoordinateRecoveryStatusTests(unittest.TestCase):
    def test_build_status_reads_proof_and_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "current-proof-anchor-readback.json"
            profile = root / "coordinate-recovery-profile.json"
            proof.write_text(
                json.dumps(
                    {
                        "status": "current-target-proofonly-passed",
                        "lastUpdatedUtc": "2026-05-15T00:00:00Z",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 1234,
                            "targetWindowHandle": "0xABCDEF",
                        },
                        "riftscanCandidateSource": {
                            "candidateId": "candidate-1",
                            "sourceAbsoluteAddressHex": "0x1000",
                            "proofSupportCount": 3,
                            "matchFile": "candidates.jsonl",
                        },
                        "latestValidation": {"status": "valid", "movementAllowed": True},
                        "latestProofOnly": {
                            "status": "passed-proof-only",
                            "generatedAtUtc": "2026-05-15T00:00:01Z",
                            "currentCoordinate": {"x": 1.0, "y": 2.0, "z": 3.0, "recordedAtUtc": "now"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile.write_text(
                json.dumps(
                    {
                        "kind": "riftreader-coordinate-recovery-profile",
                        "generatedAtUtc": "2026-05-15T00:00:02Z",
                        "referenceProvider": "chromalink-world-state",
                        "profileScanUsed": True,
                        "candidateJsonl": "candidates.jsonl",
                        "bestScanRange": {
                            "rank": 1,
                            "minAddressHex": "0x1000",
                            "maxAddressHex": "0x2000",
                            "hitCount": 1,
                            "durationSeconds": 1.5,
                        },
                        "stageTimings": [
                            {"label": "profile-priority-family-scan", "phase": "profile-scan", "status": "passed", "durationSeconds": 1.5}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = status_tool.build_status(root, proof, profile)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["liveTarget"]["verdict"], "not-checked")
        self.assertEqual(result["target"]["pid"], 1234)
        self.assertEqual(result["proof"]["anchor"]["addressHex"], "0x1000")
        self.assertTrue(result["proof"]["movementAllowed"])
        self.assertTrue(result["proof"]["movementAllowedEffective"])
        self.assertTrue(result["recoveryProfile"]["profileScanUsed"])
        self.assertEqual(result["recoveryProfile"]["bestScanRange"]["rank"], 1)

    def test_input_backend_incident_blocks_effective_movement_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "current-proof-anchor-readback.json"
            profile = root / "coordinate-recovery-profile.json"
            proof.write_text(
                json.dumps(
                    {
                        "status": "current-target-proofonly-passed",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 1234,
                            "targetWindowHandle": "0xABCDEF",
                        },
                        "latestValidation": {"status": "valid", "movementAllowed": True},
                        "inputBackendIncident": {
                            "status": "agent-live-movement-paused-after-spin-incident",
                            "automationMovementPaused": True,
                            "emergencyKeyRelease": {"summaryJson": "scripts/captures/emergency/summary.json"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile.write_text(json.dumps({}), encoding="utf-8")

            result = status_tool.build_status(root, proof, profile)

        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["proof"]["movementAllowed"])
        self.assertFalse(result["proof"]["movementAllowedEffective"])
        self.assertEqual(
            result["proof"]["inputBackendIncident"]["status"],
            "agent-live-movement-paused-after-spin-incident",
        )

    def test_live_target_check_blocks_when_artifact_pid_is_not_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "current-proof-anchor-readback.json"
            profile = root / "coordinate-recovery-profile.json"
            proof.write_text(
                json.dumps(
                    {
                        "status": "current-target-proofonly-passed",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 1234,
                            "targetWindowHandle": "0xABCDEF",
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile.write_text(json.dumps({}), encoding="utf-8")

            result = status_tool.build_status(
                root,
                proof,
                profile,
                live_target_check=True,
                live_process_snapshot={
                    "checkedAtUtc": "2026-05-16T00:00:00Z",
                    "status": "passed",
                    "processes": [{"imageName": "rift_x64.exe", "pid": 5678}],
                },
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["liveTarget"]["verdict"], "artifact-pid-stale")
        self.assertIn("artifact-target-pid-not-running:artifact=1234;live=5678", result["blockers"])

    def test_live_target_check_blocks_when_no_live_process_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "current-proof-anchor-readback.json"
            profile = root / "coordinate-recovery-profile.json"
            proof.write_text(
                json.dumps(
                    {
                        "status": "current-target-proofonly-passed",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 1234,
                            "targetWindowHandle": "0xABCDEF",
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile.write_text(json.dumps({}), encoding="utf-8")

            result = status_tool.build_status(
                root,
                proof,
                profile,
                live_target_check=True,
                live_process_snapshot={
                    "checkedAtUtc": "2026-05-16T00:00:00Z",
                    "status": "passed",
                    "processes": [],
                },
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["liveTarget"]["verdict"], "no-live-process")
        self.assertIn("live-target-not-running:rift_x64", result["blockers"])

    def test_blocked_current_proof_status_blocks_even_when_target_process_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "current-proof-anchor-readback.json"
            profile = root / "coordinate-recovery-profile.json"
            proof.write_text(
                json.dumps(
                    {
                        "status": "blocked-target-not-in-world",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 1234,
                            "targetWindowHandle": "0xABCDEF",
                        },
                        "latestValidation": {"status": "blocked-target-not-in-world", "movementAllowed": False},
                    }
                ),
                encoding="utf-8",
            )
            profile.write_text(json.dumps({}), encoding="utf-8")

            result = status_tool.build_status(
                root,
                proof,
                profile,
                live_target_check=True,
                live_process_snapshot={
                    "checkedAtUtc": "2026-05-20T11:00:00Z",
                    "status": "passed",
                    "processes": [{"imageName": "rift_x64.exe", "pid": 1234}],
                },
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["liveTarget"]["verdict"], "artifact-pid-running")
        self.assertIn("current-proof-status:blocked-target-not-in-world", result["blockers"])
        self.assertFalse(result["proof"]["movementAllowedEffective"])

    def test_probe_live_processes_disconnects_tasklist_stdin(self) -> None:
        completed = subprocess.CompletedProcess(
            ["tasklist"],
            0,
            stdout='"rift_x64.exe","1234","Console","1","10,000 K"\n',
            stderr="",
        )
        with mock.patch.object(status_tool.subprocess, "run", return_value=completed) as run:
            result = status_tool.probe_live_processes("rift_x64")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["processes"][0]["pid"], 1234)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_promoted_static_resolver_uses_current_truth_target_for_live_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "current-proof-anchor-readback.json"
            profile = root / "coordinate-recovery-profile.json"
            current_truth = root / "current-truth.json"
            proof.write_text(
                json.dumps(
                    {
                        "status": "current-target-proofonly-passed",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 100,
                            "targetWindowHandle": "0xCAFE",
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile.write_text(
                json.dumps({"target": {"processName": "rift_x64", "pid": 100, "hwnd": "0xCAFE"}}),
                encoding="utf-8",
            )
            current_truth.write_text(
                json.dumps(
                    {
                        "target": {
                            "processName": "rift_x64",
                            "processId": 200,
                            "targetWindowHandle": "0xBEEF",
                        },
                        "staticChainStatus": {
                            "status": "promoted",
                            "promotionAllowed": True,
                            "primaryCandidate": {
                                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                                "rootRva": "0x32EBC80",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = status_tool.build_status(
                root,
                proof,
                profile,
                current_truth,
                live_target_check=True,
                live_process_snapshot={
                    "checkedAtUtc": "2026-05-27T19:40:00Z",
                    "status": "passed",
                    "processes": [{"imageName": "rift_x64.exe", "pid": 200}],
                },
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["target"]["pid"], 200)
        self.assertEqual(result["liveTarget"]["artifactPid"], 200)
        self.assertEqual(result["liveTarget"]["verdict"], "artifact-pid-running")
        self.assertTrue(result["staticResolver"]["promoted"])
        self.assertIn("proof-anchor-status-superseded-by-promoted-static-resolver", result["warnings"])

    def test_unpromoted_static_resolver_keeps_stale_proof_target_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "current-proof-anchor-readback.json"
            profile = root / "coordinate-recovery-profile.json"
            current_truth = root / "current-truth.json"
            proof.write_text(
                json.dumps(
                    {
                        "status": "current-target-proofonly-passed",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 100,
                            "targetWindowHandle": "0xCAFE",
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile.write_text(
                json.dumps({"target": {"processName": "rift_x64", "pid": 100, "hwnd": "0xCAFE"}}),
                encoding="utf-8",
            )
            current_truth.write_text(
                json.dumps(
                    {
                        "target": {
                            "processName": "rift_x64",
                            "processId": 200,
                            "targetWindowHandle": "0xBEEF",
                        },
                        "staticChainStatus": {
                            "status": "promotion-review-ready-not-promoted",
                            "promotionAllowed": False,
                            "primaryCandidate": {
                                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                                "rootRva": "0x32EBC80",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = status_tool.build_status(
                root,
                proof,
                profile,
                current_truth,
                live_target_check=True,
                live_process_snapshot={
                    "checkedAtUtc": "2026-05-27T19:40:00Z",
                    "status": "passed",
                    "processes": [{"imageName": "rift_x64.exe", "pid": 200}],
                },
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["target"]["pid"], 100)
        self.assertFalse(result["staticResolver"]["promoted"])
        self.assertIn("artifact-target-pid-not-running:artifact=100;live=200", result["blockers"])


if __name__ == "__main__":
    unittest.main()
