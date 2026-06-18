# RiftReader ChatGPT MCP 50-stage finished-product plan

Status: living plan from current Cloudflare named Tunnel proof gap to full ChatGPT Web/Desktop MCP product.

Current holding point: **Post-Stage-41 live-control design contract**.
Stages 38-40 are implemented as read-only/no-input local surfaces, Stage 41 is a
design-only live-control boundary, and the MCP tool contract is still 36 tools.
A fresh 36-tool actual ChatGPT Web/Desktop proof, including
`clientTransportStatus=tool-call-succeeded` and `healthCallSucceeded=true`, is
required before final readiness can be called green again.
Runtime dependency note: after Stage 31, the server-status helper was hardened
to require live runtime `list_tools` + `health` agreement with the expected
loaded tool surface. A matching PID/port/command line alone is no longer sufficient
proof that the MCP backend is current. It also checks that the adapter process
started after current adapter source files were last modified, so
same-tool-count stale runtimes fail closed.

Stage 32 design note:
`docs/workflow/riftreader-chatgpt-mcp-bounded-command-design.md` defines the
future `run_bounded_repo_command` contract.

Stage 33 registry note:
`tools/riftreader_workflow/bounded_repo_commands.py` implements the versioned
local-only allowlist registry (`bounded-repo-command-registry-v1`) for the
current safe status, validation, and ignored-artifact command keys.

Stage 34 exposure note:
`run_bounded_repo_command` is exposed for versioned registry keys only. It never
accepts shell strings or arbitrary argv, and the current full MCP surface is
33 tools after the post-Stage-37 operational proof and runtime-recovery bundles.
Stages 38-40 intentionally raise the current full MCP surface to 36 tools.

Stage 35 audit note:
`tools/riftreader_workflow/bounded_repo_commands.py` now provides local-only
`--list-runs`, `--latest-run`, and `--replay-summary` audit helpers. These
inspect durable `.riftreader-local\riftreader-chatgpt-mcp\bounded-commands\*\run-summary.json`
envelopes without rerunning child commands and block paths outside the
bounded-command audit root.

Stage 36 provider planning note:
`docs/workflow/riftreader-chatgpt-mcp-provider-write-planning.md` defines
provider repo write boundaries for ChromaLink/RiftScan-style external roots.
Provider work remains planning-only; no external repo writes are enabled.

Stage 37 provider-safe proposal flow note:
Package-proposal metadata can now label provider write intent with
`providerWriteIntent`, `providerKey`, and `providerFiles`. The label is
preserved through submit, draft, review, dry-run blocking, and apply preflight
blocking, but provider repo writes remain disabled by default and are not
exposed as an MCP tool.

Post-Stage-37 operational proof bundle note:
`get_mcp_runtime_status`, `get_final_readiness_status`,
`submit_actual_client_observation`, `get_actual_client_proof_status`, and
`list_bounded_repo_commands` are exposed so ChatGPT can verify backend runtime
freshness, final-readiness blockers, actual-client proof state, and bounded
command registry metadata without guessing or assuming that a saved connector
started anything.

Post-Stage-37 runtime-recovery bundle note:
`get_tool_surface_diff`, `run_mcp_restart_preflight`, `restart_mcp_runtime`,
`get_tunnel_status`, and `get_chatgpt_connector_setup_packet` are exposed so
ChatGPT can distinguish source/runtime/client proof drift, obtain exact-PID
restart approval facts, schedule a guarded restart of only the verified MCP
runtime, check the Cloudflare named Tunnel route, and give the operator a
copy-safe non-Codex connector setup packet. The restart tool is approval-token
gated and does not expose arbitrary shell, tunnel mutation, Git mutation, RIFT
input, provider writes, CE, or x64dbg.

Stage 38-40 implementation note:
`get_live_rift_readonly_state`, `get_live_target_identity_gate`, and
`get_live_no_input_proof_status` are exposed as read-only/no-input tools. They
only read repo-owned current proof artifacts and fixed read-only target discovery
facts; they do not focus, capture, click, send keys, run ProofOnly, promote
truth, write providers, or touch CE/x64dbg. Stale or mismatched exact PID/HWND
proof blocks closed.

