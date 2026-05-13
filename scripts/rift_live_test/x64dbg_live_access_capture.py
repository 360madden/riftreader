from __future__ import annotations

import argparse
import ctypes
import json
import math
import struct
import threading
import time
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_safety import (
    DEFAULT_MAX_GO_ATTEMPTS,
    DEFAULT_MAX_LIVE_ATTACH_SECONDS,
    DEFAULT_UNRESPONSIVE_ABORT_SECONDS,
    live_attach_policy,
    validate_live_attach_policy,
)


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_X64DBG_PATH = Path(r"C:\RIFT MODDING\Tools\x64dbg\release\x64\x64dbg.exe")
DEFAULT_BREAKPOINT_TIMEOUT_SECONDS = 8
DEFAULT_DETACH_TIMEOUT_SECONDS = 10
MAX_STIMULUS_PULSE_MS = 250
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
MAPVK_VK_TO_VSC = 0
SW_RESTORE = 9
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

VIRTUAL_KEYS = {
    "W": 0x57,
    "A": 0x41,
    "S": 0x53,
    "D": 0x44,
    "Q": 0x51,
    "E": 0x45,
    "SPACE": 0x20,
}


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_int(value: str) -> int:
    return int(value, 0)


def parse_virtual_key(value: str) -> int:
    text = value.strip()
    if not text:
        raise ValueError("stimulus key cannot be empty")
    upper = text.upper()
    if upper in VIRTUAL_KEYS:
        return VIRTUAL_KEYS[upper]
    return int(text, 0)


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):X}"


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        return value
    if hasattr(value, "__dict__"):
        return {str(key): to_jsonable(item) for key, item in vars(value).items() if not str(key).startswith("_")}
    return str(value)


def read_json_file(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return document if isinstance(document, dict) else None


def memory_triplet(data: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {
        "byteCount": len(data),
        "bytesHex": data.hex(),
        "x": None,
        "y": None,
        "z": None,
    }
    if len(data) >= 12:
        x, y, z = struct.unpack("<fff", data[:12])
        result.update({"x": x, "y": y, "z": z})
    return result


def ascii_preview(data: bytes) -> str:
    return "".join(chr(byte) if 32 <= byte < 127 else "." for byte in data)


def float_triplet_preview(data: bytes, *, max_items: int = 8) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for offset in range(0, max(0, len(data) - 11)):
        try:
            x, y, z = struct.unpack_from("<fff", data, offset)
        except struct.error:
            break
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            continue
        if max(abs(x), abs(y), abs(z)) > 100000:
            continue
        if max(abs(x), abs(y), abs(z)) < 1:
            continue
        result.append({"offset": offset, "offsetHex": int_hex(offset), "x": x, "y": y, "z": z})
        if len(result) >= max_items:
            break
    return result


def memory_preview(client: Any, address: int, *, size: int = 128) -> dict[str, Any]:
    data = bytes(client.read_memory(address, size))
    return {
        "address": int_hex(address),
        "byteCount": len(data),
        "bytesHex": data.hex(),
        "asciiPreview": ascii_preview(data),
        "floatTriplets": float_triplet_preview(data),
    }


def build_key_lparam(scan_code: int, *, key_up: bool) -> int:
    lparam = 1 | ((scan_code & 0xFF) << 16)
    if key_up:
        lparam |= 1 << 30
        lparam |= 1 << 31
    return lparam


def load_user32_for_input() -> Any:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL
    return user32


def load_kernel32_for_focus() -> Any:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    return kernel32


def window_pid_thread(user32: Any, hwnd: int) -> tuple[int, int]:
    pid = wintypes.DWORD()
    thread_id = int(user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid)))
    return int(pid.value), thread_id


def foreground_snapshot(user32: Any) -> dict[str, Any]:
    hwnd = int(user32.GetForegroundWindow())
    if hwnd <= 0 or not user32.IsWindow(wintypes.HWND(hwnd)):
        return {"hwnd": None, "hwndValue": 0, "pid": None, "threadId": None}
    pid, thread_id = window_pid_thread(user32, hwnd)
    return {"hwnd": int_hex(hwnd), "hwndValue": hwnd, "pid": pid, "threadId": thread_id}


def focus_attempt_record(
    *,
    tier: str,
    attempt: int,
    before: dict[str, Any],
    after: dict[str, Any],
    restore_ok: bool,
    bring_to_top_ok: bool,
    set_foreground_ok: bool,
    attach_results: list[dict[str, Any]] | None = None,
    detach_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "tier": tier,
        "attempt": attempt,
        "restoreOk": restore_ok,
        "bringToTopOk": bring_to_top_ok,
        "setForegroundOk": set_foreground_ok,
        "attachThreadInput": attach_results or [],
        "detachThreadInput": detach_results or [],
        "before": before,
        "after": after,
    }


def foreground_matches(snapshot: dict[str, Any], *, hwnd: int, expected_pid: int) -> bool:
    return snapshot.get("hwndValue") == hwnd and snapshot.get("pid") == expected_pid


