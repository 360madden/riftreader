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
            description="Run the Local Artifact Bridge safety self-test without starting a persistent server.",
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
        "git-status": CommandSpec(
            key="git-status",
            label="Git Status",
            args=("git", "--no-pager", "status", "--short", "--branch"),
            timeout_seconds=30,
            description="Show local branch and dirty-file state.",
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
        repo_root / ".riftreader-local" / "package-intake",
        repo_root / ".riftreader-local" / "package-intake-selftest",
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


def bridge_docs_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "workflow" / "local-artifact-bridge.md"


def bridge_payload_root(repo_root: Path) -> Path:
    return repo_root / "artifacts" / "chatgpt-payloads"


def bridge_inbox_root(repo_root: Path) -> Path:
    return repo_root / ".riftreader-local" / "artifact-bridge-inbox"


def bridge_status_summary(repo_root: Path) -> dict[str, Any]:
    payload_root = bridge_payload_root(repo_root)
    inbox_root = bridge_inbox_root(repo_root)
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
        "docsPath": str(bridge_docs_path(repo_root)),
        "safety": {
            "artifactReadGetHeadOnly": True,
            "guardedInboxJsonPostOnly": True,
            "inboxWritesLocalIgnoredOnly": True,
            "noCommandExecution": True,
            "noArbitraryFileRead": True,
            "noApplyExecute": True,
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
        "no apply/execute, commands, RIFT input, CE, or x64dbg."
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
            "http://127.0.0.1:8765/<token>/health",
            "https://example.trycloudflare.com/<token>/health",
            "",
            "Optional guarded inbox endpoint for operator-approved JSON proposals only:",
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
            "RiftReader Local Artifact Bridge v0.2 — manual start command",
            "",
            f'cd "{repo_root}"',
            ".\\scripts\\riftreader-local-artifact-bridge.cmd --serve --payload-root artifacts\\chatgpt-payloads --port 8765 --token auto --max-response-mb 25 --max-inbox-mb 1",
            "",
            "This starts only the loopback bridge on 127.0.0.1 and prints the real token locally.",
            "Do not paste the real token into public logs. Start any tunnel manually only when needed.",
        ]
    )


def redacted_bridge_chatgpt_prompt(repo_root: Path) -> str:
    docs = bridge_docs_path(repo_root)
    return "\n".join(
        [
            "Use the RiftReader Local Artifact Bridge as a read-only artifact source for this repo task.",
            "",
            "The operator will provide a tokenized bridge URL. Treat these as placeholders until then:",
            "https://example.trycloudflare.com/<token>/",
            "https://example.trycloudflare.com/<token>/health",
            "https://example.trycloudflare.com/<token>/payloads/latest/readme.md",
            "https://example.trycloudflare.com/<token>/payloads/latest/chunks.json",
            "https://example.trycloudflare.com/<token>/payloads/latest/chunks/<chunk_id>",
            "",
            "Start with the landing page or health endpoint, then follow recommendedReadOrder.",
            "Only fetch listed endpoints and registered chunk IDs from chunks.json.",
            "Do not request arbitrary local filesystem paths or command endpoints.",
            "Use GET/HEAD only for artifact reads.",
            "If I explicitly ask you to send repo instructions/data back, POST JSON only to /<token>/inbox/messages.",
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
            "manual bridge start command copy",
            "guarded inbox index button",
            "redacted ChatGPT bridge prompt copy",
            "muted locked-control badges",
            "persistent safe-mode status bar",
        ],
    }


def run_gui(repo_root: Path) -> int:
    import tkinter as tk
    from tkinter import filedialog, font as tkfont, messagebox, scrolledtext

    specs = build_command_specs(repo_root)
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

    bridge_status_var = tk.StringVar(value=bridge_status_text(repo_root))

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
    bridge_frame = panel(root, "Local Artifact Bridge", "Bridge helpers are self-test/index/inbox/docs/copy only; persistent serve and tunnels stay manual.")
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

    def run_spec(key: str) -> None:
        spec = specs[key]
        append(f"\n## {spec.label}\n$ {' '.join(spec.args)}")
        result = run_command(spec.args, repo_root, spec.timeout_seconds, spec.expected_exit_codes)
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

    def copy_bridge_chatgpt_prompt() -> None:
        prompt = redacted_bridge_chatgpt_prompt(repo_root)
        root.clipboard_clear()
        root.clipboard_append(prompt)
        append("Copied redacted ChatGPT bridge prompt to clipboard.")

    action_button(workflow_frame, "Refresh Workflow Status", lambda: run_spec("workflow-status"), "primary")
    action_button(workflow_frame, "Compact ChatGPT SITREP", lambda: run_spec("compact-sitrep"), "primary", width=23)
    action_button(workflow_frame, "Run Live-Test Triage", lambda: run_spec("live-triage"), "warning")

    action_button(package_frame, "Package Intake Dry-Run", run_package_dry_run, "success")
    action_button(package_frame, "Package Self-Test", lambda: run_spec("package-selftest"), "success", width=18)
    action_button(package_frame, "Git Status", lambda: run_spec("git-status"), "neutral", width=14)
    action_button(package_frame, "Open Latest Report", open_latest, "neutral", width=18)

    action_button(bridge_frame, "Bridge Self-Test", lambda: run_spec("bridge-selftest"), "bridge", width=18)
    action_button(bridge_frame, "Bridge Preflight", lambda: run_spec("bridge-preflight"), "bridge", width=18)
    action_button(bridge_frame, "Bridge Payload Index", lambda: run_spec("bridge-index"), "bridge", width=20)
    action_button(bridge_frame, "Bridge Inbox Index", lambda: run_spec("bridge-inbox-index"), "bridge", width=19)
    action_button(bridge_frame, "Open Bridge Docs", open_bridge_docs, "neutral", width=17)
    action_button(bridge_frame, "Copy Bridge Start Command", copy_bridge_start_command, "neutral", width=25)
    action_button(bridge_frame, "Copy Redacted Bridge Instructions", copy_bridge_instructions, "neutral", width=31)
    action_button(bridge_frame, "Copy ChatGPT Bridge Prompt", copy_bridge_chatgpt_prompt, "neutral", width=28)

    for label in [
        "Target-Control",
        "Visual Gate",
        "ProofOnly",
        "Movement",
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
        text="READY · Safe/offline mode · Read-only artifacts + guarded inbox · No live input · No CE/x64dbg · No Git mutation",
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
    append("Local Artifact Bridge controls are self-test/index/inbox/docs/copy only; Operator Lite does not start a persistent bridge or tunnel.")
    root.mainloop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline-safe RiftReader Operator Lite.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--command-plan", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    plan = command_plan(repo_root)
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
