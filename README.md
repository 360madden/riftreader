# RiftReader

Hybrid Rift tooling project:

- a **Lua addon** in the Rift client for in-game validation
- a **.NET 10 C# memory reader** for external data collection

## Current Focus

Current work is scoped primarily to the **memory reader**.

Constraints:

- target explicitly selected Rift client processes and installs
- do not assume cross-environment compatibility without verification
- keep addon work limited to **validation support** for the reader

Discovery support helpers now live under `scripts/` and are intended to keep
the capture chain aligned while the typed reader work advances:

- `scripts\inspect-capture-consistency.ps1`
  - reports provenance, freshness, and anchor drift across the current capture set
- `scripts\refresh-discovery-chain.ps1`
  - refreshes the current source-chain -> owner -> stat-hub discovery sequence using existing repo scripts
- `scripts\export-discovery-watchset.ps1`
  - derives an owned session watchset from the current discovery artifacts
- `scripts\record-discovery-session.ps1`
  - packages the current artifacts + truth snapshot + sampled watchset bytes for offline decode work

## Repository Layout

```text
RiftReader/
├── addon/
│   ├── ReaderBridgeExport/
│   │   ├── README.md
│   │   ├── RiftAddon.toc
│   │   └── main.lua
│   └── RiftReaderValidator/
│       ├── README.md
│       ├── RiftAddon.toc
│       └── main.lua
├── docs/
│   ├── addon-validation-spec.md
│   ├── cheat-engine-workflow.md
│   ├── offline-session-workflow.md
│   ├── reader-cli-ux.md
│   └── overview.md
├── reader/
│   └── RiftReader.Reader/
│       ├── Cli/
│       ├── Formatting/
│       ├── Memory/
│       ├── Processes/
│       ├── Program.cs
│       └── RiftReader.Reader.csproj
├── scripts/
│   ├── build-reader.cmd
│   ├── deploy-addon.cmd
│   ├── generate-cheatengine-probe.cmd
│   ├── cheatengine-attach-probe.cmd
│   ├── cheatengine-capture-best.cmd
│   ├── cheatengine-exec.cmd
│   ├── cheatengine-exec.ps1
│   ├── cheatengine-reload-probe.cmd
│   ├── install-cheatengine-autorun.cmd
│   ├── export-discovery-watchset.cmd
│   ├── record-discovery-session.cmd
│   ├── run-reader.cmd
│   ├── sync-cheatengine.cmd
│   ├── sync-addon.cmd
│   ├── validate-addon.cmd
│   └── watch-readerbridge-export.cmd
├── tools/
│   └── reverse-engineering/
│       ├── README.md
│       └── install-tools.ps1
├── .gitignore
├── README.md
└── RiftReader.slnx
```

## Reader Scope

The initial reader scaffold is responsible for:

- attaching to a target Rift process by PID or process name
- opening a read-only process handle
- performing a raw memory read for a supplied address range
- printing a hex dump for inspection while pointer maps and typed models are still being defined
- growing into a CLI with robust switches, intuitive help, and colorized/highlighted output where supported

## Current Product Bias

Current implementation work should prefer a **small working reader** over a
perfectly generalized one.

The immediate product target is a narrow typed player snapshot mode that can
already prove useful:

- resolve the current best player-signature family
- prefer the CE-confirmed sample when available
- read a few stable fields directly from memory
- compare those fields against the latest ReaderBridge export

That gives the project a usable reader sooner while leaving room to refine the
anchor, offsets, and structure model later.

## Addon Validation Scope

The addon layer currently contains:

- `RiftReaderValidator`
  - manual snapshot capture
  - small in-game validator UI
  - narrow API-visible comparison snapshots
- `ReaderBridgeExport`
  - thin export layer over an installed `ReaderBridge` addon
  - richer normalized player/target telemetry snapshots for the reader
  - falls back to direct Rift API reads if `ReaderBridge.State` is not visible

The validator addon is intentionally small. Its current job is to:

- capture **API-visible** player snapshots on demand
- record a small rolling history in saved variables
- emit a few high-value validation markers such as zone/role/combat transitions
- stay out of the reader's core reverse-engineering path

The ReaderBridge export path avoids re-implementing ReaderBridge's telemetry
collection logic in this repo while still giving the C# reader a structured
saved-variable contract to consume.

## First Typed Reader Target

The reader now has two near-term targets:

1. **discovery modes**
   - string / numeric / pointer / module scans
   - Cheat Engine probe generation
   - grouped player-signature family capture
