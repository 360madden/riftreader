#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import postpatch_profile  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


class PostpatchProfileTests(unittest.TestCase):
    def test_old_root_null_blocks_tracked_promoted_truth_but_keeps_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current_truth = {
                "schemaVersion": 1,
                "kind": "riftreader-current-truth",
                "updatedAtUtc": "2026-06-02T04:13:42Z",
                "status": "current_pid_12664_static_readback_and_api_now_current",
                "target": {
                    "processName": "rift_x64",
                    "processId": 12664,
                    "targetWindowHandle": "0x205146C",
                    "processStartUtc": "2026-06-01T17:19:45Z",
                    "moduleBase": "0x7FF6EE5D0000",
                    "moduleFileName": r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe",
                    "lastVerifiedUtc": "2026-06-02T04:13:12Z",
                },
                "movementGate": {"allowed": True, "status": "allowed"},
                "bestCurrentCandidate": {
                    "candidateId": "old-root",
                    "classification": "promoted-static-player-coordinate-resolver",
                    "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                    "rootRva": "0x32EBC80",
                    "promotionEligible": True,
                    "reacquiredAfterReboot": True,
                    "status": "promoted",
                },
            }
            recovery_doc = """
            `[rift_x64+0x32EBC80] == 0x0`

            Best new candidate:
            `[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30`
            """
            current_truth_path = root / "docs" / "recovery" / "current-truth.json"
            recovery_path = root / "docs" / "recovery" / "post-update-pointer-chain-recovery-plan-2026-06-02.md"
            write_json(current_truth_path, current_truth)
            write_text(recovery_path, recovery_doc)

            summary = postpatch_profile.build_postpatch_profile(
                root,
                manifest_path=root / "missing-manifest64.txt",
                binary_path=root / "missing-rift_x64.exe",
                current_truth_path=current_truth_path,
                recovery_plan_path=recovery_path,
            )

        self.assertEqual("blocked-safe", summary["status"])
        self.assertIn("tracked-root-has-postupdate-null-evidence:0x32EBC80", summary["blockers"])
        stale = summary["staleTruthReport"]
        self.assertTrue(stale["consumerPolicy"]["navigationConsumersBlocked"])
        candidate = summary["candidateResolverProfile"]["bestCandidate"]
        self.assertEqual("[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30", candidate["chain"])
        self.assertTrue(candidate["candidateOnly"])
        self.assertFalse(summary["candidateResolverProfile"]["promotion"]["allowed"])
        self.assertTrue(summary["movementProofPlanTemplate"]["approval"]["explicitMovementApprovalRequired"])
        self.assertFalse(summary["movementProofPlanTemplate"]["approval"]["consumerMovementEnabled"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["proofPromotion"])

    def test_missing_local_build_files_is_warning_not_failure_when_candidate_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current_truth_path = root / "docs" / "recovery" / "current-truth.json"
            recovery_path = root / "docs" / "recovery" / "post-update-pointer-chain-recovery-plan-2026-06-02.md"
            write_json(
                current_truth_path,
                {
                    "status": "candidate-only",
                    "target": {"processName": "rift_x64"},
                    "bestCurrentCandidate": {
                        "chain": "[rift_x64+0x32DD7E8]+0x80/+0x28",
                        "rootRva": "0x32DD7E8",
                    },
                },
            )
            write_text(recovery_path, "`[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30`")

            summary = postpatch_profile.build_postpatch_profile(
                root,
                manifest_path=root / "missing-manifest64.txt",
                binary_path=root / "missing-rift_x64.exe",
                current_truth_path=current_truth_path,
                recovery_plan_path=recovery_path,
            )

        self.assertEqual("passed", summary["status"])
        self.assertEqual("local-build-files-not-found", summary["buildFingerprint"]["status"])
        self.assertIn("build-fingerprint-local-build-files-not-found", summary["warnings"])
        self.assertEqual("candidate-profile-ready", summary["candidateResolverProfile"]["status"])

    def test_write_artifacts_uses_ignored_local_output_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = {
                "generatedAtUtc": "2026-06-30T00:00:00Z",
                "status": "passed",
                "verdict": "postpatch-phase1-phase2-profile-ready",
                "buildFingerprint": {
                    "status": "local-build-files-not-found",
                    "manifest": {"path": "manifest64.txt", "exists": False},
                    "binary": {"path": "rift_x64.exe", "exists": False},
                },
                "staleTruthReport": {"status": "no-stale-truth-evidence-detected", "blockers": [], "warnings": []},
                "candidateResolverProfile": {
                    "bestCandidate": {
                        "chain": "[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30",
                        "rootRva": "0x32DD7E8",
                        "role": "coordinate",
                        "candidateOnly": True,
                        "promotionAllowed": False,
                    }
                },
                "movementProofPlanTemplate": {"status": "template-ready"},
                "safety": {"movementSent": False, "gitMutation": False},
            }

            artifacts = postpatch_profile.write_artifacts(
                root,
                summary,
                Path(".riftreader-local") / "postpatch-profile",
            )

        self.assertIn(".riftreader-local\\postpatch-profile", artifacts["summaryJson"])
        self.assertTrue((root / artifacts["summaryJson"]).is_file())
        self.assertTrue((root / ".riftreader-local" / "postpatch-profile" / "latest-run.txt").is_file())


if __name__ == "__main__":
    unittest.main()
