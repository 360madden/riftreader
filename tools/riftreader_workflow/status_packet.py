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
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "workflow-status"
DEFAULT_LAUNCHER_INSPECTION_DIR = Path(".riftreader-local") / "launcher-inspection"
DEFAULT_CHARACTER_LOGIN_SUPERVISOR_DIR = Path(".riftreader-local") / "character-login-supervisor"
DEFAULT_LAUNCHER_INSPECTION_MAX_AGE_SECONDS = 30 * 60
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


def summarize_current_proof(current_proof: dict[str, Any] | None) -> dict[str, Any]:
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
        },
        "latestProofOnly": {
            "status": latest_proofonly.get("status"),
            "movementSent": latest_proofonly.get("movementSent"),
            "movementAttempted": latest_proofonly.get("movementAttempted"),
            "currentCoordinate": latest_proofonly.get("currentCoordinate"),
        },
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


def stale_live_target_reason(live_target: dict[str, Any]) -> str:
    """Return live-aware movement/blocker text for stale artifact PID cases."""

    return (
        f"A rift_x64 process is visible with PID(s) {live_target.get('livePids') or []}, but the current proof "
        f"artifact points at historical PID {live_target.get('artifactPid')} / HWND "
        f"{live_target.get('artifactHwnd')}. Movement remains blocked until safe current-target "
        "reacquisition/status refresh and same-target proof validation pass."
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
) -> list[str]:
    """Keep status packets accurate when a live process exists but old proof is stale."""

    if not live_target.get("artifactPidStale"):
        return blockers

    movement_gate = current_truth_summary.get("movementGate")
    if isinstance(movement_gate, dict) and movement_gate.get("allowed") is False:
        movement_gate["reason"] = stale_live_target_reason(live_target)

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
    current_proof_summary = summarize_current_proof(current_proof)
    launcher_summary = latest_launcher_inspection(repo_root, errors, warnings)
    supervisor_summary = latest_character_login_supervisor(repo_root, errors, warnings)
    blockers.extend(current_truth_summary.get("currentBlockers") or [])

    proof_status = current_proof_summary.get("status")
    if isinstance(proof_status, str) and proof_status.startswith("blocked"):
        blockers.append(f"current-proof-status:{proof_status}")

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
    next_action = current_truth_summary.get("nextRecommendedAction")
    if live_target.get("artifactPidStale"):
        blockers = apply_live_target_overlay(
            current_truth_summary=current_truth_summary,
            blockers=[str(item) for item in blockers],
            warnings=warnings,
            live_target=live_target,
        )
        next_action = (
            f"A rift_x64 process is visible with PID(s) {live_target.get('livePids')}, but the current proof artifact points "
            f"at historical PID {live_target.get('artifactPid')} / HWND {live_target.get('artifactHwnd')}. "
            "Keep movement blocked, do not reuse stale proof, and run safe current-target reacquisition/status refresh "
            "before ProofOnly or movement."
        )
    if not next_action and blockers:
        next_action = "Resolve the listed blocker(s) before attempting live movement or proof promotion."
    if not next_action:
        next_action = "No blocker detected by the status packet; run targeted validation for the intended next change."

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
        "launcher": launcher_summary,
        "characterLoginSupervisor": supervisor_summary,
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
    stale_anchor = proof.get("staleAnchor") or {}
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
        f"- Movement allowed: `{movement_gate.get('allowed')}` / `{movement_gate.get('status')}`",
        f"- Target: PID `{target.get('processId')}`, HWND `{target.get('targetWindowHandle')}`, process `{target.get('processName')}`",
        f"- Live target check: `{live_target.get('verdict')}`; live PIDs `{live_target.get('livePids')}`",
        f"- Launcher: `{launcher.get('state')}`; Glyph PIDs `{launcher.get('launcherPids')}`; RIFT PIDs `{launcher.get('riftPids')}`",
        f"- Character login supervisor: `{supervisor.get('status')}`; approval required `{supervisor.get('approvalTokenRequired')}`",
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
    handoff = packet.get("latestHandoff") if isinstance(packet.get("latestHandoff"), dict) else {}
    repo_root_raw = packet.get("repoRoot")
    bridge_commands = bridge_command_capabilities(Path(str(repo_root_raw))) if repo_root_raw else []
    return {
        "schemaVersion": 1,
        "kind": "riftreader-local-compact-sitrep",
        "legacyKind": "riftreader-opencode-compact-sitrep",
        "generatedAtUtc": packet.get("generatedAtUtc"),
        "status": packet.get("status"),
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
    bridge_commands = summary.get("bridgeCommands") or []
    lines = [
        "# RiftReader Local Compact SITREP",
        "",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Branch: `{git.get('branch')}`; clean `{git.get('isClean')}`",
        f"- HEAD: `{head.get('hash')}` {head.get('subject')}",
        f"- Proof: `{proof.get('status')}` target PID `{proof.get('targetPid')}` HWND `{proof.get('targetHwnd')}`",
        f"- Live target: `{live_target.get('verdict')}` live PIDs `{live_target.get('livePids')}`",
        f"- Movement: `{movement_gate.get('allowed')}` / `{movement_gate.get('status')}`",
        f"- Launcher: `{launcher.get('state')}` Glyph PIDs `{launcher.get('launcherPids')}` RIFT PIDs `{launcher.get('riftPids')}`",
        f"- Character login supervisor: `{supervisor.get('status')}` target `{supervisor.get('targetCharacter')}` approval required `{supervisor.get('approvalTokenRequired')}`",
        f"- Workflow mode: local ChatGPT/helpers; external-agent checks `{opencode.get('checked')}`",
        f"- Next: {summary.get('nextRecommendedAction')}",
        "",
        "## Stale proof boundary",
        "",
        f"- Candidate: `{proof.get('staleCandidateId')}`",
        f"- Address: `{proof.get('staleAddressHex')}`",
        f"- Reuse policy: `{proof.get('reusePolicy')}`",
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
