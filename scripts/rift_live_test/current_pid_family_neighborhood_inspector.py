from __future__ import annotations

import argparse
import ctypes
import json
import math
import struct
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_preflight import normalize_hwnd


SCHEMA_VERSION = 1
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip(), 0)
        except ValueError:
            return None
    return None


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):X}"


def load_json(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def coordinate_from_mapping(value: Any) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    result: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        raw = value.get(axis, value.get(axis.upper()))
        if raw is None or isinstance(raw, bool):
            return None
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(parsed):
            return None
        result[axis] = parsed
    return result


def add(left: Mapping[str, float], right: Mapping[str, float]) -> dict[str, float]:
    return {axis: float(left[axis]) + float(right[axis]) for axis in ("x", "y", "z")}


def max_abs_delta(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return max(abs(float(left[axis]) - float(right[axis])) for axis in ("x", "y", "z"))


def load_offset_profiles(readback_doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    raw_readbacks = readback_doc.get("readbacks")
    if not isinstance(raw_readbacks, list):
        return profiles
    for readback in raw_readbacks:
        if not isinstance(readback, Mapping):
            continue
        avg_offset = coordinate_from_mapping(readback.get("averageOffset"))
        address = parse_int(readback.get("address") or readback.get("addressHex"))
        if avg_offset is None:
            continue
        profiles.append(
            {
                "candidateId": readback.get("candidateId"),
                "sourceAddress": int_hex(address),
                "sourceAddressInt": address,
                "averageOffset": avg_offset,
                "classification": readback.get("classification"),
            }
        )
    return profiles


def known_candidate_addresses(candidate_doc: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    raw = candidate_doc.get("candidates") or candidate_doc.get("Candidates") or []
    result: dict[int, dict[str, Any]] = {}
    if not isinstance(raw, list):
        return result
    for index, candidate in enumerate(raw, start=1):
        if not isinstance(candidate, Mapping):
            continue
        address = parse_int(candidate.get("address") or candidate.get("addressHex"))
        if address is None:
            continue
        result[address] = {
            "candidateId": candidate.get("candidateId") or f"candidate-{index:03d}",
            "familyBase": candidate.get("familyBaseHex"),
            "rangeLabel": candidate.get("rangeLabel"),
        }
    return result


def open_process_for_read(pid: int) -> int:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, int(pid))
    if not handle:
        raise RuntimeError(f"OpenProcess failed:{ctypes.get_last_error()}")
    return int(handle)


def close_handle(handle: int) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle(ctypes.c_void_p(handle))


def read_memory(handle: int, address: int, size: int) -> bytes:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.ReadProcessMemory.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.ReadProcessMemory.restype = ctypes.c_bool
    buffer = (ctypes.c_ubyte * int(size))()
    read = ctypes.c_size_t()
    ok = bool(kernel32.ReadProcessMemory(ctypes.c_void_p(handle), ctypes.c_void_p(address), buffer, size, ctypes.byref(read)))
    if not ok:
        raise RuntimeError(f"ReadProcessMemory failed:{ctypes.get_last_error()}:address={int_hex(address)}")
    return bytes(buffer[: read.value])


def verify_hwnd_owner(hwnd: str, expected_pid: int) -> dict[str, Any]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd_int = int(hwnd, 0)
    owner = ctypes.c_ulong(0)
    is_window = bool(user32.IsWindow(ctypes.c_void_p(hwnd_int)))
    if is_window:
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd_int), ctypes.byref(owner))
    return {
        "requestedHwnd": normalize_hwnd(hwnd),
        "requestedHwndInt": hwnd_int,
        "isWindow": is_window,
        "ownerPid": int(owner.value) if is_window else None,
        "ownerMatchesExpectedPid": bool(is_window and int(owner.value) == int(expected_pid)),
    }


def unpack_triplet(data: bytes, offset: int) -> dict[str, float] | None:
    try:
        x, y, z = struct.unpack_from("<fff", data, offset)
    except struct.error:
        return None
    values = {"x": float(x), "y": float(y), "z": float(z)}
    if not all(math.isfinite(values[axis]) for axis in ("x", "y", "z")):
        return None
    if max(abs(values["x"]), abs(values["y"]), abs(values["z"])) > 100000:
        return None
    if max(abs(values["x"]), abs(values["y"]), abs(values["z"])) < 1:
        return None
    return values


def inspect_neighborhood_bytes(
    *,
    data: bytes,
    base_address: int,
    reference: Mapping[str, float],
    profiles: list[dict[str, Any]],
    known_addresses: Mapping[int, Mapping[str, Any]],
    stride: int,
    tolerance: float,
    max_hits: int,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for offset in range(0, max(0, len(data) - 11), max(1, int(stride))):
        address = base_address + offset
        memory_value = unpack_triplet(data, offset)
        if memory_value is None:
            continue
        best_profile = None
        best_corrected = None
        best_delta = None
        for profile in profiles:
            corrected = add(memory_value, profile["averageOffset"])
            delta = max_abs_delta(corrected, reference)
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_profile = profile
                best_corrected = corrected
        if best_delta is None or best_delta > tolerance:
            continue
        known = known_addresses.get(address)
        hits.append(
            {
                "address": int_hex(address),
                "addressInt": address,
                "offsetFromWindowBase": int_hex(offset),
                "memoryValue": memory_value,
                "offsetCorrectedValue": best_corrected,
                "offsetCorrectedMaxAbsDelta": best_delta,
                "matchedOffsetProfile": {
                    "candidateId": best_profile.get("candidateId") if best_profile else None,
                    "sourceAddress": best_profile.get("sourceAddress") if best_profile else None,
                    "averageOffset": best_profile.get("averageOffset") if best_profile else None,
                },
                "knownCandidate": dict(known) if known else None,
            }
        )
        if len(hits) >= max_hits:
            break
    return sorted(hits, key=lambda item: (float(item["offsetCorrectedMaxAbsDelta"]), int(item["addressInt"])))


def make_safety(*, target_memory_bytes_read: bool) -> dict[str, Any]:
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgLaunched": False,
        "debuggerAttached": False,
        "targetMemoryBytesRead": target_memory_bytes_read,
        "targetMemoryBytesWritten": False,
        "providerWrites": False,
        "githubConnectorWrites": False,
        "movementAllowed": False,
        "candidateOnly": True,
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Current PID family neighborhood inspector",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Center address: `{summary.get('scanWindow', {}).get('centerAddress')}`",
        f"- Window: `{summary.get('scanWindow', {}).get('baseAddress')}` + `{summary.get('scanWindow', {}).get('sizeBytes')}` bytes",
        f"- Hit count: `{summary.get('hitCount')}`",
        "",
        "## Hits",
        "",
        "| Address | Corrected delta | Known candidate | Matched offset profile |",
        "|---|---:|---|---|",
    ]
    for hit in summary.get("hits") or []:
        known = hit.get("knownCandidate") or {}
        profile = hit.get("matchedOffsetProfile") or {}
        lines.append(
            f"| `{hit.get('address')}` | `{hit.get('offsetCorrectedMaxAbsDelta')}` | "
            f"`{known.get('candidateId')}` | `{profile.get('candidateId')} @ {profile.get('sourceAddress')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "Read-only target memory scan. No x64dbg, no Cheat Engine, no input, no movement, no target memory writes, no proof promotion.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"current-pid-family-neighborhood-inspector-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only current-PID coordinate-family neighborhood inspector.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--candidate-json", type=Path, required=False)
    parser.add_argument("--readback-summary-json", type=Path, required=False)
    parser.add_argument("--pid", type=int, required=False)
    parser.add_argument("--hwnd", required=False)
    parser.add_argument("--center-address", required=False)
    parser.add_argument("--span-bytes", type=lambda value: int(value, 0), default=0x4000)
    parser.add_argument("--stride", type=int, default=4)
    parser.add_argument("--tolerance", type=float, default=0.25)
    parser.add_argument("--max-hits", type=int, default=200)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def synthetic_candidate_doc() -> dict[str, Any]:
    return {"candidates": [{"candidateId": "low", "addressHex": "0x1000"}, {"candidateId": "high", "addressHex": "0x1010"}]}


def synthetic_readback_doc() -> dict[str, Any]:
    return {
        "reference": {"x": 100.0, "y": 200.0, "z": 300.0},
        "readbacks": [
            {"candidateId": "low", "addressHex": "0x1000", "averageOffset": {"x": 5.0, "y": 5.0, "z": 5.0}},
            {"candidateId": "high", "addressHex": "0x1010", "averageOffset": {"x": -5.0, "y": -5.0, "z": -5.0}},
        ],
    }


def synthetic_memory() -> tuple[int, bytes]:
    base = 0x1000
    data = bytearray(0x40)
    struct.pack_into("<fff", data, 0x0, 95.0, 195.0, 295.0)
    struct.pack_into("<fff", data, 0x10, 105.0, 205.0, 305.0)
    return base, bytes(data)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = choose_run_dir(repo_root, args.output_root)
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    hits_json = run_dir / "hits.json"
    blockers: list[str] = []
    warnings: list[str] = []
    target_memory_bytes_read = False
    try:
        if args.self_test:
            candidate_doc = synthetic_candidate_doc()
            readback_doc = synthetic_readback_doc()
            base_address, data = synthetic_memory()
            center_address = base_address + 0x20
            target = {"selfTest": True}
        else:
            if args.candidate_json is None:
                raise ValueError("--candidate-json is required unless --self-test is used")
            if args.readback_summary_json is None:
                raise ValueError("--readback-summary-json is required unless --self-test is used")
            if args.pid is None:
                raise ValueError("--pid is required unless --self-test is used")
            if not args.hwnd:
                raise ValueError("--hwnd is required unless --self-test is used")
            center_address = parse_int(args.center_address)
            if center_address is None:
                raise ValueError("--center-address is required unless --self-test is used")
            candidate_doc = load_json(args.candidate_json)
            readback_doc = load_json(args.readback_summary_json)
            target = verify_hwnd_owner(args.hwnd, int(args.pid))
            if target.get("ownerMatchesExpectedPid") is not True:
                blockers.append("target-hwnd-owner-mismatch")
                data = b""
                base_address = center_address
            else:
                span = max(0x100, int(args.span_bytes))
                base_address = max(0, int(center_address) - span // 2)
                handle = open_process_for_read(int(args.pid))
                try:
                    data = read_memory(handle, base_address, span)
                    target_memory_bytes_read = True
                finally:
                    close_handle(handle)
        reference = coordinate_from_mapping(readback_doc.get("reference"))
        if reference is None:
            blockers.append("missing-readback-reference-coordinate")
            reference = {"x": 0.0, "y": 0.0, "z": 0.0}
        profiles = load_offset_profiles(readback_doc)
        if not profiles:
            blockers.append("missing-offset-profiles")
        known_addresses = known_candidate_addresses(candidate_doc)
        hits = [] if blockers else inspect_neighborhood_bytes(
            data=data,
            base_address=base_address,
            reference=reference,
            profiles=profiles,
            known_addresses=known_addresses,
            stride=max(1, int(args.stride)),
            tolerance=float(args.tolerance),
            max_hits=max(1, int(args.max_hits)),
        )
        if not hits and not blockers:
            warnings.append("no-offset-corrected-neighborhood-hits")
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "current-pid-family-neighborhood-inspector",
            "generatedAtUtc": utc_iso(),
            "status": "blocked" if blockers else "passed",
            "repoRoot": str(repo_root),
            "target": target,
            "scanWindow": {
                "centerAddress": int_hex(center_address),
                "baseAddress": int_hex(base_address),
                "sizeBytes": len(data),
                "stride": args.stride,
                "tolerance": args.tolerance,
            },
            "reference": reference,
            "offsetProfileCount": len(profiles),
            "knownCandidateCount": len(known_addresses),
            "hitCount": len(hits),
            "hits": hits,
            "blockers": blockers,
            "warnings": warnings,
            "safety": make_safety(target_memory_bytes_read=target_memory_bytes_read),
            "artifacts": {
                "runDirectory": str(run_dir),
                "summaryJson": str(summary_json),
                "summaryMarkdown": str(summary_md),
                "hitsJson": str(hits_json),
            },
            "next": {
                "recommendedAction": "Use neighborhood hits to infer structure layout only; still require static-owner/root provenance and ProofOnly before movement use.",
            },
        }
    except Exception as exc:  # noqa: BLE001
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "current-pid-family-neighborhood-inspector",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "repoRoot": str(repo_root),
            "errors": [f"{type(exc).__name__}:{exc}"],
            "blockers": blockers,
            "warnings": warnings,
            "safety": make_safety(target_memory_bytes_read=target_memory_bytes_read),
            "artifacts": {
                "runDirectory": str(run_dir),
                "summaryJson": str(summary_json),
                "summaryMarkdown": str(summary_md),
                "hitsJson": str(hits_json),
            },
        }
    write_json(hits_json, summary.get("hits", []))
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    if args.json:
        print(json.dumps({"status": summary["status"], "summaryJson": str(summary_json), "hitCount": summary.get("hitCount"), "blockers": summary.get("blockers", []), "warnings": summary.get("warnings", [])}, separators=(",", ":")))
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary_json}")
        print(f"hitCount={summary.get('hitCount')}")
    return 2 if summary["status"] == "blocked" else (1 if summary["status"] == "failed" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
