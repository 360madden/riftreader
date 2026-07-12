#!/usr/bin/env python3
"""Check +0x318 child and angular velocity fields."""
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

def read_f32s(pid, addr, count):
    d = read_bytes(pid, addr, count * 4)
    if not d:
        return []
    return [struct.unpack('<f', d[i*4:i*4+4])[0] for i in range(count)]

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
obj318 = read_ptr(pid, obj + 0x318)
obj330 = read_ptr(pid, obj + 0x330)
print(f"Object: {hex(obj)}")
print(f"+0x318: {hex(obj318)}")
print(f"+0x330: {hex(obj330)}")

# Deep scan +0x318
print("\n=== +0x318 child (512 bytes) ===")
vals318 = read_f32s(pid, obj318, 128)
for i, v in enumerate(vals318):
    off = i * 4
    if v == 0.0 or v != v:
        continue
    tags = []
    if 5000 < abs(v) < 10000:
        tags.append("COORD")
    if 0 < v < 360 and v != int(v):
        tags.append("ANGLE")
    if 0.85 < abs(v) < 1.15 and i + 2 < len(vals318):
        v2 = vals318[i+1]
        v3 = vals318[i+2]
        if v2 != 0 and v3 != 0:
            mag = (v**2 + v2**2 + v3**2) ** 0.5
            if 0.95 < mag < 1.05:
                tags.append(f"UNIT yaw={math.degrees(math.atan2(v, v3)):.1f}")
    # Check for quaternion
    if i + 3 < len(vals318):
        w, x, y, z = v, vals318[i+1], vals318[i+2], vals318[i+3]
        if w != 0 or x != 0 or y != 0 or z != 0:
            mag = math.sqrt(w*w + x*x + y*y + z*z)
            if 0.95 < mag < 1.05:
                yaw = math.degrees(math.atan2(2*(w*y + x*z), 1 - 2*(y*y + x*x)))
                tags.append(f"QUAT yaw={yaw:.1f}")
    tag = " ".join(tags) if tags else ""
    print(f"  +{hex(off):>4}: {v:>14.6f}  {tag}")

# Check +0x330 child for rotation
print("\n=== +0x330 child — checking for rotation data ===")
vals330 = read_f32s(pid, obj330, 128)
# Look at +0x80 and +0x84 (we saw -0.45 and 1.82 earlier)
print("Key fields:")
for off, label in [(0x80, "+0x80"), (0x84, "+0x84"), (0x88, "+0x88"), 
                    (0x148, "+0x148"), (0x158, "+0x158"), (0x180, "+0x180")]:
    idx = off // 4
    if idx < len(vals330):
        print(f"  {label}: {vals330[idx]:.6f}")

# Check +0x08 and +0x0c on main object (angular velocity?)
print("\n=== Main object angular fields ===")
for off in [0x08, 0x0c]:
    v = read_f32(pid, obj + off)
    print(f"  +{hex(off)}: {v:.6f}")

# Turn and check which fields change
print("\n=== Turn test — checking +0x318 and +0x330 for changes ===")

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

# Snapshot
snap1_318 = read_f32s(pid, obj318, 128)
snap1_330 = read_f32s(pid, obj330, 128)

# Turn right
for _ in range(3):
    send_key("D", 200)
    time.sleep(0.3)
time.sleep(1)

# Snapshot
snap2_318 = read_f32s(pid, obj318, 128)
snap2_330 = read_f32s(pid, obj330, 128)

# Diff
print("\n+0x318 changes:")
for i in range(min(len(snap1_318), len(snap2_318))):
    d = snap2_318[i] - snap1_318[i]
    if abs(d) > 0.001:
        print(f"  +{hex(i*4)}: {snap1_318[i]:.4f} -> {snap2_318[i]:.4f} (d={d:+.4f})")

print("\n+0x330 changes:")
for i in range(min(len(snap1_330), len(snap2_330))):
    d = snap2_330[i] - snap1_330[i]
    if abs(d) > 0.001:
        print(f"  +{hex(i*4)}: {snap1_330[i]:.4f} -> {snap2_330[i]:.4f} (d={d:+.4f})")
