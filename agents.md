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
- Say exactly what was not validated.

## Live movement / polling invariant

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
