#!/usr/bin/env python3
"""Translate game world coordinates to screen coordinates for click-to-move."""
import ctypes
import ctypes.wintypes
import json
import math
import struct
import subprocess
import sys
import time
from pathlib import Path

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

COORD_GLOBAL_RVA = 0x32EBDC0
OFFSET_CAMERA_CHILD = 0x330
# Camera state offsets within child object
CAM_POS_X = 0x08   # Camera position X
CAM_POS_Y = 0x0C   # Camera position Y
CAM_POS_Z = 0x10   # Camera position Z
PLAYER_POS_X = 0x14  # Player position X
PLAYER_POS_Y = 0x18  # Player position Y
PLAYER_POS_Z = 0x1C  # Player position Z
CAM_DIR_X = 0x2C   # Camera direction X (normalized)
CAM_DIR_Y = 0x30   # Camera direction Y
CAM_DIR_Z = 0x34   # Camera direction Z
CAM_FOV = 0x38     # Field of view (degrees)
CAM_NEAR = 0x3C    # Near clip plane
CAM_FAR = 0x40     # Far clip plane


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


def get_camera_state(pid):
    """Read camera state from game memory."""
    base = find_base(pid)
    if not base:
        return None

    obj = read_ptr(pid, base + COORD_GLOBAL_RVA)
    if not obj or obj < 0x10000:
        return None

    child = read_ptr(pid, obj + OFFSET_CAMERA_CHILD)
    if not child or child < 0x10000:
        return None

    vals = read_f32s(pid, child, 20)
    if len(vals) < 14:
        return None

    return {
        "cam_x": vals[CAM_POS_X // 4],
        "cam_y": vals[CAM_POS_Y // 4],
        "cam_z": vals[CAM_POS_Z // 4],
        "player_x": vals[PLAYER_POS_X // 4],
        "player_y": vals[PLAYER_POS_Y // 4],
        "player_z": vals[PLAYER_POS_Z // 4],
        "dir_x": vals[CAM_DIR_X // 4],
        "dir_y": vals[CAM_DIR_Y // 4],
        "dir_z": vals[CAM_DIR_Z // 4],
        "fov": vals[CAM_FOV // 4],
        "near": vals[CAM_NEAR // 4],
        "far": vals[CAM_FAR // 4],
    }


def world_to_screen(wx, wy, wz, cam, screen_w, screen_h):
    """Project world coordinates to screen coordinates using camera state."""
    # Camera basis vectors
    # Forward: from camera toward player (already normalized)
    fx, fy, fz = cam["dir_x"], cam["dir_y"], cam["dir_z"]

    # World up
    up_x, up_y, up_z = 0.0, 1.0, 0.0

    # Right = forward x up
    rx = fy * up_z - fz * up_y
    ry = fz * up_x - fx * up_z
    rz = fx * up_y - fy * up_x
    rl = math.sqrt(rx*rx + ry*ry + rz*rz)
    if rl > 0.001:
        rx, ry, rz = rx/rl, ry/rl, rz/rl
    else:
        rx, ry, rz = 1.0, 0.0, 0.0

    # True up = right x forward
    ux = ry * fz - rz * fy
    uy = rz * fx - rx * fz
    uz = rx * fy - ry * fx

    # Vector from camera to target point
    dx = wx - cam["cam_x"]
    dy = wy - cam["cam_y"]
    dz = wz - cam["cam_z"]

    # Transform to camera space
    cx = rx * dx + ry * dy + rz * dz  # right
    cy = ux * dx + uy * dy + uz * dz  # up
    cz = fx * dx + fy * dy + fz * dz  # forward (depth)

    # Avoid division by zero
    if cz < 0.1:
        return None, None  # Behind camera

    # Projection
    fov_rad = math.radians(cam["fov"])
    aspect = screen_w / screen_h
    focal_length = 1.0 / math.tan(fov_rad / 2.0)

    # NDC
    ndc_x = (cx / cz) * focal_length / aspect
    ndc_y = (cy / cz) * focal_length

    # Screen coordinates (Y is flipped)
    sx = (ndc_x + 1.0) * screen_w / 2.0
    sy = (1.0 - ndc_y) * screen_h / 2.0

    return sx, sy


def click_at(sx, sy, hwnd=None):
    """Send mouse click at screen coordinates."""
    if hwnd:
        # Convert to client coordinates
        point = ctypes.wintypes.POINT(int(sx), int(sy))
        user32.ScreenToClient(hwnd, ctypes.byref(point))
        lparam = point.y << 16 | (point.x & 0xFFFF)
    else:
        lparam = int(sy) << 16 | (int(sx) & 0xFFFF)

    # Left click
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202

    if hwnd:
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 0x0001, lparam)
        time.sleep(0.05)
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0x0000, lparam)
    else:
        user32.SetCursorPos(int(sx), int(sy))
        time.sleep(0.05)
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP


def get_window_size(hwnd):
    """Get RIFT window dimensions."""
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    return rect.right - rect.left, rect.bottom - rect.top


def find_rift_hwnd(pid):
    """Find RIFT window handle."""
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
    return hwnds[0] if hwnds else None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Project world coordinates to screen for click-to-move")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--target-x", type=float, required=True, help="Target world X")
    parser.add_argument("--target-z", type=float, required=True, help="Target world Z")
    parser.add_argument("--click", action="store_true", help="Actually send the click")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    cam = get_camera_state(args.pid)
    if not cam:
        print("ERROR: Cannot read camera state")
        sys.exit(1)

    hwnd = find_rift_hwnd(args.pid)
    if not hwnd:
        print("ERROR: Cannot find RIFT window")
        sys.exit(1)

    w, h = get_window_size(hwnd)

    # Project target point (use player Y as ground level)
    sx, sy = world_to_screen(args.target_x, cam["player_y"], args.target_z, cam, w, h)

    if sx is None:
        print("ERROR: Target is behind camera")
        sys.exit(1)

    # Clamp to window
    sx = max(0, min(w - 1, sx))
    sy = max(0, min(h - 1, sy))

    if args.json:
        print(json.dumps({
            "screen_x": round(sx, 1),
            "screen_y": round(sy, 1),
            "window_w": w,
            "window_h": h,
            "camera": cam,
            "clicked": args.click,
        }))
    else:
        print(f"Target ({args.target_x:.1f}, {args.target_z:.1f}) -> Screen ({sx:.0f}, {sy:.0f})")
        print(f"Window: {w}x{h}")
        print(f"Camera: pos=({cam['cam_x']:.1f}, {cam['cam_y']:.1f}, {cam['cam_z']:.1f}) fov={cam['fov']}°")

    if args.click:
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        click_at(sx, sy, hwnd)
        print("Clicked!")


if __name__ == "__main__":
    main()