2. **first working typed reader modes**
   - `--read-player-current`
   - resolves the current best player-family sample
   - prefers a verified coord-trace object anchor when it belongs to the current process and still matches current exported state
   - reads level / health / coords directly from memory
   - compares them against the latest ReaderBridge export
   - `--read-player-orientation`
   - reuses the owner-selected source component
   - surfaces the artifact-side basis forward-row agreement and the live helper derives actor yaw / pitch from the full source basis matrix, with forward/up/right rows at `+0x60/+0x6C/+0x78` and a duplicate block at `+0x94/+0xA0/+0xAC`
   - `--read-player-coord-anchor`
   - loads the latest verified coord-triplet trace artifact
   - validates the traced instruction bytes as a module-local pattern
   - reports the inferred coord-base-relative access offset and derived object-relative field offsets
   - reads the trace-derived destination sample back through memory and compares it against the latest ReaderBridge export when possible
   - also reports the traced upstream source-object candidate from the live register context and verifies its coord sample against ReaderBridge when possible

Discovery-oriented modes:

- generic scan:
  - `--scan-string <text>`
  - `--scan-int32 <value>`
  - `--scan-float <value> [--scan-tolerance <epsilon>]`
  - `--scan-double <value> [--scan-tolerance <epsilon>]`
- ReaderBridge-assisted scan:
  - `--scan-readerbridge-player-name`
  - `--scan-readerbridge-player-coords`
  - `--scan-readerbridge-player-signature`
  - `--scan-readerbridge-identity`
- Cheat Engine helper generation:
  - `--cheatengine-probe`
  - `--cheatengine-probe-file <path>`
- reference scan:
  - `--scan-pointer <address>`
- module-aware scan:
  - `--list-modules`
  - `--scan-module-pattern "<aa bb ?? cc>" [--scan-module-name <module>]`

This is intended as the first practical bridge between:
- addon-visible truth
- and raw process memory evidence

The first typed reader mode is intended as the first practical bridge between:
- grouped discovery output
- and a usable memory-backed player snapshot

## Build

```powershell
dotnet build .\RiftReader.slnx
```

Or use:

- `C:\RIFT MODDING\RiftReader\scripts\build-reader.cmd`

## Run

Attach only:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 1234
```

Or use:

- `C:\RIFT MODDING\RiftReader\scripts\run-reader.cmd -- --pid 1234`

Attach and read a raw address range:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 1234 --address 0x7FF600001000 --length 64
```

Normalize the latest addon snapshot into reader-friendly output:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --addon-snapshot
```

Emit that snapshot as JSON:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --addon-snapshot --json
```

Normalize the latest ReaderBridge export snapshot:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --readerbridge-snapshot
```

Emit that ReaderBridge snapshot as JSON:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --readerbridge-snapshot --json
```

Scan a process for a specific string:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-string Atank --scan-encoding both --scan-context 32 --max-hits 16
```

Scan for an exact 32-bit integer value such as current health:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-int32 17027 --scan-context 32 --max-hits 16
```

Scan for a floating-point coordinate with tolerance:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-float 7389.71 --scan-tolerance 0.01 --scan-context 32 --max-hits 16
```

Load the latest ReaderBridge export and scan for the current player name:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-player-name --scan-context 32 --max-hits 16
```

Load the latest ReaderBridge export and scan for the current player coordinate triplet as contiguous floats:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-player-coords --scan-context 32 --max-hits 16
```

Rank coordinate hits by nearby exported player fields such as health, level, and location text:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-player-signature --scan-context 96 --max-hits 12
```

This mode now groups repeated hits into layout families so duplicated cache blobs are easier to separate from one-off UI/log copies.

Discovery maintenance helpers:

- `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1`
  - read-only provenance, freshness, and anchor-mismatch report over the current capture set
- `C:\RIFT MODDING\RiftReader\scripts\refresh-discovery-chain.ps1`
  - reruns the current stable discovery sequence in one pass using the existing capture scripts
- `C:\RIFT MODDING\RiftReader\scripts\export-discovery-watchset.ps1`
  - emits a named watchset from the current owner/source/stat artifacts for offline session work
- `C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.ps1`
  - freezes the current artifact chain plus sampled memory regions into `scripts\sessions\...`

Derive a likely identity string such as `Name@Shard` from the latest ReaderBridge export and scan for it:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-identity --scan-encoding ascii --scan-context 32 --max-hits 8
```

Scan for references to a candidate address:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-pointer 0x2039DD70 --pointer-width 8 --scan-context 32 --max-hits 16
```

