# Codex agent routing policy

Status date: 2026-05-12

## Verdict

When using Codex for RiftReader, default to **quota-aware routing**:
use lower reasoning / lower-intelligence execution only when the task is
bounded, reversible, and easy to validate. Use stronger reasoning for anything
that can corrupt truth, mutate live state, weaken gates, or make a hard-to-undo
decision.

Also default to **practical parallelism**: spawn subagents up to the practical
maximum when independent work can run in parallel without overlapping edits or
duplicating analysis.

This is a permanent Codex workflow rule for this repo, not a one-turn
preference.

## Core rule

| Principle | Required behavior |
|---|---|
| Save quota safely | Use lower reasoning for mechanical, reversible, evidence-light tasks. |
| Fail closed on risk | Use stronger reasoning when a mistake can poison proof, movement, live-debugger state, schema contracts, or repo history. |
| Parallelize where useful | Spawn agents for independent read-only discovery, independent docs research, or disjoint implementation slices. |
| Keep ownership centralized | The main agent owns risk classification, integration, validation, commit, push, and final claims. |
| Validate before trusting | Lower-reasoning work is acceptable only when targeted validation can catch likely mistakes. |

## OpenCode retirement boundary

OpenCode is **retired/demoted for RiftReader**. Do not route work through
OpenCode and do not modify OpenCode integration surfaces unless the user
explicitly re-authorizes OpenCode in the current conversation.

| Surface | Policy |
|---|---|
| `tools/riftreader_workflow/opencode_bridge.py` | Historical/deprecated maintenance surface; no new work by default. |
| OpenCode wrappers, prompt tests, `.opencode` templates, or OpenCode docs | Do not expand or harden unless explicitly re-authorized. |
| Decision-packet/local-agent workflows | Prefer Codex-native use of the decision packet and Operator Lite read-only surfaces. |
| Old plan text mentioning OpenCode | Treat it as stale unless this retirement boundary has been explicitly overridden. |

## Autonomous continuation mode

When the user asks Codex to keep working autonomously, the main agent must keep
advancing through safe local milestones instead of stopping at routine
checkpoints. This rule does not weaken live/debugger/proof/Git-push gates.

### Continue through soft checkpoints

These events are **not** stop conditions:

| Event | Required continuation |
|---|---|
| Safe validation passed | Record the result and continue to the next safe practical step. |
| Known helper/status blocker returned exit code `2` | Treat as `blocked-safe`; run the listed safe diagnostic or choose another safe local slice. |
| Worktree is clean | Refresh the decision packet/status and continue unless only gated work remains. |
| Branch is ahead of origin | Report it; do not push without approval; continue safe local work if available. |
| Local commit created | Record the commit hash, refresh packet/status, and continue. |
| Ignored `.riftreader-local` artifacts were written | Treat as status evidence and continue. |
| Decision packet reports `blocked-safe` | Follow `safeNextAction` when safe; do not escalate into live/proof actions. |
| Status question answered | If the user did not explicitly request "status only", answer briefly and continue safe work. |
| Milestone completed | Announce with a prominent banner, then move to the next safe milestone. |

### Stop only for hard gates

Ask for explicit approval before any of these:

| Hard gate | Required behavior |
|---|---|
| Live RIFT input, movement, target-control, visual gate, or ProofOnly | Stop and request approval. |
| x64dbg, Cheat Engine, debugger attach, breakpoints, or watchpoints | Stop and request approval with risk context. |
| Provider repo writes | Stop unless explicitly authorized in the current turn. |
| Proof promotion or actor-chain promotion | Stop and cite required gates. |
| Git push, branch rewrite, destructive cleanup/delete, or remote mutation | Stop and ask; local commits remain explicit-path only. |
| Unexpected validation failure | Diagnose narrowly before broadening or continuing. |
| Ambiguous scope with high blast radius | Ask the smallest concrete approval question. |

### Default autonomous execution loop

1. Refresh `.\scripts\riftreader-decision-packet.cmd --compact-json --write`.
2. Follow safe, non-mutating `safeNextAction` when possible.
3. If dirty, run targeted safe validations.
4. Commit coherent validated local slices with explicit paths only.
5. After each commit, refresh status/packet and continue.
6. Continue until a hard gate is the next required step or no useful safe local
   work remains.

## Reasoning/intelligence routing

| Task class | Default route | Why |
|---|---|---|
| Formatting, tables, typo fixes, status boards | Lower reasoning | Mechanical and easy to review. |
| Docs-only additions with known source material | Lower or medium reasoning | Low blast radius; cite sources and validate diff. |
| Read-only repo search / inventory | Lower reasoning, often subagent-friendly | No state mutation. |
| Small single-file code/test change with deterministic behavior | Medium reasoning | Reversible but still needs validation. |
| Multi-file behavior change | Medium or high reasoning | Integration risk requires main-agent review. |
| Unclear bug / conflicting evidence | High reasoning | Root-cause quality matters. |
| x64dbg, reverse-engineering, proof-watchsets, coordinate truth | High or extra-high reasoning | Bad promotion can poison future movement/proof. |
| Live RIFT input, movement, target selection, exact HWND/PID control | High or extra-high reasoning | High blast radius if wrong. |
| Commit/push decision | Main agent review; do not delegate final decision blindly | Repo history is durable. |

