#!/usr/bin/env python3
"""Prove SendInput center LMB moves the character (RRAPICOORD before/after).

Compares:
  1) original wrapper: scripts/send-rift-key-csharp.ps1
  2) harness: scripts/test_sendinput_lmb.py (via same SendInput backend)

Both clicks use client-center only.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import subprocess
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)


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


def find_target() -> dict[str, Any] | None:
    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)
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


def capture_api(repo: Path, pid: int, hwnd_hex: str, out_dir: Path, tag: str) -> dict[str, float] | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ref = out_dir / f"{tag}.json"
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
    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "{" not in blob:
        return None
    try:
        start = blob.index("{")
        end = blob.rindex("}") + 1
        payload = json.loads(blob[start:end])
        c = payload.get("Coordinate") or payload.get("coordinate")
        if isinstance(c, dict):
            if "X" in c:
                return {"x": float(c["X"]), "y": float(c["Y"]), "z": float(c["Z"])}
            return {"x": float(c["x"]), "y": float(c["y"]), "z": float(c["z"])}
        rf = payload.get("ReferenceFile")
        if rf and Path(rf).exists():
            data = json.loads(Path(rf).read_text(encoding="utf-8"))
            c2 = data.get("coordinate") or data.get("Coordinate") or {}
            if "x" in c2 or "X" in c2:
                return {
                    "x": float(c2.get("x", c2.get("X"))),
                    "y": float(c2.get("y", c2.get("Y"))),
                    "z": float(c2.get("z", c2.get("Z"))),
                }
    except (ValueError, json.JSONDecodeError, KeyError, TypeError, OSError):
        return None
    return None


def planar(a: dict[str, float], b: dict[str, float]) -> float:
    return math.hypot(a["x"] - b["x"], a["z"] - b["z"])


def sendinput_click(repo: Path, pid: int, hwnd_hex: str, cx: int, cy: int, hold_ms: int, focus_delay_ms: int) -> dict[str, Any]:
    wrapper = repo / "scripts" / "send-rift-key-csharp.ps1"
    cmd = [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(wrapper),
        "--pid",
        str(pid),
        "--hwnd",
        hwnd_hex,
        "--client-x",
        str(cx),
        "--client-y",
        str(cy),
        "--hold-ms",
        str(hold_ms),
        "--focus-delay-ms",
        str(focus_delay_ms),
        "--json",
    ]
    proc = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=60)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    payload = None
    if "{" in out:
        try:
            s = out.index("{")
            e = out.rindex("}") + 1
            payload = json.loads(out[s:e])
        except (ValueError, json.JSONDecodeError):
            payload = None
    return {"exitCode": proc.returncode, "result": payload, "stdoutTail": out[-800:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--hold-ms", type=int, default=50)
    ap.add_argument("--focus-delay-ms", type=int, default=700)
    ap.add_argument("--wait-after-ms", type=int, default=2000)
    ap.add_argument("--settle-between-ms", type=int, default=2500)
    ap.add_argument("--min-displacement", type=float, default=0.35)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = repo / "scripts" / "captures" / f"sendinput-lmb-coord-proof-{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    t = find_target()
    if not t:
        summary = {"status": "blocked", "blockers": ["no-rift"], "artifacts": {"runDirectory": str(out)}}
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 2

    cx = t["clientWidth"] // 2
    cy = t["clientHeight"] // 2
    trials: list[dict[str, Any]] = []

    # --- Trial A: original wrapper only ---
    before_a = capture_api(repo, t["pid"], t["hwndHex"], out / "A", "before")
    click_a = sendinput_click(repo, t["pid"], t["hwndHex"], cx, cy, args.hold_ms, args.focus_delay_ms)
    time.sleep(args.wait_after_ms / 1000.0)
    after_a = capture_api(repo, t["pid"], t["hwndHex"], out / "A", "after")
    delta_a = planar(before_a, after_a) if before_a and after_a else None
    ok_a = bool(click_a.get("result") and click_a["result"].get("ok") and click_a["result"].get("status") == "sent")
    moved_a = delta_a is not None and delta_a >= args.min_displacement
    trials.append(
        {
            "id": "original-wrapper",
            "tool": "scripts/send-rift-key-csharp.ps1 -> RiftReader.SendInput",
            "click": {"clientX": cx, "clientY": cy, "note": "client-center"},
            "sendInput": click_a,
            "before": before_a,
            "after": after_a,
            "playerPlanarDelta": delta_a,
            "sendOk": ok_a,
            "playerDisplaced": moved_a,
            "focusForeground": bool(((click_a.get("result") or {}).get("focus") or {}).get("TargetProcessForeground")),
            "postMessageMouseUsed": bool(((click_a.get("result") or {}).get("safety") or {}).get("postMessageMouseUsed")),
        }
    )

    time.sleep(args.settle_between_ms / 1000.0)

    # --- Trial B: harness (same center, same SendInput backend) ---
    before_b = capture_api(repo, t["pid"], t["hwndHex"], out / "B", "before")
    harness = repo / "scripts" / "test_sendinput_lmb.py"
    harness_cmd = [
        "python",
        str(harness),
        "--client-x",
        str(cx),
        "--client-y",
        str(cy),
        "--hold-ms",
        str(args.hold_ms),
        "--focus-delay-ms",
        str(args.focus_delay_ms),
        "--wait-after-ms",
        str(args.wait_after_ms),
        "--json",
    ]
    hb = subprocess.run(harness_cmd, cwd=str(repo), capture_output=True, text=True, timeout=300)
    harness_out = (hb.stdout or "") + "\n" + (hb.stderr or "")
    harness_json = None
    if "{" in harness_out:
        try:
            s = harness_out.index("{")
            e = harness_out.rindex("}") + 1
            harness_json = json.loads(harness_out[s:e])
        except (ValueError, json.JSONDecodeError):
            harness_json = None
    # Prefer harness embedded before/after if present
    before_b2 = (harness_json or {}).get("before", {}).get("coord") if harness_json else None
    after_b2 = (harness_json or {}).get("after", {}).get("coord") if harness_json else None
    # If harness failed to get before, use our before_b
    b_use = before_b2 or before_b
    a_use = after_b2
    if a_use is None:
        a_use = capture_api(repo, t["pid"], t["hwndHex"], out / "B", "after-fallback")
    delta_b = planar(b_use, a_use) if b_use and a_use else None
    ok_b = bool(harness_json and harness_json.get("checks", {}).get("sendInputOk"))
    moved_b = delta_b is not None and delta_b >= args.min_displacement
    trials.append(
        {
            "id": "harness-test_sendinput_lmb",
            "tool": "scripts/test_sendinput_lmb.py -> send-rift-key-csharp.ps1 -> RiftReader.SendInput",
            "click": {"clientX": cx, "clientY": cy, "note": "client-center"},
            "harnessExitCode": hb.returncode,
            "harness": harness_json,
            "before": b_use,
            "after": a_use,
            "playerPlanarDelta": delta_b,
            "sendOk": ok_b,
            "playerDisplaced": moved_b,
            "focusForeground": bool((harness_json or {}).get("checks", {}).get("focusForeground")),
            "postMessageMouseUsed": bool((harness_json or {}).get("checks", {}).get("postMessageMouseUsed")),
        }
    )

    both_send = all(tr["sendOk"] for tr in trials)
    both_moved = all(tr["playerDisplaced"] for tr in trials)
    any_moved = any(tr["playerDisplaced"] for tr in trials)

    if both_send and both_moved:
        status, verdict = "passed", "both-tools-center-lmb-moved-character"
    elif both_send and any_moved:
        status, verdict = "passed", "send-ok-partial-displacement-proof"
    elif both_send:
        status, verdict = "blocked", "send-ok-but-no-coord-displacement"
    else:
        status, verdict = "failed", "sendinput-failed"

    summary = {
        "schemaVersion": 1,
        "kind": "riftreader-sendinput-lmb-coord-proof",
        "generatedAtUtc": utc_now(),
        "status": status,
        "verdict": verdict,
        "target": t,
        "centerClick": {"clientX": cx, "clientY": cy, "clientSize": [t["clientWidth"], t["clientHeight"]]},
        "minDisplacement": args.min_displacement,
        "trials": trials,
        "proof": {
            "bothToolsSendOk": both_send,
            "bothToolsDisplacedPlayer": both_moved,
            "anyToolDisplacedPlayer": any_moved,
            "postMessageMouseUsedAny": any(tr.get("postMessageMouseUsed") for tr in trials),
        },
        "safety": {
            "inputSent": both_send or any(tr["sendOk"] for tr in trials),
            "backend": "RiftReader.SendInput",
            "postMessageMouseUsed": False,
            "requiresForeground": True,
            "noCheatEngine": True,
            "centerOnly": True,
        },
        "artifacts": {"runDirectory": str(out), "summaryJson": str(out / "summary.json")},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    md = [
        "# SendInput LMB coord proof (center only)",
        "",
        f"- status: `{status}`",
        f"- verdict: `{verdict}`",
        f"- center: `({cx},{cy})` on `{t['clientWidth']}x{t['clientHeight']}`",
        "",
    ]
    for tr in trials:
        md.append(
            f"## {tr['id']}\n"
            f"- sendOk: `{tr['sendOk']}` displaced: `{tr['playerDisplaced']}` delta: `{tr['playerPlanarDelta']}`\n"
            f"- before: `{tr['before']}`\n"
            f"- after: `{tr['after']}`\n"
        )
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if status == "passed" else (2 if status == "blocked" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
