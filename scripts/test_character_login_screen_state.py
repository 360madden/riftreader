from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from PIL import Image, ImageDraw

from rift_live_test.character_login_screen_state import main


def create_character_select_like_image(path: Path) -> None:
    image = Image.new("RGB", (640, 360), (35, 55, 70))
    draw = ImageDraw.Draw(image)
    # Left character roster panels.
    for index, top in enumerate([5, 52, 99, 147, 195], start=1):
        bbox = [10, top, 140, top + 43]
        draw.rectangle(bbox, fill=(12, 32, 38), outline=(70, 170, 180), width=2)
        draw.line([bbox[0] + 6, top + 10, bbox[2] - 8, top + 10], fill=(230, 220, 130), width=1)
        draw.line([bbox[0] + 6, top + 24, bbox[2] - 34, top + 24], fill=(210, 235, 240), width=1)
        if index == 3:
            draw.rectangle(bbox, outline=(255, 220, 80), width=3)
    # Center character/model area.
    draw.rectangle([245, 75, 425, 321], fill=(35, 85, 120))
    for offset in range(0, 160, 12):
        draw.line([245 + offset, 75, 425 - offset // 2, 321], fill=(55, 150, 185), width=2)
    draw.rectangle([294, 110, 360, 300], fill=(50, 35, 30), outline=(220, 210, 170), width=2)
    # Shard label.
    draw.rectangle([247, 319, 365, 334], fill=(8, 15, 18), outline=(75, 170, 190), width=1)
    draw.line([256, 326, 356, 326], fill=(230, 245, 250), width=1)
    # Play button.
    draw.rectangle([476, 329, 558, 357], fill=(10, 20, 12), outline=(80, 220, 90), width=3)
    draw.line([492, 343, 540, 343], fill=(235, 250, 235), width=3)
    draw.line([490, 348, 542, 348], fill=(105, 235, 105), width=2)
    image.save(path)


class CharacterLoginScreenStateTests(unittest.TestCase):
    def run_classifier(self, root: Path, screenshot: Path, *extra: str) -> tuple[int, dict[str, object]]:
        out = root / "out"
        with redirect_stdout(StringIO()):
            code = main([
                "--repo-root",
                str(root),
                "--screenshot",
                str(screenshot),
                "--output-root",
                str(out),
                "--max-screenshot-age-seconds",
                "999999",
                "--json",
                *extra,
            ])
        summary = json.loads((out / "character-login-screen-state-summary.json").read_text(encoding="utf-8"))
        return code, summary

    def test_character_select_like_screenshot_classifies_without_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            screenshot = root / "character-select.png"
            create_character_select_like_image(screenshot)

            code, summary = self.run_classifier(root, screenshot, "--expect-character-select")

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "classified-character-select")
            self.assertEqual(summary["classification"], "character-selection-not-in-world")
            self.assertTrue(summary["decision"]["safeToUseCharacterSelectClickTargets"])  # type: ignore[index]
            self.assertFalse(summary["safety"]["mouseClickSent"])  # type: ignore[index]
            self.assertFalse(summary["safety"]["movementSent"])  # type: ignore[index]

    def test_blank_screenshot_blocks_when_character_select_expected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            screenshot = root / "blank.png"
            Image.new("RGB", (640, 360), (0, 0, 0)).save(screenshot)

            code, summary = self.run_classifier(root, screenshot, "--expect-character-select")

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("expected-character-select-but-classified", " ".join(summary["blockers"]))
            self.assertFalse(summary["decision"]["canTreatAsInWorld"])  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
