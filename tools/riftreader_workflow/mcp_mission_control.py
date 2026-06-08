#!/usr/bin/env python3
"""MCP Mission Control dashboard for RiftReader."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .chatgpt_trial_recorder import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
    from .common import find_repo_root, run_command_envelope, safety_flags, unique, utc_iso
    from .mcp_ci_status import current_head_ci_status
    from .mcp_final_readiness import compact_final_readiness, final_readiness
    from .mcp_workflow_state import build_mcp_workflow_state, standard_commands
    from .workflow_router import ranked_actions
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.chatgpt_trial_recorder import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
    from riftreader_workflow.common import find_repo_root, run_command_envelope, safety_flags, unique, utc_iso
    from riftreader_workflow.mcp_ci_status import current_head_ci_status
    from riftreader_workflow.mcp_final_readiness import compact_final_readiness, final_readiness
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, standard_commands
    from riftreader_workflow.workflow_router import ranked_actions


FINAL_PRODUCT_PHASES = (
    (1, "Preserve current MCP baseline"),
    (2, "Final readiness contract"),
    (3, "Final readiness gate"),
    (4, "Dependency and environment preflight"),
    (5, "Operator workflow hardening"),
    (6, "Safety/security hardening"),
    (7, "Fresh real ChatGPT trial"),
    (8, "Release handoff and maintenance loop"),
)


def latest_release_handoff_path(repo_root: Path) -> str | None:
    """Return the newest repo-relative MCP final release handoff path, if present."""

    handoff_root = repo_root / "docs" / "handoffs"
    if not handoff_root.is_dir():
        return None
    matches = [path for path in handoff_root.glob("*mcp-final-readiness-release-handoff*.md") if path.is_file()]
    if not matches:
        return None
    newest = max(matches, key=lambda path: (path.stat().st_mtime_ns, path.name))
    return str(newest.relative_to(repo_root))


def _matches_expected_tool_names(value: Any) -> bool:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return False
    return sorted(value) == sorted(EXPECTED_CHATGPT_MCP_TOOL_NAMES)


def _actual_client_proof_completed(latest_artifacts: dict[str, Any]) -> bool:
    actual_client = latest_artifacts.get("actual-client-proof") if isinstance(latest_artifacts, dict) else None
    if not isinstance(actual_client, dict):
        return False
    apply_without_approval_blockers = actual_client.get("applyLatestPackageDraftWithoutApprovalBlockers")
    return (
        actual_client.get("ok") is True
        and actual_client.get("status") == "passed"
        and actual_client.get("selfTest") is not True
        and actual_client.get("chatGptRegistrationSucceeded") is True
        and actual_client.get("templateFetched") is True
        and actual_client.get("toolCount") == EXPECTED_CHATGPT_MCP_TOOL_COUNT
        and _matches_expected_tool_names(actual_client.get("toolNames"))
        and actual_client.get("toolOutputSchemasPresent") is True
        and actual_client.get("toolOutputSchemaCount") == EXPECTED_CHATGPT_MCP_TOOL_COUNT
        and _matches_expected_tool_names(actual_client.get("toolOutputSchemaToolNames"))
        and actual_client.get("submitPackageProposalSucceeded") is True
        and actual_client.get("listInboxSawInboxId") is True
        and actual_client.get("createPackageDraftSucceeded") is True
        and actual_client.get("reviewLatestPackageDraftSucceeded") is True
        and actual_client.get("reviewLatestPackageDraftReadOnly") is True
        and actual_client.get("dryRunSucceeded") is True
        and actual_client.get("dryRunDiffPreviewOk") is True
        and actual_client.get("dryRunDiffPreviewArtifactUnderPackageIntake") is True
        and actual_client.get("dryRunDiffPreviewBoundedBytes") is True
        and isinstance(actual_client.get("dryRunDiffPreviewTextLength"), int)
        and actual_client.get("dryRunDiffPreviewTextLength") > 0
        and isinstance(actual_client.get("dryRunDiffPreviewTruncated"), bool)
        and actual_client.get("applyLatestPackageDraftWithoutApprovalBlocked") is True
        and isinstance(apply_without_approval_blockers, list)
        and "APPLY_APPROVAL_MISSING" in apply_without_approval_blockers
        and actual_client.get("applyLatestPackageDraftWithoutApprovalApplied") is False
    )


def build_final_product_progress(
    repo_root: Path,
    final_status: dict[str, Any],
    commands: dict[str, list[str]],
    latest_artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize the final-product phase ladder for one operator dashboard."""

    contract_path = repo_root / "docs" / "workflow" / "riftreader-chatgpt-mcp-final-readiness.md"
    final_ok = final_status.get("ok") is True
    phase2_ready = final_status.get("phase2Ready") is True
    ci_passed = final_status.get("ciStatus") == "passed"
    upstream_passed = final_status.get("upstreamStatus") == "passed"
    dependency_passed = final_status.get("dependencyStatus") == "passed"
    environment_passed = final_status.get("environmentStatus") == "passed"
    tool_surface_passed = final_status.get("toolSurfaceStatus") == "passed"
    public_session_passed = final_status.get("publicSessionStatus") == "passed"
    proof_replay_passed = final_status.get("proofReplayStatus") == "passed"
    proof_fresh = final_status.get("proofFreshnessStatus") == "fresh"
    latest_artifacts = latest_artifacts if isinstance(latest_artifacts, dict) else {}
    actual_client_proof_completed = _actual_client_proof_completed(latest_artifacts)
    release_handoff_path = latest_release_handoff_path(repo_root)
    phase7_completed = final_ok and public_session_passed and proof_replay_passed and proof_fresh and actual_client_proof_completed
    phase8_completed = phase7_completed and bool(release_handoff_path)
    phase_rows = [
        phase_row(
            1,
            "Preserve current MCP baseline",
            "completed" if phase2_ready and ci_passed and upstream_passed else "blocked",
            "Clean upstream-synced HEAD with current-head CI and replayable proof baseline.",
        ),
        phase_row(
            2,
            "Final readiness contract",
            "completed" if contract_path.is_file() else "blocked",
            "Final readiness contract document exists.",
        ),
        phase_row(
            3,
            "Final readiness gate",
            "completed" if "mcpFinalStatus" in commands and "mcpFinalCompactStatus" in commands else "blocked",
            "Final JSON and compact JSON gate commands are registered.",
        ),
        phase_row(
            4,
            "Dependency and environment preflight",
            "completed" if dependency_passed and environment_passed else "blocked",
            "Dependency and environment preflight fields are present and passing.",
        ),
        phase_row(
            5,
            "Operator workflow hardening",
            "completed",
            "Mission Control surfaces final status, progress, display-only trial command, summary, and checklist.",
        ),
        phase_row(
            6,
            "Safety/security hardening",
            "completed" if final_ok and tool_surface_passed else "blocked",
            "Offline unsafe-surface fixtures and final-gate safety invariants are present and passing.",
        ),
        phase_row(
            7,
            "Fresh real ChatGPT Cloudflare named Tunnel proof",
            "completed" if phase7_completed else ("ready" if final_ok and public_session_passed else "pending"),
            (
                "Fresh repo-owned actual-client proof is recorded through the operator-managed Cloudflare named Tunnel Server URL, replayed, and not self-test."
                if phase7_completed
                else "Cloudflare named Tunnel proof remains explicit-only; Mission Control prints commands but starts no server, cloudflared connector, or reverse proxy."
            ),
        ),
        phase_row(
            8,
            "Release handoff and maintenance loop",
            "completed" if phase8_completed else "pending",
            (
                f"Release handoff exists: {release_handoff_path}."
                if phase8_completed
                else "Write final release handoff after a fresh actual-client proof and final gate pass."
            ),
        ),
    ]
    completed_count = sum(1 for row in phase_rows if row["status"] == "completed")
    next_phase = next((row for row in phase_rows if row["status"] not in {"completed"}), None)
    if next_phase and next_phase["phase"] == 6 and final_ok:
        recommended = {
            "key": "phase6-safety-security-hardening",
            "reason": "Operator workflow is hardened; next safe local slice is an offline safety/security fixture pass.",
            "command": commands["mcpFinalStatus"],
        }
    elif next_phase and next_phase["phase"] == 7 and final_ok:
        recommended = {
            "key": "prepare-cloudflare-named-tunnel-chatgpt-proof",
            "reason": "Local final gate passes; the next external proof should use the operator-managed Cloudflare named Tunnel Server URL path.",
            "command": commands["manualPublicIpPlan"],
        }
    elif next_phase is None:
        recommended = {
            "key": "maintenance-loop",
            "reason": "All MCP final-product phases are complete; keep proof fresh and rerun the final gate before releases.",
            "command": commands["mcpFinalCompactStatus"],
        }
    else:
        recommended = (final_status.get("recommendedNextAction") if isinstance(final_status.get("recommendedNextAction"), dict) else {}) or {
            "key": "inspect-final-readiness",
            "reason": "Final readiness has blockers or missing fields.",
            "command": commands["mcpFinalStatus"],
        }
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-final-product-progress",
        "status": "completed" if next_phase is None else ("ready-for-next-phase" if final_ok else "blocked"),
        "completedPhaseCount": completed_count,
        "totalPhaseCount": len(phase_rows),
        "currentCompletedThroughPhase": completed_count if all(row["status"] == "completed" for row in phase_rows[:completed_count]) else None,
        "nextPhase": next_phase,
        "phases": phase_rows,
        "recommendedNextAction": recommended,
        "releaseHandoffPath": release_handoff_path,
        "actualClientProofCompleted": actual_client_proof_completed,
        "externalTrialExplicitOnly": True,
        "recommendedConnection": "cloudflare-named-tunnel",
        "openAiSecureTunnelRetired": True,
        "cloudflareTunnelRetired": False,
        "cloudflareNamedTunnelActive": True,
        "cloudflareQuickTunnelRetired": True,
        "publicTunnelStarted": False,
        "chatGptRegistrationPerformed": False,
    }


