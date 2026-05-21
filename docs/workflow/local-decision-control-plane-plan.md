# Local Decision Control Plane Plan

Status: **implementation v0 landed; helper/validation/packet reminders available**
Created: 2026-05-21
Implemented: 2026-05-21
Scope: RiftReader repo workflow acceleration and safety gating

## Post-v0 hardening checkpoint

As of the current implementation, the control plane also includes these
defensive/resilience hardening slices:

| Area | Implemented behavior |
|---|---|
| Malformed tracked JSON | Malformed `current-truth.json` or `current-proof-anchor-readback.json` fails closed with structured packet errors and `targetEpoch.status = invalid-artifact`. |
| CLI malformed JSON output | `--compact-json` emits a structured failed decision packet and exits `1` for malformed tracked truth/proof JSON instead of dumping an unstructured traceback. |
| Proof-only target epoch | A current proof artifact without a current-truth target now stays `in-world-unproven` with `current-truth-target-missing` instead of being treated as current. |
| Ignored cache corruption | Corrupt `.riftreader-local\decision-packet\latest\*` cache artifacts are treated as cache misses and rebuilt; they do not block packet generation. |
| Dirty-file cache invalidation | Cache fingerprints include dirty tracked file path, Git status, mtime, and size so edits to the same dirty path cannot reuse a stale packet. |
| Schema contract | Full and compact packet schema tests protect required packet/reminder/validation/commit-plan fields. |
| Schema contract CLI | `--schema-json` emits required top-level fields, valid milestone states, commit-plan fields, and safety flags without building a repo packet. |
| OpenCode prompt integration | OpenCode prompt self-test now requires embedded `decisionPacket`, `safeNextAction`, `llmReminder`, and `milestoneStatus` fields. |
| OpenCode commit-ready reminders | OpenCode prompts detect `commit-ready-explicit-paths` and tell agents to review status plus `commitPlan.stageCommand/stageCommandPreview` instead of rerunning identical safe checks. |
| Operator Lite smoke | `--decision-packet --json` has smoke coverage for `--write --compact-json`, safe-blocked exit `2`, and captured packet JSON output. |
| Operator Lite JSON passthrough | Operator Lite command runs parse JSON stdout into `stdoutJson` so consumers can read decision-packet fields like `commitPlan.stageCommand` without parsing raw console text. |
| Commit planner messages | Code-only workflow-helper slices no longer fall back to docs-only suggested commit messages. |
| Commit planner stage command | `commitPlan.stageCommand` emits an argument array `["git", "add", "--", ...]`; `stageCommandPreview` uses `git add -- <paths>` and quotes spaces/metacharacters for humans; Markdown packets render both. |
| Post-validation reminders | After `--run-safe-checks` passes and `commitPlan.recommended` is true, `safeNextAction` switches to `commit-ready-explicit-paths` status/commit-plan review instead of looping safe checks. |

## Verdict

RiftReader should move repeated deterministic decisions from the LLM to local
Python helpers. The local PC should collect evidence, classify lanes, fail closed
on stale/live-risk state, recommend exact next commands, and emit compact
machine-readable decision packets. The LLM should then focus on strategy,
review, code changes, and high-risk approvals.

This is a workflow-control-plane project. It is **not** a movement, yaw,
auto-turn, proof-promotion, CE, or x64dbg project.

## Primary goal

Add one local read-only decision packet command that answers:

| Question | Local decision output |
|---|---|
| What lane is active? | `actor-chain`, `proof-recovery`, `mcp`, `package`, `docs`, `git`, `unknown` |
| Is the target epoch current? | `current`, `stale`, `absent`, `character-select`, `in-world-unproven`, `unknown` |
| What is blocked? | Movement, debugger attach, CE, provider writes, proof promotion, commit/push |
| What is the safest next action? | Exact command array or stop/ask-for-approval action |
| What validation is needed? | Checks inferred from changed files and lane risk |
| What can agents work on safely? | Non-overlapping file/task slices with ownership boundaries |

## Command surface

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-decision-packet.cmd --compact-json
```

| Mode | Purpose |
|---|---|
| `--json` | Full machine-readable packet |
| `--compact-json` | Small packet for LLM/OpenCode prompts |
| `--write` | Write ignored JSON/Markdown under `.riftreader-local` |
| `--run-safe-checks` | Run only packet-approved safe validations and attach command envelopes |
| `--use-cache` | Reuse ignored packet artifacts only when a fresh fingerprint exactly matches; disabled by `--run-safe-checks` |
| `--self-test` | Validate rule fixtures without live reads/input |
| `--schema-json` | Emit the static packet schema contract without building a repo packet |
| `--explain` | Human-readable explanation of the current decision |
| `--lane <name>` | Force lane-specific summarization |
| `--agent-plan` | Emit parallel-agent-safe work slices |

Proposed ignored outputs:

```text
.riftreader-local\decision-packet\latest\decision-packet.json
.riftreader-local\decision-packet\latest\decision-packet-compact.json
.riftreader-local\decision-packet\latest\decision-packet.md
.riftreader-local\decision-packet\latest\fingerprint.json
```

Markdown output from `--explain` and `decision-packet.md` must render:

| Section | Required visible cue |
|---|---|
| LLM reminder | `# **🚦 NEXT ACTION — CONTINUE SAFELY**` and `## **🔄 DO NOT STOP HERE**` |
| Commit planner | `# **✅ COMMIT-READY — EXPLICIT PATHS ONLY**` or `# **⚠️ NOT COMMIT-READY**` |
| Performance | Build mode, cache reuse, safe-check count, validation duration, and total duration |

These sections are operator/agent guidance only; they do not authorize live
input, debugger/CE, provider writes, proof promotion, actor-chain promotion, or
Git push.

Exit-code convention:

| Exit code | Meaning |
|---:|---|
| `0` | Packet generated and read-only/status use is safe |
| `2` | Packet generated but the workflow is safely blocked |
| `1` | Helper error, malformed input, missing dependency, or unexpected failure |

## Non-negotiable boundaries

| Boundary | Rule |
|---|---|
| Live input / movement | Never authorized by the decision packet alone |
| x64dbg / CE | Never attach unless explicitly approved in the current conversation |
| Coordinate / actor-chain promotion | Block unless current proof, provenance, resolver, restart/relog validation, and final ProofOnly pass |
| Stale absolute addresses | Historical hints only after PID/HWND/process-start drift |
| SavedVariables | Never live truth |
| Provider repos | RiftScan/ChromaLink read-only unless explicitly authorized |
| Git mutation | The helper may recommend explicit paths, but must not stage/commit/push |
| Generated artifacts | Do not recommend staging ignored/generated capture output |
| Safety default | Fail closed with `blocked`, not vague `maybe safe` states |

## Autonomous continuation rule

The decision control plane exists to keep safe local work moving without making
the LLM rediscover routine state. When the user has asked for autonomous work,
the packet, docs, and future agents must treat routine checkpoints as
**continue signals**, not stop signals.

### Do not stop for routine checkpoints

| Checkpoint | Continue behavior |
|---|---|
| Safe validation passed | Continue to the next safe command or milestone. |
| Known helper/status blocker returned exit code `2` | Treat as `blocked-safe`; run the listed safe diagnostic or next safe local slice. |
| Worktree is clean | Refresh the packet and continue unless only gated work remains. |
| Branch is ahead of origin | Report it; do not push without approval; continue safe local work when useful. |
| Local commit created | Record the hash, refresh packet/status, and continue. |
| Ignored `.riftreader-local` artifacts written | Treat as local evidence and continue. |
| Packet says `blocked-safe` | Follow `safeNextAction` when safe; do not drift into live/proof actions. |
| Milestone completed | Announce with the big milestone banner, then start the next safe milestone. |

### Hard stops remain gated

Autonomy does **not** authorize live input, movement, target-control, visual gate,
ProofOnly, x64dbg, Cheat Engine, provider writes, proof promotion,
actor-chain promotion, Git push, branch rewrites, destructive cleanup, or remote
mutation. If one of those is required, stop and ask for explicit approval with
the exact command/action that would run after approval.

### Default autonomous loop

1. Refresh the decision packet:
   `.\scripts\riftreader-decision-packet.cmd --compact-json --write`.
2. Follow the packet's safe, non-mutating `safeNextAction`.
3. For dirty worktrees, run safe validations.
4. Commit coherent validated local slices using explicit paths only.
5. After commit, refresh the packet and continue.
6. If only gated remote/live/debugger/proof work remains, stop and ask.

## Key definitions

| Term | Meaning |
|---|---|
| Decision packet | Local JSON/Markdown output summarizing repo state, target epoch, blockers, safe next action, validation plan, and agent-safe work slices |
| Target epoch | `{ processName, pid, hwnd, processStartUtc, moduleBase, windowTitle }` |
| Current proof | Fresh same-target proof, not merely a matching PID/HWND |
| Candidate-only | Useful evidence that cannot be promoted or used for movement |
| Lane | Current workflow class, such as actor-chain, proof recovery, MCP, package, docs, or Git |
| Hard blocker | A local rule that forbids an action until conditions change |
| Agent ownership | A non-overlapping file/task boundary for parallel workers |