Generate the current Cheat Engine probe script from the latest ReaderBridge export and the best grouped player-signature families:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --cheatengine-probe --scan-context 192 --max-hits 8
```

Read the current player snapshot from memory using the best available grouped family:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current
```

Emit that player snapshot as JSON:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
```

One-command product path: refresh the addon export, try to refresh the CE-backed
player-family confirmation only when asked, then read the current player snapshot:

```powershell
C:\RIFT MODDING\RiftReader\scripts\read-player-current.cmd
```

JSON output:

```powershell
C:\RIFT MODDING\RiftReader\scripts\read-player-current.cmd -Json
```

Force an anchor refresh before the read:

```powershell
C:\RIFT MODDING\RiftReader\scripts\read-player-current.cmd -RefreshAnchor -Json
```

Offline session workflow:

```powershell
C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.cmd -Label baseline -SampleCount 20 -IntervalMilliseconds 500
```

Export only the current watchset:

```powershell
C:\RIFT MODDING\RiftReader\scripts\export-discovery-watchset.cmd
```

Reader-only session sampler:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --record-session --session-watchset-file .\scripts\captures\session-watchset.json --session-output-directory .\scripts\sessions\20260409-baseline --session-sample-count 20 --session-interval-ms 500 --session-label baseline --json
```

See:

- `C:\RIFT MODDING\RiftReader\docs\offline-session-workflow.md`

Capture the first live coord-triplet access and validate the instruction as a
module-local pattern candidate:

```powershell
C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.cmd -Json
```

Capture the nearby instruction cluster around the latest verified coord trace:

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.cmd -Json
```

Capture the stronger pre-coord source chain that feeds that xyz cluster:

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.cmd -Json
```

Read the latest verified coord-triplet trace artifact back through the reader
and derive the current code-path-backed anchor details:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-coord-anchor --json
```

List modules in the attached Rift process:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --list-modules
```

