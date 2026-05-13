from __future__ import annotations

import argparse
import ctypes
import json
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .current_pid_family_neighborhood_inspector import (
    close_handle,
    open_process_for_read,
    read_memory,
    verify_hwnd_owner,
)
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_WINDOW_BYTES = 0x200
DEFAULT_MAX_REGION_BYTES = 0x200000
DEFAULT_MAX_MATCHES = 256
MEM_COMMIT = 0x1000


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


def parse_target_arg(value: str) -> dict[str, Any]:
    if ":" in value:
        address_text, label = value.split(":", 1)
    else:
        address_text = value
        label = value
    address = parse_int(address_text)
    if address is None:
        raise ValueError(f"invalid target address: {value}")
    return {"address": address, "addressHex": int_hex(address), "label": label.strip() or int_hex(address)}


def parse_targets(values: list[str]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    result: list[dict[str, Any]] = []
    for value in values:
        target = parse_target_arg(value)
        address = int(target["address"])
        if address in seen:
            continue
        seen.add(address)
        result.append(target)
    return result


class MemoryBasicInformation(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("PartitionId", ctypes.c_ushort),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]


def query_memory_region(handle: int, address: int) -> dict[str, Any]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.VirtualQueryEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(MemoryBasicInformation),
        ctypes.c_size_t,
    ]
    kernel32.VirtualQueryEx.restype = ctypes.c_size_t
    mbi = MemoryBasicInformation()
    result = kernel32.VirtualQueryEx(
        ctypes.c_void_p(handle),
        ctypes.c_void_p(address),
        ctypes.byref(mbi),
        ctypes.sizeof(mbi),
    )
    if not result:
        raise RuntimeError(f"VirtualQueryEx failed:{ctypes.get_last_error()}:address={int_hex(address)}")
    base = int(mbi.BaseAddress or 0)
    size = int(mbi.RegionSize or 0)
    return {
        "baseAddress": int_hex(base),
        "baseAddressInt": base,
        "allocationBase": int_hex(int(mbi.AllocationBase or 0)),
        "allocationProtect": int(mbi.AllocationProtect),
        "regionSize": size,
        "state": int(mbi.State),
        "protect": int(mbi.Protect),
        "type": int(mbi.Type),
        "containsOwnerAddress": base <= address < base + size,
        "committed": int(mbi.State) == MEM_COMMIT,
    }


def unpack_u64(data: bytes, offset: int) -> int | None:
    try:
        return struct.unpack_from("<Q", data, offset)[0]
    except struct.error:
        return None


def classify_pointer_value(
    value: int,
    *,
    targets_by_address: dict[int, dict[str, Any]],
    target_window_base: int | None,
    target_window_size: int,
    near_target_bytes: int,
    module_base: int | None,
    module_size: int,
    module_name: str,
    include_module_pointers: bool,
) -> dict[str, Any]:
    exact = targets_by_address.get(value)
    in_window = False
    window_offset = None
    if target_window_base is not None and target_window_size > 0:
        in_window = target_window_base <= value < target_window_base + target_window_size
        if in_window:
            window_offset = value - target_window_base
    nearest = None
    nearest_delta = None
    for target in targets_by_address.values():
        delta = int(value) - int(target["address"])
        abs_delta = abs(delta)
        if nearest_delta is None or abs_delta < nearest_delta:
            nearest_delta = abs_delta
            nearest = {
                "target": target["addressHex"],
                "label": target.get("label"),
                "delta": int_hex(delta) if delta >= 0 else f"-0x{abs(delta):X}",
                "absDelta": abs_delta,
            }
    near_target = bool(nearest is not None and nearest_delta is not None and nearest_delta <= near_target_bytes)
    module_pointer = None
    if module_base is not None and module_size > 0 and module_base <= value < module_base + module_size:
        module_pointer = {
            "moduleName": module_name,
            "moduleBase": int_hex(module_base),
            "rva": int_hex(value - module_base),
        }
    return {
        "exactTarget": {"address": exact["addressHex"], "label": exact.get("label")} if exact else None,
        "inTargetWindow": in_window,
        "targetWindowOffset": int_hex(window_offset),
        "nearTarget": near_target,
        "nearestTarget": nearest if near_target else None,
        "modulePointer": module_pointer,
        "interesting": bool(exact or in_window or near_target or (include_module_pointers and module_pointer)),
    }


