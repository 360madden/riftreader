#!/usr/bin/env python3
# Version: riftreader-operator-status-v0.2.0
# Total-Character-Count: 0000018124
# Purpose: Stage 51 unified read-only RiftReader repo/operator status aggregator.

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from .common import find_repo_root, preview_text, repo_rel, safety_flags, timestamped_output_dir, utc_iso
    from .decision_packet import build_decision_packet, compact_decision_packet
    from .mcp_final_readiness import compact_final_readiness, final_readiness
    from .mcp_server_status import build_status_payload as build_mcp_server_status_payload
    from .mcp_workflow_state import FRESHNESS_BUDGET_SECONDS, build_mcp_workflow_state
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, preview_text, repo_rel, safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.decision_packet import build_decision_packet, compact_decision_packet
    from riftreader_workflow.mcp_final_readiness import compact_final_readiness, final_readiness
    from riftreader_workflow.mcp_server_status import build_status_payload as build_mcp_server_status_payload
    from riftreader_workflow.mcp_workflow_state import FRESHNESS_BUDGET_SECONDS, build_mcp_workflow_state


VERSION = "riftreader-operator-status-v0.2.0"
SCHEMA_VERSION = 2
DEFAULT_TARGET_PROCESS = "rift_x64"


def _path(value: str | None) -> str | None:
    return value.replace("/", "\\") if value else None


def _command_summary(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": envelope.get("label"),
        "args": envelope.get("args"),
        "exitCode": envelope.get("exitCode"),
        "ok": envelope.get("ok"),
        "timedOut": envelope.get("timedOut"),
        "stderrPreview": envelope.get("stderrPreview"),
    }


def _run_git(repo_root: Path, args: list[str], expected: set[int] | None = None) -> dict[str, Any]:
    expected = expected or {0}
    command = ["git", *args]
    envelope: dict[str, Any] = {
        "label": f"git {' '.join(args)}",
        "args": command,
        "cwd": str(repo_root),
        "exitCode": None,
        "ok": False,
        "timedOut": False,
        "stdout": "",
        "stderr": "",
        "stdoutPreview": "",
        "stderrPreview": "",
    }
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
        envelope["exitCode"] = completed.returncode
        envelope["ok"] = completed.returncode in expected
        envelope["stdout"] = completed.stdout or ""
        envelope["stderr"] = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        envelope["timedOut"] = True
        envelope["error"] = f"TimeoutExpired:{exc}"
        envelope["stdout"] = exc.stdout if isinstance(exc.stdout, str) else ""
        envelope["stderr"] = exc.stderr if isinstance(exc.stderr, str) else ""
    except FileNotFoundError as exc:
        envelope["error"] = f"FileNotFoundError:{exc}"
    envelope["stdoutPreview"] = preview_text(str(envelope.get("stdout") or ""), max_lines=30, max_chars=4000)
    envelope["stderrPreview"] = preview_text(str(envelope.get("stderr") or ""), max_lines=20, max_chars=2000)
    return envelope


