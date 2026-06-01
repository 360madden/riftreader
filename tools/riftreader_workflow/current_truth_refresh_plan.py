#!/usr/bin/env python3
"""Build a dry-run current-truth refresh plan from navigation discovery evidence.

This helper is deliberately non-applying. It reads the tracked
``docs/recovery/current-truth.json`` and the ignored navigation pointer
discovery dashboard, then writes an ignored proposal/diff under
``.riftreader-local``. It never edits tracked truth docs, sends live input,
reads target memory, attaches debuggers, writes providers, mutates Git, or
promotes proof/candidate chains.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, preview_text, repo_rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, preview_text, repo_rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-current-truth-refresh-plan-v0.1.0"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_DASHBOARD_JSON = Path(".riftreader-local") / "navigation-pointer-discovery" / "latest" / "summary.json"
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "current-truth-refresh-plan" / "latest"
PROMOTED_FACING_STATUS = "promoted-static-owner-facing-yaw-current-pid-readback-passed"
REQUIRED_FACING_CHAIN = "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314"


class CurrentTruthRefreshPlanError(RuntimeError):
    """Raised for controlled planner failures."""


def as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise CurrentTruthRefreshPlanError(f"malformed-json:{path}:{exc}") from exc
    except OSError as exc:
        raise CurrentTruthRefreshPlanError(f"json-read-failed:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise CurrentTruthRefreshPlanError(f"json-root-not-object:{path}")
    return payload


def json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def build_unified_diff(before: dict[str, Any], after: dict[str, Any], *, fromfile: str, tofile: str) -> str:
    return "".join(
        difflib.unified_diff(
            json_text(before).splitlines(keepends=True),
            json_text(after).splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )


def get_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def set_path(payload: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = payload
    for part in path[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[path[-1]] = value


def pointer(path: tuple[str, ...]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)


def append_unique_note(notes: Any, note: str) -> list[str]:
    result = [str(item) for item in as_list(notes)]
    if note not in result:
        result.append(note)
    return result


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def truth_artifact_path(repo_root: Path, value: Any) -> str | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = repo_root / path
    return str(path)


def sibling_markdown_artifact(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    return text[:-5] + ".md" if text.lower().endswith(".json") else None


def add_update(
    *,
    current_truth: dict[str, Any],
    proposed: dict[str, Any],
    updates: list[dict[str, Any]],
    path: tuple[str, ...],
    value: Any,
    reason: str,
) -> None:
    before = get_path(current_truth, path)
    if before == value:
        return
    set_path(proposed, path, value)
    updates.append(
        {
            "path": pointer(path),
            "before": before,
            "after": value,
            "reason": reason,
        }
    )


def target_identity(current_truth: dict[str, Any], dashboard: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    return as_mapping(current_truth.get("target")), as_mapping(dashboard.get("target"))


def dashboard_target_is_fresh_readback(target: dict[str, Any]) -> bool:
    identity_source = str(target.get("identitySource") or "")
    return identity_source in {
        "latest-coordinate-readback",
        "latest-nav-state-readback",
        "latest-coordinate-and-nav-state-readbacks",
    }


def validate_target_identity(current_truth: dict[str, Any], dashboard: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    truth_target, dashboard_target = target_identity(current_truth, dashboard)
    allow_refresh = dashboard_target_is_fresh_readback(dashboard_target)
    for field in ("processName", "processId", "targetWindowHandle", "processStartUtc", "moduleBase"):
        truth_value = truth_target.get(field)
        dashboard_value = dashboard_target.get(field)
        if dashboard_value is None:
            blockers.append(f"target-identity-field-missing:{field}")
            continue
        if allow_refresh:
            continue
        if truth_value is None:
            blockers.append(f"target-identity-field-missing:{field}")
            continue
        if str(truth_value) != str(dashboard_value):
            blockers.append(f"target-identity-mismatch:{field}:truth={truth_value};dashboard={dashboard_value}")
    return blockers


def validate_dashboard_safety(dashboard: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    safety = as_mapping(dashboard.get("safety"))
    source_safety = as_mapping(dashboard.get("sourceSafety"))
    forbidden_true_flags = (
        "movementSent",
        "inputSent",
        "targetMemoryBytesRead",
        "targetMemoryBytesWritten",
        "proofPromotion",
        "actorChainPromotion",
        "facingPromotion",
        "gitMutation",
        "providerWrites",
        "x64dbgAttach",
    )
    for flag in forbidden_true_flags:
        if bool(safety.get(flag)):
            blockers.append(f"dashboard-safety-flag-true:{flag}")
    if not bool(safety.get("readOnlyArtifactIndex", False)):
        blockers.append("dashboard-not-read-only-artifact-index")
    if bool(source_safety.get("familySnapshotMovementSent")):
        # Historical source movement is allowed as evidence, but it must stay explicit.
        pass
    return blockers


def promoted_facing_yaw_already_recorded(
    current_facing: dict[str, Any],
    dashboard_facing: dict[str, Any],
) -> bool:
    """Return true only for the already-promoted static-owner facing/yaw lane.

    The refresh planner must never be the component that promotes facing/yaw.
    It may, however, refresh current-PID readback fields after a separate
    promotion artifact has already been recorded in tracked truth.
    """

    primary = as_mapping(current_facing.get("primaryCandidate"))
    chain = dashboard_facing.get("chainShape") or dashboard_facing.get("expression") or primary.get("expression")
    return (
        current_facing.get("promotionAllowed") is True
        and bool(current_facing.get("promotionArtifact"))
        and dashboard_facing.get("promotionAllowed") is True
        and dashboard_facing.get("candidateOnly") is False
        and dashboard_facing.get("status") == PROMOTED_FACING_STATUS
        and chain == REQUIRED_FACING_CHAIN
    )


def build_proposed_current_truth(
    *,
    repo_root: Path,
    current_truth: dict[str, Any],
    dashboard: dict[str, Any],
    generated_at_utc: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    proposed = copy.deepcopy(current_truth)
    updates: list[dict[str, Any]] = []
    target = as_mapping(dashboard.get("target"))
    sources = as_mapping(dashboard.get("sources"))
    coordinate_source = as_mapping(sources.get("coordinateReadback"))
    nav_state_source = as_mapping(sources.get("navState"))
    candidates = as_mapping(dashboard.get("candidates"))
    promoted = as_mapping(candidates.get("promotedCoordinate"))
    coordinate = as_mapping(promoted.get("coordinate"))
    latest_readback_at = promoted.get("latestReadbackAtUtc")
    latest_readback_json = truth_artifact_path(
        repo_root,
        promoted.get("latestReadbackJson") or coordinate_source.get("path"),
    )
    latest_readback_markdown = sibling_markdown_artifact(latest_readback_json)
    latest_nav_state_json = truth_artifact_path(repo_root, nav_state_source.get("path"))
    latest_nav_state_at = nav_state_source.get("generatedAtUtc")
    facing = as_mapping(candidates.get("candidateFacingTarget"))
    current_facing = as_mapping(current_truth.get("staticOwnerFacing"))
    facing_already_promoted = promoted_facing_yaw_already_recorded(current_facing, facing)
    latest_facing_evidence = as_mapping(facing.get("evidence"))
    process_id = target.get("processId")
    hwnd = target.get("targetWindowHandle")
    api_now_status = promoted.get("apiNowStatus")
    api_now_current = bool(
        isinstance(api_now_status, str)
        and api_now_status.startswith("passed")
        and f"current-pid-{process_id}" in api_now_status
    )
    api_now_comparison = as_mapping(promoted.get("apiNowComparison"))
    api_reference_json = truth_artifact_path(repo_root, api_now_comparison.get("apiReferenceJson"))
    latest_api_validation = None
    if api_now_comparison:
        latest_api_validation = {
            "status": api_now_status,
            "currentPidValidation": {
                "status": api_now_status,
                "processId": process_id,
                "targetWindowHandle": hwnd,
                "capturedAtUtc": api_now_comparison.get("capturedAtUtc"),
                "apiReferenceJson": api_reference_json,
                "chainReadbackJson": latest_readback_json,
                "apiCoordinate": api_now_comparison.get("apiCoordinate"),
                "chainCoordinate": api_now_comparison.get("chainCoordinate"),
                "deltasChainMinusApi": api_now_comparison.get("deltasChainMinusApi"),
                "absDeltas": api_now_comparison.get("absDeltas"),
                "maxAbsDelta": api_now_comparison.get("maxAbsDelta"),
                "tolerance": api_now_comparison.get("tolerance"),
                "withinTolerance": api_now_comparison.get("withinTolerance"),
            },
            "currentApiNowStatus": api_now_status,
            "apiReferenceJson": api_reference_json,
            "chainReadbackJson": latest_readback_json,
            "maxAbsDelta": api_now_comparison.get("maxAbsDelta"),
            "tolerance": api_now_comparison.get("tolerance"),
        }
    verification_source = (
        f"Dry-run refresh plan from navigation pointer discovery dashboard generated {dashboard.get('generatedAtUtc')}. "
        f"Latest no-input static-chain readback for exact PID {process_id} / HWND {hwnd} passed at "
        f"{latest_readback_at}. API-now status is "
        f"{'current for this target' if api_now_current else 'not refreshed for this target by this planner'}; this planner performs no "
        "proof/facing/actor promotion."
    )
    readback_status = promoted.get("status") or "promoted-static-coordinate-resolver-readback-passed"
    live_status = (
        f"current-pid-{process_id}-static-readback-and-api-now-current"
        if api_now_current
        else f"current-pid-{process_id}-static-readback-refreshed-api-now-not-refreshed-by-plan"
    )
    live_source = "Promoted static owner coordinate resolver latest no-input readback."
    if api_now_current:
        live_source += " RRAPICOORD/API-now evidence is current for this target."
    else:
        live_source += " RRAPICOORD/API-now evidence remains stale or from a prior target unless separately refreshed."
    live_view = (
        f"Current target PID {process_id} / HWND {hwnd} has a proposed tracked-truth refresh from "
        f"static-chain readback at {latest_readback_at}; "
        f"API-now status is {api_now_status or 'missing'}; no proof promotion or live input is performed."
    )
    coordinate_with_time = dict(coordinate)
    coordinate_with_time["recordedAtUtc"] = latest_readback_at
    note = (
        f"Dry-run current-truth refresh plan generated {generated_at_utc}; applying tracked truth remains a separate gate."
    )
    current_warnings = [
        str(item) for item in as_list(current_truth.get("currentWarnings"))
    ]
    refreshed_warnings: list[str] = []
    historical_api_warning_prefixes: list[str] = []
    for item in current_warnings:
        if item.startswith("current-pid-") and "api-now-validation-refreshed-at" in item:
            continue
        stale_api_warning_marker = "-api-validation-must-not-be-presented-as-current-pid-"
        if item.startswith("historical-pid-") and stale_api_warning_marker in item:
            historical_api_warning_prefixes.append(item.split(stale_api_warning_marker, 1)[0])
            continue
        refreshed_warnings.append(item)
    for prefix in unique_strings(historical_api_warning_prefixes):
        refreshed_warnings.append(f"{prefix}-api-validation-must-not-be-presented-as-current-pid-{process_id}-api-now")
    if api_now_current:
        refreshed_warnings.append(
            f"current-pid-{process_id}-api-now-validation-refreshed-at-{api_now_comparison.get('capturedAtUtc')}"
        )
    current_warnings = unique_strings(refreshed_warnings)
    latest_static_readback = {
        "status": promoted.get("latestReadbackStatus") or coordinate_source.get("status"),
        "processId": process_id,
        "targetWindowHandle": hwnd,
        "processStartUtc": target.get("processStartUtc"),
        "moduleBase": target.get("moduleBase"),
        "rootAddress": promoted.get("rootAddress"),
        "ownerAddress": promoted.get("ownerAddress"),
        "coordinateAddress": promoted.get("coordinateAddress"),
        "coordinate": coordinate,
        "recordedAtUtc": latest_readback_at,
        "summaryJson": latest_readback_json,
        "summaryMarkdown": latest_readback_markdown,
    }
    turn_rate = as_mapping(candidates.get("candidateTurnRate"))
    latest_nav_state_readback = {
        "status": nav_state_source.get("status"),
        "processId": process_id,
        "targetWindowHandle": hwnd,
        "processStartUtc": target.get("processStartUtc"),
        "coordinate": coordinate,
        "facingTargetCoordinate": facing.get("latestFacingTargetCoordinate"),
        "yawDegrees": facing.get("latestYawDegrees"),
        "pitchDegrees": facing.get("latestPitchDegrees"),
        "turnRate0x304": turn_rate.get("latestValue"),
        "turnRateClassification": turn_rate.get("classification"),
        "recordedAtUtc": latest_nav_state_at,
        "summaryJson": latest_nav_state_json,
        "summaryMarkdown": sibling_markdown_artifact(latest_nav_state_json),
    }
    live_notes: list[str] = []
    for item in as_list(get_path(current_truth, ("liveReferenceSurface", "notes"))):
        text = str(item)
        if text.startswith("Current target is PID "):
            continue
        if text.startswith("Current PID static-chain readback and RRAPICOORD API-now validation are fresh as of "):
            continue
        if text.startswith("Current PID static-chain readback is fresh as of "):
            continue
        if text.startswith("Dry-run current-truth refresh plan generated "):
            continue
        live_notes.append(text)
    live_notes = append_unique_note(
        live_notes,
        f"Current target is PID {process_id} / HWND {hwnd} with process start {target.get('processStartUtc')}.",
    )
    if api_now_current:
        live_notes = append_unique_note(
            live_notes,
            "Current PID static-chain readback and RRAPICOORD API-now validation are fresh as of "
            f"{latest_readback_at} / {api_now_comparison.get('capturedAtUtc')} for this tracked refresh.",
        )
    else:
        live_notes = append_unique_note(
            live_notes,
            f"Current PID static-chain readback is fresh as of {latest_readback_at}; "
            "RRAPICOORD/API-now validation is not current for this target.",
        )
    live_notes = append_unique_note(live_notes, note)
    if api_now_current and facing_already_promoted:
        next_recommended_action = (
            f"Use the promoted static owner coordinate and facing/yaw resolvers after exact "
            f"PID/HWND/process-start/module-base preflight. Current PID {process_id} API-now vs chain-now "
            f"coordinate validation is current at {api_now_comparison.get('capturedAtUtc')}; facing/yaw was "
            "already promoted by its explicit artifact and this refresh only updates current-PID readback fields. "
            "Keep turn-rate, actor/stat chains, proof anchors, and autonomous route-control automation separate."
        )
    elif api_now_current:
        next_recommended_action = (
            f"Use the promoted static player-coordinate resolver with exact PID/HWND/process-start/module-base "
            f"preflights; current PID {process_id} API-now vs chain-now validation is current at "
            f"{api_now_comparison.get('capturedAtUtc')}. Keep facing/turn-rate chains candidate-only until "
            "restart/relog survival, static-root proof, and formal three-pose displacement gates pass."
        )
    else:
        next_recommended_action = (
            f"Use the promoted static player-coordinate resolver only after exact PID/HWND/process-start/module-base "
            f"preflights, and capture current PID {process_id} API-now vs chain-now evidence before presenting "
            "coordinates as current API truth or promoting additional proof. Keep actor/stat discovery separate "
            "from the coordinate resolver."
        )
    best_reuse_policy = (
        "Promoted as the static player-coordinate resolver. Reacquire the owner from rift_x64+0x32EBC80 "
        f"each session; do not use a heap owner address as static; do not treat historical API-now evidence "
        f"as current PID {process_id} API proof."
    )
    stale_or_invalid: list[Any] = []
    stale_or_invalid_changed = False
    for item in as_list(current_truth.get("staleOrInvalid")):
        if not isinstance(item, dict):
            stale_or_invalid.append(item)
            continue
        refreshed_item = dict(item)
        if refreshed_item.get("status") == "historical-stale-superseded-by-promoted-static-player-coordinate-resolver":
            refreshed_item["reason"] = (
                "The promoted static resolver passed historical PID 34176 RRAPICOORD API-now vs chain-now "
                f"displacement validation, but the current live target is PID {process_id} / HWND {hwnd}. "
                "Old absolute proof-anchor addresses remain stale."
            )
            refreshed_item["reusePolicy"] = (
                f"historical audit/discovery context only; never current movement/API proof for PID {process_id}"
            )
        if refreshed_item != item:
            stale_or_invalid_changed = True
        stale_or_invalid.append(refreshed_item)
    movement_gate_status = (
        "allowed-with-current-pid-exact-target-fresh-static-readback-and-api-now-validation"
        if api_now_current
        else "blocked-current-target-api-now-not-refreshed"
    )
    movement_gate_reason = (
        f"The static coordinate resolver is promoted and current PID {process_id} exact-target readback passed at "
        f"{latest_readback_at}. "
    )
    if api_now_current:
        movement_gate_reason += (
            "Current PID RRAPICOORD/API-now validation is current in tracked truth. Live consumers must still "
            "verify PID/HWND/process-start/module-base and perform a fresh static-chain readback before input."
        )
    else:
        movement_gate_reason += (
            f"Current PID RRAPICOORD/API-now validation is not current for this target "
            f"(status={api_now_status or 'missing'}), so movement remains blocked until API-now is refreshed."
        )

    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("status",),
        value=live_status.replace("-", "_"),
        reason="align top-level truth status with latest target/readback/API freshness",
    )
    for field in ("processName", "processId", "targetWindowHandle", "processStartUtc", "moduleBase", "status"):
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("target", field),
            value=target.get(field),
            reason="refresh current target identity from latest exact-target readback",
        )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("updatedAtUtc",),
        value=generated_at_utc,
        reason="mark proposed tracked truth refresh time",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("target", "lastVerifiedUtc"),
        value=latest_readback_at,
        reason="latest exact-target static-chain coordinate readback time",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("target", "verificationSource"),
        value=verification_source,
        reason="record dry-run source and non-promotion boundary",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "status"),
        value=live_status,
        reason="separate static readback freshness from API-now/proof freshness",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "source"),
        value=live_source,
        reason="avoid claiming fresh API-now evidence from a readback-only plan",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "view"),
        value=live_view,
        reason="summarize exact-target readback plan without promotion",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "currentCoordinateFromStaticChainCandidate"),
        value=coordinate_with_time,
        reason="latest promoted coordinate resolver readback coordinate",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("currentWarnings",),
        value=current_warnings,
        reason="refresh current-pid API-now warning marker",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "apiNowStatus"),
        value=api_now_status or "missing",
        reason="record API-now freshness relative to refreshed target",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "apiNowBlockers"),
        value=[] if api_now_current else ["current-target-api-now-not-refreshed"],
        reason="keep API-now blockers aligned with refreshed target",
    )
    if latest_api_validation:
        latest_api_coordinate = {
            "status": api_now_status,
            "coordinate": api_now_comparison.get("apiCoordinate"),
            "capturedAtUtc": api_now_comparison.get("capturedAtUtc"),
            "referenceFile": api_reference_json,
            "deltasChainMinusApi": api_now_comparison.get("deltasChainMinusApi"),
            "absDeltas": api_now_comparison.get("absDeltas"),
            "maxAbsDelta": api_now_comparison.get("maxAbsDelta"),
            "tolerance": api_now_comparison.get("tolerance"),
            "staticReadbackJson": latest_readback_json,
            "note": (
                "Current-target RRAPICOORD coordinate matched the latest static-chain readback within "
                "tolerance; refresh again before later current-now claims."
            ),
        }
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("liveReferenceSurface", "latestApiCoordinate"),
            value=latest_api_coordinate,
            reason="record latest current-target RRAPICOORD coordinate",
        )
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("liveReferenceSurface", "latestApiNowVsChainNow"),
            value=latest_api_validation,
            reason="record latest current-target API-now vs static-chain comparison",
        )
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("staticChainStatus", "latestApiNowValidation"),
            value=latest_api_validation,
            reason="record latest current-target API-now vs static-chain comparison",
        )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "notes"),
        value=live_notes,
        reason="preserve dry-run/apply boundary in tracked notes",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "latestCurrentStaticReadback"),
        value=latest_static_readback,
        reason="mirror latest exact-target static readback payload",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "latestCurrentNavStateReadback"),
        value=latest_nav_state_readback,
        reason="mirror latest exact-target nav-state readback payload",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "status"),
        value=readback_status,
        reason="align coordinate resolver status with latest dashboard promoted-coordinate status",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "ownerAddress"),
        value=promoted.get("ownerAddress"),
        reason="latest owner address for current target epoch",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "rootAddress"),
        value=promoted.get("rootAddress"),
        reason="latest root address for current target epoch",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "coordinateAddress"),
        value=promoted.get("coordinateAddress"),
        reason="latest coordinate address for current target epoch",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "coordinate"),
        value=coordinate,
        reason="latest promoted coordinate resolver readback",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "latestPromotedReadbackArtifact"),
        value=latest_readback_json,
        reason="latest artifact for promoted static resolver readback",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "latestCurrentReadbackArtifact"),
        value=latest_readback_json,
        reason="latest exact-target static-chain coordinate readback artifact",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "latestCurrentReadbackAtUtc"),
        value=latest_readback_at,
        reason="latest exact-target static-chain coordinate readback time",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "latestCurrentStaticReadback"),
        value=latest_static_readback,
        reason="mirror latest exact-target static readback payload",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("bestCurrentCandidate", "rootAddress"),
        value=promoted.get("rootAddress"),
        reason="latest root address for current target epoch",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("bestCurrentCandidate", "currentOwnerAddress"),
        value=promoted.get("ownerAddress"),
        reason="latest owner address for current target epoch",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("bestCurrentCandidate", "currentCoordinateAddress"),
        value=promoted.get("coordinateAddress"),
        reason="latest coordinate address for current target epoch",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("bestCurrentCandidate", "addressHex"),
        value=promoted.get("coordinateAddress"),
        reason="latest coordinate address for current target epoch",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("bestCurrentCandidate", "coordinate"),
        value=coordinate,
        reason="latest promoted coordinate resolver readback",
    )
    for best_path in (
        ("bestCurrentCandidate", "artifact"),
        ("bestCurrentCandidate", "candidateFile"),
        ("bestCurrentCandidate", "readbackSummary"),
        ("bestCurrentCandidate", "latestCurrentReadbackArtifact"),
    ):
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=best_path,
            value=latest_readback_json,
            reason="latest exact-target static-chain coordinate readback artifact",
        )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("bestCurrentCandidate", "status"),
        value=readback_status,
        reason="align best current candidate status with latest static readback",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("bestCurrentCandidate", "latestCurrentReadbackAtUtc"),
        value=latest_readback_at,
        reason="latest exact-target static-chain coordinate readback time",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("bestCurrentCandidate", "reusePolicy"),
        value=best_reuse_policy,
        reason="align promoted coordinate resolver reuse policy with refreshed target identity",
    )
    if api_reference_json:
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("bestCurrentCandidate", "latestCurrentApiNowVsChainNowArtifact"),
            value=api_reference_json,
            reason="latest current-target API-now reference artifact",
        )
    if stale_or_invalid_changed:
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("staleOrInvalid",),
            value=stale_or_invalid,
            reason="align stale-proof explanatory text with refreshed target identity",
        )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("movementGate", "allowed"),
        value=api_now_current,
        reason="block movement when API-now is stale for the refreshed target",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("movementGate", "status"),
        value=movement_gate_status,
        reason="align movement gate status with current API-now freshness",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("movementGate", "reason"),
        value=movement_gate_reason,
        reason="align movement gate explanation with latest static readback",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("movementGate", "latestCurrentReadbackArtifact"),
        value=latest_readback_json,
        reason="latest exact-target static-chain coordinate readback artifact",
    )
    if api_reference_json:
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("movementGate", "latestCurrentApiNowValidationArtifact"),
            value=api_reference_json,
            reason="latest current-target API-now reference artifact",
        )
    if facing:
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("staticOwnerFacing", "primaryCandidate", "ownerAddress"),
            value=facing.get("ownerAddress"),
            reason="latest current-pid facing candidate owner address",
        )
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("staticOwnerFacing", "primaryCandidate", "facingTargetAddress"),
            value=facing.get("address"),
            reason="latest current-pid facing candidate address",
        )
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("staticOwnerFacing", "primaryCandidate", "latestYawDegrees"),
            value=facing.get("latestYawDegrees"),
            reason="latest current-pid nav-state yaw readback",
        )
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("staticOwnerFacing", "primaryCandidate", "latestYawSourcePose"),
            value=f"current-pid-{process_id}-static-nav-state-readback-{latest_nav_state_at}",
            reason="latest current-pid nav-state yaw source",
        )
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("staticOwnerFacing", "primaryCandidate", "latestCurrentNavStateReadbackArtifact"),
            value=truth_artifact_path(repo_root, latest_facing_evidence.get("navStateJson") or latest_nav_state_json),
            reason="latest exact-target nav-state readback artifact",
        )
        current_reacquisition = {
            "status": "promoted-current-pid-refresh" if facing_already_promoted else "passed-candidate-only-refresh",
            "navStateJson": truth_artifact_path(repo_root, latest_facing_evidence.get("navStateJson") or latest_nav_state_json),
            "facingComparisonJson": truth_artifact_path(repo_root, latest_facing_evidence.get("facingComparisonJson")),
            "topRelativeTargetOffset": facing.get("offset"),
            "maxAbsYawDeltaDegrees": facing.get("comparisonMaxAbsYawDeltaDegrees"),
            "coordinateDriftAllPoses": facing.get("comparisonMaxCoordinatePlanarDrift"),
            "processId": process_id,
            "targetWindowHandle": hwnd,
            "processStartUtc": target.get("processStartUtc"),
            "apiNowStatus": api_now_status,
            "promotionState": "already-promoted" if facing_already_promoted else "candidate-only",
            "promotionArtifact": (
                truth_artifact_path(repo_root, facing.get("promotionArtifact") or current_facing.get("promotionArtifact"))
                if facing_already_promoted
                else None
            ),
            "promotionPerformed": False,
            "recordedAtUtc": latest_nav_state_at,
        }
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("staticOwnerFacing", "latestCurrentReacquisition"),
            value=current_reacquisition,
            reason=(
                "record current-pid readback for already-promoted facing/yaw chain"
                if facing_already_promoted
                else "record current-pid facing readback as candidate-only reacquisition evidence"
            ),
        )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("canonicalArtifacts", "latestCurrentPidStaticOwnerReadback"),
        value=latest_readback_json,
        reason="latest exact-target static-owner readback artifact",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("canonicalArtifacts", "latestCurrentPidNavStateReadback"),
        value=latest_nav_state_json,
        reason="latest exact-target nav-state readback artifact",
    )
    if api_reference_json:
        add_update(
            current_truth=current_truth,
            proposed=proposed,
            updates=updates,
            path=("canonicalArtifacts", "latestCurrentPidRrapicoordApiReference"),
            value=api_reference_json,
            reason="latest current-target API-now reference artifact",
        )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("nextRecommendedAction",),
        value=next_recommended_action,
        reason="align next action with refreshed target identity and API-now status",
    )
    return proposed, updates


def build_current_truth_refresh_plan(
    repo_root: Path,
    *,
    current_truth_json: Path | None = None,
    dashboard_json: Path | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    generated = generated_at_utc or utc_iso()
    truth_path = repo_root / (current_truth_json or DEFAULT_CURRENT_TRUTH_JSON)
    dashboard_path = repo_root / (dashboard_json or DEFAULT_DASHBOARD_JSON)
    errors: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    current_truth: dict[str, Any] | None = None
    dashboard: dict[str, Any] | None = None
    try:
        current_truth = load_json_object(truth_path)
    except CurrentTruthRefreshPlanError as exc:
        errors.append(f"current-truth-load-failed:{preview_text(str(exc), max_lines=1, max_chars=500)}")
    try:
        dashboard = load_json_object(dashboard_path)
    except CurrentTruthRefreshPlanError as exc:
        errors.append(f"navigation-dashboard-load-failed:{preview_text(str(exc), max_lines=1, max_chars=500)}")

    if current_truth is None or dashboard is None:
        status = "failed"
        proposed: dict[str, Any] | None = None
        updates: list[dict[str, Any]] = []
        diff_text = ""
    else:
        if dashboard.get("kind") != "riftreader-navigation-pointer-discovery-status":
            blockers.append(f"navigation-dashboard-kind-unexpected:{dashboard.get('kind')}")
        if dashboard.get("status") != "passed":
            blockers.append(f"navigation-dashboard-not-passed:{dashboard.get('status')}")
        blockers.extend(validate_target_identity(current_truth, dashboard))
        blockers.extend(validate_dashboard_safety(dashboard))

        sources = as_mapping(dashboard.get("sources"))
        for source_key in ("coordinateReadback", "navState"):
            source = as_mapping(sources.get(source_key))
            freshness = as_mapping(source.get("freshness"))
            if source.get("status") != "passed":
                blockers.append(f"{source_key}-not-passed:{source.get('status')}")
            if freshness.get("status") != "fresh":
                blockers.append(f"{source_key}-not-fresh:{freshness.get('status')}")

        candidates = as_mapping(dashboard.get("candidates"))
        promoted = as_mapping(candidates.get("promotedCoordinate"))
        current_facing = as_mapping(current_truth.get("staticOwnerFacing"))
        if not promoted:
            blockers.append("promoted-coordinate-missing")
        else:
            if promoted.get("candidateOnly") is not False:
                blockers.append("promoted-coordinate-not-marked-promoted")
            if promoted.get("latestReadbackStatus") != "passed":
                blockers.append(f"promoted-coordinate-readback-not-passed:{promoted.get('latestReadbackStatus')}")
            if not isinstance(promoted.get("coordinate"), dict):
                blockers.append("promoted-coordinate-missing-coordinate")
            if not promoted.get("latestReadbackAtUtc"):
                blockers.append("promoted-coordinate-missing-latest-readback-time")
            if not promoted.get("ownerAddress") or not promoted.get("coordinateAddress"):
                blockers.append("promoted-coordinate-missing-current-addresses")

        freshness = as_mapping(dashboard.get("freshness"))
        stale_sources = as_list(freshness.get("staleSources"))
        if "currentTruth" not in [str(item) for item in stale_sources]:
            warnings.append("current-truth-not-marked-stale-by-dashboard")
        if any(str(item) in {"coordinateReadback", "navState"} for item in stale_sources):
            blockers.append("dashboard-has-stale-readback-source")
        facing = as_mapping(candidates.get("candidateFacingTarget"))
        if facing.get("promotionAllowed") and not promoted_facing_yaw_already_recorded(current_facing, facing):
            blockers.append("facing-target-promotion-unexpectedly-allowed")
        if as_mapping(candidates.get("candidateTurnRate")).get("promotionAllowed"):
            blockers.append("turn-rate-promotion-unexpectedly-allowed")
        if current_facing.get("promotionAllowed") is True and facing.get("candidateOnly"):
            if not current_facing.get("promotionArtifact"):
                warnings.append("current-truth-staticOwnerFacing-promoted-without-promotion-artifact")

        if blockers:
            proposed = None
            updates = []
            diff_text = ""
            status = "blocked"
        else:
            proposed, updates = build_proposed_current_truth(
                repo_root=repo_root,
                current_truth=current_truth,
                dashboard=dashboard,
                generated_at_utc=generated,
            )
            diff_text = build_unified_diff(
                current_truth,
                proposed,
                fromfile=repo_rel(repo_root, truth_path) or str(truth_path),
                tofile="proposed-current-truth.json",
            )
            status = "passed"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-current-truth-refresh-plan",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated,
        "status": status,
        "verdict": "dry-run-current-truth-refresh-plan-ready" if status == "passed" else status,
        "repoRoot": str(repo_root),
        "inputs": {
            "currentTruthJson": repo_rel(repo_root, truth_path),
            "navigationDashboardJson": repo_rel(repo_root, dashboard_path),
        },
        "target": as_mapping(dashboard).get("target") if dashboard else {},
        "updates": updates,
        "updateCount": len(updates),
        "proposedCurrentTruth": proposed,
        "diffPreview": preview_text(diff_text, max_lines=120, max_chars=12000),
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "safety": {
            **safety_flags(),
            "dryRunOnly": True,
            "trackedTruthWritten": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
        },
        "artifacts": {},
        "next": {
            "recommendedAction": (
                "Review the ignored plan artifacts. Apply a tracked current-truth update only after explicitly opening "
                "the truth-refresh gate; do not treat this plan as proof promotion."
                if status == "passed"
                else "Resolve blockers before planning a tracked current-truth refresh."
            ),
            "requiresExplicitApprovalForApply": True,
        },
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# RiftReader Current Truth Refresh Plan",
        "",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Update count: `{summary.get('updateCount')}`",
        f"- Apply requires explicit approval: `{as_mapping(summary.get('next')).get('requiresExplicitApprovalForApply')}`",
        "",
        "## Inputs",
        "",
    ]
    for key, value in as_mapping(summary.get("inputs")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Updates", "", "| Path | Reason |", "|---|---|"])
    for update in as_list(summary.get("updates")):
        item = as_mapping(update)
        lines.append(f"| `{item.get('path')}` | {item.get('reason')} |")
    if not as_list(summary.get("updates")):
        lines.append("| none | none |")
    lines.extend(["", "## Blockers", ""])
    for blocker in as_list(summary.get("blockers")) or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Warnings", ""])
    for warning in as_list(summary.get("warnings")) or ["none"]:
        lines.append(f"- `{warning}`")
    lines.extend(["", "## Artifacts", ""])
    for key, value in as_mapping(summary.get("artifacts")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Diff preview",
            "",
            "```diff",
            str(summary.get("diffPreview") or ""),
            "```",
            "",
            "## Next action",
            "",
            str(as_mapping(summary.get("next")).get("recommendedAction") or "none"),
            "",
            "## Safety",
            "",
            "| Flag | Value |",
            "|---|---:|",
        ]
    )
    for key, value in as_mapping(summary.get("safety")).items():
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)


def write_outputs(repo_root: Path, summary: dict[str, Any], output_dir: Path | None = None) -> dict[str, str]:
    base = output_dir or DEFAULT_OUTPUT_DIR
    if not base.is_absolute():
        base = repo_root / base
    base.mkdir(parents=True, exist_ok=True)
    summary_json = base / "summary.json"
    summary_md = base / "summary.md"
    proposed_json = base / "proposed-current-truth.json"
    diff_path = base / "proposed-current-truth.diff"
    artifacts = {
        "outputDirectory": repo_rel(repo_root, base) or str(base),
        "summaryJson": repo_rel(repo_root, summary_json) or str(summary_json),
        "summaryMarkdown": repo_rel(repo_root, summary_md) or str(summary_md),
        "proposedCurrentTruthJson": repo_rel(repo_root, proposed_json) or str(proposed_json),
        "proposedCurrentTruthDiff": repo_rel(repo_root, diff_path) or str(diff_path),
    }
    summary["artifacts"] = artifacts
    summary_json.write_text(json_text(summary), encoding="utf-8")
    summary_md.write_text(build_markdown(summary) + "\n", encoding="utf-8")
    if isinstance(summary.get("proposedCurrentTruth"), dict):
        proposed_json.write_text(json_text(summary["proposedCurrentTruth"]), encoding="utf-8")
        diff_path.write_text(str(summary.get("diffPreview") or ""), encoding="utf-8")
    else:
        proposed_json.write_text("", encoding="utf-8")
        diff_path.write_text("", encoding="utf-8")
    return artifacts


def write_self_test_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_text(value), encoding="utf-8")


def seed_self_test_repo(repo_root: Path) -> tuple[Path, Path]:
    truth_path = repo_root / DEFAULT_CURRENT_TRUTH_JSON
    dashboard_path = repo_root / DEFAULT_DASHBOARD_JSON
    target = {
        "processName": "rift_x64",
        "processId": 25668,
        "targetWindowHandle": "0x320CB0",
        "processStartUtc": "2026-05-30T02:46:41Z",
        "moduleBase": "0x7FF6EE5D0000",
    }
    current_truth = {
        "schemaVersion": 1,
        "kind": "riftreader-current-truth",
        "updatedAtUtc": "2026-05-31T14:23:13Z",
        "status": "old-current-truth",
        "target": {
            **target,
            "lastVerifiedUtc": "2026-05-31T14:23:12Z",
            "verificationSource": "old readback",
        },
        "liveReferenceSurface": {
            "status": "old-status",
            "source": "old source",
            "view": "old view",
            "currentCoordinateFromStaticChainCandidate": {
                "x": 1.0,
                "y": 2.0,
                "z": 3.0,
                "recordedAtUtc": "2026-05-31T14:23:12Z",
            },
            "apiNowStatus": "passed-current-pid-25668-api-now-vs-chain-now",
            "notes": ["existing note"],
        },
        "staticChainStatus": {
            "status": "old-static-status",
            "promotionAllowed": True,
            "primaryCandidate": {
                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                "rootModule": "rift_x64.exe",
                "rootRva": "0x32EBC80",
                "ownerAddress": "0xOLD",
                "coordinateAddress": "0xOLD320",
                "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                "latestPromotedReadbackArtifact": "C:\\old\\coordinate-summary.json",
                "latestCurrentReadbackArtifact": "C:\\old\\coordinate-summary.json",
                "latestCurrentReadbackAtUtc": "2026-05-31T14:23:12Z",
            },
        },
        "staticOwnerFacing": {
            "promotionAllowed": False,
            "primaryCandidate": {},
        },
        "canonicalArtifacts": {
            "latestCurrentPidStaticOwnerReadback": "C:\\old\\coordinate-summary.json",
            "latestCurrentPidNavStateReadback": "C:\\old\\nav-state-summary.json",
        },
    }
    dashboard = {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-pointer-discovery-status",
        "generatedAtUtc": "2026-05-31T15:19:44Z",
        "status": "passed",
        "target": target,
        "sources": {
            "currentTruth": {"freshness": {"status": "stale"}, "status": "loaded"},
            "coordinateReadback": {
                "status": "passed",
                "generatedAtUtc": "2026-05-31T15:19:42Z",
                "path": "scripts\\captures\\static-owner-coordinate-chain-readback-20260531-151942\\summary.json",
                "freshness": {"status": "fresh"},
            },
            "navState": {
                "status": "passed",
                "generatedAtUtc": "2026-05-31T15:19:43Z",
                "path": "scripts\\captures\\static-owner-nav-state-20260531-151943\\summary.json",
                "freshness": {"status": "fresh"},
            },
        },
        "freshness": {"status": "stale", "staleSources": ["currentTruth"]},
        "candidates": {
            "promotedCoordinate": {
                "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed",
                "promotionAllowed": True,
                "candidateOnly": False,
                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                "rootAddress": "0x7FF6F18BBC80",
                "ownerAddress": "0x1B53D7806A0",
                "coordinateAddress": "0x1B53D7809C0",
                "coordinate": {"x": 7264.431640625, "y": 821.6972045898438, "z": 3003.875732421875},
                "latestReadbackStatus": "passed",
                "latestReadbackAtUtc": "2026-05-31T15:19:42Z",
                "latestReadbackJson": "scripts\\captures\\static-owner-coordinate-chain-readback-20260531-151942\\summary.json",
            },
            "candidateFacingTarget": {
                "status": "candidate-only",
                "candidateOnly": True,
                "promotionAllowed": False,
                "ownerAddress": "0x1B53D7806A0",
                "address": "0x1B53D7809D0",
                "latestYawDegrees": 22.962550463694146,
                "evidence": {
                    "navStateJson": "scripts\\captures\\static-owner-nav-state-20260531-151943\\summary.json",
                },
            },
            "candidateTurnRate": {
                "status": "candidate-only",
                "candidateOnly": True,
                "promotionAllowed": False,
            },
        },
        "sourceSafety": {"familySnapshotMovementSent": True, "familySnapshotInputSent": True},
        "safety": {
            "readOnlyArtifactIndex": True,
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
            "gitMutation": False,
            "providerWrites": False,
            "x64dbgAttach": False,
        },
    }
    write_self_test_json(truth_path, current_truth)
    write_self_test_json(dashboard_path, dashboard)
    return truth_path, dashboard_path


def build_self_test_summary() -> dict[str, Any]:
    generated_at_utc = utc_iso()
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def record(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            errors.append(f"{name}:{detail or 'failed'}")

    with tempfile.TemporaryDirectory(prefix="riftreader-current-truth-refresh-plan-self-test-") as temp_dir:
        repo_root = Path(temp_dir)
        truth_path, _dashboard_path = seed_self_test_repo(repo_root)
        original_truth = truth_path.read_text(encoding="utf-8")
        summary = build_current_truth_refresh_plan(
            repo_root,
            generated_at_utc="2026-05-31T15:20:00Z",
        )
        after_truth = truth_path.read_text(encoding="utf-8")

    proposed = as_mapping(summary.get("proposedCurrentTruth"))
    safety = as_mapping(summary.get("safety"))
    facing = as_mapping(proposed.get("staticOwnerFacing"))
    facing_reacquisition = as_mapping(facing.get("latestCurrentReacquisition"))

    record("planner-status-passed", summary.get("status") == "passed", str(summary.get("status")))
    record("proposed-truth-built", bool(proposed), "present" if proposed else "proposedCurrentTruth missing")
    record(
        "tracked-truth-unchanged",
        original_truth == after_truth,
        "unchanged" if original_truth == after_truth else "tracked truth changed during dry run",
    )
    record("tracked-truth-written-false", safety.get("trackedTruthWritten") is False, str(safety.get("trackedTruthWritten")))
    record("movement-sent-false", safety.get("movementSent") is False, str(safety.get("movementSent")))
    record("input-sent-false", safety.get("inputSent") is False, str(safety.get("inputSent")))
    record("proof-promotion-false", safety.get("proofPromotion") is False, str(safety.get("proofPromotion")))
    record("facing-promotion-false", safety.get("facingPromotion") is False, str(safety.get("facingPromotion")))
    record(
        "facing-remains-candidate-only",
        facing_reacquisition.get("promotionPerformed") is False
        and "candidate-only" in str(facing_reacquisition.get("status")),
        json.dumps(facing_reacquisition, sort_keys=True),
    )

    status = "passed" if not errors else "failed"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-current-truth-refresh-plan-self-test",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated_at_utc,
        "status": status,
        "verdict": "self-test-passed" if status == "passed" else "self-test-failed",
        "checks": checks,
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": {
            **safety_flags(),
            "dryRunOnly": True,
            "trackedTruthWritten": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
        },
        "artifacts": {},
        "next": {
            "recommendedAction": "If this self-test passes, run unit tests before changing tracked truth workflow.",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a dry-run current-truth refresh plan.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root; defaults to auto-detect.")
    parser.add_argument("--current-truth-json", default=str(DEFAULT_CURRENT_TRUTH_JSON))
    parser.add_argument("--dashboard-json", default=str(DEFAULT_DASHBOARD_JSON))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--self-test", action="store_true", help="Run a built-in dry-run self-test and exit.")
    parser.add_argument("--write", action="store_true", help="Write ignored plan artifacts.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        summary = build_self_test_summary()
        if args.json:
            print(json_text(summary), end="")
        else:
            print(build_markdown(summary))
        return 0 if summary["status"] == "passed" else 1

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    summary = build_current_truth_refresh_plan(
        repo_root,
        current_truth_json=Path(args.current_truth_json),
        dashboard_json=Path(args.dashboard_json),
    )
    if args.write:
        write_outputs(repo_root, summary, Path(args.output_dir))
    if args.json:
        print(json_text(summary), end="")
    else:
        print(build_markdown(summary))
    if summary["status"] == "failed":
        return 1
    if summary["status"] == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
