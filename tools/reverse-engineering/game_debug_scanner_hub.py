#!/usr/bin/env python3
"""
Game Debug Scanner Hub

Merged read-only utility that combines:
- generic external memory inspection via pymem
- RiftReader-specific live-reader actions from this repo

This tool is intentionally read-only. It does not inject or write memory.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import logging
import logging.handlers
from dataclasses import dataclass
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable, Optional

from scanner_hub_ct_import import CtImportTable, parse_address_expression, parse_cheat_table
from scanner_hub_recovery import RecoverySnapshot, load_recovery_snapshot
from scanner_hub_store import (
    CandidateRecord,
    DiscoveryStore,
    EventRecord,
    ImportEntryRecord,
    ImportRecord,
)


PYMEM_AVAILABLE = True
PYMEM_IMPORT_ERROR: str | None = None
try:
    import pymem
    import pymem.process
    from pymem import Pymem
    from pymem.exception import MemoryReadError, ProcessNotFound, WinAPIError
    from pymem.pattern import pattern_scan_all, pattern_scan_module
except ImportError as exc:  # pragma: no cover - environment dependent
    Pymem = object  # type: ignore[assignment]
    PYMEM_AVAILABLE = False
    PYMEM_IMPORT_ERROR = str(exc)
    pymem = None  # type: ignore[assignment]
    MemoryReadError = RuntimeError  # type: ignore[assignment]
    ProcessNotFound = RuntimeError  # type: ignore[assignment]
    WinAPIError = RuntimeError  # type: ignore[assignment]


HEX_BYTE_RE = re.compile(r"^[0-9A-Fa-f]{2}$")
WILDCARD_RE = re.compile(r"^\?{1,2}$")
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
UI_LOG_QUEUE_MAX_MESSAGES = 1000
MIN_MONITOR_INTERVAL_SECONDS = 0.1
AOB_CANDIDATE_PERSIST_LIMIT = 200
SCANNER_HUB_STORE_VERSION = "slice2"

IsWow64Process = KERNEL32.IsWow64Process
IsWow64Process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
IsWow64Process.restype = wintypes.BOOL


class ScannerError(Exception):
    """Base scanner error."""


class PatternSyntaxError(ScannerError):
    """Raised when a human-readable AOB string is malformed."""


class RiftReaderError(Exception):
    """Raised when a RiftReader repo action fails."""


@dataclass(slots=True)
class AttachmentInfo:
    process_name: str
    process_id: int
    pointer_size: int


@dataclass(slots=True)
class AobScanResult:
    pattern_text: str
    module_name: str | None
    addresses: list[int]
    duration_seconds: float


@dataclass(slots=True)
class MonitorConfig:
    address: int
    value_type: str
    interval_seconds: float


@dataclass(slots=True)
class RiftPlayerSnapshot:
    raw: dict
    process_name: str
    process_id: int
    address_hex: str | None
    level: int | None
    health: int | None
    coord_x: float | None
    coord_y: float | None
    coord_z: float | None
    selection_source: str | None
    anchor_provenance: str | None


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("GameDebugScannerHub")
    if getattr(logger, "_codex_configured", False):
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "game_debug_scanner_hub.log",
        maxBytes=5_242_880,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger._codex_configured = True  # type: ignore[attr-defined]
    logger.info("GameDebugScannerHub initialized")
    return logger


def compile_aob_pattern(pattern_text: str) -> bytes:
    tokens = pattern_text.split()
    if not tokens:
        raise PatternSyntaxError("AOB pattern is empty.")

    regex_parts: list[bytes] = []
    for index, token in enumerate(tokens, start=1):
        if WILDCARD_RE.fullmatch(token):
            regex_parts.append(b".")
            continue

        if HEX_BYTE_RE.fullmatch(token):
            regex_parts.append(re.escape(bytes.fromhex(token)))
            continue

        raise PatternSyntaxError(
            f"Invalid token '{token}' at position {index}. "
            "Use two hex digits (for example 48) or ?? for a wildcard."
        )

    return b"".join(regex_parts)


class GameDebugScanner:
    """Generic read-only process scanner via pymem."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.pm: Optional[Pymem] = None
        self.process_name: Optional[str] = None
        self.pointer_size = ctypes.sizeof(ctypes.c_void_p)
        self._operation_lock = threading.RLock()

    def ensure_available(self) -> None:
        if not PYMEM_AVAILABLE:
            raise ScannerError(
                "pymem is not installed in this Python environment. "
                f"Import error: {PYMEM_IMPORT_ERROR}"
            )

    def _require_process(self) -> Pymem:
        self.ensure_available()
        if not self.pm:
            raise ScannerError("No process is attached.")
        return self.pm

    def _detect_pointer_size(self, pm: Pymem) -> int:
        if ctypes.sizeof(ctypes.c_void_p) == 4:
            return 4

        wow64 = wintypes.BOOL()
        if not IsWow64Process(pm.process_handle, ctypes.byref(wow64)):
            error_code = ctypes.get_last_error()
            raise ScannerError(f"IsWow64Process failed with Win32 error {error_code}.")

        return 4 if bool(wow64.value) else 8

    def attach(self, process_name: str) -> AttachmentInfo:
        with self._operation_lock:
            self.ensure_available()
            name = process_name.strip()
            if not name:
                raise ScannerError("Process name is required.")

            self.detach(log_if_missing=False)

            try:
                pm = Pymem(name)
            except (ProcessNotFound, WinAPIError) as exc:
                raise ScannerError(f"Failed to attach to '{name}': {exc}") from exc
            except Exception as exc:
                raise ScannerError(f"Unexpected attach error for '{name}': {exc}") from exc

            try:
                pointer_size = self._detect_pointer_size(pm)
            except Exception:
                try:
                    pm.close_process()
                except Exception as close_exc:
                    self.logger.warning(
                        "close_process() raised while cleaning up failed attach to '%s': %s",
                        name,
                        close_exc,
                    )
                raise

            self.pm = pm
            self.process_name = name
            self.pointer_size = pointer_size

            info = AttachmentInfo(
                process_name=name,
                process_id=pm.process_id,
                pointer_size=self.pointer_size,
            )
            self.logger.info(
                "Attached to %s (PID %s, %s-bit)",
                info.process_name,
                info.process_id,
                info.pointer_size * 8,
            )
            return info

    def detach(self, *, log_if_missing: bool = True) -> None:
        with self._operation_lock:
            if not self.pm:
                if log_if_missing:
                    self.logger.info("No generic process attached.")
                return

            try:
                self.pm.close_process()
            except Exception as exc:
                self.logger.warning("close_process() raised during detach: %s", exc)
            finally:
                self.pm = None
                self.process_name = None
                self.pointer_size = ctypes.sizeof(ctypes.c_void_p)

            self.logger.info("Detached from generic process")

    def aob_scan(self, pattern_text: str, module_name: str | None = None) -> AobScanResult:
        with self._operation_lock:
            pm = self._require_process()
            compiled_pattern = compile_aob_pattern(pattern_text.strip())
            normalized_module = module_name.strip() if module_name and module_name.strip() else None

            start = time.perf_counter()
            try:
                if normalized_module:
                    module = pymem.process.module_from_name(pm.process_handle, normalized_module)
                    if module is None:
                        raise ScannerError(
                            f"Module '{normalized_module}' was not found in the target process."
                        )

                    addresses = pattern_scan_module(
                        pm.process_handle,
                        module,
                        compiled_pattern,
                        return_multiple=True,
                    )
                else:
                    addresses = pattern_scan_all(
                        pm.process_handle,
                        compiled_pattern,
                        return_multiple=True,
                    )
            except ScannerError:
                raise
            except Exception as exc:
                scope = normalized_module or "full process"
                raise ScannerError(f"AOB scan failed for {scope}: {exc}") from exc

            duration = time.perf_counter() - start
            result = AobScanResult(
                pattern_text=pattern_text,
                module_name=normalized_module,
                addresses=list(addresses or []),
                duration_seconds=duration,
            )
            self.logger.info(
                "AOB scan complete: %s match(es) in %.2fs (%s)",
                len(result.addresses),
                duration,
                normalized_module or "full process",
            )
            return result

    def get_module_base(self, module_name: str) -> int:
        with self._operation_lock:
            pm = self._require_process()
            normalized_module = module_name.strip()
            if not normalized_module:
                raise ScannerError("Module name is required.")

            module = pymem.process.module_from_name(pm.process_handle, normalized_module)
            if module is None:
                raise ScannerError(f"Module '{normalized_module}' was not found in the target process.")

            base_address = int(getattr(module, "lpBaseOfDll"))
            self.logger.info("Resolved module %s base to 0x%X", normalized_module, base_address)
            return base_address

    def resolve_module_relative(self, module_name: str, module_rva: int) -> int:
        base_address = self.get_module_base(module_name)
        absolute_address = base_address + int(module_rva)
        self.logger.info(
            "Resolved module-relative address %s%+d to 0x%X",
            module_name,
            module_rva,
            absolute_address,
        )
        return absolute_address

    def read_pointer(self, address: int) -> int:
        with self._operation_lock:
            pm = self._require_process()
            try:
                if self.pointer_size == 8:
                    return pm.read_ulonglong(address)
                return pm.read_uint(address)
            except MemoryReadError as exc:
                raise ScannerError(f"Failed to read pointer at 0x{address:X}: {exc}") from exc

    def resolve_pointer_chain(
        self,
        base_address: int,
        offsets: list[int],
        *,
        dereference_final: bool = False,
    ) -> int:
        """
        Cheat Engine-style chain:
            ptr = read_pointer(base)
            ptr = read_pointer(ptr + offsets[0])
            ...
            final = ptr + offsets[-1]
        """

        with self._operation_lock:
            self._require_process()
            if not offsets:
                return base_address

            try:
                current = self.read_pointer(base_address)
                for offset in offsets[:-1]:
                    current = self.read_pointer(current + offset)

                final_address = current + offsets[-1]
                if dereference_final:
                    final_address = self.read_pointer(final_address)
            except ScannerError:
                raise
            except Exception as exc:
                raise ScannerError(
                    f"Pointer chain resolution failed from 0x{base_address:X}: {exc}"
                ) from exc

            self.logger.info(
                "Pointer chain resolved to 0x%X (base=0x%X, offsets=%s, dereference_final=%s)",
                final_address,
                base_address,
                [hex(value) for value in offsets],
                dereference_final,
            )
            return final_address

    def read_value(self, address: int, value_type: str) -> int | float:
        with self._operation_lock:
            pm = self._require_process()
            try:
                if value_type == "int":
                    return pm.read_int(address)
                if value_type == "uint":
                    return pm.read_uint(address)
                if value_type == "float":
                    return pm.read_float(address)
                if value_type == "double":
                    return pm.read_double(address)
                if value_type == "pointer":
                    return self.read_pointer(address)
            except MemoryReadError as exc:
                raise ScannerError(
                    f"Failed to read {value_type} value at 0x{address:X}: {exc}"
                ) from exc

            raise ScannerError(f"Unsupported value type '{value_type}'.")

    def read_bytes(self, address: int, length: int) -> bytes:
        with self._operation_lock:
            pm = self._require_process()
            if length <= 0:
                raise ScannerError("Length must be greater than zero.")
            try:
                return pm.read_bytes(address, length)
            except MemoryReadError as exc:
                raise ScannerError(
                    f"Failed to read {length} byte(s) at 0x{address:X}: {exc}"
                ) from exc


class RiftReaderBridge:
    """Thin subprocess bridge over the repo's existing RiftReader scripts."""

    def __init__(self, logger: logging.Logger, repo_root: Optional[Path] = None) -> None:
        self.logger = logger
        default_root = Path(__file__).resolve().parents[2]
        self.repo_root = (repo_root or default_root).resolve()

    @property
    def scripts_dir(self) -> Path:
        return self.repo_root / "scripts"

    def set_repo_root(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    def validate(self) -> list[str]:
        combined_missing = [
            *self.validate_core(),
            *self.validate_dashboard(live=True),
        ]
        return list(dict.fromkeys(combined_missing))

    def validate_core(self) -> list[str]:
        required = [
            self.repo_root / "reader" / "RiftReader.Reader" / "RiftReader.Reader.csproj",
            self.scripts_dir / "read-player-current.ps1",
            self.scripts_dir / "inspect-rift-debug-state.ps1",
        ]

        missing = [str(path) for path in required if not path.exists()]
        return missing

    def validate_dashboard(self, *, live: bool = False) -> list[str]:
        required = [
            self.scripts_dir / "open-dashboard.ps1",
            self.scripts_dir / "build-dashboard-summary.ps1",
            self.repo_root / "tools" / "dashboard" / "index.html",
            self.repo_root / "tools" / "dashboard" / "app.js",
            self.repo_root / "tools" / "dashboard" / "styles.css",
        ]
        if live:
            required.append(self.scripts_dir / "build-dashboard-live-data.ps1")

        return [str(path) for path in required if not path.exists()]

    def is_available(self) -> bool:
        return not self.validate_core()

    def _run_command(
        self,
        command: list[str],
        *,
        timeout_seconds: float | None = None,
        label: str,
    ) -> str:
        completed = subprocess.run(
            command,
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            creationflags=CREATE_NO_WINDOW,
        )

        output_parts = [part for part in (completed.stdout, completed.stderr) if part]
        output = "\n".join(output_parts).strip()
        if completed.returncode != 0:
            raise RiftReaderError(
                f"{label} failed with exit code {completed.returncode}.\n{output or '(no output)'}"
            )

        return output

    def _run_powershell_script(
        self,
        script_name: str,
        *args: str,
        timeout_seconds: float | None = None,
    ) -> str:
        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            raise RiftReaderError(f"Script not found: {script_path}")

        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            *args,
        ]
        return self._run_command(command, timeout_seconds=timeout_seconds, label=script_name)

    def _start_powershell_script(self, script_name: str, *args: str) -> None:
        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            raise RiftReaderError(f"Script not found: {script_path}")

        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                *args,
            ],
            cwd=str(self.repo_root),
            creationflags=CREATE_NO_WINDOW,
        )

    def run_reader_command(self, *args: str, timeout_seconds: float | None = None) -> str:
        project_path = self.repo_root / "reader" / "RiftReader.Reader" / "RiftReader.Reader.csproj"
        command = [
            "dotnet",
            "run",
            "--project",
            str(project_path),
            "--",
            *args,
        ]
        return self._run_command(command, timeout_seconds=timeout_seconds, label="reader command")

    def build_solution(self, *, timeout_seconds: float | None = None) -> str:
        solution_path = self.repo_root / "RiftReader.slnx"
        return self._run_command(
            ["dotnet", "build", str(solution_path)],
            timeout_seconds=timeout_seconds,
            label="dotnet build",
        )

    def readerbridge_snapshot(self) -> str:
        self.logger.info("Running ReaderBridge snapshot")
        return self.run_reader_command("--readerbridge-snapshot", "--json", timeout_seconds=180)

    def read_player_coord_anchor(self) -> str:
        self.logger.info("Running player coord-anchor read")
        return self.run_reader_command(
            "--process-name",
            "rift_x64",
            "--read-player-coord-anchor",
            "--json",
            timeout_seconds=180,
        )

    def rebuild_owner_source_chain(self) -> str:
        self.logger.info("Rebuilding owner/source chain")
        outputs = [
            self._run_powershell_script(
                "capture-player-source-chain.ps1",
                "-Json",
                "-RefreshCluster",
                timeout_seconds=600,
            ),
            self._run_powershell_script(
                "capture-player-owner-components.ps1",
                "-Json",
                "-RefreshSelectorTrace",
                timeout_seconds=600,
            ),
        ]
        return "\n\n".join(part for part in outputs if part).strip()

    def refresh_core_graph(self) -> str:
        self.logger.info("Refreshing owner/stat graph artifacts")
        outputs = [
            self._run_powershell_script(
                "capture-player-owner-graph.ps1",
                "-Json",
                "-RefreshSelectorTrace",
                timeout_seconds=600,
            ),
            self._run_powershell_script(
                "capture-player-stat-hub-graph.ps1",
                "-Json",
                "-RefreshOwnerComponents",
                timeout_seconds=600,
            ),
            self._run_powershell_script(
                "inspect-capture-consistency.ps1",
                "-Json",
                timeout_seconds=300,
            ),
        ]
        return "\n\n".join(part for part in outputs if part).strip()

    def inspect_capture_consistency(self) -> str:
        self.logger.info("Inspecting capture consistency")
        return self._run_powershell_script(
            "inspect-capture-consistency.ps1",
            "-Json",
            timeout_seconds=300,
        )

    def inspect_debug_state(self) -> str:
        self.logger.info("Running Rift debug-state probe")
        return self._run_powershell_script("inspect-rift-debug-state.ps1")

    def open_dashboard(self, *, live: bool = False) -> str:
        self.logger.info("Preflighting Rift dashboard (live=%s)", live)

        output_parts = [
            self._run_powershell_script("build-dashboard-summary.ps1", timeout_seconds=120)
        ]
        if live:
            output_parts.append(
                self._run_powershell_script("build-dashboard-live-data.ps1", timeout_seconds=120)
            )

        dashboard_path = self.repo_root / "tools" / "dashboard" / "index.html"
        if not dashboard_path.exists():
            raise RiftReaderError(f"Dashboard entrypoint was not found after preflight: {dashboard_path}")

        args = ["-Live"] if live else []
        self._start_powershell_script("open-dashboard.ps1", *args)
        return "\n\n".join(part for part in output_parts if part).strip()

    def read_current_player(self) -> tuple[RiftPlayerSnapshot, str]:
        self.logger.info("Reading current Rift player snapshot")
        try:
            raw_output = self._run_powershell_script(
                "read-player-current.ps1",
                "-Json",
                timeout_seconds=120,
            )
        except RiftReaderError as exc:
            self.logger.warning(
                "Default read-player-current.ps1 invocation failed; retrying with -SkipRefresh. %s",
                exc,
            )
            retry_output = self._run_powershell_script(
                "read-player-current.ps1",
                "-Json",
                "-SkipRefresh",
                timeout_seconds=120,
            )
            raw_output = (
                "[GameDebugScannerHub] Fallback: initial read-player-current.ps1 run failed; "
                "retried with -SkipRefresh.\n\n" + retry_output
            )

        payload = self._extract_last_json_object(raw_output)
        if not isinstance(payload, dict):
            raise RiftReaderError("read-player-current.ps1 did not emit a JSON object.")

        memory = payload.get("Memory") or {}
        snapshot = RiftPlayerSnapshot(
            raw=payload,
            process_name=str(payload.get("ProcessName") or "rift_x64"),
            process_id=int(payload.get("ProcessId") or 0),
            address_hex=memory.get("AddressHex"),
            level=memory.get("Level"),
            health=memory.get("Health"),
            coord_x=memory.get("CoordX"),
            coord_y=memory.get("CoordY"),
            coord_z=memory.get("CoordZ"),
            selection_source=payload.get("SelectionSource"),
            anchor_provenance=payload.get("AnchorProvenance"),
        )
        return snapshot, raw_output

    @staticmethod
    def _extract_last_json_object(text: str) -> dict | list | None:
        decoder = json.JSONDecoder()
        best_payload = None
        best_span = -1

        for index, char in enumerate(text):
            if char not in "{[":
                continue

            try:
                payload, end_index = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue

            remaining = text[index + end_index :].strip()
            if not remaining:
                return payload

            if end_index > best_span:
                best_payload = payload
                best_span = end_index

        return best_payload


