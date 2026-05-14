from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.coordinate_proof_route import build_coordinate_proof_route, main, update_current_truth, write_route


class CoordinateProofRouteTests(unittest.TestCase):
    def _root(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory()

    @staticmethod
    def _write_json(path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _target(pid: int = 123, hwnd: str = "0xABC") -> dict:
        return {
            "processName": "rift_x64",
            "processId": pid,
            "targetWindowHandle": hwnd,
            "processStartUtc": "2026-05-14T00:00:00Z",
        }

    def test_visual_only_stays_sidecar_and_blocks_movement(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            manifest = self._write_json(
                root / "scripts" / "captures" / "capture" / "manifest.json",
                {
                    "schema": "rift-window-capture-manifest/v1",
                    "runId": "capture-demo",
                    "status": "passed",
                    "target": {"pid": 123, "hwnd": "0xABC", "processName": "rift_x64"},
                    "quality": {"usable": True},
                    "safety": {
                        "movementSent": False,
                        "inputSent": False,
                        "cheatEngineUsed": False,
                        "x64dbgAttached": False,
                    },
                },
            )

            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
                capture_manifests=[manifest],
            )

            self.assertEqual(route["status"], "visual-only")
            self.assertEqual(route["visualEvidence"]["proofRole"], "sidecar_only_not_coordinate_or_movement_truth")
            self.assertFalse(route["decision"]["movementAllowed"])
            self.assertFalse(route["decision"]["visualEvidenceCanPromoteTruth"])
            self.assertIn("visual-evidence-is-not-coordinate-proof", route["blockers"])
            self.assertIn("api-reference-missing", route["blockers"])

    def test_stale_candidate_is_classified_against_api_now(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            api = self._write_json(
                root / "api.json",
                {
                    "processId": 123,
                    "processName": "rift_x64",
                    "targetWindowHandle": "0xABC",
                    "coordinate": {"x": 10.0, "y": 20.0, "z": 30.0},
                    "tolerance": 0.25,
                    "savedVariablesUse": "none",
                    "movementSent": False,
                    "noCheatEngine": True,
                },
            )
            readback = self._write_json(
                root / "readback.json",
                {
                    "ProcessId": 123,
                    "ProcessName": "rift_x64",
                    "TargetWindowHandle": "0xABC",
                    "NoCheatEngine": True,
                    "MovementSent": False,
                    "ReferenceMatchCount": 0,
                    "BestReferenceMatches": [
                        {
                            "CandidateId": "heap-old",
                            "CandidateAddressHex": "0x1000",
                            "ReferenceMatchesReadback": False,
                            "ReferenceMaxAbsDelta": 5.0,
                            "StableAcrossReadbackSamples": True,
                            "SourcePreviewMatchesReadback": True,
                        }
                    ],
                },
            )

            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
                api_reference_path=api,
                memory_readback_path=readback,
            )

            self.assertEqual(route["status"], "candidate-only-stale-against-api-now")
            self.assertTrue(route["memoryReadback"]["staleAgainstApiNow"])
            self.assertFalse(route["memoryReadback"]["apiMemoryMatch"])
            self.assertIn("memory-candidate-stale-against-api-now", route["blockers"])
            self.assertFalse(route["decision"]["movementAllowed"])

    def test_api_memory_match_allows_read_only_proof_not_movement(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            api = self._write_json(
                root / "api.json",
                {
                    "processId": 123,
                    "processName": "rift_x64",
                    "targetWindowHandle": "0xABC",
                    "coordinate": {"x": 10.0, "y": 20.0, "z": 30.0},
                    "tolerance": 0.25,
                },
            )
            readback = self._write_json(
                root / "readback.json",
                {
                    "ProcessId": 123,
                    "ProcessName": "rift_x64",
                    "TargetWindowHandle": "0xABC",
                    "NoCheatEngine": True,
                    "MovementSent": False,
                    "ReferenceMatchCount": 1,
                    "BestReferenceMatches": [
                        {
                            "CandidateId": "current-match",
                            "CandidateAddressHex": "0x2000",
                            "ReferenceMatchesReadback": True,
                            "ReferenceMaxAbsDelta": 0.001,
                            "StableAcrossReadbackSamples": True,
                        }
                    ],
                },
            )

            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
                api_reference_path=api,
                memory_readback_path=readback,
            )

            self.assertEqual(route["status"], "api-memory-match")
            self.assertTrue(route["decision"]["readOnlyProofAllowed"])
            self.assertFalse(route["decision"]["movementAllowed"])
            self.assertEqual(route["memoryReadback"]["selectedCandidate"]["candidateId"], "current-match")

    def test_reacquisition_scan_no_hits_blocks_static_root_routing(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            api = self._write_json(
                root / "api.json",
                {
                    "processId": 123,
                    "processName": "rift_x64",
                    "targetWindowHandle": "0xABC",
                    "coordinate": {"x": 10.0, "y": 20.0, "z": 30.0},
                    "tolerance": 0.25,
                },
            )
            scan = self._write_json(
                root / "scan.json",
                {
                    "mode": "riftreader-current-pid-coordinate-family-scan",
                    "processId": 123,
                    "processName": "rift_x64",
                    "targetWindowHandle": "0xABC",
                    "status": "blocked",
                    "blockers": ["no_xyz_triplets_near_reference_found"],
                    "warnings": ["scan time budget reached at 45s"],
                    "scan": {"hitCount": 0, "bytesScanned": 264241152, "durationSeconds": 45.173},
                    "artifacts": {"candidateJson": "candidates.json", "summaryJson": "scan.json"},
                },
            )

            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
                api_reference_path=api,
                memory_readback_path=scan,
            )

            self.assertEqual(route["status"], "reacquisition-no-current-hits")
            self.assertIn("memory-candidate-reacquisition-no-current-hits", route["blockers"])
            self.assertEqual(route["memoryReadback"]["reacquisition"]["hitCount"], 0)
            self.assertFalse(route["decision"]["readOnlyProofAllowed"])

    def test_reacquisition_scan_hits_allow_read_only_proof_not_movement(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            api = self._write_json(
                root / "api.json",
                {
                    "processId": 123,
                    "processName": "rift_x64",
                    "targetWindowHandle": "0xABC",
                    "coordinate": {"x": 10.0, "y": 20.0, "z": 30.0},
                    "tolerance": 0.25,
                },
            )
            scan = self._write_json(
                root / "scan.json",
                {
                    "mode": "riftreader-current-pid-coordinate-family-scan",
                    "processId": 123,
                    "processName": "rift_x64",
                    "targetWindowHandle": "0xABC",
                    "status": "passed",
                    "blockers": [],
                    "warnings": [],
                    "target": {"ownerPid": 123, "requestedHwnd": "0xABC"},
                    "scan": {"hitCount": 2, "bytesScanned": 1000000, "durationSeconds": 1.5},
                    "artifacts": {"candidateJson": "candidates.json", "summaryJson": "scan.json"},
                },
            )

            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
                api_reference_path=api,
                memory_readback_path=scan,
            )

            self.assertEqual(route["status"], "reacquisition-candidates-found")
            self.assertTrue(route["memoryReadback"]["apiMemoryMatch"])
            self.assertEqual(route["memoryReadback"]["target"]["processId"], 123)
            self.assertEqual(route["memoryReadback"]["reacquisition"]["hitCount"], 2)
            self.assertTrue(route["decision"]["readOnlyProofAllowed"])
            self.assertFalse(route["decision"]["movementAllowed"])

    def test_static_root_candidate_is_not_promotion_without_restart_validation(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            api = self._write_json(
                root / "api.json",
                {
                    "processId": 123,
                    "processName": "rift_x64",
                    "targetWindowHandle": "0xABC",
                    "coordinate": {"x": 10.0, "y": 20.0, "z": 30.0},
                    "tolerance": 0.25,
                },
            )
            readback = self._write_json(
                root / "readback.json",
                {
                    "ProcessId": 123,
                    "ProcessName": "rift_x64",
                    "TargetWindowHandle": "0xABC",
                    "ReferenceMatchCount": 1,
                    "BestReferenceMatches": [
                        {
                            "CandidateId": "current-match",
                            "CandidateAddressHex": "0x2000",
                            "ReferenceMatchesReadback": True,
                            "ReferenceMaxAbsDelta": 0.001,
                        }
                    ],
                },
            )
            static_summary = self._write_json(
                root / "static.json",
                {
                    "ProcessId": 123,
                    "ProcessName": "rift_x64",
                    "TargetWindowHandle": "0xABC",
                    "topModuleRva": "0x2641E38",
                    "moduleRvaHintCount": 9,
                    "promotionEligible": False,
                    "restartValidated": False,
                },
            )

            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
                api_reference_path=api,
                memory_readback_path=readback,
                static_root_summaries=[static_summary],
            )

            self.assertEqual(route["status"], "static-root-candidate")
            self.assertEqual(route["staticRootCandidates"]["candidateCount"], 1)
            self.assertEqual(route["staticRootCandidates"]["provenCount"], 0)
            self.assertIn("static-root-candidate-not-restart-validated", route["blockers"])
            self.assertFalse(route["decision"]["movementAllowed"])

    def test_candidate_routing_is_reported_but_not_proof(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            center_file = self._write_json(
                root / "centers.json",
                {
                    "centers": [
                        {"rank": 1, "label": "best", "address": "0x1000", "maxAbsDelta": 0.1},
                        {"rank": 2, "label": "next", "address": "0x2000", "maxAbsDelta": 0.2},
                    ]
                },
            )
            comparison = self._write_json(
                root / "comparison.json",
                {
                    "status": "candidate-only-no-two-reference-match",
                    "candidateFiles": [
                        {"matchCount": 0, "displacedMatchCount": 1, "bothReferenceMatchCount": 0}
                    ],
                },
            )

            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
                center_files=[center_file],
                candidate_comparisons=[comparison],
            )

            self.assertEqual(route["candidateRouting"]["status"], "candidate-routing-ready")
            self.assertEqual(route["candidateRouting"]["centerCount"], 2)
            self.assertEqual(route["candidateRouting"]["bothReferenceMatchCount"], 0)
            self.assertFalse(route["candidateRouting"]["movementProof"])
            self.assertIn("candidate-comparison-has-no-both-reference-match", route["warnings"])
            self.assertFalse(route["decision"]["movementAllowed"])

    def test_displaced_readiness_is_reported_as_gate_not_proof(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            readiness = self._write_json(
                root / "readiness.json",
                {
                    "status": "blocked",
                    "blockers": ["displaced-reference-age-exceeded:400>300"],
                    "warnings": ["displaced-reference-older-than-baseline-reference"],
                    "artifacts": {
                        "summaryJson": "readiness.json",
                        "summaryMarkdown": "readiness.md",
                        "summaryHtml": "readiness.html",
                    },
                    "safety": {
                        "movementSent": False,
                        "inputSent": False,
                        "reloaduiSent": False,
                        "screenshotKeySent": False,
                        "noCheatEngine": True,
                        "x64dbgAttached": False,
                        "processAttachOrMemoryReadStarted": False,
                        "providerWrite": False,
                    },
                    "baselineReference": {
                        "path": "baseline.json",
                        "target": {"processId": 123, "targetWindowHandle": "0xABC", "processName": "rift_x64"},
                    },
                    "displacedReference": {
                        "path": "displaced.json",
                        "target": {"processId": 123, "targetWindowHandle": "0xABC", "processName": "rift_x64"},
                    },
                    "ageDeltaSeconds": 400.0,
                    "delta": {"planarDistance": 4.25, "maxAbsDelta": 4.0},
                },
            )

            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
                displaced_readiness_summaries=[readiness],
            )

            self.assertEqual(route["displacedReadiness"]["status"], "blocked")
            self.assertEqual(route["displacedReadiness"]["summaryCount"], 1)
            self.assertEqual(route["displacedReadiness"]["items"][0]["planarDistance"], 4.25)
            self.assertFalse(route["displacedReadiness"]["movementProof"])
            self.assertFalse(route["displacedReadiness"]["coordinateProof"])
            self.assertIn("displaced-readiness-not-passed:blocked", route["warnings"])
            self.assertEqual(
                route["recommendedActions"][0]["action"],
                "Refresh the displaced-pose reference before any promotion attempt.",
            )
            self.assertFalse(route["decision"]["movementAllowed"])

    def test_cli_returns_blocked_exit_until_read_only_proof_is_allowed(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            manifest = self._write_json(
                root / "scripts" / "captures" / "capture" / "manifest.json",
                {
                    "schema": "rift-window-capture-manifest/v1",
                    "status": "passed",
                    "target": {"pid": 123, "hwnd": "0xABC", "processName": "rift_x64"},
                    "quality": {"usable": True},
                    "safety": {"movementSent": False, "inputSent": False},
                },
            )
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(root),
                        "--pid",
                        "123",
                        "--hwnd",
                        "0xABC",
                        "--capture-manifest",
                        str(manifest),
                        "--compact-json",
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "visual-only")

    def test_write_route_emits_markdown_html_and_latest_pointer(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )
            output_root = root / "scripts" / "captures" / "route"

            write_route(route, output_root, repo_root=root)

            self.assertTrue((output_root / "coordinate-proof-route.json").exists())
            self.assertTrue((output_root / "coordinate-proof-route.md").exists())
            html_path = output_root / "coordinate-proof-route.html"
            pointer_path = root / "scripts" / "captures" / "latest-coordinate-proof-route.json"
            self.assertTrue(html_path.exists())
            self.assertTrue(pointer_path.exists())
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            self.assertEqual(pointer["status"], route["status"])
            self.assertFalse(pointer["movementAllowed"])
            self.assertIn("Visual capture is sidecar evidence only", html_path.read_text(encoding="utf-8"))

    def test_update_current_truth_records_route_and_candidate_routing(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            truth = root / "docs" / "recovery" / "current-truth.json"
            self._write_json(truth, {"visualEvidenceRouting": {}})
            truth_md = root / "docs" / "recovery" / "current-truth.md"
            truth_md.write_text(
                "\n".join(
                    [
                        "# Current truth",
                        "",
                        "## Visual/capture proof-route policy — test",
                        "",
                        "| Field | Value |",
                        "|---|---|",
                        "| Latest route status | `old` |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
            )
            write_route(route, root / "scripts" / "captures" / "route", repo_root=root)

            update_current_truth(route, root)

            routing = json.loads(truth.read_text(encoding="utf-8"))["visualEvidenceRouting"]
            self.assertEqual(routing["latestRouteStatus"], route["status"])
            self.assertEqual(routing["latestProofRoute"], "scripts/captures/route/coordinate-proof-route.json")
            self.assertIn("| Latest route | `scripts/captures/route/coordinate-proof-route.json` |", truth_md.read_text(encoding="utf-8"))

    def test_update_current_truth_records_displaced_readiness(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            truth = root / "docs" / "recovery" / "current-truth.json"
            self._write_json(truth, {"visualEvidenceRouting": {}})
            truth_md = root / "docs" / "recovery" / "current-truth.md"
            truth_md.write_text(
                "\n".join(
                    [
                        "# Current truth",
                        "",
                        "## Visual/capture proof-route policy — test",
                        "",
                        "| Field | Value |",
                        "|---|---|",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            readiness = self._write_json(
                root / "readiness.json",
                {
                    "status": "passed",
                    "artifacts": {"summaryJson": "readiness.json", "summaryHtml": "readiness.html"},
                    "safety": {"movementSent": False, "inputSent": False, "noCheatEngine": True},
                    "baselineReference": {
                        "target": {"processId": 123, "targetWindowHandle": "0xABC", "processName": "rift_x64"}
                    },
                    "displacedReference": {
                        "target": {"processId": 123, "targetWindowHandle": "0xABC", "processName": "rift_x64"}
                    },
                },
            )
            route = build_coordinate_proof_route(
                repo_root=root,
                process_id=123,
                target_window_handle="0xABC",
                process_name="rift_x64",
                displaced_readiness_summaries=[readiness],
            )
            write_route(route, root / "scripts" / "captures" / "route", repo_root=root)

            update_current_truth(route, root)

            routing = json.loads(truth.read_text(encoding="utf-8"))["visualEvidenceRouting"]
            self.assertEqual(routing["latestDisplacedReadinessStatus"], "passed")
            self.assertEqual(routing["latestDisplacedReadinessSummary"], "readiness.json")
            self.assertIn("| Latest displaced readiness status | `passed` |", truth_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
