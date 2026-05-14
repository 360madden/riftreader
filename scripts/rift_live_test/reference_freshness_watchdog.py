from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
RRAPICOORD_MARKER_PATTERN = re.compile(r"RRAPICOORD1\|[^\x00\r\n]+?(?:savedVariablesUse=[^|\s\x00\r\n]+)")


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return document


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def path_text(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def normalize_hwnd(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        return f"0x{int(str(value), 0):X}"
    except ValueError:
        return str(value)


def latest_file(paths: Sequence[Path]) -> Path | None:
    existing = [path for path in paths if path.exists() and path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: (path.stat().st_mtime, str(path)))


def latest_chromalink_summary(repo_root: Path) -> Path | None:
    return latest_file(list((repo_root / "scripts" / "captures").glob("chromalink-world-state-reference-*/summary.json")))


def latest_rrapicoord_scan(repo_root: Path, target_pid: int | None) -> Path | None:
    capture_root = repo_root / "scripts" / "captures"
    pattern = f"rift-api-reference-scan-currentpid-{target_pid}-*.json" if target_pid is not None else "rift-api-reference-scan-currentpid-*.json"
    return latest_file(list(capture_root.glob(pattern)))


def target_mismatches(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> list[str]:
    mismatches: list[str] = []
    expected_pid = expected.get("pid")
    observed_pid = observed.get("pid")
    if expected_pid is not None and observed_pid is not None and int(expected_pid) != int(observed_pid):
        mismatches.append(f"pid:{expected_pid}!={observed_pid}")
    expected_hwnd = normalize_hwnd(expected.get("hwnd"))
    observed_hwnd = normalize_hwnd(observed.get("hwnd"))
    if expected_hwnd and observed_hwnd and expected_hwnd != observed_hwnd:
        mismatches.append(f"hwnd:{expected_hwnd}!={observed_hwnd}")
    expected_process = str(expected.get("processName") or "").lower().removesuffix(".exe")
    observed_process = str(observed.get("processName") or "").lower().removesuffix(".exe")
    if expected_process and observed_process and expected_process != observed_process:
        mismatches.append(f"processName:{expected_process}!={observed_process}")
    return mismatches


def summarize_chromalink(path: Path | None, repo_root: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    if path is None:
        return {
            "path": None,
            "status": "missing",
            "fresh": False,
            "usable": False,
            "blockers": ["chromalink-summary-not-found"],
            "warnings": [],
        }
    try:
        document = load_json_object(path)
    except Exception as exc:
        return {
            "path": path_text(path, repo_root),
            "status": "read-failed",
            "fresh": False,
            "usable": False,
            "blockers": [f"chromalink-summary-read-failed:{type(exc).__name__}:{exc}"],
            "warnings": [],
        }
    target = safe_dict(document.get("target"))
    coordinate = safe_dict(document.get("coordinate"))
    world_state = safe_dict(document.get("worldState"))
    diagnostics = safe_dict(document.get("diagnostics"))
    aggregate_freshness = safe_dict(diagnostics.get("aggregateFreshness"))
    observed = {
        "pid": target.get("pid"),
        "hwnd": target.get("hwnd"),
        "processName": target.get("processName"),
    }
    mismatches = target_mismatches(expected, observed)
    blockers = list(safe_list(document.get("blockers")))
    blockers.extend(f"chromalink-target-mismatch:{mismatch}" for mismatch in mismatches)
    fresh = (
        document.get("status") == "passed"
        and not blockers
        and coordinate.get("fresh") is True
        and coordinate.get("stale") is not True
        and coordinate.get("x") is not None
        and coordinate.get("y") is not None
        and coordinate.get("z") is not None
    )
    return {
        "path": path_text(path, repo_root),
        "status": document.get("status"),
        "fresh": fresh,
        "usable": fresh,
        "generatedAtUtc": document.get("generatedAtUtc"),
        "target": observed,
        "coordinate": {
            "x": coordinate.get("x"),
            "y": coordinate.get("y"),
            "z": coordinate.get("z"),
            "observedAtUtc": coordinate.get("observedAtUtc"),
            "fresh": coordinate.get("fresh"),
            "stale": coordinate.get("stale"),
            "ageMs": coordinate.get("ageMs"),
            "navigationPlayerPositionAvailable": coordinate.get("navigationPlayerPositionAvailable"),
        },
        "worldState": {
            "ready": world_state.get("ready"),
            "healthy": world_state.get("healthy"),
            "fresh": world_state.get("fresh"),
            "stale": world_state.get("stale"),
        },
        "diagnostics": {
            "snapshotGeneratedAtUtc": diagnostics.get("snapshotGeneratedAtUtc"),
            "aggregateLastUpdatedUtc": diagnostics.get("aggregateLastUpdatedUtc"),
            "newestFrameAgeMs": aggregate_freshness.get("newestFrameAgeMs"),
            "freshFrameCount": aggregate_freshness.get("freshFrameCount"),
            "staleFrameCount": aggregate_freshness.get("staleFrameCount"),
        },
        "blockers": blockers,
        "warnings": safe_list(document.get("warnings")),
    }


def marker_fields(marker: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    parts = marker.split("|")
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key] = value
    return fields


def marker_is_usable(fields: Mapping[str, str]) -> bool:
    if fields.get("status", "").lower() != "pass":
        return False
    if fields.get("source", "").lower() != "rift-api":
        return False
    if fields.get("savedVariablesUse", "").lower() != "none":
        return False
    try:
        float(fields["x"])
        float(fields["y"])
        float(fields["z"])
    except (KeyError, TypeError, ValueError):
        return False
    return True


def scan_texts(scan: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for hit in safe_list(scan.get("Hits")):
        if not isinstance(hit, dict):
            continue
        context = safe_dict(hit.get("Context"))
        for key in ("AsciiPreview", "Utf16Preview"):
            value = context.get(key)
            if value:
                texts.append(str(value))
    return texts


def extract_rrapicoord_markers(scan: Mapping[str, Any]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for text in scan_texts(scan):
        for match in RRAPICOORD_MARKER_PATTERN.finditer(text):
            marker = match.group(0)
            if marker in seen:
                continue
            seen.add(marker)
            fields = marker_fields(marker)
            markers.append(
                {
                    "raw": marker,
                    "fields": fields,
                    "usable": marker_is_usable(fields),
                }
            )
    return markers


def summarize_rrapicoord(path: Path | None, repo_root: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    if path is None:
        return {
            "path": None,
            "status": "missing",
            "fresh": False,
            "usable": False,
            "blockers": ["rrapicoord-scan-not-found"],
            "warnings": [],
        }
    try:
        document = load_json_object(path)
    except Exception as exc:
        return {
            "path": path_text(path, repo_root),
            "status": "read-failed",
            "fresh": False,
            "usable": False,
            "blockers": [f"rrapicoord-scan-read-failed:{type(exc).__name__}:{exc}"],
            "warnings": [],
        }
    observed = {
        "pid": document.get("ProcessId"),
        "processName": document.get("ProcessName"),
        "hwnd": None,
    }
    mismatches = target_mismatches({k: v for k, v in expected.items() if k != "hwnd"}, observed)
    markers = extract_rrapicoord_markers(document)
    usable_markers = [marker for marker in markers if marker.get("usable")]
    blockers: list[str] = []
    blockers.extend(f"rrapicoord-target-mismatch:{mismatch}" for mismatch in mismatches)
    if not usable_markers:
        blockers.append("rrapicoord-no-usable-marker")
    selected = usable_markers[0] if usable_markers else None
    selected_fields = safe_dict(selected.get("fields")) if selected else {}
    return {
        "path": path_text(path, repo_root),
        "status": "passed" if not blockers else "blocked",
        "fresh": bool(usable_markers) and not blockers,
        "usable": bool(usable_markers) and not blockers,
        "target": observed,
        "hitCount": document.get("HitCount"),
        "markerCount": len(markers),
        "usableMarkerCount": len(usable_markers),
        "selectedCoordinate": {
            "x": selected_fields.get("x"),
            "y": selected_fields.get("y"),
            "z": selected_fields.get("z"),
            "sampledAt": selected_fields.get("sampledAt"),
            "seq": selected_fields.get("seq"),
        }
        if selected
        else None,
        "blockers": blockers,
        "warnings": [],
    }


def verdict_for(chromalink: Mapping[str, Any], rrapicoord: Mapping[str, Any]) -> str:
    if chromalink.get("usable"):
        return "fresh-reference-ready:chromalink"
    if rrapicoord.get("usable"):
        return "fresh-reference-ready:rrapicoord"
    return "blocked-fresh-reference-unavailable"


def markdown_summary(summary: Mapping[str, Any]) -> str:
    chroma = safe_dict(summary.get("chromalink"))
    rrapi = safe_dict(summary.get("rrapicoord"))
    lines = [
        "# Reference freshness watchdog",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Movement sent: `{str(safe_dict(summary.get('safety')).get('movementSent')).lower()}`",
        f"- Input sent: `{str(safe_dict(summary.get('safety')).get('inputSent')).lower()}`",
        f"- Process memory read by this helper: `{str(safe_dict(summary.get('safety')).get('processMemoryReadByThisHelper')).lower()}`",
        "",
        "## Sources",
        "",
        "| Source | Status | Usable | Artifact | Key detail |",
        "|---|---|---|---|---|",
        (
            f"| ChromaLink | `{chroma.get('status')}` | `{str(chroma.get('usable')).lower()}` | "
            f"`{chroma.get('path')}` | `ageMs={safe_dict(chroma.get('coordinate')).get('ageMs')}` |"
        ),
        (
            f"| RRAPICOORD | `{rrapi.get('status')}` | `{str(rrapi.get('usable')).lower()}` | "
            f"`{rrapi.get('path')}` | `hits={rrapi.get('hitCount')}; usableMarkers={rrapi.get('usableMarkerCount')}` |"
        ),
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in safe_list(summary.get("warnings")))
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"reference-freshness-watchdog-{utc_stamp()}"
    output_root = output_root.resolve()
    expected = {
        "processName": args.process_name,
        "pid": args.target_pid,
        "hwnd": args.target_hwnd,
    }
    chromalink_path = args.chromalink_summary or latest_chromalink_summary(repo_root)
    rrapicoord_path = args.rrapicoord_scan or latest_rrapicoord_scan(repo_root, args.target_pid)
    chromalink = summarize_chromalink(chromalink_path, repo_root, expected)
    rrapicoord = summarize_rrapicoord(rrapicoord_path, repo_root, expected)
    blockers = [f"chromalink:{blocker}" for blocker in safe_list(chromalink.get("blockers"))]
    blockers.extend(f"rrapicoord:{blocker}" for blocker in safe_list(rrapicoord.get("blockers")))
    warnings = [f"chromalink:{warning}" for warning in safe_list(chromalink.get("warnings"))]
    warnings.extend(f"rrapicoord:{warning}" for warning in safe_list(rrapicoord.get("warnings")))
    verdict = verdict_for(chromalink, rrapicoord)
    if verdict.startswith("fresh-reference-ready"):
        status = "passed"
        blockers = []
    else:
        status = "blocked"
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "reference-freshness-watchdog",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "target": expected,
        "chromalink": chromalink,
        "rrapicoord": rrapicoord,
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "x64dbgAttached": False,
            "cheatEngineUsed": False,
            "processMemoryReadByThisHelper": False,
            "targetMemoryWritten": False,
            "savedVariablesUsedAsLiveTruth": False,
            "candidateOnly": True,
            "promotionEligible": verdict.startswith("fresh-reference-ready"),
        },
        "next": {
            "recommendedAction": (
                "Run same-target read-only proof/readback before ProofOnly."
                if verdict.startswith("fresh-reference-ready")
                else "Refresh/fix ChromaLink or RRAPICOORD before proof promotion; do not spend more candidate scans as proof."
            )
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(summary_json, summary)
    write_text_atomic(summary_md, markdown_summary(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize whether existing reference artifacts are fresh enough for proof promotion.")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--chromalink-summary", type=Path)
    parser.add_argument("--rrapicoord-scan", type=Path)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--target-hwnd", required=True)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_summary(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "verdict": summary["verdict"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"verdict={summary['verdict']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        if summary["blockers"]:
            print("blockers:")
            for blocker in summary["blockers"]:
                print(f"  - {blocker}")
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
