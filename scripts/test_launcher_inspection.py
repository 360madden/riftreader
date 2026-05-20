from __future__ import annotations

import unittest

from rift_live_test.launcher_inspection import (
    classify_launcher_game_state,
    classify_launcher_window_state,
    launcher_visible_state_policy,
    relaunch_readiness,
    redact_command_line,
)


class LauncherInspectionTests(unittest.TestCase):
    def test_redacts_auth_like_command_line_values_but_keeps_hidden_flag(self) -> None:
        ticket = "SECRET" + "-TICKET"
        account = "player" + "@example.invalid"
        token = "ABC" + "123"
        redacted = redact_command_line(
            '"C:\\Program Files (x86)\\Glyph\\Games\\RIFT\\Live\\rift_x64.exe" '
            + "-k "
            + ticket
            + " -u "
            + account
            + " -hidden --token="
            + token
            + " bare-value"
        )

        self.assertIsNotNone(redacted)
        assert redacted is not None
        self.assertIn("rift_x64.exe", redacted)
        self.assertIn("-hidden", redacted)
        self.assertIn("-k <redacted>", redacted)
        self.assertIn("--token=<redacted>", redacted)
        self.assertNotIn(ticket, redacted)
        self.assertNotIn(account, redacted)
        self.assertNotIn(token, redacted)
        self.assertNotIn("bare-value", redacted)

    def test_classifies_launcher_and_game_child_process(self) -> None:
        state = classify_launcher_game_state(
            [
                {"name": "GlyphCrashHandler64.exe", "processId": 9, "parentProcessId": 1},
                {"name": "GlyphClientApp.exe", "processId": 10, "parentProcessId": 9},
                {"name": "rift_x64.exe", "processId": 20, "parentProcessId": 10},
            ]
        )

        self.assertEqual(state["crashRecoveryState"], "launcher-and-game-present")
        self.assertEqual(state["reloginState"], "observe-current-game-child")
        self.assertTrue(state["riftChildOfLauncher"])
        self.assertEqual(state["riftPids"], [20])
        self.assertEqual(state["glyphClientPids"], [10])

    def test_classifies_launcher_present_game_missing_as_approval_required(self) -> None:
        state = classify_launcher_game_state(
            [
                {"name": "GlyphCrashHandler64.exe", "processId": 9, "parentProcessId": 1},
                {"name": "GlyphClientApp.exe", "processId": 10, "parentProcessId": 9},
            ]
        )

        self.assertEqual(state["crashRecoveryState"], "launcher-present-game-missing")
        self.assertEqual(state["reloginState"], "approval-required-before-launch")
        self.assertIn("game-process-missing-do-not-launch-without-explicit-approval", state["blockers"])

    def test_classifies_game_present_launcher_missing_as_warning(self) -> None:
        state = classify_launcher_game_state(
            [
                {"name": "rift_x64.exe", "processId": 20, "parentProcessId": 10},
            ]
        )

        self.assertEqual(state["crashRecoveryState"], "game-present-launcher-missing")
        self.assertFalse(state["riftChildOfLauncher"])
        self.assertIn("launcher-process-missing-while-game-is-running", state["warnings"])

    def test_classifies_hidden_or_minimized_launcher_windows(self) -> None:
        self.assertEqual(classify_launcher_window_state(None), "missing")
        self.assertEqual(
            classify_launcher_window_state({"isVisible": False, "isMinimized": False}),
            "hidden",
        )
        self.assertEqual(
            classify_launcher_window_state(
                {
                    "isVisible": True,
                    "isMinimized": False,
                    "windowRect": {"left": -32000, "top": -32000},
                    "clientSize": {"width": 0, "height": 0},
                }
            ),
            "minimized-or-offscreen",
        )
        self.assertEqual(
            classify_launcher_window_state(
                {
                    "isVisible": True,
                    "isMinimized": False,
                    "windowRect": {"left": 10, "top": 10},
                    "clientSize": {"width": 400, "height": 425},
                }
            ),
            "visible-with-client-area",
        )

    def test_visible_state_policy_requires_classifier_before_buttons(self) -> None:
        hidden = launcher_visible_state_policy("minimized-or-offscreen")
        visible = launcher_visible_state_policy("visible-with-client-area")

        self.assertFalse(hidden["safeToAutomateButtons"])
        self.assertTrue(hidden["requiresExplicitRestoreApproval"])
        self.assertIn("launcher-visible-state-not-button-safe:minimized-or-offscreen", hidden["blockers"])
        self.assertTrue(visible["safeToAutomateButtons"])
        self.assertEqual(visible["blockers"], [])

    def test_relaunch_readiness_is_approval_gated_when_game_missing(self) -> None:
        readiness = relaunch_readiness({"reloginState": "approval-required-before-launch"}, "visible-with-client-area")

        self.assertEqual(readiness["status"], "approval-required-before-launch")
        self.assertTrue(readiness["canPlanRelaunch"])
        self.assertFalse(readiness["canExecuteRelaunchNow"])
        self.assertTrue(readiness["requiresExplicitApproval"])
        self.assertIn("explicit-launch-approval-required", readiness["blockers"])

    def test_relaunch_readiness_not_needed_when_game_child_present(self) -> None:
        readiness = relaunch_readiness({"reloginState": "observe-current-game-child"}, "minimized-or-offscreen")

        self.assertEqual(readiness["status"], "not-needed-game-present")
        self.assertFalse(readiness["canPlanRelaunch"])
        self.assertFalse(readiness["canExecuteRelaunchNow"])
        self.assertEqual(readiness["blockers"], [])


if __name__ == "__main__":
    unittest.main()
