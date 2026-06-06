#!/usr/bin/env python3
# Version: riftreader-mcp-openai-tunnel-status-v0.1.1
# Purpose: Secret-safe readiness/profile helper for ChatGPT Web/Desktop via OpenAI Secure MCP Tunnel.

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from tools.riftreader_mcp.config import default_repo_root, load_config, runtime_root
from tools.riftreader_mcp.logging_util import utc_iso


VERSION = "riftreader-mcp-openai-tunnel-status-v0.1.1"
TUNNEL_ID_RE = re.compile(r"^tunnel_[0-9a-f]{32}$")
DEFAULT_PROFILE_NAME = "riftreader-chatgpt.yaml"


def _fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


def _runtime_dir(repo: Path) -> Path:
    return runtime_root(repo) / "openai-tunnel"


def auth_header_path(repo: Path) -> Path:
    return _runtime_dir(repo) / "mcp-authorization-header.txt"


def profile_path(repo: Path) -> Path:
    return _runtime_dir(repo) / DEFAULT_PROFILE_NAME


def health_url_file_path(repo: Path) -> Path:
    return _runtime_dir(repo) / "tunnel-client-health.url"


def _as_posix(path: Path) -> str:
    return path.resolve().as_posix()


def _find_tunnel_client() -> str | None:
    override = os.environ.get("TUNNEL_CLIENT_EXE")
    if override and Path(override).exists():
        return str(Path(override).resolve())
    return shutil.which("tunnel-client") or shutil.which("tunnel-client.exe")


