#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_proof_replay as replay  # noqa: E402
from riftreader_workflow import mcp_workflow_state as state  # noqa: E402


def write_json(path: Path, payload: dict[str, object], mtime: int = 1_800_000_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def valid_proof() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "connectionMode": "openai-secure-mcp-tunnel",
        "publicMcpUrl": "https://example.openai-mcp-tunnel.invalid/mcp",
        "chatgptRegistrationSucceeded": True,
        "toolCount": 10,
        "toolOutputSchemasPresent": True,
        "toolOutputSchemaCount": 10,
        "health": {"repoRoot": ".", "repoName": "RiftReader", "absoluteRepoRootExposed": False},
        "templateFetched": True,
        "submitPackageProposalSucceeded": True,
        "inboxId": "proof-id",
        "listInboxSawInboxId": True,
        "createPackageDraftSucceeded": True,
        "draftId": "proof-id",
        "reviewLatestPackageDraftSucceeded": True,
        "reviewLatestPackageDraftReadOnly": True,
        "dryRunDiffPreviewOk": True,
        "dryRunDiffPreviewArtifactUnderPackageIntake": True,
        "dryRunDiffPreviewBoundedBytes": True,
        "dryRunDiffPreviewTextLength": 195,
        "dryRunDiffPreviewTruncated": False,
        "dryRunSucceeded": True,
    }


class McpProofReplayTests(unittest.TestCase):
    def test_self_test_passes_without_chatgpt_or_tunnel(self) -> None:
        payload = replay.self_test()

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])

    def test_local_artifact_consistency_passes_for_matching_inbox_draft_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = valid_proof()
            write_json(
                root / state.INBOX_ROOT / "proof-id" / "metadata.json",
                {
                    "kind": "riftreader-local-inbox-metadata",
                    "inboxId": "proof-id",
                    "messageKind": "package-proposal",
                    "applied": False,
                    "executed": False,
                },
            )
            write_json(
                root / state.DRAFT_ROOT / "proof-id" / "summary.json",
                {
                    "kind": "riftreader-local-artifact-bridge-inbox-package-draft",
                    "inboxId": "proof-id",
                    "status": "created",
                    "ok": True,
                    "safety": {"noApplyExecute": True, "noRepoTargetWrites": True, "noGitMutation": True},
                },
            )
            write_json(
                root / state.PACKAGE_INTAKE_ROOT / "run" / "compact-package-intake-summary.json",
                {
                    "kind": "riftreader-package-intake-compact-summary",
                    "status": "passed",
                    "dryRun": True,
                    "packagePath": str(root / state.DRAFT_ROOT / "proof-id" / "package"),
                    "changedFileCount": 1,
                    "artifacts": {"diff": str(state.PACKAGE_INTAKE_ROOT / "run" / "package.diff")},
                },
            )
            (root / state.PACKAGE_INTAKE_ROOT / "run" / "package.diff").write_text("+preview\n", encoding="utf-8")

            payload = replay.local_artifact_consistency(root, proof)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["checks"]["dryRun"]["matchCount"], 1)
        self.assertTrue(payload["checks"]["dryRun"]["latest"]["diff"]["underPackageIntake"])

    def test_local_artifact_consistency_blocks_unsafe_draft_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = valid_proof()
            write_json(
                root / state.DRAFT_ROOT / "proof-id" / "summary.json",
                {
                    "kind": "riftreader-local-artifact-bridge-inbox-package-draft",
                    "inboxId": "proof-id",
                    "status": "created",
                    "ok": True,
                    "safety": {"noApplyExecute": False, "noRepoTargetWrites": True, "noGitMutation": True},
                },
            )

            payload = replay.local_artifact_consistency(root, proof)

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["ok"])
        self.assertTrue(any("noApplyExecute" in blocker for blocker in payload["blockers"]))

    def test_local_artifact_consistency_blocks_diff_outside_package_intake_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = valid_proof()
            write_json(
                root / state.PACKAGE_INTAKE_ROOT / "run" / "compact-package-intake-summary.json",
                {
                    "kind": "riftreader-package-intake-compact-summary",
                    "status": "passed",
                    "dryRun": True,
                    "packagePath": str(root / state.DRAFT_ROOT / "proof-id" / "package"),
                    "changedFileCount": 1,
                    "artifacts": {"diff": "docs/unsafe.diff"},
                },
            )

            payload = replay.local_artifact_consistency(root, proof)

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["ok"])
        self.assertIn("dry-run-diff-artifact-not-under-package-intake:docs/unsafe.diff", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
