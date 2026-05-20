from __future__ import annotations

import unittest

from PIL import Image, ImageDraw

from rift_live_test.fast_world_launch import (
    ProcessInfo,
    benchmark_mode_options,
    classify_rift_client_image,
    duplicate_rift_process_blocker,
    existing_rift_same_account_launch_blocker,
    find_glyph_play_button,
    loading_or_transition_score,
    modal_dialog_score,
    scale_client_point,
    wscript_launcher_script_text,
    world_hud_score,
)


class FastWorldLaunchTests(unittest.TestCase):
    def test_find_glyph_play_button_detects_upper_right_yellow_button(self) -> None:
        image = Image.new("RGB", (1160, 730), (35, 20, 55))
        draw = ImageDraw.Draw(image)
        draw.rectangle([870, 72, 1115, 126], fill=(255, 205, 0))

        result = find_glyph_play_button(image)

        self.assertTrue(result["found"])
        self.assertEqual(result["centerWindowPoint"], [993, 100])
        self.assertGreater(result["pixelCount"], 10000)

    def test_find_glyph_play_button_rejects_missing_button(self) -> None:
        image = Image.new("RGB", (1160, 730), (35, 20, 55))

        result = find_glyph_play_button(image)

        self.assertFalse(result["found"])
        self.assertIn("yellow-play-pixel-count-too-low", result["reason"])

    def test_world_hud_score_passes_synthetic_hud_regions(self) -> None:
        image = Image.new("RGB", (640, 360), (20, 25, 30))
        draw = ImageDraw.Draw(image)
        draw.rectangle([180, 296, 468, 359], fill=(30, 170, 50))
        draw.rectangle([493, 0, 639, 136], fill=(20, 95, 25))

        score = world_hud_score(image)

        self.assertTrue(score["passed"])
        self.assertGreaterEqual(score["score"], 0.65)

    def test_world_hud_score_rejects_plain_character_select_like_frame(self) -> None:
        image = Image.new("RGB", (640, 360), (40, 90, 110))
        draw = ImageDraw.Draw(image)
        draw.rectangle([476, 329, 558, 357], fill=(30, 130, 70))

        score = world_hud_score(image)

        self.assertFalse(score["passed"])

    def test_loading_letterbox_blocks_in_world_classification(self) -> None:
        image = Image.new("RGB", (640, 360), (50, 120, 150))
        draw = ImageDraw.Draw(image)
        draw.rectangle([180, 296, 468, 359], fill=(30, 170, 50))
        draw.rectangle([493, 0, 639, 136], fill=(20, 95, 25))
        draw.rectangle([0, 0, 639, 7], fill=(0, 0, 0))
        draw.rectangle([0, 352, 639, 359], fill=(0, 0, 0))

        loading = loading_or_transition_score(image)
        classification = classify_rift_client_image(image)

        self.assertTrue(loading["passed"])
        self.assertEqual(classification["classification"], "loading-or-transition")

    def test_modal_dialog_blocks_launch_classification(self) -> None:
        image = Image.new("RGB", (640, 360), (6, 8, 14))
        draw = ImageDraw.Draw(image)
        draw.rectangle([220, 150, 420, 215], fill=(20, 22, 24))
        draw.rectangle([292, 190, 356, 204], fill=(20, 140, 110))
        draw.rectangle([300, 194, 348, 199], fill=(15, 180, 145))

        modal = modal_dialog_score(image)
        classification = classify_rift_client_image(image)

        self.assertTrue(modal["passed"])
        self.assertEqual(classification["classification"], "modal-dialog-blocker")

    def test_scale_client_point_preserves_base_and_scales_larger_client(self) -> None:
        self.assertEqual(scale_client_point((517, 343), width=640, height=360), [517, 343])
        self.assertEqual(scale_client_point((517, 343), width=1280, height=720), [1034, 686])

    def test_wscript_launcher_script_can_run_shortcut_or_glyph_exe(self) -> None:
        script = wscript_launcher_script_text(
            glyph_exe=__import__("pathlib").Path(r"C:\Program Files (x86)\Glyph\GlyphClientApp.exe"),
            shortcut=None,
        )

        self.assertIn('CreateObject("WScript.Shell")', script)
        self.assertIn("GlyphClientApp.exe", script)
        self.assertIn("-game 1", script)

    def test_duplicate_rift_process_blocker_fails_closed(self) -> None:
        blocker = duplicate_rift_process_blocker(
            [
                ProcessInfo("GlyphClientApp.exe", 10, 1),
                ProcessInfo("rift_x64.exe", 20, 10),
                ProcessInfo("rift_x64.exe", 30, 10),
            ]
        )

        self.assertIsNotNone(blocker)
        assert blocker is not None
        self.assertEqual(blocker["blocker"], "multiple-rift-clients-detected")
        self.assertEqual([item["processId"] for item in blocker["processes"]], [20, 30])

    def test_duplicate_rift_process_blocker_allows_zero_or_one_rift(self) -> None:
        self.assertIsNone(duplicate_rift_process_blocker([]))
        self.assertIsNone(duplicate_rift_process_blocker([ProcessInfo("rift_x64.exe", 20, 10)]))

    def test_same_account_launch_blocker_blocks_any_existing_rift_client(self) -> None:
        blocker = existing_rift_same_account_launch_blocker(
            [
                ProcessInfo("GlyphClientApp.exe", 10, 1),
                ProcessInfo("rift_x64.exe", 20, 10),
            ]
        )

        self.assertIsNotNone(blocker)
        assert blocker is not None
        self.assertEqual(blocker["blocker"], "same-account-rift-client-already-running")
        self.assertEqual(blocker["policy"], "refuse-glyph-play-while-any-rift-client-exists")

    def test_same_account_launch_blocker_allows_no_existing_rift_client(self) -> None:
        self.assertIsNone(existing_rift_same_account_launch_blocker([ProcessInfo("GlyphClientApp.exe", 10, 1)]))

    def test_benchmark_mode_options_define_named_modes(self) -> None:
        self.assertEqual(
            benchmark_mode_options("warm-glyph-after-game-kill"),
            {"requireExistingGlyph": True, "killExistingRiftFirst": True, "requireNoGlyph": False},
        )
        self.assertEqual(
            benchmark_mode_options("warm-glyph"),
            {"requireExistingGlyph": True, "killExistingRiftFirst": False, "requireNoGlyph": False},
        )
        self.assertEqual(
            benchmark_mode_options("true-cold"),
            {"requireExistingGlyph": False, "killExistingRiftFirst": False, "requireNoGlyph": True},
        )


if __name__ == "__main__":
    unittest.main()
