from __future__ import annotations

import argparse
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.profile_turn_keys import (
    build_parser,
    main,
    repo_root_from_script,
    utc_now_text,
)


class RepoRootFromScriptTests(unittest.TestCase):
    def test_returns_path_object(self):
        result = repo_root_from_script()
        self.assertIsInstance(result, Path)

    def test_is_absolute(self):
        result = repo_root_from_script()
        self.assertTrue(result.is_absolute())

    def test_scripts_subfolder_exists_under_parent(self):
        result = repo_root_from_script()
        self.assertTrue((result / "scripts").is_dir())


class UtcNowTextTests(unittest.TestCase):
    def test_returns_string(self):
        result = utc_now_text()
        self.assertIsInstance(result, str)

    def test_ends_with_z(self):
        result = utc_now_text()
        self.assertTrue(result.endswith("Z"))

    def test_valid_iso_format(self):
        result = utc_now_text()
        # ISO 8601 without +00:00, replaced with Z
        self.assertRegex(result, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$")

    def test_timestamp_is_utc_based(self):
        """If now is UTC-based, the hour should be at most 24."""
        result = utc_now_text()
        # Extract hour
        match = re.search(r"T(\d{2}):", result)
        self.assertIsNotNone(match)
        hour = int(match.group(1))
        self.assertGreaterEqual(hour, 0)
        self.assertLessEqual(hour, 23)


class BuildParserTests(unittest.TestCase):
    def test_requires_pid(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--hwnd", "0x123"])

    def test_requires_hwnd(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--pid", "1234"])

    def test_default_keys(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        # Default turn keys: typically a, d
        self.assertIsInstance(args.keys, list)
        self.assertGreater(len(args.keys), 0)

    def test_default_input_modes(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertIsInstance(args.input_modes, list)
        self.assertGreater(len(args.input_modes), 0)

    def test_default_hold_ms(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertEqual(125, args.hold_ms)

    def test_default_repeat(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertEqual(1, args.repeat)

    def test_default_post_input_wait_ms(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertEqual(250, args.post_input_wait_ms)

    def test_default_min_yaw_delta_degrees(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertEqual(1.0, args.min_yaw_delta_degrees)

    def test_default_max_coord_delta(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertEqual(0.25, args.max_coord_delta)

    def test_default_proof_max_age_seconds(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertEqual(60, args.proof_max_age_seconds)

    def test_default_output_root_is_none(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertIsNone(args.output_root)

    def test_live_flag_defaults_false(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertFalse(args.live)

    def test_no_cheat_engine_flag_defaults_false(self):
        parser = build_parser()
        args = parser.parse_args(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertFalse(args.refresh_proof_first)
        self.assertFalse(args.refresh_proof_before_each_attempt)

    def test_custom_keys_and_modes(self):
        parser = build_parser()
        args = parser.parse_args([
            "--pid", "5678",
            "--hwnd", "0xDEF",
            "--keys", "a", "d", "w",
            "--input-modes", "foreground-sendinput",
            "--repeat", "3",
            "--hold-ms", "200",
            "--live",
        ])
        self.assertEqual(["a", "d", "w"], args.keys)
        self.assertEqual(["foreground-sendinput"], args.input_modes)
        self.assertEqual(3, args.repeat)
        self.assertEqual(200, args.hold_ms)
        self.assertTrue(args.live)


class MainValueErrorPathTests(unittest.TestCase):
    def test_main_returns_nonzero_on_value_error(self):
        with patch("scripts.profile_turn_keys.TurnKeyProfiler") as mock_profiler_cls:
            mock_profiler = MagicMock()
            mock_profiler_cls.return_value = mock_profiler
            mock_profiler.run.side_effect = ValueError("post-message live input is blocked")

            exit_code = main(["--pid", "1234", "--hwnd", "0xABC", "--live"])
        self.assertEqual(1, exit_code)

    def test_main_error_summary_has_correct_structure(self):
        with patch("scripts.profile_turn_keys.TurnKeyProfiler") as mock_profiler_cls:
            mock_profiler = MagicMock()
            mock_profiler_cls.return_value = mock_profiler
            mock_profiler.run.side_effect = ValueError("custom validation error")

            with patch("builtins.print") as mock_print:
                main(["--pid", "1234", "--hwnd", "0xABC", "--allow-post-message-input"])

                # Extract the printed JSON
                call_args = mock_print.call_args[0][0]
                summary = json.loads(call_args)

        self.assertEqual("blocked-input-backend", summary["status"])
        self.assertFalse(summary["ok"])
        self.assertIn("custom validation error", summary["issues"])
        self.assertEqual("rift_x64", summary["processName"])
        self.assertEqual(1234, summary["processId"])
        self.assertEqual("0xABC", summary["targetWindowHandle"])
        self.assertFalse(summary["live"])
        self.assertFalse(summary["inputSent"])
        self.assertFalse(summary["movementDetected"])
        self.assertTrue(summary["noCheatEngine"])
        self.assertIsInstance(summary["safety"], dict)
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["inputSent"])

    def test_main_error_summary_includes_input_modes(self):
        with patch("scripts.profile_turn_keys.TurnKeyProfiler") as mock_profiler_cls:
            mock_profiler = MagicMock()
            mock_profiler_cls.return_value = mock_profiler
            mock_profiler.run.side_effect = ValueError("blocked")

            with patch("builtins.print") as mock_print:
                main(["--pid", "1234", "--hwnd", "0xABC", "--input-modes", "foreground-sendinput", "post-message"])
                summary = json.loads(mock_print.call_args[0][0])

        self.assertEqual(["foreground-sendinput", "post-message"], summary["inputModes"])
        self.assertFalse(summary["allowPostMessageInput"])

    def test_main_error_includes_allow_post_message_flag(self):
        with patch("scripts.profile_turn_keys.TurnKeyProfiler") as mock_profiler_cls:
            mock_profiler = MagicMock()
            mock_profiler_cls.return_value = mock_profiler
            mock_profiler.run.side_effect = ValueError("blocked")

            with patch("builtins.print") as mock_print:
                main(["--pid", "1234", "--hwnd", "0xABC", "--allow-post-message-input"])
                summary = json.loads(mock_print.call_args[0][0])

        self.assertTrue(summary["allowPostMessageInput"])

    def test_main_error_has_schema_version(self):
        with patch("scripts.profile_turn_keys.TurnKeyProfiler") as mock_profiler_cls:
            mock_profiler = MagicMock()
            mock_profiler_cls.return_value = mock_profiler
            mock_profiler.run.side_effect = ValueError("blocked")

            with patch("builtins.print") as mock_print:
                main(["--pid", "1234", "--hwnd", "0xABC"])
                summary = json.loads(mock_print.call_args[0][0])

        self.assertEqual(1, summary["schemaVersion"])

    def test_main_error_has_generated_at_utc_timestamp(self):
        with patch("scripts.profile_turn_keys.TurnKeyProfiler") as mock_profiler_cls:
            mock_profiler = MagicMock()
            mock_profiler_cls.return_value = mock_profiler
            mock_profiler.run.side_effect = ValueError("blocked")

            with patch("builtins.print") as mock_print:
                main(["--pid", "1234", "--hwnd", "0xABC"])
                summary = json.loads(mock_print.call_args[0][0])

        self.assertIn("generatedAtUtc", summary)
        self.assertRegex(summary["generatedAtUtc"], r"^\d{4}-\d{2}-\d{2}T")


class MainSuccessPathTests(unittest.TestCase):
    def test_main_returns_zero_on_success(self):
        with patch("scripts.profile_turn_keys.TurnKeyProfiler") as mock_profiler_cls:
            mock_profiler = MagicMock()
            mock_profiler_cls.return_value = mock_profiler
            mock_profiler.run.return_value = {
                "schemaVersion": 1,
                "mode": "turn-key-profile",
                "status": "plan-only",
                "ok": True,
                "generatedAtUtc": "2026-05-29T12:00:00.000000Z",
                "inputSent": False,
                "movementDetected": False,
            }

            exit_code = main(["--pid", "1234", "--hwnd", "0xABC"])
        self.assertEqual(0, exit_code)

    def test_main_prints_summary_json(self):
        fake_summary = {
            "schemaVersion": 1,
            "mode": "turn-key-profile",
            "status": "plan-only",
            "ok": True,
            "generatedAtUtc": "2026-05-29T12:00:00.000000Z",
            "inputSent": False,
            "movementDetected": False,
        }
        with patch("scripts.profile_turn_keys.TurnKeyProfiler") as mock_profiler_cls:
            mock_profiler = MagicMock()
            mock_profiler_cls.return_value = mock_profiler
            mock_profiler.run.return_value = fake_summary

            with patch("builtins.print") as mock_print:
                main(["--pid", "1234", "--hwnd", "0xABC"])
                printed = json.loads(mock_print.call_args[0][0])

        self.assertEqual("plan-only", printed["status"])
        self.assertTrue(printed["ok"])

    def test_main_returns_one_when_not_ok(self):
        with patch("scripts.profile_turn_keys.TurnKeyProfiler") as mock_profiler_cls:
            mock_profiler = MagicMock()
            mock_profiler_cls.return_value = mock_profiler
            mock_profiler.run.return_value = {
                "schemaVersion": 1,
                "mode": "turn-key-profile",
                "status": "completed-no-promoted-turn-candidate",
                "ok": False,
                "generatedAtUtc": "2026-05-29T12:00:00.000000Z",
                "inputSent": True,
                "movementDetected": False,
            }

            exit_code = main(["--pid", "1234", "--hwnd", "0xABC", "--live"])
        self.assertEqual(1, exit_code)


if __name__ == "__main__":
    unittest.main()
