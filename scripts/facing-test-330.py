#!/usr/bin/env python3
"""Test if +0x330 child's direction vector changes with turning."""
import ctypes, struct, time

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
COORD_RVA = 0x32EBDC0
base = 0x7FF728B80000
PID = 36332
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

def read_bytes(addr, length):
    h = kernel32.OpenProcess(0x0010, False, PID)
    buf = ctypes.create_string_buffer(length)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, length, ctypes.byref(br))
    kernel32.CloseHandle(h)
    return buf.raw[:br.value] if ok else None

def read_ptr(addr):
    d = read_bytes(addr, 8)
    return struct.unpack('<Q', d)[0] if d and len(d) == 8 else None

def read_floats(addr, count):
    d = read_bytes(addr, count * 4)
    if not d:
        return []
    return [struct.unpack('<f', d[i*4:i*4+4])[0] for i in range(count)]

import math

def vec_yaw(x, z):
    return math.degrees(math.atan2(x, z))

# Find RIFT HWND
hwnds = []
def callback(hwnd, lparam):
    pid_buf = ctypes.c_uint32(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_buf))
    if pid_buf.value == PID:
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        if title.value == 'RIFT':
            hwnds.append(hwnd)
    return True
user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))(callback), 0)
hwnd = hwnds[0]

def send_key(vk, hold=0.15):
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 1 | (scan << 16))
    time.sleep(hold)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 1 | (scan << 16) | (1 << 30) | (1 << 31))

obj = read_ptr(base + COORD_RVA)
child330 = read_ptr(obj + 0x330)
print(f"Coord object: {hex(obj)}")
print(f"+0x330 child: {hex(child330)}")

VK_D = 0x44  # D = right
VK_A = 0x41  # A = left
VK_W = 0x57  # W = forward

def snap(label):
    vals = read_floats(child330, 16)
    if not vals or len(vals) < 14:
        print(f"  {label}: READ FAILED")
        return None
    fx, fy, fz = vals[2], vals[3], vals[4]  # +0x08..+0x10
    cx, cy, cz = vals[5], vals[6], vals[7]  # +0x14..+0x1c
    dx, dy, dz = vals[11], vals[12], vals[13]  # +0x2c..+0x34
    mag = math.sqrt(dx*dx + dy*dy + dz*dz)
    yaw = vec_yaw(dx, dz)
    pitch = math.degrees(math.atan2(dy, math.sqrt(dx*dx + dz*dz)))
    print(f"  {label}: dir=({dx:.4f}, {dy:.4f}, {dz:.4f}) yaw={yaw:.1f} pitch={pitch:.1f} mag={mag:.4f}")
    print(f"          from=({fx:.1f}, {fy:.1f}, {fz:.1f}) cur=({cx:.1f}, {cy:.1f}, {cz:.1f})")
    return {"dx": dx, "dy": dy, "dz": dz, "yaw": yaw, "pitch": pitch}

user32.SetForegroundWindow(hwnd)
time.sleep(0.5)

print("\n=== Initial ===")
s1 = snap("initial")

print("\n=== Turn RIGHT (D x5) ===")
for _ in range(5):
    send_key(VK_D, 0.2)
    time.sleep(0.15)
time.sleep(1)
s2 = snap("after-right")

print("\n=== Turn LEFT (A x10) ===")
for _ in range(10):
    send_key(VK_A, 0.2)
    time.sleep(0.15)
time.sleep(1)
s3 = snap("after-left")

print("\n=== Summary ===")
if s1 and s2 and s3:
    print(f"Initial yaw:     {s1['yaw']:.1f}")
    print(f"After right:     {s2['yaw']:.1f} (delta={s2['yaw']-s1['yaw']:+.1f})")
    print(f"After left x2:   {s3['yaw']:.1f} (delta={s3['yaw']-s2['yaw']:+.1f})")
    print(f"Total delta:     {s3['yaw']-s1['yaw']:+.1f}")
