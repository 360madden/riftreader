#!/usr/bin/env python3
"""Phase 1 completion gate for the RiftReader ChatGPT MCP lane.

The gate is deliberately local/offline except for reading existing ignored
proof artifacts. It does not start servers, tunnels, ChatGPT registration,
RIFT input, CE, x64dbg, or Git mutation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .chatgpt_trial_recorder import validate_proof
    from .common import find_repo_root, repo_rel, safety_flags, utc_iso, utc_stamp
    from .mcp_workflow_state import build_mcp_workflow_state, passed
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.chatgpt_trial_recorder import validate_proof
    from riftreader_workflow.common import find_repo_root, repo_rel, safety_flags, utc_iso, utc_stamp
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, passed


PHASE1_CHECKS = (
    ("readiness", "Local MCP trial readiness passed"),
    ("proposal-smoke", "Guarded submit_package_proposal transport smoke passed"),
    ("cloudflare-smoke", "Public HTTPS /mcp smoke passed"),
    ("trial-session", "Bounded ChatGPT trial-session setup passed"),
    ("actual-client-proof", "Actual ChatGPT client proof validates against current proof rules"),
)
REPO_SIDE_CHECKS = {"readiness", "proposal-smoke", "cloudflare-smoke", "trial-session"}


def _current_actual_client_proof_blockers(repo_root: Path, item: dict[str, Any] | None) -> list[str]:
    if not passed(item):
        return ["actual-client-proof-not-passed"]
    if not isinstance(item, dict):
        return ["actual-client-proof-artifact-missing"]
    proof_path_value = item.get("path")
    if not isinstance(proof_path_value, str) or not proof_path_value:
        return ["actual-client-proof-path-missing"]
    proof_path = repo_root / proof_path_value
    try:
        loaded = json.loads(proof_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - fail closed while preserving evidence.
        return [f"actual-client-proof-json-invalid:{type(exc).__name__}:{exc}"]
    if not isinstance(loaded, dict):
        return ["actual-client-proof-json-not-object"]
    proof = loaded.get("proof")
    if not isinstance(proof, dict):
        return ["actual-client-proof-payload-missing-proof-object"]
    return [f"actual-client-proof-invalid:{blocker}" for blocker in validate_proof(proof)]


def build_check(kind: str, label: str, latest: dict[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    item = latest.get(kind)
    if kind == "trial-session":
        ready_item = latest.get("trial-session-ready")
        if passed(ready_item):
            item = ready_item
    proof_rule_blockers: list[str] = []
    if kind == "actual-client-proof":
        if repo_root is None:
            proof_rule_blockers = ["actual-client-proof-repo-root-missing"]
        else:
            proof_rule_blockers = _current_actual_client_proof_blockers(repo_root, item if isinstance(item, dict) else None)
    ok = passed(item) and not proof_rule_blockers
    return {
        "kind": kind,
        "label": label,
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "path": item.get("path") if isinstance(item, dict) else None,
        "artifactStatus": item.get("status") if isinstance(item, dict) else None,
        "publicMcpUrl": item.get("publicMcpUrl") if isinstance(item, dict) else None,
        "connectionMode": item.get("connectionMode") if isinstance(item, dict) else None,
        "publicUrlExpectedExpired": bool(item.get("publicUrlExpectedExpired")) if isinstance(item, dict) else False,
        "selfTest": bool(item.get("selfTest")) if isinstance(item, dict) else False,
        "blockers": [] if ok else proof_rule_blockers or [f"{kind}-not-passed"],
    }


def phase1_status(repo_root: Path) -> dict[str, Any]:
    state = build_mcp_workflow_state(repo_root)
    latest = state.get("latestArtifacts") if isinstance(state.get("latestArtifacts"), dict) else {}
    checks = [build_check(kind, label, latest, repo_root=repo_root) for kind, label in PHASE1_CHECKS]
    blockers: list[str] = []
    for check in checks:
        if not check["ok"]:
            blockers.extend(check["blockers"])
    git_state = state.get("gitDirtyState") if isinstance(state.get("gitDirtyState"), dict) else {}
    if git_state.get("dirty"):
        blockers.append("git-working-tree-dirty")
    repo_side_complete = all(check["ok"] for check in checks if check["kind"] in REPO_SIDE_CHECKS)
    phase1_complete = not blockers
    status = "passed" if phase1_complete else "blocked"
    next_action = {
        "key": "record-actual-client-proof",
        "reason": "Actual ChatGPT Developer Mode proof is still required; write the current fillable proof template first.",
        "command": ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--write-template", "--json"],
    }
    if "git-working-tree-dirty" in blockers:
        next_action = state.get("recommendedNextAction") or next_action
    elif phase1_complete:
        next_action = {
            "key": "phase1-complete-handoff",
            "reason": "Phase 1 completion criteria are satisfied; preserve a compact handoff.",
            "command": ["scripts\\riftreader-mcp-phase1.cmd", "--write-handoff", "--json"],
        }
    elif not repo_side_complete:
        next_action = state.get("recommendedNextAction") or next_action
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-phase1-completion-status",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": phase1_complete,
        "phase": "phase-1-chatgpt-mcp",
        "repoSideComplete": repo_side_complete,
        "phase1Complete": phase1_complete,
        "blockers": blockers,
        "checks": checks,
        "warnings": state.get("warnings") or [],
        "counts": state.get("counts"),
        "gitDirtyState": git_state,
        "recommendedNextAction": next_action,
        "safety": {
            **safety_flags(),
            "phase1GateReadOnly": True,
            "publicTunnelStarted": False,
            "persistentServerStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# RiftReader ChatGPT MCP Phase 1 Status",
        "",
        f"- Generated UTC: `{payload.get('generatedAtUtc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Repo-side complete: `{payload.get('repoSideComplete')}`",
        f"- Phase 1 complete: `{payload.get('phase1Complete')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Artifact | Notes |",
        "|---|---|---|---|",
    ]
    for check in payload.get("checks") or []:
        notes = []
        if check.get("publicUrlExpectedExpired"):
            notes.append("ephemeral URL stopped/expected expired")
        if check.get("selfTest"):
            notes.append("self-test")
        lines.append(
            f"| `{check.get('kind')}` | `{check.get('status')}` | `{check.get('path') or ''}` | {', '.join(notes)} |"
        )
    lines.extend(["", "## Blockers", ""])
    for blocker in payload.get("blockers") or ["none"]:
        lines.append(f"- `{blocker}`")
    action = payload.get("recommendedNextAction") if isinstance(payload.get("recommendedNextAction"), dict) else {}
    lines.extend(
        [
            "",
            "## Recommended next action",
            "",
            f"- Key: `{action.get('key')}`",
            f"- Reason: {action.get('reason')}",
            f"- Command: `{' '.join(action.get('command') or [])}`",
            "",
            "## Safety",
            "",
            "- No RIFT input, CE, x64dbg, provider writes, public tunnel startup, or Git mutation performed by this gate.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_handoff(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    handoff_dir = repo_root / "docs" / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    suffix = "complete" if payload.get("phase1Complete") else "blocked"
    path = handoff_dir / f"{utc_stamp()}-mcp-phase1-{suffix}-handoff.md"
    text = render_markdown(payload)
    if not payload.get("phase1Complete"):
        text += (
            "\n## Handoff note\n\n"
            "Autonomous repo-side Phase 1 work is complete, but actual ChatGPT Developer Mode proof remains external-client blocked. "
            "Do not mark full Phase 1 complete until `actual-client-proof` is passed.\n"
        )
    path.write_text(text, encoding="utf-8")
    return {
        **payload,
        "handoffPath": repo_rel(repo_root, path),
        "safety": {
            **payload.get("safety", {}),
            "handoffWritten": True,
            "gitMutation": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check RiftReader ChatGPT MCP Phase 1 completion status.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true", help="Print phase 1 completion status.")
    mode.add_argument("--checklist-md", action="store_true", help="Print phase 1 completion checklist as Markdown.")
    mode.add_argument("--write-handoff", action="store_true", help="Write a compact phase 1 handoff/status file.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    payload = phase1_status(repo_root)
    if args.write_handoff:
        payload = write_handoff(repo_root, payload)
    if args.checklist_md:
        print(render_markdown(payload))
    elif args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Status: {payload['status']}")
        print(f"Repo-side complete: {payload['repoSideComplete']}")
        print(f"Phase 1 complete: {payload['phase1Complete']}")
        for blocker in payload.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
        if payload.get("handoffPath"):
            print(f"Handoff: {payload['handoffPath']}")
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
