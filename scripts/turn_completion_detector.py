#!/usr/bin/env python3
"""Detect and verify turn convergence to a target bearing via pulse-and-poll.

Replaces the "fire-and-forget calibrated turn rate" approach with active
measurement: short turn-key pulses are sent, then the pointer-chain yaw is
re-read until the target bearing is achieved, a timeout occurs, or an
overshoot is detected.

Safety:
- Only sends the requested turn direction (left/right) — never auto-corrects.
- Cross-checks the engine's 0x304 turn-rate discriminator against the commanded
  direction and surfaces dissonance as a warning.
- Fail-closed: timeout, overshoot, and readback failure all return blocked/failed.

Integration points:
- ``continuous_route_runner.py`` calls this instead of the old fire-and-forget
  ``turn_stimulus_capture.py`` pattern.
- ``route_step.py`` remains forward-only; the turn block stays but with an
  updated reason indicating that a turn-completion subprocess should handle it.
"""  # noqa: D205
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .nav_state_readback import read_nav_state
    from .static_owner_facing_discovery import normalize_degrees
    from .static_owner_nav_route_step import base_safety, load_json_object, preview, safe_mapping, write_json
except ImportError:  # pragma: no cover — direct script execution path
    from nav_state_readback import read_nav_state  # type: ignore
    from static_owner_facing_discovery import normalize_degrees  # type: ignore
    from static_owner_nav_route_step import base_safety, load_json_object, preview, safe_mapping, write_json  # type: ignore


SCHEMA_VERSION = 1

# Default pulse parameters — tuned for ~0.177 deg/ms turn rate
DEFAULT_PULSE_HOLD_MS = 50          # "tick" of turn key — ~8.9° at calibrated rate
DEFAULT_MAX_PULSES = 25             # 25×50ms = 1250ms = ~221° max turn budget
DEFAULT_ALIGNMENT_THRESHOLD_DEGREES = 7.5
DEFAULT_SETTLE_MS = 150             # wait for engine to update yaw after pulse
DEFAULT_PULSE_INTERVAL_MS = 100     # extra gap between settle end and next read

# Direction-to-sign mapping for yaw-delta validation
EXPECTED_SIGN: dict[str, float] = {
    "left": -1.0,
    "right": 1.0,
}

# Default key mappings
DEFAULT_KEYS: dict[str, str] = {
    "left": "left",
    "right": "right",
}


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_child(
    *,
    label: str,
    command: Sequence[str],
    cwd: Path,
    child_dir: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run a subprocess and capture its JSON output."""
    child_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = child_dir / f"{label}.stdout.txt"
    stderr_path = child_dir / f"{label}.stderr.txt"
    command_path = child_dir / f"{label}.command.json"
    started = time.perf_counter()
    started_utc = utc_iso()
    parsed: Any = None
    parse_error: str | None = None
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
        if stdout.strip():
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError as exc:
                parse_error = f"JSONDecodeError:{exc}"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        exit_code = 124
        parse_error = f"TimeoutExpired:{exc}"

    duration = time.perf_counter() - started
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    envelope: dict[str, Any] = {
        "label": label,
        "command": list(command),
        "cwd": str(cwd),
        "startedAtUtc": started_utc,
        "endedAtUtc": utc_iso(),
        "durationSeconds": duration,
        "exitCode": exit_code,
        "ok": exit_code == 0,
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
        "stdoutPreview": preview(stdout),
        "stderrPreview": preview(stderr),
        "json": parsed,
        "jsonParseError": parse_error,
    }
    write_json(command_path, {key: value for key, value in envelope.items() if key != "json"})
    envelope["commandPath"] = str(command_path)
    return envelope


def send_pulse_command(
    *,
    root: Path,
    key: str,
    hold_ms: int,
    title_contains: str,
    input_mode: str,
    focus_delay_ms: int = 250,
) -> list[str]:
    """Build a SendInput pulse command via the C# SendInput PowerShell wrapper."""
    return [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "scripts" / "send-rift-key-csharp.ps1"),
        "--key", str(key),
        "--hold-ms", str(hold_ms),
        "--title-contains", str(title_contains),
        "--input-mode", str(input_mode),
        "--focus-delay-ms", str(focus_delay_ms),
        "--json",
    ]


