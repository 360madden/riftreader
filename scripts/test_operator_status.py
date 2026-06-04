#!/usr/bin/env python3
# Version: riftreader-test-operator-status-v0.1.0
# Total-Character-Count: 0000001592
# Purpose: Unit tests for RiftReader operator status board rendering and self-test.

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow.operator_status import render_md, self_test  # noqa: E402


class OperatorStatusTests(unittest.TestCase):
    def test_self_test_passes(self) -> None:
        self.assertEqual(self_test()["status"], "passed")

    def test_render_markdown_contains_board(self) -> None:
        payload = {
            "status": "passed",
            "generatedAtUtc": "2026-06-04T00:00:00Z",
            "board": {
                "currentLane": "static-chain-repair-needed",
                "now": "Static-chain repair",
                "next": "Use diagnostics",
                "later": "Later",
                "blockedBy": "root-pointer-null",
            },
            "classifier": {
                "nextRecommendedAction": "Run diagnostics",
                "nextRecommendedCommand": "python example.py",
                "doNotDo": ["Do not rerun proof recovery."],
            },
        }
        rendered = render_md(payload)
        self.assertIn("Project Board", rendered)
        self.assertIn("static-chain-repair-needed", rendered)
        self.assertIn("Do not rerun proof recovery", rendered)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
