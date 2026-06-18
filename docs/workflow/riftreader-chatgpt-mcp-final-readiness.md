# RiftReader ChatGPT MCP final readiness contract

Status: Implemented contract. Phase 3 added the final gate; Phase 4 added
environment preflight fields for loopback port allocation and local artifact
root safety; Phase 6 tightened offline safety fixtures for MCP proposal targets,
proposal checks, tool-boundary flags, root-safety flags, and unsafe-action
detection. Stage 47 adds role/auth policy metadata while preserving the
personal No Authentication lane; it does not change auth enforcement.

## Purpose

This document defines the exact conditions for calling the RiftReader ChatGPT
MCP workflow **final-product ready**. It is the contract that Phase 3's
`riftreader-mcp-final` gate must implement.

Final-ready means the MCP adapter can be validated, started, registered in
ChatGPT Developer Mode, proven, replayed, and recovered by an operator from a
clean checkout without Codex context and without hidden unsafe actions.

## Non-goals

- Do not add MCP tools outside the approved narrow surface in this contract.
- Do not broaden the adapter into shell, Git, arbitrary filesystem, RIFT input,
  CE, x64dbg, provider-repo, or target-control access.
- Do not start a public tunnel or ChatGPT registration from final status checks.
- Do not treat expired quick-tunnel URLs as a blocker when their summaries prove
  the tunnel/server stopped.
- Do not treat RIFT coordinate or movement proof as part of MCP readiness.

## Final readiness verdicts

| Verdict | Meaning | Exit code |
|---|---|---:|
| `passed` | All required final-product checks passed and warnings are non-blocking. | `0` |
| `blocked` | A known gate prevents final readiness; no unsafe action occurred. | `2` |
| `failed` | A helper error, malformed artifact, unexpected exception, or unsupported state prevented a reliable verdict. | `1` |

A final gate must never report `passed` when any required check is missing,
stale, failing, or unknown.

## Required final readiness fields

The Phase 3 final gate should emit JSON with at least these top-level fields:

```json
{
  "schemaVersion": 1,
  "kind": "riftreader-mcp-final-readiness",
  "generatedAtUtc": "2026-05-19T00:00:00Z",
  "status": "passed|blocked|failed",
  "ok": true,
  "blockers": [],
  "warnings": [],
  "currentHead": "<full git sha>",
  "git": {},
  "ci": {},
  "phase2": {},
  "artifacts": {},
  "dependencies": {},
  "publicSession": {},
  "safety": {},
  "recommendedNextAction": {}
}
```

## Required checks

| Check | Required condition for `passed` | Blocker key when not satisfied |
|---|---|---|
| Repo root | Command runs inside the RiftReader repo. | `repo:not-riftreader-root` |
| Git cleanliness | `git status --short --branch --untracked-files=all` has no tracked or untracked source/doc changes except ignored local artifacts. | `git:dirty-worktree` |
| Current HEAD | `git rev-parse HEAD` succeeds and matches current local branch HEAD. | `git:head-unavailable` |
| Upstream sync | Local branch has an upstream and is neither ahead nor behind when final-ready is claimed. | `git:upstream-not-synced` |
| Current-head CI | Required GitHub workflows for current HEAD are completed and successful. | `ci:missing`, `ci:not-completed`, `ci:failed` |
| Phase 2 gate | `scripts\riftreader-mcp-phase2.cmd --status --json` returns `status=passed`. | `phase2:not-ready` |
| Actual-client proof replay | Latest actual-client proof exists and replays with required proof rules, including `connectionMode=cloudflare-named-tunnel`, `publicMcpUrl=https://mcp.360madden.com/mcp`, `clientTransportStatus=tool-call-succeeded`, `healthCallSucceeded=true`, no retired tunnel host, draft review, and bounded `dryRun.diffPreview` confirmation. | `proof:missing`, `proof:replay-failed` |
| Proof freshness | Latest proof age is within the final proof freshness budget. | `proof:stale` |
| Trial readiness freshness | Latest trial-readiness artifact exists and is fresh. | `artifact:trial-readiness-stale` |
| Proposal smoke freshness | Latest proposal transport smoke exists and is fresh. | `artifact:proposal-smoke-stale` |
| Public session state | No public tunnel or trial session is expected to still be running unless the final gate is explicitly in live-trial mode. | `public-session:unexpected-active` |
| Dependency preflight | Required dependencies for the requested mode are available. | `dependency:missing:<name>` |
| Environment preflight | Repo markers are present, loopback ephemeral port allocation works, and local generated MCP artifacts stay under ignored `.riftreader-local`. | `repo:not-riftreader-root`, `environment:*` |
| Tool exposure | MCP tool list is exactly the approved narrow surface. | `safety:unexpected-tool-surface` |
| Repo-root redaction | Public health/proof reports `repoRoot="."` and `absoluteRepoRootExposed=false`; ChatGPT-facing nested helper payloads do not expose the absolute local repo root. | `safety:absolute-repo-root-exposed` |
| Local-only writes | ChatGPT-originated writes are limited to `.riftreader-local` inbox/draft/audit artifacts. | `safety:write-boundary-broken` |
| Unsafe actions | No shell, Git mutation, package apply, provider write, RIFT input, CE, x64dbg, target-control, reloadui, or screenshot action occurred. | `safety:unsafe-action` |
| Unsafe-action unknowns | Required safety flags in proof/smoke artifacts must be present, not omitted. | `safety:unsafe-action-unknown:<flag>` |

