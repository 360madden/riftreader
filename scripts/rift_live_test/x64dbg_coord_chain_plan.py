from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_snapshot_diff import BLOCKED_OPERATIONS, SOURCE_LINKS, int_hex
from .x64dbg_safety import (
    DEFAULT_MAX_GO_ATTEMPTS,
    DEFAULT_MAX_LIVE_ATTACH_SECONDS,
    DEFAULT_UNRESPONSIVE_ABORT_SECONDS,
    live_attach_policy,
    validate_live_attach_policy,
)


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_WATCH_SIZE = 12
DEFAULT_POSE_COUNT = 3
DEFAULT_CANDIDATE_ID = "x64dbg-coord-chain-candidate-000001"
SYNTHETIC_SELF_TEST_CANDIDATE_ADDRESS = 0x111122223333
PREFLIGHT_SUMMARY_KIND = "x64dbg-target-preflight"
PREFLIGHT_SUMMARY_LATEST_ALIAS = "latest"
API_COORDINATE_FILE_LATEST_ALIAS = "latest"
FLOAT_MATCH_TOLERANCE = 0.000001
STRICT_DEFAULT_MAX_PREFLIGHT_AGE_SECONDS = 300
STRICT_DEFAULT_MAX_API_COORDINATE_AGE_SECONDS = 60


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_int(value: str) -> int:
    return int(value, 0)


