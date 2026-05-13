from __future__ import annotations

import argparse
import ctypes
import importlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_launcher import find_x64dbg_path
from .x64dbg_preflight import (
    choose_target,
    enumerate_debugger_processes,
    enumerate_window_targets,
    normalize_hwnd,
    start_time_delta_seconds,
)
from .x64dbg_safety import live_attach_policy


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_SUSPEND_RESUME = 0x0800
PROCESS_ALL_ACCESS = 0x001F0FFF
TOKEN_QUERY = 0x0008
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_ELEVATION_CLASS = 20
SE_PRIVILEGE_ENABLED = 0x00000002


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_uint32), ("HighPart", ctypes.c_int32)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", ctypes.c_uint32)]


class PRIVILEGE_SET(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", ctypes.c_uint32),
        ("Control", ctypes.c_uint32),
        ("Privilege", LUID_AND_ATTRIBUTES * 1),
    ]


class TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", ctypes.c_uint32)]


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):X}"


def plugin_paths_for_x64dbg(x64dbg_path: Path | None) -> dict[str, str | None]:
    if x64dbg_path is None:
        return {"plugin": None, "libzmq": None, "alternateLibzmq": None}
    plugin_dir = x64dbg_path.parent / "plugins"
    return {
        "plugin": str(plugin_dir / "x64dbg-automate.dp64"),
        "libzmq": str(plugin_dir / "libzmq-mt-4_3_5.dll"),
        "alternateLibzmq": str(x64dbg_path.parent / "libzmq-mt-4_3_5.dll"),
    }


def error_record(stage: str, exc: BaseException) -> dict[str, Any]:
    return {"stage": stage, "type": type(exc).__name__, "message": str(exc)}


def open_process_access_probe(pid: int, access: int, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "label": label,
        "access": int_hex(access),
        "ok": False,
        "errorCode": None,
        "errorHex": None,
    }
    if os.name != "nt":
        result["errorCode"] = "non-windows"
        return result
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    handle = kernel32.OpenProcess(access, False, int(pid))
    if handle:
        result["ok"] = True
        kernel32.CloseHandle(handle)
        return result
    code = ctypes.get_last_error()
    result["errorCode"] = code
    result["errorHex"] = int_hex(code)
    return result


def open_process_token(handle: int) -> int | None:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.OpenProcessToken.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    advapi32.OpenProcessToken.restype = ctypes.c_bool
    token = ctypes.c_void_p()
    if not advapi32.OpenProcessToken(ctypes.c_void_p(handle), TOKEN_QUERY, ctypes.byref(token)):
        return None
    return int(token.value)


def token_elevation_from_handle(token: int) -> bool | None:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.GetTokenInformation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    advapi32.GetTokenInformation.restype = ctypes.c_bool
    elevation = TOKEN_ELEVATION()
    needed = ctypes.c_uint32()
    ok = advapi32.GetTokenInformation(
        ctypes.c_void_p(token),
        TOKEN_ELEVATION_CLASS,
        ctypes.byref(elevation),
        ctypes.sizeof(elevation),
        ctypes.byref(needed),
    )
    if not ok:
        return None
    return bool(elevation.TokenIsElevated)


def current_process_token() -> int | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return open_process_token(int(kernel32.GetCurrentProcess()))


def process_token(pid: int) -> int | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None
    try:
        return open_process_token(int(handle))
    finally:
        kernel32.CloseHandle(handle)


def close_token(token: int | None) -> None:
    if token is None:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle(ctypes.c_void_p(token))


def debug_privilege_enabled(token: int | None) -> bool | None:
    if token is None:
        return None
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.LookupPrivilegeValueW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.POINTER(LUID)]
    advapi32.LookupPrivilegeValueW.restype = ctypes.c_bool
    advapi32.PrivilegeCheck.argtypes = [ctypes.c_void_p, ctypes.POINTER(PRIVILEGE_SET), ctypes.POINTER(ctypes.c_bool)]
    advapi32.PrivilegeCheck.restype = ctypes.c_bool
    luid = LUID()
    if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
        return None
    privilege_set = PRIVILEGE_SET()
    privilege_set.PrivilegeCount = 1
    privilege_set.Control = 1
    privilege_set.Privilege[0].Luid = luid
    privilege_set.Privilege[0].Attributes = SE_PRIVILEGE_ENABLED
    result = ctypes.c_bool(False)
    if not advapi32.PrivilegeCheck(ctypes.c_void_p(token), ctypes.byref(privilege_set), ctypes.byref(result)):
        return None
    return bool(result.value)


