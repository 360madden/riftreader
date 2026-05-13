from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.parent_slot_module_hint_rank import build_summary, extract_module_hints, parse_offset


class ParentSlotModuleHintRankTests(unittest.TestCase):
    def test_parse_offset_accepts_signed_hex(self) -> None:
        self.assertEqual(parse_offset("-0x40"), -0x40)
        self.assertEqual(parse_offset("0x18"), 0x18)
        self.assertIsNone(parse_offset("not-hex"))

    def test_player_near_owner_hint_ranks_first(self) -> None:
        parent_summary = {
            "generatedAtUtc": "2026-05-13T22:03:34Z",
            "slots": [
                {
                    "ownerSlot": "0x1000",
                    "classification": "owner-slot-with-module-hint",
                    "exactTargets": [{"address": "0x2000", "label": "type-instance-player-candidate"}],
                    "ownerWindowInteresting": [
                        {
                            "address": "0x0FC0",
                            "offsetFromOwner": "-0x40",
                            "classification": {
                                "modulePointer": {
                                    "moduleName": "rift_x64.exe",
                                    "moduleBase": "0x70000000",
                                    "rva": "0x263E950",
                                }
                            },
                        }
                    ],
                },
                {
                    "ownerSlot": "0x3000",
                    "classification": "owner-slot-with-module-hint",
                    "exactTargets": [{"address": "0x4000", "label": "type-instance-a"}],
                    "ownerWindowInteresting": [
                        {
                            "address": "0x2C58",
                            "offsetFromOwner": "-0x3A8",
                            "classification": {
                                "modulePointer": {
                                    "moduleName": "rift_x64.exe",
                                    "moduleBase": "0x70000000",
                                    "rva": "0x2691A88",
                                }
                            },
                        }
                    ],
                },
            ],
        }

        hints = extract_module_hints(parent_summary)
        summary = build_summary(Path("parent.json"), parent_summary)

        self.assertEqual(len(hints), 2)
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["topHint"]["rva"], "0x263E950")
        self.assertIn("player-candidate-slot", summary["topHint"]["scoreReasons"])

    def test_build_summary_counts_shared_rva(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "parent-summary.json"
            parent_summary = {
                "slots": [
                    {
                        "ownerSlot": "0x1000",
                        "classification": "owner-slot-with-module-hint",
                        "exactTargets": [{"label": "type-instance-a"}],
                        "ownerWindowInteresting": [
                            {
                                "offsetFromOwner": "0x20",
                                "classification": {"modulePointer": {"rva": "0x1234"}},
                            }
                        ],
                    },
                    {
                        "ownerSlot": "0x2000",
                        "classification": "owner-slot-with-module-hint",
                        "exactTargets": [{"label": "type-instance-b"}],
                        "ownerWindowInteresting": [
                            {
                                "offsetFromOwner": "0x28",
                                "classification": {"modulePointer": {"rva": "0x1234"}},
                            }
                        ],
                    },
                ]
            }
            path.write_text(json.dumps(parent_summary), encoding="utf-8")
            summary = build_summary(path, parent_summary)

        self.assertEqual(summary["counts"]["hintCount"], 2)
        self.assertEqual(summary["counts"]["uniqueRvaCount"], 1)
        self.assertEqual(summary["counts"]["sharedRvaCount"], 1)
        self.assertIn("rva-repeats-across-slots", summary["hints"][0]["scoreReasons"])


if __name__ == "__main__":
    unittest.main()
