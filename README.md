# RiftReader

Hybrid Rift tooling project:

- a **Lua addon** in the Rift client for in-game validation
- a **.NET 10 C# memory reader** for external data collection

## Current Focus

Current work is scoped to the **memory reader only**.

Constraints:

- target the **Rift PTS test server only**
- do not assume live-server compatibility
- keep addon work deferred until validation wiring is needed

## Repository Layout

```text
RiftReader/
├── docs/
│   └── overview.md
├── reader/
│   └── RiftReader.Reader/
│       ├── Cli/
│       ├── Formatting/
│       ├── Memory/
│       ├── Processes/
│       ├── Program.cs
│       └── RiftReader.Reader.csproj
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

## Build

```powershell
dotnet build .\RiftReader.slnx
```

## Run

Attach only:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 1234
```

Attach and read a raw address range:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 1234 --address 0x7FF600001000 --length 64
```

## Next Milestone

Replace ad hoc raw reads with documented PTS-specific pointer maps, typed models, and validation snapshots that can later be compared against addon-visible values.