def token_probe(pid: int | None) -> dict[str, Any]:
    result: dict[str, Any] = {"elevated": None, "seDebugPrivilegeEnabled": None}
    if os.name != "nt":
        result["error"] = "non-windows"
        return result
    token = current_process_token() if pid is None else process_token(pid)
    if token is None:
        result["error"] = "open-token-failed"
        return result
    try:
        result["elevated"] = token_elevation_from_handle(token)
        if pid is None:
            result["seDebugPrivilegeEnabled"] = debug_privilege_enabled(token)
    finally:
        close_token(token)
    return result


def x64dbg_install_probe(explicit_path: Path | None = None) -> dict[str, Any]:
    x64dbg_path = find_x64dbg_path(explicit_path)
    paths = plugin_paths_for_x64dbg(x64dbg_path)
    result: dict[str, Any] = {
        "x64dbgPath": str(x64dbg_path) if x64dbg_path else None,
        "x64dbgFound": x64dbg_path is not None,
        "pluginPath": paths["plugin"],
        "pluginFound": bool(paths["plugin"] and Path(paths["plugin"]).is_file()),
        "libzmqPath": paths["libzmq"],
        "alternateLibzmqPath": paths.get("alternateLibzmq"),
        "libzmqFound": bool(
            (paths["libzmq"] and Path(paths["libzmq"]).is_file())
            or (paths.get("alternateLibzmq") and Path(paths["alternateLibzmq"]).is_file())
        ),
        "pythonPackageFound": False,
        "pythonPackagePath": None,
        "activeSessions": [],
        "errors": [],
    }
    try:
        package = importlib.import_module("x64dbg_automate")
        result["pythonPackageFound"] = True
        result["pythonPackagePath"] = getattr(package, "__file__", None)
        client_class = getattr(package, "X64DbgClient")
        result["activeSessions"] = [
            {"pid": getattr(session, "pid", None), "reqRepPort": getattr(session, "sess_req_rep_port", None)}
            for session in client_class.list_sessions()
        ]
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(error_record("x64dbg_automate-import-or-list-sessions", exc))
    return result


def x64dbg_launch_self_check(x64dbg_path: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "requested": True,
        "status": "not-run",
        "sessionPid": None,
        "debuggerVersion": None,
        "terminated": False,
        "windowManagement": {},
        "errors": [],
        "warnings": [],
    }
    if not x64dbg_path:
        result["status"] = "failed"
        result["errors"].append({"stage": "preflight", "type": "ValueError", "message": "x64dbg path missing"})
        return result
    client = None
    try:
        from x64dbg_automate import X64DbgClient  # type: ignore

        from .x64dbg_live_access_capture import install_minimized_x64dbg_launch

        launch_summary = {"warnings": result["warnings"], "x64dbgWindowManagement": {}}
        install_minimized_x64dbg_launch(X64DbgClient, launch_summary)
        result["windowManagement"] = launch_summary["x64dbgWindowManagement"]
        client = X64DbgClient(x64dbg_path=x64dbg_path)
        result["sessionPid"] = client.start_session()
        try:
            result["debuggerVersion"] = str(client.get_debugger_version())
        except Exception as exc:  # noqa: BLE001
            result["warnings"].append(f"debugger-version-query-failed:{type(exc).__name__}:{exc}")
        result["status"] = "passed"
    except Exception as exc:  # noqa: BLE001
        result["status"] = "failed"
        result["errors"].append(error_record("x64dbg-launch-self-check", exc))
    finally:
        if client is not None:
            try:
                client.terminate_session()
                result["terminated"] = True
            except Exception as exc:  # noqa: BLE001
                result["warnings"].append(f"terminate-session-failed:{type(exc).__name__}:{exc}")
    return result


def access_checks(pid: int, *, include_high_access_check: bool) -> list[dict[str, Any]]:
    checks = [
        ("query-limited", PROCESS_QUERY_LIMITED_INFORMATION),
        ("vm-read-handle-only", PROCESS_VM_READ),
        ("suspend-resume-handle-only", PROCESS_SUSPEND_RESUME),
    ]
    if include_high_access_check:
        checks.append(("all-access-handle-only", PROCESS_ALL_ACCESS))
    return [open_process_access_probe(pid, access, label) for label, access in checks]


