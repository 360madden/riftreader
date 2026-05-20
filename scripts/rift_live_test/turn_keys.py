from __future__ import annotations

import math
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .commands import JsonCommandResult, command_envelope, run_json_command
from .reports import write_json, write_text_atomic
from .target import verify_target


DEFAULT_TURN_KEYS = ["a", "d", "A", "D", "Left", "Right"]
DEFAULT_INPUT_MODES = ["foreground-sendinput", "post-message"]
DEFAULT_SHELLS = ["pwsh"]
VALID_INPUT_MODES = {"foreground-sendinput", "post-message"}
VALID_SCREENSHOT_BACKENDS = {"wgc", "native-rift"}


@dataclass(frozen=True)
class TurnKeyProfileConfig:
    repo_root: Path
    process_id: int
    target_window_handle: str
    process_name: str = "rift_x64"
    keys: tuple[str, ...] = tuple(DEFAULT_TURN_KEYS)
    input_modes: tuple[str, ...] = tuple(DEFAULT_INPUT_MODES)
    shells: tuple[str, ...] = tuple(DEFAULT_SHELLS)
    repeats: int = 1
    hold_milliseconds: int = 125
    post_input_wait_milliseconds: int = 250
    min_yaw_delta_degrees: float = 1.0
    max_coord_delta: float = 0.25
    proof_max_age_seconds: int = 60
    readback_sample_count: int = 3
    readback_interval_milliseconds: int = 100
    live: bool = False
    refresh_proof_first: bool = False
    refresh_proof_before_each_attempt: bool = False
    proof_refresh_retries: int = 0
    proof_profile: str = "ProofOnly"
    capture_screenshots: bool = False
    require_screenshots: bool = False
    screenshot_backend: str = "wgc"
    native_screenshot_key_chord: str = "numpad_multiply"
    stop_on_movement: bool = True
    allow_post_message_input: bool = False
    output_root: Path | None = None
    command_timeout_seconds: int = 120
    input_timeout_seconds: int = 30


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_degrees(degrees: float) -> float:
    normalized = math.fmod(float(degrees) + 180.0, 360.0)
    if normalized < 0:
        normalized += 360.0
    return normalized - 180.0


def get_nested(document: Any, *names: str) -> Any | None:
    current = document
    for name in names:
        if not isinstance(current, dict) or name not in current:
            return None
        current = current[name]
    return current


