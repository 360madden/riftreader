from __future__ import annotations

import argparse
import ctypes
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_preflight import (
    enumerate_debugger_processes,
    enumerate_window_targets,
    int_hex,
    normalize_hwnd,
    query_process_details,
    start_time_delta_seconds,
)


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"
THREAD_QUERY_INFORMATION = 0x0040
THREAD_SUSPEND_RESUME = 0x0002
THREAD_GET_CONTEXT = 0x0008
THREAD_SET_CONTEXT = 0x0010
THREAD_QUERY_LIMITED_INFORMATION = 0x0800
TH32CS_SNAPTHREAD = 0x00000004
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
CONTEXT_AMD64 = 0x00100000
CONTEXT_DEBUG_REGISTERS = CONTEXT_AMD64 | 0x00000010


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def win_error() -> str:
    code = ctypes.get_last_error()
    return f"winerr={code}"


def hex_or_none(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{int(value) & ((1 << 64) - 1):X}"


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ThreadID", ctypes.c_uint32),
        ("th32OwnerProcessID", ctypes.c_uint32),
        ("tpBasePri", ctypes.c_long),
        ("tpDeltaPri", ctypes.c_long),
        ("dwFlags", ctypes.c_uint32),
    ]


class M128A(ctypes.Structure):
    _fields_ = [
        ("Low", ctypes.c_ulonglong),
        ("High", ctypes.c_longlong),
    ]


class AMD64_CONTEXT(ctypes.Structure):
    _fields_ = [
        ("P1Home", ctypes.c_ulonglong),
        ("P2Home", ctypes.c_ulonglong),
        ("P3Home", ctypes.c_ulonglong),
        ("P4Home", ctypes.c_ulonglong),
        ("P5Home", ctypes.c_ulonglong),
        ("P6Home", ctypes.c_ulonglong),
        ("ContextFlags", ctypes.c_ulong),
        ("MxCsr", ctypes.c_ulong),
        ("SegCs", ctypes.c_ushort),
        ("SegDs", ctypes.c_ushort),
        ("SegEs", ctypes.c_ushort),
        ("SegFs", ctypes.c_ushort),
        ("SegGs", ctypes.c_ushort),
        ("SegSs", ctypes.c_ushort),
        ("EFlags", ctypes.c_ulong),
        ("Dr0", ctypes.c_ulonglong),
        ("Dr1", ctypes.c_ulonglong),
        ("Dr2", ctypes.c_ulonglong),
        ("Dr3", ctypes.c_ulonglong),
        ("Dr6", ctypes.c_ulonglong),
        ("Dr7", ctypes.c_ulonglong),
        ("Rax", ctypes.c_ulonglong),
        ("Rcx", ctypes.c_ulonglong),
        ("Rdx", ctypes.c_ulonglong),
        ("Rbx", ctypes.c_ulonglong),
        ("Rsp", ctypes.c_ulonglong),
        ("Rbp", ctypes.c_ulonglong),
        ("Rsi", ctypes.c_ulonglong),
        ("Rdi", ctypes.c_ulonglong),
        ("R8", ctypes.c_ulonglong),
        ("R9", ctypes.c_ulonglong),
        ("R10", ctypes.c_ulonglong),
        ("R11", ctypes.c_ulonglong),
        ("R12", ctypes.c_ulonglong),
        ("R13", ctypes.c_ulonglong),
        ("R14", ctypes.c_ulonglong),
        ("R15", ctypes.c_ulonglong),
        ("Rip", ctypes.c_ulonglong),
        ("FltSave", ctypes.c_byte * 512),
        ("VectorRegister", M128A * 26),
        ("VectorControl", ctypes.c_ulonglong),
        ("DebugControl", ctypes.c_ulonglong),
        ("LastBranchToRip", ctypes.c_ulonglong),
        ("LastBranchFromRip", ctypes.c_ulonglong),
        ("LastExceptionToRip", ctypes.c_ulonglong),
        ("LastExceptionFromRip", ctypes.c_ulonglong),
    ]


