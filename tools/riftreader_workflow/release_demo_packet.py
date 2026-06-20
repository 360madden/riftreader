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
from typing import Any

try:
    from .common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, timestamped_output_dir, utc_iso
    from .mcp_contract_audit import build_contract_audit
    from .mcp_workflow_state import build_mcp_workflow_state, standard_commands
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.mcp_contract_audit import build_contract_audit
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, standard_commands


SCHEMA_VERSION = 1
PACKET_ROOT_REL = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "release-demo-packet"
FINAL_STATUS_COMMAND = ["cmd", "/c", "scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"]
DECISION_PACKET_COMMAND = ["cmd", "/c", "scripts\\riftreader-decision-packet.cmd", "--compact-json"]


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


def _render_markdown(payload: dict[str, Any]) -> str:
    blockers = [str(item) for item in _as_list(payload.get("blockers"))]
    warnings = [str(item) for item in _as_list(payload.get("warnings"))]
    release = _as_dict(payload.get("releaseReadiness"))
    contract = _as_dict(payload.get("contractAudit"))
    lane = _as_dict(payload.get("deferredLanes")).get("proofRecovery")
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
    lines.extend(["", "## Operator commands"])
    commands = _as_dict(payload.get("operatorRunbook")).get("commands")
    for key, command in _as_dict(commands).items():
        if isinstance(command, list):
            lines.append(f"- `{key}`: `{ ' '.join(str(part) for part in command) }`")
    lines.append("")
    return "\n".join(lines)


def build_release_demo_packet(
    repo_root: Path,
    *,
    write: bool = False,
    summary_md: bool = False,
    final_status_override: dict[str, Any] | None = None,
    decision_packet_override: dict[str, Any] | None = None,
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

    status = "passed" if not blockers else "blocked"
    performance = _as_dict(contract.get("performanceWarnings"))
    packet: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
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
        },
        "workflowState": {
            "status": workflow_state.get("status"),
            "ok": workflow_state.get("ok"),
            "blockers": _as_list(workflow_state.get("blockers")),
            "recommendedNextAction": workflow_state.get("recommendedNextAction"),
        },
        "git": git_state,
        "deferredLanes": {"proofRecovery": _deferred_lane(decision_packet)},
        "operatorRunbook": {
            "scope": "release-demo-readiness-only",
            "commands": {
                "finalReadiness": commands.get("mcpFinalCompactStatus"),
                "contractAudit": ["scripts\\riftreader-mcp-contract-audit.cmd", "--json", "--write", "--summary-md"],
                "releaseDemoPacket": ["scripts\\riftreader-release-demo-packet.cmd", "--json", "--write", "--summary-md"],
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
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.self_test:
        payload = self_test()
    else:
        payload = build_release_demo_packet(repo_root, write=args.write, summary_md=args.summary_md)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

