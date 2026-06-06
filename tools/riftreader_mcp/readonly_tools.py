#!/usr/bin/env python3
# Version: riftreader-mcp-http-readonly-tools-v0.1.1
# Purpose: Safe read-only RiftReader MCP tool implementations for HTTP/tunnel exposure.

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from tools.riftreader_mcp.auth import token_fingerprint
from tools.riftreader_mcp.config import McpHttpConfig, VERSION
from tools.riftreader_mcp.logging_util import utc_iso


class ReadOnlyToolError(RuntimeError):
    pass


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _run_git(repo: Path, args: list[str], *, timeout: int = 30) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {
        "args": ["git", *args],
        "exitCode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _porcelain_paths(stdout: str) -> list[str]:
    paths: list[str] = []
    for raw in stdout.splitlines():
        if not raw.strip() or raw.startswith("## "):
            continue
        path = raw[3:] if len(raw) > 3 else raw.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(_normalize_path(path))
    return sorted(paths)


def _read_text(path: Path, *, max_chars: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... truncated to {max_chars} characters ..."


def _known_handoff_candidates(repo: Path) -> list[Path]:
    roots = [
        repo / "docs" / "HANDOFF.md",
        repo / "handoffs" / "current" / "RIFTREADER_CURRENT_HANDOFF.md",
        repo / "handoffs" / "current" / "RIFTREADER_CURRENT_HANDOFF.json",
        repo / ".riftreader-local" / "mcp" / "latest" / "summary.json",
        repo / ".riftreader-local" / "mcp" / "latest" / "operator-next-steps.md",
    ]
    for folder in (repo / "docs" / "handoffs", repo / "handoffs" / "current"):
        if folder.is_dir():
            roots.extend(item for item in folder.rglob("*") if item.suffix.lower() in {".md", ".json"})
    return [item for item in roots if item.is_file()]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        }


class RiftReaderReadOnlyTools:
    def __init__(self, config: McpHttpConfig) -> None:
        self.config = config
        self.repo = config.repo_root
        all_tools = {
            "health": ToolSpec(
                "health",
                "RiftReader MCP health",
                "Use this when ChatGPT needs to verify the RiftReader MCP server is reachable and see its read-only safety boundaries.",
                {"type": "object", "properties": {}, "additionalProperties": False},
                {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "status": {"type": "string"},
                        "version": {"type": "string"},
                        "repoName": {"type": "string"},
                        "repoRoot": {"type": ["string", "null"]},
                        "toolCount": {"type": "integer"},
                        "enabledTools": {"type": "array", "items": {"type": "string"}},
                        "authRequired": {"type": "boolean"},
                        "tokenConfigured": {"type": "boolean"},
                        "generatedAtUtc": {"type": "string"},
                    },
                    "required": ["ok", "status", "version", "repoName", "toolCount", "enabledTools", "generatedAtUtc"],
                    "additionalProperties": True,
                },
                self.health,
            ),
            "get_repo_status": ToolSpec(
                "get_repo_status",
                "RiftReader repo status",
                "Use this when ChatGPT needs the current local RiftReader Git branch, HEAD commit, dirty state, and changed-file summary. This runs fixed read-only git commands only; it cannot stage, commit, push, or read arbitrary files.",
                {"type": "object", "properties": {}, "additionalProperties": False},
                {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "repoName": {"type": "string"},
                        "repoRoot": {"type": ["string", "null"]},
                        "branch": {"type": "string"},
                        "headCommit": {"type": ["string", "null"]},
                        "headShort": {"type": ["string", "null"]},
                        "headSubject": {"type": ["string", "null"]},
                        "dirty": {"type": "boolean"},
                        "changedFileCount": {"type": "integer"},
                        "changedFiles": {"type": "array", "items": {"type": "string"}},
                        "statusShortBranch": {"type": ["string", "null"]},
                        "generatedAtUtc": {"type": "string"},
                    },
                    "required": ["ok", "repoName", "branch", "dirty", "changedFileCount", "changedFiles", "generatedAtUtc"],
                    "additionalProperties": True,
                },
                self.get_repo_status,
            ),
            "get_latest_handoff": ToolSpec(
                "get_latest_handoff",
                "RiftReader latest handoff",
                "Use this when ChatGPT needs the newest bounded RiftReader handoff/status packet from known repo-local locations. This does not accept arbitrary paths and handles missing files cleanly.",
                {
                    "type": "object",
                    "properties": {
                        "maxChars": {
                            "type": "integer",
                            "minimum": 1000,
                            "maximum": 120000,
                            "default": 40000,
                            "description": "Maximum characters to return from text handoff files.",
                        }
                    },
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "status": {"type": "string", "enum": ["present", "missing"]},
                        "message": {"type": "string"},
                        "path": {"type": "string"},
                        "relativePath": {"type": "string"},
                        "lastWriteTimeUtc": {"type": "string"},
                        "content": {},
                        "generatedAtUtc": {"type": "string"},
                    },
                    "required": ["ok", "status", "generatedAtUtc"],
                    "additionalProperties": True,
                },
                self.get_latest_handoff,
            ),
        }
        self.tools = {name: all_tools[name] for name in config.enabled_tools if name in all_tools}

    def definitions(self) -> list[dict[str, Any]]:
        return [tool.definition() for tool in self.tools.values()]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if name not in self.tools:
            raise ReadOnlyToolError(f"Tool is not enabled or does not exist: {name}")
        return self.tools[name].handler(arguments or {})

    def health(self, arguments: dict[str, Any]) -> dict[str, Any]:
        del arguments
        return {
            "ok": True,
            "status": "ok",
            "version": VERSION,
            "repoName": self.repo.name,
            "repoRoot": str(self.repo) if self.config.expose_repo_root else None,
            "repoRootExposedIntentionally": bool(self.config.expose_repo_root),
            "toolCount": len(self.tools),
            "enabledTools": sorted(self.tools),
            "authRequired": self.config.require_auth,
            "tokenConfigured": bool(self.config.token),
            "tokenFingerprint": token_fingerprint(self.config.token),
            "generatedAtUtc": utc_iso(),
        }

    def get_repo_status(self, arguments: dict[str, Any]) -> dict[str, Any]:
        del arguments
        branch = _run_git(self.repo, ["branch", "--show-current"])
        head = _run_git(self.repo, ["log", "-1", "--pretty=%H%n%h%n%s"])
        status = _run_git(self.repo, ["status", "--short", "--branch"])
        changed = _porcelain_paths(status["stdout"])
        head_lines = [line for line in head["stdout"].splitlines() if line.strip()]
        return {
            "ok": branch["ok"] and head["ok"] and status["ok"],
            "repoName": self.repo.name,
            "repoRoot": str(self.repo) if self.config.expose_repo_root else None,
            "branch": branch["stdout"].strip(),
            "headCommit": head_lines[0] if len(head_lines) > 0 else None,
            "headShort": head_lines[1] if len(head_lines) > 1 else None,
            "headSubject": head_lines[2] if len(head_lines) > 2 else None,
            "dirty": bool(changed),
            "changedFileCount": len(changed),
            "changedFiles": changed[:200],
            "statusShortBranch": status["stdout"].splitlines()[0] if status["stdout"].splitlines() else None,
            "generatedAtUtc": utc_iso(),
        }

    def get_latest_handoff(self, arguments: dict[str, Any]) -> dict[str, Any]:
        max_chars = int(arguments.get("maxChars", 40000))
        candidates = _known_handoff_candidates(self.repo)
        if not candidates:
            return {
                "ok": True,
                "status": "missing",
                "message": "No handoff/status packet found in known repo-local locations.",
                "searchedLocations": [
                    "docs/HANDOFF.md",
                    "docs/handoffs/**/*.{md,json}",
                    "handoffs/current/**/*.{md,json}",
                    ".riftreader-local/mcp/latest/*",
                ],
                "generatedAtUtc": utc_iso(),
            }
        latest = max(candidates, key=lambda item: item.stat().st_mtime)
        content: Any
        if latest.suffix.lower() == ".json":
            try:
                content = json.loads(latest.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                content = _read_text(latest, max_chars=max_chars)
        else:
            content = _read_text(latest, max_chars=max_chars)
        return {
            "ok": True,
            "status": "present",
            "path": str(latest),
            "relativePath": _normalize_path(str(latest.relative_to(self.repo))),
            "lastWriteTimeUtc": utc_iso_from_mtime(latest.stat().st_mtime),
            "content": content,
            "generatedAtUtc": utc_iso(),
        }


def utc_iso_from_mtime(value: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# END_OF_SCRIPT_MARKER
