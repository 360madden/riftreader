from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER32 = ctypes.WinDLL("user32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
SW_RESTORE = 9
MAPVK_VK_TO_VSC = 0
VK_MULTIPLY = 0x6A

USER32.IsWindow.argtypes = [wintypes.HWND]
USER32.IsWindow.restype = wintypes.BOOL
USER32.IsWindowVisible.argtypes = [wintypes.HWND]
USER32.IsWindowVisible.restype = wintypes.BOOL
USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.ShowWindow.restype = wintypes.BOOL
USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
USER32.SetForegroundWindow.restype = wintypes.BOOL
USER32.BringWindowToTop.argtypes = [wintypes.HWND]
USER32.BringWindowToTop.restype = wintypes.BOOL
USER32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
USER32.AttachThreadInput.restype = wintypes.BOOL
KERNEL32.GetCurrentThreadId.argtypes = []
KERNEL32.GetCurrentThreadId.restype = wintypes.DWORD
USER32.GetForegroundWindow.argtypes = []
USER32.GetForegroundWindow.restype = wintypes.HWND
USER32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
USER32.GetWindowThreadProcessId.restype = wintypes.DWORD
USER32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
USER32.MapVirtualKeyW.restype = wintypes.UINT
USER32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
USER32.PostMessageW.restype = wintypes.BOOL
USER32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
USER32.GetWindowTextLengthW.restype = ctypes.c_int
USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
USER32.GetWindowTextW.restype = ctypes.c_int

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tga"}


ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]


USER32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
USER32.SendInput.restype = wintypes.UINT

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_hwnd(value: str) -> int:
    text = str(value).strip()
    if not text:
        raise ValueError("window handle is required")
    return int(text, 16 if text.lower().startswith("0x") else 10)


def win32_error() -> str:
    code = ctypes.get_last_error()
    if not code:
        return "Win32 error 0"
    message = ctypes.FormatError(code).strip()
    return f"Win32 error {code}: {message}"


def get_window_title(hwnd: int) -> str:
    length = USER32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    USER32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def get_window_process_id(hwnd: int) -> int | None:
    pid = wintypes.DWORD(0)
    USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value) if pid.value else None


def force_foreground(hwnd: int) -> int:
    USER32.ShowWindow(hwnd, SW_RESTORE)
    USER32.BringWindowToTop(hwnd)
    foreground = int(USER32.GetForegroundWindow())
    current_thread = int(KERNEL32.GetCurrentThreadId())
    target_pid = wintypes.DWORD(0)
    target_thread = int(USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid)))
    foreground_pid = wintypes.DWORD(0)
    foreground_thread = int(USER32.GetWindowThreadProcessId(foreground, ctypes.byref(foreground_pid))) if foreground else 0
    attached: list[tuple[int, int]] = []
    try:
        for other in (foreground_thread, target_thread):
            if other and other != current_thread:
                if USER32.AttachThreadInput(current_thread, other, True):
                    attached.append((current_thread, other))
        USER32.BringWindowToTop(hwnd)
        USER32.SetForegroundWindow(hwnd)
        time.sleep(0.15)
    finally:
        for first, second in reversed(attached):
            USER32.AttachThreadInput(first, second, False)
    return int(USER32.GetForegroundWindow())


def make_key_lparam(vk: int, *, key_up: bool = False) -> int:
    scan = int(USER32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC))
    value = 1 | (scan << 16)
    if key_up:
        value |= (1 << 30) | (1 << 31)
    return value


def post_key(hwnd: int, vk: int, *, key_up: bool = False) -> None:
    message = WM_KEYUP if key_up else WM_KEYDOWN
    if not USER32.PostMessageW(hwnd, message, vk, make_key_lparam(vk, key_up=key_up)):
        raise RuntimeError(f"PostMessage failed for vk={vk}: {win32_error()}")


