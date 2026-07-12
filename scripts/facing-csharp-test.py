#!/usr/bin/env python3
"""Proper facing test using C# SendInput for reliable key delivery."""
import ctypes, struct, time, math, subprocess, json

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0
base = 0x7FF728B80000
PID = 36332
SENDINPUT = "tools/RiftReader.SendInput/bin/Release/net10.0-windows/RiftReader.SendInput.exe"

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

def send_key(key, hold_ms=200):
    result = subprocess.run(
        ["dotnet", "run", "-c", "Release", "--", "--key", key, "--hold-ms", str(hold_ms), "--json"],
        capture_output=True, text=True, timeout=10,
        cwd="tools/RiftReader.SendInput"
    )
    if result.returncode != 0:
        print(f"  SendInput failed: {result.stderr[:200]}")
        return False
    try:
        data = json.loads(result.stdout)
        return data.get("ok", False)
    except:
        return False

obj = read_ptr(base + COORD_RVA)
print(f"Object: {hex(obj)}")

def heading():
    return read_float(obj + 0x300)

def coords():
    return read_float(obj + 0x320), read_float(obj + 0x324), read_float(obj + 0x328)

def displacement_yaw(x1, z1, x2, z2):
    dx, dz = x2 - x1, z2 - z1
    return math.degrees(math.atan2(dx, dz))

print("\n=== +0x300 heading test (C# SendInput) ===")
h0 = heading()
print(f"Initial: +0x300 = {h0:.2f} (mod360 = {h0 % 360:.1f} deg)")

# Turn RIGHT x3
print("\n--- 3x RIGHT ---")
for i in range(3):
    send_key("D", 200)
    time.sleep(0.3)
time.sleep(1.5)
h1 = heading()
print(f"Right 3x: {h0:.2f} -> {h1:.2f} (delta={h1-h0:+.2f}) mod360={h1%360:.1f}")

# Turn LEFT x6
print("\n--- 6x LEFT ---")
for i in range(6):
    send_key("A", 200)
    time.sleep(0.3)
time.sleep(1.5)
h2 = heading()
print(f"Left 6x:  {h1:.2f} -> {h2:.2f} (delta={h2-h1:+.2f}) mod360={h2%360:.1f}")

# Turn RIGHT x3 to return
print("\n--- 3x RIGHT ---")
for i in range(3):
    send_key("D", 200)
    time.sleep(0.3)
time.sleep(1.5)
h3 = heading()
print(f"Right 3x: {h2:.2f} -> {h3:.2f} (delta={h3-h2:+.2f}) mod360={h3%360:.1f}")

# Walk forward and compare heading vs displacement
print("\n=== Walk forward 3s ===")
x1, y1, z1 = coords()
h_before = heading()
send_key("W", 3000)
time.sleep(2)
x2, y2, z2 = coords()
h_after = heading()
disp = displacement_yaw(x1, z1, x2, z2)
print(f"X: {x1:.2f} -> {x2:.2f} (dx={x2-x1:+.2f})")
print(f"Z: {z1:.2f} -> {z2:.2f} (dz={z2-z1:+.2f})")
print(f"Displacement yaw: {disp:.1f} deg")
print(f"Heading mod360: {h_after % 360:.1f} deg")
print(f"Match: {abs((h_after%360) - disp) < 30 or abs((h_after%360) - disp - 360) < 30 or abs((h_after%360) - disp + 360) < 30}")
