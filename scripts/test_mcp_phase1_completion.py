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

from riftreader_workflow import mcp_phase1_completion as phase1  # noqa: E402
from riftreader_workflow import mcp_workflow_state as state  # noqa: E402
from riftreader_workflow import chatgpt_trial_recorder as recorder  # noqa: E402


def make_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    (root / ".gitignore").write_text(".riftreader-local/\ndocs/handoffs/*mcp-phase1-*-handoff.md\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", "agents.md", ".gitignore"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", "baseline"],
        cwd=root,
        check=True,
    )


def write_json(path: Path, payload: dict[str, object], mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def write_repo_side_artifacts(root: Path) -> None:
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010000Z-trial-readiness.json",
        {"kind": "readiness", "status": "passed", "ok": True},
        1_800_000_000,
    )
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010100Z-proposal-transport-smoke.json",
        {"kind": "proposal", "status": "passed", "ok": True},
        1_800_000_010,
    )
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010200Z-cloudflare-tunnel-smoke.json",
        {
            "kind": "cloudflare",
            "status": "passed",
            "ok": True,
            "publicMcpUrl": "https://example.trycloudflare.com/mcp",
            "safety": {"publicTunnelStopped": True},
        },
        1_800_000_020,
    )
    write_json(
        root / state.TRANSPORT_SMOKE_ROOT / "20260519T010300Z-chatgpt-trial-session.json",
        {
            "kind": "trial",
            "status": "passed",
            "ok": True,
            "publicMcpUrl": "https://trial.trycloudflare.com/mcp",
            "safety": {"publicTunnelStopped": True, "serverStopped": True},
        },
        1_800_000_030,
    )


def write_proof_input_template(root: Path) -> None:
    write_json(
        root / state.PROOF_INPUT_TEMPLATE_ROOT / "20260519-010350Z" / "proof-input.json",
        {
            "kind": "riftreader-chatgpt-actual-client-proof-input",
            "schemaVersion": 1,
            "status": "ready",
            "ok": True,
            "connectionMode": "cloudflare-named-tunnel",
            "toolCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "toolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "toolOutputSchemaCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "toolOutputSchemaToolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        },
        1_800_000_025,
    )


def write_actual_client_proof(root: Path) -> None:
    write_json(
        root / state.ACTUAL_CLIENT_PROOF_ROOT / "20260519-010400Z" / "proof.json",
        {
            "kind": "riftreader-chatgpt-actual-client-proof",
            "status": "passed",
            "ok": True,
            "proof": {
                "schemaVersion": 1,
                "connectionMode": "cloudflare-named-tunnel",
                "toolCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                "toolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
                "toolOutputSchemasPresent": True,
                "toolOutputSchemaCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                "toolOutputSchemaToolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
                "publicMcpUrl": "https://mcp.360madden.com/mcp",
                "chatgptRegistrationSucceeded": True,
                "health": {
                    "repoRoot": ".",
                    "repoName": "RiftReader",
                    "absoluteRepoRootExposed": False,
                },
                "templateFetched": True,
                "submitPackageProposalSucceeded": True,
                "inboxId": "inbox-1",
                "listInboxSawInboxId": True,
                "createPackageDraftSucceeded": True,
                "draftId": "draft-1",
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
            },
            "blockers": [],
        },
        1_800_000_040,
    )


def write_legacy_actual_client_proof(root: Path) -> None:
    write_json(
        root / state.ACTUAL_CLIENT_PROOF_ROOT / "20260519-010400Z" / "proof.json",
        {
            "kind": "riftreader-chatgpt-actual-client-proof",
            "status": "passed",
            "ok": True,
            "proof": {
                "toolCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                "publicMcpUrl": "https://client.trycloudflare.com/mcp",
                "inboxId": "inbox-1",
                "draftId": "draft-1",
            },
            "blockers": [],
        },
        1_800_000_040,
    )