KEY_CHORDS: dict[str, tuple[int, ...]] = {
    "numpad_multiply": (VK_MULTIPLY,),
}

NUMPAD_MULTIPLY_ALIASES = {"numpad_multiply", "numpad*", "numpad *", "numpad multiply", "multiply"}
FORBIDDEN_SCREENSHOT_CHORDS = {"ctrl+p", "control+p"}


def normalize_key_chord(value: str) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    if text in FORBIDDEN_SCREENSHOT_CHORDS:
        raise ValueError(
            "forbidden screenshot key chord: Ctrl+P is intentionally disabled; "
            "current RIFT Take Screenshot binding is NUM PAD * only"
        )
    text = text.replace("num pad", "numpad")
    if text in NUMPAD_MULTIPLY_ALIASES:
        return "numpad_multiply"
    raise ValueError(f"unsupported key chord {value!r}; supported screenshot chord is NUM PAD *")


def key_slug(key_chord: str) -> str:
    return (
        normalize_key_chord(key_chord)
        .replace("+", "-")
        .replace("*", "star")
        .replace(" ", "-")
        .replace("_", "-")
    )


def key_sequence(key_chord: str) -> tuple[int, ...]:
    return KEY_CHORDS[normalize_key_chord(key_chord)]


def send_key_chord_window_message(hwnd: int, key_chord: str, hold_seconds: float) -> None:
    sequence = key_sequence(key_chord)
    for vk in sequence:
        post_key(hwnd, vk, key_up=False)
        time.sleep(0.02)
    time.sleep(max(0.01, hold_seconds))
    for vk in reversed(sequence):
        post_key(hwnd, vk, key_up=True)
        time.sleep(0.02)


def keyboard_input(vk: int, *, key_up: bool = False) -> INPUT:
    item = INPUT()
    item.type = INPUT_KEYBOARD
    item.union.ki = KEYBDINPUT(
        wVk=vk,
        wScan=0,
        dwFlags=KEYEVENTF_KEYUP if key_up else 0,
        time=0,
        dwExtraInfo=0,
    )
    return item


def keyboard_scan_input(vk: int, *, key_up: bool = False) -> INPUT:
    scan = int(USER32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC))
    if scan <= 0:
        raise RuntimeError(f"no scan code found for vk=0x{vk:X}")
    item = INPUT()
    item.type = INPUT_KEYBOARD
    item.union.ki = KEYBDINPUT(
        wVk=0,
        wScan=scan,
        dwFlags=KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0),
        time=0,
        dwExtraInfo=0,
    )
    return item


def send_input_sequence(items: list[INPUT]) -> None:
    array_type = INPUT * len(items)
    array = array_type(*items)
    sent = USER32.SendInput(len(items), array, ctypes.sizeof(INPUT))
    if sent != len(items):
        raise RuntimeError(f"SendInput sent {sent}/{len(items)} inputs: {win32_error()}")


def send_key_chord_sendinput(key_chord: str, hold_seconds: float) -> None:
    sequence = key_sequence(key_chord)
    send_input_sequence([keyboard_input(vk) for vk in sequence])
    time.sleep(max(0.01, hold_seconds))
    send_input_sequence([keyboard_input(vk, key_up=True) for vk in reversed(sequence)])


def send_key_chord_scancode_sendinput(key_chord: str, hold_seconds: float) -> None:
    sequence = key_sequence(key_chord)
    send_input_sequence([keyboard_scan_input(vk) for vk in sequence])
    time.sleep(max(0.01, hold_seconds))
    send_input_sequence([keyboard_scan_input(vk, key_up=True) for vk in reversed(sequence)])


