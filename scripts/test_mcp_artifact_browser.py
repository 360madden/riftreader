#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_artifact_browser as browser  # noqa: E402
from riftreader_workflow import mcp_workflow_state as state  # noqa: E402


def make_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, object], mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))


class McpArtifactBrowserTests(unittest.TestCase):
    def test_latest_empty_roots_are_safe_and_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = browser.latest_payload(root)
            encoded = json.dumps(payload)

        self.assertEqual(payload["kind"], "riftreader-mcp-artifact-browser-latest")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["counts"]["readiness"], 0)
        self.assertIn("mcp-trial-readiness", encoded)
        self.assertTrue(payload["safety"]["readOnlyArtifactDiscovery"])

    def test_timeline_filters_kind_and_sorts_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_json(
                root / state.TRANSPORT_SMOKE_ROOT / "20260519T010000Z-proposal-transport-smoke.json",
                {"kind": "riftreader-chatgpt-mcp-proposal-transport-smoke", "status": "passed", "ok": True},
                1_800_000_000,
            )
            write_json(
                root / state.TRANSPORT_SMOKE_ROOT / "20260519T010100Z-proposal-transport-smoke.json",
                {"kind": "riftreader-chatgpt-mcp-proposal-transport-smoke", "status": "failed", "ok": False},
                1_800_000_100,
            )

            payload = state.artifact_timeline(root, kind="proposal-smoke", limit=10)

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["items"][0]["status"], "failed")
        self.assertTrue(payload["items"][0]["path"].endswith("20260519T010100Z-proposal-transport-smoke.json"))

    def test_cli_latest_json_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = browser.main(["--repo-root", str(root), "--latest", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-mcp-artifact-browser-latest")
        self.assertIn("latestArtifacts", payload)

    def test_cli_trial_session_kind_aggregates_ready_and_final(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_json(
                root / state.TRANSPORT_SMOKE_ROOT / "20260519T010000Z-chatgpt-trial-session-ready.json",
                {"kind": "ready", "status": "ready", "ok": True},
                1_800_000_000,
            )
            write_json(
                root / state.TRANSPORT_SMOKE_ROOT / "20260519T010100Z-chatgpt-trial-session.json",
                {"kind": "final", "status": "passed", "ok": True},
                1_800_000_100,
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = browser.main(["--repo-root", str(root), "--kind", "trial-session", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["items"][0]["status"], "passed")

    def test_open_latest_uses_read_only_local_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            write_json(
                root / state.TRANSPORT_SMOKE_ROOT / "20260519T010000Z-trial-readiness.json",
                {"kind": "readiness", "status": "passed", "ok": True},
                1_800_000_000,
            )
            with mock.patch.object(browser.os, "startfile", create=True) as startfile:
                payload = browser.open_latest_artifact(root, kind="readiness")

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["safety"]["readOnlyOpen"])
        startfile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
