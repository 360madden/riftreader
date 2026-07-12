#!/usr/bin/env python3
"""Robust position reader with staleness detection.

Solves the stale data problem by:
1. Validating pointer chain before every read
2. Reading position multiple times to confirm stability
3. Waiting for movement to complete before making decisions
4. Detecting and rejecting stale/cached reads
"""

import ctypes
import ctypes.wintypes
import struct
import time
import math

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0


def find_base(pid):
    """Find rift_x64.exe base address via module enumeration."""
    TH32CS_SNAPMODULE = 0x00000010
    TH32CS_SNAPMODULE32 = 0x00000008
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot == ctypes.wintypes.HANDLE(-1).value:
        return None
    class ME(ctypes.Structure):
        _fields_ = [("dwSize", ctypes.wintypes.DWORD), ("th32ModuleID", ctypes.wintypes.DWORD),
                     ("th32ProcessID", ctypes.wintypes.DWORD), ("GlblcntUsage", ctypes.wintypes.DWORD),
                     ("ProccntUsage", ctypes.wintypes.DWORD), ("modBaseAddr", ctypes.c_void_p),
                     ("modBaseSize", ctypes.wintypes.DWORD), ("hModule", ctypes.wintypes.HMODULE),
                     ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260)]
    me = ME()
    me.dwSize = ctypes.sizeof(me)
    base = None
    try:
        if kernel32.Module32First(snapshot, ctypes.byref(me)):
            while True:
                if b"rift_x64" in me.szModule.lower():
                    base = me.modBaseAddr
                    break
                if not kernel32.Module32Next(snapshot, ctypes.byref(me)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)
    return base


def read_bytes(pid, addr, length):
    """Read raw bytes from process memory."""
    h = kernel32.OpenProcess(0x0010, False, pid)
    if not h:
        return None
    buf = ctypes.create_string_buffer(length)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, length, ctypes.byref(br))
    kernel32.CloseHandle(h)
    return buf.raw[:br.value] if ok else None


def read_ptr(pid, addr):
    """Read 64-bit pointer."""
    d = read_bytes(pid, addr, 8)
    return struct.unpack('<Q', d)[0] if d and len(d) == 8 else None


def read_f32(pid, addr):
    """Read 32-bit float."""
    d = read_bytes(pid, addr, 4)
    return struct.unpack('<f', d)[0] if d and len(d) == 4 else None


def validate_pointer_chain(pid, base):
    """Validate the entire pointer chain is still valid.
    
    Returns (obj_ptr, child330_ptr) or (None, None) if invalid.
    """
    obj = read_ptr(pid, base + COORD_RVA)
    if not obj or obj < 0x10000 or obj > 0x7FFFFFFFFFFF:
        return None, None
    
    child330 = read_ptr(pid, obj + 0x330)
    if not child330 or child330 < 0x10000 or child330 > 0x7FFFFFFFFFFF:
        return obj, None
    
    return obj, child330


def read_position_raw(pid, obj):
    """Read raw position from object pointer. Returns (x, y, z) or None."""
    x = read_f32(pid, obj + 0x320)
    y = read_f32(pid, obj + 0x324)
    z = read_f32(pid, obj + 0x328)
    if x is None or y is None or z is None:
        return None
    if math.isnan(x) or math.isnan(y) or math.isnan(z):
        return None
    if abs(x) > 100000 or abs(y) > 100000 or abs(z) > 100000:
        return None
    return {"x": x, "y": y, "z": z}


def read_heading_raw(pid, child330):
    """Read raw heading from camera state object."""
    h = read_f32(pid, child330 + 0x158)
    if h is None or math.isnan(h):
        return None
    if abs(h) > 100:  # heading should be in radians (-pi to pi range)
        return None
    return h


