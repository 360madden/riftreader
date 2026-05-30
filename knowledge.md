# Project knowledge

This file gives Codebuff context about your project: goals, commands, conventions, and gotchas.

## What this project is

RiftReader is a **hybrid reverse-engineering and memory-reading toolkit** for the RIFT MMORPG client. It combines:
- **Lua addons** (`addon/`) — in-game validation exports (ReaderBridgeExport, RiftReaderValidator)
- **.NET 10 C# memory reader** (`reader/`) — external process memory reads for player/target state
- **Python & PowerShell scripts** (`scripts/`) — automation, discovery, capture, and workflow orchestration
- **Cheat Engine / x64dbg** — reverse-engineering aid for address/offset discovery

**Primary data source:** the C# memory reader. Addon exports validate reader anchors.

## Quickstart

### Build
```powershell
dotnet build .\RiftReader.slnx
# or: scripts\build-reader.cmd
```

### Test
```powershell
dotnet test reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj
```

### Run (attach to RIFT process, read player)
```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
# or: scripts\run-reader.cmd -- --process-name rift_x64 --read-player-current --json
```

### Validate custom agents (after editing .agents/)
```powershell
python scripts/agent-validate.py --verbose --json
```

### Agent snapshot/rollback
```powershell
python scripts/agent-snapshot.py                        # backup all .agents/*.ts
python scripts/agent-rollback.py <snapshot-dir-name>    # restore from snapshot
```

## Architecture

### Solution projects (`RiftReader.slnx` — .NET 10)
| Project | Purpose |
|---|---|
| `reader/RiftReader.Reader/` | C# memory reader: CLI, Memory, Scanning, Models, Formatting, Navigation, Sessions, Telemetry |
| `reader/RiftReader.Reader.Tests/` | C# unit tests (xUnit + coverlet) |
| `tools/RiftReader.SendInput/` | C# SendInput tool — posts keystrokes to RIFT windows (use `--input-mode ScanCode` first) |
| `tools/RiftReader.WindowTools/` | C# window enumeration and targeting utilities |

### Custom Codebuff agents (`.agents/`)
| Agent | Model | Purpose | When to spawn |
|---|---|---|---|
| `rift-readback` | `deepseek/deepseek-v4-pro` | Read-only coordinate/facing recovery | Every session — instant static chain readback |
| `rift-discovery` | `anthropic/claude-opus-4.7` | Static chain reverse-engineering | Per discovery campaign |
| `rift-proof` | `anthropic/claude-opus-4.7` | Promotion gate evaluation | Per promotion candidate |

**Interaction flow:** Discovery spawns readback for candidate validation; proof spawns readback for gate evidence. All three are backed by `.agents/backup/` snapshot system.

### Promoted static resolvers (current truth)
| Field | Chain expression | Offsets |
|---|---|---|
| Player coordinates | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` | Owner + 0x320 (X), +0x324 (Y), +0x328 (Z) |
| Facing target | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` | 20 bytes before coords, same owner object |
| Yaw formula | `atan2(Z_at_0x314 - playerZ, X_at_0x30C - playerX)` | Read both chains in same cycle |
| Turn rate | `[rift_x64+0x32EBC80]+0x304` (float) | Positive = turning left, negative = right |

### Key directories
| Directory | Purpose |
|---|---|
| `addon/ReaderBridgeExport/` | Lua addon exporting ReaderBridge telemetry to disk |
| `addon/RiftReaderValidator/` | Lua addon for manual snapshots + validation UI |
| `addon/ReaderBridge/` | Referenced ReaderBridge addon (not owned by this repo) |
| `scripts/` | Python/PowerShell automation, discovery helpers, captures, tests |
| `scripts/captures/` | Discovery artifacts (JSON trace files, family data) |
| `scripts/navigation/` | Waypoint JSON for in-game navigation |
| `.agents/` | Custom Codebuff agent definitions (TypeScript) — backed up under `.agents/backup/` |
| `tools/dashboard/` | HTML/JS live data dashboard |
| `tools/rift-game-mcp/` | Node.js MCP server for RIFT game interaction |
| `tools/rift-window-capture/` | C# tool for RIFT window capture (PrintWindow, WGC, DirectX) |
| `tools/reverse-engineering/` | Staged ReClass.NET and x64dbg installs |
| `tools/*.py` | Top-level desktop harness and drive inbox |
| `tools/riftreader_workflow/` | Python workflow orchestration (decision packet, MCP, operator-lite, etc.) |
| `docs/` | Recovery runbooks, analysis, workflow policies, handoffs |
| `docs/recovery/` | Current truth, rebuild runbook, proof anchors, static chain proofs |
| `TomTom/` | TomTom waypoint import/export |

