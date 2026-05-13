from __future__ import annotations

import re
import unittest

import scan_current_pid_coordinate_family as scan


class ScanCurrentPidCoordinateFamilyTests(unittest.TestCase):
    def test_utc_stamp_includes_microseconds_for_fast_batch_runs(self) -> None:
        stamp = scan.utc_stamp()
        self.assertRegex(stamp, re.compile(r"^\d{8}-\d{6}-\d{6}$"))


if __name__ == "__main__":
    unittest.main()
