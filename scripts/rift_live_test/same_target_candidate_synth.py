from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        return None


def norm_hex(value: Any) -> str | None:
    parsed = parse_int(value)
    if parsed is not None:
        return f"0x{parsed:X}"
    text = str(value or "").strip()
    return text if text else None


def norm_hwnd(value: Any) -> str | None:
    return norm_hex(value)


def get_float(mapping: Mapping[str, Any], name: str) -> float | None:
    value = mapping.get(name)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def coordinate_from(value: Any) -> dict[str, float] | None:
    mapping = as_mapping(value)
    x = get_float(mapping, "x")
    y = get_float(mapping, "y")
    z = get_float(mapping, "z")
    if x is None:
        x = get_float(mapping, "X")
    if y is None:
        y = get_float(mapping, "Y")
    if z is None:
        z = get_float(mapping, "Z")
    if x is None or y is None or z is None:
        return None
    return {"x": x, "y": y, "z": z}


def readbacks_from(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = summary.get("readbacks")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def rank_key(readback: Mapping[str, Any]) -> tuple[float, float, int, str]:
    corrected = get_float(readback, "offsetCorrectedMaxAbsDelta")
    direct = get_float(readback, "directMaxAbsDelta")
    rank = parse_int(readback.get("rank"))
    address = norm_hex(readback.get("address") or readback.get("addressHex")) or ""
    return (
        corrected if corrected is not None else float("inf"),
        direct if direct is not None else float("inf"),
        rank if rank is not None else 999999,
        address,
    )


def synthesize_candidate(readback: Mapping[str, Any], index: int) -> dict[str, Any] | None:
    address_hex = norm_hex(readback.get("address") or readback.get("addressHex"))
    if not address_hex:
        return None
    memory_value = coordinate_from(readback.get("memoryValue"))
    if memory_value is None:
        return None
    candidate_id = str(readback.get("candidateId") or f"same-target-candidate-{index:06d}")
    candidate_id = candidate_id.replace("snapshot-delta-", "same-target-")
    corrected_delta = get_float(readback, "offsetCorrectedMaxAbsDelta")
    direct_delta = get_float(readback, "directMaxAbsDelta")
    return {
        "schema_version": "riftreader.same_target_offset_candidate.v1",
        "candidate_id": candidate_id,
        "source_base_address_hex": address_hex,
        "source_offset_hex": "0x0",
        "source_absolute_address_hex": address_hex,
        "base_address_hex": address_hex,
        "offset_hex": "0x0",
        "x_offset_hex": "0x0",
        "y_offset_hex": "0x4",
        "z_offset_hex": "0x8",
        "axis_order": "xyz",
        "classification": str(readback.get("classification") or "same-target-current-pid-candidate"),
        "validation_status": "same_target_offset_corrected_readback",
        "truth_readiness": "candidate_only_offset_corrected_not_movement_proof",
        "confidence_level": "candidate",
        "support_count": parse_int(readback.get("snapshotOffsetCount")) or 1,
        "best_max_abs_distance": corrected_delta,
        "direct_max_abs_delta": direct_delta,
        "offset_corrected_max_abs_delta": corrected_delta,
        "direct_within_tolerance": bool(readback.get("directWithinTolerance")),
        "offset_corrected_within_tolerance": bool(readback.get("offsetCorrectedWithinTolerance")),
        "best_memory_x": memory_value["x"],
        "best_memory_y": memory_value["y"],
        "best_memory_z": memory_value["z"],
        "value_preview": [memory_value["x"], memory_value["y"], memory_value["z"]],
        "average_offset": readback.get("averageOffset"),
        "offset_corrected_value": readback.get("offsetCorrectedValue"),
        "offset_spread": readback.get("offsetSpread"),
        "source_readback_rank": readback.get("rank"),
        "evidence_summary": (
            "Synthesized from same-target current-PID candidate readback. "
            "Direct value is not movement proof unless a fresh proof-pose readback matches API-now."
        ),
        "next_validation_step": "Run explicit read-only proof-pose/readback against a fresh API reference; do not navigate.",
    }


def build_summary(
    *,
    readback_summary_path: Path,
    process_id: int,
    target_window_handle: str,
    process_name: str,
    max_candidates: int,
) -> dict[str, Any]:
    readback_summary = load_json(readback_summary_path)
    blockers: list[str] = []
    warnings = [
        "Synthesized candidates are same-target candidate evidence only, not movement truth.",
        "Offset-corrected matches still require fresh API-now vs memory-now proof before promotion.",
    ]

    source_pid = parse_int(readback_summary.get("processId") or readback_summary.get("ProcessId"))
    source_hwnd = norm_hwnd(readback_summary.get("targetWindowHandle") or readback_summary.get("TargetWindowHandle"))
    expected_hwnd = norm_hwnd(target_window_handle)
    if source_pid is not None and source_pid != process_id:
        blockers.append(f"readback-pid-mismatch:actual={source_pid};expected={process_id}")
    if source_hwnd and expected_hwnd and source_hwnd.lower() != expected_hwnd.lower():
        blockers.append(f"readback-hwnd-mismatch:actual={source_hwnd};expected={expected_hwnd}")

    unique: dict[str, Mapping[str, Any]] = {}
    for readback in readbacks_from(readback_summary):
        if readback.get("status") not in (None, "read"):
            continue
        if readback.get("offsetCorrectedWithinTolerance") is not True and readback.get("directWithinTolerance") is not True:
            continue
        address_hex = norm_hex(readback.get("address") or readback.get("addressHex"))
        if not address_hex:
            continue
        current = unique.get(address_hex)
        if current is None or rank_key(readback) < rank_key(current):
            unique[address_hex] = readback

    ranked_readbacks = sorted(unique.values(), key=rank_key)
    candidates = [
        candidate
        for index, readback in enumerate(ranked_readbacks[:max_candidates], start=1)
        if (candidate := synthesize_candidate(readback, index)) is not None
    ]
    if not candidates and not blockers:
        blockers.append("no-same-target-offset-corrected-candidates")

    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "same-target-candidate-synthesis",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "inputs": {
            "readbackSummaryJson": str(readback_summary_path.resolve()),
            "processName": process_name,
            "processId": process_id,
            "targetWindowHandle": expected_hwnd or target_window_handle,
            "maxCandidates": max_candidates,
        },
        "source": {
            "processId": source_pid,
            "targetWindowHandle": source_hwnd,
            "candidateFile": readback_summary.get("candidateFile"),
            "referenceFile": as_mapping(readback_summary.get("artifacts")).get("referenceFile"),
            "readbackCount": len(readbacks_from(readback_summary)),
            "uniqueAddressCount": len(unique),
        },
        "counts": {
            "candidateCount": len(candidates),
            "directMatchCount": sum(1 for candidate in candidates if candidate.get("direct_within_tolerance")),
            "offsetCorrectedMatchCount": sum(1 for candidate in candidates if candidate.get("offset_corrected_within_tolerance")),
        },
        "topCandidate": candidates[0] if candidates else None,
        "candidatePacket": {
            "schemaVersion": 1,
            "mode": "riftreader-same-target-candidates",
            "generatedAtUtc": utc_iso(),
            "processName": process_name,
            "processId": process_id,
            "targetWindowHandle": expected_hwnd or target_window_handle,
            "candidate_count": len(candidates),
            "candidateCount": len(candidates),
            "sourceReadbackSummary": str(readback_summary_path.resolve()),
            "truth_readiness": "candidate_only_not_movement_proof",
            "warnings": warnings,
            "candidates": candidates,
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "githubConnectorWrites": False,
            "candidateOnly": True,
            "movementProofEligible": False,
        },
        "next": {
            "recommendedAction": "Use same-target-candidates.json only with explicit read-only proof/readback; do not promote movement truth.",
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Same-target candidate synthesis",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Source readback: `{as_mapping(summary.get('inputs')).get('readbackSummaryJson')}`",
        f"- Candidate count: `{as_mapping(summary.get('counts')).get('candidateCount')}`",
        "",
        "| Rank | Candidate | Address | Offset-corrected delta | Direct delta | Direct match |",
        "|---:|---|---|---:|---:|---:|",
    ]
    packet = as_mapping(summary.get("candidatePacket"))
    for index, candidate in enumerate(packet.get("candidates", []) if isinstance(packet.get("candidates"), list) else [], start=1):
        if not isinstance(candidate, Mapping):
            continue
        lines.append(
            f"| {index} | `{candidate.get('candidate_id')}` | `{candidate.get('source_absolute_address_hex')}` | "
            f"`{candidate.get('offset_corrected_max_abs_delta')}` | `{candidate.get('direct_max_abs_delta')}` | "
            f"`{str(candidate.get('direct_within_tolerance')).lower()}` |"
        )
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in summary.get("warnings", []) if warning)
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary.get("blockers", []) if blocker)
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synthesize an importable same-target candidate file from current-PID readback evidence.")
    parser.add_argument("--readback-summary-json", type=Path, required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--hwnd", required=True)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"same-target-candidate-synth-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    candidate_json = run_dir / "same-target-candidates.json"
    candidate_jsonl = run_dir / "same-target-candidates.jsonl"

    summary = build_summary(
        readback_summary_path=args.readback_summary_json,
        process_id=args.pid,
        target_window_handle=args.hwnd,
        process_name=args.process_name,
        max_candidates=max(1, args.max_candidates),
    )
    summary["repoRoot"] = str(repo_root)
    summary["artifacts"] = {
        "runDirectory": str(run_dir),
        "summaryJson": str(summary_json),
        "summaryMarkdown": str(summary_md),
        "candidateJson": str(candidate_json),
        "candidateJsonl": str(candidate_jsonl),
    }
    packet = dict(summary["candidatePacket"])
    packet["artifactSummaryJson"] = str(summary_json)
    write_json(summary_json, summary)
    write_json(candidate_json, packet)
    candidate_lines = [json.dumps(candidate) for candidate in packet.get("candidates", []) if isinstance(candidate, dict)]
    write_text_atomic(candidate_jsonl, "\n".join(candidate_lines) + ("\n" if candidate_lines else ""))
    write_text_atomic(summary_md, render_markdown(summary))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"status={summary.get('status')} summary={summary_json} candidates={candidate_json}")
    return 0 if summary.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