## Packet schema draft

```json
{
  "schemaVersion": 1,
  "kind": "riftreader-decision-packet",
  "generatedAtUtc": "...",
  "status": "passed | blocked | failed",
  "lane": "actor-chain | proof-recovery | package | mcp | docs | git | unknown",
  "risk": "low | medium | high | critical",
  "repo": {
    "branch": "main",
    "ahead": 0,
    "behind": 0,
    "dirty": false,
    "changedFiles": []
  },
  "targetEpoch": {
    "status": "current | stale | absent | character-select | in-world-unproven | unknown",
    "processName": "rift_x64",
    "pid": null,
    "hwnd": null,
    "processStartUtc": null,
    "moduleBase": null,
    "blockers": []
  },
  "truth": {
    "proofAnchor": {
      "status": "passed | stale | missing | blocked",
      "candidateOnly": false
    },
    "actorChain": {
      "status": "candidate-only | promoted | blocked | unknown",
      "promotionAllowed": false,
      "blockers": []
    }
  },
  "allowedActions": [
    "read_repo",
    "write_local_status_artifacts"
  ],
  "forbiddenActions": [
    "movement",
    "x64dbg_attach",
    "cheat_engine",
    "provider_write",
    "proof_promotion"
  ],
  "safeNextAction": {
    "key": "actor-chain-status",
    "command": ["python", ".\\scripts\\actor_chain_no_debug_status.py", "--json"],
    "why": "Current actor-chain evidence remains candidate-only."
  },
  "validationPlan": [],
  "commitPlan": {
    "recommended": false,
    "explicitPaths": []
  },
  "agentPlan": [],
  "cacheStatus": "not-checked | hit | miss | reused",
  "performance": {
    "buildMode": "fresh | cache-reused",
    "cacheReused": false,
    "runSafeChecks": false,
    "safeValidationCommandCount": 0,
    "safeValidationDurationSeconds": 0.0,
    "totalDurationSeconds": 0.0
  },
  "blockers": [],
  "warnings": []
}
```

## Phase map

| Phase | Name | Goalpost | Risk | Output |
|---:|---|---|---|---|
| 0 | Plan + contract | Freeze schema, boundaries, and first command surface | Low | This tracked plan |
| 1 | Read-only MVP | Aggregate Git, current truth, proof, and actor-chain status | Low | `decision_packet.py`, wrapper, tests |
| 2 | Target-epoch resilience | Detect stale PID/HWND/process-start/module-base truth | Medium | Hard restart/update blockers |
| 3 | Lane classifier | Pick workflow lane/risk from local evidence | Low/Medium | `lane`, `risk`, `safeNextAction` |
| 4 | Validation planner | Recommend tests/checks from changed files and lane | Low | `validationPlan` |
| 5 | Commit-scope planner | Recommend explicit paths; exclude generated output | Medium | `commitPlan` |
| 6 | Agent work planner | Emit non-overlapping agent-safe work slices | Medium | `agentPlan` |
| 7 | OpenCode/local-agent integration | Feed packet into adaptive prompts | Medium | Smaller prompts, safer local agents |
| 8 | Operator Lite integration | Add safe button/readout for packet | Low | UI workflow acceleration |
| 9 | Hardening + caching | Add fingerprints, invalidation, regression tests | Medium | Faster repeated runs |
| 10 | v1 gate | Make packet the first repo-work command | Medium | Documented workflow standard |

## Current v0 implementation status

| Area | Status | Notes |
|---|---|---|
| Read-only packet MVP | ✅ Implemented | `tools/riftreader_workflow/decision_packet.py`, `scripts/riftreader-decision-packet.cmd`, and `scripts/test_decision_packet.py` |
| Safe validation runner | ✅ Implemented | `--run-safe-checks` executes only packet-selected safe commands and records command envelopes |
| Restart/update resilience | ✅ Implemented in packet fixtures | PID/HWND/process-start/module-base/proof-age drift blocks proof reuse; process presence is never proof |
| Commit planner | ✅ Implemented as non-mutating planner | Emits explicit paths, generated exclusions, validation gate, and stage preview only |
| Agent planner | ✅ Implemented | Emits non-overlapping ownership slices and reminds that the main agent owns integration/commit |
| Operator Lite integration | ✅ Implemented | Safe `Refresh Decision Packet` command/button; no live/debugger/Git action added |
| OpenCode integration | ✅ Implemented | Prompt builder includes compact decision packet before broader repo context |
| Cache/speed hardening | ✅ v0 implemented | Fingerprint covers helper version, Git HEAD, changed files, current-truth/proof mtimes/sizes; cache is opt-in, ignored-local only, and disabled for safe validation runs |

