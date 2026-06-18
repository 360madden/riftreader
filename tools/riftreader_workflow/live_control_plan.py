#!/usr/bin/env python3
"""Stage 42 plan-only live RIFT control helper.

This module intentionally does not focus the game window, capture frames, send
keys, click, run ProofOnly, promote truth, attach debuggers, or write provider
repos. It only reads the Stage 39 exact-target gate and writes a bounded
operator plan under ignored ``.riftreader-local`` artifacts.
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
    from .common import repo_rel, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    from riftreader_workflow import live_rift_state
    from riftreader_workflow.common import repo_rel, utc_iso


SCHEMA_VERSION = 1
PLAN_ROOT_REL = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "live-control-plans"
DEFAULT_MAX_HOLD_MILLISECONDS = 500
ABSOLUTE_MAX_HOLD_MILLISECONDS = 1500
APPROVAL_EXPIRATION_MINUTES = 10

MOVEMENT_KEY_ALIASES: dict[str, tuple[str, str]] = {
    "w": ("move-forward", "hold_key:W"),
    "arrowup": ("move-forward", "hold_key:ArrowUp"),
    "up": ("move-forward", "hold_key:ArrowUp"),
    "s": ("move-backward", "hold_key:S"),
    "arrowdown": ("move-backward", "hold_key:ArrowDown"),
    "down": ("move-backward", "hold_key:ArrowDown"),
    "a": ("strafe-left", "hold_key:A"),
    "arrowleft": ("turn-left", "hold_key:ArrowLeft"),
    "left": ("turn-left", "hold_key:ArrowLeft"),
    "d": ("strafe-right", "hold_key:D"),
    "arrowright": ("turn-right", "hold_key:ArrowRight"),
    "right": ("turn-right", "hold_key:ArrowRight"),
    "q": ("turn-left", "hold_key:Q"),
    "e": ("turn-right", "hold_key:E"),
    "space": ("jump", "press_key:Space"),
}
MOVEMENT_SEMANTIC_ALIASES = {
    "move-forward": "hold_key:W",
    "forward": "hold_key:W",
    "move-backward": "hold_key:S",
    "backward": "hold_key:S",
    "strafe-left": "hold_key:A",
    "strafe-right": "hold_key:D",
    "turn-left": "hold_key:Q",
    "turn-right": "hold_key:E",
    "jump": "press_key:Space",
}
DISPLACEMENT_HINTS = {"nudge", "stimulus", "displacement", "coordinate-proof-pulse", "proof-pulse"}
NO_INPUT_HINTS = {"inspect", "status", "read", "identity", "target", "readiness"}
PROOF_ONLY_HINTS = {"proof-only", "proofonly", "no-input-proof", "proof-status"}
UI_ACTION_HINTS = {"inventory", "open-inventory", "bag", "bags", "character", "map"}
HOTBAR_RE = re.compile(r"^(?:hotbar|press-hotbar|hotbar-slot|slot)[-_ ]?([0-9]|1[0-2])$")


def _canonical_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _canonical_action(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safety() -> dict[str, Any]:
    return {
        **live_rift_state.live_safety_flags(),
        "planOnly": True,
        "dryRun": True,
        "artifactWritten": True,
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
    }


def classify_action(*, action_kind: str | None, semantic_action: str | None, key_chord: str | None) -> dict[str, Any]:
    """Classify a requested action without executing it."""

    requested_action = _canonical_action(semantic_action)
    requested_kind = _canonical_action(action_kind)
    requested_key = _canonical_key(key_chord)
    warnings: list[str] = []
    blockers: list[str] = []
    primitive_tool = "none"
    semantic = requested_action or requested_kind or requested_key or "unspecified"
    action_kind_out = requested_kind or "unknown"
    risk_class = "unknown-action-risk"
    movement_risk = False
    requires_approval = True
    blocked_by_default = True
    recommended_verification = ["get_live_target_identity_gate"]

    if requested_key in MOVEMENT_KEY_ALIASES:
        semantic, primitive_tool = MOVEMENT_KEY_ALIASES[requested_key]
        action_kind_out = "movement-control"
        risk_class = "movement-risk"
        movement_risk = True
        recommended_verification.extend(["get_live_no_input_proof_status", "post-action-readback-required-before-trust"])
    elif requested_action in MOVEMENT_SEMANTIC_ALIASES:
        primitive_tool = MOVEMENT_SEMANTIC_ALIASES[requested_action]
        semantic = requested_action
        action_kind_out = "movement-control"
        risk_class = "movement-risk"
        movement_risk = True
        recommended_verification.extend(["get_live_no_input_proof_status", "post-action-readback-required-before-trust"])
    elif requested_kind == "movement-control":
        primitive_tool = "movement-primitive-from-approved-execution-tool"
        action_kind_out = "movement-control"
        risk_class = "movement-risk"
        movement_risk = True
        recommended_verification.extend(["get_live_no_input_proof_status", "post-action-readback-required-before-trust"])
    elif requested_kind == "displacement-stimulus" or requested_action in DISPLACEMENT_HINTS:
        semantic = requested_action or "coordinate-proof-pulse"
        primitive_tool = "bounded-displacement-stimulus"
        action_kind_out = "displacement-stimulus"
        risk_class = "live-state-mutation-risk"
        movement_risk = True
        recommended_verification.extend(["pre-and-post-coordinate-readback", "proof-promotion-still-forbidden"])
    elif requested_kind == "proof-only" or requested_action in PROOF_ONLY_HINTS:
        semantic = requested_action or "proof-only"
        primitive_tool = "none"
        action_kind_out = "proof-only"
        risk_class = "proof-gate-risk"
        movement_risk = False
        recommended_verification.append("confirm-proof-helper-is-no-input-before-running")
    elif requested_kind == "no-input-read" or requested_action in NO_INPUT_HINTS:
        semantic = requested_action or "inspect-status"
        primitive_tool = "read-only-mcp-tool"
        action_kind_out = "no-input-read"
        risk_class = "read-only"
        movement_risk = False
        requires_approval = False
        blocked_by_default = False
        recommended_verification.append("read-only-response-safety-flags")
    else:
        hotbar_match = HOTBAR_RE.match(requested_action)
        if hotbar_match:
            slot = hotbar_match.group(1)
            semantic = f"hotbar-slot-{slot}"
            primitive_tool = f"press_hotbar_slot:{slot}"
            action_kind_out = "ui-action"
            risk_class = "semantic-ui-action-risk"
            movement_risk = False
            recommended_verification.append("post-action-ui-state-check")
        elif requested_action in UI_ACTION_HINTS or requested_key == "i":
            semantic = requested_action or "open-inventory"
            primitive_tool = "send_key:I"
            action_kind_out = "ui-action"
            risk_class = "semantic-ui-action-risk"
            movement_risk = False
            recommended_verification.append("post-action-ui-state-check")
        elif not any((requested_action, requested_kind, requested_key)):
            blockers.append("live-plan-action-missing")
        else:
            warnings.append("live-plan-action-unrecognized")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-live-control-action-classification",
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "actionKind": action_kind_out,
        "riskClass": risk_class,
        "movementRisk": movement_risk,
        "requiresApproval": requires_approval,
        "blockedByDefault": blocked_by_default,
        "semanticAction": semantic,
        "primitiveTool": primitive_tool,
        "recommendedVerification": recommended_verification,
        "blockers": blockers,
        "warnings": warnings,
        "safety": _safety(),
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
            mismatches.append(f"target-identity-mismatch:{field}")
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
    md_path.write_text(
        "\n".join(
            [
                f"# Live control plan {plan_id}",
                "",
                f"- Status: `{payload.get('status')}`",
                f"- Action: `{payload.get('classification', {}).get('semanticAction')}`",
                f"- Risk: `{payload.get('classification', {}).get('riskClass')}`",
                f"- Movement risk: `{payload.get('classification', {}).get('movementRisk')}`",
                f"- Approval scope: `{approval.get('requiredApprovalScope')}`",
                "",
                "## Human approval prompt",
                "",
                str(approval.get("humanPrompt") or "No approval prompt generated."),
                "",
                "This artifact is plan-only. It does not execute input or create a reusable approval token.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "planPath": repo_rel(repo_root, json_path),
        "planMarkdownPath": repo_rel(repo_root, md_path),
    }


def build_live_control_plan(
    repo_root: Path,
    *,
    action_kind: str | None = None,
    semantic_action: str | None = None,
    key_chord: str | None = None,
    hold_milliseconds: Any = None,
    target_identity: dict[str, Any] | None = None,
    verification_requirements: dict[str, Any] | None = None,
    stop_condition: str | None = None,
    dry_run: bool = True,
    discovery_payload: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a Stage 42 live-control dry-run plan without executing input."""

    repo_root = repo_root.resolve()
    generated_at = utc_iso()
    now_utc = now or datetime.now(timezone.utc)
    expires_at = (now_utc.astimezone(timezone.utc) + timedelta(minutes=APPROVAL_EXPIRATION_MINUTES)).isoformat().replace(
        "+00:00", "Z"
    )
    classification = classify_action(action_kind=action_kind, semantic_action=semantic_action, key_chord=key_chord)
    requested_hold = _safe_int(hold_milliseconds, default=DEFAULT_MAX_HOLD_MILLISECONDS)
    max_hold = min(max(0, requested_hold), ABSOLUTE_MAX_HOLD_MILLISECONDS)
    blockers = list(classification.get("blockers") or [])
    warnings = list(classification.get("warnings") or [])
    if dry_run is not True:
        blockers.append("live-plan-dry-run-required")
    if requested_hold != max_hold:
        warnings.append(f"holdMilliseconds-clamped:{requested_hold}->{max_hold}")
    if classification.get("movementRisk") and max_hold <= 0:
        blockers.append("movement-risk-hold-duration-required")

    gate = live_rift_state.build_live_target_identity_gate(
        repo_root,
        discovery_payload=discovery_payload,
        now=now_utc,
    )
    gate_blockers = [str(item) for item in gate.get("blockers") or []]
    if not gate.get("ok"):
        blockers.extend(f"identity-gate:{item}" for item in gate_blockers)
    exact_target = gate.get("exactTargetFacts") if isinstance(gate.get("exactTargetFacts"), dict) else None
    blockers.extend(_target_identity_mismatches(exact_target, target_identity))

    target_summary = {
        "identityGateStatus": gate.get("status"),
        "identityGateOk": bool(gate.get("ok")),
        "exactTargetFacts": exact_target,
        "requestedTarget": gate.get("requestedTarget"),
        "freshness": gate.get("freshness"),
        "operatorSuppliedTargetIdentity": target_identity or {},
    }
    requested_action = {
        "actionKind": classification.get("actionKind"),
        "semanticAction": classification.get("semanticAction"),
        "keyChord": key_chord,
        "primitiveTool": classification.get("primitiveTool"),
        "holdMilliseconds": max_hold,
        "maxInputCount": 1,
        "stopCondition": stop_condition or "release-key-or-no-op-before-max-hold",
        "verificationRequirements": verification_requirements or {},
        "dryRun": True,
    }
    hash_input = {
        "schemaVersion": SCHEMA_VERSION,
        "stage": 42,
        "classification": {
            key: classification.get(key)
            for key in ("actionKind", "riskClass", "movementRisk", "semanticAction", "primitiveTool")
        },
        "targetBinding": target_summary,
        "requestedAction": requested_action,
        "expiresAtUtc": expires_at,
    }
    plan_hash = hashlib.sha256(json.dumps(hash_input, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    plan_id = f"{generated_at.replace('-', '').replace(':', '').replace('Z', 'Z')}-{plan_hash[:12]}"
    required_scope = (
        "none-read-only"
        if classification.get("requiresApproval") is False
        else f"current-turn-{classification.get('riskClass')}-approval"
    )
    human_prompt = (
        "Plan-only output: no live input was sent. If a future execution tool is available and all gates still pass, "
        f"approve exactly this plan by saying: APPROVE LIVE RIFT {classification.get('riskClass')} PLAN "
        f"{plan_hash[:16]} FOR PID "
        f"{(exact_target or {}).get('processId')} HWND {(exact_target or {}).get('targetWindowHandle')} "
        f"HOLD <= {max_hold}MS. This is not reusable and expires at {expires_at}."
    )
    execution_blockers = [
        "stage-42-plan-only-no-execution-tool",
        "live-approval-required-before-any-input",
        "post-action-readback-required-before-trust",
    ]
    if classification.get("movementRisk"):
        execution_blockers.append("movement-risk-blocked-by-default")
    ok = not blockers
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-live-control-plan",
        "generatedAtUtc": generated_at,
        "status": "planned" if ok else "blocked",
        "ok": ok,
        "stage": 42,
        "stageName": "Live control dry-run/planning tool",
        "planId": plan_id,
        "planHash": plan_hash,
        "actionKind": classification.get("actionKind"),
        "riskClass": classification.get("riskClass"),
        "movementRisk": classification.get("movementRisk"),
        "classification": classification,
        "targetBinding": target_summary,
        "requestedAction": requested_action,
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
            "futureExecutionToolRequired": True,
            "executionBlockers": execution_blockers,
        },
        "recommendedVerification": classification.get("recommendedVerification"),
        "blockers": blockers,
        "warnings": warnings,
        "safety": _safety(),
    }
    artifact_paths = _write_plan_artifacts(repo_root, plan_id, payload)
    payload["artifact"] = {
        **artifact_paths,
        "underIgnoredDotRiftReaderLocal": True,
    }
    # Rewrite once with the artifact paths included so the JSON artifact exactly
    # matches the MCP response.
    json_path = repo_root / artifact_paths["planPath"]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload

