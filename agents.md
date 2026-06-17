# RiftReader Agent Policy

This file defines the default assistant behavior for work inside
`C:\RIFT MODDING\RiftReader`.

## Response format

- Lead with the direct answer or result.
- For major findings, start with a prominent verdict such as
  `# **✅ RESULT**`, `# **⚠️ BLOCKER**`, or `# **❌ NOT DONE**`.
- Use tables by default for status, comparisons, blockers, options, and action
  lists.
- Keep responses concise but still detailed enough to be actionable.
- Prefer technical clarity over narration.

## Recommendations

- When recommendations add real value, include **Top 10 recommended next
  actions**.
- Use a table with these columns:
  - `#`
  - `Action`
  - `Why`
- Do **not** include `Model` or `Reasoning` columns unless the user explicitly
  asks for them.
- Do not pad the list with generic suggestions.

## Autonomous continuation mode

When the user asks to keep working autonomously, operate in **autonomous
continuation mode** until a hard stop condition is reached. Do not treat routine
checkpoints as reasons to stop.

### Non-stopping checkpoint events

Do **not** stop merely because one of these occurred:

| Event | Required behavior |
|---|---|
| A safe validation passed | Record it briefly, then continue to the next safe practical step. |
| A known helper/status blocker returned exit code `2` | Treat it as `blocked-safe`, run the listed safe diagnostic or choose the next safe local slice. |
| The worktree is clean | Refresh the decision packet and continue unless the only remaining action is gated. |
| The branch is ahead of origin | Report it briefly; do not push unless explicitly approved. Continue safe local work when useful. |
| A local commit was created | Record the commit hash, refresh local status/decision packet, then continue. |
| Ignored `.riftreader-local` artifacts were written | Treat them as status evidence only and continue. |
| The decision packet says `blocked-safe` | Follow its safe next command or run a safe diagnostic; do not drift into live/proof actions. |
| A status/helper command completed | Use the result as evidence and continue. |
| A milestone completed | Announce it with a big banner, then move to the next safe milestone. |

### Hard stop conditions

Stop and ask for explicit approval only when the next required action would
cross a gated boundary:

| Hard stop | Rule |
|---|---|
| Live RIFT input, movement, displacement stimulus, target-control/visual gates that send input or change game state, or ProofOnly | Ask first; never infer approval from autonomy. |
| x64dbg, Cheat Engine, debugger attach, breakpoints, or watchpoints | Ask first and state crash/risk context. |
| Provider repo writes to RiftScan/ChromaLink or other external repos | Ask first unless explicitly authorized in the current turn. |
| Proof promotion or actor-chain promotion | Ask first and cite the required proof gates. |
| Git push, branch rewrite, destructive cleanup/delete, or remote mutation | Ask first; local commits are allowed only for coherent validated slices. |
| Validation failure | Diagnose narrowly before continuing; do not paper over the failure. |
| Ambiguous scope with live/game/repo-history blast radius | Stop, state the ambiguity, and ask the smallest concrete approval question. |

### No-movement current-PID proof-recovery lane

When the user has authorized or resumed current-target proof recovery, continue
without repeated approval through the no-movement recovery lane only while every
helper remains exact-target and declares or proves:

| Required condition | Rule |
|---|---|
| Exact target identity | Bind the current PID/HWND/process start and fail closed on drift or duplicates. |
| No game-state mutation | `movementSent=false`, `inputSent=false`, no `/reloadui`, no screenshot-key input, no target selection, and no displacement stimulus. |
| No debugger/CE | Do not attach x64dbg, use CE, set breakpoints, or watchpoints in this lane. |
| No provider writes | ChromaLink/RiftScan and other provider repos stay read-only unless separately authorized. |
| No truth/proof promotion | Do not pass `--allow-current-truth-update`, run `ProofOnly`, or promote an actor/proof chain without separate approval. |
| Repo-owned artifacts only | Writing RiftReader-owned captures, summaries, current-session candidate files, and handoffs is allowed. |

Allowed no-movement recovery work includes current target discovery, no-input
target-control/visual verification, fresh API/runtime coordinate capture,
memory-region inventory, read-only current-PID coordinate-family scans or scan
plan batches, no-input candidate readback/classification, and durable
JSON/Markdown summaries. After a current-PID candidate file exists and initial
API-now vs memory-now deltas are within tolerance, recommend controlled
movement/displacement stimulus testing as the next evidence step, but still ask
before sending it.

### Default continuation loop

1. Run or refresh `.\scripts\riftreader-decision-packet.cmd --compact-json --write`.
2. Follow the packet's `safeNextAction` when it is safe and non-mutating.
3. If the worktree is dirty, run relevant safe validations.
4. If validations pass and the slice is coherent, stage explicit paths only and
   commit locally.
5. After a local commit, refresh status/decision packet and continue to the next
   safe local task.
6. If the branch is ahead of origin, report it but do not push without explicit
   approval.
7. Prefer small coherent milestones over broad risky rewrites.

### Milestone notification style

Use this format for major checkpoints:

```markdown
# **🚦 MILESTONE N — TITLE**
## **✅ DONE / ⚠️ BLOCKED-SAFE / 🛑 NEEDS APPROVAL / 🔄 CONTINUING**
Short summary:
- Files changed
- Validation run
- Commit hash if committed
- Current blocker if any
- Next command/action
```

Then continue automatically unless a hard stop condition is present.

## OpenCode retirement boundary

OpenCode is **retired/demoted for this repo**. Do not start, route, expand, or
prioritize OpenCode implementation work unless the user explicitly
re-authorizes OpenCode in the current conversation.

