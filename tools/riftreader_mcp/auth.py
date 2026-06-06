#!/usr/bin/env python3
# Version: riftreader-mcp-http-auth-v0.1.0
# Purpose: Fail-closed bearer-token auth helpers for the RiftReader HTTP MCP adapter.

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from tools.riftreader_mcp.config import McpHttpConfig


AUTH_HEADER = "Authorization"
ALT_TOKEN_HEADER = "X-RiftReader-MCP-Token"


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    status: str
    message: str


def token_fingerprint(token: str | None) -> str | None:
    if not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def redact_secret(value: str | None) -> str:
    if not value:
        return ""
    fingerprint = token_fingerprint(value)
    return f"<redacted:{fingerprint}>"


def extract_token(headers: object) -> str | None:
    get = getattr(headers, "get", None)
    if not callable(get):
        return None
    bearer = str(get(AUTH_HEADER) or "")
    if bearer.lower().startswith("bearer "):
        return bearer[7:].strip()
    alt = str(get(ALT_TOKEN_HEADER) or "")
    return alt.strip() or None


def authorize(config: McpHttpConfig, headers: object) -> AuthResult:
    if not config.require_auth:
        return AuthResult(True, "auth_disabled", "Authentication disabled by local config.")
    if not config.token:
        return AuthResult(False, "auth_token_not_configured", "Token auth is required but no token is configured.")
    supplied = extract_token(headers)
    if not supplied:
        return AuthResult(False, "auth_missing", "Missing Authorization: Bearer token.")
    if supplied != config.token:
        return AuthResult(False, "auth_invalid", "Invalid bearer token.")
    return AuthResult(True, "auth_ok", "Authenticated.")


# END_OF_SCRIPT_MARKER
