#!/usr/bin/env python3
# Version: riftreader-maintenance-blocked-handoff-helper-tests-v0.1.0
# Total-Character-Count: 33103
# Purpose: Offline tests for the RiftReader maintenance-blocked handoff helper. These tests do not require RIFT, Drive, or network access.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import riftreader_maintenance_blocked_handoff as helper


class MaintenanceBlockedHandoffTests(unittest.TestCase):
    def test_tracked_or_staged_status_lines_ignores_untracked(self) -> None:
        lines = ["?? scratch.txt", " M docs/file.md", "A  new.md"]
        self.assertEqual(helper.tracked_or_staged_status_lines(lines), [" M docs/file.md", "A  new.md"])

    def test_current_handoff_markdown_contains_end_marker(self) -> None:
        doc = {
            "status": "maintenance-blocked",
            "generatedUtc": "2026-05-12T00:00:00Z",
            "currentLane": "test",
            "currentBlocker": "blocked",
            "exactNextAction": "next",
            "repo": {"branch": "main", "head": "abc", "statusBefore": []},
            "riftProcessSnapshot": {"status": "captured", "count": 0, "items": []},
            "latestStage1Summary": {"path": "x"},
            "doNotDo": ["do not"],
            "verifiedHelpers": ["helper"],
            "driveArtifactPaths": ["drive"],
        }
        text = helper.current_handoff_markdown(doc)
        self.assertIn("maintenance-blocked", text)
        self.assertIn("END_OF_DOCUMENT_MARKER", text)

    def test_find_latest_stage1_summary_prefers_newest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captures = root / "scripts" / "captures"
            old_dir = captures / "postupdate-proof-reacquire-stage1-python-20260101T000000Z"
            new_dir = captures / "postupdate-proof-reacquire-stage1-python-20260102T000000Z"
            old_dir.mkdir(parents=True)
            new_dir.mkdir(parents=True)
            old_file = old_dir / "stage1-python-summary.json"
            new_file = new_dir / "stage1-python-summary.json"
            old_file.write_text(json.dumps({"status": "old"}), encoding="utf-8")
            new_file.write_text(json.dumps({"status": "new"}), encoding="utf-8")
            old_time = 1000
            new_time = 2000
            import os
            os.utime(old_file, (old_time, old_time))
            os.utime(new_file, (new_time, new_time))
            found = helper.find_latest_stage1_summary(root)
            self.assertIsNotNone(found)
            self.assertEqual(found["summary"]["status"], "new")

    def test_run_summary_markdown_contains_next_action(self) -> None:
        doc = {
            "status": "maintenance-blocked",
            "generatedUtc": "2026-05-12T00:00:00Z",
            "repoRoot": "C:/RIFT MODDING/RiftReader",
            "currentLane": "lane",
            "currentBlocker": "game down",
            "exactNextAction": "wait",
            "repo": {"branch": "main", "head": "abc"},
            "generatedArtifacts": ["a", "b"],
        }
        text = helper.run_summary_markdown(doc)
        self.assertIn("game down", text)
        self.assertIn("wait", text)
        self.assertIn("END_OF_DOCUMENT_MARKER", text)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
