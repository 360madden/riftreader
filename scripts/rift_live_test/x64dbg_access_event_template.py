from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_POSE_COUNT = 3
PLANNER_SUMMARY_LATEST_ALIAS = "latest"


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def int_hex(value: int | str | None) -> str | None:
    if value is None:
        return None
    try:
        return f"0x{int(value, 0) if isinstance(value, str) else int(value):X}"
    except (TypeError, ValueError):
        return str(value).strip()


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


def is_latest_planner_summary_alias(value: Path | None) -> bool:
    return value is not None and str(value).strip().lower() == PLANNER_SUMMARY_LATEST_ALIAS


def find_latest_planner_summary(repo_root: Path) -> tuple[Path | None, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    capture_root = repo_root / "scripts" / "captures"
    candidates: list[tuple[datetime, float, str, Path]] = []
    for path in capture_root.glob("x64dbg-coord-chain-plan-*/coord-chain-plan-summary.json"):
        try:
            document = read_json_file(path)
        except Exception as exc:
            warnings.append(f"planner-summary-latest-skip-read-failed:{path}:{type(exc).__name__}")
            continue
        if not isinstance(document, dict):
            warnings.append(f"planner-summary-latest-skip-non-object:{path}")
            continue
        if document.get("status") != "planned":
            continue
        generated_at = parse_utc_sort_time(document.get("generatedAtUtc"), path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        candidates.append((generated_at, mtime, str(path), path))
    if not candidates:
        blockers.append(f"planner-summary-latest-not-found:{capture_root / 'x64dbg-coord-chain-plan-*/coord-chain-plan-summary.json'}")
        return None, blockers, warnings
    candidates.sort()
    return candidates[-1][3], blockers, warnings


def resolve_planner_summary_argument(args: argparse.Namespace, repo_root: Path) -> None:
    args.planner_summary_requested = str(args.planner_summary) if args.planner_summary else None
    args.planner_summary_resolved_from_alias = None
    args.planner_summary_resolution_blockers = []
    args.planner_summary_resolution_warnings = []
    if not is_latest_planner_summary_alias(args.planner_summary):
        return
    planner_summary, blockers, warnings = find_latest_planner_summary(repo_root)
    args.planner_summary_resolution_blockers.extend(blockers)
    args.planner_summary_resolution_warnings.extend(warnings)
    args.planner_summary_resolved_from_alias = PLANNER_SUMMARY_LATEST_ALIAS
    args.planner_summary = planner_summary


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"x64dbg-access-event-template-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def load_planner_summary(args: argparse.Namespace, repo_root: Path) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    blockers = list(getattr(args, "planner_summary_resolution_blockers", []) or [])
    warnings = list(getattr(args, "planner_summary_resolution_warnings", []) or [])
    if not args.planner_summary:
        blockers.append("missing-planner-summary")
        return None, blockers, warnings
    try:
        document = read_json_file(Path(args.planner_summary))
    except Exception as exc:
        blockers.append(f"planner-summary-read-failed:{type(exc).__name__}:{exc}")
        return None, blockers, warnings
    if not isinstance(document, dict):
        blockers.append("planner-summary-must-be-json-object")
        return None, blockers, warnings
    return document, blockers, warnings


def process_from_planner(planner: dict[str, Any]) -> dict[str, Any]:
    process = planner.get("process") if isinstance(planner.get("process"), dict) else {}
    return {
        "name": process.get("name") or DEFAULT_PROCESS_NAME,
        "pid": process.get("pid"),
        "hwnd": process.get("hwnd"),
        "startTimeUtc": process.get("startTimeUtc"),
    }


def validate_planner(planner: dict[str, Any], blockers: list[str], warnings: list[str]) -> None:
    if planner.get("status") != "planned":
        blockers.append(f"planner-summary-not-planned:{planner.get('status')}")
    readiness = planner.get("readiness") if isinstance(planner.get("readiness"), dict) else {}
    if readiness.get("status") == "blocked":
        blockers.append("planner-readiness-blocked")
    process = process_from_planner(planner)
    if not process.get("pid"):
        blockers.append("planner-missing-target-pid")
    if not process.get("hwnd"):
        blockers.append("planner-missing-target-hwnd")
    if not process.get("startTimeUtc"):
        blockers.append("planner-missing-process-start-time-utc")
    candidate = planner.get("candidate") if isinstance(planner.get("candidate"), dict) else {}
    if not candidate.get("address"):
        blockers.append("planner-missing-candidate-address")
    if not candidate.get("candidateId"):
        blockers.append("planner-missing-candidate-id")
    if not isinstance(planner.get("truthSurface"), dict):
        warnings.append("planner-missing-initial-truth-surface")


def event_shell(*, index: int, candidate_address: str | None, module_base: str | None) -> dict[str, Any]:
    event_id = f"pose-{index:03d}-hit-001"
    return {
        "eventId": event_id,
        "poseId": f"pose-{index:03d}",
        "hitAtUtc": None,
        "targetStillMatched": None,
        "access": "read",
        "truthSurface": {
            "kind": "api-now",
            "source": None,
            "sampledAtUtc": None,
            "x": None,
            "y": None,
            "z": None,
        },
        "memoryNow": {
            "address": candidate_address,
            "sampledAtUtc": None,
            "x": None,
            "y": None,
            "z": None,
        },
        "instruction": {
            "module": "rift_x64.exe",
            "moduleBase": module_base,
            "address": None,
            "rva": None,
            "bytes": None,
            "disassembly": None,
            "access": "read",
            "registers": {},
            "derivedObjectPointer": None,
            "fieldOffset": None,
        },
    }


def build_template(planner: dict[str, Any], pose_count: int | None) -> dict[str, Any]:
    process = process_from_planner(planner)
    candidate = planner.get("candidate") if isinstance(planner.get("candidate"), dict) else {}
    truth_surface = planner.get("truthSurface") if isinstance(planner.get("truthSurface"), dict) else {}
    candidate_address = candidate.get("address")
    module_base = (planner.get("process") or {}).get("moduleBaseAddressHex") if isinstance(planner.get("process"), dict) else None
    required_pose_count = int(pose_count or candidate.get("poseCountRequired") or DEFAULT_POSE_COUNT)
    axis_offsets = {"x": "0x0", "y": "0x4", "z": "0x8"}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-manual-access-events",
        "status": "template-needs-fill",
        "capturedAtUtc": None,
        "source": {
            "tool": "x64dbg",
            "captureMode": "manual-watchpoint",
            "templateGeneratedAtUtc": utc_iso(),
            "templateSource": "x64dbg_coord_chain_plan",
            "plannerSummary": planner.get("artifacts", {}).get("summaryJson") if isinstance(planner.get("artifacts"), dict) else None,
        },
        "process": process,
        "initialTruthSurface": truth_surface,
        "watchWindow": {
            "baseAddress": candidate_address,
            "sizeBytes": candidate.get("watchSizeBytes") or 12,
            "axisOrder": candidate.get("axisOrder") or "xyz",
            "axisOffsets": axis_offsets,
            "access": "read",
        },
        "events": [
            event_shell(index=index, candidate_address=candidate_address, module_base=module_base)
            for index in range(1, required_pose_count + 1)
        ],
        "derivedChain": {
            "rootKind": "pending-module-rva-or-static-owner",
            "module": "rift_x64.exe",
            "moduleBase": module_base,
            "rootRva": None,
            "offsets": [],
            "chainExpression": None,
        },
        "validation": {
            "restartValidated": False,
            "runtimeHelperReadback": False,
            "proofOnlyPassed": False,
        },
        "templateInstructions": [
            "Fill capturedAtUtc after the approved x64dbg capture starts.",
            "For each pose, fill hitAtUtc, targetStillMatched=true, fresh API truthSurface, memoryNow X/Y/Z, and instruction fields.",
            "Keep each truthSurface.sampledAtUtc within the ingester max-api-hit-skew-seconds window of its hitAtUtc.",
            "Keep access as read unless a write access was intentionally approved and captured; write access remains candidate-only.",
            "After filling, run scripts/x64dbg_access_event_ingest.py --events-json <this file> --json.",
        ],
    }


def markdown_summary(summary: dict[str, Any]) -> str:
    artifacts = summary.get("artifacts") or {}
    template = summary.get("template") or {}
    lines = [
        "# x64dbg manual access-event template summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Planner summary: `{summary.get('plannerSummary', {}).get('summaryPath')}`",
        f"- Template JSON: `{artifacts.get('templateJson')}`",
        f"- Event shells: `{summary.get('eventCount')}`",
        f"- Candidate: `{template.get('watchWindow', {}).get('baseAddress')}`",
        f"- Movement sent: `{str(summary.get('safety', {}).get('movementSent')).lower()}`",
        f"- x64dbg live attach started: `{str(summary.get('safety', {}).get('x64dbgLiveAttachStarted')).lower()}`",
        f"- x64dbg commands executed: `{str(summary.get('safety', {}).get('x64dbgCommandsExecuted')).lower()}`",
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This helper writes a fillable JSON template only. It does not attach x64dbg,",
            "read or write process memory, set breakpoints/watchpoints, or send game input.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_summary(
    *,
    args: argparse.Namespace,
    repo_root: Path,
    run_dir: Path,
    planner: dict[str, Any] | None,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    template = build_template(planner, args.pose_count) if planner and not blockers else None
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    template_json = run_dir / "x64dbg-manual-access-events-template.json"
    status = "blocked" if blockers else "passed"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-access-event-template",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "repoRoot": str(repo_root),
        "plannerSummary": {
            "requestedSummary": getattr(args, "planner_summary_requested", None),
            "resolvedFromAlias": getattr(args, "planner_summary_resolved_from_alias", None),
            "summaryPath": str(args.planner_summary) if args.planner_summary else None,
            "status": planner.get("status") if planner else None,
            "readiness": (planner.get("readiness") or {}).get("status") if isinstance(planner, dict) else None,
        },
        "eventCount": len(template.get("events") or []) if template else 0,
        "template": template,
        "blockers": blockers,
        "warnings": warnings,
        "errors": [],
        "safety": {
            "offlineOnly": True,
            "movementSent": False,
            "gameInputSent": False,
            "memoryRead": False,
            "memoryWritten": False,
            "breakpointsSet": False,
            "watchpointsSet": False,
            "x64dbgLiveAttachStarted": False,
            "x64dbgCommandsExecuted": False,
            "candidateOnly": True,
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "templateJson": str(template_json) if template else None,
        },
    }


def write_outputs(summary: dict[str, Any]) -> None:
    artifacts = summary["artifacts"]
    template = summary.get("template")
    if template:
        write_json(Path(artifacts["templateJson"]), template)
    write_text_atomic(Path(artifacts["summaryMarkdown"]), markdown_summary(summary))
    write_json(Path(artifacts["summaryJson"]), summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a fillable manual x64dbg access-event JSON template from a coordinate-chain planner summary."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument(
        "--planner-summary",
        type=Path,
        required=True,
        help="coord-chain-plan-summary.json path, or 'latest' for newest planned x64dbg-coord-chain-plan artifact.",
    )
    parser.add_argument("--pose-count", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    resolve_planner_summary_argument(args, repo_root)
    run_dir = choose_run_dir(repo_root, args.output_root)
    planner, blockers, warnings = load_planner_summary(args, repo_root)
    if planner:
        validate_planner(planner, blockers, warnings)
    summary = build_summary(
        args=args,
        repo_root=repo_root,
        run_dir=run_dir,
        planner=planner,
        blockers=blockers,
        warnings=warnings,
    )
    write_outputs(summary)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "templateJson": summary["artifacts"]["templateJson"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                    "errors": summary["errors"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        if summary["artifacts"].get("templateJson"):
            print(f"templateJson={summary['artifacts']['templateJson']}")
        if summary["blockers"]:
            print("blockers=" + ";".join(summary["blockers"]))
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
