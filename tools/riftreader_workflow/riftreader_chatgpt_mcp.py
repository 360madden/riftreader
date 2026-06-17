#!/usr/bin/env python3
"""Narrow RiftReader MCP adapter for Desktop ChatGPT Developer Mode.

This module intentionally exposes only a small allowlisted surface over the
existing Local Artifact Bridge, package-draft review, commit-preflight, and
workflow-status helpers. It does not proxy broad local MCPs, does not expose
shell/live-game actions, and keeps ChatGPT-originated writes bounded to
allowlisted package drafts plus approval-gated explicit-path local commits.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import queue
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal
from urllib.parse import urlsplit

try:
    from . import commit_reviewed_slice
    from . import local_artifact_bridge as bridge
    from . import mcp_mission_control, safe_commit_packager
    from . import package_manifest
    from . import package_draft_review, status_packet, tracked_repo_context
    from .common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, utc_iso
    from .mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_NAMES, PACKAGE_PROOF_TOOL_NAMES, PUBLIC_READ_ONLY_TOOL_NAMES
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow import commit_reviewed_slice
    from riftreader_workflow import local_artifact_bridge as bridge
    from riftreader_workflow import mcp_mission_control, safe_commit_packager
    from riftreader_workflow import package_manifest
    from riftreader_workflow import package_draft_review, status_packet, tracked_repo_context
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, utc_iso
    from riftreader_workflow.mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_NAMES, PACKAGE_PROOF_TOOL_NAMES, PUBLIC_READ_ONLY_TOOL_NAMES


SCHEMA_VERSION = 1
VERSION = "0.1.2"
SERVER_NAME = "riftreader_chatgpt_mcp"
DEFAULT_PAYLOAD_ROOT = Path("artifacts") / "chatgpt-payloads"
DEFAULT_AUDIT_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "audit"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8770
DEFAULT_DRY_RUN_TIMEOUT_SECONDS = 180.0
DEFAULT_TRANSPORT_SMOKE_TIMEOUT_SECONDS = 30.0
TRANSPORT_CLIENT_CONNECT_TIMEOUT_SECONDS = 5.0
TRANSPORT_CLIENT_WRITE_TIMEOUT_SECONDS = 30.0
TRANSPORT_CLIENT_POOL_TIMEOUT_SECONDS = 30.0
TRANSPORT_CLIENT_READ_TIMEOUT_MARGIN_SECONDS = 5.0
DEFAULT_CLOUDFLARE_SMOKE_TIMEOUT_SECONDS = 120.0
DEFAULT_CHATGPT_SESSION_SECONDS = 900.0
DEFAULT_CHATGPT_ORIGIN = "https://chatgpt.com"
SECURE_TUNNEL_ID_PLACEHOLDER = "<tunnel_id from Platform tunnel settings>"
SECURE_TUNNEL_ID_RE = re.compile(r"^tunnel_[A-Za-z0-9_-]{4,}$")
SECRET_LIKE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai-api-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b")),
    ("bearer-token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}")),
)
MAX_HANDOFF_BYTES = 512 * 1024
MAX_DRY_RUN_DIFF_PREVIEW_BYTES = 16 * 1024
WORKFLOW_CONTROL_LIST_LIMIT = 5
WORKFLOW_CONTROL_TEXT_LIMIT = 160
WORKFLOW_CONTROL_MINIFIED_BYTES_TARGET = 8 * 1024
WORKFLOW_CONTROL_SUMMARY_MINIFIED_BYTES_TARGET = 3 * 1024
MCP_REPO_TREE_DEFAULT_LIMIT = 200
MCP_REPO_TREE_MAX_LIMIT = 500
MCP_REPO_SEARCH_DEFAULT_MATCHES = 25
MCP_REPO_SEARCH_MAX_MATCHES = 50
MCP_REPO_READ_FILE_DEFAULT_BYTES = 64 * 1024
MCP_REPO_READ_FILE_MAX_BYTES = 256 * 1024
MCP_REPO_READ_TOTAL_DEFAULT_BYTES = 256 * 1024
MCP_REPO_READ_TOTAL_MAX_BYTES = 512 * 1024
MCP_REPO_CONTEXT_PACK_DEFAULT_FILES = 8
MCP_REPO_CONTEXT_PACK_MAX_FILES = 12
MCP_REPO_READ_MANY_MAX_FILES = 20
BRIDGE_TOKEN = "riftreader-chatgpt-mcp-local"
CLOUDFLARED_DEFAULT_PATHS = (
    Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe"),
    Path(r"C:\Program Files\cloudflared\cloudflared.exe"),
)
TUNNEL_CLIENT_DEFAULT_PATHS = (
    Path(r"C:\RIFT MODDING\Tools\OpenAI\tunnel-client\tunnel-client.exe"),
    Path(r"C:\Program Files\OpenAI\tunnel-client\tunnel-client.exe"),
    Path(r"C:\Program Files (x86)\OpenAI\tunnel-client\tunnel-client.exe"),
)
CLOUDFLARE_QUICK_TUNNEL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

EXPECTED_TOOL_ORDER = EXPECTED_CHATGPT_MCP_TOOL_NAMES
PACKAGE_PROOF_TOOL_ORDER = PACKAGE_PROOF_TOOL_NAMES
PUBLIC_READ_ONLY_TOOL_ORDER = PUBLIC_READ_ONLY_TOOL_NAMES
TOOL_PROFILE_FULL = "full"
TOOL_PROFILE_PUBLIC_READ_ONLY = "public-read-only"
TOOL_PROFILES = (TOOL_PROFILE_FULL, TOOL_PROFILE_PUBLIC_READ_ONLY)
TOOL_ARGUMENT_KEYS: dict[str, frozenset[str]] = {
    "health": frozenset(),
    "get_repo_status": frozenset(),
    "get_latest_handoff": frozenset(),
    "get_workflow_control_summary": frozenset(),
    "get_package_proposal_template": frozenset(),
    "submit_package_proposal": frozenset({"proposal"}),
    "list_inbox": frozenset(),
    "create_package_draft_from_inbox": frozenset({"inboxId"}),
    "review_latest_package_draft": frozenset({"operatorOnly"}),
    "dry_run_latest_package_draft": frozenset({"operatorOnly", "timeoutSeconds"}),
    "apply_latest_package_draft": frozenset(
        {"operatorOnly", "dryRunSummaryPath", "dryRunDiffSha256", "approvalToken", "timeoutSeconds"}
    ),
    "commit_reviewed_slice": frozenset(
        {
            "expectedHead",
            "paths",
            "commitMessage",
            "validationSummaryPath",
            "validationDigest",
            "approvalToken",
            "timeoutSeconds",
        }
    ),
    "get_workflow_control_plan": frozenset(),
    "get_dirty_paths": frozenset(),
    "get_recent_commits": frozenset({"limit"}),
    "repo_tree_tracked": frozenset({"prefix", "depth", "limit", "includeBlockedMeta"}),
    "repo_search_tracked": frozenset({"query", "caseSensitive", "regex", "maxMatches", "maxFileBytes"}),
    "repo_read_tracked_file": frozenset({"path", "maxBytes", "includeSha256"}),
    "repo_read_many_tracked_files": frozenset({"paths", "maxFileBytes", "maxTotalBytes", "maxFiles"}),
    "repo_context_pack": frozenset({"packName", "maxFiles", "maxFileBytes", "maxTotalBytes"}),
}
TOOL_ARGUMENT_SIZE_OVERHEAD_BYTES = 16 * 1024


def tool_order_for_profile(tool_profile: str = TOOL_PROFILE_FULL) -> tuple[str, ...]:
    if tool_profile == TOOL_PROFILE_FULL:
        return EXPECTED_TOOL_ORDER
    if tool_profile == TOOL_PROFILE_PUBLIC_READ_ONLY:
        return PUBLIC_READ_ONLY_TOOL_ORDER
    raise AdapterError(
        "TOOL_PROFILE_INVALID",
        f"Unknown MCP tool profile: {tool_profile!r}.",
        status="failed",
        extra={"toolProfile": tool_profile, "allowedProfiles": list(TOOL_PROFILES)},
    )


def limited_list(value: Any, *, limit: int = WORKFLOW_CONTROL_LIST_LIMIT) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:limit]


def compact_text(value: Any, *, max_chars: int = WORKFLOW_CONTROL_TEXT_LIMIT) -> str:
    text = str(value)
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def compact_text_list(value: Any, *, limit: int = WORKFLOW_CONTROL_LIST_LIMIT) -> list[str]:
    if not isinstance(value, list):
        return []
    return [compact_text(item) for item in value[:limit]]


def compact_safety_flags(safety: Any) -> dict[str, Any]:
    if not isinstance(safety, dict):
        return {}
    keys = (
        "gitMutation",
        "providerWrites",
        "inputSent",
        "movementSent",
        "reloaduiSent",
        "screenshotKeySent",
        "noCheatEngine",
        "x64dbgAttach",
        "publicTunnelStarted",
        "chatGptRegistrationPerformed",
        "finalGateReadOnly",
    )
    return {key: safety.get(key) for key in keys if key in safety}


def compact_workflow_safety(safety: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "readOnlyControlPlan",
        "planOnly",
        "shellExecutionEndpoint",
        "gitMutation",
        "tunnelControl",
        "providerWrites",
        "inputSent",
        "movementSent",
        "noCheatEngine",
        "x64dbgAttach",
    )
    return {key: safety.get(key) for key in keys if key in safety}


def compact_tunnel_client_status(tunnel_client: Any) -> dict[str, Any]:
    if not isinstance(tunnel_client, dict):
        return {}
    return {
        "status": tunnel_client.get("status"),
        "ok": tunnel_client.get("ok"),
        "path": tunnel_client.get("path"),
        "blockers": compact_text_list(tunnel_client.get("blockers"), limit=3),
    }


def compact_final_status(final_status: dict[str, Any]) -> dict[str, Any]:
    all_blockers = final_status.get("blockers") if isinstance(final_status.get("blockers"), list) else []
    all_warnings = final_status.get("warnings") if isinstance(final_status.get("warnings"), list) else []
    return {
        "status": final_status.get("status"),
        "ok": final_status.get("ok"),
        "currentHead": final_status.get("currentHead"),
        "gitDirty": final_status.get("gitDirty"),
        "toolSurfaceStatus": final_status.get("toolSurfaceStatus"),
        "dependencyStatus": final_status.get("dependencyStatus"),
        "environmentStatus": final_status.get("environmentStatus"),
        "ciStatus": final_status.get("ciStatus"),
        "proofReplayStatus": final_status.get("proofReplayStatus"),
        "proofFreshnessStatus": final_status.get("proofFreshnessStatus"),
        "upstreamStatus": final_status.get("upstreamStatus"),
        "phase2Status": final_status.get("phase2Status"),
        "recommendedNextAction": final_status.get("recommendedNextAction"),
        "secureTunnelClient": compact_tunnel_client_status(final_status.get("secureTunnelClient")),
        "blockerCount": len(all_blockers),
        "warningCount": final_status.get("warningCount", len(all_warnings)),
        "safety": compact_safety_flags(final_status.get("safety")),
    }


def compact_final_product_progress(progress: Any) -> dict[str, Any]:
    if not isinstance(progress, dict):
        return {}
    phases = progress.get("phases") if isinstance(progress.get("phases"), list) else []
    return {
        "schemaVersion": progress.get("schemaVersion"),
        "kind": progress.get("kind"),
        "status": progress.get("status"),
        "completedPhaseCount": progress.get("completedPhaseCount"),
        "totalPhaseCount": progress.get("totalPhaseCount"),
        "currentCompletedThroughPhase": progress.get("currentCompletedThroughPhase"),
        "recommendedConnection": progress.get("recommendedConnection"),
        "recommendedNextAction": progress.get("recommendedNextAction"),
        "nextPhase": progress.get("nextPhase"),
        "actualClientProofCompleted": progress.get("actualClientProofCompleted"),
        "chatGptRegistrationPerformed": progress.get("chatGptRegistrationPerformed"),
        "publicTunnelStarted": progress.get("publicTunnelStarted"),
        "phaseCount": len(phases),
    }


def compact_stage_plan(stage_plan: dict[str, Any]) -> dict[str, Any]:
    phase_order = stage_plan.get("phaseOrder") if isinstance(stage_plan.get("phaseOrder"), list) else []
    return {
        "schemaVersion": stage_plan.get("schemaVersion"),
        "kind": stage_plan.get("kind"),
        "status": stage_plan.get("status"),
        "stageCount": stage_plan.get("stageCount"),
        "currentStage": stage_plan.get("currentStage"),
        "currentStageName": stage_plan.get("currentStageName"),
        "nextStage": stage_plan.get("nextStage"),
        "nextStageName": stage_plan.get("nextStageName"),
        "planPath": stage_plan.get("planPath"),
        "currentTruth": stage_plan.get("currentTruth"),
        "immediateStages": limited_list(stage_plan.get("immediateStages")),
        "phaseOrderCount": len(phase_order),
    }


def compact_future_capability_roadmap(roadmap: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in roadmap:
        compact.append(
            {
                "key": item.get("key"),
                "currentStatus": item.get("currentStatus"),
                "riskClass": item.get("riskClass"),
                "targetToolName": item.get("targetToolName"),
                "safePrecursorTools": item.get("safePrecursorTools") or [],
            }
        )
    return compact


def compact_apply_tool_contract(contract: dict[str, Any]) -> dict[str, Any]:
    required_gates = contract.get("requiredGates") if isinstance(contract.get("requiredGates"), list) else []
    fail_closed = contract.get("failClosedBlockers") if isinstance(contract.get("failClosedBlockers"), list) else []
    required_gate_preview = [gate for gate in required_gates if gate == "diff-hash-binding"]
    fail_closed_preview = [blocker for blocker in fail_closed if blocker == "APPLY_DRY_RUN_HASH_MISMATCH"]
    return {
        "status": contract.get("status"),
        "targetToolName": contract.get("targetToolName"),
        "designPath": contract.get("designPath"),
        "currentStage": contract.get("currentStage"),
        "exposureStatus": contract.get("exposureStatus"),
        "argumentKeys": contract.get("argumentKeys") or [],
        "requiredGateCount": len(required_gates),
        "requiredGates": required_gate_preview,
        "failClosedBlockerCount": len(fail_closed),
        "failClosedBlockers": fail_closed_preview,
        "requiredPrecursorTools": contract.get("requiredPrecursorTools") or [],
        "preflightHelper": {
            key: (contract.get("preflightHelper") or {}).get(key)
            for key in ("status", "mutatesRepo", "passesApplyFlag")
        },
        "applyBridgeHelper": {
            key: (contract.get("applyBridgeHelper") or {}).get(key)
            for key in ("status", "requiresApprovalToken", "gitMutation", "mcpToolExposed")
        },
    }


def compact_push_tool_contract(contract: dict[str, Any]) -> dict[str, Any]:
    required_gates = contract.get("requiredGates") if isinstance(contract.get("requiredGates"), list) else []
    fail_closed = contract.get("failClosedBlockers") if isinstance(contract.get("failClosedBlockers"), list) else []
    return {
        "status": contract.get("status"),
        "targetToolName": contract.get("targetToolName"),
        "designPath": contract.get("designPath"),
        "currentStage": contract.get("currentStage"),
        "exposureStatus": contract.get("exposureStatus"),
        "argumentKeys": contract.get("argumentKeys") or [],
        "requiredGateCount": len(required_gates),
        "requiredGates": [
            gate
            for gate in required_gates
            if gate in {"clean-worktree", "ahead-of-upstream", "explicit-approval-token", "no-force-push"}
        ],
        "failClosedBlockerCount": len(fail_closed),
        "failClosedBlockers": [
            blocker
            for blocker in fail_closed
            if blocker in {"PUSH_WORKTREE_DIRTY", "PUSH_BRANCH_BEHIND", "PUSH_APPROVAL_MISSING", "PUSH_FORCE_FORBIDDEN"}
        ],
        "requiredPrecursorTools": contract.get("requiredPrecursorTools") or [],
        "preflightHelper": {
            key: (contract.get("preflightHelper") or {}).get(key)
            for key in ("status", "mutatesRepo", "pushesRemote", "requiresApprovalToken")
        },
        "pushExecutionHelper": {
            key: (contract.get("pushExecutionHelper") or {}).get(key)
            for key in ("status", "requiresApprovalToken", "remoteMutation", "mcpToolExposed")
        },
    }


def compact_ranked_actions(actions: Any) -> list[dict[str, Any]]:
    if not isinstance(actions, list):
        return []
    compact: list[dict[str, Any]] = []
    for item in actions[:WORKFLOW_CONTROL_LIST_LIMIT]:
        if isinstance(item, dict):
            compact.append(
                {
                    "key": item.get("key"),
                    "priority": item.get("priority"),
                    "command": item.get("command"),
                }
            )
    return compact


def compact_safe_commit_plan(commit_plan: dict[str, Any]) -> dict[str, Any]:
    stageable_paths = commit_plan.get("stageablePaths") if isinstance(commit_plan.get("stageablePaths"), list) else []
    validation_commands = (
        commit_plan.get("validationCommandsBeforeCommit")
        if isinstance(commit_plan.get("validationCommandsBeforeCommit"), list)
        else []
    )
    return {
        "status": commit_plan.get("status"),
        "stageablePathCount": len(stageable_paths),
        "stageablePaths": stageable_paths[:WORKFLOW_CONTROL_LIST_LIMIT],
        "draftCommitMessage": commit_plan.get("draftCommitMessage"),
        "validationCommandCount": len(validation_commands),
        "containsGitAddDot": commit_plan.get("containsGitAddDot"),
        "safety": commit_plan.get("safety"),
    }


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    read_only: bool
    destructive: bool
    open_world: bool

    def annotation_payload(self) -> dict[str, bool]:
        return {
            "readOnlyHint": self.read_only,
            "destructiveHint": self.destructive,
            "openWorldHint": self.open_world,
        }


FUTURE_CAPABILITY_ROADMAP: tuple[dict[str, Any], ...] = (
    {
        "key": "apply-package-to-repo",
        "targetToolName": "apply_latest_package_draft",
        "currentStatus": "exposed-gated",
        "riskClass": "repo-source-mutation",
        "minimumGate": "explicit-operator-approval-plus-clean-reviewed-dry-run",
        "safePrecursorTools": ["review_latest_package_draft", "dry_run_latest_package_draft"],
        "requiredSafeguards": [
            "latest draft must be operator-originated, not self-test",
            "dry-run diff preview must be fresh and reviewed",
            "apply command must use explicit package path under .riftreader-local only",
            "no Git staging, commit, push, shell, RIFT input, CE, or x64dbg side effects",
            "post-apply validation summary must be returned before any commit step",
        ],
    },
    {
        "key": "commit-local-slice",
        "targetToolName": "commit_reviewed_slice",
        "currentStatus": "exposed-gated",
        "riskClass": "git-local-mutation",
        "minimumGate": "explicit-operator-approval-plus-current-commit-preflight-token",
        "safePrecursorTools": ["get_workflow_control_plan", "get_dirty_paths"],
        "requiredSafeguards": [
            "rerun local commit preflight immediately before staging",
            "require exact expectedHead, validation digest, validation summary path, and approval token",
            "stage explicit validated paths only",
            "never run git add .",
            "run pre-commit on explicit files before git commit",
            "no push, branch rewrite, reset, clean, or remote mutation",
        ],
    },
    {
        "key": "push-current-branch",
        "targetToolName": "push_current_branch",
        "currentStatus": "designed-not-exposed",
        "riskClass": "git-remote-mutation",
        "minimumGate": "explicit-operator-approval-in-current-turn",
        "safePrecursorTools": ["get_repo_status", "get_workflow_control_plan"],
        "requiredSafeguards": [
            "branch, upstream, ahead/behind state, and commit hash must be returned first",
            "worktree must be clean",
            "required local validation or pre-commit evidence must be current",
            "no force push or branch rewrite",
            "post-push CI links/status must be returned",
        ],
    },
    {
        "key": "bounded-shell-command",
        "targetToolName": "run_bounded_repo_command",
        "currentStatus": "not-exposed",
        "riskClass": "shell-execution",
        "minimumGate": "explicit-operator-approval-plus-command-allowlist",
        "safePrecursorTools": ["get_workflow_control_plan"],
        "requiredSafeguards": [
            "command must match a repo-owned allowlist entry",
            "arguments must be arrays, not shell strings",
            "timeout and output caps must be enforced",
            "destructive commands and broad filesystem writes must be blocked",
            "no RIFT input, CE, x64dbg, provider writes, or hidden Git mutation",
        ],
    },
    {
        "key": "live-rift-control",
        "targetToolName": "control_rift_live",
        "currentStatus": "not-exposed",
        "riskClass": "live-game-state-mutation",
        "minimumGate": "explicit-live-approval-and-current-target-proof",
        "safePrecursorTools": ["get_repo_status", "get_latest_handoff"],
        "requiredSafeguards": [
            "exact PID/HWND/process-start target identity must be current",
            "movement/input intent must be approved in the current turn",
            "no debugger, CE, proof promotion, or provider writes by default",
            "bounded action plan and stop conditions must be returned first",
            "post-action evidence must record inputSent/movementSent truthfully",
        ],
    },
    {
        "key": "debugger-or-ce-assist",
        "targetToolName": "debugger_ce_assist",
        "currentStatus": "not-exposed",
        "riskClass": "debugger-attach-crash-risk",
        "minimumGate": "explicit-debugger-approval-in-current-turn",
        "safePrecursorTools": ["get_repo_status", "get_latest_handoff"],
        "requiredSafeguards": [
            "attach target and crash risk must be stated before action",
            "no automatic breakpoints/watchpoints without separate approval",
            "read-only static/offline alternatives must be preferred first",
            "candidate evidence must remain candidate-only until proof gates pass",
            "promotion/current-truth updates require separate approval",
        ],
    },
)


FULL_PRODUCT_STAGE_PLAN: dict[str, Any] = {
    "schemaVersion": SCHEMA_VERSION,
    "kind": "riftreader-chatgpt-mcp-50-stage-finished-product-plan",
    "status": "active",
    "planPath": "docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md",
    "stageCount": 50,
    "currentStage": 29,
    "currentStageName": "Push preflight helper",
    "currentTruth": (
        f"Current {len(EXPECTED_TOOL_ORDER)}-tool MCP is proven for gated apply and approval-gated explicit-path "
        "local commit. Stage 28 push design is complete; push_current_branch remains not exposed until "
        "the read-only preflight helper, tests, approval-token gate, and CI follow-up contract are implemented."
    ),
    "nextStage": 30,
    "nextStageName": "Expose push_current_branch after safe preflight",
    "phaseOrder": [
        f"prove current {len(EXPECTED_TOOL_ORDER)}-tool gated-apply Cloudflare named Tunnel product",
        "add package apply with reviewed dry-run gates",
        "add local commit with safe explicit-path staging",
        "add push as separate remote-mutation gate",
        "add bounded repo command allowlist",
        "add provider-write planning and separation",
        "add live RIFT read-only then gated control",
        "add debugger/CE plan-only then gated assist",
        "add optional auth/roles for broader sharing",
        "add end-to-end evals, dashboard, recovery, and release handoff",
    ],
    "immediateStages": [
        {"stage": 21, "name": "Apply actual-client proof", "status": "complete"},
        {"stage": 22, "name": "Post-apply validation reporting", "status": "complete-local"},
        {"stage": 23, "name": "Safe commit design spec", "status": "complete-local"},
        {"stage": 24, "name": "Commit preflight helper", "status": "complete-local"},
        {"stage": 25, "name": "Commit execution helper", "status": "complete-local"},
        {"stage": 26, "name": "Expose commit_reviewed_slice", "status": "complete-local"},
        {"stage": 27, "name": "Commit actual-client proof", "status": "complete"},
        {"stage": 28, "name": "Push design spec", "status": "complete-local"},
        {"stage": 29, "name": "Push preflight helper", "status": "pending"},
    ],
    "finishedProductDefinition": (
        "All intended ChatGPT Web/Desktop repo, Git, command, live, and debugger workflows "
        "are implemented, gated, proven, documented, recoverable, and passing final readiness."
    ),
}


APPLY_TOOL_DESIGN_CONTRACT: dict[str, Any] = {
    "schemaVersion": SCHEMA_VERSION,
    "kind": "riftreader-chatgpt-mcp-apply-tool-design-contract",
    "status": "exposed-gated",
    "targetToolName": "apply_latest_package_draft",
    "designPath": "docs/workflow/riftreader-chatgpt-mcp-apply-tool-design.md",
    "stageRange": [17, 18, 19, 20, 21, 22],
    "currentStage": 20,
    "exposureStatus": "exposed-gated",
    "preflightHelper": {
        "status": "implemented-local-only",
        "module": "tools/riftreader_workflow/package_draft_review.py",
        "cliMode": "--apply-preflight-latest-operator",
        "mutatesRepo": False,
        "passesApplyFlag": False,
    },
    "applyBridgeHelper": {
        "status": "implemented-and-mcp-wrapped",
        "module": "tools/riftreader_workflow/package_draft_review.py",
        "cliMode": "--apply-latest-operator",
        "requiresApprovalToken": True,
        "requiresPreflight": True,
        "passesApplyFlagOnlyAfterApproval": True,
        "gitMutation": False,
        "providerWrites": False,
        "mcpToolExposed": True,
    },
    "argumentKeys": [
        "operatorOnly",
        "draftId",
        "dryRunSummaryPath",
        "dryRunDiffSha256",
        "approvalToken",
        "timeoutSeconds",
    ],
    "requiredPrecursorTools": ["review_latest_package_draft", "dry_run_latest_package_draft"],
    "requiredGates": [
        "operator-origin-draft",
        "draft-root-confinement",
        "package-root-confinement",
        "fresh-dry-run",
        "diff-hash-binding",
        "explicit-approval-token",
        "clean-worktree-preflight",
        "no-apply-flag-leakage",
        "post-apply-validation-by-default",
        "truthful-safety-flags",
    ],
    "failClosedBlockers": [
        "APPLY_TOOL_NOT_ENABLED",
        "APPLY_APPROVAL_MISSING",
        "APPLY_DRAFT_SELF_TEST_BLOCKED",
        "APPLY_DRAFT_NOT_FOUND",
        "APPLY_DRAFT_ROOT_INVALID",
        "APPLY_DRY_RUN_MISSING",
        "APPLY_DRY_RUN_STALE",
        "APPLY_DRY_RUN_HASH_MISMATCH",
        "APPLY_WORKTREE_DIRTY_UNRELATED",
        "APPLY_PACKAGE_TARGET_INVALID",
        "APPLY_VALIDATION_FAILED",
    ],
}


PUSH_TOOL_DESIGN_CONTRACT: dict[str, Any] = {
    "schemaVersion": SCHEMA_VERSION,
    "kind": "riftreader-chatgpt-mcp-push-tool-design-contract",
    "status": "designed-not-exposed",
    "targetToolName": "push_current_branch",
    "designPath": "docs/workflow/riftreader-chatgpt-mcp-push-tool-design.md",
    "stageRange": [28, 29, 30, 31],
    "currentStage": 28,
    "exposureStatus": "not-exposed",
    "preflightHelper": {
        "status": "planned-stage-29",
        "module": "tools/riftreader_workflow/push_current_branch.py",
        "cliMode": "--preflight",
        "mutatesRepo": False,
        "pushesRemote": False,
        "requiresApprovalToken": False,
    },
    "pushExecutionHelper": {
        "status": "planned-stage-30",
        "module": "tools/riftreader_workflow/push_current_branch.py",
        "cliMode": "--push",
        "requiresApprovalToken": True,
        "remoteMutation": True,
        "mcpToolExposed": False,
    },
    "argumentKeys": [
        "expectedHead",
        "branch",
        "upstream",
        "approvalToken",
        "timeoutSeconds",
    ],
    "requiredPrecursorTools": ["get_repo_status", "get_workflow_control_plan"],
    "requiredGates": [
        "running-current-mcp-before-actual-client-proof",
        "clean-worktree",
        "named-current-branch",
        "unambiguous-origin-upstream",
        "ahead-of-upstream",
        "not-behind-upstream",
        "exact-head-branch-upstream-binding",
        "explicit-approval-token",
        "no-force-push",
        "no-branch-rewrite",
        "no-reset-clean-or-stash",
        "post-push-remote-head-verification",
        "post-push-ci-status-visible",
    ],
    "failClosedBlockers": [
        "PUSH_BRANCH_UNNAMED",
        "PUSH_UPSTREAM_MISSING",
        "PUSH_UPSTREAM_AMBIGUOUS",
        "PUSH_REMOTE_UNEXPECTED",
        "PUSH_WORKTREE_DIRTY",
        "PUSH_HEAD_MISMATCH",
        "PUSH_BRANCH_MISMATCH",
        "PUSH_UPSTREAM_MISMATCH",
        "PUSH_NOTHING_TO_PUSH",
        "PUSH_BRANCH_BEHIND",
        "PUSH_DIVERGED",
        "PUSH_APPROVAL_MISSING",
        "PUSH_APPROVAL_TOKEN_MISMATCH",
        "PUSH_FORCE_FORBIDDEN",
        "PUSH_REMOTE_HEAD_VERIFY_FAILED",
    ],
    "safety": {
        "gitMutation": False,
        "remoteMutationOnlyAfterApproval": True,
        "providerWrites": False,
        "mcpToolExposed": False,
        "forcePushAllowed": False,
        "branchRewriteAllowed": False,
    },
}


TOOL_SPECS: dict[str, ToolSpec] = {
    "health": ToolSpec(
        name="health",
        title="RiftReader MCP Health",
        description=(
            "Use this when you need to verify that the narrow RiftReader ChatGPT MCP adapter is running "
            "and to inspect its safety boundaries before calling any other tool."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "get_repo_status": ToolSpec(
        name="get_repo_status",
        title="Get RiftReader Repo Status",
        description=(
            "Use this when you need compact current RiftReader workflow truth, Git status, blocker state, "
            "and safe next-action context without mutating Git, RIFT, CE, x64dbg, or provider repos."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "get_latest_handoff": ToolSpec(
        name="get_latest_handoff",
        title="Get Latest RiftReader Handoff",
        description=(
            "Use this when you need the newest repo-owned handoff text from docs/handoffs only. "
            "This tool never reads arbitrary filesystem paths."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "get_workflow_control_summary": ToolSpec(
        name="get_workflow_control_summary",
        title="Get Compact Workflow Control Summary",
        description=(
            "Use this when ChatGPT needs the smallest safe workflow-control summary or when "
            "get_workflow_control_plan is too large or slow for the current MCP transport."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "get_package_proposal_template": ToolSpec(
        name="get_package_proposal_template",
        title="Get Package Proposal Template",
        description=(
            "Use this when Desktop ChatGPT needs the exact package-proposal JSON shape accepted by the "
            "guarded Local Artifact Bridge inbox."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "submit_package_proposal": ToolSpec(
        name="submit_package_proposal",
        title="Submit Package Proposal",
        description=(
            "Use this when the operator explicitly wants Desktop ChatGPT to submit a structured "
            "package-proposal for later local review. The proposal is stored only under .riftreader-local "
            "and is never applied, executed, staged, committed, pushed, or sent to RIFT."
        ),
        read_only=False,
        destructive=False,
        open_world=False,
    ),
    "list_inbox": ToolSpec(
        name="list_inbox",
        title="List Local Artifact Bridge Inbox",
        description=(
            "Use this when you need metadata for locally stored ChatGPT proposals under .riftreader-local "
            "without reading arbitrary files or applying proposal content."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "create_package_draft_from_inbox": ToolSpec(
        name="create_package_draft_from_inbox",
        title="Create Package Draft From Inbox",
        description=(
            "Use this when the operator explicitly wants ChatGPT to convert a specific validated inbox package-proposal "
            "into an inert local package draft under .riftreader-local for review. This never applies files, executes checks, "
            "stages, commits, pushes, starts tunnels, registers ChatGPT, sends RIFT input, or touches CE/x64dbg."
        ),
        read_only=False,
        destructive=False,
        open_world=False,
    ),
    "review_latest_package_draft": ToolSpec(
        name="review_latest_package_draft",
        title="Review Latest Package Draft",
        description=(
            "Use this when you need the newest inert package draft summary and blockers before any "
            "operator-approved dry-run. By default it selects the latest non-self-test operator draft."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "dry_run_latest_package_draft": ToolSpec(
        name="dry_run_latest_package_draft",
        title="Dry-Run Latest Package Draft",
        description=(
            "Use this when the operator explicitly approves running package intake dry-run for the newest "
            "inert package draft. This never passes --apply and never mutates repo source, Git, RIFT, CE, or x64dbg."
        ),
        read_only=False,
        destructive=False,
        open_world=False,
    ),
    "apply_latest_package_draft": ToolSpec(
        name="apply_latest_package_draft",
        title="Apply Latest Package Draft",
        description=(
            "Use this when the local operator supplies an approval token from the local apply preflight. "
            "This applies the latest operator package draft through the guarded package-intake helper only; it "
            "returns changed-file, validation, rollback, and commit-gate reporting after apply; it never stages, "
            "commits, pushes, runs arbitrary shell commands, sends RIFT input, writes provider repos, or touches CE/x64dbg."
        ),
        read_only=False,
        destructive=False,
        open_world=False,
    ),
    "commit_reviewed_slice": ToolSpec(
        name="commit_reviewed_slice",
        title="Commit Reviewed Slice",
        description=(
            "Use this when the local operator supplies an approval token from the local commit preflight. "
            "This reruns commit preflight, stages only explicit validated paths, runs pre-commit for those files, "
            "and creates one local commit; it never pushes, rewrites branches, resets, cleans, applies packages, "
            "runs arbitrary shell commands, sends RIFT input, writes provider repos, or touches CE/x64dbg."
        ),
        read_only=False,
        destructive=False,
        open_world=False,
    ),
    "get_workflow_control_plan": ToolSpec(
        name="get_workflow_control_plan",
        title="Get Workflow Control Plan",
        description=(
            "Use this when ChatGPT needs the current safe repo workflow plan, bidirectional data-transfer steps, "
            "safe commit checklist, and gated action boundaries without shell execution, Git mutation, tunnel control, "
            "RIFT input, CE, x64dbg, or provider writes."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "get_dirty_paths": ToolSpec(
        name="get_dirty_paths",
        title="Get Dirty Git Paths",
        description=(
            "Use this when you need read-only Git worktree dirty-path status for RiftReader. "
            "This never stages, commits, pushes, rewrites branches, sends RIFT input, touches CE, or touches x64dbg."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "get_recent_commits": ToolSpec(
        name="get_recent_commits",
        title="Get Recent Git Commits",
        description=(
            "Use this when you need the latest local Git commits for RiftReader without relying on stale handoff memory. "
            "This is read-only and never stages, commits, pushes, rewrites branches, sends RIFT input, touches CE, or touches x64dbg."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "repo_tree_tracked": ToolSpec(
        name="repo_tree_tracked",
        title="List Tracked Repo Files",
        description=(
            "Use this when you need a bounded inventory of git-tracked RiftReader text files before coding. "
            "This reads tracked repo metadata only; it never reads ignored local artifacts, executes commands from user input, "
            "writes files, stages, commits, pushes, sends RIFT input, touches CE, or touches x64dbg."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "repo_search_tracked": ToolSpec(
        name="repo_search_tracked",
        title="Search Tracked Repo Files",
        description=(
            "Use this when you need bounded literal or regex search over git-tracked RiftReader text files. "
            "This excludes ignored/untracked/local artifacts and never exposes arbitrary filesystem search, shell execution, "
            "Git mutation, RIFT input, CE, or x64dbg."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "repo_read_tracked_file": ToolSpec(
        name="repo_read_tracked_file",
        title="Read One Tracked Repo File",
        description=(
            "Use this when you need bounded content from one git-tracked RiftReader text file. "
            "This rejects absolute paths, backslashes, traversal, secrets, binaries, ignored local artifacts, and untracked files."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "repo_read_many_tracked_files": ToolSpec(
        name="repo_read_many_tracked_files",
        title="Read Multiple Tracked Repo Files",
        description=(
            "Use this when you need bounded content from several git-tracked RiftReader text files. "
            "This enforces per-file, total-byte, and file-count caps and rejects secrets, binaries, local artifacts, and untracked files."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
    "repo_context_pack": ToolSpec(
        name="repo_context_pack",
        title="Read Tracked Repo Context Pack",
        description=(
            "Use this when you need a predefined bounded context pack of git-tracked RiftReader source, tests, and docs. "
            "This never accepts arbitrary filesystem roots and never reads ignored local artifacts or untracked files."
        ),
        read_only=True,
        destructive=False,
        open_world=False,
    ),
}


@dataclass
class AdapterConfig:
    repo_root: Path
    payload_root: Path
    audit_root: Path
    bridge_config: bridge.BridgeConfig
    dry_run_timeout_seconds: float = DEFAULT_DRY_RUN_TIMEOUT_SECONDS
    tool_profile: str = TOOL_PROFILE_FULL


class AdapterError(Exception):
    """Expected fail-closed adapter error."""

    def __init__(self, code: str, message: str, *, status: str = "blocked", extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def base_safety() -> dict[str, Any]:
    return {
        **safety_flags(),
        "noExistingMcpProxy": True,
        "noRiftGameMcpProxy": True,
        "noWindowsMcpProxy": True,
        "noArbitraryFilesystemRead": True,
        "noArbitraryFilesystemWrite": True,
        "noShellExecutionEndpoint": True,
        "noBroadGitMutationEndpoint": True,
        "gitMutationEndpointLimitedToCommitReviewedSlice": True,
        "noRemoteGitMutationEndpoint": True,
        "noBranchRewriteEndpoint": True,
        "noDestructiveGitCleanupEndpoint": True,
        "noRiftLiveInputEndpoint": True,
        "noTargetControlEndpoint": True,
        "noPersistentServerStartedByTool": True,
        "noTunnelStartedByTool": True,
        "chatGptOriginatedWritesLocalOnly": True,
        "absoluteRepoRootRedacted": True,
    }


def json_size_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def text_tail(value: str, max_chars: int = 4000) -> str:
    if len(value) <= max_chars:
        return value
    return value[-max_chars:]


def redact_repo_root_in_text(value: str, repo_root: Path) -> str:
    """Redact the absolute repo root from ChatGPT-facing tool payload text."""
    root = str(repo_root.resolve())
    variants = [root, root.replace("\\", "/")]
    redacted = value
    for variant in variants:
        if not variant:
            continue
        if redacted.lower() == variant.lower():
            return "."
        for separator in ("\\", "/"):
            prefix = variant + separator
            if redacted.lower().startswith(prefix.lower()):
                return redacted[len(prefix) :]
        # Handle embedded command arguments or diagnostic strings. Keep this
        # intentionally simple and deterministic: exact absolute root substrings
        # become "." while the rest of the string is preserved.
        redacted = re.sub(re.escape(variant), ".", redacted, flags=re.IGNORECASE)
    return redacted


def redact_repo_paths(value: Any, repo_root: Path) -> Any:
    if isinstance(value, dict):
        return {key: redact_repo_paths(item, repo_root) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_repo_paths(item, repo_root) for item in value]
    if isinstance(value, str):
        return redact_repo_root_in_text(value, repo_root)
    return value


def make_adapter_config(
    repo_root: Path | None = None,
    *,
    payload_root: Path = DEFAULT_PAYLOAD_ROOT,
    audit_root: Path = DEFAULT_AUDIT_ROOT,
    dry_run_timeout_seconds: float = DEFAULT_DRY_RUN_TIMEOUT_SECONDS,
    max_inbox_bytes: int = bridge.DEFAULT_MAX_INBOX_BYTES,
) -> AdapterConfig:
    root = repo_root.resolve() if repo_root is not None else find_repo_root(Path.cwd())
    if not (root / ".git").exists():
        raise AdapterError("REPO_ROOT_INVALID", f"Missing .git under repo root: {root}", status="failed")
    if not (root / "agents.md").is_file():
        raise AdapterError("REPO_POLICY_MISSING", f"Missing agents.md under repo root: {root}", status="failed")

    audit = audit_root if audit_root.is_absolute() else root / audit_root
    audit = audit.resolve()
    local_root = (root / ".riftreader-local").resolve()
    if not is_relative_to(audit, local_root):
        raise AdapterError(
            "AUDIT_ROOT_NOT_LOCAL",
            "MCP audit root must stay under .riftreader-local.",
            status="failed",
            extra={"auditRoot": str(audit)},
        )
    if dry_run_timeout_seconds <= 0 or dry_run_timeout_seconds > 1800:
        raise AdapterError("DRY_RUN_TIMEOUT_INVALID", "Dry-run timeout must be > 0 and <= 1800 seconds.", status="failed")

    bridge_config = bridge.make_config(
        repo_root=root,
        payload_root=payload_root,
        token=BRIDGE_TOKEN,
        max_inbox_bytes=max_inbox_bytes,
        log_requests=False,
    )
    return AdapterConfig(
        repo_root=root,
        payload_root=bridge_config.payload_root,
        audit_root=audit,
        bridge_config=bridge_config,
        dry_run_timeout_seconds=float(dry_run_timeout_seconds),
    )


def blocked_payload(code: str, message: str, *, kind: str, status: str = "blocked", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": kind,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": False,
        "code": code,
        "message": message,
        "blockers": [code],
        "warnings": [],
        "safety": base_safety(),
    }
    if extra:
        payload.update(extra)
    return payload


def ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdapterError("INVALID_ARGUMENT", f"{field_name} must be a JSON object.")
    return value


def model_to_plain_json(value: Any) -> Any:
    """Convert SDK/Pydantic model arguments into ordinary JSON containers."""
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return value.model_dump(mode="json", exclude_none=True)
    if hasattr(value, "dict") and callable(value.dict):
        return value.dict(exclude_none=True)
    if isinstance(value, dict):
        return {key: model_to_plain_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [model_to_plain_json(item) for item in value]
    return value


def bounded_timeout(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        raise AdapterError("INVALID_TIMEOUT", "timeoutSeconds must be a number when supplied, not a boolean.")
    if not isinstance(value, int | float):
        raise AdapterError("INVALID_TIMEOUT", "timeoutSeconds must be a number when supplied.")
    if value <= 0 or value > 1800:
        raise AdapterError("INVALID_TIMEOUT", "timeoutSeconds must be > 0 and <= 1800.")
    return float(value)


def optional_bool(value: Any, *, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise AdapterError("INVALID_BOOLEAN", f"{field_name} must be a boolean when supplied.")
    return value


def optional_str(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdapterError("INVALID_STRING", f"{field_name} must be a string when supplied.")
    stripped = value.strip()
    return stripped or None


def required_str(value: Any, *, field_name: str) -> str:
    text = optional_str(value, field_name=field_name)
    if text is None:
        raise AdapterError("INVALID_STRING", f"{field_name} is required and must be a non-empty string.")
    return text


def required_str_list(value: Any, *, field_name: str, max_items: int) -> list[str]:
    if not isinstance(value, list):
        raise AdapterError("INVALID_STRING_LIST", f"{field_name} must be a JSON array of strings.")
    if len(value) > max_items:
        raise AdapterError(
            "STRING_LIST_TOO_LARGE",
            f"{field_name} must contain at most {max_items} items.",
            extra={"fieldName": field_name, "maxItems": max_items, "actualItems": len(value)},
        )
    strings: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise AdapterError("INVALID_STRING_LIST", f"{field_name}[{index}] must be a non-empty string.")
        strings.append(item.strip())
    return strings


def bounded_int(
    value: Any,
    *,
    field_name: str,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdapterError("INVALID_INTEGER", f"{field_name} must be an integer when supplied.")
    if value < min_value or value > max_value:
        raise AdapterError(
            "INVALID_INTEGER",
            f"{field_name} must be between {min_value} and {max_value}.",
            extra={"fieldName": field_name, "minValue": min_value, "maxValue": max_value, "actualValue": value},
        )
    return value


def summarize_tool_input(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "submit_package_proposal":
        proposal = arguments.get("proposal")
        if isinstance(proposal, dict):
            payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
            files = payload.get("files") if isinstance(payload, dict) else None
            checks = payload.get("checks") if isinstance(payload, dict) else None
            try:
                proposal_size = json_size_bytes(proposal)
                proposal_json_serializable = True
            except (TypeError, ValueError):
                proposal_size = None
                proposal_json_serializable = False
            return {
                "proposalKind": proposal.get("kind"),
                "title": proposal.get("title"),
                "hasBody": isinstance(proposal.get("body"), str) and bool(str(proposal.get("body")).strip()),
                "fileCount": len(files) if isinstance(files, list) else None,
                "checkCount": len(checks) if isinstance(checks, list) else None,
                "jsonSizeBytes": proposal_size,
                "jsonSerializable": proposal_json_serializable,
            }
        return {"proposalType": type(proposal).__name__}
    return {
        key: value
        for key, value in arguments.items()
        if isinstance(value, str | int | float | bool | type(None))
    }


def validate_tool_arguments(tool_name: str, arguments: dict[str, Any], *, max_bytes: int) -> None:
    allowed_keys = TOOL_ARGUMENT_KEYS.get(tool_name)
    if allowed_keys is None:
        raise AdapterError("TOOL_ARGUMENT_POLICY_MISSING", f"No argument policy is configured for tool: {tool_name}", status="failed")
    unknown_keys = sorted(str(key) for key in arguments if key not in allowed_keys)
    if unknown_keys:
        raise AdapterError(
            "UNEXPECTED_TOOL_ARGUMENTS",
            "Tool arguments contained unsupported keys.",
            extra={"unexpectedKeys": unknown_keys, "allowedKeys": sorted(allowed_keys)},
        )
    try:
        actual_bytes = json_size_bytes(arguments)
    except (TypeError, ValueError) as exc:
        raise AdapterError(
            "TOOL_ARGUMENTS_NOT_JSON_SERIALIZABLE",
            f"Tool arguments must be JSON serializable: {type(exc).__name__}: {exc}",
        ) from exc
    if actual_bytes > max_bytes:
        raise AdapterError(
            "TOOL_ARGUMENTS_TOO_LARGE",
            "Tool arguments exceeded the MCP adapter byte limit.",
            extra={"maxBytes": max_bytes, "actualBytes": actual_bytes},
        )


def validate_tool_result_payload(tool_name: str, result: Any) -> list[str]:
    """Return contract blockers for a tool's structuredContent payload."""

    if not isinstance(result, dict):
        return [f"tool-result-not-object:{tool_name}:{type(result).__name__}"]
    blockers: list[str] = []
    if result.get("schemaVersion") != SCHEMA_VERSION:
        blockers.append(f"tool-result-schema-version-invalid:{tool_name}:{result.get('schemaVersion')!r}")
    kind = result.get("kind")
    if not isinstance(kind, str) or not kind.startswith("riftreader-chatgpt-mcp"):
        blockers.append(f"tool-result-kind-invalid:{tool_name}:{kind!r}")
    status = result.get("status")
    if not isinstance(status, str) or not status:
        blockers.append(f"tool-result-status-invalid:{tool_name}:{status!r}")
    if not isinstance(result.get("ok"), bool):
        blockers.append(f"tool-result-ok-not-boolean:{tool_name}:{result.get('ok')!r}")
    for list_field in ("blockers", "warnings", "errors"):
        value = result.get(list_field)
        if value is not None and (not isinstance(value, list) or any(not isinstance(item, str) for item in value)):
            blockers.append(f"tool-result-{list_field}-not-string-list:{tool_name}")
    safety = result.get("safety")
    if safety is not None and not isinstance(safety, dict):
        blockers.append(f"tool-result-safety-not-object:{tool_name}:{type(safety).__name__}")
    return blockers


