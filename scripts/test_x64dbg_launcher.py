from __future__ import annotations

import json
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO

from rift_live_test.x64dbg_launcher import launch_kwargs, main, safety_lines


class X64DbgLauncherTests(unittest.TestCase):
    def test_print_safety_only_does_not_launch(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(["--print-safety-only", "--json"])

        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "safety-only")
        self.assertFalse(result["launched"])
        self.assertFalse(result["safety"]["x64dbgLiveAttachStarted"])
        self.assertTrue(result["safety"]["x64dbgWindowMinimizeRequested"])
        self.assertEqual(result["safety"]["liveAttachPolicy"]["maxLiveAttachSeconds"], 30)

    def test_safety_lines_include_detach_first_guard(self) -> None:
        text = "\n".join(safety_lines())

        self.assertIn("does not attach to RIFT", text)
        self.assertIn("Responding=False", text)
        self.assertIn("detach first", text)

    def test_launch_kwargs_requests_minimized_window_on_windows(self) -> None:
        kwargs = launch_kwargs(minimize_window=True)

        if sys.platform == "win32":
            self.assertIn("startupinfo", kwargs)
            self.assertTrue(kwargs["startupinfo"].dwFlags)
        else:
            self.assertEqual(kwargs, {})

    def test_launch_kwargs_can_disable_minimized_window(self) -> None:
        self.assertEqual(launch_kwargs(minimize_window=False), {})


if __name__ == "__main__":
    unittest.main()
