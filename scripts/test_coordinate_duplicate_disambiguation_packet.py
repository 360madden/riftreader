from __future__ import annotations

import unittest

import coordinate_duplicate_disambiguation_packet as packet


class CoordinateDuplicateDisambiguationPacketTests(unittest.TestCase):
    def test_build_candidate_rows_ranks_pointer_context(self) -> None:
        current_truth = {"bestCurrentCandidate": {"addressHex": "0x11008"}}
        passive_readback = {
            "BestReferenceMatches": [
                {
                    "CandidateId": "copy-a",
                    "CandidateAddressHex": "0x11008",
                    "ReferenceMatchesReadback": True,
                    "ReferenceMaxAbsDelta": 0.001,
                    "SourcePreviewMatchesReadback": True,
                    "StableAcrossReadbackSamples": True,
                },
                {
                    "CandidateId": "copy-b",
                    "CandidateAddressHex": "0x22008",
                    "ReferenceMatchesReadback": True,
                    "ReferenceMaxAbsDelta": 0.001,
                    "SourcePreviewMatchesReadback": True,
                    "StableAcrossReadbackSamples": True,
                },
            ]
        }
        pointer_summary = {
            "rankedTargets": [
                {"target": "0x10000", "hitCount": 10, "moduleHitCount": 0, "riftModuleHitCount": 0},
                {"target": "0x20000", "hitCount": 2, "moduleHitCount": 0, "riftModuleHitCount": 0},
            ]
        }

        rows = packet.build_candidate_rows(
            current_truth=current_truth,
            passive_readback=passive_readback,
            pointer_summary=pointer_summary,
        )

        self.assertEqual([row["addressHex"] for row in rows], ["0x11008", "0x22008"])
        self.assertEqual(rows[0]["role"], "current-truth-best")
        self.assertEqual(rows[0]["segmentBasePointerHitCount"], 10)
        self.assertEqual(rows[1]["segmentBasePointerHitCount"], 2)
        self.assertFalse(rows[0]["promotionEligible"])

    def test_finite_float_rejects_nan(self) -> None:
        self.assertIsNone(packet.finite_float("NaN"))
        self.assertIsNone(packet.finite_float(float("inf")))
        self.assertEqual(packet.finite_float("1.5"), 1.5)


if __name__ == "__main__":
    unittest.main()
