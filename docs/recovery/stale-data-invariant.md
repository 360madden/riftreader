# Stale-data invariant for coordinate proof recovery

## Hard rule

If the live `rift_x64` PID/HWND is known, **that discovered target identity
wins over every cached artifact**.

Do not use a proof pointer, candidate ID, match file, absolute address, readback
summary, or `movementAllowed=true` flag from an artifact whose target metadata
points to a different PID/HWND.

## Required behavior

| Case | Required behavior |
|---|---|
| `current-proof-anchor-readback.json` targets an old PID/HWND | Replace it with `status=blocked-target-drift` for the discovered target. |
| The old proof pointer has useful fields | Archive it under `docs/recovery/historical/` and preserve only historical reacquisition hints. |
| A helper needs `candidateId` | Use an explicit current candidate file, a same-target proof anchor, or profile fallback. Never use a mismatched pointer candidate. |
| A helper needs `matchFile` | Use only same-target/current-PID evidence. A mismatched pointer `matchFile` is historical-only. |
| A helper sees stale `movementAllowed=true` | Ignore it and force movement/navigation blocked. |
| The user asks to continue discovery | Use broad current-PID family snapshots/scans; do not probe stale absolute addresses. |

## Current blocker shape

When target drift is detected, `docs/recovery/current-proof-anchor-readback.json`
must become a blocker, not a stale proof document:

```json
{
  "mode": "current-proof-anchor-readback-pointer",
  "status": "blocked-target-drift",
  "target": {
    "processName": "rift_x64",
    "processId": "<discovered-current-pid>",
    "targetWindowHandle": "<discovered-current-hwnd>"
  },
  "currentTruthClassification": {
    "classification": "stale-target-drift-blocker",
    "movementAllowed": false
  }
}
```

Only a fresh same-target `ProofOnly` pass may replace that blocker with
`status=current-target-proofonly-passed`.

## Why this exists

The old target may still contain a valid-looking coordinate chain for its own
process epoch. That does **not** make it valid after relaunch, relog, HWND
change, or PID change. Carrying old PID data forward wastes discovery time and
can make downstream tools select stale candidates.

Historical proof data remains useful only for:

1. family-shape hints;
2. likely offset relationships;
3. broad current-PID scan seeds;
4. human audit/history.

It is never current movement truth.
