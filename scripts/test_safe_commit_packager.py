#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import safe_commit_packager as packager  # noqa: E402


def fake_state() -> dict[str, object]:
    return {
        "latestArtifacts": {
            "readiness": {"status": "passed", "ok": True, "path": "ready.json"},
            "proposal-smoke": {"status": "passed", "ok": True, "path": "proposal.json"},
            "cloudflare-smoke": {"status": "passed", "ok": True, "path": "public.json"},
            "actual-client-proof": None,
        }
    }


def fake_git_state(entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": "passed",
        "ok": True,
        "branchLine": "## main...origin/main",
        "dirty": bool(entries),
        "dirtyCount": len(entries),
        "entries": entries,
        "diffStat": " files changed",
        "warnings": [],
    }


class SafeCommitPackagerTests(unittest.TestCase):
    def plan_for(self, entries: list[dict[str, object]]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                mock.patch.object(packager, "git_dirty_state", return_value=fake_git_state(entries)),
                mock.patch.object(packager, "build_mcp_workflow_state", return_value=fake_state()),
            ):
                return packager.safe_commit_plan(root)

    def test_groups_dirty_files_by_workflow_slice(self) -> None:
        payload = self.plan_for(
            [
                {"status": " M", "path": "tools/riftreader_workflow/mcp_workflow_state.py"},
                {"status": " M", "path": "tools/riftreader_workflow/operator_lite.py"},
                {"status": " M", "path": "scripts/test_mcp_workflow_state.py"},
                {"status": " M", "path": "docs/workflow/riftreader-chatgpt-mcp.md"},
                {"status": "??", "path": "docs/handoffs/2026-05-19-helper.md"},
                {"status": "??", "path": ".riftreader-local/generated.json"},
            ]
        )

        self.assertIn("mcp-code", payload["groups"])
        self.assertIn("operator-lite", payload["groups"])
        self.assertIn("tests", payload["groups"])
        self.assertIn("docs", payload["groups"])
        self.assertIn("handoff", payload["groups"])
        self.assertIn("generated-ignored", payload["groups"])
        self.assertEqual(payload["draftCommitMessage"], "Add MCP workflow helper apps")

    def test_emits_explicit_paths_only_and_never_git_add_dot(self) -> None:
        payload = self.plan_for(
            [
                {"status": " M", "path": "tools/riftreader_workflow/mcp_artifact_browser.py"},
                {"status": "??", "path": ".riftreader-local/ignored.json"},
            ]
        )

        encoded = json.dumps(payload)
        self.assertFalse(payload["containsGitAddDot"])
        self.assertNotIn("git add .", encoded)
        self.assertEqual(
            payload["gitAddCommands"],
            [["git", "add", "--", "tools/riftreader_workflow/mcp_artifact_browser.py"]],
        )
        self.assertEqual(
            payload["pasteSafeGitAddCommands"],
            ['git add -- "tools/riftreader_workflow/mcp_artifact_browser.py"'],
        )
        self.assertNotIn(".riftreader-local/ignored.json", payload["stageablePaths"])

    def test_marks_untracked_handoff_separately(self) -> None:
        payload = self.plan_for([{"status": "??", "path": "docs/handoffs/2026-05-19-helper.md"}])

        self.assertEqual(list(payload["groups"].keys()), ["handoff"])
        self.assertEqual(payload["draftCommitMessage"], "Update MCP workflow documentation")

    def test_clean_tree_returns_clean_status(self) -> None:
        payload = self.plan_for([])

        self.assertEqual(payload["status"], "clean")
        self.assertEqual(payload["stageablePaths"], [])
        self.assertTrue(payload["safety"]["planOnly"])
        self.assertFalse(payload["safety"]["gitMutation"])

    def test_markdown_export_contains_explicit_staging_and_validation(self) -> None:
        payload = self.plan_for([{"status": " M", "path": "tools/riftreader_workflow/mcp_mission_control.py"}])

        markdown = packager.render_markdown(payload)

        self.assertIn("RiftReader Safe Commit Plan", markdown)
        self.assertIn('git add -- "tools/riftreader_workflow/mcp_mission_control.py"', markdown)
        self.assertIn("Validation before commit", markdown)
        self.assertNotIn("git add .", markdown)


if __name__ == "__main__":
    unittest.main()
