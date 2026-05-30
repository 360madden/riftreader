"""Tests for nav-state integration in navigation_target_watch.py."""
from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from scripts.rift_live_test.navigation_target_watch import (
    NavigationTargetWatchOptions,
    _render_markdown,
    watch_navigation_target,
)


class TestNavigationTargetWatchNavState(unittest.TestCase):
    """Tests for navStateCheck field behavior in the target watch summary."""

    def test_nav_state_check_none_when_not_provided(self) -> None:
        """When navStateCheck is not provided to _summary, it defaults to None."""
        from scripts.rift_live_test.navigation_target_watch import _summary
        options = NavigationTargetWatchOptions(
            repo_root=Path(__file__).resolve().parents[1],
            process_id=99999,
            attempts=1,
        )
        repo_root = options.repo_root.resolve()
        output_dir = repo_root / "scripts" / "captures" / "test-dummy"
        summary = _summary(
            options=options,
            repo_root=repo_root,
            output_dir=output_dir,
            started_at="2026-05-30T00:00:00+00:00",
            attempts=[],
            final_status="target-missing",
            blockers=["target-window-missing"],
        )
        self.assertIsNone(summary.get("navStateCheck"))

    def test_nav_state_check_present_when_provided(self) -> None:
        """When nav_state_check is passed to _summary, it appears in the output."""
        from scripts.rift_live_test.navigation_target_watch import _summary
        options = NavigationTargetWatchOptions(
            repo_root=Path(__file__).resolve().parents[1],
            process_id=99999,
            attempts=1,
        )
        repo_root = options.repo_root.resolve()
        output_dir = repo_root / "scripts" / "captures" / "test-dummy"
        nav_check = {"ok": True, "status": "passed"}
        summary = _summary(
            options=options,
            repo_root=repo_root,
            output_dir=output_dir,
            started_at="2026-05-30T00:00:00+00:00",
            attempts=[],
            final_status="target-found-passive",
            blockers=[],
            nav_state_check=nav_check,
        )
        self.assertEqual(summary["navStateCheck"], nav_check)


class TestRenderMarkdownNavState(unittest.TestCase):
    """Tests for markdown rendering of nav-state in the target watch."""

    def _make_summary(self, nav_state_check: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "mode": "navigation-target-watch",
            "status": "target-found-passive",
            "completedAtUtc": "2026-05-30T00:00:00+00:00",
            "target": {
                "processName": "rift_x64",
                "processId": 25668,
                "windowHandle": "0x320CB0",
                "titleContains": "RIFT",
            },
            "safety": {
                "passiveEnumerationOnly": True,
                "foregroundChanged": False,
                "movementSent": False,
                "inputSent": False,
                "reloaduiSent": False,
                "screenshotKeySent": False,
                "noCheatEngine": True,
                "providerWrites": False,
            },
            "attempts": [{
                "attempt": 1,
                "attemptedAtUtc": "2026-05-30T00:00:00+00:00",
                "status": "target-found-passive",
                "ok": True,
                "readyForTargetControl": True,
                "readyForVisualGate": False,
                "readyForProofOnly": False,
                "blockers": [],
                "selectedWindow": {
                    "processId": 25668,
                    "windowHandleHex": "0x320CB0",
                    "processName": "rift_x64.exe",
                    "title": "RIFT",
                    "isVisible": True,
                    "isMinimized": False,
                },
                "matchingWindowCount": 1,
                "matchingWindows": [],
            }],
            "selectedWindow": {
                "processId": 25668,
                "windowHandleHex": "0x320CB0",
                "processName": "rift_x64.exe",
                "title": "RIFT",
                "isVisible": True,
                "isMinimized": False,
            },
            "blockers": [],
            "warnings": ["passive-watch-only-rerun-target-control-before-visual-or-proof"],
            "navStateCheck": nav_state_check,
            "next": [{
                "action": "Run target-control for the selected exact PID/HWND",
                "why": "Passive enumeration found a window.",
            }],
        }

    def test_markdown_includes_nav_state_section_when_present(self) -> None:
        """Markdown includes a nav-state section when navStateCheck is provided."""
        nav_check = {
            "ok": True,
            "status": "passed",
            "verdict": "nav-state-health-check-passed",
            "yawDegrees": -157.55,
            "turnRate0x304": -2.12,
            "turnRateClassification": "right",
        }
        summary = self._make_summary(nav_check)
        markdown = _render_markdown(summary)
        self.assertIn("Pointer-chain nav-state health check", markdown)
        self.assertIn("-157.55", markdown)
        self.assertIn("-2.12", markdown)
        self.assertIn("right", markdown)

    def test_markdown_omits_nav_state_when_none(self) -> None:
        """Markdown does not include nav-state section when navStateCheck is None."""
        summary = self._make_summary(None)
        markdown = _render_markdown(summary)
        self.assertNotIn("Pointer-chain nav-state health check", markdown)

    def test_markdown_warns_when_nav_state_not_ok(self) -> None:
        """Markdown includes a warning when nav-state resolver is not healthy."""
        nav_check = {
            "ok": False,
            "status": "blocked",
            "verdict": "target-process-start-mismatch",
            "yawDegrees": None,
            "turnRate0x304": None,
            "turnRateClassification": "unknown",
        }
        summary = self._make_summary(nav_check)
        markdown = _render_markdown(summary)
        self.assertIn("Pointer-chain nav-state health check", markdown)
        self.assertIn("not healthy", markdown.lower())


if __name__ == "__main__":
    unittest.main()
