#!/usr/bin/env python3
"""Probe bounded exact-target mouse-look turns against static-owner yaw.

Keyboard turn inputs currently execute without error but do not change the
static-owner yaw/facing candidate.  This helper tries the next bounded input
surface: right-button mouse-look drags sent through Win32 ``SendInput`` after
exact PID/HWND foreground validation.

It is evidence collection only.  It does not attach a debugger, use Cheat
Engine, promote proof/truth, write provider repos, or mutate Git state.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import sys
import time
from ctypes import wintypes
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
DEFAULT_DIRECTIONS = ("left", "right")
DEFAULT_PIXELS = (80, 160, 320)

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
SW_RESTORE = 9


ULONG_PTR = wintypes.WPARAM


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


LPINPUT = ctypes.POINTER(INPUT)


def parse_hwnd(value: Any) -> int:
    """Parse a decimal or hex HWND from static-owner target metadata."""
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("hwnd-must-be-positive")
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError("hwnd-required")
    base = 16 if text.lower().startswith("0x") else 10
    hwnd = int(text, base)
    if hwnd <= 0:
        raise ValueError("hwnd-must-be-positive")
    return hwnd


def hwnd_to_hex(hwnd: Any) -> str:
    return f"0x{parse_hwnd(hwnd):X}"


def expected_delta_sign(direction: str) -> int:
    if direction == "left":
        return -1
    if direction == "right":
        return 1
    raise ValueError(f"unsupported-direction:{direction}")


def direction_to_dx(direction: str, pixels: int) -> int:
    return expected_delta_sign(direction) * int(pixels)


def split_delta(total: int, steps: int) -> list[int]:
    """Split an integer mouse delta into *steps* chunks that sum to *total*."""
    if steps < 1:
        raise ValueError("steps-must-be-positive")
    sign = -1 if total < 0 else 1
    absolute = abs(int(total))
    base = absolute // steps
    remainder = absolute % steps
    return [sign * (base + (1 if index < remainder else 0)) for index in range(steps)]


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


def target_from_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    target = safe_mapping(summary.get("target"))
    if not target.get("processId"):
        raise ValueError("target-process-id-required")
    if not target.get("targetWindowHandle"):
        raise ValueError("target-window-handle-required")
    return {
        "processName": target.get("processName") or "rift_x64",
        "processId": int(target["processId"]),
        "targetWindowHandle": hwnd_to_hex(target["targetWindowHandle"]),
    }


def get_user32() -> Any:
    if not hasattr(ctypes, "WinDLL"):
        raise RuntimeError("windows-ctypes-windll-required")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.SendInput.argtypes = [wintypes.UINT, LPINPUT, ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    return user32


def process_id_for_hwnd(user32: Any, hwnd: int) -> int:
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value)


def foreground_info(user32: Any) -> dict[str, Any]:
    hwnd = int(user32.GetForegroundWindow() or 0)
    return {
        "hwnd": hwnd_to_hex(hwnd) if hwnd else None,
        "processId": process_id_for_hwnd(user32, hwnd) if hwnd else None,
    }


def client_center_screen_point(user32: Any, hwnd: int) -> dict[str, int]:
    rect = wintypes.RECT()
    if not user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        raise RuntimeError(f"GetClientRect-failed:{ctypes.get_last_error()}")
    point = POINT((int(rect.right) - int(rect.left)) // 2, (int(rect.bottom) - int(rect.top)) // 2)
    if not user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(point)):
        raise RuntimeError(f"ClientToScreen-failed:{ctypes.get_last_error()}")
    return {
        "clientX": int((int(rect.right) - int(rect.left)) // 2),
        "clientY": int((int(rect.bottom) - int(rect.top)) // 2),
        "screenX": int(point.x),
        "screenY": int(point.y),
        "clientWidth": int(rect.right) - int(rect.left),
        "clientHeight": int(rect.bottom) - int(rect.top),
    }


def mouse_input(*, flags: int, dx: int = 0, dy: int = 0) -> INPUT:
    event = INPUT()
    event.type = INPUT_MOUSE
    event.union.mi = MOUSEINPUT(
        dx=int(dx),
        dy=int(dy),
        mouseData=0,
        dwFlags=int(flags),
        time=0,
        dwExtraInfo=0,
    )
    return event


def send_input_events(user32: Any, events: Sequence[INPUT]) -> int:
    array = (INPUT * len(events))(*events)
    sent = int(user32.SendInput(len(events), array, ctypes.sizeof(INPUT)))
    if sent != len(events):
        raise RuntimeError(f"SendInput-sent-{sent}-of-{len(events)}:lastError={ctypes.get_last_error()}")
    return sent


def write_mouse_attempt_envelope(child_dir: Path, label: str, envelope: Mapping[str, Any]) -> str:
    path = child_dir / f"{label}.command.json"
    write_json(path, envelope)
    return str(path)


def perform_mouse_turn(
    *,
    label: str,
    child_dir: Path,
    target: Mapping[str, Any],
    direction: str,
    pixels: int,
    steps: int,
    hold_milliseconds: int,
    focus_delay_milliseconds: int,
    require_foreground: bool,
) -> dict[str, Any]:
    """Focus the exact target, right-drag the mouse, and return a command envelope."""
    child_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    started_utc = utc_iso()
    errors: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    ok = False
    sent_events = 0
    right_down_sent = False
    user32: Any | None = None
    hwnd = parse_hwnd(target.get("targetWindowHandle"))
    expected_pid = int(target.get("processId") or 0)
    try:
        user32 = get_user32()
        details["foregroundBefore"] = foreground_info(user32)
        if not user32.IsWindow(wintypes.HWND(hwnd)):
            blockers.append("target-window-not-found")
            raise RuntimeError("target-window-not-found")
        actual_pid = process_id_for_hwnd(user32, hwnd)
        details["targetWindowProcessId"] = actual_pid
        if actual_pid != expected_pid:
            blockers.append("target-window-pid-mismatch")
            raise RuntimeError(f"target-window-pid-mismatch:{actual_pid}!={expected_pid}")

        user32.ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)
        user32.BringWindowToTop(wintypes.HWND(hwnd))
        user32.SetForegroundWindow(wintypes.HWND(hwnd))
        if focus_delay_milliseconds:
            time.sleep(focus_delay_milliseconds / 1000.0)
        details["foregroundAfterFocus"] = foreground_info(user32)
        if require_foreground:
            foreground = safe_mapping(details["foregroundAfterFocus"])
            if foreground.get("processId") != expected_pid:
                blockers.append("target-not-foreground")
                raise RuntimeError(
                    "target-not-foreground:"
                    f"{foreground.get('processId')}!={expected_pid}"
                )
            if parse_hwnd(foreground.get("hwnd")) != hwnd:
                blockers.append("target-not-exact-foreground-window")
                raise RuntimeError(
                    "target-not-exact-foreground-window:"
                    f"{foreground.get('hwnd')}!={hwnd_to_hex(hwnd)}"
                )

        center = client_center_screen_point(user32, hwnd)
        details["clientCenter"] = center
        if not user32.SetCursorPos(center["screenX"], center["screenY"]):
            raise RuntimeError(f"SetCursorPos-failed:{ctypes.get_last_error()}")

        dx_total = direction_to_dx(direction, int(pixels))
        dx_steps = split_delta(dx_total, int(steps))
        details["mouseDelta"] = {
            "direction": direction,
            "pixels": int(pixels),
            "dxTotal": dx_total,
            "steps": dx_steps,
            "holdMilliseconds": int(hold_milliseconds),
        }

        send_input_events(user32, [mouse_input(flags=MOUSEEVENTF_RIGHTDOWN)])
        sent_events += 1
        right_down_sent = True
        delay_seconds = (hold_milliseconds / 1000.0) / max(1, len(dx_steps))
        for dx in dx_steps:
            if dx:
                send_input_events(user32, [mouse_input(flags=MOUSEEVENTF_MOVE, dx=dx)])
                sent_events += 1
            if delay_seconds:
                time.sleep(delay_seconds)
        ok = True
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{type(exc).__name__}:{exc}")
    finally:
        if user32 is not None and right_down_sent:
            try:
                send_input_events(user32, [mouse_input(flags=MOUSEEVENTF_RIGHTUP)])
                sent_events += 1
            except Exception as exc:  # noqa: BLE001
                ok = False
                errors.append(f"right-up-failed:{type(exc).__name__}:{exc}")
        if user32 is not None:
            try:
                details["foregroundAfterInput"] = foreground_info(user32)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"foreground-after-input-unavailable:{type(exc).__name__}:{exc}")

    duration = time.perf_counter() - started
    envelope: dict[str, Any] = {
        "label": label,
        "kind": "python-win32-mouse-look-sendinput",
        "startedAtUtc": started_utc,
        "endedAtUtc": utc_iso(),
        "durationSeconds": duration,
        "command": [
            "python-inproc-win32-sendinput",
            "--hwnd",
            hwnd_to_hex(hwnd),
            "--pid",
            str(expected_pid),
            "--direction",
            str(direction),
            "--pixels",
            str(pixels),
            "--steps",
            str(steps),
        ],
        "target": {
            "processName": target.get("processName"),
            "processId": expected_pid,
            "targetWindowHandle": hwnd_to_hex(hwnd),
        },
        "input": {
            "direction": direction,
            "pixels": int(pixels),
            "steps": int(steps),
            "holdMilliseconds": int(hold_milliseconds),
        },
        "ok": ok,
        "exitCode": 0 if ok else 1,
        "sentEvents": sent_events,
        "details": details,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
    }
    envelope["commandPath"] = write_mouse_attempt_envelope(child_dir, label, envelope)
    return envelope


def analyze_attempt(
    *,
    direction: str,
    pixels: int,
    pre_summary: Mapping[str, Any],
    post_summary: Mapping[str, Any],
    minimum_yaw_delta_degrees: float,
    max_planar_drift: float,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
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
        elif math.copysign(1, signed_delta or 0.0) != expected_delta_sign(direction):
            warnings.append("yaw-delta-opposite-expected-direction")

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
        "direction": direction,
        "pixels": int(pixels),
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
    if not args.directions:
        errors.append("directions-required")
    unsupported_directions = sorted(set(args.directions) - set(DEFAULT_DIRECTIONS))
    if unsupported_directions:
        errors.append(f"unsupported-directions:{','.join(unsupported_directions)}")
    if not args.pixels:
        errors.append("pixels-required")
    if any(int(item) <= 0 for item in args.pixels):
        errors.append("pixels-must-be-positive")
    if args.steps < 1:
        errors.append("steps-must-be-positive")
    if args.hold_milliseconds <= 0:
        errors.append("hold-milliseconds-must-be-positive")
    if args.focus_delay_milliseconds < 0:
        errors.append("focus-delay-milliseconds-must-be-nonnegative")
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
    run_dir = output_root / f"static-owner-mouse-turn-probe-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    errors = validate_args(args)
    safety = base_safety()
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-mouse-turn-probe",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "operator": {
            "dryRun": bool(args.dry_run),
            "mouseApproved": bool(args.mouse_approved),
            "directions": list(args.directions),
            "pixels": [int(item) for item in args.pixels],
            "steps": int(args.steps),
            "holdMilliseconds": int(args.hold_milliseconds),
            "postInputWaitMilliseconds": int(args.post_input_wait_milliseconds),
            "requireForeground": bool(args.require_foreground),
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
    if not args.dry_run and not args.mouse_approved:
        summary["status"] = "blocked"
        summary["verdict"] = "mouse-approval-required"
        summary["blockers"].append("mouse-approved-flag-required")
        return summary

    try:
        attempt_index = 0
        stop = False
        for direction in args.directions:
            if stop:
                break
            for pixels in args.pixels:
                if stop:
                    break
                attempt_index += 1
                label_prefix = f"{attempt_index:03d}-{direction}-{int(pixels)}px"
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
                    "direction": direction,
                    "pixels": int(pixels),
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
                try:
                    target = target_from_summary(pre_full)
                except Exception as exc:  # noqa: BLE001
                    attempt["status"] = "blocked"
                    attempt["blockers"].append(f"exact-target-metadata-invalid:{type(exc).__name__}:{exc}")
                    summary["attempts"].append(attempt)
                    continue

                if args.dry_run:
                    attempt["status"] = "planned"
                    attempt["inputCommandPlan"] = {
                        "kind": "python-win32-mouse-look-sendinput",
                        "target": target,
                        "direction": direction,
                        "pixels": int(pixels),
                        "steps": int(args.steps),
                    }
                    summary["attempts"].append(attempt)
                    continue

                mouse = perform_mouse_turn(
                    label=f"{label_prefix}-mouse-input",
                    child_dir=child_dir,
                    target=target,
                    direction=str(direction),
                    pixels=int(pixels),
                    steps=int(args.steps),
                    hold_milliseconds=int(args.hold_milliseconds),
                    focus_delay_milliseconds=int(args.focus_delay_milliseconds),
                    require_foreground=bool(args.require_foreground),
                )
                summary["childCommands"].append(mouse)
                attempt["inputCommand"] = mouse
                attempt["inputSent"] = True
                attempt["movementSent"] = True
                safety["inputSent"] = True
                safety["movementSent"] = True
                attempt["blockers"].extend(mouse.get("blockers", []))
                attempt["warnings"].extend(mouse.get("warnings", []))
                attempt["errors"].extend(mouse.get("errors", []))
                if not mouse["ok"]:
                    attempt["status"] = "failed"
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
                    direction=str(direction),
                    pixels=int(pixels),
                    pre_summary=pre_full,
                    post_summary=post_full,
                    minimum_yaw_delta_degrees=float(args.minimum_yaw_delta_degrees),
                    max_planar_drift=float(args.max_planar_drift),
                )
                attempt["analysis"] = analysis
                attempt["status"] = analysis["status"]
                attempt["blockers"].extend(analysis["blockers"])
                attempt["warnings"].extend(analysis["warnings"])
                summary["warnings"].extend(analysis["warnings"])
                summary["attempts"].append(attempt)
                if analysis["status"] == "passed":
                    success = {
                        "attemptIndex": attempt_index,
                        "direction": direction,
                        "pixels": int(pixels),
                        "signedYawDeltaDegrees": analysis["signedYawDeltaDegrees"],
                        "absoluteYawDeltaDegrees": analysis["absoluteYawDeltaDegrees"],
                        "coordinateDelta": analysis["coordinateDelta"],
                        "warnings": analysis["warnings"],
                    }
                    summary["successfulAttempts"].append(success)
                    if args.stop_on_first_success:
                        stop = True

        if args.dry_run:
            summary["status"] = "passed"
            summary["verdict"] = "mouse-turn-probe-dry-run-built"
            summary["warnings"].append("dry-run-only-no-input-sent")
        elif summary["successfulAttempts"]:
            summary["status"] = "passed"
            summary["verdict"] = "mouse-look-yaw-delta-validated"
            summary["warnings"].append("candidate-facing-yaw-not-promoted")
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "no-mouse-turn-produced-yaw-delta"
            summary["blockers"].append("no-mouse-look-attempt-produced-yaw-delta")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "mouse-turn-probe-error"
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
        "# Static owner mouse turn probe",
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
                f"- `{item_map.get('direction')}` / `{item_map.get('pixels')}px`: "
                f"`{item_map.get('signedYawDeltaDegrees')}` deg"
            )
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Summary JSON: `{artifacts.get('summaryJson')}`",
            f"- Run directory: `{artifacts.get('runDirectory')}`",
        ]
    )
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
    parser = argparse.ArgumentParser(description="Probe exact-target mouse-look turns against static-owner yaw")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--directions", nargs="+", choices=DEFAULT_DIRECTIONS, default=list(DEFAULT_DIRECTIONS))
    parser.add_argument("--pixels", nargs="+", type=int, default=list(DEFAULT_PIXELS))
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--hold-milliseconds", type=int, default=250)
    parser.add_argument("--focus-delay-milliseconds", type=int, default=250)
    parser.add_argument("--post-input-wait-milliseconds", type=int, default=500)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.1)
    parser.add_argument("--minimum-yaw-delta-degrees", type=float, default=1.0)
    parser.add_argument("--max-planar-drift", type=float, default=2.0)
    parser.add_argument("--command-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mouse-approved", action="store_true")
    parser.add_argument("--allow-nonforeground", dest="require_foreground", action="store_false")
    parser.set_defaults(require_foreground=True)
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
