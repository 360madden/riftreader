#!/usr/bin/env python3
"""Final readiness gate for the RiftReader ChatGPT MCP product lane."""

from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, run_command_envelope, safety_flags, unique, utc_iso
    from .mcp_phase2_status import compact_phase2_status, phase2_status
    from .mcp_workflow_state import build_mcp_workflow_state, safe_load_json, standard_commands
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, run_command_envelope, safety_flags, unique, utc_iso
    from riftreader_workflow.mcp_phase2_status import compact_phase2_status, phase2_status
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, safe_load_json, standard_commands


APPROVED_TOOL_NAMES = (
    "health",
    "get_repo_status",
    "get_latest_handoff",
    "get_package_proposal_template",
    "submit_package_proposal",
    "list_inbox",
    "review_latest_package_draft",
    "dry_run_latest_package_draft",
)

FALSE_SAFETY_KEYS = (
    "movementSent",
    "inputSent",
    "reloaduiSent",
    "screenshotKeySent",
    "x64dbgAttach",
    "providerWrites",
    "gitMutation",
    "applyFlagSent",
    "savedVariablesUsedAsLiveTruth",
)
TRUE_HEALTH_SAFETY_KEYS = (
    "noShellExecutionEndpoint",
    "noGitMutationEndpoint",
    "noArbitraryFilesystemRead",
    "noArbitraryFilesystemWrite",
    "noRiftLiveInputEndpoint",
    "noExistingMcpProxy",
    "noWindowsMcpProxy",
    "noRiftGameMcpProxy",
)
DEFAULT_LOOPBACK_HOST = "127.0.0.1"
DEFAULT_MCP_SERVE_PORT = 8770
LOCAL_IGNORED_ARTIFACT_ROOT = ".riftreader-local"


def _bool(value: object) -> bool:
    return bool(value) if value is not None else False


def _latest_path(repo_root: Path, state_payload: dict[str, Any], *kinds: str) -> Path | None:
    latest = state_payload.get("latestArtifacts") if isinstance(state_payload.get("latestArtifacts"), dict) else {}
    for kind in kinds:
        item = latest.get(kind)
        if not isinstance(item, dict):
            continue
        path_value = item.get("path")
        if not path_value:
            continue
        path = repo_root / str(path_value)
        if path.is_file():
            return path
    return None


