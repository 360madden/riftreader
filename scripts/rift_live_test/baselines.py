from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip(), 0)
    except (TypeError, ValueError):
        return None


def normalize_process_name(value: str) -> str:
    text = str(value).strip()
    if text.lower().endswith(".exe"):
        return text[:-4]
    return text


def read_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def get_reference_coordinate(summary: dict[str, Any]) -> dict[str, float] | None:
    reference = summary.get("ReferenceCoordinate")
    if not isinstance(reference, dict):
        return None
    try:
        return {
            "x": float(reference["X"]),
            "y": float(reference["Y"]),
            "z": float(reference["Z"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def reference_planar_distance(a: dict[str, float], b: dict[str, float]) -> float:
    delta_x = float(b["x"]) - float(a["x"])
    delta_z = float(b["z"]) - float(a["z"])
    return math.sqrt((delta_x * delta_x) + (delta_z * delta_z))


def summary_target_issues(
    summary: dict[str, Any],
    *,
    process_id: int,
    target_window_handle: str,
    process_name: str,
) -> list[str]:
    issues: list[str] = []
    actual_pid = coerce_int(summary.get("ProcessId"))
    if actual_pid is None or actual_pid != int(process_id):
        issues.append(f"pid_mismatch:actual={actual_pid};expected={process_id}")

    actual_process_name = summary.get("ProcessName")
    if actual_process_name:
        expected = normalize_process_name(process_name)
        actual = normalize_process_name(str(actual_process_name))
        if actual.lower() != expected.lower():
            issues.append(f"process_name_mismatch:actual={actual};expected={expected}")

    actual_hwnd = coerce_int(summary.get("TargetWindowHandle"))
    expected_hwnd = coerce_int(target_window_handle)
    if actual_hwnd is not None and expected_hwnd is not None and actual_hwnd != expected_hwnd:
        issues.append(f"hwnd_mismatch:actual=0x{actual_hwnd:X};expected=0x{expected_hwnd:X}")

    return issues


def summary_candidate_issues(summary: dict[str, Any], *, candidate_id: str) -> list[str]:
    issues: list[str] = []
    if not bool(summary.get("NoCheatEngine")):
        issues.append("no_cheat_engine_not_true")
    if bool(summary.get("MovementSent")):
        issues.append("movement_sent_true")
    if get_reference_coordinate(summary) is None:
        issues.append("reference_coordinate_missing")

    matches = summary.get("BestReferenceMatches")
    if not isinstance(matches, list):
        issues.append("best_reference_matches_missing")
        return issues

    selected = None
    for match in matches:
        if isinstance(match, dict) and str(match.get("CandidateId")) == candidate_id:
            selected = match
            break
    if not selected:
        issues.append(f"candidate_not_found:{candidate_id}")
        return issues
    if not bool(selected.get("ReferenceMatchesReadback")):
        issues.append("candidate_reference_does_not_match_readback")
    if not bool(selected.get("StableAcrossReadbackSamples")):
        issues.append("candidate_not_stable")
    return issues


def summary_is_compatible(
    summary: dict[str, Any],
    *,
    process_id: int,
    target_window_handle: str,
    process_name: str,
    candidate_id: str,
) -> tuple[bool, list[str]]:
    issues = summary_target_issues(
        summary,
        process_id=process_id,
        target_window_handle=target_window_handle,
        process_name=process_name,
    )
    issues.extend(summary_candidate_issues(summary, candidate_id=candidate_id))
    return not issues, issues


def issues_are_target_epoch_only(issues: list[str]) -> bool:
    if not issues:
        return False
    target_prefixes = ("pid_mismatch:", "hwnd_mismatch:", "process_name_mismatch:")
    return all(any(issue.startswith(prefix) for prefix in target_prefixes) for issue in issues)


def load_pool_entries(pool_file: Path) -> list[dict[str, Any]]:
    if not pool_file.exists():
        return []
    data = read_json_file(pool_file)
    entries = data.get("entries")
    return entries if isinstance(entries, list) else []


def collect_candidate_paths(
    *,
    configured_summary: str | None,
    pool_file: Path,
    proof_anchor_file: Path,
) -> list[str]:
    paths: list[str] = []
    if configured_summary:
        paths.append(str(configured_summary))

    for entry in load_pool_entries(pool_file):
        if isinstance(entry, dict) and entry.get("summaryFile"):
            paths.append(str(entry["summaryFile"]))

    if proof_anchor_file.exists():
        try:
            anchor = read_json_file(proof_anchor_file)
        except Exception:  # noqa: BLE001 - corrupt anchor should not break pool discovery.
            anchor = {}
        evidence = anchor.get("Evidence")
        files = evidence.get("ReadbackSummaryFiles") if isinstance(evidence, dict) else None
        if isinstance(files, list):
            paths.extend(str(path) for path in files if path)

    unique: list[str] = []
    seen: set[str] = set()
    for value in paths:
        full = str(Path(value).resolve())
        key = full.lower()
        if key not in seen:
            seen.add(key)
            unique.append(full)
    return unique


def select_baselines_for_fresh_summary(
    *,
    fresh_summary_file: Path,
    candidate_paths: list[str],
    process_id: int,
    target_window_handle: str,
    process_name: str,
    candidate_id: str,
    min_reference_displacement: float,
    max_count: int,
) -> tuple[list[str], dict[str, Any]]:
    fresh = read_json_file(fresh_summary_file)
    fresh_reference = get_reference_coordinate(fresh)
    if fresh_reference is None:
        return [], {
            "status": "fresh-reference-missing",
            "freshSummaryFile": str(fresh_summary_file),
            "selected": [],
            "candidates": [],
        }

    candidates: list[dict[str, Any]] = []
    fresh_key = str(fresh_summary_file.resolve()).lower()
    for path_value in candidate_paths:
        path = Path(path_value)
        item: dict[str, Any] = {"summaryFile": str(path)}
        if str(path.resolve()).lower() == fresh_key:
            item["status"] = "skipped-fresh-summary"
            candidates.append(item)
            continue
        if not path.exists():
            item["status"] = "missing"
            candidates.append(item)
            continue
        try:
            summary = read_json_file(path)
        except Exception as exc:  # noqa: BLE001 - keep bad artifact diagnostic.
            item["status"] = "unreadable"
            item["issues"] = [f"{type(exc).__name__}:{exc}"]
            candidates.append(item)
            continue

        compatible, issues = summary_is_compatible(
            summary,
            process_id=process_id,
            target_window_handle=target_window_handle,
            process_name=process_name,
            candidate_id=candidate_id,
        )
        if not compatible:
            if issues_are_target_epoch_only(issues):
                item["status"] = "historical-target-mismatch"
                item["reusePolicy"] = (
                    "preserve-as-historical-evidence-only; do not use for "
                    "current-process promotion unless reacquired and rescored"
                )
            else:
                item["status"] = "incompatible"
            item["issues"] = issues
            candidates.append(item)
            continue

        reference = get_reference_coordinate(summary)
        if reference is None:
            item["status"] = "incompatible"
            item["issues"] = ["reference_coordinate_missing"]
            candidates.append(item)
            continue

        distance = reference_planar_distance(reference, fresh_reference)
        item.update(
            {
                "status": "compatible",
                "generatedAtUtc": summary.get("GeneratedAtUtc"),
                "referencePlanarDistanceFromFresh": distance,
            }
        )
        candidates.append(item)

    compatible_candidates = [
        item
        for item in candidates
        if item.get("status") == "compatible"
        and float(item.get("referencePlanarDistanceFromFresh", 0.0)) >= min_reference_displacement
    ]
    compatible_candidates.sort(
        key=lambda item: float(item.get("referencePlanarDistanceFromFresh", 0.0)),
        reverse=True,
    )
    selected_candidates = compatible_candidates[: max(1, max_count - 1)]
    selected = [str(Path(item["summaryFile"]).resolve()) for item in selected_candidates]
    if selected:
        selected.append(str(fresh_summary_file.resolve()))

    return selected, {
        "status": "selected" if selected else "no-compatible-displaced-baseline",
        "freshSummaryFile": str(fresh_summary_file),
        "minReferenceDisplacement": min_reference_displacement,
        "selected": selected,
        "candidateCount": len(candidates),
        "compatibleDisplacedCount": len(compatible_candidates),
        "candidates": candidates,
    }


def record_baseline_summary(
    *,
    pool_file: Path,
    summary_file: Path,
    source: str,
) -> dict[str, Any]:
    summary = read_json_file(summary_file)
    reference = get_reference_coordinate(summary)
    matches = summary.get("BestReferenceMatches") if isinstance(summary, dict) else None
    candidate_id = None
    if isinstance(matches, list) and matches:
        first = matches[0]
        if isinstance(first, dict):
            candidate_id = first.get("CandidateId")

    entries = load_pool_entries(pool_file)
    resolved = str(summary_file.resolve())
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "summaryFile": resolved,
        "source": source,
        "addedAtUtc": now,
        "generatedAtUtc": summary.get("GeneratedAtUtc"),
        "processName": summary.get("ProcessName"),
        "processId": summary.get("ProcessId"),
        "targetWindowHandle": summary.get("TargetWindowHandle"),
        "candidateId": candidate_id,
        "referenceCoordinate": reference,
        "noCheatEngine": bool(summary.get("NoCheatEngine")),
        "movementSent": bool(summary.get("MovementSent")),
    }

    kept = [
        item
        for item in entries
        if isinstance(item, dict)
        and str(Path(str(item.get("summaryFile", ""))).resolve()).lower() != resolved.lower()
    ]
    kept.append(entry)
    data = {
        "schemaVersion": 1,
        "mode": "live-test-promotion-baseline-pool",
        "updatedAtUtc": now,
        "entries": kept[-50:],
    }
    pool_file.parent.mkdir(parents=True, exist_ok=True)
    pool_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return entry
