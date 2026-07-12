#!/usr/bin/env python3
"""
Resolve player coordinates from RIFT process memory.

Dual-mode:
1. Chain mode (default): rift_x64+0x32EBDC0 -> heap object -> +0x320/+0x324/+0x328 (X/Y/Z)
2. Registry mode (--registry): Assets repo approach — scan for Inspect.Unit.Detail,
   resolve handler → registry → unit object → coordinates

Usage:
    python resolve-player-coords.py --pid <pid>                  # one-shot, chain mode
    python resolve-player-coords.py --pid <pid> --registry       # one-shot, registry mode
    python resolve-player-coords.py --pid <pid> --json           # one-shot, JSON
    python resolve-player-coords.py --pid <pid> --watch          # continuous poll, writes latest.json
    python resolve-player-coords.py --pid <pid> --watch --interval 100
"""

import argparse
import ctypes
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

kernel32 = ctypes.windll.kernel32

# --- Chain configuration ---
COORD_GLOBAL_RVA = 0x32EBDC0
OFFSET_X = 0x320
OFFSET_Y = 0x324
OFFSET_Z = 0x328
OFFSET_HEADING_RAW = 0x300
OFFSET_SPEED = 0x304
PROCESS_VM_READ = 0x0010

# --- Registry configuration (from Assets repo) ---
SIGNATURE_DB_PATH = Path(__file__).parent / "lua_memory" / "rift-x64-signatures.json"
IMAGE_BASE = 0x140000000  # RIFT's preferred image base


def find_module_base(pid):
    """Find rift_x64.exe base address in target process."""
    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not handle:
        return None, "Cannot open process with VM_READ"

    # Fast path: try known bases
    known_bases = [0x7FF728B80000, 0x7FF728A00000, 0x7FF728C00000, 0x7FF6EE5D0000]
    for addr in known_bases:
        data = _read_bytes(handle, addr, 2)
        if data == b"MZ":
            kernel32.CloseHandle(handle)
            return addr, None

    # Broader scan
    try:
        for page in range(0x7FF00000, 0x7FFF0000, 0x1000):
            addr = page * 0x10000
            data = _read_bytes(handle, addr, 2)
            if data == b"MZ":
                kernel32.CloseHandle(handle)
                return addr, None
    except Exception:
        pass

    kernel32.CloseHandle(handle)
    return None, "Cannot find MZ header in expected address range"


def _read_bytes(handle, address, size):
    """Read raw bytes from process memory."""
    buf = ctypes.create_string_buffer(size)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(br))
    if not ok or br.value != size:
        return None
    return buf.raw


def _read_u64(handle, address):
    data = _read_bytes(handle, address, 8)
    return ctypes.c_ulonglong.from_buffer_copy(data).value if data else None


def _read_f32(handle, address):
    data = _read_bytes(handle, address, 4)
    return ctypes.c_float.from_buffer_copy(data).value if data else None


def _load_signature_db():
    """Load the binary signature database."""
    if SIGNATURE_DB_PATH.exists():
        return json.loads(SIGNATURE_DB_PATH.read_text(encoding="utf-8"))
    return {}


def _find_api_string(handle, module_base, needle_bytes):
    """Scan .rdata for a null-terminated string containing needle_bytes."""
    # .rdata section typically starts after .text (which is ~39MB for RIFT)
    # Scan from module_base + 0x2000000 to module_base + 0x4000000
    scan_start = module_base + 0x2000000
    scan_end = module_base + 0x4000000

    CHUNK = 0x100000
    for offset in range(0, scan_end - scan_start, CHUNK):
        chunk_start = scan_start + offset
        chunk_size = min(CHUNK, scan_end - chunk_start)
        data = _read_bytes(handle, chunk_start, chunk_size)
        if not data:
            continue

        pos = data.find(needle_bytes)
        if pos >= 0:
            # Walk backward to find null terminator (start of string)
            str_start = pos
            while str_start > 0 and data[str_start - 1] != 0:
                str_start -= 1
            # Walk forward to find null terminator (end of string)
            str_end = pos + len(needle_bytes)
            while str_end < len(data) and data[str_end] != 0:
                str_end += 1

            full_str = data[str_start:str_end]
            if needle_bytes in full_str:
                return chunk_start + str_start

    return None


