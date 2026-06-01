#!/usr/bin/env python3
"""Audit RiftReader live-input-capable surfaces without touching the game.

This helper is intentionally read-only. It scans repo-owned scripts/tools for
known keyboard/mouse/focus/input primitives and classifies each matching file so
future live runs can distinguish:

- guarded workflow entry points;
- release-only emergency helpers;
- direct input primitives;
- legacy surfaces that still require human review before use;
- debugger/stimulus surfaces that remain forbidden in the current lane.

It does not read target process memory, focus a window, send input, attach a
debugger, mutate provider repos, or mutate Git state.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow.status_packet import proof_anchor_freshness_summary  # noqa: E402


SCHEMA_VERSION = 1
DEFAULT_OUTPUT_ROOT = Path("scripts/captures")
DEFAULT_CURRENT_TRUTH = Path("docs/recovery/current-truth.json")
DEFAULT_CURRENT_PROOF = Path("docs/recovery/current-proof-anchor-readback.json")
SCAN_ROOTS = ("scripts", "tools")
SOURCE_SUFFIXES = {".py", ".ps1", ".cmd", ".bat", ".cs", ".ahk"}
SKIP_PARTS = {
    ".git",
    ".riftreader-local",
    "__pycache__",
    "bin",
    "obj",
    "node_modules",
    "captures",
}


@dataclass(frozen=True)
class TokenPattern:
    key: str
    regex: re.Pattern[str]
    reason: str


TOKEN_PATTERNS: tuple[TokenPattern, ...] = (
    TokenPattern("post-rift-key", re.compile(r"\bpost-rift-key(?:\.ps1|\.cmd)?\b", re.IGNORECASE), "legacy exact-HWND key helper"),
    TokenPattern("send-rift-key", re.compile(r"\bsend-rift-key(?:-[\w]+)?(?:\.ps1|\.cmd)?\b", re.IGNORECASE), "SendInput key helper"),
    TokenPattern("riftreader-sendinput", re.compile(r"RiftReader\.SendInput", re.IGNORECASE), "repo-owned C# SendInput tool"),
    TokenPattern("sendinput-api", re.compile(r"\bSendInput\b", re.IGNORECASE), "Windows SendInput API or wrapper"),
    TokenPattern("use-window-message", re.compile(r"\bUseWindowMessage\b", re.IGNORECASE), "WindowMessage input backend"),
    TokenPattern("window-message", re.compile(r"\bWindowMessage\b", re.IGNORECASE), "WindowMessage input backend"),
    TokenPattern("post-message", re.compile(r"\bPost(?:Thread)?Message\b", re.IGNORECASE), "Windows PostMessage/PostThreadMessage API"),
    TokenPattern("set-foreground-window", re.compile(r"\bSetForegroundWindow\b", re.IGNORECASE), "foreground/focus manipulation"),
    TokenPattern("auto-displacement", re.compile(r"\bauto-displacement\b", re.IGNORECASE), "automated displacement workflow"),
    TokenPattern("allow-game-input", re.compile(r"--allow-game-input\b", re.IGNORECASE), "explicit live-game input override"),
    TokenPattern("stimulus-key", re.compile(r"--stimulus-key\b", re.IGNORECASE), "stimulus key option"),
    TokenPattern("mouse-event", re.compile(r"\b(?:mouse_event|MOUSEEVENTF_\w+|LEFTDOWN|LEFTUP|RIGHTDOWN|RIGHTUP)\b", re.IGNORECASE), "mouse input primitive"),
    TokenPattern("click-action", re.compile(r"\bgame-click\b|[\"']click[\"']", re.IGNORECASE), "click action reference"),
    TokenPattern("sendkeys", re.compile(r"\bSendKeys\b", re.IGNORECASE), "SendKeys input primitive"),
)


KNOWN_SURFACES: dict[str, dict[str, Any]] = {
    "scripts/current_pid_family_snapshot_sequence.py": {
        "classification": "guarded-live-movement",
        "status": "guarded-requires-explicit-override",
        "risk": "high",
        "reviewRequired": False,
        "controls": [
            "current-truth movementGate blocks auto-displacement by default",
            "repo-owned C# SendInput ScanCode is the only allowed diagnostic auto-displacement backend",
            "legacy WindowMessage backend is retired and fails closed",
            "--allow-current-truth-movement-gate-override required to bypass current-truth movement pause",
            "required client geometry gate supports exact 640x360 client validation",
            "pre/post emergency key/mouse release guard is enabled by default",
        ],
        "allowedReusePolicy": "Use for read-only/manual-pose capture by default; live auto-displacement requires explicit reauthorization, current target/geometry gates, and C# ScanCode backend.",
    },
    "scripts/invoke-gated-forward-smoke.ps1": {
        "classification": "guarded-live-movement",
        "status": "guarded-requires-explicit-override",
        "risk": "high",
        "reviewRequired": False,
        "controls": [
            "defaults to repo-owned C# SendInput ScanCode backend",
            "WindowMessage and legacy PowerShell SendInput backends fail closed after the spin incident",
            "exact PID/HWND and freshness gates remain required",
        ],
        "allowedReusePolicy": "Use only after the movement gate is explicitly cleared; the only allowed diagnostic backend is C# ScanCode.",
    },
    "scripts/profile_turn_keys.py": {
        "classification": "guarded-live-input",
        "status": "guarded-requires-explicit-override",
        "risk": "high",
        "reviewRequired": False,
        "controls": [
            "live post-message input returns blocked JSON unless --allow-post-message-input is present",
            "summary records inputSent/movementSent false when blocked",
        ],
        "allowedReusePolicy": "Safe for dry-run/blocked guard checks; live input requires explicit reauthorization.",
    },
    "scripts/rift_live_test/turn_keys.py": {
        "classification": "guarded-live-input-library",
        "status": "guarded-requires-explicit-override",
        "risk": "high",
        "reviewRequired": False,
        "controls": ["post-message live input requires allow_post_message_input=True"],
        "allowedReusePolicy": "Library only; callers must keep explicit live-input override gates.",
    },
    "scripts/rift_emergency_key_release.py": {
        "classification": "release-only",
        "status": "release-only-up-events",
        "risk": "medium",
        "reviewRequired": False,
        "controls": ["keyup/mouse-up only; no key-down/mouse-down"],
        "allowedReusePolicy": "Allowed as emergency release/cleanup helper; still exact-target only.",
    },
    "scripts/rift_live_test/emergency_key_release.py": {
        "classification": "release-only",
        "status": "release-only-up-events",
        "risk": "medium",
        "reviewRequired": False,
        "controls": ["keyup/mouse-up only; no key-down/mouse-down"],
        "allowedReusePolicy": "Allowed as emergency release/cleanup helper; still exact-target only.",
    },
    "scripts/riftreader-emergency-release.cmd": {
        "classification": "release-only-launcher",
        "status": "release-only-up-events",
        "risk": "medium",
        "reviewRequired": False,
        "controls": ["thin launcher for release-only helper"],
        "allowedReusePolicy": "Allowed as emergency release/cleanup launcher when exact PID/HWND is supplied.",
    },
    "scripts/live_test.py": {
        "classification": "profile-gated-live-test-orchestrator",
        "status": "profile-dependent",
        "risk": "high",
        "reviewRequired": True,
        "controls": ["ProofOnly is no-input; other profiles require profile-specific review"],
        "allowedReusePolicy": "Use ProofOnly only for no-input proof refresh unless a live movement profile is explicitly reauthorized.",
    },
    "scripts/post-rift-key.ps1": {
        "classification": "input-primitive",
        "status": "direct-live-input-capable",
        "risk": "high",
        "reviewRequired": True,
        "controls": ["exact-target parameters exist but this helper can send key down/up"],
        "allowedReusePolicy": "Do not invoke directly from recovery automation until input-backend incident review is complete.",
    },
    "scripts/post-rift-key.cmd": {
        "classification": "input-primitive-launcher",
        "status": "direct-live-input-capable",
        "risk": "high",
        "reviewRequired": True,
        "controls": ["launcher for post-rift-key.ps1"],
        "allowedReusePolicy": "Do not invoke directly from recovery automation until input-backend incident review is complete.",
    },
    "scripts/send-rift-key.ps1": {
        "classification": "input-primitive",
        "status": "direct-live-input-capable",
        "risk": "high",
        "reviewRequired": True,
        "controls": ["foreground SendInput primitive"],
        "allowedReusePolicy": "Direct operator/calibration use only after explicit reauthorization.",
    },
    "scripts/send-rift-key-csharp.ps1": {
        "classification": "input-primitive-launcher",
        "status": "direct-live-input-capable",
        "risk": "high",
        "reviewRequired": True,
        "controls": ["launcher for repo-owned C# SendInput primitive"],
        "allowedReusePolicy": "Direct operator/calibration use only after explicit reauthorization.",
    },
    "tools/RiftReader.SendInput/Program.cs": {
        "classification": "input-primitive",
        "status": "direct-live-input-capable",
        "risk": "high",
        "reviewRequired": True,
        "controls": ["repo-owned C# SendInput primitive; can press/release keys"],
        "allowedReusePolicy": "Primitive only; caller must provide exact target and explicit movement authorization.",
    },
    "scripts/capture_x64dbg_coord_copy_probe_batch.py": {
        "classification": "debugger-stimulus-surface",
        "status": "forbidden-without-current-authorization",
        "risk": "critical",
        "reviewRequired": True,
        "controls": ["x64dbg/allow-game-input/stimulus workflow is outside current safe lane"],
        "allowedReusePolicy": "Do not use unless user explicitly reauthorizes live debugger and game input in the current turn.",
    },
    "scripts/live_input_surface_audit.py": {
        "classification": "read-only-audit-helper",
        "status": "read-only-audit",
        "risk": "low",
        "reviewRequired": False,
        "controls": ["scans source text only; sends no input and performs no live process operations"],
        "allowedReusePolicy": "Safe to run for repo input-surface inventory.",
    },
    "tools/riftreader_workflow/opencode_bridge.py": {
        "classification": "policy-reference",
        "status": "read-only-policy-reference",
        "risk": "low",
        "reviewRequired": False,
        "controls": ["contains bridge policy text that denies live input/click/movement helpers"],
        "allowedReusePolicy": "Safe as policy/config reference; does not authorize live input.",
    },
    "tools/riftreader_workflow/operator_lite.py": {
        "classification": "guarded-operator-tooling",
        "status": "guarded-live-actions-disabled",
        "risk": "medium",
        "reviewRequired": False,
        "controls": ["safe-arg deny list includes send-rift-key/post-rift-key patterns"],
        "allowedReusePolicy": "Safe to inspect/use with live action buttons disabled; do not bypass deny list.",
    },
    "tools/riftreader_workflow/package_manifest.py": {
        "classification": "policy-reference",
        "status": "read-only-policy-reference",
        "risk": "low",
        "reviewRequired": False,
        "controls": ["package deny list includes send-rift-key/post-rift-key patterns"],
        "allowedReusePolicy": "Safe as package-policy reference; does not authorize live input.",
    },
    "tools/riftreader_workflow/tool_catalog.py": {
        "classification": "policy-reference",
        "status": "read-only-policy-reference",
        "risk": "low",
        "reviewRequired": False,
        "controls": ["catalogs input-capable tools by name only; sends no input and runs no live tooling"],
        "allowedReusePolicy": "Safe as a read-only tool-routing reference; it does not authorize live input.",
    },
    "tools/RiftReader.WindowTools/Program.cs": {
        "classification": "repo-window-tool-input-capable",
        "status": "direct-live-input-capable",
        "risk": "high",
        "reviewRequired": True,
        "controls": [
            "inspect/resize/click require an explicit HWND and support expected PID/process/title checks",
            "click refuses non-foreground or minimized windows and supports dry-run mode",
            "resize avoids activation; click can send SetCursorPos plus SendInput mouse events",
        ],
        "allowedReusePolicy": "Use inspect and dry-run modes for target verification; resize/click remain explicit window-control live-input actions only after exact target and visual gates.",
    },
    "tools/rift-game-mcp/helpers/window-tools.ps1": {
        "classification": "external-local-mcp-input-capable",
        "status": "direct-live-input-capable",
        "risk": "high",
        "reviewRequired": True,
        "controls": ["MCP helper supports focus/click/send-key actions"],
        "allowedReusePolicy": "Use only through explicit rift-window-control workflow and exact-bound target gates.",
    },
}


def make_disposition(
    key: str,
    *,
    label: str,
    operator_action: str,
    approval_boundary: str,
    required_gates: list[str],
    autonomous_safe_use: bool = False,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "operatorAction": operator_action,
        "approvalBoundary": approval_boundary,
        "requiredGates": required_gates,
        "autonomousSafeUse": autonomous_safe_use,
        "notes": notes or [],
    }


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def default_safety() -> dict[str, bool]:
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "targetMemoryBytesRead": False,
        "targetMemoryBytesWritten": False,
        "providerWrites": False,
        "gitMutation": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "savedVariablesUsedAsLiveTruth": False,
    }


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "docs" / "recovery").exists():
            return candidate
    return current


def repo_rel(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def read_json_document(repo_root: Path, document_path: Path) -> dict[str, Any]:
    path = document_path if document_path.is_absolute() else repo_root / document_path
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - audit must not fail just because docs are malformed.
        return {}
    return value if isinstance(value, dict) else {}


def summarize_current_truth_gate(
    document: dict[str, Any],
    proof_document: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    movement_gate = document.get("movementGate") if isinstance(document.get("movementGate"), dict) else {}
    live_incident = movement_gate.get("liveInputIncident") if isinstance(movement_gate.get("liveInputIncident"), dict) else {}
    target = document.get("target") if isinstance(document.get("target"), dict) else {}
    client_geometry = target.get("clientGeometry") if isinstance(target.get("clientGeometry"), dict) else {}
    proof = proof_document if isinstance(proof_document, dict) else {}
    proof_latest_validation = proof.get("latestValidation") if isinstance(proof.get("latestValidation"), dict) else {}
    proof_latest_proofonly = proof.get("latestProofOnly") if isinstance(proof.get("latestProofOnly"), dict) else {}
    proof_freshness = proof_anchor_freshness_summary(proof, proof_latest_validation, proof_latest_proofonly, now=now)
    movement_allowed = movement_gate.get("allowed")
    movement_status = movement_gate.get("status")
    movement_reason = movement_gate.get("reason")
    movement_paused = bool(movement_gate.get("automationMovementPaused") or live_incident.get("automationMovementPaused"))
    proof_status = str(proof.get("status") or "")
    proof_supports_movement_gate = (
        proof_latest_validation.get("movementAllowed") is True
        or proof_status == "current-target-proofonly-passed"
        or str(proof_latest_proofonly.get("status") or "") == "passed-proof-only"
    )
    proof_freshness_blocker = None
    if movement_allowed is True and proof_supports_movement_gate and proof_freshness.get("status") != "fresh":
        age = proof_freshness.get("ageSeconds")
        max_age = proof_freshness.get("maxAgeSeconds")
        if proof_freshness.get("status") == "stale":
            movement_status = "blocked-proof-anchor-age-out-of-range"
            movement_reason = (
                "Current-truth movement status was historically allowed, but the proof-anchor/readback timestamp "
                f"is now outside the movement preflight freshness budget ({age}s > {max_age}s). "
                "Run a fresh same-target ProofOnly/proof-anchor refresh before any movement."
            )
            proof_freshness_blocker = f"proof-anchor-stale-for-movement:ageSeconds={age};maxAgeSeconds={max_age}"
        elif proof_freshness.get("status") == "future-clock-skew":
            movement_status = "blocked-proof-anchor-clock-skew"
            movement_reason = (
                "Current-truth movement status was historically allowed, but the proof-anchor/readback timestamp "
                "appears to be in the future. Recheck clock/target state and rerun same-target ProofOnly before movement."
            )
            proof_freshness_blocker = f"proof-anchor-clock-skew-for-movement:ageSeconds={age};maxAgeSeconds={max_age}"
        else:
            movement_status = "blocked-proof-anchor-freshness-unknown"
            movement_reason = (
                "Current-truth movement status was historically allowed, but no parseable proof-anchor/readback freshness "
                "timestamp is available. Run a fresh same-target ProofOnly/proof-anchor refresh before any movement."
            )
            proof_freshness_blocker = "proof-anchor-freshness-unknown-for-movement"
        movement_allowed = False
        movement_paused = True
    return {
        "movementGate": {
            "allowed": movement_allowed,
            "status": movement_status,
            "reason": movement_reason,
            "automationMovementPaused": movement_paused,
            "liveInputIncidentStatus": live_incident.get("status"),
            "proofFreshness": proof_freshness,
            "proofFreshnessBlocker": proof_freshness_blocker,
        },
        "clientGeometry": {
            "requiredClientWidth": client_geometry.get("requiredClientWidth"),
            "requiredClientHeight": client_geometry.get("requiredClientHeight"),
            "lastVerifiedAtUtc": client_geometry.get("lastVerifiedAtUtc"),
            "policy": client_geometry.get("policy"),
        },
    }


def should_skip_path(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def iter_source_files(repo_root: Path, roots: list[str] | None = None) -> list[Path]:
    found: list[Path] = []
    for root_name in roots or list(SCAN_ROOTS):
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or should_skip_path(path):
                continue
            if path.suffix.lower() in SOURCE_SUFFIXES:
                found.append(path.resolve())
    return sorted(found, key=lambda item: repo_rel(repo_root, item).lower())


def collect_evidence(path: Path, *, max_evidence_per_file: int = 12) -> tuple[list[dict[str, Any]], set[str]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception as exc:  # noqa: BLE001
        return ([{"line": None, "token": "read-error", "reason": type(exc).__name__, "text": str(exc)[:180]}], {"read-error"})

    evidence: list[dict[str, Any]] = []
    tokens: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        for pattern in TOKEN_PATTERNS:
            if not pattern.regex.search(line):
                continue
            tokens.add(pattern.key)
            if len(evidence) < max_evidence_per_file:
                evidence.append(
                    {
                        "line": line_number,
                        "token": pattern.key,
                        "reason": pattern.reason,
                        "text": line.strip()[:220],
                    }
                )
    return evidence, tokens


def is_test_or_fixture(rel_path: str) -> bool:
    name = Path(rel_path).name.lower()
    return name.startswith("test") or "/tests/" in rel_path.lower() or "\\tests\\" in rel_path.lower()


def classify_surface(rel_path: str, tokens: set[str]) -> dict[str, Any]:
    if rel_path in KNOWN_SURFACES:
        return dict(KNOWN_SURFACES[rel_path])

    lower = rel_path.lower()
    if is_test_or_fixture(rel_path):
        return {
            "classification": "test-reference-only",
            "status": "test-reference-only",
            "risk": "low",
            "reviewRequired": False,
            "controls": ["test/fixture reference; not a production workflow entry point"],
            "allowedReusePolicy": "Safe for unit-test validation only; do not infer live-input authorization from tests.",
        }

    if "x64dbg" in lower or "cheat" in lower or {"allow-game-input", "stimulus-key"} & tokens:
        return {
            "classification": "debugger-or-stimulus-surface",
            "status": "forbidden-without-current-authorization",
            "risk": "critical",
            "reviewRequired": True,
            "controls": ["debugger/stimulus/input lane requires explicit current-turn authorization"],
            "allowedReusePolicy": "Do not use in the current recovery lane.",
        }

    if lower.endswith(".cmd") and any(token in tokens for token in ("post-rift-key", "send-rift-key", "riftreader-sendinput")):
        return {
            "classification": "input-launcher",
            "status": "direct-live-input-capable",
            "risk": "high",
            "reviewRequired": True,
            "controls": ["launcher references a live-input primitive"],
            "allowedReusePolicy": "Review launcher target and require explicit operator authorization before use.",
        }

    if any(token in tokens for token in ("sendinput-api", "post-message", "sendkeys", "mouse-event")):
        return {
            "classification": "input-capable-code",
            "status": "legacy-review-required",
            "risk": "high",
            "reviewRequired": True,
            "controls": ["input API/reference detected but no dedicated guard classification is known"],
            "allowedReusePolicy": "Treat as not authorized for autonomous live use until reviewed and guarded.",
        }

    if any(token in tokens for token in ("post-rift-key", "send-rift-key", "use-window-message", "window-message", "auto-displacement")):
        return {
            "classification": "input-workflow-reference",
            "status": "legacy-review-required",
            "risk": "medium",
            "reviewRequired": True,
            "controls": ["references an input workflow or backend but no dedicated guard classification is known"],
            "allowedReusePolicy": "Review before live use; do not assume safety from references alone.",
        }

    if "set-foreground-window" in tokens or "click-action" in tokens:
        return {
            "classification": "focus-or-click-reference",
            "status": "review-required",
            "risk": "medium",
            "reviewRequired": True,
            "controls": ["focus/click reference detected"],
            "allowedReusePolicy": "Review before live use.",
        }

    return {
        "classification": "unclassified-token-match",
        "status": "review-required",
        "risk": "medium",
        "reviewRequired": True,
        "controls": ["token match needs manual classification"],
        "allowedReusePolicy": "Review before live use.",
    }


def recommend_surface_disposition(rel_path: str, tokens: set[str], classification: dict[str, Any]) -> dict[str, Any]:
    classification_name = str(classification.get("classification") or "")
    status = str(classification.get("status") or "")
    risk = str(classification.get("risk") or "")
    lower = rel_path.lower()

    if classification_name in {"read-only-audit-helper", "policy-reference"}:
        return make_disposition(
            "read-only-policy-reference",
            label="Read-only policy/reference surface",
            operator_action="Safe to inspect and run only as documented read-only policy tooling.",
            approval_boundary="none",
            required_gates=["do not use policy references as live-input authorization"],
            autonomous_safe_use=True,
        )

    if classification_name == "test-reference-only":
        return make_disposition(
            "test-reference-only",
            label="Test or fixture reference",
            operator_action="Use only for unit-test validation; do not route operator workflows through it.",
            approval_boundary="none",
            required_gates=["test/fixture scope only"],
            autonomous_safe_use=True,
        )

    if classification_name.startswith("release-only"):
        return make_disposition(
            "release-only-exact-target",
            label="Emergency release-only helper",
            operator_action="Keep available for exact-target key-up/mouse-up cleanup; do not treat it as movement authorization.",
            approval_boundary="emergency-release-exact-target",
            required_gates=[
                "exact PID/HWND target",
                "release/up events only",
                "no key-down, mouse-down, or movement stimulus",
            ],
        )

    if status.startswith("guarded") or classification_name.startswith("guarded") or classification_name.startswith("profile-gated"):
        return make_disposition(
            "guarded-entrypoint-approval-only",
            label="Guarded live-capable entry point",
            operator_action="Use dry-run/no-input modes freely; live profiles still require explicit current-turn approval and proof gates.",
            approval_boundary="live-input-or-movement",
            required_gates=[
                "fresh exact PID/HWND/process-start target",
                "fresh API-now vs memory-now coordinate readback where coordinate-driven",
                "movement/input approval in current turn",
                "post-run no-stuck-key release/readback",
            ],
        )

    if "debugger" in classification_name or risk == "critical" or "x64dbg" in lower or {"allow-game-input", "stimulus-key"} & tokens:
        return make_disposition(
            "forbidden-unless-live-debugger-and-input-approved",
            label="Debugger/stimulus surface",
            operator_action="Do not run in autonomous safe/offline lanes; require explicit live debugger plus input approval.",
            approval_boundary="live-debugger-and-input",
            required_gates=[
                "user acknowledges x64dbg/CE crash risk in current turn",
                "exact target identity",
                "explicit game-input/stimulus approval",
                "bounded capture plan and stop conditions",
            ],
        )

    if classification_name == "external-local-mcp-input-capable":
        return make_disposition(
            "external-window-tool-explicit-target-only",
            label="External local window/input helper",
            operator_action="Use only through the rift-window-control workflow after exact bind/focus/capture verification.",
            approval_boundary="rift-window-control-live-input",
            required_gates=[
                "current rift-window-control bind",
                "exact target verification",
                "explicit live input approval",
                "visual/readback confirmation after action",
            ],
        )

    if classification_name == "repo-window-tool-input-capable":
        return make_disposition(
            "repo-window-tool-explicit-target-only",
            label="Repo window/control primitive",
            operator_action="Use inspect and dry-run modes for verification; resize/click still require exact-bound window-control approval.",
            approval_boundary="window-control-live-input",
            required_gates=[
                "fresh exact PID/HWND/process/title target",
                "foreground/focus and minimized-state check before click",
                "explicit resize/click approval in the current turn",
                "visual/readback confirmation after action",
            ],
        )

    if status == "direct-live-input-capable" or classification_name in {"input-primitive", "input-primitive-launcher", "input-launcher"}:
        return make_disposition(
            "direct-input-primitive-explicit-approval-only",
            label="Direct live-input primitive",
            operator_action="Do not invoke directly from automation; wrap behind exact-target gates and current-turn live-input approval.",
            approval_boundary="live-input",
            required_gates=[
                "fresh exact PID/HWND target",
                "approved backend",
                "explicit input/movement authorization",
                "pre/post emergency release guard",
            ],
        )

    if {"post-message", "use-window-message", "window-message"} & tokens:
        return make_disposition(
            "legacy-window-message-retire-or-wrap",
            label="Legacy WindowMessage/PostMessage surface",
            operator_action="Prefer retirement or a guarded Python/C# wrapper; do not use as an autonomous live backend.",
            approval_boundary="legacy-live-input-review",
            required_gates=[
                "incident review completed",
                "exact target identity",
                "explicit live input approval",
                "bounded readback proving no spin/stuck input",
            ],
        )

    if {"click-action", "mouse-event", "set-foreground-window"} & tokens:
        return make_disposition(
            "focus-click-manual-review-required",
            label="Focus/click-capable surface",
            operator_action="Review manually and route through exact-bound window-control helpers before any live use.",
            approval_boundary="focus-or-click-live-input",
            required_gates=[
                "exact target window",
                "foreground/focus drift check",
                "explicit click/focus approval",
                "visual confirmation",
            ],
        )

    if {"sendinput-api", "riftreader-sendinput", "send-rift-key"} & tokens:
        return make_disposition(
            "guarded-sendinput-wrapper-required",
            label="SendInput-capable surface",
            operator_action="Keep as a primitive or calibration tool only; route through approved exact-target guarded wrappers.",
            approval_boundary="live-input",
            required_gates=[
                "fresh exact PID/HWND target",
                "C# ScanCode backend where movement is involved",
                "explicit live input approval",
                "post-action readback/release check",
            ],
        )

    if classification_name == "input-workflow-reference":
        return make_disposition(
            "workflow-reference-review-required",
            label="Input workflow reference",
            operator_action="Review the referenced workflow before routing or reuse; references alone are not authorization.",
            approval_boundary="workflow-review",
            required_gates=[
                "identify referenced live backend",
                "confirm exact-target gates",
                "explicit approval before live use",
            ],
        )

    return make_disposition(
        "manual-review-required",
        label="Manual review required",
        operator_action="Classify the surface and add an explicit guard or policy entry before any live use.",
        approval_boundary="manual-review",
        required_gates=["human classification", "explicit authorization before live use"],
    )


def audit_files(repo_root: Path, files: list[Path], *, max_evidence_per_file: int = 12) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    for path in files:
        evidence, tokens = collect_evidence(path, max_evidence_per_file=max_evidence_per_file)
        if not tokens:
            continue
        rel_path = repo_rel(repo_root, path)
        classification = classify_surface(rel_path, tokens)
        disposition = recommend_surface_disposition(rel_path, tokens, classification)
        surfaces.append(
            {
                "path": rel_path,
                "tokens": sorted(tokens),
                "evidence": evidence,
                **classification,
                "recommendedDisposition": disposition,
            }
        )
    return surfaces


def summarize_surfaces(surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = Counter(str(item.get("classification")) for item in surfaces)
    statuses = Counter(str(item.get("status")) for item in surfaces)
    risks = Counter(str(item.get("risk")) for item in surfaces)
    dispositions = Counter(str(item.get("recommendedDisposition", {}).get("key", "missing")) for item in surfaces)
    review_required = [item for item in surfaces if item.get("reviewRequired")]
    review_dispositions = Counter(
        str(item.get("recommendedDisposition", {}).get("key", "missing")) for item in review_required
    )
    guarded = [item for item in surfaces if str(item.get("status", "")).startswith("guarded")]
    release_only = [item for item in surfaces if str(item.get("classification", "")).startswith("release-only")]
    critical = [item for item in surfaces if item.get("risk") == "critical"]
    review_disposition_groups: dict[str, list[str]] = {}
    for item in review_required:
        key = str(item.get("recommendedDisposition", {}).get("key", "missing"))
        review_disposition_groups.setdefault(key, []).append(str(item.get("path")))
    return {
        "surfaceCount": len(surfaces),
        "reviewRequiredCount": len(review_required),
        "guardedCount": len(guarded),
        "releaseOnlyCount": len(release_only),
        "criticalCount": len(critical),
        "byClassification": dict(sorted(classifications.items())),
        "byStatus": dict(sorted(statuses.items())),
        "byRisk": dict(sorted(risks.items())),
        "byRecommendedDisposition": dict(sorted(dispositions.items())),
        "reviewRequiredByDisposition": dict(sorted(review_dispositions.items())),
        "reviewRequiredDispositionGroups": {key: sorted(paths) for key, paths in sorted(review_disposition_groups.items())},
        "reviewRequiredPaths": [str(item.get("path")) for item in review_required],
        "criticalPaths": [str(item.get("path")) for item in critical],
    }


def render_markdown(summary: dict[str, Any]) -> str:
    counts = summary.get("counts", {})
    lines = [
        "# Live input surface audit",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Surfaces found: `{counts.get('surfaceCount', 0)}`",
        f"- Review-required surfaces: `{counts.get('reviewRequiredCount', 0)}`",
        f"- Guarded surfaces: `{counts.get('guardedCount', 0)}`",
        f"- Release-only surfaces: `{counts.get('releaseOnlyCount', 0)}`",
        f"- Critical/forbidden surfaces: `{counts.get('criticalCount', 0)}`",
        "- Safety: no input, no movement, no live memory read, no CE/x64dbg attach, no provider writes, no Git mutation.",
        "",
        "## Current-truth gates",
        "",
        f"- Movement allowed: `{summary.get('currentTruthGates', {}).get('movementGate', {}).get('allowed')}`",
        f"- Movement gate status: `{summary.get('currentTruthGates', {}).get('movementGate', {}).get('status')}`",
        f"- Automation movement paused: `{summary.get('currentTruthGates', {}).get('movementGate', {}).get('automationMovementPaused')}`",
        f"- Required client geometry: `{summary.get('currentTruthGates', {}).get('clientGeometry', {}).get('requiredClientWidth')}x{summary.get('currentTruthGates', {}).get('clientGeometry', {}).get('requiredClientHeight')}`",
        "",
        "## Surfaces",
        "",
        "| Path | Classification | Status | Risk | Review? | Disposition | Evidence tokens |",
        "|---|---|---|---|---:|---|---|",
    ]
    for item in summary.get("surfaces", []):
        tokens = ", ".join(f"`{token}`" for token in item.get("tokens", [])[:8])
        disposition = item.get("recommendedDisposition", {}).get("key")
        lines.append(
            f"| `{item.get('path')}` | `{item.get('classification')}` | `{item.get('status')}` | "
            f"`{item.get('risk')}` | `{bool(item.get('reviewRequired'))}` | `{disposition}` | {tokens} |"
        )

    review_groups = counts.get("reviewRequiredDispositionGroups") or {}
    if review_groups:
        lines.extend(["", "## Review-required disposition groups", ""])
        for key, paths in review_groups.items():
            lines.append(f"- `{key}`: `{len(paths)}`")

    review_paths = counts.get("reviewRequiredPaths") or []
    if review_paths:
        lines.extend(["", "## Review-required paths", ""])
        for path in review_paths[:40]:
            lines.append(f"- `{path}`")
    return "\n".join(lines)


def build_summary(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if args.self_test:
        result = self_test()
        return (0 if result["status"] == "passed" else 1), result

    repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
    roots = args.scan_root if args.scan_root else list(SCAN_ROOTS)
    files = iter_source_files(repo_root, roots)
    surfaces = audit_files(repo_root, files, max_evidence_per_file=max(1, args.max_evidence_per_file))
    counts = summarize_surfaces(surfaces)
    current_proof_json = getattr(args, "current_proof_json", DEFAULT_CURRENT_PROOF)
    current_truth = summarize_current_truth_gate(
        read_json_document(repo_root, args.current_truth_json),
        read_json_document(repo_root, current_proof_json),
    )
    status = "passed-with-review-required" if counts["reviewRequiredCount"] else "passed"
    warnings: list[str] = []
    if counts["reviewRequiredCount"]:
        warnings.append(f"review-required-surfaces:{counts['reviewRequiredCount']}")
    if counts["criticalCount"]:
        warnings.append(f"critical-forbidden-surfaces:{counts['criticalCount']}")

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-live-input-surface-audit",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "blockers": [],
        "warnings": warnings,
        "errors": [],
        "repoRoot": str(repo_root),
        "scanRoots": roots,
        "skippedDirectoryNames": sorted(SKIP_PARTS),
        "currentTruthGates": current_truth,
        "counts": counts,
        "surfaces": surfaces,
        "safety": default_safety(),
        "next": {
            "recommendedAction": (
                "Keep current movement automation paused; review direct/legacy input primitives before any future live movement run."
                if counts["reviewRequiredCount"]
                else "No review-required input surfaces were detected by this audit."
            )
        },
    }

    output_root = args.output_root.resolve() if args.output_root else repo_root / DEFAULT_OUTPUT_ROOT
    run_dir = output_root / f"live-input-surface-audit-{utc_stamp()}"
    summary_path = run_dir / "summary.json"
    markdown_path = run_dir / "summary.md"
    summary["artifacts"] = {
        "runDirectory": str(run_dir),
        "summaryJson": str(summary_path),
        "summaryMarkdown": str(markdown_path),
    }
    write_json(summary_path, summary)
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return 0, summary


def self_test() -> dict[str, Any]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        guarded = root / "scripts" / "current_pid_family_snapshot_sequence.py"
        primitive = root / "scripts" / "post-rift-key.ps1"
        legacy = root / "scripts" / "legacy-wrapper.py"
        test_file = root / "scripts" / "test_legacy_wrapper.py"
        debugger = root / "scripts" / "capture_x64dbg_coord_copy_probe_batch.py"
        for path, text in {
            guarded: "parser.add_argument('--allow-window-message-auto-displacement')\n# auto-displacement\n",
            primitive: "RiftKeyNative::SendInput($input)\n",
            legacy: "subprocess.run(['powershell', 'post-rift-key.ps1', '-UseWindowMessage'])\n",
            test_file: "self.assertIn('send-rift-key.ps1', command)\n",
            debugger: "command.append('--allow-game-input')\ncommand.append('--stimulus-key')\n",
        }.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        surfaces = audit_files(root, iter_source_files(root))
        by_path = {item["path"]: item for item in surfaces}
        expectations = {
            "scripts/current_pid_family_snapshot_sequence.py": "guarded-live-movement",
            "scripts/post-rift-key.ps1": "input-primitive",
            "scripts/legacy-wrapper.py": "input-workflow-reference",
            "scripts/test_legacy_wrapper.py": "test-reference-only",
            "scripts/capture_x64dbg_coord_copy_probe_batch.py": "debugger-stimulus-surface",
        }
        for rel_path, expected in expectations.items():
            actual = by_path.get(rel_path, {}).get("classification")
            if actual != expected:
                errors.append(f"classification-mismatch:{rel_path}:{actual}!={expected}")
        if any(item.get("safety", {}).get("movementSent") for item in surfaces):
            errors.append("surface-should-not-include-live-safety-mutation")
        counts = summarize_surfaces(surfaces)
        if counts["reviewRequiredCount"] < 3:
            errors.append(f"review-count-too-low:{counts['reviewRequiredCount']}")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-live-input-surface-audit-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "safety": default_safety(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only audit of RiftReader live-input-capable surfaces.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--current-truth-json", type=Path, default=DEFAULT_CURRENT_TRUTH)
    parser.add_argument("--current-proof-json", type=Path, default=DEFAULT_CURRENT_PROOF)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--scan-root", action="append", default=None, help="Repo-relative root to scan. Defaults to scripts and tools.")
    parser.add_argument("--max-evidence-per-file", type=int, default=12)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        exit_code, summary = build_summary(args)
    except Exception as exc:  # noqa: BLE001
        exit_code = 1
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "riftreader-live-input-surface-audit",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "blockers": [],
            "warnings": [],
            "errors": [{"type": type(exc).__name__, "message": str(exc)}],
            "safety": default_safety(),
        }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": summary.get("status"),
                    "warnings": summary.get("warnings"),
                    "summaryJson": summary.get("artifacts", {}).get("summaryJson"),
                }
            )
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
