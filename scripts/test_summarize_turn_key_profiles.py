from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_turn_key_profiles import (
    find_summaries,
    format_counter,
    format_markdown,
    load_json,
    relative,
    repo_root_from_script,
    summarize_attempts,
    summarize_file,
)


class LoadJsonTests(unittest.TestCase):
    def test_loads_valid_json_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "data.json"
            fixture.write_text(json.dumps({"status": "passed", "count": 5}), encoding="utf-8")
            result = load_json(fixture)
        self.assertEqual("passed", result["status"])
        self.assertEqual(5, result["count"])

    def test_raises_on_array_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "arr.json"
            fixture.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_json(fixture)

    def test_raises_on_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_json(Path("/nonexistent/file.json"))

    def test_handles_bom_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "bom.json"
            fixture.write_bytes(b"\xef\xbb\xbf" + json.dumps({"key": "val"}).encode("utf-8"))
            result = load_json(fixture)
        self.assertEqual("val", result["key"])


class SummarizeAttemptsTests(unittest.TestCase):
    def test_empty_summary_returns_zeros(self):
        result = summarize_attempts({})
        self.assertEqual(0, result["attemptCount"])
        self.assertEqual({}, result["classifications"])
        self.assertEqual({}, result["deliveries"])
        self.assertEqual(0.0, result["maxAbsYawDeltaDegrees"])
        self.assertEqual(0.0, result["maxCoordPlanarDelta"])
        self.assertEqual([], result["notableAttempts"])

    def test_single_no_turn_attempt(self):
        result = summarize_attempts({
            "attempts": [
                {
                    "attemptId": 1,
                    "key": "a",
                    "inputMode": "ScanCode",
                    "classification": "no-turn",
                    "inputCommand": {"exitCode": 0},
                }
            ]
        })
        self.assertEqual(1, result["attemptCount"])
        self.assertEqual({"no-turn": 1}, result["classifications"])
        # no-turn with exitCode=0 should not be notable
        self.assertEqual([], result["notableAttempts"])

    def test_classifies_turn_and_non_turn(self):
        result = summarize_attempts({
            "attempts": [
                {"attemptId": 1, "key": "a", "inputMode": "ScanCode", "classification": "no-turn"},
                {"attemptId": 2, "key": "d", "inputMode": "ScanCode", "classification": "turn-candidate"},
                {"attemptId": 3, "key": "d", "inputMode": "ScanCode", "classification": "turn-candidate"},
            ]
        })
        self.assertEqual(3, result["attemptCount"])
        self.assertEqual({"no-turn": 1, "turn-candidate": 2}, result["classifications"])

    def test_tracks_deliveries_from_input_command_dict(self):
        result = summarize_attempts({
            "attempts": [
                {
                    "attemptId": 1,
                    "classification": "turn-candidate",
                    "inputCommand": {
                        "inputDelivery": {"effectiveMode": "ScanCode"},
                    },
                },
                {
                    "attemptId": 2,
                    "classification": "no-turn",
                    "inputCommand": {
                        "inputDelivery": {"effectiveMode": "VirtualKey"},
                    },
                },
            ]
        })
        self.assertEqual({"ScanCode": 1, "VirtualKey": 1}, result["deliveries"])

    def test_missing_inputDelivery_falls_to_unknown(self):
        result = summarize_attempts({
            "attempts": [
                {
                    "attemptId": 1,
                    "classification": "turn-candidate",
                    "inputCommand": {"exitCode": 0},
                }
            ]
        })
        # When inputDelivery key is absent, .get("inputDelivery") returns None
        # and None or {} becomes {} which passes isinstance(dict) check.
        # effectiveMode is then None, which maps to "unknown".
        self.assertEqual({"unknown": 1}, result["deliveries"])

    def test_tracks_yaw_and_coord_deltas(self):
        result = summarize_attempts({
            "attempts": [
                {
                    "attemptId": 1,
                    "classification": "turn-candidate",
                    "yawDeltaDegrees": 5.0,
                    "coordDelta": {"planarDistance": 0.1},
                },
                {
                    "attemptId": 2,
                    "classification": "turn-candidate",
                    "yawDeltaDegrees": -3.0,
                    "coordDelta": {"planarDistance": 0.05},
                },
            ]
        })
        self.assertEqual(5.0, result["maxAbsYawDeltaDegrees"])
        self.assertEqual(0.1, result["maxCoordPlanarDelta"])

    def test_max_abs_yaw_handles_negative(self):
        result = summarize_attempts({
            "attempts": [
                {"attemptId": 1, "classification": "turn", "yawDeltaDegrees": -12.0},
                {"attemptId": 2, "classification": "turn", "yawDeltaDegrees": 8.0},
            ]
        })
        self.assertEqual(12.0, result["maxAbsYawDeltaDegrees"])

    def test_notable_attempts_include_non_zero_exit(self):
        result = summarize_attempts({
            "attempts": [
                {
                    "attemptId": 1,
                    "key": "a",
                    "inputMode": "ScanCode",
                    "classification": "no-turn",
                    "inputCommand": {"exitCode": 1},
                },
                {
                    "attemptId": 2,
                    "key": "d",
                    "inputMode": "ScanCode",
                    "classification": "turn-candidate",
                    "yawDeltaDegrees": 8.0,
                },
            ]
        })
        self.assertEqual(2, len(result["notableAttempts"]))
        self.assertIn("1 a/ScanCode", result["notableAttempts"][0])
        self.assertIn("2 d/ScanCode", result["notableAttempts"][1])

    def test_notable_attempts_limited_to_six(self):
        attempts = [
            {"attemptId": i, "key": "a", "inputMode": "ScanCode",
             "classification": "turn-candidate", "yawDeltaDegrees": 5.0}
            for i in range(10)
        ]
        result = summarize_attempts({"attempts": attempts})
        self.assertEqual(6, len(result["notableAttempts"]))

    def test_skips_non_dict_attempts(self):
        result = summarize_attempts({"attempts": [None, "string", 42]})
        self.assertEqual(0, result["attemptCount"])

    def test_handles_string_classification_gracefully(self):
        result = summarize_attempts({
            "attempts": [{"attemptId": 1, "classification": None}]
        })
        self.assertEqual(1, result["attemptCount"])
        self.assertEqual({"unknown": 1}, result["classifications"])


