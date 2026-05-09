from __future__ import annotations

import unittest

from rift_live_test.visual_gate_status import (
    VISUAL_GATE_BLOCKED_CAPTURE,
    VISUAL_GATE_BLOCKED_TARGET,
    VISUAL_GATE_PASSED,
    build_visual_gate_verdict,
)


class VisualGateStatusTests(unittest.TestCase):
    def test_passes_when_target_focus_and_capture_are_usable(self) -> None:
        verdict = build_visual_gate_verdict(
            target_resolved=True,
            focus_ok=True,
            attempts=[
                {
                    "label": "rift-mcp-copyfromscreen-capture",
                    "exitCode": 0,
                    "json": {
                        "screenshotPath": "capture.png",
                        "imageSize": {"width": 100, "height": 50},
                    },
                }
            ],
        )

        self.assertEqual(VISUAL_GATE_PASSED, verdict["status"])
        self.assertTrue(verdict["readyForLiveInput"])
        self.assertEqual("rift-mcp-copyfromscreen-capture", verdict["usableCaptureMethod"])

    def test_blocks_when_target_is_missing(self) -> None:
        verdict = build_visual_gate_verdict(
            target_resolved=False,
            focus_ok=False,
            attempts=[
                {
                    "label": "inspect-window",
                    "exitCode": 1,
                    "stderr": "No windowed process named 'rift_x64' was found.",
                    "json": None,
                }
            ],
        )

        self.assertEqual(VISUAL_GATE_BLOCKED_TARGET, verdict["status"])
        self.assertFalse(verdict["readyForLiveInput"])
        self.assertIn("target-window-not-resolved", verdict["blockers"])

    def test_classifies_copyfromscreen_invalid_handle(self) -> None:
        verdict = build_visual_gate_verdict(
            target_resolved=True,
            focus_ok=True,
            attempts=[
                {
                    "label": "copyfromscreen-sanity",
                    "exitCode": 0,
                    "json": {
                        "attempts": [
                            {
                                "name": "desktop-sanity",
                                "ok": False,
                                "error": 'Exception calling "CopyFromScreen" with "5" argument(s): "The handle is invalid."',
                            }
                        ]
                    },
                },
                {
                    "label": "printwindow-capture",
                    "exitCode": 1,
                    "stderr": "PrintWindow capture appears black/unusable.",
                    "json": None,
                },
            ],
        )

        self.assertEqual(VISUAL_GATE_BLOCKED_CAPTURE, verdict["status"])
        self.assertFalse(verdict["readyForLiveInput"])
        self.assertIn("desktop-copyfromscreen-invalid-handle", verdict["blockers"])

    def test_access_denied_takes_precedence_over_black_content(self) -> None:
        verdict = build_visual_gate_verdict(
            target_resolved=True,
            focus_ok=True,
            attempts=[
                {
                    "label": "wgc-window",
                    "exitCode": 2,
                    "json": {"Usable": False, "Message": "Captured a frame, but pixel statistics look black/flat/transparent."},
                },
                {
                    "label": "dxgi-desktop-duplication",
                    "exitCode": 1,
                    "json": {"Message": "HRESULT: [0x80070005], ApiCode: [E_ACCESSDENIED], Message: [Access is denied.]"},
                },
            ],
        )

        self.assertEqual(VISUAL_GATE_BLOCKED_CAPTURE, verdict["status"])
        self.assertIn("desktop-capture-access-denied", verdict["blockers"])


if __name__ == "__main__":
    unittest.main()
