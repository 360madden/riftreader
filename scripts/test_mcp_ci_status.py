#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_ci_status as ci  # noqa: E402


class McpCiStatusTests(unittest.TestCase):
    def test_self_test_passes_without_gh(self) -> None:
        payload = ci.self_test()

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
