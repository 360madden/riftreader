# Compact handoff: static coordinate pointer-chain discovery resume

Generated: 2026-05-13 12:31 EDT / 2026-05-13 16:31 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Remote state at creation: `main` aligned with `origin/main` (`git rev-list --left-right --count origin/main...main` = `0 0`)
Newest commit at creation: `cd94266 Rank coordinate families by displacement tracking`

## TL;DR

Static coordinate pointer-chain discovery is **not done**. Current coordinate truth is **candidate-only** for the latest investigated target PID `60628`.

Do **not** promote any PID `60628` heap address, do **not** update `docs/recovery/current-proof-anchor-readback.json`, and do **not** run movement/x64dbg/watchpoints until exact-target preflight reports `responding=true` for the current live target with no debugger process attached.

The best current evidence is useful for the next discovery pass, but it is not stable static truth:

| Lead | Current meaning |
|---|---|
| `0x1FF08502BC8` | Best exact 3-pose heap candidate; x64dbg access-proven, but likely UI/scene-object metadata path and not a static player-coordinate owner. |
| `0x1FF94EC0000` | Best family-level 3-pose moving-slot candidate; excellent displacement tracking, but slots move and no module/static chain exists. |
| `0x1FF07570000` | Destination-page/unaligned copy family; continue with grouped snapshots and `--scan-stride 1` if target is recovered. |
| `0x1FF6D600020 + 0x28` | Earlier source-copy lead around `rift_x64.exe+0x47D408`; heap-local, useful shape clue only. |

## Current blocker

Latest documented live target:

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `60628` |
| HWND | `0xCE0FCE` |
| Process start UTC | `2026-05-13T04:53:58.081190Z` |
| Module base | `0x7FF796B50000` |
| Last state | `responding=false` after x64dbg access capture; debugger process count `0` |

Blocking artifacts:

- `scripts/captures/x64dbg-live-access-capture-20260513-072035-091117/summary.json`
- `scripts/captures/x64dbg-target-preflight-20260513-072327-946499/summary.json`
- `scripts/captures/post-x64dbg-nonresponsive-visual-20260513-032345-187/wgc-result.json`

Interpretation: x64dbg detached, but the RIFT target became nonresponsive. Manual recovery/relaunch is required before more live work.

## Latest repo/code changes already on `main`

Latest commits at handoff creation:

| Commit | Summary |
|---|---|
| `cd94266` | Rank coordinate families by displacement tracking. |
| `7d9619e` | Document movement displacement blocker. |
| `c00bc05` | Document high heap coordinate family leads. |
| `9082e46` | Document deeper pointer scan blocker. |
| `a5aeab7` | Classify x64dbg coordinate copy probes. |
| `4aafa0b` | Document unaligned coordinate recovery progress. |
| `132fa64` | Recover unaligned coordinate copy evidence. |
| `87e2a33` | Record PID 60628 coordinate family reacquisition. |
| `4270273` | Add bounded x64dbg stimulus support. |
| `7ea6740` | Add grouped pointer family scanner. |

Important implemented surfaces:

- `scripts/rift_live_test/coordinate_family_rank.py`
  - now computes displacement-tracking summaries and ranks same-support candidates by tracking error.
- `scripts/scan_current_pid_coordinate_family.py`
  - now writes microsecond-stamped capture directories to avoid same-second collisions.
- x64dbg/pointer-chain helper stack exists and is documented:
  - `scripts/x64dbg_access_event_ingest.py`
  - `scripts/x64dbg_static_chain_resolve.py`
  - `scripts/x64dbg_preflight.py`
  - `scripts/x64dbg_launcher.py`
  - `scripts/rift_live_test/x64dbg_access_event_ingest.py`
  - `scripts/rift_live_test/x64dbg_static_chain_resolve.py`

## Read first in the next chat

1. `docs/recovery/current-truth.md`
2. `docs/handoffs/2026-05-13-0729-currentpid-60628-threepose-candidate-blocker.md`
3. `docs/recovery/x64dbg-pointer-chain-workflow.md`
4. `docs/recovery/x64dbg-static-coord-chain-discovery-status-2026-05-12.md`
5. This handoff: `docs/handoffs/2026-05-13-1231-compact-static-pointer-chain-resume.md`

## Safety boundaries to preserve

| Boundary | Required behavior |
|---|---|
| Live target | Re-discover exact PID/HWND/start/module after any relaunch. Treat all old heap addresses as stale for a new process epoch. |
| Target response | Fail closed if exact preflight says `responding=false`. |
| x64dbg | User approved x64dbg use in this conversation, but still use short preplanned attach windows, hard detach/abort timers, and no process patching. |
| Cheat Engine | Not authorized in this lane; do not use CE/debugger/watchpoints unless separately re-authorized. |
| Movement | No movement/navigation until exact-target, visual, API-now vs memory-now, and same-target proof gates pass. |
| Promotion | x64dbg events are candidate evidence only until converted into a repo-owned resolver and validated against fresh API/runtime coordinates across poses/restart. |

