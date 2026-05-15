#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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
        self.assertEqual(result["target"]["pid"], 1234)
        self.assertEqual(result["proof"]["anchor"]["addressHex"], "0x1000")
        self.assertTrue(result["recoveryProfile"]["profileScanUsed"])
        self.assertEqual(result["recoveryProfile"]["bestScanRange"]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
