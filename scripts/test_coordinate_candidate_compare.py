from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.coordinate_candidate_compare import compare_file, main


class CoordinateCandidateCompareTests(unittest.TestCase):
    def test_compare_file_classifies_match_and_stale_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidates = root / "candidates.json"
            candidates.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "candidate_id": "match",
                                "absolute_address_hex": "0x1000",
                                "value_preview": [10.1, 20.0, 30.0],
                            },
                            {
                                "candidate_id": "stale",
                                "absolute_address_hex": "0x2000",
                                "value_preview": [99.0, 20.0, 30.0],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = compare_file(
                candidates,
                {"coordinate": {"x": 10.0, "y": 20.0, "z": 30.0}},
                root,
                tolerance=0.25,
                max_records=10,
            )

            self.assertEqual(result["recordCount"], 2)
            self.assertEqual(result["matchCount"], 1)
            self.assertEqual(result["best"]["candidateId"], "match")

    def test_cli_blocks_when_no_candidate_matches_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ref = root / "ref.json"
            candidates = root / "candidates.json"
            out = root / "out"
            ref.write_text(json.dumps({"coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")
            candidates.write_text(
                json.dumps({"candidates": [{"candidate_id": "old", "value_preview": [9, 2, 3]}]}),
                encoding="utf-8",
            )

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--api-reference",
                    str(ref),
                    "--candidate-file",
                    str(candidates),
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "candidate-only-no-current-api-match")
            self.assertFalse(summary["safety"]["movementSent"])


if __name__ == "__main__":
    unittest.main()