def result_summary(result: dict[str, Any]) -> dict[str, Any]:
    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
    files = result.get("files") if isinstance(result.get("files"), dict) else {}
    draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
    return {
        "status": result.get("status"),
        "ok": result.get("ok"),
        "code": result.get("code"),
        "kind": result.get("kind"),
        "inboxId": result.get("inboxId"),
        "draftId": draft.get("draftId") or result.get("draftId"),
        "artifactPaths": artifacts,
        "files": files,
    }


class RiftReaderChatGptMcpAdapter:
    def __init__(self, config: AdapterConfig) -> None:
        self.config = config

    def audit_path(self) -> Path:
        date = utc_iso()[:10].replace("-", "")
        return self.config.audit_root / f"{date}.jsonl"

    def write_audit(self, tool_name: str, input_summary: dict[str, Any], result: dict[str, Any]) -> None:
        self.config.audit_root.mkdir(parents=True, exist_ok=True)
        event = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-audit-event",
            "timestampUtc": utc_iso(),
            "tool": tool_name,
            "inputSummary": input_summary,
            "resultSummary": result_summary(result),
            "safety": {
                "auditUnderDotRiftReaderLocal": is_relative_to(self.audit_path(), self.config.repo_root / ".riftreader-local"),
                "proposalContentLogged": False,
                "repoSourceMutatedByAudit": False,
            },
        }
        with self.audit_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if arguments is None:
            args: dict[str, Any] = {}
        elif isinstance(arguments, dict):
            args = arguments
        else:
            result = blocked_payload(
                "INVALID_ARGUMENTS",
                "MCP tool arguments must be a JSON object.",
                kind="riftreader-chatgpt-mcp-tool-result",
            )
            result = redact_repo_paths(result, self.config.repo_root)
            self.write_audit(tool_name, {"argumentsType": type(arguments).__name__}, result)
            return result
        if tool_name not in TOOL_SPECS:
            result = blocked_payload(
                "TOOL_NOT_EXPOSED",
                f"Tool is not exposed by {SERVER_NAME}: {tool_name}",
                kind="riftreader-chatgpt-mcp-tool-result",
            )
            result = redact_repo_paths(result, self.config.repo_root)
            self.write_audit(tool_name, summarize_tool_input(tool_name, args), result)
            return result
        if tool_name not in tool_order_for_profile(self.config.tool_profile):
            result = blocked_payload(
                "TOOL_NOT_EXPOSED_IN_PROFILE",
                f"Tool is not exposed by active profile {self.config.tool_profile}: {tool_name}",
                kind="riftreader-chatgpt-mcp-tool-result",
            )
            result = redact_repo_paths(result, self.config.repo_root)
            self.write_audit(tool_name, summarize_tool_input(tool_name, args), result)
            return result

        try:
            validate_tool_arguments(
                tool_name,
                args,
                max_bytes=self.config.bridge_config.max_inbox_bytes + TOOL_ARGUMENT_SIZE_OVERHEAD_BYTES,
            )
            dispatch: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
                "health": lambda _: self.health(),
                "get_repo_status": lambda _: self.get_repo_status(),
                "get_latest_handoff": lambda _: self.get_latest_handoff(),
                "get_workflow_control_summary": lambda _: self.get_workflow_control_summary(),
                "get_package_proposal_template": lambda _: self.get_package_proposal_template(),
                "submit_package_proposal": lambda call_args: self.submit_package_proposal(call_args.get("proposal")),
                "list_inbox": lambda _: self.list_inbox(),
                "create_package_draft_from_inbox": lambda call_args: self.create_package_draft_from_inbox(call_args.get("inboxId")),
                "review_latest_package_draft": lambda call_args: self.review_latest_package_draft(
                    operator_only=optional_bool(call_args.get("operatorOnly"), field_name="operatorOnly", default=True)
                ),
                "dry_run_latest_package_draft": lambda call_args: self.dry_run_latest_package_draft(
                    operator_only=optional_bool(call_args.get("operatorOnly"), field_name="operatorOnly", default=True),
                    timeout_seconds=bounded_timeout(call_args.get("timeoutSeconds"), self.config.dry_run_timeout_seconds),
                ),
                "apply_latest_package_draft": lambda call_args: self.apply_latest_package_draft(
                    operator_only=optional_bool(call_args.get("operatorOnly"), field_name="operatorOnly", default=True),
                    dry_run_summary_path=optional_str(call_args.get("dryRunSummaryPath"), field_name="dryRunSummaryPath"),
                    dry_run_diff_sha256=optional_str(call_args.get("dryRunDiffSha256"), field_name="dryRunDiffSha256"),
                    approval_token=optional_str(call_args.get("approvalToken"), field_name="approvalToken"),
                    timeout_seconds=bounded_timeout(call_args.get("timeoutSeconds"), self.config.dry_run_timeout_seconds),
                ),
                "commit_reviewed_slice": lambda call_args: self.commit_reviewed_slice(
                    expected_head=required_str(call_args.get("expectedHead"), field_name="expectedHead"),
                    paths=required_str_list(call_args.get("paths"), field_name="paths", max_items=20),
                    commit_message=required_str(call_args.get("commitMessage"), field_name="commitMessage"),
                    validation_summary_path=required_str(
                        call_args.get("validationSummaryPath"), field_name="validationSummaryPath"
                    ),
                    validation_digest=required_str(call_args.get("validationDigest"), field_name="validationDigest"),
                    approval_token=optional_str(call_args.get("approvalToken"), field_name="approvalToken"),
                    timeout_seconds=bounded_timeout(call_args.get("timeoutSeconds"), self.config.dry_run_timeout_seconds),
                ),
                "get_workflow_control_plan": lambda _: self.get_workflow_control_plan(),
                "get_dirty_paths": lambda _: self.get_dirty_paths(),
                "get_recent_commits": lambda call_args: self.get_recent_commits(call_args.get("limit")),
                "repo_tree_tracked": lambda call_args: self.repo_tree_tracked(
                    prefix=optional_str(call_args.get("prefix"), field_name="prefix"),
                    depth=bounded_int(call_args.get("depth"), field_name="depth", default=None, min_value=0, max_value=20)
                    if call_args.get("depth") is not None
                    else None,
                    limit=bounded_int(
                        call_args.get("limit"),
                        field_name="limit",
                        default=MCP_REPO_TREE_DEFAULT_LIMIT,
                        min_value=1,
                        max_value=MCP_REPO_TREE_MAX_LIMIT,
                    ),
                    include_blocked_meta=optional_bool(
                        call_args.get("includeBlockedMeta"), field_name="includeBlockedMeta", default=False
                    ),
                ),
                "repo_search_tracked": lambda call_args: self.repo_search_tracked(
                    query=required_str(call_args.get("query"), field_name="query"),
                    case_sensitive=optional_bool(
                        call_args.get("caseSensitive"), field_name="caseSensitive", default=False
                    ),
                    regex=optional_bool(call_args.get("regex"), field_name="regex", default=False),
                    max_matches=bounded_int(
                        call_args.get("maxMatches"),
                        field_name="maxMatches",
                        default=MCP_REPO_SEARCH_DEFAULT_MATCHES,
                        min_value=1,
                        max_value=MCP_REPO_SEARCH_MAX_MATCHES,
                    ),
                    max_file_bytes=bounded_int(
                        call_args.get("maxFileBytes"),
                        field_name="maxFileBytes",
                        default=MCP_REPO_READ_FILE_DEFAULT_BYTES,
                        min_value=1,
                        max_value=MCP_REPO_READ_FILE_MAX_BYTES,
                    ),
                ),
                "repo_read_tracked_file": lambda call_args: self.repo_read_tracked_file(
                    path=required_str(call_args.get("path"), field_name="path"),
                    max_bytes=bounded_int(
                        call_args.get("maxBytes"),
                        field_name="maxBytes",
                        default=MCP_REPO_READ_FILE_DEFAULT_BYTES,
                        min_value=1,
                        max_value=MCP_REPO_READ_FILE_MAX_BYTES,
                    ),
                    include_sha256=optional_bool(call_args.get("includeSha256"), field_name="includeSha256", default=False),
                ),
                "repo_read_many_tracked_files": lambda call_args: self.repo_read_many_tracked_files(
                    paths=required_str_list(
                        call_args.get("paths"),
                        field_name="paths",
                        max_items=MCP_REPO_READ_MANY_MAX_FILES,
                    ),
                    max_file_bytes=bounded_int(
                        call_args.get("maxFileBytes"),
                        field_name="maxFileBytes",
                        default=MCP_REPO_READ_FILE_DEFAULT_BYTES,
                        min_value=1,
                        max_value=MCP_REPO_READ_FILE_MAX_BYTES,
                    ),
                    max_total_bytes=bounded_int(
                        call_args.get("maxTotalBytes"),
                        field_name="maxTotalBytes",
                        default=MCP_REPO_READ_TOTAL_DEFAULT_BYTES,
                        min_value=1,
                        max_value=MCP_REPO_READ_TOTAL_MAX_BYTES,
                    ),
                    max_files=bounded_int(
                        call_args.get("maxFiles"),
                        field_name="maxFiles",
                        default=MCP_REPO_READ_MANY_MAX_FILES,
                        min_value=1,
                        max_value=MCP_REPO_READ_MANY_MAX_FILES,
                    ),
                ),
                "repo_context_pack": lambda call_args: self.repo_context_pack(
                    pack_name=required_str(call_args.get("packName"), field_name="packName"),
                    max_files=bounded_int(
                        call_args.get("maxFiles"),
                        field_name="maxFiles",
                        default=MCP_REPO_CONTEXT_PACK_DEFAULT_FILES,
                        min_value=1,
                        max_value=MCP_REPO_CONTEXT_PACK_MAX_FILES,
                    ),
                    max_file_bytes=bounded_int(
                        call_args.get("maxFileBytes"),
                        field_name="maxFileBytes",
                        default=MCP_REPO_READ_FILE_DEFAULT_BYTES,
                        min_value=1,
                        max_value=MCP_REPO_READ_FILE_MAX_BYTES,
                    ),
                    max_total_bytes=bounded_int(
                        call_args.get("maxTotalBytes"),
                        field_name="maxTotalBytes",
                        default=MCP_REPO_READ_TOTAL_DEFAULT_BYTES,
                        min_value=1,
                        max_value=MCP_REPO_READ_TOTAL_MAX_BYTES,
                    ),
                ),
            }
            result = dispatch[tool_name](args)
        except AdapterError as exc:
            result = blocked_payload(
                exc.code,
                exc.message,
                kind=f"riftreader-chatgpt-mcp-{tool_name}",
                status=exc.status,
                extra=exc.extra,
            )
        except bridge.BridgeError as exc:
            result = blocked_payload(
                exc.code,
                exc.message,
                kind=f"riftreader-chatgpt-mcp-{tool_name}",
                status="failed" if exc.status >= 500 else "blocked",
                extra={"bridgeStatus": exc.status},
            )
        except Exception as exc:  # noqa: BLE001 - fail closed and audit unexpected handler errors.
            result = blocked_payload(
                "UNEXPECTED_TOOL_ERROR",
                f"{type(exc).__name__}: {exc}",
                kind=f"riftreader-chatgpt-mcp-{tool_name}",
                status="failed",
            )

        result_blockers = validate_tool_result_payload(tool_name, result)
        if result_blockers:
            result = blocked_payload(
                "TOOL_RESULT_CONTRACT_INVALID",
                "Tool handler returned structuredContent that does not match the minimum ChatGPT MCP result contract.",
                kind=f"riftreader-chatgpt-mcp-{tool_name}",
                status="failed",
                extra={"contractBlockers": result_blockers},
            )
        result = redact_repo_paths(result, self.config.repo_root)
        self.write_audit(tool_name, summarize_tool_input(tool_name, args), result)
        return result

    def health(self) -> dict[str, Any]:
        tool_profile = self.config.tool_profile
        tool_order = tool_order_for_profile(tool_profile)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-health",
            "service": SERVER_NAME,
            "version": VERSION,
            "generatedAtUtc": utc_iso(),
            "status": "passed",
            "ok": True,
            "repoRoot": rel(self.config.repo_root, self.config.repo_root),
            "repoName": self.config.repo_root.name,
            "repoRootRelative": rel(self.config.repo_root, self.config.repo_root),
            "payloadRoot": rel(self.config.repo_root, self.config.payload_root),
            "auditRoot": rel(self.config.repo_root, self.config.audit_root),
            "toolProfile": tool_profile,
            "toolCount": len(tool_order),
            "tools": tool_manifest(tool_profile)["tools"],
            "chatGptToolFacade": {
                "expectedAvailableToolNames": list(tool_order),
                "packageProofToolOrder": list(PACKAGE_PROOF_TOOL_ORDER),
                "writeActionExpectation": (
                    "ChatGPT Developer Mode should expose these tools; tools with readOnlyHint=false are "
                    "write actions and should require user confirmation instead of disappearing."
                ),
                "ifToolUnavailable": (
                    "Refresh the rift-mcp app in ChatGPT Apps settings, verify all tools are enabled, "
                    "select Developer Mode/rift-mcp in the conversation, then explicitly ask ChatGPT to "
                    "call the named rift-mcp tool. Do not treat health.tools as a substitute for an actual call."
                ),
            },
            "safety": {
                **base_safety(),
                "auditUnderDotRiftReaderLocal": is_relative_to(self.config.audit_root, self.config.repo_root / ".riftreader-local"),
                "absoluteRepoRootExposed": False,
                "publicReadOnlyProfile": tool_profile == TOOL_PROFILE_PUBLIC_READ_ONLY,
                "writeLikeToolsExposed": any(not TOOL_SPECS[name].read_only for name in tool_order),
            },
            "warnings": [
                "ChatGPT Developer Mode requires an HTTPS-reachable /mcp endpoint; use a tunnel manually only when testing.",
                "Server-side audit logging writes sanitized metadata under .riftreader-local.",
            ],
            "blockers": [],
        }

    def get_repo_status(self) -> dict[str, Any]:
        packet = status_packet.build_status_packet(
            self.config.repo_root,
            commit_count=8,
            ref_count=8,
            run_coordinate_status=True,
            check_opencode=False,
            collect_git_state=True,
        )
        compact = status_packet.compact_summary(packet)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-repo-status",
            "generatedAtUtc": utc_iso(),
            "status": compact.get("status") or packet.get("status") or "unknown",
            "ok": not packet.get("errors"),
            "compact": compact,
            "blockers": list(packet.get("blockers") or []),
            "warnings": list(packet.get("warnings") or []),
            "errors": list(packet.get("errors") or []),
            "safety": {
                **base_safety(),
                "statusHelperUsed": "tools.riftreader_workflow.status_packet.build_status_packet",
                "gitMutation": False,
            },
        }

    def get_latest_handoff(self) -> dict[str, Any]:
        handoff_dir = (self.config.repo_root / "docs" / "handoffs").resolve()
        latest = status_packet.find_latest_handoff(self.config.repo_root, handoff_dir)
        if latest is None:
            return blocked_payload(
                "HANDOFF_NOT_FOUND",
                "No handoff markdown files exist under docs/handoffs.",
                kind="riftreader-chatgpt-mcp-latest-handoff",
                extra={"handoffDir": rel(self.config.repo_root, handoff_dir)},
            )
        resolved = latest.resolve()
        if not is_relative_to(resolved, handoff_dir) or resolved.suffix.lower() != ".md":
            return blocked_payload(
                "HANDOFF_PATH_BLOCKED",
                "Latest handoff path failed allowlist validation.",
                kind="riftreader-chatgpt-mcp-latest-handoff",
                extra={"path": str(resolved)},
            )
        size = resolved.stat().st_size
        if size > MAX_HANDOFF_BYTES:
            return blocked_payload(
                "HANDOFF_TOO_LARGE",
                f"Latest handoff exceeds {MAX_HANDOFF_BYTES} bytes.",
                kind="riftreader-chatgpt-mcp-latest-handoff",
                extra={"path": rel(self.config.repo_root, resolved), "sizeBytes": size},
            )
        text = resolved.read_text(encoding="utf-8")
        title = None
        for line in text.splitlines():
            if line.startswith("# "):
                title = line.lstrip("#").strip()
                break
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-latest-handoff",
            "generatedAtUtc": utc_iso(),
            "status": "passed",
            "ok": True,
            "path": rel(self.config.repo_root, resolved),
            "title": title,
            "sizeBytes": size,
            "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
            "text": text,
            "blockers": [],
            "warnings": [],
            "safety": {
                **base_safety(),
                "handoffDirAllowlisted": True,
                "arbitraryPathInputAccepted": False,
            },
        }

    def get_package_proposal_template(self) -> dict[str, Any]:
        schema = bridge.inbox_schema_payload(self.config.bridge_config)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-package-proposal-template",
            "generatedAtUtc": utc_iso(),
            "status": "passed",
            "ok": True,
            "template": schema.get("packageProposalTemplate"),
            "inboxSchema": schema,
            "blockers": [],
            "warnings": [],
            "safety": {
                **base_safety(),
                "source": "tools.riftreader_workflow.local_artifact_bridge.package_proposal_template",
            },
        }

    def validate_package_proposal_for_submit(self, proposal: Any) -> dict[str, Any]:
        proposal_object = ensure_mapping(proposal, "proposal")
        raw = bridge.json_bytes(proposal_object)
        if len(raw) > self.config.bridge_config.max_inbox_bytes:
            raise AdapterError(
                "PACKAGE_PROPOSAL_TOO_LARGE",
                "Package proposal exceeds max inbox byte limit.",
                extra={"maxInboxBytes": self.config.bridge_config.max_inbox_bytes, "actualBytes": len(raw)},
            )
        normalized = bridge.validate_inbox_message(proposal_object)
        if normalized.get("kind") != "package-proposal":
            raise AdapterError(
                "PACKAGE_PROPOSAL_KIND_REQUIRED",
                "submit_package_proposal accepts kind=package-proposal only.",
                extra={"actualKind": normalized.get("kind")},
            )
        payload = normalized.get("payload")
        if not isinstance(payload, dict):
            raise AdapterError("PACKAGE_PROPOSAL_PAYLOAD_REQUIRED", "package-proposal payload must be an object.")
        _files, file_blockers = bridge.normalize_package_draft_files(self.config.bridge_config, payload.get("files"))
        target_blockers: list[str] = []
        for index, item in enumerate(_files):
            try:
                package_manifest.validate_target_path(item.get("target"), f"file-{index}-target")
            except Exception as exc:  # noqa: BLE001 - convert target policy failures into MCP blockers.
                target_blockers.append(str(exc))
        file_blockers.extend(target_blockers)
        if file_blockers:
            raise AdapterError(
                "PACKAGE_PROPOSAL_FILES_INVALID",
                "package-proposal files failed package-draft validation.",
                extra={"blockers": file_blockers},
            )
        checks = payload.get("checks", [])
        if checks is None:
            checks = []
        if not isinstance(checks, list):
            raise AdapterError("PACKAGE_PROPOSAL_CHECKS_INVALID", "package-proposal checks must be a list when supplied.")
        check_blockers: list[str] = []
        for index, check in enumerate(checks):
            try:
                package_manifest.validate_check_definition(check, index)
            except Exception as exc:  # noqa: BLE001 - convert check policy failures into MCP blockers.
                check_blockers.append(str(exc))
        if check_blockers:
            raise AdapterError(
                "PACKAGE_PROPOSAL_CHECKS_INVALID",
                "package-proposal checks failed safety validation.",
                extra={"blockers": check_blockers},
            )
        return normalized

    def submit_package_proposal(self, proposal: Any) -> dict[str, Any]:
        normalized = self.validate_package_proposal_for_submit(proposal)
        raw_size = len(bridge.json_bytes(normalized))
        stored = bridge.store_inbox_message(self.config.bridge_config, normalized, raw_size)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-submit-package-proposal",
            "generatedAtUtc": utc_iso(),
            "status": stored.get("status"),
            "ok": bool(stored.get("ok")),
            "inboxId": stored.get("inboxId"),
            "duplicate": stored.get("duplicate"),
            "storedUnder": stored.get("storedUnder"),
            "files": stored.get("files"),
            "sha256": stored.get("sha256"),
            "receivedAtUtc": stored.get("receivedAtUtc"),
            "blockers": [],
            "warnings": ["duplicate-proposal-reused-existing-inbox-item"] if stored.get("duplicate") else [],
            "safety": {
                **base_safety(),
                "localInboxOnly": True,
                "noPackageDraftCreatedBySubmit": True,
                "noRepoTargetWrites": True,
                "bridgeSafety": stored.get("safety"),
            },
            "next": [
                "Review the inbox item locally with list_inbox or the Local Artifact Bridge inbox-read helpers.",
                "Convert to an inert package draft only through an explicit operator/Codex step.",
                "No apply, command execution, Git, RIFT, CE, x64dbg, or provider writes occurred.",
            ],
        }

    def list_inbox(self) -> dict[str, Any]:
        payload = bridge.inbox_index(self.config.bridge_config)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-list-inbox",
            "generatedAtUtc": utc_iso(),
            "status": "passed",
            "ok": True,
            "inbox": payload,
            "blockers": [],
            "warnings": list(payload.get("warnings") or []),
            "safety": {
                **base_safety(),
                "readInboxMetadataOnly": True,
            },
        }

    def create_package_draft_from_inbox(self, inbox_id: Any) -> dict[str, Any]:
        if not isinstance(inbox_id, str) or not inbox_id.strip():
            raise AdapterError("INBOX_ID_REQUIRED", "create_package_draft_from_inbox requires an explicit inboxId string.")
        inbox_id = bridge.validate_inbox_id(inbox_id.strip())
        payload = bridge.create_inbox_package_draft(self.config.bridge_config, inbox_id)
        draft_root = payload.get("draftRoot")
        if isinstance(draft_root, str):
            resolved_draft_root = (self.config.repo_root / draft_root).resolve()
            if not is_relative_to(resolved_draft_root, self.config.repo_root / ".riftreader-local"):
                return blocked_payload(
                    "PACKAGE_DRAFT_ROOT_NOT_LOCAL",
                    "Package draft root escaped .riftreader-local; blocking fail-closed.",
                    kind="riftreader-chatgpt-mcp-create-package-draft-from-inbox",
                    extra={"draftRoot": draft_root},
                )
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-create-package-draft-from-inbox",
            "generatedAtUtc": utc_iso(),
            "status": payload.get("status"),
            "ok": bool(payload.get("ok")),
            "inboxId": payload.get("inboxId"),
            "draftId": Path(str(payload.get("draftRoot"))).name if payload.get("draftRoot") else None,
            "draft": payload,
            "blockers": list(payload.get("blockers") or ([payload.get("code")] if payload.get("code") else [])),
            "warnings": list(payload.get("warnings") or []),
            "safety": {
                **base_safety(),
                "localPackageDraftOnly": True,
                "explicitInboxIdRequired": True,
                "applyFlagSent": False,
                "repoSourceMutationExpected": False,
                "checksExecuted": False,
                "bridgeSafety": payload.get("safety"),
            },
            "next": [
                "Review the inert package draft summary and manifest locally.",
                "Use review_latest_package_draft and dry_run_latest_package_draft for validation before any separate apply decision.",
                "No repo target files were modified, executed, staged, committed, pushed, or sent to RIFT.",
            ],
        }

    def review_latest_package_draft(self, *, operator_only: bool = True) -> dict[str, Any]:
        payload = package_draft_review.latest_package_draft(self.config.repo_root, operator_only=operator_only)
        draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-review-latest-package-draft",
            "generatedAtUtc": utc_iso(),
            "status": payload.get("status"),
            "ok": bool(payload.get("ok")),
            "operatorOnly": operator_only,
            "draftId": draft.get("draftId"),
            "draftReview": payload,
            "blockers": list(payload.get("blockers") or ([payload.get("code")] if payload.get("code") else [])),
            "warnings": list(payload.get("warnings") or []),
            "safety": {
                **base_safety(),
                "readOnlyReview": True,
                "packageDraftRoot": rel(self.config.repo_root, package_draft_review.draft_root(self.config.repo_root)),
            },
        }

    def dry_run_latest_package_draft(self, *, operator_only: bool = True, timeout_seconds: float | None = None) -> dict[str, Any]:
        timeout = timeout_seconds if timeout_seconds is not None else self.config.dry_run_timeout_seconds
        payload = cached_dry_run_payload_for_latest_draft(self.config.repo_root, operator_only=operator_only, timeout=timeout)
        if payload is None:
            payload = package_draft_review.dry_run_latest_package_draft(
                self.config.repo_root,
                timeout_seconds=timeout,
                operator_only=operator_only,
            )
        args = []
        command = payload.get("command") if isinstance(payload.get("command"), dict) else {}
        if isinstance(command.get("args"), list):
            args = [str(item) for item in command["args"]]
        if any(arg.strip().lower() == "--apply" or arg.strip().lower().startswith("--apply=") for arg in args):
            return blocked_payload(
                "DRY_RUN_APPLY_FLAG_BLOCKED",
                "package_draft_review attempted to pass --apply; blocking fail-closed.",
                kind="riftreader-chatgpt-mcp-dry-run-latest-package-draft",
                extra={"command": command},
            )
        compact_payload = compact_dry_run_payload(self.config.repo_root, payload)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-dry-run-latest-package-draft",
            "generatedAtUtc": utc_iso(),
            "status": payload.get("status"),
            "ok": bool(payload.get("ok")),
            "operatorOnly": operator_only,
            "timeoutSeconds": timeout,
            "draftId": compact_payload.get("draft", {}).get("draftId"),
            "dryRunSucceeded": bool(payload.get("ok")),
            "dryRun": compact_payload,
            "blockers": list(payload.get("blockers") or ([payload.get("code")] if payload.get("code") else [])),
            "warnings": list(payload.get("warnings") or []),
            "safety": {
                **base_safety(),
                "packageIntakeDryRunOnly": True,
                "applyFlagSent": False,
                "repoSourceMutationExpected": False,
            },
        }

    def apply_latest_package_draft(
        self,
        *,
        operator_only: bool = True,
        dry_run_summary_path: str | None = None,
        dry_run_diff_sha256: str | None = None,
        approval_token: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        timeout = timeout_seconds if timeout_seconds is not None else self.config.dry_run_timeout_seconds
        payload = package_draft_review.apply_latest_package_draft_bridge(
            self.config.repo_root,
            approval_token=approval_token,
            operator_only=operator_only,
            dry_run_summary_path=dry_run_summary_path,
            dry_run_diff_sha256=dry_run_diff_sha256,
            timeout_seconds=timeout,
        )
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-apply-latest-package-draft",
            "generatedAtUtc": utc_iso(),
            "status": payload.get("status"),
            "ok": bool(payload.get("ok")),
            "applied": bool(payload.get("applied")),
            "operatorOnly": operator_only,
            "draftId": (payload.get("preflight") or {}).get("approvalFacts", {}).get("draftId")
            if isinstance(payload.get("preflight"), dict)
            else None,
            "applyResult": payload,
            "blockers": list(payload.get("blockers") or []),
            "warnings": list(payload.get("warnings") or []),
            "safety": {
                **base_safety(),
                "applyFlagSent": bool((payload.get("safety") or {}).get("applyFlagSent")),
                "repoSourceMutationExpected": bool((payload.get("safety") or {}).get("repoSourceMutationExpected")),
                "gitMutation": False,
                "providerWrites": False,
                "inputSent": False,
                "movementSent": False,
                "x64dbgAttach": False,
                "noCheatEngine": True,
            },
        }

    def commit_reviewed_slice(
        self,
        *,
        expected_head: str,
        paths: list[str],
        commit_message: str,
        validation_summary_path: str,
        validation_digest: str,
        approval_token: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        timeout = timeout_seconds if timeout_seconds is not None else self.config.dry_run_timeout_seconds
        payload = commit_reviewed_slice.commit_reviewed_slice_apply(
            self.config.repo_root,
            expected_head=expected_head,
            paths=paths,
            commit_message=commit_message,
            validation_summary_path=validation_summary_path,
            validation_digest=validation_digest,
            approval_token=approval_token,
            timeout_seconds=timeout,
        )
        payload_safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-commit-reviewed-slice",
            "generatedAtUtc": utc_iso(),
            "status": payload.get("status"),
            "ok": bool(payload.get("ok")),
            "committed": bool(payload.get("committed")),
            "commitHash": payload.get("commitHash"),
            "preHead": payload.get("preHead"),
            "postHead": payload.get("postHead"),
            "commitResult": payload,
            "blockers": list(payload.get("blockers") or []),
            "warnings": list(payload.get("warnings") or []),
            "safety": {
                **base_safety(),
                "gitMutation": bool(payload_safety.get("gitMutation")),
                "localCommitOnly": bool(payload_safety.get("localCommitOnly")),
                "remoteMutation": bool(payload_safety.get("remoteMutation")),
                "branchRewrite": bool(payload_safety.get("branchRewrite")),
                "destructiveCleanup": bool(payload_safety.get("destructiveCleanup")),
                "explicitPathsOnly": payload_safety.get("explicitPathsOnly") is not False,
                "stagedFiles": bool(payload_safety.get("stagedFiles")),
                "committed": bool(payload_safety.get("committed")),
                "pushed": bool(payload_safety.get("pushed")),
                "providerWrites": False,
                "inputSent": False,
                "movementSent": False,
                "x64dbgAttach": False,
                "noCheatEngine": True,
                "applyFlagSent": False,
            },
        }

    def get_workflow_control_summary(self) -> dict[str, Any]:
        """Return the smallest read-only workflow-control packet for ChatGPT MCP transport."""

        safe_read_sequence = [
            "health",
            "get_repo_status",
            "get_latest_handoff",
            "get_workflow_control_summary",
        ]
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-workflow-control-summary",
            "generatedAtUtc": utc_iso(),
            "status": "passed",
            "ok": True,
            "controlMode": "summary-only",
            "responseCompaction": {
                "status": "minimal",
                "reason": "Dedicated fallback for MCP clients that time out on the full workflow-control plan.",
                "minifiedBytesTarget": WORKFLOW_CONTROL_SUMMARY_MINIFIED_BYTES_TARGET,
                "fullPlanTool": "get_workflow_control_plan",
            },
            "currentProduct": {
                "service": SERVER_NAME,
                "version": VERSION,
                "toolCount": len(EXPECTED_TOOL_ORDER),
                "currentStage": FULL_PRODUCT_STAGE_PLAN["currentStage"],
                "currentStageName": FULL_PRODUCT_STAGE_PLAN["currentStageName"],
                "nextStage": FULL_PRODUCT_STAGE_PLAN["nextStage"],
                "nextStageName": FULL_PRODUCT_STAGE_PLAN["nextStageName"],
                "primaryProofPath": "cloudflare-named-tunnel-server-url-no-auth",
                "readiness": "blocked-on-fresh-actual-chatgpt-web-desktop-proof",
            },
            "safeReadSequence": safe_read_sequence,
            "proofRunPacket": {
                "cli": "scripts\\riftreader-mcp-mission-control.cmd --proof-run-packet-md",
                "serverUrl": "https://mcp.360madden.com/mcp",
                "auth": "No Authentication",
                "connectionMode": "cloudflare-named-tunnel",
            },
            "transportFallback": {
                "ifFullPlanTimesOut": (
                    "Use this summary plus get_repo_status and get_latest_handoff instead of "
                    "get_workflow_control_plan."
                ),
                "localCliSmokeCommand": (
                    "python tools\\riftreader_workflow\\riftreader_chatgpt_mcp.py "
                    "--call get_workflow_control_summary --json"
                ),
            },
            "gatedActions": [
                "apply-package-to-repo",
                "commit-local-slice",
                "git-push",
                "bounded-shell-command",
                "live-rift-input-or-movement",
                "x64dbg-or-cheat-engine",
                "proof-promotion-or-current-truth-update",
            ],
            "recommendedNextAction": (
                "First call health, get_repo_status, and get_latest_handoff; call get_workflow_control_plan only "
                "when larger plan detail is needed and the MCP transport is stable."
            ),
            "actualClientProofRecovery": {
                "status": "if-package-tools-unavailable-refresh-app-and-select-developer-mode-rift-mcp",
                "packageProofToolOrder": list(PACKAGE_PROOF_TOOL_ORDER),
                "operatorPrompt": (
                    "Use only rift-mcp. Call the packageProofToolOrder tools in order; call "
                    "apply_latest_package_draft without approvalToken to prove APPLY_APPROVAL_MISSING."
                ),
            },
            "blockers": [],
            "warnings": [
                "Summary omits Mission Control and safe-commit detail by design; use get_workflow_control_plan for full detail.",
            ],
            "safety": {
                **compact_workflow_safety(base_safety()),
                "readOnlyControlSummary": True,
                "planOnly": True,
                "shellExecutionEndpoint": False,
                "gitMutation": False,
                "tunnelControl": False,
            },
        }

    def get_workflow_control_plan(self) -> dict[str, Any]:
        mission_payload = mcp_mission_control.mission_control(self.config.repo_root)
        commit_plan = safe_commit_packager.safe_commit_plan(self.config.repo_root)
        final_status = mission_payload.get("finalStatus") if isinstance(mission_payload.get("finalStatus"), dict) else {}
        operator_next = mission_payload.get("operatorNextAction") if isinstance(mission_payload.get("operatorNextAction"), dict) else {}
        mission_blockers = mission_payload.get("blockers") if isinstance(mission_payload.get("blockers"), list) else []
        mission_warnings = mission_payload.get("warnings") if isinstance(mission_payload.get("warnings"), list) else []
        safe_commit = compact_safe_commit_plan(commit_plan)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-workflow-control-plan",
            "generatedAtUtc": utc_iso(),
            "status": "passed",
            "ok": True,
            "controlMode": "plan-only",
            "responseCompaction": {
                "status": "compact",
                "reason": "Keep ChatGPT Web/Desktop MCP responses small enough for reliable tool transport.",
                "listLimit": WORKFLOW_CONTROL_LIST_LIMIT,
                "minifiedBytesTarget": WORKFLOW_CONTROL_MINIFIED_BYTES_TARGET,
                "localCliSmokeCommand": "python tools\\riftreader_workflow\\riftreader_chatgpt_mcp.py --call get_workflow_control_plan --json",
            },
            "bidirectionalDataTransfer": {
                "readFromRepo": [
                    "health",
                    "get_repo_status",
                    "get_latest_handoff",
                    "get_workflow_control_summary",
                    "get_workflow_control_plan",
                    "get_package_proposal_template",
                    "list_inbox",
                    "review_latest_package_draft",
                ],
                "writeToLocalInbox": ["submit_package_proposal"],
                "draftLocalPackage": ["create_package_draft_from_inbox"],
                "validateLocalDraft": ["review_latest_package_draft", "dry_run_latest_package_draft"],
                "applyApprovedDraft": ["apply_latest_package_draft"],
                "commitApprovedSlice": ["commit_reviewed_slice"],
                "writeBoundary": (
                    "ChatGPT-originated proposal writes are stored only under .riftreader-local inbox/package-draft "
                    "artifacts until apply_latest_package_draft receives a local preflight approval token; local Git commits "
                    "are limited to commit_reviewed_slice after a current commit-preflight approval token."
                ),
            },
            "missionControl": {
                "status": mission_payload.get("status"),
                "ok": mission_payload.get("ok"),
                "operatorNextAction": operator_next,
                "finalStatus": compact_final_status(final_status),
                "finalProductProgress": compact_final_product_progress(mission_payload.get("finalProductProgress")),
                "warningCount": len(mission_warnings),
                "blockerCount": len(mission_blockers),
            },
            "safeCommitPlan": safe_commit,
            "fullProductStagePlan": compact_stage_plan(FULL_PRODUCT_STAGE_PLAN),
            "futureCapabilityRoadmap": compact_future_capability_roadmap(list(FUTURE_CAPABILITY_ROADMAP)),
            "futureToolContracts": {
                "apply_latest_package_draft": compact_apply_tool_contract(APPLY_TOOL_DESIGN_CONTRACT),
                "push_current_branch": compact_push_tool_contract(PUSH_TOOL_DESIGN_CONTRACT),
            },
            "futureCapabilityPolicy": {
                "status": "push-design-complete-preflight-next",
                "defaultDevelopmentOrder": [
                    "apply-package-to-repo",
                    "commit-local-slice",
                    "push-current-branch",
                    "bounded-shell-command",
                    "live-rift-control",
                    "debugger-or-ce-assist",
                ],
            },
            "gatedActions": [
                "apply-package-to-repo",
                "commit-local-slice",
                "git-push",
                "git-branch-rewrite",
                "bounded-shell-command",
                "tunnel-client-init-doctor-run-with-real-credentials",
                "chatgpt-connector-registration",
                "live-rift-input-or-movement",
                "x64dbg-or-cheat-engine",
                "provider-repo-writes",
                "proof-promotion-or-current-truth-update",
            ],
            "blockers": [],
            "warnings": [],
            "safety": {
                **compact_workflow_safety(base_safety()),
                "readOnlyControlPlan": True,
                "planOnly": True,
                "shellExecutionEndpoint": False,
                "gitMutation": False,
                "tunnelControl": False,
            },
        }


    def load_git_state_reader_module(self) -> Any:
        import importlib.util

        helper_path = self.config.repo_root / "tools" / "riftreader_workflow" / "git_state_reader.py"
        spec = importlib.util.spec_from_file_location("riftreader_phase1b_git_state_reader", helper_path)
        if spec is None or spec.loader is None:
            raise AdapterError(
                "GIT_STATE_READER_LOAD_FAILED",
                f"Could not load Git state reader helper: {helper_path}",
                status="failed",
            )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def get_dirty_paths(self) -> dict[str, Any]:
        git_state_reader = self.load_git_state_reader_module()

        payload = git_state_reader.get_dirty_paths(self.config.repo_root, 30.0)
        payload["kind"] = "riftreader-chatgpt-mcp-dirty-paths"
        payload["safety"] = {**base_safety(), **payload.get("safety", {})}
        return payload

    def get_recent_commits(self, limit: Any = None) -> dict[str, Any]:
        git_state_reader = self.load_git_state_reader_module()

        try:
            safe_limit = 10 if limit is None else int(limit)
        except (TypeError, ValueError):
            safe_limit = 10
        payload = git_state_reader.get_recent_commits(self.config.repo_root, safe_limit, 30.0)
        payload["kind"] = "riftreader-chatgpt-mcp-recent-commits"
        payload["safety"] = {**base_safety(), **payload.get("safety", {})}
        return payload

    def tracked_repo_context_payload(self, payload: dict[str, Any], *, kind: str) -> dict[str, Any]:
        payload = dict(payload)
        payload["schemaVersion"] = SCHEMA_VERSION
        payload["kind"] = kind
        payload["safety"] = {
            **base_safety(),
            "repoContextReadOnly": True,
            "gitTrackedFilesOnly": True,
            "ignoredAndUntrackedFilesBlocked": True,
            "secretLikePathsBlocked": True,
            "binaryFilesBlocked": True,
            **payload.get("safety", {}),
        }
        return payload

    def repo_tree_tracked(
        self,
        *,
        prefix: str | None,
        depth: int | None,
        limit: int,
        include_blocked_meta: bool,
    ) -> dict[str, Any]:
        payload = tracked_repo_context.repo_tree_tracked(
            repo_root=self.config.repo_root,
            prefix=prefix,
            depth=depth,
            limit=limit,
            include_blocked_meta=include_blocked_meta,
        )
        return self.tracked_repo_context_payload(payload, kind="riftreader-chatgpt-mcp-repo-tree-tracked")

    def repo_search_tracked(
        self,
        *,
        query: str,
        case_sensitive: bool,
        regex: bool,
        max_matches: int,
        max_file_bytes: int,
    ) -> dict[str, Any]:
        payload = tracked_repo_context.repo_search_tracked(
            query,
            repo_root=self.config.repo_root,
            case_sensitive=case_sensitive,
            regex=regex,
            max_matches=max_matches,
            max_file_bytes=max_file_bytes,
        )
        return self.tracked_repo_context_payload(payload, kind="riftreader-chatgpt-mcp-repo-search-tracked")

    def repo_read_tracked_file(
        self,
        *,
        path: str,
        max_bytes: int,
        include_sha256: bool,
    ) -> dict[str, Any]:
        payload = tracked_repo_context.repo_read_tracked_file(
            path,
            repo_root=self.config.repo_root,
            max_bytes=max_bytes,
            include_sha256=include_sha256,
        )
        return self.tracked_repo_context_payload(payload, kind="riftreader-chatgpt-mcp-repo-read-tracked-file")

    def repo_read_many_tracked_files(
        self,
        *,
        paths: list[str],
        max_file_bytes: int,
        max_total_bytes: int,
        max_files: int,
    ) -> dict[str, Any]:
        payload = tracked_repo_context.repo_read_many_tracked_files(
            paths,
            repo_root=self.config.repo_root,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            max_files=max_files,
        )
        return self.tracked_repo_context_payload(payload, kind="riftreader-chatgpt-mcp-repo-read-many-tracked-files")

    def repo_context_pack(
        self,
        *,
        pack_name: str,
        max_files: int,
        max_file_bytes: int,
        max_total_bytes: int,
    ) -> dict[str, Any]:
        payload = tracked_repo_context.repo_context_pack(
            pack_name,
            repo_root=self.config.repo_root,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )
        return self.tracked_repo_context_payload(payload, kind="riftreader-chatgpt-mcp-repo-context-pack")