| Boundary | Required behavior |
|---|---|
| New OpenCode code, wrappers, prompt builders, tests, UI buttons, or integration hardening | Do not create or modify them by default. |
| Existing OpenCode files/docs | Treat them as historical maintenance surface only. Do not use them as the active workflow. |
| Local decision automation | Prefer the Local Decision Control Plane, Operator Lite, and Codex-native repo workflows. |
| Ambiguous references to old OpenCode milestones | Treat them as stale plan text and confirm against this retirement boundary before acting. |

## Default model-picking policy

| Situation | Default model | Reasoning | Default approach |
|---|---|---|---|
| Formatting, tables, status boards, and docs-only updates | `spark` (prefer) | low | answer directly; no local modifications |
| Small script, UI, or docs change with a known fix path | `spark` (prefer) | medium | make the smallest patch and validate |
| Single-file, low-impact code change with clear rollback | `spark` (prefer) | medium | patch minimally, then validate |
| Normal multi-file bugfix or moderate behavior change | `gpt-5.4` | medium | inspect first, then patch |
| Unclear bug, conflicting evidence, or live-path risk | `gpt-5.4` | high | diagnose before editing |
| Deep discovery, reverse engineering, or proof work | `gpt-5.4` | xhigh | narrow scope and work evidence-first |

### Spark-safe guardrails

Use `spark` unless a task is in the explicit “no-spark” bucket:

| No-spark class | Why | Route |
|---|---|---|
| Any unproven live movement capture logic | high blast radius if wrong | `gpt-5.4` |
| Navigation or route planning core behavior changes | user-impacting movement state | `gpt-5.4` |
| Reverse-engineering candidate promotion (coord anchors / source-chain / proof watchsets) | stale/invalid candidates have high restart cost | `gpt-5.4` |
| Cheat Engine session state handoff, branch-wide refactors, or risky merges | evidence-sensitive and hard to auto-rollback | `gpt-5.4` |

When uncertain, use this template (or equivalent): `docs/model-routing-template.md`
and prefer `gpt-5.4` if any “No-spark” condition is true.

## Permanent Codex routing and subagent policy

When using Codex in this repo, apply the durable routing policy in
`docs/workflow/codex-agent-routing-policy.md`.

Default behavior:

| Situation | Required routing |
|---|---|
| Docs/status/search-only work | Lower reasoning / lower-intelligence routing is allowed when bounded and reviewable. |
| Small reversible code/test change | Medium reasoning is acceptable with targeted validation. |
| Unclear bug, conflicting evidence, or multi-file behavior change | Use stronger reasoning; diagnose before editing. |
| Live RIFT input, target selection, x64dbg/CE, coordinate truth, actor-facing, proof-watchsets, or movement gates | Stronger reasoning only; never route to lower intelligence. |
| Commit/push and final integration | Main agent owns review, explicit staging, validation, commit, and push decisions. |

Subagents are allowed **up to the practical maximum** when work naturally splits
into independent, non-overlapping tasks. Use them aggressively for read-only
discovery, source review, and disjoint implementation slices, but do not spawn
agents for tiny single-step fixes where coordination overhead exceeds value.

Before delegating, define the subtask scope, risk class, read/write authority,
file ownership, and expected output. Workers must be told they are not alone in
the codebase and must not revert or overwrite others' work. The main agent must
integrate and validate results before making final claims or committing.

## Custom Codebuff Agent Policy

The repo defines three custom Codebuff agents under `.agents/`. Each has a
specific model, tool set, and operating contract. The main agent should spawn
them instead of handling their specialized work directly.

### Agent Catalog

| Agent | Model | Purpose | Frequency | Blast Radius |
|---|---|---|---|---|
| `rift-readback` | `deepseek/deepseek-v4-pro` | Read-only coordinate recovery | Every session | Low — read-only tools |
| `rift-discovery` | `deepseek/deepseek-v4-pro` | Static chain reverse-engineering | Per discovery campaign | Medium — may run terminal commands |
| `rift-proof` | `deepseek/deepseek-v4-pro` | Promotion gate evaluation | Per promotion candidate | High — promotion decisions are irreversible |

### rift-readback — Spawn Policy

All agents obey the **hard stop conditions** defined above (live RIFT input, movement, debugger attach,
proof promotion all require explicit approval). The gates encoded here (`stimulusApproved`,
`movementApproved`, `promotionAllowed`) are programmatic enforcement of those hard stops.

**When to spawn:**
- Reading current player coordinates (instant static chain readback)
- Comparing API coordinates against chain readback (verified mode)
- Running a promotion readiness check
- Diagnosing RRAPICOORD resolver health
- Any task listed in Tier 1–3 of the coordinate recovery workflow

**Do NOT spawn for:**
- Discovery work (use `rift-discovery`)
- Promotion gate evaluation (use `rift-proof`)
- Any task that sends game input, attaches debuggers, or writes files

**Defensive properties:**
- Tools: `read_files`, `code_search`, `glob`, `list_directory`, `run_terminal_command`
- No `write_file`, `str_replace`, or `spawn_agents` (cannot modify files or delegate)
- All output is structured JSON with `status`, `blockers`, `warnings`, `safety`
- Never sends input, attaches debuggers, or mutates repo unless explicitly asked
- Primary tools: `scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json` (instant),
  `scripts/capture-rift-api-reference-coordinate.ps1` (API capture for verified mode)
- Promoted resolver: `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`
- This is the **canonical agent for the no-movement current-PID proof-recovery lane** (Tier 1–3)

**Input contract:**
- `mode`: `instant`, `verified`, `readiness`, or `diagnostic`
- Optional: `pid`, `hwnd`, `tolerance`

### rift-discovery — Spawn Policy

