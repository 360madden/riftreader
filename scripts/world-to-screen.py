#!/usr/bin/env python3
"""Translate game world coordinates to screen coordinates for click-to-move.

Post-2026-07 reseed (restart-proven session seed, not current-truth promoted):
  root RVA 0x32E07C0 → owner → +0x320 XYZ, +0x330 camera child

Camera child layout (validated PID 21436 restart survival):
  +0x08/+0x0C/+0x10 cam pos
  +0x14/+0x18/+0x1C look-at / player-on-camera point
  +0x38 FOV degrees, +0x3C near

Look direction: derive normalize(playerOnCam - camPos). The floats at +0x2C are
unit-length but are NOT a usable camera forward on this patch (mostly world-up).
"""
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

# Restart-survived candidate root (2026-07-18). Not current-truth promoted.
COORD_GLOBAL_RVA = 0x32E07C0
OFFSET_CAMERA_CHILD = 0x330
# Camera state offsets within child object
CAM_POS_X = 0x08   # Camera position X
CAM_POS_Y = 0x0C   # Camera position Y
CAM_POS_Z = 0x10   # Camera position Z
PLAYER_POS_X = 0x14  # Look-at / player-on-camera X
PLAYER_POS_Y = 0x18  # Look-at Y
PLAYER_POS_Z = 0x1C  # Look-at Z
# +0x2C triple is unit-length but NOT camera forward on current patch — ignored.
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
    if len(vals) < 15:
        return None

    cam_x = vals[CAM_POS_X // 4]
    cam_y = vals[CAM_POS_Y // 4]
    cam_z = vals[CAM_POS_Z // 4]
    player_x = vals[PLAYER_POS_X // 4]
    player_y = vals[PLAYER_POS_Y // 4]
    player_z = vals[PLAYER_POS_Z // 4]
    # Derive look direction from camera → look-at (third-person style).
    dx = player_x - cam_x
    dy = player_y - cam_y
    dz = player_z - cam_z
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-6:
        return None
    fov = vals[CAM_FOV // 4]
    if not (1.0 < fov < 170.0):
        fov = 75.0

    return {
        "cam_x": cam_x,
        "cam_y": cam_y,
        "cam_z": cam_z,
        "player_x": player_x,
        "player_y": player_y,
        "player_z": player_z,
        "dir_x": dx / length,
        "dir_y": dy / length,
        "dir_z": dz / length,
        "dir_source": "cam_to_player_lookat",
        "fov": fov,
        "near": vals[CAM_NEAR // 4],
        "far": vals[CAM_FAR // 4] if len(vals) > (CAM_FAR // 4) else 2400.0,
        "root_rva": COORD_GLOBAL_RVA,
        "camera_child": child,
        "owner": obj,
    }


def camera_basis(cam):
    """Return (forward, right, up) unit vectors for the camera."""
    fx, fy, fz = cam["dir_x"], cam["dir_y"], cam["dir_z"]
    fl = math.sqrt(fx * fx + fy * fy + fz * fz)
    if fl < 1e-9:
        return None
    fx, fy, fz = fx / fl, fy / fl, fz / fl

    # Right = forward × world-up
    rx = fy * 0.0 - fz * 1.0
    ry = fz * 0.0 - fx * 0.0
    rz = fx * 1.0 - fy * 0.0
    rl = math.sqrt(rx * rx + ry * ry + rz * rz)
    if rl < 1e-6:
        # Look nearly parallel to world-up; use world-Z as up hint
        rx = fy * 1.0 - fz * 0.0
        ry = fz * 0.0 - fx * 1.0
        rz = fx * 0.0 - fy * 0.0
        rl = math.sqrt(rx * rx + ry * ry + rz * rz)
    if rl < 1e-9:
        return None
    rx, ry, rz = rx / rl, ry / rl, rz / rl

    # True up = right × forward
    ux = ry * fz - rz * fy
    uy = rz * fx - rx * fz
    uz = rx * fy - ry * fx
    return (fx, fy, fz), (rx, ry, rz), (ux, uy, uz)


def world_to_screen(wx, wy, wz, cam, screen_w, screen_h):
    """Project world coordinates to screen coordinates using camera state."""
    basis = camera_basis(cam)
    if basis is None:
        return None, None
    (fx, fy, fz), (rx, ry, rz), (ux, uy, uz) = basis

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


def screen_to_world_ground(sx, sy, cam, screen_w, screen_h, ground_y=None):
    """Unproject a client pixel to a world point on a horizontal ground plane.

    Uses Y = ground_y (default: camera look-at Y / player-on-cam Y). Approximate
    C2M target math — not engine raycast truth.
    """
    basis = camera_basis(cam)
    if basis is None:
        return None
    (fx, fy, fz), (rx, ry, rz), (ux, uy, uz) = basis
    if ground_y is None:
        ground_y = cam.get("player_y")
    if ground_y is None:
        return None

    fov_rad = math.radians(cam["fov"])
    aspect = screen_w / float(screen_h)
    focal_length = 1.0 / math.tan(fov_rad / 2.0)

    ndc_x = (sx / screen_w) * 2.0 - 1.0
    ndc_y = 1.0 - (sy / screen_h) * 2.0
    # Ray direction in camera space (z=forward)
    dir_cx = (ndc_x * aspect) / focal_length
    dir_cy = ndc_y / focal_length
    dir_cz = 1.0
    # To world
    dx = rx * dir_cx + ux * dir_cy + fx * dir_cz
    dy = ry * dir_cx + uy * dir_cy + fy * dir_cz
    dz = rz * dir_cx + uz * dir_cy + fz * dir_cz
    # Intersect cam + t*dir with plane y = ground_y
    if abs(dy) < 1e-9:
        return None
    t = (ground_y - cam["cam_y"]) / dy
    if t < 0.05:
        return None  # behind / invalid
    return {
        "x": cam["cam_x"] + t * dx,
        "y": ground_y,
        "z": cam["cam_z"] + t * dz,
        "t": t,
        "groundY": ground_y,
        "method": "cam-ray-horizontal-ground-plane",
    }


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


def read_heading_rad(pid, owner=None, camera_child=None):
    """Read provisional heading from [[owner+0x330]+0x158] (pre-patch path; revalidated)."""
    if owner is None or camera_child is None:
        cam = get_camera_state(pid)
        if not cam:
            return None
        owner = cam.get("owner")
        camera_child = cam.get("camera_child")
    if not camera_child:
        return None
    d = read_bytes(pid, int(camera_child) + 0x158, 4)
    if not d or len(d) < 4:
        return None
    return struct.unpack("<f", d)[0]


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="World↔screen projection using reseeded static camera chain (candidate)"
    )
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--target-x", type=float, default=None, help="Target world X (W2S mode)")
    parser.add_argument("--target-y", type=float, default=None, help="Target world Y (default: look-at Y)")
    parser.add_argument("--target-z", type=float, default=None, help="Target world Z (W2S mode)")
    parser.add_argument("--screen-x", type=float, default=None, help="Client X (S2W mode)")
    parser.add_argument("--screen-y", type=float, default=None, help="Client Y (S2W mode)")
    parser.add_argument("--ground-y", type=float, default=None, help="Ground plane Y for S2W")
    parser.add_argument("--round-trip", action="store_true", help="Self-check W2S↔S2W on look-at/body")
    parser.add_argument(
        "--click",
        action="store_true",
        help="Send click (legacy PostMessage path — prefer SendInput harness; gated)",
    )
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
    heading = read_heading_rad(args.pid, cam.get("owner"), cam.get("camera_child"))

    # --- S2W mode ---
    if args.screen_x is not None or args.screen_y is not None:
        if args.screen_x is None or args.screen_y is None:
            print("ERROR: S2W requires both --screen-x and --screen-y")
            sys.exit(1)
        hit = screen_to_world_ground(args.screen_x, args.screen_y, cam, w, h, args.ground_y)
        if not hit:
            print("ERROR: S2W ray did not hit ground plane")
            sys.exit(1)
        if args.json:
            print(json.dumps({
                "mode": "screen-to-world",
                "screen": [args.screen_x, args.screen_y],
                "world": hit,
                "window": [w, h],
                "camera": cam,
                "headingRad": heading,
                "clicked": False,
            }, default=str))
        else:
            print(
                f"Screen ({args.screen_x:.0f},{args.screen_y:.0f}) -> "
                f"World ({hit['x']:.2f}, {hit['y']:.2f}, {hit['z']:.2f}) t={hit['t']:.2f}"
            )
        return

    # --- Round-trip self-check (no click) ---
    if args.round_trip:
        body_x = read_f32(args.pid, cam["owner"] + 0x320) if cam.get("owner") else None
        body_y = read_f32(args.pid, cam["owner"] + 0x324) if cam.get("owner") else None
        body_z = read_f32(args.pid, cam["owner"] + 0x328) if cam.get("owner") else None
        look = (cam["player_x"], cam["player_y"], cam["player_z"])
        body = (body_x, body_y, body_z) if None not in (body_x, body_y, body_z) else None

        def rt(label, pt, ground_y=None):
            sx, sy = world_to_screen(pt[0], pt[1], pt[2], cam, w, h)
            if sx is None:
                return {"label": label, "ok": False, "reason": "behind-camera"}
            hit = screen_to_world_ground(sx, sy, cam, w, h, ground_y if ground_y is not None else pt[1])
            if not hit:
                return {"label": label, "ok": False, "screen": [sx, sy], "reason": "s2w-miss"}
            err = math.sqrt((hit["x"] - pt[0]) ** 2 + (hit["z"] - pt[2]) ** 2)
            return {
                "label": label,
                "ok": err < 1.0,
                "worldIn": [pt[0], pt[1], pt[2]],
                "screen": [round(sx, 2), round(sy, 2)],
                "worldOut": [hit["x"], hit["y"], hit["z"]],
                "planarErrorM": round(err, 4),
            }

        checks = [rt("lookAt", look)]
        if body:
            checks.append(rt("body", body, ground_y=body[1]))
        # center pixel S2W should land near look-at on ground plane at look-at Y
        center_hit = screen_to_world_ground(w / 2.0, h / 2.0, cam, w, h, look[1])
        center_err = None
        if center_hit:
            center_err = math.sqrt(
                (center_hit["x"] - look[0]) ** 2 + (center_hit["z"] - look[2]) ** 2
            )
        payload = {
            "mode": "round-trip",
            "status": "passed" if all(c.get("ok") for c in checks) else "failed",
            "window": [w, h],
            "headingRad": heading,
            "headingDeg": None if heading is None else heading * 180.0 / math.pi,
            "checks": checks,
            "centerPixelS2W": center_hit,
            "centerVsLookAtPlanarErrorM": None if center_err is None else round(center_err, 4),
            "camera": cam,
            "candidateOnly": True,
            "safety": {"inputSent": False, "movementSent": False, "clickSent": False},
        }
        if args.json:
            print(json.dumps(payload, default=str))
        else:
            print(f"status={payload['status']} headingDeg={payload['headingDeg']}")
            for c in checks:
                print(c)
            print("centerVsLookAtPlanarErrorM", payload["centerVsLookAtPlanarErrorM"])
        sys.exit(0 if payload["status"] == "passed" else 1)

    # --- W2S mode ---
    if args.target_x is None or args.target_z is None:
        print("ERROR: W2S requires --target-x and --target-z (or use --screen-x/--screen-y / --round-trip)")
        sys.exit(1)

    ty = args.target_y if args.target_y is not None else cam["player_y"]
    sx, sy = world_to_screen(args.target_x, ty, args.target_z, cam, w, h)

    if sx is None:
        print("ERROR: Target is behind camera")
        sys.exit(1)

    # Clamp to window
    sx = max(0, min(w - 1, sx))
    sy = max(0, min(h - 1, sy))

    if args.json:
        print(json.dumps({
            "mode": "world-to-screen",
            "screen_x": round(sx, 1),
            "screen_y": round(sy, 1),
            "window_w": w,
            "window_h": h,
            "camera": cam,
            "headingRad": heading,
            "clicked": args.click,
        }, default=str))
    else:
        print(f"Target ({args.target_x:.1f}, {ty:.1f}, {args.target_z:.1f}) -> Screen ({sx:.0f}, {sy:.0f})")
        print(f"Window: {w}x{h}")
        print(f"Camera: pos=({cam['cam_x']:.1f}, {cam['cam_y']:.1f}, {cam['cam_z']:.1f}) fov={cam['fov']}°")
        if heading is not None:
            print(f"Heading: {heading:.4f} rad ({heading * 180.0 / math.pi:.1f} deg) via cam+0x158")

    if args.click:
        # Legacy PostMessage path — not the preferred C2M backend.
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        click_at(sx, sy, hwnd)
        print("Clicked!")


if __name__ == "__main__":
    main()

