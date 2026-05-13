from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import time
from collections.abc import Mapping, Sequence
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
DEFAULT_X64DBG_PATH = Path(r"C:\RIFT MODDING\Tools\x64dbg\release\x64\x64dbg.exe")
DEFAULT_HARMLESS_EXE = Path(r"C:\Windows\System32\winver.exe")
MAX_MEMORY_READ_BYTES = 4096
MAX_TOTAL_MEMORY_READ_BYTES = 16384

BLOCKED_OPERATIONS: tuple[str, ...] = (
    "write_memory",
    "memset",
    "virt_alloc",
    "virt_protect",
    "virt_free",
    "assemble_at",
    "set_reg",
    "set_breakpoint",
    "set_hardware_breakpoint",
    "set_memory_breakpoint",
    "clear_breakpoint",
    "toggle_breakpoint",
    "toggle_hardware_breakpoint",
    "toggle_memory_breakpoint",
    "go",
    "pause",
    "stepi",
    "stepo",
    "skip",
    "ret",
    "trace_into",
    "trace_over",
    "thread_create",
    "thread_terminate",
    "thread_pause",
    "thread_resume",
    "switch_thread",
    "cmd_sync",
    "start_session_attach",
    "attach",
    "hide_debugger_peb",
)

READ_ONLY_OPERATIONS: tuple[str, ...] = (
    "get_reg",
    "get_regs",
    "memmap",
    "virt_query",
    "check_valid_read_ptr",
    "read_memory",
    "read_word",
    "read_dword",
    "read_qword",
    "disassemble_at",
    "debugee_pid",
    "get_debugger_pid",
    "get_debugger_version",
    "is_debugging",
    "is_running",
    "detach_session",
    "terminate_session_if_helper_owned",
)

SOURCE_LINKS: tuple[str, ...] = (
    "https://x64.ooo/posts/2026-02-12-cooking-with-x64dbg-and-mcp/",
    "https://dariushoule.github.io/x64dbg-automate-pyclient/",
    "https://dariushoule.github.io/x64dbg-automate-pyclient/quickstart/",
    "https://dariushoule.github.io/x64dbg-automate-pyclient/mcp-server/",
    "https://dariushoule.github.io/x64dbg-automate-pyclient/api/debug-control/",
    "https://dariushoule.github.io/x64dbg-automate-pyclient/api/memory-control/",
    "https://dariushoule.github.io/x64dbg-automate-pyclient/api/registers-expressions/",
    "https://dariushoule.github.io/x64dbg-automate-pyclient/api/assembler-disassembler/",
)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, bytes):
        return value.hex()
    return value


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{value:X}"


def parse_int(value: str) -> int:
    return int(value, 0)


