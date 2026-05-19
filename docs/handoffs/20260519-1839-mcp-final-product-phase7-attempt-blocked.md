# RiftReader MCP final product Phase 7 handoff — attempted fresh ChatGPT proof, blocked at authenticated ChatGPT client

Generated: 2026-05-19T18:39Z
Repo: `C:\RIFT MODDING\RiftReader`
Branch/HEAD: `main` @ `a2b74d2cba2c304dd5bb63cd35be9063f0098f0c` (`a2b74d2 Harden MCP safety fixtures`)

## Verdict

Phase 7 is **not strictly complete** yet because the fresh **actual ChatGPT client proof** could not be produced from Codex autonomously. The local backend, public HTTPS MCP session, safety gates, CI checks, and final readiness gate all passed. The remaining blocked step is creating/refreshing the app in a logged-in ChatGPT Developer Mode session and recording the observed real-client tool calls.

## Phase 7 interpretation

From the current MCP final-product lane, Phase 7 means:

1. Start a bounded HTTPS-reachable MCP trial session.
2. Register the temporary `/mcp` endpoint in ChatGPT Developer Mode.
3. Exercise the real ChatGPT client against the tool surface.
4. Record a fresh actual-client proof packet.
5. Re-run the final readiness gate after the proof.

OpenAI Apps SDK docs confirm this model:

- `https://developers.openai.com/apps-sdk/build/mcp-server`: ChatGPT Apps use an MCP server reachable over HTTP/HTTPS, and ChatGPT requires an HTTPS endpoint for development.
- `https://developers.openai.com/apps-sdk/quickstart`: add the app by enabling Developer Mode under Settings -> Apps & Connectors -> Advanced settings, then create a connector/app using the public HTTPS `/mcp` URL.

## Completed work this pass

| Area | Result | Evidence |
|---|---:|---|
| Trial readiness | Passed | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183107Z-trial-readiness.json` |
| Bounded public MCP trial session | Passed | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183331Z-chatgpt-trial-session.json` |
| Public MCP URL during run | Created, then stopped | `https://achieved-tour-atlanta-teddy.trycloudflare.com/mcp` |
| Tool surface over public tunnel | Passed | `initialize`, `tools/list`, and `health` returned successfully through Cloudflare tunnel |
| Expected tools | 8 exposed | `health`, `get_repo_status`, `get_latest_handoff`, `get_package_proposal_template`, `submit_package_proposal`, `list_inbox`, `review_latest_package_draft`, `dry_run_latest_package_draft` |
| Safety | Passed | no shell/Git/RIFT/CE/x64dbg/provider-write endpoints; public tunnel and server stopped |
| Final gate before handoff | Passed | `scripts\riftreader-mcp-final.cmd --status --compact-json` at `2026-05-19T18:36:50Z` |
| Mission Control | Ready, still Phase 7 | `scripts\riftreader-mcp-mission-control.cmd --json` at `2026-05-19T18:36:51Z` |
| Browser route | Blocked | in-app Browser opened ChatGPT settings URL but was redirected to login |
| Codex Apps connector route | Blocked | `riftreader_mcp_trial` and compact connector `_health` returned `UNAVAILABLE / Connection failed` |
| RiftScan milestone review | Blocked, unrelated to MCP | missing RiftScan coordinate match artifacts; movement/proof expansion remains blocked |

## Key artifacts

| Artifact | Path | Notes |
|---|---|---|
| Latest trial readiness | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183107Z-trial-readiness.json` | local/self-test + loopback checks passed |
| Latest trial session ready packet | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183131Z-chatgpt-trial-session-ready.json` | emitted public URL while session was live |
| Latest trial session final packet | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183331Z-chatgpt-trial-session.json` | public tunnel and server stopped cleanly |
| Latest old actual-client proof | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260519-100945Z\proof.json` | passed but predates this Phase 7 retry |

## Blockers