Run a module-local AOB/signature scan against the main Rift module:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-module-pattern "4D 5A" --scan-module-name rift_x64.exe --scan-context 16
```

## Helper Scripts

- `C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd` - syntax-check all project Lua addons with `luac`
- `C:\RIFT MODDING\RiftReader\scripts\deploy-addon.cmd` - copy all project addons into the Rift `Interface\AddOns` folder
- `C:\RIFT MODDING\RiftReader\scripts\sync-addon.cmd` - validate and deploy all project addons in one step
- `C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd` - wait for `ReaderBridgeExport.lua` to appear or change, then run the reader automatically
- `C:\RIFT MODDING\RiftReader\scripts\generate-cheatengine-probe.cmd` - generate the current CE Lua helper from the live ReaderBridge export and the top grouped signature families
- `C:\RIFT MODDING\RiftReader\scripts\install-cheatengine-autorun.cmd` - install the CE autorun bootstrap that loads the repo-owned helper script
- `C:\RIFT MODDING\RiftReader\scripts\sync-cheatengine.cmd` - regenerate the CE helper and refresh the autorun bootstrap in one step
- `C:\RIFT MODDING\RiftReader\scripts\cheatengine-exec.ps1` / `C:\RIFT MODDING\RiftReader\scripts\cheatengine-exec.cmd` - send Lua to a running Cheat Engine instance through the CE Lua server
- `C:\RIFT MODDING\RiftReader\scripts\cheatengine-reload-probe.cmd` - reload the generated probe into a CE instance that already has the Lua server enabled
- `C:\RIFT MODDING\RiftReader\scripts\cheatengine-attach-probe.cmd` - remotely reload the probe and run `RiftReaderProbe.attachAndPopulate()`
- `C:\RIFT MODDING\RiftReader\scripts\cheatengine-capture-best.cmd` - remotely append the current best-family sample set to `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\probe-samples.tsv`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-command.ps1` / `C:\RIFT MODDING\RiftReader\scripts\post-rift-command.cmd` - primary native PowerShell no-focus Rift command helper; posts AHK-style raw keydown/keyup messages with proper scan-code `lParam` values and verifies success by watching `ReaderBridgeExport.lua`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1` / `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.cmd` - native PowerShell no-focus Rift gameplay-key helper for movement or hotbar-style input tests
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1` / `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.cmd` - force a fresh ReaderBridge export via the native no-focus `/reloadui` path and automatically fall back to the known-good AutoHotkey helper if the native post does not advance `ReaderBridgeExport.lua`
- `C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1` / `C:\RIFT MODDING\RiftReader\scripts\read-player-current.cmd` - preferred one-command player-reader path; refreshes the ReaderBridge export, then runs `--read-player-current` using the best available fast path. If no full player family is available, it can nudge movement and retry to reacquire one. Use `-RefreshAnchor` to refresh the CE-backed family confirmation before the read, or `-RefreshTraceAnchor` to refresh a stale saved coord trace before the read.
- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1` / `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.cmd` - actor yaw/pitch helper; reads the live selected source object, derives yaw/pitch from the forward row of the source basis matrix, reports the duplicated basis blocks and their agreement, and stores current/previous actor-orientation captures so live facing changes can be compared quickly
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1` / `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.cmd` - runs a before/after actor-orientation capture around a no-focus key stimulus and reports yaw/pitch/vector/coord deltas; useful for validating whether a given key actually turns the actor in the live client
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1` / `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.cmd` - profiles multiple no-focus key stimuli in one pass, classifies them as actor-turn / no-turn / movement / mixed, and records basis-quality metrics so control bindings can be triaged quickly
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1` / `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.cmd` - uses Cheat Engine's debugger to trap the first verified access to the current player coord triplet, tries CE-confirmed candidate addresses when available, captures the instruction and register context, and validates the captured instruction bytes through the reader's module-local pattern scan
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1` / `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.cmd` - captures a small disassembly window around the latest verified coord trace through Cheat Engine, highlights nearby instructions that reuse the traced base register, and labels offsets that line up with the current derived coord/level/health fields
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1` / `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.cmd` - derives the pre-coord source/destination handoff chain from the trace cluster, identifies the likely source-object load and resolve call, and verifies a stronger module-local source-chain pattern
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-accessor-family.ps1` / `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-accessor-family.cmd` - enumerates the sibling source-object accessors that share the same preparation function and verifies each accessor pattern against the live module
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1` / `C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.cmd` - breaks on the source-object load, captures the owning selector object / container / selected index, verifies the selected source object against the current coord trace, and records the selector-owner path as a JSON artifact
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1` / `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.cmd` - walks the stable owner object discovered by the selector trace, classifies linked children (source-wrapper, owner-backref wrapper, owner-state wrapper), and records the live owner graph as a structured artifact
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1` / `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.cmd` - enumerates the stable owner container entries, classifies the live selected-source component against sibling component records, and records the current owner/component table as a JSON artifact
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1` / `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.cmd` - walks the owner-component artifact plus current ReaderBridge snapshot, identifies raw-unit-id-bearing identity components, ranks shared child stat hubs, and records the current stat-side graph as a JSON artifact
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-thread-command.ps1` / `C:\RIFT MODDING\RiftReader\scripts\post-rift-thread-command.cmd` - experimentally try a no-focus `PostThreadMessage` command injection against the Rift UI thread and verify success by watching `ReaderBridgeExport.lua`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-command-ahk.ahk` / `C:\RIFT MODDING\RiftReader\scripts\post-rift-command-ahk.ps1` / `C:\RIFT MODDING\RiftReader\scripts\post-rift-command-ahk.cmd` - AutoHotkey fallback/reference helper kept as the known-good message-pattern baseline
- `C:\RIFT MODDING\RiftReader\scripts\ce-float-scan.lua` - tracked CE Lua helper for exact float scans plus directional next-scan workflows (`changed`, `increased`, `decreased`)
- `C:\RIFT MODDING\RiftReader\scripts\smart-capture-player-family.ps1` / `C:\RIFT MODDING\RiftReader\scripts\smart-capture-player-family.cmd` - CE-assisted player-signature family helper that can retry across multiple movement axes (`X`, then `Z` by default), uses directional next-scans after movement instead of depending only on a second exact-value scan, normalizes non-`X` CE hits back to the player-structure base address, and writes `C:\RIFT MODDING\RiftReader\scripts\captures\ce-smart-player-family.json` so the standard capture flow can prefer or directly confirm the CE-backed family on later runs
- `C:\RIFT MODDING\RiftReader\scripts\open-reclass.ps1` / `C:\RIFT MODDING\RiftReader\scripts\open-reclass.cmd` - launch the repo-local ReClass.NET x64 build staged under `C:\RIFT MODDING\RiftReader\tools\reverse-engineering\ReClass.NET`
- `C:\RIFT MODDING\RiftReader\scripts\open-x64dbg.ps1` / `C:\RIFT MODDING\RiftReader\scripts\open-x64dbg.cmd` - launch the repo-local x64dbg x64 build staged under `C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg`

Reverse-engineering tool staging:

```powershell
C:\RIFT MODDING\RiftReader\tools\reverse-engineering\install-tools.ps1
```

That refreshes the repo-local copies of:

- `ReClass.NET`
- `x64dbg`

See:

- `C:\RIFT MODDING\RiftReader\tools\reverse-engineering\README.md`

The deploy scripts auto-detect common Rift addon locations and also respect the `RIFT_ADDONS_DIR` environment variable if you want to override the target.

Watcher examples:

```powershell
C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd
C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd -Json
C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd -RunInitial
C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd -Once -FilePath "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\...\ReaderBridgeExport.lua"
```

Cheat Engine workflow:

```powershell
C:\RIFT MODDING\RiftReader\scripts\sync-cheatengine.cmd
```

Then restart Cheat Engine once so the Lua server bootstrap loads. After that, you can drive the probe remotely:

```powershell
C:\RIFT MODDING\RiftReader\scripts\cheatengine-attach-probe.cmd
```

Capture the current top-family sample set to disk:

```powershell
C:\RIFT MODDING\RiftReader\scripts\cheatengine-capture-best.cmd -Label baseline
```

See:

- `C:\RIFT MODDING\RiftReader\docs\cheat-engine-workflow.md`

Force a fresh ReaderBridge save and immediately load the new snapshot:

```powershell
C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.cmd
```

Run the CE-assisted player-family smart capture:

```powershell
C:\RIFT MODDING\RiftReader\scripts\smart-capture-player-family.cmd
```

After that file exists, the normal reader capture mode will automatically prefer the CE-backed family when it still matches the current grouped scan, and will use `SelectionSource = ce-confirmed` when the helper captured direct sample-address matches.

Recent CE improvement:

- the smart family helper now uses directional next-scans (`increased` / `decreased` / `changed`) after movement instead of relying only on a second exact-value scan
- this materially improved live narrowing on the current Rift client from zero direct triplet confirmations in some runs to dozens of moved-axis candidates and multiple CE-confirmed family sample matches
- the coord write-trace helper now rejects unverified debugger hits instead of treating unrelated reads as successful writer captures
- the coord trace helper now treats the current player base as a coord-triplet anchor, accepts verified `x/y/z` member accesses, and can walk CE-confirmed candidate addresses instead of only the default current-player sample
- the reader now has a matching `--read-player-coord-anchor` mode that loads the saved trace artifact, validates the traced bytes against the live module, reports the inferred coord-base-relative offset from the verified instruction, and surfaces the traced upstream source-object candidate when it can be reconstructed from the saved register context
- the selector-owner trace now confirms a stable owner path:
  - owner object at `0x1AED5A67610`
  - owner container at `0x1AEE411B280`
  - selector index `6`
  - selected source object `0x1AEBA302B40`
  - and repeated runs kept that mapping stable on the current client session
- the owner-graph capture now classifies the owner-linked child roles on the current client:
  - `owner + 0xA0` -> source-wrapper (`child + 0x8 == selected source`, `child + 0x100 == owner`)
  - `owner + 0xA8 / 0xB0` -> owner-backref wrapper (`child + 0x68 == owner`)
  - `owner + 0xD0 / 0xD8 / 0xE0` -> owner-state wrapper (`child + 0x8 == owner + 0xC8`)
- the owner-component capture now shows that the stable owner container behaves more like a component table than a wrapper list:
  - entry `6` is the live selected-source transform component
  - entries `0..15` are sibling component-like records under the same owner container
  - during live movement validation, entry `6` was the only enumerated component whose coord triplets changed, which strengthens the interpretation that index `6` is the current transform-bearing component
- the new stat-hub graph capture now shows the first connected stat-side graph rather than only isolated candidate components:
  - identity-bearing components currently include indices `9`, `12`, and `13`, each of which embeds the raw player unit id `0x035400012FA2D207`
  - shared stat hub `0x1AEE40A4600` is currently referenced by components `12`, `13`, `14`, and `15` and contains repeated level matches at offsets `0x100` and `0x138`
  - shared stat hub `0x1AEE411B4B0` is currently referenced by components `7` and `8`, contains a level match at `0x208`, and carries an owner backref at `0x108`
  - shared hub `0x1AEBBF6E380` is currently referenced by components `12`, `13`, `14`, and `15` and contains the first stable resource/resourceMax pair signal in the stat-side graph
- `--read-player-current` now attempts that derived object anchor as a fast path before falling back to cached family samples and grouped rescans

## Next Milestone

Ship the first narrow typed player snapshot mode quickly, then refine it with
better anchors:

- today: grouped family selection plus direct field reads
- next: ReClass/x64dbg-backed structure refinement
- later: module signatures, pointer paths, and broader entity coverage
