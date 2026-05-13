from __future__ import annotations

import argparse
import ctypes
import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_safety import live_attach_policy


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"
WINDOWS_TICK = 10_000_000
WINDOWS_EPOCH = datetime(1601, 1, 1, tzinfo=UTC)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def normalize_hwnd(value: str | int | None) -> str | None:
    if value is None or value == "":
        return None
    try:
        return f"0x{int(str(value), 0):X}"
    except ValueError:
        return str(value).strip()


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{value:X}"


def filetime_to_utc_iso(low: int, high: int) -> str:
    ticks = (int(high) << 32) + int(low)
    value = WINDOWS_EPOCH + timedelta(seconds=ticks / WINDOWS_TICK)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def process_matches_name(actual: str | None, expected: str) -> bool:
    if not actual:
        return False
    normalized_actual = actual[:-4] if actual.lower().endswith(".exe") else actual
    normalized_expected = expected[:-4] if expected.lower().endswith(".exe") else expected
    return normalized_actual.lower() == normalized_expected.lower()


def title_matches(title: str | None, contains: str | None) -> bool:
    if not contains:
        return True
    return contains.lower() in str(title or "").lower()


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


def query_process_details(pid: int) -> dict[str, Any]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    process_query_limited_information = 0x1000
    handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
    details: dict[str, Any] = {
        "pid": int(pid),
        "imagePath": None,
        "processName": None,
        "startTimeUtc": None,
        "moduleBaseAddress": None,
        "moduleBaseAddressHex": None,
        "warnings": [],
    }
    if not handle:
        details["warnings"].append("process-open-query-limited-failed")
        return details

    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            image_path = buffer.value
            details["imagePath"] = image_path
            details["processName"] = Path(image_path).stem
        else:
            details["warnings"].append("process-image-query-failed")

        creation_time = FILETIME()
        exit_time = FILETIME()
        kernel_time = FILETIME()
        user_time = FILETIME()
        if kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation_time),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            details["startTimeUtc"] = filetime_to_utc_iso(
                creation_time.dwLowDateTime,
                creation_time.dwHighDateTime,
            )
        else:
            details["warnings"].append("process-start-time-query-failed")
    finally:
        kernel32.CloseHandle(handle)

    module_base = query_main_module_base(pid)
    if module_base is not None:
        details["moduleBaseAddress"] = module_base
        details["moduleBaseAddressHex"] = int_hex(module_base)
    else:
        details["warnings"].append("module-base-query-failed")
    return details


def query_main_module_base(pid: int) -> int | None:
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        process_query_information = 0x0400
        process_vm_read = 0x0010
        list_modules_all = 0x03
        handle = kernel32.OpenProcess(process_query_information | process_vm_read, False, int(pid))
        if not handle:
            return None
        try:
            hmodule_array = (ctypes.c_void_p * 1024)()
            bytes_needed = ctypes.c_ulong()
            if not psapi.EnumProcessModulesEx(
                handle,
                ctypes.byref(hmodule_array),
                ctypes.sizeof(hmodule_array),
                ctypes.byref(bytes_needed),
                list_modules_all,
            ):
                return None
            if bytes_needed.value < ctypes.sizeof(ctypes.c_void_p):
                return None
            return int(hmodule_array[0])
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


def enumerate_window_targets(*, process_name: str, title_contains: str | None) -> list[dict[str, Any]]:
    if os.name != "nt":
        return []

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    targets: list[dict[str, Any]] = []

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            return True

        length = user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(ctypes.c_void_p(hwnd), buffer, length + 1)
        title = buffer.value
        if not title_matches(title, title_contains):
            return True

        hwnd_pid = ctypes.c_ulong(0)
        thread_id = user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(hwnd_pid))
        details = query_process_details(int(hwnd_pid.value))
        if not process_matches_name(details.get("processName"), process_name):
            return True

        responding = None
        try:
            responding = not bool(user32.IsHungAppWindow(ctypes.c_void_p(hwnd)))
        except Exception:
            details.setdefault("warnings", []).append("responding-query-failed")

        targets.append(
            {
                "processName": details.get("processName"),
                "pid": int(hwnd_pid.value),
                "hwnd": int(hwnd),
                "hwndHex": int_hex(int(hwnd)),
                "title": title,
                "threadId": int(thread_id),
                "responding": responding,
                "windowVisible": True,
                "imagePath": details.get("imagePath"),
                "startTimeUtc": details.get("startTimeUtc"),
                "moduleBaseAddress": details.get("moduleBaseAddress"),
                "moduleBaseAddressHex": details.get("moduleBaseAddressHex"),
                "warnings": details.get("warnings") or [],
            }
        )
        return True

    user32.EnumWindows(enum_windows_proc(callback), 0)
    return sorted(targets, key=lambda item: str(item.get("startTimeUtc") or ""), reverse=True)


