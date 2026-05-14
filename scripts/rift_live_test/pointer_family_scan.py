from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_preflight import (
    enumerate_window_targets,
    normalize_hwnd,
    parse_utc_datetime,
    query_process_details,
    start_time_delta_seconds,
)


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"
DEFAULT_READER_DLL = Path(r"reader\RiftReader.Reader\bin\Debug\net10.0-windows\RiftReader.Reader.dll")
DEFAULT_CONTEXT_BYTES = 64
DEFAULT_MAX_HITS = 64
DEFAULT_DEPTH = 1
DEFAULT_MAX_NEXT_TARGETS = 24
DEFAULT_MAX_TOTAL_TARGETS = 96


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_int(value: str | int) -> int:
    if isinstance(value, int):
        return value
    return int(value.strip(), 0)


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):X}"


def safe_name(address: int) -> str:
    return f"{address:X}"


def parse_target_arg(value: str) -> dict[str, Any]:
    if ":" in value:
        address_text, label = value.split(":", 1)
    else:
        address_text = value
        label = value
    address = parse_int(address_text)
    return {"address": address, "addressHex": int_hex(address), "label": label.strip() or int_hex(address)}


def parse_targets(values: list[str]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    targets: list[dict[str, Any]] = []
    for value in values:
        target = parse_target_arg(value)
        address = int(target["address"])
        if address in seen:
            continue
        seen.add(address)
        targets.append(target)
    return targets


def load_target_file(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, list):
        raise ValueError("target file must be a JSON array")
    values: list[str] = []
    for item in document:
        if isinstance(item, str):
            values.append(item)
        elif isinstance(item, dict):
            address = item.get("address") or item.get("addressHex") or item.get("target")
            label = item.get("label") or item.get("name") or address
            if address:
                values.append(f"{address}:{label}")
    return parse_targets(values)


def module_for_address(address: int, modules: list[dict[str, Any]]) -> dict[str, Any] | None:
    for module in modules:
        base = int(module.get("BaseAddress") or parse_int(str(module.get("BaseAddressHex"))))
        size = int(module.get("ModuleMemorySize") or 0)
        if base <= address < base + size:
            return module
    return None


def load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return document


def validate_target(args: argparse.Namespace) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    expected_hwnd = normalize_hwnd(args.target_hwnd)
    selected = None
    for target in enumerate_window_targets(process_name=args.process_name, title_contains=args.title_contains):
        if int(target.get("pid") or -1) != int(args.target_pid):
            continue
        if normalize_hwnd(target.get("hwndHex") or target.get("hwnd")) != expected_hwnd:
            continue
        selected = target
        break
    if selected is None:
        blockers.append("target-window-not-found")
        return None, blockers, warnings
    if selected.get("responding") is False:
        blockers.append("target-not-responding")
    details = query_process_details(int(args.target_pid))
    selected["processDetails"] = details
    if args.expected_start_time_utc:
        delta = start_time_delta_seconds(details.get("startTimeUtc"), args.expected_start_time_utc)
        if delta is None or delta > args.start_time_tolerance_seconds:
            blockers.append(
                "process-start-time-mismatch:"
                f"actual={details.get('startTimeUtc')};expected={args.expected_start_time_utc};deltaSeconds={delta}"
            )
    if args.expected_module_base:
        actual = normalize_hwnd(details.get("moduleBaseAddressHex") or details.get("moduleBaseAddress"))
        expected = normalize_hwnd(args.expected_module_base)
        if actual != expected:
            blockers.append(f"module-base-mismatch:actual={actual};expected={expected}")
    return selected, blockers, warnings


def run_reader_json(reader_dll: Path, argv: list[str], *, timeout_seconds: int) -> dict[str, Any]:
    result = subprocess.run(
        ["dotnet", str(reader_dll), *argv],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    if result.returncode != 0:
        raise RuntimeError(f"reader-exit-{result.returncode}: {result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout)


def scan_pointer(
    *,
    reader_dll: Path,
    pid: int,
    target: dict[str, Any],
    context_bytes: int,
    max_hits: int,
    timeout_seconds: int,
    raw_dir: Path,
) -> dict[str, Any]:
    address = int(target["address"])
    started = time.monotonic()
    scan = run_reader_json(
        reader_dll,
        [
            "--pid",
            str(pid),
            "--scan-pointer",
            int_hex(address) or str(address),
            "--pointer-width",
            "8",
            "--scan-context",
            str(context_bytes),
            "--max-hits",
            str(max_hits),
            "--json",
        ],
        timeout_seconds=timeout_seconds,
    )
    elapsed = round(time.monotonic() - started, 3)
    scan["scanElapsedSeconds"] = elapsed
    scan["targetLabel"] = target.get("label")
    raw_path = raw_dir / f"scan-{safe_name(address)}.json"
    write_json(raw_path, scan)
    scan["artifactPath"] = str(raw_path)
    return scan


def scan_module_list(*, reader_dll: Path, pid: int, raw_dir: Path, timeout_seconds: int) -> dict[str, Any]:
    modules = run_reader_json(reader_dll, ["--pid", str(pid), "--list-modules", "--json"], timeout_seconds=timeout_seconds)
    path = raw_dir / "modules.json"
    write_json(path, modules)
    modules["artifactPath"] = str(path)
    return modules


def summarize_scan(scan: dict[str, Any], *, modules: list[dict[str, Any]], depth: int) -> dict[str, Any]:
    target = parse_int(str(scan.get("PointerTarget")))
    hits = scan.get("Hits") if isinstance(scan.get("Hits"), list) else []
    hit_items: list[dict[str, Any]] = []
    module_hit_count = 0
    rift_module_hit_count = 0
    for hit in hits:
        address = int(hit.get("Address") or parse_int(str(hit.get("AddressHex"))))
        module = module_for_address(address, modules)
        if module:
            module_hit_count += 1
            if str(module.get("ModuleName") or "").lower() == "rift_x64.exe":
                rift_module_hit_count += 1
        hit_items.append(
            {
                "address": int_hex(address),
                "regionBase": hit.get("RegionBaseHex"),
                "module": module.get("ModuleName") if module else None,
                "moduleBase": module.get("BaseAddressHex") if module else None,
                "asciiPreview": (hit.get("Context") or {}).get("AsciiPreview"),
            }
        )
    return {
        "target": int_hex(target),
        "targetLabel": scan.get("targetLabel"),
        "depth": depth,
        "hitCount": int(scan.get("HitCount") or len(hits)),
        "moduleHitCount": module_hit_count,
        "riftModuleHitCount": rift_module_hit_count,
        "scanElapsedSeconds": scan.get("scanElapsedSeconds"),
        "artifactPath": scan.get("artifactPath"),
        "hits": hit_items,
        "candidateOnly": True,
        "promotionEligible": False,
    }


def rank_summaries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def score(item: dict[str, Any]) -> tuple[int, int, int, int]:
        return (
            int(item.get("riftModuleHitCount") or 0),
            int(item.get("moduleHitCount") or 0),
            min(int(item.get("hitCount") or 0), 64),
            -int(item.get("depth") or 0),
        )

    return sorted(items, key=score, reverse=True)


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Pointer family scan",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Target PID: `{summary.get('target', {}).get('pid')}`",
        f"- Target HWND: `{summary.get('target', {}).get('hwndHex')}`",
        f"- Seed count: `{summary.get('counts', {}).get('seedCount')}`",
        f"- Scanned target count: `{summary.get('counts', {}).get('scannedTargetCount')}`",
        f"- Candidate-only: `{str(summary.get('safety', {}).get('candidateOnly')).lower()}`",
        "",
        "## Ranked targets",
        "",
        "| Rank | Target | Label | Depth | Hits | Module hits | rift_x64 hits |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for index, item in enumerate(summary.get("rankedTargets") or [], start=1):
        lines.append(
            f"| {index} | `{item.get('target')}` | `{item.get('targetLabel')}` | "
            f"`{item.get('depth')}` | `{item.get('hitCount')}` | `{item.get('moduleHitCount')}` | "
            f"`{item.get('riftModuleHitCount')}` |"
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
            "This helper runs read-only pointer scans through RiftReader.Reader. It does not send game input, attach x64dbg, set breakpoints, or promote a pointer chain.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run_scan(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = args.output_root.resolve() if args.output_root else repo_root / "scripts" / "captures" / f"pointer-family-scan-{utc_stamp()}"
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"

    reader_dll = args.reader_dll
    if not reader_dll.is_absolute():
        reader_dll = repo_root / reader_dll

    blockers: list[str] = []
    warnings: list[str] = []
    if not reader_dll.is_file():
        blockers.append(f"reader-dll-missing:{reader_dll}")
    target, target_blockers, target_warnings = validate_target(args)
    blockers.extend(target_blockers)
    warnings.extend(target_warnings)
    targets = parse_targets(args.target_address or [])
    if args.target_file:
        targets.extend(load_target_file(args.target_file))
        targets = parse_targets([f"{item['addressHex']}:{item.get('label')}" for item in targets])
    if not targets:
        blockers.append("no-target-addresses")

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "pointer-family-scan",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "started",
        "repoRoot": str(repo_root),
        "target": target,
        "inputs": {
            "readerDll": str(reader_dll),
            "depth": args.depth,
            "maxHits": args.max_hits,
            "contextBytes": args.context_bytes,
            "maxNextTargets": args.max_next_targets,
        },
        "counts": {
            "seedCount": len(targets),
            "scannedTargetCount": 0,
            "queuedTargetCount": len(targets),
        },
        "rankedTargets": [],
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": {
            "runDirectory": str(run_dir),
            "rawDirectory": str(raw_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "safety": {
            "gameInputSent": False,
            "movementSent": False,
            "x64dbgAttached": False,
            "breakpointsSet": False,
            "targetMemoryWritten": False,
            "readOnlyProcessMemoryScan": True,
            "candidateOnly": True,
            "promotionEligible": False,
        },
    }
    if blockers:
        write_json(summary_json, summary)
        write_text_atomic(summary_md, build_markdown(summary))
        return summary

    modules_doc = scan_module_list(reader_dll=reader_dll, pid=args.target_pid, raw_dir=raw_dir, timeout_seconds=args.timeout_seconds)
    modules = modules_doc.get("Modules") if isinstance(modules_doc.get("Modules"), list) else []
    started = time.monotonic()
    scanned: set[int] = set()
    queue: deque[tuple[dict[str, Any], int]] = deque((target_item, 0) for target_item in targets)
    scan_summaries: list[dict[str, Any]] = []
    while queue:
        if args.max_elapsed_seconds and time.monotonic() - started >= args.max_elapsed_seconds:
            warnings.append(f"max-elapsed-seconds-reached:{args.max_elapsed_seconds}")
            break
        if args.max_total_targets and len(scanned) >= args.max_total_targets:
            warnings.append(f"max-total-targets-reached:{args.max_total_targets}")
            break
        target_item, depth = queue.popleft()
        address = int(target_item["address"])
        if address in scanned:
            continue
        if depth > args.depth:
            continue
        scanned.add(address)
        try:
            scan = scan_pointer(
                reader_dll=reader_dll,
                pid=args.target_pid,
                target=target_item,
                context_bytes=args.context_bytes,
                max_hits=args.max_hits,
                timeout_seconds=args.timeout_seconds,
                raw_dir=raw_dir,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"scan-failed:{int_hex(address)}:{type(exc).__name__}:{exc}")
            continue
        item = summarize_scan(scan, modules=modules, depth=depth)
        scan_summaries.append(item)
        if depth < args.depth:
            hits = scan.get("Hits") if isinstance(scan.get("Hits"), list) else []
            for hit in hits[: args.max_next_targets]:
                hit_address = int(hit.get("Address") or parse_int(str(hit.get("AddressHex"))))
                if hit_address not in scanned:
                    queue.append(
                        (
                            {
                                "address": hit_address,
                                "addressHex": int_hex(hit_address),
                                "label": f"ref-storage-depth{depth + 1}-from-{int_hex(address)}",
                            },
                            depth + 1,
                        )
                    )
    ranked = rank_summaries(scan_summaries)
    summary["status"] = "passed"
    summary["counts"]["scannedTargetCount"] = len(scan_summaries)
    summary["counts"]["queuedTargetCount"] = len(scanned)
    summary["counts"]["remainingQueueCount"] = len(queue)
    summary["limits"] = {
        "depth": args.depth,
        "maxNextTargets": args.max_next_targets,
        "maxHits": args.max_hits,
        "maxTotalTargets": args.max_total_targets,
        "maxElapsedSeconds": args.max_elapsed_seconds,
    }
    summary["rankedTargets"] = ranked
    summary["warnings"] = warnings
    summary["moduleList"] = {
        "moduleCount": modules_doc.get("ModuleCount"),
        "artifactPath": modules_doc.get("artifactPath"),
    }
    summary["next"] = {
        "recommendedAction": "Use top ranked current-process owner leads as candidate-only follow-up targets; require restart validation before promotion.",
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only grouped pointer-family scan for current-process coordinate leads.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--reader-dll", type=Path, default=DEFAULT_READER_DLL)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--target-hwnd", required=True)
    parser.add_argument("--expected-start-time-utc", default=None)
    parser.add_argument("--start-time-tolerance-seconds", type=float, default=1.0)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--target-address", action="append", default=[])
    parser.add_argument("--target-file", type=Path, default=None)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--max-next-targets", type=int, default=DEFAULT_MAX_NEXT_TARGETS)
    parser.add_argument("--max-total-targets", type=int, default=DEFAULT_MAX_TOTAL_TARGETS)
    parser.add_argument("--max-elapsed-seconds", type=float, default=0.0)
    parser.add_argument("--context-bytes", type=int, default=DEFAULT_CONTEXT_BYTES)
    parser.add_argument("--max-hits", type=int, default=DEFAULT_MAX_HITS)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_scan(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "scannedTargetCount": summary["counts"]["scannedTargetCount"],
                    "topTarget": (summary.get("rankedTargets") or [{}])[0],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    return 2 if summary["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
