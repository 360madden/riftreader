# MCP desktop-control repair guide handoff

## Verdict

Computer Use remains blocked outside the RiftReader repo-owned MCP code path.
The supported bootstrap/list-apps probe still fails with
`Computer Use native pipe path is unavailable`. This slice adds a guide-only
repair packet to make the next operator action explicit without expanding the
ChatGPT MCP tool surface or using unsafe UI fallbacks.

| Item | Current truth |
|---|---|
| Active MCP route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to `127.0.0.1:8770`. |
| Browser Use | Read-only dashboard smoke remains recorded as passed. |
| Computer Use | Blocked-safe at setup: `Computer Use native pipe path is unavailable`. |
| New command | `scripts\riftreader-desktop-control-readiness.cmd --repair-guide --json` |
| Current readiness | `blocked`; blocker is `computer-use-native-pipe-not-confirmed`. |
| MCP tool surface | Unchanged; the proven 12-tool final proof remains intact. |

## What changed

| File | Purpose |
|---|---|
| `tools\riftreader_workflow\desktop_control_readiness.py` | Adds guide-only repair payload for the Computer Use native-pipe blocker. |
| `scripts\test_desktop_control_readiness.py` | Adds coverage that the repair guide is guide-only and contains safe record commands. |
| `docs\workflow\operator-lite.md` | Documents `--repair-guide` next to readiness and observation writer commands. |
| `docs\HANDOFF.md` | Points future agents to this handoff. |

## Safety boundary

The repair guide does not automate Browser Use, Computer Use, desktop UI,
window activation, RIFT input, movement, tunnels, services, package apply, Git,
Cheat Engine, or x64dbg. It also explicitly warns not to substitute PowerShell
`SendKeys`, Windows Run, terminal UI automation, custom native-pipe clients, or
RIFT input for the supported Computer Use probe.

## Next action

Repair/reconnect the Codex Desktop Computer Use plugin/runtime outside this repo.
After that, run only the supported Computer Use bootstrap plus `list_apps` smoke.
If it passes, record a fresh observation:

```cmd
scripts\riftreader-desktop-control-readiness.cmd --record-observation --browser-dashboard-smoke-ok --computer-use-native-pipe-ok --computer-use-list-apps-ok --computer-use-stage passed --json
```

If it remains blocked, record the blocker:

```cmd
scripts\riftreader-desktop-control-readiness.cmd --record-observation --browser-dashboard-smoke-ok --computer-use-stage setup --computer-use-error "Computer Use native pipe path is unavailable" --json
```
