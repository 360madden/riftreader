from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from rift_live_test.reference_freshness_watchdog import (
    extract_rrapicoord_markers,
    marker_fields,
    marker_is_usable,
    summarize_rrapicoord_reference,
    target_mismatches,
    verdict_for,
)


class ReferenceFreshnessWatchdogTests(unittest.TestCase):
    def test_marker_fields_and_usability_require_live_reference_contract(self) -> None:
        fields = marker_fields(
            "RRAPICOORD1|status=pass|source=rift-api|x=1.5|y=2|z=3|savedVariablesUse=none"
        )

        self.assertTrue(marker_is_usable(fields))
        self.assertFalse(marker_is_usable({**fields, "savedVariablesUse": "post-save"}))
        self.assertFalse(marker_is_usable({**fields, "status": "starting"}))

    def test_extract_rrapicoord_markers_from_scan_preview(self) -> None:
        markers = extract_rrapicoord_markers(
            {
                "Hits": [
                    {
                        "Context": {
                            "AsciiPreview": (
                                "xx RRAPICOORD1|status=pass|source=rift-api|"
                                "x=1|y=2|z=3|savedVariablesUse=none yy"
                            )
                        }
                    }
                ]
            }
        )

        self.assertEqual(len(markers), 1)
        self.assertTrue(markers[0]["usable"])

    def test_target_mismatches_accepts_exe_suffix_and_hwnd_formats(self) -> None:
        mismatches = target_mismatches(
            {"processName": "rift_x64", "pid": 2928, "hwnd": "0xC0994"},
            {"processName": "rift_x64.exe", "pid": 2928, "hwnd": "788884"},
        )

        self.assertEqual(mismatches, [])

    def test_verdict_prefers_available_fresh_surface(self) -> None:
        self.assertEqual(verdict_for({"usable": True}, {"usable": False}), "fresh-reference-ready:chromalink")
        self.assertEqual(verdict_for({"usable": False}, {"usable": True}), "fresh-reference-ready:rrapicoord")
        self.assertEqual(verdict_for({"usable": False}, {"usable": False}), "blocked-fresh-reference-unavailable")

    def test_summarize_rrapicoord_reference_accepts_current_live_reference(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "reference.json"
            path.write_text(
                """
{
  "source": "rrapicoord1-memory-scan",
  "captured_at_utc": "2999-01-01T00:00:00Z",
  "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
  "marker": {
    "status": "pass",
    "source": "rift-api",
    "seq": 10,
    "sampledAt": 12.5,
    "raw": "RRAPICOORD1|status=pass|source=rift-api|x=1|y=2|z=3|savedVariablesUse=none"
  },
  "processId": 2928,
  "processName": "rift_x64",
  "targetWindowHandle": "0xC0994",
  "noCheatEngine": true,
  "movementSent": false,
  "savedVariablesUse": "none"
}
""",
                encoding="utf-8",
            )

            summary = summarize_rrapicoord_reference(
                path,
                root,
                {"processName": "rift_x64", "pid": 2928, "hwnd": "0xC0994"},
                max_age_seconds=300.0,
            )

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertTrue(summary["usable"])
        self.assertEqual(summary["sourceKind"], "rrapicoord-reference-file")


if __name__ == "__main__":
    unittest.main()
