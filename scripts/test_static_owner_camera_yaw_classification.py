from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

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

    def test_aggregate_summary_cli_is_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            summary_a = temp / "right-summary.json"
            summary_b = temp / "left-summary.json"
            base_payload = {
                "kind": "static-owner-camera-yaw-classification",
                "status": "passed",
                "verdict": "visual-changed-static-yaw-unchanged",
                "generatedAtUtc": "2026-05-31T17:44:22Z",
                "visualEvidence": {"rawDiff": {"status": "changed", "changedPercent": 74.0}},
                "analysis": {
                    "classification": "visual-changed-static-yaw-unchanged",
                    "visualChanged": True,
                    "staticYawChanged": False,
                    "actionableForRouteControl": False,
                    "signedYawDeltaDegrees": 0.0,
                    "absoluteYawDeltaDegrees": 0.0,
                    "changedFocusOffsets": [{"offset": "0x300", "delta": 58.0, "absDelta": 58.0}],
                },
                "safety": {"inputSent": True, "movementSent": True, "targetMemoryBytesRead": True, "targetMemoryBytesWritten": False},
            }
            payload_a = {**base_payload, "stimulus": {"type": "mouse-look", "direction": "right", "pixels": 120, "approved": True}}
            payload_b = {**base_payload, "stimulus": {"type": "mouse-look", "direction": "left", "pixels": 120, "approved": True}}
            summary_a.write_text(json.dumps(payload_a), encoding="utf-8")
            summary_b.write_text(json.dumps(payload_b), encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = classifier.main(
                    [
                        "--output-root",
                        str(temp / "out"),
                        "--aggregate-summary-json",
                        str(summary_a),
                        str(summary_b),
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())

            self.assertEqual(0, exit_code)
            self.assertEqual("passed", payload["status"])
            self.assertEqual("visual-changed-static-yaw-unchanged-across-poses", payload["verdict"])
            self.assertEqual(2, payload["sourceCount"])
            self.assertEqual(0, payload["routeActionablePoseCount"])
            self.assertEqual(1, payload["changedOffsetCount"])
            self.assertFalse(payload["safety"]["inputSent"])
            self.assertFalse(payload["safety"]["movementSent"])
            self.assertFalse(payload["safety"]["targetMemoryBytesRead"])
            self.assertTrue(payload["sourceSafety"]["inputSent"])
            self.assertTrue(Path(payload["summaryJson"]).is_file())
            self.assertTrue(Path(payload["summaryMarkdown"]).is_file())


if __name__ == "__main__":
    unittest.main()