def _scan_pattern(handle, module_base, pattern_bytes, scan_start=None, scan_end=None):
    """Scan memory for an exact byte pattern. Returns first match address."""
    if scan_start is None:
        scan_start = module_base
    if scan_end is None:
        scan_end = module_base + 0x8000000  # 128MB scan range

    CHUNK = 0x100000
    for offset in range(0, scan_end - scan_start, CHUNK):
        chunk_start = scan_start + offset
        chunk_size = min(CHUNK, scan_end - chunk_start)
        data = _read_bytes(handle, chunk_start, chunk_size)
        if not data:
            continue

        pos = data.find(pattern_bytes)
        if pos >= 0:
            return chunk_start + pos

    return None


def resolve_state_registry(pid):
    """Resolve player coordinates using the Assets repo registry-based approach.

    Strategy:
    1. Find Inspect.Unit.Detail string in .rdata
    2. Find registry accessor instruction
    3. Resolve LEA RIP-relative to get registry base
    4. Scan registry for player entries (player_flag == 1)
    5. Read coordinates from player sub-structure
    """
    now = datetime.now(timezone.utc)
    state = {
        "ok": False,
        "source": "memory-reader",
        "transport": "registry-based",
        "updatedAt": now.isoformat(timespec="milliseconds"),
        "capturedAt": now.isoformat(timespec="milliseconds"),
        "pid": pid,
        "method": "registry-based (Assets repo)",
        "position": None,
        "navigation": None,
        "player": None,
        "protocol": {"version": 1, "valid": True, "transport": "registry-based"},
        "blockers": [],
        "warnings": [],
    }

    # Load signature database
    sig_db = _load_signature_db()
    if not sig_db:
        state["blockers"].append("Signature database not found")
        return state

    # Find module base
    base, err = find_module_base(pid)
    if err:
        state["blockers"].append(err)
        return state
    state["moduleBase"] = hex(base)

    # Open process
    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not handle:
        state["blockers"].append("Cannot open process with VM_READ")
        return state

    try:
        # Step 1: Find the Inspect.Unit.Detail string
        api_string_anchor = None
        for anchor in sig_db.get("Anchors", []):
            if anchor["Name"] == "api-anchor-inspect-unit-detail":
                api_string_anchor = anchor
                break

        if not api_string_anchor:
            state["blockers"].append("API anchor not found in signature database")
            return state

        # Convert signature hex to bytes (skip the null terminator)
        sig_hex = api_string_anchor["SignatureHex"]
        sig_bytes = bytes.fromhex(sig_hex.replace("??", "00").replace(" ", ""))
        needle = sig_bytes.rstrip(b"\x00")  # Remove trailing null for search

        api_string_addr = _find_api_string(handle, base, needle)
        if not api_string_addr:
            state["blockers"].append("Inspect.Unit.Detail string not found in .rdata")
            return state

        state["apiStringAddr"] = hex(api_string_addr)

        # Step 2: Find the registry accessor instruction
        registry_accessor = None
        for anchor in sig_db.get("Anchors", []):
            if anchor["Name"] == "registry-accessor":
                registry_accessor = anchor
                break

        if not registry_accessor:
            state["blockers"].append("Registry accessor anchor not found")
            return state

        # Scan for the accessor pattern
        accessor_sig = bytes.fromhex(registry_accessor["SignatureHex"].replace("??", "00").replace(" ", ""))
        accessor_addr = _scan_pattern(handle, base, accessor_sig)

        if not accessor_addr:
            state["blockers"].append("Registry accessor pattern not found in memory")
            return state

        state["registryAccessorAddr"] = hex(accessor_addr)

        # Step 3: Resolve the LEA instruction to get registry base
        # The LEA is 7 bytes before the MOV instruction
        # LEA RCX, [RIP + disp32] at 0x140758b14
        # MOV RAX, [RCX + RAX * 8 + 0x810] at 0x140758bd3
        lea_offset = 0x140758bd3 - 0x140758b14  # = 0xBF
        lea_addr = accessor_addr - lea_offset

        # Read the LEA instruction: 48 8D 0D XX XX XX XX
        lea_data = _read_bytes(handle, lea_addr, 7)
        if not lea_data or lea_data[0:3] != b"\x48\x8D\x0D":
            state["blockers"].append("LEA instruction not found at expected offset")
            return state

        # Decode RIP-relative address
        disp32 = int.from_bytes(lea_data[3:7], "little", signed=True)
        # RIP points to next instruction (lea_addr + 7)
        # target_va is already a runtime address since lea_addr is runtime
        registry_base = lea_addr + 7 + disp32

        state["registryBase"] = hex(registry_base)

        # Step 4: Scan registry for player entries
        struct_db = sig_db.get("Structs", [])
        unit_struct = None
        player_struct = None
        for s in struct_db:
            if s["Name"] == "UnitObject":
                unit_struct = s
            elif s["Name"] == "LocalPlayer":
                player_struct = s

        if not unit_struct or not player_struct:
            state["blockers"].append("UnitObject or LocalPlayer struct not in signature database")
            return state

        unit_offsets = {f["Name"]: f["Offset"] for f in unit_struct.get("Fields", [])}
        player_offsets = {f["Name"]: f["Offset"] for f in player_struct.get("Fields", [])}

        # Scan up to 1024 registry entries
        for i in range(1024):
            unit_ptr = _read_u64(handle, registry_base + i * 8)
            if not unit_ptr or unit_ptr < 0x10000:
                continue

            # Check player_flag
            player_flag = _read_u32(handle, unit_ptr + unit_offsets.get("player_flag", 0x120))
            if player_flag != 1:
                continue

            # Found a player! Read coordinates from sub-structure
            details_ptr = _read_u64(handle, unit_ptr + unit_offsets.get("details_substructure", 0x6E0))
            if not details_ptr or details_ptr < 0x10000:
                continue

            x = _read_f32(handle, details_ptr + player_offsets.get("pos_x", 0x320))
            y = _read_f32(handle, details_ptr + player_offsets.get("pos_y", 0x324))
            z = _read_f32(handle, details_ptr + player_offsets.get("pos_z", 0x328))

            if x is not None and y is not None and z is not None:
                if abs(x) < 100000 and abs(y) < 100000 and abs(z) < 100000:
                    state["position"] = {"x": round(x, 4), "y": round(y, 4), "z": round(z, 4)}
                    state["navigation"] = {
                        "yawDeg": None,  # Registry approach doesn't give heading directly
                        "isMoving": False,
                        "speed": None,
                        "facingSource": "registry-based",
                    }
                    state["registryIndex"] = i
                    state["unitPtr"] = hex(unit_ptr)
                    state["detailsPtr"] = hex(details_ptr)
                    state["ok"] = True
                    return state

        state["blockers"].append("No player found in registry (scanned 1024 entries)")
        return state

    finally:
        kernel32.CloseHandle(handle)


