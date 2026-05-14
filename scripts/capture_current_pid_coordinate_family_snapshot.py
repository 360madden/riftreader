#!/usr/bin/env python3
# Version: riftreader-current-pid-coordinate-family-snapshot-v0.1.0
# Purpose: Read-only broad snapshot of plausible XYZ triplets inside a targeted
#          current-PID memory family range. This complements the exact
#          reference-near scanner by preserving the wider ring/copy family.

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.platform != "win32":
    raise SystemExit("This helper requires Windows because it uses ReadProcessMemory.")

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scan_current_pid_coordinate_family import (  # noqa: E402
    capture_reference,
    close_handle,
    enumerate_regions,
    find_repo_root,
    format_hex,
    open_process,
    query_process_image,
    read_memory,
    verify_hwnd_owner,
    write_json,
)


SCHEMA_VERSION = 1
DEFAULT_WINDOW_X = 2048.0
DEFAULT_WINDOW_Y = 512.0
DEFAULT_WINDOW_Z = 2048.0
DEFAULT_NEAR_TOLERANCE = 0.25
DEFAULT_REFERENCE_DRIFT_TOLERANCE = DEFAULT_NEAR_TOLERANCE
DEFAULT_MAX_ABS_COORDINATE = 100000.0
DEFAULT_MAX_TRIPLETS = 50000
DEFAULT_CLUSTER_GAP = 0x80


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def parse_int(value: str) -> int:
    return int(str(value), 0)


def coord_from_mapping(mapping: dict[str, Any]) -> tuple[float, float, float] | None:
    def get(name: str) -> Any:
        for key, value in mapping.items():
            if str(key).lower() == name.lower():
                return value
        return None

    x = get("x")
    y = get("y")
    z = get("z")
    if x is None or y is None or z is None:
        return None
    try:
        return float(x), float(y), float(z)
    except (TypeError, ValueError):
        return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_reference(label: str, source_file: Path, document: dict[str, Any]) -> dict[str, Any] | None:
    coord_doc = (
        document.get("reference")
        or document.get("Reference")
        or document.get("coordinate")
        or document.get("Coordinate")
        or document
    )
    if not isinstance(coord_doc, dict):
        return None
    coord = coord_from_mapping(coord_doc)
    if coord is None:
        return None
    return {
        "label": label,
        "sourceFile": str(source_file),
        "x": coord[0],
        "y": coord[1],
        "z": coord[2],
        "generatedAtUtc": (
            document.get("generatedAtUtc")
            or document.get("GeneratedAtUtc")
            or document.get("captured_at_utc")
            or coord_doc.get("CapturedAtUtc")
            or coord_doc.get("captured_at_utc")
        ),
    }


def normalize_captured_reference(label: str, source_file: Path, parsed_reference: dict[str, Any]) -> dict[str, Any]:
    coord = parsed_reference.get("Coordinate") or parsed_reference.get("coordinate") or {}
    if not isinstance(coord, dict):
        raise RuntimeError("captured_reference_missing_coordinate_object")
    xyz = coord_from_mapping(coord)
    if xyz is None:
        raise RuntimeError("captured_reference_missing_xyz")
    return {
        "label": label,
        "sourceFile": str(source_file),
        "x": xyz[0],
        "y": xyz[1],
        "z": xyz[2],
        "generatedAtUtc": coord.get("CapturedAtUtc") or coord.get("captured_at_utc") or parsed_reference.get("GeneratedAtUtc"),
    }


def compact_reference(reference: dict[str, Any] | None) -> dict[str, Any] | None:
    if reference is None:
        return None
    return {
        "label": reference.get("label"),
        "sourceFile": reference.get("sourceFile"),
        "x": float(reference["x"]),
        "y": float(reference["y"]),
        "z": float(reference["z"]),
        "generatedAtUtc": reference.get("generatedAtUtc"),
    }


def summarize_reference_drift(
    start_reference: dict[str, Any],
    end_reference: dict[str, Any],
    *,
    tolerance: float,
) -> dict[str, Any]:
    dx = float(end_reference["x"]) - float(start_reference["x"])
    dy = float(end_reference["y"]) - float(start_reference["y"])
    dz = float(end_reference["z"]) - float(start_reference["z"])
    max_delta = max(abs(dx), abs(dy), abs(dz))
    distance = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
    within_tolerance = max_delta <= tolerance
    return {
        "enabled": True,
        "status": "stable" if within_tolerance else "drifted",
        "withinTolerance": within_tolerance,
        "tolerance": tolerance,
        "maxAbsDelta": max_delta,
        "spatialDistance": distance,
        "delta": {"x": dx, "y": dy, "z": dz},
        "startReference": compact_reference(start_reference),
        "endReference": compact_reference(end_reference),
    }


