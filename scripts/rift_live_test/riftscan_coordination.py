from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RIFTSCAN_ROOT = Path(r"C:\RIFT MODDING\Riftscan")


def read_json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def utc_from_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip(), 0)
    except (TypeError, ValueError):
        return None


def normalize_hwnd(value: Any) -> str | None:
    parsed = coerce_int(value)
    if parsed is None:
        return None
    return f"0x{parsed:X}"


def get_nested(root: dict[str, Any], *names: str) -> Any:
    current: Any = root
    for name in names:
        if not isinstance(current, dict):
            return None
        current = current.get(name)
    return current


def first_present(root: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in root and root[name] not in (None, ""):
            return root[name]
    return None


def target_hint_process_id(path: Path, data: dict[str, Any] | None = None) -> int | None:
    if data:
        for value in (
            data.get("process_id"),
            data.get("processId"),
            data.get("ProcessId"),
            get_nested(data, "target", "processId"),
            get_nested(data, "target", "process_id"),
        ):
            parsed = coerce_int(value)
            if parsed is not None:
                return parsed

    match = re.search(r"(?:currentpid|pid)[-_]?(\d+)", path.name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def summarize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    source_base = first_present(candidate, "source_base_address_hex", "base_address_hex")
    source_offset = first_present(
        candidate,
        "source_offset_hex",
        "x_offset_hex",
        "offset_hex",
    )
    return {
        "candidateId": first_present(candidate, "candidate_id", "CandidateId"),
        "sourceRegionId": first_present(candidate, "source_region_id", "SourceRegionId"),
        "sourceBaseAddressHex": source_base,
        "sourceOffsetHex": source_offset,
        "sourceAbsoluteAddressHex": first_present(
            candidate,
            "source_absolute_address_hex",
            "absolute_address_hex",
        ),
        "axisOrder": first_present(candidate, "axis_order", "axisOrder"),
        "supportCount": coerce_int(first_present(candidate, "support_count", "supportCount")),
        "observationSupportCount": coerce_int(
            first_present(candidate, "observation_support_count", "observationSupportCount")
        ),
        "bestMaxAbsDistance": first_present(
            candidate,
            "best_max_abs_distance",
            "bestMaxAbsDistance",
        ),
        "bestMemory": {
            "x": first_present(candidate, "best_memory_x", "bestMemoryX"),
            "y": first_present(candidate, "best_memory_y", "bestMemoryY"),
            "z": first_present(candidate, "best_memory_z", "bestMemoryZ"),
        },
        "validationStatus": first_present(
            candidate,
            "validation_status",
            "validationStatus",
        ),
        "schemaSupported": bool(first_present(candidate, "candidate_id", "CandidateId"))
        and bool(source_base)
        and bool(source_offset),
    }


def summarize_match_file(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "lastWriteUtc": utc_from_mtime(path) if path.exists() else None,
        "status": "missing",
        "issues": [],
    }
    if not path.exists():
        item["issues"].append("match_file_missing")
        return item

    try:
        data = read_json_file(path)
    except Exception as exc:  # noqa: BLE001 - artifact inspection should report bad files.
        jsonl_candidates = read_candidate_jsonl_file(path)
        if not jsonl_candidates:
            item["status"] = "unreadable"
            item["issues"].append(f"match_file_unreadable:{type(exc).__name__}:{exc}")
            return item
        data = {
            "schemaVersion": "riftreader.api_family_vec3_candidate.jsonl",
            "mode": "riftreader-api-family-vec3-candidates-jsonl",
            "success": True,
            "candidate_count": len(jsonl_candidates),
            "candidates": jsonl_candidates,
        }
    else:
        single_candidate = summarize_candidate(data)
        if single_candidate.get("schemaSupported") and not isinstance(data.get("candidates"), list):
            data = {
                "schemaVersion": first_present(
                    data,
                    "result_schema_version",
                    "schema_version",
                    "schemaVersion",
                ),
                "mode": data.get("mode") or "riftreader-api-family-vec3-candidates-jsonl",
                "success": True,
                "process_id": first_present(
                    data,
                    "process_id",
                    "processId",
                    "ProcessId",
                ),
                "target_window_handle": first_present(
                    data,
                    "target_window_handle",
                    "targetWindowHandle",
                    "TargetWindowHandle",
                ),
                "candidate_count": 1,
                "candidates": [data],
            }

    candidates_raw = data.get("candidates")
    candidates = [
        summarize_candidate(candidate)
        for candidate in candidates_raw
        if isinstance(candidate, dict)
    ] if isinstance(candidates_raw, list) else []
    supported_candidates = [
        candidate for candidate in candidates if candidate.get("schemaSupported")
    ]
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
    reference_stability = data.get("referenceStability") if isinstance(data.get("referenceStability"), dict) else None
    truth_status = data.get("truthStatus") if isinstance(data.get("truthStatus"), dict) else None

    item.update(
        {
            "status": "ok" if supported_candidates else "no-supported-candidates",
            "schemaVersion": first_present(
                data,
                "result_schema_version",
                "schema_version",
                "schemaVersion",
            ),
            "mode": data.get("mode"),
            "success": data.get("success"),
            "processIdHint": target_hint_process_id(path, data),
            "sessionPath": data.get("session_path"),
            "truthSummaryPath": data.get("truth_summary_path"),
            "latestObservationUtc": data.get("latest_observation_utc"),
            "candidateCount": coerce_int(data.get("candidate_count")) or len(candidates),
            "matchCount": coerce_int(data.get("match_count")),
            "candidates": candidates,
            "warnings": [str(value) for value in warnings],
            "diagnostics": [str(value) for value in diagnostics],
            "sourceFamilySnapshot": data.get("sourceFamilySnapshot"),
            "referenceStability": reference_stability,
            "truthStatus": truth_status,
        }
    )
    if not supported_candidates:
        item["issues"].append("no_supported_candidate_schema")
    if supported_candidates and reference_stability:
        stability_status = str(reference_stability.get("status") or "").lower()
        within_tolerance = reference_stability.get("withinTolerance")
        if stability_status != "stable" or within_tolerance is False:
            item["status"] = "blocked-stale-reference"
            item["issues"].append(
                f"candidate_reference_stability_not_current:{stability_status or 'unknown'}"
            )
    return item


def read_candidate_jsonl_file(path: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                candidates.append(item)
    except Exception:  # noqa: BLE001 - caller preserves original JSON-object read error.
        return []
    return candidates


def same_path(left: Any, right: Any) -> bool:
    if not left or not right:
        return False
    try:
        return Path(str(left)).resolve() == Path(str(right)).resolve()
    except OSError:
        return str(left).lower() == str(right).lower()


def summarize_readback_proof(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "lastWriteUtc": utc_from_mtime(path) if path.exists() else None,
        "status": "missing",
        "issues": [],
    }
    if not path.exists():
        item["issues"].append("readback_proof_missing")
        return item

    try:
        data = read_json_file(path)
    except Exception as exc:  # noqa: BLE001 - artifact inspection should report bad files.
        item["status"] = "unreadable"
        item["issues"].append(f"readback_proof_unreadable:{type(exc).__name__}:{exc}")
        return item

    best_matches = data.get("BestReferenceMatches")
    if not isinstance(best_matches, list):
        best = data.get("BestReferenceMatch")
        best_matches = [best] if isinstance(best, dict) else []
    reference_match_count = coerce_int(data.get("ReferenceMatchCount")) or 0
    true_matches = [
        match
        for match in best_matches
        if isinstance(match, dict) and bool(match.get("ReferenceMatchesReadback"))
    ]
    stable_true_matches = [
        match
        for match in true_matches
        if bool(match.get("StableAcrossReadbackSamples"))
        and match.get("SourcePreviewMatchesReadback") is not False
    ]
    selected = (
        stable_true_matches[0]
        if stable_true_matches
        else (true_matches[0] if true_matches else (best_matches[0] if best_matches else {}))
    )
    if not isinstance(selected, dict):
        selected = {}
    status = (
        "reference-match"
        if reference_match_count > 0
        and bool(selected.get("ReferenceMatchesReadback"))
        and bool(selected.get("StableAcrossReadbackSamples"))
        and selected.get("SourcePreviewMatchesReadback") is not False
        else "reference-match-unstable"
        if reference_match_count > 0 and bool(selected.get("ReferenceMatchesReadback"))
        else "no-reference-match"
    )
    item.update(
        {
            "status": status,
            "processId": coerce_int(data.get("ProcessId")),
            "targetWindowHandle": normalize_hwnd(data.get("TargetWindowHandle")),
            "processName": data.get("ProcessName"),
            "sourceCandidateFile": data.get("SourceCandidateFile"),
            "referenceMatchCount": reference_match_count,
            "stableReferenceMatchCount": len(stable_true_matches),
            "stableDecodedCandidateCount": coerce_int(data.get("StableDecodedCandidateCount")),
            "proofAnchorStatus": data.get("ProofAnchorStatus"),
            "movementAllowed": bool(data.get("MovementAllowed")),
            "bestReferenceMatch": {
                "candidateId": selected.get("CandidateId"),
                "candidateAddressHex": selected.get("CandidateAddressHex"),
                "referenceMatchesReadback": bool(selected.get("ReferenceMatchesReadback")),
                "referenceMaxAbsDelta": selected.get("ReferenceMaxAbsDelta"),
                "referencePlanarDistance": selected.get("ReferencePlanarDistance"),
                "referenceSpatialDistance": selected.get("ReferenceSpatialDistance"),
                "stableAcrossReadbackSamples": selected.get("StableAcrossReadbackSamples"),
            },
        }
    )
    if status != "reference-match":
        item["issues"].append(
            "readback_proof_no_stable_reference_match"
            if status == "reference-match-unstable"
            else "readback_proof_no_reference_match"
        )
    return item


def find_riftreader_readback_proofs(
    repo_root: Path,
    process_id: int | None,
    target_window_handle: str | None,
    limit: int,
) -> list[Path]:
    captures = repo_root / "scripts" / "captures"
    if not captures.exists():
        return []
    files = sorted(
        captures.glob("riftscan-proof-pose-*/riftscan-riftreader-currentpid-*-readback-wrapper-summary-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    expected_hwnd = normalize_hwnd(target_window_handle)
    selected: list[Path] = []
    for path in files:
        try:
            data = read_json_file(path)
        except Exception:  # noqa: BLE001 - unreadable files are ignored during discovery.
            continue
        if process_id is not None and coerce_int(data.get("ProcessId")) != process_id:
            continue
        if expected_hwnd and normalize_hwnd(data.get("TargetWindowHandle")) != expected_hwnd:
            continue
        selected.append(path)
        if len(selected) >= max(1, limit):
            break
    return selected


def summarize_consumer_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    artifacts = candidate.get("source_artifacts")
    return {
        "stableId": candidate.get("stable_id"),
        "kind": candidate.get("kind"),
        "candidateId": candidate.get("candidate_id"),
        "source": candidate.get("source"),
        "state": candidate.get("state"),
        "claimLevel": candidate.get("claim_level"),
        "proofLevel": candidate.get("proof_level"),
        "consumerStatus": candidate.get("consumer_status"),
        "liveUseAuthorized": bool(candidate.get("live_use_authorized")),
        "sourceBaseAddressHex": candidate.get("source_base_address_hex"),
        "sourceOffsetHex": candidate.get("source_offset_hex"),
        "sourceAbsoluteAddressHex": candidate.get("source_absolute_address_hex"),
        "axisOrder": candidate.get("axis_order"),
        "supportCount": coerce_int(candidate.get("support_count")),
        "nextValidationStep": candidate.get("next_validation_step"),
        "forbiddenDownstreamUses": [
            str(value)
            for value in candidate.get("forbidden_downstream_uses", [])
            if value is not None
        ],
        "sourceArtifacts": [str(value) for value in artifacts] if isinstance(artifacts, list) else [],
    }


def summarize_candidate_consumer(path: Path, *, riftscan_root: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "status": "missing",
        "issues": [],
    }
    if not path.exists():
        summary["issues"].append("candidate_consumer_missing")
        return summary

    try:
        data = read_json_file(path)
    except Exception as exc:  # noqa: BLE001 - artifact inspection should report bad files.
        summary["status"] = "unreadable"
        summary["issues"].append(f"candidate_consumer_unreadable:{type(exc).__name__}:{exc}")
        return summary

    current_best = data.get("current_best_candidate")
    safe_candidates_raw = data.get("safe_candidates")
    current_best_summary = (
        summarize_consumer_candidate(current_best)
        if isinstance(current_best, dict)
        else None
    )
    safe_candidates = [
        summarize_consumer_candidate(candidate)
        for candidate in safe_candidates_raw
        if isinstance(candidate, dict)
    ] if isinstance(safe_candidates_raw, list) else []
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    forbidden = (
        data.get("forbidden_downstream_uses")
        if isinstance(data.get("forbidden_downstream_uses"), list)
        else []
    )
    artifact_age = data.get("artifact_age") if isinstance(data.get("artifact_age"), dict) else {}
    summary.update(
        {
            "status": str(data.get("status") or data.get("display_status") or "unknown").lower(),
            "schemaVersion": data.get("schema_version"),
            "createdUtc": data.get("created_utc"),
            "mode": data.get("mode"),
            "displayStatus": data.get("display_status"),
            "currentBestCandidate": current_best_summary,
            "safeCandidateCount": coerce_int(data.get("safe_candidate_count")),
            "safeCandidates": safe_candidates[:8],
            "allowedDownstreamUses": [
                str(value)
                for value in data.get("allowed_downstream_uses", [])
                if value is not None
            ],
            "forbiddenDownstreamUses": [str(value) for value in forbidden if value is not None],
            "safety": {
                "offlineOnly": bool(safety.get("offline_only")),
                "liveActionAuthorized": bool(safety.get("live_action_authorized")),
                "movementOrInputSent": bool(safety.get("movement_or_input_sent")),
                "processAttachOrMemoryReadStarted": bool(
                    safety.get("process_attach_or_memory_read_started")
                ),
            },
            "artifactAge": {
                "staleCount": coerce_int(artifact_age.get("stale_count")),
                "currentBestStaleCount": coerce_int(
                    artifact_age.get("current_best_stale_count")
                ),
            },
            "warnings": [str(value) for value in warnings],
            "riftscanRoot": str(riftscan_root),
        }
    )
    if current_best_summary and not current_best_summary.get("liveUseAuthorized"):
        summary["issues"].append("candidate_consumer_current_best_live_use_not_authorized")
    if summary["safety"].get("liveActionAuthorized"):
        summary["issues"].append("candidate_consumer_live_action_authorized_unexpected")
    return summary


def find_match_files(riftscan_root: Path, process_id: int | None, limit: int) -> list[Path]:
    reports = riftscan_root / "reports" / "generated"
    if not reports.exists():
        return []

    files = sorted(
        reports.glob("*addon-coordinate-matches.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if process_id is not None:
        pid_text = str(process_id)
        files = [
            path
            for path in files
            if re.search(rf"(?:currentpid|pid)[-_]?{re.escape(pid_text)}\b", path.name, re.IGNORECASE)
        ]
    return files[:limit]


def find_riftreader_candidate_files(repo_root: Path, process_id: int | None, limit: int) -> list[Path]:
    captures = repo_root / "scripts" / "captures"
    if not captures.exists():
        return []
    discovered: dict[Path, Path] = {}
    for pattern in (
        "coordinate-family-snapshot-currentpid-*/family-import-candidates.json",
        "same-target-candidate-synth-*/same-target-candidates.json",
    ):
        for path in captures.glob(pattern):
            if path.is_file():
                discovered[path.resolve()] = path
    files = sorted(discovered.values(), key=lambda path: path.stat().st_mtime, reverse=True)
    if process_id is not None:
        selected: list[Path] = []
        for path in files:
            try:
                data = read_json_file(path)
            except Exception:  # noqa: BLE001 - unreadable files are ignored during discovery.
                continue
            if target_hint_process_id(path, data) == process_id:
                selected.append(path)
        files = selected
    return files[:limit]


def load_current_pointer(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"current_proof_pointer_missing:{path}"]
    try:
        return read_json_file(path), []
    except Exception as exc:  # noqa: BLE001 - report bad artifact.
        return None, [f"current_proof_pointer_unreadable:{type(exc).__name__}:{exc}"]


def summarize_pointer(path: Path) -> tuple[dict[str, Any], list[str]]:
    pointer, issues = load_current_pointer(path)
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "target": {},
        "candidateSource": {},
    }
    if not pointer:
        return summary, issues

    target = pointer.get("target") if isinstance(pointer.get("target"), dict) else {}
    source = (
        pointer.get("riftscanCandidateSource")
        if isinstance(pointer.get("riftscanCandidateSource"), dict)
        else {}
    )
    summary.update(
        {
            "schemaVersion": pointer.get("schemaVersion"),
            "mode": pointer.get("mode"),
            "status": pointer.get("status"),
            "lastUpdatedUtc": pointer.get("lastUpdatedUtc"),
            "target": {
                "processName": target.get("processName"),
                "processId": coerce_int(target.get("processId")),
                "targetWindowHandle": normalize_hwnd(target.get("targetWindowHandle")),
            },
            "candidateSource": {
                "riftScanRoot": source.get("riftScanRoot"),
                "matchFile": source.get("matchFile"),
                "candidateId": source.get("candidateId"),
                "sourceBaseAddressHex": source.get("sourceBaseAddressHex"),
                "sourceOffsetHex": source.get("sourceOffsetHex"),
                "sourceAbsoluteAddressHex": source.get("sourceAbsoluteAddressHex"),
                "supportCount": coerce_int(source.get("supportCount")),
                "bestMaxAbsDistance": source.get("bestMaxAbsDistance"),
            },
        }
    )
    if not summary["candidateSource"].get("matchFile"):
        issues.append("current_proof_pointer_missing_riftscan_match_file")
    if not summary["candidateSource"].get("candidateId"):
        issues.append("current_proof_pointer_missing_candidate_id")
    return summary, issues


def target_issues(
    pointer_summary: dict[str, Any],
    *,
    process_id: int | None,
    hwnd: str | None,
    process_name: str | None,
) -> list[str]:
    issues: list[str] = []
    target = pointer_summary.get("target")
    if not isinstance(target, dict):
        return issues
    pointer_pid = coerce_int(target.get("processId"))
    if process_id is not None and pointer_pid is not None and pointer_pid != process_id:
        issues.append(f"pointer_pid_mismatch:actual={pointer_pid};expected={process_id}")

    pointer_hwnd = normalize_hwnd(target.get("targetWindowHandle"))
    expected_hwnd = normalize_hwnd(hwnd)
    if expected_hwnd and pointer_hwnd and pointer_hwnd.lower() != expected_hwnd.lower():
        issues.append(f"pointer_hwnd_mismatch:actual={pointer_hwnd};expected={expected_hwnd}")

    pointer_process_name = target.get("processName")
    if process_name and pointer_process_name:
        actual = str(pointer_process_name).removesuffix(".exe").lower()
        expected = str(process_name).removesuffix(".exe").lower()
        if actual != expected:
            issues.append(
                f"pointer_process_name_mismatch:actual={actual};expected={expected}"
            )
    return issues


def choose_candidate(
    *,
    pointer_summary: dict[str, Any],
    pointer_match_summary: dict[str, Any] | None,
    latest_matches: list[dict[str, Any]],
    latest_riftreader_candidates: list[dict[str, Any]],
    latest_riftreader_readback_proofs: list[dict[str, Any]],
    target_has_mismatch: bool,
) -> dict[str, Any]:
    rejected_riftreader_candidates: list[dict[str, Any]] = []
    source = pointer_summary.get("candidateSource")
    pointer_candidate_id = source.get("candidateId") if isinstance(source, dict) else None
    pointer_match_ok = bool(
        pointer_match_summary
        and pointer_match_summary.get("status") == "ok"
        and any(
            candidate.get("candidateId") == pointer_candidate_id
            for candidate in pointer_match_summary.get("candidates", [])
            if isinstance(candidate, dict)
        )
    )
    if pointer_match_ok and not target_has_mismatch:
        return {
            "source": "current-proof-pointer",
            "candidateFile": pointer_match_summary["path"],
            "candidateId": pointer_candidate_id,
            "recommendedAction": "use-existing-pointer-candidate-with-fresh-proof",
            "why": "The current RiftReader proof pointer references an existing candidate file with the expected schema for the requested target.",
        }

    for match in latest_matches:
        candidates = [
            candidate
            for candidate in match.get("candidates", [])
            if isinstance(candidate, dict) and candidate.get("schemaSupported")
        ]
        if candidates:
            return {
                "source": "latest-riftscan-match-file",
                "candidateFile": match["path"],
                "candidateId": candidates[0].get("candidateId"),
                "recommendedAction": "use-existing-riftscan-candidate-file-read-only",
                "why": "The proof pointer is missing or mismatched, but a same-PID RiftScan match file already exists and can be consumed read-only by RiftReader.",
            }

    for match in latest_riftreader_candidates:
        candidates = [
            candidate
            for candidate in match.get("candidates", [])
            if isinstance(candidate, dict) and candidate.get("schemaSupported")
        ]
        if candidates:
            is_family_import = (
                str(match.get("mode") or "") == "riftreader-current-pid-coordinate-family-import-candidates"
                or str(match.get("path") or "").endswith("family-import-candidates.json")
            )
            if match.get("status") != "ok":
                rejected_riftreader_candidates.append(
                    {
                        "candidateFile": match.get("path"),
                        "source": (
                            "latest-riftreader-family-import-candidate-file"
                            if is_family_import
                            else "latest-riftreader-same-target-candidate-file"
                        ),
                        "status": match.get("status"),
                        "issues": match.get("issues", []),
                        "reason": "candidate-file-failed-currentness-gates",
                    }
                )
                continue

            proofs_for_match = [
                item
                for item in latest_riftreader_readback_proofs
                if same_path(item.get("sourceCandidateFile"), match.get("path"))
            ]
            latest_proof = proofs_for_match[0] if proofs_for_match else None
            if latest_proof and latest_proof.get("status") != "reference-match":
                rejected_riftreader_candidates.append(
                    {
                        "candidateFile": match.get("path"),
                        "source": (
                            "latest-riftreader-family-import-candidate-file"
                            if is_family_import
                            else "latest-riftreader-same-target-candidate-file"
                        ),
                        "status": "latest-readback-no-reference-match",
                        "proofPath": latest_proof.get("path"),
                        "issues": latest_proof.get("issues", []),
                        "reason": "latest-readback-did-not-match-current-reference",
                    }
                )
                continue

            proof = (
                latest_proof
                if latest_proof
                and latest_proof.get("status") == "reference-match"
                and latest_proof.get("bestReferenceMatch", {}).get("candidateId")
                else None
            )
            proof_candidate_id = (
                proof.get("bestReferenceMatch", {}).get("candidateId")
                if isinstance(proof, dict)
                else None
            )
            selected_candidate = next(
                (
                    candidate
                    for candidate in candidates
                    if proof_candidate_id and candidate.get("candidateId") == proof_candidate_id
                ),
                candidates[0],
            )
            return {
                "source": (
                    "latest-riftreader-family-import-candidate-file"
                    if is_family_import
                    else "latest-riftreader-same-target-candidate-file"
                ),
                "candidateFile": match["path"],
                "candidateId": selected_candidate.get("candidateId"),
                "proofEvidence": {
                    "source": "latest-readback-reference-match",
                    "path": proof.get("path"),
                    "candidateId": proof_candidate_id,
                    "candidateAddressHex": proof.get("bestReferenceMatch", {}).get("candidateAddressHex"),
                    "referenceMaxAbsDelta": proof.get("bestReferenceMatch", {}).get("referenceMaxAbsDelta"),
                    "referenceMatchCount": proof.get("referenceMatchCount"),
                } if isinstance(proof, dict) else None,
                "recommendedAction": (
                    "use-riftreader-family-import-candidate-file-read-only"
                    if is_family_import
                    else "use-riftreader-same-target-candidate-file-read-only"
                ),
                "why": (
                    "RiftReader exported a current-PID family snapshot candidate file from broad grouped scanning; it is candidate-only and must be used only through explicit read-only proof/readback."
                    if is_family_import
                    else "RiftReader synthesized a same-target current-PID candidate file from existing readback evidence; it is candidate-only and must be used only through explicit read-only proof/readback."
                ),
            }

    return {
        "source": "none",
        "candidateFile": None,
        "candidateId": None,
        "rejectedCandidateFiles": rejected_riftreader_candidates[:10],
        "issues": ["riftreader_candidates_rejected_by_freshness_gates"] if rejected_riftreader_candidates else [],
        "recommendedAction": "block-until-riftscan-candidate-exists-or-write-is-authorized",
        "why": (
            "Existing RiftReader candidate files were rejected by freshness/readback gates; do not consume stale snapshots."
            if rejected_riftreader_candidates
            else "No existing supported RiftScan coordinate match artifact is available for the requested target. Do not create RiftScan sessions/reports while RiftScan is read-only."
        ),
    }


def build_coordination_plan(
    *,
    repo_root: Path,
    riftscan_root: Path,
    current_proof_pointer: Path,
    candidate_consumer_summary: Path | None = None,
    process_id: int | None = None,
    target_window_handle: str | None = None,
    process_name: str | None = "rift_x64",
    limit: int = 8,
) -> dict[str, Any]:
    pointer_summary, pointer_issues = summarize_pointer(current_proof_pointer)
    issues = list(pointer_issues)
    issues.extend(
        target_issues(
            pointer_summary,
            process_id=process_id,
            hwnd=target_window_handle,
            process_name=process_name,
        )
    )
    target_has_mismatch = any(issue.startswith("pointer_") for issue in issues)

    pointer_match_summary = None
    source = pointer_summary.get("candidateSource")
    pointer_match_file = source.get("matchFile") if isinstance(source, dict) else None
    if pointer_match_file:
        pointer_match_summary = summarize_match_file(Path(str(pointer_match_file)))
        issues.extend(str(issue) for issue in pointer_match_summary.get("issues", []))

    consumer_path = candidate_consumer_summary or (
        riftscan_root
        / "handoffs"
        / "current"
        / "candidate-ledger-consumer"
        / "candidate-ledger-consumer-summary.json"
    )
    consumer_summary = summarize_candidate_consumer(consumer_path, riftscan_root=riftscan_root)
    # Keep provider "offline/live-use" warnings visible, but do not make a
    # RiftReader current-proof pointer unusable solely because the provider
    # consumer is intentionally offline-only.
    issues.extend(
        str(issue)
        for issue in consumer_summary.get("issues", [])
        if not str(issue).endswith("_live_use_not_authorized")
    )

    current_pid = process_id
    if current_pid is None:
        current_pid = coerce_int(get_nested(pointer_summary, "target", "processId"))
    latest_matches = [
        summarize_match_file(path)
        for path in find_match_files(riftscan_root, current_pid, max(1, limit))
    ]
    latest_riftreader_candidates = [
        summarize_match_file(path)
        for path in find_riftreader_candidate_files(repo_root, current_pid, max(1, limit))
    ]
    latest_riftreader_readback_proofs = [
        summarize_readback_proof(path)
        for path in find_riftreader_readback_proofs(
            repo_root,
            current_pid,
            target_window_handle,
            max(1, limit),
        )
    ]
    if not latest_matches and not pointer_match_summary and not latest_riftreader_candidates:
        issues.append(f"no_riftscan_match_files_found:{riftscan_root}")

    selection = choose_candidate(
        pointer_summary=pointer_summary,
        pointer_match_summary=pointer_match_summary,
        latest_matches=latest_matches,
        latest_riftreader_candidates=latest_riftreader_candidates,
        latest_riftreader_readback_proofs=latest_riftreader_readback_proofs,
        target_has_mismatch=target_has_mismatch,
    )
    issues.extend(str(issue) for issue in selection.get("issues", []) if issue)
    coordination_notes = build_coordination_notes(
        pointer_summary=pointer_summary,
        consumer_summary=consumer_summary,
        selection=selection,
    )
    status = "ok"
    if selection["candidateFile"] is None:
        status = "blocked"
    elif target_has_mismatch:
        status = "needs-review"

    return {
        "schemaVersion": 1,
        "mode": "riftscan-riftreader-readonly-coordination-plan",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "issues": issues,
        "repoRoot": str(repo_root),
        "riftScanBoundary": {
            "root": str(riftscan_root),
            "mode": "read-only",
            "writeAllowed": False,
            "noCheatEngine": True,
            "movementSent": False,
        },
        "requestedTarget": {
            "processName": process_name,
            "processId": process_id,
            "targetWindowHandle": normalize_hwnd(target_window_handle),
        },
        "currentProofPointer": pointer_summary,
        "riftScanCandidateConsumer": consumer_summary,
        "pointerMatchFile": pointer_match_summary,
        "latestRiftScanMatchFiles": latest_matches,
        "latestRiftReaderCandidateFiles": latest_riftreader_candidates,
        "latestRiftReaderReadbackProofs": latest_riftreader_readback_proofs,
        "selectedCandidate": selection,
        "coordinationNotes": coordination_notes,
        "nextCommands": build_next_commands(
            repo_root=repo_root,
            process_id=process_id or current_pid,
            target_window_handle=target_window_handle
            or get_nested(pointer_summary, "target", "targetWindowHandle"),
            process_name=process_name or get_nested(pointer_summary, "target", "processName") or "rift_x64",
            selection=selection,
        ),
        "majorMilestoneReview": [
            "Re-check exact PID/HWND before live action.",
            "Keep RiftScan read-only unless the user explicitly authorizes writes to that repo.",
            "Prefer the existing current-proof pointer matchFile or newest same-PID RiftScan match file over broad RiftReader heuristic scans.",
            "Run fresh ProofOnly/preflight before movement because proof anchors are age-limited.",
            "Keep auto-turn blocked until a promoted turn backend exists.",
            "Re-run this coordination plan after every handoff/commit/push milestone before expanding live discovery scope.",
        ],
    }


def build_coordination_notes(
    *,
    pointer_summary: dict[str, Any],
    consumer_summary: dict[str, Any],
    selection: dict[str, Any],
) -> list[str]:
    notes = [
        "RiftScan is a provider/reference surface here; this plan does not modify it.",
        "Provider candidate consumer rows marked liveUseAuthorized=false remain offline evidence, not movement permission.",
    ]
    source = pointer_summary.get("candidateSource")
    pointer_address = source.get("sourceAbsoluteAddressHex") if isinstance(source, dict) else None
    current_best = consumer_summary.get("currentBestCandidate")
    consumer_address = (
        current_best.get("sourceAbsoluteAddressHex")
        if isinstance(current_best, dict)
        else None
    )
    if pointer_address and consumer_address and str(pointer_address).lower() != str(consumer_address).lower():
        notes.append(
            "Current RiftReader proof pointer address differs from RiftScan's offline candidate-consumer current best; prefer the current-proof pointer for this RiftReader target, but preserve the provider drift note for review."
        )
    if selection.get("source") == "latest-riftscan-match-file":
        notes.append(
            "A latest same-PID match file was selected only as read-only candidate evidence; it still needs RiftReader proof-pose/readback before promotion."
        )
    elif selection.get("source") == "latest-riftreader-family-import-candidate-file":
        notes.append(
            "A latest RiftReader family snapshot import candidate file was selected from grouped current-PID scanning; it still needs proof-pose/readback and static/root provenance before promotion."
        )
    return notes


def build_next_commands(
    *,
    repo_root: Path,
    process_id: int | None,
    target_window_handle: str | None,
    process_name: str,
    selection: dict[str, Any],
) -> dict[str, Any]:
    commands: dict[str, Any] = {
        "writesToRiftScan": False,
        "notes": [
            "Commands are shown as argument arrays to avoid shell-string ambiguity.",
            "Do not run invoke-riftscan-coordinate-readback.ps1 without -CandidateFile while RiftScan is read-only; that path creates a RiftScan capture/session.",
        ],
    }
    if process_id and target_window_handle:
        commands["freshProofOnly"] = [
            "python",
            str(repo_root / "scripts" / "live_test.py"),
            "--profile",
            "ProofOnly",
            "--pid",
            str(process_id),
            "--hwnd",
            normalize_hwnd(target_window_handle) or str(target_window_handle),
            "--process-name",
            process_name,
        ]
    candidate_file = selection.get("candidateFile")
    candidate_id = selection.get("candidateId")
    if process_id and target_window_handle and candidate_file:
        commands["readOnlyProofPose"] = [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / "scripts" / "capture-riftscan-proof-pose.ps1"),
            "-CandidateFile",
            str(candidate_file),
            "-ProcessId",
            str(process_id),
            "-TargetWindowHandle",
            normalize_hwnd(target_window_handle) or str(target_window_handle),
            "-ProcessName",
            process_name,
            "-Json",
        ]
    if process_id and target_window_handle and candidate_file and candidate_id:
        commands["readOnlyCandidateReadback"] = [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / "scripts" / "invoke-riftscan-coordinate-readback.ps1"),
            "-CandidateFile",
            str(candidate_file),
            "-ProcessId",
            str(process_id),
            "-TargetWindowHandle",
            normalize_hwnd(target_window_handle) or str(target_window_handle),
            "-ProcessName",
            process_name,
            "-Json",
        ]
    return commands


def write_plan(plan: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    if is_relative_to(output_file, riftscan_root):
        raise ValueError(f"Refusing to write coordination output inside RiftScan: {output_file}")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")


def default_summary_file(repo_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / "scripts" / "captures" / f"riftscan-coordination-plan-{stamp}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a read-only RiftScan -> RiftReader coordination plan."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="RiftReader repo root.",
    )
    parser.add_argument(
        "--riftscan-root",
        type=Path,
        default=DEFAULT_RIFTSCAN_ROOT,
        help="RiftScan provider repo root. This tool reads it but never writes it.",
    )
    parser.add_argument(
        "--current-proof-pointer",
        type=Path,
        help="Current proof pointer JSON. Defaults to docs/recovery/current-proof-anchor-readback.json.",
    )
    parser.add_argument(
        "--candidate-consumer-summary",
        type=Path,
        help="RiftScan candidate-ledger consumer summary. Defaults to the provider current handoff path.",
    )
    parser.add_argument("--pid", type=int, help="Expected current RIFT process id.")
    parser.add_argument("--hwnd", help="Expected current RIFT window handle.")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Write the coordination plan under RiftReader scripts/captures.",
    )
    parser.add_argument("--summary-file", type=Path, help="Explicit summary output file.")
    parser.add_argument(
        "--compact-json",
        action="store_true",
        help="Emit a single-line JSON object to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    riftscan_root = args.riftscan_root.resolve()
    pointer = args.current_proof_pointer or (
        repo_root / "docs" / "recovery" / "current-proof-anchor-readback.json"
    )
    plan = build_coordination_plan(
        repo_root=repo_root,
        riftscan_root=riftscan_root,
        current_proof_pointer=pointer,
        candidate_consumer_summary=args.candidate_consumer_summary,
        process_id=args.pid,
        target_window_handle=args.hwnd,
        process_name=args.process_name,
        limit=args.limit,
    )
    if args.write_summary or args.summary_file:
        output_file = args.summary_file or default_summary_file(repo_root)
        plan["summaryFile"] = str(output_file)
        write_plan(plan, output_file, riftscan_root=riftscan_root)

    if args.compact_json:
        print(json.dumps(plan, separators=(",", ":")))
    else:
        print(json.dumps(plan, indent=2))
    return 0 if plan["status"] in {"ok", "needs-review"} else 2


if __name__ == "__main__":
    sys.exit(main())
