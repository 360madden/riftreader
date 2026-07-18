#!/usr/bin/env python3
"""Instant pose + heading from promoted static root (current-truth).

No input. Prints JSON with owner XYZ, camera look-at, heading at cam+0x158.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
DEFAULT_ROOT = 0x32E07C0


def find_pid_hwnd() -> tuple[int, int, int] | None:
    class PE(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    class ME(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("th32ModuleID", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("GlblcntUsage", wintypes.DWORD),
            ("ProccntUsage", wintypes.DWORD),
            ("modBaseAddr", ctypes.c_void_p),
            ("modBaseSize", wintypes.DWORD),
            ("hModule", wintypes.HMODULE),
            ("szModule", ctypes.c_char * 256),
            ("szExePath", ctypes.c_char * 260),
        ]

    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    pe = PE()
    pe.dwSize = ctypes.sizeof(pe)
    pids: list[int] = []
    if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
        while True:
            if pe.szExeFile.lower() == "rift_x64.exe":
                pids.append(int(pe.th32ProcessID))
            if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                break
    kernel32.CloseHandle(snap)
    for pid in pids:
        found: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _lp, pid=pid, found=found):  # noqa: ANN001
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid and user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, buf, 256)
                if buf.value == "RIFT":
                    found.append(int(hwnd))
            return True

        user32.EnumWindows(cb, 0)
        base = None
        snap2 = kernel32.CreateToolhelp32Snapshot(0x18, pid)
        me = ME()
        me.dwSize = ctypes.sizeof(me)
        if kernel32.Module32First(snap2, ctypes.byref(me)):
            while True:
                if b"rift_x64" in me.szModule.lower():
                    base = int(me.modBaseAddr)
                    break
                if not kernel32.Module32Next(snap2, ctypes.byref(me)):
                    break
        kernel32.CloseHandle(snap2)
        if found and base:
            return pid, found[0], base
    return None


def read_bytes(pid: int, addr: int, n: int) -> bytes | None:
    h = kernel32.OpenProcess(0x0010, False, pid)
    buf = ctypes.create_string_buffer(n)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(br))
    kernel32.CloseHandle(h)
    return buf.raw[: br.value] if ok and br.value else None


def u64(pid: int, addr: int) -> int | None:
    d = read_bytes(pid, addr, 8)
    return struct.unpack("<Q", d)[0] if d and len(d) == 8 else None


def f32s(pid: int, addr: int, n: int) -> list[float] | None:
    d = read_bytes(pid, addr, n * 4)
    if not d:
        return None
    c = len(d) // 4
    return list(struct.unpack("<" + "f" * c, d[: c * 4]))


def load_root(repo: Path) -> int:
    p = repo / "docs" / "recovery" / "current-truth.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        rva = (data.get("bestCurrentCandidate") or {}).get("rootRva")
        if rva:
            return int(str(rva), 0)
    except Exception:
        pass
    return DEFAULT_ROOT


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--root-rva", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    repo = args.repo_root.resolve()
    root = int(args.root_rva, 0) if args.root_rva else load_root(repo)
    found = find_pid_hwnd()
    if not found:
        print(json.dumps({"status": "failed", "error": "no-rift"}))
        return 1
    pid, hwnd, base = found
    owner = u64(pid, base + root)
    if not owner:
        print(json.dumps({"status": "failed", "error": "root-null", "rootRva": hex(root)}))
        return 1
    xyz = f32s(pid, owner + 0x320, 3)
    cam = u64(pid, owner + 0x330)
    heading = f32s(pid, cam + 0x158, 1) if cam else None
    camf = f32s(pid, cam, 16) if cam else None
    out = {
        "status": "passed",
        "pid": pid,
        "hwnd": hex(hwnd),
        "moduleBase": hex(base),
        "rootRva": hex(root),
        "owner": hex(owner),
        "coordinate": {"x": xyz[0], "y": xyz[1], "z": xyz[2]} if xyz else None,
        "cameraChild": hex(cam) if cam else None,
        "headingRad": heading[0] if heading else None,
        "headingDeg": (heading[0] * 180.0 / math.pi) if heading else None,
        "lookAt": (
            {"x": camf[5], "y": camf[6], "z": camf[7]} if camf and len(camf) > 7 else None
        ),
        "fov": camf[14] if camf and len(camf) > 14 else None,
        "chain": f"[rift_x64+{hex(root)}]+0x320/+0x324/+0x328",
        "headingChain": "[[owner+0x330]+0x158]",
        "safety": {"inputSent": False, "movementSent": False},
    }
    print(json.dumps(out, indent=2 if args.json else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
