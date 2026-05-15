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
        "movement_key": "w",
        "hold_milliseconds": 750,
        "input_mode": "ScanCode",
        "pose_batch_timeout_seconds": 600,
        "movement_approved": False,
        "allow_current_truth_update": False,
        "run_proofonly": False,
        "write_restart_profile": False,
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
        self.assertEqual(labels[0], "target-control-visual-gate")
        self.assertIn("reference-chromalink-fast-path", labels)
        self.assertIn("reference-rrapicoord-fallback", labels)
        self.assertIn("scan-plan-batch-stop-on-hit", labels)
        self.assertIn("proofonly-final-gate", labels)
        self.assertFalse(any(step["dryRunExecuted"] for step in plan["steps"]))

    def test_no_movement_flag_is_added_without_explicit_approval(self) -> None:
        repo_root = fast.find_repo_root(Path(__file__).resolve())
        args = default_args(scan_plan_top_count=20)
        plan = fast.build_recovery_plan(args, repo_root, Path(tempfile.gettempdir()))
        pose_step = next(step for step in plan["steps"] if step["label"] == "three-pose-displacement-validation")
        self.assertIn("-NoMovement", pose_step["command"])
        self.assertFalse(pose_step["sendsInputIfExecuted"])

    def test_chromalink_reference_parser_requires_passed_reference_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reference = Path(temp_dir) / "reference.json"
            reference.write_text("{}", encoding="utf-8")
            parsed = {"status": "passed", "artifacts": {"referenceJson": str(reference)}}

            path, blockers, warnings = fast.chromalink_reference_from_summary(parsed)

        self.assertEqual(path, reference.resolve())
        self.assertEqual(blockers, [])
        self.assertEqual(warnings, [])

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
