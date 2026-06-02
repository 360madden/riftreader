from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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

    def test_default_scan_is_quick_bounded(self) -> None:
        self.assertEqual(matrix.DEFAULT_MAX_INSTRUCTIONS, 200_000)

    def test_limited_scan_warning_is_explicit(self) -> None:
        original_scan_binary = matrix.scan_binary
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            binary = root / "rift_x64.exe"
            binary.write_bytes(b"MZ")

            def fake_scan_binary(*args, **kwargs):
                return {
                    "status": "passed",
                    "binary": str(binary),
                    "imageBase": "0x140000000",
                    "rootRva": "0x32EBC80",
                    "rootAddress": "0x1432EBC80",
                    "sections": [],
                    "instructionsScanned": 200_000,
                    "rootReferences": [],
                    "offsetHits": {"0x300": []},
                    "scanLimits": {
                        "rvaWindows": [],
                        "includeStackBase": False,
                        "maxInstructions": 200_000,
                        "chunkBytes": matrix.DEFAULT_CHUNK_BYTES,
                        "hitLimitReached": False,
                        "maxInstructionLimitReached": True,
                    },
                }

            try:
                matrix.scan_binary = fake_scan_binary
                summary = matrix.build_summary(
                    root,
                    binary_path=binary,
                    offsets={0x300},
                    root_rva=matrix.DEFAULT_ROOT_RVA,
                    include_all_sections=False,
                    max_hits_per_offset=10,
                    max_root_refs=10,
                    context_bytes=matrix.DEFAULT_CONTEXT_BYTES,
                    rva_windows=[],
                    include_stack_base=False,
                    max_instructions=matrix.DEFAULT_MAX_INSTRUCTIONS,
                    chunk_bytes=matrix.DEFAULT_CHUNK_BYTES,
                    output_root=None,
                )
            finally:
                matrix.scan_binary = original_scan_binary

        self.assertIn("scan-instruction-limit-reached:200000", summary["warnings"])
        self.assertTrue(any("--full-scan" in action for action in summary["next"]["recommendedActions"]))


if __name__ == "__main__":
    unittest.main()
