#!/usr/bin/env python3
"""Run bounded x64dbg page-access probes until coordinate-copy evidence is captured.

This helper wraps the existing single-capture x64dbg helper.  It does not write
target memory, does not promote proof truth, and detaches after each underlying
capture.  It is intended for the current coordinate recovery lane where a page
contains many transient copy slots and the first page access is not always the
coordinate copy.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_SOURCE_OFFSET = 0x28
DEFAULT_REQUIRED_COPY_SIZE = 0x37


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return int(value, 0)


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{value:X}"


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    good_hits = summary.get("goodHitCount", 0)
    attempts = summary.get("attemptCount", 0)
    lines = [
        "# x64dbg coordinate-copy probe batch",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- PID/HWND: `{summary.get('target', {}).get('pid')}` / `{summary.get('target', {}).get('hwnd')}`",
        f"- Good hits: `{good_hits}` / attempts `{attempts}`",
        f"- Required copy size: `{summary.get('criteria', {}).get('requiredCopySizeHex')}`",
        f"- Breakpoint access: `{summary.get('criteria', {}).get('breakpointAccess')}`",
        f"- Source offset: `{summary.get('criteria', {}).get('sourceOffsetHex')}`",
        f"- Candidate-only: `{summary.get('truth', {}).get('candidateOnly')}`",
        "",
        "## Good hits",
        "",
    ]
    for hit in summary.get("goodHits", []):
        lines.extend(
            [
                f"- Capture: `{hit.get('captureSummaryJson')}`",
                f"  - RIP: `{hit.get('rip')}` `{hit.get('instruction')}`",
                f"  - Source: `{hit.get('sourceRegister')}` `{hit.get('sourceAddress')}` + `{hit.get('sourceOffsetHex')}` -> `{hit.get('sourceTriplet')}`",
                f"  - Destination base register: `{hit.get('destinationBaseRegister')}` `{hit.get('destinationBaseAddress')}`",
                f"  - Family scan: `{hit.get('familyScanSummaryJson')}`",
            ]
        )
    if not summary.get("goodHits"):
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Underlying x64dbg helper detaches after each capture.",
            "- Target memory writes/patches are not performed.",
            "- Evidence remains candidate-only until a separate proof gate promotes it.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_triplet_at_offset(memory_doc: dict[str, Any] | None, source_offset: int) -> dict[str, Any] | None:
    if not isinstance(memory_doc, dict):
        return None
    wanted = int_hex(source_offset)
    for triplet in memory_doc.get("floatTriplets", []) or []:
        if not isinstance(triplet, dict):
            continue
        if str(triplet.get("offsetHex", "")).lower() == str(wanted).lower():
            return triplet
        try:
            if int(triplet.get("offset", -1)) == source_offset:
                return triplet
        except Exception:
            continue
    return None


def is_plausible_rift_coord(triplet: dict[str, Any] | None) -> bool:
    if not isinstance(triplet, dict):
        return False
    try:
        x = float(triplet["x"])
        y = float(triplet["y"])
        z = float(triplet["z"])
    except Exception:
        return False
    return 1000.0 <= x <= 20000.0 and -5000.0 <= y <= 5000.0 and 1000.0 <= z <= 20000.0


def register_int(registers: dict[str, Any], name: str) -> int | None:
    value = registers.get(name)
    if value is None:
        return None
    try:
        return int(str(value), 0)
    except Exception:
        return None


def extract_coord_copy_evidence(
    capture_summary: dict[str, Any],
    *,
    source_offset: int = DEFAULT_SOURCE_OFFSET,
    required_copy_size: int | None = DEFAULT_REQUIRED_COPY_SIZE,
) -> dict[str, Any]:
    contexts = capture_summary.get("contexts", [])
    context = contexts[-1] if contexts else {}
    registers = context.get("keyRegisters") if isinstance(context, dict) else {}
    registers = registers if isinstance(registers, dict) else {}
    register_memory = context.get("registerMemory") if isinstance(context, dict) else {}
    register_memory = register_memory if isinstance(register_memory, dict) else {}

    copy_size_values = {
        name: register_int(registers, name)
        for name in ("r8", "rbx", "rsi")
        if register_int(registers, name) is not None
    }
    copy_size_matched = (
        required_copy_size is None
        or any(value == required_copy_size for value in copy_size_values.values())
    )

    source_register = "rdx"
    source_memory = register_memory.get(source_register)
    source_triplet = find_triplet_at_offset(source_memory, source_offset)
    source_plausible = is_plausible_rift_coord(source_triplet)

    destination_base_register = None
    destination_base_address = None
    for name in ("r12", "rcx"):
        value = register_int(registers, name)
        if value is not None:
            destination_base_register = name
            destination_base_address = value
            break

    evidence = {
        "isGoodHit": bool(copy_size_matched and source_plausible),
        "reason": "matched" if copy_size_matched and source_plausible else "rejected",
        "copySizeMatched": copy_size_matched,
        "copySizeValues": {name: int_hex(value) for name, value in copy_size_values.items()},
        "requiredCopySizeHex": int_hex(required_copy_size),
        "sourceRegister": source_register,
        "sourceAddress": source_memory.get("address") if isinstance(source_memory, dict) else None,
        "sourceOffset": source_offset,
        "sourceOffsetHex": int_hex(source_offset),
        "sourceTriplet": source_triplet,
        "sourceTripletPlausible": source_plausible,
        "destinationBaseRegister": destination_base_register,
        "destinationBaseAddress": int_hex(destination_base_address),
        "rip": context.get("rip") if isinstance(context, dict) else None,
        "instruction": (context.get("ripDisassembly") or {}).get("instruction") if isinstance(context, dict) else None,
    }
    if not copy_size_matched:
        evidence["reason"] = "copy-size-mismatch"
    elif not source_plausible:
        evidence["reason"] = "source-triplet-not-plausible"
    return evidence


def run_command(command: list[str], *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "command": command,
            "exitCode": completed.returncode,
            "timedOut": False,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "exitCode": None,
            "timedOut": True,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }


def parse_json_stdout(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def build_capture_command(args: argparse.Namespace, repo_root: Path) -> list[str]:
    command = [
        sys.executable,
        str(repo_root / "scripts" / "x64dbg_live_access_capture.py"),
        "--allow-live-debugger",
        "--capture-mode",
        "memory-access",
        "--target-pid",
        str(args.target_pid),
        "--target-hwnd",
        str(args.target_hwnd),
        "--process-start-time-utc",
        str(args.process_start_time_utc),
        "--candidate-address",
        str(args.candidate_address),
        "--breakpoint-access",
        str(args.breakpoint_access),
        "--read-size",
        str(args.read_size),
        "--breakpoint-timeout-seconds",
        str(args.breakpoint_timeout_seconds),
        "--detach-timeout-seconds",
        str(args.detach_timeout_seconds),
        "--max-live-attach-seconds",
        str(args.max_live_attach_seconds),
        "--max-go-attempts",
        "1",
        "--json",
    ]
    if args.expected_module_base:
        command.extend(["--expected-module-base", str(args.expected_module_base)])
    if args.candidate_evidence_file:
        command.extend(["--candidate-evidence-file", str(args.candidate_evidence_file)])
    if args.allow_game_input:
        command.append("--allow-game-input")
    if args.stimulus_key:
        command.extend(
            [
                "--stimulus-method",
                str(args.stimulus_method),
                "--stimulus-key",
                str(args.stimulus_key),
                "--stimulus-pulse-ms",
                str(args.stimulus_pulse_ms),
                "--stimulus-delay-ms",
                str(args.stimulus_delay_ms),
            ]
        )
    return command


def build_family_scan_command(args: argparse.Namespace, repo_root: Path, evidence: dict[str, Any]) -> list[str] | None:
    if not args.scan_family_on_good_hit:
        return None
    if not args.family_min_address or not args.family_max_address:
        return None
    triplet = evidence.get("sourceTriplet") or {}
    try:
        x = float(triplet["x"])
        y = float(triplet["y"])
        z = float(triplet["z"])
    except Exception:
        return None
    return [
        sys.executable,
        str(repo_root / "scripts" / "scan_current_pid_coordinate_family.py"),
        "--pid",
        str(args.target_pid),
        "--hwnd",
        str(args.target_hwnd),
        "--process-name",
        str(args.process_name),
        "--scan-stride",
        "1",
        "--min-address",
        str(args.family_min_address),
        "--max-address",
        str(args.family_max_address),
        "--reference-x",
        repr(x),
        "--reference-y",
        repr(y),
        "--reference-z",
        repr(z),
        "--tolerance",
        str(args.family_scan_tolerance),
        "--max-hits",
        str(args.family_scan_max_hits),
        "--max-seconds",
        str(args.family_scan_max_seconds),
        "--json",
    ]


def run_self_test() -> int:
    good_summary = {
        "contexts": [
            {
                "rip": "0x7FFC593F13EA",
                "ripDisassembly": {"instruction": "vmovdqu ymmword ptr ds:[rcx+r9*1-0x60], ymm1"},
                "keyRegisters": {"rdx": "0x1000", "r8": "0x37", "rbx": "0x37", "rsi": "0x37", "r12": "0x2000"},
                "registerMemory": {
                    "rdx": {
                        "address": "0x1000",
                        "floatTriplets": [
                            {"offset": 40, "offsetHex": "0x28", "x": 7406.1, "y": 871.7, "z": 3028.7}
                        ],
                    }
                },
            }
        ]
    }
    bad_summary = {
        "contexts": [
            {
                "keyRegisters": {"rdx": "0x1000", "r8": "0x4A", "r12": "0x2000"},
                "registerMemory": {
                    "rdx": {
                        "address": "0x1000",
                        "floatTriplets": [
                            {"offset": 40, "offsetHex": "0x28", "x": 7406.1, "y": 871.7, "z": 3028.7}
                        ],
                    }
                },
            }
        ]
    }
    good = extract_coord_copy_evidence(good_summary)
    bad = extract_coord_copy_evidence(bad_summary)
    if not good["isGoodHit"]:
        print(json.dumps({"status": "failed", "case": "good", "evidence": good}, indent=2))
        return 1
    if bad["isGoodHit"] or bad["reason"] != "copy-size-mismatch":
        print(json.dumps({"status": "failed", "case": "bad", "evidence": bad}, indent=2))
        return 1
    print(json.dumps({"status": "passed", "good": good, "bad": bad}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--target-pid", type=int)
    parser.add_argument("--target-hwnd")
    parser.add_argument("--process-start-time-utc")
    parser.add_argument("--expected-module-base")
    parser.add_argument("--candidate-address")
    parser.add_argument("--candidate-evidence-file", type=Path, default=None)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--min-good-hits", type=int, default=2)
    parser.add_argument("--source-offset", default=int_hex(DEFAULT_SOURCE_OFFSET))
    parser.add_argument("--required-copy-size", default=int_hex(DEFAULT_REQUIRED_COPY_SIZE))
    parser.add_argument("--breakpoint-access", choices=("read", "write"), default="read")
    parser.add_argument("--read-size", type=int, default=12)
    parser.add_argument("--allow-game-input", action="store_true")
    parser.add_argument("--stimulus-method", choices=("postmessage", "sendinput"), default="sendinput")
    parser.add_argument("--stimulus-key", default="W")
    parser.add_argument("--stimulus-pulse-ms", type=int, default=160)
    parser.add_argument("--stimulus-delay-ms", type=int, default=500)
    parser.add_argument("--breakpoint-timeout-seconds", type=int, default=10)
    parser.add_argument("--detach-timeout-seconds", type=int, default=10)
    parser.add_argument("--max-live-attach-seconds", type=int, default=25)
    parser.add_argument("--scan-family-on-good-hit", action="store_true")
    parser.add_argument("--family-min-address")
    parser.add_argument("--family-max-address")
    parser.add_argument("--family-scan-tolerance", type=float, default=0.35)
    parser.add_argument("--family-scan-max-hits", type=int, default=250)
    parser.add_argument("--family-scan-max-seconds", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    missing = [
        name
        for name in ("target_pid", "target_hwnd", "process_start_time_utc", "candidate_address")
        if getattr(args, name) in (None, "")
    ]
    if missing:
        parser.error(f"missing required arguments for live batch: {', '.join('--' + name.replace('_', '-') for name in missing)}")
    if args.attempts < 1 or args.min_good_hits < 1:
        parser.error("--attempts and --min-good-hits must be positive")

    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_script()
    output_root = args.output_root.resolve() if args.output_root else repo_root / "scripts" / "captures"
    run_dir = output_root / f"x64dbg-coord-copy-batch-{args.target_pid}-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    source_offset = parse_int(args.source_offset)
    required_copy_size = parse_int(args.required_copy_size)
    assert source_offset is not None

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "x64dbg-coordinate-copy-probe-batch",
        "generatedAtUtc": utc_iso(),
        "status": "planned" if args.dry_run else "running",
        "target": {
            "processName": args.process_name,
            "pid": args.target_pid,
            "hwnd": str(args.target_hwnd),
            "processStartTimeUtc": args.process_start_time_utc,
            "expectedModuleBase": args.expected_module_base,
        },
        "criteria": {
            "sourceOffsetHex": int_hex(source_offset),
            "requiredCopySizeHex": int_hex(required_copy_size),
            "breakpointAccess": args.breakpoint_access,
            "minGoodHits": args.min_good_hits,
            "maxAttempts": args.attempts,
        },
        "truth": {
            "candidateOnly": True,
            "promotionEligible": False,
            "reason": "batch evidence is for source-pattern discovery only",
        },
        "safety": {
            "targetMemoryWritten": False,
            "targetMemoryPatched": False,
            "cheatEngineUsed": False,
            "x64dbgDetachedPerAttempt": True,
            "gameInputAllowed": bool(args.allow_game_input),
            "stimulusKey": args.stimulus_key if args.allow_game_input else None,
        },
        "attempts": [],
        "goodHits": [],
        "goodHitCount": 0,
        "attemptCount": 0,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
        "blockers": [],
        "warnings": [],
        "errors": [],
    }

    if args.dry_run:
        summary["plannedCaptureCommand"] = build_capture_command(args, repo_root)
        write_json(run_dir / "summary.json", summary)
        write_markdown(run_dir / "summary.md", summary)
        if args.json:
            print(json.dumps(summary, indent=2))
        return 0

    for attempt_index in range(1, args.attempts + 1):
        command = build_capture_command(args, repo_root)
        envelope = run_command(
            command,
            cwd=repo_root,
            timeout_seconds=max(30, args.max_live_attach_seconds + args.breakpoint_timeout_seconds + args.detach_timeout_seconds + 10),
        )
        parsed = parse_json_stdout(str(envelope.get("stdout") or ""))
        attempt_doc: dict[str, Any] = {
            "attempt": attempt_index,
            "command": command,
            "exitCode": envelope["exitCode"],
            "timedOut": envelope["timedOut"],
            "stdoutPreview": str(envelope.get("stdout") or "")[:2000],
            "stderrPreview": str(envelope.get("stderr") or "")[:2000],
            "captureSummaryJson": parsed.get("summaryJson") if parsed else None,
            "captureStatus": parsed.get("status") if parsed else None,
        }
        evidence: dict[str, Any] | None = None
        capture_summary: dict[str, Any] | None = None
        if parsed and parsed.get("summaryJson"):
            summary_path = Path(str(parsed["summaryJson"]))
            if summary_path.exists():
                capture_summary = json.loads(summary_path.read_text(encoding="utf-8"))
                evidence = extract_coord_copy_evidence(
                    capture_summary,
                    source_offset=source_offset,
                    required_copy_size=required_copy_size,
                )
                evidence["captureSummaryJson"] = str(summary_path)
                attempt_doc["evidence"] = evidence
        if evidence is None:
            attempt_doc["evidence"] = {"isGoodHit": False, "reason": "capture-summary-unavailable"}
        elif evidence.get("isGoodHit"):
            family_command = build_family_scan_command(args, repo_root, evidence)
            if family_command:
                family_envelope = run_command(family_command, cwd=repo_root, timeout_seconds=args.family_scan_max_seconds + 15)
                family_parsed = parse_json_stdout(str(family_envelope.get("stdout") or ""))
                evidence["familyScanCommand"] = family_command
                evidence["familyScanExitCode"] = family_envelope["exitCode"]
                evidence["familyScanTimedOut"] = family_envelope["timedOut"]
                evidence["familyScanSummaryJson"] = family_parsed.get("artifacts", {}).get("summaryJson") if family_parsed else None
                evidence["familyScanStatus"] = family_parsed.get("status") if family_parsed else None
                evidence["familyScanBestHit"] = family_parsed.get("scan", {}).get("bestHit") if family_parsed else None
            summary["goodHits"].append(evidence)
            summary["goodHitCount"] = len(summary["goodHits"])
        summary["attempts"].append(attempt_doc)
        summary["attemptCount"] = attempt_index
        write_json(run_dir / "summary.json", summary)
        write_markdown(run_dir / "summary.md", summary)
        if len(summary["goodHits"]) >= args.min_good_hits:
            break

    summary["status"] = "captured" if len(summary["goodHits"]) >= args.min_good_hits else "partial"
    if not summary["goodHits"]:
        summary["blockers"].append("no-coordinate-copy-like-write-hit-captured")
    elif len(summary["goodHits"]) < args.min_good_hits:
        summary["warnings"].append("fewer-good-hits-than-requested")
    write_json(run_dir / "summary.json", summary)
    write_markdown(run_dir / "summary.md", summary)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"status={summary['status']} goodHits={summary['goodHitCount']} summary={run_dir / 'summary.json'}")
    return 0 if summary["goodHits"] else 2


if __name__ == "__main__":
    sys.exit(main())
