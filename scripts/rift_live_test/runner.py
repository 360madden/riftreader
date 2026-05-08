from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .baselines import (
    collect_candidate_paths,
    record_baseline_summary,
    select_baselines_for_fresh_summary,
)
from .commands import (
    command_envelope,
    ps_quote,
    pwsh_encoded_command,
    pwsh_file_command,
    run_json_command,
)
from .gui import start_progress_gui
from .reports import write_json, write_markdown_summary
from .recorder import record_pulse_coordinates
from .status import (
    BLOCKED_DRY_RUN,
    BLOCKED_LIVE_FLAG_REQUIRED,
    BLOCKED_LOW_AGE_BUDGET,
    BLOCKED_PROMOTION_REFERENCE_MISMATCH,
    BLOCKED_PROOF_EXPIRED,
    BLOCKED_REFERENCE_CAPTURE,
    BLOCKED_TARGET_MISMATCH,
    FAILED_INTERNAL_ERROR,
    INPUT_FAILED,
    PASSED,
    PASSED_BASELINE_CAPTURED,
    PASSED_PROOF_ONLY,
    PARTIAL_SERIES_STOPPED,
    POST_READBACK_FAILED,
    SUCCESS_STATUSES,
)
from .target import verify_target


class PromotionBaselineError(RuntimeError):
    def __init__(
        self,
        issues: list[str],
        diagnostics: dict[str, Any] | None = None,
        final_json: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("promotion baseline selection failed")
        self.issues = issues
        self.diagnostics = diagnostics or {}
        self.final_json = final_json or {}


class ReferenceCaptureError(RuntimeError):
    def __init__(self, issues: list[str]) -> None:
        super().__init__("reference capture failed")
        self.issues = issues


def classify_run_health(status: str) -> str:
    text = str(status or "").lower()
    if text in SUCCESS_STATUSES or text.startswith("passed"):
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


class LiveTestRunner:
    def __init__(
        self,
        *,
        repo_root: Path,
        profile_name: str,
        profile: dict[str, Any],
        process_id: int,
        target_window_handle: str,
        live: bool,
    ) -> None:
        self.repo_root = repo_root
        self.profile_name = profile_name
        self.profile = profile
        self.process_id = process_id
        self.target_window_handle = target_window_handle
        self.live = live
        self.states: list[dict[str, Any]] = []
        self.issues: list[str] = []
        self.child_index = 0
        self.auto_refresh_attempts_used = 0
        self.proof_refresh_sequence = 0
        self.series_pulses: list[dict[str, Any]] = []
        self.coordinate_recordings: list[dict[str, Any]] = []
        self.gui_info: dict[str, Any] | None = None
        self.latest_child_command: dict[str, Any] | None = None

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output_root = Path(str(profile.get("outputRoot", repo_root / "scripts" / "captures")))
        if not output_root.is_absolute():
            output_root = repo_root / output_root
        self.run_dir = output_root / f"live-test-{profile_name}-{stamp}"
        self.child_dir = self.run_dir / "child-outputs"
        self.progress_file = self.run_dir / "run-progress.json"
        self.latest_pointer_file = self.repo_root / "scripts" / "captures" / "latest-live-test-run.json"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.child_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> dict[str, Any]:
        status = FAILED_INTERNAL_ERROR
        try:
            write_json(self.run_dir / "profile-effective.json", self.profile)
            self.gui_info = self._start_gui()
            write_json(self.run_dir / "run-manifest.json", self._manifest())
            self._write_progress("running")
            self._state("load-profile", "passed", detail=str(self.profile.get("profilesFile")))

            target = verify_target(
                self.process_id,
                self.target_window_handle,
                str(self.profile.get("processName", "rift_x64")),
            )
            write_json(self.child_dir / "001-target-check.json", target)
            if not target.get("valid"):
                self.issues.extend(target.get("issues") or [target.get("status", "target_invalid")])
                status = BLOCKED_TARGET_MISMATCH
                self._state("verify-target", status, detail=";".join(self.issues))
                return self._finish(status)
            self._state(
                "verify-target",
                "passed",
                detail=f"pid={self.process_id};hwnd={target.get('targetWindowHandle')}",
            )

            mode = str(self.profile.get("mode"))
            has_input = isinstance(self.profile.get("input"), dict)
            if has_input and not self.live:
                self.issues.append("live_flag_required_for_input_profile")
                self._state("live-flag", BLOCKED_LIVE_FLAG_REQUIRED, detail="--live was not supplied")
                return self._finish(BLOCKED_LIVE_FLAG_REQUIRED)

            self._state(
                "promotion-baselines",
                "loaded",
                detail=str(self._promotion_baseline_pool_file()),
            )

            if mode == "baseline-only":
                captured = self._capture_proof_pose_next()
                self._state(
                    "baseline-capture",
                    "passed",
                    detail=str(captured.get("poseReadbackSummaryFile")),
                )
                final = {
                    "Status": "baseline-captured",
                    "MovementSent": False,
                    "MovementAttempted": False,
                    "SummaryFile": captured.get("poseReadbackSummaryFile"),
                    "CurrentCoordinate": captured.get("currentCoordinate"),
                }
                return self._finish(PASSED_BASELINE_CAPTURED, final_json=final)

            refresh = self._refresh_proof_next()
            self._state("proof-refresh", "passed", detail=str(refresh.get("poseReadbackSummaryFile")))

            if mode in {"proof-only", "recover-proof"}:
                readback = self._assert_current_readback(label="proof-only-readback")
                if self._readback_valid(readback):
                    self._state(
                        "post-readback",
                        "passed",
                        summaryFile=self._get(readback, "SummaryFile"),
                    )
                    return self._finish(PASSED_PROOF_ONLY, final_json=readback)
                self.issues.extend(self._json_issues(readback) or ["proof_only_readback_not_valid"])
                self._state("post-readback", POST_READBACK_FAILED, detail=";".join(self.issues))
                return self._finish(POST_READBACK_FAILED, final_json=readback)

            if mode == "live-input-series":
                return self._run_live_input_series()

            dry = self._run_gated_wrapper(dry_run=True, label="dry-run-gate")
            if self._get(dry, "Status") != "dry-run-valid":
                if self._can_refresh_for(dry):
                    self._state(
                        "dry-run-gate",
                        "refreshing",
                        detail="dry-run requested one proof refresh",
                    )
                    self._refresh_proof_next()
                    dry = self._run_gated_wrapper(dry_run=True, label="dry-run-gate-retry")
                if self._get(dry, "Status") != "dry-run-valid":
                    self.issues.extend(
                        self._json_issues(dry) or [f"dry_run_status:{self._get(dry, 'Status')}"]
                    )
                    blocked = self._map_blocked_status(dry, default=BLOCKED_DRY_RUN)
                    self._state("dry-run-gate", blocked, summaryFile=self._get(dry, "SummaryFile"))
                    return self._finish(blocked, final_json=dry)
            self._state("dry-run-gate", "passed", summaryFile=self._get(dry, "SummaryFile"))

            live_result = self._run_gated_wrapper(dry_run=False, label="live-input")
            if (
                self._get(live_result, "Status") != "passed"
                and self._safe_to_retry_live_input(live_result)
                and self._can_refresh_for(live_result)
            ):
                self._state(
                    "live-input",
                    "refreshing",
                    detail="live wrapper requested one proof refresh",
                )
                self._refresh_proof_next()
                dry_retry = self._run_gated_wrapper(dry_run=True, label="dry-run-before-live-retry")
                if self._get(dry_retry, "Status") == "dry-run-valid":
                    live_result = self._run_gated_wrapper(dry_run=False, label="live-input-retry")
                else:
                    live_result = dry_retry

            live_status = self._get(live_result, "Status")
            if live_status == "passed":
                self._record_coordinate_pulse(
                    pulse_index=1,
                    stage="live-input",
                    dry_run=dry,
                    live_result=live_result,
                )
                self._state("live-input", "passed", summaryFile=self._get(live_result, "SummaryFile"))
                return self._finish(PASSED, final_json=live_result)

            self._record_coordinate_pulse(
                pulse_index=1,
                stage="live-input",
                dry_run=dry,
                live_result=live_result,
            )
            self.issues.extend(self._json_issues(live_result) or [f"live_status:{live_status}"])
            mapped = self._map_blocked_status(live_result, default=INPUT_FAILED)
            if mode == "live-input-series" and self._movement_started(live_result):
                mapped = PARTIAL_SERIES_STOPPED
            self._state("live-input", mapped, summaryFile=self._get(live_result, "SummaryFile"))
            return self._finish(mapped, final_json=live_result)
        except PromotionBaselineError as exc:
            self.issues.extend(exc.issues)
            write_json(self.run_dir / "promotion-baseline-selection.json", exc.diagnostics)
            self._state(
                "promote-proof",
                BLOCKED_PROMOTION_REFERENCE_MISMATCH,
                detail=";".join(exc.issues),
                summaryFile=self._get(exc.final_json, "SummaryFile"),
            )
            return self._finish(BLOCKED_PROMOTION_REFERENCE_MISMATCH, final_json=exc.final_json)
        except ReferenceCaptureError as exc:
            self.issues.extend(exc.issues)
            self._state(
                "capture-reference",
                BLOCKED_REFERENCE_CAPTURE,
                detail=";".join(exc.issues),
            )
            return self._finish(BLOCKED_REFERENCE_CAPTURE)
        except Exception as exc:  # noqa: BLE001 - final summary must capture unexpected failures.
            self.issues.append(f"internal_error:{type(exc).__name__}:{exc}")
            self._state("internal-error", FAILED_INTERNAL_ERROR, detail=str(exc))
            return self._finish(status)

    def _refresh_proof_next(self) -> dict[str, Any]:
        self.proof_refresh_sequence += 1
        return self._refresh_proof(attempt=self.proof_refresh_sequence)

    def _capture_proof_pose_next(self) -> dict[str, Any]:
        self.proof_refresh_sequence += 1
        return self._capture_proof_pose(attempt=self.proof_refresh_sequence)

    def _refresh_proof(self, *, attempt: int) -> dict[str, Any]:
        captured = self._capture_proof_pose(attempt=attempt)
        fresh_summary = captured.get("poseReadbackSummaryFile")
        if not fresh_summary:
            raise RuntimeError("proof pose did not return ReadbackSummaryFile")

        selected, diagnostics = self._select_promotion_readback_files(Path(str(fresh_summary)))
        write_json(self.run_dir / f"promotion-baseline-selection-attempt-{attempt}.json", diagnostics)
        if len(selected) < 2:
            diagnostics.setdefault("freshCurrentCoordinate", captured.get("currentCoordinate"))
            raise PromotionBaselineError(
                [
                    "promotion_baseline_unavailable:"
                    f"compatibleDisplacedCount={diagnostics.get('compatibleDisplacedCount', 0)}"
                ],
                diagnostics,
                {
                    "Status": BLOCKED_PROMOTION_REFERENCE_MISMATCH,
                    "MovementSent": False,
                    "MovementAttempted": False,
                    "SummaryFile": fresh_summary,
                    "CurrentCoordinate": captured.get("currentCoordinate"),
                    "PromotionBaselineSelection": diagnostics,
                },
            )

        promote = self._run_promote(selected)
        if promote.exit_code != 0 or self._get(promote.json_data, "ProofValidationStatus") != "validated":
            raise RuntimeError(
                "proof promotion failed:"
                f" exit={promote.exit_code};"
                f"status={self._get(promote.json_data, 'ProofValidationStatus')}"
            )
        captured["proofAnchorGeneratedAtUtc"] = self._get(promote.json_data, "GeneratedAtUtc")
        captured["promotionReadbackSummaryFiles"] = selected
        captured["promotionBaselineSelection"] = diagnostics
        return captured

    def _capture_proof_pose(self, *, attempt: int) -> dict[str, Any]:
        reference_file = self.run_dir / f"reference-attempt-{attempt}.json"
        reference = self._run_ps1(
            "capture-reference",
            "capture-rift-api-reference-coordinate.ps1",
            [
                "-ProcessName",
                self._process_name(),
                "-ProcessId",
                str(self.process_id),
                "-TargetWindowHandle",
                self.target_window_handle,
                "-OutputRoot",
                str(self.run_dir),
                "-OutputFile",
                str(reference_file),
                "-ScanContextBytes",
                str(int(self.profile.get("scanContextBytes", 4096))),
                "-MaxHits",
                str(int(self.profile.get("maxHits", 512))),
                "-Json",
            ],
        )
        if reference.exit_code != 0 or self._get(reference.json_data, "Status") != "captured":
            raise ReferenceCaptureError(self._reference_capture_issues(reference))

        pose_args = [
            "-ProcessName",
            self._process_name(),
            "-ProcessId",
            str(self.process_id),
            "-TargetWindowHandle",
            self.target_window_handle,
            "-OutputRoot",
            str(self.run_dir),
            "-PoseLabel",
            f"{self.profile_name}-attempt-{attempt}",
            "-ReferenceFile",
            str(reference_file),
            "-ReferenceMaxAgeSeconds",
            str(int(self.profile.get("referenceMaxAgeSeconds", 180))),
            "-ReferenceTolerance",
            str(float(self.profile.get("referenceTolerance", 0.25))),
            "-ReadbackSampleCount",
            str(int(self.profile.get("readbackSampleCount", 3))),
            "-ReadbackIntervalMilliseconds",
            str(int(self.profile.get("readbackIntervalMilliseconds", 100))),
            "-Json",
        ]
        candidate_file = self.profile.get("candidateFile")
        if candidate_file:
            pose_args[0:0] = ["-CandidateFile", str(candidate_file)]
        pose = self._run_ps1("capture-proof-pose", "capture-riftscan-proof-pose.ps1", pose_args)
        if pose.exit_code != 0 or self._get(pose.json_data, "Status") != "captured":
            raise RuntimeError(
                "proof pose failed:"
                f" exit={pose.exit_code};status={self._get(pose.json_data, 'Status')}"
            )

        fresh_summary = self._get(pose.json_data, "ReadbackSummaryFile")
        if not fresh_summary:
            raise RuntimeError("proof pose did not return ReadbackSummaryFile")
        baseline_entry = record_baseline_summary(
            pool_file=self._promotion_baseline_pool_file(),
            summary_file=Path(str(fresh_summary)),
            source=f"{self.profile_name}-attempt-{attempt}",
        )
        return {
            "referenceFile": str(reference_file),
            "poseReadbackSummaryFile": fresh_summary,
            "baselinePoolFile": str(self._promotion_baseline_pool_file()),
            "baselineEntry": baseline_entry,
            "currentCoordinate": self._summary_coordinate(Path(str(fresh_summary))),
        }

    def _run_promote(self, readback_summary_files: list[str]):
        script_path = self.repo_root / "scripts" / "promote-riftscan-reference-match-to-proof-anchor.ps1"
        array_literal = "@(" + ",".join(ps_quote(path) for path in readback_summary_files) + ")"
        output_file = self._proof_anchor_file()
        script = " ".join(
            [
                "&",
                ps_quote(script_path),
                "-ReadbackSummaryFile",
                array_literal,
                "-CandidateId",
                ps_quote(str(self.profile.get("candidateId", "rift-addon-coordinate-candidate-000001"))),
                "-ProcessName",
                ps_quote(self._process_name()),
                "-ProcessId",
                str(self.process_id),
                "-TargetWindowHandle",
                ps_quote(self.target_window_handle),
                "-OutputFile",
                ps_quote(output_file),
                "-MinReferenceDisplacement",
                str(float(self.profile.get("minReferenceDisplacement", 1.0))),
                "-MaxDeltaError",
                str(float(self.profile.get("maxDeltaError", 0.25))),
                "-MaxEvidenceAgeSeconds",
                str(int(self.profile.get("maxEvidenceAgeSeconds", 0))),
                "-Json",
            ]
        )
        return self._run_command("promote-proof", pwsh_encoded_command(script))

    def _assert_current_readback(self, *, label: str) -> dict[str, Any] | None:
        result = self._run_ps1(
            label,
            "assert-current-proof-coord-anchor-readback.ps1",
            [
                "-ProcessName",
                self._process_name(),
                "-ProcessId",
                str(self.process_id),
                "-TargetWindowHandle",
                self.target_window_handle,
                "-ProofCoordAnchorFile",
                self._proof_anchor_file(),
                "-ProofAnchorMaxAgeSeconds",
                str(int(self.profile.get("proofAnchorMaxAgeSeconds", 60))),
                "-ReadbackSampleCount",
                str(int(self.profile.get("readbackSampleCount", 3))),
                "-ReadbackIntervalMilliseconds",
                str(int(self.profile.get("readbackIntervalMilliseconds", 100))),
                "-Json",
            ],
        )
        return result.json_data

    def _run_live_input_series(self) -> dict[str, Any]:
        input_cfg = self.profile.get("input") or {}
        requested_pulses = int(input_cfg.get("pulseCount", 1))
        last_result: dict[str, Any] | None = None

        for pulse_index in range(1, requested_pulses + 1):
            dry_label = f"series-pulse-{pulse_index}-dry-run"
            dry = self._run_gated_wrapper(
                dry_run=True,
                label=dry_label,
                pulse_count=1,
            )

            if self._get(dry, "Status") != "dry-run-valid":
                if self._can_refresh_for(dry):
                    self._state(
                        dry_label,
                        "refreshing",
                        detail=f"series pulse {pulse_index} requested proof refresh",
                    )
                    self._refresh_proof_next()
                    dry_label = f"series-pulse-{pulse_index}-dry-run-retry"
                    dry = self._run_gated_wrapper(
                        dry_run=True,
                        label=dry_label,
                        pulse_count=1,
                    )
                if self._get(dry, "Status") != "dry-run-valid":
                    self.issues.extend(
                        self._json_issues(dry) or [f"dry_run_status:{self._get(dry, 'Status')}"]
                    )
                    blocked = self._map_blocked_status(dry, default=BLOCKED_DRY_RUN)
                    self._append_series_pulse(
                        pulse_index=pulse_index,
                        status=blocked,
                        stage="dry-run",
                        dry_run=dry,
                        live_result=None,
                    )
                    self._state(
                        dry_label,
                        blocked,
                        summaryFile=self._get(dry, "SummaryFile"),
                    )
                    final_status = (
                        PARTIAL_SERIES_STOPPED
                        if self._series_movement_started()
                        else blocked
                    )
                    return self._finish(final_status, final_json=dry)

            self._state(
                dry_label,
                "passed",
                summaryFile=self._get(dry, "SummaryFile"),
            )

            live_label = f"series-pulse-{pulse_index}-live-input"
            live_result = self._run_gated_wrapper(
                dry_run=False,
                label=live_label,
                pulse_count=1,
            )
            if (
                self._get(live_result, "Status") != "passed"
                and self._safe_to_retry_live_input(live_result)
                and self._can_refresh_for(live_result)
            ):
                self._state(
                    live_label,
                    "refreshing",
                    detail=f"series pulse {pulse_index} requested proof refresh before retry",
                )
                self._refresh_proof_next()
                retry_dry_label = f"series-pulse-{pulse_index}-dry-run-before-live-retry"
                dry_retry = self._run_gated_wrapper(
                    dry_run=True,
                    label=retry_dry_label,
                    pulse_count=1,
                )
                if self._get(dry_retry, "Status") == "dry-run-valid":
                    self._state(
                        retry_dry_label,
                        "passed",
                        summaryFile=self._get(dry_retry, "SummaryFile"),
                    )
                    dry = dry_retry
                    live_label = f"series-pulse-{pulse_index}-live-input-retry"
                    live_result = self._run_gated_wrapper(
                        dry_run=False,
                        label=live_label,
                        pulse_count=1,
                    )
                else:
                    live_result = dry_retry

            live_status = self._get(live_result, "Status")
            if live_status == "passed":
                self._append_series_pulse(
                    pulse_index=pulse_index,
                    status="passed",
                    stage="live-input",
                    dry_run=dry,
                    live_result=live_result,
                )
                self._state(
                    live_label,
                    "passed",
                    summaryFile=self._get(live_result, "SummaryFile"),
                )
                last_result = live_result
                continue

            self.issues.extend(
                self._json_issues(live_result) or [f"live_status:{live_status}"]
            )
            mapped = self._map_blocked_status(live_result, default=INPUT_FAILED)
            if self._movement_started(live_result) or self._series_movement_started():
                mapped = PARTIAL_SERIES_STOPPED
            self._append_series_pulse(
                pulse_index=pulse_index,
                status=mapped,
                stage="live-input",
                dry_run=dry,
                live_result=live_result,
            )
            self._state(
                live_label,
                mapped,
                summaryFile=self._get(live_result, "SummaryFile"),
            )
            return self._finish(mapped, final_json=live_result)

        return self._finish(PASSED, final_json=last_result)

    def _run_gated_wrapper(
        self,
        *,
        dry_run: bool,
        label: str,
        pulse_count: int | None = None,
    ) -> dict[str, Any] | None:
        input_cfg = self.profile.get("input") or {}
        args = [
            "-ProcessName",
            self._process_name(),
            "-ProcessId",
            str(self.process_id),
            "-TargetWindowHandle",
            self.target_window_handle,
            "-Key",
            str(input_cfg.get("key", "w")),
            "-HoldMilliseconds",
            str(int(input_cfg.get("holdMilliseconds", 250))),
            "-PulseCount",
            str(int(pulse_count if pulse_count is not None else input_cfg.get("pulseCount", 1))),
            "-InterPulseDelayMilliseconds",
            str(int(input_cfg.get("interPulseDelayMilliseconds", 150))),
            "-ProofAnchorMaxAgeSeconds",
            str(int(self.profile.get("proofAnchorMaxAgeSeconds", 60))),
            "-MinimumPostReadbackAgeBudgetSeconds",
            str(int(self.profile.get("minimumPostReadbackAgeBudgetSeconds", 20))),
            "-ReadbackSampleCount",
            str(int(self.profile.get("readbackSampleCount", 3))),
            "-ReadbackIntervalMilliseconds",
            str(int(self.profile.get("readbackIntervalMilliseconds", 100))),
            "-ProofCoordAnchorFile",
            self._proof_anchor_file(),
            "-OutputRoot",
            str(self.run_dir),
            "-Json",
        ]
        if dry_run:
            args.append("-DryRun")
        result = self._run_ps1(label, "invoke-gated-forward-smoke.ps1", args)
        return result.json_data

    def _run_ps1(self, label: str, script_name: str, args: list[str]):
        script_path = self.repo_root / "scripts" / script_name
        return self._run_command(label, pwsh_file_command(script_path, args))

    def _run_command(self, label: str, args: list[str]):
        safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label).strip("-")
        child_number = self.child_index + 1
        output_file = self.child_dir / f"{child_number:03d}-{safe_label}.json"
        started_monotonic = time.monotonic()
        self.latest_child_command = {
            "label": label,
            "status": "running",
            "startedAtUtc": datetime.now(timezone.utc).isoformat(),
            "outputFile": str(output_file),
        }
        self._write_progress("running")
        try:
            result = run_json_command(
                args,
                cwd=self.repo_root,
                label=label,
                timeout_seconds=int(self.profile.get("childCommandTimeoutSeconds", 180)),
            )
        except Exception as exc:  # noqa: BLE001 - preserve latest command context before bubbling up.
            self.latest_child_command = {
                **self.latest_child_command,
                "status": "failed",
                "completedAtUtc": datetime.now(timezone.utc).isoformat(),
                "durationSeconds": round(time.monotonic() - started_monotonic, 3),
                "error": f"{type(exc).__name__}:{exc}",
            }
            self._write_progress("running")
            raise

        self.child_index = child_number
        write_json(output_file, command_envelope(result))
        self.latest_child_command = {
            **self.latest_child_command,
            "status": "completed",
            "completedAtUtc": datetime.now(timezone.utc).isoformat(),
            "durationSeconds": round(time.monotonic() - started_monotonic, 3),
            "exitCode": result.exit_code,
            "jsonStatus": self._command_json_status(result.json_data),
            "parseError": result.parse_error,
            "ok": result.ok,
        }
        self._write_progress("running")
        return result

    def _command_json_status(self, payload: Any) -> Any:
        for key in ("Status", "ProofValidationStatus", "status"):
            value = self._get(payload, key)
            if value:
                return value
        return None

    def _process_name(self) -> str:
        return str(self.profile.get("processName", "rift_x64"))

    def _reference_capture_issues(self, result: Any) -> list[str]:
        status = self._get(getattr(result, "json_data", None), "Status")
        issues = [f"reference_capture_failed:exit={getattr(result, 'exit_code', None)};status={status}"]
        parse_error = getattr(result, "parse_error", None)
        if parse_error:
            issues.append(f"reference_capture_json_parse_failed:{parse_error}")
        stderr = str(getattr(result, "stderr", "") or "")
        if "No usable RRAPICOORD1 marker" in stderr:
            issues.append("reference_marker_unavailable:no_usable_rrapicoord1")
        return issues

    def _proof_anchor_file(self) -> str:
        return str(
            self.profile.get(
                "proofAnchorFile",
                self.repo_root / "scripts" / "captures" / "telemetry-proof-coord-anchor.json",
            )
        )

    def _promotion_baseline_pool_file(self) -> Path:
        return Path(
            str(
                self.profile.get(
                    "promotionBaselinePoolFile",
                    self.repo_root / "scripts" / "captures" / "live-test-promotion-baselines.json",
                )
            )
        )

    def _select_promotion_readback_files(self, fresh_summary_file: Path) -> tuple[list[str], dict[str, Any]]:
        candidate_paths = collect_candidate_paths(
            configured_summary=self.profile.get("promotionReferenceReadbackSummary"),
            pool_file=self._promotion_baseline_pool_file(),
            proof_anchor_file=Path(self._proof_anchor_file()),
        )
        return select_baselines_for_fresh_summary(
            fresh_summary_file=fresh_summary_file,
            candidate_paths=candidate_paths,
            process_id=self.process_id,
            target_window_handle=self.target_window_handle,
            process_name=self._process_name(),
            candidate_id=str(self.profile.get("candidateId", "rift-addon-coordinate-candidate-000001")),
            min_reference_displacement=float(self.profile.get("minReferenceDisplacement", 1.0)),
            max_count=int(self.profile.get("maxPromotionBaselineCandidates", 6)),
        )

    @staticmethod
    def _summary_coordinate(summary_file: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(summary_file.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001 - coordinate is informational only.
            return None
        readback = data.get("ProofAnchorCandidateReadback")
        if isinstance(readback, dict) and isinstance(readback.get("CurrentCoordinate"), dict):
            value = readback["CurrentCoordinate"]
            return {
                "X": value.get("X"),
                "Y": value.get("Y"),
                "Z": value.get("Z"),
                "RecordedAtUtc": value.get("RecordedAtUtc"),
            }
        matches = data.get("BestReferenceMatches")
        if isinstance(matches, list) and matches:
            sample = matches[0].get("FirstDecodedSample") if isinstance(matches[0], dict) else None
            if isinstance(sample, dict):
                return {
                    "X": sample.get("X"),
                    "Y": sample.get("Y"),
                    "Z": sample.get("Z"),
                    "RecordedAtUtc": sample.get("RecordedAtUtc"),
                }
        return None

    def _validate_promotion_reference_target(self) -> list[str]:
        path_value = self.profile.get("promotionReferenceReadbackSummary")
        if not path_value:
            return ["promotion_reference_readback_summary_missing"]

        path = Path(str(path_value))
        if not path.exists():
            return [f"promotion_reference_readback_summary_not_found:{path}"]

        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001 - capture bad operator artifact.
            return [f"promotion_reference_readback_summary_unreadable:{type(exc).__name__}:{exc}"]

        issues: list[str] = []
        actual_pid = self._coerce_int(data.get("ProcessId"))
        if actual_pid is not None and actual_pid != int(self.process_id):
            issues.append(
                f"promotion_reference_pid_mismatch:actual={actual_pid};expected={self.process_id}"
            )

        actual_process_name = data.get("ProcessName")
        if actual_process_name:
            expected_name = self._normalize_process_name(self._process_name())
            actual_name = self._normalize_process_name(str(actual_process_name))
            if actual_name.lower() != expected_name.lower():
                issues.append(
                    f"promotion_reference_process_name_mismatch:"
                    f"actual={actual_name};expected={expected_name}"
                )

        actual_hwnd = data.get("TargetWindowHandle")
        actual_hwnd_int = self._coerce_int(actual_hwnd)
        expected_hwnd_int = self._coerce_int(self.target_window_handle)
        if (
            actual_hwnd is not None
            and actual_hwnd_int is not None
            and expected_hwnd_int is not None
            and actual_hwnd_int != expected_hwnd_int
        ):
            issues.append(
                "promotion_reference_hwnd_mismatch:"
                f"actual=0x{actual_hwnd_int:X};expected=0x{expected_hwnd_int:X}"
            )

        return issues

    def _can_refresh_for(self, payload: dict[str, Any] | None) -> bool:
        if self.auto_refresh_attempts_used >= int(self.profile.get("maxAutoRefreshAttempts", 0)):
            return False
        issues = "\n".join(self._json_issues(payload))
        if "proof_anchor_age_out_of_range" in issues and self.profile.get(
            "autoRefreshProofOnExpired",
            True,
        ):
            self.auto_refresh_attempts_used += 1
            return True
        if "proof_anchor_remaining_age_budget_too_low" in issues and self.profile.get(
            "autoRefreshProofOnLowAgeBudget",
            True,
        ):
            self.auto_refresh_attempts_used += 1
            return True
        if self._get(payload, "Status") in {"blocked-preflight", "blocked-preflight-age-budget"}:
            self.auto_refresh_attempts_used += 1
            return True
        return False

    def _map_blocked_status(self, payload: dict[str, Any] | None, *, default: str) -> str:
        status = str(self._get(payload, "Status") or "")
        issues = "\n".join(self._json_issues(payload))
        if "proof_anchor_remaining_age_budget_too_low" in issues or "age-budget" in status:
            return BLOCKED_LOW_AGE_BUDGET
        if "proof_anchor_age_out_of_range" in issues:
            return BLOCKED_PROOF_EXPIRED
        if status.startswith("blocked-dry") or status.startswith("blocked-preflight"):
            return BLOCKED_DRY_RUN
        if status == "input-failed":
            return INPUT_FAILED
        if status == "blocked-post-readback":
            return POST_READBACK_FAILED
        return default

    def _append_series_pulse(
        self,
        *,
        pulse_index: int,
        status: str,
        stage: str,
        dry_run: dict[str, Any] | None,
        live_result: dict[str, Any] | None,
    ) -> None:
        post = self._get(live_result, "PostReadback") if live_result else None
        pre = self._get(live_result, "Preflight") if live_result else None
        if not isinstance(pre, dict):
            pre = self._get(dry_run, "Preflight")
        current_source = post if isinstance(post, dict) else live_result
        item = {
            "pulseIndex": pulse_index,
            "status": status,
            "stage": stage,
            "dryRunSummaryFile": self._get(dry_run, "SummaryFile"),
            "liveSummaryFile": self._get(live_result, "SummaryFile"),
            "movementSent": bool(self._get(live_result, "MovementSent")) if live_result else False,
            "movementAttempted": (
                bool(self._get(live_result, "MovementAttempted")) if live_result else False
            ),
            "preCoordinate": self._coordinate(self._get(pre, "CurrentCoordinate")),
            "postCoordinate": self._coordinate(self._get(current_source, "CurrentCoordinate")),
            "coordinateDelta": self._delta(self._get(live_result, "CoordinateDelta")),
            "issues": self._json_issues(live_result) or self._json_issues(dry_run),
        }
        recording = self._record_coordinate_pulse(
            pulse_index=pulse_index,
            stage=stage,
            dry_run=dry_run,
            live_result=live_result,
        )
        if recording:
            item["coordinateRecording"] = recording
        self.series_pulses.append(item)
        self._write_progress("running")

    def _record_coordinate_pulse(
        self,
        *,
        pulse_index: int,
        stage: str,
        dry_run: dict[str, Any] | None,
        live_result: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        recording = record_pulse_coordinates(
            run_dir=self.run_dir,
            profile_name=self.profile_name,
            profile=self.profile,
            process_id=self.process_id,
            target_window_handle=self.target_window_handle,
            pulse_index=pulse_index,
            stage=stage,
            dry_run=dry_run,
            live_result=live_result,
        )
        if recording:
            self.coordinate_recordings.append(recording)
        return recording

    def _series_movement_started(self) -> bool:
        return any(
            bool(pulse.get("movementSent")) or bool(pulse.get("movementAttempted"))
            for pulse in self.series_pulses
        )

    def _completed_series_pulse_count(self) -> int:
        return sum(1 for pulse in self.series_pulses if pulse.get("status") == "passed")

    def _finish(self, status: str, *, final_json: dict[str, Any] | None = None) -> dict[str, Any]:
        ok = status in SUCCESS_STATUSES
        post = self._get(final_json, "PostReadback") if final_json else None
        current_source = post if isinstance(post, dict) else final_json
        movement_sent = bool(self._get(final_json, "MovementSent")) if final_json else False
        movement_attempted = (
            bool(self._get(final_json, "MovementAttempted")) if final_json else False
        )
        if self.series_pulses:
            movement_sent = movement_sent or any(
                bool(pulse.get("movementSent")) for pulse in self.series_pulses
            )
            movement_attempted = movement_attempted or any(
                bool(pulse.get("movementAttempted")) for pulse in self.series_pulses
            )
        summary = {
            "schemaVersion": 1,
            "mode": "rift-live-test-orchestrator",
            "profileName": self.profile_name,
            "status": status,
            "ok": ok,
            "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
            "runDirectory": str(self.run_dir),
            "profileEffectiveFile": str(self.run_dir / "profile-effective.json"),
            "live": self.live,
            "processId": self.process_id,
            "targetWindowHandle": self.target_window_handle,
            "movementSent": movement_sent,
            "movementAttempted": movement_attempted,
            "currentCoordinate": self._coordinate(self._get(current_source, "CurrentCoordinate")),
            "coordinateDelta": self._delta(self._get(final_json, "CoordinateDelta")),
            "summaryFile": self._get(final_json, "SummaryFile") if final_json else None,
            "issues": self.issues,
            "states": self.states,
            "childOutputsDirectory": str(self.child_dir),
            "runManifestFile": str(self.run_dir / "run-manifest.json"),
            "autoRefreshAttemptsUsed": self.auto_refresh_attempts_used,
            "runGates": self._run_gates(),
            "runHealth": self._run_health(
                status,
                movement_sent=movement_sent,
                movement_attempted=movement_attempted,
                final_summary_written=True,
            ),
            "latestPointer": self._latest_pointer_metadata(),
            "noCheatEngine": True,
            "savedVariablesUsedAsLiveTruth": False,
        }
        if self.gui_info:
            summary["gui"] = self.gui_info
        if self.latest_child_command:
            summary["latestChildCommand"] = self.latest_child_command
        if self.series_pulses:
            summary["seriesPulses"] = self.series_pulses
            summary["requestedPulseCount"] = int(
                (self.profile.get("input") or {}).get("pulseCount", len(self.series_pulses))
            )
            summary["completedPulseCount"] = self._completed_series_pulse_count()
            summary["seriesCoordinateDelta"] = self._series_coordinate_delta()
        if self.coordinate_recordings:
            summary["coordinateRecordings"] = self.coordinate_recordings
            summary["coordinateSamplesFile"] = self.coordinate_recordings[-1].get("samplesFile")
        summary["runProgressFile"] = str(self.progress_file)
        write_json(self.run_dir / "run-summary.json", summary)
        if self.profile.get("writeMarkdownSummary", True):
            write_markdown_summary(self.run_dir / "run-summary.md", summary)
        self._write_progress(status, final_json=final_json)
        self._write_latest_pointer(
            status,
            run_summary_file=self.run_dir / "run-summary.json",
            movement_sent=movement_sent,
            movement_attempted=movement_attempted,
        )
        return summary

    def _write_progress(self, status: str, *, final_json: dict[str, Any] | None = None) -> None:
        post = self._get(final_json, "PostReadback") if final_json else None
        current_source = post if isinstance(post, dict) else final_json
        movement_sent = bool(self._get(final_json, "MovementSent")) if final_json else False
        movement_attempted = (
            bool(self._get(final_json, "MovementAttempted")) if final_json else False
        )
        if self.series_pulses:
            movement_sent = movement_sent or any(
                bool(pulse.get("movementSent")) for pulse in self.series_pulses
            )
            movement_attempted = movement_attempted or any(
                bool(pulse.get("movementAttempted")) for pulse in self.series_pulses
            )

        snapshot = {
            "schemaVersion": 1,
            "mode": "rift-live-test-progress",
            "profileName": self.profile_name,
            "status": status,
            "updatedAtUtc": datetime.now(timezone.utc).isoformat(),
            "runDirectory": str(self.run_dir),
            "runSummaryFile": str(self.run_dir / "run-summary.json"),
            "runProgressFile": str(self.progress_file),
            "live": self.live,
            "processId": self.process_id,
            "targetWindowHandle": self.target_window_handle,
            "movementSent": movement_sent,
            "movementAttempted": movement_attempted,
            "currentCoordinate": self._coordinate(self._get(current_source, "CurrentCoordinate")),
            "coordinateDelta": self._delta(self._get(final_json, "CoordinateDelta")),
            "issues": self.issues,
            "states": self.states,
            "childOutputsDirectory": str(self.child_dir),
            "autoRefreshAttemptsUsed": self.auto_refresh_attempts_used,
            "runGates": self._run_gates(),
            "runHealth": self._run_health(
                status,
                movement_sent=movement_sent,
                movement_attempted=movement_attempted,
                final_summary_written=(self.run_dir / "run-summary.json").exists(),
            ),
            "latestPointer": self._latest_pointer_metadata(),
            "noCheatEngine": True,
            "savedVariablesUsedAsLiveTruth": False,
            "finalSummaryWritten": (self.run_dir / "run-summary.json").exists(),
        }
        if self.gui_info:
            snapshot["gui"] = self.gui_info
        if self.latest_child_command:
            snapshot["latestChildCommand"] = self.latest_child_command
        if self.series_pulses:
            snapshot["seriesPulses"] = self.series_pulses
            snapshot["requestedPulseCount"] = int(
                (self.profile.get("input") or {}).get("pulseCount", len(self.series_pulses))
            )
            snapshot["completedPulseCount"] = self._completed_series_pulse_count()
            snapshot["seriesCoordinateDelta"] = self._series_coordinate_delta()
        if self.coordinate_recordings:
            snapshot["coordinateRecordings"] = self.coordinate_recordings
            snapshot["coordinateSamplesFile"] = self.coordinate_recordings[-1].get("samplesFile")
        write_json(self.progress_file, snapshot)
        self._write_latest_pointer(
            status,
            run_progress_file=self.progress_file,
            movement_sent=movement_sent,
            movement_attempted=movement_attempted,
        )

    def _write_latest_pointer(
        self,
        status: str,
        *,
        run_summary_file: Path | None = None,
        run_progress_file: Path | None = None,
        movement_sent: bool | None = None,
        movement_attempted: bool | None = None,
    ) -> None:
        metadata = self._latest_pointer_metadata()
        if not metadata["updateAllowed"]:
            return
        write_json(
            self.latest_pointer_file,
            {
                "runSummaryFile": str(run_summary_file or (self.run_dir / "run-summary.json")),
                "runProgressFile": str(run_progress_file or self.progress_file),
                "runDirectory": str(self.run_dir),
                "profileName": self.profile_name,
                "status": status,
                "runHealth": self._run_health(
                    status,
                    movement_sent=movement_sent,
                    movement_attempted=movement_attempted,
                    final_summary_written=(self.run_dir / "run-summary.json").exists(),
                ),
                "runDirectoryInsideRepo": metadata["runDirectoryInsideRepo"],
                "progressFileInsideRepo": metadata["progressFileInsideRepo"],
                "runSummaryFileInsideRepo": metadata["runSummaryFileInsideRepo"],
                "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
                "finalSummaryWritten": (self.run_dir / "run-summary.json").exists(),
            },
        )

    def _latest_pointer_metadata(self) -> dict[str, Any]:
        update_requested = bool(self.profile.get("updateLatestPointer", True))
        allow_external = bool(self.profile.get("updateLatestPointerForExternalOutputRoot", False))
        run_dir_inside_repo = path_is_relative_to(self.run_dir, self.repo_root)
        progress_file_inside_repo = path_is_relative_to(self.progress_file, self.repo_root)
        summary_file_inside_repo = path_is_relative_to(
            self.run_dir / "run-summary.json",
            self.repo_root,
        )
        update_allowed = update_requested and (run_dir_inside_repo or allow_external)
        skip_reason = None
        if not update_requested:
            skip_reason = "disabled_by_profile"
        elif not run_dir_inside_repo and not allow_external:
            skip_reason = "output_root_outside_repo"
        return {
            "path": str(self.latest_pointer_file),
            "updateRequested": update_requested,
            "updateAllowed": update_allowed,
            "skipReason": skip_reason,
            "runDirectoryInsideRepo": run_dir_inside_repo,
            "progressFileInsideRepo": progress_file_inside_repo,
            "runSummaryFileInsideRepo": summary_file_inside_repo,
        }

    def _manifest(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "mode": "rift-live-test-orchestrator",
            "profileName": self.profile_name,
            "startedAtUtc": datetime.now(timezone.utc).isoformat(),
            "runDirectory": str(self.run_dir),
            "profileEffectiveFile": str(self.run_dir / "profile-effective.json"),
            "profilesFile": self.profile.get("profilesFile"),
            "live": self.live,
            "processId": self.process_id,
            "targetWindowHandle": self.target_window_handle,
            "processName": self.profile.get("processName", "rift_x64"),
            "maxAutoRefreshAttempts": int(self.profile.get("maxAutoRefreshAttempts", 0)),
            "runGates": self._run_gates(),
            "latestPointer": self._latest_pointer_metadata(),
            "gui": self.gui_info,
            "noCheatEngine": True,
            "savedVariablesUsedAsLiveTruth": False,
        }

    def _run_gates(self) -> dict[str, Any]:
        return {
            "profileMode": self.profile.get("mode"),
            "requireExactTarget": bool(self.profile.get("requireExactTarget", True)),
            "requireLiveFlagForInput": bool(self.profile.get("requireLiveFlagForInput", True)),
            "proofAnchorFile": self.profile.get("proofAnchorFile"),
            "proofAnchorMaxAgeSeconds": self.profile.get("proofAnchorMaxAgeSeconds"),
            "minimumPostReadbackAgeBudgetSeconds": self.profile.get(
                "minimumPostReadbackAgeBudgetSeconds"
            ),
            "referenceMaxAgeSeconds": self.profile.get("referenceMaxAgeSeconds"),
            "maxAutoRefreshAttempts": int(self.profile.get("maxAutoRefreshAttempts", 0)),
            "autoRefreshAttemptsUsed": self.auto_refresh_attempts_used,
            "updateLatestPointer": bool(self.profile.get("updateLatestPointer", True)),
            "updateLatestPointerForExternalOutputRoot": bool(
                self.profile.get("updateLatestPointerForExternalOutputRoot", False)
            ),
            "noCheatEngine": True,
            "savedVariablesLiveTruthAllowed": False,
        }

    def _run_health(
        self,
        status: str,
        *,
        movement_sent: bool | None = None,
        movement_attempted: bool | None = None,
        final_summary_written: bool | None = None,
    ) -> dict[str, Any]:
        latest_child_status = None
        latest_child_ok = None
        if self.latest_child_command:
            latest_child_status = self.latest_child_command.get("status")
            latest_child_ok = self.latest_child_command.get("ok")

        return {
            "state": classify_run_health(status),
            "status": status,
            "ok": status in SUCCESS_STATUSES,
            "issueCount": len(self.issues),
            "primaryIssue": self.issues[0] if self.issues else None,
            "movementSent": bool(movement_sent) if movement_sent is not None else None,
            "movementAttempted": (
                bool(movement_attempted) if movement_attempted is not None else None
            ),
            "finalSummaryWritten": bool(final_summary_written),
            "latestChildStatus": latest_child_status,
            "latestChildOk": latest_child_ok,
            "noCheatEngine": True,
            "savedVariablesUsedAsLiveTruth": False,
        }

    def _start_gui(self) -> dict[str, Any]:
        info = start_progress_gui(
            repo_root=self.repo_root,
            progress_file=self.progress_file,
            run_dir=self.run_dir,
            profile_name=self.profile_name,
            profile=self.profile,
        )
        write_json(self.run_dir / "gui-start.json", info)
        return info

    def _state(
        self,
        state: str,
        status: str,
        *,
        detail: str | None = None,
        summaryFile: str | None = None,
    ) -> None:
        item = {
            "state": state,
            "status": status,
            "recordedAtUtc": datetime.now(timezone.utc).isoformat(),
        }
        if detail:
            item["detail"] = detail
        if summaryFile:
            item["summaryFile"] = summaryFile
        self.states.append(item)
        self._write_progress("running")

    @staticmethod
    def _get(payload: Any, name: str, default: Any = None) -> Any:
        if isinstance(payload, dict):
            return payload.get(name, default)
        return default

    @staticmethod
    def _json_issues(payload: dict[str, Any] | None) -> list[str]:
        if not isinstance(payload, dict):
            return []
        issues = payload.get("Issues")
        if isinstance(issues, list):
            return [str(item) for item in issues]
        if isinstance(issues, str):
            return [issues]
        preflight = payload.get("Preflight")
        if isinstance(preflight, dict):
            nested = preflight.get("Issues")
            if isinstance(nested, list):
                return [str(item) for item in nested]
        return []

    @classmethod
    def _movement_started(cls, payload: dict[str, Any] | None) -> bool:
        if not isinstance(payload, dict):
            return False
        if bool(payload.get("MovementSent")) or bool(payload.get("MovementAttempted")):
            return True
        pulses = payload.get("Pulses")
        if isinstance(pulses, list):
            for pulse in pulses:
                if isinstance(pulse, dict) and (
                    bool(pulse.get("MovementSent")) or bool(pulse.get("MovementAttempted"))
                ):
                    return True
        return False

    @classmethod
    def _safe_to_retry_live_input(cls, payload: dict[str, Any] | None) -> bool:
        return not cls._movement_started(payload)

    @staticmethod
    def _readback_valid(payload: dict[str, Any] | None) -> bool:
        return (
            isinstance(payload, dict)
            and payload.get("Status") == "valid"
            and bool(payload.get("MovementAllowed"))
        )

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).strip(), 0)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_process_name(value: str) -> str:
        text = str(value).strip()
        if text.lower().endswith(".exe"):
            return text[:-4]
        return text

    def _series_coordinate_delta(self) -> dict[str, Any] | None:
        if not self.series_pulses:
            return None

        first: dict[str, Any] | None = None
        last: dict[str, Any] | None = None
        for pulse in self.series_pulses:
            if first is None and isinstance(pulse.get("preCoordinate"), dict):
                first = pulse["preCoordinate"]
            if isinstance(pulse.get("postCoordinate"), dict):
                last = pulse["postCoordinate"]

        if not first or not last:
            return None

        try:
            delta_x = float(last["x"]) - float(first["x"])
            delta_y = float(last["y"]) - float(first["y"])
            delta_z = float(last["z"]) - float(first["z"])
        except (KeyError, TypeError, ValueError):
            return None

        return {
            "deltaX": delta_x,
            "deltaY": delta_y,
            "deltaZ": delta_z,
            "planarDistance": math.sqrt((delta_x * delta_x) + (delta_z * delta_z)),
            "spatialDistance": math.sqrt(
                (delta_x * delta_x) + (delta_y * delta_y) + (delta_z * delta_z)
            ),
        }

    @staticmethod
    def _coordinate(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        return {
            "x": value.get("X"),
            "y": value.get("Y"),
            "z": value.get("Z"),
            "recordedAtUtc": value.get("RecordedAtUtc"),
        }

    @staticmethod
    def _delta(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        return {
            "deltaX": value.get("DeltaX"),
            "deltaY": value.get("DeltaY"),
            "deltaZ": value.get("DeltaZ"),
            "planarDistance": value.get("PlanarDistance"),
            "spatialDistance": value.get("SpatialDistance"),
        }


def path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