## Milestones

### Milestone 0 — durable planning artifact

| Field | Requirement |
|---|---|
| Goal | Save the plan and cross-link related workflow docs |
| Files | `docs/workflow/local-decision-control-plane-plan.md` plus concise references in related workflow docs |
| Done when | Plan records phases, schema, boundaries, restart rules, and agent ownership rules |
| Validation | `git diff --check` |
| No-go boundaries | No helper code, no live target reads, no Git mutation inside any helper |

### Milestone 1 — MVP decision packet

| Field | Requirement |
|---|---|
| Goal | One command emits compact repo/workflow decision state |
| Files | `tools/riftreader_workflow/decision_packet.py`, `scripts/riftreader-decision-packet.cmd`, `scripts/test_decision_packet.py` |
| Inputs | Git status, current truth JSON, current proof pointer, existing helper outputs when available |
| Outputs | `.riftreader-local\decision-packet\latest\decision-packet.json/.md` |
| Done when | `--self-test`, `--json`, `--compact-json`, and `--write` work |
| Validation | `python -m unittest scripts.test_decision_packet`, `python -m py_compile ...`, `git diff --check` |
| Boundary | Read-only except ignored `.riftreader-local` output |

### Milestone 2 — target-epoch / restart resilience

| Field | Requirement |
|---|---|
| Goal | Prevent stale PID/HWND/address reuse after game restart or patch/update |
| Rule | If PID/HWND/process-start/module-base differ, mark old proof/address as historical only |
| Done when | Packet distinguishes `current`, `stale`, `absent`, `character-select`, and `in-world-unproven` |
| Validation | Fixture tests for PID drift, HWND drift, process-start drift, module-base drift, missing process-start |
| Critical blocker | Never classify a visible `rift_x64` process as current movement proof |

### Milestone 3 — actor-chain lane rules

| Field | Requirement |
|---|---|
| Goal | Encode current actor-chain candidate-only rules locally |
| Inputs | `scripts\actor_chain_no_debug_status.py --json` and current-truth artifacts |
| Done when | Packet reports `promotionAllowed=false` unless all promotion gates pass |
| Hard blockers | `blocked-no-debugger-access-provenance`, `no-static-resolver-promoted`, `not-restart-validated`, `no-debug-root-lanes-exhausted` |
| Validation | Unit tests for candidate-only, promoted, missing artifact, stale proof |

### Milestone 4 — validation planner

| Field | Requirement |
|---|---|
| Goal | Stop asking the LLM to decide obvious checks |
| Examples | Python files -> `py_compile` + focused unit tests; docs only -> `git diff --check`; workflow helpers -> helper `--self-test` |
| Done when | Packet includes `validationPlan.commands[]` |
| Boundary | Planner recommends commands; it does not run them unless an operator/agent explicitly chooses to run validation |

### Milestone 5 — commit-scope planner

| Field | Requirement |
|---|---|
| Goal | Make "what needs committing?" local and deterministic |
| Rules | Explicit paths only; never `git add .`; exclude ignored/generated captures |
| Done when | Packet emits `commitPlan.recommended`, `explicitPaths`, `excludedGeneratedPaths`, and `suggestedMessage` |
| Validation | Fixtures for docs-only, code+test, generated-output-only, and mixed-risk worktrees |

### Milestone 6 — agent-safe work planner

| Field | Requirement |
|---|---|
| Goal | Allow multiple agents to work without merge conflicts |
| Output | `agentPlan[]` with task, risk, read/write authority, owned files, and forbidden files |
| Done when | Packet can split docs, tests, helper code, and validation into non-overlapping slices |
| Boundary | Main agent still owns final integration, validation, commit, and push |

### Milestone 7 — OpenCode / local-agent prompt integration

| Field | Requirement |
|---|---|
| Goal | Shrink prompts and improve speed by feeding agents the packet |
| Integration | `opencode_bridge.py` reads the decision packet first |
| Done when | Prompt includes packet summary, lane policy, allowed edit paths, and blockers |
| Boundary | OpenCode remains optional and no-input/no-debugger by default |

### Milestone 8 — Operator Lite integration

