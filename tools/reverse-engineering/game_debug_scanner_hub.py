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
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable, Optional


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
                f"{script_name} failed with exit code {completed.returncode}.\n{output or '(no output)'}"
            )

        return output

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

        self.monitor_thread: threading.Thread | None = None
        self.monitor_stop_event = threading.Event()
        self.scan_in_progress = False
        self.hex_read_in_progress = False
        self.generic_background_jobs = 0
        self.last_rift_snapshot: RiftPlayerSnapshot | None = None
        self._is_closing = False

        self._build_ui()
        self._sync_repo_status()
        self.root.after(75, self._drain_log_queue)

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._create_process_tab()
        self._create_aob_tab()
        self._create_pointer_tab()
        self._create_monitor_tab()
        self._create_hex_tab()
        self._create_rift_tab()
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

    def _create_log_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Log")

        self.log_text = scrolledtext.ScrolledText(
            tab,
            height=24,
            bg="#000000",
            fg="#00FF00",
            insertbackground="#00FF00",
            font=("Consolas", 10),
        )
        self.log_text.pack(fill="both", expand=True)

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
            return

        if core_ready and dashboard_ready and not live_dashboard_ready:
            self.rift_repo_status_var.set("Repo partial: live dashboard prerequisites missing")
            return

        if core_ready and not dashboard_ready:
            self.rift_repo_status_var.set("Repo partial: dashboard prerequisites missing")
            return

        self.rift_repo_status_var.set("Repo invalid: missing required files")

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

        try:
            self.root.after(0, callback)
        except tk.TclError:
            pass

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
            messagebox.showerror("Attach failed", str(exc))
            self._refresh_generic_control_states()
            return

        self.proc_status_var.set(
            f"Attached to {info.process_name} (PID {info.process_id}, {info.pointer_size * 8}-bit)"
        )
        self.pointer_size_var.set(f"{info.pointer_size * 8}-bit")
        self.status_var.set(f"Attached to {info.process_name}")
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
        self._refresh_generic_control_states()

    def do_aob_scan(self) -> None:
        if self.scan_in_progress:
            messagebox.showinfo("Scan in progress", "Wait for the current scan to finish.")
            return
        if not self._begin_generic_background_job():
            return

        pattern_text = self.aob_entry.get().strip()
        module_name = self.aob_module_entry.get().strip() or None

        self.scan_in_progress = True
        self._refresh_generic_control_states()
        self.aob_status_var.set("Scanning...")
        self.aob_results.delete("1.0", tk.END)

        def worker() -> AobScanResult:
            return self.generic_scanner.aob_scan(pattern_text, module_name)

        def on_success(result: object) -> None:
            assert isinstance(result, AobScanResult)
            self.aob_results.insert(
                tk.END,
                f"Pattern: {result.pattern_text}\n"
                f"Scope:   {result.module_name or 'full process'}\n"
                f"Time:    {result.duration_seconds:.2f}s\n"
                f"Hits:    {len(result.addresses)}\n\n",
            )
            preview = result.addresses[:200]
            for address in preview:
                self.aob_results.insert(tk.END, f"0x{address:X}\n")
            if len(result.addresses) > len(preview):
                self.aob_results.insert(tk.END, f"\n... and {len(result.addresses) - len(preview)} more\n")
            self.aob_status_var.set(f"Completed: {len(result.addresses)} hit(s)")
            self.status_var.set("AOB scan completed")

        def on_error(exc: Exception) -> None:
            self.aob_status_var.set("Scan failed")
            self.status_var.set("AOB scan failed")
            self.aob_results.insert(tk.END, f"Error: {exc}\n")
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
            dump_address, data = result  # type: ignore[misc]
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

    def validate_repo_path(self) -> None:
        self._sync_repo_status()
        missing = self.rift_bridge.validate()
        if missing:
            messagebox.showerror("Invalid RiftReader repo", "Missing required files:\n\n" + "\n".join(missing))
            return

        self.status_var.set("RiftReader repo validated")

    def read_rift_current_player(self) -> None:
        self._sync_repo_status()
        if not self.rift_bridge.is_available():
            messagebox.showerror("RiftReader unavailable", "The configured repo path is not valid.")
            return

        self.rift_output.delete("1.0", tk.END)
        self.rift_output.insert(tk.END, "Reading current player...\n")
        self.status_var.set("Reading Rift current player")

        def worker() -> tuple[RiftPlayerSnapshot, str]:
            return self.rift_bridge.read_current_player()

        def on_success(result: object) -> None:
            snapshot, raw_output = result  # type: ignore[misc]
            self.last_rift_snapshot = snapshot
            self._seed_generic_fields_from_rift(snapshot)
            self.rift_player_summary_var.set(self._format_rift_snapshot(snapshot))
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, raw_output + "\n")
            self.status_var.set("Rift current player loaded")

        def on_error(exc: Exception) -> None:
            self.rift_player_summary_var.set("No Rift snapshot loaded")
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, f"Error: {exc}\n")
            self.status_var.set("Rift current player read failed")
            messagebox.showerror("Rift current player read failed", str(exc))

        self._run_in_background(worker, on_success, on_error)

    def inspect_rift_debug_state(self) -> None:
        self._sync_repo_status()
        if not self.rift_bridge.is_available():
            messagebox.showerror("RiftReader unavailable", "The configured repo path is not valid.")
            return

        self.rift_output.delete("1.0", tk.END)
        self.rift_output.insert(tk.END, "Inspecting Rift debug state...\n")
        self.status_var.set("Inspecting Rift debug state")

        def worker() -> str:
            return self.rift_bridge.inspect_debug_state()

        def on_success(result: object) -> None:
            assert isinstance(result, str)
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, result + "\n")
            self.status_var.set("Rift debug-state probe completed")

        def on_error(exc: Exception) -> None:
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, f"Error: {exc}\n")
            self.status_var.set("Rift debug-state probe failed")
            messagebox.showerror("Rift debug-state probe failed", str(exc))

        self._run_in_background(worker, on_success, on_error)

    def open_rift_dashboard(self) -> None:
        self._sync_repo_status()
        missing_dashboard = self.rift_bridge.validate_dashboard(live=False)
        if missing_dashboard:
            messagebox.showerror(
                "RiftReader dashboard unavailable",
                "Missing required dashboard files:\n\n" + "\n".join(missing_dashboard),
            )
            return

        self.rift_output.delete("1.0", tk.END)
        self.rift_output.insert(tk.END, "Preparing dashboard...\n")
        self.status_var.set("Preparing Rift dashboard")

        def worker() -> str:
            return self.rift_bridge.open_dashboard(live=False)

        def on_success(result: object) -> None:
            assert isinstance(result, str)
            self.rift_output.delete("1.0", tk.END)
            if result:
                self.rift_output.insert(tk.END, result + "\n\n")
            self.rift_output.insert(tk.END, "Dashboard preflight succeeded. Launch requested.\n")
            self.status_var.set("Opening Rift dashboard")

        def on_error(exc: Exception) -> None:
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, f"Error: {exc}\n")
            self.status_var.set("Rift dashboard launch failed")
            messagebox.showerror("Open dashboard failed", str(exc))

        self._run_in_background(worker, on_success, on_error)

    def open_rift_live_dashboard(self) -> None:
        self._sync_repo_status()
        missing_live_dashboard = self.rift_bridge.validate_dashboard(live=True)
        if missing_live_dashboard:
            messagebox.showerror(
                "RiftReader live dashboard unavailable",
                "Missing required live dashboard files:\n\n" + "\n".join(missing_live_dashboard),
            )
            return

        self.rift_output.delete("1.0", tk.END)
        self.rift_output.insert(tk.END, "Preparing live dashboard...\n")
        self.status_var.set("Preparing Rift live dashboard")

        def worker() -> str:
            return self.rift_bridge.open_dashboard(live=True)

        def on_success(result: object) -> None:
            assert isinstance(result, str)
            self.rift_output.delete("1.0", tk.END)
            if result:
                self.rift_output.insert(tk.END, result + "\n\n")
            self.rift_output.insert(tk.END, "Live dashboard preflight succeeded. Launch requested.\n")
            self.status_var.set("Opening Rift live dashboard")

        def on_error(exc: Exception) -> None:
            self.rift_output.delete("1.0", tk.END)
            self.rift_output.insert(tk.END, f"Error: {exc}\n")
            self.status_var.set("Rift live dashboard launch failed")
            messagebox.showerror("Open live dashboard failed", str(exc))

        self._run_in_background(worker, on_success, on_error)

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self) -> None:
        self._is_closing = True
        self.stop_monitor(log=False)
        self.generic_scanner.detach(log_if_missing=False)
        self.logger.removeHandler(self.ui_log_handler)
        self.ui_log_handler.close()
        self.root.destroy()


def run_self_test(repo_root: Optional[Path] = None) -> int:
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

    check("json_extractor", test_json_extractor)
    check("repo_validation", test_repo_validation)
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
