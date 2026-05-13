from __future__ import annotations

import argparse
import glob
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_MIN_POSE_SUPPORT = 2
DEFAULT_TOP = 25
DEFAULT_POSE_DISTANCE_MIN = 0.25


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def get_mapping_value(document: dict[str, Any], *names: str) -> Any:
    for expected in names:
        for key, value in document.items():
            if str(key).lower() == expected.lower():
                return value
    return None


def to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip(), 0)
    except (TypeError, ValueError):
        return None


def to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_hwnd(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return f"0x{value:X}"
    text = str(value).strip()
    if not text:
        return None
    try:
        return f"0x{int(text, 0):X}"
    except ValueError:
        return text.upper()


def normalize_hex(value: Any) -> str | None:
    parsed = to_int_or_none(value)
    if parsed is None:
        return None
    return f"0x{parsed:X}"


def resolve_path(value: str | Path, repo_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (repo_root / path).resolve()


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def coordinate_from_mapping(document: dict[str, Any] | None) -> dict[str, float | None]:
    if not isinstance(document, dict):
        return {"x": None, "y": None, "z": None}
    return {
        "x": to_float_or_none(get_mapping_value(document, "x", "X")),
        "y": to_float_or_none(get_mapping_value(document, "y", "Y")),
        "z": to_float_or_none(get_mapping_value(document, "z", "Z")),
    }


def extract_reference(document: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    reference = get_mapping_value(candidate, "reference_coordinate", "referenceCoordinate")
    if not isinstance(reference, dict):
        reference = get_mapping_value(document, "reference", "Reference")
    if not isinstance(reference, dict):
        reference = {}
    coordinate = coordinate_from_mapping(reference)
    return {
        "x": coordinate["x"],
        "y": coordinate["y"],
        "z": coordinate["z"],
        "source": get_mapping_value(reference, "source", "Source"),
        "referenceFile": get_mapping_value(reference, "referenceFile", "ReferenceFile"),
    }


def extract_value(candidate: dict[str, Any]) -> dict[str, float | None]:
    preview = get_mapping_value(candidate, "value_preview", "valuePreview", "ValuePreview")
    if isinstance(preview, list) and len(preview) >= 3:
        return {
            "x": to_float_or_none(preview[0]),
            "y": to_float_or_none(preview[1]),
            "z": to_float_or_none(preview[2]),
        }
    return {
        "x": to_float_or_none(get_mapping_value(candidate, "best_memory_x", "bestMemoryX", "x", "X")),
        "y": to_float_or_none(get_mapping_value(candidate, "best_memory_y", "bestMemoryY", "y", "Y")),
        "z": to_float_or_none(get_mapping_value(candidate, "best_memory_z", "bestMemoryZ", "z", "Z")),
    }


def compute_max_abs_distance(reference: dict[str, Any], value: dict[str, Any]) -> float | None:
    axes = ("x", "y", "z")
    if any(reference.get(axis) is None or value.get(axis) is None for axis in axes):
        return None
    return max(abs(float(value[axis]) - float(reference[axis])) for axis in axes)


def finite_or_inf(value: float | None) -> float:
    if value is None:
        return math.inf
    if not math.isfinite(value):
        return math.inf
    return float(value)


def reference_tuple(observation: dict[str, Any]) -> tuple[float, float, float] | None:
    reference = observation.get("reference")
    if not isinstance(reference, dict):
        return None
    values = tuple(to_float_or_none(reference.get(axis)) for axis in ("x", "y", "z"))
    if any(value is None for value in values):
        return None
    return float(values[0]), float(values[1]), float(values[2])


def reference_distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> dict[str, float]:
    dx = right[0] - left[0]
    dy = right[1] - left[1]
    dz = right[2] - left[2]
    return {
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "planar": math.sqrt((dx * dx) + (dz * dz)),
        "spatial": math.sqrt((dx * dx) + (dy * dy) + (dz * dz)),
        "maxAbs": max(abs(dx), abs(dy), abs(dz)),
    }


def average(values: Iterable[float]) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return None
    return sum(finite) / len(finite)


def max_or_none(values: Iterable[float]) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return None
    return max(finite)


def min_or_none(values: Iterable[float]) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return None
    return min(finite)


def candidate_observation(
    *,
    document: dict[str, Any],
    candidate: dict[str, Any],
    source_file: Path,
) -> dict[str, Any] | None:
    address_hex = normalize_hex(
        get_mapping_value(
            candidate,
            "absolute_address_hex",
            "absoluteAddressHex",
            "candidate_address_hex",
            "candidateAddressHex",
            "addressHex",
            "AddressHex",
            "address",
            "Address",
        )
    )
    if not address_hex:
        return None

    base_hex = normalize_hex(
        get_mapping_value(candidate, "base_address_hex", "baseAddressHex", "regionBaseHex", "region_address_hex")
    )
    address_int = to_int_or_none(address_hex)
    base_int = to_int_or_none(base_hex)
    offset_hex = normalize_hex(get_mapping_value(candidate, "offset_hex", "offsetHex"))
    if offset_hex is None and address_int is not None and base_int is not None:
        offset_hex = f"0x{address_int - base_int:X}"

    value = extract_value(candidate)
    reference = extract_reference(document, candidate)
    distance = to_float_or_none(get_mapping_value(candidate, "best_max_abs_distance", "bestMaxAbsDistance"))
    if distance is None:
        distance = compute_max_abs_distance(reference, value)

    generated_at = get_mapping_value(document, "generatedAtUtc", "generated_at_utc", "GeneratedAtUtc")
    doc_process_id = to_int_or_none(get_mapping_value(document, "processId", "process_id", "ProcessId"))
    doc_hwnd = normalize_hwnd(get_mapping_value(document, "targetWindowHandle", "target_window_handle", "TargetWindowHandle"))
    process_id = to_int_or_none(get_mapping_value(candidate, "process_id", "processId", "ProcessId")) or doc_process_id
    target_hwnd = normalize_hwnd(
        get_mapping_value(candidate, "target_window_handle", "targetWindowHandle", "TargetWindowHandle")
    ) or doc_hwnd

    return {
        "sourceFile": str(source_file),
        "sourcePoseKey": str(source_file),
        "poseKey": str(source_file),
        "poseLabel": str(generated_at or source_file.parent.name),
        "generatedAtUtc": generated_at,
        "candidateId": get_mapping_value(candidate, "candidate_id", "candidateId", "CandidateId", "id", "Id"),
        "addressHex": address_hex,
        "familyBaseHex": base_hex,
        "offsetHex": offset_hex,
        "pageHex": f"0x{address_int & ~0xFFF:X}" if address_int is not None else None,
        "megapageHex": f"0x{address_int & ~0xFFFFF:X}" if address_int is not None else None,
        "processId": process_id,
        "targetWindowHandle": target_hwnd,
        "value": value,
        "reference": reference,
        "bestMaxAbsDistance": distance,
        "rankScore": to_float_or_none(get_mapping_value(candidate, "rank_score", "rankScore", "score_total", "scoreTotal")),
        "classification": get_mapping_value(candidate, "classification", "Classification"),
        "validationStatus": get_mapping_value(candidate, "validation_status", "validationStatus"),
        "truthReadiness": get_mapping_value(candidate, "truth_readiness", "truthReadiness"),
    }


def observation_matches_target(
    observation: dict[str, Any],
    *,
    process_id: int | None,
    target_hwnd: str | None,
) -> bool:
    if process_id is not None and observation.get("processId") != process_id:
        return False
    if target_hwnd is not None and observation.get("targetWindowHandle") != target_hwnd:
        return False
    return True


def load_candidate_file(
    path: Path,
    *,
    process_id: int | None,
    target_hwnd: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    document = read_json_file(path)
    if not isinstance(document, dict):
        raise ValueError("candidate file root must be a JSON object")

    candidates = get_mapping_value(document, "candidates", "Candidates")
    if not isinstance(candidates, list):
        candidates = []

    observations: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            warnings.append(f"candidate-skip-non-object:{path}")
            continue
        observation = candidate_observation(document=document, candidate=candidate, source_file=path)
        if observation is None:
            warnings.append(f"candidate-skip-missing-address:{path}")
            continue
        if not observation_matches_target(observation, process_id=process_id, target_hwnd=target_hwnd):
            warnings.append(
                "candidate-skip-target-mismatch:"
                f"{path}:pid={observation.get('processId')}:hwnd={observation.get('targetWindowHandle')}"
            )
            continue
        observations.append(observation)

    pose = {
        "sourceFile": str(path),
        "generatedAtUtc": get_mapping_value(document, "generatedAtUtc", "generated_at_utc", "GeneratedAtUtc"),
        "processId": to_int_or_none(get_mapping_value(document, "processId", "process_id", "ProcessId")),
        "targetWindowHandle": normalize_hwnd(
            get_mapping_value(document, "targetWindowHandle", "target_window_handle", "TargetWindowHandle")
        ),
        "reference": coordinate_from_mapping(get_mapping_value(document, "reference", "Reference")),
        "candidateCount": len(candidates),
        "acceptedObservationCount": len(observations),
    }
    if len(candidates) == 0:
        warnings.append(f"candidate-file-has-no-candidates:{path}")
    return pose, observations, warnings


def expand_candidate_files(args: argparse.Namespace, repo_root: Path) -> tuple[list[Path], list[str]]:
    warnings: list[str] = []
    paths: list[Path] = []
    for value in args.candidate_file or []:
        path = resolve_path(value, repo_root)
        paths.append(path)
    for pattern in args.candidate_glob or []:
        if Path(pattern).is_absolute():
            matches = [Path(match) for match in glob.glob(pattern, recursive=True)]
        else:
            matches = [Path(match) for match in glob.glob(str(repo_root / pattern), recursive=True)]
        if not matches:
            warnings.append(f"candidate-glob-no-matches:{pattern}")
        paths.extend(matches)
    if not paths and not args.no_default_candidate_glob:
        paths.extend((repo_root / "scripts" / "captures").glob("family-scan-currentpid-*/api-family-vec3-candidates.json"))

    unique: dict[str, Path] = {}
    for path in paths:
        resolved = path.resolve()
        unique[str(resolved)] = resolved
    return sorted(unique.values(), key=lambda path: str(path)), warnings


def best_by_pose(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for observation in observations:
        pose_key = str(observation.get("poseKey"))
        current = best.get(pose_key)
        if current is None or observation_sort_key(observation) < observation_sort_key(current):
            best[pose_key] = observation
    return list(best.values())


def assign_pose_groups(
    observations: list[dict[str, Any]],
    *,
    pose_distance_min: float,
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for observation in sorted(
        observations,
        key=lambda item: (str(item.get("generatedAtUtc") or ""), str(item.get("sourceFile") or "")),
    ):
        coordinate = reference_tuple(observation)
        if coordinate is None:
            key = str(observation.get("sourcePoseKey") or observation.get("sourceFile"))
            observation["poseKey"] = key
            observation["poseGroup"] = {
                "poseKey": key,
                "source": "source-file-no-reference-coordinate",
                "reference": observation.get("reference"),
            }
            groups.append(
                {
                    "poseKey": key,
                    "source": "source-file-no-reference-coordinate",
                    "reference": observation.get("reference"),
                    "sourceFiles": [observation.get("sourceFile")],
                    "observationCount": 1,
                }
            )
            continue

        matched: dict[str, Any] | None = None
        matched_distance: dict[str, float] | None = None
        for group in groups:
            representative = group.get("_coordinate")
            if representative is None:
                continue
            distance = reference_distance(representative, coordinate)
            if distance["maxAbs"] <= pose_distance_min:
                matched = group
                matched_distance = distance
                break

        if matched is None:
            key = f"pose-{len([group for group in groups if group.get('_coordinate') is not None]) + 1:06d}"
            matched = {
                "poseKey": key,
                "source": "reference-coordinate-cluster",
                "_coordinate": coordinate,
                "reference": {
                    "x": coordinate[0],
                    "y": coordinate[1],
                    "z": coordinate[2],
                },
                "sourceFiles": [],
                "observationCount": 0,
            }
            groups.append(matched)
            matched_distance = {"dx": 0.0, "dy": 0.0, "dz": 0.0, "planar": 0.0, "spatial": 0.0, "maxAbs": 0.0}

        matched["observationCount"] = int(matched.get("observationCount") or 0) + 1
        source_file = observation.get("sourceFile")
        if source_file and source_file not in matched["sourceFiles"]:
            matched["sourceFiles"].append(source_file)
        observation["poseKey"] = matched["poseKey"]
        observation["poseGroup"] = {
            "poseKey": matched["poseKey"],
            "source": matched["source"],
            "distanceFromRepresentative": matched_distance,
            "reference": observation.get("reference"),
        }

    return [
        {key: value for key, value in group.items() if key != "_coordinate"}
        for group in groups
    ]


def observation_sort_key(observation: dict[str, Any]) -> tuple[float, str, str]:
    return (
        finite_or_inf(observation.get("bestMaxAbsDistance")),
        str(observation.get("candidateId") or ""),
        str(observation.get("sourceFile") or ""),
    )


def promotion_blockers(support_pose_count: int, min_pose_support: int) -> list[str]:
    blockers: list[str] = []
    if support_pose_count < min_pose_support:
        blockers.append(f"pose-support-below-min:{support_pose_count}<{min_pose_support}")
    blockers.extend(
        [
            "restart-validation-missing",
            "runtime-readback-proof-missing",
            "movement-proof-missing",
            "x64dbg-access-proof-missing",
        ]
    )
    return blockers


def observation_summary(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceFile": observation.get("sourceFile"),
        "poseLabel": observation.get("poseLabel"),
        "poseKey": observation.get("poseKey"),
        "generatedAtUtc": observation.get("generatedAtUtc"),
        "candidateId": observation.get("candidateId"),
        "addressHex": observation.get("addressHex"),
        "familyBaseHex": observation.get("familyBaseHex"),
        "offsetHex": observation.get("offsetHex"),
        "bestMaxAbsDistance": observation.get("bestMaxAbsDistance"),
        "value": observation.get("value"),
        "reference": observation.get("reference"),
    }


def build_address_ranking(
    address_hex: str,
    observations: list[dict[str, Any]],
    *,
    min_pose_support: int,
) -> dict[str, Any]:
    per_pose = sorted(best_by_pose(observations), key=observation_sort_key)
    deltas = [finite_or_inf(observation.get("bestMaxAbsDistance")) for observation in per_pose]
    best_observation = per_pose[0] if per_pose else observations[0]
    support_pose_count = len({observation.get("poseKey") for observation in per_pose})
    return {
        "kind": "exact-address",
        "addressHex": address_hex,
        "familyBaseHex": best_observation.get("familyBaseHex"),
        "offsetHex": best_observation.get("offsetHex"),
        "supportPoseCount": support_pose_count,
        "observationCount": len(observations),
        "avgBestMaxAbsDistance": average(deltas),
        "maxBestMaxAbsDistance": max_or_none(deltas),
        "minBestMaxAbsDistance": min_or_none(deltas),
        "candidateOnly": True,
        "promotionEligible": False,
        "promotionBlockers": promotion_blockers(support_pose_count, min_pose_support),
        "x64dbgWatchCandidate": {
            "addressHex": address_hex,
            "watchSizeBytes": 12,
            "axisOrder": "xyz",
            "requiresCurrentTurnApproval": True,
        },
        "bestObservation": observation_summary(best_observation),
        "observations": [observation_summary(observation) for observation in per_pose],
    }


def address_ranking_sort_key(ranking: dict[str, Any]) -> tuple[int, float, float, str]:
    return (
        -int(ranking.get("supportPoseCount") or 0),
        finite_or_inf(ranking.get("avgBestMaxAbsDistance")),
        finite_or_inf(ranking.get("maxBestMaxAbsDistance")),
        str(ranking.get("addressHex") or ""),
    )


def build_family_ranking(
    family_base_hex: str,
    observations: list[dict[str, Any]],
    *,
    address_rankings_by_address: dict[str, dict[str, Any]],
    min_pose_support: int,
) -> dict[str, Any]:
    per_pose = sorted(best_by_pose(observations), key=observation_sort_key)
    deltas = [finite_or_inf(observation.get("bestMaxAbsDistance")) for observation in per_pose]
    support_pose_count = len({observation.get("poseKey") for observation in per_pose})
    addresses = sorted({str(observation.get("addressHex")) for observation in observations if observation.get("addressHex")})
    top_addresses = sorted(
        [address_rankings_by_address[address] for address in addresses if address in address_rankings_by_address],
        key=address_ranking_sort_key,
    )
    best_address = top_addresses[0] if top_addresses else None
    best_observation = per_pose[0] if per_pose else observations[0]
    return {
        "kind": "family-base",
        "familyBaseHex": family_base_hex,
        "supportPoseCount": support_pose_count,
        "observationCount": len(observations),
        "uniqueAddressCount": len(addresses),
        "bestAddressHex": best_address.get("addressHex") if best_address else None,
        "bestAddressSupportPoseCount": best_address.get("supportPoseCount") if best_address else 0,
        "avgBestMaxAbsDistance": average(deltas),
        "maxBestMaxAbsDistance": max_or_none(deltas),
        "minBestMaxAbsDistance": min_or_none(deltas),
        "candidateOnly": True,
        "promotionEligible": False,
        "promotionBlockers": promotion_blockers(support_pose_count, min_pose_support),
        "x64dbgWatchCandidates": [
            ranking.get("x64dbgWatchCandidate") for ranking in top_addresses[:5] if ranking.get("x64dbgWatchCandidate")
        ],
        "bestObservation": observation_summary(best_observation),
        "topAddresses": [
            {
                "addressHex": ranking.get("addressHex"),
                "offsetHex": ranking.get("offsetHex"),
                "supportPoseCount": ranking.get("supportPoseCount"),
                "avgBestMaxAbsDistance": ranking.get("avgBestMaxAbsDistance"),
                "maxBestMaxAbsDistance": ranking.get("maxBestMaxAbsDistance"),
            }
            for ranking in top_addresses[:10]
        ],
        "observations": [observation_summary(observation) for observation in per_pose],
    }


def family_ranking_sort_key(ranking: dict[str, Any]) -> tuple[int, int, float, float, str]:
    return (
        -int(ranking.get("supportPoseCount") or 0),
        -int(ranking.get("bestAddressSupportPoseCount") or 0),
        finite_or_inf(ranking.get("avgBestMaxAbsDistance")),
        finite_or_inf(ranking.get("maxBestMaxAbsDistance")),
        str(ranking.get("familyBaseHex") or ""),
    )


def rank_observations(
    observations: list[dict[str, Any]],
    *,
    min_pose_support: int,
    top: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observations_by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    observations_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        address = observation.get("addressHex")
        family = observation.get("familyBaseHex")
        if address:
            observations_by_address[str(address)].append(observation)
        if family:
            observations_by_family[str(family)].append(observation)

    address_rankings = sorted(
        [
            build_address_ranking(address, grouped, min_pose_support=min_pose_support)
            for address, grouped in observations_by_address.items()
        ],
        key=address_ranking_sort_key,
    )
    address_rankings_by_address = {str(ranking["addressHex"]): ranking for ranking in address_rankings}
    family_rankings = sorted(
        [
            build_family_ranking(
                family,
                grouped,
                address_rankings_by_address=address_rankings_by_address,
                min_pose_support=min_pose_support,
            )
            for family, grouped in observations_by_family.items()
        ],
        key=family_ranking_sort_key,
    )
    return address_rankings[:top], family_rankings[:top]


def build_markdown(summary: dict[str, Any]) -> str:
    top_address = summary.get("topAddress") or {}
    top_family = summary.get("topFamily") or {}
    lines = [
        "# Coordinate family pose ranking",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Target PID: `{summary.get('target', {}).get('processId')}`",
        f"- Target HWND: `{summary.get('target', {}).get('targetWindowHandle')}`",
        f"- Candidate files accepted: `{summary.get('acceptedCandidateFileCount')}` / `{summary.get('candidateFileCount')}`",
        f"- Observation count: `{summary.get('observationCount')}`",
        f"- Top exact address: `{top_address.get('addressHex')}` support `{top_address.get('supportPoseCount')}`",
        f"- Top family: `{top_family.get('familyBaseHex')}` support `{top_family.get('supportPoseCount')}`",
        "",
        "Candidate-only evidence. This ranking does not prove a static pointer chain and does not authorize movement or x64dbg attach by itself.",
        "",
        "## Top exact addresses",
        "",
        "| Rank | Address | Family | Offset | Pose support | Avg delta | Max delta |",
        "|---:|---|---|---|---:|---:|---:|",
    ]
    for index, ranking in enumerate(summary.get("addressRankings") or [], start=1):
        lines.append(
            f"| {index} | `{ranking.get('addressHex')}` | `{ranking.get('familyBaseHex')}` | "
            f"`{ranking.get('offsetHex')}` | `{ranking.get('supportPoseCount')}` | "
            f"`{ranking.get('avgBestMaxAbsDistance')}` | `{ranking.get('maxBestMaxAbsDistance')}` |"
        )
    lines.extend(
        [
            "",
            "## Top families",
            "",
            "| Rank | Family | Pose support | Best address | Best address support | Avg delta | Max delta |",
            "|---:|---|---:|---|---:|---:|---:|",
        ]
    )
    for index, ranking in enumerate(summary.get("familyRankings") or [], start=1):
        lines.append(
            f"| {index} | `{ranking.get('familyBaseHex')}` | `{ranking.get('supportPoseCount')}` | "
            f"`{ranking.get('bestAddressHex')}` | `{ranking.get('bestAddressSupportPoseCount')}` | "
            f"`{ranking.get('avgBestMaxAbsDistance')}` | `{ranking.get('maxBestMaxAbsDistance')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"][:50])
    return "\n".join(lines).rstrip() + "\n"


def write_top_jsonl(path: Path, address_rankings: list[dict[str, Any]], family_rankings: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for index, ranking in enumerate(address_rankings, start=1):
        rows.append({"rank": index, "rankingKind": "exact-address", **ranking})
    for index, ranking in enumerate(family_rankings, start=1):
        rows.append({"rank": index, "rankingKind": "family-base", **ranking})
    write_text_atomic(path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = resolve_path(args.repo_root, Path.cwd()) if args.repo_root else repo_root_from_module()
    process_id = to_int_or_none(args.process_id)
    target_hwnd = normalize_hwnd(args.target_hwnd)
    output_root = resolve_path(args.output_root, repo_root) if args.output_root else (
        repo_root / "scripts" / "captures" / f"coordinate-family-rank-{utc_stamp()}"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    blockers: list[str] = []
    warnings: list[str] = []
    candidate_files, file_warnings = expand_candidate_files(args, repo_root)
    warnings.extend(file_warnings)
    if not candidate_files:
        blockers.append("candidate-files-not-found")

    poses: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    accepted_candidate_file_count = 0
    for path in candidate_files:
        if not path.exists():
            warnings.append(f"candidate-file-missing:{path}")
            continue
        try:
            pose, pose_observations, load_warnings = load_candidate_file(path, process_id=process_id, target_hwnd=target_hwnd)
        except Exception as exc:  # noqa: BLE001 - artifact must preserve read failures as evidence.
            warnings.append(f"candidate-file-read-failed:{path}:{type(exc).__name__}:{exc}")
            continue
        warnings.extend(load_warnings)
        if pose_observations:
            accepted_candidate_file_count += 1
        poses.append(pose)
        observations.extend(pose_observations)

    if not observations and not blockers:
        blockers.append("candidate-observations-not-found-for-target")

    pose_groups = assign_pose_groups(observations, pose_distance_min=args.pose_distance_min)

    address_rankings, family_rankings = rank_observations(
        observations,
        min_pose_support=args.min_pose_support,
        top=args.top,
    )
    if observations and not any(int(ranking.get("supportPoseCount") or 0) >= args.min_pose_support for ranking in address_rankings):
        warnings.append(f"no-exact-address-meets-min-pose-support:{args.min_pose_support}")
    if observations and not any(int(ranking.get("supportPoseCount") or 0) >= args.min_pose_support for ranking in family_rankings):
        warnings.append(f"no-family-meets-min-pose-support:{args.min_pose_support}")

    summary_json = output_root / "coordinate-family-rankings.json"
    summary_md = output_root / "coordinate-family-rankings.md"
    top_jsonl = output_root / "top-ranked-candidates.jsonl"
    status = "blocked" if blockers else "ranked"
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-coordinate-family-pose-ranking",
        "status": status,
        "generatedAtUtc": utc_iso(),
        "target": {
            "processId": process_id,
            "targetWindowHandle": target_hwnd,
        },
        "input": {
            "candidateFiles": [str(path) for path in candidate_files],
            "candidateGlob": args.candidate_glob or [],
            "minPoseSupport": args.min_pose_support,
            "poseDistanceMin": args.pose_distance_min,
            "top": args.top,
        },
        "candidateFileCount": len(candidate_files),
        "acceptedCandidateFileCount": accepted_candidate_file_count,
        "poseCount": len(poses),
        "observationPoseCount": len({observation.get("poseKey") for observation in observations}),
        "observationCount": len(observations),
        "addressGroupCount": len({observation.get("addressHex") for observation in observations if observation.get("addressHex")}),
        "familyGroupCount": len({observation.get("familyBaseHex") for observation in observations if observation.get("familyBaseHex")}),
        "topAddress": address_rankings[0] if address_rankings else None,
        "topFamily": family_rankings[0] if family_rankings else None,
        "addressRankings": address_rankings,
        "familyRankings": family_rankings,
        "poses": poses,
        "poseGroups": pose_groups,
        "safety": {
            "candidateOnly": True,
            "promotionEligible": False,
            "movementAllowed": False,
            "gameInputSent": False,
            "targetMemoryWritten": False,
            "x64dbgAttachAuthorized": False,
            "x64dbgAttached": False,
            "breakpointsSet": False,
            "watchpointsSet": False,
        },
        "rankPolicy": {
            "addressRanking": "supportPoseCount desc, avgBestMaxAbsDistance asc, maxBestMaxAbsDistance asc",
            "familyRanking": (
                "supportPoseCount desc, bestAddressSupportPoseCount desc, "
                "avgBestMaxAbsDistance asc, maxBestMaxAbsDistance asc"
            ),
            "poseSupport": (
                "candidate files only add support when their API reference coordinates differ by more than "
                "poseDistanceMin on at least one axis; repeated same-position scans share one pose group"
            ),
        },
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "topRankedCandidatesJsonl": str(top_jsonl),
        },
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    write_top_jsonl(top_jsonl, address_rankings, family_rankings)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank current-PID coordinate family candidates across pose snapshots.")
    parser.add_argument("--candidate-file", action="append", help="api-family-vec3-candidates.json file to rank.")
    parser.add_argument("--candidate-glob", action="append", help="Glob of api-family-vec3-candidates.json files.")
    parser.add_argument("--no-default-candidate-glob", action="store_true")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--process-id", default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--min-pose-support", type=int, default=DEFAULT_MIN_POSE_SUPPORT)
    parser.add_argument("--pose-distance-min", type=float, default=DEFAULT_POSE_DISTANCE_MIN)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
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
                    "topAddress": (summary.get("topAddress") or {}).get("addressHex"),
                    "topAddressSupportPoseCount": (summary.get("topAddress") or {}).get("supportPoseCount"),
                    "topFamily": (summary.get("topFamily") or {}).get("familyBaseHex"),
                    "topFamilySupportPoseCount": (summary.get("topFamily") or {}).get("supportPoseCount"),
                    "observationCount": summary.get("observationCount"),
                    "blockers": summary.get("blockers"),
                    "warnings": summary.get("warnings"),
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "topRankedCandidatesJsonl": summary["artifacts"]["topRankedCandidatesJsonl"],
                    "candidateOnly": True,
                    "x64dbgAttachAuthorized": False,
                },
                indent=2,
            )
        )
    return 0 if summary["status"] == "ranked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
