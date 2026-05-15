#!/usr/bin/env python3
"""Fast current-PID coordinate proof-anchor recovery planner/orchestrator.

Default mode is still a dry run: it writes a command plan and safety summary
without executing child commands.  Execution is available only behind explicit
flags and is deliberately phased:

* ``--execute`` may run the no-input/read-only fast lane.
* ``--movement-approved`` is required before a pose batch can send movement.
* ``--allow-current-truth-update`` is required before promotion can update
  current truth artifacts.

The helper never uses Cheat Engine or live x64dbg, never mutates Git, and keeps
all command output in timestamped artifacts.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_TITLE_CONTAINS = "RIFT"
REFERENCE_PLACEHOLDER = "<REFERENCE_JSON_FROM_FAST_REFERENCE>"
SCAN_PLAN_PLACEHOLDER = "<SCAN_PLAN_JSON_FROM_INVENTORY>"
CANDIDATE_FILE_PLACEHOLDER = "<CANDIDATE_JSONL_FROM_SCAN_PLAN_BATCH>"


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "scripts").is_dir():
            return candidate
    raise RuntimeError(f"Could not find RiftReader repo root from {start}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def normalize_hwnd(value: str | int | None) -> str | None:
    if value is None or value == "":
        return None
    try:
        return f"0x{int(str(value), 0):X}"
    except ValueError:
        return str(value).strip()


def resolve_powershell() -> str:
    return shutil.which("pwsh") or shutil.which("powershell") or "pwsh"


def script_path(repo_root: Path, relative: str) -> Path:
    return (repo_root / relative).resolve()


def python_script_command(repo_root: Path, relative_script: str, *args: str) -> list[str]:
    return [sys.executable, str(script_path(repo_root, relative_script)), *args]


def powershell_script_command(repo_root: Path, relative_script: str, *args: str) -> list[str]:
    return [
        resolve_powershell(),
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path(repo_root, relative_script)),
        *args,
    ]


def safe_label(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-") or "step"


def extract_json(text: str) -> Any:
    value = (text or "").strip()
    if not value:
        raise RuntimeError("empty command output")
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    starts = [idx for idx in (value.find("{"), value.find("[")) if idx >= 0]
    starts = [idx for idx in starts if idx >= 0]
    if not starts:
        raise RuntimeError(f"no JSON object/array found; preview={value[:500]}")
    parsed, _ = json.JSONDecoder().raw_decode(value[min(starts) :])
    return parsed


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def get_mapping_value(document: dict[str, Any], *names: str) -> Any:
    for expected in names:
        for key, value in document.items():
            if str(key).lower() == expected.lower():
                return value
    return None


def nested_get(document: dict[str, Any], *path: str) -> Any:
    current: Any = document
    for segment in path:
        if not isinstance(current, dict):
            return None
        current = get_mapping_value(current, segment)
    return current


def status_value(document: Any) -> str | None:
    if not isinstance(document, dict):
        return None
    value = first_present(document.get("status"), document.get("Status"))
    return str(value) if value is not None else None


def flag_value(command: list[str], flag: str) -> str | None:
    try:
        index = command.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(command):
        return None
    return command[index + 1]


def replace_or_append_flag(command: list[str], flag: str, value: str) -> list[str]:
    updated = list(command)
    try:
        index = updated.index(flag)
    except ValueError:
        updated.extend([flag, value])
        return updated
    if index + 1 >= len(updated):
        updated.append(value)
    else:
        updated[index + 1] = value
    return updated


def remove_flag(command: list[str], flag: str, value_count: int = 0) -> list[str]:
    updated: list[str] = []
    index = 0
    while index < len(command):
        if command[index] == flag:
            index += 1 + value_count
            continue
        updated.append(command[index])
        index += 1
    return updated


def command_step(
    *,
    order: int,
    label: str,
    title: str,
    why: str,
    command: list[str],
    cwd: Path,
    execution_phase: str,
    condition: str = "always",
    timeout_seconds: int | None = None,
    reads_target_memory_if_executed: bool = False,
    sends_input_if_executed: bool = False,
    writes_repo_truth_if_executed: bool = False,
    requires_movement_approval: bool = False,
    requires_current_truth_update_approval: bool = False,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "order": order,
        "label": label,
        "title": title,
        "why": why,
        "executionPhase": execution_phase,
        "condition": condition,
        "command": command,
        "cwd": str(cwd),
        "timeoutSeconds": timeout_seconds,
        "dryRunExecuted": False,
        "readsTargetMemoryIfExecuted": reads_target_memory_if_executed,
        "sendsInputIfExecuted": sends_input_if_executed,
        "writesRepoTruthIfExecuted": writes_repo_truth_if_executed,
        "requiresMovementApproval": requires_movement_approval,
        "requiresCurrentTruthUpdateApproval": requires_current_truth_update_approval,
        "notes": notes or [],
    }


def read_current_proof_snapshot(repo_root: Path, requested_pid: int | None, requested_hwnd: str | None) -> dict[str, Any]:
    path = repo_root / "docs" / "recovery" / "current-proof-anchor-readback.json"
    snapshot: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "status": None,
        "target": None,
        "latestValidation": None,
        "warnings": [],
    }
    if not path.is_file():
        snapshot["warnings"].append("current-proof-anchor-readback-missing")
        return snapshot

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # keep planning robust even when the doc is malformed.
        snapshot["warnings"].append(f"current-proof-anchor-readback-read-failed:{type(exc).__name__}:{exc}")
        return snapshot

    target = document.get("target") if isinstance(document.get("target"), dict) else {}
    validation = document.get("latestValidation") if isinstance(document.get("latestValidation"), dict) else {}
    target_pid = first_present(target.get("processId"), document.get("processId"), document.get("pid"))
    target_hwnd = normalize_hwnd(first_present(target.get("targetWindowHandle"), target.get("hwnd"), document.get("hwnd")))
    requested_hwnd_normalized = normalize_hwnd(requested_hwnd)

    snapshot.update(
        {
            "status": document.get("status"),
            "target": {
                "processName": target.get("processName"),
                "processId": target_pid,
                "targetWindowHandle": target_hwnd,
            },
            "latestValidation": {
                "status": validation.get("status"),
                "movementAllowed": validation.get("movementAllowed"),
                "generatedAtUtc": validation.get("generatedAtUtc"),
                "proofAnchorCandidateId": validation.get("proofAnchorCandidateId"),
                "proofAnchorCandidateAddressHex": validation.get("proofAnchorCandidateAddressHex"),
                "readbackSummaryFile": validation.get("readbackSummaryFile"),
            },
        }
    )

    if requested_pid is not None and target_pid is not None and int(requested_pid) != int(target_pid):
        snapshot["warnings"].append(f"current-proof-artifact-target-pid-drift:{target_pid}!={requested_pid}")
    if requested_hwnd_normalized and target_hwnd and requested_hwnd_normalized != target_hwnd:
        snapshot["warnings"].append(f"current-proof-artifact-target-hwnd-drift:{target_hwnd}!={requested_hwnd_normalized}")
    return snapshot


def build_recovery_plan(args: argparse.Namespace, repo_root: Path, run_dir: Path) -> dict[str, Any]:
    pid_text = str(args.pid) if args.pid is not None else "<PID_FROM_TARGET_DISCOVERY>"
    hwnd_text = normalize_hwnd(args.hwnd) or "<HWND_FROM_TARGET_DISCOVERY>"
    process_name = args.process_name
    title_contains = args.title_contains
    top_count = max(1, int(args.scan_plan_top_count))
    pose_count = max(2, int(args.poses))
    escalate_pose_count = max(pose_count, int(args.escalate_poses))
    movement_approved = bool(args.movement_approved)

    target_output = run_dir / "01-target-control"
    chromalink_output = run_dir / "02-reference-chromalink"
    rrapi_output = run_dir / "02-reference-rrapicoord-fallback"
    rrapi_reference_file = rrapi_output / "reference.json"
    inventory_output = run_dir / "03-memory-inventory"
    pose_batch_output = run_dir / "05-pose-batch"
    proofonly_output = run_dir / "07-proofonly"

    steps: list[dict[str, Any]] = []
    order = 1

    if args.pid is None or args.hwnd is None:
        steps.append(
            command_step(
                order=order,
                label="discover-target",
                title="Discover current RIFT PID/HWND",
                why="Recovery must start from the current process epoch, not an old absolute proof pointer.",
                command=powershell_script_command(
                    repo_root,
                    "scripts/get-rift-window-targets.ps1",
                    "-ProcessName",
                    process_name,
                    "-Json",
                ),
                cwd=repo_root,
                execution_phase="target-discovery",
                timeout_seconds=15,
                notes=["Select exactly one target before running exact-PID steps."],
            )
        )
        order += 1

    steps.append(
        command_step(
            order=order,
            label="target-control-visual-gate",
            title="Run exact target-control plus visual gate",
            why="Confirms the helper is pointed at the intended RIFT window before any memory or movement proof work.",
            command=python_script_command(
                repo_root,
                "scripts/check_live_visual_gate_target_control.py",
                "--pid",
                pid_text,
                "--hwnd",
                hwnd_text,
                "--process-name",
                process_name,
                "--title-contains",
                title_contains,
                "--output-dir",
                str(target_output),
                "--timeout-seconds",
                str(args.visual_gate_timeout_seconds),
                "--json",
            ),
            cwd=repo_root,
            execution_phase="target-gate",
            timeout_seconds=max(20, int(args.visual_gate_timeout_seconds) + 20),
        )
    )
    order += 1

    steps.append(
        command_step(
            order=order,
            label="reference-chromalink-fast-path",
            title="Try ChromaLink fresh world-state coordinate reference",
            why="Fastest API-now truth source when health/freshness gates pass.",
            command=python_script_command(
                repo_root,
                "scripts/chromalink_world_state_reference.py",
                "--target-pid",
                pid_text,
                "--target-hwnd",
                hwnd_text,
                "--process-name",
                process_name,
                "--timeout-seconds",
                str(args.chromalink_timeout_seconds),
                "--output-root",
                str(chromalink_output),
                "--json",
            ),
            cwd=repo_root,
            execution_phase="reference",
            condition="use only if status is passed and artifacts.referenceJson is non-null",
            timeout_seconds=max(10, int(args.chromalink_timeout_seconds) + 10),
            notes=[
                "If this blocks as stale/unhealthy, use the RRAPICOORD fallback step.",
                "Reachability alone is not freshness proof.",
            ],
        )
    )
    order += 1

    steps.append(
        command_step(
            order=order,
            label="reference-rrapicoord-fallback",
            title="Capture one RRAPICOORD/API reference fallback",
            why="Provides API-now truth when ChromaLink is missing, stale, or unhealthy.",
            command=powershell_script_command(
                repo_root,
                "scripts/capture-rift-api-reference-coordinate.ps1",
                "-ProcessName",
                process_name,
                "-ProcessId",
                pid_text,
                "-TargetWindowHandle",
                hwnd_text,
                "-OutputRoot",
                str(rrapi_output),
                "-OutputFile",
                str(rrapi_reference_file),
                "-ScanContextBytes",
                str(args.reference_scan_context_bytes),
                "-MaxHits",
                str(args.reference_max_hits),
                "-Json",
            ),
            cwd=repo_root,
            execution_phase="reference",
            condition="fallback when ChromaLink reference is blocked",
            timeout_seconds=args.reference_timeout_seconds,
            notes=["Use exactly one fresh fallback reference for the scan-plan batch; do not reacquire per range."],
        )
    )
    order += 1

    steps.append(
        command_step(
            order=order,
            label="memory-region-inventory",
            title="Build current-PID memory-region inventory and scan plan",
            why="Ranks current-process families before byte scanning; avoids broad old-address probing.",
            command=python_script_command(
                repo_root,
                "scripts/current_pid_memory_region_inventory.py",
                "--pid",
                pid_text,
                "--hwnd",
                hwnd_text,
                "--process-name",
                process_name,
                "--output-root",
                str(inventory_output),
                "--top-count",
                str(top_count),
                "--json",
            ),
            cwd=repo_root,
            execution_phase="inventory",
            timeout_seconds=45,
            notes=["This reads region metadata only, not target memory bytes."],
        )
    )
    order += 1

    steps.append(
        command_step(
            order=order,
            label="scan-plan-batch-stop-on-hit",
            title="Scan prioritized current-PID families with stop-on-hit",
            why="This is the fast lane that replaced slow broad scans in the latest successful recovery.",
            command=python_script_command(
                repo_root,
                "scripts/current_pid_coordinate_scan_plan_batch.py",
                "--pid",
                pid_text,
                "--hwnd",
                hwnd_text,
                "--scan-plan",
                SCAN_PLAN_PLACEHOLDER,
                "--top-count",
                str(top_count),
                "--stride",
                str(args.scan_stride),
                "--tolerance",
                str(args.scan_tolerance),
                "--max-seconds-per-range",
                str(args.max_seconds_per_scan_range),
                "--reference-timeout-seconds",
                str(args.scan_reference_timeout_seconds),
                "--reference-file",
                REFERENCE_PLACEHOLDER,
                "--stop-on-hit",
                "--json",
            ),
            cwd=repo_root,
            execution_phase="scan",
            condition="after inventory and fresh reference selection",
            timeout_seconds=max(60, int(args.scan_batch_timeout_seconds)),
            reads_target_memory_if_executed=True,
            notes=[
                "Do not run broad scan first.",
                "If no hit, escalate scan-plan scope before using debugger/static-chain work.",
            ],
        )
    )
    order += 1

    pose_args = [
        "-PoseCount",
        str(pose_count),
        "-MinimumPromotionPoseSupport",
        str(args.minimum_promotion_pose_support),
        "-MinimumMovementPulsesForPromotion",
        str(args.minimum_movement_pulses_for_promotion),
        "-Key",
        args.movement_key,
        "-HoldMilliseconds",
        str(args.hold_milliseconds),
        "-InputMode",
        args.input_mode,
        "-CandidateFile",
        CANDIDATE_FILE_PLACEHOLDER,
        "-OutputRoot",
        str(pose_batch_output),
        "-Json",
    ]
    if not movement_approved:
        pose_args.insert(-1, "-NoMovement")

    steps.append(
        command_step(
            order=order,
            label="three-pose-displacement-validation",
            title="Validate candidate across displaced poses",
            why="Ranks by same-candidate delta tracking rather than single-pose proximity.",
            command=powershell_script_command(
                repo_root,
                "scripts/reacquire-current-pid-coordinate-anchor-batch.ps1",
                *pose_args,
            ),
            cwd=repo_root,
            execution_phase="pose-validation",
            condition="only after scan-plan batch produces a candidate JSONL hit",
            timeout_seconds=args.pose_batch_timeout_seconds,
            reads_target_memory_if_executed=True,
            sends_input_if_executed=movement_approved,
            requires_movement_approval=True,
            notes=[
                "Default is 3 poses; escalate to "
                f"{escalate_pose_count} poses only if dense copies or ambiguous support remain.",
                "Without movement approval, execution blocks before this step.",
            ],
        )
    )
    order += 1

    steps.append(
        command_step(
            order=order,
            label="promote-current-proof-anchor",
            title="Promote only a promotion-ready batch candidate",
            why="Updates repo truth only after same-PID multi-pose support passes.",
            command=powershell_script_command(
                repo_root,
                "scripts/promote-current-pid-proof-anchor-from-batch.ps1",
            ),
            cwd=repo_root,
            execution_phase="promotion",
            condition="only if batch summary is promotion-candidate-found and --allow-current-truth-update is set",
            timeout_seconds=120,
            reads_target_memory_if_executed=True,
            writes_repo_truth_if_executed=True,
            requires_current_truth_update_approval=True,
            notes=["Promotion is a separate explicit phase and is never run by dry-run mode."],
        )
    )
    order += 1

    steps.append(
        command_step(
            order=order,
            label="proofonly-final-gate",
            title="Run same-target ProofOnly",
            why="Final no-movement gate before any coordinate-driven navigation or polling.",
            command=python_script_command(
                repo_root,
                "scripts/live_test.py",
                "--profile",
                "ProofOnly",
                "--pid",
                pid_text,
                "--hwnd",
                hwnd_text,
                "--process-name",
                process_name,
                "--output-root",
                str(proofonly_output),
                "--no-gui",
            ),
            cwd=repo_root,
            execution_phase="proofonly",
            condition="after promotion succeeds and --run-proofonly is set",
            timeout_seconds=120,
            reads_target_memory_if_executed=True,
            notes=["ProofOnly sends no movement; movement remains blocked until it passes."],
        )
    )

    return {
        "referencePolicy": [
            "Prefer ChromaLink only when health and freshness pass.",
            "Use RRAPICOORD fallback exactly once per recovery attempt when ChromaLink is blocked.",
            "Never use SavedVariables, stale proof pointers, or old absolute addresses as live truth.",
        ],
        "promotionPolicy": {
            "defaultPoseCount": pose_count,
            "escalatePoseCount": escalate_pose_count,
            "minimumPromotionPoseSupport": args.minimum_promotion_pose_support,
            "minimumMovementPulsesForPromotion": args.minimum_movement_pulses_for_promotion,
            "rankBy": "same-candidate displaced-pose delta tracking",
        },
        "executionPolicy": {
            "executeRequiresExactPidHwnd": True,
            "movementRequiresMovementApprovedFlag": True,
            "truthUpdateRequiresAllowCurrentTruthUpdateFlag": True,
            "proofOnlyRequiresRunProofOnlyFlag": True,
            "x64dbgMode": "offline-read-only",
            "cheatEngineAllowed": False,
        },
        "steps": steps,
    }


def chromalink_reference_from_summary(parsed: Any) -> tuple[Path | None, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(parsed, dict):
        return None, ["chromalink-output-not-json-object"], warnings
    blockers.extend(str(item) for item in parsed.get("blockers") or [])
    warnings.extend(str(item) for item in parsed.get("warnings") or [])
    reference_json = first_present(
        nested_get(parsed, "artifacts", "referenceJson"),
        parsed.get("referenceJson"),
    )
    if status_value(parsed) != "passed":
        blockers.append(f"chromalink-status-not-passed:{status_value(parsed)}")
    if not reference_json:
        blockers.append("chromalink-reference-json-missing")
        return None, blockers, warnings
    path = Path(str(reference_json)).resolve()
    if not path.is_file():
        blockers.append(f"chromalink-reference-json-not-found:{path}")
        return None, blockers, warnings
    return path, blockers, warnings


def inventory_scan_plan_from_summary(parsed: Any) -> tuple[Path | None, list[str]]:
    blockers: list[str] = []
    if not isinstance(parsed, dict):
        return None, ["inventory-output-not-json-object"]
    if status_value(parsed) != "passed":
        blockers.append(f"inventory-status-not-passed:{status_value(parsed)}")
    scan_plan = first_present(nested_get(parsed, "artifacts", "scanPlanJson"), parsed.get("scanPlanJson"))
    if not scan_plan:
        blockers.append("inventory-scan-plan-json-missing")
        return None, blockers
    path = Path(str(scan_plan)).resolve()
    if not path.is_file():
        blockers.append(f"inventory-scan-plan-json-not-found:{path}")
        return None, blockers
    return path, blockers


def candidate_file_from_scan_summary(parsed: Any) -> tuple[Path | None, dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    best_result: dict[str, Any] | None = None
    if not isinstance(parsed, dict):
        return None, None, ["scan-output-not-json-object"]
    total_hits = int(nested_get(parsed, "scan", "totalHits") or 0)
    if status_value(parsed) != "passed":
        blockers.append(f"scan-status-not-passed:{status_value(parsed)}")
    if total_hits <= 0:
        blockers.append("scan-total-hits-zero")

    for item in parsed.get("rangeResults") or []:
        if not isinstance(item, dict):
            continue
        if int(item.get("hitCount") or 0) <= 0:
            continue
        candidate_jsonl = item.get("candidateJsonl")
        if candidate_jsonl:
            path = Path(str(candidate_jsonl)).resolve()
            if path.is_file():
                best_result = item
                return path, best_result, blockers
            blockers.append(f"scan-candidate-jsonl-not-found:{path}")

    fallback = first_present(nested_get(parsed, "artifacts", "candidateJsonl"), parsed.get("candidateJsonl"))
    if fallback:
        path = Path(str(fallback)).resolve()
        if path.is_file():
            return path, None, blockers
        blockers.append(f"scan-candidate-jsonl-not-found:{path}")

    blockers.append("scan-candidate-jsonl-missing")
    return None, best_result, blockers


def run_command_envelope(
    *,
    step: dict[str, Any],
    command: list[str],
    cwd: Path,
    output_dir: Path,
    timeout_seconds: int | None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    label = f"{int(step.get('order') or 0):02d}-{safe_label(str(step.get('label')))}"
    stdout_path = output_dir / f"{label}.stdout.txt"
    stderr_path = output_dir / f"{label}.stderr.txt"
    started = time.monotonic()
    started_utc = utc_iso()
    envelope: dict[str, Any] = {
        "label": step.get("label"),
        "title": step.get("title"),
        "executionPhase": step.get("executionPhase"),
        "args": command,
        "cwd": str(cwd),
        "timeoutSeconds": timeout_seconds,
        "startedAtUtc": started_utc,
        "completedAtUtc": None,
        "durationSeconds": None,
        "exitCode": None,
        "timedOut": False,
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
        "stdoutPreview": "",
        "stderrPreview": "",
        "parsedJson": None,
        "jsonParseError": None,
    }
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        envelope["exitCode"] = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
        envelope["timedOut"] = True
    finally:
        completed = utc_iso()
        envelope["completedAtUtc"] = completed
        envelope["durationSeconds"] = round(time.monotonic() - started, 3)

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    envelope["stdoutPreview"] = stdout[:2000]
    envelope["stderrPreview"] = stderr[:2000]
    if stdout.strip():
        try:
            envelope["parsedJson"] = extract_json(stdout)
        except Exception as exc:  # preserve raw stdout/stderr paths.
            envelope["jsonParseError"] = f"{type(exc).__name__}: {exc}"
    return envelope


def stage_record(envelope: dict[str, Any], status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "label": envelope.get("label"),
        "phase": envelope.get("executionPhase"),
        "status": status,
        "exitCode": envelope.get("exitCode"),
        "timedOut": envelope.get("timedOut"),
        "durationSeconds": envelope.get("durationSeconds"),
        "stdoutPath": envelope.get("stdoutPath"),
        "stderrPath": envelope.get("stderrPath"),
        "childStatus": status_value(envelope.get("parsedJson")),
        "details": details or {},
    }


def build_restart_profile(summary: dict[str, Any]) -> dict[str, Any]:
    execution = summary.get("execution") or {}
    stages = execution.get("stages") or []
    return {
        "schemaVersion": 1,
        "kind": "riftreader-coordinate-recovery-profile",
        "generatedAtUtc": utc_iso(),
        "sourceRunDirectory": summary.get("artifacts", {}).get("runDirectory"),
        "target": summary.get("target"),
        "referenceProvider": execution.get("referenceProvider"),
        "referenceJson": execution.get("referenceJson"),
        "scanPlanJson": execution.get("scanPlanJson"),
        "candidateJsonl": execution.get("candidateJsonl"),
        "bestScanRange": execution.get("bestScanRange"),
        "promotionBatchSummaryJson": execution.get("promotionBatchSummaryJson"),
        "proofOnlySummaryJson": execution.get("proofOnlySummaryJson"),
        "stageTimings": [
            {
                "label": stage.get("label"),
                "phase": stage.get("phase"),
                "status": stage.get("status"),
                "durationSeconds": stage.get("durationSeconds"),
            }
            for stage in stages
        ],
        "safety": {
            "oldAbsoluteAddressesAreHintsOnly": True,
            "savedVariablesUsedAsLiveTruth": False,
            "x64dbgMode": summary.get("operator", {}).get("x64dbgMode"),
            "cheatEngineAllowed": False,
        },
    }


def execute_recovery_plan(summary: dict[str, Any], args: argparse.Namespace, repo_root: Path, run_dir: Path) -> int:
    if args.pid is None or not normalize_hwnd(args.hwnd):
        summary["status"] = "blocked"
        summary["blockers"].append("execute-requires-exact-pid-and-hwnd")
        return 2

    plan = summary.get("plan") or {}
    steps = {step["label"]: step for step in plan.get("steps", []) if isinstance(step, dict)}
    envelopes: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    envelopes_dir = run_dir / "command-envelopes"
    reference_json: Path | None = None
    reference_provider: str | None = None
    scan_plan_json: Path | None = None
    candidate_jsonl: Path | None = None
    best_scan_range: dict[str, Any] | None = None

    summary["execution"] = {
        "mode": "execute",
        "startedAtUtc": utc_iso(),
        "completedAtUtc": None,
        "referenceProvider": None,
        "referenceJson": None,
        "scanPlanJson": None,
        "candidateJsonl": None,
        "bestScanRange": None,
        "promotionBatchSummaryJson": None,
        "proofOnlySummaryJson": None,
        "stages": stages,
    }

    def run_label(label: str, command: list[str] | None = None, acceptable_exit_codes: tuple[int | None, ...] = (0,)) -> dict[str, Any]:
        step = steps[label]
        resolved_command = command or list(step["command"])
        envelope = run_command_envelope(
            step=step,
            command=resolved_command,
            cwd=Path(step["cwd"]),
            output_dir=envelopes_dir,
            timeout_seconds=step.get("timeoutSeconds"),
        )
        envelopes.append(envelope)
        if step.get("readsTargetMemoryIfExecuted"):
            summary["safety"]["targetMemoryBytesReadOrWritten"] = True
        if step.get("sendsInputIfExecuted"):
            summary["safety"]["inputSent"] = True
            summary["safety"]["movementSent"] = True
        if step.get("writesRepoTruthIfExecuted") and envelope.get("exitCode") == 0 and not envelope.get("timedOut"):
            summary["safety"]["currentTruthUpdated"] = True
        status = "passed" if (not envelope.get("timedOut") and envelope.get("exitCode") in acceptable_exit_codes) else "failed"
        stages.append(stage_record(envelope, status))
        return envelope

    try:
        target = run_label("target-control-visual-gate")
        if stages[-1]["status"] != "passed":
            summary["status"] = "blocked"
            summary["blockers"].append("target-control-visual-gate-failed")
            return 2

        chromalink = run_label("reference-chromalink-fast-path", acceptable_exit_codes=(0, 2))
        chromalink_reference, chromalink_blockers, chromalink_warnings = chromalink_reference_from_summary(
            chromalink.get("parsedJson")
        )
        summary["warnings"].extend(f"chromalink:{item}" for item in chromalink_warnings)
        if chromalink_reference and not chromalink_blockers:
            reference_json = chromalink_reference
            reference_provider = "chromalink-world-state"
            stages[-1]["status"] = "passed"
            stages[-1]["details"]["referenceJson"] = str(reference_json)
        else:
            stages[-1]["status"] = "blocked"
            stages[-1]["details"]["blockers"] = chromalink_blockers
            summary["warnings"].extend(f"chromalink-blocked:{item}" for item in chromalink_blockers)
            rrapi = run_label("reference-rrapicoord-fallback")
            if stages[-1]["status"] != "passed":
                summary["status"] = "blocked"
                summary["blockers"].append("rrapicoord-reference-capture-failed")
                return 2
            fallback_reference = flag_value(list(steps["reference-rrapicoord-fallback"]["command"]), "-OutputFile")
            if fallback_reference and Path(fallback_reference).is_file():
                reference_json = Path(fallback_reference).resolve()
            else:
                parsed = rrapi.get("parsedJson") if isinstance(rrapi.get("parsedJson"), dict) else {}
                parsed_reference = first_present(
                    parsed.get("OutputFile"),
                    parsed.get("outputFile"),
                    parsed.get("ReferenceFile"),
                    parsed.get("referenceFile"),
                )
                if parsed_reference and Path(str(parsed_reference)).is_file():
                    reference_json = Path(str(parsed_reference)).resolve()
            if reference_json is None:
                summary["status"] = "blocked"
                summary["blockers"].append("rrapicoord-reference-json-not-found")
                return 2
            reference_provider = "rrapicoord-fallback"
            stages[-1]["details"]["referenceJson"] = str(reference_json)

        summary["execution"]["referenceProvider"] = reference_provider
        summary["execution"]["referenceJson"] = str(reference_json)

        inventory = run_label("memory-region-inventory")
        if stages[-1]["status"] != "passed":
            summary["status"] = "blocked"
            summary["blockers"].append("memory-region-inventory-failed")
            return 2
        scan_plan_json, inventory_blockers = inventory_scan_plan_from_summary(inventory.get("parsedJson"))
        if inventory_blockers or scan_plan_json is None:
            summary["status"] = "blocked"
            summary["blockers"].extend(inventory_blockers)
            return 2
        summary["execution"]["scanPlanJson"] = str(scan_plan_json)
        stages[-1]["details"]["scanPlanJson"] = str(scan_plan_json)

        scan_step = steps["scan-plan-batch-stop-on-hit"]
        scan_command = replace_or_append_flag(list(scan_step["command"]), "--reference-file", str(reference_json))
        scan_command = replace_or_append_flag(scan_command, "--scan-plan", str(scan_plan_json))
        scan = run_label("scan-plan-batch-stop-on-hit", command=scan_command, acceptable_exit_codes=(0, 2))
        candidate_jsonl, best_scan_range, scan_blockers = candidate_file_from_scan_summary(scan.get("parsedJson"))
        if scan_blockers or candidate_jsonl is None:
            summary["status"] = "blocked"
            summary["blockers"].extend(scan_blockers)
            return 2
        summary["execution"]["candidateJsonl"] = str(candidate_jsonl)
        summary["execution"]["bestScanRange"] = best_scan_range
        stages[-1]["details"]["candidateJsonl"] = str(candidate_jsonl)

        restart_profile = build_restart_profile(summary)
        restart_profile_path = run_dir / "restart-profile.json"
        write_json(restart_profile_path, restart_profile)
        summary["artifacts"]["restartProfileJson"] = str(restart_profile_path)
        if args.write_restart_profile:
            repo_profile_path = Path(args.restart_profile_path)
            if not repo_profile_path.is_absolute():
                repo_profile_path = repo_root / repo_profile_path
            repo_profile_path = repo_profile_path.resolve()
            write_json(repo_profile_path, restart_profile)
            summary["artifacts"]["repoRestartProfileJson"] = str(repo_profile_path)

        if not args.movement_approved:
            summary["status"] = "blocked"
            summary["blockers"].append("movement-approval-required-for-displaced-pose-validation")
            return 2

        pose_step = steps["three-pose-displacement-validation"]
        pose_command = replace_or_append_flag(list(pose_step["command"]), "-CandidateFile", str(candidate_jsonl))
        pose_command = remove_flag(pose_command, "-NoMovement")
        pose = run_label("three-pose-displacement-validation", command=pose_command)
        if stages[-1]["status"] != "passed":
            summary["status"] = "blocked"
            summary["blockers"].append("pose-validation-failed")
            return 2
        pose_parsed = pose.get("parsedJson") if isinstance(pose.get("parsedJson"), dict) else {}
        pose_status = status_value(pose_parsed)
        pose_summary = first_present(
            nested_get(pose_parsed, "artifacts", "summaryJson"),
            pose_parsed.get("summaryJson"),
            pose_parsed.get("SummaryJson"),
        )
        if pose_summary:
            summary["execution"]["promotionBatchSummaryJson"] = str(pose_summary)
        if pose_status != "promotion-candidate-found":
            summary["status"] = "blocked"
            summary["blockers"].append(f"pose-validation-not-promotion-ready:{pose_status}")
            return 2

        if not args.allow_current_truth_update:
            summary["status"] = "blocked"
            summary["blockers"].append("current-truth-update-requires-allow-current-truth-update")
            return 2

        promotion = run_label("promote-current-proof-anchor")
        if stages[-1]["status"] != "passed":
            summary["status"] = "blocked"
            summary["blockers"].append("current-proof-anchor-promotion-failed")
            return 2
        stages[-1]["details"]["truthUpdated"] = True

        if args.run_proofonly:
            proofonly = run_label("proofonly-final-gate")
            if stages[-1]["status"] != "passed":
                summary["status"] = "blocked"
                summary["blockers"].append("proofonly-final-gate-failed")
                return 2
            parsed = proofonly.get("parsedJson") if isinstance(proofonly.get("parsedJson"), dict) else {}
            proof_run_dir = parsed.get("runDirectory") if isinstance(parsed, dict) else None
            proof_run_summary = None
            if proof_run_dir:
                candidate_run_summary = Path(str(proof_run_dir)) / "run-summary.json"
                if candidate_run_summary.is_file():
                    proof_run_summary = str(candidate_run_summary.resolve())
            proof_summary = first_present(
                proof_run_summary,
                nested_get(parsed, "artifacts", "summaryJson"),
                parsed.get("summaryJson"),
                parsed.get("runSummaryJson"),
                parsed.get("summaryFile"),
            )
            if proof_summary:
                summary["execution"]["proofOnlySummaryJson"] = str(proof_summary)
        else:
            summary["warnings"].append("proofonly-not-run; pass --run-proofonly after promotion to complete the gate")

        summary["status"] = "passed"
        return 0
    finally:
        summary["execution"]["completedAtUtc"] = utc_iso()
        write_json(run_dir / "command-envelopes.json", envelopes)
        summary["artifacts"]["commandEnvelopesJson"] = str(run_dir / "command-envelopes.json")
        if summary.get("execution", {}).get("candidateJsonl"):
            restart_profile = build_restart_profile(summary)
            restart_profile_path = run_dir / "restart-profile.json"
            write_json(restart_profile_path, restart_profile)
            summary["artifacts"]["restartProfileJson"] = str(restart_profile_path)
            if args.write_restart_profile:
                repo_profile_path = Path(args.restart_profile_path)
                if not repo_profile_path.is_absolute():
                    repo_profile_path = repo_root / repo_profile_path
                repo_profile_path = repo_profile_path.resolve()
                write_json(repo_profile_path, restart_profile)
                summary["artifacts"]["repoRestartProfileJson"] = str(repo_profile_path)


def render_markdown(summary: dict[str, Any]) -> str:
    steps = summary.get("plan", {}).get("steps", [])
    rows = []
    for step in steps:
        flags: list[str] = []
        if step.get("readsTargetMemoryIfExecuted"):
            flags.append("reads memory if executed")
        if step.get("sendsInputIfExecuted"):
            flags.append("sends input if executed")
        if step.get("writesRepoTruthIfExecuted"):
            flags.append("writes truth if executed")
        if step.get("requiresMovementApproval"):
            flags.append("requires movement approval")
        if step.get("requiresCurrentTruthUpdateApproval"):
            flags.append("requires truth-update approval")
        flag_text = ", ".join(flags) if flags else "no live mutation in dry-run"
        rows.append(
            "| {order} | `{label}` | `{phase}` | {title} | `{condition}` | {flags} |".format(
                order=step.get("order"),
                label=step.get("label"),
                phase=step.get("executionPhase"),
                title=step.get("title"),
                condition=step.get("condition"),
                flags=flag_text,
            )
        )

    stage_rows = []
    for stage in summary.get("execution", {}).get("stages", []) or []:
        stage_rows.append(
            "| `{label}` | `{phase}` | `{status}` | {seconds} | `{child}` |".format(
                label=stage.get("label"),
                phase=stage.get("phase"),
                status=stage.get("status"),
                seconds=stage.get("durationSeconds"),
                child=stage.get("childStatus"),
            )
        )

    blockers = [f"- `{item}`" for item in summary.get("blockers", [])] or ["- none"]
    warnings = [f"- `{item}`" for item in summary.get("warnings", [])] or ["- none"]
    recommendations = [
        f"| {index} | {item.get('action')} | {item.get('why')} |"
        for index, item in enumerate(summary.get("next", {}).get("recommendedActions", []), 1)
    ]

    lines = [
        "# Fast current-PID coordinate proof-anchor recovery",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Target: PID `{summary.get('target', {}).get('pid')}`, HWND `{summary.get('target', {}).get('hwnd')}`",
        f"- Mode: `{summary.get('execution', {}).get('mode', 'dry-run')}`",
        f"- Movement approved for execution: `{summary.get('operator', {}).get('movementApproved')}`",
        f"- Current-truth update approved: `{summary.get('operator', {}).get('allowCurrentTruthUpdate')}`",
        f"- x64dbg mode: `{summary.get('operator', {}).get('x64dbgMode')}`",
        "",
        "## Planned steps",
        "",
        "| # | Label | Phase | Step | Condition | Safety note |",
        "|---:|---|---|---|---|---|",
        *rows,
    ]
    if stage_rows:
        lines.extend(
            [
                "",
                "## Executed stages",
                "",
                "| Label | Phase | Status | Seconds | Child status |",
                "|---|---|---|---:|---|",
                *stage_rows,
            ]
        )
    lines.extend(
        [
            "",
            "## Blockers",
            "",
            *blockers,
            "",
            "## Warnings",
            "",
            *warnings,
            "",
            "## Top recommended next actions",
            "",
            "| # | Action | Why |",
            "|---:|---|---|",
            *recommendations,
            "",
            "## Safety",
            "",
            "- Dry-run mode executes no child recovery commands.",
            "- Execution mode requires exact PID/HWND.",
            "- Movement requires `--movement-approved`.",
            "- Current-truth updates require `--allow-current-truth-update`.",
            "- No Cheat Engine or live x64dbg attach is used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_recommended_actions() -> list[dict[str, str]]:
    return [
        {
            "action": "Run the helper dry-run with exact --pid and --hwnd after each restart.",
            "why": "Creates a timestamped, target-specific recovery plan before touching live state.",
        },
        {
            "action": "Use --execute first without --movement-approved.",
            "why": "Runs only the target/reference/inventory/scan lane and blocks before movement.",
        },
        {
            "action": "Use --movement-approved only when displaced-pose validation is intended.",
            "why": "Keeps input/movement explicit and auditable.",
        },
        {
            "action": "Use --allow-current-truth-update only after promotion-candidate-found.",
            "why": "Separates discovery from truth mutation.",
        },
        {
            "action": "Use --run-proofonly with promotion.",
            "why": "Completes the same-target no-movement proof gate immediately.",
        },
        {
            "action": "Inspect command-envelopes.json after any execute run.",
            "why": "It records command args, stdout/stderr files, exit codes, and timings.",
        },
        {
            "action": "Prefer ChromaLink only when freshness passes.",
            "why": "Avoids treating a reachable but stale provider as API-now truth.",
        },
        {
            "action": "Keep broad scans as escalation only.",
            "why": "The scan-plan stop-on-hit lane is the faster restart path.",
        },
        {
            "action": "Enable --write-restart-profile after a real scan run.",
            "why": "Persists region/candidate timing hints without promoting old addresses as truth.",
        },
        {
            "action": "Keep x64dbg offline/read-only in this workflow.",
            "why": "Matches the current crash-risk boundary and avoids costly restart recovery.",
        },
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or execute a gated fast current-PID coordinate proof-anchor recovery lane."
    )
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--hwnd", default=None)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--title-contains", default=DEFAULT_TITLE_CONTAINS)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--scan-plan-top-count", type=int, default=80)
    parser.add_argument("--scan-stride", type=int, choices=(1, 4), default=4)
    parser.add_argument("--scan-tolerance", type=float, default=2.0)
    parser.add_argument("--max-seconds-per-scan-range", type=int, default=45)
    parser.add_argument("--scan-batch-timeout-seconds", type=int, default=900)
    parser.add_argument("--scan-reference-timeout-seconds", type=int, default=45)
    parser.add_argument("--chromalink-timeout-seconds", type=int, default=3)
    parser.add_argument("--reference-timeout-seconds", type=int, default=180)
    parser.add_argument("--reference-scan-context-bytes", type=int, default=65536)
    parser.add_argument("--reference-max-hits", type=int, default=2048)
    parser.add_argument("--visual-gate-timeout-seconds", type=int, default=10)
    parser.add_argument("--poses", type=int, default=3)
    parser.add_argument("--escalate-poses", type=int, default=5)
    parser.add_argument("--minimum-promotion-pose-support", type=int, default=3)
    parser.add_argument("--minimum-movement-pulses-for-promotion", type=int, default=2)
    parser.add_argument("--movement-key", default="w")
    parser.add_argument("--hold-milliseconds", type=int, default=750)
    parser.add_argument("--input-mode", choices=("ScanCode", "VirtualKey"), default="ScanCode")
    parser.add_argument("--pose-batch-timeout-seconds", type=int, default=600)
    parser.add_argument("--movement-approved", action="store_true")
    parser.add_argument("--allow-current-truth-update", action="store_true")
    parser.add_argument("--run-proofonly", action="store_true")
    parser.add_argument("--write-restart-profile", action="store_true")
    parser.add_argument(
        "--restart-profile-path",
        default=str(Path("docs") / "recovery" / "coordinate-recovery-profile.json"),
    )
    parser.add_argument("--dry-run", action="store_true", help="Accepted for clarity; this is the default mode.")
    parser.add_argument("--execute", action="store_true", help="Run the gated recovery lane instead of only planning.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        args.pid = 1234
        args.hwnd = "0xABCDEF"
        args.movement_approved = False
        args.allow_current_truth_update = False
        args.run_proofonly = False
        args.write_restart_profile = False

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    output_root = Path(args.output_root).resolve() if args.output_root else repo_root / "scripts" / "captures"
    target_label = args.pid if args.pid is not None else "target"
    mode_label = "execute" if args.execute else "dryrun"
    run_dir = output_root / f"recover-currentpid-coord-anchor-fast-{mode_label}-{target_label}-{utc_stamp()}"
    summary_path = run_dir / "summary.json"
    markdown_path = run_dir / "summary.md"
    command_plan_path = run_dir / "command-plan.json"

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-fast-current-pid-coordinate-recovery",
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "blockers": [],
        "warnings": [] if args.execute else ["dry-run-only:no-child-commands-executed"],
        "errors": [],
        "repoRoot": str(repo_root),
        "target": {
            "pid": args.pid,
            "hwnd": normalize_hwnd(args.hwnd),
            "processName": args.process_name,
            "titleContains": args.title_contains,
        },
        "operator": {
            "execute": bool(args.execute),
            "movementApproved": bool(args.movement_approved),
            "allowCurrentTruthUpdate": bool(args.allow_current_truth_update),
            "runProofOnly": bool(args.run_proofonly),
            "writeRestartProfile": bool(args.write_restart_profile),
            "x64dbgMode": "offline-read-only",
            "cheatEngineAllowed": False,
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "x64dbgLiveAttachStarted": False,
            "debuggerAttached": False,
            "targetMemoryBytesReadOrWritten": False,
            "providerWrites": False,
            "githubConnectorWrites": False,
            "gitMutation": False,
            "currentTruthUpdated": False,
        },
        "currentProofArtifact": read_current_proof_snapshot(repo_root, args.pid, normalize_hwnd(args.hwnd)),
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_path),
            "summaryMarkdown": str(markdown_path),
            "commandPlanJson": str(command_plan_path),
        },
        "next": {"recommendedActions": build_recommended_actions()},
    }

    exit_code = 0
    try:
        plan = build_recovery_plan(args, repo_root, run_dir)
        summary["plan"] = plan
        proof_warnings = summary.get("currentProofArtifact", {}).get("warnings") or []
        summary["warnings"].extend(proof_warnings)
        if not args.movement_approved:
            summary["warnings"].append("movement-not-approved; execution blocks before displaced-pose validation")
        if args.self_test:
            labels = [step["label"] for step in plan["steps"]]
            required = {
                "target-control-visual-gate",
                "reference-chromalink-fast-path",
                "reference-rrapicoord-fallback",
                "memory-region-inventory",
                "scan-plan-batch-stop-on-hit",
                "three-pose-displacement-validation",
                "promote-current-proof-anchor",
                "proofonly-final-gate",
            }
            missing = sorted(required.difference(labels))
            summary["selfTest"] = {"status": "passed" if not missing else "failed", "missingStepLabels": missing}
            if missing:
                summary["status"] = "failed"
                summary["errors"].append({"type": "SelfTestFailed", "message": f"missing steps: {missing}"})
                exit_code = 1
        elif args.execute:
            exit_code = execute_recovery_plan(summary, args, repo_root, run_dir)
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        exit_code = 1

    write_json(command_plan_path, summary.get("plan", {}))
    write_json(summary_path, summary)
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": summary.get("status"),
                    "blockers": summary.get("blockers"),
                    "warnings": summary.get("warnings"),
                    "summaryJson": str(summary_path),
                    "summaryMarkdown": str(markdown_path),
                    "commandPlanJson": str(command_plan_path),
                    "commandEnvelopesJson": summary.get("artifacts", {}).get("commandEnvelopesJson"),
                    "restartProfileJson": summary.get("artifacts", {}).get("restartProfileJson"),
                },
                indent=2,
            )
        )
    if summary["status"] == "failed":
        return 1
    if summary["status"] == "blocked":
        return 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