def phase_row(phase: int, name: str, status: str, evidence: str) -> dict[str, Any]:
    return {"phase": phase, "name": name, "status": status, "evidence": evidence}


def dashboard_ranked_actions(state: dict[str, Any], final_status: dict[str, Any], commands: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Return operator actions using final-gate truth before raw artifact presence."""

    final_action = final_status.get("recommendedNextAction") if isinstance(final_status.get("recommendedNextAction"), dict) else {}
    if final_status.get("ok") is not True and final_action:
        actions = [
            {
                "key": final_action.get("key"),
                "priority": "P1",
                "reason": final_action.get("reason") or "Final readiness selected this blocker-specific next action.",
                "command": final_action.get("command") or commands["mcpFinalCompactStatus"],
            },
            {
                "key": "mcp-final-status",
                "priority": "P1",
                "reason": "Inspect the full final readiness gate for blocker context.",
                "command": commands["mcpFinalStatus"],
            },
            {
                "key": "latest-artifacts",
                "priority": "P2",
                "reason": "Open latest artifact browser when evidence paths are unclear.",
                "command": commands["mcpArtifactsLatest"],
            },
            {
                "key": "mission-control",
                "priority": "P2",
                "reason": "Open consolidated MCP dashboard.",
                "command": ["scripts\\riftreader-mcp-mission-control.cmd", "--json"],
            },
        ]
        seen: set[str] = set()
        unique_actions = []
        for action in actions:
            key = str(action.get("key") or "")
            if key and key not in seen:
                seen.add(key)
                unique_actions.append(action)
        return unique_actions
    return ranked_actions(state)


def mission_control(repo_root: Path) -> dict[str, Any]:
    state = build_mcp_workflow_state(repo_root)
    ci_status = current_head_ci_status(repo_root)
    final_status = final_readiness(repo_root, state_payload=state)
    compact_final_status = compact_final_readiness(final_status)
    commands = standard_commands()
    progress = build_final_product_progress(repo_root, compact_final_status, commands, state.get("latestArtifacts"))
    warnings = unique([
        *(state.get("warnings") if isinstance(state.get("warnings"), list) else []),
        *(ci_status.get("warnings") if isinstance(ci_status.get("warnings"), list) else []),
        *(final_status.get("warnings") if isinstance(final_status.get("warnings"), list) else []),
    ])
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-mission-control",
        "generatedAtUtc": utc_iso(),
        "status": compact_final_status.get("status") or state.get("status"),
        "ok": compact_final_status.get("ok") if "ok" in compact_final_status else state.get("ok"),
        "blockers": compact_final_status.get("blockers") or state.get("blockers"),
        "warnings": warnings,
        "ciStatus": ci_status,
        "finalStatus": compact_final_status,
        "finalProductProgress": progress,
        "latestArtifacts": state.get("latestArtifacts"),
        "counts": state.get("counts"),
        "gitDirtyState": state.get("gitDirtyState"),
        "recommendedNextAction": compact_final_status.get("recommendedNextAction") or state.get("recommendedNextAction"),
        "operatorNextAction": progress.get("recommendedNextAction"),
        "rankedActions": dashboard_ranked_actions(state, compact_final_status, commands),
        "pasteSafeCommands": {
            "readiness": commands["mcpTrialReadiness"],
            "proposalSmoke": commands["proposalTransportSmoke"],
            "manualPublicIpPlan": commands["manualPublicIpPlan"],
            "trialProofTemplate": commands["trialProofTemplate"],
            "phase2Status": commands["mcpPhase2Status"],
            "phase2CompactStatus": commands["mcpPhase2CompactStatus"],
            "finalStatus": commands["mcpFinalStatus"],
            "finalCompactStatus": commands["mcpFinalCompactStatus"],
            "inboxReview": commands["inboxLatest"],
            "draftExport": commands["inboxPackageDraft"],
            "draftDryRun": commands["dryRunLatestDraft"],
            "artifactBrowser": commands["mcpArtifactsLatest"],
            "safeCommitPlan": commands["safeCommitPlan"],
        },
        "safety": {
            **safety_flags(),
            "missionControlDefaultReadOnly": True,
            "publicTunnelStarted": False,
            "persistentServerStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
            "applyFlagSent": False,
        },
    }


def trial_command_payload(repo_root: Path) -> dict[str, Any]:
    commands = standard_commands()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-mission-control-trial-command",
        "generatedAtUtc": utc_iso(),
        "status": "blocked",
        "ok": False,
        "command": commands["chatGptTrialSessionRetired"],
        "notes": [
            "Cloudflare ChatGPT trial sessions are retired for this repo lane and are not a fallback path.",
            "Use the Cloudflare named Tunnel plan command instead.",
        ],
        "safety": {
            **safety_flags(),
            "publicTunnelStarted": False,
            "commandDisplayedOnly": True,
            "cloudflareTunnelRetired": True,
        },
    }


def secure_tunnel_plan_payload(repo_root: Path) -> dict[str, Any]:
    commands = standard_commands()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-mission-control-secure-tunnel-plan-command",
        "generatedAtUtc": utc_iso(),
        "status": "blocked",
        "ok": False,
        "command": commands["secureTunnelPlanRetired"],
        "notes": [
            "OpenAI Secure MCP Tunnel is retired for this repo lane and is not a fallback path.",
            "Use the Cloudflare named Tunnel plan command instead.",
        ],
        "safety": {
            **safety_flags(),
            "publicTunnelStarted": False,
            "commandDisplayedOnly": True,
            "openAiSecureTunnelRetired": True,
            "cloudflareTunnelRetired": True,
        },
    }


def manual_public_ip_plan_payload(repo_root: Path) -> dict[str, Any]:
    commands = standard_commands()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-mission-control-manual-public-ip-plan-command",
        "generatedAtUtc": utc_iso(),
        "status": "ready",
        "ok": True,
        "command": commands["manualPublicIpPlan"],
        "notes": [
            "This prints the active Cloudflare named Tunnel Server URL plan without starting the MCP server, cloudflared connector, reverse proxy, or router configuration.",
            "Run the printed plan outside Codex with --public-mcp-host mcp.360madden.com for the canonical route.",
        ],
        "safety": {
            **safety_flags(),
            "publicTunnelStarted": False,
            "commandDisplayedOnly": True,
            "manualPublicIpPreferred": True,
            "openAiSecureTunnelRetired": True,
            "cloudflareTunnelRetired": True,
        },
    }


def render_summary_markdown(payload: dict[str, Any]) -> str:
    action = payload.get("operatorNextAction") if isinstance(payload.get("operatorNextAction"), dict) else {}
    if not action:
        action = payload.get("recommendedNextAction") if isinstance(payload.get("recommendedNextAction"), dict) else {}
    lines = [
        "# RiftReader MCP Mission Control Summary",
        "",
        f"- Generated UTC: `{payload.get('generatedAtUtc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Operator next action: `{action.get('key')}`",
        f"- Recommended command: `{' '.join(action.get('command') or [])}`",
    ]
    progress = payload.get("finalProductProgress") if isinstance(payload.get("finalProductProgress"), dict) else {}
    if progress:
        lines.extend(
            [
                "",
                "## Final product progress",
                "",
                f"- Completed phases: `{progress.get('completedPhaseCount')}/{progress.get('totalPhaseCount')}`",
                f"- Progress status: `{progress.get('status')}`",
                "",
                "| Phase | Name | Status | Evidence |",
                "|---:|---|---|---|",
            ]
        )
        for row in progress.get("phases") or []:
            if not isinstance(row, dict):
                continue
            lines.append(f"| {row.get('phase')} | {row.get('name')} | `{row.get('status')}` | {row.get('evidence')} |")
    ci = payload.get("ciStatus") if isinstance(payload.get("ciStatus"), dict) else {}
    if ci:
        lines.extend(
            [
                "",
                "## Current-head CI",
                "",
                f"- Status: `{ci.get('status')}`",
                f"- Current HEAD: `{ci.get('currentHead')}`",
            ]
        )
    final_status = payload.get("finalStatus") if isinstance(payload.get("finalStatus"), dict) else {}
    if final_status:
        final_action = final_status.get("recommendedNextAction") if isinstance(final_status.get("recommendedNextAction"), dict) else {}
        secure_tunnel_client = (
            final_status.get("secureTunnelClient") if isinstance(final_status.get("secureTunnelClient"), dict) else {}
        )
        lines.extend(
            [
                "",
                "## Final readiness",
                "",
                f"- Status: `{final_status.get('status')}`",
                f"- Environment: `{final_status.get('environmentStatus')}`",
                f"- Tool surface: `{final_status.get('toolSurfaceStatus')}`",
                f"- Dependencies: `{final_status.get('dependencyStatus')}`",
                f"- Retired Secure Tunnel client: `{secure_tunnel_client.get('status')}`"
                f" / diagnostics `{secure_tunnel_client.get('binaryDiagnosticsStatus')}`",
                f"- Public session: `{final_status.get('publicSessionStatus')}`",
                f"- Next: `{final_action.get('key')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Latest artifacts",
            "",
            "| Kind | Status | Path | Notes |",
            "|---|---|---|---|",
        ]
    )
    latest = payload.get("latestArtifacts") if isinstance(payload.get("latestArtifacts"), dict) else {}
    for kind, item in latest.items():
        if not item:
            lines.append(f"| `{kind}` | none |  |  |")
            continue
        notes = []
        if item.get("selfTest"):
            notes.append("self-test")
        if item.get("publicUrlExpectedExpired"):
            notes.append("ephemeral URL stopped")
        lines.append(f"| `{kind}` | `{item.get('status')}` | `{item.get('path')}` | {', '.join(notes)} |")
    lines.extend(["", "## Warnings", ""])
    for warning in payload.get("warnings") or ["none"]:
        lines.append(f"- `{warning}`")
    return "\n".join(lines).rstrip() + "\n"


def render_proof_checklist(payload: dict[str, Any]) -> str:
    commands = payload.get("pasteSafeCommands") if isinstance(payload.get("pasteSafeCommands"), dict) else {}
    progress = payload.get("finalProductProgress") if isinstance(payload.get("finalProductProgress"), dict) else {}
    return "\n".join(
        [
            "# RiftReader MCP Proof Checklist",
            "",
            "## Local final gate",
            "",
            f"- [ ] Confirm final readiness is green before any public exposure: `{' '.join(commands.get('finalCompactStatus') or [])}`",
            f"- [ ] Review dashboard summary if anything is blocked: `{' '.join(commands.get('finalStatus') or [])}`",
            f"- [ ] Confirm completed phases: `{progress.get('completedPhaseCount')}/{progress.get('totalPhaseCount')}`.",
            "",
            "## Local refresh checks",
            "",
            "- [ ] Run local readiness if the final gate reports stale readiness.",
            f"  - `{' '.join(commands.get('readiness') or [])}`",
            "- [ ] Run guarded proposal transport smoke if the final gate reports stale proposal smoke.",
            f"  - `{' '.join(commands.get('proposalSmoke') or [])}`",
            "- [ ] Print the Cloudflare named Tunnel Server URL plan before ChatGPT Web/Desktop connector work.",
            f"  - `{' '.join(commands.get('manualPublicIpPlan') or [])}`",
            "- [ ] Do not use OpenAI Secure MCP Tunnel, trycloudflare quick tunnels, or Caddy/router commands as backups; all are retired for this lane.",
            "",
            "## Explicit ChatGPT Cloudflare named Tunnel proof",
            "",
            "- [ ] Print the Cloudflare named Tunnel plan command without starting the server, cloudflared connector, or reverse proxy.",
            "  - `scripts\\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json`",
            "- [ ] Start the local MCP server outside Codex and keep the Cloudflared Windows service healthy; do not recreate Caddy/router forwarding.",
            "- [ ] Generate the current proof template before the ChatGPT-side run.",
            f"  - `{' '.join(commands.get('trialProofTemplate') or [])}`",
            f"- [ ] In ChatGPT Developer Mode, confirm {EXPECTED_CHATGPT_MCP_TOOL_COUNT} tools, `health.repoRoot == \".\"`, and `absoluteRepoRootExposed == false`.",
            f"- [ ] Confirm output schemas are present for all {EXPECTED_CHATGPT_MCP_TOOL_COUNT} tools and record the exact tool-name list.",
            "- [ ] Call `get_package_proposal_template` through actual ChatGPT and record `templateFetched: true`.",
            "- [ ] Submit one tiny package proposal through actual ChatGPT.",
            "- [ ] Confirm `list_inbox` sees the returned inbox ID.",
            f"  - `{' '.join(commands.get('inboxReview') or [])}`",
            "- [ ] Through actual ChatGPT, call `create_package_draft_from_inbox` for that inbox ID.",
            "- [ ] Through actual ChatGPT, call `review_latest_package_draft` and confirm `readOnlyReview: true`.",
            "- [ ] Through actual ChatGPT, call `dry_run_latest_package_draft` and record `dryRun.diffPreview` path, length, bounded-bytes flag, and truncated flag.",
            "- [ ] Through actual ChatGPT, call `apply_latest_package_draft` without an approval token and confirm it is blocked with `APPLY_APPROVAL_MISSING` and `applied: false`.",
            "",
            "## Optional local package review cross-check",
            "",
            "- [ ] If actual ChatGPT did not create the draft, export the inbox item into an inert draft locally before dry-run proof.",
            f"  - `{' '.join(commands.get('draftExport') or [])}`",
            "- [ ] If actual ChatGPT did not dry-run the draft, dry-run the latest draft locally as a cross-check only.",
            f"  - `{' '.join(commands.get('draftDryRun') or [])}`",
            "- [ ] Record actual-client facts with the ChatGPT Trial Recorder.",
            "  - `scripts\\riftreader-chatgpt-trial-recorder.cmd --record --input proof.json --json`",
            "- [ ] Rerun final readiness after recording proof.",
            f"  - `{' '.join(commands.get('finalCompactStatus') or [])}`",
            "",
            "## Safety reminders",
            "",
            "- [ ] Do not use CE, x64dbg, RIFT input, package apply, Git mutation, or provider writes for this MCP proof path.",
            "- [ ] Stop if the final gate reports any blocker; fix the blocker before starting a public trial.",
            "",
        ]
    )


def render_proof_run_packet(payload: dict[str, Any], domain_payload: dict[str, Any] | None = None) -> str:
    """Render a compact current proof packet for ChatGPT Web/Desktop setup."""

    commands = payload.get("pasteSafeCommands") if isinstance(payload.get("pasteSafeCommands"), dict) else {}
    final_status = payload.get("finalStatus") if isinstance(payload.get("finalStatus"), dict) else {}
    latest = payload.get("latestArtifacts") if isinstance(payload.get("latestArtifacts"), dict) else {}
    proof_template = latest.get("proof-input-template") if isinstance(latest.get("proof-input-template"), dict) else {}
    proof_paths = proof_template.get("artifactPaths") if isinstance(proof_template.get("artifactPaths"), dict) else {}
    proof_input_json = proof_paths.get("proofInputJson") or proof_template.get("path") or ""
    domain_payload = domain_payload if isinstance(domain_payload, dict) else {}
    public_url = domain_payload.get("publicMcpUrl") or "https://mcp.360madden.com/mcp"
    backend = domain_payload.get("backend") if isinstance(domain_payload.get("backend"), dict) else {}
    owner = backend.get("owner") if isinstance(backend.get("owner"), dict) else {}
    processes = owner.get("processes") if isinstance(owner.get("processes"), list) else []
    backend_pids = (
        ", ".join(
            str(proc.get("pid"))
            for proc in processes
            if isinstance(proc, dict) and proc.get("pid") not in {None, "", "0", 0}
        )
        or "not-detected"
    )
    public_smoke = domain_payload.get("publicSmoke") if isinstance(domain_payload.get("publicSmoke"), dict) else {}
    server_info = public_smoke.get("serverInfo") if isinstance(public_smoke.get("serverInfo"), dict) else {}
    check_command = [
        "scripts\\riftreader-chatgpt-trial-recorder.cmd",
        "--check-input",
        "--input",
        proof_input_json or "<proof-input.json>",
        "--json",
    ]
    record_command = [
        "scripts\\riftreader-chatgpt-trial-recorder.cmd",
        "--record",
        "--input",
        proof_input_json or "<proof-input.json>",
        "--json",
    ]
    tool_names_json = json.dumps(list(EXPECTED_CHATGPT_MCP_TOOL_NAMES), indent=2)
    lines = [
        "# RiftReader ChatGPT Web/Desktop MCP proof run packet",
        "",
        "## Current route",
        "",
        f"- Server URL: `{public_url}`",
        "- Authentication: `No Authentication`",
        "- Connection mode to record: `cloudflare-named-tunnel`",
        f"- Public smoke: `{public_smoke.get('status', 'unknown')}` HTTP `{public_smoke.get('httpStatus')}`",
        f"- Server info: `{server_info.get('name', 'unknown')}` version `{server_info.get('version', 'unknown')}`",
        f"- Local backend: `127.0.0.1:8770` PID(s) `{backend_pids}`",
        "- Retired paths: OpenAI Secure MCP Tunnel, `trycloudflare.com` quick tunnels, and Caddy/router are not backups.",
        "",
        "## Proof template",
        "",
        f"- Latest proof input: `{proof_input_json or 'missing'}`",
        f"- Template status: `{proof_template.get('status', 'missing')}`",
        f"- Check filled input: `{' '.join(check_command)}`",
        f"- Record after check passes: `{' '.join(record_command)}`",
        "",
        "## ChatGPT call sequence",
        "",
        "1. Connect this MCP in ChatGPT Web/Desktop with the Server URL above and No Authentication.",
        "2. Call `health` and confirm `repoRoot == \".\"` and `absoluteRepoRootExposed == false`.",
        "3. Confirm ChatGPT sees exactly the 12 tool names listed below and output schemas for all 12.",
        "4. Call `get_repo_status`, `get_latest_handoff`, and `get_workflow_control_summary`.",
        "5. Call `get_package_proposal_template` and record `templateFetched: true`.",
        "6. Submit one tiny harmless `package-proposal` via `submit_package_proposal`.",
        "7. Call `list_inbox` and record that it sees the returned `inboxId`.",
        "8. Call `create_package_draft_from_inbox` for that `inboxId`.",
        "9. Call `review_latest_package_draft` and record that the review is read-only.",
        "10. Call `dry_run_latest_package_draft` and record `diffPreview` path, length, bounded-bytes flag, and truncated flag.",
        "11. Call `apply_latest_package_draft` without an approval token and record that it blocks with `APPLY_APPROVAL_MISSING` and `applied=false`.",
        "",
        "## Expected tool names",
        "",
        "```json",
        tool_names_json,
        "```",
        "",
        "## Local validation after filling proof input",
        "",
        f"1. `{' '.join(check_command)}`",
        f"2. `{' '.join(record_command)}`",
        f"3. `{' '.join(commands.get('finalCompactStatus') or [])}`",
        "",
        "## Current blockers to clear",
        "",
    ]
    for blocker in final_status.get("blockers") or payload.get("blockers") or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(
        [
            "",
            "## Safety boundaries",
            "",
            "- Do not send RIFT input, movement, target selection, `/reloadui`, or screenshot-key input during this proof.",
            "- Do not attach CE/x64dbg or promote coordinate/current-truth artifacts.",
            "- Do not apply packages with an approval token, commit, push, or write provider repos during this proof.",
            "- Keep the MCP backend narrow and stop if ChatGPT observes unexpected tools or missing output schemas.",
            "",
        ]
    )
    return "\n".join(lines)


def domain_diagnostics_payload(repo_root: Path) -> dict[str, Any]:
    """Run domain diagnostics through its CMD wrapper to avoid import cycles."""

    envelope = run_command_envelope(
        "proof-run-packet-domain-diagnostics",
        ["scripts\\riftreader-mcp-domain-diagnostics.cmd", "--public-mcp-host", "mcp.360madden.com", "--json"],
        repo_root,
        timeout_seconds=45,
        expected_exit_codes={0, 1, 2},
        capture_full_output=True,
    )
    stdout = envelope.get("stdout") if isinstance(envelope.get("stdout"), str) else ""
    parsed: dict[str, Any] = {}
    if stdout.strip().startswith("{"):
        try:
            loaded = json.loads(stdout)
            if isinstance(loaded, dict):
                parsed = loaded
        except json.JSONDecodeError:
            parsed = {}
    if parsed:
        parsed.setdefault("commandEnvelope", envelope)
        return parsed
    return {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-mcp-domain-diagnostics-unavailable",
        "generatedAtUtc": utc_iso(),
        "status": "blocked",
        "ok": False,
        "publicMcpUrl": "https://mcp.360madden.com/mcp",
        "blockers": ["domain-diagnostics-json-unavailable"],
        "commandEnvelope": envelope,
        "safety": {
            **safety_flags(),
            "statusOnly": True,
            "serverStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
            "inputSent": False,
            "movementSent": False,
        },
    }


def run_local_action(repo_root: Path, command_key: str, label: str) -> dict[str, Any]:
    commands = standard_commands()
    args = commands[command_key]
    envelope = run_command_envelope(label, args, repo_root, timeout_seconds=180, expected_exit_codes={0, 2}, capture_full_output=True)
    status = "passed" if envelope.get("exitCode") == 0 else "blocked" if envelope.get("exitCode") == 2 else "failed"
    parsed_stdout = None
    stdout = envelope.get("stdout") if isinstance(envelope.get("stdout"), str) else ""
    if stdout.strip().startswith("{"):
        try:
            parsed_stdout = json.loads(stdout)
        except json.JSONDecodeError:
            parsed_stdout = None
    return {
        "schemaVersion": 1,
        "kind": f"riftreader-mcp-mission-control-{label}",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "command": args,
        "commandEnvelope": envelope,
        "parsedStdout": parsed_stdout,
        "safety": {
            **safety_flags(),
            "publicTunnelStarted": False,
            "gitMutation": False,
            "applyFlagSent": False,
        },
    }


def print_human(payload: dict[str, Any]) -> None:
    print(f"Status: {payload.get('status')} ok={payload.get('ok')}")
    action = payload.get("operatorNextAction") or payload.get("recommendedNextAction")
    if isinstance(action, dict):
        print(f"Next: {action.get('key')} - {' '.join(action.get('command') or [])}")
        print(f"Why: {action.get('reason')}")
    latest = payload.get("latestArtifacts") if isinstance(payload.get("latestArtifacts"), dict) else {}
    for key, item in latest.items():
        if item:
            print(f"- {key}: {item.get('status')} {item.get('path')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RiftReader MCP Mission Control dashboard.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run-readiness", action="store_true", help="Run local MCP trial-readiness only.")
    mode.add_argument("--run-proposal-smoke", action="store_true", help="Run local proposal transport smoke only.")
    mode.add_argument("--manual-public-ip-plan", action="store_true", help="Print the active Cloudflare named Tunnel plan command.")
    mode.add_argument("--secure-tunnel-plan", action="store_true", help="Retired: Secure MCP Tunnel is no longer a fallback path.")
    mode.add_argument("--trial-command", action="store_true", help="Retired: Cloudflare ChatGPT trial sessions are no longer a fallback path.")
    mode.add_argument("--summary-md", action="store_true", help="Print a Markdown mission-control summary.")
    mode.add_argument("--checklist-md", action="store_true", help="Print a Markdown actual-client proof checklist.")
    mode.add_argument("--proof-run-packet-md", action="store_true", help="Print a current ChatGPT Web/Desktop proof run packet.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.run_readiness:
        payload = run_local_action(repo_root, "mcpTrialReadiness", "run-readiness")
    elif args.run_proposal_smoke:
        payload = run_local_action(repo_root, "proposalTransportSmoke", "run-proposal-smoke")
    elif args.manual_public_ip_plan:
        payload = manual_public_ip_plan_payload(repo_root)
    elif args.secure_tunnel_plan:
        payload = secure_tunnel_plan_payload(repo_root)
    elif args.trial_command:
        payload = trial_command_payload(repo_root)
    elif args.summary_md:
        payload = mission_control(repo_root)
        print(render_summary_markdown(payload))
        return 0 if payload.get("ok") else 2 if payload.get("status") == "blocked" else 1
    elif args.checklist_md:
        payload = mission_control(repo_root)
        print(render_proof_checklist(payload))
        return 0
    elif args.proof_run_packet_md:
        payload = mission_control(repo_root)
        domain_payload = domain_diagnostics_payload(repo_root)
        print(render_proof_run_packet(payload, domain_payload))
        return 0
    else:
        payload = mission_control(repo_root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_human(payload)
    return 0 if payload.get("ok") else 2 if payload.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