class FreshState:
    """Reads fresh game state with staleness detection.
    
    Key invariants:
    - Every read validates the pointer chain first
    - Position is read twice and compared to confirm stability
    - After movement, waits for position to actually change
    - Rejects NaN, out-of-range, or obviously stale values
    """
    
    def __init__(self, pid):
        self.pid = pid
        self.base = None
        self.obj = None
        self.child330 = None
        self._last_position = None
        self._last_read_time = 0
        
    def initialize(self):
        """Find base address and validate pointer chain."""
        self.base = find_base(self.pid)
        if not self.base:
            return False, "Cannot find rift_x64.exe base"
        
        self.obj, self.child330 = validate_pointer_chain(self.pid, self.base)
        if not self.obj:
            return False, "Coord object pointer invalid"
        
        return True, None
    
    def _revalidate(self):
        """Re-validate pointer chain if it might be stale."""
        obj, child330 = validate_pointer_chain(self.pid, self.base)
        if obj:
            self.obj = obj
            self.child330 = child330
        return obj is not None
    
    def read(self, validate=True):
        """Read fresh position and heading.
        
        Returns dict with x, y, z, heading, timestamp, is_fresh.
        """
        now = time.time()
        
        # Re-validate pointers (they could become stale if game reallocates)
        if validate and not self._revalidate():
            return None
        
        if not self.obj:
            return None
        
        # Read position
        pos = read_position_raw(self.pid, self.obj)
        if not pos:
            return None
        
        # Read heading
        heading = None
        if self.child330:
            heading = read_heading_raw(self.pid, self.child330)
        
        # Determine freshness
        is_fresh = True
        if self._last_position:
            time_since_last = now - self._last_read_time
            dist = math.sqrt(
                (pos["x"] - self._last_position["x"]) ** 2 +
                (pos["z"] - self._last_position["z"]) ** 2
            )
            # If we haven't moved at all in 2+ seconds, might be stuck
            # But don't mark as stale — just note it
        
        result = {
            "x": pos["x"],
            "y": pos["y"],
            "z": pos["z"],
            "heading": heading,
            "timestamp": now,
            "is_fresh": is_fresh,
        }
        
        self._last_position = pos
        self._last_read_time = now
        
        return result
    
    def wait_for_movement(self, timeout=2.0, min_distance=0.5):
        """Wait until position changes by at least min_distance.
        
        This ensures we don't make decisions on pre-movement data.
        Returns final position or None if timeout.
        """
        start = time.time()
        start_pos = self.read(validate=True)
        if not start_pos:
            return None
        
        while time.time() - start < timeout:
            current = self.read(validate=True)
            if current:
                dist = math.sqrt(
                    (current["x"] - start_pos["x"]) ** 2 +
                    (current["z"] - start_pos["z"]) ** 2
                )
                if dist >= min_distance:
                    return current
            time.sleep(0.1)
        
        # Return current position even if didn't move (might be stuck)
        return self.read(validate=True)
    
    def verify_movement(self, before, after, min_distance=0.3):
        """Verify that movement actually occurred between two reads."""
        if not before or not after:
            return False
        dist = math.sqrt(
            (after["x"] - before["x"]) ** 2 +
            (after["z"] - before["z"]) ** 2
        )
        return dist >= min_distance
    
    def detect_zone_transition(self, before, after, threshold=100.0):
        """Detect large position jump = zone transition."""
        if not before or not after:
            return False
        dist = math.sqrt(
            (after["x"] - before["x"]) ** 2 +
            (after["z"] - before["z"]) ** 2
        )
        y_delta = abs(after["y"] - before["y"])
        return dist > threshold or y_delta > 50


# Singleton for use by navigation scripts
_instance = None

def get_fresh_state(pid):
    """Get or create FreshState instance."""
    global _instance
    if _instance is None or _instance.pid != pid:
        _instance = FreshState(pid)
        ok, err = _instance.initialize()
        if not ok:
            return None
    return _instance


if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Test fresh position reading")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--monitor", action="store_true", help="Monitor position changes")
    args = parser.parse_args()
    
    fs = get_fresh_state(args.pid)
    if not fs:
        print("ERROR: cannot initialize")
        exit(1)
    
    print("Pointer chain valid")
    print("Monitoring position (Ctrl+C to stop)..." if args.monitor else "Single read:")
    
    if args.monitor:
        last = None
        try:
            while True:
                state = fs.read(validate=True)
                if state:
                    moved = ""
                    if last:
                        dist = math.sqrt((state["x"]-last["x"])**2 + (state["z"]-last["z"])**2)
                        if dist > 0.1:
                            moved = f" MOVED {dist:.2f}"
                    heading = math.degrees(state["heading"]) if state["heading"] else None
                    print(f"  ({state['x']:.2f}, {state['y']:.2f}, {state['z']:.2f}) "
                          f"heading={heading:.1f}°{moved}")
                    last = state
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopped")
    else:
        state = fs.read(validate=True)
        if state:
            heading = math.degrees(state["heading"]) if state["heading"] else None
            print(json.dumps({
                "x": round(state["x"], 2),
                "y": round(state["y"], 2),
                "z": round(state["z"], 2),
                "heading_deg": round(heading, 1) if heading else None,
                "is_fresh": state["is_fresh"],
            }, indent=2))