class TkQueueHandler(logging.Handler):
    def __init__(self, target_queue: "queue.Queue[str]") -> None:
        super().__init__()
        self.target_queue = target_queue
        self._drop_lock = threading.Lock()
        self._dropped_messages = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.target_queue.put_nowait(self.format(record))
        except queue.Full:
            with self._drop_lock:
                self._dropped_messages += 1
        except Exception:  # pragma: no cover - logging should not raise
            self.handleError(record)

    def consume_drop_notice(self) -> str | None:
        with self._drop_lock:
            dropped_messages = self._dropped_messages
            self._dropped_messages = 0

        if dropped_messages <= 0:
            return None

        noun = "message" if dropped_messages == 1 else "messages"
        return (
            f"{time.strftime('%H:%M:%S')}.000 | WARNING  | "
            f"UI log dropped {dropped_messages} {noun} because the queue was full"
        )


class ScannerHubGUI:
    def __init__(self) -> None:
        self.logger = setup_logger()
        self.generic_scanner = GameDebugScanner(self.logger)
        self.rift_bridge = RiftReaderBridge(self.logger)
        self.discovery_store: DiscoveryStore | None = None
        self.discovery_store_error: str | None = None
        self.recovery_snapshot: RecoverySnapshot | None = None
        self.candidate_records: dict[int, CandidateRecord] = {}
        self.import_records: dict[int, ImportEntryRecord] = {}
        self.import_sources: dict[int, ImportRecord] = {}
        self.event_records: dict[int, EventRecord] = {}
        self.candidate_sort_column = "confidence"
        self.candidate_sort_reverse = True
        self.import_sort_column = "confidence"
        self.import_sort_reverse = True
        self.event_sort_column = "created_at"
        self.event_sort_reverse = True

        try:
            self.discovery_store = DiscoveryStore()
            self.discovery_store.open_session(
                repo_root=str(self.rift_bridge.repo_root),
                scanner_version=SCANNER_HUB_STORE_VERSION,
            )
        except Exception as exc:
            self.discovery_store_error = str(exc)
            self.logger.warning("Discovery store initialization failed: %s", exc)

        self.root = tk.Tk()
        self.root.title("Game Debug Scanner Hub - Generic + RiftReader (Read-only)")
        self.root.geometry("1280x820")
        self.root.minsize(1080, 720)

        self.log_queue: "queue.Queue[str]" = queue.Queue(maxsize=UI_LOG_QUEUE_MAX_MESSAGES)
        self.ui_log_handler = TkQueueHandler(self.log_queue)
        self.ui_log_handler.setLevel(logging.INFO)
        self.ui_log_handler.setFormatter(
            logging.Formatter("%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s", "%H:%M:%S")
        )
        self.logger.addHandler(self.ui_log_handler)

        self.status_var = tk.StringVar(value="Ready")
        self.pointer_size_var = tk.StringVar(value="Unknown")
        self.monitor_status_var = tk.StringVar(value="Monitor idle")
        self.rift_repo_status_var = tk.StringVar(value="")
        self.rift_player_summary_var = tk.StringVar(value="No Rift snapshot loaded")
        self.hex_status_var = tk.StringVar(value="Idle")
        self.candidate_summary_var = tk.StringVar(value="Loading candidates...")
        self.recovery_summary_var = tk.StringVar(value="Loading recovery state...")
        self.import_summary_var = tk.StringVar(value="No imported Cheat Engine tables yet")
        self.evidence_summary_var = tk.StringVar(value="Loading structured evidence log...")
        self.session_summary_var = tk.StringVar(value="Session booting...")
        self.session_export_var = tk.StringVar(value="No exports yet")
        self.candidate_filter_status_var = tk.StringVar(value="All")
        self.candidate_filter_kind_var = tk.StringVar(value="All")
        self.candidate_filter_source_var = tk.StringVar(value="All")
        self.candidate_filter_view_var = tk.StringVar(value="All")
        self.candidate_filter_search_var = tk.StringVar(value="")
        self.import_filter_status_var = tk.StringVar(value="All")
        self.import_filter_search_var = tk.StringVar(value="")
        self.import_source_var = tk.StringVar(value="All")

        self.monitor_thread: threading.Thread | None = None
        self.monitor_stop_event = threading.Event()
        self.scan_in_progress = False
        self.hex_read_in_progress = False
        self.generic_background_jobs = 0
        self.repo_background_jobs = 0
        self.last_rift_snapshot: RiftPlayerSnapshot | None = None
        self._is_closing = False

        self._build_ui()
        self._load_ui_state()
        self._sync_repo_status()
        self._refresh_candidates_view()
        self._refresh_imports_view()
        self._refresh_evidence_view()
        self._refresh_session_view()
        self.root.after(75, self._drain_log_queue)

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._create_process_tab()
        self._create_aob_tab()
        self._create_pointer_tab()
        self._create_monitor_tab()
        self._create_hex_tab()
        self._create_candidates_tab()
        self._create_imports_tab()
        self._create_recovery_tab()
        self._create_rift_tab()
        self._create_session_tab()
        self._create_log_tab()

        self._set_generic_controls_enabled(PYMEM_AVAILABLE)
        self._refresh_generic_control_states()

        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Label(status_bar, textvariable=self.status_var).pack(side="left")
        ttk.Label(status_bar, text="Pointer width:").pack(side="right", padx=(12, 4))
        ttk.Label(status_bar, textvariable=self.pointer_size_var).pack(side="right")

    def _create_process_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Generic Process")

        ttk.Label(tab, text="Process name (for example: game.exe)").grid(row=0, column=0, sticky="w")
        self.proc_entry = ttk.Entry(tab, width=48)
        self.proc_entry.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.proc_entry.insert(0, "yourgame.exe")

        button_row = ttk.Frame(tab)
        button_row.grid(row=2, column=0, sticky="w", pady=(0, 8))

        self.attach_button = ttk.Button(button_row, text="Attach", command=self.attach_process)
        self.attach_button.pack(side="left")
        self.detach_button = ttk.Button(button_row, text="Detach", command=self.detach_process)
        self.detach_button.pack(side="left", padx=(8, 0))
        self.attach_rift_button = ttk.Button(button_row, text="Attach to Rift", command=self.attach_rift_process)
        self.attach_rift_button.pack(side="left", padx=(8, 0))
        self.attach_last_snapshot_button = ttk.Button(
            button_row,
            text="Attach Last Rift Snapshot",
            command=self.attach_last_rift_snapshot_process,
        )
        self.attach_last_snapshot_button.pack(side="left", padx=(8, 0))

        self.proc_status_var = tk.StringVar(value="Not attached")
        ttk.Label(tab, textvariable=self.proc_status_var).grid(row=3, column=0, sticky="w")

        self.generic_availability_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.generic_availability_var, foreground="#666666").grid(
            row=4, column=0, sticky="w", pady=(8, 0)
        )

        tab.columnconfigure(0, weight=1)

    def _create_aob_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="AOB Scanner")

        ttk.Label(tab, text="AOB Pattern (? or ?? for wildcard)").grid(row=0, column=0, sticky="w")
        self.aob_entry = ttk.Entry(tab)
        self.aob_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        self.aob_entry.insert(0, "48 8B 05 ?? ?? ?? ??")

        ttk.Label(tab, text="Optional module name").grid(row=2, column=0, sticky="w")
        self.aob_module_entry = ttk.Entry(tab)
        self.aob_module_entry.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, 8))

        button_row = ttk.Frame(tab)
        button_row.grid(row=4, column=0, sticky="w")
        self.aob_scan_button = ttk.Button(button_row, text="Scan", command=self.do_aob_scan)
        self.aob_scan_button.pack(side="left")
        self.aob_use_snapshot_process_button = ttk.Button(
            button_row,
            text="Use Last Rift Snapshot Process",
            command=self.use_last_rift_snapshot_process_name,
        )
        self.aob_use_snapshot_process_button.pack(side="left", padx=(8, 0))
        self.aob_coord_anchor_button = ttk.Button(
            button_row,
            text="Use Coord Anchor Preset",
            command=self.use_coord_anchor_preset,
        )
        self.aob_coord_anchor_button.pack(side="left", padx=(8, 0))

        self.aob_status_var = tk.StringVar(value="Idle")
        ttk.Label(tab, textvariable=self.aob_status_var).grid(row=4, column=1, columnspan=2, sticky="w", padx=(10, 0))

        self.aob_results = scrolledtext.ScrolledText(tab, height=20, font=("Consolas", 10))
        self.aob_results.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(10, 0))

        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(2, weight=1)
        tab.rowconfigure(5, weight=1)

    def _create_pointer_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Pointer Chain")

        ttk.Label(tab, text="Base address (hex or decimal)").grid(row=0, column=0, sticky="w")
        self.base_entry = ttk.Entry(tab)
        self.base_entry.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.base_entry.insert(0, "0x7FFABC123456")

        ttk.Label(tab, text="Offsets (comma-separated, hex or decimal)").grid(row=2, column=0, sticky="w")
        self.offset_entry = ttk.Entry(tab)
        self.offset_entry.grid(row=3, column=0, sticky="ew", pady=(4, 8))
        self.offset_entry.insert(0, "0x10, 0x20, 0x8")

        self.deref_final_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(tab, text="Dereference final hop", variable=self.deref_final_var).grid(
            row=4, column=0, sticky="w", pady=(0, 8)
        )

        button_row = ttk.Frame(tab)
        button_row.grid(row=5, column=0, sticky="w")
        self.pointer_button = ttk.Button(button_row, text="Resolve", command=self.resolve_pointer)
        self.pointer_button.pack(side="left")
        self.pointer_use_snapshot_button = ttk.Button(
            button_row,
            text="Use Last Rift Snapshot Address",
            command=lambda: self.use_last_rift_snapshot_address(self.base_entry, "pointer base address"),
        )
        self.pointer_use_snapshot_button.pack(side="left", padx=(8, 0))

        self.pointer_result_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.pointer_result_var, font=("Consolas", 11)).grid(
            row=6, column=0, sticky="w", pady=(10, 0)
        )

        tab.columnconfigure(0, weight=1)

    def _create_monitor_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Live Monitor")

        ttk.Label(tab, text="Address (hex or decimal)").grid(row=0, column=0, sticky="w")
        self.monitor_entry = ttk.Entry(tab)
        self.monitor_entry.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.monitor_entry.insert(0, "0xDEADBEEF")

        ttk.Label(tab, text="Value type").grid(row=2, column=0, sticky="w")
        self.type_var = tk.StringVar(value="int")
        type_row = ttk.Frame(tab)
        type_row.grid(row=3, column=0, sticky="w", pady=(4, 8))
        for label in ("int", "uint", "float", "double", "pointer"):
            ttk.Radiobutton(type_row, text=label, variable=self.type_var, value=label).pack(side="left", padx=(0, 10))

        ttk.Label(tab, text="Interval (seconds)").grid(row=4, column=0, sticky="w")
        self.monitor_interval_entry = ttk.Entry(tab, width=12)
        self.monitor_interval_entry.grid(row=5, column=0, sticky="w", pady=(4, 8))
        self.monitor_interval_entry.insert(0, "0.5")

        button_row = ttk.Frame(tab)
        button_row.grid(row=6, column=0, sticky="w")
        self.monitor_start_button = ttk.Button(button_row, text="Start Monitor", command=self.start_monitor)
        self.monitor_start_button.pack(side="left")
        self.monitor_stop_button = ttk.Button(button_row, text="Stop Monitor", command=self.stop_monitor)
        self.monitor_stop_button.pack(side="left", padx=(8, 0))
        self.monitor_use_snapshot_button = ttk.Button(
            button_row,
            text="Use Last Rift Snapshot Address",
            command=lambda: self.use_last_rift_snapshot_address(self.monitor_entry, "monitor address"),
        )
        self.monitor_use_snapshot_button.pack(side="left", padx=(8, 0))

        ttk.Label(tab, textvariable=self.monitor_status_var).grid(row=7, column=0, sticky="w", pady=(10, 0))

        tab.columnconfigure(0, weight=1)

    def _create_hex_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Hex Dump")

        ttk.Label(tab, text="Address (hex or decimal)").grid(row=0, column=0, sticky="w")
        self.hex_address_entry = ttk.Entry(tab)
        self.hex_address_entry.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.hex_address_entry.insert(0, "0xDEADBEEF")

        ttk.Label(tab, text="Length (bytes)").grid(row=2, column=0, sticky="w")
        self.hex_length_entry = ttk.Entry(tab, width=12)
        self.hex_length_entry.grid(row=3, column=0, sticky="w", pady=(4, 8))
        self.hex_length_entry.insert(0, "64")

        button_row = ttk.Frame(tab)
        button_row.grid(row=4, column=0, sticky="w")
        self.hex_read_button = ttk.Button(button_row, text="Read Hex Dump", command=self.read_hex_dump)
        self.hex_read_button.pack(side="left")
        self.hex_use_snapshot_button = ttk.Button(
            button_row,
            text="Use Last Rift Snapshot Address",
            command=lambda: self.use_last_rift_snapshot_address(self.hex_address_entry, "hex dump address"),
        )
        self.hex_use_snapshot_button.pack(side="left", padx=(8, 0))

        ttk.Label(tab, textvariable=self.hex_status_var).grid(row=5, column=0, sticky="w", pady=(10, 4))

        self.hex_output = scrolledtext.ScrolledText(tab, height=22, font=("Consolas", 10))
        self.hex_output.grid(row=6, column=0, sticky="nsew")

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(6, weight=1)

    def _create_candidates_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Candidates")

        header = ttk.Frame(tab)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header, textvariable=self.candidate_summary_var).pack(side="left", fill="x", expand=True)
        ttk.Button(header, text="Refresh", command=self._refresh_candidates_view).pack(side="right")

        filter_frame = ttk.LabelFrame(tab, text="Filters", padding=8)
        filter_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Label(filter_frame, text="Status").grid(row=0, column=0, sticky="w")
        self.candidate_status_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.candidate_filter_status_var,
            values=("All", "candidate", "confirmed", "promoted", "stale", "broken"),
            state="readonly",
            width=14,
        )
        self.candidate_status_combo.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(4, 0))
        ttk.Label(filter_frame, text="Kind").grid(row=0, column=1, sticky="w")
        self.candidate_kind_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.candidate_filter_kind_var,
            values=("All", "aob", "pointer", "anchor", "module-offset", "address", "ct-import"),
            state="readonly",
            width=16,
        )
        self.candidate_kind_combo.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(4, 0))
        ttk.Label(filter_frame, text="Source").grid(row=0, column=2, sticky="w")
        self.candidate_source_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.candidate_filter_source_var,
            values=("All", "aob-scan", "pointer-chain", "rift-player-current", "ct-import"),
            width=18,
        )
        self.candidate_source_combo.grid(row=1, column=2, sticky="w", padx=(0, 8), pady=(4, 0))
        ttk.Label(filter_frame, text="View").grid(row=0, column=3, sticky="w")
        self.candidate_view_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.candidate_filter_view_var,
            values=("All", "Survivors since update", "Broken / stale", "Imported unresolved"),
            state="readonly",
            width=20,
        )
        self.candidate_view_combo.grid(row=1, column=3, sticky="w", padx=(0, 8), pady=(4, 0))
        ttk.Label(filter_frame, text="Search").grid(row=0, column=4, sticky="w")
        self.candidate_search_entry = ttk.Entry(filter_frame, textvariable=self.candidate_filter_search_var, width=28)
        self.candidate_search_entry.grid(row=1, column=4, sticky="ew", padx=(0, 8), pady=(4, 0))
        ttk.Button(filter_frame, text="Apply", command=self._refresh_candidates_view).grid(
            row=1, column=5, sticky="w", pady=(4, 0)
        )
        ttk.Button(filter_frame, text="Clear", command=self._reset_candidate_filters).grid(
            row=1, column=6, sticky="w", padx=(8, 0), pady=(4, 0)
        )
        filter_frame.columnconfigure(4, weight=1)

        action_frame = ttk.Frame(tab)
        action_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(action_frame, text="Promote", command=lambda: self._update_selected_candidate_status("promoted")).pack(
            side="left"
        )
        ttk.Button(action_frame, text="Demote", command=lambda: self._update_selected_candidate_status("candidate")).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(action_frame, text="Mark stale", command=lambda: self._update_selected_candidate_status("stale")).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(action_frame, text="Copy spec", command=self._copy_selected_candidate_spec).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(
            action_frame,
            text="Use addr -> Pointer",
            command=lambda: self._use_selected_candidate_address(self.base_entry, "pointer base address"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            action_frame,
            text="Use addr -> Monitor",
            command=lambda: self._use_selected_candidate_address(self.monitor_entry, "monitor address"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            action_frame,
            text="Use addr -> Hex",
            command=lambda: self._use_selected_candidate_address(self.hex_address_entry, "hex dump address"),
        ).pack(side="left", padx=(8, 0))

        columns = ("kind", "status", "confidence", "address", "source", "last_seen", "label")
        self.candidate_tree = ttk.Treeview(tab, columns=columns, show="headings", height=18)
        headings = {
            "kind": "Kind",
            "status": "Status",
            "confidence": "Confidence",
            "address": "Address",
            "source": "Source",
            "last_seen": "Last seen",
            "label": "Label",
        }
        widths = {
            "kind": 110,
            "status": 110,
            "confidence": 90,
            "address": 130,
            "source": 100,
            "last_seen": 165,
            "label": 420,
        }
        stretches = {
            "kind": False,
            "status": False,
            "confidence": False,
            "address": False,
            "source": False,
            "last_seen": False,
            "label": True,
        }

        for column in columns:
            self.candidate_tree.heading(
                column,
                text=headings[column],
                command=lambda column_name=column: self._sort_candidates_by(column_name),
            )
            self.candidate_tree.column(column, width=widths[column], stretch=stretches[column], anchor="w")

        candidate_scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.candidate_tree.yview)
        self.candidate_tree.configure(yscrollcommand=candidate_scrollbar.set)
        self.candidate_tree.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        candidate_scrollbar.grid(row=3, column=1, sticky="ns", pady=(10, 0))
        self.candidate_tree.bind("<<TreeviewSelect>>", self._on_candidate_selected)

        detail_frame = ttk.LabelFrame(tab, text="Candidate detail", padding=8)
        detail_frame.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        evidence_frame = ttk.LabelFrame(tab, text="Candidate evidence", padding=8)
        evidence_frame.grid(row=4, column=1, sticky="nsew", pady=(10, 0), padx=(10, 0))

        self.candidate_detail = scrolledtext.ScrolledText(detail_frame, height=12, font=("Consolas", 10))
        self.candidate_detail.pack(fill="both", expand=True)
        self.candidate_evidence_text = scrolledtext.ScrolledText(evidence_frame, height=12, font=("Consolas", 10))
        self.candidate_evidence_text.pack(fill="both", expand=True)

        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(3, weight=1)
        tab.rowconfigure(4, weight=1)

    def _create_imports_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Imports")

        header = ttk.Frame(tab)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header, textvariable=self.import_summary_var).pack(side="left", fill="x", expand=True)
        ttk.Button(header, text="Import .ct", command=self.import_ct_table).pack(side="right")
        ttk.Button(header, text="Refresh", command=self._refresh_imports_view).pack(side="right", padx=(0, 8))

        filter_frame = ttk.LabelFrame(tab, text="Import filter", padding=8)
        filter_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Label(filter_frame, text="Source").grid(row=0, column=0, sticky="w")
        self.import_source_combo = ttk.Combobox(filter_frame, textvariable=self.import_source_var, values=("All",), width=28)
        self.import_source_combo.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(4, 0))
        ttk.Label(filter_frame, text="Status").grid(row=0, column=1, sticky="w")
        self.import_status_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.import_filter_status_var,
            values=("All", "imported", "resolved", "promoted", "stale", "broken"),
            state="readonly",
            width=16,
        )
        self.import_status_combo.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(4, 0))
        ttk.Label(filter_frame, text="Search").grid(row=0, column=2, sticky="w")
        self.import_search_entry = ttk.Entry(filter_frame, textvariable=self.import_filter_search_var, width=36)
        self.import_search_entry.grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(4, 0))
        ttk.Button(filter_frame, text="Apply", command=self._refresh_imports_view).grid(
            row=1, column=3, sticky="w", pady=(4, 0)
        )
        ttk.Button(filter_frame, text="Clear", command=self._reset_import_filters).grid(
            row=1, column=4, sticky="w", padx=(8, 0), pady=(4, 0)
        )
        filter_frame.columnconfigure(2, weight=1)

        action_frame = ttk.Frame(tab)
        action_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(action_frame, text="Resolve selected", command=lambda: self.resolve_import_entries(selected_only=True)).pack(
            side="left"
        )
        ttk.Button(action_frame, text="Resolve visible", command=lambda: self.resolve_import_entries(selected_only=False)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(action_frame, text="Promote selected", command=lambda: self.promote_import_entries(selected_only=True)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(action_frame, text="Promote resolved", command=lambda: self.promote_import_entries(selected_only=False)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(action_frame, text="Revalidate imported", command=self.revalidate_imported_entries).pack(
            side="left", padx=(8, 0)
        )

        import_columns = ("status", "kind", "confidence", "resolved", "type", "group", "label")
        self.import_tree = ttk.Treeview(tab, columns=import_columns, show="headings", height=18)
        import_headings = {
            "status": "Status",
            "kind": "Kind",
            "confidence": "Confidence",
            "resolved": "Resolved",
            "type": "Value type",
            "group": "Group",
            "label": "Label",
        }
        import_widths = {
            "status": 110,
            "kind": 110,
            "confidence": 90,
            "resolved": 135,
            "type": 120,
            "group": 220,
            "label": 360,
        }
        for column in import_columns:
            self.import_tree.heading(
                column,
                text=import_headings[column],
                command=lambda column_name=column: self._sort_imports_by(column_name),
            )
            self.import_tree.column(column, width=import_widths[column], stretch=column in {"group", "label"}, anchor="w")
        import_scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.import_tree.yview)
        self.import_tree.configure(yscrollcommand=import_scrollbar.set)
        self.import_tree.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        import_scrollbar.grid(row=3, column=1, sticky="ns", pady=(10, 0))
        self.import_tree.bind("<<TreeviewSelect>>", self._on_import_selected)

        detail_frame = ttk.LabelFrame(tab, text="Import detail", padding=8)
        detail_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        self.import_detail_text = scrolledtext.ScrolledText(detail_frame, height=12, font=("Consolas", 10))
        self.import_detail_text.pack(fill="both", expand=True)

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        tab.rowconfigure(4, weight=1)

    def _create_recovery_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Recovery")

        header = ttk.Frame(tab)
        header.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Label(header, textvariable=self.recovery_summary_var).pack(side="left", fill="x", expand=True)
        ttk.Button(header, text="Refresh", command=self._refresh_recovery_view).pack(side="right")

        action_frame = ttk.Frame(tab)
        action_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.recovery_build_button = ttk.Button(action_frame, text="Build repo", command=self.build_rift_repo)
        self.recovery_build_button.pack(side="left")
        self.recovery_baseline_button = ttk.Button(action_frame, text="Refresh baseline", command=self.refresh_recovery_baseline)
        self.recovery_baseline_button.pack(side="left", padx=(8, 0))
        self.recovery_source_chain_button = ttk.Button(
            action_frame,
            text="Rebuild source/owner",
            command=self.rebuild_recovery_source_chain,
        )
        self.recovery_source_chain_button.pack(side="left", padx=(8, 0))
        self.recovery_core_graph_button = ttk.Button(
            action_frame,
            text="Refresh core graph",
            command=self.refresh_recovery_core_graph,
        )
        self.recovery_core_graph_button.pack(side="left", padx=(8, 0))
        self.recovery_consistency_button = ttk.Button(
            action_frame,
            text="Inspect consistency",
            command=self.inspect_recovery_consistency,
        )
        self.recovery_consistency_button.pack(side="left", padx=(8, 0))
        ttk.Button(action_frame, text="Coord anchor preset", command=self.use_coord_anchor_preset).pack(
            side="left",
            padx=(8, 0),
        )
        self.recovery_export_button = ttk.Button(
            action_frame,
            text="Export recovery package",
            command=self.export_recovery_package,
        )
        self.recovery_export_button.pack(side="left", padx=(8, 0))

        truth_frame = ttk.LabelFrame(tab, text="Current truth", padding=8)
        truth_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self.recovery_truth_tree = ttk.Treeview(truth_frame, columns=("area", "status"), show="headings", height=8)
        self.recovery_truth_tree.heading("area", text="Area")
        self.recovery_truth_tree.heading("status", text="Status")
        self.recovery_truth_tree.column("area", width=260, stretch=True, anchor="w")
        self.recovery_truth_tree.column("status", width=180, stretch=True, anchor="w")
        recovery_truth_scroll = ttk.Scrollbar(truth_frame, orient="vertical", command=self.recovery_truth_tree.yview)
        self.recovery_truth_tree.configure(yscrollcommand=recovery_truth_scroll.set)
        self.recovery_truth_tree.pack(side="left", fill="both", expand=True)
        recovery_truth_scroll.pack(side="right", fill="y")

        artifact_frame = ttk.LabelFrame(tab, text="Tracked artifacts", padding=8)
        artifact_frame.grid(row=2, column=1, columnspan=2, sticky="nsew", padx=(10, 0), pady=(10, 0))
        artifact_columns = ("tier", "exists", "updated_at", "label")
        self.recovery_artifact_tree = ttk.Treeview(
            artifact_frame,
            columns=artifact_columns,
            show="headings",
            height=8,
        )
        artifact_headings = {
            "tier": "Tier",
            "exists": "Exists",
            "updated_at": "Updated",
            "label": "Artifact",
        }
        artifact_widths = {
            "tier": 210,
            "exists": 70,
            "updated_at": 180,
            "label": 420,
        }
        for column in artifact_columns:
            self.recovery_artifact_tree.heading(column, text=artifact_headings[column])
            self.recovery_artifact_tree.column(column, width=artifact_widths[column], stretch=(column == "label"), anchor="w")
        recovery_artifact_scroll = ttk.Scrollbar(
            artifact_frame,
            orient="vertical",
            command=self.recovery_artifact_tree.yview,
        )
        self.recovery_artifact_tree.configure(yscrollcommand=recovery_artifact_scroll.set)
        self.recovery_artifact_tree.pack(side="left", fill="both", expand=True)
        recovery_artifact_scroll.pack(side="right", fill="y")

        notes_frame = ttk.LabelFrame(tab, text="Recovery notes", padding=8)
        notes_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        self.recovery_notes_text = scrolledtext.ScrolledText(notes_frame, height=16, font=("Consolas", 10))
        self.recovery_notes_text.pack(fill="both", expand=True)

        runbook_frame = ttk.LabelFrame(tab, text="Rebuild runbook", padding=8)
        runbook_frame.grid(row=3, column=2, sticky="nsew", pady=(10, 0), padx=(10, 0))
        self.recovery_runbook_text = scrolledtext.ScrolledText(runbook_frame, height=16, font=("Consolas", 10))
        self.recovery_runbook_text.pack(fill="both", expand=True)

        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(2, weight=1)
        tab.rowconfigure(2, weight=1)
        tab.rowconfigure(3, weight=1)

    def _create_rift_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="RiftReader")

        ttk.Label(tab, text="RiftReader repo path").grid(row=0, column=0, sticky="w")
        self.repo_entry = ttk.Entry(tab)
        self.repo_entry.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(4, 8))
        self.repo_entry.insert(0, str(self.rift_bridge.repo_root))

        self.repo_validate_button = ttk.Button(tab, text="Validate Repo", command=self.validate_repo_path)
        self.repo_validate_button.grid(row=2, column=0, sticky="w")
        ttk.Label(tab, textvariable=self.rift_repo_status_var).grid(row=2, column=1, columnspan=3, sticky="w", padx=(10, 0))

        ttk.Separator(tab, orient="horizontal").grid(row=3, column=0, columnspan=4, sticky="ew", pady=12)

        button_row = ttk.Frame(tab)
        button_row.grid(row=4, column=0, columnspan=4, sticky="w")
        self.rift_read_button = ttk.Button(button_row, text="Read Current Player", command=self.read_rift_current_player)
        self.rift_read_button.pack(side="left")
        self.rift_debug_button = ttk.Button(button_row, text="Inspect Debug State", command=self.inspect_rift_debug_state)
        self.rift_debug_button.pack(side="left", padx=(8, 0))
        self.rift_dashboard_button = ttk.Button(button_row, text="Open Dashboard", command=self.open_rift_dashboard)
        self.rift_dashboard_button.pack(side="left", padx=(8, 0))
        self.rift_live_dashboard_button = ttk.Button(button_row, text="Open Live Dashboard", command=self.open_rift_live_dashboard)
        self.rift_live_dashboard_button.pack(side="left", padx=(8, 0))

        ttk.Label(tab, textvariable=self.rift_player_summary_var, font=("Consolas", 10)).grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(12, 8)
        )

        self.rift_output = scrolledtext.ScrolledText(tab, height=24, font=("Consolas", 10))
        self.rift_output.grid(row=6, column=0, columnspan=4, sticky="nsew")

        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(2, weight=1)
        tab.columnconfigure(3, weight=1)
        tab.rowconfigure(6, weight=1)

    def _create_session_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Session")

        header = ttk.Frame(tab)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header, textvariable=self.session_summary_var).pack(side="left", fill="x", expand=True)
        ttk.Label(header, textvariable=self.session_export_var).pack(side="right")

        action_frame = ttk.Frame(tab)
        action_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(action_frame, text="Save notes", command=self.save_session_notes).pack(side="left")
        ttk.Button(action_frame, text="Refresh", command=self._refresh_session_view).pack(side="left", padx=(8, 0))
        ttk.Button(action_frame, text="Export session package", command=self.export_session_package).pack(
            side="left",
            padx=(8, 0),
        )
        ttk.Button(action_frame, text="Export recovery package", command=self.export_recovery_package).pack(
            side="left",
            padx=(8, 0),
        )

        notes_frame = ttk.LabelFrame(tab, text="Session notes", padding=8)
        notes_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self.session_notes_text = scrolledtext.ScrolledText(notes_frame, height=18, font=("Consolas", 10))
        self.session_notes_text.pack(fill="both", expand=True)

        export_frame = ttk.LabelFrame(tab, text="Session snapshot preview", padding=8)
        export_frame.grid(row=2, column=1, sticky="nsew", pady=(10, 0), padx=(10, 0))
        self.session_export_text = scrolledtext.ScrolledText(export_frame, height=18, font=("Consolas", 10))
        self.session_export_text.pack(fill="both", expand=True)

        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(2, weight=1)

    def _create_log_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Log")

        log_notebook = ttk.Notebook(tab)
        log_notebook.pack(fill="both", expand=True)

        operator_tab = ttk.Frame(log_notebook, padding=8)
        log_notebook.add(operator_tab, text="Operator")
        self.log_text = scrolledtext.ScrolledText(
            operator_tab,
            height=24,
            bg="#000000",
            fg="#00FF00",
            insertbackground="#00FF00",
            font=("Consolas", 10),
        )
        self.log_text.pack(fill="both", expand=True)

        evidence_tab = ttk.Frame(log_notebook, padding=8)
        log_notebook.add(evidence_tab, text="Evidence")
        evidence_header = ttk.Frame(evidence_tab)
        evidence_header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(evidence_header, textvariable=self.evidence_summary_var).pack(side="left", fill="x", expand=True)
        ttk.Button(evidence_header, text="Refresh", command=self._refresh_evidence_view).pack(side="right")

        event_columns = ("created_at", "kind", "summary")
        self.evidence_tree = ttk.Treeview(evidence_tab, columns=event_columns, show="headings", height=14)
        event_headings = {
            "created_at": "Time",
            "kind": "Kind",
            "summary": "Summary",
        }
        event_widths = {
            "created_at": 170,
            "kind": 160,
            "summary": 620,
        }
        for column in event_columns:
            self.evidence_tree.heading(
                column,
                text=event_headings[column],
                command=lambda column_name=column: self._sort_events_by(column_name),
            )
            self.evidence_tree.column(column, width=event_widths[column], stretch=(column == "summary"), anchor="w")
        evidence_scrollbar = ttk.Scrollbar(evidence_tab, orient="vertical", command=self.evidence_tree.yview)
        self.evidence_tree.configure(yscrollcommand=evidence_scrollbar.set)
        self.evidence_tree.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        evidence_scrollbar.grid(row=1, column=1, sticky="ns", pady=(10, 0))
        self.evidence_tree.bind("<<TreeviewSelect>>", self._on_event_selected)

        detail_frame = ttk.LabelFrame(evidence_tab, text="Event detail", padding=8)
        detail_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        self.evidence_detail_text = scrolledtext.ScrolledText(detail_frame, height=12, font=("Consolas", 10))
        self.evidence_detail_text.pack(fill="both", expand=True)

        evidence_tab.columnconfigure(0, weight=1)
        evidence_tab.rowconfigure(1, weight=1)
        evidence_tab.rowconfigure(2, weight=1)

    def _set_generic_controls_enabled(self, enabled: bool) -> None:
        if enabled:
            self.generic_availability_var.set("Generic pymem-backed features are available.")
        else:
            self.generic_availability_var.set(
                f"Generic pymem-backed features are unavailable: {PYMEM_IMPORT_ERROR}"
            )

    @staticmethod
    def _set_widget_enabled(widget: tk.Widget, enabled: bool) -> None:
        widget.state(["!disabled"] if enabled else ["disabled"])

    def _refresh_generic_control_states(self) -> None:
        generic_available = PYMEM_AVAILABLE
        generic_background_busy = self.generic_background_jobs > 0
        monitor_active = self.monitor_thread is not None and self.monitor_thread.is_alive()

        process_mutation_enabled = generic_available and not generic_background_busy
        self._set_widget_enabled(self.attach_button, process_mutation_enabled)
        self._set_widget_enabled(self.detach_button, process_mutation_enabled)
        self._set_widget_enabled(self.attach_rift_button, process_mutation_enabled)
        self._set_widget_enabled(self.attach_last_snapshot_button, process_mutation_enabled)

        self._set_widget_enabled(
            self.aob_scan_button,
            generic_available and not generic_background_busy and not self.scan_in_progress,
        )
        self._set_widget_enabled(self.aob_use_snapshot_process_button, generic_available)
        self._set_widget_enabled(self.pointer_button, generic_available and not generic_background_busy)
        self._set_widget_enabled(self.pointer_use_snapshot_button, generic_available)
        self._set_widget_enabled(
            self.monitor_start_button,
            generic_available and not generic_background_busy and not monitor_active,
        )
        self._set_widget_enabled(self.monitor_stop_button, generic_available and monitor_active)
        self._set_widget_enabled(self.monitor_use_snapshot_button, generic_available)
        self._set_widget_enabled(
            self.hex_read_button,
            generic_available and not generic_background_busy and not self.hex_read_in_progress,
        )
        self._set_widget_enabled(self.hex_use_snapshot_button, generic_available)

    def _begin_generic_background_job(self) -> bool:
        if self.generic_background_jobs > 0:
            self.status_var.set("Wait for the current generic operation to finish")
            messagebox.showinfo(
                "Generic operation in progress",
                "Wait for the current generic background operation to finish.",
            )
            return False

        self.generic_background_jobs += 1
        self._refresh_generic_control_states()
        return True

    def _end_generic_background_job(self) -> None:
        self.generic_background_jobs = max(0, self.generic_background_jobs - 1)
        self._refresh_generic_control_states()

    def _ensure_generic_background_idle(self, action_description: str) -> bool:
        if self.generic_background_jobs <= 0:
            return True

        self.status_var.set("Wait for the current generic operation to finish")
        messagebox.showinfo(
            "Generic operation in progress",
            f"Wait for the current generic background operation to finish before {action_description}.",
        )
        return False

    def _refresh_repo_control_states(self) -> None:
        repo_busy = self.repo_background_jobs > 0
        missing_core = self.rift_bridge.validate_core()
        missing_dashboard = self.rift_bridge.validate_dashboard(live=False)
        missing_live_dashboard = self.rift_bridge.validate_dashboard(live=True)

        core_ready = not missing_core and not repo_busy
        dashboard_ready = not missing_dashboard and not repo_busy
        live_dashboard_ready = not missing_live_dashboard and not repo_busy

        if hasattr(self, "rift_read_button"):
            self._set_widget_enabled(self.rift_read_button, core_ready)
            self._set_widget_enabled(self.rift_debug_button, core_ready)
            self._set_widget_enabled(self.rift_dashboard_button, dashboard_ready)
            self._set_widget_enabled(self.rift_live_dashboard_button, live_dashboard_ready)

        if hasattr(self, "recovery_build_button"):
            self._set_widget_enabled(self.recovery_build_button, core_ready)
            self._set_widget_enabled(self.recovery_baseline_button, core_ready)
            self._set_widget_enabled(self.recovery_source_chain_button, core_ready)
            self._set_widget_enabled(self.recovery_core_graph_button, core_ready)
            self._set_widget_enabled(self.recovery_consistency_button, core_ready)
            self._set_widget_enabled(self.recovery_export_button, core_ready and not repo_busy)

    def _begin_repo_background_job(self, action_description: str) -> bool:
        if self.repo_background_jobs > 0:
            self.status_var.set("Wait for the current Rift/recovery action to finish")
            messagebox.showinfo(
                "Rift/recovery action in progress",
                f"Wait for the current Rift/recovery action to finish before {action_description}.",
            )
            return False
        self.repo_background_jobs += 1
        self._refresh_repo_control_states()
        return True

    def _end_repo_background_job(self) -> None:
        self.repo_background_jobs = max(0, self.repo_background_jobs - 1)
        self._refresh_repo_control_states()

    @staticmethod
    def _set_text_widget_content(widget: scrolledtext.ScrolledText, text: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text.rstrip() + ("\n" if text else ""))

    @staticmethod
    def _set_entry_text(widget: ttk.Entry, value: str) -> None:
        widget.delete(0, tk.END)
        widget.insert(0, value)

    def _load_ui_state(self) -> None:
        if not self.discovery_store:
            return
        state = self.discovery_store.get_setting("ui_state", {})
        if not isinstance(state, dict):
            return

        if isinstance(state.get("process_name"), str):
            self._set_entry_text(self.proc_entry, state["process_name"])
        if isinstance(state.get("aob_pattern"), str):
            self._set_entry_text(self.aob_entry, state["aob_pattern"])
        if isinstance(state.get("aob_module"), str):
            self._set_entry_text(self.aob_module_entry, state["aob_module"])
        if isinstance(state.get("pointer_base"), str):
            self._set_entry_text(self.base_entry, state["pointer_base"])
        if isinstance(state.get("pointer_offsets"), str):
            self._set_entry_text(self.offset_entry, state["pointer_offsets"])
        if isinstance(state.get("monitor_address"), str):
            self._set_entry_text(self.monitor_entry, state["monitor_address"])
        if isinstance(state.get("monitor_interval"), str):
            self._set_entry_text(self.monitor_interval_entry, state["monitor_interval"])
        if isinstance(state.get("monitor_type"), str):
            self.type_var.set(state["monitor_type"])
        if isinstance(state.get("hex_address"), str):
            self._set_entry_text(self.hex_address_entry, state["hex_address"])
        if isinstance(state.get("hex_length"), str):
            self._set_entry_text(self.hex_length_entry, state["hex_length"])
        if isinstance(state.get("repo_root"), str):
            self._set_entry_text(self.repo_entry, state["repo_root"])

        candidate_filters = state.get("candidate_filters")
        if isinstance(candidate_filters, dict):
            self.candidate_filter_status_var.set(str(candidate_filters.get("status", "All")))
            self.candidate_filter_kind_var.set(str(candidate_filters.get("kind", "All")))
            self.candidate_filter_source_var.set(str(candidate_filters.get("source", "All")))
            self.candidate_filter_view_var.set(str(candidate_filters.get("view", "All")))
            self.candidate_filter_search_var.set(str(candidate_filters.get("search", "")))

        import_filters = state.get("import_filters")
        if isinstance(import_filters, dict):
            self.import_filter_status_var.set(str(import_filters.get("status", "All")))
            self.import_filter_search_var.set(str(import_filters.get("search", "")))
            self.import_source_var.set(str(import_filters.get("source", "All")))

    def _save_ui_state(self) -> None:
        if not self.discovery_store:
            return
        self.discovery_store.set_setting(
            "ui_state",
            {
                "process_name": self.proc_entry.get().strip(),
                "aob_pattern": self.aob_entry.get().strip(),
                "aob_module": self.aob_module_entry.get().strip(),
                "pointer_base": self.base_entry.get().strip(),
                "pointer_offsets": self.offset_entry.get().strip(),
                "monitor_address": self.monitor_entry.get().strip(),
                "monitor_interval": self.monitor_interval_entry.get().strip(),
                "monitor_type": self.type_var.get(),
                "hex_address": self.hex_address_entry.get().strip(),
                "hex_length": self.hex_length_entry.get().strip(),
                "repo_root": self.repo_entry.get().strip(),
                "candidate_filters": {
                    "status": self.candidate_filter_status_var.get(),
                    "kind": self.candidate_filter_kind_var.get(),
                    "source": self.candidate_filter_source_var.get(),
                    "view": self.candidate_filter_view_var.get(),
                    "search": self.candidate_filter_search_var.get(),
                },
                "import_filters": {
                    "status": self.import_filter_status_var.get(),
                    "search": self.import_filter_search_var.get(),
                    "source": self.import_source_var.get(),
                },
            },
        )

    def _reset_candidate_filters(self) -> None:
        self.candidate_filter_status_var.set("All")
        self.candidate_filter_kind_var.set("All")
        self.candidate_filter_source_var.set("All")
        self.candidate_filter_view_var.set("All")
        self.candidate_filter_search_var.set("")
        self._refresh_candidates_view()

    def _reset_import_filters(self) -> None:
        self.import_filter_status_var.set("All")
        self.import_filter_search_var.set("")
        self.import_source_var.set("All")
        self._refresh_imports_view()

    def _record_store_event(self, kind: str, summary: str, metadata: dict | None = None) -> None:
        if not self.discovery_store:
            return

        try:
            self.discovery_store.add_event(kind, summary, metadata)
        except Exception as exc:
            self.logger.warning("Failed to persist scanner event '%s': %s", kind, exc)
            return

        if hasattr(self, "evidence_tree"):
            self._refresh_evidence_view()

    def _persist_candidate(self, *, refresh_view: bool = True, **kwargs: object) -> int | None:
        if not self.discovery_store:
            return None

        metadata = kwargs.get("metadata")
        metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}
        source_tags = {
            str(tag)
            for tag in metadata_payload.get("source_tags", [])
            if isinstance(tag, str) and tag.strip()
        }
        for key_name in ("kind", "status", "source_kind"):
            value = kwargs.get(key_name)
            if isinstance(value, str) and value.strip():
                source_tags.add(value.strip())

        absolute_address = kwargs.get("absolute_address")
        if isinstance(absolute_address, int) and self.last_rift_snapshot and self.last_rift_snapshot.address_hex:
            try:
                anchor_address = int(self.last_rift_snapshot.address_hex, 16)
                metadata_payload.setdefault("anchor_distance", abs(absolute_address - anchor_address))
                metadata_payload.setdefault("anchor_reference", self.last_rift_snapshot.address_hex)
            except ValueError:
                pass

        if source_tags:
            metadata_payload["source_tags"] = sorted(source_tags)
        kwargs["metadata"] = metadata_payload

        try:
            candidate_id = self.discovery_store.upsert_candidate(**kwargs)
        except Exception as exc:
            self.logger.warning("Failed to persist candidate '%s': %s", kwargs.get("label", "unknown"), exc)
            return None

        if refresh_view and hasattr(self, "candidate_tree"):
            self._refresh_candidates_view()
        return candidate_id

    def _copy_to_clipboard(self, text: str, success_message: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self.status_var.set(success_message)

    def _sort_candidates_by(self, column_name: str) -> None:
        if self.candidate_sort_column == column_name:
            self.candidate_sort_reverse = not self.candidate_sort_reverse
        else:
            self.candidate_sort_column = column_name
            self.candidate_sort_reverse = column_name in {"confidence", "last_seen"}
        self._refresh_candidates_view()

    def _sort_imports_by(self, column_name: str) -> None:
        if self.import_sort_column == column_name:
            self.import_sort_reverse = not self.import_sort_reverse
        else:
            self.import_sort_column = column_name
            self.import_sort_reverse = column_name in {"confidence", "resolved"}
        self._refresh_imports_view()

    def _sort_events_by(self, column_name: str) -> None:
        if self.event_sort_column == column_name:
            self.event_sort_reverse = not self.event_sort_reverse
        else:
            self.event_sort_column = column_name
            self.event_sort_reverse = column_name == "created_at"
        self._refresh_evidence_view()

    def _candidate_matches_filter(self, record: CandidateRecord) -> bool:
        status_filter = self.candidate_filter_status_var.get().strip()
        if status_filter and status_filter != "All" and record.status != status_filter:
            return False

        kind_filter = self.candidate_filter_kind_var.get().strip()
        if kind_filter and kind_filter != "All" and record.kind != kind_filter:
            return False

        source_filter = self.candidate_filter_source_var.get().strip()
        if source_filter and source_filter != "All" and (record.source_kind or "") != source_filter:
            return False

        view_filter = self.candidate_filter_view_var.get().strip()
        post_update_cutoff = self.recovery_snapshot.current_truth_last_updated_iso if self.recovery_snapshot else None
        last_seen = record.last_verified_at or record.last_seen_at
        if view_filter == "Survivors since update":
            if post_update_cutoff and last_seen < post_update_cutoff:
                return False
            if record.status in {"stale", "broken"}:
                return False
        elif view_filter == "Broken / stale":
            if record.status not in {"stale", "broken"}:
                return False
        elif view_filter == "Imported unresolved":
            if record.source_kind != "ct-import" or record.status in {"promoted", "confirmed"}:
                return False

        search_text = self.candidate_filter_search_var.get().strip().lower()
        if search_text:
            search_haystack = " ".join(
                [
                    record.label,
                    record.canonical_key,
                    record.kind,
                    record.status,
                    record.source_kind or "",
                    record.module_name or "",
                    record.address_hex,
                ]
            ).lower()
            if search_text not in search_haystack:
                return False

        return True

    def _candidate_sort_key(self, record: CandidateRecord, column_name: str) -> object:
        if column_name == "kind":
            return record.kind
        if column_name == "status":
            return record.status
        if column_name == "confidence":
            return record.confidence
        if column_name == "address":
            return record.absolute_address or -1
        if column_name == "source":
            return record.source_kind or ""
        if column_name == "last_seen":
            return record.last_verified_at or record.last_seen_at
        return record.label.lower()

    def _format_candidate_evidence(self, candidate_id: int) -> str:
        if not self.discovery_store:
            return "Discovery store unavailable."
        evidence_rows = self.discovery_store.list_candidate_evidence(candidate_id, limit=100)
        if not evidence_rows:
            return "No evidence rows recorded for this candidate."

        lines: list[str] = []
        for evidence in evidence_rows:
            lines.append(f"{evidence.created_at} | {evidence.event_kind} | {evidence.summary}")
            if evidence.metadata:
                lines.append(json.dumps(evidence.metadata, indent=2, sort_keys=True))
            lines.append("")
        return "\n".join(lines).strip()

    def _refresh_candidates_view(self) -> None:
        if not hasattr(self, "candidate_tree"):
            return

        for item_id in self.candidate_tree.get_children():
            self.candidate_tree.delete(item_id)

        self.candidate_records = {}
        if not self.discovery_store:
            reason = self.discovery_store_error or "Discovery store unavailable."
            self.candidate_summary_var.set(reason)
            self._set_text_widget_content(self.candidate_detail, reason)
            self._set_text_widget_content(self.candidate_evidence_text, reason)
            return

        try:
            records = self.discovery_store.list_candidates(limit=5000)
            summary = self.discovery_store.get_summary()
        except Exception as exc:
            message = f"Failed to load candidates: {exc}"
            self.candidate_summary_var.set(message)
            self._set_text_widget_content(self.candidate_detail, message)
            self._set_text_widget_content(self.candidate_evidence_text, message)
            self.logger.warning(message)
            return

        source_values = ["All", *sorted({record.source_kind for record in records if record.source_kind})]
        self.candidate_source_combo.configure(values=tuple(source_values))
        if self.candidate_filter_source_var.get() not in source_values:
            self.candidate_filter_source_var.set("All")

        filtered_records = [record for record in records if self._candidate_matches_filter(record)]
        filtered_records.sort(
            key=lambda record: self._candidate_sort_key(record, self.candidate_sort_column),
            reverse=self.candidate_sort_reverse,
        )

        for record in filtered_records:
            self.candidate_records[record.candidate_id] = record
            tree_id = str(record.candidate_id)
            self.candidate_tree.insert(
                "",
                tk.END,
                iid=tree_id,
                values=(
                    record.kind,
                    record.status,
                    f"{record.confidence:.2f}",
                    record.address_hex or "n/a",
                    record.source_kind or "n/a",
                    record.last_verified_at or record.last_seen_at,
                    record.label,
                ),
            )

        started_at = self.discovery_store.session_started_at or "n/a"
        self.candidate_summary_var.set(
            "Visible: {visible} / {candidate_count} | Events: {event_count} | Imports: {import_count} "
            "| Sessions: {session_count} | Current session: {started_at} | DB: {db_path}".format(
                visible=len(filtered_records),
                candidate_count=summary["candidate_count"],
                event_count=summary["event_count"],
                import_count=summary["import_count"],
                session_count=summary["session_count"],
                started_at=started_at,
                db_path=self.discovery_store.db_path,
            )
        )
        if filtered_records:
            self._set_text_widget_content(
                self.candidate_detail,
                "Select a candidate to inspect its canonical key, metadata, artifact path, and import lineage.",
            )
            self._set_text_widget_content(
                self.candidate_evidence_text,
                "Select a candidate to inspect its evidence trail.",
            )
        else:
            self._set_text_widget_content(
                self.candidate_detail,
                "No candidates matched the current filters.",
            )
            self._set_text_widget_content(
                self.candidate_evidence_text,
                "No evidence rows are visible for the current candidate selection.",
            )

        self._save_ui_state()

    def _format_candidate_detail(self, record: CandidateRecord) -> str:
        canonical_spec = {
            "candidate_id": record.candidate_id,
            "canonical_key": record.canonical_key,
            "kind": record.kind,
            "label": record.label,
            "status": record.status,
            "confidence": record.confidence,
            "value_type": record.value_type,
            "module_name": record.module_name,
            "module_rva": f"0x{record.module_rva:X}" if record.module_rva is not None else None,
            "absolute_address": record.address_hex or None,
            "source_kind": record.source_kind,
            "artifact_path": record.artifact_path,
            "notes": record.notes,
            "metadata": record.metadata,
        }
        lines = [
            f"ID:             {record.candidate_id}",
            f"Label:          {record.label}",
            f"Kind:           {record.kind}",
            f"Status:         {record.status}",
            f"Confidence:     {record.confidence:.2f}",
            f"Address:        {record.address_hex or 'n/a'}",
            f"Value type:     {record.value_type or 'n/a'}",
            f"Module:         {record.module_name or 'n/a'}",
            f"Module RVA:     {f'0x{record.module_rva:X}' if record.module_rva is not None else 'n/a'}",
            f"Source:         {record.source_kind or 'n/a'}",
            f"Evidence rows:  {record.evidence_count}",
            f"First seen:     {record.first_seen_at}",
            f"Last seen:      {record.last_seen_at}",
            f"Last verified:  {record.last_verified_at or 'n/a'}",
            f"Last game build:{record.last_game_build or 'n/a'}",
            f"Artifact path:  {record.artifact_path or 'n/a'}",
            f"Canonical key:  {record.canonical_key}",
        ]
        if record.notes:
            lines.extend(["", "Notes:", record.notes])
        if record.metadata:
            lines.extend(["", "Metadata:", json.dumps(record.metadata, indent=2, sort_keys=True)])
        lines.extend(["", "Canonical spec:", json.dumps(canonical_spec, indent=2, sort_keys=True)])
        return "\n".join(lines)

    def _selected_candidate_record(self) -> CandidateRecord | None:
        if not hasattr(self, "candidate_tree"):
            return None
        selection = self.candidate_tree.selection()
        if not selection:
            return None
        try:
            candidate_id = int(selection[0])
        except ValueError:
            return None
        return self.candidate_records.get(candidate_id)

    def _on_candidate_selected(self, _event: object | None = None) -> None:
        record = self._selected_candidate_record()
        if not record:
            return
        self._set_text_widget_content(self.candidate_detail, self._format_candidate_detail(record))
        self._set_text_widget_content(self.candidate_evidence_text, self._format_candidate_evidence(record.candidate_id))

    def _update_selected_candidate_status(self, status: str) -> None:
        record = self._selected_candidate_record()
        if not record or not self.discovery_store:
            messagebox.showinfo("No candidate selected", "Select a candidate first.")
            return
        note = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | status -> {status}"
        try:
            self.discovery_store.update_candidate_status(
                record.candidate_id,
                status,
                note=note,
                verified=status in {"promoted", "confirmed"},
            )
        except Exception as exc:
            messagebox.showerror("Candidate update failed", str(exc))
            return
        self._record_store_event(
            "candidate-status",
            f"Candidate {record.candidate_id} marked {status}",
            {"candidate_id": record.candidate_id, "canonical_key": record.canonical_key, "status": status},
        )
        self._refresh_candidates_view()

    def _copy_selected_candidate_spec(self) -> None:
        record = self._selected_candidate_record()
        if not record:
            messagebox.showinfo("No candidate selected", "Select a candidate first.")
            return
        self._copy_to_clipboard(self._format_candidate_detail(record), "Copied candidate spec")

    def _use_selected_candidate_address(self, entry: ttk.Entry, label: str) -> None:
        record = self._selected_candidate_record()
        if not record or record.absolute_address is None:
            messagebox.showinfo("No address available", "Select a candidate with a resolved address first.")
            return
        self._set_entry_text(entry, record.address_hex)
        self.status_var.set(f"Loaded selected candidate address into {label}")

    def _selected_import_source_id(self) -> int | None:
        selected = self.import_source_var.get().strip()
        if not selected or selected == "All":
            return None
        try:
            return int(selected.split(":", 1)[0])
        except ValueError:
            return None

    def _import_matches_filter(self, record: ImportEntryRecord) -> bool:
        selected_source_id = self._selected_import_source_id()
        if selected_source_id is not None and record.import_id != selected_source_id:
            return False
        status_filter = self.import_filter_status_var.get().strip()
        if status_filter and status_filter != "All" and record.status != status_filter:
            return False
        search_text = self.import_filter_search_var.get().strip().lower()
        if search_text:
            haystack = " ".join(
                [
                    record.label,
                    record.group_path or "",
                    record.kind,
                    record.status,
                    record.value_type or "",
                    record.address_expression or "",
                    record.resolved_address_hex,
                ]
            ).lower()
            if search_text not in haystack:
                return False
        return True

    def _import_sort_key(self, record: ImportEntryRecord, column_name: str) -> object:
        if column_name == "status":
            return record.status
        if column_name == "kind":
            return record.kind
        if column_name == "confidence":
            return record.confidence
        if column_name == "resolved":
            return record.resolved_address or -1
        if column_name == "type":
            return record.value_type or ""
        if column_name == "group":
            return record.group_path or ""
        return record.label.lower()

    def _format_import_entry_detail(self, record: ImportEntryRecord) -> str:
        import_record = self.import_sources.get(record.import_id)
        lines = [
            f"Entry ID:        {record.entry_id}",
            f"Import ID:       {record.import_id}",
            f"Import source:   {import_record.source_path if import_record else 'n/a'}",
            f"Label:           {record.label}",
            f"Group path:      {record.group_path or 'n/a'}",
            f"Kind:            {record.kind}",
            f"Status:          {record.status}",
            f"Confidence:      {record.confidence:.2f}",
            f"Value type:      {record.value_type or 'n/a'}",
            f"Address expr:    {record.address_expression or 'n/a'}",
            f"Resolved addr:   {record.resolved_address_hex or 'n/a'}",
            f"Module:          {record.module_name or 'n/a'}",
            f"Module RVA:      {f'0x{record.module_rva:X}' if record.module_rva is not None else 'n/a'}",
            f"Offsets:         {', '.join(f'0x{offset:X}' for offset in record.offsets) or 'n/a'}",
            f"Last resolved:   {record.last_resolved_at or 'n/a'}",
            f"Last error:      {record.last_error or 'n/a'}",
            f"Promoted cand.:  {record.promoted_candidate_id or 'n/a'}",
            f"Import key:      {record.import_key}",
        ]
        if record.notes:
            lines.extend(["", "Notes:", record.notes])
        if record.metadata:
            lines.extend(["", "Metadata:", json.dumps(record.metadata, indent=2, sort_keys=True)])
        return "\n".join(lines)

    def _refresh_imports_view(self) -> None:
        if not hasattr(self, "import_tree"):
            return

        for item_id in self.import_tree.get_children():
            self.import_tree.delete(item_id)
        self.import_records = {}
        self.import_sources = {}

        if not self.discovery_store:
            message = self.discovery_store_error or "Discovery store unavailable."
            self.import_summary_var.set(message)
            self._set_text_widget_content(self.import_detail_text, message)
            return

        try:
            imports = self.discovery_store.list_imports(limit=200)
            records = self.discovery_store.list_import_entries(limit=5000)
        except Exception as exc:
            message = f"Failed to load imports: {exc}"
            self.import_summary_var.set(message)
            self._set_text_widget_content(self.import_detail_text, message)
            return

        self.import_sources = {record.import_id: record for record in imports}
        source_values = ["All", *[f"{record.import_id}: {record.label}" for record in imports]]
        self.import_source_combo.configure(values=tuple(source_values))
        if self.import_source_var.get() not in source_values:
            self.import_source_var.set("All")

        filtered_records = [record for record in records if self._import_matches_filter(record)]
        filtered_records.sort(
            key=lambda record: self._import_sort_key(record, self.import_sort_column),
            reverse=self.import_sort_reverse,
        )
        for record in filtered_records:
            self.import_records[record.entry_id] = record
            self.import_tree.insert(
                "",
                tk.END,
                iid=str(record.entry_id),
                values=(
                    record.status,
                    record.kind,
                    f"{record.confidence:.2f}",
                    record.resolved_address_hex or "n/a",
                    record.value_type or "n/a",
                    record.group_path or "n/a",
                    record.label,
                ),
            )

        warning_count = sum(import_record.warning_count for import_record in imports)
        self.import_summary_var.set(
            "Imports: {imports} | Entries: {entries} | Visible: {visible} | Warnings: {warnings}".format(
                imports=len(imports),
                entries=len(records),
                visible=len(filtered_records),
                warnings=warning_count,
            )
        )
        if filtered_records:
            self._set_text_widget_content(
                self.import_detail_text,
                "Select an imported entry to inspect its CT expression, offsets, and promotion state.",
            )
        else:
            self._set_text_widget_content(
                self.import_detail_text,
                "Import a Cheat Engine table or loosen the current import filters.",
            )
        self._save_ui_state()

    def _selected_import_records(self) -> list[ImportEntryRecord]:
        if not hasattr(self, "import_tree"):
            return []
        records: list[ImportEntryRecord] = []
        for item_id in self.import_tree.selection():
            try:
                entry_id = int(item_id)
            except ValueError:
                continue
            record = self.import_records.get(entry_id)
            if record:
                records.append(record)
        return records

    def _visible_import_records(self) -> list[ImportEntryRecord]:
        records: list[ImportEntryRecord] = []
        for item_id in self.import_tree.get_children():
            try:
                entry_id = int(item_id)
            except ValueError:
                continue
            record = self.import_records.get(entry_id)
            if record:
                records.append(record)
        return records

    def _on_import_selected(self, _event: object | None = None) -> None:
        selected = self._selected_import_records()
        if not selected:
            return
        self._set_text_widget_content(self.import_detail_text, self._format_import_entry_detail(selected[0]))

    def import_ct_table(self) -> None:
        if not self.discovery_store:
            messagebox.showerror("Discovery store unavailable", "The discovery store is not available.")
            return

        path = filedialog.askopenfilename(
            title="Import Cheat Engine table",
            filetypes=[("Cheat Engine tables", "*.ct"), ("XML files", "*.xml"), ("All files", "*.*")],
            initialdir=str(self.rift_bridge.repo_root),
        )
        if not path:
            return

        try:
            table = parse_cheat_table(path)
        except Exception as exc:
            messagebox.showerror("CT import failed", str(exc))
            return

        try:
            import_id = self._import_ct_table_payload(table)
        except Exception as exc:
            messagebox.showerror("CT import failed", str(exc))
            return

        self.import_source_var.set(f"{import_id}: {table.label}")
        self._refresh_imports_view()
        self._record_store_event(
            "ct-import",
            f"Imported Cheat Engine table {Path(path).name}",
            {
                "path": str(Path(path).resolve()),
                "entry_count": len(table.entries),
                "warning_count": len(table.warnings),
            },
        )
        self.status_var.set(f"Imported Cheat Engine table: {Path(path).name}")

    def _import_ct_table_payload(self, table: CtImportTable) -> int:
        assert self.discovery_store is not None
        import_id = self.discovery_store.create_import(
            source_path=str(table.source_path),
            label=table.label,
            entry_count=len(table.entries),
            warning_count=len(table.warnings),
            notes="\n".join(table.warnings) if table.warnings else None,
            metadata={"warnings": table.warnings},
        )
        rows = [
            {
                "import_key": entry.import_key,
                "label": entry.label,
                "group_path": entry.group_path,
                "kind": entry.kind,
                "status": "imported",
                "confidence": 0.10 if entry.kind == "group" else 0.45,
                "value_type": entry.value_type,
                "address_expression": entry.address_expression,
                "module_name": entry.module_name,
                "module_rva": entry.module_rva,
                "resolved_address": entry.absolute_address,
                "offsets": entry.offsets,
                "notes": entry.notes,
                "metadata": {**entry.metadata, "absolute_address": entry.absolute_address},
                "last_resolved_at": None,
                "last_error": None,
                "promoted_candidate_id": None,
            }
            for entry in table.entries
        ]
        self.discovery_store.replace_import_entries(import_id, rows)
        return import_id

    def _resolve_import_entry_live(self, record: ImportEntryRecord) -> dict[str, object]:
        if record.kind == "group":
            raise ScannerError("Group rows are organizational only and cannot be resolved.")

        metadata = dict(record.metadata)
        resolved_address: int | None = None
        confidence = max(record.confidence, 0.50)
        module_name = record.module_name
        module_rva = record.module_rva
        parsed = parse_address_expression(record.address_expression)

        if parsed.kind in {"module-relative"} or (module_name and module_rva is not None):
            module_name = parsed.module_name or module_name
            module_rva = parsed.module_rva if parsed.module_rva is not None else module_rva
            if module_name is None or module_rva is None:
                raise ScannerError("Module-relative import entry did not include a module base and offset.")
            base_address = self.generic_scanner.resolve_module_relative(module_name, module_rva)
            resolved_address = (
                self.generic_scanner.resolve_pointer_chain(base_address, record.offsets)
                if record.offsets
                else base_address
            )
            confidence = 0.82 if record.offsets else 0.88
        elif parsed.kind == "absolute" or metadata.get("absolute_address") is not None:
            base_address = parsed.absolute_address
            if base_address is None:
                base_address = int(metadata["absolute_address"])
            resolved_address = (
                self.generic_scanner.resolve_pointer_chain(base_address, record.offsets)
                if record.offsets
                else base_address
            )
            confidence = 0.70 if record.offsets else 0.62
        elif parsed.kind in {"aobscan", "aobscanmodule"}:
            pattern_text = parsed.aob_pattern or metadata.get("aob_pattern")
            if not pattern_text:
                raise ScannerError("AOB import entry did not include a pattern.")
            scan_module = parsed.aob_module or record.module_name
            scan_result = self.generic_scanner.aob_scan(
                pattern_text,
                scan_module if parsed.kind == "aobscanmodule" else None,
            )
            if not scan_result.addresses:
                raise ScannerError("AOB import entry did not resolve to any matches.")
            resolved_address = scan_result.addresses[0]
            confidence = 0.78 if len(scan_result.addresses) == 1 else 0.58
            metadata["aob_hit_count"] = len(scan_result.addresses)
            if parsed.kind == "aobscanmodule" and scan_module:
                module_name = scan_module
                try:
                    module_base = self.generic_scanner.get_module_base(scan_module)
                    module_rva = resolved_address - module_base
                except Exception:
                    module_rva = module_rva
        else:
            raise ScannerError(f"Unsupported CT address expression: {record.address_expression or '(blank)'}")

        if resolved_address is None:
            raise ScannerError("Import entry did not resolve to an address.")

        if self.last_rift_snapshot and self.last_rift_snapshot.address_hex:
            try:
                anchor_address = int(self.last_rift_snapshot.address_hex, 16)
                metadata["anchor_distance"] = abs(resolved_address - anchor_address)
            except ValueError:
                pass

        metadata["resolved_via"] = "ct-import"
        metadata["resolved_address"] = f"0x{resolved_address:X}"
        if module_name:
            metadata["module_name"] = module_name
        if module_rva is not None:
            metadata["module_rva"] = module_rva

        return {
            "status": "resolved",
            "confidence": confidence,
            "resolved_address": resolved_address,
            "module_name": module_name,
            "module_rva": module_rva,
            "metadata": metadata,
        }

    def resolve_import_entries(self, *, selected_only: bool) -> None:
        if not self.discovery_store:
            messagebox.showerror("Discovery store unavailable", "The discovery store is not available.")
            return
        if not self.generic_scanner.pm:
            messagebox.showerror("No process attached", "Attach to a process before resolving imported entries.")
            return
        if not self._begin_generic_background_job():
            return

        targets = self._selected_import_records() if selected_only else self._visible_import_records()
        targets = [record for record in targets if record.kind != "group"]
        if not targets:
            self._end_generic_background_job()
            messagebox.showinfo("No import entries", "Select or display at least one resolvable import entry.")
            return

        self.status_var.set(f"Resolving {len(targets)} imported entry(ies)")

        def worker() -> list[tuple[int, dict[str, object] | str]]:
            results: list[tuple[int, dict[str, object] | str]] = []
            for record in targets:
                try:
                    results.append((record.entry_id, self._resolve_import_entry_live(record)))
                except Exception as exc:
                    results.append((record.entry_id, str(exc)))
            return results

        def on_success(result: object) -> None:
            typed_result = self._require_result_type(result, list, "CT resolve")
            resolved = 0
            failed = 0
            for entry_id, payload in typed_result:
                existing = self.discovery_store.get_import_entry(entry_id)
                if existing is None:
                    continue
                if isinstance(payload, dict):
                    self.discovery_store.update_import_entry_resolution(
                        entry_id,
                        status=str(payload["status"]),
                        confidence=float(payload["confidence"]),
                        resolved_address=int(payload["resolved_address"]),
                        module_name=payload.get("module_name"),
                        module_rva=payload.get("module_rva"),
                        metadata=payload.get("metadata"),
                        last_error=None,
                    )
                    resolved += 1
                else:
                    status = "broken" if "Unsupported CT address expression" in payload else "stale"
                    self.discovery_store.update_import_entry_resolution(
                        entry_id,
                        status=status,
                        confidence=0.25 if status == "stale" else 0.10,
                        resolved_address=existing.resolved_address,
                        module_name=existing.module_name,
                        module_rva=existing.module_rva,
                        metadata=existing.metadata,
                        last_error=payload,
                    )
                    failed += 1

            self._record_store_event(
                "ct-resolve-batch",
                f"Resolved {resolved} imported entries ({failed} failed)",
                {"resolved": resolved, "failed": failed, "selected_only": selected_only},
            )
            self._refresh_imports_view()
            self._refresh_candidates_view()
            self.status_var.set(f"CT resolve completed: {resolved} resolved, {failed} failed")

        def on_error(exc: Exception) -> None:
            messagebox.showerror("CT resolve failed", str(exc))

        def on_finally() -> None:
            self._end_generic_background_job()

        self._run_in_background(worker, on_success, on_error, on_finally)

    def promote_import_entries(self, *, selected_only: bool) -> None:
        if not self.discovery_store:
            messagebox.showerror("Discovery store unavailable", "The discovery store is not available.")
            return

        targets = self._selected_import_records() if selected_only else self._visible_import_records()
        if not selected_only:
            targets = [record for record in targets if record.status in {"resolved", "promoted"}]
        if not targets:
            messagebox.showinfo("No import entries", "No import entries matched the promotion criteria.")
            return

        promoted = 0
        for record in targets:
            resolved_address = record.resolved_address
            if resolved_address is None:
                continue
            import_record = self.import_sources.get(record.import_id)
            candidate_id = self._persist_candidate(
                refresh_view=False,
                canonical_key=f"ct-import::{record.import_key}",
                kind=record.kind if record.kind != "group" else "ct-import",
                label=record.label,
                status="promoted",
                confidence=max(record.confidence, 0.80),
                value_type=record.value_type,
                module_name=record.module_name,
                module_rva=record.module_rva,
                absolute_address=resolved_address,
                source_kind="ct-import",
                notes=record.notes,
                metadata={
                    **record.metadata,
                    "group_path": record.group_path,
                    "address_expression": record.address_expression,
                    "offsets": record.offsets,
                    "import_id": record.import_id,
                    "import_source_path": import_record.source_path if import_record else None,
                    "resolved_via": "ct-import",
                },
                verified=True,
                evidence_kind="ct-import-promotion",
                evidence_summary=f"Imported CT entry promoted at {record.resolved_address_hex}",
                evidence_metadata={
                    "import_entry_id": record.entry_id,
                    "resolved_address": record.resolved_address_hex,
                    "group_path": record.group_path,
                },
            )
            if candidate_id is None:
                continue
            self.discovery_store.attach_import_entry_candidate(record.entry_id, candidate_id)
            self.discovery_store.update_import_entry_resolution(
                record.entry_id,
                status="promoted",
                confidence=max(record.confidence, 0.85),
                resolved_address=resolved_address,
                module_name=record.module_name,
                module_rva=record.module_rva,
                metadata=record.metadata,
                promoted_candidate_id=candidate_id,
            )
            promoted += 1

        self._record_store_event(
            "ct-promote-batch",
            f"Promoted {promoted} imported entries",
            {"promoted": promoted, "selected_only": selected_only},
        )
        self._refresh_imports_view()
        self._refresh_candidates_view()
        self.status_var.set(f"Promoted {promoted} imported entries")

    def revalidate_imported_entries(self) -> None:
        self.resolve_import_entries(selected_only=False)

    def _event_sort_key(self, record: EventRecord, column_name: str) -> object:
        if column_name == "kind":
            return record.kind
        if column_name == "summary":
            return record.summary.lower()
        return record.created_at

    def _format_event_detail(self, record: EventRecord) -> str:
        lines = [
            f"Event ID:        {record.event_id}",
            f"Session ID:      {record.session_id or 'n/a'}",
            f"Created at:      {record.created_at}",
            f"Kind:            {record.kind}",
            f"Summary:         {record.summary}",
        ]
        if record.metadata:
            lines.extend(["", "Metadata:", json.dumps(record.metadata, indent=2, sort_keys=True)])
        return "\n".join(lines)

    def _refresh_evidence_view(self) -> None:
        if not hasattr(self, "evidence_tree"):
            return
        for item_id in self.evidence_tree.get_children():
            self.evidence_tree.delete(item_id)
        self.event_records = {}

        if not self.discovery_store:
            message = self.discovery_store_error or "Discovery store unavailable."
            self.evidence_summary_var.set(message)
            self._set_text_widget_content(self.evidence_detail_text, message)
            return

        records = self.discovery_store.list_events(limit=2000)
        records.sort(
            key=lambda record: self._event_sort_key(record, self.event_sort_column),
            reverse=self.event_sort_reverse,
        )
        for record in records:
            self.event_records[record.event_id] = record
            self.evidence_tree.insert(
                "",
                tk.END,
                iid=str(record.event_id),
                values=(record.created_at, record.kind, record.summary),
            )
        self.evidence_summary_var.set(
            f"Structured events: {len(records)} | Session: {self.discovery_store.session_id or 'n/a'}"
        )
        if records:
            self._set_text_widget_content(self.evidence_detail_text, "Select an event to inspect its structured metadata.")
        else:
            self._set_text_widget_content(self.evidence_detail_text, "No structured events recorded for this session yet.")

    def _on_event_selected(self, _event: object | None = None) -> None:
        selection = self.evidence_tree.selection()
        if not selection:
            return
        try:
            event_id = int(selection[0])
        except ValueError:
            return
        record = self.event_records.get(event_id)
        if record:
            self._set_text_widget_content(self.evidence_detail_text, self._format_event_detail(record))

    def _refresh_session_view(self) -> None:
        if not hasattr(self, "session_notes_text"):
            return
        if not self.discovery_store:
            message = self.discovery_store_error or "Discovery store unavailable."
            self.session_summary_var.set(message)
            self.session_export_var.set("")
            self._set_text_widget_content(self.session_notes_text, message)
            self._set_text_widget_content(self.session_export_text, message)
            return

        session = self.discovery_store.get_session()
        summary = self.discovery_store.get_summary()
        self.session_summary_var.set(
            "Session: {session_id} | Started: {started_at} | Candidates: {candidate_count} | Events: {event_count} | Imports: {import_count}".format(
                session_id=session.session_id if session else "n/a",
                started_at=session.started_at if session else "n/a",
                candidate_count=summary["candidate_count"],
                event_count=summary["event_count"],
                import_count=summary["import_count"],
            )
        )
        notes = self.discovery_store.get_session_notes()
        current_notes = self.session_notes_text.get("1.0", tk.END).rstrip()
        if current_notes != notes:
            self.discovery_store.set_session_notes(current_notes)
            notes = current_notes
        self._set_text_widget_content(self.session_notes_text, notes)
        preview = {
            "session_id": session.session_id if session else None,
            "started_at": session.started_at if session else None,
            "repo_root": session.repo_root if session else None,
            "scanner_version": session.scanner_version if session else None,
            "summary": summary,
        }
        self._set_text_widget_content(self.session_export_text, json.dumps(preview, indent=2, sort_keys=True))

    def save_session_notes(self) -> None:
        if not self.discovery_store:
            messagebox.showerror("Discovery store unavailable", "The discovery store is not available.")
            return
        notes = self._sync_session_notes_from_ui()
        self._record_store_event(
            "session-notes",
            "Updated session notes",
            {"note_length": len(notes)},
        )
        self.status_var.set("Session notes saved")
        self._refresh_session_view()

    def _sync_session_notes_from_ui(self) -> str:
        if not self.discovery_store or not hasattr(self, "session_notes_text"):
            return ""
        notes = self.session_notes_text.get("1.0", tk.END).rstrip()
        self.discovery_store.set_session_notes(notes)
        return notes

    def _default_export_dir(self, prefix: str) -> Path:
        assert self.discovery_store is not None
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        export_root = self.discovery_store.state_root / ("recovery-packages" if prefix.startswith("recovery") else "sessions")
        export_dir = export_root / f"{prefix}-{timestamp}"
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir

    @staticmethod
    def _write_json_file(path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def export_session_package(self) -> None:
        if not self.discovery_store:
            messagebox.showerror("Discovery store unavailable", "The discovery store is not available.")
            return
        self._sync_session_notes_from_ui()
        export_dir = self._default_export_dir("session")
        payload = self.discovery_store.build_session_snapshot()
        self._write_json_file(export_dir / "session-manifest.json", payload["session"])
        self._write_json_file(export_dir / "summary.json", payload["summary"])
        self._write_json_file(export_dir / "candidates.json", payload["candidates"])
        self._write_json_file(export_dir / "imports.json", payload["imports"])
        with (export_dir / "events.jsonl").open("w", encoding="utf-8") as handle:
            for event in payload["events"]:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
        (export_dir / "notes.md").write_text(payload["session"].get("notes", "") or "", encoding="utf-8")
        self.session_export_var.set(f"Last export: {export_dir}")
        self._set_text_widget_content(
            self.session_export_text,
            json.dumps(
                {
                    "export_dir": str(export_dir),
                    "session": payload["session"],
                    "summary": payload["summary"],
                },
                indent=2,
                sort_keys=True,
            ),
        )
        self._record_store_event(
            "session-export",
            f"Exported session package to {export_dir}",
            {"export_dir": str(export_dir)},
        )
        self.status_var.set(f"Exported session package to {export_dir}")

    def export_recovery_package(self) -> None:
        if not self.discovery_store:
            messagebox.showerror("Discovery store unavailable", "The discovery store is not available.")
            return
        self._sync_session_notes_from_ui()
        if self.recovery_snapshot is None:
            self._refresh_recovery_view()
        snapshot = self.recovery_snapshot
        if snapshot is None:
            messagebox.showerror("Recovery unavailable", "The recovery snapshot could not be loaded.")
            return

        export_dir = self._default_export_dir("recovery")
        session_payload = self.discovery_store.build_session_snapshot()
        recovery_payload = {
            "repo_root": str(snapshot.repo_root),
            "current_truth_path": str(snapshot.current_truth_path),
            "current_truth_last_updated": snapshot.current_truth_last_updated,
            "current_truth_last_updated_iso": snapshot.current_truth_last_updated_iso,
            "truth_statuses": [
                {"area": row.area, "status": row.status}
                for row in snapshot.truth_statuses
            ],
            "artifact_statuses": [
                {
                    "tier": artifact.tier,
                    "label": artifact.label,
                    "path_text": artifact.path_text,
                    "exists": artifact.exists,
                    "updated_at": artifact.updated_at,
                }
                for artifact in snapshot.artifact_statuses
            ],
            "surviving_baselines_text": snapshot.surviving_baselines_text,
            "broken_or_stale_text": snapshot.broken_or_stale_text,
            "canonical_scripts_text": snapshot.canonical_scripts_text,
            "warnings": snapshot.warnings,
        }
        self._write_json_file(export_dir / "recovery-summary.json", recovery_payload)
        self._write_json_file(export_dir / "session-snapshot.json", session_payload)
        (export_dir / "current-truth.md").write_text(
            snapshot.current_truth_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (export_dir / "rebuild-runbook.md").write_text(snapshot.runbook_text, encoding="utf-8")
        self.session_export_var.set(f"Last recovery export: {export_dir}")
        self._record_store_event(
            "recovery-export",
            f"Exported recovery package to {export_dir}",
            {"export_dir": str(export_dir)},
        )
        self.status_var.set(f"Exported recovery package to {export_dir}")
        self._refresh_session_view()

    def _append_recovery_output(self, title: str, output: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = self.recovery_runbook_text.get("1.0", tk.END).strip()
        block = f"[{timestamp}] {title}\n\n{output.strip()}\n"
        text = block if not existing else f"{block}\n{'-' * 80}\n{existing}"
        self._set_text_widget_content(self.recovery_runbook_text, text)

    def _run_recovery_background_action(
        self,
        *,
        title: str,
        event_kind: str,
        worker: Callable[[], str],
        success_status: str,
    ) -> None:
        if not self._begin_repo_background_job(title.lower()):
            return
        self.status_var.set(success_status)

        def on_success(result: object) -> None:
            typed_result = str(self._require_result_type(result, str, title))
            self._record_store_event(event_kind, title, {"status": "ok"})
            self._refresh_recovery_view()
            self._append_recovery_output(title, typed_result)
            self.status_var.set(success_status)

        def on_error(exc: Exception) -> None:
            self._append_recovery_output(title, f"Error: {exc}")
            self._record_store_event(event_kind + "-failed", title, {"error": str(exc)})
            self.status_var.set(f"{title} failed")
            messagebox.showerror(title, str(exc))

        def on_finally() -> None:
            self._end_repo_background_job()

        self._run_in_background(worker, on_success, on_error, on_finally)

    def build_rift_repo(self) -> None:
        self._run_recovery_background_action(
            title="Build repo",
            event_kind="recovery-build",
            worker=lambda: self.rift_bridge.build_solution(timeout_seconds=900),
            success_status="RiftReader build completed",
        )

    def rebuild_recovery_source_chain(self) -> None:
        self._run_recovery_background_action(
            title="Rebuild source/owner chain",
            event_kind="recovery-source-chain",
            worker=self.rift_bridge.rebuild_owner_source_chain,
            success_status="Owner/source chain rebuild completed",
        )

    def refresh_recovery_core_graph(self) -> None:
        self._run_recovery_background_action(
            title="Refresh core graph",
            event_kind="recovery-core-graph",
            worker=self.rift_bridge.refresh_core_graph,
            success_status="Core graph refresh completed",
        )

    def inspect_recovery_consistency(self) -> None:
        self._run_recovery_background_action(
            title="Inspect capture consistency",
            event_kind="recovery-consistency",
            worker=self.rift_bridge.inspect_capture_consistency,
            success_status="Capture consistency inspection completed",
        )

    def refresh_recovery_baseline(self) -> None:
        if not self._begin_repo_background_job("refreshing the recovery baseline"):
            return
        self.status_var.set("Refreshing recovery baseline")

        def worker() -> tuple[str, RiftPlayerSnapshot, str, str]:
            readerbridge_output = self.rift_bridge.readerbridge_snapshot()
            player_snapshot, player_output = self.rift_bridge.read_current_player()
            coord_anchor_output = self.rift_bridge.read_player_coord_anchor()
            combined_output = "\n\n".join(
                [
                    "[ReaderBridge Snapshot]",
                    readerbridge_output,
                    "[Player Current]",
                    player_output,
                    "[Coord Anchor]",
                    coord_anchor_output,
                ]
            ).strip()
            return combined_output, player_snapshot, player_output, coord_anchor_output

        def on_success(result: object) -> None:
            typed_result = self._require_tuple_result(result, 4, "Recovery baseline")
            combined_output, snapshot, player_output, coord_anchor_output = typed_result
            if not isinstance(snapshot, RiftPlayerSnapshot):
                raise TypeError(
                    f"Recovery baseline expected RiftPlayerSnapshot, got {type(snapshot).__name__}."
                )
            if not isinstance(combined_output, str) or not isinstance(player_output, str) or not isinstance(coord_anchor_output, str):
                raise TypeError("Recovery baseline expected string output segments.")
            self.last_rift_snapshot = snapshot
            self._seed_generic_fields_from_rift(snapshot)
            self.rift_player_summary_var.set(self._format_rift_snapshot(snapshot))
            self._set_text_widget_content(self.rift_output, player_output)
            self._record_store_event(
                "recovery-baseline",
                "Recovery baseline refresh completed",
                {
                    "process_name": snapshot.process_name,
                    "process_id": snapshot.process_id,
                    "address_hex": snapshot.address_hex,
                    "coord_anchor_output_present": bool(coord_anchor_output.strip()),
                },
            )
            if snapshot.address_hex:
                family_key = (
                    snapshot.raw.get("FamilyId")
                    or snapshot.raw.get("Signature")
                    or snapshot.selection_source
                    or snapshot.anchor_provenance
                    or snapshot.process_name
                )
                self._persist_candidate(
                    canonical_key=f"rift-player-current::{snapshot.process_name}::{family_key}",
                    kind="anchor",
                    label=f"Rift player current anchor ({snapshot.process_name})",
                    status="confirmed",
                    confidence=0.95,
                    absolute_address=int(snapshot.address_hex, 16),
                    source_kind="rift-player-current",
                    artifact_path=str(self.rift_bridge.repo_root / "scripts" / "captures" / "player-current-anchor.json"),
                    metadata={
                        "process_name": snapshot.process_name,
                        "process_id": snapshot.process_id,
                        "address_hex": snapshot.address_hex,
                        "level": snapshot.level,
                        "health": snapshot.health,
                        "coord_x": snapshot.coord_x,
                        "coord_y": snapshot.coord_y,
                        "coord_z": snapshot.coord_z,
                        "selection_source": snapshot.selection_source,
                        "anchor_provenance": snapshot.anchor_provenance,
                    },
                    evidence_kind="recovery-baseline",
                    evidence_summary=f"Recovery baseline confirmed anchor {snapshot.address_hex}",
                    evidence_metadata={"address_hex": snapshot.address_hex},
                    verified=True,
                )
            self._refresh_recovery_view()
            self._append_recovery_output("Refresh baseline", combined_output)
            self.status_var.set("Recovery baseline refreshed")

        def on_error(exc: Exception) -> None:
            self._append_recovery_output("Refresh baseline", f"Error: {exc}")
            self._record_store_event("recovery-baseline-failed", "Recovery baseline refresh failed", {"error": str(exc)})
            self.status_var.set("Recovery baseline refresh failed")
            messagebox.showerror("Recovery baseline refresh failed", str(exc))

        def on_finally() -> None:
            self._end_repo_background_job()

        self._run_in_background(worker, on_success, on_error, on_finally)

    def _format_recovery_notes(self, snapshot: RecoverySnapshot) -> str:
        parts: list[str] = []
        if snapshot.warnings:
            parts.append("Warnings:")
            parts.extend(f"- {warning}" for warning in snapshot.warnings)
            parts.append("")
        parts.append("Surviving baselines:")
        parts.append(snapshot.surviving_baselines_text or "(not available)")
        parts.append("")
        parts.append("Broken or stale right now:")
        parts.append(snapshot.broken_or_stale_text or "(not available)")
        parts.append("")
        parts.append("Canonical scripts on main:")
        parts.append(snapshot.canonical_scripts_text or "(not available)")
        return "\n".join(parts).strip()

    def _refresh_recovery_view(self) -> None:
        if not hasattr(self, "recovery_truth_tree"):
            return

        for item_id in self.recovery_truth_tree.get_children():
            self.recovery_truth_tree.delete(item_id)
        for item_id in self.recovery_artifact_tree.get_children():
            self.recovery_artifact_tree.delete(item_id)

        try:
            snapshot = load_recovery_snapshot(self.rift_bridge.repo_root)
        except Exception as exc:
            self.recovery_snapshot = None
            message = f"Recovery view failed to load: {exc}"
            self.recovery_summary_var.set(message)
            self._set_text_widget_content(self.recovery_notes_text, message)
            self._set_text_widget_content(self.recovery_runbook_text, message)
            self.logger.warning(message)
            return

        self.recovery_snapshot = snapshot
        for row in snapshot.truth_statuses:
            self.recovery_truth_tree.insert("", tk.END, values=(row.area, row.status))

        for artifact in snapshot.artifact_statuses:
            self.recovery_artifact_tree.insert(
                "",
                tk.END,
                values=(
                    artifact.tier,
                    "yes" if artifact.exists else "no",
                    artifact.updated_at or "n/a",
                    artifact.label,
                ),
            )

        tracked_count = len(snapshot.artifact_statuses)
        existing_count = sum(1 for artifact in snapshot.artifact_statuses if artifact.exists)
        stale_count = sum(1 for row in snapshot.truth_statuses if "stale" in row.status.lower() or "broken" in row.status.lower())
        warning_suffix = f" | Warnings: {len(snapshot.warnings)}" if snapshot.warnings else ""
        self.recovery_summary_var.set(
            "Current truth updated: {updated} | Status rows: {statuses} | Broken/stale rows: {stale} "
            "| Tracked artifacts: {tracked} | Existing artifacts: {existing}{warning_suffix}".format(
                updated=snapshot.current_truth_last_updated or "unknown",
                statuses=len(snapshot.truth_statuses),
                stale=stale_count,
                tracked=tracked_count,
                existing=existing_count,
                warning_suffix=warning_suffix,
            )
        )

        runbook_parts: list[str] = [str(snapshot.runbook_path), "", snapshot.runbook_text or "No rebuild runbook text was found."]
        self._set_text_widget_content(self.recovery_runbook_text, "\n".join(runbook_parts))
        self._set_text_widget_content(self.recovery_notes_text, self._format_recovery_notes(snapshot))

    def _sync_repo_status(self) -> None:
        self._sync_repo_from_entry()
        missing_core = self.rift_bridge.validate_core()
        missing_dashboard = self.rift_bridge.validate_dashboard(live=False)
        missing_live_dashboard = self.rift_bridge.validate_dashboard(live=True)

        core_ready = not missing_core
        dashboard_ready = not missing_dashboard
        live_dashboard_ready = not missing_live_dashboard
        self._refresh_repo_control_states()

        if core_ready and dashboard_ready and live_dashboard_ready:
            self.rift_repo_status_var.set("Repo looks valid (core + dashboard + live)")
            self._refresh_recovery_view()
            return

        if core_ready and dashboard_ready and not live_dashboard_ready:
            self.rift_repo_status_var.set("Repo partial: live dashboard prerequisites missing")
            self._refresh_recovery_view()
            return

        if core_ready and not dashboard_ready:
            self.rift_repo_status_var.set("Repo partial: dashboard prerequisites missing")
            self._refresh_recovery_view()
            return

        self.rift_repo_status_var.set("Repo invalid: missing required files")
        self._refresh_recovery_view()

    def _refresh_candidates_view(self) -> None:
        if not hasattr(self, "candidate_tree"):
            return

        for item_id in self.candidate_tree.get_children():
            self.candidate_tree.delete(item_id)

        self.candidate_records = {}
        if not self.discovery_store:
            reason = self.discovery_store_error or "Discovery store unavailable."
            self.candidate_summary_var.set(reason)
            self._set_text_widget_content(self.candidate_detail, reason)
            return

        try:
            records = self.discovery_store.list_candidates(limit=500)
            summary = self.discovery_store.get_summary()
        except Exception as exc:
            message = f"Failed to load candidates: {exc}"
            self.candidate_summary_var.set(message)
            self._set_text_widget_content(self.candidate_detail, message)
            self.logger.warning(message)
            return

        for record in records:
            self.candidate_records[record.candidate_id] = record
            tree_id = str(record.candidate_id)
            self.candidate_tree.insert(
                "",
                tk.END,
                iid=tree_id,
                values=(
                    record.kind,
                    record.status,
                    f"{record.confidence:.2f}",
                    record.address_hex or "n/a",
                    record.source_kind or "n/a",
                    record.last_verified_at or record.last_seen_at,
                    record.label,
                ),
            )

        started_at = self.discovery_store.session_started_at or "n/a"
        self.candidate_summary_var.set(
            "Candidates: {candidate_count} | Events: {event_count} | Sessions: {session_count} | "
            "Current session: {started_at} | DB: {db_path}".format(
                candidate_count=summary["candidate_count"],
                event_count=summary["event_count"],
                session_count=summary["session_count"],
                started_at=started_at,
                db_path=self.discovery_store.db_path,
            )
        )
        if records:
            self._set_text_widget_content(
                self.candidate_detail,
                "Select a candidate to inspect its canonical key, metadata, and evidence summary.",
            )
        else:
            self._set_text_widget_content(
                self.candidate_detail,
                "No persisted candidates yet. Run an AOB scan, pointer resolution, or Rift current-player read first.",
            )

    def _format_candidate_detail(self, record: CandidateRecord) -> str:
        lines = [
            f"ID:             {record.candidate_id}",
            f"Label:          {record.label}",
            f"Kind:           {record.kind}",
            f"Status:         {record.status}",
            f"Confidence:     {record.confidence:.2f}",
            f"Address:        {record.address_hex or 'n/a'}",
            f"Value type:     {record.value_type or 'n/a'}",
            f"Module:         {record.module_name or 'n/a'}",
            f"Module RVA:     {f'0x{record.module_rva:X}' if record.module_rva is not None else 'n/a'}",
            f"Source:         {record.source_kind or 'n/a'}",
            f"Evidence rows:  {record.evidence_count}",
            f"First seen:     {record.first_seen_at}",
            f"Last seen:      {record.last_seen_at}",
            f"Last verified:  {record.last_verified_at or 'n/a'}",
            f"Last game build:{record.last_game_build or 'n/a'}",
            f"Artifact path:  {record.artifact_path or 'n/a'}",
            f"Canonical key:  {record.canonical_key}",
        ]
        if record.notes:
            lines.extend(["", "Notes:", record.notes])
        if record.metadata_json:
            metadata_text = record.metadata_json
            try:
                metadata_text = json.dumps(json.loads(record.metadata_json), indent=2, sort_keys=True)
            except Exception:
                pass
            lines.extend(["", "Metadata:", metadata_text])
        return "\n".join(lines)

    def _on_candidate_selected(self, _event: object | None = None) -> None:
        if not hasattr(self, "candidate_tree"):
            return

        selection = self.candidate_tree.selection()
        if not selection:
            return

        try:
            candidate_id = int(selection[0])
        except ValueError:
            return

        record = self.candidate_records.get(candidate_id)
        if not record:
            return

        self._set_text_widget_content(self.candidate_detail, self._format_candidate_detail(record))

    def _refresh_recovery_view(self) -> None:
        if not hasattr(self, "recovery_truth_tree"):
            return

        for item_id in self.recovery_truth_tree.get_children():
            self.recovery_truth_tree.delete(item_id)
        for item_id in self.recovery_artifact_tree.get_children():
            self.recovery_artifact_tree.delete(item_id)

        try:
            snapshot = load_recovery_snapshot(self.rift_bridge.repo_root)
        except Exception as exc:
            self.recovery_snapshot = None
            message = f"Recovery view failed to load: {exc}"
            self.recovery_summary_var.set(message)
            self._set_text_widget_content(self.recovery_runbook_text, message)
            self.logger.warning(message)
            return

        self.recovery_snapshot = snapshot
        for row in snapshot.truth_statuses:
            self.recovery_truth_tree.insert("", tk.END, values=(row.area, row.status))

        for artifact in snapshot.artifact_statuses:
            self.recovery_artifact_tree.insert(
                "",
                tk.END,
                values=(
                    artifact.tier,
                    "yes" if artifact.exists else "no",
                    artifact.updated_at or "n/a",
                    artifact.label,
                ),
            )

        tracked_count = len(snapshot.artifact_statuses)
        existing_count = sum(1 for artifact in snapshot.artifact_statuses if artifact.exists)
        warning_suffix = ""
        if snapshot.warnings:
            warning_suffix = f" | Warnings: {len(snapshot.warnings)}"
        self.recovery_summary_var.set(
            "Current truth updated: {updated} | Status rows: {statuses} | Tracked artifacts: {tracked} "
            "| Existing artifacts: {existing}{warning_suffix}".format(
                updated=snapshot.current_truth_last_updated or "unknown",
                statuses=len(snapshot.truth_statuses),
                tracked=tracked_count,
                existing=existing_count,
                warning_suffix=warning_suffix,
            )
        )

        runbook_parts: list[str] = []
        if snapshot.warnings:
            runbook_parts.append("Warnings:")
            runbook_parts.extend(f"- {warning}" for warning in snapshot.warnings)
            runbook_parts.append("")
        runbook_parts.append(str(snapshot.runbook_path))
        runbook_parts.append("")
        runbook_parts.append(snapshot.runbook_text or "No rebuild runbook text was found.")
        self._set_text_widget_content(self.recovery_runbook_text, "\n".join(runbook_parts))

    def _sync_repo_status(self) -> None:
        self._sync_repo_from_entry()
        missing_core = self.rift_bridge.validate_core()
        missing_dashboard = self.rift_bridge.validate_dashboard(live=False)
        missing_live_dashboard = self.rift_bridge.validate_dashboard(live=True)

        core_ready = not missing_core
        dashboard_ready = not missing_dashboard
        live_dashboard_ready = not missing_live_dashboard

        self._set_widget_enabled(self.rift_read_button, core_ready)
        self._set_widget_enabled(self.rift_debug_button, core_ready)
        self._set_widget_enabled(self.rift_dashboard_button, dashboard_ready)
        self._set_widget_enabled(self.rift_live_dashboard_button, live_dashboard_ready)

        if core_ready and dashboard_ready and live_dashboard_ready:
            self.rift_repo_status_var.set("Repo looks valid (core + dashboard + live)")
            self._refresh_recovery_view()
            return

        if core_ready and dashboard_ready and not live_dashboard_ready:
            self.rift_repo_status_var.set("Repo partial: live dashboard prerequisites missing")
            self._refresh_recovery_view()
            return

        if core_ready and not dashboard_ready:
            self.rift_repo_status_var.set("Repo partial: dashboard prerequisites missing")
            self._refresh_recovery_view()
            return

        self.rift_repo_status_var.set("Repo invalid: missing required files")
        self._refresh_recovery_view()

    def _sync_repo_from_entry(self) -> None:
        repo_text = self.repo_entry.get().strip()
        if repo_text:
            self.rift_bridge.set_repo_root(Path(repo_text))

    def _drain_log_queue(self) -> None:
        if self._is_closing:
            return

        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass

        drop_notice = self.ui_log_handler.consume_drop_notice()
        if drop_notice:
            self.log_text.insert(tk.END, drop_notice + "\n")
            self.log_text.see(tk.END)

        if self._is_closing:
            return

        try:
            self.root.after(75, self._drain_log_queue)
        except tk.TclError:
            pass

    def _schedule_ui(self, callback: Callable[[], None]) -> None:
        if self._is_closing:
            return

        def safe_callback() -> None:
            try:
                callback()
            except tk.TclError:
                pass
            except Exception as exc:
                self.logger.exception("Scheduled UI callback failed: %s", exc)
                if not self._is_closing:
                    try:
                        self.status_var.set(f"UI callback failed: {exc}")
                    except tk.TclError:
                        pass

        try:
            self.root.after(0, safe_callback)
        except tk.TclError:
            pass

    def _require_result_type(self, value: object, expected_type: type, context: str) -> object:
        if not isinstance(value, expected_type):
            raise TypeError(
                f"{context} expected {expected_type.__name__}, got {type(value).__name__}."
            )
        return value

    def _require_tuple_result(self, value: object, length: int, context: str) -> tuple[object, ...]:
        if not isinstance(value, tuple):
            raise TypeError(f"{context} expected tuple result, got {type(value).__name__}.")
        if len(value) != length:
            raise TypeError(f"{context} expected tuple length {length}, got {len(value)}.")
        return value

    def _run_in_background(
        self,
        worker: Callable[[], object],
        on_success: Callable[[object], None],
        on_error: Callable[[Exception], None],
        on_finally: Callable[[], None] | None = None,
    ) -> None:
        def runner() -> None:
            try:
                result = worker()
            except Exception as exc:
                self._schedule_ui(lambda exc=exc: on_error(exc))
            else:
                self._schedule_ui(lambda result=result: on_success(result))
            finally:
                if on_finally is not None:
                    self._schedule_ui(on_finally)

        threading.Thread(target=runner, daemon=True).start()

    def _parse_address(self, text: str, field_name: str) -> int:
        try:
            value = int(text.strip(), 0)
        except ValueError as exc:
            raise ScannerError(f"{field_name} must be a valid hex or decimal integer.") from exc

        if value < 0:
            raise ScannerError(f"{field_name} must be non-negative.")
        return value

    def _parse_offsets(self, text: str) -> list[int]:
        raw_parts = [part.strip() for part in text.split(",") if part.strip()]
        if not raw_parts:
            raise ScannerError("At least one offset is required.")

        offsets: list[int] = []
        for part in raw_parts:
            try:
                offsets.append(int(part, 0))
            except ValueError as exc:
                raise ScannerError(
                    f"Offset '{part}' is invalid. Use hex (0x10) or decimal."
                ) from exc
        return offsets

    def _format_rift_snapshot(self, snapshot: RiftPlayerSnapshot) -> str:
        return (
            f"Process={snapshot.process_name} PID={snapshot.process_id} "
            f"Address={snapshot.address_hex or 'n/a'} "
            f"Level={snapshot.level if snapshot.level is not None else 'n/a'} "
            f"Health={snapshot.health if snapshot.health is not None else 'n/a'} "
            f"Coords=({snapshot.coord_x}, {snapshot.coord_y}, {snapshot.coord_z}) "
            f"Selection={snapshot.selection_source or 'n/a'} "
            f"Anchor={snapshot.anchor_provenance or 'n/a'}"
        )

    def _seed_generic_fields_from_rift(self, snapshot: RiftPlayerSnapshot) -> None:
        process_name = snapshot.process_name or "rift_x64"
        if not process_name.lower().endswith(".exe"):
            process_name = f"{process_name}.exe"

        self.proc_entry.delete(0, tk.END)
        self.proc_entry.insert(0, process_name)

        if snapshot.address_hex:
            self.base_entry.delete(0, tk.END)
            self.base_entry.insert(0, snapshot.address_hex)
            self.monitor_entry.delete(0, tk.END)
            self.monitor_entry.insert(0, snapshot.address_hex)
            self.hex_address_entry.delete(0, tk.END)
            self.hex_address_entry.insert(0, snapshot.address_hex)

    def use_last_rift_snapshot_process_name(self) -> None:
        if not self.last_rift_snapshot:
            messagebox.showinfo("No Rift snapshot", "Read the current Rift player first.")
            return

        process_name = self.last_rift_snapshot.process_name or "rift_x64"
        if not process_name.lower().endswith(".exe"):
            process_name = f"{process_name}.exe"

        self.proc_entry.delete(0, tk.END)
        self.proc_entry.insert(0, process_name)
        self.status_var.set(f"Loaded last Rift snapshot process: {process_name}")

    def use_last_rift_snapshot_address(self, entry: ttk.Entry, label: str) -> None:
        if not self.last_rift_snapshot or not self.last_rift_snapshot.address_hex:
            messagebox.showinfo("No Rift snapshot", "Read the current Rift player first.")
            return

        entry.delete(0, tk.END)
        entry.insert(0, self.last_rift_snapshot.address_hex)
        self.status_var.set(f"Loaded last Rift snapshot address into {label}")

    def use_coord_anchor_preset(self) -> None:
        if self.recovery_snapshot is None:
            self._refresh_recovery_view()
        snapshot = self.recovery_snapshot
        if snapshot is None:
            messagebox.showerror("Recovery unavailable", "The recovery snapshot is not available.")
            return

        pattern_match = re.search(r"pattern:\s*`([^`]+)`", snapshot.surviving_baselines_text)
        if not pattern_match:
            messagebox.showerror("Coord anchor unavailable", "The current-truth recovery note does not expose a coord-anchor pattern.")
            return

        process_name = (
            self.generic_scanner.process_name
            or (self.last_rift_snapshot.process_name if self.last_rift_snapshot else None)
            or "rift_x64.exe"
        )
        if not process_name.lower().endswith(".exe"):
            process_name = f"{process_name}.exe"

        self._set_entry_text(self.aob_entry, pattern_match.group(1).strip())
        self._set_entry_text(self.aob_module_entry, process_name)
        setattr(self, "_next_aob_scan_scope", "anchor-neighborhood")
        self.status_var.set("Loaded coord-anchor preset into the AOB scanner")
        self._record_store_event(
            "coord-anchor-preset",
            "Loaded coord-anchor preset",
            {"process_name": process_name, "pattern_text": pattern_match.group(1).strip()},
        )

    def attach_process(self) -> None:
        if not self._ensure_generic_background_idle("changing the attached process"):
            return

        if self.monitor_thread and self.monitor_thread.is_alive():
            if not self.stop_monitor(log=False):
                self.status_var.set("Wait for the monitor to stop before attaching")
                messagebox.showwarning(
                    "Monitor still stopping",
                    "Wait for the current monitor read to finish before attaching to another process.",
                )
                return

        try:
            info = self.generic_scanner.attach(self.proc_entry.get().strip())
        except Exception as exc:
            self.proc_status_var.set("Attach failed")
            self.pointer_size_var.set("Unknown")
            self.status_var.set("Attach failed")
            self._record_store_event(
                "attach-failed",
                f"Failed to attach to {self.proc_entry.get().strip() or '(blank process name)'}",
                {"process_name": self.proc_entry.get().strip(), "error": str(exc)},
            )
            messagebox.showerror("Attach failed", str(exc))
            self._refresh_generic_control_states()
            return

        self.proc_status_var.set(
            f"Attached to {info.process_name} (PID {info.process_id}, {info.pointer_size * 8}-bit)"
        )
        self.pointer_size_var.set(f"{info.pointer_size * 8}-bit")
        self.status_var.set(f"Attached to {info.process_name}")
        self._record_store_event(
            "attach",
            f"Attached to {info.process_name}",
            {
                "process_name": info.process_name,
                "process_id": info.process_id,
                "pointer_size": info.pointer_size,
            },
        )
        self._save_ui_state()
        self._refresh_generic_control_states()

    def attach_rift_process(self) -> None:
        self.proc_entry.delete(0, tk.END)
        self.proc_entry.insert(0, "rift_x64.exe")
        self.attach_process()

    def attach_last_rift_snapshot_process(self) -> None:
        if not self.last_rift_snapshot:
            messagebox.showinfo("No Rift snapshot", "Read the current Rift player first.")
            return

        self.use_last_rift_snapshot_process_name()
        self.attach_process()

    def detach_process(self) -> None:
        if not self._ensure_generic_background_idle("detaching from the current process"):
            return

        self.stop_monitor(log=False)
        self.generic_scanner.detach()
        self.proc_status_var.set("Not attached")
        self.pointer_size_var.set("Unknown")
        self.status_var.set("Detached")
        self._record_store_event("detach", "Detached from generic process")
        self._refresh_generic_control_states()

    def do_aob_scan(self) -> None:
        if self.scan_in_progress:
            messagebox.showinfo("Scan in progress", "Wait for the current scan to finish.")
            return
        if not self._begin_generic_background_job():
            return

        pattern_text = self.aob_entry.get().strip()
        module_name = self.aob_module_entry.get().strip() or None
        scan_scope = getattr(self, "_next_aob_scan_scope", None)
        setattr(self, "_next_aob_scan_scope", None)

        self.scan_in_progress = True
        self._refresh_generic_control_states()
        self.aob_status_var.set("Scanning...")
        self.aob_results.delete("1.0", tk.END)

        def worker() -> AobScanResult:
            return self.generic_scanner.aob_scan(pattern_text, module_name)

        def on_success(result: object) -> None:
            typed_result = self._require_result_type(result, AobScanResult, "AOB scan")
            self.aob_results.insert(
                tk.END,
                f"Pattern: {typed_result.pattern_text}\n"
                f"Scope:   {typed_result.module_name or 'full process'}\n"
                f"Time:    {typed_result.duration_seconds:.2f}s\n"
                f"Hits:    {len(typed_result.addresses)}\n\n",
            )
            preview = typed_result.addresses[:200]
            for address in preview:
                self.aob_results.insert(tk.END, f"0x{address:X}\n")
            if len(typed_result.addresses) > len(preview):
                self.aob_results.insert(tk.END, f"\n... and {len(typed_result.addresses) - len(preview)} more\n")
            self.aob_status_var.set(f"Completed: {len(typed_result.addresses)} hit(s)")
            self.status_var.set("AOB scan completed")
            self._record_store_event(
                "aob-scan",
                f"AOB scan completed for {typed_result.module_name or 'full process'}",
                {
                    "pattern_text": typed_result.pattern_text,
                    "module_name": typed_result.module_name,
                    "hit_count": len(typed_result.addresses),
                    "duration_seconds": round(typed_result.duration_seconds, 6),
                    "persisted_hit_count": min(len(typed_result.addresses), AOB_CANDIDATE_PERSIST_LIMIT),
                    "scan_scope": scan_scope,
                },
            )

            persisted_hits = typed_result.addresses[:AOB_CANDIDATE_PERSIST_LIMIT]
            for index, address in enumerate(persisted_hits, start=1):
                module_rva = None
                if typed_result.module_name:
                    try:
                        module_base = self.generic_scanner.get_module_base(typed_result.module_name)
                        module_rva = address - module_base
                    except Exception:
                        module_rva = None
                self._persist_candidate(
                    refresh_view=False,
                    canonical_key=(
                        f"aob::{self.generic_scanner.process_name or 'unknown'}::"
                        f"{typed_result.module_name or '*'}::{typed_result.pattern_text}::{address:X}"
                    ),
                    kind="aob",
                    label=f"AOB hit {index}: {typed_result.pattern_text}",
                    status="confirmed" if len(typed_result.addresses) == 1 else "candidate",
                    confidence=0.8 if len(typed_result.addresses) == 1 else 0.6,
                    module_name=typed_result.module_name,
                    module_rva=module_rva,
                    absolute_address=address,
                    source_kind="aob-scan",
                    metadata={
                        "pattern_text": typed_result.pattern_text,
                        "module_name": typed_result.module_name,
                        "module_rva": module_rva,
                        "hit_index": index,
                        "total_hits": len(typed_result.addresses),
                        "duration_seconds": typed_result.duration_seconds,
                        "scan_scope": scan_scope,
                    },
                    evidence_kind="aob-scan",
                    evidence_summary=f"AOB scan located 0x{address:X}",
                    evidence_metadata={
                        "pattern_text": typed_result.pattern_text,
                        "module_name": typed_result.module_name,
                        "address": f"0x{address:X}",
                        "scan_scope": scan_scope,
                    },
                )
            self._refresh_candidates_view()
            self._save_ui_state()

        def on_error(exc: Exception) -> None:
            self.aob_status_var.set("Scan failed")
            self.status_var.set("AOB scan failed")
            self.aob_results.insert(tk.END, f"Error: {exc}\n")
            self._record_store_event(
                "aob-scan-failed",
                "AOB scan failed",
                {"pattern_text": pattern_text, "module_name": module_name, "error": str(exc)},
            )
            messagebox.showerror("AOB scan failed", str(exc))

        def on_finally() -> None:
            self.scan_in_progress = False
            self._end_generic_background_job()

        self._run_in_background(worker, on_success, on_error, on_finally)

    def resolve_pointer(self) -> None:
        try:
            base = self._parse_address(self.base_entry.get(), "Base address")
            offsets = self._parse_offsets(self.offset_entry.get())
            final_address = self.generic_scanner.resolve_pointer_chain(
                base,
                offsets,
                dereference_final=self.deref_final_var.get(),
            )
        except Exception as exc:
            self.pointer_result_var.set("Resolution failed")
            messagebox.showerror("Pointer resolution failed", str(exc))
            return

        self.pointer_result_var.set(f"Final address: 0x{final_address:X}")
        self.status_var.set("Pointer chain resolved")
        offsets_hex = [hex(value) for value in offsets]
        self._record_store_event(
            "pointer-resolved",
            f"Pointer chain resolved to 0x{final_address:X}",
            {
                "base_address": f"0x{base:X}",
                "offsets": offsets_hex,
                "dereference_final": self.deref_final_var.get(),
                "final_address": f"0x{final_address:X}",
            },
        )
        self._persist_candidate(
            canonical_key=(
                f"pointer::{self.generic_scanner.process_name or 'unknown'}::{base:X}::"
                f"{','.join(offsets_hex)}::{int(self.deref_final_var.get())}"
            ),
            kind="pointer",
            label=f"Pointer chain from 0x{base:X}",
            status="confirmed",
            confidence=0.85,
            value_type="pointer",
            absolute_address=final_address,
            source_kind="pointer-chain",
            metadata={
                "base_address": f"0x{base:X}",
                "offsets": offsets_hex,
                "dereference_final": self.deref_final_var.get(),
                "process_name": self.generic_scanner.process_name,
            },
            evidence_kind="pointer-resolved",
            evidence_summary=f"Pointer chain resolved to 0x{final_address:X}",
            evidence_metadata={
                "final_address": f"0x{final_address:X}",
                "offsets": offsets_hex,
            },
            verified=True,
        )
        self._save_ui_state()

    def start_monitor(self) -> None:
        if self.monitor_thread and self.monitor_thread.is_alive():
            messagebox.showinfo("Monitor active", "Stop the current monitor before starting a new one.")
            return
        if not self._ensure_generic_background_idle("starting the monitor"):
            return

        try:
            address = self._parse_address(self.monitor_entry.get(), "Monitor address")
            interval_seconds = float(self.monitor_interval_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid interval", "Interval must be a number in seconds.")
            return
        except Exception as exc:
            messagebox.showerror("Invalid monitor configuration", str(exc))
            return

        if interval_seconds < MIN_MONITOR_INTERVAL_SECONDS:
            messagebox.showerror(
                "Invalid interval",
                f"Interval must be at least {MIN_MONITOR_INTERVAL_SECONDS:.3f} seconds.",
            )
            return

        config = MonitorConfig(
            address=address,
            value_type=self.type_var.get(),
            interval_seconds=interval_seconds,
        )

        self.monitor_status_var.set("Verifying first monitor sample...")
        self.status_var.set("Validating monitor target")
        try:
            initial_value = self.generic_scanner.read_value(config.address, config.value_type)
        except Exception as exc:
            self.monitor_status_var.set("Monitor idle")
            self.status_var.set("Monitor start failed")
            messagebox.showerror("Monitor start failed", str(exc))
            self._refresh_generic_control_states()
            return

        self.monitor_stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(config,), daemon=True)
        self.monitor_thread.start()

        self.monitor_status_var.set(
            f"Monitoring 0x{config.address:X} as {config.value_type} every {config.interval_seconds:.3f}s"
        )
        self.status_var.set("Monitor running")
        self._refresh_generic_control_states()
        self.logger.info(
            "Started generic monitor for 0x%X (%s, interval=%ss, initial=%s)",
            config.address,
            config.value_type,
            config.interval_seconds,
            initial_value,
        )

    def stop_monitor(self, *, log: bool = True) -> bool:
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_stop_event.set()
            self.monitor_thread.join(timeout=1.5)
            if self.monitor_thread.is_alive():
                self.monitor_status_var.set("Monitor stop requested; waiting for current read to finish")
                self._refresh_generic_control_states()
                if log:
                    self.logger.warning(
                        "Generic monitor did not stop within the timeout; leaving stop flag set until the worker exits"
                    )
                return False

        self.monitor_thread = None
        self.monitor_stop_event.clear()
        self.monitor_status_var.set("Monitor idle")
        self._refresh_generic_control_states()
        if log:
            self.logger.info("Generic monitor stopped")
        return True

    def _on_monitor_worker_finished(self) -> None:
        if self.monitor_thread and self.monitor_thread.is_alive():
            return

        self.monitor_thread = None
        if self.monitor_stop_event.is_set():
            self.monitor_stop_event.clear()
        self.monitor_status_var.set("Monitor idle")
        self._refresh_generic_control_states()

    @staticmethod
    def _format_hex_dump(address: int, data: bytes) -> str:
        lines: list[str] = []
        for offset in range(0, len(data), 16):
            chunk = data[offset : offset + 16]
            hex_bytes = " ".join(f"{byte:02X}" for byte in chunk)
            ascii_text = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
            lines.append(f"0x{address + offset:016X}: {hex_bytes:<47} | {ascii_text}")
        return "\n".join(lines)

    def read_hex_dump(self) -> None:
        if self.hex_read_in_progress:
            messagebox.showinfo("Hex dump in progress", "Wait for the current read to finish.")
            return
        if not self._begin_generic_background_job():
            return

        try:
            address = self._parse_address(self.hex_address_entry.get(), "Hex dump address")
            length = int(self.hex_length_entry.get().strip(), 0)
        except ValueError:
            self._end_generic_background_job()
            messagebox.showerror("Invalid length", "Length must be a valid hex or decimal integer.")
            return
        except Exception as exc:
            self._end_generic_background_job()
            messagebox.showerror("Invalid hex dump request", str(exc))
            return

        if length <= 0:
            self._end_generic_background_job()
            messagebox.showerror("Invalid length", "Length must be greater than zero.")
            return
        if length > 4096:
            self._end_generic_background_job()
            messagebox.showerror("Invalid length", "Length must be 4096 bytes or less.")
            return

        self.hex_read_in_progress = True
        self._refresh_generic_control_states()
        self.hex_output.delete("1.0", tk.END)
        self.hex_output.insert(tk.END, "Reading bytes...\n")
        self.hex_status_var.set("Reading...")
        self.status_var.set("Reading generic hex dump")

        def worker() -> tuple[int, bytes]:
            return address, self.generic_scanner.read_bytes(address, length)

        def on_success(result: object) -> None:
            typed_result = self._require_tuple_result(result, 2, "Hex dump")
            dump_address, data = typed_result
            if not isinstance(dump_address, int) or not isinstance(data, bytes):
                raise TypeError("Hex dump expected (int, bytes) result.")
            self.hex_output.delete("1.0", tk.END)
            self.hex_output.insert(tk.END, self._format_hex_dump(dump_address, data) + "\n")
            self.hex_status_var.set(f"Read {len(data)} byte(s)")
            self.status_var.set("Generic hex dump complete")

        def on_error(exc: Exception) -> None:
            self.hex_output.delete("1.0", tk.END)
            self.hex_output.insert(tk.END, f"Error: {exc}\n")
            self.hex_status_var.set("Read failed")
            self.status_var.set("Generic hex dump failed")
            messagebox.showerror("Hex dump failed", str(exc))

        def on_finally() -> None:
            self.hex_read_in_progress = False
            self._end_generic_background_job()

        self._run_in_background(worker, on_success, on_error, on_finally)

    def _monitor_loop(self, config: MonitorConfig) -> None:
        error_logged = False
        try:
            while not self.monitor_stop_event.is_set():
                try:
                    value = self.generic_scanner.read_value(config.address, config.value_type)
                except Exception as exc:
                    if not error_logged:
                        self.logger.error("Monitor read failed: %s", exc)
                        error_logged = True
                    if self.monitor_stop_event.wait(config.interval_seconds):
                        break
                    continue

                error_logged = False
                self.logger.info("0x%X = %s (%s)", config.address, value, config.value_type)
                if self.monitor_stop_event.wait(config.interval_seconds):
                    break
        finally:
            self._schedule_ui(self._on_monitor_worker_finished)

    def validate_repo_path(self) -> None:
        self._sync_repo_status()
        missing = self.rift_bridge.validate()
        if missing:
            messagebox.showerror("Invalid RiftReader repo", "Missing required files:\n\n" + "\n".join(missing))
            return

        self.status_var.set("RiftReader repo validated")
        self._save_ui_state()

    def read_rift_current_player(self) -> None:
        self._sync_repo_status()
        if not self.rift_bridge.is_available():
            messagebox.showerror("RiftReader unavailable", "The configured repo path is not valid.")
            return
        if not self._begin_repo_background_job("reading the current Rift player"):
            return

        self.rift_output.delete("1.0", tk.END)
        self.rift_output.insert(tk.END, "Reading current player...\n")
        self.status_var.set("Reading Rift current player")

        def worker() -> tuple[RiftPlayerSnapshot, str]:
            return self.rift_bridge.read_current_player()

        def on_success(result: object) -> None:
            typed_result = self._require_tuple_result(result, 2, "Rift current player")
            snapshot, raw_output = typed_result
            if not isinstance(snapshot, RiftPlayerSnapshot) or not isinstance(raw_output, str):
                raise TypeError("Rift current player expected (RiftPlayerSnapshot, str) result.")
            self.last_rift_snapshot = snapshot
            self._seed_generic_fields_from_rift(snapshot)
            self.rift_player_summary_var.set(self._format_rift_snapshot(snapshot))
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, raw_output + "\n")
            self.status_var.set("Rift current player loaded")
            family_key = (
                snapshot.raw.get("FamilyId")
                or snapshot.raw.get("Signature")
                or snapshot.selection_source
                or snapshot.anchor_provenance
                or snapshot.process_name
            )
            self._record_store_event(
                "rift-player-current",
                f"Loaded Rift player snapshot for {snapshot.process_name}",
                {
                    "process_name": snapshot.process_name,
                    "process_id": snapshot.process_id,
                    "address_hex": snapshot.address_hex,
                    "selection_source": snapshot.selection_source,
                    "anchor_provenance": snapshot.anchor_provenance,
                },
            )
            if snapshot.address_hex:
                self._persist_candidate(
                    canonical_key=f"rift-player-current::{snapshot.process_name}::{family_key}",
                    kind="anchor",
                    label=f"Rift player current anchor ({snapshot.process_name})",
                    status="confirmed",
                    confidence=0.95,
                    absolute_address=int(snapshot.address_hex, 16),
                    source_kind="rift-player-current",
                    artifact_path=str(self.rift_bridge.repo_root / "scripts" / "captures" / "player-current-anchor.json"),
                    metadata={
                        "process_name": snapshot.process_name,
                        "process_id": snapshot.process_id,
                        "address_hex": snapshot.address_hex,
                        "level": snapshot.level,
                        "health": snapshot.health,
                        "coord_x": snapshot.coord_x,
                        "coord_y": snapshot.coord_y,
                        "coord_z": snapshot.coord_z,
                        "selection_source": snapshot.selection_source,
                        "anchor_provenance": snapshot.anchor_provenance,
                    },
                    evidence_kind="rift-player-current",
                    evidence_summary=f"Rift player current anchor resolved to {snapshot.address_hex}",
                    evidence_metadata={
                        "address_hex": snapshot.address_hex,
                        "process_id": snapshot.process_id,
                    },
                    verified=True,
                )
                self._refresh_candidates_view()

        def on_error(exc: Exception) -> None:
            self.rift_player_summary_var.set("No Rift snapshot loaded")
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, f"Error: {exc}\n")
            self.status_var.set("Rift current player read failed")
            self._record_store_event(
                "rift-player-current-failed",
                "Rift current player read failed",
                {"error": str(exc)},
            )
            messagebox.showerror("Rift current player read failed", str(exc))

        def on_finally() -> None:
            self._end_repo_background_job()

        self._run_in_background(worker, on_success, on_error, on_finally)

    def inspect_rift_debug_state(self) -> None:
        self._sync_repo_status()
        if not self.rift_bridge.is_available():
            messagebox.showerror("RiftReader unavailable", "The configured repo path is not valid.")
            return
        if not self._begin_repo_background_job("inspecting Rift debug state"):
            return

        self.rift_output.delete("1.0", tk.END)
        self.rift_output.insert(tk.END, "Inspecting Rift debug state...\n")
        self.status_var.set("Inspecting Rift debug state")

        def worker() -> str:
            return self.rift_bridge.inspect_debug_state()

        def on_success(result: object) -> None:
            typed_result = str(self._require_result_type(result, str, "Rift debug-state probe"))
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, typed_result + "\n")
            self.status_var.set("Rift debug-state probe completed")

        def on_error(exc: Exception) -> None:
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, f"Error: {exc}\n")
            self.status_var.set("Rift debug-state probe failed")
            messagebox.showerror("Rift debug-state probe failed", str(exc))

        def on_finally() -> None:
            self._end_repo_background_job()

        self._run_in_background(worker, on_success, on_error, on_finally)

    def open_rift_dashboard(self) -> None:
        self._sync_repo_status()
        missing_dashboard = self.rift_bridge.validate_dashboard(live=False)
        if missing_dashboard:
            messagebox.showerror(
                "RiftReader dashboard unavailable",
                "Missing required dashboard files:\n\n" + "\n".join(missing_dashboard),
            )
            return
        if not self._begin_repo_background_job("opening the Rift dashboard"):
            return

        self.rift_output.delete("1.0", tk.END)
        self.rift_output.insert(tk.END, "Preparing dashboard...\n")
        self.status_var.set("Preparing Rift dashboard")

        def worker() -> str:
            return self.rift_bridge.open_dashboard(live=False)

        def on_success(result: object) -> None:
            typed_result = str(self._require_result_type(result, str, "Open dashboard"))
            self.rift_output.delete("1.0", tk.END)
            if typed_result:
                self.rift_output.insert(tk.END, typed_result + "\n\n")
            self.rift_output.insert(tk.END, "Dashboard preflight succeeded. Launch requested.\n")
            self.status_var.set("Opening Rift dashboard")

        def on_error(exc: Exception) -> None:
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, f"Error: {exc}\n")
            self.status_var.set("Rift dashboard launch failed")
            messagebox.showerror("Open dashboard failed", str(exc))

        def on_finally() -> None:
            self._end_repo_background_job()

        self._run_in_background(worker, on_success, on_error, on_finally)

    def open_rift_live_dashboard(self) -> None:
        self._sync_repo_status()
        missing_live_dashboard = self.rift_bridge.validate_dashboard(live=True)
        if missing_live_dashboard:
            messagebox.showerror(
                "RiftReader live dashboard unavailable",
                "Missing required live dashboard files:\n\n" + "\n".join(missing_live_dashboard),
            )
            return
        if not self._begin_repo_background_job("opening the Rift live dashboard"):
            return

        self.rift_output.delete("1.0", tk.END)
        self.rift_output.insert(tk.END, "Preparing live dashboard...\n")
        self.status_var.set("Preparing Rift live dashboard")

        def worker() -> str:
            return self.rift_bridge.open_dashboard(live=True)

        def on_success(result: object) -> None:
            typed_result = str(self._require_result_type(result, str, "Open live dashboard"))
            self.rift_output.delete("1.0", tk.END)
            if typed_result:
                self.rift_output.insert(tk.END, typed_result + "\n\n")
            self.rift_output.insert(tk.END, "Live dashboard preflight succeeded. Launch requested.\n")
            self.status_var.set("Opening Rift live dashboard")

        def on_error(exc: Exception) -> None:
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, f"Error: {exc}\n")
            self.status_var.set("Rift live dashboard launch failed")
            messagebox.showerror("Open live dashboard failed", str(exc))

        def on_finally() -> None:
            self._end_repo_background_job()

        self._run_in_background(worker, on_success, on_error, on_finally)

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self) -> None:
        self._is_closing = True
        self.stop_monitor(log=False)
        self.generic_scanner.detach(log_if_missing=False)
        if hasattr(self, "session_notes_text") and self.discovery_store:
            try:
                self._sync_session_notes_from_ui()
            except Exception as exc:
                self.logger.warning("Failed to save session notes during shutdown: %s", exc)
        try:
            self._save_ui_state()
        except Exception as exc:
            self.logger.warning("Failed to persist UI state during shutdown: %s", exc)
        self.logger.removeHandler(self.ui_log_handler)
        self.ui_log_handler.close()
        if self.discovery_store:
            try:
                self.discovery_store.close()
            except Exception as exc:
                self.logger.warning("Discovery store close failed: %s", exc)
        self.root.destroy()