def evaluate_probe(summary: dict[str, Any], *, require_debug_access: bool) -> None:
    blockers = summary["blockers"]
    warnings = summary["warnings"]
    install = summary["x64dbgInstall"]
    if not install["x64dbgFound"]:
        blockers.append("x64dbg-exe-not-found")
    if not install["pluginFound"]:
        blockers.append("x64dbg-automate-plugin-not-found")
    if not install["libzmqFound"]:
        blockers.append("x64dbg-libzmq-not-found")
    if not install["pythonPackageFound"]:
        blockers.append("x64dbg-automate-python-package-not-found")
    if install.get("activeSessions"):
        warnings.append(f"x64dbg-active-sessions-detected:{len(install['activeSessions'])}")
    launch_self_check = summary.get("x64dbgLaunchSelfCheck") or {}
    if launch_self_check.get("requested") and launch_self_check.get("status") == "failed":
        blockers.append("x64dbg-automation-launch-self-check-failed")

    current_token = summary["currentProcessToken"]
    target_token = summary["targetToken"]
    if target_token.get("elevated") is True and current_token.get("elevated") is False:
        message = "target-elevated-but-current-process-not-elevated"
        if require_debug_access:
            blockers.append(message)
        else:
            warnings.append(message)
    if current_token.get("seDebugPrivilegeEnabled") is False:
        warnings.append("current-process-SeDebugPrivilege-not-enabled")

    for check in summary["targetAccessChecks"]:
        if check["label"] == "query-limited" and not check["ok"]:
            blockers.append("target-query-limited-open-failed")
        if require_debug_access and check["label"] == "all-access-handle-only" and not check["ok"]:
            blockers.append("target-all-access-open-failed")

    summary["status"] = "blocked" if blockers else "passed"


