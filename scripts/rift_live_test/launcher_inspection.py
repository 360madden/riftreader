from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
KIND = "riftreader-launcher-inspection"
DEFAULT_OUTPUT_ROOT = Path(".riftreader-local") / "launcher-inspection"
WATCHED_PROCESS_NAMES = ("GlyphClientApp.exe", "GlyphCrashHandler64.exe", "rift_x64.exe")
GLYPH_CLIENT_PROCESS = "GlyphClientApp.exe"
GLYPH_CRASH_PROCESS = "GlyphCrashHandler64.exe"
RIFT_PROCESS = "rift_x64.exe"
SAFE_STANDALONE_FLAGS = {"-hidden", "--hidden", "/hidden"}
SENSITIVE_OPTIONS = {
    "-a",
    "--auth",
    "--auth-token",
    "-h",
    "--host",
    "-k",
    "--key",
    "--login",
    "-p",
    "--password",
    "--pass",
    "-r",
    "--refresh",
    "-s",
    "--session",
    "--session-id",
    "-t",
    "--ticket",
    "--token",
    "-u",
    "--user",
    "--username",
}
SENSITIVE_OPTION_WORDS = (
    "auth",
    "credential",
    "key",
    "login",
    "password",
    "secret",
    "session",
    "ticket",
    "token",
    "user",
)
TOKEN_RE = re.compile(r'"[^"]*"|\S+')


if os.name == "nt":
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
else:
    WNDENUMPROC = None  # type: ignore[assignment]


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
        return str(path)


def split_command_line(command_line: str | None) -> list[str]:
    if not command_line:
        return []
    return [token.strip('"') for token in TOKEN_RE.findall(command_line)]


def option_name(token: str) -> str:
    if "=" in token:
        token = token.split("=", 1)[0]
    return token.strip().lower()


def is_sensitive_option(token: str) -> bool:
    normalized = option_name(token)
    if normalized in SENSITIVE_OPTIONS:
        return True
    stripped = normalized.lstrip("-/")
    return any(word in stripped for word in SENSITIVE_OPTION_WORDS)


def redact_command_line(command_line: str | None) -> str | None:
    """Return a conservative command-line summary without auth/session values."""

    tokens = split_command_line(command_line)
    if not tokens:
        return None

    executable = Path(tokens[0]).name or tokens[0]
    redacted: list[str] = [executable]
    index = 1
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower()
        if lowered in SAFE_STANDALONE_FLAGS:
            redacted.append(token)
            index += 1
            continue

        if "=" in token and (token.startswith("-") or token.startswith("/")):
            name = token.split("=", 1)[0]
            if is_sensitive_option(token):
                redacted.append(f"{name}=<redacted>")
            else:
                redacted.append(f"{name}=<redacted>")
            index += 1
            continue

        if token.startswith("-") or token.startswith("/"):
            redacted.append(token)
            if index + 1 < len(tokens) and not tokens[index + 1].startswith(("-", "/")):
                redacted.append("<redacted>")
                index += 2
            else:
                index += 1
            continue

        redacted.append("<redacted>")
        index += 1

    return " ".join(redacted)


