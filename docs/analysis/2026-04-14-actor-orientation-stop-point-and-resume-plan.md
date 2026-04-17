---
state: historical
as_of: 2026-04-14
---

# Actor Orientation Stop Point and Resume Plan (2026-04-14)

## Scope

This note freezes the current state of the actor yaw / pitch recovery effort on
branch `codex/actor-yaw-pitch` so work can stop cleanly and resume later
without repeating the same dead ends.

This is a **stop-point document**, not a finished recovery report.

## Snapshot metadata

| Field | Value |
|---|---|
| Date | `2026-04-14` |
| Branch | `codex/actor-yaw-pitch` |
| Primary goal | recover working actor yaw / pitch quickly on the updated client |
| Current strategy at stop | transition from broken external-chain recovery to addon-first recovery |
| CE debugger status | historically useful, currently treated as unstable / off-path |
| Live game input status | direct key-only tests were used; no chat/reload path should be resumed automatically |

## Branch working tree state

At stop time, the branch has these local changes:

- modified:
  - `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptions.cs`
  - `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs`
  - `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Program.cs`
  - `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1`
- added:
  - `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Models\PlayerOrientationCandidateFinder.cs`
  - `C:\RIFT MODDING\RiftReader\scripts\find-player-orientation-candidate.ps1`
  - `C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1`

## What was done successfully

### 1. A fast single-process actor-candidate search now exists

A new reader mode was added to avoid the old bloated PowerShell loops:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --find-player-orientation-candidate --max-hits 8 --json
```

This mode:

- loads the latest ReaderBridge snapshot
- finds current coord triplet hits
- probes nearby candidate bases in one reader attach/process
- scores candidates for duplicated coord matches and transform-like basis shape

### 2. The repo still builds

Last successful validation during this branch work:

```powershell
dotnet build C:\RIFT MODDING\RiftReader\RiftReader.slnx
```

Result:

- build succeeded
- `0 warnings`
- `0 errors`

### 3. Direct live key posting still works

These direct key-only tests were posted successfully to the Rift window without
using chat or `/reloadui`:

- `Left`
- `A`
- `D`
- `Q`
- `E`

Posted through:

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`

## What did **not** work

### 1. The old actor basis layout did not recover cleanly

Historical actor orientation layout:

- coord copy 1: `+0x48`
- coord copy 2: `+0x88`
- basis primary: `+0x60 / +0x6C / +0x78`
- basis duplicate: `+0x94 / +0xA0 / +0xAC`

Those offsets are still useful as historical reference, but they did **not**
produce a believable live transform on the updated client.

### 2. The current best coord-matching live candidate is junk

Latest strong coord-matching candidate observed:

- base: `0x2BC82217CC8`
- hit: `0x2BC82217D10`
- matched coord offset: `+0x48`

Why it is not trusted:

- basis rows are not orthonormal
- row values are mostly near-zero noise or mixed garbage
- one row contains a suspicious constant-looking `Z = 12`
- live Left/A/D/Q/E testing did not turn this into a believable actor-facing source

### 3. The old debugger-driven chain is still the wrong primary path

The historically fast chain was:

1. coord-write trace
2. source-chain reconstruction
3. selector-owner trace
4. owner-components
5. selected-source basis read

That path worked historically because it was a short, opportunistic trace path.
It should **not** be treated as currently reliable.

Current blockers:

- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1`
  still depends on pre-update disassembly assumptions
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1`
  still depends on CE debugger / trace timing
- the client/debugger combination is considered unstable

## Why the plan changed

The original recovery path leaned too hard on:

- stale post-update memory structure assumptions
- old debugger-assisted chain recovery
- external-only reconstruction

The better next path is now:

> **addon-first orientation discovery**

That means using the in-game addon layer as a discovery tool, not just as a
validation sidecar.

## Addon-side state at stop time

### Existing addons inspected

- `C:\RIFT MODDING\RiftReader\addon\ReaderBridgeExport\main.lua`
- `C:\RIFT MODDING\RiftReader\addon\RiftReaderValidator\main.lua`
- `C:\RIFT MODDING\RiftReader\addon\RiftReaderApiProbe\main.lua`

### Important finding

The repo currently **does not** aggressively probe/export orientation through
the addon path yet.

Current addon state:

- `ReaderBridgeExport` exports player/target/unit/coord/resource truth
- `RiftReaderValidator` remains a small validator UI/history addon
- `RiftReaderApiProbe` probes some APIs, but does **not** yet explicitly probe:
  - `Inspect.Unit.Heading`
  - `Inspect.Unit.Pitch`
  - hidden orientation-like fields on `Inspect.Unit.Detail`
  - orientation-like fields already present in `ReaderBridge.State`

## Correct resume strategy

### Priority 1: addon-first orientation probe

Patch the existing addons before doing more broad memory work.

#### Patch target A: `RiftReaderApiProbe`

Add a focused orientation probe command that:

- resolves player / target unit IDs
- tries direct API calls if present:
  - `Inspect.Unit.Heading`
  - `Inspect.Unit.Pitch`
- scans `Inspect.Unit.Detail(unit)` for keys matching:
  - `heading`
  - `pitch`
  - `yaw`
  - `face`
  - `facing`
  - `orient`
  - `rotation`
- optionally scans `Inspect.Stat()` for orientation-like keys
- optionally scans `ReaderBridge.State.player` / `.target` for orientation-like keys
- prints the exact returned values in-game through `/rap orientation`

#### Patch target B: `ReaderBridgeExport`

Extend the export snapshot to include a small orientation probe block for
player and target, for example:

- direct API heading/pitch values if present
- detail-field orientation-like candidates
- ReaderBridge-state orientation-like candidates if present

This data should be written into `ReaderBridgeExport_State.current` so it can be
read from saved variables without memory work.

#### Patch target C: `RiftReaderValidator`

Leave this alone unless the first two patches prove useful and a small visual
readout becomes necessary. It is not on the critical path right now.

## Resume checklist

When work resumes, do this in order:

1. **Do not** start by rebuilding the old debugger chain.
2. Patch `RiftReaderApiProbe` with `/rap orientation`.
3. Patch `ReaderBridgeExport` to export orientation probe fields.
4. Validate the Lua syntax:

   ```powershell
   C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd
   ```

5. Deploy/sync the addons:

   ```powershell
   C:\RIFT MODDING\RiftReader\scripts\sync-addon.cmd
   ```

6. In-game, run the addon probe first:
   - `/rap orientation`
   - optionally `/rbx export` then inspect `ReaderBridgeExport.lua`
7. Only if addon/API probing still yields nothing useful, return to:
   - direct live stimulus
   - raw local memory diff
   - no broad debugger-first reconstruction

## Short resume goal

The next session should aim to answer this narrow question first:

> Does the Rift addon/API layer already expose a usable actor heading / pitch /
> facing signal, or at least a strong orientation-like candidate?

Do **not** resume by trying to fully restore the old source-chain /
selector-owner / owner-components workflow unless the addon-first route fails.
