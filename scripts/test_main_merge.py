# Version: riftreader-main-merge-tests-v0.1.0
# Total-Character-Count: 4902
# Purpose: Unit tests for the Python-owned RiftReader main merge helper.

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow import main_merge


class MainMergeTests(unittest.TestCase):
    def test_normalize_rejects_traversal(self) -> None:
        with self.assertRaises(main_merge.MainMergeError):
            main_merge.normalize_repo_path("../bad")

    def test_validate_ref_rejects_unsafe(self) -> None:
        with self.assertRaises(main_merge.MainMergeError):
            main_merge.validate_ref("bad..ref", "ref")

    def test_allowed_path_list_rejects_unexpected(self) -> None:
        with self.assertRaises(main_merge.MainMergeError):
            main_merge.assert_allowed_paths(["random.tmp"], "diff")

    def test_status_ignores_generated_paths(self) -> None:
        text = "?? artifacts/chatgpt-payloads/\n?? .riftreader-local/cache/\n?? random.tmp\n"
        entries = main_merge.parse_status_porcelain(text)
        ignored = [entry.path for entry in entries if main_merge.is_ignored_dirty(entry.path)]
        unexpected = [entry.path for entry in entries if not main_merge.is_ignored_dirty(entry.path)]
        self.assertIn("artifacts/chatgpt-payloads", ignored)
        self.assertIn(".riftreader-local/cache", ignored)
        self.assertEqual(unexpected, ["random.tmp"])

    def test_inspect_review_accepts_allowed_diff(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            paths = main_merge.init_synthetic_repo(Path(name))
            report = main_merge.inspect_review(paths["work"], "origin/main", "origin/chatgpt/review-test", None, "origin", 60, True)
            self.assertTrue(report["ok"])
            self.assertEqual(report["diffPaths"], ["docs/workflow/main-merge.md"])

    def test_inspect_review_rejects_unexpected_diff(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            paths = main_merge.init_synthetic_repo(Path(name))
            work = paths["work"]
            main_merge.run_command(work, ["git", "switch", "chatgpt/review-test"], 60)
            (work / "random.tmp").write_text("bad\n", encoding="utf-8")
            main_merge.run_command(work, ["git", "add", "random.tmp"], 60)
            main_merge.run_command(work, ["git", "commit", "-m", "bad path"], 60)
            main_merge.run_command(work, ["git", "push", "origin", "chatgpt/review-test"], 60)
            main_merge.run_command(work, ["git", "switch", "main"], 60)
            with self.assertRaises(main_merge.MainMergeError):
                main_merge.inspect_review(work, "origin/main", "origin/chatgpt/review-test", None, "origin", 60, True)

    def test_squash_review_pushes_main_and_verifies_remote_sha(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            paths = main_merge.init_synthetic_repo(Path(name))
            report = main_merge.squash_review(
                paths["work"],
                "main",
                "origin/chatgpt/review-test",
                None,
                "origin",
                "squash review",
                60,
                True,
                True,
            )
            self.assertTrue(report["ok"])
            self.assertEqual(report["remoteSha"], report["squashCommit"])
            self.assertEqual(report["stagedPaths"], ["docs/workflow/main-merge.md"])

    def test_squash_review_without_yes_push_is_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            paths = main_merge.init_synthetic_repo(Path(name))
            report = main_merge.squash_review(
                paths["work"],
                "main",
                "origin/chatgpt/review-test",
                None,
                "origin",
                "squash review",
                60,
                True,
                False,
            )
            self.assertTrue(report["ok"])
            self.assertTrue(report["dryRun"])

    def test_self_test_ok(self) -> None:
        report = main_merge.command_self_test(type("Args", (), {})())
        self.assertTrue(report["ok"])
        self.assertEqual(report["checkCount"], 4)

    def test_parser_supports_commands(self) -> None:
        parser = main_merge.build_parser()
        inspect_args = parser.parse_args(["inspect-review", "--review-branch", "origin/chatgpt/review-test"])
        self.assertEqual(inspect_args.command, "inspect-review")
        squash_args = parser.parse_args(["squash-review", "--review-branch", "origin/chatgpt/review-test", "--yes-push"])
        self.assertTrue(squash_args.yes_push)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
