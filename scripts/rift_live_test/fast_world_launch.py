from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .character_login_screen_state import (
    BASE_CLIENT_HEIGHT,
    BASE_CLIENT_WIDTH,
    classify_landmarks,
    classify_screen,
)
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
KIND = "riftreader-fast-world-launch"

GLYPH_PROCESS = "GlyphClientApp.exe"
RIFT_PROCESS = "rift_x64.exe"
DEFAULT_GLYPH_EXE = Path(r"C:\Program Files (x86)\Glyph\GlyphClientApp.exe")
DEFAULT_RIFT_SHORTCUT = Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Glyph\RIFT.lnk")
DEFAULT_OUTPUT_ROOT = Path(".riftreader-local") / "fast-world-launch"
DEFAULT_GLYPH_PLAY_POINT = (970, 100)
DEFAULT_CHAR_PLAY_POINT = (517, 343)
DEFAULT_POLL_INTERVAL_SECONDS = 0.35
DEFAULT_TIMEOUT_SECONDS = 240.0
DEFAULT_LAUNCHER_READY_TIMEOUT_SECONDS = 45.0
DEFAULT_RIFT_WINDOW_TIMEOUT_SECONDS = 90.0
DEFAULT_WORLD_LOAD_TIMEOUT_SECONDS = 180.0

TH32CS_SNAPPROCESS = 0x00000002
MAX_PATH = 260
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
SW_RESTORE = 9
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
BENCHMARK_MODES = ("auto", "warm-glyph-after-game-kill", "warm-glyph", "true-cold")


if os.name == "nt":
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
else:
    WNDENUMPROC = None  # type: ignore[assignment]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


@dataclass(frozen=True)
class ProcessInfo:
    name: str
    process_id: int
    parent_process_id: int
    executable_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "processId": self.process_id,
            "parentProcessId": self.parent_process_id,
            "executablePath": self.executable_path,
        }


@dataclass(frozen=True)
class WindowInfo:
    window_handle: int
    process_id: int
    title: str
    class_name: str
    is_visible: bool
    is_minimized: bool
    window_rect: dict[str, int]
    client_rect: dict[str, int]
    client_origin: dict[str, int]

    @property
    def client_width(self) -> int:
        return int(self.client_rect.get("width", 0))

    @property
    def client_height(self) -> int:
        return int(self.client_rect.get("height", 0))

    def as_dict(self) -> dict[str, Any]:
        return {
            "windowHandle": f"0x{self.window_handle:X}",
            "processId": self.process_id,
            "title": self.title,
            "className": self.class_name,
            "isVisible": self.is_visible,
            "isMinimized": self.is_minimized,
            "windowRect": self.window_rect,
            "clientRect": self.client_rect,
            "clientOrigin": self.client_origin,
            "clientSize": {"width": self.client_width, "height": self.client_height},
        }


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def repo_relative_or_absolute(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("/", "\\")
    except ValueError:
        return str(path.resolve())


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def load_kernel32() -> Any:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    return kernel32


def load_user32() -> Any:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    user32.mouse_event.restype = None
    return user32


def process_image_path(kernel32: Any, process_id: int) -> str | None:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(process_id))
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
    finally:
        kernel32.CloseHandle(handle)
    return None


def collect_processes(names: set[str] | None = None) -> list[ProcessInfo]:
    if os.name != "nt":
        return []
    wanted = {name.casefold() for name in names} if names else None
    kernel32 = load_kernel32()
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        return []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        processes: list[ProcessInfo] = []
        has_entry = bool(kernel32.Process32FirstW(snapshot, ctypes.byref(entry)))
        while has_entry:
            name = str(entry.szExeFile)
            if wanted is None or name.casefold() in wanted:
                pid = int(entry.th32ProcessID)
                processes.append(
                    ProcessInfo(
                        name=name,
                        process_id=pid,
                        parent_process_id=int(entry.th32ParentProcessID),
                        executable_path=process_image_path(kernel32, pid),
                    )
                )
            has_entry = bool(kernel32.Process32NextW(snapshot, ctypes.byref(entry)))
        return sorted(processes, key=lambda item: (item.name.casefold(), item.process_id))
    finally:
        kernel32.CloseHandle(snapshot)


def terminate_process(process_id: int) -> dict[str, Any]:
    kernel32 = load_kernel32()
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, int(process_id))
    if not handle:
        return {
            "processId": process_id,
            "terminated": False,
            "error": f"OpenProcess(PROCESS_TERMINATE) failed:{ctypes.get_last_error()}",
        }
    try:
        ok = bool(kernel32.TerminateProcess(handle, 1))
        return {
            "processId": process_id,
            "terminated": ok,
            "error": None if ok else f"TerminateProcess failed:{ctypes.get_last_error()}",
        }
    finally:
        kernel32.CloseHandle(handle)


def terminate_rift_processes(
    processes: list[ProcessInfo],
    *,
    dry_run: bool,
    wait_timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    rift_processes = sorted(
        [process for process in processes if process.name.casefold() == RIFT_PROCESS.casefold()],
        key=lambda item: item.process_id,
    )
    result: dict[str, Any] = {
        "processes": [process.as_dict() for process in rift_processes],
        "dryRun": dry_run,
        "terminated": [],
        "remaining": [],
        "waitTimeoutSeconds": wait_timeout_seconds,
    }
    if dry_run or not rift_processes:
        result["remaining"] = [process.as_dict() for process in rift_processes]
        return result
    for process in rift_processes:
        result["terminated"].append(terminate_process(process.process_id))
    deadline = time.monotonic() + max(0.1, wait_timeout_seconds)
    remaining = rift_processes
    while time.monotonic() < deadline:
        time.sleep(0.25)
        remaining = [
            process
            for process in collect_processes({RIFT_PROCESS})
            if process.name.casefold() == RIFT_PROCESS.casefold()
        ]
        if not remaining:
            break
    result["remaining"] = [process.as_dict() for process in sorted(remaining, key=lambda item: item.process_id)]
    return result


def rect_to_dict(rect: wintypes.RECT) -> dict[str, int]:
    return {
        "left": int(rect.left),
        "top": int(rect.top),
        "right": int(rect.right),
        "bottom": int(rect.bottom),
        "width": int(rect.right - rect.left),
        "height": int(rect.bottom - rect.top),
    }


def get_window_text(user32: Any, hwnd: int) -> str:
    length = int(user32.GetWindowTextLengthW(wintypes.HWND(hwnd)))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, length + 1)
    return buffer.value