class FormatCounterTests(unittest.TestCase):
    def test_empty_counter_returns_dash(self):
        self.assertEqual("-", format_counter({}))

    def test_single_entry(self):
        self.assertEqual("no-turn:5", format_counter({"no-turn": 5}))

    def test_multiple_entries_sorted(self):
        result = format_counter({"b": 2, "a": 1, "c": 3})
        self.assertEqual("a:1, b:2, c:3", result)


class RelativeTests(unittest.TestCase):
    def test_none_returns_empty(self):
        self.assertEqual("", relative(None, Path("/root")))

    def test_empty_string_returns_empty(self):
        self.assertEqual("", relative("", Path("/root")))

    def test_relative_path_inside_root(self):
        result = relative("/root/a/b/c.json", Path("/root"))
        normalized = result.replace("\\", "/")
        self.assertEqual("a/b/c.json", normalized)

    def test_path_outside_root_returns_original(self):
        result = relative("/other/path.json", Path("/root"))
        self.assertEqual("/other/path.json", result)

    def test_os_error_falls_back_to_string(self):
        # Path outside filesystem that raises OSError
        result = relative("//invalid?path|", Path("/root"))
        self.assertEqual("//invalid?path|", result)


class SummarizeFileTests(unittest.TestCase):
    def test_file_with_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "profile.json"
            fixture.write_text(json.dumps({
                "generatedAtUtc": "2026-05-29T12:00:00Z",
                "status": "passed",
                "ok": True,
                "processId": 1234,
                "targetWindowHandle": "0xABC",
                "keys": ["a", "d"],
                "inputModes": ["ScanCode", "VirtualKey"],
                "holdMilliseconds": 125,
                "repeats": 1,
                "inputSent": True,
                "movementDetected": False,
                "promotedCandidates": ["candidate-1"],
                "issues": ["warning-1"],
                "attempts": [
                    {"attemptId": 1, "classification": "no-turn"}
                ],
            }), encoding="utf-8")
            result = summarize_file(fixture, Path(tmp))
        self.assertEqual("passed", result["status"])
        self.assertTrue(result["ok"])
        self.assertEqual(["a", "d"], result["keys"])
        self.assertEqual(1, result["attemptCount"])
        self.assertEqual({"no-turn": 1}, result["classifications"])
        self.assertEqual(1, result["promotedCandidateCount"])

    def test_file_raises_on_missing(self):
        with self.assertRaises(FileNotFoundError):
            summarize_file(Path("/nonexistent.json"), Path("/tmp"))