def default_screenshots_dir() -> Path:
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    candidates = [
        home / "OneDrive" / "Documents" / "RIFT" / "Screenshots",
        home / "Documents" / "RIFT" / "Screenshots",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def snapshot_files(directory: Path) -> dict[str, dict[str, Any]]:
    if not directory.exists():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for child in directory.iterdir():
        if not child.is_file() or child.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            stat = child.stat()
        except OSError:
            continue
        result[str(child.resolve())] = {
            "path": str(child.resolve()),
            "mtime": stat.st_mtime,
            "size": stat.st_size,
        }
    return result


def newest_file(files: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not files:
        return None
    return max(files.values(), key=lambda item: (item["mtime"], item["path"]))


def find_new_file(directory: Path, before: dict[str, dict[str, Any]], started: float) -> dict[str, Any] | None:
    current = snapshot_files(directory)
    candidates = []
    for path_text, item in current.items():
        previous = before.get(path_text)
        if previous is None:
            candidates.append(item)
            continue
        if item["mtime"] >= started - 1.0 and item["size"] > previous.get("size", 0):
            candidates.append(item)
    candidates = [item for item in candidates if item["size"] > 0 and item["mtime"] >= started - 2.0]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item["mtime"], item["path"]))


def copy_artifact(source: Path, output_root: Path | None, key_chord: str) -> str | None:
    if output_root is None:
        return None
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destination = output_root / f"rift-native-{key_slug(key_chord)}-screenshot-{stamp}{source.suffix.lower()}"
    shutil.copy2(source, destination)
    return str(destination.resolve())


