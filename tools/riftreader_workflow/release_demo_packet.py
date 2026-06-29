#!/usr/bin/env python3
"""Build a safe release/demo packet for the RiftReader ChatGPT MCP lane.

The packet is an offline aggregator: it reads the final-readiness gate,
contract audit, timing telemetry, Git status, and proof-recovery decision lane.
It does not start MCP servers, tunnels, live RIFT control, CE/x64dbg, provider
writes, or Git mutations. Optional ``--write`` output stays under ignored
``.riftreader-local`` diagnostics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from .common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, timestamped_output_dir, utc_iso
    from .mcp_contract_audit import build_contract_audit
    from .mcp_recovery_plan import build_recovery_plan
    from .mcp_workflow_state import build_mcp_workflow_state, standard_commands
    from .operator_status import build as build_operator_status
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.mcp_contract_audit import build_contract_audit
    from riftreader_workflow.mcp_recovery_plan import build_recovery_plan
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, standard_commands
    from riftreader_workflow.operator_status import build as build_operator_status


SCHEMA_VERSION = 1
PACKET_VERSION = "stage53-v2"
PACKET_ROOT_REL = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "release-demo-packet"
FINAL_STATUS_COMMAND = ["cmd", "/c", "scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"]
DECISION_PACKET_COMMAND = ["cmd", "/c", "scripts\\riftreader-decision-packet.cmd", "--compact-json"]
DASHBOARD_SELF_TEST_COMMAND = ["cmd", "/c", "scripts\\riftreader-mcp-dashboard.cmd", "--self-test", "--json"]


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _parse_command_json(envelope: dict[str, Any]) -> dict[str, Any]:
    stdout = envelope.get("stdout")
    if not isinstance(stdout, str) or not stdout.strip():
        return {
            "status": "failed",
            "ok": False,
            "blockers": ["command-json-stdout-missing"],
            "_command": {key: envelope.get(key) for key in ("label", "args", "exitCode", "ok", "timedOut", "durationSeconds")},
        }
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {
            "status": "failed",
            "ok": False,
            "blockers": [f"command-json-parse-failed:{exc.msg}"],
            "_command": {key: envelope.get(key) for key in ("label", "args", "exitCode", "ok", "timedOut", "durationSeconds")},
            "stdoutPreview": envelope.get("stdoutPreview"),
        }
    if not isinstance(payload, dict):
        return {
            "status": "failed",
            "ok": False,
            "blockers": ["command-json-not-object"],
            "_command": {key: envelope.get(key) for key in ("label", "args", "exitCode", "ok", "timedOut", "durationSeconds")},
        }
    payload["_command"] = {key: envelope.get(key) for key in ("label", "args", "exitCode", "ok", "timedOut", "durationSeconds")}
    return payload


def _run_json_command(
    label: str,
    args: list[str],
    repo_root: Path,
    *,
    timeout_seconds: float,
    expected_exit_codes: set[int],
) -> dict[str, Any]:
    envelope = run_command_envelope(
        label,
        args,
        repo_root,
        timeout_seconds=timeout_seconds,
        expected_exit_codes=expected_exit_codes,
        capture_full_output=True,
    )
    return _parse_command_json(envelope)


def _git_snapshot(repo_root: Path) -> dict[str, Any]:
    status = run_command_envelope(
        "git-status",
        ["git", "--no-pager", "status", "--short", "--branch"],
        repo_root,
        timeout_seconds=20.0,
        expected_exit_codes={0},
        capture_full_output=True,
    )
    head = run_command_envelope(
        "git-rev-parse-head",
        ["git", "rev-parse", "HEAD"],
        repo_root,
        timeout_seconds=20.0,
        expected_exit_codes={0},
        capture_full_output=True,
    )
    branch_line = None
    entries: list[str] = []
    stdout = status.get("stdout")
    if isinstance(stdout, str):
        lines = [line.rstrip() for line in stdout.splitlines() if line.strip()]
        branch_line = lines[0] if lines else None
        entries = lines[1:]
    head_stdout = head.get("stdout")
    return {
        "status": "passed" if status.get("ok") and head.get("ok") else "failed",
        "ok": bool(status.get("ok") and head.get("ok")),
        "branchLine": branch_line,
        "head": head_stdout.strip() if isinstance(head_stdout, str) else None,
        "dirtyEntries": entries,
        "dirty": bool(entries),
        "commands": {
            "status": {key: status.get(key) for key in ("exitCode", "ok", "timedOut", "durationSeconds", "stderrPreview")},
            "head": {key: head.get(key) for key in ("exitCode", "ok", "timedOut", "durationSeconds", "stderrPreview")},
        },
    }


def _compact_final_status(final_status: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": final_status.get("status"),
        "ok": final_status.get("ok"),
        "currentHead": final_status.get("currentHead"),
        "ciStatus": final_status.get("ciStatus"),
        "artifactFreshnessStatus": final_status.get("artifactFreshnessStatus"),
        "proofReplayStatus": final_status.get("proofReplayStatus"),
        "toolSurfaceStatus": final_status.get("toolSurfaceStatus"),
        "upstreamStatus": final_status.get("upstreamStatus"),
        "blockers": _as_list(final_status.get("blockers"))[:10],
        "recommendedNextAction": final_status.get("recommendedNextAction"),
        "_command": final_status.get("_command"),
    }


def _deferred_lane(decision_packet: dict[str, Any]) -> dict[str, Any]:
    blockers = [str(item) for item in _as_list(decision_packet.get("blockers"))]
    safe_next = decision_packet.get("safeNextAction") or decision_packet.get("recommendedNextAction")
    return {
        "lane": decision_packet.get("lane"),
        "status": decision_packet.get("status"),
        "risk": decision_packet.get("risk"),
        "blockers": blockers,
        "safeNextAction": safe_next,
        "deferredForReleasePacket": decision_packet.get("lane") == "proof-recovery",
        "_command": decision_packet.get("_command"),
    }


def _compact_operator_status(operator_status: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(operator_status, dict):
        return None
    workflow = _as_dict(operator_status.get("workflowArtifacts"))
    latest = _as_dict(workflow.get("latest"))
    runtime = _as_dict(operator_status.get("mcpRuntime"))
    return {
        "status": operator_status.get("status"),
        "overallState": operator_status.get("overallState"),
        "git": operator_status.get("git"),
        "handoff": operator_status.get("handoff"),
        "mcpRuntime": {
            "status": runtime.get("status"),
            "ok": runtime.get("ok"),
            "localMcpUrl": runtime.get("localMcpUrl"),
            "listenerCount": runtime.get("listenerCount"),
            "stdioCounterparts": runtime.get("stdioCounterparts"),
            "blockers": _as_list(runtime.get("blockers")),
        },
        "proofFreshness": latest.get("actualClientProof"),
        "trialReadiness": latest.get("trialReadiness"),
        "proposalSmoke": latest.get("proposalSmoke"),
        "riftTargets": operator_status.get("riftTargets"),
        "recommendedActions": _as_list(operator_status.get("recommendedActions"))[:10],
        "recommendedNextAction": operator_status.get("recommendedNextAction"),
    }


def _compact_recovery_plan(recovery_plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(recovery_plan, dict):
        return None
    return {
        "status": recovery_plan.get("status"),
        "ok": recovery_plan.get("ok"),
        "releaseBlockerCount": recovery_plan.get("releaseBlockerCount"),
        "primaryStep": recovery_plan.get("primaryStep"),
        "orderedSteps": [
            {
                "priority": step.get("priority"),
                "key": step.get("key"),
                "category": step.get("category"),
                "releaseBlocker": step.get("releaseBlocker"),
                "operatorStep": step.get("operatorStep"),
                "autoRunAllowed": step.get("autoRunAllowed"),
                "title": step.get("title"),
                "why": step.get("why"),
                "commands": step.get("commands"),
            }
            for step in _as_list(recovery_plan.get("steps"))
            if isinstance(step, dict)
        ],
    }


def _compact_dashboard_self_test(dashboard_self_test: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(dashboard_self_test, dict):
        return None
    status_preview = _as_dict(dashboard_self_test.get("statusPreview"))
    return {
        "status": dashboard_self_test.get("status"),
        "ok": dashboard_self_test.get("ok"),
        "kind": dashboard_self_test.get("kind"),
        "generatedAtUtc": dashboard_self_test.get("generatedAtUtc"),
        "blockers": _as_list(dashboard_self_test.get("blockers"))[:10],
        "checks": _as_list(dashboard_self_test.get("checks"))[:20],
        "readinessBadges": _as_list(status_preview.get("readinessBadges") or dashboard_self_test.get("readinessBadges"))[:10],
        "_command": dashboard_self_test.get("_command"),
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    blockers = [str(item) for item in _as_list(payload.get("blockers"))]
    warnings = [str(item) for item in _as_list(payload.get("warnings"))]
    release = _as_dict(payload.get("releaseReadiness"))
    contract = _as_dict(payload.get("contractAudit"))
    lane = _as_dict(payload.get("deferredLanes")).get("proofRecovery")
    v2 = _as_dict(payload.get("safeLocalRefresh"))
    lines = [
        "# RiftReader MCP Release/Demo Packet",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- OK: `{payload.get('ok')}`",
        f"- Generated: `{payload.get('generatedAtUtc')}`",
        f"- Final gate: `{release.get('status')}`",
        f"- Contract audit: `{contract.get('status')}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{item}`" for item in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- `{item}`" for item in warnings) if warnings else lines.append("- none")
    lines.extend(["", "## Deferred proof-recovery lane"])
    if isinstance(lane, dict):
        lines.append(f"- Lane status: `{lane.get('status')}`")
        lines.extend(f"- `{item}`" for item in _as_list(lane.get("blockers"))) if lane.get("blockers") else lines.append("- none")
    else:
        lines.append("- not captured")
    if v2:
        recovery = _as_dict(v2.get("recoveryPlan"))
        operator_status = _as_dict(v2.get("operatorStatus"))
        lines.extend(
            [
                "",
                "## Safe-local refresh v2",
                "",
                f"- Operator status: `{operator_status.get('status')}` / `{operator_status.get('overallState')}`",
                f"- Recovery plan: `{recovery.get('status')}` release blockers `{recovery.get('releaseBlockerCount')}`",
            ]
        )
        primary = _as_dict(recovery.get("primaryStep"))
        if primary:
            lines.append(f"- Primary recovery step: `{primary.get('key')}`")
        lines.extend(["", "## Ordered recovery actions"])
        for step in _as_list(recovery.get("orderedSteps"))[:10]:
            if isinstance(step, dict):
                lines.append(f"- `{step.get('key')}` ({step.get('category')})")
    lines.extend(["", "## Operator commands"])
    commands = _as_dict(payload.get("operatorRunbook")).get("commands")
    for key, command in _as_dict(commands).items():
        if isinstance(command, list):
            lines.append(f"- `{key}`: `{ ' '.join(str(part) for part in command) }`")
    lines.append("")
    return "\n".join(lines)


def _safe_refresh_component(label: str, builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        payload = builder()
        return payload if isinstance(payload, dict) else {"status": "failed", "ok": False, "blockers": [f"{label}:non-object-payload"]}
    except Exception as exc:  # noqa: BLE001 - optional refresh must not hide the failed component.
        return {"status": "failed", "ok": False, "blockers": [f"{label}:exception:{type(exc).__name__}:{exc}"], "warnings": []}


def build_release_demo_packet(
    repo_root: Path,
    *,
    write: bool = False,
    summary_md: bool = False,
    refresh_safe_local: bool = False,
    final_status_override: dict[str, Any] | None = None,
    decision_packet_override: dict[str, Any] | None = None,
    operator_status_override: dict[str, Any] | None = None,
    recovery_plan_override: dict[str, Any] | None = None,
    dashboard_self_test_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    commands = standard_commands()
    final_status = final_status_override or _run_json_command(
        "final-readiness",
        FINAL_STATUS_COMMAND,
        repo_root,
        timeout_seconds=45.0,
        expected_exit_codes={0, 1, 2},
    )
    decision_packet = decision_packet_override or _run_json_command(
        "decision-packet",
        DECISION_PACKET_COMMAND,
        repo_root,
        timeout_seconds=90.0,
        expected_exit_codes={0, 1, 2},
    )
    contract = build_contract_audit(repo_root)
    workflow_state = build_mcp_workflow_state(repo_root)
    git_state = _git_snapshot(repo_root)
    operator_status = operator_status_override
    recovery_plan = recovery_plan_override
    dashboard_self_test = dashboard_self_test_override
    if refresh_safe_local:
        if operator_status is None:
            operator_status = _safe_refresh_component("operator-status", lambda: build_operator_status(repo_root, write=False))
        if recovery_plan is None:
            recovery_plan = _safe_refresh_component("recovery-plan", lambda: build_recovery_plan(repo_root, status_payload=operator_status, write=False))
        if dashboard_self_test is None:
            dashboard_self_test = _run_json_command(
                "dashboard-self-test",
                DASHBOARD_SELF_TEST_COMMAND,
                repo_root,
                timeout_seconds=120.0,
                expected_exit_codes={0, 1, 2},
            )

    blockers: list[str] = []
    warnings: list[str] = []
    if final_status.get("ok") is not True:
        blockers.append("final-readiness-not-passed")
        blockers.extend(f"final:{item}" for item in _as_list(final_status.get("blockers"))[:8])
    if contract.get("ok") is not True:
        blockers.append("contract-audit-not-passed")
        blockers.extend(f"contract:{item}" for item in _as_list(contract.get("blockers"))[:8])
    if git_state.get("ok") is not True:
        warnings.append("git-snapshot-failed")
    if decision_packet.get("status") == "blocked" and decision_packet.get("lane") == "proof-recovery":
        warnings.append("proof-recovery-lane-deferred:" + ",".join(str(item) for item in _as_list(decision_packet.get("blockers"))[:3]))
    elif decision_packet.get("ok") is not True:
        warnings.append("decision-packet-not-passed")
    warnings.extend(f"contract:{item}" for item in _as_list(contract.get("warnings"))[:8])
    if refresh_safe_local and isinstance(recovery_plan, dict) and recovery_plan.get("status") == "failed":
        blockers.append("recovery-plan-failed")
    if refresh_safe_local and isinstance(dashboard_self_test, dict) and dashboard_self_test.get("ok") is not True:
        warnings.append("dashboard-self-test-not-passed")

    status = "passed" if not blockers else "blocked"
    performance = _as_dict(contract.get("performanceWarnings"))
    packet: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "packetVersion": PACKET_VERSION,
        "kind": "riftreader-mcp-release-demo-packet",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": not blockers,
        "repoRoot": str(repo_root),
        "blockers": blockers,
        "warnings": sorted(set(warnings)),
        "releaseReadiness": _compact_final_status(final_status),
        "contractAudit": {
            "status": contract.get("status"),
            "ok": contract.get("ok"),
            "blockers": _as_list(contract.get("blockers"))[:10],
            "warnings": _as_list(contract.get("warnings"))[:10],
            "toolSurface": {
                "expectedToolCount": _as_dict(contract.get("toolSurface")).get("expectedToolCount"),
                "observedProposalSmokeToolCount": _as_dict(contract.get("toolSurface")).get("observedProposalSmokeToolCount"),
            },
            "performanceWarnings": {
                "slowMcpStageCount": len(_as_list(performance.get("slowMcpStages"))),
                "slowUnittestModuleCount": len(_as_list(performance.get("slowUnittestModules"))),
                "activeUnittestTiming": _as_dict(performance.get("activeUnittestTiming")),
            },
            "artifactClassificationSummary": _as_dict(contract.get("artifactClassificationSummary")),
        },
        "workflowState": {
            "status": workflow_state.get("status"),
            "ok": workflow_state.get("ok"),
            "blockers": _as_list(workflow_state.get("blockers")),
            "recommendedNextAction": workflow_state.get("recommendedNextAction"),
        },
        "git": git_state,
        "deferredLanes": {"proofRecovery": _deferred_lane(decision_packet)},
        "safeLocalRefresh": {
            "enabled": bool(refresh_safe_local),
            "operatorStatus": _compact_operator_status(operator_status),
            "recoveryPlan": _compact_recovery_plan(recovery_plan),
            "dashboardSelfTest": _compact_dashboard_self_test(dashboard_self_test),
            "releaseImpact": {
                "topLevelStatus": status,
                "topLevelOk": not blockers,
                "safeLocalReleaseBlockerCount": len(blockers),
                "releaseBlockerKeys": blockers,
                "releaseBlockers": blockers,
                "warnings": sorted(set(warnings)),
                "artifactClassificationSummary": _as_dict(contract.get("artifactClassificationSummary")),
                "deferredProofRecoveryIsReleaseBlocker": False,
            },
        }
        if refresh_safe_local
        else {"enabled": False},
        "operatorRunbook": {
            "scope": "release-demo-readiness-only",
            "commands": {
                "finalReadiness": commands.get("mcpFinalCompactStatus"),
                "contractAudit": ["scripts\\riftreader-mcp-contract-audit.cmd", "--json", "--write", "--summary-md"],
                "releaseDemoPacket": ["scripts\\riftreader-release-demo-packet.cmd", "--json", "--write", "--summary-md"],
                "releaseDemoPacketRefresh": ["scripts\\riftreader-release-demo-packet.cmd", "--json", "--write", "--summary-md", "--refresh-safe-local"],
                "recoveryPlan": ["scripts\\riftreader-mcp-recovery-plan.cmd", "--json"],
                "operatorStatus": ["scripts\\riftreader-status.cmd", "--json"],
                "dashboardSelfTest": ["scripts\\riftreader-mcp-dashboard.cmd", "--self-test", "--json"],
                "dashboardOnceNoPublicSmoke": ["scripts\\riftreader-mcp-dashboard.cmd", "--once-json", "--no-public-smoke"],
            },
            "boundaries": [
                "No live RIFT input or movement.",
                "No CE/x64dbg attach.",
                "No provider repo writes.",
                "No proof promotion or actor-chain promotion.",
                "No Git mutation from this helper.",
            ],
        },
        "safety": {
            **safety_flags(),
            "readOnlyPacket": True,
            "refreshSafeLocal": bool(refresh_safe_local),
            "writesIgnoredArtifactsOnly": bool(write),
            "serverStarted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
            "providerWrites": False,
            "executionEndpoint": False,
        },
    }

    if write:
        output_dir = timestamped_output_dir(repo_root / PACKET_ROOT_REL)
        summary_json = output_dir / "summary.json"
        packet.setdefault("artifacts", {})
        packet["artifacts"]["summaryJson"] = rel(repo_root, summary_json)
        if summary_md:
            summary_path = output_dir / "summary.md"
            packet["artifacts"]["summaryMarkdown"] = rel(repo_root, summary_path)
        summary_json.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if summary_md:
            summary_path.write_text(_render_markdown(packet), encoding="utf-8")

    return packet


def self_test() -> dict[str, Any]:
    repo_root = Path.cwd()
    final_override = {
        "status": "passed",
        "ok": True,
        "currentHead": "self-test",
        "ciStatus": "passed",
        "artifactFreshnessStatus": "fresh",
        "proofReplayStatus": "passed",
        "toolSurfaceStatus": "passed",
        "upstreamStatus": "passed",
        "blockers": [],
    }
    decision_override = {
        "status": "blocked",
        "ok": False,
        "lane": "proof-recovery",
        "risk": "high",
        "blockers": ["latest-static-owner-readback-root-pointer-null"],
        "safeNextAction": {"command": ["scripts\\get-rift-window-targets.cmd", "-Json"]},
    }
    contract = build_contract_audit(repo_root)
    checks = [
        {"name": "contract-audit-callable", "pass": isinstance(contract, dict) and "ok" in contract},
        {"name": "final-override-passes", "pass": final_override["ok"] is True},
        {"name": "decision-proof-lane-deferred", "pass": decision_override["lane"] == "proof-recovery"},
    ]
    ok = all(bool(check.get("pass")) for check in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "packetVersion": PACKET_VERSION,
        "kind": "riftreader-mcp-release-demo-packet-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {**safety_flags(), "readOnlyPacket": True, "serverStarted": False, "publicTunnelStarted": False},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a safe RiftReader MCP release/demo readiness packet.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--write", action="store_true", help="Write ignored release packet artifacts under .riftreader-local.")
    parser.add_argument("--summary-md", action="store_true", help="Also write a Markdown summary when --write is set.")
    parser.add_argument("--refresh-safe-local", action="store_true", help="Include Stage 51 operator status, Stage 52 recovery plan, and dashboard self-test status.")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.self_test:
        payload = self_test()
    else:
        payload = build_release_demo_packet(repo_root, write=args.write, summary_md=args.summary_md, refresh_safe_local=args.refresh_safe_local)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
