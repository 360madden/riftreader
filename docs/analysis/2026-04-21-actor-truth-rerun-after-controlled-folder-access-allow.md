---
state: historical
as_of: 2026-04-21
---

# Actor Truth Rerun After Controlled Folder Access Allow (2026-04-21)

## Scope

This note freezes the later same-day follow-up live validation on branch
`xyz` after Windows Controlled Folder Access initially blocked the reader's
debug-trace refresh output path.

The goal of this pass was to:

1. confirm whether the Windows protection block was the active blocker
2. rerun `--read-player-actor-coords --json` on a healthy live process
3. rerun `--read-player-actor-truth --json` on the same process
4. record whether coord and combined truth now align on the same current-process
   root-family provenance

## Snapshot metadata

| Field | Value |
|---|---|
| State | `historical` |
| As of | `2026-04-21` |
| Report date | `2026-04-21` |
| Game update/build date | `unknown` |
| Branch | `xyz` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Input mode | `read-only` |
| Validation status | `working` |

## Commands run

```powershell
dotnet run --project "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj" -- --process-name rift_x64 --read-player-actor-coords --json
dotnet run --project "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj" -- --process-name rift_x64 --read-player-actor-truth --json
dotnet run --project "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj" -- --process-name rift_x64 --dump-player-actor-truth-chain --scan-context 128 --max-hits 12 --json
```

## Artifacts checked

- `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\rift315.1@gmail.com\Deepwood\Atank\SavedVariables\ReaderBridgeExport.lua`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-21-actor-truth-root-family-handoff.md`

## Healthy process used

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `16344` |
| Main window title | `RIFT` |
| Start time | `2026-04-21 19:08:30` local |

## Windows protection finding

| Area | Result | Notes |
|---|---|---|
| Debug-trace refresh output creation | blocked, then cleared | Windows Controlled Folder Access initially blocked creation of `C:\RIFT MODDING\RiftReader\scripts\captures\debug-traces\...`; after the app was allowed, the retry succeeded |
| Historical relaunch `Error` state | unresolved | later healthy rerun did not reproduce the `MainWindowTitle = Error` state, but did not explain it either |

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| Actor coordinate truth | working | `--read-player-actor-coords --json` succeeded on PID `16344` |
| Combined actor truth | working | `--read-player-actor-truth --json` succeeded on PID `16344` |
| Coord trace source-object path | working | coord read still resolved through `coord-trace-source-object` |
| Coord instruction anchor | working | `rift_x64.exe+0x93560E` / `movss xmm0,[rsi+15Ch]` |
| Root-family provenance in coord read | working | best chain/root family/canonical instance all present |
| Root-family provenance in combined truth | working | same best chain/root family/canonical instance as the coord rerun |

## Live coord result

| Field | Value |
|---|---|
| Resolution source | `coord-trace-source-object` |
| Signature | `trace-source-object@RDI+coord@0x48` |
| Object base | `0x2705579D8A0` |
| Coord values | `7195.165 / 871.7815 / 3029.225` |
| Match within tolerance | `true` |
| Best parent/root chain | `0x27046B3FF00 -> 0x2705579D928` |
| Best root family | `0x27055790000` |
| Canonical root-family instance | `0x2705579D928` |
| Canonical instance observations | `3 / 5` |

## Live combined truth result

| Field | Value |
|---|---|
| Coord bootstrap source | `readerbridge-snapshot+coord-trace-source-object` |
| Orientation resolution source | `pointer-hop-canonical-d4` |
| Coord source object | `0x2705579D8A0` |
| Orientation-selected surface | `0x27046B69C70` |
| Best parent/root chain | `0x27046B3FF00 -> 0x2705579D928` |
| Best root family | `0x27055790000` |
| Canonical root-family instance | `0x2705579D928` |
| Canonical instance observations | `3 / 5` |

## Interpretation

| Question | Answer |
|---|---|
| Did Windows protection still block the retry after allow? | **No** |
| Did actor-coordinate truth revalidate on the healthy process? | **Yes** |
| Did combined actor truth also revalidate on the same process? | **Yes** |
| Did coord and combined truth align on the same current-process root-family provenance in this rerun? | **Yes** |
| Did this rerun explain the historical explicit relaunch `Error` state? | **No** |

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| Explicit fresh-relaunch readiness proof | partial | current healthy rerun succeeded, but it was not the original blocked explicit relaunch sequence |
| Historical `MainWindowTitle = Error` diagnosis | unresolved | not reproduced in this pass |

## Same-pass chain-dump extension

Later in the same pass, `--dump-player-actor-truth-chain --json` also succeeded
on PID `16344`.

| Field | Value |
|---|---|
| Chain-dump best parent/root chain | `0x2706151E2C0 -> 0x27010D009D0` |
| Chain-dump best root family | `0x27010D00000` |
| Chain-dump canonical root-family instance | `0x27010D009D0` |
| Chain-dump observations | `4 / 5` |
| Distinct family instances | `1` |
| Shared second-hop ancestor candidate | none |

Important interpretation:

- the standalone coord/truth rerun aligned on `0x27046B3FF00 -> 0x2705579D928`
  inside root family `0x27055790000`
- the same-pass chain dump favored a different family:
  `0x2706151E2C0 -> 0x27010D009D0`
- the chain-dump stability ledger recorded four samples on
  `0x27010D009D0` and one sample on `0x2705579D928`
- this means the chain-dump mode is still exposing live structural variability
  above the canonical coord surface even though coord/truth reads themselves
  succeeded cleanly

## Input mode and safety notes

This pass used:

- read-only inspection
- no key stimulus
- no mouse / RMB stimulus
- no chat command injection
- no `/reloadui`

## Immediate next step

Decide whether the chain-dump mode should keep favoring the strongest
stability-vote family (`0x27010D00000` in this pass) or whether the standalone
coord/truth-aligned family (`0x27055790000`) should be surfaced more explicitly
when the two diverge inside the same live session.
