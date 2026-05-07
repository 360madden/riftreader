# ✅ Handoff: gated wrapper forward-smoke proof

_Last updated: May 7, 2026 07:25 EDT / 11:25 UTC._

## TL;DR

The current best workflow is now **RiftScan/RiftReader no-CE proof refresh → hardened gated wrapper dry-run → one bounded wrapper pulse only if green → post-pulse proof recovery/readback**.

Latest live movement truth is the **first gated-wrapper `W` 250 ms forward smoke** against exact target `rift_x64` PID `47560`, HWND `0x2122E`. The wrapper preflight was green and one exact-target pulse was sent. The wrapper internal post-readback failed closed only because the 60-second proof anchor age expired during postcheck (`proof_anchor_age_out_of_range_seconds:61.302`). A no-input post-pulse API/reference readback was immediately captured, re-promoted, and the hard current-readback gate returned `Status=valid`, `MovementAllowed=true`.

The wrapper has since been hardened with a pre-input proof-age budget guard: `MinimumPostReadbackAgeBudgetSeconds` default `15`. Future runs should block **before input** if too little proof age remains for the post-readback.

No Cheat Engine, CE Lua, debugger/watchpoints, or SavedVariables-as-live-truth were used.

## Current branch / repo state at handoff creation

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Target at last live proof | `rift_x64` PID `47560`, HWND `0x2122E` |
| Proof candidate | `rift-addon-coordinate-candidate-000001` |
| Candidate address | `0x2400EA32120` |
| Proof region / offset | `0x2400EA320E0` / `64` |
| RiftScan match file | `C:\RIFT MODDING\Riftscan\reports\generated\codex-current-coord-region-passive-20260506-230940-addon-coordinate-matches.json` |
| Current truth doc | `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` |
| Machine-readable pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |

## Latest live proof facts

| Fact | Value |
|---|---|
| Wrapper live summary | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-111630.json` |
| Wrapper preflight | green: `Status=valid`, `MovementAllowed=true` |
| Input sent | exact-target `W`, `250 ms` |
| Input backend | `post-rift-key.ps1 -RequireTargetForeground`; `SendInput` failed, AutoHotkey fallback reported `SUCCESS` |
| Baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071621-832.png` |
| Frame-change screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071648-391.png` |
| Final screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071653-129.png` |
| Frame change | `true`, `13.7569%` |
| Wrapper internal postcheck | `blocked-post-readback` due only to `proof_anchor_age_out_of_range_seconds:61.302` |
| Post-pulse recovery reference | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-post-pulse-recovery-20260507-111705\post-wrapper-api-reference-wide-context.json` |
| Post-pulse recovery pose | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-post-pulse-recovery-20260507-111705\riftscan-proof-post-gated-wrapper-pulse-20260507-111713\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260507-071714.json` |
| Post-pulse hard readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-071736.json` |
| Post-pulse status | `Status=valid`, `MovementAllowed=true` |
| Latest coordinate | `X=7437.916015625`, `Y=885.2205810546875`, `Z=3049.859130859375` at `2026-05-07T11:17:40.4096580Z` |
| Latest movement delta | `dX=0.06640625`, `dY=0.0`, `dZ=-0.3388671875`, planar `0.3453125552354311` |

## Files changed in this milestone

| File | Purpose |
|---|---|
| `scripts\capture-rift-api-reference-coordinate.ps1` | New read-only `RRAPICOORD1` / companion-payload reference capture helper. |
| `scripts\capture-riftscan-proof-pose.ps1` | New wrapper for same-time API reference + RiftScan candidate readback pose capture. |
| `scripts\invoke-gated-forward-smoke.ps1` | New hardened fail-closed wrapper for exact-target one-pulse forward smoke. |
| `scripts\test-capture-rift-api-reference-coordinate.ps1` | Regression for strict marker and companion payload fallback. |
| `scripts\test-capture-riftscan-proof-pose-reference-blocker.ps1` | Regression for missing reference blocker. |
| `scripts\test-capture-riftscan-proof-pose-success.ps1` | Regression for proof-pose wrapper success path. |
| `scripts\test-invoke-gated-forward-smoke.ps1` | Regression for wrapper success, blocked preflight, low age-budget, and hold cap. |
| `scripts\invoke-riftscan-coordinate-readback.ps1` | Hardened DateTime handling, summary path output, warning/source-preview semantics. |
| `scripts\test-invoke-riftscan-coordinate-readback-decode.ps1` | Expanded readback decode/source-preview regression. |
| `docs\riftscan-riftreader-coordinate-candidate-workflow.md` | Documents API reference helper, proof-pose wrapper, gated forward wrapper, and age-budget guard. |
| `docs\recovery\current-truth.md` | Promotes latest current truth to the gated-wrapper forward-smoke + post-recovery validation. |
| `docs\recovery\current-proof-anchor-readback.json` | Machine-readable current state pointer updated to latest gated-wrapper/post-recovery truth. |

## Validation run before handoff

All of these passed after the wrapper hardening and doc/pointer updates:

```powershell
git diff --check
# PowerShell parser checks for changed/new scripts
# JSON parse checks for current-proof-anchor-readback.json and telemetry-proof-coord-anchor.json
.\scripts\test-invoke-gated-forward-smoke.ps1
.\scripts\test-capture-rift-api-reference-coordinate.ps1
.\scripts\test-capture-riftscan-proof-pose-reference-blocker.ps1
.\scripts\test-capture-riftscan-proof-pose-success.ps1
.\scripts\test-invoke-riftscan-coordinate-readback-decode.ps1
.\scripts\test-import-riftscan-coordinate-candidates.ps1
.\scripts\test-promote-riftscan-reference-match-to-proof-anchor.ps1
.\scripts\test-invoke-riftscan-coordinate-readback-proof-gate.ps1
```

`git diff --check` emitted only CRLF warnings for existing text files.

## Critical safety boundaries for the next chat

1. **Do not use Cheat Engine** unless the user explicitly reauthorizes it in that conversation after acknowledging crash risk.
2. **Do not use SavedVariables as live truth.** `ReaderBridgeExport.lua` and similar files are post-save snapshots only.
3. Treat the proof as **session-bound and age-gated**. PID/HWND may be stale after a restart or focus change.
4. Use exact `ProcessId` + `TargetWindowHandle` for any live interaction.
5. Use `invoke-gated-forward-smoke.ps1`; do not send ad hoc `W` pulses.
6. Before input, prefer a fresh proof refresh and wrapper `-DryRun`.
7. If wrapper dry-run blocks on age budget, refresh proof instead of overriding the guard.

## Optimal resume workflow

### 1. Re-check target

```powershell
Get-Process -Id 47560 -ErrorAction SilentlyContinue |
  Select-Object ProcessName,Id,MainWindowHandle,StartTime,Responding