def validate_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if args.direction not in EXPECTED_SIGN:
        errors.append("direction-must-be-left-or-right")
    if args.target_bearing_degrees is None and args.signed_bearing_delta_degrees is None:
        errors.append("target-bearing-degrees-or-signed-bearing-delta-degrees-required")
    if args.target_bearing_degrees is not None and args.signed_bearing_delta_degrees is not None:
        errors.append("target-bearing-degrees-and-signed-bearing-delta-degrees-are-mutually-exclusive")
    if args.alignment_threshold_degrees < 0:
        errors.append("alignment-threshold-degrees-must-be-nonnegative")
    if args.max_pulses < 1:
        errors.append("max-pulses-must-be-positive")
    if args.pulse_hold_ms <= 0:
        errors.append("pulse-hold-ms-must-be-positive")
    if args.pulse_interval_ms < 0:
        errors.append("pulse-interval-ms-must-be-nonnegative")
    if args.settle_ms < 0:
        errors.append("settle-ms-must-be-nonnegative")
    if args.command_timeout_seconds <= 0:
        errors.append("command-timeout-seconds-must-be-positive")
    return sorted(set(errors))


def _read_yaw(
    *,
    root: Path,
    current_truth_json: str,
    timeout_seconds: float,
) -> tuple[float | None, str | None, dict[str, Any]]:
    """Read current yaw via the nav_state_readback helper.

    Returns (yawDegrees | None, error | None, full_readback_dict).
    """
    result = read_nav_state(
        root=root,
        use_current_truth=True,
        current_truth_json=current_truth_json,
        timeout_seconds=timeout_seconds,
    )
    if not result["ok"] or result["yawDegrees"] is None:
        return None, result.get("error") or "yaw-degrees-unavailable", result
    return float(result["yawDegrees"]), None, result


