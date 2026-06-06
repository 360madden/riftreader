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

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\start_mcp_local.cmd
```

Leave this window open. The server listens only on `127.0.0.1:8765`.

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

## 4. Token handling

The local token lives in:

```text
.riftreader-local\mcp\config.json
```

Do not paste the token into GitHub, docs, screenshots, or issue comments. Use it only as the bearer token for the Cloudflare/ChatGPT MCP connection.

## 5. Failure meanings

| Symptom | Meaning | Next action |
|---|---|---|
| `auth_token_not_configured` | Auth is required but no token exists. | Run `scripts\start_mcp_local.cmd` once to generate local config. |
| `auth_missing` | Request did not include bearer token. | Add `Authorization: Bearer <token>`. |
| `auth_invalid` | Bearer token is wrong. | Recheck `.riftreader-local\mcp\config.json`. |
| Local smoke cannot connect | Server failed to start or port is blocked. | Paste full smoke JSON output. |
| Public health fails but local smoke passes | Cloudflare tunnel/DNS route is not ready. | Follow `docs\cloudflare-tunnel-360madden.md`. |
| `BLOCKED_DOMAIN_SETUP` | Domain was bought but DNS/tunnel route is not complete. | Finish Phase -1 in `docs\cloudflare-tunnel-360madden.md`. |
