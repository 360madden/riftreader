#!/usr/bin/env python3
"""Read-only MCP contract and timing audit for the RiftReader release lane.

The audit consolidates local MCP readiness/proposal artifacts, actual-client
proof shape, guarded package-apply behavior, and recent unittest timing
telemetry. It never starts servers, opens tunnels, sends RIFT input, attaches
debuggers, mutates Git, or writes provider repositories. Optional ``--write``
output is limited to ignored ``.riftreader-local`` diagnostics.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, repo_rel as rel, safety_flags, timestamped_output_dir, utc_iso
    from .mcp_tool_surface import (
        EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        EXPECTED_CHATGPT_MCP_TOOL_NAMES,
        PACKAGE_PROOF_TOOL_NAMES,
        PUBLIC_READ_ONLY_TOOL_NAMES,
    )
    from .mcp_workflow_state import build_mcp_workflow_state, passed, safe_load_json
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.mcp_tool_surface import (
        EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        EXPECTED_CHATGPT_MCP_TOOL_NAMES,
        PACKAGE_PROOF_TOOL_NAMES,
        PUBLIC_READ_ONLY_TOOL_NAMES,
    )
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, passed, safe_load_json


SCHEMA_VERSION = 1
AUDIT_ROOT_REL = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "contract-audit"
ACTIVE_UNITTEST_TIMINGS_REL = Path(".riftreader-local") / "active-unittest-timings" / "latest.json"
DEFAULT_SLOW_TOOL_WARNING_SECONDS = 1.0
DEFAULT_SLOW_MODULE_WARNING_SECONDS = 10.0
DOCS_ALIGNMENT = {
    "source": "OpenAI official MCP / Apps SDK docs",
    "mcpEndpoint": "/mcp",
    "transport": "streamable-http",
    "chatGptTerminology": "ChatGPT apps",
    "outputSchemaExpected": True,
    "slowResponsesRisk": "slow tool calls can make ChatGPT Apps interactions time out or feel unreliable",
}
HIGH_RISK_GATED_TOOL_NAMES = (
    "restart_mcp_runtime",
    "submit_actual_client_observation",
    "execute_live_control_action",
    "execute_debugger_ce_action",
    "apply_latest_package_draft",
    "commit_reviewed_slice",
    "push_current_branch",
)


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _artifact_path(repo_root: Path, item: dict[str, Any] | None) -> Path | None:
    if not isinstance(item, dict):
        return None
    path_value = item.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return repo_root / path_value


def _load_latest_artifact(repo_root: Path, item: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None, Path | None]:
    path = _artifact_path(repo_root, item)
    if path is None or not path.is_file():
        return None, "artifact-path-missing", path
    payload, warning = safe_load_json(path)
    return payload, warning, path


def _ordered_missing(expected: tuple[str, ...], observed: list[str]) -> list[str]:
    observed_set = set(observed)
    return [name for name in expected if name not in observed_set]


def _ordered_unexpected(expected: tuple[str, ...], observed: list[str]) -> list[str]:
    expected_set = set(expected)
    return [name for name in observed if name not in expected_set]


def _tool_names_from_proposal(payload: dict[str, Any]) -> list[str]:
    client = _as_dict(payload.get("client"))
    tool_names = client.get("toolNames")
    if isinstance(tool_names, list):
        return [str(name) for name in tool_names]
    health = _as_dict(client.get("healthStructuredContent"))
    tools = _as_list(health.get("tools"))
    names = [str(tool.get("name")) for tool in tools if isinstance(tool, dict) and tool.get("name")]
    return names


def _proposal_tool_count(payload: dict[str, Any], tool_names: list[str]) -> int | None:
    client = _as_dict(payload.get("client"))
    count = client.get("toolCount")
    if isinstance(count, int):
        return count
    health = _as_dict(client.get("healthStructuredContent"))
    health_count = health.get("toolCount")
    if isinstance(health_count, int):
        return health_count
    return len(tool_names) if tool_names else None


def _proposal_apply_without_approval(payload: dict[str, Any]) -> dict[str, Any]:
    client = _as_dict(payload.get("client"))
    structured = _as_dict(client.get("applyLatestPackageDraftWithoutApprovalStructuredContent"))
    apply_result = _as_dict(structured.get("applyResult"))
    applied = structured.get("applied")
    if applied is None:
        applied = apply_result.get("applied")
    blockers = structured.get("blockers")
    if not isinstance(blockers, list):
        blockers = apply_result.get("blockers") if isinstance(apply_result.get("blockers"), list) else []
    return {
        "applied": applied,
        "ok": structured.get("ok"),
        "status": structured.get("status"),
        "blockers": [str(item) for item in blockers],
        "approvalMissing": "APPLY_APPROVAL_MISSING" in {str(item) for item in blockers},
    }


def _slow_mcp_stages(payload: dict[str, Any], threshold_seconds: float) -> list[dict[str, Any]]:
    client = _as_dict(payload.get("client"))
    slow: list[dict[str, Any]] = []
    for item in _as_list(client.get("clientStepTimings")):
        if not isinstance(item, dict):
            continue
        duration = _safe_float(item.get("durationSeconds"))
        if duration is None or duration < threshold_seconds:
            continue
        slow.append(
            {
                "stage": item.get("stage"),
                "status": item.get("status"),
                "durationSeconds": round(duration, 6),
                "thresholdSeconds": threshold_seconds,
            }
        )
    slow.sort(key=lambda item: float(item.get("durationSeconds") or 0.0), reverse=True)
    return slow


def _load_active_unittest_timings(repo_root: Path, threshold_seconds: float) -> dict[str, Any]:
    path = repo_root / ACTIVE_UNITTEST_TIMINGS_REL
    if not path.is_file():
        return {
            "status": "missing",
            "ok": None,
            "path": rel(repo_root, path),
            "slowModules": [],
            "warnings": ["active-unittest-timings-missing"],
        }
    payload, warning = safe_load_json(path)
    if warning or payload is None:
        return {
            "status": "failed",
            "ok": False,
            "path": rel(repo_root, path),
            "slowModules": [],
            "warnings": [warning or "active-unittest-timings-invalid"],
        }
    slow_modules = payload.get("slowModules") if isinstance(payload.get("slowModules"), list) else []
    if not slow_modules:
        for module in _as_list(payload.get("moduleTimings")):
            if not isinstance(module, dict):
                continue
            duration = _safe_float(module.get("durationSeconds"))
            if duration is not None and duration >= threshold_seconds:
                slow_modules.append(module)
    compact_slow_modules: list[dict[str, Any]] = []
    for module in slow_modules:
        if not isinstance(module, dict):
            continue
        duration = _safe_float(module.get("durationSeconds"))
        compact_slow_modules.append(
            {
                "module": module.get("module") or module.get("name"),
                "durationSeconds": round(duration or 0.0, 6),
                "testCount": module.get("testCount"),
                "thresholdSeconds": threshold_seconds,
            }
        )
    compact_slow_modules.sort(key=lambda item: float(item.get("durationSeconds") or 0.0), reverse=True)
    return {
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "path": rel(repo_root, path),
        "durationSeconds": payload.get("durationSeconds"),
        "activeTestCount": payload.get("activeTestCount"),
        "slowModules": compact_slow_modules,
        "warnings": [],
    }


def _actual_client_contract(item: dict[str, Any] | None, blockers: list[str]) -> dict[str, Any]:
    if not item:
        blockers.append("actual-client-proof-missing")
        return {"status": "missing", "ok": False}

    tool_names = [str(name) for name in _as_list(item.get("toolNames"))]
    schema_names = [str(name) for name in _as_list(item.get("toolOutputSchemaToolNames"))]
    missing_tools = _ordered_missing(EXPECTED_CHATGPT_MCP_TOOL_NAMES, tool_names)
    missing_schema_tools = _ordered_missing(EXPECTED_CHATGPT_MCP_TOOL_NAMES, schema_names)

    if not passed(item):
        blockers.append("actual-client-proof-not-passed")
    if item.get("toolCount") != EXPECTED_CHATGPT_MCP_TOOL_COUNT:
        blockers.append(f"actual-client-proof-tool-count-mismatch:{item.get('toolCount')}")
    if missing_tools:
        blockers.append("actual-client-proof-missing-tools:" + ",".join(missing_tools[:6]))
    if item.get("toolOutputSchemasPresent") is not True:
        blockers.append("actual-client-proof-output-schemas-not-present")
    if item.get("toolOutputSchemaCount") != EXPECTED_CHATGPT_MCP_TOOL_COUNT:
        blockers.append(f"actual-client-proof-output-schema-count-mismatch:{item.get('toolOutputSchemaCount')}")
    if missing_schema_tools:
        blockers.append("actual-client-proof-missing-output-schema-tools:" + ",".join(missing_schema_tools[:6]))
    if item.get("clientTransportStatus") != "tool-call-succeeded":
        blockers.append(f"actual-client-proof-transport-not-succeeded:{item.get('clientTransportStatus')}")
    if item.get("applyLatestPackageDraftWithoutApprovalBlocked") is not True:
        blockers.append("actual-client-proof-apply-without-approval-not-blocked")
    if item.get("applyLatestPackageDraftWithoutApprovalApplied") is not False:
        blockers.append("actual-client-proof-apply-without-approval-applied-state-not-false")

    return {
        "status": item.get("status"),
        "ok": item.get("ok"),
        "path": item.get("path"),
        "toolCount": item.get("toolCount"),
        "missingExpectedTools": missing_tools,
        "toolOutputSchemasPresent": item.get("toolOutputSchemasPresent"),
        "toolOutputSchemaCount": item.get("toolOutputSchemaCount"),
        "missingOutputSchemaTools": missing_schema_tools,
        "clientTransportStatus": item.get("clientTransportStatus"),
        "applyWithoutApprovalBlocked": item.get("applyLatestPackageDraftWithoutApprovalBlocked"),
        "applyWithoutApprovalApplied": item.get("applyLatestPackageDraftWithoutApprovalApplied"),
    }


def _proposal_contract(
    payload: dict[str, Any] | None,
    path: Path | None,
    warning: str | None,
    blockers: list[str],
    *,
    slow_tool_warning_seconds: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if warning or payload is None:
        blockers.append(f"proposal-smoke-unavailable:{warning or 'missing'}")
        return {"status": "missing", "ok": False, "path": rel(path.parent, path) if path else None}, []

    tool_names = _tool_names_from_proposal(payload)
    tool_count = _proposal_tool_count(payload, tool_names)
    missing_tools = _ordered_missing(EXPECTED_CHATGPT_MCP_TOOL_NAMES, tool_names)
    unexpected_tools = _ordered_unexpected(EXPECTED_CHATGPT_MCP_TOOL_NAMES, tool_names)
    apply_guard = _proposal_apply_without_approval(payload)
    root_safety = _as_dict(payload.get("safety"))
    slow_stages = _slow_mcp_stages(payload, slow_tool_warning_seconds)

    if tool_count != EXPECTED_CHATGPT_MCP_TOOL_COUNT:
        blockers.append(f"proposal-smoke-tool-count-mismatch:{tool_count}")
    if missing_tools:
        blockers.append("proposal-smoke-missing-expected-tools:" + ",".join(missing_tools[:6]))
    if unexpected_tools:
        blockers.append("proposal-smoke-unexpected-tools:" + ",".join(unexpected_tools[:6]))
    if apply_guard.get("applied") is not False or apply_guard.get("approvalMissing") is not True:
        blockers.append("proposal-smoke-apply-without-approval-not-blocked")
    if root_safety.get("temporaryLoopbackServerStarted") is not True:
        blockers.append("proposal-smoke-temporary-loopback-server-not-started")
    if root_safety.get("serverStopped") is not True:
        blockers.append("proposal-smoke-server-not-stopped")
    if root_safety.get("publicTunnelStarted") is not False:
        blockers.append("proposal-smoke-public-tunnel-started")
    if root_safety.get("proposalSubmitTransportCovered") is not True:
        blockers.append("proposal-smoke-submit-transport-not-covered")
    if root_safety.get("proposalSubmitWritesLocalInboxOnly") is not True:
        blockers.append("proposal-smoke-submit-not-local-inbox-only")
    for key in ("movementSent", "inputSent", "reloaduiSent", "screenshotKeySent", "x64dbgAttach", "providerWrites", "gitMutation"):
        if root_safety.get(key) is not False:
            blockers.append(f"proposal-smoke-unsafe-safety-flag:{key}")
    if root_safety.get("noCheatEngine") is not True:
        blockers.append("proposal-smoke-unsafe-safety-flag:noCheatEngine")

    contract = {
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "path": str(path) if path else None,
        "toolCount": tool_count,
        "expectedToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "missingExpectedTools": missing_tools,
        "unexpectedTools": unexpected_tools,
        "applyWithoutApproval": apply_guard,
        "temporaryLoopbackServerStarted": root_safety.get("temporaryLoopbackServerStarted"),
        "serverStopped": root_safety.get("serverStopped"),
        "publicTunnelStarted": root_safety.get("publicTunnelStarted"),
        "proposalSubmitTransportCovered": root_safety.get("proposalSubmitTransportCovered"),
        "proposalSubmitWritesLocalInboxOnly": root_safety.get("proposalSubmitWritesLocalInboxOnly"),
    }
    return contract, slow_stages


def _render_markdown(payload: dict[str, Any]) -> str:
    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    performance = _as_dict(payload.get("performanceWarnings"))
    slow_stages = performance.get("slowMcpStages") if isinstance(performance.get("slowMcpStages"), list) else []
    slow_modules = performance.get("slowUnittestModules") if isinstance(performance.get("slowUnittestModules"), list) else []
    lines = [
        "# RiftReader MCP Contract Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- OK: `{payload.get('ok')}`",
        f"- Generated: `{payload.get('generatedAtUtc')}`",
        f"- Expected tools: `{EXPECTED_CHATGPT_MCP_TOOL_COUNT}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{item}`" for item in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- `{item}`" for item in warnings) if warnings else lines.append("- none")
    lines.extend(["", "## Slow MCP stages"])
    lines.extend(
        f"- `{item.get('stage')}`: `{item.get('durationSeconds')}` seconds" for item in slow_stages[:10]
    ) if slow_stages else lines.append("- none")
    lines.extend(["", "## Slow unittest modules"])
    lines.extend(
        f"- `{item.get('module')}`: `{item.get('durationSeconds')}` seconds" for item in slow_modules[:10]
    ) if slow_modules else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_contract_audit(
    repo_root: Path,
    *,
    slow_tool_warning_seconds: float = DEFAULT_SLOW_TOOL_WARNING_SECONDS,
    slow_module_warning_seconds: float = DEFAULT_SLOW_MODULE_WARNING_SECONDS,
    write: bool = False,
    summary_md: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    state = build_mcp_workflow_state(repo_root)
    latest = _as_dict(state.get("latestArtifacts"))
    blockers: list[str] = []
    warnings: list[str] = [str(item) for item in _as_list(state.get("warnings"))]

    readiness = latest.get("readiness") if isinstance(latest.get("readiness"), dict) else None
    proposal_smoke = latest.get("proposal-smoke") if isinstance(latest.get("proposal-smoke"), dict) else None
    actual_proof = latest.get("actual-client-proof") if isinstance(latest.get("actual-client-proof"), dict) else None

    if not passed(readiness):
        blockers.append("latest-readiness-not-passed")
    if not passed(proposal_smoke):
        blockers.append("latest-proposal-smoke-not-passed")

    proposal_payload, proposal_warning, proposal_path = _load_latest_artifact(repo_root, proposal_smoke)
    proposal_contract, slow_stages = _proposal_contract(
        proposal_payload,
        proposal_path,
        proposal_warning,
        blockers,
        slow_tool_warning_seconds=slow_tool_warning_seconds,
    )
    actual_contract = _actual_client_contract(actual_proof, blockers)
    unittest_timing = _load_active_unittest_timings(repo_root, slow_module_warning_seconds)
    warnings.extend(str(item) for item in _as_list(unittest_timing.get("warnings")))

    tool_names = _tool_names_from_proposal(proposal_payload or {})
    status = "passed" if not blockers else "blocked"
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-contract-audit",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": not blockers,
        "repoRoot": str(repo_root),
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "toolSurface": {
            "expectedToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "expectedToolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "observedProposalSmokeToolCount": proposal_contract.get("toolCount"),
            "observedProposalSmokeToolNames": tool_names,
            "publicReadOnlyToolNames": list(PUBLIC_READ_ONLY_TOOL_NAMES),
            "packageProofToolNames": list(PACKAGE_PROOF_TOOL_NAMES),
            "highRiskGatedToolNames": list(HIGH_RISK_GATED_TOOL_NAMES),
            "proposalSmoke": proposal_contract,
            "actualClientProof": actual_contract,
        },
        "docsAlignment": DOCS_ALIGNMENT,
        "performanceWarnings": {
            "slowToolWarningSeconds": slow_tool_warning_seconds,
            "slowModuleWarningSeconds": slow_module_warning_seconds,
            "slowMcpStages": slow_stages,
            "slowUnittestModules": unittest_timing.get("slowModules"),
            "activeUnittestTiming": unittest_timing,
        },
        "latestArtifacts": {
            "readiness": readiness,
            "proposalSmoke": proposal_smoke,
            "actualClientProof": actual_proof,
        },
        "commands": {
            "contractAudit": ["scripts\\riftreader-mcp-contract-audit.cmd", "--json"],
            "contractAuditWrite": ["scripts\\riftreader-mcp-contract-audit.cmd", "--json", "--write", "--summary-md"],
            "releaseDemoPacket": ["scripts\\riftreader-release-demo-packet.cmd", "--json", "--write", "--summary-md"],
        },
        "safety": {
            **safety_flags(),
            "readOnlyAudit": True,
            "writesIgnoredArtifactsOnly": bool(write),
            "publicTunnelStarted": False,
            "persistentServerStarted": False,
            "chatGptRegistrationPerformed": False,
            "executionEndpoint": False,
        },
    }

    if write:
        output_dir = timestamped_output_dir(repo_root / AUDIT_ROOT_REL)
        summary_json = output_dir / "summary.json"
        payload.setdefault("artifacts", {})
        payload["artifacts"]["summaryJson"] = rel(repo_root, summary_json)
        if summary_md:
            summary_path = output_dir / "summary.md"
            payload["artifacts"]["summaryMarkdown"] = rel(repo_root, summary_path)
        summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if summary_md:
            summary_path.write_text(_render_markdown(payload), encoding="utf-8")

    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seed_contract_artifacts(repo_root: Path, *, missing_tool: str | None = None) -> None:
    tool_names = [name for name in EXPECTED_CHATGPT_MCP_TOOL_NAMES if name != missing_tool]
    transport_root = repo_root / ".riftreader-local" / "riftreader-chatgpt-mcp" / "transport-smoke"
    proof_root = repo_root / ".riftreader-local" / "riftreader-chatgpt-mcp" / "actual-client-proof" / "20260620-000000Z"
    _write_json(
        transport_root / "20260620T000000Z-trial-readiness.json",
        {"kind": "test-readiness", "status": "passed", "ok": True, "blockers": [], "warnings": []},
    )
    _write_json(
        transport_root / "20260620T000001Z-proposal-transport-smoke.json",
        {
            "kind": "test-proposal-smoke",
            "status": "passed",
            "ok": True,
            "blockers": [],
            "warnings": [],
            "client": {
                "toolCount": len(tool_names),
                "toolNames": tool_names,
                "clientStepTimings": [
                    {"stage": "initialize", "status": "passed", "durationSeconds": 0.2},
                    {"stage": "call_tool:dry_run_latest_package_draft", "status": "passed", "durationSeconds": 1.6},
                ],
                "applyLatestPackageDraftWithoutApprovalStructuredContent": {
                    "applied": False,
                    "ok": False,
                    "status": "blocked",
                    "blockers": ["APPLY_APPROVAL_MISSING"],
                },
            },
            "safety": {
                **safety_flags(),
                "temporaryLoopbackServerStarted": True,
                "serverStopped": True,
                "publicTunnelStarted": False,
                "proposalSubmitTransportCovered": True,
                "proposalSubmitWritesLocalInboxOnly": True,
            },
        },
    )
    _write_json(
        proof_root / "proof.json",
        {
            "kind": "test-proof",
            "status": "passed",
            "ok": True,
            "proof": {
                "toolCount": len(tool_names),
                "toolNames": tool_names,
                "toolOutputSchemasPresent": missing_tool is None,
                "toolOutputSchemaCount": len(tool_names),
                "toolOutputSchemaToolNames": tool_names,
                "clientTransportStatus": "tool-call-succeeded",
                "applyLatestPackageDraftWithoutApprovalBlocked": True,
                "applyLatestPackageDraftWithoutApprovalApplied": False,
            },
            "safety": safety_flags(),
        },
    )
    _write_json(
        repo_root / ACTIVE_UNITTEST_TIMINGS_REL,
        {
            "status": "passed",
            "ok": True,
            "durationSeconds": 12.5,
            "activeTestCount": 3,
            "slowModules": [{"module": "scripts.test_example", "durationSeconds": 11.0, "testCount": 2}],
        },
    )


def self_test() -> dict[str, Any]:
    checks: list[dict[str, Any]] = [
        {"name": "expected-tool-count-is-40", "pass": EXPECTED_CHATGPT_MCP_TOOL_COUNT == 40},
        {"name": "package-tools-are-expected-tools", "pass": set(PACKAGE_PROOF_TOOL_NAMES).issubset(EXPECTED_CHATGPT_MCP_TOOL_NAMES)},
        {"name": "high-risk-tools-are-expected-tools", "pass": set(HIGH_RISK_GATED_TOOL_NAMES).issubset(EXPECTED_CHATGPT_MCP_TOOL_NAMES)},
    ]
    temp_parent: Path | None = None
    try:
        temp_parent = find_repo_root(Path.cwd()) / ".riftreader-local" / "contract-audit-self-test"
        temp_parent.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001 - self-test still works outside a repo, just slower.
        temp_parent = None
    with tempfile.TemporaryDirectory(dir=temp_parent) as temp_dir:
        root = Path(temp_dir)
        _seed_contract_artifacts(root)
        payload = build_contract_audit(root)
        checks.extend(
            [
                {"name": "seeded-audit-passes", "pass": payload.get("ok") is True},
                {
                    "name": "seeded-audit-captures-slow-mcp-stage",
                    "pass": bool(_as_dict(payload.get("performanceWarnings")).get("slowMcpStages")),
                },
                {"name": "seeded-audit-read-only", "pass": _as_dict(payload.get("safety")).get("readOnlyAudit") is True},
            ]
        )
    ok = all(bool(check.get("pass")) for check in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-contract-audit-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {**safety_flags(), "readOnlyAudit": True, "serverStarted": False, "publicTunnelStarted": False},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only RiftReader MCP contract and timing audit.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--write", action="store_true", help="Write ignored audit artifacts under .riftreader-local.")
    parser.add_argument("--summary-md", action="store_true", help="Also write a Markdown summary when --write is set.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--slow-tool-warning-seconds", type=float, default=DEFAULT_SLOW_TOOL_WARNING_SECONDS)
    parser.add_argument("--slow-module-warning-seconds", type=float, default=DEFAULT_SLOW_MODULE_WARNING_SECONDS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.self_test:
        payload = self_test()
    else:
        payload = build_contract_audit(
            repo_root,
            slow_tool_warning_seconds=args.slow_tool_warning_seconds,
            slow_module_warning_seconds=args.slow_module_warning_seconds,
            write=args.write,
            summary_md=args.summary_md,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
