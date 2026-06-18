from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import current_pid_candidate_readback as helper


class CurrentPidCandidateReadbackTests(unittest.TestCase):
    def test_load_reference_file_accepts_utf8_bom_coordinate_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "reference.json"
            path.write_text('\ufeff{"coordinate":{"x":7262.47,"y":821.38,"z":2996.16}}', encoding="utf-8")

            reference = helper.load_reference_file(path)

        self.assertEqual(reference["coordinate"], {"x": 7262.47, "y": 821.38, "z": 2996.16})
        self.assertEqual(reference["referenceFile"], str(path.resolve()))


if __name__ == "__main__":
    unittest.main()
