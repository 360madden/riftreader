#!/usr/bin/env python3
"""Offline-safe RiftReader Operator Lite.

This helper is a small local launcher around already-safe workflow commands.
It intentionally does not include movement, live input, ProofOnly, target
control, visual gates, CE, x64dbg, staging, committing, or pushing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, utc_iso


DENIED_FRAGMENTS = (
    "send-rift-key",
    "post-rift-key",
    "cheatengine",
    "x64dbg",
    "git add",
    "git commit",
    "git push",
    "git reset",
    "git clean",
    "--serve",
    "cloudflared",
    "tunnel ",
    "proofonly",
    "target-control",
    "visual-gate",
)

HELP_ALIASES = {"/help", "/?", "help"}
COMMAND_ALIASES = {
    "session-start": "bridge-session-start",
    "bridge-start": "bridge-session-start",
    "preflight": "bridge-preflight",
    "bridge-preflight-check": "bridge-preflight",
    "latest-inbox": "bridge-inbox-latest",
    "inbox-latest": "bridge-inbox-latest",
    "package-draft": "bridge-inbox-package-draft",
    "inbox-package-draft": "bridge-inbox-package-draft",
    "draft-package": "bridge-inbox-package-draft",
    "package-draft-index": "package-draft-index",
    "draft-index": "package-draft-index",
    "package-drafts": "package-draft-index",
    "latest-package-draft": "package-draft-latest",
    "package-draft-latest": "package-draft-latest",
    "review-package-draft": "package-draft-latest",
    "latest-operator-draft": "package-draft-latest-operator",
    "latest-operator-package-draft": "package-draft-latest-operator",
    "operator-package-draft": "package-draft-latest-operator",
    "package-draft-dry-run": "package-draft-dry-run-latest",
    "dry-run-package-draft": "package-draft-dry-run-latest",
    "dry-run-latest-draft": "package-draft-dry-run-latest",
    "operator-draft-dry-run": "package-draft-dry-run-latest-operator",
    "dry-run-operator-draft": "package-draft-dry-run-latest-operator",
    "dry-run-latest-operator-draft": "package-draft-dry-run-latest-operator",
    "package-draft-selftest": "package-draft-loop-selftest",
    "package-draft-self-test": "package-draft-loop-selftest",
    "draft-loop-selftest": "package-draft-loop-selftest",
    "proposal-loop-selftest": "package-draft-loop-selftest",
    "mcp-trial": "mcp-trial-readiness",
    "mcp-trial-readiness": "mcp-trial-readiness",
    "chatgpt-mcp-trial": "mcp-trial-readiness",
    "chatgpt-mcp-trial-readiness": "mcp-trial-readiness",
    "mcp-mission": "mcp-mission-control",
    "mcp-mission-control": "mcp-mission-control",
    "mcp-artifacts": "mcp-artifacts-latest",
    "latest-mcp-artifacts": "mcp-artifacts-latest",
    "chatgpt-trial-proof": "chatgpt-trial-proof-template",
    "chatgpt-trial-proof-template": "chatgpt-trial-proof-template",
    "safe-commit-plan": "safe-commit-plan",
    "workflow-router": "workflow-router-mcp",
    "mcp-router": "workflow-router-mcp",
    "decision-packet": "decision-packet",
    "refresh-decision-packet": "decision-packet",
    "local-decision-packet": "decision-packet",
    "decision-packet-schema": "decision-packet-schema",
    "local-decision-packet-schema": "decision-packet-schema",
    "decision-packet-agent-plan": "decision-packet-agent-plan",
    "agent-plan": "decision-packet-agent-plan",
    "local-agent-plan": "decision-packet-agent-plan",
}
GROUP_ALIASES = {
    "startup": "bridge-startup-checks",
    "bridge-checks": "bridge-startup-checks",
    "chatgpt-startup": "bridge-startup-checks",
    "proposal-loop": "bridge-proposal-loop-checks",
    "bridge-proposal-loop": "bridge-proposal-loop-checks",
    "package-proposal-loop": "bridge-proposal-loop-checks",
    "chatgpt-proposal-loop": "bridge-proposal-loop-checks",
    "trial-readiness": "bridge-trial-readiness",
    "bridge-trial": "bridge-trial-readiness",
    "desktop-chatgpt-trial": "bridge-trial-readiness",
    "chatgpt-trial-readiness": "bridge-trial-readiness",
}

GUI_PALETTE = {
    "background": "#0f172a",
    "panel": "#111827",
    "panel_alt": "#1f2937",
    "text": "#f8fafc",
    "muted": "#cbd5e1",
    "output_bg": "#020617",
    "output_fg": "#e5e7eb",
    "status_bg": "#0b1220",
    "status_fg": "#93c5fd",
    "truth_bg": "#132033",
    "truth_border": "#2563eb",
    "truth_fg": "#bfdbfe",
    "truth_accent": "#4dd4ac",
    "primary": "#2563eb",
    "primary_active": "#1d4ed8",
    "success": "#15803d",
    "success_active": "#166534",
    "warning": "#b45309",
    "warning_active": "#92400e",
    "bridge": "#6d28d9",
    "bridge_active": "#5b21b6",
    "neutral": "#475569",
    "neutral_active": "#334155",
    "disabled_bg": "#3f1f2f",
    "disabled_fg": "#fca5a5",
}

BUTTON_VARIANTS = {
    "primary": ("primary", "primary_active"),
    "success": ("success", "success_active"),
    "warning": ("warning", "warning_active"),
    "bridge": ("bridge", "bridge_active"),
    "neutral": ("neutral", "neutral_active"),
}


@dataclass(frozen=True)
class CommandSpec:
    key: str
    label: str
    args: tuple[str, ...]
    timeout_seconds: float
    description: str
    expected_exit_codes: tuple[int, ...] = (0,)


@dataclass(frozen=True)
class CommandGroupSpec:
    key: str
    label: str
    command_keys: tuple[str, ...]
    description: str


def build_command_specs(repo_root: Path) -> dict[str, CommandSpec]:
    scripts = repo_root / "scripts"
    return {
        "workflow-status": CommandSpec(
            key="workflow-status",
            label="Refresh Workflow Status",
            args=(str(scripts / "riftreader-workflow-status.cmd"), "--write"),
            timeout_seconds=90,
            description="Build a deterministic status packet under .riftreader-local.",
            expected_exit_codes=(0, 2),
        ),
        "decision-packet": CommandSpec(
            key="decision-packet",
            label="Refresh Decision Packet",
            args=(str(scripts / "riftreader-decision-packet.cmd"), "--write", "--compact-json"),
            timeout_seconds=120,
            description="Build the local decision packet with LLM reminders, safe next action, validation plan, and blockers.",
            expected_exit_codes=(0, 2),
        ),
        "decision-packet-schema": CommandSpec(
            key="decision-packet-schema",
            label="Decision Packet Schema Contract",
            args=(str(scripts / "riftreader-decision-packet.cmd"), "--schema-json"),
            timeout_seconds=30,
            description="Print the static decision-packet schema contract without building a repo packet or writing artifacts.",
        ),
        "decision-packet-agent-plan": CommandSpec(
            key="decision-packet-agent-plan",
            label="Decision Packet Agent Plan",
            args=(str(scripts / "riftreader-decision-packet.cmd"), "--agent-plan"),
            timeout_seconds=60,
            description="Print parallel-agent-safe work slices with LLM reminders; read-only and artifact-free.",
            expected_exit_codes=(0, 2),
        ),
        "compact-sitrep": CommandSpec(
            key="compact-sitrep",
            label="Compact ChatGPT SITREP",
            args=(str(scripts / "riftreader-workflow-status.cmd"), "--compact", "--write"),
            timeout_seconds=90,
            description="Print and write a compact paste-ready local ChatGPT/non-Codex SITREP.",
            expected_exit_codes=(0, 2),
        ),
        "live-triage": CommandSpec(
            key="live-triage",
            label="Run Live-Test Triage",
            args=(str(scripts / "riftreader-live-triage.cmd"), "--write"),
            timeout_seconds=90,
            description="Classify the current blocker without live input.",
            expected_exit_codes=(0, 2),
        ),
        "package-selftest": CommandSpec(
            key="package-selftest",
            label="Package Intake Self-Test",
            args=(str(scripts / "riftreader-package-intake-selftest.cmd"),),
            timeout_seconds=120,
            description="Smoke-test package intake with a generated dry-run package.",
        ),
        "bridge-selftest": CommandSpec(
            key="bridge-selftest",
            label="Bridge Self-Test",
            args=(str(scripts / "riftreader-local-artifact-bridge.cmd"), "--self-test", "--json"),
            timeout_seconds=120,
            description="Run bridge read/inbox/package-proposal loop self-test without starting a persistent server.",
        ),
        "bridge-preflight": CommandSpec(
            key="bridge-preflight",
            label="Bridge Preflight",
            args=(
                str(scripts / "riftreader-local-artifact-bridge.cmd"),
                "--preflight",
                "--payload-root",
                "artifacts\\chatgpt-payloads",
                "--json",
            ),
            timeout_seconds=60,
            description="Check bridge payload readiness without starting a persistent server or tunnel.",
            expected_exit_codes=(0, 2),
        ),
        "bridge-handoff": CommandSpec(
            key="bridge-handoff",
            label="Bridge ChatGPT Handoff",
            args=(
                str(scripts / "riftreader-local-artifact-bridge.cmd"),
                "--chatgpt-handoff",
                "--payload-root",
                "artifacts\\chatgpt-payloads",
                "--json",
            ),
            timeout_seconds=60,
            description="Print the redacted Desktop ChatGPT handoff packet with read order, inbox schema, and safety rules.",
        ),
        "bridge-session-start": CommandSpec(
            key="bridge-session-start",
            label="Bridge Session Start",
            args=(
                str(scripts / "riftreader-local-artifact-bridge.cmd"),
                "--session-start",
                "--payload-root",
                "artifacts\\chatgpt-payloads",
                "--json",
            ),
            timeout_seconds=60,
            description="Print one redacted Desktop ChatGPT session-start packet with preflight, inbox, commands, and next steps.",
            expected_exit_codes=(0, 2),
        ),
        "bridge-bootstrap-payload": CommandSpec(
            key="bridge-bootstrap-payload",
            label="Bridge Bootstrap Payload",
            args=(
                str(scripts / "riftreader-local-artifact-bridge.cmd"),
                "--bootstrap-payload",
                "--payload-root",
                "artifacts\\chatgpt-payloads",
                "--json",
            ),
            timeout_seconds=60,
            description="Create a safe Desktop ChatGPT starter payload from fixed repo-owned docs.",
        ),
        "bridge-index": CommandSpec(
            key="bridge-index",
            label="Bridge Payload Index",
            args=(
                str(scripts / "riftreader-local-artifact-bridge.cmd"),
                "--index",
                "--payload-root",
                "artifacts\\chatgpt-payloads",
                "--json",
            ),
            timeout_seconds=60,
            description="Read the curated bridge payload index without serving HTTP or managing tunnels.",
        ),
        "bridge-inbox-index": CommandSpec(
            key="bridge-inbox-index",
            label="Bridge Inbox Index",
            args=(
                str(scripts / "riftreader-local-artifact-bridge.cmd"),
                "--inbox-index",
                "--json",
            ),
            timeout_seconds=60,
            description="Read guarded Local Inbox v0 proposals stored under .riftreader-local without applying them.",
        ),
        "bridge-inbox-latest": CommandSpec(
            key="bridge-inbox-latest",
            label="Bridge Latest Inbox",
            args=(
                str(scripts / "riftreader-local-artifact-bridge.cmd"),
                "--inbox-read-latest",
                "--json",
            ),
            timeout_seconds=60,
            description="Read the latest guarded Local Inbox v0 proposal without applying it.",
            expected_exit_codes=(0, 2),
        ),
        "bridge-inbox-package-draft": CommandSpec(
            key="bridge-inbox-package-draft",
            label="Bridge Package Draft",
            args=(
                str(scripts / "riftreader-local-artifact-bridge.cmd"),
                "--inbox-package-draft",
                "--json",
            ),
            timeout_seconds=60,
            description="Export the latest package-proposal inbox item into an inert local package draft under .riftreader-local.",
            expected_exit_codes=(0, 2),
        ),
        "package-draft-latest": CommandSpec(
            key="package-draft-latest",
            label="Latest Package Draft",
            args=(
                str(scripts / "riftreader-package-draft-review.cmd"),
                "--latest",
                "--json",
            ),
            timeout_seconds=60,
            description="Print the newest inert Local Artifact Bridge package draft summary without applying it.",
            expected_exit_codes=(0, 2),
        ),
        "package-draft-index": CommandSpec(
            key="package-draft-index",
            label="Package Draft Index",
            args=(
                str(scripts / "riftreader-package-draft-review.cmd"),
                "--index",
                "--json",
            ),
            timeout_seconds=60,
            description="List inert Local Artifact Bridge package drafts without applying or dry-running them.",
            expected_exit_codes=(0, 2),
        ),
        "package-draft-latest-operator": CommandSpec(
            key="package-draft-latest-operator",
            label="Latest Operator Draft",
            args=(
                str(scripts / "riftreader-package-draft-review.cmd"),
                "--latest-operator",
                "--json",
            ),
            timeout_seconds=60,
            description="Print the newest non-self-test operator package draft summary without applying it.",
            expected_exit_codes=(0, 2),
        ),
        "package-draft-dry-run-latest": CommandSpec(
            key="package-draft-dry-run-latest",
            label="Dry-Run Latest Draft",
            args=(
                str(scripts / "riftreader-package-draft-review.cmd"),
                "--dry-run-latest",
                "--json",
            ),
            timeout_seconds=180,
            description="Explicitly run package intake dry-run for the newest package draft; never passes --apply.",
            expected_exit_codes=(0, 2),
        ),
        "package-draft-dry-run-latest-operator": CommandSpec(
            key="package-draft-dry-run-latest-operator",
            label="Dry-Run Operator Draft",
            args=(
                str(scripts / "riftreader-package-draft-review.cmd"),
                "--dry-run-latest-operator",
                "--json",
            ),
            timeout_seconds=180,
            description="Explicitly run package intake dry-run for the newest operator draft; never passes --apply.",
            expected_exit_codes=(0, 2),
        ),
        "package-draft-loop-selftest": CommandSpec(
            key="package-draft-loop-selftest",
            label="Draft Loop Self-Test",
            args=(
                str(scripts / "riftreader-package-draft-review.cmd"),
                "--self-test",
                "--json",
            ),
            timeout_seconds=180,
            description="Run package-proposal -> inbox -> inert draft -> dry-run self-test with ignored local artifacts only.",
        ),
        "mcp-trial-readiness": CommandSpec(
            key="mcp-trial-readiness",
            label="MCP Trial Readiness",
            args=(
                str(scripts / "riftreader-chatgpt-mcp.cmd"),
                "--trial-readiness",
                "--json",
            ),
            timeout_seconds=120,
            description=(
                "Run compact local ChatGPT MCP trial-readiness checks without public tunnel, ChatGPT registration, "
                "persistent serving, package apply, Git mutation, live RIFT input, CE, or x64dbg."
            ),
            expected_exit_codes=(0, 2),
        ),
        "mcp-mission-control": CommandSpec(
            key="mcp-mission-control",
            label="MCP Mission Control",
            args=(str(scripts / "riftreader-mcp-mission-control.cmd"), "--json"),
            timeout_seconds=60,
            description="Show MCP readiness, artifacts, dirty state, and next action without starting tunnels or mutating Git.",
        ),
        "mcp-artifacts-latest": CommandSpec(
            key="mcp-artifacts-latest",
            label="Latest MCP Artifacts",
            args=(str(scripts / "riftreader-mcp-artifacts.cmd"), "--latest", "--json"),
            timeout_seconds=60,
            description="Show latest MCP readiness/smoke/trial/inbox/draft/dry-run artifacts without modifying state.",
        ),
        "chatgpt-trial-proof-template": CommandSpec(
            key="chatgpt-trial-proof-template",
            label="ChatGPT Trial Proof Template",
            args=(str(scripts / "riftreader-chatgpt-trial-recorder.cmd"), "--write-template", "--json"),
            timeout_seconds=60,
            description="Write a fillable actual ChatGPT client proof template; does not call ChatGPT or start a tunnel.",
        ),
        "safe-commit-plan": CommandSpec(
            key="safe-commit-plan",
            label="Safe Commit Plan",
            args=(str(scripts / "riftreader-safe-commit-packager.cmd"), "--plan", "--json"),
            timeout_seconds=60,
            description="Generate explicit-path staging checklist and commit message draft without staging, committing, or pushing.",
        ),
        "workflow-router-mcp": CommandSpec(
            key="workflow-router-mcp",
            label="Workflow Router",
            args=(str(scripts / "riftreader-workflow-router.cmd"), "--mcp", "--json"),
            timeout_seconds=60,
            description="Recommend the next safest MCP workflow action from current local artifacts and Git state.",
        ),
        "git-status": CommandSpec(
            key="git-status",
            label="Git Status",
            args=("git", "--no-pager", "status", "--short", "--branch"),
            timeout_seconds=30,
            description="Show local branch and dirty-file state.",
        ),
    }


def build_command_groups() -> dict[str, CommandGroupSpec]:
    return {
        "bridge-startup-checks": CommandGroupSpec(
            key="bridge-startup-checks",
            label="Bridge Startup Checks",
            command_keys=("bridge-selftest", "bridge-preflight", "bridge-session-start"),
            description="Run bridge self-test, preflight, and Desktop ChatGPT session-start without serving or tunneling.",
        ),
        "bridge-proposal-loop-checks": CommandGroupSpec(
            key="bridge-proposal-loop-checks",
            label="Bridge Proposal Loop Checks",
            command_keys=("bridge-selftest", "package-draft-loop-selftest"),
            description=(
                "Run HTTP package-proposal to draft self-test plus local draft to package-intake dry-run self-test."
            ),
        ),
        "bridge-trial-readiness": CommandGroupSpec(
            key="bridge-trial-readiness",
            label="Desktop ChatGPT Trial Readiness",
            command_keys=(
                "bridge-selftest",
                "bridge-preflight",
                "bridge-session-start",
                "bridge-inbox-index",
                "package-draft-index",
                "package-draft-latest-operator",
            ),
            description=(
                "Run the safe bridge trial gate without serving, tunneling, exporting drafts, dry-running intake, "
                "applying packages, or mutating Git."
            ),
        ),
    }


def package_intake_dry_run_args(repo_root: Path, package_path: Path) -> tuple[str, ...]:
    return (
        str(repo_root / "scripts" / "riftreader-package-intake.cmd"),
        "--package",
        str(package_path),
        "--compact-json",
    )


def validate_safe_args(args: tuple[str, ...] | list[str]) -> list[str]:
    joined = " ".join(args).lower()
    return [fragment for fragment in DENIED_FRAGMENTS if fragment in joined]


def run_command(
    args: tuple[str, ...] | list[str],
    cwd: Path,
    timeout_seconds: float,
    expected_exit_codes: tuple[int, ...] = (0,),
) -> dict[str, Any]:
    started = utc_iso()
    start = time.monotonic()
    result: dict[str, Any] = {
        "args": list(args),
        "cwd": str(cwd),
        "startedAtUtc": started,
        "timeoutSeconds": timeout_seconds,
        "expectedExitCodes": list(expected_exit_codes),
        "exitCode": None,
        "ok": False,
        "stdout": "",
        "stderr": "",
    }
    denied = validate_safe_args(args)
    if denied:
        result["stderr"] = f"operator-lite-denied-command-fragment:{','.join(denied)}"
        result["exitCode"] = 2
        return result
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        result["exitCode"] = completed.returncode
        result["ok"] = completed.returncode in expected_exit_codes
        result["stdout"] = completed.stdout
        result["stderr"] = completed.stderr
    except subprocess.TimeoutExpired as exc:
        result["exitCode"] = 2
        result["stderr"] = f"TimeoutExpired:{exc}"
    except Exception as exc:  # noqa: BLE001
        result["exitCode"] = 1
        result["stderr"] = f"{type(exc).__name__}:{exc}"
    finally:
        result["endedAtUtc"] = utc_iso()
        result["durationSeconds"] = round(time.monotonic() - start, 3)
        result["safety"] = safety_flags()
    return result

def latest_report(repo_root: Path) -> Path | None:
    roots = [
        repo_root / ".riftreader-local" / "workflow-status",
        repo_root / ".riftreader-local" / "opencode-status",
        repo_root / ".riftreader-local" / "live-test-triage",
        repo_root / ".riftreader-local" / "riftreader-chatgpt-mcp",
        repo_root / ".riftreader-local" / "package-intake",
        repo_root / ".riftreader-local" / "package-intake-selftest",
        repo_root / ".riftreader-local" / "artifact-bridge-package-drafts",
    ]
    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        candidates.extend(path for path in root.rglob("*.md") if path.is_file())
        candidates.extend(path for path in root.rglob("*.json") if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def command_plan(repo_root: Path) -> dict[str, Any]:
    specs = build_command_specs(repo_root)
    commands = []
    errors: list[str] = []
    for spec in specs.values():
        denied = validate_safe_args(spec.args)
        if denied:
            errors.append(f"{spec.key}-denied:{','.join(denied)}")
        first = Path(spec.args[0])
        if (str(first).lower().endswith(".cmd") or str(first).lower().endswith(".ps1")) and not first.exists():
            errors.append(f"{spec.key}-script-missing:{first}")
        commands.append(
            {
                "key": spec.key,
                "label": spec.label,
                "args": list(spec.args),
                "timeoutSeconds": spec.timeout_seconds,
                "expectedExitCodes": list(spec.expected_exit_codes),
                "description": spec.description,
            }
        )
    return {
        "schemaVersion": 1,
        "kind": "riftreader-operator-lite-command-plan",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "passed",
        "errors": errors,
        "commands": commands,
        "disabledLiveActions": [
            "target-control",
            "visual-gate",
            "proofonly",
            "movement",
            "send-input",
            "ce-x64dbg",
            "git-stage-commit-push",
            "bridge-serve-or-tunnel",
        ],
        "safety": safety_flags(),
    }


def normalize_cli_argv(argv: list[str] | None) -> list[str] | None:
    if argv is None:
        argv = sys.argv[1:]
    return ["--help" if arg.strip().lower() in HELP_ALIASES else arg for arg in argv]


def command_list_payload(repo_root: Path) -> dict[str, Any]:
    plan = command_plan(repo_root)
    groups = build_command_groups()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-operator-lite-command-list",
        "generatedAtUtc": utc_iso(),
        "status": plan["status"],
        "errors": plan["errors"],
        "commands": [
            {
                "key": item["key"],
                "label": item["label"],
                "description": item["description"],
                "expectedExitCodes": item["expectedExitCodes"],
                "timeoutSeconds": item["timeoutSeconds"],
            }
            for item in plan["commands"]
        ],
        "commandAliases": dict(sorted(COMMAND_ALIASES.items())),
        "groups": [
            {
                "key": group.key,
                "label": group.label,
                "description": group.description,
                "commandKeys": list(group.command_keys),
            }
            for group in groups.values()
        ],
        "groupAliases": dict(sorted(GROUP_ALIASES.items())),
        "examples": [
            ".\\scripts\\riftreader-operator-lite.cmd --list-commands --json",
            ".\\scripts\\riftreader-operator-lite.cmd --run bridge-session-start --json",
            ".\\scripts\\riftreader-operator-lite.cmd --run session-start --json",
            ".\\scripts\\riftreader-operator-lite.cmd --session-start --json",
            ".\\scripts\\riftreader-operator-lite.cmd --package-draft --json",
            ".\\scripts\\riftreader-operator-lite.cmd --package-draft-index --json",
            ".\\scripts\\riftreader-operator-lite.cmd --latest-package-draft --json",
            ".\\scripts\\riftreader-operator-lite.cmd --latest-operator-draft --json",
            ".\\scripts\\riftreader-operator-lite.cmd --package-draft-dry-run --json",
            ".\\scripts\\riftreader-operator-lite.cmd --operator-draft-dry-run --json",
            ".\\scripts\\riftreader-operator-lite.cmd --package-draft-selftest --json",
            ".\\scripts\\riftreader-operator-lite.cmd --mcp-trial-readiness --json",
            ".\\scripts\\riftreader-operator-lite.cmd --mcp-mission-control --json",
            ".\\scripts\\riftreader-operator-lite.cmd --mcp-artifacts --json",
            ".\\scripts\\riftreader-operator-lite.cmd --chatgpt-trial-proof-template --json",
            ".\\scripts\\riftreader-operator-lite.cmd --safe-commit-plan --json",
            ".\\scripts\\riftreader-operator-lite.cmd --workflow-router --json",
            ".\\scripts\\riftreader-operator-lite.cmd --run decision-packet --json",
            ".\\scripts\\riftreader-operator-lite.cmd --decision-packet-schema --json",
            ".\\scripts\\riftreader-operator-lite.cmd --decision-packet-agent-plan --json",
            ".\\scripts\\riftreader-operator-lite.cmd --run-all bridge-startup-checks --json",
            ".\\scripts\\riftreader-operator-lite.cmd --proposal-loop-checks --json",
            ".\\scripts\\riftreader-operator-lite.cmd --trial-readiness --json",
            ".\\scripts\\riftreader-operator-lite.cmd /help",
        ],
        "disabledLiveActions": plan["disabledLiveActions"],
        "safety": plan["safety"],
    }


def command_reference_markdown(repo_root: Path) -> str:
    payload = command_list_payload(repo_root)
    lines = [
        "# RiftReader Operator Lite Command Reference",
        "",
        f"- Generated UTC: `{payload.get('generatedAtUtc')}`",
        f"- Status: `{payload.get('status')}`",
        "",
        "## Commands",
        "",
        "| Key | Label | Description |",
        "|---|---|---|",
    ]
    for command in payload["commands"]:
        description = str(command["description"]).replace("|", "\\|")
        lines.append(f"| `{command['key']}` | {command['label']} | {description} |")
    lines.extend(["", "## Groups", "", "| Key | Commands | Description |", "|---|---|---|"])
    for group in payload["groups"]:
        command_keys = ", ".join(f"`{key}`" for key in group["commandKeys"])
        description = str(group["description"]).replace("|", "\\|")
        lines.append(f"| `{group['key']}` | {command_keys} | {description} |")
    lines.extend(["", "## Disabled live actions", ""])
    for action_name in payload["disabledLiveActions"]:
        lines.append(f"- `{action_name}`")
    return "\n".join(lines).rstrip() + "\n"


def resolve_command_key(command_key: str) -> str:
    normalized = command_key.strip().lower()
    return COMMAND_ALIASES.get(normalized, normalized)


def resolve_group_key(group_key: str) -> str:
    normalized = group_key.strip().lower()
    return GROUP_ALIASES.get(normalized, normalized)


def missing_command_result(repo_root: Path, command_key: str) -> dict[str, Any]:
    available = sorted(build_command_specs(repo_root))
    return {
        "schemaVersion": 1,
        "kind": "riftreader-operator-lite-command-run",
        "generatedAtUtc": utc_iso(),
        "status": "blocked",
        "ok": False,
        "code": "COMMAND_KEY_UNKNOWN",
        "commandKey": command_key,
        "availableCommands": available,
        "commandAliases": dict(sorted(COMMAND_ALIASES.items())),
        "exitCode": 2,
        "stdout": "",
        "stderr": f"Unknown safe command key: {command_key}",
        "safety": safety_flags(),
    }


def blocked_command_result(command_key: str, spec: CommandSpec, code: str, message: str) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-operator-lite-command-run",
        "generatedAtUtc": utc_iso(),
        "status": "blocked",
        "ok": False,
        "code": code,
        "commandKey": command_key,
        "label": spec.label,
        "description": spec.description,
        "args": list(spec.args),
        "expectedExitCodes": list(spec.expected_exit_codes),
        "timeoutSeconds": spec.timeout_seconds,
        "exitCode": 2,
        "stdout": "",
        "stderr": message,
        "safety": safety_flags(),
    }


def command_run_status(exit_code: int | None, ok: bool) -> str:
    if ok and exit_code == 0:
        return "passed"
    if ok and exit_code == 2:
        return "blocked"
    if ok:
        return "completed"
    if exit_code == 2:
        return "blocked"
    return "failed"


def parse_stdout_json(stdout: Any) -> dict[str, Any] | None:
    if not isinstance(stdout, str) or not stdout.strip():
        return None
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def run_command_key(repo_root: Path, command_key: str) -> dict[str, Any]:
    requested_command_key = command_key
    command_key = resolve_command_key(command_key)
    specs = build_command_specs(repo_root)
    spec = specs.get(command_key)
    if not spec:
        return missing_command_result(repo_root, requested_command_key)
    denied = validate_safe_args(spec.args)
    if denied:
        return blocked_command_result(
            command_key,
            spec,
            "COMMAND_DENIED",
            f"operator-lite-denied-command-fragment:{','.join(denied)}",
        )
    first = Path(spec.args[0])
    if (str(first).lower().endswith(".cmd") or str(first).lower().endswith(".ps1")) and not first.exists():
        return blocked_command_result(command_key, spec, "COMMAND_SCRIPT_MISSING", f"Command script is missing: {first}")
    result = run_command(spec.args, repo_root, spec.timeout_seconds, spec.expected_exit_codes)
    stdout_json = parse_stdout_json(result.get("stdout", ""))
    return {
        "schemaVersion": 1,
        "kind": "riftreader-operator-lite-command-run",
        "generatedAtUtc": utc_iso(),
        "status": command_run_status(result.get("exitCode"), bool(result.get("ok"))),
        "ok": bool(result.get("ok")),
        "commandKey": command_key,
        "requestedCommandKey": requested_command_key,
        "label": spec.label,
        "description": spec.description,
        "args": list(spec.args),
        "expectedExitCodes": list(spec.expected_exit_codes),
        "timeoutSeconds": spec.timeout_seconds,
        "exitCode": result.get("exitCode"),
        "stdout": result.get("stdout", ""),
        "stdoutJson": stdout_json,
        "stderr": result.get("stderr", ""),
        "startedAtUtc": result.get("startedAtUtc"),
        "endedAtUtc": result.get("endedAtUtc"),
        "durationSeconds": result.get("durationSeconds"),
        "safety": result.get("safety", safety_flags()),
    }


def command_group_status(results: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status")) for item in results}
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if all(item.get("ok") for item in results):
        return "passed"
    return "failed"


def missing_group_result(group_key: str) -> dict[str, Any]:
    groups = build_command_groups()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-operator-lite-command-group-run",
        "generatedAtUtc": utc_iso(),
        "status": "blocked",
        "ok": False,
        "code": "COMMAND_GROUP_UNKNOWN",
        "groupKey": group_key,
        "availableGroups": sorted(groups),
        "groupAliases": dict(sorted(GROUP_ALIASES.items())),
        "exitCode": 2,
        "results": [],
        "safety": safety_flags(),
    }


def run_command_group(repo_root: Path, group_key: str) -> dict[str, Any]:
    requested_group_key = group_key
    group_key = resolve_group_key(group_key)
    groups = build_command_groups()
    group = groups.get(group_key)
    if not group:
        return missing_group_result(requested_group_key)
    results = [run_command_key(repo_root, command_key) for command_key in group.command_keys]
    status = command_group_status(results)
    exit_code = 0 if status == "passed" else 2 if status == "blocked" else 1
    return {
        "schemaVersion": 1,
        "kind": "riftreader-operator-lite-command-group-run",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "groupKey": group.key,
        "requestedGroupKey": requested_group_key,
        "label": group.label,
        "description": group.description,
        "commandKeys": list(group.command_keys),
        "exitCode": exit_code,
        "results": results,
        "safety": safety_flags(),
    }


def bridge_docs_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "workflow" / "local-artifact-bridge.md"


def bridge_payload_root(repo_root: Path) -> Path:
    return repo_root / "artifacts" / "chatgpt-payloads"


def bridge_inbox_root(repo_root: Path) -> Path:
    return repo_root / ".riftreader-local" / "artifact-bridge-inbox"


def bridge_status_summary(repo_root: Path) -> dict[str, Any]:
    payload_root = bridge_payload_root(repo_root)
    inbox_root = bridge_inbox_root(repo_root)
    package_draft_root = repo_root / ".riftreader-local" / "artifact-bridge-package-drafts"
    payloads: list[Path] = []
    if payload_root.is_dir():
        payloads = sorted(
            (
                path
                for path in payload_root.iterdir()
                if path.is_dir() and (path / "manifest.json").is_file() and (path / "chunk-index.json").is_file()
            ),
            key=lambda path: path.stat().st_mtime,
        )
    inbox_items: list[Path] = []
    if inbox_root.is_dir():
        inbox_items = sorted(path for path in inbox_root.iterdir() if path.is_dir() and (path / "metadata.json").is_file())
    package_drafts: list[Path] = []
    if package_draft_root.is_dir():
        package_drafts = sorted(path for path in package_draft_root.iterdir() if path.is_dir() and (path / "summary.json").is_file())
    latest = payloads[-1].name if payloads else None
    return {
        "mode": "read_only_artifacts_guarded_inbox_manual_start",
        "serveManagedByOperatorLite": False,
        "tunnelManagedByOperatorLite": False,
        "payloadRoot": str(payload_root),
        "payloadCount": len(payloads),
        "latestPayloadId": latest,
        "inboxRoot": str(inbox_root),
        "inboxCount": len(inbox_items),
        "packageDraftRoot": str(package_draft_root),
        "packageDraftCount": len(package_drafts),
        "docsPath": str(bridge_docs_path(repo_root)),
        "safety": {
            "artifactReadGetHeadOnly": True,
            "guardedInboxJsonPostOnly": True,
            "inboxWritesLocalIgnoredOnly": True,
            "packageDraftsLocalIgnoredOnly": True,
            "noCommandExecution": True,
            "noArbitraryFileRead": True,
            "noApplyExecute": True,
            "noRepoTargetWrites": True,
            "noLiveRiftInput": True,
            "manualTunnelOnly": True,
        },
    }


def bridge_status_text(repo_root: Path) -> str:
    summary = bridge_status_summary(repo_root)
    latest = summary["latestPayloadId"] or "none"
    return (
        "Local Artifact Bridge: read-only artifacts + guarded local inbox; "
        f"payloads={summary['payloadCount']}; latest={latest}; inbox={summary['inboxCount']}; "
        f"packageDrafts={summary['packageDraftCount']}; "
        "no apply/execute, commands, repo target writes, RIFT input, CE, or x64dbg."
    )


def read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def latest_phase1_summary_path(repo_root: Path) -> Path | None:
    captures = repo_root / "scripts" / "captures"
    if not captures.is_dir():
        return None
    candidates = sorted(captures.glob("phase1-target-entity-snapshot-*/summary.json"), key=lambda path: path.stat().st_mtime)
    return candidates[-1] if candidates else None


def operator_truth_summary(repo_root: Path) -> dict[str, Any]:
    decision_path = repo_root / ".riftreader-local" / "decision-packet" / "latest" / "decision-packet-compact.json"
    decision = read_json_file(decision_path) if decision_path.is_file() else None
    phase1_path = latest_phase1_summary_path(repo_root)
    phase1 = read_json_file(phase1_path) if phase1_path else None
    decision_status = str((decision or {}).get("status") or "missing")
    phase1_status = str((phase1 or {}).get("status") or "missing")
    next_action = (decision or {}).get("safeNextAction") or {}
    target_reader = (phase1 or {}).get("targetCurrentReader") or {}
    reader_json = target_reader.get("readerJson") or {}
    family_id = reader_json.get("familyId") or "unknown-family"
    target_name = (((phase1 or {}).get("readerBridge") or {}).get("target") or {}).get("name") or "unknown-target"
    blockers = list((decision or {}).get("blockers") or []) + list((phase1 or {}).get("blockers") or [])
    if blockers:
        status = "blocked-safe"
    elif decision_status == "passed" and phase1_status == "passed":
        status = "passed"
    elif decision or phase1:
        status = "partial"
    else:
        status = "missing"
    return {
        "status": status,
        "decisionStatus": decision_status,
        "phase1Status": phase1_status,
        "nextAction": next_action.get("key") or "none",
        "familyId": family_id,
        "targetName": target_name,
        "decisionPath": str(decision_path) if decision_path.is_file() else None,
        "phase1Path": str(phase1_path) if phase1_path else None,
        "blockers": blockers[:3],
    }


def operator_truth_text(repo_root: Path) -> str:
    summary = operator_truth_summary(repo_root)
    blocker_text = "; blockers=" + ", ".join(str(item) for item in summary["blockers"]) if summary["blockers"] else ""
    return (
        f"Truth: {summary['status']} · decision={summary['decisionStatus']} · "
        f"phase1={summary['phase1Status']} · target={summary['targetName']} · "
        f"family={summary['familyId']} · next={summary['nextAction']}{blocker_text}"
    )


def redacted_bridge_instructions(repo_root: Path) -> str:
    docs = bridge_docs_path(repo_root)
    return "\n".join(
        [
            "RiftReader Local Artifact Bridge v0.2 — redacted operator instructions",
            "",
            f'cd "{repo_root}"',
            ".\\scripts\\riftreader-local-artifact-bridge.cmd --serve --payload-root artifacts\\chatgpt-payloads --port 8765 --token auto --max-response-mb 25 --max-inbox-mb 1",
            "",
            "Give ChatGPT only a tokenized health URL, redacted in logs like:",
            "http://127.0.0.1:8765/<token>/chatgpt-handoff.json",
            "http://127.0.0.1:8765/<token>/health",
            "https://example.trycloudflare.com/<token>/chatgpt-handoff.json",
            "https://example.trycloudflare.com/<token>/health",
            "",
            "Optional guarded inbox endpoint for operator-approved JSON proposals only:",
            "GET https://example.trycloudflare.com/<token>/inbox/schema.json",
            "POST https://example.trycloudflare.com/<token>/inbox/messages",
            "",
            "Keep tunnel management manual:",
            "cloudflared tunnel --url http://127.0.0.1:8765",
            "",
            "Safety contract: artifact reads use GET/HEAD only; inbox accepts JSON POST only under .riftreader-local; no apply/execute; no command execution; no arbitrary file reads; no repo target writes; no RIFT input; no CE/x64dbg.",
            f"Docs: {docs}",
        ]
    )


def redacted_bridge_start_command(repo_root: Path) -> str:
    return "\n".join(
        [
            "RiftReader Local Artifact Bridge v0.3 — manual start command",
            "",
            f'cd "{repo_root}"',
            ".\\scripts\\riftreader-local-artifact-bridge.cmd --serve --payload-root artifacts\\chatgpt-payloads --port 8765 --token auto --max-response-mb 25 --max-inbox-mb 1",
            "",
            "This starts only the loopback bridge on 127.0.0.1 and prints the real token locally.",
            "Do not paste the real token into public logs. Start any tunnel manually only when needed.",
        ]
    )


def redacted_bridge_inbox_template() -> str:
    return json.dumps(
        {
            "schemaVersion": 1,
            "kind": "chatgpt-message",
            "title": "Short operator-readable title",
            "body": "Write the instruction, note, or data summary here. This is stored as an inert proposal only.",
            "payload": {
                "optionalStructuredData": True,
                "example": "Replace or remove this payload object when it is not needed.",
            },
            "source": {
                "tool": "Desktop ChatGPT",
                "context": "operator-approved local inbox proposal",
            },
            "metadata": {
                "requiresHumanReview": True,
            },
        },
        indent=2,
        sort_keys=True,
    )


def redacted_bridge_package_proposal_template() -> str:
    return json.dumps(
        {
            "schemaVersion": 1,
            "kind": "package-proposal",
            "title": "Short operator-readable package title",
            "body": "Optional summary of why these files should be reviewed as a package draft.",
            "payload": {
                "packageName": "Desktop ChatGPT proposed patch",
                "files": [
                    {
                        "target": "docs/example.md",
                        "content": "# Example\n\nReplace this with the proposed UTF-8 text file content.\n",
                        "encoding": "utf-8",
                    }
                ],
                "checks": [
                    {
                        "name": "compile-bridge",
                        "args": ["python", "-m", "py_compile", "tools/riftreader_workflow/local_artifact_bridge.py"],
                        "expectedExitCodes": [0],
                        "timeoutSeconds": 120,
                    }
                ],
            },
            "source": {
                "tool": "Desktop ChatGPT",
                "context": "operator-approved package proposal for local draft export",
            },
            "metadata": {
                "requiresHumanReview": True,
                "draftOnly": True,
            },
        },
        indent=2,
        sort_keys=True,
    )


def redacted_bridge_chatgpt_prompt(repo_root: Path) -> str:
    docs = bridge_docs_path(repo_root)
    return "\n".join(
        [
            "Use the RiftReader Local Artifact Bridge as a read-only artifact source for this repo task.",
            "",
            "The operator will provide a tokenized bridge URL. Treat these as placeholders until then:",
            "https://example.trycloudflare.com/<token>/",
            "https://example.trycloudflare.com/<token>/chatgpt-handoff.json",
            "https://example.trycloudflare.com/<token>/health",
            "https://example.trycloudflare.com/<token>/payloads/latest/readme.md",
            "https://example.trycloudflare.com/<token>/payloads/latest/chunks.json",
            "https://example.trycloudflare.com/<token>/payloads/latest/chunks/<chunk_id>",
            "https://example.trycloudflare.com/<token>/inbox/schema.json",
            "",
            "Start with the handoff JSON, landing page, or health endpoint, then follow recommendedReadOrder.",
            "Only fetch listed endpoints and registered chunk IDs from chunks.json.",
            "Do not request arbitrary local filesystem paths or command endpoints.",
            "Use GET/HEAD only for artifact reads.",
            "If I explicitly ask you to send repo instructions/data back, fetch /<token>/inbox/schema.json first, then POST JSON only to /<token>/inbox/messages.",
            "Inbox messages are proposals only: no apply, execute, stage, commit, push, live RIFT input, CE/x64dbg, or tunnel management from ChatGPT.",
            "",
            f"Repo docs: {docs}",
        ]
    )


def gui_theme_summary() -> dict[str, Any]:
    return {
        "palette": GUI_PALETTE,
        "buttonVariants": sorted(BUTTON_VARIANTS.keys()),
        "sections": [
            "Workflow Status & Triage",
            "Packages, Reports & Git",
            "Local Artifact Bridge",
            "Locked Live Controls",
        ],
        "visualRules": [
            "dark grouped panels",
            "high contrast action buttons",
            "distinct bridge color",
            "bridge buttons split into action and copy rows",
            "Desktop ChatGPT handoff packet",
            "Desktop ChatGPT session-start packet",
            "guarded inbox JSON template copy",
            "guarded package proposal template copy",
            "guarded package draft export button",
            "package draft index button",
            "newest package draft summary button",
            "latest operator package draft button",
            "explicit latest package draft dry-run button",
            "explicit latest operator draft dry-run button",
            "package proposal loop self-test button",
            "proposal loop checks group button",
            "Desktop ChatGPT trial readiness gate button",
            "ChatGPT MCP trial readiness button",
            "MCP mission control button",
            "latest MCP artifacts button",
            "ChatGPT trial proof template button",
            "safe commit plan button",
            "workflow router button",
            "manual bridge start command copy",
            "guarded inbox index button",
            "redacted ChatGPT bridge prompt copy",
            "muted locked-control badges",
            "persistent safe-mode status bar",
            "local decision packet refresh button",
            "decision packet schema contract button",
            "decision packet agent plan button",
            "browser-dashboard-aligned truth banner",
            "Phase 1 target family/status line",
        ],
    }


def run_gui(repo_root: Path) -> int:
    import tkinter as tk
    from tkinter import filedialog, font as tkfont, messagebox, scrolledtext

    specs = build_command_specs(repo_root)
    groups = build_command_groups()
    palette = GUI_PALETTE

    root = tk.Tk()
    root.title("RiftReader Operator Lite")
    root.geometry("1220x820")
    root.minsize(1040, 720)
    root.configure(bg=palette["background"])

    title_font = tkfont.Font(family="Segoe UI", size=16, weight="bold")
    subtitle_font = tkfont.Font(family="Segoe UI", size=10)
    panel_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
    button_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
    small_font = tkfont.Font(family="Segoe UI", size=9)

    header = tk.Frame(root, bg=palette["background"])
    header.pack(fill=tk.X, padx=14, pady=(12, 6))
    tk.Label(
        header,
        text="RiftReader Operator Lite",
        bg=palette["background"],
        fg=palette["text"],
        font=title_font,
        anchor="w",
    ).pack(fill=tk.X)
    tk.Label(
        header,
        text="Safe local workflow launcher — no movement, debugger attach, bridge serving, tunnel management, or Git mutation.",
        bg=palette["background"],
        fg=palette["muted"],
        font=subtitle_font,
        anchor="w",
    ).pack(fill=tk.X, pady=(2, 0))

    truth_status_var = tk.StringVar(value=operator_truth_text(repo_root))
    bridge_status_var = tk.StringVar(value=bridge_status_text(repo_root))
    truth_banner = tk.Frame(
        header,
        bg=palette["truth_bg"],
        highlightbackground=palette["truth_border"],
        highlightthickness=1,
        padx=10,
        pady=8,
    )
    truth_banner.pack(fill=tk.X, pady=(8, 0))
    tk.Label(
        truth_banner,
        text="Current Truth / Phase 1 Target",
        bg=palette["truth_bg"],
        fg=palette["truth_accent"],
        font=panel_font,
        anchor="w",
    ).pack(fill=tk.X)
    tk.Label(
        truth_banner,
        textvariable=truth_status_var,
        bg=palette["truth_bg"],
        fg=palette["truth_fg"],
        font=small_font,
        anchor="w",
        justify=tk.LEFT,
        wraplength=1120,
    ).pack(fill=tk.X, pady=(3, 0))

    def panel(parent: tk.Misc, title: str, subtitle: str | None = None) -> tk.LabelFrame:
        frame = tk.LabelFrame(
            parent,
            text=f" {title} ",
            bg=palette["panel"],
            fg=palette["text"],
            font=panel_font,
            padx=10,
            pady=8,
            bd=2,
            relief=tk.GROOVE,
            labelanchor="nw",
        )
        frame.pack(fill=tk.X, padx=14, pady=6)
        if subtitle:
            tk.Label(
                frame,
                text=subtitle,
                bg=palette["panel"],
                fg=palette["muted"],
                font=small_font,
                anchor="w",
                justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(0, 6))
        return frame

    def action_button(parent: tk.Misc, text: str, command: Any, variant: str, width: int = 24) -> tk.Button:
        bg_key, active_key = BUTTON_VARIANTS[variant]
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=palette[bg_key],
            fg=palette["text"],
            activebackground=palette[active_key],
            activeforeground=palette["text"],
            disabledforeground=palette["disabled_fg"],
            font=button_font,
            relief=tk.RAISED,
            bd=2,
            padx=12,
            pady=8,
            width=width,
            cursor="hand2",
            highlightbackground=palette["background"],
            highlightcolor=palette["status_fg"],
            highlightthickness=1,
        )
        button.pack(side=tk.LEFT, padx=6, pady=5)
        return button

    def button_row(parent: tk.Misc) -> tk.Frame:
        row = tk.Frame(parent, bg=palette["panel"])
        row.pack(fill=tk.X, pady=(0, 2))
        return row

    def locked_badge(parent: tk.Misc, text: str) -> tk.Label:
        badge = tk.Label(
            parent,
            text=f"LOCKED: {text}",
            bg=palette["disabled_bg"],
            fg=palette["disabled_fg"],
            font=button_font,
            padx=12,
            pady=8,
            relief=tk.RIDGE,
            bd=2,
        )
        badge.pack(side=tk.LEFT, padx=6, pady=5)
        return badge

    workflow_frame = panel(root, "Workflow Status & Triage", "Primary read-only status commands. Exit code 2 still means a safe blocker.")
    package_frame = panel(root, "Packages, Reports & Git", "Dry-run package tools, local reports, and read-only Git status.")
    bridge_frame = panel(root, "Local Artifact Bridge", "Bridge helpers are self-test/session/index/inbox/docs/copy only; persistent serve and tunnels stay manual.")
    tk.Label(
        bridge_frame,
        textvariable=bridge_status_var,
        bg=palette["panel_alt"],
        fg=palette["status_fg"],
        font=small_font,
        anchor="w",
        justify=tk.LEFT,
        padx=10,
        pady=6,
        relief=tk.SOLID,
        bd=1,
    ).pack(fill=tk.X, pady=(0, 6))
    locked_frame = panel(root, "Locked Live Controls", "Shown explicitly so unsafe actions do not look like missing features.")

    def append(text: str) -> None:
        output.insert(tk.END, text.rstrip() + "\n")
        output.see(tk.END)

    def refresh_bridge_status_panel() -> None:
        bridge_status_var.set(bridge_status_text(repo_root))
        truth_status_var.set(operator_truth_text(repo_root))

    def run_spec(key: str) -> None:
        spec = specs[key]
        append(f"\n## {spec.label}\n$ {' '.join(spec.args)}")
        result = run_command(spec.args, repo_root, spec.timeout_seconds, spec.expected_exit_codes)
        append(json.dumps(result, indent=2))
        refresh_bridge_status_panel()

    def run_group_spec(key: str) -> None:
        group = groups[key]
        append(f"\n## {group.label}\n$ .\\scripts\\riftreader-operator-lite.cmd --run-all {key} --json")
        result = run_command_group(repo_root, key)
        append(json.dumps(result, indent=2))
        refresh_bridge_status_panel()

    def run_package_dry_run() -> None:
        selected = filedialog.askopenfilename(title="Select package .zip or manifest package file")
        if not selected:
            selected_dir = filedialog.askdirectory(title="Select package directory")
            selected = selected_dir
        if not selected:
            return
        package_path = Path(selected)
        args = package_intake_dry_run_args(repo_root, package_path)
        append(f"\n## Package Intake Dry-Run\n$ {' '.join(args)}")
        result = run_command(args, repo_root, 120)
        append(json.dumps(result, indent=2))

    def open_latest() -> None:
        report = latest_report(repo_root)
        if not report:
            messagebox.showinfo("RiftReader Operator Lite", "No .riftreader-local report found yet.")
            return
        os.startfile(report)  # type: ignore[attr-defined]
        append(f"Opened latest report: {report}")

    def open_bridge_docs() -> None:
        docs = bridge_docs_path(repo_root)
        if not docs.is_file():
            messagebox.showerror("RiftReader Operator Lite", f"Bridge docs not found:\n{docs}")
            return
        os.startfile(docs)  # type: ignore[attr-defined]
        append(f"Opened bridge docs: {docs}")

    def copy_bridge_instructions() -> None:
        instructions = redacted_bridge_instructions(repo_root)
        root.clipboard_clear()
        root.clipboard_append(instructions)
        append("Copied redacted bridge instructions to clipboard.")

    def copy_bridge_start_command() -> None:
        command = redacted_bridge_start_command(repo_root)
        root.clipboard_clear()
        root.clipboard_append(command)
        append("Copied manual bridge start command to clipboard.")

    def copy_bridge_inbox_template() -> None:
        template = redacted_bridge_inbox_template()
        root.clipboard_clear()
        root.clipboard_append(template)
        append("Copied guarded inbox JSON template to clipboard.")

    def copy_bridge_package_proposal_template() -> None:
        template = redacted_bridge_package_proposal_template()
        root.clipboard_clear()
        root.clipboard_append(template)
        append("Copied guarded package-proposal JSON template to clipboard.")

    def copy_bridge_chatgpt_prompt() -> None:
        prompt = redacted_bridge_chatgpt_prompt(repo_root)
        root.clipboard_clear()
        root.clipboard_append(prompt)
        append("Copied redacted ChatGPT bridge prompt to clipboard.")

    action_button(workflow_frame, "Refresh Workflow Status", lambda: run_spec("workflow-status"), "primary")
    action_button(workflow_frame, "Refresh Decision Packet", lambda: run_spec("decision-packet"), "primary", width=24)
    action_button(workflow_frame, "Decision Packet Schema", lambda: run_spec("decision-packet-schema"), "neutral", width=24)
    action_button(workflow_frame, "Decision Packet Agent Plan", lambda: run_spec("decision-packet-agent-plan"), "neutral", width=27)
    action_button(workflow_frame, "Compact ChatGPT SITREP", lambda: run_spec("compact-sitrep"), "primary", width=23)
    action_button(workflow_frame, "Run Live-Test Triage", lambda: run_spec("live-triage"), "warning")

    action_button(package_frame, "Package Intake Dry-Run", run_package_dry_run, "success")
    action_button(package_frame, "Package Self-Test", lambda: run_spec("package-selftest"), "success", width=18)
    action_button(package_frame, "Git Status", lambda: run_spec("git-status"), "neutral", width=14)
    action_button(package_frame, "Open Latest Report", open_latest, "neutral", width=18)

    bridge_action_row = button_row(bridge_frame)
    action_button(bridge_action_row, "Bridge Self-Test", lambda: run_spec("bridge-selftest"), "bridge", width=18)
    action_button(bridge_action_row, "Bridge Preflight", lambda: run_spec("bridge-preflight"), "bridge", width=18)
    action_button(bridge_action_row, "Bridge Session Start", lambda: run_spec("bridge-session-start"), "bridge", width=21)
    action_button(bridge_action_row, "Bridge Handoff Packet", lambda: run_spec("bridge-handoff"), "bridge", width=21)
    action_button(bridge_action_row, "Bootstrap Payload", lambda: run_spec("bridge-bootstrap-payload"), "warning", width=18)

    bridge_index_row = button_row(bridge_frame)
    action_button(bridge_index_row, "Bridge Payload Index", lambda: run_spec("bridge-index"), "bridge", width=20)
    action_button(bridge_index_row, "Bridge Inbox Index", lambda: run_spec("bridge-inbox-index"), "bridge", width=19)
    action_button(bridge_index_row, "Bridge Latest Inbox", lambda: run_spec("bridge-inbox-latest"), "bridge", width=19)
    action_button(bridge_index_row, "Bridge Package Draft", lambda: run_spec("bridge-inbox-package-draft"), "bridge", width=21)

    bridge_draft_row = button_row(bridge_frame)
    action_button(bridge_draft_row, "Draft Index", lambda: run_spec("package-draft-index"), "bridge", width=15)
    action_button(bridge_draft_row, "Latest Draft Summary", lambda: run_spec("package-draft-latest"), "bridge", width=21)
    action_button(bridge_draft_row, "Latest Operator Draft", lambda: run_spec("package-draft-latest-operator"), "bridge", width=23)

    bridge_dry_run_row = button_row(bridge_frame)
    action_button(bridge_dry_run_row, "Dry-Run Latest Draft", lambda: run_spec("package-draft-dry-run-latest"), "success", width=22)
    action_button(
        bridge_dry_run_row,
        "Dry-Run Operator Draft",
        lambda: run_spec("package-draft-dry-run-latest-operator"),
        "success",
        width=23,
    )

    bridge_loop_row = button_row(bridge_frame)
    action_button(bridge_loop_row, "Draft Loop Self-Test", lambda: run_spec("package-draft-loop-selftest"), "warning", width=22)
    action_button(bridge_loop_row, "Proposal Loop Checks", lambda: run_group_spec("bridge-proposal-loop-checks"), "warning", width=23)
    action_button(bridge_loop_row, "Trial Readiness Gate", lambda: run_group_spec("bridge-trial-readiness"), "warning", width=23)
    action_button(bridge_loop_row, "MCP Trial Readiness", lambda: run_spec("mcp-trial-readiness"), "warning", width=22)

    mcp_helper_row = button_row(bridge_frame)
    action_button(mcp_helper_row, "MCP Mission Control", lambda: run_spec("mcp-mission-control"), "primary", width=22)
    action_button(mcp_helper_row, "Latest MCP Artifacts", lambda: run_spec("mcp-artifacts-latest"), "bridge", width=23)
    action_button(mcp_helper_row, "Workflow Router", lambda: run_spec("workflow-router-mcp"), "primary", width=18)

    mcp_local_row = button_row(bridge_frame)
    action_button(
        mcp_local_row,
        "ChatGPT Trial Proof Template",
        lambda: run_spec("chatgpt-trial-proof-template"),
        "neutral",
        width=29,
    )
    action_button(mcp_local_row, "Safe Commit Plan", lambda: run_spec("safe-commit-plan"), "neutral", width=19)

    bridge_utility_row = button_row(bridge_frame)
    action_button(bridge_utility_row, "Open Bridge Docs", open_bridge_docs, "neutral", width=17)
    action_button(bridge_utility_row, "Copy Bridge Start Command", copy_bridge_start_command, "neutral", width=25)

    bridge_template_row = button_row(bridge_frame)
    action_button(bridge_template_row, "Copy Inbox JSON Template", copy_bridge_inbox_template, "neutral", width=26)
    action_button(bridge_template_row, "Copy Package Proposal Template", copy_bridge_package_proposal_template, "neutral", width=32)

    bridge_copy_row = button_row(bridge_frame)
    action_button(bridge_copy_row, "Copy Redacted Bridge Instructions", copy_bridge_instructions, "neutral", width=31)
    action_button(bridge_copy_row, "Copy ChatGPT Bridge Prompt", copy_bridge_chatgpt_prompt, "neutral", width=28)

    for label in [
        "Target-Control",
        "Visual Gate",
        "ProofOnly",
        "Movement",
        "Promotion",
        "Git Push",
        "Bridge Serve/Tunnel",
    ]:
        locked_badge(locked_frame, label)

    output = scrolledtext.ScrolledText(
        root,
        wrap=tk.WORD,
        height=18,
        bg=palette["output_bg"],
        fg=palette["output_fg"],
        insertbackground=palette["text"],
        font=("Consolas", 10),
        relief=tk.SUNKEN,
        bd=2,
    )
    output.pack(fill=tk.BOTH, expand=True, padx=14, pady=(8, 6))

    status_bar = tk.Label(
        root,
        text="READY · Truth banner mirrors browser dashboard · Safe/offline mode · No live input · No CE/x64dbg · No promotion/push",
        bg=palette["status_bg"],
        fg=palette["status_fg"],
        font=small_font,
        anchor="w",
        padx=10,
        pady=5,
    )
    status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    append("RiftReader Operator Lite loaded.")
    append("Live input, movement, CE/x64dbg, stage/commit/push, target-control, visual gate, and ProofOnly are disabled in v0.")
    append("Local Artifact Bridge controls are self-test/session/index/inbox/docs/copy only; Operator Lite does not start a persistent bridge or tunnel.")
    root.mainloop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline-safe RiftReader Operator Lite.",
        epilog=(
            "Examples: riftreader-operator-lite.cmd --list-commands --json | "
            "riftreader-operator-lite.cmd --session-start --json | "
            "riftreader-operator-lite.cmd --package-draft --json | "
            "riftreader-operator-lite.cmd --package-draft-index --json | "
            "riftreader-operator-lite.cmd --latest-package-draft --json | "
            "riftreader-operator-lite.cmd --latest-operator-draft --json | "
            "riftreader-operator-lite.cmd --package-draft-dry-run --json | "
            "riftreader-operator-lite.cmd --operator-draft-dry-run --json | "
            "riftreader-operator-lite.cmd --package-draft-selftest --json | "
            "riftreader-operator-lite.cmd --mcp-trial-readiness --json | "
            "riftreader-operator-lite.cmd --mcp-mission-control --json | "
            "riftreader-operator-lite.cmd --mcp-artifacts --json | "
            "riftreader-operator-lite.cmd --chatgpt-trial-proof-template --json | "
            "riftreader-operator-lite.cmd --safe-commit-plan --json | "
            "riftreader-operator-lite.cmd --workflow-router --json | "
            "riftreader-operator-lite.cmd --decision-packet --json | "
            "riftreader-operator-lite.cmd --decision-packet-schema --json | "
            "riftreader-operator-lite.cmd --decision-packet-agent-plan --json | "
            "riftreader-operator-lite.cmd --run-all bridge-startup-checks --json | "
            "riftreader-operator-lite.cmd --proposal-loop-checks --json | "
            "riftreader-operator-lite.cmd --trial-readiness --json | "
            "riftreader-operator-lite.cmd /help"
        ),
    )
    parser.add_argument("--repo-root", default=None, help="Repo root. Defaults to the current RiftReader checkout.")
    parser.add_argument("--self-test", action="store_true", help="Validate Operator Lite safe command wiring and exit.")
    parser.add_argument("--command-plan", action="store_true", help="Print the full safe command plan and exit.")
    parser.add_argument("--list-commands", action="store_true", help="List safe command keys available to --run.")
    parser.add_argument("--command-reference-md", action="store_true", help="Print generated Markdown command reference and exit.")
    parser.add_argument("--run", metavar="COMMAND_KEY", help="Run one known safe command key from the command plan.")
    parser.add_argument("--run-all", metavar="GROUP_KEY", help="Run one known safe command group, such as bridge-startup-checks.")
    parser.add_argument("--session-start", action="store_true", help="Shortcut for --run bridge-session-start.")
    parser.add_argument("--bridge-preflight", action="store_true", help="Shortcut for --run bridge-preflight.")
    parser.add_argument("--latest-inbox", action="store_true", help="Shortcut for --run bridge-inbox-latest.")
    parser.add_argument("--package-draft", action="store_true", help="Shortcut for --run bridge-inbox-package-draft.")
    parser.add_argument("--package-draft-index", action="store_true", help="Shortcut for --run package-draft-index.")
    parser.add_argument("--latest-package-draft", action="store_true", help="Shortcut for --run package-draft-latest.")
    parser.add_argument(
        "--latest-operator-draft",
        action="store_true",
        help="Shortcut for --run package-draft-latest-operator.",
    )
    parser.add_argument(
        "--package-draft-dry-run",
        action="store_true",
        help="Shortcut for --run package-draft-dry-run-latest. Never passes --apply.",
    )
    parser.add_argument(
        "--operator-draft-dry-run",
        action="store_true",
        help="Shortcut for --run package-draft-dry-run-latest-operator. Never passes --apply.",
    )
    parser.add_argument(
        "--package-draft-selftest",
        action="store_true",
        help="Shortcut for --run package-draft-loop-selftest.",
    )
    parser.add_argument(
        "--mcp-trial-readiness",
        action="store_true",
        help="Shortcut for --run mcp-trial-readiness.",
    )
    parser.add_argument(
        "--mcp-mission-control",
        action="store_true",
        help="Shortcut for --run mcp-mission-control.",
    )
    parser.add_argument(
        "--mcp-artifacts",
        action="store_true",
        help="Shortcut for --run mcp-artifacts-latest.",
    )
    parser.add_argument(
        "--chatgpt-trial-proof-template",
        action="store_true",
        help="Shortcut for --run chatgpt-trial-proof-template.",
    )
    parser.add_argument(
        "--safe-commit-plan",
        action="store_true",
        help="Shortcut for --run safe-commit-plan. Plan-only; never stages or commits.",
    )
    parser.add_argument(
        "--workflow-router",
        action="store_true",
        help="Shortcut for --run workflow-router-mcp.",
    )
    parser.add_argument(
        "--decision-packet",
        action="store_true",
        help="Shortcut for --run decision-packet. Read-only packet refresh; local ignored artifacts only.",
    )
    parser.add_argument(
        "--decision-packet-schema",
        action="store_true",
        help="Shortcut for --run decision-packet-schema. Read-only schema contract; no artifact writes.",
    )
    parser.add_argument(
        "--decision-packet-agent-plan",
        action="store_true",
        help="Shortcut for --run decision-packet-agent-plan. Read-only parallel-agent work plan.",
    )
    parser.add_argument("--bridge-startup-checks", action="store_true", help="Shortcut for --run-all bridge-startup-checks.")
    parser.add_argument(
        "--proposal-loop-checks",
        action="store_true",
        help="Shortcut for --run-all bridge-proposal-loop-checks.",
    )
    parser.add_argument(
        "--trial-readiness",
        action="store_true",
        help="Shortcut for --run-all bridge-trial-readiness.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON for self-test, command-plan, list-commands, run, or run-all.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_cli_argv(argv))
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    plan = command_plan(repo_root)
    shortcut_command = None
    if args.session_start:
        shortcut_command = "bridge-session-start"
    if args.bridge_preflight:
        shortcut_command = "bridge-preflight"
    if args.latest_inbox:
        shortcut_command = "bridge-inbox-latest"
    if args.package_draft:
        shortcut_command = "bridge-inbox-package-draft"
    if args.package_draft_index:
        shortcut_command = "package-draft-index"
    if args.latest_package_draft:
        shortcut_command = "package-draft-latest"
    if args.latest_operator_draft:
        shortcut_command = "package-draft-latest-operator"
    if args.package_draft_dry_run:
        shortcut_command = "package-draft-dry-run-latest"
    if args.operator_draft_dry_run:
        shortcut_command = "package-draft-dry-run-latest-operator"
    if args.package_draft_selftest:
        shortcut_command = "package-draft-loop-selftest"
    if args.mcp_trial_readiness:
        shortcut_command = "mcp-trial-readiness"
    if args.mcp_mission_control:
        shortcut_command = "mcp-mission-control"
    if args.mcp_artifacts:
        shortcut_command = "mcp-artifacts-latest"
    if args.chatgpt_trial_proof_template:
        shortcut_command = "chatgpt-trial-proof-template"
    if args.safe_commit_plan:
        shortcut_command = "safe-commit-plan"
    if args.workflow_router:
        shortcut_command = "workflow-router-mcp"
    if args.decision_packet:
        shortcut_command = "decision-packet"
    if args.decision_packet_schema:
        shortcut_command = "decision-packet-schema"
    if args.decision_packet_agent_plan:
        shortcut_command = "decision-packet-agent-plan"
    shortcut_count = sum(
        1
        for selected in (
            args.session_start,
            args.bridge_preflight,
            args.latest_inbox,
            args.package_draft,
            args.package_draft_index,
            args.latest_package_draft,
            args.latest_operator_draft,
            args.package_draft_dry_run,
            args.operator_draft_dry_run,
            args.package_draft_selftest,
            args.mcp_trial_readiness,
            args.mcp_mission_control,
            args.mcp_artifacts,
            args.chatgpt_trial_proof_template,
            args.safe_commit_plan,
            args.workflow_router,
            args.decision_packet,
            args.decision_packet_schema,
            args.decision_packet_agent_plan,
        )
        if selected
    )
    if shortcut_count > 1:
        parser.error("select only one command shortcut")
    if args.run and shortcut_command:
        parser.error("do not combine --run with a command shortcut")
    group_shortcut_count = sum(
        1
        for selected in (args.bridge_startup_checks, args.proposal_loop_checks, args.trial_readiness)
        if selected
    )
    if args.run_all and group_shortcut_count:
        parser.error("do not combine --run-all with a command group shortcut")
    if group_shortcut_count > 1:
        parser.error("select only one command group shortcut")
    command_to_run = args.run or shortcut_command
    group_to_run = args.run_all
    if args.bridge_startup_checks:
        group_to_run = "bridge-startup-checks"
    if args.proposal_loop_checks:
        group_to_run = "bridge-proposal-loop-checks"
    if args.trial_readiness:
        group_to_run = "bridge-trial-readiness"
    selected_modes = [
        bool(command_to_run),
        bool(group_to_run),
        bool(args.list_commands),
        bool(args.command_reference_md),
        bool(args.self_test or args.command_plan),
    ]
    if sum(1 for selected in selected_modes if selected) > 1:
        parser.error("select only one action mode: --run/shortcut, --run-all/group shortcut, --list-commands, or --self-test/--command-plan")
    if command_to_run:
        payload = run_command_key(repo_root, command_to_run)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Status: {payload['status']}")
            print(f"Command: {payload.get('commandKey')}")
            print(f"Exit code: {payload.get('exitCode')}")
            if payload.get("stdout"):
                print("")
                print(str(payload["stdout"]).rstrip())
            if payload.get("stderr"):
                print("", file=sys.stderr)
                print(str(payload["stderr"]).rstrip(), file=sys.stderr)
        exit_code = payload.get("exitCode")
        return int(exit_code) if isinstance(exit_code, int) else 1
    if group_to_run:
        payload = run_command_group(repo_root, group_to_run)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Status: {payload['status']}")
            print(f"Group: {payload.get('groupKey')}")
            print(f"Exit code: {payload.get('exitCode')}")
            for result in payload.get("results", []):
                print(f"- {result.get('commandKey')}: {result.get('status')} exit={result.get('exitCode')}")
        exit_code = payload.get("exitCode")
        return int(exit_code) if isinstance(exit_code, int) else 1
    if args.list_commands:
        payload = command_list_payload(repo_root)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Status: {payload['status']}")
            for command in payload["commands"]:
                print(f"- {command['key']}: {command['label']} - {command['description']}")
            for group in payload["groups"]:
                print(f"- group {group['key']}: {group['label']} - {group['description']}")
            for error in payload["errors"]:
                print(f"ERROR: {error}")
        return 1 if payload["status"] != "passed" else 0
    if args.command_reference_md:
        print(command_reference_markdown(repo_root))
        return 0 if plan["status"] == "passed" else 1
    if args.self_test or args.command_plan:
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            print(f"Status: {plan['status']}")
            for command in plan["commands"]:
                print(f"- {command['key']}: {' '.join(command['args'])}")
            for error in plan["errors"]:
                print(f"ERROR: {error}")
        return 1 if plan["status"] != "passed" else 0
    return run_gui(repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
