#!/usr/bin/env python3
"""Verify +0x300 directionality: right increases, left decreases."""
import ctypes, struct, time, math

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

def read_float(addr):
    d = read_bytes(addr, 4)
    return struct.unpack('<f', d)[0] if d and len(d) == 4 else None

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

def send_key(vk, hold=0.2):
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 1 | (scan << 16))
    time.sleep(hold)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 1 | (scan << 16) | (1 << 30) | (1 << 31))

user32.SetForegroundWindow(hwnd)
time.sleep(0.5)

obj = read_ptr(base + COORD_RVA)

VK_D = 0x44  # D = right
VK_A = 0x41  # A = left
VK_W = 0x57  # W = forward

def heading():
    return read_float(obj + 0x300)

print("=== +0x300 directionality test ===")
h0 = heading()
print(f"Initial: +0x300 = {h0:.2f} (mod360 = {h0 % 360:.1f} deg)")

# Turn RIGHT x3
for i in range(3):
    send_key(VK_D)
    time.sleep(0.15)
time.sleep(1)
h1 = heading()
print(f"After 3x RIGHT: +0x300 = {h1:.2f} (mod360 = {h1 % 360:.1f}) delta = {h1 - h0:+.2f}")

# Turn LEFT x6
for i in range(6):
    send_key(VK_A)
    time.sleep(0.15)
time.sleep(1)
h2 = heading()
print(f"After 6x LEFT:  +0x300 = {h2:.2f} (mod360 = {h2 % 360:.1f}) delta = {h2 - h1:+.2f}")

# Turn RIGHT x3 to return
for i in range(3):
    send_key(VK_D)
    time.sleep(0.15)
time.sleep(1)
h3 = heading()
print(f"After 3x RIGHT: +0x300 = {h3:.2f} (mod360 = {h3 % 360:.1f}) delta = {h3 - h2:+.2f}")

# Walk forward and check displacement
print("\n=== Displacement test (walk forward 3s) ===")
x1 = read_float(obj + 0x320)
z1 = read_float(obj + 0x328)
h_before = heading()
send_key(VK_W, hold=3.0)  # hold W for 3 seconds
time.sleep(1)
x2 = read_float(obj + 0x320)
z2 = read_float(obj + 0x328)
h_after = heading()
disp_yaw = math.degrees(math.atan2(x2 - x1, z2 - z1))
print(f"Before: X={x1:.2f} Z={z1:.2f} heading={h_before:.2f} ({h_before % 360:.1f} deg)")
print(f"After:  X={x2:.2f} Z={z2:.2f} heading={h_after:.2f} ({h_after % 360:.1f} deg)")
print(f"Displacement: dx={x2-x1:+.2f} dz={z2-z1:+.2f}")
print(f"Displacement yaw: {disp_yaw:.1f} deg")
print(f"Heading mod360: {h_after % 360:.1f} deg")
print(f"Delta: {(h_after % 360) - disp_yaw:+.1f} deg")
