# RiftReader MCP final readiness release handoff — maintenance snapshot

Updated: 2026-05-19T22:05Z
Repo: `C:\RIFT MODDING\RiftReader`
Baseline reviewed: `ffb0bd01352d63d8b2b04825278c8148e55e6027` (`ffb0bd0 Align MCP final gate maintenance action`)
Branch at review: `main`
Upstream at review: `origin/main`
Predecessor handoff: `docs\handoffs\20260519-1645-mcp-final-readiness-release-handoff.md`

## TL;DR

The RiftReader MCP final-product lane remains in **maintenance-loop** state:
all 8 final-product phases are complete, the final readiness gate passes, the
Phase 2 proof/CI gate passes, Mission Control reports 8/8 completed phases, and
the current-head GitHub Actions checks for `ffb0bd0` are green.

This handoff is a docs-only maintenance snapshot prepared for commit/push. After
this handoff is committed, pair it with the latest `git status`, `git log -1`,
GitHub Actions status, and `scripts\riftreader-mcp-final.cmd --status
--compact-json` output for the new HEAD.

## Current readiness verdict

| Gate | Status | Evidence |
|---|---:|---|
| Worktree / upstream before handoff edit | Passed | `git status --short --branch` => `## main...origin/main` |
| Final gate | Passed | `scripts\riftreader-mcp-final.cmd --status --compact-json` at `2026-05-19T22:01:14Z` |
| Phase 2 gate | Passed | `scripts\riftreader-mcp-phase2.cmd --status --compact-json` at `2026-05-19T22:01:16Z` |
| Mission Control | Completed | `completedPhaseCount: 8`, `nextPhase: null`, `operatorNextAction.key: maintenance-loop` |
| Current-head CI for reviewed baseline | Passed | `.NET build and test` + `RiftReader Policy` both success for `ffb0bd0` |
| Tool surface | Passed | Final gate reports `toolSurfaceStatus: passed`; unsafe endpoint exposure remains blocked |
| Public sessions | Passed with expected-expired warnings | Old Cloudflare/trial quick-tunnel URLs are stopped/ephemeral |
| RiftScan movement/proof lane | Blocked, separate | milestone review blocks on missing RiftScan candidate/match evidence |

## Current-head CI evidence for reviewed baseline

| Workflow | Result | HEAD | URL |
|---|---:|---|---|
| `.NET build and test` | Passed | `ffb0bd01352d63d8b2b04825278c8148e55e6027` | https://github.com/360madden/riftreader/actions/runs/26127274617 |
| `RiftReader Policy` | Passed | `ffb0bd01352d63d8b2b04825278c8148e55e6027` | https://github.com/360madden/riftreader/actions/runs/26127274614 |

## Final gate compact status

| Field | Value |
|---|---|
| `status` / `ok` | `passed` / `true` |
| `currentHead` | `ffb0bd01352d63d8b2b04825278c8148e55e6027` |
| `blockers` | `[]` |
| `recommendedNextAction.key` | `maintenance-loop` |
| `phase2Status` | `passed` |
| `proofFreshnessStatus` | `fresh` |
| `proofReplayStatus` | `passed` |
| `ciStatus` | `passed` |
| `dependencyStatus` | `passed` |
| `environmentStatus` | `passed` |
| `publicSessionStatus` | `passed` |
| `releaseHandoffPath` before this handoff | `docs\handoffs\20260519-1645-mcp-final-readiness-release-handoff.md` |

Expected after this file is committed: the final gate should continue to pass
once the docs-only handoff commit has current-head CI results, and the latest
release handoff path should resolve to this file.

## Proof and artifact freshness

| Artifact | Path / value | Status |
|---|---|---:|
| Actual-client proof JSON | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260519-100945Z\proof.json` | Passed |
| Actual-client proof generated | `2026-05-19T10:09:45Z` | Fresh at review |
| Actual-client proof freshness budget | 24 hours | Expires around `2026-05-20T10:09:45Z` |
| Trial readiness | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183107Z-trial-readiness.json` | Passed |
| Proposal transport smoke | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183107Z-proposal-transport-smoke.json` | Passed |
| Trial session final | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T183331Z-chatgpt-trial-session.json` | Passed; stopped/ephemeral |

## Safety state

