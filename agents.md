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
| Formatting, tables, docs, status organization | `gpt-5.4-mini` | low | answer directly |
| Small script, UI, or docs change with known cause | `gpt-5.4-mini` | medium | make the smallest patch and validate |
| Normal bugfix or multi-file change | `gpt-5.4` | medium | inspect first, then patch |
| Unclear bug or conflicting evidence | `gpt-5.4` | high | diagnose before editing |
| Deep discovery, reverse engineering, or proof work | `gpt-5.4` | xhigh | narrow scope and work evidence-first |

## Escalation / anti-loop rules

- Start simple. Validate quickly. Escalate only on evidence.
- First failure: gather more evidence and keep scope narrow.
- Second similar failure: increase reasoning depth and re-check the root cause.
- Third similar failure: stop retrying the same patch pattern; change tactics and
  restate the hypothesis from observed facts.
- Do not keep retrying a hypothesis without new evidence.

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
