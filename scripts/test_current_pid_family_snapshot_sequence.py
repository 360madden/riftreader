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


if __name__ == "__main__":
    unittest.main()
