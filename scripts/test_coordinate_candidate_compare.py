from __future__ import annotations

import json
import os
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

    def test_two_reference_mode_classifies_baseline_only_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline = root / "baseline.json"
            displaced = root / "displaced.json"
            candidates = root / "candidates.json"
            out = root / "out"
            baseline.write_text(json.dumps({"coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")
            displaced.write_text(json.dumps({"coordinate": {"x": 5, "y": 2, "z": 3}}), encoding="utf-8")
            candidates.write_text(
                json.dumps({"candidates": [{"candidate_id": "baseline-copy", "value_preview": [1.0, 2.0, 3.0]}]}),
                encoding="utf-8",
            )

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--api-reference",
                    str(baseline),
                    "--displaced-api-reference",
                    str(displaced),
                    "--candidate-file",
                    str(candidates),
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "candidate-only-no-two-reference-match")
            file_result = summary["candidateFiles"][0]
            self.assertEqual(file_result["matchCount"], 1)
            self.assertEqual(file_result["displacedMatchCount"], 0)
            self.assertEqual(file_result["bothReferenceMatchCount"], 0)
            self.assertEqual(file_result["rows"][0]["twoReferenceStatus"], "baseline-only")

    def test_latest_displaced_alias_blocks_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline = root / "baseline.json"
            candidates = root / "candidates.json"
            out = root / "out"
            baseline.write_text(
                json.dumps({"processId": 123, "targetWindowHandle": "0xABC", "coordinate": {"x": 1, "y": 2, "z": 3}}),
                encoding="utf-8",
            )
            candidates.write_text(json.dumps({"candidates": [{"candidate_id": "old", "value_preview": [1, 2, 3]}]}), encoding="utf-8")

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--api-reference",
                    str(baseline),
                    "--displaced-api-reference",
                    "latest-displaced",
                    "--candidate-file",
                    str(candidates),
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("displaced-api-reference-latest-not-found", summary["blockers"])
            self.assertEqual(summary["displacedReferenceResolvedFromAlias"], "latest-displaced")

    def test_latest_displaced_alias_resolves_marked_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            captures = root / "scripts" / "captures" / "manual-displaced-reference"
            captures.mkdir(parents=True)
            baseline = root / "baseline.json"
            displaced = captures / "rift-api-reference-currentpid-123-displaced.json"
            candidates = root / "candidates.json"
            out = root / "out"
            baseline.write_text(
                json.dumps({"processId": 123, "targetWindowHandle": "0xABC", "coordinate": {"x": 1, "y": 2, "z": 3}}),
                encoding="utf-8",
            )
            displaced.write_text(
                json.dumps(
                    {
                        "processId": 123,
                        "targetWindowHandle": "0xABC",
                        "poseLabel": "manual-displaced",
                        "coordinate": {"x": 1, "y": 2, "z": 3},
                    }
                ),
                encoding="utf-8",
            )
            candidates.write_text(
                json.dumps({"candidates": [{"candidate_id": "both", "absolute_address_hex": "0x1000", "value_preview": [1, 2, 3]}]}),
                encoding="utf-8",
            )

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--api-reference",
                    str(baseline),
                    "--displaced-api-reference",
                    "latest-displaced",
                    "--candidate-file",
                    str(candidates),
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "api-candidate-two-reference-match")
            self.assertEqual(summary["displacedReferenceResolvedFromAlias"], "latest-displaced")
            self.assertEqual(summary["candidateFiles"][0]["bothReferenceMatchCount"], 1)

    def test_update_current_truth_records_comparison_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            truth = root / "docs" / "recovery" / "current-truth.json"
            truth.parent.mkdir(parents=True)
            truth.write_text(json.dumps({"visualEvidenceRouting": {}}), encoding="utf-8")
            truth_md = root / "docs" / "recovery" / "current-truth.md"
            truth_md.write_text(
                "\n".join(
                    [
                        "# Current truth",
                        "",
                        "## Visual/capture proof-route policy — test",
                        "",
                        "| Field | Value |",
                        "|---|---|",
                        "| Latest route status | `blocked` |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            ref = root / "ref.json"
            candidates = root / "candidates.json"
            out = root / "out"
            ref.write_text(json.dumps({"coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")
            candidates.write_text(
                json.dumps({"candidates": [{"candidate_id": "match", "absolute_address_hex": "0x1000", "value_preview": [1, 2, 3]}]}),
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
                    "--update-current-truth",
                ]
            )

            self.assertEqual(code, 0)
            routing = json.loads(truth.read_text(encoding="utf-8"))["visualEvidenceRouting"]
            self.assertEqual(routing["latestCandidateComparison"], "out/summary.json")
            self.assertEqual(routing["latestCandidateComparisonStatus"], "api-candidate-match")
            self.assertIn("| Latest candidate comparison | `out/summary.json` |", truth_md.read_text(encoding="utf-8"))

    def test_displaced_reference_age_budget_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline = root / "baseline.json"
            displaced = root / "displaced.json"
            candidates = root / "candidates.json"
            out = root / "out"
            baseline.write_text(json.dumps({"coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")
            displaced.write_text(json.dumps({"coordinate": {"x": 2, "y": 2, "z": 3}}), encoding="utf-8")
            candidates.write_text(
                json.dumps({"candidates": [{"candidate_id": "old", "absolute_address_hex": "0x1000", "value_preview": [1, 2, 3]}]}),
                encoding="utf-8",
            )
            os.utime(displaced, (baseline.stat().st_mtime - 1000, baseline.stat().st_mtime - 1000))

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--api-reference",
                    str(baseline),
                    "--displaced-api-reference",
                    str(displaced),
                    "--candidate-file",
                    str(candidates),
                    "--max-displaced-reference-age-seconds",
                    "30",
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertTrue(any(str(item).startswith("displaced-api-reference-age-exceeded:") for item in summary["blockers"]))


if __name__ == "__main__":
    unittest.main()