**When to spawn:**
- Discovering new static pointer chains (yaw, facing, pitch, movement bearing)
- Comparing owner window memory snapshots to find stimulus-changing offsets
- Tracing module-RVA pointers near candidate offsets
- Running the discovery pipeline: snapshot → compare → trace → score
- Any reverse-engineering task that requires new static pointer chain discovery

**Do NOT spawn for:**
- Routine coordinate readback (use `rift-readback`)
- Promotion gate evaluation (use `rift-proof`)
- Simple docs updates, formatting, or status boards

**Defensive properties:**
- Tools: `read_files`, `code_search`, `glob`, `list_directory`, `run_terminal_command`, `spawn_agents`, `researcher_web`
- Can spawn `rift-readback` for candidate validation
- All output has `candidateOnly: true` — never promotes
- Blocks safely with `blocked-needs-stimulus` if turn/movement input is needed but not approved
- Requires `stimulusApproved: true` in params before sending any game input
- Never attaches x64dbg or Cheat Engine without explicit approval
- Never modifies `current-truth.json`

**Input contract:**
- `target`: `yaw`, `facing`, `pitch`, or `movement-bearing`
- Optional: `pid`, `hwnd`, `stimulusApproved` (defaults to `false`)

**Discovery pipeline:**
1. Baseline owner window snapshot (`static_owner_facing_discovery.py snapshot`)
2. Stimulus (turn key, movement) — **skipped** if `stimulusApproved` is `false`
3. Displaced snapshot
4. Compare (`static_owner_facing_discovery.py compare`)
5. Pointer trace (`pointer_owner_neighborhood_inspector.py`)
6. Candidate chain readback (delegated to `rift-readback`)

### rift-proof — Spawn Policy

**When to spawn:**
- Evaluating whether a candidate chain is ready for promotion
- Running three-pose displacement validation
- Testing reboot/relog survival of a promoted chain
- Checking API-now versus chain-now agreement
- Producing a gate-by-gate promotion readiness report

**Do NOT spawn for:**
- Routine coordinate readback (use `rift-readback`)
- Discovery work (use `rift-discovery`)
- Actually performing promotion — this agent only reports, never promotes

**Defensive properties:**
- Tools: `read_files`, `code_search`, `glob`, `list_directory`, `run_terminal_command`, `spawn_agents`
- No `write_file` or `str_replace` — cannot modify files
- Can spawn `rift-readback` for coordinate validation
- `promotionAllowed` is `false` unless **all** gates pass
- `safety.promotionPerformed` is **always** `false`
- Blocks safely if `movementApproved` is `false` and three-pose proof is needed
- Fail-closed: blocks on any ambiguity rather than risking false approval

**Input contract:**
- `chainExpression`: the candidate chain to proof
- `targetField`: what it resolves to (`coordinates`, `yaw`, `facing`, `pitch`)
- `proofType`: `three-pose-displacement`, `reboot-survival`, `promotion-readiness`, or `full`
- Optional: `movementApproved` (defaults to `false`), `pid`, `hwnd`, `tolerance`

**Required promotion gates:**
1. `staticResolverComplete` — chain resolves and root RVA is documented
2. `restartRelogSurvived` — chain survives a RIFT restart
3. `threePoseDisplacement` — chain delta matches ground truth across three poses
4. `apiNowVsChainNow` — fresh API capture matches chain readback within tolerance
5. `artifactFreshness` — proof artifacts are recent

### Agent Interaction Flow

```
User request
    │
    ├─ Read coordinates? ──────────────► rift-readback
    │
    ├─ Discover new chain? ────────────► rift-discovery
    │       │
    │       └─ Validate candidate? ────► rift-readback (spawned by discovery)
    │
    └─ Proof candidate for promotion? ─► rift-proof
            │
            └─ Read coordinates? ──────► rift-readback (spawned by proof)
```

### Recovery System

All agents are backed by a recovery system under `.agents/backup/` and `scripts/`:

| Tool | Command | Purpose |
|---|---|---|
| Snapshot | `python scripts/agent-snapshot.py` | Create timestamped backup of all agent `.ts` files |
| Rollback | `python scripts/agent-rollback.py <snapshot>` | Restore agents from a snapshot (creates safety snapshot first) |
| Validate | `python scripts/agent-validate.py --verbose --json` | CI pipeline: checks syntax, required fields, model validity, tool names, output schemas |

Run `agent-validate.py --verbose --json` after any agent edit. The validator checks all three
agents in a single pass and reports per-agent results. The `--json` flag enables structured
output for CI integration; omit `--skip-ts-check` when TypeScript is available.

## Escalation / anti-loop rules

- Start simple. Validate quickly. Escalate only on evidence.
- First failure: gather more evidence and keep scope narrow.
- Second similar failure: increase reasoning depth and re-check the root cause.
- Third similar failure: stop retrying the same patch pattern; change tactics and
  restate the hypothesis from observed facts.
- Do not keep retrying a hypothesis without new evidence.

## Live discovery / reverse-engineering signal policy

- Do **not** interpret "smallest correct patch" or "start simple" as "use the
  shortest possible live proof" for coordinate/facing discovery.
- For live reverse-engineering, memory scanning, movement capture, or candidate
  scoring, optimize for the **highest signal per bounded run**, not the
  shortest safe pulse.
- Prefer controlled, reversible, well-instrumented runs over underpowered
  probes: addon labels + native memory recorder + exact PID/HWND input +
  timestamped artifacts.
- When validating coordinate candidates, prefer scripted multi-vector movement
  traces with pauses and direction changes over a single forward pulse, unless
  the user explicitly asks for a tiny smoke test.
- Safety means bounded scope, exact targeting, crash awareness, and clear stop
  conditions; it does **not** mean minimizing the data collected below what is
  needed for strong evidence.

