from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from summarize_actor_yaw_discovery import build_summary, format_markdown


SCRIPT_PATH = Path(__file__).resolve().with_name("summarize_actor_yaw_discovery.py")


class ActorYawDiscoveryReadinessTests(unittest.TestCase):
    def test_truth_like_reversible_yaw_is_ready_for_facing_proof_suite_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_search = temp_root / "candidate-search.json"
            yaw_validation = temp_root / "yaw-validation.json"
            write_json(
                candidate_search,
                {
                    "Mode": "player-orientation-candidate-search",
                    "CandidateCount": 0,
                    "PointerHopCandidateCount": 1,
                    "BestPointerHopCandidate": {
                        "Address": "0xABCDEF00",
                        "BasisPrimaryForwardOffset": "0xD4",
                        "Score": 20,
                        "RawScore": 260,
                        "LedgerPenalty": 240,
                        "LedgerRejectionReason": "stable_but_nonresponsive",
                    },
                    "PointerHopCandidates": [
                        {
                            "Address": "0xABCDEF00",
                            "BasisPrimaryForwardOffset": "0xD4",
                            "Score": 20,
                            "RawScore": 260,
                            "LedgerPenalty": 240,
                            "LedgerRejectionReason": "stable_but_nonresponsive",
                        }
                    ],
                    "Notes": ["penalizedPointerHopCandidates=1"],
                },
            )
            write_json(
                yaw_validation,
                {
                    "Mode": "actor-yaw-candidate-test",
                    "ValidationSummary": {
                        "ValidationFocus": "player-actor-yaw-discovery",
                        "CandidateCount": 1,
                        "TruthLikeCandidateCount": 1,
                        "ResponsiveCandidateCount": 1,
                        "ReversibleCandidateCount": 1,
                        "FacingPromotionAttempted": False,
                        "DownstreamFacingUse": "not-promoted-by-this-script",
                        "BestCandidate": {
                            "CandidateKey": "0xABCDEF00|0xD4",
                            "SourceAddress": "0xABCDEF00",
                            "BasisForwardOffset": "0xD4",
                            "TruthLike": True,
                            "CandidateResponsive": True,
                            "Reversible": True,
                            "YawDiscoveryStatus": "truth-like",
                        },
                    },
                },
            )

            summary = build_summary(candidate_search, yaw_validation)

            self.assertEqual("yaw-ready-for-facing-proof-suite", summary["readiness"]["status"])
            self.assertEqual("run-facing-proof-suite-before-promotion", summary["readiness"]["decision"])
            self.assertFalse(summary["readiness"]["movementAllowed"])
            self.assertFalse(summary["readiness"]["facingPromotionAllowed"])
            self.assertTrue(summary["readiness"]["noCheatEngine"])
            self.assertFalse(summary["readiness"]["writesToRiftScan"])
            self.assertEqual(1, summary["candidateSearch"]["penalizedPointerHopCandidateCount"])
            self.assertEqual("0xABCDEF00|0xD4", summary["yawValidation"]["bestCandidate"]["candidateKey"])

            markdown = format_markdown(summary)
            self.assertIn("yaw-ready-for-facing-proof-suite", markdown)
            self.assertIn("Facing promotion allowed | `False`", markdown)

    def test_candidate_search_without_yaw_validation_requires_behavior_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_search = temp_root / "candidate-search.json"
            yaw_validation = temp_root / "missing-yaw-validation.json"
            write_json(
                candidate_search,
                {
                    "Mode": "player-orientation-candidate-search",
                    "CandidateCount": 0,
                    "PointerHopCandidateCount": 1,
                    "PointerHopCandidates": [],
                },
            )

            summary = build_summary(candidate_search, yaw_validation)

            self.assertEqual("candidate-search-only", summary["readiness"]["status"])
            self.assertEqual("run-yaw-behavior-validation", summary["readiness"]["decision"])
            self.assertFalse(summary["readiness"]["movementAllowed"])
            self.assertFalse(summary["readiness"]["facingPromotionAllowed"])

    def test_missing_evidence_recommends_candidate_search(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)

            summary = build_summary(temp_root / "missing-search.json", temp_root / "missing-yaw.json")

            self.assertEqual("missing-evidence", summary["readiness"]["status"])
            self.assertEqual("run-candidate-search", summary["readiness"]["decision"])
            self.assertFalse(summary["candidateSearch"]["loaded"])
            self.assertFalse(summary["yawValidation"]["loaded"])

    def test_responsive_without_truth_like_requires_stronger_yaw_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_search = temp_root / "missing-search.json"
            yaw_validation = temp_root / "yaw-validation.json"
            write_json(
                yaw_validation,
                {
                    "Mode": "actor-yaw-candidate-test",
                    "ValidationSummary": {
                        "ValidationFocus": "player-actor-yaw-discovery",
                        "CandidateCount": 2,
                        "TruthLikeCandidateCount": 0,
                        "ResponsiveCandidateCount": 1,
                        "ReversibleCandidateCount": 0,
                        "FacingPromotionAttempted": False,
                    },
                },
            )

            summary = build_summary(candidate_search, yaw_validation)

            self.assertEqual("yaw-responsive-needs-truth-like-proof", summary["readiness"]["status"])
            self.assertEqual("collect-stronger-yaw-proof", summary["readiness"]["decision"])

    def test_stale_artifacts_add_warning_without_allowing_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_search = temp_root / "candidate-search.json"
            yaw_validation = temp_root / "yaw-validation.json"
            write_json(
                candidate_search,
                {
                    "Mode": "player-orientation-candidate-search",
                    "CandidateCount": 0,
                    "PointerHopCandidateCount": 1,
                    "PointerHopCandidates": [],
                },
            )
            write_json(
                yaw_validation,
                {
                    "Mode": "actor-yaw-candidate-test",
                    "ValidationSummary": {
                        "ValidationFocus": "player-actor-yaw-discovery",
                        "CandidateCount": 1,
                        "TruthLikeCandidateCount": 1,
                        "ResponsiveCandidateCount": 1,
                        "ReversibleCandidateCount": 1,
                        "FacingPromotionAttempted": False,
                    },
                },
            )
            stale_timestamp = datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc).timestamp()
            os.utime(candidate_search, (stale_timestamp, stale_timestamp))
            os.utime(yaw_validation, (stale_timestamp, stale_timestamp))

            summary = build_summary(
                candidate_search,
                yaw_validation,
                max_artifact_age_hours=12.0,
                now=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc),
            )

            self.assertEqual("stale-artifacts-refresh-required", summary["readiness"]["status"])
            self.assertEqual("yaw-ready-for-facing-proof-suite", summary["readiness"]["evidenceStatusBeforeFreshnessGate"])
            self.assertEqual("refresh-stale-artifacts", summary["readiness"]["decision"])
            self.assertEqual(
                "run-facing-proof-suite-before-promotion",
                summary["readiness"]["evidenceDecisionBeforeFreshnessGate"],
            )
            self.assertEqual(2, summary["artifactFreshness"]["staleArtifactCount"])
            self.assertFalse(summary["artifactFreshness"]["freshnessGatePassed"])
            self.assertGreaterEqual(len(summary["readiness"]["warnings"]), 2)
            self.assertIn("Refresh stale actor-yaw discovery artifacts", summary["readiness"]["recommendedActions"][0]["action"])
            self.assertFalse(summary["readiness"]["movementAllowed"])
            self.assertFalse(summary["readiness"]["facingPromotionAllowed"])

    def test_require_fresh_exits_nonzero_when_artifacts_are_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_search = temp_root / "candidate-search.json"
            yaw_validation = temp_root / "yaw-validation.json"
            write_json(
                candidate_search,
                {
                    "Mode": "player-orientation-candidate-search",
                    "CandidateCount": 0,
                    "PointerHopCandidateCount": 1,
                    "PointerHopCandidates": [],
                },
            )
            write_json(
                yaw_validation,
                {
                    "Mode": "actor-yaw-candidate-test",
                    "ValidationSummary": {
                        "ValidationFocus": "player-actor-yaw-discovery",
                        "CandidateCount": 1,
                        "TruthLikeCandidateCount": 0,
                        "ResponsiveCandidateCount": 0,
                        "ReversibleCandidateCount": 0,
                        "FacingPromotionAttempted": False,
                    },
                },
            )
            stale_timestamp = datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc).timestamp()
            os.utime(candidate_search, (stale_timestamp, stale_timestamp))
            os.utime(yaw_validation, (stale_timestamp, stale_timestamp))

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--candidate-search-file",
                    str(candidate_search),
                    "--yaw-validation-file",
                    str(yaw_validation),
                    "--max-artifact-age-hours",
                    "12",
                    "--require-fresh",
                    "--compact-json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(2, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("stale-artifacts-refresh-required", payload["readiness"]["status"])
            self.assertFalse(payload["artifactFreshness"]["freshnessGatePassed"])

    def test_require_fresh_exits_zero_when_age_check_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_search = temp_root / "candidate-search.json"
            yaw_validation = temp_root / "yaw-validation.json"
            write_json(
                candidate_search,
                {
                    "Mode": "player-orientation-candidate-search",
                    "CandidateCount": 0,
                    "PointerHopCandidateCount": 1,
                    "PointerHopCandidates": [],
                },
            )
            write_json(
                yaw_validation,
                {
                    "Mode": "actor-yaw-candidate-test",
                    "ValidationSummary": {
                        "ValidationFocus": "player-actor-yaw-discovery",
                        "CandidateCount": 1,
                        "TruthLikeCandidateCount": 0,
                        "ResponsiveCandidateCount": 0,
                        "ReversibleCandidateCount": 0,
                        "FacingPromotionAttempted": False,
                    },
                },
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--candidate-search-file",
                    str(candidate_search),
                    "--yaw-validation-file",
                    str(yaw_validation),
                    "--max-artifact-age-hours",
                    "0",
                    "--require-fresh",
                    "--compact-json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["artifactFreshness"]["freshnessGatePassed"])

    def test_cli_writes_durable_summary_markdown_and_latest_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_search = temp_root / "candidate-search.json"
            yaw_validation = temp_root / "yaw-validation.json"
            summary_file = temp_root / "out" / "readiness.json"
            markdown_file = temp_root / "out" / "readiness.md"
            latest_pointer_file = temp_root / "out" / "latest.json"
            riftscan_root = temp_root / "Riftscan"
            write_json(
                candidate_search,
                {
                    "Mode": "player-orientation-candidate-search",
                    "CandidateCount": 0,
                    "PointerHopCandidateCount": 1,
                    "PointerHopCandidates": [],
                },
            )
            write_json(
                yaw_validation,
                {
                    "Mode": "actor-yaw-candidate-test",
                    "ValidationSummary": {
                        "ValidationFocus": "player-actor-yaw-discovery",
                        "CandidateCount": 1,
                        "TruthLikeCandidateCount": 1,
                        "ResponsiveCandidateCount": 1,
                        "ReversibleCandidateCount": 1,
                        "FacingPromotionAttempted": False,
                    },
                },
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--candidate-search-file",
                    str(candidate_search),
                    "--yaw-validation-file",
                    str(yaw_validation),
                    "--max-artifact-age-hours",
                    "0",
                    "--summary-file",
                    str(summary_file),
                    "--write-markdown",
                    "--markdown-file",
                    str(markdown_file),
                    "--update-latest-pointer",
                    "--latest-pointer-file",
                    str(latest_pointer_file),
                    "--riftscan-root",
                    str(riftscan_root),
                    "--compact-json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            stdout_payload = json.loads(result.stdout)
            persisted = json.loads(summary_file.read_text(encoding="utf-8"))
            latest = json.loads(latest_pointer_file.read_text(encoding="utf-8"))

            self.assertTrue(markdown_file.read_text(encoding="utf-8").startswith("# Player actor-yaw discovery readiness"))
            self.assertEqual(stdout_payload["summaryFile"], str(summary_file))
            self.assertEqual(persisted["summaryFile"], str(summary_file))
            self.assertEqual(str(markdown_file), persisted["markdownFile"])
            self.assertEqual("latest-player-actor-yaw-discovery-readiness-pointer", latest["mode"])
            self.assertEqual("yaw-ready-for-facing-proof-suite", latest["status"])
            self.assertEqual("run-facing-proof-suite-before-promotion", latest["decision"])
            self.assertFalse(latest["movementAllowed"])
            self.assertFalse(latest["facingPromotionAllowed"])
            self.assertTrue(latest["noCheatEngine"])
            self.assertFalse(latest["writesToRiftScan"])
            self.assertTrue(latest["freshnessGatePassed"])
            self.assertEqual(0, latest["staleArtifactCount"])
            self.assertEqual(str(summary_file), latest["summaryFile"])
            self.assertEqual(str(markdown_file), latest["markdownFile"])

    def test_cli_refuses_to_write_summary_inside_riftscan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_search = temp_root / "candidate-search.json"
            yaw_validation = temp_root / "yaw-validation.json"
            riftscan_root = temp_root / "Riftscan"
            bad_summary_file = riftscan_root / "reports" / "bad.json"
            write_json(
                candidate_search,
                {
                    "Mode": "player-orientation-candidate-search",
                    "CandidateCount": 0,
                    "PointerHopCandidateCount": 1,
                    "PointerHopCandidates": [],
                },
            )
            write_json(
                yaw_validation,
                {
                    "Mode": "actor-yaw-candidate-test",
                    "ValidationSummary": {
                        "ValidationFocus": "player-actor-yaw-discovery",
                        "CandidateCount": 1,
                        "TruthLikeCandidateCount": 1,
                        "ResponsiveCandidateCount": 1,
                        "ReversibleCandidateCount": 1,
                        "FacingPromotionAttempted": False,
                    },
                },
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--candidate-search-file",
                    str(candidate_search),
                    "--yaw-validation-file",
                    str(yaw_validation),
                    "--summary-file",
                    str(bad_summary_file),
                    "--riftscan-root",
                    str(riftscan_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("Refusing to write actor-yaw readiness output inside RiftScan", result.stderr)
            self.assertFalse(bad_summary_file.exists())


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
