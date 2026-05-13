from __future__ import annotations

import unittest

from rift_live_test.module_hint_graph_packet import build_graph, module_rva


class ModuleHintGraphPacketTests(unittest.TestCase):
    def test_module_rva_uses_module_base(self) -> None:
        self.assertEqual(module_rva("0x70000263E950", "0x700000000000"), "0x263E950")
        self.assertIsNone(module_rva("0x100", "0x700000000000"))

    def test_build_graph_links_module_hint_to_coord_pointer(self) -> None:
        occurrence = {
            "topRva": {
                "rva": "0x263E950",
                "score": 10,
                "occurrenceCount": 1,
                "sampleOccurrences": [
                    {
                        "moduleName": "rift_x64.exe",
                        "moduleBase": "0x700000000000",
                        "entryAddress": "0x0FC0",
                        "entryValue": "0x70000263E950",
                        "offsetFromOwner": "-0x40",
                        "offsetFromOwnerInt": -64,
                        "ownerAddress": "0x1000",
                        "sourceLists": ["ownerWindowModulePointers"],
                    }
                ],
            },
            "rvas": [],
        }
        parent_summary = {
            "slots": [
                {
                    "ownerSlot": "0x1000",
                    "ownerWindowModuleRvas": ["0x263E950"],
                    "exactTargets": [{"address": "0x2000", "label": "type-instance-player-candidate", "count": 1}],
                }
            ]
        }
        owner_graph = {
            "owners": [
                {
                    "ownerBase": "0x2000",
                    "coordPointer": "0x3000",
                    "coordPointerStorage": "0x2010",
                    "coordPointerIsCandidate": True,
                    "coordPointerCandidateLabel": "stable-d20-base-like",
                    "classification": "candidate-owner-heap-terminal",
                }
            ]
        }
        owner_instance = {
            "instances": [
                {
                    "ownerBase": "0x2000",
                    "coordPointer": "0x3000",
                    "coordPointerStorage": "0x2010",
                    "coordPointerCandidate": {"label": "stable"},
                    "qwords": [
                        {"offset": "0xE0", "address": "0x20E0", "value": "0x70000263E950"},
                    ],
                }
            ]
        }

        graph = build_graph(
            occurrence_summary=occurrence,
            parent_summary=parent_summary,
            owner_graph_summary=owner_graph,
            owner_instance_summary=owner_instance,
        )

        self.assertEqual(graph["candidateChain"]["status"], "candidate")
        self.assertFalse(graph["blockers"])
        self.assertEqual(graph["candidateChain"]["path"][-1]["value"], "0x3000")
        self.assertTrue(any(edge["kind"] == "points-to-owner" for edge in graph["edges"]))
        self.assertTrue(
            any(
                row["rva"] == "0x263E950" and row["matchesSelectedRva"]
                for row in graph["ownerInstance"]["modulePointerFields"]
            )
        )


if __name__ == "__main__":
    unittest.main()
