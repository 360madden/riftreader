# Current Truth

_Last updated: April 19, 2026 (live re-triage)_

## Current status

| Area | Status | Truth class | Notes |
|---|---|---|---|
| Low-level reader | working | live truth | Reader runtime remains usable for active work |
| ReaderBridge snapshot load | working | live truth | Fresh snapshot loaded during April 19 re-triage |
| Player current read | working | live truth | Current-player memory still matches ReaderBridge exactly |
| Current-player family anchor | working | live truth | `fam-6F81F26E` still resolves the live player |
| Coord-anchor module pattern | working | live truth | Current-process module pattern still resolves at the updated module offset |
| Coord relative offsets | working | live truth | Current anchor still implies `0x158 / 0x15C / 0x160` |
| Coord-write trace artifact | stale | not current truth | `TraceMatchesProcess = false`; use only for comparison or pattern recovery |
| Source-chain structural reconstruction | partially recovered | structural truth only | The selector/container/source instruction shape is reconstructed again, but not yet as live authority |
| Source-chain absolute trigger addresses | invalid for live use | not current truth | Current artifacts still mix stale absolute trigger addresses with fresh selector scans |
| Selector-owner trace | not re-established | not current truth | Latest artifact is cached fallback, not a live current-process hit |
| Player orientation read | stale | not current truth | Still blocked on a live owner/source rebuild |
| Actor yaw on `scanner-with-debug` | blocked | not current truth | Latest workflow summary is not promotion-ready |
| Camera yaw / pitch / distance on `main` | stale / unverified | not current truth | Do not treat camera outputs on `main` as current until the owner/source chain is live again |
| Authoritative camera controller | not yet isolated | unknown | Still not repo truth on `main` |

## Post-update note

Use this report before trusting older actor/camera captures:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`
- `C:\RIFT MODDING\RiftReader\docs\input-safety.md`

## Live baselines you can trust right now

### Player current

Still working from the cache/blob family:

- family id: `fam-6F81F26E`
- signature: `level@-144|health[1]@-136|health[2]@-128|health[3]@-120|coords@0`
- April 19 live match:
  - level `45`
  - health `18208`
  - coords `7416.6797 / 863.6 / 2957.8198`

### Coord anchor

Still working as a module-local pattern:

- pattern: `F3 0F 10 86 5C 01 00 00`
- current-process module offset observed during April 19 re-triage: `0x93560E`
- inferred coord offsets: `0x158 / 0x15C / 0x160`

## Structural recovery that is useful, but not yet authoritative

- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1` can
  again reconstruct the current selector/container/source instruction shape:
  - `mov rcx,[rax+78]`
  - `mov rdi,[rcx+rdx*8]`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-source-chain.json`
  contains a fresh selector-pattern scan for the current process.
- This structural recovery is useful for **re-discovery only**. It is **not**
  yet safe to treat as live truth because the same artifact still carries stale
  absolute addresses from older trace lineage.

## Broken or stale right now

- `trace-player-selector-owner.ps1` can still remain `armed` without a live hit
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-source-chain.json`
  currently mixes:
  - stale absolute trigger/source addresses
  - with fresh current-process selector scan results
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json`
  is stale for the current process (`TraceMatchesProcess = false`)
- `player-selector-owner-trace.json` is stale until regenerated
- `player-owner-components.json` is stale until regenerated
- `player-actor-orientation.json` is stale until regenerated
- actor yaw remains stale on `main` until
  `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1` produces a
  fresh `actor-yaw-debug-workflow.json` with `Promotion.PromotionReady = true`

## Current authority rules

- If an artifact reports `TraceMatchesProcess = false`, its **absolute
  addresses are not current truth**.
- Stale artifacts may still be used as:
  - pattern hints
  - lineage hints
  - recovery comparison input
- Stale artifacts must **not** be used as:
  - live breakpoint targets
  - live source / owner addresses
  - promotion authority
- A fresh module pattern or selector scan may be trusted only **after** it is
  resolved in the current `rift_x64.exe` process.

## Canonical scripts on `main`

- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`

## Camera script location note

The currently documented live camera helpers are **not present** on the `main`
worktree during this post-update triage pass.

The active camera workflow currently lives on:

- branch: `feature/camera-orientation-discovery`
- worktree: `C:\RIFT MODDING\RiftReader_camera_feature`

Relevant scripts there:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`

Do not treat camera outputs as current truth on `main` until the actor/source
chain is rebuilt and the camera path is revalidated on the updated client.

## Tier-1 artifacts

These remain Tier 1, but they are currently **not current truth** until rebuilt
from live current-process evidence:

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-stat-hub-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json`

## Do not trust these as current truth

- any artifact-derived absolute address from a run where `TraceMatchesProcess = false`
- `player-source-chain.json` trigger/source absolute addresses until they are rebased live
- cached-fallback selector-owner outputs unless replaced by a live current-process hit
- pre-update owner/source/actor-orientation artifacts unless regenerated after the update
- selected-source `+0xB8..+0x150` camera window
- selected-source `+0x7D0` camera basis idea
- `entry4 +0x1D0` as a confirmed direct pitch scalar
