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


def make_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")


def valid_proof() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "publicMcpUrl": "https://example.trycloudflare.com/mcp",
        "chatgptRegistrationSucceeded": True,
        "toolCount": 9,
        "health": {
            "repoRoot": ".",
            "repoName": "RiftReader",
            "absoluteRepoRootExposed": False,
        },
        "templateFetched": True,
        "submitPackageProposalSucceeded": True,
        "inboxId": "20260519T010000Z-abcdef",
        "listInboxSawInboxId": True,
        "draftId": "20260519T010100Z-abcdef",
        "dryRunSucceeded": True,
        "notes": "Observed manually in ChatGPT Developer Mode.",
    }


class ChatGptTrialRecorderTests(unittest.TestCase):
    def test_template_contains_required_fields_and_safe_defaults(self) -> None:
        payload = recorder.proof_template()

        for field in recorder.REQUIRED_FIELDS:
            self.assertIn(field, payload)
        self.assertEqual(payload["toolCount"], 9)
        self.assertEqual(payload["health"]["repoRoot"], ".")
        self.assertFalse(payload["health"]["absoluteRepoRootExposed"])

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
            self.assertFalse(payload["safety"]["chatGptApiCalled"])
            self.assertFalse(payload["safety"]["gitMutation"])

    def test_rejects_wrong_tool_count(self) -> None:
        proof = valid_proof()
        proof["toolCount"] = 7

        blockers = recorder.validate_proof(proof)

        self.assertIn("tool-count-not-9:7", blockers)

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
        self.assertIn("tool-count-not-9:99", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
