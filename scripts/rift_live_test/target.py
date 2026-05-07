from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Any


def _parse_hwnd(value: str) -> int:
    return int(str(value).strip(), 0)


def verify_target(
    process_id: int,
    target_window_handle: str,
    expected_process_name: str = "rift_x64",
) -> dict[str, Any]:
    if os.name != "nt":
        return {
            "status": "unsupported-platform",
            "valid": False,
            "processId": process_id,
            "targetWindowHandle": target_window_handle,
            "issues": ["windows_hwnd_verification_required"],
        }

    try:
        hwnd = _parse_hwnd(target_window_handle)
    except (TypeError, ValueError):
        return {
            "status": "invalid-hwnd",
            "valid": False,
            "processId": process_id,
            "targetWindowHandle": target_window_handle,
            "expectedProcessName": expected_process_name,
            "issues": [f"target_window_handle_invalid:{target_window_handle}"],
        }
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    result: dict[str, Any] = {
        "status": "unknown",
        "valid": False,
        "processId": process_id,
        "targetWindowHandle": f"0x{hwnd:X}",
        "expectedProcessName": expected_process_name,
        "issues": [],
    }

    if not user32.IsWindow(ctypes.c_void_p(hwnd)):
        result["status"] = "window-not-found"
        result["issues"].append("target_window_not_found")
        return result

    hwnd_pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(hwnd_pid))
    result["windowProcessId"] = int(hwnd_pid.value)
    if int(hwnd_pid.value) != int(process_id):
        result["status"] = "pid-hwnd-mismatch"
        result["issues"].append(
            f"window_pid_mismatch:windowPid={hwnd_pid.value};expectedPid={process_id}"
        )
        return result

    process_query_limited_information = 0x1000
    handle = kernel32.OpenProcess(
        process_query_limited_information,
        False,
        int(process_id),
    )
    if not handle:
        result["status"] = "process-not-opened"
        result["issues"].append("process_open_failed")
        return result

    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            image_path = buffer.value
            process_name = Path(image_path).stem
            result["processImagePath"] = image_path
            result["processName"] = process_name
            expected = (
                expected_process_name[:-4]
                if expected_process_name.lower().endswith(".exe")
                else expected_process_name
            )
            if process_name.lower() != expected.lower():
                result["status"] = "process-name-mismatch"
                result["issues"].append(
                    f"process_name_mismatch:actual={process_name};expected={expected}"
                )
                return result
        else:
            result["warnings"] = ["process_image_query_failed"]
    finally:
        kernel32.CloseHandle(handle)

    result["status"] = "valid"
    result["valid"] = True
    return result