def iter_qwords(data: bytes, *, base_address: int, stride: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(0, max(0, len(data) - 7), max(1, int(stride))):
        value = unpack_u64(data, offset)
        if value is None:
            continue
        rows.append({"address": base_address + offset, "offset": offset, "value": value})
    return rows


def analyze_qwords(
    *,
    data: bytes,
    base_address: int,
    owner_address: int,
    targets: list[dict[str, Any]],
    target_window_base: int | None,
    target_window_size: int,
    near_target_bytes: int,
    module_base: int | None,
    module_size: int,
    module_name: str,
    include_module_pointers: bool,
    owner_window_bytes: int,
    stride: int,
    max_matches: int,
) -> dict[str, Any]:
    targets_by_address = {int(target["address"]): target for target in targets}
    exact_counts = {target["addressHex"]: 0 for target in targets}
    region_matches: list[dict[str, Any]] = []
    owner_window: list[dict[str, Any]] = []
    owner_start = owner_address - owner_window_bytes
    owner_end = owner_address + owner_window_bytes
    for row in iter_qwords(data, base_address=base_address, stride=stride):
        value = int(row["value"])
        classification = classify_pointer_value(
            value,
            targets_by_address=targets_by_address,
            target_window_base=target_window_base,
            target_window_size=target_window_size,
            near_target_bytes=near_target_bytes,
            module_base=module_base,
            module_size=module_size,
            module_name=module_name,
            include_module_pointers=include_module_pointers,
        )
        address = int(row["address"])
        entry = {
            "address": int_hex(address),
            "addressInt": address,
            "offsetFromReadBase": int_hex(int(row["offset"])),
            "offsetFromOwner": int_hex(address - owner_address) if address >= owner_address else f"-0x{owner_address - address:X}",
            "value": int_hex(value),
            "valueInt": value,
            "classification": classification,
        }
        if owner_start <= address <= owner_end:
            owner_window.append(entry)
        exact = classification.get("exactTarget")
        if exact:
            exact_counts[str(exact["address"])] += 1
        if classification["interesting"] and len(region_matches) < max_matches:
            region_matches.append(entry)
    owner_window_module_pointers = [
        entry for entry in owner_window if (entry.get("classification") or {}).get("modulePointer")
    ]
    return {
        "exactTargetCounts": exact_counts,
        "modulePointerCount": sum(1 for match in region_matches if (match.get("classification") or {}).get("modulePointer")),
        "ownerWindowModulePointerCount": len(owner_window_module_pointers),
        "ownerWindowModulePointers": owner_window_module_pointers,
        "regionMatchCount": len(region_matches),
        "regionMatches": region_matches,
        "ownerWindowQwordCount": len(owner_window),
        "ownerWindow": owner_window,
    }


def choose_read_window(*, region: dict[str, Any], owner_address: int, max_region_bytes: int) -> dict[str, Any]:
    region_base = int(region["baseAddressInt"])
    region_size = int(region["regionSize"])
    if region_size <= max_region_bytes:
        return {
            "baseAddress": region_base,
            "sizeBytes": region_size,
            "clipped": False,
            "reason": "full-region",
        }
    half = max_region_bytes // 2
    start = max(region_base, owner_address - half)
    end = min(region_base + region_size, start + max_region_bytes)
    start = max(region_base, end - max_region_bytes)
    return {
        "baseAddress": start,
        "sizeBytes": end - start,
        "clipped": True,
        "reason": "region-larger-than-max-region-bytes",
    }


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
        "promotionEligible": False,
    }