### Data flow
1. **Lua addon** exports validated game state → `ReaderBridgeExport.lua` (SavedVariables snapshot)
2. **C# reader** attaches to `rift_x64.exe`, reads memory directly, compares against addon export
3. **Cheat Engine** helps validate candidate addresses during reverse engineering
4. **Scripts** orchestrate discovery → capture → validation → promotion pipeline

## Key commands

### Typed reader modes
```powershell
# Player snapshot (coord, health, level, name, etc.)
--read-player-current
# Player orientation (yaw/pitch from basis matrix)
--read-player-orientation --pid <pid>
# Coordinate anchor readback
--read-player-coord-anchor
# Target snapshot
--read-target-current
```

### Static chain readback (instant, no movement needed)
```powershell
# Coordinates (2 ReadProcessMemory calls, milliseconds)
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json

# Facing + nav state (same owner, reads 0x30C-0x328)
python scripts/static_owner_facing_discovery.py nav-state --pid <pid> --json
```

### Discovery / scanning
```powershell
# Generic scans
--scan-string <text>
--scan-int32 <value>
--scan-float <value> [--scan-tolerance <eps>]
--scan-pointer <address>
# Module pattern scan (AOB/signature)
--scan-module-pattern "<aa bb ?? cc>" [--scan-module-name <module>]
# List loaded modules
--list-modules
```

### Navigation
```powershell
--import-tomtom-waypoints         # Convert TomTom saved waypoints
--read-navigation-current          # Read-only destination preflight
--plan-navigation-route            # Validate v3 route chain
--navigate-waypoint-route          # Execute multi-segment route
--navigate-waypoints               # Single-segment travel
```

### Facing/yaw discovery pipeline (snapshot → compare → trace)
```powershell
# Phase 1: Baseline + displaced snapshots
python scripts/static_owner_facing_discovery.py snapshot --pid <pid> --hwnd <hwnd> --json
python scripts/static_owner_facing_discovery.py compare --baseline <path> --displaced <path> --json

# Phase 2: Pointer trace
python scripts/pointer_owner_neighborhood_inspector.py ...

# Turn-aware route plan (cross-checks atan2 vs engine 0x304 turn rate)
python scripts/static_owner_turn_aware_route_plan.py ...
```

### Helper scripts (key ones)
| Script | Purpose |
|---|---|
| `scripts/static_owner_coordinate_chain_readback.py` | Instant static chain readback (promoted resolver) |
| `scripts/static_owner_facing_discovery.py` | Owner window snapshots, comparison, nav state with turn rate |
| `scripts/static_owner_turn_aware_route_plan.py` | Turn-aware route planning with engine turn rate cross-check |
| `scripts/static_owner_nav_route_run.py` | Navigation route execution |
| `scripts/static_chain_promotion_readiness.py` | Promotion gate check (all 5 gates) |
| `scripts/agent-validate.py` | Validate custom agent definitions (syntax, schema, tool names) |
| `scripts/agent-snapshot.py` | Snapshot all `.agents/*.ts` files |
| `scripts/agent-rollback.py` | Rollback agents from a snapshot |
| `scripts/read-player-current.cmd` | One-command player snapshot |
| `scripts/trace-player-coord-write.cmd` | Capture coord-write instruction via CE |
| `scripts/smart-capture-player-family.cmd` | CE-assisted player-family confirmation |
| `scripts/riftreader-decision-packet.cmd` | Status/decision packet for autonomous mode |
| `scripts/refresh-readerbridge-export.cmd` | Force fresh addon export via /reloadui |
| `scripts/record-discovery-session.ps1` | Package artifacts + watchset for offline work |

