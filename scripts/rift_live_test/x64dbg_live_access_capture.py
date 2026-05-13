from __future__ import annotations

import argparse
import json
import math
import struct
import time
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


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_int(value: str) -> int:
    return int(value, 0)


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
    if args.max_go_attempts < 1 and args.capture_mode in {"hardware-read", "resume-only"}:
        blockers.append(f"{args.capture_mode}-capture-requires-one-go-attempt")
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
        from x64dbg_automate.models import HardwareBreakpointType  # type: ignore

        client = X64DbgClient(x64dbg_path=str(args.x64dbg_path))
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
                event = client.wait_for_debug_event(EventType.EVENT_BREAKPOINT, timeout=int(args.breakpoint_timeout_seconds))
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
    parser.add_argument("--capture-mode", choices=("stop-context", "hardware-read", "resume-only"), default="stop-context")
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