def request_exact_foreground(
    user32: Any,
    kernel32: Any,
    *,
    hwnd: int,
    expected_pid: int,
    settle_ms: int = 100,
    simple_attempts: int = 3,
    attach_attempts: int = 2,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    hwnd_value = wintypes.HWND(hwnd)

    for attempt in range(1, max(1, simple_attempts) + 1):
        before = foreground_snapshot(user32)
        restore_ok = bool(user32.ShowWindow(hwnd_value, SW_RESTORE))
        bring_to_top_ok = bool(user32.BringWindowToTop(hwnd_value))
        set_foreground_ok = bool(user32.SetForegroundWindow(hwnd_value))
        time.sleep(max(0, settle_ms) / 1000.0)
        after = foreground_snapshot(user32)
        attempts.append(
            focus_attempt_record(
                tier="showwindow-bringwindowtotop-setforegroundwindow",
                attempt=attempt,
                before=before,
                after=after,
                restore_ok=restore_ok,
                bring_to_top_ok=bring_to_top_ok,
                set_foreground_ok=set_foreground_ok,
            )
        )
        if foreground_matches(after, hwnd=hwnd, expected_pid=expected_pid):
            return {"succeeded": True, "attempts": attempts, "finalForeground": after}

    for attempt in range(1, max(0, attach_attempts) + 1):
        before = foreground_snapshot(user32)
        current_thread = int(kernel32.GetCurrentThreadId())
        target_pid, target_thread = window_pid_thread(user32, hwnd)
        foreground_thread = int(before.get("threadId") or 0)
        attach_results: list[dict[str, Any]] = []
        detach_results: list[dict[str, Any]] = []
        attached_threads: list[int] = []

        if target_pid != expected_pid:
            after = foreground_snapshot(user32)
            attempts.append(
                focus_attempt_record(
                    tier="attachthreadinput-skipped-target-pid-mismatch",
                    attempt=attempt,
                    before=before,
                    after=after,
                    restore_ok=False,
                    bring_to_top_ok=False,
                    set_foreground_ok=False,
                )
            )
            return {"succeeded": False, "attempts": attempts, "finalForeground": after}

        try:
            for thread_id in dict.fromkeys((foreground_thread, target_thread)):
                if thread_id and thread_id != current_thread:
                    ctypes.set_last_error(0)
                    attached = bool(
                        user32.AttachThreadInput(
                            wintypes.DWORD(current_thread),
                            wintypes.DWORD(thread_id),
                            True,
                        )
                    )
                    last_error = ctypes.get_last_error() if not attached else 0
                    attach_results.append({"threadId": thread_id, "succeeded": attached, "lastError": last_error})
                    if attached:
                        attached_threads.append(thread_id)

            restore_ok = bool(user32.ShowWindow(hwnd_value, SW_RESTORE))
            bring_to_top_ok = bool(user32.BringWindowToTop(hwnd_value))
            set_foreground_ok = bool(user32.SetForegroundWindow(hwnd_value))
            time.sleep(max(0, settle_ms) / 1000.0)
        finally:
            for thread_id in reversed(attached_threads):
                ctypes.set_last_error(0)
                detached = bool(
                    user32.AttachThreadInput(
                        wintypes.DWORD(current_thread),
                        wintypes.DWORD(thread_id),
                        False,
                    )
                )
                last_error = ctypes.get_last_error() if not detached else 0
                detach_results.append({"threadId": thread_id, "succeeded": detached, "lastError": last_error})

        after = foreground_snapshot(user32)
        attempts.append(
            focus_attempt_record(
                tier="attachthreadinput-bringwindowtotop-setforegroundwindow",
                attempt=attempt,
                before=before,
                after=after,
                restore_ok=restore_ok,
                bring_to_top_ok=bring_to_top_ok,
                set_foreground_ok=set_foreground_ok,
                attach_results=attach_results,
                detach_results=detach_results,
            )
        )
        if foreground_matches(after, hwnd=hwnd, expected_pid=expected_pid):
            return {"succeeded": True, "attempts": attempts, "finalForeground": after}

    return {"succeeded": False, "attempts": attempts, "finalForeground": foreground_snapshot(user32)}


def post_key_pulse(*, hwnd: int, expected_pid: int, virtual_key: int, pulse_ms: int) -> dict[str, Any]:
    user32 = load_user32_for_input()
    pid = wintypes.DWORD()
    if not user32.IsWindow(wintypes.HWND(hwnd)):
        return {"attempted": True, "succeeded": False, "error": "target-window-not-found"}
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    if int(pid.value) != int(expected_pid):
        return {
            "attempted": True,
            "succeeded": False,
            "error": f"target-pid-mismatch:{int(pid.value)}!={expected_pid}",
        }
    scan_code = int(user32.MapVirtualKeyW(ctypes.c_uint(virtual_key), MAPVK_VK_TO_VSC))
    down_ok = bool(
        user32.PostMessageW(
            wintypes.HWND(hwnd),
            WM_KEYDOWN,
            ctypes.c_void_p(virtual_key),
            ctypes.c_void_p(build_key_lparam(scan_code, key_up=False)),
        )
    )
    time.sleep(max(0, pulse_ms) / 1000.0)
    up_ok = bool(
        user32.PostMessageW(
            wintypes.HWND(hwnd),
            WM_KEYUP,
            ctypes.c_void_p(virtual_key),
            ctypes.c_void_p(build_key_lparam(scan_code, key_up=True)),
        )
    )
    return {
        "attempted": True,
        "succeeded": bool(down_ok and up_ok),
        "virtualKey": int_hex(virtual_key),
        "scanCode": int_hex(scan_code),
        "pulseMs": pulse_ms,
        "postKeyDownSucceeded": down_ok,
        "postKeyUpSucceeded": up_ok,
        "inputSent": bool(down_ok or up_ok),
        "error": None if down_ok and up_ok else "post-message-failed",
    }


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", INPUTUNION)]


def configure_sendinput(user32: Any) -> None:
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT


def foreground_pid(user32: Any) -> tuple[int, int]:
    hwnd = int(user32.GetForegroundWindow())
    pid = wintypes.DWORD()
    if hwnd:
        user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return hwnd, int(pid.value)


def sendinput_key_pulse(*, hwnd: int, expected_pid: int, virtual_key: int, pulse_ms: int) -> dict[str, Any]:
    user32 = load_user32_for_input()
    configure_sendinput(user32)
    kernel32 = load_kernel32_for_focus()
    if not user32.IsWindow(wintypes.HWND(hwnd)):
        return {"attempted": True, "succeeded": False, "method": "sendinput", "error": "target-window-not-found"}
    owner_pid, owner_thread = window_pid_thread(user32, hwnd)
    if owner_pid != int(expected_pid):
        return {
            "attempted": True,
            "succeeded": False,
            "method": "sendinput",
            "targetThreadId": owner_thread,
            "error": f"target-pid-mismatch:{owner_pid}!={expected_pid}",
        }

    focus = request_exact_foreground(user32, kernel32, hwnd=hwnd, expected_pid=expected_pid)
    fg_hwnd, fg_pid = foreground_pid(user32)
    if not focus.get("succeeded") or fg_hwnd != hwnd or fg_pid != expected_pid:
        return {
            "attempted": True,
            "succeeded": False,
            "method": "sendinput",
            "targetThreadId": owner_thread,
            "foregroundHwnd": int_hex(fg_hwnd),
            "foregroundPid": fg_pid,
            "focus": focus,
            "inputSent": False,
            "error": "exact-target-foreground-not-acquired",
        }

    down = INPUT(type=INPUT_KEYBOARD, union=INPUTUNION(ki=KEYBDINPUT(wVk=virtual_key, wScan=0, dwFlags=0, time=0, dwExtraInfo=None)))
    up = INPUT(
        type=INPUT_KEYBOARD,
        union=INPUTUNION(ki=KEYBDINPUT(wVk=virtual_key, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)),
    )
    ctypes.set_last_error(0)
    sent_down = int(user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT)))
    down_last_error = ctypes.get_last_error() if sent_down != 1 else 0
    time.sleep(max(0, pulse_ms) / 1000.0)
    ctypes.set_last_error(0)
    sent_up = int(user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT)))
    up_last_error = ctypes.get_last_error() if sent_up != 1 else 0
    return {
        "attempted": True,
        "succeeded": bool(sent_down == 1 and sent_up == 1),
        "method": "sendinput",
        "targetThreadId": owner_thread,
        "foregroundHwnd": int_hex(fg_hwnd),
        "foregroundPid": fg_pid,
        "focus": focus,
        "virtualKey": int_hex(virtual_key),
        "pulseMs": pulse_ms,
        "sendInputDownCount": sent_down,
        "sendInputUpCount": sent_up,
        "sendInputDownLastError": down_last_error,
        "sendInputUpLastError": up_last_error,
        "inputStructSize": ctypes.sizeof(INPUT),
        "inputSent": bool(sent_down or sent_up),
        "error": None if sent_down == 1 and sent_up == 1 else "sendinput-failed",
    }


