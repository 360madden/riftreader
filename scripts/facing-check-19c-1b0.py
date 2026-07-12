#!/usr/bin/env python3
"""Check +0x19c as previous position, +0x1b0 as current, compute distance."""
import ctypes, ctypes.wintypes, struct, math, subprocess, time

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

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

def send_key(key, hold_ms=200):
    exe = "tools/RiftReader.SendInput/bin/Release/net10.0-windows/RiftReader.SendInput.exe"
    subprocess.run([exe, "--key", key, "--hold-ms", str(hold_ms), "--json"],
                   capture_output=True, text=True, timeout=5)

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--pid", type=int, required=True)
args = parser.parse_args()
pid = args.pid

base = find_base(pid)
obj = read_ptr(pid, base + 0x32EBDC0)
obj180 = read_ptr(pid, obj + 0x180)

# Find RIFT HWND and focus
hwnds = []
def cb(hwnd, lp):
    pid_buf = ctypes.c_uint32(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_buf))
    if pid_buf.value == pid:
        t = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, t, 256)
        if t.value == "RIFT":
            hwnds.append(hwnd)
    return True
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
user32.EnumWindows(WNDENUMPROC(cb), 0)
hwnd = hwnds[0]
user32.SetForegroundWindow(hwnd)
time.sleep(0.3)

def get_coords():
    """Get both coordinate sets and counter."""
    # First set (+0x19c)
    x1 = read_f32(pid, obj180 + 0x19c)
    y1 = read_f32(pid, obj180 + 0x1a0)
    z1 = read_f32(pid, obj180 + 0x1a4)
    # Second set (+0x1b0)
    x2 = read_f32(pid, obj180 + 0x1b0)
    y2 = read_f32(pid, obj180 + 0x1b4)
    z2 = read_f32(pid, obj180 + 0x1b8)
    # Counter
    c = read_f32(pid, obj180 + 0x190)
    return (x1, y1, z1), (x2, y2, z2), c

print("=== +0x19c/+0x1b0 coordinate relationship ===")
coord1, coord2, counter = get_coords()
print(f"Set 1 (+0x19c): ({coord1[0]:.2f}, {coord1[1]:.2f}, {coord1[2]:.2f})")
print(f"Set 2 (+0x1b0): ({coord2[0]:.2f}, {coord2[1]:.2f}, {coord2[2]:.2f})")
print(f"Counter: {counter:.2f}")

# Move forward and track
print("\n=== Move forward — track both sets ===")
send_key("W", 500)
time.sleep(0.5)

coord1a, coord2a, counter_a = get_coords()
print(f"After move:")
print(f"  Set 1: ({coord1a[0]:.2f}, {coord1a[1]:.2f}, {coord1a[2]:.2f})")
print(f"  Set 2: ({coord2a[0]:.2f}, {coord2a[1]:.2f}, {coord2a[2]:.2f})")
print(f"  Counter: {counter_a:.2f}")
print(f"  Set 1 delta: ({coord1a[0]-coord1[0]:+.2f}, {coord1a[1]-coord1[1]:+.2f}, {coord1a[2]-coord1[2]:+.2f})")
print(f"  Set 2 delta: ({coord2a[0]-coord2[0]:+.2f}, {coord2a[1]-coord2[1]:+.2f}, {coord2a[2]-coord2[2]:+.2f})")

# Distance between sets
d1 = math.sqrt(sum((a-b)**2 for a, b in zip(coord1a, coord2a)))
print(f"  Distance between sets: {d1:.2f}")

# Move again
send_key("W", 500)
time.sleep(0.5)

coord1b, coord2b, counter_b = get_coords()
print(f"\nAfter second move:")
print(f"  Set 1: ({coord1b[0]:.2f}, {coord1b[1]:.2f}, {coord1b[2]:.2f})")
print(f"  Set 2: ({coord2b[0]:.2f}, {coord2b[1]:.2f}, {coord2b[2]:.2f})")
print(f"  Counter: {counter_b:.2f}")
print(f"  Set 1 delta from move1: ({coord1b[0]-coord1a[0]:+.2f}, {coord1b[1]-coord1a[1]:+.2f}, {coord1b[2]-coord1a[2]:+.2f})")
print(f"  Set 2 delta from move1: ({coord2b[0]-coord2a[0]:+.2f}, {coord2b[1]-coord2a[1]:+.2f}, {coord2b[2]-coord2a[2]:+.2f})")

# Check if Set 1 follows Set 2 with delay
print(f"\n=== Lag check ===")
print(f"Set 2 moved: {math.sqrt(sum((a-b)**2 for a, b in zip(coord2, coord2a))):.2f}")
print(f"Set 1 caught up: {math.sqrt(sum((a-b)**2 for a, b in zip(coord1, coord1a))):.2f}")
print(f"Set 2 second move: {math.sqrt(sum((a-b)**2 for a, b in zip(coord2a, coord2b))):.2f}")
print(f"Set 1 second move: {math.sqrt(sum((a-b)**2 for a, b in zip(coord1a, coord1b))):.2f}")
