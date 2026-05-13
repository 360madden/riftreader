from __future__ import annotations

import unittest

from rift_live_test.root_signature_family_classifier import (
    build_families,
    field_offsets,
    parent_region_clusters,
    pointer_class,
    region_hex,
    strong_parent_leads,
)


class RootSignatureFamilyClassifierTests(unittest.TestCase):
    def test_field_offsets_splits_matches_and_mismatches(self) -> None:
        candidate = {
            "fieldMatches": [
                {"offsetFromOwner": "0x0", "matched": True},
                {"offsetFromOwner": "0x110", "matched": False},
            ]
        }

        self.assertEqual(field_offsets(candidate, matched=True), ["0x0"])
        self.assertEqual(field_offsets(candidate, matched=False), ["0x110"])

    def test_pointer_class_identifies_known_heap_module_and_zero(self) -> None:
        self.assertEqual(pointer_class("0x2000", known=0x2000, module_base=0x700000000000), "known")
        self.assertEqual(pointer_class("0x268D0000000", known=None, module_base=0x700000000000), "heap-like")
        self.assertEqual(pointer_class("0x700000010000", known=None, module_base=0x700000000000), "module-or-static")
        self.assertEqual(pointer_class("0x0", known=None, module_base=0x700000000000), "zero")

    def test_region_hex_buckets_by_64k(self) -> None:
        self.assertEqual(region_hex("0x12345"), "0x10000")

    def test_build_families_groups_and_ranks(self) -> None:
        families = build_families(
            [
                {"hitAddress": "0x20", "score": 1, "kind": "a"},
                {"hitAddress": "0x10", "score": 20, "kind": "a"},
                {"hitAddress": "0x30", "score": 20, "kind": "b"},
            ],
            key_fn=lambda candidate: str(candidate.get("kind")),
            sample_limit=2,
        )

        self.assertEqual(families[0]["familyKey"], "a")
        self.assertEqual(families[0]["count"], 2)
        self.assertEqual(families[0]["topCandidate"]["hitAddress"], "0x10")

    def test_strong_parent_leads_excludes_known_parent(self) -> None:
        leads = strong_parent_leads(
            [
                {"parentSlot": "0x1000", "score": 160},
                {"parentSlot": "0x2000", "score": 15},
                {"parentSlot": "0x3000", "score": 0},
            ],
            known_parent_slot=0x1000,
            limit=10,
        )

        self.assertEqual([lead["parentSlot"] for lead in leads], ["0x2000"])

    def test_parent_region_clusters_groups_by_owner_pointer_region(self) -> None:
        clusters = parent_region_clusters(
            [
                {"parentSlot": "0x1", "ownerPointer": "0x268D1234567", "score": 1},
                {"parentSlot": "0x2", "ownerPointer": "0x268D1238888", "score": 2},
                {"parentSlot": "0x3", "ownerPointer": "0x268D9990000", "score": 3},
            ],
            sample_limit=4,
        )

        self.assertEqual(clusters[0]["count"], 2)
        self.assertEqual(clusters[0]["ownerPointerRegion"], "0x268D1230000")


if __name__ == "__main__":
    unittest.main()
