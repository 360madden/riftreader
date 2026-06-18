#!/usr/bin/env python3
"""Stage 45 plan-only debugger/Cheat Engine helper.

This module intentionally does not launch x64dbg, start Cheat Engine, attach to
the RIFT process, set breakpoints/watchpoints, scan target memory, send live game
input, promote truth, or write provider repos. It only classifies debugger/CE
requests and writes bounded operator plans under ignored ``.riftreader-local``
artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from . import live_rift_state
    from .common import repo_rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    from riftreader_workflow import live_rift_state
    from riftreader_workflow.common import repo_rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
PLAN_ROOT_REL = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "debugger-ce-plans"
DEFAULT_MAX_DURATION_SECONDS = 120
ABSOLUTE_MAX_DURATION_SECONDS = 300
APPROVAL_EXPIRATION_MINUTES = 10

STATIC_HINTS = {"static", "static-review", "offline", "offline-review", "source-review", "disassembly-review"}
ARTIFACT_HINTS = {"artifact", "artifact-review", "evidence-review", "readback-review", "proof-artifact-review"}
CANDIDATE_HINTS = {"candidate", "candidate-triage", "candidate-review", "chain-triage", "pointer-triage"}
X64DBG_HINTS = {"x64dbg", "debugger", "debugger-attach", "attach-debugger", "breakpoint", "watchpoint"}
CE_HINTS = {"ce", "cheat-engine", "cheatengine", "ce-attach", "attach-ce", "scan", "memory-scan"}
PROMOTION_HINTS = {"promote", "promotion", "current-truth", "truth-update", "proof-promotion"}
MEMORY_WRITE_HINTS = {"write-memory", "patch-memory", "poke", "nop", "inject", "modify-memory"}


def _canonical(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _contains_any(text: str, hints: set[str]) -> bool:
    if not text:
        return False
    normalized = f"-{text}-"
    return any(f"-{hint}-" in normalized or text == hint for hint in hints)


def debugger_ce_safety_flags() -> dict[str, Any]:
    """Return the shared Stage 45 no-input/no-attach safety state."""

    return {
        **safety_flags(),
        "planOnly": True,
        "dryRun": True,
        "artifactWritten": True,
        "approvalTokenGenerated": False,
        "reusableApprovalTokenCreated": False,
        "keysReleased": None,
        "focusSent": False,
        "clickSent": False,
        "windowCaptureSent": False,
        "proofOnlyExecuted": False,
        "proofPromotion": False,
        "currentTruthUpdated": False,
        "debuggerLaunched": False,
        "debuggerAttached": False,
        "cheatEngineLaunched": False,
        "cheatEngineConnected": False,
        "breakpointsSet": False,
        "watchpointsSet": False,
        "targetMemoryBytesRead": False,
        "targetMemoryBytesWritten": False,
        "targetMemoryScanned": False,
        "truthPromotionPerformed": False,
        "arbitraryFilesystemRead": False,
        "arbitraryFilesystemWrite": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "providerWrites": False,
        "savedVariablesUsedAsLiveTruth": False,
        "canExecuteDebuggerAttach": False,
    }


def classify_debugger_ce_action(
    *,
    action_kind: str | None = None,
    target_tool: str | None = None,
    requested_action: str | None = None,
) -> dict[str, Any]:
    """Classify a debugger/CE request without executing it."""

    combined = "-".join(
        part for part in (_canonical(action_kind), _canonical(target_tool), _canonical(requested_action)) if part
    )
    blockers: list[str] = []
    warnings: list[str] = []
    risk_class = "blocked"
    semantic_action = combined or "unspecified"
    requires_approval = True
    blocked_by_default = True
    primitive_tool = "none"
    recommended_verification = [
        "review-static-first-checklist",
        "confirm-no-debugger-or-ce-attach",
        "preserve-candidate-only-status",
    ]

    if not combined:
        blockers.append("DEBUGGER_ACTION_MISSING")
    elif _contains_any(combined, PROMOTION_HINTS):
        blockers.append("DEBUGGER_PROMOTION_FORBIDDEN")
        risk_class = "blocked"
        semantic_action = "truth-promotion-request"
        primitive_tool = "none"
    elif _contains_any(combined, MEMORY_WRITE_HINTS):
        blockers.append("DEBUGGER_TARGET_MEMORY_WRITE_FORBIDDEN")
        risk_class = "blocked"
        semantic_action = "target-memory-write-request"
        primitive_tool = "none"
    elif _contains_any(combined, CE_HINTS):
        risk_class = "ce-attach-plan"
        semantic_action = "cheat-engine-plan"
        primitive_tool = "none-stage-45-plan-only"
        recommended_verification.extend(["exact-target-binding-before-future-ce", "crash-risk-ack-required"])
    elif _contains_any(combined, X64DBG_HINTS):
        risk_class = "debugger-attach-plan"
        semantic_action = "x64dbg-debugger-plan"
        primitive_tool = "none-stage-45-plan-only"
        recommended_verification.extend(["exact-target-binding-before-future-debugger", "crash-risk-ack-required"])
    elif _contains_any(combined, CANDIDATE_HINTS):
        risk_class = "candidate-triage"
        semantic_action = "candidate-evidence-review"
        primitive_tool = "tracked-and-ignored-artifact-review"
        requires_approval = False
        blocked_by_default = False
        recommended_verification.append("candidate-only-no-promotion")
    elif _contains_any(combined, ARTIFACT_HINTS):
        risk_class = "artifact-review"
        semantic_action = "artifact-review"
        primitive_tool = "repo-owned-artifact-review"
        requires_approval = False
        blocked_by_default = False
        recommended_verification.append("repo-owned-artifact-path-only")
    elif _contains_any(combined, STATIC_HINTS):
        risk_class = "static-review"
        semantic_action = "static-first-review"
        primitive_tool = "tracked-source-or-offline-static-review"
        requires_approval = False
        blocked_by_default = False
        recommended_verification.append("offline-evidence-before-attach")
    else:
        warnings.append("DEBUGGER_ACTION_UNRECOGNIZED_DEFAULTING_TO_STATIC_REVIEW")
        risk_class = "static-review"
        semantic_action = semantic_action or "static-first-review"
        primitive_tool = "tracked-source-or-offline-static-review"
        requires_approval = False
        blocked_by_default = False

    ok = not blockers
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-debugger-ce-action-classification",
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "riskClass": risk_class,
        "movementRisk": False,
        "requiresApproval": requires_approval,
        "blockedByDefault": blocked_by_default,
        "semanticAction": semantic_action,
        "primitiveTool": primitive_tool,
        "recommendedVerification": recommended_verification,
        "blockers": blockers,
        "warnings": warnings,
        "safety": debugger_ce_safety_flags(),
    }


def _target_identity_mismatches(expected: dict[str, Any] | None, supplied: dict[str, Any] | None) -> list[str]:
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
            mismatches.append(f"DEBUGGER_TARGET_MISMATCH:{field}")
    return mismatches


def _write_plan_artifacts(repo_root: Path, plan_id: str, payload: dict[str, Any]) -> dict[str, str]:
    plan_root = (repo_root / PLAN_ROOT_REL).resolve()
    local_root = (repo_root / ".riftreader-local").resolve()
    plan_dir = (plan_root / plan_id).resolve()
    plan_dir.relative_to(local_root)
    plan_dir.mkdir(parents=True, exist_ok=False)
    json_path = plan_dir / "plan.json"
    md_path = plan_dir / "plan.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    approval = payload.get("approvalPacket") if isinstance(payload.get("approvalPacket"), dict) else {}
    target = payload.get("targetBinding") if isinstance(payload.get("targetBinding"), dict) else {}
    md_path.write_text(
        "\n".join(
            [
                f"# Debugger/CE plan {plan_id}",
                "",
                f"- Status: `{payload.get('status')}`",
                f"- Risk: `{payload.get('riskClass')}`",
                f"- Semantic action: `{payload.get('classification', {}).get('semanticAction')}`",
                f"- Target gate: `{target.get('identityGateStatus')}`",
                f"- Approval scope: `{approval.get('requiredApprovalScope')}`",
                "",
                "## Human approval prompt",
                "",
                str(approval.get("humanPrompt") or "No approval prompt generated."),
                "",
                "This artifact is plan-only. It does not attach x64dbg, start Cheat Engine, set breakpoints/watchpoints, read/write target memory, send input, or create a reusable approval token.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "planPath": repo_rel(repo_root, json_path),
        "planMarkdownPath": repo_rel(repo_root, md_path),
    }


def build_debugger_ce_plan(
    repo_root: Path,
    *,
    action_kind: str | None = None,
    target_tool: str | None = None,
    requested_action: str | None = None,
    question: str | None = None,
    target_identity: dict[str, Any] | None = None,
    static_evidence: dict[str, Any] | None = None,
    candidate_evidence: dict[str, Any] | None = None,
    max_duration_seconds: Any = None,
    stop_condition: str | None = None,
    crash_risk_acknowledged: bool = False,
    static_first_reviewed: bool = False,
    dry_run: bool = True,
    discovery_payload: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a Stage 45 debugger/CE dry-run plan without attach or live input."""

    repo_root = repo_root.resolve()
    generated_at = utc_iso()
    now_utc = now or datetime.now(timezone.utc)
    expires_at = (now_utc.astimezone(timezone.utc) + timedelta(minutes=APPROVAL_EXPIRATION_MINUTES)).isoformat().replace(
        "+00:00", "Z"
    )
    classification = classify_debugger_ce_action(
        action_kind=action_kind,
        target_tool=target_tool,
        requested_action=requested_action,
    )
    risk_class = str(classification.get("riskClass") or "blocked")
    attach_plan = risk_class in {"debugger-attach-plan", "ce-attach-plan"}
    blockers = list(classification.get("blockers") or [])
    warnings = list(classification.get("warnings") or [])
    requested_duration = _safe_int(max_duration_seconds, default=DEFAULT_MAX_DURATION_SECONDS)
    max_duration = min(max(0, requested_duration), ABSOLUTE_MAX_DURATION_SECONDS)
    if requested_duration != max_duration:
        warnings.append(f"maxDurationSeconds-clamped:{requested_duration}->{max_duration}")
    if dry_run is not True:
        blockers.append("DEBUGGER_PLAN_DRY_RUN_REQUIRED")
    if not (question or requested_action or action_kind):
        blockers.append("DEBUGGER_QUESTION_OR_INTENT_MISSING")

    gate: dict[str, Any] | None = None
    exact_target: dict[str, Any] | None = None
    target_binding: dict[str, Any]
    if attach_plan or target_identity:
        gate = live_rift_state.build_live_target_identity_gate(
            repo_root,
            discovery_payload=discovery_payload,
            now=now_utc,
        )
        gate_blockers = [str(item) for item in gate.get("blockers") or []]
        if not gate.get("ok"):
            blockers.extend(f"DEBUGGER_TARGET_GATE:{item}" for item in gate_blockers)
        exact_target = gate.get("exactTargetFacts") if isinstance(gate.get("exactTargetFacts"), dict) else None
        blockers.extend(_target_identity_mismatches(exact_target, target_identity))
        target_binding = {
            "identityGateStatus": gate.get("status"),
            "identityGateOk": bool(gate.get("ok")),
            "exactTargetFacts": exact_target,
            "requestedTarget": gate.get("requestedTarget"),
            "freshness": gate.get("freshness"),
            "operatorSuppliedTargetIdentity": target_identity or {},
        }
    else:
        target_binding = {
            "identityGateStatus": "not-required-for-static-or-artifact-plan",
            "identityGateOk": None,
            "exactTargetFacts": None,
            "requestedTarget": None,
            "freshness": None,
            "operatorSuppliedTargetIdentity": target_identity or {},
        }

    if attach_plan:
        if not static_first_reviewed:
            blockers.append("DEBUGGER_STATIC_FIRST_REQUIRED")
        if not crash_risk_acknowledged:
            blockers.append("DEBUGGER_CRASH_RISK_NOT_ACKNOWLEDGED")
        if max_duration <= 0 or not stop_condition:
            blockers.append("DEBUGGER_STOP_CONDITION_MISSING")
        if not exact_target:
            blockers.append("DEBUGGER_TARGET_NOT_BOUND")
    elif static_first_reviewed is False and risk_class in {"candidate-triage", "artifact-review"}:
        warnings.append("static-first-review-not-marked-complete")

    requested_plan = {
        "actionKind": action_kind,
        "targetTool": target_tool,
        "requestedAction": requested_action,
        "question": question,
        "semanticAction": classification.get("semanticAction"),
        "primitiveTool": classification.get("primitiveTool"),
        "maxDurationSeconds": max_duration,
        "stopCondition": stop_condition or "return-plan-only-before-any-attach",
        "crashRiskAcknowledged": bool(crash_risk_acknowledged),
        "staticFirstReviewed": bool(static_first_reviewed),
        "dryRun": True,
    }
    static_first_checklist = [
        {
            "key": "tracked-source-reviewed",
            "requiredBeforeAttach": True,
            "status": "operator-asserted-reviewed" if static_first_reviewed else "pending-or-not-provided",
        },
        {
            "key": "offline-static-evidence-reviewed",
            "requiredBeforeAttach": True,
            "status": "evidence-provided" if static_evidence else "not-provided",
        },
        {
            "key": "candidate-evidence-remains-candidate-only",
            "requiredBeforeAttach": True,
            "status": "evidence-provided" if candidate_evidence else "not-provided",
        },
        {
            "key": "no-proof-or-current-truth-promotion",
            "requiredBeforeAttach": True,
            "status": "enforced-by-stage-45-plan-only",
        },
    ]
    hash_input = {
        "schemaVersion": SCHEMA_VERSION,
        "stage": 45,
        "classification": {
            key: classification.get(key)
            for key in ("riskClass", "movementRisk", "semanticAction", "primitiveTool", "requiresApproval")
        },
        "targetBinding": target_binding,
        "requestedPlan": requested_plan,
        "expiresAtUtc": expires_at,
    }
    plan_hash = hashlib.sha256(json.dumps(hash_input, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    plan_id = f"{generated_at.replace('-', '').replace(':', '').replace('Z', 'Z')}-{plan_hash[:12]}"
    required_scope = "none-static-or-artifact-plan" if not classification.get("requiresApproval") else f"current-turn-{risk_class}-approval"
    pid = (exact_target or {}).get("processId")
    hwnd = (exact_target or {}).get("targetWindowHandle")
    human_prompt = (
        "Plan-only output: no debugger/CE action was taken. If a future separately approved execution tool exists "
        f"and all gates still pass, approve exactly this plan by saying: APPROVE DEBUGGER CE {risk_class} PLAN "
        f"{plan_hash[:16]} FOR PID {pid} HWND {hwnd} DURATION <= {max_duration}S. "
        f"This is not reusable and expires at {expires_at}."
    )
    execution_blockers = [
        "DEBUGGER_STAGE45_PLAN_ONLY_NO_EXECUTION_TOOL",
        "DEBUGGER_BACKEND_UNAVAILABLE",
        "DEBUGGER_APPROVAL_REQUIRED_BEFORE_ATTACH",
        "DEBUGGER_ATTACH_REQUIRES_SEPARATE_CURRENT_TURN_APPROVAL",
        "DEBUGGER_PROMOTION_FORBIDDEN",
    ]
    if attach_plan:
        execution_blockers.extend(
            [
                "DEBUGGER_CRASH_RISK_ACK_REQUIRED_FOR_FUTURE_EXECUTION",
                "DEBUGGER_STATIC_FIRST_REQUIRED_FOR_FUTURE_EXECUTION",
            ]
        )
    ok = not blockers
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-debugger-ce-plan",
        "generatedAtUtc": generated_at,
        "status": "planned" if ok else "blocked",
        "ok": ok,
        "stage": 45,
        "stageName": "Debugger/CE plan-only surface",
        "planId": plan_id,
        "planHash": plan_hash,
        "riskClass": risk_class,
        "movementRisk": False,
        "classification": classification,
        "targetBinding": target_binding,
        "staticFirstChecklist": static_first_checklist,
        "requestedAction": requested_plan,
        "evidenceSummary": {
            "staticEvidenceProvided": bool(static_evidence),
            "candidateEvidenceProvided": bool(candidate_evidence),
            "staticEvidenceKeys": sorted(str(key) for key in (static_evidence or {}).keys())[:20],
            "candidateEvidenceKeys": sorted(str(key) for key in (candidate_evidence or {}).keys())[:20],
            "candidateOnly": True,
        },
        "approvalPacket": {
            "requiredApprovalScope": required_scope,
            "approvalPhraseFingerprint": plan_hash[:16],
            "expiresAtUtc": expires_at,
            "humanPrompt": human_prompt,
            "reusableBroadApprovalToken": None,
            "mustNotExecuteFromThisTool": True,
        },
        "executionReadiness": {
            "canExecuteFromThisTool": False,
            "futureExecutionToolRequired": bool(classification.get("requiresApproval")),
            "executionBlockers": execution_blockers,
        },
        "recommendedVerification": classification.get("recommendedVerification"),
        "blockers": blockers,
        "warnings": warnings,
        "safety": debugger_ce_safety_flags(),
    }
    artifact_paths = _write_plan_artifacts(repo_root, plan_id, payload)
    payload["artifact"] = {
        **artifact_paths,
        "underIgnoredDotRiftReaderLocal": True,
    }
    json_path = repo_root / artifact_paths["planPath"]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload
