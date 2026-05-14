from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.current_pid_family_neighborhood_inspector import (
    inspect_neighborhood_bytes,
    known_candidate_addresses,
    load_offset_profiles,
    main,
    synthetic_candidate_doc,
    synthetic_memory,
    synthetic_readback_doc,
)


class CurrentPidFamilyNeighborhoodInspectorTests(unittest.TestCase):
    def test_load_offset_profiles_from_readback_summary(self) -> None:
        profiles = load_offset_profiles(synthetic_readback_doc())

        self.assertEqual(len(profiles), 2)
        self.assertEqual(profiles[0]["candidateId"], "low")
        self.assertEqual(profiles[0]["averageOffset"]["x"], 5.0)

    def test_load_offset_profiles_from_current_readback_summary(self) -> None:
        reference = {"x": 100.0, "y": 200.0, "z": 300.0}
        profiles = load_offset_profiles(
            {
                "ReferenceCoordinate": reference,
                "CandidateReadbacks": [
                    {
                        "CandidateId": "current",
                        "CandidateAddressHex": "0x2000",
                        "DecodedSamples": [
                            {"X": 99.5, "Y": 199.0, "Z": 299.25},
                            {"X": 99.5, "Y": 199.0, "Z": 299.25},
                        ],
                    }
                ],
            },
            reference,
        )

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["candidateId"], "current")
        self.assertEqual(profiles[0]["sourceAddress"], "0x2000")
        self.assertEqual(profiles[0]["averageOffset"], {"x": 0.5, "y": 1.0, "z": 0.75})

    def test_known_candidate_addresses_accepts_import_candidate_schema(self) -> None:
        known = known_candidate_addresses(
            {
                "candidates": [
                    {
                        "candidate_id": "family-snapshot-hit-000001",
                        "absolute_address_hex": "0x3000",
                        "family_base_hex": "0x3000",
                    }
                ]
            }
        )

        self.assertEqual(known[0x3000]["candidateId"], "family-snapshot-hit-000001")
        self.assertEqual(known[0x3000]["familyBase"], "0x3000")

    def test_inspect_neighborhood_finds_offset_corrected_hits(self) -> None:
        base, data = synthetic_memory()
        profiles = load_offset_profiles(synthetic_readback_doc())
        known = {0x1000: {"candidateId": "low"}, 0x1010: {"candidateId": "high"}}

        hits = inspect_neighborhood_bytes(
            data=data,
            base_address=base,
            reference={"x": 100.0, "y": 200.0, "z": 300.0},
            profiles=profiles,
            known_addresses=known,
            stride=4,
            tolerance=0.1,
            max_hits=10,
        )

        self.assertEqual([hit["address"] for hit in hits], ["0x1000", "0x1010"])
        self.assertEqual(hits[0]["knownCandidate"]["candidateId"], "low")
        self.assertEqual(hits[1]["knownCandidate"]["candidateId"], "high")

    def test_self_test_writes_summary_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "inspect"
            with redirect_stdout(StringIO()):
                code = main(["--self-test", "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["hitCount"], 2)
            self.assertFalse(summary["safety"]["x64dbgLaunched"])
            self.assertFalse(summary["safety"]["inputSent"])
            self.assertFalse(summary["safety"]["targetMemoryBytesRead"])


if __name__ == "__main__":
    unittest.main()
