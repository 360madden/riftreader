---
state: historical
as_of: 2026-04-21
---

# Actor Truth Root-Family Handoff (2026-04-21)

## Scope

This handoff freezes the current state of the **live player actor truth**
recovery work on:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\`

The work in this pass was focused on:

1. keeping `--read-player-actor-coords` as the canonical actor-coordinate truth path
2. enriching actor-coordinate truth with **stable owner/root-family provenance**
3. carrying the same provenance into `--read-player-actor-truth`
4. proving whether the old fixed owner chain was stable enough to promote
5. attempting a full post-relaunch validation on a fresh `rift_x64` PID

This document is a session handoff for the next agent, not a replacement for:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`

## Snapshot metadata

| Field | Value |
|---|---|
| State | `historical` |
| As of | `2026-04-21` |
| Branch | `xyz` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Head commit | `f8c862a8a70b85f97e00e8c8b649ba52b912a3d9` |
| Head summary | `Add root-family provenance to actor truth readers` |
| Validation status | working on live PID before relaunch; blocked on explicit fresh-relaunch validation |

## Main conclusion

| Question | Answer |
|---|---|
| Best way to get actor coordinate truth right now | `--read-player-actor-coords` |
| Is actor-coordinate truth still the trace-backed source-object path | **Yes** |
| Is the old fixed `2 / 3` owner chain the stable final owner | **No** |
| What is the better abstraction above the truth surface | **Root family / current-process root cluster** |
| Is a single exact higher shared ancestor proven | **No** |
| Is root-family provenance now surfaced directly in coord/truth reader output | **Yes** |

## Current canonical commands

```powershell
dotnet run --project "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj" -- --process-name rift_x64 --read-player-actor-coords --json
dotnet run --project "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj" -- --process-name rift_x64 --read-player-actor-truth --json
dotnet run --project "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj" -- --process-name rift_x64 --dump-player-actor-truth-chain --scan-context 128 --max-hits 12 --json
dotnet run --project "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj" -- --process-name rift_x64 --refresh-player-coord-trace --json
```

## What is solved

| Area | Status | Notes |
|---|---|---|
| Actor coordinates truth | working | canonical read path is `--read-player-actor-coords` |
| Actor orientation truth | working | canonical read path is `--read-player-actor-orientation` / process-attached `--read-player-orientation` |
| Combined actor truth | working | `--read-player-actor-truth` |
| Coord trace auto-refresh | working | stale coord-trace artifacts auto-refresh when current-process trace reacquisition succeeds |
| Root-family clustering | working | integrated into truth-chain dump and now consumed by coord/truth readers |
| Canonical root-family instance selection | working | current-process selector prefers the most observed live instance inside the best root family |

## Important current technical truth

### 1) Coordinate truth surface

| Item | Value |
|---|---|
| Instruction anchor | `rift_x64.exe+0x93560E` |
| Instruction | `movss xmm0,[rsi+15Ch]` |
| Promoted coord source surface | trace-backed source object |
| Coord offsets | `+0x48 / +0x4C / +0x50` |
| Canonical live coord command | `--read-player-actor-coords` |

### 2) Structural ownership truth

The correct current interpretation is:

- **do not** treat one fixed parent/root address pair as the stable final owner
- **do** treat the best **current-process root family** as the stronger structural abstraction
- use the coord reader for actual coordinates, and use the root-family provenance for
  ownership context

## Live evidence before the relaunch attempt

The last clean live validation before the explicit relaunch was on:

| Field | Value |
|---|---|
| Process | `rift_x64 [48840]` |
| Coord object | `0x1EED9179330` |
| Coords | `7199.9272 / 871.7709 / 3029.3923` |
| Coord match | `true` |
| Best parent/root chain | `0x1EEB13B2160 -> 0x1EED91793B8` |
| Best root family | `0x1EED9170000` |
| Root-family observations | `4 / 5` |
| Distinct family instances | `2` |
| Canonical root-family instance | `0x1EED91793B8` |
| Canonical instance observations | `3 / 5` |

## Important caution about addresses

| Item | Meaning |
|---|---|
| `0x1EED9170000` | **process-local family region**, not a cross-session constant |
| `0x1EED91793B8` | best current canonical instance for PID `48840`, not a universal hardcoded root |
| Earlier sessions used other family regions | this confirms the reader should carry **derived provenance**, not hardcoded owner addresses |

