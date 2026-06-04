#!/usr/bin/env python3
# Version: riftreader-mcp-client-config-v0.1.0
# Total-Character-Count: 0000008478
# Purpose: Generate RiftReader MCP client config and run a local stdio JSON-RPC smoke test against the repo-owned MCP server.

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "riftreader-mcp-client-config-v0.1.0"
DEFAULT_REPO = Path(r"C:\RIFT MODDING\RiftReader")
EXPECTED_TOOLS = {
    "riftreader.get_git_state",
    "riftreader.get_current_handoff",
    "riftreader.get_status",
    "riftreader.run_compact_status",
    "riftreader.run_static_chain_diagnostics",
    "riftreader.publish_chatgpt_snapshot",
}


class ClientConfigError(RuntimeError):
    pass


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def repo_root(raw: str | Path) -> Path:
    repo = Path(raw).resolve()
    if not (repo / ".git").exists():
        raise ClientConfigError(f"Missing .git under repo: {repo}")
    if not (repo / "scripts" / "riftreader-mcp-server.cmd").is_file():
        raise ClientConfigError("Missing scripts/riftreader-mcp-server.cmd")
    if not (repo / "tools" / "riftreader_mcp" / "server.py").is_file():
        raise ClientConfigError("Missing tools/riftreader_mcp/server.py")
    return repo


def mcp_config(repo: Path, *, server_name: str = "riftreader") -> dict[str, Any]:
    return {
        "mcpServers": {
            server_name: {
                "command": str(repo / "scripts" / "riftreader-mcp-server.cmd"),
                "args": ["--repo", str(repo)],
            }
        }
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_stderr(pipe: Any, sink: list[str]) -> None:
    if pipe is None:
        return
    for line in pipe:
        sink.append(line)


def read_response_line(proc: subprocess.Popen[str], *, timeout_seconds: float) -> str:
    line_holder: list[str] = []
    error_holder: list[BaseException] = []

    def target() -> None:
        try:
            if proc.stdout is None:
                raise RuntimeError("stdout pipe missing")
            line_holder.append(proc.stdout.readline())
        except BaseException as exc:  # noqa: BLE001
            error_holder.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        raise ClientConfigError(f"Timed out waiting for MCP response after {timeout_seconds}s.")
    if error_holder:
        raise ClientConfigError(f"Failed reading MCP response: {type(error_holder[0]).__name__}: {error_holder[0]}")
    if not line_holder or not line_holder[0]:
        raise ClientConfigError("MCP server closed stdout before sending a response.")
    return line_holder[0].strip()


def send_request(proc: subprocess.Popen[str], request: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    if proc.stdin is None:
        raise ClientConfigError("stdin pipe missing")
    proc.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    proc.stdin.flush()
    raw = read_response_line(proc, timeout_seconds=timeout_seconds)
    response = json.loads(raw)
    if not isinstance(response, dict):
        raise ClientConfigError("MCP response was not a JSON object.")
    return response


def smoke_test(repo: Path, *, timeout_seconds: int = 30) -> dict[str, Any]:
    server = repo / "tools" / "riftreader_mcp" / "server.py"
    command = [sys.executable, str(server), "--repo", str(repo)]
    stderr_lines: list[str] = []
    proc = subprocess.Popen(
        command,
        cwd=str(repo),
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stderr_thread = threading.Thread(target=read_stderr, args=(proc.stderr, stderr_lines), daemon=True)
    stderr_thread.start()
    try:
        initialize = send_request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "riftreader-local-smoke", "version": VERSION},
                },
            },
            timeout_seconds=timeout_seconds,
        )
        tools = send_request(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, timeout_seconds=timeout_seconds)
        git_state = send_request(
            proc,
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "riftreader.get_git_state", "arguments": {}}},
            timeout_seconds=timeout_seconds,
        )
    finally:
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except Exception:
            pass
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        except Exception:
            proc.kill()
        finally:
            for pipe in (proc.stdout, proc.stderr):
                try:
                    if pipe and not pipe.closed:
                        pipe.close()
                except Exception:
                    pass
            stderr_thread.join(timeout=1)

    tool_names = set()
    try:
        tool_names = {str(item.get("name")) for item in tools.get("result", {}).get("tools", []) if isinstance(item, dict)}
    except Exception:
        tool_names = set()

    missing = sorted(EXPECTED_TOOLS - tool_names)
    status = "passed" if not missing and "result" in initialize and "result" in tools and "result" in git_state else "failed"
    return {
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "command": command,
        "expectedToolCount": len(EXPECTED_TOOLS),
        "actualToolCount": len(tool_names),
        "missingTools": missing,
        "initialize": initialize,
        "toolsListToolNames": sorted(tool_names),
        "getGitState": git_state,
        "stderr": "".join(stderr_lines)[-4000:],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate RiftReader MCP config and smoke-test the MCP stdio server.")
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--server-name", default="riftreader")
    parser.add_argument("--print-config", action="store_true")
    parser.add_argument("--write-config", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = repo_root(args.repo)
    config = mcp_config(repo, server_name=args.server_name)
    output_dir = repo / ".riftreader-local" / "mcp" / "client-config" / utc_stamp()
    summary: dict[str, Any] = {
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "repo": str(repo),
        "serverName": args.server_name,
        "config": config,
        "writtenConfig": None,
        "smoke": None,
        "status": "passed",
    }

    try:
        if args.write_config:
            config_path = output_dir / "mcp-client-config.json"
            write_json(config_path, config)
            summary["writtenConfig"] = str(config_path)
        if args.smoke:
            summary["smoke"] = smoke_test(repo, timeout_seconds=args.timeout_seconds)
            if summary["smoke"].get("status") != "passed":
                summary["status"] = "failed"
        if not (args.print_config or args.write_config or args.smoke):
            summary["status"] = "blocked"
            summary["nextRecommendedAction"] = "Run with --print-config, --write-config, or --smoke."
            return_code = 2
        else:
            return_code = 0 if summary["status"] == "passed" else 1
        if args.print_config and not args.json:
            print(json.dumps(config, indent=2))
        else:
            print(json.dumps(summary, indent=2))
        return return_code
    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(summary, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
