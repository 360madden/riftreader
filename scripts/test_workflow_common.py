#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import common  # noqa: E402


class WorkflowCommonTests(unittest.TestCase):
    def test_utc_helpers_use_safe_formats(self) -> None:
        self.assertRegex(common.utc_iso(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertRegex(common.utc_stamp(), r"^\d{8}-\d{6}Z$")

    def test_repo_rel_prefers_windows_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child = root / "docs" / "workflow" / "test.md"
            child.parent.mkdir(parents=True)
            child.write_text("x", encoding="utf-8")

            self.assertEqual(common.repo_rel(root, child), "docs\\workflow\\test.md")
            self.assertIsNone(common.repo_rel(root, None))

    def test_unique_preserves_first_seen_order(self) -> None:
        self.assertEqual(common.unique(["a", "b", "a", "c", "b"]), ["a", "b", "c"])

    def test_timestamped_output_dir_avoids_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            first = common.timestamped_output_dir(base)
            second = common.timestamped_output_dir(base)

            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())
            self.assertNotEqual(first, second)
            self.assertTrue(re.match(r"^\d{8}-\d{6}Z(-\d+)?$", second.name))

    def test_safety_flags_are_fail_closed(self) -> None:
        flags = common.safety_flags()

        self.assertFalse(flags["movementSent"])
        self.assertFalse(flags["inputSent"])
        self.assertFalse(flags["gitMutation"])
        self.assertFalse(flags["savedVariablesUsedAsLiveTruth"])
        self.assertTrue(flags["noCheatEngine"])

    def test_run_command_envelope_records_stdout_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            envelope = common.run_command_envelope(
                "python-echo",
                [sys.executable, "-c", "print('ok')"],
                Path(temp_dir),
            )

        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["exitCode"], 0)
        self.assertEqual(envelope["stdoutPreview"].strip(), "ok")
        self.assertIn("durationSeconds", envelope)


if __name__ == "__main__":
    unittest.main()