def file_time_utc(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    except OSError:
        return None


def normalize_process_record(raw: dict[str, Any]) -> dict[str, Any]:
    command_line = raw.get("CommandLine") or raw.get("commandLine")
    process_id = raw.get("ProcessId") if raw.get("ProcessId") is not None else raw.get("processId")
    parent_id = raw.get("ParentProcessId") if raw.get("ParentProcessId") is not None else raw.get("parentProcessId")
    return {
        "name": raw.get("Name") or raw.get("name"),
        "processId": int(process_id) if process_id is not None else None,
        "parentProcessId": int(parent_id) if parent_id is not None else None,
        "executablePath": raw.get("ExecutablePath") or raw.get("executablePath"),
        "creationDate": raw.get("CreationDate") or raw.get("creationDate"),
        "commandLineRedacted": redact_command_line(command_line),
        "commandLineWasPresent": bool(command_line),
        "rawCommandLineStored": False,
    }


def powershell_executable() -> str:
    return "powershell.exe" if os.name == "nt" else "pwsh"


def collect_processes(timeout_seconds: float = 15.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if os.name != "nt":
        return [], {
            "status": "unsupported-platform",
            "ok": False,
            "error": "Windows process discovery is required for Glyph/RIFT inspection.",
            "stdoutRedacted": True,
        }

    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "$names = @('GlyphClientApp.exe','GlyphCrashHandler64.exe','rift_x64.exe')",
            "$items = @(Get-CimInstance Win32_Process | Where-Object { $names -contains $_.Name } | ForEach-Object {",
            "  [pscustomobject]@{",
            "    Name = $_.Name",
            "    ProcessId = $_.ProcessId",
            "    ParentProcessId = $_.ParentProcessId",
            "    ExecutablePath = $_.ExecutablePath",
            "    CommandLine = $_.CommandLine",
            "    CreationDate = $_.CreationDate",
            "  }",
            "})",
            "$items | ConvertTo-Json -Depth 4",
        ]
    )
    command = [
        powershell_executable(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]
    started = utc_iso()
    start_monotonic = time.monotonic()
    envelope: dict[str, Any] = {
        "label": "glyph-rift-process-query",
        "args": [command[0], command[1], command[2], command[3], command[4], command[5], "<script-redacted>"],
        "startedAtUtc": started,
        "timeoutSeconds": timeout_seconds,
        "exitCode": None,
        "ok": False,
        "stdoutRedacted": True,
        "rawCommandLinesStored": False,
    }
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
        )
        envelope["exitCode"] = completed.returncode
        envelope["ok"] = completed.returncode == 0
        envelope["stderrPreview"] = "\n".join(completed.stderr.splitlines()[:20])
        if completed.returncode != 0:
            return [], envelope
        stdout = completed.stdout.strip()
        if not stdout:
            raw_items: list[dict[str, Any]] = []
        else:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict):
                raw_items = [parsed]
            elif isinstance(parsed, list):
                raw_items = [item for item in parsed if isinstance(item, dict)]
            else:
                raw_items = []
        processes = [normalize_process_record(item) for item in raw_items]
        envelope["processCount"] = len(processes)
        return processes, envelope
    except subprocess.TimeoutExpired as exc:
        envelope["ok"] = False
        envelope["timedOut"] = True
        envelope["error"] = f"TimeoutExpired:{exc}"
        return [], envelope
    except Exception as exc:  # noqa: BLE001 - preserve diagnostics without leaking command stdout.
        envelope["ok"] = False
        envelope["error"] = f"{type(exc).__name__}:{exc}"
        return [], envelope
    finally:
        envelope["endedAtUtc"] = utc_iso()
        envelope["durationSeconds"] = round(time.monotonic() - start_monotonic, 3)


def hwnd_to_int(value: Any) -> int:
    if value is None:
        return 0
    raw_value = getattr(value, "value", value)
    if raw_value is None:
        return 0
    return int(raw_value)


def rect_to_dict(rect: wintypes.RECT) -> dict[str, int]:
    return {
        "left": int(rect.left),
        "top": int(rect.top),
        "right": int(rect.right),
        "bottom": int(rect.bottom),
        "width": int(rect.right - rect.left),
        "height": int(rect.bottom - rect.top),
    }


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
    return user32


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


def get_window_pid(user32: Any, hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value)


