from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.current_truth_validator import validate_truth


def minimal_truth(artifact: str = "artifact.json") -> dict:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-current-truth",
        "updatedAtUtc": "2026-05-14T02:20:17Z",
        "status": "candidate_only_movement_blocked",
        "target": {
            "processName": "rift_x64",
            "processId": 2928,
            "targetWindowHandle": "0xC0994",
            "processStartUtc": "2026-05-13T16:17:56.208370Z",
            "moduleBase": "0x7FF71CD90000",
        },
        "liveReferenceSurface": {
            "authoritative": "ReaderBridge_RRAPICOORD1",
            "status": "usable_for_read_only_proof",
            "source": "rift-api",
            "view": "Inspect.Unit.Detail(player)",
            "savedVariablesUse": "none",
            "latestPreflight": artifact,
        },
        "movementGate": {"allowed": False, "status": "blocked", "reason": "test"},
        "bestCurrentCandidate": {
            "candidateId": "family-snapshot-hit-000001",
            "addressHex": "0x268D1FA6120",
            "candidateFile": artifact,
            "readbackSummary": artifact,
            "status": "candidate_only_not_movement_proof",
        },
        "staleOrInvalid": [{"item": "old pid", "reason": "stale"}],
        "currentBlockers": ["proof missing"],
        "canonicalArtifacts": {"machineTruth": artifact},
        "nextRecommendedAction": "continue read-only proof",
    }


class CurrentTruthValidatorTests(unittest.TestCase):
    def test_valid_truth_passes_with_existing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "artifact.json").write_text("{}", encoding="utf-8")
            result = validate_truth(minimal_truth(), repo_root=root)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["errors"], [])

    def test_savedvariables_live_reference_fails(self) -> None:
        truth = minimal_truth()
        truth["liveReferenceSurface"]["savedVariablesUse"] = "live"

        result = validate_truth(truth, repo_root=Path.cwd(), check_artifacts=False)

        self.assertEqual(result["status"], "failed")
        self.assertIn("live-reference-must-not-use-savedvariables", result["errors"])

    def test_missing_artifact_fails_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_truth(minimal_truth("missing.json"), repo_root=Path(tmp))

        self.assertEqual(result["status"], "failed")
        self.assertIn("artifact-missing:missing.json", result["errors"])

    def test_no_current_candidate_state_allows_empty_candidate_fields(self) -> None:
        truth = minimal_truth()
        truth["status"] = "no_current_candidate_movement_blocked"
        truth["bestCurrentCandidate"] = {
            "candidateId": None,
            "addressHex": None,
            "candidateFile": None,
            "readbackSummary": None,
            "status": "none_current_reacquisition_required",
        }

        result = validate_truth(truth, repo_root=Path.cwd(), check_artifacts=False)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["errors"], [])

    def test_current_blockers_may_be_empty_when_truth_is_unblocked(self) -> None:
        truth = minimal_truth()
        truth["currentBlockers"] = []

        result = validate_truth(truth, repo_root=Path.cwd(), check_artifacts=False)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
