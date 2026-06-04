#!/usr/bin/env python3
"""Build a deterministic local ChatGPT/non-Codex status packet for RiftReader.

The status packet is intentionally safe:

- no live input;
- no movement;
- no CE/x64dbg attach;
- no provider writes;
- no Git staging/commit/push;
- optional writes only under ignored `.riftreader-local/`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import (
        find_repo_root,
        preview_text,
        repo_rel as as_repo_path,
        run_command_envelope,
        safety_flags,
        timestamped_output_dir,
        unique,
        utc_iso,
    )
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import (
        find_repo_root,
        preview_text,
        repo_rel as as_repo_path,
        run_command_envelope,
        safety_flags,
        timestamped_output_dir,
        unique,
        utc_iso,
    )


DEFAULT_CURRENT_TRUTH_MD = Path("docs") / "recovery" / "current-truth.md"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_CURRENT_PROOF_JSON = Path("docs") / "recovery" / "current-proof-anchor-readback.json"
DEFAULT_HANDOFF_DIR = Path("docs") / "handoffs"
DEFAULT_STATIC_OWNER_CAPTURE_DIR = Path("scripts") / "captures"
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "workflow-status"
DEFAULT_LAUNCHER_INSPECTION_DIR = Path(".riftreader-local") / "launcher-inspection"
DEFAULT_CHARACTER_LOGIN_SUPERVISOR_DIR = Path(".riftreader-local") / "character-login-supervisor"
DEFAULT_NAVIGATION_POINTER_DISCOVERY_SUMMARY = (
    Path(".riftreader-local") / "navigation-pointer-discovery" / "latest" / "summary.json"
)
DEFAULT_CURRENT_TRUTH_REFRESH_PLAN_SUMMARY = (
    Path(".riftreader-local") / "current-truth-refresh-plan" / "latest" / "summary.json"
)
DEFAULT_CURRENT_TRUTH_REFRESH_APPLY_SUMMARY = (
    Path(".riftreader-local") / "current-truth-refresh-apply" / "latest" / "summary.json"
)
DEFAULT_FACING_PROMOTION_READINESS_REVIEW_PREFIX = "facing-target-promotion-readiness-review"
DEFAULT_LAUNCHER_INSPECTION_MAX_AGE_SECONDS = 30 * 60
DEFAULT_STATIC_OWNER_READBACK_MAX_AGE_SECONDS = 30 * 60
DEFAULT_PROOF_ANCHOR_MAX_AGE_SECONDS = 60
DEFAULT_OPENCODE_MODEL = "openai/gpt-5.5"
DEFAULT_OPENCODE_VARIANT = "xhigh"

BRIDGE_COMMAND_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "compact-status",
        "Compact local truth",
        "scripts\\riftreader-workflow-status.cmd --compact-json --write",
        "no input/movement/debugger/Git mutation",
    ),
    (
        "package-intake-selftest",
        "Package intake self-test",
        "scripts\\riftreader-package-intake-selftest.cmd",
        "generated dry-run package; no repo target writes",
    ),
    (
        "package-intake",
        "Package dry-run",
        "scripts\\riftreader-package-intake.cmd --package <path> --compact-json",
        "dry-run by default; apply requires explicit approval",
    ),
    (
        "live-triage",
        "No-input live triage",
        "scripts\\riftreader-live-triage.cmd --json --write",
        "no live input/movement/debugger",
    ),
    (
        "operator-lite",
        "Operator Lite",
        "scripts\\riftreader-operator-lite.cmd",
        "safe local GUI; live action buttons disabled",
    ),
    (
        "local-artifact-bridge-selftest",
        "Local Artifact Bridge self-test",
        "scripts\\riftreader-local-artifact-bridge.cmd --self-test --json",
        "ephemeral loopback self-test only; no persistent server or tunnel",
    ),
    (
        "local-artifact-bridge-index",
        "Local Artifact Bridge payload index",
        "scripts\\riftreader-local-artifact-bridge.cmd --index --payload-root artifacts\\chatgpt-payloads --json",
        "read-only payload metadata; no HTTP serving or tunnel management",
    ),
    (
        "transport-probe-local-smoke",
        "Transport probe local smoke",
        "scripts\\riftreader-transport-probe.cmd --json local-smoke",
        "synthetic local bridge smoke; no live RIFT activity",
    ),
    (
        "family-neighborhood-analysis",
        "Current-PID family neighborhood analysis",
        "scripts\\riftreader-family-neighborhood-analysis.cmd --json",
        "read-only existing candidate files; no live process reads/input/movement/debugger/provider writes",
    ),
    (
        "navigation-pointer-discovery",
        "Navigation pointer discovery dashboard",
        "scripts\\riftreader-navigation-pointer-discovery.cmd --json --write",
        "read-only artifact index; no live process reads/input/movement/debugger/provider writes or promotion",
    ),
    (
        "current-truth-refresh-plan",
        "Current truth refresh dry-run plan",
        "scripts\\riftreader-current-truth-refresh-plan.cmd --json --write",
        "ignored dry-run plan only; no tracked truth write/input/movement/debugger/provider writes or promotion",
    ),
    (
        "current-truth-refresh-apply",
        "Current truth refresh apply gate",
        "scripts\\riftreader-current-truth-refresh-apply.cmd --json",
        "dry-run validation by default; --apply writes tracked current-truth and remains a deliberate truth-refresh gate",
    ),
    (
        "facing-target-three-pose-gate",
        "Facing-target three-pose gate",
        "scripts\\riftreader-facing-target-three-pose-gate.cmd --json",
        "report-only package of existing route-step summaries; no new input/movement/debugger/provider writes or promotion",
    ),
    (
        "facing-target-restart-survival-packet",
        "Facing-target restart survival packet",
        "scripts\\riftreader-facing-target-restart-survival-packet.cmd --json",
        "report-only pre/post nav-state comparison; no restart, input/movement/debugger/provider writes, or promotion",
    ),
    (
        "facing-target-promotion-readiness-review",
        "Facing-target promotion-readiness review",
        "scripts\\riftreader-facing-target-promotion-readiness-review.cmd --json",
        "report-only review of existing gate/static evidence; no input/movement/current-truth write or promotion",
    ),
    (
        "facing-target-promotion-apply",
        "Facing-target promotion apply gate",
        "scripts\\riftreader-facing-target-promotion-apply.cmd --json",
        "--apply writes tracked facing/yaw promotion and current-truth docs; dry-run by default; no input/movement/debugger/provider writes",
    ),
    (
        "turn-rate-promotion-readiness-review",
        "Turn-rate promotion-readiness review",
        "scripts\\riftreader-turn-rate-promotion-readiness-review.cmd --json",
        "report-only owner+0x304 review; no input/movement/current-truth write or promotion",
    ),
    (
        "turn-rate-promotion-apply",
        "Turn-rate promotion apply gate",
        "scripts\\riftreader-turn-rate-promotion-apply.cmd --json",
        "--apply writes tracked turn-rate promotion/current-truth docs; dry-run by default; no input/movement/debugger/provider writes",
    ),
    (
        "actor-chain-no-debug-status",
        "Actor-chain no-debug status",
        "scripts\\riftreader-actor-chain-no-debug-status.cmd --json",
        "read-only actor/stat chain status; no input/movement/debugger/provider writes and no promotion",
    ),
    (
        "static-field-access-matrix",
        "Static field access matrix",
        "scripts\\riftreader-static-field-access-matrix.cmd --json",
        "offline installed-binary scan only; no live process access/input/movement/debugger/provider writes or promotion",
    ),
    (
        "phase1-target-entity-snapshot",
        "Phase 1 target entity snapshot",
        "scripts\\riftreader-phase1-target-entity-snapshot.cmd --pid <current-pid> --hwnd <current-hwnd> --json",
        "post-flush selected-target evidence and target-current reader blocker capture; no target selection/input/reload/debugger/provider writes or promotion",
    ),
    (
        "static-owner-coordinate-chain-readback",
        "Static-owner coordinate-chain readback",
        "scripts\\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json",
        "live target memory readback only; no input/movement/debugger/provider writes",
    ),
    (
        "static-owner-nav-now",
        "Static-owner coordinate/facing state",
        "scripts\\static-owner-nav-now.cmd",
        "live target coordinate plus facing/yaw readback only; no input/movement/debugger/provider writes or promotion",
    ),
    (
        "static-owner-turn-aware-plan",
        "Static-owner turn-aware route plan",
        "scripts\\static-owner-turn-aware-route-plan.cmd --json",
        "dry-run route/turn planning only; no input/movement/debugger/provider writes",
    ),
    (
        "static-owner-camera-yaw-classification",
        "Static-owner camera/yaw classification",
        "scripts\\static-owner-camera-yaw-classification.cmd --stimulus-approved --json",
        "guarded candidate-only visual/static-yaw classification; requires explicit live stimulus approval",
    ),
    (
        "static-owner-route-run-report",
        "Static-owner route-run report",
        "scripts\\static-owner-nav-report-route-run.cmd <summary.json> --json",
        "saved route-run report only; no live input/movement/debugger/provider writes",
    ),
    (
        "emergency-release",
        "Emergency key/mouse release",
        "scripts\\riftreader-emergency-release.cmd --pid <PID> --hwnd <HWND> --process-name rift_x64 --include-mouse-buttons --json",
        "release/up events only; no key-down/mouse-down/movement/debugger/provider writes",
    ),
    (
        "live-input-surface-audit",
        "Live input surface audit",
        "scripts\\riftreader-live-input-surface-audit.cmd --json",
        "read-only repo scan; no live process reads/input/movement/debugger/provider writes",
    ),
    (
        "character-select-plan",
        "Character-select dry-run plan",
        "scripts\\riftreader-character-select-plan.cmd --target-character <name> --plan-enter-world --json",
        "dry-run planning only; no clicks/keys/movement/debugger/provider writes",
    ),
    (
        "character-select-env-capture",
        "Character-select environment summary",
        "scripts\\riftreader-character-select-env-capture.cmd --pid <PID> --hwnd <HWND> --process-start-utc <UTC> --json",
        "read-only screenshot-to-summary builder; no clicks/keys/movement/debugger/provider writes",
    ),
    (
        "character-login-resilience-plan",
        "Character login/relogin resilience plan",
        "scripts\\riftreader-character-login-resilience-plan.cmd --target-character <name> --json",
        "dry-run crash/relogin planning only; no launch/clicks/keys/movement/debugger/provider writes",
    ),
    (
        "character-login-executor-contract",
        "Character login executor contract",
        "scripts\\riftreader-character-login-executor-contract.cmd --json",
        "dry-run approval/target contract validator only; no launch/clicks/keys/movement/debugger/provider writes",
    ),
    (
        "character-login-readiness-packet",
        "Character login readiness packet",
        "scripts\\riftreader-character-login-readiness-packet.cmd --target-character <name> --json",
        "input-free consolidated login/relogin packet; no launch/clicks/keys/movement/debugger/provider writes",
    ),
    (
        "character-login-crash-watch",
        "Character login crash/relogin watch",
        "scripts\\riftreader-character-login-crash-watch.cmd --samples 3 --interval-seconds 1 --json",
        "input-free crash/relogin watcher; no launch/clicks/keys/movement/debugger/provider writes",
    ),
    (
        "character-login-screen-state",
        "Character login screen-state classifier",
        "scripts\\riftreader-character-login-screen-state.cmd --expect-character-select --json",
        "input-free screenshot classifier; no launch/clicks/keys/movement/debugger/provider writes",
    ),
    (
        "character-login-play-executor-gate",
        "Character login Play executor gate",
        "scripts\\riftreader-character-login-play-executor-gate.cmd --json",
        "input-free MCP Play-click gate validator; no launch/clicks/keys/movement/debugger/provider writes",
    ),
    (
        "character-login-supervisor",
        "Character login supervisor packet",
        "scripts\\riftreader-character-login-supervisor.cmd --target-character <name> --json",
        "input-free supervised login/relogin gate; no launch/clicks/keys/movement/debugger/provider writes",
    ),
    (
        "launcher-inspection",
        "Glyph/RIFT launcher inspection",
        "scripts\\riftreader-launcher-inspection.cmd --json",
        "read-only launcher/process/window inspection; no launch/buttons/clicks/keys/movement/debugger/provider writes",
    ),
    (
        "sensitive-artifact-scan",
        "Sensitive artifact scan",
        "scripts\\riftreader-sensitive-artifact-scan.cmd --staged --json",
        "read-only staged/working artifact scan; no secret values echoed, no input/movement/debugger/provider writes",
    ),
)


def opencode_version_command() -> list[str]:
    """Return an OpenCode version command that works with Windows npm shims."""

    if sys.platform == "win32":
        return ["cmd", "/d", "/c", "opencode", "--version"]
    return ["opencode", "--version"]


def opencode_models_command(provider: str) -> list[str]:
    """Return an OpenCode model-list command for the requested provider."""

    if sys.platform == "win32":
        return ["cmd", "/d", "/c", "opencode", "models", provider]
    return ["opencode", "models", provider]


def desired_opencode_model() -> str:
    """Return the model the OpenCode wrappers should request by default."""

    return os.environ.get("RIFTREADER_OPENCODE_MODEL", "").strip() or DEFAULT_OPENCODE_MODEL


def desired_opencode_variant() -> str:
    """Return the reasoning variant the OpenCode wrappers should request."""

    return os.environ.get("RIFTREADER_OPENCODE_VARIANT", "").strip() or DEFAULT_OPENCODE_VARIANT


def opencode_provider_from_model(model: str) -> str | None:
    """Extract the provider prefix from a provider/model OpenCode model ID."""

    if "/" not in model:
        return None
    provider = model.split("/", 1)[0].strip()
    return provider or None


def parse_opencode_models(stdout: str) -> list[str]:
    """Parse `opencode models <provider>` output into model IDs."""

    return [line.strip() for line in stdout.splitlines() if line.strip()]


def bridge_command_capabilities(repo_root: Path) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for key, label, command, safety in BRIDGE_COMMAND_SPECS:
        script_part = command.split()[0].replace("\\", "/")
        script_path = repo_root / script_part
        commands.append(
            {
                "key": key,
                "label": label,
                "command": command,
                "exists": script_path.is_file(),
                "safety": safety,
            }
        )
    return commands


def run_command(
    label: str,
    args: list[str],
    cwd: Path,
    *,
    timeout_seconds: float = 30.0,
    expected_exit_codes: set[int] | None = None,
    capture_full_output: bool = False,
) -> dict[str, Any]:
    return run_command_envelope(
        label,
        args,
        cwd,
        timeout_seconds=timeout_seconds,
        expected_exit_codes=expected_exit_codes,
        capture_full_output=capture_full_output,
    )


def read_text(path: Path, errors: list[str], warnings: list[str], label: str) -> str | None:
    if not path.is_file():
        warnings.append(f"{label}-missing:{path}")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{label}-read-failed:{type(exc).__name__}:{exc}")
        return None


def read_json(path: Path, errors: list[str], warnings: list[str], label: str) -> dict[str, Any] | None:
    text = read_text(path, errors, warnings, label)
    if text is None:
        return None
    try:
        value = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{label}-json-parse-failed:{type(exc).__name__}:{exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}-not-json-object:{path}")
        return None
    return value


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
    observed_at_utc: Any,
    *,
    now: datetime | None = None,
    max_age_seconds: int = DEFAULT_LAUNCHER_INSPECTION_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    observed = parse_utc_datetime(observed_at_utc)
    if observed is None:
        return {
            "status": "unknown",
            "ageSeconds": None,
            "maxAgeSeconds": max_age_seconds,
            "observedAtUtc": observed_at_utc,
        }
    current = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    age = int((current - observed).total_seconds())
    if age < -30:
        status = "future-clock-skew"
    elif age <= max_age_seconds:
        status = "fresh"
    else:
        status = "stale"
    return {
        "status": status,
        "ageSeconds": age,
        "maxAgeSeconds": max_age_seconds,
        "observedAtUtc": observed_at_utc,
    }


def _proof_timestamp_candidates(
    current_proof: dict[str, Any],
    latest_validation: dict[str, Any],
    latest_proofonly: dict[str, Any],
) -> list[tuple[str, Any]]:
    validation_coordinate = (
        latest_validation.get("currentCoordinate") if isinstance(latest_validation.get("currentCoordinate"), dict) else {}
    )
    proofonly_coordinate = (
        latest_proofonly.get("currentCoordinate") if isinstance(latest_proofonly.get("currentCoordinate"), dict) else {}
    )
    return [
        ("latestValidation.generatedAtUtc", latest_validation.get("generatedAtUtc")),
        ("latestProofOnly.generatedAtUtc", latest_proofonly.get("generatedAtUtc")),
        ("lastUpdatedUtc", current_proof.get("lastUpdatedUtc")),
        ("latestValidation.currentCoordinate.recordedAtUtc", validation_coordinate.get("recordedAtUtc")),
        ("latestProofOnly.currentCoordinate.recordedAtUtc", proofonly_coordinate.get("recordedAtUtc")),
    ]


def proof_anchor_freshness_summary(
    current_proof: dict[str, Any],
    latest_validation: dict[str, Any],
    latest_proofonly: dict[str, Any],
    *,
    now: datetime | None = None,
    max_age_seconds: int = DEFAULT_PROOF_ANCHOR_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    parsed: list[tuple[datetime, str, Any]] = []
    for source, value in _proof_timestamp_candidates(current_proof, latest_validation, latest_proofonly):
        observed = parse_utc_datetime(value)
        if observed is not None:
            parsed.append((observed, source, value))
    if not parsed:
        freshness = freshness_summary(None, now=now, max_age_seconds=max_age_seconds)
        freshness["observedSource"] = None
        return freshness
    _, source, value = max(parsed, key=lambda item: item[0])
    freshness = freshness_summary(value, now=now, max_age_seconds=max_age_seconds)
    freshness["observedSource"] = source
    return freshness


def latest_launcher_inspection(repo_root: Path, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    """Return a compact summary of the latest read-only launcher inspection artifact.

    The status packet intentionally does not run launcher inspection itself. It
    reads the helper's latest artifact when present so compact SITREPs can show
    the launcher/relogin state without implicitly touching live windows again.
    """

    latest_path = repo_root / DEFAULT_LAUNCHER_INSPECTION_DIR / "latest-run.txt"
    if not latest_path.is_file():
        return {
            "status": "not-collected",
            "state": None,
            "summaryJson": None,
            "observedAtUtc": None,
            "launcherPresent": None,
            "gamePresent": None,
            "launcherWindowState": None,
            "riftChildOfLauncher": None,
        }

    try:
        latest_text = latest_path.read_text(encoding="utf-8").strip()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"launcher-inspection-latest-read-failed:{type(exc).__name__}:{exc}")
        return {
            "status": "failed",
            "state": None,
            "summaryJson": None,
            "observedAtUtc": None,
            "launcherPresent": None,
            "gamePresent": None,
            "launcherWindowState": None,
            "riftChildOfLauncher": None,
        }

    if not latest_text:
        warnings.append("launcher-inspection-latest-empty")
        return {
            "status": "not-collected",
            "state": None,
            "summaryJson": None,
            "observedAtUtc": None,
            "launcherPresent": None,
            "gamePresent": None,
            "launcherWindowState": None,
            "riftChildOfLauncher": None,
        }

    run_dir = Path(latest_text)
    if not run_dir.is_absolute():
        run_dir = repo_root / run_dir
    summary_path = run_dir / "launcher-inspection-summary.json"
    summary = read_json(summary_path, errors, warnings, "launcher-inspection-summary")
    if not summary:
        return {
            "status": "missing-summary",
            "state": None,
            "summaryJson": as_repo_path(repo_root, summary_path),
            "observedAtUtc": None,
            "launcherPresent": None,
            "gamePresent": None,
            "launcherWindowState": None,
            "riftChildOfLauncher": None,
        }

    launcher = summary.get("launcher") if isinstance(summary.get("launcher"), dict) else {}
    game = summary.get("game") if isinstance(summary.get("game"), dict) else {}
    state = summary.get("state") if isinstance(summary.get("state"), dict) else {}
    visible = summary.get("visibleStateClassifier") if isinstance(summary.get("visibleStateClassifier"), dict) else {}
    relaunch = summary.get("relaunchReadiness") if isinstance(summary.get("relaunchReadiness"), dict) else {}
    main_window = launcher.get("mainWindow") if isinstance(launcher.get("mainWindow"), dict) else {}
    freshness = freshness_summary(summary.get("generatedAtUtc"))
    if freshness.get("status") == "stale":
        warnings.append(f"launcher-inspection-stale:{freshness.get('ageSeconds')}s")
    return {
        "status": summary.get("status"),
        "observedAtUtc": summary.get("generatedAtUtc"),
        "freshness": freshness,
        "state": state.get("crashRecoveryState"),
        "reloginState": state.get("reloginState"),
        "automationRecommendation": state.get("automationRecommendation"),
        "buttonAutomationPolicy": state.get("buttonAutomationPolicy"),
        "visibleStateClassifier": visible,
        "relaunchReadiness": relaunch,
        "launcherPresent": launcher.get("present"),
        "launcherPids": launcher.get("processIds") or [],
        "launcherWindowState": launcher.get("windowState") or state.get("launcherWindowState"),
        "launcherMainHwnd": main_window.get("windowHandle"),
        "gamePresent": game.get("present"),
        "riftPids": game.get("processIds") or [],
        "riftChildOfLauncher": state.get("riftChildOfLauncher"),
        "blockers": summary.get("blockers") or [],
        "warnings": summary.get("warnings") or [],
        "summaryJson": as_repo_path(repo_root, summary_path),
    }


def latest_character_login_supervisor(repo_root: Path, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    latest_path = repo_root / DEFAULT_CHARACTER_LOGIN_SUPERVISOR_DIR / "latest-run.txt"
    if not latest_path.is_file():
        return {
            "status": "not-collected",
            "observedAtUtc": None,
            "targetCharacter": None,
            "futureExecutorMayClickPlay": None,
            "approvalTokenRequired": None,
            "summaryJson": None,
        }
    try:
        latest_text = latest_path.read_text(encoding="utf-8").strip()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"character-login-supervisor-latest-read-failed:{type(exc).__name__}:{exc}")
        return {"status": "failed", "observedAtUtc": None, "summaryJson": None}
    if not latest_text:
        warnings.append("character-login-supervisor-latest-empty")
        return {"status": "not-collected", "observedAtUtc": None, "summaryJson": None}

    run_dir = Path(latest_text)
    if not run_dir.is_absolute():
        run_dir = repo_root / run_dir
    summary_path = run_dir / "character-login-supervisor-summary.json"
    summary = read_json(summary_path, errors, warnings, "character-login-supervisor-summary")
    if not summary:
        return {"status": "missing-summary", "observedAtUtc": None, "summaryJson": as_repo_path(repo_root, summary_path)}

    target = summary.get("target") if isinstance(summary.get("target"), dict) else {}
    selection = summary.get("selection") if isinstance(summary.get("selection"), dict) else {}
    decision = summary.get("supervisorDecision") if isinstance(summary.get("supervisorDecision"), dict) else {}
    manifest = summary.get("futureMcpActionManifest") if isinstance(summary.get("futureMcpActionManifest"), dict) else {}
    approval = manifest.get("approval") if isinstance(manifest.get("approval"), dict) else {}
    child = summary.get("childStatuses") if isinstance(summary.get("childStatuses"), dict) else {}
    return {
        "status": summary.get("status"),
        "observedAtUtc": summary.get("generatedAtUtc"),
        "freshness": freshness_summary(summary.get("generatedAtUtc")),
        "targetCharacter": summary.get("targetCharacter"),
        "targetPid": target.get("processId"),
        "targetHwnd": target.get("windowHandle"),
        "selectedCharacter": selection.get("selectedCharacter"),
        "screenClassification": child.get("screenClassification"),
        "futureExecutorMayClickPlay": decision.get("futureExecutorMayClickPlay"),
        "mayClickPlayInThisSupervisor": decision.get("mayClickPlayInThisSupervisor"),
        "approvalTokenRequired": bool(approval.get("token")),
        "approvalTokenStoredInStatus": False,
        "manifestStatus": manifest.get("status"),
        "dataBlockers": summary.get("dataBlockers") or [],
        "executionBlockers": summary.get("executionBlockers") or [],
        "summaryJson": as_repo_path(repo_root, summary_path),
    }


def latest_static_owner_capture_summary(
    repo_root: Path,
    *,
    prefix: str,
    label: str,
    errors: list[str],
    warnings: list[str],
    now: datetime | None = None,
) -> dict[str, Any]:
    capture_root = repo_root / DEFAULT_STATIC_OWNER_CAPTURE_DIR
    if not capture_root.is_dir():
        return {"status": "missing", "summaryJson": None}
    try:
        summaries = [path for path in capture_root.glob(f"{prefix}-*/summary.json") if path.is_file()]
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{label}-latest-search-failed:{type(exc).__name__}:{exc}")
        return {"status": "failed", "summaryJson": None}
    if not summaries:
        return {"status": "missing", "summaryJson": None}
    latest = max(summaries, key=lambda path: path.stat().st_mtime)
    payload = read_json(latest, errors, warnings, label)
    if not payload:
        return {"status": "failed", "summaryJson": as_repo_path(repo_root, latest)}
    observed_at_utc = payload.get("generatedAtUtc") or (
        datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    latest_state = payload.get("latestState") if isinstance(payload.get("latestState"), dict) else {}
    samples = payload.get("samples") if isinstance(payload.get("samples"), list) else []
    latest_sample = samples[-1] if samples and isinstance(samples[-1], dict) else {}
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    coordinate = (
        payload.get("coordinate")
        if isinstance(payload.get("coordinate"), dict)
        else latest_state.get("coordinate")
        if isinstance(latest_state.get("coordinate"), dict)
        else latest_sample.get("coordinate")
        if isinstance(latest_sample.get("coordinate"), dict)
        else {}
    )
    yaw_degrees = (
        payload.get("yawDegrees")
        if payload.get("yawDegrees") is not None
        else latest_state.get("yawDegrees") or latest_sample.get("yawDegrees")
    )
    pitch_degrees = (
        payload.get("pitchDegrees")
        if payload.get("pitchDegrees") is not None
        else latest_state.get("pitchDegrees") or latest_sample.get("pitchDegrees")
    )
    sample_count = (
        payload.get("sampleCount") if payload.get("sampleCount") is not None else analysis.get("sampleCount") or len(samples)
    )
    max_planar_delta = (
        payload.get("maxPlanarDelta") if payload.get("maxPlanarDelta") is not None else analysis.get("maxPlanarDelta")
    )
    max_planar_speed = (
        payload.get("maxSpeedPlanarPerSecond")
        if payload.get("maxSpeedPlanarPerSecond") is not None
        else analysis.get("maxSpeedPlanarPerSecond")
    )
    yaw_range = payload.get("yawRangeDegrees") if payload.get("yawRangeDegrees") is not None else analysis.get("yawRangeDegrees")
    max_abs_yaw_delta = (
        payload.get("maxAbsYawDeltaDegrees")
        if payload.get("maxAbsYawDeltaDegrees") is not None
        else analysis.get("maxAbsYawDeltaDegrees")
    )
    return {
        "status": payload.get("status"),
        "verdict": payload.get("verdict"),
        "classification": payload.get("classification"),
        "generatedAtUtc": payload.get("generatedAtUtc"),
        "summaryJson": as_repo_path(repo_root, latest),
        "freshness": freshness_summary(
            observed_at_utc,
            now=now,
            max_age_seconds=DEFAULT_STATIC_OWNER_READBACK_MAX_AGE_SECONDS,
        ),
        "ownerAddress": latest_state.get("ownerAddress") or latest_sample.get("ownerAddress"),
        "coordinate": coordinate,
        "yawDegrees": yaw_degrees,
        "pitchDegrees": pitch_degrees,
        "sampleCount": sample_count,
        "maxPlanarDelta": max_planar_delta,
        "maxSpeedPlanarPerSecond": max_planar_speed,
        "yawRangeDegrees": yaw_range,
        "maxAbsYawDeltaDegrees": max_abs_yaw_delta,
        "blockers": payload.get("blockers") or [],
        "warnings": payload.get("warnings") or [],
    }


def latest_static_owner_readback(repo_root: Path, errors: list[str], warnings: list[str], now: datetime | None = None) -> dict[str, Any]:
    return {
        "coordinateChain": latest_static_owner_capture_summary(
            repo_root,
            prefix="static-owner-coordinate-chain-readback",
            label="latest-static-owner-coordinate-chain-readback",
            errors=errors,
            warnings=warnings,
            now=now,
        ),
        "navState": latest_static_owner_capture_summary(
            repo_root,
            prefix="static-owner-nav-state",
            label="latest-static-owner-nav-state",
            errors=errors,
            warnings=warnings,
            now=now,
        ),
    }


def _summarize_navigation_candidate(candidate: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Copy only stable, compact fields from a navigation discovery candidate."""

    return {field: candidate.get(field) for field in fields}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def latest_navigation_pointer_discovery(repo_root: Path) -> dict[str, Any]:
    """Return the latest ignored navigation pointer discovery dashboard.

    This is intentionally non-blocking for the workflow status packet: the
    dashboard is a read-only convenience surface, so missing or malformed local
    artifacts are reported inside this field instead of failing the status
    packet or weakening any live/proof gate.
    """

    summary_path = repo_root / DEFAULT_NAVIGATION_POINTER_DISCOVERY_SUMMARY
    markdown_path = summary_path.with_suffix(".md")
    summary_rel = as_repo_path(repo_root, summary_path)
    markdown_rel = as_repo_path(repo_root, markdown_path)
    base = {
        "status": "missing",
        "verdict": None,
        "observedAtUtc": None,
        "summaryJson": summary_rel,
        "summaryMarkdown": markdown_rel,
        "freshnessStatus": None,
        "staleSources": [],
        "unknownSources": [],
        "target": {},
        "promotedCoordinate": {},
        "candidateFacingTarget": {},
        "candidateTurnRate": {},
        "owner304Semantics": {},
        "candidateLedger": {},
        "navigationControlChains": {},
        "coordinateDeltaCandidate": {},
        "proofGates": {},
        "promotionReadiness": {},
        "nextRecommendedAction": None,
        "recommendedActions": [],
        "blockers": [],
        "warnings": [],
        "errors": [],
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
        },
    }
    if not summary_path.is_file():
        return base

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001 - malformed ignored artifacts must not fail the packet.
        blocked = dict(base)
        blocked["status"] = "parse-error"
        blocked["warnings"] = [
            f"navigation-pointer-discovery-summary-parse-error:{type(exc).__name__}:{preview_text(str(exc))}"
        ]
        blocked["blockers"] = ["navigation-pointer-discovery-summary-unusable"]
        return blocked
    if not isinstance(payload, dict):
        blocked = dict(base)
        blocked["status"] = "parse-error"
        blocked["warnings"] = ["navigation-pointer-discovery-summary-not-json-object"]
        blocked["blockers"] = ["navigation-pointer-discovery-summary-unusable"]
        return blocked

    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), dict) else {}
    promoted = candidates.get("promotedCoordinate") if isinstance(candidates.get("promotedCoordinate"), dict) else {}
    facing = candidates.get("candidateFacingTarget") if isinstance(candidates.get("candidateFacingTarget"), dict) else {}
    turn = candidates.get("candidateTurnRate") if isinstance(candidates.get("candidateTurnRate"), dict) else {}
    owner304_semantics = (
        candidates.get("owner304Semantics") if isinstance(candidates.get("owner304Semantics"), dict) else {}
    )
    delta = (
        candidates.get("coordinateDeltaCandidate")
        if isinstance(candidates.get("coordinateDeltaCandidate"), dict)
        else {}
    )
    freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
    proof_gates = payload.get("proofGates") if isinstance(payload.get("proofGates"), dict) else {}
    three_pose_gate = (
        proof_gates.get("facingThreePoseGate") if isinstance(proof_gates.get("facingThreePoseGate"), dict) else {}
    )
    restart_survival = (
        proof_gates.get("facingRestartSurvival")
        if isinstance(proof_gates.get("facingRestartSurvival"), dict)
        else {}
    )
    turn_forward = (
        proof_gates.get("turnForwardExperiment")
        if isinstance(proof_gates.get("turnForwardExperiment"), dict)
        else {}
    )
    ghidra_static = (
        proof_gates.get("ghidraStaticEvidence")
        if isinstance(proof_gates.get("ghidraStaticEvidence"), dict)
        else {}
    )
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    next_section = payload.get("next") if isinstance(payload.get("next"), dict) else {}
    promotion_readiness = (
        payload.get("promotionReadiness") if isinstance(payload.get("promotionReadiness"), dict) else {}
    )
    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    recommended_actions = _list_or_empty(next_section.get("recommendedActions"))
    if not recommended_actions and next_section.get("recommendedAction"):
        recommended_actions = [next_section.get("recommendedAction")]

    return {
        **base,
        "status": payload.get("status") or "unknown",
        "verdict": payload.get("verdict"),
        "observedAtUtc": payload.get("generatedAtUtc"),
        "freshnessStatus": freshness.get("status"),
        "staleSources": freshness.get("staleSources") or [],
        "unknownSources": freshness.get("unknownSources") or [],
        "target": {
            "processName": target.get("processName"),
            "processId": target.get("processId"),
            "targetWindowHandle": target.get("targetWindowHandle"),
            "processStartUtc": target.get("processStartUtc"),
        },
        "promotedCoordinate": _summarize_navigation_candidate(
            promoted,
            [
                "status",
                "promotionAllowed",
                "candidateOnly",
                "chain",
                "rootModule",
                "rootRva",
                "coordinateOffset",
                "latestReadbackStatus",
                "latestReadbackAtUtc",
                "latestReadbackJson",
                "apiNowStatus",
            ],
        ),
        "candidateFacingTarget": _summarize_navigation_candidate(
            facing,
            [
                "status",
                "candidateOnly",
                "promotionAllowed",
                "chainShape",
                "offset",
                "offsetFromOwner",
                "latestYawDegrees",
                "comparisonMaxAbsYawDeltaDegrees",
                "planarLookaheadDistance",
                "promotionArtifact",
                "promotedAtUtc",
                "latestPromotionAtUtc",
                "latestPromotionReview",
            ],
        ),
        "candidateTurnRate": _summarize_navigation_candidate(
            turn,
            [
                "status",
                "candidateOnly",
                "promotionAllowed",
                "offset",
                "chainShape",
                "latestValue",
                "latestClassification",
                "promotionArtifact",
                "promotedAtUtc",
                "comparisonMaxAbsDelta",
            ],
        ),
        "owner304Semantics": _summarize_navigation_candidate(
            owner304_semantics,
            [
                "status",
                "verdict",
                "classification",
                "owner304Role",
                "semanticVerdict",
                "candidateOnly",
                "promotionAllowed",
                "activeTurnRatePromotionAllowed",
                "poseCount",
                "directions",
                "maxOppositeRadianError",
                "turnRateDeltaProofBlocked",
                "legacyTurnClassifierReliable",
                "stationaryOwner304Value",
                "recommendedAction",
            ],
        ),
        "candidateLedger": payload.get("candidateLedger") if isinstance(payload.get("candidateLedger"), dict) else {},
        "navigationControlChains": payload.get("navigationControlChains") if isinstance(payload.get("navigationControlChains"), dict) else {},
        "coordinateDeltaCandidate": _summarize_navigation_candidate(
            delta,
            [
                "status",
                "candidateOnly",
                "promotionState",
                "ownerOffset",
                "trackingErrorMaxAbs",
                "matchesPromotedCoordinateAddress",
                "familySummaryJson",
            ],
        ),
        "proofGates": {
            "facingThreePoseGate": _summarize_navigation_candidate(
                three_pose_gate,
                [
                    "status",
                    "verdict",
                    "candidateOnly",
                    "promotionAllowed",
                    "formalThreePoseGatePassed",
                    "poseCount",
                    "passedPoseCount",
                    "minimumProgressDistance",
                    "aggregateProgressDistance",
                    "candidateFacingTargetOffset",
                ],
            ),
            "facingRestartSurvival": _summarize_navigation_candidate(
                restart_survival,
                [
                    "status",
                    "verdict",
                    "candidateOnly",
                    "promotionAllowed",
                    "restartRelogSurvived",
                    "offsetsStable",
                    "processStartChanged",
                    "facingTargetOffset",
                ],
            ),
            "turnForwardExperiment": _summarize_navigation_candidate(
                turn_forward,
                [
                    "status",
                    "verdict",
                    "candidateOnly",
                    "promotionAllowed",
                    "routeStatus",
                    "totalProgressDistance",
                    "movementApproved",
                    "turnApproved",
                    "sourceMovementSent",
                    "sourceInputSent",
                ],
            ),
            "ghidraStaticEvidence": _summarize_navigation_candidate(
                ghidra_static,
                [
                    "status",
                    "kind",
                    "generatedAtUtc",
                    "summaryJson",
                    "summaryMarkdown",
                    "evidenceJson",
                    "rootAddress",
                    "rootReferenceCountCaptured",
                    "instructionsScanned",
                    "analysisTimedOutProjectSaved",
                    "offlineOnly",
                    "warnings",
                ],
            ),
        },
        "promotionReadiness": promotion_readiness,
        "nextRecommendedAction": next_section.get("recommendedAction"),
        "recommendedActions": recommended_actions,
        "blockers": _list_or_empty(payload.get("blockers")),
        "warnings": _list_or_empty(payload.get("warnings")),
        "errors": _list_or_empty(payload.get("errors")),
        "safety": {
            **base["safety"],
            "readOnlyArtifactIndex": bool(safety.get("readOnlyArtifactIndex", True)),
            "movementSent": bool(safety.get("movementSent")),
            "inputSent": bool(safety.get("inputSent")),
            "targetMemoryBytesRead": bool(safety.get("targetMemoryBytesRead")),
            "targetMemoryBytesWritten": bool(safety.get("targetMemoryBytesWritten")),
            "proofPromotion": bool(safety.get("proofPromotion")),
            "actorChainPromotion": bool(safety.get("actorChainPromotion")),
            "facingPromotion": bool(safety.get("facingPromotion")),
            "gitMutation": bool(safety.get("gitMutation")),
        },
    }