def get_window_class(user32: Any, hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetClassNameW(wintypes.HWND(hwnd), buffer, len(buffer))
    return buffer.value


def collect_windows_for_pids(pids: set[int]) -> list[WindowInfo]:
    if os.name != "nt" or not pids:
        return []
    user32 = load_user32()
    windows: list[WindowInfo] = []

    @WNDENUMPROC  # type: ignore[misc]
    def enum_proc(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        hwnd_int = int(hwnd)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(wintypes.HWND(hwnd_int), ctypes.byref(pid))
        if int(pid.value) not in pids:
            return True
        window_rect = wintypes.RECT()
        client_rect = wintypes.RECT()
        point = wintypes.POINT(0, 0)
        window_rect_dict = {}
        client_rect_dict = {}
        if user32.GetWindowRect(wintypes.HWND(hwnd_int), ctypes.byref(window_rect)):
            window_rect_dict = rect_to_dict(window_rect)
        if user32.GetClientRect(wintypes.HWND(hwnd_int), ctypes.byref(client_rect)):
            client_rect_dict = rect_to_dict(client_rect)
        user32.ClientToScreen(wintypes.HWND(hwnd_int), ctypes.byref(point))
        windows.append(
            WindowInfo(
                window_handle=hwnd_int,
                process_id=int(pid.value),
                title=get_window_text(user32, hwnd_int),
                class_name=get_window_class(user32, hwnd_int),
                is_visible=bool(user32.IsWindowVisible(wintypes.HWND(hwnd_int))),
                is_minimized=bool(user32.IsIconic(wintypes.HWND(hwnd_int))),
                window_rect=window_rect_dict,
                client_rect=client_rect_dict,
                client_origin={"x": int(point.x), "y": int(point.y)},
            )
        )
        return True

    user32.EnumWindows(enum_proc, 0)
    return sorted(windows, key=lambda item: (item.process_id, item.window_handle))


def select_best_window(windows: list[WindowInfo], *, expected_title: str | None = None) -> WindowInfo | None:
    if not windows:
        return None

    def score(window: WindowInfo) -> tuple[int, int]:
        value = 0
        if window.is_visible:
            value += 100
        if not window.is_minimized:
            value += 50
        if expected_title and window.title.casefold() == expected_title.casefold():
            value += 50
        elif window.title:
            value += 10
        value += min(20, max(0, window.client_width * window.client_height // 50000))
        return value, window.window_handle

    return max(windows, key=score)


def import_pillow_grab() -> Any:
    try:
        from PIL import ImageGrab
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Pillow ImageGrab is required for fast launch visual gates: {exc}") from exc
    return ImageGrab


def capture_window_image(window: WindowInfo, *, client: bool) -> Any:
    ImageGrab = import_pillow_grab()
    if client:
        left = window.client_origin["x"]
        top = window.client_origin["y"]
        bbox = (left, top, left + window.client_width, top + window.client_height)
    else:
        rect = window.window_rect
        bbox = (rect["left"], rect["top"], rect["right"], rect["bottom"])
    return ImageGrab.grab(bbox=bbox).convert("RGB")


def save_image(image: Any, output_dir: Path, name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}-{utc_stamp()}.png"
    image.save(path)
    return path


def pixel_fractions(image: Any, bbox: tuple[int, int, int, int]) -> dict[str, float]:
    crop = image.crop(bbox).convert("RGB")
    data = crop.tobytes()
    pixel_count = max(1, len(data) // 3)
    counts = {
        "colorful": 0,
        "bright": 0,
        "yellow": 0,
        "green": 0,
        "dark": 0,
        "white": 0,
    }
    for index in range(0, len(data), 3):
        r, g, b = data[index], data[index + 1], data[index + 2]
        max_channel = max(r, g, b)
        min_channel = min(r, g, b)
        if max_channel - min_channel > 50 and max_channel > 70:
            counts["colorful"] += 1
        if max_channel > 150:
            counts["bright"] += 1
        if r > 200 and g > 150 and b < 90:
            counts["yellow"] += 1
        if g > 80 and g >= r * 0.75 and g >= b * 0.75:
            counts["green"] += 1
        if max_channel < 45:
            counts["dark"] += 1
        if r > 180 and g > 180 and b > 180:
            counts["white"] += 1
    return {key: value / pixel_count for key, value in counts.items()}


def find_glyph_play_button(image: Any) -> dict[str, Any]:
    width, height = image.size
    search_left = int(width * 0.62)
    search_top = 0
    search_right = width
    search_bottom = max(1, int(height * 0.24))
    data = image.crop((search_left, search_top, search_right, search_bottom)).convert("RGB")
    raw = data.tobytes()
    xs: list[int] = []
    ys: list[int] = []
    crop_width = search_right - search_left
    for offset in range(0, len(raw), 3):
        r, g, b = raw[offset], raw[offset + 1], raw[offset + 2]
        # Glyph's PLAY button is a saturated yellow rectangle. Restricting the
        # search to the upper-right launcher quadrant keeps the scan independent
        # of localized text and avoids clicking ads/news cards lower down.
        if r >= 215 and g >= 155 and b <= 80 and abs(r - g) <= 110:
            pixel_index = offset // 3
            xs.append(search_left + (pixel_index % crop_width))
            ys.append(search_top + (pixel_index // crop_width))
    pixel_count = len(xs)
    required_pixels = max(400, int(width * height * 0.003))
    if pixel_count < required_pixels:
        return {
            "found": False,
            "reason": f"yellow-play-pixel-count-too-low:{pixel_count}<{required_pixels}",
            "pixelCount": pixel_count,
            "requiredPixels": required_pixels,
            "searchBox": [search_left, search_top, search_right, search_bottom],
        }
    bbox = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
    center = [round((bbox[0] + bbox[2]) / 2), round((bbox[1] + bbox[3]) / 2)]
    area = max(1, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    fill_fraction = pixel_count / area
    return {
        "found": fill_fraction >= 0.35,
        "pixelCount": pixel_count,
        "requiredPixels": required_pixels,
        "bbox": bbox,
        "centerWindowPoint": center,
        "fillFraction": round(fill_fraction, 4),
        "searchBox": [search_left, search_top, search_right, search_bottom],
        "reason": None if fill_fraction >= 0.35 else f"yellow-play-fill-too-low:{fill_fraction:.3f}<0.350",
    }


def scale_client_point(point: tuple[int, int], *, width: int, height: int) -> list[int]:
    if width <= 0 or height <= 0:
        return [point[0], point[1]]
    return [
        round(point[0] * width / BASE_CLIENT_WIDTH),
        round(point[1] * height / BASE_CLIENT_HEIGHT),
    ]


def world_hud_score(image: Any) -> dict[str, Any]:
    width, height = image.size
    bottom = pixel_fractions(image, (int(width * 0.28), int(height * 0.82), int(width * 0.73), height))
    right = pixel_fractions(image, (int(width * 0.77), 0, width, int(height * 0.38)))
    bottom_green = clamp(bottom["green"] / 0.45)
    bottom_bright = clamp(bottom["bright"] / 0.08)
    right_dark = clamp(right["dark"] / 0.25)
    right_green = clamp(right["green"] / 0.12)
    score = round(0.40 * bottom_green + 0.20 * bottom_bright + 0.20 * right_dark + 0.20 * right_green, 4)
    return {
        "score": score,
        "passed": score >= 0.65,
        "threshold": 0.65,
        "regions": {
            "bottomHud": {key: round(value, 4) for key, value in bottom.items()},
            "rightHud": {key: round(value, 4) for key, value in right.items()},
        },
    }


def loading_or_transition_score(image: Any) -> dict[str, Any]:
    width, height = image.size
    # RIFT loading art is letterboxed in this 640x360 client: the top and
    # bottom strips are nearly pure black. In-world and character-select frames
    # can be dark, but not both border strips at this density. This gate prevents
    # a colorful loading painting from being mistaken for HUD presence.
    strip_height = max(4, round(height * 0.022))
    top = pixel_fractions(image, (0, 0, width, strip_height))
    bottom = pixel_fractions(image, (0, height - strip_height, width, height))
    score = round((top["dark"] + bottom["dark"]) / 2, 4)
    return {
        "score": score,
        "passed": score >= 0.85,
        "threshold": 0.85,
        "stripHeight": strip_height,
        "regions": {
            "topBorder": {key: round(value, 4) for key, value in top.items()},
            "bottomBorder": {key: round(value, 4) for key, value in bottom.items()},
        },
    }


def modal_dialog_score(image: Any) -> dict[str, Any]:
    width, height = image.size
    dialog = pixel_fractions(
        image,
        (
            int(width * 0.34),
            int(height * 0.42),
            int(width * 0.66),
            int(height * 0.60),
        ),
    )
    ok_button = pixel_fractions(
        image,
        (
            int(width * 0.445),
            int(height * 0.52),
            int(width * 0.565),
            int(height * 0.57),
        ),
    )
    dark_component = clamp(dialog["dark"] / 0.55)
    ok_green_component = clamp(ok_button["green"] / 0.15)
    ok_dark_component = clamp(ok_button["dark"] / 0.55)
    score = round(0.45 * dark_component + 0.35 * ok_green_component + 0.20 * ok_dark_component, 4)
    return {
        "score": score,
        "passed": score >= 0.85,
        "threshold": 0.85,
        "regions": {
            "centerDialog": {key: round(value, 4) for key, value in dialog.items()},
            "okButton": {key: round(value, 4) for key, value in ok_button.items()},
        },
    }


def classify_rift_client_image(image: Any) -> dict[str, Any]:
    width, height = image.size
    landmarks, character_select_confidence = classify_landmarks(
        image,
        expected_width=BASE_CLIENT_WIDTH,
        expected_height=BASE_CLIENT_HEIGHT,
    )
    character_select = classify_screen(landmarks, character_select_confidence)
    modal = modal_dialog_score(image)
    loading = loading_or_transition_score(image)
    world = world_hud_score(image)
    world_strong = float(world["score"]) >= 0.85
    if modal["passed"]:
        classification = "modal-dialog-blocker"
    elif loading["passed"]:
        classification = "loading-or-transition"
    elif world_strong:
        classification = "in-world-likely"
    elif character_select == "character-selection-not-in-world":
        classification = "character-select"
    elif world["passed"]:
        classification = "in-world-likely"
    elif character_select == "not-character-select-or-transition":
        classification = "transition-or-non-character-select"
    else:
        classification = "unknown"
    return {
        "classification": classification,
        "width": width,
        "height": height,
        "characterSelectClassifier": {
            "classification": character_select,
            "confidence": character_select_confidence,
            "landmarks": landmarks,
        },
        "modalDialogClassifier": modal,
        "loadingOrTransitionClassifier": loading,
        "worldHudClassifier": world,
    }


def focus_window(window: WindowInfo) -> dict[str, Any]:
    user32 = load_user32()
    hwnd = wintypes.HWND(window.window_handle)
    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.05)
    set_foreground = bool(user32.SetForegroundWindow(hwnd))
    time.sleep(0.10)
    foreground = int(user32.GetForegroundWindow() or 0)
    return {
        "windowHandle": f"0x{window.window_handle:X}",
        "setForegroundReturned": set_foreground,
        "foregroundWindowHandle": f"0x{foreground:X}",
        "isForeground": foreground == window.window_handle,
    }


def click_screen_point(x: int, y: int, *, hold_seconds: float = 0.06) -> None:
    user32 = load_user32()
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
    time.sleep(max(0.01, hold_seconds))
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)


def click_window_point(window: WindowInfo, point: list[int], *, client: bool) -> dict[str, Any]:
    if client:
        x = window.client_origin["x"] + int(point[0])
        y = window.client_origin["y"] + int(point[1])
        coordinate_space = "client"
    else:
        x = window.window_rect["left"] + int(point[0])
        y = window.window_rect["top"] + int(point[1])
        coordinate_space = "window"
    click_screen_point(x, y)
    return {
        "coordinateSpace": coordinate_space,
        "point": point,
        "screenPoint": [x, y],
        "windowHandle": f"0x{window.window_handle:X}",
        "processId": window.process_id,
    }


def wscript_launcher_script_text(*, glyph_exe: Path, shortcut: Path | None) -> str:
    if shortcut and shortcut.exists():
        target = str(shortcut)
        current_directory = str(shortcut.parent)
        run_line = f'sh.Run Chr(34) & "{target}" & Chr(34), 1, False'
    else:
        target = str(glyph_exe)
        current_directory = str(glyph_exe.parent)
        run_line = f'sh.Run Chr(34) & "{target}" & Chr(34) & " -game 1", 1, False'
    return "\n".join(
        [
            'Set sh = CreateObject("WScript.Shell")',
            f'sh.CurrentDirectory = "{current_directory}"',
            run_line,
            "WScript.Quit 0",
            "",
        ]
    )


def start_launcher(
    *,
    glyph_exe: Path,
    shortcut: Path | None,
    method: str,
    output_dir: Path,
    dry_run: bool,
) -> dict[str, Any]:
    command: list[str]
    script_path: Path | None = None
    if method == "wscript":
        script_path = output_dir / "launch-rift-glyph.vbs"
        write_text_atomic(script_path, wscript_launcher_script_text(glyph_exe=glyph_exe, shortcut=shortcut))
        command = ["cscript.exe", "//nologo", str(script_path)]
    elif method == "shortcut":
        selected_shortcut = shortcut or DEFAULT_RIFT_SHORTCUT
        command = ["cmd.exe", "/c", "start", "", str(selected_shortcut)]
    else:
        command = [str(glyph_exe), "-game", "1"]

    if dry_run:
        return {
            "method": method,
            "dryRun": True,
            "command": command,
            "scriptPath": str(script_path) if script_path else None,
            "started": False,
        }
    start = time.monotonic()
    try:
        if method == "direct":
            subprocess.Popen(command, cwd=str(glyph_exe.parent))  # noqa: S603 - explicit local executable path.
            exit_code = None
            stdout = stderr = ""
        else:
            completed = subprocess.run(
                command,
                cwd=str(output_dir),
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        return {
            "method": method,
            "dryRun": False,
            "command": command,
            "scriptPath": str(script_path) if script_path else None,
            "started": True,
            "exitCode": exit_code,
            "stdoutPreview": stdout[:1000],
            "stderrPreview": stderr[:1000],
            "durationSeconds": round(time.monotonic() - start, 3),
        }
    except Exception as exc:  # noqa: BLE001 - launch helper must return durable diagnostics.
        return {
            "method": method,
            "dryRun": False,
            "command": command,
            "scriptPath": str(script_path) if script_path else None,
            "started": False,
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "durationSeconds": round(time.monotonic() - start, 3),
        }


def safety_state(
    *,
    dry_run: bool,
    launcher_clicked: bool,
    character_clicked: bool,
    launch_attempted: bool,
    rift_processes_terminated: bool = False,
) -> dict[str, Any]:
    return {
        "dryRun": dry_run,
        "movementSent": False,
        "keyInputSent": False,
        "mouseClickSent": launcher_clicked or character_clicked,
        "launcherButtonPressed": launcher_clicked,
        "characterPlayPressed": character_clicked,
        "worldEntryClicked": character_clicked,
        "launchAttempted": launch_attempted,
        "processTerminated": rift_processes_terminated,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgAttachStarted": False,
        "providerWrites": False,
        "gitMutation": False,
    }


def summarize_process_windows(processes: list[ProcessInfo], windows: list[WindowInfo]) -> dict[str, Any]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for process in processes:
        by_name.setdefault(process.name, []).append(process.as_dict())
    return {
        "processes": by_name,
        "windows": [window.as_dict() for window in windows],
    }


def duplicate_rift_process_blocker(processes: list[ProcessInfo]) -> dict[str, Any] | None:
    rift_processes = [process for process in processes if process.name.casefold() == RIFT_PROCESS.casefold()]
    if len(rift_processes) <= 1:
        return None
    return {
        "blocker": "multiple-rift-clients-detected",
        "processes": [process.as_dict() for process in sorted(rift_processes, key=lambda item: item.process_id)],
    }


def rift_processes_from(processes: list[ProcessInfo]) -> list[ProcessInfo]:
    return sorted(
        [process for process in processes if process.name.casefold() == RIFT_PROCESS.casefold()],
        key=lambda item: item.process_id,
    )


def existing_rift_same_account_launch_blocker(processes: list[ProcessInfo]) -> dict[str, Any] | None:
    """Fail closed before clicking Glyph PLAY while a game client exists.

    Glyph PLAY launches with the currently logged-in Glyph account. The helper
    cannot prove a visible RIFT client belongs to a different account, so any
    existing rift_x64.exe process is treated as a same-account session conflict
    until it is intentionally killed and verified gone.
    """

    rift_processes = rift_processes_from(processes)
    if not rift_processes:
        return None
    return {
        "blocker": "same-account-rift-client-already-running",
        "policy": "refuse-glyph-play-while-any-rift-client-exists",
        "reason": "Glyph PLAY uses the logged-in Glyph account; launching while an existing game client is logged in can create the duplicate-session modal.",
        "processes": [process.as_dict() for process in rift_processes],
    }


def existing_rift_new_launch_blocker(
    processes: list[ProcessInfo],
    windows: list[WindowInfo],
    *,
    reason: str,
) -> dict[str, Any]:
    return {
        "blocker": "existing-rift-client-present-new-launch-blocked",
        "policy": "reuse-confirmed-in-world-client-or-block-before-new-launch",
        "reason": reason,
        "processes": [process.as_dict() for process in rift_processes_from(processes)],
        "windows": [window.as_dict() for window in windows],
    }


def benchmark_mode_options(mode: str) -> dict[str, bool]:
    if mode == "warm-glyph-after-game-kill":
        return {"requireExistingGlyph": True, "killExistingRiftFirst": True, "requireNoGlyph": False}
    if mode == "warm-glyph":
        return {"requireExistingGlyph": True, "killExistingRiftFirst": False, "requireNoGlyph": False}
    if mode == "true-cold":
        return {"requireExistingGlyph": False, "killExistingRiftFirst": False, "requireNoGlyph": True}
    return {"requireExistingGlyph": False, "killExistingRiftFirst": False, "requireNoGlyph": False}


def event(now: float, start: float, stage: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "atUtc": utc_iso(),
        "offsetSeconds": round(now - start, 3),
        "stage": stage,
        "detail": detail or {},
    }


def build_summary(
    *,
    repo_root: Path,
    output_root: Path,
    dry_run: bool,
    benchmark_mode: str,
    require_existing_glyph: bool,
    kill_existing_rift_first: bool,
    start_method: str,
    glyph_exe: Path,
    shortcut: Path | None,
    timeout_seconds: float,
    poll_interval_seconds: float,
    launcher_ready_timeout_seconds: float,
    rift_window_timeout_seconds: float,
    world_load_timeout_seconds: float,
    allow_fixed_glyph_click_fallback: bool,
) -> dict[str, Any]:
    started_monotonic = time.monotonic()
    output_root.mkdir(parents=True, exist_ok=True)
    screenshots_dir = output_root / "screenshots"
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    launch_attempt: dict[str, Any] | None = None
    terminated_rift_processes: dict[str, Any] | None = None
    launcher_clicked = False
    character_clicked = False
    launch_attempted = False
    rift_processes_terminated = False
    final_classification: dict[str, Any] | None = None
    final_window: WindowInfo | None = None
    existing_client: dict[str, Any] | None = None
    state = "initial"
    launcher_started_at: float | None = None
    launcher_clicked_at: float | None = None
    rift_first_seen_at: float | None = None
    character_clicked_at: float | None = None

    if os.name != "nt":
        blockers.append("windows-required")
    if not glyph_exe.exists():
        blockers.append(f"glyph-exe-not-found:{glyph_exe}")
    if shortcut and not shortcut.exists():
        warnings.append(f"rift-shortcut-not-found:{shortcut};fallback-glyph-exe")

    mode_defaults = benchmark_mode_options(benchmark_mode)
    require_existing_glyph = require_existing_glyph or mode_defaults["requireExistingGlyph"]
    kill_existing_rift_first = kill_existing_rift_first or mode_defaults["killExistingRiftFirst"]
    require_no_glyph = mode_defaults["requireNoGlyph"]

    initial_processes = collect_processes({GLYPH_PROCESS, RIFT_PROCESS}) if os.name == "nt" else []
    initial_glyph_processes = [
        process for process in initial_processes if process.name.casefold() == GLYPH_PROCESS.casefold()
    ]
    initial_rift_processes = [
        process for process in initial_processes if process.name.casefold() == RIFT_PROCESS.casefold()
    ]
    initial_observed_windows = (
        collect_windows_for_pids({process.process_id for process in initial_processes})
        if initial_rift_processes and os.name == "nt"
        else []
    )
    events.append(
        event(
            time.monotonic(),
            started_monotonic,
            "preflight-processes",
            {
                "benchmarkMode": benchmark_mode,
                "glyphProcesses": [process.as_dict() for process in initial_glyph_processes],
                "riftProcesses": [process.as_dict() for process in initial_rift_processes],
            },
        )
    )
    if require_existing_glyph and not initial_glyph_processes:
        blockers.append("required-existing-glyph-process-missing")
    if require_no_glyph and initial_glyph_processes:
        blockers.append("true-cold-requires-glyph-not-running")
    if benchmark_mode == "true-cold" and initial_rift_processes:
        blockers.append("true-cold-requires-rift-not-running")

    if initial_rift_processes and not kill_existing_rift_first and not blockers:
        duplicate_blocker = duplicate_rift_process_blocker(initial_processes)
        if duplicate_blocker is not None:
            blockers.append(duplicate_blocker["blocker"])
            events.append(event(time.monotonic(), started_monotonic, "duplicate-rift-process-blocked-preflight", duplicate_blocker))
        else:
            rift_pids = {process.process_id for process in initial_rift_processes}
            rift_windows = [window for window in initial_observed_windows if window.process_id in rift_pids]
            rift_window = select_best_window(rift_windows, expected_title="RIFT")
            block_reason = "existing RIFT client process has no visible usable in-world window; refusing to start a new launch."
            if rift_window and rift_window.is_visible and rift_window.client_width > 0 and rift_window.client_height > 0:
                final_window = rift_window
                try:
                    image = capture_window_image(rift_window, client=True)
                    final_classification = classify_rift_client_image(image)
                    if final_classification["classification"] == "in-world-likely":
                        path = save_image(image, screenshots_dir, "existing-rift-in-world")
                        artifacts["finalScreenshot"] = repo_relative_or_absolute(repo_root, path)
                        elapsed = time.monotonic() - started_monotonic
                        existing_client = {
                            "reused": True,
                            "policy": "existing-rift-client-confirmed-in-world-no-new-launch",
                            "processes": [process.as_dict() for process in initial_rift_processes],
                            "window": rift_window.as_dict(),
                            "classification": final_classification,
                            "screenshot": artifacts["finalScreenshot"],
                        }
                        events.append(
                            event(
                                time.monotonic(),
                                started_monotonic,
                                "existing-rift-client-reused",
                                existing_client,
                            )
                        )
                        return {
                            "schemaVersion": SCHEMA_VERSION,
                            "kind": KIND,
                            "status": "passed",
                            "state": "existing-client-in-world",
                            "generatedAtUtc": utc_iso(),
                            "repoRoot": str(repo_root),
                            "input": {
                                "dryRun": dry_run,
                                "benchmarkMode": benchmark_mode,
                                "requireExistingGlyph": require_existing_glyph,
                                "killExistingRiftFirst": kill_existing_rift_first,
                                "startMethod": start_method,
                                "glyphExe": str(glyph_exe),
                                "shortcut": str(shortcut) if shortcut else None,
                                "timeoutSeconds": timeout_seconds,
                                "pollIntervalSeconds": poll_interval_seconds,
                                "launcherReadyTimeoutSeconds": launcher_ready_timeout_seconds,
                                "riftWindowTimeoutSeconds": rift_window_timeout_seconds,
                                "worldLoadTimeoutSeconds": world_load_timeout_seconds,
                                "allowFixedGlyphClickFallback": allow_fixed_glyph_click_fallback,
                            },
                            "timings": {
                                "elapsedSeconds": round(elapsed, 3),
                                "launcherStartOffsetSeconds": None,
                                "glyphPlayClickOffsetSeconds": None,
                                "riftWindowFirstSeenOffsetSeconds": round(elapsed, 3),
                                "characterPlayClickOffsetSeconds": None,
                            },
                            "events": events,
                            "lastClassification": final_classification,
                            "finalWindow": final_window.as_dict() if final_window else None,
                            "launchAttempt": None,
                            "terminatedRiftProcesses": None,
                            "blockers": [],
                            "warnings": sorted(set(warnings)),
                            "errors": errors,
                            "existingClientReused": True,
                            "existingClient": existing_client,
                            "observed": summarize_process_windows(initial_processes, initial_observed_windows),
                            "safety": safety_state(
                                dry_run=dry_run,
                                launcher_clicked=False,
                                character_clicked=False,
                                launch_attempted=False,
                                rift_processes_terminated=False,
                            ),
                            "artifacts": artifacts,
                        }
                    block_reason = (
                        "existing RIFT client is present but current screenshot classified as "
                        f"{final_classification['classification']}; refusing to start a new launch."
                    )
                except Exception as exc:  # noqa: BLE001 - fail closed with durable diagnostics.
                    warnings.append(f"existing-rift-client-classification-failed:{type(exc).__name__}:{exc}")
                    block_reason = (
                        "existing RIFT client is present but could not be classified safely; "
                        "refusing to start a new launch."
                    )
            blocker = existing_rift_new_launch_blocker(initial_processes, rift_windows, reason=block_reason)
            blockers.append(blocker["blocker"])
            events.append(
                event(
                    time.monotonic(),
                    started_monotonic,
                    "existing-rift-client-new-launch-blocked",
                    {**blocker, "classification": final_classification},
                )
            )

    if initial_rift_processes and kill_existing_rift_first and not blockers:
        terminated_rift_processes = terminate_rift_processes(initial_processes, dry_run=dry_run)
        events.append(event(time.monotonic(), started_monotonic, "existing-rift-processes-terminated", terminated_rift_processes))
        rift_processes_terminated = bool(terminated_rift_processes.get("terminated"))
        if dry_run:
            blockers.append("dry-run-no-rift-process-termination-sent")
        elif terminated_rift_processes.get("remaining"):
            blockers.append("rift-processes-remain-after-kill-existing-rift-first")
    elif (
        initial_rift_processes
        and not blockers
        and (require_existing_glyph or benchmark_mode in {"warm-glyph", "warm-glyph-after-game-kill"})
    ):
        same_account_blocker = existing_rift_same_account_launch_blocker(initial_processes)
        if same_account_blocker is not None:
            blockers.append(same_account_blocker["blocker"])
            events.append(event(time.monotonic(), started_monotonic, "same-account-launch-blocked-preflight", same_account_blocker))

    if blockers:
        elapsed = time.monotonic() - started_monotonic
        status = "blocked"
        observed_windows = (
            initial_observed_windows
            if initial_observed_windows
            else collect_windows_for_pids({process.process_id for process in initial_processes}) if os.name == "nt" else []
        )
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": KIND,
            "status": status,
            "state": "blocked-preflight",
            "generatedAtUtc": utc_iso(),
            "elapsedSeconds": round(elapsed, 3),
            "repoRoot": str(repo_root),
            "input": {
                "dryRun": dry_run,
                "benchmarkMode": benchmark_mode,
                "requireExistingGlyph": require_existing_glyph,
                "killExistingRiftFirst": kill_existing_rift_first,
                "startMethod": start_method,
                "glyphExe": str(glyph_exe),
                "shortcut": str(shortcut) if shortcut else None,
                "timeoutSeconds": timeout_seconds,
                "pollIntervalSeconds": poll_interval_seconds,
                "launcherReadyTimeoutSeconds": launcher_ready_timeout_seconds,
                "riftWindowTimeoutSeconds": rift_window_timeout_seconds,
                "worldLoadTimeoutSeconds": world_load_timeout_seconds,
                "allowFixedGlyphClickFallback": allow_fixed_glyph_click_fallback,
            },
            "timings": {
                "elapsedSeconds": round(elapsed, 3),
                "launcherStartOffsetSeconds": None,
                "glyphPlayClickOffsetSeconds": None,
                "riftWindowFirstSeenOffsetSeconds": None,
                "characterPlayClickOffsetSeconds": None,
            },
            "blockers": blockers,
            "warnings": warnings,
            "errors": errors,
            "events": events,
            "lastClassification": final_classification,
            "finalWindow": final_window.as_dict() if final_window else None,
            "existingClientReused": False,
            "existingClient": existing_client,
            "observed": summarize_process_windows(initial_processes, observed_windows),
            "safety": safety_state(
                dry_run=dry_run,
                launcher_clicked=False,
                character_clicked=False,
                launch_attempted=False,
                rift_processes_terminated=rift_processes_terminated,
            ),
            "terminatedRiftProcesses": terminated_rift_processes,
            "artifacts": artifacts,
        }

    deadline = started_monotonic + timeout_seconds
    while time.monotonic() < deadline:
        now = time.monotonic()
        try:
            processes = collect_processes({GLYPH_PROCESS, RIFT_PROCESS})
            duplicate_blocker = duplicate_rift_process_blocker(processes)
            if duplicate_blocker is not None:
                blockers.append(duplicate_blocker["blocker"])
                events.append(event(now, started_monotonic, "duplicate-rift-process-blocked", duplicate_blocker))
                state = "blocked"
                break
            glyph_pids = {process.process_id for process in processes if process.name.casefold() == GLYPH_PROCESS.casefold()}
            rift_pids = {process.process_id for process in processes if process.name.casefold() == RIFT_PROCESS.casefold()}
            windows = collect_windows_for_pids(glyph_pids | rift_pids)
            glyph_windows = [window for window in windows if window.process_id in glyph_pids]
            rift_windows = [window for window in windows if window.process_id in rift_pids]
            rift_window = select_best_window(rift_windows, expected_title="RIFT")

            if rift_window and rift_window.is_visible and rift_window.client_width > 0 and rift_window.client_height > 0:
                if rift_first_seen_at is None:
                    rift_first_seen_at = now
                    events.append(event(now, started_monotonic, "rift-window-visible", rift_window.as_dict()))
                final_window = rift_window
                focus_detail = focus_window(rift_window)
                refreshed_rift_window = select_best_window(
                    collect_windows_for_pids({rift_window.process_id}),
                    expected_title="RIFT",
                )
                if refreshed_rift_window is not None:
                    rift_window = refreshed_rift_window
                    final_window = rift_window
                image = capture_window_image(rift_window, client=True)
                classification = classify_rift_client_image(image)
                final_classification = classification
                if classification["classification"] == "in-world-likely":
                    path = save_image(image, screenshots_dir, "rift-in-world")
                    artifacts["finalScreenshot"] = repo_relative_or_absolute(repo_root, path)
                    events.append(
                        event(
                            time.monotonic(),
                            started_monotonic,
                            "in-world-detected",
                            {
                                "window": rift_window.as_dict(),
                                "focus": focus_detail,
                                "classification": classification,
                                "screenshot": artifacts["finalScreenshot"],
                            },
                        )
                    )
                    state = "in-world"
                    break
                if classification["classification"] == "modal-dialog-blocker":
                    path = save_image(image, screenshots_dir, "rift-modal-dialog-blocker")
                    artifacts["blockerScreenshot"] = repo_relative_or_absolute(repo_root, path)
                    blockers.append("rift-modal-dialog-visible-during-launch")
                    events.append(
                        event(
                            time.monotonic(),
                            started_monotonic,
                            "rift-modal-dialog-blocker",
                            {
                                "window": rift_window.as_dict(),
                                "focus": focus_detail,
                                "classification": classification,
                                "screenshot": artifacts["blockerScreenshot"],
                            },
                        )
                    )
                    state = "blocked"
                    break
                if classification["classification"] == "character-select":
                    path = save_image(image, screenshots_dir, "rift-character-select")
                    artifacts.setdefault("characterSelectScreenshot", repo_relative_or_absolute(repo_root, path))
                    if character_clicked:
                        if character_clicked_at and now - character_clicked_at > world_load_timeout_seconds:
                            blockers.append("world-load-timeout-after-character-play")
                            state = "blocked"
                            break
                    else:
                        scaled_point = scale_client_point(
                            DEFAULT_CHAR_PLAY_POINT,
                            width=rift_window.client_width,
                            height=rift_window.client_height,
                        )
                        detail = {
                            "window": rift_window.as_dict(),
                            "focus": focus_detail,
                            "classification": classification,
                            "clientPoint": scaled_point,
                            "screenshot": artifacts.get("characterSelectScreenshot"),
                        }
                        if dry_run:
                            events.append(event(now, started_monotonic, "dry-run-would-click-character-play", detail))
                            blockers.append("dry-run-no-world-entry-click-sent")
                            state = "blocked"
                            break
                        click_detail = click_window_point(rift_window, scaled_point, client=True)
                        character_clicked = True
                        character_clicked_at = time.monotonic()
                        events.append(event(character_clicked_at, started_monotonic, "character-play-clicked", {**detail, "click": click_detail}))
                        time.sleep(max(0.2, poll_interval_seconds))
                        continue
                else:
                    if character_clicked_at and now - character_clicked_at > world_load_timeout_seconds:
                        blockers.append(f"world-not-detected-after-character-play:{classification['classification']}")
                        state = "blocked"
                        break
                    events.append(
                        event(
                            now,
                            started_monotonic,
                            "rift-visible-not-ready",
                            {"classification": classification, "window": rift_window.as_dict()},
                        )
                    )
                    time.sleep(poll_interval_seconds)
                    continue

            glyph_window = select_best_window(glyph_windows, expected_title="Glyph")
            if glyph_window and glyph_window.is_visible and glyph_window.window_rect.get("width", 0) > 0:
                if launch_attempted and launcher_started_at and not launcher_clicked and now - launcher_started_at > launcher_ready_timeout_seconds:
                    blockers.append("launcher-ready-timeout-before-play-button")
                    state = "blocked"
                    break
                focus_detail = focus_window(glyph_window)
                refreshed_glyph_window = select_best_window(
                    collect_windows_for_pids({glyph_window.process_id}),
                    expected_title="Glyph",
                )
                if refreshed_glyph_window is not None:
                    glyph_window = refreshed_glyph_window
                image = capture_window_image(glyph_window, client=False)
                play = find_glyph_play_button(image)
                if not play["found"] and allow_fixed_glyph_click_fallback:
                    play = {
                        **play,
                        "found": True,
                        "fallbackUsed": True,
                        "centerWindowPoint": [
                            round(DEFAULT_GLYPH_PLAY_POINT[0] * glyph_window.window_rect["width"] / 1160),
                            round(DEFAULT_GLYPH_PLAY_POINT[1] * glyph_window.window_rect["height"] / 730),
                        ],
                    }
                    warnings.append("used-fixed-glyph-play-click-fallback")
                path = save_image(image, screenshots_dir, "glyph-visible")
                artifacts.setdefault("glyphScreenshot", repo_relative_or_absolute(repo_root, path))
                if not play["found"]:
                    if launch_attempted or glyph_pids:
                        events.append(event(now, started_monotonic, "glyph-visible-play-not-found", {"window": glyph_window.as_dict(), "play": play}))
                    time.sleep(poll_interval_seconds)
                    continue
                if launcher_clicked:
                    if launcher_clicked_at and now - launcher_clicked_at > rift_window_timeout_seconds:
                        blockers.append("rift-window-timeout-after-glyph-play")
                        state = "blocked"
                        break
                    time.sleep(poll_interval_seconds)
                    continue
                detail = {
                    "window": glyph_window.as_dict(),
                    "focus": focus_detail,
                    "playButton": play,
                    "screenshot": artifacts.get("glyphScreenshot"),
                }
                same_account_blocker = existing_rift_same_account_launch_blocker(
                    collect_processes({GLYPH_PROCESS, RIFT_PROCESS})
                )
                if same_account_blocker is not None:
                    blockers.append(same_account_blocker["blocker"])
                    events.append(event(time.monotonic(), started_monotonic, "same-account-launch-blocked-before-glyph-play", same_account_blocker))
                    state = "blocked"
                    break
                if dry_run:
                    events.append(event(now, started_monotonic, "dry-run-would-click-glyph-play", detail))
                    blockers.append("dry-run-no-launcher-click-sent")
                    state = "blocked"
                    break
                click_detail = click_window_point(glyph_window, list(play["centerWindowPoint"]), client=False)
                launcher_clicked = True
                launcher_clicked_at = time.monotonic()
                events.append(event(launcher_clicked_at, started_monotonic, "glyph-play-clicked", {**detail, "click": click_detail}))
                time.sleep(max(0.2, poll_interval_seconds))
                continue

            if not launch_attempted:
                launch_attempted = True
                launcher_started_at = time.monotonic()
                launch_attempt = start_launcher(
                    glyph_exe=glyph_exe,
                    shortcut=shortcut,
                    method=start_method,
                    output_dir=output_root,
                    dry_run=dry_run,
                )
                events.append(event(launcher_started_at, started_monotonic, "launcher-start-requested", launch_attempt))
                if dry_run:
                    blockers.append("dry-run-no-launch-attempt-sent")
                    state = "blocked"
                    break
                if not launch_attempt.get("started"):
                    errors.append({"type": "LauncherStartFailed", "stage": "start-launcher", "detail": launch_attempt})
                    state = "failed"
                    break
                time.sleep(max(0.4, poll_interval_seconds))
                continue

            if launcher_started_at and not glyph_windows and not rift_windows and now - launcher_started_at > launcher_ready_timeout_seconds:
                blockers.append("launcher-window-timeout-after-start")
                state = "blocked"
                break
            state = "waiting"
            time.sleep(poll_interval_seconds)
        except Exception as exc:  # noqa: BLE001 - preserve durable diagnostics.
            errors.append({"type": type(exc).__name__, "message": str(exc), "stage": state})
            state = "failed"
            break
    else:
        blockers.append("overall-fast-world-launch-timeout")
        state = "blocked"

    elapsed = time.monotonic() - started_monotonic
    timings = {
        "elapsedSeconds": round(elapsed, 3),
        "launcherStartOffsetSeconds": round(launcher_started_at - started_monotonic, 3) if launcher_started_at else None,
        "glyphPlayClickOffsetSeconds": round(launcher_clicked_at - started_monotonic, 3) if launcher_clicked_at else None,
        "riftWindowFirstSeenOffsetSeconds": round(rift_first_seen_at - started_monotonic, 3) if rift_first_seen_at else None,
        "characterPlayClickOffsetSeconds": round(character_clicked_at - started_monotonic, 3) if character_clicked_at else None,
    }
    status = "failed" if errors else "passed" if state == "in-world" else "blocked"
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "status": status,
        "state": state,
        "generatedAtUtc": utc_iso(),
        "repoRoot": str(repo_root),
        "input": {
            "dryRun": dry_run,
            "benchmarkMode": benchmark_mode,
            "requireExistingGlyph": require_existing_glyph,
            "killExistingRiftFirst": kill_existing_rift_first,
            "startMethod": start_method,
            "glyphExe": str(glyph_exe),
            "shortcut": str(shortcut) if shortcut else None,
            "timeoutSeconds": timeout_seconds,
            "pollIntervalSeconds": poll_interval_seconds,
            "launcherReadyTimeoutSeconds": launcher_ready_timeout_seconds,
            "riftWindowTimeoutSeconds": rift_window_timeout_seconds,
            "worldLoadTimeoutSeconds": world_load_timeout_seconds,
            "allowFixedGlyphClickFallback": allow_fixed_glyph_click_fallback,
        },
        "timings": timings,
        "events": events,
        "lastClassification": final_classification,
        "finalWindow": final_window.as_dict() if final_window else None,
        "launchAttempt": launch_attempt,
        "terminatedRiftProcesses": terminated_rift_processes,
        "blockers": blockers,
        "warnings": sorted(set(warnings)),
        "errors": errors,
        "existingClientReused": False,
        "existingClient": existing_client,
        "safety": safety_state(
            dry_run=dry_run,
            launcher_clicked=launcher_clicked,
            character_clicked=character_clicked,
            launch_attempted=launch_attempted,
            rift_processes_terminated=rift_processes_terminated,
        ),
        "artifacts": artifacts,
    }
    try:
        processes = collect_processes({GLYPH_PROCESS, RIFT_PROCESS})
        pids = {process.process_id for process in processes}
        windows = collect_windows_for_pids(pids)
        summary["observed"] = summarize_process_windows(processes, windows)
    except Exception as exc:  # noqa: BLE001
        summary.setdefault("warnings", []).append(f"final-process-window-snapshot-failed:{type(exc).__name__}:{exc}")
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    safety = summary.get("safety") or {}
    timings = summary.get("timings") or {}
    inputs = summary.get("input") or {}
    lines = [
        "# RiftReader fast world launch",
        "",
        "## Verdict",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- State: `{summary.get('state')}`",
        f"- Benchmark mode: `{inputs.get('benchmarkMode')}`",
        f"- Elapsed: `{timings.get('elapsedSeconds')}` seconds",
        f"- Dry run: `{safety.get('dryRun')}`",
        f"- Existing client reused: `{summary.get('existingClientReused')}`",
        f"- RIFT processes terminated: `{safety.get('processTerminated')}`",
        f"- Launcher click sent: `{safety.get('launcherButtonPressed')}`",
        f"- Character PLAY click sent: `{safety.get('characterPlayPressed')}`",
        f"- Movement sent: `{safety.get('movementSent')}`",
        "",
        "## Phase timings",
        "",
        "| Phase | Offset seconds |",
        "|---|---:|",
        f"| Launcher start requested | `{timings.get('launcherStartOffsetSeconds')}` |",
        f"| Glyph PLAY clicked | `{timings.get('glyphPlayClickOffsetSeconds')}` |",
        f"| RIFT window first visible | `{timings.get('riftWindowFirstSeenOffsetSeconds')}` |",
        f"| Character PLAY clicked | `{timings.get('characterPlayClickOffsetSeconds')}` |",
        f"| In-world detected / final elapsed | `{timings.get('elapsedSeconds')}` |",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- `{item}`" for item in summary.get("blockers") or []] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{item}`" for item in summary.get("warnings") or []] or ["- none"])
    artifacts = summary.get("artifacts") or {}
    lines.extend(["", "## Artifacts", ""])
    for key, value in artifacts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Safety", ""])
    lines.append("This helper does not send movement keys, hotbar/chat input, reloadui, native screenshots, CE, x64dbg, provider writes, or Git mutations. It terminates only `rift_x64.exe` when `--kill-existing-rift-first` or `warm-glyph-after-game-kill` mode is explicitly selected.")
    return "\n".join(lines)


def render_compact(summary: dict[str, Any]) -> str:
    timings = summary.get("timings") or {}
    safety = summary.get("safety") or {}
    inputs = summary.get("input") or {}
    observed = summary.get("observed") if isinstance(summary.get("observed"), dict) else {}
    processes = observed.get("processes") if isinstance(observed.get("processes"), dict) else {}
    rift_count = len(processes.get(RIFT_PROCESS, []) or [])
    glyph_count = len(processes.get(GLYPH_PROCESS, []) or [])
    lines = [
        "# RiftReader fast world launch",
        "",
        f"Result: `{summary.get('status')}` / `{summary.get('state')}`",
        "",
        "| Field | Value |",
        "|---|---:|",
        f"| Mode | `{inputs.get('benchmarkMode')}` |",
        f"| Elapsed seconds | `{timings.get('elapsedSeconds')}` |",
        f"| Glyph PLAY offset | `{timings.get('glyphPlayClickOffsetSeconds')}` |",
        f"| RIFT window offset | `{timings.get('riftWindowFirstSeenOffsetSeconds')}` |",
        f"| Character PLAY offset | `{timings.get('characterPlayClickOffsetSeconds')}` |",
        f"| Final RIFT process count | `{rift_count}` |",
        f"| Final Glyph process count | `{glyph_count}` |",
        f"| Existing client reused | `{summary.get('existingClientReused')}` |",
        f"| Killed existing RIFT first | `{safety.get('processTerminated')}` |",
        f"| Movement sent | `{safety.get('movementSent')}` |",
        "",
        "Blockers: " + (", ".join(f"`{item}`" for item in summary.get("blockers") or []) or "`none`"),
        "Warnings: " + (", ".join(f"`{item}`" for item in summary.get("warnings") or []) or "`none`"),
        "",
        f"Summary JSON: `{(summary.get('artifacts') or {}).get('summaryJson')}`",
        f"Summary Markdown: `{(summary.get('artifacts') or {}).get('summaryMarkdown')}`",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fast scripted Glyph/RIFT launch-to-world helper.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--live", action="store_true", help="Actually launch/click. Without this flag the run is a dry-run.")
    parser.add_argument("--benchmark-mode", choices=BENCHMARK_MODES, default="auto")
    parser.add_argument("--require-existing-glyph", action="store_true")
    parser.add_argument("--kill-existing-rift-first", action="store_true")
    parser.add_argument("--start-method", choices=["wscript", "shortcut", "direct"], default="wscript")
    parser.add_argument("--glyph-exe", type=Path, default=DEFAULT_GLYPH_EXE)
    parser.add_argument("--shortcut", type=Path, default=DEFAULT_RIFT_SHORTCUT)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--poll-interval-seconds", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS)
    parser.add_argument("--launcher-ready-timeout-seconds", type=float, default=DEFAULT_LAUNCHER_READY_TIMEOUT_SECONDS)
    parser.add_argument("--rift-window-timeout-seconds", type=float, default=DEFAULT_RIFT_WINDOW_TIMEOUT_SECONDS)
    parser.add_argument("--world-load-timeout-seconds", type=float, default=DEFAULT_WORLD_LOAD_TIMEOUT_SECONDS)
    parser.add_argument("--allow-fixed-glyph-click-fallback", action="store_true")
    parser.add_argument("--output-format", choices=["compact", "markdown", "json"], default="compact")
    parser.add_argument("--json", action="store_true", help="Print JSON summary instead of compact output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else (repo_root / DEFAULT_OUTPUT_ROOT / f"run-{utc_stamp()}").resolve()
    )
    summary = build_summary(
        repo_root=repo_root,
        output_root=output_root,
        dry_run=not bool(args.live),
        benchmark_mode=args.benchmark_mode,
        require_existing_glyph=bool(args.require_existing_glyph),
        kill_existing_rift_first=bool(args.kill_existing_rift_first),
        start_method=args.start_method,
        glyph_exe=args.glyph_exe.resolve(),
        shortcut=args.shortcut.resolve() if args.shortcut else None,
        timeout_seconds=max(1.0, args.timeout_seconds),
        poll_interval_seconds=max(0.05, args.poll_interval_seconds),
        launcher_ready_timeout_seconds=max(1.0, args.launcher_ready_timeout_seconds),
        rift_window_timeout_seconds=max(1.0, args.rift_window_timeout_seconds),
        world_load_timeout_seconds=max(1.0, args.world_load_timeout_seconds),
        allow_fixed_glyph_click_fallback=bool(args.allow_fixed_glyph_click_fallback),
    )
    summary_json = output_root / "fast-world-launch-summary.json"
    summary_markdown = output_root / "FAST_WORLD_LAUNCH.md"
    latest = repo_root / DEFAULT_OUTPUT_ROOT / "latest-run.txt"
    summary.setdefault("artifacts", {})["summaryJson"] = repo_relative_or_absolute(repo_root, summary_json)
    summary.setdefault("artifacts", {})["summaryMarkdown"] = repo_relative_or_absolute(repo_root, summary_markdown)
    summary.setdefault("artifacts", {})["latestRun"] = repo_relative_or_absolute(repo_root, latest)
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary) + "\n")
    write_text_atomic(latest, str(output_root.resolve()) + "\n")
    output_format = "json" if args.json else args.output_format
    if output_format == "json":
        print(json.dumps(summary, indent=2))
    elif output_format == "markdown":
        print(render_markdown(summary))
    else:
        print(render_compact(summary))
    if summary.get("status") == "passed":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
