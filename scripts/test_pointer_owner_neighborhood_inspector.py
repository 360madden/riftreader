from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.pointer_owner_neighborhood_inspector import (
    analyze_qwords,
    main,
    synthetic_memory,
    synthetic_targets,
)


class PointerOwnerNeighborhoodInspectorTests(unittest.TestCase):
    def test_analyze_qwords_finds_exact_and_window_matches(self) -> None:
        base, owner, data = synthetic_memory()

        analysis = analyze_qwords(
            data=data,
            base_address=base,
            owner_address=owner,
            targets=synthetic_targets(),
            target_window_base=0x5000,
            target_window_size=0x1000,
            near_target_bytes=0x80,
            module_base=None,
            module_size=0,
            module_name="rift_x64.exe",
            include_module_pointers=False,
            owner_window_bytes=0x40,
            stride=8,
            max_matches=16,
        )

        self.assertEqual(analysis["exactTargetCounts"]["0x5000"], 1)
        self.assertEqual(analysis["exactTargetCounts"]["0x5010"], 1)
        self.assertEqual(analysis["exactTargetCounts"]["0x56F0"], 1)
        self.assertGreaterEqual(analysis["regionMatchCount"], 4)
        self.assertTrue(any(match["address"] == "0x4100" for match in analysis["regionMatches"]))

    def test_owner_window_keeps_offsets_relative_to_owner(self) -> None:
        base, owner, data = synthetic_memory()

        analysis = analyze_qwords(
            data=data,
            base_address=base,
            owner_address=owner,
            targets=synthetic_targets(),
            target_window_base=0x5000,
            target_window_size=0x1000,
            near_target_bytes=0x80,
            module_base=None,
            module_size=0,
            module_name="rift_x64.exe",
            include_module_pointers=False,
            owner_window_bytes=0x20,
            stride=8,
            max_matches=16,
        )

        owner_entry = next(match for match in analysis["ownerWindow"] if match["address"] == "0x4100")
        self.assertEqual(owner_entry["offsetFromOwner"], "0x0")
        self.assertEqual(owner_entry["value"], "0x5000")
        self.assertEqual(owner_entry["classification"]["exactTarget"]["label"], "d20-base")

    def test_analyze_qwords_can_report_module_pointer_hints(self) -> None:
        base = 0x4000
        owner = 0x4100
        data = bytearray(0x140)
        struct_value_offset = owner - base - 0x10
        data[struct_value_offset : struct_value_offset + 8] = (0x700020).to_bytes(8, "little")

        analysis = analyze_qwords(
            data=bytes(data),
            base_address=base,
            owner_address=owner,
            targets=synthetic_targets(),
            target_window_base=0x5000,
            target_window_size=0x1000,
            near_target_bytes=0x80,
            module_base=0x700000,
            module_size=0x1000,
            module_name="rift_x64.exe",
            include_module_pointers=True,
            owner_window_bytes=0x20,
            stride=8,
            max_matches=16,
        )

        self.assertEqual(analysis["ownerWindowModulePointerCount"], 1)
        self.assertEqual(analysis["ownerWindowModulePointers"][0]["classification"]["modulePointer"]["rva"], "0x20")

    def test_self_test_writes_summary_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "owner-inspect"
            with redirect_stdout(StringIO()):
                code = main(["--self-test", "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertGreaterEqual(summary["analysis"]["regionMatchCount"], 4)
            self.assertFalse(summary["safety"]["x64dbgLaunched"])
            self.assertFalse(summary["safety"]["inputSent"])
            self.assertFalse(summary["safety"]["targetMemoryBytesRead"])


if __name__ == "__main__":
    unittest.main()