def compact_command_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    compact = {key: value for key, value in envelope.items() if key not in {"stdout", "stderr"}}
    compact["stdoutPreview"] = str(envelope.get("stdout", ""))[:2000]
    compact["stderrPreview"] = str(envelope.get("stderr", ""))[:2000]
    return compact


def load_observation_files(paths: list[str]) -> dict[str, Any]:
    references: list[dict[str, Any]] = []
    address_observations: dict[int, list[dict[str, Any]]] = defaultdict(list)
    errors: list[dict[str, str]] = []

    for raw_path in paths:
        path = Path(raw_path).resolve()
        label = path.parent.name or path.stem
        try:
            document = load_json(path)
        except Exception as exc:  # noqa: BLE001 - keep artifact evidence, continue other files.
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        if not isinstance(document, dict):
            errors.append({"path": str(path), "error": "top-level JSON is not an object"})
            continue

        reference = normalize_reference(label, path, document)
        if reference:
            references.append(reference)

        candidates = document.get("candidates") or document.get("Candidates") or []
        if not isinstance(candidates, list):
            candidates = []
        for index, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                continue
            raw_address = (
                candidate.get("absolute_address_hex")
                or candidate.get("AbsoluteAddressHex")
                or candidate.get("addressHex")
                or candidate.get("AddressHex")
            )
            if raw_address is None:
                continue
            try:
                address = parse_int(str(raw_address))
            except ValueError:
                continue
            address_observations[address].append(
                {
                    "sourceFile": str(path),
                    "label": label,
                    "candidateId": candidate.get("candidate_id") or candidate.get("CandidateId") or f"candidate-{index}",
                    "valuePreview": candidate.get("value_preview") or candidate.get("ValuePreview"),
                    "bestMaxAbsDistance": candidate.get("best_max_abs_distance") or candidate.get("BestMaxAbsDistance"),
                }
            )

    return {
        "references": references,
        "addressObservations": address_observations,
        "errors": errors,
        "observationFileCount": len(paths),
        "referenceCount": len(references),
        "observedAddressCount": len(address_observations),
    }


def max_abs_delta(x: float, y: float, z: float, ref: dict[str, Any]) -> float:
    return max(abs(x - float(ref["x"])), abs(y - float(ref["y"])), abs(z - float(ref["z"])))


def spatial_distance(x: float, y: float, z: float, ref: dict[str, Any]) -> float:
    return math.sqrt((x - float(ref["x"])) ** 2 + (y - float(ref["y"])) ** 2 + (z - float(ref["z"])) ** 2)


def in_reference_window(
    x: float,
    y: float,
    z: float,
    refs: list[dict[str, Any]],
    *,
    window_x: float,
    window_y: float,
    window_z: float,
) -> bool:
    for ref in refs:
        if (
            abs(x - float(ref["x"])) <= window_x
            and abs(y - float(ref["y"])) <= window_y
            and abs(z - float(ref["z"])) <= window_z
        ):
            return True
    return False


def neighbor_float_preview(data: bytes, offset: int, radius: int = 16) -> list[dict[str, Any]]:
    start = max(0, offset - radius)
    end = min(len(data), offset + 12 + radius)
    start -= start % 4
    result: list[dict[str, Any]] = []
    for pos in range(start, end - 3, 4):
        try:
            value = struct.unpack_from("<f", data, pos)[0]
        except struct.error:
            continue
        if math.isfinite(value):
            result.append({"relativeOffset": pos - offset, "value": float(value)})
    return result


