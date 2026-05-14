from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.coordinate_center_file import main


class CoordinateCenterFileTests(unittest.TestCase):
    def test_comparison_summary_generates_ranked_center_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            comparison = root / "comparison" / "summary.json"
            comparison.parent.mkdir(parents=True)
            out = root / "out"
            comparison.write_text(
                json.dumps(
                    {
                        "candidateFiles": [
                            {
                                "path": "candidates.json",
                                "rows": [
                                    {"candidateId": "slow", "address": "0x2000", "maxAbsDelta": 5.0},
                                    {"candidateId": "best", "address": "0x1000", "maxAbsDelta": 0.1},
                                    {"candidateId": "duplicate-worse", "address": "0x1000", "maxAbsDelta": 3.0},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--comparison-summary",
                    str(comparison),
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            centers = json.loads((out / "coordinate-scan-centers.json").read_text(encoding="utf-8"))["centers"]
            self.assertEqual(summary["status"], "passed")
            self.assertEqual(len(centers), 2)
            self.assertEqual(centers[0]["label"], "best")
            self.assertEqual(centers[0]["address"], "0x1000")
            self.assertFalse(summary["safety"]["movementSent"])

    def test_no_addresses_blocks_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            comparison = root / "comparison" / "summary.json"
            comparison.parent.mkdir(parents=True)
            out = root / "out"
            comparison.write_text(
                json.dumps({"candidateFiles": [{"path": "candidates.json", "rows": [{"candidateId": "missing"}]}]}),
                encoding="utf-8",
            )

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--comparison-summary",
                    str(comparison),
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("no-center-addresses-found", summary["blockers"])
            self.assertFalse((out / "coordinate-scan-centers.json").exists())

    def test_update_current_truth_records_center_file_paths(self) -> None:
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
            comparison = root / "comparison" / "summary.json"
            comparison.parent.mkdir(parents=True)
            comparison.write_text(
                json.dumps({"candidateFiles": [{"path": "candidates.json", "rows": [{"candidateId": "best", "address": "0x1000"}]}]}),
                encoding="utf-8",
            )
            out = root / "out"

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--comparison-summary",
                    str(comparison),
                    "--output-root",
                    str(out),
                    "--update-current-truth",
                ]
            )

            self.assertEqual(code, 0)
            updated = json.loads(truth.read_text(encoding="utf-8"))
            routing = updated["visualEvidenceRouting"]
            self.assertEqual(routing["latestGeneratedCenterFile"], "out/coordinate-scan-centers.json")
            self.assertIn("| Latest generated center file | `out/coordinate-scan-centers.json` |", truth_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
