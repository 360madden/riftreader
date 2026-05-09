from __future__ import annotations

import unittest

from rift_live_test.visual_gate_status import (
    VISUAL_GATE_BLOCKED_CAPTURE,
    VISUAL_GATE_BLOCKED_TARGET,
    VISUAL_GATE_PASSED,
    _focus_envelope_confirms_foreground,
    build_visual_gate_recovery_recommendations,
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
        self.assertEqual([], verdict["captureFailureClassifications"])

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
        self.assertIn("desktop-copyfromscreen-invalid-handle", verdict["captureFailureClassifications"])

    def test_records_access_denied_alongside_black_content(self) -> None:
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
        self.assertIn("capture-methods-return-black-or-flat-content", verdict["blockers"])
        self.assertEqual(
            [
                "desktop-capture-access-denied",
                "capture-methods-return-black-or-flat-content",
            ],
            verdict["captureFailureClassifications"],
        )

    def test_records_multiple_capture_failure_classes(self) -> None:
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
                    "label": "dxgi-desktop-duplication",
                    "exitCode": 1,
                    "json": {"Message": "HRESULT: [0x80070005], ApiCode: [E_ACCESSDENIED], Message: [Access is denied.]"},
                },
            ],
        )

        self.assertEqual(VISUAL_GATE_BLOCKED_CAPTURE, verdict["status"])
        self.assertEqual(
            [
                "desktop-capture-access-denied",
                "desktop-copyfromscreen-invalid-handle",
            ],
            verdict["captureFailureClassifications"],
        )
        self.assertIn("desktop-capture-access-denied", verdict["blockers"])
        self.assertIn("desktop-copyfromscreen-invalid-handle", verdict["blockers"])

    def test_capture_blocker_recommendations_keep_input_blocked(self) -> None:
        recommendations = build_visual_gate_recovery_recommendations(
            [
                "desktop-capture-access-denied",
                "desktop-copyfromscreen-invalid-handle",
            ]
        )

        ids = [item["id"] for item in recommendations]
        self.assertIn("restore-interactive-desktop-capture", ids)
        self.assertIn("keep-live-input-blocked", ids)

    def test_focus_exit_zero_without_foreground_is_not_confirmed(self) -> None:
        self.assertFalse(
            _focus_envelope_confirms_foreground(
                {
                    "label": "focus-window",
                    "exitCode": 0,
                    "json": {"isForeground": False, "isVisible": True},
                }
            )
        )

    def test_focus_not_foreground_gets_restore_focus_recommendation(self) -> None:
        recommendations = build_visual_gate_recovery_recommendations(["focus-window-not-foreground"])

        ids = [item["id"] for item in recommendations]
        self.assertIn("restore-focus", ids)
        self.assertIn("keep-live-input-blocked", ids)

    def test_focus_not_foreground_does_not_add_generic_focus_failed(self) -> None:
        verdict = build_visual_gate_verdict(
            target_resolved=True,
            focus_ok=False,
            attempts=[],
            existing_blockers=["focus-window-not-foreground"],
        )

        self.assertIn("focus-window-not-foreground", verdict["blockers"])
        self.assertNotIn("focus-window-failed", verdict["blockers"])


if __name__ == "__main__":
    unittest.main()
