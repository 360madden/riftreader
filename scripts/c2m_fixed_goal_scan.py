#!/usr/bin/env python3
"""Find heap vec3s that change on click but do NOT track the player.

Unlike the first C2M discovery pass, this rejects player-centered ±40 volumes
and player-tracking motion. Targets a true fixed click destination.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import struct
import subprocess
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
TH32CS_SNAPPROCESS = 0x00000002


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


def find_target() -> dict[str, Any] | None:
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
            rect = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            return {
                "pid": pid,
                "hwnd": hwnd,
                "hwndHex": hex(hwnd),
                "clientWidth": int(rect.right - rect.left),
                "clientHeight": int(rect.bottom - rect.top),
            }
    return None


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


def regions_rw(h: int, limit: int = 40) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    while len(out) < 400:
        if not kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize or 0)
        prot = int(mbi.Protect) & 0xFF
        if mbi.State == MEM_COMMIT and prot in (0x04, 0x40, 0x08, 0x80) and 0x100000 <= size <= 32 * 1024 * 1024:
            out.append((base, size))
        nxt = base + size
        if nxt <= addr:
            break
        addr = nxt
    out.sort(key=lambda r: -r[1])
    return out[:limit]


def world_like(v: float) -> bool:
    return math.isfinite(v) and 1.0 < abs(v) < 50000.0


def collect_map(
    h: int,
    regs: list[tuple[int, int]],
    player: tuple[float, float, float],
    max_bytes: int,
    min_d: float,
    max_d: float,
) -> dict[int, tuple[float, float, float]]:
    px, py, pz = player
    hits: dict[int, tuple[float, float, float]] = {}
    for base, size in regs:
        data = read_bytes(h, base, min(size, max_bytes))
        if not data:
            continue
        for i in range(0, len(data) - 12, 4):
            x, y, z = struct.unpack_from("<fff", data, i)
            if not (world_like(x) and world_like(y) and world_like(z)):
                continue
            if not (-500 < y < 10000):
                continue
            d = math.hypot(x - px, z - pz)
            if min_d <= d <= max_d:
                hits[base + i] = (x, y, z)
    return hits


def capture_api(repo: Path, pid: int, hwnd_hex: str, out_dir: Path) -> tuple[float, float, float] | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ref = out_dir / "reference.json"
    ps1 = repo / "scripts" / "capture-rift-api-reference-coordinate.ps1"
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
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if ref.exists():
        try:
            c = json.loads(ref.read_text(encoding="utf-8")).get("coordinate") or {}
            return float(c["x"]), float(c["y"]), float(c["z"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
    out = proc.stdout or ""
    if "Coordinate" in out or "coordinate" in out:
        try:
            start = out.index("{")
            end = out.rindex("}") + 1
            payload = json.loads(out[start:end])
            c = payload.get("Coordinate") or payload.get("coordinate") or {}
            if "X" in c:
                return float(c["X"]), float(c["Y"]), float(c["Z"])
            return float(c["x"]), float(c["y"]), float(c["z"])
        except (ValueError, json.JSONDecodeError, KeyError, TypeError):
            return None
    return None


def click(hwnd: int, x: int, y: int) -> None:
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.1)
    lp = (y << 16) | (x & 0xFFFF)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.04)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--stimulus-approved", action="store_true")
    ap.add_argument("--max-regions", type=int, default=30)
    ap.add_argument("--max-region-bytes", type=int, default=3 * 1024 * 1024)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    repo = args.repo_root.resolve()
    run_dir = repo / "scripts" / "captures" / f"c2m-fixed-goal-scan-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "riftreader-c2m-fixed-goal-scan",
        "generatedAtUtc": utc_now(),
        "status": "blocked",
        "blockers": [],
        "warnings": [],
        "safety": {
            "inputSent": False,
            "clickSent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "promotionPerformed": False,
        },
        "artifacts": {"runDirectory": str(run_dir)},
    }

    if not args.execute:
        summary["status"] = "planned"
        write_json(run_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2) if args.json else "planned")
        return 0

    t = find_target()
    if not t:
        summary["blockers"].append("no-rift")
        write_json(run_dir / "summary.json", summary)
        return 2
    summary["target"] = t

    if not args.stimulus_approved:
        summary["blockers"].append("stimulus-not-approved")
        write_json(run_dir / "summary.json", summary)
        return 2

    p0 = capture_api(repo, t["pid"], t["hwndHex"], run_dir / "api0")
    if not p0:
        summary["blockers"].append("api-failed")
        write_json(run_dir / "summary.json", summary)
        return 2
    summary["playerBefore"] = {"x": p0[0], "y": p0[1], "z": p0[2]}

    h = open_process(t["pid"])
    try:
        regs = regions_rw(h, args.max_regions)
        base_map = collect_map(h, regs, p0, args.max_region_bytes, 4.0, 120.0)
        write_json(run_dir / "baseline-count.json", {"count": len(base_map)})

        # Two clicks at different screen points for discrimination
        cx1 = int(t["clientWidth"] * 0.55)
        cy1 = int(t["clientHeight"] * 0.80)
        click(t["hwnd"], cx1, cy1)
        summary["safety"]["inputSent"] = True
        summary["safety"]["clickSent"] = True
        time.sleep(0.15)  # short settle — destination often written before walk

        # Re-read player quickly via memory? keep API light - use p0 approx for filter, API after
        after1 = collect_map(h, regs, p0, args.max_region_bytes, 4.0, 120.0)

        # Candidates: changed a lot OR new, not player-tracking, not ±40 corners
        px, py, pz = p0
        cands = []
        for addr, (x, y, z) in after1.items():
            prev = base_map.get(addr)
            dist = math.hypot(x - px, z - pz)
            if dist < 4:
                continue
            # reject ±40 player-centered corners
            if (
                abs(abs(x - px) - 40) < 2
                and abs(abs(y - py) - 40) < 2
                and abs(abs(z - pz) - 40) < 2
            ):
                continue
            if prev is None:
                score = 4
                reason = "new"
                change = None
            else:
                change = max(abs(x - prev[0]), abs(y - prev[1]), abs(z - prev[2]))
                if change < 1.0:
                    continue
                # if change mirrors small player noise, skip
                score = 3
                reason = "changed"
            cands.append(
                {
                    "addressHex": hex(addr),
                    "after": {"x": x, "y": y, "z": z},
                    "before": None if prev is None else {"x": prev[0], "y": prev[1], "z": prev[2]},
                    "planarDist": dist,
                    "change": change,
                    "score": score,
                    "reason": reason,
                }
            )

        # Second click
        cx2 = int(t["clientWidth"] * 0.30)
        cy2 = int(t["clientHeight"] * 0.75)
        click(t["hwnd"], cx2, cy2)
        time.sleep(0.15)
        p1 = capture_api(repo, t["pid"], t["hwndHex"], run_dir / "api1") or p0
        after2 = collect_map(h, regs, p1, args.max_region_bytes, 4.0, 120.0)

        # Boost if still far from player after and changed again toward new fixed goal
        boosted = []
        for c in cands:
            addr = int(c["addressHex"], 16)
            now = after2.get(addr)
            if not now:
                continue
            x, y, z = now
            dist2 = math.hypot(x - p1[0], z - p1[2])
            if dist2 < 4:
                continue
            if (
                abs(abs(x - p1[0]) - 40) < 2
                and abs(abs(y - p1[1]) - 40) < 2
                and abs(abs(z - p1[2]) - 40) < 2
            ):
                continue
            prev_after = c["after"]
            ch2 = max(abs(x - prev_after["x"]), abs(y - prev_after["y"]), abs(z - prev_after["z"]))
            # Fixed goal: should change on re-click (new goal) but not equal player
            sc = c["score"]
            reasons = [c["reason"]]
            if ch2 >= 1.0:
                sc += 4
                reasons.append("changed-on-second-click")
            else:
                # held fixed while player may have moved — also interesting if far
                if dist2 > 8:
                    sc += 2
                    reasons.append("held-fixed-after-second-click")
            # reject if now tracks player from p0 to p1
            if prev_after:
                track_err = abs((x - prev_after["x"]) - (p1[0] - p0[0])) + abs((z - prev_after["z"]) - (p1[2] - p0[2]))
                if track_err < 1.0 and math.hypot(p1[0] - p0[0], p1[2] - p0[2]) > 0.5:
                    sc -= 5
                    reasons.append("tracks-player")
            boosted.append(
                {
                    **c,
                    "after2": {"x": x, "y": y, "z": z},
                    "planarDist2": dist2,
                    "change2": ch2,
                    "score": sc,
                    "reasons": reasons,
                }
            )

        boosted.sort(key=lambda r: (-r["score"], -(r.get("change2") or 0)))
        top = [b for b in boosted if b["score"] >= 4][:30]
        summary["playerAfter"] = {"x": p1[0], "y": p1[1], "z": p1[2]}
        summary["playerPlanarDelta"] = math.hypot(p1[0] - p0[0], p1[2] - p0[2])
        summary["baselineCount"] = len(base_map)
        summary["after1Count"] = len(after1)
        summary["candidateCount"] = len(boosted)
        summary["topCandidates"] = top
        summary["clicks"] = [
            {"clientX": cx1, "clientY": cy1},
            {"clientX": cx2, "clientY": cy2},
        ]
        if top:
            summary["status"] = "passed"
            summary["verdict"] = "fixed-goal-session-candidates"
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "no-fixed-goal-candidates-after-player-track-rejection"
            summary["blockers"].append("no-high-score-fixed-goal")
            summary["topCandidates"] = boosted[:15]
    finally:
        kernel32.CloseHandle(h)

    write_json(run_dir / "summary.json", summary)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary.get("status"),
                    "verdict": summary.get("verdict"),
                    "blockers": summary.get("blockers"),
                    "playerBefore": summary.get("playerBefore"),
                    "playerAfter": summary.get("playerAfter"),
                    "playerPlanarDelta": summary.get("playerPlanarDelta"),
                    "candidateCount": summary.get("candidateCount"),
                    "topCandidates": summary.get("topCandidates"),
                    "runDirectory": str(run_dir),
                    "safety": summary.get("safety"),
                },
                indent=2,
            )
        )
    else:
        print(summary.get("status"), run_dir)
    return 0 if summary.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