def git_summary(repo_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    commands: list[dict[str, Any]] = []

    def capture(args: list[str], expected: set[int] | None = None) -> dict[str, Any]:
        result = _run_git(repo_root, args, expected)
        commands.append(result)
        return result

    status = capture(["status", "--short", "--branch"])
    head = capture(["rev-parse", "HEAD"])
    head_short = capture(["rev-parse", "--short", "HEAD"])
    subject = capture(["log", "-1", "--pretty=%s"])
    upstream = capture(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], {0, 128})

    status_lines = str(status.get("stdout") or "").splitlines()
    branch_line = status_lines[0] if status_lines else ""
    dirty_entries = [line for line in status_lines[1:] if line.strip()]
    branch: str | None = None
    upstream_name: str | None = None
    if branch_line.startswith("## "):
        branch_expr = branch_line[3:]
        if "..." in branch_expr:
            branch, upstream_name = branch_expr.split("...", 1)
            branch = branch.split(" ", 1)[0]
            upstream_name = upstream_name.split(" ", 1)[0]
        else:
            branch = branch_expr.split(" ", 1)[0]
    if not upstream_name and upstream.get("ok"):
        upstream_name = str(upstream.get("stdout") or "").strip() or None

    ahead: int | None = None
    behind: int | None = None
    if upstream_name:
        distance = capture(["rev-list", "--left-right", "--count", f"{upstream_name}...HEAD"], {0, 128})
        parts = str(distance.get("stdout") or "").split()
        if len(parts) >= 2:
            try:
                behind = int(parts[0])
                ahead = int(parts[1])
            except ValueError:
                pass

    return (
        {
            "status": "passed" if status.get("ok") and head.get("ok") else "failed",
            "branch": branch,
            "upstream": upstream_name,
            "ahead": ahead,
            "behind": behind,
            "dirty": bool(dirty_entries),
            "dirtyCount": len(dirty_entries),
            "dirtyEntries": dirty_entries,
            "head": str(head.get("stdout") or "").strip() or None,
            "headShort": str(head_short.get("stdout") or "").strip() or None,
            "headSubject": str(subject.get("stdout") or "").strip() or None,
            "branchLine": branch_line,
        },
        commands,
    )


