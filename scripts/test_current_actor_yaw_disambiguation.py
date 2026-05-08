from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.actor_yaw_disambiguation_validation import build_disambiguation_validation


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def valid_lead() -> dict:
    return {
        "SourceAddress": "0xABCDEF00",
        "BasisForwardOffset": "0xD4",
        "Status": "preferred-solved-lead",
        "OperationalStatus": "behavior-backed-lead",
        "CandidateDiagnostics": {
            "CandidateKey": "0xABCDEF00|0xD4",
            "ProcessId": 4242,
            "TargetWindowHandle": "0x1234",
            "RejectedControls": [
                {
                    "candidateKey": "0x0DD|0xD4",
                    "sourceAddress": "0x0DD",
                    "basisForwardOffset": "0xD4",
                    "truthLike": False,
                }
            ],
        },
        "PreviousLead": {
            "SourceAddress": "0x0DD",
            "BasisForwardOffset": "0xD4",
            "ReplacementReason": "isolated-disambiguation-control-was-responsive-only-non-reversible",
        },
    }


def valid_packet() -> dict:
    survivor = {
        "file": "C:/RiftReader/scripts/captures/validation-survivor.json",
        "candidateKey": "0xABCDEF00|0xD4",
        "sourceAddress": "0xABCDEF00",
        "basisForwardOffset": "0xD4",
        "status": "truth-like",
        "truthLikeCandidateCount": 1,
        "responsiveCandidateCount": 1,
        "reversibleCandidateCount": 1,
        "yawDeltaDegrees": -17.0,
        "reverseYawDeltaDegrees": -32.0,
        "reversibleCycleCount": 1,
        "candidateResponsive": True,
        "playerStayedMostlyStill": True,
        "truthLike": True,
        "playerCoordDeltaMagnitude": 0.0,
    }
    old_control = {
        "file": "C:/RiftReader/scripts/captures/validation-old.json",
        "candidateKey": "0x0DD|0xD4",
        "sourceAddress": "0x0DD",
        "basisForwardOffset": "0xD4",
        "status": "responsive-candidate",
        "truthLikeCandidateCount": 0,
        "responsiveCandidateCount": 1,
        "reversibleCandidateCount": 0,
        "truthLike": False,
        "candidateResponsive": True,
        "playerStayedMostlyStill": True,
        "playerCoordDeltaMagnitude": 0.0,
    }
    return {
        "schemaVersion": 1,
        "mode": "current-actor-yaw-disambiguation",
        "status": "single-survivor-promoted-to-behavior-backed-lead",
        "decision": "promoted-and-validation-passed",
        "processName": "rift_x64",
        "processId": 4242,
        "targetWindowHandle": "0x1234",
        "noCheatEngine": True,
        "movementSent": False,
        "movementAllowed": False,
        "writesToRiftScan": False,
        "savedVariablesUsedAsLiveTruth": False,
        "singleSurvivor": survivor,
        "truthLikeSurvivorCount": 1,
        "currentPromotedLeadControl": old_control,
        "candidateResults": [old_control, survivor],
        "promotionAllowed": True,
        "actorFacingPromotionApplied": True,
        "promotedLead": {
            "sourceAddress": "0xABCDEF00",
            "basisForwardOffset": "0xD4",
            "status": "preferred-solved-lead",
            "operationalStatus": "behavior-backed-lead",
            "candidateKey": "0xABCDEF00|0xD4",
        },
        "promotionValidation": {
            "readPlayerOrientation": {
                "status": "passed",
                "resolutionMode": "live-behavior-backed-lead",
                "selectedSourceAddress": "0xABCDEF00",
                "basisForwardOffset": "0xD4",
                "liveMemoryRead": True,
            },
            "captureActorOrientation": {
                "status": "passed",
                "resolutionMode": "behavior-backed-lead",
                "selectedSourceAddress": "0xABCDEF00",
                "basisForwardOffset": "0xD4",
                "liveMemoryRead": True,
            },
            "actorFacingProofSuite": {"status": "passed"},
            "targetedDotnetTests": {"status": "passed", "failedCount": 0},
        },
    }


class CurrentActorYawDisambiguationValidationTests(unittest.TestCase):
    def validate(self, packet: dict, lead: dict) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            packet_file = root / "docs" / "recovery" / "current-actor-yaw-disambiguation.json"
            lead_file = root / "scripts" / "actor-facing-behavior-backed-lead.json"
            write_json(packet_file, packet)
            write_json(lead_file, lead)
            return build_disambiguation_validation(
                packet_file=packet_file,
                lead_file=lead_file,
                repo_root=root,
            )

    def test_valid_promoted_packet_passes(self) -> None:
        result = self.validate(valid_packet(), valid_lead())
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["movementAllowed"])

    def test_current_repo_packet_passes_contract(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = build_disambiguation_validation(
            packet_file=repo_root / "docs" / "recovery" / "current-actor-yaw-disambiguation.json",
            lead_file=repo_root / "scripts" / "actor-facing-behavior-backed-lead.json",
            repo_root=repo_root,
        )
        self.assertEqual(result["status"], "pass", result["issues"])

    def test_pending_packet_fails_closed(self) -> None:
        packet = valid_packet()
        packet["status"] = "single-survivor-needs-promotion-review"
        packet["decision"] = "review-single-survivor-before-actor-facing-promotion"
        packet["actorFacingPromotionApplied"] = False
        result = self.validate(packet, valid_lead())
        self.assertEqual(result["status"], "fail")
        self.assertIn("promotion_not_completed", result["issues"])

    def test_lead_file_mismatch_fails(self) -> None:
        lead = valid_lead()
        lead["SourceAddress"] = "0xDEADBEEF"
        result = self.validate(valid_packet(), lead)
        self.assertEqual(result["status"], "fail")
        self.assertIn("lead_file_mismatch", result["issues"])

    def test_multiple_truth_like_results_fail(self) -> None:
        packet = valid_packet()
        second_truth = dict(packet["currentPromotedLeadControl"])
        second_truth["truthLike"] = True
        second_truth["truthLikeCandidateCount"] = 1
        packet["candidateResults"].append(second_truth)
        result = self.validate(packet, valid_lead())
        self.assertEqual(result["status"], "fail")
        self.assertIn("candidate_results_ambiguous", result["issues"])

    def test_promotion_validation_must_be_live_memory_read(self) -> None:
        packet = valid_packet()
        packet["promotionValidation"]["readPlayerOrientation"]["liveMemoryRead"] = False
        result = self.validate(packet, valid_lead())
        self.assertEqual(result["status"], "fail")
        self.assertIn("readPlayerOrientation_validation_failed", result["issues"])


if __name__ == "__main__":
    unittest.main()
