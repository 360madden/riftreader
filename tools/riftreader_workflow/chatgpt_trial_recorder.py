#!/usr/bin/env python3
"""Record actual ChatGPT Developer Mode MCP proof facts supplied by the operator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, repo_rel as rel, safety_flags, timestamped_output_dir, utc_iso
    from .mcp_workflow_state import ACTUAL_CLIENT_PROOF_ROOT
    from .mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.mcp_workflow_state import ACTUAL_CLIENT_PROOF_ROOT
    from riftreader_workflow.mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES


REQUIRED_FIELDS = (
    "connectionMode",
    "publicMcpUrl",
    "chatgptRegistrationSucceeded",
    "toolCount",
    "toolNames",
    "toolOutputSchemasPresent",
    "toolOutputSchemaCount",
    "toolOutputSchemaToolNames",
    "health",
    "templateFetched",
    "submitPackageProposalSucceeded",
    "inboxId",
    "listInboxSawInboxId",
    "createPackageDraftSucceeded",
    "draftId",
    "reviewLatestPackageDraftSucceeded",
    "reviewLatestPackageDraftReadOnly",
    "dryRunSucceeded",
    "dryRunDiffPreviewOk",
    "dryRunDiffPreviewArtifactUnderPackageIntake",
    "dryRunDiffPreviewBoundedBytes",
    "dryRunDiffPreviewTextLength",
    "dryRunDiffPreviewTruncated",
    "applyLatestPackageDraftWithoutApprovalBlocked",
    "applyLatestPackageDraftWithoutApprovalBlockers",
    "applyLatestPackageDraftWithoutApprovalApplied",
)
EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES = (
    "health",
    "get_repo_status",
    "get_latest_handoff",
    "get_workflow_control_summary",
    "get_workflow_control_plan",
)
EXPECTED_DOMAIN_READ_ONLY_TOOL_COUNT = len(EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES)
FINAL_12_TOOL_PROOF_MODE = "final-12-tool"
DOMAIN_READ_ONLY_PROOF_MODE = "domain-read-only"
ALLOWED_PROOF_MODES = (FINAL_12_TOOL_PROOF_MODE, DOMAIN_READ_ONLY_PROOF_MODE)
MANUAL_PUBLIC_IP_CONNECTION_MODE = "manual-public-ip"
CLOUDFLARE_NAMED_TUNNEL_CONNECTION_MODE = "cloudflare-named-tunnel"
CANONICAL_PUBLIC_MCP_URL = "https://mcp.360madden.com/mcp"
SECURE_TUNNEL_CONNECTION_MODE = "openai-secure-mcp-tunnel"
PUBLIC_HTTPS_FALLBACK_CONNECTION_MODE = "public-https-fallback"
ALLOWED_CONNECTION_MODES = frozenset(
    {
        CLOUDFLARE_NAMED_TUNNEL_CONNECTION_MODE,
    }
)
RETIRED_TUNNEL_HOST_BLOCKER = "proof-url-uses-retired-tunnel-host"
RETIRED_TUNNEL_HOST_MARKERS = (".trycloudflare.com", ".ngrok-free.app", ".ngrok.app")
PROOF_INPUT_TEMPLATE_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "proof-input-templates"


def proof_template(proof_mode: str = FINAL_12_TOOL_PROOF_MODE) -> dict[str, Any]:
    if proof_mode == DOMAIN_READ_ONLY_PROOF_MODE:
        return domain_read_only_proof_template()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-actual-client-proof-input",
        "proofMode": FINAL_12_TOOL_PROOF_MODE,
        "connectionMode": CLOUDFLARE_NAMED_TUNNEL_CONNECTION_MODE,
        "publicMcpUrl": CANONICAL_PUBLIC_MCP_URL,
        "chatgptRegistrationSucceeded": False,
        "toolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "toolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        "toolOutputSchemasPresent": False,
        "toolOutputSchemaCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "toolOutputSchemaToolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        "health": {
            "repoRoot": ".",
            "repoName": "RiftReader",
            "absoluteRepoRootExposed": False,
        },
        "templateFetched": False,
        "submitPackageProposalSucceeded": False,
        "inboxId": "",
        "listInboxSawInboxId": False,
        "createPackageDraftSucceeded": False,
        "draftId": "",
        "reviewLatestPackageDraftSucceeded": False,
        "reviewLatestPackageDraftReadOnly": False,
        "dryRunSucceeded": False,
        "dryRunDiffPreviewOk": False,
        "dryRunDiffPreviewArtifactUnderPackageIntake": False,
        "dryRunDiffPreviewBoundedBytes": False,
        "dryRunDiffPreviewTextLength": 0,
        "dryRunDiffPreviewTruncated": False,
        "applyLatestPackageDraftWithoutApprovalBlocked": False,
        "applyLatestPackageDraftWithoutApprovalBlockers": [],
        "applyLatestPackageDraftWithoutApprovalApplied": None,
        "notes": "Fill this with actual ChatGPT-side observations, then record with --record --input proof.json.",
    }


def domain_read_only_proof_template() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-domain-read-only-proof-input",
        "proofMode": DOMAIN_READ_ONLY_PROOF_MODE,
        "connectionMode": CLOUDFLARE_NAMED_TUNNEL_CONNECTION_MODE,
        "publicMcpUrl": CANONICAL_PUBLIC_MCP_URL,
        "chatgptAppCreated": False,
        "authentication": "No Authentication",
        "toolCount": EXPECTED_DOMAIN_READ_ONLY_TOOL_COUNT,
        "toolNames": list(EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES),
        "healthCallSucceeded": False,
        "getRepoStatusCallSucceeded": False,
        "getLatestHandoffCallSucceeded": False,
        "getWorkflowControlSummaryCallSucceeded": False,
        "health": {
            "repoRoot": ".",
            "repoName": "RiftReader",
            "absoluteRepoRootExposed": False,
        },
        "repoStatusAbsoluteRepoRootExposed": False,
        "latestHandoffAbsoluteRepoRootExposed": False,
        "workflowControlSummaryAbsoluteRepoRootExposed": False,
        "notes": "Fill this with actual ChatGPT Web/Desktop Developer Mode observations, then record with --record --input proof.json.",
    }


def write_proof_template(repo_root: Path, *, proof_mode: str = FINAL_12_TOOL_PROOF_MODE) -> dict[str, Any]:
    output_dir = timestamped_output_dir(repo_root / PROOF_INPUT_TEMPLATE_ROOT)
    proof_input_path = output_dir / "proof-input.json"
    template = proof_template(proof_mode)
    proof_input_path.write_text(json.dumps(template, indent=2, sort_keys=True), encoding="utf-8")
    proof_input_rel = rel(repo_root, proof_input_path)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-proof-template-write",
        "generatedAtUtc": utc_iso(),
        "status": "ready",
        "ok": True,
        "proofMode": proof_mode,
        "template": template,
        "artifactPaths": {
            "proofInputJson": proof_input_rel,
        },
        "next": [
            "Fill proofInputJson with actual ChatGPT-side observations.",
            "Check the filled proof input with the checkCommand.",
            "Record the filled proof input with the recordCommand.",
        ],
        "checkCommand": [
            "scripts\\riftreader-chatgpt-trial-recorder.cmd",
            "--check-input",
            "--input",
            proof_input_rel,
            "--json",
        ],
        "recordCommand": [
            "scripts\\riftreader-chatgpt-trial-recorder.cmd",
            "--record",
            "--input",
            proof_input_rel,
            "--json",
        ],
        "safety": {
            **safety_flags(),
            "templateWriteOnly": True,
            "chatGptApiCalled": False,
            "publicTunnelStarted": False,
            "gitMutation": False,
            "applyFlagSent": False,
        },
    }


def _tool_name_list_blockers(field_name: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        return [f"{field_name}-not-list:{type(value).__name__}"]
    if not all(isinstance(item, str) for item in value):
        return [f"{field_name}-contains-non-string"]

    blockers: list[str] = []
    expected = list(EXPECTED_CHATGPT_MCP_TOOL_NAMES)
    if len(value) != EXPECTED_CHATGPT_MCP_TOOL_COUNT:
        blockers.append(f"{field_name}-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:{len(value)}")
    if len(set(value)) != len(value):
        blockers.append(f"{field_name}-contains-duplicates")
    if sorted(value) != sorted(expected):
        blockers.append(f"{field_name}-not-expected")
    return blockers


def _specific_tool_name_list_blockers(field_name: str, value: Any, expected: tuple[str, ...]) -> list[str]:
    if not isinstance(value, list):
        return [f"{field_name}-not-list:{type(value).__name__}"]
    if not all(isinstance(item, str) for item in value):
        return [f"{field_name}-contains-non-string"]
    blockers: list[str] = []
    if len(value) != len(expected):
        blockers.append(f"{field_name}-count-not-{len(expected)}:{len(value)}")
    if len(set(value)) != len(value):
        blockers.append(f"{field_name}-contains-duplicates")
    if sorted(value) != sorted(expected):
        blockers.append(f"{field_name}-not-expected")
    return blockers


def validate_domain_read_only_proof(proof: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    required_fields = (
        "proofMode",
        "connectionMode",
        "publicMcpUrl",
        "chatgptAppCreated",
        "authentication",
        "toolCount",
        "toolNames",
        "healthCallSucceeded",
        "getRepoStatusCallSucceeded",
        "health",
    )
    for field in required_fields:
        if field not in proof:
            blockers.append(f"required-field-missing:{field}")
    health = proof.get("health") if isinstance(proof.get("health"), dict) else {}
    for field in ("repoRoot", "repoName", "absoluteRepoRootExposed"):
        if field not in health:
            blockers.append(f"required-field-missing:health.{field}")
    if proof.get("proofMode") != DOMAIN_READ_ONLY_PROOF_MODE:
        blockers.append(f"proof-mode-invalid:{proof.get('proofMode')!r}")
    public_url = str(proof.get("publicMcpUrl") or "")
    connection_mode = proof.get("connectionMode")
    if connection_mode not in ALLOWED_CONNECTION_MODES:
        blockers.append(f"connection-mode-invalid:{connection_mode!r}")
    if any(marker in public_url.lower() for marker in RETIRED_TUNNEL_HOST_MARKERS):
        blockers.append(RETIRED_TUNNEL_HOST_BLOCKER)
    if public_url != CANONICAL_PUBLIC_MCP_URL:
        blockers.append(f"public-mcp-url-not-domain-route:{public_url!r}")
    if proof.get("authentication") != "No Authentication":
        blockers.append(f"authentication-not-no-authentication:{proof.get('authentication')!r}")
    if proof.get("chatgptAppCreated") is not True:
        blockers.append("chatgpt-app-created-not-confirmed")
    if proof.get("toolCount") != EXPECTED_DOMAIN_READ_ONLY_TOOL_COUNT:
        blockers.append(f"tool-count-not-{EXPECTED_DOMAIN_READ_ONLY_TOOL_COUNT}:{proof.get('toolCount')!r}")
    blockers.extend(_specific_tool_name_list_blockers("tool-names", proof.get("toolNames"), EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES))
    if health.get("repoRoot") != ".":
        blockers.append(f"health-repo-root-not-redacted:{health.get('repoRoot')!r}")
    if health.get("repoName") != "RiftReader":
        blockers.append(f"health-repo-name-not-riftreader:{health.get('repoName')!r}")
    if health.get("absoluteRepoRootExposed") is not False:
        blockers.append(f"health-absolute-repo-root-exposed:{health.get('absoluteRepoRootExposed')!r}")
    if proof.get("healthCallSucceeded") is not True:
        blockers.append("health-call-not-confirmed")
    if proof.get("getRepoStatusCallSucceeded") is not True:
        blockers.append("get-repo-status-call-not-confirmed")
    if proof.get("getLatestHandoffCallSucceeded") is not True and proof.get("getWorkflowControlSummaryCallSucceeded") is not True:
        blockers.append("handoff-or-workflow-summary-call-not-confirmed")
    for field in (
        "repoStatusAbsoluteRepoRootExposed",
        "latestHandoffAbsoluteRepoRootExposed",
        "workflowControlSummaryAbsoluteRepoRootExposed",
    ):
        if field in proof and proof.get(field) is not False:
            blockers.append(f"{field}-not-false:{proof.get(field)!r}")
    return blockers


def validate_final_12_tool_proof(proof: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in proof:
            blockers.append(f"required-field-missing:{field}")
    health = proof.get("health") if isinstance(proof.get("health"), dict) else {}
    for field in ("repoRoot", "repoName", "absoluteRepoRootExposed"):
        if field not in health:
            blockers.append(f"required-field-missing:health.{field}")
    public_url = str(proof.get("publicMcpUrl") or "")
    connection_mode = proof.get("connectionMode")
    if connection_mode not in ALLOWED_CONNECTION_MODES:
        blockers.append(f"connection-mode-invalid:{connection_mode!r}")
    if any(marker in public_url.lower() for marker in RETIRED_TUNNEL_HOST_MARKERS):
        blockers.append(RETIRED_TUNNEL_HOST_BLOCKER)
    if "<" in public_url or ">" in public_url:
        blockers.append("public-mcp-url-placeholder")
    elif public_url != CANONICAL_PUBLIC_MCP_URL:
        blockers.append(f"public-mcp-url-not-domain-route:{public_url!r}")
    if not public_url.startswith("https://"):
        blockers.append("public-mcp-url-not-https")
    if proof.get("toolCount") != EXPECTED_CHATGPT_MCP_TOOL_COUNT:
        blockers.append(f"tool-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:{proof.get('toolCount')!r}")
    blockers.extend(_tool_name_list_blockers("tool-names", proof.get("toolNames")))
    if proof.get("toolOutputSchemasPresent") is not True:
        blockers.append("tool-output-schemas-not-confirmed")
    if proof.get("toolOutputSchemaCount") != EXPECTED_CHATGPT_MCP_TOOL_COUNT:
        blockers.append(
            f"tool-output-schema-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:{proof.get('toolOutputSchemaCount')!r}"
        )
    blockers.extend(_tool_name_list_blockers("tool-output-schema-tool-names", proof.get("toolOutputSchemaToolNames")))
    if health.get("repoRoot") != ".":
        blockers.append(f"health-repo-root-not-redacted:{health.get('repoRoot')!r}")
    if health.get("repoName") != "RiftReader":
        blockers.append(f"health-repo-name-not-riftreader:{health.get('repoName')!r}")
    if health.get("absoluteRepoRootExposed") is not False:
        blockers.append(f"health-absolute-repo-root-exposed:{health.get('absoluteRepoRootExposed')!r}")
    if proof.get("submitPackageProposalSucceeded") is not True:
        blockers.append("submit-package-proposal-not-confirmed")
    if proof.get("submitPackageProposalSucceeded") is True and not proof.get("inboxId"):
        blockers.append("submit-succeeded-but-inbox-id-missing")
    if proof.get("submitPackageProposalSucceeded") is True and proof.get("listInboxSawInboxId") is not True:
        blockers.append("submit-succeeded-but-list-inbox-did-not-see-id")
    if proof.get("createPackageDraftSucceeded") is not True:
        blockers.append("create-package-draft-not-confirmed")
    if proof.get("reviewLatestPackageDraftSucceeded") is not True:
        blockers.append("review-latest-package-draft-not-confirmed")
    if proof.get("reviewLatestPackageDraftReadOnly") is not True:
        blockers.append("review-latest-package-draft-read-only-not-confirmed")
    if proof.get("chatgptRegistrationSucceeded") is not True:
        blockers.append("chatgpt-registration-not-confirmed")
    if proof.get("templateFetched") is not True:
        blockers.append("template-fetch-not-confirmed")
    if proof.get("dryRunSucceeded") is not True:
        blockers.append("dry-run-not-confirmed")
    if proof.get("dryRunDiffPreviewOk") is not True:
        blockers.append("dry-run-diff-preview-not-confirmed")
    if proof.get("dryRunDiffPreviewArtifactUnderPackageIntake") is not True:
        blockers.append("dry-run-diff-preview-package-intake-not-confirmed")
    if proof.get("dryRunDiffPreviewBoundedBytes") is not True:
        blockers.append("dry-run-diff-preview-bounded-bytes-not-confirmed")
    text_length = proof.get("dryRunDiffPreviewTextLength")
    if not isinstance(text_length, int) or text_length <= 0:
        blockers.append(f"dry-run-diff-preview-text-length-invalid:{text_length!r}")
    if not isinstance(proof.get("dryRunDiffPreviewTruncated"), bool):
        blockers.append(f"dry-run-diff-preview-truncated-not-boolean:{proof.get('dryRunDiffPreviewTruncated')!r}")
    if proof.get("createPackageDraftSucceeded") is True and not proof.get("draftId"):
        blockers.append("create-draft-succeeded-but-draft-id-missing")
    if not proof.get("draftId"):
        blockers.append("draft-id-missing")
    if proof.get("dryRunSucceeded") is True and not proof.get("draftId"):
        blockers.append("dry-run-succeeded-but-draft-id-missing")
    if proof.get("applyLatestPackageDraftWithoutApprovalBlocked") is not True:
        blockers.append("apply-latest-package-draft-without-approval-not-blocked")
    apply_without_approval_blockers = proof.get("applyLatestPackageDraftWithoutApprovalBlockers")
    if not isinstance(apply_without_approval_blockers, list):
        blockers.append(
            "apply-latest-package-draft-without-approval-blockers-not-list:"
            f"{type(apply_without_approval_blockers).__name__}"
        )
    else:
        facade_missing_tools = sorted(
            str(item).split("TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:", 1)[1]
            for item in apply_without_approval_blockers
            if isinstance(item, str) and item.startswith("TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:")
        )
        if facade_missing_tools:
            blockers.append("chatgpt-tool-facade-unavailable:" + ",".join(facade_missing_tools))
        if "APPLY_APPROVAL_MISSING" not in apply_without_approval_blockers:
            blockers.append("apply-latest-package-draft-without-approval-missing-approval-blocker")
    if proof.get("applyLatestPackageDraftWithoutApprovalApplied") is not False:
        blockers.append(
            "apply-latest-package-draft-without-approval-applied-not-false:"
            f"{proof.get('applyLatestPackageDraftWithoutApprovalApplied')!r}"
        )
    return blockers


def validate_proof(proof: dict[str, Any]) -> list[str]:
    if proof.get("proofMode") == DOMAIN_READ_ONLY_PROOF_MODE:
        return validate_domain_read_only_proof(proof)
    return validate_final_12_tool_proof(proof)


def render_markdown(record: dict[str, Any]) -> str:
    proof = record.get("proof") if isinstance(record.get("proof"), dict) else {}
    health = proof.get("health") if isinstance(proof.get("health"), dict) else {}
    lines = [
        "# RiftReader ChatGPT MCP Actual-Client Proof",
        "",
        f"- Generated UTC: `{record.get('generatedAtUtc')}`",
        f"- Status: `{record.get('status')}`",
        f"- Proof mode: `{proof.get('proofMode')}`",
        f"- Connection mode: `{proof.get('connectionMode')}`",
        f"- Public MCP URL: `{proof.get('publicMcpUrl')}`",
        f"- Tool count: `{proof.get('toolCount')}`",
        f"- Tool names: `{proof.get('toolNames')}`",
        f"- Tool output schemas present: `{proof.get('toolOutputSchemasPresent')}`",
        f"- Tool output schema count: `{proof.get('toolOutputSchemaCount')}`",
        f"- Tool output schema tool names: `{proof.get('toolOutputSchemaToolNames')}`",
        f"- Health repoRoot: `{health.get('repoRoot')}`",
        f"- Health repoName: `{health.get('repoName')}`",
        f"- absoluteRepoRootExposed: `{health.get('absoluteRepoRootExposed')}`",
        f"- Inbox ID: `{proof.get('inboxId')}`",
        f"- Package draft created: `{proof.get('createPackageDraftSucceeded')}`",
        f"- Draft ID: `{proof.get('draftId')}`",
        f"- Package draft reviewed: `{proof.get('reviewLatestPackageDraftSucceeded')}`",
        f"- Review read-only: `{proof.get('reviewLatestPackageDraftReadOnly')}`",
        f"- Dry-run succeeded: `{proof.get('dryRunSucceeded')}`",
        f"- Diff preview OK: `{proof.get('dryRunDiffPreviewOk')}`",
        f"- Diff preview text length: `{proof.get('dryRunDiffPreviewTextLength')}`",
        f"- Diff preview truncated: `{proof.get('dryRunDiffPreviewTruncated')}`",
        f"- Apply without approval blocked: `{proof.get('applyLatestPackageDraftWithoutApprovalBlocked')}`",
        f"- Apply without approval blockers: `{proof.get('applyLatestPackageDraftWithoutApprovalBlockers')}`",
        f"- Apply without approval applied: `{proof.get('applyLatestPackageDraftWithoutApprovalApplied')}`",
        "",
        "## Blockers",
        "",
    ]
    for blocker in record.get("blockers") or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Notes", "", str(proof.get("notes") or "")])
    return "\n".join(lines).rstrip() + "\n"


def record_proof(repo_root: Path, input_path: Path) -> dict[str, Any]:
    value = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("proof-input-not-json-object")
    blockers = validate_proof(value)
    status = "passed" if not blockers else "blocked"
    output_dir = timestamped_output_dir(repo_root / ACTUAL_CLIENT_PROOF_ROOT)
    record = {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-domain-read-only-proof"
        if value.get("proofMode") == DOMAIN_READ_ONLY_PROOF_MODE
        else "riftreader-chatgpt-actual-client-proof",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "proof": value,
        "blockers": blockers,
        "warnings": [],
        "artifacts": {
            "proofJson": rel(repo_root, output_dir / "proof.json"),
            "proofMarkdown": rel(repo_root, output_dir / "proof.md"),
        },
        "safety": {
            **safety_flags(),
            "operatorSuppliedFactsOnly": True,
            "chatGptApiCalled": False,
            "publicTunnelStarted": False,
            "gitMutation": False,
            "applyFlagSent": False,
        },
    }
    (output_dir / "proof.json").write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "proof.md").write_text(render_markdown(record), encoding="utf-8")
    return record


def check_proof_input(repo_root: Path, input_path: Path) -> dict[str, Any]:
    """Validate proof input JSON without recording or writing artifacts."""

    value = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("proof-input-not-json-object")
    blockers = validate_proof(value)
    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-proof-input-check",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "inputPath": rel(repo_root, input_path),
        "blockers": blockers,
        "warnings": [],
        "next": [
            "Fix blockers in the proof input JSON before recording." if blockers else "Record the checked proof input.",
        ],
        "recordCommand": [
            "scripts\\riftreader-chatgpt-trial-recorder.cmd",
            "--record",
            "--input",
            rel(repo_root, input_path),
            "--json",
        ],
        "safety": {
            **safety_flags(),
            "readOnlyProofInputCheck": True,
            "operatorSuppliedFactsOnly": True,
            "chatGptApiCalled": False,
            "publicTunnelStarted": False,
            "gitMutation": False,
            "applyFlagSent": False,
            "artifactWrite": False,
        },
    }


def latest_proof_input_template(repo_root: Path) -> Path | None:
    """Return the newest ignored proof-input template, if one exists."""

    root = repo_root / PROOF_INPUT_TEMPLATE_ROOT
    if not root.is_dir():
        return None
    candidates = [path for path in root.glob("*/proof-input.json") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.parent.name, path.name))


def check_latest_proof_input_template(repo_root: Path) -> dict[str, Any]:
    """Validate the newest proof-input template without recording artifacts."""

    latest = latest_proof_input_template(repo_root)
    if latest is None:
        return {
            "schemaVersion": 1,
            "kind": "riftreader-chatgpt-proof-input-check",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "inputPath": None,
            "blockers": ["proof-input-template-missing"],
            "warnings": [],
            "next": ["Write a proof input template first with --write-template."],
            "safety": {
                **safety_flags(),
                "readOnlyProofInputCheck": True,
                "chatGptApiCalled": False,
                "publicTunnelStarted": False,
                "gitMutation": False,
                "applyFlagSent": False,
                "artifactWrite": False,
            },
        }
    payload = check_proof_input(repo_root, latest)
    payload["latestTemplate"] = True
    return payload


def self_test() -> dict[str, Any]:
    valid_proof = proof_template()
    valid_proof.update(
        {
            "publicMcpUrl": CANONICAL_PUBLIC_MCP_URL,
            "chatgptRegistrationSucceeded": True,
            "toolOutputSchemasPresent": True,
            "templateFetched": True,
            "submitPackageProposalSucceeded": True,
            "inboxId": "self-test-inbox",
            "listInboxSawInboxId": True,
            "createPackageDraftSucceeded": True,
            "draftId": "self-test-draft",
            "reviewLatestPackageDraftSucceeded": True,
            "reviewLatestPackageDraftReadOnly": True,
            "dryRunSucceeded": True,
            "dryRunDiffPreviewOk": True,
            "dryRunDiffPreviewArtifactUnderPackageIntake": True,
            "dryRunDiffPreviewBoundedBytes": True,
            "dryRunDiffPreviewTextLength": 1,
            "applyLatestPackageDraftWithoutApprovalBlocked": True,
            "applyLatestPackageDraftWithoutApprovalBlockers": ["APPLY_APPROVAL_MISSING"],
            "applyLatestPackageDraftWithoutApprovalApplied": False,
        }
    )
    retired_tunnel_host_proof = dict(valid_proof)
    retired_tunnel_host_proof["publicMcpUrl"] = "https://example.trycloudflare.com/mcp"
    retired_secure_mode_proof = dict(valid_proof)
    retired_secure_mode_proof["connectionMode"] = SECURE_TUNNEL_CONNECTION_MODE
    placeholder_proof = dict(valid_proof)
    placeholder_proof["publicMcpUrl"] = "https://<current-external-ip>/mcp"
    valid_domain_read_only_proof = domain_read_only_proof_template()
    valid_domain_read_only_proof.update(
        {
            "chatgptAppCreated": True,
            "healthCallSucceeded": True,
            "getRepoStatusCallSucceeded": True,
            "getLatestHandoffCallSucceeded": True,
        }
    )
    domain_read_only_extra_tool_proof = dict(valid_domain_read_only_proof)
    domain_read_only_extra_tool_proof["toolNames"] = list(EXPECTED_CHATGPT_MCP_TOOL_NAMES)
    domain_read_only_extra_tool_proof["toolCount"] = EXPECTED_CHATGPT_MCP_TOOL_COUNT

    checks = [
        {
            "name": "template-has-required-fields",
            "pass": all(field in proof_template() for field in REQUIRED_FIELDS),
        },
        {
            "name": "cloudflare-named-tunnel-valid-shape-passes",
            "pass": validate_proof(valid_proof) == [],
        },
        {
            "name": "cloudflare-named-tunnel-blocks-retired-tunnel-host",
            "pass": RETIRED_TUNNEL_HOST_BLOCKER in validate_proof(retired_tunnel_host_proof),
        },
        {
            "name": "retired-secure-tunnel-mode-blocked",
            "pass": f"connection-mode-invalid:{SECURE_TUNNEL_CONNECTION_MODE!r}" in validate_proof(retired_secure_mode_proof),
        },
        {
            "name": "placeholder-url-blocked",
            "pass": "public-mcp-url-placeholder" in validate_proof(placeholder_proof),
        },
        {
            "name": "domain-read-only-valid-shape-passes",
            "pass": validate_proof(valid_domain_read_only_proof) == [],
        },
        {
            "name": "domain-read-only-blocks-full-tool-surface",
            "pass": "tool-names-not-expected" in validate_proof(domain_read_only_extra_tool_proof),
        },
    ]
    ok = all(bool(check["pass"]) for check in checks)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-trial-recorder-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {
            **safety_flags(),
            "chatGptApiCalled": False,
            "publicTunnelStarted": False,
            "gitMutation": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record actual ChatGPT MCP proof facts supplied by the operator.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", action="store_true", help="Print proof input template JSON.")
    mode.add_argument("--write-template", action="store_true", help="Write a fillable proof input template under .riftreader-local.")
    mode.add_argument("--check-input", action="store_true", help="Validate proof input JSON without recording artifacts.")
    mode.add_argument("--check-latest-template", action="store_true", help="Validate the latest proof input template without recording artifacts.")
    mode.add_argument("--record", action="store_true", help="Validate and record proof input JSON.")
    mode.add_argument("--self-test", action="store_true", help="Run deterministic proof-rule self-test.")
    parser.add_argument("--input", default=None, help="Path to proof input JSON for --check-input or --record.")
    parser.add_argument("--proof-mode", choices=ALLOWED_PROOF_MODES, default=FINAL_12_TOOL_PROOF_MODE)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.template:
        payload = proof_template(args.proof_mode)
    elif args.write_template:
        payload = write_proof_template(repo_root, proof_mode=args.proof_mode)
    elif args.self_test:
        payload = self_test()
    elif args.check_input:
        if not args.input:
            print("error: --check-input requires --input proof.json", file=sys.stderr)
            return 2
        payload = check_proof_input(repo_root, Path(args.input))
    elif args.check_latest_template:
        payload = check_latest_proof_input_template(repo_root)
    else:
        if not args.input:
            print("error: --record requires --input proof.json", file=sys.stderr)
            return 2
        payload = record_proof(repo_root, Path(args.input))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