class McpPhase1CompletionTests(unittest.TestCase):
    def test_empty_repo_blocks_phase1(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = phase1.phase1_status(root)

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["repoSideComplete"])
        self.assertFalse(payload["phase1Complete"])
        self.assertIn("readiness-not-passed", payload["blockers"])

    def test_repo_side_complete_blocks_on_actual_client_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_repo_side_artifacts(root)

            payload = phase1.phase1_status(root)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["repoSideComplete"])
        self.assertFalse(payload["phase1Complete"])
        self.assertIn("actual-client-proof-not-passed", payload["blockers"])
        self.assertEqual(payload["recommendedNextAction"]["key"], "record-actual-client-proof")
        self.assertEqual(
            payload["recommendedNextAction"]["command"],
            ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--write-template", "--json"],
        )

    def test_repo_side_complete_records_actual_client_proof_when_template_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_repo_side_artifacts(root)
            write_proof_input_template(root)

            payload = phase1.phase1_status(root)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["repoSideComplete"])
        self.assertEqual(payload["recommendedNextAction"]["key"], "record-actual-client-proof")
        self.assertEqual(
            payload["recommendedNextAction"]["command"],
            [
                "scripts\\riftreader-chatgpt-trial-recorder.cmd",
                "--write-template",
                "--json",
            ],
        )

    def test_phase1_passes_when_actual_client_proof_exists_and_git_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_repo_side_artifacts(root)
            write_actual_client_proof(root)

            payload = phase1.phase1_status(root)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["repoSideComplete"])
        self.assertTrue(payload["phase1Complete"])
        self.assertEqual(payload["recommendedNextAction"]["key"], "phase1-complete-handoff")

    def test_phase1_blocks_legacy_passed_proof_that_fails_current_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_repo_side_artifacts(root)
            write_legacy_actual_client_proof(root)

            payload = phase1.phase1_status(root)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["repoSideComplete"])
        self.assertFalse(payload["phase1Complete"])
        self.assertIn("actual-client-proof-invalid:required-field-missing:connectionMode", payload["blockers"])

    def test_trial_session_teardown_final_does_not_invalidate_ready_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_repo_side_artifacts(root)
            write_json(
                root / state.TRANSPORT_SMOKE_ROOT / "20260519T010350Z-chatgpt-trial-session-ready.json",
                {
                    "kind": "riftreader-chatgpt-mcp-chatgpt-trial-session-ready",
                    "status": "ready",
                    "ok": True,
                    "publicMcpUrl": "https://trial-ready.trycloudflare.com/mcp",
                },
                1_800_000_035,
            )
            write_json(
                root / state.TRANSPORT_SMOKE_ROOT / "20260519T010500Z-chatgpt-trial-session.json",
                {
                    "kind": "riftreader-chatgpt-mcp-chatgpt-trial-session",
                    "status": "failed",
                    "ok": False,
                    "ready": True,
                    "blockers": ["chatgpt-session-interrupted"],
                    "publicMcpUrl": "https://trial-ready.trycloudflare.com/mcp",
                    "safety": {"publicTunnelStopped": True, "serverStopped": True},
                },
                1_800_000_050,
            )
            write_actual_client_proof(root)

            payload = phase1.phase1_status(root)

        self.assertEqual(payload["status"], "passed")
        trial_check = next(check for check in payload["checks"] if check["kind"] == "trial-session")
        self.assertTrue(trial_check["ok"])
        self.assertTrue(str(trial_check["path"]).endswith("chatgpt-trial-session-ready.json"))

    def test_markdown_and_handoff_render_blocked_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_repo_side_artifacts(root)
            payload = phase1.phase1_status(root)
            markdown = phase1.render_markdown(payload)
            handoff_payload = phase1.write_handoff(root, payload)

            handoff = root / handoff_payload["handoffPath"]
            handoff_exists = handoff.is_file()
            handoff_text = handoff.read_text(encoding="utf-8")

        self.assertIn("RiftReader ChatGPT MCP Phase 1 Status", markdown)
        self.assertIn("actual-client-proof-not-passed", markdown)
        self.assertTrue(handoff_exists)
        self.assertIn("external-client blocked", handoff_text)


if __name__ == "__main__":
    unittest.main()
