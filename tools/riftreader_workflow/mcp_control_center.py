#!/usr/bin/env python3
"""Localhost-only GUI backend for the RiftReader ChatGPT MCP control center.

This is intentionally not a generic shell runner.  It exposes a small,
allowlisted set of MCP workflow actions, can manage only the local
RiftReader ChatGPT MCP adapter process it starts itself, and keeps Cloudflare,
ChatGPT registration, Git mutation, RIFT input, CE, and x64dbg outside the
control surface.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from .chatgpt_trial_recorder import FINAL_TOOL_PROOF_MODE
    from .common import find_repo_root, repo_rel as rel, safety_flags, utc_iso
    from .mcp_dashboard import collect_status as collect_dashboard_status
    from .mcp_dashboard import redact_repo_root
    from .mcp_domain_diagnostics import DEFAULT_PUBLIC_HOST, _socket_connect, check_windows_port_owner, public_mcp_url
    from .mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
    from .riftreader_chatgpt_mcp import (
        DEFAULT_CLOUDFLARE_BIC_RULE,
        DEFAULT_CLOUDFLARE_NAMED_TUNNEL,
        DEFAULT_HOST,
        DEFAULT_PORT,
        SERVER_NAME,
    )
except ImportError:  # pragma: no cover - direct script execution fallback.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.chatgpt_trial_recorder import FINAL_TOOL_PROOF_MODE
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, safety_flags, utc_iso
    from riftreader_workflow.mcp_dashboard import collect_status as collect_dashboard_status
    from riftreader_workflow.mcp_dashboard import redact_repo_root
    from riftreader_workflow.mcp_domain_diagnostics import DEFAULT_PUBLIC_HOST, _socket_connect, check_windows_port_owner, public_mcp_url
    from riftreader_workflow.mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
    from riftreader_workflow.riftreader_chatgpt_mcp import (
        DEFAULT_CLOUDFLARE_BIC_RULE,
        DEFAULT_CLOUDFLARE_NAMED_TUNNEL,
        DEFAULT_HOST,
        DEFAULT_PORT,
        SERVER_NAME,
    )


SCHEMA_VERSION = 1
DEFAULT_CONTROL_HOST = "127.0.0.1"
DEFAULT_CONTROL_PORT = 8790
STATIC_ROOT = Path(__file__).resolve().parents[1] / "mcp-control-center"
CONTROL_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "control-center"
STATE_FILE_NAME = "managed-server.json"
ACTION_HISTORY_FILE_NAME = "action-history.jsonl"
STATUS_TTL_SECONDS = 8.0
MAX_OUTPUT_CHARS = 30_000
MAX_LOG_TAIL_CHARS = 12_000
API_MUTATION_HEADER = "X-RiftReader-Control-Center"
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
)
FORBIDDEN_ACTION_FRAGMENTS = (
    " git ",
    " git.exe ",
    " reset ",
    " clean ",
    " push ",
    " commit ",
    " proofonly",
    " x64dbg",
    " cheatengine",
    " cheat engine",
    " cloudflared tunnel ",
    " cloudflared service install",
    " tunnel-client run",
    " /reloadui",
    " --apply",
)


@dataclass(frozen=True)
class ActionSpec:
    key: str
    label: str
    description: str
    category: str
    kind: str
    command: tuple[str, ...] = ()
    timeout_seconds: float = 30.0
    expected_exit_codes: tuple[int, ...] = (0,)
    writes_ignored_artifacts: bool = False
    requires_confirmation: bool = False

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "kind": self.kind,
            "commandText": command_text(self.command) if self.command else None,
            "timeoutSeconds": self.timeout_seconds,
            "expectedExitCodes": list(self.expected_exit_codes),
            "writesIgnoredArtifacts": self.writes_ignored_artifacts,
            "requiresConfirmation": self.requires_confirmation,
        }


ACTION_SPECS: dict[str, ActionSpec] = {
    "start_full_server": ActionSpec(
        key="start_full_server",
        label="Start full local MCP server",
        description="Starts only the repo-owned MCP adapter on 127.0.0.1:8770 with the full ChatGPT tool profile.",
        category="server",
        kind="start-full",
        requires_confirmation=True,
    ),
    "start_readonly_server": ActionSpec(
        key="start_readonly_server",
        label="Start read-only MCP server",
        description="Starts only the repo-owned MCP adapter on 127.0.0.1:8770 with the public read-only profile.",
        category="server",
        kind="start-readonly",
        requires_confirmation=True,
    ),
    "stop_managed_server": ActionSpec(
        key="stop_managed_server",
        label="Stop managed MCP server",
        description="Stops only the MCP adapter process that this Control Center started and verified.",
        category="server",
        kind="stop-managed",
        requires_confirmation=True,
    ),
    "final_gate": ActionSpec(
        key="final_gate",
        label="Final readiness gate",
        description="Runs the compact local final gate status command.",
        category="readiness",
        kind="command",
        command=("cmd", "/c", "scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"),
        timeout_seconds=25.0,
        expected_exit_codes=(0, 1, 2),
    ),
    "mcp_trial_readiness": ActionSpec(
        key="mcp_trial_readiness",
        label="MCP trial readiness",
        description="Runs local MCP trial-readiness checks without public tunnel startup or ChatGPT registration.",
        category="readiness",
        kind="command",
        command=("cmd", "/c", "scripts\\riftreader-operator-lite.cmd", "--mcp-trial-readiness", "--json"),
        timeout_seconds=90.0,
        expected_exit_codes=(0, 2),
        writes_ignored_artifacts=True,
    ),
    "cloudflared_status": ActionSpec(
        key="cloudflared_status",
        label="Cloudflared service status",
        description="Checks the secret-safe Cloudflared service/process status for the named tunnel lane.",
        category="route",
        kind="command",
        command=("cmd", "/c", "scripts\\check_mcp_cloudflared_service.cmd"),
        timeout_seconds=25.0,
        expected_exit_codes=(0, 2),
        writes_ignored_artifacts=True,
    ),
    "domain_diagnostics": ActionSpec(
        key="domain_diagnostics",
        label="Domain diagnostics",
        description="Checks DNS, loopback backend, public TCP 443, and public MCP initialize smoke.",
        category="route",
        kind="command",
        command=("cmd", "/c", "scripts\\riftreader-mcp-domain-diagnostics.cmd", "--public-mcp-host", DEFAULT_PUBLIC_HOST, "--json"),
        timeout_seconds=60.0,
        expected_exit_codes=(0, 1, 2),
        writes_ignored_artifacts=True,
    ),
    "local_self_test": ActionSpec(
        key="local_self_test",
        label="Adapter self-test",
        description="Runs deterministic local adapter safety and contract checks.",
        category="validation",
        kind="command",
        command=("cmd", "/c", "START_RIFTREADER_CHATGPT_MCP.cmd", "self-test"),
        timeout_seconds=60.0,
    ),
    "sdk_validate": ActionSpec(
        key="sdk_validate",
        label="SDK metadata validation",
        description="Validates MCP SDK/tool metadata contracts locally.",
        category="validation",
        kind="command",
        command=("cmd", "/c", "START_RIFTREADER_CHATGPT_MCP.cmd", "validate"),
        timeout_seconds=60.0,
    ),
    "transport_smoke": ActionSpec(
        key="transport_smoke",
        label="Loopback transport smoke",
        description="Runs a bounded temporary loopback transport smoke; does not start the persistent public route.",
        category="validation",
        kind="command",
        command=("cmd", "/c", "START_RIFTREADER_CHATGPT_MCP.cmd", "smoke"),
        timeout_seconds=90.0,
        writes_ignored_artifacts=True,
    ),
    "proposal_smoke": ActionSpec(
        key="proposal_smoke",
        label="Proposal loop smoke",
        description="Runs the guarded proposal transport smoke with synthetic ignored local artifacts only.",
        category="validation",
        kind="command",
        command=("cmd", "/c", "START_RIFTREADER_CHATGPT_MCP.cmd", "proposal-smoke"),
        timeout_seconds=120.0,
        writes_ignored_artifacts=True,
    ),
    "route_plan": ActionSpec(
        key="route_plan",
        label="Route plan",
        description="Prints the active Cloudflare named Tunnel Server URL plan; does not start Cloudflared.",
        category="route",
        kind="command",
        command=("cmd", "/c", "START_RIFTREADER_CHATGPT_MCP.cmd", "plan"),
        timeout_seconds=45.0,
        writes_ignored_artifacts=True,
    ),
    "write_proof_template": ActionSpec(
        key="write_proof_template",
        label="Write proof template",
        description="Writes a fillable actual-client proof template under .riftreader-local for operator completion.",
        category="proof",
        kind="command",
        command=("cmd", "/c", "scripts\\riftreader-chatgpt-trial-recorder.cmd", "--write-template", "--json"),
        timeout_seconds=30.0,
        writes_ignored_artifacts=True,
    ),
    "check_latest_proof_template": ActionSpec(
        key="check_latest_proof_template",
        label="Check latest proof template",
        description="Validates the latest fillable proof template without recording proof.",
        category="proof",
        kind="command",
        command=("cmd", "/c", "scripts\\riftreader-chatgpt-trial-recorder.cmd", "--check-latest-template", "--json"),
        timeout_seconds=30.0,
        expected_exit_codes=(0, 1, 2),
    ),
}


def command_text(args: tuple[str, ...] | list[str]) -> str:
    parts: list[str] = []
    for item in args:
        text = str(item)
        escaped = text.replace('"', '\\"')
        if any(ch.isspace() for ch in text) or '"' in text:
            parts.append(f'"{escaped}"')
        else:
            parts.append(text)
    return " ".join(parts)


def redact_sensitive_text(text: str, repo_root: Path | None = None) -> str:
    redacted = text
    if repo_root is not None:
        root = str(repo_root.resolve())
        redacted = redacted.replace(root, ".").replace(root.replace("\\", "/"), ".")
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("<redacted-secret>", redacted)
    return redacted


def redact_payload(value: Any, repo_root: Path) -> Any:
    redacted = redact_repo_root(value, repo_root)
    text = json.dumps(redacted, sort_keys=True, default=str)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("<redacted-secret>", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return redacted


def parse_json_from_stdout(stdout: str) -> Any:
    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    for line in reversed(stripped.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    start = stripped.find("{")
    end = stripped.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def ensure_control_root(repo_root: Path) -> Path:
    path = repo_root / CONTROL_ROOT
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path(repo_root: Path) -> Path:
    return ensure_control_root(repo_root) / STATE_FILE_NAME


def history_path(repo_root: Path) -> Path:
    return ensure_control_root(repo_root) / ACTION_HISTORY_FILE_NAME


def load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:  # noqa: BLE001 - status must stay available.
        return None


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_history(repo_root: Path, payload: dict[str, Any]) -> None:
    path = history_path(repo_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact_payload(payload, repo_root), sort_keys=True, default=str) + "\n")


def recent_history(repo_root: Path, limit: int = 12) -> list[dict[str, Any]]:
    path = history_path(repo_root)
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except Exception:  # noqa: BLE001
        return []
    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            items.append(parsed)
    return items


def tail_file(path: Path | None, repo_root: Path, limit: int = MAX_LOG_TAIL_CHARS) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        data = path.read_bytes()[-limit:]
    except Exception as exc:  # noqa: BLE001
        return f"<tail failed: {type(exc).__name__}:{exc}>"
    return redact_sensitive_text(data.decode("utf-8", errors="replace"), repo_root)


def control_center_command(repo_root: Path) -> str:
    return f'cd /d "{repo_root}" && scripts\\riftreader-mcp-control-center.cmd --open'


def adapter_command(repo_root: Path, profile: str) -> list[str]:
    adapter = repo_root / "tools" / "riftreader_workflow" / "riftreader_chatgpt_mcp.py"
    return [
        sys.executable,
        str(adapter),
        "--serve",
        "--tool-profile",
        profile,
        "--host",
        DEFAULT_HOST,
        "--port",
        str(DEFAULT_PORT),
        "--transport",
        "streamable-http",
        "--allowed-host",
        DEFAULT_PUBLIC_HOST,
        "--allowed-origin",
        "https://chatgpt.com",
    ]


def pid_process_info(pid: int) -> dict[str, Any]:
    if pid <= 0:
        return {"ok": False, "status": "invalid-pid", "pid": pid}
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return {"ok": True, "status": "running", "pid": pid, "commandLine": ""}
        except OSError:
            return {"ok": False, "status": "not-running", "pid": pid}
    ps_command = (
        "$p=Get-CimInstance Win32_Process -Filter \"ProcessId = {0}\";"
        "if($null -eq $p){{'null'}}else{{$p|Select-Object ProcessId,Name,CommandLine|ConvertTo-Json -Compress}}"
    ).format(pid)
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": "query-failed", "pid": pid, "error": f"{type(exc).__name__}:{exc}"}
    text = completed.stdout.strip()
    if completed.returncode != 0:
        return {"ok": False, "status": "query-failed", "pid": pid, "stderr": completed.stderr[-1000:]}
    if not text or text == "null":
        return {"ok": False, "status": "not-running", "pid": pid}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "status": "query-parse-failed", "pid": pid, "stdout": text[-1000:]}
    return {"ok": True, "status": "running", "pid": pid, **payload}


def managed_state(repo_root: Path) -> dict[str, Any]:
    state = load_json_file(state_path(repo_root)) or {}
    pid = state.get("pid")
    process = pid_process_info(int(pid)) if isinstance(pid, int) else {"ok": False, "status": "not-started"}
    stdout_path = repo_root / str(state.get("stdoutPath") or "") if state.get("stdoutPath") else None
    stderr_path = repo_root / str(state.get("stderrPath") or "") if state.get("stderrPath") else None
    profile = state.get("profile")
    return redact_payload(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-mcp-control-center-managed-server",
            "status": "running" if process.get("ok") else "stopped",
            "ok": bool(process.get("ok")),
            "tracked": bool(state),
            "profile": profile,
            "pid": pid,
            "startedAtUtc": state.get("startedAtUtc"),
            "process": process,
            "statePath": rel(repo_root, state_path(repo_root)),
            "stdoutPath": state.get("stdoutPath"),
            "stderrPath": state.get("stderrPath"),
            "stdoutTail": tail_file(stdout_path, repo_root),
            "stderrTail": tail_file(stderr_path, repo_root),
            "stopScope": "Only a tracked process whose command line contains riftreader_chatgpt_mcp.py can be stopped.",
        },
        repo_root,
    )


def start_managed_server(repo_root: Path, profile: str) -> dict[str, Any]:
    if profile not in {"full", "public-read-only"}:
        return {"status": "failed", "ok": False, "blockers": [f"profile-not-allowed:{profile}"]}
    existing_connect = _socket_connect(DEFAULT_HOST, DEFAULT_PORT, 0.75)
    if existing_connect.get("ok"):
        return {
            "status": "blocked",
            "ok": False,
            "blockers": [f"tcp-{DEFAULT_PORT}-already-listening"],
            "backend": {"connect": existing_connect, "owner": check_windows_port_owner(DEFAULT_PORT)},
            "managedServer": managed_state(repo_root),
        }
    control_root = ensure_control_root(repo_root)
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    stdout_path = control_root / f"adapter-{profile}-{timestamp}.out.log"
    stderr_path = control_root / f"adapter-{profile}-{timestamp}.err.log"
    command = adapter_command(repo_root, profile)
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    stdout_handle = stdout_path.open("ab")
    stderr_handle = stderr_path.open("ab")
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed argv allowlist, no shell.
            command,
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=creationflags,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()
    state = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-control-center-managed-server-state",
        "pid": process.pid,
        "profile": profile,
        "startedAtUtc": utc_iso(),
        "command": command,
        "stdoutPath": rel(repo_root, stdout_path),
        "stderrPath": rel(repo_root, stderr_path),
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
        "publicMcpUrl": public_mcp_url(DEFAULT_PUBLIC_HOST),
        "safety": {
            **safety_flags(),
            "localhostOnly": True,
            "cloudflareMutation": False,
            "chatGptRegistrationMutation": False,
            "gitMutation": False,
            "riftInput": False,
            "cheatEngine": False,
            "x64dbg": False,
        },
    }
    write_json_file(state_path(repo_root), state)
    deadline = time.monotonic() + 5.0
    connect = {"ok": False, "status": "pending"}
    while time.monotonic() < deadline:
        connect = _socket_connect(DEFAULT_HOST, DEFAULT_PORT, 0.5)
        if connect.get("ok"):
            break
        if process.poll() is not None:
            break
        time.sleep(0.25)
    status = "started" if connect.get("ok") else "starting"
    return redact_payload(
        {
            "status": status,
            "ok": bool(connect.get("ok") or process.poll() is None),
            "pid": process.pid,
            "profile": profile,
            "backendConnect": connect,
            "managedServer": managed_state(repo_root),
            "safety": state["safety"],
        },
        repo_root,
    )


def stop_managed_server(repo_root: Path) -> dict[str, Any]:
    path = state_path(repo_root)
    state = load_json_file(path) or {}
    pid = state.get("pid")
    if not isinstance(pid, int):
        return {"status": "not-started", "ok": True, "blockers": [], "managedServer": managed_state(repo_root)}
    info = pid_process_info(pid)
    if not info.get("ok"):
        try:
            path.unlink(missing_ok=True)
        except TypeError:  # pragma: no cover - old Python fallback.
            if path.exists():
                path.unlink()
        return {"status": "already-stopped", "ok": True, "process": info, "managedServer": managed_state(repo_root)}
    command_line = str(info.get("CommandLine") or info.get("commandLine") or "")
    if "riftreader_chatgpt_mcp.py" not in command_line:
        return {
            "status": "blocked",
            "ok": False,
            "blockers": ["tracked-pid-command-line-not-riftreader-mcp-adapter"],
            "process": redact_payload(info, repo_root),
        }
    if os.name == "nt":
        command = ["taskkill", "/PID", str(pid), "/T", "/F"]
    else:
        command = ["kill", str(pid)]
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "ok": False, "blockers": [f"stop-failed:{type(exc).__name__}:{exc}"], "process": info}
    if completed.returncode == 0:
        try:
            path.unlink(missing_ok=True)
        except TypeError:  # pragma: no cover
            if path.exists():
                path.unlink()
    return redact_payload(
        {
            "status": "stopped" if completed.returncode == 0 else "failed",
            "ok": completed.returncode == 0,
            "exitCode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "process": info,
            "managedServer": managed_state(repo_root),
        },
        repo_root,
    )


def run_command_action(repo_root: Path, spec: ActionSpec) -> dict[str, Any]:
    if spec.kind != "command" or not spec.command:
        return {"status": "failed", "ok": False, "blockers": [f"action-not-command:{spec.key}"]}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(spec.command),
            cwd=repo_root,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=spec.timeout_seconds,
        )
        stdout = completed.stdout[-MAX_OUTPUT_CHARS:]
        stderr = completed.stderr[-MAX_OUTPUT_CHARS:]
        parsed = parse_json_from_stdout(completed.stdout)
        exit_code_expected = completed.returncode in spec.expected_exit_codes
        status = "passed" if completed.returncode == 0 else ("blocked" if completed.returncode == 2 else "failed")
        if completed.returncode != 0 and isinstance(parsed, dict) and str(parsed.get("status") or "").lower() == "blocked":
            status = "blocked"
        return redact_payload(
            {
                "status": status,
                "ok": completed.returncode == 0,
                "exitCode": completed.returncode,
                "exitCodeExpected": exit_code_expected,
                "expectedExitCodes": list(spec.expected_exit_codes),
                "durationSeconds": round(time.monotonic() - started, 3),
                "commandText": command_text(spec.command),
                "stdout": stdout,
                "stderr": stderr,
                "parsedJson": parsed,
            },
            repo_root,
        )
    except subprocess.TimeoutExpired as exc:
        return redact_payload(
            {
                "status": "failed",
                "ok": False,
                "blockers": [f"timeout-after-{spec.timeout_seconds}-seconds"],
                "durationSeconds": round(time.monotonic() - started, 3),
                "commandText": command_text(spec.command),
                "stdout": (exc.stdout or "")[-MAX_OUTPUT_CHARS:] if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "")[-MAX_OUTPUT_CHARS:] if isinstance(exc.stderr, str) else "",
            },
            repo_root,
        )
    except Exception as exc:  # noqa: BLE001
        return redact_payload(
            {
                "status": "failed",
                "ok": False,
                "blockers": [f"{type(exc).__name__}:{exc}"],
                "durationSeconds": round(time.monotonic() - started, 3),
                "commandText": command_text(spec.command),
            },
            repo_root,
        )


def run_action(repo_root: Path, action_key: str, *, confirmed: bool = False) -> dict[str, Any]:
    spec = ACTION_SPECS.get(action_key)
    if spec is None:
        return {"status": "failed", "ok": False, "blockers": [f"unknown-action:{action_key}"]}
    if spec.requires_confirmation and not confirmed:
        return {"status": "blocked", "ok": False, "blockers": ["confirmation-required"], "action": spec.as_public_dict()}
    if spec.kind == "start-full":
        result = start_managed_server(repo_root, "full")
    elif spec.kind == "start-readonly":
        result = start_managed_server(repo_root, "public-read-only")
    elif spec.kind == "stop-managed":
        result = stop_managed_server(repo_root)
    elif spec.kind == "command":
        result = run_command_action(repo_root, spec)
    else:
        result = {"status": "failed", "ok": False, "blockers": [f"unsupported-action-kind:{spec.kind}"]}
    envelope = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-control-center-action-result",
        "generatedAtUtc": utc_iso(),
        "action": spec.as_public_dict(),
        "result": result,
        "ok": bool(result.get("ok")),
        "status": result.get("status", "unknown"),
    }
    append_history(repo_root, envelope)
    return redact_payload(envelope, repo_root)


def collect_status(repo_root: Path, public_host: str, *, include_public_smoke: bool) -> dict[str, Any]:
    dashboard_status = collect_dashboard_status(repo_root, public_host, include_public_smoke=include_public_smoke)
    route_url = public_mcp_url(public_host)
    status = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-control-center-status",
        "generatedAtUtc": utc_iso(),
        "status": dashboard_status.get("status"),
        "ok": dashboard_status.get("ok"),
        "controlCenter": {
            "host": DEFAULT_CONTROL_HOST,
            "defaultPort": DEFAULT_CONTROL_PORT,
            "localhostOnly": True,
            "apiMutationHeader": API_MUTATION_HEADER,
            "command": control_center_command(repo_root),
        },
        "chatGpt": {
            "serverUrl": route_url,
            "authentication": "No Authentication",
            "surface": "ChatGPT Web/Desktop Developer Mode",
            "appName": "rift-mcp",
            "connectorStartsServer": False,
        },
        "route": {
            "publicHost": public_host,
            "publicMcpUrl": route_url,
            "namedTunnel": DEFAULT_CLOUDFLARE_NAMED_TUNNEL,
            "browserIntegrityRule": DEFAULT_CLOUDFLARE_BIC_RULE,
            "localBackend": f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp",
        },
        "toolSurface": {
            "service": SERVER_NAME,
            "finalProofMode": FINAL_TOOL_PROOF_MODE,
            "expectedToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "expectedToolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        },
        "dashboardStatus": dashboard_status,
        "managedServer": managed_state(repo_root),
        "actions": [spec.as_public_dict() for spec in ACTION_SPECS.values()],
        "recentActions": recent_history(repo_root),
        "safety": {
            **safety_flags(),
            "localhostOnly": True,
            "arbitraryShellEndpoint": False,
            "arbitraryFilesystemEndpoint": False,
            "gitMutationEndpoint": False,
            "cloudflareMutationEndpoint": False,
            "chatGptRegistrationEndpoint": False,
            "riftInputEndpoint": False,
            "cheatEngineEndpoint": False,
            "x64dbgEndpoint": False,
            "onlyManagedAdapterStop": True,
        },
    }
    return redact_payload(status, repo_root)


class ControlCenterServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        repo_root: Path,
        public_host: str,
        include_public_smoke: bool,
    ) -> None:
        super().__init__(server_address, handler)
        self.repo_root = repo_root
        self.public_host = public_host
        self.include_public_smoke = include_public_smoke
        self._cache_lock = threading.Lock()
        self._cache_at = 0.0
        self._cache: dict[str, Any] | None = None
        self._cache_include_public_smoke: bool | None = None

    def status(self, *, force: bool = False, include_public_smoke: bool | None = None) -> dict[str, Any]:
        with self._cache_lock:
            now = time.monotonic()
            use_smoke = self.include_public_smoke if include_public_smoke is None else include_public_smoke
            if (
                force
                or self._cache_include_public_smoke != use_smoke
                or self._cache is None
                or now - self._cache_at > STATUS_TTL_SECONDS
            ):
                self._cache = collect_status(self.repo_root, self.public_host, include_public_smoke=use_smoke)
                self._cache_include_public_smoke = use_smoke
                self._cache_at = now
            return self._cache

    def invalidate(self) -> None:
        with self._cache_lock:
            self._cache = None
            self._cache_at = 0.0
            self._cache_include_public_smoke = None


class Handler(BaseHTTPRequestHandler):
    server: ControlCenterServer

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def write_body(self, body: bytes) -> None:
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def send_json(self, payload: Any, status_code: int = 200) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.write_body(body)

    def send_static(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            static_root = STATIC_ROOT.resolve()
            if static_root not in (resolved, *resolved.parents):
                self.send_error(403)
                return
            body = resolved.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        if resolved.name == "index.html":
            content_type = "text/html; charset=utf-8"
        elif resolved.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif resolved.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if resolved.suffix in {".html", ".js", ".css"} else "max-age=60")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()
        self.write_body(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            query = parse_qs(parsed.query)
            include_smoke = query.get("publicSmoke", ["0"])[0] in {"1", "true", "yes"}
            force = query.get("force", ["0"])[0] in {"1", "true", "yes"}
            self.send_json(self.server.status(force=force, include_public_smoke=include_smoke))
            return
        if parsed.path in ("", "/", "/index.html"):
            self.send_static(STATIC_ROOT / "index.html")
            return
        relative = parsed.path.lstrip("/")
        if not relative or ".." in Path(relative).parts:
            self.send_error(404)
            return
        self.send_static(STATIC_ROOT / relative)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/actions":
            self.send_error(404)
            return
        if self.headers.get(API_MUTATION_HEADER) != "1":
            self.send_json({"status": "blocked", "ok": False, "blockers": ["missing-control-center-header"]}, 403)
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 16_384)
        except ValueError:
            length = 0
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json({"status": "failed", "ok": False, "blockers": ["invalid-json"]}, 400)
            return
        if not isinstance(payload, dict):
            self.send_json({"status": "failed", "ok": False, "blockers": ["request-not-object"]}, 400)
            return
        action = str(payload.get("action") or "")
        confirmed = payload.get("confirm") is True
        result = run_action(self.server.repo_root, action, confirmed=confirmed)
        self.server.invalidate()
        self.send_json(result, 200 if result.get("ok") else 409)


def registry_static_checks() -> list[str]:
    blockers: list[str] = []
    if not STATIC_ROOT.is_dir():
        blockers.append("static-root-missing")
    for name in ("index.html", "styles.css", "app.js"):
        if not (STATIC_ROOT / name).is_file():
            blockers.append(f"static-file-missing:{name}")
    for spec in ACTION_SPECS.values():
        text = f" {command_text(spec.command).lower()} " if spec.command else ""
        for fragment in FORBIDDEN_ACTION_FRAGMENTS:
            if fragment in text:
                blockers.append(f"forbidden-action-fragment:{spec.key}:{fragment.strip()}")
        if spec.kind.startswith("start") and spec.command:
            blockers.append(f"start-action-must-not-use-command-shell:{spec.key}")
    if "start_full_server" not in ACTION_SPECS or "stop_managed_server" not in ACTION_SPECS:
        blockers.append("managed-server-actions-missing")
    return blockers


def self_test(repo_root: Path, public_host: str) -> dict[str, Any]:
    blockers = registry_static_checks()
    status = collect_status(repo_root, public_host, include_public_smoke=False)
    text = json.dumps(status, sort_keys=True, default=str)
    root_text = str(repo_root.resolve())
    if root_text in text or root_text.replace("\\", "\\\\") in text or root_text.replace("\\", "/") in text:
        blockers.append("absolute-repo-root-exposed")
    if "sk-" in text or "Bearer " in text:
        blockers.append("secret-like-token-exposed")
    safety = status.get("safety") if isinstance(status.get("safety"), dict) else {}
    if safety.get("localhostOnly") is not True:
        blockers.append("localhost-only-flag-missing")
    for disabled_key in (
        "arbitraryShellEndpoint",
        "arbitraryFilesystemEndpoint",
        "gitMutationEndpoint",
        "cloudflareMutationEndpoint",
        "chatGptRegistrationEndpoint",
        "riftInputEndpoint",
        "cheatEngineEndpoint",
        "x64dbgEndpoint",
    ):
        if safety.get(disabled_key) is not False:
            blockers.append(f"safety-flag-not-disabled:{disabled_key}")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-control-center-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "failed",
        "ok": not blockers,
        "blockers": blockers,
        "actionCount": len(ACTION_SPECS),
        "staticRoot": rel(repo_root, STATIC_ROOT) if STATIC_ROOT.is_relative_to(repo_root) else str(STATIC_ROOT),
        "safety": {
            **safety_flags(),
            "serverStarted": False,
            "localhostOnly": True,
            "publicTunnelStarted": False,
            "gitMutation": False,
            "riftInput": False,
            "cheatEngine": False,
            "x64dbg": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Localhost-only RiftReader ChatGPT MCP Control Center GUI.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--host", default=DEFAULT_CONTROL_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_CONTROL_PORT)
    parser.add_argument("--public-mcp-host", default=DEFAULT_PUBLIC_HOST)
    parser.add_argument("--include-public-smoke", action="store_true", help="Include public /mcp smoke in regular status refreshes.")
    parser.add_argument("--open", action="store_true", help="Open the Control Center URL in the default browser after startup.")
    parser.add_argument("--once-json", action="store_true", help="Print one status JSON payload and exit.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.host != DEFAULT_CONTROL_HOST:
        payload = {"status": "failed", "ok": False, "blockers": ["control-center-host-must-be-127.0.0.1"], "host": args.host}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    if args.self_test:
        payload = self_test(repo_root, args.public_mcp_host)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("ok") else 1
    if args.once_json:
        payload = collect_status(repo_root, args.public_mcp_host, include_public_smoke=args.include_public_smoke)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("ok") else 2
    httpd = ControlCenterServer(
        (args.host, args.port),
        Handler,
        repo_root,
        args.public_mcp_host,
        args.include_public_smoke,
    )
    url = f"http://{args.host}:{args.port}/"
    print(f"RiftReader MCP Control Center: {url}")
    print("Scope: localhost-only allowlisted controls; no arbitrary shell, Git mutation, RIFT input, CE, x64dbg, or Cloudflare mutation.")
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nRiftReader MCP Control Center stopped.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
