# Cloudflare named Tunnel route for `mcp.360madden.com`

This is the **canonical public route** for the RiftReader ChatGPT Web/Desktop
Developer Mode MCP adapter:

```text
ChatGPT Web/Desktop
-> https://mcp.360madden.com/mcp
-> Cloudflare proxied DNS
-> Cloudflare Tunnel riftreader-mcp-360madden
-> cloudflared Windows service on this PC
-> http://127.0.0.1:8770/mcp
-> scripts\riftreader-chatgpt-mcp.cmd
```

Do **not** recreate the old Caddy/router/direct-public-IP route for this lane.
It is deprecated legacy context, not a fallback. OpenAI Secure MCP Tunnel and
ad hoc `trycloudflare.com` quick tunnels also remain retired for this repo lane.

Context7 documentation checked:

| Source | Relevant point |
|---|---|
| `/cloudflare/cloudflare-docs` | Cloudflare Tunnel public hostnames map a domain to a local service behind `cloudflared`; dashboard routes create DNS records to the tunnel hostname. |
| `/cloudflare/cloudflare-docs` | Cloudflare Configuration Rules can disable Browser Integrity Check for matched URI paths, such as an API/MCP path. |

## Current route contract

| Field | Required value |
|---|---|
| Public hostname | `mcp.360madden.com` |
| ChatGPT Server URL | `https://mcp.360madden.com/mcp` |
| ChatGPT auth | `No Authentication` |
| Expected ChatGPT app name | `rift-mcp` |
| Local MCP adapter | `http://127.0.0.1:8770/mcp` |
| Tunnel name | `riftreader-mcp-360madden` |
| Cloudflare published application service | `http://127.0.0.1:8770` |
| Required scoped security rule | `Disable BIC for RiftReader MCP endpoint` |

The local adapter still binds loopback only. Public exposure is provided by the
persistent named Cloudflare Tunnel, not by opening inbound router ports.

## Operator-owned runtime

Start the repo MCP adapter outside Codex and leave it running:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-mcp.cmd --serve --tool-profile public-read-only --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com
```

Then confirm the Cloudflared Windows service is healthy:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\check_mcp_cloudflared_service.cmd
```

## Cloudflare dashboard requirements

| Area | Required setting |
|---|---|
| Tunnel | Persistent named tunnel `riftreader-mcp-360madden`; do not create duplicate quick tunnels. |
| Connector | `cloudflared` is installed/running on this Windows PC, preferably as the `Cloudflared` service. |
| Public hostname | `mcp.360madden.com`. |
| Service target | `http://127.0.0.1:8770` (not `8765`). |
| DNS | Cloudflare-managed/proxied tunnel DNS record; no home-IP A record for `mcp.360madden.com`. |
| Browser Integrity Check | Scoped Configuration Rule disables BIC for `https://mcp.360madden.com/mcp*`. |
| Access/OAuth | Not enabled for Phase 0 read-only proof; ChatGPT app uses `No Authentication`. |

The rule name currently used is:

```text
Disable BIC for RiftReader MCP endpoint
```

## Repo diagnostics

Run the repo-owned public smoke:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json
```

Passing public smoke requires:

| Check | Expected |
|---|---|
| Local backend | `127.0.0.1:8770` reachable. |
| DNS | `mcp.360madden.com` resolves publicly. |
| Public TCP 443 | Reachable through Cloudflare. |
| MCP initialize | HTTP 200 MCP JSON using protocol/header `2025-06-18`. |
| Server identity | `serverInfo.name = riftreader_chatgpt_mcp`. |

Failures such as HTTP `403`, `404`, `421`, `502`, or non-MCP JSON are blockers,
even when the HTTP client itself exits normally.

## Locally managed `cloudflared` template

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
    service: http://127.0.0.1:8770
  - service: http_status:404
```

Do not commit the real tunnel ID, credentials path, token, or Cloudflare
credentials.

## Deprecated route guardrails

| Deprecated/retired path | Rule |
|---|---|
| Caddy/router/direct-public-IP route | Deprecated legacy path. Do not recreate as a default or fallback. |
| TCP 443/80 router forwarding | Not required for the canonical route. Do not add new docs that require it. |
| Local Caddy/nginx reverse proxy | Not part of the canonical route. Any generated Caddyfile is legacy evidence only. |
| `trycloudflare.com` quick tunnel | Retired; not stable enough for the ChatGPT app Server URL. |
| OpenAI Secure MCP Tunnel | Retired for this no-OpenAI-API-key lane unless explicitly reauthorized. |

## Verification checklist

| Check | Expected |
|---|---|
| Local adapter | `scripts\riftreader-chatgpt-mcp.cmd --serve ... --port 8770` is running outside Codex. |
| Cloudflared service | `scripts\check_mcp_cloudflared_service.cmd` reports the persistent service healthy. |
| Tunnel route | Cloudflare published application maps `mcp.360madden.com` to `http://127.0.0.1:8770`. |
| BIC rule | Scoped rule disables Browser Integrity Check for `/mcp*`. |
| Public smoke | `scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json` passes. |
| ChatGPT | Developer Mode app `rift-mcp` uses Server URL `https://mcp.360madden.com/mcp` and `No Authentication`. |

## Failure triage

| Failure | Meaning |
|---|---|
| Local backend unreachable | Repo MCP adapter is not running or is on the wrong port. |
| Public 404 | Tunnel public hostname/path is wrong or catch-all route matched. |
| Public 403 / Error 1010 | Cloudflare security setting is still blocking `/mcp`; recheck the scoped BIC-off rule and bot/security settings. |
| Public 502 | Cloudflare reached the tunnel but the local service target is stopped or wrong. |
| Public 421 | Adapter allowed-host does not include `mcp.360madden.com`. |
| ChatGPT cannot see tools but public initialize works | ChatGPT app configuration/proof step is pending; recheck Server URL and No Authentication. |
