# Cheat Engine Workflow

Cheat Engine is now treated as the **interactive discovery workbench** for
RiftReader, not as a replacement for the reader itself.

## Current operating modes (2026-04-14)

Cheat Engine is back in the workflow, but it should be treated as two separate
lanes:

### 1. CE scan / inspection lane

Use this lane by default when CE is needed:

- grouped family inspection
- changed/unchanged narrowing
- address-list materialization
- quick structure inspection
- manual comparison of candidate families
- helper-script loading through the CE Lua server

This lane is the preferred way to reintegrate CE into active work.

### 2. CE debugger-trace lane

Use this lane only when a trace is explicitly needed:

- coord write trace
- selector-owner trace
- projector trace
- live breakpoint-backed register capture

This lane is currently **opt-in**, not the default first step.

## Immediate attach note

Current operator evidence indicates that CE can fail very early with:

- `Error attaching the windows debugger: 87`

That symptom appears to happen at the debugger-attach layer itself, before the
repo's higher-level trace logic becomes useful.

Because of that:

- do not treat `/reloadui` or later game-window behavior as the primary cause
- do not patch the Lua debugger guards from a single failure alone
- wait for **multiple fresh attach failures** before changing the shared
  `debugProcess(2)` path

## Verified local integration points

From the installed Cheat Engine 7.6 files on this machine:

- `C:\Program Files\Cheat Engine\celua.txt`
  - documents Lua APIs we can use directly:
    - `getProcessIDFromProcessName(...)`
    - `openProcess(...)`
    - `getAddressList()`
    - `createMemoryRecord()`
    - `createMemScan(...)`
    - `createFoundList(...)`
- `C:\Program Files\Cheat Engine\autorun\Lua files in this folder get executed automatically.txt`
- `C:\Program Files\Cheat Engine\autorun\custom\Lua files in this folder get executed automatically as well.txt`

That gives us a safe automation seam:

- generate a repo-owned CE Lua helper from current RiftReader findings
- install a tiny autorun bootstrap in CE
- keep the actual investigation logic in the repo, not in Program Files

## Generated helper artifacts

RiftReader now generates:

- `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderProbe.lua`

And installs a CE bootstrap here:

- `C:\Program Files\Cheat Engine\autorun\custom\RiftReaderBootstrap.lua`

The bootstrap only loads the repo script. It does not hardcode discovery logic.
It also opens a CE Lua server named:

- `RiftReader`

## What the generated CE script does

The generated `RiftReaderProbe.lua` script:

- uses the latest `ReaderBridgeExport.lua` snapshot
- reruns the current grouped player-signature scan against the selected Rift process
- materializes the top candidate families into CE address-list groups
- creates watchable records for:
  - candidate coord triplets
  - nearby level fields
  - nearby health copies
  - nearby location/name strings when present
  - a raw byte-array context window around each sample

This makes it faster to answer questions like:

- which candidate updates first while moving?
- which candidate changes when health changes?
- which family is just UI/cache noise?
- which sample behaves like the authoritative live structure?

## Main commands

Generate/update the CE helper:

```cmd
C:\RIFT MODDING\RiftReader\scripts\generate-cheatengine-probe.cmd
```

Install/update the CE autorun bootstrap:

```cmd
C:\RIFT MODDING\RiftReader\scripts\install-cheatengine-autorun.cmd
```

Do both:

```cmd
C:\RIFT MODDING\RiftReader\scripts\sync-cheatengine.cmd
```

You can also call the reader directly:

```cmd
C:\RIFT MODDING\RiftReader\scripts\run-reader.cmd --process-name rift_x64 --cheatengine-probe --scan-context 192 --max-hits 8
```

## Cheat Engine usage

After running `sync-cheatengine.cmd`:

1. restart Cheat Engine once so the autorun bootstrap loads and opens the `RiftReader` Lua server
2. after that, you can drive the probe remotely:

```cmd
C:\RIFT MODDING\RiftReader\scripts\cheatengine-attach-probe.cmd
```

Or reload the script only:

```cmd
C:\RIFT MODDING\RiftReader\scripts\cheatengine-reload-probe.cmd
```

Then, after moving or changing health, append the current best-family sample set to disk:

```cmd
C:\RIFT MODDING\RiftReader\scripts\cheatengine-capture-best.cmd -Label moved
```

Default capture file:

- `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\probe-samples.tsv`

Useful follow-up actions inside CE:

- move the character slightly and watch which sample/family updates cleanly
- change health and compare which health copies move together
- change target/location and see which candidate survives without turning into UI noise
- use CE access/write tracing on the best behaving sample

## Crash-ledger fields for debugger-trace attempts

When a debugger-trace run fails, capture at least:

1. date/time
2. script used
3. whether CE was already attached or freshly started
4. whether CE and Rift were elevated
5. exact dialog/error text
6. whether a `.status.txt` file was produced
7. whether CE stayed open, detached, or fully crashed
8. whether the failure happened before any breakpoint was armed

This keeps future debugger-guard changes evidence-based.

The debugger-trace scripts now append attach-related failures to the ledger by
default when they fail during `debug-attach` / `debug-ready`:

- `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-state-projector.ps1`

Use `-SkipAttachFailureLedger` only when you explicitly do **not** want that
CSV entry for a run.

Use the repo helper to append one entry:

```powershell
C:\RIFT MODDING\RiftReader\scripts\log-ce-debugger-failure.ps1 `
  -ScriptName trace-player-selector-owner.ps1 `
  -ErrorText "Error attaching the windows debugger: 87" `
  -StatusFile C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.status.txt `
  -CeStayedOpen
```

Ledger path:

- `C:\RIFT MODDING\RiftReader\scripts\captures\ce-debugger-attach-failures.csv`

Summarize the currently logged failures:

```powershell
C:\RIFT MODDING\RiftReader\scripts\summarize-ce-debugger-failures.cmd
```

Structured output:

```powershell
C:\RIFT MODDING\RiftReader\scripts\summarize-ce-debugger-failures.cmd -Json
```

## Expected next use

Use CE to confirm one authoritative candidate family, then encode that layout
back into the C# reader as a typed structure reader instead of continuing with
pure exploratory scans.