def cached_dry_run_payload_for_latest_draft(
    repo_root: Path,
    *,
    operator_only: bool,
    timeout: float,
) -> dict[str, Any] | None:
    """Return a prior passing dry-run for the same latest draft, if one exists.

    ChatGPT's MCP client can time out on local package-intake subprocess calls
    through a temporary tunnel. Reusing a fresh repo-local dry-run artifact keeps
    the actual ChatGPT proof path small while still requiring a real prior
    package-intake dry-run for the same inert package draft.
    """
    latest_payload = package_draft_review.latest_package_draft(repo_root, operator_only=operator_only)
    if not latest_payload.get("ok"):
        return None
    draft = latest_payload.get("draft") if isinstance(latest_payload.get("draft"), dict) else {}
    package_root_value = draft.get("packageRoot")
    if not package_root_value:
        return None
    package_root = (repo_root / str(package_root_value)).resolve()
    try:
        package_latest_mtime = max(path.stat().st_mtime for path in package_root.rglob("*") if path.is_file())
    except (OSError, ValueError):
        package_latest_mtime = package_root.stat().st_mtime if package_root.exists() else 0.0
    intake_root = repo_root / ".riftreader-local" / "package-intake"
    if not intake_root.is_dir():
        return None
    candidates = sorted(
        intake_root.glob("*/compact-package-intake-summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            summary = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summary_package_root = summary.get("packageRoot") or summary.get("packagePath")
        if not summary_package_root:
            continue
        try:
            summary_root_path = Path(str(summary_package_root))
            summary_root = (
                summary_root_path.resolve()
                if summary_root_path.is_absolute()
                else (repo_root / summary_root_path).resolve()
            )
        except OSError:
            continue
        if summary_root != package_root:
            continue
        try:
            if candidate.stat().st_mtime < package_latest_mtime:
                continue
        except OSError:
            continue
        if summary.get("status") != "passed" or summary.get("dryRun") is not True:
            continue
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-package-draft-review-dry-run-cached",
            "generatedAtUtc": utc_iso(),
            "status": "passed",
            "ok": True,
            "exitCode": 0,
            "draft": draft,
            "command": {
                "args": [
                    "cached-dry-run-artifact",
                    rel(repo_root, candidate),
                ],
                "timeoutSeconds": timeout,
                "applyFlagSent": False,
                "dryRunOnly": True,
                "operatorOnly": operator_only,
                "cached": True,
            },
            "commandEnvelope": {
                "label": "cached-latest-package-draft-intake-dry-run",
                "exitCode": 0,
                "ok": True,
                "timedOut": False,
                "durationSeconds": 0.0,
                "cached": True,
            },
            "intakeCompactSummary": summary,
            "blockers": [],
            "warnings": ["cached-dry-run-artifact-reused"],
            "errors": [],
            "safety": {
                **latest_payload["safety"],
                "packageIntakeInvoked": False,
                "cachedDryRunArtifact": True,
                "applyFlagSent": False,
                "dryRunOnly": True,
            },
            "next": [
                "Review the cached package intake compact summary and diff artifact.",
                "Do not apply, stage, commit, or push unless explicitly approved in a separate step.",
            ],
        }
    return None


def dry_run_diff_preview(repo_root: Path, intake_summary: dict[str, Any]) -> dict[str, Any]:
    """Return a bounded, repo-local package-intake diff preview for ChatGPT review."""
    artifacts = intake_summary.get("artifacts") if isinstance(intake_summary.get("artifacts"), dict) else {}
    diff_value = artifacts.get("diff")
    preview_base = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-package-diff-preview",
        "maxBytes": MAX_DRY_RUN_DIFF_PREVIEW_BYTES,
        "safety": {
            **base_safety(),
            "readOnlyPreview": True,
            "diffArtifactUnderPackageIntake": False,
            "boundedBytes": True,
            "repoSourceMutationExpected": False,
            "applyFlagSent": False,
        },
    }
    if not isinstance(diff_value, str) or not diff_value.strip():
        return {
            **preview_base,
            "status": "unavailable",
            "ok": False,
            "code": "DIFF_ARTIFACT_MISSING",
            "blockers": [],
            "warnings": ["package-intake-diff-artifact-missing"],
        }
    try:
        diff_path = Path(diff_value)
        resolved = diff_path.resolve() if diff_path.is_absolute() else (repo_root / diff_path).resolve()
    except OSError as exc:
        return {
            **preview_base,
            "status": "blocked",
            "ok": False,
            "code": "DIFF_ARTIFACT_PATH_INVALID",
            "artifactPath": "<invalid-diff-artifact-path>",
            "blockers": [f"diff-artifact-path-invalid:{type(exc).__name__}"],
            "warnings": [],
        }
    intake_root = (repo_root / ".riftreader-local" / "package-intake").resolve()
    if not is_relative_to(resolved, intake_root):
        return {
            **preview_base,
            "status": "blocked",
            "ok": False,
            "code": "DIFF_ARTIFACT_OUTSIDE_PACKAGE_INTAKE",
            "artifactPath": "<outside-package-intake>",
            "blockers": ["diff-artifact-outside-package-intake"],
            "warnings": [],
        }
    if resolved.name != "package.diff":
        return {
            **preview_base,
            "status": "blocked",
            "ok": False,
            "code": "DIFF_ARTIFACT_UNEXPECTED_NAME",
            "artifactPath": rel(repo_root, resolved),
            "blockers": ["diff-artifact-unexpected-name"],
            "warnings": [],
        }
    if not resolved.is_file():
        return {
            **preview_base,
            "status": "unavailable",
            "ok": False,
            "code": "DIFF_ARTIFACT_NOT_FOUND",
            "artifactPath": rel(repo_root, resolved),
            "blockers": [],
            "warnings": ["package-intake-diff-artifact-not-found"],
            "safety": {**preview_base["safety"], "diffArtifactUnderPackageIntake": True},
        }
    try:
        size_bytes = resolved.stat().st_size
        with resolved.open("rb") as handle:
            raw = handle.read(MAX_DRY_RUN_DIFF_PREVIEW_BYTES + 1)
    except OSError as exc:
        return {
            **preview_base,
            "status": "blocked",
            "ok": False,
            "code": "DIFF_ARTIFACT_READ_FAILED",
            "artifactPath": rel(repo_root, resolved),
            "blockers": [f"diff-artifact-read-failed:{type(exc).__name__}"],
            "warnings": [],
            "safety": {**preview_base["safety"], "diffArtifactUnderPackageIntake": True},
        }
    truncated = len(raw) > MAX_DRY_RUN_DIFF_PREVIEW_BYTES
    if truncated:
        raw = raw[:MAX_DRY_RUN_DIFF_PREVIEW_BYTES]
    text = raw.decode("utf-8", errors="replace")
    return {
        **preview_base,
        "status": "ready",
        "ok": True,
        "artifactPath": rel(repo_root, resolved),
        "sizeBytes": size_bytes,
        "truncated": truncated or size_bytes > MAX_DRY_RUN_DIFF_PREVIEW_BYTES,
        "text": text,
        "blockers": [],
        "warnings": ["package-intake-diff-preview-truncated"] if truncated or size_bytes > MAX_DRY_RUN_DIFF_PREVIEW_BYTES else [],
        "safety": {**preview_base["safety"], "diffArtifactUnderPackageIntake": True},
    }


