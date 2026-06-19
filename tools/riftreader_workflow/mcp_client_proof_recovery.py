#!/usr/bin/env python3
"""One-command recovery packet for stale ChatGPT MCP actual-client proof.

This helper deliberately coordinates existing repo-owned checks instead of
substituting local backend status for actual ChatGPT Web/Desktop proof.  It can
start the local backend when missing, verifies the public route, compares the
latest saved actual-client proof to the current tool surface, and writes a
durable ignored summary with the exact next commands for proof recording.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from .chatgpt_trial_recorder import latest_proof_input_template, write_proof_template
    from .common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, timestamped_output_dir, utc_iso
    from .mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES
except ImportError:  # pragma: no cover - direct script execution fallback.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.chatgpt_trial_recorder import latest_proof_input_template, write_proof_template
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES


SCHEMA_VERSION = 1
DEFAULT_PUBLIC_HOST = "mcp.360madden.com"
OUTPUT_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "client-proof-recovery"


def _json_from_envelope(envelope: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    stdout = str(envelope.get("stdout") or envelope.get("stdoutPreview") or "").strip()
    if not stdout:
        return None, "stdout-empty"
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return None, f"stdout-json-invalid:{exc.msg}"
    if not isinstance(value, dict):
        return None, "stdout-json-not-object"
    return value, None


def _dig(obj: Any, *keys: str, default: Any = None) -> Any:
    current = obj
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _tool_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - caller treats unreadable template as absent.
        return None
    return value if isinstance(value, dict) else None


def _latest_template_state(repo_root: Path) -> dict[str, Any]:
    path = latest_proof_input_template(repo_root)
    if path is None:
        return {"status": "missing", "ok": False, "path": None, "current": False}
    payload = _read_json(path)
    current = bool(
        payload
        and payload.get("toolCount") == EXPECTED_CHATGPT_MCP_TOOL_COUNT
        and payload.get("toolOutputSchemaCount") == EXPECTED_CHATGPT_MCP_TOOL_COUNT
        and _tool_names(payload.get("toolNames")) == list(EXPECTED_CHATGPT_MCP_TOOL_NAMES)
        and _tool_names(payload.get("toolOutputSchemaToolNames")) == list(EXPECTED_CHATGPT_MCP_TOOL_NAMES)
    )
    return {
        "status": "current" if current else "stale-or-invalid",
        "ok": current,
        "path": rel(repo_root, path),
        "current": current,
        "toolCount": payload.get("toolCount") if payload else None,
        "toolOutputSchemaCount": payload.get("toolOutputSchemaCount") if payload else None,
    }


def _start_backend(repo_root: Path) -> dict[str, Any]:
    launcher = repo_root / "START_RIFTREADER_CHATGPT_MCP.cmd"
    result: dict[str, Any] = {
        "attempted": True,
        "launcher": rel(repo_root, launcher),
        "ok": False,
        "pid": None,
        "error": None,
    }
    if not launcher.is_file():
        result["error"] = "launcher-missing"
        return result

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed repo-owned launcher argv; no shell string.
            ["cmd", "/c", str(launcher), "serve"],
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception as exc:  # noqa: BLE001 - write diagnostic evidence instead of raising.
        result["error"] = f"{type(exc).__name__}:{exc}"
        return result

    result["ok"] = True
    result["pid"] = process.pid
    return result


def _run_json_command(
    repo_root: Path,
    label: str,
    args: list[str],
    *,
    timeout_seconds: float = 120.0,
    expected_exit_codes: set[int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    envelope = run_command_envelope(
        label,
        args,
        repo_root,
        timeout_seconds=timeout_seconds,
        expected_exit_codes=expected_exit_codes if expected_exit_codes is not None else {0, 1, 2},
        capture_full_output=True,
    )
    payload, parse_error = _json_from_envelope(envelope)
    envelope.pop("stdout", None)
    envelope.pop("stderr", None)
    return envelope, payload, parse_error


def _server_status(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    return _run_json_command(
        repo_root,
        "mcp-server-status",
        ["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"],
        timeout_seconds=60.0,
    )


def _runtime_surface_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    runtime_surface = payload.get("runtimeSurface") if isinstance(payload, dict) else None
    if not isinstance(runtime_surface, dict):
        runtime_surface = {}
    return {
        "status": runtime_surface.get("status"),
        "ok": runtime_surface.get("ok"),
        "expectedToolCount": runtime_surface.get("expectedToolCount"),
        "observedToolCount": runtime_surface.get("observedToolCount"),
        "healthToolCount": runtime_surface.get("healthToolCount"),
        "missingRuntimeTools": [
            name for name in EXPECTED_CHATGPT_MCP_TOOL_NAMES if name not in _tool_names(runtime_surface.get("observedToolNames"))
        ],
        "url": runtime_surface.get("url") or (payload or {}).get("localMcpUrl"),
    }


def _proof_summary(proof_payload: dict[str, Any] | None) -> dict[str, Any]:
    summary = proof_payload.get("proofSummary") if isinstance(proof_payload, dict) else None
    if not isinstance(summary, dict):
        summary = {}
    proof_names = _tool_names(summary.get("toolNames"))
    proof_schema_names = _tool_names(summary.get("toolOutputSchemaToolNames"))
    return {
        "status": (proof_payload or {}).get("status") if isinstance(proof_payload, dict) else None,
        "ok": (proof_payload or {}).get("ok") if isinstance(proof_payload, dict) else None,
        "proofPath": (proof_payload or {}).get("proofPath") if isinstance(proof_payload, dict) else None,
        "toolCount": summary.get("toolCount"),
        "toolOutputSchemaCount": summary.get("toolOutputSchemaCount"),
        "clientTransportStatus": summary.get("clientTransportStatus"),
        "healthCallSucceeded": summary.get("healthCallSucceeded"),
        "missingToolsFromProof": [name for name in EXPECTED_CHATGPT_MCP_TOOL_NAMES if name not in proof_names],
        "extraToolsInProof": [name for name in proof_names if name not in EXPECTED_CHATGPT_MCP_TOOL_NAMES],
        "missingOutputSchemaToolsFromProof": [name for name in EXPECTED_CHATGPT_MCP_TOOL_NAMES if name not in proof_schema_names],
        "extraOutputSchemaToolsInProof": [name for name in proof_schema_names if name not in EXPECTED_CHATGPT_MCP_TOOL_NAMES],
    }


def classify_recovery_state(
    *,
    server_payload: dict[str, Any] | None,
    domain_payload: dict[str, Any] | None,
    final_payload: dict[str, Any] | None,
    proof_payload: dict[str, Any] | None,
    template_state: dict[str, Any],
) -> dict[str, Any]:
    """Return the durable stale-client classification used by tests and CLI."""

    runtime = _runtime_surface_summary(server_payload)
    proof = _proof_summary(proof_payload)
    final_blockers = final_payload.get("blockers") if isinstance(final_payload, dict) else []
    if not isinstance(final_blockers, list):
        final_blockers = []

    backend_running_current = bool(server_payload and server_payload.get("status") == "running-current" and server_payload.get("ok") is True)
    runtime_tool_count_ok = bool(
        runtime.get("observedToolCount") == EXPECTED_CHATGPT_MCP_TOOL_COUNT
        and runtime.get("healthToolCount") in (None, EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        and not runtime.get("missingRuntimeTools")
    )
    public_route_ok = bool(domain_payload and domain_payload.get("ok") is True and _dig(domain_payload, "publicSmoke", "ok") is True)
    proof_tool_count_ok = bool(
        proof.get("toolCount") == EXPECTED_CHATGPT_MCP_TOOL_COUNT
        and proof.get("toolOutputSchemaCount") == EXPECTED_CHATGPT_MCP_TOOL_COUNT
        and not proof.get("missingToolsFromProof")
        and not proof.get("missingOutputSchemaToolsFromProof")
    )
    final_ready = bool(final_payload and final_payload.get("ok") is True and final_payload.get("status") == "passed")
    actual_client_refresh_required = bool(backend_running_current and runtime_tool_count_ok and public_route_ok and not proof_tool_count_ok)

    local_blockers: list[str] = []
    if not backend_running_current:
        local_blockers.append("backend:not-running-current")
    if backend_running_current and not runtime_tool_count_ok:
        local_blockers.append("backend:runtime-tool-surface-mismatch")
    if not public_route_ok:
        local_blockers.append("public-route:not-passed")
    if not template_state.get("current"):
        local_blockers.append("proof-template:not-current")

    if final_ready:
        status = "passed"
    elif actual_client_refresh_required:
        status = "blocked-actual-client-refresh-required"
    elif local_blockers:
        status = "blocked-local-recovery-required"
    else:
        status = "blocked"

    return {
        "status": status,
        "ok": final_ready,
        "expectedToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "expectedToolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        "backendRunningCurrent": backend_running_current,
        "runtimeToolCountOk": runtime_tool_count_ok,
        "publicRouteOk": public_route_ok,
        "actualClientProofMatchesCurrentSurface": proof_tool_count_ok,
        "actualClientRefreshRequired": actual_client_refresh_required,
        "localBlockers": local_blockers,
        "finalBlockers": [str(item) for item in final_blockers],
        "runtimeSurface": runtime,
        "actualClientProof": proof,
        "proofTemplate": template_state,
    }


def _markdown_summary(payload: dict[str, Any]) -> str:
    state = payload["state"]
    next_commands = payload["nextCommands"]
    missing = state["actualClientProof"].get("missingToolsFromProof") or []
    lines = [
        f"# RiftReader MCP client proof recovery — {state['status']}",
        "",
        f"- Generated: `{payload['generatedAtUtc']}`",
        f"- Expected tool count: `{state['expectedToolCount']}`",
        f"- Backend running-current: `{state['backendRunningCurrent']}`",
        f"- Runtime tool surface OK: `{state['runtimeToolCountOk']}`",
        f"- Public route OK: `{state['publicRouteOk']}`",
        f"- Actual-client proof matches current surface: `{state['actualClientProofMatchesCurrentSurface']}`",
        f"- Actual-client refresh required: `{state['actualClientRefreshRequired']}`",
        f"- Latest proof path: `{state['actualClientProof'].get('proofPath')}`",
        f"- Proof template path: `{state['proofTemplate'].get('path')}`",
        "",
        "## Missing tools from actual-client proof",
        "",
    ]
    if missing:
        lines.extend(f"- `{name}`" for name in missing)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Next commands",
            "",
        ]
    )
    for command in next_commands:
        lines.append(f"- `{command}`")
    lines.append("")
    return "\n".join(lines)


def recover(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = find_repo_root(Path(args.repo_root or Path.cwd()))
    command_envelopes: dict[str, Any] = {}
    parse_errors: dict[str, str] = {}
    start_attempt: dict[str, Any] = {"attempted": False}

    initial_envelope, initial_server, initial_parse_error = _server_status(repo_root)
    command_envelopes["initialServerStatus"] = initial_envelope
    if initial_parse_error:
        parse_errors["initialServerStatus"] = initial_parse_error

    server_payload = initial_server
    if not args.no_start_server and not (initial_server and initial_server.get("status") == "running-current" and initial_server.get("ok") is True):
        start_attempt = _start_backend(repo_root)
        # Give the detached launcher a short bounded window to bind 127.0.0.1:8770.
        for index in range(max(1, args.start_wait_seconds)):
            time.sleep(1)
            poll_envelope, poll_payload, poll_parse_error = _server_status(repo_root)
            command_envelopes[f"postStartServerStatus{index + 1}"] = poll_envelope
            if poll_parse_error:
                parse_errors[f"postStartServerStatus{index + 1}"] = poll_parse_error
            server_payload = poll_payload
            if poll_payload and poll_payload.get("status") == "running-current" and poll_payload.get("ok") is True:
                break

    final_server_envelope, final_server_payload, final_server_parse_error = _server_status(repo_root)
    command_envelopes["finalServerStatus"] = final_server_envelope
    if final_server_parse_error:
        parse_errors["finalServerStatus"] = final_server_parse_error
    if final_server_payload is not None:
        server_payload = final_server_payload

    domain_envelope, domain_payload, domain_parse_error = _run_json_command(
        repo_root,
        "domain-diagnostics",
        [
            "cmd",
            "/c",
            "scripts\\riftreader-mcp-domain-diagnostics.cmd",
            "--public-mcp-host",
            args.public_mcp_host,
            "--json",
        ],
        timeout_seconds=90.0,
    )
    command_envelopes["domainDiagnostics"] = domain_envelope
    if domain_parse_error:
        parse_errors["domainDiagnostics"] = domain_parse_error

    proof_envelope, proof_payload, proof_parse_error = _run_json_command(
        repo_root,
        "proof-replay",
        ["cmd", "/c", "python", "tools\\riftreader_workflow\\mcp_proof_replay.py", "--replay", "--json"],
        timeout_seconds=60.0,
    )
    command_envelopes["proofReplay"] = proof_envelope
    if proof_parse_error:
        parse_errors["proofReplay"] = proof_parse_error

    template_state = _latest_template_state(repo_root)
    template_written: dict[str, Any] | None = None
    if args.force_template or not template_state.get("current"):
        template_written = write_proof_template(repo_root)
        template_state = _latest_template_state(repo_root)

    final_envelope, final_payload, final_parse_error = _run_json_command(
        repo_root,
        "final-readiness",
        ["cmd", "/c", "scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"],
        timeout_seconds=120.0,
    )
    command_envelopes["finalReadiness"] = final_envelope
    if final_parse_error:
        parse_errors["finalReadiness"] = final_parse_error

    state = classify_recovery_state(
        server_payload=server_payload,
        domain_payload=domain_payload,
        final_payload=final_payload,
        proof_payload=proof_payload,
        template_state=template_state,
    )

    template_path = template_state.get("path")
    check_command = (
        f'scripts\\riftreader-chatgpt-trial-recorder.cmd --check-input --input "{template_path}" --json'
        if template_path
        else "scripts\\riftreader-chatgpt-trial-recorder.cmd --write-template --json"
    )
    record_command = (
        f'scripts\\riftreader-chatgpt-trial-recorder.cmd --record --input "{template_path}" --json'
        if template_path
        else ""
    )
    next_commands = [
        "START_RIFTREADER_CHATGPT_MCP.cmd serve",
        "scripts\\riftreader-mcp-server-status.cmd --json",
        f"scripts\\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host {args.public_mcp_host} --json",
        check_command,
    ]
    if record_command:
        next_commands.append(record_command)
    next_commands.append("scripts\\riftreader-mcp-final.cmd --status --compact-json")

    output_dir = timestamped_output_dir(repo_root / OUTPUT_ROOT)
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-mcp-client-proof-recovery",
        "generatedAtUtc": utc_iso(),
        "status": state["status"],
        "ok": state["ok"],
        "state": state,
        "serverStart": start_attempt,
        "templateWritten": template_written,
        "nextCommands": next_commands,
        "artifacts": {
            "summaryJson": rel(repo_root, output_dir / "summary.json"),
            "summaryMarkdown": rel(repo_root, output_dir / "summary.md"),
        },
        "commandEnvelopes": command_envelopes,
        "parseErrors": parse_errors,
        "safety": {
            **safety_flags(),
            "persistentServerStartAttempted": bool(start_attempt.get("attempted")),
            "persistentServerStarted": bool(start_attempt.get("ok")),
            "publicTunnelStarted": False,
            "chatGptRegistrationPerformed": False,
            "chatGptApiCalled": False,
            "actualClientProofFabricated": False,
            "writesUnderRiftreaderLocalOnly": True,
        },
    }
    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary.md"
    summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    summary_md.write_text(_markdown_summary(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--public-mcp-host", default=DEFAULT_PUBLIC_HOST)
    parser.add_argument("--no-start-server", action="store_true", help="Do not launch START_RIFTREADER_CHATGPT_MCP.cmd if the backend is missing.")
    parser.add_argument("--start-wait-seconds", type=int, default=12)
    parser.add_argument("--force-template", action="store_true", help="Always write a fresh actual-client proof template.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = recover(args)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_markdown_summary(payload))
        print(f"Summary JSON: {payload['artifacts']['summaryJson']}")
        print(f"Summary Markdown: {payload['artifacts']['summaryMarkdown']}")

    if payload.get("ok"):
        return 0
    if payload.get("status") == "blocked-actual-client-refresh-required":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