def run(args: argparse.Namespace) -> dict[str, Any]:
    hwnd = parse_hwnd(args.hwnd)
    screenshots_dir = Path(args.screenshots_dir).expanduser() if args.screenshots_dir else default_screenshots_dir()
    output_root = Path(args.output_root).expanduser() if args.output_root else None
    started_text = utc_now_text()
    before = snapshot_files(screenshots_dir)
    before_newest = newest_file(before)

    try:
        key_chord = normalize_key_chord(args.key_chord)
    except ValueError as exc:
        return {
            "schemaVersion": 1,
            "mode": "rift-native-screenshot-trial",
            "status": "blocked-invalid-key-chord",
            "ok": False,
            "issue": str(exc),
            "startedAtUtc": started_text,
            "processId": args.pid,
            "targetWindowHandle": args.hwnd,
        }

    result: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "rift-native-screenshot-trial",
        "status": "running",
        "startedAtUtc": started_text,
        "processId": args.pid,
        "targetWindowHandle": args.hwnd,
        "keyChord": key_chord,
        "keyVirtualKeys": [f"0x{vk:X}" for vk in key_sequence(key_chord)],
        "inputMethod": "window-message",
        "screenshotsDirectory": str(screenshots_dir),
        "beforeNewestScreenshot": before_newest,
        "noPrintScreen": True,
        "whyNoPrintScreen": "PRINT SCREEN is intentionally avoided because Windows Snipping Tool can intercept it; Ctrl+P is forbidden because it is no longer bound; current RIFT Take Screenshot binding is NUM PAD *.",
    }

    if not USER32.IsWindow(hwnd):
        result.update({"status": "blocked-target-missing", "ok": False, "issue": "hwnd_not_a_window"})
        return result

    owner_pid = get_window_process_id(hwnd)
    title = get_window_title(hwnd)
    result["window"] = {
        "processId": owner_pid,
        "title": title,
        "isVisible": bool(USER32.IsWindowVisible(hwnd)),
        "foregroundBefore": f"0x{int(USER32.GetForegroundWindow()):X}",
    }
    if args.pid and owner_pid != args.pid:
        result.update({"status": "blocked-target-mismatch", "ok": False, "issue": f"owner_pid={owner_pid};expected={args.pid}"})
        return result

    result["window"]["foregroundAfterFocus"] = f"0x{force_foreground(hwnd):X}"

    sent_at = time.time()
    attempts = 0
    new_file = None
    input_attempts: list[dict[str, Any]] = []

    def poll_for_file(start_time: float, timeout_ms: int) -> tuple[dict[str, Any] | None, int]:
        deadline = start_time + (timeout_ms / 1000.0)
        local_attempts = 0
        while time.time() < deadline:
            local_attempts += 1
            found = find_new_file(screenshots_dir, before, start_time)
            if found:
                return found, local_attempts
            time.sleep(args.poll_interval_milliseconds / 1000.0)
        return None, local_attempts

    try:
        send_key_chord_window_message(hwnd, key_chord, args.hold_milliseconds / 1000.0)
        input_attempts.append({"method": "window-message", "sent": True})
    except Exception as exc:  # noqa: BLE001
        input_attempts.append({"method": "window-message", "sent": False, "error": str(exc)})

    new_file, used_attempts = poll_for_file(sent_at, args.window_message_timeout_milliseconds)
    attempts += used_attempts

    def run_sendinput_fallback(
        *,
        method: str,
        sender: Any,
        timeout_milliseconds: int,
    ) -> dict[str, Any] | None:
        nonlocal attempts
        fallback_start = time.time()
        foreground = int(USER32.GetForegroundWindow())
        if foreground != hwnd:
            foreground = force_foreground(hwnd)
        if foreground != hwnd:
            input_attempts.append({
                "method": method,
                "sent": False,
                "error": f"target_not_foreground:foreground=0x{foreground:X};target=0x{hwnd:X}",
            })
            return None
        try:
            sender(key_chord, args.hold_milliseconds / 1000.0)
            input_attempts.append({"method": method, "sent": True})
        except Exception as exc:  # noqa: BLE001
            input_attempts.append({"method": method, "sent": False, "error": str(exc)})
            return None
        found, used_attempts = poll_for_file(fallback_start, timeout_milliseconds)
        attempts += used_attempts
        return found

    if not new_file and args.fallback_sendinput:
        new_file = run_sendinput_fallback(
            method="sendinput-virtual-key",
            sender=send_key_chord_sendinput,
            timeout_milliseconds=args.timeout_milliseconds,
        )

    if not new_file and args.fallback_scancode_sendinput:
        new_file = run_sendinput_fallback(
            method="sendinput-scancode",
            sender=send_key_chord_scancode_sendinput,
            timeout_milliseconds=args.timeout_milliseconds,
        )

    result["inputAttempts"] = input_attempts
    result["inputMethod"] = "+".join(item["method"] for item in input_attempts if item.get("sent")) or "none"
    result["attempts"] = attempts
    result["completedAtUtc"] = utc_now_text()
    result["elapsedMilliseconds"] = int((time.time() - sent_at) * 1000)
    if not new_file:
        result.update({"status": "screenshot-timeout", "ok": False, "issue": "no_new_rift_screenshot_file"})
        result["afterNewestScreenshot"] = newest_file(snapshot_files(screenshots_dir))
        return result

    source = Path(new_file["path"])
    result.update({
        "status": "captured",
        "ok": True,
        "screenshotPath": str(source),
        "screenshotLastWriteUtc": datetime.fromtimestamp(float(new_file["mtime"]), timezone.utc).isoformat(),
        "screenshotSizeBytes": int(new_file["size"]),
        "artifactPath": copy_artifact(source, output_root, key_chord),
    })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trigger RIFT's native screenshot keybind and wait for the new file.")
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--hwnd", required=True)
    parser.add_argument("--screenshots-dir")
    parser.add_argument("--output-root")
    parser.add_argument("--key-chord", default="numpad_multiply", help="Screenshot keybind to send; only NUM PAD * is allowed. Ctrl+P is forbidden.")
    parser.add_argument("--timeout-milliseconds", type=int, default=5000)
    parser.add_argument("--window-message-timeout-milliseconds", type=int, default=750)
    parser.add_argument("--poll-interval-milliseconds", type=int, default=100)
    parser.add_argument("--hold-milliseconds", type=int, default=80)
    parser.add_argument("--fallback-sendinput", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--fallback-scancode-sendinput", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = run(args)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
