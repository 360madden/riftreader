# Version: riftreader-test-live-test-target-control-final-summary-field-v0.3.4
# Total-Character-Count: 1913
# Purpose: Source-level tests ensuring LiveTestRunner final summaries expose targetControl at top level. Offline-only; no live game access.

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "scripts" / "rift_live_test" / "runner.py"


class LiveTestTargetControlFinalSummaryFieldTests(unittest.TestCase):
    def _finish_block(self) -> str:
        text = RUNNER_PATH.read_text(encoding="utf-8")
        start = text.find("    def _finish(")
        self.assertNotEqual(-1, start, "def _finish not found in runner.py")
        next_def = text.find("\n    def ", start + 1)
        return text[start:] if next_def == -1 else text[start:next_def]

    def test_finish_summary_contains_top_level_target_control(self) -> None:
        block = self._finish_block()
        self.assertIn('"targetControl": self.target_control_summary,', block)

    def test_target_control_is_between_target_window_and_movement_fields(self) -> None:
        block = self._finish_block()
        target_index = block.index('"targetWindowHandle": self.target_window_handle,')
        target_control_index = block.index('"targetControl": self.target_control_summary,')
        movement_index = block.index('"movementSent":')
        self.assertLess(target_index, target_control_index)
        self.assertLess(target_control_index, movement_index)

    def test_target_control_recording_state_still_exists(self) -> None:
        text = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertIn("def _record_target_control_preflight", text)
        self.assertIn('"target-control"', text)
        self.assertIn("compact_target_control_summary", text)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
