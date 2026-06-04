#!/usr/bin/env python3
# Version: riftreader-recovery-classifier-v0.1.0
# Total-Character-Count: 0000021275
# Purpose: Classify RiftReader workflow/recovery state from existing artifacts and produce a compact project-manager board with next action.

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-recovery-classifier-v0.1.0"


@dataclass(frozen=True)
class Classification:
    name: str
    confidence: str
    reason: str
    blocker: str | None
    next_recommended_action: str
    next_recommended_command: str | None
    safe_automatic_actions: list[str]
    approval_required_actions: list[str]
    do_not_do: list[str]
    now: str
    next_step: str
    later: str


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return current


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return value if isinstance(value, dict) else {}


def safe_rel(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def latest_subdir(path: Path) -> Path | None:
    if not path.is_dir():
        return None
    dirs = [item for item in path.iterdir() if item.is_dir()]
    return max(dirs, key=lambda item: item.stat().st_mtime) if dirs else None


def latest_compact_status(repo_root: Path, explicit_path: Path | None = None) -> tuple[Path | None, dict[str, Any]]:
    if explicit_path is not None:
        path = explicit_path if explicit_path.is_absolute() else repo_root / explicit_path
        return path, read_json(path)
    root = repo_root / ".riftreader-local" / "workflow-status"
    latest = latest_subdir(root)
    if latest is None:
        return None, {}
    path = latest / "compact-sitrep.json"
    return path, read_json(path)


def run_git(args: list[str], cwd: Path, timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "exitCode": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "exitCode": None, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}


def git_state(repo_root: Path) -> dict[str, Any]:
    branch = run_git(["branch", "--show-current"], repo_root)
    status = run_git(["status", "--short", "--branch"], repo_root)
    head = run_git(["log", "-1", "--pretty=%H%n%s"], repo_root)
    remote = run_git(["ls-remote", "origin", "refs/heads/main"], repo_root)
    return {
        "branch": branch.get("stdout", "").strip(),
        "statusShort": status.get("stdout", ""),
        "isClean": not any(line and not line.startswith("## ") for line in status.get("stdout", "").splitlines()),
        "head": head.get("stdout", "").splitlines(),
        "remoteMain": remote.get("stdout", "").strip(),
        "commandsOk": {
            "branch": bool(branch.get("ok")),
            "status": bool(status.get("ok")),
            "head": bool(head.get("ok")),
            "remote": bool(remote.get("ok")),
        },
    }


def get_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def get_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def string_contains_any(values: list[Any], needles: list[str]) -> bool:
    text = "\n".join(str(value).lower() for value in values)
    return any(needle.lower() in text for needle in needles)


def evidence_from_status(status: dict[str, Any]) -> dict[str, Any]:
    workflow = get_dict(status.get("workflowClassification"))
    proof = get_dict(status.get("currentProof"))
    proof_freshness = get_dict(proof.get("proofFreshness"))
    live_target = get_dict(status.get("liveTarget"))
    static_owner = get_dict(status.get("staticOwnerReadback"))
    coord_chain = get_dict(static_owner.get("coordinateChain"))
    blockers = get_list(status.get("blockers"))
    warnings = get_list(status.get("warnings"))
    return {
        "status": status.get("status"),
        "generatedAtUtc": status.get("generatedAtUtc"),
        "workflowClassification": workflow,
        "classification": workflow.get("classification"),
        "workflowBlocker": workflow.get("blocker"),
        "proofAnchorCurrent": workflow.get("proofAnchorCurrent"),
        "staticOwnerRootNull": workflow.get("staticOwnerRootNull"),
        "currentProof": {
            "status": proof.get("status"),
            "targetPid": proof.get("targetPid"),
            "targetHwnd": proof.get("targetHwnd"),
            "proofFreshness": proof_freshness,
        },
        "liveTarget": live_target,
        "staticOwnerCoordinateChain": {
            "status": coord_chain.get("status"),
            "verdict": coord_chain.get("verdict"),
            "summaryJson": coord_chain.get("summaryJson"),
            "blockers": coord_chain.get("blockers") or [],
            "warnings": coord_chain.get("warnings") or [],
        },
        "blockers": blockers,
        "warnings": warnings,
    }


def classify(status: dict[str, Any], *, compact_status_path: Path | None) -> Classification:
    if not status:
        return Classification(
            name="status-refresh-needed",
            confidence="high",
            reason="No compact workflow status artifact was found.",
            blocker="compact-status-missing",
            next_recommended_action="Run compact workflow status before choosing recovery/discovery work.",
            next_recommended_command='python tools/riftreader_mcp/call_tool.py --tool riftreader.run_compact_status --timeout-seconds 240 --json',
            safe_automatic_actions=["run compact status", "read current handoff", "read git state"],
            approval_required_actions=[],
            do_not_do=["Do not run discovery or promotion until status exists."],
            now="Refresh compact status",
            next_step="Classify recovery lane from compact status",
            later="Run lane-specific automation only after classification",
        )

    ev = evidence_from_status(status)
    workflow = ev["workflowClassification"]
    blockers = ev["blockers"]
    coord_blockers = ev["staticOwnerCoordinateChain"]["blockers"]
    proof_current = workflow.get("proofAnchorCurrent")
    static_root_null = workflow.get("staticOwnerRootNull")
    classification = workflow.get("classification")
    workflow_blocker = workflow.get("blocker")

    if classification == "static-chain-repair-needed" or (proof_current is True and static_root_null is True):
        return Classification(
            name="static-chain-repair-needed",
            confidence="high",
            reason="Proof anchor is current, but static owner root/chain is null or blocked.",
            blocker=workflow_blocker or "static-root-null",
            next_recommended_action="Run or inspect static-chain repair diagnostics; do not rerun proof-anchor recovery for this state.",
            next_recommended_command='python tools/riftreader_mcp/call_tool.py --tool riftreader.run_static_chain_diagnostics --timeout-seconds 900 --json',
            safe_automatic_actions=[
                "run compact status",
                "run no-input static-chain diagnostics",
                "publish ChatGPT snapshot",
                "write handoff draft",
            ],
            approval_required_actions=[
                "static-chain promotion",
                "current-truth apply",
                "debugger attach",
                "movement",
            ],
            do_not_do=[
                "Do not rerun proof-anchor recovery when proofAnchorCurrent is true.",
                "Do not apply stale current-truth/dashboard artifacts.",
                "Do not promote heap/current-PID-only evidence as restart-stable truth.",
                "Do not use CE/x64dbg unless the debugger lane is explicitly selected later.",
            ],
            now="Static-chain repair",
            next_step="Use existing diagnostics/artifacts to identify repair target",
            later="Only build a new helper if the same blocker repeats",
        )

    stale_pid_terms = [
        "proof-anchor-stale",
        "proof-current:false",
        "pid-changed",
        "target-not-current",
        "current-proof-stale",
        "proofAnchorCurrent false",
    ]
    if proof_current is False or string_contains_any(blockers + coord_blockers, stale_pid_terms):
        return Classification(
            name="proof-reacquire-needed",
            confidence="high",
            reason="Current proof anchor is not current for the live target or PID/HWND epoch changed.",
            blocker=workflow_blocker or "proof-anchor-not-current",
            next_recommended_action="Run the proof-anchor reacquisition lane for the current live PID/HWND.",
            next_recommended_command="Use the existing full proof-anchor reacquire runner with explicit movement approval only when ready.",
            safe_automatic_actions=[
                "discover current PID/HWND",
                "run no-movement proof-anchor scan",
                "write recovery summary",
            ],
            approval_required_actions=[
                "bounded movement validation",
                "proof anchor promotion",
                "ProofOnly commit/push",
            ],
            do_not_do=[
                "Do not use old PID/HWND values.",
                "Do not run current-truth apply before proof is current.",
                "Do not skip ProofOnly after promotion.",
            ],
            now="Proof-anchor reacquisition",
            next_step="Discover current live target and run no-movement scan",
            later="After ProofOnly, return to static-chain classification",
        )

    live = ev["liveTarget"]
    live_verdict = str(live.get("verdict") or "").lower()
    if "stale" in live_verdict or string_contains_any(blockers, ["dashboard-stale", "current-truth-stale", "stale-artifact"]):
        return Classification(
            name="stale-dashboard-or-current-truth",
            confidence="medium",
            reason="Status indicates stale dashboard/current-truth artifact state.",
            blocker=workflow_blocker or "stale-dashboard-current-truth",
            next_recommended_action="Refresh the stale status/current-truth source only after backing proof evidence is current.",
            next_recommended_command='python tools/riftreader_mcp/call_tool.py --tool riftreader.run_compact_status --timeout-seconds 240 --json',
            safe_automatic_actions=["run compact status", "read proof anchor", "publish snapshot"],
            approval_required_actions=["current-truth write", "navigation enable"],
            do_not_do=[
                "Do not treat stale dashboard as live truth.",
                "Do not enable navigation from stale PID/HWND artifacts.",
            ],
            now="Stale artifact cleanup",
            next_step="Refresh status and compare proof/current-truth epochs",
            later="Apply current-truth only if gates pass",
        )

    if not blockers and str(status.get("status") or "").lower() in {"passed", "ok", "ready"}:
        return Classification(
            name="ready-or-review-needed",
            confidence="medium",
            reason="No blockers were detected in compact status.",
            blocker=None,
            next_recommended_action="Review latest status and handoff before selecting the next lane.",
            next_recommended_command='python tools/riftreader_mcp/call_tool.py --tool riftreader.get_current_handoff --json',
            safe_automatic_actions=["read handoff", "publish snapshot"],
            approval_required_actions=[],
            do_not_do=["Do not start a live-action lane without explicit operator selection."],
            now="Review ready status",
            next_step="Select next lane from handoff",
            later="Automate repeated lane if friction repeats",
        )

    return Classification(
        name="manual-review-needed",
        confidence="medium",
        reason="Compact status exists but did not match a known high-confidence recovery lane.",
        blocker=workflow_blocker or "unclassified-status",
        next_recommended_action="Have the LLM inspect the compact status and current handoff before running more tools.",
        next_recommended_command='python tools/riftreader_mcp/call_tool.py --tool riftreader.get_status --json',
        safe_automatic_actions=["read compact status", "read handoff", "read git state"],
        approval_required_actions=[],
        do_not_do=["Do not build new tools until the existing status artifact is interpreted."],
        now="Manual review",
        next_step="Classify missing rule or add playbook entry if repeated",
        later="Patch classifier only after repeated unclassified cases",
    )


def build_board(classification: Classification, git: dict[str, Any], compact_status_path: Path | None, repo_root: Path) -> dict[str, Any]:
    return {
        "currentLane": classification.name,
        "now": classification.now,
        "next": classification.next_step,
        "later": classification.later,
        "blockedBy": classification.blocker,
        "repo": {
            "branch": git.get("branch"),
            "head": git.get("head"),
            "isClean": git.get("isClean"),
        },
        "artifacts": {
            "compactStatus": safe_rel(repo_root, compact_status_path),
        },
    }


def build_summary(repo_root: Path, *, compact_status_path: Path | None, write: bool) -> dict[str, Any]:
    status_path, status = latest_compact_status(repo_root, compact_status_path)
    git = git_state(repo_root)
    decision = classify(status, compact_status_path=status_path)
    evidence = evidence_from_status(status) if status else {}
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-recovery-classifier",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "repoRoot": str(repo_root),
        "status": "passed",
        "classification": decision.name,
        "confidence": decision.confidence,
        "reason": decision.reason,
        "blocker": decision.blocker,
        "nextRecommendedAction": decision.next_recommended_action,
        "nextRecommendedCommand": decision.next_recommended_command,
        "safeAutomaticActions": decision.safe_automatic_actions,
        "approvalRequiredActions": decision.approval_required_actions,
        "doNotDo": decision.do_not_do,
        "board": build_board(decision, git, status_path, repo_root),
        "evidence": evidence,
        "inputs": {
            "compactStatusPath": safe_rel(repo_root, status_path),
        },
        "git": git,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "gitMutation": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "proofPromotion": False,
            "currentTruthWritten": False,
        },
    }

    if write:
        out_dir = repo_root / ".riftreader-local" / "recovery-classifier" / utc_stamp()
        latest_dir = repo_root / ".riftreader-local" / "recovery-classifier" / "latest"
        out_dir.mkdir(parents=True, exist_ok=True)
        latest_dir.mkdir(parents=True, exist_ok=True)
        for target_dir in (out_dir, latest_dir):
            json_path = target_dir / "summary.json"
            md_path = target_dir / "summary.md"
            json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            md_path.write_text(render_markdown(summary), encoding="utf-8")
        summary["artifacts"] = {
            "summaryJson": safe_rel(repo_root, out_dir / "summary.json"),
            "summaryMarkdown": safe_rel(repo_root, out_dir / "summary.md"),
            "latestJson": safe_rel(repo_root, latest_dir / "summary.json"),
            "latestMarkdown": safe_rel(repo_root, latest_dir / "summary.md"),
        }
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    board = summary.get("board") if isinstance(summary.get("board"), dict) else {}
    lines = [
        "# RiftReader Recovery Classifier",
        "",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Classification: `{summary.get('classification')}`",
        f"- Confidence: `{summary.get('confidence')}`",
        f"- Blocker: `{summary.get('blocker')}`",
        f"- Reason: {summary.get('reason')}",
        "",
        "## Project Board",
        "",
        "| Area | Status |",
        "|---|---|",
        f"| Current lane | `{board.get('currentLane')}` |",
        f"| Now | `{board.get('now')}` |",
        f"| Next | `{board.get('next')}` |",
        f"| Later | `{board.get('later')}` |",
        f"| Blocked by | `{board.get('blockedBy')}` |",
        "",
        "## Next Recommended Action",
        "",
        str(summary.get("nextRecommendedAction") or ""),
        "",
        "```text",
        str(summary.get("nextRecommendedCommand") or ""),
        "```",
        "",
        "## Safe Automatic Actions",
        "",
        *[f"- {item}" for item in summary.get("safeAutomaticActions") or []],
        "",
        "## Approval Required Actions",
        "",
        *[f"- {item}" for item in summary.get("approvalRequiredActions") or []],
        "",
        "## Do Not Do",
        "",
        *[f"- {item}" for item in summary.get("doNotDo") or []],
        "",
        "## END_OF_SCRIPT_MARKER",
        "",
    ]
    return "\n".join(lines)


