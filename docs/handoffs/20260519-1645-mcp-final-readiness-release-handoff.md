# RiftReader MCP final readiness release handoff — final gate green, all 8 phases complete

Updated: 2026-05-19T20:59Z
Repo: `C:\RIFT MODDING\RiftReader`
Baseline: code/dashboard completion at `6da92b730dae93d0973daa8d72592dc568b6d75e` (`6da92b7 Complete MCP final progress dashboard`); this handoff is maintained on `main` and should be paired with current `git status` plus final-gate output.
Remote: `origin/main` synced

## TL;DR

The RiftReader MCP final local product gate is **green** at current HEAD. The dashboard/progress blocker was cleared by committing and pushing `6da92b7`, then waiting for both required GitHub Actions workflows to pass. Mission Control now reports **8/8 final-product phases complete** using the repo-owned actual-client proof plus this release handoff.

No local MCP final-product blockers remain. The only operational caveat is the current Codex thread's already-open `mcp__riftreader__` tool handle: it remains bound to a closed stdio transport until the Codex tool host is reloaded or a fresh conversation starts. Direct stdio MCP validation passes against the durable config.

## Current readiness verdict

| Gate | Status | Evidence |
|---|---:|---|
| Worktree / upstream | Passed | `git status --short --branch` => `## main...origin/main` |
| Phase 2 gate | Passed | `scripts\riftreader-mcp-phase2.cmd --status --compact-json` at `2026-05-19T20:58:54Z` |
| Final gate | Passed | `scripts\riftreader-mcp-final.cmd --status --compact-json` at `2026-05-19T20:58:44Z` |
| Mission Control | Completed | `completedPhaseCount: 8`, `nextPhase: null`, maintenance loop recommended |
| Current-head CI | Passed | `.NET build and test` + `RiftReader Policy` both success for the validated handoff-update HEAD; rerun final gate for the current HEAD |
| Tool surface | Passed | 8 allowlisted MCP tools; no shell/Git/RIFT/CE/x64dbg/provider-write endpoints |
| Public sessions | Passed with expected-expired warnings | quick-tunnel URLs are stopped/ephemeral |
| RiftScan movement/proof lane | Blocked, separate | no supported RiftScan candidate/match evidence |

## Required CI evidence

| Workflow | Result | URL |
|---|---:|---|
| `.NET build and test` | Passed | https://github.com/360madden/riftreader/actions/runs/26124829413 |
| `RiftReader Policy` | Passed | https://github.com/360madden/riftreader/actions/runs/26124829207 |

## Key proof and readiness artifacts

| Artifact | Path / value | Status |
|---|---|---:|
| Actual-client proof JSON | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260519-100945Z\proof.json` | Passed; 8 tools |
| Actual-client proof Markdown | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260519-100945Z\proof.md` | Passed |
| Actual-client inbox ID | `20260519T095322Z-46628318b21e` | Stored |
| Actual-client draft ID | `20260519T095322Z-46628318b21e` | Proof packet |
| Latest readiness artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183107Z-trial-readiness.json` | Passed |
| Latest proposal smoke | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183107Z-proposal-transport-smoke.json` | Passed |
| Latest trial-session final | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183331Z-chatgpt-trial-session.json` | Passed; stopped |
| Latest dry-run summary | `.riftreader-local\package-intake\20260519-183105Z\compact-package-intake-summary.json` | Passed |

## MCP configuration state

The durable Codex MCP config is present in `C:\Users\mrkoo\.codex\config.toml`:

```toml
[mcp_servers.riftreader]
command = 'C:\Users\mrkoo\AppData\Local\Programs\Python\Python314\python.exe'
args = ['C:\RIFT MODDING\RiftReader\tools\riftreader_workflow\riftreader_chatgpt_mcp.py', "--serve", "--transport", "stdio", "--repo-root", 'C:\RIFT MODDING\RiftReader']
cwd = 'C:\RIFT MODDING\RiftReader'
```

Important current-session note: this Codex thread's `mcp__riftreader__` tool handle remained bound to a closed stdio transport after an earlier helper restart. Direct stdio validation passes, and new Codex sessions should spawn the configured server cleanly.

## Exact reproduce/health commands

```cmd
codex mcp get riftreader --json
scripts\riftreader-mcp-phase2.cmd --status --compact-json
scripts\riftreader-mcp-final.cmd --status --compact-json
scripts\riftreader-mcp-mission-control.cmd --json
scripts\riftreader-mcp-artifacts.cmd --latest --json
git status --short --branch
gh run list --limit 5 --json workflowName,headSha,status,conclusion,url,updatedAt
```

Expected final local result: `status: passed`, `ok: true`, `blockers: []` from `scripts\riftreader-mcp-final.cmd --status --compact-json`.

## Fresh ChatGPT trial command

Use this only when an authenticated ChatGPT Desktop/Web session is ready to register the app immediately:

```cmd
scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 900 --json
```

While the command is running:

1. Copy the fresh `publicMcpUrl`.
2. Open ChatGPT settings: `https://chatgpt.com/#settings/Connectors/Advanced`.
3. Enable Developer Mode if needed.
4. Create/refresh the app with Authentication = `No Authentication` and MCP URL = fresh `https://.../mcp`.
5. In ChatGPT, call: `health`, `get_package_proposal_template`, `submit_package_proposal`, `list_inbox`, `review_latest_package_draft`, `dry_run_latest_package_draft`.
6. Record proof immediately.