## SavedVariables live-capture hazard

- Treat RIFT addon `SavedVariables` files, including
  `ReaderBridgeExport.lua`, as **post-save snapshots only**. They are **not**
  live IPC and should be expected to update only on `/reloadui`, logout, UI
  shutdown, or another client save event.
- Never use `ReaderBridgeExport.lua` last contents as live movement truth during
  a START/STOP capture unless a fresh save/flush was intentionally performed
  and the file timestamp proves it happened after the movement state being
  analyzed.
- For live coordinate capture, use a true live surface: on-screen addon overlay
  screenshots/OCR, native memory reads, a validated coord-trace anchor, or an
  explicitly implemented live bridge. In-game addon runtime state may be live,
  but the SavedVariables file is not live until flushed.
- Any scan, seed list, or candidate packet derived from a SavedVariables file
  must record the file `LastWriteTimeUtc`, capture start time, and freshness
  classification. If the file predates the capture, mark those seeds
  `stale-post-save-snapshot` and do not mix them with live overlay truth as if
  they were same-time samples.
- Before any future coord bundle, declare the authoritative truth surface in the
  manifest (`overlay`, `memory-anchor`, `post-flush-savedvariables`, etc.) and
  fail closed if the recorder accidentally uses a non-live SavedVariables file
  as live truth.

## Scope and validation

- Prefer the smallest correct patch over broad refactors.
- Preserve existing architecture unless there is a clear reason to change it.
- Run the most relevant validation available after changes.
- Prefer the timestamped validation ledger for repeatable validation so long
  runs record UTC start/end timestamps, durations, logs, and slow-command
  warnings:
  - smoke: `python tools\riftreader_workflow\validation_ledger.py --tier smoke`
  - targeted: `python tools\riftreader_workflow\validation_ledger.py --tier targeted --command "<command>"`
  - full local: `python tools\riftreader_workflow\validation_ledger.py --tier full-local`
  - CI parity: `python tools\riftreader_workflow\validation_ledger.py --tier ci-parity --commit HEAD`
- Use `pre-commit` as the fast local commit gate for deterministic, non-live
  checks before local commits. See `docs/workflow/pre-commit-local-gates.md`.
  Run `pre-commit run --all-files --show-diff-on-failure` after changing
  `.pre-commit-config.yaml`.
- Preserve the third-party workflow tools cataloged in
  `docs/workflow/third-party-workflow-tools.md`. Do not remove, bypass, or
  silently downgrade pre-commit, pre-commit-hooks, Ruff, actionlint,
  EditorConfig, Gitleaks, Pyright, Semgrep CE, OSV-Scanner, Renovate, or
  markdownlint-cli2 integration to make a check pass. Repair the setup or
  document an equal-or-stronger replacement instead. PSScriptAnalyzer is
  intentionally excluded unless the user explicitly asks for it.
- Include the latest ledger `summary.md` path and timing summary in handoffs
  after substantial validation runs.
- Say exactly what was not validated.

## Context7 documentation lookup policy

Use Context7 before answering questions about current library, framework, SDK,
CLI, or cloud-service behavior. This includes `.NET`, PowerShell, Playwright,
JavaScript/TypeScript packages, and version-specific migration questions.

Required workflow:

1. Call `resolve-library-id` with the library name and the user's full question,
   unless the user already provides an exact `/org/project` Context7 ID.
2. Pick the best match by exact name, source reputation, snippet coverage,
   benchmark score, and version relevance.
3. Call `query-docs` with the selected ID and the full question.
4. Answer from the fetched docs and mention the Context7 ID used when accuracy
   or ambiguity matters.

Do not use Context7 for local RiftReader debugging, repo-specific refactors,
business-logic review, code review, or live RIFT/x64dbg/coordinate-truth
diagnosis. Inspect the repo, tests, build output, git history, and live artifacts
directly for those. Treat Context7 output as advisory external-doc context, not
as proof of current repo truth.

Examples:

- `Use Context7: current .NET CLI syntax for dotnet test filters.`
- `Use Context7 with /dotnet/docs: .NET 10 SDK CLI behavior for build/test.`
- `Use Context7 with /dotnet/docs: can dotnet build target a .slnx solution?`
- `Use Context7: current PowerShell 7 pwsh -File syntax.`
- `Use Context7: current Playwright tracing config for failed tests.`
- `Use Context7 with /modelcontextprotocol/modelcontextprotocol: current MCP schema/tool contract docs.`

Repo cheat sheet: `docs/workflow/context7-usage.md`.

## Workflow/helper-app implementation language policy

From this point forward, do **not** add new live-test workflow brains, helper
apps, orchestration state machines, JSON/report processors, or multi-step
automation in PowerShell by default.

Use this split unless the user explicitly authorizes an exception:

| Layer | Default tool | Hard rule |
|---|---|---|
| User convenience launchers | `.cmd` | Keep dumb: `cd` to repo, call Python, pass through args. No JSON parsing, no branching-heavy workflow logic, no proof decisions. |
| Workflow automation / live-test orchestration | Python | Python owns state machines, subprocess calls, JSON parsing, age-budget timing, summaries, and fail-closed decisions. |
| Helper apps / operator tooling | Python first | Prefer Python for CLIs, TUIs, small local helper apps, report writers, and workflow utilities. |
| Low-level memory/process engine | Existing C#/.NET | Keep process-memory/readback/native engine code in the existing .NET projects unless a focused migration is requested. |
| PowerShell `.ps1` | Legacy leaf adapter only | Existing proven `.ps1` scripts may be called by Python, but do not create new PowerShell orchestration unless there is a narrow Windows-native reason and it is documented. |

