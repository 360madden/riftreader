from __future__ import annotations

import unittest

from rift_live_test.pointer_family_scan import module_for_address, parse_targets, rank_summaries, summarize_scan


class PointerFamilyScanTests(unittest.TestCase):
    def test_parse_targets_dedupes_and_labels(self) -> None:
        targets = parse_targets(["0x10:first", "16:duplicate", "0x20"])

        self.assertEqual(
            targets,
            [
                {"address": 0x10, "addressHex": "0x10", "label": "first"},
                {"address": 0x20, "addressHex": "0x20", "label": "0x20"},
            ],
        )

    def test_module_for_address_uses_module_range(self) -> None:
        modules = [{"ModuleName": "rift_x64.exe", "BaseAddress": 0x1000, "BaseAddressHex": "0x1000", "ModuleMemorySize": 0x200}]

        self.assertEqual(module_for_address(0x10FF, modules)["ModuleName"], "rift_x64.exe")
        self.assertIsNone(module_for_address(0x1200, modules))

    def test_summarize_scan_counts_module_hits(self) -> None:
        scan = {
            "PointerTarget": "0x2000",
            "targetLabel": "seed",
            "HitCount": 2,
            "scanElapsedSeconds": 1.25,
            "artifactPath": "scan.json",
            "Hits": [
                {"Address": 0x1010, "AddressHex": "0x1010", "RegionBaseHex": "0x1000", "Context": {"AsciiPreview": "a"}},
                {"Address": 0x3000, "AddressHex": "0x3000", "RegionBaseHex": "0x3000", "Context": {"AsciiPreview": "b"}},
            ],
        }
        modules = [{"ModuleName": "rift_x64.exe", "BaseAddress": 0x1000, "BaseAddressHex": "0x1000", "ModuleMemorySize": 0x100}]

        summary = summarize_scan(scan, modules=modules, depth=0)

        self.assertEqual(summary["target"], "0x2000")
        self.assertEqual(summary["hitCount"], 2)
        self.assertEqual(summary["moduleHitCount"], 1)
        self.assertEqual(summary["riftModuleHitCount"], 1)
        self.assertFalse(summary["promotionEligible"])

    def test_rank_summaries_prefers_rift_module_hits_then_hit_count(self) -> None:
        ranked = rank_summaries(
            [
                {"target": "0x1", "hitCount": 20, "moduleHitCount": 0, "riftModuleHitCount": 0, "depth": 0},
                {"target": "0x2", "hitCount": 1, "moduleHitCount": 1, "riftModuleHitCount": 1, "depth": 1},
            ]
        )

        self.assertEqual(ranked[0]["target"], "0x2")


if __name__ == "__main__":
    unittest.main()
