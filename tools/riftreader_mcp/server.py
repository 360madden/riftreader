#!/usr/bin/env python3
# Version: riftreader-mcp-server-v0.1.0
# Total-Character-Count: 0000020761
# Purpose: RiftReader-specific MCP stdio server exposing strict allowlisted repo/status tools only; no generic shell, no movement, no CE, no x64dbg.

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


VERSION = "riftreader-mcp-server-v0.1.0"
PROTOCOL_VERSION = "2025-06-18"
DEFAULT_REPO = Path(r"C:\RIFT MODDING\RiftReader")


class McpError(RuntimeError):
    def __init__(self, message: str, *, code: int = -32000) -> None:
        super().__init__(message)
        self.code = code


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def text_result(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    text = value if isinstance(value, str) else json_text(value)
    return {"content": [{"type": "text", "text": text}], "isError": bool(is_error)}


def compact_text(value: str, limit: int = 120_000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n\n... truncated to {limit} characters ..."


def repo_root(raw: str | Path | None) -> Path:
    root = Path(raw or DEFAULT_REPO).resolve()
    if not (root / ".git").exists():
        raise McpError(f"Repo .git directory not found: {root}")
    return root


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def porcelain_paths(stdout: str) -> list[str]:
    paths: list[str] = []
    for raw in stdout.splitlines():
        if not raw.strip():
            continue
        path = raw[3:] if len(raw) > 3 else raw.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(normalize_path(path))
    return sorted(paths)


def run_command(args: list[str], cwd: Path, *, timeout: int = 120, ok_codes: set[int] | None = None) -> dict[str, Any]:
    ok_codes = ok_codes or {0}
    started = utc_iso()
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
        exit_code = None
        timed_out = True

    return {
        "args": args,
        "cwd": str(cwd),
        "startedAtUtc": started,
        "completedAtUtc": utc_iso(),
        "timeoutSeconds": timeout,
        "exitCode": exit_code,
        "timedOut": timed_out,
        "ok": (not timed_out and exit_code in ok_codes),
        "stdout": stdout,
        "stderr": stderr,
    }


def run_cmd_script(repo: Path, script_rel: str, args: list[str], *, timeout: int, ok_codes: set[int] | None = None) -> dict[str, Any]:
    script = repo / script_rel
    if not script.is_file():
        raise McpError(f"Required script missing: {script_rel}")
    if os.name == "nt":
        cmd = ["cmd", "/c", str(script), *args]
    else:
        cmd = [str(script), *args]
    return run_command(cmd, repo, timeout=timeout, ok_codes=ok_codes)


def latest_dir(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    dirs = [item for item in root.iterdir() if item.is_dir()]
    return max(dirs, key=lambda item: item.stat().st_mtime) if dirs else None


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_read_text(path: Path, max_chars: int = 120_000) -> str:
    if not path.is_file():
        raise McpError(f"File not found: {path}")
    return compact_text(path.read_text(encoding="utf-8", errors="replace"), limit=max_chars)


def write_artifact(repo: Path, lane: str, payload: dict[str, Any]) -> Path:
    out_dir = repo / ".riftreader-local" / "mcp" / lane / utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "summary.json"
    out.write_text(json_text(payload), encoding="utf-8")
    return out


class RiftReaderMcpServer:
    def __init__(self, repo: Path) -> None:
        self.repo = repo_root(repo)
        self.tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "riftreader.get_git_state": self.tool_get_git_state,
            "riftreader.get_current_handoff": self.tool_get_current_handoff,
            "riftreader.get_status": self.tool_get_status,
            "riftreader.run_compact_status": self.tool_run_compact_status,
            "riftreader.run_static_chain_diagnostics": self.tool_run_static_chain_diagnostics,
            "riftreader.publish_chatgpt_snapshot": self.tool_publish_chatgpt_snapshot,
        }

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "riftreader.get_git_state",
                "title": "RiftReader git state",
                "description": "Read-only Git status/head/remote SHA for the local RiftReader repo.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                "annotations": {"readOnlyHint": True, "destructiveHint": False},
            },
            {
                "name": "riftreader.get_current_handoff",
                "title": "RiftReader current handoff",
                "description": "Read the current RiftReader handoff Markdown and JSON files.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"maxChars": {"type": "integer", "minimum": 1000, "maximum": 200000, "default": 80000}},
                    "additionalProperties": False,
                },
                "annotations": {"readOnlyHint": True, "destructiveHint": False},
            },
            {
                "name": "riftreader.get_status",
                "title": "RiftReader latest compact status",
                "description": "Read the latest compact status; optionally run the compact status helper first.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "runFirst": {"type": "boolean", "default": False},
                        "maxChars": {"type": "integer", "minimum": 1000, "maximum": 200000, "default": 120000},
                    },
                    "additionalProperties": False,
                },
                "annotations": {"readOnlyHint": True, "destructiveHint": False},
            },
            {
                "name": "riftreader.run_compact_status",
                "title": "Run compact status",
                "description": "Run scripts/riftreader-workflow-status.cmd --compact-json --write and return the JSON output.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"timeoutSeconds": {"type": "integer", "minimum": 30, "maximum": 300, "default": 180}},
                    "additionalProperties": False,
                },
                "annotations": {"readOnlyHint": True, "destructiveHint": False},
            },
            {
                "name": "riftreader.run_static_chain_diagnostics",
                "title": "Run static-chain diagnostics",
                "description": "Run no-input static-chain repair diagnostics: actor-chain no-debug status, static field access matrix, and family neighborhood analysis.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"timeoutSeconds": {"type": "integer", "minimum": 60, "maximum": 900, "default": 300}},
                    "additionalProperties": False,
                },
                "annotations": {"readOnlyHint": True, "destructiveHint": False},
            },
            {
                "name": "riftreader.publish_chatgpt_snapshot",
                "title": "Publish ChatGPT snapshot",
                "description": "Run the existing snapshot publisher helper. Requires the local bridge/session prerequisites already used by RiftReader.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "push": {"type": "boolean", "default": True},
                        "waitUrlFileSeconds": {"type": "integer", "minimum": 0, "maximum": 300, "default": 90},
                        "timeoutSeconds": {"type": "integer", "minimum": 60, "maximum": 900, "default": 300},
                    },
                    "additionalProperties": False,
                },
                "annotations": {"readOnlyHint": False, "destructiveHint": False},
            },
        ]

    def tool_get_git_state(self, arguments: dict[str, Any]) -> dict[str, Any]:
        del arguments
        commands = {
            "branch": run_command(["git", "branch", "--show-current"], self.repo, timeout=30),
            "status": run_command(["git", "status", "--short", "--branch"], self.repo, timeout=30),
            "head": run_command(["git", "log", "-1", "--pretty=%H%n%s"], self.repo, timeout=30),
            "remote": run_command(["git", "ls-remote", "origin", "refs/heads/main"], self.repo, timeout=60),
        }
        payload = {
            "repo": str(self.repo),
            "generatedAtUtc": utc_iso(),
            "branch": commands["branch"]["stdout"].strip(),
            "statusShort": commands["status"]["stdout"],
            "dirtyPaths": porcelain_paths(commands["status"]["stdout"]),
            "head": commands["head"]["stdout"].splitlines(),
            "remoteMain": commands["remote"]["stdout"].strip(),
            "commandsOk": {key: value["ok"] for key, value in commands.items()},
        }
        return text_result(payload)

    def tool_get_current_handoff(self, arguments: dict[str, Any]) -> dict[str, Any]:
        max_chars = int(arguments.get("maxChars", 80_000))
        md = self.repo / "handoffs" / "current" / "RIFTREADER_CURRENT_HANDOFF.md"
        js = self.repo / "handoffs" / "current" / "RIFTREADER_CURRENT_HANDOFF.json"
        payload = {
            "repo": str(self.repo),
            "generatedAtUtc": utc_iso(),
            "markdownPath": str(md),
            "jsonPath": str(js),
            "markdown": safe_read_text(md, max_chars=max_chars) if md.is_file() else None,
            "json": read_json_file(js) if js.is_file() else None,
        }
        return text_result(payload)

    def tool_run_compact_status(self, arguments: dict[str, Any]) -> dict[str, Any]:
        timeout = int(arguments.get("timeoutSeconds", 180))
        envelope = run_cmd_script(
            self.repo,
            "scripts/riftreader-workflow-status.cmd",
            ["--compact-json", "--write"],
            timeout=timeout,
            ok_codes={0, 2},
        )
        payload: dict[str, Any] = {"generatedAtUtc": utc_iso(), "command": {k: v for k, v in envelope.items() if k not in ("stdout", "stderr")}}
        try:
            payload["compactStatus"] = json.loads(envelope["stdout"])
        except Exception as exc:
            payload["parseError"] = f"{type(exc).__name__}: {exc}"
            payload["stdout"] = compact_text(envelope["stdout"])
            payload["stderr"] = compact_text(envelope["stderr"])
        summary_path = write_artifact(self.repo, "compact-status", payload)
        payload["mcpSummaryJson"] = str(summary_path)
        return text_result(payload, is_error=not envelope["ok"])

    def tool_get_status(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if bool(arguments.get("runFirst", False)):
            return self.tool_run_compact_status({"timeoutSeconds": int(arguments.get("timeoutSeconds", 180))})
        max_chars = int(arguments.get("maxChars", 120_000))
        latest = latest_dir(self.repo / ".riftreader-local" / "workflow-status")
        if latest is None:
            return text_result({"status": "missing", "message": "No workflow-status runs found. Call riftreader.run_compact_status first."}, is_error=True)
        compact_path = latest / "compact-sitrep.json"
        markdown_path = latest / "COMPACT_SITREP.md"
        payload = {
            "generatedAtUtc": utc_iso(),
            "latestRunDir": str(latest),
            "compactJsonPath": str(compact_path),
            "compactMarkdownPath": str(markdown_path),
            "compactStatus": read_json_file(compact_path) if compact_path.is_file() else None,
            "markdown": safe_read_text(markdown_path, max_chars=max_chars) if markdown_path.is_file() else None,
        }
        return text_result(payload)

    def tool_run_static_chain_diagnostics(self, arguments: dict[str, Any]) -> dict[str, Any]:
        timeout = int(arguments.get("timeoutSeconds", 300))
        specs = [
            ("actor-chain-no-debug-status", "scripts/riftreader-actor-chain-no-debug-status.cmd", ["--json"]),
            ("static-field-access-matrix", "scripts/riftreader-static-field-access-matrix.cmd", ["--json"]),
            ("family-neighborhood-analysis", "scripts/riftreader-family-neighborhood-analysis.cmd", ["--json"]),
        ]
        payload: dict[str, Any] = {"generatedAtUtc": utc_iso(), "repo": str(self.repo), "commands": [], "results": {}}
        for label, script, script_args in specs:
            envelope = run_cmd_script(self.repo, script, script_args, timeout=timeout, ok_codes={0, 2})
            command_summary = {k: v for k, v in envelope.items() if k not in ("stdout", "stderr")}
            payload["commands"].append({"label": label, **command_summary})
            try:
                payload["results"][label] = json.loads(envelope["stdout"]) if envelope["stdout"].strip() else None
            except Exception as exc:
                payload["results"][label] = {
                    "parseError": f"{type(exc).__name__}: {exc}",
                    "stdout": compact_text(envelope["stdout"]),
                    "stderr": compact_text(envelope["stderr"]),
                }
        summary_path = write_artifact(self.repo, "static-chain-diagnostics", payload)
        payload["mcpSummaryJson"] = str(summary_path)
        return text_result(payload)

    def tool_publish_chatgpt_snapshot(self, arguments: dict[str, Any]) -> dict[str, Any]:
        push = bool(arguments.get("push", True))
        wait = int(arguments.get("waitUrlFileSeconds", 90))
        timeout = int(arguments.get("timeoutSeconds", 300))
        script_args = ["--capture", "--write", "--wait-url-file-seconds", str(wait)]
        if push:
            script_args.append("--push")
        envelope = run_cmd_script(
            self.repo,
            "scripts/riftreader-publish-chatgpt-snapshot.cmd",
            script_args,
            timeout=timeout,
            ok_codes={0, 2},
        )
        payload = {
            "generatedAtUtc": utc_iso(),
            "ok": envelope["ok"],
            "exitCode": envelope["exitCode"],
            "timedOut": envelope["timedOut"],
            "stdout": compact_text(envelope["stdout"]),
            "stderr": compact_text(envelope["stderr"]),
        }
        summary_path = write_artifact(self.repo, "publish-chatgpt-snapshot", payload)
        payload["mcpSummaryJson"] = str(summary_path)
        return text_result(payload, is_error=not envelope["ok"])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if name not in self.tools:
            raise McpError(f"Unknown tool: {name}", code=-32602)
        return self.tools[name](arguments or {})

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        jsonrpc = request.get("jsonrpc")
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params") if isinstance(request.get("params"), dict) else {}

        if jsonrpc != "2.0":
            return self.error_response(request_id, -32600, "Invalid JSON-RPC version")

        if request_id is None and isinstance(method, str) and method.startswith("notifications/"):
            return None

        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "riftreader-mcp", "version": VERSION},
                    },
                }
            if method == "ping":
                return {"jsonrpc": "2.0", "id": request_id, "result": {}}
            if method == "tools/list":
                return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": self.tool_definitions()}}
            if method == "tools/call":
                name = str(params.get("name") or "")
                arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
                result = self.call_tool(name, arguments)
                return {"jsonrpc": "2.0", "id": request_id, "result": result}
            return self.error_response(request_id, -32601, f"Method not found: {method}")
        except McpError as exc:
            return self.error_response(request_id, exc.code, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self.error_response(request_id, -32000, f"{type(exc).__name__}: {exc}")

    @staticmethod
    def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def run_stdio(server: RiftReaderMcpServer) -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                response = server.error_response(None, -32600, "Request must be a JSON object")
            else:
                response = server.handle_request(request)
        except Exception as exc:  # noqa: BLE001
            response = server.error_response(None, -32700, f"Parse error: {type(exc).__name__}: {exc}")
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


def run_self_test(repo: Path) -> dict[str, Any]:
    server = RiftReaderMcpServer(repo)
    init = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    tools = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    git_state = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "riftreader.get_git_state", "arguments": {}},
        }
    )
    ok = (
        isinstance(init, dict)
        and isinstance(tools, dict)
        and isinstance(git_state, dict)
        and "result" in init
        and "result" in tools
        and "result" in git_state
    )
    return {"version": VERSION, "status": "passed" if ok else "failed", "toolCount": len(server.tool_definitions())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RiftReader-specific MCP stdio server")
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--list-tools", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo = repo_root(args.repo)
    server = RiftReaderMcpServer(repo)

    if args.self_test:
        result = run_self_test(repo)
        print(json.dumps(result, indent=2 if args.json else None))
        return 0 if result.get("status") == "passed" else 1
    if args.list_tools:
        result = {"version": VERSION, "tools": server.tool_definitions()}
        print(json.dumps(result, indent=2 if args.json else None))
        return 0

    return run_stdio(server)


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
