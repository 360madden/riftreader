#!/usr/bin/env python3
"""Test +0x180 +0x190 as frame counter or distance counter."""
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

print("=== +0x180 +0x190 counter test ===")
v0 = read_f32(pid, obj180 + 0x190)
print(f"Initial: {v0:.2f}")

# Wait 1 second (no movement)
time.sleep(1)
v1 = read_f32(pid, obj180 + 0x190)
print(f"After 1s idle: {v1:.2f} (delta={v1-v0:+.2f})")

# Move forward
send_key("W", 500)
time.sleep(0.5)
v2 = read_f32(pid, obj180 + 0x190)
print(f"After move: {v2:.2f} (delta={v2-v1:+.2f})")

# Turn right (no movement)
send_key("D", 300)
time.sleep(0.5)
v3 = read_f32(pid, obj180 + 0x190)
print(f"After turn: {v3:.2f} (delta={v3-v2:+.2f})")

# Move forward again
send_key("W", 500)
time.sleep(0.5)
v4 = read_f32(pid, obj180 + 0x190)
print(f"After move: {v4:.2f} (delta={v4-v3:+.2f})")

print(f"\nIdle delta: {v1-v0:+.2f}")
print(f"Move deltas: {v2-v1:+.2f}, {v4-v3:+.2f}")
print(f"Turn delta: {v3-v2:+.2f}")

# Check if it's frame-based (should increase steadily)
print("\n=== Steady increase test ===")
for i in range(5):
    time.sleep(0.5)
    v = read_f32(pid, obj180 + 0x190)
    print(f"  {i*0.5:.1f}s: {v:.2f}")
