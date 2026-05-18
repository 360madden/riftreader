# Version: riftreader-github-review-publish-tests-v0.1.2
# Total-Character-Count: 6083
# Purpose: Unit tests for the Python-owned RiftReader GitHub review publish helper.

from __future__ import annotations

import json
import subprocess
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


    def test_publish_branch_can_return_to_start_branch(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            remote = root / "remote.git"
            repo = root / "work"

            subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run(["git", "config", "user.email", "riftreader-tests@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "RiftReader Tests"], cwd=repo, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            rel = "docs/workflow/github-review-publish.md"
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("review docs\n", encoding="utf-8")

            result = grp.stage_commit_push_branch(
                repo,
                "chatgpt/review-return-test",
                "test review branch",
                [rel],
                30,
                return_to_start_branch=True,
            )

            self.assertEqual(result["startingBranch"], "main")
            self.assertTrue(result["returnedToStartBranch"])
            self.assertEqual(result["finalBranch"], "main")
            self.assertEqual(result["remoteSha"], result["commit"])
            current = subprocess.run(["git", "branch", "--show-current"], cwd=repo, check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
            self.assertEqual(current, "main")

    def test_publish_parser_accepts_return_to_start_branch(self) -> None:
        parser = grp.build_parser()
        args = parser.parse_args(["publish-branch", "--yes-push", "--return-to-start-branch"])
        self.assertTrue(args.return_to_start_branch)


    def test_main_merge_paths_are_allowlisted(self) -> None:
        self.assertIn("tools/riftreader_workflow/main_merge.py", grp.ALLOWED_STAGE_PATHS)
        self.assertIn("scripts/riftreader-main-merge.cmd", grp.ALLOWED_STAGE_PATHS)
        self.assertIn("scripts/test_main_merge.py", grp.ALLOWED_STAGE_PATHS)
        self.assertIn("docs/workflow/main-merge.md", grp.ALLOWED_STAGE_PATHS)

    def test_self_test_ok(self) -> None:
        report = grp.command_self_test(type("Args", (), {})())
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["checkCount"], 5)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
