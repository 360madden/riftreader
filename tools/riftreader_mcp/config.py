#!/usr/bin/env python3
# Version: riftreader-mcp-http-config-v0.1.1
# Purpose: Local, secret-safe configuration helpers for the RiftReader HTTP MCP adapter.

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VERSION = "riftreader-mcp-http-v0.1.2"
PROTOCOL_VERSION = "2025-06-18"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_ENABLED_TOOLS = ("health", "get_repo_status", "get_latest_handoff")
DEFAULT_ALLOWED_ORIGINS = ("https://chatgpt.com", "https://chat.openai.com", "https://platform.openai.com")
TOKEN_ENV_VAR = "RIFTREADER_MCP_TOKEN"


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def local_config_path(repo_root: Path) -> Path:
    return repo_root / ".riftreader-local" / "mcp" / "config.json"


def runtime_root(repo_root: Path) -> Path:
    return repo_root / ".riftreader-local" / "mcp"


@dataclass(frozen=True)
class McpHttpConfig:
    repo_root: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    require_auth: bool = True
    expose_repo_root: bool = True
    enabled_tools: tuple[str, ...] = DEFAULT_ENABLED_TOOLS
    validate_origin: bool = True
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS
    token: str | None = None
    token_source: str = "missing"

    @property
    def runtime_root(self) -> Path:
        return runtime_root(self.repo_root)

    @property
    def log_root(self) -> Path:
        return self.runtime_root / "logs"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config JSON must be an object: {path}")
    return payload


def _bool_value(payload: dict[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _enabled_tools(payload: dict[str, Any]) -> tuple[str, ...]:
    raw = payload.get("enabledTools", DEFAULT_ENABLED_TOOLS)
    if not isinstance(raw, list | tuple):
        return DEFAULT_ENABLED_TOOLS
    tools = tuple(str(item) for item in raw if str(item).strip())
    return tools or DEFAULT_ENABLED_TOOLS


def _string_tuple(payload: dict[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = payload.get(key, default)
    if not isinstance(raw, list | tuple):
        return default
    values = tuple(str(item).strip().rstrip("/") for item in raw if str(item).strip())
    return values or default


def load_config(
    *,
    repo: str | Path | None = None,
    config_path: str | Path | None = None,
    host: str | None = None,
    port: int | None = None,
    token: str | None = None,
) -> McpHttpConfig:
    repo_root = Path(repo or default_repo_root()).resolve()
    if not (repo_root / ".git").exists():
        raise ValueError(f"Repo .git directory not found: {repo_root}")

    config_file = Path(config_path).resolve() if config_path else local_config_path(repo_root)
    payload = _read_json(config_file)

    env_token = os.environ.get(TOKEN_ENV_VAR)
    config_token = payload.get("token") if isinstance(payload.get("token"), str) else None
    selected_token = token or env_token or config_token
    token_source = "argument" if token else ("environment" if env_token else ("local-config" if config_token else "missing"))

    return McpHttpConfig(
        repo_root=repo_root,
        host=host or str(payload.get("host") or DEFAULT_HOST),
        port=int(port or payload.get("port") or DEFAULT_PORT),
        require_auth=_bool_value(payload, "requireAuth", True),
        expose_repo_root=_bool_value(payload, "exposeRepoRoot", True),
        enabled_tools=_enabled_tools(payload),
        validate_origin=_bool_value(payload, "validateOrigin", True),
        allowed_origins=_string_tuple(payload, "allowedOrigins", DEFAULT_ALLOWED_ORIGINS),
        token=selected_token,
        token_source=token_source,
    )


def ensure_local_config(repo: str | Path | None = None, *, force: bool = False) -> dict[str, Any]:
    repo_root = Path(repo or default_repo_root()).resolve()
    path = local_config_path(repo_root)
    if path.exists() and not force:
        cfg = load_config(repo=repo_root)
        return {
            "status": "exists",
            "path": str(path),
            "host": cfg.host,
            "port": cfg.port,
            "requireAuth": cfg.require_auth,
            "enabledTools": list(cfg.enabled_tools),
            "validateOrigin": cfg.validate_origin,
            "allowedOrigins": list(cfg.allowed_origins),
            "tokenSource": cfg.token_source,
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": VERSION,
        "purpose": "Local-only RiftReader MCP HTTP config. Do not commit this file.",
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
        "requireAuth": True,
        "exposeRepoRoot": True,
        "enabledTools": list(DEFAULT_ENABLED_TOOLS),
        "validateOrigin": True,
        "allowedOrigins": list(DEFAULT_ALLOWED_ORIGINS),
        "token": secrets.token_urlsafe(32),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "created" if not force else "replaced",
        "path": str(path),
        "host": payload["host"],
        "port": payload["port"],
        "requireAuth": payload["requireAuth"],
        "enabledTools": payload["enabledTools"],
        "validateOrigin": payload["validateOrigin"],
        "allowedOrigins": payload["allowedOrigins"],
        "tokenSource": "local-config",
    }


# END_OF_SCRIPT_MARKER
