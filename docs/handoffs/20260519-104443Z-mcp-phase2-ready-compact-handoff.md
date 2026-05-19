# RiftReader MCP Phase 2 Ready Compact Handoff

Generated: 2026-05-19T10:44:43Z
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
HEAD: `d621205 Normalize temp paths for policy CI`

## TL;DR

Phase 1 is complete and pushed. The repo is ready to start Phase 2 of the live artifact bridge/MCP workflow suite: make the now-working proof path more durable, CI-aware, replayable, and operator-fast. Latest verified source state before this handoff was clean at `main...origin/main`; this handoff itself is a new local untracked doc until committed.

## Current truth snapshot

| Area | Status | Evidence |
|---|---:|---|
| Local repo sync | Clean before handoff | `git status --short --branch --untracked-files=all` returned `## main...origin/main` |
| Latest pushed HEAD | Current on origin/main | `d621205 Normalize temp paths for policy CI` |
| GitHub `.NET build and test` | Passed | run `26091793262`, SHA `d621205f26d58f7e89bcdd29b55bd7d242153332`, completed `2026-05-19T10:37:27Z` |
| GitHub `RiftReader Policy` | Passed | run `26091793203`, SHA `d621205f26d58f7e89bcdd29b55bd7d242153332`, completed `2026-05-19T10:38:24Z` |
| MCP Phase 1 gate | Passed | `scripts\riftreader-mcp-phase1.cmd --status --json` returned `status=passed`, `phase1Complete=true`, `repoSideComplete=true`, blockers `[]` |
| Mission Control | Ready | `scripts\riftreader-mcp-mission-control.cmd --json` returned `status=ready`, blockers `[]` |
| Workflow Router | Ready | `scripts\riftreader-workflow-router.cmd --mcp --json` returned `status=ready`, blockers `[]` |

## Latest proof/artifact facts

| Artifact | Latest path / ID | Status |
|---|---|---|
| Trial readiness | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T063557Z-trial-readiness.json` | Passed |
| Proposal transport smoke | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T063557Z-proposal-transport-smoke.json` | Passed; local inbox-only write path covered |
| Public tunnel smoke | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T063454Z-cloudflare-tunnel-smoke.json` | Passed; ephemeral URL expected expired; server/tunnel stopped |
| ChatGPT trial ready | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T100413Z-chatgpt-trial-session-ready.json` | Ready; public URL was `https://centuries-championships-mat-ccd.trycloudflare.com/mcp` |
| ChatGPT trial final | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T101128Z-chatgpt-trial-session.json` | Final teardown recorded `chatgpt-session-interrupted`; server/tunnel stopped; expected after bounded window |
| Actual ChatGPT proof | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260519-100945Z\proof.json` | Passed; tool count `8`; repo root `.`; absolute repo root exposure false |
| Proof Markdown | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260519-100945Z\proof.md` | Human-readable proof packet |
| Actual proof inbox/draft | `20260519T095322Z-46628318b21e` | Inbox saw ID; draft ID matched |
| Latest dry-run | `.riftreader-local\package-intake\20260519-095817Z\compact-package-intake-summary.json` | Passed; dry-run true; changed file count `1` |

## Recently landed commits to preserve as context

| Commit | Purpose |
|---|---|
| `d621205` | Normalize temp paths for policy CI |
| `efe135d` | Align policy CI with Windows test environment |
| `30d833b` | Run policy CI on Windows |
| `e0f66cf` | Fix policy CI validation failures |
| `b6e31ea` | Record MCP phase 1 completion handoff |
| `58a7205` | Treat stopped MCP trial sessions as proof-ready |
| `8982cee` | Harden ChatGPT MCP dry-run proof |
| `023db67` | Add MCP phase 1 external-proof handoff |

## Safety boundaries still active

| Boundary | Current rule |
|---|---|
| Public tunnel | Do not auto-start. Only explicit `--chatgpt-trial-session` / run flags start a bounded tunnel. |
| Git | No hidden staging/commit/push from helpers; Safe Commit Packager remains plan-only. |
| Filesystem/provider writes | Actual MCP write path remains local ignored artifact bridge/inbox/draft only. |
| RIFT input | None sent by this MCP lane. |
| CE/x64dbg | Not used; no attach. |
| SavedVariables as live truth | Not used as live truth. |
| ChatGPT registration | Operator/browser-side action only; helper records supplied proof facts, not credentials or hidden client calls. |

## Phase 2 recommended first slice

Build a small `phase2` status/gate around the existing suite instead of adding broad new capabilities first.

Acceptance criteria for the first Phase 2 slice:

1. Read-only `phase2` status command reports Phase 1 proof, CI state, artifact freshness, and next action in one JSON packet.
2. Mission Control includes latest CI workflow status for current HEAD when `gh` is available, with fail-closed warnings when unavailable.
3. A proof replay/revalidation helper can validate the recorded actual-client proof packet without starting ChatGPT/tunnel/server.
4. Actual-client proof gets age/freshness warnings without invalidating the saved Phase 1 proof.
5. Tests cover CI unavailable, stale proof, fresh proof, and current-head CI pass/fail cases.

## Paste-ready resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader from docs\handoffs\20260519-104443Z-mcp-phase2-ready-compact-handoff.md. Phase 1 ChatGPT MCP proof is complete and pushed at d621205 with GitHub .NET and Policy CI green. Start Phase 2 by implementing a read-only MCP phase2 status/gate that combines Phase 1 proof, current-head CI state, artifact freshness, proof replay/revalidation, and a safer next-action recommendation. Keep public tunnels explicit, no RIFT input, no CE/x64dbg, no hidden Git mutation. Validate with targeted unit tests, riftreader-mcp-phase1 status, mission-control/router JSON, and git diff --check.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Add `scripts\riftreader-mcp-phase2.cmd --status --json` backed by Python | Creates a durable Phase 2 gate without changing MCP behavior. |
| 2 | Add a CI-status reader module used by Phase 2 and Mission Control | Current readiness should include whether HEAD's GitHub workflows passed. |
| 3 | Add proof replay/revalidation for `.riftreader-local\...\actual-client-proof\proof.json` | Lets future sessions re-check proof quality without rerunning ChatGPT. |
| 4 | Add proof freshness/age warnings | Prevents old proof from being mistaken for a current public endpoint. |
| 5 | Update Workflow Router to prefer Phase 2 status when Phase 1 is complete | Moves next-action logic beyond basic artifact browsing. |
| 6 | Add tests for CI unavailable / pass / fail / stale SHA | Avoids making GitHub connectivity a brittle hard blocker. |
| 7 | Add tests for actual-client proof replay failure modes | Keeps fail-closed proof rules stable: tool count, repo root, exposure, inbox/draft/dry-run. |
| 8 | Add Mission Control summary rows for CI and proof age | Makes the main operator dashboard enough for most check-ins. |
| 9 | Run `python -m unittest` for MCP/helper suites plus `git --no-pager diff --check` | Keeps Phase 2 validation as strong as the Phase 1 cleanup. |
| 10 | Commit Phase 2 as one coherent read-only slice before any new public-trial behavior | Preserves the currently green baseline and limits risk. |
