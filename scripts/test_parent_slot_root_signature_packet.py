from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.parent_slot_root_signature_packet import build_summary, offset_address, render_markdown


def write_json(root: Path, name: str, payload: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class ParentSlotRootSignaturePacketTests(unittest.TestCase):
    def test_offset_address_supports_negative_offsets(self) -> None:
        self.assertEqual(offset_address("0x1040", "-0x40"), "0x1000")
        self.assertIsNone(offset_address("bad", "-0x40"))

    def test_build_summary_creates_root_search_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parent_rank_path = write_json(
                root,
                "rank.json",
                {
                    "counts": {"slotCount": 1},
                    "topSlot": {
                        "ownerSlot": "0x1000",
                        "exactOwner": {"address": "0x2000", "label": "type-instance-player-candidate"},
                        "score": 285,
                        "scoreReasons": ["slot-has-selected-rva"],
                        "slotClassification": "owner-slot-with-module-hint",
                        "ownerCoordPointer": "0x3000",
                        "ownerCoordPointerStorage": "0x2010",
                        "ownerCoordPointerIsCandidate": True,
                        "parentRefParentHitCount": 0,
                        "ownerWindowModulePointers": [{"offsetFromOwner": "-0x40", "rva": "0x263E950"}],
                        "nearOwnerInternalPointerOffsets": ["0x0", "0x10", "0x40"],
                        "internalPointerOffsets": ["0x0", "0x10", "0x40", "0x200"],
                        "regionMatchCount": 159,
                        "modulePointerCount": 62,
                    },
                    "slots": [],
                },
            )
            parent_summary_path = write_json(
                root,
                "parent-summary.json",
                {
                    "counts": {"slotSummaryCount": 1},
                    "slots": [{"ownerSlot": "0x1000", "classification": "owner-slot-with-module-hint"}],
                },
            )
            owner_summary_path = write_json(
                root,
                "owner-summary.json",
                {
                    "counts": {"ownerCount": 1},
                    "topOwner": {
                        "ownerBase": "0x2000",
                        "score": 270,
                        "scoreReasons": ["complete-module-field-signature"],
                        "modulePointerFields": [
                            {"offset": "0x0", "storage": "0x2000", "value": "0x7000026AAE70", "rva": "0x26AAE70"},
                            {"offset": "0xE0", "storage": "0x20E0", "value": "0x70000263E950", "rva": "0x263E950"},
                        ],
                        "coordPointerStorage": "0x2010",
                        "coordPointer": "0x3000",
                        "coordPointerIsCandidate": True,
                        "coordPointerVec3": {"x": 1.0, "y": 2.0, "z": 3.0},
                        "parentRef": {"address": "0x1000", "parentHitCount": 0, "parentHits": []},
                    },
                    "owners": [],
                },
            )

            summary = build_summary(
                parent_slot_container_rank_path=parent_rank_path,
                parent_slot_summary_path=parent_summary_path,
                owner_structural_signature_path=owner_summary_path,
            )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["rootSearch"]["rootGapAbove"], "0x1000")
        self.assertFalse(summary["safety"]["movementProofEligible"])
        self.assertTrue(summary["safety"]["candidateOnly"])
        self.assertIn("0x263E950", {p.get("expectedRva") for p in summary["searchPredicates"]})
        self.assertEqual(summary["signature"]["parentSlotModuleHints"][0]["storageAddress"], "0xFC0")
        markdown = render_markdown(summary)
        self.assertIn("Parent-slot root signature packet", markdown)
        self.assertIn("parent-slot-selected-rva-module-hint", markdown)

    def test_build_summary_blocks_without_parent_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parent_rank_path = write_json(root, "rank.json", {"counts": {"slotCount": 0}, "slots": []})
            parent_summary_path = write_json(root, "parent-summary.json", {"counts": {"slotSummaryCount": 0}, "slots": []})
            owner_summary_path = write_json(root, "owner-summary.json", {"counts": {"ownerCount": 0}, "owners": []})

            summary = build_summary(
                parent_slot_container_rank_path=parent_rank_path,
                parent_slot_summary_path=parent_summary_path,
                owner_structural_signature_path=owner_summary_path,
            )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("no-parent-slot-container-rank-row-found", summary["blockers"])
        self.assertIn("no-owner-structural-signature-row-found", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
