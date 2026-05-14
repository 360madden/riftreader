# Version: riftreader-target-control-v0.1.2
# Total-Character-Count: 27091
# Purpose: No-input RiftReader target-control preflight. Resolves the RIFT target, restores/requests foreground, classifies exact-HWND versus same-PID foreground state, and writes readiness artifacts.

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_CONTROL_PASSED = "passed-target-control"
TARGET_CONTROL_BLOCKED = "blocked-target-control"

EXACT_HWND_FOREGROUND = "exact-hwnd-foreground"
SAME_PID_DIFFERENT_HWND_FOREGROUND = "same-pid-different-hwnd-foreground"
TARGET_VISIBLE_NOT_FOREGROUND = "target-visible-not-foreground"
DIFFERENT_PROCESS_FOREGROUND = "different-process-foreground"
TARGET_PROCESS_MISSING = "target-process-missing"
TARGET_WINDOW_MISSING = "target-window-missing"
TARGET_WINDOW_MINIMIZED = "target-window-minimized"
FOREGROUND_NOT_ACQUIRED = "foreground-not-acquired"
UNSUPPORTED_NON_WINDOWS = "unsupported-non-windows"

DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"
DEFAULT_RETRIES = 5
DEFAULT_SETTLE_MS = 400
SW_RESTORE = 9

if os.name == "nt":
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
else:
    WNDENUMPROC = None  # type: ignore[assignment]


@dataclass(frozen=True)
class TargetControlOptions:
    repo_root: Path
    process_id: int | None = None
    window_handle: str | None = None
    process_name: str = DEFAULT_PROCESS_NAME
    title_contains: str = DEFAULT_TITLE_CONTAINS
    output_dir: Path | None = None
    retries: int = DEFAULT_RETRIES
    settle_ms: int = DEFAULT_SETTLE_MS
    strong_assist: bool = True


@dataclass(frozen=True)
class WindowSnapshot:
    hwnd: int
    hwnd_hex: str
    process_id: int
    process_name: str | None
    title: str
    is_window: bool
    is_visible: bool
    is_minimized: bool


@dataclass(frozen=True)
class ForegroundSnapshot:
    hwnd: int
    hwnd_hex: str | None
    process_id: int | None
    process_name: str | None
    title: str | None


