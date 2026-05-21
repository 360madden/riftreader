from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from rift_live_test.coordinate_candidate_semantic_classifier import (
    build_summary,
    classify_candidate,
    tracking_summary,
)
from rift_live_test.reports import write_json


class CoordinateCandidateSemanticClassifierTests(unittest.TestCase):
    def test_tracking_summary_detects_stable_y_offset(self) -> None:
        samples = [
            {"api": {"x": 10.0, "y": 20.0, "z": 30.0}, "memory": {}, "delta": {"x": 0.01, "y": 1.54, "z": -0.01}},
            {"api": {"x": 15.0, "y": 18.0, "z": 35.0}, "memory": {}, "delta": {"x": -0.02, "y": 1.55, "z": 0.02}},
        ]

        summary = tracking_summary(samples, axis_tolerance=0.25, stable_offset_range=0.1)

        self.assertTrue(summary["xTracksApi"])
        self.assertFalse(summary["yTracksApi"])
        self.assertTrue(summary["zTracksApi"])
        self.assertTrue(summary["stableYOffset"])
        self.assertEqual(summary["classificationHint"], "xz-tracks-stable-y-offset")

    def test_classify_api_buffer_wins_on_player_position_context(self) -> None:
        classification, reasons, promotion = classify_candidate(
            tracking={"xTracksApi": True, "zTracksApi": True, "stableYOffset": True},
            root_signature={"completeOwnerModuleFieldSignature": True, "matchedFieldCount": 5},
            context_text="... playerPosition ...",
        )

        self.assertEqual(classification, "api-buffer-coordinate-source")
        self.assertIn("context-contains-playerPosition", reasons)
        self.assertFalse(promotion)

    def test_classify_actor_like_offset_candidate(self) -> None:
        classification, reasons, promotion = classify_candidate(
            tracking={"xTracksApi": True, "yTracksApi": False, "zTracksApi": True, "stableYOffset": True},
            root_signature={"completeOwnerModuleFieldSignature": True, "matchedFieldCount": 5},
            context_text="binary structure",
        )

        self.assertEqual(classification, "actor-like-offset-coordinate-candidate")
        self.assertIn("complete-owner-module-field-signature", reasons)
        self.assertFalse(promotion)

    def test_build_summary_extracts_pose_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pose_summary = root / "pose.json"
            root_sweep = root / "root.json"
            neighborhood = root / "neighborhood.json"
            family = root / "family.json"
            write_json(
                pose_summary,
                {
                    "poseResults": [
                        {
                            "poseIndex": 1,
                            "poseName": "pose-01",
                            "reference": {"Coordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0}},
                            "referenceMatches": [
                                {
                                    "CandidateId": "c1",
                                    "CandidateAddressHex": "0x1000",
                                    "FirstDecodedSample": {"X": 1.01, "Y": 3.54, "Z": 3.01},
                                }
                            ],
                        },
                        {
                            "poseIndex": 2,
                            "poseName": "pose-02",
                            "reference": {"Coordinate": {"X": 4.0, "Y": 2.5, "Z": 6.0}},
                            "referenceMatches": [
                                {
                                    "CandidateId": "c1",
                                    "CandidateAddressHex": "0x1000",
                                    "FirstDecodedSample": {"X": 4.02, "Y": 4.05, "Z": 5.98},
                                }
                            ],
                        },
                    ]
                },
            )
            write_json(
                root_sweep,
                {
                    "topOwnerFieldCandidate": {
                        "scoreReasons": ["complete-owner-module-field-signature"],
                        "fieldMatches": [
                            {"matched": True},
                            {"matched": True},
                            {"matched": True},
                            {"matched": True},
                            {"matched": True},
                        ],
                    }
                },
            )
            write_json(neighborhood, {"analysis": {"ownerWindow": []}})
            write_json(family, {"contextKindCounts": {}})

            summary = build_summary(
                Namespace(
                    candidate_id="c1",
                    candidate_address="0x1000",
                    pose_summary=pose_summary,
                    neighborhood_summary=neighborhood,
                    root_sweep_summary=root_sweep,
                    family_classifier_summary=family,
                    axis_tolerance=0.25,
                    stable_offset_range=0.1,
                )
            )

        self.assertEqual(summary["candidate"]["classification"], "actor-like-offset-coordinate-candidate")
        self.assertEqual(summary["tracking"]["sampleCount"], 2)


if __name__ == "__main__":
    unittest.main()
