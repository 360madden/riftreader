from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.riftscan_feedback import (
    build_feedback_packet,
    write_feedback_packet,
)


class RiftScanFeedbackTests(unittest.TestCase):
    @staticmethod
    def _write_match(
        path: Path,
        *,
        pid: int = 123,
        candidate_id: str = "rift-addon-coordinate-candidate-000001",
    ) -> None:
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
    def _write_consumer_summary(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "ok",
                    "display_status": "ok",
                    "mode": "candidate-ledger-consumer-summary",
                    "current_best_candidate": {
                        "stable_id": "consumer-current-best",
                        "kind": "coordinate",
                        "candidate_id": "rift-addon-coordinate-candidate-000001",
                        "source": "riftscan-offline",
                        "state": "candidate",
                        "claim_level": "offline-evidence",
                        "proof_level": "unproven-live",
                        "consumer_status": "safe-offline-only",
                        "live_use_authorized": False,
                        "source_base_address_hex": "0x10000000",
                        "source_offset_hex": "0x120",
                        "source_absolute_address_hex": "0x10000120",
                        "axis_order": "xyz",
                        "support_count": 3,
                        "next_validation_step": "riftreader-proof-pose",
                    },
                    "safe_candidate_count": 1,
                    "safe_candidates": [],
                    "allowed_downstream_uses": ["offline_review"],
                    "forbidden_downstream_uses": ["movement", "input"],
                    "safety": {
                        "offline_only": True,
                        "live_action_authorized": False,
                        "movement_or_input_sent": False,
                        "process_attach_or_memory_read_started": False,
                    },
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )

    def test_packet_wraps_coordination_without_riftscan_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            match = riftscan / "reports" / "generated" / "currentpid-123-demo-addon-coordinate-matches.json"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            current_truth = root / "docs" / "recovery" / "current-truth.md"
            latest_handoff = root / "docs" / "handoffs" / "2026-05-08-demo-handoff.md"
            latest_live_pointer = root / "scripts" / "captures" / "latest-live-test-run.json"
            live_summary = root / "scripts" / "captures" / "live-test-ProofOnly-demo" / "run-summary.json"
            live_progress = root / "scripts" / "captures" / "live-test-ProofOnly-demo" / "run-progress.json"
            consumer = (
                riftscan
                / "handoffs"
                / "current"
                / "candidate-ledger-consumer"
                / "candidate-ledger-consumer-summary.json"
            )
            self._write_match(match)
            self._write_pointer(pointer, match_file=match)
            self._write_consumer_summary(consumer)
            current_truth.parent.mkdir(parents=True, exist_ok=True)
            current_truth.write_text("# Current truth\n", encoding="utf-8")
            latest_handoff.parent.mkdir(parents=True, exist_ok=True)
            latest_handoff.write_text("# Handoff\n", encoding="utf-8")
            live_summary.parent.mkdir(parents=True, exist_ok=True)
            live_summary.write_text('{"status":"passed-proof-only"}\n', encoding="utf-8")
            live_progress.write_text('{"status":"passed-proof-only"}\n', encoding="utf-8")
            latest_live_pointer.write_text(
                json.dumps(
                    {
                        "runSummaryFile": str(live_summary),
                        "runProgressFile": str(live_progress),
                        "runDirectory": str(live_summary.parent),
                        "profileName": "ProofOnly",
                        "status": "passed-proof-only",
                        "runHealth": {
                            "ok": True,
                            "movementSent": False,
                            "noCheatEngine": True,
                        },
                        "generatedAtUtc": "2026-05-08T10:31:44Z",
                    }
                ),
                encoding="utf-8",
            )

            packet = build_feedback_packet(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )

            self.assertEqual(packet["status"], "ready-for-read-only-proof")
            self.assertEqual(packet["coordinationStatus"], "ok")
            self.assertFalse(packet["riftScanBoundary"]["writeAllowed"])
            self.assertFalse(packet["riftScanBoundary"]["feedbackWritesToRiftScan"])
            self.assertEqual(packet["selectedCandidate"]["source"], "current-proof-pointer")
            self.assertEqual(packet["selectedCandidate"]["candidateFile"], str(match))
            self.assertIn("riftscan_write", packet["forbiddenDownstreamUses"])
            self.assertTrue(packet["riftReaderArtifacts"]["currentTruth"]["exists"])
            self.assertEqual(packet["riftReaderArtifacts"]["latestHandoff"]["path"], str(latest_handoff))
            self.assertEqual(packet["riftReaderArtifacts"]["latestLiveTestPointer"]["status"], "passed-proof-only")
            self.assertTrue(packet["riftReaderArtifacts"]["latestLiveTestPointer"]["runSummaryFile"]["exists"])
            self.assertIn("readOnlyCandidateReadback", packet["nextCommands"])
            self.assertFalse(packet["nextCommands"]["writesToRiftScan"])

    def test_packet_exposes_target_mismatch_as_review_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            old_match = riftscan / "reports" / "generated" / "currentpid-123-old-addon-coordinate-matches.json"
            new_match = riftscan / "reports" / "generated" / "currentpid-456-new-addon-coordinate-matches.json"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            self._write_match(old_match, pid=123)
            self._write_match(new_match, pid=456)
            self._write_pointer(pointer, match_file=old_match, pid=123)

            packet = build_feedback_packet(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=456,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )

            self.assertEqual(packet["status"], "needs-review-before-proof")
            self.assertEqual(packet["coordinationStatus"], "needs-review")
            self.assertIn("pointer_pid_mismatch:actual=123;expected=456", packet["issues"])
            self.assertEqual(packet["selectedCandidate"]["source"], "latest-riftscan-match-file")
            self.assertEqual(packet["selectedCandidate"]["candidateFile"], str(new_match))
            self.assertIn("movement", packet["forbiddenDownstreamUses"])

    def test_write_feedback_refuses_to_write_inside_riftscan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            riftscan = Path(temp) / "Riftscan"
            packet = {"status": "ready-for-read-only-proof"}
            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                write_feedback_packet(
                    packet,
                    riftscan / "reports" / "generated" / "bad.json",
                    riftscan_root=riftscan,
                )


if __name__ == "__main__":
    unittest.main()