def _read_u32(handle, address):
    data = _read_bytes(handle, address, 4)
    return ctypes.c_uint32.from_buffer_copy(data).value if data else None


def resolve_state(pid):
    """Read full player state from memory. Returns dict matching watch_rift.py output shape."""
    now = datetime.now(timezone.utc)
    state = {
        "ok": False,
        "source": "memory-reader",
        "transport": "memory-chain",
        "updatedAt": now.isoformat(timespec="milliseconds"),
        "capturedAt": now.isoformat(timespec="milliseconds"),
        "pid": pid,
        "chain": {
            "globalRva": hex(COORD_GLOBAL_RVA),
            "offsets": {"x": hex(OFFSET_X), "y": hex(OFFSET_Y), "z": hex(OFFSET_Z), "heading": hex(OFFSET_HEADING_RAW)},
        },
        "position": None,
        "navigation": None,
        "player": None,
        "protocol": {"version": 1, "valid": True, "transport": "memory-chain"},
        "blockers": [],
        "warnings": [],
    }

    # Find module base
    base, err = find_module_base(pid)
    if err:
        state["blockers"].append(err)
        return state
    state["moduleBase"] = hex(base)

    # Open process
    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not handle:
        state["blockers"].append("Cannot open process with VM_READ")
        return state

    try:
        # Read global pointer
        obj_ptr = _read_u64(handle, base + COORD_GLOBAL_RVA)
        if obj_ptr is None:
            state["blockers"].append("Cannot read global pointer")
            return state

        if obj_ptr == 0 or obj_ptr < 0x10000:
            state["blockers"].append("Global pointer invalid: " + hex(obj_ptr) if obj_ptr else "Global pointer null (not in world?)")
            return state

        # Read coordinates
        x = _read_f32(handle, obj_ptr + OFFSET_X)
        y = _read_f32(handle, obj_ptr + OFFSET_Y)
        z = _read_f32(handle, obj_ptr + OFFSET_Z)
        heading_raw = _read_f32(handle, obj_ptr + OFFSET_HEADING_RAW)
        speed = _read_f32(handle, obj_ptr + OFFSET_SPEED)

        if any(v is None for v in (x, y, z, heading_raw)):
            state["blockers"].append("Cannot read coordinate fields from object")
            return state

        # Validate
        if any(math.isnan(v) or math.isinf(v) for v in (x, y, z)):
            state["blockers"].append("Coordinate contains NaN or Infinity")
            return state

        if abs(x) > 100000 or abs(y) > 100000 or abs(z) > 100000:
            state["warnings"].append("Coordinates look unreasonable")

        if x == 0.0 and y == 0.0 and z == 0.0:
            state["warnings"].append("All coordinates zero — player may not be loaded")

        # Compute heading (cumulative rotation mod 360)
        heading_deg = round(heading_raw % 360, 4) if heading_raw is not None else None

        # Detect movement (speed threshold)
        is_moving = abs(speed) > 0.1 if speed is not None else False

        state["position"] = {"x": round(x, 4), "y": round(y, 4), "z": round(z, 4)}
        state["navigation"] = {
            "yawDeg": heading_deg,
            "isMoving": is_moving,
            "speed": round(speed, 4) if speed is not None else None,
            "facingSource": "memory-chain",
        }
        state["ok"] = True
        return state

    finally:
        kernel32.CloseHandle(handle)