def _extract_health_and_tools(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    client = payload.get("client") if isinstance(payload.get("client"), dict) else {}
    stages = payload.get("stages") if isinstance(payload.get("stages"), dict) else {}
    transport_stage = stages.get("transport_smoke") if isinstance(stages.get("transport_smoke"), dict) else {}
    transport_client = transport_stage.get("client") if isinstance(transport_stage.get("client"), dict) else {}

    health = client.get("healthStructuredContent") if isinstance(client.get("healthStructuredContent"), dict) else None
    if health is None:
        health = transport_client.get("healthStructuredContent") if isinstance(transport_client.get("healthStructuredContent"), dict) else None
    if health is None and payload.get("kind") == "riftreader-chatgpt-mcp-health":
        health = payload

    tool_names = client.get("toolNames") if isinstance(client.get("toolNames"), list) else None
    if tool_names is None:
        tool_names = transport_client.get("toolNames") if isinstance(transport_client.get("toolNames"), list) else None
    if tool_names is None and health is not None:
        tools = health.get("tools") if isinstance(health.get("tools"), list) else []
        tool_names = [str(tool.get("name")) for tool in tools if isinstance(tool, dict) and tool.get("name")]
    if tool_names is None:
        registered = client.get("registeredTools") if isinstance(client.get("registeredTools"), list) else []
        tool_names = [str(tool.get("name")) for tool in registered if isinstance(tool, dict) and tool.get("name")]

    return health, [str(name) for name in (tool_names or [])]


def tool_surface_status(repo_root: Path, state_payload: dict[str, Any]) -> dict[str, Any]:
    path = _latest_path(repo_root, state_payload, "proposal-smoke", "readiness")
    blockers: list[str] = []
    warnings: list[str] = []
    if path is None:
        return {
            "status": "blocked",
            "ok": False,
            "blockers": ["safety:tool-surface-unavailable"],
            "warnings": [],
            "sourcePath": None,
            "toolNames": [],
            "approvedToolNames": list(APPROVED_TOOL_NAMES),
        }
    payload, warning = safe_load_json(path)
    if warning or payload is None:
        return {
            "status": "blocked",
            "ok": False,
            "blockers": [f"safety:tool-surface-unavailable:{warning}"],
            "warnings": [],
            "sourcePath": str(path),
            "toolNames": [],
            "approvedToolNames": list(APPROVED_TOOL_NAMES),
        }

    health, tool_names = _extract_health_and_tools(payload)
    if tuple(tool_names) != APPROVED_TOOL_NAMES:
        blockers.append("safety:unexpected-tool-surface")
    if health is None:
        blockers.append("safety:health-unavailable")
        health_safety: dict[str, Any] = {}
    else:
        health_safety = health.get("safety") if isinstance(health.get("safety"), dict) else {}
        if health.get("repoRoot") != "." or health_safety.get("absoluteRepoRootExposed") is not False:
            blockers.append("safety:absolute-repo-root-exposed")
        for key in TRUE_HEALTH_SAFETY_KEYS:
            if health_safety.get(key) is not True:
                blockers.append(f"safety:unsafe-tool-boundary:{key}")

    root_safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    for key in FALSE_SAFETY_KEYS:
        value = root_safety.get(key)
        if value is True:
            blockers.append(f"safety:unsafe-action:{key}")
    if root_safety.get("noCheatEngine") is False:
        blockers.append("safety:unsafe-action:noCheatEngine")

    blockers = unique(blockers)
    return {
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "sourcePath": str(path),
        "toolNames": tool_names,
        "approvedToolNames": list(APPROVED_TOOL_NAMES),
        "repoRootRedacted": bool(health and health.get("repoRoot") == "." and health_safety.get("absoluteRepoRootExposed") is False),
    }


def public_session_status(state_payload: dict[str, Any], *, live_trial_mode: bool = False) -> dict[str, Any]:
    latest = state_payload.get("latestArtifacts") if isinstance(state_payload.get("latestArtifacts"), dict) else {}
    blockers: list[str] = []
    warnings: list[str] = []
    states: dict[str, str] = {}
    for kind in ("cloudflare-smoke", "trial-session"):
        item = latest.get(kind)
        if not isinstance(item, dict):
            states[kind] = "not-started"
            continue
        if item.get("publicUrlExpectedExpired"):
            states[kind] = "expected-expired"
            continue
        if item.get("publicTunnelStopped") or item.get("serverStopped"):
            states[kind] = "stopped"
            continue
        if item.get("publicMcpUrl") and item.get("status") == "ready":
            states[kind] = "ready-active"
            if not live_trial_mode:
                blockers.append(f"public-session:unexpected-active:{kind}")
            continue
        if item.get("publicMcpUrl"):
            states[kind] = "unknown"
            blockers.append(f"public-session:unknown:{kind}")
        else:
            states[kind] = "not-started"
    return {
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "states": states,
        "liveTrialMode": live_trial_mode,
    }


def git_upstream_sync(repo_root: Path) -> dict[str, Any]:
    upstream = run_command_envelope(
        "git-upstream",
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo_root,
        timeout_seconds=15,
        capture_full_output=True,
    )
    blockers: list[str] = []
    if not upstream.get("ok"):
        return {
            "status": "blocked",
            "ok": False,
            "blockers": ["git:upstream-missing"],
            "warnings": [],
            "upstream": None,
            "ahead": None,
            "behind": None,
            "commands": {"upstream": {k: v for k, v in upstream.items() if k not in {"stdout", "stderr"}}},
        }
    upstream_name = str(upstream.get("stdout") or "").strip().splitlines()[0]
    counts = run_command_envelope(
        "git-ahead-behind",
        ["git", "rev-list", "--left-right", "--count", "@{u}...HEAD"],
        repo_root,
        timeout_seconds=15,
        capture_full_output=True,
    )
    ahead = behind = None
    if not counts.get("ok"):
        blockers.append("git:upstream-count-unavailable")
    else:
        parts = str(counts.get("stdout") or "").strip().split()
        if len(parts) >= 2:
            behind, ahead = int(parts[0]), int(parts[1])
            if ahead or behind:
                blockers.append(f"git:upstream-not-synced:behind={behind}:ahead={ahead}")
        else:
            blockers.append("git:upstream-count-unparseable")
    return {
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "blockers": blockers,
        "warnings": [],
        "upstream": upstream_name,
        "ahead": ahead,
        "behind": behind,
        "commands": {
            "upstream": {k: v for k, v in upstream.items() if k not in {"stdout", "stderr"}},
            "aheadBehind": {k: v for k, v in counts.items() if k not in {"stdout", "stderr"}},
        },
    }


def _find_executable(name: str, extra_candidates: list[Path] | None = None) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in extra_candidates or []:
        if candidate.is_file():
            return str(candidate)
    return None


def dependency_preflight(repo_root: Path, *, live_trial_mode: bool = False) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    dependencies: dict[str, dict[str, Any]] = {}

    dependencies["python"] = {"status": "passed", "ok": True, "path": sys.executable, "required": True}

    sdk_root = repo_root / ".riftreader-local" / "mcp-sdk-validation"
    added_sdk_root = False
    if sdk_root.is_dir() and str(sdk_root) not in sys.path:
        sys.path.insert(0, str(sdk_root))
        added_sdk_root = True
    try:
        sdk_ok = importlib.util.find_spec("mcp") is not None
    except Exception:  # noqa: BLE001
        sdk_ok = False
    dependencies["mcp-sdk"] = {
        "status": "passed" if sdk_ok else "blocked",
        "ok": sdk_ok,
        "required": True,
        "pathAddition": str(sdk_root) if sdk_root.is_dir() else None,
        "pathAdded": added_sdk_root,
    }
    if not sdk_ok:
        blockers.append("dependency:missing:mcp-sdk")

    gh = _find_executable("gh")
    dependencies["gh"] = {"status": "passed" if gh else "blocked", "ok": bool(gh), "path": gh, "required": True}
    if not gh:
        blockers.append("dependency:missing:gh")

    cloudflared = _find_executable(
        "cloudflared",
        [Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe"), Path(r"C:\Program Files\cloudflared\cloudflared.exe")],
    )
    dependencies["cloudflared"] = {
        "status": "passed" if cloudflared else ("blocked" if live_trial_mode else "not-required"),
        "ok": bool(cloudflared) or not live_trial_mode,
        "path": cloudflared,
        "required": live_trial_mode,
    }
    if live_trial_mode and not cloudflared:
        blockers.append("dependency:missing:cloudflared")

    curl = _find_executable("curl")
    dependencies["curl"] = {
        "status": "passed" if curl else ("blocked" if live_trial_mode else "not-required"),
        "ok": bool(curl) or not live_trial_mode,
        "path": curl,
        "required": live_trial_mode,
    }
    if live_trial_mode and not curl:
        blockers.append("dependency:missing:curl")

    return {
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "dependencies": dependencies,
        "liveTrialMode": live_trial_mode,
    }


def _bind_check(host: str, port: int) -> dict[str, Any]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
            assigned_port = int(sock.getsockname()[1])
        return {"status": "available", "ok": True, "host": host, "port": port, "assignedPort": assigned_port}
    except OSError as exc:
        return {
            "status": "busy-or-unavailable",
            "ok": False,
            "host": host,
            "port": port,
            "error": f"{type(exc).__name__}:{exc}",
        }


def _git_ignored(repo_root: Path, repo_relative_path: str) -> dict[str, Any]:
    envelope = run_command_envelope(
        f"git-check-ignore:{repo_relative_path}",
        ["git", "check-ignore", "-q", "--", repo_relative_path],
        repo_root,
        timeout_seconds=15,
        expected_exit_codes={0, 1},
        capture_full_output=True,
    )
    exit_code = envelope.get("exitCode")
    return {
        "path": repo_relative_path,
        "ignored": exit_code == 0,
        "status": "ignored" if exit_code == 0 else "not-ignored" if exit_code == 1 else "unknown",
        "command": {key: value for key, value in envelope.items() if key not in {"stdout", "stderr"}},
    }


def environment_preflight(repo_root: Path, *, live_trial_mode: bool = False) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    repo_markers = {
        "agents": (repo_root / "agents.md").is_file() or (repo_root / "AGENTS.md").is_file(),
        "git": (repo_root / ".git").exists(),
        "workflowPackage": (repo_root / "tools" / "riftreader_workflow").is_dir(),
    }
    if not all(repo_markers.values()):
        blockers.append("repo:not-riftreader-root")

    ephemeral_port = _bind_check(DEFAULT_LOOPBACK_HOST, 0)
    if not ephemeral_port.get("ok"):
        blockers.append("environment:loopback-ephemeral-port-unavailable")

    default_port = _bind_check(DEFAULT_LOOPBACK_HOST, DEFAULT_MCP_SERVE_PORT)
    if not default_port.get("ok"):
        warnings.append(f"environment:default-serve-port-busy:{DEFAULT_MCP_SERVE_PORT}")

    ignored_root = _git_ignored(repo_root, LOCAL_IGNORED_ARTIFACT_ROOT)
    if ignored_root.get("ignored") is not True:
        blockers.append(f"environment:artifact-root-not-ignored:{LOCAL_IGNORED_ARTIFACT_ROOT}")

    local_roots = {
        "mcpLocalRoot": str(Path(LOCAL_IGNORED_ARTIFACT_ROOT) / "riftreader-chatgpt-mcp"),
        "artifactBridgeInbox": str(Path(LOCAL_IGNORED_ARTIFACT_ROOT) / "artifact-bridge-inbox"),
        "artifactBridgeDrafts": str(Path(LOCAL_IGNORED_ARTIFACT_ROOT) / "artifact-bridge-package-drafts"),
        "packageIntake": str(Path(LOCAL_IGNORED_ARTIFACT_ROOT) / "package-intake"),
    }
    root_prefix = LOCAL_IGNORED_ARTIFACT_ROOT.replace("/", "\\") + "\\"
    for name, value in local_roots.items():
        if not value.replace("/", "\\").startswith(root_prefix):
            blockers.append(f"environment:local-artifact-root-outside-ignored-root:{name}")

    return {
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "liveTrialMode": live_trial_mode,
        "repoRoot": str(repo_root),
        "repoMarkers": repo_markers,
        "loopback": {
            "ephemeralPort": ephemeral_port,
            "defaultServePort": default_port,
        },
        "artifactRoots": {
            "ignoredRoot": ignored_root,
            "localRoots": local_roots,
            "trackedPayloadRoot": "artifacts\\chatgpt-payloads",
        },
    }


def _map_ci_blocker(blocker: str) -> str:
    if blocker.startswith("ci-workflow-missing-current-head:"):
        return "ci:missing:" + blocker.split(":", 1)[1]
    if blocker.startswith("ci-workflow-not-completed:"):
        return "ci:not-completed:" + blocker.split(":", 1)[1]
    if blocker.startswith("ci-workflow-not-success:"):
        return "ci:failed:" + blocker.split(":", 1)[1]
    return "ci:" + blocker


def _unsafe_safety_blockers(safety: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key in FALSE_SAFETY_KEYS:
        if safety.get(key) is True:
            blockers.append(f"safety:unsafe-action:{key}")
    for key in ("publicTunnelStarted", "persistentServerStarted", "chatGptRegistrationPerformed"):
        if safety.get(key) is True:
            blockers.append(f"safety:unsafe-action:{key}")
    if safety.get("noCheatEngine") is False:
        blockers.append("safety:unsafe-action:noCheatEngine")
    return blockers


def _next_action(blockers: list[str]) -> dict[str, Any]:
    commands = standard_commands()
    for blocker in blockers:
        if blocker.startswith("git:dirty-worktree"):
            return {"key": "safe-commit-plan", "reason": "Final readiness requires a clean worktree.", "command": commands["safeCommitPlan"]}
        if blocker.startswith("ci:"):
            return {
                "key": "inspect-current-head-ci",
                "reason": "Current HEAD CI is unavailable, pending, or failing.",
                "command": ["gh", "run", "list", "--limit", "10", "--json", "databaseId,workflowName,headSha,status,conclusion,createdAt,updatedAt,event,url"],
            }
        if blocker.startswith("artifact:trial-readiness"):
            return {"key": "refresh-trial-readiness", "reason": "Final readiness requires fresh local trial readiness.", "command": commands["mcpTrialReadiness"]}
        if blocker.startswith("artifact:proposal-smoke"):
            return {"key": "refresh-proposal-smoke", "reason": "Final readiness requires a fresh guarded proposal transport smoke.", "command": commands["proposalTransportSmoke"]}
        if blocker.startswith("proof:"):
            return {"key": "record-actual-client-proof", "reason": "Actual-client proof is missing, stale, or failed replay.", "command": commands["trialProofTemplate"]}
        if blocker.startswith("phase2:"):
            return {"key": "mcp-phase2-status", "reason": "Final readiness builds on a passing Phase 2 gate.", "command": commands["mcpPhase2Status"]}
        if blocker.startswith("dependency:"):
            return {"key": "fix-final-readiness-dependency", "reason": blocker, "command": commands["mcpMissionControl"]}
        if blocker.startswith("environment:") or blocker.startswith("repo:"):
            return {"key": "fix-final-readiness-environment", "reason": blocker, "command": commands["mcpMissionControl"]}
        if blocker.startswith("safety:"):
            return {"key": "inspect-mcp-safety", "reason": blocker, "command": commands["mcpTrialReadiness"]}
        if blocker.startswith("public-session:"):
            return {"key": "inspect-public-session-state", "reason": blocker, "command": commands["mcpMissionControl"]}
    return {"key": "ready-for-release-handoff", "reason": "Final readiness checks passed; write or update the final release handoff.", "command": commands["mcpMissionControl"]}


def final_readiness(
    repo_root: Path,
    *,
    live_trial_mode: bool = False,
    phase2_payload: dict[str, Any] | None = None,
    state_payload: dict[str, Any] | None = None,
    git_sync_payload: dict[str, Any] | None = None,
    dependency_payload: dict[str, Any] | None = None,
    environment_payload: dict[str, Any] | None = None,
    tool_surface_payload: dict[str, Any] | None = None,
    public_session_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state_payload = state_payload if state_payload is not None else build_mcp_workflow_state(repo_root)
    phase2_payload = phase2_payload if phase2_payload is not None else phase2_status(repo_root)
    git_sync_payload = git_sync_payload if git_sync_payload is not None else git_upstream_sync(repo_root)
    dependency_payload = dependency_payload if dependency_payload is not None else dependency_preflight(repo_root, live_trial_mode=live_trial_mode)
    environment_payload = environment_payload if environment_payload is not None else environment_preflight(repo_root, live_trial_mode=live_trial_mode)
    tool_surface_payload = tool_surface_payload if tool_surface_payload is not None else tool_surface_status(repo_root, state_payload)
    public_session_payload = public_session_payload if public_session_payload is not None else public_session_status(state_payload, live_trial_mode=live_trial_mode)

    blockers: list[str] = []
    warnings: list[str] = []
    git_state = state_payload.get("gitDirtyState") if isinstance(state_payload.get("gitDirtyState"), dict) else {}
    if git_state.get("dirty"):
        blockers.append("git:dirty-worktree")
    blockers.extend(str(blocker) for blocker in git_sync_payload.get("blockers") or [])

    if not phase2_payload.get("ok"):
        blockers.append("phase2:not-ready")
    ci_status = phase2_payload.get("ciStatus") if isinstance(phase2_payload.get("ciStatus"), dict) else {}
    if not ci_status.get("ok"):
        blockers.extend(_map_ci_blocker(str(blocker)) for blocker in ci_status.get("blockers") or ["missing"])

    proof = phase2_payload.get("proofReplay") if isinstance(phase2_payload.get("proofReplay"), dict) else {}
    if not proof.get("ok"):
        blockers.extend("proof:replay-failed:" + str(blocker) for blocker in proof.get("blockers") or ["unknown"])
    proof_freshness = proof.get("proofFreshness") if isinstance(proof.get("proofFreshness"), dict) else {}
    if proof_freshness.get("status") == "stale":
        blockers.append("proof:stale")
    elif proof_freshness and proof_freshness.get("status") not in {"fresh", None}:
        blockers.append("proof:freshness-unknown")

    artifact_freshness = phase2_payload.get("artifactFreshness") if isinstance(phase2_payload.get("artifactFreshness"), dict) else {}
    items = artifact_freshness.get("items") if isinstance(artifact_freshness.get("items"), dict) else {}
    readiness = items.get("readiness") if isinstance(items.get("readiness"), dict) else {}
    proposal = items.get("proposal-smoke") if isinstance(items.get("proposal-smoke"), dict) else {}
    if readiness.get("status") != "fresh":
        blockers.append("artifact:trial-readiness-stale")
    if proposal.get("status") != "fresh":
        blockers.append("artifact:proposal-smoke-stale")

    blockers.extend(str(blocker) for blocker in dependency_payload.get("blockers") or [])
    blockers.extend(str(blocker) for blocker in environment_payload.get("blockers") or [])
    blockers.extend(str(blocker) for blocker in tool_surface_payload.get("blockers") or [])
    blockers.extend(str(blocker) for blocker in public_session_payload.get("blockers") or [])
    phase2_safety = phase2_payload.get("safety") if isinstance(phase2_payload.get("safety"), dict) else {}
    blockers.extend(_unsafe_safety_blockers(phase2_safety))

    warnings = unique(
        [
            *(state_payload.get("warnings") if isinstance(state_payload.get("warnings"), list) else []),
            *(phase2_payload.get("warnings") if isinstance(phase2_payload.get("warnings"), list) else []),
            *(git_sync_payload.get("warnings") if isinstance(git_sync_payload.get("warnings"), list) else []),
            *(dependency_payload.get("warnings") if isinstance(dependency_payload.get("warnings"), list) else []),
            *(environment_payload.get("warnings") if isinstance(environment_payload.get("warnings"), list) else []),
            *(tool_surface_payload.get("warnings") if isinstance(tool_surface_payload.get("warnings"), list) else []),
            *(public_session_payload.get("warnings") if isinstance(public_session_payload.get("warnings"), list) else []),
        ]
    )
    blockers = unique(blockers)
    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-final-readiness",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "blockers": blockers,
        "warnings": warnings,
        "currentHead": ci_status.get("currentHead"),
        "git": {"dirtyState": git_state, "upstreamSync": git_sync_payload},
        "ci": ci_status,
        "phase2": phase2_payload,
        "artifacts": {
            "freshness": artifact_freshness,
            "latest": state_payload.get("latestArtifacts"),
            "toolSurface": tool_surface_payload,
        },
        "dependencies": dependency_payload,
        "environment": environment_payload,
        "publicSession": public_session_payload,
        "recommendedNextAction": _next_action(blockers),
        "safety": {
            **safety_flags(),
            "finalGateReadOnly": True,
            "publicTunnelStarted": False,
            "persistentServerStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
            "applyFlagSent": False,
        },
    }


def compact_final_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    phase2_payload = payload.get("phase2") if isinstance(payload.get("phase2"), dict) else {}
    phase2_compact = compact_phase2_status(phase2_payload) if phase2_payload else {}
    deps = payload.get("dependencies") if isinstance(payload.get("dependencies"), dict) else {}
    environment = payload.get("environment") if isinstance(payload.get("environment"), dict) else {}
    dep_map = deps.get("dependencies") if isinstance(deps.get("dependencies"), dict) else {}
    tool_surface = ((payload.get("artifacts") or {}).get("toolSurface") if isinstance(payload.get("artifacts"), dict) else {}) or {}
    public_session = payload.get("publicSession") if isinstance(payload.get("publicSession"), dict) else {}
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-final-compact-status",
        "generatedAtUtc": payload.get("generatedAtUtc"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "currentHead": payload.get("currentHead"),
        "gitDirty": ((payload.get("git") or {}).get("dirtyState") or {}).get("dirty") if isinstance(payload.get("git"), dict) else None,
        "upstreamStatus": ((payload.get("git") or {}).get("upstreamSync") or {}).get("status") if isinstance(payload.get("git"), dict) else None,
        "ciStatus": (payload.get("ci") or {}).get("status") if isinstance(payload.get("ci"), dict) else None,
        "phase2Status": phase2_compact.get("status"),
        "phase2Ready": phase2_compact.get("phase2Ready"),
        "proofReplayStatus": phase2_compact.get("proofReplayStatus"),
        "proofFreshnessStatus": phase2_compact.get("proofFreshnessStatus"),
        "artifactFreshnessStatus": phase2_compact.get("artifactFreshnessStatus"),
        "toolSurfaceStatus": tool_surface.get("status"),
        "dependencyStatus": deps.get("status"),
        "environmentStatus": environment.get("status"),
        "loopbackEphemeralPortStatus": ((environment.get("loopback") or {}).get("ephemeralPort") or {}).get("status")
        if isinstance(environment.get("loopback"), dict)
        else None,
        "defaultServePortStatus": ((environment.get("loopback") or {}).get("defaultServePort") or {}).get("status")
        if isinstance(environment.get("loopback"), dict)
        else None,
        "requiredDependencies": {name: item.get("status") for name, item in dep_map.items() if isinstance(item, dict) and item.get("required")},
        "publicSessionStatus": public_session.get("status"),
        "publicSessionStates": public_session.get("states"),
        "recommendedNextAction": payload.get("recommendedNextAction"),
        "blockers": payload.get("blockers") or [],
        "warningCount": len(payload.get("warnings") or []),
        "warnings": payload.get("warnings") or [],
        "safety": payload.get("safety"),
    }


def self_test() -> dict[str, Any]:
    phase2 = {
        "status": "passed",
        "ok": True,
        "ciStatus": {"status": "passed", "ok": True, "currentHead": "self-test", "blockers": []},
        "proofReplay": {"status": "passed", "ok": True, "blockers": [], "proofFreshness": {"status": "fresh"}},
        "artifactFreshness": {"items": {"readiness": {"status": "fresh"}, "proposal-smoke": {"status": "fresh"}}},
        "warnings": [],
        "safety": safety_flags(),
    }
    state = {"warnings": [], "latestArtifacts": {}, "gitDirtyState": {"dirty": False, "dirtyCount": 0, "entries": []}}
    ok_payload = final_readiness(
        Path.cwd(),
        phase2_payload=phase2,
        state_payload=state,
        git_sync_payload={"status": "passed", "ok": True, "blockers": [], "warnings": []},
        dependency_payload={"status": "passed", "ok": True, "blockers": [], "warnings": [], "dependencies": {}},
        environment_payload={"status": "passed", "ok": True, "blockers": [], "warnings": []},
        tool_surface_payload={"status": "passed", "ok": True, "blockers": [], "warnings": []},
        public_session_payload={"status": "passed", "ok": True, "blockers": [], "warnings": [], "states": {}},
    )
    dirty_state = {"warnings": [], "latestArtifacts": {}, "gitDirtyState": {"dirty": True, "dirtyCount": 1, "entries": [{"path": "x"}]}}
    dirty_payload = final_readiness(
        Path.cwd(),
        phase2_payload=phase2,
        state_payload=dirty_state,
        git_sync_payload={"status": "passed", "ok": True, "blockers": [], "warnings": []},
        dependency_payload={"status": "passed", "ok": True, "blockers": [], "warnings": [], "dependencies": {}},
        environment_payload={"status": "passed", "ok": True, "blockers": [], "warnings": []},
        tool_surface_payload={"status": "passed", "ok": True, "blockers": [], "warnings": []},
        public_session_payload={"status": "passed", "ok": True, "blockers": [], "warnings": [], "states": {}},
    )
    checks = [
        {"name": "all-pass-fixture-passes", "pass": ok_payload.get("status") == "passed"},
        {"name": "dirty-fixture-blocks", "pass": "git:dirty-worktree" in (dirty_payload.get("blockers") or [])},
    ]
    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-final-readiness-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {**safety_flags(), "publicTunnelStarted": False, "gitMutation": False},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check final-product readiness for the RiftReader ChatGPT MCP lane.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true", help="Print final MCP readiness status.")
    mode.add_argument("--self-test", action="store_true", help="Run deterministic final-readiness self-test.")
    parser.add_argument("--live-trial-mode", action="store_true", help="Require public-trial dependencies and allow an explicit active bounded session.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--compact-json", action="store_true", help="Emit a bounded operator-facing JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
        payload = self_test() if args.self_test else final_readiness(repo_root, live_trial_mode=args.live_trial_mode)
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with structured error.
        payload = {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-final-readiness",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "ok": False,
            "blockers": [f"final-readiness-exception:{type(exc).__name__}:{exc}"],
            "warnings": [],
            "safety": safety_flags(),
        }
    output_payload = compact_final_readiness(payload) if args.compact_json else payload
    if args.json or args.compact_json:
        print(json.dumps(output_payload, indent=2, sort_keys=True))
    else:
        action = output_payload.get("recommendedNextAction") if isinstance(output_payload.get("recommendedNextAction"), dict) else {}
        print(f"Status: {payload.get('status')} ok={payload.get('ok')}")
        print(f"Next: {action.get('key')} - {' '.join(action.get('command') or [])}")
        for blocker in payload.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    if payload.get("status") == "failed":
        return 1
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
