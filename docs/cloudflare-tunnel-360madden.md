# Cloudflare Tunnel Plan for `mcp.360madden.com`

Use this for the public fallback route:

`https://mcp.360madden.com -> Cloudflare Tunnel -> http://127.0.0.1:8765`

For ChatGPT Web/Desktop local repo access, prefer
`docs\chatgpt-web-mcp-secure-tunnel.md` when OpenAI Secure MCP Tunnel is
available. That path keeps the local MCP server private and avoids relying on a
public MCP endpoint.

This plan assumes Joey owns `360madden.com` in Cloudflare and stays on a free Cloudflare account. It does not require router port forwarding or a raw external IP.

If Joey only bought the domain and did not configure anything beyond basic security, start at **Phase -1** below. That is not a blocker; it just means the domain/tunnel route is not ready yet.

Context7 documentation checked:

| Source | Relevant point |
|---|---|
| `/cloudflare/cloudflare-docs` | Cloudflare Tunnel maps a public hostname to a local service, with ingress catch-all `http_status:404`; dashboard routes create DNS records to the tunnel. |
| `/modelcontextprotocol/modelcontextprotocol` | MCP uses `tools/list` for discovery and `tools/call` for tool execution over JSON-RPC. |
| [OpenAI Apps SDK auth docs](https://developers.openai.com/apps-sdk/build/auth) | Authenticated ChatGPT Apps MCP servers should use OAuth; ChatGPT does not present arbitrary custom API keys/static bearer tokens for app auth. |

## Local service target

| Field | Value |
|---|---|
| Local service | `http://127.0.0.1:8765` |
| Public hostname | `mcp.360madden.com` |
| MCP endpoint | `https://mcp.360madden.com/mcp` |
| Health endpoint | `https://mcp.360madden.com/health` |
| Auth | Bearer token from `.riftreader-local\mcp\config.json` |

## Phase -1: domain-only bootstrap

Run this first when the domain has only been purchased:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\check_mcp_domain_readiness.cmd
```

Expected result when the domain is not fully configured yet:

```text
BLOCKED_DOMAIN_SETUP
END_RIFTREADER_MCP_DOMAIN_PREFLIGHT
```

That means the local repo/server can still be prepared, but Cloudflare DNS/Tunnel setup is still pending.

In the Cloudflare dashboard, confirm:

| Check | What Joey should see/do |
|---|---|
| Domain zone | `360madden.com` exists in Cloudflare Websites/DNS and is active. |
| Nameservers | Public NS records should be Cloudflare nameservers. If the domain was bought through Cloudflare Registrar, this is normally already handled. |
| No home-IP A record | Do not point `mcp.360madden.com` at the home/router IP. |
| Zero Trust | Open Cloudflare Zero Trust and create/select an account/team if prompted. |
| Tunnel | Create a Cloudflare Tunnel for this Windows PC. |
| Connector | Install/run `cloudflared` connector on this PC using the token/command Cloudflare provides. |
| Public hostname | Add `mcp.360madden.com` and route it to `http://127.0.0.1:8765`. |

Do not configure Cloudflare Access in front of `mcp.360madden.com` yet unless ChatGPT is known to support the chosen Access flow. The repo MCP server already requires bearer-token auth.

## Dashboard/manual steps

1. Run domain readiness:

   ```cmd
   cd /d "C:\RIFT MODDING\RiftReader"
   scripts\check_mcp_domain_readiness.cmd
   ```

2. Run local smoke:

   ```cmd
   cd /d "C:\RIFT MODDING\RiftReader"
   scripts\test_mcp_local.cmd
   ```

3. Start local server and leave it running:

   ```cmd
   cd /d "C:\RIFT MODDING\RiftReader"
   scripts\start_mcp_local_background.cmd
   ```

4. In Cloudflare Zero Trust, create or select a Tunnel.
5. Add a public hostname:

   | Field | Value |
   |---|---|
   | Subdomain | `mcp` |
   | Domain | `360madden.com` |
   | Service type | `HTTP` |
   | Service URL | `127.0.0.1:8765` |

6. Confirm Cloudflare created/routes DNS for `mcp.360madden.com`.
7. Test public health with bearer-token auth.
8. Later, configure ChatGPT to use `https://mcp.360madden.com/mcp`.

Public route smoke command after the tunnel is configured:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
python -m tools.riftreader_mcp.smoke_http --public-url https://mcp.360madden.com --json
```

This reads the token from `RIFTREADER_MCP_TOKEN` or `.riftreader-local\mcp\config.json` and does not print the token.

## Locally-managed `cloudflared` template

Tracked example only:

```text
tools\riftreader_mcp\cloudflare-tunnel-360madden.example.yml
```

Template:

```yaml
tunnel: YOUR-TUNNEL-ID
credentials-file: C:\Users\YOUR_USER\.cloudflared\YOUR-TUNNEL-ID.json

ingress:
  - hostname: mcp.360madden.com
    service: http://127.0.0.1:8765
  - service: http_status:404
```

Do not commit the real tunnel ID, credentials path, token, or Cloudflare credentials.

## Verification checklist

| Check | Expected |
|---|---|
| Local smoke | `scripts\test_mcp_local.cmd` prints `PASS`. |
| Local server | Startup JSON says `status: listening`. |
| DNS/hostname | `mcp.360madden.com` exists in Cloudflare. |
| Tunnel route | Public hostname routes to `http://127.0.0.1:8765`. |
| Public health | `https://mcp.360madden.com/health` returns JSON when bearer token is supplied. |
| Public MCP discovery | `POST https://mcp.360madden.com/mcp` with `tools/list` returns only `health`, `get_repo_status`, `get_latest_handoff`. |
| ChatGPT | Pending until ChatGPT connector/developer-mode setup uses OpenAI Secure MCP Tunnel, OAuth, or noauth. The static-bearer public route is diagnostic-only for direct ChatGPT setup. |
| Origin defense | Unknown browser `Origin` headers are rejected; server-side connector/tunnel requests without an `Origin` header continue to work. |

Note: Public Cloudflare smoke proves DNS, tunnel routing, auth enforcement, and
tool discovery through `mcp.360madden.com`. It does not by itself make the app
ChatGPT-ready while the public endpoint still requires this repo's static bearer
token. Keep the bearer token local; use OpenAI Secure MCP Tunnel with
tunnel-client static MCP headers, or implement OAuth/noauth before treating the
public hostname as a direct ChatGPT app route.

## Duplicate connector IDs

Two connector IDs for one tunnel usually means two local `cloudflared` instances
are connected to the same tunnel. That can happen if the Windows service is
installed manually and a second foreground/detached connector is also started.

Preferred steady state for this Windows PC:

| Check | Expected |
|---|---|
| Service | Windows service `Cloudflared` is running. |
| Extra processes | No non-service `cloudflared.exe` process remains. |
| Status command | `scripts\check_mcp_cloudflared_service.cmd` reports `status: service_only`. |

If the Cloudflare dashboard briefly still shows an old second connector after
the duplicate process was stopped, refresh the page or wait for the stale entry
to age out. Do not delete the tunnel for this condition.

## Failure triage

| Failure | Meaning |
|---|---|
| Local smoke fails | Local server/package issue. Fix before Cloudflare. |
| Local passes, public connection refused/timeout | Tunnel is down or not connected. |
| Public 404 | Cloudflare hostname/ingress route is wrong or catch-all matched. |
| Public 401 `auth_missing` | Route works; bearer token was not sent. |
| Public 401 `auth_invalid` | Route works; bearer token is wrong. |
| ChatGPT cannot see tools but public `tools/list` works | ChatGPT connector setup is pending/misconfigured, not a local server failure. |
