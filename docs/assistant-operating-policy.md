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
| `Model` | recommended GPT-5.4 family model |
| `Reasoning` | `low`, `medium`, `high`, or `xhigh` |
| `Why` | short justification |

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
