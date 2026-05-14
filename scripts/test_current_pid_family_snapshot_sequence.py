#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import current_pid_family_snapshot_sequence as sequence


def write_current_truth(path: Path, *, pid: int = 79184, hwnd: str = "0xA90BFC", address: str = "0x268D5A80730") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "riftreader-current-truth",
                "target": {
                    "processName": "rift_x64",
                    "processId": pid,
                    "targetWindowHandle": hwnd,
                    "processStartUtc": "2026-05-13T00:43:12.080812Z",
                    "moduleBase": "0x7FF796B50000",
                },
                "bestCurrentCandidate": {
                    "candidateId": "family-snapshot-hit-000004",
                    "addressHex": address,
                    "candidateFile": "scripts/captures/coordinate-family-snapshot-currentpid-79184/family-import-candidates.json",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def args(**overrides) -> argparse.Namespace:
    values = {
        "pid": None,
        "hwnd": None,
        "expected_start_time_utc": None,
        "expected_module_base": None,
        "current_truth_json": None,
        "disable_current_truth": False,
        "self_test": False,
        "top_count": 1,
        "max_total_ranges": 4,
        "max_prior_ranges": 3,
        "disable_default_priors": True,
        "prior_address": ["lead=0x200123"],
        "prior_family": [],
        "prior_radius": 0x2000,
        "prior_family_span": 0x10000,
        "prior_family_step": 0x10000,
        "prior_neighbor_family_count": 1,
        "prior_alignment": 0x1000,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class CurrentPidFamilySnapshotSequenceTests(unittest.TestCase):
    def test_prior_ranges_are_selected_before_generic_scan_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            scan_plan = Path(temp) / "scan-plan.json"
            scan_plan.write_text(
                json.dumps(
                    {
                        "ranges": [
                            {
                                "rank": 1,
                                "minAddressHex": "0x900000",
                                "maxAddressHex": "0xA00000",
                                "spanMiB": 1.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            selected, strategy = sequence.select_adaptive_scan_ranges(scan_plan, args())

            self.assertGreater(strategy["priorRangeCount"], 0)
            self.assertEqual(selected[0]["source"], "prior-exact-window")
            self.assertTrue(any(item["source"] == "current-pid-scan-plan" for item in selected))
            self.assertLess(
                selected.index(next(item for item in selected if item["source"] == "prior-exact-window")),
                selected.index(next(item for item in selected if item["source"] == "current-pid-scan-plan")),
            )

    def test_documented_default_priors_exist_when_not_disabled(self) -> None:
        ranges = sequence.build_prior_ranges(args(disable_default_priors=False, prior_address=[], max_prior_ranges=24))

        labels = {item["label"].split(":")[0] for item in ranges}
        self.assertIn("pid2928-best-focused-offset-copy-candidate", labels)
        self.assertIn("pid2928-offset-copy-family-base", labels)
        self.assertIn("pid60628-destination-copy-family", labels)
        self.assertIn("pid60628-best-moving-slot-family", labels)

    def test_operator_prior_outranks_documented_historical_priors(self) -> None:
        ranges = sequence.build_prior_ranges(
            args(
                disable_default_priors=False,
                prior_address=["currentTruth=0x268D5A80730"],
                max_prior_ranges=4,
            )
        )

        self.assertEqual(ranges[0]["label"], "currentTruth")
        self.assertEqual(ranges[0]["source"], "prior-exact-window")
        self.assertLess(ranges[0]["priority"], 10)
        self.assertTrue(any("currentTruth" in item["label"] for item in ranges))

    def test_current_truth_context_fills_target_and_candidate_prior(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            truth = write_current_truth(temp_path / "docs" / "recovery" / "current-truth.json")
            parsed = args(current_truth_json=truth, prior_address=[])

            context = sequence.apply_current_truth_context(parsed, temp_path)

            self.assertTrue(context["loaded"])
            self.assertEqual(parsed.pid, 79184)
            self.assertEqual(parsed.hwnd, "0xA90BFC")
            self.assertEqual(parsed.expected_start_time_utc, "2026-05-13T00:43:12.080812Z")
            self.assertEqual(parsed.expected_module_base, "0x7FF796B50000")
            self.assertIn("currentTruth=0x268D5A80730", parsed.prior_address)
            self.assertEqual(context["targetDefaultsApplied"], ["pid", "hwnd", "expected-start-time-utc", "expected-module-base"])
            self.assertFalse(context["blockers"])

    def test_current_truth_context_blocks_explicit_target_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            truth = write_current_truth(temp_path / "docs" / "recovery" / "current-truth.json")
            parsed = args(current_truth_json=truth, pid=12345, hwnd="0xA90BFC", prior_address=[])

            context = sequence.apply_current_truth_context(parsed, temp_path)

            self.assertIn("current-truth-target-pid-mismatch:12345!=79184", context["blockers"])
            self.assertIn("currentTruth=0x268D5A80730", parsed.prior_address)

    def test_plan_only_can_bootstrap_from_current_truth_without_manual_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            write_current_truth(temp_path / "docs" / "recovery" / "current-truth.json")
            scan_plan = (
                temp_path
                / "scripts"
                / "captures"
                / "memory-region-inventory-currentpid-79184-test"
                / "scan-plan.json"
            )
            scan_plan.parent.mkdir(parents=True, exist_ok=True)
            scan_plan.write_text(
                json.dumps(
                    {
                        "ranges": [
                            {
                                "rank": 1,
                                "minAddressHex": "0x900000",
                                "maxAddressHex": "0xA00000",
                                "spanMiB": 1.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out = temp_path / "sequence"

            original_argv = None
            import sys

            original_argv = sys.argv
            try:
                sys.argv = [
                    "current_pid_family_snapshot_sequence.py",
                    "--repo-root",
                    str(temp_path),
                    "--output-root",
                    str(out),
                    "--plan-only",
                    "--disable-default-priors",
                    "--max-prior-ranges",
                    "1",
                    "--json",
                ]
                with redirect_stdout(StringIO()):
                    code = sequence.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["processId"], 79184)
            self.assertEqual(summary["targetWindowHandle"], "0xA90BFC")
            self.assertTrue(summary["currentTruth"]["loaded"])
            self.assertEqual(manifest["scanRanges"][0]["label"], "currentTruth")

    def test_auto_displacement_uses_exact_hwnd_window_message_backend(self) -> None:
        captured = {}

        def fake_run_command(command, cwd, timeout_seconds):  # noqa: ANN001
            captured["command"] = command
            captured["timeout_seconds"] = timeout_seconds
            return {"exitCode": 0, "timedOut": False, "stdout": "ok", "stderr": ""}

        original = sequence.run_command
        try:
            sequence.run_command = fake_run_command
            ok, envelope = sequence.run_auto_displacement(
                Path("C:/repo"),
                args(
                    pid=1234,
                    hwnd="0xABC",
                    auto_displacement_key="w",
                    auto_displacement_hold_ms=750,
                    auto_displacement_timeout_seconds=9,
                ),
            )
        finally:
            sequence.run_command = original

        self.assertTrue(ok)
        self.assertEqual(envelope["exitCode"], 0)
        command = captured["command"]
        self.assertIn("post-rift-key.ps1", " ".join(command))
        self.assertIn("-TargetProcessId", command)
        self.assertIn("1234", command)
        self.assertIn("-TargetWindowHandle", command)
        self.assertIn("0xABC", command)
        self.assertIn("-SkipBackgroundFocus", command)
        self.assertIn("-UseWindowMessage", command)

    def test_rrapicoord_reference_uses_robust_capture_helper(self) -> None:
        captured = {}
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            reference = temp_path / "rift-api-reference-currentpid-1234.json"
            reference.write_text(
                json.dumps(
                    {
                        "source": "rrapicoord1-memory-scan",
                        "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0, "capturedAtUtc": "2026-05-13T01:00:00Z"},
                        "processId": 1234,
                        "targetWindowHandle": "0xABC",
                    }
                ),
                encoding="utf-8",
            )

            def fake_run_command(command, cwd, timeout_seconds):  # noqa: ANN001
                captured["command"] = command
                captured["timeout_seconds"] = timeout_seconds
                return {
                    "exitCode": 0,
                    "timedOut": False,
                    "stdout": json.dumps({"Status": "captured", "ReferenceFile": str(reference)}),
                    "stderr": "",
                }

            original = sequence.run_command
            try:
                sequence.run_command = fake_run_command
                loaded, reference_path, envelope = sequence.capture_rrapicoord_reference(
                    Path("C:/repo"),
                    args(
                        pid=1234,
                        hwnd="0xABC",
                        reference_scan_context_bytes=4096,
                        reference_max_hits=512,
                        reference_scan_attempts=5,
                        reference_scan_retry_delay_milliseconds=1500,
                        reference_tolerance=0.25,
                        reference_timeout_seconds=45,
                    ),
                    temp_path,
                )
            finally:
                sequence.run_command = original

            self.assertEqual(reference_path, reference.resolve())
            self.assertEqual(loaded["source"], "rrapicoord1-memory-scan")
            self.assertEqual(envelope["exitCode"], 0)
            command = captured["command"]
            self.assertIn("capture-rift-api-reference-coordinate.ps1", " ".join(command))
            self.assertIn("-ProcessId", command)
            self.assertIn("1234", command)
            self.assertIn("-TargetWindowHandle", command)
            self.assertIn("0xABC", command)
            self.assertIn("-ScanContextBytes", command)
            self.assertIn("4096", command)
            self.assertIn("-MaxHits", command)
            self.assertIn("512", command)
            self.assertIn("-ScanAttempts", command)
            self.assertIn("5", command)
            self.assertIn("-ScanRetryDelayMilliseconds", command)
            self.assertIn("1500", command)
            self.assertIn("-Json", command)

    def test_rrapicoord_reference_failure_preserves_command_envelope(self) -> None:
        captured = {}

        def fake_run_command(command, cwd, timeout_seconds):  # noqa: ANN001
            captured["command"] = command
            return {
                "args": command,
                "cwd": str(cwd),
                "exitCode": None,
                "timedOut": True,
                "stdout": "",
                "stderr": "",
            }

        original = sequence.run_command
        try:
            sequence.run_command = fake_run_command
            with self.assertRaises(sequence.CommandEnvelopeError) as context:
                sequence.capture_rrapicoord_reference(
                    Path("C:/repo"),
                    args(
                        pid=1234,
                        hwnd="0xABC",
                        reference_scan_context_bytes=4096,
                        reference_max_hits=512,
                        reference_scan_attempts=5,
                        reference_scan_retry_delay_milliseconds=1500,
                        reference_tolerance=0.25,
                        reference_timeout_seconds=45,
                    ),
                    Path("C:/out"),
                )
        finally:
            sequence.run_command = original

        self.assertIn("reference_capture_failed: source=rrapicoord", str(context.exception))
        self.assertTrue(context.exception.envelope["timedOut"])
        self.assertEqual(context.exception.envelope["args"], captured["command"])
        compact = sequence.compact_envelope(context.exception.envelope, "reference:baseline")
        self.assertEqual(compact["stage"], "reference:baseline")
        self.assertIn("capture-rift-api-reference-coordinate.ps1", " ".join(compact["args"]))


if __name__ == "__main__":
    unittest.main()
