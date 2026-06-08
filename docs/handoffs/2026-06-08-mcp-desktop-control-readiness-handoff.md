# MCP Browser/Computer Use readiness handoff

## Verdict

This slice adds a safe, repo-owned Browser/Computer Use readiness surface for the
ChatGPT Web/Desktop MCP workflow. It does **not** automate browser UI, desktop UI,
RIFT input, tunnels, package apply, or Git mutation. Instead, it makes the current
external automation gap explicit and visible in Operator Lite plus the localhost
MCP dashboard.

| Item | Current truth |
|---|---|
| Active MCP route | `https://mcp.360madden.com/mcp` via Cloudflare named Tunnel to `127.0.0.1:8770`. |
| New helper | `scripts\riftreader-desktop-control-readiness.cmd --json` |
| New Python module | `tools\riftreader_workflow\desktop_control_readiness.py` |
| Operator Lite command | `desktop-control-readiness` / `--desktop-control-readiness` |
| Dashboard card | `Browser & Computer Use` in the localhost-only MCP dashboard. |
| Current readiness result | Browser Use dashboard smoke is confirmed; blocked-safe only on Computer Use native-pipe/list-apps smoke. |
| Latest local observation | `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\20260608-095805Z\observation.json` |

## Current blockers surfaced by the helper

| Blocker | Meaning |
|---|---|
| `computer-use-native-pipe-not-confirmed` | Computer Use bootstrap/list-apps has not yet succeeded; previous live probe reported native pipe unavailable. |

## Browser/Computer Use smoke result

| Surface | Result |
|---|---|
| Browser Use | Passed read-only dashboard smoke against `http://127.0.0.1:8788/`; rendered the `Browser & Computer Use` card and read `/status.json` with `status=passed`, `ok=true`, and `finalReadiness.ok=true`. |
| Computer Use | Blocked-safe at setup: `Computer Use native pipe path is unavailable`. No list-apps response was returned. |

## Files changed

| File | Purpose |
|---|---|
| `tools\riftreader_workflow\desktop_control_readiness.py` | JSON-first readiness helper and self-test. |
| `scripts\riftreader-desktop-control-readiness.cmd` | Thin CMD launcher. |
| `tools\riftreader_workflow\operator_lite.py` | Adds command aliases, shortcut, GUI button, safe command list, and disabled automation marker. |
| `tools\riftreader_workflow\mcp_dashboard.py` | Adds `desktopControl` payload and Browser/Computer dashboard card. |
| `docs\workflow\operator-lite.md` | Documents command, shortcut, aliases, button, and safety. |
| `scripts\test_desktop_control_readiness.py` | Focused helper tests. |
| `scripts\test_operator_lite.py` | Operator Lite command/shortcut/GUI summary coverage. |
| `scripts\test_mcp_dashboard.py` | Dashboard card coverage. |

## Validation

| Check | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\desktop_control_readiness.py tools\riftreader_workflow\operator_lite.py tools\riftreader_workflow\mcp_dashboard.py` | Passed. |
| `python -m unittest scripts.test_desktop_control_readiness scripts.test_operator_lite scripts.test_mcp_dashboard` | Passed: 57 tests. |
| `scripts\riftreader-desktop-control-readiness.cmd --self-test --json` | Passed. |
| `scripts\riftreader-operator-lite.cmd --self-test --json` | Passed. |
| `scripts\riftreader-mcp-dashboard.cmd --self-test --json` | Passed. |
| `git diff --check` | Passed. |
| `pre-commit run --files ... --show-diff-on-failure` | Passed for touched files. |

## Safety boundary

No Browser Use clicks, Computer Use actions, desktop clicks, typing, RIFT input,
movement, reload UI, screenshot-key input, Cheat Engine, x64dbg attach, provider
write, package apply, tunnel start/stop, service stop, or Git mutation through the
helper was performed. Caddy remains only a deprecated legacy route artifact; this
slice does not stop or reconfigure it.

## Next action

Repair/confirm the Computer Use native pipe, rerun the lightweight bootstrap plus
`list_apps` smoke, then update the ignored observation artifact under
`.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\`.
