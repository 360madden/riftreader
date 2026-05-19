#!/usr/bin/env python3
"""Narrow RiftReader MCP adapter for Desktop ChatGPT Developer Mode.

This module intentionally exposes only a small allowlisted surface over the
existing Local Artifact Bridge, package-draft review, and workflow-status
helpers. It does not proxy broad local MCPs, does not expose shell/Git/live-game
actions, and keeps ChatGPT-originated writes under ``.riftreader-local``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from . import local_artifact_bridge as bridge
    from . import package_draft_review, status_packet
    from .common import find_repo_root, repo_rel as rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow import local_artifact_bridge as bridge
    from riftreader_workflow import package_draft_review, status_packet
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
VERSION = "0.1.0"
SERVER_NAME = "riftreader_chatgpt_mcp"
DEFAULT_PAYLOAD_ROOT = Path("artifacts") / "chatgpt-payloads"
DEFAULT_AUDIT_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "audit"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8770
DEFAULT_DRY_RUN_TIMEOUT_SECONDS = 180.0
DEFAULT_TRANSPORT_SMOKE_TIMEOUT_SECONDS = 30.0
MAX_HANDOFF_BYTES = 512 * 1024
BRIDGE_TOKEN = "riftreader-chatgpt-mcp-local"

EXPECTED_TOOL_ORDER = (
    "health",
    "get_repo_status",
    "get_latest_handoff",
    "get_package_proposal_template",
    "submit_package_proposal",
    "list_inbox",
    "review_latest_package_draft",
    "dry_run_latest_package_draft",
)


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
}


@dataclass
class AdapterConfig:
    repo_root: Path
    payload_root: Path
    audit_root: Path
    bridge_config: bridge.BridgeConfig
    dry_run_timeout_seconds: float = DEFAULT_DRY_RUN_TIMEOUT_SECONDS


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
        "noGitMutationEndpoint": True,
        "noRiftLiveInputEndpoint": True,
        "noTargetControlEndpoint": True,
        "noPersistentServerStartedByTool": True,
        "noTunnelStartedByTool": True,
        "chatGptOriginatedWritesLocalOnly": True,
    }


def json_size_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def text_tail(value: str, max_chars: int = 4000) -> str:
    if len(value) <= max_chars:
        return value
    return value[-max_chars:]


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


def summarize_tool_input(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "submit_package_proposal":
        proposal = arguments.get("proposal")
        if isinstance(proposal, dict):
            payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
            files = payload.get("files") if isinstance(payload, dict) else None
            checks = payload.get("checks") if isinstance(payload, dict) else None
            return {
                "proposalKind": proposal.get("kind"),
                "title": proposal.get("title"),
                "hasBody": isinstance(proposal.get("body"), str) and bool(str(proposal.get("body")).strip()),
                "fileCount": len(files) if isinstance(files, list) else None,
                "checkCount": len(checks) if isinstance(checks, list) else None,
                "jsonSizeBytes": json_size_bytes(proposal),
            }
        return {"proposalType": type(proposal).__name__}
    return {
        key: value
        for key, value in arguments.items()
        if isinstance(value, str | int | float | bool | type(None))
    }


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
        "draftId": draft.get("draftId"),
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
            self.write_audit(tool_name, {"argumentsType": type(arguments).__name__}, result)
            return result
        if tool_name not in TOOL_SPECS:
            result = blocked_payload(
                "TOOL_NOT_EXPOSED",
                f"Tool is not exposed by {SERVER_NAME}: {tool_name}",
                kind="riftreader-chatgpt-mcp-tool-result",
            )
            self.write_audit(tool_name, summarize_tool_input(tool_name, args), result)
            return result

        try:
            dispatch: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
                "health": lambda _: self.health(),
                "get_repo_status": lambda _: self.get_repo_status(),
                "get_latest_handoff": lambda _: self.get_latest_handoff(),
                "get_package_proposal_template": lambda _: self.get_package_proposal_template(),
                "submit_package_proposal": lambda call_args: self.submit_package_proposal(call_args.get("proposal")),
                "list_inbox": lambda _: self.list_inbox(),
                "review_latest_package_draft": lambda call_args: self.review_latest_package_draft(
                    operator_only=optional_bool(call_args.get("operatorOnly"), field_name="operatorOnly", default=True)
                ),
                "dry_run_latest_package_draft": lambda call_args: self.dry_run_latest_package_draft(
                    operator_only=optional_bool(call_args.get("operatorOnly"), field_name="operatorOnly", default=True),
                    timeout_seconds=bounded_timeout(call_args.get("timeoutSeconds"), self.config.dry_run_timeout_seconds),
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

        self.write_audit(tool_name, summarize_tool_input(tool_name, args), result)
        return result

    def health(self) -> dict[str, Any]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-health",
            "service": SERVER_NAME,
            "version": VERSION,
            "generatedAtUtc": utc_iso(),
            "status": "passed",
            "ok": True,
            "repoRoot": str(self.config.repo_root),
            "repoRootRelative": rel(self.config.repo_root, self.config.repo_root),
            "payloadRoot": rel(self.config.repo_root, self.config.payload_root),
            "auditRoot": rel(self.config.repo_root, self.config.audit_root),
            "toolCount": len(TOOL_SPECS),
            "tools": tool_manifest()["tools"],
            "safety": {
                **base_safety(),
                "auditUnderDotRiftReaderLocal": is_relative_to(self.config.audit_root, self.config.repo_root / ".riftreader-local"),
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

    def review_latest_package_draft(self, *, operator_only: bool = True) -> dict[str, Any]:
        payload = package_draft_review.latest_package_draft(self.config.repo_root, operator_only=operator_only)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-review-latest-package-draft",
            "generatedAtUtc": utc_iso(),
            "status": payload.get("status"),
            "ok": bool(payload.get("ok")),
            "operatorOnly": operator_only,
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
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-chatgpt-mcp-dry-run-latest-package-draft",
            "generatedAtUtc": utc_iso(),
            "status": payload.get("status"),
            "ok": bool(payload.get("ok")),
            "operatorOnly": operator_only,
            "timeoutSeconds": timeout,
            "dryRun": payload,
            "blockers": list(payload.get("blockers") or ([payload.get("code")] if payload.get("code") else [])),
            "warnings": list(payload.get("warnings") or []),
            "safety": {
                **base_safety(),
                "packageIntakeDryRunOnly": True,
                "applyFlagSent": False,
                "repoSourceMutationExpected": False,
            },
        }


def tool_manifest() -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-tool-manifest",
        "service": SERVER_NAME,
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "ok": True,
        "tools": [
            {
                "name": TOOL_SPECS[name].name,
                "title": TOOL_SPECS[name].title,
                "description": TOOL_SPECS[name].description,
                "annotations": TOOL_SPECS[name].annotation_payload(),
            }
            for name in EXPECTED_TOOL_ORDER
        ],
        "safety": base_safety(),
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
        stages["internal_create_self_test_draft"] = bridge.create_inbox_package_draft(config.bridge_config, inbox_id)
        if not stages["internal_create_self_test_draft"].get("ok"):
            blockers.append(
                "internal_create_self_test_draft:"
                f"{stages['internal_create_self_test_draft'].get('code') or stages['internal_create_self_test_draft'].get('status')}"
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


def verify_registered_sdk_tools(server: Any) -> list[dict[str, Any]]:
    registered_tools = list_registered_sdk_tools(server)
    summaries: list[dict[str, Any]] = []
    blockers: list[str] = []
    by_name: dict[str, Any] = {}
    for tool in registered_tools:
        name = getattr(tool, "name", None)
        if isinstance(name, str):
            by_name[name] = tool
    actual_names = list(by_name.keys())
    expected_names = list(EXPECTED_TOOL_ORDER)
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
        summaries.append(
            {
                "name": expected_name,
                "descriptionStartsUseThisWhen": str(description).startswith("Use this when"),
                "annotations": annotation_payload,
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
    if importlib.util.find_spec("mcp") is not None:
        return added
    local_sdk = local_mcp_sdk_validation_root(repo_root)
    if (local_sdk / "mcp" / "__init__.py").is_file():
        sys.path.insert(0, str(local_sdk))
        added.append(str(local_sdk))
    if importlib.util.find_spec("mcp") is None:
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


def validate_sdk_registration(config: AdapterConfig, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict[str, Any]:
    if host != DEFAULT_HOST:
        raise AdapterError(
            "UNSAFE_BIND_HOST",
            "The MVP MCP adapter only supports 127.0.0.1 for SDK validation and serving.",
            status="failed",
            extra={"host": host},
        )
    if port < 0 or port > 65535:
        raise AdapterError("INVALID_PORT", "Port must be in range 0-65535.", status="failed", extra={"port": port})
    adapter = RiftReaderChatGptMcpAdapter(config)
    server = create_fastmcp_server(adapter, host=host, port=port)
    registered_tools = verify_registered_sdk_tools(server)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-sdk-registration-validation",
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "ok": True,
        "service": SERVER_NAME,
        "version": VERSION,
        "serverClass": type(server).__name__,
        "toolCount": len(EXPECTED_TOOL_ORDER),
        "tools": tool_manifest()["tools"],
        "registeredTools": registered_tools,
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
            "serverStarted": False,
            "tunnelStarted": False,
        },
    }


async def run_transport_client_once(url: str) -> dict[str, Any]:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url, timeout=5, sse_read_timeout=10) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            health_result = await session.call_tool("health", {})
    tools = list(getattr(tools_result, "tools", []) or [])
    tool_names = [getattr(tool, "name", None) for tool in tools]
    registered_summaries = []
    for tool in tools:
        registered_summaries.append(
            {
                "name": getattr(tool, "name", None),
                "descriptionStartsUseThisWhen": str(getattr(tool, "description", "") or "").startswith("Use this when"),
                "annotations": actual_tool_annotation_payload(tool),
            }
        )
    return {
        "toolCount": len(tools),
        "toolNames": tool_names,
        "registeredTools": registered_summaries,
        "healthIsError": bool(getattr(health_result, "isError", False)),
        "healthStructuredContent": getattr(health_result, "structuredContent", None),
        "healthContentTypes": [type(item).__name__ for item in getattr(health_result, "content", []) or []],
    }


async def run_transport_client_with_retry(url: str, server_process: subprocess.Popen[str], timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    while time.monotonic() < deadline:
        if server_process.poll() is not None:
            raise AdapterError(
                "MCP_TRANSPORT_SERVER_EXITED_EARLY",
                "MCP server process exited before the transport smoke client could connect.",
                status="failed",
                extra={"serverExitCode": server_process.returncode, "lastClientError": last_error},
            )
        try:
            return await run_transport_client_once(url)
        except Exception as exc:  # noqa: BLE001 - retry until bounded timeout expires.
            last_error = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(0.5)
    raise AdapterError(
        "MCP_TRANSPORT_CLIENT_TIMEOUT",
        "Timed out waiting for MCP streamable HTTP client smoke test to pass.",
        status="failed",
        extra={"url": url, "timeoutSeconds": timeout_seconds, "lastClientError": last_error},
    )


def verify_transport_smoke_result(client_result: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected_names = list(EXPECTED_TOOL_ORDER)
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
        if health.get("toolCount") != len(EXPECTED_TOOL_ORDER):
            blockers.append(f"health-tool-count-mismatch:{health.get('toolCount')!r}")
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
    return blockers


def run_transport_smoke_test(
    config: AdapterConfig,
    *,
    host: str = DEFAULT_HOST,
    timeout_seconds: float = DEFAULT_TRANSPORT_SMOKE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if host != DEFAULT_HOST:
        raise AdapterError(
            "UNSAFE_BIND_HOST",
            "The transport smoke test only binds to 127.0.0.1.",
            status="failed",
            extra={"host": host},
        )
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise AdapterError(
            "TRANSPORT_SMOKE_TIMEOUT_INVALID",
            "Transport smoke timeout must be > 0 and <= 120 seconds.",
            status="failed",
            extra={"timeoutSeconds": timeout_seconds},
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
        "streamable-http",
        "--repo-root",
        str(config.repo_root),
        "--payload-root",
        str(config.payload_root),
        "--audit-root",
        str(config.audit_root),
    ]
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
        client_result = asyncio.run(run_transport_client_with_retry(url, process, timeout_seconds))
        blockers = verify_transport_smoke_result(client_result)
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
        "kind": "riftreader-chatgpt-mcp-transport-smoke",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": ok,
        "service": SERVER_NAME,
        "version": VERSION,
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
            "transport": "streamable-http",
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
        },
    }
    if not server_stopped:
        payload["status"] = "failed"
        payload["ok"] = False
        payload["blockers"] = list(payload["blockers"]) + ["temporary-server-not-stopped"]
    return payload


def create_fastmcp_server(adapter: RiftReaderChatGptMcpAdapter, *, host: str, port: int):
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional SDK install.
        raise AdapterError(
            "MCP_PYTHON_SDK_MISSING",
            'Python package "mcp" is not installed. Install it before --serve, e.g. pip install "mcp[cli]".',
            status="failed",
        ) from exc

    def annotations_for(spec: ToolSpec) -> Any:
        return ToolAnnotations(
            readOnlyHint=spec.read_only,
            destructiveHint=spec.destructive,
            openWorldHint=spec.open_world,
        )

    mcp = FastMCP(
        SERVER_NAME,
        instructions=(
            "Narrow RiftReader Desktop ChatGPT MCP adapter. Use only the exposed allowlisted tools. "
            "Do not ask this server for shell, arbitrary filesystem, Git mutation, RIFT input, CE, x64dbg, "
            "or tunnel control; those tools are intentionally absent."
        ),
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
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

    def get_package_proposal_template() -> dict[str, Any]:
        """Use this when you need the guarded package-proposal JSON template."""

        return adapter.call_tool("get_package_proposal_template", {})

    def submit_package_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
        """Use this when the operator explicitly approves storing a package-proposal under .riftreader-local."""

        return adapter.call_tool("submit_package_proposal", {"proposal": proposal})

    def list_inbox() -> dict[str, Any]:
        """Use this when you need Local Artifact Bridge inbox metadata only."""

        return adapter.call_tool("list_inbox", {})

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

    for tool_name, fn in (
        ("health", health),
        ("get_repo_status", get_repo_status),
        ("get_latest_handoff", get_latest_handoff),
        ("get_package_proposal_template", get_package_proposal_template),
        ("submit_package_proposal", submit_package_proposal),
        ("list_inbox", list_inbox),
        ("review_latest_package_draft", review_latest_package_draft),
        ("dry_run_latest_package_draft", dry_run_latest_package_draft),
    ):
        register(tool_name, fn)
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
    mode.add_argument("--call", choices=EXPECTED_TOOL_ORDER, help="Call one local tool handler without starting a server.")
    mode.add_argument("--serve", action="store_true", help="Start the MCP server. Does not start a tunnel.")
    parser.add_argument("--arguments-json", default=None, help="JSON object or path for --call arguments.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root. Defaults to auto-detect.")
    parser.add_argument("--payload-root", default=str(DEFAULT_PAYLOAD_ROOT), help="Bridge payload root under repo.")
    parser.add_argument("--audit-root", default=str(DEFAULT_AUDIT_ROOT), help="Audit root under .riftreader-local.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Serve host for --serve. Only 127.0.0.1 is allowed.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Serve port for --serve.")
    parser.add_argument(
        "--transport",
        choices=("streamable-http", "sse"),
        default="streamable-http",
        help="MCP transport for --serve.",
    )
    parser.add_argument("--dry-run-timeout-seconds", type=float, default=DEFAULT_DRY_RUN_TIMEOUT_SECONDS)
    parser.add_argument("--transport-smoke-timeout-seconds", type=float, default=DEFAULT_TRANSPORT_SMOKE_TIMEOUT_SECONDS)
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
        if args.tool_manifest:
            payload = tool_manifest()
            print_payload(payload, json_mode=args.json)
            return 0
        if args.self_test:
            payload = run_self_test(config)
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 1
        if args.validate_sdk:
            payload = validate_sdk_registration(config, host=args.host, port=args.port)
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 1
        if args.transport_smoke:
            payload = run_transport_smoke_test(config, host=args.host, timeout_seconds=args.transport_smoke_timeout_seconds)
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else 1
        if args.call:
            adapter = RiftReaderChatGptMcpAdapter(config)
            payload = adapter.call_tool(args.call, load_arguments_json(args.arguments_json))
            print_payload(payload, json_mode=args.json)
            return 0 if payload.get("ok") else (1 if payload.get("status") == "failed" else 2)
        if args.serve:
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
            mcp = create_fastmcp_server(adapter, host=args.host, port=args.port)
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
