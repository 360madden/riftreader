#!/usr/bin/env python3
"""Capture a durable Phase 1 selected-target evidence packet.

This helper does not select a target, send input, reload UI, or promote truth.
It records the current post-flush ReaderBridge target snapshot, then runs the
existing C# ``--read-target-current`` path and captures success or the exact
resolution blocker as structured evidence for target-entity discovery.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping


TOOL_VERSION = "riftreader-phase1-target-entity-snapshot-v0.1.0"
DEFAULT_READER_PROJECT = Path("reader") / "RiftReader.Reader" / "RiftReader.Reader.csproj"
DEFAULT_OUTPUT_ROOT = Path("scripts") / "captures"


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_stamp(now: datetime | None = None) -> str:
    value = now or utc_now()
    return value.strftime("%Y%m%d-%H%M%S-%f")


def iso_utc(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected top-level JSON object in {path}")
    return loaded


def safe_get(mapping: Mapping[str, Any] | None, *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def compact_target(target: Mapping[str, Any] | None) -> dict[str, Any]:
    target = target or {}
    coord = target.get("Coord") if isinstance(target.get("Coord"), Mapping) else {}
    cast = target.get("Cast") if isinstance(target.get("Cast"), Mapping) else {}
    return {
        "id": target.get("Id"),
        "name": target.get("Name"),
        "level": target.get("Level"),
        "calling": target.get("Calling"),
        "relation": target.get("Relation"),
        "role": target.get("Role"),
        "player": target.get("Player"),
        "hp": target.get("Hp"),
        "hpMax": target.get("HpMax"),
        "hpPct": target.get("HpPct"),
        "resourceKind": target.get("ResourceKind"),
        "resource": target.get("Resource"),
        "resourceMax": target.get("ResourceMax"),
        "distance": target.get("Distance"),
        "zone": target.get("Zone"),
        "locationName": target.get("LocationName"),
        "coord": {
            "x": coord.get("X"),
            "y": coord.get("Y"),
            "z": coord.get("Z"),
        },
        "cast": {
            "active": cast.get("Active"),
            "channeled": cast.get("Channeled"),
            "uninterruptible": cast.get("Uninterruptible"),
            "progressPct": cast.get("ProgressPct"),
            "text": cast.get("Text"),
        },
    }


def summarize_readerbridge_snapshot(snapshot: Mapping[str, Any], source_mtime_utc: str | None) -> dict[str, Any]:
    current = snapshot.get("Current") if isinstance(snapshot.get("Current"), Mapping) else {}
    target = current.get("Target") if isinstance(current.get("Target"), Mapping) else {}
    telemetry = current.get("Telemetry") if isinstance(current.get("Telemetry"), Mapping) else {}
    capabilities = telemetry.get("Capabilities") if isinstance(telemetry.get("Capabilities"), Mapping) else {}
    context = telemetry.get("Context") if isinstance(telemetry.get("Context"), Mapping) else {}
    target_present = bool(target) or bool(context.get("TargetPresent")) or bool(capabilities.get("TargetAvailable"))

    return {
        "sourceFile": snapshot.get("SourceFile"),
        "sourceLastWriteTimeUtc": source_mtime_utc,
        "loadedAtUtc": snapshot.get("LoadedAtUtc"),
        "lastExportAt": snapshot.get("LastExportAt"),
        "lastReason": snapshot.get("LastReason"),
        "exportCount": snapshot.get("ExportCount"),
        "sourceMode": current.get("SourceMode"),
        "sourceAddon": current.get("SourceAddon"),
        "status": current.get("Status"),
        "savedVariablesClassification": "post-flush-savedvariables",
        "savedVariablesUse": "post-flush selected-target bootstrap only; not live IPC",
        "targetPresent": target_present,
        "targetAvailable": bool(capabilities.get("TargetAvailable") or target_present),
        "targetId": context.get("TargetId") or target.get("Id"),
        "target": compact_target(target),
        "targetBuffLines": current.get("TargetBuffLines") if isinstance(current.get("TargetBuffLines"), list) else [],
        "targetDebuffLines": current.get("TargetDebuffLines") if isinstance(current.get("TargetDebuffLines"), list) else [],
    }


@dataclass
class CommandResult:
    label: str
    args: list[str]
    cwd: str
    started_at_utc: str
    ended_at_utc: str
    duration_seconds: float
    exit_code: int
    stdout_path: str
    stderr_path: str
    stdout_preview: str
    stderr_preview: str
    json_status: str
    parsed_json_path: str | None = None
    parse_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "args": self.args,
            "cwd": self.cwd,
            "startedAtUtc": self.started_at_utc,
            "endedAtUtc": self.ended_at_utc,
            "durationSeconds": self.duration_seconds,
            "exitCode": self.exit_code,
            "stdoutPath": self.stdout_path,
            "stderrPath": self.stderr_path,
            "stdoutPreview": self.stdout_preview,
            "stderrPreview": self.stderr_preview,
            "jsonStatus": self.json_status,
            "parsedJsonPath": self.parsed_json_path,
            "parseError": self.parse_error,
        }


def preview(text: str, max_chars: int = 1000) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def run_command(
    *,
    label: str,
    args: list[str],
    cwd: Path,
    output_dir: Path,
    timeout_seconds: float,
) -> tuple[CommandResult, dict[str, Any] | None]:
    started = utc_now()
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
    )
    ended = utc_now()

    stdout_path = output_dir / f"{label}.stdout.txt"
    stderr_path = output_dir / f"{label}.stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")

    parsed: dict[str, Any] | None = None
    parsed_json_path: str | None = None
    parse_error: str | None = None
    json_status = "not-json"
    if proc.stdout.strip():
        try:
            candidate = json.loads(proc.stdout)
            if isinstance(candidate, dict):
                parsed = candidate
                parsed_path = output_dir / f"{label}.json"
                parsed_path.write_text(json.dumps(candidate, indent=2, sort_keys=True), encoding="utf-8")
                parsed_json_path = str(parsed_path)
                json_status = "valid"
            else:
                parse_error = "top-level-json-not-object"
                json_status = "invalid"
        except json.JSONDecodeError as exc:
            parse_error = f"JSONDecodeError:{exc.msg}:line={exc.lineno}:column={exc.colno}"
            json_status = "invalid"

    result = CommandResult(
        label=label,
        args=args,
        cwd=str(cwd),
        started_at_utc=started.isoformat().replace("+00:00", "Z"),
        ended_at_utc=ended.isoformat().replace("+00:00", "Z"),
        duration_seconds=round((ended - started).total_seconds(), 3),
        exit_code=proc.returncode,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        stdout_preview=preview(proc.stdout),
        stderr_preview=preview(proc.stderr),
        json_status=json_status,
        parsed_json_path=parsed_json_path,
        parse_error=parse_error,
    )
    return result, parsed


def reader_family_blocker(text: str) -> str | None:
    match = re.search(r"family '([^']+)'", text)
    if match:
        return f"target-current-family-resolution-failed:{match.group(1)}"
    if "Unable to resolve a full current-target snapshot" in text:
        return "target-current-family-resolution-failed"
    return None


def build_markdown(summary: Mapping[str, Any]) -> str:
    target = safe_get(summary, "readerBridge", "target") or {}
    reader = summary.get("targetCurrentReader") if isinstance(summary.get("targetCurrentReader"), Mapping) else {}
    lines = [
        "# Phase 1 target entity snapshot",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- PID/HWND: `{safe_get(summary, 'target', 'processId')}` / `{safe_get(summary, 'target', 'targetWindowHandle')}`",
        f"- ReaderBridge target present: `{safe_get(summary, 'readerBridge', 'targetPresent')}`",
        f"- SavedVariables surface: `{safe_get(summary, 'readerBridge', 'savedVariablesClassification')}`",
        f"- Target: `{target.get('name')}` / `{target.get('id')}`",
        f"- Target HP: `{target.get('hp')}` / `{target.get('hpMax')}`",
        f"- Target level: `{target.get('level')}`",
        f"- Target coord: `{target.get('coord')}`",
        f"- Target-current reader status: `{reader.get('status')}`",
        f"- Target-current reader exit: `{reader.get('exitCode')}`",
        f"- Target-current family: `{reader.get('familyId')}`",
        "",
        "## Blockers",
    ]
    blockers = summary.get("blockers") if isinstance(summary.get("blockers"), list) else []
    if blockers:
        lines.extend(f"- `{item}`" for item in blockers)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Safety",
            f"- Movement sent by this helper: `{safe_get(summary, 'safety', 'movementSent')}`",
            f"- Input sent by this helper: `{safe_get(summary, 'safety', 'inputSent')}`",
            f"- Reload UI sent by this helper: `{safe_get(summary, 'safety', 'reloaduiSent')}`",
            f"- Target memory bytes read by this helper: `{safe_get(summary, 'safety', 'targetMemoryBytesRead')}`",
            f"- Target memory bytes written: `{safe_get(summary, 'safety', 'targetMemoryBytesWritten')}`",
            "",
            "SavedVariables are recorded as a deliberate post-flush snapshot only; this is not live IPC truth.",
        ]
    )
    return "\n".join(lines) + "\n"


def self_test() -> int:
    fixture = {
        "SourceFile": "ReaderBridgeExport.lua",
        "LoadedAtUtc": "2026-06-02T00:00:00Z",
        "LastExportAt": 1.0,
        "LastReason": "save-begin",
        "ExportCount": 3,
        "Current": {
            "Status": "ready",
            "SourceMode": "DirectAPI",
            "SourceAddon": "RiftAPI",
            "Target": {
                "Id": "u1",
                "Name": "Atank",
                "Level": 45,
                "Hp": 18208,
                "HpMax": 18208,
                "Coord": {"X": 1.0, "Y": 2.0, "Z": 3.0},
            },
            "Telemetry": {
                "Capabilities": {"TargetAvailable": True},
                "Context": {"TargetPresent": True, "TargetId": "u1"},
            },
        },
    }
    summary = summarize_readerbridge_snapshot(fixture, "2026-06-02T00:00:01Z")
    assert summary["targetPresent"] is True
    assert summary["target"]["name"] == "Atank"
    assert summary["target"]["coord"]["z"] == 3.0
    assert reader_family_blocker("Unable to resolve a full current-target snapshot from family 'fam-ABC'.") == (
        "target-current-family-resolution-failed:fam-ABC"
    )
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture Phase 1 selected-target evidence without selecting a target.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--hwnd", default=None)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--scan-context", type=int, default=512)
    parser.add_argument("--max-hits", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--skip-target-current-reader", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        return self_test()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_here()
    output_root = (repo_root / args.output_root).resolve() if not Path(args.output_root).is_absolute() else Path(args.output_root).resolve()
    output_dir = output_root / f"phase1-target-entity-snapshot-{utc_stamp()}"
    output_dir.mkdir(parents=True, exist_ok=True)

    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    readerbridge_summary: dict[str, Any] = {}
    target_current_summary: dict[str, Any] = {"status": "skipped"}
    target_memory_read = False

    reader_project = repo_root / DEFAULT_READER_PROJECT
    if not reader_project.exists():
        blockers.append(f"reader-project-missing:{reader_project}")

    try:
        snapshot_cmd = [
            "dotnet",
            "run",
            "--project",
            str(reader_project),
            "--",
            "--readerbridge-snapshot",
            "--json",
        ]
        snapshot_result, snapshot_json = run_command(
            label="readerbridge-snapshot",
            args=snapshot_cmd,
            cwd=repo_root,
            output_dir=output_dir,
            timeout_seconds=args.timeout_seconds,
        )
        commands.append(snapshot_result.as_dict())
        if snapshot_result.exit_code != 0:
            blockers.append(f"readerbridge-snapshot-exit:{snapshot_result.exit_code}")
        if not snapshot_json:
            blockers.append("readerbridge-snapshot-json-missing")
        else:
            source_file = Path(str(snapshot_json.get("SourceFile") or ""))
            source_mtime_utc = None
            if source_file.exists():
                source_mtime_utc = datetime.fromtimestamp(source_file.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")
            else:
                warnings.append(f"readerbridge-source-file-missing:{source_file}")
            readerbridge_summary = summarize_readerbridge_snapshot(snapshot_json, source_mtime_utc)
            if not readerbridge_summary.get("targetPresent"):
                blockers.append("readerbridge-target-not-present")

        if not args.skip_target_current_reader and not blockers:
            target_memory_read = True
            selector = ["--pid", str(args.pid)] if args.pid is not None else ["--process-name", args.process_name]
            target_cmd = [
                "dotnet",
                "run",
                "--project",
                str(reader_project),
                "--",
                *selector,
                "--read-target-current",
                "--scan-context",
                str(args.scan_context),
                "--max-hits",
                str(args.max_hits),
                "--json",
            ]
            target_result, target_json = run_command(
                label="target-current-reader",
                args=target_cmd,
                cwd=repo_root,
                output_dir=output_dir,
                timeout_seconds=args.timeout_seconds,
            )
            commands.append(target_result.as_dict())
            target_current_summary = {
                "status": "passed" if target_result.exit_code == 0 and target_json else "blocked",
                "exitCode": target_result.exit_code,
                "jsonStatus": target_result.json_status,
                "stdoutPreview": target_result.stdout_preview,
                "stderrPreview": target_result.stderr_preview,
                "parsedJsonPath": target_result.parsed_json_path,
                "familyId": None,
            }
            combined = "\n".join([target_result.stdout_preview, target_result.stderr_preview])
            family_blocker = reader_family_blocker(combined)
            if family_blocker:
                blockers.append(family_blocker)
                target_current_summary["familyId"] = family_blocker.rsplit(":", 1)[-1]
            elif target_result.exit_code != 0:
                blockers.append(f"target-current-reader-exit:{target_result.exit_code}")
            elif target_json and target_json.get("HasTarget") is False:
                blockers.append("target-current-reader-has-target-false")
            if target_json:
                target_current_summary["readerJson"] = {
                    "mode": target_json.get("Mode"),
                    "hasTarget": target_json.get("HasTarget"),
                    "familyId": target_json.get("FamilyId"),
                    "selectionSource": target_json.get("SelectionSource"),
                    "anchorProvenance": target_json.get("AnchorProvenance"),
                    "memoryAddressHex": safe_get(target_json, "Memory", "AddressHex"),
                    "match": target_json.get("Match"),
                }
                if target_json.get("FamilyId"):
                    target_current_summary["familyId"] = target_json.get("FamilyId")
        elif args.skip_target_current_reader:
            warnings.append("target-current-reader-skipped")
    except subprocess.TimeoutExpired as exc:
        blockers.append(f"command-timeout:{exc.cmd}")
        errors.append({"type": "TimeoutExpired", "message": str(exc), "stage": "command"})
    except Exception as exc:  # pragma: no cover - error envelope path.
        blockers.append("phase1-target-entity-snapshot-exception")
        errors.append({"type": type(exc).__name__, "message": str(exc), "stage": "main"})

    status = "passed" if not blockers and not errors else "blocked"
    verdict = "phase1-target-current-reader-passed" if status == "passed" else "phase1-target-evidence-captured-reader-blocked"

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "riftreader-phase1-target-entity-snapshot",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": iso_utc(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(repo_root),
        "target": {
            "processName": args.process_name,
            "processId": args.pid,
            "targetWindowHandle": args.hwnd,
        },
        "readerBridge": readerbridge_summary,
        "targetCurrentReader": target_current_summary,
        "commands": commands,
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "providerWrites": False,
            "gitMutation": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "targetMemoryBytesRead": target_memory_read,
            "targetMemoryBytesWritten": False,
            "savedVariablesUsedAsLiveTruth": False,
            "savedVariablesReadAsPostFlushSnapshot": True,
        },
        "artifacts": {
            "outputDirectory": str(output_dir),
            "summaryJson": str(output_dir / "summary.json"),
            "summaryMarkdown": str(output_dir / "summary.md"),
        },
        "next": {
            "recommendedAction": (
                "Use this post-flush target snapshot to debug the C# target family resolver, "
                "then repeat with a non-self target once a hostile/friendly unit can be reliably selected."
            )
        },
    }

    summary_path = output_dir / "summary.json"
    markdown_path = output_dir / "summary.md"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(build_markdown(summary), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"status={status}")
        print(f"summaryJson={summary_path}")
        print(f"summaryMarkdown={markdown_path}")
        if blockers:
            print("blockers=" + ",".join(blockers))

    return 0 if status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
