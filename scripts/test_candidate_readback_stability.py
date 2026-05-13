from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.candidate_readback_stability import build_summary, main


def readback(address: int, corrected_delta: float, *, value: tuple[float, float, float], match: bool) -> dict:
    return {
        "rank": 1,
        "candidateId": f"candidate-{address:X}",
        "address": address,
        "addressHex": f"0x{address:X}",
        "memoryValue": {"x": value[0], "y": value[1], "z": value[2]},
        "reference": {"x": 10.0, "y": 20.0, "z": 30.0},
        "offsetCorrectedValue": {"x": 10.0 + corrected_delta, "y": 20.0, "z": 30.0},
        "directMaxAbsDelta": 5.0,
        "offsetCorrectedMaxAbsDelta": corrected_delta,
        "directWithinTolerance": False,
        "offsetCorrectedWithinTolerance": match,
        "classification": "offset-corrected-current-coordinate-candidate" if match else "readback-mismatch",
    }


def summary_doc(generated: str, rows: list[dict]) -> dict:
    return {
        "generatedAtUtc": generated,
        "status": "passed",
        "reference": {"x": 10.0, "y": 20.0, "z": 30.0},
        "readbacks": rows,
        "readbackCandidateCount": len(rows),
        "matchingCandidateCount": sum(1 for row in rows if row["offsetCorrectedWithinTolerance"]),
    }


class CandidateReadbackStabilityTests(unittest.TestCase):
    def test_build_summary_classifies_stable_and_intermitent_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.json"
            second = root / "second.json"
            first.write_text(
                json.dumps(
                    summary_doc(
                        "2026-05-13T00:00:00Z",
                        [
                            readback(0x5000, 0.01, value=(15.0, 25.0, 35.0), match=True),
                            readback(0x6000, 0.02, value=(12.0, 22.0, 32.0), match=True),
                        ],
                    )
                ),
                encoding="utf-8",
            )
            second.write_text(
                json.dumps(
                    summary_doc(
                        "2026-05-13T00:01:00Z",
                        [
                            readback(0x5000, 0.01, value=(15.0, 25.0, 35.0), match=True),
                            readback(0x6000, 10.0, value=(99.0, 99.0, 99.0), match=False),
                        ],
                    )
                ),
                encoding="utf-8",
            )

            result = build_summary([first, second])

        by_address = {row["addressHex"]: row for row in result["addresses"]}
        self.assertEqual(result["status"], "passed")
        self.assertEqual(by_address["0x5000"]["stability"], "stable-repeat-match")
        self.assertEqual(by_address["0x6000"]["stability"], "intermittent-or-dropped-match")

    def test_cli_writes_summaries_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.json"
            second = root / "second.json"
            out = root / "out"
            first.write_text(
                json.dumps(summary_doc("2026-05-13T00:00:00Z", [readback(0x5000, 0.01, value=(1, 2, 3), match=True)])),
                encoding="utf-8",
            )
            second.write_text(
                json.dumps(summary_doc("2026-05-13T00:01:00Z", [readback(0x5000, 0.01, value=(1, 2, 3), match=True)])),
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                code = main([str(first), str(second), "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertFalse(summary["safety"]["inputSent"])
            self.assertFalse(summary["safety"]["targetMemoryBytesRead"])
            self.assertTrue((out / "summary.md").exists())


if __name__ == "__main__":
    unittest.main()
