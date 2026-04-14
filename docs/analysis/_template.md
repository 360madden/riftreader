---
state: historical
as_of: <YYYY-MM-DD>
---

# <Report title> (<YYYY-MM-DD>)

## Scope

Describe the specific investigation window and what this report is freezing.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `<current / stale / historical>` |
| As of | `<YYYY-MM-DD>` |
| Report date | `<YYYY-MM-DD>` |
| Game update/build date | `<date or unknown>` |
| Branch | `<branch>` |
| Worktree | `<absolute path>` |
| Input mode | `<read-only / direct key-mouse / chat-reload>` |
| Validation status | `<working / partial / blocked / stale>` |

## Commands run

```powershell
<command 1>
<command 2>
```

## Artifacts checked

- `<artifact path>`
- `<artifact path>`

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| `<area>` | `<working/partial>` | `<notes>` |

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| `<area>` | `<broken/stale>` | `<notes>` |

## Stale artifacts

- `<artifact path>`

## Branch / workflow authority

Document where the authoritative scripts and notes live for this investigation,
especially if `main` and a feature branch differ.

## Input mode and safety notes

Record exactly whether the run used:

- read-only inspection
- direct key stimulus
- direct mouse/RMB stimulus
- chat command injection
- `/reloadui`

Also record any UI-intrusive helpers that were used or intentionally avoided.

## Immediate next step

State the next required rebuild or validation step without overstating certainty.
