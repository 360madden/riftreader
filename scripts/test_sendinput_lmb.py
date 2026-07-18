#!/usr/bin/env python3
"""Test C# SendInput left-click against live RIFT (focus required).

Measures: tool ok/focus, optional player planar displacement via RRAPICOORD.
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


def capture_api(repo: Path, pid: int, hwnd_hex: str, out_dir: Path, tag: str) -> dict[str, Any]:
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
    coord = None
    if "{" in blob:
        try:
            start = blob.index("{")
            end = blob.rindex("}") + 1
            payload = json.loads(blob[start:end])
            c = payload.get("Coordinate") or payload.get("coordinate")
            if isinstance(c, dict):
                if "X" in c:
                    coord = {"x": float(c["X"]), "y": float(c["Y"]), "z": float(c["Z"])}
                else:
                    coord = {"x": float(c["x"]), "y": float(c["y"]), "z": float(c["z"])}
            rf = payload.get("ReferenceFile")
            if coord is None and rf and Path(rf).exists():
                data = json.loads(Path(rf).read_text(encoding="utf-8"))
                c2 = data.get("coordinate") or data.get("Coordinate") or {}
                if "x" in c2 or "X" in c2:
                    coord = {
                        "x": float(c2.get("x", c2.get("X"))),
                        "y": float(c2.get("y", c2.get("Y"))),
                        "z": float(c2.get("z", c2.get("Z"))),
                    }
        except (ValueError, json.JSONDecodeError, KeyError, TypeError):
            pass
    return {"coord": coord, "exitCode": proc.returncode}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--client-x", type=int)
    ap.add_argument("--client-y", type=int)
    ap.add_argument("--hold-ms", type=int, default=50)
    ap.add_argument("--focus-delay-ms", type=int, default=700)
    ap.add_argument("--wait-after-ms", type=int, default=1500)
    ap.add_argument("--skip-api", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = repo / "scripts" / "captures" / f"sendinput-lmb-test-{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    t = find_target()
    if not t:
        summary = {"status": "blocked", "blockers": ["no-rift"], "artifacts": {"runDirectory": str(out)}}
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 2

    w, h = t["clientWidth"], t["clientHeight"]
    # Default: true client-center only (safe inset; never chrome / lower-edge guesswork)
    cx = args.client_x if args.client_x is not None else max(8, w // 2)
    cy = args.client_y if args.client_y is not None else max(8, h // 2)
    margin = 8
    if cx < margin or cy < margin or cx >= w - margin or cy >= h - margin:
        raise SystemExit(
            f"refusing unsafe click ({cx},{cy}) outside client inset of {w}x{h}"
        )

    # Snapshot client size before focus/click to detect accidental un-maximize
    size_before = {"w": w, "h": h}

    before = None if args.skip_api else capture_api(repo, t["pid"], t["hwndHex"], out, "before")

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
        str(t["pid"]),
        "--hwnd",
        t["hwndHex"],
        "--client-x",
        str(cx),
        "--client-y",
        str(cy),
        "--hold-ms",
        str(args.hold_ms),
        "--focus-delay-ms",
        str(args.focus_delay_ms),
        "--json",
    ]
    t0 = time.time()
    click = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=60)
    click_ms = int((time.time() - t0) * 1000)

    # Re-read client size after focus path
    t2 = find_target()
    size_after = (
        {"w": t2["clientWidth"], "h": t2["clientHeight"]}
        if t2
        else None
    )
    click_out = (click.stdout or "") + "\n" + (click.stderr or "")
    click_json = None
    if "{" in click_out:
        try:
            start = click_out.index("{")
            end = click_out.rindex("}") + 1
            click_json = json.loads(click_out[start:end])
        except (ValueError, json.JSONDecodeError):
            click_json = None

    if not args.skip_api:
        time.sleep(args.wait_after_ms / 1000.0)
    after = None if args.skip_api else capture_api(repo, t["pid"], t["hwndHex"], out, "after")

    bc = (before or {}).get("coord")
    ac = (after or {}).get("coord")
    delta = None
    if bc and ac:
        delta = math.hypot(bc["x"] - ac["x"], bc["z"] - ac["z"])

    send_ok = bool(click_json and click_json.get("ok") is True and click_json.get("status") == "sent")
    focus = (click_json or {}).get("focus") or {}
    focus_ok = bool(focus.get("TargetProcessForeground"))
    exact_hwnd = bool(focus.get("ExactHwndForeground"))
    post_msg = bool(((click_json or {}).get("safety") or {}).get("postMessageMouseUsed"))
    moved = delta is not None and delta >= 0.35

    if not send_ok:
        status, verdict = "failed", "sendinput-lmb-failed"
    elif not focus_ok:
        status, verdict = "failed", "sendinput-lmb-sent-but-not-foreground"
    elif args.skip_api:
        status, verdict = "passed", "sendinput-lmb-sent-focus-ok-api-skipped"
    elif moved:
        status, verdict = "passed", "sendinput-lmb-sent-and-player-displaced"
    else:
        # Tool path worked; game may not treat click as C2M (mode/UI)
        status, verdict = "passed", "sendinput-lmb-sent-no-player-displacement"

    size_changed = bool(
        size_after
        and (size_after["w"] != size_before["w"] or size_after["h"] != size_before["h"])
    )
    focus_meta = (click_json or {}).get("focus") or {}

    summary = {
        "schemaVersion": 1,
        "kind": "riftreader-sendinput-lmb-test",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "verdict": verdict,
        "target": t,
        "click": {
            "clientX": cx,
            "clientY": cy,
            "holdMs": args.hold_ms,
            "focusDelayMs": args.focus_delay_ms,
            "durationMs": click_ms,
            "note": "client-center-only-safe-inset",
        },
        "clientSizeBefore": size_before,
        "clientSizeAfter": size_after,
        "clientSizeChanged": size_changed,
        "sendInputExitCode": click.returncode,
        "sendInput": click_json,
        "sendInputStdoutTail": click_out[-1200:],
        "before": before,
        "after": after,
        "playerPlanarDelta": delta,
        "checks": {
            "sendInputOk": send_ok,
            "focusForeground": focus_ok,
            "exactHwndForeground": exact_hwnd,
            "postMessageMouseUsed": post_msg,
            "playerDisplaced": moved,
            "clientSizeUnchanged": not size_changed,
            "usedShowRestore": focus_meta.get("UsedShowRestore"),
            "wasZoomed": focus_meta.get("WasZoomed"),
            "wasIconic": focus_meta.get("WasIconic"),
            "backend": ((click_json or {}).get("mouse") or {}).get("backend"),
        },
        "safety": {
            "inputSent": send_ok,
            "clickSent": send_ok,
            "backend": "RiftReader.SendInput",
            "postMessageMouseUsed": False,
            "requiresForeground": True,
            "noCheatEngine": True,
        },
        "artifacts": {"runDirectory": str(out), "summaryJson": str(out / "summary.json")},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