| Blocker | Impact | Required resolution |
|---|---|---|
| In-app Browser is not logged into ChatGPT | Codex cannot create the app in ChatGPT Developer Mode or exercise tools in a real ChatGPT conversation | Operator must use a logged-in ChatGPT Desktop/Web session, or provide an authenticated browser context |
| Existing Codex Apps connector endpoint is stale/unavailable | Cannot use the connector tools as a fresh actual-client proof path | Refresh/recreate connector against a currently running trial `/mcp` URL |
| Public quick-tunnel URLs are ephemeral | The `achieved-tour...trycloudflare.com` URL is intentionally expired after session stop | Start a new trial session for the actual proof window |
| RiftScan milestone review has unrelated coordinate-provider blockers | Does not block MCP app transport, but blocks movement/proof-expansion work | Keep movement/live proof lanes blocked until provider evidence exists or RiftScan writes are explicitly authorized |

## Exact next commands

### 1. Start a fresh bounded trial window

```cmd
scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 900 --json
```

While it is running, copy the printed `publicMcpUrl`.

### 2. In a logged-in ChatGPT session

1. Open ChatGPT settings: `https://chatgpt.com/#settings/Connectors/Advanced`
2. Enable Developer Mode if it is off.
3. Create a new app/connector.
4. Name: `RiftReader MCP Trial`
5. MCP Server URL: the fresh `https://...trycloudflare.com/mcp` from the command.
6. Authentication: `No Authentication`.
7. Create/refresh the app.
8. In a new ChatGPT chat, enable the app and call:
   - `health`
   - `get_package_proposal_template`
   - `submit_package_proposal` with a harmless proof packet
   - `list_inbox`
   - `review_latest_package_draft`
   - `dry_run_latest_package_draft`

### 3. Record the actual-client proof

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --template --json
```

Fill the generated template from the real ChatGPT observations, then run:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --record --input <proof-input>.json --json
```

### 4. Re-run gates

```cmd
scripts\riftreader-mcp-final.cmd --status --compact-json
scripts\riftreader-mcp-mission-control.cmd --json
python scripts\riftscan_milestone_review.py --compact-json
git --no-pager diff --check
```

## Validation results from this pass

| Command | Result | Notes |
|---|---:|---|
| `scripts\riftreader-mcp-mission-control.cmd --trial-command --json` | Passed | printed the bounded Phase 7 trial command |
| `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` | Passed | self-test/tool manifest/SDK/proposal transport passed |
| `scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 120 --json` | Passed | public tunnel + server started, verified, then stopped |
| Browser navigation to `https://chatgpt.com/#settings/Connectors/Advanced` | Blocked | redirected to `https://chatgpt.com/auth/login?...`; no authenticated ChatGPT session available |
| Codex Apps `riftreader_mcp_trial._health` | Blocked | `UNAVAILABLE / Connection failed` |
| Codex Apps `riftreader_mcp_trial_compact._health` | Blocked | `UNAVAILABLE / Connection failed` |
| `scripts\riftreader-mcp-final.cmd --status --compact-json` | Passed | final gate passed at HEAD `a2b74d2cba2c304dd5bb63cd35be9063f0098f0c`; warning only for expected-expired ephemeral public URLs and self-test draft |
| `scripts\riftreader-mcp-mission-control.cmd --json` | Passed | status ready; completed through Phase 6; Phase 7 still ready |
| `python scripts\riftscan_milestone_review.py --compact-json` | Blocked | missing RiftScan coordinate match files/candidate metadata; unrelated to MCP public transport |

## Safety notes

- No Cheat Engine.
- No x64dbg.
- No RIFT movement/input.
- No provider-repo writes.
- No Git mutation.
- No public tunnel left running.
- No persistent MCP server left running.
- Public trial URL was ephemeral and should be treated as expired.

## Remaining Phase 7 tasks

| # | Task | Acceptance |
|---:|---|---|
| 1 | Run a new 900-second trial session | fresh `publicMcpUrl` is live |
| 2 | Create/refresh the app in a logged-in ChatGPT Developer Mode session | ChatGPT accepts the MCP URL and lists/calls tools |
| 3 | Submit harmless proof proposal through real ChatGPT | local inbox receives a new operator-origin proof packet |
| 4 | Run dry-run review through real ChatGPT path | dry-run succeeds without `--apply` |
| 5 | Record actual-client proof | new `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\<timestamp>\proof.json` |
| 6 | Re-run final gate + Mission Control | Phase 7 evidence is current and final readiness remains passed |