def compact_dry_run_payload(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a ChatGPT-safe dry-run summary without large command stdout blobs."""
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    intake = payload.get("intakeCompactSummary") if isinstance(payload.get("intakeCompactSummary"), dict) else {}
    command = payload.get("command") if isinstance(payload.get("command"), dict) else {}
    command_envelope = payload.get("commandEnvelope") if isinstance(payload.get("commandEnvelope"), dict) else {}
    compact_envelope = {
        key: command_envelope.get(key)
        for key in ("label", "exitCode", "ok", "timedOut", "durationSeconds", "startedAtUtc", "endedAtUtc")
        if key in command_envelope
    }
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "kind": payload.get("kind"),
        "generatedAtUtc": payload.get("generatedAtUtc"),
        "status": payload.get("status"),
        "ok": bool(payload.get("ok")),
        "exitCode": payload.get("exitCode"),
        "command": command,
        "commandEnvelope": compact_envelope,
        "draft": {
            key: draft.get(key)
            for key in (
                "draftId",
                "inboxId",
                "status",
                "ok",
                "origin",
                "selfTest",
                "messageTitle",
                "packageName",
                "fileCount",
                "summaryPath",
                "manifestPath",
                "packageRoot",
                "reviewReady",
            )
            if key in draft
        },
        "intakeCompactSummary": {
            key: intake.get(key)
            for key in (
                "schemaVersion",
                "kind",
                "generatedAtUtc",
                "status",
                "dryRun",
                "changedFiles",
                "changedFileCount",
                "checks",
                "blockers",
                "warnings",
                "errors",
                "artifacts",
                "safety",
            )
            if key in intake
        },
        "diffPreview": dry_run_diff_preview(repo_root, intake) if intake else None,
        "blockers": list(payload.get("blockers") or []),
        "warnings": list(payload.get("warnings") or []),
        "errors": list(payload.get("errors") or []),
        "safety": payload.get("safety") if isinstance(payload.get("safety"), dict) else {},
    }


def tool_manifest(tool_profile: str = TOOL_PROFILE_FULL) -> dict[str, Any]:
    tool_order = tool_order_for_profile(tool_profile)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-tool-manifest",
        "service": SERVER_NAME,
        "version": VERSION,
        "toolProfile": tool_profile,
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "ok": True,
        "tools": [
            {
                "name": TOOL_SPECS[name].name,
                "title": TOOL_SPECS[name].title,
                "description": TOOL_SPECS[name].description,
                "allowedArgumentKeys": sorted(TOOL_ARGUMENT_KEYS[name]),
                "annotations": TOOL_SPECS[name].annotation_payload(),
                "outputSchema": tool_output_schema(name),
            }
            for name in tool_order
        ],
        "safety": {
            **base_safety(),
            "publicReadOnlyProfile": tool_profile == TOOL_PROFILE_PUBLIC_READ_ONLY,
            "writeLikeToolsExposed": any(not TOOL_SPECS[name].read_only for name in tool_order),
        },
    }


def tool_output_schema(tool_name: str) -> dict[str, Any]:
    """Return the minimum structuredContent contract all ChatGPT MCP tools expose."""

    return {
        "type": "object",
        "additionalProperties": True,
        "required": ["schemaVersion", "kind", "status", "ok"],
        "properties": {
            "schemaVersion": {"type": "integer", "const": SCHEMA_VERSION},
            "kind": {"type": "string", "pattern": "^riftreader-chatgpt-mcp.*"},
            "status": {"type": "string"},
            "ok": {"type": "boolean"},
            "blockers": {"type": "array", "items": {"type": "string"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "errors": {"type": "array", "items": {"type": "string"}},
            "safety": {"type": "object", "additionalProperties": True},
        },
    }


def self_test_package_proposal() -> dict[str, Any]:
    proposal = bridge.package_proposal_template()
    proposal["title"] = "RiftReader ChatGPT MCP self-test package proposal"
    proposal["body"] = "Synthetic self-test proposal stored only under .riftreader-local."
    proposal["payload"]["packageName"] = "RiftReader ChatGPT MCP self-test"
    proposal["payload"]["files"] = [
        {
            "target": "docs/workflow/riftreader-chatgpt-mcp-selftest-preview.md",
            "content": "# RiftReader ChatGPT MCP Self-Test Preview\n\nThis file is never applied by the MCP self-test.\n",
            "encoding": "utf-8",
        }
    ]
    proposal["payload"]["checks"] = [
        {
            "name": "compile-chatgpt-mcp",
            "args": [sys.executable, "-m", "py_compile", "tools/riftreader_workflow/riftreader_chatgpt_mcp.py"],
            "expectedExitCodes": [0],
            "timeoutSeconds": 120,
        }
    ]
    proposal["metadata"] = {
        "requiresHumanReview": True,
        "draftOnly": True,
        "selfTest": True,
    }
    proposal["source"] = {
        "tool": "riftreader_chatgpt_mcp self-test",
        "context": "local self-test without ChatGPT or public tunnel",
    }
    return proposal


def run_self_test(config: AdapterConfig) -> dict[str, Any]:
    adapter = RiftReaderChatGptMcpAdapter(config)
    stages: dict[str, Any] = {}
    blockers: list[str] = []

    for tool_name, args in (
        ("health", {}),
        ("get_repo_status", {}),
        ("get_latest_handoff", {}),
        ("get_package_proposal_template", {}),
    ):
        stages[tool_name] = adapter.call_tool(tool_name, args)
        if stages[tool_name].get("status") == "failed":
            blockers.append(f"{tool_name}:failed")

    proposal_result = adapter.call_tool("submit_package_proposal", {"proposal": self_test_package_proposal()})
    stages["submit_package_proposal"] = proposal_result
    if not proposal_result.get("ok"):
        blockers.append(f"submit_package_proposal:{proposal_result.get('code') or proposal_result.get('status')}")

    stages["list_inbox"] = adapter.call_tool("list_inbox", {})
    inbox_id = proposal_result.get("inboxId") if isinstance(proposal_result.get("inboxId"), str) else None
    if inbox_id:
        stages["create_package_draft_from_inbox"] = adapter.call_tool("create_package_draft_from_inbox", {"inboxId": inbox_id})
        if not stages["create_package_draft_from_inbox"].get("ok"):
            blockers.append(
                "create_package_draft_from_inbox:"
                f"{stages['create_package_draft_from_inbox'].get('code') or stages['create_package_draft_from_inbox'].get('status')}"
            )

    stages["review_latest_package_draft"] = adapter.call_tool("review_latest_package_draft", {"operatorOnly": False})
    stages["dry_run_latest_package_draft"] = adapter.call_tool(
        "dry_run_latest_package_draft",
        {"operatorOnly": False, "timeoutSeconds": config.dry_run_timeout_seconds},
    )
    if not stages["review_latest_package_draft"].get("ok"):
        blockers.append(
            "review_latest_package_draft:"
            f"{stages['review_latest_package_draft'].get('code') or stages['review_latest_package_draft'].get('status')}"
        )
    if not stages["dry_run_latest_package_draft"].get("ok"):
        blockers.append(
            "dry_run_latest_package_draft:"
            f"{stages['dry_run_latest_package_draft'].get('code') or stages['dry_run_latest_package_draft'].get('status')}"
        )

    status = "passed" if not blockers else "failed"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-self-test",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": not blockers,
        "blockers": blockers,
        "warnings": [
            "Self-test creates ignored .riftreader-local inbox/draft/audit artifacts only.",
            "No persistent server, HTTPS tunnel, apply, Git, RIFT, CE, or x64dbg action is started.",
        ],
        "stages": stages,
        "safety": {
            **base_safety(),
            "selfTestLocalOnly": True,
            "applyFlagSent": False,
            "serverStarted": False,
            "tunnelStarted": False,
        },
        "artifacts": {
            "auditRoot": rel(config.repo_root, config.audit_root),
            "auditLatest": rel(config.repo_root, adapter.audit_path()),
        },
    }


def actual_tool_annotation_payload(tool: Any) -> dict[str, bool | None]:
    annotations = getattr(tool, "annotations", None)
    return {
        "readOnlyHint": getattr(annotations, "readOnlyHint", None),
        "destructiveHint": getattr(annotations, "destructiveHint", None),
        "openWorldHint": getattr(annotations, "openWorldHint", None),
    }


def actual_tool_input_schema_payload(tool: Any) -> dict[str, Any] | None:
    schema = getattr(tool, "inputSchema", None)
    return schema if isinstance(schema, dict) else None


def actual_tool_output_schema_payload(tool: Any) -> dict[str, Any] | None:
    schema = getattr(tool, "outputSchema", None)
    return schema if isinstance(schema, dict) else None


def verify_tool_output_schema(tool_name: str, schema: Any) -> list[str]:
    if not isinstance(schema, dict):
        return [f"output-schema-missing:{tool_name}"]
    blockers: list[str] = []
    if schema.get("type") != "object":
        blockers.append(f"output-schema-not-object:{tool_name}:{schema.get('type')!r}")
    if schema.get("additionalProperties") not in (True, False):
        blockers.append(f"output-schema-additional-properties-missing:{tool_name}")
    return blockers


def verify_submit_package_proposal_input_schema(schema: Any) -> list[str]:
    if not isinstance(schema, dict):
        return ["submit-package-proposal-input-schema-missing"]
    blockers: list[str] = []
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    if "proposal" not in properties:
        blockers.append("submit-package-proposal-missing-proposal-property")
    if "proposal" not in required:
        blockers.append("submit-package-proposal-proposal-not-required")
    defs = schema.get("$defs") if isinstance(schema.get("$defs"), dict) else {}
    proposal = defs.get("PackageProposal") if isinstance(defs.get("PackageProposal"), dict) else {}
    payload = defs.get("PackageProposalPayload") if isinstance(defs.get("PackageProposalPayload"), dict) else {}
    file_item = defs.get("PackageProposalFile") if isinstance(defs.get("PackageProposalFile"), dict) else {}
    check_item = defs.get("PackageProposalCheck") if isinstance(defs.get("PackageProposalCheck"), dict) else {}
    if proposal.get("additionalProperties") is not False:
        blockers.append("submit-package-proposal-top-level-extra-not-forbidden")
    if payload.get("additionalProperties") is not False:
        blockers.append("submit-package-payload-extra-not-forbidden")
    if file_item.get("additionalProperties") is not False:
        blockers.append("submit-package-file-extra-not-forbidden")
    if check_item.get("additionalProperties") is not False:
        blockers.append("submit-package-check-extra-not-forbidden")
    proposal_required = proposal.get("required") if isinstance(proposal.get("required"), list) else []
    for field in ("schemaVersion", "kind", "title", "payload"):
        if field not in proposal_required:
            blockers.append(f"submit-package-proposal-required-field-missing:{field}")
    proposal_properties = proposal.get("properties") if isinstance(proposal.get("properties"), dict) else {}
    if proposal_properties.get("schemaVersion", {}).get("const") != 1:
        blockers.append("submit-package-proposal-schema-version-not-const-1")
    if proposal_properties.get("kind", {}).get("const") != "package-proposal":
        blockers.append("submit-package-proposal-kind-not-const")
    payload_required = payload.get("required") if isinstance(payload.get("required"), list) else []
    for field in ("packageName", "files"):
        if field not in payload_required:
            blockers.append(f"submit-package-payload-required-field-missing:{field}")
    file_properties = file_item.get("properties") if isinstance(file_item.get("properties"), dict) else {}
    file_required = file_item.get("required") if isinstance(file_item.get("required"), list) else []
    for field in ("target", "content"):
        if field not in file_required:
            blockers.append(f"submit-package-file-required-field-missing:{field}")
    if file_properties.get("encoding", {}).get("const") != "utf-8":
        blockers.append("submit-package-file-encoding-not-const-utf8")
    check_properties = check_item.get("properties") if isinstance(check_item.get("properties"), dict) else {}
    if "args" not in check_properties:
        blockers.append("submit-package-check-args-schema-missing")
    return blockers


def list_registered_sdk_tools(server: Any) -> list[Any]:
    list_tools = getattr(server, "list_tools", None)
    if not callable(list_tools):
        raise AdapterError(
            "MCP_SDK_LIST_TOOLS_UNAVAILABLE",
            "FastMCP server object does not expose list_tools(); cannot verify registered tool metadata.",
            status="failed",
        )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return list(asyncio.run(list_tools()))
    raise AdapterError(
        "MCP_SDK_VALIDATION_REQUIRES_SYNC_CONTEXT",
        "SDK validation must run from a synchronous context because it verifies FastMCP list_tools().",
        status="failed",
    )


def verify_registered_sdk_tools(server: Any, *, tool_profile: str = TOOL_PROFILE_FULL) -> list[dict[str, Any]]:
    registered_tools = list_registered_sdk_tools(server)
    summaries: list[dict[str, Any]] = []
    blockers: list[str] = []
    by_name: dict[str, Any] = {}
    for tool in registered_tools:
        name = getattr(tool, "name", None)
        if isinstance(name, str):
            by_name[name] = tool
    actual_names = list(by_name.keys())
    expected_names = list(tool_order_for_profile(tool_profile))
    if actual_names != expected_names:
        blockers.append(f"tool-order-or-set-mismatch:actual={actual_names!r}:expected={expected_names!r}")

    for expected_name in expected_names:
        spec = TOOL_SPECS[expected_name]
        tool = by_name.get(expected_name)
        if tool is None:
            blockers.append(f"missing-tool:{expected_name}")
            continue
        annotation_payload = actual_tool_annotation_payload(tool)
        expected_annotations = spec.annotation_payload()
        for field, expected_value in expected_annotations.items():
            actual_value = annotation_payload.get(field)
            if actual_value is not expected_value:
                blockers.append(f"annotation-mismatch:{expected_name}:{field}:actual={actual_value!r}:expected={expected_value!r}")
        description = getattr(tool, "description", "") or ""
        if not str(description).startswith("Use this when"):
            blockers.append(f"description-prefix-missing:{expected_name}")
        input_schema = actual_tool_input_schema_payload(tool)
        output_schema = actual_tool_output_schema_payload(tool)
        blockers.extend(verify_tool_output_schema(expected_name, output_schema))
        if expected_name == "submit_package_proposal" and input_schema is not None:
            blockers.extend(verify_submit_package_proposal_input_schema(input_schema))
        summaries.append(
            {
                "name": expected_name,
                "descriptionStartsUseThisWhen": str(description).startswith("Use this when"),
                "annotations": annotation_payload,
                "inputSchema": input_schema,
                "outputSchema": output_schema,
            }
        )

    if blockers:
        raise AdapterError(
            "MCP_SDK_REGISTRATION_MISMATCH",
            "FastMCP registered tool metadata did not match the narrow adapter manifest.",
            status="failed",
            extra={"blockers": blockers, "registeredTools": summaries},
        )
    return summaries


def local_mcp_sdk_validation_root(repo_root: Path) -> Path:
    return (repo_root / ".riftreader-local" / "mcp-sdk-validation").resolve()


def ensure_mcp_sdk_available(repo_root: Path) -> list[str]:
    added: list[str] = []
    try:
        if importlib.util.find_spec("mcp") is not None:
            return added
    except ValueError:
        if "mcp" in sys.modules:
            return added
        raise
    local_sdk = local_mcp_sdk_validation_root(repo_root)
    if (local_sdk / "mcp" / "__init__.py").is_file():
        sys.path.insert(0, str(local_sdk))
        added.append(str(local_sdk))
    try:
        sdk_missing = importlib.util.find_spec("mcp") is None
    except ValueError:
        sdk_missing = "mcp" not in sys.modules
    if sdk_missing:
        raise AdapterError(
            "MCP_PYTHON_SDK_MISSING",
            'Python package "mcp" is not installed. Install it before SDK or transport validation, '
            'for example: python -m pip install --target .riftreader-local\\mcp-sdk-validation "mcp[cli]".',
            status="failed",
        )
    return added


def build_child_pythonpath(config: AdapterConfig, existing_env: dict[str, str] | None = None) -> str:
    env = existing_env if existing_env is not None else os.environ
    entries: list[str] = []
    local_sdk = local_mcp_sdk_validation_root(config.repo_root)
    if (local_sdk / "mcp" / "__init__.py").is_file():
        entries.append(str(local_sdk))
    tools_root = (config.repo_root / "tools").resolve()
    entries.append(str(tools_root))
    existing = env.get("PYTHONPATH", "")
    if existing:
        entries.append(existing)
    return os.pathsep.join(entries)


def choose_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((DEFAULT_HOST, 0))
        return int(sock.getsockname()[1])


def validate_public_host_value(value: str, *, field_name: str = "allowed host") -> str:
    candidate = value.strip()
    if not candidate:
        raise AdapterError("PUBLIC_HOST_INVALID", f"{field_name} must not be empty.", status="failed")
    if "://" in candidate or "/" in candidate or "\\" in candidate:
        raise AdapterError(
            "PUBLIC_HOST_INVALID",
            f"{field_name} must be a bare host or host:port value, not a URL/path.",
            status="failed",
            extra={"value": value},
        )
    if candidate == "*":
        raise AdapterError("PUBLIC_HOST_INVALID", f"{field_name} wildcard '*' is not allowed.", status="failed")
    return candidate


def normalize_allowed_hosts(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        candidate = validate_public_host_value(value)
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized


def normalize_allowed_origins(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        candidate = value.strip()
        if not candidate:
            raise AdapterError("PUBLIC_ORIGIN_INVALID", "allowed origin must not be empty.", status="failed")
        if candidate == "*" or "*" in candidate:
            raise AdapterError("PUBLIC_ORIGIN_INVALID", "allowed origin wildcards are not allowed.", status="failed")
        candidate = candidate.rstrip("/")
        parsed = urlsplit(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AdapterError(
                "PUBLIC_ORIGIN_INVALID",
                "allowed origin must be an exact http(s) origin, e.g. https://chatgpt.com.",
                status="failed",
                extra={"value": value},
            )
        if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise AdapterError(
                "PUBLIC_ORIGIN_INVALID",
                "allowed origin must not include path, query, fragment, or credentials.",
                status="failed",
                extra={"value": value},
            )
        candidate = f"{parsed.scheme}://{parsed.netloc}"
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized


def default_transport_allowed_hosts() -> list[str]:
    return ["127.0.0.1:*", "localhost:*", "[::1]:*"]


def default_transport_allowed_origins() -> list[str]:
    return ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


def validate_sdk_registration(
    config: AdapterConfig,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    tool_profile: str = TOOL_PROFILE_FULL,
) -> dict[str, Any]:
    if host != DEFAULT_HOST:
        raise AdapterError(
            "UNSAFE_BIND_HOST",
            "The MVP MCP adapter only supports 127.0.0.1 for SDK validation and serving.",
            status="failed",
            extra={"host": host},
        )
    if port < 0 or port > 65535:
        raise AdapterError("INVALID_PORT", "Port must be in range 0-65535.", status="failed", extra={"port": port})
    sdk_path_additions = ensure_mcp_sdk_available(config.repo_root)
    adapter = RiftReaderChatGptMcpAdapter(config)
    server = create_fastmcp_server(
        adapter,
        host=host,
        port=port,
        allowed_hosts=normalize_allowed_hosts(allowed_hosts),
        allowed_origins=normalize_allowed_origins(allowed_origins),
        tool_profile=tool_profile,
    )
    registered_tools = verify_registered_sdk_tools(server, tool_profile=tool_profile)
    tool_order = tool_order_for_profile(tool_profile)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-sdk-registration-validation",
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "ok": True,
        "service": SERVER_NAME,
        "version": VERSION,
        "toolProfile": tool_profile,
        "serverClass": type(server).__name__,
        "toolCount": len(tool_order),
        "tools": tool_manifest(tool_profile)["tools"],
        "registeredTools": registered_tools,
        "allowedHosts": normalize_allowed_hosts(allowed_hosts),
        "allowedOrigins": normalize_allowed_origins(allowed_origins),
        "blockers": [],
        "warnings": [
            "SDK validation constructs the FastMCP server object only; it does not call run(), bind a port, or start a tunnel.",
        ],
        "safety": {
            **base_safety(),
            "sdkImported": True,
            "toolAnnotationsRequired": True,
            "registeredToolMetadataVerified": True,
            "serverConstructed": True,
            "sdkPathAdditions": sdk_path_additions,
            "serverStarted": False,
            "tunnelStarted": False,
        },
    }


def compact_exception_text(exc: BaseException) -> str:
    child_exceptions = getattr(exc, "exceptions", None)
    if type(exc).__name__ in {"BaseExceptionGroup", "ExceptionGroup"} and isinstance(child_exceptions, tuple):
        child_errors = "; ".join(compact_exception_text(child) for child in child_exceptions[:3])
        suffix = f" [{child_errors}]" if child_errors else ""
        if len(child_exceptions) > 3:
            suffix += f" (+{len(child_exceptions) - 3} more)"
        return f"{type(exc).__name__}: {exc}{suffix}"
    return f"{type(exc).__name__}: {exc}"


class TransportClientStepError(Exception):
    """Transport smoke client error annotated with the failing MCP step."""

    def __init__(self, stage: str, original: BaseException, step_timings: list[dict[str, Any]]) -> None:
        super().__init__(f"{stage}: {compact_exception_text(original)}")
        self.stage = stage
        self.original = original
        self.step_timings = list(step_timings)


async def record_transport_client_step(
    stage: str,
    step_timings: list[dict[str, Any]],
    progress: dict[str, Any],
    operation: Callable[[], Awaitable[Any]],
) -> Any:
    progress["currentStage"] = stage
    progress["stepTimings"] = step_timings
    started = time.monotonic()
    try:
        result = await operation()
    except asyncio.CancelledError:
        duration = time.monotonic() - started
        step_timings.append(
            {
                "stage": stage,
                "status": "cancelled",
                "durationSeconds": round(duration, 3),
                "error": "CancelledError: transport client attempt exceeded its bounded timeout",
            }
        )
        raise
    except Exception as exc:
        duration = time.monotonic() - started
        step_timings.append(
            {
                "stage": stage,
                "status": "failed",
                "durationSeconds": round(duration, 3),
                "error": compact_exception_text(exc),
            }
        )
        raise TransportClientStepError(stage, exc, step_timings) from exc
    duration = time.monotonic() - started
    step_timings.append({"stage": stage, "status": "passed", "durationSeconds": round(duration, 3)})
    progress["lastCompletedStage"] = stage
    return result


async def run_transport_client_once(
    url: str,
    package_proposal: dict[str, Any] | None = None,
    *,
    client_read_timeout_seconds: float,
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared._httpx_utils import create_mcp_http_client
    import httpx

    step_timings: list[dict[str, Any]] = []
    progress = progress if progress is not None else {}
    progress["stepTimings"] = step_timings
    timeout = httpx.Timeout(
        connect=TRANSPORT_CLIENT_CONNECT_TIMEOUT_SECONDS,
        read=client_read_timeout_seconds,
        write=TRANSPORT_CLIENT_WRITE_TIMEOUT_SECONDS,
        pool=TRANSPORT_CLIENT_POOL_TIMEOUT_SECONDS,
    )
    async with create_mcp_http_client(timeout=timeout) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream, _get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await record_transport_client_step("initialize", step_timings, progress, session.initialize)
                tools_result = await record_transport_client_step("list_tools", step_timings, progress, session.list_tools)
                health_result = await record_transport_client_step(
                    "call_tool:health",
                    step_timings,
                    progress,
                    lambda: session.call_tool("health", {}),
                )
                submit_result = None
                inbox_result = None
                draft_result = None
                review_result = None
                dry_run_result = None
                apply_without_approval_result = None
                if package_proposal is not None:
                    submit_result = await record_transport_client_step(
                        "call_tool:submit_package_proposal",
                        step_timings,
                        progress,
                        lambda: session.call_tool("submit_package_proposal", {"proposal": package_proposal}),
                    )
                    inbox_result = await record_transport_client_step(
                        "call_tool:list_inbox",
                        step_timings,
                        progress,
                        lambda: session.call_tool("list_inbox", {}),
                    )
                    submit_content = getattr(submit_result, "structuredContent", None)
                    inbox_id = submit_content.get("inboxId") if isinstance(submit_content, dict) else None
                    if isinstance(inbox_id, str) and inbox_id:
                        draft_result = await record_transport_client_step(
                            "call_tool:create_package_draft_from_inbox",
                            step_timings,
                            progress,
                            lambda: session.call_tool("create_package_draft_from_inbox", {"inboxId": inbox_id}),
                        )
                        review_result = await record_transport_client_step(
                            "call_tool:review_latest_package_draft",
                            step_timings,
                            progress,
                            lambda: session.call_tool("review_latest_package_draft", {"operatorOnly": False}),
                        )
                        dry_run_result = await record_transport_client_step(
                            "call_tool:dry_run_latest_package_draft",
                            step_timings,
                            progress,
                            lambda: session.call_tool(
                                "dry_run_latest_package_draft",
                                {"operatorOnly": False, "timeoutSeconds": DEFAULT_DRY_RUN_TIMEOUT_SECONDS},
                            ),
                        )
                        apply_without_approval_result = await record_transport_client_step(
                            "call_tool:apply_latest_package_draft",
                            step_timings,
                            progress,
                            lambda: session.call_tool(
                                "apply_latest_package_draft",
                                {"operatorOnly": False, "timeoutSeconds": DEFAULT_DRY_RUN_TIMEOUT_SECONDS},
                            ),
                        )
    tools = list(getattr(tools_result, "tools", []) or [])
    tool_names = [getattr(tool, "name", None) for tool in tools]
    registered_summaries = []
    for tool in tools:
        registered_summaries.append(
            {
                "name": getattr(tool, "name", None),
                "descriptionStartsUseThisWhen": str(getattr(tool, "description", "") or "").startswith("Use this when"),
                "annotations": actual_tool_annotation_payload(tool),
                "inputSchema": actual_tool_input_schema_payload(tool),
                "outputSchema": actual_tool_output_schema_payload(tool),
            }
        )
    return {
        "toolCount": len(tools),
        "toolNames": tool_names,
        "registeredTools": registered_summaries,
        "transportClientApi": "streamable_http_client",
        "clientReadTimeoutSeconds": client_read_timeout_seconds,
        "clientStepTimings": step_timings,
        "healthIsError": bool(getattr(health_result, "isError", False)),
        "healthStructuredContent": getattr(health_result, "structuredContent", None),
        "healthContentTypes": [type(item).__name__ for item in getattr(health_result, "content", []) or []],
        "submitPackageProposalIsError": bool(getattr(submit_result, "isError", False)) if submit_result is not None else None,
        "submitPackageProposalStructuredContent": getattr(submit_result, "structuredContent", None) if submit_result is not None else None,
        "listInboxAfterSubmitIsError": bool(getattr(inbox_result, "isError", False)) if inbox_result is not None else None,
        "listInboxAfterSubmitStructuredContent": getattr(inbox_result, "structuredContent", None) if inbox_result is not None else None,
        "createPackageDraftIsError": bool(getattr(draft_result, "isError", False)) if draft_result is not None else None,
        "createPackageDraftStructuredContent": getattr(draft_result, "structuredContent", None) if draft_result is not None else None,
        "reviewLatestPackageDraftIsError": bool(getattr(review_result, "isError", False)) if review_result is not None else None,
        "reviewLatestPackageDraftStructuredContent": getattr(review_result, "structuredContent", None) if review_result is not None else None,
        "dryRunLatestPackageDraftIsError": bool(getattr(dry_run_result, "isError", False)) if dry_run_result is not None else None,
        "dryRunLatestPackageDraftStructuredContent": getattr(dry_run_result, "structuredContent", None) if dry_run_result is not None else None,
        "applyLatestPackageDraftWithoutApprovalIsError": bool(getattr(apply_without_approval_result, "isError", False))
        if apply_without_approval_result is not None
        else None,
        "applyLatestPackageDraftWithoutApprovalStructuredContent": getattr(apply_without_approval_result, "structuredContent", None)
        if apply_without_approval_result is not None
        else None,
    }


async def run_transport_client_with_retry(
    url: str,
    server_process: subprocess.Popen[str],
    timeout_seconds: float,
    package_proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    last_stage: str | None = None
    last_step_timings: list[dict[str, Any]] = []
    last_client_read_timeout: float | None = None
    while time.monotonic() < deadline:
        if server_process.poll() is not None:
            raise AdapterError(
                "MCP_TRANSPORT_SERVER_EXITED_EARLY",
                "MCP server process exited before the transport smoke client could connect.",
                status="failed",
                extra={
                    "serverExitCode": server_process.returncode,
                    "lastClientError": last_error,
                    "lastClientStage": last_stage,
                    "lastClientStepTimings": last_step_timings,
                },
            )
        remaining_seconds = max(0.001, deadline - time.monotonic())
        last_client_read_timeout = remaining_seconds + TRANSPORT_CLIENT_READ_TIMEOUT_MARGIN_SECONDS
        progress: dict[str, Any] = {}
        try:
            return await asyncio.wait_for(
                run_transport_client_once(
                    url,
                    package_proposal=package_proposal,
                    client_read_timeout_seconds=last_client_read_timeout,
                    progress=progress,
                ),
                timeout=remaining_seconds,
            )
        except asyncio.TimeoutError:
            last_stage = str(progress.get("currentStage") or "unknown")
            last_step_timings = list(progress.get("stepTimings") or [])
            last_error = (
                "TimeoutError: transport client attempt exceeded remaining smoke timeout "
                f"at {last_stage}"
            )
            break
        except TransportClientStepError as exc:
            last_stage = exc.stage
            last_step_timings = exc.step_timings
            last_error = compact_exception_text(exc.original)
            await asyncio.sleep(0.5)
        except Exception as exc:  # noqa: BLE001 - retry until bounded timeout expires.
            last_stage = str(progress.get("currentStage") or "unknown")
            last_step_timings = list(progress.get("stepTimings") or [])
            last_error = compact_exception_text(exc)
            await asyncio.sleep(0.5)
    raise AdapterError(
        "MCP_TRANSPORT_CLIENT_TIMEOUT",
        "Timed out waiting for MCP streamable HTTP client smoke test to pass.",
        status="failed",
        extra={
            "url": url,
            "timeoutSeconds": timeout_seconds,
            "lastClientError": last_error,
            "lastClientStage": last_stage,
            "lastClientReadTimeoutSeconds": last_client_read_timeout,
            "lastClientStepTimings": last_step_timings,
        },
    )


def verify_transport_smoke_result(client_result: dict[str, Any], *, tool_profile: str = TOOL_PROFILE_FULL) -> list[str]:
    blockers: list[str] = []
    expected_names = list(tool_order_for_profile(tool_profile))
    if client_result.get("toolNames") != expected_names:
        blockers.append(f"tool-order-or-set-mismatch:actual={client_result.get('toolNames')!r}:expected={expected_names!r}")
    if client_result.get("healthIsError") is True:
        blockers.append("health-call-returned-error")
    health = client_result.get("healthStructuredContent")
    if not isinstance(health, dict):
        blockers.append("health-structured-content-missing")
    else:
        if health.get("service") != SERVER_NAME:
            blockers.append(f"health-service-mismatch:{health.get('service')!r}")
        if health.get("toolCount") != len(expected_names):
            blockers.append(f"health-tool-count-mismatch:{health.get('toolCount')!r}")
        if health.get("toolProfile") not in (tool_profile, None):
            blockers.append(f"health-tool-profile-mismatch:{health.get('toolProfile')!r}")
        if health.get("repoRoot") != ".":
            blockers.append(f"health-repo-root-not-redacted:{health.get('repoRoot')!r}")
        safety = health.get("safety") if isinstance(health.get("safety"), dict) else {}
        if safety.get("absoluteRepoRootExposed") is not False:
            blockers.append(
                "health-absolute-repo-root-exposure-flag-not-false:"
                f"{safety.get('absoluteRepoRootExposed')!r}"
            )
    for tool in client_result.get("registeredTools") or []:
        name = tool.get("name")
        if not isinstance(name, str) or name not in TOOL_SPECS:
            blockers.append(f"unexpected-tool-in-transport:{name!r}")
            continue
        spec = TOOL_SPECS[name]
        annotations = tool.get("annotations") if isinstance(tool.get("annotations"), dict) else {}
        for field, expected_value in spec.annotation_payload().items():
            if annotations.get(field) is not expected_value:
                blockers.append(f"transport-annotation-mismatch:{name}:{field}:actual={annotations.get(field)!r}:expected={expected_value!r}")
        if tool.get("descriptionStartsUseThisWhen") is not True:
            blockers.append(f"transport-description-prefix-missing:{name}")
        blockers.extend(verify_tool_output_schema(name, tool.get("outputSchema")))
        if name == "submit_package_proposal":
            blockers.extend(verify_submit_package_proposal_input_schema(tool.get("inputSchema")))
    if client_result.get("submitPackageProposalIsError") is not None:
        if client_result.get("submitPackageProposalIsError") is True:
            blockers.append("submit-package-proposal-returned-error")
        submit_result = client_result.get("submitPackageProposalStructuredContent")
        if not isinstance(submit_result, dict):
            blockers.append("submit-package-proposal-structured-content-missing")
        else:
            if submit_result.get("ok") is not True:
                blockers.append(f"submit-package-proposal-not-ok:{submit_result.get('code') or submit_result.get('status')}")
            if not isinstance(submit_result.get("inboxId"), str) or not submit_result.get("inboxId"):
                blockers.append("submit-package-proposal-inbox-id-missing")
            safety = submit_result.get("safety") if isinstance(submit_result.get("safety"), dict) else {}
            if safety.get("noRepoTargetWrites") is not True:
                blockers.append("submit-package-proposal-no-repo-target-writes-flag-missing")
        if client_result.get("listInboxAfterSubmitIsError") is True:
            blockers.append("list-inbox-after-submit-returned-error")
        inbox_result = client_result.get("listInboxAfterSubmitStructuredContent")
        if not isinstance(inbox_result, dict):
            blockers.append("list-inbox-after-submit-structured-content-missing")
        elif inbox_result.get("ok") is not True:
            blockers.append(f"list-inbox-after-submit-not-ok:{inbox_result.get('code') or inbox_result.get('status')}")
        if client_result.get("createPackageDraftIsError") is True:
            blockers.append("create-package-draft-returned-error")
        draft_result = client_result.get("createPackageDraftStructuredContent")
        if not isinstance(draft_result, dict):
            blockers.append("create-package-draft-structured-content-missing")
        else:
            if draft_result.get("ok") is not True:
                blockers.append(f"create-package-draft-not-ok:{draft_result.get('code') or draft_result.get('status')}")
            if not isinstance(draft_result.get("draftId"), str) or not draft_result.get("draftId"):
                blockers.append("create-package-draft-draft-id-missing")
            safety = draft_result.get("safety") if isinstance(draft_result.get("safety"), dict) else {}
            if safety.get("localPackageDraftOnly") is not True:
                blockers.append("create-package-draft-local-only-flag-missing")
            if safety.get("applyFlagSent") is not False:
                blockers.append("create-package-draft-apply-flag-not-false")
        if client_result.get("reviewLatestPackageDraftIsError") is True:
            blockers.append("review-latest-package-draft-returned-error")
        review_result = client_result.get("reviewLatestPackageDraftStructuredContent")
        if not isinstance(review_result, dict):
            blockers.append("review-latest-package-draft-structured-content-missing")
        else:
            if review_result.get("ok") is not True:
                blockers.append(f"review-latest-package-draft-not-ok:{review_result.get('code') or review_result.get('status')}")
            safety = review_result.get("safety") if isinstance(review_result.get("safety"), dict) else {}
            if safety.get("readOnlyReview") is not True:
                blockers.append("review-latest-package-draft-read-only-review-flag-missing")
        if client_result.get("dryRunLatestPackageDraftIsError") is True:
            blockers.append("dry-run-latest-package-draft-returned-error")
        dry_run_result = client_result.get("dryRunLatestPackageDraftStructuredContent")
        if not isinstance(dry_run_result, dict):
            blockers.append("dry-run-latest-package-draft-structured-content-missing")
        else:
            if dry_run_result.get("ok") is not True:
                blockers.append(f"dry-run-latest-package-draft-not-ok:{dry_run_result.get('code') or dry_run_result.get('status')}")
            if dry_run_result.get("dryRunSucceeded") is not True:
                blockers.append("dry-run-latest-package-draft-succeeded-flag-missing")
            safety = dry_run_result.get("safety") if isinstance(dry_run_result.get("safety"), dict) else {}
            if safety.get("packageIntakeDryRunOnly") is not True:
                blockers.append("dry-run-latest-package-draft-dry-run-only-flag-missing")
            if safety.get("applyFlagSent") is not False:
                blockers.append("dry-run-latest-package-draft-apply-flag-not-false")
            dry_run = dry_run_result.get("dryRun") if isinstance(dry_run_result.get("dryRun"), dict) else {}
            diff_preview = dry_run.get("diffPreview") if isinstance(dry_run.get("diffPreview"), dict) else {}
            if diff_preview.get("ok") is not True:
                blockers.append(f"dry-run-diff-preview-not-ok:{diff_preview.get('code') or diff_preview.get('status')}")
            if not isinstance(diff_preview.get("text"), str):
                blockers.append("dry-run-diff-preview-text-missing")
            diff_safety = diff_preview.get("safety") if isinstance(diff_preview.get("safety"), dict) else {}
            if diff_safety.get("diffArtifactUnderPackageIntake") is not True:
                blockers.append("dry-run-diff-preview-package-intake-flag-missing")
            if diff_safety.get("boundedBytes") is not True:
                blockers.append("dry-run-diff-preview-bounded-bytes-flag-missing")
            if diff_safety.get("applyFlagSent") is not False:
                blockers.append("dry-run-diff-preview-apply-flag-not-false")
        if client_result.get("applyLatestPackageDraftWithoutApprovalIsError") is None:
            blockers.append("apply-latest-package-draft-without-approval-not-covered")
        apply_without_approval = client_result.get("applyLatestPackageDraftWithoutApprovalStructuredContent")
        if not isinstance(apply_without_approval, dict):
            blockers.append("apply-latest-package-draft-without-approval-structured-content-missing")
        else:
            if apply_without_approval.get("ok") is not False:
                blockers.append(f"apply-latest-package-draft-without-approval-ok-not-false:{apply_without_approval.get('ok')!r}")
            if apply_without_approval.get("applied") is not False:
                blockers.append(
                    "apply-latest-package-draft-without-approval-applied-not-false:"
                    f"{apply_without_approval.get('applied')!r}"
                )
            apply_blockers = apply_without_approval.get("blockers")
            if not isinstance(apply_blockers, list):
                blockers.append(
                    "apply-latest-package-draft-without-approval-blockers-not-list:"
                    f"{type(apply_blockers).__name__}"
                )
            elif "APPLY_APPROVAL_MISSING" not in apply_blockers:
                blockers.append("apply-latest-package-draft-without-approval-missing-approval-blocker")
            safety = apply_without_approval.get("safety") if isinstance(apply_without_approval.get("safety"), dict) else {}
            if safety.get("applyFlagSent") is not False:
                blockers.append("apply-latest-package-draft-without-approval-apply-flag-not-false")
            if safety.get("repoSourceMutationExpected") is not False:
                blockers.append("apply-latest-package-draft-without-approval-repo-mutation-expected-not-false")
    return blockers


def run_transport_smoke_test(
    config: AdapterConfig,
    *,
    host: str = DEFAULT_HOST,
    transport: str = "streamable-http",
    timeout_seconds: float = DEFAULT_TRANSPORT_SMOKE_TIMEOUT_SECONDS,
    include_proposal_submit: bool = False,
    tool_profile: str = TOOL_PROFILE_FULL,
) -> dict[str, Any]:
    if host != DEFAULT_HOST:
        raise AdapterError(
            "UNSAFE_BIND_HOST",
            "The transport smoke test only binds to 127.0.0.1.",
            status="failed",
            extra={"host": host},
        )
    if transport != "streamable-http":
        raise AdapterError(
            "TRANSPORT_SMOKE_TRANSPORT_UNSUPPORTED",
            "Transport smoke currently validates streamable-http only.",
            status="failed",
            extra={"transport": transport},
        )
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise AdapterError(
            "TRANSPORT_SMOKE_TIMEOUT_INVALID",
            "Transport smoke timeout must be > 0 and <= 120 seconds.",
            status="failed",
            extra={"timeoutSeconds": timeout_seconds},
        )
    if include_proposal_submit and tool_profile != TOOL_PROFILE_FULL:
        raise AdapterError(
            "PROPOSAL_SMOKE_REQUIRES_FULL_TOOL_PROFILE",
            "Proposal transport smoke requires the full tool profile.",
            status="failed",
            extra={"toolProfile": tool_profile},
        )

    sdk_path_additions = ensure_mcp_sdk_available(config.repo_root)
    port = choose_loopback_port()
    url = f"http://{host}:{port}/mcp"
    script_path = Path(__file__).resolve()
    command = [
        sys.executable,
        str(script_path),
        "--serve",
        "--host",
        host,
        "--port",
        str(port),
        "--transport",
        transport,
        "--repo-root",
        str(config.repo_root),
        "--payload-root",
        str(config.payload_root),
        "--audit-root",
        str(config.audit_root),
    ]
    if tool_profile != TOOL_PROFILE_FULL:
        command.extend(["--tool-profile", tool_profile])
    env = os.environ.copy()
    env["PYTHONPATH"] = build_child_pythonpath(config, env)

    process: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    server_stopped = False
    try:
        process = subprocess.Popen(
            command,
            cwd=str(config.repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        client_result = asyncio.run(
            run_transport_client_with_retry(
                url,
                process,
                timeout_seconds,
                package_proposal=self_test_package_proposal() if include_proposal_submit else None,
            )
        )
        blockers = verify_transport_smoke_result(client_result, tool_profile=tool_profile)
        status = "passed" if not blockers else "failed"
        ok = not blockers
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            server_stopped = process.poll() is not None
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=2)
                server_stopped = process.poll() is not None

    server_exit_code = process.returncode if process is not None else None
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-proposal-transport-smoke"
        if include_proposal_submit
        else "riftreader-chatgpt-mcp-transport-smoke",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": ok,
        "service": SERVER_NAME,
        "version": VERSION,
        "toolProfile": tool_profile,
        "url": url,
        "host": host,
        "port": port,
        "timeoutSeconds": timeout_seconds,
        "command": {
            "args": command,
            "cwd": str(config.repo_root),
        },
        "client": client_result,
        "blockers": blockers,
        "warnings": [
            "Transport smoke starts a temporary loopback-only server, calls list_tools and health, then terminates it.",
            "Proposal transport smoke also calls submit_package_proposal, list_inbox, create_package_draft_from_inbox, review_latest_package_draft, dry_run_latest_package_draft, and apply_latest_package_draft without approval with a synthetic self-test package; it writes ignored .riftreader-local inbox/draft/package-intake/audit artifacts only and expects apply to be blocked."
            if include_proposal_submit
            else "No proposal submit is performed by this smoke.",
            "No HTTPS tunnel, ChatGPT registration, Git mutation, RIFT input, CE, or x64dbg action is performed.",
        ],
        "serverProcess": {
            "exitCodeAfterStop": server_exit_code,
            "stopped": server_stopped,
            "stdoutTail": text_tail(stdout, 4000),
            "stderrTail": text_tail(stderr, 4000),
        },
        "safety": {
            **base_safety(),
            "temporaryLoopbackServerStarted": True,
            "serverStopped": server_stopped,
            "sdkPathAdditions": sdk_path_additions,
            "transport": transport,
            "proposalSubmitTransportCovered": include_proposal_submit,
            "proposalSubmitWritesLocalInboxOnly": include_proposal_submit,
            "packageDraftCreateTransportCovered": include_proposal_submit,
            "packageDraftWritesLocalOnly": include_proposal_submit,
            "packageDraftReviewTransportCovered": include_proposal_submit,
            "packageDraftDryRunTransportCovered": include_proposal_submit,
            "packageDraftDiffPreviewTransportCovered": include_proposal_submit,
            "packageDraftApplyWithoutApprovalBlocked": include_proposal_submit,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
        },
    }
    if not server_stopped:
        payload["status"] = "failed"
        payload["ok"] = False
        payload["blockers"] = list(payload["blockers"]) + ["temporary-server-not-stopped"]
    artifact = write_smoke_artifact(
        config,
        payload,
        prefix="proposal-transport-smoke" if include_proposal_submit else "transport-smoke",
    )
    payload["artifactPaths"] = {"summaryJson": artifact}
    Path(config.repo_root / artifact).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def smoke_artifact_root(config: AdapterConfig) -> Path:
    return (config.repo_root / ".riftreader-local" / "riftreader-chatgpt-mcp" / "transport-smoke").resolve()


def write_smoke_artifact(config: AdapterConfig, payload: dict[str, Any], *, prefix: str) -> str:
    root = smoke_artifact_root(config)
    if not is_relative_to(root, config.repo_root / ".riftreader-local"):
        raise AdapterError(
            "SMOKE_ARTIFACT_ROOT_NOT_LOCAL",
            "Transport smoke artifacts must stay under .riftreader-local.",
            status="failed",
            extra={"artifactRoot": str(root)},
        )
    root.mkdir(parents=True, exist_ok=True)
    stamp = utc_iso().replace(":", "").replace("-", "")
    path = root / f"{stamp}-{prefix}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return rel(config.repo_root, path)


def compact_stage_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "status": "failed",
            "ok": False,
            "code": "INVALID_STAGE_PAYLOAD",
            "message": f"Stage returned {type(payload).__name__}, not a JSON object.",
        }
    compact: dict[str, Any] = {}
    for key in (
        "schemaVersion",
        "kind",
        "service",
        "version",
        "status",
        "ok",
        "code",
        "message",
        "toolCount",
        "host",
        "port",
        "url",
        "timeoutSeconds",
        "exitCode",
    ):
        if key in payload:
            compact[key] = payload[key]
    for key in ("blockers", "warnings", "errors"):
        values = payload.get(key)
        if isinstance(values, list):
            compact[key] = values[:10]
            if len(values) > 10:
                compact[f"{key}Truncated"] = len(values) - 10
    artifacts = payload.get("artifactPaths") or payload.get("artifacts")
    if isinstance(artifacts, dict):
        compact["artifacts"] = artifacts
    safety = payload.get("safety")
    if isinstance(safety, dict):
        compact["safety"] = {
            key: safety.get(key)
            for key in (
                "temporaryLoopbackServerStarted",
                "serverStopped",
                "proposalSubmitTransportCovered",
                "proposalSubmitWritesLocalInboxOnly",
                "packageDraftCreateTransportCovered",
                "packageDraftWritesLocalOnly",
                "packageDraftReviewTransportCovered",
                "packageDraftDryRunTransportCovered",
                "packageDraftDiffPreviewTransportCovered",
                "packageDraftApplyWithoutApprovalBlocked",
                "publicTunnelStarted",
                "chatGptRegistrationPerformed",
                "applyFlagSent",
            )
            if key in safety
        }
    client = payload.get("client")
    if isinstance(client, dict):
        client_compact = {
            "toolCount": client.get("toolCount"),
            "toolNames": client.get("toolNames"),
            "healthIsError": client.get("healthIsError"),
        }
        for key in (
            "submitPackageProposalIsError",
            "listInboxAfterSubmitIsError",
            "createPackageDraftIsError",
            "reviewLatestPackageDraftIsError",
            "dryRunLatestPackageDraftIsError",
            "applyLatestPackageDraftWithoutApprovalIsError",
        ):
            if key in client:
                client_compact[key] = client.get(key)
        submit_result = client.get("submitPackageProposalStructuredContent")
        if isinstance(submit_result, dict):
            client_compact["submitPackageProposal"] = {
                "ok": submit_result.get("ok"),
                "status": submit_result.get("status"),
                "code": submit_result.get("code"),
                "inboxId": submit_result.get("inboxId"),
                "noRepoTargetWrites": (submit_result.get("safety") or {}).get("noRepoTargetWrites")
                if isinstance(submit_result.get("safety"), dict)
                else None,
            }
        inbox_result = client.get("listInboxAfterSubmitStructuredContent")
        if isinstance(inbox_result, dict):
            client_compact["listInboxAfterSubmit"] = {
                "ok": inbox_result.get("ok"),
                "status": inbox_result.get("status"),
                "code": inbox_result.get("code"),
                "count": inbox_result.get("count"),
            }
        draft_result = client.get("createPackageDraftStructuredContent")
        if isinstance(draft_result, dict):
            client_compact["createPackageDraft"] = {
                "ok": draft_result.get("ok"),
                "status": draft_result.get("status"),
                "code": draft_result.get("code"),
                "draftId": draft_result.get("draftId"),
                "localPackageDraftOnly": (draft_result.get("safety") or {}).get("localPackageDraftOnly")
                if isinstance(draft_result.get("safety"), dict)
                else None,
            }
        review_result = client.get("reviewLatestPackageDraftStructuredContent")
        if isinstance(review_result, dict):
            client_compact["reviewLatestPackageDraft"] = {
                "ok": review_result.get("ok"),
                "status": review_result.get("status"),
                "code": review_result.get("code"),
                "draftId": review_result.get("draftId"),
                "readOnlyReview": (review_result.get("safety") or {}).get("readOnlyReview")
                if isinstance(review_result.get("safety"), dict)
                else None,
            }
        dry_run_result = client.get("dryRunLatestPackageDraftStructuredContent")
        if isinstance(dry_run_result, dict):
            dry_run = dry_run_result.get("dryRun") if isinstance(dry_run_result.get("dryRun"), dict) else {}
            diff_preview = dry_run.get("diffPreview") if isinstance(dry_run.get("diffPreview"), dict) else {}
            client_compact["dryRunLatestPackageDraft"] = {
                "ok": dry_run_result.get("ok"),
                "status": dry_run_result.get("status"),
                "code": dry_run_result.get("code"),
                "draftId": dry_run_result.get("draftId"),
                "dryRunSucceeded": dry_run_result.get("dryRunSucceeded"),
                "packageIntakeDryRunOnly": (dry_run_result.get("safety") or {}).get("packageIntakeDryRunOnly")
                if isinstance(dry_run_result.get("safety"), dict)
                else None,
                "diffPreview": {
                    "ok": diff_preview.get("ok"),
                    "status": diff_preview.get("status"),
                    "code": diff_preview.get("code"),
                    "artifactPath": diff_preview.get("artifactPath"),
                    "truncated": diff_preview.get("truncated"),
                    "sizeBytes": diff_preview.get("sizeBytes"),
                    "maxBytes": diff_preview.get("maxBytes"),
                    "textLength": len(diff_preview.get("text")) if isinstance(diff_preview.get("text"), str) else None,
                    "diffArtifactUnderPackageIntake": (diff_preview.get("safety") or {}).get("diffArtifactUnderPackageIntake")
                    if isinstance(diff_preview.get("safety"), dict)
                    else None,
                },
            }
        apply_without_approval = client.get("applyLatestPackageDraftWithoutApprovalStructuredContent")
        if isinstance(apply_without_approval, dict):
            client_compact["applyLatestPackageDraftWithoutApproval"] = {
                "ok": apply_without_approval.get("ok"),
                "status": apply_without_approval.get("status"),
                "code": apply_without_approval.get("code"),
                "applied": apply_without_approval.get("applied"),
                "blockers": list(apply_without_approval.get("blockers") or [])[:10],
                "applyFlagSent": (apply_without_approval.get("safety") or {}).get("applyFlagSent")
                if isinstance(apply_without_approval.get("safety"), dict)
                else None,
                "repoSourceMutationExpected": (apply_without_approval.get("safety") or {}).get("repoSourceMutationExpected")
                if isinstance(apply_without_approval.get("safety"), dict)
                else None,
            }
        compact["client"] = client_compact
    registered = payload.get("registeredTools")
    if isinstance(registered, list):
        compact["registeredToolNames"] = [item.get("name") for item in registered if isinstance(item, dict)]
    return compact


def stage_blockers(stage_name: str, payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{stage_name}:invalid-stage-payload"]
    if payload.get("ok"):
        return []
    raw_blockers = payload.get("blockers")
    if isinstance(raw_blockers, list) and raw_blockers:
        return [f"{stage_name}:{blocker}" for blocker in raw_blockers[:10]]
    return [f"{stage_name}:{payload.get('code') or payload.get('status') or 'not-ok'}"]


def run_readiness_stage(stage_name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except AdapterError as exc:
        return blocked_payload(
            exc.code,
            exc.message,
            kind=f"riftreader-chatgpt-mcp-trial-readiness-{stage_name}",
            status=exc.status,
            extra=exc.extra,
        )
    except Exception as exc:  # noqa: BLE001 - fail closed with compact evidence.
        return blocked_payload(
            "TRIAL_READINESS_STAGE_FAILED",
            f"{stage_name}: {type(exc).__name__}: {exc}",
            kind=f"riftreader-chatgpt-mcp-trial-readiness-{stage_name}",
            status="failed",
        )


def optional_executable_readiness(
    name: str,
    resolver: Callable[[], Path],
    *,
    required_for: str,
) -> dict[str, Any]:
    try:
        path = resolver()
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-optional-executable-readiness",
            "name": name,
            "requiredFor": required_for,
            "status": "passed",
            "ok": True,
            "path": str(path),
            "blockers": [],
            "warnings": [],
        }
    except AdapterError as exc:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-optional-executable-readiness",
            "name": name,
            "requiredFor": required_for,
            "status": "blocked",
            "ok": False,
            "code": exc.code,
            "message": exc.message,
            "blockers": [],
            "warnings": [exc.code],
            **exc.extra,
        }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def executable_binary_diagnostics(
    name: str,
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Return fail-closed binary integrity and behavior diagnostics.

    The probe only runs ``--version``. It does not initialize profiles, start a
    tunnel, call OpenAI, mutate local config, or touch the MCP server.
    """

    blockers: list[str] = []
    warnings: list[str] = []
    resolved = path.expanduser()
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-executable-binary-diagnostics",
        "name": name,
        "path": str(resolved),
        "versionProbeArgs": [str(resolved), "--version"],
        "blockers": blockers,
        "warnings": warnings,
    }
    if not resolved.is_file():
        blockers.append(f"{name}-binary-not-file")
        payload.update({"status": "blocked", "ok": False})
        return payload
    try:
        payload["sha256"] = file_sha256(resolved)
    except OSError as exc:
        blockers.append(f"{name}-sha256-failed")
        payload["error"] = f"{type(exc).__name__}:{exc}"
        payload.update({"status": "blocked", "ok": False})
        return payload

    version_probe = run_command_envelope(
        f"{name}-version",
        [str(resolved), "--version"],
        cwd,
        timeout_seconds=timeout_seconds,
    )
    payload["versionProbe"] = version_probe
    if not version_probe.get("ok"):
        blockers.append(f"{name}-version-probe-failed")
    payload.update({"status": "passed" if not blockers else "blocked", "ok": not blockers})
    return payload


