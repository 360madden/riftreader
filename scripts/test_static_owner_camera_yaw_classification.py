from __future__ import annotations

import contextlib
import io
import json
import unittest

import static_owner_camera_yaw_classification as classifier


class StaticOwnerCameraYawClassificationTests(unittest.TestCase):
    def test_self_test_cli_passes_without_live_input(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = classifier.main(["--self-test", "--json"])

        payload = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", payload["status"])
        self.assertFalse(payload["safety"]["inputSent"])
        self.assertFalse(payload["safety"]["movementSent"])
        self.assertFalse(payload["safety"]["targetMemoryBytesRead"])
        self.assertFalse(payload["safety"]["targetMemoryBytesWritten"])

    def test_focus_offset_deltas_reports_candidate_offsets(self) -> None:
        before = {
            "floatSamples": [
                {"offset": "0x304", "value": 1.0},
                {"offset": "0x30C", "value": 10.0},
            ]
        }
        after = {
            "floatSamples": [
                {"offset": "0x304", "value": 1.25},
                {"offset": "0x30C", "value": 8.5},
            ]
        }

        rows = classifier.focus_offset_deltas(before, after)
        by_offset = {row["offset"]: row for row in rows}

        self.assertEqual(0.25, by_offset["0x304"]["delta"])
        self.assertEqual(-1.5, by_offset["0x30C"]["delta"])

    def test_signed_angle_delta_wraps(self) -> None:
        self.assertEqual(20.0, classifier.signed_angle_delta(350.0, 10.0))
        self.assertEqual(-20.0, classifier.signed_angle_delta(10.0, 350.0))


if __name__ == "__main__":
    unittest.main()