Before final readiness is considered green again, rerun the dependency sequence
in `docs/workflow/riftreader-chatgpt-mcp-final-readiness.md`: local runtime
current, Cloudflare named Tunnel route passed, actual ChatGPT Web/Desktop
36-tool proof recorded and replayed with a successful actual client transport
call, Phase 2 passed, and final readiness passed. A saved ChatGPT connector
entry is configuration only; it does not start the local MCP server or prove the
current tool surface.
Also inspect `stdioCounterparts` in the MCP server-status payload: stale
Codex/local stdio counterparts are not the Cloudflare HTTP runtime, but they can
explain why an actual callable client surface still reports an old tool count
after the HTTP runtime is already current.
If the ChatGPT/Codex client returns `Transport closed` for a RiftReader tool,
record that as a client-refresh blocker rather than treating the saved connector
or local backend as sufficient proof.
A successful Codex Apps wrapper/facade health call is useful diagnostics, but it
is not a substitute for the non-Codex ChatGPT Web/Desktop proof artifact unless
that actual-client proof records the same current 36-tool client surface, output
schemas, and successful tool calls.
The local-only Stage 38 consideration gate remains historical approval evidence:

```cmd
scripts\riftreader-stage38-consideration.cmd --status --compact-json
```

This helper predates the Stage 38-40 implementation and never starts live RIFT
tooling. It checks the current local runtime, public route, final readiness, and
the explicit live-boundary approval requirement before an approval packet can be
drafted.
The approval packet itself must also be generated through the fail-closed local
writer:

```cmd
scripts\riftreader-stage38-consideration.cmd --write-approval-packet --json
```

This writes ignored `.riftreader-local` evidence only. It reports `blocked` while
final readiness or proof replay is blocked and remains useful as audit history
for the live-boundary decision.

Stage 21 approved package-apply proof, Stage 27 approved local-commit proof,
Stage 30 approval-gated push exposure, and Stage 31 read-only CI monitor
integration are complete-local. The MCP surface now includes `push_current_branch`
and `get_current_head_ci_status`; the operational proof bundle adds status/proof
tools only; arbitrary shell remains absent.

Stage 38-40 no-input live-state tools are now present, and Stage 41 now
documents the live movement/control design contract without adding a tool or
changing the 36-tool proof contract. Stage 42 is the next implementation
boundary: a plan-only live-control planning tool that still sends no input.
Do not expose movement/input execution until the later gated stages explicitly
require it.

## Operating rules

- Keep `https://mcp.360madden.com/mcp` through the persistent Cloudflare named Tunnel as the primary ChatGPT Web/Desktop Server URL; OpenAI Secure MCP Tunnel, trycloudflare quick tunnels, and Caddy/router are retired, not backups.
- Do not expose higher-power endpoints until their design, tests, proof, and approval gates exist.
- Expand in this order: proof current product, apply, local commit, push, bounded commands, provider writes, live RIFT read/control, debugger/CE, auth/roles, eval/dashboard/release.
- Every mutating tool must return explicit safety truth: Git mutation, provider writes, input/movement, public tunnel, CE/x64dbg, and apply flags.
- Prefer Python helpers for orchestration and thin `.cmd` launchers for operator convenience.
- Stage 17 apply design contract: `docs\workflow\riftreader-chatgpt-mcp-apply-tool-design.md`; it remains plan metadata only until the tool is deliberately exposed in Stage 20.
- Stage 18 local-only preflight helper: `tools\riftreader_workflow\package_draft_review.py --apply-preflight-latest-operator`; it never passes `--apply`.
- Stage 19 local-only apply bridge: `tools\riftreader_workflow\package_draft_review.py --apply-latest-operator`; it requires the preflight approval token.
- Stage 20 MCP apply wrapper: `apply_latest_package_draft`; it is exposed-gated and still requires the local approval token.
- Stage 23 commit design contract: `docs\workflow\riftreader-chatgpt-mcp-commit-tool-design.md`; later stages now implement and expose the approval-gated local commit lane.
- Stage 24 commit preflight helper: `scripts\riftreader-commit-reviewed-slice.cmd --preflight`; it is read-only and returns blockers, approval facts, and exact future commands without staging or committing.
- Stage 25 commit execution helper: `scripts\riftreader-commit-reviewed-slice.cmd --commit`; it is local-only, approval-token-gated, reruns preflight, stages explicit paths only, runs pre-commit, and creates one local commit without push/rewrite/reset/clean.
- Stage 26 MCP commit wrapper: `commit_reviewed_slice`; it exposes the Stage 25 helper through strict MCP args, reruns preflight, requires the approval token, and never pushes/rewrite/resets/cleans.