def build_markdown(summary: dict[str, Any]) -> str:
    analysis = summary.get("analysis") or {}
    lines = [
        "# Pointer owner neighborhood inspector",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Owner/ref storage: `{summary.get('owner', {}).get('address')}`",
        f"- Region: `{summary.get('ownerRegion', {}).get('baseAddress')}` + `{summary.get('ownerRegion', {}).get('regionSize')}` bytes",
        f"- Read window: `{summary.get('readWindow', {}).get('baseAddress')}` + `{summary.get('readWindow', {}).get('sizeBytes')}` bytes",
        f"- Region match count: `{analysis.get('regionMatchCount')}`",
        f"- Owner-window module pointer count: `{analysis.get('ownerWindowModulePointerCount')}`",
        "",
        "## Exact target counts",
        "",
        "| Target | Count |",
        "|---|---:|",
    ]
    for target, count in (analysis.get("exactTargetCounts") or {}).items():
        lines.append(f"| `{target}` | `{count}` |")
    if analysis.get("ownerWindowModulePointers"):
        lines.extend(
            [
                "",
                "## Owner-window module pointer hints",
                "",
                "| Address | Offset from owner | Value | RVA |",
                "|---|---:|---|---|",
            ]
        )
        for match in analysis.get("ownerWindowModulePointers") or []:
            module_pointer = (match.get("classification") or {}).get("modulePointer") or {}
            lines.append(
                f"| `{match.get('address')}` | `{match.get('offsetFromOwner')}` | "
                f"`{match.get('value')}` | `{module_pointer.get('rva')}` |"
            )
    lines.extend(
        [
            "",
            "## Interesting matches",
            "",
            "| Address | Offset from owner | Value | Classification |",
            "|---|---:|---|---|",
        ]
    )
    for match in (analysis.get("regionMatches") or [])[:25]:
        classification = match.get("classification") or {}
        exact = classification.get("exactTarget") or {}
        label = exact.get("label")
        if not label and classification.get("inTargetWindow"):
            label = f"target-window+{classification.get('targetWindowOffset')}"
        if not label and classification.get("nearTarget"):
            nearest = classification.get("nearestTarget") or {}
            label = f"near {nearest.get('label')} {nearest.get('delta')}"
        lines.append(
            f"| `{match.get('address')}` | `{match.get('offsetFromOwner')}` | "
            f"`{match.get('value')}` | `{label}` |"
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
            "Read-only target memory inspection. No x64dbg, no Cheat Engine, no input, no movement, no memory writes, no proof promotion.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def synthetic_targets() -> list[dict[str, Any]]:
    return parse_targets(["0x5000:d20-base", "0x5010:d30-field", "0x56F0:sibling"])


def synthetic_memory() -> tuple[int, int, bytes]:
    base = 0x4000
    owner = 0x4100
    data = bytearray(0x300)
    struct.pack_into("<Q", data, owner - base, 0x5000)
    struct.pack_into("<Q", data, owner - base + 0x08, 0x5010)
    struct.pack_into("<Q", data, owner - base + 0x18, 0x56F0)
    struct.pack_into("<Q", data, 0x20, 0x5008)
    return base, owner, bytes(data)


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = args.output_root.resolve() if args.output_root else repo_root / "scripts" / "captures" / f"pointer-owner-neighborhood-inspector-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    matches_json = run_dir / "matches.json"
    blockers: list[str] = []
    warnings: list[str] = []
    target_memory_bytes_read = False
    try:
        if args.self_test:
            base_address, owner_address, data = synthetic_memory()
            owner_region = {
                "baseAddress": int_hex(base_address),
                "baseAddressInt": base_address,
                "regionSize": len(data),
                "containsOwnerAddress": True,
                "committed": True,
            }
            read_window = {"baseAddress": base_address, "sizeBytes": len(data), "clipped": False, "reason": "self-test"}
            targets = synthetic_targets()
            target = {"selfTest": True}
        else:
            if args.pid is None:
                raise ValueError("--pid is required unless --self-test is used")
            if not args.hwnd:
                raise ValueError("--hwnd is required unless --self-test is used")
            owner_address = parse_int(args.owner_address)
            if owner_address is None:
                raise ValueError("--owner-address is required unless --self-test is used")
            targets = parse_targets(args.target_address or [])
            if not targets:
                raise ValueError("at least one --target-address is required unless --self-test is used")
            target = verify_hwnd_owner(args.hwnd, int(args.pid))
            if target.get("ownerMatchesExpectedPid") is not True:
                blockers.append("target-hwnd-owner-mismatch")
                data = b""
                owner_region = {}
                read_window = {}
                base_address = owner_address
            else:
                handle = open_process_for_read(int(args.pid))
                try:
                    owner_region = query_memory_region(handle, owner_address)
                    if not owner_region.get("committed"):
                        blockers.append("owner-region-not-committed")
                    read_window = choose_read_window(
                        region=owner_region,
                        owner_address=owner_address,
                        max_region_bytes=max(0x100, int(args.max_region_bytes)),
                    )
                    base_address = int(read_window["baseAddress"])
                    data = read_memory(handle, base_address, int(read_window["sizeBytes"])) if not blockers else b""
                    target_memory_bytes_read = bool(data)
                finally:
                    close_handle(handle)
        target_window_base = parse_int(args.target_window_base)
        analysis = (
            {}
            if blockers
            else analyze_qwords(
                data=data,
                base_address=base_address,
                owner_address=owner_address,
                targets=targets,
                target_window_base=target_window_base,
                target_window_size=int(args.target_window_size),
                near_target_bytes=int(args.near_target_bytes),
                module_base=parse_int(args.module_base),
                module_size=int(args.module_size),
                module_name=str(args.module_name),
                include_module_pointers=bool(args.include_module_pointers),
                owner_window_bytes=int(args.owner_window_bytes),
                stride=max(1, int(args.stride)),
                max_matches=max(1, int(args.max_matches)),
            )
        )
        if not blockers and not (analysis.get("regionMatches") or []):
            warnings.append("no-interesting-owner-region-qword-matches")
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "pointer-owner-neighborhood-inspector",
            "generatedAtUtc": utc_iso(),
            "status": "blocked" if blockers else "passed",
            "repoRoot": str(repo_root),
            "target": target,
            "owner": {"address": int_hex(owner_address), "addressInt": owner_address},
            "targets": [{"address": target["addressHex"], "label": target.get("label")} for target in targets],
            "targetWindow": {
                "baseAddress": int_hex(target_window_base),
                "sizeBytes": int(args.target_window_size),
                "nearTargetBytes": int(args.near_target_bytes),
            },
            "moduleHintRange": {
                "moduleName": str(args.module_name),
                "moduleBase": int_hex(parse_int(args.module_base)),
                "moduleSize": int(args.module_size),
                "includeModulePointers": bool(args.include_module_pointers),
            },
            "ownerRegion": owner_region,
            "readWindow": {
                **read_window,
                "baseAddress": int_hex(read_window.get("baseAddress")) if read_window else None,
            },
            "analysis": analysis,
            "blockers": blockers,
            "warnings": warnings,
            "safety": make_safety(target_memory_bytes_read=target_memory_bytes_read),
            "artifacts": {
                "runDirectory": str(run_dir),
                "summaryJson": str(summary_json),
                "summaryMarkdown": str(summary_md),
                "matchesJson": str(matches_json),
            },
            "next": {
                "recommendedAction": "If matches remain heap-only, scan owner/ref storage chains and require module/static-owner evidence before resolver work.",
            },
        }
    except Exception as exc:  # noqa: BLE001
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "pointer-owner-neighborhood-inspector",
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
                "matchesJson": str(matches_json),
            },
        }
    write_json(matches_json, (summary.get("analysis") or {}).get("regionMatches") or [])
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only pointer owner/ref-storage neighborhood inspector.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--pid", type=int, required=False)
    parser.add_argument("--hwnd", required=False)
    parser.add_argument("--owner-address", required=False)
    parser.add_argument("--target-address", action="append", default=[])
    parser.add_argument("--target-window-base", default=None)
    parser.add_argument("--target-window-size", type=lambda value: int(value, 0), default=0x4000)
    parser.add_argument("--near-target-bytes", type=lambda value: int(value, 0), default=0x80)
    parser.add_argument("--module-base", default=None)
    parser.add_argument("--module-size", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--module-name", default="rift_x64.exe")
    parser.add_argument("--include-module-pointers", action="store_true")
    parser.add_argument("--owner-window-bytes", type=lambda value: int(value, 0), default=DEFAULT_WINDOW_BYTES)
    parser.add_argument("--max-region-bytes", type=lambda value: int(value, 0), default=DEFAULT_MAX_REGION_BYTES)
    parser.add_argument("--stride", type=int, default=8)
    parser.add_argument("--max-matches", type=int, default=DEFAULT_MAX_MATCHES)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "regionMatchCount": (summary.get("analysis") or {}).get("regionMatchCount"),
                    "exactTargetCounts": (summary.get("analysis") or {}).get("exactTargetCounts"),
                    "blockers": summary.get("blockers", []),
                    "warnings": summary.get("warnings", []),
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"regionMatchCount={(summary.get('analysis') or {}).get('regionMatchCount')}")
    return 2 if summary["status"] == "blocked" else (1 if summary["status"] == "failed" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
