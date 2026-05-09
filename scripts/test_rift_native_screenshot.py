from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rift_live_test.commands import JsonCommandResult
from rift_live_test.turn_keys import TurnKeyProfileConfig, TurnKeyProfiler


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_native_screenshot_module():
    path = repo_root() / "scripts" / "rift_native_screenshot.py"
    spec = importlib.util.spec_from_file_location("rift_native_screenshot", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["rift_native_screenshot"] = module
    spec.loader.exec_module(module)
    return module


class RiftNativeScreenshotTests(unittest.TestCase):
    def test_only_numpad_multiply_is_allowed_for_screenshot_key(self) -> None:
        module = load_native_screenshot_module()

        self.assertEqual(module.normalize_key_chord("NUM PAD *"), "numpad_multiply")
        self.assertEqual(module.key_sequence("NUM PAD *"), (0x6A,))
        self.assertEqual(module.key_sequence("numpad_multiply"), (0x6A,))

        with self.assertRaisesRegex(ValueError, "Ctrl\\+P is intentionally disabled"):
            module.normalize_key_chord("ctrl+p")
        with self.assertRaisesRegex(ValueError, "Ctrl\\+P is intentionally disabled"):
            module.normalize_key_chord("control+p")

    def test_turn_key_profiler_native_screenshot_uses_native_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "rift_native_screenshot.py").write_text("# test helper\n", encoding="utf-8")
            profiler = TurnKeyProfiler(
                TurnKeyProfileConfig(
                    repo_root=root,
                    process_id=49504,
                    target_window_handle="0x5121A",
                    capture_screenshots=True,
                    screenshot_backend="native-rift",
                    native_screenshot_key_chord="numpad_multiply",
                    output_root=root / "captures",
                )
            )

            calls: list[list[str]] = []

            def fake_run_json_command(args, *, cwd, label, timeout_seconds):
                calls.append(list(args))
                return JsonCommandResult(
                    label=label,
                    args=list(args),
                    exit_code=0,
                    stdout='{"ok": true}',
                    stderr="",
                    json_data={
                        "ok": True,
                        "status": "captured",
                        "artifactPath": str(root / "shot.jpg"),
                        "keyChord": "numpad_multiply",
                    },
                    json_text='{"ok": true}',
                    parse_error=None,
                )

            with patch("rift_live_test.turn_keys.run_json_command", side_effect=fake_run_json_command):
                preview = profiler._capture_screenshot("001-test", phase="before")

            self.assertIsNotNone(preview)
            assert preview is not None
            self.assertEqual(preview["screenshotBackend"], "native-rift")
            self.assertTrue(preview["usable"])
            self.assertEqual(preview["nativeScreenshotKeyChord"], "numpad_multiply")
            command = calls[0]
            self.assertIn(str(root / "scripts" / "rift_native_screenshot.py"), command)
            self.assertIn("--key-chord", command)
            self.assertEqual(command[command.index("--key-chord") + 1], "numpad_multiply")
            self.assertNotIn("ctrl+p", [part.lower() for part in command])


if __name__ == "__main__":
    unittest.main()
