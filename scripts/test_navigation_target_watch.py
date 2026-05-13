from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rift_live_test.navigation_target_watch import (
    TARGET_FOUND_PASSIVE,
    TARGET_MINIMIZED,
    TARGET_MISSING,
    NavigationTargetWatchOptions,
    _attempt_summary,
    _filter_matching_windows,
    _process_name_matches,
    _summary,
)
from rift_live_test.target_control import WindowSnapshot


def make_window(
    *,
    hwnd: int = 0xC0994,
    pid: int = 2928,
    process_name: str = "rift_x64",
    title: str = "RIFT",
    visible: bool = True,
    minimized: bool = False,
) -> WindowSnapshot:
    return WindowSnapshot(
        hwnd=hwnd,
        hwnd_hex=f"0x{hwnd:X}",
        process_id=pid,
        process_name=process_name,
        title=title,
        is_window=True,
        is_visible=visible,
        is_minimized=minimized,
    )


class NavigationTargetWatchTests(unittest.TestCase):
    def test_process_name_matching_accepts_exe_suffix(self) -> None:
        self.assertTrue(_process_name_matches("rift_x64", "rift_x64.exe"))
        self.assertTrue(_process_name_matches("rift_x64.exe", "rift_x64"))
        self.assertFalse(_process_name_matches("notepad", "rift_x64"))

    def test_filters_matching_windows(self) -> None:
        windows = [
            make_window(pid=2928, title="RIFT"),
            make_window(pid=1234, title="Other", process_name="notepad"),
        ]
        matches = _filter_matching_windows(
            windows,
            process_id=2928,
            process_name="rift_x64",
            title_contains="RIFT",
        )

        self.assertEqual(1, len(matches))
        self.assertEqual(0xC0994, matches[0].hwnd)

    def test_attempt_summary_visible_target_is_ready_for_target_control(self) -> None:
        attempt = _attempt_summary(1, [make_window()])

        self.assertEqual(TARGET_FOUND_PASSIVE, attempt["status"])
        self.assertTrue(attempt["readyForTargetControl"])
        self.assertFalse(attempt["readyForVisualGate"])
        self.assertEqual([], attempt["blockers"])

    def test_attempt_summary_minimized_target_blocks(self) -> None:
        attempt = _attempt_summary(1, [make_window(minimized=True)])

        self.assertEqual(TARGET_MINIMIZED, attempt["status"])
        self.assertFalse(attempt["readyForTargetControl"])
        self.assertIn("target-window-minimized", attempt["blockers"])

    def test_attempt_summary_missing_target_blocks(self) -> None:
        attempt = _attempt_summary(1, [])

        self.assertEqual(TARGET_MISSING, attempt["status"])
        self.assertFalse(attempt["readyForTargetControl"])
        self.assertIn("target-window-missing", attempt["blockers"])

    def test_summary_records_no_input_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            options = NavigationTargetWatchOptions(repo_root=root, attempts=1)
            attempt = _attempt_summary(1, [make_window()])
            summary = _summary(
                options=options,
                repo_root=root,
                output_dir=root / "out",
                started_at="2026-05-13T00:00:00Z",
                attempts=[attempt],
                final_status=TARGET_FOUND_PASSIVE,
                blockers=[],
            )

        self.assertTrue(summary["ok"])
        self.assertTrue(summary["safety"]["passiveEnumerationOnly"])
        self.assertFalse(summary["safety"]["foregroundChanged"])
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["readyForVisualGate"])


if __name__ == "__main__":
    unittest.main()