def _cross_check_turn_rate(
    direction: str,
    turn_rate_classification: str,
    pulse_index: int,
) -> tuple[list[str], list[str]]:
    """Cross-check engine 0x304 turn rate against commanded direction.

    Returns (agreements, warnings).
    """
    agreements: list[str] = []
    warnings: list[str] = []
    if not turn_rate_classification or turn_rate_classification in ("unknown", "aligned"):
        return agreements, warnings

    if turn_rate_classification == direction:
        agreements.append(
            f"pulse-{pulse_index}: engine-0x304-agrees-with-commanded-{direction}"
        )
    else:
        warnings.append(
            f"pulse-{pulse_index}: sent-{direction}-but-engine-0x304-indicates-{turn_rate_classification}"
        )
    return agreements, warnings


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"turn-completion-detector-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=True)

    errors = validate_args(args)
    safety = base_safety()
    key = args.key or DEFAULT_KEYS.get(str(args.direction), str(args.direction))
    # target_bearing resolved after pre-turn yaw readback if using signed delta
    target_bearing_explicit: float | None = float(args.target_bearing_degrees) if args.target_bearing_degrees is not None else None
    signed_delta: float | None = float(args.signed_bearing_delta_degrees) if args.signed_bearing_delta_degrees is not None else None
    alignment_threshold = float(args.alignment_threshold_degrees)

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "turn-completion-detector",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "operator": {
            "turnApproved": bool(args.turn_approved),
            "direction": str(args.direction),
            "targetBearingDegrees": target_bearing_explicit,
            "signedBearingDeltaDegrees": signed_delta,
            "alignmentThresholdDegrees": alignment_threshold,
            "maxPulses": int(args.max_pulses),
            "pulseHoldMs": int(args.pulse_hold_ms),
        },
        "preYawDegrees": None,
        "postYawDegrees": None,
        "targetBearingDegrees": target_bearing_explicit,
        "achievedBearingDegrees": None,
        "bearingErrorDegrees": None,
        "totalPulses": 0,
        "totalHoldMs": 0,
        "totalYawDeltaDegrees": 0.0,
        "pulseHistory": [],
        "turnRate0x304CrossCheck": {
            "agreements": [],
            "warnings": [],
        },
        "childCommands": [],
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }
    if errors:
        return summary

    if not args.turn_approved:
        summary["status"] = "blocked"
        summary["verdict"] = "turn-approval-required"
        summary["blockers"].append("turn-approved-flag-required")
        return summary

    try:
        # ── Step 1: pre-turn yaw readback ──
        pre_yaw, pre_error, pre_readback = _read_yaw(
            root=root,
            current_truth_json=str(args.current_truth_json),
            timeout_seconds=float(args.command_timeout_seconds),
        )
        if pre_yaw is None:
            summary["status"] = "failed"
            summary["verdict"] = "pre-turn-yaw-readback-failed"
            summary["errors"].append(pre_error or "pre-turn-yaw-unavailable")
            return summary
        summary["preYawDegrees"] = pre_yaw

        # Resolve target bearing from signed delta if not explicitly provided
        if target_bearing_explicit is not None:
            target_bearing = target_bearing_explicit
        elif signed_delta is not None:
            target_bearing = normalize_degrees(pre_yaw + signed_delta)
            summary["targetBearingDegrees"] = target_bearing
            summary["operator"]["resolvedTargetBearingDegrees"] = target_bearing
        else:
            raise ValueError("neither-target-bearing-nor-signed-delta-provided")

        initial_bearing_error = normalize_degrees(target_bearing - pre_yaw)
        initial_error_sign = math.copysign(1.0, initial_bearing_error) if abs(initial_bearing_error) > 0 else 0.0

        # ── Step 2: cross-check engine 0x304 on first read ──
        turn_class = str(pre_readback.get("turnRateClassification") or "unknown")
        if turn_class not in ("unknown", "aligned"):
            if turn_class == str(args.direction):
                summary["turnRate0x304CrossCheck"]["agreements"].append(
                    f"pre-turn: engine-0x304-agrees-with-commanded-{args.direction}"
                )
            else:
                summary["turnRate0x304CrossCheck"]["warnings"].append(
                    f"pre-turn: engine-0x304-shows-{turn_class}-but-commanded-{args.direction}"
                )

        # ── Step 3: pulse loop ──
        current_yaw = pre_yaw
        for pulse_idx in range(int(args.max_pulses)):
            # Read current yaw (skip on first iteration — we already have it)
            if pulse_idx > 0:
                current_yaw, read_error, readback = _read_yaw(
                    root=root,
                    current_truth_json=str(args.current_truth_json),
                    timeout_seconds=float(args.command_timeout_seconds),
                )
                if current_yaw is None:
                    summary["status"] = "failed"
                    summary["verdict"] = "post-pulse-yaw-readback-failed"
                    summary["errors"].append(read_error or "post-pulse-yaw-unavailable")
                    return summary

                # Cross-check 0x304
                turn_class = str(readback.get("turnRateClassification") or "unknown")
                agreements, warn = _cross_check_turn_rate(
                    str(args.direction), turn_class, pulse_idx,
                )
                summary["turnRate0x304CrossCheck"]["agreements"].extend(agreements)
                summary["turnRate0x304CrossCheck"]["warnings"].extend(warn)

            bearing_error = normalize_degrees(target_bearing - current_yaw)
            absolute_error = abs(bearing_error)

            summary["achievedBearingDegrees"] = current_yaw
            summary["bearingErrorDegrees"] = bearing_error
            summary["postYawDegrees"] = current_yaw

            pulse_record: dict[str, Any] = {
                "pulseIndex": pulse_idx,
                "yawDegrees": current_yaw,
                "bearingErrorDegrees": bearing_error,
                "absoluteBearingErrorDegrees": absolute_error,
            }
            summary["pulseHistory"].append(pulse_record)

            # Check convergence
            if absolute_error <= alignment_threshold:
                summary["status"] = "passed"
                summary["verdict"] = "turn-converged"
                summary["totalYawDeltaDegrees"] = normalize_degrees(current_yaw - pre_yaw)
                break

            # Check overshoot — sign flip relative to initial error
            if pulse_idx > 0 and initial_error_sign != 0.0:
                current_sign = math.copysign(1.0, bearing_error) if absolute_error > 0 else 0.0
                if current_sign != 0.0 and current_sign != initial_error_sign:
                    summary["status"] = "blocked"
                    summary["verdict"] = "turn-overcorrected"
                    summary["blockers"].append(
                        f"yaw-error-sign-flipped-from-{initial_error_sign:+.0f}-to-{current_sign:+.0f}"
                    )
                    summary["totalYawDeltaDegrees"] = normalize_degrees(current_yaw - pre_yaw)
                    break

            # Haven't converged yet — send a pulse
            cmd = send_pulse_command(
                root=root,
                key=key,
                hold_ms=int(args.pulse_hold_ms),
                title_contains=str(args.title_contains),
                input_mode=str(args.input_mode),
            )
            pulse_child = run_child(
                label=f"pulse-{pulse_idx:03d}",
                command=cmd,
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=float(args.command_timeout_seconds),
            )
            summary["childCommands"].append(pulse_child)
            safety["inputSent"] = True
            safety["movementSent"] = True
            summary["totalPulses"] += 1
            summary["totalHoldMs"] += int(args.pulse_hold_ms)

            pulse_record["pulseSent"] = True
            pulse_record["pulseOk"] = pulse_child["ok"]

            if not pulse_child["ok"]:
                summary["status"] = "failed"
                summary["verdict"] = "turn-pulse-failed"
                summary["errors"].append(f"pulse-{pulse_idx}-failed")
                return summary

            # Wait settle + interval before next read
            if float(args.settle_ms) > 0:
                time.sleep(float(args.settle_ms) / 1000.0)
            if float(args.pulse_interval_ms) > 0:
                time.sleep(float(args.pulse_interval_ms) / 1000.0)

        else:
            # Loop exhausted without convergence or overshoot
            summary["status"] = "blocked"
            summary["verdict"] = "turn-timeout"
            summary["blockers"].append(f"max-pulses-exhausted:{args.max_pulses}")
            if summary["postYawDegrees"] is not None and summary["preYawDegrees"] is not None:
                summary["totalYawDeltaDegrees"] = normalize_degrees(
                    float(summary["postYawDegrees"]) - float(summary["preYawDegrees"])
                )

    except subprocess.TimeoutExpired as exc:
        summary["status"] = "failed"
        summary["verdict"] = "turn-completion-command-timeout"
        summary["errors"].append(f"TimeoutExpired:{exc}")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "turn-completion-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")

    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Compact the summary for CLI output (strips heavy child command envelopes)."""
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "direction": summary.get("operator", {}).get("direction") if isinstance(summary.get("operator"), Mapping) else None,
        "targetBearingDegrees": summary.get("targetBearingDegrees"),
        "preYawDegrees": summary.get("preYawDegrees"),
        "postYawDegrees": summary.get("postYawDegrees"),
        "achievedBearingDegrees": summary.get("achievedBearingDegrees"),
        "bearingErrorDegrees": summary.get("bearingErrorDegrees"),
        "totalPulses": summary.get("totalPulses"),
        "totalHoldMs": summary.get("totalHoldMs"),
        "totalYawDeltaDegrees": summary.get("totalYawDeltaDegrees"),
        "pulseCount": len(summary.get("pulseHistory", [])),
        "turnRateCrossCheckWarnings": sum(
            1 for _ in (summary.get("turnRate0x304CrossCheck") or {}).get("warnings", [])
        ) if isinstance(summary.get("turnRate0x304CrossCheck"), Mapping) else 0,
        "movementSent": (summary.get("safety") or {}).get("movementSent") if isinstance(summary.get("safety"), Mapping) else False,
        "inputSent": (summary.get("safety") or {}).get("inputSent") if isinstance(summary.get("safety"), Mapping) else False,
        "summaryJson": (summary.get("artifacts") or {}).get("summaryJson") if isinstance(summary.get("artifacts"), Mapping) else None,
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a Markdown summary of the turn completion run."""
    operator = safe_mapping(summary.get("operator"))
    safety = safe_mapping(summary.get("safety"))
    cross_check = safe_mapping(summary.get("turnRate0x304CrossCheck"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Turn completion detector",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Parameters",
        "",
        f"- Direction: `{operator.get('direction')}`",
        f"- Target bearing: `{operator.get('targetBearingDegrees')}`",
        f"- Alignment threshold: `{operator.get('alignmentThresholdDegrees')}°`",
        f"- Max pulses: `{operator.get('maxPulses')}` × `{operator.get('pulseHoldMs')}ms`",
        "",
        "## Results",
        "",
        f"- Pre-turn yaw: `{summary.get('preYawDegrees')}`",
        f"- Post-turn yaw: `{summary.get('postYawDegrees')}`",
        f"- Achieved bearing: `{summary.get('achievedBearingDegrees')}`",
        f"- Bearing error: `{summary.get('bearingErrorDegrees')}`",
        f"- Total yaw delta: `{summary.get('totalYawDeltaDegrees')}`",
        f"- Pulses sent: `{summary.get('totalPulses')}` / `{summary.get('totalHoldMs')}ms` total hold",
        "",
        "## 0x304 turn rate cross-check",
        "",
        f"- Agreements: `{len(cross_check.get('agreements', []))}`",
        f"- Warnings: `{len(cross_check.get('warnings', []))}`",
    ]
    if cross_check.get("warnings"):
        lines.append("")
        lines.extend(f"- :warning: {w}" for w in cross_check.get("warnings", []))
    lines.extend([
        "",
        "## Safety",
        "",
        f"- Movement sent: `{safety.get('movementSent')}`",
        f"- Input sent: `{safety.get('inputSent')}`",
        f"- Cheat Engine: `{not bool(safety.get('noCheatEngine'))}`",
        "",
        "## Artifacts",
        "",
        f"- Summary JSON: `{artifacts.get('summaryJson')}`",
        f"- Run directory: `{artifacts.get('runDirectory')}`",
    ])
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect and verify turn convergence to a target bearing via pulse-and-poll",
    )
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--direction", choices=("left", "right"), required=True,
        help="Turn direction (matches engine 0x304 sign convention)")
    parser.add_argument("--key", help="Override key name (default: left/right)")
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--target-bearing-degrees", type=float,
        help="Target bearing in degrees (0=North, 90=East)")
    target_group.add_argument("--signed-bearing-delta-degrees", type=float,
        help="Signed delta from current yaw to target bearing (turn completion detector reads yaw internally)")
    parser.add_argument("--alignment-threshold-degrees", type=float,
        default=DEFAULT_ALIGNMENT_THRESHOLD_DEGREES,
        help=f"Acceptable bearing error margin (default: {DEFAULT_ALIGNMENT_THRESHOLD_DEGREES}°)")
    parser.add_argument("--max-pulses", type=int, default=DEFAULT_MAX_PULSES,
        help=f"Maximum turn-key pulses before timeout (default: {DEFAULT_MAX_PULSES})")
    parser.add_argument("--pulse-hold-ms", type=int, default=DEFAULT_PULSE_HOLD_MS,
        help=f"Turn key hold duration per pulse in ms (default: {DEFAULT_PULSE_HOLD_MS})")
    parser.add_argument("--pulse-interval-ms", type=int, default=DEFAULT_PULSE_INTERVAL_MS,
        help=f"Extra delay between settle and next read in ms (default: {DEFAULT_PULSE_INTERVAL_MS})")
    parser.add_argument("--settle-ms", type=int, default=DEFAULT_SETTLE_MS,
        help=f"Post-pulse settle time in ms before reading yaw (default: {DEFAULT_SETTLE_MS})")
    parser.add_argument("--input-mode", choices=("ScanCode", "VirtualKey"), default="ScanCode")
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--command-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--turn-approved", action="store_true",
        help="Required safety gate: approve sending turn key input")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(
        build_markdown(summary), encoding="utf-8",
    )
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    if summary.get("status") == "passed":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
