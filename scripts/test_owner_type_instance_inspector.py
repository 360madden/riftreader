from __future__ import annotations

import struct
import unittest

from rift_live_test.owner_type_instance_inspector import extract_scan_hit_addresses, inspect_instance_bytes, unpack_vec3


class OwnerTypeInstanceInspectorTests(unittest.TestCase):
    def test_extract_scan_hit_addresses_dedupes_and_limits(self) -> None:
        scan = {
            "Hits": [
                {"AddressHex": "0x1000"},
                {"Address": 0x1000},
                {"AddressHex": "0x2000"},
            ]
        }

        self.assertEqual(extract_scan_hit_addresses(scan, max_instances=2), [0x1000, 0x2000])

    def test_inspect_instance_bytes_marks_candidate_coord_pointer(self) -> None:
        data = bytearray(0x40)
        struct.pack_into("<Q", data, 0x0, 0x7000)
        struct.pack_into("<Q", data, 0x8, 0x8000)
        struct.pack_into("<Q", data, 0x10, 0x5000)

        instance = inspect_instance_bytes(
            data=bytes(data),
            owner_base=0x4000,
            coord_pointer_offset=0x10,
            type_qword_offsets=[0x0, 0x8],
            candidate_addresses={0x5000: {"address": 0x5000, "addressHex": "0x5000", "label": "coord-candidate"}},
        )

        self.assertEqual(instance["ownerBase"], "0x4000")
        self.assertEqual(instance["coordPointerStorage"], "0x4010")
        self.assertEqual(instance["coordPointer"], "0x5000")
        self.assertTrue(instance["coordPointerIsCandidate"])
        self.assertEqual(instance["coordPointerCandidate"]["label"], "coord-candidate")

    def test_unpack_vec3_filters_bad_values(self) -> None:
        good = struct.pack("<fff", 1.0, 2.0, 3.0)
        bad = struct.pack("<fff", float("nan"), 2.0, 3.0)
        zero = struct.pack("<fff", 0.0, 0.0, 0.0)

        self.assertEqual(unpack_vec3(good), {"x": 1.0, "y": 2.0, "z": 3.0})
        self.assertIsNone(unpack_vec3(bad))
        self.assertIsNone(unpack_vec3(zero))


if __name__ == "__main__":
    unittest.main()
