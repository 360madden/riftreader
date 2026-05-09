from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reports import write_json


PALETTE = {
    "bg": "#0B1120",
    "card": "#111827",
    "card_2": "#0F172A",
    "text": "#E5E7EB",
    "muted": "#94A3B8",
    "line": "#1F2937",
    "accent": "#38BDF8",
    "ok": "#22C55E",
    "warn": "#F59E0B",
    "bad": "#EF4444",
    "idle": "#64748B",
}


def start_progress_gui(
    *,
    repo_root: Path,
    progress_file: Path,
    run_dir: Path,
    profile_name: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Start the read-only progress HUD as a detached child process.

    The HUD only reads the progress JSON. It does not expose actions back into
    the orchestrator and it never sends game input.
    """
    if not bool(profile.get("showGui", False)):
        return {
            "enabled": False,
            "requested": False,
            "reason": "profile_showGui_false",
            "mode": "read-only-progress-hud",
        }

    script = repo_root / "scripts" / "live_test_gui.py"
    args = [
        sys.executable,
        str(script),
        "--progress-file",
        str(progress_file),
        "--run-directory",
        str(run_dir),
        "--profile-name",
        profile_name,
        "--poll-ms",
        str(profile_gui_poll_milliseconds(profile)),
    ]
    if bool(profile.get("guiAlwaysOnTop", False)):
        args.append("--always-on-top")

    try:
        proc = subprocess.Popen(
            args,
            cwd=str(repo_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception as exc:  # noqa: BLE001 - GUI must never block the run.
        return {
            "enabled": False,
            "requested": True,
            "mode": "read-only-progress-hud",
            "error": f"{type(exc).__name__}:{exc}",
            "args": args,
        }

    return {
        "enabled": True,
        "requested": True,
        "mode": "read-only-progress-hud",
        "processId": proc.pid,
        "progressFile": str(progress_file),
        "runDirectory": str(run_dir),
        "alwaysOnTop": bool(profile.get("guiAlwaysOnTop", False)),
        "infoOnly": True,
        "args": args,
    }


def profile_gui_poll_milliseconds(profile: dict[str, Any]) -> int:
    try:
        value = int(profile.get("guiPollMilliseconds", 500))
    except (TypeError, ValueError):
        return 500
    return max(250, value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Display a read-only live-test HUD.")
    parser.add_argument("--progress-file", help="run-progress.json to watch.")
    parser.add_argument("--run-directory", help="Current run directory.")
    parser.add_argument("--profile-name", help="Live-test profile name.")
    parser.add_argument("--poll-ms", type=int, default=500, help="Progress refresh interval.")
    parser.add_argument("--always-on-top", action="store_true", help="Keep HUD topmost.")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Open the run-progress.json referenced by scripts/captures/latest-live-test-run.json.",
    )
    parser.add_argument(
        "--latest-pointer",
        default=None,
        help="Optional latest-run pointer JSON path for --latest.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use a generated offline demo progress file instead of a live run.",
    )
    parser.add_argument(
        "--demo-scenario",
        choices=("running", "passed", "blocked", "blocked-reference", "blocked-proof"),
        default="running",
        help="Demo payload scenario.",
    )
    parser.add_argument(
        "--demo-output-root",
        default=None,
        help="Optional output root for --demo; default is scripts/captures/gui-demo.",
    )
    parser.add_argument(
        "--write-demo-only",
        action="store_true",
        help="With --demo, write the demo progress file and exit without opening a window.",
    )
    parser.add_argument(
        "--inspect-progress",
        action="store_true",
        help="Read progress JSON, print compact health JSON, and exit without opening a window.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="With --inspect-progress, exit nonzero on contract/freshness/stale warnings.",
    )
    parser.add_argument(
        "--require-ok-run",
        action="store_true",
        help="With --inspect-progress, exit nonzero unless the inspected run health is ok.",
    )
    parser.add_argument(
        "--compact-json",
        action="store_true",
        help="With --inspect-progress, print one-line JSON for scripts.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="With --inspect-progress, print a short human-readable summary instead of JSON.",
    )
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=30,
        help="Running progress older than this is stale for inspect/HUD formatting.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_module()
    if args.demo and args.latest:
        build_parser().error("--demo and --latest are mutually exclusive")
    if args.fail_on_warning and not args.inspect_progress:
        build_parser().error("--fail-on-warning requires --inspect-progress")
    if args.require_ok_run and not args.inspect_progress:
        build_parser().error("--require-ok-run requires --inspect-progress")
    if args.compact_json and not args.inspect_progress:
        build_parser().error("--compact-json requires --inspect-progress")
    if args.summary and not args.inspect_progress:
        build_parser().error("--summary requires --inspect-progress")
    if args.summary and args.compact_json:
        build_parser().error("--summary and --compact-json are mutually exclusive")

    latest: dict[str, Any] | None = None
    if args.latest:
        try:
            latest = resolve_latest_run(
                repo_root=repo_root,
                pointer_file=Path(args.latest_pointer) if args.latest_pointer else None,
            )
        except Exception as exc:  # noqa: BLE001 - launcher should fail clearly, not with a traceback.
            print(
                json.dumps(
                    {
                        "status": "latest-run-unavailable",
                        "error": f"{type(exc).__name__}:{exc}",
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
        progress_file = latest["progressFile"]
        run_dir = latest["runDirectory"]
        profile_name = args.profile_name or str(latest["profileName"])
    elif args.demo:
        run_dir = (
            Path(args.run_directory)
            if args.run_directory
            else Path(args.demo_output_root or (repo_root / "scripts" / "captures" / "gui-demo"))
        )
        progress_file = Path(args.progress_file) if args.progress_file else run_dir / "run-progress.json"
        profile_name = args.profile_name or "GuiDemo"
        write_demo_progress(
            progress_file=progress_file,
            run_dir=run_dir,
            profile_name=profile_name,
            scenario=args.demo_scenario,
        )
        if args.write_demo_only:
            print(
                json.dumps(
                    {
                        "status": "demo-progress-written",
                        "progressFile": str(progress_file),
                        "runDirectory": str(run_dir),
                        "demoScenario": args.demo_scenario,
                    },
                    indent=2,
                )
            )
            return 0
    else:
        progress_file = resolve_progress_file_arg(args.progress_file, args.run_directory)
        required = [("--progress-file or --run-directory", progress_file)]
        if not args.inspect_progress:
            required.extend(
                [
                    ("--run-directory", args.run_directory),
                    ("--profile-name", args.profile_name),
                ]
            )
        missing = [
            name
            for name, value in required
            if not value
        ]
        if missing:
            build_parser().error(f"{', '.join(missing)} required unless --demo is used")
        run_dir = Path(str(args.run_directory)) if args.run_directory else progress_file.parent
        profile_name = str(args.profile_name or "InspectProgress")

    if args.inspect_progress:
        stale_after_seconds = max(1, int(args.stale_after_seconds))
        result = (
            inspect_latest_progress(latest, stale_after_seconds=stale_after_seconds)
            if latest is not None
            else inspect_progress_file(
                progress_file,
                stale_after_seconds=stale_after_seconds,
            )
        )
        if args.fail_on_warning:
            apply_strict_inspect_gate(result)
        if args.require_ok_run:
            apply_run_success_gate(result)
        print(
            format_inspect_summary(result)
            if args.summary
            else format_inspect_json(result, compact=bool(args.compact_json))
        )
        return 0 if inspect_exit_ok(result) else 1

    run_progress_hud(
        progress_file=progress_file,
        run_dir=run_dir,
        profile_name=profile_name,
        poll_ms=max(250, int(args.poll_ms)),
        always_on_top=bool(args.always_on_top),
    )
    return 0


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_latest_run(
    *,
    repo_root: Path,
    pointer_file: Path | None = None,
) -> dict[str, Any]:
    pointer = pointer_file or repo_root / "scripts" / "captures" / "latest-live-test-run.json"
    if not pointer.exists():
        raise FileNotFoundError(f"Latest-run pointer not found: {pointer}")
    with pointer.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Latest-run pointer root must be an object: {pointer}")

    progress_value = data.get("runProgressFile")
    if not progress_value:
        raise ValueError(f"Latest-run pointer missing runProgressFile: {pointer}")
    progress_file = repo_relative_path(repo_root, progress_value)
    run_dir = repo_relative_path(repo_root, data.get("runDirectory") or progress_file.parent)
    summary_value = data.get("runSummaryFile")
    summary_file = (
        repo_relative_path(repo_root, summary_value)
        if summary_value
        else run_dir / "run-summary.json"
    )
    run_dir_inside_repo = path_is_relative_to(run_dir, repo_root)
    progress_file_inside_repo = path_is_relative_to(progress_file, repo_root)
    summary_file_inside_repo = path_is_relative_to(summary_file, repo_root)
    return {
        "pointerFile": pointer,
        "progressFile": progress_file,
        "progressFileExists": progress_file.exists(),
        "progressFileInsideRepo": progress_file_inside_repo,
        "runSummaryFile": summary_file,
        "runSummaryFileExists": summary_file.exists(),
        "runSummaryFileInsideRepo": summary_file_inside_repo,
        "runDirectory": run_dir,
        "runDirectoryInsideRepo": run_dir_inside_repo,
        "profileName": data.get("profileName") or "LatestRun",
        "status": data.get("status"),
        "runHealth": data.get("runHealth") if isinstance(data.get("runHealth"), dict) else None,
        "generatedAtUtc": data.get("generatedAtUtc"),
        "finalSummaryWritten": bool(data.get("finalSummaryWritten")),
    }


def inspect_latest_progress(
    latest: dict[str, Any],
    *,
    now: datetime | None = None,
    stale_after_seconds: int = 30,
) -> dict[str, Any]:
    result = inspect_progress_file(
        latest["progressFile"],
        now=now,
        stale_after_seconds=stale_after_seconds,
    )
    result["latestPointer"] = latest_pointer_summary(
        latest,
        progress_result=result,
        drift_warning_seconds=stale_after_seconds,
    )
    return result


def latest_pointer_summary(
    latest: dict[str, Any],
    *,
    progress_result: dict[str, Any] | None = None,
    drift_warning_seconds: int = 30,
) -> dict[str, Any]:
    run_health = latest.get("runHealth")
    return {
        "pointerFile": str(latest.get("pointerFile")),
        "profileName": latest.get("profileName"),
        "status": latest.get("status"),
        "runHealth": run_health if isinstance(run_health, dict) else None,
        "generatedAtUtc": latest.get("generatedAtUtc"),
        "freshness": latest_pointer_freshness(
            latest,
            progress_result=progress_result,
            drift_warning_seconds=drift_warning_seconds,
        ),
        "finalSummaryWritten": bool(latest.get("finalSummaryWritten")),
        "progressFile": str(latest.get("progressFile")),
        "progressFileExists": bool(latest.get("progressFileExists")),
        "progressFileInsideRepo": bool(latest.get("progressFileInsideRepo")),
        "runDirectory": str(latest.get("runDirectory")),
        "runDirectoryInsideRepo": bool(latest.get("runDirectoryInsideRepo")),
        "runSummaryFile": str(latest.get("runSummaryFile")),
        "runSummaryFileExists": bool(latest.get("runSummaryFileExists")),
        "runSummaryFileInsideRepo": bool(latest.get("runSummaryFileInsideRepo")),
    }


def latest_pointer_freshness(
    latest: dict[str, Any],
    *,
    progress_result: dict[str, Any] | None = None,
    drift_warning_seconds: int = 30,
) -> dict[str, Any]:
    issues: list[str] = []
    pointer_generated_at = latest.get("generatedAtUtc")
    progress_updated_at = progress_result.get("updatedAtUtc") if progress_result else None
    pointer_time = parse_time(pointer_generated_at)
    progress_time = parse_time(progress_updated_at)
    timestamp_gap_seconds = None

    if pointer_time and progress_time:
        timestamp_gap_seconds = int(abs((pointer_time - progress_time).total_seconds()))
        if timestamp_gap_seconds > drift_warning_seconds:
            issues.append(f"latest_pointer_timestamp_drift_seconds:{timestamp_gap_seconds}")
    else:
        if pointer_generated_at:
            issues.append("latest_pointer_timestamp_invalid")
        else:
            issues.append("latest_pointer_timestamp_missing")
        if progress_updated_at:
            issues.append("progress_timestamp_invalid")
        else:
            issues.append("progress_timestamp_missing")

    pointer_status = latest.get("status")
    progress_status = progress_result.get("runStatus") if progress_result else None
    if pointer_status and progress_status and pointer_status != progress_status:
        issues.append(f"latest_pointer_status_mismatch:pointer={pointer_status};progress={progress_status}")

    pointer_health = latest.get("runHealth") if isinstance(latest.get("runHealth"), dict) else {}
    progress_health_result = (
        progress_result.get("runHealth")
        if progress_result and isinstance(progress_result.get("runHealth"), dict)
        else {}
    )
    pointer_state = pointer_health.get("state")
    progress_state = progress_health_result.get("state")
    if pointer_state and progress_state and pointer_state != progress_state:
        issues.append(f"latest_pointer_health_mismatch:pointer={pointer_state};progress={progress_state}")

    if latest.get("runDirectoryInsideRepo") is False:
        issues.append("latest_pointer_run_directory_outside_repo")
    if latest.get("progressFileInsideRepo") is False:
        issues.append("latest_pointer_progress_file_outside_repo")

    return {
        "status": "warning" if issues else "ok",
        "pointerGeneratedAtUtc": pointer_generated_at,
        "progressUpdatedAtUtc": progress_updated_at,
        "timestampGapSeconds": timestamp_gap_seconds,
        "driftWarningSeconds": drift_warning_seconds,
        "issues": issues,
    }


def apply_strict_inspect_gate(result: dict[str, Any]) -> dict[str, Any]:
    warnings = inspect_result_warnings(result)
    result["strict"] = {
        "failOnWarning": True,
        "ok": bool(result.get("ok")) and not warnings,
        "warningCount": len(warnings),
        "warnings": warnings,
    }
    return result


def apply_run_success_gate(result: dict[str, Any]) -> dict[str, Any]:
    health = result.get("runHealth") if isinstance(result.get("runHealth"), dict) else {}
    health_ok = bool(health.get("ok"))
    issues: list[str] = []
    if not bool(result.get("ok")):
        issues.append(f"inspect_not_ok:status={result.get('status') or 'unknown'}")
    if not health_ok:
        state = health.get("state") or "unknown"
        status = health.get("status") or result.get("runStatus") or "unknown"
        issues.append(f"run_not_ok:state={state};status={status}")
    result["runGate"] = {
        "requireOkRun": True,
        "ok": bool(result.get("ok")) and health_ok,
        "issues": issues,
    }
    return result


def format_inspect_json(result: dict[str, Any], *, compact: bool = False) -> str:
    if compact:
        return json.dumps(result, separators=(",", ":"))
    return json.dumps(result, indent=2)


def format_inspect_summary(result: dict[str, Any]) -> str:
    health = result.get("runHealth") if isinstance(result.get("runHealth"), dict) else {}
    contract = result.get("contract") if isinstance(result.get("contract"), dict) else {}
    latest_pointer = (
        result.get("latestPointer")
        if isinstance(result.get("latestPointer"), dict)
        else None
    )
    strict = result.get("strict") if isinstance(result.get("strict"), dict) else None
    run_gate = result.get("runGate") if isinstance(result.get("runGate"), dict) else None

    lines = [
        "RiftReader live-test inspect summary",
        f"Inspect: {result.get('status') or 'unknown'} (ok={str(bool(result.get('ok'))).lower()})",
        f"Profile: {result.get('profileName') or '—'}",
        f"Run status: {result.get('runStatus') or '—'}",
        f"Run health: {health.get('state') or 'unknown'}",
        f"Updated: {result.get('updatedAtUtc') or '—'}",
        f"Latest state: {result.get('latestState') or '—'}",
        f"Latest child: {result.get('latestChild') or '—'}",
        f"Contract: {contract.get('status') or 'unknown'}",
        f"Summary file exists: {str(bool(result.get('runSummaryFileExists'))).lower()}",
    ]

    contract_issues = contract.get("issues") if isinstance(contract.get("issues"), list) else []
    if contract_issues:
        lines.append("Contract issues:")
        lines.extend(f"- {issue}" for issue in contract_issues)

    if latest_pointer is not None:
        freshness = (
            latest_pointer.get("freshness")
            if isinstance(latest_pointer.get("freshness"), dict)
            else {}
        )
        lines.extend(
            [
                f"Latest pointer status: {latest_pointer.get('status') or '—'}",
                f"Latest pointer freshness: {freshness.get('status') or 'unknown'}",
            ]
        )
        freshness_issues = (
            freshness.get("issues") if isinstance(freshness.get("issues"), list) else []
        )
        if freshness_issues:
            lines.append("Latest pointer freshness issues:")
            lines.extend(f"- {issue}" for issue in freshness_issues)

    if strict is not None:
        strict_ok = bool(strict.get("ok"))
        lines.append(
            f"Strict: {'passed' if strict_ok else 'failed'} "
            f"(warnings={strict.get('warningCount') or 0})"
        )
        warnings = strict.get("warnings") if isinstance(strict.get("warnings"), list) else []
        if warnings:
            lines.append("Strict warnings:")
            lines.extend(f"- {warning}" for warning in warnings)

    if run_gate is not None:
        run_gate_ok = bool(run_gate.get("ok"))
        lines.append(f"Run gate: {'passed' if run_gate_ok else 'failed'}")
        issues = run_gate.get("issues") if isinstance(run_gate.get("issues"), list) else []
        if issues:
            lines.append("Run gate issues:")
            lines.extend(f"- {issue}" for issue in issues)

    return "\n".join(lines)


def inspect_exit_ok(result: dict[str, Any]) -> bool:
    ok = bool(result.get("ok"))
    strict = result.get("strict") if isinstance(result.get("strict"), dict) else None
    if strict is not None:
        ok = ok and bool(strict.get("ok"))
    run_gate = result.get("runGate") if isinstance(result.get("runGate"), dict) else None
    if run_gate is not None:
        ok = ok and bool(run_gate.get("ok"))
    return ok


def inspect_result_warnings(result: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    contract = result.get("contract") if isinstance(result.get("contract"), dict) else {}
    if contract.get("status") == "warning":
        issues = contract.get("issues") if isinstance(contract.get("issues"), list) else []
        warnings.extend(f"contract:{issue}" for issue in issues)

    health = result.get("runHealth") if isinstance(result.get("runHealth"), dict) else {}
    health_state = str(health.get("state") or "").lower()
    if health_state in {"stale", "warning"}:
        warnings.append(f"run_health_state:{health_state}")

    latest_pointer = (
        result.get("latestPointer")
        if isinstance(result.get("latestPointer"), dict)
        else {}
    )
    freshness = (
        latest_pointer.get("freshness")
        if isinstance(latest_pointer.get("freshness"), dict)
        else {}
    )
    if freshness.get("status") == "warning":
        issues = freshness.get("issues") if isinstance(freshness.get("issues"), list) else []
        warnings.extend(f"latest_pointer_freshness:{issue}" for issue in issues)
    return warnings


def repo_relative_path(repo_root: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else (repo_root / path).resolve()


def path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_progress_file_arg(progress_file: Any, run_directory: Any = None) -> Path | None:
    if progress_file:
        return Path(str(progress_file))
    if run_directory:
        return Path(str(run_directory)) / "run-progress.json"
    return None


def inspect_progress_file(
    progress_file: Path,
    *,
    now: datetime | None = None,
    stale_after_seconds: int = 30,
) -> dict[str, Any]:
    if not progress_file.exists():
        return {
            "status": "progress-unavailable",
            "ok": False,
            "progressFile": str(progress_file),
            "error": "progress_file_not_found",
        }
    try:
        with progress_file.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except Exception as exc:  # noqa: BLE001 - inspection should report corrupt files as data.
        return {
            "status": "progress-unreadable",
            "ok": False,
            "progressFile": str(progress_file),
            "error": f"{type(exc).__name__}:{exc}",
        }
    if not isinstance(payload, dict):
        return {
            "status": "progress-invalid",
            "ok": False,
            "progressFile": str(progress_file),
            "error": "progress_root_must_be_object",
        }

    run_summary_file = payload.get("runSummaryFile")
    run_summary_file_exists = path_exists_with_fallback(run_summary_file, progress_file.parent)
    health = progress_health(payload, now=now, stale_after_seconds=stale_after_seconds)
    contract = validate_progress_contract(
        payload,
        run_summary_file_exists=run_summary_file_exists,
    )
    return {
        "status": "progress-valid",
        "ok": contract["ok"],
        "progressFile": str(progress_file),
        "profileName": payload.get("profileName"),
        "runDirectory": payload.get("runDirectory"),
        "updatedAtUtc": payload.get("updatedAtUtc"),
        "runSummaryFile": run_summary_file,
        "runSummaryFileExists": run_summary_file_exists,
        "runStatus": payload.get("status"),
        "runHealth": health,
        "contract": contract,
        "issueCount": len(payload.get("issues") or []),
        "latestState": format_latest_state(payload.get("states")),
        "latestChild": format_child_command(payload.get("latestChildCommand")),
        "finalSummaryWritten": bool(payload.get("finalSummaryWritten")),
    }


def path_exists_with_fallback(value: Any, fallback_dir: Path) -> bool:
    if not value:
        return False
    path = Path(str(value))
    if path.exists():
        return True
    if not path.is_absolute() and (fallback_dir / path).exists():
        return True
    return False


def validate_progress_contract(
    payload: dict[str, Any],
    *,
    run_summary_file_exists: bool | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    required = (
        "schemaVersion",
        "mode",
        "profileName",
        "status",
        "updatedAtUtc",
        "runDirectory",
        "runProgressFile",
        "noCheatEngine",
        "savedVariablesUsedAsLiveTruth",
    )
    for key in required:
        if key not in payload:
            issues.append(f"missing_required_field:{key}")

    if payload.get("schemaVersion") != 1:
        issues.append(f"schema_version_unsupported:{payload.get('schemaVersion')}")
    if payload.get("mode") != "rift-live-test-progress":
        issues.append(f"mode_unexpected:{payload.get('mode')}")
    if payload.get("noCheatEngine") is not True:
        issues.append("safety_no_cheat_engine_not_true")
    if payload.get("savedVariablesUsedAsLiveTruth") is not False:
        issues.append("safety_savedvariables_live_truth_not_false")

    if "issues" in payload and not isinstance(payload.get("issues"), list):
        issues.append("issues_field_not_list")
    if "states" in payload and not isinstance(payload.get("states"), list):
        issues.append("states_field_not_list")
    if "runHealth" in payload and not isinstance(payload.get("runHealth"), dict):
        issues.append("runHealth_field_not_object")
    if "runHealth" not in payload:
        issues.append("runHealth_missing")
    if "runGates" not in payload:
        issues.append("runGates_missing")
    if payload.get("finalSummaryWritten") is True and run_summary_file_exists is False:
        issues.append("run_summary_marked_written_but_missing")

    error_count = sum(1 for issue in issues if progress_contract_issue_severity(issue) == "error")
    status = "invalid" if error_count else "warning" if issues else "valid"
    return {
        "status": status,
        "ok": error_count == 0,
        "issues": issues,
        "errorCount": error_count,
        "warningCount": len(issues) - error_count,
    }


def progress_contract_issue_severity(issue: str) -> str:
    text = issue.lower()
    warning_markers = (
        "runhealth_missing",
        "rungates_missing",
        "run_summary_marked_written_but_missing",
    )
    if any(marker in text for marker in warning_markers):
        return "warn"
    return "error"


def write_demo_progress(
    *,
    progress_file: Path,
    run_dir: Path,
    profile_name: str = "GuiDemo",
    scenario: str = "running",
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = demo_progress_payload(
        run_dir=run_dir,
        progress_file=progress_file,
        profile_name=profile_name,
        scenario=scenario,
    )
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    write_json(progress_file, payload)
    return payload


def demo_progress_payload(
    *,
    run_dir: Path,
    progress_file: Path,
    profile_name: str = "GuiDemo",
    scenario: str = "running",
) -> dict[str, Any]:
    summary_file = run_dir / "run-summary.json"
    samples_file = run_dir / "recorder" / "coord-samples.ndjson"
    payload = {
        "schemaVersion": 1,
        "mode": "rift-live-test-progress",
        "profileName": profile_name,
        "status": "running",
        "updatedAtUtc": "2026-05-07T17:05:00Z",
        "runDirectory": str(run_dir),
        "runSummaryFile": str(summary_file),
        "runProgressFile": str(progress_file),
        "live": True,
        "processId": 47560,
        "targetWindowHandle": "0x2122E",
        "movementSent": True,
        "movementAttempted": True,
        "currentCoordinate": {
            "x": 7437.5146484375,
            "y": 885.2191772460938,
            "z": 3055.517822265625,
            "recordedAtUtc": "2026-05-07T16:38:15.4855135Z",
        },
        "coordinateDelta": {
            "deltaX": 0.0517578125,
            "deltaY": 0.0,
            "deltaZ": -0.219970703125,
            "planarDistance": 0.225977833842375,
            "spatialDistance": 0.225977833842375,
        },
        "issues": [],
        "states": [
            {
                "state": "load-profile",
                "status": "passed",
                "recordedAtUtc": "2026-05-07T16:36:12Z",
                "detail": "demo profile loaded",
            },
            {
                "state": "verify-target",
                "status": "passed",
                "recordedAtUtc": "2026-05-07T16:36:13Z",
                "detail": "pid=47560;hwnd=0x2122E",
            },
            {
                "state": "proof-refresh",
                "status": "passed",
                "recordedAtUtc": "2026-05-07T16:37:44Z",
                "summaryFile": str(run_dir / "demo-proof-summary.json"),
            },
            {
                "state": "live-input",
                "status": "passed",
                "recordedAtUtc": "2026-05-07T16:38:16Z",
                "summaryFile": str(summary_file),
            },
        ],
        "childOutputsDirectory": str(run_dir / "child-outputs"),
        "latestChildCommand": {
            "label": "live-input",
            "status": "completed",
            "exitCode": 0,
            "jsonStatus": "passed",
            "durationSeconds": 0.42,
            "ok": True,
            "outputFile": str(run_dir / "child-outputs" / "006-live-input.json"),
        },
        "autoRefreshAttemptsUsed": 0,
        "runGates": {
            "profileMode": "live-input",
            "requireExactTarget": True,
            "requireLiveFlagForInput": True,
            "proofAnchorFile": str(run_dir / "telemetry-proof-coord-anchor.json"),
            "proofAnchorMaxAgeSeconds": 60,
            "minimumPostReadbackAgeBudgetSeconds": 20,
            "referenceMaxAgeSeconds": 180,
            "maxAutoRefreshAttempts": 1,
            "autoRefreshAttemptsUsed": 0,
            "noCheatEngine": True,
            "savedVariablesLiveTruthAllowed": False,
        },
        "noCheatEngine": True,
        "savedVariablesUsedAsLiveTruth": False,
        "finalSummaryWritten": False,
        "coordinateRecordings": [
            {
                "pulseIndex": 1,
                "sampleCount": 9,
                "samplesFile": str(samples_file),
                "pulseSummaryFile": str(run_dir / "recorder" / "coord-pulse-001-summary.json"),
                "phases": {
                    "dry-run-preflight": 3,
                    "live-preflight": 3,
                    "live-post-readback": 3,
                },
            }
        ],
        "coordinateSamplesFile": str(samples_file),
    }
    if scenario == "passed":
        payload["status"] = "passed"
        payload["finalSummaryWritten"] = True
    elif scenario == "blocked":
        payload.update(
            {
                "status": "blocked-target-mismatch",
                "live": False,
                "processId": 123,
                "targetWindowHandle": "not-a-hwnd",
                "movementSent": False,
                "movementAttempted": False,
                "currentCoordinate": None,
                "coordinateDelta": None,
                "issues": ["target_window_handle_invalid:not-a-hwnd"],
                "states": [
                    {
                        "state": "load-profile",
                        "status": "passed",
                        "recordedAtUtc": "2026-05-07T16:36:12Z",
                    },
                    {
                        "state": "verify-target",
                        "status": "blocked-target-mismatch",
                        "recordedAtUtc": "2026-05-07T16:36:13Z",
                        "detail": "target_window_handle_invalid:not-a-hwnd",
                    },
                ],
                "latestChildCommand": None,
                "coordinateRecordings": [],
                "coordinateSamplesFile": None,
                "runGates": {
                    **payload["runGates"],
                    "profileMode": "proof-only",
                },
            }
        )
    elif scenario == "blocked-reference":
        payload.update(
            {
                "status": "blocked-reference-capture",
                "live": False,
                "movementSent": False,
                "movementAttempted": False,
                "currentCoordinate": None,
                "coordinateDelta": None,
                "issues": [
                    "reference_capture_failed:exit=1;status=None",
                    "reference_marker_unavailable:no_usable_rrapicoord1",
                ],
                "states": [
                    {
                        "state": "load-profile",
                        "status": "passed",
                        "recordedAtUtc": "2026-05-07T16:36:12Z",
                    },
                    {
                        "state": "verify-target",
                        "status": "passed",
                        "recordedAtUtc": "2026-05-07T16:36:13Z",
                        "detail": "pid=47560;hwnd=0x2122E",
                    },
                    {
                        "state": "capture-reference",
                        "status": "blocked-reference-capture",
                        "recordedAtUtc": "2026-05-07T16:36:20Z",
                        "detail": "reference_marker_unavailable:no_usable_rrapicoord1",
                    },
                ],
                "latestChildCommand": {
                    "label": "capture-reference",
                    "status": "completed",
                    "exitCode": 1,
                    "durationSeconds": 2.18,
                    "parseError": "No JSON object or array found in command output",
                    "ok": False,
                    "outputFile": str(run_dir / "child-outputs" / "002-capture-reference.json"),
                },
                "coordinateRecordings": [],
                "coordinateSamplesFile": None,
                "runGates": {
                    **payload["runGates"],
                    "profileMode": "proof-only",
                },
            }
        )
    elif scenario == "blocked-proof":
        payload.update(
            {
                "status": "blocked-proof-expired",
                "live": True,
                "movementSent": False,
                "movementAttempted": False,
                "issues": ["proof_anchor_expired:maxAgeSeconds=60"],
                "states": [
                    {
                        "state": "load-profile",
                        "status": "passed",
                        "recordedAtUtc": "2026-05-07T16:36:12Z",
                    },
                    {
                        "state": "verify-target",
                        "status": "passed",
                        "recordedAtUtc": "2026-05-07T16:36:13Z",
                        "detail": "pid=47560;hwnd=0x2122E",
                    },
                    {
                        "state": "dry-run-gate",
                        "status": "blocked-proof-expired",
                        "recordedAtUtc": "2026-05-07T16:36:40Z",
                        "summaryFile": str(run_dir / "blocked-proof-summary.json"),
                    },
                ],
                "latestChildCommand": {
                    "label": "dry-run-gate",
                    "status": "completed",
                    "exitCode": 1,
                    "jsonStatus": "blocked-preflight-proof-expired",
                    "durationSeconds": 0.73,
                    "ok": False,
                    "outputFile": str(run_dir / "child-outputs" / "005-dry-run-gate.json"),
                },
                "coordinateRecordings": [],
                "coordinateSamplesFile": None,
            }
        )
    payload["runHealth"] = progress_health(
        payload,
        now=parse_time(payload.get("updatedAtUtc") or payload.get("generatedAtUtc")),
    )
    return payload


def run_progress_hud(
    *,
    progress_file: Path,
    run_dir: Path,
    profile_name: str,
    poll_ms: int,
    always_on_top: bool,
) -> None:
    # Import lazily so unit tests and --help do not require a GUI subsystem.
    import tkinter as tk
    from tkinter import font as tkfont

    root = tk.Tk()
    app = ProgressHud(
        root=root,
        progress_file=progress_file,
        run_dir=run_dir,
        profile_name=profile_name,
        poll_ms=poll_ms,
        always_on_top=always_on_top,
        tkfont=tkfont,
    )
    app.run()


class ProgressHud:
    def __init__(
        self,
        *,
        root: Any,
        progress_file: Path,
        run_dir: Path,
        profile_name: str,
        poll_ms: int,
        always_on_top: bool,
        tkfont: Any,
    ) -> None:
        self.root = root
        self.progress_file = progress_file
        self.run_dir = run_dir
        self.profile_name = profile_name
        self.poll_ms = poll_ms
        self.always_on_top = always_on_top
        self.tkfont = tkfont
        self._lights: dict[str, Any] = {}
        self._labels: dict[str, Any] = {}
        self._last_payload: dict[str, Any] | None = None

        self._build()

    def run(self) -> None:
        self._poll()
        self.root.mainloop()

    def _build(self) -> None:
        import tkinter as tk

        self.root.title(f"RiftReader HUD - {self.profile_name}")
        self.root.geometry("580x840")
        self.root.minsize(520, 700)
        self.root.configure(bg=PALETTE["bg"])
        if self.always_on_top:
            self.root.attributes("-topmost", True)

        self._build_menu()

        title_font = self.tkfont.Font(family="Segoe UI", size=16, weight="bold")
        sub_font = self.tkfont.Font(family="Segoe UI", size=9)
        label_font = self.tkfont.Font(family="Segoe UI", size=9, weight="bold")
        value_font = self.tkfont.Font(family="Segoe UI", size=10)
        mono_font = self.tkfont.Font(family="Consolas", size=9)

        outer = tk.Frame(self.root, bg=PALETTE["bg"], padx=18, pady=16)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=PALETTE["bg"])
        header.pack(fill="x")
        self._lights["status"] = self._light(header, size=18)
        self._lights["status"].pack(side="left", padx=(0, 10))
        title_area = tk.Frame(header, bg=PALETTE["bg"])
        title_area.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_area,
            text="RiftReader Orchestrator",
            fg=PALETTE["text"],
            bg=PALETTE["bg"],
            font=title_font,
            anchor="w",
        ).pack(fill="x")
        self._labels["subtitle"] = tk.Label(
            title_area,
            text=f"{self.profile_name} • waiting for progress",
            fg=PALETTE["muted"],
            bg=PALETTE["bg"],
            font=sub_font,
            anchor="w",
        )
        self._labels["subtitle"].pack(fill="x")

        self._section(
            outer,
            "Indicators",
            [
                ("target", "Target"),
                ("proof", "Proof"),
                ("input", "Input"),
                ("recorder", "Recorder"),
                ("safety", "Safety"),
            ],
            label_font=label_font,
            value_font=value_font,
        )

        self._info_grid(
            outer,
            "Live Info",
            [
                ("status", "Status"),
                ("health", "Health"),
                ("run", "Run"),
                ("progress", "Progress"),
                ("updated", "Updated"),
                ("progress_age", "Progress age"),
                ("elapsed", "Elapsed"),
                ("latest", "Latest"),
                ("child", "Child"),
                ("pid", "PID / HWND"),
                ("live", "Live flag"),
                ("gates", "Gates"),
                ("proof_budget", "Proof budget"),
                ("safety", "Safety"),
                ("movement", "Movement"),
                ("coord", "Coordinate"),
                ("delta", "Delta"),
                ("series", "Series"),
                ("recorder", "Recorder"),
                ("recorder_file", "Samples"),
                ("summary", "Summary"),
            ],
            label_font=label_font,
            value_font=value_font,
        )

        issues_card = self._card(outer, "Issues", label_font)
        self._labels["issues"] = tk.Text(
            issues_card,
            height=4,
            wrap="word",
            bg=PALETTE["card_2"],
            fg=PALETTE["text"],
            insertbackground=PALETTE["text"],
            relief="flat",
            font=mono_font,
            padx=10,
            pady=8,
        )
        self._labels["issues"].pack(fill="both", expand=True)
        self._labels["issues"].configure(state="disabled")

        states_card = self._card(outer, "State History", label_font)
        self._labels["states"] = tk.Text(
            states_card,
            height=8,
            wrap="none",
            bg=PALETTE["card_2"],
            fg=PALETTE["text"],
            insertbackground=PALETTE["text"],
            relief="flat",
            font=mono_font,
            padx=10,
            pady=8,
        )
        self._labels["states"].pack(fill="both", expand=True)
        self._labels["states"].configure(state="disabled")

        footer = tk.Label(
            outer,
            text="Info-only HUD: reads run-progress.json; no controls, no input, no CE.",
            fg=PALETTE["muted"],
            bg=PALETTE["bg"],
            font=sub_font,
            anchor="w",
        )
        footer.pack(fill="x", pady=(10, 0))

    def _build_menu(self) -> None:
        import tkinter as tk

        menu = tk.Menu(self.root, tearoff=False, bg=PALETTE["card"], fg=PALETTE["text"])
        options = tk.Menu(menu, tearoff=False, bg=PALETTE["card"], fg=PALETTE["text"])
        options.add_command(label="Information-only mode: On", state="disabled")
        options.add_command(label="Orchestrator controls: Locked", state="disabled")
        options.add_command(
            label=f"Always on top: {'On' if self.always_on_top else 'Off'}",
            state="disabled",
        )
        options.add_separator()
        options.add_command(label="Legend: green = passed / safe", state="disabled")
        options.add_command(label="Legend: amber = running / waiting", state="disabled")
        options.add_command(label="Legend: red = blocked / failed", state="disabled")
        options.add_command(label="Legend: gray = idle / not used", state="disabled")
        options.add_separator()
        options.add_command(label="Future: theme / visibility options", state="disabled")
        menu.add_cascade(label="Options", menu=options)
        self.root.config(menu=menu)

    def _section(
        self,
        parent: Any,
        title: str,
        indicators: list[tuple[str, str]],
        *,
        label_font: Any,
        value_font: Any,
    ) -> None:
        import tkinter as tk

        card = self._card(parent, title, label_font)
        row = tk.Frame(card, bg=PALETTE["card"])
        row.pack(fill="x")
        for key, label in indicators:
            box = tk.Frame(row, bg=PALETTE["card"])
            box.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self._lights[key] = self._light(box, size=14)
            self._lights[key].pack(anchor="center")
            tk.Label(
                box,
                text=label,
                fg=PALETTE["muted"],
                bg=PALETTE["card"],
                font=value_font,
            ).pack(anchor="center", pady=(5, 0))

    def _info_grid(
        self,
        parent: Any,
        title: str,
        rows: list[tuple[str, str]],
        *,
        label_font: Any,
        value_font: Any,
    ) -> None:
        import tkinter as tk

        card = self._card(parent, title, label_font)
        for key, label in rows:
            row = tk.Frame(card, bg=PALETTE["card"])
            row.pack(fill="x", pady=2)
            tk.Label(
                row,
                text=label,
                width=12,
                fg=PALETTE["muted"],
                bg=PALETTE["card"],
                font=label_font,
                anchor="w",
            ).pack(side="left")
            self._labels[key] = tk.Label(
                row,
                text="—",
                fg=PALETTE["text"],
                bg=PALETTE["card"],
                font=value_font,
                anchor="w",
                justify="left",
            )
            self._labels[key].pack(side="left", fill="x", expand=True)

    def _card(self, parent: Any, title: str, label_font: Any) -> Any:
        import tkinter as tk

        card = tk.Frame(parent, bg=PALETTE["card"], padx=14, pady=12)
        card.pack(fill="x", pady=(14, 0))
        tk.Label(
            card,
            text=title.upper(),
            fg=PALETTE["accent"],
            bg=PALETTE["card"],
            font=label_font,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))
        return card

    def _light(self, parent: Any, *, size: int) -> Any:
        import tkinter as tk

        canvas = tk.Canvas(
            parent,
            width=size,
            height=size,
            bg=parent["bg"],
            highlightthickness=0,
            bd=0,
        )
        canvas.create_oval(2, 2, size - 2, size - 2, fill=PALETTE["idle"], outline="")
        return canvas

    def _poll(self) -> None:
        payload = self._read_payload()
        if payload:
            self._last_payload = payload
            self._render(payload)
        else:
            self._render_waiting()
        self.root.after(self.poll_ms, self._poll)

    def _read_payload(self) -> dict[str, Any] | None:
        if not self.progress_file.exists():
            return None
        try:
            with self.progress_file.open("r", encoding="utf-8-sig") as handle:
                data = json.load(handle)
        except Exception:  # noqa: BLE001 - transient partial writes should not kill the HUD.
            return self._last_payload
        return data if isinstance(data, dict) else None

    def _render_waiting(self) -> None:
        self._set_light("status", "warn")
        self._labels["subtitle"].configure(text=f"{self.profile_name} • waiting for progress file")

    def _render(self, payload: dict[str, Any]) -> None:
        status = str(payload.get("status") or "running")
        self._set_light("status", status_color(status))
        self._set_indicator_lights(payload)

        self._labels["subtitle"].configure(
            text=f"{payload.get('profileName') or self.profile_name} • {status}"
        )
        self._set_text("status", status)
        self._set_text("health", format_run_health(payload))
        self._set_text("run", shorten_path(payload.get("runDirectory") or self.run_dir))
        self._set_text("progress", shorten_path(payload.get("runProgressFile") or self.progress_file))
        self._set_text("updated", short_time(payload.get("updatedAtUtc") or payload.get("generatedAtUtc")))
        self._set_text("progress_age", format_progress_age(payload))
        self._set_text("elapsed", format_elapsed(payload))
        self._set_text("latest", format_latest_state(payload.get("states")))
        self._set_text("child", format_child_command(payload.get("latestChildCommand")))
        self._set_text("pid", f"{payload.get('processId')} / {payload.get('targetWindowHandle')}")
        self._set_text("live", "enabled" if payload.get("live") else "disabled")
        self._set_text("gates", format_run_gates(payload.get("runGates")))
        self._set_text("proof_budget", format_proof_budget(payload.get("runGates")))
        self._set_text("safety", format_safety(payload))
        self._set_text(
            "movement",
            f"sent={bool(payload.get('movementSent'))} attempted={bool(payload.get('movementAttempted'))}",
        )
        self._set_text("coord", format_coord(payload.get("currentCoordinate")))
        self._set_text("delta", format_delta(payload.get("coordinateDelta") or payload.get("seriesCoordinateDelta")))
        self._set_text("series", format_series(payload))
        self._set_text("recorder", format_recorder(payload.get("coordinateRecordings")))
        self._set_text("recorder_file", shorten_path(payload.get("coordinateSamplesFile")))
        self._set_text("summary", format_summary_file(payload))
        self._set_text_block("issues", format_issues(payload.get("issues")))
        self._set_text_block("states", format_states(payload.get("states")))

    def _set_indicator_lights(self, payload: dict[str, Any]) -> None:
        states = payload.get("states") if isinstance(payload.get("states"), list) else []
        state_status = {str(item.get("state")): str(item.get("status")) for item in states if isinstance(item, dict)}
        status = str(payload.get("status") or "")
        status_light = status_color(status)

        target_status = state_status.get("verify-target")
        self._set_light(
            "target",
            "ok"
            if target_status == "passed"
            else "bad"
            if target_status and status_color(target_status) == "bad"
            else "warn",
        )
        self._set_light(
            "proof",
            status_light
            if status_light in {"ok", "bad"}
            else "ok"
            if any(name in state_status for name in ("proof-refresh", "post-readback"))
            else "warn",
        )
        self._set_light(
            "input",
            "ok"
            if payload.get("movementSent")
            else "bad"
            if status in {"input-failed", "input-no-movement", "partial-series-stopped"}
            else "idle",
        )
        self._set_light("recorder", "ok" if payload.get("coordinateRecordings") else "idle")
        self._set_light(
            "safety",
            "ok"
            if payload.get("noCheatEngine") and not payload.get("savedVariablesUsedAsLiveTruth")
            else "bad",
        )

    def _set_text(self, key: str, value: str) -> None:
        self._labels[key].configure(text=value or "—")

    def _set_text_block(self, key: str, value: str) -> None:
        widget = self._labels[key]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value or "—")
        widget.configure(state="disabled")

    def _set_light(self, key: str, color_key: str) -> None:
        canvas = self._lights.get(key)
        if not canvas:
            return
        canvas.itemconfig(1, fill=PALETTE.get(color_key, PALETTE["idle"]))


def status_color(status: str) -> str:
    text = status.lower()
    if text.startswith("passed"):
        return "ok"
    if (
        text.startswith("blocked")
        or text.startswith("failed")
        or text.endswith("failed")
        or "no-movement" in text
    ):
        return "bad"
    if "partial" in text or "refresh" in text or text == "running":
        return "warn"
    return "idle"


def format_coord(coord: Any) -> str:
    if not isinstance(coord, dict):
        return "—"
    x = coord.get("x")
    y = coord.get("y")
    z = coord.get("z")
    when = short_time(coord.get("recordedAtUtc"))
    if x is None or y is None or z is None:
        return "—"
    return f"X={float(x):.3f}  Y={float(y):.3f}  Z={float(z):.3f}  @ {when}"


def format_delta(delta: Any) -> str:
    if not isinstance(delta, dict):
        return "—"
    planar = delta.get("planarDistance")
    dx = delta.get("deltaX", 0.0)
    dy = delta.get("deltaY", 0.0)
    dz = delta.get("deltaZ", 0.0)
    if planar is None:
        return "—"
    try:
        return (
            f"planar={float(planar):.3f}  "
            f"dX={float(dx or 0.0):.3f} "
            f"dY={float(dy or 0.0):.3f} "
            f"dZ={float(dz or 0.0):.3f}"
        )
    except (TypeError, ValueError):
        return f"planar={planar}"


def format_series(payload: dict[str, Any]) -> str:
    requested = payload.get("requestedPulseCount")
    completed = payload.get("completedPulseCount")
    if requested is None and completed is None:
        return "—"
    return f"{completed or 0} / {requested or 0} pulses"


def format_latest_state(states: Any) -> str:
    if not isinstance(states, list) or not states:
        return "waiting"
    for item in reversed(states):
        if isinstance(item, dict):
            state = item.get("state") or "unknown"
            status = item.get("status") or "unknown"
            return f"{state}: {status}"
    return "waiting"


def format_recorder(recordings: Any) -> str:
    if not isinstance(recordings, list) or not recordings:
        return "idle"
    total_samples = 0
    pulse_count = 0
    for recording in recordings:
        if not isinstance(recording, dict):
            continue
        pulse_count += 1
        try:
            total_samples += int(recording.get("sampleCount") or 0)
        except (TypeError, ValueError):
            pass
    return f"{pulse_count} pulse(s), {total_samples} sample(s)"


def format_child_command(command: Any) -> str:
    if not isinstance(command, dict):
        return "waiting"
    label = command.get("label") or "unknown"
    status = command.get("status") or "unknown"
    exit_code = command.get("exitCode")
    json_status = command.get("jsonStatus")
    duration = command.get("durationSeconds")
    suffix = []
    if exit_code is not None:
        suffix.append(f"exit={exit_code}")
    if json_status:
        suffix.append(f"json={json_status}")
    if duration is not None:
        try:
            suffix.append(f"{float(duration):.1f}s")
        except (TypeError, ValueError):
            pass
    if command.get("parseError"):
        suffix.append("json=parse-failed")
    suffix_text = f" ({', '.join(suffix)})" if suffix else ""
    return f"{label}: {status}{suffix_text}"


def format_run_gates(gates: Any) -> str:
    if not isinstance(gates, dict):
        return "—"
    labels = [str(gates.get("profileMode") or "unknown")]
    labels.append("exact target" if gates.get("requireExactTarget") else "target gate off")
    labels.append("live flag" if gates.get("requireLiveFlagForInput") else "live flag off")
    return " • ".join(labels)


def format_proof_budget(gates: Any) -> str:
    if not isinstance(gates, dict):
        return "—"
    anchor_max = gates.get("proofAnchorMaxAgeSeconds")
    post_budget = gates.get("minimumPostReadbackAgeBudgetSeconds")
    reference_max = gates.get("referenceMaxAgeSeconds")
    refresh_used = gates.get("autoRefreshAttemptsUsed", 0)
    refresh_max = gates.get("maxAutoRefreshAttempts", 0)
    parts = []
    if anchor_max is not None:
        parts.append(f"anchor≤{anchor_max}s")
    if post_budget is not None:
        parts.append(f"post≥{post_budget}s")
    if reference_max is not None:
        parts.append(f"ref≤{reference_max}s")
    parts.append(f"refresh={refresh_used}/{refresh_max}")
    return " • ".join(parts)


def format_safety(payload: dict[str, Any]) -> str:
    gates = payload.get("runGates") if isinstance(payload.get("runGates"), dict) else {}
    no_ce = payload.get("noCheatEngine") is True or gates.get("noCheatEngine") is True
    saved_variables_live = (
        payload.get("savedVariablesUsedAsLiveTruth") is True
        or gates.get("savedVariablesLiveTruthAllowed") is True
    )
    ce_label = "no CE" if no_ce else "CE flag unknown"
    saved_variables_label = (
        "no SavedVariables live truth" if not saved_variables_live else "SavedVariables live truth enabled"
    )
    return f"{ce_label} • {saved_variables_label} • read-only HUD"


def format_summary_file(payload: dict[str, Any]) -> str:
    state = "written" if payload.get("finalSummaryWritten") else "pending"
    return f"{state} • {shorten_path(payload.get('runSummaryFile'))}"


def format_run_health(payload: dict[str, Any]) -> str:
    health = payload.get("runHealth") if isinstance(payload.get("runHealth"), dict) else None
    if not health:
        health = progress_health(payload)
    state = health.get("state") or "unknown"
    issue_count = health.get("issueCount")
    primary = health.get("primaryIssue")
    latest_child_status = health.get("latestChildStatus")
    latest_child_ok = health.get("latestChildOk")
    text = f"{state}"
    if issue_count:
        text += f" • issues={issue_count}"
    if primary:
        text += f" • {primary}"
    if latest_child_status:
        child_text = f"child={latest_child_status}"
        if latest_child_ok is True:
            child_text += ":ok"
        elif latest_child_ok is False:
            child_text += ":not-ok"
        text += f" • {child_text}"
    return text


def progress_health(
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
    stale_after_seconds: int = 30,
) -> dict[str, Any]:
    status = str(payload.get("status") or "unknown")
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    latest_child = (
        payload.get("latestChildCommand")
        if isinstance(payload.get("latestChildCommand"), dict)
        else {}
    )
    latest_child_ok = latest_child.get("ok") if isinstance(latest_child.get("ok"), bool) else None
    state = classify_progress_health(status)
    updated = parse_time(payload.get("updatedAtUtc") or payload.get("generatedAtUtc"))
    age_seconds = None
    if updated:
        current = now or datetime.now(timezone.utc)
        age_seconds = max(0, int((current.astimezone(timezone.utc) - updated).total_seconds()))
        if state == "running" and age_seconds > stale_after_seconds:
            state = "stale"
    return {
        "state": state,
        "status": status,
        "ok": state == "ok",
        "ageSeconds": age_seconds,
        "issueCount": len(issues),
        "primaryIssue": issues[0] if issues else None,
        "movementSent": bool(payload.get("movementSent")),
        "movementAttempted": bool(payload.get("movementAttempted")),
        "finalSummaryWritten": bool(payload.get("finalSummaryWritten")),
        "latestChildStatus": latest_child.get("status"),
        "latestChildOk": latest_child_ok,
        "noCheatEngine": payload.get("noCheatEngine") is True,
        "savedVariablesUsedAsLiveTruth": payload.get("savedVariablesUsedAsLiveTruth") is True,
    }


def classify_progress_health(status: str) -> str:
    text = str(status or "").lower()
    if text.startswith("passed"):
        return "ok"
    if text == "running" or text == "refreshing":
        return "running"
    if "partial" in text or "low-age" in text or "age-budget" in text:
        return "warning"
    if text.startswith("blocked"):
        return "blocked"
    if text.startswith("failed") or text.endswith("failed") or "internal-error" in text:
        return "failed"
    return "unknown"


def format_progress_age(
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
    stale_after_seconds: int = 30,
) -> str:
    updated = parse_time(payload.get("updatedAtUtc") or payload.get("generatedAtUtc"))
    if not updated:
        return "—"
    current = now or datetime.now(timezone.utc)
    seconds = max(0, int((current.astimezone(timezone.utc) - updated).total_seconds()))
    if seconds < 60:
        label = f"{seconds}s since update"
    else:
        minutes, remainder = divmod(seconds, 60)
        if minutes < 60:
            label = f"{minutes}m {remainder:02d}s since update"
        else:
            hours, minutes = divmod(minutes, 60)
            label = f"{hours}h {minutes:02d}m since update"
    if str(payload.get("status") or "").lower() == "running" and seconds > stale_after_seconds:
        return f"stale: {label}"
    return label


def format_elapsed(payload: dict[str, Any]) -> str:
    states = payload.get("states")
    started = None
    if isinstance(states, list):
        for item in states:
            if isinstance(item, dict):
                started = parse_time(item.get("recordedAtUtc"))
                if started:
                    break
    ended = parse_time(payload.get("updatedAtUtc") or payload.get("generatedAtUtc"))
    if not started or not ended:
        return "—"
    seconds = max(0, int((ended - started).total_seconds()))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    return f"{minutes:02d}m {seconds:02d}s"


def format_issues(issues: Any) -> str:
    if not issues:
        return "none"
    if isinstance(issues, list):
        return "\n".join(format_issue_line(item) for item in issues[:8])
    return str(issues)


def format_issue_line(issue: Any) -> str:
    text = str(issue)
    severity = issue_severity(text)
    if severity == "error":
        return f"ERROR • {text}"
    if severity == "warn":
        return f"WARN  • {text}"
    return f"INFO  • {text}"


def issue_severity(issue: str) -> str:
    text = issue.lower()
    error_markers = (
        "blocked",
        "failed",
        "mismatch",
        "invalid",
        "unavailable",
        "expired",
        "not_found",
        "not-found",
        "internal_error",
    )
    if any(marker in text for marker in error_markers):
        return "error"
    warn_markers = ("warning", "stale", "low-age", "low_age", "age_budget", "remaining=")
    if any(marker in text for marker in warn_markers):
        return "warn"
    return "info"


def format_states(states: Any) -> str:
    if not isinstance(states, list) or not states:
        return "waiting for state updates"
    lines = []
    for item in states[-10:]:
        if not isinstance(item, dict):
            continue
        detail = item.get("detail") or item.get("summaryFile") or ""
        if detail:
            detail = " | " + shorten_path(detail)
        lines.append(f"{short_time(item.get('recordedAtUtc'))}  {item.get('state')}: {item.get('status')}{detail}")
    return "\n".join(lines)


def short_time(value: Any) -> str:
    if not value:
        return "—"
    text = str(value)
    if "T" in text:
        return text.split("T", 1)[1].replace("+00:00", "Z").replace(".000000", "")[:12]
    return text


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def shorten_path(value: Any) -> str:
    if not value:
        return "—"
    text = str(value)
    parts = text.replace("/", "\\").split("\\")
    if len(parts) <= 3:
        return text
    return "…\\" + "\\".join(parts[-3:])
