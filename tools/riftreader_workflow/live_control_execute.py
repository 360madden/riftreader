#!/usr/bin/env python3
"""Stage 43 fail-closed live RIFT control execution-boundary helper.

This module exposes the approval-bound boundary for a future exact-target live
control action, but it does not focus the game window, capture frames, send
keys, click, run ProofOnly, promote truth, attach debuggers, or write provider
repos. It writes only ignored run/audit artifacts under ``.riftreader-local``
and fails closed before input when the live input backend is unavailable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from . import live_control_plan, live_rift_state
    from .common import repo_rel, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    from riftreader_workflow import live_control_plan, live_rift_state
    from riftreader_workflow.common import repo_rel, utc_iso


SCHEMA_VERSION = 1
RUN_ROOT_REL = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "live-control-runs"
STAGE = 43
STAGE_NAME = "Expose minimal live action tool"


def _safety(*, dry_run: bool, artifact_written: bool = True, **overrides: Any) -> dict[str, Any]:
    safety = {
        **live_rift_state.live_safety_flags(),
        "executionBoundary": True,
        "dryRun": dry_run,
        "artifactWritten": artifact_written,
        "approvalTokenGenerated": False,
        "reusableApprovalTokenCreated": False,
        "focusSent": False,
        "clickSent": False,
        "windowCaptureSent": False,
        "inputSent": False,
        "movementSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "keysReleased": None,
        "targetMemoryBytesRead": False,
        "targetMemoryBytesWritten": False,
        "truthPromotionPerformed": False,
        "providerWrites": False,
        "x64dbgAttach": False,
        "noCheatEngine": True,
        "savedVariablesUsedAsLiveTruth": False,
        "routeControlAuthorized": False,
        "canExecuteLiveNavigation": False,
        "liveInputBackendCalled": False,
        "liveInputBackendAvailable": False,
    }
    safety.update(overrides)
    return safety


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _safe_plan_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or any(part in text for part in ("/", "\\", "..")):
        return None
    return text


def _resolve_plan_path(repo_root: Path, *, plan_id: str | None, plan_path: str | None) -> tuple[Path | None, list[str]]:
    blockers: list[str] = []
    local_root = (repo_root / ".riftreader-local").resolve()
    plan_root = (repo_root / live_control_plan.PLAN_ROOT_REL).resolve()

    if plan_id:
        safe_id = _safe_plan_id(plan_id)
        if safe_id is None:
            blockers.append("LIVE_PLAN_ID_INVALID")
            return None, blockers
        resolved = (plan_root / safe_id / "plan.json").resolve()
    elif plan_path:
        raw = Path(str(plan_path))
        if raw.is_absolute():
            blockers.append("LIVE_PLAN_PATH_ABSOLUTE_FORBIDDEN")
            return None, blockers
        resolved = (repo_root / raw).resolve()
    else:
        blockers.append("LIVE_PLAN_REQUIRED")
        return None, blockers

    try:
        resolved.relative_to(plan_root)
        resolved.relative_to(local_root)
    except ValueError:
        blockers.append("LIVE_PLAN_PATH_OUTSIDE_ALLOWED_ROOT")
        return None, blockers
    if resolved.name != "plan.json":
        blockers.append("LIVE_PLAN_FILE_NAME_INVALID")
    return resolved, blockers


def _load_plan(repo_root: Path, *, plan_id: str | None, plan_path: str | None) -> tuple[dict[str, Any] | None, Path | None, list[str]]:
    resolved, blockers = _resolve_plan_path(repo_root, plan_id=plan_id, plan_path=plan_path)
    if blockers or resolved is None:
        return None, resolved, blockers
    if not resolved.is_file():
        return None, resolved, ["LIVE_PLAN_NOT_FOUND"]
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, resolved, ["LIVE_PLAN_JSON_INVALID"]
    if not isinstance(payload, dict):
        return None, resolved, ["LIVE_PLAN_JSON_NOT_OBJECT"]
    if payload.get("kind") != "riftreader-chatgpt-mcp-live-control-plan" or payload.get("stage") != 42:
        return payload, resolved, ["LIVE_PLAN_KIND_OR_STAGE_INVALID"]
    return payload, resolved, []


def _target_identity_mismatches(expected: dict[str, Any] | None, supplied: dict[str, Any] | None, *, prefix: str) -> list[str]:
    if not expected or not supplied:
        return []
    comparisons = {
        "processId": (expected.get("processId"), supplied.get("processId", supplied.get("pid"))),
        "targetWindowHandle": (
            expected.get("targetWindowHandle"),
            supplied.get("targetWindowHandle", supplied.get("hwnd")),
        ),
        "processStartTime": (expected.get("processStartTime"), supplied.get("processStartTime")),
        "moduleBase": (expected.get("moduleBase"), supplied.get("moduleBase")),
    }
    mismatches: list[str] = []
    for field, (actual, claimed) in comparisons.items():
        if claimed in (None, ""):
            continue
        if str(actual) != str(claimed):
            mismatches.append(f"{prefix}:{field}")
    return mismatches


def _approval_phrase_for_plan(plan: dict[str, Any]) -> str:
    plan_hash = str(plan.get("planHash") or "")
    target_binding = plan.get("targetBinding") if isinstance(plan.get("targetBinding"), dict) else {}
    exact_target = target_binding.get("exactTargetFacts") if isinstance(target_binding.get("exactTargetFacts"), dict) else {}
    requested_action = plan.get("requestedAction") if isinstance(plan.get("requestedAction"), dict) else {}
    return (
        f"APPROVE LIVE RIFT {plan.get('riskClass')} PLAN {plan_hash[:16]} "
        f"FOR PID {exact_target.get('processId')} HWND {exact_target.get('targetWindowHandle')} "
        f"HOLD <= {requested_action.get('holdMilliseconds')}MS"
    )


def _write_run_artifacts(repo_root: Path, run_id: str, payload: dict[str, Any]) -> dict[str, str]:
    run_root = (repo_root / RUN_ROOT_REL).resolve()
    local_root = (repo_root / ".riftreader-local").resolve()
    run_dir = (run_root / run_id).resolve()
    run_dir.relative_to(local_root)
    run_dir.mkdir(parents=True, exist_ok=False)
    json_path = run_dir / "run.json"
    md_path = run_dir / "run.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    md_path.write_text(
        "\n".join(
            [
                f"# Live control execution boundary {run_id}",
                "",
                f"- Status: `{payload.get('status')}`",
                f"- Dry run: `{payload.get('dryRun')}`",
                f"- Action: `{payload.get('semanticAction')}`",
                f"- Risk: `{payload.get('riskClass')}`",
                f"- Movement risk: `{payload.get('movementRisk')}`",
                f"- Input sent: `{payload.get('safety', {}).get('inputSent')}`",
                f"- Movement sent: `{payload.get('safety', {}).get('movementSent')}`",
                "",
                "## One-shot approval phrase",
                "",
                str(approval.get("expectedApprovalPhrase") or "No approval phrase available."),
                "",
                "This artifact is fail-closed before input in the current slice; it is not a reusable approval token.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {"runPath": repo_rel(repo_root, json_path), "runMarkdownPath": repo_rel(repo_root, md_path)}


def build_live_control_execution_boundary(
    repo_root: Path,
    *,
    plan_id: str | None = None,
    plan_path: str | None = None,
    approval_phrase: str | None = None,
    target_identity: dict[str, Any] | None = None,
    dry_run: bool = True,
    allow_movement_risk: bool = False,
    discovery_payload: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a Stage 43 live-control execution request without sending input."""

    repo_root = repo_root.resolve()
    generated_at = utc_iso()
    now_utc = now or datetime.now(timezone.utc)
    blockers: list[str] = []
    warnings: list[str] = []
    plan, resolved_plan_path, plan_blockers = _load_plan(repo_root, plan_id=plan_id, plan_path=plan_path)
    blockers.extend(plan_blockers)

    plan_hash = str((plan or {}).get("planHash") or "")
    run_hash_input = {
        "stage": STAGE,
        "generatedAtUtc": generated_at,
        "planId": (plan or {}).get("planId") or plan_id,
        "planHash": plan_hash,
        "dryRun": dry_run,
        "targetIdentity": target_identity or {},
    }
    run_hash = hashlib.sha256(json.dumps(run_hash_input, sort_keys=True, default=str).encode()).hexdigest()
    run_id = f"{generated_at.replace('-', '').replace(':', '').replace('Z', 'Z')}-{run_hash[:12]}"

    classification = (plan or {}).get("classification") if isinstance((plan or {}).get("classification"), dict) else {}
    target_binding = (plan or {}).get("targetBinding") if isinstance((plan or {}).get("targetBinding"), dict) else {}
    requested_action = (plan or {}).get("requestedAction") if isinstance((plan or {}).get("requestedAction"), dict) else {}
    approval_packet = (plan or {}).get("approvalPacket") if isinstance((plan or {}).get("approvalPacket"), dict) else {}
    exact_target = target_binding.get("exactTargetFacts") if isinstance(target_binding.get("exactTargetFacts"), dict) else None
    expected_approval_phrase = _approval_phrase_for_plan(plan or {}) if plan else None

    if plan and not plan.get("ok"):
        blockers.append("LIVE_PLAN_NOT_OK")
    if plan and requested_action.get("stopCondition") in (None, ""):
        blockers.append("LIVE_STOP_CONDITION_MISSING")
    expires_at = _parse_utc(approval_packet.get("expiresAtUtc")) if approval_packet else None
    if plan and expires_at is None:
        blockers.append("LIVE_APPROVAL_EXPIRATION_MISSING")
    elif expires_at is not None and now_utc.astimezone(timezone.utc) > expires_at:
        blockers.append("LIVE_APPROVAL_EXPIRED")

    gate = live_rift_state.build_live_target_identity_gate(repo_root, discovery_payload=discovery_payload, now=now_utc)
    gate_blockers = [str(item) for item in gate.get("blockers") or []]
    if not gate.get("ok"):
        blockers.extend(f"LIVE_TARGET_GATE_BLOCKED:{item}" for item in gate_blockers)
    current_target = gate.get("exactTargetFacts") if isinstance(gate.get("exactTargetFacts"), dict) else None
    blockers.extend(_target_identity_mismatches(exact_target, current_target, prefix="LIVE_TARGET_DRIFT"))
    blockers.extend(_target_identity_mismatches(exact_target, target_identity, prefix="LIVE_TARGET_REQUEST_MISMATCH"))

    movement_risk = bool((plan or {}).get("movementRisk"))
    if movement_risk and not allow_movement_risk:
        blockers.append("LIVE_ROUTE_CONTROL_UNAUTHORIZED")

    approval_status = "not-required-for-dry-run" if dry_run else "required"
    if not dry_run:
        supplied = (approval_phrase or "").strip()
        if not supplied:
            blockers.append("LIVE_APPROVAL_MISSING")
            approval_status = "missing"
        elif supplied != expected_approval_phrase:
            blockers.append("LIVE_APPROVAL_MISMATCH")
            approval_status = "mismatch"
        else:
            approval_status = "matched"
        # Stage 43 currently exposes the boundary and audit contract only. Keep
        # the actual live-input backend disabled until a separately reviewed
        # local backend slice wires exact-target focus/capture/send/release/readback.
        blockers.append("LIVE_INPUT_BACKEND_UNAVAILABLE")

    unique_blockers = list(dict.fromkeys(blockers))
    status = "ready-for-approval" if dry_run and not unique_blockers else "blocked-before-input"
    ok = dry_run and not unique_blockers
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-live-control-execution-boundary",
        "generatedAtUtc": generated_at,
        "status": status,
        "ok": ok,
        "stage": STAGE,
        "stageName": STAGE_NAME,
        "dryRun": dry_run,
        "runId": run_id,
        "planId": (plan or {}).get("planId") or plan_id,
        "planPath": repo_rel(repo_root, resolved_plan_path) if resolved_plan_path else None,
        "planHash": plan_hash or None,
        "actionKind": (plan or {}).get("actionKind") or classification.get("actionKind"),
        "riskClass": (plan or {}).get("riskClass") or classification.get("riskClass"),
        "movementRisk": movement_risk,
        "semanticAction": classification.get("semanticAction") or requested_action.get("semanticAction"),
        "primitiveTool": classification.get("primitiveTool") or requested_action.get("primitiveTool"),
        "requestedAction": requested_action,
        "targetBinding": {
            "plannedExactTargetFacts": exact_target,
            "currentIdentityGateStatus": gate.get("status"),
            "currentIdentityGateOk": bool(gate.get("ok")),
            "currentExactTargetFacts": current_target,
            "operatorSuppliedTargetIdentity": target_identity or {},
        },
        "approval": {
            "status": approval_status,
            "requiredForLiveInput": True,
            "expectedApprovalPhrase": expected_approval_phrase,
            "approvalPhraseFingerprint": (plan_hash or "")[:16] or None,
            "reusableBroadApprovalToken": None,
            "expiresAtUtc": approval_packet.get("expiresAtUtc") if approval_packet else None,
            "suppliedApprovalMatched": approval_status == "matched",
        },
        "executionReadiness": {
            "canExecuteFromThisToolNow": False,
            "liveInputBackendAvailable": False,
            "futureBackendRequired": True,
            "blockedBeforeInput": True,
            "postActionReadbackRequiredBeforeTrust": True,
        },
        "recommendedVerification": [
            "get_live_target_identity_gate",
            "get_live_no_input_proof_status",
            "post-action-readback-required-before-trust",
        ],
        "blockers": unique_blockers,
        "warnings": warnings,
        "safety": _safety(dry_run=dry_run),
    }
    artifact_paths = _write_run_artifacts(repo_root, run_id, payload)
    payload["artifact"] = {**artifact_paths, "underIgnoredDotRiftReaderLocal": True}
    json_path = repo_root / artifact_paths["runPath"]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload
