#!/usr/bin/env python3
# Version: riftreader-scan-current-pid-coordinate-family-v0.1.0
# Total-Character-Count: 23899
# Purpose: Read-only current-PID memory family scan for float32 XYZ triplets near a fresh RRAPICOORD reference, with structured blocker logging and candidate JSON/JSONL output.

from __future__ import annotations

import argparse
import ctypes
import json
import math
import shutil
import struct
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
READABLE_PROTECTIONS = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}

if sys.platform != "win32":
    raise SystemExit("This helper requires Windows because it uses ReadProcessMemory.")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)


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


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
kernel32.VirtualQueryEx.restype = ctypes.c_size_t
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.GetProcessTimes.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
]
kernel32.GetProcessTimes.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "scripts").is_dir():
            return candidate
    raise RuntimeError(f"Could not find RiftReader repo root from {start}")


def win_error(label: str) -> str:
    code = ctypes.get_last_error()
    return f"{label}: win32={code}"


def parse_hwnd(value: str) -> int:
    text = str(value).strip()
    if text.lower().startswith("0x"):
        return int(text[2:], 16)
    return int(text, 10)


def format_hex(value: int) -> str:
    return f"0x{value:X}"


def resolve_powershell() -> str:
    for exe in ("pwsh", "powershell"):
        found = shutil.which(exe)
        if found:
            return found
    raise RuntimeError("Neither pwsh nor powershell was found on PATH.")


def run_command(args: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    started_utc = utc_iso()
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "args": args,
            "cwd": str(cwd),
            "startedAtUtc": started_utc,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(time.monotonic() - started, 3),
            "exitCode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timedOut": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "cwd": str(cwd),
            "startedAtUtc": started_utc,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(time.monotonic() - started, 3),
            "exitCode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timedOut": True,
            "timeoutSeconds": timeout_seconds,
        }


def extract_json(text: str) -> Any:
    value = (text or "").strip()
    if not value:
        raise RuntimeError("empty command output")
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    starts = [idx for idx in (value.find("{"), value.find("[")) if idx >= 0]
    if not starts:
        raise RuntimeError(f"no JSON object/array found; preview={value[:500]}")
    parsed, _ = json.JSONDecoder().raw_decode(value[min(starts):])
    return parsed


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_process_start_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:
        prefix, suffix = text.split(".", 1)
        tz_suffix = ""
        if "+" in suffix:
            fraction, tz_suffix = suffix.split("+", 1)
            tz_suffix = "+" + tz_suffix
        elif "-" in suffix:
            fraction, tz_suffix = suffix.split("-", 1)
            tz_suffix = "-" + tz_suffix
        else:
            fraction = suffix
        if len(fraction) > 6:
            text = f"{prefix}.{fraction[:6]}{tz_suffix}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def process_start_matches(actual_utc: Any, expected_utc: Any, *, tolerance_seconds: float = 2.0) -> bool:
    actual = parse_process_start_datetime(actual_utc)
    expected = parse_process_start_datetime(expected_utc)
    if actual is None or expected is None:
        return False
    return abs((actual - expected).total_seconds()) <= tolerance_seconds


def filetime_to_iso(filetime: FILETIME) -> str:
    value = (int(filetime.dwHighDateTime) << 32) + int(filetime.dwLowDateTime)
    unix_seconds = (value - 116444736000000000) / 10000000
    return datetime.fromtimestamp(unix_seconds, timezone.utc).isoformat()


def get_process_start_utc(handle: int) -> str | None:
    create = FILETIME()
    exit_time = FILETIME()
    kernel = FILETIME()
    user = FILETIME()
    ok = kernel32.GetProcessTimes(
        wintypes.HANDLE(handle),
        ctypes.byref(create),
        ctypes.byref(exit_time),
        ctypes.byref(kernel),
        ctypes.byref(user),
    )
    if not ok:
        return None
    return filetime_to_iso(create)


def is_readable_region(mbi: MEMORY_BASIC_INFORMATION) -> bool:
    if mbi.State != MEM_COMMIT:
        return False
    if mbi.Protect & PAGE_GUARD:
        return False
    if mbi.Protect & PAGE_NOACCESS:
        return False
    return (mbi.Protect & 0xFF) in READABLE_PROTECTIONS


def open_process(pid: int) -> int:
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        raise RuntimeError(win_error(f"OpenProcess failed for PID {pid}"))
    return int(handle)


def close_handle(handle: int) -> None:
    if handle:
        kernel32.CloseHandle(wintypes.HANDLE(handle))


def query_process_image(handle: int) -> str | None:
    size = wintypes.DWORD(32768)
    buf = ctypes.create_unicode_buffer(size.value)
    ok = kernel32.QueryFullProcessImageNameW(wintypes.HANDLE(handle), 0, buf, ctypes.byref(size))
    if not ok:
        return None
    return buf.value


def verify_hwnd_owner(hwnd_text: str, expected_pid: int) -> dict[str, Any]:
    hwnd = parse_hwnd(hwnd_text)
    result: dict[str, Any] = {"requestedHwnd": hwnd_text, "requestedHwndInt": hwnd, "isWindow": False}
    if not user32.IsWindow(wintypes.HWND(hwnd)):
        result["blocker"] = "hwnd_not_window"
        return result
    owner = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(owner))
    result.update({"isWindow": True, "ownerPid": int(owner.value), "ownerMatchesExpectedPid": int(owner.value) == expected_pid})
    if int(owner.value) != expected_pid:
        result["blocker"] = f"hwnd_owner_pid_mismatch:actual={owner.value};expected={expected_pid}"
    return result


def enumerate_regions(handle: int, min_address: int, max_address: int) -> list[dict[str, int]]:
    regions: list[dict[str, int]] = []
    address = max(0, min_address)
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(MEMORY_BASIC_INFORMATION)
    while address < max_address:
        query_size = kernel32.VirtualQueryEx(wintypes.HANDLE(handle), ctypes.c_void_p(address), ctypes.byref(mbi), mbi_size)
        if not query_size:
            address += 0x10000
            continue
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize or 0)
        if size <= 0:
            address += 0x10000
            continue
        if base + size <= min_address:
            address = base + size
            continue
        if is_readable_region(mbi):
            regions.append({"base": base, "size": size, "protect": int(mbi.Protect), "type": int(mbi.Type), "state": int(mbi.State)})
        next_addr = base + size
        address = next_addr if next_addr > address else address + 0x10000
    return regions


def read_memory(handle: int, address: int, size: int) -> bytes | None:
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(wintypes.HANDLE(handle), ctypes.c_void_p(address), buf, size, ctypes.byref(read))
    if not ok or read.value == 0:
        return None
    return buf.raw[: read.value]


def scan_buffer_for_xyz(
    data: bytes,
    base_addr: int,
    ref_x: float,
    ref_y: float,
    ref_z: float,
    tolerance: float,
    max_hits: int,
    region_base: int,
    scan_stride: int = 4,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    limit = len(data) - 12
    if limit < 0:
        return hits

    for offset in range(0, limit + 1, scan_stride):
        try:
            x, y, z = struct.unpack_from("<fff", data, offset)
        except struct.error:
            continue
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            continue
        dx = abs(float(x) - ref_x)
        dy = abs(float(y) - ref_y)
        dz = abs(float(z) - ref_z)
        max_abs = max(dx, dy, dz)
        if max_abs <= tolerance:
            absolute = base_addr + offset
            context_start = max(0, offset - 32)
            context_end = min(len(data), offset + 44)
            neighbor_floats = []
            aligned_start = context_start - (context_start % 4)
            for n_offset in range(aligned_start, context_end - 3, 4):
                try:
                    value = struct.unpack_from("<f", data, n_offset)[0]
                    if math.isfinite(value):
                        neighbor_floats.append({"relativeOffset": n_offset - offset, "value": value})
                except struct.error:
                    pass
            hits.append({
                "address": absolute,
                "addressHex": format_hex(absolute),
                "regionBase": region_base,
                "regionBaseHex": format_hex(region_base),
                "regionOffset": absolute - region_base,
                "regionOffsetHex": format_hex(absolute - region_base),
                "axisOrder": "xyz",
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "deltaX": float(x) - ref_x,
                "deltaY": float(y) - ref_y,
                "deltaZ": float(z) - ref_z,
                "maxAbsDelta": max_abs,
                "neighborFloats": neighbor_floats,
            })
            if len(hits) >= max_hits:
                return hits
    return hits


def capture_reference(repo_root: Path, run_dir: Path, pid: int, hwnd: str, process_name: str, timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any], Path]:
    ps = resolve_powershell()
    script = repo_root / "scripts" / "capture-rift-api-reference-coordinate.ps1"
    output = run_dir / "fresh-reference-coordinate.json"
    cmd = [
        ps, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
        "-ProcessName", process_name, "-ProcessId", str(pid), "-TargetWindowHandle", hwnd,
        "-OutputRoot", str(run_dir), "-OutputFile", str(output), "-ScanContextBytes", "16384", "-MaxHits", "512", "-Json",
    ]
    envelope = run_command(cmd, repo_root, timeout_seconds)
    if envelope["timedOut"] or envelope["exitCode"] != 0:
        raise RuntimeError(f"reference_capture_failed: exit={envelope['exitCode']}; timedOut={envelope['timedOut']}; stderr={envelope['stderr'][:500]}")
    parsed = extract_json(envelope["stdout"])
    if str(parsed.get("Status", "")).lower() != "captured":
        raise RuntimeError(f"reference_capture_not_captured: {parsed}")
    return parsed, envelope, output