def latest_handoff_summary(repo_root: Path) -> dict[str, Any]:
    pointer = repo_root / "docs" / "HANDOFF.md"
    text = pointer.read_text(encoding="utf-8", errors="replace") if pointer.is_file() else ""
    match = re.search(r"`([^`]*docs[\\/]handoffs[\\/][^`]+)`", text)
    handoff_root = repo_root / "docs" / "handoffs"
    handoffs = (
        sorted([p for p in handoff_root.glob("*.md") if p.is_file()], key=lambda p: (p.stat().st_mtime, str(p)), reverse=True)
        if handoff_root.is_dir()
        else []
    )
    newest = handoffs[0] if handoffs else None
    return {
        "status": "passed" if pointer.is_file() or newest else "missing",
        "pointerPath": repo_rel(repo_root, pointer) if pointer.exists() else None,
        "pointerTarget": _path(match.group(1)) if match else None,
        "newestTrackedHandoffPath": repo_rel(repo_root, newest) if newest else None,
        "newestTrackedHandoffMtimeUtc": datetime.fromtimestamp(newest.stat().st_mtime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        if newest
        else None,
        "newestTrackedHandoffBytes": newest.stat().st_size if newest else None,
    }


def compact_artifact(kind: str, item: dict[str, Any] | None) -> dict[str, Any]:
    budget = FRESHNESS_BUDGET_SECONDS.get(kind)
    if not item:
        return {"kind": kind, "status": "missing", "fresh": False, "path": None, "ageSeconds": None, "budgetSeconds": budget, "passed": False}
    age = item.get("artifactAgeSeconds")
    fresh = isinstance(age, int) and isinstance(budget, int) and age <= budget
    status = "fresh" if fresh else "stale" if isinstance(age, int) and isinstance(budget, int) else str(item.get("status") or "unknown")
    return {
        "kind": kind,
        "status": status,
        "fresh": fresh,
        "path": item.get("path"),
        "mtimeUtc": item.get("mtimeUtc"),
        "ageSeconds": age,
        "budgetSeconds": budget,
        "passed": bool(item.get("ok") is True or item.get("status") == "passed"),
        "proofMode": item.get("proofMode"),
        "toolCount": item.get("toolCount"),
    }


def workflow_artifact_summary(repo_root: Path) -> dict[str, Any]:
    state = build_mcp_workflow_state(repo_root)
    latest = state.get("latestArtifacts") if isinstance(state.get("latestArtifacts"), dict) else {}
    return {
        "status": state.get("status"),
        "ok": state.get("ok"),
        "blockers": state.get("blockers") or [],
        "warningCount": len(state.get("warnings") or []),
        "latest": {
            "trialReadiness": compact_artifact("readiness", latest.get("readiness") if isinstance(latest.get("readiness"), dict) else None),
            "proposalSmoke": compact_artifact("proposal-smoke", latest.get("proposal-smoke") if isinstance(latest.get("proposal-smoke"), dict) else None),
            "actualClientProof": compact_artifact("actual-client-proof", latest.get("actual-client-proof") if isinstance(latest.get("actual-client-proof"), dict) else None),
            "proofInputTemplate": compact_artifact("proof-input-template", latest.get("proof-input-template") if isinstance(latest.get("proof-input-template"), dict) else None),
        },
        "recommendedNextAction": state.get("recommendedNextAction"),
    }


def safe_component(label: str, builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        payload = builder()
        return payload if isinstance(payload, dict) else {"status": "failed", "ok": False, "blockers": [f"{label}:non-object-payload"]}
    except Exception as exc:  # noqa: BLE001 - status collection must fail closed per component.
        return {"status": "failed", "ok": False, "blockers": [f"{label}:exception:{type(exc).__name__}:{exc}"], "warnings": []}


def final_readiness_summary(repo_root: Path) -> dict[str, Any]:
    compact = compact_final_readiness(final_readiness(repo_root))
    return {
        "status": compact.get("status"),
        "ok": compact.get("ok"),
        "generatedAtUtc": compact.get("generatedAtUtc"),
        "currentHead": compact.get("currentHead"),
        "ciStatus": compact.get("ciStatus"),
        "phase2Status": compact.get("phase2Status"),
        "proofReplayStatus": compact.get("proofReplayStatus"),
        "proofFreshnessStatus": compact.get("proofFreshnessStatus"),
        "artifactFreshnessStatus": compact.get("artifactFreshnessStatus"),
        "toolSurfaceStatus": compact.get("toolSurfaceStatus"),
        "publicSessionStatus": compact.get("publicSessionStatus"),
        "latestMcpHandoffPath": compact.get("latestMcpHandoffPath"),
        "releaseHandoffPath": compact.get("releaseHandoffPath"),
        "recommendedNextAction": compact.get("recommendedNextAction"),
        "blockers": compact.get("blockers") or [],
        "warningCount": compact.get("warningCount"),
    }


def mcp_runtime_summary(repo_root: Path) -> dict[str, Any]:
    payload = build_mcp_server_status_payload(repo_root)
    selected = payload.get("selectedListener") if isinstance(payload.get("selectedListener"), dict) else None
    stdio = payload.get("stdioCounterparts") if isinstance(payload.get("stdioCounterparts"), dict) else {}
    processes = stdio.get("processes") if isinstance(stdio.get("processes"), list) else []
    return {
        "status": payload.get("status"),
        "ok": payload.get("ok"),
        "localMcpUrl": payload.get("localMcpUrl"),
        "host": payload.get("host"),
        "port": payload.get("port"),
        "listenerCount": len(payload.get("listeners") or []),
        "selectedListener": {
            "processId": selected.get("processId") or selected.get("owningProcess"),
            "processName": selected.get("processName"),
            "classification": selected.get("classification"),
        }
        if selected
        else None,
        "runtimeSurface": payload.get("runtimeSurface"),
        "runtimeSourceFreshness": payload.get("runtimeSourceFreshness"),
        "stdioCounterparts": {
            "status": stdio.get("status"),
            "ok": stdio.get("ok"),
            "count": stdio.get("count"),
            "processIds": [item.get("processId") for item in processes if isinstance(item, dict)],
            "staleProcessIds": stdio.get("staleProcessIds") or [],
            "warnings": stdio.get("warnings") or [],
        },
        "dependencySequence": payload.get("dependencySequence") or [],
        "blockers": payload.get("blockers") or [],
        "warnings": payload.get("warnings") or [],
    }


def _process_name_matches(value: str | None, target_process: str) -> bool:
    if not value:
        return False
    return value.lower().removesuffix(".exe") == target_process.lower().removesuffix(".exe")


def discover_rift_targets(target_process: str = DEFAULT_TARGET_PROCESS) -> dict[str, Any]:
    warnings: list[str] = []
    windows: list[dict[str, Any]] = []
    pids: set[int] = set()
    try:
        import psutil  # type: ignore[import-not-found]

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if _process_name_matches(str(proc.info.get("name")), target_process):
                    pids.add(int(proc.info["pid"]))
            except Exception:  # noqa: BLE001 - process can exit during enumeration.
                continue
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"psutil-unavailable:{type(exc).__name__}:{exc}")
    try:
        import win32gui  # type: ignore[import-not-found]
        import win32process  # type: ignore[import-not-found]

        def callback(hwnd: int, _extra: object) -> None:
            try:
                _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
                if int(pid) not in pids:
                    return
                windows.append(
                    {
                        "pid": int(pid),
                        "hwnd": f"0x{int(hwnd):X}",
                        "title": str(win32gui.GetWindowText(hwnd) or ""),
                        "visible": bool(win32gui.IsWindowVisible(hwnd)),
                        "minimized": bool(win32gui.IsIconic(hwnd)),
                        "rect": [int(v) for v in win32gui.GetWindowRect(hwnd)],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"window-enumeration-item-failed:{type(exc).__name__}:{exc}")

        win32gui.EnumWindows(callback, None)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"win32-window-enumeration-unavailable:{type(exc).__name__}:{exc}")
    windows.sort(key=lambda item: (not bool(item.get("visible")), bool(item.get("minimized")), item.get("rect") or [], item.get("hwnd") or ""))
    return {
        "status": "passed",
        "ok": True,
        "processName": target_process,
        "processCount": len(pids),
        "windowCount": len(windows),
        "count": len(windows),
        "windows": windows,
        "warnings": sorted(set(warnings)),
        "safety": {**safety_flags(), "readOnlyTargetDiscovery": True, "focusChanged": False, "targetMemoryBytesRead": False, "targetMemoryBytesWritten": False},
    }


def decision_packet_summary(repo_root: Path) -> dict[str, Any]:
    compact = compact_decision_packet(build_decision_packet(repo_root, run_safe_checks=False, use_cache=False, include_nav_state=False))
    return {
        "status": compact.get("status"),
        "lane": compact.get("lane"),
        "risk": compact.get("risk"),
        "targetEpoch": compact.get("targetEpoch"),
        "safeNextAction": compact.get("safeNextAction"),
        "milestoneStatus": compact.get("milestoneStatus"),
        "commitPlan": compact.get("commitPlan"),
        "blockers": compact.get("blockers") or [],
        "warnings": compact.get("warnings") or [],
    }


def action(key: str, why: str, command: list[str] | None, *, source: str, operator_step: bool = False) -> dict[str, Any]:
    return {"key": key, "why": why, "command": command or [], "source": source, "safe": True, "operatorStep": operator_step}


def select_recommended_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    final_state = payload.get("finalReadiness") if isinstance(payload.get("finalReadiness"), dict) else {}
    final_action = final_state.get("recommendedNextAction") if isinstance(final_state.get("recommendedNextAction"), dict) else None
    if final_action:
        actions.append(
            action(
                str(final_action.get("key") or "final-readiness-next-action"),
                str(final_action.get("reason") or "Final readiness reported this recovery action."),
                [str(part) for part in (final_action.get("command") or [])],
                source="finalReadiness",
            )
        )
    runtime = payload.get("mcpRuntime") if isinstance(payload.get("mcpRuntime"), dict) else {}
    if not runtime.get("ok"):
        actions.append(
            action(
                "start-full-http-mcp-runtime",
                "The local ChatGPT MCP HTTP runtime is not ready; start the repo launcher before actual-client/public-route proof.",
                ["START_RIFTREADER_CHATGPT_MCP.cmd", "serve"],
                source="mcpRuntime",
                operator_step=True,
            )
        )
    decision = payload.get("decisionPacket") if isinstance(payload.get("decisionPacket"), dict) else {}
    safe_next = decision.get("safeNextAction") if isinstance(decision.get("safeNextAction"), dict) else None
    if safe_next:
        actions.append(
            action(
                str(safe_next.get("key") or "decision-packet-safe-next-action"),
                str(safe_next.get("why") or "Decision packet reported this safe next action."),
                [str(part) for part in (safe_next.get("command") or [])],
                source="decisionPacket",
            )
        )
    targets = payload.get("riftTargets") if isinstance(payload.get("riftTargets"), dict) else {}
    if targets.get("count") == 0:
        actions.append(
            action(
                "manual-start-rift-then-refresh-status",
                "No RIFT window target is visible; current-PID proof recovery must wait for an operator-started RIFT client.",
                ["scripts\\riftreader-status.cmd", "--json"],
                source="riftTargets",
                operator_step=True,
            )
        )
    actions.append(
        action(
            "refresh-unified-operator-status",
            "Rerun the unified status command after any recovery step.",
            ["scripts\\riftreader-status.cmd", "--json"],
            source="operatorStatus",
        )
    )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in actions:
        key = str(item.get("key"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _legacy_board(decision: dict[str, Any], primary: dict[str, Any] | None) -> dict[str, Any]:
    safe_next = decision.get("safeNextAction") if isinstance(decision.get("safeNextAction"), dict) else {}
    milestone = decision.get("milestoneStatus") if isinstance(decision.get("milestoneStatus"), dict) else {}
    return {
        "currentLane": decision.get("lane"),
        "now": decision.get("status"),
        "next": (primary or {}).get("key") or safe_next.get("key"),
        "later": "refresh-unified-operator-status",
        "blockedBy": ", ".join(str(item) for item in (decision.get("blockers") or [])),
        "milestoneState": milestone.get("state"),
    }


def _legacy_classifier(decision: dict[str, Any], primary: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "classification": decision.get("lane"),
        "confidence": "status-derived",
        "reason": (primary or {}).get("why"),
        "blocker": ", ".join(str(item) for item in (decision.get("blockers") or [])),
        "nextRecommendedAction": (primary or {}).get("key"),
        "nextRecommendedCommand": " ".join(str(part) for part in ((primary or {}).get("command") or [])),
        "doNotDo": [
            "Do not treat Codex stdio MCP health as proof of the public HTTP runtime.",
            "Do not send live RIFT input, attach debuggers, promote proof, or mutate provider repos from status collection.",
        ],
    }


def render_md(summary: dict[str, Any]) -> str:
    git = summary.get("git") if isinstance(summary.get("git"), dict) else {}
    handoff = summary.get("handoff") if isinstance(summary.get("handoff"), dict) else {}
    runtime = summary.get("mcpRuntime") if isinstance(summary.get("mcpRuntime"), dict) else {}
    final_state = summary.get("finalReadiness") if isinstance(summary.get("finalReadiness"), dict) else {}
    artifacts = summary.get("workflowArtifacts") if isinstance(summary.get("workflowArtifacts"), dict) else {}
    latest = artifacts.get("latest") if isinstance(artifacts.get("latest"), dict) else {}
    targets = summary.get("riftTargets") if isinstance(summary.get("riftTargets"), dict) else {}
    decision = summary.get("decisionPacket") if isinstance(summary.get("decisionPacket"), dict) else {}
    primary = summary.get("recommendedNextAction") if isinstance(summary.get("recommendedNextAction"), dict) else {}

    def artifact_cell(name: str) -> str:
        item = latest.get(name) if isinstance(latest.get(name), dict) else {}
        return f"`{item.get('status')}` age=`{item.get('ageSeconds')}` path=`{item.get('path') or ''}`"

    lines = [
        "# RiftReader Unified Operator Status",
        "",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Collection status: `{summary.get('status')}`",
        f"- Overall state: `{summary.get('overallState')}`",
        "",
        "## Current State",
        "",
        "| Area | Value |",
        "|---|---|",
        f"| Git | branch=`{git.get('branch')}` upstream=`{git.get('upstream')}` ahead=`{git.get('ahead')}` behind=`{git.get('behind')}` dirty=`{git.get('dirty')}` HEAD=`{git.get('headShort')}` |",
        f"| Handoff | pointer=`{handoff.get('pointerTarget')}` newest=`{handoff.get('newestTrackedHandoffPath')}` |",
        f"| MCP runtime | status=`{runtime.get('status')}` ok=`{runtime.get('ok')}` url=`{runtime.get('localMcpUrl')}` listeners=`{runtime.get('listenerCount')}` stdio=`{(runtime.get('stdioCounterparts') or {}).get('count')}` |",
        f"| Final readiness | status=`{final_state.get('status')}` ok=`{final_state.get('ok')}` blockers=`{len(final_state.get('blockers') or [])}` warnings=`{final_state.get('warningCount')}` |",
        f"| Trial readiness | {artifact_cell('trialReadiness')} |",
        f"| Proposal smoke | {artifact_cell('proposalSmoke')} |",
        f"| Actual-client proof | {artifact_cell('actualClientProof')} |",
        f"| RIFT target | processCount=`{targets.get('processCount')}` windowCount=`{targets.get('windowCount')}` |",
        f"| Decision packet | status=`{decision.get('status')}` lane=`{decision.get('lane')}` risk=`{decision.get('risk')}` |",
        "",
        "## Primary Next Action",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Key | `{primary.get('key')}` |",
        f"| Source | `{primary.get('source')}` |",
        f"| Why | {primary.get('why') or ''} |",
        f"| Command | `{' '.join(primary.get('command') or [])}` |",
        "",
        "## Safety",
        "",
        "| Flag | Value |",
        "|---|---|",
    ]
    for key, value in sorted((summary.get("safety") or {}).items()):
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## END_OF_SCRIPT_MARKER", ""])
    return "\n".join(lines)


def write_artifacts(repo_root: Path, summary: dict[str, Any]) -> dict[str, str | None]:
    root = repo_root / ".riftreader-local" / "operator-status"
    out = timestamped_output_dir(root)
    latest = root / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    for directory in (out, latest):
        (directory / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (directory / "summary.md").write_text(render_md(summary), encoding="utf-8")
    return {
        "summaryJson": repo_rel(repo_root, out / "summary.json"),
        "summaryMarkdown": repo_rel(repo_root, out / "summary.md"),
        "latestJson": repo_rel(repo_root, latest / "summary.json"),
        "latestMarkdown": repo_rel(repo_root, latest / "summary.md"),
    }


def build(repo_root: Path, timeout: int = 180, write: bool = False) -> dict[str, Any]:
    del timeout  # Component helpers own their bounded read-only timeouts.
    git, git_commands = git_summary(repo_root)
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-unified-operator-status",
        "toolVersion": VERSION,
        "generatedAtUtc": utc_iso(),
        "repoRoot": str(repo_root),
        "status": "passed",
        "ok": True,
        "git": git,
        "handoff": latest_handoff_summary(repo_root),
        "workflowArtifacts": safe_component("workflow-artifacts", lambda: workflow_artifact_summary(repo_root)),
        "mcpRuntime": safe_component("mcp-runtime", lambda: mcp_runtime_summary(repo_root)),
        "finalReadiness": safe_component("final-readiness", lambda: final_readiness_summary(repo_root)),
        "riftTargets": safe_component("rift-targets", discover_rift_targets),
        "decisionPacket": safe_component("decision-packet", lambda: decision_packet_summary(repo_root)),
        "commands": [_command_summary(cmd) for cmd in git_commands],
        "safety": {
            **safety_flags(),
            "readOnlyStatus": True,
            "serverStarted": False,
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "proofPromotion": False,
            "currentTruthWritten": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "focusChanged": False,
        },
    }
    component_failures = [
        name
        for name in ("workflowArtifacts", "mcpRuntime", "finalReadiness", "riftTargets", "decisionPacket")
        if (summary.get(name) or {}).get("status") == "failed"
    ]
    if component_failures:
        summary["status"] = "degraded"
        summary["collectionWarnings"] = [f"component-failed:{name}" for name in component_failures]
    final_ok = bool((summary.get("finalReadiness") or {}).get("ok"))
    runtime_ok = bool((summary.get("mcpRuntime") or {}).get("ok"))
    dirty = bool((summary.get("git") or {}).get("dirty"))
    summary["overallState"] = "ready" if final_ok and runtime_ok and not dirty else "blocked"
    actions = select_recommended_actions(summary)
    summary["recommendedActions"] = actions
    summary["recommendedNextAction"] = actions[0] if actions else None
    decision = summary.get("decisionPacket") if isinstance(summary.get("decisionPacket"), dict) else {}
    summary["board"] = _legacy_board(decision, summary["recommendedNextAction"])
    summary["classifier"] = _legacy_classifier(decision, summary["recommendedNextAction"])
    summary["compactStatus"] = {
        "status": summary["overallState"],
        "blockers": (summary.get("finalReadiness") or {}).get("blockers") or (summary.get("decisionPacket") or {}).get("blockers") or [],
        "git": summary.get("git"),
    }
    if write:
        summary["artifacts"] = write_artifacts(repo_root, summary)
    return summary


def self_test() -> dict[str, Any]:
    sample = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-unified-operator-status",
        "generatedAtUtc": "2026-06-29T00:00:00Z",
        "status": "passed",
        "overallState": "blocked",
        "git": {"branch": "main", "upstream": "origin/main", "ahead": 0, "behind": 0, "dirty": False, "headShort": "abc1234"},
        "handoff": {"pointerTarget": "docs\\handoffs\\latest.md", "newestTrackedHandoffPath": "docs\\handoffs\\latest.md"},
        "mcpRuntime": {"status": "blocked-query-failed", "ok": False, "localMcpUrl": "http://127.0.0.1:8770/mcp", "listenerCount": 0, "stdioCounterparts": {"count": 1}},
        "finalReadiness": {"status": "blocked", "ok": False, "blockers": ["proof:stale"], "warningCount": 1},
        "workflowArtifacts": {"latest": {"trialReadiness": {"status": "stale", "ageSeconds": 10, "path": "x"}, "proposalSmoke": {"status": "fresh", "ageSeconds": 1, "path": "y"}, "actualClientProof": {"status": "stale", "ageSeconds": 20, "path": "z"}}},
        "riftTargets": {"processCount": 0, "windowCount": 0, "count": 0},
        "decisionPacket": {"status": "blocked", "lane": "proof-recovery", "risk": "high"},
        "recommendedNextAction": {"key": "start-full-http-mcp-runtime", "source": "mcpRuntime", "why": "start", "command": ["START_RIFTREADER_CHATGPT_MCP.cmd", "serve"]},
        "safety": safety_flags(),
    }
    rendered = render_md(sample)
    checks = [
        {"name": "markdown-title", "pass": "Unified Operator Status" in rendered},
        {"name": "git-row", "pass": "origin/main" in rendered},
        {"name": "runtime-row", "pass": "127.0.0.1:8770" in rendered},
        {"name": "next-action-row", "pass": "start-full-http-mcp-runtime" in rendered},
        {"name": "missing-artifact-status", "pass": compact_artifact("actual-client-proof", None)["status"] == "missing"},
    ]
    ok = all(bool(check["pass"]) for check in checks)
    return {"schemaVersion": SCHEMA_VERSION, "kind": "riftreader-operator-status-self-test", "toolVersion": VERSION, "status": "passed" if ok else "failed", "ok": ok, "checks": checks, "safety": safety_flags()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a unified read-only RiftReader repo/operator status packet.")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--write", action="store_true", help="Write ignored summary artifacts under .riftreader-local/operator-status.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        payload = self_test()
    else:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
        payload = build(repo_root, timeout=max(30, int(args.timeout_seconds)), write=bool(args.write))
    if args.json or args.self_test:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_md(payload), end="")
    return 0 if payload.get("status") in {"passed", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
