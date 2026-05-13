#!/usr/bin/env python3
"""Offline delta analyzer for current-PID family memory snapshots.

This tool compares sequential, targeted family-group snapshots captured by
current_pid_family_snapshot_sequence.py.  It is intentionally offline-only: it
does not open the RIFT process, send input, launch a debugger, or write provider
state.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import struct
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_WINDOW_X = 2048.0
DEFAULT_WINDOW_Y = 512.0
DEFAULT_WINDOW_Z = 2048.0
DEFAULT_MAX_TRACKING_ERROR = 0.75
DEFAULT_MIN_API_PLANAR_DELTA = 0.05
DEFAULT_MAX_ABS_COORDINATE = 100000.0
DEFAULT_MAX_CANDIDATE_STARTS_PER_SEGMENT = 250000
DEFAULT_TOP = 100


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def format_hex(value: int | None) -> str | None:
    return None if value is None else f"0x{int(value):X}"


def parse_int(value: Any) -> int:
    return int(str(value), 0)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_manifest_path(manifest_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def read_segment_bytes(manifest_path: Path, segment: dict[str, Any]) -> bytes:
    raw_path = segment.get("path") or segment.get("snapshotPath")
    if not raw_path:
        raise RuntimeError(f"segment missing path: {segment}")
    path = resolve_manifest_path(manifest_path, str(raw_path))
    data = path.read_bytes()
    if path.suffix.lower() == ".gz" or segment.get("compression") == "gzip":
        return gzip.decompress(data)
    return data


def mapping_get(mapping: dict[str, Any], *names: str) -> Any:
    for expected in names:
        for key, value in mapping.items():
            if str(key).lower() == expected.lower():
                return value
    return None


def coordinate_from_any(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    doc = (
        mapping_get(value, "coordinate", "Coordinate")
        or mapping_get(value, "reference", "Reference")
        or value
    )
    if not isinstance(doc, dict):
        return None
    try:
        return {
            "x": float(mapping_get(doc, "x", "X")),
            "y": float(mapping_get(doc, "y", "Y")),
            "z": float(mapping_get(doc, "z", "Z")),
        }
    except (TypeError, ValueError):
        return None


def pose_reference(pose: dict[str, Any]) -> dict[str, float] | None:
    direct = coordinate_from_any(pose.get("reference") or pose.get("apiReference"))
    if direct is not None:
        return direct
    reference_file = pose.get("referenceFile")
    if not reference_file:
        return None
    try:
        return coordinate_from_any(load_json(Path(reference_file)))
    except Exception:
        return None


def ref_delta(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    dx = right["x"] - left["x"]
    dy = right["y"] - left["y"]
    dz = right["z"] - left["z"]
    return {
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "planar": math.sqrt(dx * dx + dz * dz),
        "spatial": math.sqrt(dx * dx + dy * dy + dz * dz),
        "maxAbs": max(abs(dx), abs(dy), abs(dz)),
    }


def value_delta(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    return ref_delta(left, right)


def tracking_error(reference_delta: dict[str, float], memory_delta: dict[str, float]) -> dict[str, float]:
    dx = memory_delta["dx"] - reference_delta["dx"]
    dy = memory_delta["dy"] - reference_delta["dy"]
    dz = memory_delta["dz"] - reference_delta["dz"]
    return {
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "planar": math.sqrt(dx * dx + dz * dz),
        "spatial": math.sqrt(dx * dx + dy * dy + dz * dz),
        "maxAbs": max(abs(dx), abs(dy), abs(dz)),
    }


def plausible_coordinate(value: dict[str, float], reference: dict[str, float], args: argparse.Namespace) -> bool:
    if not all(math.isfinite(value[axis]) for axis in ("x", "y", "z")):
        return False
    if any(abs(value[axis]) > args.max_abs_coordinate for axis in ("x", "y", "z")):
        return False
    return (
        abs(value["x"] - reference["x"]) <= args.window_x
        and abs(value["y"] - reference["y"]) <= args.window_y
        and abs(value["z"] - reference["z"]) <= args.window_z
    )


def decode_vec3(data: bytes, offset: int, axis_order: str) -> dict[str, float] | None:
    try:
        raw = struct.unpack_from("<fff", data, offset)
    except struct.error:
        return None
    if len(axis_order) != 3 or set(axis_order) != {"x", "y", "z"}:
        raise ValueError(f"Invalid axis order: {axis_order}")
    values = {axis_order[index]: float(raw[index]) for index in range(3)}
    if not all(math.isfinite(values[axis]) for axis in ("x", "y", "z")):
        return None
    return {"x": values["x"], "y": values["y"], "z": values["z"]}


def segment_key(segment: dict[str, Any]) -> str:
    base = segment.get("baseHex") or segment.get("baseAddressHex")
    end = segment.get("endHex") or segment.get("endAddressHex")
    if base and end:
        return f"{str(base).upper()}-{str(end).upper()}"
    return str(segment.get("id") or segment.get("path"))


def segment_base(segment: dict[str, Any]) -> int:
    return parse_int(segment.get("baseHex") or segment.get("baseAddressHex") or segment.get("base"))


def changed_offsets(left: bytes, right: bytes) -> set[int]:
    limit = min(len(left), len(right))
    return {index for index in range(limit) if left[index] != right[index]}


def candidate_starts_from_changes(changes: set[int], data_len: int, stride: int, max_starts: int) -> tuple[list[int], bool]:
    starts: set[int] = set()
    for changed in changes:
        lo = max(0, changed - 11)
        hi = min(changed, data_len - 12)
        for start in range(lo, hi + 1):
            if stride == 1 or start % stride == 0:
                starts.add(start)
                if len(starts) > max_starts:
                    return sorted(starts)[:max_starts], True
    return sorted(starts), False


def score_candidate(candidate: dict[str, Any]) -> float:
    return round(
        float(candidate["trackingError"]["maxAbs"])
        + (float(candidate["baselineMaxAbsDelta"]) * 0.01)
        + (float(candidate["displacedMaxAbsDelta"]) * 0.01)
        + (int(candidate["passiveNoiseByteOverlap"]) * 0.05),
        6,
    )


def build_candidate(
    *,
    base_address: int,
    offset: int,
    segment: dict[str, Any],
    axis_order: str,
    baseline_label: str,
    displaced_label: str,
    baseline_ref: dict[str, float],
    displaced_ref: dict[str, float],
    baseline_value: dict[str, float],
    displaced_value: dict[str, float],
    passive_noise: set[int],
) -> dict[str, Any]:
    absolute = base_address + offset
    api_delta = ref_delta(baseline_ref, displaced_ref)
    mem_delta = value_delta(baseline_value, displaced_value)
    error = tracking_error(api_delta, mem_delta)
    passive_overlap = sum(1 for pos in range(offset, offset + 12) if pos in passive_noise)
    baseline_max_abs = max(abs(baseline_value[axis] - baseline_ref[axis]) for axis in ("x", "y", "z"))
    displaced_max_abs = max(abs(displaced_value[axis] - displaced_ref[axis]) for axis in ("x", "y", "z"))
    candidate = {
        "candidateId": f"snapshot-delta-{absolute:X}-{axis_order}",
        "address": absolute,
        "addressHex": format_hex(absolute),
        "segmentBaseHex": format_hex(base_address),
        "segmentOffset": offset,
        "segmentOffsetHex": format_hex(offset),
        "rangeRank": segment.get("rangeRank"),
        "rangeSource": segment.get("rangeSource"),
        "rangeLabel": segment.get("rangeLabel"),
        "familyBaseHex": format_hex(absolute & ~0xFFFFF),
        "pageHex": format_hex(absolute & ~0xFFF),
        "residueMod4": absolute % 4,
        "residueMod16Hex": format_hex(absolute % 16),
        "residueMod48Hex": format_hex(absolute % 48),
        "residueMod256Hex": format_hex(absolute % 256),
        "axisOrder": axis_order,
        "baselinePose": baseline_label,
        "displacedPose": displaced_label,
        "baselineValue": baseline_value,
        "displacedValue": displaced_value,
        "baselineReference": baseline_ref,
        "displacedReference": displaced_ref,
        "apiDelta": api_delta,
        "memoryDelta": mem_delta,
        "trackingError": error,
        "baselineMaxAbsDelta": baseline_max_abs,
        "displacedMaxAbsDelta": displaced_max_abs,
        "passiveNoiseByteOverlap": passive_overlap,
        "cleanDisplacementWindow": passive_overlap == 0,
    }
    candidate["score"] = score_candidate(candidate)
    return candidate


def summarize_families(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        families[str(candidate["familyBaseHex"])].append(candidate)

    summaries: list[dict[str, Any]] = []
    for family, rows in families.items():
        addresses = sorted({int(row["address"]) for row in rows})
        gaps = [right - left for left, right in zip(addresses, addresses[1:]) if 0 < right - left <= 0x10000]
        gap_counts = Counter(gaps)
        residue_mod_16 = Counter(str(row["residueMod16Hex"]) for row in rows)
        residue_mod_48 = Counter(str(row["residueMod48Hex"]) for row in rows)
        residue_mod_256 = Counter(str(row["residueMod256Hex"]) for row in rows)
        best = min(rows, key=lambda item: (float(item["score"]), float(item["trackingError"]["maxAbs"]), int(item["passiveNoiseByteOverlap"])))
        summaries.append(
            {
                "familyBaseHex": family,
                "candidateCount": len(rows),
                "addressCount": len(addresses),
                "bestCandidate": {
                    "candidateId": best["candidateId"],
                    "addressHex": best["addressHex"],
                    "axisOrder": best["axisOrder"],
                    "score": best["score"],
                    "trackingErrorMaxAbs": best["trackingError"]["maxAbs"],
                    "passiveNoiseByteOverlap": best["passiveNoiseByteOverlap"],
                },
                "commonAddressDeltaHex": format_hex(gap_counts.most_common(1)[0][0]) if gap_counts else None,
                "commonAddressDeltaCount": gap_counts.most_common(1)[0][1] if gap_counts else 0,
                "residueMod16Counts": dict(residue_mod_16.most_common(12)),
                "residueMod48Counts": dict(residue_mod_48.most_common(12)),
                "residueMod256Counts": dict(residue_mod_256.most_common(12)),
            }
        )

    return sorted(summaries, key=lambda item: (float(item["bestCandidate"]["score"]), -int(item["candidateCount"])))


def analyze_manifest(manifest_path: Path, output_root: Path | None, args: argparse.Namespace) -> tuple[dict[str, Any], Path, Path, Path, Path, Path]:
    manifest = load_json(manifest_path)
    run_dir = output_root.resolve() if output_root else manifest_path.parent / "delta-analysis"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / "delta-summary.json"
    markdown_path = run_dir / "delta-summary.md"
    candidates_json_path = run_dir / "candidate-vec3.json"
    candidates_path = run_dir / "candidate-vec3.jsonl"
    families_path = run_dir / "candidate-families.json"

    poses = manifest.get("poses")
    if not isinstance(poses, list) or not poses:
        raise RuntimeError("manifest has no poses")

    baseline_pose = next((pose for pose in poses if pose.get("role") == "baseline"), poses[0])
    passive_poses = [pose for pose in poses if pose.get("role") == "passive"]
    displaced_poses = [pose for pose in poses if pose.get("role") == "displaced"]
    baseline_ref = pose_reference(baseline_pose)

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-family-snapshot-delta-analysis",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "manifestPath": str(manifest_path),
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "processAttachOrMemoryReadStarted": False,
            "providerWrites": False,
            "githubConnectorWrites": False,
        },
        "analysis": {
            "poseCount": len(poses),
            "passivePoseCount": len(passive_poses),
            "displacedPoseCount": len(displaced_poses),
            "axisOrders": args.axis_orders,
            "candidateScanStride": args.candidate_scan_stride,
            "maxTrackingError": args.max_tracking_error,
            "minApiPlanarDelta": args.min_api_planar_delta,
        },
        "artifacts": {
            "summaryJson": str(summary_path),
            "summaryMarkdown": str(markdown_path),
            "candidateVec3Json": str(candidates_json_path),
            "candidateVec3Jsonl": str(candidates_path),
            "candidateFamiliesJson": str(families_path),
        },
        "next": {},
    }

    candidates: list[dict[str, Any]] = []
    segment_summaries: list[dict[str, Any]] = []

    if baseline_ref is None:
        summary["blockers"].append("baseline-reference-missing")
    if not displaced_poses:
        summary["blockers"].append("blocked-no-displaced-pose")

    if summary["blockers"]:
        write_json(
            candidates_json_path,
            {
                "schemaVersion": SCHEMA_VERSION,
                "mode": "riftreader-family-snapshot-delta-candidates",
                "generatedAtUtc": utc_iso(),
                "processId": manifest.get("processId"),
                "targetWindowHandle": manifest.get("targetWindowHandle"),
                "candidateCount": 0,
                "candidates": [],
            },
        )
        write_jsonl(candidates_path, [])
        write_json(families_path, {"schemaVersion": SCHEMA_VERSION, "families": []})
        summary["status"] = "blocked"
        summary["next"]["recommendedAction"] = "Capture a baseline pose and at least one manually displaced pose, then rerun offline delta analysis."
        write_json(summary_path, summary)
        markdown_path.write_text(render_markdown(summary, []), encoding="utf-8")
        return summary, summary_path, markdown_path, candidates_json_path, candidates_path, families_path

    baseline_segments = {segment_key(segment): segment for segment in baseline_pose.get("segments", [])}
    passive_by_key = {
        key: [segment for pose in passive_poses for segment in pose.get("segments", []) if segment_key(segment) == key]
        for key in baseline_segments
    }
    displaced_by_key = {
        key: [segment for pose in displaced_poses for segment in pose.get("segments", []) if segment_key(segment) == key]
        for key in baseline_segments
    }

    axis_orders = [order.strip().lower() for order in str(args.axis_orders).split(",") if order.strip()]

    for key, base_segment in baseline_segments.items():
        base_data = read_segment_bytes(manifest_path, base_segment)
        base_addr = segment_base(base_segment)
        passive_noise: set[int] = set()
        passive_changed_total = 0
        displaced_changed_total = 0
        too_noisy = False

        for passive_segment in passive_by_key.get(key, []):
            passive_data = read_segment_bytes(manifest_path, passive_segment)
            if len(passive_data) != len(base_data):
                summary["warnings"].append(f"passive-segment-size-mismatch:{key}")
                continue
            changes = changed_offsets(base_data, passive_data)
            passive_changed_total += len(changes)
            passive_noise.update(changes)

        for displaced_pose in displaced_poses:
            displaced_ref = pose_reference(displaced_pose)
            if displaced_ref is None:
                summary["warnings"].append(f"displaced-reference-missing:{displaced_pose.get('label')}")
                continue
            api_delta = ref_delta(baseline_ref, displaced_ref)
            if api_delta["planar"] < args.min_api_planar_delta:
                summary["warnings"].append(f"displaced-pose-too-small:{displaced_pose.get('label')}:planar={api_delta['planar']:.6f}")
                continue
            displaced_segment = next((segment for segment in displaced_pose.get("segments", []) if segment_key(segment) == key), None)
            if displaced_segment is None:
                summary["warnings"].append(f"displaced-segment-missing:{key}")
                continue
            displaced_data = read_segment_bytes(manifest_path, displaced_segment)
            if len(displaced_data) != len(base_data):
                summary["warnings"].append(f"displaced-segment-size-mismatch:{key}")
                continue
            changes = changed_offsets(base_data, displaced_data)
            displaced_changed_total += len(changes)
            starts, truncated = candidate_starts_from_changes(
                changes,
                len(base_data),
                args.candidate_scan_stride,
                args.max_candidate_starts_per_segment,
            )
            too_noisy = too_noisy or truncated
            if truncated:
                summary["warnings"].append(f"candidate-starts-truncated:{key}:{args.max_candidate_starts_per_segment}")
            for offset in starts:
                for axis_order in axis_orders:
                    baseline_value = decode_vec3(base_data, offset, axis_order)
                    displaced_value = decode_vec3(displaced_data, offset, axis_order)
                    if baseline_value is None or displaced_value is None:
                        continue
                    if not plausible_coordinate(baseline_value, baseline_ref, args):
                        continue
                    if not plausible_coordinate(displaced_value, displaced_ref, args):
                        continue
                    mem_delta = value_delta(baseline_value, displaced_value)
                    error = tracking_error(api_delta, mem_delta)
                    if error["maxAbs"] > args.max_tracking_error:
                        continue
                    candidates.append(
                        build_candidate(
                            base_address=base_addr,
                            offset=offset,
                            segment=base_segment,
                            axis_order=axis_order,
                            baseline_label=str(baseline_pose.get("label") or "baseline"),
                            displaced_label=str(displaced_pose.get("label") or "displaced"),
                            baseline_ref=baseline_ref,
                            displaced_ref=displaced_ref,
                            baseline_value=baseline_value,
                            displaced_value=displaced_value,
                            passive_noise=passive_noise,
                        )
                    )

        segment_summaries.append(
            {
                "segmentKey": key,
                "baseHex": format_hex(base_addr),
                "rangeRank": base_segment.get("rangeRank"),
                "rangeSource": base_segment.get("rangeSource"),
                "rangeLabel": base_segment.get("rangeLabel"),
                "sizeBytes": len(base_data),
                "passiveChangedBytes": passive_changed_total,
                "passiveNoiseByteCount": len(passive_noise),
                "displacedChangedBytes": displaced_changed_total,
                "tooNoisyForFullCandidateStartScan": too_noisy,
            }
        )

    candidates = sorted(
        candidates,
        key=lambda item: (
            float(item["score"]),
            int(item["passiveNoiseByteOverlap"]),
            float(item["trackingError"]["maxAbs"]),
            int(item["address"]),
        ),
    )[: args.max_candidates]
    families = summarize_families(candidates)

    write_json(
        candidates_json_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "riftreader-family-snapshot-delta-candidates",
            "generatedAtUtc": utc_iso(),
            "processId": manifest.get("processId"),
            "targetWindowHandle": manifest.get("targetWindowHandle"),
            "candidateCount": len(candidates),
            "candidates": candidates,
        },
    )
    write_jsonl(candidates_path, candidates)
    write_json(
        families_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAtUtc": utc_iso(),
            "familyCount": len(families),
            "families": families,
        },
    )

    summary["status"] = "passed" if candidates else "blocked"
    if not candidates:
        summary["blockers"].append("no-delta-tracking-vec3-candidates")
        summary["next"]["recommendedAction"] = "Widen the family range set, use more displacement, or enable additional axis orders before x64dbg."
    else:
        summary["next"]["recommendedAction"] = "Run focused readback/ranking on candidate-vec3.jsonl; keep movement and x64dbg blocked until candidates survive proof gates."

    summary["analysis"].update(
        {
            "segmentCount": len(segment_summaries),
            "candidateCount": len(candidates),
            "familyCount": len(families),
            "cleanCandidateCount": sum(1 for item in candidates if item["cleanDisplacementWindow"]),
            "bestCandidate": candidates[0] if candidates else None,
            "topFamily": families[0] if families else None,
            "segments": segment_summaries[: args.top],
        }
    )
    write_json(summary_path, summary)
    markdown_path.write_text(render_markdown(summary, families[: args.top]), encoding="utf-8")
    return summary, summary_path, markdown_path, candidates_json_path, candidates_path, families_path


def render_markdown(summary: dict[str, Any], families: list[dict[str, Any]]) -> str:
    rows = []
    for family in families:
        best = family.get("bestCandidate") or {}
        rows.append(
            f"| `{family.get('familyBaseHex')}` | `{family.get('candidateCount')}` | "
            f"`{best.get('addressHex')}` | `{best.get('trackingErrorMaxAbs')}` | "
            f"`{family.get('commonAddressDeltaHex')}` |"
        )
    return "\n".join(
        [
            "# Family snapshot delta analysis",
            "",
            f"- Status: `{summary.get('status')}`",
            f"- Blockers: `{', '.join(summary.get('blockers') or [])}`",
            f"- Candidates: `{summary.get('analysis', {}).get('candidateCount')}`",
            f"- Families: `{summary.get('analysis', {}).get('familyCount')}`",
            f"- Candidate JSONL: `{summary.get('artifacts', {}).get('candidateVec3Jsonl')}`",
            "",
            "| Family | Candidates | Best address | Max tracking error | Common stride |",
            "|---|---:|---|---:|---|",
            *rows,
            "",
            "Candidate-only evidence. No movement, debugger, Cheat Engine, provider writes, or promotion are authorized by this analysis.",
            "",
        ]
    )


def write_gzip(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(data))


def build_self_test_manifest(root: Path, *, include_displaced: bool = True, passive_noise: bool = True, unaligned: bool = True) -> Path:
    run_dir = root / f"family-snapshot-delta-selftest-{utc_stamp()}"
    offset = 0x23 if unaligned else 0x20
    base_addr = 0x10000000000
    baseline = bytearray(512)
    struct.pack_into("<fff", baseline, offset, 100.0, 20.0, 200.0)
    # Repeated family/stride candidate for stride inference.
    struct.pack_into("<fff", baseline, offset + 0x100, 100.0, 20.0, 200.0)
    passive = bytearray(baseline)
    displaced = bytearray(baseline)
    struct.pack_into("<fff", displaced, offset, 101.25, 20.0, 198.75)
    struct.pack_into("<fff", displaced, offset + 0x100, 101.25, 20.0, 198.75)
    if passive_noise:
        struct.pack_into("<f", passive, 0x180, 123.456)

    poses: list[dict[str, Any]] = []
    for label, role, data, ref in [
        ("baseline-still", "baseline", baseline, {"x": 100.0, "y": 20.0, "z": 200.0}),
        ("passive-still", "passive", passive, {"x": 100.0, "y": 20.0, "z": 200.0}),
        ("operator-displaced-settled", "displaced", displaced, {"x": 101.25, "y": 20.0, "z": 198.75}),
    ]:
        if role == "displaced" and not include_displaced:
            continue
        segment_path = run_dir / label / "segments" / "seg-000001-10000000000-10000000200.bin.gz"
        write_gzip(segment_path, bytes(data))
        poses.append(
            {
                "label": label,
                "role": role,
                "reference": {"coordinate": ref, "fresh": True},
                "segments": [
                    {
                        "id": "seg-000001",
                        "path": str(segment_path.relative_to(run_dir)),
                        "compression": "gzip",
                        "baseHex": format_hex(base_addr),
                        "endHex": format_hex(base_addr + len(data)),
                        "sizeBytes": len(data),
                        "rangeRank": 1,
                    }
                ],
            }
        )
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-family-snapshot-sequence",
        "generatedAtUtc": utc_iso(),
        "processId": 0,
        "targetWindowHandle": "0x0",
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
        },
        "poses": poses,
    }
    manifest_path = run_dir / "manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze family-group snapshot deltas offline.")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--axis-orders", default="xyz")
    parser.add_argument("--candidate-scan-stride", type=int, choices=(1, 4), default=1)
    parser.add_argument("--max-tracking-error", type=float, default=DEFAULT_MAX_TRACKING_ERROR)
    parser.add_argument("--min-api-planar-delta", type=float, default=DEFAULT_MIN_API_PLANAR_DELTA)
    parser.add_argument("--window-x", type=float, default=DEFAULT_WINDOW_X)
    parser.add_argument("--window-y", type=float, default=DEFAULT_WINDOW_Y)
    parser.add_argument("--window-z", type=float, default=DEFAULT_WINDOW_Z)
    parser.add_argument("--max-abs-coordinate", type=float, default=DEFAULT_MAX_ABS_COORDINATE)
    parser.add_argument("--max-candidate-starts-per-segment", type=int, default=DEFAULT_MAX_CANDIDATE_STARTS_PER_SEGMENT)
    parser.add_argument("--max-candidates", type=int, default=1000)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--self-test-no-displaced", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if args.self_test or args.self_test_no_displaced:
            root = args.output_root.resolve() if args.output_root else Path(tempfile.mkdtemp(prefix="riftreader-family-delta-selftest-"))
            manifest_path = build_self_test_manifest(root, include_displaced=not args.self_test_no_displaced)
        elif args.manifest:
            manifest_path = args.manifest.resolve()
        else:
            raise RuntimeError("--manifest is required unless --self-test is used")

        summary, summary_path, markdown_path, candidates_json_path, candidates_path, families_path = analyze_manifest(manifest_path, args.output_root, args)
        result = {
            "status": summary.get("status"),
            "blockers": summary.get("blockers"),
            "candidateCount": summary.get("analysis", {}).get("candidateCount"),
            "familyCount": summary.get("analysis", {}).get("familyCount"),
            "summaryJson": str(summary_path),
            "summaryMarkdown": str(markdown_path),
            "candidateVec3Json": str(candidates_json_path),
            "candidateVec3Jsonl": str(candidates_path),
            "candidateFamiliesJson": str(families_path),
        }
        print(json.dumps(summary if args.json else result, indent=2))
        return 0 if summary.get("status") == "passed" else 2
    except Exception as exc:  # noqa: BLE001
        result = {"status": "failed", "errors": [{"type": type(exc).__name__, "message": str(exc)}]}
        print(json.dumps(result, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
