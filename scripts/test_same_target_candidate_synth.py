from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.same_target_candidate_synth import build_summary


class SameTargetCandidateSynthTests(unittest.TestCase):
    def test_build_summary_synthesizes_importable_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            readback = Path(temp) / "readback.json"
            readback.write_text(
                json.dumps(
                    {
                        "processId": 2928,
                        "targetWindowHandle": "0xC0994",
                        "candidateFile": "source.jsonl",
                        "readbacks": [
                            {
                                "rank": 2,
                                "candidateId": "snapshot-delta-2000-xyz",
                                "addressHex": "0x2000",
                                "status": "read",
                                "memoryValue": {"x": 11.0, "y": 12.0, "z": 13.0},
                                "averageOffset": {"x": -1.0, "y": -2.0, "z": -3.0},
                                "offsetCorrectedValue": {"x": 10.0, "y": 10.0, "z": 10.0},
                                "directMaxAbsDelta": 3.0,
                                "offsetCorrectedMaxAbsDelta": 0.01,
                                "directWithinTolerance": False,
                                "offsetCorrectedWithinTolerance": True,
                                "snapshotOffsetCount": 2,
                            },
                            {
                                "rank": 1,
                                "candidateId": "snapshot-delta-1000-xyz",
                                "addressHex": "0x1000",
                                "status": "read",
                                "memoryValue": {"x": 1.0, "y": 2.0, "z": 3.0},
                                "directMaxAbsDelta": 0.2,
                                "offsetCorrectedMaxAbsDelta": 0.2,
                                "directWithinTolerance": True,
                                "offsetCorrectedWithinTolerance": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            summary = build_summary(
                readback_summary_path=readback,
                process_id=2928,
                target_window_handle="0xC0994",
                process_name="rift_x64",
                max_candidates=10,
            )

            self.assertEqual(summary["status"], "passed")
            packet = summary["candidatePacket"]
            self.assertEqual(packet["processId"], 2928)
            self.assertEqual(packet["targetWindowHandle"], "0xC0994")
            self.assertEqual(packet["candidate_count"], 2)
            self.assertEqual(packet["candidates"][0]["candidate_id"], "same-target-2000-xyz")
            self.assertEqual(packet["candidates"][0]["source_base_address_hex"], "0x2000")
            self.assertEqual(packet["candidates"][0]["source_offset_hex"], "0x0")
            self.assertEqual(packet["candidates"][0]["axis_order"], "xyz")
            self.assertFalse(packet["candidates"][0]["direct_within_tolerance"])

    def test_target_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            readback = Path(temp) / "readback.json"
            readback.write_text(
                json.dumps(
                    {
                        "processId": 111,
                        "targetWindowHandle": "0xBAD",
                        "readbacks": [],
                    }
                ),
                encoding="utf-8",
            )

            summary = build_summary(
                readback_summary_path=readback,
                process_id=2928,
                target_window_handle="0xC0994",
                process_name="rift_x64",
                max_candidates=10,
            )

            self.assertEqual(summary["status"], "blocked")
            self.assertIn("readback-pid-mismatch:actual=111;expected=2928", summary["blockers"])
            self.assertIn("readback-hwnd-mismatch:actual=0xBAD;expected=0xC0994", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
