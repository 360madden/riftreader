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

## Workflow automation language decision tree

Codex is too slow to be the real-time controller for live movement windows.
Time-sensitive live workflows must be automated as deterministic local
controllers, with Codex acting as planner/reviewer.

From this point forward, new workflow/helper-app implementation should follow
this practical split:

| Question | Default answer |
|---|---|
| Is this a double-click or terminal convenience entry point? | Use a tiny `.cmd` launcher. |
| Is this multi-step workflow, proof refresh, live-test orchestration, JSON/report processing, or state-machine control? | Use Python. |
| Is this a helper app, operator CLI/TUI, run-summary parser, report writer, or evidence packager? | Use Python first. |
| Is this low-level process-memory reading, native process inspection, or existing reader engine work? | Keep it in the existing C#/.NET code. |
| Is this PowerShell? | Treat it as a legacy leaf adapter unless a narrow Windows-native need is documented. |

### Required pattern for new live-test workflow automation

New automation such as a gated movement experiment should use this structure:

| Layer | Responsibility |
|---|---|
| `.cmd` launcher | `cd /d "C:\RIFT MODDING\RiftReader"` and call Python with `%*`; no decisions. |
| Python controller | Profiles, state machine, subprocess argument lists, JSON parsing, timeout handling, proof-age budget, summaries, and fail-closed statuses. |
| Existing `.ps1` leaves | Temporary compatibility adapters for already-proven commands only. |
| .NET reader | Memory/readback/process engine. |

The Python controller should:

1. Verify exact target process and window.
2. Refresh proof without Cheat Engine or SavedVariables live truth.
3. Promote only current, same-PID/same-HWND evidence.
4. Run a no-input dry-run gate.
5. Send at most the configured bounded input when all gates are green.
6. Immediately perform post-readback.
7. Write one compact `run-summary.json`; write `run-summary.md` when useful.
8. Fail closed with explicit machine-readable labels.

### PowerShell use limits

Do **not** add new PowerShell workflow brains. Avoid using `.ps1` for:

| Avoid in PowerShell | Use Python because |
|---|---|
| Multi-step orchestration | Python is clearer and more testable for state machines. |
| JSON parsing/rewriting | Python JSON handling is less brittle. |
| Subprocess fan-out | Python `subprocess.run([...])` avoids quoting and array-binding bugs. |
| Proof-age timing chains | Python can keep refresh, dry-run, input, and postcheck tightly chained. |
| Helper apps / operator tooling | Python scales better into CLI/TUI/reporting code. |

PowerShell is still acceptable when:

| Allowed use | Constraint |
|---|---|
| Existing proven `.ps1` leaf command | May be invoked by Python until replaced. |
| Narrow Windows-native operation | Keep it focused, documented, and covered by validation. |
| Temporary compatibility shim | No broad state machine or proof decision logic. |

Do not rewrite all existing `.ps1` files immediately. The safest migration is:

1. Put a Python controller above the current proven commands.
2. Validate the controller with the live workflow in bounded profiles.
3. Port brittle PowerShell leaves one at a time only after behavior is locked.

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


## Live screenshot capture invariant

For RIFT native screenshots, the only approved in-game screenshot input is
**`NUM PAD *`** (`VK_MULTIPLY`, `0x6A`). This was live-proven on May 8,
2026 against `rift_x64` PID `49504`, HWND `0x5121A`, and produced
`C:\Users\mrkoo\OneDrive\Documents\RIFT\Screenshots\2026-05-08_200805.jpg`.

| Input | Policy | Reason |
|---|---|---|
| `NUM PAD *` | Allowed for native RIFT screenshots | Current verified `Take Screenshot` binding |
| `Ctrl+P` / `Control+P` | Forbidden | Keybind was removed; helpers must reject it before input |
| `PrtSc` / Print Screen | Forbidden for automation | Windows 11 Snipping Tool intercepts it on this machine |
| Snipping Tool / `Win+Shift+S` | Manual fallback only | Interactive, not unattended exact-HWND capture |
| `Take Screenshot Without UI` | Do not use unless explicitly rebound and re-proven | Currently not bound |

Use `C:\RIFT MODDING\RiftReader\scripts\rift_native_screenshot.py` for native
screenshot attempts and `C:\RIFT MODDING\RiftReader\docs\recovery\native-rift-screenshot-backend.md`
for the current command, proof artifact, and troubleshooting rules. A visual
screenshot is evidence only; it does not replace no-CE proof-anchor/readback
movement gates.

## Live movement / polling invariant

Before any live movement polling, forward-hold capture, or coordinate-driven
navigation proof:

| Rule | Requirement |
|---|---|
| Coordinate freshness | Use **API-now vs memory-now** as the default stale/non-stale gate: sample a fresh live API/runtime coordinate, immediately read the memory coordinate from the current candidate/anchor, compare X/Y/Z deltas, and call it current only if the API source is fresh and the delta is within tolerance |
| PID/HWND role | Treat PID/HWND/process-start match as targeting preflight only; it never proves that a cached coordinate value is fresh |
| Fresh API surfaces | Accept only freshness-proven live surfaces such as ChromaLink `/api/v1/riftreader/world-state`, explicitly live ReaderBridge/in-game runtime state, or another current telemetry source; never use SavedVariables, `rift.cfg`, or old run summaries as the API side of the freshness comparison |
| Freshness failure policy | If API is stale/missing, memory readback fails, or API-vs-memory delta exceeds tolerance, classify the coordinate as stale/mismatch, block movement, and keep artifacts only as reacquisition seeds |
| Freshness evidence | Record API coordinate/timestamp/source, memory coordinate/timestamp/address/candidate, PID/HWND/process identity, per-axis deltas, tolerance, and verdict |
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
