from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.x64dbg_preflight import choose_target, main, normalize_hwnd, title_matches


class X64DbgPreflightTests(unittest.TestCase):
    def test_normalize_hwnd_formats_hex(self) -> None:
        self.assertEqual(normalize_hwnd("123"), "0x7B")
        self.assertEqual(normalize_hwnd("0xabc"), "0xABC")
        self.assertIsNone(normalize_hwnd(None))

    def test_title_match_is_case_insensitive(self) -> None:
        self.assertTrue(title_matches("RIFT", "rift"))
        self.assertFalse(title_matches("Other", "rift"))

    def test_choose_target_blocks_multiple_without_exact_target(self) -> None:
        candidates = [
            {"pid": 1, "hwndHex": "0x1"},
            {"pid": 2, "hwndHex": "0x2"},
        ]

        selected, blockers, warnings = choose_target(candidates, target_pid=None, target_hwnd=None)

        self.assertIsNone(selected)
        self.assertIn("multiple-windowed-targets-found:2", blockers)
        self.assertEqual(warnings, [])

    def test_choose_target_exact_pid_hwnd(self) -> None:
        candidates = [
            {"pid": 1, "hwndHex": "0x1"},
            {"pid": 2, "hwndHex": "0x2"},
        ]

        selected, blockers, warnings = choose_target(candidates, target_pid=2, target_hwnd="0x2")

        self.assertEqual(selected, {"pid": 2, "hwndHex": "0x2"})
        self.assertEqual(blockers, [])
        self.assertEqual(warnings, [])

    def test_self_test_writes_no_attach_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "preflight"
            with redirect_stdout(StringIO()):
                code = main(["--self-test", "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertFalse(summary["safety"]["processAttachOrMemoryReadStarted"])
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertEqual(summary["selectedTarget"]["moduleBaseAddressHex"], "0x7FF796B50000")
            self.assertTrue((out / "summary.md").is_file())
            self.assertTrue((out / "targets.json").is_file())


if __name__ == "__main__":
    unittest.main()
