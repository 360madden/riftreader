#!/usr/bin/env python3
"""Read the current static playerPosition chain candidate.

Candidate chain discovered from the 2026-05-27 x64dbg access-provenance hit:
    [[rift_x64 + 0x32FFB68] + 0x0] + 0x40

This is a read-only validation helper. It does not attach a debugger, send input,
promote proof, or mutate provider repos.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rift_live_test.current_pid_family_neighborhood_inspector import (
    close_handle,
    open_process_for_read,
    read_memory,
    verify_hwnd_owner,
)

DEFAULT_ROOT_RVA = 0x32FFB68
DEFAULT_DESCRIPTOR_OFFSET = 0x0
DEFAULT_COORD_OFFSET = 0x40
DEFAULT_PROOF_ANCHOR = 0x23863A26E50


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):X}"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_qword(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def read_triplet(data: bytes, offset: int = 0) -> dict[str, float]:
    x, y, z = struct.unpack_from("<fff", data, offset)
    return {"x": x, "y": y, "z": z}


def ascii_preview(data: bytes, limit: int = 64) -> str:
    return "".join(chr(c) if 32 <= c < 127 else "." for c in data[:limit])


def build_markdown(summary: dict[str, Any]) -> str:
    reads = summary.get("reads") if isinstance(summary.get("reads"), dict) else {}
    safety = summary.get("safety") if isinstance(summary.get("safety"), dict) else {}
    lines = [
        "# Static playerPosition chain readback",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Chain",
        "",
        "`[[rift_x64+0x32FFB68]+0x0]+0x40`",
        "",
        "## Readback",
        "",
        f"- Root address: `{summary.get('candidate', {}).get('rootAddress')}`",
        f"- Root first pointer: `{reads.get('rootFirstPointer')}`",
        f"- Descriptor address: `{reads.get('descriptorAddress')}`",
        f"- Descriptor name: `{reads.get('descriptorName')}`",
        f"- Coordinate pointer: `{reads.get('coordinatePointer')}`",
        f"- Coordinate: `{reads.get('coordinate')}`",
        "",
        "## Safety",
        "",
    ]
    for key in ("movementSent", "inputSent", "noCheatEngine", "x64dbgAttach", "debugActiveProcessStopCalled", "providerWrites", "proofPromotion", "actorChainPromotion"):
        lines.append(f"- {key}: `{str(safety.get(key)).lower()}`")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    out_dir = (Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures") / f"static-playerposition-chain-readback-{utc_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_json = out_dir / "summary.json"
    summary_md = out_dir / "summary.md"

    root_address = int(args.module_base, 0) + int(args.root_rva, 0)
    expected_anchor = int(args.expected_anchor, 0) if args.expected_anchor else None
    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "static-playerposition-chain-readback",
        "generatedAtUtc": datetime.now(UTC).isoformat(),
        "status": "failed",
        "verdict": None,
        "target": {
            "processName": args.process_name,
            "processId": int(args.pid),
            "targetWindowHandle": args.hwnd,
            "moduleBase": int_hex(int(args.module_base, 0)),
        },
        "candidate": {
            "rootModule": "rift_x64.exe",
            "rootRva": int_hex(int(args.root_rva, 0)),
            "rootAddress": int_hex(root_address),
            "descriptorOffset": int_hex(int(args.descriptor_offset, 0)),
            "coordinateOffset": int_hex(int(args.coord_offset, 0)),
            "chain": "[[rift_x64+0x32FFB68]+0x0]+0x40",
            "expectedProofAnchor": int_hex(expected_anchor),
        },
        "reads": {},
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "debuggerAttached": False,
            "debugActiveProcessStopCalled": False,
            "targetMemoryBytesRead": True,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "gitMutation": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
        },
        "artifacts": {"outputDir": str(out_dir), "summaryJson": str(summary_json), "summaryMarkdown": str(summary_md)},
    }

    hwnd_check = verify_hwnd_owner(args.hwnd, int(args.pid))
    summary["target"]["hwndCheck"] = hwnd_check
    if not hwnd_check.get("ownerMatchesExpectedPid"):
        summary["status"] = "blocked"
        summary["verdict"] = "target-hwnd-pid-mismatch"
        summary["blockers"].append("target-hwnd-pid-mismatch")
        return summary

    handle = open_process_for_read(int(args.pid))
    try:
        root_bytes = read_memory(handle, root_address, 0x40)
        root_first_pointer = read_qword(root_bytes, 0)
        table_bytes = read_memory(handle, root_first_pointer, 0x90)
        descriptor_address = read_qword(table_bytes, int(args.descriptor_offset, 0))
        descriptor_bytes = read_memory(handle, descriptor_address, max(0x80, int(args.coord_offset, 0) + 8))
        coordinate_pointer = read_qword(descriptor_bytes, int(args.coord_offset, 0))
        coordinate_bytes = read_memory(handle, coordinate_pointer, 0x40)
        descriptor_name = descriptor_bytes[:0x20].split(b"\x00")[0].decode("ascii", "replace")

        summary["reads"] = {
            "rootQwords": [int_hex(read_qword(root_bytes, offset)) for offset in range(0, len(root_bytes), 8)],
            "rootFirstPointer": int_hex(root_first_pointer),
            "tableQwords": [int_hex(read_qword(table_bytes, offset)) for offset in range(0, len(table_bytes), 8)],
            "descriptorAddress": int_hex(descriptor_address),
            "descriptorName": descriptor_name,
            "descriptorAsciiPreview": ascii_preview(descriptor_bytes),
            "coordinatePointer": int_hex(coordinate_pointer),
            "coordinate": read_triplet(coordinate_bytes),
            "coordinateBytesHex": coordinate_bytes[:16].hex(),
            "expectedAnchorMatches": bool(expected_anchor is not None and coordinate_pointer == expected_anchor),
        }
        if expected_anchor is not None:
            proof_bytes = read_memory(handle, expected_anchor, 0x40)
            summary["reads"]["expectedAnchorCoordinate"] = read_triplet(proof_bytes)
        if descriptor_name == "playerPosition" and (expected_anchor is None or coordinate_pointer == expected_anchor):
            summary["status"] = "passed"
            summary["verdict"] = "static-module-root-playerPosition-chain-resolved"
            summary["classification"] = "static-proof/playerPosition-resolver-candidate-not-actor-owner"
            summary["warnings"].extend([
                "not-restart-validated",
                "not-actor-owner-layout",
                "promotion-requires-api-now-vs-chain-now-and-restart-validation",
            ])
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "chain-resolved-but-descriptor-or-anchor-mismatch"
            summary["blockers"].append("descriptor-or-anchor-mismatch")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "readback-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    finally:
        close_handle(handle)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read static playerPosition chain candidate")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--hwnd", required=True)
    parser.add_argument("--module-base", required=True)
    parser.add_argument("--root-rva", default=hex(DEFAULT_ROOT_RVA))
    parser.add_argument("--descriptor-offset", default=hex(DEFAULT_DESCRIPTOR_OFFSET))
    parser.add_argument("--coord-offset", default=hex(DEFAULT_COORD_OFFSET))
    parser.add_argument("--expected-anchor", default=hex(DEFAULT_PROOF_ANCHOR))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    summary = run(args)
    artifacts = summary.get("artifacts", {})
    summary_json = Path(artifacts["summaryJson"])
    summary_md = Path(artifacts["summaryMarkdown"])
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_md.write_text(build_markdown(summary), encoding="utf-8")
    compact = {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "classification": summary.get("classification"),
        "descriptorName": summary.get("reads", {}).get("descriptorName"),
        "coordinatePointer": summary.get("reads", {}).get("coordinatePointer"),
        "coordinate": summary.get("reads", {}).get("coordinate"),
        "summaryJson": str(summary_json),
        "summaryMarkdown": str(summary_md),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }
    if args.json:
        print(json.dumps(compact))
    else:
        print(json.dumps(compact, indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
