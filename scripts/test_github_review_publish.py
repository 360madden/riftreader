# Version: riftreader-github-review-publish-tests-v0.1.0
# Total-Character-Count: 3376
# Purpose: Unit tests for the Python-owned RiftReader GitHub review publish helper.

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow import github_review_publish as grp


class GitHubReviewPublishTests(unittest.TestCase):
    def test_normalize_rejects_traversal(self) -> None:
        with self.assertRaises(grp.ReviewPublishError):
            grp.normalize_repo_path("../bad")

    def test_normalize_rejects_drive_root(self) -> None:
        with self.assertRaises(grp.ReviewPublishError):
            grp.normalize_repo_path("C:/bad")

    def test_parse_status_porcelain(self) -> None:
        entries = grp.parse_status_porcelain("?? docs/workflow/github-review-publish.md\n M tools/x.py\n")
        self.assertEqual(entries[0].path, "docs/workflow/github-review-publish.md")
        self.assertEqual(entries[1].path, "tools/x.py")

    def test_dirty_policy_allows_and_ignores_expected_paths(self) -> None:
        entries = grp.parse_status_porcelain(
            "?? docs/workflow/github-review-publish.md\n"
            "?? artifacts/chatgpt-payloads/\n"
            "?? random.tmp\n"
        )
        dirty = grp.categorize_dirty(entries)
        self.assertIn("docs/workflow/github-review-publish.md", dirty["allowed"])
        self.assertIn("artifacts/chatgpt-payloads", dirty["ignored"])
        self.assertIn("random.tmp", dirty["unexpected"])

    def test_branch_name_policy(self) -> None:
        self.assertEqual(grp.validate_branch_name("chatgpt/review-20260517-000000Z"), "chatgpt/review-20260517-000000Z")
        with self.assertRaises(grp.ReviewPublishError):
            grp.validate_branch_name("bad..branch")

    def test_snapshot_write(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            payload = {
                "schemaVersion": 1,
                "tool": grp.TOOL_VERSION,
                "createdUtc": grp.utc_iso(),
                "currentBranch": "main",
                "head": "0" * 40,
                "validationProfiles": [{"profile": "github-review-publish", "ok": True}],
                "dirtyPaths": {"allowed": [], "ignored": [], "unexpected": []},
            }
            paths = grp.write_review_snapshot(root, payload)
            self.assertTrue((root / paths["json"]).is_file())
            self.assertTrue((root / paths["markdown"]).is_file())
            parsed = json.loads((root / paths["json"]).read_text(encoding="utf-8"))
            self.assertEqual(parsed["tool"], grp.TOOL_VERSION)

    def test_existing_allowed_paths_blocks_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with self.assertRaises(grp.ReviewPublishError):
                grp.existing_allowed_paths(root, ["artifacts/chatgpt-payloads/file.json"])

    def test_self_test_ok(self) -> None:
        report = grp.command_self_test(type("Args", (), {})())
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["checkCount"], 5)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
