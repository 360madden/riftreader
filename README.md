# RiftReader

Hybrid Rift tooling project:

- a **Lua addon** in the Rift client for in-game validation
- a **.NET 10 C# memory reader** for external data collection

## Current Focus

Current work is scoped primarily to the **memory reader**.

Constraints:

- target the **Rift PTS test server only**
- do not assume live-server compatibility
- keep addon work limited to **validation support** for the reader

## Repository Layout

```text
RiftReader/
├── addon/
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
│   └── validate-addon.cmd
├── .gitignore
├── README.md
└── RiftReader.slnx
```

## Reader Scope

The initial reader scaffold is responsible for:

- attaching to a target Rift PTS process by PID or process name
- opening a read-only process handle
- performing a raw memory read for a supplied address range
- printing a hex dump for inspection while pointer maps and typed models are still being defined
- growing into a CLI with robust switches, intuitive help, and colorized/highlighted output where supported

## Addon Validation Scope

The helper addon is intentionally small. Its current job is to:

- capture **API-visible** player snapshots on demand
- record a small rolling history in saved variables
- emit a few high-value validation markers such as zone/role/combat transitions
- stay out of the reader's core reverse-engineering path

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

## Helper Scripts

- `C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd` - syntax-check the Lua addon with `luac`
- `C:\RIFT MODDING\RiftReader\scripts\deploy-addon.cmd` - copy the addon into the Rift `Interface\AddOns` folder
- `C:\RIFT MODDING\RiftReader\scripts\sync-addon.cmd` - validate and deploy in one step

The deploy scripts auto-detect common Rift addon locations and also respect the `RIFT_ADDONS_DIR` environment variable if you want to override the target.

## Next Milestone

Replace ad hoc raw reads with documented PTS-specific pointer maps, typed models, and addon-backed validation snapshots that can later be compared against reader output.
