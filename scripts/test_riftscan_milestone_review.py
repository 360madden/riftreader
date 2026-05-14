from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.riftscan_milestone_review import (
    build_milestone_review,
    markdown_for_review,
    write_markdown_review,
    write_review,
)


class RiftScanMilestoneReviewTests(unittest.TestCase):
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
                    "status": "pass",
                    "display_status": "PASS",
                    "mode": "offline_candidate_ledger_consumer",
                    "current_best_candidate": {
                        "stable_id": "consumer-current-best",
                        "kind": "coordinate_vec3",
                        "candidate_id": "rift-addon-coordinate-candidate-000001",
                        "source": "riftscan_addon_coordinate_match",
                        "state": "validated_candidate_historical_checkpoint",
                        "claim_level": "validated_candidate",
                        "proof_level": "riftscan_candidate",
                        "consumer_status": "available_offline_only",
                        "live_use_authorized": False,
                        "source_absolute_address_hex": "0x10000120",
                        "axis_order": "xyz",
                        "support_count": 3,
                        "forbidden_downstream_uses": ["movement", "input"],
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

    @staticmethod
    def _write_proof_route(path: Path, *, status: str = "visual-only") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "kind": "coordinate-proof-route",
                    "status": status,
                    "decision": {
                        "readOnlyProofAllowed": False,
                        "movementAllowed": False,
                        "visualEvidenceCanPromoteTruth": False,
                    },
                    "visualEvidence": {
                        "status": "usable-sidecar",
                        "proofRole": "sidecar_only_not_coordinate_or_movement_truth",
                        "coordinateProof": False,
                        "movementProof": False,
                        "items": [],
                    },
                    "blockers": ["visual-evidence-is-not-coordinate-proof"],
                    "safety": {
                        "movementSent": False,
                        "inputSent": False,
                        "noCheatEngine": True,
                    },
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_proof_route_pointer(path: Path, *, summary_json: Path, status: str = "visual-only") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "kind": "latest-coordinate-proof-route-pointer",
                    "status": status,
                    "summaryJson": str(summary_json),
                    "readOnlyProofAllowed": False,
                    "movementAllowed": False,
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_latest_live_pointer(
        root: Path,
        *,
        pid: int = 123,
        hwnd: str = "0xABC",
        status: str = "passed-proof-only",
        profile_name: str = "ProofOnly",
        movement_sent: bool = False,
    ) -> None:
        latest_live_pointer = root / "scripts" / "captures" / "latest-live-test-run.json"
        live_summary = root / "scripts" / "captures" / f"live-test-{profile_name}-demo" / "run-summary.json"
        live_progress = root / "scripts" / "captures" / f"live-test-{profile_name}-demo" / "run-progress.json"
        live_summary.parent.mkdir(parents=True, exist_ok=True)
        live_summary.write_text(
            json.dumps(
                {
                    "status": status,
                    "processName": "rift_x64",
                    "processId": pid,
                    "targetWindowHandle": hwnd,
                    "movementSent": movement_sent,
                    "noCheatEngine": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        live_progress.write_text(
            json.dumps(
                {
                    "status": status,
                    "processName": "rift_x64",
                    "processId": pid,
                    "targetWindowHandle": hwnd,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        latest_live_pointer.write_text(
            json.dumps(
                {
                    "runSummaryFile": str(live_summary),
                    "runProgressFile": str(live_progress),
                    "runDirectory": str(live_summary.parent),
                    "profileName": profile_name,
                    "status": status,
                    "runHealth": {
                        "ok": True,
                        "movementSent": movement_sent,
                        "noCheatEngine": True,
                    },
                    "generatedAtUtc": "2026-05-08T10:31:44Z",
                }
            ),
            encoding="utf-8",
        )

    def test_review_ready_for_read_only_proof_without_movement_permission(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            match = riftscan / "reports" / "generated" / "currentpid-123-demo-addon-coordinate-matches.json"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
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
            self._write_latest_live_pointer(root)

            review = build_milestone_review(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )

            self.assertEqual(review["status"], "ready-for-read-only-proof")
            self.assertEqual(review["strategy"]["decision"], "proceed-read-only-proof-first")
            self.assertFalse(review["strategy"]["movementAllowedByReview"])
            self.assertTrue(review["strategy"]["readOnlyProofAllowedByReview"])
            self.assertEqual(review["selectedCandidate"]["source"], "current-proof-pointer")
            self.assertFalse(review["riftScanBoundary"]["writeAllowed"])
            failed_blockers = [
                check
                for check in review["checks"]
                if check["severity"] == "blocker" and check["status"] == "fail"
            ]
            self.assertEqual(failed_blockers, [])

    def test_review_blocks_on_pointer_target_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            old_match = riftscan / "reports" / "generated" / "currentpid-123-old-addon-coordinate-matches.json"
            new_match = riftscan / "reports" / "generated" / "currentpid-456-new-addon-coordinate-matches.json"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            self._write_match(old_match, pid=123)
            self._write_match(new_match, pid=456)
            self._write_pointer(pointer, match_file=old_match, pid=123)
            self._write_latest_live_pointer(root)

            review = build_milestone_review(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_id=456,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )

            self.assertEqual(review["status"], "blocked")
            self.assertEqual(review["strategy"]["decision"], "block")
            self.assertIn("pointer_pid_mismatch:actual=123;expected=456", review["issues"])
            self.assertFalse(review["strategy"]["readOnlyProofAllowedByReview"])

    def test_review_infers_latest_live_target_instead_of_stale_docs_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            old_match = riftscan / "reports" / "generated" / "currentpid-123-old-addon-coordinate-matches.json"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            self._write_match(old_match, pid=123)
            self._write_pointer(pointer, match_file=old_match, pid=123, hwnd="0xABC")
            self._write_latest_live_pointer(
                root,
                pid=456,
                hwnd="0xDEF",
                status="passed",
                profile_name="ForwardSeries3x250",
                movement_sent=True,
            )

            review = build_milestone_review(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                process_name="rift_x64",
            )

            self.assertEqual(review["requestedTarget"]["processId"], 456)
            self.assertEqual(review["requestedTarget"]["targetWindowHandle"], "0xDEF")
            self.assertEqual(review["targetInference"]["source"], "runSummaryFile")
            self.assertEqual(review["status"], "blocked")
            self.assertIn("pointer_pid_mismatch:actual=123;expected=456", review["issues"])
            self.assertIn("pointer_hwnd_mismatch:actual=0xABC;expected=0xDEF", review["issues"])
            self.assertNotEqual(review["selectedCandidate"]["source"], "current-proof-pointer")
            self.assertEqual(
                review["nextCommands"]["freshProofOnly"],
                [
                    "python",
                    str(root / "scripts" / "live_test.py"),
                    "--profile",
                    "ProofOnly",
                    "--pid",
                    "456",
                    "--hwnd",
                    "0xDEF",
                    "--process-name",
                    "rift_x64",
                ],
            )

    def test_review_writers_refuse_riftscan_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            riftscan = Path(temp) / "Riftscan"
            review = {"status": "ready-for-read-only-proof"}
            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                write_review(review, riftscan / "reports" / "generated" / "bad.json", riftscan_root=riftscan)
            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                write_markdown_review(review, riftscan / "reports" / "generated" / "bad.md", riftscan_root=riftscan)

    def test_review_includes_coordinate_proof_route_without_treating_visual_as_movement_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            match = riftscan / "reports" / "generated" / "currentpid-123-demo-addon-coordinate-matches.json"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            proof_route = root / "scripts" / "captures" / "route" / "coordinate-proof-route.json"
            self._write_match(match)
            self._write_pointer(pointer, match_file=match)
            self._write_latest_live_pointer(root)
            self._write_proof_route(proof_route)

            review = build_milestone_review(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                proof_route_summary=proof_route,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )

            self.assertEqual(review["coordinateProofRoute"]["status"], "visual-only")
            route_check = [
                check
                for check in review["checks"]
                if check["name"] == "coordinate-proof-route-visual-sidecar"
            ][0]
            self.assertEqual(route_check["status"], "pass")
            current_memory_check = [
                check
                for check in review["checks"]
                if check["name"] == "coordinate-proof-route-current-memory"
            ][0]
            self.assertEqual(current_memory_check["status"], "pass")
            self.assertFalse(review["coordinateProofRoute"]["decision"]["movementAllowed"])
            self.assertIn("Coordinate proof route", markdown_for_review(review))

    def test_review_resolves_latest_coordinate_proof_route_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            match = riftscan / "reports" / "generated" / "currentpid-123-demo-addon-coordinate-matches.json"
            current_pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            proof_route = root / "scripts" / "captures" / "route" / "coordinate-proof-route.json"
            route_pointer = root / "scripts" / "captures" / "latest-coordinate-proof-route.json"
            self._write_match(match)
            self._write_pointer(current_pointer, match_file=match)
            self._write_latest_live_pointer(root)
            self._write_proof_route(proof_route)
            self._write_proof_route_pointer(route_pointer, summary_json=proof_route)

            review = build_milestone_review(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=current_pointer,
                proof_route_summary=route_pointer,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )

            self.assertEqual(review["coordinateProofRoute"]["kind"], "coordinate-proof-route")
            self.assertEqual(review["coordinateProofRoute"]["status"], "visual-only")
            self.assertEqual(review["coordinateProofRoute"]["pointerPath"], str(route_pointer))
            route_check = [
                check
                for check in review["checks"]
                if check["name"] == "coordinate-proof-route-visual-sidecar"
            ][0]
            self.assertEqual(route_check["status"], "pass")

    def test_review_blocks_when_attached_coordinate_route_says_memory_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            match = riftscan / "reports" / "generated" / "currentpid-123-demo-addon-coordinate-matches.json"
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            proof_route = root / "scripts" / "captures" / "route" / "coordinate-proof-route.json"
            self._write_match(match)
            self._write_pointer(pointer, match_file=match)
            self._write_latest_live_pointer(root)
            self._write_proof_route(proof_route, status="candidate-only-stale-against-api-now")

            review = build_milestone_review(
                repo_root=root,
                riftscan_root=riftscan,
                current_proof_pointer=pointer,
                proof_route_summary=proof_route,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )

            self.assertEqual(review["status"], "blocked")
            route_check = [
                check
                for check in review["checks"]
                if check["name"] == "coordinate-proof-route-current-memory"
            ][0]
            self.assertEqual(route_check["status"], "fail")
            self.assertFalse(review["strategy"]["readOnlyProofAllowedByReview"])


if __name__ == "__main__":
    unittest.main()
