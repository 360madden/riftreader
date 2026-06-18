#!/usr/bin/env python3
"""Safe read-only live RIFT state surfaces for the ChatGPT MCP adapter.

This module intentionally does not focus windows, capture frames, click, send
keys, run ProofOnly, promote truth, attach debuggers, or read arbitrary files.
It only reads repo-owned proof artifacts and fixed read-only target-discovery
facts from the existing ``scripts/get-rift-window-targets.cmd`` helper.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import repo_rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    from riftreader_workflow.common import repo_rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
DEFAULT_PROOF_MAX_AGE_SECONDS = 24 * 60 * 60
DEFAULT_PROCESS_NAME = "rift_x64"
CURRENT_PROOF_ANCHOR_REL = Path("docs") / "recovery" / "current-proof-anchor-readback.json"
COORDINATE_RECOVERY_PROFILE_REL = Path("docs") / "recovery" / "coordinate-recovery-profile.json"
TARGET_DISCOVERY_SCRIPT_REL = Path("scripts") / "get-rift-window-targets.cmd"


def live_safety_flags() -> dict[str, Any]:
    """Return the shared no-input/no-debugger/no-provider safety state."""

    return {
        **safety_flags(),
        "readOnlyLiveState": True,
        "targetDiscoveryReadOnly": True,
        "focusSent": False,
        "clickSent": False,
        "windowCaptureSent": False,
        "keysReleased": None,
        "proofOnlyExecuted": False,
        "proofPromotion": False,
        "currentTruthUpdated": False,
        "arbitraryFilesystemRead": False,
        "savedVariablesRead": False,
    }


def _blocked_payload(
    *,
    kind: str,
    blockers: list[str],
    warnings: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": kind,
        "generatedAtUtc": utc_iso(),
        "status": "blocked",
        "ok": False,
        "blockers": blockers,
        "warnings": warnings or [],
        "safety": live_safety_flags(),
    }
    if extra:
        payload.update(extra)
    return payload


def normalize_hwnd(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return f"0x{value:X}"
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.lower().startswith("0x"):
            return f"0x{int(text[2:], 16):X}"
        return f"0x{int(text, 10):X}"
    except ValueError:
        return text.upper() if text.lower().startswith("0x") else text


def normalize_process_name(value: Any) -> str:
    text = str(value or DEFAULT_PROCESS_NAME).strip()
    if text.lower().endswith(".exe"):
        text = text[:-4]
    return text or DEFAULT_PROCESS_NAME


def normalize_pid(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_repo_json(repo_root: Path, relative_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = (repo_root / relative_path).resolve()
    if not path.is_file():
        return None, f"json-artifact-missing:{relative_path.as_posix()}"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - convert artifact parse errors into blockers.
        return None, f"json-artifact-unreadable:{relative_path.as_posix()}:{type(exc).__name__}"
    if not isinstance(value, dict):
        return None, f"json-artifact-not-object:{relative_path.as_posix()}"
    return value, None


def parse_utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def freshness_summary(
    timestamp_value: Any,
    *,
    max_age_seconds: int = DEFAULT_PROOF_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    parsed = parse_utc_datetime(timestamp_value)
    if parsed is None:
        return {
            "status": "blocked",
            "ok": False,
            "sourceTimestampUtc": timestamp_value,
            "ageSeconds": None,
            "maxAgeSeconds": max_age_seconds,
            "blockers": ["proof-anchor-timestamp-missing-or-invalid"],
        }
    age = max(0.0, (now_utc - parsed).total_seconds())
    ok = age <= max_age_seconds
    return {
        "status": "fresh" if ok else "stale",
        "ok": ok,
        "sourceTimestampUtc": parsed.isoformat().replace("+00:00", "Z"),
        "ageSeconds": round(age, 3),
        "maxAgeSeconds": max_age_seconds,
        "blockers": [] if ok else [f"proof-anchor-stale:{int(age)}s>{max_age_seconds}s"],
    }


def discover_rift_window_targets(repo_root: Path, *, process_name: str = DEFAULT_PROCESS_NAME) -> dict[str, Any]:
    """Run the fixed read-only target-discovery helper and parse its JSON."""

    script = repo_root / TARGET_DISCOVERY_SCRIPT_REL
    if not script.is_file():
        return {
            "status": "blocked",
            "ok": False,
            "script": repo_rel(repo_root, script),
            "blockers": ["target-discovery-script-missing"],
            "warnings": [],
            "safety": live_safety_flags(),
        }
    command = ["cmd", "/c", str(script), "-ProcessName", normalize_process_name(process_name), "-Json"]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed repo-owned script with validated args.
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "blocked",
            "ok": False,
            "script": repo_rel(repo_root, script),
            "blockers": ["target-discovery-timeout"],
            "warnings": [],
            "safety": live_safety_flags(),
        }
    except Exception as exc:  # noqa: BLE001 - fail closed for local discovery errors.
        return {
            "status": "blocked",
            "ok": False,
            "script": repo_rel(repo_root, script),
            "blockers": [f"target-discovery-exception:{type(exc).__name__}"],
            "warnings": [],
            "safety": live_safety_flags(),
        }
    if completed.returncode != 0:
        return {
            "status": "blocked",
            "ok": False,
            "script": repo_rel(repo_root, script),
            "exitCode": completed.returncode,
            "blockers": ["target-discovery-exit-nonzero"],
            "warnings": [],
            "stderrPreview": (completed.stderr or "")[:2000],
            "safety": live_safety_flags(),
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {
            "status": "blocked",
            "ok": False,
            "script": repo_rel(repo_root, script),
            "blockers": [f"target-discovery-json-invalid:{exc.msg}"],
            "warnings": [],
            "stdoutPreview": (completed.stdout or "")[:2000],
            "safety": live_safety_flags(),
        }
    if not isinstance(payload, dict):
        return {
            "status": "blocked",
            "ok": False,
            "script": repo_rel(repo_root, script),
            "blockers": ["target-discovery-json-not-object"],
            "warnings": [],
            "safety": live_safety_flags(),
        }
    payload.setdefault("status", "passed" if payload.get("ok") else "blocked")
    payload.setdefault("warnings", [])
    payload.setdefault("blockers", list(payload.get("errors") or []))
    payload["script"] = repo_rel(repo_root, script)
    payload["safety"] = live_safety_flags()
    return payload


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) not in (None, ""):
            return mapping.get(key)
    return None


def _window_process_id(window: dict[str, Any]) -> int | None:
    value = _first_present(window, "ProcessId", "processId", "pid")
    return normalize_pid(value)


def _window_process_name(window: dict[str, Any]) -> str:
    return normalize_process_name(_first_present(window, "ProcessName", "processName"))


def _window_hwnd(window: dict[str, Any]) -> str | None:
    return normalize_hwnd(_first_present(window, "WindowHandleHex", "targetWindowHandle", "hwnd", "WindowHandle"))


def _window_module_base(window: dict[str, Any]) -> str | None:
    return normalize_hwnd(
        _first_present(window, "ModuleBaseAddressHex", "moduleBaseAddressHex", "moduleBase", "ModuleBase")
    )


def compact_window(window: dict[str, Any]) -> dict[str, Any]:
    return {
        "processId": _window_process_id(window),
        "processName": _window_process_name(window),
        "targetWindowHandle": _window_hwnd(window),
        "title": _first_present(window, "Title", "title"),
        "foreground": bool(_first_present(window, "Foreground", "foreground")),
        "responding": _first_present(window, "Responding", "responding"),
        "processStartTime": _first_present(window, "StartTime", "startTime", "processStartTime"),
        "moduleBase": _window_module_base(window),
        "modulePath": _first_present(window, "ModulePath", "modulePath", "ExecutablePath", "executablePath"),
        "rect": {
            "left": _first_present(window, "Left", "left"),
            "top": _first_present(window, "Top", "top"),
            "right": _first_present(window, "Right", "right"),
            "bottom": _first_present(window, "Bottom", "bottom"),
            "width": _first_present(window, "Width", "width"),
            "height": _first_present(window, "Height", "height"),
        },
    }


def _proof_target(proof_anchor: dict[str, Any]) -> dict[str, Any]:
    target = proof_anchor.get("target") if isinstance(proof_anchor.get("target"), dict) else {}
    return {
        "processName": normalize_process_name(target.get("processName")),
        "processId": normalize_pid(target.get("processId")),
        "targetWindowHandle": normalize_hwnd(target.get("targetWindowHandle") or target.get("hwnd")),
    }


def _proof_anchor_summary(repo_root: Path, proof_anchor: dict[str, Any]) -> dict[str, Any]:
    latest_validation = proof_anchor.get("latestValidation") if isinstance(proof_anchor.get("latestValidation"), dict) else {}
    latest_proof_only = proof_anchor.get("latestProofOnly") if isinstance(proof_anchor.get("latestProofOnly"), dict) else {}
    classification = (
        proof_anchor.get("currentTruthClassification")
        if isinstance(proof_anchor.get("currentTruthClassification"), dict)
        else {}
    )
    return {
        "path": repo_rel(repo_root, repo_root / CURRENT_PROOF_ANCHOR_REL),
        "status": proof_anchor.get("status"),
        "lastUpdatedUtc": proof_anchor.get("lastUpdatedUtc"),
        "target": _proof_target(proof_anchor),
        "currentTruthClassification": {
            "classification": classification.get("classification"),
            "sourceOfTruth": classification.get("sourceOfTruth"),
            "savedVariablesUsedAsLiveTruth": classification.get("savedVariablesUsedAsLiveTruth"),
            "noCheatEngine": classification.get("noCheatEngine"),
        },
        "latestValidation": {
            "status": latest_validation.get("status"),
            "movementSent": latest_validation.get("movementSent"),
            "currentCoordinate": latest_validation.get("currentCoordinate"),
            "readbackSummaryFile": latest_validation.get("readbackSummaryFile"),
            "proofAnchorCandidateId": latest_validation.get("proofAnchorCandidateId"),
            "proofAnchorCandidateAddressHex": latest_validation.get("proofAnchorCandidateAddressHex"),
            "generatedAtUtc": latest_validation.get("generatedAtUtc"),
        },
        "latestProofOnly": {
            "status": latest_proof_only.get("status"),
            "generatedAtUtc": latest_proof_only.get("generatedAtUtc"),
            "movementSent": latest_proof_only.get("movementSent"),
            "movementAttempted": latest_proof_only.get("movementAttempted"),
            "currentCoordinate": latest_proof_only.get("currentCoordinate"),
            "runSummaryFile": latest_proof_only.get("runSummaryFile"),
            "readbackSummaryFile": latest_proof_only.get("readbackSummaryFile"),
        },
    }


def build_live_target_identity_gate(
    repo_root: Path,
    *,
    max_proof_age_seconds: int = DEFAULT_PROOF_MAX_AGE_SECONDS,
    discovery_payload: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the Stage 39 exact target gate without sending input."""

    repo_root = repo_root.resolve()
    blockers: list[str] = []
    warnings: list[str] = []
    proof_anchor, proof_error = read_repo_json(repo_root, CURRENT_PROOF_ANCHOR_REL)
    profile, profile_error = read_repo_json(repo_root, COORDINATE_RECOVERY_PROFILE_REL)
    if proof_error:
        blockers.append(f"proof-anchor:{proof_error}")
    if profile_error:
        warnings.append(f"coordinate-profile:{profile_error}")
    if proof_anchor is None:
        return _blocked_payload(
            kind="riftreader-chatgpt-mcp-live-target-identity-gate",
            blockers=blockers,
            warnings=warnings,
            extra={
                "proofAnchor": {"path": repo_rel(repo_root, repo_root / CURRENT_PROOF_ANCHOR_REL)},
                "recommendedNextSafeAction": {
                    "key": "reacquire-current-proof-anchor",
                    "why": "No repo-owned current proof anchor is available for exact PID/HWND gating.",
                    "inputAllowed": False,
                },
            },
        )

    target = _proof_target(proof_anchor)
    proof_summary = _proof_anchor_summary(repo_root, proof_anchor)
    freshness = freshness_summary(
        proof_anchor.get("lastUpdatedUtc"),
        max_age_seconds=max_proof_age_seconds,
        now=now,
    )
    blockers.extend(str(item) for item in freshness.get("blockers") or [])
    if proof_anchor.get("status") != "current-target-proofonly-passed":
        blockers.append(f"proof-anchor-status-not-current-target-proofonly-passed:{proof_anchor.get('status')}")
    latest_proof_only = proof_anchor.get("latestProofOnly") if isinstance(proof_anchor.get("latestProofOnly"), dict) else {}
    if latest_proof_only.get("status") != "passed-proof-only":
        blockers.append(f"proof-only-status-not-passed:{latest_proof_only.get('status')}")
    if latest_proof_only.get("movementSent") is True or latest_proof_only.get("movementAttempted") is True:
        blockers.append("proof-only-recorded-movement-or-attempt")
    if target.get("processId") in (None, ""):
        blockers.append("proof-target-processId-missing")
    if not target.get("targetWindowHandle"):
        blockers.append("proof-target-hwnd-missing")

    discovery = discovery_payload if discovery_payload is not None else discover_rift_window_targets(repo_root, process_name=target["processName"])
    discovery_ok = bool(discovery.get("ok"))
    if not discovery_ok:
        discovery_blockers = discovery.get("blockers") or discovery.get("errors") or ["target-discovery-blocked"]
        blockers.extend(f"target-discovery:{item}" for item in discovery_blockers)

    windows_raw = discovery.get("windows") if isinstance(discovery.get("windows"), list) else []
    windows = [item for item in windows_raw if isinstance(item, dict)]
    expected_pid = target.get("processId")
    expected_hwnd = target.get("targetWindowHandle")
    matches = [
        item
        for item in windows
        if _window_process_id(item) == expected_pid and _window_hwnd(item) == expected_hwnd
    ]
    exact_window = compact_window(matches[0]) if len(matches) == 1 else None
    if discovery_ok and len(matches) != 1:
        blockers.append(f"exact-target-window-match-count-not-one:{len(matches)}")
    if len(windows) > 1:
        warnings.append(f"rift-window-duplicates-detected:{len(windows)}")
    module_base = exact_window.get("moduleBase") if exact_window else None
    process_start = exact_window.get("processStartTime") if exact_window else None
    if exact_window:
        if not process_start:
            blockers.append("exact-target-process-start-missing")
        if not module_base:
            blockers.append("exact-target-module-base-missing")
        if normalize_process_name(exact_window.get("processName")) != normalize_process_name(target.get("processName")):
            blockers.append("exact-target-process-name-mismatch")

    profile_target = profile.get("target") if isinstance(profile, dict) and isinstance(profile.get("target"), dict) else {}
    if profile_target:
        profile_pid = normalize_pid(profile_target.get("pid") or profile_target.get("processId"))
        profile_hwnd = normalize_hwnd(profile_target.get("hwnd") or profile_target.get("targetWindowHandle"))
        if profile_pid not in (None, "", expected_pid):
            warnings.append(f"coordinate-profile-pid-differs:{profile_pid}")
        if profile_hwnd and profile_hwnd != expected_hwnd:
            warnings.append(f"coordinate-profile-hwnd-differs:{profile_hwnd}")

    ok = not blockers
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-live-target-identity-gate",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "stage": 39,
        "stageName": "Live target identity gate",
        "proofAnchor": proof_summary,
        "freshness": freshness,
        "requestedTarget": target,
        "exactTargetFacts": exact_window if ok else None,
        "identityChecks": {
            "proofAnchorCurrent": proof_anchor.get("status") == "current-target-proofonly-passed",
            "proofOnlyPassed": latest_proof_only.get("status") == "passed-proof-only",
            "proofOnlyNoMovement": not (
                latest_proof_only.get("movementSent") is True or latest_proof_only.get("movementAttempted") is True
            ),
            "freshProof": bool(freshness.get("ok")),
            "exactPidHwndMatchCount": len(matches),
            "processStartPresent": bool(process_start),
            "moduleBasePresent": bool(module_base),
        },
        "duplicateDetection": {
            "processName": normalize_process_name(target.get("processName")),
            "windowCount": len(windows),
            "duplicateWindowsDetected": len(windows) > 1,
            "matchedCount": len(matches),
            "windowSummaries": [compact_window(item) for item in windows[:5]],
        },
        "configValidationSummary": {
            "proofAnchorPath": repo_rel(repo_root, repo_root / CURRENT_PROOF_ANCHOR_REL),
            "coordinateRecoveryProfilePath": repo_rel(repo_root, repo_root / COORDINATE_RECOVERY_PROFILE_REL),
            "targetDiscoveryScript": repo_rel(repo_root, repo_root / TARGET_DISCOVERY_SCRIPT_REL),
            "maxProofAgeSeconds": max_proof_age_seconds,
            "usesSavedVariablesAsLiveTruth": False,
        },
        "recommendedNextSafeAction": {
            "key": "inspect-live-no-input-proof-status" if ok else "refresh-no-input-current-target-proof",
            "why": (
                "Exact target identity passed; no-input proof summaries can be inspected."
                if ok
                else "Exact target identity is not safe enough for live proof readback surfaces."
            ),
            "inputAllowed": False,
            "movementAllowed": False,
        },
        "blockers": blockers,
        "warnings": warnings,
        "safety": live_safety_flags(),
    }


