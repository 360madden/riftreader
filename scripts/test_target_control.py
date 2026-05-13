# Version: riftreader-test-target-control-v0.1.2
# Total-Character-Count: 5847
# Purpose: Offline tests for RiftReader target-control classification and workflow capability policy. These tests do not touch the live game window.

from __future__ import annotations

import unittest
from pathlib import Path

from rift_live_test.target_control import (
    DIFFERENT_PROCESS_FOREGROUND,
    EXACT_HWND_FOREGROUND,
    FOREGROUND_NOT_ACQUIRED,
    SAME_PID_DIFFERENT_HWND_FOREGROUND,
    TARGET_CONTROL_BLOCKED,
    TARGET_CONTROL_PASSED,
    TARGET_WINDOW_MINIMIZED,
    TARGET_WINDOW_MISSING,
    ForegroundSnapshot,
    WindowSnapshot,
    build_capabilities,
    classify_foreground,
    parse_hwnd,
    select_target_window_from_candidates,
    TargetControlOptions,
)


def make_window(
    *,
    hwnd: int = 0x5121A,
    pid: int = 49504,
    visible: bool = True,
    minimized: bool = False,
) -> WindowSnapshot:
    return WindowSnapshot(
        hwnd=hwnd,
        hwnd_hex=f"0x{hwnd:X}",
        process_id=pid,
        process_name="rift_x64",
        title="RIFT",
        is_window=True,
        is_visible=visible,
        is_minimized=minimized,
    )


def make_foreground(*, hwnd: int = 0x5121A, pid: int = 49504) -> ForegroundSnapshot:
    return ForegroundSnapshot(
        hwnd=hwnd,
        hwnd_hex=f"0x{hwnd:X}",
        process_id=pid,
        process_name="rift_x64" if pid == 49504 else "WindowsTerminal",
        title="RIFT" if pid == 49504 else "PowerShell",
    )


class TargetControlTests(unittest.TestCase):
    def test_parse_hwnd_hex_and_decimal(self) -> None:
        self.assertEqual(0x5121A, parse_hwnd("0x5121A"))
        self.assertEqual(0x5121A, parse_hwnd(str(0x5121A)))
        self.assertIsNone(parse_hwnd(None))
        self.assertIsNone(parse_hwnd(""))

    def test_exact_hwnd_foreground_is_strong_pass(self) -> None:
        target = make_window()
        classification = classify_foreground(target, make_foreground())

        self.assertEqual(EXACT_HWND_FOREGROUND, classification.classification)
        self.assertEqual(TARGET_CONTROL_PASSED, classification.status)
        self.assertEqual((), classification.blockers)

        capabilities = build_capabilities(target, classification.classification, list(classification.blockers))
        self.assertTrue(capabilities["readOnlyProof"])
        self.assertTrue(capabilities["visualCapture"])
        self.assertTrue(capabilities["exactHwndInput"])
        self.assertTrue(capabilities["foregroundSendInput"])
        self.assertFalse(capabilities["yawStimulus"])
        self.assertFalse(capabilities["autoTurn"])

    def test_same_pid_different_hwnd_is_partial_pass_with_warning(self) -> None:
        target = make_window(hwnd=0x5121A, pid=49504)
        foreground = make_foreground(hwnd=0x77777, pid=49504)
        classification = classify_foreground(target, foreground)

        self.assertEqual(SAME_PID_DIFFERENT_HWND_FOREGROUND, classification.classification)
        self.assertEqual(TARGET_CONTROL_PASSED, classification.status)
        self.assertIn("foreground-window-belongs-to-same-process-but-not-requested-hwnd", classification.warnings)

        capabilities = build_capabilities(target, classification.classification, list(classification.blockers))
        self.assertTrue(capabilities["readOnlyProof"])
        self.assertFalse(capabilities["visualCapture"])
        self.assertTrue(capabilities["exactHwndInput"])
        self.assertFalse(capabilities["foregroundSendInput"])
        self.assertTrue(capabilities["samePidForegroundDiagnostic"])

    def test_different_process_foreground_blocks(self) -> None:
        target = make_window(hwnd=0x5121A, pid=49504)
        foreground = make_foreground(hwnd=0x12345, pid=11111)
        classification = classify_foreground(target, foreground)

        self.assertEqual(DIFFERENT_PROCESS_FOREGROUND, classification.classification)
        self.assertEqual(TARGET_CONTROL_BLOCKED, classification.status)
        self.assertIn(DIFFERENT_PROCESS_FOREGROUND, classification.blockers)

    def test_missing_target_blocks(self) -> None:
        classification = classify_foreground(None, make_foreground())

        self.assertEqual(TARGET_WINDOW_MISSING, classification.classification)
        self.assertEqual(TARGET_CONTROL_BLOCKED, classification.status)
        self.assertIn(TARGET_WINDOW_MISSING, classification.blockers)

    def test_no_foreground_blocks(self) -> None:
        target = make_window()
        foreground = ForegroundSnapshot(hwnd=0, hwnd_hex=None, process_id=None, process_name=None, title=None)
        classification = classify_foreground(target, foreground)

        self.assertEqual(FOREGROUND_NOT_ACQUIRED, classification.classification)
        self.assertEqual(TARGET_CONTROL_BLOCKED, classification.status)
        self.assertIn(FOREGROUND_NOT_ACQUIRED, classification.blockers)

    def test_minimized_target_blocks_even_if_exact_foreground(self) -> None:
        target = make_window(minimized=True)
        classification = classify_foreground(target, make_foreground())

        self.assertEqual(EXACT_HWND_FOREGROUND, classification.classification)
        self.assertEqual(TARGET_CONTROL_BLOCKED, classification.status)
        self.assertIn(TARGET_WINDOW_MINIMIZED, classification.blockers)

    def test_invisible_target_blocks_visual_and_input(self) -> None:
        target = make_window(visible=False)
        classification = classify_foreground(target, make_foreground())

        self.assertEqual(EXACT_HWND_FOREGROUND, classification.classification)
        self.assertEqual(TARGET_CONTROL_BLOCKED, classification.status)

        capabilities = build_capabilities(target, classification.classification, list(classification.blockers))
        self.assertFalse(capabilities["visualCapture"])
        self.assertFalse(capabilities["foregroundSendInput"])

    def test_process_name_title_selection_without_exact_pid(self) -> None:
        windows = [
            WindowSnapshot(
                hwnd=0x11111,
                hwnd_hex="0x11111",
                process_id=100,
                process_name="notepad",
                title="Other",
                is_window=True,
                is_visible=True,
                is_minimized=False,
            ),
            WindowSnapshot(
                hwnd=0xC0994,
                hwnd_hex="0xC0994",
                process_id=2928,
                process_name="rift_x64",
                title="RIFT",
                is_window=True,
                is_visible=True,
                is_minimized=False,
            ),
        ]
        options = TargetControlOptions(
            repo_root=Path("."),
            process_name="rift_x64",
            title_contains="RIFT",
        )

        selected = select_target_window_from_candidates(windows, options)

        self.assertIsNotNone(selected)
        self.assertEqual(0xC0994, selected.hwnd)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