In other words:

- the **algorithm** is stable
- the **exact addresses** are not

## What was changed in code

| File | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Program.cs` | Added truth-structural-context analysis, canonical root-family instance selection, and coord/truth enrichment |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Models\PlayerActorCoordReadResult.cs` | Added root-family summary field |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Models\PlayerActorCoordReader.cs` | Initialized new provenance fields |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Models\PlayerActorTruthReadResult.cs` | Added best-chain / best-root-family / compact root-family summary |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Formatting\PlayerActorCoordReadTextFormatter.cs` | Added root-family provenance text |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Formatting\PlayerActorTruthReadTextFormatter.cs` | Added same provenance text for combined truth |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs` | Updated CLI notes to document the new provenance in coord/truth reads |

## Commit landed

| Field | Value |
|---|---|
| Commit | `f8c862a8a70b85f97e00e8c8b649ba52b912a3d9` |
| Subject | `Add root-family provenance to actor truth readers` |

## Validation completed

| Check | Result |
|---|---|
| `dotnet build "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj"` | passed |
| `--read-player-actor-coords --json` on PID `48840` | passed |
| `--read-player-actor-truth --json` on PID `48840` | passed |
| explicit kill/relaunch of `rift_x64.exe` | process restarted |
| clean post-relaunch coord/truth validation | **blocked** |

## Explicit relaunch blocker

The explicit restart produced:

| Field | Value |
|---|---|
| Old PID | `48840` |
| New PID | `42048` |
| New process detected | yes |
| Main window title after relaunch | `Error` |
| Post-relaunch coord validation | not completed |

Interpretation:

- the restart **did** create a fresh process
- but the relaunched client was not in a clean playable/inspectable state
- this blocks the intended “fresh process, then immediately revalidate coord truth”
  proof

## What is not yet proven

| Item | Status |
|---|---|
| Clean post-relaunch validation on a healthy new Rift client window | not done |
| Cross-session stability of the same root-family *type* without manual recovery | not fully proven |
| Higher structural abstraction above the current-process root family | not proven |
| One permanent fixed owner/root address pair | explicitly rejected |

## Best next starting point for the next agent

If the next agent needs actor coordinate truth immediately:

1. start with  
   - `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj --read-player-actor-coords --json`
2. trust the returned:
   - coord object
   - best chain
   - best root family
   - canonical root-family instance
3. do **not** hardcode any returned owner/root address as session-independent truth

If the next agent wants to finish the blocked validation:

1. fix or diagnose the fresh relaunch `Error` state
2. rerun:
   - `--read-player-actor-coords --json`
   - `--read-player-actor-truth --json`
3. compare whether the new process still yields:
   - a working trace-backed coord read
   - a best root family
   - a canonical instance inside that family

## Recommended next actions

1. diagnose why the explicit fresh relaunch returned a `MainWindowTitle = Error`
2. add a readiness gate before automatic post-relaunch truth validation
3. carry `RootFamilySummary` into `PlayerActorTruthChainDumpResult` too for
   output consistency
4. add a small regression test around canonical root-family instance selection
5. once relaunch validation is healthy, update
   `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` with the new
   “coord reader includes root-family provenance” status

## Later same-day branch note (not part of the original frozen snapshot)

Later on **April 21, 2026**, branch `xyz` was revalidated on a healthy live
process (`rift_x64` PID `16344`, main window title `RIFT`).

Important later findings:

- the first retry hit a different blocker from the historical relaunch `Error`
  state: Windows Controlled Folder Access blocked creation of the debug-trace
  refresh output directory under
  `C:\RIFT MODDING\RiftReader\scripts\captures\debug-traces\...`
- once that access was allowed, both
  `--read-player-actor-coords --json` and `--read-player-actor-truth --json`
  succeeded again on PID `16344`
- the later aligned rerun produced the same best parent/root chain and canonical
  root-family instance in both the coord and combined truth reads:
  - best parent/root chain: `0x27046B3FF00 -> 0x2705579D928`
  - best root family: `0x27055790000`
  - canonical root-family instance: `0x2705579D928` (`3 / 5` observations)

This later note improves branch operating context, but it does **not** explain
the original explicit relaunch `MainWindowTitle = Error` state that blocked the
frozen handoff snapshot above.

See the follow-up analysis note:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-21-actor-truth-rerun-after-controlled-folder-access-allow.md`