## Conventions

### Shell: PowerShell 7+ (`pwsh`) is the default repo shell
- Use `pwsh` for scripted workflows
- `.cmd` launchers resolve `pwsh` and fail fast if unavailable
- Windows PowerShell 5.1 is transitional only

### C# (.NET 10, C# 12)
- Target framework: `net10.0-windows`
- Nullable enabled project-wide
- No suppressed nullability without `// NilRisk:` comment
- `System.Text.Json` only — no Newtonsoft.Json
- Immutable records with `init`-only properties
- Interface-based design, constructor-injected dependencies
- No `async void`
- Process memory reads must include bounds checks and null guards
- Key dependency: `Reloaded.Memory.Sigscan` for AOB/signature scanning
- Tests: xUnit + coverlet.collector + Microsoft.NET.Test.Sdk
- SendInput: prefer `--input-mode ScanCode` for movement tests; supports Space, Left, Up, Right, Down, Enter, Esc, Backspace, Tab, PageUp, PageDown

### Lua (5.1 only)
- All `Inspect.*` / `Command.*` wrapped in `pcall()`; nil-check results
- Minimize global state; prefer module-local variables
- Saved-variable tables must be backward-compatible
- No magic numbers

### Python
- Root `__init__.py` and `scripts/__init__.py` exist — project is a Python package
- Test files follow `test_<module>.py` naming, mirroring their source modules
- Python helpers should emit structured JSON summaries, explicit exit codes (0=pass, 1=error, 2=blocked-safe), and Markdown summaries
- Prefer `subprocess.run([...])` argument lists; do not compose shell command strings

### Python / PowerShell split (policy)
- **Python:** owns state machines, subprocess calls, JSON parsing, summaries, fail-closed decisions. **Always prefer calling Python scripts directly** (e.g., `python tools/riftreader_workflow/decision_packet.py --json`) rather than going through `.cmd` wrappers.
- **`.cmd` launchers:** keep dumb — cd to repo, call Python, forward args. Use only as a convenience shortcut when they already exist; do not create new ones for new logic.
- **PowerShell `.ps1`:** legacy leaf adapters only; do not create new orchestration in PS
- New workflow/helper code should be Python-first

### Commit / Git
- Stage explicit paths only (`git add path/to/file`); never `git add .`
- Do not push, branch-rewrite, or remote-mutate without explicit approval
- Use `git --no-pager` for diff/log to avoid pager stalls

### Custom Codebuff agents (`.agents/`)
- Three agents defined: `rift-readback` (read-only), `rift-discovery` (RE pipeline), `rift-proof` (promotion gates)
- Run `python scripts/agent-validate.py --verbose --json` after editing any `.agents/*.ts` file
- Snapshots live under `.agents/backup/snapshot-<timestamp>/`
- `rift-readback` has NO write tools — cannot modify files
- `rift-discovery` can spawn `rift-readback` for candidate validation; NEVER promotes
- `rift-proof` can spawn `rift-readback` for gate evidence; `promotionPerformed` is ALWAYS false
- Agent tool names must match the validated tool set (e.g., `researcher_web` not `web_search`)

## Gotchas & constraints

### Critical invariants
- **SavedVariables are NOT live IPC.** `ReaderBridgeExport.lua` updates only on `/reloadui`/logout/save. Never treat it as live movement truth.
- **Coordinate freshness requires API-now vs memory-now comparison.** PID/HWND match alone is not enough.
- **Struct offsets shift across game updates.** Validate anchors against addon exports every session.
- **Never hardcode addresses.** Always read trace artifacts or rebuild anchors at startup.

### Live movement / safety gates
- Live RIFT input, movement, target selection, debugger attach: **must ask for explicit approval**
- Proof promotion, actor-chain promotion: **must ask with required proof gates**
- `--movement-approved`, `--allow-current-truth-update`, `--run-proofonly`: separate explicit gates
- Fail closed on anchor loss, no progress, moving away, input failure, or timeout

### Cross-repo boundaries
- **ChromaLink:** external provider — read-only unless explicitly authorized
- **RiftScan:** external candidate/evidence provider — read-only by default
- Do not modify files in those repos from RiftReader tasks

