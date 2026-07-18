#!/usr/bin/env python3
"""Targeted C2M volume probe: read AABB A/B before/after one ground click.

Expect: if A/B encode a move volume, center jumps on click while player is still
near the pre-click position (brief window), then player walks toward center.

Requires --stimulus-approved for the click. No CE/x64dbg/promotion.
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


def read_f32(h: int, addr: int) -> float | None:
    buf = ctypes.create_string_buffer(4)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, 4, ctypes.byref(br))
    if not ok or br.value != 4:
        return None
    return struct.unpack("<f", buf.raw)[0]


def read_vec3(h: int, addr: int) -> dict[str, float] | None:
    x, y, z = read_f32(h, addr), read_f32(h, addr + 4), read_f32(h, addr + 8)
    if x is None or y is None or z is None:
        return None
    return {"x": x, "y": y, "z": z}


def read_volume(h: int, base: int) -> dict[str, Any] | None:
    a = read_vec3(h, base)
    b = read_vec3(h, base + 0x10)
    if not a or not b:
        return None
    center = {
        "x": (a["x"] + b["x"]) / 2.0,
        "y": (a["y"] + b["y"]) / 2.0,
        "z": (a["z"] + b["z"]) / 2.0,
    }
    extent = {
        "x": b["x"] - a["x"],
        "y": b["y"] - a["y"],
        "z": b["z"] - a["z"],
    }
    return {"A": a, "B": b, "center": center, "extent": extent, "baseHex": hex(base)}


def planar(a: dict[str, float], b: dict[str, float]) -> float:
    return math.hypot(a["x"] - b["x"], a["z"] - b["z"])


def max_abs_vec(a: dict[str, float], b: dict[str, float]) -> float:
    return max(abs(a["x"] - b["x"]), abs(a["y"] - b["y"]), abs(a["z"] - b["z"]))


def _coord_from_obj(data: dict[str, Any]) -> dict[str, float] | None:
    c = data.get("coordinate") or data.get("Coordinate")
    if not isinstance(c, dict):
        return None
    try:
        return {
            "x": float(c.get("x", c.get("X"))),
            "y": float(c.get("y", c.get("Y"))),
            "z": float(c.get("z", c.get("Z"))),
        }
    except (TypeError, ValueError):
        return None


def capture_api(repo: Path, pid: int, hwnd_hex: str, out_dir: Path) -> dict[str, float] | None:
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
    # Prefer written reference.json
    if ref.exists():
        try:
            got = _coord_from_obj(json.loads(ref.read_text(encoding="utf-8")))
            if got:
                return got
        except json.JSONDecodeError:
            pass
    # Parse stdout JSON if present
    out = proc.stdout or ""
    if "{" in out:
        try:
            start = out.index("{")
            end = out.rindex("}") + 1
            got = _coord_from_obj(json.loads(out[start:end]))
            if got:
                return got
            # nested Coordinate casing from capture script
            payload = json.loads(out[start:end])
            if "Coordinate" in payload:
                c = payload["Coordinate"]
                return {"x": float(c["X"]), "y": float(c["Y"]), "z": float(c["Z"])}
        except (ValueError, json.JSONDecodeError, KeyError, TypeError):
            pass
    # Last resort: any reference*.json under out_dir
    for p in sorted(out_dir.glob("**/*reference*.json"), reverse=True):
        try:
            got = _coord_from_obj(json.loads(p.read_text(encoding="utf-8")))
            if got:
                return got
        except (json.JSONDecodeError, OSError):
            continue
    return None


def click_client(hwnd: int, x: int, y: int, hold_ms: int = 40) -> None:
    lparam = (int(y) << 16) | (int(x) & 0xFFFF)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.12)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    time.sleep(hold_ms / 1000.0)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)


def sample_loop(
    h: int,
    bases: list[int],
    duration_ms: int,
    interval_ms: int,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    end = time.time() + duration_ms / 1000.0
    while time.time() < end:
        row: dict[str, Any] = {"tUtc": utc_now(), "volumes": {}}
        for base in bases:
            vol = read_volume(h, base)
            if vol:
                row["volumes"][hex(base)] = vol
        samples.append(row)
        time.sleep(interval_ms / 1000.0)
    return samples


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument(
        "--bases",
        default="0x174041f89f0,0x174004fefa0",
        help="Comma-separated volume bases (A at +0, B at +0x10)",
    )
    ap.add_argument("--stimulus-approved", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--click-x-ratio", type=float, default=0.62)
    ap.add_argument("--click-y-ratio", type=float, default=0.78)
    ap.add_argument("--post-sample-ms", type=int, default=2500)
    ap.add_argument("--sample-interval-ms", type=int, default=100)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    run_dir = repo / "scripts" / "captures" / f"c2m-volume-click-probe-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "riftreader-c2m-volume-click-probe",
        "generatedAtUtc": utc_now(),
        "status": "blocked",
        "blockers": [],
        "warnings": [],
        "safety": {
            "inputSent": False,
            "clickSent": False,
            "movementSent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "targetMemoryBytesWritten": False,
            "promotionPerformed": False,
        },
        "artifacts": {"runDirectory": str(run_dir)},
    }

    if not args.execute:
        summary["status"] = "planned"
        write_json(run_dir / "summary.json", summary)
        if args.json:
            print(json.dumps(summary, indent=2))
        return 0

    t = find_target()
    if not t:
        summary["blockers"].append("no-rift")
        write_json(run_dir / "summary.json", summary)
        return 2
    summary["target"] = t

    bases = [int(x.strip(), 16) if x.strip().lower().startswith("0x") else int(x.strip()) for x in args.bases.split(",") if x.strip()]
    summary["bases"] = [hex(b) for b in bases]

    # Volume first (session seed). API is best-effort; click test can still run.
    h = open_process(t["pid"])
    try:
        before = {hex(b): read_volume(h, b) for b in bases}
        summary["volumeBefore"] = before
        primary = before.get(hex(bases[0]))
        if not primary:
            summary["blockers"].append("primary-volume-unreadable-address-may-be-stale")
            write_json(run_dir / "summary.json", summary)
            if args.json:
                print(json.dumps(summary, indent=2))
            return 2

        player0 = capture_api(repo, t["pid"], t["hwndHex"], run_dir / "api-before")
        summary["playerBefore"] = player0
        if not player0:
            summary["warnings"].append("api-before-failed-continuing-volume-only")
        else:
            summary["centerMinusPlayerBefore"] = {
                "planar": planar(primary["center"], player0),
                "maxAbs": max_abs_vec(primary["center"], player0),
            }

        if not args.stimulus_approved:
            summary["blockers"].append("stimulus-not-approved")
            summary["status"] = "blocked"
            write_json(run_dir / "summary.json", summary)
            return 2

        cx = max(2, min(t["clientWidth"] - 3, int(t["clientWidth"] * args.click_x_ratio)))
        cy = max(2, min(t["clientHeight"] - 3, int(t["clientHeight"] * args.click_y_ratio)))
        click_client(t["hwnd"], cx, cy)
        summary["safety"]["inputSent"] = True
        summary["safety"]["clickSent"] = True
        summary["click"] = {"clientX": cx, "clientY": cy, "atUtc": utc_now()}

        # Immediate samples without waiting for API (API is slow)
        t0 = time.time()
        immediate = []
        for i in range(8):
            row = {"dtMs": int((time.time() - t0) * 1000), "volumes": {}}
            for b in bases:
                vol = read_volume(h, b)
                if vol:
                    row["volumes"][hex(b)] = vol
            immediate.append(row)
            time.sleep(0.03)

        samples = sample_loop(h, bases, args.post_sample_ms, args.sample_interval_ms)
        summary["immediateSamples"] = immediate
        summary["timedSamples"] = samples

        # First changed sample vs before
        primary_hex = hex(bases[0])
        first_change = None
        for row in immediate + samples:
            vol = (row.get("volumes") or {}).get(primary_hex)
            if not vol:
                continue
            d = max_abs_vec(vol["center"], primary["center"])
            if d >= 0.5:
                first_change = {
                    "dtMs": row.get("dtMs"),
                    "tUtc": row.get("tUtc"),
                    "centerDeltaMaxAbs": d,
                    "volume": vol,
                }
                break

        summary["firstCenterChange"] = first_change

        player1 = capture_api(repo, t["pid"], t["hwndHex"], run_dir / "api-after-burst")
        summary["playerAfterBurst"] = player1
        vol_now = read_volume(h, bases[0])
        summary["volumeAfterBurst"] = vol_now
        if player0 and player1:
            summary["playerPlanarDelta"] = planar(player0, player1)
        if player1 and vol_now:
            summary["centerMinusPlayerAfter"] = {
                "planar": planar(vol_now["center"], player1),
                "maxAbs": max_abs_vec(vol_now["center"], player1),
            }

        # Verdict
        vol_changed = first_change is not None
        player_delta = float(summary.get("playerPlanarDelta") or 0.0)
        if vol_changed and (player0 is None or player_delta < 1.0):
            summary["status"] = "passed"
            summary["verdict"] = (
                "volume-center-jumped-before-significant-player-move"
                if player0 is not None
                else "volume-center-jumped-on-click-api-partial"
            )
        elif vol_changed and player_delta >= 1.0:
            summary["status"] = "passed"
            summary["verdict"] = "volume-changed-and-player-also-moved"
            summary["warnings"].append("player-already-moving-ambiguous-ordering")
        elif not vol_changed and player_delta >= 1.0:
            summary["status"] = "blocked"
            summary["verdict"] = "player-moved-volume-frozen-not-c2m-goal-or-stale-address"
            summary["blockers"].append("volume-did-not-change-on-click")
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "no-volume-change-no-player-move-click-may-have-missed"
            summary["blockers"].append("no-effect-observed")
    finally:
        kernel32.CloseHandle(h)

    write_json(run_dir / "summary.json", summary)
    md = [
        "# C2M volume click probe",
        "",
        f"- status: `{summary.get('status')}`",
        f"- verdict: `{summary.get('verdict')}`",
        f"- click: `{summary.get('click')}`",
        f"- player planar delta: `{summary.get('playerPlanarDelta')}`",
        f"- first center change: `{summary.get('firstCenterChange')}`",
        f"- center-player before: `{summary.get('centerMinusPlayerBefore')}`",
        f"- center-player after: `{summary.get('centerMinusPlayerAfter')}`",
        "",
    ]
    (run_dir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if args.json:
        # compact print for console
        compact = {
            "status": summary.get("status"),
            "verdict": summary.get("verdict"),
            "blockers": summary.get("blockers"),
            "playerBefore": summary.get("playerBefore"),
            "playerAfterBurst": summary.get("playerAfterBurst"),
            "playerPlanarDelta": summary.get("playerPlanarDelta"),
            "centerMinusPlayerBefore": summary.get("centerMinusPlayerBefore"),
            "centerMinusPlayerAfter": summary.get("centerMinusPlayerAfter"),
            "firstCenterChange": summary.get("firstCenterChange"),
            "volumeBeforePrimary": (summary.get("volumeBefore") or {}).get(hex(bases[0])),
            "volumeAfterBurst": summary.get("volumeAfterBurst"),
            "click": summary.get("click"),
            "runDirectory": str(run_dir),
            "safety": summary.get("safety"),
        }
        print(json.dumps(compact, indent=2))
    else:
        print(summary.get("status"), summary.get("verdict"), run_dir)
    return 0 if summary.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