Practical requirements for new workflow/helper code:

- Prefer `python .\scripts\<name>.py ...` as the real entry point.
- If a friendly launcher is needed, add a minimal `.cmd` wrapper that only calls
  Python and forwards `%*`.
- Use Python `subprocess.run([...])` argument lists; do not compose shell
  command strings for workflow control.
- Require child tools to emit JSON where possible; parse and validate that JSON
  in Python.
- Emit compact `run-summary.json` and, when useful, `run-summary.md` from the
  Python controller.
- Keep fail-closed states explicit, e.g. `target-drift`, `proof-expired`,
  `low-age-budget`, `dry-run-blocked`, `input-failed`, `post-readback-failed`.
- Do **not** rewrite all existing `.ps1` scripts just to satisfy this policy.
  First place Python above the proven scripts as the orchestrator; only port
  brittle PowerShell leaf scripts one at a time after behavior is locked.

## PowerShell 7 paste-safety policy

Interactive PowerShell command blocks must be treated as an operator interface, not
as an informal scratchpad. The repo assistant should prefer paste-safe,
low-ambiguity commands and avoid raw interactive flow-control blocks.

### Rules for assistant-generated PowerShell

| Situation | Required behavior |
|---|---|
| Simple read-only checks | Direct PowerShell paste is acceptable when commands are linear and do not depend on `if` / `else`, loops, or functions. |
| Branching, loops, functions, `try` / `catch`, here-strings, JSON parsing, or multi-step orchestration | Generate a `.ps1` or Python helper script and provide a single command to run it. Do not rely on interactive paste of complex PowerShell logic. |
| `if` / `else` logic | Do not provide raw multi-line `if` / `else` blocks for interactive paste unless the whole block is wrapped in a generated script file. This prevents standalone `else` parser failures when pasted in fragments. |
| Expected output, YAML, checklists, or interpretation notes | Keep them outside executable PowerShell blocks and label them clearly as `DO NOT PASTE`. |
| Git inspection commands | Use `git --no-pager` for `diff`, `log`, and similar commands to avoid pager stalls. |
| Git staging | Stage explicit paths only, such as `git add docs/recovery/current-truth.md`; never suggest `git add .` for repo workflow tasks. |
| Complex repo edits | Prefer Python applier scripts with validation, backup under `.riftreader-local/`, explicit path allowlists, and unified diff output. |
| Completion visibility | End runnable command blocks with a visible sentinel command when useful, such as `Write-Host "DONE"`, rather than ending with only a comment. |
| Local validation limits | If the assistant cannot execute the script in the user's Windows/PowerShell environment, it must say so and still proofread for PowerShell 7 syntax and paste safety. |

### Block labeling standard

Use these labels consistently:

| Label | Meaning |
|---|---|
| `RUN THIS` | Safe to paste into PowerShell as commands. |
| `SCRIPT CONTENT` | Save as a file or use an applier; do not paste line-by-line unless explicitly designed for it. |
| `DO NOT PASTE — expected output` | Reference only. |
| `DO NOT PASTE — checklist` | Reference only. |

### Default pattern

For anything beyond a short linear command sequence, create or update a local
script artifact, then run it with one command. This is the preferred pattern for
vibe-coding workflows in this repo because it reduces partial-paste failures,
keeps validation reproducible, and makes recovery easier after context switches.

## Python-first reusable helper policy

RiftReader recovery and development workflows should treat PowerShell as a
simple shell/launcher layer, not as the primary orchestration language.

### Tooling rules

| Situation | Required behavior |
|---|---|
| Short local checks | Simple PowerShell commands are acceptable. |
| Git status/log/add/commit/push | Simple PowerShell convenience blocks are acceptable, with explicit paths only. |
| Branching, loops, JSON parsing, validation, file generation, or multi-step recovery logic | Prefer Python helper scripts. |
| Existing proven `.ps1` scripts | Keep them when they are historically useful; call them as leaf helpers from Python rather than rewriting them without reason. |
| New repeatable recovery workflow | Implement as a tracked helper under `scripts/`, not as a disposable one-off block. |
| One-time documentation/text patch | A temporary applier under `.riftreader-local/` is acceptable if the logic has no reuse value. |

### Reusable-helper promotion criteria

A helper should be kept in the repo when it provides one or more of these:

| Criterion | Meaning |
|---|---|
| Repeated workflow | Likely to be used again after restarts, patches, target drift, or proof-anchor recovery. |
| Safety gate | Prevents unsafe movement, stale proof use, bad target selection, or accidental repo/provider writes. |
| Artifact contract | Writes durable JSON/Markdown summaries useful for handoffs and future sessions. |
| Operator value | Reduces manual copy/paste, repeated terminal logic, or context-loss risk. |
| Testability | Can be syntax-checked, dry-run validated, or regression-tested. |
| Historical continuity | Preserves proven repo behavior and avoids unnecessary churn. |

### Current workflow implication

Post-restart reacquisition, target-drift recovery, current-PID candidate
generation, candidate readback, proof-anchor rebuild, and handoff creation are
repeatable workflows. They should be implemented as Python-first helpers or
documented repo helper apps when practical. PowerShell wrappers should remain
thin launchers or proven leaf scripts.

## Python helper logging and blocker-reporting criteria

Larger or complex Python helpers must include built-in structured logging,
error capture, blocker reporting, and smoke-test support. Python orchestration is
more powerful than interactive shell commands, so the helper must leave enough
durable evidence to diagnose the next step without rerunning blindly.

### Required criteria for complex Python helpers

