#!/usr/bin/env python3
"""Local-only Stage 38 consideration gate for the ChatGPT MCP workflow.

This helper deliberately does not expose an MCP tool. It summarizes whether the
repo/runtime/proof state is strong enough to draft a Stage 38 approval packet,
and it still requires an explicit live-boundary approval token before returning
``passed``. It never starts servers or tunnels, records proof, sends RIFT input,
attaches debuggers, mutates Git, or writes provider repositories.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, safety_flags, unique, utc_iso
    from .mcp_final_readiness import compact_final_readiness, final_readiness
    from .mcp_runtime_control import DEFAULT_PUBLIC_MCP_URL, build_tunnel_status
    from .mcp_server_status import build_status_payload
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, unique, utc_iso
    from riftreader_workflow.mcp_final_readiness import compact_final_readiness, final_readiness
    from riftreader_workflow.mcp_runtime_control import DEFAULT_PUBLIC_MCP_URL, build_tunnel_status
    from riftreader_workflow.mcp_server_status import build_status_payload


SCHEMA_VERSION = 1
KIND = "riftreader-stage38-consideration-status"
VERSION = "riftreader-stage38-consideration-v0.1.0"
STAGE38_APPROVAL_TOKEN = "STAGE38-LIVE-BOUNDARY-APPROVED"


def _criterion(
    key: str,
    *,
    ok: bool,
    summary: str,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "summary": summary,
        "blockers": blockers or [],
        "warnings": warnings or [],
        "evidence": evidence or {},
    }


def _runtime_criterion(runtime_payload: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = [str(item) for item in runtime_payload.get("warnings") or []]
    if runtime_payload.get("status") != "running-current" or runtime_payload.get("ok") is not True:
        blockers.append(f"stage38:mcp-runtime-not-current:{runtime_payload.get('status') or 'unknown'}")
    runtime_surface = runtime_payload.get("runtimeSurface") if isinstance(runtime_payload.get("runtimeSurface"), dict) else {}
    if runtime_surface and runtime_surface.get("ok") is not True:
        blockers.append(f"stage38:mcp-runtime-surface-not-passed:{runtime_surface.get('status') or 'unknown'}")
    source_freshness = (
        runtime_payload.get("runtimeSourceFreshness")
        if isinstance(runtime_payload.get("runtimeSourceFreshness"), dict)
        else {}
    )
    if source_freshness and source_freshness.get("ok") is not True:
        blockers.append(f"stage38:mcp-runtime-source-not-fresh:{source_freshness.get('status') or 'unknown'}")
    stdio = runtime_payload.get("stdioCounterparts") if isinstance(runtime_payload.get("stdioCounterparts"), dict) else {}
    if stdio and stdio.get("ok") is not True:
        blockers.append(f"stage38:stdio-counterparts-not-clean:{stdio.get('status') or 'unknown'}")

    return _criterion(
        "mcp-runtime-current",
        ok=not blockers,
        summary="Local MCP backend must be running-current with the expected loaded tool surface.",
        blockers=unique(blockers + [str(item) for item in runtime_payload.get("blockers") or []]),
        warnings=warnings,
        evidence={
            "status": runtime_payload.get("status"),
            "pid": ((runtime_payload.get("selectedListener") or {}).get("owningProcess"))
            if isinstance(runtime_payload.get("selectedListener"), dict)
            else None,
            "runtimeSurfaceStatus": runtime_surface.get("status"),
            "observedToolCount": runtime_surface.get("observedToolCount"),
            "stdioCounterpartsStatus": stdio.get("status"),
            "sourceFreshnessStatus": source_freshness.get("status"),
        },
    )


def _tunnel_criterion(tunnel_payload: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if tunnel_payload.get("status") != "passed" or tunnel_payload.get("ok") is not True:
        blockers.append(f"stage38:public-route-not-passed:{tunnel_payload.get('status') or 'unknown'}")
    blockers.extend(str(item) for item in tunnel_payload.get("blockers") or [])
    public_probe = (
        tunnel_payload.get("publicRouteProbe") if isinstance(tunnel_payload.get("publicRouteProbe"), dict) else {}
    )
    local_runtime = tunnel_payload.get("localRuntime") if isinstance(tunnel_payload.get("localRuntime"), dict) else {}
    return _criterion(
        "cloudflare-route-current",
        ok=not blockers,
        summary="Cloudflare named Tunnel route must forward to the current MCP backend.",
        blockers=unique(blockers),
        warnings=[str(item) for item in tunnel_payload.get("warnings") or []],
        evidence={
            "status": tunnel_payload.get("status"),
            "publicMcpUrl": tunnel_payload.get("publicMcpUrl"),
            "connectionMode": tunnel_payload.get("connectionMode"),
            "publicRouteProbeStatus": public_probe.get("status"),
            "localRuntimeStatus": local_runtime.get("status"),
        },
    )


def _final_readiness_criterion(final_payload: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if final_payload.get("status") != "passed" or final_payload.get("ok") is not True:
        blockers.append(f"stage38:final-readiness-not-passed:{final_payload.get('status') or 'unknown'}")
    blockers.extend(str(item) for item in final_payload.get("blockers") or [])
    compact = compact_final_readiness(final_payload)
    return _criterion(
        "final-readiness-passed",
        ok=not blockers,
        summary="Final readiness must pass before Stage 38 can be considered.",
        blockers=unique(blockers),
        warnings=[str(item) for item in final_payload.get("warnings") or []],
        evidence={
            "currentHead": final_payload.get("currentHead"),
            "ciStatus": compact.get("ciStatus"),
            "phase2Status": compact.get("phase2Status"),
            "proofReplayStatus": compact.get("proofReplayStatus"),
            "proofFreshnessStatus": compact.get("proofFreshnessStatus"),
            "artifactFreshnessStatus": compact.get("artifactFreshnessStatus"),
            "recommendedNextAction": compact.get("recommendedNextAction"),
        },
    )


def _approval_criterion(*, approval_token: str | None, prerequisites_ok: bool) -> dict[str, Any]:
    if not prerequisites_ok:
        return _criterion(
            "explicit-live-boundary-approval",
            ok=False,
            summary="Live-boundary approval is not actionable until all pre-Stage-38 prerequisites pass.",
            blockers=["stage38:approval-waiting-on-prerequisites"],
            evidence={"requiredApprovalToken": STAGE38_APPROVAL_TOKEN, "approvalTokenAccepted": False},
        )
    accepted = approval_token == STAGE38_APPROVAL_TOKEN
    return _criterion(
        "explicit-live-boundary-approval",
        ok=accepted,
        summary="Stage 38 is a live RIFT boundary and requires explicit approval before an approval packet can pass.",
        blockers=[] if accepted else ["stage38:explicit-live-boundary-approval-required"],
        evidence={"requiredApprovalToken": STAGE38_APPROVAL_TOKEN, "approvalTokenAccepted": accepted},
    )


def build_stage38_consideration_status(
    repo_root: Path,
    *,
    approval_token: str | None = None,
    public_mcp_url: str = DEFAULT_PUBLIC_MCP_URL,
    final_payload: dict[str, Any] | None = None,
    runtime_payload: dict[str, Any] | None = None,
    tunnel_payload: dict[str, Any] | None = None,
    check_tunnel: bool = True,
) -> dict[str, Any]:
    """Return the fail-closed Stage 38 consideration status."""

    final_payload = final_payload if final_payload is not None else final_readiness(repo_root)
    runtime_payload = (
        runtime_payload
        if runtime_payload is not None
        else build_status_payload(repo_root, check_runtime_surface=True)
    )
    if check_tunnel:
        tunnel_payload = (
            tunnel_payload
            if tunnel_payload is not None
            else build_tunnel_status(repo_root, public_mcp_url=public_mcp_url)
        )
    else:
        tunnel_payload = {
            "status": "skipped",
            "ok": None,
            "publicMcpUrl": public_mcp_url,
            "connectionMode": "cloudflare-named-tunnel",
            "blockers": ["stage38:tunnel-check-skipped"],
            "warnings": ["stage38:tunnel-check-skipped-not-valid-for-final-consideration"],
        }

    criteria = [
        _runtime_criterion(runtime_payload),
        _tunnel_criterion(tunnel_payload),
        _final_readiness_criterion(final_payload),
    ]
    prerequisites_ok = all(bool(item.get("ok")) for item in criteria)
    criteria.append(_approval_criterion(approval_token=approval_token, prerequisites_ok=prerequisites_ok))

    blockers = unique(
        str(blocker)
        for criterion in criteria
        for blocker in (criterion.get("blockers") if isinstance(criterion.get("blockers"), list) else [])
    )
    warnings = unique(
        str(warning)
        for criterion in criteria
        for warning in (criterion.get("warnings") if isinstance(criterion.get("warnings"), list) else [])
    )
    if prerequisites_ok and approval_token != STAGE38_APPROVAL_TOKEN:
        status = "approval-required"
    else:
        status = "passed" if not blockers else "blocked"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "stage": 38,
        "stageName": "Live RIFT read-only state surface",
        "stage38Active": False,
        "stage38Started": False,
        "blockers": blockers,
        "warnings": warnings,
        "criteria": criteria,
        "requiredApprovalToken": STAGE38_APPROVAL_TOKEN,
        "recommendedNextAction": _next_action(status, criteria),
        "safety": {
            **safety_flags(),
            "stage38Started": False,
            "stage38ToolSurfaceChanged": False,
            "liveBoundaryApprovalTokenRequired": True,
            "liveBoundaryApprovalAccepted": approval_token == STAGE38_APPROVAL_TOKEN,
            "finalGateReadOnly": True,
            "serverStarted": False,
            "serverStopped": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "providerWrites": False,
            "gitMutation": False,
            "inputSent": False,
            "movementSent": False,
            "x64dbgAttach": False,
            "noCheatEngine": True,
        },
    }


def _next_action(status: str, criteria: list[dict[str, Any]]) -> dict[str, Any]:
    final_item = next((item for item in criteria if item.get("key") == "final-readiness-passed"), {})
    final_next = ((final_item.get("evidence") or {}).get("recommendedNextAction")) if isinstance(final_item, dict) else None
    runtime_item = next((item for item in criteria if item.get("key") == "mcp-runtime-current"), {})
    tunnel_item = next((item for item in criteria if item.get("key") == "cloudflare-route-current"), {})

    if runtime_item and runtime_item.get("ok") is not True:
        return {
            "key": "fix-mcp-runtime-before-stage38",
            "reason": "Stage 38 consideration requires a current local MCP backend first.",
            "command": ["scripts\\riftreader-mcp-server-status.cmd", "--json"],
        }
    if tunnel_item and tunnel_item.get("ok") is not True:
        return {
            "key": "fix-cloudflare-route-before-stage38",
            "reason": "Stage 38 consideration requires the public ChatGPT route to reach the current backend.",
            "command": ["python", "tools\\riftreader_workflow\\riftreader_chatgpt_mcp.py", "--call", "get_tunnel_status", "--json"],
        }
    if final_item and final_item.get("ok") is not True:
        if isinstance(final_next, dict):
            return final_next
        return {
            "key": "pass-final-readiness-before-stage38",
            "reason": "Stage 38 consideration requires final readiness to pass.",
            "command": ["scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"],
        }
    if status == "approval-required":
        return {
            "key": "request-stage38-live-boundary-approval",
            "reason": "All local prerequisites passed; Stage 38 still needs explicit live-boundary approval.",
            "command": [
                "scripts\\riftreader-stage38-consideration.cmd",
                "--status",
                "--approval-token",
                STAGE38_APPROVAL_TOKEN,
                "--json",
            ],
        }
    return {
        "key": "draft-stage38-approval-packet",
        "reason": "Stage 38 consideration gate passed; draft an approval packet before implementing live tooling.",
        "command": ["scripts\\riftreader-stage38-consideration.cmd", "--status", "--json"],
    }


def compact_stage38_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-stage38-consideration-compact-status",
        "generatedAtUtc": payload.get("generatedAtUtc"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "stage38Active": payload.get("stage38Active"),
        "stage38Started": payload.get("stage38Started"),
        "blockers": payload.get("blockers") or [],
        "warnings": payload.get("warnings") or [],
        "criteria": [
            {
                "key": item.get("key"),
                "status": item.get("status"),
                "ok": item.get("ok"),
                "evidence": item.get("evidence"),
                "blockers": item.get("blockers") or [],
            }
            for item in payload.get("criteria") or []
            if isinstance(item, dict)
        ],
        "recommendedNextAction": payload.get("recommendedNextAction"),
        "safety": payload.get("safety"),
    }


def self_test() -> dict[str, Any]:
    final_ok = {
        "status": "passed",
        "ok": True,
        "blockers": [],
        "warnings": [],
        "currentHead": "self-test",
        "ci": {"status": "passed", "ok": True},
        "phase2": {"status": "passed", "ok": True},
        "artifacts": {"freshness": {"status": "fresh"}},
        "recommendedNextAction": {"key": "maintenance-loop"},
    }
    runtime_ok = {
        "status": "running-current",
        "ok": True,
        "blockers": [],
        "warnings": [],
        "selectedListener": {"owningProcess": 1234},
        "runtimeSurface": {"status": "passed", "ok": True, "observedToolCount": 33},
        "runtimeSourceFreshness": {"status": "passed", "ok": True},
        "stdioCounterparts": {"status": "not-running", "ok": True},
    }
    tunnel_ok = {
        "status": "passed",
        "ok": True,
        "blockers": [],
        "warnings": [],
        "publicMcpUrl": DEFAULT_PUBLIC_MCP_URL,
        "connectionMode": "cloudflare-named-tunnel",
        "publicRouteProbe": {"status": "passed", "ok": True},
        "localRuntime": {"status": "running-current", "ok": True},
    }
    approval_required = build_stage38_consideration_status(
        Path.cwd(),
        final_payload=final_ok,
        runtime_payload=runtime_ok,
        tunnel_payload=tunnel_ok,
    )
    approved = build_stage38_consideration_status(
        Path.cwd(),
        approval_token=STAGE38_APPROVAL_TOKEN,
        final_payload=final_ok,
        runtime_payload=runtime_ok,
        tunnel_payload=tunnel_ok,
    )
    final_blocked = dict(final_ok)
    final_blocked.update({"status": "blocked", "ok": False, "blockers": ["proof:replay-failed:tool-count-not-33:20"]})
    blocked = build_stage38_consideration_status(
        Path.cwd(),
        final_payload=final_blocked,
        runtime_payload=runtime_ok,
        tunnel_payload=tunnel_ok,
    )
    checks = [
        {"name": "all-prerequisites-still-need-approval", "pass": approval_required.get("status") == "approval-required"},
        {"name": "approved-prerequisites-pass", "pass": approved.get("status") == "passed"},
        {
            "name": "final-readiness-blocker-blocks-stage38",
            "pass": "stage38:final-readiness-not-passed:blocked" in (blocked.get("blockers") or []),
        },
    ]
    ok = all(bool(check["pass"]) for check in checks)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-stage38-consideration-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {
            **safety_flags(),
            "stage38Started": False,
            "inputSent": False,
            "movementSent": False,
            "gitMutation": False,
            "providerWrites": False,
            "x64dbgAttach": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether Stage 38 can be considered.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true", help="Print Stage 38 consideration status.")
    mode.add_argument("--self-test", action="store_true", help="Run deterministic self-test fixtures.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--public-mcp-url", default=DEFAULT_PUBLIC_MCP_URL)
    parser.add_argument("--approval-token", default=None)
    parser.add_argument("--skip-tunnel-status", action="store_true", help="Skip public route probe; output cannot pass.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--compact-json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
        payload = (
            self_test()
            if args.self_test
            else build_stage38_consideration_status(
                repo_root,
                approval_token=args.approval_token,
                public_mcp_url=args.public_mcp_url,
                check_tunnel=not args.skip_tunnel_status,
            )
        )
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with structured error.
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": KIND,
            "version": VERSION,
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "ok": False,
            "stage38Active": False,
            "stage38Started": False,
            "blockers": [f"stage38-consideration-exception:{type(exc).__name__}:{exc}"],
            "warnings": [],
            "safety": safety_flags(),
        }
    output_payload = compact_stage38_status(payload) if args.compact_json else payload
    if args.json or args.compact_json:
        print(json.dumps(output_payload, indent=2, sort_keys=True))
    else:
        action = payload.get("recommendedNextAction") if isinstance(payload.get("recommendedNextAction"), dict) else {}
        print(f"Status: {payload.get('status')} ok={payload.get('ok')}")
        print(f"Next: {action.get('key')} - {' '.join(action.get('command') or [])}")
        for blocker in payload.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    if payload.get("status") == "failed":
        return 1
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
