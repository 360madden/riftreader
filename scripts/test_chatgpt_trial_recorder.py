#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import chatgpt_trial_recorder as recorder  # noqa: E402
from riftreader_workflow import riftreader_chatgpt_mcp as chatgpt_mcp  # noqa: E402


def make_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")


def valid_proof() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "connectionMode": "openai-secure-mcp-tunnel",
        "publicMcpUrl": "https://example.openai-mcp-tunnel.invalid/mcp",
        "chatgptRegistrationSucceeded": True,
        "toolCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "toolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        "toolOutputSchemasPresent": True,
        "toolOutputSchemaCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "toolOutputSchemaToolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        "health": {
            "repoRoot": ".",
            "repoName": "RiftReader",
            "absoluteRepoRootExposed": False,
        },
        "templateFetched": True,
        "submitPackageProposalSucceeded": True,
        "inboxId": "20260519T010000Z-abcdef",
        "listInboxSawInboxId": True,
        "createPackageDraftSucceeded": True,
        "draftId": "20260519T010100Z-abcdef",
        "reviewLatestPackageDraftSucceeded": True,
        "reviewLatestPackageDraftReadOnly": True,
        "dryRunDiffPreviewOk": True,
        "dryRunDiffPreviewArtifactUnderPackageIntake": True,
        "dryRunDiffPreviewBoundedBytes": True,
        "dryRunDiffPreviewTextLength": 195,
        "dryRunDiffPreviewTruncated": False,
        "dryRunSucceeded": True,
        "applyLatestPackageDraftWithoutApprovalBlocked": True,
        "applyLatestPackageDraftWithoutApprovalBlockers": ["APPLY_APPROVAL_MISSING"],
        "applyLatestPackageDraftWithoutApprovalApplied": False,
        "notes": "Observed manually in ChatGPT Developer Mode.",
    }


