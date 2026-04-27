---
state: current
as_of: 2026-04-15
---

# Actor yaw focused-PostMessage recovery (2026-04-15)

## Scope

Freeze the first successful post-update live actor-yaw recovery on
`codex/actor-yaw-pitch` using the Desktop-2 workflow:

- focus Rift first
- verify focus
- deliver turn input with `PostMessage`
- skip screenshot UI gating on the hidden desktop

This report also captures why the first strong candidate initially looked bad:
the recovery sequence was paying repeated live-warning countdown delays, which
introduced false idle drift between phases.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `current` |
| As of | `2026-04-15` |
| Report date | `2026-04-15` |
| Game update/build date | `unknown` |
| Branch | `codex/actor-yaw-pitch` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Input mode | `direct key stimulus` |
| Validation status | `working` |

## Commands run

```powershell
powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1" -Json

powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1" -Json -RefreshReaderBridge $false

powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\recover-actor-orientation.ps1" `
  -Json `
  -PinnedSourceAddress "0x245D78DCB50" `
  -PinnedBasisForwardOffset "0xD4" `
  -RequireTargetFocus `
  -SkipUiClearCheck `
  -OrientationCandidateLedgerFile "C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-ledger.aggressive.ndjson" `
  -OutputFile "C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245d78dcb50-basis-d4.manual.json"

powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\recover-actor-orientation.ps1" `
  -Json `
  -PinnedSourceAddress "0x245D78DCB50" `
  -PinnedBasisForwardOffset "0xD4" `
  -RequireTargetFocus `
  -SkipUiClearCheck `
  -SkipLiveInputWarning `
  -OrientationCandidateLedgerFile "C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-ledger.aggressive.ndjson" `
  -OutputFile "C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245d78dcb50-basis-d4.manual.nowarning.json"
```

## Artifacts checked

- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-ledger.aggressive.ndjson`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-screen.aggressive.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245cfabe970-basis-d4.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245d78dcb50-basis-d4.manual.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245d78dcb50-basis-d4.manual.nowarning.json`

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| Focus-enforced live key delivery | working | `post-rift-key.ps1 -RequireTargetFocus` successfully focused Rift and still used `PostMessage` instead of `SendInput` |
| Actor-yaw candidate `0x245D78DCB50 @ 0xD4` | working | first proven post-update actor-yaw winner on this branch |
| Opposite-direction recovery gate | working | successful run produced opposite-sign high-magnitude A/D yaw deltas with zero coord drift |
| Pitch from the same basis | working | winning recovery also marked `PitchRecovered = true` |

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| Refresh ReaderBridge export lane | broken | `refresh-readerbridge-export.ps1` hit an AutoHotkey fallback failure (`code 2`) during wrapper runs |
| Recovery timing with repeated warning countdowns | drifted | the first pinned recovery on the winning candidate failed as `idle_drift`, but the candidate recovered cleanly once `-SkipLiveInputWarning` removed the extra delay |
| Screenshot UI-clear gating on Desktop 2 | partial | not authoritative when Rift is isolated on a hidden desktop |

## Stale artifacts

- `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245d78dcb50-basis-d4.manual.json`
  - historical failed recovery for the same winning source; failure reason was timing-induced `idle_drift`

## Branch / workflow authority

The authoritative live actor-yaw workflow for this recovery pass lives on:

- branch: `codex/actor-yaw-pitch`
- worktree: `C:\RIFT MODDING\RiftReader`

Authoritative scripts for this pass:

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\recover-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\screen-actor-orientation-candidates.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1`

Winning pinned source for current branch truth:

- source address: `0x245D78DCB50`
- basis forward offset: `0xD4`

Winning artifact:

- `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245d78dcb50-basis-d4.manual.nowarning.json`

## Input mode and safety notes

This pass used:

- direct key stimulus
- focused `PostMessage`

This pass intentionally avoided:

- foreground `SendInput` as the trusted lane
- screenshot-based UI gating as an authority signal on Desktop 2
- `/reloadui` for the successful pinned recovery run

The successful recovery required:

1. focus Rift
2. verify Rift really became foreground
3. send A/D via `PostMessage`
4. suppress repeated live-warning countdown delays during AI-driven recovery

## Proven recovery metrics

Winning run:

- source: `0x245D78DCB50`
- basis: `0xD4`
- delivery mode: `focused-postmessage`
- `YawRecovered = true`
- `PitchRecovered = true`
- `IdleConsistencyPass = true`
- baseline idle drift: `0.0°`
- inter-stimulus drift: `3.607°`
- `A` yaw delta: `+175.421°`
- `D` yaw delta: `-171.331°`
- coord drift: `0.0`

This satisfies the branch’s opposite-direction turn gate for actor yaw.

## Immediate next step

Promote `0x245D78DCB50 @ 0xD4` into the living recovery truth and harden the
aggressive wrapper so ReaderBridge refresh failure can degrade gracefully
instead of blocking otherwise-valid focused-PostMessage recovery runs.
