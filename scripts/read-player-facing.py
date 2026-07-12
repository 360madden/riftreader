#!/usr/bin/env python3
"""Read player facing from the camera direction vector."""
import ctypes, ctypes.wintypes, struct, math, json, sys

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0
CAMERA_OFFSET = 0x330
DIR_X_OFFSET = 0x2C
DIR_Z_OFFSET = 0x34


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("GlblcntUsage", ctypes.wintypes.DWORD),
        ("ProccntUsage", ctypes.wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", ctypes.wintypes.DWORD),
        ("hModule", ctypes.wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


def find_base(pid):
    kernel32 = ctypes.windll.kernel32
    TH32CS_SNAPMODULE = 0x00000010
    TH32CS_SNAPMODULE32 = 0x00000008
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot == ctypes.wintypes.HANDLE(-1).value:
        return None
    me = MODULEENTRY32()
    me.dwSize = ctypes.sizeof(me)
    base = None
    try:
        if kernel32.Module32First(snapshot, ctypes.byref(me)):
            while True:
                name = me.szModule.decode("utf-8", errors="ignore").lower()
                if "rift_x64" in name:
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

def read_float(pid, addr):
    d = read_bytes(pid, addr, 4)
    return struct.unpack('<f', d)[0] if d and len(d) == 4 else None

def read_floats(pid, addr, count):
    d = read_bytes(pid, addr, count * 4)
    if not d:
        return []
    return [struct.unpack('<f', d[i*4:i*4+4])[0] for i in range(count)]

def get_player_facing(pid):
    """Get player facing from camera direction vector."""
    base = find_base(pid)
    if not base:
        return None, None, None
    
    obj = read_ptr(pid, base + COORD_RVA)
    if not obj or obj < 0x10000:
        return None, None, None
    
    child330 = read_ptr(pid, obj + CAMERA_OFFSET)
    if not child330 or child330 < 0x10000:
        return None, None, None
    
    vals = read_floats(pid, child330, 16)
    if len(vals) < 14:
        return None, None, None
    
    x = read_float(pid, obj + 0x320)
    z = read_float(pid, obj + 0x328)
    dx, dz = vals[DIR_X_OFFSET // 4], vals[DIR_Z_OFFSET // 4]
    yaw = math.degrees(math.atan2(dx, dz)) % 360
    
    return x, z, yaw

def get_player_coords(pid):
    """Get player coordinates."""
    base = find_base(pid)
    if not base:
        return None, None, None
    obj = read_ptr(pid, base + COORD_RVA)
    if not obj or obj < 0x10000:
        return None, None, None
    x = read_float(pid, obj + 0x320)
    y = read_float(pid, obj + 0x324)
    z = read_float(pid, obj + 0x328)
    return x, y, z

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    
    base = find_base(args.pid)
    if not base:
        print("ERROR: Cannot find rift_x64.exe base")
        sys.exit(1)
    
    x, z, yaw = get_player_facing(args.pid)
    if x is None:
        print("ERROR: Cannot read facing")
        sys.exit(1)
    
    if args.json:
        print(json.dumps({
            "x": round(x, 2),
            "z": round(z, 2),
            "facing_deg": round(yaw, 1),
            "facing_rad": round(math.radians(yaw), 4),
            "source": "camera-direction",
            "chain": f"[[{hex(base + COORD_RVA)}+0x330]+0x2c/+0x34]",
        }))
    else:
        print(f"Position: ({x:.2f}, {z:.2f})")
        print(f"Facing: {yaw:.1f} deg")
        print(f"Chain: [[{hex(base + COORD_RVA)}+0x330]+0x2c/+0x34]")