def run_trial_readiness(
    config: AdapterConfig,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    transport: str = "streamable-http",
    transport_timeout_seconds: float = DEFAULT_TRANSPORT_SMOKE_TIMEOUT_SECONDS,
    tunnel_client_path: str | None = None,
    cloudflared_path: str | None = None,
) -> dict[str, Any]:
    stages: dict[str, Any] = {}
    blockers: list[str] = []
    warnings: list[str] = []

    stage_fns: tuple[tuple[str, Callable[[], dict[str, Any]]], ...] = (
        ("tool_manifest", tool_manifest),
        ("self_test", lambda: run_self_test(config)),
        (
            "validate_sdk",
            lambda: validate_sdk_registration(
                config,
                host=host,
                port=port,
                allowed_hosts=allowed_hosts,
                allowed_origins=allowed_origins,
            ),
        ),
        (
            "transport_smoke",
            lambda: run_transport_smoke_test(
                config,
                host=host,
                timeout_seconds=transport_timeout_seconds,
                transport=transport,
                include_proposal_submit=True,
            ),
        ),
    )
    for stage_name, fn in stage_fns:
        stage_payload = run_readiness_stage(stage_name, fn)
        stages[stage_name] = compact_stage_payload(stage_payload)
        blockers.extend(stage_blockers(stage_name, stage_payload))

    optional_dependencies = {
        "curl": optional_executable_readiness(
            "curl",
            resolve_curl_executable,
            required_for="optional Cloudflare named Tunnel reachability verification",
        ),
    }
    for name, dependency in optional_dependencies.items():
        if not dependency.get("ok"):
            warnings.append(f"{name}:{dependency.get('code') or dependency.get('status')}")

    status = "passed" if not blockers else "blocked"
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-trial-readiness",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "service": SERVER_NAME,
        "version": VERSION,
        "repoRoot": str(config.repo_root),
        "stages": stages,
        "optionalDependencies": optional_dependencies,
        "blockers": blockers,
        "warnings": warnings
        + [
            "Trial readiness starts only local/self-test and temporary loopback checks, including synthetic submit_package_proposal, create_package_draft_from_inbox, review_latest_package_draft, dry_run_latest_package_draft, diff-preview transport calls, and apply_latest_package_draft without approval.",
            "It does not start a public tunnel, register ChatGPT, serve persistently, perform an approved package apply, mutate Git, send RIFT input, or attach CE/x64dbg.",
        ],
        "safety": {
            **base_safety(),
            "trialReadinessLocalOnly": True,
            "temporaryLoopbackServerMayStart": True,
            "persistentServerStarted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "applyFlagSent": False,
        },
        "next": [
            "If status is passed, the narrow MCP adapter is locally ready for the Cloudflare named Tunnel Server URL path.",
            "Run --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json for the repo-specific operator plan.",
            "OpenAI Secure MCP Tunnel, trycloudflare quick tunnels, and Caddy/router paths are retired for this repo lane and are not fallback paths.",
            "If status is blocked, fix the listed stage blockers before any public-IP ChatGPT registration attempt.",
        ],
    }
    artifact = write_smoke_artifact(config, payload, prefix="trial-readiness")
    payload["artifactPaths"] = {"summaryJson": artifact}
    Path(config.repo_root / artifact).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def resolve_tunnel_client_executable(value: str | None = None, *, repo_root: Path | None = None) -> Path:
    candidates: list[Path] = []
    if value:
        candidates.append(Path(value).expanduser())
    for env_name in ("TUNNEL_CLIENT_PATH", "OPENAI_TUNNEL_CLIENT_PATH", "TUNNEL_CLIENT", "OPENAI_TUNNEL_CLIENT"):
        env_value = os.environ.get(env_name)
        if env_value:
            candidates.append(Path(env_value).expanduser())
    for found in (shutil.which("tunnel-client.exe"), shutil.which("tunnel-client")):
        if found:
            candidates.append(Path(found))
    if repo_root is not None:
        candidates.extend(
            (
                repo_root / ".riftreader-local" / "tools" / "openai" / "tunnel-client" / "tunnel-client.exe",
                repo_root / ".riftreader-local" / "tools" / "tunnel-client" / "tunnel-client.exe",
            )
        )
    candidates.extend(TUNNEL_CLIENT_DEFAULT_PATHS)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AdapterError(
        "TUNNEL_CLIENT_NOT_FOUND",
        "OpenAI tunnel-client executable was not found. Install it from Platform tunnel settings or pass --tunnel-client-path.",
        status="failed",
    )


