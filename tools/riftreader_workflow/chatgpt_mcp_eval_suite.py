#!/usr/bin/env python3
"""Stage 48 local ChatGPT MCP eval-suite checklist generator.

This helper is deliberately non-executing by default. It emits the local
commands, expected denial blockers, actual-client proof checklist, and safety
truth needed to evaluate the current ChatGPT Web/Desktop MCP surface without
starting the server, starting tunnels, registering ChatGPT, mutating Git,
sending RIFT input, or touching CE/x64dbg.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .mcp_tool_surface import (
        EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        EXPECTED_CHATGPT_MCP_TOOL_NAMES,
        PUBLIC_READ_ONLY_TOOL_COUNT,
        PUBLIC_READ_ONLY_TOOL_NAMES,
    )
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.mcp_tool_surface import (
        EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        EXPECTED_CHATGPT_MCP_TOOL_NAMES,
        PUBLIC_READ_ONLY_TOOL_COUNT,
        PUBLIC_READ_ONLY_TOOL_NAMES,
    )


SCHEMA_VERSION = 1
STAGE = 48
STAGE_NAME = "End-to-end product eval suite"
EVAL_ROOT_REL = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "eval-suite"


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def timestamp_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def repo_rel(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _command(*args: str) -> list[str]:
    return list(args)


def _local_eval_commands() -> list[dict[str, Any]]:
    return [
        {
            "key": "stage48-focused-unit-tests",
            "purpose": "Validate MCP payload contracts, denial paths, and workflow docs.",
            "command": _command(
                "python",
                "-m",
                "unittest",
                "scripts.test_riftreader_chatgpt_mcp",
                "scripts.test_chatgpt_mcp_workflow_docs",
            ),
            "expectedExitCodes": [0],
            "startsServer": False,
            "startsTunnel": False,
            "mutatesRepo": False,
        },
        {
            "key": "stage48-broader-mcp-regression",
            "purpose": "Cover live/debugger/final-readiness/workflow-state denial and status paths.",
            "command": _command(
                "python",
                "-m",
                "unittest",
                "scripts.test_debugger_ce_execute",
                "scripts.test_debugger_ce_plan",
                "scripts.test_live_control_plan",
                "scripts.test_chatgpt_mcp_workflow_docs",
                "scripts.test_riftreader_chatgpt_mcp",
                "scripts.test_mcp_final_readiness",
                "scripts.test_mcp_phase2_status",
                "scripts.test_mcp_workflow_state",
                "scripts.test_mcp_mission_control",
                "scripts.test_stage38_consideration",
            ),
            "expectedExitCodes": [0],
            "startsServer": False,
            "startsTunnel": False,
            "mutatesRepo": False,
        },
        {
            "key": "sdk-validate-full",
            "purpose": "Verify the current full 40-tool FastMCP registration surface.",
            "command": _command(
                "python",
                "tools\\riftreader_workflow\\riftreader_chatgpt_mcp.py",
                "--validate-sdk",
                "--tool-profile",
                "full",
                "--json",
            ),
            "expectedExitCodes": [0],
            "startsServer": False,
            "startsTunnel": False,
            "mutatesRepo": False,
        },
        {
            "key": "sdk-validate-public-read-only",
            "purpose": "Verify the shared no-auth diagnostics profile has only read-only tools.",
            "command": _command(
                "python",
                "tools\\riftreader_workflow\\riftreader_chatgpt_mcp.py",
                "--validate-sdk",
                "--tool-profile",
                "public-read-only",
                "--json",
            ),
            "expectedExitCodes": [0],
            "startsServer": False,
            "startsTunnel": False,
            "mutatesRepo": False,
        },
        {
            "key": "diff-check",
            "purpose": "Catch whitespace errors before local commit.",
            "command": _command("git", "--no-pager", "diff", "--check"),
            "expectedExitCodes": [0],
            "startsServer": False,
            "startsTunnel": False,
            "mutatesRepo": False,
        },
    ]


def _eval_matrix() -> list[dict[str, Any]]:
    return [
        {
            "key": "read-only-surface",
            "class": "allowed-read",
            "toolNames": [
                "health",
                "get_repo_status",
                "get_latest_handoff",
                "get_workflow_control_summary",
                "get_chatgpt_connector_setup_packet",
                "get_final_readiness_status",
                "get_actual_client_proof_status",
            ],
            "expected": "allowed; no repo mutation, no server/tunnel start, repo root redacted",
        },
        {
            "key": "auth-profile-policy",
            "class": "allowed-read",
            "expected": "No Authentication personal lane preserved; public-read-only recommended for shared no-auth diagnostics.",
            "requiredFields": [
                "authRolePolicy.personalNoAuthPreserved=true",
                "authRolePolicy.authEnforcementChanged=false",
                "authRolePolicy.recommendedSharedDefaultProfile=public-read-only",
            ],
        },
        {
            "key": "package-apply-denial",
            "class": "blocked-local-repo-mutation",
            "toolName": "apply_latest_package_draft",
            "denialCall": "call without approvalToken",
            "expectedBlockers": ["APPLY_APPROVAL_MISSING"],
        },
        {
            "key": "commit-denial",
            "class": "blocked-local-git-mutation",
            "toolName": "commit_reviewed_slice",
            "denialCall": "call without approvalToken",
            "expectedBlockers": ["COMMIT_APPROVAL_MISSING"],
        },
        {
            "key": "push-denial",
            "class": "blocked-remote-git-mutation",
            "toolName": "push_current_branch",
            "denialCall": "call without approvalToken",
            "expectedBlockers": ["PUSH_APPROVAL_MISSING"],
        },
        {
            "key": "live-control-denial",
            "class": "blocked-live-rift-input",
            "toolName": "execute_live_control_action",
            "denialCall": "call without approvalPhrase/current backend",
            "expectedBlockers": ["LIVE_APPROVAL_MISSING", "LIVE_INPUT_BACKEND_UNAVAILABLE"],
        },
        {
            "key": "debugger-ce-denial",
            "class": "blocked-debugger-ce",
            "toolName": "execute_debugger_ce_action",
            "denialCall": "call without approvalPhrase/current backend",
            "expectedBlockers": ["DEBUGGER_APPROVAL_MISSING", "DEBUGGER_BACKEND_UNAVAILABLE"],
        },
        {
            "key": "provider-write-denial",
            "class": "blocked-provider-mutation",
            "expected": "provider intent may be labeled, but provider writes are not exposed and remain blocked by default",
        },
        {
            "key": "actual-client-proof-freshness",
            "class": "blocked-until-fresh-external-proof",
            "expected": "final readiness remains blocked until actual ChatGPT Web/Desktop proof observes the current 40-tool surface",
        },
    ]


def _actual_client_checklist() -> dict[str, Any]:
    return {
        "status": "manual-actual-client-proof-required",
        "serverUrl": "https://mcp.360madden.com/mcp",
        "authMode": "No Authentication",
        "connectionMode": "cloudflare-named-tunnel",
        "requiredObservedFields": {
            "toolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "toolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "toolOutputSchemasPresent": True,
            "toolOutputSchemaCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "clientTransportStatus": "tool-call-succeeded",
            "healthCallSucceeded": True,
            "authRolePolicyObserved": True,
        },
        "safeCallOrder": [
            "health",
            "get_repo_status",
            "get_latest_handoff",
            "get_chatgpt_connector_setup_packet",
            "get_actual_client_proof_status",
        ],
        "denialCalls": [
            {
                "toolName": "apply_latest_package_draft",
                "call": "omit approvalToken",
                "expectedBlockers": ["APPLY_APPROVAL_MISSING"],
            }
        ],
        "recordingTool": "submit_actual_client_observation",
        "finalGateCommand": "scripts\\riftreader-mcp-final.cmd --status --compact-json",
    }


def safety_flags(*, artifact_written: bool) -> dict[str, Any]:
    return {
        "readOnlyEvalPlan": True,
        "localIgnoredArtifactWrite": artifact_written,
        "serverStarted": False,
        "publicTunnelStarted": False,
        "chatGptRegistrationPerformed": False,
        "gitMutation": False,
        "remoteMutation": False,
        "providerWrites": False,
        "inputSent": False,
        "movementSent": False,
        "x64dbgAttach": False,
        "noCheatEngine": True,
        "proofPromotionPerformed": False,
        "authEnforcementChanged": False,
        "secretMaterialIncluded": False,
    }


def build_eval_suite(repo_root: Path, *, artifact_written: bool = False) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-stage48-eval-suite",
        "generatedAtUtc": utc_iso(),
        "status": "ready",
        "ok": True,
        "stage": STAGE,
        "stageName": STAGE_NAME,
        "toolSurface": {
            "fullProfile": {
                "toolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                "toolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            },
            "publicReadOnlyProfile": {
                "toolCount": PUBLIC_READ_ONLY_TOOL_COUNT,
                "toolNames": list(PUBLIC_READ_ONLY_TOOL_NAMES),
            },
        },
        "localEvalCommands": _local_eval_commands(),
        "evalMatrix": _eval_matrix(),
        "actualClientChecklist": _actual_client_checklist(),
        "blockers": [],
        "warnings": [
            "This is an eval plan/checklist generator; it does not run commands unless the operator runs them separately.",
            "Actual-client proof still requires ChatGPT Web/Desktop to call the live connector and record observations.",
        ],
        "safety": safety_flags(artifact_written=artifact_written),
        "recommendedNextAction": (
            "Run the localEvalCommands, refresh the non-Codex HTTP MCP runtime, record fresh actual-client proof, "
            "then rerun final readiness."
        ),
        "repoRoot": ".",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# ChatGPT MCP Stage 48 eval suite",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Stage: `{payload.get('stage')}` `{payload.get('stageName')}`",
        f"- Full tool count: `{payload['toolSurface']['fullProfile']['toolCount']}`",
        f"- Public read-only tool count: `{payload['toolSurface']['publicReadOnlyProfile']['toolCount']}`",
        "",
        "## Local eval commands",
        "",
        "| Key | Command |",
        "|---|---|",
    ]
    for item in payload.get("localEvalCommands", []):
        lines.append(f"| `{item['key']}` | `{' '.join(item['command'])}` |")
    lines.extend(
        [
            "",
            "## Denial / proof matrix",
            "",
            "| Key | Class | Expected |",
            "|---|---|---|",
        ]
    )
    for item in payload.get("evalMatrix", []):
        expected = item.get("expected") or ", ".join(item.get("expectedBlockers", []))
        lines.append(f"| `{item['key']}` | `{item['class']}` | {expected} |")
    checklist = payload.get("actualClientChecklist", {})
    lines.extend(
        [
            "",
            "## Actual-client checklist",
            "",
            f"- Server URL: `{checklist.get('serverUrl')}`",
            f"- Auth mode: `{checklist.get('authMode')}`",
            f"- Required tool count: `{checklist.get('requiredObservedFields', {}).get('toolCount')}`",
            f"- Required transport: `{checklist.get('requiredObservedFields', {}).get('clientTransportStatus')}`",
            "",
            "## Safety",
            "",
            f"- Server started: `{payload['safety']['serverStarted']}`",
            f"- Public tunnel started: `{payload['safety']['publicTunnelStarted']}`",
            f"- Git mutation: `{payload['safety']['gitMutation']}`",
            f"- RIFT input sent: `{payload['safety']['inputSent']}`",
            f"- x64dbg attach: `{payload['safety']['x64dbgAttach']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_eval_suite(repo_root: Path) -> dict[str, Any]:
    run_id = timestamp_id()
    output_dir = repo_root / EVAL_ROOT_REL / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_eval_suite(repo_root, artifact_written=True)
    json_path = output_dir / "eval-suite.json"
    md_path = output_dir / "eval-suite.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    latest_json = repo_root / EVAL_ROOT_REL / "latest.json"
    latest_md = repo_root / EVAL_ROOT_REL / "latest.md"
    latest_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    latest_md.write_text(render_markdown(payload), encoding="utf-8")
    payload["artifactPaths"] = {
        "summaryJson": repo_rel(repo_root, json_path),
        "summaryMarkdown": repo_rel(repo_root, md_path),
        "latestJson": repo_rel(repo_root, latest_json),
        "latestMarkdown": repo_rel(repo_root, latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    latest_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the Stage 48 ChatGPT MCP eval-suite checklist.")
    parser.add_argument("--repo-root", default=".", help="RiftReader repo root. Defaults to current directory.")
    parser.add_argument("--write", action="store_true", help="Write ignored JSON/Markdown artifacts under .riftreader-local.")
    parser.add_argument("--summary-md", action="store_true", help="Print Markdown instead of JSON.")
    parser.add_argument("--json", action="store_true", help="Print JSON. This is the default unless --summary-md is set.")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    payload = write_eval_suite(repo_root) if args.write else build_eval_suite(repo_root)
    if args.summary_md:
        print(render_markdown(payload), end="")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