| Criterion | Required behavior |
|---|---|
| Structured summary | Write a durable JSON summary under `scripts/captures/` or another documented repo-owned output path. |
| Human summary | Write a compact Markdown summary when the helper produces operator-relevant evidence. |
| Explicit verdict | Use a top-level `status` such as `passed`, `blocked`, or `failed`; do not rely on console text alone. |
| Blocker list | Record `blockers` as explicit strings when the workflow cannot safely continue. |
| Warning list | Record `warnings` for non-fatal but important issues, such as candidate-only evidence or stale historical context. |
| Error capture | Record exception type, message, and where possible the failed stage. |
| Command envelopes | For every child process, record command arguments, working directory, exit code, stdout/stderr preview or artifact path, start/end time, and duration. |
| Absolute paths | Resolve output and child-script paths to absolute paths before invoking `.ps1`, `dotnet`, Git, or external helpers. |
| Timeout handling | Use finite timeouts for child processes unless a documented reason exists. |
| Fail-closed behavior | Stop on target mismatch, stale proof pointer, missing candidate, bad JSON, timeout, or unsupported state. |
| Safety state | Record `movementSent`, `inputSent`, `reloaduiSent`, `screenshotKeySent`, `noCheatEngine`, and provider-write state when relevant. |
| Artifact paths | Print and write summary paths so the next session can resume without guessing. |
| Recovery hints | Include a compact `next` or `recommendedActions` section when blocked or failed. |
| No hidden Git mutation | Do not stage, commit, push, pull, or modify refs unless the helper is explicitly a Git helper. |
| Smoke mode | Reusable helpers should support `--dry-run`, `--self-test`, or equivalent command-plan validation when practical. |

### Exit-code convention

| Exit code | Meaning |
|---|---|
| `0` | Completed successfully and the requested safe action passed. |
| `1` | Failed due to script error, malformed input, missing dependency, or unexpected exception. |
| `2` | Blocked safely by a known gate, such as target mismatch, stale pointer, missing candidate, or proof not current. |

### Minimum output contract

Complex helpers should emit or write a final compact object with at least:

```yaml
status: "passed | blocked | failed"
blockers: []
warnings: []
errors: []
artifacts:
  summaryJson: ""
  summaryMarkdown: ""
safety:
  movementSent: false
  inputSent: false
  noCheatEngine: true
  githubConnectorWrites: false
next:
  recommendedAction: ""
```

If a blocker occurs, the helper should preserve enough command output and artifact
paths for diagnosis. A blocked helper is acceptable; a silent or ambiguous helper
is not.

<!-- RIFTREADER_NON_CODEX_WORKFLOW_POLICY_START -->
## Non-Codex desktop ChatGPT workflow invariant

When Codex is unavailable, quota-blocked, or not being used, the assistant must use the RiftReader **non-Codex desktop ChatGPT workflow**.

Required behavior:

1. treat the GitHub connector as read-only unless the user explicitly authorizes a write in the current turn;
2. inspect repo files and commits read-only;
3. deliver repo edits as a downloadable ZIP package or clearly labeled local applier content;
4. prefer Python appliers with explicit target allowlists, backups under `.riftreader-local/`, JSON summaries, and diff output;
5. keep PowerShell pasted in chat short and linear;
6. avoid interactive PowerShell functions, loops, `try/catch`, JSON parsing, here-strings, or `exit` in pasted blocks;
7. separate apply/review from commit/push unless the user explicitly requests full automation;
8. use local Git only with explicit paths, never `git add .`;
9. verify remote commits through the GitHub connector read-only after the user pushes.

If the assistant needs to change docs or code, it should provide the package plus the exact extract/apply commands in chat. The user applies locally, reviews the diff, commits/pushes from PowerShell, and pastes the result for read-only verification.

ChatGPT MCP runtime invariant:

- The narrow ChatGPT MCP adapter and related scripts already exist; inspect
  `scripts\riftreader-chatgpt-mcp.cmd` and
  `docs/workflow/riftreader-chatgpt-mcp.md` before creating new launchers.
- Do not confuse `scripts\riftreader-bridge-tunnel-session.cmd` with the narrow
  ChatGPT MCP adapter; it is the Local Artifact Bridge tunnel lane.
- Do not treat a Codex-launched MCP server/tunnel as final proof for the
  non-Codex workflow. Final proof requires an operator-owned process started
  outside Codex.
- Stable public-host Server URL is the primary Web/Desktop path for this lane.
  The current stable target is `https://mcp.360madden.com/mcp`, routed through
  the persistent Cloudflare named Tunnel `riftreader-mcp-360madden` to the
  loopback MCP server at `http://127.0.0.1:8770`. The old
  Caddy/router/direct-public-IP route is deprecated legacy context, not a
  fallback. OpenAI Secure MCP Tunnel and `trycloudflare.com` quick tunnels remain
  retired paths, not backups, unless a future explicit policy reverses that
  decision.
- Before any actual-client proof or ChatGPT connector debugging, prove the
  runtime dependency chain in order. A saved ChatGPT connector entry is only
  configuration and **does not** start the local backend. Run
  `scripts\riftreader-mcp-server-status.cmd --json` and require
  `status=running-current` for the current lane. `not-running`,
  `foreign-listener`, or `running-legacy` are blockers; do not treat a busy port
  or stale proof artifact as a running current server.

Durable workflow doc: `docs/workflow/non-codex-desktop-chatgpt-workflow.md`.
<!-- RIFTREADER_NON_CODEX_WORKFLOW_POLICY_END -->

## Cross-repo ChromaLink boundary

- Treat ChromaLink as an external **provider** repo and RiftReader as a
  **consumer** unless the user explicitly authorizes a ChromaLink edit pass.
