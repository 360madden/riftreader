#!/usr/bin/env python3
"""Read back post-update global-container coordinate candidates.

This helper consumes the candidate-only packet produced by
``postupdate_static_access_chain.py`` and re-reads any breadcrumb-global
container leads against the exact current PID/HWND target.  It is intended for
the no-movement post-update recovery lane:

- no input or movement;
- no debugger or Cheat Engine;
- no target memory writes;
- no current-truth/proof/actor-chain promotion.

The output is still candidate-only.  A matching current readback is useful
evidence, but movement/restart proof is still required before any consumer
navigation system can rely on it.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workflow_common import base_safety, repo_root as default_repo_root, utc_iso, utc_stamp, write_json  # noqa: E402
import postupdate_owner_root_rediscovery as rediscovery  # noqa: E402


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-postupdate-global-container-coordinate-readback-v0.1.0"
DEFAULT_TOLERANCE = 1.0
DEFAULT_CHILD_WINDOW_BYTES = 0x80
DEFAULT_INTERVAL_SECONDS = 0.2
DEFAULT_MAX_STATIONARY_PLANAR_DRIFT = 0.5
COORDINATE_LEAD_CLASSIFICATION = "global-container-child-coordinate-lead"


def parse_int(value: Any) -> int | None:
    return rediscovery.parse_int(value)


def hex_int(value: int | None) -> str | None:
    return rediscovery.hex_int(value)


def safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return data


def qword(data: bytes | None, offset: int = 0) -> int | None:
    if data is None or offset < 0 or offset + 8 > len(data):
        return None
    return int(struct.unpack_from("<Q", data, offset)[0])


def triplet(data: bytes | None, offset: int = 0) -> dict[str, float] | None:
    if data is None or offset < 0 or offset + 12 > len(data):
        return None
    x, y, z = struct.unpack_from("<fff", data, offset)
    values = {"x": float(x), "y": float(y), "z": float(z)}
    if not all(math.isfinite(value) for value in values.values()):
        return None
    return values


def coordinate_delta(coordinate: Mapping[str, float] | None, reference: Mapping[str, float] | None) -> dict[str, Any]:
    if coordinate is None or reference is None:
        return {"available": False}
    dx = float(coordinate["x"]) - float(reference["x"])
    dy = float(coordinate["y"]) - float(reference["y"])
    dz = float(coordinate["z"]) - float(reference["z"])
    return {
        "available": True,
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "maxAbsDelta": max(abs(dx), abs(dy), abs(dz)),
        "planarDelta": math.hypot(dx, dz),
    }


def classify_coordinate_read(coordinate: Mapping[str, float] | None, reference: Mapping[str, float] | None, tolerance: float) -> str:
    delta = coordinate_delta(coordinate, reference)
    if coordinate is None:
        return "candidate-chain-coordinate-unreadable"
    if reference is None:
        return "candidate-chain-current-readback-no-reference"
    if bool(delta.get("available")) and float(delta.get("maxAbsDelta") or 0.0) <= tolerance:
        return "candidate-coordinate-chain-current-readback"
    return "candidate-chain-readback-mismatch"


def chain_expression(global_rva: int, parent_offset: int, coordinate_offset: int) -> str:
    return (
        f"[[rift_x64+{hex_int(global_rva)}]+{hex_int(parent_offset)}]"
        f"+{hex_int(coordinate_offset)}/+{hex_int(coordinate_offset + 4)}/+{hex_int(coordinate_offset + 8)}"
    )


def extract_candidate_paths(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int]] = set()
    for sample in safe_list(packet.get("breadcrumbGlobalSamples")):
        global_sample = safe_mapping(sample)
        if global_sample.get("classification") != COORDINATE_LEAD_CLASSIFICATION:
            continue
        global_rva = parse_int(global_sample.get("globalRva"))
        if global_rva is None:
            continue
        for child in safe_list(global_sample.get("childPointerSamples")):
            child_sample = safe_mapping(child)
            parent_offset = parse_int(child_sample.get("parentOffset"))
            if parent_offset is None:
                continue
            for triple in safe_list(child_sample.get("nearWorldTriples")):
                triple_sample = safe_mapping(triple)
                coordinate_offset = parse_int(triple_sample.get("offset"))
                if coordinate_offset is None:
                    continue
                key = (global_rva, parent_offset, coordinate_offset)
                if key in seen:
                    continue
                seen.add(key)
                paths.append(
                    {
                        "globalRva": hex_int(global_rva),
                        "parentOffset": hex_int(parent_offset),
                        "coordinateOffset": hex_int(coordinate_offset),
                        "sourceFunctionRva": global_sample.get("sourceFunctionRva"),
                        "sourceInstructionRva": global_sample.get("sourceInstructionRva"),
                        "sourceInstruction": global_sample.get("sourceInstruction"),
                        "artifactMaxAbsDelta": triple_sample.get("maxAbsDelta"),
                        "chain": chain_expression(global_rva, parent_offset, coordinate_offset),
                    }
                )
    return paths


def packet_target(packet: Mapping[str, Any]) -> dict[str, Any]:
    target = safe_mapping(packet.get("target"))
    return {
        "pid": parse_int(target.get("pid") or target.get("processId")),
        "hwnd": target.get("hwnd") or target.get("targetWindowHandle"),
        "moduleBase": parse_int(target.get("moduleBase") or target.get("moduleBaseAddressHex")),
        "expectedProcessStartUtc": (
            target.get("expectedProcessStartUtc")
            or target.get("actualProcessStartUtc")
            or target.get("processStartUtc")
            or target.get("startTimeUtc")
        ),
    }


def read_candidate_paths(
    *,
    target: Mapping[str, Any],
    candidate_paths: Sequence[Mapping[str, Any]],
    reference: Mapping[str, float] | None,
    tolerance: float,
    child_window_bytes: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], list[str]]:
    from scan_current_pid_coordinate_family import close_handle, open_process, read_memory, verify_hwnd_owner  # noqa: E402

    blockers: list[str] = []
    warnings: list[str] = []
    pid = parse_int(target.get("pid"))
    hwnd = target.get("hwnd")
    module_base = parse_int(target.get("moduleBase"))
    expected_start = target.get("expectedProcessStartUtc")
    live_target: dict[str, Any] = {
        "pid": pid,
        "hwnd": hwnd,
        "moduleBase": hex_int(module_base),
        "expectedProcessStartUtc": expected_start,
        "liveGlobalContainerCoordinateRead": False,
    }
    if pid is None or not hwnd or module_base is None:
        blockers.append("target-fields-missing-for-global-container-readback")
        return live_target, [], blockers, warnings

    hwnd_check = verify_hwnd_owner(str(hwnd), int(pid))
    live_target["hwndCheck"] = hwnd_check
    if not bool(hwnd_check.get("ownerMatchesExpectedPid")):
        blockers.append("pid-hwnd-mismatch")
        return live_target, [], blockers, warnings

    handle = open_process(int(pid))
    try:
        actual_start = rediscovery.get_process_start_utc(handle)
        live_target["actualProcessStartUtc"] = actual_start
        if expected_start and actual_start:
            expected_prefix = str(expected_start).replace("Z", "+00:00")[:19]
            if not actual_start.startswith(expected_prefix):
                blockers.append("process-start-mismatch")
                return live_target, [], blockers, warnings

        reads: list[dict[str, Any]] = []
        for candidate in candidate_paths:
            row = safe_mapping(candidate)
            global_rva = parse_int(row.get("globalRva"))
            parent_offset = parse_int(row.get("parentOffset"))
            coordinate_offset = parse_int(row.get("coordinateOffset"))
            if global_rva is None or parent_offset is None or coordinate_offset is None:
                continue
            global_slot = int(module_base) + global_rva
            container_pointer = qword(read_memory(handle, global_slot, 8))
            child_slot = container_pointer + parent_offset if container_pointer is not None else None
            child_pointer = qword(read_memory(handle, child_slot, 8)) if child_slot is not None else None
            child_window_size = max(child_window_bytes, coordinate_offset + 12)
            child_window = read_memory(handle, child_pointer, child_window_size) if child_pointer else None
            coordinate = triplet(child_window, coordinate_offset)
            delta = coordinate_delta(coordinate, reference)
            classification = classify_coordinate_read(coordinate, reference, tolerance)
            reads.append(
                {
                    **row,
                    "globalSlotAddress": hex_int(global_slot),
                    "containerPointer": hex_int(container_pointer),
                    "childSlotAddress": hex_int(child_slot),
                    "childPointer": hex_int(child_pointer),
                    "coordinateAddress": hex_int(child_pointer + coordinate_offset if child_pointer is not None else None),
                    "coordinate": coordinate,
                    "deltaVsReference": delta,
                    "classification": classification,
                    "candidateOnly": True,
                    "promotionEligible": False,
                }
            )
        live_target["liveGlobalContainerCoordinateRead"] = True
        return live_target, reads, blockers, warnings
    finally:
        close_handle(handle)


def best_read(reads: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    def score(item: Mapping[str, Any]) -> tuple[int, float]:
        classification = str(item.get("classification") or "")
        delta = safe_mapping(item.get("deltaVsReference"))
        max_abs = float(delta.get("maxAbsDelta") if delta.get("maxAbsDelta") is not None else 1e12)
        return (0 if classification == "candidate-coordinate-chain-current-readback" else 1, max_abs)

    values = [safe_mapping(item) for item in reads]
    return min(values, key=score) if values else None


def polling_analysis(readbacks: Sequence[Mapping[str, Any]], max_stationary_planar_drift: float) -> dict[str, Any]:
    samples_by_index: dict[int, list[dict[str, Any]]] = {}
    for item in readbacks:
        row = safe_mapping(item)
        sample_index = parse_int(row.get("sampleIndex"))
        if sample_index is None:
            sample_index = 0
        samples_by_index.setdefault(sample_index, []).append(row)

    best_by_sample = [best_read(samples_by_index[index]) for index in sorted(samples_by_index)]
    best_by_sample = [item for item in best_by_sample if item is not None]
    matching = [item for item in best_by_sample if item.get("classification") == "candidate-coordinate-chain-current-readback"]
    first_coordinate = safe_mapping(matching[0].get("coordinate")) if matching else {}
    last_coordinate = safe_mapping(matching[-1].get("coordinate")) if matching else {}
    drift = coordinate_delta(last_coordinate, first_coordinate) if first_coordinate and last_coordinate else {"available": False}
    return {
        "sampleCount": len(samples_by_index),
        "bestMatchingSampleCount": len(matching),
        "allSamplesMatchedReference": len(best_by_sample) > 0 and len(matching) == len(best_by_sample),
        "firstBestCoordinate": first_coordinate or None,
        "lastBestCoordinate": last_coordinate or None,
        "bestCoordinateDrift": drift,
        "stationaryDriftWithinLimit": bool(drift.get("available")) and float(drift.get("planarDelta") or 0.0) <= max_stationary_planar_drift,
        "maxStationaryPlanarDrift": max_stationary_planar_drift,
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    best = safe_mapping(summary.get("bestReadback"))
    polling = safe_mapping(summary.get("polling"))
    lines = [
        "# Post-update global-container coordinate readback",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Static access-chain packet: `{safe_mapping(summary.get('inputs')).get('staticAccessChain')}`",
        f"- Best chain: `{best.get('chain')}`",
        f"- Best classification: `{best.get('classification')}`",
        f"- Best coordinate: `{best.get('coordinate')}`",
        f"- Best max abs delta: `{safe_mapping(best.get('deltaVsReference')).get('maxAbsDelta')}`",
        f"- Polling samples: `{polling.get('sampleCount')}`",
        f"- Stationary drift within limit: `{polling.get('stationaryDriftWithinLimit')}`",
        "",
        "| Chain | Coordinate | Max abs delta | Classification |",
        "|---|---|---:|---|",
    ]
    for row in safe_list(summary.get("readbacks"))[:12]:
        item = safe_mapping(row)
        lines.append(
            f"| `{item.get('chain')}` | `{item.get('coordinate')}` | "
            f"`{safe_mapping(item.get('deltaVsReference')).get('maxAbsDelta')}` | `{item.get('classification')}` |"
        )
    lines.extend(["", "## Blockers"])
    for blocker in safe_list(summary.get("blockers")):
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Recommended next action"])
    lines.append(str(safe_mapping(summary.get("next")).get("recommendedAction") or ""))
    lines.extend(["", "No input, movement, debugger/CE, truth update, provider write, or promotion was performed."])
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else repo_root / "scripts" / "captures"
    output_dir = output_root / f"postupdate-global-container-coordinate-readback-{utc_stamp()}"
    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary.md"
    blockers: list[str] = []
    warnings: list[str] = []

    latest = rediscovery.latest_artifact_paths(repo_root)
    static_access_chain_path = (
        Path(args.static_access_chain_json).resolve()
        if args.static_access_chain_json
        else (Path(latest["staticAccessChain"]) if latest["staticAccessChain"] else None)
    )
    packet = load_json_object(static_access_chain_path)
    if not packet:
        blockers.append("static-access-chain-packet-missing")

    candidate_paths = extract_candidate_paths(packet)
    if not candidate_paths and not blockers:
        blockers.append("global-container-coordinate-leads-missing")

    target = packet_target(packet)
    reference = safe_mapping(packet.get("referenceCoordinate")) or None
    live_target: dict[str, Any] = {"liveGlobalContainerCoordinateRead": False}
    readbacks: list[dict[str, Any]] = []
    polling: dict[str, Any] = {
        "requestedSampleCount": max(1, int(args.samples)),
        "intervalSeconds": float(args.interval_seconds),
        "sampleCount": 0,
        "bestMatchingSampleCount": 0,
        "allSamplesMatchedReference": False,
        "stationaryDriftWithinLimit": False,
    }
    if not blockers:
        requested_samples = max(1, int(args.samples))
        for sample_index in range(requested_samples):
            live_target, sample_reads, live_blockers, live_warnings = read_candidate_paths(
                target=target,
                candidate_paths=candidate_paths,
                reference=reference,
                tolerance=float(args.tolerance),
                child_window_bytes=int(args.child_window_bytes, 0),
            )
            sample_time = utc_iso()
            for row in sample_reads:
                row["sampleIndex"] = sample_index
                row["sampledAtUtc"] = sample_time
            readbacks.extend(sample_reads)
            blockers.extend(live_blockers)
            warnings.extend(live_warnings)
            if live_blockers:
                break
            if sample_index + 1 < requested_samples:
                time.sleep(max(0.0, float(args.interval_seconds)))
        polling.update(polling_analysis(readbacks, float(args.max_stationary_planar_drift)))

    best = best_read(readbacks)
    if blockers:
        status = "blocked"
        verdict = "global-container-coordinate-readback-blocked"
        recommended = "Fix the blocked-safe readback prerequisites, then rerun this helper."
    elif best and best.get("classification") == "candidate-coordinate-chain-current-readback":
        status = "candidate"
        verdict = "global-container-coordinate-chain-current-readback-passed"
        if int(args.samples) > 1 and not polling.get("stationaryDriftWithinLimit"):
            status = "blocked"
            verdict = "global-container-coordinate-chain-polling-drift-blocked"
            blockers.append("no-input-polling-drift-exceeded")
        recommended = (
            "Keep this as candidate-only static global/container coordinate evidence. "
            "Next safe step is a no-input short polling baseline; movement/restart proof still requires explicit approval before promotion."
        )
    else:
        status = "blocked"
        verdict = "global-container-coordinate-readback-no-current-match"
        blockers.append("global-container-coordinate-chain-current-readback-missing")
        recommended = "Review the candidate readbacks and rerun static access-chain sampling before any proof gate."

    safety = base_safety()
    safety.update(
        {
            "offlineOnly": False,
            "targetMemoryBytesRead": bool(live_target.get("liveGlobalContainerCoordinateRead")),
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "currentTruthUpdate": False,
            "candidateOnly": True,
        }
    )
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-postupdate-global-container-coordinate-readback",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(repo_root),
        "inputs": {
            "staticAccessChain": str(static_access_chain_path.resolve()) if static_access_chain_path else None,
        },
        "referenceCoordinate": reference,
        "target": live_target if live_target.get("liveGlobalContainerCoordinateRead") else target,
        "candidatePaths": candidate_paths,
        "readbacks": readbacks,
        "bestReadback": best,
        "polling": polling,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "safety": safety,
        "next": {
            "recommendedAction": recommended,
            "requiresApprovalBefore": [
                "movement/displacement stimulus",
                "x64dbg or Cheat Engine",
                "current-truth update",
                "ProofOnly or proof promotion",
                "actor-chain promotion",
            ],
        },
        "artifacts": {
            "outputDir": str(output_dir.resolve()),
            "summaryJson": str(summary_json.resolve()),
            "summaryMarkdown": str(summary_md.resolve()),
        },
    }
    write_json(summary_json, summary)
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text(build_markdown(summary), encoding="utf-8")
    return summary, 2 if status == "blocked" else 0


def self_test() -> dict[str, Any]:
    packet = {
        "breadcrumbGlobalSamples": [
            {
                "globalRva": "0x32DD7E8",
                "classification": COORDINATE_LEAD_CLASSIFICATION,
                "sourceFunctionRva": "0xC38390",
                "sourceInstructionRva": "0xC3843B",
                "sourceInstruction": "mov rbx, qword ptr [rip + 0x26a53a6]",
                "childPointerSamples": [
                    {
                        "parentOffset": "0x80",
                        "nearWorldTriples": [
                            {"offset": "0x1C", "maxAbsDelta": 0.3},
                            {"offset": "0x28", "maxAbsDelta": 0.004},
                        ],
                    }
                ],
            }
        ]
    }
    paths = extract_candidate_paths(packet)
    classification = classify_coordinate_read(
        {"x": 10.0, "y": 20.0, "z": 30.0},
        {"x": 10.1, "y": 20.0, "z": 30.0},
        0.25,
    )
    checks = [
        {"name": "extracts-two-coordinate-offsets", "pass": len(paths) == 2},
        {"name": "chain-expression-shape", "pass": paths[1]["chain"] == "[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30"},
        {"name": "coordinate-read-classification", "pass": classification == "candidate-coordinate-chain-current-readback"},
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-postupdate-global-container-coordinate-readback-self-test",
        "toolVersion": TOOL_VERSION,
        "status": "passed" if all(item["pass"] for item in checks) else "failed",
        "checks": checks,
        "safety": {**base_safety(), "offlineOnly": True, "targetMemoryBytesRead": False},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read post-update global-container coordinate chain candidates.")
    parser.add_argument("--repo-root")
    parser.add_argument("--static-access-chain-json")
    parser.add_argument("--child-window-bytes", default=hex(DEFAULT_CHILD_WINDOW_BYTES))
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--max-stationary-planar-drift", type=float, default=DEFAULT_MAX_STATIONARY_PLANAR_DRIFT)
    parser.add_argument("--output-root")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        payload = self_test()
        if args.json:
            print(json.dumps(payload, separators=(",", ":")))
        else:
            print(payload["status"])
        return 0 if payload["status"] == "passed" else 1

    summary, exit_code = build_summary(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary.get("status"),
                    "verdict": summary.get("verdict"),
                    "summaryJson": safe_mapping(summary.get("artifacts")).get("summaryJson"),
                    "bestReadback": summary.get("bestReadback"),
                    "polling": summary.get("polling"),
                    "blockers": summary.get("blockers"),
                    "warnings": summary.get("warnings"),
                    "next": summary.get("next"),
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"{summary.get('status')}: {safe_mapping(summary.get('artifacts')).get('summaryJson')}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