def build_self_test() -> dict[str, Any]:
    static_status = {
        "status": "passed",
        "workflowClassification": {
            "classification": "static-chain-repair-needed",
            "blocker": "static-chain-repair-needed:root-pointer-null",
            "proofAnchorCurrent": True,
            "staticOwnerRootNull": True,
        },
        "blockers": [],
    }
    stale_status = {
        "workflowClassification": {
            "classification": None,
            "proofAnchorCurrent": False,
            "staticOwnerRootNull": True,
            "blocker": "proof-anchor-not-current",
        },
        "blockers": ["proof-anchor-stale"],
    }
    checks = [
        {
            "name": "classifies-static-chain-repair-needed",
            "pass": classify(static_status, compact_status_path=None).name == "static-chain-repair-needed",
        },
        {
            "name": "classifies-proof-reacquire-needed",
            "pass": classify(stale_status, compact_status_path=None).name == "proof-reacquire-needed",
        },
        {
            "name": "classifies-status-refresh-needed",
            "pass": classify({}, compact_status_path=None).name == "status-refresh-needed",
        },
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-recovery-classifier-self-test",
        "toolVersion": TOOL_VERSION,
        "status": "passed" if all(item["pass"] for item in checks) else "failed",
        "checks": checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--compact-status-json", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        payload = build_self_test()
    else:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
        payload = build_summary(repo_root, compact_status_path=args.compact_status_json, write=bool(args.write))
    if args.json or args.self_test:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_markdown(payload), end="")
    return 0 if payload.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())

# END_OF_SCRIPT_MARKER