def aligned_context() -> tuple[ctypes.Array[ctypes.c_char], AMD64_CONTEXT]:
    raw = ctypes.create_string_buffer(ctypes.sizeof(AMD64_CONTEXT) + 16)
    address = ctypes.addressof(raw)
    aligned = (address + 15) & ~15
    context = AMD64_CONTEXT.from_address(aligned)
    context.ContextFlags = CONTEXT_DEBUG_REGISTERS
    return raw, context


def enumerate_threads(pid: int) -> list[dict[str, Any]]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return []
    threads: list[dict[str, Any]] = []
    try:
        entry = THREADENTRY32()
        entry.dwSize = ctypes.sizeof(THREADENTRY32)
        if not kernel32.Thread32First(snapshot, ctypes.byref(entry)):
            return []
        while True:
            if int(entry.th32OwnerProcessID) == int(pid):
                threads.append(
                    {
                        "threadId": int(entry.th32ThreadID),
                        "ownerProcessId": int(entry.th32OwnerProcessID),
                        "basePriority": int(entry.tpBasePri),
                    }
                )
            if not kernel32.Thread32Next(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return threads


def query_debug_state(pid: int) -> dict[str, Any]:
    if os.name != "nt":
        return {"supported": False, "warnings": ["windows-required"]}
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    result: dict[str, Any] = {
        "supported": True,
        "processDebugPort": None,
        "processDebugFlags": None,
        "processDebugObjectHandle": None,
        "processDebugFlagsIndicatesDebugger": None,
        "debuggerLikelyAttached": None,
        "warnings": [],
    }
    if not handle:
        result["warnings"].append(f"open-process-query-failed:{win_error()}")
        return result
    try:
        nt_query = ntdll.NtQueryInformationProcess
        nt_query.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
        nt_query.restype = ctypes.c_long

        return_length = ctypes.c_ulong(0)
        debug_port = ctypes.c_void_p()
        status = nt_query(handle, 7, ctypes.byref(debug_port), ctypes.sizeof(debug_port), ctypes.byref(return_length))
        if status == 0:
            port_value = int(debug_port.value or 0)
            result["processDebugPort"] = hex_or_none(port_value)
        else:
            result["warnings"].append(f"process-debug-port-query-failed:ntstatus=0x{status & 0xFFFFFFFF:X}")

        debug_object = ctypes.c_void_p()
        return_length = ctypes.c_ulong(0)
        status = nt_query(handle, 30, ctypes.byref(debug_object), ctypes.sizeof(debug_object), ctypes.byref(return_length))
        if status == 0:
            result["processDebugObjectHandle"] = hex_or_none(int(debug_object.value or 0))
        else:
            result["warnings"].append(f"process-debug-object-query-failed:ntstatus=0x{status & 0xFFFFFFFF:X}")

        debug_flags = ctypes.c_ulong(0)
        return_length = ctypes.c_ulong(0)
        status = nt_query(handle, 31, ctypes.byref(debug_flags), ctypes.sizeof(debug_flags), ctypes.byref(return_length))
        if status == 0:
            result["processDebugFlags"] = int(debug_flags.value)
        else:
            result["warnings"].append(f"process-debug-flags-query-failed:ntstatus=0x{status & 0xFFFFFFFF:X}")

        debug_port_int = int(debug_port.value or 0)
        debug_object_int = int(debug_object.value or 0)
        debug_flags_int = int(debug_flags.value)
        result["processDebugFlagsIndicatesDebugger"] = bool(debug_flags_int == 0)
        result["debuggerLikelyAttached"] = bool(debug_port_int or debug_object_int)
        if debug_flags_int == 0 and not debug_port_int and not debug_object_int:
            result["warnings"].append(
                "process-debug-flags-zero-without-debug-port-or-object; treating as not actively debugged"
            )
    finally:
        kernel32.CloseHandle(handle)
    return result


def inspect_thread_debug_registers(
    thread: dict[str, Any],
    *,
    clear_debug_registers: bool,
    force_resume_existing_suspended: bool,
) -> dict[str, Any]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    access = (
        THREAD_QUERY_INFORMATION
        | THREAD_QUERY_LIMITED_INFORMATION
        | THREAD_SUSPEND_RESUME
        | THREAD_GET_CONTEXT
        | (THREAD_SET_CONTEXT if clear_debug_registers else 0)
    )
    thread_id = int(thread["threadId"])
    item = dict(thread)
    item.update(
        {
            "opened": False,
            "previousSuspendCount": None,
            "resumeReturnCount": None,
            "contextCaptured": False,
            "debugRegisters": None,
            "debugRegistersNonZero": False,
            "clearDebugRegistersAttempted": False,
            "clearDebugRegistersSucceeded": False,
            "forceResumeExistingSuspensionAttempted": False,
            "forceResumeExistingSuspensionCalls": 0,
            "forceResumeExistingSuspensionResults": [],
            "errors": [],
        }
    )
    handle = kernel32.OpenThread(access, False, thread_id)
    if not handle:
        item["errors"].append(f"open-thread-failed:{win_error()}")
        return item
    item["opened"] = True
    suspended = False
    try:
        previous_count = kernel32.SuspendThread(handle)
        if previous_count == 0xFFFFFFFF:
            item["errors"].append(f"suspend-thread-failed:{win_error()}")
            return item
        suspended = True
        item["previousSuspendCount"] = int(previous_count)
        _raw, context = aligned_context()
        if not kernel32.GetThreadContext(handle, ctypes.byref(context)):
            item["errors"].append(f"get-thread-context-failed:{win_error()}")
        else:
            item["contextCaptured"] = True
            registers = {
                "dr0": hex_or_none(int(context.Dr0)),
                "dr1": hex_or_none(int(context.Dr1)),
                "dr2": hex_or_none(int(context.Dr2)),
                "dr3": hex_or_none(int(context.Dr3)),
                "dr6": hex_or_none(int(context.Dr6)),
                "dr7": hex_or_none(int(context.Dr7)),
            }
            item["debugRegisters"] = registers
            item["debugRegistersNonZero"] = any(
                int(getattr(context, name)) != 0 for name in ("Dr0", "Dr1", "Dr2", "Dr3", "Dr6", "Dr7")
            )
            if clear_debug_registers and item["debugRegistersNonZero"]:
                item["clearDebugRegistersAttempted"] = True
                context.ContextFlags = CONTEXT_DEBUG_REGISTERS
                context.Dr0 = 0
                context.Dr1 = 0
                context.Dr2 = 0
                context.Dr3 = 0
                context.Dr6 = 0
                context.Dr7 = 0
                item["clearDebugRegistersSucceeded"] = bool(kernel32.SetThreadContext(handle, ctypes.byref(context)))
                if not item["clearDebugRegistersSucceeded"]:
                    item["errors"].append(f"set-thread-context-clear-debug-registers-failed:{win_error()}")
    finally:
        if suspended:
            resumed_from = kernel32.ResumeThread(handle)
            if resumed_from == 0xFFFFFFFF:
                item["errors"].append(f"resume-thread-restore-failed:{win_error()}")
            else:
                item["resumeReturnCount"] = int(resumed_from)
            if force_resume_existing_suspended and (item.get("previousSuspendCount") or 0) > 0:
                item["forceResumeExistingSuspensionAttempted"] = True
                for _ in range(int(item["previousSuspendCount"])):
                    resume_result = kernel32.ResumeThread(handle)
                    if resume_result == 0xFFFFFFFF:
                        item["errors"].append(f"force-resume-existing-suspension-failed:{win_error()}")
                        break
                    item["forceResumeExistingSuspensionCalls"] = int(item["forceResumeExistingSuspensionCalls"]) + 1
                    item["forceResumeExistingSuspensionResults"].append(int(resume_result))
        kernel32.CloseHandle(handle)
    return item


def debug_active_process_stop(pid: int) -> dict[str, Any]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    result: dict[str, Any] = {
        "attempted": True,
        "succeeded": False,
        "error": None,
    }
    succeeded = bool(kernel32.DebugActiveProcessStop(int(pid)))
    result["succeeded"] = succeeded
    if not succeeded:
        result["error"] = win_error()
    return result


def summarize_threads(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "threadCount": len(items),
        "openedCount": sum(1 for item in items if item.get("opened")),
        "contextCapturedCount": sum(1 for item in items if item.get("contextCaptured")),
        "nonZeroDebugRegisterCount": sum(1 for item in items if item.get("debugRegistersNonZero")),
        "clearDebugRegistersAttemptedCount": sum(1 for item in items if item.get("clearDebugRegistersAttempted")),
        "clearDebugRegistersSucceededCount": sum(1 for item in items if item.get("clearDebugRegistersSucceeded")),
        "previouslySuspendedCount": sum(1 for item in items if (item.get("previousSuspendCount") or 0) > 0),
        "forceResumeExistingSuspensionAttemptedCount": sum(
            1 for item in items if item.get("forceResumeExistingSuspensionAttempted")
        ),
        "forceResumeExistingSuspensionCallCount": sum(
            int(item.get("forceResumeExistingSuspensionCalls") or 0) for item in items
        ),
        "errorCount": sum(1 for item in items if item.get("errors")),
    }


def process_cpu_seconds(pid: int) -> float | None:
    try:
        import psutil  # type: ignore

        process = psutil.Process(pid)
        times = process.cpu_times()
        return float(times.user + times.system)
    except Exception:
        return None


def choose_target(
    *,
    process_name: str,
    title_contains: str | None,
    target_pid: int,
    target_hwnd: str,
) -> dict[str, Any] | None:
    expected_hwnd = normalize_hwnd(target_hwnd)
    for target in enumerate_window_targets(process_name=process_name, title_contains=title_contains):
        if int(target.get("pid") or -1) != int(target_pid):
            continue
        if normalize_hwnd(target.get("hwndHex") or target.get("hwnd")) != expected_hwnd:
            continue
        return target
    return None


def build_markdown(summary: dict[str, Any]) -> str:
    target = summary.get("target") if isinstance(summary.get("target"), dict) else {}
    thread_summary = summary.get("threadSummary") if isinstance(summary.get("threadSummary"), dict) else {}
    lines = [
        "# x64dbg target recovery diagnostics",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- PID: `{summary.get('inputs', {}).get('targetPid')}`",
        f"- HWND: `{summary.get('inputs', {}).get('targetHwnd')}`",
        f"- Responding before: `{target.get('respondingBefore')}`",
        f"- Responding after: `{target.get('respondingAfter')}`",
        f"- Debugger likely attached: `{summary.get('debugState', {}).get('debuggerLikelyAttached')}`",
        f"- Threads inspected: `{thread_summary.get('threadCount')}`",
        f"- Non-zero debug-register threads: `{thread_summary.get('nonZeroDebugRegisterCount')}`",
        f"- Previously suspended threads: `{thread_summary.get('previouslySuspendedCount')}`",
        f"- Force-resume calls: `{thread_summary.get('forceResumeExistingSuspensionCallCount')}`",
        f"- DebugActiveProcessStop: `{summary.get('debugActiveProcessStop', {}).get('succeeded')}`",
        f"- Clear debug registers attempted: `{thread_summary.get('clearDebugRegistersAttemptedCount')}`",
        f"- CPU delta seconds: `{summary.get('cpu', {}).get('deltaSeconds')}`",
        "",
        "This artifact does not send game input, patch memory, set breakpoints, or promote coordinate candidates.",
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    return "\n".join(lines).rstrip() + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = args.output_root.resolve() if args.output_root else repo_root / "scripts" / "captures" / f"x64dbg-target-recovery-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    threads_json = run_dir / "threads.json"

    blockers: list[str] = []
    warnings: list[str] = []
    if os.name != "nt":
        blockers.append("windows-required")
    if args.clear_debug_registers and not args.allow_clear_debug_registers:
        blockers.append("clear-debug-registers-requires-allow-clear-debug-registers")
    if args.inspect_thread_context and not args.allow_thread_touch:
        blockers.append("inspect-thread-context-requires-allow-thread-touch")
    if args.debug_active_process_stop and not args.allow_debug_active_process_stop:
        blockers.append("debug-active-process-stop-requires-allow-debug-active-process-stop")
    if args.force_resume_existing_suspended and not args.allow_force_resume_existing_suspended:
        blockers.append("force-resume-existing-suspended-requires-allow-force-resume-existing-suspended")

    target_before = choose_target(
        process_name=args.process_name,
        title_contains=args.title_contains,
        target_pid=args.target_pid,
        target_hwnd=args.target_hwnd,
    )
    details = query_process_details(args.target_pid)
    if target_before is None:
        blockers.append("target-window-not-found")
    if details.get("startTimeUtc") and args.expected_start_time_utc:
        delta = start_time_delta_seconds(details.get("startTimeUtc"), args.expected_start_time_utc)
        if delta is None or delta > args.start_time_tolerance_seconds:
            blockers.append(
                "process-start-time-mismatch:"
                f"actual={details.get('startTimeUtc')};expected={args.expected_start_time_utc};deltaSeconds={delta}"
            )
    if args.expected_module_base:
        actual_base = normalize_hwnd(details.get("moduleBaseAddressHex") or details.get("moduleBaseAddress"))
        expected_base = normalize_hwnd(args.expected_module_base)
        if actual_base != expected_base:
            blockers.append(f"module-base-mismatch:actual={actual_base};expected={expected_base}")

    cpu_before = process_cpu_seconds(args.target_pid)
    debug_state = query_debug_state(args.target_pid) if not blockers else {"skipped": True}
    threads = enumerate_threads(args.target_pid) if not blockers else []
    inspected_threads: list[dict[str, Any]] = []
    if not blockers and args.inspect_thread_context:
        for thread in threads:
            inspected_threads.append(
                inspect_thread_debug_registers(
                    thread,
                    clear_debug_registers=bool(args.clear_debug_registers and args.allow_clear_debug_registers),
                    force_resume_existing_suspended=bool(
                        args.force_resume_existing_suspended and args.allow_force_resume_existing_suspended
                    ),
                )
            )
    elif not blockers:
        inspected_threads = threads
    debug_stop_result = {"attempted": False, "succeeded": False, "error": None}
    if not blockers and args.debug_active_process_stop:
        debug_stop_result = debug_active_process_stop(args.target_pid)
    time.sleep(max(0.0, float(args.post_probe_wait_seconds)))
    cpu_after = process_cpu_seconds(args.target_pid)
    target_after = choose_target(
        process_name=args.process_name,
        title_contains=args.title_contains,
        target_pid=args.target_pid,
        target_hwnd=args.target_hwnd,
    )
    debugger_processes = enumerate_debugger_processes() if not blockers else []

    thread_summary = summarize_threads(inspected_threads)
    if thread_summary.get("nonZeroDebugRegisterCount") and not args.clear_debug_registers:
        warnings.append("non-zero-debug-registers-detected; rerun with --clear-debug-registers if cleanup is approved")
    if thread_summary.get("previouslySuspendedCount"):
        if args.force_resume_existing_suspended and args.allow_force_resume_existing_suspended:
            warnings.append("threads-had-existing-suspend-count; force-resumed per recovery flags")
        else:
            warnings.append("threads-had-existing-suspend-count; not force-resuming existing suspension")
    if (target_after or {}).get("responding") is False:
        warnings.append("target-still-not-responding-after-diagnostics")

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-target-recovery",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "captured",
        "repoRoot": str(repo_root),
        "inputs": {
            "processName": args.process_name,
            "titleContains": args.title_contains,
            "targetPid": args.target_pid,
            "targetHwnd": normalize_hwnd(args.target_hwnd),
            "expectedStartTimeUtc": args.expected_start_time_utc,
            "expectedModuleBase": normalize_hwnd(args.expected_module_base),
            "inspectThreadContext": bool(args.inspect_thread_context),
            "allowThreadTouch": bool(args.allow_thread_touch),
            "clearDebugRegisters": bool(args.clear_debug_registers),
            "allowClearDebugRegisters": bool(args.allow_clear_debug_registers),
            "debugActiveProcessStop": bool(args.debug_active_process_stop),
            "allowDebugActiveProcessStop": bool(args.allow_debug_active_process_stop),
            "forceResumeExistingSuspended": bool(args.force_resume_existing_suspended),
            "allowForceResumeExistingSuspended": bool(args.allow_force_resume_existing_suspended),
        },
        "target": {
            "processDetails": details,
            "windowBefore": target_before,
            "respondingBefore": (target_before or {}).get("responding"),
            "windowAfter": target_after,
            "respondingAfter": (target_after or {}).get("responding"),
        },
        "debugState": debug_state,
        "debugActiveProcessStop": debug_stop_result,
        "threadSummary": thread_summary,
        "cpu": {
            "beforeSeconds": cpu_before,
            "afterSeconds": cpu_after,
            "deltaSeconds": round(cpu_after - cpu_before, 6) if cpu_before is not None and cpu_after is not None else None,
            "sampleSeconds": args.post_probe_wait_seconds,
        },
        "debuggerProcessCount": len(debugger_processes),
        "debuggerProcesses": debugger_processes,
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "threadsJson": str(threads_json),
        },
        "safety": {
            "gameInputSent": False,
            "movementSent": False,
            "targetMemoryWritten": False,
            "breakpointsSet": False,
            "x64dbgAttached": False,
            "threadSuspendResumeTouched": bool(args.inspect_thread_context and args.allow_thread_touch and not blockers),
            "debugRegistersCleared": bool(thread_summary.get("clearDebugRegistersSucceededCount")),
            "debugActiveProcessStopCalled": bool(debug_stop_result.get("attempted")),
            "forceResumeExistingSuspensionCalled": bool(thread_summary.get("forceResumeExistingSuspensionCallCount")),
            "candidateOnly": True,
            "promotionEligible": False,
        },
    }
    write_json(threads_json, inspected_threads)
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read/debugger-remnant diagnostics for an exact RIFT target after x64dbg work.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--target-hwnd", required=True)
    parser.add_argument("--expected-start-time-utc", default=None)
    parser.add_argument("--start-time-tolerance-seconds", type=float, default=1.0)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--inspect-thread-context", action="store_true")
    parser.add_argument("--allow-thread-touch", action="store_true")
    parser.add_argument("--clear-debug-registers", action="store_true")
    parser.add_argument("--allow-clear-debug-registers", action="store_true")
    parser.add_argument("--debug-active-process-stop", action="store_true")
    parser.add_argument("--allow-debug-active-process-stop", action="store_true")
    parser.add_argument("--force-resume-existing-suspended", action="store_true")
    parser.add_argument("--allow-force-resume-existing-suspended", action="store_true")
    parser.add_argument("--post-probe-wait-seconds", type=float, default=2.0)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "threadsJson": summary["artifacts"]["threadsJson"],
                    "respondingBefore": summary["target"]["respondingBefore"],
                    "respondingAfter": summary["target"]["respondingAfter"],
                    "debuggerLikelyAttached": (summary.get("debugState") or {}).get("debuggerLikelyAttached"),
                    "debugActiveProcessStop": summary.get("debugActiveProcessStop"),
                    "threadSummary": summary["threadSummary"],
                    "cpu": summary["cpu"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    return 2 if summary["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
