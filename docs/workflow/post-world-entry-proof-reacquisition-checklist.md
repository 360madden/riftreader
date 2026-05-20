# Post-world-entry proof reacquisition checklist

Use this checklist after an explicitly approved character-select `Play` action
loads a character into the world. It is intentionally conservative: world entry
does **not** restore movement permission by itself.

## Required sequence

| # | Step | Required evidence |
|---:|---|---|
| 1 | Re-run exact RIFT target discovery | Current `rift_x64.exe` PID, HWND, process start/epoch |
| 2 | Capture current screen state | Fresh screenshot proving in-world UI, not character-select/loading |
| 3 | Rebuild same-target proof context | Current PID/HWND must match the live target, not historical artifacts |
| 4 | Resolve current coordinate truth | Fresh API/runtime coordinate compared to immediate memory read |
| 5 | Run same-target `ProofOnly` | Must pass with `movementAllowed=false/true` verdict recorded by the proof gate |
| 6 | Promote only current-session evidence | No stale absolute addresses, old PIDs, SavedVariables snapshots, or launcher logs |
| 7 | Keep first post-world action no-input when possible | Prefer readback/status captures before diagnostic input |
| 8 | Only then consider movement/input tests | Requires explicit movement approval and the normal movement gates |

## Fail-closed blockers

- Current PID/HWND differs from the proof artifact.
- API/runtime coordinate is missing or stale.
- Memory readback fails, drifts outside tolerance, or comes from candidate-only evidence.
- Screen classifier cannot distinguish in-world from loading/character select.
- Any helper would need CE, x64dbg attach, raw launcher secrets, or hidden launcher buttons.

## Sensitive data rule

Do not record raw launcher/RIFT command lines, auth/session arguments, account
names, API keys, tokens, or ticket values in tracked docs. Use placeholders such
as `$RIFT_AUTH_TOKEN`, `$GLYPH_SESSION_ID`, `$ACCOUNT_NAME`, or `<redacted>`.