## Follow-up update: Codex Desktop stdio MCP path

Updated: 2026-05-19T19:56Z

After the initial handoff, a dedicated Codex Desktop MCP server named
`riftreader` was registered in `C:\Users\mrkoo\.codex\config.toml` using stdio:

```toml
[mcp_servers.riftreader]
command = 'C:\Users\mrkoo\AppData\Local\Programs\Python\Python314\python.exe'
args = ['C:\RIFT MODDING\RiftReader\tools\riftreader_workflow\riftreader_chatgpt_mcp.py', "--serve", "--transport", "stdio", "--repo-root", 'C:\RIFT MODDING\RiftReader']
cwd = 'C:\RIFT MODDING\RiftReader'
```

### Completed in follow-up

| Area | Result | Evidence |
|---|---:|---|
| Local Codex MCP registration | Added | `codex mcp get riftreader --json` showed command, args, and cwd for `C:\RIFT MODDING\RiftReader` |
| `--serve --transport stdio` support | Implemented | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --help` lists `stdio` |
| Local SDK bootstrap for stdio serve | Implemented | `--serve` now calls `ensure_mcp_sdk_available(config.repo_root)` before FastMCP startup |
| `health` through stdio client | Passed | direct MCP stdio client returned `status=passed`, `toolCount=8`, and safe tool annotations |
| `get_repo_status` stdio timeout | Fixed for fresh server processes | child subprocesses now use `stdin=subprocess.DEVNULL`, preventing git/tasklist/status children from inheriting the MCP protocol stdin pipe |
| `get_repo_status` through direct stdio client | Passed | completed in `1.326s`, `isError=false`, `structuredContent.status=blocked`, `ok=true`, `bytes=6612` |

### Follow-up validation

| Command | Result | Notes |
|---|---:|---|
| `python -m unittest scripts.test_workflow_common scripts.test_coordinate_recovery_status scripts.test_riftreader_chatgpt_mcp` | Passed | 51 tests |
| Direct MCP stdio client calling `get_repo_status` | Passed | completed in 1.326s with structured content |
| `python -m py_compile @files` for workflow helpers + script tests | Passed | CI policy equivalent |
| `python -m unittest discover -s scripts -p "test_*.py"` | Passed | 847 tests |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed | one pre-existing style warning for large `common.py` test naming |
| `git --no-pager diff --check` | Passed | only CRLF normalization warnings from Git |

### Follow-up blocker / operator note

The current Codex conversation's already-started `mcp__riftreader__` transport
remained stale/closed after stopping the old helper process. A fresh server
process validates correctly via direct stdio, and the config is correct, but
this Codex UI session may need an MCP reload/restart/new conversation before
`mcp__riftreader__.get_repo_status` reflects the patched code in-tool.

An attempted in-place config refresh was rolled back from
`C:\Users\mrkoo\.codex\config.toml.backup-riftreader-refresh-20260519-155645`.
After rollback, `codex mcp get riftreader --json` verified the intended
command, arguments, and working directory are present.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Start a fresh 900-second trial session only when the operator is ready in ChatGPT | Avoids wasting the ephemeral Cloudflare URL |
| 2 | Use ChatGPT Desktop/Web where the operator is already logged in | Removes the Browser login blocker |
| 3 | Create a new app/connector with `No Authentication` and the fresh `/mcp` URL | Matches the current local trial server contract |
| 4 | Call `health` first from ChatGPT | Confirms tool surface and safety before any write-like local inbox action |
| 5 | Submit one harmless package proposal | Proves the only allowed ChatGPT-originated write path is local/inert |
| 6 | Run `list_inbox` and `review_latest_package_draft` | Proves the proposal is visible without arbitrary file reads |
| 7 | Run `dry_run_latest_package_draft` | Proves guarded dry-run intake works without `--apply` |
| 8 | Record the actual-client proof immediately after the run | Prevents evidence drift from stale tunnel URLs |
| 9 | Re-run final gate and Mission Control | Confirms the product gate accepts the new proof |
| 10 | After Phase 7 proof passes, write the final Phase 8 release/maintenance handoff | Converts validated proof into final-product operating instructions |
