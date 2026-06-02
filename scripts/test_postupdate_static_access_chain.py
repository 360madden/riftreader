from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import postupdate_static_access_chain as helper  # noqa: E402


class PostUpdateStaticAccessChainTests(unittest.TestCase):
    def test_direct_call_target_rva_decodes_rel32_destination(self) -> None:
        self.assertEqual(helper.direct_call_target_rva(0x1000, 0x20), 0x1025)
        self.assertEqual(helper.direct_call_target_rva(0x1000, -0x25), 0xFE0)

    def test_function_start_heuristic_uses_previous_int3_padding(self) -> None:
        section = helper.SectionBlob(
            name=".text",
            rva=0x1000,
            data=b"\x90\xC3" + (b"\xCC" * 8) + b"\x55\x48\x89\xE5\xE8\x00\x00\x00\x00",
            executable=True,
        )

        start = helper.find_function_start_by_int3(section, 0x1000 + 14)

        self.assertEqual(start, 0x1000 + 10)

    def test_unique_breadcrumb_function_rvas_keeps_targets_and_callers(self) -> None:
        breadcrumbs = [
            {
                "targetRva": "0x3F8B0",
                "directCallSites": [{"containingFunctionStartRva": "0x39CD0"}],
            },
            {
                "targetRva": "0x39CD0",
                "directCallSites": [{"containingFunctionStartRva": "0x13D2D80"}],
            },
        ]

        values = helper.unique_breadcrumb_function_rvas(breadcrumbs, limit=8)

        self.assertEqual(values, [0x3F8B0, 0x39CD0, 0x13D2D80])

    def test_root_sample_classifier_detects_position_candidate(self) -> None:
        module_base = 0x700000000000
        data = bytearray(helper.DEFAULT_ROOT_SAMPLE_BYTES)
        data[0:8] = (module_base + 0x1234).to_bytes(8, "little")
        struct.pack_into("<fff", data, 0x320, 100.0, 200.0, 300.0)

        result = helper.classify_root_sample(
            root_rva=0x335F508,
            root_pointer=0x20000000,
            data=bytes(data),
            module_base=module_base,
            module_size=0x500000,
            reference={"x": 100.0, "y": 200.0, "z": 300.0},
            tolerance=0.25,
        )

        self.assertEqual(result["classification"], "candidate-position-root-needs-proof")
        self.assertFalse(result["promotionEligible"])

    def test_root_sample_classifier_detects_orientation_not_position(self) -> None:
        module_base = 0x700000000000
        data = bytearray(helper.DEFAULT_ROOT_SAMPLE_BYTES)
        data[0:8] = (module_base + 0x1234).to_bytes(8, "little")
        struct.pack_into("<fff", data, 0x300, 0.0, 0.0, 1.0)
        struct.pack_into("<fff", data, 0x320, 0.95, -0.28, 0.01)

        result = helper.classify_root_sample(
            root_rva=0x335F508,
            root_pointer=0x20000000,
            data=bytes(data),
            module_base=module_base,
            module_size=0x500000,
            reference={"x": 7256.0, "y": 821.0, "z": 2990.0},
            tolerance=1.0,
        )

        self.assertEqual(result["classification"], "orientation-matrix-root-not-position-root")
        self.assertIn("unit-or-matrix-vector-at-promoted-coordinate-offset", result["reasons"])

    def test_self_test_passes(self) -> None:
        self.assertEqual(helper.self_test()["status"], "passed")


if __name__ == "__main__":
    unittest.main()
