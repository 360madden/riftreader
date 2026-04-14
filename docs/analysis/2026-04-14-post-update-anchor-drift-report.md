# Post-Update Anchor Drift Report (2026-04-14)

## Scope

This note records what changed immediately after the April 14, 2026 game
update, before any repair work is treated as complete.

It is intentionally conservative:

- document what still works
- document what broke
- mark anything stale or unverified clearly
- avoid promoting older captures as current truth

## Short summary

The update did **not** break the low-level reader.

The update **did** break the current owner/source discovery chain that the
actor-orientation and camera workflows depend on.

## Commands run during triage

```powershell
dotnet build C:\RIFT MODDING\RiftReader\RiftReader.slnx
C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1 -Json
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-coord-anchor --json
C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1 -Json -RefreshCluster
C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1 -Json -RefreshSourceChain
C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1 -Json
```

## Triage result

| Area | Result | Notes |
|---|---|---|
| Build | working | `dotnet build` succeeded |
| ReaderBridge snapshot load | working | current player snapshot loaded successfully |
| Player current read | working | still matched live ReaderBridge values |
| Coord-anchor module pattern | working | pattern still matched in the updated module, but at a new module address |
| Trace process linkage | stale | previous trace belonged to an older process instance |
| Source-chain refresh | broken | current cluster logic could not locate the expected source-container load |
| Selector-owner trace | broken | trace status stayed `armed` and never produced a live hit |
| Owner-components refresh | blocked | depends on the broken selector-owner path |
| Actor orientation refresh | blocked/stale | old artifact path no longer safe to trust |
| Camera live recheck on `main` | blocked/stale | current recovery docs reference camera scripts that are not present on the `main` worktree |

## Surviving anchors

### 1. Player-current family still works

Live result from `--read-player-current`:

- family id: `fam-6F81F26E`
- family notes: `location/cache blob`
- signature: `level@-144|health[1]@-136|health[2]@-128|health[3]@-120|coords@0`
- selected address at time of triage: `0x2618C941920`

This path still matched:

- level
- health
- player coordinates

against the current ReaderBridge export.

### 2. Coord-trace-backed module pattern still works

Live result from `--read-player-coord-anchor`:

- instruction pattern: `F3 0F 10 86 5C 01 00 00`
- matched instruction address: `0x7FF77BDF560E`
- matched module offset: `0x93560E`
- access operand: `[rsi+0000015C]`
- inferred coord-base-relative offset: `344`
- inferred coord offsets: `0x158 / 0x15C / 0x160`
- inferred level / health offsets from that coord base: `0xC8 / 0xD0`

The old trace metadata is still stale because it came from a previous process
instance, but the **module-local pattern** still matched the updated binary.

## Broken or stale anchors

### 1. Source-chain assumptions drifted

`capture-player-source-chain.ps1 -Json -RefreshCluster` failed with:

> Unable to locate required instruction: source container load

That means the current disassembly/cluster assumptions around:

- `mov rcx,[rax+78]`
- `mov rdi,[rcx+rdx*8]`

are no longer safe to treat as the live source-chain path.

### 2. Selector-owner trace no longer hits

`trace-player-selector-owner.ps1` produced a status file that remained:

```text
status=armed
```

with no terminal hit/error captured from the expected live trigger path.

### 3. Owner-components and actor orientation are now stale

`capture-actor-orientation.ps1 -Json` failed against stale artifact-derived
addresses with:

> ReadProcessMemory failed ... Win32: 299

That means the current:

- `player-selector-owner-trace.json`
- `player-owner-components.json`
- `player-actor-orientation.json`

should be treated as **pre-update historical evidence**, not current truth,
until regenerated from a repaired chain.

## Camera-specific state

The `main` worktree recovery docs currently reference camera scripts such as:

- `C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1`

Those scripts are **not present** on the current `main` worktree during this
triage pass.

They do exist on:

- git branch: `feature/camera-orientation-discovery`
- worktree used for inspection: `C:\RIFT MODDING\RiftReader_camera_feature`

So camera status right now is:

| Camera area | State |
|---|---|
| Previous camera findings | historical only |
| Camera live scripts on `main` | missing |
| Camera live scripts on feature branch | present |
| Camera yaw/pitch/distance after the update | not revalidated on `main` |

## Input-safety note from this triage pass

Some older helper flows use:

- chat command injection
- `Enter`-driven typing
- `/reloadui`

Those paths are too UI-sensitive for unattended live probing.

For future live camera checks, prefer:

- direct key/mouse/RMB stimulus only
- no chat-command injection by default
- no `/reloadui` unless an operator explicitly wants that disruption

## Small script drift fixed during triage

Two helper scripts were patched locally so background-focus logic can resolve
the current Cheat Engine process name more safely:

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-command.ps1`

The change was narrow:

- if the requested process starts with `cheatengine`, the helper now accepts
  any `cheatengine*` windowed process instead of only the older hardcoded name

This fixes helper drift, but it does **not** repair the broken source-chain.

## Documentation-system requirements surfaced by this update

When the dedicated documentation system is implemented, each update recheck
should capture at least:

1. game build/update date
2. repo branch/worktree used
3. exact commands run
4. which anchors survived
5. which anchors broke
6. which artifacts became stale
7. which scripts are authoritative on which branch
8. whether the run used read-only inspection or live input
9. whether chat/reload/UI-intrusive helpers were used
10. the next required rebuild step

## Immediate next step

Do **not** treat camera or actor orientation outputs as current truth until the
source-chain and selector-owner path are rebuilt on the updated client.
