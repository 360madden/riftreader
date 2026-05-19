#!/usr/bin/env python3
"""Read-only Phase 2 status/gate for the RiftReader ChatGPT MCP lane."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, safety_flags, unique, utc_iso
    from .mcp_ci_status import current_head_ci_status
    from .mcp_phase1_completion import phase1_status
    from .mcp_proof_replay import replay_actual_client_proof
    from .mcp_workflow_state import FRESHNESS_BUDGET_SECONDS, build_mcp_workflow_state, standard_commands
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, unique, utc_iso
    from riftreader_workflow.mcp_ci_status import current_head_ci_status
    from riftreader_workflow.mcp_phase1_completion import phase1_status
    from riftreader_workflow.mcp_proof_replay import replay_actual_client_proof
    from riftreader_workflow.mcp_workflow_state import FRESHNESS_BUDGET_SECONDS, build_mcp_workflow_state, standard_commands


def _phase1_proof_summary(payload: dict[str, Any]) -> dict[str, Any]:
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    checks_passed = all(isinstance(check, dict) and check.get("ok") is True for check in checks) if checks else False
    blockers = [
        str(blocker)
        for blocker in (payload.get("blockers") if isinstance(payload.get("blockers"), list) else [])
        if blocker != "git-working-tree-dirty"
    ]
    return {
        "status": "passed" if checks_passed and not blockers else "blocked",
        "ok": checks_passed and not blockers,
        "phase1Complete": payload.get("phase1Complete"),
        "repoSideComplete": payload.get("repoSideComplete"),
        "checksPassedIgnoringWorkingTree": checks_passed,
        "blockersIgnoringWorkingTree": blockers,
        "checks": checks,
    }


def _artifact_freshness(state: dict[str, Any]) -> dict[str, Any]:
    latest = state.get("latestArtifacts") if isinstance(state.get("latestArtifacts"), dict) else {}
    items: dict[str, dict[str, Any]] = {}
    stale: list[str] = []
    for kind, budget in FRESHNESS_BUDGET_SECONDS.items():
        item = latest.get(kind)
        if not isinstance(item, dict):
            items[kind] = {"status": "missing", "path": None, "ageSeconds": None, "budgetSeconds": budget}
            continue
        age = item.get("artifactAgeSeconds")
        status = "unknown"
        if isinstance(age, int):
            status = "fresh" if age <= budget else "stale"
        if status == "stale":
            stale.append(kind)
        items[kind] = {
            "status": status,
            "path": item.get("path"),
            "ageSeconds": age,
            "budgetSeconds": budget,
            "artifactStatus": item.get("status"),
            "ok": item.get("ok"),
        }
    return {
        "status": "fresh" if not stale else "stale",
        "ok": True,
        "staleKinds": stale,
        "items": items,
    }


def _next_action(
    *,
    phase1_proof: dict[str, Any],
    proof_replay: dict[str, Any],
    ci_status: dict[str, Any],
    git_dirty: bool,
) -> dict[str, Any]:
    commands = standard_commands()
    if not phase1_proof.get("ok"):
        return {
            "key": "restore-phase1-proof",
            "reason": "Phase 1 proof artifacts are incomplete; rerun the Phase 1 gate before Phase 2.",
            "command": commands["mcpPhase1Status"],
        }
    if not proof_replay.get("ok"):
        return {
            "key": "record-or-fix-actual-client-proof",
            "reason": "Saved actual-client proof did not replay cleanly.",
            "command": commands["trialProofTemplate"],
        }
    if not ci_status.get("ok"):
        return {
            "key": "inspect-current-head-ci",
            "reason": "Current HEAD CI is unavailable, missing, pending, or failing.",
            "command": [
                "gh",
                "run",
                "list",
                "--limit",
                "10",
                "--json",
                "databaseId,workflowName,headSha,status,conclusion,createdAt,updatedAt,event,url",
            ],
        }
    if git_dirty:
        return {
            "key": "safe-commit-plan",
            "reason": "Phase 2 gate is healthy for HEAD, but local changes are not covered by current-head CI.",
            "command": commands["safeCommitPlan"],
        }
    return {
        "key": "phase2-ready-next-hardening-slice",
        "reason": "Phase 1 proof replays, current-head CI passed, and artifacts have freshness metadata.",
        "command": commands["mcpMissionControl"],
    }


def phase2_status(
    repo_root: Path,
    *,
    proof_path: Path | None = None,
    ci_status_payload: dict[str, Any] | None = None,
    strict_artifacts: bool = False,
) -> dict[str, Any]:
    """Build the read-only Phase 2 status packet."""

    state = build_mcp_workflow_state(repo_root)
    phase1_payload = phase1_status(repo_root)
    phase1_proof = _phase1_proof_summary(phase1_payload)
    proof_replay = replay_actual_client_proof(repo_root, proof_path=proof_path, strict_artifacts=strict_artifacts)
    ci_status = ci_status_payload if ci_status_payload is not None else current_head_ci_status(repo_root)
    freshness = _artifact_freshness(state)
    git_state = state.get("gitDirtyState") if isinstance(state.get("gitDirtyState"), dict) else {}
    git_dirty = bool(git_state.get("dirty"))

    blockers: list[str] = []
    if not phase1_proof.get("ok"):
        blockers.extend([f"phase1:{blocker}" for blocker in phase1_proof.get("blockersIgnoringWorkingTree") or ["phase1-proof-incomplete"]])
    if not proof_replay.get("ok"):
        blockers.extend([f"proof-replay:{blocker}" for blocker in proof_replay.get("blockers") or ["proof-replay-blocked"]])
    if not ci_status.get("ok"):
        blockers.extend([f"ci:{blocker}" for blocker in ci_status.get("blockers") or ["ci-status-blocked"]])

    warnings = unique(
        [
            *(state.get("warnings") if isinstance(state.get("warnings"), list) else []),
            *(phase1_payload.get("warnings") if isinstance(phase1_payload.get("warnings"), list) else []),
            *(proof_replay.get("warnings") if isinstance(proof_replay.get("warnings"), list) else []),
            *(ci_status.get("warnings") if isinstance(ci_status.get("warnings"), list) else []),
        ]
    )
    if git_dirty:
        warnings.append("working-tree-dirty-current-head-ci-does-not-cover-local-changes")

    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-phase2-status",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "phase": "phase-2-mcp-durability",
        "phase2Ready": status == "passed",
        "blockers": blockers,
        "warnings": warnings,
        "phase1Proof": phase1_proof,
        "phase1Status": phase1_payload,
        "proofReplay": proof_replay,
        "ciStatus": ci_status,
        "artifactFreshness": freshness,
        "gitDirtyState": git_state,
        "recommendedNextAction": _next_action(
            phase1_proof=phase1_proof,
            proof_replay=proof_replay,
            ci_status=ci_status,
            git_dirty=git_dirty,
        ),
        "safety": {
            **safety_flags(),
            "phase2GateReadOnly": True,
            "proofReplayReadOnly": True,
            "readOnlyGitHubCliInspection": True,
            "publicTunnelStarted": False,
            "persistentServerStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
            "applyFlagSent": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    action = payload.get("recommendedNextAction") if isinstance(payload.get("recommendedNextAction"), dict) else {}
    ci = payload.get("ciStatus") if isinstance(payload.get("ciStatus"), dict) else {}
    proof = payload.get("proofReplay") if isinstance(payload.get("proofReplay"), dict) else {}
    freshness = payload.get("artifactFreshness") if isinstance(payload.get("artifactFreshness"), dict) else {}
    lines = [
        "# RiftReader MCP Phase 2 Status",
        "",
        f"- Generated UTC: `{payload.get('generatedAtUtc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Phase 1 proof: `{(payload.get('phase1Proof') or {}).get('status')}`",
        f"- Proof replay: `{proof.get('status')}`",
        f"- Proof freshness: `{(proof.get('proofFreshness') or {}).get('status')}`",
        f"- Current-head CI: `{ci.get('status')}`",
        f"- Artifact freshness: `{freshness.get('status')}`",
        "",
        "## Blockers",
        "",
    ]
    for blocker in payload.get("blockers") or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(
        [
            "",
            "## Recommended next action",
            "",
            f"- Key: `{action.get('key')}`",
            f"- Reason: {action.get('reason')}",
            f"- Command: `{' '.join(action.get('command') or [])}`",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def compact_phase2_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a bounded operator-facing summary of a Phase 2 status packet."""

    ci = payload.get("ciStatus") if isinstance(payload.get("ciStatus"), dict) else {}
    workflows = ci.get("workflows") if isinstance(ci.get("workflows"), dict) else {}
    proof = payload.get("proofReplay") if isinstance(payload.get("proofReplay"), dict) else {}
    proof_freshness = proof.get("proofFreshness") if isinstance(proof.get("proofFreshness"), dict) else {}
    artifact_consistency = proof.get("artifactConsistency") if isinstance(proof.get("artifactConsistency"), dict) else {}
    artifact_freshness = payload.get("artifactFreshness") if isinstance(payload.get("artifactFreshness"), dict) else {}
    git_state = payload.get("gitDirtyState") if isinstance(payload.get("gitDirtyState"), dict) else {}
    action = payload.get("recommendedNextAction") if isinstance(payload.get("recommendedNextAction"), dict) else {}
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-phase2-compact-status",
        "generatedAtUtc": payload.get("generatedAtUtc"),
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "phase2Ready": payload.get("phase2Ready"),
        "currentHead": ci.get("currentHead"),
        "phase1ProofStatus": (payload.get("phase1Proof") or {}).get("status") if isinstance(payload.get("phase1Proof"), dict) else None,
        "ciStatus": ci.get("status"),
        "ciWorkflows": [
            {
                "workflowName": item.get("workflowName"),
                "status": item.get("status"),
                "conclusion": item.get("conclusion"),
                "ok": item.get("ok"),
                "databaseId": item.get("databaseId"),
                "url": item.get("url"),
            }
            for item in workflows.values()
            if isinstance(item, dict)
        ],
        "proofReplayStatus": proof.get("status"),
        "proofPath": proof.get("proofPath"),
        "proofFreshnessStatus": proof_freshness.get("status"),
        "proofAgeSeconds": proof_freshness.get("ageSeconds"),
        "proofFreshnessBudgetSeconds": proof_freshness.get("budgetSeconds"),
        "artifactConsistencyStatus": artifact_consistency.get("status"),
        "artifactFreshnessStatus": artifact_freshness.get("status"),
        "staleArtifactKinds": artifact_freshness.get("staleKinds") or [],
        "gitDirty": git_state.get("dirty"),
        "gitDirtyCount": git_state.get("dirtyCount"),
        "recommendedNextAction": {
            "key": action.get("key"),
            "reason": action.get("reason"),
            "command": action.get("command") or [],
        },
        "blockers": blockers,
        "warnings": warnings,
        "warningCount": len(warnings),
        "safety": payload.get("safety"),
    }


