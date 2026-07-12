#!/usr/bin/env python3
"""Verify camera-based facing by walking forward and comparing displacement."""
import ctypes, struct, time, math, subprocess, json

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

def read_float(addr):
    d = read_bytes(addr, 4)
    return struct.unpack('<f', d)[0] if d and len(d) == 4 else None

def read_floats(addr, count):
    d = read_bytes(addr, count * 4)
    if not d:
        return []
    return [struct.unpack('<f', d[i*4:i*4+4])[0] for i in range(count)]

def send_key(key, hold_ms=3000):
    exe = "tools/RiftReader.SendInput/bin/Release/net10.0-windows/RiftReader.SendInput.exe"
    subprocess.run(
        [exe, "--key", key, "--hold-ms", str(hold_ms), "--json"],
        capture_output=True, text=True, timeout=hold_ms // 1000 + 5
    )

obj = read_ptr(base + COORD_RVA)
child330 = read_ptr(obj + 0x330)

# Get camera-based facing
vals = read_floats(child330, 16)
cam_dir_x, cam_dir_z = vals[11], vals[13]
player_facing = math.degrees(math.atan2(-cam_dir_x, -cam_dir_z))

# Get position before walking
x1 = read_float(obj + 0x320)
z1 = read_float(obj + 0x328)

print(f"Camera-based facing: {player_facing:.1f} deg")
print(f"Position before walk: ({x1:.2f}, {z1:.2f})")

# Walk forward 3s
send_key("W", 3000)
time.sleep(2)

# Get position after walking
x2 = read_float(obj + 0x320)
z2 = read_float(obj + 0x328)

# Get camera-based facing after walking
vals2 = read_floats(child330, 16)
cam_dir_x2, cam_dir_z2 = vals2[11], vals2[13]
player_facing2 = math.degrees(math.atan2(-cam_dir_x2, -cam_dir_z2))

# Calculate displacement yaw
disp_yaw = math.degrees(math.atan2(x2 - x1, z2 - z1))

print(f"Position after walk: ({x2:.2f}, {z2:.2f})")
print(f"Displacement: dx={x2-x1:+.2f} dz={z2-z1:+.2f}")
print(f"Displacement yaw: {disp_yaw:.1f} deg")
print(f"Camera facing after: {player_facing2:.1f} deg")
print(f"Match: {abs(disp_yaw - player_facing2) < 30 or abs(disp_yaw - player_facing2 - 360) < 30 or abs(disp_yaw - player_facing2 + 360) < 30}")
