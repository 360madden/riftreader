# Version: riftreader-test-visual-gate-target-control-v0.2.0
# Total-Character-Count: 3415
# Purpose: Offline tests for the visual-gate target-control wrapper. These tests do not touch the live game window.

from __future__ import annotations

import unittest
from pathlib import Path

from rift_live_test.target_control import EXACT_HWND_FOREGROUND, SAME_PID_DIFFERENT_HWND_FOREGROUND
from rift_live_test.visual_gate_with_target_control import (
    VISUAL_GATE_TC_BLOCKED_TARGET_CONTROL,
    build_combined_summary,
    target_control_allows_visual_gate,
)


def target_summary(*, status: str = "passed-target-control", classification: str = EXACT_HWND_FOREGROUND, ready: bool = True, blockers: list[str] | None = None) -> dict[str, object]:
    return {
        "status": status,
        "classification": classification,
        "readyForVisualGate": ready,
        "readyForLiveInput": ready,
        "blockers": blockers or [],
        "warnings": [],
    }


class VisualGateTargetControlTests(unittest.TestCase):
    def test_exact_hwnd_target_control_allows_visual_gate(self) -> None:
        self.assertTrue(target_control_allows_visual_gate(target_summary()))

    def test_same_pid_different_hwnd_does_not_allow_visual_gate(self) -> None:
        self.assertFalse(
            target_control_allows_visual_gate(
                target_summary(classification=SAME_PID_DIFFERENT_HWND_FOREGROUND)
            )
        )

    def test_target_control_blockers_do_not_allow_visual_gate(self) -> None:
        self.assertFalse(target_control_allows_visual_gate(target_summary(blockers=["focus-window-not-foreground"])))

    def test_target_control_not_ready_does_not_allow_visual_gate(self) -> None:
        self.assertFalse(target_control_allows_visual_gate(target_summary(ready=False)))

    def test_combined_summary_blocks_when_target_control_blocks(self) -> None:
        summary = build_combined_summary(
            repo_root=Path("C:/RIFT MODDING/RiftReader"),
            output_dir=Path("C:/RIFT MODDING/RiftReader/scripts/captures/test"),
            status=VISUAL_GATE_TC_BLOCKED_TARGET_CONTROL,
            target_control_summary=target_summary(status="blocked-target-control", ready=False, blockers=["different-process-foreground"]),
            visual_gate_summary=None,
            attempted_at_utc="2026-05-09T00:00:00Z",
        )

        self.assertEqual(VISUAL_GATE_TC_BLOCKED_TARGET_CONTROL, summary["status"])
        self.assertFalse(summary["readyForVisualGate"])
        self.assertFalse(summary["readyForLiveInput"])
        self.assertIn("target-control:different-process-foreground", summary["blockers"])

    def test_combined_summary_passes_when_both_layers_pass(self) -> None:
        summary = build_combined_summary(
            repo_root=Path("C:/RIFT MODDING/RiftReader"),
            output_dir=Path("C:/RIFT MODDING/RiftReader/scripts/captures/test"),
            status="passed-visual-gate-target-control",
            target_control_summary=target_summary(),
            visual_gate_summary={"status": "passed-visual-baseline", "readyForLiveInput": True, "blockers": []},
            attempted_at_utc="2026-05-09T00:00:00Z",
        )

        self.assertTrue(summary["readyForVisualGate"])
        self.assertTrue(summary["readyForLiveInput"])
        self.assertEqual([], summary["blockers"])


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