| Boundary | Current state |
|---|---:|
| Cheat Engine | Not used |
| x64dbg attach | Not used |
| RIFT movement/input | Not sent |
| `/reloadui` / screenshot key | Not sent |
| Provider-repo writes | Not performed |
| Public tunnel during final gate | Not started |
| Persistent MCP server during final gate | Not started |
| ChatGPT registration during final gate | Not performed |
| MCP Git/shell/filesystem-wide unsafe tools | Not exposed |

## Known warnings and blockers

| Item | Status | Handling |
|---|---:|---|
| Old Cloudflare smoke URL | Expected-expired warning | Start a fresh bounded trial session only when the operator is ready |
| Old ChatGPT trial-session URL | Expected-expired warning | Do not reuse old trycloudflare URLs |
| Latest draft is self-test | Warning | Acceptable for local inert draft lane; actual-client proof is not self-test |
| Current Codex thread MCP handle may be closed | Operational caveat | Start a fresh Codex conversation/tool-host reload, then call `mcp__riftreader__.health` |
| RiftScan movement/proof expansion | Blocked | Keep separate until RiftScan candidate/match evidence exists or writes are explicitly authorized |

## RiftScan milestone review result

`python scripts\riftscan_milestone_review.py --compact-json` was run at
`2026-05-19T22:01:38Z` and intentionally returned exit code `1` with
`status: blocked`.

| Issue | Meaning |
|---|---|
| `current_proof_pointer_missing_riftscan_match_file` | No supported RiftScan match file is attached to the current proof pointer |
| `current_proof_pointer_missing_candidate_id` | No candidate ID is attached for safe provider-consumer promotion |
| `no_riftscan_match_files_found:C:\RIFT MODDING\Riftscan` | No existing supported RiftScan match artifact is available under read-only provider rules |

This does **not** block the MCP final product. It blocks movement/RiftScan proof
expansion only.

## Exact resume commands

```cmd
git status --short --branch
git --no-pager log -1 --oneline --decorate
scripts\riftreader-mcp-final.cmd --status --compact-json
scripts\riftreader-mcp-phase2.cmd --status --compact-json
scripts\riftreader-mcp-mission-control.cmd --json
gh run list --limit 5 --json workflowName,headSha,status,conclusion,url,updatedAt
python scripts\riftscan_milestone_review.py --compact-json
```

Expected MCP result after current-head CI is available: final gate `status:
passed`, `ok: true`, `blockers: []`, `recommendedNextAction.key:
maintenance-loop`.

## Fresh external ChatGPT trial command

Use only when an authenticated ChatGPT Desktop/Web session is ready to register
the app immediately:

```cmd
scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 900 --json
```

Operator flow:

1. Copy the fresh `publicMcpUrl`.
2. Open ChatGPT settings: `https://chatgpt.com/#settings/Connectors/Advanced`.
3. Enable Developer Mode if needed.
4. Create/refresh the app with Authentication = `No Authentication` and MCP URL
   = fresh `https://.../mcp`.
5. In ChatGPT, call `health`, `get_package_proposal_template`,
   `submit_package_proposal`, `list_inbox`, `review_latest_package_draft`, and
   `dry_run_latest_package_draft`.
6. Record proof immediately, then rerun the final gate.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | After this handoff commit is pushed, wait for both required GitHub Actions workflows | The final gate requires CI for the current HEAD |
| 2 | Rerun `scripts\riftreader-mcp-final.cmd --status --compact-json` on the pushed HEAD | Confirms the docs-only handoff commit did not disturb readiness |
| 3 | Start a fresh Codex conversation and call `mcp__riftreader__.health` | Verifies the durable stdio MCP config in a new tool host |
| 4 | Call `mcp__riftreader__.get_repo_status` in the fresh session | Confirms the real MCP tool path sees the clean/synced repo |
| 5 | Refresh actual-client proof before `2026-05-20T10:09:45Z` if this lane remains active | Keeps the 24-hour proof budget green |
| 6 | Use `scripts\riftreader-mcp-mission-control.cmd --trial-command --json` before any external trial | Prints the exact bounded public trial command without starting it |
| 7 | Run a new ChatGPT trial only when already logged into ChatGPT | Avoids wasting the ephemeral Cloudflare URL |
| 8 | Treat all old trycloudflare URLs as expired | Prevents accidental reliance on stopped public tunnels |
| 9 | Keep RiftScan/movement lanes blocked until provider evidence exists | Avoids mixing MCP readiness with unproven live movement truth |
| 10 | Use final gate + Mission Control as the maintenance baseline before future releases | They consolidate proof freshness, CI, tool surface, dependency, and safety gates |
