#!/usr/bin/env python3
"""Investigate +0x180 object and scan for velocity/movement state."""
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

def read_i32(pid, addr):
    d = read_bytes(pid, addr, 4)
    return struct.unpack('<i', d)[0] if d and len(d) == 4 else None

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
obj90 = read_ptr(pid, obj + 0x90)
obj180 = read_ptr(pid, obj + 0x180)

print(f"Object: {hex(obj)}")
print(f"+0x90: {hex(obj90)}")
print(f"+0x180: {hex(obj180)}")

# Read +0x180 object structure
print("\n=== +0x180 object deep analysis ===")
vals = read_f32s(pid, obj180, 128)

# Print all non-zero values with context
print("Non-zero fields:")
for i, v in enumerate(vals):
    off = i * 4
    if v == 0.0:
        continue
    tags = []
    if 5000 < abs(v) < 10000:
        tags.append(f"coord={v:.2f}")
    if v == int(v) and abs(v) < 1000:
        tags.append(f"int={int(v)}")
    # Check if it's a pointer (high 32 bits = 0, low 32 bits = reasonable)
    as_u32 = struct.unpack('<I', struct.pack('<f', v))[0]
    if 0x10000 < as_u32 < 0x100000000:
        tags.append(f"u32={hex(as_u32)}")
    tag = " ".join(tags) if tags else ""
    print(f"  +{hex(off):>4}: {v:>14.6f}  {tag}")

# Check the shared camera state pointers
print("\n=== Shared camera state pointers ===")
cam1_ptr = read_ptr(pid, obj180 + 0x1c0)
cam2_ptr = read_ptr(pid, obj180 + 0x1c8)
print(f"+0x1c0: {hex(cam1_ptr)}")
print(f"+0x1c8: {hex(cam2_ptr)}")

# Read the camera state from +0x180's perspective
cam1_vals = read_f32s(pid, cam1_ptr, 32)
cam2_vals = read_f32s(pid, cam2_ptr, 32)
print(f"Camera 1 (+0x1c0) values:")
for i, v in enumerate(cam1_vals[:16]):
    if v != 0:
        print(f"  +{hex(i*4)}: {v:.6f}")
print(f"Camera 2 (+0x1c8) values:")
for i, v in enumerate(cam2_vals[:16]):
    if v != 0:
        print(f"  +{hex(i*4)}: {v:.6f}")

# Check if +0x180 object has velocity by comparing coordinates
print("\n=== Velocity check ===")
# Get current position
cur_x = read_f32(pid, obj + 0x320)
cur_y = read_f32(pid, obj + 0x324)
cur_z = read_f32(pid, obj + 0x328)
# Get +0x180 coordinates
obj180_x = read_f32(pid, obj180 + 0x19c)
obj180_y = read_f32(pid, obj180 + 0x1b0)
obj180_z = read_f32(pid, obj180 + 0x1c0)
print(f"Current position: ({cur_x:.2f}, {cur_y:.2f}, {cur_z:.2f})")
print(f"+0x180 coords: ({obj180_x:.2f}, {obj180_y:.2f}, {obj180_z:.2f})")

# Check for velocity fields (floats that change during movement)
print("\n=== Movement test — checking velocity fields ===")
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

# Snapshot before movement
snap1_obj = read_f32s(pid, obj, 128)
snap1_180 = read_f32s(pid, obj180, 128)
snap1_cam1 = read_f32s(pid, cam1_ptr, 32)

# Move forward
send_key("W", 500)
time.sleep(1)

# Snapshot after movement
snap2_obj = read_f32s(pid, obj, 128)
snap2_180 = read_f32s(pid, obj180, 128)
snap2_cam1 = read_f32s(pid, cam1_ptr, 32)

print("\nMain object changes:")
for i in range(min(len(snap1_obj), len(snap2_obj))):
    d = snap2_obj[i] - snap1_obj[i]
    if abs(d) > 0.001:
        print(f"  +{hex(i*4)}: {snap1_obj[i]:.4f} -> {snap2_obj[i]:.4f} (d={d:+.4f})")

print("\n+0x180 changes:")
for i in range(min(len(snap1_180), len(snap2_180))):
    d = snap2_180[i] - snap1_180[i]
    if abs(d) > 0.001:
        print(f"  +{hex(i*4)}: {snap1_180[i]:.4f} -> {snap2_180[i]:.4f} (d={d:+.4f})")

print("\nCamera 1 changes:")
for i in range(min(len(snap1_cam1), len(snap2_cam1))):
    d = snap2_cam1[i] - snap1_cam1[i]
    if abs(d) > 0.001:
        print(f"  +{hex(i*4)}: {snap1_cam1[i]:.4f} -> {snap2_cam1[i]:.4f} (d={d:+.4f})")
