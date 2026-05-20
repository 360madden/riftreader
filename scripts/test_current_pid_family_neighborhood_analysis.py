from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import current_pid_family_neighborhood_analysis as analysis


def write_jsonl(path: Path, addresses: list[int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            json.dumps(
                {
                    "candidate_id": f"hit-{index:06d}",
                    "absolute_address_hex": f"0x{address:X}",
                    "support_count": index,
                    "axis_order": "xyz",
                    "best_max_abs_distance": 0.01,
                }
            )
            for index, address in enumerate(addresses, start=1)
        )
        + "\n",
        encoding="utf-8",
    )
    return path


class CurrentPidFamilyNeighborhoodAnalysisTests(unittest.TestCase):
    def test_family_base_aligns_down(self) -> None:
        self.assertEqual(analysis.family_base(0x12345, 0x1000), 0x12000)
        self.assertEqual(analysis.family_base(0x1000, 0x1000), 0x1000)

    def test_load_candidate_jsonl_keeps_addressed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_jsonl(Path(temp) / "candidates.jsonl", [0x1000, 0x2000])

            rows = analysis.load_candidate_jsonl(path)

            self.assertEqual([row["_addressInt"] for row in rows], [0x1000, 0x2000])

    def test_analyze_reports_anchor_family_and_pairwise_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            anchor = 0x1A91015CB00
            family = analysis.family_base(anchor, analysis.FAMILY_SPAN_16MIB)
            run_a = write_jsonl(root / "run-a" / "api-family-vec3-candidates.jsonl", [anchor, family + 0x2000, family + analysis.FAMILY_SPAN_16MIB + 0x10])
            run_b = write_jsonl(root / "run-b" / "api-family-vec3-candidates.jsonl", [anchor, family + 0x3000])

            summary = analysis.analyze_candidate_files([run_a, run_b], anchor, adjacent_family_radius=1)

            self.assertTrue(summary["classification"]["anchorFamilySurvived"])
            self.assertTrue(summary["classification"]["adjacentFamiliesHaveCandidates"])
            self.assertEqual(summary["crossRunSharedAddressCount"], 1)
            self.assertEqual(summary["pairwiseOverlap"][0]["sharedAddressCount"], 1)
            self.assertEqual(summary["runs"][0]["anchorAdjacentFamilyCandidateCounts"]["+1"], 1)

    def test_run_bootstraps_from_current_truth_and_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            anchor = 0x1A91015CB00
            truth = root / "docs" / "recovery" / "current-truth.json"
            truth.parent.mkdir(parents=True, exist_ok=True)
            truth.write_text(
                json.dumps(
                    {
                        "target": {"processId": 1948, "targetWindowHandle": "0x3C0D58"},
                        "bestCurrentCandidate": {"candidateId": "api-family-hit-000010", "addressHex": f"0x{anchor:X}"},
                    }
                ),
                encoding="utf-8",
            )
            write_jsonl(
                root / "scripts" / "captures" / "family-scan-currentpid-1948-test" / "api-family-vec3-candidates.jsonl",
                [anchor],
            )
            out = root / "out"

            code, summary = analysis.run(
                argparse.Namespace(
                    repo_root=root,
                    current_truth_json=Path("docs/recovery/current-truth.json"),
                    pid=None,
                    anchor_address=None,
                    anchor_candidate_id=None,
                    candidate_jsonl=None,
                    output_root=out,
                    adjacent_family_radius=1,
                    self_test=False,
                    json=True,
                )
            )

            self.assertEqual(code, 0)
            self.assertEqual(summary["pid"], 1948)
            self.assertEqual(summary["anchor"]["candidateId"], "api-family-hit-000010")
            self.assertTrue(Path(summary["artifacts"]["summaryJson"]).exists())
            self.assertTrue(Path(summary["artifacts"]["summaryMarkdown"]).exists())
            self.assertFalse(summary["safety"]["movementSent"])


if __name__ == "__main__":
    unittest.main()
