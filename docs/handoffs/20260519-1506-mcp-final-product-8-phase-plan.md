# RiftReader ChatGPT MCP Final Product 8-Phase Plan

Generated: 2026-05-19T15:06:00Z
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## Verdict

The MCP lane is functionally proven but not final-product-ready until it has a clean, CI-covered baseline, a final readiness gate, fresh external proof, and operator-ready runbooks.

Final MCP product means a clean, CI-covered, operator-safe ChatGPT MCP workflow that can be validated, started, registered, proven, replayed, and recovered without Codex context or hidden unsafe actions.

## Phase overview

| Phase | Name | Goal | Key deliverables | Exit criteria |
|---:|---|---|---|---|
| 1 | Preserve current MCP baseline | Lock down the existing local MCP status-gate work before expanding scope. | Revalidate current MCP slice, safe commit plan, explicit-path commit/push when authorized. | Clean worktree, pushed MCP baseline commit, remote CI green. |
| 2 | Final readiness contract | Define exactly what MCP product-ready means. | Readiness schema, blocker taxonomy, acceptance criteria doc. | One documented product-readiness contract exists and later checks can reference it. |
| 3 | Final readiness gate | Add one authoritative command that answers whether MCP is final-ready. | `scripts\riftreader-mcp-final.cmd --status --json`, Python backend, compact JSON mode. | Gate fails closed on dirty tree, stale proof, stale smoke, missing CI, unsafe state, or dependency gaps. |
| 4 | Dependency and environment preflight | Make setup failures obvious before public/ChatGPT trial sessions. | Checks for Python MCP SDK, `gh`, `cloudflared`, port availability, repo root, ignored artifact dirs. | Missing dependencies produce actionable blockers, not stack traces. |
| 5 | Operator workflow hardening | Make the workflow usable without remembering many commands. | Mission Control final-product section, router recommendations, checklist/runbook updates. | Operator has one dashboard and one recommended next action. |
| 6 | Safety/security hardening | Ensure MCP exposes only intended safe tools and local-only writes. | Tool exposure audit, package proposal constraints, no broad FS/shell/Git/RIFT/CE/x64dbg actions. | Safety tests prove unsafe capabilities are rejected or absent. |
| 7 | Fresh real ChatGPT trial | Prove the final path from clean HEAD through the actual external client. | Fresh readiness/proposal smoke, bounded tunnel/session, ChatGPT registration, tiny package proposal, inbox/draft/dry-run. | New actual-client proof recorded and proof replay passes. |
| 8 | Release handoff and maintenance loop | Make final MCP product durable after this session. | Final handoff, exact commands, proof paths, CI links, known limits, refresh cadence. | A future session can reproduce product readiness from the handoff and commands. |

## Phase 1 — Preserve current MCP baseline

| Item | Plan |
|---|---|
| Purpose | Stop building on uncommitted local MCP work. |
| Current evidence | MCP Phase 2 status gate is implemented locally, but the worktree has an uncommitted MCP slice and remote CI does not cover those files. |
| Work | Rerun validation, use Safe Commit Packager, stage explicit paths only, then commit/push the coherent MCP baseline slice when authorized. |
| Validation | `scripts\riftreader-mcp-phase2.cmd --status --compact-json`, full script tests, policy lint, `git --no-pager diff --check`, `.NET build`, `.NET test`, remote CI after push. |
| Exit | `main...origin/main` clean, MCP baseline commit pushed, GitHub `.NET build and test` and `RiftReader Policy` green. |

## Phase 2 — Final readiness contract

| Item | Plan |
|---|---|
| Purpose | Prevent vague ready claims. |
| Work | Write a concise MCP final-product readiness spec. |
| Include | Required proofs, freshness budgets, public-session state, CI state, clean-tree state, safety boundaries, dependency checks. |
| Output | `docs\workflow\riftreader-chatgpt-mcp-final-readiness.md` or equivalent. |
| Exit | Every later gate/test can point to the contract. |

## Phase 3 — Final readiness gate