## Approved MCP tool surface

The final-ready adapter may expose exactly these tools unless a future contract
updates this list:

| Tool | Access class | Final-readiness requirement |
|---|---|---|
| `health` | Read-only | Must redact absolute repo root and report safety flags. |
| `get_repo_status` | Read-only | Must not mutate Git, repo files, provider repos, RIFT, CE, or x64dbg. |
| `get_latest_handoff` | Read-only | Must read only `docs/handoffs`. |
| `get_workflow_control_summary` | Read-only | Must return a tiny transport-safe workflow summary without Mission Control, Git mutation, shell, tunnel, RIFT, CE, or x64dbg side effects. |
| `get_mcp_runtime_status` | Read-only | Must report local backend/runtime/source freshness without starting servers or tunnels. |
| `get_tool_surface_diff` | Read-only | Must compare source, loaded manifest, runtime status, and actual-client proof tool surfaces without starting servers or tunnels. |
| `run_mcp_restart_preflight` | Read-only | Must return exact-PID restart facts and approval token without stopping or starting processes. |
| `restart_mcp_runtime` | Approval-token gated local process action | May schedule restart only for the exact verified current MCP PID after token/fact match; must never accept arbitrary commands, start tunnels, register ChatGPT, mutate Git, send RIFT input, write providers, or touch CE/x64dbg. |
| `get_tunnel_status` | Read-only external status | Must inspect Cloudflared/local-runtime/public-route status only; must never start, stop, or mutate tunnel configuration. |
| `get_chatgpt_connector_setup_packet` | Read-only | Must return non-secret ChatGPT Web/Desktop setup instructions, expected tool count, and proof checklist only. |
| `get_final_readiness_status` | Read-only external status | Must compactly report final gate blockers without mutating GitHub or local state. |
| `submit_actual_client_observation` | Guarded local proof write | May write only operator-supplied actual-client proof artifacts under `.riftreader-local`; must never start ChatGPT/tunnels or mutate Git/repo/provider/RIFT state. |
| `get_actual_client_proof_status` | Read-only | Must replay the latest actual-client proof without starting ChatGPT, tunnels, or servers. |
| `get_live_rift_readonly_state` | Read-only live status | Must return only exact-target status/readiness facts and fail closed on stale or mismatched target proof; must never focus, capture, click, send keys, run ProofOnly, promote truth, write providers, or touch CE/x64dbg. |
| `get_live_target_identity_gate` | Read-only live status | Must return the reusable exact-target PID/HWND/process-start/module/duplicate-detection gate without sending input or mutating state. |
| `get_live_no_input_proof_status` | Read-only live proof status | Must return no-input proof/readback summaries only after the identity gate passes; must withhold summaries while gated and never move, input, promote truth, or attach debuggers. |
| `plan_live_control_action` | Plan-only local artifact write | May write ignored live-control plan artifacts with target binding, risk classification, approval prompt, and verification requirements; must never execute input, focus/capture/click, run ProofOnly, promote truth, write providers, or touch CE/x64dbg. |
| `execute_live_control_action` | Fail-closed execution-boundary artifact write | May evaluate one Stage 42 plan and write ignored run artifacts, but in the current slice must block before input because the live backend is unavailable; validation must keep `inputSent=false` and `movementSent=false`. |
| `plan_debugger_ce_action` | Plan-only local artifact write | May write ignored debugger/CE/static-review plan artifacts with risk classification, static-first checklist, target binding when applicable, approval prompt, and candidate-only evidence handling; must never launch or attach x64dbg, start Cheat Engine, set breakpoints/watchpoints, read or write target memory, send RIFT input, promote truth, write providers, or expose generic shell/file tools. |
| `get_package_proposal_template` | Read-only | Must return the accepted package-proposal shape only. |
| `submit_package_proposal` | Guarded local write | May write only inert proposal artifacts under `.riftreader-local\artifact-bridge-inbox`. |
| `list_inbox` | Read-only | Must list inbox metadata only. |
| `create_package_draft_from_inbox` | Guarded local write | May create only inert package-draft artifacts under `.riftreader-local\artifact-bridge-package-drafts` from an explicit validated `inboxId`; must never apply files or execute checks. |
| `review_latest_package_draft` | Read-only | Must review inert draft summaries only. |
| `dry_run_latest_package_draft` | Explicit dry-run action | May run dry-run only; must never pass `--apply`; may return only a bounded `dryRun.diffPreview` from `.riftreader-local\package-intake\*\package.diff`. |
| `apply_latest_package_draft` | Approval-token gated action | May apply only the latest approved operator draft through package intake after matching dry-run summary, diff SHA-256, and approval token; must never stage, commit, push, run shell, send RIFT input, write providers, or touch CE/x64dbg. |
| `commit_reviewed_slice` | Approval-token gated local Git action | May create one explicit-path local commit after matching preflight facts; must never push, rewrite, reset, clean, or broad-stage. |
| `push_current_branch` | Approval-token gated remote Git action | May perform one normal non-force current-branch push after matching preflight facts; must never commit, force-push, rewrite, reset, clean, or use ambiguous refspecs. |
| `get_current_head_ci_status` | Read-only external status | Must inspect current HEAD CI without mutating GitHub state. |
| `run_bounded_repo_command` | Registry-key bounded action | May run only versioned allowlisted repo commands; must never accept shell strings or arbitrary argv. |
| `list_bounded_repo_commands` | Read-only | Must list bounded-command registry metadata without executing commands. |
| `get_workflow_control_plan` | Read-only | Must report Mission Control, safe commit-plan guidance, bidirectional data-flow steps, and gated boundaries without executing shell, Git, tunnel, RIFT, CE, x64dbg, or provider actions. |
| `get_dirty_paths` | Read-only | Must inspect Git dirty-path state only. |
| `get_recent_commits` | Read-only | Must inspect recent local commits only. |
| `repo_tree_tracked` | Read-only tracked-repo context | Must list bounded git-tracked file metadata only. |
| `repo_search_tracked` | Read-only tracked-repo context | Must search bounded git-tracked text content only. |
| `repo_read_tracked_file` | Read-only tracked-repo context | Must read one bounded git-tracked text file only. |
| `repo_read_many_tracked_files` | Read-only tracked-repo context | Must read multiple bounded git-tracked text files only. |
| `repo_context_pack` | Read-only tracked-repo context | Must read predefined bounded tracked-file context packs only. |