def make_triplet_record(
    *,
    address: int,
    region_base: int,
    offset: int,
    data: bytes,
    x: float,
    y: float,
    z: float,
    references: list[dict[str, Any]],
    current_reference: dict[str, Any],
    near_tolerance: float,
    address_observations: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    nearest_ref = min(references, key=lambda ref: max_abs_delta(x, y, z, ref))
    current_delta = max_abs_delta(x, y, z, current_reference)
    nearest_delta = max_abs_delta(x, y, z, nearest_ref)
    near_refs = [
        {
            "label": ref["label"],
            "maxAbsDelta": max_abs_delta(x, y, z, ref),
            "spatialDistance": spatial_distance(x, y, z, ref),
        }
        for ref in references
        if max_abs_delta(x, y, z, ref) <= near_tolerance
    ]
    return {
        "address": address,
        "addressHex": format_hex(address),
        "regionBase": region_base,
        "regionBaseHex": format_hex(region_base),
        "regionOffset": address - region_base,
        "regionOffsetHex": format_hex(address - region_base),
        "familyBaseHex": format_hex(address & ~0xFFFF),
        "offsetWithin64kHex": format_hex(address & 0xFFFF),
        "axisOrder": "xyz",
        "x": float(x),
        "y": float(y),
        "z": float(z),
        "currentMaxAbsDelta": current_delta,
        "currentSpatialDistance": spatial_distance(x, y, z, current_reference),
        "nearestReferenceLabel": nearest_ref["label"],
        "nearestReferenceMaxAbsDelta": nearest_delta,
        "nearestReferenceSpatialDistance": spatial_distance(x, y, z, nearest_ref),
        "nearReferenceCount": len(near_refs),
        "nearReferences": sorted(near_refs, key=lambda item: item["maxAbsDelta"])[:8],
        "addressObservationCount": len(address_observations.get(address, [])),
        "addressObservations": address_observations.get(address, [])[:8],
        "residueMod16Hex": format_hex(address % 0x10),
        "residueMod48Hex": format_hex(address % 0x30),
        "residueMod256Hex": format_hex(address % 0x100),
        "neighborFloats": neighbor_float_preview(data, offset),
    }


def scan_data_for_triplets(
    *,
    data: bytes,
    base_addr: int,
    region_base: int,
    references: list[dict[str, Any]],
    current_reference: dict[str, Any],
    window_x: float,
    window_y: float,
    window_z: float,
    near_tolerance: float,
    max_abs_coordinate: float,
    address_observations: dict[int, list[dict[str, Any]]],
    remaining_budget: int,
    scan_stride: int,
) -> list[dict[str, Any]]:
    triplets: list[dict[str, Any]] = []
    limit = len(data) - 12
    if limit < 0:
        return triplets
    for offset in range(0, limit + 1, scan_stride):
        try:
            x, y, z = struct.unpack_from("<fff", data, offset)
        except struct.error:
            continue
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            continue
        if max(abs(x), abs(y), abs(z)) > max_abs_coordinate:
            continue
        if not in_reference_window(x, y, z, references, window_x=window_x, window_y=window_y, window_z=window_z):
            continue
        triplets.append(
            make_triplet_record(
                address=base_addr + offset,
                region_base=region_base,
                offset=offset,
                data=data,
                x=float(x),
                y=float(y),
                z=float(z),
                references=references,
                current_reference=current_reference,
                near_tolerance=near_tolerance,
                address_observations=address_observations,
            )
        )
        if len(triplets) >= remaining_budget:
            break
    return triplets


def summarize_clusters(triplets: list[dict[str, Any]], cluster_gap: int) -> list[dict[str, Any]]:
    if not triplets:
        return []
    ordered = sorted(triplets, key=lambda item: item["address"])
    clusters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = [ordered[0]]
    for item in ordered[1:]:
        if item["address"] - current[-1]["address"] <= cluster_gap:
            current.append(item)
        else:
            clusters.append(current)
            current = [item]
    clusters.append(current)

    summaries: list[dict[str, Any]] = []
    for index, cluster in enumerate(clusters, start=1):
        near_count = sum(1 for item in cluster if item["nearReferenceCount"] > 0)
        observed_count = sum(1 for item in cluster if item["addressObservationCount"] > 0)
        best_current = min(cluster, key=lambda item: item["currentMaxAbsDelta"])
        best_nearest = min(cluster, key=lambda item: item["nearestReferenceMaxAbsDelta"])
        summaries.append(
            {
                "clusterId": f"cluster-{index:04d}",
                "startAddressHex": format_hex(cluster[0]["address"]),
                "endAddressHex": format_hex(cluster[-1]["address"] + 12),
                "byteSpan": (cluster[-1]["address"] + 12) - cluster[0]["address"],
                "tripletCount": len(cluster),
                "nearReferenceTripletCount": near_count,
                "addressObservationTripletCount": observed_count,
                "bestCurrentAddressHex": best_current["addressHex"],
                "bestCurrentMaxAbsDelta": best_current["currentMaxAbsDelta"],
                "bestNearestAddressHex": best_nearest["addressHex"],
                "bestNearestReferenceLabel": best_nearest["nearestReferenceLabel"],
                "bestNearestReferenceMaxAbsDelta": best_nearest["nearestReferenceMaxAbsDelta"],
            }
        )
    return sorted(
        summaries,
        key=lambda item: (
            -int(item["nearReferenceTripletCount"]),
            -int(item["addressObservationTripletCount"]),
            float(item["bestNearestReferenceMaxAbsDelta"]),
            float(item["bestCurrentMaxAbsDelta"]),
        ),
    )


def compact_triplet(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "addressHex": item["addressHex"],
        "familyBaseHex": item["familyBaseHex"],
        "regionOffsetHex": item["regionOffsetHex"],
        "value": [item["x"], item["y"], item["z"]],
        "currentMaxAbsDelta": item["currentMaxAbsDelta"],
        "nearestReferenceLabel": item["nearestReferenceLabel"],
        "nearestReferenceMaxAbsDelta": item["nearestReferenceMaxAbsDelta"],
        "nearReferenceCount": item["nearReferenceCount"],
        "addressObservationCount": item["addressObservationCount"],
        "residueMod48Hex": item["residueMod48Hex"],
        "residueMod256Hex": item["residueMod256Hex"],
    }


def make_import_candidate(item: dict[str, Any], index: int) -> dict[str, Any]:
    region_offset = int(str(item["regionOffsetHex"]), 0)
    current_delta = float(item["currentMaxAbsDelta"])
    near_count = int(item.get("nearReferenceCount") or 0)
    observed_count = int(item.get("addressObservationCount") or 0)
    support_count = max(1, near_count + observed_count)
    score = max(0.0, 100000.0 - (current_delta * 10000.0)) + (near_count * 100.0) + (observed_count * 250.0)

    return {
        "schema_version": "riftreader.current_pid_family_snapshot_candidate.v1",
        "candidate_id": f"family-snapshot-hit-{index:06d}",
        "base_address_hex": item["regionBaseHex"],
        "offset_hex": item["regionOffsetHex"],
        "x_offset_hex": item["regionOffsetHex"],
        "y_offset_hex": format_hex(region_offset + 4),
        "z_offset_hex": format_hex(region_offset + 8),
        "absolute_address_hex": item["addressHex"],
        "axis_order": item.get("axisOrder") or "xyz",
        "value_preview": [item["x"], item["y"], item["z"]],
        "best_memory_x": item["x"],
        "best_memory_y": item["y"],
        "best_memory_z": item["z"],
        "best_max_abs_distance": current_delta,
        "score_total": score,
        "rank_score": score,
        "support_count": support_count,
        "observation_support_count": observed_count,
        "classification": "current-pid-family-snapshot-triplet",
        "validation_status": "near_reference_candidate" if near_count > 0 else "broad_family_window_candidate",
        "truth_readiness": "candidate_only_not_movement_proof",
        "confidence_level": "candidate",
        "evidence_summary": (
            f"currentMaxAbsDelta={current_delta:.6g}; nearReferenceCount={near_count}; "
            f"addressObservationCount={observed_count}; familyBase={item['familyBaseHex']}"
        ),
        "next_validation_step": "Run read-only proof-pose readback; require current-process proof anchor before movement.",
        "family_base_hex": item["familyBaseHex"],
        "nearest_reference_label": item["nearestReferenceLabel"],
        "nearest_reference_max_abs_delta": item["nearestReferenceMaxAbsDelta"],
        "near_reference_count": near_count,
        "address_observation_count": observed_count,
        "residue_mod48_hex": item["residueMod48Hex"],
        "residue_mod256_hex": item["residueMod256Hex"],
    }


def select_import_candidates(triplets: list[dict[str, Any]], top_count: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add_ordered(items: list[dict[str, Any]]) -> None:
        for item in items:
            address = int(item["address"])
            if address in seen:
                continue
            selected.append(item)
            seen.add(address)
            if len(selected) >= top_count:
                return

    near_or_observed = sorted(
        [item for item in triplets if int(item.get("nearReferenceCount") or 0) > 0 or int(item.get("addressObservationCount") or 0) > 0],
        key=lambda item: (
            float(item["currentMaxAbsDelta"]),
            -int(item.get("addressObservationCount") or 0),
            int(item["address"]),
        ),
    )
    add_ordered(near_or_observed)
    if len(selected) < top_count:
        add_ordered(sorted(triplets, key=lambda item: (float(item["currentMaxAbsDelta"]), int(item["address"]))))

    return [make_import_candidate(item, index) for index, item in enumerate(selected[:top_count], start=1)]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + ("\n" if records else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only broad coordinate family snapshot for a current RIFT PID.")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--hwnd", required=True)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--reference-file", default=None)
    parser.add_argument("--reference-x", type=float, default=None)
    parser.add_argument("--reference-y", type=float, default=None)
    parser.add_argument("--reference-z", type=float, default=None)
    parser.add_argument("--observation-file", action="append", default=[])
    parser.add_argument("--min-address", required=True)
    parser.add_argument("--max-address", required=True)
    parser.add_argument("--chunk-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--scan-stride", type=int, choices=(1, 4), default=4)
    parser.add_argument("--max-seconds", type=int, default=60)
    parser.add_argument("--reference-timeout-seconds", type=int, default=90)
    parser.add_argument("--window-x", type=float, default=DEFAULT_WINDOW_X)
    parser.add_argument("--window-y", type=float, default=DEFAULT_WINDOW_Y)
    parser.add_argument("--window-z", type=float, default=DEFAULT_WINDOW_Z)
    parser.add_argument("--near-tolerance", type=float, default=DEFAULT_NEAR_TOLERANCE)
    parser.add_argument(
        "--reference-drift-tolerance",
        type=float,
        default=DEFAULT_REFERENCE_DRIFT_TOLERANCE,
        help="Maximum allowed pre/post RRAPICOORD max-axis drift before the snapshot is blocked as stale.",
    )
    parser.add_argument(
        "--skip-post-reference-check",
        action="store_true",
        help="Skip the default post-scan RRAPICOORD freshness check. Use only for explicitly offline/diagnostic captures.",
    )
    parser.add_argument("--max-abs-coordinate", type=float, default=DEFAULT_MAX_ABS_COORDINATE)
    parser.add_argument("--max-triplets", type=int, default=DEFAULT_MAX_TRIPLETS)
    parser.add_argument("--top-count", type=int, default=25)
    parser.add_argument("--cluster-gap", type=lambda value: int(value, 0), default=DEFAULT_CLUSTER_GAP)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    run_dir = Path(args.output_root).resolve() if args.output_root else repo_root / "scripts" / "captures" / f"coordinate-family-snapshot-currentpid-{args.pid}-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "family-snapshot-summary.json"
    markdown_path = run_dir / "family-snapshot-summary.md"
    triplets_jsonl = run_dir / "family-triplets.jsonl"
    top_triplets_json = run_dir / "family-top-triplets.json"
    candidate_json = run_dir / "family-import-candidates.json"
    candidate_jsonl = run_dir / "family-import-candidates.jsonl"

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-current-pid-coordinate-family-snapshot",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "processName": args.process_name,
        "processId": args.pid,
        "targetWindowHandle": args.hwnd,
        "repoRoot": str(repo_root),
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "memoryWritten": False,
            "breakpointsSet": False,
            "debuggerAttached": False,
            "noCheatEngine": True,
            "githubConnectorWrites": False,
            "providerWrites": False,
        },
        "scan": {},
        "referenceStability": {
            "enabled": not args.skip_post_reference_check,
            "status": "not-run",
            "tolerance": args.reference_drift_tolerance,
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_path),
            "summaryMarkdown": str(markdown_path),
            "tripletsJsonl": str(triplets_jsonl),
            "topTripletsJson": str(top_triplets_json),
            "candidateJson": str(candidate_json),
            "candidateJsonl": str(candidate_jsonl),
        },
        "blockers": [],
        "warnings": [],
        "errors": [],
    }
    return_code = 1

    try:
        observation_bundle = load_observation_files(args.observation_file)
        summary["observations"] = {
            "observationFileCount": observation_bundle["observationFileCount"],
            "referenceCount": observation_bundle["referenceCount"],
            "observedAddressCount": observation_bundle["observedAddressCount"],
            "loadErrors": observation_bundle["errors"],
        }
        if observation_bundle["errors"]:
            summary["warnings"].append("one-or-more-observation-files-could-not-be-loaded")

        hwnd_info = verify_hwnd_owner(args.hwnd, args.pid)
        summary["target"] = hwnd_info
        if hwnd_info.get("blocker"):
            summary["status"] = "blocked"
            summary["blockers"].append(str(hwnd_info["blocker"]))
            return_code = 2
            return return_code

        handle = open_process(args.pid)
        try:
            image = query_process_image(handle)
            summary["target"]["processImage"] = image

            if args.reference_file:
                ref_doc = load_json(Path(args.reference_file))
                if not isinstance(ref_doc, dict):
                    raise RuntimeError("reference_file_json_not_object")
                current = normalize_reference("current-reference-file", Path(args.reference_file), ref_doc)
                if current is None:
                    raise RuntimeError("reference_file_missing_xyz")
                current_reference = current
            elif args.reference_x is not None and args.reference_y is not None and args.reference_z is not None:
                current_reference = {
                    "label": "manual-current-reference",
                    "sourceFile": None,
                    "x": float(args.reference_x),
                    "y": float(args.reference_y),
                    "z": float(args.reference_z),
                    "generatedAtUtc": None,
                }
            else:
                parsed_ref, command_envelope, ref_file = capture_reference(
                    repo_root,
                    run_dir,
                    args.pid,
                    args.hwnd,
                    args.process_name,
                    args.reference_timeout_seconds,
                )
                summary["commandEnvelopes"] = {"referenceCapture": compact_command_envelope(command_envelope)}
                current_reference = normalize_captured_reference("fresh-rrapicoord-current", ref_file, parsed_ref)

            references = [current_reference, *observation_bundle["references"]]
            # De-duplicate near-identical references by rounded XYZ and label to keep reports compact.
            seen_refs: set[tuple[float, float, float, str]] = set()
            unique_refs: list[dict[str, Any]] = []
            for ref in references:
                key = (round(float(ref["x"]), 3), round(float(ref["y"]), 3), round(float(ref["z"]), 3), str(ref["label"]))
                if key in seen_refs:
                    continue
                seen_refs.add(key)
                unique_refs.append(ref)
            references = unique_refs
            summary["currentReference"] = current_reference
            summary["referenceSet"] = references

            min_address = parse_int(args.min_address)
            max_address = parse_int(args.max_address)
            regions = enumerate_regions(handle, min_address=min_address, max_address=max_address)
            summary["scan"].update(
                {
                    "minAddress": format_hex(min_address),
                    "maxAddress": format_hex(max_address),
                    "readableRegionCount": len(regions),
                    "windowX": args.window_x,
                    "windowY": args.window_y,
                    "windowZ": args.window_z,
                    "nearTolerance": args.near_tolerance,
                    "maxTriplets": args.max_triplets,
                    "clusterGap": format_hex(args.cluster_gap),
                    "scanStride": args.scan_stride,
                }
            )

            started = time.monotonic()
            triplets: list[dict[str, Any]] = []
            chunks_read = 0
            bytes_scanned = 0
            read_failures = 0

            for region in regions:
                if time.monotonic() - started > args.max_seconds:
                    summary["warnings"].append(f"scan-time-budget-reached:{args.max_seconds}s")
                    break
                base = region["base"]
                size = min(region["size"], max_address - base)
                offset = 0
                overlap = b""
                overlap_bytes = 11 if args.scan_stride == 1 else 8
                while offset < size and len(triplets) < args.max_triplets:
                    if time.monotonic() - started > args.max_seconds:
                        summary["warnings"].append(f"scan-time-budget-reached:{args.max_seconds}s")
                        break
                    read_size = min(args.chunk_bytes, size - offset)
                    address = base + offset
                    data = read_memory(handle, address, read_size)
                    if data is None:
                        read_failures += 1
                        overlap = b""
                        offset += read_size
                        continue
                    chunks_read += 1
                    bytes_scanned += len(data)
                    scan_data = overlap + data
                    scan_base = address - len(overlap)
                    found = scan_data_for_triplets(
                        data=scan_data,
                        base_addr=scan_base,
                        region_base=base,
                        references=references,
                        current_reference=current_reference,
                        window_x=args.window_x,
                        window_y=args.window_y,
                        window_z=args.window_z,
                        near_tolerance=args.near_tolerance,
                        max_abs_coordinate=args.max_abs_coordinate,
                        address_observations=observation_bundle["addressObservations"],
                        remaining_budget=args.max_triplets - len(triplets),
                        scan_stride=args.scan_stride,
                    )
                    triplets.extend(found)
                    overlap = data[-overlap_bytes:] if len(data) >= overlap_bytes else data
                    offset += read_size
                if len(triplets) >= args.max_triplets:
                    summary["warnings"].append(f"max-triplets-reached:{args.max_triplets}")
                    break

            triplets = sorted(triplets, key=lambda item: item["address"])
            write_jsonl(triplets_jsonl, triplets)

            family_counts = Counter(item["familyBaseHex"] for item in triplets)
            near_reference_triplets = [item for item in triplets if item["nearReferenceCount"] > 0]
            observed_address_triplets = [item for item in triplets if item["addressObservationCount"] > 0]
            top_current = sorted(triplets, key=lambda item: item["currentMaxAbsDelta"])[: args.top_count]
            top_nearest = sorted(triplets, key=lambda item: item["nearestReferenceMaxAbsDelta"])[: args.top_count]
            clusters = summarize_clusters(triplets, args.cluster_gap)

            residue_near_mod48 = Counter(item["residueMod48Hex"] for item in near_reference_triplets)
            residue_near_mod256 = Counter(item["residueMod256Hex"] for item in near_reference_triplets)

            reference_blockers: list[str] = []
            post_scan_reference: dict[str, Any] | None = None
            if args.skip_post_reference_check:
                summary["referenceStability"] = {
                    "enabled": False,
                    "status": "skipped",
                    "tolerance": args.reference_drift_tolerance,
                    "reason": "operator-disabled",
                }
                summary["warnings"].append("post-scan-reference-check-skipped")
                reference_blockers.append("post-scan-reference-check-skipped")
            else:
                try:
                    post_ref_dir = run_dir / "post-scan-reference"
                    post_ref_dir.mkdir(parents=True, exist_ok=True)
                    parsed_post_ref, post_command_envelope, post_ref_file = capture_reference(
                        repo_root,
                        post_ref_dir,
                        args.pid,
                        args.hwnd,
                        args.process_name,
                        args.reference_timeout_seconds,
                    )
                    command_envelopes = summary.setdefault("commandEnvelopes", {})
                    command_envelopes["postScanReferenceCapture"] = compact_command_envelope(post_command_envelope)
                    post_scan_reference = normalize_captured_reference(
                        "post-scan-rrapicoord-current",
                        post_ref_file,
                        parsed_post_ref,
                    )
                    summary["postScanReference"] = post_scan_reference
                    stability = summarize_reference_drift(
                        current_reference,
                        post_scan_reference,
                        tolerance=args.reference_drift_tolerance,
                    )
                    summary["referenceStability"] = stability
                    if not stability["withinTolerance"]:
                        blocker = (
                            "reference-drift-during-snapshot:"
                            f"{stability['maxAbsDelta']:.6g}>{args.reference_drift_tolerance:.6g}"
                        )
                        summary["blockers"].append(blocker)
                        reference_blockers.append(blocker)
                except Exception as exc:  # noqa: BLE001 - fail closed but preserve snapshot artifacts.
                    blocker = "post-scan-reference-capture-failed"
                    summary["referenceStability"] = {
                        "enabled": True,
                        "status": "blocked",
                        "tolerance": args.reference_drift_tolerance,
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                    }
                    summary["blockers"].append(blocker)
                    reference_blockers.append(blocker)

            top_payload = {
                "schemaVersion": SCHEMA_VERSION,
                "generatedAtUtc": utc_iso(),
                "referenceStability": summary["referenceStability"],
                "topCurrentMatches": [compact_triplet(item) for item in top_current],
                "topNearestReferenceMatches": [compact_triplet(item) for item in top_nearest],
                "observedAddressMatches": [compact_triplet(item) for item in observed_address_triplets[: args.top_count]],
                "topClusters": clusters[: args.top_count],
            }
            write_json(top_triplets_json, top_payload)

            import_candidates = select_import_candidates(triplets, args.top_count)
            write_json(
                candidate_json,
                {
                    "schemaVersion": SCHEMA_VERSION,
                    "mode": "riftreader-current-pid-coordinate-family-import-candidates",
                    "generatedAtUtc": utc_iso(),
                    "processId": args.pid,
                    "targetWindowHandle": args.hwnd,
                    "sourceFamilySnapshot": str(summary_path),
                    "currentReference": current_reference,
                    "postScanReference": post_scan_reference,
                    "referenceStability": summary["referenceStability"],
                    "candidateCount": len(import_candidates),
                    "candidates": import_candidates,
                    "truthStatus": {
                        "candidateOnly": True,
                        "promotionEligible": False,
                        "promotionBlockers": [
                            "family-snapshot-candidates-are-read-only-evidence",
                            "same-target-proof-readback-not-yet-run",
                            "no-current-process-proof-anchor",
                            *reference_blockers,
                        ],
                    },
                },
            )
            write_jsonl(candidate_jsonl, import_candidates)

            summary["scan"].update(
                {
                    "durationSeconds": round(time.monotonic() - started, 3),
                    "chunksRead": chunks_read,
                    "bytesScanned": bytes_scanned,
                    "readFailures": read_failures,
                    "tripletCount": len(triplets),
                    "nearReferenceTripletCount": len(near_reference_triplets),
                    "observedAddressTripletCount": len(observed_address_triplets),
                    "familyCounts": dict(family_counts.most_common(20)),
                    "nearReferenceResidueMod48Counts": dict(residue_near_mod48.most_common(20)),
                    "nearReferenceResidueMod256Counts": dict(residue_near_mod256.most_common(20)),
                    "bestCurrentTriplet": compact_triplet(top_current[0]) if top_current else None,
                    "bestNearestReferenceTriplet": compact_triplet(top_nearest[0]) if top_nearest else None,
                    "clusterCount": len(clusters),
                    "importCandidateCount": len(import_candidates),
                }
            )
            summary["topClusters"] = clusters[: args.top_count]
            summary["truthStatus"] = {
                "candidateOnly": True,
                "promotionEligible": False,
                "promotionBlockers": [
                    "broad-family-snapshot-is-read-only-candidate-evidence",
                    "exact-address-stability-not-proven",
                    "no-writer-or-static-pointer-chain-proof",
                    *reference_blockers,
                ],
            }
            if triplets:
                if reference_blockers:
                    summary["status"] = "blocked"
                    return_code = 2
                else:
                    summary["status"] = "captured"
                    return_code = 0
            else:
                summary["status"] = "blocked"
                summary["blockers"].append("no-plausible-coordinate-triplets-in-family-window")
                return_code = 2
            return return_code
        finally:
            close_handle(handle)
    except Exception as exc:  # noqa: BLE001 - preserve failure in artifact.
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        return_code = 1
        return return_code
    finally:
        write_json(summary_path, summary)
        markdown_path.write_text(
            "\n".join(
                [
                    "# Current-PID coordinate family snapshot",
                    "",
                    f"- Status: `{summary.get('status')}`",
                    f"- PID/HWND: `{args.pid}` / `{args.hwnd}`",
                    f"- Range: `{summary.get('scan', {}).get('minAddress')}`-`{summary.get('scan', {}).get('maxAddress')}`",
                    f"- Triplets: `{summary.get('scan', {}).get('tripletCount')}`",
                    f"- Near-reference triplets: `{summary.get('scan', {}).get('nearReferenceTripletCount')}`",
                    f"- Observed-address triplets: `{summary.get('scan', {}).get('observedAddressTripletCount')}`",
                    f"- Best current: `{(summary.get('scan', {}).get('bestCurrentTriplet') or {}).get('addressHex')}`",
                    f"- Reference stability: `{summary.get('referenceStability', {}).get('status')}`"
                    f" (maxAbsDelta=`{summary.get('referenceStability', {}).get('maxAbsDelta')}`)",
                    f"- Import candidates: `{summary.get('artifacts', {}).get('candidateJson')}`",
                    f"- Blockers: `{', '.join(summary.get('blockers') or [])}`",
                    "",
                    "This is read-only candidate evidence. It sends no input, writes no memory, and sets no breakpoints.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(
                json.dumps(
                    {
                        "status": summary.get("status"),
                        "tripletCount": summary.get("scan", {}).get("tripletCount"),
                        "nearReferenceTripletCount": summary.get("scan", {}).get("nearReferenceTripletCount"),
                        "bestCurrent": summary.get("scan", {}).get("bestCurrentTriplet"),
                        "summaryJson": str(summary_path),
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    raise SystemExit(main())
