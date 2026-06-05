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
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.mcp_workflow_state import ACTUAL_CLIENT_PROOF_ROOT


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
)
EXPECTED_CHATGPT_MCP_TOOL_NAMES = (
    "health",
    "get_repo_status",
    "get_latest_handoff",
    "get_package_proposal_template",
    "submit_package_proposal",
    "list_inbox",
    "create_package_draft_from_inbox",
    "review_latest_package_draft",
    "dry_run_latest_package_draft",
    "get_workflow_control_plan",
)
EXPECTED_CHATGPT_MCP_TOOL_COUNT = len(EXPECTED_CHATGPT_MCP_TOOL_NAMES)
SECURE_TUNNEL_CONNECTION_MODE = "openai-secure-mcp-tunnel"
PUBLIC_HTTPS_FALLBACK_CONNECTION_MODE = "public-https-fallback"
ALLOWED_CONNECTION_MODES = frozenset(
    {
        SECURE_TUNNEL_CONNECTION_MODE,
        PUBLIC_HTTPS_FALLBACK_CONNECTION_MODE,
    }
)
PUBLIC_FALLBACK_HOST_MARKERS = (".trycloudflare.com", ".ngrok-free.app", ".ngrok.app")


def proof_template() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-actual-client-proof-input",
        "connectionMode": SECURE_TUNNEL_CONNECTION_MODE,
        "publicMcpUrl": "https://<secure-mcp-tunnel-selected-in-chatgpt>/mcp",
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
        "notes": "Fill this with actual ChatGPT-side observations, then record with --record --input proof.json.",
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


def validate_proof(proof: dict[str, Any]) -> list[str]:
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
    if (
        connection_mode == SECURE_TUNNEL_CONNECTION_MODE
        and any(marker in public_url.lower() for marker in PUBLIC_FALLBACK_HOST_MARKERS)
    ):
        blockers.append("secure-tunnel-proof-url-uses-public-fallback-host")
    if "<" in public_url or ">" in public_url:
        blockers.append("public-mcp-url-placeholder")
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
    return blockers


def render_markdown(record: dict[str, Any]) -> str:
    proof = record.get("proof") if isinstance(record.get("proof"), dict) else {}
    health = proof.get("health") if isinstance(proof.get("health"), dict) else {}
    lines = [
        "# RiftReader ChatGPT MCP Actual-Client Proof",
        "",
        f"- Generated UTC: `{record.get('generatedAtUtc')}`",
        f"- Status: `{record.get('status')}`",
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
        "kind": "riftreader-chatgpt-actual-client-proof",
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


def self_test() -> dict[str, Any]:
    valid_proof = proof_template()
    valid_proof.update(
        {
            "publicMcpUrl": "https://example.openai-mcp-tunnel.invalid/mcp",
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
        }
    )
    secure_fallback_host_proof = dict(valid_proof)
    secure_fallback_host_proof["publicMcpUrl"] = "https://example.trycloudflare.com/mcp"
    explicit_fallback_proof = dict(secure_fallback_host_proof)
    explicit_fallback_proof["connectionMode"] = PUBLIC_HTTPS_FALLBACK_CONNECTION_MODE
    placeholder_proof = dict(valid_proof)
    placeholder_proof["publicMcpUrl"] = "https://<secure-mcp-tunnel-selected-in-chatgpt>/mcp"

    checks = [
        {
            "name": "template-has-required-fields",
            "pass": all(field in proof_template() for field in REQUIRED_FIELDS),
        },
        {
            "name": "secure-tunnel-valid-shape-passes",
            "pass": validate_proof(valid_proof) == [],
        },
        {
            "name": "secure-tunnel-blocks-public-fallback-host",
            "pass": "secure-tunnel-proof-url-uses-public-fallback-host" in validate_proof(secure_fallback_host_proof),
        },
        {
            "name": "explicit-public-fallback-host-allowed",
            "pass": "secure-tunnel-proof-url-uses-public-fallback-host" not in validate_proof(explicit_fallback_proof),
        },
        {
            "name": "placeholder-url-blocked",
            "pass": "public-mcp-url-placeholder" in validate_proof(placeholder_proof),
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
    mode.add_argument("--record", action="store_true", help="Validate and record proof input JSON.")
    mode.add_argument("--self-test", action="store_true", help="Run deterministic proof-rule self-test.")
    parser.add_argument("--input", default=None, help="Path to proof input JSON for --record.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.template:
        payload = proof_template()
    elif args.self_test:
        payload = self_test()
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
