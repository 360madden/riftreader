---
state: historical
as_of: 2026-04-14
---

# Actor Yaw Pointer-Hop Candidate Stop Point (2026-04-14)

## Scope

This report records the first post-update actor-yaw pass that exhausted the
addon-first lane, then recovered fresh **current-process pointer-hop orientation
candidates** from the live player-signature blob without reusing the stale
owner/source chain.

This is a stop-point report, not a finished actor-yaw recovery.

## Snapshot metadata

| Field | Value |
|---|---|
| Report date | `2026-04-14` |
| Game process | `rift_x64` PID `65032` |
| Branch | `codex/actor-yaw-pitch` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Primary goal | recover actor yaw first, pitch second |
| Strategy used | addon-first, then bounded pointer-hop memory discovery |
| Input mode | addon reload + direct key attempts + focused AHK key attempts |
| Validation status | partial: fresh pointer-hop basis candidates found, actor-yaw stimulus validation still blocked |

## Commands run

```powershell
cmd /c C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd
cmd /c C:\RIFT MODDING\RiftReader\scripts\sync-addon.cmd
C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1 -Json
C:\RIFT MODDING\RiftReader\scripts\inspect-readerbridge-orientation.ps1 -Json

dotnet build C:\RIFT MODDING\RiftReader\RiftReader.slnx /m:1
dotnet run --no-build --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
dotnet run --no-build --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --find-player-orientation-candidate --max-hits 8 --json
dotnet run --no-build --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-player-signature --scan-context 96 --max-hits 12

dotnet run --no-build --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --address 0x2BC82A832D0 --length 256 --json
dotnet run --no-build --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --address 0x2BCBF900030 --length 320 --json
dotnet run --no-build --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --address 0x2BCBF902DB0 --length 320 --json

C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1 -Key Left -HoldMilliseconds 400 -BackgroundProcessName Codex
C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1 -Key W -HoldMilliseconds 400 -BackgroundProcessName Codex
# plus focused AutoHotkey foreground-send trials for Escape/W and W
```

## Artifacts checked

- `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\rift315.1@gmail.com\Deepwood\Atank\SavedVariables\ReaderBridgeExport.lua`
- `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-orientation-probe.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-current-anchor.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\ce-smart-player-family.json`

## Surviving anchors

### 1. Reader baseline still holds

- `dotnet build` succeeded on `2026-04-14`
- `--read-player-current` still matched level/health/coords cleanly
- `--read-player-coord-anchor` remained usable as a code-path-backed coord anchor,
  but its trace-owned absolute source/object addresses were still stale and not safe
  to reuse as current truth

### 2. Addon refresh was real, but still produced no orientation signal

After validate/sync plus a live `/reloadui` refresh, the saved export advanced to
`ExportCount = 641`, but the fresh snapshot still had:

- `OrientationProbePresent = false`
- no direct heading/pitch
- no detail/state/stat orientation-like candidates

That means the addon/API lane was genuinely retried and still yielded no usable
actor-yaw signal on this client/session.

### 3. A fresh pointer-hop recovery lead exists

The grouped player-signature scan still surfaced a live unclassified `coords@0`
family, including representative:

- root blob: `0x2BC82A832D0`
- family id: `fam-CEC3708F`

A bounded first-hop pointer walk from that live root blob exposed two child
objects with meaningful orthonormal bases at `+0xD4`:

| Child object | Basis offset | Forward vector | Derived yaw | Derived pitch |
|---|---:|---|---:|---:|
| `0x2BCBF900030` | `0xD4` | `(-0.072707, -0.311154, 0.947575)` | `94.388°` | `-18.129°` |
| `0x2BCBF902DB0` | `0xD4` | `(0.281653, -0.197156, 0.939043)` | `73.304°` | `-11.371°` |

These are **current-process** candidates recovered without the stale
owner/source chain.

## Broken or drifted anchors

### 1. The addon/API layer still does not expose actor orientation

Fresh export, fresh reload, same result: no orientation probe block.

### 2. The old read-only local coord-window candidate search still bottoms out

`--find-player-orientation-candidate` returned `CandidateCount = 0` in this pass.
The direct local-window search is still too narrow for the updated client because
it does not reach the pointer-hop child transforms found under the live
player-signature blob.

### 3. Live key stimulus validation was blocked in this session

Both of these input paths reported success but produced **no observed state
change** in this session:

- background `PostMessage` key posting via `post-rift-key.ps1`
- focused foreground AHK key sends (`W`, `Left`, `Escape` + `W`)

Additional operator evidence received after this pass:

- a live screenshot showed the in-game **RIFT system/options menu** open during
  recent probing

That means at least some of the recent key-validation attempts were landing on a
modal UI layer instead of gameplay state.

Observed result during the validation attempts:

- player coord delta stayed `0`
- pointer-hop candidate yaw deltas stayed `0`

So this stop point is **not** “pointer-hop candidates disproved.”
It is:

> pointer-hop candidates found, but stimulus validation is currently blocked
> because the recent live key attempts were not landing on clean gameplay state.

## Stale artifacts explicitly rejected

These were not reused as current truth:

- stale `player-selector-owner-trace.json`
- stale `player-owner-components.json`
- stale `player-actor-orientation.json`
- stale absolute addresses from earlier selected-source / source-chain captures

## Branch / workflow authority

- living recovery truth remains in `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- this report freezes this specific pointer-hop discovery pass
- camera workflow authority remains on `feature/camera-orientation-discovery`
  and was not promoted during this actor-yaw stop-point pass

## Immediate next step

Do **not** return to the stale owner/source debugger-first chain yet.

Resume from here by solving the live validation lane first:

1. ensure no system/options/chat/modal UI is open before the validation pass
2. get a verified gameplay key or mouse-turn stimulus to land on the active Rift session
3. re-read the pointer-hop candidates above before/after that stimulus
4. keep the candidate whose yaw changes monotonically with low coord drift
5. only if that still fails, deepen the pointer-hop search to second-hop child transforms before revisiting CE scan/manual inspection