Any extra tool is a final-readiness blocker until the contract is updated and
tests prove the new tool stays within the safety model.

Stage 44 adds the debugger/CE static-first design at
`docs/workflow/riftreader-chatgpt-mcp-debugger-ce-static-first-design.md`.
Stage 46 adds `execute_debugger_ce_action`, a fail-closed no-attach
ignored-artifact writer. Stage 47 adds `authRolePolicy` metadata to health,
manifest, connector setup, and workflow-control payloads so the personal
**No Authentication** lane stays explicit while shared/high-power exposure is
classified for `public-read-only` or future auth/explicit gates. CE/x64dbg
attach, breakpoints, watchpoints, memory reads/writes, debugger command
surfaces, OAuth setup, Mixed Authentication setup, and server-side auth
middleware remain outside the final-ready execution surface until later gated
stages update this contract and tests.

Every approved tool must also enforce a strict wrapper-argument allowlist. Any
unknown top-level argument key, non-object argument payload, non-JSON-
serializable payload, or oversized argument payload must block before inbox,
draft, audit-expansion, dry-run, shell, Git, tunnel, RIFT, CE, x64dbg, or
provider side effects can occur.

## Freshness budgets

| Artifact | Budget | Stale behavior |
|---|---:|---|
| Trial readiness | 6 hours | Block final readiness; rerun local readiness. |
| Proposal transport smoke | 6 hours | Block final readiness; rerun proposal smoke. |
| Actual-client proof replay | 24 hours | Block final readiness; record fresh actual-client proof. |
| Current-head CI | Must match current HEAD | Block if missing, queued, in-progress, failed, or for another SHA. |
| Public quick-tunnel smoke | No freshness requirement for final-ready | Historical stopped/expired URLs are warnings only. |
| Bounded ChatGPT trial session final summary | No freshness requirement unless in live-trial mode | Expired/stopped URLs are warnings only; active unexpected sessions block. |

