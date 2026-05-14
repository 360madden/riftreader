#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

import current_pid_family_snapshot_sequence as sequence


def args(**overrides) -> argparse.Namespace:
    values = {
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