class FindSummariesTests(unittest.TestCase):
    def test_returns_empty_when_no_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = find_summaries(Path(tmp))
        self.assertEqual([], result)

    def test_finds_summary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create the nested glob structure
            run_dir = Path(tmp) / "turn-key-profile-currentpid-1234-20260529"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "turn-key-profile-summary.json").write_text("{}", encoding="utf-8")
            # Non-matching file should be ignored
            (run_dir / "other.json").write_text("{}", encoding="utf-8")
            result = find_summaries(Path(tmp))
        self.assertEqual(1, len(result))
        self.assertIn("turn-key-profile-summary.json", result[0].name)


class FormatMarkdownTests(unittest.TestCase):
    def test_empty_rows_produces_header_and_no_notable(self):
        md = format_markdown([], repo_root_from_script())
        self.assertIn("Turn key profile evidence", md)
        self.assertIn("Notable attempts", md)
        self.assertIn("None; all attempts were no-turn/no-movement", md)

    def test_single_row_with_notable_attempts(self):
        rows = [
            {
                "generatedAtUtc": "2026-05-29T12:00:00Z",
                "summaryFileRelative": "captures/summary.json",
                "summaryFile": "/abs/captures/summary.json",
                "keys": ["a", "d"],
                "inputModes": ["ScanCode"],
                "holdMilliseconds": 125,
                "attemptCount": 2,
                "classifications": {"no-turn": 1, "turn-candidate": 1},
                "deliveries": {"ScanCode": 2},
                "maxAbsYawDeltaDegrees": 8.5,
                "maxCoordPlanarDelta": 0.12,
                "promotedCandidateCount": 1,
                "issues": ["minor-issue"],
                "notableAttempts": [
                    "1 a/ScanCode: turn-candidate, yaw=8.5"
                ],
            }
        ]
        md = format_markdown(rows, repo_root_from_script())
        self.assertIn("Turn key profile evidence", md)
        # Row has notable attempts, so notable section should show them
        self.assertIn("1 a/ScanCode: turn-candidate", md)
        # The "None; all attempts were..." fallback should NOT appear
        self.assertNotIn("None; all attempts", md)
        # The notable section should have the attempt
        self.assertIn("1 a/ScanCode: turn-candidate", md)

    def test_multiple_rows_produce_table_rows(self):
        rows = [
            {
                "generatedAtUtc": "2026-05-29T12:00:00Z",
                "summaryFileRelative": "run1/summary.json",
                "summaryFile": "/abs/run1/summary.json",
                "keys": ["a"],
                "inputModes": ["ScanCode"],
                "holdMilliseconds": 125,
                "attemptCount": 1,
                "classifications": {"no-turn": 1},
                "deliveries": {"ScanCode": 1},
                "maxAbsYawDeltaDegrees": 0.0,
                "maxCoordPlanarDelta": 0.0,
                "promotedCandidateCount": 0,
                "issues": [],
                "notableAttempts": [],
            },
            {
                "generatedAtUtc": "2026-05-29T13:00:00Z",
                "summaryFileRelative": "run2/summary.json",
                "summaryFile": "/abs/run2/summary.json",
                "keys": ["d"],
                "inputModes": ["VirtualKey"],
                "holdMilliseconds": 250,
                "attemptCount": 3,
                "classifications": {"turn-candidate": 3},
                "deliveries": {"VirtualKey": 3},
                "maxAbsYawDeltaDegrees": 15.0,
                "maxCoordPlanarDelta": 0.5,
                "promotedCandidateCount": 2,
                "issues": ["issue-1"],
                "notableAttempts": [
                    "1 d/VirtualKey: turn-candidate, yaw=15.0",
                    "2 d/VirtualKey: turn-candidate, yaw=12.0",
                ],
            },
        ]
        md = format_markdown(rows, repo_root_from_script())
        # Two table rows (plus header + separator = 4 lines in table section)
        self.assertIn("run1/summary.json", md)
        self.assertIn("run2/summary.json", md)
        # Issues column shows formatted issue
        self.assertIn("issue-1", md)
        # Notable section has two entries for second row
        self.assertIn("2 d/VirtualKey: turn-candidate, yaw=12.0", md)


if __name__ == "__main__":
    unittest.main()