def parse_memory_read_spec(spec: str) -> dict[str, Any]:
    parts = spec.split(":")
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError("memory read must be ADDRESS:SIZE[:LABEL]")
    try:
        address = parse_int(parts[0])
        size = int(parts[1], 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid memory read spec {spec!r}: {exc}") from exc
    if address < 0:
        raise argparse.ArgumentTypeError("memory read address must be non-negative")
    if size <= 0 or size > MAX_MEMORY_READ_BYTES:
        raise argparse.ArgumentTypeError(f"memory read size must be 1..{MAX_MEMORY_READ_BYTES}")
    label = parts[2] if len(parts) == 3 and parts[2] else int_hex(address)
    return {"address": address, "size": size, "label": label}


def make_safety(
    *,
    offline_only: bool,
    helper_owned_session: bool = False,
    process_read_started: bool = False,
    max_live_attach_seconds: int = DEFAULT_MAX_LIVE_ATTACH_SECONDS,
    unresponsive_abort_seconds: int = DEFAULT_UNRESPONSIVE_ABORT_SECONDS,
    max_go_attempts: int = DEFAULT_MAX_GO_ATTEMPTS,
) -> dict[str, Any]:
    return {
        "offlineOnly": offline_only,
        "helperOwnedSession": helper_owned_session,
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "githubConnectorWrites": False,
        "providerWrites": False,
        "codexMcpConfigured": False,
        "codexMcpServerStarted": False,
        "x64dbgLiveAttachStarted": False,
        "processAttachOrMemoryReadStarted": process_read_started,
        "movementAllowed": False,
        "writeClassOperationsBlocked": True,
        "blockedOperations": list(BLOCKED_OPERATIONS),
        "readOnlyOperations": list(READ_ONLY_OPERATIONS),
        "liveAttachPolicy": live_attach_policy(
            max_live_attach_seconds=max_live_attach_seconds,
            unresponsive_abort_seconds=unresponsive_abort_seconds,
            max_go_attempts=max_go_attempts,
        ),
    }


def flatten_scalars(value: Any, prefix: str = "", limit: int = 2000) -> dict[str, Any]:
    result: dict[str, Any] = {}

    def visit(node: Any, path: str) -> None:
        if len(result) >= limit:
            return
        if isinstance(node, Mapping):
            for key in sorted(node.keys(), key=str):
                child = node[key]
                child_path = f"{path}.{key}" if path else str(key)
                visit(child, child_path)
            return
        if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for index, child in enumerate(node):
                child_path = f"{path}[{index}]"
                visit(child, child_path)
            return
        if isinstance(node, bytes):
            result[path] = node.hex()
            return
        if node is None or isinstance(node, (bool, int, float, str)):
            result[path] = node

    visit(value, prefix)
    return result


def snapshot_identity(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    process = snapshot.get("process") if isinstance(snapshot.get("process"), Mapping) else {}
    x64dbg = snapshot.get("x64dbg") if isinstance(snapshot.get("x64dbg"), Mapping) else {}
    return {
        "source": snapshot.get("source"),
        "processName": process.get("name"),
        "processId": process.get("pid"),
        "hwnd": process.get("hwnd"),
        "processStartTimeUtc": process.get("startTimeUtc"),
        "debuggerPid": x64dbg.get("debuggerPid"),
        "sessionMode": x64dbg.get("sessionMode"),
    }


def collected_target_identity_blockers(snapshot: Mapping[str, Any], args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    process = snapshot.get("process") if isinstance(snapshot.get("process"), Mapping) else {}
    x64dbg = snapshot.get("x64dbg") if isinstance(snapshot.get("x64dbg"), Mapping) else {}

    debuggee_pid = process.get("debuggeePid")
    if args.target_pid is not None and debuggee_pid is not None and int(debuggee_pid) != int(args.target_pid):
        blockers.append(f"debuggee-pid-mismatch:{debuggee_pid}!={args.target_pid}")

    debugger_pid = x64dbg.get("debuggerPid")
    if args.connect_session is not None and debugger_pid is not None and int(debugger_pid) != int(args.connect_session):
        blockers.append(f"debugger-pid-mismatch:{debugger_pid}!={args.connect_session}")

    hwnd_value = process.get("hwnd")
    hwnd = normalize_hwnd(str(hwnd_value) if hwnd_value is not None else None)
    expected_hwnd = normalize_hwnd(args.target_hwnd)
    if expected_hwnd and hwnd and hwnd != expected_hwnd:
        blockers.append(f"target-hwnd-mismatch:{hwnd}!={expected_hwnd}")

    process_name = process.get("name")
    if args.process_name and process_name and str(process_name).lower() != str(args.process_name).lower():
        blockers.append(f"process-name-mismatch:{process_name}!={args.process_name}")

    start_time = process.get("startTimeUtc")
    if args.process_start_time_utc and start_time and str(start_time) != str(args.process_start_time_utc):
        blockers.append(f"process-start-time-mismatch:{start_time}!={args.process_start_time_utc}")

    return blockers


def compare_scalar_maps(before: Mapping[str, Any], after: Mapping[str, Any], *, max_changes: int = 200) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    keys = sorted(set(before.keys()) | set(after.keys()))
    for key in keys:
        old = before.get(key, "<missing>")
        new = after.get(key, "<missing>")
        if old != new:
            changes.append({"path": key, "before": old, "after": new})
            if len(changes) >= max_changes:
                break
    return changes


def memory_read_key(read: Mapping[str, Any]) -> str:
    label = read.get("label")
    address = read.get("addressHex") or read.get("address")
    size = read.get("size")
    return f"{label}|{address}|{size}"


def diff_snapshots(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_registers = flatten_scalars(before.get("registers", {}), "registers")
    after_registers = flatten_scalars(after.get("registers", {}), "registers")
    register_changes = compare_scalar_maps(before_registers, after_registers)

    before_reads = {
        memory_read_key(read): read
        for read in before.get("memoryReads", [])
        if isinstance(read, Mapping)
    }
    after_reads = {
        memory_read_key(read): read
        for read in after.get("memoryReads", [])
        if isinstance(read, Mapping)
    }
    memory_read_changes: list[dict[str, Any]] = []
    for key in sorted(set(before_reads) | set(after_reads)):
        old = before_reads.get(key)
        new = after_reads.get(key)
        if old is None or new is None:
            memory_read_changes.append({"key": key, "change": "added" if old is None else "removed"})
        elif old.get("sha256") != new.get("sha256"):
            memory_read_changes.append(
                {
                    "key": key,
                    "change": "sha256-changed",
                    "beforeSha256": old.get("sha256"),
                    "afterSha256": new.get("sha256"),
                }
            )

    before_disasm = flatten_scalars(before.get("disassembly", []), "disassembly")
    after_disasm = flatten_scalars(after.get("disassembly", []), "disassembly")
    disassembly_changes = compare_scalar_maps(before_disasm, after_disasm)

    before_pages = before.get("memoryMap", [])
    after_pages = after.get("memoryMap", [])
    memory_map_changed = before_pages != after_pages

    changed_sections: list[str] = []
    if register_changes:
        changed_sections.append("registers")
    if memory_read_changes:
        changed_sections.append("memoryReads")
    if disassembly_changes:
        changed_sections.append("disassembly")
    if memory_map_changed:
        changed_sections.append("memoryMap")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-snapshot-diff",
        "generatedAtUtc": utc_iso(),
        "beforeIdentity": snapshot_identity(before),
        "afterIdentity": snapshot_identity(after),
        "counts": {
            "registerChanges": len(register_changes),
            "memoryReadChanges": len(memory_read_changes),
            "disassemblyChanges": len(disassembly_changes),
            "memoryMapPagesBefore": len(before_pages) if isinstance(before_pages, list) else None,
            "memoryMapPagesAfter": len(after_pages) if isinstance(after_pages, list) else None,
            "candidateCount": len(register_changes) + len(memory_read_changes) + len(disassembly_changes) + (1 if memory_map_changed else 0),
        },
        "changedSections": changed_sections,
        "registerChanges": register_changes,
        "memoryReadChanges": memory_read_changes,
        "disassemblyChanges": disassembly_changes,
        "memoryMapChanged": memory_map_changed,
    }


def build_synthetic_snapshots() -> tuple[dict[str, Any], dict[str, Any]]:
    base = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-read-only-snapshot",
        "source": "synthetic-self-test",
        "capturedAtUtc": utc_iso(),
        "process": {
            "name": "synthetic.exe",
            "pid": 1000,
            "hwnd": "0x0",
            "startTimeUtc": "2026-05-12T00:00:00Z",
        },
        "x64dbg": {
            "sessionMode": "synthetic",
            "packageVersion": None,
            "debuggerPid": None,
        },
        "safety": make_safety(offline_only=True),
        "memoryMap": [
            {"baseAddressHex": "0x1000", "regionSize": 4096, "protect": 32, "state": 4096, "type": 131072, "info": "synthetic"}
        ],
        "disassembly": [
            {"address": 4096, "addressHex": "0x1000", "instruction": "mov eax, 1", "size": 5},
            {"address": 4101, "addressHex": "0x1005", "instruction": "ret", "size": 1},
        ],
    }
    before = json.loads(json.dumps(base))
    before["label"] = "before"
    before["registers"] = {"context": {"rip": 4096, "rax": 1, "rbx": 2}}
    before["memoryReads"] = [
        {
            "label": "synthetic-code",
            "address": 4096,
            "addressHex": "0x1000",
            "size": 8,
            "sha256": hashlib.sha256(b"before!!").hexdigest(),
            "hexPreview": b"before!!".hex(),
        }
    ]
    after = json.loads(json.dumps(base))
    after["label"] = "after"
    after["registers"] = {"context": {"rip": 4096, "rax": 2, "rbx": 2}}
    after["memoryReads"] = [
        {
            "label": "synthetic-code",
            "address": 4096,
            "addressHex": "0x1000",
            "size": 8,
            "sha256": hashlib.sha256(b"after!!!").hexdigest(),
            "hexPreview": b"after!!!".hex(),
        }
    ]
    return before, after


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def package_version() -> str | None:
    try:
        return importlib.metadata.version("x64dbg_automate")
    except importlib.metadata.PackageNotFoundError:
        return None


def assert_live_target_metadata(args: argparse.Namespace, blockers: list[str]) -> None:
    if not args.process_name:
        blockers.append("missing-process-name")
    if args.target_pid is None:
        blockers.append("missing-target-pid")
    if not args.target_hwnd:
        blockers.append("missing-target-hwnd")
    if not args.process_start_time_utc:
        blockers.append("missing-process-start-time-utc")
    if str(args.process_name or "").lower() == "rift_x64" and not args.allow_live_debugger:
        blockers.append("rift-live-debugger-not-authorized-current-turn")


def normalize_hwnd(hwnd: str | None) -> str | None:
    if not hwnd:
        return None
    text = hwnd.strip()
    try:
        return f"0x{int(text, 0):X}"
    except ValueError:
        return text


def collect_snapshot(
    client: Any,
    *,
    label: str,
    process_name: str,
    target_pid: int | None,
    target_hwnd: str | None,
    process_start_time_utc: str | None,
    session_mode: str,
    x64dbg_path: Path,
    max_memory_map_pages: int,
    disassemble_count: int,
    read_code_bytes: int,
    memory_read_specs: list[dict[str, Any]],
    helper_owned_session: bool,
    max_live_attach_seconds: int,
    unresponsive_abort_seconds: int,
    max_go_attempts: int,
) -> dict[str, Any]:
    debugger_pid: int | None = None
    debugee_pid: int | None = None
    try:
        debugger_pid = int(client.get_debugger_pid())
    except Exception:
        debugger_pid = None
    try:
        debugee_pid = client.debugee_pid()
    except Exception:
        debugee_pid = None

    registers: Any = {}
    instruction_pointer: int | None = None
    errors: list[str] = []

    try:
        registers = to_jsonable(client.get_regs())
    except Exception as exc:
        errors.append(f"get_regs:{type(exc).__name__}:{exc}")
    try:
        instruction_pointer = int(client.get_reg("cip"))
    except Exception as exc:
        errors.append(f"get_reg_cip:{type(exc).__name__}:{exc}")

    pages: list[dict[str, Any]] = []
    try:
        raw_pages = client.memmap()
        for page in raw_pages[:max_memory_map_pages]:
            page_data = to_jsonable(page)
            if isinstance(page_data, dict):
                base = page_data.get("base_address")
                page_data["baseAddressHex"] = int_hex(int(base)) if isinstance(base, int) else None
                alloc = page_data.get("allocation_base")
                page_data["allocationBaseHex"] = int_hex(int(alloc)) if isinstance(alloc, int) else None
            pages.append(page_data)
    except Exception as exc:
        errors.append(f"memmap:{type(exc).__name__}:{exc}")

    disassembly: list[dict[str, Any]] = []
    if instruction_pointer is not None:
        address = instruction_pointer
        for _ in range(disassemble_count):
            try:
                instruction = client.disassemble_at(address)
            except Exception as exc:
                errors.append(f"disassemble_at:{int_hex(address)}:{type(exc).__name__}:{exc}")
                break
            if instruction is None:
                break
            instruction_data = to_jsonable(instruction)
            size = int(instruction_data.get("instr_size") or 0) if isinstance(instruction_data, dict) else 0
            disassembly.append(
                {
                    "address": address,
                    "addressHex": int_hex(address),
                    "instruction": instruction_data.get("instruction") if isinstance(instruction_data, dict) else str(instruction),
                    "size": size,
                    "raw": instruction_data,
                }
            )
            if size <= 0:
                break
            address += size

    memory_reads: list[dict[str, Any]] = []
    read_specs = list(memory_read_specs)
    if instruction_pointer is not None and read_code_bytes > 0:
        read_specs.insert(0, {"address": instruction_pointer, "size": read_code_bytes, "label": "cip-code"})
    total_requested = sum(int(spec["size"]) for spec in read_specs)
    if total_requested > MAX_TOTAL_MEMORY_READ_BYTES:
        errors.append(f"memory_reads_total_too_large:{total_requested}>{MAX_TOTAL_MEMORY_READ_BYTES}")
        read_specs = []
    for spec in read_specs:
        address = int(spec["address"])
        size = int(spec["size"])
        label = str(spec["label"])
        readable = False
        try:
            readable = bool(client.check_valid_read_ptr(address))
        except Exception as exc:
            errors.append(f"check_valid_read_ptr:{int_hex(address)}:{type(exc).__name__}:{exc}")
        if not readable:
            memory_reads.append(
                {
                    "label": label,
                    "address": address,
                    "addressHex": int_hex(address),
                    "size": size,
                    "readable": False,
                    "sha256": None,
                    "hexPreview": None,
                }
            )
            continue
        try:
            data = bytes(client.read_memory(address, size))
            memory_reads.append(
                {
                    "label": label,
                    "address": address,
                    "addressHex": int_hex(address),
                    "size": size,
                    "readable": True,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "hexPreview": data[:64].hex(),
                }
            )
        except Exception as exc:
            errors.append(f"read_memory:{int_hex(address)}:{type(exc).__name__}:{exc}")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-read-only-snapshot",
        "source": "x64dbg_automate",
        "label": label,
        "capturedAtUtc": utc_iso(),
        "process": {
            "name": process_name,
            "pid": target_pid if target_pid is not None else debugee_pid,
            "debuggeePid": debugee_pid,
            "hwnd": normalize_hwnd(target_hwnd),
            "startTimeUtc": process_start_time_utc,
        },
        "x64dbg": {
            "sessionMode": session_mode,
            "x64dbgPath": str(x64dbg_path),
            "debuggerPid": debugger_pid,
            "packageVersion": package_version(),
        },
        "instructionPointer": instruction_pointer,
        "instructionPointerHex": int_hex(instruction_pointer),
        "registers": registers,
        "memoryMap": pages,
        "disassembly": disassembly,
        "memoryReads": memory_reads,
        "errors": errors,
        "safety": make_safety(
            offline_only=False,
            helper_owned_session=helper_owned_session,
            process_read_started=True,
            max_live_attach_seconds=max_live_attach_seconds,
            unresponsive_abort_seconds=unresponsive_abort_seconds,
            max_go_attempts=max_go_attempts,
        ),
    }


def write_summary_markdown(path: Path, summary: Mapping[str, Any]) -> None:
    diff = summary.get("diff") if isinstance(summary.get("diff"), Mapping) else {}
    counts = diff.get("counts") if isinstance(diff.get("counts"), Mapping) else {}
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), Mapping) else {}
    lines = [
        "# x64dbg snapshot diff summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Mode: `{summary.get('mode')}`",
        f"- Movement allowed: `{str(summary.get('safety', {}).get('movementAllowed')).lower()}`",
        f"- Codex MCP configured: `{str(summary.get('safety', {}).get('codexMcpConfigured')).lower()}`",
        "",
        "## Diff counts",
        "",
        "| Field | Value |",
        "|---|---:|",
        f"| Register changes | `{counts.get('registerChanges', 0)}` |",
        f"| Memory read changes | `{counts.get('memoryReadChanges', 0)}` |",
        f"| Disassembly changes | `{counts.get('disassemblyChanges', 0)}` |",
        f"| Candidate count | `{counts.get('candidateCount', 0)}` |",
        "",
        "## Artifacts",
        "",
        "| Artifact | Path |",
        "|---|---|",
    ]
    for key, value in artifacts.items():
        lines.append(f"| `{key}` | `{value}` |")
    blockers = summary.get("blockers") or []
    warnings = summary.get("warnings") or []
    errors = summary.get("errors") or []
    if blockers:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{item}`" for item in blockers)
    if warnings:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{item}`" for item in warnings)
    if errors:
        lines.extend(["", "## Errors"])
        lines.extend(f"- `{item}`" for item in errors)
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This helper is candidate-evidence only. It does not authorize movement,",
            "does not configure Codex MCP, and blocks write-class x64dbg operations by default.",
        ]
    )
    write_text_atomic(path, "\n".join(lines).rstrip() + "\n")


