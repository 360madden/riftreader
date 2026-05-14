from __future__ import annotations

import argparse
import html
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .reports import write_json, write_text_atomic
from .riftscan_coordination import coerce_int, normalize_hwnd, read_json_file

SCHEMA_VERSION = 1
DEFAULT_TOLERANCE = 0.25


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def path_text(path: Path | None, repo_root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def artifact_path_text(value: Any, repo_root: Path) -> str | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = repo_root / path
    return path_text(path, repo_root)


def first_present(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping and mapping[name] not in (None, ""):
            return mapping[name]
    return None


def number_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def int_or_none(value: Any) -> int | None:
    try:
        return coerce_int(value)
    except Exception:  # noqa: BLE001 - malformed external artifacts should classify as unknown.
        return None


def bool_or_false(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def read_optional_json(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, None
    if not path.exists():
        return None, f"artifact_missing:{path}"
    try:
        value = read_json_file(path)
    except Exception as exc:  # noqa: BLE001 - route should preserve unreadable artifact evidence.
        return None, f"artifact_unreadable:{path}:{type(exc).__name__}:{exc}"
    if not isinstance(value, dict):
        return None, f"artifact_not_json_object:{path}"
    return value, None


def extract_target(document: Mapping[str, Any]) -> dict[str, Any]:
    nested_target = dict_or_empty(document.get("target"))
    source = nested_target or document
    process_id = int_or_none(first_present(source, "processId", "ProcessId", "pid", "Pid", "requestedPid", "ownerPid"))
    if process_id is None and nested_target:
        process_id = int_or_none(first_present(document, "processId", "ProcessId", "pid", "Pid", "requestedPid", "ownerPid"))
    hwnd = normalize_hwnd(
        first_present(
            source,
            "targetWindowHandle",
            "TargetWindowHandle",
            "hwnd",
            "Hwnd",
            "windowHandle",
            "requestedHwnd",
        )
    )
    if hwnd is None and nested_target:
        hwnd = normalize_hwnd(
            first_present(
                document,
                "targetWindowHandle",
                "TargetWindowHandle",
                "hwnd",
                "Hwnd",
                "windowHandle",
                "requestedHwnd",
            )
        )
    process_name = first_present(source, "processName", "ProcessName", "requestedProcessName")
    if process_name is None and nested_target:
        process_name = first_present(document, "processName", "ProcessName", "requestedProcessName")
    process_start = first_present(
        source,
        "processStartUtc",
        "ProcessStartUtc",
        "expectedProcessStartUtc",
        "ExpectedProcessStartUtc",
    )
    if process_start is None and nested_target:
        process_start = first_present(
            document,
            "processStartUtc",
            "ProcessStartUtc",
            "expectedProcessStartUtc",
            "ExpectedProcessStartUtc",
        )
    return {
        "processName": process_name,
        "processId": process_id,
        "targetWindowHandle": hwnd,
        "processStartUtc": process_start,
    }


def requested_target(
    *,
    process_id: int | None,
    target_window_handle: str | None,
    process_name: str | None,
    process_start_utc: str | None,
    current_truth: Mapping[str, Any] | None,
) -> dict[str, Any]:
    current_target = extract_target(current_truth or {}) if current_truth else {}
    return {
        "processName": process_name or current_target.get("processName") or "rift_x64",
        "processId": process_id if process_id is not None else current_target.get("processId"),
        "targetWindowHandle": normalize_hwnd(target_window_handle or current_target.get("targetWindowHandle")),
        "processStartUtc": process_start_utc or current_target.get("processStartUtc"),
    }


def target_mismatches(expected: Mapping[str, Any], actual: Mapping[str, Any], *, label: str) -> list[str]:
    issues: list[str] = []
    expected_pid = int_or_none(expected.get("processId"))
    actual_pid = int_or_none(actual.get("processId"))
    if expected_pid is not None and actual_pid is not None and expected_pid != actual_pid:
        issues.append(f"{label}_pid_mismatch:actual={actual_pid};expected={expected_pid}")
    expected_hwnd = normalize_hwnd(expected.get("targetWindowHandle"))
    actual_hwnd = normalize_hwnd(actual.get("targetWindowHandle"))
    if expected_hwnd and actual_hwnd and expected_hwnd != actual_hwnd:
        issues.append(f"{label}_hwnd_mismatch:actual={actual_hwnd};expected={expected_hwnd}")
    expected_name = str(expected.get("processName") or "").replace(".exe", "").lower()
    actual_name = str(actual.get("processName") or "").replace(".exe", "").lower()
    if expected_name and actual_name and expected_name != actual_name:
        issues.append(f"{label}_process_mismatch:actual={actual_name};expected={expected_name}")
    expected_start = str(expected.get("processStartUtc") or "")
    actual_start = str(actual.get("processStartUtc") or "")
    if expected_start and actual_start and expected_start[:19] != actual_start[:19]:
        issues.append(f"{label}_process_start_mismatch:actual={actual_start};expected={expected_start}")
    return issues


def coordinate_from_mapping(mapping: Mapping[str, Any] | None) -> dict[str, float] | None:
    if not mapping:
        return None
    x = number_or_none(first_present(mapping, "x", "X"))
    y = number_or_none(first_present(mapping, "y", "Y"))
    z = number_or_none(first_present(mapping, "z", "Z"))
    if x is None or y is None or z is None:
        return None
    return {"x": x, "y": y, "z": z}


def extract_coordinate(document: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("coordinate", "referenceCoordinate", "ReferenceCoordinate", "currentCoordinate"):
        coord = coordinate_from_mapping(dict_or_empty(document.get(key)))
        if coord:
            return coord
    coord = coordinate_from_mapping(document)
    return coord or {}


def build_visual_evidence(paths: Sequence[Path], *, repo_root: Path, expected_target: Mapping[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    items: list[dict[str, Any]] = []
    usable_count = 0
    target_issues: list[str] = []
    for index, path in enumerate(paths, start=1):
        data, error = read_optional_json(path)
        item: dict[str, Any] = {
            "path": path_text(path, repo_root),
            "exists": path.exists(),
            "proofRole": "visual-sidecar-only",
            "coordinateProof": False,
            "movementProof": False,
        }
        if error:
            item["status"] = "unreadable" if path.exists() else "missing"
            item["error"] = error
            warnings.append(f"visual_evidence_{item['status']}:{path_text(path, repo_root)}")
            items.append(item)
            continue
        assert data is not None
        quality = dict_or_empty(data.get("quality"))
        safety = dict_or_empty(data.get("safety"))
        artifacts = dict_or_empty(data.get("artifacts"))
        item.update(
            {
                "status": data.get("status") or ("passed" if data.get("ok") is True else "unknown"),
                "runId": data.get("runId"),
                "target": extract_target(data),
                "frame": data.get("frame"),
                "quality": quality,
                "safety": safety,
                "artifacts": artifacts,
            }
        )
        if item["status"] == "passed" and quality.get("usable") is not False:
            usable_count += 1
        if safety:
            for unsafe_key in ("movementSent", "inputSent", "cheatEngineUsed", "x64dbgAttached"):
                if safety.get(unsafe_key) is True:
                    blockers.append(f"visual_evidence_unsafe_{unsafe_key}:index={index}")
        actual_target = item.get("target") if isinstance(item.get("target"), dict) else {}
        target_issues.extend(target_mismatches(expected_target, actual_target, label=f"visual_{index}"))
        items.append(item)

    if items:
        blockers.append("visual-evidence-is-not-coordinate-proof")
        warnings.append("capture-present-but-no-coordinate-proof-unless-api-memory-static-route-also-passes")
    status = "usable-sidecar" if usable_count else "absent" if not items else "present-not-usable"
    if target_issues:
        blockers.extend(target_issues)
        status = "target-mismatch"
    return (
        {
            "status": status,
            "proofRole": "sidecar_only_not_coordinate_or_movement_truth",
            "coordinateProof": False,
            "movementProof": False,
            "usableCount": usable_count,
            "items": items,
        },
        blockers,
        warnings,
    )


def build_api_reference(path: Path | None, *, repo_root: Path, expected_target: Mapping[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    data, error = read_optional_json(path)
    if error:
        return (
            {
                "status": "missing" if path and not path.exists() else "absent",
                "path": path_text(path, repo_root),
                "coordinate": {},
                "fresh": False,
                "error": error,
            },
            ["api-reference-missing-or-unreadable"],
            [],
        )
    if data is None:
        return ({"status": "absent", "path": None, "coordinate": {}, "fresh": False}, ["api-reference-missing"], [])
    coordinate = extract_coordinate(data)
    target = extract_target(data)
    blockers = target_mismatches(expected_target, target, label="api_reference")
    if not coordinate:
        blockers.append("api-reference-coordinate-missing")
    fresh = bool(coordinate) and not blockers
    return (
        {
            "status": "usable" if fresh else "blocked",
            "path": path_text(path, repo_root),
            "coordinate": coordinate,
            "capturedAtUtc": first_present(data, "captured_at_utc", "capturedAtUtc", "GeneratedAtUtc"),
            "tolerance": number_or_none(first_present(data, "tolerance", "Tolerance")) or DEFAULT_TOLERANCE,
            "target": target,
            "fresh": fresh,
            "savedVariablesUse": first_present(data, "savedVariablesUse", "SavedVariablesUse"),
            "noCheatEngine": first_present(data, "noCheatEngine", "NoCheatEngine"),
            "movementSent": first_present(data, "movementSent", "MovementSent"),
        },
        blockers,
        [],
    )


def build_memory_readback(path: Path | None, *, repo_root: Path, expected_target: Mapping[str, Any], tolerance: float) -> tuple[dict[str, Any], list[str], list[str]]:
    data, error = read_optional_json(path)
    if error:
        return (
            {"status": "missing" if path and not path.exists() else "absent", "path": path_text(path, repo_root), "error": error},
            ["memory-readback-missing-or-unreadable"],
            [],
        )
    if data is None:
        return ({"status": "absent", "path": None}, ["memory-readback-missing"], [])
    mode = str(first_present(data, "mode", "Mode") or "")
    if mode == "riftreader-current-pid-coordinate-family-scan":
        target = extract_target(data)
        blockers = target_mismatches(expected_target, target, label="memory_reacquisition")
        scan = dict_or_empty(data.get("scan"))
        artifacts = dict_or_empty(data.get("artifacts"))
        hit_count = int_or_none(scan.get("hitCount")) or 0
        if hit_count <= 0:
            blockers.append("memory-candidate-reacquisition-no-current-hits")
        return (
            {
                "status": "reacquisition-no-current-hits" if hit_count <= 0 else "reacquisition-candidates-found",
                "path": path_text(path, repo_root),
                "target": target,
                "referenceMatchCount": hit_count,
                "decodedCandidateCount": hit_count,
                "stableDecodedCandidateCount": None,
                "selectedCandidate": {},
                "apiMemoryMatch": hit_count > 0 and not blockers,
                "staleAgainstApiNow": hit_count <= 0,
                "movementAllowed": False,
                "reacquisition": {
                    "mode": mode,
                    "hitCount": hit_count,
                    "bytesScanned": scan.get("bytesScanned"),
                    "durationSeconds": scan.get("durationSeconds"),
                    "candidateJson": artifacts.get("candidateJson"),
                    "summaryJson": artifacts.get("summaryJson"),
                    "blockers": list_or_empty(data.get("blockers")),
                    "warnings": list_or_empty(data.get("warnings")),
                },
            },
            blockers,
            list_or_empty(data.get("warnings")),
        )
    blockers = target_mismatches(expected_target, extract_target(data), label="memory_readback")
    reference_match_count = int_or_none(first_present(data, "ReferenceMatchCount", "referenceMatchCount")) or 0
    best_matches = list_or_empty(first_present(data, "BestReferenceMatches", "bestReferenceMatches"))
    candidate_readbacks = list_or_empty(first_present(data, "CandidateReadbacks", "candidateReadbacks"))
    selected: dict[str, Any] = {}
    if best_matches:
        selected = dict_or_empty(best_matches[0])
    elif candidate_readbacks:
        selected = dict_or_empty(candidate_readbacks[0])
    reference_delta = number_or_none(first_present(selected, "ReferenceMaxAbsDelta", "referenceMaxAbsDelta"))
    if reference_delta is None:
        reference_delta = number_or_none(first_present(data, "referenceMaxAbsDelta", "ReferenceMaxAbsDelta"))
    reference_matches_readback = bool_or_false(first_present(selected, "ReferenceMatchesReadback", "referenceMatchesReadback"))
    stable = bool_or_false(first_present(selected, "StableAcrossReadbackSamples", "stableAcrossReadbackSamples"))
    source_preview_matches = bool_or_false(first_present(selected, "SourcePreviewMatchesReadback", "sourcePreviewMatchesReadback"))
    api_memory_match = reference_match_count > 0 or reference_matches_readback or (reference_delta is not None and reference_delta <= tolerance)
    stale_against_api = not api_memory_match and (reference_delta is not None or reference_match_count == 0)
    if first_present(data, "MovementSent", "movementSent") is True:
        blockers.append("memory-readback-sent-movement")
    if first_present(data, "NoCheatEngine", "noCheatEngine") is False:
        blockers.append("memory-readback-used-cheat-engine")
    status = "api-memory-match" if api_memory_match and not blockers else "candidate-only-stale-against-api-now" if stale_against_api else "candidate-only"
    if stale_against_api:
        blockers.append("memory-candidate-stale-against-api-now")
    return (
        {
            "status": status,
            "path": path_text(path, repo_root),
            "target": extract_target(data),
            "referenceMatchCount": reference_match_count,
            "decodedCandidateCount": int_or_none(first_present(data, "DecodedCandidateCount", "decodedCandidateCount")),
            "stableDecodedCandidateCount": int_or_none(first_present(data, "StableDecodedCandidateCount", "stableDecodedCandidateCount")),
            "selectedCandidate": {
                "candidateId": first_present(selected, "CandidateId", "candidateId"),
                "addressHex": first_present(selected, "CandidateAddressHex", "candidateAddressHex", "AddressHex", "addressHex"),
                "referenceMaxAbsDelta": reference_delta,
                "referenceMatchesReadback": reference_matches_readback,
                "stableAcrossReadbackSamples": stable,
                "sourcePreviewMatchesReadback": source_preview_matches,
            },
            "apiMemoryMatch": api_memory_match,
            "staleAgainstApiNow": stale_against_api,
            "movementAllowed": False,
        },
        blockers,
        [],
    )


def build_static_roots(paths: Sequence[Path], *, repo_root: Path, expected_target: Mapping[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    items: list[dict[str, Any]] = []
    candidate_count = 0
    proven_count = 0
    for index, path in enumerate(paths, start=1):
        data, error = read_optional_json(path)
        item: dict[str, Any] = {"path": path_text(path, repo_root), "exists": path.exists()}
        if error:
            item["status"] = "unreadable" if path.exists() else "missing"
            item["error"] = error
            warnings.append(f"static_root_{item['status']}:{path_text(path, repo_root)}")
            items.append(item)
            continue
        assert data is not None
        target = extract_target(data)
        module_rva = first_present(data, "topModuleRva", "TopModuleRva", "moduleRva", "ModuleRva", "selectedModuleRva")
        module_hits = int_or_none(first_present(data, "moduleRvaHintCount", "ModuleRvaHintCount", "modulePointerHitCount", "ModulePointerHitCount"))
        promotion_eligible = bool_or_false(first_present(data, "promotionEligible", "PromotionEligible"))
        restart_validated = bool_or_false(first_present(data, "restartValidated", "RestartValidated"))
        static_proven = bool_or_false(first_present(data, "staticRootProven", "StaticRootProven")) or (promotion_eligible and restart_validated)
        if module_rva or (module_hits is not None and module_hits > 0):
            candidate_count += 1
        if static_proven:
            proven_count += 1
        issues = target_mismatches(expected_target, target, label=f"static_root_{index}") if target.get("processId") else []
        blockers.extend(issues)
        item.update(
            {
                "status": "static-root-proven" if static_proven else "static-root-candidate" if module_rva or module_hits else data.get("status", "candidate-only"),
                "target": target,
                "moduleRva": module_rva,
                "moduleRvaHintCount": module_hits,
                "promotionEligible": promotion_eligible,
                "restartValidated": restart_validated,
                "staticRootProven": static_proven,
                "movementProof": False,
            }
        )
        items.append(item)
    if candidate_count and not proven_count:
        blockers.append("static-root-candidate-not-restart-validated")
    status = "static-root-proven" if proven_count else "static-root-candidate" if candidate_count else "absent"
    return ({"status": status, "candidateCount": candidate_count, "provenCount": proven_count, "items": items}, blockers, warnings)


def build_candidate_routing(
    *,
    center_files: Sequence[Path],
    candidate_comparisons: Sequence[Path],
    repo_root: Path,
) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    center_items: list[dict[str, Any]] = []
    comparison_items: list[dict[str, Any]] = []
    for path in center_files:
        data, error = read_optional_json(path)
        item: dict[str, Any] = {"path": path_text(path, repo_root), "exists": data is not None}
        if error:
            warnings.append(error)
            item["status"] = "unreadable"
            center_items.append(item)
            continue
        centers = list_or_empty(data.get("centers") if data else None)
        item.update(
            {
                "status": data.get("status") or "available",
                "centerCount": len(centers),
                "topCenters": [
                    {
                        "rank": dict_or_empty(center).get("rank"),
                        "label": dict_or_empty(center).get("label"),
                        "address": dict_or_empty(center).get("address"),
                        "maxAbsDelta": dict_or_empty(center).get("maxAbsDelta"),
                    }
                    for center in centers[:5]
                    if isinstance(center, dict)
                ],
            }
        )
        center_items.append(item)
    for path in candidate_comparisons:
        data, error = read_optional_json(path)
        item = {"path": path_text(path, repo_root), "exists": data is not None}
        if error:
            warnings.append(error)
            item["status"] = "unreadable"
            comparison_items.append(item)
            continue
        files = [dict_or_empty(value) for value in list_or_empty(data.get("candidateFiles"))]
        baseline_matches = sum(int_or_none(file_result.get("matchCount")) or 0 for file_result in files)
        displaced_matches = sum(int_or_none(file_result.get("displacedMatchCount")) or 0 for file_result in files)
        both_matches = sum(int_or_none(file_result.get("bothReferenceMatchCount")) or 0 for file_result in files)
        if both_matches <= 0:
            warnings.append("candidate-comparison-has-no-both-reference-match")
        item.update(
            {
                "status": data.get("status"),
                "baselineMatchCount": baseline_matches,
                "displacedMatchCount": displaced_matches,
                "bothReferenceMatchCount": both_matches,
                "warningCount": len(list_or_empty(data.get("warnings"))),
                "blockerCount": len(list_or_empty(data.get("blockers"))),
            }
        )
        comparison_items.append(item)
    center_count = sum(int_or_none(item.get("centerCount")) or 0 for item in center_items)
    both_reference_count = sum(int_or_none(item.get("bothReferenceMatchCount")) or 0 for item in comparison_items)
    status = "not-provided"
    if center_items or comparison_items:
        status = "candidate-routing-ready" if center_count > 0 else "candidate-routing-no-centers"
    return (
        {
            "status": status,
            "proofRole": "candidate-routing-only-not-coordinate-truth",
            "centerFileCount": len(center_items),
            "centerCount": center_count,
            "candidateComparisonCount": len(comparison_items),
            "bothReferenceMatchCount": both_reference_count,
            "movementProof": False,
            "coordinateProof": False,
            "centerFiles": center_items,
            "candidateComparisons": comparison_items,
        },
        blockers,
        list(dict.fromkeys(warnings)),
    )


def build_displaced_readiness(
    *,
    paths: Sequence[Path],
    repo_root: Path,
    expected_target: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    items: list[dict[str, Any]] = []
    passed_count = 0
    blocked_count = 0
    failed_count = 0
    for index, path in enumerate(paths, start=1):
        data, error = read_optional_json(path)
        item: dict[str, Any] = {
            "path": path_text(path, repo_root),
            "exists": path.exists(),
            "proofRole": "displaced-reference-readiness-gate-not-coordinate-proof",
            "coordinateProof": False,
            "movementProof": False,
        }
        if error:
            warnings.append(error)
            item["status"] = "unreadable" if path.exists() else "missing"
            items.append(item)
            continue

        assert data is not None
        status = str(data.get("status") or "unknown")
        artifacts = dict_or_empty(data.get("artifacts"))
        safety = dict_or_empty(data.get("safety"))
        baseline_reference = dict_or_empty(data.get("baselineReference"))
        displaced_reference = dict_or_empty(data.get("displacedReference"))
        delta = dict_or_empty(data.get("delta"))
        baseline_target = extract_target(baseline_reference)
        displaced_target = extract_target(displaced_reference)
        target_issues: list[str] = []
        target_issues.extend(target_mismatches(expected_target, baseline_target, label=f"displaced_readiness_{index}_baseline"))
        target_issues.extend(target_mismatches(expected_target, displaced_target, label=f"displaced_readiness_{index}_displaced"))
        if target_issues:
            warnings.extend(target_issues)

        for unsafe_key in (
            "movementSent",
            "inputSent",
            "reloaduiSent",
            "screenshotKeySent",
            "x64dbgAttached",
            "processAttachOrMemoryReadStarted",
            "providerWrite",
        ):
            if safety.get(unsafe_key) is True:
                blockers.append(f"displaced-readiness-unsafe-{unsafe_key}:index={index}")
        if safety.get("noCheatEngine") is False:
            blockers.append(f"displaced-readiness-used-cheat-engine:index={index}")

        if status == "passed":
            passed_count += 1
        elif status == "blocked":
            blocked_count += 1
            warnings.append("displaced-readiness-not-passed:blocked")
        elif status == "failed":
            failed_count += 1
            warnings.append("displaced-readiness-not-passed:failed")
        elif status != "unknown":
            warnings.append(f"displaced-readiness-not-passed:{status}")

        item.update(
            {
                "status": status,
                "summaryJson": artifact_path_text(artifacts.get("summaryJson"), repo_root) or path_text(path, repo_root),
                "summaryMarkdown": artifact_path_text(artifacts.get("summaryMarkdown"), repo_root),
                "summaryHtml": artifact_path_text(artifacts.get("summaryHtml"), repo_root),
                "baselineReferencePath": baseline_reference.get("path"),
                "displacedReferencePath": displaced_reference.get("path"),
                "baselineTarget": baseline_target,
                "displacedTarget": displaced_target,
                "ageDeltaSeconds": number_or_none(data.get("ageDeltaSeconds")),
                "planarDistance": number_or_none(delta.get("planarDistance")),
                "maxAbsDelta": number_or_none(delta.get("maxAbsDelta")),
                "blockers": list_or_empty(data.get("blockers")),
                "warnings": list_or_empty(data.get("warnings")),
                "safety": safety,
            }
        )
        items.append(item)

    if not items:
        status = "not-provided"
    elif failed_count:
        status = "failed"
    elif blocked_count:
        status = "blocked"
    elif passed_count == len(items):
        status = "passed"
    elif passed_count:
        status = "mixed"
    else:
        status = "unknown"

    return (
        {
            "status": status,
            "proofRole": "displaced-reference-readiness-gate-not-coordinate-proof",
            "summaryCount": len(items),
            "passedCount": passed_count,
            "blockedCount": blocked_count,
            "failedCount": failed_count,
            "movementProof": False,
            "coordinateProof": False,
            "items": items,
        },
        list(dict.fromkeys(blockers)),
        list(dict.fromkeys(warnings)),
    )


def route_status(
    *,
    visual: Mapping[str, Any],
    api_reference: Mapping[str, Any],
    memory_readback: Mapping[str, Any],
    static_roots: Mapping[str, Any],
    blockers: Sequence[str],
) -> str:
    hard_target_blocker = any("_mismatch" in blocker or blocker.endswith("sent-movement") for blocker in blockers)
    if hard_target_blocker:
        return "blocked"
    if memory_readback.get("status") == "api-memory-match" and static_roots.get("status") == "static-root-proven":
        return "promotion-eligible-static-root"
    if static_roots.get("status") == "static-root-candidate":
        return "static-root-candidate"
    if memory_readback.get("status") == "api-memory-match":
        return "api-memory-match"
    if memory_readback.get("status") == "reacquisition-candidates-found" and memory_readback.get("apiMemoryMatch") is True:
        return "reacquisition-candidates-found"
    if memory_readback.get("status") in {
        "candidate-only-stale-against-api-now",
        "reacquisition-no-current-hits",
    }:
        return str(memory_readback.get("status"))
    if visual.get("items"):
        return "visual-only"
    return "blocked"


def build_recommended_actions(status: str) -> list[dict[str, str]]:
    actions = [
        {
            "action": "Treat visual capture as sidecar evidence only.",
            "why": "A screenshot/crop/diff cannot promote coordinate or movement truth without API and memory agreement.",
        },
        {
            "action": "Refresh API-now RRAPICOORD before any candidate promotion.",
            "why": "The current route must be grounded in live runtime coordinate truth, not stale SavedVariables or old heap copies.",
        },
        {
            "action": "Run same-target memory readback against explicit candidate files.",
            "why": "Readback is the first proof surface that can upgrade from visual-only to API-memory-match.",
        },
    ]
    if status == "candidate-only-stale-against-api-now":
        actions.insert(
            0,
            {
                "action": "Reacquire current-process memory candidates before static-root work.",
                "why": "The selected heap copy is stable but stale against API-now, so root scans from it risk chasing an old coordinate copy.",
            },
        )
    elif status == "reacquisition-candidates-found":
        actions.insert(
            0,
            {
                "action": "Run explicit read-only candidate readback and multi-pose validation from the reacquired current-memory candidates.",
                "why": "The scan found current API-matching memory candidates, but movement still needs a stronger proof chain and explicit approval.",
            },
        )
    elif status == "reacquisition-no-current-hits":
        actions.insert(
            0,
            {
                "action": "Broaden or retarget current-process coordinate reacquisition before static-root work.",
                "why": "The read-only scan did not find any current XYZ triplets near API-now, so there is no current candidate to promote.",
            },
        )
    elif status == "api-memory-match":
        actions.insert(
            0,
            {
                "action": "Use the matching current-process candidate as the seed for static owner/module-RVA routing.",
                "why": "API-now and memory-now agree, but movement still needs a canonical proof/static chain and ProofOnly.",
            },
        )
    elif status == "static-root-candidate":
        actions.insert(
            0,
            {
                "action": "Validate static-root candidates across restart/process epochs before promotion.",
                "why": "Module/RVA hints are useful leads but are not static coordinate truth until restart validation passes.",
            },
        )
    return actions


def markdown_summary(route: Mapping[str, Any]) -> str:
    target = dict_or_empty(route.get("target"))
    decision = dict_or_empty(route.get("decision"))
    visual = dict_or_empty(route.get("visualEvidence"))
    api = dict_or_empty(route.get("apiReference"))
    memory = dict_or_empty(route.get("memoryReadback"))
    static_roots = dict_or_empty(route.get("staticRootCandidates"))
    candidate_routing = dict_or_empty(route.get("candidateRouting"))
    displaced_readiness = dict_or_empty(route.get("displacedReadiness"))
    lines = [
        "# Coordinate proof route",
        "",
        "| Fact | Value |",
        "|---|---|",
        f"| Status | `{route.get('status')}` |",
        f"| Target | `{target.get('processName')}` PID `{target.get('processId')}`, HWND `{target.get('targetWindowHandle')}` |",
        f"| Visual evidence | `{visual.get('status')}` / role `{visual.get('proofRole')}` |",
        f"| API reference | `{api.get('status')}` |",
        f"| Memory readback | `{memory.get('status')}` |",
        f"| Static root | `{static_roots.get('status')}` |",
        f"| Candidate routing | `{candidate_routing.get('status')}` / centers `{candidate_routing.get('centerCount')}` |",
        f"| Displaced readiness | `{displaced_readiness.get('status')}` / summaries `{displaced_readiness.get('summaryCount')}` |",
        f"| Read-only proof allowed | `{str(decision.get('readOnlyProofAllowed')).lower()}` |",
        f"| Movement allowed | `{str(decision.get('movementAllowed')).lower()}` |",
        "",
    ]
    if route.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in route.get("blockers", []))
        lines.append("")
    if route.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in route.get("warnings", []))
        lines.append("")
    if candidate_routing:
        lines.extend(["## Candidate routing", "", "| Type | Path | Status | Count |", "|---|---|---|---:|"])
        for item in list_or_empty(candidate_routing.get("centerFiles")):
            item_map = dict_or_empty(item)
            lines.append(f"| Center file | `{item_map.get('path')}` | `{item_map.get('status')}` | `{item_map.get('centerCount')}` |")
        for item in list_or_empty(candidate_routing.get("candidateComparisons")):
            item_map = dict_or_empty(item)
            lines.append(
                f"| Candidate comparison | `{item_map.get('path')}` | `{item_map.get('status')}` | `{item_map.get('bothReferenceMatchCount')}` |"
            )
        lines.append("")
    if displaced_readiness:
        lines.extend(["## Displaced readiness", "", "| Path | Status | Age delta seconds | Planar distance |", "|---|---|---:|---:|"])
        for item in list_or_empty(displaced_readiness.get("items")):
            item_map = dict_or_empty(item)
            lines.append(
                f"| `{item_map.get('path')}` | `{item_map.get('status')}` | `{item_map.get('ageDeltaSeconds')}` | `{item_map.get('planarDistance')}` |"
            )
        lines.append("")
    actions = list_or_empty(route.get("recommendedActions"))
    if actions:
        lines.extend(["## Recommended actions", "", "| # | Action | Why |", "|---:|---|---|"])
        for index, action in enumerate(actions, start=1):
            action_map = dict_or_empty(action)
            lines.append(f"| {index} | {action_map.get('action')} | {action_map.get('why')} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def html_summary(route: Mapping[str, Any]) -> str:
    target = dict_or_empty(route.get("target"))
    decision = dict_or_empty(route.get("decision"))
    visual = dict_or_empty(route.get("visualEvidence"))
    api = dict_or_empty(route.get("apiReference"))
    memory = dict_or_empty(route.get("memoryReadback"))
    static_roots = dict_or_empty(route.get("staticRootCandidates"))
    candidate_routing = dict_or_empty(route.get("candidateRouting"))
    displaced_readiness = dict_or_empty(route.get("displacedReadiness"))
    blockers = [str(item) for item in list_or_empty(route.get("blockers"))]
    warnings = [str(item) for item in list_or_empty(route.get("warnings"))]
    actions = [dict_or_empty(item) for item in list_or_empty(route.get("recommendedActions"))]
    status = str(route.get("status") or "unknown")
    status_class = "good" if decision.get("readOnlyProofAllowed") else "blocked"
    rows = [
        ("Status", status),
        ("Target", f"{target.get('processName')} PID {target.get('processId')} HWND {target.get('targetWindowHandle')}"),
        ("Visual evidence", f"{visual.get('status')} / {visual.get('proofRole')}"),
        ("API reference", api.get("status")),
        ("Memory readback", memory.get("status")),
        ("Static root", static_roots.get("status")),
        ("Candidate routing", f"{candidate_routing.get('status')} / centers {candidate_routing.get('centerCount')}"),
        ("Displaced readiness", f"{displaced_readiness.get('status')} / summaries {displaced_readiness.get('summaryCount')}"),
        ("Read-only proof allowed", str(decision.get("readOnlyProofAllowed")).lower()),
        ("Movement allowed", str(decision.get("movementAllowed")).lower()),
    ]
    body_rows = "\n".join(
        f"<tr><th>{html_escape(name)}</th><td>{html_escape(value)}</td></tr>" for name, value in rows
    )
    blocker_items = "\n".join(f"<li>{html_escape(item)}</li>" for item in blockers) or "<li>None</li>"
    warning_items = "\n".join(f"<li>{html_escape(item)}</li>" for item in warnings) or "<li>None</li>"
    action_rows = "\n".join(
        "<tr>"
        f"<td>{index}</td>"
        f"<td>{html_escape(action.get('action'))}</td>"
        f"<td>{html_escape(action.get('why'))}</td>"
        "</tr>"
        for index, action in enumerate(actions, start=1)
    )
    readiness_items = [dict_or_empty(item) for item in list_or_empty(displaced_readiness.get("items"))]
    readiness_rows = "\n".join(
        "<tr>"
        f"<td>{html_escape(item.get('path'))}</td>"
        f"<td>{html_escape(item.get('status'))}</td>"
        f"<td>{html_escape(item.get('ageDeltaSeconds'))}</td>"
        f"<td>{html_escape(item.get('planarDistance'))}</td>"
        "</tr>"
        for item in readiness_items
    )
    readiness_table = (
        "<table><tr><th>Path</th><th>Status</th><th>Age delta seconds</th><th>Planar distance</th></tr>"
        f"{readiness_rows}</table>"
        if readiness_rows
        else "<p>No displaced-readiness summary was provided.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coordinate proof route - {html_escape(status)}</title>
<style>
body {{ margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: #08111f; color: #e5eefb; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 32px 22px 48px; }}
.hero {{ border: 1px solid #263a57; border-radius: 22px; padding: 24px; background: linear-gradient(135deg, rgba(56,189,248,.15), rgba(167,139,250,.10)); }}
h1 {{ margin: 0 0 8px; font-size: 34px; }}
h2 {{ margin-top: 28px; }}
.badge {{ display: inline-block; padding: 7px 12px; border-radius: 999px; font-weight: 800; }}
.badge.blocked {{ background: #7f1d1d; color: #fecaca; }}
.badge.good {{ background: #14532d; color: #bbf7d0; }}
table {{ width: 100%; border-collapse: collapse; background: #0f1b2e; border: 1px solid #263a57; border-radius: 14px; overflow: hidden; }}
th, td {{ padding: 11px 13px; border-bottom: 1px solid #263a57; text-align: left; vertical-align: top; }}
th {{ color: #bae6fd; width: 260px; }}
tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
li {{ margin: 6px 0; }}
code {{ background: #020817; border: 1px solid #263a57; padding: 2px 6px; border-radius: 6px; color: #bfdbfe; }}
.note {{ color: #fed7aa; border: 1px solid rgba(249,115,22,.4); background: rgba(249,115,22,.10); padding: 12px 14px; border-radius: 14px; }}
</style>
</head>
<body>
<main>
<section class="hero">
<h1>Coordinate proof route</h1>
<p><span class="badge {status_class}">{html_escape(status)}</span></p>
<p class="note">Visual capture is sidecar evidence only. This report never grants movement permission.</p>
</section>
<h2>Route facts</h2>
<table>{body_rows}</table>
<h2>Displaced readiness gate</h2>
{readiness_table}
<h2>Blockers</h2>
<ul>{blocker_items}</ul>
<h2>Warnings</h2>
<ul>{warning_items}</ul>
<h2>Recommended actions</h2>
<table><tr><th>#</th><th>Action</th><th>Why</th></tr>{action_rows}</table>
</main>
</body>
</html>
"""


def latest_pointer_payload(route: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = dict_or_empty(route.get("artifacts"))
    decision = dict_or_empty(route.get("decision"))
    return {
        "schemaVersion": 1,
        "kind": "latest-coordinate-proof-route-pointer",
        "updatedAtUtc": utc_iso(),
        "status": route.get("status"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "summaryHtml": artifacts.get("summaryHtml"),
        "readOnlyProofAllowed": decision.get("readOnlyProofAllowed") is True,
        "movementAllowed": False,
        "blockers": list_or_empty(route.get("blockers")),
        "warnings": list_or_empty(route.get("warnings")),
        "target": route.get("target"),
        "safety": route.get("safety"),
    }


def build_coordinate_proof_route(
    *,
    repo_root: Path,
    output_root: Path | None = None,
    process_id: int | None = None,
    target_window_handle: str | None = None,
    process_name: str | None = "rift_x64",
    process_start_utc: str | None = None,
    current_truth_path: Path | None = None,
    capture_manifests: Sequence[Path] = (),
    api_reference_path: Path | None = None,
    memory_readback_path: Path | None = None,
    static_root_summaries: Sequence[Path] = (),
    center_files: Sequence[Path] = (),
    candidate_comparisons: Sequence[Path] = (),
    displaced_readiness_summaries: Sequence[Path] = (),
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    current_truth_data: dict[str, Any] | None = None
    current_truth_error: str | None = None
    if current_truth_path:
        current_truth_data, current_truth_error = read_optional_json(current_truth_path)
    target = requested_target(
        process_id=process_id,
        target_window_handle=target_window_handle,
        process_name=process_name,
        process_start_utc=process_start_utc,
        current_truth=current_truth_data,
    )
    blockers: list[str] = []
    warnings: list[str] = []
    if current_truth_error:
        warnings.append(current_truth_error)
    if target.get("processId") is None:
        blockers.append("target-process-id-missing")
    if not target.get("targetWindowHandle"):
        blockers.append("target-window-handle-missing")

    visual, visual_blockers, visual_warnings = build_visual_evidence(capture_manifests, repo_root=repo_root, expected_target=target)
    api_reference, api_blockers, api_warnings = build_api_reference(api_reference_path, repo_root=repo_root, expected_target=target)
    tolerance = number_or_none(api_reference.get("tolerance")) or DEFAULT_TOLERANCE
    memory_readback, memory_blockers, memory_warnings = build_memory_readback(
        memory_readback_path,
        repo_root=repo_root,
        expected_target=target,
        tolerance=tolerance,
    )
    static_roots, static_blockers, static_warnings = build_static_roots(static_root_summaries, repo_root=repo_root, expected_target=target)
    candidate_routing, routing_blockers, routing_warnings = build_candidate_routing(
        center_files=center_files,
        candidate_comparisons=candidate_comparisons,
        repo_root=repo_root,
    )
    displaced_readiness, displaced_blockers, displaced_warnings = build_displaced_readiness(
        paths=displaced_readiness_summaries,
        repo_root=repo_root,
        expected_target=target,
    )
    blockers.extend(
        visual_blockers
        + api_blockers
        + memory_blockers
        + static_blockers
        + routing_blockers
        + displaced_blockers
    )
    warnings.extend(
        visual_warnings
        + api_warnings
        + memory_warnings
        + static_warnings
        + routing_warnings
        + displaced_warnings
    )
    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    status = route_status(visual=visual, api_reference=api_reference, memory_readback=memory_readback, static_roots=static_roots, blockers=blockers)
    read_only_proof_allowed = status in {
        "api-memory-match",
        "reacquisition-candidates-found",
        "static-root-candidate",
        "promotion-eligible-static-root",
    }
    movement_allowed = False
    artifacts = {
        "outputRoot": path_text(output_root, repo_root) if output_root else None,
        "summaryJson": None,
        "summaryMarkdown": None,
        "summaryHtml": None,
        "latestPointer": None,
        "currentTruth": path_text(current_truth_path, repo_root),
        "captureManifests": [path_text(path, repo_root) for path in capture_manifests],
        "apiReference": path_text(api_reference_path, repo_root),
        "memoryReadback": path_text(memory_readback_path, repo_root),
        "staticRootSummaries": [path_text(path, repo_root) for path in static_root_summaries],
        "centerFiles": [path_text(path, repo_root) for path in center_files],
        "candidateComparisons": [path_text(path, repo_root) for path in candidate_comparisons],
        "displacedReadinessSummaries": [path_text(path, repo_root) for path in displaced_readiness_summaries],
    }
    recommended_actions = build_recommended_actions(status)
    candidate_comparison_needs_fresh_displaced = (
        candidate_routing.get("bothReferenceMatchCount") == 0 and bool(candidate_routing.get("candidateComparisonCount"))
    )
    if (
        displaced_readiness.get("summaryCount")
        and displaced_readiness.get("status") != "passed"
        and not candidate_comparison_needs_fresh_displaced
    ):
        recommended_actions.insert(
            0,
            {
                "action": "Refresh the displaced-pose reference before any promotion attempt.",
                "why": "The displaced-readiness gate is not passed, so two-pose evidence is unavailable even if same-pose API/readback agrees.",
            },
        )
    if candidate_routing.get("centerCount"):
        recommended_actions.insert(
            0,
            {
                "action": "Use routed center files for bounded current-memory scans before repeating broad sweeps.",
                "why": "Center files preserve the best candidate neighborhoods without treating stale/candidate evidence as proof.",
            },
        )
    if candidate_comparison_needs_fresh_displaced:
        recommended_actions.insert(
            0,
            {
                "action": "Capture a fresh displaced-pose reference before promotion.",
                "why": "Candidate comparisons still have no both-reference match, so they cannot prove a pose-tracking coordinate lane.",
            },
        )
    route: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "coordinate-proof-route",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "target": target,
        "decision": {
            "readOnlyProofAllowed": read_only_proof_allowed,
            "movementAllowed": movement_allowed,
            "movementBlockedReason": "coordinate-proof-route never grants movement; movement also requires proof gate pass and explicit approval.",
            "visualEvidenceCanPromoteTruth": False,
        },
        "visualEvidence": visual,
        "apiReference": api_reference,
        "memoryReadback": memory_readback,
        "staticRootCandidates": static_roots,
        "candidateRouting": candidate_routing,
        "displacedReadiness": displaced_readiness,
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": artifacts,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "providerWrite": False,
            "githubConnectorWrites": False,
            "savedVariablesUsedAsLiveTruth": False,
        },
        "recommendedActions": recommended_actions,
    }
    return route


def write_route(route: dict[str, Any], output_root: Path, *, repo_root: Path) -> dict[str, Any]:
    summary_json = output_root / "coordinate-proof-route.json"
    summary_md = output_root / "coordinate-proof-route.md"
    summary_html = output_root / "coordinate-proof-route.html"
    latest_pointer = repo_root / "scripts" / "captures" / "latest-coordinate-proof-route.json"
    route["artifacts"]["outputRoot"] = path_text(output_root, repo_root)
    route["artifacts"]["summaryJson"] = path_text(summary_json, repo_root)
    route["artifacts"]["summaryMarkdown"] = path_text(summary_md, repo_root)
    route["artifacts"]["summaryHtml"] = path_text(summary_html, repo_root)
    route["artifacts"]["latestPointer"] = path_text(latest_pointer, repo_root)
    write_json(summary_json, route)
    write_text_atomic(summary_md, markdown_summary(route))
    write_text_atomic(summary_html, html_summary(route))
    write_json(latest_pointer, latest_pointer_payload(route))
    return route


def upsert_markdown_table_rows(text: str, heading_prefix: str, rows: Mapping[str, str]) -> str:
    lines = text.splitlines()
    heading_index = next((index for index, line in enumerate(lines) if line.startswith(heading_prefix)), None)
    if heading_index is None:
        appended = [
            "",
            heading_prefix,
            "",
            "| Field | Value |",
            "|---|---|",
            *[f"| {label} | `{value}` |" for label, value in rows.items()],
        ]
        return "\n".join([*lines, *appended]).rstrip() + "\n"
    table_start = None
    for index in range(heading_index + 1, len(lines)):
        if lines[index].strip() == "| Field | Value |":
            table_start = index
            break
        if index > heading_index and lines[index].startswith("## "):
            break
    if table_start is None:
        lines[heading_index + 1:heading_index + 1] = [
            "",
            "| Field | Value |",
            "|---|---|",
            *[f"| {label} | `{value}` |" for label, value in rows.items()],
        ]
        return "\n".join(lines).rstrip() + "\n"
    table_end = table_start + 2
    while table_end < len(lines) and lines[table_end].startswith("|"):
        table_end += 1
    updated: set[str] = set()
    for index in range(table_start + 2, table_end):
        parts = [part.strip() for part in lines[index].strip().strip("|").split("|")]
        if len(parts) < 2:
            continue
        label = parts[0]
        if label in rows:
            lines[index] = f"| {label} | `{rows[label]}` |"
            updated.add(label)
    lines[table_end:table_end] = [f"| {label} | `{value}` |" for label, value in rows.items() if label not in updated]
    return "\n".join(lines).rstrip() + "\n"


def update_current_truth(route: Mapping[str, Any], repo_root: Path) -> None:
    truth_path = repo_root / "docs" / "recovery" / "current-truth.json"
    if not truth_path.exists():
        return
    document = read_json_file(truth_path)
    if not isinstance(document, dict):
        return
    routing = document.setdefault("visualEvidenceRouting", {})
    artifacts = dict_or_empty(route.get("artifacts"))
    if artifacts.get("summaryJson"):
        routing["latestProofRoute"] = artifacts["summaryJson"]
        routing["latestProofRouteWithCandidateRouting"] = artifacts["summaryJson"]
    if artifacts.get("summaryHtml"):
        routing["latestProofRouteHtml"] = artifacts["summaryHtml"]
    if artifacts.get("latestPointer"):
        routing["latestProofRoutePointer"] = artifacts["latestPointer"]
    routing["latestRouteStatus"] = str(route.get("status"))
    candidate_routing = dict_or_empty(route.get("candidateRouting"))
    if candidate_routing:
        routing["latestCandidateRoutingStatus"] = str(candidate_routing.get("status"))
        routing["latestCandidateRoutingCenterCount"] = int_or_none(candidate_routing.get("centerCount")) or 0
    displaced_readiness = dict_or_empty(route.get("displacedReadiness"))
    if displaced_readiness.get("summaryCount"):
        routing["latestDisplacedReadinessStatus"] = str(displaced_readiness.get("status"))
        routing["latestDisplacedReadinessSummaryCount"] = int_or_none(displaced_readiness.get("summaryCount")) or 0
        readiness_items = [dict_or_empty(item) for item in list_or_empty(displaced_readiness.get("items"))]
        latest_readiness = next((item for item in readiness_items if item.get("summaryJson")), None)
        if latest_readiness:
            routing["latestDisplacedReadinessSummary"] = latest_readiness.get("summaryJson")
            if latest_readiness.get("summaryHtml"):
                routing["latestDisplacedReadinessHtml"] = latest_readiness.get("summaryHtml")
    write_json(truth_path, document)

    markdown_path = repo_root / "docs" / "recovery" / "current-truth.md"
    if not markdown_path.exists():
        return
    rows = {
        "Latest route": str(routing.get("latestProofRoute") or ""),
        "Latest route HTML": str(routing.get("latestProofRouteHtml") or ""),
        "Latest route pointer": str(routing.get("latestProofRoutePointer") or ""),
        "Latest route status": str(routing.get("latestRouteStatus") or ""),
        "Latest route with candidate routing": str(routing.get("latestProofRouteWithCandidateRouting") or ""),
        "Latest candidate routing status": str(routing.get("latestCandidateRoutingStatus") or ""),
        "Latest candidate routing center count": str(routing.get("latestCandidateRoutingCenterCount") or 0),
        "Latest displaced readiness status": str(routing.get("latestDisplacedReadinessStatus") or ""),
        "Latest displaced readiness summary": str(routing.get("latestDisplacedReadinessSummary") or ""),
        "Latest displaced readiness HTML": str(routing.get("latestDisplacedReadinessHtml") or ""),
    }
    updated = upsert_markdown_table_rows(
        markdown_path.read_text(encoding="utf-8"),
        "## Visual/capture proof-route policy",
        {key: value for key, value in rows.items() if value},
    )
    write_text_atomic(markdown_path, updated)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a fail-closed coordinate proof route manifest from existing evidence artifacts.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--output-root", type=Path, help="Output directory. Defaults under scripts/captures.")
    parser.add_argument("--pid", type=int, help="Expected current RIFT PID.")
    parser.add_argument("--hwnd", help="Expected current RIFT HWND.")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--process-start-utc")
    parser.add_argument("--current-truth", type=Path, help="Defaults to docs/recovery/current-truth.json when present.")
    parser.add_argument("--capture-manifest", type=Path, action="append", default=[])
    parser.add_argument("--api-reference", type=Path)
    parser.add_argument("--memory-readback", type=Path)
    parser.add_argument("--static-root-summary", type=Path, action="append", default=[])
    parser.add_argument("--center-file", type=Path, action="append", default=[])
    parser.add_argument("--candidate-comparison", type=Path, action="append", default=[])
    parser.add_argument("--displaced-readiness-summary", type=Path, action="append", default=[])
    parser.add_argument("--write-summary", action="store_true")
    parser.add_argument("--summary-file", type=Path, help="Explicit JSON summary path; Markdown is written next to it.")
    parser.add_argument("--update-current-truth", action="store_true")
    parser.add_argument("--compact-json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    current_truth = args.current_truth
    if current_truth is None:
        candidate = repo_root / "docs" / "recovery" / "current-truth.json"
        current_truth = candidate if candidate.exists() else None
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"coordinate-proof-route-{utc_stamp()}"
    route = build_coordinate_proof_route(
        repo_root=repo_root,
        output_root=output_root,
        process_id=args.pid,
        target_window_handle=args.hwnd,
        process_name=args.process_name,
        process_start_utc=args.process_start_utc,
        current_truth_path=current_truth,
        capture_manifests=args.capture_manifest,
        api_reference_path=args.api_reference,
        memory_readback_path=args.memory_readback,
        static_root_summaries=args.static_root_summary,
        center_files=args.center_file,
        candidate_comparisons=args.candidate_comparison,
        displaced_readiness_summaries=args.displaced_readiness_summary,
    )
    if args.summary_file:
        summary_html = args.summary_file.with_suffix(".html")
        latest_pointer = repo_root / "scripts" / "captures" / "latest-coordinate-proof-route.json"
        route["artifacts"]["summaryJson"] = path_text(args.summary_file, repo_root)
        route["artifacts"]["summaryMarkdown"] = path_text(args.summary_file.with_suffix(".md"), repo_root)
        route["artifacts"]["summaryHtml"] = path_text(summary_html, repo_root)
        route["artifacts"]["latestPointer"] = path_text(latest_pointer, repo_root)
        write_json(args.summary_file, route)
        write_text_atomic(args.summary_file.with_suffix(".md"), markdown_summary(route))
        write_text_atomic(summary_html, html_summary(route))
        write_json(latest_pointer, latest_pointer_payload(route))
    elif args.write_summary:
        write_route(route, output_root, repo_root=repo_root)
    if args.update_current_truth:
        update_current_truth(route, repo_root)
    if args.compact_json:
        print(json.dumps(route, separators=(",", ":")))
    else:
        print(json.dumps(route, indent=2))
    decision = route.get("decision") if isinstance(route.get("decision"), dict) else {}
    return 0 if decision.get("readOnlyProofAllowed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
