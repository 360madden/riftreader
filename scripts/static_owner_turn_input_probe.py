#!/usr/bin/env python3
"""Probe exact-target turn input backends against static-owner yaw readback.

This is a bounded evidence helper for the current navigation blocker: forward
SendInput can move the player, but the currently tried turn keys do not change
the static-owner facing/yaw chain.  The helper runs fresh pre/post static-owner
state readbacks around each approved input attempt and records durable JSON
evidence for each key/backend combination.

It does not attach a debugger, use Cheat Engine, promote proof/truth, write
provider repos, or mutate Git state.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .static_owner_facing_discovery import normalize_degrees
    from .workflow_common import (
        base_safety,
        full_summary_from_compact,
        repo_root,
        run_child,
        safe_mapping,
        utc_iso,
        utc_stamp,
        write_json,
    )
except ImportError:  # pragma: no cover - direct script execution path
    from static_owner_facing_discovery import normalize_degrees  # type: ignore
    from workflow_common import (  # type: ignore
        base_safety,
        full_summary_from_compact,
        repo_root,
        run_child,
        safe_mapping,
        utc_iso,
        utc_stamp,
        write_json,
    )


SCHEMA_VERSION = 1
DEFAULT_KEYS = ("left", "right", "a", "d", "q", "e")
DEFAULT_BACKENDS = (
    "csharp-scancode",
    "csharp-virtualkey",
    "legacy-window-message",
    "legacy-foreground-sendinput",
)
LEFT_KEYS = {"left", "a", "q"}
RIGHT_KEYS = {"right", "d", "e"}


def infer_direction(key: str) -> str | None:
    lowered = key.lower()
    if lowered in LEFT_KEYS:
        return "left"
    if lowered in RIGHT_KEYS:
        return "right"
    return None


def expected_delta_sign(direction: str | None) -> int | None:
    if direction == "left":
        return -1
    if direction == "right":
        return 1
    return None


def state_command(args: argparse.Namespace, root: Path, output_root: Path) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_facing_discovery.py"),
        "state",
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--current-truth-json",
        str(args.current_truth_json),
        "--samples",
        str(args.samples),
        "--interval-seconds",
        str(args.interval_seconds),
        "--expect-stationary",
        "--json",
    ]


def csharp_sendinput_command(
    *,
    args: argparse.Namespace,
    root: Path,
    target: Mapping[str, Any],
    key: str,
    input_mode: str,
) -> list[str]:
    return [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "scripts" / "send-rift-key-csharp.ps1"),
        "--key",
        str(key),
        "--hold-ms",
        str(args.hold_milliseconds),
        "--process-name",
        str(target.get("processName") or args.process_name),
        "--pid",
        str(target.get("processId")),
        "--hwnd",
        str(target.get("targetWindowHandle")),
        "--title-contains",
        str(args.title_contains),
        "--input-mode",
        str(input_mode),
        "--focus-delay-ms",
        str(args.focus_delay_milliseconds),
        "--json",
    ]


def legacy_post_key_command(
    *,
    args: argparse.Namespace,
    root: Path,
    target: Mapping[str, Any],
    key: str,
    require_foreground: bool,
) -> list[str]:
    command = [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "scripts" / "post-rift-key.ps1"),
        "-Key",
        str(key),
        "-HoldMilliseconds",
        str(args.hold_milliseconds),
        "-TargetProcessName",
        str(target.get("processName") or args.process_name),
        "-TargetProcessId",
        str(target.get("processId")),
        "-TargetWindowHandle",
        str(target.get("targetWindowHandle")),
        "-SkipBackgroundFocus",
    ]
    if require_foreground:
        command.append("-RequireTargetForeground")
    else:
        command.append("-UseWindowMessage")
    return command


def input_command(
    *,
    args: argparse.Namespace,
    root: Path,
    target: Mapping[str, Any],
    key: str,
    backend: str,
) -> list[str]:
    if backend == "csharp-scancode":
        return csharp_sendinput_command(
            args=args,
            root=root,
            target=target,
            key=key,
            input_mode="ScanCode",
        )
    if backend == "csharp-virtualkey":
        return csharp_sendinput_command(
            args=args,
            root=root,
            target=target,
            key=key,
            input_mode="VirtualKey",
        )
    if backend == "legacy-window-message":
        return legacy_post_key_command(
            args=args,
            root=root,
            target=target,
            key=key,
            require_foreground=False,
        )
    if backend == "legacy-foreground-sendinput":
        return legacy_post_key_command(
            args=args,
            root=root,
            target=target,
            key=key,
            require_foreground=True,
        )
    raise ValueError(f"unsupported-backend:{backend}")


def latest_state(summary: Mapping[str, Any]) -> dict[str, Any]:
    return safe_mapping(summary.get("latestState"))


def coordinate_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, float]:
    dx = float(after["x"]) - float(before["x"])
    dy = float(after["y"]) - float(before["y"])
    dz = float(after["z"]) - float(before["z"])
    return {
        "x": dx,
        "y": dy,
        "z": dz,
        "planar": math.hypot(dx, dz),
        "distance3d": math.sqrt((dx * dx) + (dy * dy) + (dz * dz)),
    }


def analyze_attempt(
    *,
    key: str,
    backend: str,
    pre_summary: Mapping[str, Any],
    post_summary: Mapping[str, Any],
    minimum_yaw_delta_degrees: float,
    max_planar_drift: float,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    direction = infer_direction(key)
    expected_sign = expected_delta_sign(direction)
    pre_state = latest_state(pre_summary)
    post_state = latest_state(post_summary)
    pre_yaw = pre_state.get("yawDegrees")
    post_yaw = post_state.get("yawDegrees")
    if pre_yaw is None or post_yaw is None:
        blockers.append("pre-post-yaw-required")
        signed_delta = None
        absolute_delta = None
    else:
        signed_delta = normalize_degrees(float(post_yaw) - float(pre_yaw))
        absolute_delta = abs(signed_delta)
        if absolute_delta < minimum_yaw_delta_degrees:
            blockers.append("yaw-delta-below-threshold")
        if (
            expected_sign is not None
            and absolute_delta >= minimum_yaw_delta_degrees
            and math.copysign(1, signed_delta or 0.0) != expected_sign
        ):
            blockers.append("yaw-delta-opposite-expected-direction")

    pre_coord = safe_mapping(pre_state.get("coordinate"))
    post_coord = safe_mapping(post_state.get("coordinate"))
    if pre_coord and post_coord:
        drift = coordinate_delta(pre_coord, post_coord)
        if drift["planar"] > max_planar_drift:
            warnings.append("planar-drift-exceeded")
    else:
        drift = {}
        blockers.append("pre-post-coordinate-required")

    return {
        "status": "passed" if not blockers else "blocked",
        "candidateOnly": True,
        "actionableForNavigation": False,
        "movementPermission": False,
        "facingPromotion": False,
        "key": key,
        "backend": backend,
        "inferredDirection": direction,
        "preYawDegrees": pre_yaw,
        "postYawDegrees": post_yaw,
        "signedYawDeltaDegrees": signed_delta,
        "absoluteYawDeltaDegrees": absolute_delta,
        "minimumYawDeltaDegrees": minimum_yaw_delta_degrees,
        "coordinateDelta": drift,
        "maxPlanarDrift": max_planar_drift,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
    }


def validate_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if not args.keys:
        errors.append("keys-required")
    if not args.backends:
        errors.append("backends-required")
    unsupported = sorted(set(args.backends) - set(DEFAULT_BACKENDS))
    if unsupported:
        errors.append(f"unsupported-backends:{','.join(unsupported)}")
    if args.hold_milliseconds <= 0:
        errors.append("hold-milliseconds-must-be-positive")
    if args.post_input_wait_milliseconds < 0:
        errors.append("post-input-wait-milliseconds-must-be-nonnegative")
    if args.samples < 1:
        errors.append("samples-must-be-positive")
    if args.interval_seconds < 0:
        errors.append("interval-seconds-must-be-nonnegative")
    if args.minimum_yaw_delta_degrees < 0:
        errors.append("minimum-yaw-delta-degrees-must-be-nonnegative")
    if args.max_planar_drift < 0:
        errors.append("max-planar-drift-must-be-nonnegative")
    if args.command_timeout_seconds <= 0:
        errors.append("command-timeout-seconds-must-be-positive")
    return sorted(set(errors))


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-turn-input-probe-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    errors = validate_args(args)
    safety = base_safety()
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-turn-input-probe",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "operator": {
            "dryRun": bool(args.dry_run),
            "probeApproved": bool(args.probe_approved),
            "keys": list(args.keys),
            "backends": list(args.backends),
            "holdMilliseconds": int(args.hold_milliseconds),
            "postInputWaitMilliseconds": int(args.post_input_wait_milliseconds),
            "stopOnFirstSuccess": bool(args.stop_on_first_success),
        },
        "attempts": [],
        "successfulAttempts": [],
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
    if not args.dry_run and not args.probe_approved:
        summary["status"] = "blocked"
        summary["verdict"] = "probe-approval-required"
        summary["blockers"].append("probe-approved-flag-required")
        return summary

    try:
        attempt_index = 0
        stop = False
        for key in args.keys:
            if stop:
                break
            for backend in args.backends:
                if stop:
                    break
                attempt_index += 1
                label_prefix = f"{attempt_index:03d}-{backend}-{key}".replace(" ", "_")
                pre = run_child(
                    label=f"{label_prefix}-pre-state",
                    command=state_command(args, root, output_root),
                    cwd=root,
                    child_dir=child_dir,
                    timeout_seconds=float(args.command_timeout_seconds),
                )
                summary["childCommands"].append(pre)
                attempt: dict[str, Any] = {
                    "attemptIndex": attempt_index,
                    "key": key,
                    "backend": backend,
                    "inputSent": False,
                    "movementSent": False,
                    "preStateCommand": pre,
                    "postStateCommand": None,
                    "inputCommand": None,
                    "analysis": None,
                    "status": "failed",
                    "blockers": [],
                    "warnings": [],
                    "errors": [],
                }
                if not pre["ok"] or not isinstance(pre.get("json"), Mapping):
                    attempt["status"] = "failed"
                    attempt["errors"].append("pre-state-readback-failed")
                    summary["attempts"].append(attempt)
                    continue
                pre_full = full_summary_from_compact(pre["json"])
                attempt["preStateSummaryJson"] = safe_mapping(pre["json"]).get("summaryJson")
                if pre_full.get("status") != "passed":
                    attempt["status"] = "blocked"
                    attempt["blockers"].append("pre-state-readback-not-passed")
                    summary["attempts"].append(attempt)
                    continue
                target = safe_mapping(pre_full.get("target"))
                if not target.get("processId") or not target.get("targetWindowHandle"):
                    attempt["status"] = "blocked"
                    attempt["blockers"].append("exact-target-metadata-missing")
                    summary["attempts"].append(attempt)
                    continue

                if args.dry_run:
                    attempt["status"] = "planned"
                    attempt["inputCommandPlan"] = input_command(
                        args=args,
                        root=root,
                        target=target,
                        key=key,
                        backend=backend,
                    )
                    summary["attempts"].append(attempt)
                    continue

                inp = run_child(
                    label=f"{label_prefix}-input",
                    command=input_command(
                        args=args,
                        root=root,
                        target=target,
                        key=key,
                        backend=backend,
                    ),
                    cwd=root,
                    child_dir=child_dir,
                    timeout_seconds=float(args.command_timeout_seconds),
                )
                summary["childCommands"].append(inp)
                attempt["inputCommand"] = inp
                attempt["inputSent"] = True
                attempt["movementSent"] = True
                safety["inputSent"] = True
                safety["movementSent"] = True
                if not inp["ok"]:
                    attempt["status"] = "failed"
                    attempt["errors"].append("input-command-failed")
                    summary["attempts"].append(attempt)
                    continue

                if args.post_input_wait_milliseconds:
                    time.sleep(float(args.post_input_wait_milliseconds) / 1000.0)

                post = run_child(
                    label=f"{label_prefix}-post-state",
                    command=state_command(args, root, output_root),
                    cwd=root,
                    child_dir=child_dir,
                    timeout_seconds=float(args.command_timeout_seconds),
                )
                summary["childCommands"].append(post)
                attempt["postStateCommand"] = post
                if not post["ok"] or not isinstance(post.get("json"), Mapping):
                    attempt["status"] = "failed"
                    attempt["errors"].append("post-state-readback-failed")
                    summary["attempts"].append(attempt)
                    continue
                post_full = full_summary_from_compact(post["json"])
                attempt["postStateSummaryJson"] = safe_mapping(post["json"]).get("summaryJson")
                if post_full.get("status") != "passed":
                    attempt["status"] = "blocked"
                    attempt["blockers"].append("post-state-readback-not-passed")
                    summary["attempts"].append(attempt)
                    continue

                analysis = analyze_attempt(
                    key=key,
                    backend=backend,
                    pre_summary=pre_full,
                    post_summary=post_full,
                    minimum_yaw_delta_degrees=float(args.minimum_yaw_delta_degrees),
                    max_planar_drift=float(args.max_planar_drift),
                )
                attempt["analysis"] = analysis
                attempt["status"] = analysis["status"]
                attempt["blockers"].extend(analysis["blockers"])
                attempt["warnings"].extend(analysis["warnings"])
                summary["attempts"].append(attempt)
                if analysis["status"] == "passed":
                    success = {
                        "attemptIndex": attempt_index,
                        "key": key,
                        "backend": backend,
                        "signedYawDeltaDegrees": analysis["signedYawDeltaDegrees"],
                        "absoluteYawDeltaDegrees": analysis["absoluteYawDeltaDegrees"],
                        "coordinateDelta": analysis["coordinateDelta"],
                    }
                    summary["successfulAttempts"].append(success)
                    if args.stop_on_first_success:
                        stop = True

        if args.dry_run:
            summary["status"] = "passed"
            summary["verdict"] = "turn-input-probe-dry-run-built"
            summary["warnings"].append("dry-run-only-no-input-sent")
        elif summary["successfulAttempts"]:
            summary["status"] = "passed"
            summary["verdict"] = "turn-input-backend-yaw-delta-validated"
            summary["warnings"].append("candidate-facing-yaw-not-promoted")
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "no-turn-input-backend-produced-yaw-delta"
            summary["blockers"].append("no-key-backend-produced-yaw-delta")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "turn-input-probe-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")

    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    attempts = summary.get("attempts", [])
    successes = summary.get("successfulAttempts", [])
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "attemptCount": len(attempts) if isinstance(attempts, Sequence) else 0,
        "successfulAttemptCount": len(successes) if isinstance(successes, Sequence) else 0,
        "successfulAttempts": successes,
        "movementSent": safe_mapping(summary.get("safety")).get("movementSent"),
        "inputSent": safe_mapping(summary.get("safety")).get("inputSent"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner turn input probe",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Results",
        "",
        f"- Attempts: `{len(summary.get('attempts', []))}`",
        f"- Successful attempts: `{len(summary.get('successfulAttempts', []))}`",
        "",
        "## Successful attempts",
        "",
    ]
    successes = summary.get("successfulAttempts", [])
    if successes:
        for item in successes:
            item_map = safe_mapping(item)
            lines.append(
                f"- `{item_map.get('backend')}` / `{item_map.get('key')}`: "
                f"`{item_map.get('signedYawDeltaDegrees')}` deg"
            )
    else:
        lines.append("- None")
    lines.extend([
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
    parser = argparse.ArgumentParser(description="Probe exact-target turn input backends against static-owner yaw")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--keys", nargs="+", default=list(DEFAULT_KEYS))
    parser.add_argument("--backends", nargs="+", choices=DEFAULT_BACKENDS, default=list(DEFAULT_BACKENDS))
    parser.add_argument("--hold-milliseconds", type=int, default=250)
    parser.add_argument("--post-input-wait-milliseconds", type=int, default=350)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.1)
    parser.add_argument("--minimum-yaw-delta-degrees", type=float, default=1.0)
    parser.add_argument("--max-planar-drift", type=float, default=1.5)
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--focus-delay-milliseconds", type=int, default=250)
    parser.add_argument("--command-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe-approved", action="store_true")
    parser.add_argument("--no-stop-on-first-success", dest="stop_on_first_success", action="store_false")
    parser.set_defaults(stop_on_first_success=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    if summary.get("status") == "passed":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
