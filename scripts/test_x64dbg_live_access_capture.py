from __future__ import annotations

import ctypes
import unittest

from rift_live_test.x64dbg_live_access_capture import (
    INPUT,
    build_key_lparam,
    clear_all_hardware_breakpoints,
    clear_all_memory_breakpoints,
    exact_target_snapshot,
    install_minimized_x64dbg_launch,
    minimize_windows_for_process,
    parse_virtual_key,
    resume_if_stopped,
)
import rift_live_test.x64dbg_live_access_capture as live_access


def minimal_summary() -> dict:
    return {
        "warnings": [],
        "safety": {
            "goAttempts": 0,
            "hardwareBreakpointSet": True,
            "memoryBreakpointSet": True,
            "liveAttachPolicy": {"maxGoAttempts": 1},
        },
    }


class FakeClient:
    def __init__(self, *, running: bool, go_result: bool = True, wait_result: bool = True) -> None:
        self.running = running
        self.go_result = go_result
        self.wait_result = wait_result
        self.go_calls = 0
        self.clear_calls: list[object] = []

    def is_running(self) -> bool:
        return self.running

    def go(self, *, pass_exceptions: bool, swallow_exceptions: bool) -> bool:
        self.go_calls += 1
        self.running = self.go_result
        self.pass_exceptions = pass_exceptions
        self.swallow_exceptions = swallow_exceptions
        return self.go_result

    def wait_until_running(self, *, timeout: int) -> bool:
        self.wait_timeout = timeout
        return self.wait_result

    def clear_hardware_breakpoint(self, value: object = None) -> bool:
        self.clear_calls.append(value)
        return True

    def clear_memory_breakpoint(self, value: object = None) -> bool:
        self.clear_calls.append(value)
        return True


class FakeProcess:
    pid = 4242


class X64DbgLiveAccessCaptureTests(unittest.TestCase):
    def test_parse_virtual_key_accepts_named_and_numeric_keys(self) -> None:
        self.assertEqual(parse_virtual_key("w"), 0x57)
        self.assertEqual(parse_virtual_key("SPACE"), 0x20)
        self.assertEqual(parse_virtual_key("0x41"), 0x41)

    def test_build_key_lparam_sets_keyup_transition_bits(self) -> None:
        down = build_key_lparam(0x11, key_up=False)
        up = build_key_lparam(0x11, key_up=True)

        self.assertEqual(down & 0xFFFF, 1)
        self.assertEqual((down >> 16) & 0xFF, 0x11)
        self.assertEqual(up & (1 << 30), 1 << 30)
        self.assertEqual(up & (1 << 31), 1 << 31)

    def test_sendinput_input_struct_size_matches_windows_layout(self) -> None:
        expected_size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(INPUT), expected_size)

    def test_resume_if_stopped_uses_single_go_attempt(self) -> None:
        client = FakeClient(running=False)
        summary = minimal_summary()

        resumed = resume_if_stopped(client, summary, reason="test")

        self.assertTrue(resumed)
        self.assertEqual(client.go_calls, 1)
        self.assertEqual(summary["safety"]["goAttempts"], 1)
        self.assertFalse(client.pass_exceptions)
        self.assertFalse(client.swallow_exceptions)

    def test_resume_if_stopped_does_not_go_when_already_running(self) -> None:
        client = FakeClient(running=True)
        summary = minimal_summary()

        resumed = resume_if_stopped(client, summary, reason="test")

        self.assertTrue(resumed)
        self.assertEqual(client.go_calls, 0)
        self.assertEqual(summary["safety"]["goAttempts"], 0)
        self.assertIn("resume-not-needed-target-running:test", summary["warnings"])

    def test_resume_if_stopped_honors_go_budget(self) -> None:
        client = FakeClient(running=False)
        summary = minimal_summary()
        summary["safety"]["goAttempts"] = 1

        resumed = resume_if_stopped(client, summary, reason="test")

        self.assertFalse(resumed)
        self.assertEqual(client.go_calls, 0)
        self.assertIn("resume-skipped-go-budget-exhausted:test", summary["warnings"])

    def test_clear_all_hardware_breakpoints_clears_by_none(self) -> None:
        client = FakeClient(running=True)
        summary = minimal_summary()

        cleared = clear_all_hardware_breakpoints(client, summary, reason="test")

        self.assertTrue(cleared)
        self.assertEqual(client.clear_calls, [None])
        self.assertFalse(summary["safety"]["hardwareBreakpointSet"])

    def test_clear_all_memory_breakpoints_clears_by_none(self) -> None:
        client = FakeClient(running=True)
        summary = minimal_summary()

        cleared = clear_all_memory_breakpoints(client, summary, reason="test")

        self.assertTrue(cleared)
        self.assertEqual(client.clear_calls, [None])
        self.assertFalse(summary["safety"]["memoryBreakpointSet"])

    def test_minimize_windows_skips_when_process_id_is_target(self) -> None:
        result = minimize_windows_for_process(2928, expected_target_pid=2928)

        self.assertFalse(result["attempted"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "process-id-is-target-debuggee")

    def test_exact_target_snapshot_requires_pid_and_hwnd_match(self) -> None:
        original = live_access.enumerate_window_targets
        try:
            live_access.enumerate_window_targets = lambda *, process_name, title_contains: [  # type: ignore[assignment]
                {"pid": 100, "hwndHex": "0x1"},
                {"pid": 200, "hwndHex": "0x2"},
            ]

            target = exact_target_snapshot(process_name="rift_x64", target_pid=200, target_hwnd="2")
        finally:
            live_access.enumerate_window_targets = original  # type: ignore[assignment]

        self.assertEqual(target, {"pid": 200, "hwndHex": "0x2"})

    def test_install_minimized_x64dbg_launch_requests_minimized_popen(self) -> None:
        calls: list[dict] = []

        class FakeX64DbgClientClass:
            def __init__(self) -> None:
                self.x64dbg_path = "C:/Tools/x64dbg.exe"
                self.session_pid = None
                self.attached_session = None

            def attach_session(self, session_pid: int) -> None:
                self.attached_session = session_pid

            def _launch_x64dbg(self) -> None:
                raise AssertionError("original launcher should be patched")

        original_popen = live_access.subprocess.Popen
        original_launch_kwargs = live_access.launch_kwargs
        try:
            live_access.subprocess.Popen = lambda *args, **kwargs: calls.append({"args": args, "kwargs": kwargs}) or FakeProcess()  # type: ignore[assignment]
            live_access.launch_kwargs = lambda *, minimize_window: {"startupinfo": "minimized"}  # type: ignore[assignment]
            summary = {"warnings": [], "x64dbgWindowManagement": {}}

            patched = install_minimized_x64dbg_launch(FakeX64DbgClientClass, summary)
            client = FakeX64DbgClientClass()
            client._launch_x64dbg()
        finally:
            live_access.subprocess.Popen = original_popen  # type: ignore[assignment]
            live_access.launch_kwargs = original_launch_kwargs  # type: ignore[assignment]

        self.assertTrue(patched)
        self.assertEqual(client.session_pid, 4242)
        self.assertEqual(client.attached_session, 4242)
        self.assertEqual(calls[0]["args"], (["C:/Tools/x64dbg.exe"],))
        self.assertEqual(calls[0]["kwargs"]["executable"], "C:/Tools/x64dbg.exe")
        self.assertEqual(calls[0]["kwargs"]["startupinfo"], "minimized")
        self.assertTrue(summary["x64dbgWindowManagement"]["launchMinimizedPatchInstalled"])


if __name__ == "__main__":
    unittest.main()
