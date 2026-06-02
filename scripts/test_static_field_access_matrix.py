from __future__ import annotations

import unittest

from tools.riftreader_workflow import static_field_access_matrix as matrix


class StaticFieldAccessMatrixTests(unittest.TestCase):
    def test_semantic_tags_classify_scalar_float_ops(self) -> None:
        self.assertIn("scalar-float", matrix.semantic_tags("movss"))
        self.assertIn("arithmetic", matrix.semantic_tags("subss"))
        self.assertIn("compare", matrix.semantic_tags("comiss"))

    def test_summarize_offsets_rewards_same_promoted_cluster(self) -> None:
        ranked = matrix.summarize_offsets(
            {
                "0x300": [
                    {
                        "offsetInt": 0x300,
                        "operandAccess": "read",
                        "semanticTags": ["scalar-float", "compare"],
                        "linearFunctionStartRva": "0x57A000",
                    }
                ],
                "0x320": [
                    {
                        "offsetInt": 0x320,
                        "operandAccess": "read-write",
                        "semanticTags": ["scalar-float", "move"],
                        "linearFunctionStartRva": "0x57A000",
                    }
                ],
            }
        )
        by_offset = {row["offset"]: row for row in ranked}
        self.assertEqual(by_offset["0x300"]["samePromotedClusterFunctionCount"], 1)
        self.assertEqual(by_offset["0x320"]["readiness"], "already-promoted-static-anchor")
        self.assertGreater(by_offset["0x320"]["score"], by_offset["0x300"]["score"])

    def test_parse_offsets_accepts_repeated_and_comma_separated_values(self) -> None:
        self.assertEqual(matrix.parse_offsets(["0x300,0x304", "0x408"]), {0x300, 0x304, 0x408})


if __name__ == "__main__":
    unittest.main()
