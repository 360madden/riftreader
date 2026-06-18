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

    def test_collect_breadcrumb_global_rvas_keeps_constructor_then_breadcrumbs(self) -> None:
        constructor = {
            "functionRva": "0x3F8B0",
            "candidateGlobalRoots": [
                {
                    "globalRva": "0x335F508",
                    "rva": "0x3FCFD",
                    "instruction": "mov qword ptr [rip + 0x331f804], rdi",
                    "access": "write",
                }
            ],
        }
        function_summaries = [
            {
                "functionRva": "0xC38390",
                "ripRelativeAccesses": [
                    {
                        "globalRva": "0x271E1D0",
                        "rva": "0xC38391",
                        "instruction": "lea rax, [rip + 0x26de8f2]",
                        "access": "read",
                    },
                    {
                        "globalRva": "0x32DD7E8",
                        "rva": "0xC383AA",
                        "instruction": "mov rax, qword ptr [rip + 0x2699441]",
                        "access": "read",
                    }
                ],
            }
        ]

        rows = helper.collect_breadcrumb_global_rvas(constructor, function_summaries, max_globals=8)

        self.assertEqual([row["globalRva"] for row in rows], ["0x335F508", "0x32DD7E8"])
        self.assertEqual(rows[0]["source"], "constructor-candidate-global-root")
        self.assertEqual(rows[1]["source"], "breadcrumb-rip-relative-access")

    def test_global_container_classifier_surfaces_child_coordinate_lead(self) -> None:
        result = helper.classify_global_container_sample(
            global_rva=0x32DD7E8,
            global_value=0x1D4D0BFC020,
            data=b"\x00" * 128,
            module_base=0x7FF700000000,
            module_size=0x4000000,
            reference={"x": 7256.0, "y": 821.0, "z": 2990.0},
            coordinate_candidate=0x1D4BA11BE00,
            child_samples=[
                {
                    "parentOffset": "0x48",
                    "childPointer": "0x1D4BA11BE00",
                    "nearWorldTriples": [{"offset": "0x0"}],
                    "coordinatePointerHits": [],
                }
            ],
            tolerance=1.0,
        )

        self.assertEqual(result["classification"], "global-container-child-coordinate-lead")
        self.assertFalse(result["promotionEligible"])

    def test_target_from_artifacts_prefers_current_candidate_over_stale_static_target(self) -> None:
        static_readback = {
            "target": {
                "pid": 12664,
                "hwnd": "0x205146C",
                "moduleBase": "0x7FF6EE5D0000",
                "expectedProcessStartUtc": "2026-06-01T17:19:45.159353Z",
            }
        }
        candidate_readback = {
            "target": {
                "pid": 77152,
                "hwnd": "0x17A0DB2",
                "moduleBase": "0x7FF7211C0000",
                "expectedProcessStartUtc": "2026-06-02T15:45:29.2617327Z",
            }
        }

        target = helper.target_from_artifacts(static_readback, candidate_readback)

        self.assertEqual(target["pid"], 77152)
        self.assertEqual(target["hwnd"], "0x17A0DB2")
        self.assertEqual(target["moduleBase"], "0x7FF7211C0000")
        self.assertEqual(target["expectedProcessStartUtc"], "2026-06-02T15:45:29.2617327Z")

    def test_process_start_guard_accepts_same_instant_with_different_offsets(self) -> None:
        self.assertTrue(
            helper.rediscovery.process_start_matches(
                "2026-06-18T01:57:01.857121+00:00",
                "2026-06-17T21:57:01.8571209-04:00",
            )
        )

    def test_self_test_passes(self) -> None:
        self.assertEqual(helper.self_test()["status"], "passed")


if __name__ == "__main__":
    unittest.main()
