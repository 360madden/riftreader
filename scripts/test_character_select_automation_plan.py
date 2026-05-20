from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.character_select_automation_plan import main


def sample_environment(*, client_width: int = 640, client_height: int = 360) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-character-select-automation-environment",
        "status": "captured-read-only-character-select",
        "generatedAtUtc": "2026-05-20T11:15:37Z",
        "target": {
            "processName": "rift_x64",
            "processId": 60636,
            "windowHandle": "0xC51368",
            "windowTitle": "RIFT",
            "processStartUtc": "2026-05-20T11:02:20.5639279Z",
        },
        "window": {
            "clientRectScreen": {
                "left": 13,
                "top": 37,
                "right": 653,
                "bottom": 397,
                "width": client_width,
                "height": client_height,
            },
            "clientSize": {
                "width": client_width,
                "height": client_height,
            },
            "coordinateSystem": "client coordinates, origin top-left of the 640x360 client area",
        },
        "screenState": {
            "classification": "character-selection-not-in-world",
            "selectedCharacter": "ATANK",
            "currentShard": "Deepwood",
            "worldEntryAvailableVisually": True,
            "worldEntryPermittedNow": False,
        },
        "targets": {
            "visibleCharacterSlots": [
                {
                    "slot": 1,
                    "name": "SYRACUSE",
                    "bbox": [10, 5, 140, 48],
                    "clickPoint": [75, 27],
                    "selected": False,
                },
                {
                    "slot": 2,
                    "name": "CEBU",
                    "bbox": [10, 52, 140, 96],
                    "clickPoint": [75, 74],
                    "selected": False,
                },
                {
                    "slot": 3,
                    "name": "ATANK",
                    "bbox": [10, 99, 140, 143],
                    "clickPoint": [75, 121],
                    "selected": True,
                },
            ],
            "selectedCharacter": {
                "slot": 3,
                "name": "ATANK",
                "bbox": [10, 99, 140, 143],
                "clickPoint": [75, 121],
                "selected": True,
            },
            "playButton": {
                "bbox": [476, 329, 558, 357],
                "clickPoint": [517, 343],
                "description": "large lower-right PLAY button; use only after explicit approval to enter world",
            },
        },
        "safety": {
            "movementSent": False,
            "keyInputSent": False,
            "mouseClickSent": False,
            "worldEntryClicked": False,
            "cheatEngineUsed": False,
            "x64dbgAttachStarted": False,
            "savedVariablesUsedAsLiveTruth": False,
        },
        "artifacts": {
            "screenshot": "C:\\RIFT MODDING\\RiftReader\\tools\\rift-game-mcp\\.runtime\\screenshots\\capture.png",
        },
    }