The compact `artifactFreshnessStatus` summarizes only freshness that can block
final readiness: trial readiness and proposal transport smoke. Historical
Cloudflare quick-tunnel and bounded trial-session artifacts may still appear in
`staleArtifactKinds` / warnings when expired, but they are reported as
warning-only stale artifacts and must not be treated as the next actionable
blocker while `publicSessionStatus=passed`.

## Dependency classes

| Dependency | Required for | Final-readiness behavior |
|---|---|---|
| Python runtime | All local MCP helpers | Missing or unusable Python is `failed` or `dependency:missing:python`. |
| Python MCP SDK | SDK validation, serving, transport smoke, ChatGPT trial | Missing SDK blocks modes that require server/client validation. |
| `gh` CLI authenticated for repo read access | Current-head CI verification | Missing/unavailable `gh` blocks final readiness unless a future equivalent read-only CI source is implemented. |
| `cloudflared` or equivalent HTTPS tunnel tool | Public/ChatGPT trial mode only | Missing blocks live-trial readiness, not local-only final-contract validation. |
| `curl` | Public tunnel smoke verification | Missing blocks public-smoke/live-trial modes that use curl verification. |

## Environment preflight fields

The implemented final gate also reports an `environment` object. This check is
read-only and does not start the MCP server or a public tunnel.

| Field | Required condition | Failure behavior |
|---|---|---|
| Repo markers | `agents.md` or `AGENTS.md`, `.git`, and `tools\riftreader_workflow` exist under the resolved repo root. | Block with `repo:not-riftreader-root`. |
| Loopback ephemeral port | Binding `127.0.0.1:0` succeeds and returns an assigned port. | Block with `environment:loopback-ephemeral-port-unavailable`. |
| Default serve port | Binding `127.0.0.1:8770` succeeds. | Warning only; final-readiness is artifact/CI/proof replay based. For live proof collection, run `scripts\riftreader-mcp-server-status.cmd --json` and require `status=running-current`. |
| Ignored local artifact root | `.riftreader-local` is ignored by Git. | Block with `environment:artifact-root-not-ignored:.riftreader-local`. |
| Local MCP roots | MCP local roots remain under `.riftreader-local`. | Block with `environment:local-artifact-root-outside-ignored-root:<name>`. |

## Safety invariants

A final gate must report these safety facts explicitly and fail closed if any are
false in a required proof or smoke artifact:

```yaml
movementSent: false
inputSent: false
reloaduiSent: false
screenshotKeySent: false
noCheatEngine: true
x64dbgAttach: false
providerWrites: false
gitMutation: false
applyFlagSent: false
chatGptRegistrationPerformed: false # except explicitly recorded actual-client proof metadata
publicTunnelStarted: false # except explicit public smoke/live-trial helpers
persistentServerStarted: false # except explicit serve/live-trial helpers with teardown evidence or approval-token gated restart_mcp_runtime scheduling
savedVariablesUsedAsLiveTruth: false
noShellExecutionEndpoint: true
noBroadGitMutationEndpoint: true
gitMutationEndpointLimitedToCommitReviewedSlice: true
noRemoteGitMutationEndpoint: true
noBranchRewriteEndpoint: true
noDestructiveGitCleanupEndpoint: true
noArbitraryFilesystemRead: true
noArbitraryFilesystemWrite: true
noRiftLiveInputEndpoint: true
noTargetControlEndpoint: true
noPersistentServerStartedByTool: true # except restart_mcp_runtime, which is exact-PID and approval-token gated
noTunnelStartedByTool: true
chatGptOriginatedWritesLocalOnly: true
noExistingMcpProxy: true
noWindowsMcpProxy: true
noRiftGameMcpProxy: true
authEnforcementChanged: false
oauthConfigured: false
mixedAuthConfigured: false
secretMaterialIncluded: false
```

