#!/usr/bin/env python3
"""Read the current static owner-coordinate chain candidate.

Candidate chain:
    [rift_x64 + 0x32EBC80] + 0x320

This is read-only current-session validation. Promotion still requires fresh
API-now vs chain-now plus restart/relog validation and explicit approval.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rift_live_test.current_pid_family_neighborhood_inspector import close_handle, open_process_for_read, read_memory, verify_hwnd_owner

DEFAULT_ROOT_RVA = 0x32EBC80
DEFAULT_COORD_OFFSET = 0x320
DEFAULT_EXPECTED_PROOF_ANCHOR = 0x23863A26E50


def int_hex(value: int | None) -> str | None:
    return None if value is None else f"0x{int(value):X}"


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def qword(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def triplet(data: bytes, offset: int = 0) -> dict[str, float]:
    x, y, z = struct.unpack_from("<fff", data, offset)
    return {"x": x, "y": y, "z": z}


def build_markdown(summary: dict[str, Any]) -> str:
    reads = summary.get("reads") if isinstance(summary.get("reads"), dict) else {}
    return "\n".join([
        "# Static owner-coordinate chain readback",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Chain",
        "",
        "`[rift_x64+0x32EBC80]+0x320`",
        "",
        "## Result",
        "",
        f"- Owner address: `{reads.get('ownerAddress')}`",
        f"- Owner vtable: `{reads.get('ownerVtable')}`",
        f"- Coordinate: `{reads.get('coordinate')}`",
        f"- Proof-anchor deltas: `{reads.get('deltasVsExpectedProofAnchor')}`",
        "",
        "## Promotion status",
        "",
        "Candidate only. Requires fresh API-now vs chain-now and restart/relog validation before promotion.",
    ]) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    out_dir = (Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures") / f"static-owner-coordinate-chain-readback-{utc_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    module_base = int(args.module_base, 0)
    root_rva = int(args.root_rva, 0)
    coord_offset = int(args.coord_offset, 0)
    expected_anchor = int(args.expected_proof_anchor, 0) if args.expected_proof_anchor else None
    root_address = module_base + root_rva
    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "static-owner-coordinate-chain-readback",
        "generatedAtUtc": datetime.now(UTC).isoformat(),
        "status": "failed",
        "verdict": None,
        "target": {"processName": args.process_name, "processId": int(args.pid), "targetWindowHandle": args.hwnd, "moduleBase": int_hex(module_base)},
        "candidate": {
            "rootModule": "rift_x64.exe",
            "rootRva": int_hex(root_rva),
            "rootAddress": int_hex(root_address),
            "coordinateOffset": int_hex(coord_offset),
            "chain": "[rift_x64+0x32EBC80]+0x320",
            "historicalTemplateMatch": "owner+0x320/+0x324/+0x328",
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
        "artifacts": {"outputDir": str(out_dir), "summaryJson": str(out_dir / "summary.json"), "summaryMarkdown": str(out_dir / "summary.md")},
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
        owner_address = qword(read_memory(handle, root_address, 8))
        owner_window = read_memory(handle, owner_address, max(0x380, coord_offset + 12))
        coordinate = triplet(owner_window, coord_offset)
        reads: dict[str, Any] = {
            "ownerAddress": int_hex(owner_address),
            "ownerVtable": int_hex(qword(owner_window, 0)),
            "ownerVtableRva": int_hex(qword(owner_window, 0) - module_base) if module_base <= qword(owner_window, 0) < module_base + 0x4000000 else None,
            "coordinate": coordinate,
            "ownerPreviewQwords": [int_hex(qword(owner_window, off)) for off in range(0, 0x90, 8)],
        }
        if expected_anchor is not None:
            proof = triplet(read_memory(handle, expected_anchor, 12))
            reads["expectedProofAnchorCoordinate"] = proof
            reads["deltasVsExpectedProofAnchor"] = {axis: abs(coordinate[axis] - proof[axis]) for axis in ("x", "y", "z")}
        summary["reads"] = reads
        max_delta = max(reads.get("deltasVsExpectedProofAnchor", {"x": 0, "y": 0, "z": 0}).values())
        if expected_anchor is None or max_delta <= float(args.tolerance):
            summary["status"] = "passed"
            summary["verdict"] = "static-module-root-owner-plus-0x320-coordinate-chain-resolved"
            summary["classification"] = "static-owner-layout-coordinate-chain-candidate-current-session"
            summary["warnings"].extend(["not-restart-validated", "not-promoted", "api-now-vs-chain-now-not-refreshed-in-this-helper"])
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "coordinate-mismatch-vs-expected-proof-anchor"
            summary["blockers"].append("coordinate-mismatch-vs-expected-proof-anchor")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "readback-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    finally:
        close_handle(handle)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read static owner-coordinate chain candidate")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--hwnd", required=True)
    parser.add_argument("--module-base", required=True)
    parser.add_argument("--root-rva", default=hex(DEFAULT_ROOT_RVA))
    parser.add_argument("--coord-offset", default=hex(DEFAULT_COORD_OFFSET))
    parser.add_argument("--expected-proof-anchor", default=hex(DEFAULT_EXPECTED_PROOF_ANCHOR))
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    summary = run(args)
    artifacts = summary["artifacts"]
    Path(artifacts["summaryJson"]).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    Path(artifacts["summaryMarkdown"]).write_text(build_markdown(summary), encoding="utf-8")
    compact = {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "classification": summary.get("classification"),
        "ownerAddress": summary.get("reads", {}).get("ownerAddress"),
        "coordinate": summary.get("reads", {}).get("coordinate"),
        "summaryJson": artifacts["summaryJson"],
        "summaryMarkdown": artifacts["summaryMarkdown"],
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }
    print(json.dumps(compact) if args.json else json.dumps(compact, indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
