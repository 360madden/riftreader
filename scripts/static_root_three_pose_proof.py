#!/usr/bin/env python3
"""Three-pose displacement proof for a static owner-coordinate root.

Requires explicit --movement-approved. Sends W then S via C# SendInput ScanCode.
Compares chain XYZ across poses and optional RRAPICOORD API-now at each pose.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import ctypes
from ctypes import wintypes

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def find_target() -> dict[str, Any] | None:
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
        for hwnd in found:
            return {"pid": pid, "hwnd": hwnd, "hwndHex": hex(hwnd), "moduleBase": base}
    return None


def read_bytes(pid: int, addr: int, n: int) -> bytes | None:
    h = kernel32.OpenProcess(0x0010, False, pid)
    if not h:
        return None
    buf = ctypes.create_string_buffer(n)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(br))
    kernel32.CloseHandle(h)
    return buf.raw[: br.value] if ok and br.value else None


def read_u64(pid: int, addr: int) -> int | None:
    d = read_bytes(pid, addr, 8)
    return struct.unpack("<Q", d)[0] if d and len(d) == 8 else None


def read_f32s(pid: int, addr: int, count: int) -> list[float] | None:
    d = read_bytes(pid, addr, count * 4)
    if not d:
        return None
    c = len(d) // 4
    return list(struct.unpack("<" + "f" * c, d[: c * 4]))


def read_chain(pid: int, module_base: int, root_rva: int, coord_off: int) -> dict[str, Any] | None:
    owner = read_u64(pid, module_base + root_rva)
    if not owner or owner < 0x10000:
        return None
    xyz = read_f32s(pid, owner + coord_off, 3)
    if not xyz or len(xyz) < 3:
        return None
    cam = read_u64(pid, owner + 0x330)
    heading = None
    if cam and cam > 0x10000:
        h = read_f32s(pid, cam + 0x158, 1)
        heading = h[0] if h else None
    return {
        "owner": hex(owner),
        "coordAddress": hex(owner + coord_off),
        "cameraChild": hex(cam) if cam else None,
        "x": xyz[0],
        "y": xyz[1],
        "z": xyz[2],
        "headingRad": heading,
        "atUtc": utc_iso(),
    }


def planar(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot(float(b["x"]) - float(a["x"]), float(b["z"]) - float(a["z"]))


def send_key(pid: int, hwnd_hex: str, key: str, hold_ms: int) -> dict[str, Any]:
    ps1 = SCRIPTS / "send-rift-key-csharp.ps1"
    proc = subprocess.run(
        [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            "--key",
            key,
            "--hold-ms",
            str(hold_ms),
            "--process-name",
            "rift_x64",
            "--pid",
            str(pid),
            "--hwnd",
            hwnd_hex,
            "--input-mode",
            "ScanCode",
            "--focus-delay-ms",
            "400",
            "--json",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    parsed = None
    if "{" in out:
        try:
            parsed = json.loads(out[out.index("{") : out.rindex("}") + 1])
        except json.JSONDecodeError:
            parsed = None
    return {
        "exitCode": proc.returncode,
        "key": key,
        "holdMs": hold_ms,
        "ok": proc.returncode == 0,
        "parsed": parsed,
        "stdoutTail": out[-800:],
    }


def capture_api(pid: int, hwnd_hex: str, out_dir: Path, tag: str) -> dict[str, Any] | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ref = out_dir / f"{tag}.json"
    ps1 = SCRIPTS / "capture-rift-api-reference-coordinate.ps1"
    proc = subprocess.run(
        [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            "-ProcessId",
            str(pid),
            "-TargetWindowHandle",
            hwnd_hex,
            "-OutputRoot",
            str(out_dir),
            "-OutputFile",
            str(ref),
            "-Json",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "{" not in blob:
        return None
    try:
        data = json.loads(blob[blob.index("{") : blob.rindex("}") + 1])
    except json.JSONDecodeError:
        return None
    coord = data.get("Coordinate") or data.get("coordinate")
    if not isinstance(coord, dict):
        return None
    return {
        "x": float(coord.get("X", coord.get("x"))),
        "y": float(coord.get("Y", coord.get("y"))),
        "z": float(coord.get("Z", coord.get("z"))),
        "file": str(ref),
        "status": data.get("Status") or data.get("status"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--hwnd")
    ap.add_argument("--module-base")
    ap.add_argument("--root-rva", default="0x32E07C0")
    ap.add_argument("--coord-offset", default="0x320")
    ap.add_argument("--hold-ms", type=int, default=800)
    ap.add_argument("--settle-seconds", type=float, default=1.0)
    ap.add_argument("--min-pose-planar", type=float, default=0.75)
    ap.add_argument("--api-tolerance", type=float, default=0.5)
    ap.add_argument("--skip-api", action="store_true")
    ap.add_argument("--movement-approved", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.movement_approved:
        print(json.dumps({"status": "blocked", "blockers": ["movement-approved-flag-required"]}))
        return 2

    target = find_target()
    if not target:
        print(json.dumps({"status": "failed", "errors": ["no-rift-target"]}))
        return 1

    pid = int(args.pid or target["pid"])
    hwnd_hex = args.hwnd or target["hwndHex"]
    if isinstance(hwnd_hex, int):
        hwnd_hex = hex(hwnd_hex)
    module_base = int(args.module_base, 0) if args.module_base else int(target["moduleBase"])
    root_rva = int(args.root_rva, 0)
    coord_off = int(args.coord_offset, 0)

    if pid != target["pid"] or int(hwnd_hex, 16) != target["hwnd"]:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blockers": ["target-drift"],
                    "expected": target,
                    "requested": {"pid": pid, "hwnd": hwnd_hex},
                }
            )
        )
        return 2

    run_dir = SCRIPTS / "captures" / f"static-root-three-pose-{pid}-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "static-root-three-pose-proof",
        "generatedAtUtc": utc_iso(),
        "status": "running",
        "target": {
            "pid": pid,
            "hwnd": hwnd_hex,
            "moduleBase": hex(module_base),
            "rootRva": hex(root_rva),
            "coordOffset": hex(coord_off),
            "chain": f"[rift_x64+{hex(root_rva)}]+{hex(coord_off)}/+{hex(coord_off+4)}/+{hex(coord_off+8)}",
        },
        "poses": [],
        "inputs": [],
        "blockers": [],
        "warnings": [],
        "safety": {
            "movementApproved": True,
            "movementSent": False,
            "inputSent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "truthUpdated": False,
        },
    }

    def sample(tag: str) -> dict[str, Any]:
        chain = read_chain(pid, module_base, root_rva, coord_off)
        api = None if args.skip_api else capture_api(pid, hwnd_hex, run_dir / "api", tag)
        pose: dict[str, Any] = {"tag": tag, "chain": chain, "api": api}
        if chain and api:
            dx = abs(chain["x"] - api["x"])
            dy = abs(chain["y"] - api["y"])
            dz = abs(chain["z"] - api["z"])
            pose["apiVsChain"] = {
                "dx": dx,
                "dy": dy,
                "dz": dz,
                "maxAbs": max(dx, dy, dz),
                "withinTolerance": max(dx, dy, dz) <= args.api_tolerance,
                "tolerance": args.api_tolerance,
            }
        summary["poses"].append(pose)
        return pose

    # Pose A
    a = sample("A-baseline")
    if not a.get("chain"):
        summary["status"] = "failed"
        summary["blockers"].append("chain-null-at-baseline")
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({"status": summary["status"], "blockers": summary["blockers"], "summaryJson": str(run_dir / "summary.json")}))
        return 1

    # Forward
    fwd = send_key(pid, hwnd_hex, "w", args.hold_ms)
    summary["inputs"].append(fwd)
    summary["safety"]["inputSent"] = True
    summary["safety"]["movementSent"] = True
    time.sleep(args.settle_seconds)
    b = sample("B-after-W")

    # Reverse
    rev = send_key(pid, hwnd_hex, "s", args.hold_ms)
    summary["inputs"].append(rev)
    time.sleep(args.settle_seconds)
    c = sample("C-after-S")

    chains = [p.get("chain") for p in summary["poses"]]
    if any(ch is None for ch in chains):
        summary["blockers"].append("chain-null-mid-proof")

    ab = planar(chains[0], chains[1]) if chains[0] and chains[1] else None
    bc = planar(chains[1], chains[2]) if chains[1] and chains[2] else None
    ac = planar(chains[0], chains[2]) if chains[0] and chains[2] else None
    summary["displacement"] = {
        "A_to_B_planar": ab,
        "B_to_C_planar": bc,
        "A_to_C_planar": ac,
        "minRequired": args.min_pose_planar,
        "A_to_B_ok": ab is not None and ab >= args.min_pose_planar,
        "B_to_C_ok": bc is not None and bc >= args.min_pose_planar * 0.5,
    }

    api_oks = [
        p.get("apiVsChain", {}).get("withinTolerance")
        for p in summary["poses"]
        if p.get("apiVsChain") is not None
    ]
    summary["apiNowGate"] = {
        "posesCompared": len(api_oks),
        "allWithinTolerance": bool(api_oks) and all(api_oks),
        "skipped": bool(args.skip_api),
    }

    owners = {p["chain"]["owner"] for p in summary["poses"] if p.get("chain")}
    summary["ownerStableAcrossPoses"] = len(owners) == 1
    summary["ownersSeen"] = sorted(owners)

    ok_disp = summary["displacement"]["A_to_B_ok"] and summary["displacement"]["B_to_C_ok"]
    ok_api = summary["apiNowGate"]["skipped"] or summary["apiNowGate"]["allWithinTolerance"]
    ok_owner = summary["ownerStableAcrossPoses"]
    ok_inputs = all(i.get("ok") for i in summary["inputs"])

    if not ok_inputs:
        summary["blockers"].append("input-send-failed")
    if not ok_disp:
        summary["blockers"].append("insufficient-displacement")
    if not ok_api:
        summary["blockers"].append("api-vs-chain-mismatch")
    if not ok_owner:
        summary["warnings"].append("owner-changed-across-poses")

    if not summary["blockers"] and ok_disp and ok_api:
        summary["status"] = "passed"
        summary["verdict"] = "three-pose-displacement-and-api-match-passed"
    elif summary["blockers"]:
        summary["status"] = "failed" if "chain-null" in str(summary["blockers"]) or "input-send" in str(summary["blockers"]) else "blocked"
        summary["verdict"] = "three-pose-proof-incomplete"
    else:
        summary["status"] = "failed"
        summary["verdict"] = "three-pose-proof-failed"

    summary["artifacts"] = {
        "runDirectory": str(run_dir),
        "summaryJson": str(run_dir / "summary.json"),
        "summaryMarkdown": str(run_dir / "summary.md"),
    }

    md = [
        "# Static root three-pose proof",
        "",
        f"- status: **{summary['status']}**",
        f"- verdict: `{summary.get('verdict')}`",
        f"- chain: `{summary['target']['chain']}`",
        f"- pid/hwnd: `{pid}` / `{hwnd_hex}`",
        f"- A→B planar: `{ab}`",
        f"- B→C planar: `{bc}`",
        f"- API gate: `{summary['apiNowGate']}`",
        f"- movementSent: true",
        "",
    ]
    (run_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": summary["status"],
                "verdict": summary.get("verdict"),
                "displacement": summary["displacement"],
                "apiNowGate": summary["apiNowGate"],
                "blockers": summary["blockers"],
                "summaryJson": summary["artifacts"]["summaryJson"],
            }
        )
    )
    return 0 if summary["status"] == "passed" else (2 if summary["status"] == "blocked" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
