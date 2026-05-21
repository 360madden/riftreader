from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from rift_live_test import fast_world_launch as fwl
from rift_live_test.fast_world_launch import (
    ProcessInfo,
    WindowInfo,
    benchmark_mode_options,
    build_summary,
    classify_rift_client_image,
    duplicate_rift_process_blocker,
    existing_rift_new_launch_blocker,
    existing_rift_same_account_launch_blocker,
    find_glyph_play_button,
    loading_or_transition_score,
    modal_dialog_score,
    scale_client_point,
    wscript_launcher_script_text,
    world_hud_score,
)


class FastWorldLaunchTests(unittest.TestCase):
    def make_rift_window(self, *, process_id: int = 20, visible: bool = True) -> WindowInfo:
        return WindowInfo(
            window_handle=0x2C0B22,
            process_id=process_id,
            title="RIFT",
            class_name="TWNClientFramework",
            is_visible=visible,
            is_minimized=False,
            window_rect={"left": 17, "top": 18, "right": 673, "bottom": 417, "width": 656, "height": 399},
            client_rect={"left": 0, "top": 0, "right": 640, "bottom": 360, "width": 640, "height": 360},
            client_origin={"x": 25, "y": 49},
        )

    def make_glyph_window(self, *, process_id: int = 10) -> WindowInfo:
        return WindowInfo(
            window_handle=0xB0CE6,
            process_id=process_id,
            title="Glyph",
            class_name="Qt5QWindowIcon",
            is_visible=True,
            is_minimized=False,
            window_rect={"left": 14, "top": 237, "right": 1174, "bottom": 967, "width": 1160, "height": 730},
            client_rect={"left": 0, "top": 0, "right": 1160, "bottom": 730, "width": 1160, "height": 730},
            client_origin={"x": 14, "y": 237},
        )

    def make_in_world_image(self) -> Image.Image:
        image = Image.new("RGB", (640, 360), (20, 25, 30))
        draw = ImageDraw.Draw(image)
        draw.rectangle([180, 296, 468, 359], fill=(30, 170, 50))
        draw.rectangle([493, 0, 639, 136], fill=(20, 95, 25))
        return image

    def build_fast_launch_summary(
        self,
        *,
        processes: list[ProcessInfo],
        windows: list[WindowInfo],
        image: Image.Image | None = None,
        dry_run: bool = False,
        timeout_seconds: float = 0.2,
    ) -> dict:
        with TemporaryDirectory() as temp_dir:
            patches = [
                patch.object(fwl.os, "name", "nt"),
                patch.object(fwl, "collect_processes", return_value=processes),
                patch.object(fwl, "collect_windows_for_pids", return_value=windows),
            ]
            if image is not None:
                patches.append(patch.object(fwl, "capture_window_image", return_value=image))
            with patches[0], patches[1], patches[2]:
                if len(patches) == 4:
                    with patches[3]:
                        return build_summary(
                            repo_root=Path.cwd(),
                            output_root=Path(temp_dir),
                            dry_run=dry_run,
                            benchmark_mode="auto",
                            require_existing_glyph=False,
                            kill_existing_rift_first=False,
                            start_method="wscript",
                            glyph_exe=Path(__file__).resolve(),
                            shortcut=None,
                            timeout_seconds=timeout_seconds,
                            poll_interval_seconds=0.01,
                            launcher_ready_timeout_seconds=0.01,
                            rift_window_timeout_seconds=0.01,
                            world_load_timeout_seconds=0.01,
                            allow_fixed_glyph_click_fallback=False,
                        )
                return build_summary(
                    repo_root=Path.cwd(),
                    output_root=Path(temp_dir),
                    dry_run=dry_run,
                    benchmark_mode="auto",
                    require_existing_glyph=False,
                    kill_existing_rift_first=False,
                    start_method="wscript",
                    glyph_exe=Path(__file__).resolve(),
                    shortcut=None,
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=0.01,
                    launcher_ready_timeout_seconds=0.01,
                    rift_window_timeout_seconds=0.01,
                    world_load_timeout_seconds=0.01,
                    allow_fixed_glyph_click_fallback=False,
                )

    def assert_no_unsafe_side_effects(self, summary: dict) -> None:
        safety = summary["safety"]
        self.assertFalse(safety["movementSent"])
        self.assertFalse(safety["keyInputSent"])
        self.assertFalse(safety["reloaduiSent"])
        self.assertTrue(safety["noCheatEngine"])
        self.assertFalse(safety["x64dbgAttachStarted"])
        self.assertFalse(safety["providerWrites"])
        self.assertFalse(safety["gitMutation"])

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

    def test_existing_rift_new_launch_blocker_includes_process_and_window_evidence(self) -> None:
        blocker = existing_rift_new_launch_blocker(
            [ProcessInfo("rift_x64.exe", 20, 10)],
            [self.make_rift_window()],
            reason="unit-test",
        )

        self.assertEqual(blocker["blocker"], "existing-rift-client-present-new-launch-blocked")
        self.assertEqual(blocker["processes"][0]["processId"], 20)
        self.assertEqual(blocker["windows"][0]["windowHandle"], "0x2C0B22")

    def test_existing_rift_without_visible_window_blocks_before_launcher_start(self) -> None:
        summary = self.build_fast_launch_summary(
            processes=[ProcessInfo("rift_x64.exe", 20, 10)],
            windows=[],
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("existing-rift-client-present-new-launch-blocked", summary["blockers"])
        self.assertFalse(summary["existingClientReused"])
        self.assertFalse(summary["safety"]["launchAttempted"])
        self.assertFalse(summary["safety"]["launcherButtonPressed"])
        self.assertFalse(summary["safety"]["worldEntryClicked"])
        self.assert_no_unsafe_side_effects(summary)

    def test_existing_rift_visible_in_world_reuses_client_without_launcher_or_clicks(self) -> None:
        summary = self.build_fast_launch_summary(
            processes=[ProcessInfo("GlyphClientApp.exe", 10, 1), ProcessInfo("rift_x64.exe", 20, 10)],
            windows=[self.make_rift_window(process_id=20), self.make_glyph_window(process_id=10)],
            image=self.make_in_world_image(),
        )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["state"], "existing-client-in-world")
        self.assertTrue(summary["existingClientReused"])
        self.assertIsNone(summary["launchAttempt"])
        self.assertFalse(summary["safety"]["launchAttempted"])
        self.assertFalse(summary["safety"]["launcherButtonPressed"])
        self.assertFalse(summary["safety"]["worldEntryClicked"])
        self.assert_no_unsafe_side_effects(summary)

    def test_existing_rift_and_glyph_play_visible_blocks_before_glyph_play_click(self) -> None:
        summary = self.build_fast_launch_summary(
            processes=[ProcessInfo("GlyphClientApp.exe", 10, 1), ProcessInfo("rift_x64.exe", 20, 10)],
            windows=[self.make_glyph_window(process_id=10)],
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("existing-rift-client-present-new-launch-blocked", summary["blockers"])
        self.assertFalse(summary["safety"]["launchAttempted"])
        self.assertFalse(summary["safety"]["launcherButtonPressed"])
        self.assertFalse(summary["safety"]["worldEntryClicked"])
        self.assert_no_unsafe_side_effects(summary)

    def test_no_existing_rift_preserves_dry_run_launch_plan_behavior(self) -> None:
        summary = self.build_fast_launch_summary(processes=[ProcessInfo("GlyphClientApp.exe", 10, 1)], windows=[], dry_run=True)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("dry-run-no-launch-attempt-sent", summary["blockers"])
        self.assertFalse(summary["existingClientReused"])
        self.assertFalse(summary["safety"]["launcherButtonPressed"])
        self.assertFalse(summary["safety"]["worldEntryClicked"])
        self.assert_no_unsafe_side_effects(summary)

    def test_duplicate_existing_rift_processes_block_before_launcher_start(self) -> None:
        summary = self.build_fast_launch_summary(
            processes=[ProcessInfo("rift_x64.exe", 20, 10), ProcessInfo("rift_x64.exe", 30, 10)],
            windows=[],
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("multiple-rift-clients-detected", summary["blockers"])
        self.assertFalse(summary["safety"]["launchAttempted"])
        self.assertFalse(summary["safety"]["launcherButtonPressed"])
        self.assertFalse(summary["safety"]["worldEntryClicked"])
        self.assert_no_unsafe_side_effects(summary)

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
