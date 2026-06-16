#!/usr/bin/env python3

from __future__ import annotations

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

from riftreader_workflow import commit_reviewed_slice as commit_preflight  # noqa: E402


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


def make_repo(root: Path) -> str:
    (root / "agents.md").write_text("# test policy\n", encoding="utf-8")
    (root / ".gitignore").write_text(".riftreader-local/\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "slice.md").write_text("before\n", encoding="utf-8")
    (root / "docs" / "other.md").write_text("other before\n", encoding="utf-8")
    git(root, "init")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "RiftReader Test")
    git(root, "add", ".gitignore", "agents.md", "docs/slice.md", "docs/other.md")
    git(root, "commit", "-m", "initial")
    return git(root, "rev-parse", "HEAD")


def make_validation(root: Path, head: str, *, status: str = "passed", ok: bool = True) -> tuple[str, str]:
    validation_dir = root / ".riftreader-local" / "validation-runs" / "unit-test"
    validation_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "schemaVersion": 1,
        "kind": "riftreader-validation-ledger",
        "status": status,
        "ok": ok,
        "git": {"head": head},
        "commands": [{"label": "unit-test", "ok": ok}],
        "blockers": [] if ok else ["unit-test-failed"],
        "errors": [],
    }
    path = validation_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    digest = commit_preflight.sha256_file(path)
    return str(path.relative_to(root)).replace("\\", "/"), digest


class CommitReviewedSlicePreflightTests(unittest.TestCase):
    def test_ready_for_safe_dirty_file_with_validation_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            head = make_repo(root)
            (root / "docs" / "slice.md").write_text("after\n", encoding="utf-8")
            validation_path, digest = make_validation(root, head)

            payload = commit_preflight.commit_preflight(
                root,
                expected_head=head,
                paths=["docs/slice.md"],
                commit_message="Update commit preflight docs",
                validation_summary_path=validation_path,
                validation_digest=digest,
            )

        self.assertTrue(payload["ok"], payload.get("blockers"))
        self.assertEqual(payload["status"], "ready")
        self.assertFalse(payload["committed"])
        self.assertEqual(payload["requestedPaths"], ["docs/slice.md"])
        self.assertEqual(payload["futureCommands"]["gitAdd"], ["git", "add", "--", "docs/slice.md"])
        self.assertEqual(
            payload["futureCommands"]["preCommit"],
            ["pre-commit", "run", "--files", "docs/slice.md"],
        )
        self.assertEqual(
            payload["futureCommands"]["gitCommit"],
            ["git", "commit", "-m", "Update commit preflight docs"],
        )
        self.assertTrue(payload["expectedApprovalToken"].startswith("COMMIT-"))
        self.assertFalse(payload["safety"]["gitMutation"])
        self.assertTrue(payload["safety"]["readOnlyPreflight"])

    def test_blocks_unrelated_dirty_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            head = make_repo(root)
            (root / "docs" / "slice.md").write_text("after\n", encoding="utf-8")
            (root / "docs" / "other.md").write_text("other after\n", encoding="utf-8")
            validation_path, digest = make_validation(root, head)

            payload = commit_preflight.commit_preflight(
                root,
                expected_head=head,
                paths=["docs/slice.md"],
                commit_message="Update one file only",
                validation_summary_path=validation_path,
                validation_digest=digest,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("COMMIT_UNRELATED_DIRTY_PATHS:1", payload["blockers"])
        self.assertEqual(payload["unrelatedDirtyPaths"], ["docs/other.md"])

    def test_blocks_forbidden_paths_and_wildcards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            head = make_repo(root)
            (root / "docs" / "slice.md").write_text("after\n", encoding="utf-8")
            validation_path, digest = make_validation(root, head)

            payload = commit_preflight.commit_preflight(
                root,
                expected_head=head,
                paths=["docs/*.md", "../outside.md", ".riftreader-local/capture.json", ".env"],
                commit_message="Update forbidden path test",
                validation_summary_path=validation_path,
                validation_digest=digest,
            )

        self.assertFalse(payload["ok"])
        blockers = "\n".join(payload["blockers"])
        self.assertIn("COMMIT_PATH_FORBIDDEN:docs/*.md:wildcard-path", blockers)
        self.assertIn("COMMIT_PATH_FORBIDDEN:../outside.md:path-traversal", blockers)
        self.assertIn("COMMIT_PATH_FORBIDDEN:.riftreader-local/capture.json:blocked-directory", blockers)
        self.assertIn("COMMIT_PATH_FORBIDDEN:.env:secret-like-name", blockers)

    def test_blocks_stale_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            head = make_repo(root)
            (root / "docs" / "slice.md").write_text("after\n", encoding="utf-8")
            validation_path, digest = make_validation(root, head)

            payload = commit_preflight.commit_preflight(
                root,
                expected_head="0" * 40,
                paths=["docs/slice.md"],
                commit_message="Update stale head test",
                validation_summary_path=validation_path,
                validation_digest=digest,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("COMMIT_HEAD_MISMATCH", payload["blockers"])

    def test_blocks_missing_and_failed_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            head = make_repo(root)
            (root / "docs" / "slice.md").write_text("after\n", encoding="utf-8")

            missing = commit_preflight.commit_preflight(
                root,
                expected_head=head,
                paths=["docs/slice.md"],
                commit_message="Update missing validation test",
                validation_summary_path=None,
                validation_digest=None,
            )

            failed_path, failed_digest = make_validation(root, head, status="failed", ok=False)
            failed = commit_preflight.commit_preflight(
                root,
                expected_head=head,
                paths=["docs/slice.md"],
                commit_message="Update failed validation test",
                validation_summary_path=failed_path,
                validation_digest=failed_digest,
            )

        self.assertFalse(missing["ok"])
        self.assertIn("COMMIT_VALIDATION_MISSING", missing["blockers"])
        self.assertFalse(failed["ok"])
        self.assertIn("COMMIT_VALIDATION_FAILED", failed["blockers"])

    def test_self_test_passes(self) -> None:
        payload = commit_preflight.run_self_test()

        self.assertTrue(payload["ok"], payload.get("blockers"))
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(all(payload["checks"].values()))


if __name__ == "__main__":
    unittest.main()
