#!/usr/bin/env python3
# Version: riftreader-test-primary-workflow-policy-v0.1.0
# Total-Character-Count: 3031
# Purpose: Unit tests for the Python-owned RiftReader primary workflow policy helper.
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import primary_workflow_policy as policy  # noqa: E402


class PrimaryWorkflowPolicyTests(unittest.TestCase):
    def make_repo(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / ".git").mkdir()
        (root / "agents.md").write_text("# agents\n", encoding="utf-8")
        (root / "docs/workflow").mkdir(parents=True)
        (root / "docs/development").mkdir(parents=True)
        (root / "docs/workflow/non-codex-desktop-chatgpt-workflow.md").write_text("# Non-Codex\n\nBody\n", encoding="utf-8")
        (root / "docs/workflow/opencode-non-codex-bridge.md").write_text("# OpenCode\n\nBody\n", encoding="utf-8")
        (root / "docs/development/riftreader-drive-outbox-and-intake.md").write_text("# Drive\n\nBody\n", encoding="utf-8")
        return root

    def test_dry_run_does_not_write_docs(self) -> None:
        root = self.make_repo()
        target = root / policy.POLICY_DOC
        summary = policy.build_summary(root, apply=False, generated_utc="2026-05-17T00:00:00Z")
        self.assertTrue(summary["dryRun"])
        self.assertIn("docs/workflow/local-git-gh-primary-workflow.md", summary["changedFiles"])
        self.assertFalse(target.exists())

    def test_apply_writes_policy_docs_and_marker_blocks(self) -> None:
        root = self.make_repo()
        summary = policy.build_summary(root, apply=True, generated_utc="2026-05-17T00:00:00Z")
        self.assertFalse(summary["dryRun"])
        self.assertTrue((root / policy.POLICY_DOC).is_file())
        self.assertIn("local Python plus local git/gh CLI", (root / policy.POLICY_DOC).read_text(encoding="utf-8"))
        self.assertIn("RIFTREADER-PRIMARY-WORKFLOW-POLICY-BEGIN", (root / policy.NON_CODEX_DOC).read_text(encoding="utf-8"))
        self.assertIn("RIFTREADER-OPENCODE-DEMOTION-BEGIN", (root / policy.OPENCODE_DOC).read_text(encoding="utf-8"))
        self.assertIn("RIFTREADER-DRIVE-DEMOTION-BEGIN", (root / policy.DRIVE_DOC).read_text(encoding="utf-8"))

    def test_apply_is_idempotent_for_marker_blocks(self) -> None:
        root = self.make_repo()
        policy.build_summary(root, apply=True, generated_utc="2026-05-17T00:00:00Z")
        policy.build_summary(root, apply=True, generated_utc="2026-05-17T00:00:00Z")
        text = (root / policy.NON_CODEX_DOC).read_text(encoding="utf-8")
        self.assertEqual(text.count("RIFTREADER-PRIMARY-WORKFLOW-POLICY-BEGIN"), 1)
        self.assertEqual(text.count("RIFTREADER-PRIMARY-WORKFLOW-POLICY-END"), 1)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
