#!/usr/bin/env python3
"""Build a read-only current-PID memory-region inventory and scan plan.

This helper intentionally does not read target memory bytes.  It uses
VirtualQueryEx metadata only, then writes a prioritized scan plan that can be
fed to scripts/scan_current_pid_coordinate_family.py.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import sys
from collections import Counter, defaultdict
from ctypes import wintypes
from pathlib import Path
from typing import Any

try:
    from .workflow_common import utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from workflow_common import utc_iso, utc_stamp, write_json  # type: ignore


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400

MEM_COMMIT = 0x1000
MEM_FREE = 0x10000
MEM_RESERVE = 0x2000
MEM_IMAGE = 0x1000000
MEM_MAPPED = 0x40000
MEM_PRIVATE = 0x20000

PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100
PAGE_NOCACHE = 0x200
PAGE_WRITECOMBINE = 0x400

READABLE_BASE_PROTECTIONS = {
    PAGE_READONLY,
    PAGE_READWRITE,
    PAGE_WRITECOPY,
    PAGE_EXECUTE_READ,
    PAGE_EXECUTE_READWRITE,
    PAGE_EXECUTE_WRITECOPY,
}


if sys.platform == "win32":
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
else:  # pragma: no cover - live mode is Windows-only, pure functions remain testable.
    kernel32 = None
    user32 = None


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


if sys.platform == "win32":
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.VirtualQueryEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(MEMORY_BASIC_INFORMATION),
        ctypes.c_size_t,
    ]
    kernel32.VirtualQueryEx.restype = ctypes.c_size_t
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "scripts").is_dir():
            return candidate
    raise RuntimeError(f"Could not find RiftReader repo root from {start}")


def format_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):X}"


def parse_hwnd(value: str) -> int:
    text = str(value).strip()
    return int(text, 16) if text.lower().startswith("0x") else int(text, 10)


def win_error(label: str) -> str:
    code = ctypes.get_last_error()
    return f"{label}: win32={code}"


def state_name(value: int) -> str:
    return {
        MEM_COMMIT: "commit",
        MEM_RESERVE: "reserve",
        MEM_FREE: "free",
    }.get(value, f"unknown-{value:#x}")


def type_name(value: int) -> str:
    return {
        MEM_IMAGE: "image",
        MEM_MAPPED: "mapped",
        MEM_PRIVATE: "private",
        0: "none",
    }.get(value, f"unknown-{value:#x}")


def protect_base(value: int) -> int:
    return int(value) & 0xFF


def protect_name(value: int) -> str:
    base = protect_base(value)
    names = {
        PAGE_NOACCESS: "noaccess",
        PAGE_READONLY: "readonly",
        PAGE_READWRITE: "readwrite",
        PAGE_WRITECOPY: "writecopy",
        PAGE_EXECUTE: "execute",
        PAGE_EXECUTE_READ: "execute-read",
        PAGE_EXECUTE_READWRITE: "execute-readwrite",
        PAGE_EXECUTE_WRITECOPY: "execute-writecopy",
    }
    parts = [names.get(base, f"unknown-{base:#x}")]
    if value & PAGE_GUARD:
        parts.append("guard")
    if value & PAGE_NOCACHE:
        parts.append("nocache")
    if value & PAGE_WRITECOMBINE:
        parts.append("writecombine")
    return "|".join(parts)


def is_readable_committed(region: dict[str, Any]) -> bool:
    protect = int(region.get("protect", 0))
    state = int(region.get("state", 0))
    if state != MEM_COMMIT:
        return False
    if protect & PAGE_GUARD:
        return False
    if protect_base(protect) == PAGE_NOACCESS:
        return False
    return protect_base(protect) in READABLE_BASE_PROTECTIONS


def score_region(region: dict[str, Any]) -> float:
    """Score likely coordinate-storage regions before any byte reads.

    This is a heuristic planner score only.  It must not be interpreted as
    memory truth.
    """

    if not is_readable_committed(region):
        return -1000.0

    base = int(region.get("base", 0))
    size = max(1, int(region.get("size", 0)))
    protect = protect_base(int(region.get("protect", 0)))
    mem_type = int(region.get("type", 0))
    score = 0.0

    if mem_type == MEM_PRIVATE:
        score += 90
    elif mem_type == MEM_MAPPED:
        score += 25
    elif mem_type == MEM_IMAGE:
        score -= 35

    if protect == PAGE_READWRITE:
        score += 90
    elif protect == PAGE_WRITECOPY:
        score += 45
    elif protect == PAGE_EXECUTE_READWRITE:
        score += 20
    elif protect == PAGE_READONLY:
        score += 10
    elif protect in {PAGE_EXECUTE_READ, PAGE_EXECUTE_WRITECOPY}:
        score -= 10

    # Historical RIFT coordinate candidates in this lane have repeatedly lived
    # in high private heap families (for example 0x1FF... in the prior PID).
    # Very high 0x7FF... ranges are more often module/stack-adjacent noise for
    # this specific current-PID recovery workflow.
    if 0x10000000000 <= base < 0x700000000000:
        score += 80
    elif 0x1000000000 <= base < 0x10000000000:
        score += 35
    elif base >= 0x700000000000:
        score -= 55

    # Prefer useful scan chunks over single guard-edge fragments without making
    # enormous ranges dominate solely because of size.
    size_mib = size / (1024 * 1024)
    if 0.03125 <= size_mib <= 128:
        score += min(35.0, 8.0 + math.log2(size_mib + 1.0) * 8.0)
    elif size_mib > 128:
        score += 10

    if base % 0x10000 == 0:
        score += 5

    return round(score, 3)


def normalize_region(raw: dict[str, Any]) -> dict[str, Any]:
    base = int(raw["base"])
    size = int(raw["size"])
    end = base + size
    normalized = {
        "base": base,
        "baseHex": format_hex(base),
        "end": end,
        "endHex": format_hex(end),
        "size": size,
        "sizeMiB": round(size / (1024 * 1024), 6),
        "allocationBase": int(raw.get("allocationBase") or base),
        "allocationBaseHex": format_hex(int(raw.get("allocationBase") or base)),
        "allocationProtect": int(raw.get("allocationProtect") or 0),
        "allocationProtectHex": format_hex(int(raw.get("allocationProtect") or 0)),
        "allocationProtectName": protect_name(int(raw.get("allocationProtect") or 0)),
        "state": int(raw.get("state") or 0),
        "stateName": state_name(int(raw.get("state") or 0)),
        "protect": int(raw.get("protect") or 0),
        "protectHex": format_hex(int(raw.get("protect") or 0)),
        "protectName": protect_name(int(raw.get("protect") or 0)),
        "type": int(raw.get("type") or 0),
        "typeHex": format_hex(int(raw.get("type") or 0)),
        "typeName": type_name(int(raw.get("type") or 0)),
    }
    normalized["readableCommitted"] = is_readable_committed(normalized)
    normalized["plannerScore"] = score_region(normalized)
    return normalized


def merge_regions_for_scan(regions: list[dict[str, Any]], max_gap: int = 0x10000) -> list[dict[str, Any]]:
    eligible = [
        r
        for r in regions
        if r.get("readableCommitted")
        and int(r.get("type", 0)) == MEM_PRIVATE
        and protect_base(int(r.get("protect", 0))) in {PAGE_READWRITE, PAGE_WRITECOPY, PAGE_EXECUTE_READWRITE}
        and int(r.get("plannerScore", -1000)) > 0
    ]
    eligible.sort(key=lambda r: (int(r.get("allocationBase") or r["base"]), int(r["base"])))

    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for region in eligible:
        allocation_base = int(region.get("allocationBase") or region["base"])
        base = int(region["base"])
        end = int(region["end"])
        if (
            current is not None
            and current["allocationBase"] == allocation_base
            and base <= int(current["maxAddress"]) + max_gap
        ):
            current["minAddress"] = min(int(current["minAddress"]), base)
            current["maxAddress"] = max(int(current["maxAddress"]), end)
            current["readableBytes"] += int(region["size"])
            current["regionCount"] += 1
            current["regionScores"].append(float(region["plannerScore"]))
            current["regions"].append(
                {
                    "baseHex": region["baseHex"],
                    "endHex": region["endHex"],
                    "sizeMiB": region["sizeMiB"],
                    "protectName": region["protectName"],
                }
            )
            continue

        current = {
            "allocationBase": allocation_base,
            "allocationBaseHex": format_hex(allocation_base),
            "minAddress": base,
            "minAddressHex": format_hex(base),
            "maxAddress": end,
            "maxAddressHex": format_hex(end),
            "readableBytes": int(region["size"]),
            "readableMiB": round(int(region["size"]) / (1024 * 1024), 6),
            "spanBytes": int(region["size"]),
            "spanMiB": round(int(region["size"]) / (1024 * 1024), 6),
            "regionCount": 1,
            "typeName": region["typeName"],
            "primaryProtectName": region["protectName"],
            "regionScores": [float(region["plannerScore"])],
            "regions": [
                {
                    "baseHex": region["baseHex"],
                    "endHex": region["endHex"],
                    "sizeMiB": region["sizeMiB"],
                    "protectName": region["protectName"],
                }
            ],
        }
        groups.append(current)

    for group in groups:
        group["minAddressHex"] = format_hex(int(group["minAddress"]))
        group["maxAddressHex"] = format_hex(int(group["maxAddress"]))
        group["spanBytes"] = int(group["maxAddress"]) - int(group["minAddress"])
        group["spanMiB"] = round(group["spanBytes"] / (1024 * 1024), 6)
        group["readableMiB"] = round(group["readableBytes"] / (1024 * 1024), 6)
        max_score = max(group["regionScores"]) if group["regionScores"] else 0.0
        group["plannerScore"] = round(
            max_score
            + min(35.0, math.log2(max(1, group["readableBytes"] / 4096)) * 4.0)
            + min(20.0, group["regionCount"] * 1.5),
            3,
        )
        del group["regionScores"]

    groups.sort(key=lambda g: (-float(g["plannerScore"]), int(g["minAddress"])))
    for index, group in enumerate(groups, 1):
        group["rank"] = index
        group["suggestedStride4Command"] = (
            "python scripts\\scan_current_pid_coordinate_family.py "
            "--pid {pid} --hwnd {hwnd} --tolerance 2.0 --scan-stride 4 "
            f"--min-address {group['minAddressHex']} --max-address {group['maxAddressHex']} "
            "--max-seconds 90 --json"
        )
        group["suggestedStride1Command"] = (
            "python scripts\\scan_current_pid_coordinate_family.py "
            "--pid {pid} --hwnd {hwnd} --tolerance 2.0 --scan-stride 1 "
            f"--min-address {group['minAddressHex']} --max-address {group['maxAddressHex']} "
            "--max-seconds 90 --json"
        )
    return groups


def summarize_regions(regions: list[dict[str, Any]]) -> dict[str, Any]:
    readable = [r for r in regions if r.get("readableCommitted")]
    return {
        "regionCount": len(regions),
        "readableCommittedCount": len(readable),
        "totalMiB": round(sum(int(r["size"]) for r in regions) / (1024 * 1024), 3),
        "readableCommittedMiB": round(sum(int(r["size"]) for r in readable) / (1024 * 1024), 3),
        "typeCounts": dict(Counter(str(r["typeName"]) for r in regions)),
        "protectionCounts": dict(Counter(str(r["protectName"]) for r in regions)),
    }


def open_process(pid: int) -> int:
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
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
    return buf.value if ok else None


def verify_hwnd_owner(hwnd_text: str, expected_pid: int) -> dict[str, Any]:
    hwnd = parse_hwnd(hwnd_text)
    result: dict[str, Any] = {
        "requestedHwnd": hwnd_text,
        "requestedHwndInt": hwnd,
        "requestedHwndHex": format_hex(hwnd),
        "isWindow": False,
    }
    if not user32.IsWindow(wintypes.HWND(hwnd)):
        result["blocker"] = "hwnd_not_window"
        return result
    owner = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(owner))
    result.update(
        {
            "isWindow": True,
            "ownerPid": int(owner.value),
            "ownerMatchesExpectedPid": int(owner.value) == int(expected_pid),
        }
    )
    if int(owner.value) != int(expected_pid):
        result["blocker"] = f"hwnd_owner_pid_mismatch:actual={owner.value};expected={expected_pid}"
    return result


def enumerate_regions(handle: int, min_address: int, max_address: int) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    address = max(0, int(min_address))
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(MEMORY_BASIC_INFORMATION)
    while address < max_address:
        query_size = kernel32.VirtualQueryEx(
            wintypes.HANDLE(handle),
            ctypes.c_void_p(address),
            ctypes.byref(mbi),
            mbi_size,
        )
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
        if base >= max_address:
            break
        regions.append(
            normalize_region(
                {
                    "base": base,
                    "size": min(size, max_address - base) if base + size > max_address else size,
                    "allocationBase": int(mbi.AllocationBase or base),
                    "allocationProtect": int(mbi.AllocationProtect),
                    "state": int(mbi.State),
                    "protect": int(mbi.Protect),
                    "type": int(mbi.Type),
                }
            )
        )
        next_address = base + size
        address = next_address if next_address > address else address + 0x10000
    return regions


def run_self_test() -> dict[str, Any]:
    fake_regions = [
        normalize_region(
            {
                "base": 0x7FF71CD90000,
                "size": 0x200000,
                "allocationBase": 0x7FF71CD90000,
                "allocationProtect": PAGE_EXECUTE_READ,
                "state": MEM_COMMIT,
                "protect": PAGE_EXECUTE_READ,
                "type": MEM_IMAGE,
            }
        ),
        normalize_region(
            {
                "base": 0x268FF472000,
                "size": 0x1F0000,
                "allocationBase": 0x268FF000000,
                "allocationProtect": PAGE_READWRITE,
                "state": MEM_COMMIT,
                "protect": PAGE_READWRITE,
                "type": MEM_PRIVATE,
            }
        ),
        normalize_region(
            {
                "base": 0x268FF662000,
                "size": 0x1A0000,
                "allocationBase": 0x268FF000000,
                "allocationProtect": PAGE_READWRITE,
                "state": MEM_COMMIT,
                "protect": PAGE_READWRITE,
                "type": MEM_PRIVATE,
            }
        ),
    ]
    merged = merge_regions_for_scan(fake_regions, max_gap=0x2000)
    errors: list[str] = []
    if not merged:
        errors.append("expected merged scan groups")
    elif merged[0]["allocationBaseHex"] != "0x268FF000000":
        errors.append(f"unexpected top allocation {merged[0]['allocationBaseHex']}")
    if fake_regions[1]["plannerScore"] <= fake_regions[0]["plannerScore"]:
        errors.append("heap private readwrite region did not outrank image execute-read region")
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "topGroup": merged[0] if merged else None,
        "topRegionScore": fake_regions[1]["plannerScore"],
        "imageRegionScore": fake_regions[0]["plannerScore"],
    }


def render_markdown(summary: dict[str, Any], top_plan: list[dict[str, Any]]) -> str:
    rows = []
    for item in top_plan[:20]:
        rows.append(
            "| {rank} | `{min}`-`{max}` | {mib} | {count} | {score} | `{alloc}` |".format(
                rank=item["rank"],
                min=item["minAddressHex"],
                max=item["maxAddressHex"],
                mib=item["spanMiB"],
                count=item["regionCount"],
                score=item["plannerScore"],
                alloc=item["allocationBaseHex"],
            )
        )
    return "\n".join(
        [
            "# Current-PID memory-region inventory",
            "",
            f"- Status: `{summary.get('status')}`",
            f"- PID/HWND: `{summary.get('processId')}` / `{summary.get('targetWindowHandle')}`",
            f"- Regions: `{summary.get('inventory', {}).get('regionCount')}`",
            f"- Readable committed MiB: `{summary.get('inventory', {}).get('readableCommittedMiB')}`",
            f"- Top scan-plan groups: `{len(top_plan)}`",
            "",
            "| Rank | Range | Span MiB | Regions | Score | Allocation |",
            "|---:|---|---:|---:|---:|---|",
            *rows,
            "",
            "This helper sends no input, reads no target memory bytes, uses no debugger, and uses no Cheat Engine.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only current-PID memory region inventory and scan planner.")
    parser.add_argument("--pid", type=int, required=False)
    parser.add_argument("--hwnd", required=False)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--top-count", type=int, default=20)
    parser.add_argument("--min-address", default="0x0")
    parser.add_argument("--max-address", default="0x7FFFFFFFFFFF")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    output_root = Path(args.output_root).resolve() if args.output_root else repo_root / "scripts" / "captures"
    run_label_pid = args.pid if args.pid is not None else "selftest"
    run_dir = output_root / f"memory-region-inventory-currentpid-{run_label_pid}-{utc_stamp()}"
    summary_path = run_dir / "summary.json"
    markdown_path = run_dir / "summary.md"
    regions_path = run_dir / "regions.json"
    scan_plan_path = run_dir / "scan-plan.json"

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "riftreader-current-pid-memory-region-inventory",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "processName": args.process_name,
        "processId": args.pid,
        "targetWindowHandle": args.hwnd,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "targetMemoryBytesReadOrWritten": False,
            "githubConnectorWrites": False,
            "providerWrites": False,
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_path),
            "summaryMarkdown": str(markdown_path),
            "regionsJson": str(regions_path),
            "scanPlanJson": str(scan_plan_path),
        },
        "next": {},
    }

    exit_code = 1
    regions: list[dict[str, Any]] = []
    scan_plan: list[dict[str, Any]] = []
    try:
        if args.self_test:
            self_test = run_self_test()
            summary["selfTest"] = self_test
            summary["status"] = self_test["status"]
            if self_test["status"] != "passed":
                summary["errors"].extend(self_test["errors"])
                exit_code = 1
            else:
                summary["warnings"].append("self-test only; no live process queried")
                exit_code = 0
            return exit_code

        if sys.platform != "win32":
            raise RuntimeError("live inventory requires Windows")
        if args.pid is None or args.hwnd is None:
            raise RuntimeError("--pid and --hwnd are required unless --self-test is used")

        hwnd_info = verify_hwnd_owner(args.hwnd, args.pid)
        summary["target"] = hwnd_info
        if hwnd_info.get("blocker"):
            summary["status"] = "blocked"
            summary["blockers"].append(str(hwnd_info["blocker"]))
            exit_code = 2
            return exit_code

        handle = open_process(args.pid)
        try:
            image = query_process_image(handle)
            summary["target"]["processImage"] = image
            if image and args.process_name.lower() not in Path(image).stem.lower():
                summary["warnings"].append(f"process image does not obviously match process name: {image}")
            min_address = int(str(args.min_address), 0)
            max_address = int(str(args.max_address), 0)
            regions = enumerate_regions(handle, min_address=min_address, max_address=max_address)
            scan_plan = merge_regions_for_scan(regions)[: max(1, args.top_count)]

            for group in scan_plan:
                group["suggestedStride4Command"] = group["suggestedStride4Command"].format(pid=args.pid, hwnd=args.hwnd)
                group["suggestedStride1Command"] = group["suggestedStride1Command"].format(pid=args.pid, hwnd=args.hwnd)

            top_regions = sorted(regions, key=lambda r: (-float(r["plannerScore"]), int(r["base"])))[: max(1, args.top_count)]
            for index, region in enumerate(top_regions, 1):
                region["rank"] = index

            inventory = summarize_regions(regions)
            inventory["topRegionCount"] = len(top_regions)
            inventory["scanPlanCount"] = len(scan_plan)
            inventory["minAddress"] = format_hex(min_address)
            inventory["maxAddress"] = format_hex(max_address)
            summary["inventory"] = inventory
            summary["topRegions"] = top_regions
            summary["status"] = "passed" if scan_plan else "blocked"
            if scan_plan:
                summary["next"]["recommendedAction"] = (
                    "Run scan_current_pid_coordinate_family.py against the top scan-plan ranges with a fresh API reference; "
                    "keep movement and x64dbg blocked until candidates exist."
                )
                exit_code = 0
            else:
                summary["blockers"].append("no_scan_plan_regions_found")
                summary["next"]["recommendedAction"] = "Recheck exact target or widen inventory address bounds."
                exit_code = 2
            return exit_code
        finally:
            close_handle(handle)

    except Exception as exc:
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        exit_code = 1
        return exit_code
    finally:
        write_json(regions_path, regions)
        write_json(scan_plan_path, {"topCount": args.top_count, "ranges": scan_plan})
        write_json(summary_path, summary)
        markdown_path.write_text(render_markdown(summary, scan_plan), encoding="utf-8")
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(
                json.dumps(
                    {
                        "status": summary.get("status"),
                        "blockers": summary.get("blockers"),
                        "summaryJson": str(summary_path),
                        "scanPlanJson": str(scan_plan_path),
                        "topRange": scan_plan[0] if scan_plan else None,
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    raise SystemExit(main())