def command_line(args: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return shlex.join(args)


def secure_tunnel_mcp_command(config: AdapterConfig) -> str:
    script = config.repo_root / "tools" / "riftreader_workflow" / "riftreader_chatgpt_mcp.py"
    args = [
        sys.executable,
        str(script),
        "--serve",
        "--transport",
        "stdio",
        "--repo-root",
        str(config.repo_root),
        "--payload-root",
        str(config.payload_root),
        "--audit-root",
        str(config.audit_root),
    ]
    return command_line(args)


def find_secret_like_values(value: Any) -> list[dict[str, str]]:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    findings: list[dict[str, str]] = []
    for name, pattern in SECRET_LIKE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"kind": name, "preview": match.group(0)[:6] + "...<redacted>"})
    return findings


def resolve_secure_tunnel_id(value: str | None) -> dict[str, Any]:
    if value is None or value.strip() == "":
        return {
            "status": "placeholder",
            "ok": True,
            "value": SECURE_TUNNEL_ID_PLACEHOLDER,
            "placeholder": True,
            "redacted": False,
            "blockers": [],
            "warnings": ["secure-tunnel-id-placeholder-used"],
        }

    stripped = value.strip()
    secret_findings = find_secret_like_values(stripped)
    if secret_findings:
        return {
            "status": "blocked",
            "ok": False,
            "value": SECURE_TUNNEL_ID_PLACEHOLDER,
            "placeholder": True,
            "redacted": True,
            "blockers": ["secure-tunnel-id-looks-like-secret"],
            "warnings": ["supplied-secure-tunnel-id-redacted"],
            "secretFindings": secret_findings,
        }
    if not SECURE_TUNNEL_ID_RE.fullmatch(stripped):
        return {
            "status": "blocked",
            "ok": False,
            "value": SECURE_TUNNEL_ID_PLACEHOLDER,
            "placeholder": True,
            "redacted": True,
            "blockers": ["secure-tunnel-id-invalid-format"],
            "warnings": ["supplied-secure-tunnel-id-not-echoed"],
        }
    return {
        "status": "passed",
        "ok": True,
        "value": stripped,
        "placeholder": False,
        "redacted": False,
        "blockers": [],
        "warnings": [],
    }


def build_secure_tunnel_plan(
    config: AdapterConfig,
    *,
    profile: str = "riftreader-local-stdio",
    tunnel_id: str | None = None,
    tunnel_client_path: str | None = None,
) -> dict[str, Any]:
    tunnel_client_status = optional_executable_readiness(
        "tunnel-client",
        lambda: resolve_tunnel_client_executable(tunnel_client_path, repo_root=config.repo_root),
        required_for="OpenAI Secure MCP Tunnel ChatGPT Web/Desktop path",
    )
    tunnel_client_diagnostics = None
    if tunnel_client_status.get("ok") and tunnel_client_status.get("path"):
        tunnel_client_diagnostics = executable_binary_diagnostics(
            "tunnel-client",
            Path(str(tunnel_client_status["path"])),
            cwd=config.repo_root,
        )
        tunnel_client_status["binaryDiagnostics"] = tunnel_client_diagnostics
    tunnel_client = str(tunnel_client_status.get("path") or "tunnel-client")
    blockers: list[str] = []
    if not tunnel_client_status.get("ok"):
        blockers.append("tunnel-client-not-found-or-not-configured")
    elif tunnel_client_diagnostics and not tunnel_client_diagnostics.get("ok"):
        blockers.extend(str(blocker) for blocker in tunnel_client_diagnostics.get("blockers") or [])
    tunnel_id_status = resolve_secure_tunnel_id(tunnel_id)
    if not tunnel_id_status.get("ok"):
        blockers.extend(str(blocker) for blocker in tunnel_id_status.get("blockers") or [])
    effective_tunnel_id = str(tunnel_id_status["value"])
    mcp_command = secure_tunnel_mcp_command(config)
    init_command = [
        tunnel_client,
        "init",
        "--sample",
        "sample_mcp_stdio_local",
        "--profile",
        profile,
        "--tunnel-id",
        effective_tunnel_id,
        "--mcp-command",
        mcp_command,
    ]
    doctor_command = [tunnel_client, "doctor", "--profile", profile, "--explain"]
    run_command_args = [tunnel_client, "run", "--profile", profile]
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-secure-tunnel-plan",
        "generatedAtUtc": utc_iso(),
        "status": "ready" if not blockers else "blocked",
        "ok": not blockers,
        "service": SERVER_NAME,
        "version": VERSION,
        "recommendedPath": "retired-openai-secure-mcp-tunnel",
        "deprecatedFallback": "none",
        "repoRoot": str(config.repo_root),
        "profile": profile,
        "tunnelId": effective_tunnel_id,
        "tunnelIdInput": {key: value for key, value in tunnel_id_status.items() if key != "value"},
        "mcpCommand": mcp_command,
        "commands": {
            "setApiKeyCmd": 'set "CONTROL_PLANE_API_KEY=<runtime API key with Tunnels Read + Use>"',
            "setApiKeyEnvVar": "CONTROL_PLANE_API_KEY=<runtime API key with Tunnels Read + Use>",
            "init": init_command,
            "doctor": doctor_command,
            "run": run_command_args,
        },
        "commandLines": {
            "init": command_line(init_command),
            "doctor": command_line(doctor_command),
            "run": command_line(run_command_args),
        },
        "openAiRequirements": {
            "tunnelId": "Create or select one in OpenAI Platform tunnel settings.",
            "runtimeApiKey": "CONTROL_PLANE_API_KEY principal needs Tunnels Read + Use for the target tunnel.",
            "managerPermission": "Tunnels Read + Manage is needed only to create or edit tunnel metadata.",
            "network": "The tunnel-client host needs outbound HTTPS to api.openai.com:443 and local reachability to the stdio MCP command.",
            "adminHealth": "Use tunnel-client doctor plus the local /ui, /healthz, and /readyz surfaces before ChatGPT smoke testing.",
        },
        "tunnelClientDiscovery": {
            "explicitFlag": "--tunnel-client-path",
            "environmentVariables": ["TUNNEL_CLIENT_PATH", "OPENAI_TUNNEL_CLIENT_PATH", "TUNNEL_CLIENT", "OPENAI_TUNNEL_CLIENT"],
            "adminlessSharedToolsPath": r"C:\RIFT MODDING\Tools\OpenAI\tunnel-client\tunnel-client.exe",
            "repoLocalFallbackPath": str(config.repo_root / ".riftreader-local" / "tools" / "openai" / "tunnel-client" / "tunnel-client.exe"),
        },
        "chatGptConnector": {
            "name": "rift-mcp",
            "connectionMode": "Tunnel",
            "retired": True,
            "notFallback": True,
            "toolSmokeOrder": ["health", "get_repo_status", "get_latest_handoff"],
            "notes": [
                "This path is retired for the RiftReader ChatGPT Web/Desktop lane and is not a fallback.",
                "Use --manual-public-ip-plan for the active Server URL path.",
            ],
        },
        "dependencies": {
            "tunnelClient": tunnel_client_status,
        },
        "blockers": blockers,
        "warnings": [
            "This plan does not create a tunnel, create credentials, register ChatGPT, mutate Git, send RIFT input, or expose broad local tools.",
            "CONTROL_PLANE_API_KEY is intentionally shown as a placeholder; do not store or commit it.",
            "OpenAI Secure MCP Tunnel, trycloudflare quick tunnels, and Caddy/router paths are retired for this repo lane and are not fallback paths.",
        ],
        "safety": {
            **base_safety(),
            "publicTunnelStarted": False,
            "openAiSecureTunnelRetired": True,
            "credentialPlaceholderOnly": True,
            "cloudflareTunnelRetired": True,
            "mcpTransport": "stdio",
            "chatGptRegistrationPerformed": False,
        },
        "docs": {
            "openaiSecureMcpTunnel": "https://developers.openai.com/api/docs/guides/secure-mcp-tunnels",
            "connectFromChatGpt": "https://developers.openai.com/api/docs/guides/secure-mcp-tunnels#connect-from-chatgpt",
            "platformTunnelSettings": "https://platform.openai.com/settings/organization/tunnels",
            "tunnelClientLatestRelease": "https://github.com/openai/tunnel-client/releases/latest",
            "chatGptConnectorSettings": "https://chatgpt.com/#settings/Connectors",
        },
    }
    secret_findings = find_secret_like_values(payload)
    payload["secretLeakCheck"] = {
        "status": "passed" if not secret_findings else "blocked",
        "ok": not secret_findings,
        "findings": secret_findings,
    }
    if secret_findings:
        payload["blockers"] = [*payload["blockers"], "secure-tunnel-plan-secret-like-value-detected"]
        payload["status"] = "blocked"
        payload["ok"] = False
    return payload


def repo_script_command(config: AdapterConfig, script_name: str, args: list[str]) -> list[str]:
    return [str(config.repo_root / "scripts" / script_name), *args]


MANUAL_PUBLIC_IP_PLACEHOLDER = "CURRENT_EXTERNAL_IP_OR_DDNS_HOST"
DEFAULT_DOMAIN_PUBLIC_MCP_HOST = "mcp.360madden.com"
DEFAULT_CLOUDFLARE_NAMED_TUNNEL = "riftreader-mcp-360madden"
DEFAULT_CLOUDFLARE_BIC_RULE = "Disable BIC for RiftReader MCP endpoint"


def normalize_manual_public_mcp_host(value: str | None) -> tuple[str, bool]:
    candidate = (value or "").strip()
    if not candidate or candidate == MANUAL_PUBLIC_IP_PLACEHOLDER:
        return MANUAL_PUBLIC_IP_PLACEHOLDER, True
    return validate_public_host_value(candidate, field_name="public MCP host"), False


def build_manual_public_ip_plan(config: AdapterConfig, *, public_mcp_host: str | None = None) -> dict[str, Any]:
    """Return a plan-only packet for the operator-managed public-host MCP route.

    The CLI flag name is kept for compatibility with existing workflow callers,
    but the canonical route for ``mcp.360madden.com`` is now the persistent
    Cloudflare named Tunnel. The old Caddy/router/direct-public-IP path is
    represented as deprecated legacy context only.
    """
    public_host, placeholder = normalize_manual_public_mcp_host(public_mcp_host)
    public_url = f"https://{public_host}/mcp"
    allowed_host = "<current-external-ip-or-host>" if placeholder else public_host
    is_canonical_domain = (not placeholder) and public_host.lower() == DEFAULT_DOMAIN_PUBLIC_MCP_HOST
    route_key = "cloudflare-named-tunnel" if is_canonical_domain else "legacy-public-host"
    local_serve_command = repo_script_command(
        config,
        "riftreader-chatgpt-mcp.cmd",
        [
            "--serve",
            "--host",
            DEFAULT_HOST,
            "--port",
            str(DEFAULT_PORT),
            "--transport",
            "streamable-http",
            "--allowed-host",
            allowed_host,
            "--allowed-origin",
            DEFAULT_CHATGPT_ORIGIN,
        ],
    )
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-manual-public-ip-plan",
        "generatedAtUtc": utc_iso(),
        "status": "ready-template" if placeholder else "ready",
        "ok": True,
        "service": SERVER_NAME,
        "version": VERSION,
        "repoRoot": str(config.repo_root),
        "activePath": {
            "key": route_key,
            "legacyCliAlias": "--manual-public-ip-plan",
            "publicHostKind": "placeholder" if placeholder else ("raw-ip" if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", public_host) else "domain-or-ddns-host"),
            "connectionMode": "Server URL",
            "chatGptAuthentication": "No Authentication",
            "publicMcpUrl": public_url,
            "operatorMustEditChatGptAppWhenIpChanges": not is_canonical_domain,
            "why": (
                "Canonical current path: ChatGPT uses the stable domain Server URL routed by the persistent "
                f"Cloudflare named Tunnel {DEFAULT_CLOUDFLARE_NAMED_TUNNEL} to the loopback MCP server."
                if is_canonical_domain
                else "Legacy public-host template retained for compatibility only; prefer mcp.360madden.com through the persistent Cloudflare named Tunnel."
            ),
        },
        "operatorInputs": {
            "publicMcpHost": public_host,
            "publicMcpHostPlaceholder": placeholder,
            "chatGptServerUrl": public_url,
            "cloudflareTunnelName": DEFAULT_CLOUDFLARE_NAMED_TUNNEL,
            "cloudflarePublishedApplicationRoute": f"{DEFAULT_DOMAIN_PUBLIC_MCP_HOST} -> http://{DEFAULT_HOST}:{DEFAULT_PORT}",
            "cloudflareBrowserIntegrityRule": DEFAULT_CLOUDFLARE_BIC_RULE,
            "reverseProxyTarget": f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp",
            "deprecatedRouterPortForward": "Deprecated legacy path: TCP 443 on the gateway -> local HTTPS reverse proxy.",
        },
        "localRuntime": {
            "mcpServerCommand": local_serve_command,
            "mcpServerCommandLine": command_line(local_serve_command),
            "mcpServerBindsLoopbackOnly": True,
            "expectedProcessesWhenRunning": ["python.exe", "cloudflared.exe-or-Cloudflared-Windows-service"],
            "notes": [
                "Keep the repo MCP server bound to 127.0.0.1; the persistent Cloudflare named Tunnel is the public bridge.",
                f"The Cloudflare published application for {DEFAULT_DOMAIN_PUBLIC_MCP_HOST} must target http://{DEFAULT_HOST}:{DEFAULT_PORT}.",
                "The ChatGPT Server URL remains https://mcp.360madden.com/mcp and uses No Authentication.",
                "The old Caddy/router/direct-public-IP path is deprecated legacy context; do not recreate it for this lane.",
            ],
        },
        "manualNetworkChecklist": [
            "Start the local MCP server outside Codex and keep that console/process running.",
            f"Confirm the Cloudflared Windows service for named tunnel {DEFAULT_CLOUDFLARE_NAMED_TUNNEL} is running.",
            f"Confirm Cloudflare Tunnel public hostname {DEFAULT_DOMAIN_PUBLIC_MCP_HOST} targets http://{DEFAULT_HOST}:{DEFAULT_PORT}.",
            f"Confirm Cloudflare DNS for {DEFAULT_DOMAIN_PUBLIC_MCP_HOST} points to the tunnel hostname and remains proxied.",
            f"Confirm the scoped Cloudflare Configuration Rule '{DEFAULT_CLOUDFLARE_BIC_RULE}' disables Browser Integrity Check for /mcp*.",
            "Create or edit the ChatGPT custom MCP app with https://mcp.360madden.com/mcp and No Authentication.",
            "Run scripts\\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json and require MCP initialize HTTP 200.",
        ],
        "retiredPaths": {
            "openAiSecureMcpTunnel": {
                "retired": True,
                "notFallback": True,
                "reason": "User-selected no-OpenAI-API-key workflow; do not route new work through tunnel-client.",
            },
            "cloudflareQuickTunnel": {
                "retired": True,
                "notFallback": True,
                "reason": "Ad hoc trycloudflare.com quick tunnels are not the stable ChatGPT Web/Desktop MCP route.",
            },
            "caddyRouter": {
                "deprecated": True,
                "notFallback": True,
                "reason": "The active route is the persistent Cloudflare named Tunnel; local Caddy/router forwarding is legacy and should not be recreated.",
            },
        },
        "doNotUse": [
            "Do not create duplicate launcher scripts before extending scripts\\riftreader-chatgpt-mcp.cmd.",
            "Do not start tunnel-client for this lane.",
            "Do not start ad hoc trycloudflare.com quick tunnels for this lane.",
            "Do not use Caddy/router/direct-public-IP forwarding as the default public proof route.",
            "Do not count a Codex-launched server/proxy as final non-Codex acceptance proof.",
            "Do not expose write, shell, Git mutation, RIFT input, CE, or x64dbg tools on a public No Auth endpoint.",
        ],
        "chatGptSmokeOrder": ["health", "get_repo_status", "get_latest_handoff"],
        "warnings": [
            "This plan does not start a server, start cloudflared, edit Cloudflare, register ChatGPT, mutate Git, send RIFT input, or attach CE/x64dbg.",
            "The public-host Server URL mode is intentionally simple but public. Keep the first exposed MCP tool surface narrow and low-risk.",
            "The Caddy/router/direct-public-IP path is deprecated; do not revive it unless a future explicit cleanup plan reverses this policy.",
        ],
        "blockers": [],
        "safety": {
            **base_safety(),
            "operatorOwnedRuntimeRequired": True,
            "codexLaunchedRuntimeAcceptedAsProof": False,
            "persistentServerStarted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "manualPublicIpPreferred": False,
            "cloudflareNamedTunnelPreferred": True,
            "openAiSecureTunnelRetired": True,
            "cloudflareQuickTunnelRetired": True,
            "cloudflareTunnelRetired": False,
            "caddyRouterDeprecated": True,
            "planOnly": True,
        },
    }
    return payload


def build_operator_launch_plan(config: AdapterConfig, *, session_seconds: float = 3600.0) -> dict[str, Any]:
    """Return a plan-only non-Codex launch packet without starting a server or tunnel."""
    cloudflare_named_tunnel_plan_command = repo_script_command(
        config,
        "riftreader-chatgpt-mcp.cmd",
        ["--manual-public-ip-plan", "--public-mcp-host", DEFAULT_DOMAIN_PUBLIC_MCP_HOST, "--json"],
    )
    retired_secure_plan_command = repo_script_command(config, "riftreader-chatgpt-mcp.cmd", ["--secure-tunnel-plan", "--json"])
    retired_cloudflare_trial_command = repo_script_command(
        config,
        "riftreader-chatgpt-mcp.cmd",
        ["--chatgpt-trial-session", "--chatgpt-session-seconds", str(int(session_seconds)), "--json"],
    )
    local_serve_command = repo_script_command(
        config,
        "riftreader-chatgpt-mcp.cmd",
        ["--serve", "--host", DEFAULT_HOST, "--port", str(DEFAULT_PORT), "--transport", "streamable-http"],
    )
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-operator-launch-plan",
        "generatedAtUtc": utc_iso(),
        "status": "ready",
        "ok": True,
        "service": SERVER_NAME,
        "version": VERSION,
        "purpose": "Plan-only operator-owned non-Codex ChatGPT Web/Desktop MCP launch guidance.",
        "nonCodexInvariant": {
            "operatorOwnedRuntimeRequired": True,
            "codexLaunchedRuntimeIsFinalProof": False,
            "savedChatGptAppStartsLocalServer": False,
            "existingLaunchersMustBeReused": True,
        },
        "existingEntrypoints": {
            "chatgptMcpWrapper": "scripts\\riftreader-chatgpt-mcp.cmd",
            "artifactBridgeTunnel": "scripts\\riftreader-bridge-tunnel-session.cmd",
            "mcpServer": "scripts\\riftreader-mcp-server.cmd",
            "mcpClient": "scripts\\riftreader-mcp-client.cmd",
        },
        "recommendedPath": {
            "key": "cloudflare-named-tunnel",
            "legacyCliAlias": "--manual-public-ip-plan",
            "command": cloudflare_named_tunnel_plan_command,
            "commandLine": command_line(cloudflare_named_tunnel_plan_command),
            "defaultPublicHost": DEFAULT_DOMAIN_PUBLIC_MCP_HOST,
            "why": f"Current selected Web/Desktop path: use https://{DEFAULT_DOMAIN_PUBLIC_MCP_HOST}/mcp through persistent Cloudflare named Tunnel {DEFAULT_CLOUDFLARE_NAMED_TUNNEL}, targeting http://{DEFAULT_HOST}:{DEFAULT_PORT}.",
            "startsRuntime": False,
            "requiresOperatorRunAfterPlan": True,
        },
        "prerequisiteChain": [
            "Operator-owned local MCP server process: scripts\\riftreader-chatgpt-mcp.cmd --serve ...",
            f"Persistent Cloudflare named Tunnel {DEFAULT_CLOUDFLARE_NAMED_TUNNEL} is healthy on this PC.",
            f"Cloudflare published application route maps {DEFAULT_DOMAIN_PUBLIC_MCP_HOST} to http://{DEFAULT_HOST}:{DEFAULT_PORT}.",
            f"Cloudflare DNS for {DEFAULT_DOMAIN_PUBLIC_MCP_HOST} points to the tunnel hostname and remains proxied.",
            f"Scoped Cloudflare Configuration Rule '{DEFAULT_CLOUDFLARE_BIC_RULE}' disables Browser Integrity Check for /mcp*.",
            "ChatGPT Web/Desktop Developer Mode app uses Server URL https://mcp.360madden.com/mcp with No Authentication.",
        ],
        "retiredPaths": {
            "openAiSecureMcpTunnel": {
                "key": "openai-secure-mcp-tunnel",
                "command": retired_secure_plan_command,
                "commandLine": command_line(retired_secure_plan_command),
                "retired": True,
                "notFallback": True,
            },
            "cloudflareQuickTunnel": {
                "key": "cloudflare-quick-tunnel",
                "command": retired_cloudflare_trial_command,
                "commandLine": command_line(retired_cloudflare_trial_command),
                "retired": True,
                "notFallback": True,
            },
        },
        "localOnlyServePath": {
            "key": "loopback-streamable-http",
            "command": local_serve_command,
            "commandLine": command_line(local_serve_command),
            "endpoint": f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp",
            "why": "Local-only development server. ChatGPT Web/Desktop reaches it through the persistent Cloudflare named Tunnel public hostname.",
            "startsRuntimeWhenOperatorRunsIt": True,
            "expectedProcessesWhenRunning": ["python.exe"],
        },
        "doNotUse": [
            "Do not create duplicate launcher scripts before extending scripts\\riftreader-chatgpt-mcp.cmd.",
            "Do not confuse scripts\\riftreader-bridge-tunnel-session.cmd with the narrow ChatGPT MCP adapter.",
            "Do not treat old trycloudflare.com URLs as active or backup endpoints.",
            "Do not count a Codex-launched server/tunnel as final non-Codex acceptance proof.",
            "Do not use Caddy/router/direct-public-IP forwarding as the default public proof route.",
            "Do not start tunnel-client or ad hoc trycloudflare quick tunnels for this lane.",
        ],
        "chatGptSmokeOrder": ["health", "get_repo_status", "get_latest_handoff"],
        "docs": {
            "mcpWorkflow": "docs\\workflow\\riftreader-chatgpt-mcp.md",
            "nonCodexWorkflow": "docs\\workflow\\non-codex-desktop-chatgpt-workflow.md",
            "finalReadiness": "docs\\workflow\\riftreader-chatgpt-mcp-final-readiness.md",
        },
        "warnings": [
            "This plan does not start a server, start cloudflared, edit Cloudflare, create credentials, register ChatGPT, mutate Git, send RIFT input, or attach CE/x64dbg.",
            "OpenAI Secure MCP Tunnel, trycloudflare quick tunnels, and the Caddy/router route are not backups.",
        ],
        "blockers": [],
        "safety": {
            **base_safety(),
            "operatorOwnedRuntimeRequired": True,
            "codexLaunchedRuntimeAcceptedAsProof": False,
            "persistentServerStarted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "manualPublicIpPreferred": False,
            "cloudflareNamedTunnelPreferred": True,
            "cloudflareTunnelRetired": False,
            "cloudflareQuickTunnelRetired": True,
            "caddyRouterDeprecated": True,
            "openAiSecureTunnelRetired": True,
            "planOnly": True,
        },
    }
    return payload


def write_secure_tunnel_plan_summary(config: AdapterConfig, payload: dict[str, Any]) -> Path:
    generated = str(payload.get("generatedAtUtc") or utc_iso()).replace("-", "").replace(":", "")
    safe_timestamp = generated.replace("T", "T").replace("Z", "Z")
    output_root = config.repo_root / ".riftreader-local" / "riftreader-chatgpt-mcp" / "transport-smoke"
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / f"{safe_timestamp}-secure-tunnel-plan.json"
    payload["artifactPaths"] = {"summaryJson": rel(config.repo_root, output_path)}
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def resolve_cloudflared_executable(value: str | None = None) -> Path:
    candidates: list[Path] = []
    if value:
        candidates.append(Path(value).expanduser())
    for found in (shutil.which("cloudflared.exe"), shutil.which("cloudflared")):
        if found:
            candidates.append(Path(found))
    candidates.extend(CLOUDFLARED_DEFAULT_PATHS)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AdapterError(
        "CLOUDFLARED_NOT_FOUND",
        "cloudflared executable was not found. Install cloudflared or pass --cloudflared-path.",
        status="failed",
        extra={"checked": [str(path) for path in candidates]},
    )


def resolve_curl_executable() -> str:
    for name in ("curl.exe", "curl"):
        found = shutil.which(name)
        if found:
            return found
    raise AdapterError("CURL_NOT_FOUND", "curl was not found on PATH; cannot run HTTPS tunnel smoke.", status="failed")


def parse_cloudflare_quick_tunnel_url(text: str) -> str | None:
    match = CLOUDFLARE_QUICK_TUNNEL_PATTERN.search(text)
    return match.group(0) if match else None


def host_from_https_url(url: str) -> str:
    match = re.fullmatch(r"https://([^/?#]+)(?:[/?#].*)?", url.strip())
    if not match:
        raise AdapterError("PUBLIC_TUNNEL_URL_INVALID", "Expected an https:// public tunnel URL.", status="failed", extra={"url": url})
    return match.group(1)


def parse_ipv4_addresses(text: str) -> list[str]:
    addresses: list[str] = []
    for match in re.finditer(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text):
        candidate = match.group(0)
        if candidate in addresses:
            continue
        if all(0 <= int(part) <= 255 for part in candidate.split(".")):
            addresses.append(candidate)
    return addresses