def _run(args: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def _tunnel_client_version(exe: str | None) -> dict[str, Any]:
    if not exe:
        return {"found": False, "path": None, "version": None, "exitCode": None}
    result = _run([exe, "--version"])
    stdout = (result.stdout or "").strip() if result else ""
    stderr = (result.stderr or "").strip() if result else ""
    return {
        "found": True,
        "path": exe,
        "version": stdout or stderr or None,
        "exitCode": result.returncode if result else None,
    }


def _request_health(repo: Path, *, timeout: float = 3.0) -> dict[str, Any]:
    try:
        cfg = load_config(repo=repo)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": "config_unavailable", "error": f"{type(exc).__name__}: {exc}"}
    if cfg.require_auth and not cfg.token:
        return {"ok": False, "status": "token_missing"}
    req = urllib.request.Request(f"http://{cfg.host}:{cfg.port}/health", method="GET")
    req.add_header("Authorization", f"Bearer {cfg.token}")
    req.add_header("User-Agent", "RiftReader-OpenAI-Tunnel-Readiness/0.1")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - local-only operator readiness probe.
            payload = json.loads(response.read().decode("utf-8"))
            return {"ok": int(response.status) == 200, "statusCode": int(response.status), "serverStatus": payload.get("status")}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "statusCode": int(exc.code), "serverStatus": "http_error"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": "unreachable", "error": f"{type(exc).__name__}: {exc}"}


def write_profile(repo: Path) -> dict[str, Any]:
    cfg = load_config(repo=repo)
    out_dir = _runtime_dir(repo)
    out_dir.mkdir(parents=True, exist_ok=True)
    header_path = auth_header_path(repo)
    profile = profile_path(repo)
    health_file = health_url_file_path(repo)
    if not cfg.token:
        return {
            "ok": False,
            "status": "token_missing",
            "message": "Local MCP token is missing; run scripts\\start_mcp_local_background.cmd once to initialize local config.",
        }
    header_path.write_text(f"Bearer {cfg.token}", encoding="utf-8")
    profile.write_text(
        "# RiftReader ChatGPT Web/Desktop MCP via OpenAI Secure MCP Tunnel.\n"
        "# Local-only generated profile. Do not commit this file.\n"
        "config_version: 1\n"
        "control_plane:\n"
        "  base_url: https://api.openai.com\n"
        "  tunnel_id: env:CONTROL_PLANE_TUNNEL_ID\n"
        "  api_key: env:CONTROL_PLANE_API_KEY\n"
        "health:\n"
        "  listen_addr: 127.0.0.1:0\n"
        f"  url_file: {_as_posix(health_file)}\n"
        "  admin_ui:\n"
        "    open_browser: false\n"
        "mcp:\n"
        "  server_urls:\n"
        "    - channel: main\n"
        f"      url: http://{cfg.host}:{cfg.port}/mcp\n"
        "  extra_headers:\n"
        f"    Authorization: file:{_as_posix(header_path)}\n"
        "  discovery_extra_headers:\n"
        f"    Authorization: file:{_as_posix(header_path)}\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "status": "written",
        "profilePath": str(profile),
        "authHeaderPath": str(header_path),
        "healthUrlFile": str(health_file),
        "tokenPrinted": False,
    }


def build_openai_tunnel_status(repo: str | Path | None = None, *, ensure_profile: bool = False) -> dict[str, Any]:
    repo_path = Path(repo or default_repo_root()).resolve()
    cfg = load_config(repo=repo_path)
    exe = _find_tunnel_client()
    client = _tunnel_client_version(exe)
    tunnel_id = os.environ.get("CONTROL_PLANE_TUNNEL_ID")
    api_key = os.environ.get("CONTROL_PLANE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    local_health = _request_health(repo_path)
    write_result = write_profile(repo_path) if ensure_profile else None
    profile = profile_path(repo_path)
    header_path = auth_header_path(repo_path)
    health_file = health_url_file_path(repo_path)
    health_url = health_file.read_text(encoding="utf-8", errors="replace").strip() if health_file.is_file() else None
    blockers: list[str] = []
    if not client["found"]:
        blockers.append("Install tunnel-client or set TUNNEL_CLIENT_EXE to its full path.")
    if not tunnel_id:
        blockers.append("Set CONTROL_PLANE_TUNNEL_ID to the OpenAI tunnel id for this ChatGPT app.")
    elif not TUNNEL_ID_RE.match(tunnel_id):
        blockers.append("CONTROL_PLANE_TUNNEL_ID does not match expected tunnel_ plus 32 lowercase hex characters.")
    if not api_key:
        blockers.append("Set CONTROL_PLANE_API_KEY to a runtime key with Tunnels Read + Use.")
    if not cfg.token:
        blockers.append("Initialize the local MCP bearer token with scripts\\start_mcp_local_background.cmd.")
    if not profile.is_file():
        blockers.append("Run scripts\\prepare_chatgpt_mcp_tunnel_profile.cmd to write the local tunnel-client profile.")
    if not header_path.is_file():
        blockers.append("Run scripts\\prepare_chatgpt_mcp_tunnel_profile.cmd to write the local MCP auth-header file.")
    if not local_health.get("ok"):
        blockers.append("Start the local MCP server with scripts\\start_mcp_local_background.cmd before running tunnel-client.")
    status = "ready_for_doctor" if not blockers else "blocked"
    return {
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "repo": str(repo_path),
        "preferredChatGptConnectionMode": "openai_secure_mcp_tunnel",
        "whyPreferred": "Keeps the local MCP server private and uses outbound-only HTTPS to OpenAI instead of exposing the MCP endpoint publicly.",
        "tunnelClient": client,
        "controlPlaneTunnelIdConfigured": bool(tunnel_id),
        "controlPlaneTunnelIdLooksValid": bool(tunnel_id and TUNNEL_ID_RE.match(tunnel_id)),
        "controlPlaneApiKeyConfigured": bool(api_key),
        "controlPlaneApiKeyFingerprint": _fingerprint(api_key),
        "localMcpServer": local_health,
        "localMcpUrl": f"http://{cfg.host}:{cfg.port}/mcp",
        "profilePath": str(profile),
        "profileExists": profile.is_file(),
        "authHeaderPath": str(header_path),
        "authHeaderExists": header_path.is_file(),
        "healthUrlFile": str(health_file),
        "tunnelClientHealthUrl": health_url,
        "writeProfileResult": write_result,
        "blockers": blockers,
        "commands": [
            "cd /d \"C:\\RIFT MODDING\\RiftReader\"",
            "scripts\\start_mcp_local_background.cmd",
            "set CONTROL_PLANE_TUNNEL_ID=tunnel_0123456789abcdef0123456789abcdef",
            "set CONTROL_PLANE_API_KEY=<runtime key with Tunnels Read + Use>",
            "scripts\\prepare_chatgpt_mcp_tunnel_profile.cmd",
            "tunnel-client doctor --profile-file \".riftreader-local\\mcp\\openai-tunnel\\riftreader-chatgpt.yaml\" --explain",
            "tunnel-client run --profile-file \".riftreader-local\\mcp\\openai-tunnel\\riftreader-chatgpt.yaml\"",
        ],
        "tokenPrinted": False,
        "tokenMaterialRead": bool(cfg.token),
    }


def write_summary(repo: Path, payload: dict[str, Any]) -> Path:
    out_dir = _runtime_dir(repo)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "status.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check/prep ChatGPT Web/Desktop MCP via OpenAI Secure MCP Tunnel.")
    parser.add_argument("--repo", default=str(default_repo_root()))
    parser.add_argument("--write-profile", action="store_true")
    parser.add_argument("--write-status", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    payload = build_openai_tunnel_status(repo, ensure_profile=args.write_profile)
    if args.write_status:
        payload["summaryJson"] = str(write_summary(repo, payload))
    print(json.dumps(payload, indent=2))
    print("END_RIFTREADER_CHATGPT_MCP_TUNNEL_STATUS")
    return 0 if payload.get("status") == "ready_for_doctor" else 2


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
