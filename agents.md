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
  - `Model`
  - `Reasoning`
  - `Why`
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

See `C:\RIFT MODDING\RiftReader\docs\assistant-operating-policy.md` for the
longer decision tree and examples.