def normalize_hwnd(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return f"0x{int(value, 0):X}"
    except ValueError:
        return value.strip()


def normalize_hex_int(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        return int_hex(int(value, 0) if isinstance(value, str) else int(value))
    except (TypeError, ValueError):
        return str(value).strip()


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def get_mapping_value(document: dict[str, Any], *names: str) -> Any:
    for expected in names:
        for key, value in document.items():
            if str(key).lower() == expected.lower():
                return value
    return None


def get_nested_mapping_value(document: dict[str, Any], *path: str) -> Any:
    current: Any = document
    for segment in path:
        if not isinstance(current, dict):
            return None
        current = get_mapping_value(current, segment)
        if current is None:
            return None
    return current


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(str(value), 0)
        except (TypeError, ValueError):
            return None


def bool_is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def floats_match(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= FLOAT_MATCH_TOLERANCE


def extract_coordinate_mapping(document: dict[str, Any]) -> dict[str, Any] | None:
    coordinate = get_mapping_value(document, "coordinate", "Coordinate")
    if isinstance(coordinate, dict):
        return coordinate
    player_position = get_nested_mapping_value(document, "player", "position")
    if isinstance(player_position, dict):
        return player_position
    truth_player_position = get_nested_mapping_value(document, "truthSurface", "player", "position")
    if isinstance(truth_player_position, dict):
        return truth_player_position
    if all(get_mapping_value(document, axis) is not None for axis in ("x", "y", "z")):
        return document
    return None


def extract_api_coordinate_document(document: dict[str, Any]) -> dict[str, Any]:
    coordinate = extract_coordinate_mapping(document) or {}
    contract = get_mapping_value(document, "contract", "Contract")
    source = (
        get_mapping_value(document, "source", "Source", "Mode", "sourceView", "SourceView")
        or (get_mapping_value(contract, "name", "Name") if isinstance(contract, dict) else None)
        or get_mapping_value(document, "artifactKind", "ArtifactKind")
        or "api-coordinate-file"
    )
    return {
        "source": source,
        "status": get_mapping_value(document, "status", "Status"),
        "referenceFile": get_mapping_value(document, "referenceFile", "ReferenceFile"),
        "sampledAtUtc": get_mapping_value(
            coordinate,
            "capturedAtUtc",
            "CapturedAtUtc",
            "sampledAtUtc",
            "SampledAtUtc",
            "observedAtUtc",
            "ObservedAtUtc",
        )
        or get_mapping_value(
            document,
            "captured_at_utc",
            "CapturedAtUtc",
            "sampledAtUtc",
            "SampledAtUtc",
            "observedAtUtc",
            "ObservedAtUtc",
            "generatedAtUtc",
            "GeneratedAtUtc",
        ),
        "x": to_float_or_none(get_mapping_value(coordinate, "x", "X")),
        "y": to_float_or_none(get_mapping_value(coordinate, "y", "Y")),
        "z": to_float_or_none(get_mapping_value(coordinate, "z", "Z")),
        "fresh": first_present(
            get_mapping_value(coordinate, "fresh", "Fresh"),
            get_mapping_value(document, "fresh", "Fresh"),
        ),
        "stale": first_present(
            get_mapping_value(coordinate, "stale", "Stale"),
            get_mapping_value(document, "stale", "Stale"),
        ),
        "ready": get_mapping_value(document, "ready", "Ready", "aggregateReady", "AggregateReady"),
        "healthy": get_mapping_value(document, "healthy", "Healthy", "aggregateHealthy", "AggregateHealthy"),
        "aggregateStale": get_mapping_value(document, "aggregateStale", "AggregateStale"),
        "navigationPlayerPositionAvailable": get_nested_mapping_value(
            document,
            "navigation",
            "playerPositionAvailable",
        ),
        "processName": get_mapping_value(document, "processName", "ProcessName"),
        "processId": to_int_or_none(get_mapping_value(document, "processId", "ProcessId")),
        "targetWindowHandle": get_mapping_value(document, "targetWindowHandle", "TargetWindowHandle"),
        "noCheatEngine": get_mapping_value(document, "noCheatEngine", "NoCheatEngine"),
        "movementSent": get_mapping_value(document, "movementSent", "MovementSent"),
        "savedVariablesUse": get_mapping_value(document, "savedVariablesUse", "SavedVariablesUse"),
        "savedVariablesUsedAsLiveTruth": get_mapping_value(
            document,
            "savedVariablesUsedAsLiveTruth",
            "SavedVariablesUsedAsLiveTruth",
        ),
    }


def candidate_address_value(document: dict[str, Any]) -> Any:
    return get_mapping_value(
        document,
        "address",
        "Address",
        "addressHex",
        "AddressHex",
        "absoluteAddressHex",
        "AbsoluteAddressHex",
        "candidateAddressHex",
        "CandidateAddressHex",
        "xAddressHex",
        "XAddressHex",
    )


def extract_candidate_record(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidateId": get_mapping_value(candidate, "candidateId", "CandidateId", "id", "Id"),
        "address": candidate_address_value(candidate),
        "axisOrder": get_mapping_value(candidate, "axisOrder", "AxisOrder"),
        "processName": get_mapping_value(candidate, "processName", "ProcessName"),
        "processId": to_int_or_none(get_mapping_value(candidate, "processId", "ProcessId")),
        "targetWindowHandle": get_mapping_value(candidate, "targetWindowHandle", "TargetWindowHandle"),
        "sourceKind": get_mapping_value(candidate, "sourceKind", "SourceKind", "kind", "Kind"),
    }


def extract_candidate_records(document: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = get_mapping_value(document, "candidates", "Candidates")
    if isinstance(candidates, list):
        return [extract_candidate_record(candidate) for candidate in candidates if isinstance(candidate, dict)]
    return [extract_candidate_record(document)]


def is_latest_preflight_alias(value: Path | None) -> bool:
    return value is not None and str(value).strip().lower() == PREFLIGHT_SUMMARY_LATEST_ALIAS


def is_latest_api_coordinate_alias(value: Path | None) -> bool:
    return value is not None and str(value).strip().lower() == API_COORDINATE_FILE_LATEST_ALIAS


def parse_utc_sort_time(value: Any, fallback_path: Path) -> datetime:
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(fallback_path.stat().st_mtime, UTC)
    except OSError:
        return datetime.min.replace(tzinfo=UTC)


def parse_utc_datetime_value(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def artifact_age_seconds(timestamp: Any, now_utc: str | None) -> float | None:
    captured = parse_utc_datetime_value(timestamp)
    current = parse_utc_datetime_value(now_utc) if now_utc else datetime.now(UTC)
    if captured is None or current is None:
        return None
    return max(0.0, (current - captured).total_seconds())


def find_latest_passed_preflight_summary(repo_root: Path) -> tuple[Path | None, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    capture_root = repo_root / "scripts" / "captures"
    candidates: list[tuple[datetime, float, str, Path]] = []

    for path in capture_root.glob("x64dbg-target-preflight-*/summary.json"):
        try:
            document = read_json_file(path)
        except Exception as exc:
            warnings.append(f"preflight-summary-latest-skip-read-failed:{path}:{type(exc).__name__}")
            continue
        if not isinstance(document, dict):
            warnings.append(f"preflight-summary-latest-skip-non-object:{path}")
            continue
        if document.get("kind") != PREFLIGHT_SUMMARY_KIND:
            warnings.append(f"preflight-summary-latest-skip-kind:{path}")
            continue
        if document.get("status") != "passed":
            continue
        if not isinstance(document.get("selectedTarget"), dict):
            warnings.append(f"preflight-summary-latest-skip-missing-selected-target:{path}")
            continue
        generated_at = parse_utc_sort_time(document.get("generatedAtUtc"), path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        candidates.append((generated_at, mtime, str(path), path))

    if not candidates:
        blockers.append(f"preflight-summary-latest-not-found:{capture_root / 'x64dbg-target-preflight-*/summary.json'}")
        return None, blockers, warnings

    candidates.sort()
    return candidates[-1][3], blockers, warnings


def resolve_preflight_summary_argument(args: argparse.Namespace, repo_root: Path) -> None:
    args.preflight_summary_requested = str(args.preflight_summary) if args.preflight_summary else None
    args.preflight_summary_resolved_from_alias = None
    args.preflight_summary_resolution_blockers = []
    args.preflight_summary_resolution_warnings = []
    if not is_latest_preflight_alias(args.preflight_summary):
        return

    summary_path, blockers, warnings = find_latest_passed_preflight_summary(repo_root)
    args.preflight_summary_resolution_blockers.extend(blockers)
    args.preflight_summary_resolution_warnings.extend(warnings)
    args.preflight_summary_resolved_from_alias = PREFLIGHT_SUMMARY_LATEST_ALIAS
    args.preflight_summary = summary_path


def api_coordinate_file_is_usable(extracted: dict[str, Any]) -> bool:
    status = extracted.get("status")
    if status is not None and str(status).lower() not in {"captured", "pass", "passed", "ok"}:
        return False
    if extracted.get("fresh") is not None and not bool_is_true(extracted.get("fresh")):
        return False
    if bool_is_true(extracted.get("stale")):
        return False
    if extracted.get("ready") is not None and not bool_is_true(extracted.get("ready")):
        return False
    if extracted.get("healthy") is not None and not bool_is_true(extracted.get("healthy")):
        return False
    if bool_is_true(extracted.get("aggregateStale")):
        return False
    if extracted.get("navigationPlayerPositionAvailable") is not None and not bool_is_true(
        extracted.get("navigationPlayerPositionAvailable")
    ):
        return False
    if extracted.get("noCheatEngine") is not None and not bool_is_true(extracted.get("noCheatEngine")):
        return False
    if bool_is_true(extracted.get("movementSent")):
        return False
    if bool_is_true(extracted.get("savedVariablesUsedAsLiveTruth")):
        return False
    saved_variables_use = extracted.get("savedVariablesUse")
    if saved_variables_use is not None and str(saved_variables_use).strip().lower() != "none":
        return False
    if extracted.get("x") is None or extracted.get("y") is None or extracted.get("z") is None:
        return False
    if not extracted.get("sampledAtUtc"):
        return False
    return True


def find_latest_api_coordinate_file(
    repo_root: Path,
    *,
    target_pid: int | None,
    target_hwnd: str | None,
) -> tuple[Path | None, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    capture_root = repo_root / "scripts" / "captures"
    target_hwnd_normalized = normalize_hwnd(target_hwnd)

    if target_pid is None or not target_hwnd_normalized:
        blockers.append("api-coordinate-file-latest-requires-target-pid-hwnd")
        return None, blockers, warnings

    candidates: list[tuple[datetime, float, str, Path]] = []
    for path in capture_root.rglob("rift-api-reference-currentpid-*.json"):
        try:
            document = read_json_file(path)
        except Exception as exc:
            warnings.append(f"api-coordinate-file-latest-skip-read-failed:{path}:{type(exc).__name__}")
            continue
        if not isinstance(document, dict):
            warnings.append(f"api-coordinate-file-latest-skip-non-object:{path}")
            continue
        extracted = extract_api_coordinate_document(document)
        if not api_coordinate_file_is_usable(extracted):
            continue
        process_id = extracted.get("processId")
        target_window_handle = normalize_hwnd(str(extracted.get("targetWindowHandle") or ""))
        if process_id is None or int(process_id) != int(target_pid):
            continue
        if not target_window_handle or target_window_handle != target_hwnd_normalized:
            continue
        generated_at = parse_utc_sort_time(extracted.get("sampledAtUtc"), path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        candidates.append((generated_at, mtime, str(path), path))

    if not candidates:
        blockers.append(
            f"api-coordinate-file-latest-not-found:{capture_root / '**' / 'rift-api-reference-currentpid-*.json'}"
        )
        return None, blockers, warnings

    candidates.sort()
    return candidates[-1][3], blockers, warnings


def resolve_api_coordinate_file_argument(args: argparse.Namespace, repo_root: Path) -> None:
    args.api_coordinate_file_requested = str(args.api_coordinate_file) if args.api_coordinate_file else None
    args.api_coordinate_file_resolved_from_alias = None
    args.api_coordinate_file_resolution_blockers = []
    args.api_coordinate_file_resolution_warnings = []
    if not is_latest_api_coordinate_alias(args.api_coordinate_file):
        return

    coordinate_file, blockers, warnings = find_latest_api_coordinate_file(
        repo_root,
        target_pid=args.target_pid,
        target_hwnd=args.target_hwnd,
    )
    args.api_coordinate_file_resolution_blockers.extend(blockers)
    args.api_coordinate_file_resolution_warnings.extend(warnings)
    args.api_coordinate_file_resolved_from_alias = API_COORDINATE_FILE_LATEST_ALIAS
    args.api_coordinate_file = coordinate_file


def apply_preflight_summary(args: argparse.Namespace) -> None:
    args.preflight_summary_data = None
    args.preflight_summary_blockers = list(getattr(args, "preflight_summary_resolution_blockers", []) or [])
    args.preflight_summary_warnings = list(getattr(args, "preflight_summary_resolution_warnings", []) or [])
    if not args.preflight_summary:
        return

    try:
        document = read_json_file(Path(args.preflight_summary))
    except Exception as exc:
        args.preflight_summary_blockers.append(f"preflight-summary-read-failed:{type(exc).__name__}:{exc}")
        return
    if not isinstance(document, dict):
        args.preflight_summary_blockers.append("preflight-summary-must-be-json-object")
        return
    args.preflight_summary_data = document

    status = document.get("status")
    if status != "passed":
        args.preflight_summary_blockers.append(f"preflight-summary-not-passed:{status}")
    for blocker in document.get("blockers") or []:
        args.preflight_summary_blockers.append(f"preflight-summary-blocker:{blocker}")
    for warning in document.get("warnings") or []:
        args.preflight_summary_warnings.append(f"preflight-summary-warning:{warning}")

    debugger_count = document.get("debuggerProcessCount")
    if isinstance(debugger_count, int) and debugger_count > 0:
        args.preflight_summary_warnings.append(f"preflight-debugger-process-count:{debugger_count}")

    selected = document.get("selectedTarget")
    if not isinstance(selected, dict):
        args.preflight_summary_blockers.append("preflight-summary-missing-selected-target")
        return

    selected_pid = selected.get("pid")
    if selected_pid is not None:
        selected_pid = int(selected_pid)
        if args.target_pid is not None and int(args.target_pid) != selected_pid:
            args.preflight_summary_blockers.append(f"target-pid-mismatch-preflight:{args.target_pid}!={selected_pid}")
        else:
            args.target_pid = selected_pid

    selected_hwnd = normalize_hwnd(str(selected.get("hwndHex") or selected.get("hwnd") or ""))
    if selected_hwnd:
        if args.target_hwnd and normalize_hwnd(args.target_hwnd) != selected_hwnd:
            args.preflight_summary_blockers.append(
                f"target-hwnd-mismatch-preflight:{normalize_hwnd(args.target_hwnd)}!={selected_hwnd}"
            )
        else:
            args.target_hwnd = selected_hwnd

    selected_start = selected.get("startTimeUtc")
    if selected_start:
        if args.process_start_time_utc and str(args.process_start_time_utc) != str(selected_start):
            args.preflight_summary_blockers.append(
                f"process-start-time-mismatch-preflight:{args.process_start_time_utc}!={selected_start}"
            )
        else:
            args.process_start_time_utc = str(selected_start)

    selected_module_base = selected.get("moduleBaseAddressHex") or selected.get("moduleBaseAddress")
    if selected_module_base:
        try:
            selected_module_base_int = int(str(selected_module_base), 0)
        except ValueError:
            args.preflight_summary_blockers.append(f"module-base-preflight-invalid:{selected_module_base}")
        else:
            if args.module_base is not None and int(args.module_base) != selected_module_base_int:
                args.preflight_summary_blockers.append(
                    f"module-base-mismatch-preflight:{normalize_hex_int(args.module_base)}!={int_hex(selected_module_base_int)}"
                )
            else:
                args.module_base = selected_module_base_int

    selected_process_name = selected.get("processName")
    if selected_process_name:
        expected = str(args.process_name or DEFAULT_PROCESS_NAME).removesuffix(".exe").lower()
        actual = str(selected_process_name).removesuffix(".exe").lower()
        if actual != expected:
            args.preflight_summary_blockers.append(f"process-name-mismatch-preflight:{actual}!={expected}")


def apply_api_coordinate_file(args: argparse.Namespace) -> None:
    args.api_coordinate_file_data = None
    args.api_coordinate_file_blockers = list(getattr(args, "api_coordinate_file_resolution_blockers", []) or [])
    args.api_coordinate_file_warnings = list(getattr(args, "api_coordinate_file_resolution_warnings", []) or [])
    if not args.api_coordinate_file:
        return

    try:
        document = read_json_file(Path(args.api_coordinate_file))
    except Exception as exc:
        args.api_coordinate_file_blockers.append(f"api-coordinate-file-read-failed:{type(exc).__name__}:{exc}")
        return
    if not isinstance(document, dict):
        args.api_coordinate_file_blockers.append("api-coordinate-file-must-be-json-object")
        return

    extracted = extract_api_coordinate_document(document)
    args.api_coordinate_file_data = extracted

    status = extracted.get("status")
    if status is not None and str(status).lower() not in {"captured", "pass", "passed", "ok"}:
        args.api_coordinate_file_blockers.append(f"api-coordinate-file-status-not-usable:{status}")

    if extracted.get("fresh") is not None and not bool_is_true(extracted.get("fresh")):
        args.api_coordinate_file_blockers.append("api-coordinate-file-not-fresh")
    if bool_is_true(extracted.get("stale")):
        args.api_coordinate_file_blockers.append("api-coordinate-file-stale")
    if extracted.get("ready") is not None and not bool_is_true(extracted.get("ready")):
        args.api_coordinate_file_blockers.append("api-coordinate-file-not-ready")
    if extracted.get("healthy") is not None and not bool_is_true(extracted.get("healthy")):
        args.api_coordinate_file_blockers.append("api-coordinate-file-not-healthy")
    if bool_is_true(extracted.get("aggregateStale")):
        args.api_coordinate_file_blockers.append("api-coordinate-file-aggregate-stale")
    if extracted.get("navigationPlayerPositionAvailable") is not None and not bool_is_true(
        extracted.get("navigationPlayerPositionAvailable")
    ):
        args.api_coordinate_file_blockers.append("api-coordinate-file-navigation-player-position-unavailable")

    if extracted.get("noCheatEngine") is not None and not bool_is_true(extracted.get("noCheatEngine")):
        args.api_coordinate_file_blockers.append("api-coordinate-file-cheat-engine-not-excluded")
    if bool_is_true(extracted.get("movementSent")):
        args.api_coordinate_file_blockers.append("api-coordinate-file-movement-sent")
    if bool_is_true(extracted.get("savedVariablesUsedAsLiveTruth")):
        args.api_coordinate_file_blockers.append("api-coordinate-file-savedvariables-used-as-live-truth")
    saved_variables_use = extracted.get("savedVariablesUse")
    if saved_variables_use is not None and str(saved_variables_use).strip().lower() != "none":
        args.api_coordinate_file_blockers.append(f"api-coordinate-file-savedvariables-use:{saved_variables_use}")

    x_value = extracted.get("x")
    y_value = extracted.get("y")
    z_value = extracted.get("z")
    if x_value is None or y_value is None or z_value is None:
        args.api_coordinate_file_blockers.append("api-coordinate-file-missing-coordinate")
    else:
        for axis, explicit_value, file_value in (
            ("x", args.api_x, x_value),
            ("y", args.api_y, y_value),
            ("z", args.api_z, z_value),
        ):
            if explicit_value is not None and not floats_match(float(explicit_value), float(file_value)):
                args.api_coordinate_file_blockers.append(
                    f"api-coordinate-{axis}-mismatch-file:{explicit_value}!={file_value}"
                )
        if args.api_x is None:
            args.api_x = x_value
        if args.api_y is None:
            args.api_y = y_value
        if args.api_z is None:
            args.api_z = z_value

    sampled_at_utc = extracted.get("sampledAtUtc")
    if sampled_at_utc:
        if args.api_sampled_at_utc and str(args.api_sampled_at_utc) != str(sampled_at_utc):
            args.api_coordinate_file_blockers.append(
                f"api-sampled-at-utc-mismatch-file:{args.api_sampled_at_utc}!={sampled_at_utc}"
            )
        else:
            args.api_sampled_at_utc = str(sampled_at_utc)
    else:
        args.api_coordinate_file_blockers.append("api-coordinate-file-missing-sampled-at-utc")

    source = extracted.get("source")
    if source and args.api_source == "fresh-api-runtime-coordinate":
        args.api_source = str(source)

    process_id = extracted.get("processId")
    if process_id is not None:
        if args.target_pid is not None and int(args.target_pid) != int(process_id):
            args.api_coordinate_file_blockers.append(f"target-pid-mismatch-api-coordinate:{args.target_pid}!={process_id}")
        elif args.target_pid is None:
            args.target_pid = int(process_id)

    target_hwnd = normalize_hwnd(str(extracted.get("targetWindowHandle") or ""))
    if target_hwnd:
        if args.target_hwnd and normalize_hwnd(args.target_hwnd) != target_hwnd:
            args.api_coordinate_file_blockers.append(
                f"target-hwnd-mismatch-api-coordinate:{normalize_hwnd(args.target_hwnd)}!={target_hwnd}"
            )
        elif not args.target_hwnd:
            args.target_hwnd = target_hwnd

    process_name = extracted.get("processName")
    if process_name:
        expected = str(args.process_name or DEFAULT_PROCESS_NAME).removesuffix(".exe").lower()
        actual = str(process_name).removesuffix(".exe").lower()
        if actual != expected:
            args.api_coordinate_file_blockers.append(f"process-name-mismatch-api-coordinate:{actual}!={expected}")


def apply_candidate_file(args: argparse.Namespace) -> None:
    args.candidate_file_data = None
    args.candidate_file_blockers = []
    args.candidate_file_warnings = []
    if not args.candidate_file:
        return

    try:
        document = read_json_file(Path(args.candidate_file))
    except Exception as exc:
        args.candidate_file_blockers.append(f"candidate-file-read-failed:{type(exc).__name__}:{exc}")
        return
    if not isinstance(document, dict):
        args.candidate_file_blockers.append("candidate-file-must-be-json-object")
        return

    records = extract_candidate_records(document)
    usable_records = [record for record in records if record.get("address")]
    if not usable_records:
        args.candidate_file_blockers.append("candidate-file-missing-address")
        return

    selected: dict[str, Any] | None = None
    if len(usable_records) == 1:
        selected = usable_records[0]
    else:
        requested_id = None if args.candidate_id == DEFAULT_CANDIDATE_ID else str(args.candidate_id)
        if requested_id:
            matches = [record for record in usable_records if str(record.get("candidateId")) == requested_id]
            if len(matches) == 1:
                selected = matches[0]
            elif not matches:
                args.candidate_file_blockers.append(f"candidate-file-candidate-id-not-found:{requested_id}")
            else:
                args.candidate_file_blockers.append(f"candidate-file-candidate-id-ambiguous:{requested_id}")
        else:
            args.candidate_file_blockers.append("candidate-file-multiple-candidates-requires-candidate-id")
    if selected is None:
        return

    args.candidate_file_data = selected
    selected_id = selected.get("candidateId")
    if selected_id:
        if args.candidate_id != DEFAULT_CANDIDATE_ID and str(args.candidate_id) != str(selected_id):
            args.candidate_file_blockers.append(f"candidate-id-mismatch-file:{args.candidate_id}!={selected_id}")
        else:
            args.candidate_id = str(selected_id)

    try:
        selected_address = int(str(selected.get("address")), 0)
    except ValueError:
        args.candidate_file_blockers.append(f"candidate-file-address-invalid:{selected.get('address')}")
        return
    if args.candidate_address is not None and int(args.candidate_address) != selected_address:
        args.candidate_file_blockers.append(
            f"candidate-address-mismatch-file:{normalize_hex_int(args.candidate_address)}!={int_hex(selected_address)}"
        )
    else:
        args.candidate_address = selected_address

    axis_order = selected.get("axisOrder")
    if axis_order:
        if args.axis_order and str(args.axis_order) != str(axis_order):
            args.candidate_file_blockers.append(f"candidate-axis-order-mismatch-file:{args.axis_order}!={axis_order}")
        else:
            args.axis_order = str(axis_order)

    process_id = selected.get("processId")
    if process_id is not None:
        if args.target_pid is not None and int(args.target_pid) != int(process_id):
            args.candidate_file_blockers.append(f"target-pid-mismatch-candidate:{args.target_pid}!={process_id}")
        elif args.target_pid is None:
            args.target_pid = int(process_id)

    target_hwnd = normalize_hwnd(str(selected.get("targetWindowHandle") or ""))
    if target_hwnd:
        if args.target_hwnd and normalize_hwnd(args.target_hwnd) != target_hwnd:
            args.candidate_file_blockers.append(
                f"target-hwnd-mismatch-candidate:{normalize_hwnd(args.target_hwnd)}!={target_hwnd}"
            )
        elif not args.target_hwnd:
            args.target_hwnd = target_hwnd

    process_name = selected.get("processName")
    if process_name:
        expected = str(args.process_name or DEFAULT_PROCESS_NAME).removesuffix(".exe").lower()
        actual = str(process_name).removesuffix(".exe").lower()
        if actual != expected:
            args.candidate_file_blockers.append(f"process-name-mismatch-candidate:{actual}!={expected}")


def apply_strict_live_debugger_readiness(args: argparse.Namespace) -> None:
    args.strict_readiness_blockers = []
    args.strict_readiness_defaults_applied = {}
    if not args.strict_live_debugger_readiness:
        return

    if args.max_preflight_age_seconds is None:
        args.max_preflight_age_seconds = STRICT_DEFAULT_MAX_PREFLIGHT_AGE_SECONDS
        args.strict_readiness_defaults_applied["maxPreflightAgeSeconds"] = STRICT_DEFAULT_MAX_PREFLIGHT_AGE_SECONDS
    if args.max_api_coordinate_age_seconds is None:
        args.max_api_coordinate_age_seconds = STRICT_DEFAULT_MAX_API_COORDINATE_AGE_SECONDS
        args.strict_readiness_defaults_applied[
            "maxApiCoordinateAgeSeconds"
        ] = STRICT_DEFAULT_MAX_API_COORDINATE_AGE_SECONDS

    if not args.preflight_summary:
        args.strict_readiness_blockers.append("strict-readiness-requires-preflight-summary")
    if not args.api_coordinate_file:
        args.strict_readiness_blockers.append("strict-readiness-requires-api-coordinate-file")
    if not args.candidate_file:
        args.strict_readiness_blockers.append("strict-readiness-requires-candidate-file")


def build_safety(
    *,
    allow_live_debugger: bool,
    max_live_attach_seconds: int,
    unresponsive_abort_seconds: int,
    max_go_attempts: int,
) -> dict[str, Any]:
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "githubConnectorWrites": False,
        "providerWrites": False,
        "codexMcpConfigured": False,
        "codexMcpServerStarted": False,
        "x64dbgLiveDebuggerApprovedForFutureSession": allow_live_debugger,
        "x64dbgLiveAttachStarted": False,
        "x64dbgCommandsExecuted": False,
        "processAttachOrMemoryReadStarted": False,
        "targetMutationAllowed": False,
        "movementAllowed": False,
        "candidateOnly": True,
        "writeClassOperationsBlocked": True,
        "blockedOperations": list(BLOCKED_OPERATIONS),
        "liveAttachPolicy": live_attach_policy(
            max_live_attach_seconds=max_live_attach_seconds,
            unresponsive_abort_seconds=unresponsive_abort_seconds,
            max_go_attempts=max_go_attempts,
        ),
    }


def process_identity(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "name": args.process_name,
        "pid": args.target_pid,
        "hwnd": normalize_hwnd(args.target_hwnd),
        "startTimeUtc": args.process_start_time_utc,
        "moduleBaseAddressHex": normalize_hex_int(args.module_base),
    }


def truth_surface(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "kind": "api-now",
        "source": args.api_source,
        "sampledAtUtc": args.api_sampled_at_utc,
        "x": args.api_x,
        "y": args.api_y,
        "z": args.api_z,
        "artifactPath": str(args.api_coordinate_file) if getattr(args, "api_coordinate_file", None) else None,
    }


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def placeholder(name: str) -> str:
    return f"<{name}>"


def command_value(value: Any, name: str) -> str:
    return str(value) if value not in (None, "") else placeholder(name)


def append_flag(lines: list[str], name: str, value: Any, placeholder_name: str | None = None) -> None:
    if placeholder_name is None and value in (None, ""):
        return
    text = command_value(value, placeholder_name or name.lstrip("-"))
    lines.append(f"  {name} {powershell_quote(text)} `")


def rerun_command_text(summary: dict[str, Any]) -> str:
    repo_root = Path(summary["repoRoot"])
    script_path = repo_root / "scripts" / "x64dbg_coord_chain_plan.py"
    preflight = summary.get("preflight") or {}
    api_coordinate_file = summary.get("apiCoordinateFile") or {}
    candidate = summary["candidate"]
    process = summary["process"]
    truth = summary["truthSurface"]
    policy = summary["safety"]["liveAttachPolicy"]
    lines = [
        "# Generated x64dbg coordinate-chain planner command.",
        "# This command is artifact-only. It does not attach x64dbg, set watchpoints, read live memory, or send input.",
        "# Replace any <...> placeholder before running.",
        f"python {powershell_quote(str(script_path))} `",
    ]

    if preflight.get("summaryPath"):
        append_flag(lines, "--preflight-summary", preflight.get("summaryPath"))
    else:
        append_flag(lines, "--target-pid", process.get("pid"), "target-pid")
        append_flag(lines, "--target-hwnd", process.get("hwnd"), "target-hwnd")
        append_flag(lines, "--process-start-time-utc", process.get("startTimeUtc"), "process-start-time-utc")
        append_flag(lines, "--module-base", process.get("moduleBaseAddressHex"))

    if api_coordinate_file.get("path"):
        append_flag(lines, "--api-coordinate-file", api_coordinate_file.get("path"))
    else:
        append_flag(lines, "--api-x", truth.get("x"), "api-x")
        append_flag(lines, "--api-y", truth.get("y"), "api-y")
        append_flag(lines, "--api-z", truth.get("z"), "api-z")
        append_flag(lines, "--api-sampled-at-utc", truth.get("sampledAtUtc"), "api-sampled-at-utc")
        append_flag(lines, "--api-source", truth.get("source"))

    if candidate.get("artifactPath"):
        append_flag(lines, "--candidate-file", candidate.get("artifactPath"))
    else:
        append_flag(lines, "--candidate-address", candidate.get("address"), "candidate-address")
    append_flag(lines, "--candidate-id", candidate.get("candidateId"))
    append_flag(lines, "--max-live-attach-seconds", policy.get("maxLiveAttachSeconds"))
    append_flag(lines, "--unresponsive-abort-seconds", policy.get("unresponsiveAbortSeconds"))
    append_flag(lines, "--max-go-attempts", policy.get("maxGoAttempts"))
    lines.append("  --json")
    return "\n".join(lines).rstrip() + "\n"


def candidate_template(args: argparse.Namespace) -> dict[str, Any]:
    address = args.candidate_address
    axis_offsets = {"x": "0x0", "y": "0x4", "z": "0x8"}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "candidate-template",
        "tool": "x64dbg",
        "capturedAtUtc": None,
        "candidateId": args.candidate_id,
        "process": process_identity(args),
        "truthSurface": truth_surface(args),
        "memoryNow": {
            "address": int_hex(address) if address is not None else None,
            "axisOrder": args.axis_order,
            "x": None,
            "y": None,
            "z": None,
            "sampledAtUtc": None,
        },
        "watchWindow": {
            "baseAddress": int_hex(address) if address is not None else None,
            "sizeBytes": args.watch_size,
            "axisOffsets": axis_offsets,
            "access": "read | write | access",
            "plannedOnly": True,
        },
        "observedAccessEvents": [],
        "instruction": {
            "module": "rift_x64.exe",
            "moduleBase": None,
            "address": None,
            "rva": None,
            "bytes": None,
            "disassembly": None,
            "access": None,
            "registers": {},
            "derivedObjectPointer": None,
            "fieldOffset": None,
        },
        "derivedChain": {
            "rootKind": "pending-module-rva-or-static-owner",
            "module": "rift_x64.exe",
            "moduleBase": None,
            "rootRva": None,
            "offsets": [],
            "fieldOffsets": axis_offsets,
            "chainExpression": None,
        },
        "validation": {
            "sameTarget": False,
            "apiNowVsChainNow": False,
            "multiPose": False,
            "poseCountRequired": args.pose_count,
            "restartValidated": False,
            "runtimeHelperReadback": False,
            "proofOnlyPassed": False,
            "movementProofEligible": False,
        },
        "blockers": [
            "no-x64dbg-access-events-recorded",
            "not-module-relative-rooted",
            "not-multi-pose-validated",
            "not-restart-validated",
            "not-promoted-through-api-now-vs-chain-now",
        ],
    }


def readiness_check(name: str, status: str, passed: bool, detail: str, evidence: Any = None) -> dict[str, Any]:
    check: dict[str, Any] = {
        "name": name,
        "status": status,
        "passed": passed,
        "detail": detail,
    }
    if evidence is not None:
        check["evidence"] = evidence
    return check


def build_readiness(args: argparse.Namespace, blockers: list[str]) -> dict[str, Any]:
    preflight = getattr(args, "preflight_summary_data", None) or {}
    debugger_count = preflight.get("debuggerProcessCount")
    selected_target = preflight.get("selectedTarget") if isinstance(preflight.get("selectedTarget"), dict) else None
    target_identity_passed = bool(args.target_pid and args.target_hwnd and args.process_start_time_utc and args.module_base)
    strict_preflight_passed = bool(
        args.preflight_summary
        and preflight.get("status") == "passed"
        and selected_target
        and debugger_count == 0
        and not getattr(args, "preflight_summary_blockers", [])
    )
    api_coordinate_passed = bool(
        args.api_x is not None
        and args.api_y is not None
        and args.api_z is not None
        and args.api_sampled_at_utc
        and not getattr(args, "api_coordinate_file_blockers", [])
    )
    candidate_passed = bool(args.candidate_address is not None and not getattr(args, "candidate_file_blockers", []))
    policy_blockers = validate_live_attach_policy(
        max_live_attach_seconds=args.max_live_attach_seconds,
        unresponsive_abort_seconds=args.unresponsive_abort_seconds,
        max_go_attempts=args.max_go_attempts,
    )
    policy_passed = not policy_blockers
    age_blockers = validate_artifact_age_policy(args)
    age_policy_passed = not age_blockers
    strict_blockers = getattr(args, "strict_readiness_blockers", []) or []
    strict_passed = not args.strict_live_debugger_readiness or not strict_blockers
    input_ready = (
        target_identity_passed
        and strict_preflight_passed
        and api_coordinate_passed
        and candidate_passed
        and policy_passed
        and age_policy_passed
        and strict_passed
    )
    approval_granted = bool(args.allow_live_debugger)

    checks = [
        readiness_check(
            "target-identity-complete",
            "passed" if target_identity_passed else "blocked",
            target_identity_passed,
            "PID, HWND, process start UTC, and module base are present.",
            {
                "pid": args.target_pid,
                "hwnd": normalize_hwnd(args.target_hwnd),
                "startTimeUtc": args.process_start_time_utc,
                "moduleBaseAddressHex": normalize_hex_int(args.module_base),
            },
        ),
        readiness_check(
            "strict-no-attach-preflight",
            "passed" if strict_preflight_passed else "missing-or-not-strict",
            strict_preflight_passed,
            "A passed same-target no-attach preflight with zero debugger-class processes is required before live debugger approval.",
            {
                "summaryPath": str(args.preflight_summary) if args.preflight_summary else None,
                "status": preflight.get("status"),
                "debuggerProcessCount": debugger_count,
            },
        ),
        readiness_check(
            "api-coordinate-present",
            "passed" if api_coordinate_passed else "blocked",
            api_coordinate_passed,
            "API/runtime coordinate X/Y/Z and sampled UTC are present.",
            {
                "source": args.api_source,
                "artifactPath": str(args.api_coordinate_file) if args.api_coordinate_file else None,
                "sampledAtUtc": args.api_sampled_at_utc,
            },
        ),
        readiness_check(
            "candidate-address-present",
            "passed" if candidate_passed else "blocked",
            candidate_passed,
            "A coordinate candidate address is present for the planned watch window.",
            {
                "candidateId": args.candidate_id,
                "address": int_hex(args.candidate_address) if args.candidate_address is not None else None,
                "artifactPath": str(args.candidate_file) if args.candidate_file else None,
            },
        ),
        readiness_check(
            "live-attach-policy-bounds",
            "passed" if policy_passed else "blocked",
            policy_passed,
            "Live attach timeout, unresponsive abort, and go/run attempt limits are within policy.",
            {
                "maxLiveAttachSeconds": args.max_live_attach_seconds,
                "unresponsiveAbortSeconds": args.unresponsive_abort_seconds,
                "maxGoAttempts": args.max_go_attempts,
                "policyBlockers": policy_blockers,
            },
        ),
        readiness_check(
            "artifact-age-policy",
            "passed" if age_policy_passed else "blocked",
            age_policy_passed,
            "Optional max-age checks for preflight/API artifacts are satisfied, or no max age was requested.",
            {
                "maxPreflightAgeSeconds": args.max_preflight_age_seconds,
                "maxApiCoordinateAgeSeconds": args.max_api_coordinate_age_seconds,
                "nowUtc": args.readiness_now_utc,
                "ageBlockers": age_blockers,
            },
        ),
        readiness_check(
            "strict-live-debugger-readiness-preset",
            "passed" if strict_passed else "blocked",
            strict_passed,
            "When enabled, strict readiness requires preflight, API coordinate, and candidate artifacts plus max-age gates.",
            {
                "enabled": args.strict_live_debugger_readiness,
                "defaultsApplied": getattr(args, "strict_readiness_defaults_applied", {}),
                "strictBlockers": strict_blockers,
            },
        ),
        readiness_check(
            "current-turn-debugger-approval",
            "approved" if approval_granted else "pending",
            approval_granted,
            "Live debugger capture still requires explicit current-turn approval; planner generation is artifact-only.",
        ),
    ]

    if args.self_test:
        status = "self-test"
    elif blockers:
        status = "blocked"
    elif input_ready and approval_granted:
        status = "approved-for-bounded-capture"
    elif input_ready:
        status = "ready-for-current-turn-approval"
    else:
        status = "needs-strict-preflight"

    return {
        "status": status,
        "readyForCurrentTurnApproval": bool(input_ready and not blockers),
        "readyForBoundedDebuggerCapture": bool(input_ready and approval_granted and not blockers),
        "checks": checks,
    }


def planned_phases(args: argparse.Namespace) -> list[dict[str, Any]]:
    address = int_hex(args.candidate_address) if args.candidate_address is not None else "<candidate-address>"
    return [
        {
            "phase": 0,
            "name": "preflight-no-attach",
            "goal": "Confirm exact target identity, fresh API coordinate, current coordinate candidate, and no other debugger.",
            "allowedNow": True,
        },
        {
            "phase": 1,
            "name": "approved-x64dbg-attach",
            "goal": (
                "After explicit current-turn approval, attach x64dbg only to the recorded "
                f"PID/HWND/process-start target and detach within {args.max_live_attach_seconds} seconds."
            ),
            "allowedNow": bool(args.allow_live_debugger),
        },
        {
            "phase": 2,
            "name": "12-byte-coordinate-watch-window",
            "goal": f"Set x64dbg data watch/breakpoint over {address}..{address}+0x{args.watch_size - 1:X} for X/Y/Z lane access evidence.",
            "allowedNow": bool(args.allow_live_debugger),
        },
        {
            "phase": 3,
            "name": "multi-pose-access-capture",
            "goal": f"Capture at least {args.pose_count} pose-separated access events with same-target API-now coordinates.",
            "allowedNow": bool(args.allow_live_debugger),
        },
        {
            "phase": 4,
            "name": "module-relative-chain-hypothesis",
            "goal": "Derive module/RVA/static-owner root, offsets, field offsets, and instruction provenance.",
            "allowedNow": False,
        },
        {
            "phase": 5,
            "name": "runtime-readback-without-x64dbg",
            "goal": "Implement repo-owned readback for chain-now vs API-now comparison without debugger dependency.",
            "allowedNow": False,
        },
        {
            "phase": 6,
            "name": "restart-validation-and-proofonly",
            "goal": "Validate chain across restart/client epoch and pass same-target ProofOnly before movement use.",
            "allowedNow": False,
        },
    ]


def validate_args(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    blockers.extend(getattr(args, "preflight_summary_blockers", []) or [])
    blockers.extend(getattr(args, "api_coordinate_file_blockers", []) or [])
    blockers.extend(getattr(args, "candidate_file_blockers", []) or [])
    blockers.extend(getattr(args, "strict_readiness_blockers", []) or [])
    blockers.extend(validate_artifact_age_policy(args))
    if args.candidate_address is None:
        blockers.append("missing-candidate-address")
    if args.target_pid is None:
        blockers.append("missing-target-pid")
    if not args.target_hwnd:
        blockers.append("missing-target-hwnd")
    if not args.process_start_time_utc:
        blockers.append("missing-process-start-time-utc")
    if args.api_x is None or args.api_y is None or args.api_z is None:
        blockers.append("missing-api-coordinate")
    if not args.api_sampled_at_utc:
        blockers.append("missing-api-sampled-at-utc")
    if args.watch_size < 12:
        blockers.append("watch-size-must-cover-12-byte-xyz-triplet")
    if args.pose_count < 3:
        blockers.append("pose-count-must-be-at-least-3")
    blockers.extend(
        validate_live_attach_policy(
            max_live_attach_seconds=args.max_live_attach_seconds,
            unresponsive_abort_seconds=args.unresponsive_abort_seconds,
            max_go_attempts=args.max_go_attempts,
        )
    )
    return blockers


def validate_max_age(
    *,
    kind: str,
    timestamp: Any,
    max_age_seconds: int | None,
    now_utc: str | None,
) -> list[str]:
    if max_age_seconds is None:
        return []
    age = artifact_age_seconds(timestamp, now_utc)
    if age is None:
        return [f"{kind}-timestamp-invalid-for-age-check"]
    if age > max_age_seconds:
        return [f"{kind}-stale:{int(age)}>{max_age_seconds}"]
    return []


def validate_artifact_age_policy(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    preflight = getattr(args, "preflight_summary_data", None) or {}
    blockers.extend(
        validate_max_age(
            kind="preflight-summary",
            timestamp=preflight.get("generatedAtUtc"),
            max_age_seconds=args.max_preflight_age_seconds,
            now_utc=args.readiness_now_utc,
        )
    )
    blockers.extend(
        validate_max_age(
            kind="api-coordinate",
            timestamp=args.api_sampled_at_utc,
            max_age_seconds=args.max_api_coordinate_age_seconds,
            now_utc=args.readiness_now_utc,
        )
    )
    return blockers


def build_plan(args: argparse.Namespace, repo_root: Path, run_dir: Path) -> dict[str, Any]:
    blockers = [] if args.self_test else validate_args(args)
    warnings: list[str] = []
    if args.process_name.lower() == "rift_x64" and not args.allow_live_debugger:
        warnings.append("x64dbg live RIFT attach is not authorized in this plan; request explicit current-turn approval before any attach/watchpoint session")
    if args.self_test:
        warnings.append("self-test only; no x64dbg session, RIFT process, watchpoint, memory read, or movement touched")
    warnings.extend(getattr(args, "preflight_summary_warnings", []) or [])
    warnings.extend(getattr(args, "api_coordinate_file_warnings", []) or [])
    warnings.extend(getattr(args, "candidate_file_warnings", []) or [])

    summary_json = run_dir / "coord-chain-plan-summary.json"
    summary_md = run_dir / "coord-chain-plan.md"
    template_json = run_dir / "x64dbg-coordinate-chain-candidate-template.json"
    checklist_md = run_dir / "x64dbg-coordinate-chain-session-checklist.md"
    command_txt = run_dir / "x64dbg-coordinate-chain-rerun-command.txt"
    handoff_md = run_dir / "x64dbg-coordinate-chain-compact-handoff.md"
    handoff_json = run_dir / "x64dbg-coordinate-chain-compact-handoff.json"

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "x64dbg-static-coord-chain-plan",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "planned",
        "repoRoot": str(repo_root),
        "process": process_identity(args),
        "truthSurface": truth_surface(args),
        "candidate": {
            "candidateId": args.candidate_id,
            "address": int_hex(args.candidate_address) if args.candidate_address is not None else None,
            "axisOrder": args.axis_order,
            "watchSizeBytes": args.watch_size,
            "poseCountRequired": args.pose_count,
            "artifactPath": str(args.candidate_file) if args.candidate_file else None,
            "sourceKind": (getattr(args, "candidate_file_data", {}) or {}).get("sourceKind")
            if getattr(args, "candidate_file_data", None)
            else None,
        },
        "preflight": {
            "requestedSummary": getattr(args, "preflight_summary_requested", None),
            "resolvedFromAlias": getattr(args, "preflight_summary_resolved_from_alias", None),
            "summaryPath": str(args.preflight_summary) if args.preflight_summary else None,
            "status": (getattr(args, "preflight_summary_data", {}) or {}).get("status")
            if getattr(args, "preflight_summary_data", None)
            else None,
            "selectedTarget": (getattr(args, "preflight_summary_data", {}) or {}).get("selectedTarget")
            if getattr(args, "preflight_summary_data", None)
            else None,
            "debuggerProcessCount": (getattr(args, "preflight_summary_data", {}) or {}).get("debuggerProcessCount")
            if getattr(args, "preflight_summary_data", None)
            else None,
        },
        "apiCoordinateFile": {
            "requestedFile": getattr(args, "api_coordinate_file_requested", None),
            "resolvedFromAlias": getattr(args, "api_coordinate_file_resolved_from_alias", None),
            "path": str(args.api_coordinate_file) if args.api_coordinate_file else None,
            "source": (getattr(args, "api_coordinate_file_data", {}) or {}).get("source")
            if getattr(args, "api_coordinate_file_data", None)
            else None,
            "status": (getattr(args, "api_coordinate_file_data", {}) or {}).get("status")
            if getattr(args, "api_coordinate_file_data", None)
            else None,
            "referenceFile": (getattr(args, "api_coordinate_file_data", {}) or {}).get("referenceFile")
            if getattr(args, "api_coordinate_file_data", None)
            else None,
        },
        "candidateFile": {
            "path": str(args.candidate_file) if args.candidate_file else None,
            "candidateId": (getattr(args, "candidate_file_data", {}) or {}).get("candidateId")
            if getattr(args, "candidate_file_data", None)
            else None,
            "sourceKind": (getattr(args, "candidate_file_data", {}) or {}).get("sourceKind")
            if getattr(args, "candidate_file_data", None)
            else None,
        },
        "strictLiveDebuggerReadiness": {
            "enabled": bool(args.strict_live_debugger_readiness),
            "defaultsApplied": getattr(args, "strict_readiness_defaults_applied", {}),
            "blockers": getattr(args, "strict_readiness_blockers", []),
        },
        "readiness": build_readiness(args, blockers),
        "plannedPhases": planned_phases(args),
        "promotionGates": [
            "same PID/HWND/process-start target for all samples",
            "fresh API/runtime coordinate sampled close to each chain read",
            "same chain tracks X/Y/Z across at least three displaced poses",
            "module-relative or static-owner root, not heap-only",
            "restart/client-epoch validation",
            "repo-owned runtime readback without x64dbg",
            "same-target ProofOnly pass before movement",
        ],
        "blockers": blockers,
        "warnings": warnings,
        "errors": [],
        "sources": list(SOURCE_LINKS),
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "candidateTemplateJson": str(template_json),
            "sessionChecklistMarkdown": str(checklist_md),
            "rerunCommandText": str(command_txt),
            "compactHandoffJson": str(handoff_json),
            "compactHandoffMarkdown": str(handoff_md),
        },
        "safety": build_safety(
            allow_live_debugger=bool(args.allow_live_debugger),
            max_live_attach_seconds=args.max_live_attach_seconds,
            unresponsive_abort_seconds=args.unresponsive_abort_seconds,
            max_go_attempts=args.max_go_attempts,
        ),
        "next": {
            "recommendedAction": (
                "Fill the candidate template from an explicitly approved x64dbg watchpoint session, then validate chain-now vs API-now outside x64dbg."
                if not blockers
                else "Provide the missing target/candidate/API fields, then regenerate the coord-chain plan."
            )
        },
    }
    return summary


def markdown_summary(summary: dict[str, Any]) -> str:
    candidate = summary["candidate"]
    safety = summary["safety"]
    lines = [
        "# x64dbg static coordinate pointer-chain plan",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated UTC: `{summary['generatedAtUtc']}`",
        f"- Candidate: `{candidate.get('candidateId')}` at `{candidate.get('address')}`",
        f"- Preflight summary: `{summary.get('preflight', {}).get('summaryPath')}`",
        f"- Readiness: `{summary.get('readiness', {}).get('status')}`",
        f"- Rerun command: `{summary.get('artifacts', {}).get('rerunCommandText')}`",
        f"- Compact handoff JSON: `{summary.get('artifacts', {}).get('compactHandoffJson')}`",
        f"- Compact handoff: `{summary.get('artifacts', {}).get('compactHandoffMarkdown')}`",
        f"- Movement allowed: `{str(safety.get('movementAllowed')).lower()}`",
        f"- x64dbg live attach started: `{str(safety.get('x64dbgLiveAttachStarted')).lower()}`",
        f"- x64dbg commands executed: `{str(safety.get('x64dbgCommandsExecuted')).lower()}`",
        "",
        "## Planned phases",
        "",
        "| Phase | Name | Allowed now | Goal |",
        "|---:|---|---|---|",
    ]
    for phase in summary["plannedPhases"]:
        lines.append(
            f"| `{phase['phase']}` | `{phase['name']}` | `{str(phase['allowedNow']).lower()}` | {phase['goal']} |"
        )
    if summary["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    readiness = summary.get("readiness") or {}
    if readiness:
        lines.extend(
            [
                "",
                "## Readiness verdict",
                "",
                f"- Status: `{readiness.get('status')}`",
                f"- Ready for current-turn approval: `{str(readiness.get('readyForCurrentTurnApproval')).lower()}`",
                f"- Ready for bounded debugger capture: `{str(readiness.get('readyForBoundedDebuggerCapture')).lower()}`",
                "",
                "| Check | Status | Passed | Detail | Evidence |",
                "|---|---|---|---|---|",
            ]
        )
        for check in readiness.get("checks") or []:
            lines.append(
                f"| `{check.get('name')}` | `{check.get('status')}` | `{str(check.get('passed')).lower()}` | "
                f"{markdown_cell(check.get('detail'))} | `{markdown_cell(check.get('evidence'))}` |"
            )
    lines.extend(
        [
            "",
            "## Promotion gates",
            "",
        ]
    )
    lines.extend(f"- {gate}" for gate in summary["promotionGates"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This plan creates artifacts only. It does not attach x64dbg, set watchpoints,",
            "read live memory, configure MCP, send input, or authorize movement.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def checklist_markdown(summary: dict[str, Any]) -> str:
    candidate = summary["candidate"]
    process = summary["process"]
    truth = summary["truthSurface"]
    policy = summary["safety"]["liveAttachPolicy"]
    lines = [
        "# x64dbg coordinate-chain session checklist",
        "",
        "Use only after explicit current-turn approval for a live debugger session.",
        "",
        "## Target",
        "",
        f"- Process: `{process.get('name')}`",
        f"- PID: `{process.get('pid')}`",
        f"- HWND: `{process.get('hwnd')}`",
        f"- Process start UTC: `{process.get('startTimeUtc')}`",
        f"- Module base: `{process.get('moduleBaseAddressHex')}`",
        f"- Candidate address: `{candidate.get('address')}`",
        f"- API coordinate: `X={truth.get('x')}`, `Y={truth.get('y')}`, `Z={truth.get('z')}` at `{truth.get('sampledAtUtc')}`",
        "",
        "## Attach guard",
        "",
        f"- Prebuild every command, capture path, and detach path before attach.",
        f"- Start a wall-clock timer before attach; detach within `{policy['maxLiveAttachSeconds']}` seconds.",
        f"- If RIFT is `Responding=False` for more than `{policy['unresponsiveAbortSeconds']}` seconds after attach/run, detach immediately.",
        f"- Permit at most `{policy['maxGoAttempts']}` `go/run` attempt by default.",
        "- Do not use exception-swallowing as a retry loop.",
        "- Detach first, analyze artifacts second.",
        "",
        "## Required capture per access event",
        "",
        "- pose label and fresh API coordinate;",
        "- instruction address, module, module base, RVA, bytes, disassembly;",
        "- read/write/access type;",
        "- registers used to address the coordinate field;",
        "- derived object pointer and field offset;",
        "- memory X/Y/Z read at the candidate/derived chain;",
        "- confirmation that PID/HWND/process-start still match.",
        "",
        "## Stop immediately if",
        "",
        "- target PID/HWND/process-start changes;",
        "- API/runtime coordinate is stale or missing;",
        "- x64dbg or RIFT becomes unstable;",
        f"- RIFT is `Responding=False` for more than `{policy['unresponsiveAbortSeconds']}` seconds;",
        f"- live attach reaches `{policy['maxLiveAttachSeconds']}` seconds without explicit extension;",
        f"- more than `{policy['maxGoAttempts']}` `go/run` attempt would be needed;",
        "- another debugger-class tool is attached;",
        "- the workflow would require patching or write-class operations.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def compact_handoff_markdown(summary: dict[str, Any]) -> str:
    readiness = summary.get("readiness") or {}
    process = summary["process"]
    truth = summary["truthSurface"]
    candidate = summary["candidate"]
    preflight = summary.get("preflight") or {}
    api_coordinate_file = summary.get("apiCoordinateFile") or {}
    candidate_file = summary.get("candidateFile") or {}
    safety = summary["safety"]
    artifacts = summary["artifacts"]

    lines = [
        "# x64dbg coordinate-chain compact handoff",
        "",
        "## TL;DR",
        "",
        f"- Plan status: `{summary['status']}`",
        f"- Readiness: `{readiness.get('status')}`",
        f"- Ready for current-turn approval: `{str(readiness.get('readyForCurrentTurnApproval')).lower()}`",
        f"- Ready for bounded debugger capture: `{str(readiness.get('readyForBoundedDebuggerCapture')).lower()}`",
        "- Coord evidence remains `candidate-only`; do not promote any address from this packet alone.",
        "- This handoff is artifact-only: no x64dbg attach, no watchpoints, no memory byte read/write, and no game input were performed by the planner.",
        "",
        "## Target identity",
        "",
        f"- Process: `{process.get('name')}`",
        f"- PID: `{process.get('pid')}`",
        f"- HWND: `{process.get('hwnd')}`",
        f"- Process start UTC: `{process.get('startTimeUtc')}`",
        f"- Module base: `{process.get('moduleBaseAddressHex')}`",
        "",
        "## Inputs",
        "",
        f"- Preflight summary: `{preflight.get('summaryPath')}`",
        f"- API coordinate file: `{api_coordinate_file.get('path')}`",
        f"- Candidate file: `{candidate_file.get('path')}`",
        f"- Candidate: `{candidate.get('candidateId')}` at `{candidate.get('address')}`",
        f"- API coordinate: `X={truth.get('x')}`, `Y={truth.get('y')}`, `Z={truth.get('z')}` at `{truth.get('sampledAtUtc')}`",
        "",
        "## Safety state",
        "",
        f"- Movement sent: `{str(safety.get('movementSent')).lower()}`",
        f"- Input sent: `{str(safety.get('inputSent')).lower()}`",
        f"- x64dbg live attach started: `{str(safety.get('x64dbgLiveAttachStarted')).lower()}`",
        f"- x64dbg commands executed: `{str(safety.get('x64dbgCommandsExecuted')).lower()}`",
        f"- Process attach or memory read started: `{str(safety.get('processAttachOrMemoryReadStarted')).lower()}`",
        f"- Target mutation allowed: `{str(safety.get('targetMutationAllowed')).lower()}`",
        "",
        "## Blockers",
        "",
    ]
    if summary["blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    else:
        lines.append("- None in planner inputs.")
    if summary["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    lines.extend(
        [
            "",
            "## Readiness checks",
            "",
            "| Check | Status | Passed | Evidence |",
            "|---|---|---|---|",
        ]
    )
    for check in readiness.get("checks") or []:
        lines.append(
            f"| `{check.get('name')}` | `{check.get('status')}` | `{str(check.get('passed')).lower()}` | "
            f"`{markdown_cell(check.get('evidence'))}` |"
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Summary JSON: `{artifacts.get('summaryJson')}`",
            f"- Summary MD: `{artifacts.get('summaryMarkdown')}`",
            f"- Candidate template: `{artifacts.get('candidateTemplateJson')}`",
            f"- Session checklist: `{artifacts.get('sessionChecklistMarkdown')}`",
            f"- Rerun command: `{artifacts.get('rerunCommandText')}`",
            f"- Handoff JSON: `{artifacts.get('compactHandoffJson')}`",
            f"- This handoff: `{artifacts.get('compactHandoffMarkdown')}`",
            "",
            "## Ready-to-paste resume prompt",
            "",
            "```text",
            "Resume the RiftReader x64dbg coordinate-chain workflow from this compact handoff.",
            f"Read `{artifacts.get('compactHandoffMarkdown')}` first, then read the plan summary JSON `{artifacts.get('summaryJson')}`.",
            "Do not attach x64dbg, send game input, set breakpoints/watchpoints, or read/write target memory unless I explicitly approve it in the current turn.",
            "Treat all live PID/HWND/process-start/module-base values and candidate addresses as session-specific; rerun no-attach preflight before any live-debugger work.",
            "Coordinate evidence remains candidate-only until same-target API-now vs chain-now, multi-pose, restart/client-epoch, and ProofOnly gates pass.",
            "Continue with the smallest safe artifact-only/read-only step and report blockers exactly.",
            "```",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def compact_handoff_document(summary: dict[str, Any]) -> dict[str, Any]:
    artifacts = summary["artifacts"]
    resume_prompt = (
        "Resume the RiftReader x64dbg coordinate-chain workflow from the compact handoff. "
        f"Read `{artifacts.get('compactHandoffMarkdown')}` first, then read `{artifacts.get('summaryJson')}`. "
        "Do not attach x64dbg, send game input, set breakpoints/watchpoints, or read/write target memory unless explicitly approved in the current turn. "
        "Treat all live PID/HWND/process-start/module-base values and candidate addresses as session-specific; rerun no-attach preflight before live-debugger work. "
        "Coordinate evidence remains candidate-only until same-target API-now vs chain-now, multi-pose, restart/client-epoch, and ProofOnly gates pass."
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-coordinate-chain-compact-handoff",
        "generatedAtUtc": summary["generatedAtUtc"],
        "planStatus": summary["status"],
        "readiness": summary.get("readiness"),
        "process": summary.get("process"),
        "truthSurface": summary.get("truthSurface"),
        "candidate": summary.get("candidate"),
        "preflight": summary.get("preflight"),
        "apiCoordinateFile": summary.get("apiCoordinateFile"),
        "candidateFile": summary.get("candidateFile"),
        "strictLiveDebuggerReadiness": summary.get("strictLiveDebuggerReadiness"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "safety": {
            "movementSent": summary["safety"].get("movementSent"),
            "inputSent": summary["safety"].get("inputSent"),
            "x64dbgLiveAttachStarted": summary["safety"].get("x64dbgLiveAttachStarted"),
            "x64dbgCommandsExecuted": summary["safety"].get("x64dbgCommandsExecuted"),
            "processAttachOrMemoryReadStarted": summary["safety"].get("processAttachOrMemoryReadStarted"),
            "targetMutationAllowed": summary["safety"].get("targetMutationAllowed"),
            "candidateOnly": summary["safety"].get("candidateOnly"),
            "liveAttachPolicy": summary["safety"].get("liveAttachPolicy"),
        },
        "artifacts": {
            "summaryJson": artifacts.get("summaryJson"),
            "summaryMarkdown": artifacts.get("summaryMarkdown"),
            "compactHandoffJson": artifacts.get("compactHandoffJson"),
            "compactHandoffMarkdown": artifacts.get("compactHandoffMarkdown"),
            "rerunCommandText": artifacts.get("rerunCommandText"),
            "candidateTemplateJson": artifacts.get("candidateTemplateJson"),
            "sessionChecklistMarkdown": artifacts.get("sessionChecklistMarkdown"),
        },
        "resumePrompt": resume_prompt,
        "truthWarnings": [
            "Coord evidence remains candidate-only.",
            "Do not promote candidate addresses from this handoff alone.",
            "Live PID/HWND/process-start/module-base values are session-specific and must be revalidated.",
        ],
    }


def markdown_cell(value: Any, *, max_length: int = 180) -> str:
    if value is None:
        text = ""
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, separators=(",", ":"), sort_keys=True)
    else:
        text = str(value)
    text = text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def write_outputs(summary: dict[str, Any]) -> None:
    run_dir = Path(summary["artifacts"]["runDirectory"])
    template = candidate_template(argparse.Namespace(**{
        "candidate_address": int(summary["candidate"]["address"], 16) if summary["candidate"].get("address") else None,
        "candidate_id": summary["candidate"]["candidateId"],
        "candidate_file": Path(summary["candidate"]["artifactPath"])
        if summary["candidate"].get("artifactPath")
        else None,
        "process_name": summary["process"]["name"],
        "target_pid": summary["process"]["pid"],
        "target_hwnd": summary["process"]["hwnd"],
        "process_start_time_utc": summary["process"]["startTimeUtc"],
        "module_base": int(summary["process"]["moduleBaseAddressHex"], 16)
        if summary["process"].get("moduleBaseAddressHex")
        else None,
        "api_source": summary["truthSurface"]["source"],
        "api_sampled_at_utc": summary["truthSurface"]["sampledAtUtc"],
        "api_x": summary["truthSurface"]["x"],
        "api_y": summary["truthSurface"]["y"],
        "api_z": summary["truthSurface"]["z"],
        "api_coordinate_file": Path(summary["truthSurface"]["artifactPath"])
        if summary["truthSurface"].get("artifactPath")
        else None,
        "axis_order": summary["candidate"]["axisOrder"],
        "watch_size": summary["candidate"]["watchSizeBytes"],
        "pose_count": summary["candidate"]["poseCountRequired"],
    }))
    write_json(Path(summary["artifacts"]["candidateTemplateJson"]), template)
    write_json(Path(summary["artifacts"]["compactHandoffJson"]), compact_handoff_document(summary))
    write_text_atomic(Path(summary["artifacts"]["sessionChecklistMarkdown"]), checklist_markdown(summary))
    write_text_atomic(Path(summary["artifacts"]["rerunCommandText"]), rerun_command_text(summary))
    write_text_atomic(Path(summary["artifacts"]["compactHandoffMarkdown"]), compact_handoff_markdown(summary))
    write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))
    write_json(Path(summary["artifacts"]["summaryJson"]), summary)
    run_dir.mkdir(parents=True, exist_ok=True)


def apply_self_test_defaults(args: argparse.Namespace) -> None:
    args.process_name = "rift_x64"
    args.target_pid = 12345
    args.target_hwnd = "0xABCDEF"
    args.process_start_time_utc = "2026-05-12T20:00:00Z"
    args.module_base = 0x7FF796B50000
    args.candidate_id = "x64dbg-coord-chain-self-test"
    args.candidate_file = None
    args.candidate_address = SYNTHETIC_SELF_TEST_CANDIDATE_ADDRESS
    args.api_source = "synthetic-api-now"
    args.api_sampled_at_utc = "2026-05-12T20:00:10Z"
    args.api_x = 7376.87
    args.api_y = 863.82
    args.api_z = 2990.35
    args.api_coordinate_file = None
    args.max_preflight_age_seconds = None
    args.max_api_coordinate_age_seconds = None
    args.readiness_now_utc = None
    args.strict_live_debugger_readiness = False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a safe x64dbg static pointer-chain workflow for coordinate data.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument(
        "--preflight-summary",
        type=Path,
        default=None,
        help=(
            "No-attach x64dbg_preflight.py summary.json to populate target PID/HWND/start metadata; "
            "use 'latest' to select the newest passed scripts/captures/x64dbg-target-preflight-*/summary.json."
        ),
    )
    parser.add_argument("--target-pid", type=int, default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--process-start-time-utc", default=None)
    parser.add_argument(
        "--module-base",
        type=parse_int,
        default=None,
        help="Current rift_x64.exe module base; imported from --preflight-summary when present.",
    )
    parser.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID)
    parser.add_argument(
        "--candidate-file",
        type=Path,
        default=None,
        help=(
            "Coordinate candidate JSON. Single-candidate files import the address directly; "
            "multi-candidate files require --candidate-id and fail closed if ambiguous."
        ),
    )
    parser.add_argument("--candidate-address", type=parse_int, default=None)
    parser.add_argument("--axis-order", choices=["xyz"], default="xyz")
    parser.add_argument("--watch-size", type=int, default=DEFAULT_WATCH_SIZE)
    parser.add_argument("--pose-count", type=int, default=DEFAULT_POSE_COUNT)
    parser.add_argument("--api-source", default="fresh-api-runtime-coordinate")
    parser.add_argument(
        "--api-coordinate-file",
        type=Path,
        default=None,
        help=(
            "Fresh Rift API/reference coordinate JSON or capture summary JSON; imports X/Y/Z, sampled time, "
            "and same-target PID/HWND when present. Use 'latest' only after target PID/HWND are available; "
            "it selects the newest usable same-target rift-api-reference-currentpid-*.json under scripts/captures."
        ),
    )
    parser.add_argument("--api-sampled-at-utc", default=None)
    parser.add_argument("--api-x", type=float, default=None)
    parser.add_argument("--api-y", type=float, default=None)
    parser.add_argument("--api-z", type=float, default=None)
    parser.add_argument("--allow-live-debugger", action="store_true")
    parser.add_argument("--max-live-attach-seconds", type=int, default=DEFAULT_MAX_LIVE_ATTACH_SECONDS)
    parser.add_argument("--unresponsive-abort-seconds", type=int, default=DEFAULT_UNRESPONSIVE_ABORT_SECONDS)
    parser.add_argument("--max-go-attempts", type=int, default=DEFAULT_MAX_GO_ATTEMPTS)
    parser.add_argument(
        "--max-preflight-age-seconds",
        type=int,
        default=None,
        help="Optional fail-closed max age for the selected preflight summary generatedAtUtc.",
    )
    parser.add_argument(
        "--max-api-coordinate-age-seconds",
        type=int,
        default=None,
        help="Optional fail-closed max age for the API/reference coordinate sampledAtUtc.",
    )
    parser.add_argument(
        "--readiness-now-utc",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--strict-live-debugger-readiness",
        action="store_true",
        help=(
            "Fail closed unless preflight/API/candidate artifacts are supplied and artifact age gates are active. "
            f"Defaults ages to preflight <= {STRICT_DEFAULT_MAX_PREFLIGHT_AGE_SECONDS}s and API <= "
            f"{STRICT_DEFAULT_MAX_API_COORDINATE_AGE_SECONDS}s when not explicitly provided."
        ),
    )
    return parser


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"x64dbg-coord-chain-plan-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        apply_self_test_defaults(args)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    resolve_preflight_summary_argument(args, repo_root)
    apply_preflight_summary(args)
    resolve_api_coordinate_file_argument(args, repo_root)
    apply_api_coordinate_file(args)
    apply_candidate_file(args)
    apply_strict_live_debugger_readiness(args)
    run_dir = choose_run_dir(repo_root, args.output_root)
    summary = build_plan(args, repo_root, run_dir)
    write_outputs(summary)

    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "candidateTemplateJson": summary["artifacts"]["candidateTemplateJson"],
                    "rerunCommandText": summary["artifacts"]["rerunCommandText"],
                    "compactHandoffJson": summary["artifacts"]["compactHandoffJson"],
                    "compactHandoffMarkdown": summary["artifacts"]["compactHandoffMarkdown"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"summaryMarkdown={summary['artifacts']['summaryMarkdown']}")
        print(f"rerunCommandText={summary['artifacts']['rerunCommandText']}")
        print(f"compactHandoffJson={summary['artifacts']['compactHandoffJson']}")
        print(f"compactHandoffMarkdown={summary['artifacts']['compactHandoffMarkdown']}")
        if summary["blockers"]:
            print("blockers=" + ";".join(summary["blockers"]))
        if summary["warnings"]:
            print("warnings=" + ";".join(summary["warnings"]))
    return 2 if summary["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