## Actual-client proof recorder commands

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --template --json
scripts\riftreader-chatgpt-trial-recorder.cmd --record --input <proof-input>.json --json
scripts\riftreader-mcp-final.cmd --status --compact-json
```

## Refresh cadence and stale recovery

| Item | Cadence / budget | Recovery when stale or blocked |
|---|---:|---|
| Current-head CI | Must match HEAD | Push or wait for CI; rerun final gate after both workflows pass |
| Trial readiness | 6 hours | `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` |
| Proposal transport smoke | 6 hours | `scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json` |
| Actual-client proof replay | 24 hours | Run fresh bounded ChatGPT trial and record a new proof |
| Public quick tunnel | Ephemeral by design | Start a new trial session; never reuse old trycloudflare URLs |
| Codex stdio MCP handle | Per Codex session | Restart/reload Codex or start a new conversation if in-thread handle says `Transport closed` |
| RiftScan coordinate evidence | Separate live-proof lane | Keep blocked until supported candidate/match evidence exists or RiftScan writes are explicitly authorized |

## Safety boundaries

- No Cheat Engine.
- No x64dbg attach.
- No RIFT movement/input.
- No provider-repo writes.
- No Git mutation from MCP tools.
- No arbitrary filesystem read/write tools exposed.
- No shell endpoint exposed.
- Public tunnel is explicit-only and bounded by command.
- ChatGPT-originated writes are local/inert package proposals under `.riftreader-local` only.

## Remaining known limits

| Limit | Impact | Current handling |
|---|---|---|
| ChatGPT Developer Mode/app registration cannot be automated from this session | New proof refresh still needs authenticated UI | Use operator-ready trial command and recorder |
| Existing old ChatGPT app connector endpoints are stale | `_health` returns `UNAVAILABLE / Connection failed` | Recreate/refresh app against a fresh trial URL |
| Current Codex thread's `mcp__riftreader__` transport is closed | In-thread tool call may fail until reload | Direct stdio proof passes; configured `riftreader` should work in a fresh session |
| RiftScan candidate evidence missing | Blocks movement/proof expansion only | Keep live movement and RiftScan consumption blocked |

## Resume checklist for the next session

1. Run `git status --short --branch` and confirm `## main...origin/main`.
2. Run `scripts\riftreader-mcp-final.cmd --status --compact-json`.
3. If `Transport closed` appears for `mcp__riftreader__`, restart/reload Codex and retry `mcp__riftreader__.health`.
4. If actual-client proof is stale, run a fresh bounded trial session and record proof.
5. Do not attempt movement/proof promotion until RiftScan milestone review is unblocked.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Start a new Codex conversation and call `mcp__riftreader__.health` | Verifies the final stdio MCP config in a fresh tool host |
| 2 | Call `mcp__riftreader__.get_repo_status` | Confirms the status timeout fix through the real MCP tool path |
| 3 | Run `scripts\riftreader-mcp-final.cmd --status --compact-json` | Confirms product readiness remains green |
| 4 | Use `scripts\riftreader-mcp-mission-control.cmd --trial-command --json` before an external trial | Prints the exact bounded public trial command |
| 5 | Run the fresh ChatGPT trial only when logged into ChatGPT | Avoids wasting the ephemeral Cloudflare URL |
| 6 | Record a new actual-client proof immediately after the trial | Prevents proof freshness drift |
| 7 | Re-run Phase 2 and final gates after any proof refresh | Locks in CI/proof/freshness status |
| 8 | Keep old trycloudflare URLs treated as expired | Quick-tunnel URLs are not durable endpoints |
| 9 | Keep RiftScan/movement lanes blocked | Current provider candidate evidence is missing |
| 10 | Use this handoff as the release-maintenance baseline | It reflects 8/8 completion, proof paths, commands, limits, and refresh cadence; pair it with current final-gate output |