class CharacterSelectAutomationPlanTests(unittest.TestCase):
    def write_env(self, path: Path, document: dict[str, object] | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document or sample_environment(), indent=2), encoding="utf-8")

    def run_plan(self, args: list[str], out: Path) -> tuple[int, dict[str, object]]:
        with redirect_stdout(StringIO()):
            code = main([*args, "--output-root", str(out), "--json"])
        summary = json.loads((out / "character-select-automation-plan-summary.json").read_text(encoding="utf-8"))
        return code, summary

    def test_selected_target_plans_no_character_click_and_no_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env_path = root / "env.json"
            out = root / "plan"
            self.write_env(env_path)

            code, summary = self.run_plan(
                ["--repo-root", str(root), "--env-summary", str(env_path), "--target-character", "ATANK", "--plan-enter-world"],
                out,
            )

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "planned")
            self.assertTrue(summary["selection"]["selectedAlready"])
            actions = [item["action"] for item in summary["plannedActions"]]
            self.assertIn("keep-selected-character", actions)
            self.assertNotIn("click-character-slot", actions)
            play_action = next(item for item in summary["plannedActions"] if item["action"] == "click-play-button")
            self.assertEqual(play_action["clientClick"], [517, 343])
            self.assertTrue(play_action["requiresExplicitApproval"])
            self.assertFalse(play_action["willExecute"])
            self.assertTrue(summary["safety"]["planOnly"])
            self.assertFalse(summary["safety"]["mouseClickSent"])
            self.assertFalse(summary["safety"]["worldEntryClicked"])
            self.assertFalse(summary["safety"]["movementAllowed"])

    def test_unselected_visible_target_plans_slot_click_then_gated_play(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env_path = root / "env.json"
            out = root / "plan"
            self.write_env(env_path)

            code, summary = self.run_plan(
                ["--repo-root", str(root), "--env-summary", str(env_path), "--target-character", "CEBU", "--plan-enter-world"],
                out,
            )

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "planned")
            self.assertFalse(summary["selection"]["selectedAlready"])
            slot_action = next(item for item in summary["plannedActions"] if item["action"] == "click-character-slot")
            self.assertEqual(slot_action["clientClick"], [75, 74])
            self.assertEqual(slot_action["target"]["character"], "CEBU")
            self.assertTrue(slot_action["requiresExplicitApproval"])
            self.assertTrue(slot_action["requiresRecaptureVerification"])
            self.assertFalse(slot_action["willExecute"])
            play_action = next(item for item in summary["plannedActions"] if item["action"] == "click-play-button")
            self.assertEqual(play_action["clientClick"], [517, 343])
            self.assertFalse(play_action["willExecute"])

    def test_unknown_target_blocks_without_click_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env_path = root / "env.json"
            out = root / "plan"
            self.write_env(env_path)

            code, summary = self.run_plan(
                ["--repo-root", str(root), "--env-summary", str(env_path), "--target-character", "MISSING"],
                out,
            )

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("target-character-not-visible", summary["blockers"])
            actions = [item["action"] for item in summary["plannedActions"]]
            self.assertNotIn("click-character-slot", actions)
            self.assertFalse(summary["safety"]["mouseClickSent"])

    def test_client_size_mismatch_blocks_stale_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env_path = root / "env.json"
            out = root / "plan"
            self.write_env(env_path, sample_environment(client_width=800, client_height=600))

            code, summary = self.run_plan(
                ["--repo-root", str(root), "--env-summary", str(env_path), "--target-character", "ATANK"],
                out,
            )

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("client-size-mismatch-expected-640x360", summary["blockers"])
            self.assertFalse(summary["safety"]["mouseClickSent"])

    def test_click_points_outside_client_or_bbox_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env_path = root / "env.json"
            out = root / "plan"
            env = sample_environment()
            targets = env["targets"]  # type: ignore[index]
            targets["playButton"]["clickPoint"] = [700, 343]  # type: ignore[index]
            targets["visibleCharacterSlots"][0]["clickPoint"] = [141, 27]  # type: ignore[index]
            self.write_env(env_path, env)

            code, summary = self.run_plan(
                ["--repo-root", str(root), "--env-summary", str(env_path), "--target-character", "ATANK"],
                out,
            )

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("play-button-click-point-out-of-client-bounds", summary["blockers"])
            self.assertIn("play-button-click-point-outside-bbox", summary["blockers"])
            self.assertIn("character-slot-1-click-point-outside-bbox", summary["blockers"])
            self.assertFalse(summary["safety"]["mouseClickSent"])

    def test_multiple_selected_slots_block_ambiguous_roster_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env_path = root / "env.json"
            out = root / "plan"
            env = sample_environment()
            env["targets"]["visibleCharacterSlots"][0]["selected"] = True  # type: ignore[index]
            self.write_env(env_path, env)

            code, summary = self.run_plan(
                ["--repo-root", str(root), "--env-summary", str(env_path), "--target-character", "ATANK"],
                out,
            )

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("multiple-selected-character-slots", summary["blockers"])
            self.assertFalse(summary["safety"]["mouseClickSent"])

    def test_missing_environment_summary_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = root / "plan"

            code, summary = self.run_plan(["--repo-root", str(root), "--target-character", "ATANK"], out)

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("missing-environment-summary", summary["blockers"])
            self.assertEqual(summary["plannedActions"], [])


if __name__ == "__main__":
    unittest.main()
