#!/usr/bin/env python3
"""Capture an AOB (array-of-byte) signature around a module-RVA root pointer.

Reads the pointer at the RVA, captures ±32 bytes of context, identifies a unique
byte pattern in the module, and writes a signature file for fast reacquisition
after game updates.

Safety: read-only. No input, no debugger, no memory writes.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SIGNATURES_DIR = Path(__file__).resolve().parents[1] / "signatures"

# AOB signature constants
_CONTEXT_BYTES = 32  # ± bytes of context to capture around the root pointer

# Windows API constants
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
MAX_MODULE_NAME32 = 255
MAX_PATH_WIN = 260


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("th32ModuleID", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("GlblcntUsage", ctypes.c_uint32),
        ("ProccntUsage", ctypes.c_uint32),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", ctypes.c_uint32),
        ("hModule", ctypes.c_void_p),
        ("szModule", ctypes.c_wchar * (MAX_MODULE_NAME32 + 1)),
        ("szExePath", ctypes.c_wchar * MAX_PATH_WIN),
    ]


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def open_process(pid: int) -> int:
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid
    )
    if not handle:
        raise OSError(f"OpenProcess failed for PID {pid}: winerr={ctypes.get_last_error()}")
    return handle


def close_handle(handle: int) -> None:
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)


def read_memory(handle: int, address: int, size: int) -> bytes:
    buf = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t(0)
    if not ctypes.windll.kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(address), buf, size, ctypes.byref(bytes_read)
    ):
        raise OSError(
            f"ReadProcessMemory failed at 0x{address:X}: winerr={ctypes.get_last_error()}"
        )
    if bytes_read.value != size:
        raise OSError(
            f"Short read at 0x{address:X}: got {bytes_read.value}, wanted {size}"
        )
    return buf.raw


def get_module_info(pid: int, module_name: str) -> dict[str, Any] | None:
    """Enumerate modules and find the one matching module_name (case-insensitive)."""
    snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid
    )
    if snapshot == -1:
        return None

    try:
        me = MODULEENTRY32W()
        me.dwSize = ctypes.sizeof(MODULEENTRY32W)

        if not ctypes.windll.kernel32.Module32FirstW(snapshot, ctypes.byref(me)):
            return None

        while True:
            name = me.szModule.lower()
            if name == module_name.lower():
                return {
                    "moduleName": me.szModule,
                    "moduleBase": me.modBaseAddr,
                    "moduleSize": me.modBaseSize,
                    "modulePath": me.szExePath,
                }

            if not ctypes.windll.kernel32.Module32NextW(snapshot, ctypes.byref(me)):
                break
    finally:
        ctypes.windll.kernel32.CloseHandle(snapshot)

    return None


def find_unique_pattern(module_bytes: bytes, root_rva: int, context_bytes: bytes) -> dict[str, Any] | None:
    """Find a unique AOB pattern in the module around the root RVA.

    Strategy: start with ±_CONTEXT_BYTES around the root, try smaller windows until
    we find a pattern that appears exactly once in the module. Worst-case O(m×n)
    linear scan over the module bytes — acceptable for a one-shot capture tool.
    """
    root_offset = root_rva - _CONTEXT_BYTES
    pattern_window = module_bytes[root_offset : root_offset + 2 * _CONTEXT_BYTES]

    # Try increasingly large windows until we find a unique pattern
    for window_size in range(8, min(len(pattern_window) + 1, 64), 4):
        # Center the window around the root pointer
        center = _CONTEXT_BYTES
        start = max(0, center - window_size // 2)
        end = min(len(pattern_window), start + window_size)
        if end - start < window_size:
            start = max(0, end - window_size)

        candidate = pattern_window[start:end]
        # Count occurrences in the module
        count = 0
        pos = 0
        while True:
            pos = module_bytes.find(candidate, pos)
            if pos == -1:
                break
            count += 1
            pos += 1

        if count == 1:
            # Found unique pattern — build AOB string with wildcards for pointers
            aob_parts = []
            raw_offset = root_rva - (_CONTEXT_BYTES - start)
            for i, b in enumerate(candidate):
                abs_rva = raw_offset + i
                # If this byte is part of the root pointer (the 8 bytes at root_rva),
                # mark it as wildcard since the absolute address changes per session
                if root_rva <= abs_rva < root_rva + 8:
                    aob_parts.append("??")
                else:
                    aob_parts.append(f"{b:02X}")

            return {
                "aobPattern": " ".join(aob_parts),
                "patternSize": len(candidate),
                "windowStartRva": raw_offset,
                "windowEndRva": raw_offset + len(candidate),
                "rootRvaInPattern": root_rva - raw_offset,
                "moduleScanCount": count,
            }

    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture an AOB signature around a module-RVA root pointer"
    )
    parser.add_argument("--rva", required=True, help="Root RVA in hex (e.g., 0x32EBC80)")
    parser.add_argument("--label", required=True, help="Short label for the signature file")
    parser.add_argument("--pid", type=int, required=True, help="Target RIFT process ID")
    parser.add_argument("--module-name", default="rift_x64.exe", help="Module name (default: rift_x64.exe)")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    rva = int(args.rva, 16)
    module_name = args.module_name

    # Step 1: Enumerate module
    mod = get_module_info(args.pid, module_name)
    if mod is None:
        result = {"status": "failed", "verdict": "module-not-found", "error": f"{module_name} not found in PID {args.pid}"}
        if args.json:
            json.dump(result, sys.stdout, indent=2)
        else:
            print(f"ERROR: {module_name} not found in PID {args.pid}")
        sys.exit(1)

    module_base = mod["moduleBase"]
    module_size = mod["moduleSize"]

    if not args.json:
        print(f"Module: {mod['moduleName']} base=0x{module_base:X} size={module_size}")

    # Validity: RVA must be within the module bounds with _CONTEXT_BYTES margin
    if rva < _CONTEXT_BYTES or rva + _CONTEXT_BYTES >= module_size:
        result = {
            "status": "failed",
            "verdict": "rva-out-of-module-bounds",
            "error": f"RVA 0x{rva:X} is too close to module edge (size={module_size}, need ±{_CONTEXT_BYTES} bytes of context)",
        }
        if args.json:
            json.dump(result, sys.stdout, indent=2)
        else:
            print(f"ERROR: RVA 0x{rva:X} is too close to module edge (size={module_size})")
        sys.exit(1)

    if module_size < _CONTEXT_BYTES * 2:
        result = {
            "status": "failed",
            "verdict": "module-too-small",
            "error": f"Module {module_name} is too small ({module_size} bytes) for AOB capture",
        }
        if args.json:
            json.dump(result, sys.stdout, indent=2)
        else:
            print(f"ERROR: Module {module_name} is too small ({module_size} bytes)")
        sys.exit(1)

    # Step 2: Read pointer at RVA
    handle = open_process(args.pid)
    try:
        root_addr = module_base + rva
        raw = read_memory(handle, root_addr, 8)
        owner_ptr = struct.unpack_from("<Q", raw, 0)[0]

        # Step 3: Read context bytes (±32 bytes)
        context_start = root_addr - 32
        context_bytes = read_memory(handle, context_start, 64)
    finally:
        close_handle(handle)

    if not args.json:
        print(f"Root pointer at 0x{root_addr:X}: 0x{owner_ptr:X}")
        print(f"Context: {context_bytes[:32].hex(' ')} [{raw.hex(' ')}] {context_bytes[40:].hex(' ')}")

    # Step 4: Read the full module bytes for pattern uniqueness scan
    # We only need the module, not the full process memory
    handle = open_process(args.pid)
    try:
        module_bytes = read_memory(handle, module_base, module_size)
    finally:
        close_handle(handle)

    # Step 5: Find unique AOB pattern
    pattern = find_unique_pattern(module_bytes, rva, context_bytes)
    if pattern is None:
        result = {
            "status": "failed",
            "verdict": "no-unique-pattern-found",
            "error": f"Could not find unique AOB pattern near RVA 0x{rva:X}",
        }
        if args.json:
            json.dump(result, sys.stdout, indent=2)
        else:
            print(f"ERROR: Could not find unique AOB pattern near RVA 0x{rva:X}")
        sys.exit(1)

    # Step 6: Build signature file
    captured_at = utc_iso()
    safe_label = args.label.lower().replace(" ", "-").replace("_", "-")
    sig = {
        "schemaVersion": 1,
        "kind": "riftreader-aob-signature",
        "capturedAtUtc": captured_at,
        "label": args.label,
        "module": module_name,
        "rva": f"0x{rva:X}",
        "chain": f"[{module_name}+0x{rva:X}]",
        "whatThisFinds": "Player owner pointer root — dereference to reach the player object (coordinates at +0x320, facing target at +0x30C, candidate/support yaw-adjacent scalar at +0x304)",
        "sessionContext": {
            "pid": args.pid,
            "moduleBase": f"0x{module_base:X}",
            "moduleSize": module_size,
            "rootAddress": f"0x{root_addr:X}",
            "ownerPointerValue": f"0x{owner_ptr:X}",
        },
        "signature": pattern,
        "validation": {
            "status": "pending",
            "instructions": "After capturing, validate by restarting RIFT and running: dotnet run --project reader/RiftReader.Reader -- --process-name rift_x64 --scan-module-pattern \"<aob>\" --json",
        },
    }

    # Step 7: Write signature file
    module_dir = SIGNATURES_DIR / module_name.replace(".exe", "")
    module_dir.mkdir(parents=True, exist_ok=True)
    sig_path = module_dir / f"root_{safe_label}.json"
    sig_path.write_text(json.dumps(sig, indent=2), encoding="utf-8")

    result = {
        "status": "passed",
        "verdict": "aob-signature-captured",
        "signaturePath": str(sig_path.relative_to(Path.cwd())),
        "signature": pattern,
        "ownerPointer": f"0x{owner_ptr:X}",
        "capturedAtUtc": captured_at,
    }

    if args.json:
        json.dump(result, sys.stdout, indent=2)
    else:
        print(f"\n✅ Signature captured: {sig_path}")
        print(f"   AOB: {pattern['aobPattern']}")
        print(f"   Unique: {pattern['moduleScanCount'] == 1}")
        print(f"   Owner: 0x{owner_ptr:X}")
        print(f"\nTo validate after a restart:")
        print(f'   dotnet run --project reader/RiftReader.Reader -- --process-name rift_x64 --scan-module-pattern "{pattern["aobPattern"]}" --json')


if __name__ == "__main__":
    main()
