#!/usr/bin/env python3
"""Test camera direction response to turns — does it track player facing?"""
import ctypes, struct, time, math, subprocess

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0
base = 0x7FF728B80000
PID = 36332

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

def send_key(key, hold_ms=200):
    exe = "tools/RiftReader.SendInput/bin/Release/net10.0-windows/RiftReader.SendInput.exe"
    subprocess.run(
        [exe, "--key", key, "--hold-ms", str(hold_ms), "--json"],
        capture_output=True, text=True, timeout=5
    )

obj = read_ptr(base + COORD_RVA)
child330 = read_ptr(obj + 0x330)

def get_camera_yaw():
    vals = read_floats(child330, 16)
    dx, dz = vals[11], vals[13]  # +0x2c, +0x34
    return math.degrees(math.atan2(dx, dz))

print("=== Camera direction turn test ===")
y0 = get_camera_yaw()
print(f"Initial: {y0:.1f} deg (mod360={y0%360:.1f})")

# Turn RIGHT x3
for _ in range(3):
    send_key("D", 200)
    time.sleep(0.3)
time.sleep(1)
y1 = get_camera_yaw()
print(f"After 3x RIGHT: {y1:.1f} (delta={y1-y0:+.1f})")

# Turn LEFT x6
for _ in range(6):
    send_key("A", 200)
    time.sleep(0.3)
time.sleep(1)
y2 = get_camera_yaw()
print(f"After 6x LEFT:  {y2:.1f} (delta={y2-y1:+.1f})")

# Turn RIGHT x3 to return
for _ in range(3):
    send_key("D", 200)
    time.sleep(0.3)
time.sleep(1)
y3 = get_camera_yaw()
print(f"After 3x RIGHT: {y3:.1f} (delta={y3-y2:+.1f})")

print(f"\nTotal: {y3-y0:+.1f} deg (expect ~0 if we returned)")
