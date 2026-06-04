#!/usr/bin/env python3
# Version: riftreader-test-operator-status-publisher-v0.1.0
# Total-Character-Count: 0000001756
# Purpose: Unit tests for operator status GitHub snapshot publisher rendering.

from __future__ import annotations
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow.operator_status_publisher import build_snapshot, render_md, self_test, valid_branch  # noqa: E402

class OperatorStatusPublisherTests(unittest.TestCase):
    def test_self_test_passes(self) -> None:
        self.assertEqual(self_test()["status"], "passed")
    def test_validate_branch_rejects_bad(self) -> None:
        with self.assertRaises(Exception):
            valid_branch("../bad")
    def test_render_snapshot_markdown(self) -> None:
        status = {
            "board": {"currentLane": "static-chain-repair-needed", "now": "Static-chain repair", "next": "Use diagnostics", "later": "Later", "blockedBy": "root-pointer-null"},
            "classifier": {"classification": "static-chain-repair-needed", "confidence": "high", "reason": "test", "blocker": "root-pointer-null", "nextRecommendedAction": "Run diagnostics", "nextRecommendedCommand": "python example.py", "doNotDo": ["Do not rerun proof recovery."]},
            "compactStatus": {"blockers": ["root-pointer-null"]},
        }
        snap = build_snapshot(Path("C:/RIFT MODDING/RiftReader"), status, "# Test", "abc")
        md = render_md(snap)
        self.assertIn("Project Board", md)
        self.assertIn("static-chain-repair-needed", md)
        self.assertIn("root-pointer-null", md)

if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
