#!/usr/bin/env python3
"""Calibrate RIFT turn rate by measuring heading change for different hold durations."""
import ctypes, ctypes.wintypes, struct, math, subprocess, sys, time
from pathlib import Path

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0
SENDINPUT_DLL = str(Path(__file__).parent.parent / "tools" / "RiftReader.SendInput" / "bin" / "Release" / "net10.0-windows" / "RiftReader.SendInput.exe")


def find_base(pid):
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
    h = kernel32.OpenProcess(0x0010, False, pid)
    buf = ctypes.create_string_buffer(length)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, length, ctypes.byref(br))
    kernel32.CloseHandle(h)
    return buf.raw[:br.value] if ok else None


def read_ptr(pid, addr):
    d = read_bytes(pid, addr, 8)
    return struct.unpack('<Q', d)[0] if d and len(d) == 8 else None


def read_f32(pid, addr):
    d = read_bytes(pid, addr, 4)
    return struct.unpack('<f', d)[0] if d and len(d) == 4 else None


def get_heading(pid, base):
    obj = read_ptr(pid, base + COORD_RVA)
    if not obj or obj < 0x10000:
        return None
    child330 = read_ptr(pid, obj + 0x330)
    if not child330 or child330 < 0x10000:
        return None
    h = read_f32(pid, child330 + 0x158)
    return math.degrees(h) if h is not None else None


def send_key(key, hold_ms):
    subprocess.run([SENDINPUT_DLL, "--key", key, "--hold-ms", str(hold_ms), "--json"],
                   capture_output=True, text=True, timeout=5)


def normalize_angle(a):
    while a >= 180:
        a -= 360
    while a < -180:
        a += 360
    return a


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--direction", choices=["left", "right", "both"], default="both")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    base = find_base(args.pid)
    if not base:
        print("ERROR: cannot find base"); sys.exit(1)

    # Test different hold durations
    durations = [100, 200, 300, 400, 500, 600, 800, 1000]
    results = []

    for hold_ms in durations:
        if args.direction in ("right", "both"):
            h_before = get_heading(args.pid, base)
            time.sleep(0.2)
            send_key("D", hold_ms)
            time.sleep(0.5)
            h_after = get_heading(args.pid, base)
            if h_before is not None and h_after is not None:
                delta = normalize_angle(h_after - h_before)
                results.append({"hold_ms": hold_ms, "direction": "right", "before": h_before, "after": h_after, "delta": delta})
                if not args.json:
                    print(f"RIGHT {hold_ms}ms: {h_before:.1f} -> {h_after:.1f} (delta={delta:+.1f}°)")

            # Return to starting position
            send_key("A", hold_ms)
            time.sleep(0.5)

        if args.direction in ("left", "both"):
            h_before = get_heading(args.pid, base)
            time.sleep(0.2)
            send_key("A", hold_ms)
            time.sleep(0.5)
            h_after = get_heading(args.pid, base)
            if h_before is not None and h_after is not None:
                delta = normalize_angle(h_after - h_before)
                results.append({"hold_ms": hold_ms, "direction": "left", "before": h_before, "after": h_after, "delta": delta})
                if not args.json:
                    print(f"LEFT  {hold_ms}ms: {h_before:.1f} -> {h_after:.1f} (delta={delta:+.1f}°)")

            # Return
            send_key("D", hold_ms)
            time.sleep(0.5)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        # Compute turn rate (degrees per second)
        print("\nTurn rates:")
        for r in results:
            rate = abs(r["delta"]) / (r["hold_ms"] / 1000.0)
            print(f"  {r['direction']} {r['hold_ms']}ms: {abs(r['delta']):.1f}° in {r['hold_ms']/1000:.1f}s = {rate:.1f}°/s")


if __name__ == "__main__":
    import json
    main()
