#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_workflow_state as state  # noqa: E402
from riftreader_workflow import chatgpt_trial_recorder as recorder  # noqa: E402


def make_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, object], mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def write_transport_artifacts(root: Path) -> None:
    base = root / state.TRANSPORT_SMOKE_ROOT
    write_json(
        base / "20260519T010000Z-trial-readiness.json",
        {"kind": "riftreader-chatgpt-mcp-trial-readiness", "status": "passed", "ok": True, "blockers": []},
        1_800_000_000,
    )
    write_json(
        base / "20260519T010100Z-proposal-transport-smoke.json",
        {
            "kind": "riftreader-chatgpt-mcp-proposal-transport-smoke",
            "status": "passed",
            "ok": True,
            "client": {"submitPackageProposalStructuredContent": {"inboxId": "inbox-1"}},
            "safety": {"serverStopped": True, "proposalSubmitWritesLocalInboxOnly": True},
        },
        1_800_000_010,
    )
    write_json(
        base / "20260519T010200Z-cloudflare-tunnel-smoke.json",
        {
            "kind": "riftreader-chatgpt-mcp-cloudflare-tunnel-smoke",
            "status": "passed",
            "ok": True,
            "publicMcpUrl": "https://example.trycloudflare.com/mcp",
            "safety": {"serverStopped": True, "publicTunnelStopped": True},
        },
        1_800_000_020,
    )
    write_json(
        base / "20260519T010300Z-chatgpt-trial-session-ready.json",
        {
            "kind": "riftreader-chatgpt-mcp-chatgpt-trial-session-ready",
            "status": "ready",
            "ok": True,
            "publicMcpUrl": "https://ready.trycloudflare.com/mcp",
        },
        1_800_000_030,
    )
    write_json(
        base / "20260519T010400Z-chatgpt-trial-session.json",
        {
            "kind": "riftreader-chatgpt-mcp-chatgpt-trial-session",
            "status": "passed",
            "ok": True,
            "publicMcpUrl": "https://final.trycloudflare.com/mcp",
            "safety": {"serverStopped": True, "publicTunnelStopped": True},
        },
        1_800_000_040,
    )


