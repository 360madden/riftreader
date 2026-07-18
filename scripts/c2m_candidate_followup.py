#!/usr/bin/env python3
"""Follow-up validation for C2M destination discovery candidates.

No input. Re-reads ranked addresses, compares to fresh RRAPICOORD, classifies
stability, optional pointer-scan toward module bases for top survivors.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import struct
import subprocess
import sys
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000010
TH32CS_SNAPMODULE32 = 0x00000008
MEM_COMMIT = 0x1000


class PROCESSENTRY32W(ctypes.Structure):
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


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def find_targets() -> list[dict[str, Any]]:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(pe)
    pids: list[int] = []
    if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
        while True:
            if pe.szExeFile.lower() == "rift_x64.exe":
                pids.append(int(pe.th32ProcessID))
            if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                break
    kernel32.CloseHandle(snap)
    out: list[dict[str, Any]] = []
    for pid in pids:
        found: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _lp):  # noqa: ANN001
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid and user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, buf, 256)
                if buf.value == "RIFT":
                    found.append(int(hwnd))
            return True

        user32.EnumWindows(cb, 0)
        for hwnd in found:
            out.append({"pid": pid, "hwnd": hwnd, "hwndHex": hex(hwnd)})
    return out


def module_base(pid: int) -> int | None:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap in (-1, wintypes.HANDLE(-1).value):
        return None
    me = MODULEENTRY32W()
    me.dwSize = ctypes.sizeof(me)
    base = None
    try:
        if kernel32.Module32FirstW(snap, ctypes.byref(me)):
            while True:
                if "rift_x64" in me.szModule.lower():
                    base = int(me.modBaseAddr or 0)
                    break
                if not kernel32.Module32NextW(snap, ctypes.byref(me)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return base


def open_process(pid: int) -> int:
    h = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        raise OSError(ctypes.get_last_error())
    return int(h)


def read_bytes(h: int, addr: int, n: int) -> bytes | None:
    buf = ctypes.create_string_buffer(n)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(br))
    if not ok or br.value != n:
        return None
    return buf.raw


def read_f32(h: int, addr: int) -> float | None:
    b = read_bytes(h, addr, 4)
    return struct.unpack("<f", b)[0] if b else None


def read_u64(h: int, addr: int) -> int | None:
    b = read_bytes(h, addr, 8)
    return struct.unpack("<Q", b)[0] if b else None


def capture_api(repo: Path, pid: int, hwnd_hex: str, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ref = out_dir / "reference.json"
    ps1 = repo / "scripts" / "capture-rift-api-reference-coordinate.ps1"
    subprocess.run(
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
            "-ScanContextBytes",
            "4096",
            "-MaxHits",
            "128",
            "-Json",
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if ref.exists():
        return json.loads(ref.read_text(encoding="utf-8"))
    return {}


def scan_pointers_to(
    h: int,
    target: int,
    module_base_addr: int | None,
    max_regions: int = 80,
    max_region_bytes: int = 2 * 1024 * 1024,
) -> dict[str, Any]:
    """Find qwords equal to target (or target-0x320 etc owner candidates)."""
    needles = {
        "exact": target,
        "owner_minus_0x320": target - 0x320 if target > 0x320 else None,
        "minus_0x8": target - 8,
        "minus_0x10": target - 0x10,
        "minus_0x30": target - 0x30,
    }
    needles = {k: v for k, v in needles.items() if v and v > 0x10000}
    patterns = {k: struct.pack("<Q", v) for k, v in needles.items()}
    hits: dict[str, list[dict[str, Any]]] = {k: [] for k in patterns}

    addr = 0
    regions = 0
    mbi = MEMORY_BASIC_INFORMATION()
    while regions < 5000:
        if not kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize or 0)
        prot = int(mbi.Protect) & 0xFF
        if mbi.State == MEM_COMMIT and size > 0 and prot in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80):
            if 0x10000 <= size <= 64 * 1024 * 1024 and regions < max_regions + 200:
                # only scan first max_regions large rw-ish
                if prot in (0x04, 0x40, 0x08, 0x80) and len([1 for xs in hits.values() for _ in xs]) < 200:
                    to_read = min(size, max_region_bytes)
                    data = read_bytes(h, base, to_read)
                    if data:
                        for name, pat in patterns.items():
                            start = 0
                            while len(hits[name]) < 30:
                                i = data.find(pat, start)
                                if i < 0:
                                    break
                                hit_addr = base + i
                                rva = None
                                if module_base_addr and module_base_addr <= hit_addr < module_base_addr + 0x4000000:
                                    rva = hit_addr - module_base_addr
                                hits[name].append(
                                    {
                                        "pointerAddressHex": hex(hit_addr),
                                        "pointsToHex": hex(needles[name]),
                                        "moduleRvaHex": hex(rva) if rva is not None else None,
                                        "inModuleImage": rva is not None,
                                    }
                                )
                                start = i + 8
        nxt = base + size
        if nxt <= addr:
            break
        addr = nxt
        regions += 1

    module_hits = []
    for name, lst in hits.items():
        for hitem in lst:
            if hitem.get("inModuleImage"):
                module_hits.append({"kind": name, **hitem})
    return {"needles": {k: hex(v) for k, v in needles.items()}, "hits": hits, "moduleHits": module_hits}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--discovery-summary", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--top-n", type=int, default=8)
    ap.add_argument("--pointer-scan-top", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    disc = json.loads(args.discovery_summary.read_text(encoding="utf-8"))
    cands = (disc.get("topCandidates") or [])[: args.top_n]
    if not cands:
        print(json.dumps({"status": "blocked", "blockers": ["no-candidates"]}))
        return 2

    targets = find_targets()
    if not targets:
        print(json.dumps({"status": "blocked", "blockers": ["no-rift"]}))
        return 2
    t = targets[0]
    run_dir = repo / "scripts" / "captures" / f"c2m-candidate-followup-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    api = capture_api(repo, t["pid"], t["hwndHex"], run_dir / "api")
    coord = api.get("coordinate") or {}
    try:
        px, py, pz = float(coord["x"]), float(coord["y"]), float(coord["z"])
    except (KeyError, TypeError, ValueError):
        write_json(run_dir / "summary.json", {"status": "blocked", "blockers": ["api-missing"]})
        return 2

    h = open_process(t["pid"])
    mbase = module_base(t["pid"])
    reads = []
    try:
        for c in cands:
            addr = int(c["address"])
            raw = read_bytes(h, addr, 12)
            if not raw:
                reads.append({"addressHex": hex(addr), "status": "unreadable"})
                continue
            x, y, z = struct.unpack("<fff", raw)
            prev = c.get("afterClick2") or c.get("after") or {}
            d_prev = None
            if prev:
                d_prev = max(abs(x - prev["x"]), abs(y - prev["y"]), abs(z - prev["z"]))
            dist = math.hypot(x - px, z - pz)
            # classification
            cls = "unknown"
            if dist < 2.0:
                cls = "player-body-like"
            elif d_prev is not None and d_prev < 0.05:
                cls = "frozen-since-discovery"
            elif d_prev is not None and d_prev < 5.0 and dist > 5.0:
                cls = "stable-nonplayer-goal-like"
            elif d_prev is not None and d_prev >= 5.0:
                cls = "moved-a-lot-since-discovery"
            neigh = []
            for off in range(-64, 80, 4):
                v = read_f32(h, addr + off)
                neigh.append({"rel": off, "v": v})
            # pointer-looking neighbors
            ptrs = []
            for off in (-24, -16, -8, 12, 16, 24, 32):
                p = read_u64(h, addr + off)
                if p and p > 0x10000:
                    ptrs.append({"rel": off, "ptrHex": hex(p)})
            reads.append(
                {
                    "addressHex": hex(addr),
                    "discoveryScore": c.get("score"),
                    "now": {"x": x, "y": y, "z": z},
                    "apiPlayer": {"x": px, "y": py, "z": pz},
                    "planarToPlayer": dist,
                    "deltaVsDiscovery": d_prev,
                    "classification": cls,
                    "neighborhood": neigh,
                    "nearbyQwords": ptrs,
                }
            )

        # pointer scan best stable-nonplayer
        survivors = [r for r in reads if r.get("classification") == "stable-nonplayer-goal-like"]
        if not survivors:
            survivors = [r for r in reads if (r.get("planarToPlayer") or 0) > 5 and r.get("status") != "unreadable"]
        survivors = survivors[: args.pointer_scan_top]
        pointer_results = []
        for s in survivors:
            addr = int(s["addressHex"], 16)
            pointer_results.append(
                {
                    "targetHex": s["addressHex"],
                    "scan": scan_pointers_to(h, addr, mbase),
                }
            )
    finally:
        kernel32.CloseHandle(h)

    # rank follow-up
    for r in reads:
        score = 0
        reasons = []
        if r.get("classification") == "stable-nonplayer-goal-like":
            score += 5
            reasons.append("stable-nonplayer")
        if r.get("classification") == "frozen-since-discovery" and (r.get("planarToPlayer") or 0) > 10:
            score += 3
            reasons.append("frozen-far")
        if r.get("classification") == "player-body-like":
            score -= 5
            reasons.append("body")
        if (r.get("planarToPlayer") or 0) > 40:
            score += 1
            reasons.append("far")
        r["followupScore"] = score
        r["followupReasons"] = reasons
    reads_sorted = sorted(reads, key=lambda r: (-(r.get("followupScore") or -99), r.get("planarToPlayer") or 0))

    summary = {
        "schemaVersion": 1,
        "kind": "riftreader-c2m-candidate-followup",
        "generatedAtUtc": utc_now(),
        "status": "passed" if any((r.get("followupScore") or 0) >= 3 for r in reads_sorted) else "blocked",
        "verdict": "c2m-followup-classified",
        "target": t,
        "moduleBase": hex(mbase) if mbase else None,
        "api": coord,
        "sourceDiscovery": str(args.discovery_summary),
        "reads": reads_sorted,
        "pointerScans": pointer_results,
        "safety": {
            "inputSent": False,
            "movementSent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "targetMemoryBytesWritten": False,
        },
        "next": {
            "recommended": [
                "Treat top followupScore>=3 as session C2M-related seeds only",
                "Optional: one approved click while watching top address for write",
                "Do not promote without restart survival + multi-click proof",
            ]
        },
    }
    write_json(run_dir / "summary.json", summary)
    md = [
        "# C2M candidate follow-up",
        "",
        f"- status: `{summary['status']}`",
        f"- api: `{coord}`",
        "",
        "## Ranked reads",
        "",
    ]
    for r in reads_sorted:
        md.append(
            f"- `{r.get('addressHex')}` class=`{r.get('classification')}` "
            f"follow={r.get('followupScore')} dist={r.get('planarToPlayer')} "
            f"delta={r.get('deltaVsDiscovery')} now={r.get('now')}"
        )
    md.append("")
    md.append("## Module pointer hits")
    for ps in pointer_results:
        md.append(f"### {ps['targetHex']}")
        mh = ps["scan"].get("moduleHits") or []
        if not mh:
            md.append("- (none in scanned window)")
        for hitem in mh[:10]:
            md.append(f"- {hitem}")
    (run_dir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(summary["status"], run_dir)
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
