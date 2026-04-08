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
│   ├── run-reader.cmd
│   ├── sync-addon.cmd
│   ├── validate-addon.cmd
│   └── watch-readerbridge-export.cmd
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

The first comparison-oriented reader target is now a **process memory string
scan**:

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
- reference scan:
  - `--scan-pointer <address>`

This is intended as the first practical bridge between:
- addon-visible truth
- and raw process memory evidence

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

Derive a likely identity string such as `Name@Shard` from the latest ReaderBridge export and scan for it:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-identity --scan-encoding ascii --scan-context 32 --max-hits 8
```

Scan for references to a candidate address:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-pointer 0x2039DD70 --pointer-width 8 --scan-context 32 --max-hits 16
```

## Helper Scripts

- `C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd` - syntax-check all project Lua addons with `luac`
- `C:\RIFT MODDING\RiftReader\scripts\deploy-addon.cmd` - copy all project addons into the Rift `Interface\AddOns` folder
- `C:\RIFT MODDING\RiftReader\scripts\sync-addon.cmd` - validate and deploy all project addons in one step
- `C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd` - wait for `ReaderBridgeExport.lua` to appear or change, then run the reader automatically

The deploy scripts auto-detect common Rift addon locations and also respect the `RIFT_ADDONS_DIR` environment variable if you want to override the target.

Watcher examples:

```powershell
C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd
C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd -Json
C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd -RunInitial
C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.cmd -Once -FilePath "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\...\ReaderBridgeExport.lua"
```

## Next Milestone

Replace ad hoc raw reads with documented environment-specific pointer maps, typed models, and addon-backed validation snapshots that can later be compared against reader output.