def write_candidate_files(run_dir: Path, hits: list[dict[str, Any]], ref: dict[str, Any], pid: int, hwnd: str) -> tuple[Path, Path]:
    json_path = run_dir / "api-family-vec3-candidates.json"
    jsonl_path = run_dir / "api-family-vec3-candidates.jsonl"
    candidates = []
    for idx, hit in enumerate(sorted(hits, key=lambda h: h["maxAbsDelta"]), start=1):
        candidate_id = f"api-family-hit-{idx:06d}"
        score = max(0.0, 100000.0 - (float(hit["maxAbsDelta"]) * 100000.0))
        candidates.append({
            "schema_version": "riftreader.api_family_vec3_candidate.v1",
            "candidate_id": candidate_id,
            "base_address_hex": hit["regionBaseHex"],
            "offset_hex": hit["regionOffsetHex"],
            "x_offset_hex": hit["regionOffsetHex"],
            "y_offset_hex": format_hex(hit["regionOffset"] + 4),
            "z_offset_hex": format_hex(hit["regionOffset"] + 8),
            "absolute_address_hex": hit["addressHex"],
            "axis_order": "xyz",
            "value_preview": [hit["x"], hit["y"], hit["z"]],
            "best_memory_x": hit["x"],
            "best_memory_y": hit["y"],
            "best_memory_z": hit["z"],
            "best_max_abs_distance": hit["maxAbsDelta"],
            "score_total": score,
            "rank_score": score,
            "support_count": 1,
            "classification": "api-reference-family-scan",
            "validation_status": "reference_match_candidate",
            "truth_readiness": "candidate_only_not_movement_proof",
            "process_id": pid,
            "target_window_handle": hwnd,
            "reference_coordinate": ref,
            "neighbor_floats": hit["neighborFloats"],
        })
    write_json(json_path, {"schemaVersion": 1, "mode": "riftreader-api-family-vec3-candidates", "generatedAtUtc": utc_iso(), "processId": pid, "targetWindowHandle": hwnd, "reference": ref, "candidateCount": len(candidates), "candidates": candidates})
    jsonl_path.write_text("\n".join(json.dumps(item) for item in candidates) + ("\n" if candidates else ""), encoding="utf-8")
    return json_path, jsonl_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only current-PID coordinate family scan.")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--hwnd", required=True)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--reference-file", default=None)
    parser.add_argument("--reference-x", type=float, default=None)
    parser.add_argument("--reference-y", type=float, default=None)
    parser.add_argument("--reference-z", type=float, default=None)
    parser.add_argument("--module-base", default=None)
    parser.add_argument("--expected-process-start-utc", default=None)
    parser.add_argument("--tolerance", type=float, default=0.25)
    parser.add_argument("--max-hits", type=int, default=200)
    parser.add_argument("--chunk-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--scan-stride", type=int, choices=(1, 4), default=4)
    parser.add_argument("--min-address", default="0x0")
    parser.add_argument("--max-address", default="0x7FFFFFFFFFFF")
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--reference-timeout-seconds", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    run_dir = repo_root / "scripts" / "captures" / f"family-scan-currentpid-{args.pid}-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "family-scan-summary.json"
    markdown_path = run_dir / "family-scan-summary.md"

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "riftreader-current-pid-coordinate-family-scan",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "processName": args.process_name,
        "processId": args.pid,
        "targetWindowHandle": args.hwnd,
        "target": {
            "pid": args.pid,
            "hwnd": args.hwnd,
            "moduleBase": args.module_base,
            "expectedProcessStartUtc": args.expected_process_start_utc,
            "processIdentityVerified": False,
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "githubConnectorWrites": False,
            "providerWrites": False,
        },
        "artifacts": {"runDirectory": str(run_dir), "summaryJson": str(summary_path), "summaryMarkdown": str(markdown_path)},
        "scan": {},
        "next": {},
    }

    return_code = 1
    try:
        if args.self_test:
            summary["status"] = "passed"
            summary["warnings"].append("self-test only; no live process scan executed")
            return_code = 0
            return return_code

        hwnd_info = verify_hwnd_owner(args.hwnd, args.pid)
        summary["target"].update(hwnd_info)
        if hwnd_info.get("blocker"):
            summary["status"] = "blocked"
            summary["blockers"].append(str(hwnd_info["blocker"]))
            return_code = 2
            return return_code

        handle = open_process(args.pid)
        try:
            actual_start = get_process_start_utc(handle)
            summary["target"]["actualProcessStartUtc"] = actual_start
            if args.expected_process_start_utc:
                if not actual_start:
                    summary["status"] = "blocked"
                    summary["blockers"].append("process-start-unavailable")
                    return_code = 2
                    return return_code
                if not process_start_matches(actual_start, args.expected_process_start_utc):
                    summary["status"] = "blocked"
                    summary["blockers"].append("process-start-mismatch")
                    return_code = 2
                    return return_code
                summary["target"]["processIdentityVerified"] = True
            else:
                summary["warnings"].append("process-start-not-bound-pass---expected-process-start-utc-for-exact-target-safety")

            image = query_process_image(handle)
            summary["target"]["processImage"] = image
            if image and args.process_name.lower() not in Path(image).stem.lower():
                summary["warnings"].append(f"process image does not obviously match process name: {image}")

            if args.reference_file:
                ref_doc = load_json_file(Path(args.reference_file))
                coord = ref_doc.get("coordinate") or ref_doc.get("Coordinate") or ref_doc
                ref_x = float(coord.get("x", coord.get("X")))
                ref_y = float(coord.get("y", coord.get("Y")))
                ref_z = float(coord.get("z", coord.get("Z")))
                reference = {"X": ref_x, "Y": ref_y, "Z": ref_z, "Source": "reference-file", "ReferenceFile": str(Path(args.reference_file).resolve())}
            elif args.reference_x is not None and args.reference_y is not None and args.reference_z is not None:
                ref_x, ref_y, ref_z = float(args.reference_x), float(args.reference_y), float(args.reference_z)
                reference = {"X": ref_x, "Y": ref_y, "Z": ref_z, "Source": "manual-arguments"}
            else:
                parsed_ref, command_envelope, ref_file = capture_reference(repo_root, run_dir, args.pid, args.hwnd, args.process_name, args.reference_timeout_seconds)
                summary["commandEnvelopes"] = {"referenceCapture": {k: v for k, v in command_envelope.items() if k not in {"stdout", "stderr"}}}
                summary["commandEnvelopes"]["referenceCapture"]["stdoutPreview"] = command_envelope["stdout"][:2000]
                summary["commandEnvelopes"]["referenceCapture"]["stderrPreview"] = command_envelope["stderr"][:2000]
                coord = parsed_ref.get("Coordinate") or {}
                ref_x = float(coord["X"])
                ref_y = float(coord["Y"])
                ref_z = float(coord["Z"])
                reference = parsed_ref.get("Coordinate", {})
                reference["Source"] = "fresh-rrapicoord"
                reference["ReferenceFile"] = str(ref_file)

            summary["reference"] = reference

            if args.dry_run:
                summary["status"] = "blocked"
                summary["warnings"].append("dry-run requested; no memory scan executed")
                summary["next"]["recommendedAction"] = "Run without --dry-run to scan readable committed memory."
                return_code = 2
                return return_code

            min_address = int(str(args.min_address), 0)
            max_address = int(str(args.max_address), 0)
            regions = enumerate_regions(handle, min_address=min_address, max_address=max_address)
            summary["scan"]["readableRegionCount"] = len(regions)
            summary["scan"]["tolerance"] = args.tolerance
            summary["scan"]["maxHits"] = args.max_hits
            summary["scan"]["scanStride"] = args.scan_stride
            summary["scan"]["minAddress"] = format_hex(min_address)
            summary["scan"]["maxAddress"] = format_hex(max_address)

            started = time.monotonic()
            hits: list[dict[str, Any]] = []
            read_failures = 0
            chunks_read = 0
            bytes_scanned = 0

            for region in regions:
                if time.monotonic() - started > args.max_seconds:
                    summary["warnings"].append(f"scan time budget reached at {args.max_seconds}s")
                    break
                base = region["base"]
                size = region["size"]
                offset = 0
                overlap = b""
                overlap_bytes = 11 if args.scan_stride == 1 else 8
                while offset < size:
                    if time.monotonic() - started > args.max_seconds:
                        break
                    read_size = min(args.chunk_bytes, size - offset)
                    address = base + offset
                    data = read_memory(handle, address, read_size)
                    if data is None:
                        read_failures += 1
                        offset += read_size
                        overlap = b""
                        continue
                    chunks_read += 1
                    bytes_scanned += len(data)
                    scan_data = overlap + data
                    scan_base = address - len(overlap)
                    hits.extend(scan_buffer_for_xyz(scan_data, scan_base, ref_x, ref_y, ref_z, args.tolerance, max(0, args.max_hits - len(hits)), base, scan_stride=args.scan_stride))
                    if len(hits) >= args.max_hits:
                        break
                    overlap = data[-overlap_bytes:] if len(data) >= overlap_bytes else data
                    offset += read_size
                if len(hits) >= args.max_hits:
                    break

            json_path, jsonl_path = write_candidate_files(run_dir, hits, reference, args.pid, args.hwnd)
            summary["status"] = "passed" if hits else "blocked"
            if not hits:
                summary["blockers"].append("no_xyz_triplets_near_reference_found")
                summary["next"]["recommendedAction"] = "Increase tolerance/time budget or inspect alternate axis/order/object-family strategy."
                return_code = 2
            else:
                summary["next"]["recommendedAction"] = "Use api-family-vec3-candidates.jsonl as explicit candidate file for readback/proof-pose validation; movement remains blocked."
                return_code = 0

            summary["scan"].update({
                "durationSeconds": round(time.monotonic() - started, 3),
                "chunksRead": chunks_read,
                "bytesScanned": bytes_scanned,
                "readFailures": read_failures,
                "hitCount": len(hits),
                "bestHit": min(hits, key=lambda h: h["maxAbsDelta"]) if hits else None,
            })
            summary["artifacts"].update({"candidateJson": str(json_path), "candidateJsonl": str(jsonl_path)})
            return return_code
        finally:
            close_handle(handle)

    except Exception as exc:
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        return_code = 1
        return return_code
    finally:
        write_json(summary_path, summary)
        markdown_path.write_text("\n".join([
            "# Current-PID coordinate family scan",
            "",
            f"- Status: `{summary.get('status')}`",
            f"- PID/HWND: `{args.pid}` / `{args.hwnd}`",
            f"- Blockers: `{', '.join(summary.get('blockers') or [])}`",
            f"- Hit count: `{summary.get('scan', {}).get('hitCount')}`",
            f"- Candidate JSONL: `{summary.get('artifacts', {}).get('candidateJsonl')}`",
            "",
            "Movement remains blocked. This helper sends no input and uses no Cheat Engine.",
            "",
        ]), encoding="utf-8")
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("=== FAMILY SCAN RESULT ===")
            print(json.dumps({
                "status": summary.get("status"),
                "blockers": summary.get("blockers"),
                "hitCount": summary.get("scan", {}).get("hitCount"),
                "candidateJsonl": summary.get("artifacts", {}).get("candidateJsonl"),
                "summaryJson": str(summary_path),
            }, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