def collect_windows_for_pids(pids: set[int]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if os.name != "nt":
        return [], [{"type": "UnsupportedPlatform", "message": "Windows HWND enumeration is required."}]
    if not pids:
        return [], []

    user32 = load_user32()
    windows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    @WNDENUMPROC  # type: ignore[misc]
    def enum_proc(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        hwnd_int = hwnd_to_int(hwnd)
        try:
            pid = get_window_pid(user32, hwnd_int)
            if pid not in pids:
                return True
            window_rect = wintypes.RECT()
            client_rect = wintypes.RECT()
            window_rect_dict: dict[str, int] | None = None
            client_rect_dict: dict[str, int] | None = None
            if user32.GetWindowRect(wintypes.HWND(hwnd_int), ctypes.byref(window_rect)):
                window_rect_dict = rect_to_dict(window_rect)
            if user32.GetClientRect(wintypes.HWND(hwnd_int), ctypes.byref(client_rect)):
                client_rect_dict = rect_to_dict(client_rect)
            windows.append(
                {
                    "processId": pid,
                    "windowHandle": f"0x{hwnd_int:X}",
                    "title": get_window_text(user32, hwnd_int),
                    "className": get_window_class(user32, hwnd_int),
                    "isVisible": bool(user32.IsWindowVisible(wintypes.HWND(hwnd_int))),
                    "isMinimized": bool(user32.IsIconic(wintypes.HWND(hwnd_int))),
                    "windowRect": window_rect_dict,
                    "clientRect": client_rect_dict,
                    "clientSize": {
                        "width": client_rect_dict.get("width", 0) if client_rect_dict else 0,
                        "height": client_rect_dict.get("height", 0) if client_rect_dict else 0,
                    },
                }
            )
        except Exception as exc:  # noqa: BLE001 - preserve per-window failures without aborting the inspection.
            errors.append({"type": type(exc).__name__, "message": str(exc), "windowHandle": f"0x{hwnd_int:X}"})
        return True

    user32.EnumWindows(enum_proc, 0)
    windows.sort(key=lambda item: (int(item.get("processId") or 0), str(item.get("windowHandle") or "")))
    return windows, errors


def name_matches(process: dict[str, Any], expected_name: str) -> bool:
    return str(process.get("name") or "").casefold() == expected_name.casefold()


def process_ids(processes: list[dict[str, Any]], expected_name: str) -> list[int]:
    result: list[int] = []
    for process in processes:
        if name_matches(process, expected_name) and process.get("processId") is not None:
            result.append(int(process["processId"]))
    return sorted(result)


def is_descendant(pid: int, ancestor_pid: int, parent_by_pid: dict[int, int | None]) -> bool:
    seen: set[int] = set()
    current = pid
    while current not in seen:
        seen.add(current)
        parent = parent_by_pid.get(current)
        if parent is None:
            return False
        if parent == ancestor_pid:
            return True
        current = parent
    return False


def classify_launcher_game_state(processes: list[dict[str, Any]]) -> dict[str, Any]:
    glyph_client_pids = process_ids(processes, GLYPH_CLIENT_PROCESS)
    glyph_crash_pids = process_ids(processes, GLYPH_CRASH_PROCESS)
    rift_pids = process_ids(processes, RIFT_PROCESS)
    parent_by_pid: dict[int, int | None] = {
        int(process["processId"]): int(process["parentProcessId"])
        if process.get("parentProcessId") is not None
        else None
        for process in processes
        if process.get("processId") is not None
    }
    relations: list[dict[str, Any]] = []
    for rift_pid in rift_pids:
        parent_pid = parent_by_pid.get(rift_pid)
        descendant_of = [glyph_pid for glyph_pid in glyph_client_pids if is_descendant(rift_pid, glyph_pid, parent_by_pid)]
        relations.append(
            {
                "riftPid": rift_pid,
                "parentProcessId": parent_pid,
                "descendantOfGlyphClientPids": descendant_of,
                "isDescendantOfGlyphClient": bool(descendant_of),
            }
        )

    launcher_present = bool(glyph_client_pids)
    game_present = bool(rift_pids)
    rift_child_of_launcher = any(item["isDescendantOfGlyphClient"] for item in relations)
    warnings: list[str] = []
    blockers: list[str] = []
    if launcher_present and game_present and not rift_child_of_launcher:
        warnings.append("rift-process-present-but-parent-not-glyph-client")

    if launcher_present and game_present and rift_child_of_launcher:
        crash_state = "launcher-and-game-present"
        relogin_state = "observe-current-game-child"
    elif launcher_present and game_present:
        crash_state = "launcher-and-game-present-parent-unverified"
        relogin_state = "observe-current-game-parent-unverified"
    elif launcher_present:
        crash_state = "launcher-present-game-missing"
        relogin_state = "approval-required-before-launch"
        blockers.append("game-process-missing-do-not-launch-without-explicit-approval")
    elif game_present:
        crash_state = "game-present-launcher-missing"
        relogin_state = "observe-game-without-launcher-parent"
        warnings.append("launcher-process-missing-while-game-is-running")
    else:
        crash_state = "launcher-and-game-missing"
        relogin_state = "blocked-launcher-and-game-missing"
        blockers.append("launcher-and-game-processes-missing")

    return {
        "crashRecoveryState": crash_state,
        "reloginState": relogin_state,
        "glyphClientPids": glyph_client_pids,
        "glyphCrashHandlerPids": glyph_crash_pids,
        "riftPids": rift_pids,
        "riftChildOfLauncher": rift_child_of_launcher,
        "relations": relations,
        "warnings": warnings,
        "blockers": blockers,
    }


def classify_launcher_window_state(window: dict[str, Any] | None) -> str:
    if not window:
        return "missing"
    if not bool(window.get("isVisible")):
        return "hidden"
    if bool(window.get("isMinimized")):
        return "minimized-or-offscreen"
    rect = window.get("windowRect") if isinstance(window.get("windowRect"), dict) else {}
    if int(rect.get("left", 0) or 0) <= -30000 or int(rect.get("top", 0) or 0) <= -30000:
        return "minimized-or-offscreen"
    client = window.get("clientSize") if isinstance(window.get("clientSize"), dict) else {}
    if int(client.get("width", 0) or 0) <= 0 or int(client.get("height", 0) or 0) <= 0:
        return "no-client-area"
    return "visible-with-client-area"


def select_launcher_main_window(windows: list[dict[str, Any]], launcher_pids: list[int]) -> dict[str, Any] | None:
    candidates = [window for window in windows if int(window.get("processId") or 0) in set(launcher_pids)]
    if not candidates:
        return None

    def score(window: dict[str, Any]) -> tuple[int, str]:
        title = str(window.get("title") or "")
        class_name = str(window.get("className") or "")
        client = window.get("clientSize") if isinstance(window.get("clientSize"), dict) else {}
        value = 0
        if title.casefold() == "glyph":
            value += 100
        elif title.strip():
            value += 20
        if class_name == "Qt5QWindowIcon":
            value += 10
        if bool(window.get("isVisible")):
            value += 5
        if not bool(window.get("isMinimized")):
            value += 3
        if int(client.get("width", 0) or 0) > 0 and int(client.get("height", 0) or 0) > 0:
            value += 2
        return value, str(window.get("windowHandle") or "")

    selected = max(candidates, key=score)
    selected = dict(selected)
    selected["state"] = classify_launcher_window_state(selected)
    return selected


def read_manifest_metadata(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "lastWriteTimeUtc": file_time_utc(path) if path.exists() else None,
        "version": None,
    }
    if not path.is_file():
        return result
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(20):
                line = handle.readline()
                if not line:
                    break
                stripped = line.strip()
                if stripped.lower().startswith("version "):
                    result["version"] = stripped.split(" ", 1)[1]
                    break
    except Exception as exc:  # noqa: BLE001 - inspection should keep going when a metadata file is locked.
        result["readError"] = f"{type(exc).__name__}:{exc}"
    return result


def file_metadata(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError as exc:
        return {"path": str(path), "exists": False, "error": f"{type(exc).__name__}:{exc}"}
    return {
        "path": str(path),
        "exists": True,
        "length": stat.st_size,
        "lastWriteTimeUtc": datetime.fromtimestamp(stat.st_mtime, UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }


def collect_metadata(processes: list[dict[str, Any]], *, include_log_tail: bool = False) -> dict[str, Any]:
    glyph_manifest_paths: set[Path] = set()
    rift_manifest_paths: set[Path] = set()
    notification_log_paths: set[Path] = set()
    for process in processes:
        executable = process.get("executablePath")
        if not executable:
            continue
        exe_path = Path(str(executable))
        if name_matches(process, GLYPH_CLIENT_PROCESS):
            glyph_manifest_paths.add(exe_path.parent / "library_manifest.txt")
            notification_log_paths.add(exe_path.parent / "Notification.log")
        if name_matches(process, RIFT_PROCESS):
            rift_manifest_paths.add(exe_path.parent / "manifest64.txt")

    metadata: dict[str, Any] = {
        "glyphLibraryManifests": [read_manifest_metadata(path) for path in sorted(glyph_manifest_paths)],
        "riftLiveManifests": [read_manifest_metadata(path) for path in sorted(rift_manifest_paths)],
        "notificationLogs": [file_metadata(path) for path in sorted(notification_log_paths)],
        "notificationLogTailStored": False,
    }
    if include_log_tail:
        tails: list[dict[str, Any]] = []
        for path in sorted(notification_log_paths):
            tail_record = file_metadata(path)
            if path.is_file():
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                    tail_record["tailPreview"] = "\n".join(lines[-40:])
                except Exception as exc:  # noqa: BLE001
                    tail_record["tailReadError"] = f"{type(exc).__name__}:{exc}"
            tails.append(tail_record)
        metadata["notificationLogs"] = tails
        metadata["notificationLogTailStored"] = True
    return metadata


def safety_state() -> dict[str, bool]:
    return {
        "movementSent": False,
        "inputSent": False,
        "mouseClickSent": False,
        "keyPressSent": False,
        "launcherButtonPressed": False,
        "launchAttempted": False,
        "processTerminated": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "providerWrites": False,
        "gitMutation": False,
        "rawCommandLinesStored": False,
    }


def build_launcher_inspection(
    repo_root: Path,
    *,
    output_root: Path,
    include_log_tail: bool = False,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    processes, process_envelope = collect_processes()
    if not process_envelope.get("ok") and process_envelope.get("status") != "unsupported-platform":
        errors.append({"type": "ProcessQueryFailed", "message": str(process_envelope.get("error") or process_envelope)})

    pids = {int(process["processId"]) for process in processes if process.get("processId") is not None}
    windows, window_errors = collect_windows_for_pids(pids)
    errors.extend(window_errors)
    state = classify_launcher_game_state(processes)
    launcher_main_window = select_launcher_main_window(windows, state["glyphClientPids"])
    launcher_window_state = classify_launcher_window_state(launcher_main_window)
    warnings = list(state.get("warnings") or [])
    blockers = list(state.get("blockers") or [])
    if launcher_window_state in {"hidden", "minimized-or-offscreen", "no-client-area"}:
        warnings.append(f"launcher-ui-not-ready-for-button-automation:{launcher_window_state}")
        blockers.append("launcher-button-automation-blocked-until-visible-state-classified")
    if any(process.get("commandLineWasPresent") for process in processes):
        warnings.append("process-command-lines-redacted-by-default")
    if include_log_tail:
        warnings.append("notification-log-tail-included-historical-only")

    metadata = collect_metadata(processes, include_log_tail=include_log_tail)
    output_dir = output_root / f"run-{utc_stamp()}"
    output_dir.mkdir(parents=True, exist_ok=False)
    summary_path = output_dir / "launcher-inspection-summary.json"
    markdown_path = output_dir / "LAUNCHER_INSPECTION.md"
    latest_path = output_root / "latest-run.txt"

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors and not process_envelope.get("ok") else "passed",
        "repoRoot": str(repo_root),
        "launcher": {
            "present": bool(state["glyphClientPids"]),
            "processIds": state["glyphClientPids"],
            "crashHandlerProcessIds": state["glyphCrashHandlerPids"],
            "mainWindow": launcher_main_window,
            "windowState": launcher_window_state,
            "processes": [process for process in processes if name_matches(process, GLYPH_CLIENT_PROCESS)],
        },
        "game": {
            "present": bool(state["riftPids"]),
            "processIds": state["riftPids"],
            "processes": [process for process in processes if name_matches(process, RIFT_PROCESS)],
        },
        "processTree": {
            "processes": processes,
            "relations": state["relations"],
            "queryEnvelope": process_envelope,
        },
        "windows": windows,
        "metadata": metadata,
        "state": {
            **state,
            "launcherWindowState": launcher_window_state,
            "automationRecommendation": (
                "observe-process-tree-and-game-window-only"
                if state["riftPids"]
                else "do-not-launch-without-explicit-approval"
            ),
            "buttonAutomationPolicy": (
                "blocked-hidden-or-minimized"
                if launcher_window_state in {"hidden", "minimized-or-offscreen", "no-client-area"}
                else "requires-explicit-approval-and-screenshot-classifier"
            ),
        },
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": errors,
        "safety": safety_state(),
        "artifacts": {
            "outputDir": repo_relative_or_absolute(repo_root, output_dir),
            "summaryJson": repo_relative_or_absolute(repo_root, summary_path),
            "summaryMarkdown": repo_relative_or_absolute(repo_root, markdown_path),
            "latestRun": repo_relative_or_absolute(repo_root, latest_path),
        },
    }
    write_json(summary_path, summary)
    write_text_atomic(markdown_path, render_markdown(summary) + "\n")
    write_text_atomic(latest_path, str(output_dir.resolve()) + "\n")
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    launcher = summary.get("launcher") or {}
    game = summary.get("game") or {}
    state = summary.get("state") or {}
    main_window = launcher.get("mainWindow") or {}
    metadata = summary.get("metadata") or {}
    glyph_versions = [
        item.get("version") for item in metadata.get("glyphLibraryManifests") or [] if isinstance(item, dict) and item.get("version")
    ]
    rift_versions = [
        item.get("version") for item in metadata.get("riftLiveManifests") or [] if isinstance(item, dict) and item.get("version")
    ]
    lines = [
        "# RiftReader launcher inspection",
        "",
        "## Verdict",
        "",
        (
            f"Glyph/RIFT launcher state is `{state.get('crashRecoveryState')}`. "
            f"Launcher button automation is `{state.get('buttonAutomationPolicy')}`."
        ),
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Generated UTC | `{summary.get('generatedAtUtc')}` |",
        f"| Status | `{summary.get('status')}` |",
        f"| Launcher present | `{launcher.get('present')}` |",
        f"| Launcher PIDs | `{launcher.get('processIds')}` |",
        f"| Launcher window state | `{launcher.get('windowState')}` |",
        f"| Launcher main HWND | `{main_window.get('windowHandle')}` title `{main_window.get('title')}` class `{main_window.get('className')}` |",
        f"| Game present | `{game.get('present')}` |",
        f"| RIFT PIDs | `{game.get('processIds')}` |",
        f"| RIFT child of Glyph | `{state.get('riftChildOfLauncher')}` |",
        f"| Glyph version(s) | `{glyph_versions}` |",
        f"| RIFT live version(s) | `{rift_versions}` |",
        "",
        "## Blockers",
        "",
    ]
    for blocker in summary.get("blockers") or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Warnings", ""])
    for warning in summary.get("warnings") or ["none"]:
        lines.append(f"- `{warning}`")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "No launcher buttons were pressed. No focus, click, key input, launch attempt, process termination, provider write, Git mutation, CE, or x64dbg attach was performed.",
            "",
            "## Artifacts",
            "",
        ]
    )
    for key, value in (summary.get("artifacts") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Glyph/RIFT launcher inspection for crash/relogin planning.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root. Defaults to this checkout.")
    parser.add_argument("--output-dir", default=None, help="Output root. Defaults to .riftreader-local/launcher-inspection.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    parser.add_argument(
        "--include-log-tail",
        action="store_true",
        help="Include a bounded Notification.log tail. Historical only; off by default.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_module()
    output_root = Path(args.output_dir) if args.output_dir else repo_root / DEFAULT_OUTPUT_ROOT
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    summary = build_launcher_inspection(
        repo_root,
        output_root=output_root,
        include_log_tail=bool(args.include_log_tail),
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(render_markdown(summary))
    return 1 if summary.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