def latest_current_truth_refresh_plan(repo_root: Path) -> dict[str, Any]:
    """Return the latest ignored current-truth refresh dry-run plan."""

    summary_path = repo_root / DEFAULT_CURRENT_TRUTH_REFRESH_PLAN_SUMMARY
    base = {
        "status": "missing",
        "verdict": None,
        "observedAtUtc": None,
        "summaryJson": as_repo_path(repo_root, summary_path),
        "summaryMarkdown": as_repo_path(repo_root, summary_path.with_suffix(".md")),
        "proposedCurrentTruthJson": as_repo_path(repo_root, summary_path.parent / "proposed-current-truth.json"),
        "proposedCurrentTruthDiff": as_repo_path(repo_root, summary_path.parent / "proposed-current-truth.diff"),
        "updateCount": 0,
        "requiresExplicitApprovalForApply": True,
        "nextRecommendedAction": None,
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": {
            "dryRunOnly": True,
            "trackedTruthWritten": False,
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
            "gitMutation": False,
        },
    }
    if not summary_path.is_file():
        return base
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001 - malformed ignored artifacts must not fail status.
        blocked = dict(base)
        blocked["status"] = "parse-error"
        blocked["warnings"] = [
            f"current-truth-refresh-plan-summary-parse-error:{type(exc).__name__}:{preview_text(str(exc))}"
        ]
        blocked["blockers"] = ["current-truth-refresh-plan-summary-unusable"]
        return blocked
    if not isinstance(payload, dict):
        blocked = dict(base)
        blocked["status"] = "parse-error"
        blocked["warnings"] = ["current-truth-refresh-plan-summary-not-json-object"]
        blocked["blockers"] = ["current-truth-refresh-plan-summary-unusable"]
        return blocked

    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    next_section = payload.get("next") if isinstance(payload.get("next"), dict) else {}
    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    return {
        **base,
        "status": payload.get("status") or "unknown",
        "verdict": payload.get("verdict"),
        "observedAtUtc": payload.get("generatedAtUtc"),
        "summaryJson": artifacts.get("summaryJson") or base["summaryJson"],
        "summaryMarkdown": artifacts.get("summaryMarkdown") or base["summaryMarkdown"],
        "proposedCurrentTruthJson": artifacts.get("proposedCurrentTruthJson") or base["proposedCurrentTruthJson"],
        "proposedCurrentTruthDiff": artifacts.get("proposedCurrentTruthDiff") or base["proposedCurrentTruthDiff"],
        "updateCount": payload.get("updateCount") if isinstance(payload.get("updateCount"), int) else 0,
        "requiresExplicitApprovalForApply": bool(next_section.get("requiresExplicitApprovalForApply", True)),
        "nextRecommendedAction": next_section.get("recommendedAction"),
        "blockers": _list_or_empty(payload.get("blockers")),
        "warnings": _list_or_empty(payload.get("warnings")),
        "errors": _list_or_empty(payload.get("errors")),
        "safety": {
            **base["safety"],
            "dryRunOnly": bool(safety.get("dryRunOnly", True)),
            "trackedTruthWritten": bool(safety.get("trackedTruthWritten")),
            "movementSent": bool(safety.get("movementSent")),
            "inputSent": bool(safety.get("inputSent")),
            "targetMemoryBytesRead": bool(safety.get("targetMemoryBytesRead")),
            "targetMemoryBytesWritten": bool(safety.get("targetMemoryBytesWritten")),
            "proofPromotion": bool(safety.get("proofPromotion")),
            "actorChainPromotion": bool(safety.get("actorChainPromotion")),
            "facingPromotion": bool(safety.get("facingPromotion")),
            "gitMutation": bool(safety.get("gitMutation")),
        },
    }


