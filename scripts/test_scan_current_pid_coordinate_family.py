from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import scan_current_pid_coordinate_family as scan


class ScanCurrentPidCoordinateFamilyTests(unittest.TestCase):
    def test_utc_stamp_includes_microseconds_for_fast_batch_runs(self) -> None:
        stamp = scan.utc_stamp()
        self.assertRegex(stamp, re.compile(r"^\d{8}-\d{6}-\d{6}$"))

    def test_load_json_file_accepts_utf8_bom_reference_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "reference.json"
            path.write_text('\ufeff{"coordinate":{"x":1,"y":2,"z":3}}', encoding="utf-8")

            payload = scan.load_json_file(path)

        self.assertEqual(payload["coordinate"], {"x": 1, "y": 2, "z": 3})

    def test_process_start_matches_normalizes_seven_digit_fraction_and_offsets(self) -> None:
        self.assertTrue(
            scan.process_start_matches(
                "2026-06-30T12:49:06.803203+00:00",
                "2026-06-30T08:49:06.8032030-04:00",
            )
        )
        self.assertFalse(
            scan.process_start_matches(
                "2026-06-30T12:49:06.803203+00:00",
                "2026-06-30T12:50:06.803203+00:00",
            )
        )


if __name__ == "__main__":
    unittest.main()
