"""Top-level Lua memory reader API for RIFT.

Usage:
    from lua_memory import LuaReader

    with LuaReader.from_process_name("rift_x64") as reader:
        # Read a string global
        player = reader.get_string("RiftReaderApiProbe_Player")

        # Read all globals
        globals = reader.get_all_globals()

        # Get just the names of all globals
        names = reader.list_globals()
"""

import json
import struct
import time
from dataclasses import dataclass, field
from typing import Optional

from .process import ProcessMemory
from .scanner import LuaStateFinder, GlobalEntry
from .lua_types import LuaType


@dataclass
class ReaderStats:
    """Statistics about a read operation."""
    scan_time: float = 0
    globals_found: int = 0
    global_table_addr: int = 0
    string_table_addrs: list = field(default_factory=list)
    cached: bool = False


class LuaReader:
    """High-level API for reading Lua 5.1 globals from RIFT process memory.

    First read does a full heap scan to find the Lua state and global table.
    Subsequent reads use cached addresses for instant access.
    """

    def __init__(self, pm: ProcessMemory, verbose: bool = False):
        self._pm = pm
        self._finder = LuaStateFinder(pm)
        self._verbose = verbose
        self._initialized = False
        self._stats = ReaderStats()

    @classmethod
    def from_pid(cls, pid: int, verbose: bool = False) -> "LuaReader":
        """Create a reader for a process by PID."""
        pm = ProcessMemory(pid)
        return cls(pm, verbose=verbose)

    @classmethod
    def from_process_name(cls, name: str, verbose: bool = False) -> "LuaReader":
        """Create a reader by process name (e.g., 'rift_x64')."""
        import subprocess
        result = subprocess.run(
            ["powershell", "-Command",
             f"(Get-Process '{name}' -ErrorAction SilentlyContinue).Id"],
            capture_output=True, text=True
        )
        pids = [int(x.strip()) for x in result.stdout.strip().split("\n") if x.strip()]
        if not pids:
            raise ValueError(f"Process '{name}' not found")
        return cls.from_pid(pids[0], verbose=verbose)

    def close(self):
        self._pm.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _ensure_initialized(self):
        """Run the initial scan if not done yet."""
        if self._initialized:
            return

        t0 = time.time()

        # Step 1: Find known Lua strings
        if self._verbose:
            print("[LuaReader] Scanning for Lua strings...")
        strings = self._finder.scan_for_lua_strings(verbose=self._verbose)
        if not strings:
            raise RuntimeError("No Lua strings found. RIFT may not be running or addon not loaded.")

        # Step 2: Find the global table
        if self._verbose:
            print("[LuaReader] Finding global table (_G)...")
        gt_addr = self._finder.find_global_table(verbose=self._verbose)
        if not gt_addr:
            raise RuntimeError("Could not find global table (_G).")

        # Step 3: Parse all globals
        if self._verbose:
            print("[LuaReader] Parsing globals...")
        globals_dict = self._finder.read_globals(verbose=self._verbose)

        self._initialized = True
        self._stats = ReaderStats(
            scan_time=time.time() - t0,
            globals_found=len(globals_dict),
            global_table_addr=gt_addr,
            cached=False,
        )

        if self._verbose:
            print(f"[LuaReader] Initialized in {self._stats.scan_time:.1f}s — "
                  f"{self._stats.globals_found} globals found")

    def get_string(self, name: str) -> Optional[str]:
        """Read a string global by name. Returns None if not found or not a string."""
        self._ensure_initialized()
        return self._finder.read_global_string(name)

    def get_number(self, name: str) -> Optional[float]:
        """Read a number global by name."""
        self._ensure_initialized()
        return self._finder.read_global_number(name)

    def get_global(self, name: str) -> Optional[dict]:
        """Read any global by name. Returns a dict with type and value info."""
        self._ensure_initialized()
        globals_dict = self._finder.read_globals()
        entry = globals_dict.get(name)
        if not entry:
            return None

        result = {
            "name": entry.name,
            "type": entry.value_type,
            "tt": entry.value_tt,
            "address": hex(entry.value_raw),
        }

        # Try to read the actual value
        if entry.value_tt == LuaType.TSTRING:
            val = self._finder.read_global_string(name)
            result["value"] = val
            result["length"] = len(val) if val else 0
        elif entry.value_tt == LuaType.TNUMBER:
            raw_bytes = entry.value_raw.to_bytes(8, "little")
            result["value"] = struct.unpack("d", raw_bytes)[0]
        elif entry.value_tt == LuaType.TBOOLEAN:
            result["value"] = bool(entry.value_raw)
        elif entry.value_tt == LuaType.TNIL:
            result["value"] = None
        elif entry.value_tt == LuaType.TTABLE:
            result["value"] = f"<table at {hex(entry.value_raw)}>"
        elif entry.value_tt == LuaType.TFUNCTION:
            result["value"] = f"<function at {hex(entry.value_raw)}>"
        else:
            result["value"] = f"<{entry.value_type} at {hex(entry.value_raw)}>"

        return result

    def get_all_globals(self, include_non_string: bool = False) -> dict[str, dict]:
        """Read all globals. Returns dict of name -> value info.

        By default, only includes string globals (most useful for addons).
        Set include_non_string=True to include all types.
        """
        self._ensure_initialized()
        globals_dict = self._finder.read_globals()
        result = {}

        for name, entry in globals_dict.items():
            if not include_non_string and entry.value_tt != LuaType.TSTRING:
                continue
            info = self.get_global(name)
            if info:
                result[name] = info

        return result

    def list_globals(self) -> list[str]:
        """List all global variable names."""
        self._ensure_initialized()
        return list(self._finder.read_globals().keys())

    def list_string_globals(self) -> list[str]:
        """List only string global names."""
        self._ensure_initialized()
        return [
            name for name, entry in self._finder.read_globals().items()
            if entry.value_tt == LuaType.TSTRING
        ]

    def get_string_value(self, name: str) -> Optional[str]:
        """Shorthand: read a string global and return just the string value."""
        return self.get_string(name)

    def get_stats(self) -> ReaderStats:
        """Get statistics about the last scan."""
        self._ensure_initialized()
        return self._stats

    def invalidate(self):
        """Force a fresh scan on next read."""
        self._finder.invalidate_cache()
        self._initialized = False