def run_self_test(repo_root: Optional[Path] = None) -> int:
    import tempfile

    logger = setup_logger()
    bridge = RiftReaderBridge(logger, repo_root=repo_root)

    failures: list[str] = []
    results: list[tuple[str, str]] = []

    def safe_text(value: str) -> str:
        return value.encode("ascii", "backslashreplace").decode("ascii")

    def check(name: str, func: Callable[[], str | None]) -> None:
        try:
            detail = func() or "ok"
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            results.append((name, f"FAIL - {exc}"))
        else:
            results.append((name, f"PASS - {detail}"))

    def test_json_extractor() -> str:
        sample = (
            "noise before\n"
            + json.dumps(
                {
                    "ProcessName": "rift_x64",
                    "ProcessId": 1234,
                    "Memory": {"AddressHex": "0x1", "CoordX": 1.0},
                    "Match": {"CoordMatchesWithinTolerance": True},
                }
            )
        )
        payload = bridge._extract_last_json_object(sample)
        if not isinstance(payload, dict):
            raise AssertionError("extractor did not return a dict")
        if payload.get("ProcessName") != "rift_x64":
            raise AssertionError("extractor returned a nested object instead of the top-level payload")
        return "top-level payload extracted correctly"

    def test_repo_validation() -> str:
        missing = bridge.validate()
        if missing:
            raise AssertionError("missing required files:\n" + "\n".join(missing))
        return "repo layout valid"

    def test_dashboard_summary() -> str:
        output = bridge._run_powershell_script("build-dashboard-summary.ps1", timeout_seconds=120)
        if "dashboard-data.js" not in output:
            raise AssertionError("summary build output did not mention dashboard-data.js")
        return "dashboard summary build ok"

    def test_dashboard_live() -> str:
        output = bridge._run_powershell_script("build-dashboard-live-data.ps1", timeout_seconds=120)
        if "dashboard-live-data.js" not in output:
            raise AssertionError("live build output did not mention dashboard-live-data.js")
        return "dashboard live-data build ok"

    def test_debug_state() -> str:
        output = bridge.inspect_debug_state()
        if not output.strip():
            raise AssertionError("debug-state probe returned no output")
        first_line = output.splitlines()[0].strip()
        return f"debug-state probe ok ({safe_text(first_line[:120])})"

    def test_discovery_store() -> str:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "hub.db"
            store = DiscoveryStore(db_path)
            try:
                store.open_session(repo_root=str(bridge.repo_root), scanner_version=SCANNER_HUB_STORE_VERSION)
                store.add_event("self-test", "store event ok", {"repo_root": str(bridge.repo_root)})
                store.upsert_candidate(
                    canonical_key="self-test::candidate",
                    kind="pointer",
                    label="self-test candidate",
                    status="confirmed",
                    confidence=0.75,
                    absolute_address=0x1234,
                    source_kind="self-test",
                    metadata={"address_hex": "0x1234"},
                    evidence_kind="self-test",
                    evidence_summary="candidate insert ok",
                    evidence_metadata={"address_hex": "0x1234"},
                    verified=True,
                )
                store.set_setting("ui_state", {"process_name": "rift_x64.exe"})
                store.set_session_notes("session notes ok")
                import_id = store.create_import(
                    source_path=str(Path(temp_dir) / "sample.ct"),
                    label="sample",
                    entry_count=1,
                    warning_count=0,
                    metadata={"self_test": True},
                )
                store.replace_import_entries(
                    import_id,
                    [
                        {
                            "import_key": "ct::self-test",
                            "label": "sample entry",
                            "group_path": "Pointers",
                            "kind": "module-offset",
                            "status": "imported",
                            "confidence": 0.45,
                            "value_type": "Float",
                            "address_expression": "rift_x64.exe+0x1234",
                            "module_name": "rift_x64.exe",
                            "module_rva": 0x1234,
                            "resolved_address": None,
                            "offsets": [0x10, 0x20],
                            "notes": "self-test import entry",
                            "metadata": {"self_test": True},
                        }
                    ],
                )
                candidates = store.list_candidates(limit=10)
                if len(candidates) != 1:
                    raise AssertionError(f"expected 1 candidate, found {len(candidates)}")
                import_entries = store.list_import_entries(limit=10)
                if len(import_entries) != 1:
                    raise AssertionError(f"expected 1 import entry, found {len(import_entries)}")
                snapshot = store.build_session_snapshot()
                if snapshot["session"]["notes"] != "session notes ok":
                    raise AssertionError("session notes were not included in the export payload")
                summary = store.get_summary()
                if summary["candidate_count"] != 1 or summary["event_count"] != 1 or summary["import_count"] != 1:
                    raise AssertionError(f"unexpected discovery store counts: {summary}")
            finally:
                store.close()

        return "discovery store roundtrip ok"

    def test_ct_import_parser() -> str:
        sample_xml = """
<CheatTable>
  <CheatEntries>
    <CheatEntry>
      <ID>1</ID>
      <Description>"Root Pointers"</Description>
      <CheatEntries>
        <CheatEntry>
          <ID>2</ID>
          <Description>"Player Coord X"</Description>
          <VariableType>Float</VariableType>
          <Address>rift_x64.exe+0x93560E</Address>
          <Offsets>
            <Offset>0x158</Offset>
            <Offset>0x10</Offset>
          </Offsets>
        </CheatEntry>
        <CheatEntry>
          <ID>3</ID>
          <Description>"Coord Anchor Pattern"</Description>
          <Address>aobscanmodule(rift_x64.exe,F3 0F 10 86 5C 01 00 00)</Address>
        </CheatEntry>
      </CheatEntries>
    </CheatEntry>
  </CheatEntries>
</CheatTable>
""".strip()
        with tempfile.TemporaryDirectory() as temp_dir:
            ct_path = Path(temp_dir) / "sample.ct"
            ct_path.write_text(sample_xml, encoding="utf-8")
            table = parse_cheat_table(ct_path)
        if len(table.entries) < 3:
            raise AssertionError(f"expected at least 3 parsed CT entries, found {len(table.entries)}")
        pointer_entry = next((entry for entry in table.entries if entry.label == "Player Coord X"), None)
        if pointer_entry is None or pointer_entry.module_name != "rift_x64.exe":
            raise AssertionError("module-relative pointer entry was not parsed correctly")
        aob_entry = next((entry for entry in table.entries if entry.kind == "aob"), None)
        if aob_entry is None:
            raise AssertionError("AOB entry was not parsed from the CT sample")
        return f"ct import parser ok ({len(table.entries)} entries)"

    def test_recovery_snapshot() -> str:
        snapshot = load_recovery_snapshot(bridge.repo_root)
        if not snapshot.current_truth_path.exists():
            raise AssertionError("current-truth.md was not found")
        if not snapshot.truth_statuses:
            raise AssertionError("no truth status rows were parsed from current-truth.md")
        if not snapshot.runbook_text.strip():
            raise AssertionError("rebuild-runbook.md was empty")
        if snapshot.current_truth_last_updated_iso is None:
            raise AssertionError("current-truth last-updated date was not normalized")
        if "pattern:" not in snapshot.surviving_baselines_text:
            raise AssertionError("surviving baselines section did not include the coord-anchor pattern")
        return f"recovery snapshot ok ({len(snapshot.truth_statuses)} status rows)"

    check("json_extractor", test_json_extractor)
    check("repo_validation", test_repo_validation)
    check("discovery_store", test_discovery_store)
    check("ct_import_parser", test_ct_import_parser)
    check("recovery_snapshot", test_recovery_snapshot)
    check("dashboard_summary", test_dashboard_summary)
    check("dashboard_live", test_dashboard_live)
    check("debug_state", test_debug_state)

    for name, result in results:
        print(f"[SELFTEST] {safe_text(name)}: {safe_text(result)}")

    if failures:
        print("\nSelf-test failures:")
        for failure in failures:
            print(f" - {safe_text(failure)}")
        return 1

    print("\nAll self-tests passed.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Game Debug Scanner Hub (read-only)")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run non-GUI self-tests for the JSON extractor and RiftReader bridge wrappers.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Optional RiftReader repo root to use for self-test mode.",
    )
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(run_self_test(args.repo_root))

    print("Starting Game Debug Scanner Hub (read-only)")
    app = ScannerHubGUI()
    app.run()
