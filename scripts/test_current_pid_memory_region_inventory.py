#!/usr/bin/env python3

from __future__ import annotations

import unittest

import current_pid_memory_region_inventory as inv


class MemoryRegionInventoryTests(unittest.TestCase):
    def test_heap_private_readwrite_scores_above_image_execute_read(self) -> None:
        heap = inv.normalize_region(
            {
                "base": 0x268FF472000,
                "size": 0x200000,
                "allocationBase": 0x268FF000000,
                "allocationProtect": inv.PAGE_READWRITE,
                "state": inv.MEM_COMMIT,
                "protect": inv.PAGE_READWRITE,
                "type": inv.MEM_PRIVATE,
            }
        )
        image = inv.normalize_region(
            {
                "base": 0x7FF71CD90000,
                "size": 0x800000,
                "allocationBase": 0x7FF71CD90000,
                "allocationProtect": inv.PAGE_EXECUTE_READ,
                "state": inv.MEM_COMMIT,
                "protect": inv.PAGE_EXECUTE_READ,
                "type": inv.MEM_IMAGE,
            }
        )

        self.assertGreater(heap["plannerScore"], image["plannerScore"])
        self.assertTrue(heap["readableCommitted"])

    def test_merge_regions_groups_same_allocation_neighbors(self) -> None:
        regions = [
            inv.normalize_region(
                {
                    "base": 0x268FF472000,
                    "size": 0x10000,
                    "allocationBase": 0x268FF000000,
                    "allocationProtect": inv.PAGE_READWRITE,
                    "state": inv.MEM_COMMIT,
                    "protect": inv.PAGE_READWRITE,
                    "type": inv.MEM_PRIVATE,
                }
            ),
            inv.normalize_region(
                {
                    "base": 0x268FF482000,
                    "size": 0x10000,
                    "allocationBase": 0x268FF000000,
                    "allocationProtect": inv.PAGE_READWRITE,
                    "state": inv.MEM_COMMIT,
                    "protect": inv.PAGE_READWRITE,
                    "type": inv.MEM_PRIVATE,
                }
            ),
        ]

        groups = inv.merge_regions_for_scan(regions, max_gap=0)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["allocationBaseHex"], "0x268FF000000")
        self.assertEqual(groups[0]["minAddressHex"], "0x268FF472000")
        self.assertEqual(groups[0]["maxAddressHex"], "0x268FF492000")
        self.assertEqual(groups[0]["regionCount"], 2)


if __name__ == "__main__":
    unittest.main()