## Runtime dependency sequence for actual-client proof

Do not start with the ChatGPT connector UI. Prove dependencies in this order:

1. A saved ChatGPT connector entry exists, but treat it as configuration only.
   It does not start the local backend.
2. `scripts\riftreader-mcp-server-status.cmd --json` returns
   `status=running-current` for `127.0.0.1:8770`.
3. The selected listener command line is the current
   `riftreader_chatgpt_mcp.py --serve` adapter, not a foreign process or the
   legacy `tools.riftreader_mcp.http_server`.
4. The selected listener uses the intended profile (`full` for final 40-tool
   proof, `public-read-only` only for Phase 0 domain checks).
5. The Cloudflare named Tunnel/public route forwards to that backend.
6. If a local/Codex stdio MCP counterpart is present, treat it as a separate
   optional client-side process, not as the Cloudflare HTTP runtime. A stale
   stdio counterpart can make actual callable tools show an old tool count; use
   `stdioCounterparts` from `mcp_server_status.py` to recognize this and
   refresh/restart that client-side app/server before proof.
7. If a Codex Apps wrapper or alternate connector facade can call `health`, use
   that only as a diagnostic of a separate facade. It does not replace the
   non-Codex ChatGPT Web/Desktop actual-client proof unless the proof artifact
   itself records the same client surface and successful tool calls.
8. Actual ChatGPT/MCP connector `health` must be callable from the current
   client surface, with `clientTransportStatus=tool-call-succeeded` and
   `healthCallSucceeded=true`. A `Transport closed`, missing-tool, or stale
   tool-facade result is a client-refresh blocker, not proof that final
   readiness passed.
9. Actual ChatGPT/MCP connector `health` sees the expected tools and output
   schemas.
10. Only then fill/check/record proof input and rerun this final gate.

Fail closed on `not-running`, `foreign-listener`, or `running-legacy`; these
states mean the MCP backend dependency is not satisfied even if a connector
entry or stale proof artifact exists.

## Stage 38 consideration guard

Stage 38 was the first live RIFT boundary. The local-only consideration gate is
historical approval evidence for the Stage 38-40 no-input implementation and can
still be rerun for audit:

```cmd
scripts\riftreader-stage38-consideration.cmd --status --compact-json
```

That helper intentionally never starts live RIFT tooling. The current ChatGPT
surface is 40 tools after adding Stage 42 plan-only live-control artifacts,
the Stage 43 fail-closed execution-boundary artifact writer, and the Stage 45
debugger/CE plan-only artifact writer on top of the Stage 38-40 read-only/no-input
live status surfaces. The helper combines the runtime-status check, Cloudflare named Tunnel
public-route check, final-readiness result, and explicit live-boundary approval
requirement. It reports `blocked` while any prerequisite is missing,
`approval-required` when all local prerequisites pass but no live-boundary
approval token was supplied, and `passed` only after the required approval token
is supplied.

To make that review reproducible, generate the packet through the fail-closed
local writer:

```cmd
scripts\riftreader-stage38-consideration.cmd --write-approval-packet --json
```

When the consideration gate is still blocked, this command writes a blocked
packet under ignored `.riftreader-local` artifacts and returns a blocked status.
When all prerequisites pass but live-boundary approval is still missing, the
packet status is `ready-to-review`. The packet is evidence for review only; it
does not send RIFT input, run ProofOnly, promote truth, or change the MCP tool
surface.

## Phase 6 safety fixture acceptance criteria

Phase 6 may be considered complete when:

1. `submit_package_proposal` rejects unsafe package targets before any inbox
   write, including parent traversal, absolute/drive-qualified paths, `.git`,
   `.riftreader-local`, and generated capture/session roots.
2. `submit_package_proposal` rejects unsafe package checks before any inbox
   write, including Git mutation, RIFT input helpers, Cheat Engine, and x64dbg
   command fragments.
3. The final gate blocks when tool-surface health exposes an absolute repo root,
   omits or falsifies required endpoint-boundary flags, or reports unapproved
   tools.
4. The final gate blocks when root proof/smoke safety flags are missing,
   unknown, or report Git mutation, provider writes, RIFT input, x64dbg attach,
   SavedVariables-as-live-truth, package apply, or CE usage.
