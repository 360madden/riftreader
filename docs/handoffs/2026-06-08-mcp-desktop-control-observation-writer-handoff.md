# MCP desktop-control observation writer handoff

## Verdict

This slice hardens the Browser/Computer Use readiness lane without expanding the
ChatGPT MCP tool surface. The existing 12-tool ChatGPT MCP proof surface remains
unchanged. Desktop-control readiness is still exposed through the localhost MCP
dashboard/status JSON and the repo-owned helper only.

| Item | Current truth |
|---|---|
| Active MCP route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to `127.0.0.1:8770`. |
| Observation writer | `scripts\riftreader-desktop-control-readiness.cmd --record-observation ... --json` |
| Latest observation | `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\20260608-101740Z\observation.json` |
| Browser Use | Read-only dashboard smoke passed. |
| Computer Use | Blocked-safe at setup: `Computer Use native pipe path is unavailable`. |
| Readiness status | `blocked` with only `computer-use-native-pipe-not-confirmed`. |
| Freshness budget | `maxAgeSeconds=86400`; stale observations block readiness. |
| MCP tool surface | No new tool added; keeping the proven 12-tool final proof intact. |

## What changed

| File | Purpose |
|---|---|
| `tools\riftreader_workflow\desktop_control_readiness.py` | Adds observation writing, observation age metadata, and stale-observation blocking. |
| `scripts\test_desktop_control_readiness.py` | Adds coverage for writer output, partial observations, stale observations, and mtime age fallback. |
| `docs\workflow\operator-lite.md` | Documents the observation writer and 24-hour freshness gate. |
| `docs\HANDOFF.md` | Points future agents to this compact handoff. |

## Validation already run

| Check | Result |
|---|---|
| Computer Use bootstrap/list-apps probe | Blocked-safe at setup with `Computer Use native pipe path is unavailable`; no app/window input attempted. |
| `python -m unittest scripts.test_desktop_control_readiness` | Passed: 7 tests. |
| `python -m py_compile tools\riftreader_workflow\desktop_control_readiness.py` | Passed. |
| Observation writer command | Stored `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\20260608-101740Z\observation.json`. |
| Readiness command after write | Expected exit `2`; Browser passed, Computer blocked, observation fresh. |

## Safety boundary

No Browser Use clicks, Computer Use actions, desktop clicks, typing, window
activation, RIFT input, movement, reload UI, screenshot-key input, Cheat Engine,
x64dbg attach, provider write, package apply, tunnel start/stop, service stop,
or Git mutation through the helper was performed.

## Next action

Repair the Codex Computer Use native-pipe environment outside this repo, then run
only the supported lightweight bootstrap plus `list_apps` smoke. If it passes,
record a new observation with:

```cmd
scripts\riftreader-desktop-control-readiness.cmd --record-observation --browser-dashboard-smoke-ok --computer-use-native-pipe-ok --computer-use-list-apps-ok --computer-use-stage passed --json
```

Then rerun:

```cmd
scripts\riftreader-desktop-control-readiness.cmd --json
```