def resolve_ipv4_for_curl(host: str, *, timeout_seconds: float = 10.0) -> str | None:
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        return None
    commands = [
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Resolve-DnsName -Name '{host}' -Type A -ErrorAction Stop | Select-Object -ExpandProperty IPAddress",
        ],
        ["nslookup", "-type=A", host, "1.1.1.1"],
    ]
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        stdout = completed.stdout
        if command[0].lower() == "nslookup" and "Name:" in stdout:
            stdout = stdout.split("Name:", 1)[1]
        addresses = [address for address in parse_ipv4_addresses(stdout) if address != "1.1.1.1"]
        if addresses:
            return addresses[0]
    return None


def start_process_stream_readers(process: subprocess.Popen[str]) -> tuple[queue.Queue[tuple[str, str]], list[str], list[str]]:
    output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def reader(stream: Any, stream_name: str, sink: list[str]) -> None:
        try:
            if stream is None:
                return
            for line in stream:
                sink.append(line)
                output_queue.put((stream_name, line))
        except Exception as exc:  # pragma: no cover - diagnostic helper only.
            output_queue.put((stream_name, f"[stream-reader-error] {type(exc).__name__}: {exc}\n"))

    threading.Thread(target=reader, args=(process.stdout, "stdout", stdout_lines), daemon=True).start()
    threading.Thread(target=reader, args=(process.stderr, "stderr", stderr_lines), daemon=True).start()
    return output_queue, stdout_lines, stderr_lines


def stop_process(process: subprocess.Popen[str] | None, *, graceful_timeout_seconds: float = 5.0) -> bool:
    if process is None:
        return False
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=graceful_timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=graceful_timeout_seconds)
    return process.poll() is not None


def wait_for_cloudflare_quick_tunnel_url(
    process: subprocess.Popen[str],
    output_queue: queue.Queue[tuple[str, str]],
    *,
    timeout_seconds: float,
    stdout_lines: list[str],
    stderr_lines: list[str],
) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            combined = "".join(stdout_lines + stderr_lines)
            url = parse_cloudflare_quick_tunnel_url(combined)
            if url:
                return url
            raise AdapterError(
                "CLOUDFLARED_EXITED_BEFORE_URL",
                "cloudflared exited before printing a trycloudflare URL.",
                status="failed",
                extra={
                    "exitCode": process.returncode,
                    "stdoutTail": text_tail("".join(stdout_lines), 4000),
                    "stderrTail": text_tail("".join(stderr_lines), 4000),
                },
            )
        try:
            _stream_name, line = output_queue.get(timeout=0.25)
        except queue.Empty:
            continue
        url = parse_cloudflare_quick_tunnel_url(line)
        if url:
            return url
    raise AdapterError(
        "CLOUDFLARED_URL_TIMEOUT",
        "Timed out waiting for cloudflared to print a trycloudflare URL.",
        status="failed",
        extra={
            "timeoutSeconds": timeout_seconds,
            "stdoutTail": text_tail("".join(stdout_lines), 4000),
            "stderrTail": text_tail("".join(stderr_lines), 4000),
        },
    )


def http_status_from_headers(headers: str) -> int | None:
    status: int | None = None
    for line in headers.splitlines():
        match = re.match(r"^HTTP/\S+\s+(\d{3})\b", line.strip())
        if match:
            status = int(match.group(1))
    return status


def curl_json_rpc_request(
    *,
    curl_executable: str,
    url: str,
    request: dict[str, Any],
    timeout_seconds: float,
    temp_dir: Path,
    origin: str | None = None,
    resolve_host: str | None = None,
    resolve_ip: str | None = None,
) -> dict[str, Any]:
    request_id = request.get("id", "notification")
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(request_id))
    headers_path = temp_dir / f"headers-{safe_id}.txt"
    body_path = temp_dir / f"body-{safe_id}.json"
    command = [
        curl_executable,
        "-sS",
        "--show-error",
        "--max-time",
        str(timeout_seconds),
    ]
    if resolve_host and resolve_ip:
        command.extend(["--resolve", f"{resolve_host}:443:{resolve_ip}"])
    command.extend([
        "-D",
        str(headers_path),
        "-o",
        str(body_path),
        "-X",
        "POST",
        url,
        "-H",
        "Content-Type: application/json",
        "-H",
        "Accept: application/json, text/event-stream",
    ])
    if origin:
        command.extend(["-H", f"Origin: {origin}"])
    command.extend(["--data-binary", json.dumps(request, separators=(",", ":"))])
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=str(temp_dir),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds + 5,
        check=False,
    )
    duration = time.monotonic() - started
    headers = headers_path.read_text(encoding="utf-8", errors="replace") if headers_path.is_file() else ""
    body = body_path.read_text(encoding="utf-8", errors="replace") if body_path.is_file() else ""
    parsed: Any = None
    parse_error: str | None = None
    if body.strip():
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            parse_error = f"{type(exc).__name__}: {exc}"
    else:
        parse_error = "empty response body"
    return {
        "request": {"id": request.get("id"), "method": request.get("method")},
        "command": {
            "args": [command[0], *command[1:11], "...request-body-redacted"],
            "cwd": str(temp_dir),
        },
        "exitCode": completed.returncode,
        "durationSeconds": round(duration, 3),
        "httpStatus": http_status_from_headers(headers),
        "stdoutTail": text_tail(completed.stdout, 1000),
        "stderrTail": text_tail(completed.stderr, 4000),
        "headersTail": text_tail(headers, 4000),
        "bodyTail": text_tail(body, 4000),
        "json": parsed,
        "jsonParseError": parse_error,
    }


def result_json(result: dict[str, Any]) -> dict[str, Any] | None:
    value = result.get("json")
    return value if isinstance(value, dict) else None


def tool_call_structured_content(response: dict[str, Any]) -> tuple[bool | None, dict[str, Any] | None]:
    payload = result_json(response)
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return None, None
    structured = result.get("structuredContent")
    return bool(result.get("isError", False)), structured if isinstance(structured, dict) else None


def json_rpc_tool_call_request(request_id: int, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }


def cloudflare_smoke_client_result(
    *,
    curl_executable: str,
    url: str,
    timeout_seconds: float,
    temp_dir: Path,
    origin: str,
    resolve_host: str | None = None,
    resolve_ip: str | None = None,
    include_proposal_submit: bool = False,
) -> dict[str, Any]:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "riftreader-chatgpt-mcp-cloudflare-smoke", "version": VERSION},
            },
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "health", "arguments": {}}},
    ]
    responses = []
    for request in requests:
        responses.append(
            curl_json_rpc_request(
                curl_executable=curl_executable,
                url=url,
                request=request,
                timeout_seconds=timeout_seconds,
                temp_dir=temp_dir,
                origin=origin,
                resolve_host=resolve_host,
                resolve_ip=resolve_ip,
            )
        )
    tools_payload = result_json(responses[1])
    tools = []
    if tools_payload:
        tools_result = tools_payload.get("result")
        if isinstance(tools_result, dict):
            tools = [tool for tool in tools_result.get("tools", []) if isinstance(tool, dict)]
    registered = [
        {
            "name": tool.get("name"),
            "descriptionStartsUseThisWhen": str(tool.get("description") or "").startswith("Use this when"),
            "annotations": tool.get("annotations") if isinstance(tool.get("annotations"), dict) else {},
            "inputSchema": tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else None,
            "outputSchema": tool.get("outputSchema") if isinstance(tool.get("outputSchema"), dict) else None,
        }
        for tool in tools
    ]

    health_payload = result_json(responses[2])
    health_structured: Any = None
    health_is_error = None
    if health_payload:
        call_result = health_payload.get("result")
        if isinstance(call_result, dict):
            health_is_error = bool(call_result.get("isError", False))
            health_structured = call_result.get("structuredContent")

    submit_is_error = None
    submit_structured = None
    inbox_is_error = None
    inbox_structured = None
    draft_is_error = None
    draft_structured = None
    review_is_error = None
    review_structured = None
    dry_run_is_error = None
    dry_run_structured = None
    apply_without_approval_is_error = None
    apply_without_approval_structured = None
    if include_proposal_submit:
        submit_response = curl_json_rpc_request(
            curl_executable=curl_executable,
            url=url,
            request=json_rpc_tool_call_request(4, "submit_package_proposal", {"proposal": self_test_package_proposal()}),
            timeout_seconds=timeout_seconds,
            temp_dir=temp_dir,
            origin=origin,
            resolve_host=resolve_host,
            resolve_ip=resolve_ip,
        )
        responses.append(submit_response)
        submit_is_error, submit_structured = tool_call_structured_content(submit_response)

        inbox_response = curl_json_rpc_request(
            curl_executable=curl_executable,
            url=url,
            request=json_rpc_tool_call_request(5, "list_inbox", {}),
            timeout_seconds=timeout_seconds,
            temp_dir=temp_dir,
            origin=origin,
            resolve_host=resolve_host,
            resolve_ip=resolve_ip,
        )
        responses.append(inbox_response)
        inbox_is_error, inbox_structured = tool_call_structured_content(inbox_response)

        inbox_id = submit_structured.get("inboxId") if isinstance(submit_structured, dict) else None
        if isinstance(inbox_id, str) and inbox_id:
            draft_response = curl_json_rpc_request(
                curl_executable=curl_executable,
                url=url,
                request=json_rpc_tool_call_request(6, "create_package_draft_from_inbox", {"inboxId": inbox_id}),
                timeout_seconds=timeout_seconds,
                temp_dir=temp_dir,
                origin=origin,
                resolve_host=resolve_host,
                resolve_ip=resolve_ip,
            )
            responses.append(draft_response)
            draft_is_error, draft_structured = tool_call_structured_content(draft_response)

            review_response = curl_json_rpc_request(
                curl_executable=curl_executable,
                url=url,
                request=json_rpc_tool_call_request(7, "review_latest_package_draft", {"operatorOnly": False}),
                timeout_seconds=timeout_seconds,
                temp_dir=temp_dir,
                origin=origin,
                resolve_host=resolve_host,
                resolve_ip=resolve_ip,
            )
            responses.append(review_response)
            review_is_error, review_structured = tool_call_structured_content(review_response)

            dry_run_response = curl_json_rpc_request(
                curl_executable=curl_executable,
                url=url,
                request=json_rpc_tool_call_request(
                    8,
                    "dry_run_latest_package_draft",
                    {"operatorOnly": False, "timeoutSeconds": DEFAULT_DRY_RUN_TIMEOUT_SECONDS},
                ),
                timeout_seconds=timeout_seconds,
                temp_dir=temp_dir,
                origin=origin,
                resolve_host=resolve_host,
                resolve_ip=resolve_ip,
            )
            responses.append(dry_run_response)
            dry_run_is_error, dry_run_structured = tool_call_structured_content(dry_run_response)

            apply_without_approval_response = curl_json_rpc_request(
                curl_executable=curl_executable,
                url=url,
                request=json_rpc_tool_call_request(
                    9,
                    "apply_latest_package_draft",
                    {"operatorOnly": False, "timeoutSeconds": DEFAULT_DRY_RUN_TIMEOUT_SECONDS},
                ),
                timeout_seconds=timeout_seconds,
                temp_dir=temp_dir,
                origin=origin,
                resolve_host=resolve_host,
                resolve_ip=resolve_ip,
            )
            responses.append(apply_without_approval_response)
            apply_without_approval_is_error, apply_without_approval_structured = tool_call_structured_content(
                apply_without_approval_response
            )

    return {
        "responses": responses,
        "toolCount": len(tools),
        "toolNames": [tool.get("name") for tool in tools],
        "registeredTools": registered,
        "healthIsError": health_is_error,
        "healthStructuredContent": health_structured,
        "submitPackageProposalIsError": submit_is_error,
        "submitPackageProposalStructuredContent": submit_structured,
        "listInboxAfterSubmitIsError": inbox_is_error,
        "listInboxAfterSubmitStructuredContent": inbox_structured,
        "createPackageDraftIsError": draft_is_error,
        "createPackageDraftStructuredContent": draft_structured,
        "reviewLatestPackageDraftIsError": review_is_error,
        "reviewLatestPackageDraftStructuredContent": review_structured,
        "dryRunLatestPackageDraftIsError": dry_run_is_error,
        "dryRunLatestPackageDraftStructuredContent": dry_run_structured,
        "applyLatestPackageDraftWithoutApprovalIsError": apply_without_approval_is_error,
        "applyLatestPackageDraftWithoutApprovalStructuredContent": apply_without_approval_structured,
    }


