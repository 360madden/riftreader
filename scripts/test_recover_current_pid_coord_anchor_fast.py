#!/usr/bin/env python3

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

import recover_current_pid_coord_anchor_fast as fast


def default_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "pid": 1234,
        "hwnd": "0xABCDEF",
        "process_name": "rift_x64",
        "title_contains": "RIFT",
        "scan_plan_top_count": 80,
        "scan_stride": 4,
        "scan_tolerance": 2.0,
        "max_seconds_per_scan_range": 45,
        "scan_batch_timeout_seconds": 900,
        "scan_reference_timeout_seconds": 45,
        "chromalink_timeout_seconds": 3,
        "reference_timeout_seconds": 180,
        "reference_scan_context_bytes": 65536,
        "reference_max_hits": 2048,
        "visual_gate_timeout_seconds": 10,
        "poses": 3,
        "escalate_poses": 5,
        "minimum_promotion_pose_support": 3,
        "minimum_movement_pulses_for_promotion": 2,
        "minimum_displaced_pose_support": 2,
        "minimum_planar_displacement": 1.0,
        "movement_key": "w",
        "hold_milliseconds": 750,
        "adaptive_movement_sequence": None,
        "input_mode": "ScanCode",
        "pose_batch_timeout_seconds": 600,
        "movement_approved": False,
        "allow_current_truth_update": False,
        "run_proofonly": False,
        "write_restart_profile": False,
        "use_restart_profile": False,
        "restart_profile_path": "docs/recovery/coordinate-recovery-profile.json",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class FastRecoveryDryRunTests(unittest.TestCase):
    def test_plan_contains_fast_lane_order_and_no_live_execution(self) -> None:
        repo_root = fast.find_repo_root(Path(__file__).resolve())
        with tempfile.TemporaryDirectory() as temp_dir:
            args = default_args()
            plan = fast.build_recovery_plan(args, repo_root, Path(temp_dir))

        labels = [step["label"] for step in plan["steps"]]
        self.assertEqual(labels[0], "target-window-discovery-preflight")
        self.assertEqual(labels[1], "target-control-visual-gate")
        self.assertIn("reference-chromalink-fast-path", labels)
        self.assertIn("reference-rrapicoord-fallback", labels)
        self.assertIn("scan-plan-batch-stop-on-hit", labels)
        self.assertIn("proofonly-final-gate", labels)
        self.assertFalse(any(step["dryRunExecuted"] for step in plan["steps"]))
        promote_step = next(step for step in plan["steps"] if step["label"] == "promote-current-proof-anchor")
        self.assertIn("-BatchSummaryFile", promote_step["command"])

    def test_no_movement_flag_is_added_without_explicit_approval(self) -> None:
        repo_root = fast.find_repo_root(Path(__file__).resolve())
        args = default_args(scan_plan_top_count=20)
        plan = fast.build_recovery_plan(args, repo_root, Path(tempfile.gettempdir()))
        pose_step = next(step for step in plan["steps"] if step["label"] == "three-pose-displacement-validation")
        self.assertIn("-NoMovement", pose_step["command"])
        self.assertFalse(pose_step["sendsInputIfExecuted"])
        self.assertIn("-MinimumDisplacedPoseSupport", pose_step["command"])
        self.assertIn("-MinimumPlanarDisplacement", pose_step["command"])

    def test_default_adaptive_movement_sequence_matches_fast_recovery_plan(self) -> None:
        args = default_args()

        attempts = fast.parse_adaptive_movement_sequence(fast.adaptive_movement_sequence_text(args))

        self.assertEqual(
            [(item["key"], item["holdMilliseconds"]) for item in attempts],
            [("w", 750), ("w", 1500), ("q", 1000), ("e", 1000)],
        )

    def test_custom_first_movement_attempt_keeps_safe_fallbacks(self) -> None:
        args = default_args(movement_key="q", hold_milliseconds=500)

        attempts = fast.parse_adaptive_movement_sequence(fast.adaptive_movement_sequence_text(args))

        self.assertEqual(attempts[0]["key"], "q")
        self.assertEqual(attempts[0]["holdMilliseconds"], 500)
        self.assertIn(("w", 1500), [(item["key"], item["holdMilliseconds"]) for item in attempts])

    def test_duplicate_rift_windows_block_target_discovery_preflight(self) -> None:
        parsed = {
            "count": 2,
            "windows": [
                {"ProcessId": 111, "WindowHandleHex": "0xAAA", "Title": "RIFT"},
                {"ProcessId": 222, "WindowHandleHex": "0xBBB", "Title": "RIFT"},
            ],
        }

        gate = fast.target_discovery_preflight(parsed, requested_pid=222, requested_hwnd="0xBBB")

        self.assertFalse(gate["passed"])
        self.assertEqual(gate["windowCount"], 2)
        self.assertTrue(gate["matchedRequestedTarget"])
        self.assertIn("multiple-rift-clients-present-current-anchor-recovery-blocked:2", gate["blockers"])

    def test_single_requested_rift_window_passes_target_discovery_preflight(self) -> None:
        parsed = {
            "count": 1,
            "windows": [{"ProcessId": 222, "WindowHandleHex": "0xBBB", "Title": "RIFT"}],
        }

        gate = fast.target_discovery_preflight(parsed, requested_pid=222, requested_hwnd="0xBBB")

        self.assertTrue(gate["passed"])
        self.assertEqual(gate["blockers"], [])
        self.assertTrue(gate["matchedRequestedTarget"])

    def test_zero_coordinate_delta_does_not_pass_displacement_gate(self) -> None:
        parsed = {
            "status": "promotion-candidate-found",
            "topCandidate": {
                "key": "api-family-hit-000001@0x1000",
                "candidateId": "api-family-hit-000001",
                "candidateAddressHex": "0x1000",
            },
            "poseResults": [
                {
                    "poseIndex": 1,
                    "poseName": "pose-01",
                    "reference": {"Coordinate": {"X": 100.0, "Y": 20.0, "Z": 200.0}},
                    "referenceMatches": [
                        {
                            "CandidateId": "api-family-hit-000001",
                            "CandidateAddressHex": "0x1000",
                        }
                    ],
                },
                {
                    "poseIndex": 2,
                    "poseName": "pose-02",
                    "reference": {"Coordinate": {"X": 100.0, "Y": 20.0, "Z": 200.0}},
                    "referenceMatches": [
                        {
                            "CandidateId": "api-family-hit-000001",
                            "CandidateAddressHex": "0x1000",
                        }
                    ],
                },
                {
                    "poseIndex": 3,
                    "poseName": "pose-03",
                    "reference": {"Coordinate": {"X": 100.0, "Y": 20.0, "Z": 200.0}},
                    "referenceMatches": [
                        {
                            "CandidateId": "api-family-hit-000001",
                            "CandidateAddressHex": "0x1000",
                        }
                    ],
                },
            ],
        }

        gate = fast.displacement_gate_from_pose_summary(
            parsed,
            minimum_displaced_pose_support=2,
            minimum_planar_displacement=1.0,
        )

        self.assertFalse(gate["passed"])
        self.assertEqual(gate["displacedPoseCount"], 0)
        self.assertEqual(gate["maxPlanarDisplacement"], 0.0)
        self.assertIn("displaced-pose-count-too-low:0<2", gate["blockers"])
        self.assertIn("max-planar-displacement-too-low:0.000000<1.0", gate["blockers"])

    def test_real_coordinate_delta_passes_displacement_gate(self) -> None:
        parsed = {
            "status": "promotion-candidate-found",
            "topCandidate": {
                "key": "api-family-hit-000001@0x1000",
                "candidateId": "api-family-hit-000001",
                "candidateAddressHex": "0x1000",
            },
            "poseResults": [
                {
                    "poseIndex": 1,
                    "poseName": "pose-01",
                    "reference": {"Coordinate": {"X": 100.0, "Y": 20.0, "Z": 200.0}},
                    "referenceMatches": [
                        {
                            "CandidateId": "api-family-hit-000001",
                            "CandidateAddressHex": "0x1000",
                        }
                    ],
                },
                {
                    "poseIndex": 2,
                    "poseName": "pose-02",
                    "reference": {"Coordinate": {"X": 101.5, "Y": 20.0, "Z": 200.0}},
                    "referenceMatches": [
                        {
                            "CandidateId": "api-family-hit-000001",
                            "CandidateAddressHex": "0x1000",
                        }
                    ],
                },
                {
                    "poseIndex": 3,
                    "poseName": "pose-03",
                    "reference": {"Coordinate": {"X": 103.0, "Y": 20.0, "Z": 200.0}},
                    "referenceMatches": [
                        {
                            "CandidateId": "api-family-hit-000001",
                            "CandidateAddressHex": "0x1000",
                        }
                    ],
                },
            ],
        }

        gate = fast.displacement_gate_from_pose_summary(
            parsed,
            minimum_displaced_pose_support=2,
            minimum_planar_displacement=1.0,
        )

        self.assertTrue(gate["passed"])
        self.assertEqual(gate["displacedPoseCount"], 2)
        self.assertEqual(gate["topCandidateDisplacedPoseSupportCount"], 2)
        self.assertAlmostEqual(gate["maxPlanarDisplacement"], 3.0)
        self.assertEqual(gate["blockers"], [])

    def test_chromalink_reference_parser_requires_passed_reference_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reference = Path(temp_dir) / "reference.json"
            reference.write_text("{}", encoding="utf-8")
            parsed = {"status": "passed", "artifacts": {"referenceJson": str(reference)}}

            path, blockers, warnings = fast.chromalink_reference_from_summary(parsed)

        self.assertEqual(path, reference.resolve())
        self.assertEqual(blockers, [])
        self.assertEqual(warnings, [])

    def test_chromalink_reference_parser_blocks_stale_missing_reference(self) -> None:
        parsed = {
            "status": "blocked",
            "blockers": ["world-state-player-position-stale"],
            "artifacts": {"referenceJson": None},
        }

        path, blockers, _warnings = fast.chromalink_reference_from_summary(parsed)

        self.assertIsNone(path)
        self.assertIn("world-state-player-position-stale", blockers)
        self.assertIn("chromalink-status-not-passed:blocked", blockers)
        self.assertIn("chromalink-reference-json-missing", blockers)

    def test_scan_parser_finds_candidate_jsonl_from_hit_range(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = Path(temp_dir) / "candidates.jsonl"
            candidate.write_text('{"id":"hit"}\n', encoding="utf-8")
            parsed = {
                "status": "passed",
                "scan": {"totalHits": 1},
                "rangeResults": [{"rank": 4, "hitCount": 1, "candidateJsonl": str(candidate)}],
            }

            path, best_range, blockers = fast.candidate_file_from_scan_summary(parsed)

        self.assertEqual(path, candidate.resolve())
        self.assertEqual(best_range["rank"], 4)
        self.assertEqual(blockers, [])

    def test_scan_parser_accepts_single_family_scan_hit_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = Path(temp_dir) / "candidates.jsonl"
            candidate.write_text('{"id":"hit"}\n', encoding="utf-8")
            parsed = {
                "status": "passed",
                "scan": {
                    "hitCount": 1,
                    "minAddress": "0x1000",
                    "maxAddress": "0x2000",
                    "durationSeconds": 1.25,
                    "bestHit": {"addressHex": "0x1800"},
                },
                "artifacts": {"candidateJsonl": str(candidate), "summaryJson": str(Path(temp_dir) / "summary.json")},
            }

            path, best_range, blockers = fast.candidate_file_from_scan_summary(parsed)

        self.assertEqual(path, candidate.resolve())
        self.assertEqual(best_range["source"], "single-family-scan")
        self.assertEqual(best_range["hitCount"], 1)
        self.assertEqual(best_range["minAddressHex"], "0x1000")
        self.assertEqual(blockers, [])

    def test_use_restart_profile_adds_profile_scan_before_inventory(self) -> None:
        repo_root = fast.find_repo_root(Path(__file__).resolve())
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            profile = temp / "coordinate-recovery-profile.json"
            profile.write_text(
                """{
                  "kind": "riftreader-coordinate-recovery-profile",
                  "generatedAtUtc": "2026-05-15T00:00:00Z",
                  "candidateJsonl": "old-candidate.jsonl",
                  "bestScanRange": {
                    "rank": 1,
                    "minAddressHex": "0x1000",
                    "maxAddressHex": "0x2000",
                    "hitCount": 1
                  }
                }""",
                encoding="utf-8",
            )
            args = default_args(use_restart_profile=True, restart_profile_path=str(profile))
            plan = fast.build_recovery_plan(args, repo_root, temp)

        labels = [step["label"] for step in plan["steps"]]
        self.assertIn("profile-priority-family-scan", labels)
        self.assertLess(labels.index("reference-rrapicoord-fallback"), labels.index("profile-priority-family-scan"))
        self.assertLess(labels.index("profile-priority-family-scan"), labels.index("memory-region-inventory"))
        profile_step = next(step for step in plan["steps"] if step["label"] == "profile-priority-family-scan")
        self.assertIn("--min-address", profile_step["command"])
        self.assertIn("0x1000", profile_step["command"])

    def test_restart_profile_records_profile_and_final_proof_fields(self) -> None:
        summary = {
            "artifacts": {"runDirectory": "run-dir"},
            "target": {"pid": 1234, "hwnd": "0xABCDEF"},
            "operator": {"x64dbgMode": "offline-read-only"},
            "execution": {
                "referenceProvider": "chromalink-world-state",
                "referenceJson": "reference.json",
                "candidateJsonl": "candidates.jsonl",
                "bestScanRange": {"source": "single-family-scan", "hitCount": 1},
                "profileScanUsed": True,
                "profileScanRange": {"minAddressHex": "0x1000", "maxAddressHex": "0x2000"},
                "profileScanSummaryJson": "profile-scan-summary.json",
                "promotionBatchSummaryJson": "promotion-summary.json",
                "proofOnlySummaryJson": "proofonly-summary.json",
                "stages": [
                    {"label": "profile-priority-family-scan", "phase": "profile-scan", "status": "passed", "durationSeconds": 2.0},
                    {"label": "proofonly-final-gate", "phase": "proofonly", "status": "passed", "durationSeconds": 3.0},
                ],
            },
        }

        profile = fast.build_restart_profile(summary)

        self.assertTrue(profile["profileScanUsed"])
        self.assertEqual(profile["profileScanSummaryJson"], "profile-scan-summary.json")
        self.assertEqual(profile["promotionBatchSummaryJson"], "promotion-summary.json")
        self.assertEqual(profile["proofOnlySummaryJson"], "proofonly-summary.json")
        self.assertEqual(profile["stageTimings"][-1]["label"], "proofonly-final-gate")

    def test_execute_blocks_without_exact_pid_hwnd_before_child_commands(self) -> None:
        repo_root = fast.find_repo_root(Path(__file__).resolve())
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            args = default_args(pid=None, hwnd=None)
            summary = {
                "status": "passed",
                "blockers": [],
                "warnings": [],
                "safety": {"targetMemoryBytesReadOrWritten": False},
                "operator": {"x64dbgMode": "offline-read-only"},
                "target": {"pid": None, "hwnd": None},
                "artifacts": {"runDirectory": str(run_dir)},
                "plan": fast.build_recovery_plan(args, repo_root, run_dir),
            }

            exit_code = fast.execute_recovery_plan(summary, args, repo_root, run_dir)

        self.assertEqual(exit_code, 2)
        self.assertEqual(summary["status"], "blocked")
        self.assertIn("execute-requires-exact-pid-and-hwnd", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