class ChatGptTrialRecorderTests(unittest.TestCase):
    def test_expected_tool_surface_tracks_mcp_adapter_order(self) -> None:
        self.assertEqual(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES, chatgpt_mcp.EXPECTED_TOOL_ORDER)
        self.assertEqual(recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT, len(chatgpt_mcp.EXPECTED_TOOL_ORDER))
        self.assertIn("apply_latest_package_draft", recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES)

    def test_template_contains_required_fields_and_safe_defaults(self) -> None:
        payload = recorder.proof_template()

        for field in recorder.REQUIRED_FIELDS:
            self.assertIn(field, payload)
        self.assertEqual(payload["toolCount"], recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(payload["toolNames"], list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES))
        self.assertFalse(payload["toolOutputSchemasPresent"])
        self.assertEqual(payload["toolOutputSchemaCount"], recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(payload["toolOutputSchemaToolNames"], list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES))
        self.assertEqual(payload["connectionMode"], "openai-secure-mcp-tunnel")
        self.assertNotIn("trycloudflare.com", str(payload["publicMcpUrl"]))
        self.assertEqual(payload["health"]["repoRoot"], ".")
        self.assertFalse(payload["health"]["absoluteRepoRootExposed"])
        self.assertFalse(payload["applyLatestPackageDraftWithoutApprovalBlocked"])
        self.assertEqual(payload["applyLatestPackageDraftWithoutApprovalBlockers"], [])
        self.assertIsNone(payload["applyLatestPackageDraftWithoutApprovalApplied"])

    def test_self_test_passes_without_chatgpt_or_tunnel(self) -> None:
        payload = recorder.self_test()

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["safety"]["chatGptApiCalled"])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])

    def test_valid_proof_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            input_path = root / "proof-input.json"
            input_path.write_text(json.dumps(valid_proof()), encoding="utf-8")

            payload = recorder.record_proof(root, input_path)

            proof_json = root / payload["artifacts"]["proofJson"]
            proof_md = root / payload["artifacts"]["proofMarkdown"]
            markdown = proof_md.read_text(encoding="utf-8")

            self.assertEqual(payload["status"], "passed")
            self.assertTrue(payload["ok"])
            self.assertTrue(proof_json.is_file())
            self.assertTrue(proof_md.is_file())
            self.assertIn("RiftReader ChatGPT MCP Actual-Client Proof", markdown)
            self.assertIn("Connection mode", markdown)
            self.assertIn("Tool names", markdown)
            self.assertIn("Tool output schemas present", markdown)
            self.assertFalse(payload["safety"]["chatGptApiCalled"])
            self.assertFalse(payload["safety"]["gitMutation"])

    def test_rejects_wrong_tool_count(self) -> None:
        proof = valid_proof()
        proof["toolCount"] = 7

        blockers = recorder.validate_proof(proof)

        self.assertIn(f"tool-count-not-{recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:7", blockers)

    def test_rejects_unexpected_tool_name_set(self) -> None:
        proof = valid_proof()
        proof["toolNames"] = list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES[:-1]) + ["unexpected_tool"]

        blockers = recorder.validate_proof(proof)

        self.assertIn("tool-names-not-expected", blockers)

    def test_rejects_duplicate_tool_name_list(self) -> None:
        proof = valid_proof()
        proof["toolNames"] = ["health"] * recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT

        blockers = recorder.validate_proof(proof)

        self.assertIn("tool-names-contains-duplicates", blockers)
        self.assertIn("tool-names-not-expected", blockers)

    def test_rejects_missing_tool_output_schema_confirmation(self) -> None:
        proof = valid_proof()
        proof["toolOutputSchemasPresent"] = False
        proof["toolOutputSchemaCount"] = 9
        proof["toolOutputSchemaToolNames"] = list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES[:-1]) + ["unexpected_tool"]

        blockers = recorder.validate_proof(proof)

        self.assertIn("tool-output-schemas-not-confirmed", blockers)
        self.assertIn(f"tool-output-schema-count-not-{recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:9", blockers)
        self.assertIn("tool-output-schema-tool-names-not-expected", blockers)

    def test_rejects_public_fallback_url_for_secure_tunnel_mode(self) -> None:
        proof = valid_proof()
        proof["publicMcpUrl"] = "https://example.trycloudflare.com/mcp"

        blockers = recorder.validate_proof(proof)

        self.assertIn("secure-tunnel-proof-url-uses-public-fallback-host", blockers)

    def test_allows_public_url_only_when_fallback_mode_is_explicit(self) -> None:
        proof = valid_proof()
        proof["connectionMode"] = "public-https-fallback"
        proof["publicMcpUrl"] = "https://example.trycloudflare.com/mcp"

        blockers = recorder.validate_proof(proof)

        self.assertNotIn("secure-tunnel-proof-url-uses-public-fallback-host", blockers)

    def test_rejects_unknown_connection_mode(self) -> None:
        proof = valid_proof()
        proof["connectionMode"] = "trycloudflare"

        blockers = recorder.validate_proof(proof)

        self.assertIn("connection-mode-invalid:'trycloudflare'", blockers)

    def test_rejects_unfilled_public_url_placeholder(self) -> None:
        proof = valid_proof()
        proof["publicMcpUrl"] = "https://<secure-mcp-tunnel-selected-in-chatgpt>/mcp"

        blockers = recorder.validate_proof(proof)

        self.assertIn("public-mcp-url-placeholder", blockers)

    def test_rejects_unredacted_repo_root(self) -> None:
        proof = valid_proof()
        proof["health"] = {
            "repoRoot": r"C:\RIFT MODDING\RiftReader",
            "repoName": "RiftReader",
            "absoluteRepoRootExposed": True,
        }

        blockers = recorder.validate_proof(proof)

        self.assertTrue(any(blocker.startswith("health-repo-root-not-redacted") for blocker in blockers))
        self.assertTrue(any(blocker.startswith("health-absolute-repo-root-exposed") for blocker in blockers))

    def test_rejects_missing_inbox_id_for_successful_submit(self) -> None:
        proof = valid_proof()
        proof["inboxId"] = ""

        blockers = recorder.validate_proof(proof)

        self.assertIn("submit-succeeded-but-inbox-id-missing", blockers)

    def test_rejects_missing_review_and_diff_preview_confirmation(self) -> None:
        proof = valid_proof()
        proof["reviewLatestPackageDraftSucceeded"] = False
        proof["reviewLatestPackageDraftReadOnly"] = False
        proof["dryRunDiffPreviewOk"] = False
        proof["dryRunDiffPreviewArtifactUnderPackageIntake"] = False
        proof["dryRunDiffPreviewBoundedBytes"] = False
        proof["dryRunDiffPreviewTextLength"] = 0
        proof["dryRunDiffPreviewTruncated"] = "no"

        blockers = recorder.validate_proof(proof)

        self.assertIn("review-latest-package-draft-not-confirmed", blockers)
        self.assertIn("review-latest-package-draft-read-only-not-confirmed", blockers)
        self.assertIn("dry-run-diff-preview-not-confirmed", blockers)
        self.assertIn("dry-run-diff-preview-package-intake-not-confirmed", blockers)
        self.assertIn("dry-run-diff-preview-bounded-bytes-not-confirmed", blockers)
        self.assertIn("dry-run-diff-preview-text-length-invalid:0", blockers)
        self.assertIn("dry-run-diff-preview-truncated-not-boolean:'no'", blockers)

    def test_rejects_missing_apply_without_approval_denial_proof(self) -> None:
        proof = valid_proof()
        proof["applyLatestPackageDraftWithoutApprovalBlocked"] = False
        proof["applyLatestPackageDraftWithoutApprovalBlockers"] = ["APPLY_PREFLIGHT_NOT_READY"]
        proof["applyLatestPackageDraftWithoutApprovalApplied"] = True

        blockers = recorder.validate_proof(proof)

        self.assertIn("apply-latest-package-draft-without-approval-not-blocked", blockers)
        self.assertIn("apply-latest-package-draft-without-approval-missing-approval-blocker", blockers)
        self.assertIn("apply-latest-package-draft-without-approval-applied-not-false:True", blockers)

    def test_rejects_non_list_apply_without_approval_blockers(self) -> None:
        proof = valid_proof()
        proof["applyLatestPackageDraftWithoutApprovalBlockers"] = "APPLY_APPROVAL_MISSING"

        blockers = recorder.validate_proof(proof)

        self.assertIn("apply-latest-package-draft-without-approval-blockers-not-list:str", blockers)

    def test_record_invalid_proof_returns_exit_2_in_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            input_path = root / "proof-input.json"
            proof = valid_proof()
            proof["toolCount"] = 99
            input_path.write_text(json.dumps(proof), encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = recorder.main(["--repo-root", str(root), "--record", "--input", str(input_path), "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn(f"tool-count-not-{recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:99", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
