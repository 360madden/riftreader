# RiftReader MCP 360madden Operator Runbook

Joey should not need to code. Use these commands and paste output if something fails.

## 1. Prove local server behavior

If the domain was only purchased and not configured yet, run this first:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\check_mcp_domain_readiness.cmd
```

`BLOCKED_DOMAIN_SETUP` is expected until Cloudflare DNS/Tunnel public hostname setup is complete.

Then run the local server smoke:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\test_mcp_local.cmd
```

Pass markers:

```text
PASS
END_RIFTREADER_MCP_HTTP_SMOKE
END_RIFTREADER_MCP_LOCAL_TEST
```

## 2. Start the local server

Preferred background start:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\start_mcp_local_background.cmd
```

Compatibility foreground start:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\start_mcp_local.cmd
```

If using foreground start, leave that window open. The server listens only on
`127.0.0.1:8765`.

For background status/restart/stop without keeping a start window open:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\check_mcp_local_server.cmd
scripts\restart_mcp_local.cmd
scripts\stop_mcp_local.cmd
```

The background start helper creates `.riftreader-local\mcp\config.json` on first
run without printing the token. The restart/stop helpers fail closed if
`127.0.0.1:8765` is owned by anything other than the repo-local ChatGPT
Web/Desktop HTTP MCP server.

## 3. Print status packet

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\print_mcp_operator_status.cmd
```

This writes:

| File | Purpose |
|---|---|
| `.riftreader-local\mcp\latest\summary.json` | Machine-readable handoff/status. |
| `.riftreader-local\mcp\latest\operator-next-steps.md` | Human next steps and expected markers. |

## 3a. Check Cloudflared service status

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\check_mcp_cloudflared_service.cmd
```

Expected clean steady state:

```text
"status": "service_only"
END_RIFTREADER_MCP_CLOUDFLARED_STATUS
PASS: cloudflared connector process detected
END_RIFTREADER_MCP_CLOUDFLARED_STATUS_CMD
```

If it reports `duplicate_processes`, keep the Windows service and stop only the
extra non-service `cloudflared.exe` process. Do not delete the Cloudflare tunnel.

## 3b. Prepare ChatGPT Web/Desktop Secure MCP Tunnel

This is now the preferred ChatGPT Web/Desktop path.

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\prepare_chatgpt_mcp_tunnel_profile.cmd
scripts\check_chatgpt_mcp_tunnel_readiness.cmd
```

If the output is `BLOCKED`, read the listed blockers. Common missing
prerequisites are `tunnel-client`, `CONTROL_PLANE_TUNNEL_ID`, and
`CONTROL_PLANE_API_KEY`.

Once those exist:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
set CONTROL_PLANE_TUNNEL_ID=tunnel_0123456789abcdef0123456789abcdef
set CONTROL_PLANE_API_KEY=<runtime key with Tunnels Read + Use>
scripts\start_chatgpt_mcp_tunnel.cmd
```

Then create the custom app in ChatGPT Settings > Apps using **Tunnel**
connection mode. Do not paste the local bearer token into ChatGPT.

## 4. Token handling

The local token lives in:

```text
.riftreader-local\mcp\config.json
```

Do not paste the token into GitHub, docs, screenshots, or issue comments. Use it only as the bearer token for the Cloudflare/ChatGPT MCP connection.

## 5. Failure meanings

| Symptom | Meaning | Next action |
|---|---|---|
| `auth_token_not_configured` | Auth is required but no token exists. | Run `scripts\start_mcp_local_background.cmd` once to generate local config. |
| `auth_missing` | Request did not include bearer token. | Add `Authorization: Bearer <token>`. |
| `auth_invalid` | Bearer token is wrong. | Recheck `.riftreader-local\mcp\config.json`. |
| Local smoke cannot connect | Server failed to start or port is blocked. | Paste full smoke JSON output. |
| `blocked_foreign_listener` | Port `127.0.0.1:8765` is owned by an unexpected process. | Do not kill it blindly; inspect the JSON process details first. |
| Public health fails but local smoke passes | Cloudflare tunnel/DNS route is not ready. | Follow `docs\cloudflare-tunnel-360madden.md`. |
| `BLOCKED_DOMAIN_SETUP` | Domain was bought but DNS/tunnel route is not complete. | Finish Phase -1 in `docs\cloudflare-tunnel-360madden.md`. |
| `origin_rejected` | Request came from an untrusted browser origin. | Use ChatGPT/tunnel-client or update only trusted local origins. |
| Unsupported `MCP-Protocol-Version` | Client sent an unsupported MCP transport version. | Use current ChatGPT/tunnel-client or omit the header for backward-compatible default handling. |
