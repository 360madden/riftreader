# Assistant Operating Policy

This document expands the repo-level guidance in
`C:\RIFT MODDING\RiftReader\agents.md`.

## Goals

| Goal | Meaning |
|---|---|
| Keep answers easy to scan | lead with the verdict and use tables |
| Keep changes low-risk | prefer the smallest correct patch |
| Avoid endless loops | escalate on evidence and change tactics after repeated similar failures |
| Stay iterative | start simple for code patches; for live discovery, start with enough instrumentation to produce strong evidence |

## Default response shape

| Part | Default |
|---|---|
| Opening | direct answer first |
| Major result | large bold verdict heading |
| Structure | tables for status, comparisons, blockers, and options |
| Detail level | concise but still detailed |
| Recommendations | optional Top 10 table when useful |

## Simple decision tree

| Situation | Model | Reasoning | What to do |
|---|---|---|---|
| Explanation, formatting, status board, or doc-only work | `spark` (prefer) | low | answer directly |
| Small isolated code/script change with a known root cause | `spark` (prefer) | medium | patch minimally and validate |
| Single-file, low-impact code change with quick rollback | `spark` (prefer) | medium | patch minimally and validate |
| Normal bugfix, validation issue, or moderate multi-file change | `gpt-5.4` | medium | inspect first, then patch |
| Root cause unclear or evidence conflicts | `gpt-5.4` | high | diagnose before editing |
| Reverse engineering, controller proof, pointer-chain proof, or other high-risk discovery work | `gpt-5.4` | xhigh | narrow scope and work evidence-first |

### Spark-only decision template

When deciding routing, run this quick check before editing:

1. Will the task touch **live/critical runtime movement behavior** or **unproven discovery logic**?
2. Is there any possibility it can create **hard-to-revert game/client impact**?
3. Is the required change **single-file and clearly bounded**?

Only use `spark` when the answer to 1 and 2 is clearly "no" and 3 is "yes."
If any safety question is uncertain, treat as non-spark and route to
`gpt-5.4`.

## Failure escalation

| Signal | Response |
|---|---|
| First failure | gather more evidence and keep the current scope narrow |
| Second similar failure | increase reasoning depth and restate the current hypothesis |
| Third similar failure | stop repeating the same patch pattern; change tactics |
| Conflicting evidence | rebuild the explanation from observed facts only |
| No new evidence | do not retry blindly |

## Model routing quick check list

| Check | Spark allowed only if ✅ |
|---|---|
| Task is docs-only, formatting, or status organization | ✅ |
| Task is a single file, low-impact code change with deterministic diff | ✅ |
| Task can be validated with existing tests/commands before/after edit | ✅ |
| Task changes live movement, proof sourcing, or CE-dependent assumptions | ❌ |
| Task has unclear acceptance criteria / conflicting evidence | ❌ |
| Task is branch-wide behavior refactor or risky merge scope | ❌ |

Use `docs/model-routing-template.md` when you want a more structured review.

## Cross-repo provider/consumer rule

RiftReader may consume ChromaLink, but a RiftReader-focused task must not
silently mutate the ChromaLink provider repo.

| Situation | Required behavior |
|---|---|
| Need existing ChromaLink world-state data | Consume the documented local HTTP/API/schema/client surface only |
| Need a new ChromaLink field or endpoint | Write a request with `docs\chromalink-change-request-template.md` |
| User explicitly asks for a ChromaLink edit pass | Switch context deliberately, read the latest ChromaLink handoff, and validate/push in the ChromaLink repo |
| Both repos must change | Make ChromaLink provider contract changes first, then integrate the explicit contract in RiftReader |
| ChromaLink tests pass | Still run/record RiftReader-side validation before claiming RiftReader integration works |

Do not use `spark` for hidden cross-repo behavior changes. Spark is acceptable
for read-only contract review or docs-only coordination notes, but not for
provider schema/API/client changes unless the user explicitly scopes the change
as low-risk and reversible.

