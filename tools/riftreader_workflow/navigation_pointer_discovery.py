#!/usr/bin/env python3
"""Summarize navigation pointer-chain discovery evidence.

This helper is intentionally read-only. It indexes existing RiftReader-owned
artifacts and current truth docs, then emits a compact dashboard for promoted
coordinate state and candidate-only navigation fields. It never sends live
input, reads target memory, attaches debuggers, writes providers, mutates Git,
or promotes proof.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, preview_text, repo_rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    _script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(_script_dir.parent))
    from riftreader_workflow.common import find_repo_root, preview_text, repo_rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-navigation-pointer-discovery-v0.1.0"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "navigation-pointer-discovery" / "latest"
CAPTURE_ROOT = Path("scripts") / "captures"
CURRENT_READBACK_MAX_AGE_SECONDS = 1800
DISCOVERY_EVIDENCE_MAX_AGE_SECONDS = 86400
SOURCE_FRESHNESS_BUDGETS_SECONDS = {
    "currentTruth": CURRENT_READBACK_MAX_AGE_SECONDS,
    "coordinateReadback": CURRENT_READBACK_MAX_AGE_SECONDS,
    "navState": CURRENT_READBACK_MAX_AGE_SECONDS,
    "apiReference": CURRENT_READBACK_MAX_AGE_SECONDS,
    "facingComparison": DISCOVERY_EVIDENCE_MAX_AGE_SECONDS,
    "pointerNeighborhood": DISCOVERY_EVIDENCE_MAX_AGE_SECONDS,
    "familySnapshot": DISCOVERY_EVIDENCE_MAX_AGE_SECONDS,
    "cameraYawClassification": DISCOVERY_EVIDENCE_MAX_AGE_SECONDS,
    "cameraYawMultipose": DISCOVERY_EVIDENCE_MAX_AGE_SECONDS,
    "facingThreePoseGate": DISCOVERY_EVIDENCE_MAX_AGE_SECONDS,
    "facingRestartSurvival": DISCOVERY_EVIDENCE_MAX_AGE_SECONDS,
    "turnForwardExperiment": DISCOVERY_EVIDENCE_MAX_AGE_SECONDS,
    "ghidraStaticEvidence": DISCOVERY_EVIDENCE_MAX_AGE_SECONDS,
    "facingPromotionReadinessReview": CURRENT_READBACK_MAX_AGE_SECONDS,
}


class NavigationPointerDiscoveryError(RuntimeError):
    """Raised for controlled helper failures."""


def safe_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_utc(value: Any) -> str | None:
    parsed = parse_iso(value)
    if parsed is None:
        return str(value) if value else None
    return parsed.isoformat().replace("+00:00", "Z")


def normalize_hwnd(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = int(text, 16) if text.lower().startswith("0x") else int(text, 10)
    except ValueError:
        return text
    return f"0x{number:X}"


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise NavigationPointerDiscoveryError(f"malformed-json:{path}:{exc}") from exc
    if not isinstance(data, dict):
        raise NavigationPointerDiscoveryError(f"json-root-not-object:{path}")
    return data


def try_load_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return load_json_object(path), None
    except Exception as exc:  # noqa: BLE001 - status helper must capture malformed artifacts.
        return None, f"{type(exc).__name__}: {exc}"


def absolute_from_artifact(repo_root: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else repo_root / path


def artifact_path(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    return repo_rel(repo_root, path)


def normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def freshness_summary(observed_at: Any, *, now: datetime, max_age_seconds: int) -> dict[str, Any]:
    observed = parse_iso(observed_at)
    if observed is None:
        return {
            "status": "unknown",
            "ageSeconds": None,
            "maxAgeSeconds": max_age_seconds,
            "observedAtUtc": observed_at,
        }
    age_seconds = round((now - observed).total_seconds(), 3)
    if age_seconds < -5:
        status = "future-clock-skew"
    elif age_seconds <= max_age_seconds:
        status = "fresh"
    else:
        status = "stale"
    return {
        "status": status,
        "ageSeconds": age_seconds,
        "maxAgeSeconds": max_age_seconds,
        "observedAtUtc": observed.isoformat().replace("+00:00", "Z"),
    }


def current_truth_observed_at(current_truth: dict[str, Any] | None) -> Any:
    truth = safe_mapping(current_truth)
    target = safe_mapping(truth.get("target"))
    primary = safe_mapping(safe_mapping(truth.get("staticChainStatus")).get("primaryCandidate"))
    return (
        truth.get("updatedAtUtc")
        or target.get("lastVerifiedUtc")
        or primary.get("latestCurrentReadbackAtUtc")
        or target.get("processStartUtc")
    )


def newest_summary(
    repo_root: Path,
    *,
    directory_prefix: str,
    expected_kind: str | None = None,
    warn_kind_mismatch: bool = True,
) -> tuple[Path | None, dict[str, Any] | None, list[str]]:
    capture_root = repo_root / CAPTURE_ROOT
    warnings: list[str] = []
    if not capture_root.is_dir():
        return None, None, [f"capture-root-missing:{repo_rel(repo_root, capture_root)}"]

    valid: list[tuple[datetime, Path, dict[str, Any]]] = []
    for path in capture_root.glob(f"{directory_prefix}*/summary.json"):
        if not path.is_file():
            continue
        data, error = try_load_json_object(path)
        if error or data is None:
            warnings.append(f"artifact-parse-error:{repo_rel(repo_root, path)}:{preview_text(error)}")
            continue
        if expected_kind and data.get("kind") != expected_kind:
            if warn_kind_mismatch:
                warnings.append(
                    f"artifact-kind-mismatch:{repo_rel(repo_root, path)}:"
                    f"expected={expected_kind}:actual={data.get('kind')}"
                )
            continue
        generated = parse_iso(data.get("generatedAtUtc"))
        if generated is None:
            generated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            warnings.append(f"artifact-generatedAtUtc-missing:{repo_rel(repo_root, path)}")
        valid.append((generated, path, data))

    if not valid:
        return None, None, warnings
    _generated, path, data = max(valid, key=lambda item: (item[0], item[1].stat().st_mtime_ns))
    return path, data, warnings


def summarize_source(
    repo_root: Path,
    path: Path | None,
    data: dict[str, Any] | None,
    *,
    now: datetime,
    max_age_seconds: int,
) -> dict[str, Any]:
    if not path or not data:
        return {
            "status": "missing",
            "freshness": freshness_summary(None, now=now, max_age_seconds=max_age_seconds),
        }
    return {
        "status": data.get("status"),
        "kind": data.get("kind") or data.get("mode"),
        "verdict": data.get("verdict"),
        "generatedAtUtc": data.get("generatedAtUtc"),
        "freshness": freshness_summary(data.get("generatedAtUtc"), now=now, max_age_seconds=max_age_seconds),
        "path": artifact_path(repo_root, path),
        "blockers": safe_list(data.get("blockers")),
        "warnings": safe_list(data.get("warnings")),
    }


def summarize_api_reference_source(
    repo_root: Path,
    path: Path | None,
    data: dict[str, Any] | None,
    *,
    now: datetime,
    max_age_seconds: int,
) -> dict[str, Any]:
    if not path or not data:
        return {
            "status": "missing",
            "freshness": freshness_summary(None, now=now, max_age_seconds=max_age_seconds),
        }
    observed = api_reference_observed_at(data)
    return {
        "status": data.get("Status") or data.get("status") or safe_mapping(data.get("marker")).get("status"),
        "kind": data.get("Mode") or data.get("mode"),
        "verdict": data.get("Status") or data.get("status") or safe_mapping(data.get("marker")).get("status"),
        "generatedAtUtc": iso_utc(observed),
        "freshness": freshness_summary(observed, now=now, max_age_seconds=max_age_seconds),
        "path": artifact_path(repo_root, path),
        "blockers": safe_list(data.get("Blockers") or data.get("blockers")),
        "warnings": safe_list(data.get("Warnings") or data.get("warnings")),
    }


def newest_api_reference_for_pid(repo_root: Path, pid: Any) -> tuple[Path | None, dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    if pid is None:
        return None, None, ["api-reference-target-pid-missing"]
    capture_root = repo_root / CAPTURE_ROOT
    valid: list[tuple[datetime, Path, dict[str, Any]]] = []
    for path in capture_root.glob(f"rift-api-reference-currentpid-{pid}-*.json"):
        data, error = try_load_json_object(path)
        if error or data is None:
            warnings.append(f"artifact-parse-error:{repo_rel(repo_root, path)}:{preview_text(error)}")
            continue
        observed = (
            data.get("GeneratedAtUtc")
            or data.get("generatedAtUtc")
            or data.get("captured_at_utc")
            or data.get("capturedAtUtc")
            or safe_mapping(data.get("Coordinate")).get("CapturedAtUtc")
            or safe_mapping(data.get("coordinate")).get("capturedAtUtc")
        )
        generated = parse_iso(observed)
        if generated is None:
            generated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            warnings.append(f"artifact-generatedAtUtc-missing:{repo_rel(repo_root, path)}")
        valid.append((generated, path, data))
    if not valid:
        return None, None, warnings
    _generated, path, data = max(valid, key=lambda item: (item[0], item[1].stat().st_mtime_ns))
    return path, data, warnings


def api_reference_coordinate(api_reference: dict[str, Any] | None) -> dict[str, float] | None:
    coordinate = safe_mapping(safe_mapping(api_reference).get("Coordinate")) or safe_mapping(
        safe_mapping(api_reference).get("coordinate")
    )
    try:
        return {
            "x": float(coordinate.get("X", coordinate.get("x"))),
            "y": float(coordinate.get("Y", coordinate.get("y"))),
            "z": float(coordinate.get("Z", coordinate.get("z"))),
        }
    except (TypeError, ValueError):
        return None


def api_reference_observed_at(api_reference: dict[str, Any] | None) -> Any:
    api = safe_mapping(api_reference)
    coordinate = safe_mapping(api.get("Coordinate")) or safe_mapping(api.get("coordinate"))
    return (
        api.get("captured_at_utc")
        or api.get("capturedAtUtc")
        or coordinate.get("captured_at_utc")
        or coordinate.get("CapturedAtUtc")
        or coordinate.get("capturedAtUtc")
        or api.get("GeneratedAtUtc")
        or api.get("generatedAtUtc")
    )


def api_now_comparison(
    *,
    target_pid: Any,
    promoted_coordinate: dict[str, Any],
    api_reference: dict[str, Any] | None,
    api_path: Path | None,
    repo_root: Path,
) -> tuple[str | None, dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    if not api_reference or not api_path:
        return None, None, warnings
    marker = safe_mapping(api_reference.get("marker"))
    api_status = api_reference.get("Status") or api_reference.get("status") or marker.get("status")
    api_pid = api_reference.get("ProcessId") or api_reference.get("processId")
    api_coord = api_reference_coordinate(api_reference)
    chain_coord = safe_mapping(promoted_coordinate.get("coordinate"))
    if str(api_status).lower() not in {"captured", "pass"}:
        return "api-now-reference-not-captured", None, warnings
    if target_pid is not None and str(api_pid) != str(target_pid):
        warnings.append(f"api-reference-target-mismatch:api={api_pid};target={target_pid}")
        return "stale-api-now-target-mismatch", None, warnings
    if api_coord is None:
        return "api-now-reference-coordinate-missing", None, warnings
    try:
        chain_xyz = {
            "x": float(chain_coord["x"]),
            "y": float(chain_coord["y"]),
            "z": float(chain_coord["z"]),
        }
    except (KeyError, TypeError, ValueError):
        return "api-now-chain-coordinate-missing", None, warnings
    deltas = {axis: chain_xyz[axis] - api_coord[axis] for axis in ("x", "y", "z")}
    abs_deltas = {axis: abs(value) for axis, value in deltas.items()}
    max_abs_delta = max(abs_deltas.values())
    tolerance = float(
        api_reference.get("ReferenceTolerance")
        or api_reference.get("referenceTolerance")
        or api_reference.get("tolerance")
        or 0.25
    )
    within_tolerance = max_abs_delta <= tolerance
    status = (
        f"passed-current-pid-{target_pid}-api-now-vs-chain-now"
        if within_tolerance
        else f"blocked-current-pid-{target_pid}-api-now-vs-chain-now-delta"
    )
    comparison = {
        "status": status,
        "apiReferenceJson": artifact_path(repo_root, api_path),
        "capturedAtUtc": iso_utc(api_reference_observed_at(api_reference)),
        "apiCoordinate": api_coord,
        "chainCoordinate": chain_xyz,
        "deltasChainMinusApi": deltas,
        "absDeltas": abs_deltas,
        "maxAbsDelta": max_abs_delta,
        "tolerance": tolerance,
        "withinTolerance": within_tolerance,
    }
    return status, comparison, warnings


def readback_target(data: dict[str, Any] | None, *, source: str) -> dict[str, Any] | None:
    if safe_mapping(data).get("status") != "passed":
        return None
    raw = safe_mapping(safe_mapping(data).get("target"))
    pid = raw.get("processId") or raw.get("pid")
    hwnd = normalize_hwnd(raw.get("targetWindowHandle") or raw.get("hwnd"))
    if pid is None or hwnd is None:
        return None
    process_name = raw.get("processName") or "rift_x64"
    process_start = (
        raw.get("expectedProcessStartUtc")
        or raw.get("processStartUtc")
        or raw.get("actualProcessStartUtc")
    )
    module_base = raw.get("moduleBase") or safe_mapping(raw.get("moduleBaseCheck")).get("liveModuleBase")
    return {
        "processName": process_name,
        "processId": int(pid),
        "targetWindowHandle": hwnd,
        "processStartUtc": iso_utc(process_start),
        "moduleBase": module_base,
        "status": f"current-pid-{int(pid)}-static-chain-readback-passed",
        "identitySource": source,
    }


def current_readback_target(
    coordinate_readback: dict[str, Any] | None,
    nav_state: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    coordinate_target = readback_target(coordinate_readback, source="latest-coordinate-readback")
    nav_target = readback_target(nav_state, source="latest-nav-state-readback")
    warnings: list[str] = []
    if coordinate_target and nav_target:
        mismatch_fields: list[str] = []
        for field in ("processName", "processId", "targetWindowHandle", "processStartUtc", "moduleBase"):
            if str(coordinate_target.get(field)) != str(nav_target.get(field)):
                mismatch_fields.append(field)
        if mismatch_fields:
            warnings.append(
                "readback-target-identity-mismatch:"
                + ",".join(
                    f"{field}:coordinate={coordinate_target.get(field)};nav={nav_target.get(field)}"
                    for field in mismatch_fields
                )
            )
            return None, warnings
        merged = dict(coordinate_target)
        merged["identitySource"] = "latest-coordinate-and-nav-state-readbacks"
        return merged, warnings
    return coordinate_target or nav_target, warnings


def api_now_status_for_target(static_status: dict[str, Any], target: dict[str, Any]) -> tuple[str | None, str | None]:
    current_api = safe_mapping(static_status.get("latestApiNowValidation"))
    current_pid_validation = safe_mapping(current_api.get("currentPidValidation"))
    status = (
        current_pid_validation.get("status")
        or current_api.get("currentApiNowStatus")
        or current_api.get("status")
    )
    if not status:
        return None, None
    target_pid = target.get("processId")
    match = re.search(r"current-pid-(\d+)", str(status))
    if match and target_pid is not None and str(target_pid) != match.group(1):
        return "stale-api-now-target-mismatch", (
            f"api-now-validation-target-mismatch:api={match.group(1)};target={target_pid}"
        )
    return str(status), None


def aggregate_source_freshness(sources: dict[str, Any]) -> dict[str, Any]:
    fresh: list[str] = []
    stale: list[str] = []
    unknown: list[str] = []
    future_skew: list[str] = []
    ages: list[float] = []
    for label, source in sources.items():
        freshness = safe_mapping(safe_mapping(source).get("freshness"))
        status = freshness.get("status")
        age = freshness.get("ageSeconds")
        if isinstance(age, (int, float)):
            ages.append(float(age))
        if status == "fresh":
            fresh.append(label)
        elif status == "stale":
            stale.append(label)
        elif status == "future-clock-skew":
            future_skew.append(label)
        else:
            unknown.append(label)
    return {
        "status": "stale" if stale else ("future-clock-skew" if future_skew else ("unknown" if unknown and not fresh else "fresh")),
        "freshSources": fresh,
        "staleSources": stale,
        "unknownSources": unknown,
        "futureClockSkewSources": future_skew,
        "oldestAgeSeconds": max(ages) if ages else None,
        "budgetsSeconds": dict(SOURCE_FRESHNESS_BUDGETS_SECONDS),
        "interpretation": (
            "Freshness is an operator resume signal only. Stale candidate artifacts remain historical evidence "
            "and do not authorize promotion or live input."
        ),
    }


def int_from_hex(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value), 16)
    except (TypeError, ValueError):
        return None


def offset_hex(base_hex: Any, address_hex: Any) -> str | None:
    base = int_from_hex(base_hex)
    address = int_from_hex(address_hex)
    if base is None or address is None:
        return None
    delta = address - base
    sign = "-" if delta < 0 else ""
    return f"{sign}0x{abs(delta):X}"


def address_plus_offset(address_hex: Any, offset: int) -> str | None:
    address = int_from_hex(address_hex)
    if address is None:
        return None
    return f"0x{address + offset:X}"


def top_relative_target_candidate(facing_comparison: dict[str, Any] | None) -> dict[str, Any] | None:
    comparison = safe_mapping(safe_mapping(facing_comparison).get("comparison"))
    candidates = safe_list(comparison.get("relativeTargetCandidates"))
    if not candidates:
        return None
    return safe_mapping(candidates[0])


def scalar_candidate_by_offset(facing_comparison: dict[str, Any] | None, offset: str) -> dict[str, Any] | None:
    comparison = safe_mapping(safe_mapping(facing_comparison).get("comparison"))
    for candidate in safe_list(comparison.get("scalarCandidates")):
        item = safe_mapping(candidate)
        if str(item.get("offset")).lower() == offset.lower():
            return item
    return None


def load_candidate_vec3(repo_root: Path, family_summary: dict[str, Any] | None, warnings: list[str]) -> dict[str, Any] | None:
    artifacts = safe_mapping(safe_mapping(family_summary).get("artifacts"))
    path = absolute_from_artifact(repo_root, artifacts.get("candidateVec3Json"))
    if path is None:
        return None
    data, error = try_load_json_object(path)
    if error or data is None:
        warnings.append(f"candidate-vec3-parse-error:{artifact_path(repo_root, path)}:{preview_text(error)}")
        return None
    return data


def promoted_coordinate_summary(
    repo_root: Path,
    current_truth: dict[str, Any] | None,
    coordinate_readback: dict[str, Any] | None,
    readback_path: Path | None,
) -> dict[str, Any]:
    static_status = safe_mapping(safe_mapping(current_truth).get("staticChainStatus"))
    primary = safe_mapping(static_status.get("primaryCandidate"))
    readback_candidate = safe_mapping(safe_mapping(coordinate_readback).get("candidate"))
    reads = safe_mapping(safe_mapping(coordinate_readback).get("reads"))
    analysis = safe_mapping(safe_mapping(coordinate_readback).get("analysis"))
    owner_address = reads.get("ownerAddress") or primary.get("ownerAddress")
    coordinate_address = address_plus_offset(owner_address, 0x320) or primary.get("coordinateAddress")
    coordinate = reads.get("coordinate") or primary.get("coordinate")
    return {
        "status": static_status.get("status") or safe_mapping(coordinate_readback).get("status"),
        "promotionAllowed": bool(static_status.get("promotionAllowed")),
        "candidateOnly": False,
        "chain": primary.get("chain") or readback_candidate.get("chain"),
        "rootModule": primary.get("rootModule") or readback_candidate.get("rootModule"),
        "rootRva": primary.get("rootRva") or readback_candidate.get("rootRva"),
        "rootAddress": readback_candidate.get("rootAddress") or primary.get("rootAddress"),
        "ownerAddress": owner_address,
        "coordinateAddress": coordinate_address,
        "coordinateOffset": "0x320",
        "coordinate": coordinate,
        "latestReadbackStatus": safe_mapping(coordinate_readback).get("status"),
        "latestReadbackAtUtc": safe_mapping(coordinate_readback).get("generatedAtUtc") or primary.get("latestCurrentReadbackAtUtc"),
        "latestReadbackJson": artifact_path(repo_root, readback_path),
        "maxPlanarDelta": analysis.get("maxPlanarDelta"),
        "apiNowStatus": safe_mapping(static_status.get("latestApiNowValidation")).get("currentApiNowStatus")
        or safe_mapping(static_status.get("latestApiNowValidation")).get("status"),
        "notes": [
            "Promoted coordinate resolver only.",
            "Reacquire owner through rift_x64+0x32EBC80; do not reuse heap addresses across target epochs.",
        ],
    }


def facing_target_summary(
    repo_root: Path,
    nav_state: dict[str, Any] | None,
    nav_state_path: Path | None,
    facing_comparison: dict[str, Any] | None,
    facing_comparison_path: Path | None,
    pointer_neighborhood: dict[str, Any] | None,
    pointer_neighborhood_path: Path | None,
) -> dict[str, Any] | None:
    latest_state = safe_mapping(safe_mapping(nav_state).get("latestState"))
    relative = top_relative_target_candidate(facing_comparison)
    if not latest_state and relative is None:
        return None
    comparison = safe_mapping(safe_mapping(facing_comparison).get("comparison"))
    owner_addresses = safe_list(comparison.get("ownerAddresses"))
    owner_address = latest_state.get("ownerAddress") or (owner_addresses[0] if owner_addresses else None)
    address_hex = latest_state.get("facingTargetAddress") or safe_mapping(relative).get("address")
    analysis = safe_mapping(safe_mapping(pointer_neighborhood).get("analysis"))
    return {
        "status": "candidate-only",
        "candidateOnly": True,
        "promotionAllowed": False,
        "chainShape": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
        "ownerAddress": owner_address,
        "address": address_hex,
        "offset": latest_state.get("facingTargetOffset") or safe_mapping(relative).get("offset") or "0x30C",
        "offsetFromOwner": offset_hex(owner_address, address_hex),
        "latestYawDegrees": latest_state.get("yawDegrees"),
        "latestPitchDegrees": latest_state.get("pitchDegrees"),
        "latestFacingTargetCoordinate": latest_state.get("facingTargetCoordinate"),
        "planarLookaheadDistance": latest_state.get("planarLookaheadDistance"),
        "comparisonYawDeltasFromBaseline": safe_mapping(relative).get("yawDeltasFromBaseline"),
        "comparisonMaxAbsYawDeltaDegrees": safe_mapping(relative).get("maxAbsYawDeltaDegrees"),
        "comparisonMaxCoordinatePlanarDrift": safe_mapping(safe_mapping(facing_comparison).get("comparison")).get("maxCoordinatePlanarDrift"),
        "pointerNeighborhood": {
            "status": safe_mapping(pointer_neighborhood).get("status"),
            "exactTargetCount": safe_mapping(analysis.get("exactTargetCounts")).get(str(address_hex)) if address_hex else None,
            "regionMatchCount": analysis.get("regionMatchCount"),
            "modulePointerCount": analysis.get("modulePointerCount"),
            "path": artifact_path(repo_root, pointer_neighborhood_path),
        },
        "evidence": {
            "navStateJson": artifact_path(repo_root, nav_state_path),
            "facingComparisonJson": artifact_path(repo_root, facing_comparison_path),
        },
        "promotionBlockers": [
            "candidate-only-facing-target",
            "requires-static-root-reference-proof",
            "requires-restart-relog-survival",
            "requires-three-pose-displacement-validation",
        ],
    }


def turn_rate_summary(nav_state: dict[str, Any] | None, facing_comparison: dict[str, Any] | None) -> dict[str, Any] | None:
    latest_state = safe_mapping(safe_mapping(nav_state).get("latestState"))
    scalar = scalar_candidate_by_offset(facing_comparison, "0x304")
    if not latest_state and scalar is None:
        return None
    return {
        "status": "candidate-only",
        "candidateOnly": True,
        "promotionAllowed": False,
        "offset": latest_state.get("turnRateOffset") or "0x304",
        "latestValue": latest_state.get("turnRate0x304"),
        "latestClassification": latest_state.get("turnRateClassification"),
        "comparisonDeltasFromBaseline": safe_mapping(scalar).get("deltasFromBaseline"),
        "comparisonMaxAbsDelta": safe_mapping(scalar).get("maxAbsDelta"),
        "promotionBlockers": [
            "candidate-only-turn-rate",
            "requires-dedicated-turn-stimulus-proof",
            "requires-restart-relog-survival",
        ],
    }


def coordinate_delta_summary(
    repo_root: Path,
    current_truth: dict[str, Any] | None,
    family_summary: dict[str, Any] | None,
    family_path: Path | None,
    candidate_vec3: dict[str, Any] | None,
) -> dict[str, Any] | None:
    analysis = safe_mapping(safe_mapping(family_summary).get("analysis"))
    nested_analysis = safe_mapping(analysis.get("analysis"))
    best = safe_mapping(nested_analysis.get("bestCandidate"))
    if not best:
        candidates = safe_list(safe_mapping(candidate_vec3).get("candidates"))
        best = safe_mapping(candidates[0]) if candidates else {}
    if not best:
        return None
    primary = safe_mapping(safe_mapping(safe_mapping(current_truth).get("staticChainStatus")).get("primaryCandidate"))
    promoted_address = primary.get("coordinateAddress")
    best_address = best.get("addressHex") or best.get("absolute_address_hex")
    matches_promoted = bool(promoted_address and best_address and str(promoted_address).lower() == str(best_address).lower())
    return {
        "status": "confirms-promoted-coordinate-offset" if matches_promoted else "candidate-only",
        "candidateOnly": not matches_promoted,
        "promotionAllowed": False,
        "promotionState": "already-promoted-coordinate-evidence" if matches_promoted else "candidate-only-requires-proof",
        "candidateId": best.get("candidateId") or best.get("candidate_id"),
        "address": best_address,
        "ownerOffset": "0x320" if matches_promoted else None,
        "segmentOffset": best.get("segmentOffsetHex") or best.get("offset_hex"),
        "axisOrder": best.get("axisOrder") or best.get("axis_order"),
        "matchesPromotedCoordinateAddress": matches_promoted,
        "apiDeltaPlanar": safe_mapping(best.get("apiDelta")).get("planar"),
        "memoryDeltaPlanar": safe_mapping(best.get("memoryDelta")).get("planar"),
        "trackingErrorMaxAbs": safe_mapping(best.get("trackingError")).get("maxAbs"),
        "baselineMaxAbsDelta": best.get("baselineMaxAbsDelta"),
        "displacedMaxAbsDelta": best.get("displacedMaxAbsDelta"),
        "candidateCount": nested_analysis.get("candidateCount") or safe_mapping(candidate_vec3).get("candidateCount"),
        "familyCount": nested_analysis.get("familyCount"),
        "familySummaryJson": repo_rel(repo_root, family_path) if family_path else None,
        "notes": [
            "Delta evidence confirms movement tracking for this target epoch.",
            "It does not promote any new navigation pointer chain by itself.",
        ],
    }


def camera_yaw_classification_summary(
    repo_root: Path,
    camera_yaw: dict[str, Any] | None,
    camera_yaw_path: Path | None,
) -> dict[str, Any] | None:
    if not camera_yaw:
        return None
    if camera_yaw.get("kind") == "static-owner-camera-yaw-multipose-report":
        analysis = safe_mapping(camera_yaw.get("analysis"))
        source_safety = safe_mapping(camera_yaw.get("sourceSafety"))
        poses = safe_list(camera_yaw.get("poses"))
        route_actionable_count = int(analysis.get("routeActionablePoseCount") or 0)
        offset_aggregate = safe_mapping(camera_yaw.get("offsetAggregate"))
        return {
            "status": "candidate-only",
            "candidateOnly": True,
            "promotionAllowed": False,
            "proofPackKind": "multipose-camera-yaw-report",
            "verdict": camera_yaw.get("verdict"),
            "classification": camera_yaw.get("verdict"),
            "generatedAtUtc": camera_yaw.get("generatedAtUtc"),
            "sourceCount": camera_yaw.get("sourceCount"),
            "classificationCounts": analysis.get("classificationCounts"),
            "routeActionablePoseCount": route_actionable_count,
            "visualChangedStaticYawUnchangedCount": analysis.get("visualChangedStaticYawUnchangedCount"),
            "changedFocusOffsetCount": analysis.get("changedOffsetCount"),
            "changedFocusOffsets": [
                {
                    "offset": offset,
                    "sampleCount": safe_mapping(item).get("sampleCount"),
                    "directions": safe_mapping(item).get("directions"),
                    "maxAbsDelta": safe_mapping(item).get("maxAbsDelta"),
                }
                for offset, item in sorted(offset_aggregate.items())
            ][:10],
            "actionableForRouteControl": analysis.get("actionableForRouteControl"),
            "poses": [
                {
                    "summaryJson": safe_mapping(pose).get("summaryJson"),
                    "direction": safe_mapping(safe_mapping(pose).get("stimulus")).get("direction"),
                    "pixels": safe_mapping(safe_mapping(pose).get("stimulus")).get("pixels"),
                    "classification": safe_mapping(pose).get("classification"),
                    "staticYawChanged": safe_mapping(pose).get("staticYawChanged"),
                    "signedYawDeltaDegrees": safe_mapping(pose).get("signedYawDeltaDegrees"),
                    "actionableForRouteControl": safe_mapping(pose).get("actionableForRouteControl"),
                }
                for pose in poses[:10]
            ],
            "evidence": {
                "summaryJson": artifact_path(repo_root, camera_yaw_path),
                "sourceInputSent": source_safety.get("inputSent"),
                "sourceMovementSent": source_safety.get("movementSent"),
                "sourceTargetMemoryBytesRead": source_safety.get("targetMemoryBytesRead"),
            },
            "promotionBlockers": [
                "candidate-only-camera-yaw-multipose-report",
                "requires-route-actionable-yaw-control-proof",
                "requires-formal-three-pose-displacement-validation",
                "requires-restart-relog-survival",
                "requires-separate-promotion-approval",
            ],
        }
    analysis = safe_mapping(camera_yaw.get("analysis"))
    stimulus = safe_mapping(camera_yaw.get("stimulus"))
    visual = safe_mapping(camera_yaw.get("visualEvidence"))
    snapshot = safe_mapping(camera_yaw.get("snapshotEvidence"))
    raw_diff = safe_mapping(safe_mapping(visual.get("rawDiff")))
    changed_offsets = safe_list(analysis.get("changedFocusOffsets"))
    return {
        "status": "candidate-only",
        "candidateOnly": True,
        "promotionAllowed": False,
        "verdict": camera_yaw.get("verdict"),
        "classification": analysis.get("classification") or camera_yaw.get("verdict"),
        "generatedAtUtc": camera_yaw.get("generatedAtUtc"),
        "stimulus": {
            "type": stimulus.get("type"),
            "direction": stimulus.get("direction"),
            "pixels": stimulus.get("pixels"),
            "approved": bool(stimulus.get("approved")),
        },
        "visualChanged": analysis.get("visualChanged"),
        "staticYawChanged": analysis.get("staticYawChanged"),
        "actionableForRouteControl": analysis.get("actionableForRouteControl"),
        "signedYawDeltaDegrees": analysis.get("signedYawDeltaDegrees"),
        "absoluteYawDeltaDegrees": analysis.get("absoluteYawDeltaDegrees"),
        "changedFocusOffsetCount": len(changed_offsets),
        "changedFocusOffsets": changed_offsets[:10],
        "visualRawDiff": {
            "status": raw_diff.get("status"),
            "changedPercent": raw_diff.get("changedPercent"),
        },
        "evidence": {
            "summaryJson": artifact_path(repo_root, camera_yaw_path),
            "baselinePng": safe_mapping(visual.get("baseline")).get("output"),
            "postPng": safe_mapping(visual.get("post")).get("output"),
            "comparisonJson": snapshot.get("comparisonJson"),
            "pointerNeighborhoodJson": snapshot.get("pointerNeighborhoodJson"),
        },
        "promotionBlockers": [
            "candidate-only-camera-yaw-classification",
            "requires-paired-left-right-return-proof",
            "requires-route-actionable-yaw-control-proof",
            "requires-separate-promotion-approval",
        ],
    }


def facing_three_pose_gate_summary(
    repo_root: Path,
    gate: dict[str, Any] | None,
    gate_path: Path | None,
) -> dict[str, Any] | None:
    if not gate:
        return None
    analysis = safe_mapping(gate.get("analysis"))
    source_safety = safe_mapping(gate.get("sourceSafety"))
    return {
        "status": gate.get("status"),
        "verdict": gate.get("verdict"),
        "candidateOnly": bool(analysis.get("candidateOnly", True)),
        "promotionAllowed": bool(analysis.get("promotionAllowed")),
        "generatedAtUtc": gate.get("generatedAtUtc"),
        "formalThreePoseGatePassed": bool(analysis.get("formalThreePoseGatePassed")),
        "poseCount": gate.get("poseCount"),
        "passedPoseCount": gate.get("passedPoseCount"),
        "aggregateProgressDistance": analysis.get("aggregateProgressDistance"),
        "minimumProgressDistance": analysis.get("minimumProgressDistance"),
        "maximumProgressDistance": analysis.get("maximumProgressDistance"),
        "candidateFacingTargetOffset": analysis.get("candidateFacingTargetOffset"),
        "supportOnlyTurnRateOffset": analysis.get("supportOnlyTurnRateOffset"),
        "evidence": {"summaryJson": artifact_path(repo_root, gate_path)},
        "sourceMovementSent": bool(source_safety.get("movementSent")),
        "sourceInputSent": bool(source_safety.get("inputSent")),
        "blockers": safe_list(gate.get("blockers")),
        "warnings": safe_list(gate.get("warnings")),
        "promotionBlockers": [
            "candidate-only-three-pose-gate",
            "requires-restart-relog-survival",
            "requires-static-root-source-site-review",
            "requires-separate-promotion-review",
        ],
    }


def facing_restart_survival_summary(
    repo_root: Path,
    packet: dict[str, Any] | None,
    packet_path: Path | None,
) -> dict[str, Any] | None:
    if not packet:
        return None
    analysis = safe_mapping(packet.get("analysis"))
    source_safety = safe_mapping(packet.get("sourceSafety"))
    pre_restart = safe_mapping(packet.get("preRestart"))
    post_restart = safe_mapping(packet.get("postRestart"))
    return {
        "status": packet.get("status"),
        "verdict": packet.get("verdict"),
        "candidateOnly": bool(analysis.get("candidateOnly", True)),
        "promotionAllowed": bool(analysis.get("promotionAllowed")),
        "generatedAtUtc": packet.get("generatedAtUtc"),
        "restartRelogSurvived": bool(analysis.get("restartRelogSurvived")),
        "offsetsStable": bool(analysis.get("offsetsStable")),
        "processStartChanged": bool(analysis.get("processStartChanged")),
        "processIdChanged": bool(analysis.get("processIdChanged")),
        "windowHandleChanged": bool(analysis.get("windowHandleChanged")),
        "ownerAddressChanged": bool(analysis.get("ownerAddressChanged")),
        "facingTargetOffset": analysis.get("facingTargetOffset"),
        "positionOffset": analysis.get("positionOffset"),
        "supportOnlyTurnRateOffset": analysis.get("supportOnlyTurnRateOffset"),
        "preRestartSummaryJson": pre_restart.get("summaryJson"),
        "postRestartSummaryJson": post_restart.get("summaryJson"),
        "evidence": {"summaryJson": artifact_path(repo_root, packet_path)},
        "sourceMovementSent": bool(source_safety.get("movementSent")),
        "sourceInputSent": bool(source_safety.get("inputSent")),
        "sourceTargetMemoryBytesRead": bool(source_safety.get("targetMemoryBytesRead")),
        "blockers": safe_list(packet.get("blockers")),
        "warnings": safe_list(packet.get("warnings")),
        "promotionBlockers": [
            "candidate-only-restart-survival-packet",
            "requires-three-pose-route-progress-gate",
            "requires-static-root-source-site-review",
            "requires-separate-promotion-review",
        ],
    }


def turn_forward_experiment_summary(
    repo_root: Path,
    experiment: dict[str, Any] | None,
    experiment_path: Path | None,
) -> dict[str, Any] | None:
    if not experiment:
        return None
    operator = safe_mapping(experiment.get("operator"))
    forward = safe_mapping(experiment.get("forwardResult"))
    contract = safe_mapping(experiment.get("contract"))
    safety = safe_mapping(experiment.get("safety"))
    artifacts = safe_mapping(experiment.get("artifacts"))
    return {
        "status": experiment.get("status"),
        "verdict": experiment.get("verdict"),
        "generatedAtUtc": experiment.get("generatedAtUtc"),
        "candidateOnly": True,
        "promotionAllowed": False,
        "movementApproved": bool(operator.get("movementApproved")),
        "turnApproved": bool(operator.get("turnApproved")),
        "allowCandidateTurnControl": bool(operator.get("allowCandidateTurnControl")),
        "routeStatus": forward.get("routeStatus"),
        "totalProgressDistance": forward.get("totalProgressDistance"),
        "initialPlanarDistance": forward.get("initialPlanarDistance"),
        "finalPlanarDistance": forward.get("finalPlanarDistance"),
        "contractStatus": contract.get("status"),
        "evidence": {
            "summaryJson": artifact_path(repo_root, experiment_path),
            "forwardStepSummaryJson": artifacts.get("forwardStepSummaryJson"),
            "turnAwarePlanSummaryJson": artifacts.get("turnAwarePlanSummaryJson"),
        },
        "sourceMovementSent": bool(safety.get("movementSent")),
        "sourceInputSent": bool(safety.get("inputSent")),
        "sourceNavigationControl": bool(safety.get("navigationControl")),
        "blockers": safe_list(experiment.get("blockers")),
        "warnings": safe_list(experiment.get("warnings")),
    }


def facing_promotion_readiness_review_summary(
    repo_root: Path,
    review: dict[str, Any] | None,
    review_path: Path | None,
) -> dict[str, Any] | None:
    if not review:
        return None
    decision = safe_mapping(review.get("promotionDecision"))
    next_section = safe_mapping(review.get("next"))
    artifacts = safe_mapping(review.get("artifacts"))
    return {
        "status": review.get("status"),
        "verdict": review.get("verdict"),
        "generatedAtUtc": review.get("generatedAtUtc"),
        "summaryJson": artifacts.get("summaryJson") or artifact_path(repo_root, review_path),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "reviewPassed": bool(decision.get("reviewPassed")),
        "promotionAllowed": bool(decision.get("promotionAllowed")),
        "promotionPerformed": bool(decision.get("promotionPerformed")),
        "explicitPromotionGateRequired": bool(decision.get("explicitPromotionGateRequired", True)),
        "freshPrePromotionReadbackRequired": bool(decision.get("freshPrePromotionReadbackRequired", True)),
        "recommendedPromotionState": decision.get("recommendedPromotionState"),
        "nextRecommendedAction": next_section.get("recommendedAction"),
        "target": safe_mapping(review.get("target")),
        "candidate": safe_mapping(review.get("candidate")),
        "blockers": safe_list(review.get("blockers")),
        "warnings": safe_list(review.get("warnings")),
    }


def ghidra_static_evidence_summary(
    repo_root: Path,
    evidence: dict[str, Any] | None,
    evidence_path: Path | None,
) -> dict[str, Any] | None:
    if not evidence:
        return None
    evidence_summary = safe_mapping(evidence.get("evidenceSummary"))
    offsets = safe_mapping(evidence_summary.get("offsets"))
    interesting_offsets: dict[str, Any] = {}
    for offset in ("0x300", "0x304", "0x30C", "0x310", "0x314", "0x320", "0x324", "0x328"):
        offset_summary = safe_mapping(offsets.get(offset))
        if not offset_summary:
            continue
        interesting_offsets[offset] = {
            "hitCount": offset_summary.get("hitCount"),
            "writeLikeCount": offset_summary.get("writeLikeCount"),
            "firstHits": safe_list(offset_summary.get("firstHits"))[:3],
        }
    return {
        "status": evidence.get("status"),
        "kind": evidence.get("kind"),
        "generatedAtUtc": evidence.get("generatedAtUtc"),
        "summaryJson": evidence.get("summaryJson") or artifact_path(repo_root, evidence_path),
        "summaryMarkdown": evidence.get("summaryMarkdown"),
        "evidenceJson": evidence.get("evidenceJson"),
        "programName": evidence_summary.get("programName"),
        "imageBase": evidence_summary.get("imageBase"),
        "rootAddress": evidence_summary.get("rootAddress"),
        "rootReferenceCountCaptured": evidence_summary.get("rootReferenceCountCaptured"),
        "rootReferenceTypes": evidence_summary.get("rootReferenceTypes"),
        "instructionsScanned": evidence_summary.get("instructionsScanned"),
        "offsets": interesting_offsets,
        "analysisTimedOutProjectSaved": "ghidra-analysis-timeout-project-saved" in safe_list(evidence.get("warnings")),
        "offlineOnly": bool(safe_mapping(evidence.get("safety")).get("offlineOnly", True)),
        "blockers": safe_list(evidence.get("blockers")),
        "warnings": safe_list(evidence.get("warnings")),
    }


def build_next_action(
    freshness: dict[str, Any],
    facing_target: dict[str, Any] | None,
    camera_yaw: dict[str, Any] | None = None,
    three_pose_gate: dict[str, Any] | None = None,
    restart_survival: dict[str, Any] | None = None,
    turn_forward: dict[str, Any] | None = None,
    promotion_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stale_sources = set(str(item) for item in safe_list(freshness.get("staleSources")))
    recommended_actions: list[str] = []
    if {"coordinateReadback", "navState"} & stale_sources:
        recommended_actions.append(
            "Refresh no-input static coordinate/nav-state readbacks before navigation decisions."
        )
    if "currentTruth" in stale_sources and not ({"coordinateReadback", "navState"} & stale_sources):
        recommended_actions.append(
            "If tracked truth must be current, run a deliberate current-truth refresh slice from the fresh readback/API evidence; do not treat the dashboard as proof promotion."
        )
    camera_yaw_map = safe_mapping(camera_yaw)
    three_pose_map = safe_mapping(three_pose_gate)
    restart_map = safe_mapping(restart_survival)
    turn_forward_map = safe_mapping(turn_forward)
    promotion_review_map = safe_mapping(promotion_review)
    three_pose_passed = three_pose_map.get("formalThreePoseGatePassed") is True
    restart_survived = restart_map.get("restartRelogSurvived") is True
    turn_forward_passed = turn_forward_map.get("status") == "passed" and turn_forward_map.get("routeStatus") == "progress"
    review_passed = (
        promotion_review_map.get("status") == "passed"
        and promotion_review_map.get("reviewPassed") is True
        and promotion_review_map.get("promotionAllowed") is False
        and promotion_review_map.get("promotionPerformed") is False
    )

    if facing_target and three_pose_passed and restart_survived and review_passed:
        recommended_actions.append(
            "Refresh exact-target static/nav/API readbacks immediately before any explicit facing-promotion gate."
        )
        recommended_actions.append(
            "Run a separate explicit facing-promotion gate only after reviewing the latest readiness packet; do not promote from the dashboard."
        )
        if turn_forward_passed:
            recommended_actions.append(
                "Keep the latest turn-forward progress proof as supporting evidence only; it does not grant movement or promotion permission."
            )
    elif facing_target and three_pose_passed and restart_survived:
        recommended_actions.append(
            "Build a separate candidate-facing promotion-readiness review packet from the three-pose gate, restart-survival packet, latest turn-forward progress proof, and static-root/source-site evidence; do not promote automatically."
        )
        recommended_actions.append(
            "Refresh exact-target static/nav/API readbacks immediately before any additional live movement or review."
        )
        if turn_forward_passed:
            recommended_actions.append(
                "Keep the latest turn-forward progress proof as supporting evidence only; it does not grant movement or promotion permission."
            )
    elif facing_target and three_pose_passed:
        recommended_actions.append(
            "Build or refresh the report-only restart/relog survival packet for owner+0x30C/+0x310/+0x314 before any promotion review."
        )
    elif camera_yaw_map:
        if (
            camera_yaw_map.get("proofPackKind") == "multipose-camera-yaw-report"
            and int(camera_yaw_map.get("routeActionablePoseCount") or 0) >= 2
        ):
            recommended_actions.append(
                "Package the existing route-forward passes into a formal three-pose gate before any promotion review."
            )
            recommended_actions.append(
                "Refresh exact-target static/nav/API readbacks, then run one bounded turn-forward proof only if continuing live route-control evidence."
            )
        elif camera_yaw_map.get("actionableForRouteControl") is True:
            recommended_actions.append(
                "Rerun a small camera/yaw proof pack before any turn-dependent route movement."
            )
        else:
            recommended_actions.append(
                "Run a paired left/right/return camera-yaw classification set under explicit stimulus approval; compare owner+0x300/+0x304 before any turn-dependent route."
            )
    if facing_target and not (three_pose_passed and restart_survived):
        recommended_actions.append(
            "Run restart/relog survival plus static-root proof for owner+0x30C/+0x310/+0x314 before any facing promotion."
        )
    elif not facing_target:
        recommended_actions.append("Run static-owner facing snapshot/compare to reacquire candidate-facing target evidence.")

    return {
        "recommendedAction": recommended_actions[0],
        "recommendedActions": recommended_actions,
    }


def build_navigation_pointer_discovery(repo_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now_utc = normalize_now(now)
    warnings: list[str] = []
    errors: list[str] = []
    blockers: list[str] = []

    truth_path = repo_root / DEFAULT_CURRENT_TRUTH_JSON
    current_truth: dict[str, Any] | None = None
    if truth_path.exists():
        current_truth, error = try_load_json_object(truth_path)
        if error:
            errors.append(f"current-truth-malformed:{repo_rel(repo_root, truth_path)}:{preview_text(error)}")
    else:
        warnings.append(f"current-truth-missing:{repo_rel(repo_root, truth_path)}")

    coord_path, coord_data, coord_warnings = newest_summary(
        repo_root,
        directory_prefix="static-owner-coordinate-chain-readback-",
    )
    nav_path, nav_data, nav_warnings = newest_summary(
        repo_root,
        directory_prefix="static-owner-nav-state-",
        expected_kind="static-owner-nav-state-readback",
    )
    facing_path, facing_data, facing_warnings = newest_summary(
        repo_root,
        directory_prefix="static-owner-facing-comparison-",
        expected_kind="static-owner-facing-comparison",
    )
    pointer_path, pointer_data, pointer_warnings = newest_summary(
        repo_root,
        directory_prefix="pointer-owner-neighborhood-inspector-",
        expected_kind="pointer-owner-neighborhood-inspector",
    )
    family_path, family_data, family_warnings = newest_summary(
        repo_root,
        directory_prefix="family-snapshot-sequence-currentpid-",
    )
    camera_yaw_path, camera_yaw_data, camera_yaw_warnings = newest_summary(
        repo_root,
        directory_prefix="static-owner-camera-yaw-classification-",
        expected_kind="static-owner-camera-yaw-classification",
    )
    camera_yaw_multipose_path, camera_yaw_multipose_data, camera_yaw_multipose_warnings = newest_summary(
        repo_root,
        directory_prefix="static-owner-camera-yaw-multipose-report-",
        expected_kind="static-owner-camera-yaw-multipose-report",
    )
    three_pose_gate_path, three_pose_gate_data, three_pose_gate_warnings = newest_summary(
        repo_root,
        directory_prefix="facing-target-three-pose-gate-",
        expected_kind="facing-target-three-pose-gate",
    )
    restart_survival_path, restart_survival_data, restart_survival_warnings = newest_summary(
        repo_root,
        directory_prefix="facing-target-restart-survival-packet-",
        expected_kind="facing-target-restart-survival-packet",
    )
    turn_forward_path, turn_forward_data, turn_forward_warnings = newest_summary(
        repo_root,
        directory_prefix="static-owner-turn-forward-experiment-20",
        expected_kind="static-owner-turn-forward-experiment",
    )
    promotion_review_path, promotion_review_data, promotion_review_warnings = newest_summary(
        repo_root,
        directory_prefix="facing-target-promotion-readiness-review-",
        expected_kind="facing-target-promotion-readiness-review-packet",
    )
    ghidra_static_path, ghidra_static_data, ghidra_static_warnings = newest_summary(
        repo_root,
        directory_prefix="ghidra-static-analysis-",
        expected_kind="riftreader-ghidra-static-evidence-run",
        warn_kind_mismatch=False,
    )
    warnings.extend(
        coord_warnings
        + nav_warnings
        + facing_warnings
        + pointer_warnings
        + family_warnings
        + camera_yaw_warnings
        + camera_yaw_multipose_warnings
        + three_pose_gate_warnings
        + restart_survival_warnings
        + turn_forward_warnings
        + promotion_review_warnings
        + ghidra_static_warnings
    )
    candidate_vec3 = load_candidate_vec3(repo_root, family_data, warnings)

    readback_identity, identity_warnings = current_readback_target(coord_data, nav_data)
    warnings.extend(identity_warnings)
    truth_target = safe_mapping(safe_mapping(current_truth).get("target"))
    target = readback_identity or {
        "processName": truth_target.get("processName"),
        "processId": truth_target.get("processId") or truth_target.get("pid"),
        "targetWindowHandle": normalize_hwnd(truth_target.get("targetWindowHandle") or truth_target.get("hwnd")),
        "processStartUtc": iso_utc(truth_target.get("processStartUtc")),
        "moduleBase": truth_target.get("moduleBase"),
        "status": truth_target.get("status"),
        "identitySource": "current-truth",
    }
    if identity_warnings:
        blockers.append("readback-target-identity-mismatch")

    promoted_coordinate = promoted_coordinate_summary(repo_root, current_truth, coord_data, coord_path)
    facing_target = facing_target_summary(repo_root, nav_data, nav_path, facing_data, facing_path, pointer_data, pointer_path)
    turn_rate = turn_rate_summary(nav_data, facing_data)
    coordinate_delta = coordinate_delta_summary(repo_root, current_truth, family_data, family_path, candidate_vec3)
    selected_camera_yaw_path = camera_yaw_multipose_path or camera_yaw_path
    selected_camera_yaw_data = camera_yaw_multipose_data or camera_yaw_data
    camera_yaw = camera_yaw_classification_summary(repo_root, selected_camera_yaw_data, selected_camera_yaw_path)
    three_pose_gate = facing_three_pose_gate_summary(repo_root, three_pose_gate_data, three_pose_gate_path)
    restart_survival = facing_restart_survival_summary(repo_root, restart_survival_data, restart_survival_path)
    turn_forward = turn_forward_experiment_summary(repo_root, turn_forward_data, turn_forward_path)
    promotion_review = facing_promotion_readiness_review_summary(repo_root, promotion_review_data, promotion_review_path)
    ghidra_static = ghidra_static_evidence_summary(repo_root, ghidra_static_data, ghidra_static_path)
    api_path, api_data, api_warnings = newest_api_reference_for_pid(repo_root, target.get("processId"))
    warnings.extend(api_warnings)

    if not coord_data and not nav_data and not facing_data and not family_data:
        blockers.append("navigation-pointer-evidence-missing")
    if current_truth is None and truth_path.exists():
        blockers.append("current-truth-unreadable")
    if facing_target is None:
        warnings.append("facing-target-candidate-missing")
    if coordinate_delta is None:
        warnings.append("coordinate-delta-candidate-missing")

    static_status = safe_mapping(safe_mapping(current_truth).get("staticChainStatus"))
    api_reference_status, api_comparison, api_comparison_warnings = api_now_comparison(
        target_pid=target.get("processId"),
        promoted_coordinate=promoted_coordinate,
        api_reference=api_data,
        api_path=api_path,
        repo_root=repo_root,
    )
    warnings.extend(api_comparison_warnings)
    api_now_status, api_now_warning = (
        (api_reference_status, None)
        if api_reference_status
        else api_now_status_for_target(static_status, target)
    )
    if api_now_warning:
        warnings.append(api_now_warning)
    promoted_coordinate["apiNowStatus"] = api_now_status
    if api_comparison:
        promoted_coordinate["apiNowComparison"] = api_comparison
    family_safety = safe_mapping(safe_mapping(family_data).get("safety"))
    camera_yaw_safety = safe_mapping(safe_mapping(selected_camera_yaw_data).get("sourceSafety")) or safe_mapping(
        safe_mapping(selected_camera_yaw_data).get("safety")
    )
    coord_safety = safe_mapping(safe_mapping(coord_data).get("safety"))
    nav_safety = safe_mapping(safe_mapping(nav_data).get("safety"))
    source_safety = {
        "familySnapshotMovementSent": bool(family_safety.get("movementSent")),
        "familySnapshotInputSent": bool(family_safety.get("inputSent")),
        "cameraYawClassificationMovementSent": bool(camera_yaw_safety.get("movementSent")),
        "cameraYawClassificationInputSent": bool(camera_yaw_safety.get("inputSent")),
        "turnForwardExperimentMovementSent": bool(safe_mapping(safe_mapping(turn_forward_data).get("safety")).get("movementSent")),
        "turnForwardExperimentInputSent": bool(safe_mapping(safe_mapping(turn_forward_data).get("safety")).get("inputSent")),
        "latestReadbackTargetMemoryBytesRead": bool(coord_safety.get("targetMemoryBytesRead"))
        or bool(nav_safety.get("targetMemoryBytesRead")),
    }
    sources = {
        "currentTruth": {
            "status": "loaded" if current_truth is not None else "missing-or-unreadable",
            "path": repo_rel(repo_root, truth_path),
            "generatedAtUtc": current_truth_observed_at(current_truth),
            "freshness": freshness_summary(
                current_truth_observed_at(current_truth),
                now=now_utc,
                max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["currentTruth"],
            ),
        },
        "coordinateReadback": summarize_source(
            repo_root,
            coord_path,
            coord_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["coordinateReadback"],
        ),
        "navState": summarize_source(
            repo_root,
            nav_path,
            nav_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["navState"],
        ),
        "apiReference": summarize_api_reference_source(
            repo_root,
            api_path,
            api_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["apiReference"],
        ),
        "facingComparison": summarize_source(
            repo_root,
            facing_path,
            facing_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["facingComparison"],
        ),
        "pointerNeighborhood": summarize_source(
            repo_root,
            pointer_path,
            pointer_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["pointerNeighborhood"],
        ),
        "familySnapshot": summarize_source(
            repo_root,
            family_path,
            family_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["familySnapshot"],
        ),
        "cameraYawClassification": summarize_source(
            repo_root,
            camera_yaw_path,
            camera_yaw_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["cameraYawClassification"],
        ),
        "cameraYawMultipose": summarize_source(
            repo_root,
            camera_yaw_multipose_path,
            camera_yaw_multipose_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["cameraYawMultipose"],
        ),
        "facingThreePoseGate": summarize_source(
            repo_root,
            three_pose_gate_path,
            three_pose_gate_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["facingThreePoseGate"],
        ),
        "facingRestartSurvival": summarize_source(
            repo_root,
            restart_survival_path,
            restart_survival_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["facingRestartSurvival"],
        ),
        "turnForwardExperiment": summarize_source(
            repo_root,
            turn_forward_path,
            turn_forward_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["turnForwardExperiment"],
        ),
        "ghidraStaticEvidence": summarize_source(
            repo_root,
            ghidra_static_path,
            ghidra_static_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["ghidraStaticEvidence"],
        ),
        "facingPromotionReadinessReview": summarize_source(
            repo_root,
            promotion_review_path,
            promotion_review_data,
            now=now_utc,
            max_age_seconds=SOURCE_FRESHNESS_BUDGETS_SECONDS["facingPromotionReadinessReview"],
        ),
    }
    freshness = aggregate_source_freshness(sources)
    promotion_review_passed = (
        safe_mapping(promotion_review).get("reviewPassed") is True
        and safe_mapping(promotion_review).get("promotionAllowed") is False
        and safe_mapping(promotion_review).get("promotionPerformed") is False
    )
    facing_readiness = (
        "review-passed-awaiting-explicit-promotion-gate-and-fresh-readback"
        if promotion_review_passed
        else (
            "candidate-only-gates-packaged-requires-review"
            if facing_target
            and safe_mapping(three_pose_gate).get("formalThreePoseGatePassed")
            and safe_mapping(restart_survival).get("restartRelogSurvived")
            else ("candidate-only-requires-proof" if facing_target else "missing")
        )
    )

    status = "failed" if errors else ("blocked" if blockers else "passed")
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-navigation-pointer-discovery-status",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": "navigation-pointer-discovery-indexed" if status == "passed" else status,
        "repoRoot": str(repo_root),
        "target": {
            "processName": target.get("processName"),
            "processId": target.get("processId") or target.get("pid"),
            "targetWindowHandle": target.get("targetWindowHandle") or target.get("hwnd"),
            "processStartUtc": target.get("processStartUtc"),
            "moduleBase": target.get("moduleBase"),
            "status": target.get("status"),
            "identitySource": target.get("identitySource"),
        },
        "sources": sources,
        "freshness": freshness,
        "candidates": {
            "promotedCoordinate": promoted_coordinate,
            "candidateFacingTarget": facing_target,
            "candidateTurnRate": turn_rate,
            "coordinateDeltaCandidate": coordinate_delta,
            "cameraYawClassification": camera_yaw,
        },
        "proofGates": {
            "facingThreePoseGate": three_pose_gate,
            "facingRestartSurvival": restart_survival,
            "turnForwardExperiment": turn_forward,
            "ghidraStaticEvidence": ghidra_static,
            "facingPromotionReadinessReview": promotion_review,
        },
        "promotionReadiness": {
            "coordinateResolver": static_status.get("status"),
            "currentApiNowStatus": api_now_status,
            "facingTarget": facing_readiness,
            "facingThreePoseGate": "passed" if safe_mapping(three_pose_gate).get("formalThreePoseGatePassed") else "missing-or-not-passed",
            "restartRelogSurvival": "passed" if safe_mapping(restart_survival).get("restartRelogSurvived") else "missing-or-not-passed",
            "turnForwardLiveProgress": (
                "passed"
                if safe_mapping(turn_forward).get("status") == "passed"
                and safe_mapping(turn_forward).get("routeStatus") == "progress"
                else "missing-or-not-passed"
            ),
            "staticEvidence": "passed" if safe_mapping(ghidra_static).get("status") == "passed" else "missing-or-not-passed",
            "turnRate": "candidate-only-requires-proof" if turn_rate else "missing",
            "promotionReviewRequired": True,
            "promotionReview": "passed" if safe_mapping(promotion_review).get("reviewPassed") else "missing-or-not-passed",
            "proofPromotionPerformed": False,
        },
        "next": build_next_action(
            freshness,
            facing_target,
            camera_yaw,
            three_pose_gate,
            restart_survival,
            turn_forward,
            promotion_review,
        ),
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": errors,
        "sourceSafety": source_safety,
        "safety": {
            **safety_flags(),
            "readOnlyArtifactIndex": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
        },
        "artifacts": {},
    }
    return summary


def markdown_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return "`" + json.dumps(value, sort_keys=True) + "`"
    return f"`{value}`"


def build_markdown(summary: dict[str, Any]) -> str:
    candidates = safe_mapping(summary.get("candidates"))
    promoted = safe_mapping(candidates.get("promotedCoordinate"))
    facing = safe_mapping(candidates.get("candidateFacingTarget"))
    turn = safe_mapping(candidates.get("candidateTurnRate"))
    delta = safe_mapping(candidates.get("coordinateDeltaCandidate"))
    camera_yaw = safe_mapping(candidates.get("cameraYawClassification"))
    proof_gates = safe_mapping(summary.get("proofGates"))
    three_pose = safe_mapping(proof_gates.get("facingThreePoseGate"))
    restart = safe_mapping(proof_gates.get("facingRestartSurvival"))
    turn_forward = safe_mapping(proof_gates.get("turnForwardExperiment"))
    ghidra_static = safe_mapping(proof_gates.get("ghidraStaticEvidence"))
    promotion_review = safe_mapping(proof_gates.get("facingPromotionReadinessReview"))
    artifacts = safe_mapping(summary.get("artifacts"))
    freshness = safe_mapping(summary.get("freshness"))
    lines = [
        "# RiftReader Navigation Pointer Discovery Status",
        "",
        f"# **{'✅' if summary.get('status') == 'passed' else '⚠️' if summary.get('status') == 'blocked' else '❌'} {str(summary.get('status')).upper()}**",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Generated UTC | `{summary.get('generatedAtUtc')}` |",
        f"| Verdict | `{summary.get('verdict')}` |",
        f"| Target PID | `{safe_mapping(summary.get('target')).get('processId')}` |",
        f"| Target HWND | `{safe_mapping(summary.get('target')).get('targetWindowHandle')}` |",
        f"| Freshness | `{freshness.get('status')}` |",
        f"| Stale sources | `{', '.join(str(item) for item in freshness.get('staleSources') or []) or 'none'}` |",
        "",
        "## Candidate summary",
        "",
        "| Candidate | Status | Key evidence | Promotion state |",
        "|---|---|---|---|",
        f"| Coordinate `+0x320/+0x324/+0x328` | `{promoted.get('status')}` | `{promoted.get('chain')}` | `promoted={str(bool(promoted.get('promotionAllowed'))).lower()}` |",
        f"| Facing target `+0x30C/+0x310/+0x314` | `{facing.get('status')}` | `max yaw delta={facing.get('comparisonMaxAbsYawDeltaDegrees')}` | `candidate-only` |",
        f"| Turn rate `+0x304` | `{turn.get('status')}` | `latest={turn.get('latestValue')}` | `candidate-only` |",
        f"| Coordinate delta evidence | `{delta.get('status')}` | `tracking max abs={delta.get('trackingErrorMaxAbs')}` | `matches promoted={delta.get('matchesPromotedCoordinateAddress')}` |",
        f"| Camera/yaw classification | `{camera_yaw.get('status')}` | `{camera_yaw.get('classification')}` | `route-actionable={camera_yaw.get('actionableForRouteControl')}` |",
        f"| Facing three-pose gate | `{three_pose.get('status')}` | `poses={three_pose.get('passedPoseCount')}/{three_pose.get('poseCount')}; min progress={three_pose.get('minimumProgressDistance')}` | `candidate-only` |",
        f"| Facing restart survival | `{restart.get('status')}` | `survived={restart.get('restartRelogSurvived')}; offsets stable={restart.get('offsetsStable')}` | `candidate-only` |",
        f"| Turn-forward live progress | `{turn_forward.get('status')}` | `progress={turn_forward.get('totalProgressDistance')}; route={turn_forward.get('routeStatus')}` | `support-only` |",
        f"| Ghidra static pointer evidence | `{ghidra_static.get('status')}` | `root refs={ghidra_static.get('rootReferenceCountCaptured')}; root={ghidra_static.get('rootAddress')}` | `offline-only` |",
        f"| Facing promotion-readiness review | `{promotion_review.get('status')}` | `reviewPassed={promotion_review.get('reviewPassed')}` | `promotionAllowed={promotion_review.get('promotionAllowed')}; performed={promotion_review.get('promotionPerformed')}` |",
        "",
        "## Source artifacts",
        "",
        "| Source | Status | Freshness | Age seconds | Path |",
        "|---|---|---|---:|---|",
    ]
    for label, source in safe_mapping(summary.get("sources")).items():
        source_map = safe_mapping(source)
        source_freshness = safe_mapping(source_map.get("freshness"))
        lines.append(
            f"| `{label}` | `{source_map.get('status')}` | `{source_freshness.get('status')}` | "
            f"`{source_freshness.get('ageSeconds')}` | `{source_map.get('path')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{item}`" for item in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{item}`" for item in safe_list(summary.get("warnings")))
    if summary.get("errors"):
        lines.extend(["", "## Errors"])
        lines.extend(f"- `{item}`" for item in safe_list(summary.get("errors")))
    lines.extend(
        [
            "",
            "## Next action",
            "",
            str(safe_mapping(summary.get("next")).get("recommendedAction") or ""),
        ]
    )
    recommended_actions = safe_list(safe_mapping(summary.get("next")).get("recommendedActions"))
    if recommended_actions:
        lines.extend(["", "### Recommended action list", ""])
        lines.extend(f"- {item}" for item in recommended_actions)
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Summary JSON: `{artifacts.get('summaryJson')}`",
            f"- Summary Markdown: `{artifacts.get('summaryMarkdown')}`",
            "",
            "## Safety",
            "",
            "This helper indexes existing artifacts only. It performs no live input, movement, target memory read, debugger/CE attach, provider write, Git mutation, or proof promotion.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def resolve_output_dir(repo_root: Path, output_dir: Path) -> Path:
    return output_dir if output_dir.is_absolute() else repo_root / output_dir


def write_outputs(repo_root: Path, summary: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir = resolve_output_dir(repo_root, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "summary.json"
    md_path = output_dir / "summary.md"
    artifacts = {
        "runDirectory": repo_rel(repo_root, output_dir),
        "summaryJson": repo_rel(repo_root, json_path),
        "summaryMarkdown": repo_rel(repo_root, md_path),
    }
    summary["artifacts"] = artifacts
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown(summary), encoding="utf-8")
    return artifacts


def build_self_test() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="riftreader-nav-pointer-discovery-") as temp_name:
        root = Path(temp_name)
        (root / "docs" / "recovery").mkdir(parents=True)
        (root / "scripts" / "captures").mkdir(parents=True)
        (root / "docs" / "recovery" / "current-truth.json").write_text(
            json.dumps(
                {
                    "target": {"processName": "rift_x64", "processId": 1, "targetWindowHandle": "0x1"},
                    "staticChainStatus": {
                        "status": "promoted",
                        "promotionAllowed": True,
                        "primaryCandidate": {
                            "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                            "ownerAddress": "0x1000",
                            "coordinateAddress": "0x1320",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        nav_dir = root / "scripts" / "captures" / "static-owner-nav-state-20260531-000000-000000"
        nav_dir.mkdir()
        (nav_dir / "summary.json").write_text(
            json.dumps(
                {
                    "kind": "static-owner-nav-state-readback",
                    "status": "passed",
                    "generatedAtUtc": "2026-05-31T00:00:00Z",
                    "latestState": {
                        "ownerAddress": "0x1000",
                        "facingTargetOffset": "0x30C",
                        "turnRateOffset": "0x304",
                        "turnRate0x304": 0.0,
                    },
                }
            ),
            encoding="utf-8",
        )
        summary = build_navigation_pointer_discovery(root)
        checks.append({"name": "builds_summary", "pass": summary["status"] == "passed"})
        checks.append({"name": "keeps_facing_candidate_only", "pass": safe_mapping(summary["candidates"]["candidateFacingTarget"]).get("candidateOnly") is True})
        checks.append({"name": "no_live_action", "pass": summary["safety"]["inputSent"] is False and summary["safety"]["targetMemoryBytesRead"] is False})
    ok = all(item["pass"] for item in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-navigation-pointer-discovery-self-test",
        "toolVersion": TOOL_VERSION,
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {**safety_flags(), "readOnlyArtifactIndex": True, "proofPromotion": False},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    parser.add_argument("--write", action="store_true", help="Write ignored summary artifacts under .riftreader-local.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--self-test", action="store_true", help="Run fixture-only self-test.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            summary = build_self_test()
        else:
            repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
            summary = build_navigation_pointer_discovery(repo_root)
            if args.write:
                write_outputs(repo_root, summary, args.output_dir)
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(build_markdown(summary), end="")
        if summary.get("status") == "blocked":
            return 2
        return 0 if summary.get("status") == "passed" or summary.get("ok") is True else 1
    except (NavigationPointerDiscoveryError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        error = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-navigation-pointer-discovery-error",
            "toolVersion": TOOL_VERSION,
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "error": f"{type(exc).__name__}:{exc}",
            "safety": {**safety_flags(), "readOnlyArtifactIndex": True, "proofPromotion": False},
        }
        if args.json:
            print(json.dumps(error, indent=2, sort_keys=True), file=sys.stderr)
        else:
            print(error["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
