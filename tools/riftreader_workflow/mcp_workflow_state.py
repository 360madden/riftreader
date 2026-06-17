#!/usr/bin/env python3
"""Shared MCP workflow artifact and state discovery for RiftReader helpers.

This module is intentionally local/offline and does not start servers, tunnels,
Git mutations, RIFT input, CE, or x64dbg. It reads repo-owned artifacts and
runs read-only Git inspection commands only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from .mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
    from .common import find_repo_root, repo_rel as rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
TRANSPORT_SMOKE_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "transport-smoke"
ACTUAL_CLIENT_PROOF_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "actual-client-proof"
PROOF_INPUT_TEMPLATE_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "proof-input-templates"
INBOX_ROOT = Path(".riftreader-local") / "artifact-bridge-inbox"
DRAFT_ROOT = Path(".riftreader-local") / "artifact-bridge-package-drafts"
PACKAGE_INTAKE_ROOT = Path(".riftreader-local") / "package-intake"
FRESHNESS_BUDGET_SECONDS = {
    "readiness": 6 * 60 * 60,
    "proposal-smoke": 6 * 60 * 60,
    "manual-public-ip-plan": 24 * 60 * 60,
    "cloudflare-smoke": 24 * 60 * 60,
    "trial-session": 24 * 60 * 60,
    "proof-input-template": 24 * 60 * 60,
    "actual-client-proof": 24 * 60 * 60,
}
CURRENT_PROOF_INPUT_CONNECTION_MODE = "cloudflare-named-tunnel"
CURRENT_PROOF_INPUT_TOOL_COUNT = EXPECTED_CHATGPT_MCP_TOOL_COUNT
CURRENT_PROOF_INPUT_REQUIRED_TOOLS = frozenset(EXPECTED_CHATGPT_MCP_TOOL_NAMES)

ARTIFACT_KINDS = (
    "readiness",
    "proposal-smoke",
    "manual-public-ip-plan",
    "secure-tunnel-plan",
    "cloudflare-smoke",
    "transport-smoke",
    "trial-session",
    "trial-session-ready",
    "trial-session-final",
    "proof-input-template",
    "actual-client-proof",
    "inbox",
    "draft",
    "dry-run",
)

DEFAULT_TIMELINE_KINDS = (
    "readiness",
    "proposal-smoke",
    "manual-public-ip-plan",
    "secure-tunnel-plan",
    "cloudflare-smoke",
    "transport-smoke",
    "trial-session",
    "proof-input-template",
    "actual-client-proof",
    "inbox",
    "draft",
    "dry-run",
)


def mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def artifact_age_seconds(path: Path) -> int:
    return max(0, int((datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)).total_seconds()))


def public_url_is_ephemeral(public_url: object) -> bool:
    value = str(public_url or "").lower()
    return ".trycloudflare.com" in value or ".ngrok-free.app" in value or ".ngrok.app" in value


def safe_load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - artifact browser must preserve malformed evidence.
        return None, f"json-invalid:{path}:{type(exc).__name__}:{exc}"
    if not isinstance(value, dict):
        return None, f"json-not-object:{path}"
    return value, None


def first_existing_json(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def summarize_payload(repo_root: Path, path: Path, payload: dict[str, Any], artifact_kind: str) -> dict[str, Any]:
    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    processes = payload.get("processes") if isinstance(payload.get("processes"), dict) else {}
    server_process = payload.get("serverProcess") if isinstance(payload.get("serverProcess"), dict) else {}
    server_process = server_process or (processes.get("server") if isinstance(processes.get("server"), dict) else {})
    tunnel_process = processes.get("cloudflared") if isinstance(processes.get("cloudflared"), dict) else {}
    artifact_paths = payload.get("artifactPaths") if isinstance(payload.get("artifactPaths"), dict) else payload.get("artifacts")
    client = payload.get("client") if isinstance(payload.get("client"), dict) else {}
    submit = client.get("submitPackageProposalStructuredContent") if isinstance(client.get("submitPackageProposalStructuredContent"), dict) else {}
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    proof = payload.get("proof") if isinstance(payload.get("proof"), dict) else {}
    proof_facts = payload if artifact_kind == "proof-input-template" else proof
    message_metadata = payload.get("messageMetadata") if isinstance(payload.get("messageMetadata"), dict) else {}
    message_source = payload.get("messageSource") if isinstance(payload.get("messageSource"), dict) else {}
    title = str(payload.get("messageTitle") or payload.get("title") or payload.get("packageName") or "")
    source_tool = str(message_source.get("tool") or "")
    self_test = bool(message_metadata.get("selfTest")) or "self-test" in title.lower() or "self-test" in source_tool.lower()
    status = payload.get("status")
    if status is None and artifact_kind == "inbox":
        status = "stored"
    if status is None and artifact_kind == "proof-input-template":
        status = "ready"
    ok = bool(payload.get("ok")) if "ok" in payload else status in {"passed", "created", "ready", "stored"}
    public_mcp_url = payload.get("publicMcpUrl") or proof.get("publicMcpUrl")
    public_tunnel_stopped = safety.get("publicTunnelStopped") if "publicTunnelStopped" in safety else tunnel_process.get("stopped")
    ephemeral_public_url = public_url_is_ephemeral(public_mcp_url)
    item = {
        "artifactKind": artifact_kind,
        "path": rel(repo_root, path),
        "fileName": path.name,
        "mtimeUtc": mtime_utc(path),
        "artifactAgeSeconds": artifact_age_seconds(path),
        "kind": payload.get("kind"),
        "status": status,
        "ok": ok,
        "generatedAtUtc": payload.get("generatedAtUtc"),
        "blockers": payload.get("blockers") if isinstance(payload.get("blockers"), list) else [],
        "warnings": payload.get("warnings") if isinstance(payload.get("warnings"), list) else [],
        "connectionMode": payload.get("connectionMode") or proof_facts.get("connectionMode"),
        "publicMcpUrl": public_mcp_url,
        "publicUrlEphemeral": ephemeral_public_url,
        "publicUrlExpectedExpired": bool(ephemeral_public_url and public_tunnel_stopped),
        "toolCount": payload.get("toolCount") or proof_facts.get("toolCount"),
        "toolNames": proof_facts.get("toolNames"),
        "toolOutputSchemasPresent": proof_facts.get("toolOutputSchemasPresent"),
        "toolOutputSchemaCount": proof_facts.get("toolOutputSchemaCount"),
        "toolOutputSchemaToolNames": proof_facts.get("toolOutputSchemaToolNames"),
        "inboxId": payload.get("inboxId") or submit.get("inboxId") or draft.get("inboxId") or proof_facts.get("inboxId"),
        "draftId": payload.get("draftId") or draft.get("draftId") or proof_facts.get("draftId"),
        "packageName": payload.get("packageName") or draft.get("packageName"),
        "messageTitle": payload.get("messageTitle") or payload.get("title"),
        "messageKind": payload.get("messageKind"),
        "selfTest": self_test,
        "origin": "self-test" if self_test else "operator-or-live",
        "dryRun": payload.get("dryRun"),
        "changedFileCount": payload.get("changedFileCount"),
        "serverStopped": safety.get("serverStopped") if "serverStopped" in safety else server_process.get("stopped"),
        "publicTunnelStopped": public_tunnel_stopped,
        "chatGptRegistrationPerformed": safety.get("chatGptRegistrationPerformed"),
        "chatGptRegistrationSucceeded": proof_facts.get("chatgptRegistrationSucceeded"),
        "clientTransportStatus": proof_facts.get("clientTransportStatus"),
        "healthCallSucceeded": proof_facts.get("healthCallSucceeded"),
        "templateFetched": proof_facts.get("templateFetched"),
        "submitPackageProposalSucceeded": proof_facts.get("submitPackageProposalSucceeded"),
        "listInboxSawInboxId": proof_facts.get("listInboxSawInboxId"),
        "createPackageDraftSucceeded": proof_facts.get("createPackageDraftSucceeded"),
        "reviewLatestPackageDraftSucceeded": proof_facts.get("reviewLatestPackageDraftSucceeded"),
        "reviewLatestPackageDraftReadOnly": proof_facts.get("reviewLatestPackageDraftReadOnly"),
        "dryRunSucceeded": proof_facts.get("dryRunSucceeded"),
        "dryRunDiffPreviewOk": proof_facts.get("dryRunDiffPreviewOk"),
        "dryRunDiffPreviewArtifactUnderPackageIntake": proof_facts.get("dryRunDiffPreviewArtifactUnderPackageIntake"),
        "dryRunDiffPreviewBoundedBytes": proof_facts.get("dryRunDiffPreviewBoundedBytes"),
        "dryRunDiffPreviewTextLength": proof_facts.get("dryRunDiffPreviewTextLength"),
        "dryRunDiffPreviewTruncated": proof_facts.get("dryRunDiffPreviewTruncated"),
        "applyLatestPackageDraftWithoutApprovalBlocked": proof_facts.get("applyLatestPackageDraftWithoutApprovalBlocked"),
        "applyLatestPackageDraftWithoutApprovalBlockers": proof_facts.get("applyLatestPackageDraftWithoutApprovalBlockers"),
        "applyLatestPackageDraftWithoutApprovalApplied": proof_facts.get("applyLatestPackageDraftWithoutApprovalApplied"),
        "proposalSubmitTransportCovered": safety.get("proposalSubmitTransportCovered"),
        "proposalSubmitWritesLocalInboxOnly": safety.get("proposalSubmitWritesLocalInboxOnly"),
        "artifactPaths": artifact_paths if isinstance(artifact_paths, dict) else {},
    }
    if artifact_kind == "proof-input-template":
        item["artifactPaths"] = {"proofInputJson": rel(repo_root, path)}
    if artifact_kind == "inbox" and not item["inboxId"]:
        item["inboxId"] = path.parent.name if path.name.endswith(".json") else path.name
    if artifact_kind == "draft" and not item["draftId"]:
        item["draftId"] = path.parent.name
    return item


def state_artifact_warnings(latest_artifacts: dict[str, dict[str, Any] | None]) -> list[str]:
    warnings: list[str] = []
    for kind, budget_seconds in FRESHNESS_BUDGET_SECONDS.items():
        item = latest_artifacts.get(kind)
        if not item:
            continue
        age_seconds = item.get("artifactAgeSeconds")
        if isinstance(age_seconds, int) and age_seconds > budget_seconds:
            warnings.append(f"artifact-age-exceeds-budget:{kind}:{age_seconds}s>{budget_seconds}s:{item.get('path')}")
    for kind in ("cloudflare-smoke", "trial-session", "actual-client-proof"):
        item = latest_artifacts.get(kind)
        if item and item.get("publicUrlExpectedExpired"):
            warnings.append(f"ephemeral-public-url-expected-expired:{kind}:{item.get('path')}")
    for kind in ("inbox", "draft"):
        item = latest_artifacts.get(kind)
        if item and item.get("selfTest"):
            warnings.append(f"latest-{kind}-is-self-test:{item.get('path')}")
    return warnings


def collect_json_file_artifacts(repo_root: Path, root_rel: Path, pattern: str, artifact_kind: str) -> tuple[list[dict[str, Any]], list[str]]:
    root = repo_root / root_rel
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not root.exists():
        return items, warnings
    if not root.is_dir():
        return items, [f"artifact-root-not-directory:{root_rel}"]
    for path in root.glob(pattern):
        if not path.is_file():
            continue
        payload, warning = safe_load_json(path)
        if warning:
            warnings.append(warning)
            items.append({
                "artifactKind": artifact_kind,
                "path": rel(repo_root, path),
                "fileName": path.name,
                "mtimeUtc": mtime_utc(path),
                "status": "failed",
                "ok": False,
                "blockers": [warning],
                "warnings": [],
            })
            continue
        assert payload is not None
        items.append(summarize_payload(repo_root, path, payload, artifact_kind))
    items.sort(key=lambda item: (str(item.get("mtimeUtc")), str(item.get("path"))))
    return items, warnings


def collect_directory_artifacts(
    repo_root: Path,
    root_rel: Path,
    artifact_kind: str,
    candidate_names: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[str]]:
    root = repo_root / root_rel
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not root.exists():
        return items, warnings
    if not root.is_dir():
        return items, [f"artifact-root-not-directory:{root_rel}"]
    for child in root.iterdir():
        if not child.is_dir():
            continue
        json_path = first_existing_json(child / name for name in candidate_names)
        if json_path is None:
            warnings.append(f"{artifact_kind}-summary-missing:{child.name}")
            continue
        payload, warning = safe_load_json(json_path)
        if warning:
            warnings.append(warning)
            items.append({
                "artifactKind": artifact_kind,
                "path": rel(repo_root, json_path),
                "fileName": json_path.name,
                "mtimeUtc": mtime_utc(json_path),
                "status": "failed",
                "ok": False,
                "blockers": [warning],
                "warnings": [],
            })
            continue
        assert payload is not None
        items.append(summarize_payload(repo_root, json_path, payload, artifact_kind))
    items.sort(key=lambda item: (str(item.get("mtimeUtc")), str(item.get("path"))))
    return items, warnings


def latest(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return items[-1] if items else None


def git_dirty_state(repo_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unknown",
        "ok": False,
        "branchLine": None,
        "dirty": False,
        "dirtyCount": 0,
        "entries": [],
        "diffStat": "",
        "warnings": [],
    }
    try:
        status = subprocess.run(
            ["git", "--no-pager", "status", "--short", "--branch", "--untracked-files=all"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        result["warnings"].append(f"git-status-failed:{type(exc).__name__}:{exc}")
        return result
    if status.returncode != 0:
        result["warnings"].append(f"git-status-exit:{status.returncode}:{status.stderr.strip()}")
        return result
    lines = [line.rstrip() for line in status.stdout.splitlines() if line.rstrip()]
    result["status"] = "passed"
    result["ok"] = True
    result["branchLine"] = lines[0] if lines else None
    entries: list[dict[str, Any]] = []
    for line in lines[1:]:
        status_code = line[:2]
        path = line[3:] if len(line) > 3 else ""
        entries.append({"status": status_code, "path": path, "slice": classify_dirty_path(path)})
    result["entries"] = entries
    result["dirtyCount"] = len(entries)
    result["dirty"] = bool(entries)
    try:
        diff = subprocess.run(
            ["git", "--no-pager", "diff", "--stat"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if diff.returncode == 0:
            result["diffStat"] = diff.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        result["warnings"].append(f"git-diff-stat-failed:{type(exc).__name__}:{exc}")
    return result


def classify_dirty_path(path: str) -> str:
    normalized = path.replace("/", "\\")
    lower = normalized.lower()
    if lower.startswith(".riftreader-local\\"):
        return "generated-ignored"
    if lower.startswith("docs\\handoffs\\"):
        return "handoff"
    if lower.startswith("docs\\workflow\\"):
        return "docs"
    if lower.startswith("scripts\\test_") or lower.startswith("scripts\\test-"):
        return "tests"
    if lower.startswith("scripts\\riftreader-") and lower.endswith(".cmd"):
        return "wrappers"
    if lower.startswith("tools\\riftreader_workflow\\"):
        if lower.endswith("operator_lite.py"):
            return "operator-lite"
        if "mcp" in lower or "chatgpt" in lower or "workflow_router" in lower or "commit_packager" in lower:
            return "mcp-code"
        return "workflow-code"
    return "unrelated"


def has_stageable_dirty(git_state: dict[str, Any]) -> bool:
    entries = git_state.get("entries") if isinstance(git_state.get("entries"), list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        slice_name = str(entry.get("slice") or classify_dirty_path(path))
        if path and slice_name not in {"generated-ignored", "unrelated"}:
            return True
    return False


def discover_actual_client_proofs(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    return collect_directory_artifacts(repo_root, ACTUAL_CLIENT_PROOF_ROOT, "actual-client-proof", ("proof.json",))


def discover_proof_input_templates(repo_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    return collect_directory_artifacts(repo_root, PROOF_INPUT_TEMPLATE_ROOT, "proof-input-template", ("proof-input.json",))


def discover_mcp_artifacts(repo_root: Path) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    warnings: list[str] = []
    by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in ARTIFACT_KINDS}
    patterns = {
        "readiness": "*-trial-readiness.json",
        "proposal-smoke": "*-proposal-transport-smoke.json",
        "manual-public-ip-plan": "*-manual-public-ip-plan.json",
        "cloudflare-smoke": "*-cloudflare-tunnel-smoke.json",
        "transport-smoke": "*-transport-smoke.json",
        "trial-session-ready": "*-chatgpt-trial-session-ready.json",
        "trial-session-final": "*-chatgpt-trial-session.json",
    }
    for kind, pattern in patterns.items():
        items, item_warnings = collect_json_file_artifacts(repo_root, TRANSPORT_SMOKE_ROOT, pattern, kind)
        if kind == "transport-smoke":
            items = [item for item in items if "-proposal-transport-smoke.json" not in str(item.get("path", ""))]
        by_kind[kind] = items
        warnings.extend(item_warnings)
    trial_items = [*by_kind["trial-session-ready"], *by_kind["trial-session-final"]]
    trial_items.sort(key=lambda item: (str(item.get("mtimeUtc")), str(item.get("path"))))
    by_kind["trial-session"] = trial_items
    secure_plan_items, secure_plan_warnings = collect_json_file_artifacts(
        repo_root,
        TRANSPORT_SMOKE_ROOT,
        "*secure-tunnel-plan*.json",
        "secure-tunnel-plan",
    )
    by_kind["secure-tunnel-plan"] = secure_plan_items
    warnings.extend(secure_plan_warnings)
    proof_items, proof_warnings = discover_actual_client_proofs(repo_root)
    by_kind["actual-client-proof"] = proof_items
    warnings.extend(proof_warnings)
    proof_template_items, proof_template_warnings = discover_proof_input_templates(repo_root)
    by_kind["proof-input-template"] = proof_template_items
    warnings.extend(proof_template_warnings)
    inbox_items, inbox_warnings = collect_directory_artifacts(repo_root, INBOX_ROOT, "inbox", ("metadata.json", "message.json"))
    by_kind["inbox"] = inbox_items
    warnings.extend(inbox_warnings)
    draft_items, draft_warnings = collect_directory_artifacts(repo_root, DRAFT_ROOT, "draft", ("summary.json",))
    by_kind["draft"] = draft_items
    warnings.extend(draft_warnings)
    dry_items, dry_warnings = collect_directory_artifacts(
        repo_root,
        PACKAGE_INTAKE_ROOT,
        "dry-run",
        ("compact-package-intake-summary.json", "package-intake-summary.json"),
    )
    by_kind["dry-run"] = dry_items
    warnings.extend(dry_warnings)
    return by_kind, warnings


def latest_by_kind(by_kind: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any] | None]:
    return {kind: latest(items) for kind, items in by_kind.items()}


def passed(item: dict[str, Any] | None) -> bool:
    if not item:
        return False
    return bool(item.get("ok")) and item.get("status") in {"passed", "created", "ready"}


def build_recommended_next_action(state: dict[str, Any]) -> dict[str, Any]:
    latest_artifacts = state.get("latestArtifacts") if isinstance(state.get("latestArtifacts"), dict) else {}
    git_state = state.get("gitDirtyState") if isinstance(state.get("gitDirtyState"), dict) else {}
    commands = standard_commands()
    if has_stageable_dirty(git_state) and passed(latest_artifacts.get("readiness")) and passed(latest_artifacts.get("proposal-smoke")):
        return action("safe-commit-plan", "Review explicit-path commit plan for the validated dirty MCP slice.", commands["safeCommitPlan"])
    if not passed(latest_artifacts.get("readiness")):
        return action("mcp-trial-readiness", "Run local MCP readiness before public or ChatGPT client work.", commands["mcpTrialReadiness"])
    if not passed(latest_artifacts.get("proposal-smoke")):
        return action("proposal-transport-smoke", "Prove guarded submit_package_proposal through local MCP transport.", commands["proposalTransportSmoke"])
    if not passed(latest_artifacts.get("manual-public-ip-plan")):
        return action(
            "cloudflare-named-tunnel-plan",
            "Prepare the Cloudflare named Tunnel Server URL plan before ChatGPT Web/Desktop connector work.",
            commands["manualPublicIpPlan"],
        )
    if not passed(latest_artifacts.get("actual-client-proof")):
        template_action = proof_input_template_next_action(latest_artifacts)
        if template_action["command"] != commands["trialProofTemplate"]:
            return template_action
        return action(
            "chatgpt-cloudflare-named-tunnel-proof",
            "Use the operator-managed Cloudflare named Tunnel Server URL for actual ChatGPT proof; OpenAI Secure MCP Tunnel, trycloudflare quick tunnels, and Caddy/router are retired.",
            commands["manualPublicIpPlan"],
        )
    if latest_artifacts.get("inbox") and not latest_artifacts.get("draft"):
        return action("inbox-to-draft", "Export the latest package-proposal inbox item into an inert draft.", commands["inboxPackageDraft"])
    if latest_artifacts.get("draft") and not passed(latest_artifacts.get("dry-run")):
        return action("draft-dry-run", "Dry-run the latest inert package draft without apply.", commands["dryRunLatestDraft"])
    return action("docs-or-commit", "Update handoff/docs or commit the validated actual-client proof slice.", commands["safeCommitPlan"])


def action(key: str, reason: str, command: list[str]) -> dict[str, Any]:
    return {"key": key, "reason": reason, "command": command}


def standard_commands() -> dict[str, list[str]]:
    return {
        "mcpMissionControl": ["scripts\\riftreader-mcp-mission-control.cmd", "--json"],
        "mcpPhase1Status": ["scripts\\riftreader-mcp-phase1.cmd", "--status", "--json"],
        "mcpPhase2Status": ["scripts\\riftreader-mcp-phase2.cmd", "--status", "--json"],
        "mcpPhase2CompactStatus": ["scripts\\riftreader-mcp-phase2.cmd", "--status", "--compact-json"],
        "mcpFinalStatus": ["scripts\\riftreader-mcp-final.cmd", "--status", "--json"],
        "mcpFinalCompactStatus": ["scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"],
        "mcpArtifactsLatest": ["scripts\\riftreader-mcp-artifacts.cmd", "--latest", "--json"],
        "mcpTrialReadiness": ["scripts\\riftreader-operator-lite.cmd", "--mcp-trial-readiness", "--json"],
        "proposalTransportSmoke": ["scripts\\riftreader-chatgpt-mcp.cmd", "--proposal-transport-smoke", "--json"],
        "manualPublicIpPlan": ["scripts\\riftreader-chatgpt-mcp.cmd", "--manual-public-ip-plan", "--json"],
        "secureTunnelPlanRetired": ["scripts\\riftreader-chatgpt-mcp.cmd", "--secure-tunnel-plan", "--json"],
        "cloudflareSmokeRetired": ["scripts\\riftreader-chatgpt-mcp.cmd", "--cloudflare-tunnel-smoke", "--json"],
        "chatGptTrialSessionRetired": ["scripts\\riftreader-chatgpt-mcp.cmd", "--chatgpt-trial-session", "--chatgpt-session-seconds", "900", "--json"],
        "inboxLatest": ["scripts\\riftreader-local-artifact-bridge.cmd", "--inbox-read-latest", "--json"],
        "inboxPackageDraft": ["scripts\\riftreader-local-artifact-bridge.cmd", "--inbox-package-draft", "--json"],
        "latestDraft": ["scripts\\riftreader-package-draft-review.cmd", "--latest", "--json"],
        "dryRunLatestDraft": ["scripts\\riftreader-package-draft-review.cmd", "--dry-run-latest", "--json"],
        "trialProofTemplate": ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--write-template", "--json"],
        "safeCommitPlan": ["scripts\\riftreader-safe-commit-packager.cmd", "--plan", "--json"],
        "workflowRouter": ["scripts\\riftreader-workflow-router.cmd", "--mcp", "--json"],
    }


def proof_input_template_check_command(item: dict[str, Any] | None) -> list[str] | None:
    """Return the read-only check command for a ready, fresh current proof-input template."""

    if not passed(item):
        return None
    age_seconds = item.get("artifactAgeSeconds")
    if not isinstance(age_seconds, int) or age_seconds > FRESHNESS_BUDGET_SECONDS["proof-input-template"]:
        return None
    if item.get("connectionMode") != CURRENT_PROOF_INPUT_CONNECTION_MODE:
        return None
    if item.get("toolCount") != CURRENT_PROOF_INPUT_TOOL_COUNT:
        return None
    if item.get("toolOutputSchemaCount") != CURRENT_PROOF_INPUT_TOOL_COUNT:
        return None
    tool_names = item.get("toolNames")
    output_schema_tool_names = item.get("toolOutputSchemaToolNames")
    if not isinstance(tool_names, list) or not CURRENT_PROOF_INPUT_REQUIRED_TOOLS.issubset(set(tool_names)):
        return None
    if not isinstance(output_schema_tool_names, list) or not CURRENT_PROOF_INPUT_REQUIRED_TOOLS.issubset(
        set(output_schema_tool_names)
    ):
        return None
    artifact_paths = item.get("artifactPaths") if isinstance(item.get("artifactPaths"), dict) else {}
    proof_input = artifact_paths.get("proofInputJson") or item.get("path")
    if not isinstance(proof_input, str) or not proof_input.strip():
        return None
    return ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--check-input", "--input", proof_input, "--json"]


def proof_input_template_next_action(latest_artifacts: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    """Prefer checking the latest fresh template over writing another one."""

    command = proof_input_template_check_command(latest_artifacts.get("proof-input-template"))
    if command:
        return action(
            "check-actual-client-proof-input",
            "Fill the latest fresh proof-input template with actual ChatGPT observations, then check it read-only before recording.",
            command,
        )
    return action(
        "record-actual-client-proof",
        "Actual ChatGPT Developer Mode proof is still required; write the current fillable proof template first.",
        standard_commands()["trialProofTemplate"],
    )


def build_mcp_workflow_state(repo_root: Path) -> dict[str, Any]:
    by_kind, warnings = discover_mcp_artifacts(repo_root)
    latest_artifacts = latest_by_kind(by_kind)
    git_state = git_dirty_state(repo_root)
    warnings.extend(git_state.get("warnings") or [])
    warnings.extend(state_artifact_warnings(latest_artifacts))
    counts = {kind: len(items) for kind, items in by_kind.items()}
    blockers: list[str] = []
    if not passed(latest_artifacts.get("readiness")):
        blockers.append("latest-readiness-not-passed")
    if not passed(latest_artifacts.get("proposal-smoke")):
        blockers.append("latest-proposal-smoke-not-passed")
    status = "ready" if not blockers else "blocked"
    state: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-workflow-state",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "ready",
        "repoRoot": str(repo_root),
        "blockers": blockers,
        "warnings": warnings,
        "latestArtifacts": latest_artifacts,
        "counts": counts,
        "gitDirtyState": git_state,
        "commands": standard_commands(),
        "safety": {
            **safety_flags(),
            "readOnlyArtifactDiscovery": True,
            "publicTunnelStarted": False,
            "persistentServerStarted": False,
            "chatGptRegistrationPerformed": False,
            "applyFlagSent": False,
        },
    }
    state["recommendedNextAction"] = build_recommended_next_action(state)
    return state


def artifact_timeline(repo_root: Path, *, kind: str | None = None, limit: int | None = None) -> dict[str, Any]:
    by_kind, warnings = discover_mcp_artifacts(repo_root)
    if kind:
        kinds = [kind]
    else:
        kinds = list(DEFAULT_TIMELINE_KINDS)
    unknown = [item for item in kinds if item not in by_kind]
    items: list[dict[str, Any]] = []
    for item_kind in kinds:
        items.extend(by_kind.get(item_kind, []))
    items.sort(key=lambda item: (str(item.get("mtimeUtc")), str(item.get("path"))), reverse=True)
    if limit is not None:
        items = items[:limit]
    status = "blocked" if unknown else "ready"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-artifact-timeline",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": not unknown,
        "artifactKindFilter": kind,
        "unknownKinds": unknown,
        "count": len(items),
        "items": items,
        "warnings": warnings,
        "safety": {
            **safety_flags(),
            "readOnlyArtifactDiscovery": True,
        },
    }


def self_test() -> dict[str, Any]:
    checks = [
        {"name": "ephemeral-cloudflare-url-detected", "pass": public_url_is_ephemeral("https://x.trycloudflare.com/mcp")},
        {"name": "non-ephemeral-local-url-ignored", "pass": not public_url_is_ephemeral("http://127.0.0.1:3000/mcp")},
        {"name": "standard-commands-include-phase2", "pass": "mcpPhase2Status" in standard_commands()},
        {"name": "standard-commands-include-compact-phase2", "pass": "mcpPhase2CompactStatus" in standard_commands()},
        {"name": "standard-commands-include-final", "pass": "mcpFinalStatus" in standard_commands()},
        {"name": "standard-commands-include-compact-final", "pass": "mcpFinalCompactStatus" in standard_commands()},
        {"name": "standard-commands-include-manual-public-ip-plan", "pass": "manualPublicIpPlan" in standard_commands()},
    ]
    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-workflow-state-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {
            **safety_flags(),
            "readOnlyArtifactDiscovery": True,
            "gitMutation": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect RiftReader MCP workflow state.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--state", action="store_true", help="Print current MCP workflow state.")
    mode.add_argument("--timeline", action="store_true", help="Print artifact timeline.")
    mode.add_argument("--self-test", action="store_true", help="Run deterministic workflow-state self-test.")
    parser.add_argument("--kind", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
        if args.self_test:
            payload = self_test()
        elif args.timeline:
            payload = artifact_timeline(repo_root, kind=args.kind, limit=args.limit)
        else:
            payload = build_mcp_workflow_state(repo_root)
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with structured error.
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-mcp-workflow-state",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "ok": False,
            "blockers": [f"workflow-state-exception:{type(exc).__name__}:{exc}"],
            "warnings": [],
            "safety": safety_flags(),
        }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
