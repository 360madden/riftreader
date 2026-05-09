# Version: riftreader-test-live-test-target-control-summary-field-v0.3.2
# Total-Character-Count: 1411
# Purpose: Offline tests verifying LiveTestRunner exposes target-control as a top-level run-summary field. No live game access.

from __future__ import annotations

from pathlib import Path
import unittest


def runner_text() -> str:
    return (Path(__file__).resolve().parents[1] / "scripts" / "rift_live_test" / "runner.py").read_text(encoding="utf-8")


class LiveTestTargetControlSummaryFieldTests(unittest.TestCase):
    def test_runner_has_target_control_attribute(self) -> None:
        text = runner_text()
        self.assertIn("self.target_control_summary: dict[str, Any] | None = None", text)

    def test_runner_exposes_top_level_target_control_field(self) -> None:
        text = runner_text()
        self.assertIn('"targetControl": self.target_control_summary,', text)

    def test_target_control_summary_field_is_near_target_identity(self) -> None:
        text = runner_text()
        target_index = text.index('"targetWindowHandle": self.target_window_handle')
        field_index = text.index('"targetControl": self.target_control_summary')
        movement_index = text.index('"movementSent":', field_index)
        self.assertLess(target_index, field_index)
        self.assertLess(field_index, movement_index)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