```

If PID/HWND changed, re-bind target and do not reuse old proof artifacts blindly.

### 2. Refresh no-CE proof if age gate is expired

Use a fresh same-time API reference + RiftScan candidate readback:

```powershell
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')
$outRoot = Join-Path (Resolve-Path .\scripts\captures) "resume-proof-refresh-$stamp"
New-Item -ItemType Directory -Path $outRoot -Force | Out-Null
$refFile = Join-Path $outRoot 'resume-api-reference-wide-context.json'

.\scripts\capture-rift-api-reference-coordinate.ps1 `
  -ProcessId 47560 `
  -TargetWindowHandle 0x2122E `
  -OutputRoot $outRoot `
  -OutputFile $refFile `
  -ScanContextBytes 4096 `
  -MaxHits 512 `
  -Json

.\scripts\capture-riftscan-proof-pose.ps1 `
  -ProcessId 47560 `
  -TargetWindowHandle 0x2122E `
  -OutputRoot $outRoot `
  -PoseLabel resume-current `
  -ReferenceFile $refFile `
  -ReferenceMaxAgeSeconds 180 `
  -Json
```

Then promote using one older displaced proof summary plus the fresh pose summary. The known older stable displaced summary is:

```text
C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-warning-count-smoke-20260507-043815\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260507-003823.json
```

Promotion shape:

```powershell
.\scripts\promote-riftscan-reference-match-to-proof-anchor.ps1 `
  -ReadbackSummaryFile '<older-displaced-summary>','<fresh-pose-summary>' `
  -CandidateId 'rift-addon-coordinate-candidate-000001' `
  -ProcessId 47560 `
  -TargetWindowHandle 0x2122E `
  -OutputFile .\scripts\captures\telemetry-proof-coord-anchor.json `
  -MinReferenceDisplacement 1.0 `
  -MaxDeltaError 0.25 `
  -MaxEvidenceAgeSeconds 0 `
  -Json
```

### 3. Run the hardened wrapper dry-run

```powershell
.\scripts\invoke-gated-forward-smoke.ps1 `
  -ProcessId 47560 `
  -TargetWindowHandle 0x2122E `
  -HoldMilliseconds 250 `
  -PulseCount 1 `
  -DryRun `
  -Json
```

Proceed to input only if status is `dry-run-valid` and there is sufficient age budget.

### 4. If live input is still desired, use only the wrapper

```powershell
.\scripts\invoke-gated-forward-smoke.ps1 `
  -ProcessId 47560 `
  -TargetWindowHandle 0x2122E `
  -HoldMilliseconds 250 `
  -PulseCount 1 `
  -Json
```

If it blocks, treat the blocker as real evidence. Refresh proof rather than bypassing.

### 5. After any pulse, update truth docs

Update:

- `docs\recovery\current-truth.md`
- `docs\recovery\current-proof-anchor-readback.json`

Include exact artifact paths, coordinates, deltas, frame-change screenshots, and whether the wrapper passed or failed closed.

## Ready-to-paste prompt for new chat

```text
Resume in C:\RIFT MODDING\RiftReader. Read the newest handoff first: C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-07-072508-gated-wrapper-forward-smoke-handoff.md. Continue the no-CE RiftScan/RiftReader gated movement workflow. Do not use Cheat Engine or SavedVariables as live truth. Treat PID 47560 / HWND 0x2122E as possibly stale; verify exact target first. Use the hardened invoke-gated-forward-smoke.ps1 wrapper only after a fresh proof refresh and dry-run gate. Do not send ad hoc W pulses. Start by checking git status, current-truth.md, current-proof-anchor-readback.json, and the latest 10 commits, then continue with the smallest safe next step.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit and push this handoff/milestone. | Preserves the working state for the next chat. |
| 2 | In the next chat, verify PID/HWND first. | Live target may drift. |
| 3 | Refresh proof before further movement. | The gate is short-lived by design. |
| 4 | Run wrapper `-DryRun` after refresh. | Confirms gate and age budget without input. |
| 5 | Use exactly one wrapper pulse if dry-run is green. | Maintains bounded live risk. |
| 6 | Do not override `MinimumPostReadbackAgeBudgetSeconds`. | It was added from a real live timing failure. |
| 7 | Add screenshot capture into the wrapper next. | Makes future proof artifacts self-contained. |
| 8 | Add a compact wrapper-summary parser. | Speeds SITREP and comparison. |
| 9 | Move from forward proof to turn/facing wrapper next. | Forward proof is now sufficient for this lane. |
| 10 | Keep current-truth as the newest validated source. | Prevents stale historical artifacts from becoming operational truth. |