from __future__ import annotations

import base64
import json
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rift_live_test.baselines import (
    record_baseline_summary,
    select_baselines_for_fresh_summary,
)
from rift_live_test.commands import extract_first_json
from rift_live_test.profiles import load_profile
from rift_live_test.runner import LiveTestRunner
from rift_live_test.status import BLOCKED_LIVE_FLAG_REQUIRED, BLOCKED_TARGET_MISMATCH


class LiveTestOrchestratorTests(unittest.TestCase):
    @staticmethod
    def _write_pose_summary(
        path: Path,
        *,
        process_id: int = 123,
        hwnd: str = "0x123",
        x: float = 1.0,
        y: float = 2.0,
        z: float = 3.0,
        candidate_id: str = "rift-addon-coordinate-candidate-000001",
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "GeneratedAtUtc": "2026-05-07T00:00:00+00:00",
                    "ProcessName": "rift_x64",
                    "ProcessId": process_id,
                    "TargetWindowHandle": hwnd,
                    "NoCheatEngine": True,
                    "MovementSent": False,
                    "ReferenceCoordinate": {"X": x, "Y": y, "Z": z},
                    "BestReferenceMatches": [
                        {
                            "CandidateId": candidate_id,
                            "ReferenceMatchesReadback": True,
                            "StableAcrossReadbackSamples": True,
                            "FirstDecodedSample": {"X": x, "Y": y, "Z": z},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_extract_first_json_skips_noise(self) -> None:
        payload, text = extract_first_json('warning before\n{"Status":"valid"}\ntrailing')
        self.assertEqual(payload["Status"], "valid")
        self.assertEqual(text, '{"Status":"valid"}')

    def test_profile_merges_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "profiles.json"
            (root / "old.json").write_text("{}", encoding="utf-8")
            config.write_text(
                json.dumps(
                    {
                        "defaults": {
                            "processName": "rift_x64",
                            "outputRoot": "captures",
                            "promotionReferenceReadbackSummary": "old.json",
                            "maxHoldMilliseconds": 1000,
                            "maxPulseCount": 3,
                        },
                        "profiles": {
                            "Forward250": {
                                "mode": "live-input",
                                "input": {
                                    "key": "w",
                                    "holdMilliseconds": 250,
                                    "pulseCount": 1,
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile = load_profile(root, config, "Forward250")
            self.assertEqual(profile["processName"], "rift_x64")
            self.assertEqual(profile["input"]["holdMilliseconds"], 250)
            self.assertTrue(Path(profile["outputRoot"]).is_absolute())

    def test_profile_rejects_live_flag_opt_out_for_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "profiles.json"
            (root / "old.json").write_text("{}", encoding="utf-8")
            config.write_text(
                json.dumps(
                    {
                        "defaults": {
                            "outputRoot": "captures",
                            "promotionReferenceReadbackSummary": "old.json",
                        },
                        "profiles": {
                            "UnsafeForward": {
                                "mode": "live-input",
                                "requireLiveFlagForInput": False,
                                "input": {
                                    "key": "w",
                                    "holdMilliseconds": 250,
                                    "pulseCount": 1,
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "cannot disable requireLiveFlagForInput"):
                load_profile(root, config, "UnsafeForward")

    def test_live_retry_is_blocked_after_any_movement_started(self) -> None:
        payload = {
            "Status": "blocked-preflight-age-budget",
            "MovementSent": True,
            "MovementAttempted": True,
            "Issues": ["proof_anchor_remaining_age_budget_too_low:remaining=3"],
        }
        self.assertTrue(LiveTestRunner._movement_started(payload))
        self.assertFalse(LiveTestRunner._safe_to_retry_live_input(payload))

    def test_auto_refresh_attempts_are_capped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile={
                    "outputRoot": str(root / "captures"),
                    "maxAutoRefreshAttempts": 1,
                    "autoRefreshProofOnLowAgeBudget": True,
                },
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            payload = {
                "Status": "blocked-preflight-age-budget",
                "MovementSent": False,
                "MovementAttempted": False,
                "Issues": ["proof_anchor_remaining_age_budget_too_low:remaining=3"],
            }
            self.assertTrue(runner._can_refresh_for(payload))
            self.assertEqual(runner.auto_refresh_attempts_used, 1)
            self.assertFalse(runner._can_refresh_for(payload))

    def test_input_profile_blocks_without_live_before_proof_refresh_even_if_profile_opts_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = {
                "mode": "live-input",
                "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 1},
                "outputRoot": str(root / "captures"),
                "requireLiveFlagForInput": False,
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile=profile,
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            with patch(
                "rift_live_test.runner.verify_target",
                return_value={"valid": True, "status": "valid", "targetWindowHandle": "0x123"},
            ), patch.object(runner, "_refresh_proof") as refresh:
                summary = runner.run()
            self.assertEqual(summary["status"], BLOCKED_LIVE_FLAG_REQUIRED)
            self.assertFalse(summary["movementSent"])
            refresh.assert_not_called()

    def test_target_mismatch_blocks_before_any_proof_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = {
                "mode": "proof-only",
                "input": None,
                "outputRoot": str(root / "captures"),
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile=profile,
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            with patch(
                "rift_live_test.runner.verify_target",
                return_value={
                    "valid": False,
                    "status": "window-not-found",
                    "issues": ["target_window_not_found"],
                },
            ), patch.object(runner, "_refresh_proof") as refresh:
                summary = runner.run()
            self.assertEqual(summary["status"], BLOCKED_TARGET_MISMATCH)
            self.assertIn("target_window_not_found", summary["issues"])
            refresh.assert_not_called()

    def test_child_commands_receive_process_name_and_proof_anchor_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            proof_anchor = root / "custom-proof-anchor.json"
            profile = {
                "mode": "live-input",
                "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 1},
                "outputRoot": str(root / "captures"),
                "processName": "rift_x64",
                "proofAnchorFile": str(proof_anchor),
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile=profile,
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            with patch.object(
                runner,
                "_run_ps1",
                return_value=SimpleNamespace(json_data={"Status": "valid"}, exit_code=0),
            ) as run_ps1:
                runner._assert_current_readback(label="readback")
                runner._run_gated_wrapper(dry_run=True, label="dry")

            readback_args = run_ps1.call_args_list[0].args[2]
            dry_args = run_ps1.call_args_list[1].args[2]
            for argv in (readback_args, dry_args):
                self.assertIn("-ProcessName", argv)
                self.assertIn("-ProofCoordAnchorFile", argv)
                self.assertEqual(argv[argv.index("-ProofCoordAnchorFile") + 1], str(proof_anchor))

    def test_promote_command_receives_process_name_and_proof_anchor_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            proof_anchor = root / "custom-proof-anchor.json"
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile={
                    "outputRoot": str(root / "captures"),
                    "processName": "rift_x64",
                    "proofAnchorFile": str(proof_anchor),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            with patch.object(
                runner,
                "_run_command",
                return_value=SimpleNamespace(json_data={"ProofValidationStatus": "validated"}, exit_code=0),
            ) as run_command:
                runner._run_promote([str(root / "a.json"), str(root / "b.json")])

            encoded = run_command.call_args.args[1][-1]
            script = base64.b64decode(encoded).decode("utf-16le")
            self.assertIn("-ProcessName 'rift_x64'", script)
            self.assertIn(f"-OutputFile '{proof_anchor}'", script)

    def test_promotion_reference_target_mismatch_is_detected_before_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "ProcessName": "rift_x64",
                        "ProcessId": 999,
                        "TargetWindowHandle": "0x123",
                    }
                ),
                encoding="utf-8",
            )
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "promotionReferenceReadbackSummary": str(baseline),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            issues = runner._validate_promotion_reference_target()
            self.assertIn("promotion_reference_pid_mismatch:actual=999;expected=123", issues)

    def test_progress_file_is_written_incrementally(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile={
                    "mode": "live-input",
                    "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 1},
                    "outputRoot": str(root / "captures"),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )

            runner._state("verify-target", "passed", detail="pid=123;hwnd=0x123")

            progress = json.loads(runner.progress_file.read_text(encoding="utf-8"))
            self.assertEqual(progress["status"], "running")
            self.assertFalse(progress["finalSummaryWritten"])
            self.assertEqual(progress["states"][0]["state"], "verify-target")

            latest = json.loads(
                (root / "scripts" / "captures" / "latest-live-test-run.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(latest["runProgressFile"], str(runner.progress_file))
            self.assertFalse(latest["finalSummaryWritten"])

    def test_final_summary_marks_progress_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )

            summary = runner._finish(
                "passed-proof-only",
                final_json={
                    "Status": "valid",
                    "MovementSent": False,
                    "MovementAttempted": False,
                    "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0},
                },
            )

            progress = json.loads(runner.progress_file.read_text(encoding="utf-8"))
            self.assertTrue(progress["finalSummaryWritten"])
            self.assertEqual(progress["status"], "passed-proof-only")
            self.assertEqual(summary["runProgressFile"], str(runner.progress_file))

    def test_baseline_pool_selects_compatible_displaced_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pool = root / "pool.json"
            old = root / "old.json"
            near = root / "near.json"
            wrong_pid = root / "wrong-pid.json"
            fresh = root / "fresh.json"
            self._write_pose_summary(old, x=8.0, z=18.0)
            self._write_pose_summary(near, x=10.1, z=20.1)
            self._write_pose_summary(wrong_pid, process_id=999, x=0.0, z=0.0)
            self._write_pose_summary(fresh, x=10.2, z=20.2)
            record_baseline_summary(pool_file=pool, summary_file=old, source="test-old")
            record_baseline_summary(pool_file=pool, summary_file=near, source="test-near")
            record_baseline_summary(pool_file=pool, summary_file=wrong_pid, source="test-wrong")

            selected, diagnostics = select_baselines_for_fresh_summary(
                fresh_summary_file=fresh,
                candidate_paths=[str(old), str(near), str(wrong_pid)],
                process_id=123,
                target_window_handle="0x123",
                process_name="rift_x64",
                candidate_id="rift-addon-coordinate-candidate-000001",
                min_reference_displacement=1.0,
                max_count=4,
            )

            self.assertEqual(diagnostics["status"], "selected")
            self.assertEqual(selected, [str(old.resolve()), str(fresh.resolve())])
            self.assertEqual(diagnostics["compatibleDisplacedCount"], 1)
            wrong = [item for item in diagnostics["candidates"] if "wrong-pid" in item["summaryFile"]][0]
            self.assertEqual(wrong["status"], "incompatible")

    def test_baseline_pool_reports_no_displaced_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            near = root / "near.json"
            fresh = root / "fresh.json"
            self._write_pose_summary(near, x=1.0, z=1.0)
            self._write_pose_summary(fresh, x=1.1, z=1.1)

            selected, diagnostics = select_baselines_for_fresh_summary(
                fresh_summary_file=fresh,
                candidate_paths=[str(near)],
                process_id=123,
                target_window_handle="0x123",
                process_name="rift_x64",
                candidate_id="rift-addon-coordinate-candidate-000001",
                min_reference_displacement=1.0,
                max_count=4,
            )

            self.assertEqual(selected, [])
            self.assertEqual(diagnostics["status"], "no-compatible-displaced-baseline")

    def test_series_runs_one_wrapper_pulse_at_a_time(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ForwardSeries2x250",
                profile={
                    "mode": "live-input-series",
                    "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 2},
                    "outputRoot": str(root / "captures"),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            dry_1 = {"Status": "dry-run-valid", "SummaryFile": "dry-1.json"}
            live_1 = {
                "Status": "passed",
                "SummaryFile": "live-1.json",
                "MovementSent": True,
                "MovementAttempted": True,
                "Preflight": {
                    "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0}
                },
                "PostReadback": {
                    "CurrentCoordinate": {"X": 1.1, "Y": 2.0, "Z": 2.7}
                },
                "CoordinateDelta": {
                    "DeltaX": 0.1,
                    "DeltaY": 0.0,
                    "DeltaZ": -0.3,
                    "PlanarDistance": 0.316,
                    "SpatialDistance": 0.316,
                },
            }
            dry_2 = {"Status": "dry-run-valid", "SummaryFile": "dry-2.json"}
            live_2 = {
                "Status": "passed",
                "SummaryFile": "live-2.json",
                "MovementSent": True,
                "MovementAttempted": True,
                "Preflight": {
                    "CurrentCoordinate": {"X": 1.1, "Y": 2.0, "Z": 2.7}
                },
                "PostReadback": {
                    "CurrentCoordinate": {"X": 1.2, "Y": 2.0, "Z": 2.4}
                },
                "CoordinateDelta": {
                    "DeltaX": 0.1,
                    "DeltaY": 0.0,
                    "DeltaZ": -0.3,
                    "PlanarDistance": 0.316,
                    "SpatialDistance": 0.316,
                },
            }
            with patch.object(
                runner,
                "_run_gated_wrapper",
                side_effect=[dry_1, live_1, dry_2, live_2],
            ) as wrapper:
                summary = runner._run_live_input_series()

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["requestedPulseCount"], 2)
            self.assertEqual(summary["completedPulseCount"], 2)
            self.assertTrue(summary["movementSent"])
            self.assertEqual(len(summary["seriesPulses"]), 2)
            self.assertAlmostEqual(summary["seriesCoordinateDelta"]["deltaX"], 0.2)
            self.assertAlmostEqual(summary["seriesCoordinateDelta"]["deltaZ"], -0.6)
            for call in wrapper.call_args_list:
                self.assertEqual(call.kwargs["pulse_count"], 1)

    def test_series_stops_partial_after_prior_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ForwardSeries2x250",
                profile={
                    "mode": "live-input-series",
                    "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 2},
                    "outputRoot": str(root / "captures"),
                    "maxAutoRefreshAttempts": 0,
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            dry_1 = {"Status": "dry-run-valid", "SummaryFile": "dry-1.json"}
            live_1 = {
                "Status": "passed",
                "SummaryFile": "live-1.json",
                "MovementSent": True,
                "MovementAttempted": True,
                "Preflight": {
                    "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0}
                },
                "PostReadback": {
                    "CurrentCoordinate": {"X": 1.1, "Y": 2.0, "Z": 2.7}
                },
            }
            dry_2 = {
                "Status": "blocked-preflight-age-budget",
                "SummaryFile": "dry-2.json",
                "Issues": ["proof_anchor_remaining_age_budget_too_low:remaining=3"],
            }
            with patch.object(
                runner,
                "_run_gated_wrapper",
                side_effect=[dry_1, live_1, dry_2],
            ):
                summary = runner._run_live_input_series()

            self.assertEqual(summary["status"], "partial-series-stopped")
            self.assertEqual(summary["completedPulseCount"], 1)
            self.assertTrue(summary["movementSent"])
            self.assertEqual(summary["seriesPulses"][1]["stage"], "dry-run")
            self.assertIn("proof_anchor_remaining_age_budget_too_low", summary["issues"][0])


if __name__ == "__main__":
    unittest.main()
