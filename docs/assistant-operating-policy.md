# Assistant Operating Policy

This document expands the repo-level guidance in
`C:\RIFT MODDING\RiftReader\agents.md`.

## Goals

| Goal | Meaning |
|---|---|
| Keep answers easy to scan | lead with the verdict and use tables |
| Keep changes low-risk | prefer the smallest correct patch |
| Avoid endless loops | escalate on evidence and change tactics after repeated similar failures |
| Stay iterative | start simple and only add complexity when needed |

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
| Explanation, formatting, status board, or doc-only work | `gpt-5.4-mini` | low | answer directly |
| Small isolated change with a known root cause | `gpt-5.4-mini` | medium | patch minimally and validate |
| Normal bugfix, validation issue, or moderate multi-file change | `gpt-5.4` | medium | inspect first, then patch |
| Root cause unclear or evidence conflicts | `gpt-5.4` | high | diagnose before editing |
| Reverse engineering, controller proof, pointer-chain proof, or other high-risk discovery work | `gpt-5.4` | xhigh | narrow scope and work evidence-first |

## Failure escalation

| Signal | Response |
|---|---|
| First failure | gather more evidence and keep the current scope narrow |
| Second similar failure | increase reasoning depth and restate the current hypothesis |
| Third similar failure | stop repeating the same patch pattern; change tactics |
| Conflicting evidence | rebuild the explanation from observed facts only |
| No new evidence | do not retry blindly |

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
| Proof reacquisition seed order | Prefer **last-good trace seeds** and **debug-scanned source-chain seeds** first; do not reseed proof tracing from heuristic or cached current-player snapshots when stronger seeds exist |
| Escalation after repeated proof-reacquisition failure | Escalate to **debug scanning** instead of retrying the same heuristic/bootstrap trace loop |
| Discovery artifacts | Treat selected-source coord lanes, projector traces, stat hubs, and similar discovery artifacts as candidate-only unless they have been re-proven for the current session |
| Failure policy | If the watchset lacks canonical coord-trace coords or the resolved anchor is not validated, stop and fix the proof source instead of recording stale/candidate/heuristic movement data |

## Example routing

| Example task | Model | Reasoning | Why |
|---|---|---|---|
| Rewrite a status update into tables | `gpt-5.4-mini` | low | formatting only |
| Fix a brittle PowerShell path default | `gpt-5.4-mini` | medium | small targeted script change |
| Add dashboard snapshot refresh logic | `gpt-5.4` | medium | moderate UI/data-flow change |
| Diagnose a repeated validator failure | `gpt-5.4` | high | requires better evidence handling |
| Prove the authoritative camera controller path | `gpt-5.4` | xhigh | ambiguous, high-cost reverse-engineering work |

## Iteration rule

Start with the lightest approach likely to succeed, validate quickly, and only
increase reasoning or scope when the evidence shows the current level is not
enough.
