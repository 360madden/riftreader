from __future__ import annotations

import unittest
from pathlib import Path

from rift_live_test.actor_chain_no_debug_status import BLOCKER_DIAGNOSTICS, _build_blocker_diagnostics, build_markdown, build_summary_from_documents, display_artifact_path, summarize_pointer_scan


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

    def test_build_summary_recognizes_static_resolver_candidate_without_promotion(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth={
                "target": {"processName": "rift_x64", "processId": 34176, "targetWindowHandle": "0x3D1544"},
                "staticChainStatus": {
                    "status": "promotion-review-ready-not-promoted",
                    "promotionAllowed": False,
                    "primaryCandidate": {
                        "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                        "rootModule": "rift_x64.exe",
                        "rootRva": "0x32EBC80",
                        "rootAddress": "0x7FF77E22BC80",
                        "ownerAddress": "0x278C3830010",
                        "coordinateAddress": "0x278C3830330",
                        "restartRelogSurvived": True,
                    },
                    "latestApiNowValidation": {"status": "passed"},
                    "latestFreshApiSourceRefreshAttempt": {"status": "blocked"},
                    "latestExtendedStaticRootDiscovery": {"status": "passed-candidate-only-not-promoted"},
                },
            },
            proof={"status": "current-target-proofonly-passed", "riftscanCandidateSource": {"sourceAbsoluteAddressHex": "0x1"}},
            candidate_readback=None,
            root_sweep=None,
            root_family=None,
            pointer_scans=[
                (
                    "scan.json",
                    {
                        "status": "passed",
                        "counts": {"scannedTargetCount": 20},
                        "rankedTargets": [{"hitCount": 20, "moduleHitCount": 1, "riftModuleHitCount": 1}],
                    },
                )
            ],
            exhaustion_reports=[],
            missing_artifacts=[],
        )

        self.assertEqual(summary["verdict"], "static-resolver-candidate-found-not-promoted")
        self.assertTrue(summary["promotionGates"]["staticResolverCandidateFound"])
        self.assertFalse(summary["promotionGates"]["staticResolverPromoted"])
        self.assertTrue(summary["promotionGates"]["restartValidated"])
        self.assertEqual(summary["staticResolver"]["rootRva"], "0x32EBC80")
        self.assertIn("static-resolver-candidate-not-promoted", summary["blockers"])
        self.assertNotIn("actor-candidate-readback-not-passed", summary["blockers"])
        self.assertIn("restore a fresh API/reference source", summary["next"]["recommendedAction"])

    def test_blocker_diagnostics_maps_known_blockers(self) -> None:
        blockers = [
            "current-proof-anchor-not-passed",
            "no-static-resolver-promoted",
            "blocked-no-debugger-access-provenance",
            "no-debug-root-lanes-exhausted",
        ]
        diagnostics = _build_blocker_diagnostics(blockers)
        self.assertEqual(len(diagnostics), 4)
        prefixes = [d["blocker"] for d in diagnostics]
        self.assertIn("current-proof-anchor-not-passed", prefixes)
        self.assertIn("no-static-resolver-promoted", prefixes)
        for diag in diagnostics:
            self.assertIn("meaning", diag)
            self.assertIn("action", diag)
            self.assertTrue(len(diag["meaning"]) > 10, f"meaning too short for {diag['blocker']}")
            self.assertTrue(len(diag["action"]) > 10, f"action too short for {diag['blocker']}")

    def test_blocker_diagnostics_deduplicates_same_prefix(self) -> None:
        blockers = [
            "artifact-missing:path/a.json",
            "artifact-missing:path/b.json",
            "current-proof-anchor-not-passed",
        ]
        diagnostics = _build_blocker_diagnostics(blockers)
        # artifact-missing should only appear once (deduped by prefix)
        self.assertEqual(len(diagnostics), 2)
        prefixes = [d["blocker"] for d in diagnostics]
        self.assertIn("current-proof-anchor-not-passed", prefixes)
        self.assertTrue(any(p.startswith("artifact-missing") for p in prefixes))

    def test_blocker_diagnostics_unknown_blocker_fallback(self) -> None:
        blockers = ["some-unknown-blocker-that-doesnt-match"]
        diagnostics = _build_blocker_diagnostics(blockers)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["blocker"], "some-unknown-blocker-that-doesnt-match")
        self.assertIn("Unrecognized", diagnostics[0]["meaning"])

    def test_all_blocker_diagnostic_keys_have_diagnostics(self) -> None:
        # Every key in BLOCKER_DIAGNOSTICS must have meaning and action
        for key, diag in BLOCKER_DIAGNOSTICS.items():
            with self.subTest(key=key):
                self.assertIn("meaning", diag)
                self.assertIn("action", diag)
                self.assertTrue(isinstance(diag["meaning"], str) and len(diag["meaning"]) > 10)
                self.assertTrue(isinstance(diag["action"], str) and len(diag["action"]) > 10)

    def test_build_summary_includes_blocker_diagnostics(self) -> None:
        summary = build_summary_from_documents(
            repo_root=Path("."),
            truth={
                "target": {"processName": "rift_x64", "processId": 67680, "targetWindowHandle": "0x120CBE"},
                "staticChainStatus": {"blockers": ["blocked-no-debugger-access-provenance"]},
            },
            proof={"status": "current-target-proofonly-passed", "riftscanCandidateSource": {"sourceAbsoluteAddressHex": "0x1"}},
            candidate_readback=None,
            root_sweep=None,
            root_family=None,
            pointer_scans=[("scan.json", {"status": "passed", "counts": {"scannedTargetCount": 1}, "rankedTargets": [{"hitCount": 0, "moduleHitCount": 0, "riftModuleHitCount": 0}]})],
            exhaustion_reports=[],
            missing_artifacts=[],
        )
        self.assertIn("blockerDiagnostics", summary)
        diagnostics = summary["blockerDiagnostics"]
        self.assertTrue(isinstance(diagnostics, list))
        self.assertGreater(len(diagnostics), 0)
        self.assertTrue(any(d["blocker"] == "no-static-resolver-promoted" for d in diagnostics))

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
