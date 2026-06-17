#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import push_current_branch as push_preflight  # noqa: E402


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        shell=False,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', errors='replace')}")
    return proc.stdout.decode("utf-8", errors="replace").strip()


def make_repo_with_origin(base: Path) -> tuple[Path, Path]:
    origin = base / "origin.git"
    root = base / "work"
    origin.mkdir()
    root.mkdir()
    git(origin, "init", "--bare")
    (root / "agents.md").write_text("# test policy\n", encoding="utf-8")
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "RiftReader Test")
    git(root, "add", "agents.md")
    git(root, "commit", "-m", "initial")
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "-u", "origin", "main")
    return root, origin


def add_local_commit(root: Path) -> str:
    (root / "agents.md").write_text("# test policy\n\nupdated\n", encoding="utf-8")
    git(root, "add", "agents.md")
    git(root, "commit", "-m", "local update")
    return git(root, "rev-parse", "HEAD")


class PushCurrentBranchPreflightTests(unittest.TestCase):
    def test_ready_when_clean_and_ahead_of_origin_main(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, _origin = make_repo_with_origin(Path(temp_dir))
            head = add_local_commit(root)

            payload = push_preflight.push_preflight(root)

        self.assertTrue(payload["ok"], payload.get("blockers"))
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["currentHead"], head)
        self.assertEqual(payload["branch"], "main")
        self.assertEqual(payload["upstream"], "origin/main")
        self.assertEqual(payload["ahead"], 1)
        self.assertEqual(payload["behind"], 0)
        self.assertTrue(payload["expectedApprovalToken"].startswith("PUSH-"))
        self.assertEqual(payload["futureCommands"]["gitPush"], ["git", "push", "origin", "HEAD:main"])
        self.assertFalse(payload["safety"]["gitMutation"])
        self.assertFalse(payload["safety"]["remoteMutation"])
        self.assertTrue(payload["safety"]["readOnlyPreflight"])

    def test_blocks_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, _origin = make_repo_with_origin(Path(temp_dir))
            add_local_commit(root)
            (root / "untracked.txt").write_text("dirty\n", encoding="utf-8")

            payload = push_preflight.push_preflight(root)

        self.assertFalse(payload["ok"])
        self.assertIn("PUSH_WORKTREE_DIRTY", payload["blockers"])
        self.assertIsNone(payload["expectedApprovalToken"])
        self.assertFalse(payload["safety"]["remoteMutation"])

    def test_blocks_missing_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agents.md").write_text("# test policy\n", encoding="utf-8")
            git(root, "init", "-b", "main")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "RiftReader Test")
            git(root, "add", "agents.md")
            git(root, "commit", "-m", "initial")

            payload = push_preflight.push_preflight(root)

        self.assertFalse(payload["ok"])
        self.assertIn("PUSH_UPSTREAM_MISSING", payload["blockers"])

    def test_blocks_when_branch_is_behind_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            root, origin = make_repo_with_origin(base)
            other = base / "other"
            git(base, "clone", "-b", "main", str(origin), str(other))
            git(other, "config", "user.email", "test@example.invalid")
            git(other, "config", "user.name", "RiftReader Test")
            (other / "agents.md").write_text("# test policy\n\nremote update\n", encoding="utf-8")
            git(other, "add", "agents.md")
            git(other, "commit", "-m", "remote update")
            git(other, "push", "origin", "main")
            git(root, "fetch", "origin")

            payload = push_preflight.push_preflight(root)

        self.assertFalse(payload["ok"])
        self.assertIn("PUSH_BRANCH_BEHIND", payload["blockers"])
        self.assertIn("PUSH_NOTHING_TO_PUSH", payload["blockers"])

    def test_expected_fact_mismatches_block_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, _origin = make_repo_with_origin(Path(temp_dir))
            add_local_commit(root)

            payload = push_preflight.push_preflight(
                root,
                expected_head="0" * 40,
                branch="wrong",
                upstream="origin/wrong",
            )

        self.assertFalse(payload["ok"])
        self.assertIn("PUSH_HEAD_MISMATCH", payload["blockers"])
        self.assertIn("PUSH_BRANCH_MISMATCH", payload["blockers"])
        self.assertIn("PUSH_UPSTREAM_MISMATCH", payload["blockers"])

    def test_self_test_passes(self) -> None:
        payload = push_preflight.run_self_test()

        self.assertTrue(payload["ok"], payload.get("blockers"))
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["checks"]["ready_preflight"])
        self.assertTrue(payload["checks"]["dirty_blocks"])


if __name__ == "__main__":
    unittest.main()