class McpWorkflowStateTests(unittest.TestCase):
    def test_empty_artifact_roots_fail_closed_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = state.build_mcp_workflow_state(root)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("latest-readiness-not-passed", payload["blockers"])
        self.assertIn("latest-proposal-smoke-not-passed", payload["blockers"])
        self.assertEqual(payload["counts"]["readiness"], 0)
        self.assertEqual(payload["latestArtifacts"]["readiness"], None)
        self.assertEqual(payload["recommendedNextAction"]["key"], "mcp-trial-readiness")
        self.assertTrue(payload["safety"]["readOnlyArtifactDiscovery"])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])

    def test_discovers_current_artifact_shapes_and_latest_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_transport_artifacts(root)
            write_json(
                root / state.INBOX_ROOT / "20260519T010500Z-abc" / "metadata.json",
                {
                    "kind": "riftreader-local-inbox-metadata",
                    "inboxId": "20260519T010500Z-abc",
                    "messageKind": "package-proposal",
                },
                1_800_000_050,
            )
            write_json(
                root / state.DRAFT_ROOT / "20260519T010600Z-def" / "summary.json",
                {
                    "kind": "riftreader-local-artifact-bridge-inbox-package-draft",
                    "status": "created",
                    "ok": True,
                    "inboxId": "20260519T010500Z-abc",
                    "packageName": "Desktop ChatGPT proposed patch",
                },
                1_800_000_060,
            )
            write_json(
                root / state.PACKAGE_INTAKE_ROOT / "20260519-010700Z" / "compact-package-intake-summary.json",
                {
                    "kind": "riftreader-package-intake-compact-summary",
                    "status": "passed",
                    "dryRun": True,
                    "changedFileCount": 1,
                    "blockers": [],
                },
                1_800_000_070,
            )
            write_json(
                root / state.ACTUAL_CLIENT_PROOF_ROOT / "20260519-010800Z" / "proof.json",
                {
                    "kind": "riftreader-chatgpt-actual-client-proof",
                    "status": "passed",
                    "ok": True,
                    "proof": {
                        "connectionMode": "openai-secure-mcp-tunnel",
                        "chatgptRegistrationSucceeded": True,
                        "templateFetched": True,
                        "submitPackageProposalSucceeded": True,
                        "listInboxSawInboxId": True,
                        "createPackageDraftSucceeded": True,
                        "reviewLatestPackageDraftSucceeded": True,
                        "reviewLatestPackageDraftReadOnly": True,
                        "dryRunSucceeded": True,
                        "dryRunDiffPreviewOk": True,
                        "dryRunDiffPreviewArtifactUnderPackageIntake": True,
                        "dryRunDiffPreviewBoundedBytes": True,
                        "dryRunDiffPreviewTextLength": 195,
                        "dryRunDiffPreviewTruncated": False,
                        "applyLatestPackageDraftWithoutApprovalBlocked": True,
                        "applyLatestPackageDraftWithoutApprovalBlockers": ["APPLY_APPROVAL_MISSING"],
                        "applyLatestPackageDraftWithoutApprovalApplied": False,
                        "publicMcpUrl": "https://client.trycloudflare.com/mcp",
                        "toolCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                        "toolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
                        "toolOutputSchemasPresent": True,
                        "toolOutputSchemaCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                        "toolOutputSchemaToolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
                        "inboxId": "20260519T010500Z-abc",
                        "draftId": "20260519T010600Z-def",
                    },
                    "blockers": [],
                },
                1_800_000_080,
            )

            payload = state.build_mcp_workflow_state(root)

        latest = payload["latestArtifacts"]
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(latest["readiness"]["status"], "passed")
        self.assertEqual(latest["proposal-smoke"]["inboxId"], "inbox-1")
        self.assertEqual(latest["cloudflare-smoke"]["publicMcpUrl"], "https://example.trycloudflare.com/mcp")
        self.assertTrue(latest["cloudflare-smoke"]["serverStopped"])
        self.assertTrue(latest["cloudflare-smoke"]["publicTunnelStopped"])
        self.assertEqual(latest["trial-session"]["publicMcpUrl"], "https://final.trycloudflare.com/mcp")
        self.assertEqual(latest["inbox"]["status"], "stored")
        self.assertTrue(latest["inbox"]["ok"])
        self.assertEqual(latest["draft"]["draftId"], "20260519T010600Z-def")
        self.assertTrue(latest["dry-run"]["dryRun"])
        self.assertEqual(latest["actual-client-proof"]["toolCount"], recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(latest["actual-client-proof"]["toolNames"], list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES))
        self.assertTrue(latest["actual-client-proof"]["toolOutputSchemasPresent"])
        self.assertEqual(latest["actual-client-proof"]["toolOutputSchemaCount"], recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(latest["actual-client-proof"]["toolOutputSchemaToolNames"], list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES))
        self.assertEqual(latest["actual-client-proof"]["connectionMode"], "openai-secure-mcp-tunnel")
        self.assertTrue(latest["actual-client-proof"]["chatGptRegistrationSucceeded"])
        self.assertTrue(latest["actual-client-proof"]["templateFetched"])
        self.assertTrue(latest["actual-client-proof"]["submitPackageProposalSucceeded"])
        self.assertTrue(latest["actual-client-proof"]["listInboxSawInboxId"])
        self.assertTrue(latest["actual-client-proof"]["createPackageDraftSucceeded"])
        self.assertTrue(latest["actual-client-proof"]["reviewLatestPackageDraftSucceeded"])
        self.assertTrue(latest["actual-client-proof"]["reviewLatestPackageDraftReadOnly"])
        self.assertTrue(latest["actual-client-proof"]["dryRunSucceeded"])
        self.assertTrue(latest["actual-client-proof"]["dryRunDiffPreviewOk"])
        self.assertTrue(latest["actual-client-proof"]["dryRunDiffPreviewArtifactUnderPackageIntake"])
        self.assertTrue(latest["actual-client-proof"]["dryRunDiffPreviewBoundedBytes"])
        self.assertEqual(latest["actual-client-proof"]["dryRunDiffPreviewTextLength"], 195)
        self.assertFalse(latest["actual-client-proof"]["dryRunDiffPreviewTruncated"])
        self.assertTrue(latest["actual-client-proof"]["applyLatestPackageDraftWithoutApprovalBlocked"])
        self.assertEqual(
            latest["actual-client-proof"]["applyLatestPackageDraftWithoutApprovalBlockers"],
            ["APPLY_APPROVAL_MISSING"],
        )
        self.assertFalse(latest["actual-client-proof"]["applyLatestPackageDraftWithoutApprovalApplied"])

    def test_marks_self_test_artifacts_and_expired_ephemeral_public_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_json(
                root / state.TRANSPORT_SMOKE_ROOT / "20260519T010000Z-cloudflare-tunnel-smoke.json",
                {
                    "kind": "riftreader-chatgpt-mcp-cloudflare-tunnel-smoke",
                    "status": "passed",
                    "ok": True,
                    "publicMcpUrl": "https://example.trycloudflare.com/mcp",
                    "safety": {"publicTunnelStopped": True},
                },
                1_800_000_000,
            )
            write_json(
                root / state.DRAFT_ROOT / "20260519T010100Z-selftest" / "summary.json",
                {
                    "kind": "riftreader-local-artifact-bridge-inbox-package-draft",
                    "status": "created",
                    "ok": True,
                    "messageTitle": "RiftReader MCP self-test package proposal",
                    "messageMetadata": {"selfTest": True},
                },
                1_800_000_010,
            )

            payload = state.build_mcp_workflow_state(root)

        self.assertTrue(payload["latestArtifacts"]["cloudflare-smoke"]["publicUrlExpectedExpired"])
        self.assertTrue(payload["latestArtifacts"]["draft"]["selfTest"])
        self.assertEqual(payload["latestArtifacts"]["draft"]["origin"], "self-test")
        self.assertTrue(any("ephemeral-public-url-expected-expired:cloudflare-smoke" in item for item in payload["warnings"]))
        self.assertTrue(any("latest-draft-is-self-test" in item for item in payload["warnings"]))

    def test_malformed_json_is_reported_as_warning_and_failed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            bad = root / state.TRANSPORT_SMOKE_ROOT / "20260519T010000Z-trial-readiness.json"
            bad.parent.mkdir(parents=True)
            bad.write_text("{not-json", encoding="utf-8")

            payload = state.build_mcp_workflow_state(root)

        self.assertTrue(any("json-invalid:" in warning for warning in payload["warnings"]))
        self.assertEqual(payload["latestArtifacts"]["readiness"]["status"], "failed")
        self.assertFalse(payload["latestArtifacts"]["readiness"]["ok"])


if __name__ == "__main__":
    unittest.main()
