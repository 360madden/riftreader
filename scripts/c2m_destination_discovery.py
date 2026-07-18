#!/usr/bin/env python3
"""Automated click-to-move (C2M) destination discovery.

Lane:
  preflight → RRAPICOORD API → baseline float scan → optional ground click
  → post-click scan → rank candidates that changed toward a non-player world vec3

Safety:
  - Exact PID/HWND required for --execute
  - Ground click only with --stimulus-approved
  - No CE, no x64dbg, no truth/proof promotion, no destination writes
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import struct
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_WRITECOPY = 0x80
TH32CS_SNAPPROCESS = 0x00000002
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001

READABLE_RW = {
    PAGE_READWRITE,
    PAGE_EXECUTE_READWRITE,
    PAGE_WRITECOPY,
    PAGE_EXECUTE_WRITECOPY,
}


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


@dataclass
class Vec3:
    x: float
    y: float
    z: float

    def planar_dist(self, other: "Vec3") -> float:
        return math.hypot(self.x - other.x, self.z - other.z)

    def max_abs_delta(self, other: "Vec3") -> float:
        return max(abs(self.x - other.x), abs(self.y - other.y), abs(self.z - other.z))

    def as_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def find_rift_targets() -> list[dict[str, Any]]:
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
            rect = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            out.append(
                {
                    "pid": pid,
                    "hwnd": hwnd,
                    "hwndHex": hex(hwnd),
                    "clientWidth": int(rect.right - rect.left),
                    "clientHeight": int(rect.bottom - rect.top),
                }
            )
    return out


def open_process(pid: int) -> int:
    h = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        h = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        raise OSError(f"OpenProcess failed err={ctypes.get_last_error()}")
    return int(h)


def read_bytes(h: int, addr: int, size: int) -> bytes | None:
    buf = ctypes.create_string_buffer(size)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(br))
    if not ok or br.value != size:
        return None
    return buf.raw


def enumerate_rw_regions(h: int, max_regions: int = 400) -> list[tuple[int, int]]:
    regions: list[tuple[int, int]] = []
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    while len(regions) < max_regions:
        got = kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not got:
            break
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize or 0)
        prot = int(mbi.Protect)
        if mbi.State == MEM_COMMIT and size > 0 and (prot & 0xFF) in READABLE_RW:
            # Prefer heap-like private mid/high addresses; skip tiny and huge
            if 0x10000 <= size <= 64 * 1024 * 1024:
                regions.append((base, size))
        nxt = base + size
        if nxt <= addr:
            break
        addr = nxt
    # Prefer larger private-looking regions first (by size desc, then high addr)
    regions.sort(key=lambda r: (-min(r[1], 16 * 1024 * 1024), -r[0]))
    return regions


def world_like(v: float) -> bool:
    return math.isfinite(v) and 1.0 < abs(v) < 50000.0


def parse_vec3s_in_blob(
    blob: bytes,
    base_addr: int,
    player: Vec3,
    min_planar: float,
    max_planar: float,
    stride: int = 4,
) -> dict[int, Vec3]:
    found: dict[int, Vec3] = {}
    n = len(blob)
    # Need 12 bytes
    limit = n - 12
    i = 0
    while i <= limit:
        try:
            x, y, z = struct.unpack_from("<fff", blob, i)
        except struct.error:
            break
        if world_like(x) and world_like(y) and world_like(z):
            # Y elevation often 0..5000 in RIFT zones
            if -500.0 < y < 10000.0:
                vec = Vec3(x, y, z)
                d = vec.planar_dist(player)
                if min_planar <= d <= max_planar:
                    found[base_addr + i] = vec
        i += stride
    return found


def scan_near_player_world_vec3(
    h: int,
    player: Vec3,
    regions: list[tuple[int, int]],
    *,
    min_planar: float,
    max_planar: float,
    max_region_bytes: int,
    max_regions: int,
    stride: int,
) -> dict[int, Vec3]:
    hits: dict[int, Vec3] = {}
    for base, size in regions[:max_regions]:
        to_read = min(size, max_region_bytes)
        data = read_bytes(h, base, to_read)
        if not data:
            continue
        part = parse_vec3s_in_blob(data, base, player, min_planar, max_planar, stride=stride)
        hits.update(part)
        if len(hits) > 50000:
            break
    return hits


def capture_rrapicoord(repo: Path, pid: int, hwnd_hex: str, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ps1 = repo / "scripts" / "capture-rift-api-reference-coordinate.ps1"
    ref = out_dir / "reference.json"
    cmd = [
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
        "256",
        "-Json",
    ]
    proc = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=180)
    payload: dict[str, Any] = {
        "exitCode": proc.returncode,
        "stdoutTail": (proc.stdout or "")[-2000:],
        "stderrTail": (proc.stderr or "")[-1000:],
        "referencePath": str(ref) if ref.exists() else None,
    }
    if ref.exists():
        try:
            payload["reference"] = json.loads(ref.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            payload["referenceError"] = str(exc)
    return payload


def player_from_reference(ref: dict[str, Any] | None) -> Vec3 | None:
    if not ref:
        return None
    c = ref.get("coordinate") or ref.get("Coordinate")
    if isinstance(c, dict):
        try:
            return Vec3(float(c["x"] if "x" in c else c["X"]), float(c["y"] if "y" in c else c["Y"]), float(c["z"] if "z" in c else c["Z"]))
        except (KeyError, TypeError, ValueError):
            return None
    return None


def click_client(hwnd: int, x: int, y: int, hold_ms: int = 40) -> None:
    # Ensure client coords in range
    lparam = (int(y) << 16) | (int(x) & 0xFFFF)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    time.sleep(hold_ms / 1000.0)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)


def focus_window(hwnd: int) -> None:
    # Best-effort; may fail if elevated / foreground lock
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)


def score_candidates(
    baseline: dict[int, Vec3],
    after: dict[int, Vec3],
    player_before: Vec3,
    player_after: Vec3,
    *,
    min_change: float,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    addrs = set(baseline) | set(after)
    player_delta = player_before.planar_dist(player_after)
    for addr in addrs:
        b = baseline.get(addr)
        a = after.get(addr)
        if a is None:
            continue
        # Prefer values present after click
        score = 0
        reasons: list[str] = []
        dist_player = a.planar_dist(player_after)
        # Reject player-body and player-centered volumes (±40-style):
        # if after ≈ player, or after moves almost exactly with player, not a click goal.
        if dist_player < 2.0:
            score -= 5
            reasons.append("near-player-body")
        else:
            score += 1
            reasons.append("away-from-player")
        if b is not None:
            # How much did this vec track the player's motion?
            tracked = abs(
                (a.x - b.x) - (player_after.x - player_before.x)
            ) + abs((a.z - b.z) - (player_after.z - player_before.z))
            if player_delta >= 0.5 and tracked < 0.75:
                score -= 4
                reasons.append("tracks-player-motion")
        if b is None:
            score += 2
            reasons.append("new-after-click")
            change = None
        else:
            change = b.max_abs_delta(a)
            if change >= min_change:
                score += 3
                reasons.append(f"changed>={min_change}")
            else:
                score -= 1
                reasons.append("little-change")
        # Prefer mid-range destinations that stay fixed relative to goal space
        if 5.0 <= dist_player <= 60.0:
            score += 2
            reasons.append("plausible-c2m-range")
        elif dist_player > 60.0:
            score += 0
            reasons.append("far-goal")
        # Half-extent-40 cube corner signature (player±40 on all axes) is a known non-goal
        if (
            abs(abs(a.x - player_after.x) - 40.0) < 1.5
            and abs(abs(a.y - player_after.y) - 40.0) < 1.5
            and abs(abs(a.z - player_after.z) - 40.0) < 1.5
        ):
            score -= 6
            reasons.append("player-centered-pm40-volume-corner")
        ranked.append(
            {
                "addressHex": hex(addr),
                "address": addr,
                "after": a.as_dict(),
                "before": b.as_dict() if b else None,
                "planarDistToPlayerAfter": dist_player,
                "maxAbsChange": change,
                "score": score,
                "reasons": reasons,
            }
        )
    ranked.sort(key=lambda r: (-r["score"], r["planarDistToPlayerAfter"]))
    return ranked


def main() -> int:
    parser = argparse.ArgumentParser(description="Automated C2M destination discovery")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd", type=str)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--stimulus-approved",
        action="store_true",
        help="Required to send ground clicks. Without this, baseline-only dry discovery.",
    )
    parser.add_argument("--click-x-ratio", type=float, default=0.50, help="Client X fraction for ground click")
    parser.add_argument("--click-y-ratio", type=float, default=0.72, help="Client Y fraction (below center = ground)")
    parser.add_argument("--second-click", action="store_true", help="Second click at alternate screen point")
    parser.add_argument("--settle-ms", type=int, default=250)
    parser.add_argument("--min-planar", type=float, default=3.0)
    parser.add_argument("--max-planar", type=float, default=80.0)
    parser.add_argument("--max-regions", type=int, default=60)
    parser.add_argument("--max-region-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--stride", type=int, default=4)
    parser.add_argument("--min-change", type=float, default=0.5)
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo / "scripts" / "captures" / f"c2m-destination-discovery-{utc_stamp()}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "riftreader-c2m-destination-discovery",
        "generatedAtUtc": utc_now(),
        "status": "blocked",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "clickSent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "gitMutation": False,
            "currentTruthUpdated": False,
            "promotionPerformed": False,
        },
        "artifacts": {"runDirectory": str(run_dir)},
        "target": None,
        "stages": [],
    }

    targets = find_rift_targets()
    if not targets:
        summary["blockers"].append("no-rift-window")
        write_json(run_dir / "summary.json", summary)
        if args.json:
            print(json.dumps(summary, indent=2))
        return 2

    if len(targets) > 1 and (args.pid is None or args.hwnd is None):
        summary["blockers"].append("multiple-rift-windows-need-explicit-pid-hwnd")
        summary["targets"] = targets
        write_json(run_dir / "summary.json", summary)
        if args.json:
            print(json.dumps(summary, indent=2))
        return 2

    t = targets[0]
    if args.pid is not None:
        t = next((x for x in targets if x["pid"] == args.pid), None) or t
    if args.hwnd is not None:
        want = int(args.hwnd, 16) if str(args.hwnd).lower().startswith("0x") else int(args.hwnd)
        match = next((x for x in targets if x["hwnd"] == want), None)
        if match:
            t = match
        elif args.pid is not None and t["pid"] != args.pid:
            summary["blockers"].append("hwnd-pid-mismatch")
            write_json(run_dir / "summary.json", summary)
            if args.json:
                print(json.dumps(summary, indent=2))
            return 2

    summary["target"] = t
    if not args.execute:
        summary["status"] = "planned"
        summary["plan"] = {
            "steps": [
                "preflight-bind",
                "rrapicoord-api",
                "baseline-float-scan",
                "ground-click-if-stimulus-approved",
                "post-click-float-scan",
                "rank-diff-candidates",
            ],
            "stimulusApproved": bool(args.stimulus_approved),
        }
        write_json(run_dir / "summary.json", summary)
        if args.json:
            print(json.dumps(summary, indent=2))
        return 0

    # --- API ---
    api_dir = run_dir / "01-api"
    api = capture_rrapicoord(repo, t["pid"], t["hwndHex"], api_dir)
    summary["stages"].append({"label": "rrapicoord", "result": {"exitCode": api.get("exitCode"), "hasReference": bool(api.get("reference"))}})
    write_json(api_dir / "capture-envelope.json", {k: v for k, v in api.items() if k != "reference"})
    player = player_from_reference(api.get("reference"))
    if not player:
        # try nested from capture script style
        ref = api.get("reference") or {}
        if "coordinate" in ref:
            player = player_from_reference(ref)
    if not player:
        summary["blockers"].append("rrapicoord-player-unavailable")
        summary["api"] = {"rawKeys": list((api.get("reference") or {}).keys())}
        write_json(run_dir / "summary.json", summary)
        if args.json:
            print(json.dumps(summary, indent=2))
        return 2

    summary["playerBefore"] = player.as_dict()

    h = open_process(t["pid"])
    try:
        regions = enumerate_rw_regions(h)
        write_json(run_dir / "regions-top.json", [{"base": hex(b), "size": s} for b, s in regions[: args.max_regions]])

        # Include near-player body range too for rejection context (min_planar 0)
        baseline_near = scan_near_player_world_vec3(
            h,
            player,
            regions,
            min_planar=args.min_planar,
            max_planar=args.max_planar,
            max_region_bytes=args.max_region_bytes,
            max_regions=args.max_regions,
            stride=args.stride,
        )
        # Also capture very-near (body copies) for filtering only
        body_like = scan_near_player_world_vec3(
            h,
            player,
            regions,
            min_planar=0.0,
            max_planar=2.0,
            max_region_bytes=args.max_region_bytes,
            max_regions=min(20, args.max_regions),
            stride=args.stride,
        )
        write_json(
            run_dir / "02-baseline" / "hits.json",
            {
                "count": len(baseline_near),
                "bodyLikeCount": len(body_like),
                "sample": [{"addressHex": hex(a), **v.as_dict()} for a, v in list(baseline_near.items())[:50]],
            },
        )
        summary["stages"].append(
            {
                "label": "baseline-scan",
                "hitCount": len(baseline_near),
                "bodyLikeCount": len(body_like),
            }
        )

        clicks: list[dict[str, Any]] = []
        if not args.stimulus_approved:
            summary["blockers"].append("stimulus-not-approved-baseline-only")
            summary["status"] = "blocked"
            summary["baselineOnly"] = True
            summary["baselineHitCount"] = len(baseline_near)
            write_json(run_dir / "summary.json", summary)
            if args.json:
                print(json.dumps(summary, indent=2))
            return 2

        # --- click 1 ---
        focus_window(t["hwnd"])
        cx = max(2, min(t["clientWidth"] - 3, int(t["clientWidth"] * args.click_x_ratio)))
        cy = max(2, min(t["clientHeight"] - 3, int(t["clientHeight"] * args.click_y_ratio)))
        click_client(t["hwnd"], cx, cy)
        summary["safety"]["inputSent"] = True
        summary["safety"]["clickSent"] = True
        clicks.append({"index": 1, "clientX": cx, "clientY": cy, "atUtc": utc_now()})
        time.sleep(args.settle_ms / 1000.0)

        api2 = capture_rrapicoord(repo, t["pid"], t["hwndHex"], run_dir / "03-api-after-click1")
        player2 = player_from_reference(api2.get("reference")) or player
        summary["playerAfterClick1"] = player2.as_dict()
        summary["playerPlanarDeltaClick1"] = player.planar_dist(player2)

        after1 = scan_near_player_world_vec3(
            h,
            player2,
            regions,
            min_planar=args.min_planar,
            max_planar=args.max_planar,
            max_region_bytes=args.max_region_bytes,
            max_regions=args.max_regions,
            stride=args.stride,
        )
        ranked1 = score_candidates(baseline_near, after1, player, player2, min_change=args.min_change)
        # Drop pure body addresses
        body_addrs = set(body_like)
        ranked1 = [r for r in ranked1 if r["address"] not in body_addrs]
        write_json(run_dir / "04-after-click1" / "ranked.json", ranked1[: args.top_n * 4])
        summary["stages"].append({"label": "after-click1-scan", "hitCount": len(after1), "ranked": len(ranked1)})

        ranked_final = ranked1
        if args.second_click:
            cx2 = max(2, min(t["clientWidth"] - 3, int(t["clientWidth"] * 0.35)))
            cy2 = max(2, min(t["clientHeight"] - 3, int(t["clientHeight"] * 0.68)))
            click_client(t["hwnd"], cx2, cy2)
            clicks.append({"index": 2, "clientX": cx2, "clientY": cy2, "atUtc": utc_now()})
            time.sleep(args.settle_ms / 1000.0)
            api3 = capture_rrapicoord(repo, t["pid"], t["hwndHex"], run_dir / "05-api-after-click2")
            player3 = player_from_reference(api3.get("reference")) or player2
            after2 = scan_near_player_world_vec3(
                h,
                player3,
                regions,
                min_planar=args.min_planar,
                max_planar=args.max_planar,
                max_region_bytes=args.max_region_bytes,
                max_regions=args.max_regions,
                stride=args.stride,
            )
            # Boost candidates that changed again between click1 and click2
            boost: list[dict[str, Any]] = []
            after1_map = {r["address"]: r for r in ranked1}
            for addr, vec in after2.items():
                if addr in body_addrs:
                    continue
                prev = after1.get(addr)
                if prev is None:
                    continue
                ch = prev.max_abs_delta(vec)
                if ch < args.min_change:
                    continue
                base = after1_map.get(addr, {
                    "address": addr,
                    "addressHex": hex(addr),
                    "score": 0,
                    "reasons": [],
                    "after": prev.as_dict(),
                })
                item = dict(base)
                item["afterClick2"] = vec.as_dict()
                item["changeClick1to2"] = ch
                item["score"] = int(item.get("score", 0)) + 4
                item["reasons"] = list(item.get("reasons") or []) + ["updated-on-second-click"]
                item["planarDistToPlayerAfter"] = vec.planar_dist(player3)
                boost.append(item)
            boost.sort(key=lambda r: (-r["score"], r.get("planarDistToPlayerAfter") or 0))
            ranked_final = boost if boost else ranked1
            write_json(run_dir / "06-after-click2" / "ranked.json", ranked_final[: args.top_n * 4])
            summary["stages"].append({"label": "after-click2-scan", "boosted": len(boost)})

        top = ranked_final[: args.top_n]
        write_json(run_dir / "candidates-top.json", top)
        summary["clicks"] = clicks
        summary["topCandidates"] = top
        summary["candidateCount"] = len(ranked_final)
        if top and top[0]["score"] >= 3:
            summary["status"] = "passed"
            summary["verdict"] = "c2m-destination-session-candidates-found"
        elif top:
            summary["status"] = "passed"
            summary["verdict"] = "weak-c2m-destination-candidates"
            summary["warnings"].append("top-score-low-manual-review")
        else:
            summary["status"] = "blocked"
            summary["blockers"].append("no-c2m-destination-candidates")
            summary["verdict"] = "no-candidates"
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    finally:
        kernel32.CloseHandle(h)

    summary["completedAtUtc"] = utc_now()
    write_json(run_dir / "summary.json", summary)
    md = [
        f"# C2M destination discovery",
        "",
        f"- status: `{summary.get('status')}`",
        f"- verdict: `{summary.get('verdict')}`",
        f"- pid/hwnd: `{t['pid']}` / `{t['hwndHex']}`",
        f"- clicks: `{len(summary.get('clicks') or [])}`",
        f"- top candidates: `{len(summary.get('topCandidates') or [])}`",
        "",
    ]
    for c in (summary.get("topCandidates") or [])[:10]:
        md.append(
            f"- `{c.get('addressHex')}` score={c.get('score')} "
            f"dist={c.get('planarDistToPlayerAfter'):.2f} after={c.get('after')}"
        )
    (run_dir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    summary["artifacts"]["summaryJson"] = str(run_dir / "summary.json")
    summary["artifacts"]["summaryMarkdown"] = str(run_dir / "summary.md")
    write_json(run_dir / "summary.json", summary)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(summary.get("status"), summary.get("verdict"), run_dir)

    if summary["status"] == "failed":
        return 1
    if summary["status"] == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