def build_base_summary(*, mode: str, repo_root: Path, run_dir: Path, status: str = "failed") -> dict[str, Any]:
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    diff_json = run_dir / "snapshot-diff.json"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": mode,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "repoRoot": str(repo_root),
        "blockers": [],
        "warnings": [],
        "errors": [],
        "sources": list(SOURCE_LINKS),
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "diffJson": str(diff_json),
        },
        "safety": make_safety(offline_only=True),
        "next": {
            "recommendedAction": "Review diff candidates; do not promote without current-session proof.",
        },
    }


def finalize_summary(summary: dict[str, Any], run_dir: Path, *, before: dict[str, Any] | None, after: dict[str, Any] | None, diff: dict[str, Any] | None) -> None:
    if before is not None:
        before_path = run_dir / "snapshot-before.json"
        write_json(before_path, before)
        summary["artifacts"]["beforeJson"] = str(before_path)
    if after is not None:
        after_path = run_dir / "snapshot-after.json"
        write_json(after_path, after)
        summary["artifacts"]["afterJson"] = str(after_path)
    if diff is not None:
        diff_path = Path(summary["artifacts"]["diffJson"])
        write_json(diff_path, diff)
        summary["diff"] = diff
    write_json(Path(summary["artifacts"]["summaryJson"]), summary)
    write_summary_markdown(Path(summary["artifacts"]["summaryMarkdown"]), summary)