def latest_current_truth_refresh_apply(repo_root: Path) -> dict[str, Any]:
    """Return the latest ignored current-truth refresh apply-gate summary."""

    summary_path = repo_root / DEFAULT_CURRENT_TRUTH_REFRESH_APPLY_SUMMARY
    base = {
        "status": "missing",
        "verdict": None,
        "observedAtUtc": None,
        "summaryJson": as_repo_path(repo_root, summary_path),
        "summaryMarkdown": as_repo_path(repo_root, summary_path.with_suffix(".md")),
        "backupCurrentTruthJson": as_repo_path(repo_root, summary_path.parent / "current-truth-before-apply.json"),
        "applyRequested": None,
        "target": {},
        "plan": {},
        "hashes": {},
        "nextRecommendedAction": None,
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": {
            "dryRunOnly": True,
            "applyFlagSent": False,
            "trackedTruthWritten": False,
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
            "gitMutation": False,
        },
    }
    if not summary_path.is_file():
        return base
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001 - malformed ignored artifacts must not fail status.
        blocked = dict(base)
        blocked["status"] = "parse-error"
        blocked["warnings"] = [
            f"current-truth-refresh-apply-summary-parse-error:{type(exc).__name__}:{preview_text(str(exc))}"
        ]
        blocked["blockers"] = ["current-truth-refresh-apply-summary-unusable"]
        return blocked
    if not isinstance(payload, dict):
        blocked = dict(base)
        blocked["status"] = "parse-error"
        blocked["warnings"] = ["current-truth-refresh-apply-summary-not-json-object"]
        blocked["blockers"] = ["current-truth-refresh-apply-summary-unusable"]
        return blocked

    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    next_section = payload.get("next") if isinstance(payload.get("next"), dict) else {}
    return {
        **base,
        "status": payload.get("status") or "unknown",
        "verdict": payload.get("verdict"),
        "observedAtUtc": payload.get("generatedAtUtc"),
        "summaryJson": artifacts.get("summaryJson") or base["summaryJson"],
        "summaryMarkdown": artifacts.get("summaryMarkdown") or base["summaryMarkdown"],
        "backupCurrentTruthJson": artifacts.get("backupCurrentTruthJson") or base["backupCurrentTruthJson"],
        "applyRequested": bool(payload.get("applyRequested")),
        "target": payload.get("target") if isinstance(payload.get("target"), dict) else {},
        "plan": payload.get("plan") if isinstance(payload.get("plan"), dict) else {},
        "hashes": payload.get("hashes") if isinstance(payload.get("hashes"), dict) else {},
        "nextRecommendedAction": next_section.get("recommendedAction"),
        "blockers": _list_or_empty(payload.get("blockers")),
        "warnings": _list_or_empty(payload.get("warnings")),
        "errors": _list_or_empty(payload.get("errors")),
        "safety": {
            **base["safety"],
            "dryRunOnly": bool(safety.get("dryRunOnly", True)),
            "applyFlagSent": bool(safety.get("applyFlagSent")),
            "trackedTruthWritten": bool(safety.get("trackedTruthWritten")),
            "movementSent": bool(safety.get("movementSent")),
            "inputSent": bool(safety.get("inputSent")),
            "targetMemoryBytesRead": bool(safety.get("targetMemoryBytesRead")),
            "targetMemoryBytesWritten": bool(safety.get("targetMemoryBytesWritten")),
            "proofPromotion": bool(safety.get("proofPromotion")),
            "actorChainPromotion": bool(safety.get("actorChainPromotion")),
            "facingPromotion": bool(safety.get("facingPromotion")),
            "gitMutation": bool(safety.get("gitMutation")),
        },
    }


