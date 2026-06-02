#!/usr/bin/env python3
"""Build the browser dashboard live-data payload.

This is the Python-first successor to the legacy PowerShell live-data builder.
It preserves the existing ``window.DASHBOARD_LIVE_DATA`` contract while adding
schema v2 fields for the truth banner, next safe action, and Phase 1 target
cards. It is read-only with respect to RIFT/game state: it can read local repo
artifacts and invoke existing reader commands, but it never sends input, writes
target memory, attaches debuggers, promotes truth, or mutates Git state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TOOL_VERSION = "dashboard-live-data-v2-python-0.1.0"
DEFAULT_STALE_AFTER_SECONDS = 10


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def to_number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def get_any(mapping: Any, *names: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default

    lowered = {str(key).lower(): key for key in mapping.keys()}
    for name in names:
        if name in mapping:
            return mapping[name]
        key = lowered.get(name.lower())
        if key is not None:
            return mapping[key]
    return default


def get_nested(mapping: Any, *names: str, default: Any = None) -> Any:
    current = mapping
    for name in names:
        current = get_any(current, name, default=None)
        if current is None:
            return default
    return current


def parse_json_text(text: str) -> tuple[Any | None, str | None]:
    stripped = (text or "").strip()
    if not stripped:
        return None, "empty-json-output"

    try:
        return json.loads(stripped), None
    except json.JSONDecodeError:
        pass

    starts = [index for index in (stripped.find("{"), stripped.find("[")) if index >= 0]
    if not starts:
        return None, "no-json-start-found"
    start = min(starts)
    end = max(stripped.rfind("}"), stripped.rfind("]"))
    if end < start:
        return None, "no-json-end-found"

    try:
        return json.loads(stripped[start : end + 1]), None
    except json.JSONDecodeError as exc:
        return None, f"json-parse-error: {exc}"


def preview(text: str, limit: int = 1400) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


@dataclass
class CommandResult:
    label: str
    args: list[str]
    cwd: str
    startedAtUtc: str
    endedAtUtc: str
    durationSeconds: float
    exitCode: int | None
    ok: bool
    timedOut: bool
    stdoutPreview: str
    stderrPreview: str
    parsedJson: Any | None = None
    parseError: str | None = None
    error: str | None = None

    def envelope(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "args": self.args,
            "cwd": self.cwd,
            "startedAtUtc": self.startedAtUtc,
            "endedAtUtc": self.endedAtUtc,
            "durationSeconds": self.durationSeconds,
            "exitCode": self.exitCode,
            "ok": self.ok,
            "timedOut": self.timedOut,
            "stdoutPreview": self.stdoutPreview,
            "stderrPreview": self.stderrPreview,
            "jsonStatus": "valid" if self.parsedJson is not None else "invalid" if self.parseError else "not-requested",
            "parseError": self.parseError,
            "error": self.error,
        }


def run_command(
    label: str,
    args: list[str],
    cwd: Path,
    timeout_seconds: float,
    *,
    parse_json: bool = False,
    expected_exit_codes: tuple[int, ...] = (0,),
) -> CommandResult:
    started = time.monotonic()
    started_at = utc_now()
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    timed_out = False
    error: str | None = None
    parsed: Any | None = None
    parse_error: str | None = None

    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
        error = f"timeout-after-{timeout_seconds:g}s"
    except Exception as exc:  # noqa: BLE001 - captured into payload for operator diagnosis.
        error = f"{type(exc).__name__}: {exc}"

    if parse_json and stdout and not timed_out:
        parsed, parse_error = parse_json_text(stdout)

    ended_at = utc_now()
    duration = round(time.monotonic() - started, 3)
    ok = exit_code in expected_exit_codes and not timed_out and error is None and (not parse_json or parsed is not None)
    return CommandResult(
        label=label,
        args=args,
        cwd=str(cwd),
        startedAtUtc=started_at,
        endedAtUtc=ended_at,
        durationSeconds=duration,
        exitCode=exit_code,
        ok=ok,
        timedOut=timed_out,
        stdoutPreview=preview(stdout),
        stderrPreview=preview(stderr),
        parsedJson=parsed,
        parseError=parse_error,
        error=error,
    )


def source_state(status: str, updated_at: str, *, using_previous: bool = False, fallback: str = "", error: str = "") -> dict[str, Any]:
    return {
        "status": status,
        "updatedAt": updated_at,
        "usingPrevious": using_previous,
        "fallback": fallback,
        "error": error,
    }


def source_state_from_command(result: CommandResult | None, updated_at: str) -> dict[str, Any]:
    if result is None:
        return source_state("skipped", updated_at, fallback="command-not-run")
    if result.ok:
        return source_state("active", updated_at)
    return source_state("partial", updated_at, error=result.error or result.parseError or result.stderrPreview or "command-failed")


def parse_git_status(stdout: str, repo_root: Path, generated_at: str) -> dict[str, Any]:
    lines = [line.rstrip("\n") for line in (stdout or "").splitlines() if line.strip()]
    branch_line = lines[0] if lines and lines[0].startswith("## ") else ""
    branch_text = branch_line[3:] if branch_line else ""
    current_branch = branch_text.split("...", 1)[0].split(" ", 1)[0] if branch_text else ""
    changes = lines[1:] if branch_line else lines
    counts = {"modified": 0, "added": 0, "deleted": 0, "renamed": 0, "untracked": 0}
    for line in changes:
        status = line[:2]
        if status == "??":
            counts["untracked"] += 1
        if "M" in status:
            counts["modified"] += 1
        if "A" in status:
            counts["added"] += 1
        if "D" in status:
            counts["deleted"] += 1
        if "R" in status:
            counts["renamed"] += 1

    return {
        "repoPath": str(repo_root),
        "currentBranch": current_branch,
        "changedFileCount": len(changes),
        "dirty": bool(changes),
        "dirtyCounts": counts,
        "changes": changes[:16],
        "updatedAt": generated_at,
    }


def map_health(unit: dict[str, Any] | None, read_json: dict[str, Any] | None) -> dict[str, Any]:
    memory = get_any(read_json, "Memory", default={})
    expected = get_any(read_json, "Expected", default={})
    match = get_any(read_json, "Match", default={})
    return {
        "current": to_number(get_any(unit, "Hp", "hp", default=get_any(expected, "Health"))),
        "max": to_number(get_any(unit, "HpMax", "hpMax", default=get_any(expected, "HealthMax"))),
        "percent": to_number(get_any(unit, "HpPct", "hpPct")),
        "memory": to_number(get_any(memory, "Health")),
        "expected": to_number(get_any(expected, "Health")),
        "matches": get_any(match, "HealthMatches"),
    }


def map_level(unit: dict[str, Any] | None, read_json: dict[str, Any] | None) -> dict[str, Any]:
    memory = get_any(read_json, "Memory", default={})
    expected = get_any(read_json, "Expected", default={})
    match = get_any(read_json, "Match", default={})
    return {
        "current": to_number(get_any(unit, "Level", "level", default=get_any(expected, "Level"))),
        "memory": to_number(get_any(memory, "Level")),
        "expected": to_number(get_any(expected, "Level")),
        "matches": get_any(match, "LevelMatches"),
    }


def map_coords(unit: dict[str, Any] | None, read_json: dict[str, Any] | None) -> dict[str, Any]:
    coord = get_any(unit, "Coord", "coord", default={})
    memory = get_any(read_json, "Memory", default={})
    expected = get_any(read_json, "Expected", default={})
    return {
        "x": to_number(get_any(coord, "X", "x", default=get_any(expected, "CoordX"))),
        "y": to_number(get_any(coord, "Y", "y", default=get_any(expected, "CoordY"))),
        "z": to_number(get_any(coord, "Z", "z", default=get_any(expected, "CoordZ"))),
        "memoryX": to_number(get_any(memory, "CoordX")),
        "memoryY": to_number(get_any(memory, "CoordY")),
        "memoryZ": to_number(get_any(memory, "CoordZ")),
        "expectedX": to_number(get_any(expected, "CoordX")),
        "expectedY": to_number(get_any(expected, "CoordY")),
        "expectedZ": to_number(get_any(expected, "CoordZ")),
    }


def map_resource(unit: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "kind": get_any(unit, "ResourceKind", "resourceKind", default=""),
        "current": to_number(get_any(unit, "Resource", "resource")),
        "max": to_number(get_any(unit, "ResourceMax", "resourceMax")),
        "percent": to_number(get_any(unit, "ResourcePct", "resourcePct")),
    }


def map_anchor(read_json: dict[str, Any] | None) -> dict[str, Any]:
    memory = get_any(read_json, "Memory", default={})
    return {
        "address": get_any(memory, "AddressHex"),
        "familyId": get_any(read_json, "FamilyId"),
        "familyNotes": get_any(read_json, "FamilyNotes"),
        "signature": get_any(read_json, "Signature"),
        "selectionSource": get_any(read_json, "SelectionSource"),
        "anchorProvenance": get_any(read_json, "AnchorProvenance"),
        "anchorCacheFile": get_any(read_json, "AnchorCacheFile"),
        "anchorCacheUsed": get_any(read_json, "AnchorCacheUsed"),
        "anchorCacheUpdated": get_any(read_json, "AnchorCacheUpdated"),
        "confirmationFile": get_any(read_json, "ConfirmationFile"),
    }


def map_unit_payload(
    unit: dict[str, Any] | None,
    read_json: dict[str, Any] | None,
    *,
    generated_at: str,
    source_file: str | None,
    is_target: bool,
) -> dict[str, Any]:
    unit = unit if isinstance(unit, dict) else {}
    read_json = read_json if isinstance(read_json, dict) else {}
    expected = get_any(read_json, "Expected", default={})
    match = get_any(read_json, "Match")
    has_target = get_any(read_json, "HasTarget", default=True)
    available = bool(unit or read_json)
    if is_target and has_target is False:
        available = True

    payload = {
        "available": available,
        "updatedAt": generated_at,
        "sourceMode": "memory+snapshot" if read_json and unit else "memory" if read_json else "snapshot" if unit else "unavailable",
        "sourceFile": source_file,
        "name": get_any(unit, "Name", "name", default=get_any(expected, "Name", default="")),
        "role": get_any(unit, "Role", "role", default=""),
        "location": get_any(unit, "LocationName", "locationName", default=get_any(unit, "Zone", "zone", default="")),
        "level": map_level(unit, read_json),
        "health": map_health(unit, read_json),
        "resource": map_resource(unit),
        "coords": map_coords(unit, read_json),
        "memoryMatch": match,
        "anchor": map_anchor(read_json),
        "process": {
            "processId": get_any(read_json, "ProcessId"),
            "processName": get_any(read_json, "ProcessName"),
        },
    }
    if is_target:
        payload["hasTarget"] = bool(has_target)
        payload["distance"] = {
            "current": to_number(get_any(unit, "Distance", "distance")),
            "memory": to_number(get_nested(read_json, "Memory", "Distance")),
            "expected": to_number(get_nested(read_json, "Expected", "Distance")),
            "matches": get_nested(read_json, "Match", "DistanceMatchesWithinTolerance"),
            "delta": to_number(get_nested(read_json, "Match", "DistanceDelta")),
        }
    return payload


def map_snapshot(snapshot_json: dict[str, Any] | None, generated_at: str) -> dict[str, Any]:
    snapshot_json = snapshot_json if isinstance(snapshot_json, dict) else {}
    current = get_any(snapshot_json, "Current", default={})
    return {
        "available": bool(snapshot_json),
        "updatedAt": generated_at,
        "sourceFile": get_any(snapshot_json, "SourceFile"),
        "loadedAt": get_any(snapshot_json, "LoadedAtUtc"),
        "exportCount": get_any(snapshot_json, "ExportCount", default=get_any(current, "ExportCount")),
        "lastReason": get_any(snapshot_json, "LastReason"),
        "status": get_any(current, "Status"),
        "exportReason": get_any(current, "ExportReason"),
        "sourceMode": get_any(current, "SourceMode"),
        "sourceAddon": get_any(current, "SourceAddon"),
        "sourceVersion": get_any(current, "SourceVersion"),
        "generatedAtReal": get_any(current, "GeneratedAtRealtime"),
        "playerName": get_nested(current, "Player", "Name"),
        "targetName": get_nested(current, "Target", "Name"),
    }


def latest_phase1_summary(repo_root: Path) -> tuple[dict[str, Any] | None, Path | None, str | None]:
    captures = repo_root / "scripts" / "captures"
    if not captures.is_dir():
        return None, None, "scripts-captures-missing"

    candidates = sorted(captures.glob("phase1-target-entity-snapshot-*/summary.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        return None, None, "phase1-summary-missing"

    path = candidates[0]
    try:
        return json.loads(path.read_text(encoding="utf-8")), path, None
    except Exception as exc:  # noqa: BLE001
        return None, path, f"{type(exc).__name__}: {exc}"


def compact_phase1(summary: dict[str, Any] | None, path: Path | None, error: str | None) -> dict[str, Any]:
    if not summary:
        return {
            "available": False,
            "status": "unavailable",
            "sourceFile": str(path) if path else None,
            "error": error,
            "blockers": [error] if error else ["phase1-summary-unavailable"],
        }

    reader_bridge = get_any(summary, "readerBridge", default={})
    target_reader = get_any(summary, "targetCurrentReader", default={})
    return {
        "available": True,
        "sourceFile": str(path) if path else None,
        "generatedAtUtc": get_any(summary, "generatedAtUtc"),
        "status": get_any(summary, "status"),
        "verdict": get_any(summary, "verdict"),
        "artifacts": get_any(summary, "artifacts", default={}),
        "blockers": get_any(summary, "blockers", default=[]),
        "warnings": get_any(summary, "warnings", default=[]),
        "readerBridge": {
            "status": get_any(reader_bridge, "status"),
            "targetPresent": get_any(reader_bridge, "targetPresent"),
            "targetAvailable": get_any(reader_bridge, "targetAvailable"),
            "targetId": get_any(reader_bridge, "targetId"),
            "target": get_any(reader_bridge, "target", default={}),
            "savedVariablesClassification": get_any(reader_bridge, "savedVariablesClassification"),
        },
        "targetCurrentReader": target_reader,
        "safety": get_any(summary, "safety", default={}),
        "next": get_any(summary, "next", default={}),
    }


def load_decision_artifact(repo_root: Path) -> tuple[dict[str, Any] | None, Path | None, str | None]:
    candidates = [
        repo_root / ".riftreader-local" / "decision-packet" / "latest" / "decision-packet-compact.json",
        repo_root / ".riftreader-local" / "latest-decision-packet.json",
    ]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return None, None, "decision-packet-artifact-missing"
    path = max(existing, key=lambda item: item.stat().st_mtime)
    try:
        return json.loads(path.read_text(encoding="utf-8")), path, None
    except Exception as exc:  # noqa: BLE001
        return None, path, f"{type(exc).__name__}: {exc}"


def compact_decision(decision: dict[str, Any] | None, source: str, path: Path | None, error: str | None) -> dict[str, Any]:
    if not decision:
        return {
            "available": False,
            "source": source,
            "sourceFile": str(path) if path else None,
            "status": "unavailable",
            "error": error,
            "blockers": [error] if error else ["decision-packet-unavailable"],
        }

    return {
        "available": True,
        "source": source,
        "sourceFile": str(path) if path else None,
        "generatedAtUtc": get_any(decision, "generatedAtUtc"),
        "status": get_any(decision, "status"),
        "lane": get_any(decision, "lane"),
        "risk": get_any(decision, "risk"),
        "safeNextAction": get_any(decision, "safeNextAction", default=get_nested(decision, "llmReminder", "continueWith")),
        "milestoneStatus": get_any(decision, "milestoneStatus", default={}),
        "llmReminder": get_any(decision, "llmReminder", default={}),
        "blockers": get_any(decision, "blockers", default=[]),
        "warnings": get_any(decision, "warnings", default=[]),
    }


def safety_gates() -> dict[str, Any]:
    return {
        "movement": {"label": "Movement", "status": "blocked until approved", "allowed": False},
        "liveInput": {"label": "Live input", "status": "blocked until approved", "allowed": False},
        "proofOnly": {"label": "ProofOnly", "status": "blocked until approved", "allowed": False},
        "debugger": {"label": "CE/x64dbg", "status": "blocked until approved", "allowed": False},
        "providerWrites": {"label": "Provider writes", "status": "blocked until approved", "allowed": False},
        "promotion": {"label": "Promotion", "status": "blocked until approved", "allowed": False},
        "gitPush": {"label": "Git push", "status": "blocked until approved", "allowed": False},
    }


def build_truth_banner(
    *,
    decision: dict[str, Any],
    phase1: dict[str, Any],
    errors: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    blockers = []
    warnings = []
    blockers.extend(decision.get("blockers") or [])
    blockers.extend(phase1.get("blockers") or [])
    warnings.extend(decision.get("warnings") or [])
    warnings.extend(phase1.get("warnings") or [])
    source_errors = [f"{key}: {value}" for key, value in errors.items() if value]
    warnings.extend(source_errors)

    phase_status = str(phase1.get("status") or "").lower()
    decision_status = str(decision.get("status") or "").lower()
    target_reader = phase1.get("targetCurrentReader") or {}
    reader_json = target_reader.get("readerJson") or {}
    family_id = reader_json.get("familyId") or "unknown-family"

    if blockers:
        status = "blocked-safe"
        label = "Blocked-safe local truth"
        reason = "One or more local evidence sources reports a blocker; do not cross gated live/proof boundaries."
    elif source_errors:
        status = "partial"
        label = "Partial live truth"
        reason = "Decision/Phase 1 artifacts may be available, but one or more live read sources reported a current issue."
    elif "passed" in phase_status and "passed" in decision_status:
        status = "passed"
        label = "Truth current / target readout ready"
        reason = f"Decision packet is passed and latest Phase 1 target reader is available for {family_id}."
    elif phase1.get("available") or decision.get("available"):
        status = "partial"
        label = "Partial local truth"
        reason = "Some local truth sources are available, but the live payload is not fully green."
    else:
        status = "unavailable"
        label = "Local truth unavailable"
        reason = "No current decision packet or Phase 1 target artifact was available."

    return {
        "status": status,
        "label": label,
        "reason": reason,
        "generatedAt": generated_at,
        "blockers": blockers[:8],
        "warnings": warnings[:8],
    }


def build_self_test_payload(repo_root: Path, generated_at: str) -> dict[str, Any]:
    decision = compact_decision(
        {
            "status": "passed",
            "lane": "dashboard-self-test",
            "risk": "low",
            "safeNextAction": {
                "key": "dashboard-live-data-self-test",
                "command": ["python", "scripts/dashboard_live_data.py", "--self-test"],
                "why": "Validate the schema v2 browser payload without live reads.",
            },
            "blockers": [],
            "warnings": [],
        },
        "self-test",
        None,
        None,
    )
    phase1 = {
        "available": True,
        "generatedAtUtc": generated_at,
        "status": "passed",
        "verdict": "self-test-phase1-target-card",
        "artifacts": {"summaryJson": "self-test"},
        "blockers": [],
        "warnings": [],
        "readerBridge": {"targetPresent": True, "target": {"name": "SelfTestTarget", "level": 1}},
        "targetCurrentReader": {
            "status": "passed",
            "readerJson": {
                "familyId": "fam-SELFTEST",
                "memoryAddressHex": "0x0",
                "selectionSource": "self-test",
                "match": {"LevelMatches": True, "HealthMatches": True, "CoordMatchesWithinTolerance": True},
            },
        },
    }
    errors: dict[str, Any] = {"repo": None, "snapshot": None, "player": None, "target": None, "decision": None, "phase1": None}
    return {
        "meta": {
            "schemaVersion": 2,
            "toolVersion": TOOL_VERSION,
            "generator": "dashboard_live_data.py",
            "generatedAt": generated_at,
            "staleAfterSeconds": DEFAULT_STALE_AFTER_SECONDS,
            "status": "active",
            "sources": {
                "repo": source_state("active", generated_at, fallback="self-test"),
                "snapshot": source_state("active", generated_at, fallback="self-test"),
                "player": source_state("active", generated_at, fallback="self-test"),
                "target": source_state("active", generated_at, fallback="self-test"),
                "decision": source_state("active", generated_at, fallback="self-test"),
                "phase1": source_state("active", generated_at, fallback="self-test"),
            },
        },
        "repo": parse_git_status("## self-test\n", repo_root, generated_at),
        "snapshot": {"available": True, "updatedAt": generated_at, "status": "ready", "sourceMode": "self-test"},
        "player": {"available": True, "updatedAt": generated_at, "name": "SelfTestPlayer", "sourceMode": "self-test"},
        "target": {
            "available": True,
            "hasTarget": True,
            "updatedAt": generated_at,
            "name": "SelfTestTarget",
            "sourceMode": "self-test",
            "anchor": {"familyId": "fam-SELFTEST", "address": "0x0"},
            "memoryMatch": {"LevelMatches": True, "HealthMatches": True, "CoordMatchesWithinTolerance": True},
        },
        "decision": decision,
        "nextSafeAction": decision["safeNextAction"],
        "phase1Target": phase1,
        "truthBanner": build_truth_banner(decision=decision, phase1=phase1, errors=errors, generated_at=generated_at),
        "safetyGates": safety_gates(),
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "providerWrites": False,
            "gitMutation": False,
            "targetMemoryBytesWritten": False,
        },
        "errors": errors,
        "commands": {},
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_path.resolve()
    generated_at = utc_now()
    if args.self_test:
        return build_self_test_payload(repo_root, generated_at)

    reader_project = repo_root / "reader" / "RiftReader.Reader" / "RiftReader.Reader.csproj"
    commands: dict[str, CommandResult] = {}
    errors: dict[str, Any] = {"repo": None, "snapshot": None, "player": None, "target": None, "decision": None, "phase1": None}

    git_result = run_command(
        "git-status",
        ["git", "--no-pager", "status", "--short", "--branch", "--untracked-files=all"],
        repo_root,
        20,
    )
    commands["repo"] = git_result
    repo_payload = parse_git_status(git_result.stdoutPreview, repo_root, generated_at) if git_result.ok else parse_git_status("", repo_root, generated_at)
    if not git_result.ok:
        errors["repo"] = git_result.error or git_result.stderrPreview or "git-status-failed"

    snapshot_result: CommandResult | None = None
    player_result: CommandResult | None = None
    target_result: CommandResult | None = None
    if not args.skip_live_reads:
        dotnet_prefix = ["dotnet", "run", "--project", str(reader_project), "--"]
        snapshot_result = run_command(
            "readerbridge-snapshot",
            [*dotnet_prefix, "--readerbridge-snapshot", "--json"],
            repo_root,
            args.timeout_seconds,
            parse_json=True,
        )
        commands["snapshot"] = snapshot_result

        player_result = run_command(
            "player-current-reader",
            [*dotnet_prefix, "--process-name", args.process_name, "--read-player-current", "--json"],
            repo_root,
            args.timeout_seconds,
            parse_json=True,
        )
        commands["player"] = player_result

        target_result = run_command(
            "target-current-reader",
            [*dotnet_prefix, "--process-name", args.process_name, "--read-target-current", "--scan-context", "512", "--max-hits", "64", "--json"],
            repo_root,
            args.timeout_seconds,
            parse_json=True,
        )
        commands["target"] = target_result

    snapshot_json = snapshot_result.parsedJson if snapshot_result and snapshot_result.parsedJson is not None else {}
    current = get_any(snapshot_json, "Current", default={})
    source_file = get_any(snapshot_json, "SourceFile")
    player_unit = get_any(current, "Player", default={})
    target_unit = get_any(current, "Target", default={})
    snapshot_payload = map_snapshot(snapshot_json, generated_at)
    player_payload = map_unit_payload(player_unit, player_result.parsedJson if player_result else None, generated_at=generated_at, source_file=source_file, is_target=False)
    target_payload = map_unit_payload(target_unit, target_result.parsedJson if target_result else None, generated_at=generated_at, source_file=source_file, is_target=True)

    for key, result in (("snapshot", snapshot_result), ("player", player_result), ("target", target_result)):
        if result is not None and not result.ok:
            errors[key] = result.error or result.parseError or result.stderrPreview or f"{key}-failed"
        elif result is None:
            errors[key] = "skipped-live-reads"

    decision_error: str | None = None
    decision_path: Path | None = None
    decision_raw: dict[str, Any] | None = None
    decision_source = "artifact"
    if args.include_decision:
        if args.refresh_decision:
            decision_result = run_command(
                "decision-packet",
                [str(repo_root / "scripts" / "riftreader-decision-packet.cmd"), "--compact-json"],
                repo_root,
                max(args.timeout_seconds, 120),
                parse_json=True,
                expected_exit_codes=(0, 2),
            )
            commands["decision"] = decision_result
            if decision_result.parsedJson is not None:
                decision_raw = decision_result.parsedJson
                decision_source = "command"
            else:
                decision_error = decision_result.error or decision_result.parseError or decision_result.stderrPreview or "decision-command-failed"
        else:
            decision_raw, decision_path, decision_error = load_decision_artifact(repo_root)
    else:
        decision_error = "decision-disabled"
    decision_payload = compact_decision(decision_raw, decision_source, decision_path, decision_error)
    if decision_error:
        errors["decision"] = decision_error

    phase_raw, phase_path, phase_error = latest_phase1_summary(repo_root)
    phase_payload = compact_phase1(phase_raw, phase_path, phase_error)
    if phase_error:
        errors["phase1"] = phase_error

    any_errors = any(value for value in errors.values() if value and value != "skipped-live-reads")
    sources = {
        "repo": source_state_from_command(git_result, generated_at),
        "snapshot": source_state_from_command(snapshot_result, generated_at),
        "player": source_state_from_command(player_result, generated_at),
        "target": source_state_from_command(target_result, generated_at),
        "decision": source_state("active" if decision_payload.get("available") else "partial", generated_at, error=decision_error or ""),
        "phase1": source_state("active" if phase_payload.get("available") else "partial", generated_at, error=phase_error or ""),
    }

    return {
        "meta": {
            "schemaVersion": 2,
            "toolVersion": TOOL_VERSION,
            "generator": "dashboard_live_data.py",
            "generatedAt": generated_at,
            "staleAfterSeconds": args.stale_after_seconds,
            "status": "partial" if any_errors else "active",
            "sources": sources,
        },
        "repo": repo_payload,
        "snapshot": snapshot_payload,
        "player": player_payload,
        "target": target_payload,
        "decision": decision_payload,
        "nextSafeAction": decision_payload.get("safeNextAction"),
        "phase1Target": phase_payload,
        "truthBanner": build_truth_banner(decision=decision_payload, phase1=phase_payload, errors=errors, generated_at=generated_at),
        "safetyGates": safety_gates(),
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "providerWrites": False,
            "gitMutation": False,
            "targetMemoryBytesWritten": False,
        },
        "errors": errors,
        "commands": {key: value.envelope() for key, value in commands.items()},
    }


def write_payload_js(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "window.DASHBOARD_LIVE_DATA = " + json.dumps(payload, indent=2, ensure_ascii=False) + ";\n"
    output_path.write_text(content, encoding="utf-8")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build RiftReader dashboard live-data schema v2.")
    parser.add_argument("--repo-path", type=Path, default=Path(__file__).resolve().parents[1], help="RiftReader repo root.")
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Output JS path. Defaults to tools/dashboard/dashboard-live-data.js under --repo-path.",
    )
    parser.add_argument("--process-name", default="rift_x64", help="Target process name for read-only memory reads.")
    parser.add_argument("--timeout-seconds", type=positive_int, default=45, help="Per-child-command timeout.")
    parser.add_argument("--stale-after-seconds", type=positive_int, default=DEFAULT_STALE_AFTER_SECONDS, help="Browser freshness budget.")
    parser.add_argument("--watch", action="store_true", help="Continuously rebuild the live payload.")
    parser.add_argument("--poll-seconds", type=positive_int, default=2, help="Delay between watch-mode rebuilds.")
    parser.add_argument("--skip-live-reads", action="store_true", help="Skip ReaderBridge/player/target memory reads.")
    parser.add_argument("--include-decision", action=argparse.BooleanOptionalAction, default=True, help="Include decision-packet data.")
    parser.add_argument("--refresh-decision", action="store_true", help="Run the decision-packet helper instead of reading the latest artifact.")
    parser.add_argument("--self-test", action="store_true", help="Emit a deterministic schema v2 payload without child commands.")
    parser.add_argument("--no-write", action="store_true", help="Do not write the JS payload.")
    parser.add_argument("--json", action="store_true", help="Print the raw payload JSON to stdout.")
    return parser


def run_once(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    output_path = args.output_path or (args.repo_path.resolve() / "tools" / "dashboard" / "dashboard-live-data.js")
    try:
        payload = build_payload(args)
        if not args.no_write:
            write_payload_js(payload, output_path)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        status = str(payload.get("meta", {}).get("status", "partial"))
        if status == "active":
            return 0, payload
        return 2, payload
    except Exception as exc:  # noqa: BLE001 - top-level blocker summary.
        generated_at = utc_now()
        payload = {
            "meta": {
                "schemaVersion": 2,
                "toolVersion": TOOL_VERSION,
                "generator": "dashboard_live_data.py",
                "generatedAt": generated_at,
                "staleAfterSeconds": args.stale_after_seconds,
                "status": "failed",
                "sources": {},
            },
            "truthBanner": {
                "status": "failed",
                "label": "Dashboard live payload failed",
                "reason": f"{type(exc).__name__}: {exc}",
                "blockers": ["dashboard-live-data-exception"],
                "warnings": [],
            },
            "safety": {
                "movementSent": False,
                "inputSent": False,
                "reloaduiSent": False,
                "screenshotKeySent": False,
                "noCheatEngine": True,
                "x64dbgAttach": False,
                "providerWrites": False,
                "gitMutation": False,
                "targetMemoryBytesWritten": False,
            },
            "errors": {"generator": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()},
        }
        if not args.no_write:
            write_payload_js(payload, output_path)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"[dashboard-live-data] failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1, payload


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    args.repo_path = args.repo_path.resolve()

    if not args.watch:
        exit_code, _payload = run_once(args)
        return exit_code

    last_exit = 0
    while True:
        exit_code, payload = run_once(args)
        last_exit = exit_code
        status = payload.get("meta", {}).get("status", "unknown")
        print(f"[dashboard-live-data] {utc_now()} status={status}; next poll in {args.poll_seconds}s", flush=True)
        time.sleep(args.poll_seconds)
    return last_exit


if __name__ == "__main__":
    raise SystemExit(main())