5. A refreshed guarded proposal transport smoke still passes locally through
   submit, inbox list, inert draft creation, draft review, dry-run, and bounded
   `dryRun.diffPreview`, with no public tunnel, ChatGPT registration, Git
   mutation, RIFT input, CE, x64dbg, package apply, or provider write.
6. A fresh actual-client proof records `connectionMode=cloudflare-named-tunnel`,
   uses `publicMcpUrl=https://mcp.360madden.com/mcp`, records
   `clientTransportStatus=tool-call-succeeded`, records
   `healthCallSucceeded=true`, avoids retired tunnel hosts, and records the same
   review and bounded `dryRun.diffPreview` facts using the current proof
   template.

## Public session states

| State | Meaning | Final readiness impact |
|---|---|---|
| `not-started` | No public endpoint was started in this check. | Passable. |
| `ready-active` | A bounded trial helper reports a currently usable public URL. | Passable only in explicit live-trial mode; otherwise block as unexpected active exposure. |
| `stopped` | Helper recorded clean server/tunnel teardown. | Passable. |
| `expected-expired` | Historical quick-tunnel URL is known expired/stopped. | Warning only. |
| `interrupted-stopped` | Session was interrupted but server/tunnel stopped. | Warning unless the current task is to prove a fresh live trial. |
| `unknown` | Artifact lacks enough state to prove whether a public endpoint is active or stopped. | Block. |

## Recommended next-action mapping

| Condition | Recommended key | Command |
|---|---|---|
| Dirty worktree | `safe-commit-plan` | `scripts\riftreader-safe-commit-packager.cmd --plan --json` |
| Missing `tunnel-client` dependency | `install-or-locate-tunnel-client` | `scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json` |
| Environment, repo, safety, or public-session blocker | `fix-final-readiness-environment`, `inspect-mcp-safety`, or `inspect-public-session-state` | Mission Control or local readiness command; no live tunnel starts by default. |
| Trial readiness stale | `refresh-trial-readiness` | `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` |
| Proposal smoke stale | `refresh-proposal-smoke` | `scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json` |
| Proof stale/missing/replay-failed | `check-actual-client-proof-input` or `record-actual-client-proof` | Latest fresh `--check-input --input <proof-input.json> --json` command when an indexed proof-input template exists; otherwise `scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json`. |
| CI missing/pending/failing after proof is current | `inspect-current-head-ci` | `gh run list --limit 10 --json databaseId,workflowName,headSha,status,conclusion,createdAt,updatedAt,event,url` |
| Upstream not synced after local gates pass | `request-push-approval` | `git --no-pager status --short --branch` |
| Generic Phase 2 blocker without a more specific blocker | `mcp-phase2-status` | `scripts\riftreader-mcp-phase2.cmd --status --json` |
| All checks pass | `ready-for-release-handoff` | Write/update final release handoff. |

When multiple blockers exist, the final gate chooses the safest specific
operator action before generic wrapper blockers. For example, proof replay
failures take priority over `phase2:not-ready` and current-head CI blockers.

## Phase 3 implementation acceptance criteria

Phase 3 may be considered complete when:

1. `scripts\riftreader-mcp-final.cmd --status --json` exists and returns this
   contract's schema.
2. `scripts\riftreader-mcp-final.cmd --status --compact-json` exists for fast
   operator checks.
3. The final gate fails closed for dirty tree, CI pending/failing, stale
   readiness, stale proposal smoke, stale/missing proof, unsafe tool exposure,
   public-session unknown, and missing required dependency cases.
4. Tests cover each required blocker class and at least one all-pass fixture.
5. Mission Control and Workflow Router can reference the final gate without
   replacing the existing Phase 2 gate.
6. No public tunnel, ChatGPT registration, Git mutation, RIFT input, CE, x64dbg,
   package apply, or provider write occurs during final status checks.

## Operator validation order

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-mcp-phase2.cmd --status --compact-json
.\scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
.\scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json
.\scripts\riftreader-mcp-mission-control.cmd --json
```

After Phase 3 exists, replace the first command with:

```powershell
.\scripts\riftreader-mcp-final.cmd --status --compact-json
```

For a full final-readiness packet including dependency and environment details:

```powershell
.\scripts\riftreader-mcp-final.cmd --status --json
```