def latest_facing_promotion_readiness_review(repo_root: Path) -> dict[str, Any]:
    """Return the latest report-only candidate-facing promotion-readiness review."""

    base = {
        "status": "missing",
        "verdict": None,
        "observedAtUtc": None,
        "summaryJson": None,
        "summaryMarkdown": None,
        "target": {},
        "candidate": {},
        "reviewGates": {},
        "promotionDecision": {
            "reviewPassed": False,
            "promotionAllowed": False,
            "promotionPerformed": False,
            "explicitPromotionGateRequired": True,
            "freshPrePromotionReadbackRequired": True,
        },
        "nextRecommendedAction": None,
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
            "currentTruthWrite": False,
            "gitMutation": False,
        },
        "sourceSafety": {},
    }
    capture_root = repo_root / DEFAULT_STATIC_OWNER_CAPTURE_DIR
    if not capture_root.is_dir():
        return base
    try:
        summaries = [
            path
            for path in capture_root.glob(f"{DEFAULT_FACING_PROMOTION_READINESS_REVIEW_PREFIX}-*/summary.json")
            if path.is_file()
        ]
    except Exception as exc:  # noqa: BLE001 - malformed ignored artifacts must not fail status.
        blocked = dict(base)
        blocked["status"] = "search-error"
        blocked["warnings"] = [
            f"facing-promotion-readiness-review-search-error:{type(exc).__name__}:{preview_text(str(exc))}"
        ]
        return blocked
    if not summaries:
        return base
    latest = max(summaries, key=lambda path: path.stat().st_mtime_ns)
    markdown = latest.with_suffix(".md")
    try:
        payload = json.loads(latest.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001 - malformed ignored artifacts must not fail status.
        blocked = dict(base)
        blocked["status"] = "parse-error"
        blocked["summaryJson"] = as_repo_path(repo_root, latest)
        blocked["summaryMarkdown"] = as_repo_path(repo_root, markdown)
        blocked["warnings"] = [
            f"facing-promotion-readiness-review-parse-error:{type(exc).__name__}:{preview_text(str(exc))}"
        ]
        blocked["blockers"] = ["facing-promotion-readiness-review-summary-unusable"]
        return blocked
    if not isinstance(payload, dict):
        blocked = dict(base)
        blocked["status"] = "parse-error"
        blocked["summaryJson"] = as_repo_path(repo_root, latest)
        blocked["summaryMarkdown"] = as_repo_path(repo_root, markdown)
        blocked["warnings"] = ["facing-promotion-readiness-review-summary-not-json-object"]
        blocked["blockers"] = ["facing-promotion-readiness-review-summary-unusable"]
        return blocked

    if payload.get("kind") != "facing-target-promotion-readiness-review-packet":
        blocked = dict(base)
        blocked["status"] = "kind-mismatch"
        blocked["summaryJson"] = as_repo_path(repo_root, latest)
        blocked["summaryMarkdown"] = as_repo_path(repo_root, markdown)
        blocked["warnings"] = [
            f"facing-promotion-readiness-review-kind-mismatch:{payload.get('kind')}"
        ]
        return blocked

    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    decision = payload.get("promotionDecision") if isinstance(payload.get("promotionDecision"), dict) else {}
    next_section = payload.get("next") if isinstance(payload.get("next"), dict) else {}
    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    source_safety = payload.get("sourceSafety") if isinstance(payload.get("sourceSafety"), dict) else {}
    return {
        **base,
        "status": payload.get("status") or "unknown",
        "verdict": payload.get("verdict"),
        "observedAtUtc": payload.get("generatedAtUtc"),
        "summaryJson": artifacts.get("summaryJson") or as_repo_path(repo_root, latest),
        "summaryMarkdown": artifacts.get("summaryMarkdown") or as_repo_path(repo_root, markdown),
        "target": payload.get("target") if isinstance(payload.get("target"), dict) else {},
        "candidate": payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {},
        "reviewGates": payload.get("reviewGates") if isinstance(payload.get("reviewGates"), dict) else {},
        "promotionDecision": {
            **base["promotionDecision"],
            "reviewPassed": bool(decision.get("reviewPassed")),
            "promotionAllowed": bool(decision.get("promotionAllowed")),
            "promotionPerformed": bool(decision.get("promotionPerformed")),
            "explicitPromotionGateRequired": bool(decision.get("explicitPromotionGateRequired", True)),
            "freshPrePromotionReadbackRequired": bool(decision.get("freshPrePromotionReadbackRequired", True)),
            "recommendedPromotionState": decision.get("recommendedPromotionState"),
        },
        "nextRecommendedAction": next_section.get("recommendedAction"),
        "blockers": _list_or_empty(payload.get("blockers")),
        "warnings": _list_or_empty(payload.get("warnings")),
        "errors": _list_or_empty(payload.get("errors")),
        "safety": {
            **base["safety"],
            "movementSent": bool(safety.get("movementSent")),
            "inputSent": bool(safety.get("inputSent")),
            "targetMemoryBytesRead": bool(safety.get("targetMemoryBytesRead")),
            "targetMemoryBytesWritten": bool(safety.get("targetMemoryBytesWritten")),
            "proofPromotion": bool(safety.get("proofPromotion")),
            "actorChainPromotion": bool(safety.get("actorChainPromotion")),
            "facingPromotion": bool(safety.get("facingPromotion")),
            "currentTruthWrite": bool(safety.get("currentTruthWrite")),
            "gitMutation": bool(safety.get("gitMutation")),
        },
        "sourceSafety": source_safety,
    }


def find_latest_handoff(repo_root: Path, handoff_dir: Path | None = None) -> Path | None:
    directory = handoff_dir if handoff_dir is not None else repo_root / DEFAULT_HANDOFF_DIR
    if not directory.is_dir():
        return None
    files = [path for path in directory.glob("*.md") if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda item: (item.stat().st_mtime, item.name))


def extract_section(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip().lower() == heading.lower():
            start = index + 1
            break
    if start is None:
        return None
    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            section.append(line.rstrip())
    return "\n".join(section).strip() or None


def summarize_handoff(repo_root: Path, path: Path | None, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    if path is None:
        warnings.append("latest-handoff-missing")
        return {"path": None, "title": None, "lastWriteTimeUtc": None, "tldr": None}
    text = read_text(path, errors, warnings, "latest-handoff") or ""
    title = None
    for line in text.splitlines():
        if line.startswith("# "):
            title = line.lstrip("#").strip()
            break
    return {
        "path": as_repo_path(repo_root, path),
        "title": title,
        "lastWriteTimeUtc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "tldr": extract_section(text, "## TL;DR"),
    }


def parse_git_status(stdout: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in stdout.splitlines() if line.strip()]
    branch = lines[0] if lines else None
    dirty = [line for line in lines[1:] if line.strip()]
    return {
        "branch": branch,
        "isClean": len(dirty) == 0,
        "dirty": dirty,
        "raw": lines,
    }


def parse_git_log(stdout: str) -> list[dict[str, Any]]:
    commits: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        commits.append({"hash": parts[0], "date": parts[1], "decorate": parts[2].strip(), "subject": parts[3]})
    return commits


def parse_refs(stdout: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        refs.append({"date": parts[0], "ref": parts[1], "hash": parts[2], "subject": parts[3]})
    return refs


def parse_json_from_envelope(envelope: dict[str, Any], warnings: list[str], errors: list[str], label: str) -> dict[str, Any] | None:
    stdout = envelope.get("stdout") if isinstance(envelope.get("stdout"), str) else envelope.get("stdoutPreview")
    if not isinstance(stdout, str) or not stdout.strip():
        if envelope.get("ok"):
            warnings.append(f"{label}-empty-output")
        else:
            errors.append(f"{label}-no-json-output")
        return None
    try:
        value = json.loads(stdout)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{label}-json-parse-failed:{type(exc).__name__}:{exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}-not-json-object")
        return None
    return value


def summarize_current_truth(current_truth: dict[str, Any] | None) -> dict[str, Any]:
    current_truth = current_truth or {}
    movement_gate = current_truth.get("movementGate") if isinstance(current_truth.get("movementGate"), dict) else {}
    target = current_truth.get("target") if isinstance(current_truth.get("target"), dict) else {}
    latest_pointer = (
        current_truth.get("latestPointerEvidence") if isinstance(current_truth.get("latestPointerEvidence"), dict) else {}
    )
    best_candidate = current_truth.get("bestCurrentCandidate") if isinstance(current_truth.get("bestCurrentCandidate"), dict) else {}
    blockers = current_truth.get("currentBlockers") if isinstance(current_truth.get("currentBlockers"), list) else []
    return {
        "status": current_truth.get("status"),
        "updatedAtUtc": current_truth.get("updatedAtUtc"),
        "target": {
            "processName": target.get("processName"),
            "processId": target.get("processId"),
            "targetWindowHandle": target.get("targetWindowHandle"),
            "live": target.get("live"),
            "status": target.get("status"),
        },
        "movementGate": {
            "allowed": movement_gate.get("allowed"),
            "status": movement_gate.get("status"),
            "reason": movement_gate.get("reason"),
        },
        "latestPointerEvidence": {
            "status": latest_pointer.get("status"),
            "movementAllowed": latest_pointer.get("movementAllowed"),
            "movementSent": latest_pointer.get("movementSent"),
            "candidateId": latest_pointer.get("candidateId"),
            "candidateAddressHex": latest_pointer.get("candidateAddressHex"),
            "historicalProofPointerArchive": latest_pointer.get("historicalProofPointerArchive"),
        },
        "bestCurrentCandidate": {
            "candidateId": best_candidate.get("candidateId"),
            "addressHex": best_candidate.get("addressHex"),
            "status": best_candidate.get("status"),
            "reusePolicy": best_candidate.get("reusePolicy"),
            "movementGradeOnlyThroughCurrentProof": best_candidate.get("movementGradeOnlyThroughCurrentProof"),
        },
        "currentBlockers": [str(item) for item in blockers],
        "nextRecommendedAction": current_truth.get("nextRecommendedAction"),
    }


def summarize_current_proof(current_proof: dict[str, Any] | None, *, now: datetime | None = None) -> dict[str, Any]:
    current_proof = current_proof or {}
    target = current_proof.get("target") if isinstance(current_proof.get("target"), dict) else {}
    latest_validation = current_proof.get("latestValidation") if isinstance(current_proof.get("latestValidation"), dict) else {}
    latest_proofonly = current_proof.get("latestProofOnly") if isinstance(current_proof.get("latestProofOnly"), dict) else {}
    stale_pointer = current_proof.get("staleProofPointer") if isinstance(current_proof.get("staleProofPointer"), dict) else {}
    preserved = stale_pointer.get("preservedEvidence") if isinstance(stale_pointer.get("preservedEvidence"), dict) else {}
    preserved_source = (
        preserved.get("riftscanCandidateSource")
        if isinstance(preserved.get("riftscanCandidateSource"), dict)
        else {}
    )
    return {
        "status": current_proof.get("status"),
        "lastUpdatedUtc": current_proof.get("lastUpdatedUtc"),
        "target": {
            "processName": target.get("processName"),
            "processId": target.get("processId"),
            "targetWindowHandle": target.get("targetWindowHandle"),
        },
        "latestValidation": {
            "status": latest_validation.get("status"),
            "movementAllowed": latest_validation.get("movementAllowed"),
            "movementSent": latest_validation.get("movementSent"),
            "currentCoordinate": latest_validation.get("currentCoordinate"),
            "generatedAtUtc": latest_validation.get("generatedAtUtc"),
        },
        "latestProofOnly": {
            "status": latest_proofonly.get("status"),
            "movementSent": latest_proofonly.get("movementSent"),
            "movementAttempted": latest_proofonly.get("movementAttempted"),
            "currentCoordinate": latest_proofonly.get("currentCoordinate"),
            "generatedAtUtc": latest_proofonly.get("generatedAtUtc"),
        },
        "proofFreshness": proof_anchor_freshness_summary(
            current_proof,
            latest_validation,
            latest_proofonly,
            now=now,
        ),
        "staleAnchor": {
            "candidateId": preserved_source.get("candidateId"),
            "addressHex": preserved_source.get("sourceAbsoluteAddressHex"),
            "candidateFile": preserved_source.get("matchFile"),
            "archivedPointer": stale_pointer.get("archivedPointer"),
            "reusePolicy": stale_pointer.get("reusePolicy"),
        },
    }


def summarize_live_target(coordinate_status: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(coordinate_status, dict):
        return {"checked": False, "verdict": None, "artifactPid": None, "artifactHwnd": None, "livePids": []}
    live_target = coordinate_status.get("liveTarget") if isinstance(coordinate_status.get("liveTarget"), dict) else {}
    live_pids = live_target.get("livePids") if isinstance(live_target.get("livePids"), list) else []
    return {
        "checked": bool(live_target),
        "status": live_target.get("status"),
        "checkedAtUtc": live_target.get("checkedAtUtc"),
        "verdict": live_target.get("verdict"),
        "artifactProcessName": live_target.get("artifactProcessName"),
        "artifactPid": live_target.get("artifactPid"),
        "artifactHwnd": live_target.get("artifactHwnd"),
        "livePids": live_pids,
        "artifactPidStale": live_target.get("verdict") == "artifact-pid-stale",
    }


def stale_live_target_reason(live_target: dict[str, Any], *, artifact_label: str = "current proof artifact") -> str:
    """Return live-aware movement/blocker text for stale artifact PID cases."""

    return (
        f"A rift_x64 process is visible with PID(s) {live_target.get('livePids') or []}, but the {artifact_label} "
        f"points at historical PID {live_target.get('artifactPid')} / HWND "
        f"{live_target.get('artifactHwnd')}. Movement remains blocked until the stale artifact is refreshed "
        "or the workflow is reclassified to the correct repair lane."
    )


def _is_superseded_no_live_blocker(blocker: str) -> bool:
    lower = blocker.lower()
    return "no live rift_x64 process" in lower or lower == "live-target-not-running:rift_x64"


def apply_live_target_overlay(
    *,
    current_truth_summary: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
    live_target: dict[str, Any],
    artifact_label: str = "current proof artifact",
) -> list[str]:
    """Keep status packets accurate when a live process exists but an artifact PID is stale."""

    if not live_target.get("artifactPidStale"):
        return blockers

    movement_gate = current_truth_summary.get("movementGate")
    if isinstance(movement_gate, dict) and movement_gate.get("allowed") is False:
        movement_gate["reason"] = stale_live_target_reason(live_target, artifact_label=artifact_label)

    filtered: list[str] = []
    for blocker in blockers:
        text = str(blocker)
        if _is_superseded_no_live_blocker(text):
            warnings.append(f"superseded-offline-blocker-live-target-detected:{text}")
            continue
        filtered.append(text)

    filtered.append(
        "live-target-artifact-pid-stale:"
        f"artifact={live_target.get('artifactPid')};"
        f"artifactHwnd={live_target.get('artifactHwnd')};"
        f"live={','.join(str(item) for item in live_target.get('livePids') or [])}"
    )
    return filtered


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        return None


def proof_target_matches_live_target(current_proof_summary: dict[str, Any], live_target: dict[str, Any]) -> bool:
    """Return true when the proof-anchor target matches one of the currently visible live PIDs."""

    target = current_proof_summary.get("target") if isinstance(current_proof_summary.get("target"), dict) else {}
    proof_pid = _int_or_none(target.get("processId"))
    if proof_pid is None:
        return False
    live_pids = {_int_or_none(item) for item in live_target.get("livePids") or []}
    live_pids.discard(None)
    return proof_pid in live_pids


def classify_workflow_state(
    *,
    current_proof_summary: dict[str, Any],
    live_target: dict[str, Any],
    static_owner_readback: dict[str, Any],
    navigation_pointer_discovery: dict[str, Any],
    current_truth_refresh_plan: dict[str, Any],
) -> dict[str, Any]:
    """Classify proof-current/static-root-null states so status does not loop back to proof recovery."""

    proof_status = str(current_proof_summary.get("status") or "")
    proof_current = proof_status == "current-target-proofonly-passed" and proof_target_matches_live_target(
        current_proof_summary, live_target
    )
    coordinate_chain = (
        static_owner_readback.get("coordinateChain") if isinstance(static_owner_readback.get("coordinateChain"), dict) else {}
    )
    chain_blockers = [str(item) for item in coordinate_chain.get("blockers") or []]
    static_root_null = coordinate_chain.get("verdict") == "root-pointer-null" or "root-pointer-null" in chain_blockers
    live_artifact_stale = bool(live_target.get("artifactPidStale"))

    if proof_current and live_artifact_stale and static_root_null:
        proof_target = (
            current_proof_summary.get("target") if isinstance(current_proof_summary.get("target"), dict) else {}
        )
        return {
            "classification": "static-chain-repair-needed",
            "status": "blocked",
            "proofAnchorCurrent": True,
            "staleArtifactIsCurrentTruthOrDashboard": True,
            "staticOwnerRootNull": True,
            "blocker": "static-chain-repair-needed:root-pointer-null",
            "warning": (
                "stale-current-truth-or-dashboard-artifact-not-current-proof:"
                f"artifact={live_target.get('artifactPid')};"
                f"artifactHwnd={live_target.get('artifactHwnd')};"
                f"proof={proof_target.get('processId')};"
                f"proofHwnd={proof_target.get('targetWindowHandle')}"
            ),
            "nextRecommendedAction": (
                "Proof anchor is current for the live target, but the current-truth/navigation dashboard still "
                "references a historical target and the promoted static owner root is null. Do not rerun proof-anchor "
                "recovery or apply stale current-truth refresh. Repair the static pointer chain/root next."
            ),
        }

    if proof_current and live_artifact_stale:
        return {
            "classification": "current-truth-status-refresh-needed",
            "status": "blocked",
            "proofAnchorCurrent": True,
            "staleArtifactIsCurrentTruthOrDashboard": True,
            "staticOwnerRootNull": False,
            "blocker": "current-truth-status-refresh-needed:stale-artifact-target",
            "warning": (
                "stale-current-truth-or-dashboard-artifact-not-current-proof:"
                f"artifact={live_target.get('artifactPid')};"
                f"live={','.join(str(item) for item in live_target.get('livePids') or [])}"
            ),
            "nextRecommendedAction": (
                "Proof anchor is current for the live target, but a current-truth/status artifact still references "
                "a historical target. Refresh the stale status source before movement or navigation decisions."
            ),
        }

    return {
        "classification": None,
        "status": None,
        "proofAnchorCurrent": proof_current,
        "staleArtifactIsCurrentTruthOrDashboard": False,
        "staticOwnerRootNull": static_root_null,
        "blocker": None,
        "warning": None,
        "nextRecommendedAction": None,
    }


def apply_proof_freshness_overlay(
    *,
    current_truth_summary: dict[str, Any],
    current_proof_summary: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> None:
    """Fail closed when current-truth movement status outlives proof-anchor freshness."""

    movement_gate = current_truth_summary.get("movementGate")
    if not isinstance(movement_gate, dict) or movement_gate.get("allowed") is not True:
        return

    latest_validation = current_proof_summary.get("latestValidation")
    latest_proofonly = current_proof_summary.get("latestProofOnly")
    proof_status = str(current_proof_summary.get("status") or "")
    validation_movement_allowed = (
        isinstance(latest_validation, dict) and latest_validation.get("movementAllowed") is True
    )
    proofonly_passed = (
        isinstance(latest_proofonly, dict) and str(latest_proofonly.get("status") or "") == "passed-proof-only"
    )
    if not (validation_movement_allowed or proof_status == "current-target-proofonly-passed" or proofonly_passed):
        return

    freshness = current_proof_summary.get("proofFreshness")
    if not isinstance(freshness, dict):
        return

    freshness_status = str(freshness.get("status") or "unknown")
    if freshness_status == "fresh":
        return

    age = freshness.get("ageSeconds")
    max_age = freshness.get("maxAgeSeconds")
    if freshness_status == "stale":
        blocked_status = "blocked-proof-anchor-age-out-of-range"
        blocker = f"proof-anchor-stale-for-movement:ageSeconds={age};maxAgeSeconds={max_age}"
        reason = (
            "Current-truth movement status was historically allowed, but the proof-anchor/readback timestamp "
            f"is now outside the movement preflight freshness budget ({age}s > {max_age}s). "
            "Run a fresh same-target ProofOnly/proof-anchor refresh before any movement."
        )
    elif freshness_status == "future-clock-skew":
        blocked_status = "blocked-proof-anchor-clock-skew"
        blocker = f"proof-anchor-clock-skew-for-movement:ageSeconds={age};maxAgeSeconds={max_age}"
        reason = (
            "Current-truth movement status was historically allowed, but the proof-anchor/readback timestamp "
            "appears to be in the future. Recheck clock/target state and rerun same-target ProofOnly before movement."
        )
    else:
        blocked_status = "blocked-proof-anchor-freshness-unknown"
        blocker = "proof-anchor-freshness-unknown-for-movement"
        reason = (
            "Current-truth movement status was historically allowed, but no parseable proof-anchor/readback freshness "
            "timestamp is available. Run a fresh same-target ProofOnly/proof-anchor refresh before any movement."
        )

    movement_gate["baseAllowedBeforeProofFreshnessOverlay"] = True
    movement_gate["allowed"] = False
    movement_gate["status"] = blocked_status
    movement_gate["reason"] = reason
    movement_gate["proofFreshness"] = freshness
    movement_gate["newMovementStillRequiresPreflightAndApproval"] = True
    blockers.append(blocker)
    warnings.append(f"movement-gate-overridden-by-proof-freshness:{freshness_status}")


def collect_git(repo_root: Path, commit_count: int, ref_count: int, errors: list[str]) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    status_env = run_command("git-status", ["git", "--no-pager", "status", "--short", "--branch"], repo_root)
    commands.append(status_env)
    head_env = run_command(
        "git-head",
        [
            "git",
            "--no-pager",
            "log",
            "--max-count=1",
            "--date=short",
            "--pretty=format:%h%x09%ad%x09%d%x09%s",
            "HEAD",
        ],
        repo_root,
    )
    commands.append(head_env)
    log_env = run_command(
        "git-log",
        [
            "git",
            "--no-pager",
            "log",
            f"--max-count={commit_count}",
            "--date=short",
            "--pretty=format:%h%x09%ad%x09%d%x09%s",
        ],
        repo_root,
    )
    commands.append(log_env)
    refs_env = run_command(
        "git-remote-refs",
        [
            "git",
            "--no-pager",
            "for-each-ref",
            "refs/remotes",
            "--sort=-committerdate",
            "--format=%(committerdate:short)%09%(refname:short)%09%(objectname:short)%09%(subject)",
            f"--count={ref_count}",
        ],
        repo_root,
    )
    commands.append(refs_env)

    for envelope in commands:
        if not envelope.get("ok"):
            errors.append(f"{envelope.get('label')}-failed:{envelope.get('exitCode')}:{envelope.get('error', '')}")

    status_summary = parse_git_status(str(status_env.get("stdoutPreview") or "")) if status_env.get("ok") else {}
    head_commits = parse_git_log(str(head_env.get("stdoutPreview") or "")) if head_env.get("ok") else []
    commits = parse_git_log(str(log_env.get("stdoutPreview") or "")) if log_env.get("ok") else []
    remote_refs = parse_refs(str(refs_env.get("stdoutPreview") or "")) if refs_env.get("ok") else []
    return {
        "status": status_summary,
        "head": head_commits[0] if head_commits else None,
        "recentCommits": commits,
        "remoteRefs": remote_refs,
        "commandEnvelopes": commands,
    }


def build_status_packet(
    repo_root: Path,
    *,
    commit_count: int = 100,
    ref_count: int = 30,
    run_coordinate_status: bool = True,
    check_opencode: bool = False,
    collect_git_state: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []

    latest_handoff = find_latest_handoff(repo_root)
    current_truth_md = repo_root / DEFAULT_CURRENT_TRUTH_MD
    current_truth_json_path = repo_root / DEFAULT_CURRENT_TRUTH_JSON
    current_proof_path = repo_root / DEFAULT_CURRENT_PROOF_JSON

    handoff = summarize_handoff(repo_root, latest_handoff, errors, warnings)
    current_truth_text = read_text(current_truth_md, errors, warnings, "current-truth-md")
    current_truth = read_json(current_truth_json_path, errors, warnings, "current-truth-json")
    current_proof = read_json(current_proof_path, errors, warnings, "current-proof-json")

    current_truth_summary = summarize_current_truth(current_truth)
    current_proof_summary = summarize_current_proof(current_proof, now=now)
    launcher_summary = latest_launcher_inspection(repo_root, errors, warnings)
    supervisor_summary = latest_character_login_supervisor(repo_root, errors, warnings)
    static_owner_readback = latest_static_owner_readback(repo_root, errors, warnings, now=now)
    navigation_pointer_discovery = latest_navigation_pointer_discovery(repo_root)
    current_truth_refresh_plan = latest_current_truth_refresh_plan(repo_root)
    current_truth_refresh_apply = latest_current_truth_refresh_apply(repo_root)
    facing_promotion_readiness_review = latest_facing_promotion_readiness_review(repo_root)
    blockers.extend(current_truth_summary.get("currentBlockers") or [])

    proof_status = current_proof_summary.get("status")
    if isinstance(proof_status, str) and proof_status.startswith("blocked"):
        blockers.append(f"current-proof-status:{proof_status}")

    apply_proof_freshness_overlay(
        current_truth_summary=current_truth_summary,
        current_proof_summary=current_proof_summary,
        blockers=blockers,
        warnings=warnings,
    )

    movement_allowed = (current_truth_summary.get("movementGate") or {}).get("allowed")
    movement_status = (current_truth_summary.get("movementGate") or {}).get("status")
    if movement_allowed is False:
        blockers.append(f"movement-not-allowed:{movement_status}")

    git_summary: dict[str, Any] = {}
    if collect_git_state:
        git_summary = collect_git(repo_root, commit_count, ref_count, errors)

    coordinate_status: dict[str, Any] | None = None
    coordinate_envelope: dict[str, Any] | None = None
    if run_coordinate_status:
        coordinate_script = repo_root / "scripts" / "coordinate_recovery_status.py"
        if coordinate_script.is_file():
            coordinate_envelope = run_command(
                "coordinate-recovery-status",
                [sys.executable, str(coordinate_script), "--json"],
                repo_root,
                timeout_seconds=60.0,
                expected_exit_codes={0, 2},
                capture_full_output=True,
            )
            coordinate_status = parse_json_from_envelope(
                coordinate_envelope,
                warnings,
                errors if not coordinate_envelope.get("ok") else warnings,
                "coordinate-recovery-status",
            )
            if coordinate_status:
                for blocker in coordinate_status.get("blockers") or []:
                    blockers.append(f"coordinate-status:{blocker}")
                live_target_summary = summarize_live_target(coordinate_status)
                if live_target_summary.get("artifactPidStale"):
                    warnings.append(
                        "current-truth-stale-live-target-detected:"
                        f"artifact={live_target_summary.get('artifactPid')};"
                        f"live={','.join(str(item) for item in live_target_summary.get('livePids') or [])}"
                    )
        else:
            warnings.append(f"coordinate-recovery-status-script-missing:{coordinate_script}")

    opencode: dict[str, Any] = {
        "retired": True,
        "retirementReason": "user-declared-not-used-for-this-repo",
        "checked": False,
        "available": None,
        "version": None,
        "desiredModel": desired_opencode_model(),
        "desiredVariant": desired_opencode_variant(),
        "modelProvider": opencode_provider_from_model(desired_opencode_model()),
        "modelVisible": None,
    }
    if check_opencode:
        warnings.append("opencode-check-explicitly-requested-but-repo-policy-is-retired")
        requested_model = desired_opencode_model()
        model_provider = opencode_provider_from_model(requested_model)
        envelope = run_command("opencode-version", opencode_version_command(), repo_root, timeout_seconds=15.0)
        model_envelope: dict[str, Any] | None = None
        visible_models: list[str] = []
        model_visible: bool | None = None
        if envelope.get("ok") and model_provider:
            model_envelope = run_command(
                "opencode-models",
                opencode_models_command(model_provider),
                repo_root,
                timeout_seconds=20.0,
            )
            if model_envelope.get("ok"):
                visible_models = parse_opencode_models(str(model_envelope.get("stdoutPreview") or ""))
                model_visible = requested_model in visible_models
                if not model_visible:
                    warnings.append(f"opencode-model-not-visible:{requested_model}")
            else:
                warnings.append(f"opencode-model-list-unavailable:{model_provider}")
        elif envelope.get("ok"):
            warnings.append(f"opencode-model-provider-unparseable:{requested_model}")
        opencode = {
            "retired": True,
            "retirementReason": "user-declared-not-used-for-this-repo",
            "checked": True,
            "available": bool(envelope.get("ok")),
            "version": str(envelope.get("stdoutPreview") or "").strip() or None,
            "desiredModel": requested_model,
            "desiredVariant": desired_opencode_variant(),
            "modelProvider": model_provider,
            "modelVisible": model_visible,
            "visibleModelsPreview": visible_models[:20],
            "commandEnvelope": envelope,
            "modelsCommandEnvelope": model_envelope,
        }
        if not envelope.get("ok"):
            warnings.append("opencode-version-unavailable")

    status = "failed" if errors else ("blocked" if blockers else "passed")
    live_target = summarize_live_target(coordinate_status)
    workflow_classification = classify_workflow_state(
        current_proof_summary=current_proof_summary,
        live_target=live_target,
        static_owner_readback=static_owner_readback,
        navigation_pointer_discovery=navigation_pointer_discovery,
        current_truth_refresh_plan=current_truth_refresh_plan,
    )
    if workflow_classification.get("blocker"):
        blockers.append(str(workflow_classification["blocker"]))
    if workflow_classification.get("warning"):
        warnings.append(str(workflow_classification["warning"]))

    next_action = current_truth_summary.get("nextRecommendedAction")
    movement_gate = current_truth_summary.get("movementGate") if isinstance(current_truth_summary.get("movementGate"), dict) else {}
    if live_target.get("artifactPidStale"):
        artifact_label = "current proof artifact"
        if workflow_classification.get("staleArtifactIsCurrentTruthOrDashboard"):
            artifact_label = "current-truth/status coordinate artifact"
        blockers = apply_live_target_overlay(
            current_truth_summary=current_truth_summary,
            blockers=[str(item) for item in blockers],
            warnings=warnings,
            live_target=live_target,
            artifact_label=artifact_label,
        )
        if workflow_classification.get("nextRecommendedAction"):
            next_action = str(workflow_classification["nextRecommendedAction"])
        else:
            next_action = (
                f"A rift_x64 process is visible with PID(s) {live_target.get('livePids')}, but the {artifact_label} points "
                f"at historical PID {live_target.get('artifactPid')} / HWND {live_target.get('artifactHwnd')}. "
                "Keep movement blocked until the stale artifact is refreshed or the workflow is reclassified."
            )
    elif str(movement_gate.get("status") or "").startswith("blocked-proof-anchor-"):
        next_action = (
            "Movement is proof-anchor freshness blocked. Continue no-input artifact/status diagnostics if useful, "
            "or request explicit same-target ProofOnly/proof-anchor refresh approval before any new movement."
        )
    else:
        navigation_readiness = (
            navigation_pointer_discovery.get("promotionReadiness")
            if isinstance(navigation_pointer_discovery.get("promotionReadiness"), dict)
            else {}
        )
        navigation_next = navigation_pointer_discovery.get("nextRecommendedAction")
        if (
            navigation_next
            and navigation_readiness.get("facingTarget") == "promoted-static-owner-facing-yaw-current-pid-readback-passed"
        ):
            next_action = navigation_next
        if (
            navigation_next
            and navigation_readiness.get("facingTarget") == "candidate-only-gates-packaged-requires-review"
        ):
            next_action = navigation_next
        review_next = facing_promotion_readiness_review.get("nextRecommendedAction")
        if (
            review_next
            and facing_promotion_readiness_review.get("status") == "passed"
            and navigation_readiness.get("facingTarget") != "promoted-static-owner-facing-yaw-current-pid-readback-passed"
        ):
            next_action = review_next
    if not next_action and blockers:
        next_action = "Resolve the listed blocker(s) before attempting live movement or proof promotion."
    if not next_action:
        next_action = "No blocker detected by the status packet; run targeted validation for the intended next change."

    status = "failed" if errors else ("blocked" if blockers else "passed")

    return {
        "schemaVersion": 1,
        "kind": "riftreader-local-workflow-status-packet",
        "legacyKind": "riftreader-opencode-non-codex-status-packet",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "repoRoot": str(repo_root),
        "blockers": unique([str(item) for item in blockers]),
        "warnings": unique(warnings),
        "errors": unique(errors),
        "latestHandoff": handoff,
        "currentTruth": {
            "markdownPath": as_repo_path(repo_root, current_truth_md),
            "jsonPath": as_repo_path(repo_root, current_truth_json_path),
            "summary": current_truth_summary,
            "markdownVerdictPreview": extract_section(current_truth_text or "", "## Verdict"),
        },
        "currentProof": {
            "path": as_repo_path(repo_root, current_proof_path),
            "summary": current_proof_summary,
        },
        "git": git_summary,
        "liveTarget": live_target,
        "workflowClassification": workflow_classification,
        "launcher": launcher_summary,
        "characterLoginSupervisor": supervisor_summary,
        "staticOwnerReadback": static_owner_readback,
        "navigationPointerDiscovery": navigation_pointer_discovery,
        "currentTruthRefreshPlan": current_truth_refresh_plan,
        "currentTruthRefreshApply": current_truth_refresh_apply,
        "facingPromotionReadinessReview": facing_promotion_readiness_review,
        "coordinateRecoveryStatus": coordinate_status,
        "coordinateRecoveryStatusCommand": coordinate_envelope,
        "opencode": opencode,
        "safety": safety_flags(),
        "artifacts": {},
        "nextRecommendedAction": next_action,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    git_status = ((packet.get("git") or {}).get("status") or {})
    head = (packet.get("git") or {}).get("head") or {}
    proof = ((packet.get("currentProof") or {}).get("summary") or {})
    truth = ((packet.get("currentTruth") or {}).get("summary") or {})
    movement_gate = truth.get("movementGate") or {}
    target = (proof.get("target") or truth.get("target") or {})
    coord = packet.get("coordinateRecoveryStatus") or {}
    live_target = packet.get("liveTarget") or coord.get("liveTarget") or {}
    launcher = packet.get("launcher") or {}
    supervisor = packet.get("characterLoginSupervisor") or {}
    navigation = packet.get("navigationPointerDiscovery") or {}
    truth_plan = packet.get("currentTruthRefreshPlan") or {}
    truth_apply = packet.get("currentTruthRefreshApply") or {}
    facing_review = packet.get("facingPromotionReadinessReview") or {}
    stale_anchor = proof.get("staleAnchor") or {}
    proof_freshness = proof.get("proofFreshness") if isinstance(proof.get("proofFreshness"), dict) else {}
    handoff = packet.get("latestHandoff") or {}
    opencode = packet.get("opencode") or {}
    artifacts = packet.get("artifacts") or {}

    lines = [
        "# RiftReader Local Workflow Status Packet",
        "",
        f"- Generated UTC: `{packet.get('generatedAtUtc')}`",
        f"- Status: `{packet.get('status')}`",
        f"- Branch: `{git_status.get('branch')}`",
        f"- Git clean: `{git_status.get('isClean')}`",
        f"- HEAD: `{head.get('hash')}` `{head.get('subject')}`",
        f"- Latest handoff: `{handoff.get('path')}`",
        f"- Current proof: `{proof.get('status')}`",
        f"- Proof freshness: `{proof_freshness.get('status')}` age `{proof_freshness.get('ageSeconds')}`s / max `{proof_freshness.get('maxAgeSeconds')}`s",
        f"- Movement allowed: `{movement_gate.get('allowed')}` / `{movement_gate.get('status')}`",
        f"- Target: PID `{target.get('processId')}`, HWND `{target.get('targetWindowHandle')}`, process `{target.get('processName')}`",
        f"- Live target check: `{live_target.get('verdict')}`; live PIDs `{live_target.get('livePids')}`",
        f"- Launcher: `{launcher.get('state')}`; Glyph PIDs `{launcher.get('launcherPids')}`; RIFT PIDs `{launcher.get('riftPids')}`",
        f"- Character login supervisor: `{supervisor.get('status')}`; approval required `{supervisor.get('approvalTokenRequired')}`",
        f"- Navigation pointer discovery: `{navigation.get('status')}`; freshness `{navigation.get('freshnessStatus')}`",
        f"- Current truth refresh plan: `{truth_plan.get('status')}`; updates `{truth_plan.get('updateCount')}`; apply approval required `{truth_plan.get('requiresExplicitApprovalForApply')}`",
        f"- Current truth refresh apply: `{truth_apply.get('status')}`; tracked write `{(truth_apply.get('safety') or {}).get('trackedTruthWritten')}`",
        f"- Facing promotion-readiness review: `{facing_review.get('status')}`; promotion allowed `{(facing_review.get('promotionDecision') or {}).get('promotionAllowed')}`",
        f"- Workflow mode: local ChatGPT/helpers; external-agent checks `{opencode.get('checked')}`",
        "",
        "## Stale proof boundary",
        "",
        f"- Stale candidate: `{stale_anchor.get('candidateId')}`",
        f"- Stale address: `{stale_anchor.get('addressHex')}`",
        f"- Reuse policy: `{stale_anchor.get('reusePolicy')}`",
        "",
        "## Blockers",
        "",
    ]
    for blocker in packet.get("blockers") or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Warnings", ""])
    for warning in packet.get("warnings") or ["none"]:
        lines.append(f"- `{warning}`")
    if navigation:
        facing = navigation.get("candidateFacingTarget") if isinstance(navigation.get("candidateFacingTarget"), dict) else {}
        turn = navigation.get("candidateTurnRate") if isinstance(navigation.get("candidateTurnRate"), dict) else {}
        owner304_semantics = navigation.get("owner304Semantics") if isinstance(navigation.get("owner304Semantics"), dict) else {}
        promoted = navigation.get("promotedCoordinate") if isinstance(navigation.get("promotedCoordinate"), dict) else {}
        lines.extend(
            [
                "",
                "## Navigation pointer discovery",
                "",
                f"- Status: `{navigation.get('status')}` / `{navigation.get('verdict')}`",
                f"- Freshness: `{navigation.get('freshnessStatus')}` stale sources `{navigation.get('staleSources')}`",
                f"- Promoted coordinate: `{promoted.get('status')}` chain `{promoted.get('chain')}`",
                f"- Candidate facing target: `{facing.get('status')}` offset `{facing.get('offset')}` max yaw delta `{facing.get('comparisonMaxAbsYawDeltaDegrees')}`",
                f"- Candidate turn rate: `{turn.get('status')}` offset `{turn.get('offset')}`",
                f"- Owner +0x304 semantics: `{owner304_semantics.get('status')}` role `{owner304_semantics.get('owner304Role')}`",
                f"- Next: {navigation.get('nextRecommendedAction')}",
                f"- Summary JSON: `{navigation.get('summaryJson')}`",
            ]
        )
    if truth_plan:
        lines.extend(
            [
                "",
                "## Current truth refresh plan",
                "",
                f"- Status: `{truth_plan.get('status')}` / `{truth_plan.get('verdict')}`",
                f"- Update count: `{truth_plan.get('updateCount')}`",
                f"- Apply approval required: `{truth_plan.get('requiresExplicitApprovalForApply')}`",
                f"- Summary JSON: `{truth_plan.get('summaryJson')}`",
                f"- Proposed diff: `{truth_plan.get('proposedCurrentTruthDiff')}`",
                f"- Next: {truth_plan.get('nextRecommendedAction')}",
            ]
        )
    if truth_apply:
        lines.extend(
            [
                "",
                "## Current truth refresh apply",
                "",
                f"- Status: `{truth_apply.get('status')}` / `{truth_apply.get('verdict')}`",
                f"- Apply requested: `{truth_apply.get('applyRequested')}`",
                f"- Tracked truth written: `{(truth_apply.get('safety') or {}).get('trackedTruthWritten')}`",
                f"- Summary JSON: `{truth_apply.get('summaryJson')}`",
                f"- Backup JSON: `{truth_apply.get('backupCurrentTruthJson')}`",
                f"- Next: {truth_apply.get('nextRecommendedAction')}",
            ]
        )
    lines.extend(["", "## Errors", ""])
    for error in packet.get("errors") or ["none"]:
        lines.append(f"- `{error}`")
    lines.extend(["", "## Recent commits", "", "| Hash | Date | Subject |", "|---|---|---|"])
    for commit in ((packet.get("git") or {}).get("recentCommits") or [])[:10]:
        lines.append(f"| `{commit.get('hash')}` | `{commit.get('date')}` | {commit.get('subject')} |")
    if not ((packet.get("git") or {}).get("recentCommits") or []):
        lines.append("| none | none | none |")
    lines.extend(["", "## Remote refs", "", "| Ref | Hash | Subject |", "|---|---|---|"])
    for ref in ((packet.get("git") or {}).get("remoteRefs") or [])[:10]:
        lines.append(f"| `{ref.get('ref')}` | `{ref.get('hash')}` | {ref.get('subject')} |")
    if not ((packet.get("git") or {}).get("remoteRefs") or []):
        lines.append("| none | none | none |")
    lines.extend(
        [
            "",
            "## Next recommended action",
            "",
            str(packet.get("nextRecommendedAction") or "none"),
            "",
            "## Safety",
            "",
            "| Flag | Value |",
            "|---|---:|",
        ]
    )
    for key, value in (packet.get("safety") or {}).items():
        lines.append(f"| `{key}` | `{value}` |")
    if artifacts:
        lines.extend(["", "## Artifacts", ""])
        for key, value in artifacts.items():
            lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines)


def compact_summary(packet: dict[str, Any]) -> dict[str, Any]:
    git_status = ((packet.get("git") or {}).get("status") or {})
    head = (packet.get("git") or {}).get("head") or {}
    proof = ((packet.get("currentProof") or {}).get("summary") or {})
    truth = ((packet.get("currentTruth") or {}).get("summary") or {})
    movement_gate = truth.get("movementGate") if isinstance(truth.get("movementGate"), dict) else {}
    live_target = packet.get("liveTarget") if isinstance(packet.get("liveTarget"), dict) else {}
    stale_anchor = proof.get("staleAnchor") if isinstance(proof.get("staleAnchor"), dict) else {}
    opencode = packet.get("opencode") if isinstance(packet.get("opencode"), dict) else {}
    launcher = packet.get("launcher") if isinstance(packet.get("launcher"), dict) else {}
    supervisor = packet.get("characterLoginSupervisor") if isinstance(packet.get("characterLoginSupervisor"), dict) else {}
    static_owner_readback = packet.get("staticOwnerReadback") if isinstance(packet.get("staticOwnerReadback"), dict) else {}
    workflow_classification = (
        packet.get("workflowClassification") if isinstance(packet.get("workflowClassification"), dict) else {}
    )
    navigation_pointer = (
        packet.get("navigationPointerDiscovery") if isinstance(packet.get("navigationPointerDiscovery"), dict) else {}
    )
    current_truth_refresh_plan = (
        packet.get("currentTruthRefreshPlan") if isinstance(packet.get("currentTruthRefreshPlan"), dict) else {}
    )
    current_truth_refresh_apply = (
        packet.get("currentTruthRefreshApply") if isinstance(packet.get("currentTruthRefreshApply"), dict) else {}
    )
    facing_promotion_readiness_review = (
        packet.get("facingPromotionReadinessReview")
        if isinstance(packet.get("facingPromotionReadinessReview"), dict)
        else {}
    )
    handoff = packet.get("latestHandoff") if isinstance(packet.get("latestHandoff"), dict) else {}
    repo_root_raw = packet.get("repoRoot")
    bridge_commands = bridge_command_capabilities(Path(str(repo_root_raw))) if repo_root_raw else []
    return {
        "schemaVersion": 1,
        "kind": "riftreader-local-compact-sitrep",
        "legacyKind": "riftreader-opencode-compact-sitrep",
        "generatedAtUtc": packet.get("generatedAtUtc"),
        "status": packet.get("status"),
        "workflowClassification": workflow_classification,
        "git": {
            "branch": git_status.get("branch"),
            "isClean": git_status.get("isClean"),
            "head": {"hash": head.get("hash"), "subject": head.get("subject")},
        },
        "latestHandoff": {"path": handoff.get("path"), "title": handoff.get("title")},
        "currentProof": {
            "status": proof.get("status"),
            "targetPid": (proof.get("target") or {}).get("processId") if isinstance(proof.get("target"), dict) else None,
            "targetHwnd": (proof.get("target") or {}).get("targetWindowHandle")
            if isinstance(proof.get("target"), dict)
            else None,
            "proofFreshness": proof.get("proofFreshness") if isinstance(proof.get("proofFreshness"), dict) else {},
            "staleCandidateId": stale_anchor.get("candidateId"),
            "staleAddressHex": stale_anchor.get("addressHex"),
            "reusePolicy": stale_anchor.get("reusePolicy"),
        },
        "liveTarget": {
            "verdict": live_target.get("verdict"),
            "livePids": live_target.get("livePids") or [],
            "artifactPid": live_target.get("artifactPid"),
            "artifactHwnd": live_target.get("artifactHwnd"),
            "artifactPidStale": bool(live_target.get("artifactPidStale")),
        },
        "movementGate": {
            "allowed": movement_gate.get("allowed"),
            "status": movement_gate.get("status"),
            "reason": movement_gate.get("reason"),
        },
        "opencode": {
            "retired": opencode.get("retired", True),
            "retirementReason": opencode.get("retirementReason") or "user-declared-not-used-for-this-repo",
            "checked": opencode.get("checked"),
            "available": opencode.get("available"),
            "version": opencode.get("version"),
            "desiredModel": opencode.get("desiredModel"),
            "desiredVariant": opencode.get("desiredVariant"),
            "modelProvider": opencode.get("modelProvider"),
            "modelVisible": opencode.get("modelVisible"),
        },
        "launcher": {
            "status": launcher.get("status"),
            "observedAtUtc": launcher.get("observedAtUtc"),
            "state": launcher.get("state"),
            "reloginState": launcher.get("reloginState"),
            "automationRecommendation": launcher.get("automationRecommendation"),
            "buttonAutomationPolicy": launcher.get("buttonAutomationPolicy"),
            "launcherPresent": launcher.get("launcherPresent"),
            "launcherPids": launcher.get("launcherPids") or [],
            "launcherWindowState": launcher.get("launcherWindowState"),
            "launcherMainHwnd": launcher.get("launcherMainHwnd"),
            "gamePresent": launcher.get("gamePresent"),
            "riftPids": launcher.get("riftPids") or [],
            "riftChildOfLauncher": launcher.get("riftChildOfLauncher"),
            "summaryJson": launcher.get("summaryJson"),
            "freshness": launcher.get("freshness") or {},
            "visibleStateClassifier": launcher.get("visibleStateClassifier") or {},
            "relaunchReadiness": launcher.get("relaunchReadiness") or {},
        },
        "characterLoginSupervisor": {
            "status": supervisor.get("status"),
            "observedAtUtc": supervisor.get("observedAtUtc"),
            "freshness": supervisor.get("freshness") or {},
            "targetCharacter": supervisor.get("targetCharacter"),
            "targetPid": supervisor.get("targetPid"),
            "targetHwnd": supervisor.get("targetHwnd"),
            "selectedCharacter": supervisor.get("selectedCharacter"),
            "screenClassification": supervisor.get("screenClassification"),
            "futureExecutorMayClickPlay": supervisor.get("futureExecutorMayClickPlay"),
            "mayClickPlayInThisSupervisor": supervisor.get("mayClickPlayInThisSupervisor"),
            "approvalTokenRequired": supervisor.get("approvalTokenRequired"),
            "approvalTokenStoredInStatus": supervisor.get("approvalTokenStoredInStatus"),
            "manifestStatus": supervisor.get("manifestStatus"),
            "dataBlockers": supervisor.get("dataBlockers") or [],
            "executionBlockers": supervisor.get("executionBlockers") or [],
            "summaryJson": supervisor.get("summaryJson"),
        },
        "staticOwnerReadback": {
            "coordinateChain": static_owner_readback.get("coordinateChain") or {},
            "navState": static_owner_readback.get("navState") or {},
        },
        "navigationPointerDiscovery": {
            "status": navigation_pointer.get("status") or "not-collected",
            "verdict": navigation_pointer.get("verdict"),
            "observedAtUtc": navigation_pointer.get("observedAtUtc"),
            "summaryJson": navigation_pointer.get("summaryJson"),
            "summaryMarkdown": navigation_pointer.get("summaryMarkdown"),
            "freshnessStatus": navigation_pointer.get("freshnessStatus"),
            "staleSources": navigation_pointer.get("staleSources") or [],
            "unknownSources": navigation_pointer.get("unknownSources") or [],
            "target": navigation_pointer.get("target") or {},
            "promotedCoordinate": navigation_pointer.get("promotedCoordinate") or {},
            "candidateFacingTarget": navigation_pointer.get("candidateFacingTarget") or {},
            "candidateTurnRate": navigation_pointer.get("candidateTurnRate") or {},
            "owner304Semantics": navigation_pointer.get("owner304Semantics") or {},
            "candidateLedger": navigation_pointer.get("candidateLedger") or {},
            "navigationControlChains": navigation_pointer.get("navigationControlChains") or {},
            "coordinateDeltaCandidate": navigation_pointer.get("coordinateDeltaCandidate") or {},
            "proofGates": navigation_pointer.get("proofGates") or {},
            "promotionReadiness": navigation_pointer.get("promotionReadiness") or {},
            "nextRecommendedAction": navigation_pointer.get("nextRecommendedAction"),
            "recommendedActions": navigation_pointer.get("recommendedActions") or [],
            "blockers": navigation_pointer.get("blockers") or [],
            "warnings": navigation_pointer.get("warnings") or [],
            "errors": navigation_pointer.get("errors") or [],
            "safety": navigation_pointer.get("safety") or {},
        },
        "currentTruthRefreshPlan": {
            "status": current_truth_refresh_plan.get("status") or "not-collected",
            "verdict": current_truth_refresh_plan.get("verdict"),
            "observedAtUtc": current_truth_refresh_plan.get("observedAtUtc"),
            "summaryJson": current_truth_refresh_plan.get("summaryJson"),
            "summaryMarkdown": current_truth_refresh_plan.get("summaryMarkdown"),
            "proposedCurrentTruthJson": current_truth_refresh_plan.get("proposedCurrentTruthJson"),
            "proposedCurrentTruthDiff": current_truth_refresh_plan.get("proposedCurrentTruthDiff"),
            "updateCount": current_truth_refresh_plan.get("updateCount"),
            "requiresExplicitApprovalForApply": current_truth_refresh_plan.get("requiresExplicitApprovalForApply"),
            "nextRecommendedAction": current_truth_refresh_plan.get("nextRecommendedAction"),
            "blockers": current_truth_refresh_plan.get("blockers") or [],
            "warnings": current_truth_refresh_plan.get("warnings") or [],
            "errors": current_truth_refresh_plan.get("errors") or [],
            "safety": current_truth_refresh_plan.get("safety") or {},
        },
        "currentTruthRefreshApply": {
            "status": current_truth_refresh_apply.get("status") or "not-collected",
            "verdict": current_truth_refresh_apply.get("verdict"),
            "observedAtUtc": current_truth_refresh_apply.get("observedAtUtc"),
            "summaryJson": current_truth_refresh_apply.get("summaryJson"),
            "summaryMarkdown": current_truth_refresh_apply.get("summaryMarkdown"),
            "backupCurrentTruthJson": current_truth_refresh_apply.get("backupCurrentTruthJson"),
            "applyRequested": current_truth_refresh_apply.get("applyRequested"),
            "target": current_truth_refresh_apply.get("target") or {},
            "plan": current_truth_refresh_apply.get("plan") or {},
            "hashes": current_truth_refresh_apply.get("hashes") or {},
            "nextRecommendedAction": current_truth_refresh_apply.get("nextRecommendedAction"),
            "blockers": current_truth_refresh_apply.get("blockers") or [],
            "warnings": current_truth_refresh_apply.get("warnings") or [],
            "errors": current_truth_refresh_apply.get("errors") or [],
            "safety": current_truth_refresh_apply.get("safety") or {},
        },
        "facingPromotionReadinessReview": {
            "status": facing_promotion_readiness_review.get("status") or "not-collected",
            "verdict": facing_promotion_readiness_review.get("verdict"),
            "observedAtUtc": facing_promotion_readiness_review.get("observedAtUtc"),
            "summaryJson": facing_promotion_readiness_review.get("summaryJson"),
            "summaryMarkdown": facing_promotion_readiness_review.get("summaryMarkdown"),
            "target": facing_promotion_readiness_review.get("target") or {},
            "candidate": facing_promotion_readiness_review.get("candidate") or {},
            "promotionDecision": facing_promotion_readiness_review.get("promotionDecision") or {},
            "nextRecommendedAction": facing_promotion_readiness_review.get("nextRecommendedAction"),
            "blockers": facing_promotion_readiness_review.get("blockers") or [],
            "warnings": facing_promotion_readiness_review.get("warnings") or [],
            "errors": facing_promotion_readiness_review.get("errors") or [],
            "safety": facing_promotion_readiness_review.get("safety") or {},
            "sourceSafety": facing_promotion_readiness_review.get("sourceSafety") or {},
        },
        "bridgeCommands": bridge_commands,
        "blockers": packet.get("blockers") or [],
        "warnings": packet.get("warnings") or [],
        "errors": packet.get("errors") or [],
        "nextRecommendedAction": packet.get("nextRecommendedAction"),
        "safety": packet.get("safety") or {},
        "artifacts": packet.get("artifacts") or {},
    }


def render_compact_markdown(packet: dict[str, Any]) -> str:
    summary = compact_summary(packet)
    git = summary.get("git") or {}
    head = git.get("head") or {}
    proof = summary.get("currentProof") or {}
    live_target = summary.get("liveTarget") or {}
    movement_gate = summary.get("movementGate") or {}
    opencode = summary.get("opencode") or {}
    launcher = summary.get("launcher") or {}
    supervisor = summary.get("characterLoginSupervisor") or {}
    navigation = summary.get("navigationPointerDiscovery") or {}
    truth_plan = summary.get("currentTruthRefreshPlan") or {}
    truth_apply = summary.get("currentTruthRefreshApply") or {}
    facing_review = summary.get("facingPromotionReadinessReview") or {}
    bridge_commands = summary.get("bridgeCommands") or []
    lines = [
        "# RiftReader Local Compact SITREP",
        "",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Branch: `{git.get('branch')}`; clean `{git.get('isClean')}`",
        f"- HEAD: `{head.get('hash')}` {head.get('subject')}",
        f"- Proof: `{proof.get('status')}` target PID `{proof.get('targetPid')}` HWND `{proof.get('targetHwnd')}`",
        f"- Proof freshness: `{(proof.get('proofFreshness') or {}).get('status')}` age `{(proof.get('proofFreshness') or {}).get('ageSeconds')}`s / max `{(proof.get('proofFreshness') or {}).get('maxAgeSeconds')}`s",
        f"- Live target: `{live_target.get('verdict')}` live PIDs `{live_target.get('livePids')}`",
        f"- Movement: `{movement_gate.get('allowed')}` / `{movement_gate.get('status')}`",
        f"- Launcher: `{launcher.get('state')}` Glyph PIDs `{launcher.get('launcherPids')}` RIFT PIDs `{launcher.get('riftPids')}`",
        f"- Character login supervisor: `{supervisor.get('status')}` target `{supervisor.get('targetCharacter')}` approval required `{supervisor.get('approvalTokenRequired')}`",
        f"- Navigation pointer discovery: `{navigation.get('status')}` freshness `{navigation.get('freshnessStatus')}` stale `{navigation.get('staleSources')}`",
        f"- Current truth refresh plan: `{truth_plan.get('status')}` updates `{truth_plan.get('updateCount')}` apply approval required `{truth_plan.get('requiresExplicitApprovalForApply')}`",
        f"- Current truth refresh apply: `{truth_apply.get('status')}` tracked write `{(truth_apply.get('safety') or {}).get('trackedTruthWritten')}`",
        f"- Facing promotion-readiness review: `{facing_review.get('status')}` promotion allowed `{(facing_review.get('promotionDecision') or {}).get('promotionAllowed')}`",
        f"- Workflow mode: local ChatGPT/helpers; external-agent checks `{opencode.get('checked')}`",
        f"- Next: {summary.get('nextRecommendedAction')}",
        "",
        "## Stale proof boundary",
        "",
        f"- Candidate: `{proof.get('staleCandidateId')}`",
        f"- Address: `{proof.get('staleAddressHex')}`",
        f"- Reuse policy: `{proof.get('reusePolicy')}`",
        "",
        "## Navigation pointer discovery",
        "",
        f"- Summary JSON: `{navigation.get('summaryJson')}`",
        f"- Promoted coordinate: `{(navigation.get('promotedCoordinate') or {}).get('status')}` chain `{(navigation.get('promotedCoordinate') or {}).get('chain')}`",
        f"- Facing target/yaw: `{(navigation.get('candidateFacingTarget') or {}).get('status')}` offset `{(navigation.get('candidateFacingTarget') or {}).get('offset')}` max yaw `{(navigation.get('candidateFacingTarget') or {}).get('comparisonMaxAbsYawDeltaDegrees')}`",
        f"- Candidate turn rate: `{(navigation.get('candidateTurnRate') or {}).get('status')}` offset `{(navigation.get('candidateTurnRate') or {}).get('offset')}`",
        f"- Owner +0x304 semantics: `{(navigation.get('owner304Semantics') or {}).get('status')}` role `{(navigation.get('owner304Semantics') or {}).get('owner304Role')}`",
        f"- Proof gates: `{(navigation.get('promotionReadiness') or {}).get('facingThreePoseGate')}` three-pose, `{(navigation.get('promotionReadiness') or {}).get('restartRelogSurvival')}` restart, `{(navigation.get('promotionReadiness') or {}).get('turnForwardLiveProgress')}` turn-forward",
        f"- Next: {navigation.get('nextRecommendedAction')}",
        "",
        "## Current truth refresh plan",
        "",
        f"- Summary JSON: `{truth_plan.get('summaryJson')}`",
        f"- Proposed diff: `{truth_plan.get('proposedCurrentTruthDiff')}`",
        f"- Update count: `{truth_plan.get('updateCount')}`",
        f"- Apply approval required: `{truth_plan.get('requiresExplicitApprovalForApply')}`",
        f"- Next: {truth_plan.get('nextRecommendedAction')}",
        "",
        "## Current truth refresh apply",
        "",
        f"- Summary JSON: `{truth_apply.get('summaryJson')}`",
        f"- Status: `{truth_apply.get('status')}` / `{truth_apply.get('verdict')}`",
        f"- Apply requested: `{truth_apply.get('applyRequested')}`",
        f"- Tracked truth written: `{(truth_apply.get('safety') or {}).get('trackedTruthWritten')}`",
        f"- Backup JSON: `{truth_apply.get('backupCurrentTruthJson')}`",
        f"- Next: {truth_apply.get('nextRecommendedAction')}",
        "",
        "## Facing promotion-readiness review",
        "",
        f"- Summary JSON: `{facing_review.get('summaryJson')}`",
        f"- Status: `{facing_review.get('status')}` / `{facing_review.get('verdict')}`",
        f"- Review passed: `{(facing_review.get('promotionDecision') or {}).get('reviewPassed')}`",
        f"- Promotion allowed: `{(facing_review.get('promotionDecision') or {}).get('promotionAllowed')}`",
        f"- Promotion performed: `{(facing_review.get('promotionDecision') or {}).get('promotionPerformed')}`",
        f"- Fresh readback required: `{(facing_review.get('promotionDecision') or {}).get('freshPrePromotionReadbackRequired')}`",
        f"- Next: {facing_review.get('nextRecommendedAction')}",
        "",
        "## Bridge commands",
        "",
    ]
    for command in bridge_commands:
        lines.append(
            f"- `{command.get('key')}` exists `{command.get('exists')}`: `{command.get('command')}`"
        )
    lines.extend([
        "",
        "## Blockers",
        "",
    ])
    for blocker in summary.get("blockers") or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Warnings", ""])
    for warning in summary.get("warnings") or ["none"]:
        lines.append(f"- `{warning}`")
    return "\n".join(lines)


def write_outputs(packet: dict[str, Any], repo_root: Path, output_root: Path | None = None) -> dict[str, str]:
    base = output_root if output_root is not None else repo_root / DEFAULT_OUTPUT_DIR
    if not base.is_absolute():
        base = repo_root / base
    output_dir = timestamped_output_dir(base)
    json_path = output_dir / "workflow-status-summary.json"
    md_path = output_dir / "WORKFLOW_STATUS_REPORT.md"
    compact_json_path = output_dir / "compact-sitrep.json"
    compact_md_path = output_dir / "COMPACT_SITREP.md"
    artifacts = {
        "outputDir": as_repo_path(repo_root, output_dir) or str(output_dir),
        "summaryJson": as_repo_path(repo_root, json_path) or str(json_path),
        "summaryMarkdown": as_repo_path(repo_root, md_path) or str(md_path),
        "compactJson": as_repo_path(repo_root, compact_json_path) or str(compact_json_path),
        "compactMarkdown": as_repo_path(repo_root, compact_md_path) or str(compact_md_path),
    }
    packet["artifacts"] = artifacts
    json_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(packet) + "\n", encoding="utf-8")
    compact_json_path.write_text(json.dumps(compact_summary(packet), indent=2), encoding="utf-8")
    compact_md_path.write_text(render_compact_markdown(packet) + "\n", encoding="utf-8")
    return artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a safe RiftReader local ChatGPT/non-Codex status packet.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root. Defaults to auto-detect from cwd.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--compact-json", action="store_true", help="Print compact machine-readable SITREP JSON.")
    parser.add_argument("--compact", action="store_true", help="Print compact Markdown SITREP.")
    parser.add_argument("--write", action="store_true", help="Write ignored JSON/Markdown artifacts under .riftreader-local.")
    parser.add_argument("--output-dir", default=None, help="Override output root for --write.")
    parser.add_argument("--commits", type=int, default=100, help="Number of recent commits to include in JSON.")
    parser.add_argument("--refs", type=int, default=30, help="Number of remote refs to include.")
    parser.add_argument(
        "--skip-coordinate-status",
        action="store_true",
        help="Do not run scripts/coordinate_recovery_status.py --json.",
    )
    parser.add_argument(
        "--check-opencode",
        action="store_true",
        help="Deprecated compatibility check. OpenCode is retired for this repo and is off by default.",
    )
    parser.add_argument(
        "--skip-opencode-check",
        action="store_true",
        help="Deprecated compatibility flag; OpenCode checks are already off by default.",
    )
    parser.add_argument("--skip-git", action="store_true", help="Do not collect git status/log/ref summaries.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    packet = build_status_packet(
        repo_root,
        commit_count=args.commits,
        ref_count=args.refs,
        run_coordinate_status=not args.skip_coordinate_status,
        check_opencode=bool(args.check_opencode and not args.skip_opencode_check),
        collect_git_state=not args.skip_git,
    )
    if args.write:
        output_root = Path(args.output_dir) if args.output_dir else None
        write_outputs(packet, repo_root, output_root)
    if args.compact_json:
        print(json.dumps(compact_summary(packet), indent=2))
    elif args.compact:
        print(render_compact_markdown(packet))
    elif args.json:
        print(json.dumps(packet, indent=2))
    else:
        print(render_markdown(packet))
    if packet.get("status") == "failed":
        return 1
    if packet.get("status") == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