def self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="riftreader-mcp-phase2-selftest-") as temp_name:
        root = Path(temp_name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        (root / "agents.md").write_text("# policy\n", encoding="utf-8")
        ci_payload = {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-current-head-ci-status",
            "generatedAtUtc": utc_iso(),
            "status": "passed",
            "ok": True,
            "currentHead": "self-test",
            "blockers": [],
            "warnings": [],
        }
        payload = phase2_status(root, ci_status_payload=ci_payload)
    checks = [
        {"name": "missing-proof-blocks", "pass": any(str(blocker).startswith("phase1:") for blocker in payload.get("blockers") or [])},
        {"name": "no-public-tunnel-started", "pass": payload.get("safety", {}).get("publicTunnelStarted") is False},
    ]
    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-phase2-status-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {
            **safety_flags(),
            "publicTunnelStarted": False,
            "gitMutation": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check RiftReader ChatGPT MCP Phase 2 status.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true", help="Print Phase 2 status.")
    mode.add_argument("--replay-proof", action="store_true", help="Replay/revalidate saved actual-client proof only.")
    mode.add_argument("--summary-md", action="store_true", help="Print Phase 2 status as Markdown.")
    mode.add_argument("--self-test", action="store_true", help="Run deterministic Phase 2 self-test.")
    parser.add_argument("--proof-path", default=None, help="Optional explicit proof.json path.")
    parser.add_argument("--strict-artifacts", action="store_true", help="Treat missing local proof-linked artifacts as blockers.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--compact-json", action="store_true", help="Emit a bounded operator-facing JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
        proof_path = Path(args.proof_path).resolve() if args.proof_path else None
        if args.self_test:
            payload = self_test()
        elif args.replay_proof:
            payload = replay_actual_client_proof(repo_root, proof_path=proof_path, strict_artifacts=args.strict_artifacts)
        else:
            payload = phase2_status(repo_root, proof_path=proof_path, strict_artifacts=args.strict_artifacts)
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with structured error.
        payload = {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-phase2-status",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "ok": False,
            "blockers": [f"phase2-status-exception:{type(exc).__name__}:{exc}"],
            "warnings": [],
            "safety": safety_flags(),
        }
    output_payload = compact_phase2_status(payload) if args.compact_json else payload
    if args.summary_md:
        print(render_markdown(payload))
    elif args.json or args.compact_json:
        print(json.dumps(output_payload, indent=2, sort_keys=True))
    else:
        action = output_payload.get("recommendedNextAction") if isinstance(output_payload.get("recommendedNextAction"), dict) else {}
        print(f"Status: {payload.get('status')} ok={payload.get('ok')}")
        print(f"Next: {action.get('key')} - {' '.join(action.get('command') or [])}")
        for blocker in payload.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
