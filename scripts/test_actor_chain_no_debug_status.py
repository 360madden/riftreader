from __future__ import annotations

import unittest
from pathlib import Path

from rift_live_test.actor_chain_no_debug_status import build_markdown, build_summary_from_documents, display_artifact_path, summarize_pointer_scan


class ActorChainNoDebugStatusTests(unittest.TestCase):
    def test_summarize_pointer_scan_counts_hits(self) -> None:
        result = summarize_pointer_scan(
            "scan.json",
            {
                "status": "passed",
                "counts": {"scannedTargetCount": 2, "queuedTargetCount": 2},
                "rankedTargets": [
                    {"hitCount": 1, "moduleHitCount": 0, "riftModuleHitCount": 0},
                    {"hitCount": 0, "moduleHitCount": 0, "riftModuleHitCount": 0},
                ],
            },
        )

        self.assertEqual(result["targetsWithHits"], 1)
        self.assertEqual(result["totalHits"], 1)
        self.assertEqual(result["moduleHitCount"], 0)

    def test_display_artifact_path_disambiguates_summary_json(self) -> None:
        self.assertEqual(
            display_artifact_path(r"C:\RIFT MODDING\RiftReader\scripts\captures\pointer-family-scan-20260521-162245-598545\summary.json"),
            "pointer-family-scan-20260521-162245-598545/summary.json",
        )

    def test_build_summary_blocks_promotion_when_no_static_resolver(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth={
                "target": {"processName": "rift_x64", "processId": 67680, "targetWindowHandle": "0x120CBE"},
                "staticChainStatus": {"blockers": ["blocked-no-debugger-access-provenance"]},
            },
            proof={"status": "current-target-proofonly-passed", "riftscanCandidateSource": {"sourceAbsoluteAddressHex": "0x1"}},
            candidate_readback={
                "status": "passed",
                "bestReadback": {
                    "candidateId": "api-family-hit-000001",
                    "addressHex": "0x2",
                    "classification": "offset-corrected-current-coordinate-candidate",
                    "offsetCorrectedMaxAbsDelta": 0.01,
                    "truthReadiness": "candidate_only_not_movement_proof",
                },
            },
            root_sweep={"topOwnerFieldCandidate": {"score": 285, "ownerBase": "0x10", "coordPointerStorage": "0x20"}},
            root_family={"counts": {"ownerFamilyCount": 4, "priorityParentLeadCount": 1}},
            pointer_scans=[("scan.json", {"status": "passed", "counts": {"scannedTargetCount": 1}, "rankedTargets": [{"hitCount": 0, "moduleHitCount": 0, "riftModuleHitCount": 0}]})],
            exhaustion_reports=[],
            missing_artifacts=[],
        )

        self.assertEqual(summary["verdict"], "candidate-only-no-debug-root-blocked")
        self.assertFalse(summary["promotionGates"]["promotionAllowed"])
        self.assertIn("no-static-resolver-promoted", summary["blockers"])
        self.assertIn("no-debug-root-lanes-exhausted", summary["blockers"])

    def test_build_markdown_includes_scan_context_and_next_action(self) -> None:
        markdown = build_markdown(
            {
                "status": "passed",
                "verdict": "candidate-only-no-debug-root-blocked",
                "actorCandidate": {"candidateId": "api-family-hit-000001", "addressHex": "0x2"},
                "promotionGates": {},
                "noDebugRootSearch": {
                    "totalModuleHitCount": 0,
                    "totalRiftModuleHitCount": 0,
                    "noDebugRootLanesExhausted": True,
                    "pointerScans": [
                        {
                            "path": r"C:\RIFT MODDING\RiftReader\scripts\captures\pointer-family-scan-20260521-162245-598545\summary.json",
                            "scannedTargetCount": 6,
                            "totalHits": 3,
                            "moduleHitCount": 0,
                            "riftModuleHitCount": 0,
                        }
                    ],
                },
                "next": {"recommendedAction": "Keep the actor chain candidate-only."},
            }
        )

        self.assertIn("pointer-family-scan-20260521-162245-598545/summary.json", markdown)
        self.assertIn("## Recommended next action", markdown)


if __name__ == "__main__":
    unittest.main()
