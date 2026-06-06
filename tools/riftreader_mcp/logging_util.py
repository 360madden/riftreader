#!/usr/bin/env python3
# Version: riftreader-mcp-http-logging-v0.1.0
# Purpose: JSONL logging helpers that avoid writing secrets to RiftReader MCP logs.

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.riftreader_mcp.auth import redact_secret
from tools.riftreader_mcp.config import McpHttpConfig


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def log_path(config: McpHttpConfig) -> Path:
    config.log_root.mkdir(parents=True, exist_ok=True)
    return config.log_root / f"mcp-http-{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"


def redact_payload(value: Any, *, token: str | None) -> Any:
    if isinstance(value, dict):
        return {str(k): redact_payload(v, token=token) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_payload(item, token=token) for item in value]
    if isinstance(value, str) and token and token in value:
        return value.replace(token, redact_secret(token))
    return value


def write_log(config: McpHttpConfig, event: str, payload: dict[str, Any]) -> None:
    entry = {
        "timestampUtc": utc_iso(),
        "event": event,
        "payload": redact_payload(payload, token=config.token),
    }
    log_path(config).write_text("", encoding="utf-8") if not log_path(config).exists() else None
    with log_path(config).open("a", encoding="utf-8") as handle:
        handle.write(safe_json(entry) + "\n")


# END_OF_SCRIPT_MARKER