| Field | Requirement |
|---|---|
| Goal | Add a safe operator button/readout |
| UI button | `Refresh Decision Packet` |
| Done when | Operator Lite can show status, lane, risk, blockers, and safe next command |
| Boundary | No movement/debugger/Git buttons are added |

### Milestone 9 — cache + fingerprint acceleration

| Field | Requirement |
|---|---|
| Goal | Avoid recomputing unchanged repo state |
| Fingerprint inputs | Git HEAD, changed files, key artifact mtimes/sizes, current-truth mtime, proof pointer mtime, helper version |
| Done when | Packet says `cacheStatus: hit | miss | reused` and includes `performance` timing fields |
| Invalidated by | Git change, target epoch change, current-truth/proof artifact change, helper version change |
| Boundary | Cache cannot override safety blockers |

Performance fields are operator evidence only. They must not be used to suppress
target-epoch checks, proof blockers, validation failures, or explicit approval
gates.

### Milestone 10 — production gate

| Field | Requirement |
|---|---|
| Goal | Make the decision packet the first command before repo work |
| Done when | Handoff templates and workflow docs say to start with `riftreader-decision-packet.cmd --compact-json` once implemented |
| Validation | Existing workflow-status and actor-chain helpers still pass |
| Boundary | Decision packet is a gate, not a live-action executor |

## Restart / game-update resilience model

| Threat | Local packet behavior |
|---|---|
| RIFT restarts with a new PID | Mark old proof/current addresses stale |
| HWND changes | Mark old target identity stale |
| Process start changes with same PID reused | Mark old artifacts stale |
| Module base changes | Require static/module assumptions to be revalidated |
| Heap absolute address changes | Treat as historical hint only |
| Proof file older than process start | Mark stale |
| Artifact lacks process-start identity | Treat as weak evidence; require revalidation before promotion |
| Visible `rift_x64` process exists | Process presence only, not in-world/current proof |
| Character-select screen | Block movement |
| SavedVariables updated | Post-save snapshot only, not live truth |
| Actor candidate matches current PID once | Candidate-only until provenance/restart gates pass |
| Game patch/update suspected | Require fresh proof and do not trust offsets blindly |

Target epoch comparison:

| Comparison | Verdict |
|---|---|
| PID, HWND, process-start, and module-base all match | Same epoch |
| PID/HWND match but process-start missing | Weak match; no promotion |
| PID/HWND match but process-start changed | Stale |
| PID differs | Stale |
| HWND differs | Stale |
| Module base changed | Revalidate static/module assumptions |
| No live target | Offline/status only |

## Parallel-agent model

| Workstream | Can run in parallel? | Owned files | Risk |
|---|---:|---|---|
| Docs/plan writer | Yes | `docs/workflow/local-decision-control-plane-plan.md` | Low |
| Schema/test-fixture writer | Yes | `scripts/test_decision_packet.py` and optional fixtures | Low |
| Core packet implementation | Yes, isolated | `tools/riftreader_workflow/decision_packet.py` | Medium |
| CMD wrapper | Yes, tiny | `scripts/riftreader-decision-packet.cmd` | Low |
| Operator Lite integration | Later only | `tools/riftreader_workflow/operator_lite.py` | Medium |
| OpenCode bridge integration | Later only | `tools/riftreader_workflow/opencode_bridge.py` | Medium |
| Commit/push | No delegation | Main agent only | Medium |

Rule: no two agents edit the same file in the same milestone. Workers must know
they are not alone in the codebase and must not revert or overwrite others'
changes.

## Suggested first implementation sequence

| Step | Action | Why |
|---:|---|---|
| 1 | Create tracked plan doc | Locks scope and prevents drift |
| 2 | Add `decision_packet.py --self-test` stub | Establishes command contract early |
| 3 | Add wrapper `.cmd` | Keeps operator workflow simple |
| 4 | Add tests for stale/current target epoch fixtures | Protects against game restarts and address drift |
| 5 | Add Git/current-truth/proof aggregation | First useful packet |
| 6 | Add actor-chain no-debug integration | Directly supports the current lane |
| 7 | Add validation planner | Speeds practical commit decisions |
| 8 | Add commit planner | Speeds "what needs committing?" |
| 9 | Add agent-plan output | Enables safe parallel work |
| 10 | Integrate with OpenCode/Operator Lite only after the core packet is stable | Avoids coupling too early |

## Success criteria

A future fresh session should start with one command:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-decision-packet.cmd --compact-json
```

The output should be enough for the LLM or a local agent to know the safe lane,
risk, blockers, validation plan, and next command without manually hunting
through the repo.