- Do not directly modify
  `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink` from a
  RiftReader-focused task to add fields, change schemas, adjust frame rotation,
  or update the typed client.
- If RiftReader needs more ChromaLink data, write a ChromaLink change request
  instead of silently editing the provider. Use
  `docs\chromalink-change-request-template.md`.
- A RiftReader-side integration may consume only explicit ChromaLink surfaces:
  `/api/v1/riftreader/world-state`, its schema endpoint, the HTTP bridge
  manifest, or a published `ChromaLink.Client` version.
- Never claim RiftReader integration is complete because ChromaLink provider
  tests passed; record separate RiftReader-side validation.

## Cross-repo RiftScan boundary

- Treat `C:\RIFT MODDING\Riftscan` as an external **candidate/evidence
  provider** for RiftReader unless the user explicitly authorizes a RiftScan
  edit or capture/write pass in the current conversation.
- Do not modify files under `C:\RIFT MODDING\Riftscan` from a RiftReader-focused
  task by default. Reading existing reports, sessions, handoffs, and generated
  artifacts is allowed when it helps RiftReader choose the best discovery path.
- When the boundary is "do not modify RiftScan", consume only existing RiftScan
  outputs such as `reports\generated\*-addon-coordinate-matches.json`,
  existing session candidate files, or paths recorded in
  `docs\recovery\current-proof-anchor-readback.json`.
- Do not run RiftReader wrappers in a mode that creates new RiftScan sessions or
  reports unless writes were explicitly authorized. In particular,
  `scripts\invoke-riftscan-coordinate-readback.ps1` without `-CandidateFile`
  can create RiftScan capture/session output; use an existing `-CandidateFile`
  or `scripts\riftscan_coordination.py` instead.
- When provider feedback is useful but RiftScan remains read-only, write a
  RiftReader-owned packet with `scripts\riftscan_feedback.py`; do not place
  feedback artifacts under `C:\RIFT MODDING\Riftscan`.
- After every major handoff/commit/push/discovery milestone, run
  `scripts\riftscan_milestone_review.py` for a combined strategy gate before
  expanding scope or attempting live work.
- Before committing this coordination lane, prefer
  `scripts\validate_riftscan_coordination.py` to rerun the no-CE/read-only
  RiftScan validation suite from one Python entry point.
- RiftScan candidates remain candidate evidence until RiftReader validates and
  promotes them with current PID/HWND proof. Never claim movement/navigation
  truth solely from a RiftScan provider artifact.

## Live movement / polling invariant

- **Current no-CE live boundary:** do **not** use Cheat Engine, CE Lua,
  CE debugger attach, CE breakpoints/watchpoints, or `cheatengine-exec.ps1` for
  live RIFT work unless the user explicitly re-authorizes CE in the current
  conversation after acknowledging the crash risk. If a required proof anchor
  cannot be refreshed without CE, fail closed and block movement instead of
  falling back to a stale/cached or heuristic source.
- **Coordinate freshness invariant:** do not call a coordinate value current
  just because an artifact PID/HWND still matches. PID/HWND/process-start match
  is only a targeting preflight. The default stale/non-stale proof is
  **API-now vs memory-now**: sample a fresh live API/runtime coordinate, read
  the memory coordinate from the candidate/anchor immediately, compare X/Y/Z
  deltas, and only treat the memory coordinate as current when the API source is
  fresh and the delta is within tolerance. If the API source is stale/missing,
  the memory read fails, or the delta exceeds tolerance, fail closed and treat
  the artifact coordinate as a timestamped snapshot/reacquisition seed only.
- Fresh API/runtime coordinate means ChromaLink `/api/v1/riftreader/world-state`
  with freshness/contract proof, an explicitly live ReaderBridge/in-game runtime
  surface, or another current live telemetry source. It does **not** mean
  `ReaderBridgeExport.lua`, any SavedVariables file, `rift.cfg`, or an old
  run-summary coordinate.
- Every coordinate freshness result must record API coordinate + timestamp,
  memory coordinate + timestamp/address/candidate, PID/HWND/process identity,
  per-axis deltas, tolerance, and verdict.
- For any **movement polling**, **forward-hold proof**, or other live
  coordinate-driven capture, resolve a **validated coord-trace anchor** first
  via `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1` and
  build the proof watchset from that anchor only.
- Treat the validated coord-trace coordinate triplet as the **canonical**
  movement source for proof runs.
- Allow the validated coord-trace proof source to resolve to either the traced
  object or the trace-linked source object, whichever still matches live
  ReaderBridge coordinates; do not force the raw traced object when it has
  drifted.
- Treat `read-player-current.ps1` and any `heuristic` or cached current-player
  anchor as **exploration-only** unless separately re-proven and explicitly
  promoted.
- For **proof reacquisition**, prefer **last-good trace seeds** and
  **debug-scanned selector/source-chain seeds** first; do **not** reseed proof
  tracing from heuristic or cached current-player snapshots.
- In proof reacquisition with access watchpoints, default to a **12-byte
  coord-triplet watch window** instead of a 4-byte scalar watch so `X/Y/Z`
  lane accesses can be re-proven from the same live source object.
- If proof reacquisition fails repeatedly, escalate to **debug scanning**
  instead of looping the same heuristic/bootstrap trace attempt.
- Use **debug tracing proactively**, not only after failures. When working on
  live coords, actor facing, or proof-watchset quality, use breakpoints,
  trace-cluster inspection, selector/owner tracing, and neighborhood scans to
  look for related fields, stronger offsets, pointer relationships, and better
  candidates before settling on a watchset.
- Treat selected-source coord lanes and other discovery artifacts as
  **candidate-only** unless they have been re-proven for the current session.