def run_self_test(repo_root: Path, run_dir: Path) -> tuple[int, dict[str, Any]]:
    before, after = build_synthetic_snapshots()
    diff = diff_snapshots(before, after)
    summary = build_base_summary(mode="self-test", repo_root=repo_root, run_dir=run_dir, status="passed")
    summary["warnings"].append("self-test only; no x64dbg session, live process, RIFT target, MCP server, or movement touched")
    summary["safety"] = make_safety(offline_only=True)
    finalize_summary(summary, run_dir, before=before, after=after, diff=diff)
    return 0, summary


def run_dry_run(repo_root: Path, run_dir: Path, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    summary = build_base_summary(mode="dry-run", repo_root=repo_root, run_dir=run_dir, status="blocked")
    summary["blockers"].append("dry-run-requested")
    summary["warnings"].append("planned only; no x64dbg session, live process, MCP server, or movement touched")
    summary["plannedInputs"] = {
        "before": str(args.before) if args.before else None,
        "after": str(args.after) if args.after else None,
        "connectSession": args.connect_session,
        "harmlessExe": str(args.harmless_exe) if args.harmless_exe else None,
        "x64dbgPath": str(args.x64dbg_path),
    }
    finalize_summary(summary, run_dir, before=None, after=None, diff=None)
    return 2, summary


def run_file_diff(repo_root: Path, run_dir: Path, before_path: Path, after_path: Path) -> tuple[int, dict[str, Any]]:
    summary = build_base_summary(mode="file-diff", repo_root=repo_root, run_dir=run_dir, status="failed")
    try:
        before = read_json_file(before_path)
        after = read_json_file(after_path)
        if not isinstance(before, dict) or not isinstance(after, dict):
            summary["status"] = "blocked"
            summary["blockers"].append("snapshots-must-be-json-objects")
            finalize_summary(summary, run_dir, before=None, after=None, diff=None)
            return 2, summary
        diff = diff_snapshots(before, after)
        summary["status"] = "passed"
        summary["inputs"] = {"beforeSnapshot": str(before_path), "afterSnapshot": str(after_path)}
        finalize_summary(summary, run_dir, before=before, after=after, diff=diff)
        return 0, summary
    except Exception as exc:
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        finalize_summary(summary, run_dir, before=None, after=None, diff=None)
        return 1, summary


def validate_harmless_exe(path: Path) -> Path:
    resolved = path.resolve()
    allowed = DEFAULT_HARMLESS_EXE.resolve()
    if os.path.normcase(str(resolved)) != os.path.normcase(str(allowed)):
        raise ValueError(f"harmless exe is not allowlisted: {resolved}; expected {allowed}")
    if not resolved.is_file():
        raise FileNotFoundError(str(resolved))
    return resolved


def run_x64dbg_collect(repo_root: Path, run_dir: Path, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    summary = build_base_summary(mode="x64dbg-collect", repo_root=repo_root, run_dir=run_dir, status="failed")
    blockers: list[str] = []
    helper_owned = False
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    diff: dict[str, Any] | None = None
    session_started_at = time.monotonic()
    is_rift_live_session = args.connect_session is not None and str(args.process_name or "").lower() == "rift_x64"
    summary["safety"] = make_safety(
        offline_only=False,
        max_live_attach_seconds=args.max_live_attach_seconds,
        unresponsive_abort_seconds=args.unresponsive_abort_seconds,
        max_go_attempts=args.max_go_attempts,
    )
    if args.connect_session is not None:
        assert_live_target_metadata(args, blockers)
    if is_rift_live_session:
        blockers.extend(
            validate_live_attach_policy(
                max_live_attach_seconds=args.max_live_attach_seconds,
                unresponsive_abort_seconds=args.unresponsive_abort_seconds,
                max_go_attempts=args.max_go_attempts,
            )
        )
    if args.harmless_exe is not None and not args.allow_harmless_exe:
        blockers.append("harmless-exe-mode-requires-allow-harmless-exe")
    if not Path(args.x64dbg_path).is_file():
        blockers.append(f"x64dbg-path-missing:{args.x64dbg_path}")
    if blockers:
        summary["status"] = "blocked"
        summary["blockers"].extend(blockers)
        finalize_summary(summary, run_dir, before=None, after=None, diff=None)
        return 2, summary

    try:
        from x64dbg_automate import X64DbgClient  # type: ignore
    except Exception as exc:
        summary["status"] = "blocked"
        summary["blockers"].append("x64dbg-automate-python-client-unavailable")
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        finalize_summary(summary, run_dir, before=None, after=None, diff=None)
        return 2, summary

    client = X64DbgClient(x64dbg_path=str(args.x64dbg_path))
    session_mode = "unknown"
    try:
        if args.connect_session is not None:
            session_mode = "connect-existing-session"
            client.attach_session(int(args.connect_session))
        else:
            harmless = validate_harmless_exe(Path(args.harmless_exe))
            session_mode = "helper-owned-harmless-exe"
            helper_owned = True
            client.start_session(str(harmless))
            process_name = harmless.name
            args.process_name = process_name
            try:
                client.wait_until_stopped(timeout=args.wait_timeout)
            except Exception:
                client.wait_cmd_ready(timeout=args.wait_timeout)

        before = collect_snapshot(
            client,
            label="before",
            process_name=args.process_name or "unknown",
            target_pid=args.target_pid,
            target_hwnd=args.target_hwnd,
            process_start_time_utc=args.process_start_time_utc,
            session_mode=session_mode,
            x64dbg_path=Path(args.x64dbg_path),
            max_memory_map_pages=args.max_memory_map_pages,
            disassemble_count=args.disassemble_count,
            read_code_bytes=args.read_code_bytes,
            memory_read_specs=args.memory_read,
            helper_owned_session=helper_owned,
            max_live_attach_seconds=args.max_live_attach_seconds,
            unresponsive_abort_seconds=args.unresponsive_abort_seconds,
            max_go_attempts=args.max_go_attempts,
        )
        identity_blockers = collected_target_identity_blockers(before, args)
        if identity_blockers:
            summary["status"] = "blocked"
            summary["blockers"].extend(identity_blockers)
            summary["warnings"].append("detaching because x64dbg target identity did not match the approved target")
            finalize_summary(summary, run_dir, before=before, after=None, diff=None)
            return 2, summary
        if is_rift_live_session and time.monotonic() - session_started_at > args.max_live_attach_seconds:
            summary["status"] = "blocked"
            summary["blockers"].append("live-attach-time-budget-exceeded-after-before-snapshot")
            summary["warnings"].append("detaching before second snapshot/diff to preserve RIFT responsiveness")
            finalize_summary(summary, run_dir, before=before, after=None, diff=None)
            return 2, summary
        after = collect_snapshot(
            client,
            label="after",
            process_name=args.process_name or "unknown",
            target_pid=args.target_pid,
            target_hwnd=args.target_hwnd,
            process_start_time_utc=args.process_start_time_utc,
            session_mode=session_mode,
            x64dbg_path=Path(args.x64dbg_path),
            max_memory_map_pages=args.max_memory_map_pages,
            disassemble_count=args.disassemble_count,
            read_code_bytes=args.read_code_bytes,
            memory_read_specs=args.memory_read,
            helper_owned_session=helper_owned,
            max_live_attach_seconds=args.max_live_attach_seconds,
            unresponsive_abort_seconds=args.unresponsive_abort_seconds,
            max_go_attempts=args.max_go_attempts,
        )
        identity_blockers = collected_target_identity_blockers(after, args)
        if identity_blockers:
            summary["status"] = "blocked"
            summary["blockers"].extend(identity_blockers)
            summary["warnings"].append("detaching because x64dbg target identity changed during read-only capture")
            finalize_summary(summary, run_dir, before=before, after=after, diff=None)
            return 2, summary
        diff = diff_snapshots(before, after)
        elapsed_seconds = time.monotonic() - session_started_at
        if is_rift_live_session and elapsed_seconds > args.max_live_attach_seconds:
            summary["status"] = "blocked"
            summary["blockers"].append("live-attach-time-budget-exceeded-before-detach")
            code = 2
        else:
            summary["status"] = "passed"
            code = 0
        summary["inputs"] = {
            "connectSession": args.connect_session,
            "harmlessExe": str(args.harmless_exe) if args.harmless_exe else None,
            "x64dbgPath": str(args.x64dbg_path),
        }
        summary["timing"] = {
            "elapsedSecondsBeforeDetach": round(elapsed_seconds, 3),
            "maxLiveAttachSeconds": args.max_live_attach_seconds,
        }
        summary["safety"] = make_safety(
            offline_only=False,
            helper_owned_session=helper_owned,
            process_read_started=True,
            max_live_attach_seconds=args.max_live_attach_seconds,
            unresponsive_abort_seconds=args.unresponsive_abort_seconds,
            max_go_attempts=args.max_go_attempts,
        )
        summary["warnings"].append("candidate-only x64dbg read-only snapshot; not movement proof")
        finalize_summary(summary, run_dir, before=before, after=after, diff=diff)
        return code, summary
    except Exception as exc:
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        finalize_summary(summary, run_dir, before=None, after=None, diff=None)
        return 1, summary
    finally:
        try:
            if helper_owned:
                client.terminate_session()
            else:
                client.detach_session()
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only x64dbg snapshot/diff helper with RiftReader safety gates.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--before", type=Path, default=None, help="Existing before snapshot JSON for offline diff.")
    parser.add_argument("--after", type=Path, default=None, help="Existing after snapshot JSON for offline diff.")
    parser.add_argument("--self-test", action="store_true", help="Run synthetic no-live self-test and write artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Write planned blocked summary without touching x64dbg.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON result to stdout.")
    parser.add_argument("--x64dbg-path", type=Path, default=Path(os.environ.get("X64DBG_PATH", DEFAULT_X64DBG_PATH)))
    parser.add_argument("--connect-session", type=int, default=None, help="Connect to an existing x64dbg debugger PID.")
    parser.add_argument("--harmless-exe", type=Path, default=None, help="Launch allowlisted harmless exe under helper-owned x64dbg.")
    parser.add_argument("--allow-harmless-exe", action="store_true", help="Required with --harmless-exe.")
    parser.add_argument("--allow-live-debugger", action="store_true", help="Required for any RIFT live-debugger connection.")
    parser.add_argument("--process-name", default=None)
    parser.add_argument("--target-pid", type=int, default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--process-start-time-utc", default=None)
    parser.add_argument("--max-memory-map-pages", type=int, default=128)
    parser.add_argument("--disassemble-count", type=int, default=16)
    parser.add_argument("--read-code-bytes", type=int, default=64)
    parser.add_argument("--memory-read", action="append", type=parse_memory_read_spec, default=[], metavar="ADDRESS:SIZE[:LABEL]")
    parser.add_argument("--wait-timeout", type=int, default=10)
    parser.add_argument("--max-live-attach-seconds", type=int, default=DEFAULT_MAX_LIVE_ATTACH_SECONDS)
    parser.add_argument("--unresponsive-abort-seconds", type=int, default=DEFAULT_UNRESPONSIVE_ABORT_SECONDS)
    parser.add_argument("--max-go-attempts", type=int, default=DEFAULT_MAX_GO_ATTEMPTS)
    return parser


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    if output_root is not None:
        run_dir = output_root.resolve()
    else:
        run_dir = repo_root / "scripts" / "captures" / f"x64dbg-snapshot-diff-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def validate_args(args: argparse.Namespace) -> list[str]:
    modes = [
        bool(args.self_test),
        bool(args.dry_run),
        bool(args.before or args.after),
        args.connect_session is not None,
        args.harmless_exe is not None,
    ]
    if sum(1 for item in modes if item) != 1:
        return ["choose-exactly-one-mode:self-test,dry-run,before-after,connect-session,harmless-exe"]
    if bool(args.before) != bool(args.after):
        return ["before-and-after-required-together"]
    if args.disassemble_count < 0 or args.disassemble_count > 100:
        return ["disassemble-count-out-of-range"]
    if args.read_code_bytes < 0 or args.read_code_bytes > MAX_MEMORY_READ_BYTES:
        return ["read-code-bytes-out-of-range"]
    if args.max_memory_map_pages < 0:
        return ["max-memory-map-pages-out-of-range"]
    if args.connect_session is not None and str(args.process_name or "").lower() == "rift_x64":
        policy_blockers = validate_live_attach_policy(
            max_live_attach_seconds=args.max_live_attach_seconds,
            unresponsive_abort_seconds=args.unresponsive_abort_seconds,
            max_go_attempts=args.max_go_attempts,
        )
        if policy_blockers:
            return policy_blockers
    return []


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = choose_run_dir(repo_root, args.output_root)

    validation_blockers = validate_args(args)
    if validation_blockers:
        summary = build_base_summary(mode="argument-validation", repo_root=repo_root, run_dir=run_dir, status="blocked")
        summary["blockers"].extend(validation_blockers)
        finalize_summary(summary, run_dir, before=None, after=None, diff=None)
        if args.json:
            print(json.dumps({"status": summary["status"], "summaryJson": summary["artifacts"]["summaryJson"]}, separators=(",", ":")))
        else:
            print(f"status={summary['status']}")
            print(f"summaryJson={summary['artifacts']['summaryJson']}")
        return 2

    if args.self_test:
        code, summary = run_self_test(repo_root, run_dir)
    elif args.dry_run:
        code, summary = run_dry_run(repo_root, run_dir, args)
    elif args.before and args.after:
        code, summary = run_file_diff(repo_root, run_dir, args.before, args.after)
    else:
        code, summary = run_x64dbg_collect(repo_root, run_dir, args)

    if args.json:
        print(
            json.dumps(
                {
                    "status": summary.get("status"),
                    "summaryJson": summary.get("artifacts", {}).get("summaryJson"),
                    "summaryMarkdown": summary.get("artifacts", {}).get("summaryMarkdown"),
                    "blockers": summary.get("blockers", []),
                    "warnings": summary.get("warnings", []),
                    "errors": summary.get("errors", []),
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary.get('status')}")
        print(f"summaryJson={summary.get('artifacts', {}).get('summaryJson')}")
        print(f"summaryMarkdown={summary.get('artifacts', {}).get('summaryMarkdown')}")
        if summary.get("blockers"):
            print("blockers=" + ";".join(summary["blockers"]))
        if summary.get("warnings"):
            print("warnings=" + ";".join(summary["warnings"]))
        if summary.get("errors"):
            print("errors=" + ";".join(summary["errors"]))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
