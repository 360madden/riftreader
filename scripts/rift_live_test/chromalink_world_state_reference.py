from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_WORLD_STATE_URL = "http://127.0.0.1:7337/api/v1/riftreader/world-state"
DEFAULT_PROCESS_NAME = "rift_x64"
PREFLIGHT_SUMMARY_LATEST_ALIAS = "latest"
PREFLIGHT_SUMMARY_KIND = "x64dbg-target-preflight"


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


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


def normalize_hwnd(value: str | int | None) -> str | None:
    if value is None or value == "":
        return None
    try:
        return f"0x{int(str(value), 0):X}"
    except ValueError:
        return str(value).strip()


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


def bool_is_false(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return value.strip().lower() in {"0", "false", "no"}
    return not bool(value)


def parse_utc_datetime_value(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_utc_sort_time(value: Any, fallback_path: Path) -> datetime:
    parsed = parse_utc_datetime_value(value)
    if parsed is not None:
        return parsed
    try:
        return datetime.fromtimestamp(fallback_path.stat().st_mtime, tz=UTC)
    except OSError:
        return datetime.min.replace(tzinfo=UTC)


def is_latest_preflight_alias(value: Path | None) -> bool:
    return value is not None and str(value).lower() == PREFLIGHT_SUMMARY_LATEST_ALIAS


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


def fetch_world_state(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        status = int(response.status)
        body = response.read().decode("utf-8")
    if status < 200 or status >= 300:
        raise ValueError(f"world-state-http-status:{status}")
    document = json.loads(body)
    if not isinstance(document, dict):
        raise ValueError("world-state-json-must-be-object")
    return document


def load_world_state(args: argparse.Namespace) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []

    if args.self_test:
        observed_at = "2026-05-13T01:05:30Z"
        return (
            {
                "artifactKind": "riftreader-world-state",
                "contract": {"name": "chromalink-riftreader-world-state", "schemaVersion": 1},
                "ready": True,
                "healthy": True,
                "fresh": True,
                "stale": False,
                "navigation": {"playerPositionAvailable": True},
                "player": {
                    "position": {
                        "x": 7455.6,
                        "y": 876.25,
                        "z": 3053.75,
                        "observedAtUtc": observed_at,
                        "fresh": True,
                        "stale": False,
                    }
                },
            },
            blockers,
            warnings,
        )

    if args.world_state_file:
        try:
            document = read_json_file(Path(args.world_state_file))
        except Exception as exc:
            blockers.append(f"world-state-file-read-failed:{type(exc).__name__}:{exc}")
            return None, blockers, warnings
        if not isinstance(document, dict):
            blockers.append("world-state-json-must-be-object")
            return None, blockers, warnings
        return document, blockers, warnings

    try:
        return fetch_world_state(args.world_state_url, args.timeout_seconds), blockers, warnings
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        blockers.append(f"world-state-fetch-failed:{type(exc).__name__}:{exc}")
        return None, blockers, warnings


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


def apply_preflight_summary(args: argparse.Namespace) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    blockers = list(getattr(args, "preflight_summary_resolution_blockers", []) or [])
    warnings = list(getattr(args, "preflight_summary_resolution_warnings", []) or [])
    if not args.preflight_summary:
        return None, blockers, warnings

    try:
        document = read_json_file(Path(args.preflight_summary))
    except Exception as exc:
        blockers.append(f"preflight-summary-read-failed:{type(exc).__name__}:{exc}")
        return None, blockers, warnings
    if not isinstance(document, dict):
        blockers.append("preflight-summary-must-be-json-object")
        return None, blockers, warnings
    if document.get("kind") != PREFLIGHT_SUMMARY_KIND:
        blockers.append(f"preflight-summary-kind-mismatch:{document.get('kind')}")
        return document, blockers, warnings
    if document.get("status") != "passed":
        blockers.append(f"preflight-summary-status-not-passed:{document.get('status')}")
    selected = document.get("selectedTarget")
    if not isinstance(selected, dict):
        blockers.append("preflight-summary-missing-selected-target")
        return document, blockers, warnings

    selected_pid = to_int_or_none(selected.get("pid"))
    if selected_pid is not None:
        if args.target_pid is not None and int(args.target_pid) != selected_pid:
            blockers.append(f"target-pid-mismatch-preflight:{args.target_pid}!={selected_pid}")
        else:
            args.target_pid = selected_pid

    selected_hwnd = normalize_hwnd(first_present(selected.get("hwndHex"), selected.get("hwnd")))
    if selected_hwnd:
        if args.target_hwnd and normalize_hwnd(args.target_hwnd) != selected_hwnd:
            blockers.append(f"target-hwnd-mismatch-preflight:{normalize_hwnd(args.target_hwnd)}!={selected_hwnd}")
        else:
            args.target_hwnd = selected_hwnd

    selected_process_name = selected.get("processName")
    if selected_process_name:
        expected = str(args.process_name or DEFAULT_PROCESS_NAME).removesuffix(".exe").lower()
        actual = str(selected_process_name).removesuffix(".exe").lower()
        if actual != expected:
            blockers.append(f"process-name-mismatch-preflight:{actual}!={expected}")

    return document, blockers, warnings


def extract_position(document: dict[str, Any]) -> dict[str, Any] | None:
    position = get_nested_mapping_value(document, "player", "position")
    return position if isinstance(position, dict) else None


def validate_world_state(document: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    position = extract_position(document)
    if position is None:
        blockers.append("world-state-missing-player-position")
        position = {}

    x_value = to_float_or_none(get_mapping_value(position, "x", "X"))
    y_value = to_float_or_none(get_mapping_value(position, "y", "Y"))
    z_value = to_float_or_none(get_mapping_value(position, "z", "Z"))
    observed_at = first_present(
        get_mapping_value(position, "observedAtUtc", "ObservedAtUtc", "sampledAtUtc", "SampledAtUtc"),
        get_mapping_value(document, "observedAtUtc", "ObservedAtUtc", "generatedAtUtc", "GeneratedAtUtc"),
    )

    if x_value is None or y_value is None or z_value is None:
        blockers.append("world-state-missing-player-position-coordinate")
    if not observed_at:
        blockers.append("world-state-missing-player-position-observed-at")

    top_fresh = get_mapping_value(document, "fresh", "Fresh")
    top_stale = get_mapping_value(document, "stale", "Stale")
    ready = get_mapping_value(document, "ready", "Ready")
    healthy = get_mapping_value(document, "healthy", "Healthy")
    position_fresh = get_mapping_value(position, "fresh", "Fresh")
    position_stale = get_mapping_value(position, "stale", "Stale")
    nav_available = get_nested_mapping_value(document, "navigation", "playerPositionAvailable")

    if top_fresh is not None and bool_is_false(top_fresh):
        blockers.append("world-state-not-fresh")
    if bool_is_true(top_stale):
        blockers.append("world-state-stale")
    if ready is not None and bool_is_false(ready):
        blockers.append("world-state-not-ready")
    if healthy is not None and bool_is_false(healthy):
        blockers.append("world-state-not-healthy")
    if position_fresh is not None and bool_is_false(position_fresh):
        blockers.append("world-state-player-position-not-fresh")
    if bool_is_true(position_stale):
        blockers.append("world-state-player-position-stale")
    if nav_available is not None and bool_is_false(nav_available):
        blockers.append("world-state-navigation-player-position-unavailable")

    contract = get_mapping_value(document, "contract", "Contract")
    contract_name = get_mapping_value(contract, "name", "Name") if isinstance(contract, dict) else None
    artifact_kind = get_mapping_value(document, "artifactKind", "ArtifactKind")
    if artifact_kind is not None and str(artifact_kind) != "riftreader-world-state":
        warnings.append(f"world-state-artifact-kind-unexpected:{artifact_kind}")
    if contract_name is not None and str(contract_name) != "chromalink-riftreader-world-state":
        warnings.append(f"world-state-contract-name-unexpected:{contract_name}")

    extracted = {
        "x": x_value,
        "y": y_value,
        "z": z_value,
        "observedAtUtc": str(observed_at) if observed_at else None,
        "ready": ready,
        "healthy": healthy,
        "fresh": top_fresh,
        "stale": top_stale,
        "playerPositionFresh": position_fresh,
        "playerPositionStale": position_stale,
        "playerPositionAgeMs": get_mapping_value(position, "ageMs", "AgeMs"),
        "navigationPlayerPositionAvailable": nav_available,
        "contractName": contract_name,
        "artifactKind": artifact_kind,
    }
    return extracted, blockers, warnings


def build_reference_document(
    *,
    args: argparse.Namespace,
    generated_at_utc: str,
    world_state_json: Path,
    extracted: dict[str, Any],
    preflight_document: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": "chromalink-riftreader-world-state",
        "sourceView": "chromalink-riftreader-world-state",
        "status": "captured",
        "captured_at_utc": extracted["observedAtUtc"],
        "generatedAtUtc": generated_at_utc,
        "coordinate": {
            "x": extracted["x"],
            "y": extracted["y"],
            "z": extracted["z"],
            "capturedAtUtc": extracted["observedAtUtc"],
            "fresh": extracted.get("playerPositionFresh"),
            "stale": extracted.get("playerPositionStale"),
            "ageMs": extracted.get("playerPositionAgeMs"),
        },
        "processName": args.process_name,
        "processId": args.target_pid,
        "targetWindowHandle": normalize_hwnd(args.target_hwnd),
        "noCheatEngine": True,
        "movementSent": False,
        "savedVariablesUse": "none",
        "savedVariablesUsedAsLiveTruth": False,
        "fresh": extracted.get("playerPositionFresh"),
        "stale": extracted.get("playerPositionStale"),
        "ready": extracted.get("ready"),
        "healthy": extracted.get("healthy"),
        "navigationPlayerPositionAvailable": extracted.get("navigationPlayerPositionAvailable"),
        "worldStateFile": str(world_state_json),
        "preflightSummary": str(args.preflight_summary) if args.preflight_summary else None,
        "preflightGeneratedAtUtc": preflight_document.get("generatedAtUtc") if preflight_document else None,
        "safety": {
            "movementSent": False,
            "x64dbgLiveAttachStarted": False,
            "processAttachOrMemoryReadStarted": False,
            "savedVariablesUsedAsLiveTruth": False,
        },
    }


def markdown_summary(summary: dict[str, Any]) -> str:
    artifacts = summary.get("artifacts") or {}
    target = summary.get("target") or {}
    coordinate = summary.get("coordinate") or {}
    lines = [
        "# ChromaLink world-state coordinate reference",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- World-state JSON: `{artifacts.get('worldStateJson')}`",
        f"- Reference JSON: `{artifacts.get('referenceJson')}`",
        f"- Target: PID `{target.get('pid')}`, HWND `{target.get('hwnd')}`, process `{target.get('processName')}`",
        (
            "- Coordinate: "
            f"`X={coordinate.get('x')}`, `Y={coordinate.get('y')}`, `Z={coordinate.get('z')}` "
            f"at `{coordinate.get('observedAtUtc')}`"
        ),
        "",
        "## Safety",
        "",
        "- No game input sent.",
        "- No x64dbg attach started.",
        "- No process memory bytes read or written.",
        "- SavedVariables are not used as live truth.",
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"chromalink-world-state-reference-{utc_stamp()}"
    output_root = output_root.resolve()
    generated_at_utc = utc_iso()
    resolve_preflight_summary_argument(args, repo_root)
    preflight_document, preflight_blockers, preflight_warnings = apply_preflight_summary(args)
    world_state_document, world_state_load_blockers, world_state_load_warnings = load_world_state(args)

    blockers = list(preflight_blockers) + list(world_state_load_blockers)
    warnings = list(preflight_warnings) + list(world_state_load_warnings)
    extracted: dict[str, Any] = {
        "x": None,
        "y": None,
        "z": None,
        "observedAtUtc": None,
    }
    validation_blockers: list[str] = []
    validation_warnings: list[str] = []
    if world_state_document is not None:
        extracted, validation_blockers, validation_warnings = validate_world_state(world_state_document)
        blockers.extend(validation_blockers)
        warnings.extend(validation_warnings)

    if args.target_pid is None:
        blockers.append("missing-target-pid")
    if not normalize_hwnd(args.target_hwnd):
        blockers.append("missing-target-hwnd")

    world_state_json = output_root / "world-state.json"
    reference_json = (
        output_root / f"rift-api-reference-currentpid-{args.target_pid}-{utc_stamp()}.json"
        if args.target_pid is not None
        else None
    )
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    status = "passed" if not blockers else "blocked"

    reference_document = None
    if status == "passed" and reference_json is not None:
        reference_document = build_reference_document(
            args=args,
            generated_at_utc=generated_at_utc,
            world_state_json=world_state_json,
            extracted=extracted,
            preflight_document=preflight_document,
        )

    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "chromalink-world-state-coordinate-reference",
        "generatedAtUtc": generated_at_utc,
        "status": status,
        "input": {
            "worldStateUrl": None if args.world_state_file else args.world_state_url,
            "worldStateFile": str(args.world_state_file) if args.world_state_file else None,
            "inputMode": "self-test" if args.self_test else ("world-state-file" if args.world_state_file else "world-state-url"),
        },
        "preflight": {
            "requestedSummary": getattr(args, "preflight_summary_requested", None),
            "resolvedFromAlias": getattr(args, "preflight_summary_resolved_from_alias", None),
            "summaryPath": str(args.preflight_summary) if args.preflight_summary else None,
            "status": preflight_document.get("status") if preflight_document else None,
        },
        "target": {
            "processName": args.process_name,
            "pid": args.target_pid,
            "hwnd": normalize_hwnd(args.target_hwnd),
        },
        "coordinate": {
            "x": extracted.get("x"),
            "y": extracted.get("y"),
            "z": extracted.get("z"),
            "observedAtUtc": extracted.get("observedAtUtc"),
            "fresh": extracted.get("playerPositionFresh"),
            "stale": extracted.get("playerPositionStale"),
            "ageMs": extracted.get("playerPositionAgeMs"),
            "navigationPlayerPositionAvailable": extracted.get("navigationPlayerPositionAvailable"),
        },
        "worldState": {
            "artifactKind": extracted.get("artifactKind"),
            "contractName": extracted.get("contractName"),
            "ready": extracted.get("ready"),
            "healthy": extracted.get("healthy"),
            "fresh": extracted.get("fresh"),
            "stale": extracted.get("stale"),
        },
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "worldStateJson": str(world_state_json),
            "referenceJson": str(reference_json) if reference_document is not None else None,
        },
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "movementSent": False,
            "x64dbgLiveAttachStarted": False,
            "processAttachOrMemoryReadStarted": False,
            "targetMemoryBytesReadOrWritten": False,
            "savedVariablesUsedAsLiveTruth": False,
        },
    }

    output_root.mkdir(parents=True, exist_ok=True)
    if world_state_document is not None:
        write_json(world_state_json, world_state_document)
    if reference_document is not None and reference_json is not None:
        write_json(reference_json, reference_document)
    write_json(summary_json, summary)
    write_text_atomic(summary_md, markdown_summary(summary))
    return summary


def apply_self_test_defaults(args: argparse.Namespace) -> None:
    args.world_state_file = None
    args.preflight_summary = None
    args.target_pid = 12345
    args.target_hwnd = "0xABCDEF"
    args.process_name = DEFAULT_PROCESS_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture ChromaLink world-state as a planner-compatible API coordinate reference."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--world-state-url", default=DEFAULT_WORLD_STATE_URL)
    parser.add_argument("--world-state-file", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=2.0)
    parser.add_argument("--preflight-summary", type=Path, default=None, help="x64dbg_preflight.py summary.json or 'latest'.")
    parser.add_argument("--target-pid", type=int, default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        apply_self_test_defaults(args)
    summary = build_summary(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "worldStateJson": summary["artifacts"]["worldStateJson"],
                    "referenceJson": summary["artifacts"]["referenceJson"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"worldStateJson={summary['artifacts']['worldStateJson']}")
        print(f"referenceJson={summary['artifacts']['referenceJson']}")
        if summary["blockers"]:
            print("blockers:")
            for blocker in summary["blockers"]:
                print(f"  - {blocker}")
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