def _write_atomic(path, payload):
    """Write JSON atomically."""
    tmp = Path(str(path) + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def watch_loop(pid, output_path, interval_ms):
    """Continuous polling loop matching watch_rift.py output format."""
    print(f"Memory reader started. pid={pid} interval={interval_ms}ms output={output_path}")
    print("Press Ctrl+C to stop.", flush=True)

    iteration = 0
    while True:
        iteration += 1
        t0 = time.monotonic()

        state = resolve_state(pid)
        state["iteration"] = iteration

        payload = json.dumps(state, separators=(",", ":"), sort_keys=True)
        try:
            _write_atomic(output_path, payload)
        except OSError as exc:
            print(f"  write failed: {exc}", flush=True)

        # Compact status line
        if state["ok"]:
            p = state["position"]
            n = state["navigation"]
            heading = n.get("yawDeg", "?") if n else "?"
            print(f"  #{iteration} X={p['x']:.1f} Y={p['y']:.1f} Z={p['z']:.1f} H={heading}°", flush=True)
        else:
            print(f"  #{iteration} BLOCKED: {'; '.join(state['blockers'])}", flush=True)

        elapsed_ms = (time.monotonic() - t0) * 1000
        remaining = interval_ms - int(elapsed_ms)
        if remaining > 0:
            time.sleep(remaining / 1000.0)


def main():
    parser = argparse.ArgumentParser(description="Resolve RIFT player coordinates from memory")
    parser.add_argument("--pid", type=int, required=True, help="RIFT process ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON (one-shot)")
    parser.add_argument("--watch", action="store_true", help="Continuous polling mode")
    parser.add_argument("--interval", type=int, default=200, help="Poll interval in ms (default: 200)")
    parser.add_argument("--output", type=str, default=None, help="Output path for --watch mode")
    parser.add_argument("--registry", action="store_true", help="Use registry-based approach (Assets repo)")
    args = parser.parse_args()

    if args.pid <= 0:
        err = {"ok": False, "blockers": ["Invalid PID: " + str(args.pid)]}
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print("BLOCKER: Invalid PID", file=sys.stderr)
        sys.exit(1)

    if args.watch:
        output = Path(args.output) if args.output else Path(".local") / "state" / "latest.json"
        try:
            watch_loop(args.pid, output, args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")
        sys.exit(0)

    # One-shot mode
    if args.registry:
        state = resolve_state_registry(args.pid)
    else:
        state = resolve_state(args.pid)

    if args.json:
        print(json.dumps(state, indent=2))
    else:
        if state["ok"]:
            p = state["position"]
            n = state["navigation"]
            heading = n.get("yawDeg", "?") if n else "?"
            method = state.get("method", "chain-based")
            print(f"[{method}] X={p['x']:.4f} Y={p['y']:.4f} Z={p['z']:.4f} heading={heading}°")
        else:
            for b in state["blockers"]:
                print("BLOCKER: " + b, file=sys.stderr)

    sys.exit(0 if state["ok"] else 1)


if __name__ == "__main__":
    main()
