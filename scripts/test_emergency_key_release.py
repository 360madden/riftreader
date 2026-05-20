from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rift_live_test.emergency_key_release import (
    DEFAULT_RELEASE_KEYS,
    build_release_plan,
    build_mouse_release_plan,
    keyup_lparam,
    normalize_key_name,
    normalize_mouse_button_name,
    parse_key_list,
    parse_mouse_button_list,
    run,
    build_parser,
)


class EmergencyKeyReleaseTests(unittest.TestCase):
    def test_default_keys_include_turn_and_movement_keys(self) -> None:
        keys = parse_key_list(None)

        for key in ["W", "A", "S", "D", "Q", "E", "LEFT", "RIGHT", "UP", "DOWN"]:
            self.assertIn(key, keys)
        self.assertEqual(len(keys), len(set(keys)))

    def test_key_aliases_normalize(self) -> None:
        self.assertEqual(normalize_key_name("leftArrow"), "LEFT")
        self.assertEqual(normalize_key_name("ctrl"), "CONTROL")
        self.assertEqual(normalize_mouse_button_name("mouseRight"), "RIGHT")

    def test_release_plan_contains_only_keyup_events(self) -> None:
        plan = build_release_plan(["W", "A", "Right"])

        self.assertEqual([item["key"] for item in plan], ["W", "A", "RIGHT"])
        for item in plan:
            joined = " ".join(item["events"]).upper()
            self.assertIn("KEYUP", joined)
            self.assertNotIn("KEYDOWN", joined)

    def test_mouse_release_plan_contains_only_mouse_up_events(self) -> None:
        buttons = parse_mouse_button_list(None, include_default=True)
        plan = build_mouse_release_plan(buttons)

        self.assertEqual(buttons, ["LEFT", "RIGHT", "MIDDLE"])
        for item in plan:
            joined = " ".join(item["events"]).upper()
            self.assertIn("UP", joined)
            self.assertNotIn("DOWN", joined)

    def test_keyup_lparam_marks_previous_and_transition_bits(self) -> None:
        value = keyup_lparam(0x11)

        self.assertTrue(value & 0x40000000)
        self.assertTrue(value & 0x80000000)

    def test_dry_run_does_not_mark_input_sent(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--hwnd", "0x1234", "--pid", "99", "--dry-run", "--json"])

        exit_code, summary = run(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["status"], "planned")
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["safety"]["keyDownSent"])
        self.assertEqual(len(summary["releasePlan"]), len(DEFAULT_RELEASE_KEYS))

    def test_dry_run_can_plan_mouse_button_release_without_mouse_down(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--hwnd", "0x1234", "--pid", "99", "--dry-run", "--include-mouse-buttons", "--json"])

        exit_code, summary = run(args)

        self.assertEqual(exit_code, 0)
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["safety"]["mouseDownSent"])
        self.assertEqual(summary["safety"]["inputType"], "keyup-and-mouseup-release")
        self.assertEqual([item["button"] for item in summary["mouseReleasePlan"]], ["LEFT", "RIGHT", "MIDDLE"])


if __name__ == "__main__":
    unittest.main()
