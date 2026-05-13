from __future__ import annotations

import unittest

from rift_live_test.root_signature_module_hint_sweep import (
    analyze_owner_field_candidate,
    analyze_parent_slot_candidate,
    bytes_from_hex,
    field_mismatch_warnings,
    qword_at,
    rank_candidates,
)


def make_hit(window_start: int, values: dict[int, int], *, hit_address: int = 0x20E0) -> dict:
    data = bytearray(0x220)
    for address, value in values.items():
        offset = address - window_start
        data[offset : offset + 8] = int(value).to_bytes(8, "little")
    return {
        "Address": hit_address,
        "AddressHex": f"0x{hit_address:X}",
        "Context": {
            "WindowStart": f"0x{window_start:X}",
            "BytesHex": " ".join(f"{byte:02X}" for byte in data),
        },
    }


class RootSignatureModuleHintSweepTests(unittest.TestCase):
    def test_qword_at_decodes_window_bytes(self) -> None:
        hit = make_hit(0x1000, {0x1010: 0x12345678})

        self.assertEqual(bytes_from_hex("78 56 34 12"), b"\x78\x56\x34\x12")
        self.assertEqual(qword_at(hit, 0x1010), 0x12345678)
        self.assertIsNone(qword_at(hit, 0x2000))

    def test_analyze_owner_field_candidate_scores_complete_known_owner(self) -> None:
        module_base = 0x700000000000
        owner_base = 0x2000
        hit = make_hit(
            0x1FE0,
            {
                owner_base + 0x0: module_base + 0x26AAE70,
                owner_base + 0x8: module_base + 0x272DBC0,
                owner_base + 0x10: 0x3000,
                owner_base + 0xE0: module_base + 0x263E950,
                owner_base + 0x110: module_base + 0x2657C80,
            },
        )

        candidate = analyze_owner_field_candidate(
            hit=hit,
            selected_owner_offset=0xE0,
            owner_field_rvas={0x0: 0x26AAE70, 0x8: 0x272DBC0, 0xE0: 0x263E950, 0x110: 0x2657C80},
            module_base=module_base,
            expected_owner=owner_base,
            expected_coord_pointer=0x3000,
        )

        self.assertEqual(candidate["ownerBase"], "0x2000")
        self.assertIn("complete-owner-module-field-signature", candidate["scoreReasons"])
        self.assertIn("matches-known-coord-pointer", candidate["scoreReasons"])
        self.assertGreater(candidate["score"], 200)

    def test_analyze_parent_slot_candidate_scores_known_parent(self) -> None:
        hit = make_hit(0x0F80, {0x1040: 0x2000}, hit_address=0x1000)

        candidate = analyze_parent_slot_candidate(
            hit=hit,
            selected_parent_slot_offset=-0x40,
            module_base=0x700000000000,
            expected_parent_slot=0x1040,
            expected_owner=0x2000,
        )

        self.assertEqual(candidate["parentSlot"], "0x1040")
        self.assertEqual(candidate["selectedParentSlotOffset"], "-0x40")
        self.assertEqual(candidate["ownerPointer"], "0x2000")
        self.assertIn("matches-known-parent-slot", candidate["scoreReasons"])
        self.assertIn("matches-known-owner", candidate["scoreReasons"])

    def test_field_mismatch_warnings_surface_stale_signature_fields(self) -> None:
        warnings = field_mismatch_warnings(
            {
                "ownerBase": "0x2000",
                "fieldMatches": [
                    {"offsetFromOwner": "0x0", "expectedRva": "0x1", "actualRva": "0x1", "matched": True},
                    {"offsetFromOwner": "0x110", "expectedRva": "0x2", "actualRva": "0x3", "matched": False},
                ],
            }
        )

        self.assertEqual(len(warnings), 1)
        self.assertIn("offset=0x110", warnings[0])

    def test_rank_candidates_prefers_score(self) -> None:
        ranked = rank_candidates([{"hitAddress": "0x2", "score": 1}, {"hitAddress": "0x1", "score": 10}])

        self.assertEqual(ranked[0]["hitAddress"], "0x1")


if __name__ == "__main__":
    unittest.main()