## Stage table

| Stage | Phase | Objective | Exit gate / deliverable | Status |
|---:|---|---|---|---|
| 1 | Current baseline and proof gap | Capture current truth: clean local repo, branch ahead locally, local MCP readiness passed, final gate blocked on actual ChatGPT proof. | Baseline doc and control-plan summary reflect exact current blockers. | complete |
| 2 | Publish current roadmap slice | Push the current roadmap/control-plan commits and wait for current-head CI. | Origin and CI are green for the roadmap baseline. | complete |
| 3 | Refresh Cloudflare named Tunnel command plan | Regenerate the Cloudflare named Tunnel Server URL plan for `mcp.360madden.com` and the exact loopback MCP serve command. | Fresh legacy `manual-public-ip-plan` artifact whose active path is `cloudflare-named-tunnel` with no blockers. | complete |
| 4 | ChatGPT proof template refresh | Generate the current actual-client proof template and verify all required fields are visible. | Template includes connectionMode, tool names, output-schema proof, draft/review/dry-run fields. | complete |
| 5 | Cloudflare named Tunnel network rehearsal | Verify local loopback MCP, Cloudflared service health, public domain initialize, and no retired tunnel/Caddy fallback without broad repo mutation. | `https://mcp.360madden.com/mcp` is reachable through Cloudflare and forwards to the loopback MCP server. | complete |
| 6 | ChatGPT connector registration smoke | Connect ChatGPT Web/Desktop to `https://mcp.360madden.com/mcp` using No Authentication and the narrow MCP app. | ChatGPT can discover the app without OpenAI Secure MCP Tunnel, trycloudflare quick tunnels, Caddy/router, or ngrok. | complete |
| 7 | Read-only ChatGPT smoke | From ChatGPT, call health, get_repo_status, get_latest_handoff, get_workflow_control_summary, and get_workflow_control_plan when transport allows. | Proof records read-only calls, redaction, safety flags, and no unexpected tools. | complete |
| 8 | Tool identity proof | Record exact ChatGPT-observed toolNames for the canonical 19 tools. | Proof replay passes exact tool identity checks. | complete |
| 9 | Output schema proof | Record exact ChatGPT-observed outputSchema coverage for all 19 tools. | Proof replay passes output-schema count and tool-name checks. | complete |
| 10 | Local proposal submit proof | From ChatGPT, submit a harmless package-proposal into .riftreader-local. | Proposal lands in local inbox only with expected metadata and no repo target writes. | complete |
| 11 | Inbox/listing proof | From ChatGPT, list the local inbox and verify the submitted item is visible. | ChatGPT can receive local proposal metadata back through MCP. | complete |
| 12 | Draft creation proof | From ChatGPT, create an inert package draft from the explicit inboxId. | Draft exists under .riftreader-local and is marked inert/local-only. | complete |
| 13 | Draft review proof | From ChatGPT, review the latest operator draft without applying it. | Review returns package summary, blockers, and read-only safety flags. | complete |
| 14 | Dry-run diff proof | From ChatGPT, run dry_run_latest_package_draft and receive bounded diffPreview. | Proof records bounded bytes, text length, truncation boolean, and package-intake path confinement. | complete |
| 15 | Final gate pass for prior 19-tool product | Replay proof and rerun final gate after CI/prior proof are fresh. | Final gate passes for the prior gated-apply ChatGPT MCP product. | complete |
| 16 | Release handoff for prior product | Create and commit a compact handoff for the prior proven 19-tool Cloudflare named Tunnel product. | Durable handoff captures proof artifacts, commands, CI, and remaining future-roadmap gates. | complete |
| 17 | Apply-tool design spec | Design apply_latest_package_draft with exact inputs, approval copy, dry-run hash binding, and fail-closed states. | Design doc exists, control-plan metadata is surfaced, and tests prove the gated tool behavior. | complete-local |
| 18 | Package identity and freshness gate | Add reusable checks that bind apply to a reviewed package root, dry-run summary, diff hash, and age budget. | Unit tests block stale/mismatched/self-test apply attempts. | complete-local |
| 19 | Apply dry-run-to-apply bridge | Implement local apply helper behind explicit approval parameters but do not expose it to ChatGPT yet. | Helper blocks missing/mismatched approval tokens and only passes `--apply` after preflight approval. | complete-local |
| 20 | Expose apply_latest_package_draft | Expose apply as an MCP tool only after helper gates pass and descriptions/outputSchema are complete. | Tool count intentionally changes with updated proof contract and tests. | complete-local |
| 21 | Apply actual-client proof | Prove ChatGPT can apply only an approved reviewed draft and receive post-apply evidence. | Proof records repo source mutation truthfully and blocks unapproved apply. | complete |
| 22 | Post-apply validation reporting | Return validation commands/results, changed files, and rollback hints after apply. | ChatGPT can explain applied state without committing. | complete-local |
| 23 | Safe commit design spec | Design commit_reviewed_slice using safeCommitPlan only, explicit paths, validation gate, and visible commit message. | Spec blocks git add dot, dirty unrelated files, reset/clean/rewrite, and push. | complete-local |
| 24 | Commit preflight helper | Implement read-only commit preflight that validates stageable paths and required tests. | Preflight returns exact add/commit commands and blockers. | complete-local |
| 25 | Commit execution helper | Implement local commit helper with explicit approval and no remote mutation. | Helper commits only approved staged paths after validation. | complete-local |
| 26 | Expose commit_reviewed_slice | Expose local commit as an MCP tool with strict args and outputSchema. | ChatGPT can create local commits only through approved preflight. | complete-local |
| 27 | Commit actual-client proof | Prove ChatGPT can request a local commit for a safe slice and receive hash/status. | Proof shows no push, no branch rewrite, and clean post-commit status. | complete |
| 28 | Push design spec | Design push_current_branch as separate remote-mutation tool with explicit branch/upstream state and no force push. | Spec requires current-turn approval and CI follow-up. | complete-local |
| 29 | Push preflight helper | Implement read-only push preflight with branch, upstream, ahead/behind, protected branch, and CI expectation checks. | Preflight blocks ambiguous or dangerous push cases. | complete-local |
| 30 | Expose push_current_branch | Expose push tool only after local commit flow is proven. | Tool pushes current branch without force/rewrite and returns remote result. | complete-local |
| 31 | CI monitor integration | Add ChatGPT-visible CI status after push using existing GitHub/gh-safe local surfaces. | ChatGPT can report current-head CI pass/fail links after push. | complete-local |
| 32 | Bounded command design spec | Design run_bounded_repo_command with repo-owned allowlist, array args, timeout/output caps, and no shell strings. | Spec defines allowed commands and forbidden classes. | complete-local |
| 33 | Command allowlist registry | Implement versioned allowlist for validation/build/status helpers only. | Tests prove blocked destructive commands and accepted safe commands. | complete-local |
| 34 | Expose bounded command read/write-safe subset | Expose command tool for deterministic repo helpers, not arbitrary shell. | ChatGPT can run allowed validations and status helpers only. | complete-local |
| 35 | Command audit and replay evidence | Add durable audit envelopes for command args, cwd, exit code, timing, stdout/stderr previews. | Every command call is explainable and bounded. | complete-local |
| 36 | Provider repo write planning | Design external/provider repo write boundaries for ChromaLink/RiftScan-style integrations. | Plan requires explicit provider authorization and separate roots. | complete-local |
| 37 | Provider-safe proposal flow | Extend proposal/draft model to label provider writes separately without enabling them by default. | ChatGPT cannot silently mix RiftReader and provider repo mutations. | complete-local |
| 38 | Live RIFT read-only state surface | Expose read-only current target/status facts if exact PID/HWND proof is fresh. | No input/movement; stale target blocks closed. | complete-local |
| 39 | Live target identity gate | Implement reusable exact-target gate: PID, HWND, process start, module base, duplicate detection. | All live tools depend on this gate. | complete-local |
| 40 | Live no-input proof tool | Expose no-input readback/proof summaries only after target identity gate passes. | ChatGPT can inspect proof state without movement/input. | complete-local |
| 41 | Live movement/control design spec | Design bounded live control with explicit movement/input approval, stop conditions, and post-action evidence. | Spec separates no-input, UI/action risk, displacement, movement, and ProofOnly gates without changing the tool surface. | complete-local |
| 42 | Live control dry-run/planning tool | Expose a plan-only live-control tool that returns exact actions but sends no input. | ChatGPT can propose live actions without executing them. | pending |
| 43 | Expose minimal live action tool | Expose the smallest approved exact-target live action after proof gates and manual approval model are stable. | Action records inputSent/movementSent and fails closed on drift. | pending |
| 44 | Debugger/CE static-first design | Design debugger/CE assist to prefer offline/static evidence and require explicit attach approval. | No attach happens from generic repo commands or no-input lanes. | pending |
| 45 | Debugger/CE plan-only surface | Expose plan-only debugger/CE guidance and candidate evidence review. | ChatGPT can assist without attaching or setting breakpoints. | pending |
| 46 | Debugger/CE gated assist | Expose carefully bounded attach/watchpoint assistance only after explicit approval and crash-risk disclosure. | All actions are logged and candidate-only by default. | pending |
| 47 | Role and auth hardening | Add optional auth/role modes for broader sharing while preserving no-auth personal mode. | No-auth remains easy; shared/high-power use can require stronger gates. | pending |
| 48 | End-to-end product eval suite | Build automated local plus actual-client eval checklist covering all tool classes and denial paths. | Regression suite proves both allowed and blocked behaviors. | pending |
| 49 | Operational dashboard and recovery | Surface current stage, blockers, last proof, CI, tunnel health, audit paths, and next action in one dashboard. | Operator can resume without reading long transcripts. | pending |
| 50 | Finished product release | All intended ChatGPT Web/Desktop repo, Git, command, live, and debugger workflows are implemented, gated, proven, documented, and recoverable. | Final gate passes, CI passes, proof artifacts are fresh, and release handoff is published. | pending |

## Immediate implementation window

| Priority | Stage | Action | Why |
|---:|---:|---|---|
| 1 | 42 | Live control dry-run/planning tool | Let ChatGPT propose exact actions while still sending no input. |
| 2 | 48 | End-to-end product eval suite | Keep regression coverage ready as higher-power tools are added. |
| 3 | 49 | Operational dashboard and recovery | Surface stage, blockers, proof, CI, and audit paths as tool count grows. |
| 4 | 50 | Finished product release | Final release remains after live/debugger/auth/eval stages. |

## High-risk exposure order

1. Current gated-apply product proof must pass before the next high-power tool changes the ChatGPT proof contract again.
2. `apply_latest_package_draft` is first because package dry-run and diff-preview are already present.
3. `commit_reviewed_slice` comes after apply so source mutation evidence exists before Git mutation.
4. `push_current_branch` stays separate from commit because it mutates remote state.
5. `run_bounded_repo_command` must be allowlist-only, never arbitrary shell.
6. Live RIFT and debugger/CE tools come last because they have the highest blast radius.
