from __future__ import annotations

import unittest

from rift_live_test.owner_structural_signature_packet import (
    build_summary,
    module_fields,
    module_rva,
    summarize_owner,
)


class OwnerStructuralSignaturePacketTests(unittest.TestCase):
    def test_module_rva_bounds_module_window(self) -> None:
        self.assertEqual(module_rva("0x70000263E950", "0x700000000000"), "0x263E950")
        self.assertIsNone(module_rva("0x700F00000000", "0x700000000000"))

    def test_module_fields_extracts_rvas_from_qwords(self) -> None:
        instance = {
            "qwords": [
                {"offset": "0x0", "address": "0x1000", "value": "0x7000026AAE70"},
                {"offset": "0x10", "address": "0x1010", "value": "0x2000"},
            ]
        }

        fields = module_fields(instance, "0x700000000000")

        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["rva"], "0x26AAE70")

    def test_summarize_owner_scores_complete_signature(self) -> None:
        instance = {
            "ownerBase": "0x2000",
            "coordPointerOffset": "0x10",
            "coordPointerStorage": "0x2010",
            "coordPointer": "0x3000",
            "coordPointerIsCandidate": True,
            "coordPointerVec3": {"x": 1, "y": 2, "z": 3},
            "qwords": [
                {"offset": "0x0", "address": "0x2000", "value": "0x7000026AAE70"},
                {"offset": "0x8", "address": "0x2008", "value": "0x70000272DBC0"},
                {"offset": "0xE0", "address": "0x20E0", "value": "0x70000263E950"},
                {"offset": "0x110", "address": "0x2110", "value": "0x700002657C80"},
            ],
        }
        graph_owner = {"parentRefCount": 1, "classification": "candidate-owner-heap-terminal"}
        parent_slot = {"ownerSlot": "0x1000", "ownerWindowModulePointerCount": 1}

        row = summarize_owner(
            instance=instance,
            graph_owner=graph_owner,
            parent_slot=parent_slot,
            target_rvas=["0x26AAE70", "0x272DBC0", "0x263E950", "0x2657C80"],
            module_base="0x700000000000",
        )

        self.assertFalse(row["missingRvas"])
        self.assertEqual(row["coordPointer"], "0x3000")
        self.assertIn("complete-module-field-signature", row["scoreReasons"])
        self.assertGreater(row["score"], 200)


if __name__ == "__main__":
    unittest.main()