def markdown_summary(summary: dict[str, Any]) -> str:
    selected = summary.get("selectedTarget") or {}
    lines = [
        "# x64dbg attach environment probe",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- x64dbg launched: `{str(summary['safety']['x64dbgLaunched']).lower()}`",
        f"- live attach started: `{str(summary['safety']['x64dbgLiveAttachStarted']).lower()}`",
        "",
        "## Selected target",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| PID | `{selected.get('pid')}` |",
        f"| HWND | `{selected.get('hwndHex')}` |",
        f"| Responding | `{selected.get('responding')}` |",
        f"| Start UTC | `{selected.get('startTimeUtc')}` |",
        f"| Module base | `{selected.get('moduleBaseAddressHex')}` |",
        "",
        "## Access checks",
        "",
        "| Check | Access | OK | Error |",
        "|---|---:|---:|---|",
    ]
    for check in summary.get("targetAccessChecks") or []:
        lines.append(
            f"| `{check.get('label')}` | `{check.get('access')}` | `{check.get('ok')}` | "
            f"`{check.get('errorCode')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    lines.extend(["", "## Safety", ""])
    if summary.get("safety", {}).get("x64dbgLaunched"):
        lines.extend(
            [
                "This probe launched x64dbg minimized without a debuggee, verified automation",
                "connectivity, and terminated that debugger session. It did not attach to RIFT,",
                "set breakpoints, send input, or read/write process memory bytes.",
            ]
        )
    else:
        lines.extend(
            [
                "This probe does not launch x64dbg, attach to RIFT, set breakpoints, send input,",
                "or read/write process memory bytes.",
            ]
        )
    lines.extend(
        [
            "Access probes only open and close process handles to identify likely attach",
            "blockers before another live debugger attempt.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="No-attach x64dbg environment probe for RIFT attach readiness.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--x64dbg-path", type=Path, default=None)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--target-pid", type=int, default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--expected-start-time-utc", default=None)
    parser.add_argument("--start-time-tolerance-seconds", type=float, default=1.0)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--require-exact-target", action="store_true")
    parser.add_argument("--require-no-debugger-process", action="store_true")
    parser.add_argument("--include-high-access-check", action="store_true")
    parser.add_argument("--require-debug-access", action="store_true")
    parser.add_argument(
        "--allow-x64dbg-launch-self-check",
        action="store_true",
        help="Launch x64dbg minimized without a debuggee, verify automation connectivity, then terminate it.",
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"x64dbg-attach-environment-probe-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_summary(args: argparse.Namespace, repo_root: Path, run_dir: Path) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if args.self_test:
        candidates = [
            {
                "processName": args.process_name,
                "pid": args.target_pid or 12345,
                "hwndHex": normalize_hwnd(args.target_hwnd) or "0xABCDEF",
                "responding": True,
                "startTimeUtc": args.expected_start_time_utc or "2026-05-13T00:00:00.000000Z",
                "moduleBaseAddressHex": normalize_hwnd(args.expected_module_base) or "0x7FF700000000",
            }
        ]
        debugger_processes: list[dict[str, Any]] = []
        selected = candidates[0]
        warnings.append("self-test only; no live process inspection, x64dbg launch, attach, memory read, or input")
    else:
        candidates = enumerate_window_targets(process_name=args.process_name, title_contains=args.title_contains)
        debugger_processes = enumerate_debugger_processes()
        selected, choose_blockers, choose_warnings = choose_target(
            candidates,
            target_pid=args.target_pid,
            target_hwnd=args.target_hwnd,
        )
        blockers.extend(choose_blockers)
        warnings.extend(choose_warnings)

    if args.require_exact_target:
        if args.target_pid is None:
            blockers.append("exact-target-required-missing-target-pid")
        if not args.target_hwnd:
            blockers.append("exact-target-required-missing-target-hwnd")

    if selected is not None and args.expected_start_time_utc:
        delta = start_time_delta_seconds(selected.get("startTimeUtc"), args.expected_start_time_utc)
        if delta is None or delta > args.start_time_tolerance_seconds:
            blockers.append(f"process-start-time-mismatch:deltaSeconds={delta}")
    if selected is not None and args.expected_module_base:
        actual_module_base = normalize_hwnd(selected.get("moduleBaseAddressHex") or selected.get("moduleBaseAddress"))
        expected_module_base = normalize_hwnd(args.expected_module_base)
        if actual_module_base != expected_module_base:
            blockers.append(f"module-base-mismatch:actual={actual_module_base};expected={expected_module_base}")

    if debugger_processes:
        names = ",".join(f"{item.get('processName')}:{item.get('pid')}" for item in debugger_processes)
        if args.require_no_debugger_process:
            blockers.append(f"debugger-process-detected:{names}")
        else:
            warnings.append(f"debugger-process-detected:{names}")

    target_pid = int(selected["pid"]) if selected is not None and selected.get("pid") is not None else None
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-attach-environment-probe",
        "generatedAtUtc": utc_iso(),
        "status": "blocked",
        "repoRoot": str(repo_root),
        "inputs": {
            "targetPid": args.target_pid,
            "targetHwnd": normalize_hwnd(args.target_hwnd),
            "expectedStartTimeUtc": args.expected_start_time_utc,
            "expectedModuleBase": normalize_hwnd(args.expected_module_base),
            "includeHighAccessCheck": bool(args.include_high_access_check),
            "requireDebugAccess": bool(args.require_debug_access),
            "allowX64dbgLaunchSelfCheck": bool(args.allow_x64dbg_launch_self_check),
            "selfTest": bool(args.self_test),
        },
        "selectedTarget": selected,
        "debuggerProcesses": debugger_processes,
        "x64dbgInstall": x64dbg_install_probe(args.x64dbg_path),
        "x64dbgLaunchSelfCheck": {"requested": False, "status": "not-run"}
        if args.self_test or not args.allow_x64dbg_launch_self_check
        else None,
        "currentProcessToken": {"elevated": None, "seDebugPrivilegeEnabled": None}
        if args.self_test
        else token_probe(None),
        "targetToken": {"elevated": None, "seDebugPrivilegeEnabled": None}
        if args.self_test or target_pid is None
        else token_probe(target_pid),
        "targetAccessChecks": []
        if args.self_test or target_pid is None
        else access_checks(target_pid, include_high_access_check=args.include_high_access_check),
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "x64dbgLaunched": False,
            "x64dbgLiveAttachStarted": False,
            "x64dbgCommandsExecuted": False,
            "processAttachOrMemoryReadStarted": False,
            "targetMemoryWritten": False,
            "liveAttachPolicy": live_attach_policy(),
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "next": {
            "recommendedAction": "Resolve blockers before repeating a live x64dbg attach attempt.",
        },
    }
    if summary["x64dbgLaunchSelfCheck"] is None:
        summary["x64dbgLaunchSelfCheck"] = x64dbg_launch_self_check(summary["x64dbgInstall"].get("x64dbgPath"))
        summary["safety"]["x64dbgLaunched"] = True
        summary["safety"]["x64dbgCommandsExecuted"] = True
    evaluate_probe(summary, require_debug_access=bool(args.require_debug_access))
    if summary["status"] == "passed":
        summary["next"]["recommendedAction"] = (
            "If static-chain provenance is still required, perform one bounded minimized x64dbg attach/capture attempt."
        )
    return summary


def write_outputs(summary: dict[str, Any]) -> None:
    write_json(Path(summary["artifacts"]["summaryJson"]), summary)
    write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = choose_run_dir(repo_root, args.output_root)
    summary = build_summary(args, repo_root, run_dir)
    write_outputs(summary)
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
        if summary["blockers"]:
            print("blockers=" + ";".join(summary["blockers"]))
        if summary["warnings"]:
            print("warnings=" + ";".join(summary["warnings"]))
    return 2 if summary["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