- If a proof watchset does not include the validated canonical
  `coord-trace-coords` region, treat that as a blocker instead of silently
  recording stale/candidate or heuristic data.

<!-- RIFTREADER_CURRENT_PID_FAMILY_RECOVERY_POLICY_START -->
## x64dbg static coordinate-chain invariant

- Keep **current proof-anchor recovery** and **player actor static-chain
  discovery** separate. A proof/API-family anchor can be movement-safe after
  same-target `ProofOnly`, but it is not a promoted actor static chain.
- Once a current proof anchor and credible actor-like candidate exist, stop
  repeating broad coordinate value scans by default. Freeze the actor-like
  candidate/owner hypothesis and pivot to provenance: owner layout, bounded
  access event, normalized instruction/module/RVA context, resolver generation,
  API-now vs chain-now validation, then restart validation.
- The durable optimized workflow is
  `docs/recovery/optimized-player-actor-coordinate-chain-workflow.md`; the
  10-phase checklist is
  `docs/recovery/static-coordinate-chain-10-phase-plan-2026-05-21.md`.
- Treat x64dbg coordinate access events as candidate evidence only until they
  are converted into a repo-owned chain resolver and validated against fresh
  API/runtime coordinates.
- Do not attach x64dbg to `rift_x64.exe` unless the user explicitly authorizes a
  live-debugger session in the current conversation.
- Default x64dbg sequence for static actor-chain discovery is bounded:
  `stop-context` attach/detach first, verify the RIFT window still responds,
  then at most one short targeted hardware watchpoint per explicit decision.
  Do not loop watchpoints, use broad debugger scanning, or use memory-access
  breakpoints by default.
- Normalize manual watchpoint/access events with
  `scripts/x64dbg_access_event_ingest.py`; the helper must stay offline-only and
  must not send input, read live memory, configure MCP, or promote movement
  truth.
- A stable coordinate chain requires module/RVA or static-owner provenance,
  multi-pose API-now versus chain-now agreement, restart validation, and the
  existing same-target ProofOnly gate before any movement/navigation use.

## Current-PID coordinate-family recovery invariant

If the live RIFT PID/HWND changes and `ProofOnly` blocks with target drift, the assistant must not fall back to narrow stale-pointer probing.

Required behavior:

1. state that the tracked proof pointer is stale for the new process epoch;
2. rediscover or confirm the current PID/HWND;
3. immediately invalidate `docs/recovery/current-proof-anchor-readback.json`
   to a `blocked-target-drift` blocker for the discovered PID/HWND and preserve
   the old pointer under `docs/recovery/historical/`;
4. refuse to use the stale pointer's `candidateId`, `matchFile`, absolute
   address, or `movementAllowed=true` fields except as historical
   reacquisition hints;
5. run no-movement target-control and visual gate checks for the current target
   when they send no input and change no game state;
6. use the no-movement current-PID recovery lane: fresh API/runtime reference,
   memory inventory, scan-plan batch or broad coordinate-family scan, and
   candidate JSONL/readback artifacts;
7. after a candidate matches API-now vs memory-now in the current pose,
   recommend controlled displacement stimulus testing, but do not send it
   without explicit approval;
8. validate candidates across poses before promotion;
9. keep `--movement-approved`, `--allow-current-truth-update`, and
   `--run-proofonly` as separate explicit gates;
10. block movement/navigation use until same-target `ProofOnly` passes.

Never describe an old absolute proof address, stale proof-pointer candidate,
nearby offset probe, SavedVariables snapshot, or single-pose candidate as
current movement truth. If the current PID/HWND is known, code must prefer that
fresh target identity over any cached artifact that points to another PID/HWND.
<!-- RIFTREADER_CURRENT_PID_FAMILY_RECOVERY_POLICY_END -->

## Cheat Engine preservation

- Treat live Cheat Engine work as potentially ephemeral until the repo has a
  durable copy.
- When a CE table contains reverse-engineering state that would be expensive to
  reconstruct, save a `.ct` snapshot before closing CE, restarting Rift, or
  changing branches.
- Store durable CE tables under
  `C:\RIFT MODDING\RiftReader\artifacts\cheat-engine\tables\`, not under
  `scripts\cheat-engine\`, because the latter is ignored as generated/local
  helper output.
- Pair saved `.ct` files with a short note covering date, branch, target
  process/build, and what the table proves or is still pending.

See `C:\RIFT MODDING\RiftReader\docs\assistant-operating-policy.md` for the
longer decision tree and examples.

<!-- RIFTREADER_CSHARP_SENDINPUT_SCANCODE_PROOF_20260511_START -->
## RiftReader live-input backend rule — 2026-05-11

For RIFT movement/backend diagnostics:

- Prefer repo-owned C# `tools/RiftReader.SendInput` via `scripts/send-rift-key-csharp.ps1`.
- Use `--input-mode ScanCode` first for SendInput movement tests.
- Treat legacy `scripts/send-rift-key.ps1` as diagnostic/legacy, not the authoritative SendInput implementation.
- Preserve `scripts/post-rift-key.ps1 -SkipBackgroundFocus -UseWindowMessage` as a working exact-HWND window-message backend.
- Do not auto-send `Esc`; chat/text-entry mode is operator-managed until a reliable detector exists.
- Keep pasted chat commands minimal. If a workflow repeats, add or use a repo-owned helper rather than creating untracked inline scripts.
- Backend calibration may use fresh API coordinate before/after without requiring a current proof anchor. Navigation/proof promotion still requires the normal proof gates.

Proof reference: `docs/recovery/csharp-sendinput-scancode-proof-2026-05-11.md`.
<!-- RIFTREADER_CSHARP_SENDINPUT_SCANCODE_PROOF_20260511_END -->