## Best known evidence details

### Movement/input truth

C# exact-HWND SendInput `VirtualKey` `w` moved the character in PID `60628` tests:

- `scripts/captures/csharp-sendinput-current-virtualkey-w-currentpid-60628-20260513-025312/measured-result.json`
  - planar displacement `0.4616189445850858`
- `scripts/captures/csharp-sendinput-current-virtualkey-w-thirdpose-currentpid-60628-20260513-031727/measured-result.json`
  - planar displacement `0.37082363732641205`

Earlier C# `ScanCode` `w` was ineffective/low-signal for this target. Use `VirtualKey` only after gates pass.

### Three-pose ranking

Artifact:

- `scripts/captures/coordinate-family-rank-currentpid-60628-threepose-tracking-20260513-032001-311/coordinate-family-rankings.json`

Best exact candidate:

- address `0x1FF08502BC8`
- support `3`
- track max error `0.004333593749834108`
- avg delta `0.003232356770846915`

Best family candidate:

- family `0x1FF94EC0000`
- support `3`
- track max error `6.0937500165891834e-05`
- moving slots: `0x1FF94EC8B80` -> `0x1FF94EC8DC0` -> `0x1FF94EC93D0`

Demoted after third pose:

- `0x1FF392C0000`
- `0x1FF40660000`
- `0x1FF841D0000`

### Pointer/static chain status

Latest broader pointer-family scan:

- `scripts/captures/pointer-family-scan-20260513-070942-089639/summary.json`

Result:

- seed count `14`
- scanned target count `67`
- total module hits `0`
- total `rift_x64.exe` hits `0`
- heap refs only

Bottom line: no static owner/module-root chain yet.

## Non-promotion list

Keep these candidate-only unless a future current-PID/restart proof promotes them:

- `0x1FF08502BC8`
- `0x1FF94EC0000`
- `0x1FF94EC93D0`
- `0x1FF07574839`
- `0x1FF07575346`
- `0x1FF0757215A`
- `0x1FF6D600020`
- `0x1FF65FADE88`
- `0x1FF6D658590`
- transient `0x1FF392*`, `0x1FF406*`, `0x1FF841*` leads

## Paste-ready resume prompt

Resume in `C:\RIFT MODDING\RiftReader` on `main`. Start by running `git status --short --branch`, `git rev-list --left-right --count origin/main...main`, and reading `docs/recovery/current-truth.md`, `docs/handoffs/2026-05-13-0729-currentpid-60628-threepose-candidate-blocker.md`, and `docs/handoffs/2026-05-13-1231-compact-static-pointer-chain-resume.md`. Current static coordinate pointer-chain discovery is not complete. Latest investigated PID `60628` became `responding=false` after `scripts/captures/x64dbg-live-access-capture-20260513-072035-091117/summary.json`; latest blocker is `scripts/captures/x64dbg-target-preflight-20260513-072327-946499/summary.json`. Do not run movement, x64dbg, or watchpoints until exact-target preflight passes with `responding=true` and no debugger processes. Treat `0x1FF08502BC8`, `0x1FF94EC0000`, `0x1FF07570000`, and `0x1FF6D600020 + 0x28` as candidate-only shape clues. The next useful step is to recover/relaunch RIFT, reacquire exact PID/HWND/start/module/API-now, then continue grouped family scans and displacement-aware ranking before any short preplanned x64dbg attach.

## Optional top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Manually recover or relaunch RIFT. | Current live/debugger work is blocked by `responding=false`. |
| 2 | Run exact-target x64dbg preflight after recovery. | Confirms PID/HWND/start/module/responding and no debugger processes. |
| 3 | Reacquire fresh API/runtime coordinate for the new/current process epoch. | Old absolute heap addresses are stale across restart/relog. |
| 4 | Re-run grouped current-PID coordinate family scans. | Family snapshots saved time and gave higher signal than isolated offset probes. |
| 5 | Re-rank with displacement tracking across at least three poses. | Demotes stationary midpoint false positives and identifies moving-slot families. |
| 6 | Prioritize `0x1FF94EC0000`-style moving families over one-off exact heap hits. | Moving-slot families may reveal copy/storage topology better than static-looking snapshots. |
| 7 | Use `--scan-stride 1` on destination/copy pages. | Unaligned copy evidence was missed by wider stride assumptions. |
| 8 | Run pointer-family scans only after fresh tracking candidates exist. | Avoids expensive scans on stale or low-signal heap regions. |
| 9 | Use x64dbg only as a short, preplanned, detach-first event capture. | Reduces freeze/logout risk while still collecting access provenance. |
| 10 | Promote nothing until API-now vs chain-now, multi-pose, restart validation, and same-target `ProofOnly` all pass. | Prevents false coordinate truth from contaminating movement/navigation gates. |
