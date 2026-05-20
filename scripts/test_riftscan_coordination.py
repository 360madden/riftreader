from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from rift_live_test.riftscan_coordination import (
    build_coordination_plan,
    summarize_match_file,
    summarize_readback_proof,
    write_plan,
)


class RiftScanCoordinationTests(unittest.TestCase):
    @staticmethod
    def _write_match(path: Path, *, pid: int = 123, candidate_id: str = "rift-addon-coordinate-candidate-000001") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "result_schema_version": "riftscan.rift_session_addon_coordinate_match_result.v1",
                    "success": True,
                    "session_path": f"C:/Riftscan/sessions/currentpid-{pid}-demo",
                    "truth_summary_path": f"C:/Riftscan/reports/generated/currentpid-{pid}-truth.json",
                    "candidate_count": 1,
                    "match_count": 3,
                    "candidates": [
                        {
                            "candidate_id": candidate_id,
                            "source_region_id": "region-000001",
                            "source_base_address_hex": "0x10000000",
                            "source_offset_hex": "0x120",
                            "source_absolute_address_hex": "0x10000120",
                            "axis_order": "xyz",
                            "support_count": 3,
                            "observation_support_count": 1,
                            "best_max_abs_distance": 0.003,
                        }
                    ],
                    "warnings": ["addon_coordinate_matches_are_validation_evidence_not_final_truth"],
                    "diagnostics": ["offline_snapshot_scan_only"],
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_pointer(path: Path, *, match_file: Path, pid: int = 123, hwnd: str = "0xABC") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "mode": "current-proof-anchor-readback-pointer",
                    "status": "movement-grade-current-session",
                    "target": {
                        "processName": "rift_x64",
                        "processId": pid,
                        "targetWindowHandle": hwnd,
                    },
                    "riftscanCandidateSource": {
                        "riftScanRoot": "C:/Riftscan",
                        "matchFile": str(match_file),
                        "candidateId": "rift-addon-coordinate-candidate-000001",
                        "sourceBaseAddressHex": "0x10000000",
                        "sourceOffsetHex": "0x120",
                        "sourceAbsoluteAddressHex": "0x10000120",
                        "supportCount": 3,
                    },
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_riftreader_candidate(path: Path, *, pid: int = 456, hwnd: str = "0xDEF") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "mode": "riftreader-same-target-candidates",
                    "processId": pid,
                    "targetWindowHandle": hwnd,
                    "candidate_count": 1,
                    "candidates": [
                        {
                            "schema_version": "riftreader.same_target_offset_candidate.v1",
                            "candidate_id": "same-target-demo",
                            "source_base_address_hex": "0x20000000",
                            "source_offset_hex": "0x0",
                            "source_absolute_address_hex": "0x20000000",
                            "axis_order": "xyz",
                            "support_count": 2,
                            "best_max_abs_distance": 0.01,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_family_import_candidate(
        path: Path,
        *,
        pid: int = 456,
        hwnd: str = "0xDEF",
        reference_stability: dict | None = None,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schemaVersion": 1,
            "mode": "riftreader-current-pid-coordinate-family-import-candidates",
            "processId": pid,
            "targetWindowHandle": hwnd,
            "candidateCount": 1,
            "candidates": [
                {
                    "schema_version": "riftreader.current_pid_family_snapshot_candidate.v1",
                    "candidate_id": "family-snapshot-hit-000001",
                    "base_address_hex": "0x30000000",
                    "offset_hex": "0x80",
                    "absolute_address_hex": "0x30000080",
                    "axis_order": "xyz",
                    "support_count": 2,
                    "best_max_abs_distance": 0.0001,
                },
                {
                    "schema_version": "riftreader.current_pid_family_snapshot_candidate.v1",
                    "candidate_id": "family-snapshot-hit-000002",
                    "base_address_hex": "0x30010000",
                    "offset_hex": "0x90",
                    "absolute_address_hex": "0x30010090",
                    "axis_order": "xyz",
                    "support_count": 2,
                    "best_max_abs_distance": 0.00005,
                },
            ],
        }
        if reference_stability is not None:
            payload["referenceStability"] = reference_stability
        path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    @staticmethod
    def _write_readback_proof(
        path: Path,
        *,
        candidate_file: Path,
        pid: int = 456,
        hwnd: str = "0xDEF",
        reference_match_count: int = 1,
        best_matches_reference: bool = True,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "ProcessId": pid,
                    "TargetWindowHandle": hwnd,
                    "ProcessName": "rift_x64",
                    "SourceCandidateFile": str(candidate_file),
                    "ReferenceMatchCount": reference_match_count,
                    "StableDecodedCandidateCount": 2,
                    "MovementAllowed": False,
                    "ProofAnchorStatus": "failed",
                    "BestReferenceMatches": [
                        {
                            "CandidateId": "family-snapshot-hit-000002",
                            "CandidateAddressHex": "0x30010090",
                            "ReferenceMatchesReadback": best_matches_reference,
                            "ReferenceMaxAbsDelta": 0.00005,
                            "ReferencePlanarDistance": 0.00006,
                            "ReferenceSpatialDistance": 0.00007,
                            "StableAcrossReadbackSamples": True,
                        },
                        {
                            "CandidateId": "family-snapshot-hit-000001",
                            "CandidateAddressHex": "0x30000080",
                            "ReferenceMatchesReadback": False,
                            "ReferenceMaxAbsDelta": 0.25,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_plan_uses_existing_pointer_match_without_riftscan_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            match = riftscan / "reports" / "generated" / "currentpid-123-demo-addon-coordinate-matches.json"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            self._write_match(match)
            self._write_pointer(pointer, match_file=match)

            plan = build_coordination_plan(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )

            self.assertEqual(plan["status"], "ok")
            self.assertFalse(plan["riftScanBoundary"]["writeAllowed"])
            self.assertEqual(plan["selectedCandidate"]["source"], "current-proof-pointer")
            self.assertEqual(plan["selectedCandidate"]["candidateFile"], str(match))
            self.assertIn("-CandidateFile", plan["nextCommands"]["readOnlyCandidateReadback"])
            self.assertFalse(plan["nextCommands"]["writesToRiftScan"])

    def test_summarize_match_file_supports_riftreader_candidate_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            match = Path(temp) / "api-family-vec3-candidates.jsonl"
            match.write_text(
                json.dumps(
                    {
                        "schema_version": "riftreader.api_family_vec3_candidate.v1",
                        "candidate_id": "api-family-hit-000010",
                        "base_address_hex": "0x1A91015CAC0",
                        "offset_hex": "0x40",
                        "absolute_address_hex": "0x1A91015CB00",
                        "axis_order": "xyz",
                        "support_count": 6,
                        "best_max_abs_distance": 0.004,
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "schema_version": "riftreader.api_family_vec3_candidate.v1",
                        "candidate_id": "api-family-hit-000011",
                        "base_address_hex": "0x1A914170980",
                        "offset_hex": "0x40",
                        "absolute_address_hex": "0x1A9141709C0",
                        "axis_order": "xyz",
                        "support_count": 1,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = summarize_match_file(match)

            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["mode"], "riftreader-api-family-vec3-candidates-jsonl")
            self.assertEqual(summary["candidateCount"], 2)
            self.assertEqual(summary["candidates"][0]["candidateId"], "api-family-hit-000010")
            self.assertTrue(summary["candidates"][0]["schemaSupported"])

    def test_plan_marks_pointer_mismatch_and_selects_existing_same_pid_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            old_match = riftscan / "reports" / "generated" / "currentpid-123-old-addon-coordinate-matches.json"
            new_match = riftscan / "reports" / "generated" / "currentpid-456-new-addon-coordinate-matches.json"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            self._write_match(old_match, pid=123)
            self._write_match(new_match, pid=456)
            self._write_pointer(pointer, match_file=old_match, pid=123)

            plan = build_coordination_plan(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=456,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )

            self.assertEqual(plan["status"], "needs-review")
            self.assertIn("pointer_pid_mismatch:actual=123;expected=456", plan["issues"])
            self.assertEqual(plan["selectedCandidate"]["source"], "latest-riftscan-match-file")
            self.assertEqual(plan["selectedCandidate"]["candidateFile"], str(new_match))

    def test_plan_selects_riftreader_same_target_candidate_when_provider_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True, exist_ok=True)
            pointer.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "mode": "current-proof-anchor-readback-pointer",
                        "status": "blocked-target-drift",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 456,
                            "targetWindowHandle": "0xDEF",
                        },
                    }
                ),
                encoding="utf-8",
            )
            candidate = root / "scripts" / "captures" / "same-target-candidate-synth-demo" / "same-target-candidates.json"
            self._write_riftreader_candidate(candidate)

            plan = build_coordination_plan(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=456,
                target_window_handle="0xDEF",
                process_name="rift_x64",
            )

            self.assertEqual(plan["status"], "ok")
            self.assertEqual(plan["selectedCandidate"]["source"], "latest-riftreader-same-target-candidate-file")
            self.assertEqual(plan["selectedCandidate"]["candidateFile"], str(candidate))
            self.assertIn("latestRiftReaderCandidateFiles", plan)
            self.assertIn("-CandidateFile", plan["nextCommands"]["readOnlyProofPose"])

    def test_plan_prefers_latest_family_import_candidate_when_newest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True, exist_ok=True)
            pointer.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "mode": "current-proof-anchor-readback-pointer",
                        "status": "blocked-target-drift",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 456,
                            "targetWindowHandle": "0xDEF",
                        },
                    }
                ),
                encoding="utf-8",
            )
            same_target = root / "scripts" / "captures" / "same-target-candidate-synth-demo" / "same-target-candidates.json"
            family_import = root / "scripts" / "captures" / "coordinate-family-snapshot-currentpid-456-demo" / "family-import-candidates.json"
            proof = (
                root
                / "scripts"
                / "captures"
                / "riftscan-proof-pose-demo"
                / "riftscan-riftreader-currentpid-456-readback-wrapper-summary-demo.json"
            )
            self._write_riftreader_candidate(same_target)
            self._write_family_import_candidate(family_import)
            self._write_readback_proof(proof, candidate_file=family_import)
            now = time.time()
            os.utime(same_target, (now - 10, now - 10))
            os.utime(family_import, (now, now))
            os.utime(proof, (now, now))

            plan = build_coordination_plan(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=456,
                target_window_handle="0xDEF",
                process_name="rift_x64",
            )

            self.assertEqual(plan["status"], "ok")
            self.assertEqual(plan["selectedCandidate"]["source"], "latest-riftreader-family-import-candidate-file")
            self.assertEqual(plan["selectedCandidate"]["candidateFile"], str(family_import))
            self.assertEqual(plan["selectedCandidate"]["candidateId"], "family-snapshot-hit-000002")
            self.assertEqual(plan["selectedCandidate"]["proofEvidence"]["path"], str(proof))
            self.assertIn("-CandidateFile", plan["nextCommands"]["readOnlyProofPose"])

    def test_readback_summary_prefers_stable_reference_match_over_unstable_rank_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate_file = root / "family-import-candidates.json"
            proof = root / "riftscan-riftreader-currentpid-456-readback-wrapper-summary-demo.json"
            proof.write_text(
                json.dumps(
                    {
                        "ProcessId": 456,
                        "TargetWindowHandle": "0xDEF",
                        "ProcessName": "rift_x64",
                        "SourceCandidateFile": str(candidate_file),
                        "ReferenceMatchCount": 2,
                        "StableDecodedCandidateCount": 1,
                        "MovementAllowed": False,
                        "BestReferenceMatches": [
                            {
                                "CandidateId": "unstable-rank-one",
                                "CandidateAddressHex": "0x1",
                                "ReferenceMatchesReadback": True,
                                "ReferenceMaxAbsDelta": 0.000001,
                                "StableAcrossReadbackSamples": False,
                                "SourcePreviewMatchesReadback": True,
                            },
                            {
                                "CandidateId": "stable-rank-two",
                                "CandidateAddressHex": "0x2",
                                "ReferenceMatchesReadback": True,
                                "ReferenceMaxAbsDelta": 0.000002,
                                "StableAcrossReadbackSamples": True,
                                "SourcePreviewMatchesReadback": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            summary = summarize_readback_proof(proof)

            self.assertEqual(summary["status"], "reference-match")
            self.assertEqual(summary["bestReferenceMatch"]["candidateId"], "stable-rank-two")
            self.assertEqual(summary["stableReferenceMatchCount"], 1)

    def test_plan_rejects_family_import_candidate_with_drifted_reference_stability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True, exist_ok=True)
            pointer.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "mode": "current-proof-anchor-readback-pointer",
                        "status": "blocked-target-drift",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 456,
                            "targetWindowHandle": "0xDEF",
                        },
                    }
                ),
                encoding="utf-8",
            )
            family_import = root / "scripts" / "captures" / "coordinate-family-snapshot-currentpid-456-demo" / "family-import-candidates.json"
            self._write_family_import_candidate(
                family_import,
                reference_stability={
                    "enabled": True,
                    "status": "drifted",
                    "withinTolerance": False,
                    "maxAbsDelta": 1.4,
                    "tolerance": 0.25,
                },
            )

            plan = build_coordination_plan(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=456,
                target_window_handle="0xDEF",
                process_name="rift_x64",
            )

            self.assertEqual(plan["status"], "blocked")
            self.assertEqual(plan["selectedCandidate"]["source"], "none")
            self.assertIsNone(plan["selectedCandidate"]["candidateFile"])
            self.assertIn("riftreader_candidates_rejected_by_freshness_gates", plan["issues"])
            self.assertEqual(
                plan["selectedCandidate"]["rejectedCandidateFiles"][0]["status"],
                "blocked-stale-reference",
            )
            self.assertNotIn("readOnlyProofPose", plan["nextCommands"])

    def test_plan_rejects_family_import_candidate_when_latest_readback_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True, exist_ok=True)
            pointer.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "mode": "current-proof-anchor-readback-pointer",
                        "status": "blocked-target-drift",
                        "target": {
                            "processName": "rift_x64",
                            "processId": 456,
                            "targetWindowHandle": "0xDEF",
                        },
                    }
                ),
                encoding="utf-8",
            )
            family_import = root / "scripts" / "captures" / "coordinate-family-snapshot-currentpid-456-demo" / "family-import-candidates.json"
            proof = (
                root
                / "scripts"
                / "captures"
                / "riftscan-proof-pose-demo"
                / "riftscan-riftreader-currentpid-456-readback-wrapper-summary-demo.json"
            )
            self._write_family_import_candidate(family_import)
            self._write_readback_proof(
                proof,
                candidate_file=family_import,
                reference_match_count=0,
                best_matches_reference=False,
            )

            plan = build_coordination_plan(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=456,
                target_window_handle="0xDEF",
                process_name="rift_x64",
            )

            self.assertEqual(plan["status"], "blocked")
            self.assertEqual(plan["selectedCandidate"]["source"], "none")
            self.assertIn("riftreader_candidates_rejected_by_freshness_gates", plan["issues"])
            self.assertEqual(
                plan["selectedCandidate"]["rejectedCandidateFiles"][0]["status"],
                "latest-readback-no-reference-match",
            )

    def test_write_plan_refuses_to_write_inside_riftscan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            riftscan = Path(temp) / "Riftscan"
            plan = {"status": "ok"}
            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                write_plan(plan, riftscan / "reports" / "generated" / "bad.json", riftscan_root=riftscan)


if __name__ == "__main__":
    unittest.main()