## Lower-reasoning allowlist

Lower-reasoning work is allowed when **all** are true:

1. the task is bounded and easy to describe;
2. file ownership is clear or the task is read-only;
3. the task does not decide durable truth;
4. the task does not touch live input, debugger attach, process memory, or
   coordinate/facing promotion;
5. validation is available or the output is easily reviewable;
6. rollback is obvious.

Examples:

| Allowed lower-reasoning task | Validation |
|---|---|
| Convert a status paragraph to a table | Human diff review. |
| Search docs for existing policy hooks | Read-only output. |
| Add citations to an existing docs note | Link/source review plus `git diff --check`. |
| Write a small wrapper around an existing tested helper | Targeted unit test or `--self-test`. |
| Summarize latest git status/log | Git command output. |

## Lower-reasoning hard blocks

Do **not** route these to lower reasoning:

| Hard block | Reason |
|---|---|
| Live movement/input behavior | Wrong action can move the character or affect game state. |
| RIFT window/PID/HWND targeting decisions | Wrong target can send input to the wrong process/window. |
| x64dbg / Cheat Engine live attach, watchpoints, breakpoints, or debugger control | Debugger state is high risk and can destabilize the client. |
| Coordinate, actor-facing, camera, source-chain, or proof-watchset promotion | False truth is expensive to unwind. |
| Schema/provider contracts across ChromaLink/RiftScan/RiftReader | Contract drift can break consumers. |
| Guard weakening or stale-data policy changes | Can silently degrade safety. |
| Risky merges, branch rewrites, broad refactors | Hard to rollback safely. |
| Commit/push after mixed worktree or uncertain scope | Durable repo history needs main-agent review. |

## Subagent parallelism policy

Use subagents **up to the practical maximum** when they materially reduce elapsed
time and the work can be separated cleanly.

| Situation | Subagent use |
|---|---|
| Multiple independent read-only questions | Spawn parallel explorers. |
| Docs/source research independent from local code inspection | Spawn a researcher/explorer while main agent inspects repo. |
| Implementation can be split by disjoint file ownership | Spawn workers with explicit write scopes. |
| Validation can run while non-overlapping implementation continues | Spawn a validator only if it does not race file edits. |
| Tiny single-file change | Do not spawn unless there is a separate useful side question. |
| Urgent blocker on the critical path | Main agent handles it locally instead of waiting. |

### Required subagent contract

Every delegated task must state:

1. exact scope;
2. whether it is read-only or write-capable;
3. owned files/modules if editing;
4. files it must not touch;
5. expected output;
6. risk class;
7. validation requested, if any.

Workers must be told they are not alone in the codebase and must not revert or
overwrite others' work.

## Main-agent responsibilities

Even when lower reasoning or subagents are used, the main agent must:

| Responsibility | Required behavior |
|---|---|
| Risk classification | Decide whether lower reasoning is safe before delegating. |
| Coordination | Avoid duplicated work and overlapping edits. |
| Integration | Review subagent output before applying or committing. |
| Validation | Run targeted tests/lint/diff checks in the main thread when practical. |
| Safety | Enforce live/debugger/movement/coord-truth boundaries. |
| Final claims | State only what was actually changed and validated. |
| Commit/push | Stage explicit paths only and push only coherent, validated slices. |

## Escalation rule

Escalate from lower/medium to stronger reasoning when any of these occur:

| Trigger | Response |
|---|---|
| First non-obvious failure | Gather evidence; keep scope narrow. |
| Second similar failure | Increase reasoning and restate root cause from observed facts. |
| Third similar failure | Stop repeating the pattern; change tactics. |
| Evidence conflicts | Rebuild the plan from source artifacts. |
| Safety boundary becomes relevant | Switch to stronger reasoning immediately. |
| Validation fails unexpectedly | Diagnose before patching symptoms. |

## Default execution pattern

1. Classify task risk.
2. Split into independent subtasks if useful.
3. Spawn subagents only for non-overlapping work.
4. Keep the main agent on the critical path.
5. Integrate results.
6. Validate.
7. Commit/push only coherent, explicit paths when requested or needed for the
   milestone.
8. Summarize routing, changes, validation, and remaining uncertainty.

## Quick checklist

| Question | If yes |
|---|---|
| Is this docs/status/search-only? | Lower reasoning/subagent is usually safe. |
| Is this reversible, single-file, and testable? | Medium reasoning may be enough. |
| Does this touch live RIFT/debugger/coordinate proof/movement? | Stronger reasoning only. |
| Can subtasks run independently? | Spawn agents up to the practical maximum. |
| Are files or responsibilities overlapping? | Do not parallelize edits until ownership is clear. |
| Is final repo history affected? | Main agent reviews, stages explicit paths, validates, then commits/pushes. |
