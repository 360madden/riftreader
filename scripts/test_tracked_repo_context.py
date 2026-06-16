#!/usr/bin/env python3
# Version: riftreader-test-tracked-repo-context-v0.1.0
# Total-Character-Count: 0000006676
# Purpose: Unit tests for read-only git-tracked RiftReader context helper safety and behavior.

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.riftreader_workflow import tracked_repo_context as trc


class TrackedRepoContextTests(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git executable is required")
        self.temp = tempfile.TemporaryDirectory(prefix="riftreader-context-test-")
        self.root = Path(self.temp.name)
        self._write("docs/workflow/intro.md", "# Intro\nneedle line\n")
        self._write("tools/riftreader_workflow/helper.py", "VALUE = 'needle'\n")
        self._write("scripts/run.cmd", "@echo off\nREM needle cmd\n")
        self._write("config/sample.json", '{"needle": true}\n')
        self._write("untracked.md", "needle untracked\n")
        self._write(".env", "TOKEN=needle\n")
        self._write("secrets/credentials.txt", "needle secret\n")
        self._write(".riftreader-local/local.md", "needle local\n")
        self._write_bytes("data/blob.bin", b"\x00\x01\x02")
        self._git("init")
        self._git("add", "docs/workflow/intro.md")
        self._git("add", "tools/riftreader_workflow/helper.py")
        self._git("add", "scripts/run.cmd")
        self._git("add", "config/sample.json")
        self._git("add", ".env")
        self._git("add", "secrets/credentials.txt")
        self._git("add", ".riftreader-local/local.md")
        self._git("add", "data/blob.bin")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write(self, rel_path: str, text: str) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_bytes(self, rel_path: str, data: bytes) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _git(self, *args: str) -> None:
        proc = subprocess.run(["git", *args], cwd=self.root, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", errors="replace"))

    def test_tree_lists_allowed_tracked_text_only_by_default(self) -> None:
        result = trc.repo_tree_tracked(repo_root=self.root)
        self.assertTrue(result["ok"], result)
        paths = {row["path"] for row in result["files"]}
        self.assertIn("docs/workflow/intro.md", paths)
        self.assertIn("scripts/run.cmd", paths)
        self.assertNotIn("untracked.md", paths)
        self.assertNotIn(".env", paths)
        self.assertNotIn("data/blob.bin", paths)
        self.assertGreaterEqual(result["blockedCount"], 4)

    def test_read_tracked_file_returns_content(self) -> None:
        result = trc.repo_read_tracked_file("docs/workflow/intro.md", repo_root=self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["path"], "docs/workflow/intro.md")
        self.assertIn("needle line", result["content"])

    def test_read_untracked_file_is_blocked(self) -> None:
        result = trc.repo_read_tracked_file("untracked.md", repo_root=self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "not-git-tracked")

    def test_path_traversal_absolute_and_backslash_are_rejected(self) -> None:
        self.assertEqual(trc.repo_read_tracked_file("../docs/workflow/intro.md", repo_root=self.root)["reason"], "path-traversal")
        self.assertEqual(trc.repo_read_tracked_file("/docs/workflow/intro.md", repo_root=self.root)["reason"], "absolute-path")
        self.assertEqual(trc.repo_read_tracked_file("docs\\workflow\\intro.md", repo_root=self.root)["reason"], "backslash-path")
        self.assertEqual(trc.repo_read_tracked_file("docs/%2e%2e/.env", repo_root=self.root)["reason"], "path-traversal")

    def test_secret_binary_and_local_paths_are_blocked(self) -> None:
        self.assertEqual(trc.repo_read_tracked_file(".env", repo_root=self.root)["reason"], "secret-like-name")
        self.assertEqual(trc.repo_read_tracked_file("secrets/credentials.txt", repo_root=self.root)["reason"], "secret-like-path")
        self.assertEqual(trc.repo_read_tracked_file("data/blob.bin", repo_root=self.root)["reason"], "blocked-extension")
        self.assertEqual(trc.repo_read_tracked_file(".riftreader-local/local.md", repo_root=self.root)["reason"], "blocked-directory")

    def test_search_finds_tracked_text_and_skips_blocked_or_untracked(self) -> None:
        result = trc.repo_search_tracked("needle", repo_root=self.root)
        self.assertTrue(result["ok"], result)
        paths = {row["path"] for row in result["matches"]}
        self.assertIn("docs/workflow/intro.md", paths)
        self.assertIn("tools/riftreader_workflow/helper.py", paths)
        self.assertIn("scripts/run.cmd", paths)
        self.assertIn("config/sample.json", paths)
        self.assertNotIn("untracked.md", paths)
        self.assertNotIn(".env", paths)
        self.assertNotIn("secrets/credentials.txt", paths)

    def test_read_many_respects_total_limit(self) -> None:
        result = trc.repo_read_many_tracked_files(["docs/workflow/intro.md", "tools/riftreader_workflow/helper.py"], repo_root=self.root, max_total_bytes=10)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["ok"])

    def test_context_pack_reports_unknown_pack(self) -> None:
        result = trc.repo_context_pack("missing-pack", repo_root=self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "unknown-context-pack")
        self.assertIn("mcp-adapter", result["availablePacks"])

    def test_workflow_docs_context_pack_prefers_current_docs_and_newest_handoffs(self) -> None:
        self._write("docs/HANDOFF.md", "# Current handoff\n")
        self._write("docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md", "# MCP plan\n")
        self._write("docs/workflow/riftreader-chatgpt-mcp.md", "# MCP workflow\n")
        self._write("docs/workflow/aaa-older-workflow-doc.md", "# Older workflow doc\n")
        self._write("docs/handoffs/20260519-1805-mcp-final-readiness-release-handoff-maintenance.md", "# May handoff\n")
        self._write("docs/handoffs/2026-06-14-chatgpt-proof-mode-label-handoff.md", "# Mid handoff\n")
        self._write("docs/handoffs/2026-06-16-mcp-final-readiness-release-handoff-19-tool-current-product.md", "# New handoff\n")
        self._git(
            "add",
            "docs/HANDOFF.md",
            "docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md",
            "docs/workflow/riftreader-chatgpt-mcp.md",
            "docs/workflow/aaa-older-workflow-doc.md",
            "docs/handoffs/20260519-1805-mcp-final-readiness-release-handoff-maintenance.md",
            "docs/handoffs/2026-06-14-chatgpt-proof-mode-label-handoff.md",
            "docs/handoffs/2026-06-16-mcp-final-readiness-release-handoff-19-tool-current-product.md",
        )

        result = trc.repo_context_pack("workflow-docs", repo_root=self.root, max_files=6)

        self.assertTrue(result["ok"], result)
        self.assertEqual(
            result["selectedPaths"],
            [
                "docs/HANDOFF.md",
                "docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md",
                "docs/workflow/riftreader-chatgpt-mcp.md",
                "docs/handoffs/2026-06-16-mcp-final-readiness-release-handoff-19-tool-current-product.md",
                "docs/handoffs/2026-06-14-chatgpt-proof-mode-label-handoff.md",
                "docs/handoffs/20260519-1805-mcp-final-readiness-release-handoff-maintenance.md",
            ],
        )

    def test_self_test_passes(self) -> None:
        result = trc.run_self_test()
        self.assertTrue(result["ok"], json.dumps(result, indent=2))

    def test_cli_accepts_global_flags_after_subcommand(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = trc.main(["tree", "--repo-root", str(self.root), "--json"])
        self.assertEqual(exit_code, 0)
        self.assertIn("riftreader-repo-tree-tracked", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
