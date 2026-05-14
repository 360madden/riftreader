from __future__ import annotations

import tempfile
import os
import unittest
from pathlib import Path

from rift_live_test.coordinate_proof_preflight import (
    command_failed,
    json_from_stdout,
    latest_file,
    preview_text,
)


class CoordinateProofPreflightTests(unittest.TestCase):
    def test_json_from_stdout_reads_plain_or_embedded_json(self) -> None:
        self.assertEqual(json_from_stdout('{"status":"passed"}'), {"status": "passed"})
        self.assertEqual(json_from_stdout('noise\n{"status":"blocked","x":1}\n'), {"status": "blocked", "x": 1})
        self.assertIsNone(json_from_stdout("not-json"))

    def test_command_failed_reports_failed_only(self) -> None:
        failures = command_failed(
            [
                {"name": "a", "status": "completed", "exitCode": 0},
                {"name": "b", "status": "blocked", "exitCode": 2},
                {"name": "c", "status": "failed", "exitCode": 1},
            ]
        )

        self.assertEqual(failures, ["command-failed:c:exit=1"])

    def test_latest_file_can_filter_by_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old.json"
            new = root / "new.json"
            old.write_text("{}", encoding="utf-8")
            new.write_text("{}", encoding="utf-8")
            os.utime(old, (1000.0, 1000.0))
            os.utime(new, (2000.0, 2000.0))
            cutoff = 1500.0

            self.assertEqual(latest_file([old, new]), new)
            self.assertEqual(latest_file([old, new], min_mtime=cutoff), new)

    def test_preview_text_truncates_long_output(self) -> None:
        preview = preview_text("a" * 20, limit=5)

        self.assertTrue(preview.startswith("aaaaa"))
        self.assertIn("truncated", preview)


if __name__ == "__main__":
    unittest.main()
