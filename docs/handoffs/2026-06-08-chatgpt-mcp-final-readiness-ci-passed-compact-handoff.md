# ChatGPT MCP final readiness + CI passed compact handoff

## Verdict

The non-Codex ChatGPT Web/Desktop `rift-mcp` workflow is now proven end-to-end
for the safe package-loop contract and the repo final readiness gate is passing.
Actual ChatGPT called the full 12-tool surface, package draft intake reached
dry-run, unapproved apply was blocked, the proof was recorded, the commits were
pushed, and current-head CI passed.

| Item | Current truth |
|---|---|
| Public MCP URL | `https://mcp.360madden.com/mcp` |
| Connection mode | Cloudflare named Tunnel `riftreader-mcp-360madden` |
| Local backend | `http://127.0.0.1:8770/mcp`, owned by `python.exe` PID `48828` during diagnostics |
| ChatGPT app | `rift-mcp`, Developer Mode, No Authentication |
| Tool profile | `full`, 12 tools with output schemas |
| Proof/CI baseline HEAD | `b332124f8bb28a09839ff584a293de6e8d2851a6` |
| Proof baseline Git state | `main` synchronized with `origin/main` at `b332124f8bb28a09839ff584a293de6e8d2851a6` before this docs-only handoff commit |
| Final readiness | Passed at `2026-06-08T09:23:15Z`: `ok=true`, `status=passed`, `phase2Ready=true` |
| Domain diagnostics | Passed at `2026-06-08T09:23:13Z`; public smoke returned HTTP `200`, server `riftreader_chatgpt_mcp` version `1.27.1` |
| CI | `.NET build and test` run `27127927030` passed; `RiftReader Policy` run `27127927100` passed |

## Actual ChatGPT proof package loop

| Step | Result |
|---|---|
| `get_package_proposal_template` | Passed; ChatGPT received the package-proposal template and safety contract. |
| `submit_package_proposal` | Passed; stored inbox item `20260608T034503Z-2828ca695563`. |
| `list_inbox` | Passed; saw the stored inbox item as latest, not applied, not executed. |
| `create_package_draft_from_inbox` | Passed; created draft `20260608T034503Z-2828ca695563`. |
| `review_latest_package_draft` | Passed/ready; read-only review with no blockers. |
| `dry_run_latest_package_draft` | Passed; diff artifact was bounded and under `.riftreader-local\package-intake`. |
| `apply_latest_package_draft` without `approvalToken` | Blocked as required; no apply command started and `applyFlagSent=false`. |

## Key artifacts

| Artifact | Path |
|---|---|
| Recorded proof JSON | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260608-091238Z\proof.json` |
| Recorded proof Markdown | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260608-091238Z\proof.md` |
| Latest trial readiness | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260608T091330Z-trial-readiness.json` |
| Latest final readiness command | `scripts\riftreader-mcp-final.cmd --status --compact-json` |
| Latest domain diagnostics JSON | `.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics\20260608-092312Z\summary.json` |
| Latest domain diagnostics Markdown | `.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics\20260608-092312Z\summary.md` |
| Dry-run diff artifact | `.riftreader-local\package-intake\20260608-090251Z\package.diff` |

## Route clarification

Caddy/router/direct-public-IP is deprecated legacy for this lane. Current public
traffic goes through Cloudflare DNS and the named Tunnel to the local Python MCP
backend. Domain diagnostics still observed `caddy.exe` listening on TCP 443, but
reported `activeRouteUsesCaddy=false`; this explains why Caddy can appear in
local port output without being the active ChatGPT MCP route.

## Final readiness warnings that remain non-blocking

| Warning class | Meaning |
|---|---|
| Expected-expired public sessions | Old Cloudflare smoke/trial-session artifacts are ephemeral and expected to expire; final gate still passed. |
| `environment:default-serve-port-busy:8770` | The backend was already running on the expected local port. |
| `latest-draft-is-self-test` | Historical latest local package-draft summary warning; actual ChatGPT proof artifact is current and passed replay. |
| GitHub Actions annotations | Node.js 20 action deprecation and `windows-latest` redirect notices; both current-head workflows passed. |

## Safety boundary

No package apply, repo target write through MCP, RIFT input, player movement,
reload UI, screenshot-key input, Cheat Engine, x64dbg attach, provider write,
proof promotion, or live stimulus testing was performed by this final readiness
handoff. Git activity in this slice was limited to proof/handoff documentation
commits and approved pushes.

## Recommended next action

Move from proof/registration into maintenance and UX hardening: keep the
Cloudflare named Tunnel route canonical, add a no-write browser/computer-use
operator smoke card, and design the live-stimulus protocol behind explicit
operator approval gates before any game input is sent.