def build_live_readonly_state(
    repo_root: Path,
    *,
    max_proof_age_seconds: int = DEFAULT_PROOF_MAX_AGE_SECONDS,
    discovery_payload: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the Stage 38 read-only live RIFT target/status surface."""

    gate = build_live_target_identity_gate(
        repo_root,
        max_proof_age_seconds=max_proof_age_seconds,
        discovery_payload=discovery_payload,
        now=now,
    )
    ok = bool(gate.get("ok"))
    proof_anchor = gate.get("proofAnchor") if isinstance(gate.get("proofAnchor"), dict) else {}
    proof_latest = proof_anchor.get("latestProofOnly") if isinstance(proof_anchor.get("latestProofOnly"), dict) else {}
    validation = proof_anchor.get("latestValidation") if isinstance(proof_anchor.get("latestValidation"), dict) else {}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-live-rift-readonly-state",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "stage": 38,
        "stageName": "Live RIFT read-only state surface",
        "identityGate": {
            "status": gate.get("status"),
            "ok": gate.get("ok"),
            "blockers": gate.get("blockers") or [],
            "warnings": gate.get("warnings") or [],
        },
        "liveState": (
            {
                "target": gate.get("exactTargetFacts"),
                "proofFreshness": gate.get("freshness"),
                "latestProofOnlyStatus": proof_latest.get("status"),
                "latestValidationStatus": validation.get("status"),
                "currentCoordinate": proof_latest.get("currentCoordinate") or validation.get("currentCoordinate"),
            }
            if ok
            else {"withheldUntilIdentityGatePasses": True}
        ),
        "configValidationSummary": gate.get("configValidationSummary"),
        "recommendedNextSafeAction": gate.get("recommendedNextSafeAction"),
        "blockers": list(gate.get("blockers") or []),
        "warnings": list(gate.get("warnings") or []),
        "safety": live_safety_flags(),
    }


def build_live_no_input_proof_status(
    repo_root: Path,
    *,
    max_proof_age_seconds: int = DEFAULT_PROOF_MAX_AGE_SECONDS,
    discovery_payload: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the Stage 40 no-input proof/readback summary behind the identity gate."""

    gate = build_live_target_identity_gate(
        repo_root,
        max_proof_age_seconds=max_proof_age_seconds,
        discovery_payload=discovery_payload,
        now=now,
    )
    ok = bool(gate.get("ok"))
    proof_anchor, proof_error = read_repo_json(repo_root.resolve(), CURRENT_PROOF_ANCHOR_REL)
    proof_summary = {}
    if ok and proof_anchor:
        latest_validation = proof_anchor.get("latestValidation") if isinstance(proof_anchor.get("latestValidation"), dict) else {}
        latest_proof_only = proof_anchor.get("latestProofOnly") if isinstance(proof_anchor.get("latestProofOnly"), dict) else {}
        proof_summary = {
            "target": gate.get("exactTargetFacts"),
            "proofAnchorStatus": proof_anchor.get("status"),
            "latestProofOnly": {
                "status": latest_proof_only.get("status"),
                "generatedAtUtc": latest_proof_only.get("generatedAtUtc"),
                "movementSent": latest_proof_only.get("movementSent"),
                "movementAttempted": latest_proof_only.get("movementAttempted"),
                "currentCoordinate": latest_proof_only.get("currentCoordinate"),
                "coordinateDelta": latest_proof_only.get("coordinateDelta"),
                "runSummaryFile": latest_proof_only.get("runSummaryFile"),
                "readbackSummaryFile": latest_proof_only.get("readbackSummaryFile"),
            },
            "latestValidation": {
                "status": latest_validation.get("status"),
                "movementSent": latest_validation.get("movementSent"),
                "currentCoordinate": latest_validation.get("currentCoordinate"),
                "proofAnchorCandidateId": latest_validation.get("proofAnchorCandidateId"),
                "proofAnchorCandidateAddressHex": latest_validation.get("proofAnchorCandidateAddressHex"),
                "readbackSummaryFile": latest_validation.get("readbackSummaryFile"),
                "proofAnchorFile": latest_validation.get("proofAnchorFile"),
                "generatedAtUtc": latest_validation.get("generatedAtUtc"),
            },
        }
    elif proof_error:
        proof_summary = {"withheldUntilIdentityGatePasses": True, "proofAnchorError": proof_error}
    else:
        proof_summary = {"withheldUntilIdentityGatePasses": True}

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-live-no-input-proof-status",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "stage": 40,
        "stageName": "Live no-input proof tool",
        "identityGate": {
            "status": gate.get("status"),
            "ok": gate.get("ok"),
            "exactTargetFacts": gate.get("exactTargetFacts") if ok else None,
            "freshness": gate.get("freshness"),
        },
        "proofSummary": proof_summary,
        "recommendedNextSafeAction": {
            "key": "design-live-control-plan-only-tool" if ok else "refresh-no-input-current-target-proof",
            "why": (
                "No-input proof state is inspectable; next implementation stage is plan-only live-control design."
                if ok
                else "No-input proof summaries are withheld until the exact target gate passes."
            ),
            "inputAllowed": False,
            "movementAllowed": False,
        },
        "blockers": list(gate.get("blockers") or []),
        "warnings": list(gate.get("warnings") or []),
        "safety": live_safety_flags(),
    }


def self_test() -> dict[str, Any]:
    now = datetime(2026, 6, 18, 6, 30, tzinfo=timezone.utc)
    with_fake_repo = Path.cwd()
    payload = build_live_target_identity_gate(
        with_fake_repo,
        discovery_payload={"ok": False, "blockers": ["self-test-no-live-discovery"], "windows": []},
        now=now,
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-live-rift-state-self-test",
        "status": "passed",
        "ok": True,
        "sampleStatus": payload.get("status"),
        "safety": live_safety_flags(),
        "blockers": [],
        "warnings": [],
    }
