from __future__ import annotations

import unittest
from pathlib import Path

from rift_live_test.parent_slot_neighborhood_summary import build_summary, summarize_slot


class ParentSlotNeighborhoodSummaryTests(unittest.TestCase):
    def test_summarize_slot_classifies_module_hint_owner_slot(self) -> None:
        doc = {
            "status": "passed",
            "owner": {"address": "0x1000"},
            "targets": [{"address": "0x5000", "label": "owner"}],
            "analysis": {
                "exactTargetCounts": {"0x5000": 1},
                "regionMatchCount": 2,
                "modulePointerCount": 1,
                "ownerWindowModulePointerCount": 1,
                "ownerWindowModulePointers": [
                    {"classification": {"modulePointer": {"rva": "0x1234"}}},
                ],
                "ownerWindow": [
                    {"classification": {"interesting": True}},
                ],
            },
        }

        row = summarize_slot(Path("slot.json"), doc)

        self.assertEqual(row["classification"], "owner-slot-with-module-hint")
        self.assertEqual(row["ownerWindowModuleRvas"], ["0x1234"])

    def test_build_summary_counts_slots(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "slot.json"
            path.write_text(
                json.dumps(
                    {
                        "owner": {"address": "0x1000"},
                        "targets": [{"address": "0x5000", "label": "owner"}],
                        "analysis": {
                            "exactTargetCounts": {"0x5000": 1},
                            "ownerWindowModulePointerCount": 0,
                            "ownerWindowModulePointers": [],
                            "ownerWindow": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = build_summary([path])

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["counts"]["slotSummaryCount"], 1)
        self.assertEqual(summary["counts"]["exactOwnerSlotCount"], 1)


if __name__ == "__main__":
    unittest.main()