| Item | Plan |
|---|---|
| Purpose | One command gives final product verdict. |
| Proposed commands | `scripts\riftreader-mcp-final.cmd --status --json` and `scripts\riftreader-mcp-final.cmd --status --compact-json`. |
| Backend | Python-first helper under `tools\riftreader_workflow\`. |
| Must check | Phase 2 gate, clean tree, current-head CI, proof replay, freshness, stale tunnel/session, safety flags, dependency preflight. |
| Exit | Gate returns `passed`, `blocked`, or `failed` with explicit blockers and no ambiguity. |

## Phase 4 — Dependency and environment preflight

| Item | Plan |
|---|---|
| Purpose | Make operator setup reliable. |
| Checks | Python version/imports, MCP SDK, `gh` availability/auth, `cloudflared`, port availability, repo path, local ignored artifact paths. |
| Behavior | Fail closed with clear recovery commands. |
| Output | Structured JSON plus compact human summary. |
| Exit | Missing dependencies produce actionable blockers, not stack traces. |

## Phase 5 — Operator workflow hardening

| Item | Plan |
|---|---|
| Purpose | Reduce command sprawl. |
| Work | Update Mission Control and Workflow Router to prefer final-product gate once available. |
| Add | Final checklist, final status rows, paste-safe commands, exact next action. |
| Docs | Update MCP runbook with normal path, blocked path, and proof refresh path. |
| Exit | Operator can start from Mission Control and follow one recommended path. |

## Phase 6 — Safety/security hardening

| Item | Plan |
|---|---|
| Purpose | Ensure final MCP cannot become a dangerous control surface. |
| Audit | MCP tool list, package proposal schema, local inbox/draft behavior, absolute path exposure, repo-root redaction. |
| Hard blocks | Shell execution, broad filesystem writes, Git mutation, provider-repo writes, RIFT input, CE, x64dbg. |
| Tests | Unsafe request fixtures, path traversal, absolute repo root exposure, unexpected tool count. |
| Exit | Safety tests prove MCP remains local-artifact/proposal-only unless explicitly expanded later. |

## Phase 7 — Fresh real ChatGPT trial

| Item | Plan |
|---|---|
| Purpose | Prove final product through the actual external client path. |
| Precondition | Clean HEAD, CI green, final gate ready except fresh trial. |
| Work | Refresh readiness/proposal smoke, start bounded tunnel/session, register in ChatGPT, submit tiny proposal, verify inbox/draft/dry-run. |
| Record | Actual-client proof JSON/Markdown. |
| Exit | Final proof replay passes and final readiness gate reports product-ready. |

## Phase 8 — Release handoff and maintenance loop

| Item | Plan |
|---|---|
| Purpose | Make final MCP product durable after this session. |
| Output | Timestamped final handoff with CI URLs, proof paths, exact commands, known limits. |
| Add | Refresh cadence for proof/smoke artifacts, stale-artifact recovery steps, and explicit safety boundaries. |
| Exit | A future session can resume from handoff and reproduce product readiness without guessing. |

## Product readiness blockers to fail closed on

| Blocker | Why |
|---|---|
| Dirty tracked MCP files | Current CI does not cover local changes. |
| Remote CI missing/failing for HEAD | Product baseline is not proven. |
| Readiness/proposal smoke stale | Local transport path may no longer be fresh. |
| Actual-client proof missing/failing/stale | ChatGPT integration proof is not durable enough. |
| Public tunnel/session still running unexpectedly | Avoid accidental exposure. |
| SDK/cloudflared dependency missing when needed | Operator cannot run the final flow. |
| Unsafe MCP tool exposure detected | Product safety boundary is broken. |

## Recommended immediate execution

1. Commit this plan as a standalone documentation commit.
2. Revalidate the current MCP baseline slice.
3. Use Safe Commit Packager for explicit-path staging only.
4. Commit/push the validated MCP baseline slice.
5. Verify remote CI for the pushed baseline.
6. Start Phase 2 only after the Phase 1 baseline is clean and CI-green.
