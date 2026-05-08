# Navigation turn-backend promotion checklist

This checklist is the required path before any keyboard or message-based turn
backend can be used by navigation auto-turn.

Current status as of May 8, 2026: **no turn backend is promoted** for current
PID `33912` / HWND `0xE0DB2`.

## Hard gate

`scripts\navigation\run-a-to-b-prototype.ps1 -AutoTurnBeforeMove` must not
pulse a turn key unless promoted evidence contains a matching
`promotedCandidates` entry for the selected key and input mode.

Default evidence file:

```text
C:\RIFT MODDING\RiftReader\docs\recovery\turn-key-profile-evidence.json
```

## Minimum promotion criteria

| # | Requirement | Pass condition |
|---:|---|---|
| 1 | Exact target | Profile run targets exact process ID and HWND, not process name alone |
| 2 | Fresh proof | `ProofOnly` passes before each input attempt or before the bounded profile batch |
| 3 | No CE | No Cheat Engine, CE Lua, debugger attach, breakpoints, or watchpoints are used |
| 4 | No SavedVariables live truth | SavedVariables are not treated as live coordinate truth |
| 5 | Input delivery known | Evidence records the effective input mode; fallback ambiguity is not promotable |
| 6 | Repeat count | At least two completed attempts for the same `key` + `inputMode` + `shell` |
| 7 | Same-sign yaw | Completed attempts produce same-sign yaw deltas above the configured minimum |
| 8 | Zero movement | Proof-coordinate planar deltas stay within the configured no-movement threshold |
| 9 | Post-profile proof | A no-input `ProofOnly` run passes after the profile |
| 10 | Evidence persisted | `docs\recovery\turn-key-profile-evidence.json` contains a matching `promotedCandidates` entry |

## Current disqualified surfaces

| Surface | Evidence | Why not promoted |
|---|---|---|
| True foreground SendInput `d` | `turn-key-profile-currentpid-33912-20260508-081354`, `...-081531` | Delivered without fallback but yaw delta stayed `0.0` |
| True foreground SendInput `Left/Right` | `turn-key-profile-currentpid-33912-20260508-082051` | Completed attempts no-turned; one attempt failed closed before input |
| True foreground SendInput `q/e` | `turn-key-profile-currentpid-33912-20260508-083210` | Delivered without fallback but yaw delta stayed `0.0` |
| Retry-enabled true foreground SendInput `Right` | `turn-key-profile-currentpid-33912-20260508-084929` | Delivered twice without fallback but yaw delta stayed `0.0` |
| Exact-HWND post-message `Left/Right` | `turn-key-profile-currentpid-33912-20260508-090211` | Delivered four attempts but yaw delta stayed `0.0` |
| Post-message `d` | `turn-key-profile-currentpid-33912-20260508-075910` | Produced opposite-sign yaw deltas, so direction is not repeatable |

## Promotion command shape

Use the Python profiler; PowerShell remains a leaf adapter only.

```powershell
python .\scripts\profile_turn_keys.py `
  --pid <exact-pid> `
  --hwnd <exact-hwnd> `
  --process-name rift_x64 `
  --keys <candidate-key> `
  --input-modes <candidate-input-mode> `
  --repeat 2 `
  --hold-ms <bounded-hold-ms> `
  --post-input-wait-ms 250 `
  --live `
  --refresh-proof-before-each-attempt `
  --proof-refresh-retries 1
```

Then regenerate compact evidence:

```powershell
python .\scripts\summarize_turn_key_profiles.py `
  --process-id <exact-pid> `
  --limit 12 `
  --output-json docs\recovery\turn-key-profile-evidence.json `
  --output-markdown docs\recovery\turn-key-profile-evidence.md
```

## Auto-turn usage after promotion

Only after the compact evidence contains a matching promoted candidate:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\navigation\run-a-to-b-prototype.ps1 `
  -ProcessId <exact-pid> `
  -TargetWindowHandle <exact-hwnd> `
  -UseExistingWaypoints `
  -AutoConfirm `
  -AutoTurnBeforeMove `
  -AutoTurnBackendEvidenceFile .\docs\recovery\turn-key-profile-evidence.json
```

If the selected turn key/input mode has no matching promoted candidate, the
prototype must fail closed before sending turn or forward movement input.