## Recommendation list format

When recommendations add real value, use a **Top 10 recommended next actions**
table with these columns:

| Column | Meaning |
|---|---|
| `#` | priority or order |
| `Action` | concrete next step |
| `Why` | short justification |

Do **not** include `Model` or `Reasoning` columns unless the user explicitly
asks for them.

## Live movement / polling invariant

Before any live movement polling, forward-hold capture, or coordinate-driven
navigation proof:

| Rule | Requirement |
|---|---|
| Canonical coord source | Resolve `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1` first and use the validated coord-trace anchor as the movement source of truth |
| Coord-trace selection | Allow the proof resolver to choose either the traced object or the trace-linked source object, whichever still matches live ReaderBridge coordinates |
| Watchset export | Ensure the proof watchset contains the canonical `coord-trace-coords` region derived from that validated coord-trace anchor |
| Heuristic current-player reads | Treat `read-player-current.ps1`, cached current-player anchors, and any `heuristic` source as exploration-only unless they have been separately re-proven and explicitly promoted |
| Proof reacquisition seed order | Prefer **last-good trace seeds** and **debug-scanned selector/source-chain seeds** first; do not reseed proof tracing from heuristic or cached current-player snapshots when stronger seeds exist |
| Proof access-watch size | In proof reacquisition with access watchpoints, default to a **12-byte coord-triplet watch window** so `X/Y/Z` lane accesses can be re-proven from the same live source object instead of missing non-`X` reads with a 4-byte watch |
| Escalation after repeated proof-reacquisition failure | Escalate to **debug scanning** instead of retrying the same heuristic/bootstrap trace loop |
| Proactive debug tracing | Use debug tracing as a **primary discovery method**, not just a recovery tool. For coords, facing, and proof-watchset quality, use breakpoints, trace-cluster inspection, selector/owner tracing, and neighborhood scans to look for related fields, better offsets, pointer relationships, and stronger candidates before locking a watchset |
| Live discovery signal | For coordinate/facing reverse engineering, optimize for **highest signal per bounded run**, not the shortest safe pulse. Use addon labels, exact-window helper input, native memory recording, and timestamped artifacts together when available |
| Movement trace shape | Prefer scripted multi-vector movement traces with baseline pauses, stops, turns/strafe/backtrack, and final stabilization over a single forward pulse when scoring candidates |
| SavedVariables freshness | Treat `ReaderBridgeExport.lua` and all RIFT addon `SavedVariables` files as post-save snapshots only, not live IPC. They normally update on `/reloadui`, logout, UI shutdown, or another save event. Do not use them as live movement truth unless a fresh save/flush timestamp proves the file is current for the capture. |
| Live truth declaration | Every coord bundle must declare its authoritative truth surface (`overlay`, `validated-memory-anchor`, `post-flush-savedvariables`, etc.) and fail closed if stale SavedVariables data is accidentally used as live truth |
| Discovery artifacts | Treat selected-source coord lanes, projector traces, stat hubs, and similar discovery artifacts as candidate-only unless they have been re-proven for the current session |
| Failure policy | If the watchset lacks canonical coord-trace coords or the resolved anchor is not validated, stop and fix the proof source instead of recording stale/candidate/heuristic movement data |

## Example routing

| Example task | Model | Reasoning | Why |
|---|---|---|---|
| Rewrite a status update into tables | `spark` | low | formatting only |
| Fix a brittle PowerShell path default | `spark` | medium | small targeted script change |
| Add dashboard snapshot refresh logic | `gpt-5.4` | medium | moderate UI/data-flow change |
| Diagnose a repeated validator failure | `gpt-5.4` | high | requires better evidence handling |
| Prove the authoritative camera controller path | `gpt-5.4` | xhigh | ambiguous, high-cost reverse-engineering work |

## Iteration rule

Start with the lightest approach likely to succeed, validate quickly, and only
increase reasoning or scope when the evidence shows the current level is not
enough.