def choose_target(
    candidates: Iterable[dict[str, Any]],
    *,
    target_pid: int | None,
    target_hwnd: str | None,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    items = list(candidates)
    expected_hwnd = normalize_hwnd(target_hwnd)

    if target_pid is not None:
        items = [item for item in items if int(item.get("pid") or -1) == int(target_pid)]
        if not items:
            blockers.append(f"target-pid-not-found:{target_pid}")
    if expected_hwnd is not None:
        items = [item for item in items if normalize_hwnd(item.get("hwndHex") or item.get("hwnd")) == expected_hwnd]
        if not items:
            blockers.append(f"target-hwnd-not-found:{expected_hwnd}")

    if blockers:
        return None, blockers, warnings
    if len(items) == 0:
        return None, ["no-windowed-target-found"], warnings
    if len(items) > 1:
        return None, [f"multiple-windowed-targets-found:{len(items)}"], warnings
    if target_pid is None or expected_hwnd is None:
        warnings.append("target-selected-by-single-windowed-process; pass --target-pid and --target-hwnd before live debugger work")
    return items[0], blockers, warnings


def make_safety() -> dict[str, Any]:
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "x64dbgLiveAttachStarted": False,
        "x64dbgCommandsExecuted": False,
        "x64dbgSessionConnected": False,
        "processAttachOrMemoryReadStarted": False,
        "processInspectionStarted": True,
        "targetMutationAllowed": False,
        "movementAllowed": False,
        "readOnlyOperatingSystemInspection": True,
        "liveAttachPolicy": live_attach_policy(),
    }


def build_summary(args: argparse.Namespace, repo_root: Path, run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    targets_json = run_dir / "targets.json"

    blockers: list[str] = []
    warnings: list[str] = []
    if args.self_test:
        candidates = [
            {
                "processName": args.process_name,
                "pid": args.target_pid or 12345,
                "hwnd": int(args.target_hwnd, 0) if args.target_hwnd else 0xABCDEF,
                "hwndHex": normalize_hwnd(args.target_hwnd) or "0xABCDEF",
                "title": "RIFT",
                "responding": True,
                "windowVisible": True,
                "startTimeUtc": "2026-05-13T00:00:00.0000000Z",
                "moduleBaseAddress": 0x7FF796B50000,
                "moduleBaseAddressHex": "0x7FF796B50000",
                "warnings": [],
            }
        ]
        warnings.append("self-test only; no live process inspection, x64dbg attach, memory read, or input")
    else:
        if os.name != "nt":
            blockers.append("windows-required-for-rift-window-preflight")
            candidates = []
        else:
            candidates = enumerate_window_targets(process_name=args.process_name, title_contains=args.title_contains)

    selected, choose_blockers, choose_warnings = choose_target(
        candidates,
        target_pid=args.target_pid,
        target_hwnd=args.target_hwnd,
    )
    blockers.extend(choose_blockers)
    warnings.extend(choose_warnings)

    if selected is not None and selected.get("responding") is False:
        blockers.append("selected-target-not-responding")
    if selected is not None and not selected.get("moduleBaseAddressHex"):
        warnings.append("selected-target-module-base-unavailable")
    if selected is not None and not selected.get("startTimeUtc"):
        warnings.append("selected-target-start-time-unavailable")

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-target-preflight",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "passed",
        "repoRoot": str(repo_root),
        "inputs": {
            "processName": args.process_name,
            "titleContains": args.title_contains,
            "targetPid": args.target_pid,
            "targetHwnd": normalize_hwnd(args.target_hwnd),
            "selfTest": bool(args.self_test),
        },
        "selectedTarget": selected,
        "targetCount": len(candidates),
        "blockers": blockers,
        "warnings": warnings,
        "safety": make_safety(),
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "targetsJson": str(targets_json),
        },
        "next": {
            "recommendedAction": (
                "Generate an x64dbg coord-chain plan packet from this exact PID/HWND/start metadata before any live debugger attach."
                if not blockers
                else "Resolve blockers before any x64dbg live debugger work."
            )
        },
    }
    return summary, candidates


def markdown_summary(summary: dict[str, Any]) -> str:
    selected = summary.get("selectedTarget") or {}
    lines = [
        "# x64dbg target preflight",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Movement sent: `{str(summary.get('safety', {}).get('movementSent')).lower()}`",
        f"- x64dbg live attach started: `{str(summary.get('safety', {}).get('x64dbgLiveAttachStarted')).lower()}`",
        f"- Process attach or memory read started: `{str(summary.get('safety', {}).get('processAttachOrMemoryReadStarted')).lower()}`",
        "",
        "## Selected target",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Process | `{selected.get('processName')}` |",
        f"| PID | `{selected.get('pid')}` |",
        f"| HWND | `{selected.get('hwndHex')}` |",
        f"| Title | `{selected.get('title')}` |",
        f"| Responding | `{selected.get('responding')}` |",
        f"| Start UTC | `{selected.get('startTimeUtc')}` |",
        f"| Module base | `{selected.get('moduleBaseAddressHex')}` |",
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This preflight uses read-only OS/window/process metadata only. It does not",
            "attach x64dbg, send game input, set breakpoints/watchpoints, or read/write",
            "target memory.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(summary: dict[str, Any], candidates: list[dict[str, Any]]) -> None:
    write_json(Path(summary["artifacts"]["targetsJson"]), candidates)
    write_json(Path(summary["artifacts"]["summaryJson"]), summary)
    write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"x64dbg-target-preflight-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only no-attach x64dbg target preflight for RIFT.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--target-pid", type=int, default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = choose_run_dir(repo_root, args.output_root)
    summary, candidates = build_summary(args, repo_root, run_dir)
    write_outputs(summary, candidates)

    result = {
        "status": summary["status"],
        "summaryJson": summary["artifacts"]["summaryJson"],
        "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
        "selectedTarget": summary.get("selectedTarget"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
    }
    if args.json:
        print(json.dumps(result, separators=(",", ":")))
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"summaryMarkdown={summary['artifacts']['summaryMarkdown']}")
        if summary.get("blockers"):
            print("blockers=" + ";".join(summary["blockers"]))
        if summary.get("warnings"):
            print("warnings=" + ";".join(summary["warnings"]))
    return 2 if summary["status"] == "blocked" else 0