@dataclass(frozen=True)
class ForegroundClassification:
    classification: str
    status: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_hwnd(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        return None

    if text.lower().startswith("0x"):
        return int(text[2:], 16)

    return int(text, 10)


def hwnd_to_int(value: Any) -> int:
    """Convert Win32 HWND values from ctypes callbacks/restypes without int(c_void_p)."""
    if value is None:
        return 0
    raw_value = getattr(value, "value", value)
    if raw_value is None:
        return 0
    return int(raw_value)


def _require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("RiftReader target-control live preflight requires Windows.")


def _load_user32() -> Any:
    _require_windows()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    return user32


def _load_kernel32() -> Any:
    _require_windows()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
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
    return kernel32


def process_name_from_pid(pid: int) -> str | None:
    if os.name != "nt" or pid <= 0:
        return None

    kernel32 = _load_kernel32()
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return None

    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return Path(buffer.value).stem
    finally:
        kernel32.CloseHandle(handle)


def get_window_pid(user32: Any, hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value)


def get_window_thread_id(user32: Any, hwnd: int) -> int:
    pid = wintypes.DWORD()
    thread_id = user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return int(thread_id)


def get_window_title(user32: Any, hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(wintypes.HWND(hwnd))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, length + 1)
    return buffer.value


def get_window_snapshot(user32: Any, hwnd: int) -> WindowSnapshot | None:
    if hwnd <= 0 or not user32.IsWindow(wintypes.HWND(hwnd)):
        return None

    pid = get_window_pid(user32, hwnd)
    return WindowSnapshot(
        hwnd=hwnd,
        hwnd_hex=f"0x{hwnd:X}",
        process_id=pid,
        process_name=process_name_from_pid(pid),
        title=get_window_title(user32, hwnd),
        is_window=True,
        is_visible=bool(user32.IsWindowVisible(wintypes.HWND(hwnd))),
        is_minimized=bool(user32.IsIconic(wintypes.HWND(hwnd))),
    )


def get_foreground_snapshot(user32: Any) -> ForegroundSnapshot:
    hwnd = hwnd_to_int(user32.GetForegroundWindow())
    if hwnd <= 0 or not user32.IsWindow(wintypes.HWND(hwnd)):
        return ForegroundSnapshot(hwnd=0, hwnd_hex=None, process_id=None, process_name=None, title=None)

    pid = get_window_pid(user32, hwnd)
    return ForegroundSnapshot(
        hwnd=hwnd,
        hwnd_hex=f"0x{hwnd:X}",
        process_id=pid,
        process_name=process_name_from_pid(pid),
        title=get_window_title(user32, hwnd),
    )


def enumerate_windows_for_pid(user32: Any, pid: int) -> list[WindowSnapshot]:
    windows: list[WindowSnapshot] = []

    @WNDENUMPROC  # type: ignore[misc]
    def enum_proc(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        hwnd_int = hwnd_to_int(hwnd)
        if get_window_pid(user32, hwnd_int) != pid:
            return True
        snapshot = get_window_snapshot(user32, hwnd_int)
        if snapshot is not None:
            windows.append(snapshot)
        return True

    user32.EnumWindows(enum_proc, 0)
    return windows


def enumerate_top_level_windows(user32: Any) -> list[WindowSnapshot]:
    windows: list[WindowSnapshot] = []

    @WNDENUMPROC  # type: ignore[misc]
    def enum_proc(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        snapshot = get_window_snapshot(user32, hwnd_to_int(hwnd))
        if snapshot is not None:
            windows.append(snapshot)
        return True

    user32.EnumWindows(enum_proc, 0)
    return windows


def select_target_window_from_candidates(
    windows: list[WindowSnapshot],
    options: TargetControlOptions,
) -> WindowSnapshot | None:
    candidates = [
        window
        for window in windows
        if window.is_visible
        and _title_matches(window.title, options.title_contains)
        and (
            not options.process_name
            or not window.process_name
            or _process_matches(window.process_name, options.process_name)
        )
    ]

    if not candidates:
        return None

    titled = [window for window in candidates if window.title.strip()]
    return titled[0] if titled else candidates[0]


def resolve_target_window(options: TargetControlOptions, user32: Any) -> tuple[WindowSnapshot | None, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    requested_hwnd = parse_hwnd(options.window_handle)

    if requested_hwnd is not None:
        snapshot = get_window_snapshot(user32, requested_hwnd)
        if snapshot is None:
            return None, [TARGET_WINDOW_MISSING], warnings
        _validate_snapshot_expectations(snapshot, options, blockers, warnings)
        return snapshot, blockers, warnings

    if options.process_id is not None:
        if process_name_from_pid(options.process_id) is None:
            return None, [TARGET_PROCESS_MISSING], warnings

        windows = enumerate_windows_for_pid(user32, options.process_id)
        target = select_target_window_from_candidates(windows, options)
        if target is None:
            return None, [TARGET_WINDOW_MISSING], warnings

        _validate_snapshot_expectations(target, options, blockers, warnings)
        return target, blockers, warnings

    target = select_target_window_from_candidates(enumerate_top_level_windows(user32), options)
    if target is None:
        return None, [TARGET_WINDOW_MISSING], warnings

    _validate_snapshot_expectations(target, options, blockers, warnings)
    return target, blockers, warnings


def _validate_snapshot_expectations(
    snapshot: WindowSnapshot,
    options: TargetControlOptions,
    blockers: list[str],
    warnings: list[str],
) -> None:
    if options.process_id is not None and snapshot.process_id != options.process_id:
        blockers.append("target-process-id-mismatch")

    if options.process_name and snapshot.process_name:
        if not _process_matches(snapshot.process_name, options.process_name):
            blockers.append("target-process-name-mismatch")
    elif options.process_name and not snapshot.process_name:
        warnings.append("target-process-name-could-not-be-queried")

    if options.title_contains and not _title_matches(snapshot.title, options.title_contains):
        blockers.append("target-title-mismatch")

    if not snapshot.is_visible:
        blockers.append("target-window-not-visible")

    if snapshot.is_minimized:
        warnings.append(TARGET_WINDOW_MINIMIZED)


def _process_matches(actual: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    if not actual:
        return False

    actual_normalized = actual.lower()
    expected_normalized = expected.lower()

    if actual_normalized.endswith(".exe"):
        actual_normalized = actual_normalized[:-4]
    if expected_normalized.endswith(".exe"):
        expected_normalized = expected_normalized[:-4]

    return actual_normalized == expected_normalized


def _title_matches(actual: str, expected_contains: str | None) -> bool:
    if not expected_contains:
        return True
    return expected_contains.lower() in actual.lower()


def request_foreground(
    user32: Any,
    target: WindowSnapshot,
    *,
    retries: int,
    settle_ms: int,
    strong_assist: bool,
) -> tuple[list[dict[str, Any]], ForegroundSnapshot]:
    attempts: list[dict[str, Any]] = []
    hwnd_value = wintypes.HWND(target.hwnd)

    for attempt_number in range(1, max(1, retries) + 1):
        before = get_foreground_snapshot(user32)
        restore_ok = bool(user32.ShowWindow(hwnd_value, SW_RESTORE))
        set_foreground_ok = bool(user32.SetForegroundWindow(hwnd_value))
        time.sleep(max(0, settle_ms) / 1000.0)
        after = get_foreground_snapshot(user32)

        attempts.append(
            _attempt_record(
                tier="tier1-showwindow-setforegroundwindow",
                attempt=attempt_number,
                before=before,
                after=after,
                restore_ok=restore_ok,
                set_foreground_ok=set_foreground_ok,
                bring_to_top_ok=None,
                attach_thread_input_used=False,
            )
        )

        if after.hwnd == target.hwnd:
            return attempts, after

    if strong_assist:
        for attempt_number in range(1, 3):
            before = get_foreground_snapshot(user32)
            result = _request_foreground_with_attach_thread_input(user32, target.hwnd, settle_ms)
            after = get_foreground_snapshot(user32)

            attempts.append(
                _attempt_record(
                    tier="tier2-attachthreadinput-bringwindowtotop",
                    attempt=attempt_number,
                    before=before,
                    after=after,
                    restore_ok=result.get("restoreOk"),
                    set_foreground_ok=result.get("setForegroundOk"),
                    bring_to_top_ok=result.get("bringToTopOk"),
                    attach_thread_input_used=True,
                    attach_thread_input_ok=result.get("attachThreadInputOk"),
                    errors=result.get("errors"),
                )
            )

            if after.hwnd == target.hwnd:
                return attempts, after

    return attempts, get_foreground_snapshot(user32)


def _request_foreground_with_attach_thread_input(user32: Any, hwnd: int, settle_ms: int) -> dict[str, Any]:
    kernel32 = _load_kernel32()
    errors: list[str] = []
    hwnd_value = wintypes.HWND(hwnd)
    current_thread = int(kernel32.GetCurrentThreadId())

    foreground = get_foreground_snapshot(user32)
    foreground_thread = get_window_thread_id(user32, foreground.hwnd) if foreground.hwnd else 0
    target_thread = get_window_thread_id(user32, hwnd)

    attached_threads: list[int] = []

    try:
        for thread_id in (foreground_thread, target_thread):
            if thread_id and thread_id != current_thread:
                ok = bool(user32.AttachThreadInput(current_thread, thread_id, True))
                if ok:
                    attached_threads.append(thread_id)
                else:
                    errors.append(f"AttachThreadInput failed for thread {thread_id}")

        restore_ok = bool(user32.ShowWindow(hwnd_value, SW_RESTORE))
        bring_to_top_ok = bool(user32.BringWindowToTop(hwnd_value))
        set_foreground_ok = bool(user32.SetForegroundWindow(hwnd_value))
        time.sleep(max(0, settle_ms) / 1000.0)

        return {
            "restoreOk": restore_ok,
            "bringToTopOk": bring_to_top_ok,
            "setForegroundOk": set_foreground_ok,
            "attachThreadInputOk": not errors,
            "errors": errors,
        }
    finally:
        for thread_id in reversed(attached_threads):
            user32.AttachThreadInput(current_thread, thread_id, False)


def _attempt_record(
    *,
    tier: str,
    attempt: int,
    before: ForegroundSnapshot,
    after: ForegroundSnapshot,
    restore_ok: bool | None,
    set_foreground_ok: bool | None,
    bring_to_top_ok: bool | None,
    attach_thread_input_used: bool,
    attach_thread_input_ok: bool | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "tier": tier,
        "attempt": attempt,
        "restoreOk": restore_ok,
        "setForegroundOk": set_foreground_ok,
        "bringToTopOk": bring_to_top_ok,
        "attachThreadInputUsed": attach_thread_input_used,
        "attachThreadInputOk": attach_thread_input_ok,
        "before": foreground_to_dict(before),
        "after": foreground_to_dict(after),
        "errors": errors or [],
    }


def classify_foreground(
    target: WindowSnapshot | None,
    foreground: ForegroundSnapshot | None,
    existing_blockers: list[str] | None = None,
    existing_warnings: list[str] | None = None,
) -> ForegroundClassification:
    blockers = list(existing_blockers or [])
    warnings = list(existing_warnings or [])

    if target is None:
        _append_once(blockers, TARGET_WINDOW_MISSING)
        return ForegroundClassification(TARGET_WINDOW_MISSING, TARGET_CONTROL_BLOCKED, tuple(blockers), tuple(warnings))

    if target.is_minimized:
        _append_once(blockers, TARGET_WINDOW_MINIMIZED)

    if not target.is_visible:
        _append_once(blockers, "target-window-not-visible")

    if foreground is None or foreground.hwnd <= 0:
        _append_once(blockers, FOREGROUND_NOT_ACQUIRED)
        return ForegroundClassification(FOREGROUND_NOT_ACQUIRED, TARGET_CONTROL_BLOCKED, tuple(blockers), tuple(warnings))

    if foreground.hwnd == target.hwnd:
        status = TARGET_CONTROL_BLOCKED if blockers else TARGET_CONTROL_PASSED
        return ForegroundClassification(EXACT_HWND_FOREGROUND, status, tuple(blockers), tuple(warnings))

    if foreground.process_id == target.process_id:
        _append_once(warnings, "foreground-window-belongs-to-same-process-but-not-requested-hwnd")
        status = TARGET_CONTROL_BLOCKED if blockers else TARGET_CONTROL_PASSED
        return ForegroundClassification(SAME_PID_DIFFERENT_HWND_FOREGROUND, status, tuple(blockers), tuple(warnings))

    _append_once(blockers, DIFFERENT_PROCESS_FOREGROUND)
    return ForegroundClassification(DIFFERENT_PROCESS_FOREGROUND, TARGET_CONTROL_BLOCKED, tuple(blockers), tuple(warnings))


def build_capabilities(target: WindowSnapshot | None, classification: str, blockers: list[str]) -> dict[str, bool]:
    critical_identity_blockers = {
        TARGET_WINDOW_MISSING,
        "target-process-id-mismatch",
        "target-process-name-mismatch",
        "target-title-mismatch",
    }

    identity_ok = target is not None and not any(blocker in critical_identity_blockers for blocker in blockers)
    target_visible_ok = identity_ok and target is not None and target.is_visible and not target.is_minimized
    exact = classification == EXACT_HWND_FOREGROUND
    same_pid = classification == SAME_PID_DIFFERENT_HWND_FOREGROUND

    return {
        "readOnlyProof": identity_ok,
        "visualCapture": target_visible_ok and exact,
        "exactHwndInput": target_visible_ok and classification in {EXACT_HWND_FOREGROUND, SAME_PID_DIFFERENT_HWND_FOREGROUND},
        "foregroundSendInput": target_visible_ok and exact,
        "yawStimulus": False,
        "autoTurn": False,
        "samePidForegroundDiagnostic": same_pid,
    }


def run_target_control(options: TargetControlOptions) -> dict[str, Any]:
    repo_root = options.repo_root.resolve()
    output_dir = (options.output_dir or default_output_dir(repo_root, options.process_id)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if os.name != "nt":
        summary = _blocked_summary(repo_root, output_dir, options, UNSUPPORTED_NON_WINDOWS, [UNSUPPORTED_NON_WINDOWS])
        write_artifacts(summary, output_dir)
        return summary

    user32 = _load_user32()
    attempted_at = utc_now()
    target, blockers, warnings = resolve_target_window(options, user32)
    attempts: list[dict[str, Any]] = []

    if target is not None and not blockers:
        attempts, foreground = request_foreground(
            user32,
            target,
            retries=options.retries,
            settle_ms=options.settle_ms,
            strong_assist=options.strong_assist,
        )
    else:
        foreground = get_foreground_snapshot(user32)

    classification = classify_foreground(target, foreground, blockers, warnings)
    blockers = list(classification.blockers)
    warnings = list(classification.warnings)
    capabilities = build_capabilities(target, classification.classification, blockers)

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "status": classification.status,
        "classification": classification.classification,
        "ok": classification.status == TARGET_CONTROL_PASSED,
        "readyForReadOnlyProof": capabilities["readOnlyProof"],
        "readyForVisualGate": capabilities["visualCapture"],
        "readyForLiveInput": capabilities["foregroundSendInput"],
        "movementSent": False,
        "inputSent": False,
        "screenshotKeySent": False,
        "reloaduiSent": False,
        "noCheatEngine": True,
        "attemptedAtUtc": attempted_at,
        "completedAtUtc": utc_now(),
        "repoRoot": str(repo_root),
        "outputDir": str(output_dir),
        "target": {
            "processName": options.process_name,
            "processId": options.process_id,
            "requestedWindowHandle": options.window_handle,
            "titleContains": options.title_contains,
        },
        "window": window_to_dict(target),
        "foreground": foreground_to_dict(foreground),
        "attempts": attempts,
        "blockers": blockers,
        "warnings": warnings,
        "capabilities": capabilities,
        "policyNotes": [
            "Target-control is a preflight only; it does not authorize movement by itself.",
            "Yaw stimulus and auto-turn remain false until visual gate, fresh ProofOnly, and current-session actor-facing truth are satisfied.",
            "Same-PID different-HWND foreground is classified separately and must be accepted explicitly by downstream policy.",
        ],
    }

    summary["summaryPath"] = str(output_dir / "target-control-status.json")
    write_artifacts(summary, output_dir)
    return summary


def _blocked_summary(
    repo_root: Path,
    output_dir: Path,
    options: TargetControlOptions,
    classification: str,
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "status": TARGET_CONTROL_BLOCKED,
        "classification": classification,
        "ok": False,
        "readyForReadOnlyProof": False,
        "readyForVisualGate": False,
        "readyForLiveInput": False,
        "movementSent": False,
        "inputSent": False,
        "screenshotKeySent": False,
        "reloaduiSent": False,
        "noCheatEngine": True,
        "attemptedAtUtc": utc_now(),
        "completedAtUtc": utc_now(),
        "repoRoot": str(repo_root),
        "outputDir": str(output_dir),
        "target": {
            "processName": options.process_name,
            "processId": options.process_id,
            "requestedWindowHandle": options.window_handle,
            "titleContains": options.title_contains,
        },
        "window": None,
        "foreground": None,
        "attempts": [],
        "blockers": blockers,
        "warnings": [],
        "capabilities": build_capabilities(None, classification, blockers),
        "summaryPath": str(output_dir / "target-control-status.json"),
    }


def window_to_dict(snapshot: WindowSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "windowHandle": snapshot.hwnd,
        "windowHandleHex": snapshot.hwnd_hex,
        "processId": snapshot.process_id,
        "processName": snapshot.process_name,
        "title": snapshot.title,
        "isWindow": True,
        "isVisible": snapshot.is_visible,
        "isMinimized": snapshot.is_minimized,
    }


def foreground_to_dict(snapshot: ForegroundSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "foregroundWindowHandle": snapshot.hwnd,
        "foregroundWindowHandleHex": snapshot.hwnd_hex,
        "foregroundProcessId": snapshot.process_id,
        "foregroundProcessName": snapshot.process_name,
        "foregroundTitle": snapshot.title,
    }


def write_artifacts(summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "target-control-status.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown_summary(summary, output_dir / "target-control-status.md")


def write_markdown_summary(summary: dict[str, Any], path: Path) -> None:
    blockers = ", ".join(summary.get("blockers") or []) or "none"
    warnings = ", ".join(summary.get("warnings") or []) or "none"
    capabilities = summary.get("capabilities") or {}
    capability_rows = "\n".join(f"| `{key}` | `{value}` |" for key, value in capabilities.items())

    body = f"""# RiftReader Target-Control Status

| Field | Value |
|---|---|
| Status | `{summary.get('status')}` |
| Classification | `{summary.get('classification')}` |
| Ready for read-only proof | `{summary.get('readyForReadOnlyProof')}` |
| Ready for visual gate | `{summary.get('readyForVisualGate')}` |
| Ready for live input preflight | `{summary.get('readyForLiveInput')}` |
| Blockers | `{blockers}` |
| Warnings | `{warnings}` |
| Summary JSON | `{summary.get('summaryPath')}` |

## Capabilities

| Capability | Value |
|---|---|
{capability_rows}

## Safety

No movement, yaw stimulus, turn stimulus, slash command, screenshot-key input, or `/reloadui` was sent by target-control.
"""
    path.write_text(body, encoding="utf-8")


def default_output_dir(repo_root: Path, process_id: int | None) -> Path:
    pid_text = f"currentpid-{process_id}" if process_id is not None else "currenttarget"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return repo_root / "scripts" / "captures" / f"target-control-{pid_text}-{stamp}"


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the no-input RiftReader target-control preflight.")
    parser.add_argument("--pid", type=int, dest="process_id", help="Exact target Rift process id.")
    parser.add_argument("--hwnd", dest="window_handle", help="Exact target window handle, e.g. 0x5121A.")
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--settle-ms", type=int, default=DEFAULT_SETTLE_MS)
    parser.add_argument("--no-strong-assist", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    summary = run_target_control(
        TargetControlOptions(
            repo_root=repo_root,
            process_id=args.process_id,
            window_handle=args.window_handle,
            process_name=args.process_name,
            title_contains=args.title_contains,
            output_dir=args.output_dir,
            retries=args.retries,
            settle_ms=args.settle_ms,
            strong_assist=not args.no_strong_assist,
        )
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"{summary['status']}: classification={summary['classification']} "
            f"readyForVisualGate={summary['readyForVisualGate']} "
            f"readyForLiveInput={summary['readyForLiveInput']} "
            f"blockers={','.join(summary['blockers']) or 'none'}"
        )
        print(f"summaryPath={summary['summaryPath']}")

    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())

# END_OF_SCRIPT_MARKER
