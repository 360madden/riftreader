from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.coordinate_family_rank import main


class CoordinateFamilyRankTests(unittest.TestCase):
    def write_candidates(
        self,
        path: Path,
        *,
        generated_at: str,
        process_id: int = 79184,
        hwnd: str = "0xA90BFC",
        reference: tuple[float, float, float],
        candidates: list[dict[str, object]] | None = None,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "mode": "riftreader-api-family-vec3-candidates",
                    "generatedAtUtc": generated_at,
                    "processId": process_id,
                    "targetWindowHandle": hwnd,
                    "reference": {"X": reference[0], "Y": reference[1], "Z": reference[2]},
                    "candidateCount": len(candidates or []),
                    "candidates": candidates or [],
                }
            ),
            encoding="utf-8",
        )

    def candidate(
        self,
        address: str,
        base: str,
        offset: str,
        *,
        value: tuple[float, float, float],
        delta: float,
    ) -> dict[str, object]:
        return {
            "candidate_id": f"candidate-{address}",
            "absolute_address_hex": address,
            "base_address_hex": base,
            "offset_hex": offset,
            "value_preview": [value[0], value[1], value[2]],
            "best_max_abs_distance": delta,
            "process_id": 79184,
            "target_window_handle": "0xA90BFC",
            "truth_readiness": "candidate_only_not_movement_proof",
        }

    def run_main(self, args: list[str]) -> int:
        with redirect_stdout(StringIO()):
            return main(args)

    def test_shared_address_beats_single_pose_exact_hits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            pose_a = temp_path / "scripts" / "captures" / "family-scan-a" / "api-family-vec3-candidates.json"
            pose_b = temp_path / "scripts" / "captures" / "family-scan-b" / "api-family-vec3-candidates.json"
            out = temp_path / "rank"
            self.write_candidates(
                pose_a,
                generated_at="2026-05-13T02:46:23Z",
                reference=(7376.67, 863.58, 2988.98),
                candidates=[
                    self.candidate("0x17382765E40", "0x17382730000", "0x35E40", value=(7376.6699, 863.58, 2988.98), delta=0.00008),
                    self.candidate("0x1738127A5A4", "0x17381270000", "0xA5A4", value=(7376.67, 863.5212, 2988.98), delta=0.05882),
                ],
            )
            self.write_candidates(
                pose_b,
                generated_at="2026-05-13T03:30:27Z",
                reference=(7376.41, 863.58, 2989.52),
                candidates=[
                    self.candidate("0x17383632BF0", "0x17383620000", "0x12BF0", value=(7376.4097, 863.58, 2989.52), delta=0.00033),
                    self.candidate("0x1738127A5A4", "0x17381270000", "0xA5A4", value=(7376.41, 863.5212, 2989.52), delta=0.05882),
                ],
            )

            code = self.run_main(
                [
                    "--repo-root",
                    str(temp_path),
                    "--candidate-file",
                    str(pose_a),
                    "--candidate-file",
                    str(pose_b),
                    "--process-id",
                    "79184",
                    "--target-hwnd",
                    "0xA90BFC",
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 0)
            summary = json.loads((out / "coordinate-family-rankings.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "ranked")
            self.assertEqual(summary["topAddress"]["addressHex"], "0x1738127A5A4")
            self.assertEqual(summary["topAddress"]["supportPoseCount"], 2)
            self.assertEqual(summary["topFamily"]["familyBaseHex"], "0x17381270000")
            self.assertFalse(summary["topAddress"]["promotionEligible"])
            self.assertTrue(summary["topAddress"]["candidateOnly"])
            self.assertIn("restart-validation-missing", summary["topAddress"]["promotionBlockers"])

    def test_target_filter_blocks_wrong_pid_and_hwnd(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            pose = temp_path / "api-family-vec3-candidates.json"
            out = temp_path / "rank"
            self.write_candidates(
                pose,
                generated_at="2026-05-13T02:46:23Z",
                process_id=111,
                hwnd="0x123",
                reference=(1.0, 2.0, 3.0),
                candidates=[
                    {
                        **self.candidate("0x2000", "0x1000", "0x1000", value=(1.0, 2.0, 3.0), delta=0.0),
                        "process_id": 111,
                        "target_window_handle": "0x123",
                    }
                ],
            )

            code = self.run_main(
                [
                    "--repo-root",
                    str(temp_path),
                    "--candidate-file",
                    str(pose),
                    "--process-id",
                    "79184",
                    "--target-hwnd",
                    "0xA90BFC",
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "coordinate-family-rankings.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("candidate-observations-not-found-for-target", summary["blockers"])

    def test_no_candidate_files_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            out = temp_path / "rank"

            code = self.run_main(
                [
                    "--repo-root",
                    str(temp_path),
                    "--no-default-candidate-glob",
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "coordinate-family-rankings.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("candidate-files-not-found", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