### Reverse engineering
- Cheat Engine: validation aid only; no runtime CE dependency in reader
- x64dbg: attach/detach only with explicit authorization; at most one short HW watchpoint per decision
- Coordinate access events are candidate evidence until converted to repo-owned chain resolver
- Module-local pattern validation required — instructions must be within `rift_x64.exe` bounds

### Player facing / orientation
- **NOT exposed by RIFT Lua API.** Derive from memory basis matrix or position deltas.
- **Promoted facing target:** `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` — same owner as coordinates, 20 bytes before
- **Yaw formula:** `atan2(Z_at_0x314 - playerZ, X_at_0x30C - playerX)`
- **Turn rate discriminator:** offset 0x304 (float) — positive = left turn, negative = right turn
- Actor basis matrix: forward row at `+0x60`, duplicate basis at `+0x94` (historical, revalidate after updates)

### Target process
- Target explicitly selected Rift client processes and installs
- Do not assume cross-environment compatibility without verification
- Windows-only (Linux/Mac planned for future)

## Assistant policies (from agents.md)

- Lead with direct answer/result; use tables for status/blocks/options
- **Autonomous mode:** continue through safe checkpoints; stop only at gated boundaries (live input, debugger, push, promotion)
- **OpenCode is retired** for this repo — do not create/modify OpenCode code unless explicitly re-authorized
- **Model routing:** prefer stronger reasoning for live RIFT, x64dbg, coordinate truth, proof work; simpler models OK for docs/status
- **Context7:** use for .NET, PowerShell, library docs; do NOT use for local RiftReader debugging
- **Custom agents:** spawn `rift-readback` for coordinates, `rift-discovery` for RE, `rift-proof` for promotion gates
- **Non-Codex workflow:** use when Codex is unavailable — GitHub connector read-only, deliver edits as ZIP or applier

### Turn-aware route plan engine cross-check
The route planner cross-checks atan2-derived turn direction against the engine's 0x304 turn rate discriminator. If they disagree (e.g., atan2 says "left" but 0x304 says "right"), the route is **blocked** with a `turn-direction-mismatch` blocker. This prevents sending input when atan2 might be ambiguous.

### `--nav-state` pointer-chain readback pipeline

A read-only pointer-chain nav-state pipeline that independently reads yaw, turn rate (0x304), facing target, and pitch from the promoted static resolver — without game input, debuggers, or mutation.

**Architecture:** 6 tools use a single shared helper (`scripts/nav_state_readback.py`) to spawn the coordinate chain readback subprocess:

| Tool | `--nav-state` flag | How it uses the result |
|---|---|---|
| `static_owner_coordinate_chain_readback.py` | `--nav-state` | Produces nav-state (yaw, turn rate, facing target, pitch) |
| `decision_packet.py` | `--nav-state` | Includes `navigationPointerChains` in decision payload |
| `nav_state_freshness_watchdog.py` | N/A (always on) | Compares two reads 0.5s apart for correlation/drift |
| `static_owner_turn_aware_route_plan.py` | `--nav-state` | Cross-checks pointer-chain vs facing-discovery yaw/turn-rate |
| `static_owner_continuous_route_runner.py` | `--nav-state` | Per-iteration nav-state health monitoring during multi-segment routes |
| `navigation_target_watch.py` | `--nav-state` | Validates resolver health after finding RIFT window |

**Shared helper:** `scripts/nav_state_readback.py` — `read_nav_state()`
- Supports explicit target mode (`--pid`/`--hwnd`/`--module-base`)
- Supports current-truth mode (`--use-current-truth`/`--current-truth-json`)
- Returns standardized flat dict with all nav-state fields
- Handles subprocess spawning, JSON parsing, timeouts, and errors

**Safety markers (present on all paths):**
- `candidateOnly: true` — never used for auto-navigation decisions
- `actionableForNavigation: false` — no game input triggered
- Read-only subprocess — no debugger attach, no mutation

## Recovery docs (when state drifts)

Start here:
- `docs/recovery/README.md`
- `docs/recovery/current-truth.md`
- `docs/recovery/rebuild-runbook.md`
- `docs/recovery/coordinate-recovery-workflow.md`
