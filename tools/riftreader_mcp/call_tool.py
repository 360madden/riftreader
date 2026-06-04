#!/usr/bin/env python3
# Version: riftreader-mcp-tool-caller-v0.1.2
# Total-Character-Count: 0000007893
# Purpose: Local CLI client for invoking allowlisted RiftReader MCP tools over stdio without an external MCP UI.

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "riftreader-mcp-tool-caller-v0.1.2"
DEFAULT_REPO = Path(r"C:\RIFT MODDING\RiftReader")


class ToolCallError(RuntimeError):
    pass


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_root(raw: str | Path) -> Path:
    repo = Path(raw).resolve()
    if not (repo / ".git").exists():
        raise ToolCallError(f"Missing .git under repo: {repo}")
    if not (repo / "tools" / "riftreader_mcp" / "server.py").is_file():
        raise ToolCallError("Missing tools/riftreader_mcp/server.py")
    return repo


def read_stderr(pipe: Any, sink: list[str]) -> None:
    if pipe is None:
        return
    for line in pipe:
        sink.append(line)


def read_response_line(proc: subprocess.Popen[str], *, timeout_seconds: float) -> str:
    line_holder: list[str] = []
    error_holder: list[BaseException] = []

    def reader() -> None:
        try:
            if proc.stdout is None:
                raise RuntimeError("stdout pipe missing")
            line_holder.append(proc.stdout.readline())
        except BaseException as exc:  # noqa: BLE001
            error_holder.append(exc)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        raise ToolCallError(f"Timed out waiting for MCP response after {timeout_seconds}s.")
    if error_holder:
        raise ToolCallError(f"Failed reading MCP response: {type(error_holder[0]).__name__}: {error_holder[0]}")
    if not line_holder or not line_holder[0]:
        raise ToolCallError("MCP server closed stdout before sending a response.")
    return line_holder[0].strip()


def send_request(proc: subprocess.Popen[str], request: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    if proc.stdin is None:
        raise ToolCallError("stdin pipe missing")
    proc.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    proc.stdin.flush()
    raw = read_response_line(proc, timeout_seconds=timeout_seconds)
    response = json.loads(raw)
    if not isinstance(response, dict):
        raise ToolCallError("MCP response was not a JSON object.")
    return response


def extract_text_content(response: dict[str, Any]) -> str | None:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    content = result.get("content") if isinstance(result.get("content"), list) else []
    chunks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text") or ""))
    return "\n".join(chunks) if chunks else None


def parse_arguments_json(raw: str | None, file_path: str | None) -> dict[str, Any]:
    if raw and file_path:
        raise ToolCallError("Use either --arguments-json or --arguments-file, not both.")
    if file_path:
        payload = json.loads(Path(file_path).read_text(encoding="utf-8-sig"))
    elif raw:
        payload = json.loads(raw)
    else:
        payload = {}
    if not isinstance(payload, dict):
        raise ToolCallError("Tool arguments must be a JSON object.")
    return payload


def call_tool(repo: Path, *, tool: str, arguments: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
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
                    "clientInfo": {"name": "riftreader-mcp-tool-caller", "version": VERSION},
                },
            },
            timeout_seconds=timeout_seconds,
        )
        tools = send_request(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, timeout_seconds=timeout_seconds)
        available_tools = sorted(
            str(item.get("name"))
            for item in tools.get("result", {}).get("tools", [])
            if isinstance(item, dict) and item.get("name")
        )
        if tool not in available_tools:
            raise ToolCallError(f"Tool not available: {tool}. Available: {', '.join(available_tools)}")
        tool_response = send_request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            },
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

    return {
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "repo": str(repo),
        "tool": tool,
        "arguments": arguments,
        "status": "passed" if "result" in tool_response and not tool_response.get("result", {}).get("isError") else "failed",
        "command": command,
        "initialize": initialize,
        "availableTools": available_tools,
        "toolResponse": tool_response,
        "textContent": extract_text_content(tool_response),
        "stderr": "".join(stderr_lines)[-4000:],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call one allowlisted RiftReader MCP tool over stdio.")
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--tool", required=True)
    parser.add_argument("--arguments-json")
    parser.add_argument("--arguments-file")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo = repo_root(args.repo)
        arguments = parse_arguments_json(args.arguments_json, args.arguments_file)
        payload = call_tool(repo, tool=args.tool, arguments=arguments, timeout_seconds=args.timeout_seconds)
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("status") == "passed" else 1
    except Exception as exc:
        payload = {
            "version": VERSION,
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(payload, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
