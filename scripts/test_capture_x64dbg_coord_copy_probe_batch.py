from __future__ import annotations

import unittest

from capture_x64dbg_coord_copy_probe_batch import extract_coord_copy_evidence


class CaptureX64DbgCoordCopyProbeBatchTests(unittest.TestCase):
    def test_extract_coord_copy_evidence_accepts_coord_copy_sized_source_triplet(self) -> None:
        summary = {
            "contexts": [
                {
                    "rip": "0x7FFC593F13EA",
                    "ripDisassembly": {"instruction": "vmovdqu ymmword ptr ds:[rcx+r9*1-0x60], ymm1"},
                    "keyRegisters": {
                        "rdx": "0x1FF6D600020",
                        "r8": "0x37",
                        "rbx": "0x37",
                        "rsi": "0x37",
                        "r12": "0x1FF075750F9",
                    },
                    "registerMemory": {
                        "rdx": {
                            "address": "0x1FF6D600020",
                            "floatTriplets": [
                                {
                                    "offset": 40,
                                    "offsetHex": "0x28",
                                    "x": 7406.6005859375,
                                    "y": 871.7725830078125,
                                    "z": 3028.814208984375,
                                }
                            ],
                        }
                    },
                }
            ]
        }

        evidence = extract_coord_copy_evidence(summary)

        self.assertTrue(evidence["isGoodHit"])
        self.assertEqual(evidence["reason"], "matched")
        self.assertEqual(evidence["sourceAddress"], "0x1FF6D600020")
        self.assertEqual(evidence["destinationBaseRegister"], "r12")

    def test_extract_coord_copy_evidence_rejects_non_coord_copy_size(self) -> None:
        summary = {
            "contexts": [
                {
                    "keyRegisters": {"rdx": "0x1FF6D600020", "r8": "0x4A", "r12": "0x1FF075750F9"},
                    "registerMemory": {
                        "rdx": {
                            "address": "0x1FF6D600020",
                            "floatTriplets": [
                                {
                                    "offset": 40,
                                    "offsetHex": "0x28",
                                    "x": 7406.6005859375,
                                    "y": 871.7725830078125,
                                    "z": 3028.814208984375,
                                }
                            ],
                        }
                    },
                }
            ]
        }

        evidence = extract_coord_copy_evidence(summary)

        self.assertFalse(evidence["isGoodHit"])
        self.assertEqual(evidence["reason"], "copy-size-mismatch")

    def test_extract_coord_copy_evidence_rejects_unplausible_source_triplet(self) -> None:
        summary = {
            "contexts": [
                {
                    "keyRegisters": {"rdx": "0x1FF6D600020", "r8": "0x37", "r12": "0x1FF075750F9"},
                    "registerMemory": {
                        "rdx": {
                            "address": "0x1FF6D600020",
                            "floatTriplets": [
                                {"offset": 40, "offsetHex": "0x28", "x": 72.0, "y": 0.0, "z": -0.006}
                            ],
                        }
                    },
                }
            ]
        }

        evidence = extract_coord_copy_evidence(summary)

        self.assertFalse(evidence["isGoodHit"])
        self.assertEqual(evidence["reason"], "source-triplet-not-plausible")


if __name__ == "__main__":
    unittest.main()