def capture_context(client: Any, *, candidate_address: int, label: str, read_size: int) -> dict[str, Any]:
    errors: list[str] = []
    debugger_pid = None
    debugee_pid = None
    is_running = None
    is_debugging = None
    rip = None
    regs = None
    key_regs: dict[str, str | None] = {}
    disassembly = None
    candidate_bytes = b""
    rip_code_bytes = b""
    stack_bytes = b""
    stack_qwords: list[dict[str, Any]] = []
    register_memory: dict[str, Any] = {}

    for field, fn in (
        ("debuggerPid", client.get_debugger_pid),
        ("debuggeePid", client.debugee_pid),
        ("isRunning", client.is_running),
        ("isDebugging", client.is_debugging),
    ):
        try:
            value = fn()
            if field == "debuggerPid":
                debugger_pid = value
            elif field == "debuggeePid":
                debugee_pid = value
            elif field == "isRunning":
                is_running = value
            elif field == "isDebugging":
                is_debugging = value
        except Exception as exc:  # noqa: BLE001 - preserve debugger API failures as evidence.
            errors.append(f"{field}:{type(exc).__name__}:{exc}")

    try:
        rip = int(client.get_reg("rip"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"get_reg:rip:{type(exc).__name__}:{exc}")

    for reg_name in (
        "cip",
        "rip",
        "rsp",
        "rbp",
        "rax",
        "rbx",
        "rcx",
        "rdx",
        "rsi",
        "rdi",
        "r8",
        "r9",
        "r10",
        "r11",
        "r12",
        "r13",
        "r14",
        "r15",
    ):
        try:
            key_regs[reg_name] = int_hex(int(client.get_reg(reg_name)))
        except Exception as exc:  # noqa: BLE001
            key_regs[reg_name] = None
            errors.append(f"get_reg:{reg_name}:{type(exc).__name__}:{exc}")

    if rip is None and key_regs.get("rip"):
        rip = int(str(key_regs["rip"]), 0)

    rsp_value = None
    if key_regs.get("rsp"):
        try:
            rsp_value = int(str(key_regs["rsp"]), 0)
        except ValueError:
            rsp_value = None

    try:
        regs = to_jsonable(client.get_regs())
    except Exception as exc:  # noqa: BLE001
        errors.append(f"get_regs:{type(exc).__name__}:{exc}")

    if rip is not None:
        try:
            disassembly = to_jsonable(client.disassemble_at(rip))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"disassemble_at:rip:{type(exc).__name__}:{exc}")
        try:
            rip_code_start = max(0, rip - 16)
            rip_code_bytes = bytes(client.read_memory(rip_code_start, 96))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"read_memory:rip_code:{type(exc).__name__}:{exc}")

    if rsp_value is not None:
        try:
            stack_bytes = bytes(client.read_memory(rsp_value, 256))
            for offset in range(0, len(stack_bytes) - 7, 8):
                stack_qwords.append(
                    {
                        "offset": offset,
                        "offsetHex": int_hex(offset),
                        "address": int_hex(rsp_value + offset),
                        "value": int_hex(struct.unpack_from("<Q", stack_bytes, offset)[0]),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"read_memory:stack:{type(exc).__name__}:{exc}")

    for reg_name in ("rax", "rbx", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r12", "r13", "r14", "r15"):
        raw_value = key_regs.get(reg_name)
        if raw_value is None:
            continue
        try:
            address = int(str(raw_value), 0)
        except ValueError:
            continue
        if address < 0x10000:
            continue
        try:
            preview = memory_preview(client, address, size=128)
            register_memory[reg_name] = preview
            if len(preview.get("bytesHex") or "") >= 16:
                deref = struct.unpack_from("<Q", bytes.fromhex(str(preview["bytesHex"])), 0)[0]
                if deref >= 0x10000:
                    try:
                        register_memory[f"{reg_name}Deref0"] = memory_preview(client, deref, size=128)
                    except Exception as deref_exc:  # noqa: BLE001
                        register_memory[f"{reg_name}Deref0"] = {
                            "address": int_hex(deref),
                            "error": f"{type(deref_exc).__name__}:{deref_exc}",
                        }
        except Exception as exc:  # noqa: BLE001
            register_memory[reg_name] = {
                "address": int_hex(address),
                "error": f"{type(exc).__name__}:{exc}",
            }

    try:
        candidate_bytes = bytes(client.read_memory(candidate_address, read_size))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"read_memory:candidate:{type(exc).__name__}:{exc}")

    return {
        "label": label,
        "capturedAtUtc": utc_iso(),
        "debuggerPid": debugger_pid,
        "debuggeePid": debugee_pid,
        "isRunning": is_running,
        "isDebugging": is_debugging,
        "rip": int_hex(rip),
        "keyRegisters": key_regs,
        "registers": regs,
        "ripDisassembly": disassembly,
        "ripCode": {
            "start": int_hex(max(0, rip - 16) if rip is not None else None),
            "byteCount": len(rip_code_bytes),
            "bytesHex": rip_code_bytes.hex(),
        },
        "stack": {
            "rsp": int_hex(rsp_value),
            "byteCount": len(stack_bytes),
            "qwords": stack_qwords,
        },
        "registerMemory": register_memory,
        "candidateMemory": {
            "address": int_hex(candidate_address),
            "readSize": read_size,
            "triplet": memory_triplet(candidate_bytes),
        },
        "errors": errors,
    }


def clear_all_hardware_breakpoints(client: Any, summary: dict[str, Any], *, reason: str) -> bool:
    try:
        cleared = bool(client.clear_hardware_breakpoint(None))
        if cleared:
            summary["safety"]["hardwareBreakpointSet"] = False
        else:
            summary["warnings"].append(f"clear-all-hardware-breakpoints-returned-false:{reason}")
        return cleared
    except Exception as exc:  # noqa: BLE001 - debugger cleanup failures are evidence.
        summary["warnings"].append(f"clear-all-hardware-breakpoints-failed:{reason}:{type(exc).__name__}:{exc}")
        return False


def clear_all_memory_breakpoints(client: Any, summary: dict[str, Any], *, reason: str) -> bool:
    try:
        cleared = bool(client.clear_memory_breakpoint(None))
        if cleared:
            summary["safety"]["memoryBreakpointSet"] = False
        else:
            summary["warnings"].append(f"clear-all-memory-breakpoints-returned-false:{reason}")
        return cleared
    except Exception as exc:  # noqa: BLE001 - debugger cleanup failures are evidence.
        summary["warnings"].append(f"clear-all-memory-breakpoints-failed:{reason}:{type(exc).__name__}:{exc}")
        return False


def resume_if_stopped(client: Any, summary: dict[str, Any], *, reason: str) -> bool | None:
    try:
        running = bool(client.is_running())
    except Exception as exc:  # noqa: BLE001
        summary["warnings"].append(f"is-running-before-resume-failed:{reason}:{type(exc).__name__}:{exc}")
        return None
    if running:
        summary["warnings"].append(f"resume-not-needed-target-running:{reason}")
        return True
    if int(summary["safety"]["goAttempts"]) >= int(summary["safety"]["liveAttachPolicy"]["maxGoAttempts"]):
        summary["warnings"].append(f"resume-skipped-go-budget-exhausted:{reason}")
        return False
    summary["safety"]["goAttempts"] = int(summary["safety"]["goAttempts"]) + 1
    try:
        go_result = bool(client.go(pass_exceptions=False, swallow_exceptions=False))
    except Exception as exc:  # noqa: BLE001
        summary["warnings"].append(f"resume-go-failed:{reason}:{type(exc).__name__}:{exc}")
        return False
    if not go_result:
        summary["warnings"].append(f"resume-go-returned-false:{reason}")
        return False
    try:
        running_after = bool(client.wait_until_running(timeout=2))
    except Exception as exc:  # noqa: BLE001
        summary["warnings"].append(f"wait-until-running-after-resume-failed:{reason}:{type(exc).__name__}:{exc}")
        return None
    if not running_after:
        summary["warnings"].append(f"resume-go-did-not-reach-running:{reason}")
    return running_after


def build_markdown(summary: dict[str, Any]) -> str:
    event = summary.get("event") if isinstance(summary.get("event"), dict) else {}
    candidate = summary.get("candidate") if isinstance(summary.get("candidate"), dict) else {}
    lines = [
        "# x64dbg live access capture",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Capture mode: `{summary.get('captureMode')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Target PID: `{summary.get('target', {}).get('pid')}`",
        f"- Target HWND: `{summary.get('target', {}).get('hwnd')}`",
        f"- Candidate: `{candidate.get('address')}`",
        f"- x64dbg session PID: `{summary.get('x64dbg', {}).get('sessionPid')}`",
        f"- Event status: `{event.get('status')}`",
        f"- Detach attempted: `{str(summary.get('detach', {}).get('attempted')).lower()}`",
        f"- Detach succeeded: `{str(summary.get('detach', {}).get('succeeded')).lower()}`",
        f"- x64dbg terminate attempted: `{str(summary.get('detach', {}).get('terminateSessionAttempted')).lower()}`",
        f"- Elapsed seconds: `{summary.get('timing', {}).get('elapsedSeconds')}`",
        "",
        "This artifact is candidate-only. It is not movement proof and does not promote a static pointer chain.",
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    if summary.get("errors"):
        lines.extend(["", "## Errors"])
        lines.extend(f"- `{error}`" for error in summary["errors"])
    return "\n".join(lines).rstrip() + "\n"


def run_capture(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = args.output_root.resolve() if args.output_root else repo_root / "scripts" / "captures" / f"x64dbg-live-access-capture-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"

    candidate_address = int(args.candidate_address, 0)
    breakpoint_address = int(args.breakpoint_address, 0) if args.breakpoint_address else candidate_address
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    if not args.allow_live_debugger:
        blockers.append("rift-live-debugger-not-authorized-current-turn")
    blockers.extend(
        validate_live_attach_policy(
            max_live_attach_seconds=args.max_live_attach_seconds,
            unresponsive_abort_seconds=args.unresponsive_abort_seconds,
            max_go_attempts=args.max_go_attempts,
        )
    )
    if args.max_go_attempts < 1 and args.capture_mode in {"hardware-read", "memory-access", "resume-only"}:
        blockers.append(f"{args.capture_mode}-capture-requires-one-go-attempt")
    if args.stimulus_key and not args.allow_game_input:
        blockers.append("stimulus-key-requires-allow-game-input")
    if args.stimulus_pulse_ms < 0 or args.stimulus_pulse_ms > MAX_STIMULUS_PULSE_MS:
        blockers.append(f"stimulus-pulse-ms-out-of-range:0..{MAX_STIMULUS_PULSE_MS}")
    if not Path(args.x64dbg_path).is_file():
        blockers.append(f"x64dbg-path-missing:{args.x64dbg_path}")

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "x64dbg-live-access-capture",
        "captureMode": args.capture_mode,
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "started",
        "repoRoot": str(repo_root),
        "target": {
            "processName": args.process_name,
            "pid": args.target_pid,
            "hwnd": args.target_hwnd,
            "processStartTimeUtc": args.process_start_time_utc,
            "expectedModuleBase": args.expected_module_base,
        },
        "candidate": {
            "address": int_hex(candidate_address),
            "breakpointAddress": int_hex(breakpoint_address),
            "breakpointAccess": args.breakpoint_access,
            "breakpointSize": args.breakpoint_size,
            "readSize": args.read_size,
            "evidenceFile": str(args.candidate_evidence_file) if args.candidate_evidence_file else None,
            "accessTemplate": str(args.access_template) if args.access_template else None,
            "candidateEvidence": read_json_file(args.candidate_evidence_file),
        },
        "x64dbg": {
            "path": str(args.x64dbg_path),
            "sessionPid": None,
        },
        "contexts": [],
        "event": {
            "status": None,
            "raw": None,
        },
        "detach": {
            "attempted": False,
            "succeeded": False,
            "terminateSessionAttempted": False,
            "terminateSessionSucceeded": False,
        },
        "timing": {
            "maxLiveAttachSeconds": args.max_live_attach_seconds,
            "breakpointTimeoutSeconds": args.breakpoint_timeout_seconds,
            "elapsedSeconds": None,
        },
        "safety": {
            "movementSent": False,
            "gameInputSent": False,
            "targetMemoryWritten": False,
            "hardwareBreakpointSet": False,
            "memoryBreakpointSet": False,
            "goAttempts": 0,
            "exceptionSwallowRetryLoopAllowed": False,
            "candidateOnly": True,
            "promotionEligible": False,
            "liveAttachPolicy": live_attach_policy(
                max_live_attach_seconds=args.max_live_attach_seconds,
                unresponsive_abort_seconds=args.unresponsive_abort_seconds,
                max_go_attempts=args.max_go_attempts,
            ),
        },
        "stimulus": {
            "requested": bool(args.stimulus_key),
            "allowGameInput": bool(args.allow_game_input),
            "key": args.stimulus_key,
            "pulseMs": args.stimulus_pulse_ms,
            "delayMs": args.stimulus_delay_ms,
            "result": None,
        },
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
    }
    if blockers:
        write_json(summary_json, summary)
        write_text_atomic(summary_md, build_markdown(summary))
        return summary

    client = None
    started = time.monotonic()
    try:
        from x64dbg_automate import X64DbgClient  # type: ignore
        from x64dbg_automate.events import EventType  # type: ignore
        from x64dbg_automate.models import HardwareBreakpointType, MemoryBreakpointType  # type: ignore

        client = X64DbgClient(x64dbg_path=str(args.x64dbg_path))
        stimulus_thread = None
        stimulus_holder: dict[str, Any] = {"result": None}
        session_pid = client.start_session_attach(int(args.target_pid))
        summary["x64dbg"]["sessionPid"] = session_pid
        summary["contexts"].append(capture_context(client, candidate_address=candidate_address, label="attached-stop", read_size=args.read_size))

        attached_pid = summary["contexts"][-1].get("debuggeePid")
        if attached_pid is not None and int(attached_pid) == 0:
            summary["warnings"].append("debuggee-pid-unavailable-from-x64dbg-api:0; preserving start_session_attach target PID as identity guard")
        if attached_pid is not None and int(attached_pid) not in (0, int(args.target_pid)):
            summary["blockers"].append(f"debuggee-pid-mismatch:{attached_pid}!={args.target_pid}")
            summary["status"] = "blocked"
        elif args.capture_mode == "resume-only":
            clear_all_hardware_breakpoints(client, summary, reason="resume-only")
            resume_if_stopped(client, summary, reason="resume-only")
            summary["event"]["status"] = "not-requested"
            summary["status"] = "captured"
        elif args.capture_mode == "hardware-read":
            client.clear_debug_events()
            breakpoint_type = {
                "read": HardwareBreakpointType.r,
                "write": HardwareBreakpointType.w,
                "execute": HardwareBreakpointType.x,
            }[args.breakpoint_access]
            if not client.set_hardware_breakpoint(breakpoint_address, bp_type=breakpoint_type, size=args.breakpoint_size):
                summary["blockers"].append("set-hardware-breakpoint-failed")
                summary["status"] = "blocked"
            else:
                summary["safety"]["hardwareBreakpointSet"] = True
                running_after_breakpoint = None
                try:
                    running_after_breakpoint = bool(client.is_running())
                except Exception as exc:  # noqa: BLE001
                    summary["warnings"].append(f"is-running-after-breakpoint-failed:{type(exc).__name__}:{exc}")
                if running_after_breakpoint:
                    summary["warnings"].append("target-already-running-after-hardware-breakpoint; waiting without issuing go")
                else:
                    summary["safety"]["goAttempts"] = 1
                    if not client.go(pass_exceptions=False, swallow_exceptions=False):
                        summary["warnings"].append("go-returned-false; waiting for breakpoint anyway")
                if args.stimulus_key:
                    virtual_key = parse_virtual_key(args.stimulus_key)
                    hwnd = int(str(args.target_hwnd), 0)

                    def send_stimulus() -> None:
                        time.sleep(max(0, args.stimulus_delay_ms) / 1000.0)
                        if args.stimulus_method == "sendinput":
                            stimulus_holder["result"] = sendinput_key_pulse(
                                hwnd=hwnd,
                                expected_pid=int(args.target_pid),
                                virtual_key=virtual_key,
                                pulse_ms=int(args.stimulus_pulse_ms),
                            )
                        else:
                            stimulus_holder["result"] = post_key_pulse(
                                hwnd=hwnd,
                                expected_pid=int(args.target_pid),
                                virtual_key=virtual_key,
                                pulse_ms=int(args.stimulus_pulse_ms),
                            )

                    stimulus_thread = threading.Thread(target=send_stimulus, name="x64dbg-stimulus", daemon=True)
                    stimulus_thread.start()
                event = client.wait_for_debug_event(EventType.EVENT_BREAKPOINT, timeout=int(args.breakpoint_timeout_seconds))
                if stimulus_thread is not None:
                    stimulus_thread.join(timeout=max(2.0, (args.stimulus_pulse_ms + args.stimulus_delay_ms) / 1000.0 + 1.0))
                    summary["stimulus"]["result"] = stimulus_holder.get("result")
                    summary["safety"]["gameInputSent"] = bool(
                        isinstance(stimulus_holder.get("result"), dict)
                        and stimulus_holder["result"].get("inputSent")
                    )
                    summary["safety"]["movementSent"] = bool(summary["safety"]["gameInputSent"])
                if event is None:
                    summary["event"]["status"] = "timeout"
                    summary["warnings"].append("hardware-read-breakpoint-timeout-before-hit")
                    summary["status"] = "timed-out"
                else:
                    summary["event"]["status"] = "hit"
                    summary["event"]["raw"] = to_jsonable(event)
                    summary["contexts"].append(capture_context(client, candidate_address=candidate_address, label="hardware-read-hit", read_size=args.read_size))
                    summary["status"] = "captured"
                    clear_all_hardware_breakpoints(client, summary, reason="after-hardware-read-hit")
                    resume_if_stopped(client, summary, reason="after-hardware-read-hit")
                if summary["safety"]["hardwareBreakpointSet"]:
                    clear_all_hardware_breakpoints(client, summary, reason="after-hardware-read")
        elif args.capture_mode == "memory-access":
            client.clear_debug_events()
            breakpoint_type = {
                "read": MemoryBreakpointType.r,
                "write": MemoryBreakpointType.w,
                "execute": MemoryBreakpointType.x,
            }[args.breakpoint_access]
            if not client.set_memory_breakpoint(breakpoint_address, bp_type=breakpoint_type, singleshoot=True):
                summary["blockers"].append("set-memory-breakpoint-failed")
                summary["status"] = "blocked"
            else:
                summary["safety"]["memoryBreakpointSet"] = True
                running_after_breakpoint = None
                try:
                    running_after_breakpoint = bool(client.is_running())
                except Exception as exc:  # noqa: BLE001
                    summary["warnings"].append(f"is-running-after-memory-breakpoint-failed:{type(exc).__name__}:{exc}")
                if running_after_breakpoint:
                    summary["warnings"].append("target-already-running-after-memory-breakpoint; waiting without issuing go")
                else:
                    summary["safety"]["goAttempts"] = 1
                    if not client.go(pass_exceptions=False, swallow_exceptions=False):
                        summary["warnings"].append("go-returned-false-after-memory-breakpoint; waiting for breakpoint anyway")
                if args.stimulus_key:
                    virtual_key = parse_virtual_key(args.stimulus_key)
                    hwnd = int(str(args.target_hwnd), 0)

                    def send_stimulus() -> None:
                        time.sleep(max(0, args.stimulus_delay_ms) / 1000.0)
                        if args.stimulus_method == "sendinput":
                            stimulus_holder["result"] = sendinput_key_pulse(
                                hwnd=hwnd,
                                expected_pid=int(args.target_pid),
                                virtual_key=virtual_key,
                                pulse_ms=int(args.stimulus_pulse_ms),
                            )
                        else:
                            stimulus_holder["result"] = post_key_pulse(
                                hwnd=hwnd,
                                expected_pid=int(args.target_pid),
                                virtual_key=virtual_key,
                                pulse_ms=int(args.stimulus_pulse_ms),
                            )

                    stimulus_thread = threading.Thread(name="x64dbg-memory-stimulus", target=send_stimulus, daemon=True)
                    stimulus_thread.start()
                event = client.wait_for_debug_event(EventType.EVENT_BREAKPOINT, timeout=int(args.breakpoint_timeout_seconds))
                if stimulus_thread is not None:
                    stimulus_thread.join(timeout=max(2.0, (args.stimulus_pulse_ms + args.stimulus_delay_ms) / 1000.0 + 1.0))
                    summary["stimulus"]["result"] = stimulus_holder.get("result")
                    summary["safety"]["gameInputSent"] = bool(
                        isinstance(stimulus_holder.get("result"), dict)
                        and stimulus_holder["result"].get("inputSent")
                    )
                    summary["safety"]["movementSent"] = bool(summary["safety"]["gameInputSent"])
                if event is None:
                    summary["event"]["status"] = "timeout"
                    summary["warnings"].append("memory-breakpoint-timeout-before-hit")
                    summary["status"] = "timed-out"
                else:
                    summary["event"]["status"] = "hit"
                    summary["event"]["raw"] = to_jsonable(event)
                    summary["contexts"].append(capture_context(client, candidate_address=candidate_address, label="memory-breakpoint-hit", read_size=args.read_size))
                    summary["status"] = "captured"
                    clear_all_memory_breakpoints(client, summary, reason="after-memory-breakpoint-hit")
                    resume_if_stopped(client, summary, reason="after-memory-breakpoint-hit")
                if summary["safety"]["memoryBreakpointSet"]:
                    clear_all_memory_breakpoints(client, summary, reason="after-memory-breakpoint")
        else:
            summary["event"]["status"] = "not-requested"
            summary["status"] = "captured"
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    finally:
        summary["timing"]["elapsedSeconds"] = round(time.monotonic() - started, 3)
        if client is not None:
            if summary["safety"].get("hardwareBreakpointSet"):
                clear_all_hardware_breakpoints(client, summary, reason="finally-before-detach")
                resume_if_stopped(client, summary, reason="finally-before-detach")
            if summary["safety"].get("memoryBreakpointSet"):
                clear_all_memory_breakpoints(client, summary, reason="finally-before-detach")
                resume_if_stopped(client, summary, reason="finally-before-detach")
            try:
                summary["detach"]["attempted"] = True
                summary["detach"]["succeeded"] = bool(client.detach(wait_timeout=args.detach_timeout_seconds))
            except Exception as exc:  # noqa: BLE001
                summary["warnings"].append(f"detach-failed:{type(exc).__name__}:{exc}")
            if summary["detach"]["succeeded"]:
                try:
                    summary["detach"]["terminateSessionAttempted"] = True
                    client.terminate_session()
                    summary["detach"]["terminateSessionSucceeded"] = True
                except Exception as exc:  # noqa: BLE001
                    summary["warnings"].append(f"terminate-session-failed:{type(exc).__name__}:{exc}")
            if not summary["detach"]["succeeded"]:
                summary["blockers"].append("x64dbg-detach-failed")
                if summary["status"] not in {"failed", "blocked"}:
                    summary["status"] = "blocked"
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded live x64dbg capture for a top-ranked coordinate candidate.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--x64dbg-path", type=Path, default=DEFAULT_X64DBG_PATH)
    parser.add_argument("--allow-live-debugger", action="store_true")
    parser.add_argument("--capture-mode", choices=("stop-context", "hardware-read", "memory-access", "resume-only"), default="stop-context")
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--target-hwnd", required=True)
    parser.add_argument("--process-start-time-utc", required=True)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--candidate-address", required=True)
    parser.add_argument("--breakpoint-address", default=None)
    parser.add_argument("--breakpoint-access", choices=("read", "write", "execute"), default="read")
    parser.add_argument("--breakpoint-size", type=int, choices=(1, 2, 4, 8), default=4)
    parser.add_argument("--candidate-evidence-file", type=Path, default=None)
    parser.add_argument("--access-template", type=Path, default=None)
    parser.add_argument("--read-size", type=int, default=12)
    parser.add_argument("--allow-game-input", action="store_true")
    parser.add_argument("--stimulus-method", choices=("postmessage", "sendinput"), default="postmessage")
    parser.add_argument("--stimulus-key", default=None)
    parser.add_argument("--stimulus-pulse-ms", type=int, default=80)
    parser.add_argument("--stimulus-delay-ms", type=int, default=500)
    parser.add_argument("--breakpoint-timeout-seconds", type=int, default=DEFAULT_BREAKPOINT_TIMEOUT_SECONDS)
    parser.add_argument("--detach-timeout-seconds", type=int, default=DEFAULT_DETACH_TIMEOUT_SECONDS)
    parser.add_argument("--max-live-attach-seconds", type=int, default=DEFAULT_MAX_LIVE_ATTACH_SECONDS)
    parser.add_argument("--unresponsive-abort-seconds", type=int, default=DEFAULT_UNRESPONSIVE_ABORT_SECONDS)
    parser.add_argument("--max-go-attempts", type=int, default=DEFAULT_MAX_GO_ATTEMPTS)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_capture(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "captureMode": summary["captureMode"],
                    "eventStatus": (summary.get("event") or {}).get("status"),
                    "detachSucceeded": (summary.get("detach") or {}).get("succeeded"),
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                    "errors": summary["errors"],
                },
                separators=(",", ":"),
            )
        )
    return 0 if summary["status"] in {"captured", "timed-out"} and summary["detach"]["succeeded"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
