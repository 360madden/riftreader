"""Exact-target emergency release helper for live RIFT input recovery.

This module intentionally sends only release/up events.  It is for recovering
from a suspected stuck movement/turn key or mouse-look button after a live
workflow is interrupted or an input backend misbehaves.  It must never send
key-down events or mouse-down events.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import platform
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RELEASE_KEYS = [
    "W",
    "A",
    "S",
    "D",
    "Q",
    "E",
    "Left",
    "Right",
    "Up",
    "Down",
    "Space",
    "Shift",
    "Control",
    "Alt",
]

DEFAULT_RELEASE_MOUSE_BUTTONS = ["Left", "Right", "Middle"]

VK_BY_NAME = {
    "W": 0x57,
    "A": 0x41,
    "S": 0x53,
    "D": 0x44,
    "Q": 0x51,
    "E": 0x45,
    "LEFT": 0x25,
    "RIGHT": 0x27,
    "UP": 0x26,
    "DOWN": 0x28,
    "SPACE": 0x20,
    "SHIFT": 0x10,
    "CONTROL": 0x11,
    "CTRL": 0x11,
    "ALT": 0x12,
}

WM_KEYUP = 0x0101
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_MBUTTONUP = 0x0208
MAPVK_VK_TO_VSC = 0
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEUP = 0x0040
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

MOUSE_RELEASE_BY_NAME = {
    "LEFT": {"message": WM_LBUTTONUP, "flag": MOUSEEVENTF_LEFTUP},
    "RIGHT": {"message": WM_RBUTTONUP, "flag": MOUSEEVENTF_RIGHTUP},
    "MIDDLE": {"message": WM_MBUTTONUP, "flag": MOUSEEVENTF_MIDDLEUP},
}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def parse_hwnd(value: str | int | None) -> int:
    if value is None:
        raise ValueError("hwnd is required")
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("hwnd is required")
    return int(text, 0)


def normalize_key_name(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("blank key name")
    upper = text.upper()
    aliases = {
        "ARROWLEFT": "LEFT",
        "LEFTARROW": "LEFT",
        "ARROWRIGHT": "RIGHT",
        "RIGHTARROW": "RIGHT",
        "ARROWUP": "UP",
        "UPARROW": "UP",
        "ARROWDOWN": "DOWN",
        "DOWNARROW": "DOWN",
        "CTRL": "CONTROL",
    }
    return aliases.get(upper, upper)


def parse_key_list(values: list[str] | None) -> list[str]:
    raw_items: list[str] = []
    if values:
        for value in values:
            raw_items.extend(part.strip() for part in str(value).split(","))
    else:
        raw_items = list(DEFAULT_RELEASE_KEYS)

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not item:
            continue
        key = normalize_key_name(item)
        if key not in VK_BY_NAME:
            raise ValueError(f"unsupported key for emergency release: {item!r}")
        if key not in seen:
            seen.add(key)
            normalized.append(key)
    if not normalized:
        raise ValueError("no keys selected for emergency release")
    return normalized


def normalize_mouse_button_name(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("blank mouse button name")
    upper = text.upper()
    aliases = {
        "L": "LEFT",
        "LEFTBUTTON": "LEFT",
        "MOUSELEFT": "LEFT",
        "R": "RIGHT",
        "RIGHTBUTTON": "RIGHT",
        "MOUSERIGHT": "RIGHT",
        "M": "MIDDLE",
        "MID": "MIDDLE",
        "MIDDLEBUTTON": "MIDDLE",
        "MOUSEMIDDLE": "MIDDLE",
    }
    return aliases.get(upper, upper)


def parse_mouse_button_list(values: list[str] | None, *, include_default: bool) -> list[str]:
    if values:
        raw_items: list[str] = []
        for value in values:
            raw_items.extend(part.strip() for part in str(value).split(","))
    elif include_default:
        raw_items = list(DEFAULT_RELEASE_MOUSE_BUTTONS)
    else:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not item:
            continue
        button = normalize_mouse_button_name(item)
        if button not in MOUSE_RELEASE_BY_NAME:
            raise ValueError(f"unsupported mouse button for emergency release: {item!r}")
        if button not in seen:
            seen.add(button)
            normalized.append(button)
    return normalized


def keyup_lparam(scan_code: int) -> int:
    return 1 | (int(scan_code) << 16) | 0xC0000000


def build_release_plan(keys: list[str]) -> list[dict[str, Any]]:
    plan = []
    for key in keys:
        vk = VK_BY_NAME[normalize_key_name(key)]
        plan.append(
            {
                "key": normalize_key_name(key),
                "virtualKey": vk,
                "virtualKeyHex": f"0x{vk:X}",
                "events": ["WM_KEYUP", "SendInput KEYEVENTF_KEYUP"],
            }
        )
    return plan


def build_mouse_release_plan(buttons: list[str]) -> list[dict[str, Any]]:
    plan = []
    for button in buttons:
        normalized = normalize_mouse_button_name(button)
        release = MOUSE_RELEASE_BY_NAME[normalized]
        plan.append(
            {
                "button": normalized,
                "windowMessage": f"0x{release['message']:X}",
                "sendInputFlag": f"0x{release['flag']:X}",
                "events": ["WM_*BUTTONUP", "SendInput MOUSEEVENTF_*UP"],
            }
        )
    return plan


def self_test() -> dict[str, Any]:
    keys = parse_key_list(None)
    mouse_buttons = parse_mouse_button_list(None, include_default=True)
    plan = build_release_plan(keys)
    mouse_plan = build_mouse_release_plan(mouse_buttons)
    bad = [
        item
        for item in [*plan, *mouse_plan]
        if any(
            "DOWN" in str(event).upper()
            and "KEYEVENTF_KEYUP" not in str(event).upper()
            and "MOUSEEVENTF_" not in str(event).upper()
            for event in item["events"]
        )
    ]
    return {
        "status": "passed" if not bad else "failed",
        "defaultKeys": keys,
        "defaultMouseButtons": mouse_buttons,
        "releasePlan": plan,
        "mouseReleasePlan": mouse_plan,
        "errors": [] if not bad else ["release plan contains a down event"],
    }


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.LPARAM),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.LPARAM),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUTUNION),
    ]


@dataclass
class WinApi:
    user32: Any
    kernel32: Any


def load_winapi() -> WinApi:
    if platform.system().lower() != "windows":
        raise RuntimeError("emergency key release requires Windows")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    return WinApi(user32=user32, kernel32=kernel32)


def query_process_image(api: WinApi, pid: int) -> str | None:
    handle = api.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not api.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        api.kernel32.CloseHandle(handle)


def verify_target(api: WinApi, hwnd: int, expected_pid: int | None, process_name: str | None) -> dict[str, Any]:
    hwnd_value = wintypes.HWND(hwnd)
    result: dict[str, Any] = {
        "hwnd": hwnd,
        "hwndHex": f"0x{hwnd:X}",
        "isWindow": bool(api.user32.IsWindow(hwnd_value)),
    }
    if not result["isWindow"]:
        result["blocker"] = "hwnd-not-window"
        return result

    owner_pid = wintypes.DWORD(0)
    thread_id = api.user32.GetWindowThreadProcessId(hwnd_value, ctypes.byref(owner_pid))
    result["ownerPid"] = int(owner_pid.value)
    result["threadId"] = int(thread_id)
    result["ownerMatchesExpectedPid"] = expected_pid is None or int(owner_pid.value) == int(expected_pid)
    if expected_pid is not None and int(owner_pid.value) != int(expected_pid):
        result["blocker"] = f"hwnd-owner-pid-mismatch:owner={owner_pid.value};expected={expected_pid}"
        return result

    image = query_process_image(api, int(owner_pid.value))
    result["processImage"] = image
    if process_name:
        expected = str(process_name).removesuffix(".exe").lower()
        actual = ((image or "").rsplit("\\", 1)[-1]).removesuffix(".exe").lower()
        result["processNameMatches"] = actual == expected
        if actual and actual != expected:
            result["blocker"] = f"process-name-mismatch:actual={actual};expected={expected}"
    return result


def send_release_events(
    *,
    api: WinApi,
    hwnd: int,
    keys: list[str],
    release_delay_ms: int,
    skip_postmessage: bool,
    skip_sendinput: bool,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    hwnd_value = wintypes.HWND(hwnd)
    for key in keys:
        vk = VK_BY_NAME[normalize_key_name(key)]
        scan_code = int(api.user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC))
        lparam = keyup_lparam(scan_code)
        item: dict[str, Any] = {
            "key": normalize_key_name(key),
            "virtualKey": vk,
            "virtualKeyHex": f"0x{vk:X}",
            "scanCode": scan_code,
            "lParamHex": f"0x{lparam & 0xFFFFFFFF:X}",
            "postMessageKeyupSent": False,
            "sendInputKeyupSent": False,
        }
        if not skip_postmessage:
            item["postMessageKeyupSent"] = bool(
                api.user32.PostMessageW(hwnd_value, WM_KEYUP, wintypes.WPARAM(vk), wintypes.LPARAM(lparam))
            )
        if not skip_sendinput:
            keyboard_input = INPUT()
            keyboard_input.type = INPUT_KEYBOARD
            keyboard_input.u.ki.wVk = vk
            keyboard_input.u.ki.wScan = 0
            keyboard_input.u.ki.dwFlags = KEYEVENTF_KEYUP
            keyboard_input.u.ki.time = 0
            keyboard_input.u.ki.dwExtraInfo = 0
            sent = api.user32.SendInput(1, ctypes.byref(keyboard_input), ctypes.sizeof(INPUT))
            item["sendInputKeyupSent"] = int(sent) == 1
            if int(sent) != 1:
                item["sendInputLastError"] = ctypes.get_last_error()
        results.append(item)
        if release_delay_ms > 0:
            time.sleep(release_delay_ms / 1000.0)
    return results


def send_mouse_release_events(
    *,
    api: WinApi,
    hwnd: int,
    buttons: list[str],
    release_delay_ms: int,
    skip_postmessage: bool,
    skip_sendinput: bool,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    hwnd_value = wintypes.HWND(hwnd)
    for button in buttons:
        normalized = normalize_mouse_button_name(button)
        release = MOUSE_RELEASE_BY_NAME[normalized]
        item: dict[str, Any] = {
            "button": normalized,
            "windowMessage": f"0x{release['message']:X}",
            "sendInputFlag": f"0x{release['flag']:X}",
            "postMessageMouseUpSent": False,
            "sendInputMouseUpSent": False,
        }
        if not skip_postmessage:
            item["postMessageMouseUpSent"] = bool(
                api.user32.PostMessageW(
                    hwnd_value,
                    wintypes.UINT(release["message"]),
                    wintypes.WPARAM(0),
                    wintypes.LPARAM(0),
                )
            )
        if not skip_sendinput:
            mouse_input = INPUT()
            mouse_input.type = INPUT_MOUSE
            mouse_input.u.mi.dx = 0
            mouse_input.u.mi.dy = 0
            mouse_input.u.mi.mouseData = 0
            mouse_input.u.mi.dwFlags = release["flag"]
            mouse_input.u.mi.time = 0
            mouse_input.u.mi.dwExtraInfo = 0
            sent = api.user32.SendInput(1, ctypes.byref(mouse_input), ctypes.sizeof(INPUT))
            item["sendInputMouseUpSent"] = int(sent) == 1
            if int(sent) != 1:
                item["sendInputLastError"] = ctypes.get_last_error()
        results.append(item)
        if release_delay_ms > 0:
            time.sleep(release_delay_ms / 1000.0)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send exact-target emergency key-up events only.")
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--hwnd", required=False)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--key", action="append", default=None, help="Key to release; repeat or comma-separate.")
    parser.add_argument(
        "--include-mouse-buttons",
        action="store_true",
        help="Also release left/right/middle mouse buttons with up-only events.",
    )
    parser.add_argument("--mouse-button", action="append", default=None, help="Mouse button to release; repeat or comma-separate.")
    parser.add_argument("--release-delay-ms", type=int, default=10)
    parser.add_argument("--skip-postmessage", action="store_true")
    parser.add_argument("--skip-sendinput", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def render_markdown(summary: dict[str, Any]) -> str:
    rows = []
    for item in summary.get("releaseResults") or summary.get("releasePlan") or []:
        rows.append(
            "| `{key}` | `{vk}` | `{post}` | `{send}` |".format(
                key=item.get("key"),
                vk=item.get("virtualKeyHex"),
                post=item.get("postMessageKeyupSent", "planned"),
                send=item.get("sendInputKeyupSent", "planned"),
            )
        )
    mouse_rows = []
    for item in summary.get("mouseReleaseResults") or summary.get("mouseReleasePlan") or []:
        mouse_rows.append(
            "| `{button}` | `{post}` | `{send}` |".format(
                button=item.get("button"),
                post=item.get("postMessageMouseUpSent", "planned"),
                send=item.get("sendInputMouseUpSent", "planned"),
            )
        )
    return "\n".join(
        [
            "# RiftReader emergency key release",
            "",
            f"- Status: `{summary.get('status')}`",
            f"- Generated: `{summary.get('generatedAtUtc')}`",
            f"- Target: `{summary.get('target', {}).get('processId')}` / `{summary.get('target', {}).get('targetWindowHandle')}`",
            f"- Movement sent: `{summary.get('safety', {}).get('movementSent')}`",
            f"- Key-down sent: `{summary.get('safety', {}).get('keyDownSent')}`",
            f"- Mouse-down sent: `{summary.get('safety', {}).get('mouseDownSent')}`",
            f"- Input type: `{summary.get('safety', {}).get('inputType')}`",
            "",
            "| Key | VK | PostMessage keyup | SendInput keyup |",
            "|---|---|---|---|",
            *rows,
            "",
            "| Mouse button | PostMessage mouse-up | SendInput mouse-up |",
            "|---|---|---|",
            *mouse_rows,
            "",
        ]
    )


def maybe_write_artifacts(summary: dict[str, Any], output_root: Path | None) -> None:
    if output_root is None:
        return
    run_dir = output_root / f"emergency-key-release-{utc_stamp()}"
    summary_path = run_dir / "summary.json"
    markdown_path = run_dir / "summary.md"
    summary.setdefault("artifacts", {})
    summary["artifacts"]["runDirectory"] = str(run_dir)
    summary["artifacts"]["summaryJson"] = str(summary_path)
    summary["artifacts"]["summaryMarkdown"] = str(markdown_path)
    write_json(summary_path, summary)
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if args.self_test:
        result = self_test()
        maybe_write_artifacts(result, args.output_root)
        return (0 if result["status"] == "passed" else 1), result

    keys = parse_key_list(args.key)
    mouse_buttons = parse_mouse_button_list(args.mouse_button, include_default=bool(args.include_mouse_buttons))
    hwnd = parse_hwnd(args.hwnd)
    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "riftreader-emergency-key-release",
        "generatedAtUtc": utc_iso(),
        "status": "planned" if args.dry_run else "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "target": {
            "processName": args.process_name,
            "processId": args.pid,
            "targetWindowHandle": f"0x{hwnd:X}",
        },
        "releasePlan": build_release_plan(keys),
        "mouseReleasePlan": build_mouse_release_plan(mouse_buttons),
        "releaseResults": [],
        "mouseReleaseResults": [],
        "safety": {
            "movementSent": False,
            "keyDownSent": False,
            "mouseDownSent": False,
            "mouseUpSent": False,
            "inputSent": False,
            "inputType": "keyup-and-mouseup-release" if mouse_buttons else "keyup-only",
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "providerWrites": False,
            "gitMutation": False,
        },
    }

    if args.dry_run:
        maybe_write_artifacts(summary, args.output_root)
        return 0, summary

    api = load_winapi()
    target = verify_target(api, hwnd, args.pid, args.process_name)
    summary["targetVerification"] = target
    if target.get("blocker"):
        summary["status"] = "blocked"
        summary["blockers"].append(str(target["blocker"]))
        maybe_write_artifacts(summary, args.output_root)
        return 2, summary

    results = send_release_events(
        api=api,
        hwnd=hwnd,
        keys=keys,
        release_delay_ms=max(0, int(args.release_delay_ms)),
        skip_postmessage=bool(args.skip_postmessage),
        skip_sendinput=bool(args.skip_sendinput),
    )
    mouse_results = send_mouse_release_events(
        api=api,
        hwnd=hwnd,
        buttons=mouse_buttons,
        release_delay_ms=max(0, int(args.release_delay_ms)),
        skip_postmessage=bool(args.skip_postmessage),
        skip_sendinput=bool(args.skip_sendinput),
    )
    summary["releaseResults"] = results
    summary["mouseReleaseResults"] = mouse_results
    summary["safety"]["inputSent"] = True
    summary["safety"]["mouseUpSent"] = bool(mouse_results)
    failed = [
        item["key"]
        for item in results
        if not (item.get("postMessageKeyupSent") or item.get("sendInputKeyupSent"))
    ]
    failed_mouse = [
        item["button"]
        for item in mouse_results
        if not (item.get("postMessageMouseUpSent") or item.get("sendInputMouseUpSent"))
    ]
    if failed or failed_mouse:
        summary["status"] = "failed"
        if failed:
            summary["errors"].append(f"keyup-release-failed:{','.join(failed)}")
        if failed_mouse:
            summary["errors"].append(f"mouseup-release-failed:{','.join(failed_mouse)}")
        maybe_write_artifacts(summary, args.output_root)
        return 1, summary

    summary["status"] = "released-keyup"
    maybe_write_artifacts(summary, args.output_root)
    return 0, summary


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        exit_code, summary = run(args)
    except Exception as exc:  # noqa: BLE001
        exit_code = 1
        summary = {
            "schemaVersion": 1,
            "mode": "riftreader-emergency-key-release",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "blockers": [],
            "warnings": [],
            "errors": [{"type": type(exc).__name__, "message": str(exc)}],
            "safety": {
                "movementSent": False,
                "keyDownSent": False,
                "mouseDownSent": False,
                "mouseUpSent": False,
                "inputSent": False,
                "inputType": "none",
                "noCheatEngine": True,
                "x64dbgAttach": False,
                "providerWrites": False,
                "gitMutation": False,
            },
        }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps({"status": summary.get("status"), "blockers": summary.get("blockers")}))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
