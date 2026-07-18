#!/usr/bin/env python3
"""In-game C2M + SendInput clicks + arrival via static chain and/or RRAPICOORD.

Aim modes:
  w2s      — project world goal through reseeded camera (root 0x32E07C0)
  center   — client-center aim with small lateral bias only (no toolbar band)
  heuristic— motion-bearing bias with safe mid-client Y (never ~0.82 toolbar)

Pose sources:
  static-chain — [rift_x64+rootRva]+0x320 (default when current-truth / root works)
  rrapicoord   — fast string scan / API capture
  auto         — static first, RRAPICOORD fallback

Safety:
  --stimulus-approved required for clicks
  exact one RIFT window
  no CE/x64dbg/promotion/truth writes from this helper
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

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001


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


_RR_CACHE: dict[str, Any] = {"pid": None, "addr": None, "handle": None}
DEFAULT_ROOT_RVA = 0x32E07C0
DEFAULT_COORD_OFFSET = 0x320
DEFAULT_CAMERA_CHILD_OFFSET = 0x330


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


def _parse_rrapicoord_text(text: str) -> dict[str, float] | None:
    # RRAPICOORD1|...|status=pass|x=1|y=2|z=3|...
    if "RRAPICOORD1" not in text or "status=pass" not in text:
        return None
    # take last usable marker in blob
    best = None
    for part in text.split("RRAPICOORD1"):
        if "status=pass" not in part or "x=" not in part:
            continue
        fields = {}
        for tok in part.split("|"):
            if "=" in tok:
                k, v = tok.split("=", 1)
                fields[k.strip()] = v.strip()
        try:
            if fields.get("status") == "pass":
                best = {
                    "x": float(fields["x"]),
                    "y": float(fields["y"]),
                    "z": float(fields["z"]),
                    "seq": fields.get("seq"),
                }
        except (KeyError, ValueError):
            continue
    return best


def _open_process(pid: int) -> int:
    h = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        raise OSError(ctypes.get_last_error())
    return int(h)


def _read_bytes(h: int, addr: int, n: int) -> bytes | None:
    buf = ctypes.create_string_buffer(n)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(br))
    if not ok or br.value != n:
        return None
    return buf.raw


def scan_rrapicoord_fast(pid: int, max_regions: int = 120, chunk: int = 2 * 1024 * 1024) -> dict[str, float] | None:
    """In-process RRAPICOORD scan; caches last hit address for fast re-read."""
    needle = b"RRAPICOORD1|"
    h = _RR_CACHE.get("handle")
    if _RR_CACHE.get("pid") != pid or not h:
        if h:
            try:
                kernel32.CloseHandle(h)
            except Exception:
                pass
        h = _open_process(pid)
        _RR_CACHE["pid"] = pid
        _RR_CACHE["handle"] = h
        _RR_CACHE["addr"] = None

    # Fast path: re-read cached string page (and nearby for newer copies)
    cached = _RR_CACHE.get("addr")
    if cached:
        for off in (0, -0x1000, 0x1000, -0x10000, 0x10000):
            start = max(0, int(cached) + off - 64)
            data = _read_bytes(h, start, 2048)
            if not data:
                continue
            text = data.decode("latin1", errors="ignore")
            got = _parse_rrapicoord_text(text)
            if got:
                return got
        _RR_CACHE["addr"] = None

    # Scan committed readable regions in chunks (full region, not only first 4MB)
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    scanned = 0
    best: dict[str, float] | None = None
    best_seq = -1
    best_addr = None
    while scanned < max_regions:
        if not kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize or 0)
        prot = int(mbi.Protect) & 0xFF
        if mbi.State == MEM_COMMIT and prot in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80) and size > 0x1000:
            # skip huge mapped images > 128MB
            if size <= 128 * 1024 * 1024:
                off = 0
                while off < size:
                    n = min(chunk, size - off)
                    data = _read_bytes(h, base + off, n)
                    if data:
                        # overlap for boundary markers
                        start = 0
                        while True:
                            i = data.find(needle, start)
                            if i < 0:
                                break
                            end = min(len(data), i + 500)
                            raw = data[i:end]
                            if b"savedVariablesUse" not in raw and i + 500 >= len(data) and off + n < size:
                                extra = _read_bytes(h, base + off + i, 600)
                                if extra:
                                    raw = extra
                            text = raw.split(b"\x00", 1)[0].decode("latin1", errors="ignore")
                            if not text.startswith("RRAPICOORD1"):
                                text = "RRAPICOORD1" + text
                            got = _parse_rrapicoord_text(text)
                            if got:
                                try:
                                    seq = int(float(got.get("seq") or -1))
                                except (TypeError, ValueError):
                                    seq = -1
                                if seq >= best_seq:
                                    best_seq = seq
                                    best = got
                                    best_addr = base + off + i
                            start = i + 1
                    off += n
                scanned += 1
        nxt = base + size
        if nxt <= addr:
            break
        addr = nxt
    if best and best_addr is not None:
        _RR_CACHE["addr"] = best_addr
    return best


def capture_api(
    repo: Path,
    pid: int,
    hwnd_hex: str,
    out_dir: Path,
    prefer_fast: bool = True,
    *,
    allow_stale_file: bool = False,
    max_stale_seconds: float = 3.0,
) -> dict[str, float] | None:
    def _from_coord_dict(c: dict[str, Any], source: str) -> dict[str, float] | None:
        try:
            if "X" in c:
                return {"x": float(c["X"]), "y": float(c["Y"]), "z": float(c["Z"]), "source": source}
            return {"x": float(c["x"]), "y": float(c["y"]), "z": float(c["z"]), "source": source}
        except (KeyError, TypeError, ValueError):
            return None

    if prefer_fast:
        fast = scan_rrapicoord_fast(pid)
        if fast:
            return {"x": fast["x"], "y": fast["y"], "z": fast["z"], "source": "fast-rrapicoord", "seq": fast.get("seq")}

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
            data = json.loads(ref.read_text(encoding="utf-8"))
            c = data.get("coordinate") or data.get("Coordinate") or {}
            got = _from_coord_dict(c, "ps1-reference")
            if got:
                return got
        except (json.JSONDecodeError, OSError):
            pass
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "{" in out:
        try:
            start = out.index("{")
            end = out.rindex("}") + 1
            payload = json.loads(out[start:end])
            c = payload.get("Coordinate") or payload.get("coordinate") or {}
            got = _from_coord_dict(c, "ps1-stdout")
            if got:
                return got
            # script often writes default ReferenceFile even when OutputFile unused
            ref_path = payload.get("ReferenceFile") or payload.get("referenceFile")
            if ref_path and Path(ref_path).exists():
                data = json.loads(Path(ref_path).read_text(encoding="utf-8"))
                c = data.get("coordinate") or data.get("Coordinate") or {}
                got = _from_coord_dict(c, "ps1-referencefile")
                if got:
                    return got
        except (ValueError, json.JSONDecodeError, KeyError, TypeError, OSError):
            pass
    # Only allow recent default-capture files when explicitly enabled (startup only)
    if allow_stale_file:
        default_caps = repo / "scripts" / "captures"
        now = time.time()
        refs = sorted(
            default_caps.glob("rift-api-reference-currentpid-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in refs[:3]:
            try:
                age = now - p.stat().st_mtime
                if age > max_stale_seconds:
                    continue
                data = json.loads(p.read_text(encoding="utf-8"))
                c = data.get("coordinate") or data.get("Coordinate") or {}
                got = _from_coord_dict(c, f"fresh-capture:{p.name}")
                if got:
                    got["captureAgeSec"] = age
                    return got
            except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
                continue
    return None


def planar(a: dict[str, float], b: dict[str, float]) -> float:
    return math.hypot(a["x"] - b["x"], a["z"] - b["z"])


def _read_u64(h: int, addr: int) -> int | None:
    data = _read_bytes(h, addr, 8)
    if not data or len(data) < 8:
        return None
    import struct

    return struct.unpack("<Q", data)[0]


def _read_f32s(h: int, addr: int, count: int) -> list[float] | None:
    import struct

    data = _read_bytes(h, addr, count * 4)
    if not data:
        return None
    c = len(data) // 4
    return list(struct.unpack("<" + "f" * c, data[: c * 4]))


def find_module_base(pid: int) -> int | None:
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

    snap = kernel32.CreateToolhelp32Snapshot(0x18, pid)
    me = ME()
    me.dwSize = ctypes.sizeof(me)
    base = None
    if kernel32.Module32First(snap, ctypes.byref(me)):
        while True:
            if b"rift_x64" in me.szModule.lower():
                base = int(me.modBaseAddr)
                break
            if not kernel32.Module32Next(snap, ctypes.byref(me)):
                break
    kernel32.CloseHandle(snap)
    return base


def load_current_truth(repo: Path) -> dict[str, Any] | None:
    truth = repo / "docs" / "recovery" / "current-truth.json"
    try:
        data = json.loads(truth.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def load_root_rva(repo: Path) -> int:
    data = load_current_truth(repo)
    if data:
        try:
            rva = (
                (data.get("bestCurrentCandidate") or {}).get("rootRva")
                or ((data.get("staticChainStatus") or {}).get("primaryCandidate") or {}).get("rootRva")
            )
            if rva:
                return int(str(rva), 0)
        except (ValueError, TypeError):
            pass
    return DEFAULT_ROOT_RVA


def get_process_start_utc(pid: int) -> str | None:
    """Best-effort process start UTC (PowerShell)."""
    try:
        proc = subprocess.run(
            [
                "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-Command",
                f"(Get-Process -Id {int(pid)}).StartTime.ToUniversalTime().ToString('o')",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        text = (proc.stdout or "").strip()
        return text or None
    except (OSError, subprocess.SubprocessError):
        return None


def parse_utc(text: str | None) -> datetime | None:
    if not text:
        return None
    t = str(text).strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    # trim fractional seconds > 6 digits
    if "." in t:
        head, rest = t.split(".", 1)
        frac = rest
        tz = ""
        for sep in ("+", "-"):
            if sep in rest[1:] if rest[:1].isdigit() else rest:
                # find timezone from end
                break
        # simpler: fromisoformat after truncating
        try:
            return datetime.fromisoformat(t)
        except ValueError:
            if "+" in rest:
                frac, tzpart = rest.split("+", 1)
                t = f"{head}.{frac[:6]}+{tzpart}"
            elif rest.count("-") >= 1 and "T" in t:
                # handle -offset
                idx = rest.rfind("-")
                if idx > 0:
                    frac, tzpart = rest[:idx], rest[idx:]
                    t = f"{head}.{frac[:6]}{tzpart}"
            try:
                return datetime.fromisoformat(t)
            except ValueError:
                return None
    try:
        return datetime.fromisoformat(t)
    except ValueError:
        return None


def bind_target_fail_closed(
    *,
    repo: Path,
    live: dict[str, Any],
    module_base: int | None,
    root_rva: int,
    use_current_truth: bool,
    allow_target_drift: bool,
    process_start_tolerance_seconds: float = 2.0,
) -> dict[str, Any]:
    """Compare live RIFT target to current-truth. Fail closed unless drift allowed."""
    result: dict[str, Any] = {
        "enabled": bool(use_current_truth),
        "status": "skipped",
        "blockers": [],
        "warnings": [],
        "truthPath": str(repo / "docs" / "recovery" / "current-truth.json"),
        "live": {
            "pid": live.get("pid"),
            "hwnd": live.get("hwndHex") or hex(int(live.get("hwnd") or 0)),
            "moduleBase": hex(module_base) if module_base else None,
            "rootRva": hex(root_rva),
        },
        "truth": None,
        "allowTargetDrift": bool(allow_target_drift),
    }
    if not use_current_truth:
        result["status"] = "disabled"
        return result

    truth = load_current_truth(repo)
    if not truth:
        result["status"] = "blocked"
        result["blockers"].append("current-truth-json-missing-or-invalid")
        return result

    tgt = truth.get("target") or {}
    best = truth.get("bestCurrentCandidate") or {}
    truth_pid = tgt.get("processId")
    truth_hwnd = str(tgt.get("targetWindowHandle") or "").lower()
    truth_base = str(tgt.get("moduleBase") or "").lower()
    truth_start = tgt.get("processStartUtc")
    truth_root = best.get("rootRva") or ((truth.get("staticChainStatus") or {}).get("primaryCandidate") or {}).get(
        "rootRva"
    )
    result["truth"] = {
        "pid": truth_pid,
        "hwnd": truth_hwnd,
        "moduleBase": truth_base,
        "processStartUtc": truth_start,
        "rootRva": truth_root,
        "status": truth.get("status"),
    }

    live_pid = int(live["pid"])
    live_hwnd = str(live.get("hwndHex") or hex(int(live["hwnd"]))).lower()
    live_base = hex(module_base).lower() if module_base else None

    if truth_pid is not None and int(truth_pid) != live_pid:
        result["blockers"].append(f"pid-mismatch:live={live_pid}:truth={truth_pid}")
    if truth_hwnd and truth_hwnd != live_hwnd:
        result["blockers"].append(f"hwnd-mismatch:live={live_hwnd}:truth={truth_hwnd}")
    if truth_base and live_base and truth_base != live_base:
        # module base can change on ASLR restart — warn if PID matched but base differed without start check
        result["warnings"].append(f"module-base-differs:live={live_base}:truth={truth_base}")
    if truth_root:
        try:
            if int(str(truth_root), 0) != int(root_rva):
                result["blockers"].append(f"root-rva-mismatch:live={hex(root_rva)}:truth={truth_root}")
        except (ValueError, TypeError):
            result["warnings"].append("truth-root-rva-unparseable")

    live_start = get_process_start_utc(live_pid)
    result["live"]["processStartUtc"] = live_start
    if truth_start and live_start:
        ts = parse_utc(str(truth_start))
        ls = parse_utc(live_start)
        if ts and ls:
            # normalize tz
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ls.tzinfo is None:
                ls = ls.replace(tzinfo=timezone.utc)
            delta = abs((ts - ls).total_seconds())
            result["processStartDeltaSeconds"] = delta
            if delta > process_start_tolerance_seconds:
                result["blockers"].append(
                    f"process-start-mismatch:deltaSec={delta:.3f}:tol={process_start_tolerance_seconds}"
                )
        else:
            result["warnings"].append("process-start-parse-failed")
    elif truth_start and not live_start:
        result["warnings"].append("live-process-start-unavailable")

    if result["blockers"]:
        if allow_target_drift:
            result["status"] = "drift-allowed"
            result["warnings"].extend([f"allowed:{b}" for b in result["blockers"]])
        else:
            result["status"] = "blocked"
    else:
        result["status"] = "passed"
    return result


def read_static_chain_pose(
    pid: int,
    *,
    module_base: int | None = None,
    root_rva: int = DEFAULT_ROOT_RVA,
    coord_offset: int = DEFAULT_COORD_OFFSET,
) -> dict[str, float] | None:
    """Read player XYZ from promoted static root. Fast; no RRAPICOORD scan."""
    base = module_base or find_module_base(pid)
    if not base:
        return None
    h = _RR_CACHE.get("handle")
    if _RR_CACHE.get("pid") != pid or not h:
        if h:
            try:
                kernel32.CloseHandle(h)
            except Exception:
                pass
        h = _open_process(pid)
        _RR_CACHE["pid"] = pid
        _RR_CACHE["handle"] = h
    owner = _read_u64(h, base + root_rva)
    if not owner or owner < 0x10000:
        return None
    xyz = _read_f32s(h, owner + coord_offset, 3)
    if not xyz or len(xyz) < 3:
        return None
    return {
        "x": float(xyz[0]),
        "y": float(xyz[1]),
        "z": float(xyz[2]),
        "source": "static-chain",
        "owner": hex(owner),
        "moduleBase": hex(base),
        "rootRva": hex(root_rva),
    }


def read_camera_for_w2s(
    pid: int,
    *,
    module_base: int | None = None,
    root_rva: int = DEFAULT_ROOT_RVA,
) -> dict[str, float] | None:
    base = module_base or find_module_base(pid)
    if not base:
        return None
    h = _RR_CACHE.get("handle")
    if _RR_CACHE.get("pid") != pid or not h:
        h = _open_process(pid)
        _RR_CACHE["pid"] = pid
        _RR_CACHE["handle"] = h
    owner = _read_u64(h, base + root_rva)
    if not owner:
        return None
    child = _read_u64(h, owner + DEFAULT_CAMERA_CHILD_OFFSET)
    if not child:
        return None
    vals = _read_f32s(h, child, 20)
    if not vals or len(vals) < 15:
        return None
    cam_x, cam_y, cam_z = vals[2], vals[3], vals[4]
    look_x, look_y, look_z = vals[5], vals[6], vals[7]
    dx, dy, dz = look_x - cam_x, look_y - cam_y, look_z - cam_z
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-6:
        return None
    fov = vals[14]
    if not (1.0 < fov < 170.0):
        fov = 75.0
    return {
        "cam_x": cam_x,
        "cam_y": cam_y,
        "cam_z": cam_z,
        "player_x": look_x,
        "player_y": look_y,
        "player_z": look_z,
        "dir_x": dx / length,
        "dir_y": dy / length,
        "dir_z": dz / length,
        "fov": fov,
    }


def project_w2s(wx: float, wy: float, wz: float, cam: dict[str, float], w: int, h: int) -> tuple[float, float] | None:
    fx, fy, fz = cam["dir_x"], cam["dir_y"], cam["dir_z"]
    # right = forward × world-up
    rx, ry, rz = fy * 0.0 - fz * 1.0, fz * 0.0 - fx * 0.0, fx * 1.0 - fy * 0.0
    rl = math.sqrt(rx * rx + ry * ry + rz * rz)
    if rl < 1e-6:
        rx, ry, rz = fy * 1.0 - fz * 0.0, fz * 0.0 - fx * 1.0, fx * 0.0 - fy * 0.0
        rl = math.sqrt(rx * rx + ry * ry + rz * rz)
    if rl < 1e-9:
        return None
    rx, ry, rz = rx / rl, ry / rl, rz / rl
    ux, uy, uz = ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx
    dx, dy, dz = wx - cam["cam_x"], wy - cam["cam_y"], wz - cam["cam_z"]
    cx = rx * dx + ry * dy + rz * dz
    cy = ux * dx + uy * dy + uz * dz
    cz = fx * dx + fy * dy + fz * dz
    if cz < 0.15:
        return None
    fl = 1.0 / math.tan(math.radians(cam["fov"]) / 2.0)
    aspect = w / float(h)
    ndc_x = (cx / cz) * fl / aspect
    ndc_y = (cy / cz) * fl
    sx = (ndc_x + 1.0) * w / 2.0
    sy = (1.0 - ndc_y) * h / 2.0
    return sx, sy


def capture_pose(
    repo: Path,
    pid: int,
    hwnd_hex: str,
    out_dir: Path,
    *,
    pose_source: str = "auto",
    root_rva: int = DEFAULT_ROOT_RVA,
    module_base: int | None = None,
    prefer_fast: bool = True,
) -> dict[str, float] | None:
    if pose_source in ("static-chain", "auto"):
        static = read_static_chain_pose(pid, module_base=module_base, root_rva=root_rva)
        if static:
            return static
        if pose_source == "static-chain":
            return None
    return capture_api(repo, pid, hwnd_hex, out_dir, prefer_fast=prefer_fast)


def bearing_deg(from_p: dict[str, float], to_p: dict[str, float]) -> float:
    # atan2(dx, dz) degrees, 0 = +Z
    return math.degrees(math.atan2(to_p["x"] - from_p["x"], to_p["z"] - from_p["z"]))


def norm_angle(d: float) -> float:
    while d > 180:
        d -= 360
    while d < -180:
        d += 360
    return d


def click_client_sendinput(
    repo: Path,
    pid: int,
    hwnd: int,
    x: int,
    y: int,
    hold_ms: int = 45,
    focus_delay_ms: int = 500,
    *,
    no_refocus: bool = True,
) -> dict[str, Any]:
    """Ground click via repo C# SendInput (foreground required). Never PostMessage mouse.

    no_refocus=True (default for C2M routes): leave RIFT foreground after the click.
    Without this, SendInput restores the previous window every step → visible
    focus/unfocus flicker during multi-click routes.
    """
    wrapper = repo / "scripts" / "send-rift-key-csharp.ps1"
    if not wrapper.exists():
        raise FileNotFoundError(f"missing {wrapper}")
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
        hex(int(hwnd)),
        "--client-x",
        str(int(x)),
        "--client-y",
        str(int(y)),
        "--hold-ms",
        str(int(hold_ms)),
        "--focus-delay-ms",
        str(int(focus_delay_ms)),
        "--json",
    ]
    if no_refocus:
        cmd.append("--no-refocus")
    proc = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=60)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    payload: dict[str, Any] = {
        "exitCode": proc.returncode,
        "backend": "RiftReader.SendInput",
        "stdoutTail": out[-1500:],
    }
    if "{" in out:
        try:
            start = out.index("{")
            end = out.rindex("}") + 1
            payload["result"] = json.loads(out[start:end])
        except (ValueError, json.JSONDecodeError):
            pass
    if proc.returncode != 0:
        err = payload.get("result") or {}
        msg = err.get("error") if isinstance(err, dict) else None
        raise RuntimeError(msg or f"SendInput mouse click failed exit={proc.returncode}: {out[-500:]}")
    return payload


def choose_click(
    width: int,
    height: int,
    bearing_error_deg: float | None,
    step: int,
    dist_to_goal: float,
    *,
    invert_lateral: bool = False,
    turn_hard: bool = False,
    aim_mode: str = "center",
    goal: dict[str, float] | None = None,
    cam: dict[str, float] | None = None,
) -> tuple[int, int, str]:
    """Pick client click for in-game C2M.

    aim_mode:
      center    — true client center Y; lateral bias only (safe; avoids toolbar)
      w2s       — project world goal; fall back to center if behind/off-screen
      heuristic — mid-client Y band (never toolbar ~0.82)
    """
    inset = 8
    cx0, cy0 = width // 2, height // 2

    def clamp_xy(x: int, y: int) -> tuple[int, int]:
        return max(inset, min(width - inset - 1, x)), max(inset, min(height - inset - 1, y))

    # --- W2S path ---
    if aim_mode == "w2s" and goal is not None and cam is not None:
        gy = float(goal.get("y", cam.get("player_y", 0.0)))
        proj = project_w2s(float(goal["x"]), gy, float(goal["z"]), cam, width, height)
        if proj is not None:
            sx, sy = proj
            # Keep in playable band: never bottom 18% (toolbar risk) or top 8%
            y_lo, y_hi = int(height * 0.08), int(height * 0.72)
            x_lo, x_hi = inset, width - inset - 1
            if x_lo <= sx <= x_hi and y_lo <= sy <= y_hi:
                x, y = clamp_xy(int(round(sx)), int(round(sy)))
                return x, y, f"w2s/on-screen/dist={dist_to_goal:.1f}"
            # clamp into safe band rather than toolbar
            x, y = clamp_xy(int(round(sx)), int(max(y_lo, min(y_hi, sy))))
            return x, y, f"w2s/clamped/dist={dist_to_goal:.1f}"
        # fall through to center if behind camera

    # Lateral bias from bearing error
    bias = 0.0
    if bearing_error_deg is not None:
        scale = 60.0 if turn_hard else 90.0
        bias = -bearing_error_deg / scale
        if invert_lateral:
            bias = -bias
        if turn_hard:
            bias = 0.28 if bias >= 0 else -0.28
        else:
            bias = max(-0.28, min(0.28, bias))
    elif aim_mode != "center":
        sweep = [0.0, 0.08, -0.08, 0.14, -0.14]
        bias = sweep[step % len(sweep)]
        if invert_lateral:
            bias = -bias

    if aim_mode == "center" or aim_mode == "w2s":
        # Center-safe: Y always client center; X = center + modest lateral bias
        x = int(width * (0.50 + bias * 0.5))
        y = cy0
        x, y = clamp_xy(x, y)
        return x, y, f"center-safe/bias={bias:.3f}/err={bearing_error_deg}/inv={invert_lateral}"

    # heuristic: safe mid Y only (max ~0.68 — never toolbar band)
    if turn_hard:
        y_ratio = 0.55
    elif dist_to_goal < 6:
        y_ratio = 0.58
    elif dist_to_goal < 15:
        y_ratio = 0.62
    else:
        y_ratio = 0.66
    x = int(width * (0.50 + bias))
    y = int(height * y_ratio)
    x, y = clamp_xy(x, y)
    return x, y, f"heuristic/bias={bias:.3f}/y={y_ratio:.2f}/err={bearing_error_deg}/inv={invert_lateral}"


def poll_until_settled(
    repo: Path,
    pid: int,
    hwnd_hex: str,
    out_dir: Path,
    prev: dict[str, float],
    wait_ms: int,
    poll_ms: int = 150,
    *,
    pose_source: str = "auto",
    root_rva: int = DEFAULT_ROOT_RVA,
    module_base: int | None = None,
) -> dict[str, float] | None:
    """After a click, poll pose until moved or timeout."""
    deadline = time.time() + wait_ms / 1000.0
    last = prev
    best = None
    while time.time() < deadline:
        cur = capture_pose(
            repo,
            pid,
            hwnd_hex,
            out_dir,
            pose_source=pose_source,
            root_rva=root_rva,
            module_base=module_base,
            prefer_fast=True,
        )
        if cur:
            best = cur
            if planar(prev, cur) >= 0.35:
                time.sleep(0.2)
                cur2 = capture_pose(
                    repo,
                    pid,
                    hwnd_hex,
                    out_dir,
                    pose_source=pose_source,
                    root_rva=root_rva,
                    module_base=module_base,
                    prefer_fast=True,
                )
                return cur2 or cur
            last = cur
        time.sleep(poll_ms / 1000.0)
    return best or last


def confirm_arrival_dwell(
    *,
    repo: Path,
    t: dict[str, Any],
    run_dir: Path,
    pos: dict[str, float],
    goal: dict[str, float],
    arrival_radius: float,
    dwell_ms: int,
    poll_ms: int,
    pose_source: str,
    root_rva: int,
    module_base: int | None,
) -> dict[str, Any]:
    """Require pose to stay inside arrival radius for dwell_ms."""
    if dwell_ms <= 0:
        return {"ok": True, "skipped": True, "final": pos}
    deadline = time.time() + dwell_ms / 1000.0
    samples = 0
    last = pos
    while time.time() < deadline:
        cur = capture_pose(
            repo,
            t["pid"],
            t["hwndHex"],
            run_dir / "dwell",
            pose_source=pose_source,
            root_rva=root_rva,
            module_base=module_base,
            prefer_fast=True,
        )
        if cur:
            last = cur
            samples += 1
            if planar(cur, goal) > arrival_radius:
                return {
                    "ok": False,
                    "reason": "left-radius-during-dwell",
                    "final": cur,
                    "dist": planar(cur, goal),
                    "samples": samples,
                }
        time.sleep(max(0.05, poll_ms / 1000.0))
    return {
        "ok": True,
        "final": last,
        "dist": planar(last, goal),
        "samples": samples,
        "dwellMs": dwell_ms,
    }


def drive_to_goal(
    *,
    repo: Path,
    run_dir: Path,
    t: dict[str, Any],
    start_pos: dict[str, float],
    goal: dict[str, float],
    arrival_radius: float,
    max_steps: int,
    step_wait_ms: int,
    poll_ms: int,
    safety: dict[str, Any],
    step_prefix: str = "",
    click_mode: str = "sendinput",
    focus_delay_ms: int = 500,
    aim_mode: str = "w2s",
    pose_source: str = "auto",
    root_rva: int = DEFAULT_ROOT_RVA,
    module_base: int | None = None,
    dwell_ms: int = 600,
    stuck_streak_limit: int = 6,
) -> dict[str, Any]:
    """Drive from start_pos toward goal. Returns leg summary (does not close RR cache)."""
    if click_mode in ("post", "cursor"):
        raise ValueError(
            "click_mode 'post'/'cursor' removed: RIFT mouse requires foreground SendInput "
            "(see Agents.md / RiftReader.SendInput). Use click_mode=sendinput."
        )
    steps: list[dict[str, Any]] = []
    prev = start_pos
    motion_bearing: float | None = None
    arrived = False
    no_progress_streak = 0
    invert_lateral = False
    wrong_way_streak = 0
    reaim_events = 0
    warnings: list[str] = []
    blockers: list[str] = []
    best_dist = planar(start_pos, goal)
    # Effective aim can temporarily force center after stuck
    force_center_steps = 0
    # First click may need full focus delay; later clicks keep RIFT focused (--no-refocus)
    clicks_sent = 0

    for i in range(max_steps):
        rect = wintypes.RECT()
        user32.GetClientRect(t["hwnd"], ctypes.byref(rect))
        width = max(32, int(rect.right - rect.left))
        height = max(32, int(rect.bottom - rect.top))

        dist = planar(prev, goal)
        best_dist = min(best_dist, dist)
        step: dict[str, Any] = {
            "index": i,
            "pos": {k: prev[k] for k in ("x", "y", "z") if k in prev},
            "distToGoal": dist,
            "atUtc": utc_now(),
            "aimMode": aim_mode,
            "poseSourcePref": pose_source,
            "noProgressStreak": no_progress_streak,
        }
        if dist <= arrival_radius:
            dwell = confirm_arrival_dwell(
                repo=repo,
                t=t,
                run_dir=run_dir / f"{step_prefix}dwell-{i}",
                pos=prev,
                goal=goal,
                arrival_radius=arrival_radius,
                dwell_ms=dwell_ms,
                poll_ms=poll_ms,
                pose_source=pose_source,
                root_rva=root_rva,
                module_base=module_base,
            )
            step["dwell"] = dwell
            if dwell.get("ok"):
                arrived = True
                step["arrived"] = True
                if dwell.get("final"):
                    prev = dwell["final"]
                steps.append(step)
                break
            warnings.append(f"{step_prefix}dwell-failed-step-{i}")
            if dwell.get("final"):
                prev = dwell["final"]
            # fall through — re-aim if we left radius

        # --- stuck re-aim policy before click ---
        step_aim = aim_mode
        turn_hard = False
        if force_center_steps > 0:
            step_aim = "center"
            force_center_steps -= 1
            step["forcedCenterReaim"] = True
        if no_progress_streak >= 1:
            invert_lateral = not invert_lateral
            step["stuckReaimFlip"] = invert_lateral
            reaim_events += 1
        if no_progress_streak >= 2:
            step_aim = "center"
            turn_hard = True
            force_center_steps = max(force_center_steps, 1)
            step["stuckReaimCenter"] = True
        if no_progress_streak >= 3:
            # refresh W2S cam + hard center-safe lateral sweep next
            step_aim = "w2s" if aim_mode == "w2s" else "center"
            turn_hard = True
            step["stuckReaimRefreshW2s"] = True

        goal_bearing = bearing_deg(prev, goal)
        err = None if motion_bearing is None else norm_angle(goal_bearing - motion_bearing)
        if err is not None and abs(err) > 40.0:
            turn_hard = True
        cam = None
        if step_aim == "w2s":
            cam = read_camera_for_w2s(t["pid"], module_base=module_base, root_rva=root_rva)
            if not cam:
                warnings.append(f"{step_prefix}w2s-cam-unavailable-step-{i}")
                step_aim = "center"
        cx, cy, why = choose_click(
            width,
            height,
            err,
            i,
            dist,
            invert_lateral=invert_lateral,
            turn_hard=turn_hard,
            aim_mode=step_aim if cam or step_aim != "w2s" else "center",
            goal=goal,
            cam=cam,
        )
        if no_progress_streak >= 1:
            why = f"stuck-reaim(streak={no_progress_streak})/" + why
        # Keep RIFT focused for the whole leg; only first click needs full settle delay
        step_focus_delay = focus_delay_ms if clicks_sent == 0 else min(80, focus_delay_ms)
        try:
            click_payload = click_client_sendinput(
                repo,
                t["pid"],
                t["hwnd"],
                cx,
                cy,
                hold_ms=45,
                focus_delay_ms=step_focus_delay,
                no_refocus=True,
            )
            step["sendInput"] = {
                "ok": True,
                "exitCode": click_payload.get("exitCode"),
                "resultStatus": (click_payload.get("result") or {}).get("status"),
                "focus": (click_payload.get("result") or {}).get("focus"),
                "noRefocus": True,
                "focusDelayMs": step_focus_delay,
            }
            clicks_sent += 1
        except Exception as exc:  # noqa: BLE001
            step["sendInput"] = {"ok": False, "error": str(exc)}
            steps.append(step)
            warnings.append(f"{step_prefix}sendinput-click-failed-step-{i}")
            no_progress_streak += 1
            if no_progress_streak >= 2:
                blockers.append("sendinput-click-failed")
                break
            continue
        safety["inputSent"] = True
        safety["clickSent"] = True
        safety["sendInputMouseUsed"] = True
        safety["postMessageMouseUsed"] = False
        safety["requiresForeground"] = True
        safety["noRefocusDuringRoute"] = True
        step["click"] = {
            "clientX": cx,
            "clientY": cy,
            "why": why,
            "clientSize": [width, height],
            "mode": "sendinput",
            "effectiveAimMode": step_aim,
            "centerOnlyY": cy == height // 2 or step_aim in ("center", "w2s"),
            "noRefocus": True,
        }
        step["goalBearingDeg"] = goal_bearing
        step["motionBearingDeg"] = motion_bearing
        step["bearingErrorDeg"] = err
        step["invertLateral"] = invert_lateral

        nxt = poll_until_settled(
            repo,
            t["pid"],
            t["hwndHex"],
            run_dir / f"{step_prefix}api-step-{i}",
            prev,
            step_wait_ms,
            poll_ms,
            pose_source=pose_source,
            root_rva=root_rva,
            module_base=module_base,
        )
        if not nxt:
            step["apiFailed"] = True
            steps.append(step)
            warnings.append(f"{step_prefix}pose-failed-step-{i}")
            no_progress_streak += 1
            if no_progress_streak >= 3:
                blockers.append("pose-fail-streak")
                break
            continue
        moved = planar(prev, nxt)
        step["posAfter"] = {k: nxt[k] for k in ("x", "y", "z")}
        step["poseSource"] = nxt.get("source")
        step["movedPlanar"] = moved
        if moved >= 0.30:
            motion_bearing = bearing_deg(prev, nxt)
            step["motionBearingUpdated"] = motion_bearing
        step["distAfter"] = planar(nxt, goal)
        step["progress"] = dist - step["distAfter"]
        best_dist = min(best_dist, step["distAfter"])
        # Camera-relative / W2S can still go wrong — flip lateral map
        if step["progress"] < -0.75 and moved >= 0.30:
            wrong_way_streak += 1
            if wrong_way_streak >= 1:
                invert_lateral = not invert_lateral
                step["flippedInvertLateral"] = invert_lateral
                wrong_way_streak = 0
        elif step["progress"] > 0.25:
            wrong_way_streak = 0
        if step["progress"] < 0.20 and moved < 0.30:
            no_progress_streak += 1
            step["stuckDetected"] = True
        else:
            no_progress_streak = 0
        steps.append(step)
        prev = nxt
        if step["distAfter"] <= arrival_radius:
            dwell = confirm_arrival_dwell(
                repo=repo,
                t=t,
                run_dir=run_dir / f"{step_prefix}dwell-after-{i}",
                pos=prev,
                goal=goal,
                arrival_radius=arrival_radius,
                dwell_ms=dwell_ms,
                poll_ms=poll_ms,
                pose_source=pose_source,
                root_rva=root_rva,
                module_base=module_base,
            )
            step["dwell"] = dwell
            if dwell.get("ok"):
                arrived = True
                if dwell.get("final"):
                    prev = dwell["final"]
                break
            warnings.append(f"{step_prefix}dwell-failed-after-step-{i}")
            if dwell.get("final"):
                prev = dwell["final"]
        if no_progress_streak >= stuck_streak_limit:
            warnings.append(f"{step_prefix}stuck-streak-stop")
            blockers.append("stuck-no-progress")
            break

    final_dist = planar(prev, goal)
    start_dist = planar(start_pos, goal)
    if arrived:
        status, verdict = "passed", "arrived-within-radius"
    elif final_dist < start_dist - 1.0 or best_dist < start_dist - 1.0:
        status, verdict = "passed", "progressed-but-not-arrived"
        warnings.append("did-not-reach-arrival-radius")
    else:
        status, verdict = "blocked", "little-or-no-progress-toward-goal"
        blockers.append("no-meaningful-progress")

    return {
        "status": status,
        "verdict": verdict,
        "arrived": arrived,
        "start": {k: start_pos[k] for k in ("x", "y", "z") if k in start_pos},
        "goal": goal,
        "final": {k: prev[k] for k in ("x", "y", "z") if k in prev},
        "finalDistToGoal": final_dist,
        "bestDistToGoal": best_dist,
        "steps": steps,
        "reaimEvents": reaim_events,
        "dwellMs": dwell_ms,
        "warnings": warnings,
        "blockers": blockers,
        "aimMode": aim_mode,
        "poseSource": pose_source,
    }


def parse_waypoint_offsets(spec: str) -> list[tuple[float, float]]:
    """Parse 'dx,dz;dx,dz' relative offsets from route start."""
    out: list[tuple[float, float]] = []
    for part in spec.split(";"):
        part = part.strip()
        if not part:
            continue
        a, b = part.split(",")
        out.append((float(a.strip()), float(b.strip())))
    return out


def load_waypoints_json(path: Path) -> dict[str, Any]:
    """Load absolute or relative route JSON.

    Schema (preferred)::

        {
          "schemaVersion": 1,
          "kind": "riftreader-c2m-route",
          "name": "smoke-rel-L",
          "coordinateMode": "relative" | "absolute",
          "defaultArrivalRadius": 2.5,
          "waypoints": [
            {"id": "a", "dx": 0, "dz": 5},          # relative
            {"id": "b", "x": 7460.0, "y": 865.0, "z": 3122.0}  # absolute
          ]
        }

    Legacy: bare list of absolute {x,y,z} or {waypoints:[...]}.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        meta = {
            "schemaVersion": 0,
            "kind": "legacy-list",
            "name": path.stem,
            "coordinateMode": "absolute",
            "defaultArrivalRadius": None,
            "raw": data,
        }
        wps = data
    elif isinstance(data, dict):
        meta = {
            "schemaVersion": data.get("schemaVersion", 1),
            "kind": data.get("kind") or "riftreader-c2m-route",
            "name": data.get("name") or path.stem,
            "coordinateMode": str(data.get("coordinateMode") or data.get("mode") or "absolute").lower(),
            "defaultArrivalRadius": data.get("defaultArrivalRadius"),
            "notes": data.get("notes"),
            "zoneHint": data.get("zoneHint"),
        }
        wps = data.get("waypoints") or data.get("points")
        if not isinstance(wps, list):
            raise ValueError("waypoints json must include a waypoints list")
    else:
        raise ValueError("waypoints json must be object or list")

    if meta["coordinateMode"] not in ("absolute", "relative"):
        raise ValueError("coordinateMode must be absolute or relative")

    out: list[dict[str, Any]] = []
    for i, w in enumerate(wps):
        if not isinstance(w, dict):
            raise ValueError(f"waypoint[{i}] must be object")
        item: dict[str, Any] = {
            "id": w.get("id") or f"wp-{i+1:03d}",
            "arrivalRadius": float(w["arrivalRadius"]) if w.get("arrivalRadius") is not None else None,
        }
        if meta["coordinateMode"] == "relative":
            if "dx" not in w or "dz" not in w:
                # allow absolute fields in a relative file only if both x and z present → treat as absolute point
                if "x" in w and "z" in w:
                    item["mode"] = "absolute"
                    item["x"] = float(w["x"])
                    item["y"] = float(w["y"]) if w.get("y") is not None else None
                    item["z"] = float(w["z"])
                else:
                    raise ValueError(f"waypoint[{i}] relative mode needs dx,dz")
            else:
                item["mode"] = "relative"
                item["dx"] = float(w["dx"])
                item["dz"] = float(w["dz"])
                item["dy"] = float(w["dy"]) if w.get("dy") is not None else 0.0
        else:
            if "x" not in w or "z" not in w:
                raise ValueError(f"waypoint[{i}] absolute mode needs x,z")
            item["mode"] = "absolute"
            item["x"] = float(w["x"])
            item["y"] = float(w["y"]) if w.get("y") is not None else None
            item["z"] = float(w["z"])
        out.append(item)
    meta["waypoints"] = out
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="C2M run-to-goal / multi-waypoint MVP")
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--stimulus-approved", action="store_true")
    ap.add_argument("--goal-x", type=float)
    ap.add_argument("--goal-y", type=float)
    ap.add_argument("--goal-z", type=float)
    ap.add_argument("--offset-x", type=float, default=0.0, help="If no goal, offset from current API pos")
    ap.add_argument("--offset-z", type=float, default=15.0)
    ap.add_argument(
        "--waypoint-offsets",
        type=str,
        default="",
        help="Multi-leg relative offsets from start: 'dx,dz;dx,dz' e.g. '0,6;5,0'",
    )
    ap.add_argument(
        "--waypoints-json",
        type=Path,
        help="Route file: absolute or relative waypoints (see scripts/routes/*.json)",
    )
    ap.add_argument("--arrival-radius", type=float, default=3.0)
    ap.add_argument("--max-steps", type=int, default=8, help="Max clicks per waypoint leg")
    ap.add_argument("--step-wait-ms", type=int, default=1800)
    ap.add_argument("--poll-ms", type=int, default=200)
    ap.add_argument("--dwell-ms", type=int, default=600, help="Must remain in arrival radius this long (0=off)")
    ap.add_argument("--stuck-streak-limit", type=int, default=6, help="Stop leg after this many no-progress steps")
    ap.add_argument(
        "--click-mode",
        choices=["sendinput"],
        default="sendinput",
        help="Only SendInput mouse after foreground focus is supported for RIFT C2M.",
    )
    ap.add_argument(
        "--aim-mode",
        choices=["w2s", "center", "heuristic"],
        default="w2s",
        help="w2s=project goal via camera; center=client-center safe; heuristic=mid-Y bias",
    )
    ap.add_argument(
        "--pose-source",
        choices=["auto", "static-chain", "rrapicoord"],
        default="auto",
        help="Pose for arrival: static-chain (fast), rrapicoord, or auto",
    )
    ap.add_argument("--root-rva", default=None, help="Override static root RVA (default: current-truth / 0x32E07C0)")
    ap.add_argument(
        "--use-current-truth",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail closed if live PID/HWND/root disagree with current-truth (default: true)",
    )
    ap.add_argument(
        "--allow-target-drift",
        action="store_true",
        help="With --use-current-truth, allow PID/HWND mismatch (recovery only)",
    )
    ap.add_argument("--process-start-tolerance-seconds", type=float, default=2.0)
    ap.add_argument("--focus-delay-ms", type=int, default=500)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    run_dir = repo / "scripts" / "captures" / f"c2m-run-to-goal-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "riftreader-c2m-run-to-goal",
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
            "usesEngineDestinationField": False,
            "usesStaticPlayerRoot": False,
            "postMessageMouseUsed": False,
            "sendInputMouseUsed": False,
            "requiresForeground": True,
        },
        "artifacts": {"runDirectory": str(run_dir)},
        "strategy": "in-game-c2m + SendInput + W2S/center aim + static-chain/RRAPICOORD arrival",
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

    root_rva = int(args.root_rva, 0) if args.root_rva else load_root_rva(repo)
    module_base = find_module_base(t["pid"])
    summary["rootRva"] = hex(root_rva)
    summary["moduleBase"] = hex(module_base) if module_base else None
    summary["aimMode"] = args.aim_mode
    summary["poseSource"] = args.pose_source
    summary["dwellMs"] = args.dwell_ms
    summary["stuckStreakLimit"] = args.stuck_streak_limit

    # Truth fail-closed bind (default on)
    bind = bind_target_fail_closed(
        repo=repo,
        live=t,
        module_base=module_base,
        root_rva=root_rva,
        use_current_truth=bool(args.use_current_truth),
        allow_target_drift=bool(args.allow_target_drift),
        process_start_tolerance_seconds=float(args.process_start_tolerance_seconds),
    )
    summary["truthBind"] = bind
    if bind.get("status") == "blocked":
        summary["blockers"].extend(bind.get("blockers") or ["truth-bind-blocked"])
        summary["blockers"] = list(dict.fromkeys(summary["blockers"]))
        summary["verdict"] = "truth-bind-failed"
        write_json(run_dir / "summary.json", summary)
        if args.json:
            print(json.dumps(summary, indent=2, default=str))
        else:
            print(f"blocked: truth-bind {bind.get('blockers')}")
        return 2
    if bind.get("warnings"):
        summary["warnings"].extend(bind["warnings"])

    # Warm static chain / RRAPICOORD before timed start
    t_warm = time.time()
    warm_static = read_static_chain_pose(t["pid"], module_base=module_base, root_rva=root_rva)
    warm_rr = None if warm_static else scan_rrapicoord_fast(t["pid"])
    summary["poseWarmMs"] = int((time.time() - t_warm) * 1000)
    summary["staticChainWarmHit"] = bool(warm_static)
    summary["rrapicoordWarmHit"] = bool(warm_rr)
    if warm_static:
        summary["safety"]["usesStaticPlayerRoot"] = True

    t0 = time.time()
    pos = capture_pose(
        repo,
        t["pid"],
        t["hwndHex"],
        run_dir / "api-start",
        pose_source=args.pose_source,
        root_rva=root_rva,
        module_base=module_base,
        prefer_fast=True,
    )
    if not pos and args.pose_source != "rrapicoord":
        pos = capture_api(
            repo,
            t["pid"],
            t["hwndHex"],
            run_dir / "api-start",
            prefer_fast=True,
            allow_stale_file=True,
            max_stale_seconds=8.0,
        )
    if not pos:
        summary["blockers"].append("pose-start-failed")
        write_json(run_dir / "summary.json", summary)
        return 2
    summary["start"] = pos
    summary["poseStartMs"] = int((time.time() - t0) * 1000)

    # Build ordered goals
    goals: list[dict[str, Any]] = []
    route_meta: dict[str, Any] | None = None
    if args.waypoints_json:
        route_meta = load_waypoints_json(args.waypoints_json.resolve())
        summary["route"] = {
            "path": str(args.waypoints_json.resolve()),
            "name": route_meta.get("name"),
            "coordinateMode": route_meta.get("coordinateMode"),
            "schemaVersion": route_meta.get("schemaVersion"),
            "notes": route_meta.get("notes"),
        }
        default_r = route_meta.get("defaultArrivalRadius")
        origin = pos  # relative offsets from route start pose
        for w in route_meta["waypoints"]:
            radius = w.get("arrivalRadius")
            if radius is None:
                radius = default_r if default_r is not None else args.arrival_radius
            if w.get("mode") == "relative":
                goals.append(
                    {
                        "id": w["id"],
                        "x": origin["x"] + float(w["dx"]),
                        "y": origin["y"] + float(w.get("dy") or 0.0),
                        "z": origin["z"] + float(w["dz"]),
                        "arrivalRadius": float(radius),
                        "sourceMode": "relative",
                    }
                )
            else:
                goals.append(
                    {
                        "id": w["id"],
                        "x": float(w["x"]),
                        "y": float(w["y"]) if w.get("y") is not None else origin["y"],
                        "z": float(w["z"]),
                        "arrivalRadius": float(radius),
                        "sourceMode": "absolute",
                    }
                )
    elif args.waypoint_offsets.strip():
        for i, (dx, dz) in enumerate(parse_waypoint_offsets(args.waypoint_offsets)):
            goals.append(
                {
                    "id": f"rel-{i+1:02d}",
                    "x": pos["x"] + dx,
                    "y": pos["y"],
                    "z": pos["z"] + dz,
                    "arrivalRadius": args.arrival_radius,
                    "sourceMode": "relative-cli",
                }
            )
    elif args.goal_x is not None and args.goal_z is not None:
        goals.append(
            {
                "id": "goal",
                "x": float(args.goal_x),
                "y": float(args.goal_y if args.goal_y is not None else pos["y"]),
                "z": float(args.goal_z),
                "arrivalRadius": args.arrival_radius,
                "sourceMode": "absolute-cli",
            }
        )
    else:
        goals.append(
            {
                "id": "offset",
                "x": pos["x"] + args.offset_x,
                "y": pos["y"],
                "z": pos["z"] + args.offset_z,
                "arrivalRadius": args.arrival_radius,
                "sourceMode": "relative-cli",
            }
        )

    summary["goals"] = goals
    summary["arrivalRadiusDefault"] = args.arrival_radius

    legs: list[dict[str, Any]] = []
    cur = pos
    all_arrived = True
    for gi, g in enumerate(goals):
        goal = {"x": g["x"], "y": g["y"], "z": g["z"]}
        radius = float(g.get("arrivalRadius") or args.arrival_radius)
        leg = drive_to_goal(
            repo=repo,
            run_dir=run_dir,
            t=t,
            start_pos=cur,
            goal=goal,
            arrival_radius=radius,
            max_steps=args.max_steps,
            step_wait_ms=args.step_wait_ms,
            poll_ms=args.poll_ms,
            safety=summary["safety"],
            step_prefix=f"leg{gi:02d}-",
            click_mode=args.click_mode,
            focus_delay_ms=args.focus_delay_ms,
            aim_mode=args.aim_mode,
            pose_source=args.pose_source,
            root_rva=root_rva,
            module_base=module_base,
            dwell_ms=args.dwell_ms,
            stuck_streak_limit=args.stuck_streak_limit,
        )
        leg["id"] = g["id"]
        leg["arrivalRadius"] = radius
        legs.append(leg)
        summary["warnings"].extend(leg.get("warnings") or [])
        summary["blockers"].extend(leg.get("blockers") or [])
        cur = leg["final"]
        if not leg.get("arrived"):
            all_arrived = False
            break

    # close cached process handle
    if _RR_CACHE.get("handle"):
        try:
            kernel32.CloseHandle(_RR_CACHE["handle"])
        except Exception:
            pass
        _RR_CACHE["handle"] = None

    summary["legs"] = legs
    summary["final"] = cur
    summary["legsArrived"] = sum(1 for L in legs if L.get("arrived"))
    summary["legsTotal"] = len(goals)
    summary["legsAttempted"] = len(legs)

    # Backward-compatible single-goal fields
    if legs:
        summary["goal"] = legs[-1]["goal"]
        summary["steps"] = legs[-1]["steps"]
        summary["finalDistToGoal"] = legs[-1]["finalDistToGoal"]
        summary["arrived"] = all_arrived and len(legs) == len(goals)

    if all_arrived and len(legs) == len(goals):
        summary["status"] = "passed"
        summary["verdict"] = "all-waypoints-arrived" if len(goals) > 1 else "arrived-within-radius"
    elif any(L.get("arrived") for L in legs) or any(
        (L.get("finalDistToGoal") is not None) and L["finalDistToGoal"] < planar(L["start"], L["goal"]) - 1.0 for L in legs
    ):
        summary["status"] = "passed"
        summary["verdict"] = "partial-route-progress"
        summary["warnings"].append("route-incomplete")
    else:
        summary["status"] = "blocked"
        summary["verdict"] = "little-or-no-progress-toward-goal"
        if "no-meaningful-progress" not in summary["blockers"]:
            summary["blockers"].append("no-meaningful-progress")

    # de-dupe blockers/warnings
    summary["blockers"] = list(dict.fromkeys(summary["blockers"]))
    summary["warnings"] = list(dict.fromkeys(summary["warnings"]))

    write_json(run_dir / "summary.json", summary)
    md = [
        "# C2M run-to-goal",
        "",
        f"- status: `{summary['status']}`",
        f"- verdict: `{summary.get('verdict')}`",
        f"- start: `{summary.get('start')}`",
        f"- legs: `{summary.get('legsArrived')}/{summary.get('legsTotal')}`",
        f"- final: `{summary.get('final')}`",
        f"- aim: `{summary.get('aimMode')}` pose: `{summary.get('poseSource')}` root: `{summary.get('rootRva')}`",
        f"- warmMs: `{summary.get('poseWarmMs')}` sourceStart: `{(summary.get('start') or {}).get('source')}`",
        "",
    ]
    for L in legs:
        md.append(f"## Leg `{L.get('id')}` — {L.get('verdict')} dist={L.get('finalDistToGoal'):.2f}")
        for s in L.get("steps") or []:
            md.append(
                f"- step {s['index']}: dist={s.get('distToGoal'):.2f}→{s.get('distAfter')} "
                f"moved={s.get('movedPlanar')} click={s.get('click')}"
            )
        md.append("")
    (run_dir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "verdict": summary.get("verdict"),
                    "blockers": summary.get("blockers"),
                    "warnings": summary.get("warnings"),
                    "start": summary.get("start"),
                    "goals": summary.get("goals"),
                    "legsArrived": summary.get("legsArrived"),
                    "legsTotal": summary.get("legsTotal"),
                    "final": summary.get("final"),
                    "finalDistToGoal": summary.get("finalDistToGoal"),
                    "arrived": summary.get("arrived"),
                    "rrapicoordWarmMs": summary.get("rrapicoordWarmMs"),
                    "apiStartMs": summary.get("apiStartMs"),
                    "apiStartSource": (summary.get("start") or {}).get("source"),
                    "legs": [
                        {
                            "id": L.get("id"),
                            "verdict": L.get("verdict"),
                            "arrived": L.get("arrived"),
                            "finalDistToGoal": L.get("finalDistToGoal"),
                            "stepCount": len(L.get("steps") or []),
                        }
                        for L in legs
                    ],
                    "runDirectory": str(run_dir),
                    "safety": summary.get("safety"),
                },
                indent=2,
            )
        )
    else:
        print(summary["status"], summary.get("verdict"), run_dir)
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
