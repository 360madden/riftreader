from __future__ import annotations

import unittest

from rift_live_test.owner_type_parent_graph import build_graph


class OwnerTypeParentGraphTests(unittest.TestCase):
    def test_build_graph_classifies_terminal_candidate_owner(self) -> None:
        owner_summary = {
            "instances": [
                {
                    "ownerBase": "0x1000",
                    "coordPointer": "0x5000",
                    "coordPointerStorage": "0x1010",
                    "coordPointerIsCandidate": True,
                    "coordPointerCandidate": {"label": "player"},
                    "coordPointerVec3": {"x": 1.0, "y": 2.0, "z": 3.0},
                },
                {
                    "ownerBase": "0x2000",
                    "coordPointer": "0x6000",
                    "coordPointerStorage": "0x2010",
                    "coordPointerIsCandidate": False,
                    "coordPointerVec3": {"x": 4.0, "y": 5.0, "z": 6.0},
                },
            ]
        }
        pointer_summary = {
            "rankedTargets": [
                {"target": "0x1000", "hitCount": 1, "hits": [{"address": "0x3000"}]},
                {"target": "0x3000", "hitCount": 0, "hits": []},
                {"target": "0x2000", "hitCount": 0, "hits": []},
            ]
        }

        graph = build_graph(owner_summary, pointer_summary)

        self.assertEqual(graph["candidateOwnerCount"], 1)
        self.assertEqual(graph["terminalCandidateOwnerCount"], 1)
        self.assertEqual(graph["owners"][0]["classification"], "candidate-owner-heap-terminal")
        self.assertEqual(graph["owners"][0]["parentRefs"][0]["address"], "0x3000")

    def test_build_graph_marks_candidate_with_parent_search_needed(self) -> None:
        owner_summary = {
            "instances": [
                {
                    "ownerBase": "0x1000",
                    "coordPointer": "0x5000",
                    "coordPointerIsCandidate": True,
                    "coordPointerCandidate": {"label": "player"},
                }
            ]
        }
        pointer_summary = {
            "rankedTargets": [
                {"target": "0x1000", "hitCount": 1, "hits": [{"address": "0x3000"}]},
                {"target": "0x3000", "hitCount": 1, "hits": [{"address": "0x4000"}]},
            ]
        }

        graph = build_graph(owner_summary, pointer_summary)

        self.assertEqual(graph["terminalCandidateOwnerCount"], 0)
        self.assertEqual(graph["owners"][0]["classification"], "candidate-owner-parent-search-needed")


if __name__ == "__main__":
    unittest.main()
