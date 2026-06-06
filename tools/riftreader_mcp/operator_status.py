#!/usr/bin/env python3
# Version: riftreader-mcp-http-operator-status-v0.1.4
# Purpose: Print and write an operator-facing status packet for the 360madden MCP lane.

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.riftreader_mcp.cloudflared_status import build_cloudflared_status
from tools.riftreader_mcp.config import ADAPTER_KIND, ADAPTER_PURPOSE, default_repo_root, load_config, local_config_path, runtime_root
from tools.riftreader_mcp.logging_util import utc_iso
from tools.riftreader_mcp.openai_tunnel_status import build_openai_tunnel_status
from tools.riftreader_mcp.readonly_tools import RiftReaderReadOnlyTools


def latest_file(root: Path, pattern: str) -> Path | None:
    if not root.is_dir():
        return None
    files = list(root.rglob(pattern))
    return max(files, key=lambda item: item.stat().st_mtime) if files else None


def read_json_or_none(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def latest_json_matching(root: Path, pattern: str, key: str) -> tuple[Path | None, dict[str, Any] | None]:
    if not root.is_dir():
        return None, None
    files = sorted(root.rglob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in files:
        payload = read_json_or_none(path)
        if isinstance(payload, dict) and isinstance(payload.get(key), dict):
            return path, payload
    return None, None


def build_status(repo: Path) -> dict[str, Any]:
    cfg_path = local_config_path(repo)
    config = load_config(repo=repo) if cfg_path.exists() else load_config(repo=repo, token="status-placeholder-token")
    tools = RiftReaderReadOnlyTools(config)
    repo_status = tools.get_repo_status({})
    latest_handoff = tools.get_latest_handoff({"maxChars": 2000})
    latest_smoke = latest_file(runtime_root(repo) / "smoke", "summary.json")
    latest_smoke_payload = read_json_or_none(latest_smoke)
    latest_public_smoke, latest_public_smoke_payload = latest_json_matching(
        runtime_root(repo) / "smoke", "summary.json", "public"
    )
    latest_domain = latest_file(runtime_root(repo) / "domain-preflight", "summary.json")
    latest_domain_payload = read_json_or_none(latest_domain)
    latest_connector = (
        latest_file(runtime_root(repo) / "cloudflared", "service-status-*.json")
        or latest_file(runtime_root(repo) / "cloudflared", "dedupe-*.json")
        or latest_file(runtime_root(repo) / "cloudflared", "detached-*.json")
        or latest_file(runtime_root(repo) / "cloudflared", "connector-install-*.json")
    )
    latest_connector_payload = read_json_or_none(latest_connector)
    latest_dedupe = latest_file(runtime_root(repo) / "cloudflared", "dedupe-*.json")
    latest_dedupe_payload = read_json_or_none(latest_dedupe)
    latest_log = latest_file(runtime_root(repo) / "logs", "*.jsonl")
    cloudflared_runtime = build_cloudflared_status(repo)
    openai_tunnel_runtime = build_openai_tunnel_status(repo, ensure_profile=False)
    ready_local = cfg_path.exists() and config.require_auth and bool(config.token)
    public_ready = bool(
        latest_public_smoke_payload
        and latest_public_smoke_payload.get("status") == "passed"
        and latest_public_smoke_payload["public"].get("status") == "passed"
    )
    domain_ready = bool(latest_domain_payload and latest_domain_payload.get("status") == "passed")
    cloudflared_running = cloudflared_runtime.get("status") in {"service_only", "duplicate_processes", "detached_only"}
    connector_started = cloudflared_running or bool(
        latest_connector_payload
        and latest_connector_payload.get("status")
        in {"service_only", "deduped_service_only", "started", "foreground_connector_started", "service_installed"}
    )
    known_risks = [
        "A bearer token must be copied only through trusted operator setup paths; it is intentionally not printed by smoke tests.",
    ]
    if "ahead" in str(repo_status.get("statusShortBranch", "")):
        known_risks.append("The repo branch is ahead of origin; no push was performed by this workflow.")
    if cloudflared_runtime.get("status") == "duplicate_processes":
        known_risks.append("Cloudflared has duplicate local processes; keep the Windows service and stop detached duplicates.")
    elif cloudflared_runtime.get("status") == "detached_only":
        known_risks.append("Cloudflared is running as a detached user process; install/run it as a Windows service for durable restart behavior.")
    elif cloudflared_runtime.get("status") in {"not_running", "service_configured_not_running"}:
        known_risks.append("Cloudflared is not confirmed running locally; public MCP routing may fail after connector timeout.")
    elif cloudflared_runtime.get("status") == "service_only":
        known_risks.append("Cloudflare dashboard may briefly show a stale disconnected connector after duplicate-process cleanup.")

    return {
        "version": "riftreader-mcp-http-operator-status-v0.1.4",
        "generatedAtUtc": utc_iso(),
        "repo": str(repo),
        "whatChanged": [
            "Added a separate read-only HTTP MCP adapter for ChatGPT Web/Desktop local repo access.",
            "Added token-gated auth, Origin validation, explicit tool allowlist, structured tool results, JSONL logging, local/public smoke tests, operator status output, and Cloudflare/OpenAI tunnel docs.",
            "Kept the existing stdio MCP adapter intact; this slice does not add write tools or live-game integrations.",
        ],
        "filesCreatedOrModified": [
            "tools/riftreader_mcp/config.py",
            "tools/riftreader_mcp/auth.py",
            "tools/riftreader_mcp/logging_util.py",
            "tools/riftreader_mcp/readonly_tools.py",
            "tools/riftreader_mcp/http_server.py",
            "tools/riftreader_mcp/smoke_http.py",
            "tools/riftreader_mcp/domain_preflight.py",
            "tools/riftreader_mcp/start_cloudflared_connector.py",
            "tools/riftreader_mcp/cloudflared_status.py",
            "tools/riftreader_mcp/openai_tunnel_status.py",
            "tools/riftreader_mcp/operator_status.py",
            "tools/riftreader_mcp/mcp-http-config.example.json",
            "tools/riftreader_mcp/cloudflare-tunnel-360madden.example.yml",
            "scripts/check_mcp_domain_readiness.cmd",
            "scripts/check_mcp_cloudflared_service.cmd",
            "scripts/check_chatgpt_mcp_tunnel_readiness.cmd",
            "scripts/prepare_chatgpt_mcp_tunnel_profile.cmd",
            "scripts/start_chatgpt_mcp_tunnel.cmd",
            "scripts/start_mcp_local.cmd",
            "scripts/test_mcp_local.cmd",
            "scripts/print_mcp_operator_status.cmd",
            "docs/mcp-360madden-local-setup.md",
            "docs/mcp-360madden-operator-runbook.md",
            "docs/cloudflare-tunnel-360madden.md",
            "docs/chatgpt-web-mcp-secure-tunnel.md",
        ],
        "commandsForJoey": [
            "cd /d \"C:\\RIFT MODDING\\RiftReader\"",
            "scripts\\check_mcp_domain_readiness.cmd",
            "scripts\\test_mcp_local.cmd",
            "scripts\\start_mcp_local.cmd",
            "scripts\\prepare_chatgpt_mcp_tunnel_profile.cmd",
            "scripts\\check_chatgpt_mcp_tunnel_readiness.cmd",
            "scripts\\check_mcp_cloudflared_service.cmd",
            "scripts\\print_mcp_operator_status.cmd",
            "python -m tools.riftreader_mcp.smoke_http --repo \"C:\\RIFT MODDING\\RiftReader\" --public-url https://mcp.360madden.com --json",
        ],
        "expectedOutputMarkers": [
            "PASS",
            "BLOCKED_DOMAIN_SETUP",
            "END_RIFTREADER_MCP_DOMAIN_PREFLIGHT",
            "END_RIFTREADER_MCP_HTTP_SMOKE",
            "END_RIFTREADER_MCP_CLOUDFLARED_STATUS",
            "END_RIFTREADER_CHATGPT_MCP_TUNNEL_STATUS",
            "END_RIFTREADER_MCP_LOCAL_TEST",
            "END_RIFTREADER_MCP_LOCAL_STARTUP_BEGIN_SERVER",
            "END_RIFTREADER_MCP_OPERATOR_STATUS_CMD",
        ],
        "localConfigPath": str(cfg_path),
        "localConfigExists": cfg_path.exists(),
        "localServerUrl": f"http://{config.host}:{config.port}",
        "localMcpUrl": f"http://{config.host}:{config.port}/mcp",
        "publicMcpUrl": "https://mcp.360madden.com/mcp",
        "adapterKind": ADAPTER_KIND,
        "adapterPurpose": ADAPTER_PURPOSE,
        "codexStdioAdapter": False,
        "preferredChatGptMcpMode": "openai_secure_mcp_tunnel",
        "chatGptMcpFallbackMode": "cloudflare_public_hostname",
        "authRequired": config.require_auth,
        "tokenConfigured": ready_local,
        "enabledTools": list(config.enabled_tools),
        "originValidationEnabled": config.validate_origin,
        "allowedOrigins": list(config.allowed_origins),
        "mcpProtocolVersion": "2025-06-18",
        "repoStatus": repo_status,
        "latestHandoff": {k: latest_handoff.get(k) for k in ("status", "relativePath", "lastWriteTimeUtc")},
        "latestSmokeSummary": str(latest_smoke) if latest_smoke else None,
        "latestSmokeStatus": latest_smoke_payload.get("status") if latest_smoke_payload else None,
        "latestPublicSmokeSummary": str(latest_public_smoke) if latest_public_smoke else None,
        "latestPublicSmokeStatus": (
            latest_public_smoke_payload.get("public", {}).get("status") if latest_public_smoke_payload else None
        ),
        "latestDomainPreflightSummary": str(latest_domain or ""),
        "latestDomainPreflightStatus": latest_domain_payload.get("status") if latest_domain_payload else None,
        "latestConnectorSummary": str(latest_connector or ""),
        "latestConnectorStatus": latest_connector_payload.get("status") if latest_connector_payload else None,
        "latestDedupeSummary": str(latest_dedupe or ""),
        "latestDedupeStatus": latest_dedupe_payload.get("status") if latest_dedupe_payload else None,
        "cloudflaredRuntime": cloudflared_runtime,
        "cloudflaredRuntimeStatus": cloudflared_runtime.get("status"),
        "cloudflaredServiceRunning": cloudflared_runtime.get("service", {}).get("running"),
        "cloudflaredServicePid": cloudflared_runtime.get("service", {}).get("pid"),
        "cloudflaredProcessPids": cloudflared_runtime.get("processes", {}).get("pids"),
        "cloudflaredNonServicePids": cloudflared_runtime.get("processes", {}).get("nonServicePids"),
        "openaiSecureMcpTunnelRuntime": openai_tunnel_runtime,
        "openaiSecureMcpTunnelStatus": openai_tunnel_runtime.get("status"),
        "openaiSecureMcpTunnelBlockers": openai_tunnel_runtime.get("blockers"),
        "chatgptMcpTunnelProfileReadyForDoctor": openai_tunnel_runtime.get("status") == "ready_for_doctor",
        "latestLog": str(latest_log) if latest_log else None,
        "domainReady": domain_ready,
        "connectorStarted": connector_started,
        "publicMcpReady": public_ready,
        "chatgptWebConnectionReady": False,
        "cloudflareTunnelReady": public_ready,
        "knownRisks": known_risks,
        "intentionallyNotImplementedYet": [
            "No write tools.",
            "No game/RIFT process attach or memory read.",
            "No x64dbg or Cheat Engine integration.",
            "No Cloudflare credential storage.",
            "No ChatGPT connector registration automation or bearer-token transfer into ChatGPT.",
            "No Git push.",
        ],
        "blockedOn": (
            [
                "Install/configure OpenAI tunnel-client prerequisites, set CONTROL_PLANE_TUNNEL_ID and CONTROL_PLANE_API_KEY, then run scripts\\start_chatgpt_mcp_tunnel.cmd.",
                "Create the ChatGPT custom app from ChatGPT Settings > Apps using Tunnel connection mode.",
            ]
            if openai_tunnel_runtime.get("status") != "ready_for_doctor"
            else ["Run tunnel-client, then create/scan the ChatGPT custom app using Tunnel connection mode."]
        ),
    }


def write_latest(repo: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = runtime_root(repo) / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "summary.json"
    next_steps = out_dir / "operator-next-steps.md"
    summary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if payload.get("publicMcpReady"):
        next_steps_text = (
            "# RiftReader MCP 360madden Operator Next Steps\n\n"
            "Current status: public MCP smoke passed for `https://mcp.360madden.com`, but the preferred ChatGPT Web/Desktop path is OpenAI Secure MCP Tunnel.\n\n"
            "1. Run `scripts\\check_mcp_cloudflared_service.cmd` after any restart and confirm `status: service_only`.\n"
            "2. Set `CONTROL_PLANE_TUNNEL_ID` and `CONTROL_PLANE_API_KEY` in the operator shell.\n"
            "3. Run `scripts\\prepare_chatgpt_mcp_tunnel_profile.cmd`.\n"
            "4. Run `scripts\\start_chatgpt_mcp_tunnel.cmd` and keep the daemon running.\n"
            "5. In ChatGPT Settings > Apps, create the custom app using Tunnel connection mode.\n"
            "6. Keep `.riftreader-local\\mcp\\config.json` private and never paste the token into ChatGPT, GitHub, docs, screenshots, or logs.\n\n"
            "Expected markers: `PASS`, `END_RIFTREADER_MCP_HTTP_SMOKE`, `END_RIFTREADER_MCP_CLOUDFLARED_STATUS`, `END_RIFTREADER_CHATGPT_MCP_TUNNEL_STATUS`.\n"
        )
    else:
        next_steps_text = (
            "# RiftReader MCP 360madden Operator Next Steps\n\n"
            "1. Run `scripts\\test_mcp_local.cmd` and confirm `PASS`.\n"
            "2. Run `scripts\\start_mcp_local.cmd` and leave the server running.\n"
            "3. Configure Cloudflare Tunnel public hostname `mcp.360madden.com` to `http://127.0.0.1:8765`.\n"
            "4. Run public verification from `docs\\cloudflare-tunnel-360madden.md`.\n"
            "5. For ChatGPT Web/Desktop, prefer `scripts\\prepare_chatgpt_mcp_tunnel_profile.cmd` plus OpenAI Secure MCP Tunnel instead of direct public bearer-token setup.\n\n"
            "Expected markers: `PASS`, `END_RIFTREADER_MCP_HTTP_SMOKE`, and `status: listening` from the server startup JSON.\n"
        )
    next_steps.write_text(next_steps_text, encoding="utf-8")
    return summary, next_steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print RiftReader MCP 360madden operator status.")
    parser.add_argument("--repo", default=str(default_repo_root()))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    payload = build_status(repo)
    if args.write:
        summary, next_steps = write_latest(repo, payload)
        payload["summaryJson"] = str(summary)
        payload["operatorNextSteps"] = str(next_steps)
    print(json.dumps(payload, indent=2))
    print("END_RIFTREADER_MCP_OPERATOR_STATUS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