def verify_cloudflare_smoke_client_result(client_result: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for response in client_result.get("responses") or []:
        request = response.get("request") if isinstance(response, dict) else {}
        label = request.get("method") if isinstance(request, dict) else "unknown"
        if response.get("exitCode") != 0:
            blockers.append(f"curl-exit:{label}:{response.get('exitCode')}")
        if response.get("httpStatus") != 200:
            blockers.append(f"http-status:{label}:{response.get('httpStatus')}")
        if response.get("jsonParseError"):
            blockers.append(f"json-parse:{label}:{response.get('jsonParseError')}")
        payload = result_json(response)
        if isinstance(payload, dict) and payload.get("error"):
            blockers.append(f"json-rpc-error:{label}:{payload.get('error')!r}")
    blockers.extend(verify_transport_smoke_result(client_result))
    return blockers


def run_cloudflare_tunnel_smoke_test(
    config: AdapterConfig,
    *,
    host: str = DEFAULT_HOST,
    timeout_seconds: float = DEFAULT_CLOUDFLARE_SMOKE_TIMEOUT_SECONDS,
    cloudflared_path: str | None = None,
    origin: str = DEFAULT_CHATGPT_ORIGIN,
) -> dict[str, Any]:
    if host != DEFAULT_HOST:
        raise AdapterError(
            "UNSAFE_BIND_HOST",
            "Cloudflare tunnel smoke keeps the MCP origin bound to 127.0.0.1 only.",
            status="failed",
            extra={"host": host},
        )
    if timeout_seconds <= 0 or timeout_seconds > 300:
        raise AdapterError(
            "CLOUDFLARE_SMOKE_TIMEOUT_INVALID",
            "Cloudflare tunnel smoke timeout must be > 0 and <= 300 seconds.",
            status="failed",
            extra={"timeoutSeconds": timeout_seconds},
        )

    sdk_path_additions = ensure_mcp_sdk_available(config.repo_root)
    normalized_origins = normalize_allowed_origins([origin])
    public_origin = normalized_origins[0]
    cloudflared_executable = resolve_cloudflared_executable(cloudflared_path)
    curl_executable = resolve_curl_executable()
    port = choose_loopback_port()
    local_origin = f"http://{host}:{port}"
    tunnel_command = [
        str(cloudflared_executable),
        "tunnel",
        "--url",
        local_origin,
        "--no-autoupdate",
        "--protocol",
        "quic",
        "--ha-connections",
        "1",
    ]
    tunnel_process: subprocess.Popen[str] | None = None
    server_process: subprocess.Popen[str] | None = None
    server_command: list[str] | None = None
    tunnel_stdout: list[str] = []
    tunnel_stderr: list[str] = []
    server_stdout = ""
    server_stderr = ""
    public_url: str | None = None
    public_host: str | None = None
    curl_resolve_ip: str | None = None
    client_result: dict[str, Any] = {"responses": []}
    blockers: list[str] = []
    status = "failed"
    ok = False
    server_stopped = False
    tunnel_stopped = False

    tmp_parent = smoke_artifact_root(config)
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cloudflare-smoke-", dir=str(tmp_parent)) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        try:
            tunnel_process = subprocess.Popen(
                tunnel_command,
                cwd=str(config.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            tunnel_queue, tunnel_stdout, tunnel_stderr = start_process_stream_readers(tunnel_process)
            public_url = wait_for_cloudflare_quick_tunnel_url(
                tunnel_process,
                tunnel_queue,
                timeout_seconds=min(timeout_seconds, 45.0),
                stdout_lines=tunnel_stdout,
                stderr_lines=tunnel_stderr,
            )
            public_host = host_from_https_url(public_url)
            curl_resolve_ip = resolve_ipv4_for_curl(public_host)
            script_path = Path(__file__).resolve()
            server_command = [
                sys.executable,
                str(script_path),
                "--serve",
                "--host",
                host,
                "--port",
                str(port),
                "--transport",
                "streamable-http",
                "--repo-root",
                str(config.repo_root),
                "--payload-root",
                str(config.payload_root),
                "--audit-root",
                str(config.audit_root),
                "--allowed-host",
                public_host,
                "--allowed-origin",
                public_origin,
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = build_child_pythonpath(config, env)
            server_process = subprocess.Popen(
                server_command,
                cwd=str(config.repo_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + timeout_seconds
            last_blockers: list[str] = []
            while time.monotonic() < deadline:
                if tunnel_process.poll() is not None:
                    raise AdapterError("CLOUDFLARED_EXITED_EARLY", "cloudflared exited during smoke test.", status="failed")
                if server_process.poll() is not None:
                    raise AdapterError(
                        "MCP_TRANSPORT_SERVER_EXITED_EARLY",
                        "MCP server exited during Cloudflare tunnel smoke.",
                        status="failed",
                        extra={"serverExitCode": server_process.returncode},
                    )
                if curl_resolve_ip is None:
                    curl_resolve_ip = resolve_ipv4_for_curl(public_host)
                client_result = cloudflare_smoke_client_result(
                    curl_executable=curl_executable,
                    url=f"{public_url}/mcp",
                    timeout_seconds=min(10.0, max(2.0, timeout_seconds / 6)),
                    temp_dir=temp_dir,
                    origin=public_origin,
                    resolve_host=public_host,
                    resolve_ip=curl_resolve_ip,
                )
                last_blockers = verify_cloudflare_smoke_client_result(client_result)
                if not last_blockers:
                    blockers = []
                    status = "passed"
                    ok = True
                    break
                blockers = last_blockers
                time.sleep(2.0)
            else:
                blockers = last_blockers or ["cloudflare-smoke-timeout"]
        except AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed with evidence.
            raise AdapterError(
                "CLOUDFLARE_SMOKE_FAILED",
                f"{type(exc).__name__}: {exc}",
                status="failed",
            ) from exc
        finally:
            server_stopped = stop_process(server_process)
            tunnel_stopped = stop_process(tunnel_process)
            if server_process is not None:
                try:
                    server_stdout, server_stderr = server_process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    server_process.kill()
                    server_stdout, server_stderr = server_process.communicate(timeout=2)
                    server_stopped = server_process.poll() is not None

    if not tunnel_stopped:
        blockers.append("cloudflared-not-stopped")
    if not server_stopped:
        blockers.append("temporary-server-not-stopped")
    if blockers:
        status = "failed"
        ok = False

    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-cloudflare-tunnel-smoke",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": ok,
        "service": SERVER_NAME,
        "version": VERSION,
        "publicUrl": public_url,
        "publicMcpUrl": f"{public_url}/mcp" if public_url else None,
        "publicHost": public_host,
        "originHeader": public_origin,
        "curlResolveIp": curl_resolve_ip,
        "localOrigin": local_origin,
        "host": host,
        "port": port,
        "timeoutSeconds": timeout_seconds,
        "client": client_result,
        "commands": {
            "cloudflared": {"args": tunnel_command, "cwd": str(config.repo_root)},
        },
        "processes": {
            "cloudflared": {
                "exitCodeAfterStop": tunnel_process.returncode if tunnel_process is not None else None,
                "stopped": tunnel_stopped,
                "stdoutTail": text_tail("".join(tunnel_stdout), 4000),
                "stderrTail": text_tail("".join(tunnel_stderr), 4000),
            },
            "server": {
                "exitCodeAfterStop": server_process.returncode if server_process is not None else None,
                "stopped": server_stopped,
                "stdoutTail": text_tail(server_stdout, 4000),
                "stderrTail": text_tail(server_stderr, 4000),
            },
        },
        "blockers": blockers,
        "warnings": [
            "This explicit smoke starts a temporary public Cloudflare quick tunnel and temporary loopback MCP server, then stops both.",
            "It does not register the app in ChatGPT and does not expose broad filesystem, shell, Git, RIFT, CE, or x64dbg tools.",
            "Use the printed public /mcp URL only while the temporary tunnel is running; quick-tunnel URLs are ephemeral.",
        ],
        "safety": {
            **base_safety(),
            "temporaryLoopbackServerStarted": server_process is not None,
            "serverStopped": server_stopped,
            "temporaryPublicTunnelStarted": tunnel_process is not None,
            "publicTunnelStopped": tunnel_stopped,
            "chatGptRegistrationPerformed": False,
            "sdkPathAdditions": sdk_path_additions,
            "transport": "streamable-http",
            "allowedHostExact": public_host,
            "allowedOriginExact": public_origin,
            "originBoundToLoopbackOnly": host == DEFAULT_HOST,
        },
    }
    artifact = write_smoke_artifact(config, payload, prefix="cloudflare-tunnel-smoke")
    payload["artifactPaths"] = {"summaryJson": artifact}
    Path(config.repo_root / artifact).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def run_chatgpt_trial_session(
    config: AdapterConfig,
    *,
    host: str = DEFAULT_HOST,
    session_seconds: float = DEFAULT_CHATGPT_SESSION_SECONDS,
    verify_timeout_seconds: float = DEFAULT_CLOUDFLARE_SMOKE_TIMEOUT_SECONDS,
    cloudflared_path: str | None = None,
    origin: str = DEFAULT_CHATGPT_ORIGIN,
) -> dict[str, Any]:
    if host != DEFAULT_HOST:
        raise AdapterError(
            "UNSAFE_BIND_HOST",
            "ChatGPT trial session keeps the MCP origin bound to 127.0.0.1 only.",
            status="failed",
            extra={"host": host},
        )
    if session_seconds < 0 or session_seconds > 3600:
        raise AdapterError(
            "CHATGPT_SESSION_SECONDS_INVALID",
            "ChatGPT trial session duration must be between 0 and 3600 seconds.",
            status="failed",
            extra={"sessionSeconds": session_seconds},
        )
    if verify_timeout_seconds <= 0 or verify_timeout_seconds > 300:
        raise AdapterError(
            "CHATGPT_SESSION_VERIFY_TIMEOUT_INVALID",
            "ChatGPT trial session verify timeout must be > 0 and <= 300 seconds.",
            status="failed",
            extra={"verifyTimeoutSeconds": verify_timeout_seconds},
        )

    sdk_path_additions = ensure_mcp_sdk_available(config.repo_root)
    normalized_origins = normalize_allowed_origins([origin])
    public_origin = normalized_origins[0]
    cloudflared_executable = resolve_cloudflared_executable(cloudflared_path)
    curl_executable = resolve_curl_executable()
    port = choose_loopback_port()
    local_origin = f"http://{host}:{port}"
    tunnel_command = [
        str(cloudflared_executable),
        "tunnel",
        "--url",
        local_origin,
        "--no-autoupdate",
        "--protocol",
        "quic",
        "--ha-connections",
        "1",
    ]
    tunnel_process: subprocess.Popen[str] | None = None
    server_process: subprocess.Popen[str] | None = None
    server_command: list[str] | None = None
    tunnel_stdout: list[str] = []
    tunnel_stderr: list[str] = []
    server_stdout = ""
    server_stderr = ""
    public_url: str | None = None
    public_host: str | None = None
    curl_resolve_ip: str | None = None
    client_result: dict[str, Any] = {"responses": []}
    resolved_diagnostic_client_result: dict[str, Any] = {"responses": []}
    blockers: list[str] = []
    ready = False
    ready_artifact: str | None = None
    ready_at_utc: str | None = None
    held_seconds = 0.0
    server_stopped = False
    tunnel_stopped = False
    status = "failed"
    ok = False

    tmp_parent = smoke_artifact_root(config)
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="chatgpt-trial-session-", dir=str(tmp_parent)) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        try:
            tunnel_process = subprocess.Popen(
                tunnel_command,
                cwd=str(config.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            tunnel_queue, tunnel_stdout, tunnel_stderr = start_process_stream_readers(tunnel_process)
            public_url = wait_for_cloudflare_quick_tunnel_url(
                tunnel_process,
                tunnel_queue,
                timeout_seconds=min(verify_timeout_seconds, 45.0),
                stdout_lines=tunnel_stdout,
                stderr_lines=tunnel_stderr,
            )
            public_host = host_from_https_url(public_url)
            curl_resolve_ip = resolve_ipv4_for_curl(public_host)
            script_path = Path(__file__).resolve()
            server_command = [
                sys.executable,
                str(script_path),
                "--serve",
                "--host",
                host,
                "--port",
                str(port),
                "--transport",
                "streamable-http",
                "--repo-root",
                str(config.repo_root),
                "--payload-root",
                str(config.payload_root),
                "--audit-root",
                str(config.audit_root),
                "--allowed-host",
                public_host,
                "--allowed-origin",
                public_origin,
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = build_child_pythonpath(config, env)
            server_process = subprocess.Popen(
                server_command,
                cwd=str(config.repo_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + verify_timeout_seconds
            last_blockers: list[str] = []
            while time.monotonic() < deadline:
                if tunnel_process.poll() is not None:
                    raise AdapterError("CLOUDFLARED_EXITED_EARLY", "cloudflared exited during ChatGPT trial session setup.", status="failed")
                if server_process.poll() is not None:
                    raise AdapterError(
                        "MCP_TRANSPORT_SERVER_EXITED_EARLY",
                        "MCP server exited during ChatGPT trial session setup.",
                        status="failed",
                        extra={"serverExitCode": server_process.returncode},
                    )
                if curl_resolve_ip is None:
                    curl_resolve_ip = resolve_ipv4_for_curl(public_host)
                # ChatGPT will use ordinary public DNS, not curl's
                # ``--resolve`` escape hatch.  The manual registration URL is
                # only useful if the same no-resolve path succeeds here.
                client_result = cloudflare_smoke_client_result(
                    curl_executable=curl_executable,
                    url=f"{public_url}/mcp",
                    timeout_seconds=min(10.0, max(2.0, verify_timeout_seconds / 6)),
                    temp_dir=temp_dir,
                    origin=public_origin,
                    include_proposal_submit=True,
                )
                last_blockers = verify_cloudflare_smoke_client_result(client_result)
                if not last_blockers:
                    ready = True
                    ready_at_utc = utc_iso()
                    break
                if curl_resolve_ip:
                    resolved_diagnostic_client_result = cloudflare_smoke_client_result(
                        curl_executable=curl_executable,
                        url=f"{public_url}/mcp",
                        timeout_seconds=min(10.0, max(2.0, verify_timeout_seconds / 6)),
                        temp_dir=temp_dir,
                        origin=public_origin,
                        resolve_host=public_host,
                        resolve_ip=curl_resolve_ip,
                        include_proposal_submit=False,
                    )
                    resolved_blockers = verify_cloudflare_smoke_client_result(resolved_diagnostic_client_result)
                    if not resolved_blockers:
                        last_blockers = [
                            "public-dns-path-failed-while-curl-resolve-path-passed",
                            *last_blockers,
                        ]
                last_blockers = last_blockers or ["chatgpt-session-public-verify-not-ready"]
                time.sleep(2.0)
            if not ready:
                blockers = last_blockers or ["chatgpt-session-public-verify-timeout"]
            else:
                ready_payload = {
                    "schemaVersion": SCHEMA_VERSION,
                    "kind": "riftreader-chatgpt-mcp-chatgpt-trial-session-ready",
                    "generatedAtUtc": ready_at_utc,
                    "status": "ready",
                    "ok": True,
                    "service": SERVER_NAME,
                    "version": VERSION,
                    "publicUrl": public_url,
                    "publicMcpUrl": f"{public_url}/mcp",
                    "publicHost": public_host,
                    "originHeader": public_origin,
                    "localOrigin": local_origin,
                    "host": host,
                    "port": port,
                    "sessionSeconds": session_seconds,
                    "curlResolveIp": curl_resolve_ip,
                    "publicDnsVerified": True,
                    "registration": {
                        "chatGptDeveloperMode": True,
                        "mcpUrl": f"{public_url}/mcp",
                        "protocol": "streamable-http",
                        "authentication": "No Authentication",
                        "firstToolToCall": "health",
                    },
                    "client": compact_stage_payload({"client": client_result}).get("client", {}),
                    "safety": {
                        **base_safety(),
                        "temporaryLoopbackServerStarted": True,
                        "temporaryPublicTunnelStarted": True,
                        "chatGptRegistrationPerformed": False,
                        "providerWrites": False,
                        "gitMutation": False,
                        "movementSent": False,
                        "inputSent": False,
                        "noCheatEngine": True,
                        "x64dbgAttach": False,
                        "sdkPathAdditions": sdk_path_additions,
                        "transport": "streamable-http",
                        "allowedHostExact": public_host,
                        "allowedOriginExact": public_origin,
                    },
                    "next": [
                        "In ChatGPT web, enable Developer mode under Settings -> Apps -> Advanced settings.",
                        "Create an app from this remote MCP URL while this session is still running.",
                        "Use No Authentication and streamable HTTP if prompted.",
                        "In a Developer Mode conversation, first call health and confirm the 12-tool surface.",
                        "For Stage 21 proof, call apply_latest_package_draft without approval and confirm APPLY_APPROVAL_MISSING.",
                    ],
                }
                ready_artifact = write_smoke_artifact(config, ready_payload, prefix="chatgpt-trial-session-ready")
                ready_payload["artifactPaths"] = {"summaryJson": ready_artifact}
                Path(config.repo_root / ready_artifact).write_text(json.dumps(ready_payload, indent=2, sort_keys=True), encoding="utf-8")

                hold_started = time.monotonic()
                hold_deadline = hold_started + session_seconds
                while time.monotonic() < hold_deadline:
                    if tunnel_process.poll() is not None:
                        blockers.append("cloudflared-exited-during-chatgpt-session")
                        break
                    if server_process.poll() is not None:
                        blockers.append("mcp-server-exited-during-chatgpt-session")
                        break
                    time.sleep(min(0.5, max(0.0, hold_deadline - time.monotonic())))
                held_seconds = time.monotonic() - hold_started
        except AdapterError:
            raise
        except KeyboardInterrupt:
            blockers.append("chatgpt-session-interrupted")
        except Exception as exc:  # noqa: BLE001 - fail closed with evidence.
            raise AdapterError(
                "CHATGPT_TRIAL_SESSION_FAILED",
                f"{type(exc).__name__}: {exc}",
                status="failed",
            ) from exc
        finally:
            server_stopped = stop_process(server_process)
            tunnel_stopped = stop_process(tunnel_process)
            if server_process is not None:
                try:
                    server_stdout, server_stderr = server_process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    server_process.kill()
                    server_stdout, server_stderr = server_process.communicate(timeout=2)
                    server_stopped = server_process.poll() is not None

    if not tunnel_stopped:
        blockers.append("cloudflared-not-stopped")
    if not server_stopped:
        blockers.append("temporary-server-not-stopped")
    if ready and not blockers:
        status = "passed"
        ok = True

    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-chatgpt-trial-session",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": ok,
        "ready": ready,
        "readyAtUtc": ready_at_utc,
        "service": SERVER_NAME,
        "version": VERSION,
        "publicUrl": public_url,
        "publicMcpUrl": f"{public_url}/mcp" if public_url else None,
        "publicHost": public_host,
        "originHeader": public_origin,
        "curlResolveIp": curl_resolve_ip,
        "localOrigin": local_origin,
        "host": host,
        "port": port,
        "sessionSeconds": session_seconds,
        "heldSeconds": round(held_seconds, 3),
        "verifyTimeoutSeconds": verify_timeout_seconds,
        "client": client_result,
        "resolvedDiagnosticClient": resolved_diagnostic_client_result,
        "commands": {
            "cloudflared": {"args": tunnel_command, "cwd": str(config.repo_root)},
            "server": {"args": server_command, "cwd": str(config.repo_root)},
        },
        "processes": {
            "cloudflared": {
                "exitCodeAfterStop": tunnel_process.returncode if tunnel_process is not None else None,
                "stopped": tunnel_stopped,
                "stdoutTail": text_tail("".join(tunnel_stdout), 4000),
                "stderrTail": text_tail("".join(tunnel_stderr), 4000),
            },
            "server": {
                "exitCodeAfterStop": server_process.returncode if server_process is not None else None,
                "stopped": server_stopped,
                "stdoutTail": text_tail(server_stdout, 4000),
                "stderrTail": text_tail(server_stderr, 4000),
            },
        },
        "registration": {
            "chatGptDeveloperMode": True,
            "mcpUrl": f"{public_url}/mcp" if public_url else None,
            "protocol": "streamable-http",
            "authentication": "No Authentication",
            "firstToolToCall": "health",
            "remainingManualStep": "Create the app in ChatGPT Developer Mode while this session is running.",
        },
        "blockers": blockers,
        "warnings": [
            "This starts a temporary public Cloudflare quick tunnel and temporary loopback MCP server for a bounded ChatGPT registration window.",
            "It does not register the app in ChatGPT automatically.",
            "It does not expose broad filesystem, shell, Git, RIFT, CE, or x64dbg tools.",
            "The public quick-tunnel URL is ephemeral and stops when this command exits.",
        ],
        "safety": {
            **base_safety(),
            "temporaryLoopbackServerStarted": server_process is not None,
            "serverStopped": server_stopped,
            "temporaryPublicTunnelStarted": tunnel_process is not None,
            "publicTunnelStopped": tunnel_stopped,
            "chatGptRegistrationPerformed": False,
            "sdkPathAdditions": sdk_path_additions,
            "transport": "streamable-http",
            "allowedHostExact": public_host,
            "allowedOriginExact": public_origin,
            "originBoundToLoopbackOnly": host == DEFAULT_HOST,
        },
        "artifactPaths": {
            "readyJson": ready_artifact,
        },
    }
    artifact = write_smoke_artifact(config, payload, prefix="chatgpt-trial-session")
    payload["artifactPaths"]["summaryJson"] = artifact
    Path(config.repo_root / artifact).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def create_fastmcp_server(
    adapter: RiftReaderChatGptMcpAdapter,
    *,
    host: str,
    port: int,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    tool_profile: str = TOOL_PROFILE_FULL,
):
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.server.transport_security import TransportSecuritySettings
        from mcp.types import ToolAnnotations
        from pydantic import BaseModel, ConfigDict, Field
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional SDK install.
        raise AdapterError(
            "MCP_PYTHON_SDK_MISSING",
            'Python package "mcp" with pydantic support is not installed. Install it before --serve, e.g. pip install "mcp[cli]".',
            status="failed",
        ) from exc

    class PackageProposalFile(BaseModel):
        """One UTF-8 text file proposed for later local package-draft review."""

        model_config = ConfigDict(extra="forbid")
        target: str = Field(
            ...,
            description="Repo-relative target path for a text file. Use forward slashes; allowed extensions are .md, .json, .jsonl, .csv, or .txt.",
        )
        content: str = Field(..., description="Full UTF-8 text content for the proposed file.")
        encoding: Literal["utf-8"] = Field("utf-8", description="Only utf-8 is accepted.")

    class PackageProposalCheck(BaseModel):
        """Optional package-intake dry-run check command descriptor."""

        model_config = ConfigDict(extra="forbid")
        name: str = Field(..., description="Short check name.")
        args: list[str] = Field(
            ...,
            description="Command arguments for a later local package-intake dry-run. This is not executed by submit_package_proposal.",
        )
        expectedExitCodes: list[int] = Field(default_factory=lambda: [0], description="Acceptable exit codes for the later dry-run check.")
        timeoutSeconds: float = Field(120, description="Per-check timeout in seconds for a later dry-run.")

    class PackageProposalPayload(BaseModel):
        """Inert package payload stored under the local inbox for later review."""

        model_config = ConfigDict(extra="forbid")
        packageName: str = Field(..., description="Operator-readable package name.")
        files: list[PackageProposalFile] = Field(
            ...,
            description="One to twenty UTF-8 text files proposed for later review; submit only stores them as an inbox proposal.",
        )
        checks: list[PackageProposalCheck] = Field(
            default_factory=list,
            description="Optional dry-run checks for later package intake. These are never executed by submit_package_proposal.",
        )

    class PackageProposal(BaseModel):
        """Exact package-proposal object accepted by submit_package_proposal."""

        model_config = ConfigDict(extra="forbid")
        schemaVersion: Literal[1] = Field(..., description="Must be 1.")
        kind: Literal["package-proposal"] = Field(..., description="Must be package-proposal.")
        title: str = Field(..., description="Short operator-readable proposal title.")
        body: str | None = Field(None, description="Optional human-readable proposal summary.")
        payload: PackageProposalPayload = Field(..., description="Inert package payload to store under .riftreader-local.")
        source: dict[str, Any] = Field(
            default_factory=lambda: {
                "tool": "Desktop ChatGPT",
                "context": "operator-approved package proposal for local draft export",
            },
            description="Optional source metadata. Must not contain credentials or secrets.",
        )
        metadata: dict[str, Any] = Field(
            default_factory=lambda: {"requiresHumanReview": True, "draftOnly": True},
            description="Optional metadata. Proposals remain inert and require local review.",
        )

    def annotations_for(spec: ToolSpec) -> Any:
        return ToolAnnotations(
            readOnlyHint=spec.read_only,
            destructiveHint=spec.destructive,
            openWorldHint=spec.open_world,
        )

    public_allowed_hosts = normalize_allowed_hosts(allowed_hosts)
    public_allowed_origins = normalize_allowed_origins(allowed_origins)
    tool_order = tool_order_for_profile(tool_profile)
    adapter.config.tool_profile = tool_profile
    transport_security = None
    if public_allowed_hosts or public_allowed_origins:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=default_transport_allowed_hosts() + public_allowed_hosts,
            allowed_origins=default_transport_allowed_origins() + public_allowed_origins,
        )

    mcp = FastMCP(
        SERVER_NAME,
        instructions=(
            "Narrow RiftReader MCP adapter for ChatGPT Web/Desktop Developer Mode only. "
            "For package-loop proof call get_package_proposal_template, submit_package_proposal, list_inbox, "
            "create_package_draft_from_inbox, review_latest_package_draft, dry_run_latest_package_draft, then "
            "apply_latest_package_draft without approvalToken. "
            "This is not ChatGPT Codex and not a broad local MCP proxy. Use only the exposed allowlisted tools. "
            "Do not ask this server for shell, arbitrary filesystem, remote Git mutation, branch rewrite, reset, clean, "
            "RIFT input, CE, x64dbg, or tunnel control; those tools are intentionally absent. "
            "The only Git mutation endpoint is commit_reviewed_slice, which requires a current local preflight approval token "
            "and can create one explicit-path local commit only. "
            f"Active tool profile: {tool_profile}."
        ),
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
        transport_security=transport_security,
    )

    def register(name: str, fn: Callable[..., dict[str, Any]]) -> None:
        spec = TOOL_SPECS[name]
        # Keep mandatory annotations while tolerating recent FastMCP decorator
        # signature differences. If the installed SDK cannot register
        # annotations, fail closed instead of exposing mislabeled tools.
        decorator_attempts = (
            {
                "name": spec.name,
                "title": spec.title,
                "description": spec.description,
                "annotations": annotations_for(spec),
                "structured_output": True,
            },
            {
                "name": spec.name,
                "title": spec.title,
                "description": spec.description,
                "annotations": annotations_for(spec),
            },
            {
                "name": spec.name,
                "description": spec.description,
                "annotations": annotations_for(spec),
            },
        )
        last_error: TypeError | None = None
        for kwargs in decorator_attempts:
            try:
                mcp.tool(**kwargs)(fn)
                return
            except TypeError as exc:
                last_error = exc
        raise AdapterError(
            "MCP_TOOL_REGISTRATION_FAILED",
            f"FastMCP rejected tool decorator signatures for {spec.name}: {last_error}",
            status="failed",
        )

    def health() -> dict[str, Any]:
        """Use this when you need RiftReader ChatGPT MCP health and safety boundaries."""

        return adapter.call_tool("health", {})

    def get_repo_status() -> dict[str, Any]:
        """Use this when you need compact current RiftReader repo/workflow truth."""

        return adapter.call_tool("get_repo_status", {})

    def get_latest_handoff() -> dict[str, Any]:
        """Use this when you need the newest allowlisted RiftReader handoff text."""

        return adapter.call_tool("get_latest_handoff", {})

    def get_workflow_control_summary() -> dict[str, Any]:
        """Use this when you need the smallest read-only repo workflow control summary."""

        return adapter.call_tool("get_workflow_control_summary", {})

    def get_package_proposal_template() -> dict[str, Any]:
        """Use this when you need the guarded package-proposal JSON template."""

        return adapter.call_tool("get_package_proposal_template", {})

    def submit_package_proposal(proposal: PackageProposal) -> dict[str, Any]:
        """Use this when the operator explicitly approves storing a package-proposal under .riftreader-local."""

        return adapter.call_tool("submit_package_proposal", {"proposal": model_to_plain_json(proposal)})

    # This module uses ``from __future__ import annotations``. FastMCP evaluates
    # function annotations with inspect.signature(eval_str=True), so nested
    # Pydantic model classes must be attached as concrete annotations.
    submit_package_proposal.__annotations__["proposal"] = PackageProposal

    def list_inbox() -> dict[str, Any]:
        """Use this when you need Local Artifact Bridge inbox metadata only."""

        return adapter.call_tool("list_inbox", {})

    def create_package_draft_from_inbox(inboxId: str) -> dict[str, Any]:  # noqa: N803 - MCP input name.
        """Use this when the operator explicitly approves creating an inert package draft from an inbox proposal."""

        return adapter.call_tool("create_package_draft_from_inbox", {"inboxId": inboxId})

    def review_latest_package_draft(operatorOnly: bool = True) -> dict[str, Any]:  # noqa: N803 - MCP input name.
        """Use this when you need the latest inert package draft summary before any dry-run."""

        return adapter.call_tool("review_latest_package_draft", {"operatorOnly": operatorOnly})

    def dry_run_latest_package_draft(
        operatorOnly: bool = True,  # noqa: N803 - MCP input name.
        timeoutSeconds: float | None = None,  # noqa: N803 - MCP input name.
    ) -> dict[str, Any]:
        """Use this when the operator explicitly approves dry-running the latest inert package draft."""

        return adapter.call_tool(
            "dry_run_latest_package_draft",
            {"operatorOnly": operatorOnly, "timeoutSeconds": timeoutSeconds},
        )

    def apply_latest_package_draft(
        operatorOnly: bool = True,  # noqa: N803 - MCP input name.
        dryRunSummaryPath: str | None = None,  # noqa: N803 - MCP input name.
        dryRunDiffSha256: str | None = None,  # noqa: N803 - MCP input name.
        approvalToken: str | None = None,  # noqa: N803 - MCP input name.
        timeoutSeconds: float | None = None,  # noqa: N803 - MCP input name.
    ) -> dict[str, Any]:
        """Use this only after a local operator supplies the apply preflight approval token."""

        return adapter.call_tool(
            "apply_latest_package_draft",
            {
                "operatorOnly": operatorOnly,
                "dryRunSummaryPath": dryRunSummaryPath,
                "dryRunDiffSha256": dryRunDiffSha256,
                "approvalToken": approvalToken,
                "timeoutSeconds": timeoutSeconds,
            },
        )

    def commit_reviewed_slice(
        expectedHead: str,  # noqa: N803 - MCP input name.
        paths: list[str],
        commitMessage: str,  # noqa: N803 - MCP input name.
        validationSummaryPath: str,  # noqa: N803 - MCP input name.
        validationDigest: str,  # noqa: N803 - MCP input name.
        approvalToken: str | None = None,  # noqa: N803 - MCP input name.
        timeoutSeconds: float | None = None,  # noqa: N803 - MCP input name.
    ) -> dict[str, Any]:
        """Use this only after a local operator supplies the commit preflight approval token."""

        return adapter.call_tool(
            "commit_reviewed_slice",
            {
                "expectedHead": expectedHead,
                "paths": paths,
                "commitMessage": commitMessage,
                "validationSummaryPath": validationSummaryPath,
                "validationDigest": validationDigest,
                "approvalToken": approvalToken,
                "timeoutSeconds": timeoutSeconds,
            },
        )

    def get_workflow_control_plan() -> dict[str, Any]:
        """Use this when you need a read-only repo workflow control plan."""

        return adapter.call_tool("get_workflow_control_plan", {})

    def get_dirty_paths() -> dict[str, Any]:
        """Use this when you need read-only Git dirty path status for RiftReader."""

        return adapter.call_tool("get_dirty_paths", {})

    def get_recent_commits(limit: int = 10) -> dict[str, Any]:
        """Use this when you need the latest local Git commits for RiftReader."""

        return adapter.call_tool("get_recent_commits", {"limit": limit})

    def repo_tree_tracked(
        prefix: str | None = None,
        depth: int | None = None,
        limit: int = MCP_REPO_TREE_DEFAULT_LIMIT,
        includeBlockedMeta: bool = False,  # noqa: N803 - MCP input name.
    ) -> dict[str, Any]:
        """Use this when you need a bounded inventory of git-tracked RiftReader text files."""

        return adapter.call_tool(
            "repo_tree_tracked",
            {
                "prefix": prefix,
                "depth": depth,
                "limit": limit,
                "includeBlockedMeta": includeBlockedMeta,
            },
        )

    def repo_search_tracked(
        query: str,
        caseSensitive: bool = False,  # noqa: N803 - MCP input name.
        regex: bool = False,
        maxMatches: int = MCP_REPO_SEARCH_DEFAULT_MATCHES,  # noqa: N803 - MCP input name.
        maxFileBytes: int = MCP_REPO_READ_FILE_DEFAULT_BYTES,  # noqa: N803 - MCP input name.
    ) -> dict[str, Any]:
        """Use this when you need bounded search over git-tracked RiftReader text files."""

        return adapter.call_tool(
            "repo_search_tracked",
            {
                "query": query,
                "caseSensitive": caseSensitive,
                "regex": regex,
                "maxMatches": maxMatches,
                "maxFileBytes": maxFileBytes,
            },
        )

    def repo_read_tracked_file(
        path: str,
        maxBytes: int = MCP_REPO_READ_FILE_DEFAULT_BYTES,  # noqa: N803 - MCP input name.
        includeSha256: bool = False,  # noqa: N803 - MCP input name.
    ) -> dict[str, Any]:
        """Use this when you need bounded content from one git-tracked RiftReader text file."""

        return adapter.call_tool(
            "repo_read_tracked_file",
            {"path": path, "maxBytes": maxBytes, "includeSha256": includeSha256},
        )

    def repo_read_many_tracked_files(
        paths: list[str],
        maxFileBytes: int = MCP_REPO_READ_FILE_DEFAULT_BYTES,  # noqa: N803 - MCP input name.
        maxTotalBytes: int = MCP_REPO_READ_TOTAL_DEFAULT_BYTES,  # noqa: N803 - MCP input name.
        maxFiles: int = MCP_REPO_READ_MANY_MAX_FILES,  # noqa: N803 - MCP input name.
    ) -> dict[str, Any]:
        """Use this when you need bounded content from several git-tracked RiftReader text files."""

        return adapter.call_tool(
            "repo_read_many_tracked_files",
            {
                "paths": paths,
                "maxFileBytes": maxFileBytes,
                "maxTotalBytes": maxTotalBytes,
                "maxFiles": maxFiles,
            },
        )

    def repo_context_pack(
        packName: str,  # noqa: N803 - MCP input name.
        maxFiles: int = MCP_REPO_CONTEXT_PACK_DEFAULT_FILES,  # noqa: N803 - MCP input name.
        maxFileBytes: int = MCP_REPO_READ_FILE_DEFAULT_BYTES,  # noqa: N803 - MCP input name.
        maxTotalBytes: int = MCP_REPO_READ_TOTAL_DEFAULT_BYTES,  # noqa: N803 - MCP input name.
    ) -> dict[str, Any]:
        """Use this when you need a predefined bounded git-tracked RiftReader context pack."""

        return adapter.call_tool(
            "repo_context_pack",
            {
                "packName": packName,
                "maxFiles": maxFiles,
                "maxFileBytes": maxFileBytes,
                "maxTotalBytes": maxTotalBytes,
            },
        )

    handlers = {
        "health": health,
        "get_repo_status": get_repo_status,
        "get_latest_handoff": get_latest_handoff,
        "get_workflow_control_summary": get_workflow_control_summary,
        "get_package_proposal_template": get_package_proposal_template,
        "submit_package_proposal": submit_package_proposal,
        "list_inbox": list_inbox,
        "create_package_draft_from_inbox": create_package_draft_from_inbox,
        "review_latest_package_draft": review_latest_package_draft,
        "dry_run_latest_package_draft": dry_run_latest_package_draft,
        "apply_latest_package_draft": apply_latest_package_draft,
        "commit_reviewed_slice": commit_reviewed_slice,
        "get_workflow_control_plan": get_workflow_control_plan,
        "get_dirty_paths": get_dirty_paths,
        "get_recent_commits": get_recent_commits,
        "repo_tree_tracked": repo_tree_tracked,
        "repo_search_tracked": repo_search_tracked,
        "repo_read_tracked_file": repo_read_tracked_file,
        "repo_read_many_tracked_files": repo_read_many_tracked_files,
        "repo_context_pack": repo_context_pack,
    }
    for tool_name in tool_order:
        register(tool_name, handlers[tool_name])
    return mcp


def print_payload(payload: dict[str, Any], *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(json.dumps(payload, indent=2, sort_keys=True))


def load_arguments_json(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    stripped = value.lstrip()
    if stripped.startswith(("{", "[")):
        payload = json.loads(value)
    else:
        try:
            path = Path(value)
            if path.is_file():
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                payload = json.loads(value)
        except OSError:
            payload = json.loads(value)
    return ensure_mapping(payload, "arguments")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Narrow RiftReader MCP adapter for Desktop ChatGPT Developer Mode.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tool-manifest", action="store_true", help="Print the allowlisted MCP tool manifest.")
    mode.add_argument("--self-test", action="store_true", help="Run local handler self-test without ChatGPT or tunnel.")
    mode.add_argument("--validate-sdk", action="store_true", help="Validate FastMCP SDK import/tool registration without serving.")
    mode.add_argument("--transport-smoke", action="store_true", help="Start a temporary loopback MCP server, smoke test it, then stop it.")
    mode.add_argument(
        "--proposal-transport-smoke",
        action="store_true",
        help="Start a temporary loopback MCP server, call submit_package_proposal with a synthetic local-only proposal, then stop it.",
    )
    mode.add_argument(
        "--trial-readiness",
        action="store_true",
        help="Run compact local MCP trial-readiness checks without starting a public tunnel or ChatGPT registration.",
    )
    mode.add_argument(
        "--secure-tunnel-plan",
        action="store_true",
        help="Retired: OpenAI Secure MCP Tunnel is no longer a RiftReader ChatGPT Web/Desktop fallback path.",
    )
    mode.add_argument(
        "--manual-public-ip-plan",
        action="store_true",
        help="Print the active Cloudflare named Tunnel Server URL plan. Does not start a server or configure networking.",
    )
    mode.add_argument(
        "--operator-launch-plan",
        action="store_true",
        help="Print non-Codex operator-owned launch guidance using existing scripts. Does not start a server or tunnel.",
    )
    mode.add_argument(
        "--cloudflare-tunnel-smoke",
        action="store_true",
        help="Retired: Cloudflare quick tunnels are no longer a RiftReader ChatGPT Web/Desktop fallback path.",
    )
    mode.add_argument(
        "--chatgpt-trial-session",
        action="store_true",
        help="Retired: bounded Cloudflare public MCP sessions are no longer a RiftReader ChatGPT Web/Desktop fallback path.",
    )
    mode.add_argument("--call", choices=EXPECTED_TOOL_ORDER, help="Call one local tool handler without starting a server.")
    mode.add_argument("--serve", action="store_true", help="Start the MCP server. Does not start a tunnel.")
    parser.add_argument("--arguments-json", default=None, help="JSON object or path for --call arguments.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root. Defaults to auto-detect.")
    parser.add_argument("--payload-root", default=str(DEFAULT_PAYLOAD_ROOT), help="Bridge payload root under repo.")
    parser.add_argument("--audit-root", default=str(DEFAULT_AUDIT_ROOT), help="Audit root under .riftreader-local.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Serve host for --serve. Only 127.0.0.1 is allowed.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Serve port for --serve.")
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        help="Extra exact Host header value allowed by MCP DNS rebinding protection for an explicit HTTPS tunnel.",
    )
    parser.add_argument(
        "--allowed-origin",
        action="append",
        default=[],
        help="Extra exact Origin allowed by MCP DNS rebinding protection, e.g. https://chatgpt.com.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http", "sse"),
        default="streamable-http",
        help="MCP transport for --serve.",
    )
    parser.add_argument(
        "--tool-profile",
        choices=TOOL_PROFILES,
        default=TOOL_PROFILE_FULL,
        help=(
            "MCP tool surface to expose. Default full preserves the current full tool path; "
            "public-read-only exposes only Phase 0 read-only proof tools."
        ),
    )
    parser.add_argument("--dry-run-timeout-seconds", type=float, default=DEFAULT_DRY_RUN_TIMEOUT_SECONDS)
    parser.add_argument("--transport-smoke-timeout-seconds", type=float, default=DEFAULT_TRANSPORT_SMOKE_TIMEOUT_SECONDS)
    parser.add_argument("--cloudflare-smoke-timeout-seconds", type=float, default=DEFAULT_CLOUDFLARE_SMOKE_TIMEOUT_SECONDS)
    parser.add_argument("--chatgpt-session-seconds", type=float, default=DEFAULT_CHATGPT_SESSION_SECONDS)
    parser.add_argument("--secure-tunnel-profile", default="riftreader-local-stdio")
    parser.add_argument("--secure-tunnel-id", default=None, help="Optional OpenAI Platform tunnel_id to include in --secure-tunnel-plan output.")
    parser.add_argument("--tunnel-client-path", default=None, help="Optional explicit path to OpenAI tunnel-client.")
    parser.add_argument(
        "--public-mcp-host",
        default=MANUAL_PUBLIC_IP_PLACEHOLDER,
        help="Bare public hostname for --manual-public-ip-plan; use mcp.360madden.com for the canonical Cloudflare named Tunnel route. Do not include scheme or path.",
    )
    parser.add_argument(
        "--cloudflare-smoke-origin",
        default=DEFAULT_CHATGPT_ORIGIN,
        help="Origin header to validate during --cloudflare-tunnel-smoke or --chatgpt-trial-session; defaults to ChatGPT web origin.",
    )
    parser.add_argument("--cloudflared-path", default=None, help="Retired Cloudflare path option; retained only for historical argument compatibility.")
    parser.add_argument("--max-inbox-mb", type=float, default=1.0)
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
        config = make_adapter_config(
            repo_root,
            payload_root=Path(args.payload_root),
            audit_root=Path(args.audit_root),
            dry_run_timeout_seconds=args.dry_run_timeout_seconds,
            max_inbox_bytes=int(args.max_inbox_mb * 1024 * 1024),
        )
        config.tool_profile = args.tool_profile
        if args.tool_manifest:
            payload = tool_manifest(args.tool_profile)
            print_payload(payload, json_mode=args.json)
            return 0
        if args.self_test:
            payload = run_self_test(config)
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 1
        if args.validate_sdk:
            payload = validate_sdk_registration(
                config,
                host=args.host,
                port=args.port,
                allowed_hosts=args.allowed_host,
                allowed_origins=args.allowed_origin,
                tool_profile=args.tool_profile,
            )
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 1
        if args.transport_smoke:
            payload = run_transport_smoke_test(
                config,
                host=args.host,
                transport=args.transport,
                timeout_seconds=args.transport_smoke_timeout_seconds,
                tool_profile=args.tool_profile,
            )
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 1
        if args.proposal_transport_smoke:
            payload = run_transport_smoke_test(
                config,
                host=args.host,
                transport=args.transport,
                timeout_seconds=args.transport_smoke_timeout_seconds,
                include_proposal_submit=True,
                tool_profile=args.tool_profile,
            )
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 1
        if args.trial_readiness:
            payload = run_trial_readiness(
                config,
                host=args.host,
                port=args.port,
                allowed_hosts=args.allowed_host,
                allowed_origins=args.allowed_origin,
                transport=args.transport,
                transport_timeout_seconds=args.transport_smoke_timeout_seconds,
                tunnel_client_path=args.tunnel_client_path,
                cloudflared_path=args.cloudflared_path,
            )
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 2
        if args.secure_tunnel_plan:
            payload = blocked_payload(
                "RETIRED_TRANSPORT_PATH",
                "OpenAI Secure MCP Tunnel is retired for the RiftReader ChatGPT Web/Desktop lane; use --manual-public-ip-plan.",
                kind="riftreader-chatgpt-mcp-retired-transport-path",
                status="blocked",
                extra={
                    "retiredPath": "openai-secure-mcp-tunnel",
                    "replacement": "--manual-public-ip-plan",
                    "notFallback": True,
                },
            )
            print_payload(payload, json_mode=args.json)
            return 2
        if args.manual_public_ip_plan:
            payload = build_manual_public_ip_plan(config, public_mcp_host=args.public_mcp_host)
            artifact = write_smoke_artifact(config, payload, prefix="manual-public-ip-plan")
            payload["artifactPaths"] = {"summaryJson": artifact}
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 2
        if args.operator_launch_plan:
            payload = build_operator_launch_plan(config, session_seconds=args.chatgpt_session_seconds)
            artifact = write_smoke_artifact(config, payload, prefix="operator-launch-plan")
            payload["artifactPaths"] = {"summaryJson": artifact}
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 2
        if args.cloudflare_tunnel_smoke:
            payload = blocked_payload(
                "RETIRED_TRANSPORT_PATH",
                "Cloudflare quick tunnel smoke is retired for the RiftReader ChatGPT Web/Desktop lane; use --manual-public-ip-plan.",
                kind="riftreader-chatgpt-mcp-retired-transport-path",
                status="blocked",
                extra={
                    "retiredPath": "cloudflare-quick-tunnel-smoke",
                    "replacement": "--manual-public-ip-plan",
                    "notFallback": True,
                },
            )
            print_payload(payload, json_mode=args.json)
            return 2
        if args.chatgpt_trial_session:
            payload = blocked_payload(
                "RETIRED_TRANSPORT_PATH",
                "Cloudflare ChatGPT trial sessions are retired for the RiftReader ChatGPT Web/Desktop lane; use --manual-public-ip-plan.",
                kind="riftreader-chatgpt-mcp-retired-transport-path",
                status="blocked",
                extra={
                    "retiredPath": "cloudflare-chatgpt-trial-session",
                    "replacement": "--manual-public-ip-plan",
                    "notFallback": True,
                },
            )
            print_payload(payload, json_mode=args.json)
            return 2
        if args.call:
            adapter = RiftReaderChatGptMcpAdapter(config)
            payload = adapter.call_tool(args.call, load_arguments_json(args.arguments_json))
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else (1 if payload.get("status") == "failed" else 2)
        if args.serve:
            ensure_mcp_sdk_available(config.repo_root)
            if args.host != DEFAULT_HOST:
                payload = blocked_payload(
                    "UNSAFE_BIND_HOST",
                    "The MVP MCP adapter only binds to 127.0.0.1. Use a manual HTTPS tunnel when needed.",
                    kind="riftreader-chatgpt-mcp-serve",
                    status="failed",
                    extra={"host": args.host},
                )
                print_payload(payload, json_mode=True)
                return 1
            adapter = RiftReaderChatGptMcpAdapter(config)
            mcp = create_fastmcp_server(
                adapter,
                host=args.host,
                port=args.port,
                allowed_hosts=args.allowed_host,
                allowed_origins=args.allowed_origin,
                tool_profile=args.tool_profile,
            )
            mcp.run(transport=args.transport)
            return 0
    except AdapterError as exc:
        payload = blocked_payload(
            exc.code,
            exc.message,
            kind="riftreader-chatgpt-mcp-error",
            status=exc.status,
            extra=exc.extra,
        )
        print_payload(payload, json_mode=True)
        return 1 if exc.status == "failed" else 2
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with JSON.
        payload = blocked_payload(
            "UNEXPECTED_CLI_ERROR",
            f"{type(exc).__name__}: {exc}",
            kind="riftreader-chatgpt-mcp-error",
            status="failed",
        )
        print_payload(payload, json_mode=True)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
