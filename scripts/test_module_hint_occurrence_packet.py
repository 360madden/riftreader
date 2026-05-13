from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.module_hint_occurrence_packet import build_summary, norm_hex, occurrences_from_doc


class ModuleHintOccurrencePacketTests(unittest.TestCase):
    def test_norm_hex_normalizes_numeric_strings(self) -> None:
        self.assertEqual(norm_hex("0x263e950"), "0x263E950")
        self.assertEqual(norm_hex("400"), "0x190")

    def test_occurrences_from_pointer_owner_summary_dedupes_sources(self) -> None:
        doc = {
            "kind": "pointer-owner-neighborhood-inspector",
            "generatedAtUtc": "2026-05-13T22:00:00Z",
            "owner": {"address": "0x1000"},
            "targets": [{"label": "type-instance-player-candidate"}],
            "analysis": {
                "ownerWindowModulePointers": [
                    {
                        "address": "0x0FC0",
                        "value": "0x7000263E950",
                        "offsetFromOwner": "-0x40",
                        "classification": {
                            "modulePointer": {
                                "moduleName": "rift_x64.exe",
                                "moduleBase": "0x70000000000",
                                "rva": "0x263E950",
                            }
                        },
                    }
                ],
                "regionMatches": [
                    {
                        "address": "0x0FC0",
                        "value": "0x7000263E950",
                        "offsetFromOwner": "-0x40",
                        "classification": {
                            "modulePointer": {
                                "moduleName": "rift_x64.exe",
                                "moduleBase": "0x70000000000",
                                "rva": "0x263E950",
                            }
                        },
                    }
                ],
            },
        }

        rows = occurrences_from_doc(Path("summary.json"), Path.cwd(), doc)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rva"], "0x263E950")
        self.assertEqual(set(rows[0]["sourceLists"]), {"ownerWindowModulePointers", "regionMatches"})

    def test_build_summary_ranks_player_near_owner_rva(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "scripts" / "captures" / "run-a"
            run.mkdir(parents=True)
            (run / "summary.json").write_text(
                json.dumps(
                    {
                        "kind": "pointer-owner-neighborhood-inspector",
                        "owner": {"address": "0x1000"},
                        "targets": [{"label": "type-instance-player-candidate"}],
                        "analysis": {
                            "ownerWindowModulePointers": [
                                {
                                    "address": "0x0FC0",
                                    "value": "0x7000263E950",
                                    "offsetFromOwner": "-0x40",
                                    "classification": {
                                        "modulePointer": {
                                            "moduleName": "rift_x64.exe",
                                            "moduleBase": "0x70000000000",
                                            "rva": "0x263E950",
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = build_summary(
                repo_root=root,
                captures_roots=[root / "scripts" / "captures"],
                rvas={"0x263E950"},
                module_addresses=set(),
                player_label_fragment="player",
            )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["topRva"]["rva"], "0x263E950")
        self.assertEqual(summary["topRva"]["nearOwnerOccurrenceCount"], 1)


if __name__ == "__main__":
    unittest.main()
