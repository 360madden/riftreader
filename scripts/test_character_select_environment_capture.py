from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from PIL import Image

from rift_live_test.character_select_environment_capture import main


class CharacterSelectEnvironmentCaptureTests(unittest.TestCase):
    def make_image(self, path: Path, *, size: tuple[int, int] = (640, 360)) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color=(10, 20, 30)).save(path)

    def run_capture(self, root: Path, screenshot: Path) -> tuple[int, dict[str, object]]:
        out = root / "out"
        with redirect_stdout(StringIO()):
            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--screenshot",
                    str(screenshot),
                    "--pid",
                    "77728",
                    "--hwnd",
                    "0x8E13A6",
                    "--process-start-utc",
                    "2026-05-20T15:54:23Z",
                    "--module-base",
                    "0x7FF7B77A0000",
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )
        summary = json.loads((out / "character-select-automation-env-summary.json").read_text(encoding="utf-8"))
        return code, summary

    def test_builds_environment_from_fresh_640x360_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            screenshot = root / "capture.png"
            self.make_image(screenshot)

            code, summary = self.run_capture(root, screenshot)

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "captured-read-only-character-select")
            self.assertEqual(summary["target"]["processId"], 77728)
            self.assertEqual(summary["targets"]["playButton"]["clickPoint"], [517, 343])
            self.assertFalse(summary["safety"]["mouseClickSent"])
            self.assertTrue(Path(summary["artifacts"]["annotatedScreenshot"]).is_file())
            self.assertTrue((root / ".riftreader-local" / "character-select-automation-env" / "latest-run.txt").is_file())

    def test_blocks_wrong_screenshot_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            screenshot = root / "capture.png"
            self.make_image(screenshot, size=(800, 600))

            code, summary = self.run_capture(root, screenshot)

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("screenshot-size-mismatch-expected-640x360", summary["blockers"])
            self.assertFalse(summary["safety"]["worldEntryClicked"])


if __name__ == "__main__":
    unittest.main()
