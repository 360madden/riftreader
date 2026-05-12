#!/usr/bin/env python3
# Version: riftreader-postupdate-proof-reacquire-stage1-python-v0.1.0
# Total-Character-Count: 22571
# Purpose: Python-first RiftReader post-update proof-anchor reacquisition stage-1 control plane. It reuses existing repo helpers, captures structured artifacts, and only sends bounded movement stimulus when explicitly allowed.

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_json_loads(text: str) -> Any:
    value = (text or "").strip()
    if not value:
        raise ValueError("empty JSON text")
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        starts = [idx for idx in (value.find("{"), value.find("[")) if idx >= 0]
        if not starts:
            raise
        parsed, _ = json.JSONDecoder().raw_decode(value[min(starts):])
        return parsed


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def resolve_python() -> str:
    return sys.executable or "python"


def resolve_powershell() -> str:
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError("Neither pwsh nor powershell was found on PATH.")


def powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def powershell_encoded_args(script_text: str) -> list[str]:
    encoded = base64.b64encode(script_text.encode("utf-16-le")).decode("ascii")
    return ["-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded]


def run_command(
    *,
    label: str,
    args: list[str],
    cwd: Path,
    output_dir: Path,
    timeout_seconds: int,
    allow_failure: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    started_at = utc_iso()
    stdout_path = output_dir / f"{label}.stdout.txt"
    stderr_path = output_dir / f"{label}.stderr.txt"
    command_path = output_dir / f"{label}.command.json"

    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code: int | None = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        timed_out = True

    completed_at = utc_iso()
    duration = round(time.monotonic() - started, 3)
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")

    envelope: dict[str, Any] = {
        "label": label,
        "args": args,
        "cwd": str(cwd),
        "startedAtUtc": started_at,
        "completedAtUtc": completed_at,
        "durationSeconds": duration,
        "exitCode": exit_code,
        "timedOut": timed_out,
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
        "stdoutPreview": stdout[:2000],
        "stderrPreview": stderr[:2000],
    }

    parsed_json = None
    parse_error = None
    if stdout.strip():
        try:
            parsed_json = safe_json_loads(stdout)
        except Exception as exc:  # noqa: BLE001
            parse_error = f"{type(exc).__name__}: {exc}"
    envelope["json"] = parsed_json
    envelope["jsonParseError"] = parse_error
    write_json(command_path, envelope)
    envelope["commandPath"] = str(command_path)

    if (timed_out or exit_code not in (0,)) and not allow_failure:
        raise RuntimeError(f"{label} failed exit={exit_code} timedOut={timed_out}; stderr={stderr[:500]}")
    return envelope


def git_text(repo_root: Path, args: list[str], timeout_seconds: int = 30) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "args": ["git", *args],
        "exitCode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "lines": (proc.stdout or "").splitlines(),
    }


def resolve_target(
    *,
    repo_root: Path,
    run_root: Path,
    process_name: str,
    title_contains: str,
    pid: int | None,
    hwnd: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    ps = resolve_powershell()
    if pid is not None:
        pid_clause = f"$PidValue = {pid}\n"
    else:
        pid_clause = "$PidValue = $null\n"
    hwnd_literal = "$null" if not hwnd else powershell_literal(hwnd)
    script = f"""
$ErrorActionPreference = 'Stop'
$ProcessName = {powershell_literal(process_name)}
$TitleContains = {powershell_literal(title_contains)}
{pid_clause}$HwndValue = {hwnd_literal}
function Format-Hwnd($Value) {{
    if ($null -eq $Value -or [int64]$Value -eq 0) {{ return $null }}
    return ('0x{{0:X}}' -f [int64]$Value)
}}
try {{
    if ($null -ne $PidValue) {{
        $proc = Get-Process -Id $PidValue -ErrorAction Stop
        $matches = @($proc)
    }} else {{
        $matches = @(Get-Process -Name $ProcessName -ErrorAction SilentlyContinue |
            Where-Object {{ $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like "*$TitleContains*" }} |
            Sort-Object StartTime -Descending)
    }}
    $items = @($matches | ForEach-Object {{
        [ordered]@{{
            processId = [int]$_.Id
            processName = [string]$_.ProcessName
            title = [string]$_.MainWindowTitle
            hwnd = (Format-Hwnd $_.MainWindowHandle)
            startTime = try {{ $_.StartTime.ToUniversalTime().ToString('o') }} catch {{ $null }}
        }}
    }})
    $status = 'resolved'
    $blockers = @()
    if ($items.Count -eq 0) {{
        $status = 'blocked'
        $blockers += 'rift_target_not_found'
    }} elseif ($items.Count -gt 1 -and $null -eq $PidValue) {{
        $status = 'blocked'
        $blockers += 'multiple_rift_targets_found'
    }} elseif ($items.Count -eq 1) {{
        if ($items[0].processName -ne $ProcessName) {{
            $status = 'blocked'
            $blockers += 'process_name_mismatch'
        }}
        if ($HwndValue -and $items[0].hwnd -ne $HwndValue) {{
            $status = 'blocked'
            $blockers += 'hwnd_mismatch'
        }}
    }}
    [ordered]@{{
        status = $status
        ok = ($status -eq 'resolved')
        processName = $ProcessName
        titleContains = $TitleContains
        requestedPid = $PidValue
        requestedHwnd = $HwndValue
        blockers = $blockers
        target = if ($items.Count -eq 1) {{ $items[0] }} else {{ $null }}
        candidates = $items
    }} | ConvertTo-Json -Depth 12
}} catch {{
    [ordered]@{{
        status = 'failed'
        ok = $false
        blockers = @('target_resolution_exception')
        error = $_.Exception.Message
    }} | ConvertTo-Json -Depth 12
    exit 1
}}
"""
    envelope = run_command(
        label="resolve-target",
        args=[ps, *powershell_encoded_args(script)],
        cwd=repo_root,
        output_dir=run_root / "child-outputs",
        timeout_seconds=timeout_seconds,
        allow_failure=True,
    )
    data = envelope.get("json")
    if not isinstance(data, dict):
        return {
            "status": "failed",
            "ok": False,
            "blockers": ["target_resolution_non_json"],
            "command": envelope,
        }
    data["command"] = {k: v for k, v in envelope.items() if k not in {"json"}}
    return data


def run_visual_gate(
    *,
    repo_root: Path,
    run_root: Path,
    target: dict[str, Any],
    process_name: str,
    title_contains: str,
    full: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    output_dir = run_root / "visual-gate"
    args = [
        resolve_python(),
        str(repo_root / "scripts" / "check_live_visual_gate.py"),
        "--pid",
        str(target["processId"]),
        "--hwnd",
        str(target["hwnd"]),
        "--process-name",
        process_name,
        "--title-contains",
        title_contains,
        "--output-dir",
        str(output_dir),
        "--timeout-seconds",
        str(timeout_seconds),
        "--json",
    ]
    if full:
        args.append("--full")
    return run_command(
        label="visual-gate",
        args=args,
        cwd=repo_root,
        output_dir=run_root / "child-outputs",
        timeout_seconds=max(timeout_seconds + 30, 90),
        allow_failure=True,
    )


def run_family_scan(
    *,
    repo_root: Path,
    run_root: Path,
    target: dict[str, Any],
    process_name: str,
    max_seconds: int,
    max_hits: int,
    tolerance: float,
) -> dict[str, Any]:
    args = [
        resolve_python(),
        str(repo_root / "scripts" / "scan_current_pid_coordinate_family.py"),
        "--pid",
        str(target["processId"]),
        "--hwnd",
        str(target["hwnd"]),
        "--process-name",
        process_name,
        "--repo-root",
        str(repo_root),
        "--max-seconds",
        str(max_seconds),
        "--max-hits",
        str(max_hits),
        "--tolerance",
        str(tolerance),
        "--json",
    ]
    return run_command(
        label="family-scan",
        args=args,
        cwd=repo_root,
        output_dir=run_root / "child-outputs",
        timeout_seconds=max(max_seconds + 120, 240),
        allow_failure=True,
    )


def candidate_jsonl_from_scan(scan_summary: dict[str, Any] | None) -> str | None:
    if not isinstance(scan_summary, dict):
        return None
    artifacts = scan_summary.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    value = artifacts.get("candidateJsonl")
    if isinstance(value, str) and value.strip():
        return value
    return None


def visual_gate_ready(visual_summary: dict[str, Any] | None) -> bool:
    return isinstance(visual_summary, dict) and visual_summary.get("readyForLiveInput") is True


def should_run_batch(*, allow_movement_stimulus: bool, visual_summary: dict[str, Any] | None, candidate_jsonl: str | None) -> bool:
    return bool(allow_movement_stimulus and visual_gate_ready(visual_summary) and candidate_jsonl)


def run_anchor_batch(
    *,
    repo_root: Path,
    run_root: Path,
    candidate_jsonl: str,
    pose_count: int,
    minimum_promotion_pose_support: int,
    minimum_movement_pulses_for_promotion: int,
    key: str,
    hold_ms: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    ps = resolve_powershell()
    output_root = run_root / "coordinate-anchor-batch"
    args = [
        ps,
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(repo_root / "scripts" / "reacquire-current-pid-coordinate-anchor-batch.ps1"),
        "-CandidateFile",
        candidate_jsonl,
        "-OutputRoot",
        str(output_root),
        "-PoseCount",
        str(pose_count),
        "-MinimumPromotionPoseSupport",
        str(minimum_promotion_pose_support),
        "-MinimumMovementPulsesForPromotion",
        str(minimum_movement_pulses_for_promotion),
        "-Key",
        key,
        "-HoldMilliseconds",
        str(hold_ms),
        "-Json",
    ]
    return run_command(
        label="coordinate-anchor-batch",
        args=args,
        cwd=repo_root,
        output_dir=run_root / "child-outputs",
        timeout_seconds=timeout_seconds,
        allow_failure=True,
    )


def markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# RiftReader Python stage-1 proof reacquisition summary",
            "",
            f"- Status: `{summary.get('status')}`",
            f"- OK: `{summary.get('ok')}`",
            f"- Repo root: `{summary.get('repoRoot')}`",
            f"- Run root: `{summary.get('runRoot')}`",
            f"- Target: `{summary.get('target')}`",
            f"- Visual gate status: `{summary.get('visualGateStatus')}`",
            f"- Family scan status: `{summary.get('familyScanStatus')}`",
            f"- Candidate JSONL: `{summary.get('candidateJsonl')}`",
            f"- Movement stimulus allowed: `{summary.get('allowMovementStimulus')}`",
            f"- Movement sent: `{summary.get('movementSent')}`",
            f"- Batch status: `{summary.get('batchStatus')}`",
            "",
            "## Next action",
            "",
            str(summary.get("nextAction") or ""),
            "",
            "## Safety",
            "",
            "- No Cheat Engine is used by this helper.",
            "- No movement is sent unless `--allow-movement-stimulus` is supplied and the visual gate passes.",
            "- No truth files are updated by this stage-1 helper.",
            "- No git commands are run by this helper.",
            "",
            "# END_OF_DOCUMENT_MARKER",
            "",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Python-first RiftReader post-update proof reacquisition stage-1 runner.")
    parser.add_argument("--repo-root", default=r"C:\RIFT MODDING\RiftReader")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--output-root")
    parser.add_argument("--visual-full", action="store_true")
    parser.add_argument("--allow-movement-stimulus", action="store_true")
    parser.add_argument("--scan-max-seconds", type=int, default=180)
    parser.add_argument("--scan-max-hits", type=int, default=200)
    parser.add_argument("--scan-tolerance", type=float, default=0.25)
    parser.add_argument("--pose-count", type=int, default=4)
    parser.add_argument("--minimum-promotion-pose-support", type=int, default=3)
    parser.add_argument("--minimum-movement-pulses-for-promotion", type=int, default=2)
    parser.add_argument("--movement-key", default="w")
    parser.add_argument("--movement-hold-ms", type=int, default=750)
    parser.add_argument("--command-timeout-seconds", type=int, default=180)
    parser.add_argument("--batch-timeout-seconds", type=int, default=900)
    parser.add_argument("--json", action="store_true")
    return parser


def run_stage1(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    if not repo_root.exists():
        raise FileNotFoundError(f"repo root not found: {repo_root}")
    if not (repo_root / ".git").exists():
        raise RuntimeError(f"repo root is not a git repository: {repo_root}")

    run_root = Path(args.output_root).resolve() if args.output_root else repo_root / "scripts" / "captures" / f"postupdate-proof-reacquire-stage1-python-{utc_stamp()}"
    run_root.mkdir(parents=True, exist_ok=False)

    git_state = {
        "branch": git_text(repo_root, ["branch", "--show-current"]).get("stdout", "").strip(),
        "head": git_text(repo_root, ["rev-parse", "HEAD"]).get("stdout", "").strip(),
        "statusShort": git_text(repo_root, ["status", "--short"]).get("lines", []),
    }

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "riftreader-postupdate-proof-reacquire-stage1-python",
        "status": "started",
        "ok": False,
        "generatedAtUtc": utc_iso(),
        "repoRoot": str(repo_root),
        "runRoot": str(run_root),
        "git": git_state,
        "target": None,
        "visualGateStatus": "not-run",
        "familyScanStatus": "not-run",
        "candidateJsonl": None,
        "allowMovementStimulus": bool(args.allow_movement_stimulus),
        "movementSent": False,
        "batchStatus": "not-run",
        "artifacts": {},
        "issues": [],
        "nextAction": "",
        "safety": {
            "noCheatEngine": True,
            "truthFilesUpdated": False,
            "gitCommandsRun": False,
            "movementRequiresExplicitAllowFlag": True,
        },
    }

    try:
        target_result = resolve_target(
            repo_root=repo_root,
            run_root=run_root,
            process_name=args.process_name,
            title_contains=args.title_contains,
            pid=args.pid,
            hwnd=args.hwnd,
            timeout_seconds=args.command_timeout_seconds,
        )
        summary["targetResolution"] = target_result
        if not target_result.get("ok"):
            summary["status"] = "blocked-target"
            summary["issues"].extend(target_result.get("blockers") or ["target_resolution_failed"])
            summary["nextAction"] = "RIFT target is unavailable or ambiguous. Wait for maintenance to end, log in-world, then rerun."
            return summary

        target = target_result["target"]
        summary["target"] = target

        visual = run_visual_gate(
            repo_root=repo_root,
            run_root=run_root,
            target=target,
            process_name=args.process_name,
            title_contains=args.title_contains,
            full=args.visual_full,
            timeout_seconds=args.command_timeout_seconds,
        )
        visual_json = visual.get("json") if isinstance(visual.get("json"), dict) else None
        summary["visualGate"] = visual
        summary["visualGateStatus"] = str((visual_json or {}).get("status") or "failed")
        summary["visualGateReadyForLiveInput"] = visual_gate_ready(visual_json)
        if not visual_gate_ready(visual_json):
            summary["issues"].extend((visual_json or {}).get("blockers") or ["visual_gate_not_ready"])

        scan = run_family_scan(
            repo_root=repo_root,
            run_root=run_root,
            target=target,
            process_name=args.process_name,
            max_seconds=args.scan_max_seconds,
            max_hits=args.scan_max_hits,
            tolerance=args.scan_tolerance,
        )
        scan_json = scan.get("json") if isinstance(scan.get("json"), dict) else None
        summary["familyScan"] = scan
        summary["familyScanStatus"] = str((scan_json or {}).get("status") or "failed")
        candidate_jsonl = candidate_jsonl_from_scan(scan_json)
        summary["candidateJsonl"] = candidate_jsonl

        if not candidate_jsonl:
            summary["status"] = "blocked-no-candidate-file"
            summary["issues"].extend((scan_json or {}).get("blockers") or ["candidate_jsonl_missing"])
            summary["nextAction"] = "No candidate JSONL was produced. Inspect the family-scan summary and restore coordinate truth before movement."
            return summary

        if should_run_batch(allow_movement_stimulus=args.allow_movement_stimulus, visual_summary=visual_json, candidate_jsonl=candidate_jsonl):
            batch = run_anchor_batch(
                repo_root=repo_root,
                run_root=run_root,
                candidate_jsonl=candidate_jsonl,
                pose_count=args.pose_count,
                minimum_promotion_pose_support=args.minimum_promotion_pose_support,
                minimum_movement_pulses_for_promotion=args.minimum_movement_pulses_for_promotion,
                key=args.movement_key,
                hold_ms=args.movement_hold_ms,
                timeout_seconds=args.batch_timeout_seconds,
            )
            batch_json = batch.get("json") if isinstance(batch.get("json"), dict) else None
            summary["batch"] = batch
            summary["batchStatus"] = str((batch_json or {}).get("status") or "failed")
            summary["movementSent"] = bool((batch_json or {}).get("safety", {}).get("movementSent") or (batch_json or {}).get("movementSentCount", 0))
            if batch_json and batch_json.get("ok"):
                summary["status"] = "promotion-candidate-found"
                summary["ok"] = True
                summary["nextAction"] = "Review batch summary, then run the repo promotion helper and same-target ProofOnly. Do not update current truth before ProofOnly passes."
            else:
                summary["status"] = summary["batchStatus"]
                summary["nextAction"] = "Batch did not produce a promotion-ready candidate. Inspect ranked candidates and rerun after maintenance if needed."
        else:
            summary["status"] = "candidate-file-ready"
            summary["ok"] = True
            summary["nextAction"] = "Candidate file is ready. Rerun with --allow-movement-stimulus after maintenance and visual gate readiness to collect displaced poses."

        return summary
    finally:
        summary["completedAtUtc"] = utc_iso()
        summary_json = run_root / "stage1-python-summary.json"
        summary_md = run_root / "stage1-python-summary.md"
        summary["artifacts"]["summaryJson"] = str(summary_json)
        summary["artifacts"]["summaryMarkdown"] = str(summary_md)
        write_json(summary_json, summary)
        write_text(summary_md, markdown_summary(summary))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_stage1(args)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("=== RIFTREADER PYTHON STAGE1 SUMMARY ===")
        print(f"Status          : {summary.get('status')}")
        print(f"OK              : {summary.get('ok')}")
        print(f"RunRoot         : {summary.get('runRoot')}")
        print(f"Target          : {summary.get('target')}")
        print(f"Candidate JSONL : {summary.get('candidateJsonl')}")
        print(f"Movement sent   : {summary.get('movementSent')}")
        print(f"Batch status    : {summary.get('batchStatus')}")
        print(f"Summary JSON    : {summary.get('artifacts', {}).get('summaryJson')}")
        print(f"Next            : {summary.get('nextAction')}")
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
