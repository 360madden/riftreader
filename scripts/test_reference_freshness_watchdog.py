from __future__ import annotations

import unittest

from rift_live_test.reference_freshness_watchdog import (
    extract_rrapicoord_markers,
    marker_fields,
    marker_is_usable,
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


if __name__ == "__main__":
    unittest.main()
