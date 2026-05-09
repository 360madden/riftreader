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
    BLOCKED_TARGET_DRIFT,
    BLOCKED_TARGET_MISMATCH,
    FAILED_INTERNAL_ERROR,
    INPUT_FAILED,
    INPUT_NO_MOVEMENT,
    PASSED,
    PASSED_BASELINE_CAPTURED,
    PASSED_PROOF_ONLY,
    PARTIAL_SERIES_STOPPED,
    POST_READBACK_FAILED,
    SUCCESS_STATUSES,
)
from .target import verify_target
from .target_control import TargetControlOptions, run_target_control
from .target_control_summary import compact_target_control_summary, target_control_state_detail


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


class TargetDriftError(RuntimeError):
    def __init__(
        self,
        issues: list[str],
        final_json: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("target drift detected")
        self.issues = issues
        self.final_json = final_json or {}


def classify_run_health(status: str) -> str:
    text = str(status or "").lower()
    if text in SUCCESS_STATUSES or text.startswith("passed"):
        return "ok"
    if text == "running" or text == "refreshing":
        return "running"
    if "partial" in text or "low-age" in text or "age-budget" in text:
        return "warning"
    if text == INPUT_NO_MOVEMENT or "no-movement" in text:
        return "failed"
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
        self.current_proof_pointer_update: dict[str, Any] | None = None
        self.target_control_summary: dict[str, Any] | None = None

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
            self._record_target_control_preflight()

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
                movement_issue = self._movement_delta_issue(live_result)
                if movement_issue:
                    self.issues.append(movement_issue)
                    self._state(
                        "live-input",
                        INPUT_NO_MOVEMENT,
                        summaryFile=self._get(live_result, "SummaryFile"),
                    )
                    return self._finish(INPUT_NO_MOVEMENT, final_json=live_result)
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
        except TargetDriftError as exc:
            self.issues.extend(exc.issues)
            self._state(
                "target-drift-reacquire",
                BLOCKED_TARGET_DRIFT,
                detail=";".join(exc.issues),
                summaryFile=self._get(exc.final_json, "SummaryFile"),
            )
            return self._finish(BLOCKED_TARGET_DRIFT, final_json=exc.final_json)
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

    def _record_target_control_preflight(self) -> None:
        output_dir = self.run_dir / "target-control"
        try:
            summary = run_target_control(
                TargetControlOptions(
                    repo_root=self.repo_root,
                    process_id=self.process_id,
                    window_handle=self.target_window_handle,
                    process_name=self._process_name(),
                    title_contains=str(self.profile.get("titleContains", "RIFT")),
                    output_dir=output_dir,
                    retries=int(self.profile.get("targetControlRetries", 5)),
                    settle_ms=int(self.profile.get("targetControlSettleMilliseconds", 400)),
                    strong_assist=bool(self.profile.get("targetControlStrongAssist", True)),
                )
            )
        except Exception as exc:  # noqa: BLE001 - target-control must record failure without hiding root run status.
            summary = {
                "schemaVersion": 1,
                "status": "target-control-record-failed",
                "classification": "target-control-exception",
                "ok": False,
                "readyForReadOnlyProof": False,
                "readyForVisualGate": False,
                "readyForLiveInput": False,
                "summaryPath": None,
                "blockers": [f"target_control_exception:{type(exc).__name__}:{exc}"],
                "warnings": [],
                "capabilities": {},
                "movementSent": False,
                "inputSent": False,
                "screenshotKeySent": False,
                "reloaduiSent": False,
                "noCheatEngine": True,
            }
        self.target_control_summary = compact_target_control_summary(summary)
        write_json(self.child_dir / "002-target-control.json", summary)
        self._state(
            "target-control",
            str(self.target_control_summary.get("status", "unknown")),
            detail=target_control_state_detail(self.target_control_summary),
            summaryFile=self.target_control_summary.get("summaryPath"),
        )

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

        candidate_file = self._proof_pose_candidate_file()
        if candidate_file is None:
            pointer_drift = self._current_proof_pointer_target_drift()
            if pointer_drift.get("issues"):
                final = self._write_target_drift_reacquire_summary(
                    issues=[str(issue) for issue in pointer_drift["issues"]],
                    reference_file=reference_file,
                    source="current-proof-pointer-target-check",
                    details=pointer_drift,
                )
                raise TargetDriftError([str(issue) for issue in pointer_drift["issues"]], final)

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
        if candidate_file:
            pose_args[0:0] = ["-CandidateFile", str(candidate_file)]
        pose = self._run_ps1("capture-proof-pose", "capture-riftscan-proof-pose.ps1", pose_args)
        if pose.exit_code != 0 or self._get(pose.json_data, "Status") != "captured":
            drift_issues = self._target_drift_issues_from_command(pose)
            if drift_issues:
                final = self._write_target_drift_reacquire_summary(
                    issues=drift_issues,
                    reference_file=reference_file,
                    source="capture-proof-pose-target-check",
                    details={
                        "poseExitCode": pose.exit_code,
                        "poseStatus": self._get(pose.json_data, "Status"),
                        "poseParseError": getattr(pose, "parse_error", None),
                    },
                )
                raise TargetDriftError(drift_issues, final)
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
        candidate_id = self._candidate_id()
        script = " ".join(
            [
                "&",
                ps_quote(script_path),
                "-ReadbackSummaryFile",
                array_literal,
                "-CandidateId",
                ps_quote(candidate_id),
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
                movement_issue = self._movement_delta_issue(live_result)
                if movement_issue:
                    self.issues.append(movement_issue)
                    mapped = (
                        PARTIAL_SERIES_STOPPED
                        if self._series_movement_started()
                        else INPUT_NO_MOVEMENT
                    )
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
            "-InputBackend",
            str(self.profile.get("inputBackend", "window-message")),
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

    def _current_proof_pointer_target_drift(self) -> dict[str, Any]:
        if self.profile.get("candidateFile"):
            return {
                "checked": False,
                "reason": "explicit_candidate_file_supplied",
                "issues": [],
            }

        pointer_file = self._current_proof_pointer_file()
        result: dict[str, Any] = {
            "checked": True,
            "pointerFile": str(pointer_file),
            "requestedTarget": {
                "processId": self.process_id,
                "processName": self._process_name(),
                "targetWindowHandle": self.target_window_handle,
            },
            "issues": [],
        }
        try:
            pointer = json.loads(pointer_file.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            result["checked"] = False
            result["reason"] = "current_proof_pointer_missing"
            return result
        except Exception as exc:  # noqa: BLE001 - invalid pointer is target-state evidence.
            result["issues"] = [
                f"target_drift:current_proof_pointer_unreadable:{type(exc).__name__}:{exc}"
            ]
            return result

        preserved_evidence = self._extract_current_proof_pointer_evidence(pointer)
        if preserved_evidence:
            result["preservedEvidence"] = preserved_evidence

        target = self._first_mapping_value(pointer, "target")
        if not isinstance(target, dict):
            result["issues"] = ["target_drift:current_proof_pointer_missing_target_metadata"]
            return result

        pointer_process_id = self._coerce_int(
            self._first_mapping_value(target, "processId", "ProcessId", "pid")
        )
        pointer_process_name = self._first_mapping_value(target, "processName", "ProcessName")
        pointer_window_handle = self._first_mapping_value(
            target,
            "targetWindowHandle",
            "TargetWindowHandle",
            "hwnd",
        )
        pointer_window_int = self._coerce_int(pointer_window_handle)
        requested_window_int = self._coerce_int(self.target_window_handle)

        result["pointerTarget"] = {
            "processId": pointer_process_id,
            "processName": pointer_process_name,
            "targetWindowHandle": pointer_window_handle,
        }

        issues: list[str] = []
        if pointer_process_id is None or pointer_process_id != int(self.process_id):
            issues.append(
                "target_drift:current_proof_pointer_pid_mismatch:"
                f"actual={pointer_process_id};expected={self.process_id}"
            )

        if pointer_process_name is None or not str(pointer_process_name).strip():
            issues.append("target_drift:current_proof_pointer_process_name_missing")
        else:
            actual_name = self._normalize_process_name(str(pointer_process_name))
            expected_name = self._normalize_process_name(self._process_name())
            if actual_name.lower() != expected_name.lower():
                issues.append(
                    "target_drift:current_proof_pointer_process_name_mismatch:"
                    f"actual={actual_name};expected={expected_name}"
                )

        if pointer_window_handle is None or not str(pointer_window_handle).strip():
            issues.append("target_drift:current_proof_pointer_hwnd_missing")
        elif (
            pointer_window_int is not None
            and requested_window_int is not None
            and pointer_window_int != requested_window_int
        ):
            issues.append(
                "target_drift:current_proof_pointer_hwnd_mismatch:"
                f"actual=0x{pointer_window_int:X};expected=0x{requested_window_int:X}"
            )

        result["issues"] = issues
        return result

    def _write_target_drift_reacquire_summary(
        self,
        *,
        issues: list[str],
        reference_file: Path,
        source: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_coordinate = self._reference_coordinate(reference_file)
        summary_path = self.run_dir / "target-drift-reacquire-current-state.json"
        payload = {
            "SchemaVersion": 1,
            "Mode": "target-drift-reacquire-current-state",
            "GeneratedAtUtc": datetime.now(timezone.utc).isoformat(),
            "Status": BLOCKED_TARGET_DRIFT,
            "MovementSent": False,
            "MovementAttempted": False,
            "ProcessName": self._process_name(),
            "ProcessId": self.process_id,
            "TargetWindowHandle": self.target_window_handle,
            "CurrentCoordinate": current_coordinate,
            "ReferenceFile": str(reference_file),
            "ReacquireStatus": (
                "api-reference-captured" if current_coordinate else "api-reference-captured-no-coordinate"
            ),
            "ProofPointerFile": str(self._current_proof_pointer_file()),
            "TargetDrift": {
                "source": source,
                "issues": issues,
                "details": details or {},
                "movementGate": "blocked",
                "proofAnchorPromoted": False,
                "reason": (
                    "The live target changed underneath the cached proof pointer. "
                    "The runner reacquired current API coordinate state but did not "
                    "promote a movement-grade proof anchor."
                ),
            },
            "PreservedHistoricalEvidence": (
                details.get("preservedEvidence")
                if isinstance(details, dict) and details.get("preservedEvidence")
                else None
            ),
            "MovementGate": "blocked_until_current_process_proof_anchor_is_rebuilt_after_target_drift",
            "SummaryFile": str(summary_path),
            "NoCheatEngine": True,
            "SavedVariablesUsedAsLiveTruth": False,
            "Issues": issues,
        }
        if payload["PreservedHistoricalEvidence"] is None:
            payload.pop("PreservedHistoricalEvidence")
        write_json(summary_path, payload)
        return payload

    def _reference_coordinate(self, reference_file: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(reference_file.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001 - coordinate is best-effort reporting.
            return None

        coordinate = self._first_mapping_value(data, "CurrentCoordinate", "coordinate")
        if not isinstance(coordinate, dict):
            return None

        x = self._first_mapping_value(coordinate, "X", "x")
        y = self._first_mapping_value(coordinate, "Y", "y")
        z = self._first_mapping_value(coordinate, "Z", "z")
        if x is None or y is None or z is None:
            return None
        return {
            "X": x,
            "Y": y,
            "Z": z,
            "RecordedAtUtc": self._first_mapping_value(
                coordinate,
                "RecordedAtUtc",
                "recordedAtUtc",
                "captured_at_utc",
            )
            or self._first_mapping_value(data, "CapturedAtUtc", "captured_at_utc"),
        }

    @staticmethod
    def _first_mapping_value(payload: Any, *names: str) -> Any:
        if not isinstance(payload, dict):
            return None
        for name in names:
            if name in payload:
                return payload[name]
        return None

    def _extract_current_proof_pointer_evidence(self, pointer: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(pointer, dict):
            return None

        evidence: dict[str, Any] = {
            "classification": "historical-target-epoch-evidence",
            "reusePolicy": (
                "do-not-use-as-current-proof; preserve for audit/reacquire hints only; "
                "candidate addresses and readbacks must be rescored against the current PID/HWND"
            ),
        }
        for key in (
            "lastUpdatedUtc",
            "status",
            "target",
            "riftscanCandidateSource",
            "latestValidation",
            "latestProofOnly",
            "latestBaselineCapture",
            "latestForward250",
            "latestForwardSeries3x250",
        ):
            value = pointer.get(key)
            if value:
                evidence[key] = value

        source = pointer.get("riftscanCandidateSource")
        if isinstance(source, dict):
            for key in (
                "candidateId",
                "matchFile",
                "truthSummaryFile",
                "inventoryFile",
                "sessionPath",
                "sourceAbsoluteAddressHex",
                "sourceBaseAddressHex",
                "sourceOffsetHex",
            ):
                value = source.get(key)
                if value:
                    evidence.setdefault("reacquireHints", {})[key] = value
        return evidence if len(evidence) > 2 else None

    @classmethod
    def _target_drift_issues_from_command(cls, result: Any) -> list[str]:
        collected: list[str] = []
        payload = getattr(result, "json_data", None)
        for issue in cls._json_issues(payload):
            if cls._looks_like_target_drift_text(issue):
                cls._append_unique(collected, issue)

        text = "\n".join(
            str(value or "")
            for value in (
                getattr(result, "stderr", None),
                getattr(result, "stdout", None),
                getattr(result, "parse_error", None),
            )
        )
        if cls._looks_like_target_drift_text(text):
            cls._append_unique(
                collected,
                "target_drift:current_proof_pointer_or_anchor_target_mismatch",
            )
            for line in text.splitlines():
                clean = line.strip()
                if clean and cls._looks_like_target_drift_text(clean):
                    cls._append_unique(collected, clean)
        return collected

    @classmethod
    def _is_target_drift_payload(cls, payload: dict[str, Any] | None) -> bool:
        if not isinstance(payload, dict):
            return False
        if str(payload.get("Status") or "") == BLOCKED_TARGET_DRIFT:
            return True
        return any(cls._looks_like_target_drift_text(issue) for issue in cls._json_issues(payload))

    @staticmethod
    def _looks_like_target_drift_text(value: Any) -> bool:
        text = str(value or "").lower()
        if not text:
            return False
        pointer_mismatch = (
            "current proof pointer" in text
            and (
                "does not match requested pid" in text
                or "does not match requested hwnd" in text
                or "does not match requested process" in text
                or "missing target metadata" in text
                or "missing targetwindowhandle" in text
                or "missing target processname" in text
            )
        )
        target_window_drift = "target window handle" in text and (
            "belongs to pid" in text
            or "not pid" in text
            or "not a valid window" in text
        )
        return pointer_mismatch or target_window_drift or any(
            phrase in text
            for phrase in (
                "target_drift:",
                "proof_anchor_pid_mismatch",
                "proof_anchor_process_mismatch",
                "window_pid_mismatch:",
            )
        )

    @staticmethod
    def _append_unique(items: list[str], value: Any) -> None:
        text = str(value).strip()
        if text and text not in items:
            items.append(text)

    def _proof_anchor_file(self) -> str:
        return str(
            self.profile.get(
                "proofAnchorFile",
                self.repo_root / "scripts" / "captures" / "telemetry-proof-coord-anchor.json",
            )
        )

    def _resolve_path(self, value: Any) -> Path:
        path = Path(str(value))
        return path if path.is_absolute() else self.repo_root / path

    def _proof_anchor_path(self) -> Path:
        return self._resolve_path(self._proof_anchor_file())

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
            candidate_id=self._candidate_id(),
            min_reference_displacement=float(self.profile.get("minReferenceDisplacement", 1.0)),
            max_count=int(self.profile.get("maxPromotionBaselineCandidates", 6)),
        )

    def _current_proof_pointer_file(self) -> Path:
        configured = self.profile.get("currentProofPointerFile")
        if configured:
            path = Path(str(configured))
            return path if path.is_absolute() else self.repo_root / path
        return self.repo_root / "docs" / "recovery" / "current-proof-anchor-readback.json"

    def _current_proof_anchor(self) -> dict[str, Any] | None:
        try:
            anchor = json.loads(self._proof_anchor_path().read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001 - stale/missing anchor is not fatal for fallback lookup.
            return None
        return anchor if isinstance(anchor, dict) else None

    def _target_issues_for_document(self, document: dict[str, Any], *, label: str) -> list[str]:
        issues: list[str] = []
        process_id = self._coerce_int(
            self._first_mapping_value(document, "ProcessId", "processId", "pid")
        )
        process_name = self._first_mapping_value(document, "ProcessName", "processName")
        window_handle = self._first_mapping_value(
            document,
            "TargetWindowHandle",
            "targetWindowHandle",
            "hwnd",
        )
        window_int = self._coerce_int(window_handle)
        requested_window_int = self._coerce_int(self.target_window_handle)

        if process_id is None or process_id != int(self.process_id):
            issues.append(f"{label}_pid_mismatch:actual={process_id};expected={self.process_id}")

        if process_name is None or not str(process_name).strip():
            issues.append(f"{label}_process_name_missing")
        else:
            actual_name = self._normalize_process_name(str(process_name))
            expected_name = self._normalize_process_name(self._process_name())
            if actual_name.lower() != expected_name.lower():
                issues.append(
                    f"{label}_process_name_mismatch:actual={actual_name};expected={expected_name}"
                )

        if window_handle is None or not str(window_handle).strip():
            issues.append(f"{label}_hwnd_missing")
        elif (
            window_int is not None
            and requested_window_int is not None
            and window_int != requested_window_int
        ):
            issues.append(f"{label}_hwnd_mismatch:actual=0x{window_int:X};expected=0x{requested_window_int:X}")
        return issues

    def _current_proof_anchor_candidate_id(self) -> str | None:
        anchor = self._current_proof_anchor()
        if not anchor or self._target_issues_for_document(anchor, label="proof_anchor"):
            return None
        evidence = anchor.get("Evidence")
        if isinstance(evidence, dict) and evidence.get("CandidateId"):
            return str(evidence["CandidateId"])
        return None

    def _proof_pose_candidate_file(self) -> Path | None:
        explicit = self.profile.get("candidateFile")
        if explicit:
            return self._resolve_path(explicit)

        anchor = self._current_proof_anchor()
        if not anchor or self._target_issues_for_document(anchor, label="proof_anchor"):
            return None

        evidence = anchor.get("Evidence")
        if not isinstance(evidence, dict):
            return None

        readback_files = evidence.get("ReadbackSummaryFiles")
        if not isinstance(readback_files, list):
            readback_files = []
        for summary_value in reversed(readback_files):
            source = self._source_candidate_file_from_readback_summary(summary_value)
            if source is not None:
                return source

        return self._write_candidate_file_from_current_proof_anchor(anchor, evidence)

    def _source_candidate_file_from_readback_summary(self, summary_value: Any) -> Path | None:
        if not summary_value:
            return None
        summary_path = self._resolve_path(summary_value)
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001 - old summary may be missing; try the next one.
            return None
        if not isinstance(summary, dict):
            return None
        source_candidate_file = summary.get("SourceCandidateFile")
        if not source_candidate_file:
            return None
        source_path = self._resolve_path(source_candidate_file)
        return source_path if source_path.exists() else None

    def _candidate_record_from_candidate_file(
        self,
        candidate_file: Path,
        candidate_id: Any,
    ) -> dict[str, Any] | None:
        try:
            data = json.loads(candidate_file.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001 - candidate-file detail is best-effort metadata.
            return None
        candidates = data.get("candidates") if isinstance(data, dict) else None
        if not isinstance(candidates, list):
            return None
        expected = str(candidate_id)
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            actual = self._first_mapping_value(candidate, "candidate_id", "candidateId", "id")
            if actual is not None and str(actual) == expected:
                return candidate
        return None

    def _write_candidate_file_from_current_proof_anchor(
        self,
        anchor: dict[str, Any],
        evidence: dict[str, Any],
    ) -> Path | None:
        candidate_id = evidence.get("CandidateId")
        address = evidence.get("CandidateAddressHex") or anchor.get("ObjectBaseAddress")
        if not candidate_id or not address:
            return None

        candidate_file = self.run_dir / "current-proof-anchor-candidate-seed.json"
        current = self._first_pose_candidate_sample(evidence)
        payload: dict[str, Any] = {
            "candidates": [
                {
                    "candidate_id": str(candidate_id),
                    "source_base_address_hex": str(address),
                    "source_offset_hex": "0x0",
                    "source_absolute_address_hex": str(address),
                    "axis_order": "xyz",
                    "support_count": int(evidence.get("PoseCount") or 1),
                    "validation_status": "current_proof_anchor_seed",
                    "evidence_summary": (
                        "Synthesized from a current-target proof anchor so stale recovery "
                        "pointers cannot override newer same-PID/HWND evidence."
                    ),
                }
            ]
        }
        if current:
            payload["candidates"][0]["best_memory_x"] = current.get("X")
            payload["candidates"][0]["best_memory_y"] = current.get("Y")
            payload["candidates"][0]["best_memory_z"] = current.get("Z")
        write_json(candidate_file, payload)
        return candidate_file

    @staticmethod
    def _first_pose_candidate_sample(evidence: dict[str, Any]) -> dict[str, Any] | None:
        poses = evidence.get("Poses")
        if not isinstance(poses, list) or not poses:
            return None
        sample = poses[-1].get("CandidateSample") if isinstance(poses[-1], dict) else None
        return sample if isinstance(sample, dict) else None

    def _candidate_id(self) -> str:
        source = str(self.profile.get("candidateIdSource", "current-proof-pointer")).lower()
        fallback = str(self.profile.get("candidateId", "rift-addon-coordinate-candidate-000001"))
        if source in {"profile", "config"}:
            return fallback

        anchor_candidate = self._current_proof_anchor_candidate_id()
        if anchor_candidate:
            return anchor_candidate

        pointer_file = self._current_proof_pointer_file()
        try:
            pointer = json.loads(pointer_file.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001 - stale/missing pointer should fall back to profile config.
            return fallback
        candidate_source = pointer.get("riftscanCandidateSource")
        if isinstance(candidate_source, dict):
            pointer_candidate = candidate_source.get("candidateId")
            if pointer_candidate:
                return str(pointer_candidate)
        return fallback

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
        if self._is_target_drift_payload(payload):
            return False
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
        if self._is_target_drift_payload(payload):
            return BLOCKED_TARGET_DRIFT
        if "proof_anchor_remaining_age_budget_too_low" in issues or "age-budget" in status:
            return BLOCKED_LOW_AGE_BUDGET
        if "proof_anchor_age_out_of_range" in issues:
            return BLOCKED_PROOF_EXPIRED
        if status.startswith("blocked-dry") or status.startswith("blocked-preflight"):
            return BLOCKED_DRY_RUN
        if status == "input-failed":
            return INPUT_FAILED
        if status == INPUT_NO_MOVEMENT:
            return INPUT_NO_MOVEMENT
        if status == "blocked-post-readback":
            return POST_READBACK_FAILED
        return default

    def _movement_delta_issue(self, payload: dict[str, Any] | None) -> str | None:
        minimum = self._minimum_movement_planar_distance()
        if minimum <= 0.0:
            return None
        if not isinstance(payload, dict) or not bool(self._get(payload, "MovementSent")):
            return None

        delta = self._get(payload, "CoordinateDelta")
        planar = self._get(delta, "PlanarDistance") if isinstance(delta, dict) else None
        if planar is None:
            return f"movement_delta_missing:required={minimum:.6f}"
        try:
            planar_value = float(planar)
        except (TypeError, ValueError):
            return f"movement_delta_unreadable:actual={planar};required={minimum:.6f}"
        if planar_value < minimum:
            return (
                "movement_delta_below_threshold:"
                f"planar={planar_value:.6f};required={minimum:.6f}"
            )
        return None

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
            "targetControl": self.target_control_summary,
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
        self.current_proof_pointer_update = self._maybe_write_current_proof_pointer(
            status,
            summary=summary,
            final_json=final_json,
        )
        if self.current_proof_pointer_update:
            summary["currentProofPointerUpdate"] = self.current_proof_pointer_update
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

    def _maybe_write_current_proof_pointer(
        self,
        status: str,
        *,
        summary: dict[str, Any],
        final_json: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if status != PASSED_PROOF_ONLY:
            return None
        if not bool(self.profile.get("updateCurrentProofPointer", True)):
            return {
                "updated": False,
                "skipReason": "disabled_by_profile",
            }
        if not path_is_relative_to(self.run_dir, self.repo_root):
            return {
                "updated": False,
                "skipReason": "output_root_outside_repo",
            }

        anchor = self._current_proof_anchor()
        if not anchor:
            return {
                "updated": False,
                "skipReason": "proof_anchor_missing_or_unreadable",
            }
        target_issues = self._target_issues_for_document(anchor, label="proof_anchor")
        if target_issues:
            return {
                "updated": False,
                "skipReason": "proof_anchor_target_mismatch",
                "issues": target_issues,
            }

        evidence = anchor.get("Evidence")
        if not isinstance(evidence, dict):
            return {
                "updated": False,
                "skipReason": "proof_anchor_evidence_missing",
            }

        candidate_file = self._proof_pose_candidate_file()
        candidate_id = evidence.get("CandidateId")
        candidate_address = evidence.get("CandidateAddressHex") or anchor.get("ObjectBaseAddress")
        if not candidate_file or not candidate_id or not candidate_address:
            return {
                "updated": False,
                "skipReason": "candidate_source_unavailable",
            }
        candidate_record = self._candidate_record_from_candidate_file(candidate_file, candidate_id)
        candidate_source_base = self._first_mapping_value(
            candidate_record or {},
            "base_address_hex",
            "source_base_address_hex",
            "region_id",
        ) or evidence.get("RegionAddressHex") or anchor.get("CoordRegionAddress") or candidate_address
        candidate_absolute = self._first_mapping_value(
            candidate_record or {},
            "absolute_address_hex",
            "source_absolute_address_hex",
        ) or candidate_address
        candidate_offset = self._first_mapping_value(
            candidate_record or {},
            "offset_hex",
            "source_offset_hex",
        )
        offset_int = self._coerce_int(candidate_offset)
        if offset_int is None:
            offset_int = self._coerce_int(evidence.get("CandidateOffsetInRegion"))
        if offset_int is None:
            base_int = self._coerce_int(candidate_source_base)
            absolute_int = self._coerce_int(candidate_absolute)
            if base_int is not None and absolute_int is not None and absolute_int >= base_int:
                offset_int = absolute_int - base_int
        candidate_offset_hex = f"0x{offset_int:X}" if offset_int is not None else "0x0"
        candidate_support = self._coerce_int(
            self._first_mapping_value(
                candidate_record or {},
                "support_count",
                "snapshot_support",
                "observation_support_count",
            )
        )
        if candidate_support is None:
            candidate_support = self._coerce_int(evidence.get("PoseCount")) or 1
        candidate_best_distance = self._first_mapping_value(
            candidate_record or {},
            "best_max_abs_distance",
            "bestMaxAbsDistance",
        )

        readback_summary_file = self._get(final_json, "SummaryFile") if final_json else None
        pointer_file = self._current_proof_pointer_file()
        pointer_file.parent.mkdir(parents=True, exist_ok=True)
        existing_pointer = self._load_json_object(pointer_file)
        archived_pointer = self._archive_existing_current_pointer_if_target_changed(
            pointer_file,
            existing_pointer,
        )
        payload = {
            "schemaVersion": 1,
            "mode": "current-proof-anchor-readback-pointer",
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": datetime.now(timezone.utc).isoformat(),
            "target": {
                "processName": self._process_name(),
                "processId": self.process_id,
                "targetWindowHandle": self.target_window_handle,
            },
            "currentTruthClassification": {
                "classification": "current-live-target-proof-anchor",
                "sourceOfTruth": "scripts/captures/telemetry-proof-coord-anchor.json plus latest ProofOnly readback",
                "staleProtection": (
                    "This pointer is updated only from same-PID/HWND ProofOnly success; "
                    "mismatched PID/HWND artifacts are historical-only."
                ),
                "savedVariablesUsedAsLiveTruth": False,
                "noCheatEngine": True,
            },
            "riftscanCandidateSource": {
                "sourceKind": "current-proof-anchor-candidate-file",
                "compatibilityNote": (
                    "Field name is retained for existing pointer consumers; the candidate file may be "
                    "RiftReader-owned evidence and must still be gated by current proof-anchor/readback."
                ),
                "riftScanRoot": None,
                "matchFile": str(candidate_file),
                "candidateId": str(candidate_id),
                "sourceBaseAddressHex": str(candidate_source_base),
                "sourceOffsetHex": candidate_offset_hex,
                "sourceAbsoluteAddressHex": str(candidate_absolute),
                "axisOrder": str(
                    self._first_mapping_value(candidate_record or {}, "axis_order", "axisOrder")
                    or "xyz"
                ),
                "supportCount": int(candidate_support),
                "proofSupportCount": int(self._coerce_int(evidence.get("PoseCount")) or 1),
                "bestMaxAbsDistance": (
                    candidate_best_distance
                    if candidate_best_distance is not None
                    else self._get(self._get(anchor, "Match"), "MaxDeltaError")
                ),
                "promotedByProofAnchor": True,
                "proofAnchorFile": str(self._proof_anchor_path()),
                "notes": [
                    "Candidate evidence is movement-grade only through same-PID/HWND proof-anchor/readback gates.",
                    "Do not treat this pointer as valid after a client restart unless target metadata still matches.",
                ],
            },
            "latestValidation": {
                "status": self._get(final_json, "Status") if final_json else None,
                "movementAllowed": self._get(final_json, "MovementAllowed") if final_json else None,
                "movementSent": False,
                "noCheatEngine": True,
                "readbackSummaryFile": readback_summary_file,
                "proofAnchorFile": str(self._proof_anchor_path()),
                "proofAnchorCandidateId": str(candidate_id),
                "proofAnchorCandidateAddressHex": str(candidate_address),
                "currentCoordinate": self._coordinate(self._get(final_json, "CurrentCoordinate")),
                "generatedAtUtc": self._get(final_json, "GeneratedAtUtc") if final_json else None,
            },
            "latestProofOnly": {
                "runSummaryFile": str(self.run_dir / "run-summary.json"),
                "status": status,
                "generatedAtUtc": summary.get("generatedAtUtc"),
                "movementSent": False,
                "movementAttempted": False,
                "currentCoordinate": summary.get("currentCoordinate"),
                "coordinateDelta": None,
                "readbackSummaryFile": readback_summary_file,
            },
            "runtimePointers": {
                "latestRuntimePointer": str(self.latest_pointer_file),
                "proofCoordAnchorCacheFile": str(self._proof_anchor_path()),
            },
            "notes": [
                "Auto-written after ProofOnly passed for the exact current target.",
                "This file is a current pointer, not an immutable historical record.",
            ],
        }
        if archived_pointer:
            payload["historicalSupersededPointer"] = archived_pointer
        elif isinstance(existing_pointer, dict) and isinstance(
            existing_pointer.get("historicalSupersededPointer"),
            dict,
        ):
            payload["historicalSupersededPointer"] = existing_pointer["historicalSupersededPointer"]

        if isinstance(existing_pointer, dict) and self._pointer_target_matches_current(existing_pointer):
            for name in (
                "latestForward250",
                "latestForwardSeries3x250",
                "latestDefaultPointerProofPose",
            ):
                if name in existing_pointer:
                    payload[name] = existing_pointer[name]
        write_json(pointer_file, payload)
        return {
            "updated": True,
            "path": str(pointer_file),
            "archivedSupersededPointer": archived_pointer,
        }

    @staticmethod
    def _load_json_object(path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001 - missing/unreadable pointer should not block a fresh proof.
            return None
        return data if isinstance(data, dict) else None

    def _pointer_target_matches_current(self, pointer: dict[str, Any]) -> bool:
        target = pointer.get("target") if isinstance(pointer.get("target"), dict) else {}
        if not isinstance(target, dict):
            return False
        pointer_pid = self._coerce_int(
            self._first_mapping_value(target, "processId", "ProcessId", "pid")
        )
        pointer_hwnd = self._coerce_int(
            self._first_mapping_value(target, "targetWindowHandle", "TargetWindowHandle", "hwnd")
        )
        expected_hwnd = self._coerce_int(self.target_window_handle)
        return (
            pointer_pid == int(self.process_id)
            and pointer_hwnd is not None
            and expected_hwnd is not None
            and pointer_hwnd == expected_hwnd
        )

    def _archive_existing_current_pointer_if_target_changed(
        self,
        pointer_file: Path,
        existing_pointer: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(existing_pointer, dict) or self._pointer_target_matches_current(existing_pointer):
            return None
        target = existing_pointer.get("target") if isinstance(existing_pointer.get("target"), dict) else {}
        old_pid = self._coerce_int(
            self._first_mapping_value(target, "processId", "ProcessId", "pid")
        )
        old_hwnd = self._coerce_int(
            self._first_mapping_value(target, "targetWindowHandle", "TargetWindowHandle", "hwnd")
        )
        pid_segment = str(old_pid) if old_pid is not None else "unknown"
        hwnd_segment = f"{old_hwnd:X}" if old_hwnd is not None else "unknown"
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        archive_file = (
            pointer_file.parent
            / "historical"
            / f"current-proof-anchor-readback-{stamp}-pid{pid_segment}-hwnd{hwnd_segment}-historical.json"
        )
        archive_file.parent.mkdir(parents=True, exist_ok=True)
        if not archive_file.exists():
            archive_payload = dict(existing_pointer)
            archive_payload["historicalClassification"] = {
                "classification": "historical-target-epoch-evidence",
                "archivedAtUtc": datetime.now(timezone.utc).isoformat(),
                "supersededBy": {
                    "processName": self._process_name(),
                    "processId": self.process_id,
                    "targetWindowHandle": self.target_window_handle,
                },
                "reusePolicy": "do-not-use-as-current-proof; preserve for audit/reacquire hints only",
            }
            write_json(archive_file, archive_payload)
        return {
            "path": str(archive_file),
            "classification": "historical-target-epoch-evidence",
            "supersededTarget": {
                "processName": self._first_mapping_value(target, "processName", "ProcessName"),
                "processId": old_pid,
                "targetWindowHandle": f"0x{old_hwnd:X}" if old_hwnd is not None else None,
            },
            "reusePolicy": "do-not-use-as-current-proof; preserve for audit/reacquire hints only",
        }

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
        if self.current_proof_pointer_update:
            snapshot["currentProofPointerUpdate"] = self.current_proof_pointer_update
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
                "currentProofPointerUpdate": self.current_proof_pointer_update,
            "targetControl": self.target_control_summary,
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
            "minimumMovementPlanarDistance": self._minimum_movement_planar_distance(),
            "inputBackend": self.profile.get("inputBackend", "window-message"),
            "candidateId": self._candidate_id(),
            "candidateIdSource": self.profile.get("candidateIdSource", "current-proof-pointer"),
            "maxAutoRefreshAttempts": int(self.profile.get("maxAutoRefreshAttempts", 0)),
            "autoRefreshAttemptsUsed": self.auto_refresh_attempts_used,
            "updateLatestPointer": bool(self.profile.get("updateLatestPointer", True)),
            "updateLatestPointerForExternalOutputRoot": bool(
                self.profile.get("updateLatestPointerForExternalOutputRoot", False)
            ),
            "noCheatEngine": True,
            "savedVariablesLiveTruthAllowed": False,
        }

    def _minimum_movement_planar_distance(self) -> float:
        try:
            return max(0.0, float(self.profile.get("minimumMovementPlanarDistance", 0.0)))
        except (TypeError, ValueError):
            return 0.0

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