def number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_orientation_sample(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(document, dict):
        return None

    estimate = get_nested(document, "ReaderOrientation", "PreferredEstimate")
    reader_orientation = document.get("ReaderOrientation") if isinstance(document, dict) else None
    if not isinstance(estimate, dict) or not isinstance(reader_orientation, dict):
        return None

    return {
        "generatedAtUtc": document.get("GeneratedAtUtc"),
        "yawDegrees": number_or_none(estimate.get("YawDegrees")),
        "pitchDegrees": number_or_none(estimate.get("PitchDegrees")),
        "sourceAddress": reader_orientation.get("SelectedSourceAddress"),
        "basisForwardOffset": reader_orientation.get("BasisPrimaryForwardOffset")
        or reader_orientation.get("BasisForwardOffset"),
        "status": reader_orientation.get("Status"),
        "operationalStatus": reader_orientation.get("OperationalStatus"),
    }


def extract_readback_sample(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(document, dict):
        return None
    coord = document.get("CurrentCoordinate")
    if not isinstance(coord, dict):
        return None
    return {
        "generatedAtUtc": document.get("GeneratedAtUtc"),
        "status": document.get("Status"),
        "movementAllowed": bool(document.get("MovementAllowed")),
        "noCheatEngine": bool(document.get("NoCheatEngine")),
        "movementSent": bool(document.get("MovementSent")),
        "candidateId": document.get("ProofAnchorCandidateId"),
        "candidateAddressHex": document.get("ProofAnchorCandidateAddressHex"),
        "summaryFile": document.get("SummaryFile"),
        "x": number_or_none(coord.get("X")),
        "y": number_or_none(coord.get("Y")),
        "z": number_or_none(coord.get("Z")),
        "recordedAtUtc": coord.get("RecordedAtUtc"),
    }


def planar_coord_delta(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, float | None]:
    if not before or not after:
        return {
            "deltaX": None,
            "deltaY": None,
            "deltaZ": None,
            "planarDistance": None,
            "linearDistance": None,
        }
    bx = number_or_none(before.get("x"))
    by = number_or_none(before.get("y"))
    bz = number_or_none(before.get("z"))
    ax = number_or_none(after.get("x"))
    ay = number_or_none(after.get("y"))
    az = number_or_none(after.get("z"))
    if None in (bx, by, bz, ax, ay, az):
        return {
            "deltaX": None,
            "deltaY": None,
            "deltaZ": None,
            "planarDistance": None,
            "linearDistance": None,
        }
    dx = float(ax) - float(bx)
    dy = float(ay) - float(by)
    dz = float(az) - float(bz)
    return {
        "deltaX": dx,
        "deltaY": dy,
        "deltaZ": dz,
        "planarDistance": math.sqrt(dx * dx + dz * dz),
        "linearDistance": math.sqrt(dx * dx + dy * dy + dz * dz),
    }


def classify_turn_attempt(
    *,
    input_exit_code: int | None,
    yaw_delta_degrees: float | None,
    coord_delta: dict[str, float | None],
    min_yaw_delta_degrees: float,
    max_coord_delta: float,
) -> str:
    if input_exit_code is None:
        return "planned"
    if input_exit_code != 0:
        return "input-failed"
    planar = coord_delta.get("planarDistance")
    if planar is None:
        return "readback-missing"
    if float(planar) > float(max_coord_delta):
        return "movement-detected"
    if yaw_delta_degrees is None:
        return "yaw-missing"
    if abs(float(yaw_delta_degrees)) >= float(min_yaw_delta_degrees):
        return "turn-candidate"
    return "no-turn"


def _ps_file_command(shell: str, script_path: Path, args: list[str]) -> list[str]:
    return [
        shell,
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *args,
    ]


def _safe_name(value: str) -> str:
    safe = []
    for char in str(value):
        if char.isalnum() or char in ("-", "_"):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("_") or "value"


def _command_preview(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": envelope.get("label"),
        "exitCode": envelope.get("exitCode"),
        "jsonParseError": envelope.get("jsonParseError"),
    }


def _write_json_command_envelope(path: Path, result: JsonCommandResult) -> dict[str, Any]:
    envelope = command_envelope(result)
    write_json(path, envelope)
    preview = _command_preview(envelope)
    preview["outputFile"] = str(path)
    return preview


def _write_text_command_envelope(
    path: Path,
    *,
    label: str,
    args: list[str],
    exit_code: int,
    stdout: str,
    stderr: str,
    requested_input_mode: str | None = None,
) -> dict[str, Any]:
    delivery = summarize_input_delivery(
        stdout=stdout,
        stderr=stderr,
        requested_input_mode=requested_input_mode,
    )
    envelope = {
        "label": label,
        "args": args,
        "exitCode": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "inputDelivery": delivery,
    }
    write_json(path, envelope)
    return {
        "label": label,
        "exitCode": exit_code,
        "outputFile": str(path),
        "inputDelivery": delivery,
    }


def summarize_input_delivery(
    *,
    stdout: str,
    stderr: str = "",
    requested_input_mode: str | None = None,
) -> dict[str, Any]:
    text = "\n".join(part for part in (stdout or "", stderr or "") if part)
    sendinput_failed = (
        "Foreground SendInput path failed" in text
        or "SendInput sent 0 of 1 keyboard inputs" in text
    )
    ahk_fallback = "AutoHotkey fallback SUCCESS" in text
    success = "[RiftKey] SUCCESS" in text
    if ahk_fallback:
        effective_mode = "autohotkey-fallback"
    elif sendinput_failed:
        effective_mode = "sendinput-failed"
    elif success and requested_input_mode:
        effective_mode = requested_input_mode
    elif success:
        effective_mode = "helper-success"
    else:
        effective_mode = "unknown"

    return {
        "requestedInputMode": requested_input_mode,
        "successMarker": success,
        "sendInputFailed": sendinput_failed,
        "autoHotkeyFallbackUsed": ahk_fallback,
        "effectiveMode": effective_mode,
    }


class TurnKeyProfiler:
    def __init__(self, config: TurnKeyProfileConfig) -> None:
        self.config = config
        output_root = config.output_root or (config.repo_root / "scripts" / "captures")
        if not output_root.is_absolute():
            output_root = config.repo_root / output_root
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.run_dir = output_root / f"turn-key-profile-currentpid-{config.process_id}-{stamp}"
        self.child_dir = self.run_dir / "child-outputs"
        self.orientation_dir = self.run_dir / "orientation"
        self.readback_dir = self.run_dir / "readbacks"
        self.session_dir = self.run_dir / "sessions"
        self.screenshot_dir = self.run_dir / "screenshots"
        self.issues: list[str] = []
        self.attempts: list[dict[str, Any]] = []
        self.child_index = 0

    def run(self) -> dict[str, Any]:
        self._validate_config()
        self.child_dir.mkdir(parents=True, exist_ok=True)
        self.orientation_dir.mkdir(parents=True, exist_ok=True)
        self.readback_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        if self.config.capture_screenshots:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        target = verify_target(
            self.config.process_id,
            self.config.target_window_handle,
            self.config.process_name,
        )
        write_json(self.child_dir / "001-target-check.json", target)
        if not target.get("valid"):
            self.issues.extend(target.get("issues") or [target.get("status", "target_invalid")])
            return self._finish("blocked-target-mismatch", target=target)

        proof_refresh = None
        if self.config.live and self.config.refresh_proof_first:
            proof_refresh = self._run_proof_refresh_with_retries(
                label="proof-refresh-first",
                output_subdir="proof-refreshes",
            )
            if not proof_refresh.get("ok"):
                self.issues.append("proof_refresh_failed")
                return self._finish("blocked-proof-refresh", target=target, proof_refresh=proof_refresh)

        if not self.config.live:
            self.attempts = self._planned_attempts()
            return self._finish("plan-only", target=target, proof_refresh=proof_refresh)

        stop_after_attempt = False
        for shell in self.config.shells:
            for input_mode in self.config.input_modes:
                for key in self.config.keys:
                    for repeat_index in range(1, self.config.repeats + 1):
                        attempt = self._run_attempt(
                            key=key,
                            input_mode=input_mode,
                            shell=shell,
                            repeat_index=repeat_index,
                        )
                        self.attempts.append(attempt)
                        if (
                            self.config.stop_on_movement
                            and attempt.get("classification") == "movement-detected"
                        ):
                            self.issues.append(
                                "movement_detected_during_turn_key_profile; stopped remaining attempts"
                            )
                            stop_after_attempt = True
                            break
                    if stop_after_attempt:
                        break
                if stop_after_attempt:
                    break
            if stop_after_attempt:
                break

        if any(attempt.get("classification") == "movement-detected" for attempt in self.attempts):
            status = "blocked-unintended-movement"
        elif self.promoted_candidates():
            status = "completed-with-promoted-turn-candidate"
        else:
            status = "completed-no-promoted-turn-candidate"
        return self._finish(status, target=target, proof_refresh=proof_refresh)

    def _validate_config(self) -> None:
        if self.config.process_id <= 0:
            raise ValueError("process_id must be positive")
        if not self.config.target_window_handle:
            raise ValueError("target_window_handle is required")
        if self.config.repeats <= 0:
            raise ValueError("repeats must be positive")
        if self.config.hold_milliseconds <= 0:
            raise ValueError("hold_milliseconds must be positive")
        if self.config.post_input_wait_milliseconds < 0:
            raise ValueError("post_input_wait_milliseconds cannot be negative")
        if self.config.proof_max_age_seconds <= 0:
            raise ValueError("proof_max_age_seconds must be positive")
        if self.config.readback_sample_count <= 0:
            raise ValueError("readback_sample_count must be positive")
        if self.config.readback_interval_milliseconds < 0:
            raise ValueError("readback_interval_milliseconds cannot be negative")
        if self.config.min_yaw_delta_degrees < 0:
            raise ValueError("min_yaw_delta_degrees cannot be negative")
        if self.config.max_coord_delta < 0:
            raise ValueError("max_coord_delta cannot be negative")
        if self.config.proof_refresh_retries < 0:
            raise ValueError("proof_refresh_retries cannot be negative")
        invalid_modes = [mode for mode in self.config.input_modes if mode not in VALID_INPUT_MODES]
        if invalid_modes:
            raise ValueError(f"unsupported input modes: {', '.join(invalid_modes)}")
        if (
            self.config.live
            and "post-message" in self.config.input_modes
            and not self.config.allow_post_message_input
        ):
            raise ValueError(
                "post-message live input is blocked after the spin incident; "
                "rerun with --allow-post-message-input only after incident review"
            )
        if self.config.screenshot_backend not in VALID_SCREENSHOT_BACKENDS:
            raise ValueError(f"unsupported screenshot backend: {self.config.screenshot_backend}")

    def _planned_attempts(self) -> list[dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        for shell in self.config.shells:
            for input_mode in self.config.input_modes:
                for key in self.config.keys:
                    for repeat_index in range(1, self.config.repeats + 1):
                        attempt_index = len(attempts) + 1
                        attempt_id = (
                            f"{attempt_index:03d}-"
                            f"{_safe_name(shell)}-{_safe_name(input_mode)}-"
                            f"{_safe_name(key)}-r{repeat_index}"
                        )
                        attempts.append(
                            {
                                "attemptId": attempt_id,
                                "key": key,
                                "inputMode": input_mode,
                                "shell": shell,
                                "repeatIndex": repeat_index,
                                "status": "planned",
                                "classification": "planned",
                                "inputSent": False,
                                "plannedCommand": self._post_key_command(
                                    key=key,
                                    input_mode=input_mode,
                                    shell=shell,
                                ),
                            }
                        )
        return attempts

    def _run_attempt(
        self,
        *,
        key: str,
        input_mode: str,
        shell: str,
        repeat_index: int,
    ) -> dict[str, Any]:
        attempt_id = self._attempt_id(
            key=key,
            input_mode=input_mode,
            shell=shell,
            repeat_index=repeat_index,
        )
        attempt: dict[str, Any] = {
            "attemptId": attempt_id,
            "key": key,
            "inputMode": input_mode,
            "shell": shell,
            "repeatIndex": repeat_index,
            "holdMilliseconds": self.config.hold_milliseconds,
            "postInputWaitMilliseconds": self.config.post_input_wait_milliseconds,
            "inputSent": False,
        }

        if self.config.refresh_proof_before_each_attempt:
            attempt_proof = self._run_proof_refresh_with_retries(
                label=f"{attempt_id}-proof-refresh-before",
                output_subdir=f"proof-refreshes/{attempt_id}",
            )
            attempt["proofRefresh"] = attempt_proof
            if not attempt_proof.get("ok"):
                issue = "proof_refresh_before_attempt_failed"
                attempt["issues"] = [issue]
                self.issues.append(f"{attempt_id}:{issue}")
                attempt["status"] = "blocked-proof-refresh"
                attempt["classification"] = "proof-refresh-failed"
                return attempt

        before_orientation = self._capture_orientation(attempt_id, phase="before")
        attempt["beforeOrientationCommand"] = before_orientation["command"]
        attempt["beforeOrientation"] = before_orientation["sample"]
        if not before_orientation["ok"]:
            attempt["issues"] = self._json_issues(before_orientation.get("json"))
            self._record_attempt_issues(attempt)
            attempt["status"] = "blocked-before-orientation"
            attempt["classification"] = "before-orientation-failed"
            return attempt

        before_readback = self._capture_readback(attempt_id, phase="before")
        attempt["beforeReadbackCommand"] = before_readback["command"]
        attempt["beforeReadback"] = before_readback["sample"]
        if not self._readback_valid(before_readback):
            attempt["issues"] = self._json_issues(before_readback.get("json"))
            self._record_attempt_issues(attempt)
            attempt["status"] = "blocked-before-readback"
            attempt["classification"] = "before-readback-failed"
            return attempt

        before_screenshot = self._capture_screenshot(attempt_id, phase="before")
        if before_screenshot is not None:
            attempt["beforeScreenshot"] = before_screenshot
            if self.config.require_screenshots and before_screenshot.get("exitCode") != 0:
                attempt["status"] = "blocked-before-screenshot"
                attempt["classification"] = "before-screenshot-failed"
                return attempt

        input_result = self._send_key(
            key=key,
            input_mode=input_mode,
            shell=shell,
            attempt_id=attempt_id,
        )
        attempt["inputCommand"] = input_result
        attempt["inputSent"] = input_result.get("exitCode") == 0

        if self.config.post_input_wait_milliseconds > 0:
            time.sleep(self.config.post_input_wait_milliseconds / 1000.0)

        after_orientation = self._capture_orientation(attempt_id, phase="after")
        attempt["afterOrientationCommand"] = after_orientation["command"]
        attempt["afterOrientation"] = after_orientation["sample"]
        if not after_orientation["ok"]:
            attempt["issues"] = self._json_issues(after_orientation.get("json"))
            self._record_attempt_issues(attempt)

        after_readback = self._capture_readback(attempt_id, phase="after")
        attempt["afterReadbackCommand"] = after_readback["command"]
        attempt["afterReadback"] = after_readback["sample"]
        if not self._readback_valid(after_readback):
            attempt["issues"] = self._json_issues(after_readback.get("json"))
            self._record_attempt_issues(attempt)

        after_screenshot = self._capture_screenshot(attempt_id, phase="after")
        if after_screenshot is not None:
            attempt["afterScreenshot"] = after_screenshot

        before_yaw = number_or_none((attempt.get("beforeOrientation") or {}).get("yawDegrees"))
        after_yaw = number_or_none((attempt.get("afterOrientation") or {}).get("yawDegrees"))
        yaw_delta = None
        if before_yaw is not None and after_yaw is not None:
            yaw_delta = normalize_degrees(float(after_yaw) - float(before_yaw))
        coord_delta = planar_coord_delta(
            attempt.get("beforeReadback"),
            attempt.get("afterReadback"),
        )
        attempt["yawDeltaDegrees"] = yaw_delta
        attempt["absYawDeltaDegrees"] = None if yaw_delta is None else abs(yaw_delta)
        attempt["coordDelta"] = coord_delta
        attempt["classification"] = classify_turn_attempt(
            input_exit_code=input_result.get("exitCode"),
            yaw_delta_degrees=yaw_delta,
            coord_delta=coord_delta,
            min_yaw_delta_degrees=self.config.min_yaw_delta_degrees,
            max_coord_delta=self.config.max_coord_delta,
        )
        attempt["status"] = "completed" if input_result.get("exitCode") == 0 else "input-failed"
        return attempt

    def _attempt_id(self, *, key: str, input_mode: str, shell: str, repeat_index: int) -> str:
        return (
            f"{len(self.attempts) + 1:03d}-"
            f"{_safe_name(shell)}-{_safe_name(input_mode)}-"
            f"{_safe_name(key)}-r{repeat_index}"
        )

    def _next_child_file(self, label: str) -> Path:
        self.child_index += 1
        return self.child_dir / f"{self.child_index:03d}-{_safe_name(label)}.json"

    def _run_proof_refresh(self, *, label: str, output_subdir: str) -> dict[str, Any]:
        output_root = self.run_dir / output_subdir
        command = [
            sys.executable,
            str(self.config.repo_root / "scripts" / "live_test.py"),
            "--profile",
            self.config.proof_profile,
            "--pid",
            str(self.config.process_id),
            "--hwnd",
            self.config.target_window_handle,
            "--process-name",
            self.config.process_name,
            "--output-root",
            str(output_root),
            "--no-gui",
        ]
        result = run_json_command(
            command,
            cwd=self.config.repo_root,
            label=label,
            timeout_seconds=self.config.command_timeout_seconds * 3,
        )
        command_file = self._next_child_file(label)
        preview = _write_json_command_envelope(command_file, result)
        summary = {
            "ok": result.exit_code == 0 and bool((result.json_data or {}).get("ok", False)),
            "command": preview,
            "summary": result.json_data,
        }
        write_json(self.run_dir / f"{_safe_name(label)}.json", summary)
        return summary

    def _run_proof_refresh_with_retries(self, *, label: str, output_subdir: str) -> dict[str, Any]:
        max_attempts = 1 + self.config.proof_refresh_retries
        attempt_results: list[dict[str, Any]] = []
        latest: dict[str, Any] | None = None

        for index in range(1, max_attempts + 1):
            retry_label = label if max_attempts == 1 else f"{label}-try{index}"
            retry_output_subdir = output_subdir if max_attempts == 1 else f"{output_subdir}/try{index}"
            latest = self._run_proof_refresh(label=retry_label, output_subdir=retry_output_subdir)
            run_summary = latest.get("summary") if isinstance(latest, dict) else None
            run_status = run_summary.get("status") if isinstance(run_summary, dict) else None
            run_directory = run_summary.get("runDirectory") if isinstance(run_summary, dict) else None
            attempt_results.append(
                {
                    "try": index,
                    "ok": bool(latest.get("ok")) if isinstance(latest, dict) else False,
                    "status": run_status,
                    "runDirectory": run_directory,
                    "label": retry_label,
                }
            )
            if latest.get("ok"):
                break

        if latest is None:
            latest = {"ok": False, "summary": None}
        latest = dict(latest)
        latest["attemptCount"] = len(attempt_results)
        latest["maxAttemptCount"] = max_attempts
        latest["attemptResults"] = attempt_results
        return latest

    def _capture_orientation(self, attempt_id: str, *, phase: str) -> dict[str, Any]:
        script = self.config.repo_root / "scripts" / "capture-actor-orientation.ps1"
        output_file = self.orientation_dir / f"{attempt_id}-{phase}.json"
        previous_file = self.orientation_dir / f"{attempt_id}-{phase}.previous.json"
        args = [
            "-Json",
            "-ProcessName",
            self.config.process_name,
            "-ProcessId",
            str(self.config.process_id),
            "-TargetWindowHandle",
            self.config.target_window_handle,
            "-Label",
            f"turn-key-profile:{attempt_id}:{phase}",
            "-OutputFile",
            str(output_file),
            "-PreviousFile",
            str(previous_file),
        ]
        result = run_json_command(
            _ps_file_command("pwsh", script, args),
            cwd=self.config.repo_root,
            label=f"{attempt_id}-{phase}-orientation",
            timeout_seconds=self.config.command_timeout_seconds,
        )
        preview = _write_json_command_envelope(
            self._next_child_file(f"{attempt_id}-{phase}-orientation"),
            result,
        )
        return {
            "ok": result.ok,
            "command": preview,
            "sample": extract_orientation_sample(result.json_data),
            "json": result.json_data,
        }

    def _capture_readback(self, attempt_id: str, *, phase: str) -> dict[str, Any]:
        script = self.config.repo_root / "scripts" / "assert-current-proof-coord-anchor-readback.ps1"
        output_root = self.readback_dir / f"{attempt_id}-{phase}"
        session_root = self.session_dir / f"{attempt_id}-{phase}"
        args = [
            "-Json",
            "-ProcessName",
            self.config.process_name,
            "-ProcessId",
            str(self.config.process_id),
            "-TargetWindowHandle",
            self.config.target_window_handle,
            "-OutputRoot",
            str(output_root),
            "-ReaderSessionRoot",
            str(session_root),
            "-ProofAnchorMaxAgeSeconds",
            str(self.config.proof_max_age_seconds),
            "-ReadbackSampleCount",
            str(self.config.readback_sample_count),
            "-ReadbackIntervalMilliseconds",
            str(self.config.readback_interval_milliseconds),
        ]
        result = run_json_command(
            _ps_file_command("pwsh", script, args),
            cwd=self.config.repo_root,
            label=f"{attempt_id}-{phase}-readback",
            timeout_seconds=self.config.command_timeout_seconds,
        )
        preview = _write_json_command_envelope(
            self._next_child_file(f"{attempt_id}-{phase}-readback"),
            result,
        )
        return {
            "ok": result.ok,
            "command": preview,
            "sample": extract_readback_sample(result.json_data),
            "json": result.json_data,
        }

    def _capture_screenshot(self, attempt_id: str, *, phase: str) -> dict[str, Any] | None:
        if not self.config.capture_screenshots:
            return None
        if self.config.screenshot_backend == "native-rift":
            return self._capture_native_rift_screenshot(attempt_id, phase=phase)
        return self._capture_wgc_screenshot(attempt_id, phase=phase)

    def _capture_wgc_screenshot(self, attempt_id: str, *, phase: str) -> dict[str, Any]:
        script = self.config.repo_root / "scripts" / "capture-rift-window-wgc.ps1"
        output_path = self.screenshot_dir / f"{attempt_id}-{phase}.png"
        args = [
            "-Json",
            "-ProcessName",
            self.config.process_name,
            "-ProcessId",
            str(self.config.process_id),
            "-OutputPath",
            str(output_path),
            "-Attempts",
            "1",
        ]
        if self.config.require_screenshots:
            args.append("-RequireUsable")
        result = run_json_command(
            _ps_file_command("pwsh", script, args),
            cwd=self.config.repo_root,
            label=f"{attempt_id}-{phase}-screenshot",
            timeout_seconds=self.config.command_timeout_seconds,
        )
        preview = _write_json_command_envelope(
            self._next_child_file(f"{attempt_id}-{phase}-screenshot"),
            result,
        )
        preview["screenshotBackend"] = "wgc"
        preview["screenshotPath"] = str(output_path)
        if isinstance(result.json_data, dict):
            preview["usable"] = result.json_data.get("Usable") or result.json_data.get("usable")
        return preview

    def _capture_native_rift_screenshot(self, attempt_id: str, *, phase: str) -> dict[str, Any]:
        script = self.config.repo_root / "scripts" / "rift_native_screenshot.py"
        args = [
            sys.executable,
            str(script),
            "--pid",
            str(self.config.process_id),
            "--hwnd",
            self.config.target_window_handle,
            "--output-root",
            str(self.screenshot_dir),
            "--key-chord",
            self.config.native_screenshot_key_chord,
            "--json",
        ]
        result = run_json_command(
            args,
            cwd=self.config.repo_root,
            label=f"{attempt_id}-{phase}-native-screenshot",
            timeout_seconds=self.config.command_timeout_seconds,
        )
        preview = _write_json_command_envelope(
            self._next_child_file(f"{attempt_id}-{phase}-native-screenshot"),
            result,
        )
        preview["screenshotBackend"] = "native-rift"
        if isinstance(result.json_data, dict):
            preview["usable"] = bool(result.json_data.get("ok"))
            preview["screenshotPath"] = result.json_data.get("artifactPath") or result.json_data.get("screenshotPath")
            preview["nativeScreenshotStatus"] = result.json_data.get("status")
            preview["nativeScreenshotKeyChord"] = result.json_data.get("keyChord")
        return preview

    def _send_key(self, *, key: str, input_mode: str, shell: str, attempt_id: str) -> dict[str, Any]:
        command = self._post_key_command(key=key, input_mode=input_mode, shell=shell)
        label = f"{attempt_id}-input"
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.config.repo_root),
                capture_output=True,
                text=True,
                timeout=self.config.input_timeout_seconds,
                check=False,
            )
            return _write_text_command_envelope(
                self._next_child_file(label),
                label=label,
                args=command,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                requested_input_mode=input_mode,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
            stderr = "\n".join(
                part
                for part in (
                    stderr,
                    f"Command timed out after {self.config.input_timeout_seconds} seconds",
                )
                if part
            )
            return _write_text_command_envelope(
                self._next_child_file(label),
                label=label,
                args=command,
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                requested_input_mode=input_mode,
            )

    def _post_key_command(self, *, key: str, input_mode: str, shell: str) -> list[str]:
        script = self.config.repo_root / "scripts" / "post-rift-key.ps1"
        args = [
            "-Key",
            key,
            "-HoldMilliseconds",
            str(self.config.hold_milliseconds),
            "-TargetProcessName",
            self.config.process_name,
            "-TargetProcessId",
            str(self.config.process_id),
            "-TargetWindowHandle",
            self.config.target_window_handle,
            "-SkipBackgroundFocus",
        ]
        if input_mode == "foreground-sendinput":
            args.append("-RequireTargetForeground")
        return _ps_file_command(shell, script, args)

    def _readback_valid(self, readback: dict[str, Any]) -> bool:
        sample = readback.get("sample")
        if not readback.get("ok") or not isinstance(sample, dict):
            return False
        return (
            str(sample.get("status")).lower() == "valid"
            and bool(sample.get("movementAllowed"))
            and bool(sample.get("noCheatEngine"))
            and not bool(sample.get("movementSent"))
        )

    def _json_issues(self, document: Any) -> list[str]:
        if not isinstance(document, dict):
            return []
        issues = document.get("Issues") or document.get("issues") or []
        if isinstance(issues, list):
            return [str(issue) for issue in issues]
        if issues:
            return [str(issues)]
        return []

    def _record_attempt_issues(self, attempt: dict[str, Any]) -> None:
        attempt_id = str(attempt.get("attemptId") or "attempt")
        for issue in attempt.get("issues") or []:
            text = f"{attempt_id}:{issue}"
            if text not in self.issues:
                self.issues.append(text)

    def promoted_candidates(self) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for attempt in self.attempts:
            if attempt.get("classification") != "turn-candidate":
                continue
            key = (str(attempt.get("key")), str(attempt.get("inputMode")), str(attempt.get("shell")))
            groups.setdefault(key, []).append(attempt)

        promoted: list[dict[str, Any]] = []
        required = max(2, self.config.repeats)
        for (key, input_mode, shell), attempts in sorted(groups.items()):
            usable = [a for a in attempts if number_or_none(a.get("yawDeltaDegrees")) is not None]
            signs = {
                1 if float(a["yawDeltaDegrees"]) > 0 else -1
                for a in usable
                if abs(float(a["yawDeltaDegrees"])) >= self.config.min_yaw_delta_degrees
            }
            if len(usable) >= required and len(signs) == 1:
                promoted.append(
                    {
                        "key": key,
                        "inputMode": input_mode,
                        "shell": shell,
                        "attemptCount": len(usable),
                        "requiredAttemptCount": required,
                        "consistentSign": next(iter(signs)),
                        "yawDeltaDegrees": [a.get("yawDeltaDegrees") for a in usable],
                        "coordPlanarDeltas": [
                            (a.get("coordDelta") or {}).get("planarDistance") for a in usable
                        ],
                        "attemptIds": [a.get("attemptId") for a in usable],
                    }
                )
        return promoted

    def _finish(
        self,
        status: str,
        *,
        target: dict[str, Any] | None = None,
        proof_refresh: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        promoted = self.promoted_candidates()
        input_sent = any(bool(attempt.get("inputSent")) for attempt in self.attempts)
        movement_detected = any(
            attempt.get("classification") == "movement-detected" for attempt in self.attempts
        )
        summary_path = self.run_dir / "turn-key-profile-summary.json"
        markdown_path = self.run_dir / "turn-key-profile-summary.md"
        summary: dict[str, Any] = {
            "schemaVersion": 1,
            "mode": "turn-key-profile",
            "generatedAtUtc": utc_now_text(),
            "status": status,
            "ok": status in {"plan-only", "completed-with-promoted-turn-candidate"},
            "runDirectory": str(self.run_dir),
            "summaryFile": str(summary_path),
            "markdownSummaryFile": str(markdown_path),
            "processName": self.config.process_name,
            "processId": self.config.process_id,
            "targetWindowHandle": self.config.target_window_handle,
            "live": self.config.live,
            "inputSent": input_sent,
            "movementDetected": movement_detected,
            "noCheatEngine": True,
            "savedVariablesUsedAsLiveTruth": False,
            "keys": list(self.config.keys),
            "inputModes": list(self.config.input_modes),
            "allowPostMessageInput": self.config.allow_post_message_input,
            "shells": list(self.config.shells),
            "captureScreenshots": self.config.capture_screenshots,
            "requireScreenshots": self.config.require_screenshots,
            "screenshotBackend": self.config.screenshot_backend,
            "nativeScreenshotKeyChord": self.config.native_screenshot_key_chord,
            "repeats": self.config.repeats,
            "holdMilliseconds": self.config.hold_milliseconds,
            "postInputWaitMilliseconds": self.config.post_input_wait_milliseconds,
            "minYawDeltaDegrees": self.config.min_yaw_delta_degrees,
            "maxCoordDelta": self.config.max_coord_delta,
            "proofMaxAgeSeconds": self.config.proof_max_age_seconds,
            "refreshProofBeforeEachAttempt": self.config.refresh_proof_before_each_attempt,
            "proofRefreshRetries": self.config.proof_refresh_retries,
            "readbackSampleCount": self.config.readback_sample_count,
            "readbackIntervalMilliseconds": self.config.readback_interval_milliseconds,
            "target": target,
            "proofRefresh": proof_refresh,
            "attempts": self.attempts,
            "promotedCandidates": promoted,
            "issues": self.issues,
        }
        write_json(summary_path, summary)
        write_text_atomic(markdown_path, format_turn_key_markdown(summary))
        return summary


def format_turn_key_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Turn key profile summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- OK: `{str(summary.get('ok')).lower()}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Run directory: `{summary.get('runDirectory')}`",
        f"- Target: `{summary.get('processName')}` PID `{summary.get('processId')}`, HWND `{summary.get('targetWindowHandle')}`",
        f"- Live: `{str(summary.get('live')).lower()}`",
        f"- Input sent: `{str(summary.get('inputSent')).lower()}`",
        f"- Movement detected: `{str(summary.get('movementDetected')).lower()}`",
        f"- No Cheat Engine: `{str(summary.get('noCheatEngine')).lower()}`",
        f"- SavedVariables live truth: `{str(summary.get('savedVariablesUsedAsLiveTruth')).lower()}`",
        f"- Proof refresh retries: `{summary.get('proofRefreshRetries')}`",
        f"- Screenshots: `{summary.get('screenshotBackend')}` capture=`{str(summary.get('captureScreenshots')).lower()}` require=`{str(summary.get('requireScreenshots')).lower()}`",
        "",
        "## Promoted candidates",
        "",
    ]
    promoted = summary.get("promotedCandidates") or []
    if promoted:
        lines.extend(["| Key | Mode | Shell | Attempts | Yaw deltas | Planar coord deltas |", "|---|---|---|---:|---|---|"])
        for candidate in promoted:
            lines.append(
                f"| `{candidate.get('key')}` | `{candidate.get('inputMode')}` | "
                f"`{candidate.get('shell')}` | `{candidate.get('attemptCount')}` | "
                f"`{candidate.get('yawDeltaDegrees')}` | `{candidate.get('coordPlanarDeltas')}` |"
            )
    else:
        lines.append("No turn key/backend combo was promoted. A combo needs at least two same-sign turn-candidate attempts.")

    lines.extend(
        [
            "",
            "## Attempts",
            "",
            "| Attempt | Key | Mode | Delivery | Shell | Classification | Yaw delta | Planar coord delta | Input exit |",
            "|---|---|---|---|---|---|---:|---:|---:|",
        ]
    )
    for attempt in summary.get("attempts") or []:
        coord_delta = attempt.get("coordDelta") or {}
        input_command = attempt.get("inputCommand") or {}
        input_delivery = input_command.get("inputDelivery") or {}
        lines.append(
            f"| `{attempt.get('attemptId')}` | `{attempt.get('key')}` | "
            f"`{attempt.get('inputMode')}` | `{input_delivery.get('effectiveMode')}` | "
            f"`{attempt.get('shell')}` | "
            f"`{attempt.get('classification')}` | `{attempt.get('yawDeltaDegrees')}` | "
            f"`{coord_delta.get('planarDistance')}` | `{input_command.get('exitCode')}` |"
        )

    if summary.get("issues"):
        lines.extend(["", "## Issues"])
        for issue in summary.get("issues") or []:
            lines.append(f"- `{issue}`")

    return "\n".join(lines).rstrip() + "\n"
