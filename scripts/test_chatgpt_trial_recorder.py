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
        "connectionMode": "cloudflare-named-tunnel",
        "publicMcpUrl": "https://mcp.360madden.com/mcp",
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
        self.assertEqual(recorder.EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES, chatgpt_mcp.PUBLIC_READ_ONLY_TOOL_ORDER)

    def test_template_contains_required_fields_and_safe_defaults(self) -> None:
        payload = recorder.proof_template()

        for field in recorder.REQUIRED_FIELDS:
            self.assertIn(field, payload)
        self.assertEqual(payload["toolCount"], recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(payload["toolNames"], list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES))
        self.assertFalse(payload["toolOutputSchemasPresent"])
        self.assertEqual(payload["toolOutputSchemaCount"], recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(payload["toolOutputSchemaToolNames"], list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES))
        self.assertEqual(payload["connectionMode"], "cloudflare-named-tunnel")
        self.assertNotIn("trycloudflare.com", str(payload["publicMcpUrl"]))
        self.assertEqual(payload["health"]["repoRoot"], ".")
        self.assertFalse(payload["health"]["absoluteRepoRootExposed"])
        self.assertFalse(payload["applyLatestPackageDraftWithoutApprovalBlocked"])
        self.assertEqual(payload["applyLatestPackageDraftWithoutApprovalBlockers"], [])
        self.assertIsNone(payload["applyLatestPackageDraftWithoutApprovalApplied"])

    def test_domain_read_only_template_contains_phase0_fields(self) -> None:
        payload = recorder.proof_template(recorder.DOMAIN_READ_ONLY_PROOF_MODE)

        self.assertEqual(payload["kind"], "riftreader-chatgpt-domain-read-only-proof-input")
        self.assertEqual(payload["proofMode"], recorder.DOMAIN_READ_ONLY_PROOF_MODE)
        self.assertEqual(payload["publicMcpUrl"], "https://mcp.360madden.com/mcp")
        self.assertEqual(payload["authentication"], "No Authentication")
        self.assertEqual(payload["toolCount"], recorder.EXPECTED_DOMAIN_READ_ONLY_TOOL_COUNT)
        self.assertEqual(payload["toolNames"], list(recorder.EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES))
        self.assertNotIn("submit_package_proposal", payload["toolNames"])
        self.assertFalse(payload["health"]["absoluteRepoRootExposed"])

    def test_write_template_creates_ignored_fillable_proof_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = recorder.write_proof_template(root)

            proof_input = root / payload["artifactPaths"]["proofInputJson"]
            proof = json.loads(proof_input.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["safety"]["templateWriteOnly"])
        self.assertIn(".riftreader-local", payload["artifactPaths"]["proofInputJson"])
        self.assertEqual(proof["kind"], "riftreader-chatgpt-actual-client-proof-input")
        self.assertEqual(proof["toolCount"], recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(payload["recordCommand"][0], "scripts\\riftreader-chatgpt-trial-recorder.cmd")
        self.assertEqual(payload["checkCommand"][0], "scripts\\riftreader-chatgpt-trial-recorder.cmd")
        self.assertIn("--check-input", payload["checkCommand"])
        self.assertIn(payload["artifactPaths"]["proofInputJson"], payload["checkCommand"])
        self.assertIn("--record", payload["recordCommand"])
        self.assertIn(payload["artifactPaths"]["proofInputJson"], payload["recordCommand"])

    def test_write_domain_read_only_template_creates_phase0_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = recorder.write_proof_template(root, proof_mode=recorder.DOMAIN_READ_ONLY_PROOF_MODE)
            proof_input = root / payload["artifactPaths"]["proofInputJson"]
            proof = json.loads(proof_input.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["proofMode"], recorder.DOMAIN_READ_ONLY_PROOF_MODE)
        self.assertEqual(proof["kind"], "riftreader-chatgpt-domain-read-only-proof-input")
        self.assertEqual(proof["toolNames"], list(recorder.EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES))

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

    def test_check_input_validates_without_writing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            input_path = root / "proof-input.json"
            input_path.write_text(json.dumps(valid_proof()), encoding="utf-8")

            payload = recorder.check_proof_input(root, input_path)

            proof_root = root / recorder.ACTUAL_CLIENT_PROOF_ROOT

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["blockers"], [])
        self.assertFalse(proof_root.exists())
        self.assertTrue(payload["safety"]["readOnlyProofInputCheck"])
        self.assertFalse(payload["safety"]["artifactWrite"])
        self.assertIn("--record", payload["recordCommand"])

    def test_check_input_reports_blockers_without_writing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            input_path = root / "proof-input.json"
            proof = valid_proof()
            proof["toolCount"] = 99
            input_path.write_text(json.dumps(proof), encoding="utf-8")

            payload = recorder.check_proof_input(root, input_path)

            proof_root = root / recorder.ACTUAL_CLIENT_PROOF_ROOT

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["ok"])
        self.assertIn(f"tool-count-not-{recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:99", payload["blockers"])
        self.assertFalse(proof_root.exists())
        self.assertTrue(payload["safety"]["readOnlyProofInputCheck"])
        self.assertFalse(payload["safety"]["artifactWrite"])

    def test_check_latest_template_uses_newest_template_without_writing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            older = root / recorder.PROOF_INPUT_TEMPLATE_ROOT / "20260519-010000Z" / "proof-input.json"
            newer = root / recorder.PROOF_INPUT_TEMPLATE_ROOT / "20260519-010100Z" / "proof-input.json"
            older.parent.mkdir(parents=True, exist_ok=True)
            newer.parent.mkdir(parents=True, exist_ok=True)
            older.write_text(json.dumps(valid_proof()), encoding="utf-8")
            bad = valid_proof()
            bad["toolCount"] = 99
            newer.write_text(json.dumps(bad), encoding="utf-8")

            payload = recorder.check_latest_proof_input_template(root)

            proof_root = root / recorder.ACTUAL_CLIENT_PROOF_ROOT

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["latestTemplate"])
        self.assertTrue(payload["inputPath"].endswith("20260519-010100Z\\proof-input.json"))
        self.assertIn(f"tool-count-not-{recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:99", payload["blockers"])
        self.assertFalse(proof_root.exists())
        self.assertTrue(payload["safety"]["readOnlyProofInputCheck"])

    def test_check_latest_template_blocks_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = recorder.check_latest_proof_input_template(root)

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["ok"])
        self.assertIn("proof-input-template-missing", payload["blockers"])
        self.assertTrue(payload["safety"]["readOnlyProofInputCheck"])

    def test_rejects_wrong_tool_count(self) -> None:
        proof = valid_proof()
        proof["toolCount"] = 7

        blockers = recorder.validate_proof(proof)

        self.assertIn(f"tool-count-not-{recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:7", blockers)

    def test_reports_chatgpt_tool_facade_unavailable_blocker(self) -> None:
        proof = valid_proof()
        proof["applyLatestPackageDraftWithoutApprovalBlocked"] = False
        proof["applyLatestPackageDraftWithoutApprovalBlockers"] = [
            "TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:get_package_proposal_template",
            "TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:submit_package_proposal",
        ]

        blockers = recorder.validate_proof(proof)

        self.assertIn(
            "chatgpt-tool-facade-unavailable:get_package_proposal_template,submit_package_proposal",
            blockers,
        )

    def test_accepts_valid_domain_read_only_phase0_proof(self) -> None:
        proof = recorder.domain_read_only_proof_template()
        proof.update(
            {
                "chatgptAppCreated": True,
                "healthCallSucceeded": True,
                "getRepoStatusCallSucceeded": True,
                "getWorkflowControlSummaryCallSucceeded": True,
            }
        )

        blockers = recorder.validate_proof(proof)

        self.assertEqual(blockers, [])

    def test_domain_read_only_phase0_rejects_full_tool_surface(self) -> None:
        proof = recorder.domain_read_only_proof_template()
        proof.update(
            {
                "chatgptAppCreated": True,
                "healthCallSucceeded": True,
                "getRepoStatusCallSucceeded": True,
                "getWorkflowControlSummaryCallSucceeded": True,
                "toolCount": recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                "toolNames": list(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            }
        )

        blockers = recorder.validate_proof(proof)

        full_tool_count = len(recorder.EXPECTED_CHATGPT_MCP_TOOL_NAMES)
        self.assertIn(f"tool-count-not-{recorder.EXPECTED_DOMAIN_READ_ONLY_TOOL_COUNT}:{full_tool_count}", blockers)
        self.assertIn("tool-names-not-expected", blockers)

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

    def test_rejects_retired_tunnel_url_for_manual_public_ip_mode(self) -> None:
        proof = valid_proof()
        proof["publicMcpUrl"] = "https://example.trycloudflare.com/mcp"

        blockers = recorder.validate_proof(proof)

        self.assertIn("proof-url-uses-retired-tunnel-host", blockers)

    def test_rejects_retired_public_fallback_mode(self) -> None:
        proof = valid_proof()
        proof["connectionMode"] = "public-https-fallback"
        proof["publicMcpUrl"] = "https://example.trycloudflare.com/mcp"

        blockers = recorder.validate_proof(proof)

        self.assertIn("connection-mode-invalid:'public-https-fallback'", blockers)
        self.assertIn("proof-url-uses-retired-tunnel-host", blockers)

    def test_rejects_unknown_connection_mode(self) -> None:
        proof = valid_proof()
        proof["connectionMode"] = "trycloudflare"

        blockers = recorder.validate_proof(proof)

        self.assertIn("connection-mode-invalid:'trycloudflare'", blockers)

    def test_rejects_unfilled_public_url_placeholder(self) -> None:
        proof = valid_proof()
        proof["publicMcpUrl"] = "https://<current-external-ip>/mcp"

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

    def test_check_input_invalid_proof_returns_exit_2_without_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            input_path = root / "proof-input.json"
            proof = valid_proof()
            proof["toolCount"] = 99
            input_path.write_text(json.dumps(proof), encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = recorder.main(["--repo-root", str(root), "--check-input", "--input", str(input_path), "--json"])
            payload = json.loads(stdout.getvalue())
            proof_root = root / recorder.ACTUAL_CLIENT_PROOF_ROOT

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn(f"tool-count-not-{recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:99", payload["blockers"])
        self.assertFalse(proof_root.exists())
        self.assertTrue(payload["safety"]["readOnlyProofInputCheck"])

    def test_check_latest_template_invalid_proof_returns_exit_2_without_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            input_path = root / recorder.PROOF_INPUT_TEMPLATE_ROOT / "20260519-010000Z" / "proof-input.json"
            input_path.parent.mkdir(parents=True, exist_ok=True)
            proof = valid_proof()
            proof["toolCount"] = 99
            input_path.write_text(json.dumps(proof), encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = recorder.main(["--repo-root", str(root), "--check-latest-template", "--json"])
            payload = json.loads(stdout.getvalue())
            proof_root = root / recorder.ACTUAL_CLIENT_PROOF_ROOT

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["latestTemplate"])
        self.assertIn(f"tool-count-not-{recorder.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:99", payload["blockers"])
        self.assertFalse(proof_root.exists())


if __name__ == "__main__":
    unittest.main()
