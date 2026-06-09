# Version: riftreader-git-state-reader-tests-v0.1.0
# Total-Character-Count: 0000002055
# Purpose: Unit-test read-only Git state parser helpers for MCP Phase 1A.
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow import git_state_reader as reader


class GitStateReaderTests(unittest.TestCase):
    def test_parse_clean_branch(self) -> None:
        parsed = reader.parse_status_short_branch("## main...origin/main [ahead 12]\n")
        self.assertEqual(parsed["branchLine"], "main...origin/main [ahead 12]")
        self.assertEqual(parsed["ahead"], 12)
        self.assertIsNone(parsed["behind"])
        self.assertTrue(parsed["isClean"])
        self.assertEqual(parsed["paths"], [])

    def test_parse_dirty_paths(self) -> None:
        text = "## main...origin/main\n M docs/workflow/x.md\n?? scripts/y.py\n"
        parsed = reader.parse_status_short_branch(text)
        self.assertFalse(parsed["isClean"])
        self.assertEqual(parsed["paths"], [
            {"xy": " M", "path": "docs/workflow/x.md"},
            {"xy": "??", "path": "scripts/y.py"},
        ])

    def test_parse_behind_and_ahead(self) -> None:
        parsed = reader.parse_status_short_branch("## main...origin/main [ahead 2, behind 1]\n")
        self.assertEqual(parsed["ahead"], 2)
        self.assertEqual(parsed["behind"], 1)

    def test_parse_log_records(self) -> None:
        raw = "abcdef123456\x1fabcdef1\x1f2026-06-09T10:00:00+00:00\x1fSubject one\n"
        commits = reader.parse_log_records(raw)
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["shortSha"], "abcdef1")
        self.assertEqual(commits[0]["subject"], "Subject one")

    def test_safety_no_mutation(self) -> None:
        safety = reader.safety()
        self.assertFalse(safety["gitMutation"])
        self.assertFalse(safety["committed"])
        self.assertFalse(safety["pushed"])
        self.assertTrue(safety["readOnlyGit"])


if __name__ == "__main__":
    unittest.main()
# END_OF_SCRIPT_MARKER
