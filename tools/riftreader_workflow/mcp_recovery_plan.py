#!/usr/bin/env python3
"""Build a guided, read-only MCP readiness recovery plan.

The plan converts the unified operator-status packet into ordered recovery
steps. It never starts servers, tunnels, ChatGPT registration, live RIFT input,
debuggers, proof promotion, provider writes, or Git mutation. Commands in the
plan are recommendations for the operator or a later explicitly invoked helper.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, repo_rel, safety_flags, timestamped_output_dir, utc_iso
    from .operator_status import build as build_operator_status
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel, safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.operator_status import build as build_operator_status


SCHEMA_VERSION = 1
VERSION = "riftreader-mcp-recovery-plan-v0.1.0"
OUTPUT_ROOT_REL = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "recovery-plan"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value)]


def _command(
    label: str,
    args: list[str],
    *,
    run_policy: str = "operator-run",
    expected_exit_codes: list[int] | None = None,
    starts_runtime: bool = False,
    writes_ignored_artifacts: bool = False,
    external_action: bool = False,
) -> dict[str, Any]:
    return {
        "label": label,
        "args": args,
        "runPolicy": run_policy,
        "expectedExitCodes": expected_exit_codes or [0, 2],
        "startsRuntime": starts_runtime,
        "writesIgnoredArtifacts": writes_ignored_artifacts,
        "externalAction": external_action,
    }


def _step(
    priority: int,
    key: str,
    title: str,
    why: str,
    commands: list[dict[str, Any]],
    *,
    source: str,
    source_blockers: list[str] | None = None,
    category: str = "operator-action-needed",
    auto_run_allowed: bool = False,
    operator_step: bool = False,
    release_blocker: bool = True,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "key": key,
        "title": title,
        "why": why,
        "source": source,
        "sourceBlockers": source_blockers or [],
        "category": category,
        "releaseBlocker": release_blocker,
        "safe": True,
        "autoRunAllowed": auto_run_allowed,
        "operatorStep": operator_step,
        "commands": commands,
    }


def _contains(blockers: list[str], token: str) -> bool:
    return any(token in blocker for blocker in blockers)


def _append_unique(steps: list[dict[str, Any]], step: dict[str, Any]) -> None:
    if any(existing.get("key") == step.get("key") for existing in steps):
        return
    steps.append(step)


def _collect_blockers(status: dict[str, Any]) -> dict[str, list[str]]:
    final_state = _as_dict(status.get("finalReadiness"))
    runtime = _as_dict(status.get("mcpRuntime"))
    workflow = _as_dict(status.get("workflowArtifacts"))
    decision = _as_dict(status.get("decisionPacket"))
    runtime_sequence = _as_list(runtime.get("dependencySequence"))
    dependency_blockers = [
        str(item.get("key"))
        for item in runtime_sequence
        if isinstance(item, dict) and item.get("ok") is False and item.get("key")
    ]
    return {
        "final": _strings(final_state.get("blockers")),
        "runtime": [*_strings(runtime.get("blockers")), *dependency_blockers],
        "workflow": _strings(workflow.get("blockers")),
        "decision": _strings(decision.get("blockers")),
    }


def build_steps(status: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = _collect_blockers(status)
    final_blockers = blockers["final"]
    runtime_blockers = blockers["runtime"]
    decision_blockers = blockers["decision"]
    workflow = _as_dict(status.get("workflowArtifacts"))
    latest = _as_dict(workflow.get("latest"))
    runtime = _as_dict(status.get("mcpRuntime"))
    targets = _as_dict(status.get("riftTargets"))

    steps: list[dict[str, Any]] = []

    if _contains(final_blockers, "git:dirty-worktree"):
        _append_unique(
            steps,
            _step(
                10,
                "review-safe-commit-plan",
                "Review explicit-path commit plan",
                "Final readiness requires a clean worktree before release/demo proof can be trusted.",
                [_command("safe commit plan", ["scripts\\riftreader-safe-commit-packager.cmd", "--plan", "--json"])],
                source="finalReadiness",
                source_blockers=[item for item in final_blockers if "git:dirty-worktree" in item],
                category="release-blocker",
            ),
        )

    if _contains(final_blockers, "ci:not-completed") or _contains(final_blockers, "phase2:not-ready"):
        _append_unique(
            steps,
            _step(
                20,
                "wait-for-ci-then-recheck-final-readiness",
                "Wait for current-head CI, then recheck final readiness",
                "Final readiness is blocked by current-head CI or phase-2 readiness; this is evidence freshness, not a code fix.",
                [_command("final readiness", ["scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"])],
                source="finalReadiness",
                source_blockers=[item for item in final_blockers if "ci:not-completed" in item or "phase2:not-ready" in item],
                category="operator-action-needed",
                operator_step=True,
            ),
        )

    trial = _as_dict(latest.get("trialReadiness"))
    if _contains(final_blockers, "artifact:trial-readiness-stale") or trial.get("status") in {"stale", "missing"}:
        _append_unique(
            steps,
            _step(
                30,
                "refresh-trial-readiness",
                "Refresh local MCP trial readiness",
                "The latest local trial-readiness artifact is stale or missing.",
                [
                    _command(
                        "trial readiness",
                        ["scripts\\riftreader-operator-lite.cmd", "--mcp-trial-readiness", "--json"],
                        writes_ignored_artifacts=True,
                    )
                ],
                source="workflowArtifacts",
                source_blockers=[item for item in final_blockers if "trial-readiness" in item],
                category="release-blocker",
            ),
        )

    proposal = _as_dict(latest.get("proposalSmoke"))
    if _contains(final_blockers, "artifact:proposal-smoke-stale") or proposal.get("status") in {"stale", "missing"}:
        _append_unique(
            steps,
            _step(
                40,
                "refresh-proposal-transport-smoke",
                "Refresh package/proposal transport smoke evidence",
                "The package/proposal smoke artifact is stale or missing; trial readiness usually refreshes the same local proposal loop.",
                [
                    _command(
                        "trial readiness including proposal loop",
                        ["scripts\\riftreader-operator-lite.cmd", "--mcp-trial-readiness", "--json"],
                        writes_ignored_artifacts=True,
                    )
                ],
                source="workflowArtifacts",
                source_blockers=[item for item in final_blockers if "proposal-smoke" in item],
                category="release-blocker",
            ),
        )

    if not runtime.get("ok") or _contains(runtime_blockers, "local-mcp-server-listener-query-failed") or _contains(runtime_blockers, "loopback-listener"):
        _append_unique(
            steps,
            _step(
                50,
                "start-full-http-mcp-runtime",
                "Start the full local HTTP MCP runtime",
                "The saved ChatGPT connector does not start the backend; actual-client proof needs the full HTTP runtime on 127.0.0.1:8770.",
                [
                    _command(
                        "start full HTTP runtime",
                        ["START_RIFTREADER_CHATGPT_MCP.cmd", "serve"],
                        run_policy="operator-start",
                        expected_exit_codes=[0],
                        starts_runtime=True,
                    ),
                    _command("verify runtime", ["scripts\\riftreader-mcp-server-status.cmd", "--json"]),
                ],
                source="mcpRuntime",
                source_blockers=runtime_blockers,
                category="operator-action-needed",
                operator_step=True,
            ),
        )

    if _contains(runtime_blockers, "tool-profile") or _contains(runtime_blockers, "runtime-loaded-tool-surface"):
        _append_unique(
            steps,
            _step(
                60,
                "verify-tool-surface",
                "Verify the full current tool surface",
                "The live runtime must expose the current full MCP tool surface before proof replay is meaningful.",
                [_command("server status", ["scripts\\riftreader-mcp-server-status.cmd", "--json"])],
                source="mcpRuntime",
                source_blockers=runtime_blockers,
                category="operator-action-needed",
            ),
        )

    if _contains(final_blockers, "proof:stale") or _contains(final_blockers, "actual-client"):
        _append_unique(
            steps,
            _step(
                70,
                "refresh-actual-client-proof",
                "Refresh actual ChatGPT Web/Desktop MCP proof",
                "The saved actual-client proof is stale; local runtime facts cannot substitute for observed ChatGPT/Web Desktop tool-call proof.",
                [
                    _command("write proof template", ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--write-template", "--json"], writes_ignored_artifacts=True),
                    _command("check latest proof template", ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--check-latest-template", "--json"]),
                    _command(
                        "record filled actual-client proof",
                        ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--record", "--input", "<filled-proof.json>", "--json"],
                        writes_ignored_artifacts=True,
                        external_action=True,
                    ),
                ],
                source="finalReadiness",
                source_blockers=[item for item in final_blockers if "proof" in item or "actual-client" in item],
                category="operator-action-needed",
                operator_step=True,
            ),
        )

    if _contains(final_blockers, "public") or _contains(runtime_blockers, "public-route"):
        _append_unique(
            steps,
            _step(
                80,
                "verify-public-route",
                "Verify public route/domain diagnostics",
                "After the local backend is healthy, verify the Cloudflare named Tunnel/public route separately.",
                [_command("domain diagnostics", ["scripts\\riftreader-mcp-domain-diagnostics.cmd", "--json", "--write", "--summary-md"], writes_ignored_artifacts=True)],
                source="mcpRuntime",
                source_blockers=[*final_blockers, *runtime_blockers],
                category="operator-action-needed",
            ),
        )

    if targets.get("count") == 0:
        _append_unique(
            steps,
            _step(
                900,
                "deferred-proof-recovery-target-refresh",
                "Deferred proof-recovery target discovery",
                "No RIFT target is visible. This blocks current-PID proof-recovery work but is not itself an MCP release-readiness local code blocker.",
                [_command("refresh unified status after RIFT is started", ["scripts\\riftreader-status.cmd", "--json"])],
                source="riftTargets",
                category="deferred-proof-recovery",
                operator_step=True,
                release_blocker=False,
            ),
        )

    if decision_blockers:
        _append_unique(
            steps,
            _step(
                910,
                "deferred-decision-packet-safe-next",
                "Deferred decision-packet safe diagnostic",
                "The local decision packet reports a proof-recovery blocker. Keep it separate from MCP release readiness unless explicitly working that lane.",
                [_command("decision packet safe next", _as_list(_as_dict(_as_dict(status.get("decisionPacket")).get("safeNextAction")).get("command")))],
                source="decisionPacket",
                source_blockers=decision_blockers,
                category="deferred-proof-recovery",
                release_blocker=False,
            ),
        )

    _append_unique(
        steps,
        _step(
            1000,
            "recheck-final-readiness",
            "Recheck final readiness after recovery",
            "After completing the applicable recovery steps, rerun the authoritative final gate.",
            [_command("final readiness", ["scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"])],
            source="mcpRecoveryPlan",
            category="verification",
            release_blocker=False,
        ),
    )

    return sorted(steps, key=lambda item: int(item.get("priority") or 9999))


def build_plan_from_status(repo_root: Path, status: dict[str, Any]) -> dict[str, Any]:
    final_state = _as_dict(status.get("finalReadiness"))
    blockers = _collect_blockers(status)
    all_blockers = sorted({item for values in blockers.values() for item in values if item})
    steps = build_steps(status)
    release_steps = [step for step in steps if step.get("releaseBlocker")]
    ok = bool(final_state.get("ok")) and not release_steps
    plan_status = "passed" if ok else "blocked"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-recovery-plan",
        "toolVersion": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": plan_status,
        "ok": ok,
        "repoRoot": str(repo_root),
        "sourceStatus": {
            "operatorStatusKind": status.get("kind"),
            "operatorStatusGeneratedAtUtc": status.get("generatedAtUtc"),
            "overallState": status.get("overallState"),
            "git": _as_dict(status.get("git")),
            "finalReadiness": final_state,
            "mcpRuntime": _as_dict(status.get("mcpRuntime")),
        },
        "blockers": all_blockers,
        "releaseBlockerCount": len(release_steps),
        "steps": steps,
        "primaryStep": steps[0] if steps else None,
        "safety": {
            **safety_flags(),
            "readOnlyPlan": True,
            "serverStarted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "proofRecorded": False,
            "gitMutation": False,
            "providerWrites": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        },
    }


def render_md(plan: dict[str, Any]) -> str:
    lines = [
        "# RiftReader MCP Readiness Recovery Plan",
        "",
        f"- Generated UTC: `{plan.get('generatedAtUtc')}`",
        f"- Status: `{plan.get('status')}`",
        f"- OK: `{plan.get('ok')}`",
        f"- Release blocker count: `{plan.get('releaseBlockerCount')}`",
        "",
        "## Ordered steps",
        "",
        "| # | Key | Category | Why | Command |",
        "|---:|---|---|---|---|",
    ]
    for index, step in enumerate(_as_list(plan.get("steps")), start=1):
        if not isinstance(step, dict):
            continue
        commands = _as_list(step.get("commands"))
        first = _as_dict(commands[0]) if commands else {}
        lines.append(
            f"| {index} | `{step.get('key')}` | `{step.get('category')}` | {step.get('why')} | `{' '.join(str(part) for part in _as_list(first.get('args')))}` |"
        )
    lines.extend(["", "## Safety", ""])
    safety = _as_dict(plan.get("safety"))
    for key in sorted(safety):
        lines.append(f"- `{key}`: `{safety[key]}`")
    lines.extend(["", "# END_OF_SCRIPT_MARKER", ""])
    return "\n".join(lines)


def write_artifacts(repo_root: Path, plan: dict[str, Any]) -> dict[str, str | None]:
    output_dir = timestamped_output_dir(repo_root / OUTPUT_ROOT_REL)
    latest_dir = repo_root / OUTPUT_ROOT_REL / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    for directory in (output_dir, latest_dir):
        (directory / "summary.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (directory / "summary.md").write_text(render_md(plan), encoding="utf-8")
    return {
        "summaryJson": repo_rel(repo_root, output_dir / "summary.json"),
        "summaryMarkdown": repo_rel(repo_root, output_dir / "summary.md"),
        "latestJson": repo_rel(repo_root, latest_dir / "summary.json"),
        "latestMarkdown": repo_rel(repo_root, latest_dir / "summary.md"),
    }


def build_recovery_plan(repo_root: Path, *, status_payload: dict[str, Any] | None = None, write: bool = False) -> dict[str, Any]:
    status = status_payload if status_payload is not None else build_operator_status(repo_root, write=False)
    plan = build_plan_from_status(repo_root, status)
    if write:
        plan["artifacts"] = write_artifacts(repo_root, plan)
    return plan


def self_test() -> dict[str, Any]:
    sample_status = {
        "kind": "riftreader-unified-operator-status",
        "generatedAtUtc": "2026-06-29T00:00:00Z",
        "overallState": "blocked",
        "git": {"dirty": False},
        "finalReadiness": {
            "ok": False,
            "status": "blocked",
            "blockers": ["proof:stale", "artifact:trial-readiness-stale", "artifact:proposal-smoke-stale"],
        },
        "mcpRuntime": {"ok": False, "blockers": ["local-mcp-server-listener-query-failed"], "dependencySequence": []},
        "workflowArtifacts": {
            "latest": {
                "trialReadiness": {"status": "stale"},
                "proposalSmoke": {"status": "stale"},
                "actualClientProof": {"status": "stale"},
            }
        },
        "riftTargets": {"count": 0},
        "decisionPacket": {"blockers": ["latest-static-owner-readback-root-pointer-null"], "safeNextAction": {"command": ["scripts\\get-rift-window-targets.cmd", "-Json"]}},
    }
    plan = build_plan_from_status(Path.cwd(), sample_status)
    keys = [step["key"] for step in plan["steps"]]
    checks = [
        {"name": "plan-blocked", "pass": plan["status"] == "blocked"},
        {"name": "trial-step", "pass": "refresh-trial-readiness" in keys},
        {"name": "runtime-step", "pass": "start-full-http-mcp-runtime" in keys},
        {"name": "proof-step", "pass": "refresh-actual-client-proof" in keys},
        {"name": "no-auto-runtime-start", "pass": not next(step for step in plan["steps"] if step["key"] == "start-full-http-mcp-runtime")["autoRunAllowed"]},
    ]
    ok = all(bool(check["pass"]) for check in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-recovery-plan-self-test",
        "toolVersion": VERSION,
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": safety_flags(),
    }


def _load_status_input(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Status input is not a JSON object: {path}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--input-status-json", type=Path, help="Use an existing operator-status JSON packet instead of collecting a fresh one.")
    parser.add_argument("--write", action="store_true", help="Write ignored recovery-plan artifacts under .riftreader-local.")
    parser.add_argument("--summary-md", action="store_true", help="Render Markdown instead of JSON unless --json is also set.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        payload = self_test()
    else:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
        status_payload = _load_status_input(args.input_status_json) if args.input_status_json else None
        payload = build_recovery_plan(repo_root, status_payload=status_payload, write=bool(args.write))
    if args.json or args.self_test:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.summary_md:
        print(render_md(payload), end="")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status") == "passed" else 2 if payload.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())

