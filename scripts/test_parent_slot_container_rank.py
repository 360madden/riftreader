from __future__ import annotations

import unittest

from rift_live_test.parent_slot_container_rank import build_summary, near_offsets, summarize_slot


class ParentSlotContainerRankTests(unittest.TestCase):
    def test_near_offsets_filters_by_absolute_distance(self) -> None:
        self.assertEqual(near_offsets(["-0x40", "0x10", "0x200", "bad"]), ["-0x40", "0x10"])

    def test_summarize_slot_scores_best_container_seed(self) -> None:
        slot = {
            "ownerSlot": "0x1000",
            "classification": "owner-slot-with-module-hint",
            "exactTargets": [{"address": "0x2000", "label": "type-instance-player-candidate"}],
            "ownerWindowModulePointerCount": 1,
            "regionMatchCount": "0x96",
            "modulePointerCount": 10,
            "ownerWindowInteresting": [
                {
                    "offsetFromOwner": "-0x40",
                    "classification": {"modulePointer": {"rva": "0x263E950"}},
                },
                {"offsetFromOwner": "0x10", "classification": {"inTargetWindow": True}},
                {"offsetFromOwner": "0x18", "classification": {"inTargetWindow": True}},
                {"offsetFromOwner": "0x40", "classification": {"inTargetWindow": True}},
                {"offsetFromOwner": "0x48", "classification": {"inTargetWindow": True}},
            ],
        }
        owner = {
            "ownerBase": "0x2000",
            "score": 270,
            "missingRvas": [],
            "coordPointer": "0x3000",
            "coordPointerStorage": "0x2010",
            "coordPointerIsCandidate": True,
        }

        row = summarize_slot(
            slot=slot,
            owner_by_base={"0x2000": owner},
            selected_rva="0x263E950",
            player_label_fragment="player",
        )

        self.assertEqual(row["exactOwner"]["address"], "0x2000")
        self.assertIn("slot-has-selected-rva", row["scoreReasons"])
        self.assertIn("near-internal-pointer-cluster", row["scoreReasons"])
        self.assertIn("dense-region-matches", row["scoreReasons"])
        self.assertEqual(row["ownerWindowModulePointers"], [{"offsetFromOwner": "-0x40", "rva": "0x263E950"}])
        self.assertGreater(row["score"], 200)


if __name__ == "__main__":
    unittest.main()
